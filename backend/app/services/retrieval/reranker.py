"""候选文档 rerank 精排序。

bi-encoder 向量检索会分别编码 query 和 document，再用向量相似度做粗召回。
这种方式速度快，适合在大量 chunk 中找候选，但 query 和 document 之间
没有充分交互，因此排序精度有限。

rerank provider 会把 query 和候选文档成对评分，输出相关性分数。它通常
比 bi-encoder 排序更准确，但计算成本更高，无法直接用于全库检索。

因此本项目只在 RRF 融合后的少量候选上执行 rerank：

    粗召回 -> RRF 融合候选 -> rerank 精排 -> top-k 上下文

默认 provider 是本地 BAAI/bge-reranker-base Cross-Encoder。登录用户也
可以在设置页选择 Qwen、Voyage、Cohere、Jina 或自定义 rerank API，并
按厂商保存多份 API Key。
"""

import json
import os
from functools import lru_cache
from importlib import import_module
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from langchain_core.documents import Document
from openai import OpenAI

from app.core import config
from app.services.rerank_settings_service import (
    COHERE_RERANK_PROVIDER,
    DEFAULT_RERANK_MAX_RETRIES,
    DEFAULT_RERANK_TIMEOUT_SECONDS,
    LOCAL_RERANK_PROVIDER,
    OPENAI_COMPATIBLE_RERANK_PROVIDER,
    QWEN_RERANK_PROVIDER,
    RerankModelSettings,
    VOYAGE_RERANK_PROVIDER,
    get_effective_rerank_model_settings,
    normalize_rerank_provider,
    resolve_rerank_base_url,
    resolve_rerank_model_name,
)
from app.services.vectors.embedding_model import resolve_dashscope_api_key


DEFAULT_RERANKER_MODEL = str(config.RERANKER_MODEL_PATH)
DEFAULT_RERANKER_MAX_LENGTH = 384


def _post_json(
    url: str,
    api_key: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: float,
    max_retries: int,
) -> dict[str, Any]:
    """向远程 rerank provider 发送 JSON POST 请求并返回 JSON 响应。"""
    if not api_key.strip():
        raise RuntimeError("缺少当前用户的 rerank API Key。")

    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    attempts = max(max_retries, 0) + 1
    last_error: Exception | None = None
    for _ in range(attempts):
        request = Request(url, data=body, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                raw_body = response.read().decode("utf-8")
        except HTTPError as exc:
            last_error = exc
            if 400 <= exc.code < 500:
                break
            continue
        except URLError as exc:
            last_error = exc
            continue

        try:
            decoded = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise RuntimeError("rerank provider 响应不是有效 JSON") from exc
        if not isinstance(decoded, dict):
            raise RuntimeError("rerank provider 响应格式不是 JSON object")
        return decoded

    if isinstance(last_error, HTTPError):
        raise RuntimeError(
            f"rerank provider 调用失败，HTTP {last_error.code}"
        ) from last_error
    raise RuntimeError("rerank provider 调用失败") from last_error


def _extract_results(response: object, provider_name: str) -> list[dict[str, Any]]:
    """兼容多种远程 rerank 响应中的 results/data 结果数组。"""
    if hasattr(response, "model_dump"):
        response = response.model_dump()
    if not isinstance(response, dict):
        raise RuntimeError(f"{provider_name} rerank 响应格式不是 JSON object。")

    raw_results = response.get("results")
    if raw_results is None:
        raw_results = response.get("data")
    if raw_results is None:
        output = response.get("output")
        if isinstance(output, dict):
            raw_results = output.get("results")

    if not isinstance(raw_results, list):
        raise RuntimeError(f"{provider_name} rerank 响应缺少 results。")

    return [
        result
        for result in raw_results
        if isinstance(result, dict)
    ]


def _score_by_index(response: object, provider_name: str) -> dict[int, float]:
    """从 rerank 响应中提取原始候选 index 和 relevance score。"""
    scores: dict[int, float] = {}
    for fallback_index, result in enumerate(
        _extract_results(response, provider_name),
    ):
        raw_index = result.get("index", fallback_index)
        raw_score = result.get(
            "relevance_score",
            result.get("score"),
        )
        if raw_score is None:
            continue
        try:
            index = int(raw_index)
            score = float(raw_score)
        except (TypeError, ValueError):
            continue
        scores[index] = score
    return scores


def _rank_documents_from_scores(
    documents: list[Document],
    scores: dict[int, float],
    provider: str,
    top_k: int,
) -> list[Document]:
    """把 provider 返回的 index 分数写入文档 metadata 并排序。"""
    if not scores:
        raise RuntimeError("rerank 响应未返回可用分数。")

    scored_documents: list[Document] = []
    for index, document in enumerate(documents):
        if index not in scores:
            continue
        document.metadata["rerank_score"] = scores[index]
        scored_documents.append(document)

    reranked_documents = sorted(
        scored_documents,
        key=lambda document: document.metadata["rerank_score"],
        reverse=True,
    )
    for rank, document in enumerate(reranked_documents, start=1):
        document.metadata["rerank_rank"] = rank
        document.metadata["rerank_provider"] = provider

    return reranked_documents[:top_k]


def load_reranker_runtime() -> tuple[Any, Any, Any]:
    """按需加载 Cross-Encoder 依赖，避免默认镜像强制安装大模型栈。"""
    try:
        torch = import_module("torch")
        transformers = import_module("transformers")
    except ImportError as exc:
        raise RuntimeError(
            "CrossEncoder rerank 依赖未安装。默认 Docker 镜像会跳过 rerank，"
            "如需启用请安装 backend/requirements-rerank.txt。"
        ) from exc

    return (
        torch,
        transformers.AutoModelForSequenceClassification,
        transformers.AutoTokenizer,
    )


class LocalCrossEncoderReranker:
    """使用本地 Cross-Encoder 模型对候选文档精排序。"""

    provider = LOCAL_RERANK_PROVIDER

    def __init__(
        self,
        model_name: str = DEFAULT_RERANKER_MODEL,
        device: str | None = None,
    ) -> None:
        """加载本地 Cross-Encoder 模型和 tokenizer。"""
        torch, model_cls, tokenizer_cls = load_reranker_runtime()
        self.torch = torch
        self.model_name = model_name
        self.base_url = None
        self.device = device or (
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        self.tokenizer = tokenizer_cls.from_pretrained(
            model_name,
            local_files_only=True,
        )
        self.model = model_cls.from_pretrained(
            model_name,
            local_files_only=True,
        ).to(self.device)
        self.model.eval()

    def score_documents(
        self,
        query: str,
        documents: list[Document],
        batch_size: int = 8,
        max_length: int = DEFAULT_RERANKER_MAX_LENGTH,
    ) -> list[float]:
        """计算 query 与多个文档的相关性分数。

        每个候选会以 `(query, document.page_content)` 的形式输入模型。
        返回值是模型 logits，值越大表示候选和问题越相关。
        """
        scores: list[float] = []

        for start in range(0, len(documents), batch_size):
            batch_documents = documents[start:start + batch_size]
            features = self.tokenizer(
                [query] * len(batch_documents),
                [document.page_content for document in batch_documents],
                padding=True,
                truncation=True,
                max_length=max_length,
                return_tensors="pt",
            )
            features = {
                name: value.to(self.device)
                for name, value in features.items()
            }

            with self.torch.no_grad():
                logits = self.model(**features).logits

            # BGE reranker 输出 raw relevance score；排序时直接使用 logits。
            batch_scores = logits.view(-1).detach().cpu().float().tolist()
            scores.extend(batch_scores)

        return scores

    def rerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int = 5,
        batch_size: int = 8,
        max_length: int = DEFAULT_RERANKER_MAX_LENGTH,
    ) -> list[Document]:
        """返回按 Cross-Encoder 分数重排后的 top_k 文档。"""
        if not documents:
            return []

        scores = self.score_documents(
            query=query,
            documents=documents,
            batch_size=batch_size,
            max_length=max_length,
        )

        for document, score in zip(documents, scores, strict=True):
            document.metadata["rerank_score"] = score

        reranked_documents = sorted(
            documents,
            key=lambda document: document.metadata["rerank_score"],
            reverse=True,
        )
        for rank, document in enumerate(reranked_documents, start=1):
            document.metadata["rerank_rank"] = rank
            document.metadata["rerank_provider"] = LOCAL_RERANK_PROVIDER

        return reranked_documents[:top_k]


@lru_cache(maxsize=4)
def get_local_reranker(
    model_name: str = DEFAULT_RERANKER_MODEL,
) -> LocalCrossEncoderReranker:
    """缓存本地 reranker，避免每次检索重复加载模型。"""
    return LocalCrossEncoderReranker(model_name=model_name)


class DashScopeQwenReranker:
    """通过阿里云 Qwen rerank API 对候选文档精排序。"""

    provider = QWEN_RERANK_PROVIDER

    def __init__(
        self,
        model_name: str,
        base_url: str,
        instruct: str = "",
        api_key: str | None = None,
        timeout_seconds: float = DEFAULT_RERANK_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_RERANK_MAX_RETRIES,
    ) -> None:
        """保存远程 rerank 调用配置。"""
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.instruct = instruct.strip()
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.client: OpenAI | None = None

    def _get_client(self) -> OpenAI:
        """按需创建 OpenAI-compatible client。"""
        if self.client is None:
            self.client = OpenAI(
                api_key=self.api_key or resolve_dashscope_api_key("rerank"),
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                max_retries=self.max_retries,
            )
        return self.client

    def _build_payload(
        self,
        query: str,
        documents: list[Document],
        top_k: int,
    ) -> dict[str, object]:
        """构造 /reranks 请求体。"""
        payload: dict[str, object] = {
            "model": self.model_name,
            "query": query,
            "documents": [document.page_content for document in documents],
            "top_n": top_k,
        }
        if self.instruct:
            payload["instruct"] = self.instruct
        return payload

    def rerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int = 5,
        batch_size: int = 8,
        max_length: int = DEFAULT_RERANKER_MAX_LENGTH,
    ) -> list[Document]:
        """调用 OpenAI-compatible rerank API 并返回排序后的 top_k 文档。"""
        if not documents:
            return []

        response = self._get_client().post(
            "/reranks",
            body=self._build_payload(query, documents, top_k),
            cast_to=object,
        )
        return _rank_documents_from_scores(
            documents,
            _score_by_index(response, "Qwen"),
            self.provider,
            top_k,
        )


class OpenAICompatibleReranker(DashScopeQwenReranker):
    """通过自定义 OpenAI-compatible /reranks API 对候选文档精排序。"""

    provider = OPENAI_COMPATIBLE_RERANK_PROVIDER


class HttpJsonReranker:
    """通过 provider 原生 JSON API 对候选文档精排序。"""

    def __init__(self, settings: RerankModelSettings) -> None:
        """保存远程 JSON rerank 调用配置。"""
        self.provider = settings.provider
        self.model_name = settings.model
        self.api_key = settings.api_key
        self.base_url = resolve_rerank_base_url(
            settings.provider,
            settings.base_url,
        )
        self.timeout_seconds = settings.timeout_seconds
        self.max_retries = settings.max_retries

    def _endpoint_path(self) -> str:
        """返回当前 provider 的 rerank endpoint path。"""
        if self.provider == COHERE_RERANK_PROVIDER:
            return "/v2/rerank"
        return "/rerank"

    def _build_payload(
        self,
        query: str,
        documents: list[Document],
        top_k: int,
    ) -> dict[str, object]:
        """构造 provider 原生 rerank 请求体。"""
        document_texts = [document.page_content for document in documents]
        if self.provider == VOYAGE_RERANK_PROVIDER:
            return {
                "model": self.model_name,
                "query": query,
                "documents": document_texts,
                "top_k": top_k,
                "return_documents": False,
                "truncation": True,
            }
        return {
            "model": self.model_name,
            "query": query,
            "documents": document_texts,
            "top_n": top_k,
            "return_documents": False,
        }

    def rerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int = 5,
        batch_size: int = 8,
        max_length: int = DEFAULT_RERANKER_MAX_LENGTH,
    ) -> list[Document]:
        """调用远程 JSON rerank API 并返回排序后的 top_k 文档。"""
        if not documents:
            return []

        response = _post_json(
            f"{self.base_url}{self._endpoint_path()}",
            self.api_key,
            self._build_payload(query, documents, top_k),
            timeout_seconds=self.timeout_seconds,
            max_retries=self.max_retries,
        )
        return _rank_documents_from_scores(
            documents,
            _score_by_index(response, self.provider),
            self.provider,
            top_k,
        )


def create_reranker_from_settings(
    settings: RerankModelSettings,
) -> LocalCrossEncoderReranker | DashScopeQwenReranker | HttpJsonReranker:
    """根据用户 rerank 设置创建对应 provider。"""
    if settings.provider == LOCAL_RERANK_PROVIDER:
        return get_local_reranker(settings.model)
    if settings.provider == QWEN_RERANK_PROVIDER:
        return DashScopeQwenReranker(
            model_name=settings.model,
            base_url=resolve_rerank_base_url(
                settings.provider,
                settings.base_url,
            ) or "",
            instruct=settings.instruct or "",
            api_key=settings.api_key,
            timeout_seconds=settings.timeout_seconds,
            max_retries=settings.max_retries,
        )
    if settings.provider == OPENAI_COMPATIBLE_RERANK_PROVIDER:
        return OpenAICompatibleReranker(
            model_name=settings.model,
            base_url=resolve_rerank_base_url(
                settings.provider,
                settings.base_url,
            ) or "",
            instruct=settings.instruct or "",
            api_key=settings.api_key,
            timeout_seconds=settings.timeout_seconds,
            max_retries=settings.max_retries,
        )
    return HttpJsonReranker(settings)


def _build_env_rerank_settings(
    model_name: str = DEFAULT_RERANKER_MODEL,
) -> RerankModelSettings:
    """兼容历史环境变量，生成未传 user_id 时使用的 rerank 设置。"""
    provider = normalize_rerank_provider(
        os.environ.get("RERANK_PROVIDER")
        or config.RERANK_PROVIDER
        or LOCAL_RERANK_PROVIDER,
    )
    configured_model = os.environ.get("RERANK_MODEL") or config.RERANK_MODEL
    if not configured_model and provider == LOCAL_RERANK_PROVIDER:
        configured_model = model_name
    model = resolve_rerank_model_name(provider, configured_model)
    return RerankModelSettings(
        provider=provider,
        model=model,
        api_key=os.environ.get("RERANK_API_KEY", ""),
        base_url=os.environ.get("RERANK_BASE_URL") or config.RERANK_BASE_URL,
        instruct=os.environ.get("RERANK_INSTRUCT") or config.RERANK_INSTRUCT,
        timeout_seconds=DEFAULT_RERANK_TIMEOUT_SECONDS,
        max_retries=DEFAULT_RERANK_MAX_RETRIES,
    )


def get_reranker(
    model_name: str = DEFAULT_RERANKER_MODEL,
    user_id: int | None = None,
) -> LocalCrossEncoderReranker | DashScopeQwenReranker | HttpJsonReranker:
    """根据当前用户设置或历史环境变量获取 reranker。"""
    settings = (
        get_effective_rerank_model_settings(user_id)
        if user_id is not None
        else _build_env_rerank_settings(model_name)
    )
    return create_reranker_from_settings(settings)

"""候选文档 rerank 精排序。

bi-encoder 向量检索会分别编码 query 和 document，再用向量相似度做粗召回。
这种方式速度快，适合在大量 chunk 中找候选，但 query 和 document 之间
没有充分交互，因此排序精度有限。

rerank provider 会把 query 和候选文档成对评分，输出相关性分数。它通常
比 bi-encoder 排序更准确，但计算成本更高，无法直接用于全库检索。

因此本项目只在 RRF 融合后的少量候选上执行 rerank：

    粗召回 -> RRF 融合候选 -> rerank 精排 -> top-k 上下文

默认 provider 是本地 BAAI/bge-reranker-base Cross-Encoder；也可以通过
`RERANK_PROVIDER=qwen` 切到阿里云 Qwen rerank API。BGE 输出的是 raw
relevance score，排序只需要比较分数大小，因此直接使用 logits，不额外做
sigmoid。
"""

import os
from functools import lru_cache
from importlib import import_module
from typing import Any

from langchain_core.documents import Document
from openai import OpenAI

from app.core import config
from app.services.vectors.embedding_model import (
    QWEN_EMBEDDING_PROVIDER_ALIASES,
    resolve_dashscope_api_key,
)


LOCAL_RERANK_PROVIDER = "local"
QWEN_RERANK_PROVIDER = "qwen"
DEFAULT_RERANKER_MODEL = str(config.RERANKER_MODEL_PATH)
DEFAULT_QWEN_RERANK_MODEL = "qwen3-rerank"
DEFAULT_RERANKER_MAX_LENGTH = 384


def normalize_rerank_provider(raw_provider: str | None = None) -> str:
    """归一化 rerank provider 名称。"""
    provider = (
        raw_provider
        or os.environ.get("RERANK_PROVIDER")
        or config.RERANK_PROVIDER
        or LOCAL_RERANK_PROVIDER
    ).strip().lower() or LOCAL_RERANK_PROVIDER
    if provider in {"local", "cross_encoder", "cross-encoder", "bge"}:
        return LOCAL_RERANK_PROVIDER
    if provider in QWEN_EMBEDDING_PROVIDER_ALIASES:
        return QWEN_RERANK_PROVIDER
    raise ValueError(f"不支持的 rerank provider：{provider}")


def resolve_rerank_model_name(
    provider: str,
    local_model_name: str = DEFAULT_RERANKER_MODEL,
) -> str:
    """根据 provider 解析 rerank 模型名。"""
    configured_model = (
        os.environ.get("RERANK_MODEL")
        or config.RERANK_MODEL
    ).strip()
    if configured_model:
        return configured_model
    if provider == QWEN_RERANK_PROVIDER:
        return DEFAULT_QWEN_RERANK_MODEL
    return local_model_name


def resolve_qwen_rerank_base_url() -> str:
    """读取阿里云 OpenAI-compatible rerank API 地址。"""
    base_url = (
        os.environ.get("RERANK_BASE_URL")
        or config.RERANK_BASE_URL
    ).strip()
    if not base_url:
        raise RuntimeError(
            "使用 Qwen rerank 时需要配置 RERANK_BASE_URL，例如 "
            "https://<WorkspaceId>.ap-southeast-1.maas.aliyuncs.com/compatible-api/v1"
        )
    return base_url.rstrip("/")


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

    def __init__(
        self,
        model_name: str = DEFAULT_RERANKER_MODEL,
        device: str | None = None,
    ) -> None:
        torch, model_cls, tokenizer_cls = load_reranker_runtime()
        self.torch = torch
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

        return reranked_documents[:top_k]


@lru_cache(maxsize=1)
def get_local_reranker(
    model_name: str = DEFAULT_RERANKER_MODEL,
) -> LocalCrossEncoderReranker:
    """缓存本地 reranker，避免每次检索重复加载模型。"""
    return LocalCrossEncoderReranker(model_name=model_name)


class DashScopeQwenReranker:
    """通过阿里云 Qwen rerank API 对候选文档精排序。"""

    def __init__(
        self,
        model_name: str,
        base_url: str,
        instruct: str = "",
    ) -> None:
        """保存远程 rerank 调用配置。"""
        self.model_name = model_name
        self.base_url = base_url
        self.instruct = instruct.strip()
        self.client: OpenAI | None = None

    def _get_client(self) -> OpenAI:
        """按需创建阿里云 OpenAI-compatible client。"""
        if self.client is None:
            self.client = OpenAI(
                api_key=resolve_dashscope_api_key("rerank"),
                base_url=self.base_url,
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

    def _extract_results(self, response: object) -> list[dict[str, Any]]:
        """兼容 OpenAI-compatible 与 DashScope 风格的 rerank 响应。"""
        if hasattr(response, "model_dump"):
            response = response.model_dump()
        if not isinstance(response, dict):
            raise RuntimeError("Qwen rerank 响应格式不是 JSON object。")

        raw_results = response.get("results")
        if raw_results is None:
            output = response.get("output")
            if isinstance(output, dict):
                raw_results = output.get("results")

        if not isinstance(raw_results, list):
            raise RuntimeError("Qwen rerank 响应缺少 results。")

        return [
            result
            for result in raw_results
            if isinstance(result, dict)
        ]

    def _score_by_index(self, response: object) -> dict[int, float]:
        """从 rerank 响应中提取原始候选 index 和 relevance score。"""
        scores: dict[int, float] = {}
        for fallback_index, result in enumerate(self._extract_results(response)):
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

    def rerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int = 5,
        batch_size: int = 8,
        max_length: int = DEFAULT_RERANKER_MAX_LENGTH,
    ) -> list[Document]:
        """调用 Qwen rerank API 并返回按相关性排序后的 top_k 文档。"""
        if not documents:
            return []

        response = self._get_client().post(
            "/reranks",
            body=self._build_payload(query, documents, top_k),
            cast_to=object,
        )
        scores = self._score_by_index(response)
        if not scores:
            raise RuntimeError("Qwen rerank 响应未返回可用分数。")

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
            document.metadata["rerank_provider"] = QWEN_RERANK_PROVIDER

        return reranked_documents[:top_k]


def get_reranker(
    model_name: str = DEFAULT_RERANKER_MODEL,
) -> LocalCrossEncoderReranker | DashScopeQwenReranker:
    """根据环境变量获取本地或远程 reranker。"""
    provider = normalize_rerank_provider()
    resolved_model = resolve_rerank_model_name(provider, model_name)
    if provider == QWEN_RERANK_PROVIDER:
        return DashScopeQwenReranker(
            model_name=resolved_model,
            base_url=resolve_qwen_rerank_base_url(),
            instruct=(
                os.environ.get("RERANK_INSTRUCT")
                or config.RERANK_INSTRUCT
            ),
        )
    return get_local_reranker(resolved_model)

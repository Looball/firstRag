from __future__ import annotations

import json
import os
from typing import Any, List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from langchain_core.embeddings import Embeddings
from openai import OpenAI
from zai import ZhipuAiClient

from app.services.vectors.embedding_settings_service import (
    COHERE_EMBEDDING_PROVIDER,
    DEFAULT_COHERE_EMBEDDING_BASE_URL,
    DEFAULT_VOYAGE_EMBEDDING_BASE_URL,
    EmbeddingModelSettings,
    JINA_EMBEDDING_PROVIDER,
    OPENAI_COMPATIBLE_EMBEDDING_PROVIDER,
    OPENAI_EMBEDDING_PROVIDER,
    QWEN_EMBEDDING_PROVIDER,
    VOYAGE_EMBEDDING_PROVIDER,
    ZHIPU_EMBEDDING_PROVIDER,
    get_effective_embedding_model_settings,
    resolve_embedding_base_url,
)


def is_placeholder_api_key(value: str) -> bool:
    """判断 provider Key 是否为空或仍是模板占位值。"""
    normalized = value.strip().lower()
    return not normalized or normalized.startswith("replace-with-")


def get_embedding_cache_identity(user_id: int) -> tuple[str, str, str, str]:
    """返回 query embedding 缓存使用的 provider/model 标识。"""
    settings = get_effective_embedding_model_settings(user_id)
    return (
        str(user_id),
        settings.provider,
        settings.model,
        str(settings.dimensions or ""),
    )


def resolve_dashscope_api_key(purpose: str = "rerank") -> str:
    """读取阿里云 DashScope/Qwen API Key，兼容历史环境变量配置。"""
    provider_specific_key = (
        os.environ.get("RERANK_API_KEY") if purpose == "rerank" else None
    )
    candidate_keys = [
        provider_specific_key,
        os.environ.get("DASHSCOPE_API_KEY"),
        os.environ.get("QWEN_API_KEY"),
    ]
    for api_key in candidate_keys:
        if api_key and not is_placeholder_api_key(api_key):
            return api_key.strip()

    raise RuntimeError(
        "缺少阿里云 DashScope/Qwen API Key，请配置 DASHSCOPE_API_KEY、"
        "QWEN_API_KEY 或对应的 RERANK_API_KEY。"
    )


def _post_json(
    url: str,
    api_key: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: float,
    max_retries: int,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """向 provider 发送 JSON POST 请求并返回 JSON object 响应。"""
    if not api_key.strip():
        raise RuntimeError("缺少当前用户的 embedding API Key。")

    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        **(extra_headers or {}),
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
            raise RuntimeError("embedding provider 响应不是有效 JSON") from exc
        if not isinstance(decoded, dict):
            raise RuntimeError("embedding provider 响应格式不是 JSON object")
        return decoded

    if isinstance(last_error, HTTPError):
        raise RuntimeError(
            f"embedding provider 调用失败，HTTP {last_error.code}"
        ) from last_error
    raise RuntimeError("embedding provider 调用失败") from last_error


def _extract_openai_embeddings(response: Any) -> list[list[float]]:
    """从 OpenAI-compatible embedding 响应中提取向量列表。"""
    return [
        list(item.embedding)
        for item in response.data
    ]


def create_embedding_model_from_settings(
    settings: EmbeddingModelSettings,
) -> Embeddings:
    """根据用户配置创建当前 embedding provider。"""
    if settings.provider == ZHIPU_EMBEDDING_PROVIDER:
        return ZhipuAIEmbeddings(settings)
    if settings.provider == QWEN_EMBEDDING_PROVIDER:
        return DashScopeQwenEmbeddings(settings)
    if settings.provider == VOYAGE_EMBEDDING_PROVIDER:
        return VoyageAIEmbeddings(settings)
    if settings.provider == COHERE_EMBEDDING_PROVIDER:
        return CohereEmbeddings(settings)
    return OpenAICompatibleEmbeddings(settings)


def create_embedding_model(user_id: int) -> Embeddings:
    """根据当前用户保存的配置创建 embedding provider。"""
    return create_embedding_model_from_settings(
        get_effective_embedding_model_settings(user_id),
    )


class ZhipuAIEmbeddings(Embeddings):
    """`Zhipuai Embeddings` embedding models."""

    def __init__(self, settings: EmbeddingModelSettings):
        """初始化 embedding 包装器，客户端在实际调用时再创建。"""
        self.client: ZhipuAiClient | None = None
        self.settings = settings
        self.model = settings.model

    def _get_client(self) -> ZhipuAiClient:
        """按需创建智谱客户端。"""
        api_key = self.settings.api_key.strip()
        if not api_key:
            raise RuntimeError("缺少当前用户的智谱 embedding API Key。")
        if self.client is None:
            self.client = ZhipuAiClient(api_key=api_key)
        return self.client

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        生成输入文本列表的embedding。

        Args:
            texts: 要生成embedding的文本列表。

        Returns:
            输入列表中每个文档的embedding列表。
        """
        batch_size = 64  # 智谱AI embedding一次最多接收64条
        all_embeddings = []
        client = self._get_client()

        for start in range(0, len(texts), batch_size):
            batch_texts = texts[start:start + batch_size]
            response = client.embeddings.create(
                model=self.model,
                input=batch_texts,
            )
            all_embeddings.extend(
                item.embedding for item in response.data
            )

        return all_embeddings

    def embed_query(self, text: str) -> List[float]:
        """
        生成输入文本的embedding。

        Args:
            text: 要生成embedding的文本。

        Returns:
            输入文本的embedding。
        """
        return self.embed_documents([text])[0]


class OpenAICompatibleEmbeddings(Embeddings):
    """OpenAI-compatible embedding provider 封装。"""

    def __init__(self, settings: EmbeddingModelSettings) -> None:
        """延迟创建 OpenAI client。"""
        self.client: OpenAI | None = None
        self.settings = settings
        self.model = settings.model
        self.base_url = resolve_embedding_base_url(
            settings.provider,
            settings.base_url,
        )
        self.dimensions = settings.dimensions

    def _get_client(self) -> OpenAI:
        """按需创建 OpenAI-compatible client。"""
        if self.client is None:
            self.client = OpenAI(
                api_key=self.settings.api_key,
                base_url=self.base_url,
                timeout=self.settings.timeout_seconds,
                max_retries=self.settings.max_retries,
            )
        return self.client

    def _build_request_payload(self, texts: list[str]) -> dict[str, object]:
        """构造 OpenAI-compatible embeddings 请求体。"""
        payload: dict[str, object] = {
            "model": self.model,
            "input": texts,
        }
        if self.dimensions is not None:
            payload["dimensions"] = self.dimensions
        return payload

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """通过 OpenAI-compatible embeddings API 生成文档向量。"""
        batch_size = 10
        all_embeddings: list[list[float]] = []
        client = self._get_client()

        for start in range(0, len(texts), batch_size):
            batch_texts = texts[start:start + batch_size]
            response = client.embeddings.create(
                **self._build_request_payload(batch_texts),
            )
            all_embeddings.extend(_extract_openai_embeddings(response))

        return all_embeddings

    def embed_query(self, text: str) -> List[float]:
        """通过 OpenAI-compatible embeddings API 生成 query 向量。"""
        return self.embed_documents([text])[0]


class DashScopeQwenEmbeddings(OpenAICompatibleEmbeddings):
    """阿里云 Model Studio / DashScope OpenAI-compatible embedding 封装。"""


class VoyageAIEmbeddings(Embeddings):
    """Voyage AI embedding provider 封装。"""

    def __init__(self, settings: EmbeddingModelSettings) -> None:
        """保存 Voyage embedding 调用配置。"""
        self.settings = settings
        self.model = settings.model
        self.base_url = (
            settings.base_url or DEFAULT_VOYAGE_EMBEDDING_BASE_URL
        ).rstrip("/")

    def _embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        """调用 Voyage embedding API 生成指定 input_type 的向量。"""
        payload: dict[str, Any] = {
            "model": self.model,
            "input": texts,
            "input_type": input_type,
            "truncation": True,
        }
        if self.settings.dimensions is not None:
            payload["output_dimension"] = self.settings.dimensions
        response = _post_json(
            f"{self.base_url}/embeddings",
            self.settings.api_key,
            payload,
            timeout_seconds=self.settings.timeout_seconds,
            max_retries=self.settings.max_retries,
        )
        data = response.get("data")
        if not isinstance(data, list):
            raise RuntimeError("Voyage embedding 响应缺少 data")
        return [
            list(item["embedding"])
            for item in data
            if isinstance(item, dict) and isinstance(item.get("embedding"), list)
        ]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """通过 Voyage embedding API 生成文档向量。"""
        return self._embed(list(texts), "document")

    def embed_query(self, text: str) -> List[float]:
        """通过 Voyage embedding API 生成 query 向量。"""
        return self._embed([text], "query")[0]


class CohereEmbeddings(Embeddings):
    """Cohere Embed v2 provider 封装。"""

    def __init__(self, settings: EmbeddingModelSettings) -> None:
        """保存 Cohere embedding 调用配置。"""
        self.settings = settings
        self.model = settings.model
        self.base_url = (
            settings.base_url or DEFAULT_COHERE_EMBEDDING_BASE_URL
        ).rstrip("/")

    def _embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        """调用 Cohere v2 embed API 生成指定 input_type 的向量。"""
        payload: dict[str, Any] = {
            "model": self.model,
            "inputs": [
                {"content": [{"type": "text", "text": text}]}
                for text in texts
            ],
            "input_type": input_type,
            "embedding_types": ["float"],
        }
        response = _post_json(
            f"{self.base_url}/v2/embed",
            self.settings.api_key,
            payload,
            timeout_seconds=self.settings.timeout_seconds,
            max_retries=self.settings.max_retries,
        )
        embeddings = response.get("embeddings")
        if not isinstance(embeddings, dict):
            raise RuntimeError("Cohere embedding 响应缺少 embeddings")
        floats = embeddings.get("float")
        if not isinstance(floats, list):
            raise RuntimeError("Cohere embedding 响应缺少 float embeddings")
        return [
            list(item)
            for item in floats
            if isinstance(item, list)
        ]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """通过 Cohere embed API 生成文档向量。"""
        return self._embed(list(texts), "search_document")

    def embed_query(self, text: str) -> List[float]:
        """通过 Cohere embed API 生成 query 向量。"""
        return self._embed([text], "search_query")[0]


__all__ = [
    "CohereEmbeddings",
    "DashScopeQwenEmbeddings",
    "JINA_EMBEDDING_PROVIDER",
    "OpenAICompatibleEmbeddings",
    "OPENAI_COMPATIBLE_EMBEDDING_PROVIDER",
    "OPENAI_EMBEDDING_PROVIDER",
    "QWEN_EMBEDDING_PROVIDER",
    "VoyageAIEmbeddings",
    "ZhipuAIEmbeddings",
    "create_embedding_model",
    "create_embedding_model_from_settings",
    "get_embedding_cache_identity",
    "resolve_dashscope_api_key",
]

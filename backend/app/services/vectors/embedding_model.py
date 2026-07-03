from __future__ import annotations

import os
from typing import List

from langchain_core.embeddings import Embeddings
from openai import OpenAI
from zai import ZhipuAiClient

from app.services.vectors.embedding_settings_service import (
    DEFAULT_QWEN_EMBEDDING_BASE_URL,
    EmbeddingModelSettings,
    QWEN_EMBEDDING_PROVIDER,
    get_effective_embedding_model_settings,
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
    """读取阿里云 DashScope/Qwen API Key，支持 rerank 专用 Key 和通用 Key。"""
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


def create_embedding_model_from_settings(
    settings: EmbeddingModelSettings,
) -> Embeddings:
    """根据用户配置创建当前 embedding provider。"""
    if settings.provider == QWEN_EMBEDDING_PROVIDER:
        return DashScopeQwenEmbeddings(settings)
    return ZhipuAIEmbeddings(settings)


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


class DashScopeQwenEmbeddings(Embeddings):
    """阿里云 Model Studio / DashScope OpenAI-compatible embedding 封装。"""

    def __init__(self, settings: EmbeddingModelSettings) -> None:
        """延迟创建 OpenAI client。"""
        self.client: OpenAI | None = None
        self.settings = settings
        self.model = settings.model
        self.base_url = settings.base_url or DEFAULT_QWEN_EMBEDDING_BASE_URL
        self.dimensions = settings.dimensions

    def _get_client(self) -> OpenAI:
        """按需创建阿里云 OpenAI-compatible client。"""
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
        """通过阿里云 Qwen embedding API 生成文档向量。"""
        batch_size = 10
        all_embeddings: list[list[float]] = []
        client = self._get_client()

        for start in range(0, len(texts), batch_size):
            batch_texts = texts[start:start + batch_size]
            response = client.embeddings.create(
                **self._build_request_payload(batch_texts),
            )
            all_embeddings.extend(
                item.embedding for item in response.data
            )

        return all_embeddings

    def embed_query(self, text: str) -> List[float]:
        """通过阿里云 Qwen embedding API 生成 query 向量。"""
        return self.embed_documents([text])[0]

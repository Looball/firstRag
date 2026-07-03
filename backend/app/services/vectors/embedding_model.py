from __future__ import annotations

import os
from typing import List

from langchain_core.embeddings import Embeddings
from openai import OpenAI
from zai import ZhipuAiClient

from app.core import config


ZHIPU_EMBEDDING_PROVIDER = "zhipuai"
QWEN_EMBEDDING_PROVIDER = "qwen"
DEFAULT_ZHIPU_EMBEDDING_MODEL = "embedding-3"
DEFAULT_QWEN_EMBEDDING_MODEL = "text-embedding-v4"
DEFAULT_QWEN_EMBEDDING_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
QWEN_EMBEDDING_PROVIDER_ALIASES = {"qwen", "dashscope", "aliyun", "aliyun-qwen"}
ZHIPU_EMBEDDING_PROVIDER_ALIASES = {"zhipu", "zhipuai", "glm"}


def is_placeholder_api_key(value: str) -> bool:
    """判断 provider Key 是否为空或仍是模板占位值。"""
    normalized = value.strip().lower()
    return not normalized or normalized.startswith("replace-with-")


def normalize_embedding_provider(raw_provider: str | None = None) -> str:
    """归一化 embedding provider 名称。"""
    provider = (
        raw_provider
        or os.environ.get("EMBEDDING_PROVIDER")
        or config.EMBEDDING_PROVIDER
        or ZHIPU_EMBEDDING_PROVIDER
    ).strip().lower() or ZHIPU_EMBEDDING_PROVIDER
    if provider in ZHIPU_EMBEDDING_PROVIDER_ALIASES:
        return ZHIPU_EMBEDDING_PROVIDER
    if provider in QWEN_EMBEDDING_PROVIDER_ALIASES:
        return QWEN_EMBEDDING_PROVIDER
    raise ValueError(f"不支持的 embedding provider：{provider}")


def resolve_embedding_model_name(provider: str) -> str:
    """根据 provider 解析 embedding 模型名。"""
    configured_model = (
        os.environ.get("EMBEDDING_MODEL")
        or config.EMBEDDING_MODEL
    ).strip()
    if configured_model:
        return configured_model
    if provider == QWEN_EMBEDDING_PROVIDER:
        return DEFAULT_QWEN_EMBEDDING_MODEL
    return DEFAULT_ZHIPU_EMBEDDING_MODEL


def resolve_embedding_dimensions() -> int | None:
    """读取可选 embedding 维度配置；未配置时使用 provider 默认值。"""
    raw_value = (
        os.environ.get("EMBEDDING_DIMENSIONS")
        or str(config.EMBEDDING_DIMENSIONS or "")
    ).strip()
    if not raw_value:
        return None
    try:
        dimensions = int(raw_value)
    except ValueError as exc:
        raise RuntimeError("EMBEDDING_DIMENSIONS 必须是正整数。") from exc
    if dimensions <= 0:
        return None
    return dimensions


def get_embedding_cache_identity() -> tuple[str, str]:
    """返回 query embedding 缓存使用的 provider/model 标识。"""
    provider = normalize_embedding_provider()
    return provider, resolve_embedding_model_name(provider)


def resolve_dashscope_api_key(purpose: str = "embedding") -> str:
    """读取阿里云 DashScope/Qwen API Key，支持专用 Key 和通用 Key。"""
    provider_specific_key = (
        os.environ.get("EMBEDDING_API_KEY")
        if purpose == "embedding"
        else os.environ.get("RERANK_API_KEY")
    )
    candidate_keys = [
        provider_specific_key,
        os.environ.get("EMBEDDING_API_KEY"),
        os.environ.get("DASHSCOPE_API_KEY"),
        os.environ.get("QWEN_API_KEY"),
    ]
    if (
        (os.environ.get("LLM_PROVIDER") or config.LLM_PROVIDER).strip().lower()
        == "qwen"
    ):
        candidate_keys.append(os.environ.get("LLM_API_KEY"))

    for api_key in candidate_keys:
        if api_key and not is_placeholder_api_key(api_key):
            return api_key.strip()

    raise RuntimeError(
        "缺少阿里云 DashScope/Qwen API Key，请配置 DASHSCOPE_API_KEY、"
        "QWEN_API_KEY 或对应的 *_API_KEY 后重启 backend/worker。"
    )


def resolve_embedding_base_url(provider: str) -> str | None:
    """解析 embedding API 地址。"""
    configured_base_url = (
        os.environ.get("EMBEDDING_BASE_URL")
        or config.EMBEDDING_BASE_URL
    ).strip()
    if configured_base_url:
        return configured_base_url.rstrip("/")
    if provider == QWEN_EMBEDDING_PROVIDER:
        return DEFAULT_QWEN_EMBEDDING_BASE_URL
    return None


def create_embedding_model() -> Embeddings:
    """根据环境变量创建当前 embedding provider。"""
    provider = normalize_embedding_provider()
    if provider == QWEN_EMBEDDING_PROVIDER:
        return DashScopeQwenEmbeddings()
    return ZhipuAIEmbeddings()


class ZhipuAIEmbeddings(Embeddings):
    """`Zhipuai Embeddings` embedding models."""

    def __init__(self):
        """
        初始化 embedding 包装器，客户端在实际调用时再创建。

        使用环境变量：ZAI_EMD_API
        """
        self.client: ZhipuAiClient | None = None

    def _get_client(self) -> ZhipuAiClient:
        """按需创建智谱客户端，避免缺少 Key 时影响服务启动。"""
        api_key = (os.environ.get("ZAI_EMD_API") or "").strip()
        if not api_key or api_key.startswith("replace-with-"):
            raise RuntimeError(
                "缺少环境变量 ZAI_EMD_API，请配置后重启 backend/worker 再执行向量化。"
            )
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
                model=resolve_embedding_model_name(ZHIPU_EMBEDDING_PROVIDER),
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

    def __init__(self) -> None:
        """延迟创建 OpenAI client，避免缺少 Key 时阻塞 Docker 启动。"""
        self.client: OpenAI | None = None
        self.model = resolve_embedding_model_name(QWEN_EMBEDDING_PROVIDER)
        self.base_url = resolve_embedding_base_url(QWEN_EMBEDDING_PROVIDER)
        self.dimensions = resolve_embedding_dimensions()

    def _get_client(self) -> OpenAI:
        """按需创建阿里云 OpenAI-compatible client。"""
        if self.client is None:
            self.client = OpenAI(
                api_key=resolve_dashscope_api_key("embedding"),
                base_url=self.base_url,
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

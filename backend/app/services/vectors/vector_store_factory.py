"""创建当前启用的 provider-neutral vector store。"""

import hashlib
from pathlib import Path
import re

from langchain_chroma import Chroma

from app.core.config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_HOST,
    CHROMA_PORT,
    CHROMA_SSL,
    VECTOR_STORE_PATH,
)
from app.services.vectors.chroma_vector_store import ChromaVectorStore
from app.services.vectors.embedding_model import create_embedding_model_from_settings
from app.services.vectors.embedding_settings_service import (
    EmbeddingModelSettings,
    get_effective_embedding_model_settings,
)
from app.services.vectors.vector_store import VectorStoreBoundary


def _normalize_collection_name_part(value: str) -> str:
    """将 collection 名称片段规范化为后端均可接受的安全字符。"""
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower())
    normalized = normalized.strip("-_")
    return normalized or "collection"


def build_user_vector_collection_name(
    base_collection_name: str,
    user_id: int,
    settings: EmbeddingModelSettings,
) -> str:
    """按用户和 embedding identity 生成稳定隔离的 collection 名称。"""
    identity = "|".join([
        str(user_id),
        settings.provider,
        settings.model,
        str(settings.dimensions or ""),
    ])
    digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:12]
    base = _normalize_collection_name_part(base_collection_name)[:24]
    collection_name = f"{base}-u{user_id}-{digest}"
    return collection_name[:63].strip("-_") or f"u{user_id}-{digest}"


def get_vector_store(
    user_id: int | None = None,
    persist_directory: str | Path = VECTOR_STORE_PATH,
    collection_name: str = CHROMA_COLLECTION_NAME,
) -> VectorStoreBoundary:
    """创建当前 Chroma adapter；后续 provider 切换由本工厂收口。"""
    resolved_collection_name = collection_name
    embedding_function = None
    if user_id is not None:
        settings = get_effective_embedding_model_settings(user_id)
        resolved_collection_name = build_user_vector_collection_name(
            collection_name,
            user_id,
            settings,
        )
        embedding_function = create_embedding_model_from_settings(settings)

    common_options = {
        "collection_name": resolved_collection_name,
        "embedding_function": embedding_function,
    }
    if CHROMA_HOST:
        client = Chroma(
            **common_options,
            host=CHROMA_HOST,
            port=CHROMA_PORT,
            ssl=CHROMA_SSL,
        )
    else:
        client = Chroma(
            **common_options,
            persist_directory=str(persist_directory),
        )
    return ChromaVectorStore(client, resolved_collection_name)

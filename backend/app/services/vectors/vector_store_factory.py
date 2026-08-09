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
    MILVUS_COLLECTION_PREFIX,
    MILVUS_CONSISTENCY_LEVEL,
    MILVUS_DATABASE,
    MILVUS_TIMEOUT_SECONDS,
    MILVUS_TOKEN,
    MILVUS_URI,
    VECTOR_STORE_PROVIDER,
    VECTOR_STORE_PATH,
)
from app.services.vectors.chroma_vector_store import ChromaVectorStore
from app.services.vectors.embedding_model import create_embedding_model_from_settings
from app.services.vectors.embedding_settings_service import (
    EmbeddingModelSettings,
    get_effective_embedding_model_settings,
)
from app.services.vectors.milvus_vector_store import MilvusVectorStore
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


def _embedding_identity_digest(
    user_id: int,
    settings: EmbeddingModelSettings,
) -> str:
    """返回 user/provider/model/dimensions 的稳定 SHA-1 前缀。"""
    identity = "|".join([
        str(user_id),
        settings.provider,
        settings.model,
        str(settings.dimensions or ""),
    ])
    return hashlib.sha1(identity.encode("utf-8")).hexdigest()[:12]


def build_milvus_user_collection_name(
    prefix: str,
    user_id: int,
    settings: EmbeddingModelSettings,
) -> str:
    """按 ADR 生成仅含小写字母、数字和下划线的 Milvus collection。"""
    normalized_prefix = re.sub(r"[^a-z0-9_]+", "_", prefix.strip().lower())
    normalized_prefix = normalized_prefix.strip("_") or "firstrag"
    digest = _embedding_identity_digest(user_id, settings)
    return f"{normalized_prefix[:24]}_u{user_id}_{digest}"[:63].strip("_")


def build_milvus_user_collection_prefix(prefix: str, user_id: int) -> str:
    """返回永久删除和重建用于扫描当前用户 identities 的安全前缀。"""
    normalized_prefix = re.sub(r"[^a-z0-9_]+", "_", prefix.strip().lower())
    normalized_prefix = normalized_prefix.strip("_") or "firstrag"
    return f"{normalized_prefix[:24]}_u{user_id}_"


def _create_milvus_client() -> object:
    """延迟创建认证 PyMilvus client，避免 Chroma 默认路径承担 import。"""
    from pymilvus import MilvusClient

    return MilvusClient(
        uri=MILVUS_URI,
        token=MILVUS_TOKEN,
        db_name=MILVUS_DATABASE,
        timeout=MILVUS_TIMEOUT_SECONDS,
    )


def get_vector_store(
    user_id: int | None = None,
    persist_directory: str | Path = VECTOR_STORE_PATH,
    collection_name: str = CHROMA_COLLECTION_NAME,
) -> VectorStoreBoundary:
    """按当前 provider 创建用户隔离的 vector store adapter。"""
    resolved_collection_name = collection_name
    embedding_function = None
    settings = None
    if user_id is not None:
        settings = get_effective_embedding_model_settings(user_id)
        embedding_function = create_embedding_model_from_settings(settings)

    if VECTOR_STORE_PROVIDER == "milvus":
        if user_id is None or settings is None:
            raise ValueError("Milvus vector store 需要 user_id 和 embedding settings")
        resolved_collection_name = build_milvus_user_collection_name(
            MILVUS_COLLECTION_PREFIX,
            user_id,
            settings,
        )
        return MilvusVectorStore(
            client=_create_milvus_client(),
            collection_name=resolved_collection_name,
            user_collection_prefix=build_milvus_user_collection_prefix(
                MILVUS_COLLECTION_PREFIX,
                user_id,
            ),
            embedding_model=embedding_function,
            dimensions=settings.dimensions,
            timeout_seconds=MILVUS_TIMEOUT_SECONDS,
            consistency_level=MILVUS_CONSISTENCY_LEVEL,
        )

    if user_id is not None and settings is not None:
        resolved_collection_name = build_user_vector_collection_name(
            collection_name,
            user_id,
            settings,
        )

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


def get_vector_store_for_cleanup(user_id: int) -> VectorStoreBoundary:
    """创建无需 embedding 凭据的文件生命周期 cleanup adapter。"""
    if VECTOR_STORE_PROVIDER == "milvus":
        return MilvusVectorStore(
            client=_create_milvus_client(),
            collection_name="",
            user_collection_prefix=build_milvus_user_collection_prefix(
                MILVUS_COLLECTION_PREFIX,
                user_id,
            ),
            embedding_model=None,
            dimensions=None,
            timeout_seconds=MILVUS_TIMEOUT_SECONDS,
            consistency_level=MILVUS_CONSISTENCY_LEVEL,
        )
    return get_vector_store()

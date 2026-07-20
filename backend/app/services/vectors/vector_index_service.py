import hashlib
import logging
from pathlib import Path
import re
from typing import Any
from uuid import UUID

from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.core.config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_HOST,
    CHROMA_PORT,
    CHROMA_SSL,
    VECTOR_STORE_PATH,
)
from app.db.locks import file_index_lock
from app.db.executor import Row
from app.repositories.knowledge_chunk_repository import (
    delete_file_chunks,
    replace_file_chunks,
)
from app.repositories.knowledge_file_repository import update_knowledge_file_status
from app.services.documents.document_service import (
    EmptyDocumentError,
    load_document,
    split_documents,
)
from app.services.knowledge_profile_cache import (
    invalidate_file_knowledge_base_contexts,
)
from app.services.vectors.embedding_model import create_embedding_model_from_settings
from app.services.vectors.embedding_settings_service import (
    EmbeddingModelSettings,
    get_effective_embedding_model_settings,
)


logger = logging.getLogger(__name__)


def _normalize_collection_name_part(value: str) -> str:
    """将 collection 名称片段规范化为 Chroma 可接受的安全字符。"""
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower())
    normalized = normalized.strip("-_")
    return normalized or "collection"


def build_user_vector_collection_name(
    base_collection_name: str,
    user_id: int,
    settings: EmbeddingModelSettings,
) -> str:
    """按用户和 embedding 配置生成隔离的 Chroma collection 名称。"""
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
) -> Chroma:
    """创建 Chroma 向量库连接；Compose 使用 HTTP，单进程本地可嵌入。"""
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
        return Chroma(
            **common_options,
            host=CHROMA_HOST,
            port=CHROMA_PORT,
            ssl=CHROMA_SSL,
        )

    return Chroma(
        **common_options,
        persist_directory=str(persist_directory),
    )


def build_chunk_ids(chunks: list[Document]) -> list[str]:
    """为分块生成稳定向量 ID，避免同一文件重复入库。"""
    chunk_ids = []
    for chunk in chunks:
        user_id = chunk.metadata["user_id"]
        file_id = chunk.metadata["file_id"]
        chunk_index = chunk.metadata["chunk_index"]
        index_version = chunk.metadata["index_version"]
        chunk_ids.append(f"{user_id}:{file_id}:v{index_version}:{chunk_index}")
    return chunk_ids


def build_file_vector_filter(user_id: int, file_id: UUID | str) -> dict:
    """构造删除单个文件所有 Chroma 向量的 metadata 条件。"""
    return {
        "$and": [
            {"user_id": str(user_id)},
            {"file_id": str(file_id)},
        ]
    }


def delete_file_vector_entries(
    user_id: int,
    file_id: UUID | str,
    vectordb: Chroma | None = None,
) -> None:
    """删除单个文件在 Chroma 中的全部索引版本。"""
    if vectordb is not None:
        resolved_vectordb = vectordb
    else:
        try:
            resolved_vectordb = get_vector_store(user_id=user_id)
        except ValueError:
            # 兼容迁移前的旧 collection 清理：删除操作不应要求用户先配置 Key。
            resolved_vectordb = get_vector_store()
    resolved_vectordb.delete(where=build_file_vector_filter(user_id, file_id))


def compensate_failed_file_index(
    user_id: int,
    file_id: UUID | str,
    vectordb: Chroma | None = None,
) -> None:
    """尽力清除一次失败索引留下的 Chroma 与全文检索分块。"""
    try:
        delete_file_vector_entries(user_id, file_id, vectordb)
    except Exception:
        logger.exception("补偿清理 Chroma 向量失败 file_id=%s", file_id)

    try:
        delete_file_chunks(user_id, file_id)
    except Exception:
        logger.exception("补偿清理全文分块失败 file_id=%s", file_id)


def index_file_vectors(
    user_id: int,
    file_id: UUID | str,
    storage_path: str | Path,
    index_version: int,
    original_name: str | None = None,
    persist_directory: str | Path = VECTOR_STORE_PATH,
    collection_name: str = CHROMA_COLLECTION_NAME,
) -> dict[str, Any]:
    """将单个知识文件解析、切分并写入 Chroma。"""
    file_path = Path(storage_path)
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在：{file_path}")

    documents = load_document(
        file_path=file_path,
        file_id=file_id,
        user_id=user_id,
        original_name=original_name or file_path.name,
    )
    chunks = split_documents(documents)
    if not chunks:
        raise EmptyDocumentError("文件为空，未解析出可入库的文本分块")

    for chunk in chunks:
        chunk.metadata["index_version"] = index_version

    normalized_file_id = str(file_id)
    vectordb: Chroma | None = None
    try:
        vectordb = get_vector_store(
            user_id=user_id,
            persist_directory=persist_directory,
            collection_name=collection_name,
        )
        delete_file_vector_entries(user_id, file_id, vectordb)
        chunk_ids = build_chunk_ids(chunks)
        vectordb.add_documents(
            documents=chunks,
            ids=chunk_ids,
        )
        replace_file_chunks(
            user_id=user_id,
            file_id=file_id,
            index_version=index_version,
            chunks=chunks,
            chunk_ids=chunk_ids,
        )
    except Exception:
        # 两套存储不能参与同一事务；失败时清空半成品并保持 failed 状态。
        compensate_failed_file_index(
            user_id,
            file_id,
            vectordb,
        )
        raise

    actual_collection_name = getattr(
        getattr(vectordb, "_collection", None),
        "name",
        collection_name,
    )
    return {
        "file_id": normalized_file_id,
        "chunk_count": len(chunks),
        "character_count": sum(
            len(chunk.page_content)
            for chunk in chunks
        ),
        "collection_name": actual_collection_name,
        "persist_directory": str(persist_directory),
    }


def index_knowledge_file_record(
    file_record: Row | dict[str, Any],
    user_id: int,
    index_version: int,
) -> dict[str, Any]:
    """索引单条知识文件记录，并同步文件处理状态。

    API 层只负责权限校验和 HTTP 错误转换；文件解析、切分、向量入库、
    全文 chunk 入库和文件状态流转统一放在这里。
    """
    file_id = file_record["id"]
    with file_index_lock(user_id, file_id):
        # 删除接口会先递增版本；旧任务取得锁后不会写入已失效的数据。
        if not update_knowledge_file_status(
            user_id,
            file_id,
            "indexing",
            expected_index_version=index_version,
        ):
            raise RuntimeError("索引任务版本已过期")
        invalidate_file_knowledge_base_contexts(user_id, file_id)

        try:
            index_result = index_file_vectors(
                user_id=user_id,
                file_id=file_id,
                storage_path=file_record["storage_path"],
                index_version=index_version,
                original_name=str(file_record["original_name"]),
            )
        except Exception:
            update_knowledge_file_status(
                user_id,
                file_id,
                "failed",
                expected_index_version=index_version,
            )
            invalidate_file_knowledge_base_contexts(user_id, file_id)
            raise

        if not update_knowledge_file_status(
            user_id,
            file_id,
            "indexed",
            expected_index_version=index_version,
        ):
            raise RuntimeError("索引任务版本已过期")
        invalidate_file_knowledge_base_contexts(user_id, file_id)
    return {
        "id": str(file_id),
        "original_name": file_record["original_name"],
        "status": "indexed",
        **index_result,
    }

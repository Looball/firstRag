from pathlib import Path
from typing import Any
from uuid import UUID

from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.core.config import CHROMA_COLLECTION_NAME, VECTOR_STORE_PATH
from app.db.locks import file_index_lock
from app.db.executor import Row
from app.repositories.knowledge_chunk_repository import replace_file_chunks
from app.repositories.knowledge_file_repository import update_knowledge_file_status
from app.services.documents.document_service import (
    load_document,
    split_documents,
)
from app.services.vectors.embedding_model import ZhipuAIEmbeddings


def get_vector_store(
    persist_directory: str | Path = VECTOR_STORE_PATH,
    collection_name: str = CHROMA_COLLECTION_NAME,
) -> Chroma:
    """创建或打开 Chroma 向量库。"""
    return Chroma(
        collection_name=collection_name,
        persist_directory=str(persist_directory),
        embedding_function=ZhipuAIEmbeddings(),
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


def index_file_vectors(
    user_id: int,
    file_id: UUID | str,
    storage_path: str | Path,
    index_version: int,
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
    )
    chunks = split_documents(documents)
    if not chunks:
        raise ValueError("文件未解析出可入库的文本分块")

    for chunk in chunks:
        chunk.metadata["index_version"] = index_version

    vectordb = get_vector_store(
        persist_directory=persist_directory,
        collection_name=collection_name,
    )

    normalized_user_id = str(user_id)
    normalized_file_id = str(file_id)
    vectordb.delete(
        where={
            "$and": [
                {"user_id": normalized_user_id},
                {"file_id": normalized_file_id},
            ]
        }
    )
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

    return {
        "file_id": normalized_file_id,
        "chunk_count": len(chunks),
        "character_count": sum(
            len(chunk.page_content)
            for chunk in chunks
        ),
        "collection_name": collection_name,
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

        try:
            index_result = index_file_vectors(
                user_id=user_id,
                file_id=file_id,
                storage_path=file_record["storage_path"],
                index_version=index_version,
            )
        except Exception:
            update_knowledge_file_status(
                user_id,
                file_id,
                "failed",
                expected_index_version=index_version,
            )
            raise

        if not update_knowledge_file_status(
            user_id,
            file_id,
            "indexed",
            expected_index_version=index_version,
        ):
            raise RuntimeError("索引任务版本已过期")
    return {
        "id": str(file_id),
        "original_name": file_record["original_name"],
        "status": "indexed",
        **index_result,
    }

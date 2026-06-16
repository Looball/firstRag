from collections.abc import Sequence
from uuid import UUID

from langchain_core.documents import Document

from app.repositories.knowledge_chunk_repository import search_chunks


def get_fulltext_documents(
    query: str,
    user_id: int,
    file_ids: Sequence[UUID | str] | None = None,
    k: int = 5,
) -> list[Document]:
    """使用 PostgreSQL 在指定用户和文件范围内做全文检索。"""
    rows = search_chunks(
        user_id=user_id,
        query=query,
        file_ids=file_ids,
        limit=k,
    )

    documents = []
    for row in rows:
        metadata = dict(row["metadata"] or {})
        metadata.update({
            "file_id": str(row["file_id"]),
            "chunk_index": row["chunk_index"],
            "fulltext_score": float(row["score"] or 0.0),
            "retrieval_source": "fulltext",
        })
        documents.append(
            Document(
                page_content=row["content"],
                metadata=metadata,
            )
        )

    return documents

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from langchain_core.documents import Document
from psycopg.types.json import Jsonb

from app.db.connection import get_connection
from app.db.executor import Row, fetch_all


def replace_file_chunks(
    user_id: int,
    file_id: UUID | str,
    index_version: int,
    chunks: list[Document],
    chunk_ids: list[str],
) -> int:
    """替换单个文件在 PostgreSQL 中的全文检索分块。"""
    if len(chunks) != len(chunk_ids):
        raise ValueError("chunks 和 chunk_ids 数量不一致")

    normalized_file_id = str(file_id)
    rows = [
        (
            chunk_id,
            user_id,
            normalized_file_id,
            index_version,
            chunk.metadata["chunk_index"],
            chunk.page_content,
            Jsonb(chunk.metadata),
        )
        for chunk_id, chunk in zip(chunk_ids, chunks, strict=True)
    ]

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM knowledge_file_chunks
                WHERE user_id = %s
                  AND knowledge_file_id = %s;
                """,
                (user_id, normalized_file_id),
            )

            if not rows:
                return 0

            cursor.executemany(
                """
                INSERT INTO knowledge_file_chunks (
                    chunk_id,
                    user_id,
                    knowledge_file_id,
                    index_version,
                    chunk_index,
                    content,
                    metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s);
                """,
                rows,
            )
            return cursor.rowcount


def delete_file_chunks(
    user_id: int,
    file_id: UUID | str,
) -> int:
    """删除单个文件在 PostgreSQL 中的全文检索分块。"""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM knowledge_file_chunks
                WHERE user_id = %s
                  AND knowledge_file_id = %s;
                """,
                (user_id, str(file_id)),
            )
            return cursor.rowcount


def search_chunks(
    user_id: int,
    query: str,
    file_ids: Sequence[UUID | str] | None = None,
    limit: int = 5,
) -> list[Row]:
    """在指定用户和文件范围内检索 PostgreSQL 文本分块。"""
    normalized_query = query.strip()
    if not normalized_query:
        return []

    query_terms = [
        term
        for term in normalized_query.split()
        if term
    ]
    if not query_terms:
        query_terms = [normalized_query]

    like_patterns = [f"%{term}%" for term in query_terms]
    phrase_pattern = f"%{normalized_query}%"

    file_filter = ""
    params: list[Any] = [
        normalized_query,
        phrase_pattern,
        user_id,
        like_patterns,
        normalized_query,
    ]

    if file_ids:
        file_filter = "AND knowledge_file_id = ANY(%s::uuid[])"
        params.append([str(file_id) for file_id in file_ids])

    params.append(limit)

    return fetch_all(
        f"""
        SELECT
            chunk_id,
            knowledge_file_id AS file_id,
            chunk_index,
            content,
            metadata,
            (
                ts_rank_cd(
                    to_tsvector('simple', content),
                    websearch_to_tsquery('simple', %s)
                )
                + CASE
                    WHEN content ILIKE %s THEN 1.0
                    ELSE 0.0
                  END
            ) AS score
        FROM knowledge_file_chunks
        WHERE user_id = %s
          AND (
              content ILIKE ANY(%s)
              OR to_tsvector('simple', content)
                 @@ websearch_to_tsquery('simple', %s)
          )
          {file_filter}
        ORDER BY score DESC, chunk_index ASC
        LIMIT %s;
        """,
        params,
    )

from collections.abc import Sequence
import re
from typing import Any
from uuid import UUID

from langchain_core.documents import Document
from psycopg.types.json import Jsonb

from app.db.connection import get_connection
from app.db.executor import Row, fetch_all


CHINESE_STOP_TERMS = {
    "什么",
    "什么是",
    "是什么",
    "怎么",
    "如何",
    "哪些",
    "请问",
    "一下",
    "这个",
    "那个",
}


def extract_chinese_search_terms(
    text: str,
    min_size: int = 2,
    max_size: int = 6,
    max_terms: int = 64,
) -> list[str]:
    """从中文查询中提取短语片段，用于 PostgreSQL ILIKE 兜底检索。

    PostgreSQL `simple` 词典不能像中文分词器一样理解“诉讼法的任务是什么”。
    因此在全文检索之外额外提取中文 ngram，让“诉讼法”“任务”这类
    关键词能命中文档分块。
    """
    terms: list[str] = []
    seen: set[str] = set()

    for match in re.finditer(r"[\u4e00-\u9fff]+", text):
        chars = match.group(0)
        max_window = min(max_size, len(chars))
        for size in range(max_window, min_size - 1, -1):
            for start in range(0, len(chars) - size + 1):
                term = chars[start:start + size]
                if term in CHINESE_STOP_TERMS or term in seen:
                    continue
                seen.add(term)
                terms.append(term)
                if len(terms) >= max_terms:
                    return terms

    return terms


def build_search_terms(query: str) -> list[str]:
    """构造 SQL 检索关键词，兼容空格分词和中文连续文本。"""
    normalized_query = query.strip()
    terms = [
        term
        for term in normalized_query.split()
        if term
    ]

    if normalized_query and normalized_query not in terms:
        terms.append(normalized_query)

    for term in extract_chinese_search_terms(normalized_query):
        if term not in terms:
            terms.append(term)

    return terms


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


def get_user_knowledge_file_chunk_context(
    user_id: int,
    file_id: UUID | str,
    chunk_index: int,
    radius: int = 1,
    index_version: int | None = None,
) -> list[Row]:
    """查询指定版本或最新可用版本的目标 chunk 及相邻上下文。"""
    return fetch_all(
        """
        WITH target_chunk AS (
            SELECT
                chunk.knowledge_file_id,
                chunk.index_version,
                chunk.chunk_index AS target_chunk_index,
                file.original_name
            FROM knowledge_file_chunks AS chunk
            JOIN knowledge_files AS file
              ON file.id = chunk.knowledge_file_id
             AND file.user_id = chunk.user_id
            WHERE chunk.user_id = %s
              AND chunk.knowledge_file_id = %s
              AND chunk.chunk_index = %s
              AND (%s IS NULL OR chunk.index_version = %s)
              AND file.deleted_at IS NULL
            ORDER BY chunk.index_version DESC
            LIMIT 1
        )
        SELECT
            target.original_name,
            target.index_version,
            target.target_chunk_index,
            context.chunk_index,
            context.content,
            context.metadata
        FROM target_chunk AS target
        JOIN knowledge_file_chunks AS context
          ON context.user_id = %s
         AND context.knowledge_file_id = target.knowledge_file_id
         AND context.index_version = target.index_version
        WHERE context.chunk_index BETWEEN
              target.target_chunk_index - %s
              AND target.target_chunk_index + %s
        ORDER BY context.chunk_index ASC;
        """,
        (
            user_id,
            str(file_id),
            chunk_index,
            index_version,
            index_version,
            user_id,
            radius,
            radius,
        ),
    )


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

    query_terms = build_search_terms(normalized_query)
    if not query_terms:
        return []

    like_patterns = [f"%{term}%" for term in query_terms]
    phrase_pattern = f"%{normalized_query}%"

    file_filter = ""
    params: list[Any] = [
        normalized_query,
        like_patterns,
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
                    WHEN content ILIKE ANY(%s) THEN 0.2
                    ELSE 0.0
                  END
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

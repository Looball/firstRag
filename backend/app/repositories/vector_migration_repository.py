"""Chroma 到 Milvus 迁移使用的只读 PostgreSQL 事实查询。"""

from uuid import UUID

from app.db.executor import Row, fetch_all, fetch_one


def list_vector_migration_chunk_rows(
    *,
    user_id: int | None = None,
    file_id: UUID | str | None = None,
) -> list[Row]:
    """列出未软删除文件的 chunk 与非敏感 embedding identity 字段。"""
    return fetch_all(
        """
        SELECT
            chunk.chunk_id,
            chunk.user_id,
            chunk.knowledge_file_id::text AS file_id,
            chunk.index_version,
            chunk.chunk_index,
            chunk.content,
            chunk.metadata,
            file.index_version AS file_index_version,
            file.status AS file_status,
            settings.provider AS embedding_provider,
            settings.model AS embedding_model,
            settings.dimensions AS embedding_dimensions,
            settings.timeout_seconds AS embedding_timeout_seconds,
            settings.max_retries AS embedding_max_retries
        FROM knowledge_file_chunks AS chunk
        JOIN knowledge_files AS file
          ON file.id = chunk.knowledge_file_id
         AND file.user_id = chunk.user_id
        LEFT JOIN user_embedding_settings AS settings
          ON settings.user_id = chunk.user_id
        WHERE file.deleted_at IS NULL
          AND (%s::bigint IS NULL OR chunk.user_id = %s)
          AND (%s::uuid IS NULL OR chunk.knowledge_file_id = %s)
        ORDER BY
            chunk.user_id ASC,
            chunk.knowledge_file_id ASC,
            chunk.chunk_index ASC,
            chunk.chunk_id ASC;
        """,
        (
            user_id,
            user_id,
            str(file_id) if file_id is not None else None,
            str(file_id) if file_id is not None else None,
        ),
    )


def count_active_vector_index_jobs() -> int:
    """统计尚未 drain 的 queued/processing jobs，供维护窗口门禁使用。"""
    row = fetch_one(
        """
        SELECT COUNT(*)::integer AS active_count
        FROM vector_index_jobs
        WHERE status IN ('queued', 'processing');
        """,
    )
    return int((row or {}).get("active_count") or 0)

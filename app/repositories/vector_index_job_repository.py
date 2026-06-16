from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from app.db.connection import get_connection
from app.db.executor import Row, fetch_one


def enqueue_vector_index_job(
    user_id: int,
    knowledge_file_id: UUID,
    knowledge_base_id: UUID | None = None,
    priority: int = 100,
) -> Row:
    """创建文件向量化任务；如果已有活跃任务，则返回已有任务。"""
    job_id = uuid4()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO vector_index_jobs (
                    id,
                    user_id,
                    knowledge_file_id,
                    knowledge_base_id,
                    priority
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING
                    id,
                    user_id,
                    knowledge_file_id,
                    knowledge_base_id,
                    status,
                    attempts,
                    max_attempts,
                    error_message,
                    result,
                    created_at,
                    updated_at;
                """,
                (
                    job_id,
                    user_id,
                    knowledge_file_id,
                    knowledge_base_id,
                    priority,
                ),
            )
            row = cursor.fetchone()
            if row is not None:
                result = dict(row)
                result["already_queued"] = False
                return result

            cursor.execute(
                """
                SELECT
                    id,
                    user_id,
                    knowledge_file_id,
                    knowledge_base_id,
                    status,
                    attempts,
                    max_attempts,
                    error_message,
                    result,
                    created_at,
                    updated_at
                FROM vector_index_jobs
                WHERE user_id = %s
                  AND knowledge_file_id = %s
                  AND status IN ('queued', 'processing')
                ORDER BY created_at ASC
                LIMIT 1;
                """,
                (user_id, knowledge_file_id),
            )
            active_job = cursor.fetchone()
            if active_job is None:
                raise RuntimeError("向量化任务创建失败")

            result = dict(active_job)
            result["already_queued"] = True
            return result


def get_user_vector_index_job(
    user_id: int,
    job_id: UUID,
) -> Row | None:
    """查询当前用户的单个向量化任务。"""
    return fetch_one(
        """
        SELECT
            id,
            user_id,
            knowledge_file_id,
            knowledge_base_id,
            status,
            attempts,
            max_attempts,
            error_message,
            result,
            created_at,
            updated_at,
            started_at,
            finished_at
        FROM vector_index_jobs
        WHERE id = %s
          AND user_id = %s;
        """,
        (job_id, user_id),
    )


def claim_next_vector_index_job(worker_id: str) -> Row | None:
    """原子领取一个待处理任务，支持多 worker 并发消费。"""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                WITH next_job AS (
                    SELECT id
                    FROM vector_index_jobs
                    WHERE status = 'queued'
                    ORDER BY priority ASC, created_at ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE vector_index_jobs AS job
                SET status = 'processing',
                    attempts = attempts + 1,
                    locked_by = %s,
                    locked_at = now(),
                    started_at = COALESCE(started_at, now()),
                    updated_at = now()
                FROM next_job
                WHERE job.id = next_job.id
                RETURNING
                    job.id,
                    job.user_id,
                    job.knowledge_file_id,
                    job.knowledge_base_id,
                    job.status,
                    job.attempts,
                    job.max_attempts,
                    job.error_message,
                    job.result,
                    job.created_at,
                    job.updated_at;
                """,
                (worker_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row is not None else None


def mark_vector_index_job_succeeded(
    job_id: UUID,
    result: dict[str, Any],
) -> Row | None:
    """标记任务成功并保存索引结果。"""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE vector_index_jobs
                SET status = 'succeeded',
                    result = %s,
                    error_message = NULL,
                    locked_by = NULL,
                    locked_at = NULL,
                    finished_at = now(),
                    updated_at = now()
                WHERE id = %s
                RETURNING id, status, result, updated_at, finished_at;
                """,
                (Jsonb(result), job_id),
            )
            row = cursor.fetchone()
            return dict(row) if row is not None else None


def mark_vector_index_job_failed(
    job_id: UUID,
    error_message: str,
) -> Row | None:
    """标记任务失败；未达到最大次数时重新入队等待重试。"""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE vector_index_jobs
                SET status = CASE
                        WHEN attempts < max_attempts THEN 'queued'
                        ELSE 'failed'
                    END,
                    error_message = %s,
                    locked_by = NULL,
                    locked_at = NULL,
                    finished_at = CASE
                        WHEN attempts >= max_attempts THEN now()
                        ELSE finished_at
                    END,
                    updated_at = now()
                WHERE id = %s
                RETURNING
                    id,
                    status,
                    attempts,
                    max_attempts,
                    error_message,
                    updated_at,
                    finished_at;
                """,
                (error_message[:2000], job_id),
            )
            row = cursor.fetchone()
            return dict(row) if row is not None else None

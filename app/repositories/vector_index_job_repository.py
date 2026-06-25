from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from app.db.connection import get_connection
from app.db.executor import Row, fetch_all, fetch_one


DEFAULT_JOB_LEASE_SECONDS = 15 * 60


def enqueue_vector_index_job(
    user_id: int,
    knowledge_file_id: UUID,
    knowledge_base_id: UUID | None = None,
    index_version: int = 0,
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
                    index_version,
                    priority
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING
                    id,
                    user_id,
                    knowledge_file_id,
                    knowledge_base_id,
                    index_version,
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
                    index_version,
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
                    index_version,
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
            index_version,
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


def get_latest_vector_index_jobs_by_file_ids(
    user_id: int,
    file_ids: list[str],
) -> dict[str, Row]:
    """批量查询每个文件最近一次向量化任务。"""
    if not file_ids:
        return {}

    rows = fetch_all(
        """
        SELECT DISTINCT ON (knowledge_file_id)
            id,
            user_id,
            knowledge_file_id,
            knowledge_base_id,
            index_version,
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
        WHERE user_id = %s
          AND knowledge_file_id = ANY(%s::uuid[])
        ORDER BY knowledge_file_id, created_at DESC, id DESC;
        """,
        (user_id, file_ids),
    )
    return {
        str(row["knowledge_file_id"]): row
        for row in rows
    }


def get_user_vector_index_job_health(
    user_id: int,
    stale_after_seconds: int = DEFAULT_JOB_LEASE_SECONDS,
) -> Row:
    """统计当前用户向量化任务队列健康状态。"""
    return fetch_one(
        """
        SELECT
            now() AS checked_at,
            COUNT(*)::integer AS total,
            COUNT(*) FILTER (WHERE status = 'queued')::integer AS queued,
            COUNT(*) FILTER (WHERE status = 'processing')::integer AS processing,
            COUNT(*) FILTER (WHERE status = 'succeeded')::integer AS succeeded,
            COUNT(*) FILTER (WHERE status = 'failed')::integer AS failed,
            COUNT(*) FILTER (WHERE status = 'cancelled')::integer AS cancelled,
            COUNT(*) FILTER (
                WHERE status = 'queued'
                  AND available_at <= now()
                  AND created_at < now() - make_interval(secs => %s)
            )::integer AS stale_queued,
            COUNT(*) FILTER (
                WHERE status = 'processing'
                  AND COALESCE(heartbeat_at, locked_at, started_at, updated_at)
                      < now() - make_interval(secs => %s)
            )::integer AS stale_processing,
            MAX(updated_at) AS last_job_updated_at,
            MAX(heartbeat_at) FILTER (
                WHERE status = 'processing'
            ) AS last_processing_heartbeat_at,
            MIN(created_at) FILTER (
                WHERE status IN ('queued', 'processing')
            ) AS oldest_active_created_at
        FROM vector_index_jobs
        WHERE user_id = %s;
        """,
        (stale_after_seconds, stale_after_seconds, user_id),
    ) or {}


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
                      AND available_at <= now()
                    ORDER BY priority ASC, created_at ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE vector_index_jobs AS job
                SET status = 'processing',
                    attempts = attempts + 1,
                    locked_by = %s,
                    locked_at = now(),
                    heartbeat_at = now(),
                    started_at = COALESCE(started_at, now()),
                    updated_at = now()
                FROM next_job
                WHERE job.id = next_job.id
                RETURNING
                    job.id,
                    job.user_id,
                    job.knowledge_file_id,
                    job.knowledge_base_id,
                    job.index_version,
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


def reclaim_expired_vector_index_jobs(
    lease_seconds: int = DEFAULT_JOB_LEASE_SECONDS,
) -> int:
    """回收超过租约时间仍未完成的任务。

    worker 异常退出时不会执行失败回调。该函数将过期 processing 任务
    重新排队；已耗尽重试次数的任务则标记为 failed，避免永久卡住文件。
    """
    if lease_seconds <= 0:
        raise ValueError("lease_seconds 必须大于 0")

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE vector_index_jobs
                SET status = CASE
                        WHEN attempts >= max_attempts THEN 'failed'
                        ELSE 'queued'
                    END,
                    error_message = CASE
                        WHEN attempts >= max_attempts THEN
                            '任务执行超时，已达到最大重试次数'
                        ELSE error_message
                    END,
                    locked_by = NULL,
                    locked_at = NULL,
                    heartbeat_at = NULL,
                    available_at = CASE
                        WHEN attempts >= max_attempts THEN available_at
                        ELSE now()
                    END,
                    finished_at = CASE
                        WHEN attempts >= max_attempts THEN now()
                        ELSE finished_at
                    END,
                    updated_at = now()
                WHERE status = 'processing'
                  AND COALESCE(heartbeat_at, locked_at, started_at)
                      < now() - make_interval(secs => %s)
                """,
                (lease_seconds,),
            )
            return cursor.rowcount


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
                    heartbeat_at = NULL,
                    finished_at = now(),
                    updated_at = now()
                WHERE id = %s
                  AND status = 'processing'
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
                    heartbeat_at = NULL,
                    available_at = CASE
                        WHEN attempts < max_attempts THEN
                            now() + make_interval(
                                secs => LEAST(
                                    300,
                                    (5 * power(2, attempts))::integer
                                )
                            )
                        ELSE available_at
                    END,
                    finished_at = CASE
                        WHEN attempts >= max_attempts THEN now()
                        ELSE finished_at
                    END,
                    updated_at = now()
                WHERE id = %s
                  AND status = 'processing'
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


def cancel_active_vector_index_jobs(
    user_id: int,
    knowledge_file_id: UUID,
    reason: str,
) -> int:
    """取消同一文件尚未完成的旧版本索引任务。"""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE vector_index_jobs
                SET status = 'cancelled',
                    error_message = %s,
                    locked_by = NULL,
                    locked_at = NULL,
                    heartbeat_at = NULL,
                    finished_at = now(),
                    updated_at = now()
                WHERE user_id = %s
                  AND knowledge_file_id = %s
                  AND status IN ('queued', 'processing')
                """,
                (reason[:2000], user_id, knowledge_file_id),
            )
            return cursor.rowcount


def mark_vector_index_job_cancelled(
    job_id: UUID,
    reason: str,
) -> Row | None:
    """将已领取但过期的索引任务标记为 cancelled。"""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE vector_index_jobs
                SET status = 'cancelled',
                    error_message = %s,
                    locked_by = NULL,
                    locked_at = NULL,
                    heartbeat_at = NULL,
                    finished_at = now(),
                    updated_at = now()
                WHERE id = %s
                  AND status = 'processing'
                RETURNING id, status, error_message, updated_at, finished_at;
                """,
                (reason[:2000], job_id),
            )
            row = cursor.fetchone()
            return dict(row) if row is not None else None

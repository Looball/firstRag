import argparse
import logging
import socket
import time
from time import perf_counter
from uuid import UUID

from app.core.observability import log_exception_event, log_structured_event
from app.repositories.knowledge_file_repository import get_user_knowledge_file
from app.repositories.vector_index_job_repository import (
    claim_next_vector_index_job,
    mark_vector_index_job_cancelled,
    mark_vector_index_job_failed,
    mark_vector_index_job_succeeded,
    reclaim_expired_vector_index_jobs,
)
from app.services.vectors.vector_index_service import index_knowledge_file_record


logger = logging.getLogger(__name__)


def process_next_vector_index_job(worker_id: str) -> bool:
    """领取并处理一个向量化任务；没有任务时返回 False。"""
    reclaimed_count = reclaim_expired_vector_index_jobs()
    if reclaimed_count:
        log_structured_event(
            logger,
            logging.INFO,
            "vector_index_jobs_reclaimed",
            worker_id=worker_id,
            reclaimed_count=reclaimed_count,
            message="回收过期向量化任务",
        )

    job = claim_next_vector_index_job(worker_id)
    if job is None:
        return False

    job_id = job["id"]
    user_id = job["user_id"]
    file_id = job["knowledge_file_id"]
    index_version = job.get("index_version", 0)
    job_started_at = perf_counter()
    log_context = {
        "worker_id": worker_id,
        "job_id": str(job_id),
        "user_id": user_id,
        "file_id": str(file_id),
        "index_version": index_version,
    }

    log_structured_event(
        logger,
        logging.INFO,
        "vector_index_job_claimed",
        **log_context,
        message="领取向量化任务",
    )

    try:
        file_record = get_user_knowledge_file(user_id, file_id)
        if file_record is None:
            raise FileNotFoundError(f"文件不存在：{file_id}")

        if file_record.get("index_version", 0) != index_version:
            mark_vector_index_job_cancelled(
                UUID(str(job_id)),
                "文件索引版本已更新，旧任务已取消",
            )
            log_structured_event(
                logger,
                logging.INFO,
                "vector_index_job_cancelled",
                **log_context,
                status="cancelled",
                duration_ms=round((perf_counter() - job_started_at) * 1000, 2),
                message="取消过期向量化任务",
            )
            return True

        if file_record["status"] == "indexed":
            result = {
                "file_id": str(file_id),
                "status": "indexed",
                "skipped": True,
                "message": "文件已完成向量化，跳过重复任务",
            }
            mark_vector_index_job_succeeded(UUID(str(job_id)), result)
            log_structured_event(
                logger,
                logging.INFO,
                "vector_index_job_skipped",
                **log_context,
                status="succeeded",
                skipped=True,
                duration_ms=round((perf_counter() - job_started_at) * 1000, 2),
                message="跳过已完成向量化的文件",
            )
            return True

        result = index_knowledge_file_record(
            file_record,
            user_id,
            index_version,
        )
        mark_vector_index_job_succeeded(UUID(str(job_id)), result)
        log_structured_event(
            logger,
            logging.INFO,
            "vector_index_job_succeeded",
            **log_context,
            status="succeeded",
            duration_ms=round((perf_counter() - job_started_at) * 1000, 2),
            chunk_count=result.get("chunk_count"),
            character_count=result.get("character_count"),
            message="完成文件向量化",
        )
    except Exception as exc:
        mark_vector_index_job_failed(UUID(str(job_id)), str(exc))
        log_exception_event(
            logger,
            "vector_index_job_failed",
            exc,
            default_source="worker",
            **log_context,
            status="failed",
            duration_ms=round((perf_counter() - job_started_at) * 1000, 2),
            message="向量化任务失败",
        )

    return True


def run_vector_index_worker(
    worker_id: str | None = None,
    poll_interval: float = 2.0,
    once: bool = False,
) -> None:
    """持续消费 PostgreSQL 中的向量化任务队列。"""
    resolved_worker_id = worker_id or f"{socket.gethostname()}:{time.time_ns()}"

    while True:
        processed = process_next_vector_index_job(resolved_worker_id)
        if once:
            return
        if not processed:
            time.sleep(poll_interval)


def main() -> None:
    """命令行入口：python -m app.workers.vector_index_worker。"""
    parser = argparse.ArgumentParser(description="向量化任务队列 worker")
    parser.add_argument("--worker-id", default=None)
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    run_vector_index_worker(
        worker_id=args.worker_id,
        poll_interval=args.poll_interval,
        once=args.once,
    )


if __name__ == "__main__":
    main()

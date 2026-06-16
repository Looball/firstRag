import argparse
import socket
import time
from uuid import UUID

from app.repositories.knowledge_file_repository import get_user_knowledge_file
from app.repositories.vector_index_job_repository import (
    claim_next_vector_index_job,
    mark_vector_index_job_failed,
    mark_vector_index_job_succeeded,
)
from app.services.vectors.vector_index_service import index_knowledge_file_record


def process_next_vector_index_job(worker_id: str) -> bool:
    """领取并处理一个向量化任务；没有任务时返回 False。"""
    job = claim_next_vector_index_job(worker_id)
    if job is None:
        return False

    job_id = job["id"]
    user_id = job["user_id"]
    file_id = job["knowledge_file_id"]

    try:
        file_record = get_user_knowledge_file(user_id, file_id)
        if file_record is None:
            raise FileNotFoundError(f"文件不存在：{file_id}")

        result = index_knowledge_file_record(file_record, user_id)
        mark_vector_index_job_succeeded(UUID(str(job_id)), result)
        print(f"[{worker_id}] indexed file={file_id} job={job_id}")
    except Exception as exc:
        mark_vector_index_job_failed(UUID(str(job_id)), str(exc))
        print(f"[{worker_id}] failed file={file_id} job={job_id}: {exc}")

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

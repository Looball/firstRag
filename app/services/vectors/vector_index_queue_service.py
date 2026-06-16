from typing import Any
from uuid import UUID

from app.db.executor import Row
from app.repositories.knowledge_file_repository import update_knowledge_file_status
from app.repositories.vector_index_job_repository import enqueue_vector_index_job


def serialize_vector_index_job(job: Row | dict[str, Any]) -> dict[str, Any]:
    """将向量化任务记录转换为接口响应结构。"""
    return {
        "id": str(job["id"]),
        "user_id": job["user_id"],
        "knowledge_file_id": str(job["knowledge_file_id"]),
        "knowledge_base_id": (
            str(job["knowledge_base_id"])
            if job.get("knowledge_base_id") is not None
            else None
        ),
        "status": job["status"],
        "attempts": job["attempts"],
        "max_attempts": job["max_attempts"],
        "already_queued": job.get("already_queued", False),
        "error_message": job.get("error_message"),
        "result": job.get("result"),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
    }


def enqueue_file_vector_index(
    file_record: Row | dict[str, Any],
    user_id: int,
    knowledge_base_id: UUID | None = None,
) -> dict[str, Any]:
    """为单个文件创建向量化任务，并把文件状态更新为 queued。"""
    job = enqueue_vector_index_job(
        user_id=user_id,
        knowledge_file_id=file_record["id"],
        knowledge_base_id=knowledge_base_id,
    )
    if job["status"] == "queued":
        update_knowledge_file_status(user_id, file_record["id"], "queued")

    return serialize_vector_index_job(job)

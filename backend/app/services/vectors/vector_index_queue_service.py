from typing import Any
from uuid import UUID

from app.db.executor import Row
from app.repositories.knowledge_file_repository import update_knowledge_file_status
from app.repositories.vector_index_job_repository import enqueue_vector_index_job


def build_job_worker_hint(job: Row | dict[str, Any]) -> str | None:
    """根据单个任务状态生成给前端展示的 worker 提示。"""
    if not job.get("is_stale"):
        return None

    status = job.get("status")
    if status == "queued":
        return "该文件向量化任务长时间排队，可能 worker 未启动。"
    if status == "processing":
        return "该文件向量化任务长时间处理中且没有心跳，可能 worker 已停止或任务卡住。"
    return None


def serialize_vector_index_job(job: Row | dict[str, Any]) -> dict[str, Any]:
    """将向量化任务记录转换为接口响应结构。"""
    if not job:
        return {}

    return {
        "id": str(job["id"]) if job.get("id") is not None else None,
        "user_id": job["user_id"],
        "knowledge_file_id": str(job["knowledge_file_id"]),
        "knowledge_base_id": (
            str(job["knowledge_base_id"])
            if job.get("knowledge_base_id") is not None
            else None
        ),
        "index_version": job.get("index_version", 0),
        "status": job["status"],
        "attempts": job["attempts"],
        "max_attempts": job["max_attempts"],
        "already_queued": job.get("already_queued", False),
        "already_indexed": job.get("already_indexed", False),
        "skipped": job.get("skipped", False),
        "message": job.get("message"),
        "error_message": job.get("error_message"),
        "result": job.get("result"),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "active_seconds": job.get("active_seconds"),
        "is_stale": bool(job.get("is_stale", False)),
        "worker_hint": build_job_worker_hint(job),
    }


def serialize_latest_vector_index_job(
    job: Row | dict[str, Any] | None,
) -> dict[str, Any] | None:
    """序列化文件列表中的最近一次向量化任务。"""
    if job is None:
        return None

    serialized_job = serialize_vector_index_job(job)
    # vector_index_jobs 内部完成态是 succeeded；文件列表接口对外统一成前端协议的 completed。
    if serialized_job["status"] == "succeeded":
        serialized_job["status"] = "completed"

    return serialized_job


def serialize_current_vector_index_job(
    file_record: Row | dict[str, Any],
    job: Row | dict[str, Any] | None,
) -> dict[str, Any] | None:
    """序列化文件当前索引版本对应的最近任务。"""
    if job is None:
        return None

    # 删除向量会递增文件 index_version；旧版本成功任务不应继续驱动前端状态。
    if job.get("index_version") != file_record.get("index_version"):
        return None

    return serialize_latest_vector_index_job(job)


def serialize_vector_index_job_health(
    health: Row | dict[str, Any],
) -> dict[str, Any]:
    """将向量化队列健康统计转换为接口响应结构。"""
    queued = int(health.get("queued") or 0)
    processing = int(health.get("processing") or 0)
    succeeded = int(health.get("succeeded") or 0)
    failed = int(health.get("failed") or 0)
    cancelled = int(health.get("cancelled") or 0)
    stale_queued = int(health.get("stale_queued") or 0)
    stale_processing = int(health.get("stale_processing") or 0)
    active = queued + processing

    # 没有独立 worker 心跳表时，用任务是否长期停留在活跃态来判断是否需要关注。
    if stale_queued > 0 or stale_processing > 0:
        worker_status = "attention_needed"
        queue_status = "stuck"
    elif processing > 0:
        worker_status = "active"
        queue_status = "processing"
    elif queued > 0:
        worker_status = "waiting"
        queue_status = "waiting"
    else:
        worker_status = "idle"
        queue_status = "idle"

    worker_hint = None
    if stale_processing > 0 and stale_queued > 0:
        worker_hint = "向量化任务长时间未推进，可能 worker 未启动或已卡住。"
    elif stale_processing > 0:
        worker_hint = "存在处理中的向量化任务长时间没有心跳，可能 worker 已停止或任务卡住。"
    elif stale_queued > 0:
        worker_hint = "存在排队任务长时间未被领取，可能 worker 未启动。"
    elif processing > 0:
        worker_hint = "worker 正在处理向量化任务。"
    elif queued > 0:
        worker_hint = "任务正在排队，等待 worker 领取。"

    return {
        "worker": {
            "status": worker_status,
            "is_healthy": worker_status != "attention_needed",
            "has_recent_activity": processing > 0 and stale_processing == 0,
            "hint": worker_hint,
            "last_job_updated_at": health.get("last_job_updated_at"),
            "last_processing_heartbeat_at": health.get(
                "last_processing_heartbeat_at",
            ),
            "oldest_active_created_at": health.get("oldest_active_created_at"),
            "oldest_queued_created_at": health.get("oldest_queued_created_at"),
            "oldest_processing_heartbeat_at": health.get(
                "oldest_processing_heartbeat_at",
            ),
            "oldest_active_seconds": health.get("oldest_active_seconds"),
            "oldest_queued_seconds": health.get("oldest_queued_seconds"),
            "oldest_processing_seconds": health.get(
                "oldest_processing_seconds",
            ),
            "stale_queued": stale_queued,
            "stale_processing": stale_processing,
            "checked_at": health.get("checked_at"),
        },
        "queue": {
            "status": queue_status,
            "total": int(health.get("total") or 0),
            "active": active,
            "queued": queued,
            "processing": processing,
            "succeeded": succeeded,
            "failed": failed,
            "cancelled": cancelled,
        },
    }


def enqueue_file_vector_index(
    file_record: Row | dict[str, Any],
    user_id: int,
    knowledge_base_id: UUID | None = None,
) -> dict[str, Any]:
    """为单个文件创建向量化任务，并把文件状态更新为 queued。

    同一用户的同一文件成功向量化一次后，后续提交会直接跳过。
    已经处于 queued/processing 的文件会复用现有活跃任务。
    """
    if file_record["status"] == "indexed":
        return serialize_vector_index_job({
            "id": None,
            "user_id": user_id,
            "knowledge_file_id": file_record["id"],
            "knowledge_base_id": knowledge_base_id,
            "status": "indexed",
            "attempts": 0,
            "max_attempts": 0,
            "already_queued": False,
            "already_indexed": True,
            "skipped": True,
            "message": "文件已完成向量化，跳过重复任务",
            "error_message": None,
            "result": None,
            "created_at": None,
            "updated_at": file_record.get("updated_at"),
        })

    job = enqueue_vector_index_job(
        user_id=user_id,
        knowledge_file_id=file_record["id"],
        knowledge_base_id=knowledge_base_id,
        index_version=file_record.get("index_version", 0),
    )
    if job["status"] == "queued":
        update_knowledge_file_status(
            user_id,
            file_record["id"],
            "queued",
            expected_index_version=file_record.get("index_version", 0),
        )

    return serialize_vector_index_job(job)

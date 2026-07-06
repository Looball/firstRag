from typing import Any
from uuid import UUID

from app.db.executor import Row
from app.repositories.knowledge_file_repository import update_knowledge_file_status
from app.repositories.vector_index_job_repository import enqueue_vector_index_job
from app.services.knowledge_profile_cache import (
    invalidate_file_knowledge_base_contexts,
)


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


def classify_vector_index_failure(error_message: str | None) -> str | None:
    """根据错误信息粗略归类向量化失败原因。"""
    if not error_message:
        return None

    normalized = error_message.lower()
    if any(
        keyword in normalized
        for keyword in [
            "unsupported",
            "不支持的文件类型",
            "不支持",
        ]
    ):
        return "unsupported_file_type"
    if any(
        keyword in normalized
        for keyword in [
            "empty document",
            "文件为空",
            "空文档",
        ]
    ):
        return "empty_document"
    if any(
        keyword in normalized
        for keyword in [
            "图片解析",
            "vision",
            "视觉能力",
            "qwen-vl",
            "glm-4v",
        ]
    ):
        return "image_parse_error"
    if any(
        keyword in normalized
        for keyword in [
            "timeout",
            "timed out",
            "deadline",
            "lease expired",
            "任务超时",
            "超时",
        ]
    ):
        return "task_timeout"
    if any(
        keyword in normalized
        for keyword in [
            "parse",
            "loader",
            "pdf",
            "docx",
            "decode",
            "encoding",
            "未解析",
            "解析",
            "文本分块",
            "分块",
        ]
    ):
        return "parse_error"
    if any(
        keyword in normalized
        for keyword in [
            "knowledge_file_chunks",
            "chunk repository",
            "chunk insert",
            "chunk write",
            "chunk 写入",
            "分块写入",
            "全文分块写入",
        ]
    ):
        return "chunk_write_error"
    if any(
        keyword in normalized
        for keyword in [
            "database",
            "postgres",
            "psycopg",
            "sql",
            "deadlock",
            "数据库",
        ]
    ):
        return "database_error"
    if any(
        keyword in normalized
        for keyword in [
            "embedding",
            "embed",
            "zhipu",
            "qwen",
            "dashscope",
            "api key",
            "apikey",
            "401",
            "403",
            "429",
            "timeout",
            "timed out",
            "connection",
            "network",
            "向量模型",
            "嵌入",
        ]
    ):
        return "embedding_error"
    if any(
        keyword in normalized
        for keyword in [
            "chroma",
            "chromadb",
            "vector store",
            "vector database",
            "collection",
            "向量库",
        ]
    ):
        return "vector_store_error"
    if "版本已过期" in error_message:
        return "stale_job"
    return "unknown_error"


def build_vector_index_failure_hint(failure_type: str | None) -> str | None:
    """根据失败类型生成可恢复建议。"""
    if failure_type == "unsupported_file_type":
        return "文件类型暂不支持。请上传 PDF、DOCX、Markdown、TXT、PNG、JPEG 或 WebP 文件后重新向量化。"
    if failure_type == "empty_document":
        return "文件没有解析出可入库文本。请确认文件不是空文件，必要时转为可复制文本后重新上传。"
    if failure_type == "image_parse_error":
        return "图片解析失败。请在设置页配置支持 vision 的聊天模型，例如 Qwen-VL 或 GLM-4V，然后重新向量化。"
    if failure_type == "parse_error":
        return "文件解析失败。请确认文件内容可读取，必要时转为 PDF、Markdown、TXT 或支持的图片格式后重新上传。"
    if failure_type == "embedding_error":
        return "Embedding 调用失败。请检查向量模型 API Key、网络连通性或稍后重新向量化。"
    if failure_type == "vector_store_error":
        return "向量库写入失败。请确认 Chroma/vector_db 可用，可删除向量后重新向量化。"
    if failure_type == "chunk_write_error":
        return "全文分块写入失败。请检查 PostgreSQL chunk 表和迁移状态，然后重新向量化。"
    if failure_type == "database_error":
        return "数据库写入失败。请检查数据库连接和迁移状态，然后重新向量化。"
    if failure_type == "task_timeout":
        return "向量化任务超时。请检查 worker 日志和文件大小，必要时重启 worker 后重新向量化。"
    if failure_type == "stale_job":
        return "该任务版本已过期，通常是文件向量被重置或重新提交导致，可直接重新向量化。"
    if failure_type == "unknown_error":
        return "向量化失败。请查看错误信息，确认 worker、模型配置和文件内容后重新向量化。"
    return None


def build_safe_vector_index_error_message(
    error_message: str | None,
    failure_type: str | None,
) -> str | None:
    """生成可展示给用户的错误摘要，避免泄露内部路径或凭据。"""
    if not error_message:
        return None

    if failure_type == "unsupported_file_type":
        return "文件类型暂不支持"
    if failure_type == "empty_document":
        return "文件没有可入库文本"
    if failure_type == "image_parse_error":
        return "图片解析失败"
    if failure_type == "parse_error":
        return "文件解析失败"
    if failure_type == "embedding_error":
        return "Embedding 调用失败"
    if failure_type == "vector_store_error":
        return "向量库写入失败"
    if failure_type == "chunk_write_error":
        return "全文分块写入失败"
    if failure_type == "database_error":
        return "数据库写入失败"
    if failure_type == "task_timeout":
        return "向量化任务超时"
    if failure_type == "stale_job":
        return "任务版本已过期"

    return "向量化失败"


def serialize_vector_index_job(job: Row | dict[str, Any]) -> dict[str, Any]:
    """将向量化任务记录转换为接口响应结构。"""
    if not job:
        return {}

    failure_type = classify_vector_index_failure(job.get("error_message"))
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
        "error_message": build_safe_vector_index_error_message(
            job.get("error_message"),
            failure_type,
        ),
        "failure_type": failure_type,
        "failure_hint": build_vector_index_failure_hint(failure_type),
        "can_retry": job.get("status") == "failed",
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
    worker_runtime: dict[str, Any] | None = None,
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
    runtime = worker_runtime or {}
    redis_available = runtime.get("redis_available")
    online_worker_count = int(runtime.get("online_worker_count") or 0)
    has_runtime = redis_available is True

    # Redis worker runtime 可用时优先用在线 worker 判断；不可用时继续按
    # PostgreSQL 队列中的活跃任务时长推断。
    if stale_queued > 0 or stale_processing > 0:
        worker_status = "attention_needed"
        queue_status = "stuck"
    elif has_runtime and active > 0 and online_worker_count == 0:
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
    elif has_runtime and active > 0 and online_worker_count == 0:
        worker_hint = "没有检测到在线 vector worker，排队或处理中任务可能无法推进。"
    elif processing > 0:
        worker_hint = "worker 正在处理向量化任务。"
    elif queued > 0:
        worker_hint = "任务正在排队，等待 worker 领取。"
    elif redis_available is False:
        worker_hint = "Redis worker 运行态暂不可用，已退回 PostgreSQL 队列状态判断。"

    has_recent_activity = (
        processing > 0
        and stale_processing == 0
        and (
            not has_runtime
            or online_worker_count > 0
            or runtime.get("last_heartbeat_at") is not None
        )
    )

    return {
        "worker": {
            "status": worker_status,
            "is_healthy": worker_status != "attention_needed",
            "has_recent_activity": has_recent_activity,
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
            "online_count": online_worker_count,
            "redis_enabled": runtime.get("redis_enabled"),
            "redis_available": redis_available,
            "redis_status": runtime.get("redis_status"),
            "redis_error_message": runtime.get("redis_error_message"),
            "last_heartbeat_at": runtime.get("last_heartbeat_at"),
            "last_heartbeat_age_seconds": runtime.get(
                "last_heartbeat_age_seconds",
            ),
            "heartbeat_ttl_seconds": runtime.get("heartbeat_ttl_seconds"),
            "active_file_lock_count": runtime.get("active_file_lock_count"),
            "runtime_workers": runtime.get("workers") or [],
            "runtime_metrics": runtime.get("metrics") or {},
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
        invalidate_file_knowledge_base_contexts(user_id, file_record["id"])

    return serialize_vector_index_job(job)

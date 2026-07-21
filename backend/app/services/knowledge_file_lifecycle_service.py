"""知识文件永久删除与跨存储清理。"""

import logging
from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.config import UPLOAD_ROOT
from app.db.locks import file_index_lock
from app.repositories.knowledge_base_repository import (
    get_knowledge_base_ids_for_file,
)
from app.repositories.knowledge_file_repository import (
    get_user_knowledge_file,
    purge_user_knowledge_file_records,
)
from app.repositories.vector_index_job_repository import (
    cancel_active_vector_index_jobs,
)
from app.services.knowledge_profile_cache import (
    invalidate_knowledge_base_context,
)
from app.services.vectors.vector_index_service import (
    delete_file_vector_entries,
)


logger = logging.getLogger(__name__)


def resolve_knowledge_file_storage_path(storage_path: str) -> Path:
    """解析并限制待删除文件必须位于 uploads 根目录内。"""
    upload_root = UPLOAD_ROOT.resolve()
    resolved_path = Path(storage_path).resolve()
    if not resolved_path.is_relative_to(upload_root):
        raise ValueError("知识文件存储路径不在允许的上传目录内")
    return resolved_path


def permanently_delete_knowledge_file(
    user_id: int,
    knowledge_file_id: UUID,
) -> dict[str, Any] | None:
    """永久删除用户文件，并串行清理向量、数据库与磁盘数据。"""
    file_record = get_user_knowledge_file(user_id, knowledge_file_id)
    if file_record is None:
        return None

    storage_path = resolve_knowledge_file_storage_path(
        str(file_record["storage_path"]),
    )
    knowledge_base_ids = get_knowledge_base_ids_for_file(
        user_id,
        knowledge_file_id,
    )

    with file_index_lock(user_id, knowledge_file_id):
        cancel_active_vector_index_jobs(
            user_id,
            knowledge_file_id,
            "用户永久删除了该知识文件",
        )
        delete_file_vector_entries(user_id, knowledge_file_id)
        deletion_counts = purge_user_knowledge_file_records(
            user_id,
            knowledge_file_id,
        )
        if deletion_counts is None:
            return None

        try:
            storage_path.unlink(missing_ok=True)
        except OSError:
            logger.exception(
                "知识文件数据库记录已删除，但磁盘文件清理失败 "
                "user_id=%s file_id=%s path=%s",
                user_id,
                knowledge_file_id,
                storage_path,
            )
            raise

    for knowledge_base_id in knowledge_base_ids:
        invalidate_knowledge_base_context(user_id, knowledge_base_id)

    return {
        "file_id": str(knowledge_file_id),
        "storage_deleted": True,
        **deletion_counts,
    }

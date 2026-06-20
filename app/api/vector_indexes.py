from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user_id
from app.db.locks import file_index_lock
from app.repositories.knowledge_base_repository import knowledge_base_exists
from app.repositories.knowledge_chunk_repository import delete_file_chunks
from app.repositories.knowledge_file_repository import (
    get_knowledge_base_files_for_indexing,
    get_user_knowledge_file,
    reset_file_index_state,
)
from app.repositories.vector_index_job_repository import (
    cancel_active_vector_index_jobs,
    get_user_vector_index_job,
)
from app.services.vectors.vector_index_queue_service import (
    enqueue_file_vector_index,
    serialize_vector_index_job,
)
from app.services.vectors.vector_index_service import get_vector_store


router = APIRouter(prefix="/chat", tags=["vector-indexes"])


@router.post("/knowledge-files/{knowledge_file_id}/vectors")
def index_knowledge_file_vectors(
    knowledge_file_id: UUID,
    user_id: int = Depends(get_current_user_id),
):
    """提交单个知识文件向量化任务。"""
    file_record = get_user_knowledge_file(user_id, knowledge_file_id)
    if file_record is None:
        raise HTTPException(status_code=404, detail="文件不存在")

    job = enqueue_file_vector_index(
        file_record=file_record,
        user_id=user_id,
    )

    return {
        "success": True,
        "message": job.get("message") or "文件向量化任务已提交",
        "job": job,
    }


@router.post("/knowledge-base/{knowledge_base_id}/vectors")
def index_knowledge_base_vectors(
    knowledge_base_id: UUID,
    user_id: int = Depends(get_current_user_id),
):
    """提交当前知识库下所有文件的向量化任务。"""
    if not knowledge_base_exists(knowledge_base_id, user_id):
        raise HTTPException(status_code=404, detail="知识库不存在")

    file_records = get_knowledge_base_files_for_indexing(
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
    )
    if not file_records:
        return {
            "success": True,
            "knowledge_base_id": str(knowledge_base_id),
            "jobs": [],
            "message": "知识库中没有可向量化的文件",
        }

    jobs = []
    for file_record in file_records:
        jobs.append(
            enqueue_file_vector_index(
                file_record=file_record,
                user_id=user_id,
                knowledge_base_id=knowledge_base_id,
            )
        )

    return {
        "success": True,
        "knowledge_base_id": str(knowledge_base_id),
        "jobs": jobs,
    }


@router.get("/vector-index-jobs/{job_id}")
def get_vector_index_job(
    job_id: UUID,
    user_id: int = Depends(get_current_user_id),
):
    """查询当前用户的向量化任务状态。"""
    job = get_user_vector_index_job(user_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    return {
        "success": True,
        "job": serialize_vector_index_job(job),
    }


@router.delete("/knowledge-files/{knowledge_file_id}/vectors")
def delete_knowledge_file_vectors(
    knowledge_file_id: UUID,
    user_id: int = Depends(get_current_user_id),
):
    """删除单个知识文件的向量化存储。

    同时清理 Chroma 向量库和 PostgreSQL 全文检索分块，
    并将文件状态重置为 pending，允许重新向量化。
    """
    file_record = get_user_knowledge_file(user_id, knowledge_file_id)
    if file_record is None:
        raise HTTPException(status_code=404, detail="文件不存在")

    normalized_user_id = str(user_id)
    normalized_file_id = str(knowledge_file_id)

    with file_index_lock(user_id, knowledge_file_id):
        # 1. 使尚未完成的旧任务失效，避免其在删除后再次写回数据。
        cancel_active_vector_index_jobs(
            user_id,
            knowledge_file_id,
            "用户删除了该文件的向量化结果",
        )

        # 2. 从 Chroma 向量库删除
        try:
            vectordb = get_vector_store()
            vectordb.delete(
                where={
                    "$and": [
                        {"user_id": normalized_user_id},
                        {"file_id": normalized_file_id},
                    ]
                }
            )
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"删除向量存储失败: {exc}",
            ) from exc

        # 3. 从 PostgreSQL 删除全文检索分块并递增版本。
        chunks_deleted = delete_file_chunks(user_id, knowledge_file_id)
        reset_file_index_state(user_id, knowledge_file_id)

    return {
        "success": True,
        "message": "向量化存储已删除",
        "file_id": normalized_file_id,
        "chunks_deleted": chunks_deleted,
    }

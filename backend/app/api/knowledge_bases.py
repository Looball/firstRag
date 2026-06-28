from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user_id
from app.repositories.knowledge_base_repository import (
    add_file_relation,
    create_knowledge_base as create_knowledge_base_record,
    file_relation_exists,
    get_knowledge_base_files as get_knowledge_base_file_records,
    get_user_knowledge_bases,
    remove_file_relation,
)
from app.repositories.retrieval_settings_repository import (
    DEFAULT_RETRIEVAL_SETTINGS,
    get_knowledge_base_retrieval_settings,
    upsert_knowledge_base_retrieval_settings,
)
from app.repositories.vector_index_job_repository import (
    get_latest_vector_index_jobs_by_file_ids,
)
from app.schemas.knowledge import (
    CreateKnowledgeBaseRequest,
    UpdateRetrievalSettingsRequest,
)
from app.services.vectors.vector_index_queue_service import (
    serialize_current_vector_index_job,
)
from app.services.knowledge_profile_cache import (
    invalidate_knowledge_base_context,
)


router = APIRouter(prefix="/chat", tags=["knowledge-bases"])


# 获取用户的知识库
@router.get("/knowledge-bases")
def get_knowledge_bases(user_id: int = Depends(get_current_user_id)):
    # 查询当前用户未删除的知识库、文件数量及所属会话
    rows = get_user_knowledge_bases(user_id)

    knowledge_bases = {}
    for row in rows:
        knowledge_base_id = row["id"]
        if knowledge_base_id not in knowledge_bases:
            knowledge_bases[knowledge_base_id] = {
                "id": str(knowledge_base_id),
                "name": row["name"],
                "is_default": row["is_default"],
                "file_count": row["file_count"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "conversations": [],
            }

        if row["conversation_id"] is not None:
            knowledge_bases[knowledge_base_id]["conversations"].append({
                "id": str(row["conversation_id"]),
                "title": row["conversation_title"],
            })

    return {
        "success": True,
        "knowledge_bases": list(knowledge_bases.values()),
    }


# 新建知识库
@router.post("/knowledge-base")
def create_knowledge_base(
    req: CreateKnowledgeBaseRequest,
    user_id: int = Depends(get_current_user_id),
):
    # 去除知识库名称首尾空格
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="知识库名称不能为空")

    # 创建知识库
    knowledge_base = create_knowledge_base_record(user_id, name)
    if knowledge_base is None:
        raise HTTPException(status_code=500, detail="知识库创建失败")

    return {
        "success": True,
        "knowledge_base": {
            "id": str(knowledge_base["id"]),
            "name": knowledge_base["name"],
            "is_default": knowledge_base["is_default"],
            "file_count": 0,
            "created_at": knowledge_base["created_at"],
            "updated_at": knowledge_base["updated_at"],
        },
    }


@router.get("/knowledge-base/{knowledge_base_id}/retrieval-settings")
def get_retrieval_settings(
    knowledge_base_id: UUID,
    user_id: int = Depends(get_current_user_id),
):
    """读取当前知识库的 RAG 检索策略设置。"""
    settings = get_knowledge_base_retrieval_settings(
        knowledge_base_id=knowledge_base_id,
        user_id=user_id,
    )
    if settings is None:
        raise HTTPException(status_code=404, detail="知识库不存在")

    return {
        "success": True,
        "knowledge_base_id": str(knowledge_base_id),
        "settings": settings,
    }


@router.patch("/knowledge-base/{knowledge_base_id}/retrieval-settings")
def update_retrieval_settings(
    knowledge_base_id: UUID,
    req: UpdateRetrievalSettingsRequest,
    user_id: int = Depends(get_current_user_id),
):
    """保存当前知识库的 RAG 检索策略设置。"""
    current_settings = get_knowledge_base_retrieval_settings(
        knowledge_base_id=knowledge_base_id,
        user_id=user_id,
    )
    if current_settings is None:
        raise HTTPException(status_code=404, detail="知识库不存在")

    update_values = req.model_dump(exclude_unset=True)
    settings = {
        **DEFAULT_RETRIEVAL_SETTINGS,
        **current_settings,
        **update_values,
    }
    saved_settings = upsert_knowledge_base_retrieval_settings(
        knowledge_base_id=knowledge_base_id,
        user_id=user_id,
        settings=settings,
    )
    if saved_settings is None:
        raise HTTPException(status_code=404, detail="知识库不存在")

    return {
        "success": True,
        "knowledge_base_id": str(knowledge_base_id),
        "settings": saved_settings,
    }


# 获取当前知识库的文件信息
@router.get("/knowledge-base/{knowledge_base_id}/files")
def get_knowledge_base_files(
    knowledge_base_id: UUID,
    user_id: int = Depends(get_current_user_id),
):
    rows = get_knowledge_base_file_records(
        knowledge_base_id,
        user_id,
    )
    latest_jobs = get_latest_vector_index_jobs_by_file_ids(
        user_id=user_id,
        file_ids=[str(row["id"]) for row in rows],
    )
    return {
        "success": True,
        "files": [
            {
                "id": str(row["id"]),
                "original_name": row["original_name"],
                "mime_type": row["mime_type"],
                "size_bytes": row["size_bytes"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "latest_index_job": serialize_current_vector_index_job(
                    row,
                    latest_jobs.get(str(row["id"])),
                ),
            }
            for row in rows
        ],
    }


# 解除数据库与文件的关联
@router.delete("/knowledge-base/{knowledge_base_id}/files/{knowledge_file_id}")
def remove_file_from_knowledge_base(
    knowledge_base_id: UUID,
    knowledge_file_id: UUID,
    user_id: int = Depends(get_current_user_id),
):
    # 解除关联
    relation = remove_file_relation(
        knowledge_base_id,
        knowledge_file_id,
        user_id,
    )
    if relation is None:
        raise HTTPException(status_code=404, detail="文件关联不存在")

    invalidate_knowledge_base_context(user_id, knowledge_base_id)

    return {
        "success": True,
        "knowledge_base_id": str(knowledge_base_id),
        "knowledge_file_id": str(knowledge_file_id),
    }


# 增加文件和知识库的关联
@router.post("/knowledge-base/{knowledge_base_id}/files/{knowledge_file_id}")
def add_file_to_knowledge_base(
    knowledge_base_id: UUID,
    knowledge_file_id: UUID,
    user_id: int = Depends(get_current_user_id),
):
    # 仅为属于当前用户且未删除的知识库和文件建立关联
    relation = add_file_relation(
        knowledge_base_id,
        knowledge_file_id,
        user_id,
    )
    # 可能是资源不存在，也可能已经关联
    if relation is None:
        if file_relation_exists(knowledge_base_id, knowledge_file_id):
            return {
                "success": True,
                "already_exists": True,
                "message": "文件已经关联到该知识库",
                "knowledge_base_id": str(knowledge_base_id),
                "knowledge_file_id": str(knowledge_file_id),
            }
        raise HTTPException(status_code=404, detail="知识库或文件不存在")

    invalidate_knowledge_base_context(user_id, knowledge_base_id)

    return {
        "success": True,
        "already_exists": False,
        "message": "文件关联成功",
        "knowledge_base_id": str(relation["knowledge_base_id"]),
        "knowledge_file_id": str(relation["knowledge_file_id"]),
        "created_at": relation["created_at"],
    }

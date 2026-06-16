from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user_id
from app.repositories.knowledge_base_repository import knowledge_base_exists
from app.repositories.knowledge_file_repository import (
    get_knowledge_base_files_for_indexing,
    get_user_knowledge_file,
)
from app.services.vectors.vector_index_service import index_knowledge_file_record


router = APIRouter(prefix="/chat", tags=["vector-indexes"])


@router.post("/knowledge-files/{knowledge_file_id}/vectors")
def index_knowledge_file_vectors(
    knowledge_file_id: UUID,
    user_id: int = Depends(get_current_user_id),
):
    """将当前用户的单个知识文件向量化并写入 Chroma。"""
    file_record = get_user_knowledge_file(user_id, knowledge_file_id)
    if file_record is None:
        raise HTTPException(status_code=404, detail="文件不存在")

    try:
        indexed_file = index_knowledge_file_record(file_record, user_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "success": True,
        "file": indexed_file,
    }


@router.post("/knowledge-base/{knowledge_base_id}/vectors")
def index_knowledge_base_vectors(
    knowledge_base_id: UUID,
    user_id: int = Depends(get_current_user_id),
):
    """将当前知识库关联的所有文件向量化并写入 Chroma。"""
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
            "indexed_files": [],
            "failed_files": [],
            "message": "知识库中没有可向量化的文件",
        }

    indexed_files = []
    failed_files = []

    for file_record in file_records:
        try:
            indexed_files.append(
                index_knowledge_file_record(file_record, user_id)
            )
        except Exception as exc:
            failed_files.append({
                "id": str(file_record["id"]),
                "original_name": file_record["original_name"],
                "error": str(exc),
            })

    return {
        "success": not failed_files,
        "knowledge_base_id": str(knowledge_base_id),
        "indexed_files": indexed_files,
        "failed_files": failed_files,
    }

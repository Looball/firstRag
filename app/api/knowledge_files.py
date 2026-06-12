from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.security import get_current_user_id
from app.repositories.knowledge_base_repository import (
    add_existing_file_relation,
    knowledge_base_exists,
)
from app.repositories.knowledge_file_repository import (
    create_file_with_relation,
    get_file_by_hash,
    get_user_knowledge_files,
)
from app.services.file_service import build_storage_path, calculate_file_hash


router = APIRouter(prefix="/chat", tags=["knowledge-files"])


# 向知识库上传文件
@router.post("/knowledge-base/{knowledge_base_id}/files")
async def upload_knowledge_files(
    knowledge_base_id: UUID,
    files: list[UploadFile] = File(...),
    description: str = Form(""),
    user_id: int = Depends(get_current_user_id),
):
    # 检查知识库存在且属于当前用户
    if not knowledge_base_exists(knowledge_base_id, user_id):
        raise HTTPException(status_code=404, detail="知识库不存在")

    uploaded_files = []

    # 使用循环处理多个文件
    for file in files:
        # 判断文件名是否存在
        if not file.filename:
            raise HTTPException(status_code=400, detail="文件名不能为空")

        # 计算文件hash值和文件大小
        file_hash, size_bytes = await calculate_file_hash(file)

        # 同一用户上传过相同内容时，复用已有文件，只补充知识库关联
        existing_file = get_file_by_hash(user_id, file_hash)

        if existing_file is not None:
            relation_created = add_existing_file_relation(
                knowledge_base_id,
                existing_file["id"],
            )
            uploaded_files.append({
                **dict(existing_file),
                "reused": True,
                "already_in_knowledge_base": not relation_created,
            })
            await file.close()
            continue

        # 为文件生成UUID
        file_id = uuid4()

        # 拼接文件存储路径
        storage_path = build_storage_path(
            user_id=user_id,
            file_id=str(file_id),
            file_hash=file_hash,
            original_name=file.filename,
        )

        # 创建文件目录
        storage_path.parent.mkdir(parents=True, exist_ok=True)

        # 保存文件，写入本地路径
        try:
            with storage_path.open("wb") as output:
                while chunk := await file.read(1024 * 1024):
                    output.write(chunk)

            # 同时插入文件记录和知识库关联记录
            file_record = create_file_with_relation(
                file_id=file_id,
                user_id=user_id,
                original_name=file.filename,
                storage_path=str(storage_path),
                mime_type=(
                    file.content_type
                    or "application/octet-stream"
                ),
                size_bytes=size_bytes,
                file_hash=file_hash,
                knowledge_base_id=knowledge_base_id,
            )
            if file_record is None:
                raise RuntimeError("文件记录创建失败")

            uploaded_files.append(dict(file_record))
        except Exception:
            storage_path.unlink(missing_ok=True)
            raise
        finally:
            await file.close()

    return {
        "success": True,
        "description": description,
        "files": uploaded_files,
    }


# 获取当前用户下所有知识库文件
@router.get("/knowledge-files")
def get_all_knowledge_files(user_id: int = Depends(get_current_user_id)):
    rows = get_user_knowledge_files(user_id)
    return {
        "success": True,
        "files": [
            {
                "id": str(row["id"]),
                "original_name": row["original_name"],
                "mime_type": row["mime_type"],
                "size_bytes": row["size_bytes"],
                "status": row["status"],
                "usage_count": row["usage_count"],
                "created_at": row["created_at"],
            }
            for row in rows
        ],
    }

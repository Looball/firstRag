from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.security import get_current_user_id
from app.db.executor import Row
from app.repositories.knowledge_base_repository import (
    add_existing_file_relation,
    knowledge_base_exists,
)
from app.repositories.knowledge_file_repository import (
    create_file_with_relation,
    get_file_by_hash,
    get_user_knowledge_files,
)
from app.repositories.vector_index_job_repository import (
    get_latest_vector_index_jobs_by_file_ids,
)
from app.services.file_service import (
    FileTooLargeError,
    build_storage_path,
    calculate_file_hash,
)
from app.services.vectors.vector_index_queue_service import (
    enqueue_file_vector_index,
    serialize_current_vector_index_job,
)


router = APIRouter(prefix="/chat", tags=["knowledge-files"])


def serialize_knowledge_file(
    row: Row | dict,
    reused: bool = False,
    already_in_knowledge_base: bool = False,
    index_job: dict | None = None,
) -> dict:
    """将知识文件数据库记录转换为接口响应结构。"""
    status = row["status"]
    if index_job is not None:
        status = index_job.get("status", "queued")

    return {
        "id": str(row["id"]),
        "original_name": row["original_name"],
        "mime_type": row["mime_type"],
        "size_bytes": row["size_bytes"],
        "status": status,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "reused": reused,
        "already_in_knowledge_base": already_in_knowledge_base,
        "index_job": index_job,
    }


def enqueue_uploaded_file_index(
    file_record: Row | dict,
    user_id: int,
    knowledge_base_id: UUID,
) -> dict:
    """上传接口可选提交向量化任务。"""
    return enqueue_file_vector_index(
        file_record=file_record,
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
    )


# 向知识库上传文件
@router.post("/knowledge-base/{knowledge_base_id}/files")
async def upload_knowledge_files(
    knowledge_base_id: UUID,
    files: list[UploadFile] = File(...),
    description: str = Form(""),
    auto_index: bool = Form(False),
    user_id: int = Depends(get_current_user_id),
):
    """上传文件到知识库。

    `auto_index=True` 时，文件保存或复用成功后只提交向量化任务，
    实际解析、切分、embedding 和入库由独立 worker 异步执行。
    """
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
        try:
            file_hash, size_bytes = await calculate_file_hash(file)
        except FileTooLargeError as exc:
            await file.close()
            raise HTTPException(status_code=413, detail=str(exc)) from exc

        # 同一用户上传过相同内容时，复用已有文件，只补充知识库关联
        existing_file = get_file_by_hash(user_id, file_hash)

        if existing_file is not None:
            relation_created = add_existing_file_relation(
                knowledge_base_id,
                existing_file["id"],
            )
            index_job = None
            if auto_index:
                index_job = enqueue_uploaded_file_index(
                    existing_file,
                    user_id,
                    knowledge_base_id,
                )

            uploaded_files.append(
                serialize_knowledge_file(
                    existing_file,
                    reused=True,
                    already_in_knowledge_base=not relation_created,
                    index_job=index_job,
                )
            )
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
        file_record = None
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

            index_job = None
            if auto_index:
                index_job = enqueue_uploaded_file_index(
                    file_record,
                    user_id,
                    knowledge_base_id,
                )

            uploaded_files.append(
                serialize_knowledge_file(
                    file_record,
                    index_job=index_job,
                )
            )
        except Exception:
            if file_record is None:
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
                "usage_count": row["usage_count"],
                "created_at": row["created_at"],
                "latest_index_job": serialize_current_vector_index_job(
                    row,
                    latest_jobs.get(str(row["id"])),
                ),
            }
            for row in rows
        ],
    }

import logging
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)

from app.core.config import (
    API_RATE_LIMIT_WINDOW_SECONDS,
    UPLOAD_RATE_LIMIT_MAX_REQUESTS,
    USER_UPLOAD_MAX_BYTES,
    USER_UPLOAD_MAX_FILES,
)
from app.core.rate_limit import build_rate_limit_identifier, enforce_rate_limit
from app.core.security import get_current_user_id
from app.db.executor import Row
from app.repositories.knowledge_base_repository import (
    add_existing_file_relation,
    knowledge_base_exists,
)
from app.repositories.knowledge_file_repository import (
    create_file_with_relation,
    get_file_by_hash,
    get_user_file_quota_usage,
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
from app.services.documents.document_service import (
    UnsupportedDocumentTypeError,
    build_unsupported_document_type_message,
    is_image_document_file_name,
    is_supported_document_file,
    validate_supported_image_content,
)
from app.services.vectors.vector_index_queue_service import (
    enqueue_file_vector_index,
    serialize_current_vector_index_job,
)
from app.services.knowledge_profile_cache import (
    invalidate_knowledge_base_context,
)
from app.services.knowledge_file_lifecycle_service import (
    permanently_delete_knowledge_file,
)


router = APIRouter(prefix="/chat", tags=["knowledge-files"])
logger = logging.getLogger(__name__)


def format_quota_size(size_bytes: int) -> str:
    """将容量字节数格式化为用户可读文本。"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def ensure_upload_quota_available(
    current_file_count: int,
    current_total_size_bytes: int,
    next_file_size_bytes: int,
) -> None:
    """检查新增文件是否会超过用户文件数量或容量配额。"""
    next_file_count = current_file_count + 1
    next_total_size_bytes = current_total_size_bytes + next_file_size_bytes

    if USER_UPLOAD_MAX_FILES > 0 and next_file_count > USER_UPLOAD_MAX_FILES:
        raise HTTPException(
            status_code=413,
            detail=(
                "上传文件数量已达上限："
                f"当前 {current_file_count} 个 / 上限 {USER_UPLOAD_MAX_FILES} 个。"
                "请删除不需要的文件后再上传。"
            ),
        )

    if USER_UPLOAD_MAX_BYTES > 0 and next_total_size_bytes > USER_UPLOAD_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                "上传容量配额不足："
                f"当前 {format_quota_size(current_total_size_bytes)}，"
                f"本次文件 {format_quota_size(next_file_size_bytes)}，"
                f"上限 {format_quota_size(USER_UPLOAD_MAX_BYTES)}。"
                "请删除不需要的文件后再上传。"
            ),
        )


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
    request: Request,
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

    enforce_rate_limit(
        "upload",
        build_rate_limit_identifier(request, "user", user_id),
        UPLOAD_RATE_LIMIT_MAX_REQUESTS,
        API_RATE_LIMIT_WINDOW_SECONDS,
        "上传请求过于频繁，请稍后再试。",
    )

    quota_usage = get_user_file_quota_usage(user_id)
    current_file_count = int(quota_usage["file_count"] or 0)
    current_total_size_bytes = int(quota_usage["total_size_bytes"] or 0)
    uploaded_files = []

    # 使用循环处理多个文件
    for file in files:
        # 判断文件名是否存在
        if not file.filename:
            await file.close()
            raise HTTPException(status_code=400, detail="文件名不能为空")
        if not is_supported_document_file(file.filename, file.content_type):
            await file.close()
            raise HTTPException(
                status_code=400,
                detail=build_unsupported_document_type_message(file.filename),
            )

        # 计算文件hash值和文件大小
        try:
            file_hash, size_bytes = await calculate_file_hash(file)
        except FileTooLargeError as exc:
            await file.close()
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        if is_image_document_file_name(file.filename):
            content_sample = await file.read(32)
            await file.seek(0)
            try:
                validate_supported_image_content(
                    file.filename,
                    content_sample,
                    file.content_type,
                )
            except UnsupportedDocumentTypeError as exc:
                await file.close()
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        # 同一用户上传过相同内容时，复用已有文件，只补充知识库关联
        existing_file = get_file_by_hash(user_id, file_hash)

        if existing_file is not None:
            relation_created = add_existing_file_relation(
                knowledge_base_id,
                existing_file["id"],
            )
            if relation_created:
                invalidate_knowledge_base_context(user_id, knowledge_base_id)
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

        try:
            ensure_upload_quota_available(
                current_file_count,
                current_total_size_bytes,
                size_bytes,
            )
        except HTTPException:
            await file.close()
            raise

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

            current_file_count += 1
            current_total_size_bytes += size_bytes
            invalidate_knowledge_base_context(user_id, knowledge_base_id)

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


@router.delete("/knowledge-files/{knowledge_file_id}")
def delete_knowledge_file(
    knowledge_file_id: UUID,
    user_id: int = Depends(get_current_user_id),
):
    """永久删除知识文件及其所有索引、关联和磁盘内容。"""
    try:
        result = permanently_delete_knowledge_file(user_id, knowledge_file_id)
    except Exception as exc:
        logger.exception(
            "永久删除知识文件失败 user_id=%s file_id=%s",
            user_id,
            knowledge_file_id,
        )
        raise HTTPException(
            status_code=500,
            detail="永久删除知识文件失败，请稍后重试或检查存储服务状态。",
        ) from exc

    if result is None:
        raise HTTPException(status_code=404, detail="文件不存在")

    return {
        "success": True,
        "message": "知识文件及其索引数据已永久删除",
        **result,
    }

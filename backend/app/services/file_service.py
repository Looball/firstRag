import hashlib
from pathlib import Path

from fastapi import UploadFile

from app.core.config import MAX_UPLOAD_FILE_SIZE_BYTES, UPLOAD_ROOT


class FileTooLargeError(ValueError):
    """文件大小超过后端允许上限时抛出的异常。"""


# 组装文件存储路径
def build_storage_path(
    user_id: int,
    file_id: str,
    file_hash: str,
    original_name: str,
) -> Path:
    """根据用户、文件和哈希信息构造文件落盘路径。"""
    extension = Path(original_name).suffix.lower()
    return (
        UPLOAD_ROOT
        / "users"
        / str(user_id)
        / file_hash[:2]
        / file_hash[2:4]
        / file_id
        / f"source{extension}"
    )


# 异步分批计算单个文件hash值
async def calculate_file_hash(file: UploadFile) -> tuple[str, int]:
    """分块计算上传文件哈希，并在超出限制时立即终止。"""
    sha256 = hashlib.sha256()
    size_bytes = 0

    while chunk := await file.read(1024 * 1024):
        size_bytes += len(chunk)
        if size_bytes > MAX_UPLOAD_FILE_SIZE_BYTES:
            raise FileTooLargeError(
                f"上传文件不能超过 {MAX_UPLOAD_FILE_SIZE_BYTES // (1024 * 1024)}MB"
            )

        sha256.update(chunk)

    await file.seek(0)
    return sha256.hexdigest(), size_bytes

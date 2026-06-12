import hashlib
from pathlib import Path

from fastapi import UploadFile

from app.core.config import UPLOAD_ROOT


def build_storage_path(
    user_id: int,
    file_id: str,
    file_hash: str,
    original_name: str,
) -> Path:
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


async def calculate_file_hash(file: UploadFile) -> tuple[str, int]:
    sha256 = hashlib.sha256()
    size_bytes = 0

    while chunk := await file.read(1024 * 1024):
        sha256.update(chunk)
        size_bytes += len(chunk)

    await file.seek(0)
    return sha256.hexdigest(), size_bytes

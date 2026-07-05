"""聊天图片附件的校验、存储和序列化。"""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile

from app.core.config import (
    CHAT_ATTACHMENT_ROOT,
    CHAT_IMAGE_MAX_FILE_SIZE_BYTES,
    CHAT_IMAGE_MAX_FILES,
    CHAT_IMAGE_MAX_TOTAL_BYTES,
)
from app.db.executor import Row
from app.repositories.message_attachment_repository import (
    bind_message_attachments,
    create_message_attachment,
    get_chat_attachments_for_binding,
)


SUPPORTED_CHAT_IMAGE_MIME_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
}
NORMALIZED_CHAT_IMAGE_MIME_TYPES = {
    "image/jpg": "image/jpeg",
}


class ChatAttachmentError(ValueError):
    """聊天附件不符合上传或绑定要求时抛出。"""


def normalize_image_mime_type(mime_type: str | None) -> str:
    """标准化图片 MIME type。"""
    normalized = (mime_type or "").strip().lower()
    normalized = NORMALIZED_CHAT_IMAGE_MIME_TYPES.get(
        normalized,
        normalized,
    )
    if normalized not in {"image/png", "image/jpeg", "image/webp"}:
        raise ChatAttachmentError("仅支持 PNG、JPEG 或 WebP 图片")
    return normalized


def sniff_image_mime_type(content: bytes) -> str:
    """根据文件头识别图片 MIME type，避免仅信任客户端声明。"""
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if (
        len(content) >= 12
        and content[:4] == b"RIFF"
        and content[8:12] == b"WEBP"
    ):
        return "image/webp"
    raise ChatAttachmentError("无法识别图片格式，仅支持 PNG、JPEG 或 WebP")


async def read_chat_image_upload(file: UploadFile) -> tuple[bytes, int]:
    """读取上传图片并检查单文件大小限制。"""
    content = bytearray()
    while chunk := await file.read(1024 * 1024):
        content.extend(chunk)
        if len(content) > CHAT_IMAGE_MAX_FILE_SIZE_BYTES:
            raise ChatAttachmentError(
                "单张图片不能超过 "
                f"{CHAT_IMAGE_MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB"
            )
    if not content:
        raise ChatAttachmentError("图片内容不能为空")
    return bytes(content), len(content)


def build_chat_attachment_storage_path(
    *,
    user_id: int,
    attachment_id: UUID,
    file_hash: str,
    mime_type: str,
) -> Path:
    """构造聊天图片附件落盘路径。"""
    extension = SUPPORTED_CHAT_IMAGE_MIME_TYPES[mime_type]
    return (
        CHAT_ATTACHMENT_ROOT
        / "users"
        / str(user_id)
        / file_hash[:2]
        / file_hash[2:4]
        / str(attachment_id)
        / f"image{extension}"
    )


def serialize_chat_attachment(row: Row | dict) -> dict:
    """将聊天图片附件记录转换为安全响应结构。"""
    attachment_id = str(row["id"])
    return {
        "id": attachment_id,
        "original_name": row["original_name"],
        "mime_type": row["mime_type"],
        "size_bytes": row["size_bytes"],
        "content_url": f"/chat/attachments/{attachment_id}/content",
        "created_at": row["created_at"],
    }


async def save_chat_image_attachment(
    *,
    user_id: int,
    conversation_id: UUID,
    file: UploadFile,
) -> dict:
    """校验并保存单个聊天图片附件。"""
    if not file.filename:
        raise ChatAttachmentError("图片文件名不能为空")

    content, size_bytes = await read_chat_image_upload(file)
    sniffed_mime_type = sniff_image_mime_type(content)
    declared_mime_type = (
        normalize_image_mime_type(file.content_type)
        if file.content_type
        else sniffed_mime_type
    )
    if declared_mime_type != sniffed_mime_type:
        raise ChatAttachmentError("图片内容与声明的文件类型不一致")

    file_hash = hashlib.sha256(content).hexdigest()
    attachment_id = uuid4()
    storage_path = build_chat_attachment_storage_path(
        user_id=user_id,
        attachment_id=attachment_id,
        file_hash=file_hash,
        mime_type=sniffed_mime_type,
    )
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(content)

    record = create_message_attachment(
        attachment_id=attachment_id,
        user_id=user_id,
        conversation_id=conversation_id,
        original_name=file.filename,
        storage_path=str(storage_path),
        mime_type=sniffed_mime_type,
        size_bytes=size_bytes,
        file_hash=file_hash,
    )
    if record is None:
        storage_path.unlink(missing_ok=True)
        raise RuntimeError("聊天图片附件保存失败")
    return serialize_chat_attachment(record)


def resolve_attachment_file_path(row: Row | dict) -> Path:
    """校验附件路径仍位于聊天附件目录内，并返回绝对路径。"""
    storage_root = CHAT_ATTACHMENT_ROOT.resolve()
    attachment_path = Path(row["storage_path"]).resolve()
    if storage_root not in attachment_path.parents:
        raise ChatAttachmentError("图片附件路径无效")
    if not attachment_path.is_file():
        raise ChatAttachmentError("图片附件文件不存在")
    return attachment_path


def validate_chat_attachments_for_message(
    *,
    user_id: int,
    conversation_id: UUID,
    attachment_ids: list[UUID],
) -> list[dict]:
    """校验本轮聊天要绑定的附件，并按请求顺序返回记录。"""
    if not attachment_ids:
        return []
    if len(attachment_ids) > CHAT_IMAGE_MAX_FILES:
        raise ChatAttachmentError(
            f"单轮最多只能附加 {CHAT_IMAGE_MAX_FILES} 张图片"
        )
    if len(set(attachment_ids)) != len(attachment_ids):
        raise ChatAttachmentError("图片附件不能重复提交")

    rows = get_chat_attachments_for_binding(
        user_id,
        conversation_id,
        attachment_ids,
    )
    rows_by_id = {str(row["id"]): dict(row) for row in rows}
    ordered_rows = []
    for attachment_id in attachment_ids:
        row = rows_by_id.get(str(attachment_id))
        if row is None:
            raise ChatAttachmentError("图片附件不存在或无权访问")
        if row.get("message_id") is not None:
            raise ChatAttachmentError("图片附件已经用于其他消息")
        ordered_rows.append(row)

    total_size = sum(int(row["size_bytes"] or 0) for row in ordered_rows)
    if total_size > CHAT_IMAGE_MAX_TOTAL_BYTES:
        raise ChatAttachmentError(
            "单轮图片总大小不能超过 "
            f"{CHAT_IMAGE_MAX_TOTAL_BYTES // (1024 * 1024)}MB"
        )
    return ordered_rows


def bind_attachments_to_user_message(
    *,
    user_id: int,
    conversation_id: UUID,
    message_id: int,
    attachment_ids: list[UUID],
) -> None:
    """将已校验的附件绑定到刚保存的用户消息。"""
    if not attachment_ids:
        return
    updated = bind_message_attachments(
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        attachment_ids=attachment_ids,
    )
    if updated != len(attachment_ids):
        raise RuntimeError("聊天图片附件绑定失败")


def build_vision_image_content(attachments: list[dict]) -> list[dict]:
    """读取附件文件并构造 OpenAI-compatible vision content。"""
    image_parts = []
    for attachment in attachments:
        attachment_path = resolve_attachment_file_path(attachment)
        encoded_image = base64.b64encode(
            attachment_path.read_bytes(),
        ).decode("ascii")
        image_parts.append({
            "type": "image_url",
            "image_url": {
                "url": (
                    f"data:{attachment['mime_type']};"
                    f"base64,{encoded_image}"
                ),
            },
        })
    return image_parts

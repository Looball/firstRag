"""聊天消息图片附件的数据访问。"""

from uuid import UUID

from app.db.executor import Row, execute, fetch_all, fetch_one


def create_message_attachment(
    *,
    attachment_id: UUID,
    user_id: int,
    conversation_id: UUID,
    original_name: str,
    storage_path: str,
    mime_type: str,
    size_bytes: int,
    file_hash: str,
) -> Row | None:
    """创建一条聊天图片附件记录。"""
    return fetch_one(
        """
        INSERT INTO message_attachments (
            id,
            user_id,
            conversation_id,
            original_name,
            storage_path,
            mime_type,
            size_bytes,
            file_hash
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING
            id,
            user_id,
            conversation_id,
            message_id,
            original_name,
            storage_path,
            mime_type,
            size_bytes,
            file_hash,
            status,
            created_at,
            updated_at;
        """,
        (
            attachment_id,
            user_id,
            conversation_id,
            original_name,
            storage_path,
            mime_type,
            size_bytes,
            file_hash,
        ),
    )


def get_user_message_attachment(
    user_id: int,
    attachment_id: UUID,
) -> Row | None:
    """查询当前用户可访问的单个图片附件。"""
    return fetch_one(
        """
        SELECT
            id,
            user_id,
            conversation_id,
            message_id,
            original_name,
            storage_path,
            mime_type,
            size_bytes,
            file_hash,
            status,
            created_at,
            updated_at
        FROM message_attachments
        WHERE user_id = %s
          AND id = %s
          AND status <> 'deleted';
        """,
        (user_id, attachment_id),
    )


def get_chat_attachments_for_binding(
    user_id: int,
    conversation_id: UUID,
    attachment_ids: list[UUID],
) -> list[Row]:
    """查询待绑定到本轮消息的附件。"""
    if not attachment_ids:
        return []
    return fetch_all(
        """
        SELECT
            id,
            user_id,
            conversation_id,
            message_id,
            original_name,
            storage_path,
            mime_type,
            size_bytes,
            file_hash,
            status,
            created_at,
            updated_at
        FROM message_attachments
        WHERE user_id = %s
          AND conversation_id = %s
          AND id = ANY(%s)
          AND status <> 'deleted'
        ORDER BY created_at ASC, id ASC;
        """,
        (user_id, conversation_id, attachment_ids),
    )


def bind_message_attachments(
    *,
    user_id: int,
    conversation_id: UUID,
    message_id: int,
    attachment_ids: list[UUID],
) -> int:
    """将图片附件绑定到用户消息。"""
    if not attachment_ids:
        return 0
    return execute(
        """
        UPDATE message_attachments
        SET message_id = %s,
            status = 'attached',
            updated_at = now()
        WHERE user_id = %s
          AND conversation_id = %s
          AND id = ANY(%s)
          AND status <> 'deleted';
        """,
        (message_id, user_id, conversation_id, attachment_ids),
    )

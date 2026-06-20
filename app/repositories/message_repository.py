from uuid import UUID

from app.db.executor import Row, fetch_all, fetch_one


def create_message(
    conversation_id: UUID,
    role: str,
    content: str,
    status: str = "completed",
) -> Row | None:
    """保存一条会话消息，并返回其主键和生成状态。"""
    return fetch_one(
        """
        INSERT INTO messages (conversation_id, role, content, status)
        VALUES (%s, %s, %s, %s)
        RETURNING id, status;
        """,
        (conversation_id, role, content, status),
    )


def finish_assistant_message(
    message_id: UUID,
    content: str,
    status: str,
    error_message: str | None = None,
) -> Row | None:
    """写入流式助手消息的最终内容和结束状态。"""
    return fetch_one(
        """
        UPDATE messages
        SET content = %s,
            status = %s,
            error_message = %s,
            completed_at = now()
        WHERE id = %s
          AND role = 'assistant'
          AND status = 'generating'
        RETURNING id, status, content, error_message, completed_at;
        """,
        (content, status, error_message, message_id),
    )


def get_conversation_messages(conversation_id: UUID) -> list[Row]:
    """按时间顺序查询会话消息。"""
    return fetch_all(
        """
        SELECT role, content
        FROM messages
        WHERE conversation_id = %s
          AND (role <> 'assistant' OR status = 'completed')
        ORDER BY created_at ASC, id ASC;
        """,
        (conversation_id,),
    )


def get_user_conversation_messages(
    user_id: int,
    conversation_id: UUID,
) -> list[Row]:
    """查询属于当前用户的指定会话消息。"""
    return fetch_all(
        """
        SELECT
            m.id,
            m.role,
            m.content,
            m.status,
            m.error_message,
            m.created_at
        FROM messages AS m
        JOIN conversations AS c
          ON c.id = m.conversation_id
        WHERE c.id = %s
          AND c.user_id = %s
          AND c.deleted_at IS NULL
        ORDER BY m.created_at ASC, m.id ASC;
        """,
        (conversation_id, user_id),
    )

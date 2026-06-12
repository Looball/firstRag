from uuid import UUID

from app.db.executor import Row, fetch_all, fetch_one


def conversation_exists(
    user_id: int,
    conversation_id: str | UUID,
) -> bool:
    """检查会话是否存在且属于当前用户。"""
    row = fetch_one(
        """
        SELECT id
        FROM conversations
        WHERE user_id = %s AND id = %s
        """,
        (user_id, conversation_id),
    )
    return row is not None


def get_user_conversations(user_id: int) -> list[Row]:
    """查询用户的会话及其消息。"""
    return fetch_all(
        """
        SELECT
            c.id AS conversation_id,
            c.title,
            c.created_at AS conversation_created_at,
            c.updated_at AS conversation_updated_at,
            m.id AS message_id,
            m.role,
            m.content,
            m.created_at AS message_created_at
        FROM conversations AS c
        LEFT JOIN messages AS m
          ON m.conversation_id = c.id
        WHERE c.user_id = %s
          AND c.deleted_at IS NULL
        ORDER BY c.updated_at DESC, m.created_at ASC, m.id ASC;
        """,
        (user_id,),
    )


def rename_conversation(
    conversation_id: UUID,
    user_id: int,
    title: str,
) -> Row | None:
    """重命名属于当前用户的会话。"""
    return fetch_one(
        """
        UPDATE conversations
        SET title = %s,
            updated_at = now()
        WHERE id = %s AND user_id = %s
        RETURNING id, user_id, title, created_at, updated_at;
        """,
        (title, conversation_id, user_id),
    )


def soft_delete_conversation(
    conversation_id: UUID,
    user_id: int,
) -> Row | None:
    """软删除属于当前用户的会话。"""
    return fetch_one(
        """
        UPDATE conversations
        SET deleted_at = now(),
            updated_at = now()
        WHERE id = %s
          AND user_id = %s
          AND deleted_at IS NULL
        RETURNING id;
        """,
        (conversation_id, user_id),
    )


def create_conversation(user_id: int, title: str | None) -> Row | None:
    """创建新会话。"""
    return fetch_one(
        """
        INSERT INTO conversations (user_id, title)
        VALUES (%s, %s)
        RETURNING id, user_id, title, created_at, updated_at;
        """,
        (user_id, title),
    )

from app.db.executor import Row, fetch_all, fetch_one


def create_message(
    conversation_id: str,
    role: str,
    content: str,
) -> Row | None:
    """保存一条会话消息。"""
    return fetch_one(
        """
        INSERT INTO messages (conversation_id, role, content)
        VALUES (%s, %s, %s)
        RETURNING id;
        """,
        (conversation_id, role, content),
    )


def get_conversation_messages(conversation_id: str) -> list[Row]:
    """按时间顺序查询会话消息。"""
    return fetch_all(
        """
        SELECT role, content
        FROM messages
        WHERE conversation_id = %s
        ORDER BY created_at ASC, id ASC;
        """,
        (conversation_id,),
    )

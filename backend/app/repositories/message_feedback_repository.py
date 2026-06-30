from psycopg.types.json import Jsonb

from app.db.executor import Row, fetch_all, fetch_one


def get_user_assistant_message(
    user_id: int,
    message_id: int,
) -> Row | None:
    """查询当前用户可反馈的助手消息。"""
    return fetch_one(
        """
        SELECT
            m.id,
            m.role,
            m.status,
            m.conversation_id
        FROM messages AS m
        JOIN conversations AS c
          ON c.id = m.conversation_id
        WHERE m.id = %s
          AND m.role = 'assistant'
          AND c.user_id = %s
          AND c.deleted_at IS NULL
        LIMIT 1;
        """,
        (message_id, user_id),
    )


def upsert_message_feedback(
    user_id: int,
    message_id: int,
    rating: str,
    reason: str | None,
    note: str | None,
    metadata: dict | None = None,
) -> Row | None:
    """创建或更新用户对单条助手消息的质量反馈。"""
    return fetch_one(
        """
        INSERT INTO message_feedback (
            user_id,
            message_id,
            rating,
            reason,
            note,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, message_id)
        DO UPDATE SET
            rating = EXCLUDED.rating,
            reason = EXCLUDED.reason,
            note = EXCLUDED.note,
            metadata = EXCLUDED.metadata,
            updated_at = now()
        RETURNING
            id,
            user_id,
            message_id,
            rating,
            reason,
            note,
            metadata,
            created_at,
            updated_at;
        """,
        (user_id, message_id, rating, reason, note, Jsonb(metadata or {})),
    )


def get_message_feedback_for_user_messages(
    user_id: int,
    message_ids: list[int],
) -> list[Row]:
    """批量查询当前用户在指定消息上的反馈。"""
    if not message_ids:
        return []

    return fetch_all(
        """
        SELECT
            id,
            user_id,
            message_id,
            rating,
            reason,
            note,
            metadata,
            created_at,
            updated_at
        FROM message_feedback
        WHERE user_id = %s
          AND message_id = ANY(%s);
        """,
        (user_id, message_ids),
    )

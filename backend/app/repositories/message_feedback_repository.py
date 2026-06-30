from psycopg.types.json import Jsonb

from app.db.executor import Row, fetch_one


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
            m.conversation_id,
            m.sources
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


def find_message_source(
    sources: list[dict],
    source_index: int,
) -> tuple[int, dict] | None:
    """在消息 sources 中按显式 index 或数组位置查找来源。"""
    for position, source in enumerate(sources):
        if source.get("index") == source_index or position == source_index:
            return position, source

    return None


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


def upsert_message_source_feedback(
    user_id: int,
    message_id: int,
    source_index: int,
    knowledge_file_id: str | None,
    chunk_index: int | None,
    rating: str,
    note: str | None,
    metadata: dict | None = None,
) -> Row | None:
    """创建或更新用户对单条引用来源的反馈。"""
    return fetch_one(
        """
        INSERT INTO message_source_feedback (
            user_id,
            message_id,
            source_index,
            knowledge_file_id,
            chunk_index,
            rating,
            note,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, message_id, source_index)
        DO UPDATE SET
            knowledge_file_id = EXCLUDED.knowledge_file_id,
            chunk_index = EXCLUDED.chunk_index,
            rating = EXCLUDED.rating,
            note = EXCLUDED.note,
            metadata = EXCLUDED.metadata,
            updated_at = now()
        RETURNING
            id,
            user_id,
            message_id,
            source_index,
            knowledge_file_id,
            chunk_index,
            rating,
            note,
            metadata,
            created_at,
            updated_at
        """,
        (
            user_id,
            message_id,
            source_index,
            knowledge_file_id,
            chunk_index,
            rating,
            note,
            Jsonb(metadata or {}),
        ),
    )

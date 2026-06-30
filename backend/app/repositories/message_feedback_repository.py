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


def get_user_message_eval_draft_context(
    user_id: int,
    message_id: int,
) -> Row | None:
    """查询从真实助手消息生成 eval case 草稿所需的上下文。"""
    return fetch_one(
        """
        SELECT
            m.id AS message_id,
            m.content AS answer,
            m.sources,
            m.retrieval,
            m.created_at AS message_created_at,
            c.id AS conversation_id,
            c.title AS conversation_title,
            kb.id AS knowledge_base_id,
            kb.name AS knowledge_base_name,
            user_message.content AS question,
            user_message.id AS question_message_id,
            mf.rating AS feedback_rating,
            mf.reason AS feedback_reason,
            mf.note AS feedback_note,
            mf.metadata AS feedback_metadata
        FROM messages AS m
        JOIN conversations AS c
          ON c.id = m.conversation_id
        JOIN knowledge_bases AS kb
          ON kb.id = c.knowledge_base_id
        LEFT JOIN LATERAL (
            SELECT previous_message.id, previous_message.content
            FROM messages AS previous_message
            WHERE previous_message.conversation_id = m.conversation_id
              AND previous_message.role = 'user'
              AND (
                  previous_message.created_at < m.created_at
                  OR (
                      previous_message.created_at = m.created_at
                      AND previous_message.id < m.id
                  )
              )
            ORDER BY previous_message.created_at DESC, previous_message.id DESC
            LIMIT 1
        ) AS user_message ON TRUE
        LEFT JOIN message_feedback AS mf
          ON mf.message_id = m.id
         AND mf.user_id = %s
        WHERE m.id = %s
          AND m.role = 'assistant'
          AND c.user_id = %s
          AND c.deleted_at IS NULL
          AND kb.user_id = %s
          AND kb.deleted_at IS NULL
        LIMIT 1;
        """,
        (user_id, message_id, user_id, user_id),
    )

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


def get_quality_feedback_summary(
    user_id: int,
    days: int = 7,
) -> Row | None:
    """统计当前用户最近一段时间的消息反馈总览。"""
    return fetch_one(
        """
        SELECT
            COUNT(*)::integer AS total_feedback,
            COUNT(*) FILTER (WHERE mf.rating = 'positive')::integer
                AS positive_feedback,
            COUNT(*) FILTER (WHERE mf.rating = 'negative')::integer
                AS negative_feedback
        FROM message_feedback AS mf
        JOIN messages AS m
          ON m.id = mf.message_id
        JOIN conversations AS c
          ON c.id = m.conversation_id
        WHERE mf.user_id = %s
          AND c.user_id = %s
          AND c.deleted_at IS NULL
          AND mf.created_at >= now() - (%s * interval '1 day');
        """,
        (user_id, user_id, days),
    )


def get_quality_feedback_reasons(
    user_id: int,
    days: int = 7,
) -> list[Row]:
    """统计当前用户负反馈原因分布。"""
    return fetch_all(
        """
        SELECT
            COALESCE(mf.reason, 'other') AS reason,
            COUNT(*)::integer AS count
        FROM message_feedback AS mf
        JOIN messages AS m
          ON m.id = mf.message_id
        JOIN conversations AS c
          ON c.id = m.conversation_id
        WHERE mf.user_id = %s
          AND c.user_id = %s
          AND c.deleted_at IS NULL
          AND mf.rating = 'negative'
          AND mf.created_at >= now() - (%s * interval '1 day')
        GROUP BY COALESCE(mf.reason, 'other')
        ORDER BY count DESC, reason ASC;
        """,
        (user_id, user_id, days),
    )


def get_quality_source_summary(
    user_id: int,
    days: int = 7,
) -> Row | None:
    """统计当前用户最近一段时间的 source 反馈总览。"""
    return fetch_one(
        """
        SELECT
            COUNT(*)::integer AS total_source_feedback,
            COUNT(*) FILTER (WHERE msf.rating = 'useful')::integer
                AS useful_source_feedback,
            COUNT(*) FILTER (WHERE msf.rating = 'irrelevant')::integer
                AS irrelevant_source_feedback
        FROM message_source_feedback AS msf
        JOIN messages AS m
          ON m.id = msf.message_id
        JOIN conversations AS c
          ON c.id = m.conversation_id
        WHERE msf.user_id = %s
          AND c.user_id = %s
          AND c.deleted_at IS NULL
          AND msf.created_at >= now() - (%s * interval '1 day');
        """,
        (user_id, user_id, days),
    )


def get_quality_irrelevant_source_files(
    user_id: int,
    days: int = 7,
    limit: int = 5,
) -> list[Row]:
    """统计当前用户被标记无关最多的来源文件。"""
    return fetch_all(
        """
        SELECT
            COALESCE(
                NULLIF(msf.metadata->>'file_name', ''),
                msf.knowledge_file_id::text,
                '未知来源'
            ) AS file_name,
            COUNT(*)::integer AS count
        FROM message_source_feedback AS msf
        JOIN messages AS m
          ON m.id = msf.message_id
        JOIN conversations AS c
          ON c.id = m.conversation_id
        WHERE msf.user_id = %s
          AND c.user_id = %s
          AND c.deleted_at IS NULL
          AND msf.rating = 'irrelevant'
          AND msf.created_at >= now() - (%s * interval '1 day')
        GROUP BY file_name
        ORDER BY count DESC, file_name ASC
        LIMIT %s;
        """,
        (user_id, user_id, days, limit),
    )


def get_quality_retrieval_summary(
    user_id: int,
    days: int = 7,
) -> Row | None:
    """统计当前用户最近助手消息的检索表现。"""
    return fetch_one(
        """
        SELECT
            COUNT(*)::integer AS assistant_messages,
            AVG(jsonb_array_length(COALESCE(m.sources, '[]'::jsonb)))
                AS average_sources,
            AVG(
                NULLIF(
                    m.retrieval #>> '{diagnostics,timing,first_answer_token_ms}',
                    ''
                )::numeric
            ) AS average_first_token_ms
        FROM messages AS m
        JOIN conversations AS c
          ON c.id = m.conversation_id
        WHERE c.user_id = %s
          AND c.deleted_at IS NULL
          AND m.role = 'assistant'
          AND m.status = 'completed'
          AND m.created_at >= now() - (%s * interval '1 day');
        """,
        (user_id, days),
    )

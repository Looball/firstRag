from uuid import UUID

from psycopg.types.json import Jsonb

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
    sources: list[dict] | None = None,
    retrieval: dict | None = None,
) -> Row | None:
    """写入流式助手消息的最终内容和结束状态。"""
    serialized_sources = sources if sources is not None else []
    serialized_retrieval = retrieval if retrieval is not None else {}
    return fetch_one(
        """
        UPDATE messages
        SET content = %s,
            status = %s,
            error_message = %s,
            sources = %s,
            retrieval = %s,
            completed_at = now()
        WHERE id = %s
          AND role = 'assistant'
          AND status = 'generating'
        RETURNING
            id,
            status,
            content,
            error_message,
            sources,
            retrieval,
            completed_at;
        """,
        (
            content,
            status,
            error_message,
            Jsonb(serialized_sources),
            Jsonb(serialized_retrieval),
            message_id,
        ),
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
            m.sources,
            m.retrieval,
            m.created_at,
            mf.id AS feedback_id,
            mf.rating AS feedback_rating,
            mf.reason AS feedback_reason,
            mf.note AS feedback_note,
            mf.metadata AS feedback_metadata,
            mf.created_at AS feedback_created_at,
            mf.updated_at AS feedback_updated_at,
            COALESCE(msf.source_feedbacks, '[]'::jsonb) AS source_feedbacks
        FROM messages AS m
        JOIN conversations AS c
          ON c.id = m.conversation_id
        LEFT JOIN message_feedback AS mf
          ON mf.message_id = m.id
         AND mf.user_id = %s
        LEFT JOIN LATERAL (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'id', source_feedback.id::text,
                    'source_index', source_feedback.source_index,
                    'knowledge_file_id', source_feedback.knowledge_file_id::text,
                    'chunk_index', source_feedback.chunk_index,
                    'rating', source_feedback.rating,
                    'note', source_feedback.note,
                    'metadata', source_feedback.metadata,
                    'created_at', source_feedback.created_at,
                    'updated_at', source_feedback.updated_at
                )
                ORDER BY source_feedback.source_index
            ) AS source_feedbacks
            FROM message_source_feedback AS source_feedback
            WHERE source_feedback.message_id = m.id
              AND source_feedback.user_id = %s
        ) AS msf ON TRUE
        WHERE c.id = %s
          AND c.user_id = %s
          AND c.deleted_at IS NULL
        ORDER BY m.created_at ASC, m.id ASC;
        """,
        (user_id, user_id, conversation_id, user_id),
    )

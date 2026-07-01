from uuid import UUID

from app.db.executor import Row, fetch_all, fetch_one


def conversation_exists(
    user_id: int,
    conversation_id: str | UUID,
) -> bool:
    """检查会话是否存在且属于当前用户。"""
    row = fetch_one(
        """
        SELECT c.id
        FROM conversations AS c
        JOIN knowledge_bases AS kb
          ON kb.id = c.knowledge_base_id
        WHERE c.user_id = %s
          AND c.id = %s
          AND c.deleted_at IS NULL
          AND kb.user_id = %s
          AND kb.deleted_at IS NULL;
        """,
        (user_id, conversation_id, user_id),
    )
    return row is not None


def get_knowledge_base_conversations(
    user_id: int,
    knowledge_base_id: UUID,
) -> list[Row]:
    """查询当前用户指定知识库下的会话。"""
    return fetch_all(
        """
        SELECT
            c.id AS conversation_id,
            c.knowledge_base_id,
            c.title,
            c.created_at AS conversation_created_at,
            c.updated_at AS conversation_updated_at
        FROM conversations AS c
        JOIN knowledge_bases AS kb
          ON kb.id = c.knowledge_base_id
        WHERE c.user_id = %s
          AND c.knowledge_base_id = %s
          AND c.deleted_at IS NULL
          AND kb.user_id = %s
          AND kb.deleted_at IS NULL
        ORDER BY c.updated_at DESC;
        """,
        (user_id, knowledge_base_id, user_id),
    )


def get_user_conversations(user_id: int) -> list[Row]:
    """查询当前用户所有未删除知识库下的未删除会话。"""
    return fetch_all(
        """
        SELECT
            c.id,
            c.knowledge_base_id,
            c.title,
            c.created_at,
            c.updated_at
        FROM conversations AS c
        JOIN knowledge_bases AS kb
          ON kb.id = c.knowledge_base_id
        WHERE c.user_id = %s
          AND c.deleted_at IS NULL
          AND kb.user_id = %s
          AND kb.deleted_at IS NULL
        ORDER BY c.updated_at DESC;
        """,
        (user_id, user_id),
    )


def rename_conversation(
    conversation_id: UUID,
    user_id: int,
    title: str,
) -> Row | None:
    """重命名属于当前用户的会话。"""
    return fetch_one(
        """
        UPDATE conversations AS c
        SET title = %s,
            updated_at = now()
        FROM knowledge_bases AS kb
        WHERE c.id = %s
          AND c.user_id = %s
          AND c.deleted_at IS NULL
          AND kb.id = c.knowledge_base_id
          AND kb.user_id = %s
          AND kb.deleted_at IS NULL
        RETURNING c.id, c.user_id, c.knowledge_base_id, c.title, c.created_at, c.updated_at;
        """,
        (title, conversation_id, user_id, user_id),
    )


def soft_delete_conversation(
    conversation_id: UUID,
    user_id: int,
) -> Row | None:
    """软删除属于当前用户的会话。"""
    return fetch_one(
        """
        UPDATE conversations AS c
        SET deleted_at = now(),
            updated_at = now()
        FROM knowledge_bases AS kb
        WHERE c.id = %s
          AND c.user_id = %s
          AND c.deleted_at IS NULL
          AND kb.id = c.knowledge_base_id
          AND kb.user_id = %s
          AND kb.deleted_at IS NULL
        RETURNING c.id;
        """,
        (conversation_id, user_id, user_id),
    )


def create_conversation(
    user_id: int,
    knowledge_base_id: UUID,
    title: str | None,
) -> Row | None:
    """创建新会话。"""
    return fetch_one(
        """
        INSERT INTO conversations (
            user_id,
            knowledge_base_id,
            title
        )
        SELECT
            %s,
            kb.id,
            %s
        FROM knowledge_bases AS kb
        WHERE kb.id = %s
          AND kb.user_id = %s
          AND kb.deleted_at IS NULL
        RETURNING id, user_id, knowledge_base_id, title, created_at, updated_at;
        """,
        (user_id, title, knowledge_base_id, user_id),
    )


def conversation_belongs_base(
    user_id: int,
    knowledge_base_id: UUID,
    conversation_id: UUID,
) -> bool:
    """检查会话是否属于当前知识库。"""
    row = fetch_one(
        """
        SELECT 1
        FROM conversations AS c
        JOIN knowledge_bases AS kb
          ON kb.id = c.knowledge_base_id
        WHERE c.id = %s
          AND c.user_id = %s
          AND c.knowledge_base_id = %s
          AND c.deleted_at IS NULL
          AND kb.user_id = %s
          AND kb.deleted_at IS NULL
        LIMIT 1;
        """,
        (conversation_id, user_id, knowledge_base_id, user_id),
    )

    return row is not None

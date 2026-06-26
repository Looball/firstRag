from uuid import UUID

from app.db.executor import Row, fetch_all, fetch_one


def get_user_knowledge_bases(user_id: int) -> list[Row]:
    """查询用户的知识库、文件数量及其会话。"""
    return fetch_all(
        """
        SELECT
            kb.id,
            kb.name,
            kb.is_default,
            kb.created_at,
            kb.updated_at,
            COALESCE(file_counts.file_count, 0) AS file_count,
            c.id AS conversation_id,
            c.title AS conversation_title
        FROM knowledge_bases AS kb
        LEFT JOIN (
            SELECT
                knowledge_base_id,
                COUNT(knowledge_file_id) AS file_count
            FROM knowledge_base_files
            GROUP BY knowledge_base_id
        ) AS file_counts
          ON file_counts.knowledge_base_id = kb.id
        LEFT JOIN conversations AS c
          ON c.knowledge_base_id = kb.id
         AND c.user_id = kb.user_id
         AND c.deleted_at IS NULL
        WHERE kb.user_id = %s
          AND kb.deleted_at IS NULL
        ORDER BY
            kb.is_default DESC,
            kb.created_at ASC,
            c.updated_at DESC;
        """,
        (user_id,),
    )


def create_knowledge_base(user_id: int, name: str) -> Row | None:
    """创建非默认知识库。"""
    return fetch_one(
        """
        INSERT INTO knowledge_bases (user_id, name, is_default)
        VALUES (%s, %s, FALSE)
        RETURNING id, name, is_default, created_at, updated_at;
        """,
        (user_id, name),
    )


def knowledge_base_exists(knowledge_base_id: UUID, user_id: int) -> bool:
    """检查知识库是否存在且属于当前用户。"""
    row = fetch_one(
        """
        SELECT id
        FROM knowledge_bases
        WHERE id = %s
          AND user_id = %s
          AND deleted_at IS NULL
        """,
        (knowledge_base_id, user_id),
    )
    return row is not None


def get_knowledge_base_files(
    knowledge_base_id: UUID,
    user_id: int,
) -> list[Row]:
    """查询指定知识库中的文件。"""
    return fetch_all(
        """
        SELECT
            kf.id,
            kf.original_name,
            kf.mime_type,
            kf.size_bytes,
            kf.status,
            kf.index_version,
            kf.created_at,
            kf.updated_at
        FROM knowledge_base_files AS kbf
        JOIN knowledge_bases AS kb
          ON kb.id = kbf.knowledge_base_id
        JOIN knowledge_files AS kf
          ON kf.id = kbf.knowledge_file_id
        WHERE kb.id = %s
          AND kb.user_id = %s
          AND kb.deleted_at IS NULL
          AND kf.user_id = %s
          AND kf.deleted_at IS NULL
        ORDER BY kbf.created_at DESC;
        """,
        (knowledge_base_id, user_id, user_id),
    )


def remove_file_relation(
    knowledge_base_id: UUID,
    knowledge_file_id: UUID,
    user_id: int,
) -> Row | None:
    """解除知识库与文件的关联。"""
    return fetch_one(
        """
        DELETE FROM knowledge_base_files AS kbf
        USING knowledge_bases AS kb, knowledge_files AS kf
        WHERE kbf.knowledge_base_id = kb.id
          AND kbf.knowledge_file_id = kf.id
          AND kb.id = %s
          AND kf.id = %s
          AND kb.user_id = %s
          AND kf.user_id = %s
          AND kb.deleted_at IS NULL
          AND kf.deleted_at IS NULL
        RETURNING kbf.knowledge_base_id, kbf.knowledge_file_id;
        """,
        (
            knowledge_base_id,
            knowledge_file_id,
            user_id,
            user_id,
        ),
    )


def add_file_relation(
    knowledge_base_id: UUID,
    knowledge_file_id: UUID,
    user_id: int,
) -> Row | None:
    """为属于当前用户的知识库和文件建立关联。"""
    return fetch_one(
        """
        INSERT INTO knowledge_base_files (
            knowledge_base_id,
            knowledge_file_id
        )
        SELECT kb.id, kf.id
        FROM knowledge_bases AS kb
        CROSS JOIN knowledge_files AS kf
        WHERE kb.id = %s
          AND kb.user_id = %s
          AND kb.deleted_at IS NULL
          AND kf.id = %s
          AND kf.user_id = %s
          AND kf.deleted_at IS NULL
        ON CONFLICT (knowledge_base_id, knowledge_file_id)
        DO NOTHING
        RETURNING knowledge_base_id, knowledge_file_id, created_at;
        """,
        (
            knowledge_base_id,
            user_id,
            knowledge_file_id,
            user_id,
        ),
    )


def file_relation_exists(
    knowledge_base_id: UUID,
    knowledge_file_id: UUID,
) -> bool:
    """检查知识库与文件是否已经关联。"""
    row = fetch_one(
        """
        SELECT 1
        FROM knowledge_base_files
        WHERE knowledge_base_id = %s
          AND knowledge_file_id = %s;
        """,
        (knowledge_base_id, knowledge_file_id),
    )
    return row is not None


def add_existing_file_relation(
    knowledge_base_id: UUID,
    knowledge_file_id: UUID,
) -> bool:
    """关联已有文件，返回本次是否新建了关联。"""
    row = fetch_one(
        """
        INSERT INTO knowledge_base_files (
            knowledge_base_id,
            knowledge_file_id
        )
        VALUES (%s, %s)
        ON CONFLICT (knowledge_base_id, knowledge_file_id)
        DO NOTHING
        RETURNING knowledge_file_id;
        """,
        (knowledge_base_id, knowledge_file_id),
    )
    return row is not None

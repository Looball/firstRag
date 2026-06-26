from uuid import UUID

from app.db.executor import Row, execute, fetch_all, fetch_one


def get_file_by_hash(user_id: int, file_hash: str) -> Row | None:
    """查询用户是否已经上传过相同内容的文件。"""
    return fetch_one(
        """
        SELECT
            id,
            user_id,
            original_name,
            storage_path,
            mime_type,
            size_bytes,
            status,
            index_version,
            created_at,
            updated_at
        FROM knowledge_files
        WHERE user_id = %s
          AND file_hash = %s
          AND deleted_at IS NULL
        LIMIT 1;
        """,
        (user_id, file_hash),
    )


def create_file_with_relation(
    file_id: UUID,
    user_id: int,
    original_name: str,
    storage_path: str,
    mime_type: str,
    size_bytes: int,
    file_hash: str,
    knowledge_base_id: UUID,
) -> Row | None:
    """创建文件记录并关联到知识库。"""
    return fetch_one(
        """
        WITH new_file AS (
            INSERT INTO knowledge_files (
                id,
                user_id,
                original_name,
                storage_path,
                mime_type,
                size_bytes,
                file_hash,
                status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
            RETURNING
                id,
                user_id,
                original_name,
                storage_path,
                mime_type,
                size_bytes,
                status,
                index_version,
                created_at,
                updated_at
        ),
        new_relation AS (
            INSERT INTO knowledge_base_files (
                knowledge_base_id,
                knowledge_file_id
            )
            SELECT %s, id
            FROM new_file
        )
        SELECT *
        FROM new_file;
        """,
        (
            file_id,
            user_id,
            original_name,
            storage_path,
            mime_type,
            size_bytes,
            file_hash,
            knowledge_base_id,
        ),
    )


def get_user_knowledge_files(user_id: int) -> list[Row]:
    """查询用户的全部知识文件及其使用次数。"""
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
            COUNT(kbf.knowledge_base_id) AS usage_count
        FROM knowledge_files AS kf
        LEFT JOIN knowledge_base_files AS kbf
          ON kbf.knowledge_file_id = kf.id
        WHERE kf.user_id = %s
          AND kf.deleted_at IS NULL
        GROUP BY
            kf.id,
            kf.original_name,
            kf.mime_type,
            kf.size_bytes,
            kf.status,
            kf.created_at
        ORDER BY kf.created_at DESC;
        """,
        (user_id,),
    )


def get_user_knowledge_file(
    user_id: int,
    knowledge_file_id: UUID,
) -> Row | None:
    """查询属于当前用户的单个知识文件。"""
    return fetch_one(
        """
        SELECT
            id,
            user_id,
            original_name,
            storage_path,
            mime_type,
            size_bytes,
            status,
            index_version,
            created_at,
            updated_at
        FROM knowledge_files
        WHERE id = %s
          AND user_id = %s
          AND deleted_at IS NULL;
        """,
        (knowledge_file_id, user_id),
    )


def get_knowledge_base_files_for_indexing(
    user_id: int,
    knowledge_base_id: UUID,
) -> list[Row]:
    """查询知识库中属于当前用户的文件及其存储路径。"""
    return fetch_all(
        """
        SELECT
            kf.id,
            kf.user_id,
            kf.original_name,
            kf.storage_path,
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
        ORDER BY kbf.created_at ASC;
        """,
        (knowledge_base_id, user_id, user_id),
    )


def update_knowledge_file_status(
    user_id: int,
    knowledge_file_id: UUID,
    status: str,
    expected_index_version: int | None = None,
) -> int:
    """更新属于当前用户的知识文件处理状态。"""
    version_filter = ""
    params: list[object] = [status, knowledge_file_id, user_id]
    if expected_index_version is not None:
        version_filter = "AND index_version = %s"
        params.append(expected_index_version)

    return execute(
        f"""
        UPDATE knowledge_files
        SET status = %s,
            updated_at = now()
        WHERE id = %s
          AND user_id = %s
          AND deleted_at IS NULL
          {version_filter};
        """,
        params,
    )


def reset_file_index_state(
    user_id: int,
    knowledge_file_id: UUID,
) -> Row | None:
    """递增索引版本并将文件重置为待索引状态。"""
    return fetch_one(
        """
        UPDATE knowledge_files
        SET index_version = index_version + 1,
            status = 'pending',
            updated_at = now()
        WHERE id = %s
          AND user_id = %s
          AND deleted_at IS NULL
        RETURNING id, index_version, status, updated_at;
        """,
        (knowledge_file_id, user_id),
    )


def get_file_original_names(
    user_id: int,
    file_ids: list[str],
) -> dict[str, str]:
    """批量查询 file_id → original_name 映射。

    用于检索结果序列化时，将磁盘存储文件名替换为用户上传的原始文件名。
    """
    if not file_ids:
        return {}

    rows = fetch_all(
        """
        SELECT id, original_name
        FROM knowledge_files
        WHERE user_id = %s
          AND id = ANY(%s::uuid[])
          AND deleted_at IS NULL;
        """,
        (user_id, file_ids),
    )
    return {str(row["id"]): row["original_name"] for row in rows}

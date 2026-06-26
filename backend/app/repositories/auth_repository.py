from app.db.executor import Row, fetch_one


def create_user_with_default_knowledge_base(
    username: str,
    password_hash: str,
) -> Row | None:
    """创建用户及其默认知识库。"""
    return fetch_one(
        """
        WITH new_user AS (
            INSERT INTO users (username, password_hash)
            VALUES (%s, %s)
            RETURNING id, username, created_at
        ),
        new_knowledge_base AS (
            INSERT INTO knowledge_bases (user_id, name, is_default)
            SELECT id, '默认知识库', TRUE
            FROM new_user
            RETURNING id, user_id, name, is_default, created_at
        )
        SELECT
            new_user.id AS user_id,
            new_user.username,
            new_knowledge_base.id AS knowledge_base_id,
            new_knowledge_base.name AS knowledge_base_name
        FROM new_user
        JOIN new_knowledge_base
          ON new_knowledge_base.user_id = new_user.id
        """,
        (username, password_hash),
    )


def get_user_by_username(username: str) -> Row | None:
    """按用户名查询登录所需的用户信息。"""
    return fetch_one(
        """
        SELECT u.id, u.username, u.password_hash
        FROM users AS u
        WHERE u.username = %s
        """,
        (username,),
    )

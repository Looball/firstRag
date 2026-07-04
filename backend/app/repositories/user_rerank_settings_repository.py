"""用户 rerank 模型设置的数据访问。"""

from typing import Any

from app.db.executor import Row, fetch_one


def get_user_rerank_settings(user_id: int) -> Row | None:
    """查询当前用户的 rerank 模型设置。"""
    return fetch_one(
        """
        SELECT
            user_id,
            provider,
            model,
            base_url,
            instruct,
            timeout_seconds,
            max_retries,
            created_at,
            updated_at
        FROM user_rerank_settings
        WHERE user_id = %s;
        """,
        (user_id,),
    )


def upsert_user_rerank_settings(
    user_id: int,
    settings: dict[str, Any],
) -> Row | None:
    """新增或更新当前用户的 rerank 模型设置。"""
    return fetch_one(
        """
        INSERT INTO user_rerank_settings (
            user_id,
            provider,
            model,
            base_url,
            instruct,
            timeout_seconds,
            max_retries
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE
        SET
            provider = EXCLUDED.provider,
            model = EXCLUDED.model,
            base_url = EXCLUDED.base_url,
            instruct = EXCLUDED.instruct,
            timeout_seconds = EXCLUDED.timeout_seconds,
            max_retries = EXCLUDED.max_retries,
            updated_at = now()
        RETURNING
            user_id,
            provider,
            model,
            base_url,
            instruct,
            timeout_seconds,
            max_retries,
            created_at,
            updated_at;
        """,
        (
            user_id,
            settings["provider"],
            settings["model"],
            settings["base_url"],
            settings["instruct"],
            settings["timeout_seconds"],
            settings["max_retries"],
        ),
    )

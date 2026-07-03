"""用户向量模型设置的数据访问。"""

from typing import Any

from app.db.executor import Row, fetch_one


def get_user_embedding_settings(user_id: int) -> Row | None:
    """查询当前用户的向量模型设置。"""
    return fetch_one(
        """
        SELECT
            user_id,
            provider,
            model,
            base_url,
            dimensions,
            api_key_ciphertext,
            api_key_hint,
            encryption_key_version,
            timeout_seconds,
            max_retries,
            created_at,
            updated_at
        FROM user_embedding_settings
        WHERE user_id = %s;
        """,
        (user_id,),
    )


def upsert_user_embedding_settings(
    user_id: int,
    settings: dict[str, Any],
) -> Row | None:
    """新增或更新当前用户的向量模型设置。"""
    return fetch_one(
        """
        INSERT INTO user_embedding_settings (
            user_id,
            provider,
            model,
            base_url,
            dimensions,
            api_key_ciphertext,
            api_key_hint,
            encryption_key_version,
            timeout_seconds,
            max_retries
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE
        SET
            provider = EXCLUDED.provider,
            model = EXCLUDED.model,
            base_url = EXCLUDED.base_url,
            dimensions = EXCLUDED.dimensions,
            api_key_ciphertext = EXCLUDED.api_key_ciphertext,
            api_key_hint = EXCLUDED.api_key_hint,
            encryption_key_version = EXCLUDED.encryption_key_version,
            timeout_seconds = EXCLUDED.timeout_seconds,
            max_retries = EXCLUDED.max_retries,
            updated_at = now()
        RETURNING
            user_id,
            provider,
            model,
            base_url,
            dimensions,
            api_key_ciphertext,
            api_key_hint,
            encryption_key_version,
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
            settings["dimensions"],
            settings["api_key_ciphertext"],
            settings["api_key_hint"],
            settings["encryption_key_version"],
            settings["timeout_seconds"],
            settings["max_retries"],
        ),
    )

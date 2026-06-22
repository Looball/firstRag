"""用户聊天模型设置的数据访问。"""

from typing import Any

from app.db.executor import Row, fetch_one


def get_user_llm_settings(user_id: int) -> Row | None:
    """查询当前用户的聊天模型设置。"""
    return fetch_one(
        """
        SELECT
            user_id,
            credential_mode,
            provider,
            model,
            base_url,
            api_key_ciphertext,
            encryption_key_version,
            temperature,
            max_tokens,
            timeout_seconds,
            max_retries,
            created_at,
            updated_at
        FROM user_llm_settings
        WHERE user_id = %s;
        """,
        (user_id,),
    )


def upsert_user_llm_settings(
    user_id: int,
    settings: dict[str, Any],
) -> Row | None:
    """新增或更新当前用户的聊天模型设置。"""
    return fetch_one(
        """
        INSERT INTO user_llm_settings (
            user_id,
            credential_mode,
            provider,
            model,
            base_url,
            api_key_ciphertext,
            encryption_key_version,
            temperature,
            max_tokens,
            timeout_seconds,
            max_retries
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (user_id) DO UPDATE
        SET
            credential_mode = EXCLUDED.credential_mode,
            provider = EXCLUDED.provider,
            model = EXCLUDED.model,
            base_url = EXCLUDED.base_url,
            api_key_ciphertext = EXCLUDED.api_key_ciphertext,
            encryption_key_version = EXCLUDED.encryption_key_version,
            temperature = EXCLUDED.temperature,
            max_tokens = EXCLUDED.max_tokens,
            timeout_seconds = EXCLUDED.timeout_seconds,
            max_retries = EXCLUDED.max_retries,
            updated_at = now()
        RETURNING
            user_id,
            credential_mode,
            provider,
            model,
            base_url,
            api_key_ciphertext,
            encryption_key_version,
            temperature,
            max_tokens,
            timeout_seconds,
            max_retries,
            created_at,
            updated_at;
        """,
        (
            user_id,
            settings["credential_mode"],
            settings["provider"],
            settings["model"],
            settings["base_url"],
            settings["api_key_ciphertext"],
            settings["encryption_key_version"],
            settings["temperature"],
            settings["max_tokens"],
            settings["timeout_seconds"],
            settings["max_retries"],
        ),
    )

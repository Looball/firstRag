"""用户按 rerank 厂商保存的 API 凭据数据访问。"""

from typing import Any

from app.db.executor import Row, fetch_all, fetch_one


def get_user_rerank_provider_credential(
    user_id: int,
    provider: str,
) -> Row | None:
    """查询当前用户指定 rerank 厂商的加密 API 凭据。"""
    return fetch_one(
        """
        SELECT
            user_id,
            provider,
            api_key_ciphertext,
            api_key_hint,
            encryption_key_version,
            created_at,
            updated_at
        FROM user_rerank_provider_credentials
        WHERE user_id = %s AND provider = %s;
        """,
        (user_id, provider),
    )


def get_user_rerank_provider_credentials(user_id: int) -> list[Row]:
    """查询当前用户已保存的 rerank 厂商凭据元数据。"""
    return fetch_all(
        """
        SELECT
            provider,
            api_key_hint,
            updated_at
        FROM user_rerank_provider_credentials
        WHERE user_id = %s
        ORDER BY provider;
        """,
        (user_id,),
    )


def upsert_user_rerank_provider_credential(
    user_id: int,
    provider: str,
    credential: dict[str, Any],
) -> Row | None:
    """新增或更新当前用户指定 rerank 厂商的加密 API 凭据。"""
    return fetch_one(
        """
        INSERT INTO user_rerank_provider_credentials (
            user_id,
            provider,
            api_key_ciphertext,
            api_key_hint,
            encryption_key_version
        )
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (user_id, provider) DO UPDATE
        SET
            api_key_ciphertext = EXCLUDED.api_key_ciphertext,
            api_key_hint = EXCLUDED.api_key_hint,
            encryption_key_version = EXCLUDED.encryption_key_version,
            updated_at = now()
        RETURNING
            user_id,
            provider,
            api_key_ciphertext,
            api_key_hint,
            encryption_key_version,
            created_at,
            updated_at;
        """,
        (
            user_id,
            provider,
            credential["api_key_ciphertext"],
            credential["api_key_hint"],
            credential["encryption_key_version"],
        ),
    )

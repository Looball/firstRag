-- 用户聊天模型设置。API Key 仅保存应用层加密后的密文。
CREATE TABLE IF NOT EXISTS user_llm_settings (
    user_id INTEGER PRIMARY KEY
        REFERENCES users(id) ON DELETE CASCADE,
    credential_mode TEXT NOT NULL DEFAULT 'platform'
        CHECK (credential_mode IN ('platform', 'user')),
    provider TEXT,
    model TEXT,
    base_url TEXT,
    api_key_ciphertext TEXT,
    encryption_key_version SMALLINT NOT NULL DEFAULT 1,
    temperature NUMERIC(3, 2) NOT NULL DEFAULT 0.20
        CHECK (temperature >= 0 AND temperature <= 2),
    max_tokens INTEGER NOT NULL DEFAULT 8000
        CHECK (max_tokens > 0),
    timeout_seconds NUMERIC(8, 2) NOT NULL DEFAULT 60
        CHECK (timeout_seconds > 0),
    max_retries SMALLINT NOT NULL DEFAULT 2
        CHECK (max_retries >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT user_llm_settings_mode_check CHECK (
        (
            credential_mode = 'platform'
            AND api_key_ciphertext IS NULL
        )
        OR
        (
            credential_mode = 'user'
            AND provider IS NOT NULL
            AND model IS NOT NULL
            AND api_key_ciphertext IS NOT NULL
        )
    )
);

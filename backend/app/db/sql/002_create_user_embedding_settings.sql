CREATE TABLE IF NOT EXISTS user_embedding_settings (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    base_url TEXT,
    dimensions INTEGER,
    api_key_ciphertext TEXT NOT NULL,
    api_key_hint TEXT,
    encryption_key_version SMALLINT NOT NULL DEFAULT 1,
    timeout_seconds NUMERIC(8, 2) NOT NULL DEFAULT 60,
    max_retries SMALLINT NOT NULL DEFAULT 2,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT user_embedding_settings_provider_check
        CHECK (provider IN ('qwen', 'zhipuai')),
    CONSTRAINT user_embedding_settings_model_check
        CHECK (btrim(model) <> ''),
    CONSTRAINT user_embedding_settings_dimensions_check
        CHECK (dimensions IS NULL OR dimensions > 0),
    CONSTRAINT user_embedding_settings_timeout_seconds_check
        CHECK (timeout_seconds > 0),
    CONSTRAINT user_embedding_settings_max_retries_check
        CHECK (max_retries >= 0)
);

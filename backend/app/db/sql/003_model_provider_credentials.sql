ALTER TABLE user_embedding_settings
DROP CONSTRAINT IF EXISTS user_embedding_settings_provider_check;

ALTER TABLE user_embedding_settings
ADD CONSTRAINT user_embedding_settings_provider_check
CHECK (btrim(provider) <> '');

CREATE TABLE IF NOT EXISTS user_embedding_provider_credentials (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    api_key_ciphertext TEXT NOT NULL,
    api_key_hint TEXT,
    encryption_key_version SMALLINT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, provider),
    CONSTRAINT user_embedding_provider_credentials_provider_check
        CHECK (btrim(provider) <> '')
);

INSERT INTO user_embedding_provider_credentials (
    user_id,
    provider,
    api_key_ciphertext,
    api_key_hint,
    encryption_key_version,
    created_at,
    updated_at
)
SELECT
    user_id,
    provider,
    api_key_ciphertext,
    api_key_hint,
    encryption_key_version,
    created_at,
    updated_at
FROM user_embedding_settings
WHERE api_key_ciphertext IS NOT NULL
ON CONFLICT (user_id, provider) DO NOTHING;

CREATE TABLE IF NOT EXISTS user_rerank_settings (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL DEFAULT 'local',
    model TEXT NOT NULL,
    base_url TEXT,
    instruct TEXT,
    timeout_seconds NUMERIC(8, 2) NOT NULL DEFAULT 60,
    max_retries SMALLINT NOT NULL DEFAULT 2,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT user_rerank_settings_provider_check
        CHECK (btrim(provider) <> ''),
    CONSTRAINT user_rerank_settings_model_check
        CHECK (btrim(model) <> ''),
    CONSTRAINT user_rerank_settings_timeout_seconds_check
        CHECK (timeout_seconds > 0),
    CONSTRAINT user_rerank_settings_max_retries_check
        CHECK (max_retries >= 0)
);

CREATE TABLE IF NOT EXISTS user_rerank_provider_credentials (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    api_key_ciphertext TEXT NOT NULL,
    api_key_hint TEXT,
    encryption_key_version SMALLINT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, provider),
    CONSTRAINT user_rerank_provider_credentials_provider_check
        CHECK (btrim(provider) <> '')
);

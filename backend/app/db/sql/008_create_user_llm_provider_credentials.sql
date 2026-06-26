-- 用户按厂商保存的加密 API 凭据；完整 Key 绝不返回给前端。
CREATE TABLE IF NOT EXISTS user_llm_provider_credentials (
    user_id INTEGER NOT NULL
        REFERENCES users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    api_key_ciphertext TEXT NOT NULL,
    api_key_hint TEXT,
    encryption_key_version SMALLINT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, provider)
);

-- 将历史单一活动凭据复制到对应厂商，保留已有厂商凭据。
INSERT INTO user_llm_provider_credentials (
    user_id,
    provider,
    api_key_ciphertext,
    api_key_hint,
    encryption_key_version
)
SELECT
    user_id,
    provider,
    api_key_ciphertext,
    api_key_hint,
    encryption_key_version
FROM user_llm_settings
WHERE credential_mode = 'user'
  AND provider IS NOT NULL
  AND api_key_ciphertext IS NOT NULL
ON CONFLICT (user_id, provider) DO NOTHING;

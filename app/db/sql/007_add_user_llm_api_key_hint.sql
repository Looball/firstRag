-- API Key 脱敏提示仅用于设置页确认已保存凭据，不包含完整 Key。
ALTER TABLE user_llm_settings
    ADD COLUMN IF NOT EXISTS api_key_hint TEXT;

-- 持久化助手回答引用，支持页面刷新后继续展示 Sources。
ALTER TABLE messages
    ADD COLUMN IF NOT EXISTS sources JSONB NOT NULL DEFAULT '[]'::jsonb;

-- 持久化本轮检索路由和召回统计，支持刷新后恢复检索状态。
ALTER TABLE messages
    ADD COLUMN IF NOT EXISTS retrieval JSONB NOT NULL DEFAULT '{}'::jsonb;

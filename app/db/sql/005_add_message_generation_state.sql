-- 保存流式回答的生成状态，避免失败时只留下孤立的用户消息。
ALTER TABLE messages
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'completed',
    ADD COLUMN IF NOT EXISTS error_message TEXT,
    ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;

ALTER TABLE messages
    DROP CONSTRAINT IF EXISTS messages_status_check;

ALTER TABLE messages
    ADD CONSTRAINT messages_status_check
    CHECK (status IN ('generating', 'completed', 'failed', 'cancelled'));

CREATE INDEX IF NOT EXISTS idx_messages_conversation_status
ON messages (conversation_id, status, created_at, id);

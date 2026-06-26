-- 为已有的向量化任务补充可恢复的租约与延迟重试能力。
ALTER TABLE vector_index_jobs
    ADD COLUMN IF NOT EXISTS available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ;

UPDATE vector_index_jobs
SET available_at = COALESCE(available_at, created_at, now())
WHERE available_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_vector_index_jobs_ready
ON vector_index_jobs (status, available_at, priority, created_at);

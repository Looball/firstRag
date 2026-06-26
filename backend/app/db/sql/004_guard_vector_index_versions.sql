-- 使用版本号标识每次文件索引，避免已经取消的旧任务覆盖新结果。
ALTER TABLE knowledge_files
    ADD COLUMN IF NOT EXISTS index_version INTEGER NOT NULL DEFAULT 0;

ALTER TABLE knowledge_file_chunks
    ADD COLUMN IF NOT EXISTS index_version INTEGER NOT NULL DEFAULT 0;

ALTER TABLE vector_index_jobs
    ADD COLUMN IF NOT EXISTS index_version INTEGER NOT NULL DEFAULT 0;

ALTER TABLE vector_index_jobs
    DROP CONSTRAINT IF EXISTS vector_index_jobs_status_check;

ALTER TABLE vector_index_jobs
    ADD CONSTRAINT vector_index_jobs_status_check
    CHECK (status IN ('queued', 'processing', 'succeeded', 'failed', 'cancelled'));

CREATE INDEX IF NOT EXISTS idx_knowledge_file_chunks_file_version
ON knowledge_file_chunks (user_id, knowledge_file_id, index_version);

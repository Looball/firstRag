CREATE TABLE IF NOT EXISTS vector_index_jobs (
    id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL,
    knowledge_file_id UUID NOT NULL REFERENCES knowledge_files(id) ON DELETE CASCADE,
    knowledge_base_id UUID REFERENCES knowledge_bases(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    priority INTEGER NOT NULL DEFAULT 100,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    locked_by TEXT,
    locked_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    error_message TEXT,
    result JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT vector_index_jobs_status_check
        CHECK (status IN ('queued', 'processing', 'succeeded', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_vector_index_jobs_status_created
ON vector_index_jobs (status, priority, created_at);

CREATE INDEX IF NOT EXISTS idx_vector_index_jobs_user_file
ON vector_index_jobs (user_id, knowledge_file_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_vector_index_jobs_active_file
ON vector_index_jobs (user_id, knowledge_file_id)
WHERE status IN ('queued', 'processing');

-- FirstRAG 当前数据库结构基线。
-- 项目尚未进入生产环境，本文件以 2026-06-30 的完整 schema 作为空库初始化基线。
-- 后续新增表、字段、索引或约束时，从 001_xxx.sql 开始新增增量 migration。

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS knowledge_bases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_knowledge_bases_user_default
ON knowledge_bases (user_id)
WHERE is_default = TRUE AND deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS knowledge_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL,
    original_name TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    mime_type TEXT,
    size_bytes BIGINT,
    file_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    index_version INTEGER NOT NULL DEFAULT 0
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_knowledge_files_user_hash
ON knowledge_files (user_id, file_hash)
WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS knowledge_base_files (
    knowledge_base_id UUID NOT NULL,
    knowledge_file_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (knowledge_base_id, knowledge_file_id)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_base_files_base_id
ON knowledge_base_files (knowledge_base_id);

CREATE INDEX IF NOT EXISTS idx_knowledge_base_files_file_id
ON knowledge_base_files (knowledge_file_id);

CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL,
    title TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    knowledge_base_id UUID NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_conversations_knowledge_base_id
ON conversations (knowledge_base_id);

CREATE INDEX IF NOT EXISTS idx_conversations_user_knowledge_base
ON conversations (user_id, knowledge_base_id)
WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    conversation_id UUID NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status TEXT NOT NULL DEFAULT 'completed',
    error_message TEXT,
    completed_at TIMESTAMPTZ,
    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    retrieval JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT messages_status_check
        CHECK (status IN ('generating', 'completed', 'failed', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_status
ON messages (conversation_id, status, created_at, id);

CREATE TABLE IF NOT EXISTS knowledge_file_chunks (
    chunk_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    knowledge_file_id UUID NOT NULL REFERENCES knowledge_files(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    index_version INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_knowledge_file_chunks_user_file
ON knowledge_file_chunks (user_id, knowledge_file_id);

CREATE INDEX IF NOT EXISTS idx_knowledge_file_chunks_search
ON knowledge_file_chunks
USING GIN (to_tsvector('simple', content));

CREATE INDEX IF NOT EXISTS idx_knowledge_file_chunks_content_trgm
ON knowledge_file_chunks
USING GIN (content gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_knowledge_file_chunks_file_version
ON knowledge_file_chunks (user_id, knowledge_file_id, index_version);

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
    available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    heartbeat_at TIMESTAMPTZ,
    index_version INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT vector_index_jobs_status_check
        CHECK (status IN ('queued', 'processing', 'succeeded', 'failed', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_vector_index_jobs_status_created
ON vector_index_jobs (status, priority, created_at);

CREATE INDEX IF NOT EXISTS idx_vector_index_jobs_user_file
ON vector_index_jobs (user_id, knowledge_file_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_vector_index_jobs_active_file
ON vector_index_jobs (user_id, knowledge_file_id)
WHERE status IN ('queued', 'processing');

CREATE INDEX IF NOT EXISTS idx_vector_index_jobs_ready
ON vector_index_jobs (status, available_at, priority, created_at);

CREATE TABLE IF NOT EXISTS user_llm_settings (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    credential_mode TEXT NOT NULL DEFAULT 'platform',
    provider TEXT,
    model TEXT,
    base_url TEXT,
    api_key_ciphertext TEXT,
    encryption_key_version SMALLINT NOT NULL DEFAULT 1,
    temperature NUMERIC(3, 2) NOT NULL DEFAULT 0.20,
    max_tokens INTEGER NOT NULL DEFAULT 8000,
    timeout_seconds NUMERIC(8, 2) NOT NULL DEFAULT 60,
    max_retries SMALLINT NOT NULL DEFAULT 2,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    api_key_hint TEXT,
    CONSTRAINT user_llm_settings_credential_mode_check
        CHECK (credential_mode IN ('platform', 'user')),
    CONSTRAINT user_llm_settings_temperature_check
        CHECK (temperature >= 0 AND temperature <= 2),
    CONSTRAINT user_llm_settings_max_tokens_check
        CHECK (max_tokens > 0),
    CONSTRAINT user_llm_settings_timeout_seconds_check
        CHECK (timeout_seconds > 0),
    CONSTRAINT user_llm_settings_max_retries_check
        CHECK (max_retries >= 0),
    CONSTRAINT user_llm_settings_mode_check CHECK (
        (
            credential_mode = 'platform'
            AND api_key_ciphertext IS NULL
        )
        OR
        (
            credential_mode = 'user'
            AND provider IS NOT NULL
            AND model IS NOT NULL
            AND api_key_ciphertext IS NOT NULL
        )
    )
);

CREATE TABLE IF NOT EXISTS user_llm_provider_credentials (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    api_key_ciphertext TEXT NOT NULL,
    api_key_hint TEXT,
    encryption_key_version SMALLINT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, provider)
);

CREATE TABLE IF NOT EXISTS knowledge_base_retrieval_settings (
    knowledge_base_id UUID PRIMARY KEY REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    retrieval_mode TEXT NOT NULL DEFAULT 'auto',
    enable_query_router BOOLEAN NOT NULL DEFAULT TRUE,
    enable_rerank BOOLEAN NOT NULL DEFAULT TRUE,
    top_k INTEGER NOT NULL DEFAULT 5,
    vector_top_k INTEGER NOT NULL DEFAULT 20,
    fulltext_top_k INTEGER NOT NULL DEFAULT 20,
    rrf_k INTEGER NOT NULL DEFAULT 10,
    rerank_score_threshold NUMERIC(6, 3) NOT NULL DEFAULT 0.000,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT knowledge_base_retrieval_settings_mode_check
        CHECK (retrieval_mode IN ('auto', 'always', 'never')),
    CONSTRAINT knowledge_base_retrieval_settings_top_k_check
        CHECK (top_k BETWEEN 1 AND 20),
    CONSTRAINT knowledge_base_retrieval_settings_vector_top_k_check
        CHECK (vector_top_k BETWEEN 1 AND 100),
    CONSTRAINT knowledge_base_retrieval_settings_fulltext_top_k_check
        CHECK (fulltext_top_k BETWEEN 1 AND 100),
    CONSTRAINT knowledge_base_retrieval_settings_rrf_k_check
        CHECK (rrf_k BETWEEN 1 AND 100),
    CONSTRAINT knowledge_base_retrieval_settings_threshold_check
        CHECK (rerank_score_threshold BETWEEN -20.000 AND 20.000)
);

CREATE INDEX IF NOT EXISTS idx_kb_retrieval_settings_user
ON knowledge_base_retrieval_settings (user_id);

CREATE TABLE IF NOT EXISTS message_feedback (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    message_id BIGINT NOT NULL,
    rating TEXT NOT NULL,
    reason TEXT,
    note TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT message_feedback_rating_check
        CHECK (rating IN ('positive', 'negative')),
    CONSTRAINT message_feedback_reason_check
        CHECK (
            reason IS NULL OR reason IN (
                'irrelevant_sources',
                'missing_answer',
                'hallucination',
                'outdated_or_wrong',
                'too_slow',
                'format_issue',
                'other'
            )
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_message_feedback_user_message
ON message_feedback (user_id, message_id);

CREATE INDEX IF NOT EXISTS idx_message_feedback_user_created
ON message_feedback (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_message_feedback_rating_reason
ON message_feedback (rating, reason, created_at DESC);

CREATE TABLE IF NOT EXISTS message_source_feedback (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    message_id BIGINT NOT NULL,
    source_index INTEGER NOT NULL,
    knowledge_file_id UUID,
    chunk_index INTEGER,
    rating TEXT NOT NULL,
    note TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT message_source_feedback_source_index_check
        CHECK (source_index >= 0),
    CONSTRAINT message_source_feedback_rating_check
        CHECK (rating IN ('useful', 'irrelevant'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_message_source_feedback_unique_source
ON message_source_feedback (user_id, message_id, source_index);

CREATE INDEX IF NOT EXISTS idx_message_source_feedback_file_created
ON message_source_feedback (knowledge_file_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_message_source_feedback_rating_created
ON message_source_feedback (rating, created_at DESC);

CREATE TABLE IF NOT EXISTS knowledge_file_chunks (
    chunk_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    knowledge_file_id UUID NOT NULL REFERENCES knowledge_files(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_file_chunks_user_file
ON knowledge_file_chunks (user_id, knowledge_file_id);

CREATE INDEX IF NOT EXISTS idx_knowledge_file_chunks_search
ON knowledge_file_chunks
USING GIN (to_tsvector('simple', content));

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_knowledge_file_chunks_content_trgm
ON knowledge_file_chunks
USING GIN (content gin_trgm_ops);

CREATE TABLE IF NOT EXISTS knowledge_file_chunk_parents (
    parent_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    knowledge_file_id UUID NOT NULL REFERENCES knowledge_files(id) ON DELETE CASCADE,
    index_version INTEGER NOT NULL,
    parent_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT knowledge_file_chunk_parents_identity_unique
        UNIQUE (user_id, knowledge_file_id, index_version, parent_index)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_file_chunk_parents_user_file_version
ON knowledge_file_chunk_parents (
    user_id,
    knowledge_file_id,
    index_version,
    parent_index
);

ALTER TABLE knowledge_file_chunks
ADD COLUMN IF NOT EXISTS parent_id TEXT
    REFERENCES knowledge_file_chunk_parents(parent_id) ON DELETE CASCADE;

ALTER TABLE knowledge_file_chunks
ADD COLUMN IF NOT EXISTS child_index INTEGER;

ALTER TABLE knowledge_file_chunks
DROP CONSTRAINT IF EXISTS knowledge_file_chunks_parent_child_pair_check;

ALTER TABLE knowledge_file_chunks
ADD CONSTRAINT knowledge_file_chunks_parent_child_pair_check
CHECK (
    (parent_id IS NULL AND child_index IS NULL)
    OR (parent_id IS NOT NULL AND child_index >= 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_knowledge_file_chunks_parent_child
ON knowledge_file_chunks (parent_id, child_index)
WHERE parent_id IS NOT NULL;

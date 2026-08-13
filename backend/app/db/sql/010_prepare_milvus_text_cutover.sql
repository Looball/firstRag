ALTER TABLE knowledge_base_retrieval_settings
RENAME COLUMN fulltext_top_k TO sparse_top_k;

ALTER TABLE knowledge_base_retrieval_settings
RENAME CONSTRAINT knowledge_base_retrieval_settings_fulltext_top_k_check
TO knowledge_base_retrieval_settings_sparse_top_k_check;

CREATE TABLE IF NOT EXISTS milvus_text_cutover_audits (
    knowledge_file_id UUID PRIMARY KEY
        REFERENCES knowledge_files(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    index_version INTEGER NOT NULL CHECK (index_version >= 1),
    collection_name VARCHAR(255) NOT NULL,
    chunk_count INTEGER NOT NULL CHECK (chunk_count >= 1),
    content_sha256 CHAR(64) NOT NULL,
    audited_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT milvus_text_cutover_audits_content_sha256_check
        CHECK (content_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE INDEX IF NOT EXISTS idx_milvus_text_cutover_audits_user
ON milvus_text_cutover_audits (user_id, audited_at DESC);

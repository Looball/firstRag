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
    rerank_score_threshold NUMERIC(6,3) NOT NULL DEFAULT 0.000,
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
    ON knowledge_base_retrieval_settings(user_id);

ALTER TABLE knowledge_base_retrieval_settings
    ALTER COLUMN top_k SET DEFAULT 4,
    ALTER COLUMN vector_top_k SET DEFAULT 16,
    ALTER COLUMN fulltext_top_k SET DEFAULT 16,
    ALTER COLUMN rrf_k SET DEFAULT 8;

UPDATE knowledge_base_retrieval_settings
SET top_k = 4,
    vector_top_k = 16,
    fulltext_top_k = 16,
    rrf_k = 8,
    updated_at = now()
WHERE top_k = 5
  AND vector_top_k = 20
  AND fulltext_top_k = 20
  AND rrf_k = 10;

ALTER TABLE knowledge_base_retrieval_settings
    ALTER COLUMN rrf_k SET DEFAULT 10;

UPDATE knowledge_base_retrieval_settings
SET rrf_k = 10,
    updated_at = now()
WHERE rrf_k = 20;

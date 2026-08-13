DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM knowledge_files AS file
        LEFT JOIN milvus_text_cutover_audits AS audit
          ON audit.knowledge_file_id = file.id
         AND audit.user_id = file.user_id
         AND audit.index_version = file.index_version
        WHERE file.deleted_at IS NULL
          AND file.status = 'indexed'
          AND audit.knowledge_file_id IS NULL
    ) THEN
        RAISE EXCEPTION
            'Milvus text cutover audit is incomplete; run rebuild_milvus_text_collections.py before dropping PostgreSQL text tables';
    END IF;
END $$;

DROP TABLE IF EXISTS knowledge_file_chunks;
DROP TABLE IF EXISTS knowledge_file_chunk_parents;

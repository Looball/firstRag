CREATE TABLE IF NOT EXISTS knowledge_file_ocr_history (
    id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    knowledge_file_id UUID NOT NULL REFERENCES knowledge_files(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    index_version INTEGER NOT NULL,
    ocr_attempt INTEGER NOT NULL,
    source_job_id UUID REFERENCES vector_index_jobs(id) ON DELETE SET NULL,
    trigger VARCHAR(64) NOT NULL,
    ocr_engine VARCHAR(64) NOT NULL,
    ocr_confidence DOUBLE PRECISION,
    ocr_quality VARCHAR(16) NOT NULL,
    ocr_word_count INTEGER NOT NULL,
    ocr_text TEXT NOT NULL,
    ocr_text_sha256 CHAR(64) NOT NULL,
    ocr_text_source VARCHAR(32) NOT NULL,
    correction_revision INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT knowledge_file_ocr_history_page_check
        CHECK (page_number >= 1),
    CONSTRAINT knowledge_file_ocr_history_version_check
        CHECK (index_version >= 0),
    CONSTRAINT knowledge_file_ocr_history_attempt_check
        CHECK (ocr_attempt >= 1),
    CONSTRAINT knowledge_file_ocr_history_confidence_check
        CHECK (
            ocr_confidence IS NULL
            OR (ocr_confidence >= 0 AND ocr_confidence <= 100)
        ),
    CONSTRAINT knowledge_file_ocr_history_word_count_check
        CHECK (ocr_word_count >= 0),
    CONSTRAINT knowledge_file_ocr_history_quality_check
        CHECK (ocr_quality IN ('good', 'low', 'unknown')),
    CONSTRAINT knowledge_file_ocr_history_text_check
        CHECK (char_length(ocr_text) <= 100000),
    CONSTRAINT knowledge_file_ocr_history_hash_check
        CHECK (ocr_text_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT knowledge_file_ocr_history_correction_revision_check
        CHECK (correction_revision IS NULL OR correction_revision >= 1),
    UNIQUE (user_id, knowledge_file_id, page_number, index_version)
);

CREATE INDEX IF NOT EXISTS idx_pdf_ocr_history_page_created
ON knowledge_file_ocr_history (
    user_id,
    knowledge_file_id,
    page_number,
    created_at DESC
);

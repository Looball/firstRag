CREATE TABLE IF NOT EXISTS knowledge_file_ocr_corrections (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    knowledge_file_id UUID NOT NULL REFERENCES knowledge_files(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    original_ocr_text TEXT NOT NULL,
    corrected_text TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, knowledge_file_id, page_number),
    CONSTRAINT knowledge_file_ocr_corrections_page_check
        CHECK (page_number >= 1),
    CONSTRAINT knowledge_file_ocr_corrections_text_check
        CHECK (
            char_length(btrim(corrected_text)) BETWEEN 1 AND 50000
        ),
    CONSTRAINT knowledge_file_ocr_corrections_revision_check
        CHECK (revision >= 1)
);

CREATE INDEX IF NOT EXISTS idx_pdf_ocr_corrections_file
ON knowledge_file_ocr_corrections (user_id, knowledge_file_id);

ALTER TABLE knowledge_file_ocr_history
    ADD COLUMN IF NOT EXISTS ocr_strategy VARCHAR(64) NOT NULL
        DEFAULT 'baseline_auto',
    ADD COLUMN IF NOT EXISTS ocr_preprocessing VARCHAR(32) NOT NULL
        DEFAULT 'color',
    ADD COLUMN IF NOT EXISTS ocr_psm INTEGER NOT NULL DEFAULT 3,
    ADD COLUMN IF NOT EXISTS ocr_rotation INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS ocr_candidate_count INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS ocr_candidate_results JSONB NOT NULL
        DEFAULT '[]'::jsonb;

ALTER TABLE knowledge_file_ocr_history
    ADD CONSTRAINT knowledge_file_ocr_history_psm_check
        CHECK (ocr_psm BETWEEN 0 AND 13),
    ADD CONSTRAINT knowledge_file_ocr_history_rotation_check
        CHECK (ocr_rotation IN (0, 90, 180, 270)),
    ADD CONSTRAINT knowledge_file_ocr_history_candidate_count_check
        CHECK (ocr_candidate_count BETWEEN 0 AND 6),
    ADD CONSTRAINT knowledge_file_ocr_history_candidate_results_check
        CHECK (jsonb_typeof(ocr_candidate_results) = 'array');

ALTER TABLE milvus_text_cutover_audits
DROP CONSTRAINT IF EXISTS milvus_text_cutover_audits_index_version_check;

ALTER TABLE milvus_text_cutover_audits
ADD CONSTRAINT milvus_text_cutover_audits_index_version_check
CHECK (index_version >= 0);

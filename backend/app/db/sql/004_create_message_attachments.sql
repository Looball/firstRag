CREATE TABLE IF NOT EXISTS message_attachments (
    id UUID PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    message_id BIGINT REFERENCES messages(id) ON DELETE CASCADE,
    original_name TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    file_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'uploaded',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT message_attachments_mime_type_check
        CHECK (mime_type IN ('image/png', 'image/jpeg', 'image/webp')),
    CONSTRAINT message_attachments_size_bytes_check
        CHECK (size_bytes > 0),
    CONSTRAINT message_attachments_status_check
        CHECK (status IN ('uploaded', 'attached', 'deleted'))
);

CREATE INDEX IF NOT EXISTS idx_message_attachments_user_conversation
ON message_attachments (user_id, conversation_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_message_attachments_message_id
ON message_attachments (message_id);

CREATE INDEX IF NOT EXISTS idx_message_attachments_user_hash
ON message_attachments (user_id, file_hash);

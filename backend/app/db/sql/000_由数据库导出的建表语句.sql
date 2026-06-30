create table users
(
    id            bigserial
        primary key,
    username      text                                   not null
        unique,
    password_hash text                                   not null,
    created_at    timestamp with time zone default now() not null
);

alter table users
    owner to bing;

create table conversations
(
    id                uuid                     default gen_random_uuid() not null
        primary key,
    user_id           bigint                                             not null,
    title             text,
    created_at        timestamp with time zone default now()             not null,
    updated_at        timestamp with time zone default now()             not null,
    deleted_at        timestamp with time zone,
    knowledge_base_id uuid                                               not null
);

alter table conversations
    owner to bing;

create index idx_conversations_knowledge_base_id
    on conversations (knowledge_base_id);

create index idx_conversations_user_knowledge_base
    on conversations (user_id, knowledge_base_id)
    where (deleted_at IS NULL);

create table messages
(
    id              bigserial
        primary key,
    conversation_id uuid                                               not null,
    role            text                                               not null,
    content         text                                               not null,
    created_at      timestamp with time zone default now()             not null,
    status          text                     default 'completed'::text not null
        constraint messages_status_check
            check (status = ANY (ARRAY ['generating'::text, 'completed'::text, 'failed'::text, 'cancelled'::text])),
    error_message   text,
    completed_at    timestamp with time zone,
    sources         jsonb                    default '[]'::jsonb       not null,
    retrieval       jsonb                    default '{}'::jsonb       not null
);

alter table messages
    owner to bing;

create index idx_messages_conversation_status
    on messages (conversation_id, status, created_at, id);

create table knowledge_bases
(
    id         uuid                     default gen_random_uuid() not null
        primary key,
    user_id    bigint                                             not null,
    name       text                                               not null,
    is_default boolean                  default false             not null,
    created_at timestamp with time zone default now()             not null,
    updated_at timestamp with time zone default now()             not null,
    deleted_at timestamp with time zone
);

alter table knowledge_bases
    owner to bing;

create unique index uq_knowledge_bases_user_default
    on knowledge_bases (user_id)
    where ((is_default = true) AND (deleted_at IS NULL));

create table knowledge_files
(
    id            uuid                     default gen_random_uuid() not null
        primary key,
    user_id       bigint                                             not null,
    original_name text                                               not null,
    storage_path  text                                               not null,
    mime_type     text,
    size_bytes    bigint,
    file_hash     text                                               not null,
    status        text                     default 'pending'::text   not null,
    error_message text,
    created_at    timestamp with time zone default now()             not null,
    updated_at    timestamp with time zone default now()             not null,
    deleted_at    timestamp with time zone,
    index_version integer                  default 0                 not null
);

alter table knowledge_files
    owner to bing;

create unique index uq_knowledge_files_user_hash
    on knowledge_files (user_id, file_hash)
    where (deleted_at IS NULL);

create table knowledge_base_files
(
    knowledge_base_id uuid                                   not null,
    knowledge_file_id uuid                                   not null,
    created_at        timestamp with time zone default now() not null,
    primary key (knowledge_base_id, knowledge_file_id)
);

alter table knowledge_base_files
    owner to bing;

create index idx_knowledge_base_files_base_id
    on knowledge_base_files (knowledge_base_id);

create index idx_knowledge_base_files_file_id
    on knowledge_base_files (knowledge_file_id);

create table knowledge_file_chunks
(
    chunk_id          text                                         not null
        primary key,
    user_id           integer                                      not null
        references users
            on delete cascade,
    knowledge_file_id uuid                                         not null
        references knowledge_files
            on delete cascade,
    chunk_index       integer                                      not null,
    content           text                                         not null,
    metadata          jsonb                    default '{}'::jsonb not null,
    created_at        timestamp with time zone default now()       not null,
    updated_at        timestamp with time zone default now()       not null,
    index_version     integer                  default 0           not null
);

alter table knowledge_file_chunks
    owner to bing;

create index idx_knowledge_file_chunks_user_file
    on knowledge_file_chunks (user_id, knowledge_file_id);

create index idx_knowledge_file_chunks_search
    on knowledge_file_chunks using gin (to_tsvector('simple'::regconfig, content));

create index idx_knowledge_file_chunks_content_trgm
    on knowledge_file_chunks using gin (content gin_trgm_ops);

create index idx_knowledge_file_chunks_file_version
    on knowledge_file_chunks (user_id, knowledge_file_id, index_version);

create table vector_index_jobs
(
    id                uuid                                            not null
        primary key,
    user_id           bigint                                          not null,
    knowledge_file_id uuid                                            not null
        references knowledge_files
            on delete cascade,
    knowledge_base_id uuid
                                                                      references knowledge_bases
                                                                          on delete set null,
    status            text                     default 'queued'::text not null
        constraint vector_index_jobs_status_check
            check (status = ANY
                   (ARRAY ['queued'::text, 'processing'::text, 'succeeded'::text, 'failed'::text, 'cancelled'::text])),
    priority          integer                  default 100            not null,
    attempts          integer                  default 0              not null,
    max_attempts      integer                  default 3              not null,
    locked_by         text,
    locked_at         timestamp with time zone,
    started_at        timestamp with time zone,
    finished_at       timestamp with time zone,
    error_message     text,
    result            jsonb,
    created_at        timestamp with time zone default now()          not null,
    updated_at        timestamp with time zone default now()          not null,
    available_at      timestamp with time zone default now()          not null,
    heartbeat_at      timestamp with time zone,
    index_version     integer                  default 0              not null
);

alter table vector_index_jobs
    owner to bing;

create index idx_vector_index_jobs_status_created
    on vector_index_jobs (status, priority, created_at);

create index idx_vector_index_jobs_user_file
    on vector_index_jobs (user_id, knowledge_file_id);

create unique index idx_vector_index_jobs_active_file
    on vector_index_jobs (user_id, knowledge_file_id)
    where (status = ANY (ARRAY ['queued'::text, 'processing'::text]));

create index idx_vector_index_jobs_ready
    on vector_index_jobs (status, available_at, priority, created_at);

create table user_llm_settings
(
    user_id                integer                                           not null
        primary key
        references users
            on delete cascade,
    credential_mode        text                     default 'platform'::text not null
        constraint user_llm_settings_credential_mode_check
            check (credential_mode = ANY (ARRAY ['platform'::text, 'user'::text])),
    provider               text,
    model                  text,
    base_url               text,
    api_key_ciphertext     text,
    encryption_key_version smallint                 default 1                not null,
    temperature            numeric(3, 2)            default 0.20             not null
        constraint user_llm_settings_temperature_check
            check ((temperature >= (0)::numeric) AND (temperature <= (2)::numeric)),
    max_tokens             integer                  default 8000             not null
        constraint user_llm_settings_max_tokens_check
            check (max_tokens > 0),
    timeout_seconds        numeric(8, 2)            default 60               not null
        constraint user_llm_settings_timeout_seconds_check
            check (timeout_seconds > (0)::numeric),
    max_retries            smallint                 default 2                not null
        constraint user_llm_settings_max_retries_check
            check (max_retries >= 0),
    created_at             timestamp with time zone default now()            not null,
    updated_at             timestamp with time zone default now()            not null,
    api_key_hint           text,
    constraint user_llm_settings_mode_check
        check (((credential_mode = 'platform'::text) AND (api_key_ciphertext IS NULL)) OR
               ((credential_mode = 'user'::text) AND (provider IS NOT NULL) AND (model IS NOT NULL) AND
                (api_key_ciphertext IS NOT NULL)))
);

alter table user_llm_settings
    owner to bing;

create table user_llm_provider_credentials
(
    user_id                integer                                not null
        references users
            on delete cascade,
    provider               text                                   not null,
    api_key_ciphertext     text                                   not null,
    api_key_hint           text,
    encryption_key_version smallint                 default 1     not null,
    created_at             timestamp with time zone default now() not null,
    updated_at             timestamp with time zone default now() not null,
    primary key (user_id, provider)
);

alter table user_llm_provider_credentials
    owner to bing;

create table knowledge_base_retrieval_settings
(
    knowledge_base_id      uuid                                          not null
        primary key
        references knowledge_bases
            on delete cascade,
    user_id                integer                                       not null
        references users
            on delete cascade,
    retrieval_mode         text                     default 'auto'::text not null
        constraint knowledge_base_retrieval_settings_mode_check
            check (retrieval_mode = ANY (ARRAY ['auto'::text, 'always'::text, 'never'::text])),
    enable_query_router    boolean                  default true         not null,
    enable_rerank          boolean                  default true         not null,
    top_k                  integer                  default 5            not null
        constraint knowledge_base_retrieval_settings_top_k_check
            check ((top_k >= 1) AND (top_k <= 20)),
    vector_top_k           integer                  default 20           not null
        constraint knowledge_base_retrieval_settings_vector_top_k_check
            check ((vector_top_k >= 1) AND (vector_top_k <= 100)),
    fulltext_top_k         integer                  default 20           not null
        constraint knowledge_base_retrieval_settings_fulltext_top_k_check
            check ((fulltext_top_k >= 1) AND (fulltext_top_k <= 100)),
    rrf_k                  integer                  default 20           not null
        constraint knowledge_base_retrieval_settings_rrf_k_check
            check ((rrf_k >= 1) AND (rrf_k <= 100)),
    rerank_score_threshold numeric(6, 3)            default 0.000        not null
        constraint knowledge_base_retrieval_settings_threshold_check
            check ((rerank_score_threshold >= '-20.000'::numeric) AND (rerank_score_threshold <= 20.000)),
    created_at             timestamp with time zone default now()        not null,
    updated_at             timestamp with time zone default now()        not null
);

alter table knowledge_base_retrieval_settings
    owner to bing;

create index idx_kb_retrieval_settings_user
    on knowledge_base_retrieval_settings (user_id);



# 数据结构说明

本文汇总 PostgreSQL 表、Pydantic 请求模型和主要运行时结构。

## PostgreSQL 核心表

| 表 | 用途 |
| --- | --- |
| `users` | 用户账号，保存 argon2 密码哈希。 |
| `knowledge_bases` | 用户知识库，每个用户有默认知识库。 |
| `knowledge_files` | 知识文件元数据，包含软删除、SHA-256 去重和索引状态。 |
| `knowledge_base_files` | 知识库与文件多对多关联。 |
| `knowledge_file_chunks` | 文本分块正文、metadata、全文检索索引和索引版本。 |
| `conversations` | 会话，属于某个知识库。 |
| `messages` | 会话消息，保存 role、content、status、sources、retrieval。 |
| `vector_index_jobs` | 向量化任务队列，支持租约、重试、取消和并发 worker。 |
| `user_llm_settings` | 当前用户生效模型设置。 |
| `user_llm_provider_credentials` | 按厂商保存的加密 API Key。 |

迁移 SQL 位于 `backend/app/db/sql/`。

## Pydantic 请求模型

| 模型 | 字段 | 用途 |
| --- | --- | --- |
| `RegisterRequest` | `username`, `password` | 注册。 |
| `LoginRequest` | `username`, `password` | 登录。 |
| `ChatRequest` | `conversation_id`, `knowledge_base_id`, `message` | 聊天。 |
| `CreateConversationRequest` | `title` | 新建会话。 |
| `RenameConversationRequest` | `title` | 重命名会话。 |
| `CreateKnowledgeBaseRequest` | `name` | 新建知识库，1 到 50 字符。 |
| `UpdateUserLLMSettingsRequest` | `credential_mode`, `provider`, `model`, `base_url`, `api_key`, `temperature`, `max_tokens`, `timeout_seconds`, `max_retries` | 更新或测试用户模型设置。 |

## 消息结构

`messages.role` 当前使用：

- `user`
- `assistant`

`messages.status` 当前使用：

- `generating`
- `completed`
- `failed`
- `cancelled`

`messages.sources` 保存引用来源数组，常见字段包括：

- `index`
- `file_id`
- `file_name`
- `chunk_index`
- `retrieval_sources`
- `vector_score`
- `fulltext_score`
- `rrf_score`
- `rerank_score`

`messages.retrieval` 保存本轮检索诊断，常见字段包括：

- `need_retrieval`
- `rewritten_query`
- `reason`
- `retrieved_count`
- `source_count`
- `retrieval_sources`
- `vector_degraded`
- `diagnostics`

## 向量化任务状态

`vector_index_jobs.status` 当前使用：

- `queued`
- `processing`
- `succeeded`
- `failed`
- `cancelled`

`knowledge_files.status` 与任务状态共同决定前端展示的文件索引状态。

## 凭据安全结构

用户 API Key 只保存密文和脱敏提示：

- `api_key_ciphertext`
- `api_key_hint`
- `encryption_key_version`

响应中只允许返回 `has_api_key` 和 `api_key_hint`，禁止返回完整 Key。

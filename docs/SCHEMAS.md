# 数据结构说明

本文汇总 PostgreSQL 表、Pydantic 请求模型和主要运行时结构。

## PostgreSQL 核心表

| 表 | 用途 |
| --- | --- |
| `users` | 用户账号，保存 argon2 密码哈希。 |
| `knowledge_bases` | 用户知识库，每个用户有默认知识库。 |
| `knowledge_base_retrieval_settings` | 知识库级 RAG 检索策略设置。 |
| `knowledge_files` | 知识文件元数据，包含软删除、SHA-256 去重和索引状态。 |
| `knowledge_base_files` | 知识库与文件多对多关联。 |
| `knowledge_file_chunks` | 文本分块正文、metadata、全文检索索引和索引版本。 |
| `conversations` | 会话，属于某个知识库。 |
| `messages` | 会话消息，保存 role、content、status、sources、retrieval。 |
| `message_feedback` | 用户对 assistant message 的回答质量反馈，使用 `user_id + message_id` 唯一约束，不使用外键。 |
| `message_source_feedback` | 用户对 assistant message 单个引用来源的有用性反馈，使用 `user_id + message_id + source_index` 唯一约束，不使用外键。 |
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
| `MessageFeedbackRequest` | `rating`, `reason`, `note` | 创建或更新助手消息质量反馈。 |
| `MessageSourceFeedbackRequest` | `rating`, `note` | 创建或更新助手消息引用来源反馈。 |
| `CreateKnowledgeBaseRequest` | `name` | 新建知识库，1 到 50 字符。 |
| `UpdateRetrievalSettingsRequest` | `retrieval_mode`, `enable_query_router`, `enable_rerank`, `top_k`, `vector_top_k`, `fulltext_top_k`, `rrf_k`, `rerank_score_threshold` | 更新知识库检索策略。 |
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
- `final_need_retrieval`
- `llm_need_retrieval`
- `rewritten_query`
- `reason`
- `llm_reason`
- `override_applied`
- `override_reason`
- `retrieved_count`
- `source_count`
- `retrieval_sources`
- `vector_degraded`
- `diagnostics`

其中 `need_retrieval` 继续表示最终是否检索，保留给旧前端兼容；
`llm_need_retrieval` 表示 Router LLM 的原始判断；
`override_applied` 与 `override_reason` 表示后端规则是否覆盖了 LLM 判断，
例如问题关键词命中当前知识库文件画像时强制检索。

## 消息反馈结构

`message_feedback.rating` 当前使用：

- `positive`
- `negative`

`message_feedback.reason` 当前使用：

- `irrelevant_sources`
- `missing_answer`
- `hallucination`
- `outdated_or_wrong`
- `too_slow`
- `format_issue`
- `other`

历史消息接口会把当前用户对消息的反馈序列化到 `messages[].feedback`：

```json
{
  "id": "7",
  "rating": "negative",
  "reason": "missing_answer",
  "note": "没有回答核心问题",
  "metadata": {
    "status": "completed"
  }
}
```

`message_source_feedback.rating` 当前使用：

- `useful`
- `irrelevant`

历史消息接口会把当前用户对引用来源的反馈附加到 `messages[].sources[].feedback`：

```json
{
  "id": "11",
  "source_index": 1,
  "knowledge_file_id": null,
  "chunk_index": 2,
  "rating": "useful",
  "note": null,
  "metadata": {
    "file_name": "民事诉讼法.pdf"
  }
}
```

## Eval Case 草稿结构

真实问答可通过 `GET /chat/messages/{message_id}/eval-case-draft` 导出为草稿。草稿顶层字段尽量兼容 `docs/evals/rag_eval_cases.jsonl`：

- `id`
- `knowledge_base_name`
- `question`
- `retrieval_settings`
- `expect_retrieval`
- `min_sources`
- `expected_files`
- `expected_keywords`
- `expected_reason_keywords`
- `expected_diagnostics`

额外的 `draft_metadata` 用于人工审核，包含原始 answer、feedback、retrieval diagnostics 和 sources，不作为正式 eval 断言字段。

## 质量看板结构

`GET /chat/quality-dashboard` 返回当前用户范围内的聚合数据：

- `window_days`：统计窗口天数。
- `has_feedback`：窗口内是否存在 message 或 source feedback。
- `message_feedback`：回答级反馈总数、正负反馈数、负反馈率和原因分布。
- `source_feedback`：引用级反馈总数、有用/无关数、无关率和无关来源排行。
- `retrieval`：窗口内 completed assistant message 数、平均 sources 数和平均首 token 等待。

统计接口必须通过 `conversations.user_id` 约束当前用户，不能跨用户聚合。

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

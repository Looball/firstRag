# API 接口说明

后端基地址默认是 `http://127.0.0.1:8000`。除注册、登录外，业务接口均需要：

```http
Authorization: Bearer <access_token>
```

成功响应约定为 `{"success": true, ...}`。资源不存在或不属于当前用户时返回 `404`。

请求超过后端限流时返回 `429`，并携带 `Retry-After` 响应头。Next.js API proxy 会保留该响应头，前端按剩余秒数禁用对应操作并显示倒计时，不会自动重放请求。默认 Docker/生产环境使用 Redis 分布式 sliding-window 限流，多 backend 实例共享计数；登录失败、聊天、上传、向量化提交和模型测试的阈值由 `.env` 中的 `LOGIN_FAILURE_RATE_LIMIT_*`、`*_RATE_LIMIT_MAX_REQUESTS` 和 `API_RATE_LIMIT_WINDOW_SECONDS` 配置控制。

## 系统健康

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/health` | 返回后端进程和 Redis 基础设施的安全健康摘要。 |

`GET /health` 不需要认证，只返回可公开的健康状态，不返回 Redis URL、密码、JWT、数据库连接串或用户数据。Redis 当前用于基础设施健康检查、RAG 热点缓存和后端分布式限流；worker 运行态迁移由后续 Redis 专项任务承接。

```json
{
  "success": true,
  "status": "healthy",
  "dependencies": {
    "redis": {
      "enabled": true,
      "configured": true,
      "is_healthy": true,
      "status": "healthy"
    }
  }
}
```

## 认证

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/register` | 注册用户，并创建默认知识库。 |
| `POST` | `/login` | 登录并返回 Bearer Token。 |

`/register` 受 `ALLOW_PUBLIC_REGISTRATION` 控制。默认 `true` 保持本地开发体验；公开 demo 可设为 `false`，此时注册接口不会创建用户，并返回：

```json
{
  "detail": "当前演示环境暂不开放注册，请使用已提供的账号登录。"
}
```

请求体：

```json
{
  "username": "alice",
  "password": "password"
}
```

登录失败达到配置阈值后会返回：

```json
{
  "detail": "登录失败次数过多，请稍后再试。"
}
```

## 聊天

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/chat` | SSE 流式聊天回答。 |
| `POST` | `/chat/attachments` | 上传当前会话的聊天图片附件，支持 `multipart/form-data`。 |
| `GET` | `/chat/attachments/{attachment_id}/content` | 读取当前用户自己的聊天图片附件内容。 |

请求体：

```json
{
  "conversation_id": "uuid",
  "knowledge_base_id": "uuid",
  "message": "问题内容",
  "attachment_ids": ["uuid"]
}
```

`attachment_ids` 可省略或传空数组。发送图片时，前端先调用
`POST /chat/attachments?conversation_id={conversation_id}` 上传图片，再把返回的附件
ID 随聊天请求提交。当前支持 `image/png`、`image/jpeg` 和 `image/webp`；单轮最多
`CHAT_IMAGE_MAX_FILES` 张，单张不超过 `CHAT_IMAGE_MAX_FILE_SIZE_BYTES`，总大小不超过
`CHAT_IMAGE_MAX_TOTAL_BYTES`。当当前用户的聊天模型不支持 vision 输入时，`POST /chat`
返回 `400`，不会创建本轮半成品消息。

聊天图片附件只用于当前会话消息的多模态提问，不会自动进入知识库向量化链路。
如果需要把图片作为长期知识资料检索，请通过知识文件上传入口上传 PNG、JPEG 或 WebP 图片。

附件上传响应：

```json
{
  "success": true,
  "attachments": [
    {
      "id": "uuid",
      "original_name": "chart.png",
      "mime_type": "image/png",
      "size_bytes": 1024,
      "content_url": "/chat/attachments/uuid/content",
      "created_at": "2026-07-04T12:00:00+08:00"
    }
  ]
}
```

附件响应只返回安全 metadata 和读取 URL，不返回服务器本地存储路径或图片 base64。

## 知识库

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/chat/knowledge-bases` | 当前用户知识库列表。 |
| `GET` | `/chat/knowledge-bases/trash` | 当前用户知识库回收站。 |
| `POST` | `/chat/knowledge-base` | 新建知识库。 |
| `PATCH` | `/chat/knowledge-base/{knowledge_base_id}` | 重命名活动知识库。 |
| `DELETE` | `/chat/knowledge-base/{knowledge_base_id}` | 将非默认知识库移入回收站。 |
| `POST` | `/chat/knowledge-base/{knowledge_base_id}/restore` | 恢复回收站中的知识库。 |
| `GET` | `/chat/knowledge-base/{knowledge_base_id}/retrieval-settings` | 获取知识库检索策略设置。 |
| `PATCH` | `/chat/knowledge-base/{knowledge_base_id}/retrieval-settings` | 保存知识库检索策略设置。 |
| `GET` | `/chat/knowledge-base/{knowledge_base_id}/files` | 知识库文件列表。 |
| `POST` | `/chat/knowledge-base/{knowledge_base_id}/files/{knowledge_file_id}` | 关联已有文件。 |
| `DELETE` | `/chat/knowledge-base/{knowledge_base_id}/files/{knowledge_file_id}` | 解除文件关联。 |

新建知识库：

```json
{
  "name": "默认知识库"
}
```

知识库删除采用软删除：知识库及其原会话会从活动列表隐藏，但文件记录、磁盘文件和索引仍保留，恢复后原会话和文件关联重新可见。默认知识库不能删除；跨用户、已删除或不存在资源返回 `404`。

## 知识文件

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/chat/knowledge-base/{knowledge_base_id}/files` | 上传文件，支持 `multipart/form-data`。 |
| `GET` | `/chat/knowledge-files` | 当前用户所有知识文件。 |
| `DELETE` | `/chat/knowledge-files/{knowledge_file_id}` | 永久删除用户知识文件及其全部索引数据。 |

上传字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `files` | file[] | 一个或多个文件。 |
| `description` | string | 可选说明。 |
| `auto_index` | boolean | 是否上传后提交向量化任务。 |

上传入口当前支持 `.pdf`、`.docx`、`.md`、`.txt`、`.png`、`.jpg/.jpeg` 和 `.webp`。不支持的扩展名、明显不匹配的 MIME 类型或伪装成图片的无效文件头会返回 `400`，不会创建无效文件记录或向量化任务。

图片知识文件上传成功后仍然走异步向量化。worker 会使用当前登录用户保存的 vision-capable 聊天模型把图片解析为可检索 Markdown，再切分为 chunk，写入 PostgreSQL full-text chunks 和 Chroma。若用户未配置聊天模型，或当前模型不支持 vision，单文件/整库向量化提交会返回 `400`；通过 `auto_index=true` 自动入队的任务会在 worker 阶段失败，并返回安全的恢复提示。

上传同时受单文件大小、用户文件数量和用户总容量配额限制：

| 配置 | 说明 |
| --- | --- |
| `MAX_UPLOAD_FILE_SIZE_BYTES` | 单个文件大小上限。 |
| `USER_UPLOAD_MAX_FILES` | 当前用户未删除文件数量上限，`0` 表示关闭。 |
| `USER_UPLOAD_MAX_BYTES` | 当前用户未删除文件总容量上限，`0` 表示关闭。 |

超过单文件或用户配额时返回 `413`，`detail` 会说明当前占用、上限或建议删除不需要的文件后重试。同一用户重复上传相同内容时会复用已有文件，不重复计入全局文件数量和容量。

`DELETE /chat/knowledge-files/{knowledge_file_id}` 是不可恢复操作。后端使用单文件 advisory lock 与正在执行的 indexing 串行化，取消 active jobs，并清理所有知识库关联、Chroma vectors、PostgreSQL chunks、历史消息中的对应 source、source feedback、任务记录和 `uploads/` 下的磁盘文件。删除接口会拒绝不在允许上传目录内的异常存储路径。

## 向量化

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/chat/knowledge-files/{knowledge_file_id}/vectors` | 提交单文件向量化任务。 |
| `POST` | `/chat/knowledge-base/{knowledge_base_id}/vectors` | 提交知识库全部文件向量化任务。 |
| `GET` | `/chat/vector-index-jobs/health` | 当前用户任务队列健康状态。 |
| `GET` | `/chat/vector-index-jobs/{job_id}` | 查询任务状态。 |
| `DELETE` | `/chat/knowledge-files/{knowledge_file_id}/vectors` | 删除单文件向量化存储。 |

`POST /chat/knowledge-base/{knowledge_base_id}/vectors` 受 `VECTOR_INDEX_MAX_BATCH_FILES` 限制，超过单次批量提交上限时返回 `413`，避免一次性提交过多 vector index job。

`GET /chat/vector-index-jobs/health` 会合并 PostgreSQL 持久任务统计和 Redis worker 运行态，返回队列总览、在线 worker、最近心跳和提示，供前端判断任务是否可能卡住。Redis 不可用时仍会返回 PostgreSQL 队列状态，并在 `worker.redis_available` 和 `worker.hint` 中提示降级：

```json
{
  "success": true,
  "worker": {
    "status": "attention_needed",
    "is_healthy": false,
    "has_recent_activity": false,
    "hint": "存在排队任务长时间未被领取，可能 worker 未启动。",
    "stale_queued": 1,
    "stale_processing": 0,
    "oldest_active_seconds": 1200,
    "oldest_queued_seconds": 1200,
    "oldest_processing_seconds": null,
    "online_count": 0,
    "redis_enabled": true,
    "redis_available": true,
    "redis_status": "healthy",
    "last_heartbeat_at": null,
    "last_heartbeat_age_seconds": null,
    "heartbeat_ttl_seconds": 30,
    "active_file_lock_count": 0
  },
  "queue": {
    "status": "stuck",
    "total": 3,
    "active": 1,
    "queued": 1,
    "processing": 0,
    "succeeded": 2,
    "failed": 0,
    "cancelled": 0
  }
}
```

文件列表中的 `latest_index_job` 也会携带单文件提示：

```json
{
  "status": "queued",
  "active_seconds": 1200,
  "is_stale": true,
  "worker_hint": "该文件向量化任务长时间排队，可能 worker 未启动。",
  "failure_type": null,
  "failure_hint": null,
  "can_retry": false
}
```

向量化失败时，`latest_index_job` 会额外返回可恢复建议：

```json
{
  "status": "failed",
  "error_message": "文件解析失败",
  "failure_type": "parse_error",
  "failure_hint": "文件解析失败。请确认文件内容可读取，必要时转为 PDF、Markdown、TXT 或支持的图片格式后重新上传。",
  "can_retry": true
}
```

`error_message` 是面向用户的安全摘要，不返回本地路径、数据库连接串、API Key
或底层异常全文；详细异常仅保留在后端日志中。前端应优先使用
`failure_type`、`failure_hint`、`worker_hint` 和 `can_retry` 展示恢复动作。

当前稳定的 `failure_type` 包括：

| 类型 | 说明 |
| --- | --- |
| `unsupported_file_type` | 文件类型不在当前解析链路支持范围内。 |
| `empty_document` | 文件可读取，但没有解析出可入库文本。 |
| `image_parse_error` | 图片知识文件无法通过当前用户的 vision 聊天模型解析。 |
| `parse_error` | 文件解析、编码或文本分块失败。 |
| `embedding_error` | Embedding provider 调用失败。 |
| `vector_store_error` | Chroma/vector_db 写入或查询失败。 |
| `chunk_write_error` | PostgreSQL 文本 chunk 写入失败。 |
| `database_error` | 数据库连接、SQL 或迁移相关失败。 |
| `task_timeout` | 向量化任务超时或租约过期。 |
| `stale_job` | 任务版本已过期。 |
| `unknown_error` | 未能归入以上类型的失败。 |

## 会话

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/chat/conversations` | 当前用户所有知识库下的会话列表，兼容旧前端代理。 |
| `POST` | `/chat/conversation` | 新建会话，兼容旧前端代理；可传 `knowledge_base_id`，省略时使用默认知识库。 |
| `PATCH` | `/chat/conversation/{conversation_id}` | 按会话 ID 重命名，兼容旧前端代理。 |
| `DELETE` | `/chat/conversation/{conversation_id}` | 按会话 ID 软删除，兼容旧前端代理。 |
| `GET` | `/chat/knowledge-bases/{knowledge_base_id}/conversations` | 知识库会话列表。 |
| `POST` | `/chat/knowledge-bases/{knowledge_base_id}/conversations` | 新建会话。 |
| `PATCH` | `/chat/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}` | 重命名会话。 |
| `DELETE` | `/chat/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}` | 软删除会话。 |
| `GET` | `/chat/conversations/{conversation_id}/messages` | 会话消息列表。 |
| `GET` | `/chat/conversations/{conversation_id}/diagnostics` | 会话 RAG 诊断。 |
| `GET` | `/chat/quality-dashboard` | 当前用户回答质量和检索表现看板摘要。 |
| `POST` | `/chat/messages/{message_id}/feedback` | 创建或更新助手消息质量反馈。 |
| `POST` | `/chat/messages/{message_id}/sources/{source_index}/feedback` | 创建或更新单个引用来源反馈。 |
| `GET` | `/chat/messages/{message_id}/eval-case-draft` | 导出真实问答对应的 RAG eval case 草稿。 |

### 消息质量反馈

`POST /chat/messages/{message_id}/feedback` 只能提交当前用户可访问的 assistant message 反馈。资源不存在、跨用户或非助手消息统一返回 `404`。

请求体：

```json
{
  "rating": "negative",
  "reason": "missing_answer",
  "note": "没有回答核心问题"
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `rating` | 必填，`positive` 或 `negative`。 |
| `reason` | 可选，负反馈原因，支持 `irrelevant_sources`、`missing_answer`、`hallucination`、`outdated_or_wrong`、`too_slow`、`format_issue`、`other`。 |
| `note` | 可选，1000 字符以内的补充说明。 |

同一用户对同一消息重复提交时执行 upsert。`GET /chat/conversations/{conversation_id}/messages` 会在消息对象中返回当前用户的 `feedback` 字段，用于前端回显。

### 引用来源反馈

`POST /chat/messages/{message_id}/sources/{source_index}/feedback` 用于标记单个 source 是否有用。后端会校验 message 属于当前用户、message 是 assistant 消息，并且 `source_index` 存在于当前 `messages.sources` 数组中；不存在或无权访问时返回 `404`。

请求体：

```json
{
  "rating": "useful",
  "note": null
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `rating` | 必填，`useful` 或 `irrelevant`。 |
| `note` | 可选，1000 字符以内的补充说明；当前前端先不展示备注输入。 |

同一用户对同一消息的同一 source 重复提交时执行 upsert。历史消息接口会把当前用户的 source feedback 附加到 `messages[].sources[].feedback`，用于前端回显。

### Eval Case 草稿

`GET /chat/messages/{message_id}/eval-case-draft` 用于把真实 assistant message 导出为可人工整理的 RAG eval case 草稿。后端会读取同会话中该 assistant message 之前最近一条 user message 作为 `question`；跨用户、非助手消息或资源不存在返回 `404`，缺少可导出的用户问题时返回 `400`。

响应体：

```json
{
  "success": true,
  "draft": {
    "id": "draft_message_42",
    "knowledge_base_name": "默认知识库",
    "question": "民事诉讼法的任务是什么",
    "retrieval_settings": {
      "retrieval_mode": "auto",
      "enable_query_router": true,
      "enable_rerank": true
    },
    "expect_retrieval": true,
    "min_sources": 1,
    "expected_files": ["中华人民共和国民事诉讼法_20230901.pdf"],
    "expected_keywords": [],
    "expected_reason_keywords": [],
    "expected_diagnostics": {},
    "draft_metadata": {
      "answer": "真实回答内容",
      "feedback": {
        "rating": "negative",
        "reason": "missing_answer"
      },
      "retrieval": {},
      "sources": []
    }
  }
}
```

`draft` 外层字段尽量兼容 `docs/evals/rag_eval_cases.jsonl`，`draft_metadata` 仅作为人工审核上下文。前端当前以 JSON 文件下载，不自动写入正式 eval case。

### 质量看板

`GET /chat/quality-dashboard?days=7` 返回当前用户最近一段时间的回答质量和检索表现摘要。`days` 支持 1 到 90，超出范围会被后端归一化。

响应体：

```json
{
  "success": true,
  "window_days": 7,
  "has_feedback": true,
  "message_feedback": {
    "total": 4,
    "positive": 1,
    "negative": 3,
    "negative_rate": 0.75,
    "reason_distribution": [
      {"reason": "missing_answer", "count": 2}
    ]
  },
  "source_feedback": {
    "total": 5,
    "useful": 2,
    "irrelevant": 3,
    "irrelevant_rate": 0.6,
    "top_irrelevant_files": [
      {"file_name": "民事诉讼法.pdf", "count": 2}
    ]
  },
  "retrieval": {
    "assistant_messages": 8,
    "average_sources": 2.5,
    "average_first_token_ms": 1234.5
  }
}
```

没有反馈时 `has_feedback=false`，比例字段返回 `null`，前端应展示空状态而不是将空数据解读为质量良好。

## 用户模型设置

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/user/settings/providers` | 厂商目录和凭据状态。 |
| `POST` | `/user/settings/providers/{provider}/models` | 使用已保存凭据读取模型列表。 |
| `GET` | `/user/settings` | 当前模型设置。 |
| `PATCH` | `/user/settings` | 保存模型设置。 |
| `POST` | `/user/settings/test` | 测试当前或草稿设置。 |
| `GET` | `/user/settings/embedding-providers` | 向量厂商目录和凭据状态。 |
| `GET` | `/user/settings/embedding` | 当前向量模型设置。 |
| `PATCH` | `/user/settings/embedding` | 保存向量模型设置。 |
| `POST` | `/user/settings/embedding/test` | 测试当前或草稿向量模型设置。 |
| `GET` | `/user/settings/rerank-providers` | Rerank 厂商目录和凭据状态。 |
| `GET` | `/user/settings/rerank` | 当前 Rerank 模型设置。 |
| `PATCH` | `/user/settings/rerank` | 保存 Rerank 模型设置。 |
| `POST` | `/user/settings/rerank/test` | 测试当前或草稿 Rerank 模型设置。 |

更细的设置页协议见 `backend/frontend_llm_settings_protocol.md` 和 `backend/user_settings_api.md`。

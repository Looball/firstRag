# API 接口说明

后端基地址默认是 `http://127.0.0.1:8000`。除注册、登录外，业务接口均需要：

```http
Authorization: Bearer <access_token>
```

成功响应约定为 `{"success": true, ...}`。资源不存在或不属于当前用户时返回 `404`。

## 认证

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/register` | 注册用户，并创建默认知识库。 |
| `POST` | `/login` | 登录并返回 Bearer Token。 |

请求体：

```json
{
  "username": "alice",
  "password": "password"
}
```

## 聊天

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/chat` | SSE 流式聊天回答。 |

请求体：

```json
{
  "conversation_id": "uuid",
  "knowledge_base_id": "uuid",
  "message": "问题内容"
}
```

## 知识库

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/chat/knowledge-bases` | 当前用户知识库列表。 |
| `POST` | `/chat/knowledge-base` | 新建知识库。 |
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

## 知识文件

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/chat/knowledge-base/{knowledge_base_id}/files` | 上传文件，支持 `multipart/form-data`。 |
| `GET` | `/chat/knowledge-files` | 当前用户所有知识文件。 |

上传字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `files` | file[] | 一个或多个文件。 |
| `description` | string | 可选说明。 |
| `auto_index` | boolean | 是否上传后提交向量化任务。 |

上传入口当前支持 `.pdf`、`.docx`、`.md`、`.txt`。不支持的扩展名或明显不匹配的 MIME 类型会返回 `400`，不会创建无效文件记录或向量化任务。

## 向量化

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/chat/knowledge-files/{knowledge_file_id}/vectors` | 提交单文件向量化任务。 |
| `POST` | `/chat/knowledge-base/{knowledge_base_id}/vectors` | 提交知识库全部文件向量化任务。 |
| `GET` | `/chat/vector-index-jobs/health` | 当前用户任务队列健康状态。 |
| `GET` | `/chat/vector-index-jobs/{job_id}` | 查询任务状态。 |
| `DELETE` | `/chat/knowledge-files/{knowledge_file_id}/vectors` | 删除单文件向量化存储。 |

`GET /chat/vector-index-jobs/health` 会返回队列总览和 worker 提示，供前端判断任务是否可能卡住：

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
    "oldest_processing_seconds": null
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
  "error_message": "解析失败",
  "failure_type": "parse_error",
  "failure_hint": "文件解析失败。请确认文件内容可读取，必要时转为 PDF、Markdown 或 TXT 后重新上传。",
  "can_retry": true
}
```

当前稳定的 `failure_type` 包括：

| 类型 | 说明 |
| --- | --- |
| `unsupported_file_type` | 文件类型不在当前解析链路支持范围内。 |
| `empty_document` | 文件可读取，但没有解析出可入库文本。 |
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
| `GET` | `/chat/knowledge-bases/{knowledge_base_id}/conversations` | 知识库会话列表。 |
| `POST` | `/chat/knowledge-bases/{knowledge_base_id}/conversations` | 新建会话。 |
| `PATCH` | `/chat/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}` | 重命名会话。 |
| `DELETE` | `/chat/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}` | 软删除会话。 |
| `GET` | `/chat/conversations/{conversation_id}/messages` | 会话消息列表。 |
| `GET` | `/chat/conversations/{conversation_id}/diagnostics` | 会话 RAG 诊断。 |
| `POST` | `/chat/messages/{message_id}/feedback` | 创建或更新助手消息质量反馈。 |

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

## 用户模型设置

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/user/settings/providers` | 厂商目录和凭据状态。 |
| `POST` | `/user/settings/providers/{provider}/models` | 使用已保存凭据读取模型列表。 |
| `GET` | `/user/settings` | 当前模型设置。 |
| `PATCH` | `/user/settings` | 保存模型设置。 |
| `POST` | `/user/settings/test` | 测试当前或草稿设置。 |

更细的设置页协议见 `backend/frontend_llm_settings_protocol.md` 和 `backend/user_settings_api.md`。

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

## 向量化

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/chat/knowledge-files/{knowledge_file_id}/vectors` | 提交单文件向量化任务。 |
| `POST` | `/chat/knowledge-base/{knowledge_base_id}/vectors` | 提交知识库全部文件向量化任务。 |
| `GET` | `/chat/vector-index-jobs/health` | 当前用户任务队列健康状态。 |
| `GET` | `/chat/vector-index-jobs/{job_id}` | 查询任务状态。 |
| `DELETE` | `/chat/knowledge-files/{knowledge_file_id}/vectors` | 删除单文件向量化存储。 |

## 会话

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/chat/knowledge-bases/{knowledge_base_id}/conversations` | 知识库会话列表。 |
| `POST` | `/chat/knowledge-bases/{knowledge_base_id}/conversations` | 新建会话。 |
| `PATCH` | `/chat/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}` | 重命名会话。 |
| `DELETE` | `/chat/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}` | 软删除会话。 |
| `GET` | `/chat/conversations/{conversation_id}/messages` | 会话消息列表。 |
| `GET` | `/chat/conversations/{conversation_id}/diagnostics` | 会话 RAG 诊断。 |

## 用户模型设置

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/user/settings/providers` | 厂商目录和凭据状态。 |
| `POST` | `/user/settings/providers/{provider}/models` | 使用已保存凭据读取模型列表。 |
| `GET` | `/user/settings` | 当前模型设置。 |
| `PATCH` | `/user/settings` | 保存模型设置。 |
| `POST` | `/user/settings/test` | 测试当前或草稿设置。 |

更细的设置页协议见 `backend/frontend_llm_settings_protocol.md` 和 `backend/user_settings_api.md`。

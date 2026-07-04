# 用户模型设置接口说明

本文档供用户设置页面接入使用。所有接口都需要登录认证：

```http
Authorization: Bearer <access_token>
```

所有成功响应都包含 `success: true`。API Key 只在 `PATCH` 和临时测试请求中由前端提交，服务端不会在任何响应中回传它。

## 建议的前端交互流程

1. 页面加载时并行调用聊天、向量和 rerank 模型设置：`GET /user/settings/providers`、`GET /user/settings`、`GET /user/settings/embedding-providers`、`GET /user/settings/embedding`、`GET /user/settings/rerank-providers`、`GET /user/settings/rerank`。
2. 用 provider 目录渲染厂商下拉框；`enabled: false` 的选项应禁用或隐藏。
3. 聊天模型、向量模型和远程 rerank 模型都必须由当前登录用户配置 API Key；本地 rerank 不需要 Key。
4. 点击聊天模型“测试连接”时，调用 `POST /user/settings/test`；点击向量模型“测试连接”时，调用 `POST /user/settings/embedding/test`；点击 rerank“测试连接”时，调用 `POST /user/settings/rerank/test`。
5. 测试成功后，分别调用 `PATCH /user/settings`、`PATCH /user/settings/embedding` 和 `PATCH /user/settings/rerank` 保存设置。
6. 保存后再次读取设置或直接使用 `PATCH` 返回的 `settings` 更新页面。后续聊天、向量化、向量检索和 rerank 精排会自动使用该用户的新设置。

## 1. 获取厂商目录

```http
GET /user/settings/providers
```

响应示例：

```json
{
  "success": true,
  "providers": [
    {
      "id": "deepseek",
      "name": "DeepSeek",
      "base_url": "https://api.deepseek.com/v1",
      "requires_base_url": false,
      "enabled": true
    },
    {
      "id": "qwen",
      "name": "通义千问",
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "requires_base_url": false,
      "enabled": true
    },
    {
      "id": "openai_compatible",
      "name": "自定义 OpenAI 兼容服务",
      "base_url": null,
      "requires_base_url": true,
      "enabled": false
    }
  ]
}
```

当前内置预设：`deepseek`、`qwen`、`zhipu`、`kimi`、`doubao`、`minimax`。模型名由用户输入，前端不应假定某个模型名长期有效。

`openai_compatible` 的 `enabled` 默认是 `false`。该选项仅在服务端显式开启 `ALLOW_USER_CUSTOM_LLM_BASE_URL=true` 后可用，以避免用户借由模型地址访问服务端内网。

## 2. 获取当前设置

```http
GET /user/settings
```

聊天模型响应示例：

```json
{
  "success": true,
  "settings": {
    "credential_mode": "user",
    "provider": "qwen",
    "model": "qwen-plus",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "has_api_key": true,
    "temperature": 0.2,
    "max_tokens": 8000,
    "timeout_seconds": 60.0,
    "max_retries": 2
  }
}
```

`has_api_key` 仅表示服务端是否拥有可用 Key。页面应显示“已保存”，不能试图回填 API Key。

## 3. 保存设置

```http
PATCH /user/settings
Content-Type: application/json
```

保存 DeepSeek 聊天模型配置：

```json
{
  "credential_mode": "user",
  "provider": "deepseek",
  "model": "deepseek-v4-flash",
  "api_key": "sk-用户填写的真实密钥",
  "temperature": 0.2,
  "max_tokens": 8000,
  "timeout_seconds": 60,
  "max_retries": 2
}
```

预设厂商不需要提交 `base_url`。如果前端使用了目录接口返回的预设地址，即使提交该地址也会被服务端规范化处理。

更新已保存的个人配置时，若不修改 API Key，可省略 `api_key`：

```json
{
  "model": "deepseek-v4-flash",
  "temperature": 0.4
}
```

注意：`credential_mode` 仍保留 `user` 值用于兼容旧数据结构；新版本不再允许切换到 `platform`。首次保存必须同时提交 `credential_mode=user`、`provider`、`model` 和 `api_key`。

成功响应与 `GET /user/settings` 的 `settings` 结构一致。

## 4. 测试连接

```http
POST /user/settings/test
Content-Type: application/json
```

测试已保存配置时，发送空请求体：

```http
POST /user/settings/test
```

测试尚未保存的表单时，提交与 `PATCH` 相同的 JSON。例如：

```json
{
  "credential_mode": "user",
  "provider": "qwen",
  "model": "qwen-plus",
  "api_key": "用户当前输入的密钥",
  "temperature": 0.2,
  "max_tokens": 8000
}
```

该接口会发起最小模型请求验证地址、模型名和认证信息，但**不会保存**本次临时表单数据。

成功响应：

```json
{
  "success": true,
  "message": "模型连接测试成功"
}
```

## 字段约束与错误处理

| 字段 | 约束 |
| --- | --- |
| `credential_mode` | 新版本固定为 `user`，`platform` 仅为历史兼容值 |
| `provider` | 当前支持的厂商 ID，最长 50 个字符 |
| `model` | 最长 200 个字符 |
| `base_url` | 最长 500 个字符；仅自定义兼容服务需要 |
| `api_key` | 最长 2000 个字符；个人模式首次保存必填 |
| `temperature` | 0 到 2 |
| `max_tokens` | 1 到 100000 |
| `timeout_seconds` | 大于 0 且不超过 600 |
| `max_retries` | 0 到 10 |

| 状态码 | 前端建议 |
| --- | --- |
| `401` | 跳转登录或提示登录已过期。 |
| `400` | 直接展示 `detail`，例如缺少 API Key、不支持的厂商或自定义地址未开启。 |
| `429` | 测试或模型列表请求过于频繁；读取 `Retry-After` 后再允许重试。 |
| `502` | 仅出现在测试连接失败时；提示用户检查 Key、模型名与网络，不展示服务端异常细节。 |

## 5. 向量模型设置

向量模型 provider 目录：

```http
GET /user/settings/embedding-providers
```

响应示例：

```json
{
  "success": true,
  "providers": [
    {
      "id": "qwen",
      "name": "通义千问向量",
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "requires_base_url": false,
      "enabled": true,
      "default_model": "text-embedding-v4",
      "has_api_key": true,
      "api_key_hint": "••••abcd"
    },
    {
      "id": "zhipuai",
      "name": "智谱 Embedding",
      "base_url": null,
      "requires_base_url": false,
      "enabled": true,
      "default_model": "embedding-3",
      "has_api_key": false,
      "api_key_hint": null
    }
  ]
}
```

读取当前向量模型设置：

```http
GET /user/settings/embedding
```

保存向量模型设置：

```http
PATCH /user/settings/embedding
Content-Type: application/json
```

```json
{
  "provider": "qwen",
  "model": "text-embedding-v4",
  "dimensions": 1024,
  "api_key": "用户当前输入的向量 API Key",
  "timeout_seconds": 60,
  "max_retries": 2
}
```

测试向量模型设置：

```http
POST /user/settings/embedding/test
Content-Type: application/json
```

成功响应：

```json
{
  "success": true,
  "message": "向量模型连接测试成功",
  "provider": "qwen",
  "model": "text-embedding-v4",
  "dimensions": 1024
}
```

切换向量模型 provider、model 或 dimensions 后，已有文件需要重新向量化。后端会按用户和 embedding 配置隔离 Chroma collection，避免不同维度的向量写入同一 collection。

当前内置向量 provider：`qwen`、`zhipuai`、`openai`、`voyage`、`cohere`、`jina`、`openai_compatible`。用户可按厂商保存多份 API Key，切换回已保存厂商时可省略 `api_key`。`openai_compatible` 仅在服务端开启 `ALLOW_USER_CUSTOM_LLM_BASE_URL=true` 后可用。

## 6. Rerank 模型设置

Rerank provider 目录：

```http
GET /user/settings/rerank-providers
```

响应示例：

```json
{
  "success": true,
  "providers": [
    {
      "id": "local",
      "name": "本地 BGE Cross-Encoder",
      "base_url": null,
      "requires_base_url": false,
      "requires_api_key": false,
      "enabled": true,
      "default_model": "models/rerankers/bge-reranker-base",
      "has_api_key": true,
      "api_key_hint": null
    },
    {
      "id": "voyage",
      "name": "Voyage AI Rerank",
      "base_url": "https://api.voyageai.com/v1",
      "requires_base_url": false,
      "requires_api_key": true,
      "enabled": true,
      "default_model": "rerank-2.5",
      "has_api_key": false,
      "api_key_hint": null
    }
  ]
}
```

读取当前 rerank 设置：

```http
GET /user/settings/rerank
```

保存 rerank 设置：

```http
PATCH /user/settings/rerank
Content-Type: application/json
```

```json
{
  "provider": "voyage",
  "model": "rerank-2.5",
  "api_key": "用户当前输入的 Rerank API Key",
  "timeout_seconds": 60,
  "max_retries": 2
}
```

测试 rerank 设置：

```http
POST /user/settings/rerank/test
Content-Type: application/json
```

成功响应：

```json
{
  "success": true,
  "message": "Rerank 模型连接测试成功",
  "provider": "voyage",
  "model": "rerank-2.5",
  "top_score": 0.93
}
```

当前内置 rerank provider：`local`、`qwen`、`voyage`、`cohere`、`jina`、`openai_compatible`。`local` 使用本地 Cross-Encoder，不保存 API Key；远程 provider 的 Key 按 `(user_id, provider)` 加密保存。`qwen` 和 `openai_compatible` 需要填写 `base_url`。

## 与聊天和向量化接口的关系

`/chat` 会按当前登录用户读取聊天模型设置。个人配置的 Key 会在服务端解密后用于模型调用，前端无需也不应在聊天请求中再次传递 API Key。若已保存配置无效，`/chat` 返回 `400`，并且不会创建本轮消息记录。

向量化任务会按当前登录用户读取向量模型设置。未配置向量模型时，提交向量化任务会返回 `400`，提示先配置向量模型 API Key。

Hybrid retrieval 会按当前登录用户读取 rerank 模型设置；若远程 rerank 调用失败，会降级为 RRF 融合结果并写入 retrieval diagnostics。

完整 API Key 只允许在用户输入后随聊天模型、向量模型或 rerank 模型的保存/测试接口提交。后端仅持久化密文和 `api_key_hint`，错误响应会对提交的 Key、`api_key=...` 和 Bearer token 形态文本做脱敏处理，不回显明文。

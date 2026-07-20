# 聊天模型设置前端协议

本文档描述设置页与 Next.js 代理接口的联调协议。完整 API Key 只会在用户本次输入后随测试或保存请求提交；后端不会在任何响应中返回完整 Key。

## 认证与前端代理

所有请求携带：

```http
Authorization: Bearer <access_token>
```

前端请求路径与后端路径的映射如下：

| 前端请求 | 后端接口 | 用途 |
| --- | --- | --- |
| `GET /api/settings/providers` | `GET /user/settings/providers` | 读取厂商目录及每个厂商的 Key 状态 |
| `GET /api/settings` | `GET /user/settings` | 读取当前生效设置 |
| `PATCH /api/settings` | `PATCH /user/settings` | 保存当前生效设置 |
| `POST /api/settings` | `POST /user/settings/test` | 保存草稿后测试连接/获取模型列表 |
| `GET /api/settings/embedding-providers` | `GET /user/settings/embedding-providers` | 读取向量模型厂商目录 |
| `GET /api/settings/embedding` | `GET /user/settings/embedding` | 读取当前向量模型设置 |
| `PATCH /api/settings/embedding` | `PATCH /user/settings/embedding` | 保存当前向量模型设置 |
| `POST /api/settings/embedding` | `POST /user/settings/embedding/test` | 测试向量模型连接 |
| `GET /api/settings/rerank-providers` | `GET /user/settings/rerank-providers` | 读取 Rerank 厂商目录 |
| `GET /api/settings/rerank` | `GET /user/settings/rerank` | 读取当前 Rerank 模型设置 |
| `PATCH /api/settings/rerank` | `PATCH /user/settings/rerank` | 保存当前 Rerank 模型设置 |
| `POST /api/settings/rerank` | `POST /user/settings/rerank/test` | 测试 Rerank 模型连接 |

## 页面初始化

页面加载时并行调用：

```ts
const [
  settingsResponse,
  providersResponse,
  embeddingSettingsResponse,
  embeddingProvidersResponse,
  rerankSettingsResponse,
  rerankProvidersResponse,
] = await Promise.all([
  fetch("/api/settings", { headers: { Authorization } }),
  fetch("/api/settings/providers", { headers: { Authorization } }),
  fetch("/api/settings/embedding", { headers: { Authorization } }),
  fetch("/api/settings/embedding-providers", { headers: { Authorization } }),
  fetch("/api/settings/rerank", { headers: { Authorization } }),
  fetch("/api/settings/rerank-providers", { headers: { Authorization } }),
]);
```

`GET /api/settings` 返回当前激活厂商、模型和生成参数。`GET /api/settings/providers` 返回所有厂商及当前用户的凭据状态。

厂商目录响应示例：

```json
{
  "success": true,
  "providers": [
    {
      "id": "deepseek",
      "name": "DeepSeek",
      "base_url": "https://api.deepseek.com/v1",
      "requires_base_url": false,
      "enabled": true,
      "has_api_key": true,
      "api_key_hint": "••••abcd"
    },
    {
      "id": "qwen",
      "name": "通义千问",
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "requires_base_url": false,
      "enabled": true,
      "has_api_key": false,
      "api_key_hint": null
    }
  ]
}
```

`has_api_key` 和 `api_key_hint` 是唯一允许前端获得的凭据状态。`api_key_hint` 仅为类似 `••••abcd` 的提示，不能当作真实 Key 重新提交。

## 切换厂商

切换下拉框时，从已加载的 `providers` 状态中读取选中厂商：

```ts
const selectedProvider = providers.find(
  (item) => item.id === nextProviderId,
);

setSettings((current) => ({
  ...current,
  provider: nextProviderId,
  model: "",
  baseUrl: selectedProvider?.base_url ?? "",
  hasApiKey: selectedProvider?.has_api_key ?? false,
  apiKeyHint: selectedProvider?.api_key_hint ?? null,
}));
setApiKey("");
setModelCandidates([]);
```

关键规则：

- 切换厂商后必须清空当前模型名和模型候选列表。
- 若 `has_api_key` 为 `true`，显示“已保存（••••abcd）”，不要求用户再次输入 Key。
- 若 `has_api_key` 为 `false`，要求输入新 Key。
- 禁止调用接口以获取完整 Key；禁止将 Key 写入 `localStorage`、`sessionStorage`、URL、日志或错误上报。

若选中厂商的 `has_api_key` 为 `true`，切换完成后自动调用：

```http
POST /api/settings/providers/{provider}/models
```

它映射至 `POST /user/settings/providers/{provider}/models`，只使用该厂商
的已保存 Key 获取模型列表，不保存草稿、不改变当前聊天设置。响应示例：

```json
{
  "success": true,
  "provider": "qwen",
  "models": ["qwen-plus", "qwen-turbo"]
}
```

为避免用户快速切换时旧请求覆盖新选项，前端应使用 `AbortController` 或请求
序号，仅接受最后一次厂商切换的响应。

## 获取模型列表与测试连接

聊天模型的 API Key 区域应直接提供“获取模型列表”按钮。该动作只做模型发现，
即使页面残留旧模型名也不得把它放入请求；选择候选模型后，页面底部的
“测试聊天模型”再执行最小聊天请求。

用户模式下，第一次测试可不传 `model`：

```json
{
  "credential_mode": "user",
  "provider": "deepseek",
  "api_key": "仅当该厂商尚未保存 Key 时提交",
  "temperature": 0.2,
  "max_tokens": 8000,
  "timeout_seconds": 60,
  "max_retries": 2
}
```

如果已保存该厂商 Key，则省略 `api_key`：

```json
{
  "credential_mode": "user",
  "provider": "deepseek",
  "temperature": 0.2,
  "max_tokens": 8000,
  "timeout_seconds": 60,
  "max_retries": 2
}
```

成功响应：

```json
{
  "success": true,
  "message": "模型列表获取成功，请选择一个模型",
  "models": ["deepseek-v4-flash", "deepseek-v4-pro"],
  "model_list_available": true,
  "api_key_saved": true
}
```

将 `models` 作为模型输入框的候选项。用户选择模型后，使用同一路径再次测试：

```json
{
  "credential_mode": "user",
  "provider": "deepseek",
  "model": "deepseek-v4-flash",
  "temperature": 0.2,
  "max_tokens": 8000,
  "timeout_seconds": 60,
  "max_retries": 2
}
```

未选择模型的测试请求会清空旧模型名，不会错误复用上一个厂商的模型。
厂商返回 `401` 或 `403` 时，后端以 `400` 返回安全的中文提示（API Key
无效或无权访问），前端直接展示 `detail`，不应误报为厂商不支持模型列表。

## 保存设置

选择模型并测试成功后，调用：

```http
PATCH /api/settings
Content-Type: application/json
```

请求体与最终测试请求相同。若用户重新输入了 Key，则包含 `api_key`；否则省略该字段，后端自动使用已保存的厂商凭据。

新版本不再提供“平台 Key”模式；聊天模型必须由当前登录用户保存 API Key。历史响应中的 `credential_mode` 仍使用 `user`，用于兼容后端数据结构。

## 向量模型

向量模型设置与聊天模型在同一个页面维护。provider 目录来自：

```http
GET /api/settings/embedding-providers
```

当前设置来自：

```http
GET /api/settings/embedding
```

保存请求：

```json
{
  "provider": "qwen",
  "model": "text-embedding-v4",
  "dimensions": 1024,
  "api_key": "仅当需要新增或替换 Key 时提交",
  "timeout_seconds": 60,
  "max_retries": 2
}
```

测试请求走 `POST /api/settings/embedding`，成功响应会返回本次测试得到的向量维度：

```json
{
  "success": true,
  "message": "向量模型连接测试成功",
  "provider": "qwen",
  "model": "text-embedding-v4",
  "dimensions": 1024
}
```

切换向量模型 provider、model 或 dimensions 后，前端应提示用户重新向量化相关文件；后端会按用户和 embedding 配置隔离 Chroma collection。

向量 provider 支持 `qwen`、`zhipuai`、`openai`、`voyage`、`cohere`、`jina` 和 `openai_compatible`。后端按 `(user_id, provider)` 保存多份向量 API Key，切换回已保存厂商时前端可省略 `api_key`。

## Rerank 模型

Rerank 模型设置与聊天模型、向量模型在同一个页面维护。provider 目录来自：

```http
GET /api/settings/rerank-providers
```

当前设置来自：

```http
GET /api/settings/rerank
```

保存请求：

```json
{
  "provider": "voyage",
  "model": "rerank-2.5",
  "api_key": "仅当需要新增或替换 Key 时提交",
  "timeout_seconds": 60,
  "max_retries": 2
}
```

测试请求走 `POST /api/settings/rerank`，成功响应会返回测试排序的最高分：

```json
{
  "success": true,
  "message": "Rerank 模型连接测试成功",
  "provider": "voyage",
  "model": "rerank-2.5",
  "top_score": 0.93
}
```

Rerank provider 支持 `local`、`qwen`、`voyage`、`cohere`、`jina` 和 `openai_compatible`。`local` 不需要 API Key；远程 provider 的 Key 按 `(user_id, provider)` 加密保存。`qwen` 和 `openai_compatible` 需要填写 `base_url`。

## 错误处理

| 状态码 | 前端处理 |
| --- | --- |
| `400` | 展示 `detail`，通常是必填字段、厂商或参数校验问题。 |
| `401` | 清理登录态并跳转登录。 |
| `502` | 提示连接测试失败；随后重新加载聊天、向量和 Rerank 模型设置。聊天模型测试前提交的新 Key 已被加密保存，用户无需重复输入。 |

个别兼容厂商不支持 `/models`。若用户已填写模型，且最小对话调用成功，接口仍返回成功并携带：

```json
{
  "model_list_available": false,
  "models": []
}
```

此时前端应保留模型名手动输入能力。

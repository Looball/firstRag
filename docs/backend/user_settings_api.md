# 用户模型设置接口说明

本文档供用户设置页面接入使用。所有接口都需要登录认证：

```http
Authorization: Bearer <access_token>
```

所有成功响应都包含 `success: true`。API Key 只在 `PATCH` 和临时测试请求中由前端提交，服务端不会在任何响应中回传它。

## 建议的前端交互流程

1. 页面加载时并行调用 `GET /user/settings/providers` 和 `GET /user/settings`。
2. 用 `providers` 渲染厂商下拉框；`enabled: false` 的选项应禁用或隐藏。
3. 用户选择“使用平台配置”时，仅允许调整生成参数；不显示 API Key 输入框。
4. 用户选择“使用自己的 API Key”时，要求填写厂商、模型名和 API Key。
5. 点击“测试连接”时，调用 `POST /user/settings/test`，提交当前表单数据，但不保存。
6. 测试成功后，点击“保存设置”，调用 `PATCH /user/settings`。
7. 保存后再次调用 `GET /user/settings` 或直接使用 `PATCH` 返回的 `settings` 更新页面。后续发起的 `/chat` 请求会自动使用该用户的新设置。

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

平台模式响应示例：

```json
{
  "success": true,
  "settings": {
    "credential_mode": "platform",
    "provider": "deepseek",
    "model": "deepseek-v4-flash",
    "base_url": "https://api.deepseek.com/v1",
    "has_api_key": true,
    "temperature": 0.2,
    "max_tokens": 8000,
    "timeout_seconds": 60.0,
    "max_retries": 2
  }
}
```

个人配置模式响应示例：

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

切换至平台模式：

```json
{
  "credential_mode": "platform",
  "temperature": 0.2,
  "max_tokens": 8000,
  "timeout_seconds": 60,
  "max_retries": 2
}
```

切换至个人 DeepSeek 配置：

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

注意：从平台模式首次切换到个人模式时，必须同时提交 `credential_mode`、`provider`、`model` 和 `api_key`。切换回平台模式会清除该用户已保存的 API Key 密文。

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
| `credential_mode` | `platform` 或 `user` |
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

## 与聊天接口的关系

`/chat` 会按当前登录用户读取设置。个人配置的 Key 会在服务端解密后用于模型调用，前端无需也不应在聊天请求中再次传递 API Key。若已保存配置无效，`/chat` 返回 `400`，并且不会创建本轮消息记录。

完整 API Key 只允许在用户输入后随 `PATCH /user/settings` 或 `POST /user/settings/test` 提交。后端仅持久化密文和 `api_key_hint`，错误响应会对提交的 Key、`api_key=...` 和 Bearer token 形态文本做脱敏处理，不回显明文。

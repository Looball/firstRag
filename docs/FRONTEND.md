# 前端结构说明

前端位于 `frontend/`，使用 Next.js App Router。浏览器只请求 Next.js 接口，Next.js API Route 再代理到 FastAPI 后端。

## 目录结构

```text
frontend/
├── src/
│   ├── app/
│   │   ├── api/          # Next.js API 代理
│   │   ├── login/        # 登录页
│   │   ├── register/     # 注册页
│   │   ├── settings/     # 模型设置页
│   │   ├── layout.tsx
│   │   └── page.tsx      # 聊天工作台
│   ├── components/
│   │   └── settings/
│   └── lib/
├── package.json
└── tsconfig.json
```

## 启动

```bash
cd frontend
npm install
npm run dev
```

默认访问 `http://localhost:3000`。

## API 代理约定

前端 API Route 默认将请求转发到：

```text
BACKEND_ORIGIN=http://127.0.0.1:8000
BACKEND_API_PREFIX=
```

常见映射：

| 前端路径 | 后端路径 |
| --- | --- |
| `/api/login` | `/login` |
| `/api/register` | `/register` |
| `/api/chat` | `/chat` |
| `/api/chat/knowledge-bases` | `/chat/knowledge-bases` |
| `/api/chat/knowledge-base/...` | `/chat/knowledge-base/...` |
| `/api/chat/knowledge-files...` | `/chat/knowledge-files...` |
| `/api/settings...` | `/user/settings...` |

代理层应透传 `Authorization`，聊天接口应保持 SSE 流式响应。

## 页面职责

- `login/page.tsx`：登录并保存访问令牌。
- `register/page.tsx`：注册新用户。
- `page.tsx`：知识库、文件、会话和聊天主工作台。
- `settings/page.tsx`：模型厂商、个人 API Key、模型列表和生成参数设置。

## 安全约定

- 完整 API Key 只在用户输入后提交给后端。
- 前端不得从后端读取完整 API Key。
- 不把 API Key 写入 `localStorage`、`sessionStorage`、URL、日志或错误上报。
- 登录过期时清理本地认证状态并跳转登录页。


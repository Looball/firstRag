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

默认在仓库根目录通过 Docker Compose 启动完整链路：

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 migrate backend worker frontend postgres
```

默认访问 `http://localhost:3000`。常规验证应基于 Compose 中的 Next.js frontend service。

本地单独启动 Next.js 仅用于页面专项调试：

```bash
cd frontend
npm install
npm run dev
```

## 普通模式与高级模式

聊天工作台默认按普通用户模式展示，只保留聊天、知识库、文件、引用来源和必要状态提示。高级/开发模式通过工作台侧栏的本地开关打开，打开后展示 diagnostics、eval case 草稿、回答反馈、source feedback、质量看板和知识库检索参数。

具备 `file_id` 和 `chunk_index` 的引用卡片会显示“查看原文”。点击后按需加载 `SourcePreviewDialog`，并通过 React Query 按 `file_id + chunk_index + radius` 缓存请求；弹窗高亮目标 chunk、展示相邻上下文、标题层级和 PDF 页码或 DOCX 段落范围。扫描 PDF 来源显示 OCR 置信度，低于后端阈值时展示质量警告和“重新识别此页”；提交后复用 vector job 查询，以 `queued`、`processing`、`succeeded`、`failed` 状态反馈重建进度，避免重复提交。打开 PDF 原始文件时 blob URL 会附加 `#page=N` 跳到目标页；浏览器无法可靠控制 DOCX 内部光标，因此 DOCX 只在内置弹窗中高亮并展示段落范围。历史 source 缺少定位字段时保留现有摘要，不展示不可用入口。

新浏览器会使用 `NEXT_PUBLIC_FIRSTRAG_ADVANCED_MODE_DEFAULT` 作为高级模式默认值；未配置或设为 `false` 时默认进入普通模式。用户手动切换后，偏好会写入浏览器 `localStorage`，只影响当前浏览器。

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
| `/api/chat/attachments` | `/chat/attachments` |
| `/api/chat/attachments/{attachmentId}/content` | `/chat/attachments/{attachment_id}/content` |
| `/api/chat/knowledge-bases` | `/chat/knowledge-bases` |
| `/api/chat/knowledge-base/...` | `/chat/knowledge-base/...` |
| `/api/chat/knowledge-files...` | `/chat/knowledge-files...` |
| `/api/settings...` | `/user/settings...` |

代理层应透传 `Authorization`，聊天接口应保持 SSE 流式响应。后端返回 `429` 时，代理必须保留 `Retry-After`；登录、聊天、图片/知识文件上传、向量化和模型测试会显示剩余等待秒数，并在倒计时结束前禁用对应操作，且不会自动重复提交。

## 页面职责

- `login/page.tsx`：登录并保存访问令牌。
- `register/page.tsx`：注册新用户。
- `page.tsx`：知识库、文件、会话和聊天主工作台；知识库管理支持重命名、移入回收站和恢复，文件管理支持解除单个知识库关联或经二次确认永久删除全局文件；知识文件上传支持 PDF、DOCX、Markdown、TXT、PNG、JPEG 和 WebP，图片入库向量化失败时展示 vision 模型配置恢复动作。
- `settings/page.tsx`：模型厂商、个人 API Key、模型列表和生成参数设置。

## 安全约定

- 完整 API Key 只在用户输入后提交给后端。
- 前端不得从后端读取完整 API Key。
- 不把 API Key 写入 `localStorage`、`sessionStorage`、URL、日志或错误上报。
- `localStorage` 仅保存登录态；设置页的 API Key 输入只保留在组件内存状态中，提交后立即清空。
- 登录过期时清理本地认证状态并跳转登录页。
- 限流错误只保存 `status` 和 `Retry-After` 秒数，不保存限流 identifier、用户名、IP 或 Redis key；不同业务 scope 使用独立倒计时。

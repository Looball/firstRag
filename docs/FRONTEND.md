# 前端结构说明

前端位于 `frontend/`，使用 Next.js App Router。浏览器只请求 Next.js 接口，Next.js API Route 再代理到 FastAPI 后端。

## 目录结构

```text
frontend/
├── e2e/                    # Playwright 浏览器端到端回归
├── src/
│   ├── app/
│   │   ├── api/          # Next.js API 代理
│   │   ├── login/        # 登录页
│   │   ├── register/     # 注册页
│   │   ├── settings/     # 模型设置页
│   │   ├── layout.tsx
│   │   └── page.tsx      # 聊天工作台
│   ├── components/
│   │   ├── chat-workspace/ # 消息、知识库、文件、来源预览、OCR 与诊断组件
│   │   └── settings/
│   └── lib/
├── package.json
├── playwright.config.ts
├── vitest.config.ts
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

## 前端测试

前端测试分为两层，收集范围相互隔离：

- `npm test` 使用 Vitest 运行 `src/` 内的单元与组件测试。
- `npm run test:e2e` 使用 Playwright 启动独立 Next.js dev server，并在 Chromium 中运行 `e2e/` 下的浏览器回归。

OCR source 预览 E2E 使用同源 API fixture 注入合成知识库、会话、chunk context 和 1×1 PNG，不读取真实账号、API Key、后端或外部网络。测试仍会经过真实工作台、`SourcePreviewDialog`、鉴权 header、preview fetch、Blob URL 和浏览器图像解码链路，明确检查点击 source 后访问 `/pages/2/preview`，并确认第 2 页 PNG 完成加载。失败恢复用例让首次 preview 返回受控 `502`，验证错误反馈和手动重试后，再监听 `URL.createObjectURL` / `URL.revokeObjectURL`，确保关闭弹窗会释放当前图像 URL。异步清理用例使用 Promise gate 暂停成功响应，先关闭弹窗再放行 PNG，确认延迟创建的 URL 也会立即撤销，且不会向已关闭界面回写状态。

CI 同时启用 GitHub 和 HTML reporter；E2E 失败时上传 `playwright-report/` 与 `test-results/`，其中包含 HTML report、失败截图和 trace，artifact 名称带 run ID/attempt 并保留 14 天。成功运行不上传诊断 artifact。

`npm run test:e2e:full-stack` 使用独立 Playwright 配置连接已启动的隔离 Compose 环境。标准入口为仓库根目录的 `scripts/run_full_stack_e2e.sh`：它会创建临时 PostgreSQL、Chroma 和 uploads volumes，使用本地确定性 OpenAI-compatible stub 提供 chat/embedding，先通过真实注册 API 创建测试账号，再由 Chromium 完成登录、TXT 上传、worker 向量化、SSE 回答和引用展示。该门禁不读取真实账号、`.env` provider Key 或公网模型服务，结束后只删除自己的 `firstrag-t089-*` Compose project。

首次在本机运行 E2E 前需要安装对应版本的 Chromium：

```bash
cd frontend
npx --no-install playwright install chromium
npm run test:e2e
```

## 普通模式与高级模式

聊天工作台默认按普通用户模式展示，只保留聊天、知识库、文件、引用来源和必要状态提示。高级/开发模式通过工作台侧栏的本地开关打开，打开后展示 diagnostics、eval case 草稿、回答反馈、source feedback、质量看板和知识库检索参数。

具备 `file_id` 和 `chunk_index` 的引用卡片会显示“查看原文”。点击后按需加载 `SourcePreviewDialog`，并通过 React Query 按 `file_id + chunk_index + radius` 缓存请求；弹窗高亮目标 chunk、展示相邻上下文、标题层级和 PDF 页码或 DOCX 段落范围。文件管理对已索引 PDF 提供“OCR 巡检”：`OcrQualityInspectorDialog` 展示待处理、已校对、OCR 页数和平均置信度，页码质量刻度以琥珀标出待处理页、墨绿标出人工修订页，并支持全部/待处理/已校对筛选与低分/页码排序。批次清单可选择待处理页或当前筛选页，把页码合并为一个异步重建任务；进度轨展示排队、处理中、成功、失败和查询异常，失败时按服务端保存的原批次重试。每个页面同时显示历史数量、最近 confidence delta、当前 OCR strategy/PSM/rotation 和候选数；`OcrHistoryDialog` 仅在打开时按需加载识别账本，以 Run 轨道切换记录，汇总最佳/当前分数和改善/下降次数，并用 Candidate Lab 条带解释每个候选的状态、confidence、词数、字符数和最终采用项，再复用线性空间 diff 展示相邻 Tesseract 原文变化。点击页码仍会构造绑定 `file_id + chunk_index + index_version` 的安全 source，直接以校对模式打开现有来源弹窗，不要求先产生聊天引用。

扫描 PDF 来源显示 OCR 置信度，低于后端阈值时展示质量警告；点击 OCR source 后，来源弹窗会立即请求并展示引用页的后端 PNG，无需先进入校对模式。人工校对工作台在桌面并排显示同一目标页 PNG 和完整文本，窄屏改为纵向排列。编辑区可切换“编辑全文”和“查看差异”，差异算法使用唯一行锚点和线性空间逐段对齐，高亮新增、删除、修改行及变化字符；`useDeferredValue` 避免长文本输入被比较阻塞。PDF 预览使用临时 Blob URL，组件关闭、页码切换或重新加载时立即释放；失败不会清空草稿，并提供重试和新窗口打开原 PDF。保存后展示 revision，也可经过二次确认撤销修订。校对、撤销和“重新识别此页”都复用 vector job 查询，以 `queued`、`processing`、`succeeded`、`failed` 状态反馈重建进度，失败时只重试索引而不重复写修订。新窗口打开 PDF 时 blob URL 会附加 `#page=N` 跳到目标页；浏览器无法可靠控制 DOCX 内部光标，因此 DOCX 只在内置弹窗中高亮并展示段落范围。历史 source 缺少定位字段时保留现有摘要，不展示不可用入口。

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
- `page.tsx`：知识库、文件、会话和聊天主工作台；知识库管理支持重命名、移入回收站和恢复，文件管理支持解除单个知识库关联或经二次确认永久删除全局文件；知识文件上传支持 PDF、DOCX、Markdown、TXT、PNG、JPEG 和 WebP，图片入库向量化失败时展示 vision 模型配置恢复动作。单条消息的角色外观、流式占位、检索空态和子组件组合由 `components/chat-workspace/ConversationMessageItem.tsx` 独立渲染；其内部复用 `AssistantMessageActions.tsx`、`MessageSourceList.tsx` 和 `MessageContent.tsx`。message/source feedback 与 Eval 草稿的 state、请求、目标消息回写、提示计时和文件下载由 `lib/chat-workspace/use-message-quality-actions.ts` 管理，conversation diagnostics 的缓存、silent preload、首次展开加载和错误状态由 `lib/chat-workspace/use-conversation-diagnostics.ts` 管理，回答复制的 Clipboard API、textarea fallback 和 1.5 秒提示由 `lib/chat-workspace/use-message-clipboard.ts` 管理，会话创建、选择消息加载、重命名和删除由 `lib/chat-workspace/use-conversation-actions.ts` 管理，`sessions` 仍由页面持有。聊天输入、待发送图片和发送状态由 `components/chat-workspace/ChatComposer.tsx` 独立渲染，待发送图片的数量/类型/大小校验、剪贴板筛选、预览和 Object URL 生命周期由 `lib/chat-workspace/use-pending-chat-images.ts` 管理。主工作区标题与消息/文件统计由 `components/chat-workspace/ChatWorkspaceHeader.tsx` 独立渲染，用户身份、设置/退出入口和模式切换由 `components/chat-workspace/SidebarAccountModeControls.tsx` 独立渲染，知识库管理弹窗由 `components/chat-workspace/KnowledgeBaseManagerDialog.tsx` 独立渲染，知识库选择与文件入口由 `components/chat-workspace/KnowledgeBaseSidebarControls.tsx` 独立渲染，会话索引由 `components/chat-workspace/ConversationSidebar.tsx` 独立渲染，高级模式质量指标由 `components/chat-workspace/QualityDashboardPanel.tsx` 独立渲染，其展开、缓存、首次加载和刷新流程由 `lib/chat-workspace/use-quality-dashboard.ts` 管理；页面保留认证、模式偏好、图片上传发送流程、原文弹窗，以及相关请求、生命周期状态、sources、诊断和流式状态编排。
- `settings/page.tsx`：模型厂商、个人 API Key、模型列表和生成参数设置。

## 安全约定

- 完整 API Key 只在用户输入后提交给后端。
- 前端不得从后端读取完整 API Key。
- 不把 API Key 写入 `localStorage`、`sessionStorage`、URL、日志或错误上报。
- `localStorage` 仅保存登录态；设置页的 API Key 输入只保留在组件内存状态中，提交后立即清空。
- 登录过期时清理本地认证状态并跳转登录页。
- 限流错误只保存 `status` 和 `Retry-After` 秒数，不保存限流 identifier、用户名、IP 或 Redis key；不同业务 scope 使用独立倒计时。

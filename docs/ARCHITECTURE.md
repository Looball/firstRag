# 系统架构

FirstRAG 是一个全栈 RAG 应用，当前采用 monorepo 组织：

```text
FirstRAG/
├── frontend/      # Next.js / React 前端
├── backend/       # FastAPI 后端
├── docs/          # 项目文档
├── deploy/        # 部署配置
├── scripts/       # 初始化、迁移、维护脚本
└── .env.example   # 环境变量模板
```

## 核心数据流

```text
用户上传文件
  -> Next.js API 代理
  -> FastAPI 路由层
  -> 文件落盘 + PostgreSQL 元数据
  -> 创建 vector_index_jobs 队列任务
  -> vector_index_worker 消费任务
  -> document_service 解析/切分（图片知识文件先经用户 vision 模型转为可检索文本）
  -> Chroma 写入向量 + PostgreSQL 写入全文检索 chunk

用户提问
  -> Next.js API 代理
  -> FastAPI /chat
  -> 可选校验并绑定聊天图片附件
  -> rag_service 构建 LCEL 链
  -> 混合检索：向量 + 全文 + RRF + rerank
  -> LLM 流式生成（带图片时使用多模态消息）
  -> SSE 返回 token、来源和检索诊断
  -> messages 持久化回答、sources、retrieval

聊天图片附件
  -> Next.js API 代理
  -> FastAPI /chat/attachments
  -> 文件落盘 + PostgreSQL message_attachments metadata
  -> /chat 绑定到当前用户消息

永久删除知识文件
  -> 单文件 PostgreSQL advisory lock
  -> 取消 active vector index jobs
  -> 删除 Chroma vectors
  -> 事务清理文件关联、chunks、jobs、历史 sources/feedback 和文件记录
  -> 删除 uploads 下的磁盘文件并失效知识库画像缓存

回答引用原文预览
  -> source.file_id + source.chunk_index + source.index_version
  -> 当前用户 JWT 权限校验
  -> PostgreSQL knowledge_file_chunks 当前 index_version
  -> 返回目标 chunk、相邻上下文及 PDF 页码或 DOCX 段落范围
  -> 校对工作台按权限将 PDF 目标页即时渲染为 PNG；新窗口原文件使用 #page=N 跳页
```

## 分层边界

| 层 | 目录 | 职责 |
| --- | --- | --- |
| 前端页面 | `frontend/src/app` | 登录、注册、聊天工作台、设置页。 |
| 前端代理 | `frontend/src/app/api` | 将浏览器请求转发到后端，统一处理鉴权头与流式响应。 |
| 后端路由 | `backend/app/api` | 参数校验、认证依赖、权限检查、HTTP 错误转换。 |
| Schema | `backend/app/schemas` | Pydantic 请求模型。 |
| 服务层 | `backend/app/services` | RAG 编排、文件处理、模型调用、向量化业务流程。 |
| 仓库层 | `backend/app/repositories` | 纯 SQL 数据访问。 |
| 数据库工具 | `backend/app/db` | 连接、执行器、PostgreSQL advisory lock。 |
| 基础设施 | `backend/app/core` | 配置、JWT、安全和密钥加密。 |
| Worker | `backend/app/workers` | 异步向量化任务消费；扫描 PDF 页面在容器内通过 Tesseract OCR，保存页级置信度，消费受控重识别选项，并在切分前应用持久化人工修订。 |

## 存储组件

- PostgreSQL：用户、知识库、文件、会话、消息、聊天附件 metadata、文本/图片解析分块、向量化任务队列。
- PostgreSQL OCR corrections：按用户、文件和页码保存人工修订、原始 OCR 文本与 revision；知识文件永久删除时级联清理。
- Redis：提供基础设施健康检查、RAG 热点共享缓存、后端分布式限流和 vector worker 运行态，包括知识库画像、retrieval settings、query embedding、登录/业务 API sliding-window 计数、worker 心跳、单文件短租约和运行指标；不作为会话、消息或 vector index job 的持久存储。
- Chroma：文档分块向量。Docker Compose 使用独立 `chroma` service，backend 与
  worker 通过 HTTP client 共享访问，数据持久化到根目录 `vector_db/chroma`；
  单进程 conda 调试未配置 `CHROMA_HOST` 时仍可使用 embedded 模式。
- Tesseract：仅对无有效文本层或用户明确重识别的 PDF 页面执行本地 OCR；同次调用产出正文和 TSV word confidence，原始页面和识别文本不发送到外部 OCR 服务。
- 本地文件系统：知识文件默认保存到根目录 `uploads/users/...`，聊天图片附件默认保存到 `uploads/chat_attachments/users/...`。

## 认证与权限

后端使用 JWT Bearer Token。所有用户数据接口通过 `Depends(get_current_user_id)` 取得当前用户 ID。涉及知识库、文件、会话和任务的查询必须带 `user_id` 权限隔离；不存在或不属于当前用户时统一返回 `404`。

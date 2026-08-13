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
  -> provider-neutral vector store boundary
  -> Milvus child dense/sparse vectors + PostgreSQL parent/child context

用户提问
  -> Next.js API 代理
  -> FastAPI /chat
  -> 可选校验并绑定聊天图片附件
  -> rag_service 构建 LCEL 链
  -> v2：Milvus dense+sparse hybrid/RRF -> child rerank -> PostgreSQL parent context
     兼容：Milvus dense + PostgreSQL full-text + 应用层 RRF
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
  -> 删除当前 vector store entities
  -> 事务清理文件关联、chunks、jobs、历史 sources/feedback 和文件记录
  -> 删除 uploads 下的磁盘文件并失效知识库画像缓存

回答引用原文预览
  -> source.file_id + source.chunk_index + source.index_version
  -> 当前用户 JWT 权限校验
  -> PostgreSQL knowledge_file_chunks 当前 index_version
  -> 返回目标 chunk、相邻上下文及 PDF 页码或 DOCX 段落范围
  -> 校对工作台按权限将 PDF 目标页即时渲染为 PNG；新窗口原文件使用 #page=N 跳页

文件级 OCR 质量巡检
  -> 当前用户选择已索引 PDF
  -> PostgreSQL 当前 index_version 的 OCR 代表 chunks + corrections + history 摘要
  -> 汇总待处理、已校对、页级置信度、安全摘要和最近质量变化
  -> 按需读取单页 OCR history，展示识别账本与相邻原文差异
  -> 点击页码复用引用原文预览与校对工作台
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
| Worker | `backend/app/workers` | 异步向量化任务消费；扫描 PDF 页面在容器内通过 Tesseract OCR，主动重识别时比较预处理/PSM/旋转候选，保存页级置信度、选优依据和原始识别历史，一次消费单页或多页受控批次，并在切分前应用持久化人工修订。 |
| Sparse encoder | `backend/sparse_encoder` | Compose 内网单实例加载固定 revision BGE-M3，提供 document/query learned sparse contract；worker 用于 v2 写入，backend 用于 v2 hybrid query。 |

## 存储组件

- PostgreSQL：用户、知识库、文件、会话、消息、聊天附件 metadata、文本/图片解析分块、向量化任务队列。
- PostgreSQL OCR corrections：按用户、文件和页码保存人工修订、原始 OCR 文本与 revision；知识文件永久删除时级联清理。
- PostgreSQL OCR history：按用户、文件、页码和 index version 保存有上限的 Tesseract 最佳原始识别记录、质量指标、文本 SHA、所选策略、候选摘要和来源 job；与 chunks 生命周期解耦，文件删除时级联清理。
- Redis：提供基础设施健康检查、RAG 热点共享缓存、后端分布式限流和 vector worker 运行态，包括知识库画像、retrieval settings、query embedding、登录/业务 API sliding-window 计数、worker 心跳、单文件短租约和运行指标；不作为会话、消息或 vector index job 的持久存储。
- Vector store boundary：业务层只使用 collection、单文件替换/删除、检索、审计、计数和健康检查契约；collection 命名、scalar filter、distance 规范化和异常分类均收口在 Milvus adapter 内。
- Milvus：唯一受支持的 vector store。Compose 启动 authenticated Standalone、etcd、MinIO 和一次性 health probe；backend 与 worker 使用独立 PyMilvus client，Strong consistency 与写后 self-hit 保证跨进程可见。
- BGE-M3 sparse encoder：独立容器只加载一份 `BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181`，不映射 host port；`/health/live` 区分进程存活，`/health/ready` 只有在模型加载和最小 sparse inference 成功后才通过。模型 cache 保存到 `bge_m3_cache` named volume，服务日志只记录 mode、batch 和耗时，不记录企业文本。
- Tesseract：仅对无有效文本层或用户明确重识别的 PDF 页面执行本地 OCR；首次索引使用单次基线，主动重识别在候选/总超时上限内比较原图、灰度、二值化和页面旋转，同次调用产出正文和 TSV word confidence，原始页面和识别文本不发送到外部 OCR 服务。
- 本地文件系统：知识文件默认保存到根目录 `uploads/users/...`，聊天图片附件默认保存到 `uploads/chat_attachments/users/...`。

## 认证与权限

后端使用 JWT Bearer Token。所有用户数据接口通过 `Depends(get_current_user_id)` 取得当前用户 ID。涉及知识库、文件、会话和任务的查询必须带 `user_id` 权限隔离；不存在或不属于当前用户时统一返回 `404`。

# FirstRAG 源码地图

本页不是完整文件清单，而是面向学习的入口索引。先按业务问题找到一条纵向链路，再进入相邻模块；不要从目录树第一行开始逐文件阅读。

## 全局入口

| 入口 | 职责 | 重点观察 |
| --- | --- | --- |
| [`frontend/src/app/page.tsx`](../../frontend/src/app/page.tsx) | 聊天工作台页面编排。 | 页面如何组合会话、知识库、文件、检索设置、消息和质量反馈 hooks。 |
| [`frontend/src/app/api/chat/route.ts`](../../frontend/src/app/api/chat/route.ts) | 浏览器到 FastAPI `/chat` 的 SSE proxy。 | Authorization 转发、streaming body 和错误适配。 |
| [`backend/app/main.py`](../../backend/app/main.py) | FastAPI app 与 router 注册入口。 | middleware、request ID、八个业务 router 的装配。 |
| [`docker-compose.yml`](../../docker-compose.yml) | 默认完整运行拓扑。 | Redis、PostgreSQL、Chroma、migrate、backend、worker、frontend 的依赖关系。 |
| [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) | PR 与 `main` 的自动门禁。 | Backend、Frontend、Full-stack E2E、Container OS Security 四个稳定 job。 |

## 文件入库与异步索引

调用顺序从 HTTP 到存储如下：

```text
Next.js proxy
  -> FastAPI route
  -> repository 权限/metadata
  -> queue service + vector_index_jobs
  -> vector_index_worker
  -> document service + embedding
  -> Chroma vectors + PostgreSQL chunks
```

| 层 | 源码入口 | 职责 |
| --- | --- | --- |
| 前端请求 | [`frontend/src/lib/chat-workspace/api.ts`](../../frontend/src/lib/chat-workspace/api.ts) | 文件、任务和知识库相关浏览器请求。 |
| 前端状态 | [`use-knowledge-files.ts`](../../frontend/src/lib/chat-workspace/use-knowledge-files.ts)、[`use-knowledge-file-indexing.ts`](../../frontend/src/lib/chat-workspace/use-knowledge-file-indexing.ts) | 组合文件 library、mutation、任务队列与 worker health。 |
| Route | [`backend/app/api/knowledge_files.py`](../../backend/app/api/knowledge_files.py)、[`vector_indexes.py`](../../backend/app/api/vector_indexes.py) | 参数校验、认证、资源归属与 HTTP error。 |
| Schema | [`backend/app/schemas/knowledge.py`](../../backend/app/schemas/knowledge.py) | 文件、知识库和向量任务请求/响应结构。 |
| Repository | [`knowledge_file_repository.py`](../../backend/app/repositories/knowledge_file_repository.py)、[`vector_index_job_repository.py`](../../backend/app/repositories/vector_index_job_repository.py) | 文件 metadata、关联关系和持久任务队列 SQL。 |
| Queue service | [`vector_index_queue_service.py`](../../backend/app/services/vectors/vector_index_queue_service.py) | 入队、重试、版本和任务状态编排。 |
| Worker | [`vector_index_worker.py`](../../backend/app/workers/vector_index_worker.py) | 领取任务、租约/心跳、单文件锁和最终状态。 |
| 文档解析 | [`document_service.py`](../../backend/app/services/documents/document_service.py) | PDF、DOCX、Markdown、TXT、图片解析与 chunk。 |
| 向量化 | [`embedding_model.py`](../../backend/app/services/vectors/embedding_model.py)、[`vector_index_service.py`](../../backend/app/services/vectors/vector_index_service.py) | 用户 embedding 配置、向量生成、vector store 与 chunk 写入。 |
| Vector store boundary | [`vector_store.py`](../../backend/app/services/vectors/vector_store.py)、[`vector_store_factory.py`](../../backend/app/services/vectors/vector_store_factory.py)、[`chroma_vector_store.py`](../../backend/app/services/vectors/chroma_vector_store.py)、[`milvus_vector_store.py`](../../backend/app/services/vectors/milvus_vector_store.py) | 统一 collection、写入、删除、检索、审计、计数和健康契约；默认 Chroma 与迁移候选 Milvus 使用同一应用层契约。 |
| 锁与 SQL | [`backend/app/db/locks.py`](../../backend/app/db/locks.py)、[`000_initial_schema.sql`](../../backend/app/db/sql/000_initial_schema.sql) | PostgreSQL advisory lock 与空库 schema 基线。 |

继续阅读：[文件入库与异步索引教程](FILE_INGESTION_AND_INDEXING.md)和[RAG 核心流程：文件入库与向量化任务](../RAG_WORKFLOW.md#文件入库)。

## 混合检索与流式回答

```text
POST /chat
  -> 会话/知识库权限
  -> retrieval decision
  -> vector + full-text
  -> RRF + optional rerank
  -> LCEL streaming
  -> SSE token/sources/diagnostics
  -> messages 持久化
```

| 层 | 源码入口 | 职责 |
| --- | --- | --- |
| Route | [`backend/app/api/chat.py`](../../backend/app/api/chat.py) | chat 请求校验、会话权限和 StreamingResponse。 |
| Service 门面 | [`backend/app/services/rag_service.py`](../../backend/app/services/rag_service.py) | 保留兼容导入，委托 `services/rag/`。 |
| 检索决策 | [`retrieval_decision.py`](../../backend/app/services/rag/retrieval_decision.py) | `auto/always/never`、Router 结果和确定性覆盖。 |
| 检索流水线 | [`retrieval_pipeline.py`](../../backend/app/services/rag/retrieval_pipeline.py) | 设置、知识库画像、文件范围、hybrid retrieval 和 diagnostics。 |
| Hybrid / Vector | [`hybrid_retriever.py`](../../backend/app/services/retrieval/hybrid_retriever.py)、[`chroma_vector_store.py`](../../backend/app/services/vectors/chroma_vector_store.py)、[`milvus_vector_store.py`](../../backend/app/services/vectors/milvus_vector_store.py) | 两路并行、query embedding cache、严格用户/文件过滤、统一 distance 结果与 provider-aware diagnostics。 |
| Full-text | [`fulltext_retriever.py`](../../backend/app/services/retrieval/fulltext_retriever.py) | PostgreSQL 全文召回。 |
| Fusion / rerank | [`rrf.py`](../../backend/app/services/retrieval/rrf.py)、[`reranker.py`](../../backend/app/services/retrieval/reranker.py) | RRF 融合与可选本地/远程精排。 |
| Chain | [`chain_builder.py`](../../backend/app/services/rag/chain_builder.py) | LCEL Router 与问答链构建。 |
| SSE | [`streaming.py`](../../backend/app/services/rag/streaming.py) | retrieval、sources、usage、answer 事件序列化。 |
| 引用 | [`reference_serializer.py`](../../backend/app/services/rag/reference_serializer.py) | prompt context 和前端 sources。 |
| 持久化 | [`message_repository.py`](../../backend/app/repositories/message_repository.py) | assistant 状态、回答、sources 与 retrieval JSON。 |

继续阅读：[混合检索与流式回答教程](HYBRID_RETRIEVAL_AND_STREAMING.md)、[RAG 核心流程：聊天生成](../RAG_WORKFLOW.md#聊天生成)和[检索诊断](../RAG_WORKFLOW.md#检索诊断)。

## 前端工作台与 API proxy

| 主题 | 源码入口 | 重点观察 |
| --- | --- | --- |
| 页面编排 | [`frontend/src/app/page.tsx`](../../frontend/src/app/page.tsx) | 页面持有的顶层选择状态与各职责 hook 的组合。 |
| Proxy helper | [`frontend/src/lib/api-proxy.ts`](../../frontend/src/lib/api-proxy.ts) | 后端 origin、header 转发、错误和 streaming 适配。 |
| 前端 API client | [`frontend/src/lib/chat-workspace/api.ts`](../../frontend/src/lib/chat-workspace/api.ts) | UI 使用的请求函数和轻量响应解析。 |
| Chat 提交 | [`use-chat-submission.ts`](../../frontend/src/lib/chat-workspace/use-chat-submission.ts) | 图片上传、提交事务和页面状态。 |
| SSE 回写 | [`use-chat-response-stream.ts`](../../frontend/src/lib/chat-workspace/use-chat-response-stream.ts)、[`chat-stream.ts`](../../frontend/src/lib/chat-workspace/chat-stream.ts) | assistant 占位、token 累加、sources/diagnostics 和失败状态。 |
| 会话 | [`use-conversation-actions.ts`](../../frontend/src/lib/chat-workspace/use-conversation-actions.ts)、[`use-conversation-message-loader.ts`](../../frontend/src/lib/chat-workspace/use-conversation-message-loader.ts) | CRUD 与 active session 消息懒加载。 |
| 文件与任务 | [`use-knowledge-files.ts`](../../frontend/src/lib/chat-workspace/use-knowledge-files.ts)、[`use-vector-index-queue.ts`](../../frontend/src/lib/chat-workspace/use-vector-index-queue.ts) | 文件操作、任务等待、轮询与 health。 |
| 消息组件 | [`ConversationMessageItem.tsx`](../../frontend/src/components/chat-workspace/ConversationMessageItem.tsx)、[`MessageSourceList.tsx`](../../frontend/src/components/chat-workspace/MessageSourceList.tsx) | 回答、sources、diagnostics 和反馈入口。 |

继续阅读：[前端、安全、测试与部署进阶](FRONTEND_SECURITY_TESTING_AND_DEPLOYMENT.md#3-前端页面状态与-api-proxy)和[前端结构说明](../FRONTEND.md)。

## 认证、模型设置与安全边界

| 层 | 源码入口 | 职责 |
| --- | --- | --- |
| Auth route | [`backend/app/api/auth.py`](../../backend/app/api/auth.py) | 注册、登录、JWT 和登录限流。 |
| Settings route | [`backend/app/api/user_settings.py`](../../backend/app/api/user_settings.py) | LLM、embedding、rerank 设置和 provider 测试。 |
| Settings service | [`user_settings_service.py`](../../backend/app/services/user_settings_service.py)、[`embedding_settings_service.py`](../../backend/app/services/vectors/embedding_settings_service.py) | provider/model 规范化和凭据读取。 |
| 凭据持久化 | [`user_llm_provider_credential_repository.py`](../../backend/app/repositories/user_llm_provider_credential_repository.py)、[`user_embedding_provider_credential_repository.py`](../../backend/app/repositories/user_embedding_provider_credential_repository.py) | 按用户/provider 保存密文与安全 hint。 |
| 加密与脱敏 | [`secret_cipher.py`](../../backend/app/core/secret_cipher.py)、[`sensitive_data.py`](../../backend/app/core/sensitive_data.py) | Fernet 加解密与错误/日志脱敏。 |
| 自定义地址 | [`provider_base_url.py`](../../backend/app/services/provider_base_url.py) | OpenAI-compatible base URL 与 SSRF 边界。 |
| 前端设置页 | [`frontend/src/app/settings/page.tsx`](../../frontend/src/app/settings/page.tsx)、[`ModelSettingsForm.tsx`](../../frontend/src/components/settings/ModelSettingsForm.tsx) | API Key 只在输入后提交，不回显完整值。 |

继续阅读：[前端、安全、测试与部署进阶：认证、API Key 与自定义 provider 安全](FRONTEND_SECURITY_TESTING_AND_DEPLOYMENT.md#4-认证api-key-与自定义-provider-安全)、[用户设置 API](../backend/user_settings_api.md)和[前后端设置协议](../backend/frontend_llm_settings_protocol.md)。

## OCR 与引用核验

| 主题 | 源码入口 | 职责 |
| --- | --- | --- |
| OCR engine | [`pdf_ocr_engine.py`](../../backend/app/services/documents/pdf_ocr_engine.py) | Tesseract 基线与主动重识别候选。 |
| 质量与历史 | [`pdf_ocr_quality_service.py`](../../backend/app/services/documents/pdf_ocr_quality_service.py)、[`pdf_ocr_history_service.py`](../../backend/app/services/documents/pdf_ocr_history_service.py) | 置信度、质量等级和页级识别账本。 |
| 人工校对 | [`pdf_ocr_correction_service.py`](../../backend/app/services/documents/pdf_ocr_correction_service.py)、[`pdf_ocr_reindex_service.py`](../../backend/app/services/documents/pdf_ocr_reindex_service.py) | revision、撤销和异步索引重建。 |
| 原页预览 | [`pdf_page_preview_service.py`](../../backend/app/services/documents/pdf_page_preview_service.py) | 权限校验后的 PDF 页 PNG。 |
| 前端巡检 | [`OcrQualityInspectorDialog.tsx`](../../frontend/src/components/chat-workspace/OcrQualityInspectorDialog.tsx)、[`OcrCorrectionWorkspace.tsx`](../../frontend/src/components/chat-workspace/OcrCorrectionWorkspace.tsx) | 低质量页面发现、历史、重识别和校对。 |
| 回归门禁 | [`scripts/eval_pdf_ocr.py`](../../scripts/eval_pdf_ocr.py)、[`test_pdf_ocr_engine.py`](../../backend/tests/services/test_pdf_ocr_engine.py) | 合成扫描退化评测与 engine 单测。 |

继续阅读：[PDF OCR 回归门禁](../evals/README.md#pdf-ocr-回归门禁)。

## 测试、评测与部署

| 类型 | 源码入口 | 何时使用 |
| --- | --- | --- |
| 后端测试 | [`backend/tests/`](../../backend/tests/) | route、service、repository 边界或脚本变化。 |
| 前端单测 | [`frontend/src/`](../../frontend/src/) 中的 `*.test.*` | 组件、hook、解析和状态 helper 变化。 |
| 浏览器 E2E | [`ocr-source-preview.spec.ts`](../../frontend/e2e/ocr-source-preview.spec.ts) | 页面交互、鉴权请求、Blob URL 和图片预览。 |
| 无密钥全栈 E2E | [`run_full_stack_e2e.sh`](../../scripts/run_full_stack_e2e.sh)、[`full-stack-core.spec.ts`](../../frontend/e2e/full-stack-core.spec.ts) | 注册、登录、上传、worker、检索、SSE 和 sources 完整链路。 |
| RAG / indexing eval | [`eval_rag.py`](../../scripts/eval_rag.py)、[`eval_indexing.py`](../../scripts/eval_indexing.py) | 有真实账号和 provider 配置时验证质量与索引行为。 |
| Production preflight | [`production_preflight.py`](../../scripts/production_preflight.py) | 部署配置、migration 方法和 runtime health。 |
| 教程文档门禁 | [`check_tutorial_docs.py`](../../scripts/check_tutorial_docs.py)、[`tutorial_manifest.json`](tutorial_manifest.json) | 内部链接、源码路径、三级练习、fixture 来源、命令格式和敏感模式。 |
| Migration | [`migrate_db.py`](../../scripts/migrate_db.py)、[`backend/app/db/sql/`](../../backend/app/db/sql/) | schema 变更和空库/增量迁移。 |
| CI | [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) | PR 与 `main` 的完整 required checks。 |
| Docker runtime | [`deploy/docker/`](../../deploy/docker/) | backend/frontend 镜像和隔离 E2E override。 |

继续阅读：[前端、安全、测试与部署进阶：测试金字塔](FRONTEND_SECURITY_TESTING_AND_DEPLOYMENT.md#6-测试金字塔每个门禁证明什么)、[无外部密钥入门实验](CREDENTIAL_FREE_QUICKSTART.md)、[部署与本地工作流](../DEPLOYMENT.md)和[评测说明](../evals/README.md)。

## 按问题反查

| 问题 | 先看 |
| --- | --- |
| 文件为什么一直 `queued`？ | `vector_index_job_repository.py` → `vector_index_worker.py` → `vector_worker_runtime_service.py`。 |
| 为什么 vector 失败但仍有回答？ | `hybrid_retriever.py` → `retrieval_pipeline.py` 的 degraded diagnostics。 |
| 为什么 sources 没显示？ | `reference_serializer.py` → `streaming.py` → `chat-stream.ts` → `MessageSourceList.tsx`。 |
| API Key 保存在哪里？ | settings route/service → provider credential repository → `secret_cipher.py`。 |
| OCR 修改后为何需要重建？ | correction service → reindex service → vector job → document service。 |
| CI 为什么耗时较长？ | workflow 中的 OCR regression、full-stack E2E、镜像构建与 Trivy 扫描。 |

如果入口文件发生移动，应在同一 PR 中更新本页；不要保留指向旧路径的“历史兼容”教程链接。

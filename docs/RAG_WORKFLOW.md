# RAG 核心流程

本文说明 FirstRAG 的文件入库、检索和回答生成流程。

## 文件入库

1. 用户在前端上传文件到某个知识库。
2. Next.js API Route 代理到 `POST /chat/knowledge-base/{knowledge_base_id}/files`。
3. 后端计算 SHA-256 和文件大小。
4. 若同一用户已上传过相同内容，则复用 `knowledge_files` 记录，只补充知识库关联。

知识库移入回收站只隐藏知识库及其会话，不删除可复用文件或索引；恢复后原关联重新生效。永久删除知识文件会使用与 indexing 相同的单文件 advisory lock，取消 active jobs，并清理 Chroma、PostgreSQL 和磁盘内容，避免旧 worker 在删除后写回数据。
5. 新文件保存到根目录 `uploads/users/{user_id}/{hash_prefix}/{file_id}/source.ext`。
6. `auto_index=true` 时创建 `vector_index_jobs` 任务。

## 向量化任务

1. `vector_index_worker` 领取 `queued` 任务。
2. 使用 PostgreSQL advisory lock 避免同一文件并发索引。
3. `document_service` 加载 PDF、DOCX、Markdown、TXT 或图片知识文件。PDF 先按页解析原生文本，无有效文本层的页面渲染为 PNG 并通过本地 Tesseract OCR，同时写入真实页码和解析方式 metadata；DOCX 从 OOXML 主文档按标题和段落边界加载，保留原始段落范围。图片文件会使用当前用户配置的 vision 聊天模型解析为可检索 Markdown；聊天图片附件不走这条入库链路。
4. 文本或图片解析结果切分为 chunk；同一文件跨 PDF page 或 DOCX block 使用全局连续的 `chunk_index`。
5. 当前登录用户保存的 embedding provider 生成向量，支持 Qwen、智谱、OpenAI、Voyage、Cohere、Jina 和自定义 OpenAI-compatible embedding API。用户可按厂商保存多份 API Key，当前生效配置决定实际调用的 provider/model/base_url。
6. Chroma 保存向量；Compose 中 worker 与 backend 均通过 HTTP client 访问独立
   `chroma` service，避免多个 embedded 进程共享目录产生索引可见性问题。
7. PostgreSQL `knowledge_file_chunks` 保存 chunk 正文和 metadata，用于全文检索。
8. 更新文件状态和任务状态。

## 聊天生成

1. 前端发送 `POST /api/chat`，代理到后端 `POST /chat`。
2. 后端校验会话属于当前用户和知识库。
3. 若本轮包含图片附件，后端校验附件属于当前用户和当前会话，并确认当前聊天模型支持 vision 输入。
4. 问候类本地可回答内容直接走本地响应，避免额外模型调用；带图片的问题始终进入模型调用链路。
5. 普通问题加载历史消息，构建 RAG 链。
6. `rag_service` 兼容入口委托 `app/services/rag/` 内部模块读取 retrieval settings、判断是否需要检索，并可改写多轮问题。
7. 召回候选片段：
   - Chroma 向量检索和 PostgreSQL 全文检索并行粗召回。
   - RRF 融合多路结果。
   - 可选 reranker 精排，默认本地 CrossEncoder；也可在用户设置中切换到 Qwen、Voyage、Cohere、Jina 或自定义 rerank API。
8. 用户配置的 OpenAI 兼容聊天模型流式生成回答；带图片时，最终用户消息按 OpenAI-compatible 多模态 payload 发送。
9. SSE 返回 token、sources、retrieval 诊断。
10. 回答完成后持久化到 `messages`，用户图片 metadata 通过 `message_attachments` 与用户消息关联。

聊天图片附件通过 `POST /chat/attachments` 先上传到本地文件系统，后端只向前端返回安全 metadata 和读取 URL。附件用于当前会话消息的视觉问答，不会自动进入 `knowledge_files`、`knowledge_file_chunks` 或 Chroma。需要长期检索的图片应作为知识文件上传，worker 会用当前用户的 vision 模型解析图片内容并写入既有 chunk 与向量链路。

知识库级 retrieval settings 可通过
`GET/PATCH /chat/knowledge-base/{knowledge_base_id}/retrieval-settings`
读写，当前支持：

- `retrieval_mode`：`auto`、`always`、`never`。
- `enable_query_router`：是否调用 Router LLM 判断本轮是否检索。
- `enable_rerank`：是否启用 rerank 精排。
- `top_k`、`vector_top_k`、`fulltext_top_k`、`rrf_k`：控制最终引用数、两路召回数和 RRF 候选池；默认分别为 `4`、`16`、`16`、`8`，用于减少 rerank 候选数和首 token 前等待时间。
- `rerank_score_threshold`：控制低相关片段是否进入上下文和 Sources。

## 检索诊断

## RAG Service 模块边界

`backend/app/services/rag_service.py` 保留为兼容门面，继续导出历史 public function。实际职责拆分到
`backend/app/services/rag/`：

| 模块 | 职责 |
| --- | --- |
| `chain_builder.py` | 创建 LCEL 问答链、Router chain 和 QA chain。 |
| `retrieval_decision.py` | 规范化 retrieval settings、解析 Router JSON、执行确定性覆盖规则并生成最终检索决策。 |
| `retrieval_pipeline.py` | 读取 retrieval settings、构建知识库画像、查询已索引文件 ID、执行 hybrid retrieval，并把 diagnostics 写回文档 metadata。 |
| `reference_serializer.py` | 过滤低相关片段，格式化 prompt context，并序列化前端 Sources。 |
| `diagnostics.py` | 管理 retrieval settings 子阶段 diagnostics、RAG timing 合并和 LLM token usage 解析。 |
| `streaming.py` | 将 LCEL stream chunk 转换为 SSE 事件，包括 retrieval、sources、llm_usage 和 answer。 |

拆分后 SSE 字段名、`messages.sources`、`messages.retrieval` 和现有导入入口保持兼容。

助手消息会保存：

- `sources`：回答引用的文件、chunk、分数和检索来源。
- `retrieval`：最终是否检索、Router LLM 原始判断、规则覆盖原因、改写问题、召回数量、降级状态和诊断信息。

前端可使用 source 中持久化的 `file_id + chunk_index + index_version` 调用 chunk 上下文 API，从 PostgreSQL 精确读取目标 chunk 和相邻正文；source 同时携带 PDF 页码或 DOCX 段落范围。旧 source 缺少 `index_version` 时回退到最新可用 chunk 版本。该能力用于引用核验，不重新执行 embedding、全文检索或 rerank；旧 source 缺少文件/chunk 定位字段、文件已永久删除或重新索引后指定版本不再存在时安全返回不可用状态。

诊断展示应区分三类信息：

| 类型 | 字段 | 说明 |
| --- | --- | --- |
| 决策 | `final_need_retrieval` / `need_retrieval` | 后端最终是否执行知识库检索。 |
| Router 判断 | `llm_need_retrieval`、`llm_reason` | LLM Router 对本轮问题是否需要检索的原始判断与原因。 |
| 规则覆盖 | `override_applied`、`override_reason` | 后端确定性规则是否覆盖 Router 判断，例如命中知识库文件画像。 |
| 召回排序 | `diagnostics.vector_count`、`fulltext_count`、`fused_count`、`reranked_count` | vector/fulltext 召回数量、RRF 融合后数量和 rerank 精排后数量。 |
| 召回降级 | `vector_degraded`、`fulltext_degraded`、`vector_errors`、`fulltext_errors` | 单路粗召回失败时的降级状态和错误摘要，另一通道仍可兜底。 |
| 阶段耗时 | `diagnostics.timing.*_ms` | 问题改写、Router、检索、RRF、rerank、首 token 和整体流式回答耗时，单位毫秒。 |
| 画像缓存 | `knowledge_profile_cache_hit`、`knowledge_profile_cache_source`、`knowledge_profile_indexed_file_count` | 本轮知识库画像是否命中 Redis 或进程内 fallback 短 TTL 缓存，以及画像中的已索引文件数量。 |
| 设置缓存 | `retrieval_settings_cache_hit`、`retrieval_settings_source`、`retrieval_settings_cache_backend` | 本轮知识库检索设置是否命中缓存、设置来源，以及缓存后端是 Redis 还是进程内 fallback。 |
| Query embedding 缓存 | `query_embedding_cache_hit`、`query_embedding_cache_source`、`query_embedding_cache_ttl_seconds` | 向量粗召回是否复用短 TTL query embedding 缓存；Redis 用于多实例共享，进程内缓存用于本实例快速命中，不缓存回答或最终检索结果。 |
| LLM 配置 | `diagnostics.llm.provider`、`model`、`credential_mode`、`temperature`、`max_tokens` | 本轮实际使用的模型厂商、模型名、凭据来源和生成参数，不包含 API Key。 |
| 最终引用 | `retrieval_sources`、`sources` | 最终展示给用户的引用片段及这些片段命中的召回通道。 |

常见耗时字段：

- `standalone_question_ms`：生成独立问题阶段耗时。
- `retrieval_settings_ms`：LCEL 外层观察到的 retrieval settings 阶段耗时，可能包含上游 Runnable 调度等待。
- `retrieval_settings_load_total_ms`：后端实际读取并规范化 retrieval settings 的总耗时。
- `retrieval_settings_query_ms`：查询知识库检索配置的数据库耗时。
- `retrieval_settings_normalize_ms`：合并默认值并规范化检索配置的耗时。
- `knowledge_profile_ms`：构建知识库文件画像耗时。
- `query_router_ms`：Query Router 判断耗时。
- `finalize_decision_ms`：规则覆盖和最终检索决策耗时。
- `retrieve_documents_ms`：执行检索阶段耗时。
- `embedding_ms`、`vector_ms`、`fulltext_ms`、`rrf_ms`、`rerank_ms`：混合检索内部阶段耗时。
- `pre_answer_total_ms`：开始生成回答前的总耗时。
- `first_answer_token_ms`：从后端开始处理到首个回答 token 的耗时。

当 RRF 融合后的候选数量不超过最终 `top_k` 时，后端会跳过 rerank，
并在 diagnostics 中写入 `rerank_skipped=true` 与 `rerank_skip_reason`。该策略用于避免
小候选集场景下的无收益精排开销；候选数超过 `top_k` 时仍会执行 rerank。

向量检索和全文检索在 hybrid retrieval 中并行执行。任一路粗召回失败时，失败通道会
降级为空候选并写入对应 degraded/error diagnostics，另一通道的候选仍会进入 RRF 和后续
rerank 流程。

知识库文件画像和已索引文件 ID 使用 Redis 优先短 TTL 缓存，默认用于减少同一知识库在
连续对话中的重复数据库查询；Redis 不可用时回退到进程内缓存。文件上传、知识库文件关联
变化、向量化状态变化和删除向量结果会主动失效相关缓存；TTL 负责兜底处理未覆盖的边界场景。

知识库 retrieval settings 也使用 Redis 优先短 TTL 缓存，默认用于减少聊天和本地问候
短路判断中的重复设置查询；Redis 不可用时回退到进程内缓存。更新 retrieval settings 后会
主动失效对应知识库缓存，下一轮聊天会立即读取新配置；TTL 负责兜底处理未覆盖的边界场景。

query embedding 使用 Redis + 进程内短 TTL 缓存，key 由用户 ID、embedding provider、model、
维度和归一化后的 query 组成，用于减少 eval 重跑、短时间重复问题和多轮相近测试对
embedding provider 的重复调用。缓存只保存 query embedding；embedding 生成失败不会写入缓存，
后续请求仍可重试。

Redis 不保存会话记录、assistant 回答、sources 或最终检索结果，这些长期数据仍由
PostgreSQL 的 `conversations`、`messages` 和相关 JSON 字段持久化。Redis 故障只影响缓存命中、
限流和 worker 运行态可见性，不应导致已保存会话丢失。

Rerank provider 由当前登录用户的 `user_rerank_settings` 决定；远程 provider 的 API Key
按 `(user_id, provider)` 保存到 `user_rerank_provider_credentials`。本地 provider 不需要
API Key；远程 provider 只在服务端调用时临时解密，前端只能看到 `has_api_key` 与
`api_key_hint`。
- `answer_stream_ms`：首个回答 token 后到回答完成的流式耗时。
- `chat_stream_total_ms`：本轮后端流式回答总耗时。

`diagnostics.llm` 当前会记录：

- `provider`：实际使用的模型厂商。
- `model`：实际使用的模型名。
- `credential_mode`：当前版本固定为 `user`；历史 `platform` 数据会提示用户到设置页配置当前账号 API Key。
- `base_url`：实际请求的 OpenAI-compatible 地址。
- `temperature`、`max_tokens`、`timeout_seconds`、`max_retries`：本轮生成参数。
- `prompt_tokens`、`completion_tokens`、`total_tokens`：Token 用量。当前兼容流式链路拿不到 usage 时为 `null`。

前端可通过：

```http
GET /chat/conversations/{conversation_id}/diagnostics
```

恢复历史会话的检索状态。

# RAG 核心流程

本文说明 FirstRAG 的文件入库、检索和回答生成流程。

## 文件入库

1. 用户在前端上传文件到某个知识库。
2. Next.js API Route 代理到 `POST /chat/knowledge-base/{knowledge_base_id}/files`。
3. 后端计算 SHA-256 和文件大小。
4. 若同一用户已上传过相同内容，则复用 `knowledge_files` 记录，只补充知识库关联。
5. 新文件保存到根目录 `uploads/users/{user_id}/{hash_prefix}/{file_id}/source.ext`。
6. `auto_index=true` 时创建 `vector_index_jobs` 任务。

## 向量化任务

1. `vector_index_worker` 领取 `queued` 任务。
2. 使用 PostgreSQL advisory lock 避免同一文件并发索引。
3. `document_service` 加载 PDF、Markdown 或文本内容。
4. 文本切分为 chunk。
5. 智谱 embedding 生成向量。
6. Chroma 保存向量。
7. PostgreSQL `knowledge_file_chunks` 保存 chunk 正文和 metadata，用于全文检索。
8. 更新文件状态和任务状态。

## 聊天生成

1. 前端发送 `POST /api/chat`，代理到后端 `POST /chat`。
2. 后端校验会话属于当前用户和知识库。
3. 问候类本地可回答内容直接走本地响应，避免额外模型调用。
4. 普通问题加载历史消息，构建 RAG 链。
5. `rag_service` 读取当前知识库的 retrieval settings，判断是否需要检索，并可改写多轮问题。
6. 召回候选片段：
   - Chroma 向量检索。
   - PostgreSQL 全文检索。
   - RRF 融合多路结果。
   - CrossEncoder reranker 精排。
7. DeepSeek 或用户配置的 OpenAI 兼容模型流式生成回答。
8. SSE 返回 token、sources、retrieval 诊断。
9. 回答完成后持久化到 `messages`。

知识库级 retrieval settings 可通过
`GET/PATCH /chat/knowledge-base/{knowledge_base_id}/retrieval-settings`
读写，当前支持：

- `retrieval_mode`：`auto`、`always`、`never`。
- `enable_query_router`：是否调用 Router LLM 判断本轮是否检索。
- `enable_rerank`：是否启用 CrossEncoder rerank。
- `top_k`、`vector_top_k`、`fulltext_top_k`、`rrf_k`：控制最终引用数、两路召回数和 RRF 候选池。
- `rerank_score_threshold`：控制低相关片段是否进入上下文和 Sources。

## 检索诊断

助手消息会保存：

- `sources`：回答引用的文件、chunk、分数和检索来源。
- `retrieval`：最终是否检索、Router LLM 原始判断、规则覆盖原因、改写问题、召回数量、降级状态和诊断信息。

诊断展示应区分三类信息：

| 类型 | 字段 | 说明 |
| --- | --- | --- |
| 决策 | `final_need_retrieval` / `need_retrieval` | 后端最终是否执行知识库检索。 |
| Router 判断 | `llm_need_retrieval`、`llm_reason` | LLM Router 对本轮问题是否需要检索的原始判断与原因。 |
| 规则覆盖 | `override_applied`、`override_reason` | 后端确定性规则是否覆盖 Router 判断，例如命中知识库文件画像。 |
| 召回排序 | `diagnostics.vector_count`、`fulltext_count`、`fused_count`、`reranked_count` | vector/fulltext 召回数量、RRF 融合后数量和 rerank 精排后数量。 |
| 阶段耗时 | `diagnostics.timing.*_ms` | 问题改写、Router、检索、RRF、rerank、首 token 和整体流式回答耗时，单位毫秒。 |
| LLM 配置 | `diagnostics.llm.provider`、`model`、`credential_mode`、`temperature`、`max_tokens` | 本轮实际使用的模型厂商、模型名、凭据来源和生成参数，不包含 API Key。 |
| 最终引用 | `retrieval_sources`、`sources` | 最终展示给用户的引用片段及这些片段命中的召回通道。 |

常见耗时字段：

- `standalone_question_ms`：生成独立问题阶段耗时。
- `retrieval_settings_ms`：读取知识库检索配置耗时。
- `knowledge_profile_ms`：构建知识库文件画像耗时。
- `query_router_ms`：Query Router 判断耗时。
- `finalize_decision_ms`：规则覆盖和最终检索决策耗时。
- `retrieve_documents_ms`：执行检索阶段耗时。
- `embedding_ms`、`vector_ms`、`fulltext_ms`、`rrf_ms`、`rerank_ms`：混合检索内部阶段耗时。
- `pre_answer_total_ms`：开始生成回答前的总耗时。
- `first_answer_token_ms`：从后端开始处理到首个回答 token 的耗时。
- `answer_stream_ms`：首个回答 token 后到回答完成的流式耗时。
- `chat_stream_total_ms`：本轮后端流式回答总耗时。

`diagnostics.llm` 当前会记录：

- `provider`：实际使用的模型厂商。
- `model`：实际使用的模型名。
- `credential_mode`：`platform` 或 `user`。
- `base_url`：实际请求的 OpenAI-compatible 地址。
- `temperature`、`max_tokens`、`timeout_seconds`、`max_retries`：本轮生成参数。
- `prompt_tokens`、`completion_tokens`、`total_tokens`：Token 用量。当前兼容流式链路拿不到 usage 时为 `null`。

前端可通过：

```http
GET /chat/conversations/{conversation_id}/diagnostics
```

恢复历史会话的检索状态。

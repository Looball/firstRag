# ADR-0002：使用 BGE-M3 sparse 将混合检索统一到 Milvus

- 状态：`Accepted`
- 决定日期：2026-08-11
- 对应任务：`T-140` 至 `T-144`
- 当前运行时：Milvus 3.0.0 + PyMilvus 3.0.1，dense only；本 ADR 不在 T-140 立即切换读写
- 基线证据：[PostgreSQL full-text 退出基线](../evals/bge_m3_sparse_baseline_20260811.md)

## 背景

FirstRAG 当前把 chunk dense embedding 写入 Milvus，同时把正文写入 PostgreSQL；查询时并行执行 Milvus dense ANN 与 PostgreSQL full-text，再由应用层 RRF 融合。企业内部场景希望让向量和关键词召回统一由 Milvus 管理，并明确选择 BGE-M3 learned sparse embedding，而不是 Milvus 内置 BM25。

本次变更只替换关键词召回职责。现有用户级 dense embedding provider、Cross-Encoder rerank、SSE sources、retrieval diagnostics、PostgreSQL chunk/source context、权限隔离和异步 indexing 契约继续保留。

## 决策摘要

| 主题 | 决策 |
| --- | --- |
| Sparse 模型 | `BAAI/bge-m3` |
| Model revision | `5617a9f61b028005a4858fdac845db406aefb181` |
| License | MIT |
| 推理实现起始 pin | `FlagEmbedding==1.4.0`；T-141 构建验证后连同完整 lock/pin 固定 |
| Dense embedding | 继续使用登录用户保存的 Qwen/Zhipu/OpenAI/Voyage/Cohere/Jina/OpenAI-compatible provider |
| Sparse embedding | BGE-M3 `lexical_weights`，文档和 query 使用同一固定 revision |
| Sparse 存储 | Milvus `SPARSE_FLOAT_VECTOR` |
| Sparse index / metric | `SPARSE_INVERTED_INDEX` + `IP` |
| Dense index / metric | 保持 `HNSW` + `COSINE` |
| 融合 | Milvus `hybrid_search()` + `RRFRanker`，随后保留现有 Cross-Encoder rerank |
| 推理拓扑 | 单独的 Compose 内网 `sparse-encoder` service，backend/worker 不重复加载模型 |
| PostgreSQL | 保留 chunk/source context 与对账；移除 full-text/trigram 召回和仅为召回存在的 indexes |
| Rollout | 新 collection identity + 维护窗口全量重建；不原地修改或混用旧 dense-only collection |

BGE-M3 官方 model card 声明模型支持 dense、sparse 和 ColBERT 三种检索模式、100 多种语言和最长 8192 tokens；本阶段只启用 `lexical_weights`，不引入 ColBERT。固定 revision 的 `pytorch_model.bin` 为 2,271,145,830 bytes，另有 tokenizer 与小型 projection 文件；实际容器镜像、加载内存、冷启动和 CPU/GPU 性能由 T-141/T-144 实测，不能只按权重文件大小估算。

参考：

- [BAAI/bge-m3 model card](https://huggingface.co/BAAI/bge-m3)
- [Milvus sparse vector](https://milvus.io/docs/sparse_vector.md)
- [Milvus multi-vector hybrid search](https://milvus.io/docs/multi-vector-search.md)

## 为什么不使用 Milvus BM25 Function

Milvus BM25 能以更低的运行成本在 server 内生成 sparse vector，但本次产品决策明确选择 learned sparse retrieval。BGE-M3 的 token weights 由模型学习得到，能够与当前中文、英文、技术术语和代码片段混合语料使用同一 vocabulary；代价是增加约 2.3 GB 模型下载、推理内存、冷启动和内部服务运维。

BGE-M3 输出不是 BM25 统计量，因此：

- schema 不增加 `FunctionType.BM25`；
- sparse index 的 metric 使用 `IP`，不得写成 `BM25`；
- document/query 必须由完全相同的 model revision 和 tokenizer 生成；
- sparse 模型变更必须形成新的 collection identity 并全量重建。

## 推理服务边界

```text
worker  ─┐
         ├─ HTTP / internal Compose network ─> sparse-encoder
backend ─┘                                  └─ BGE-M3 loaded once
```

- `sparse-encoder` 不声明 host port，只允许 Compose service 访问。
- API 区分 document batch 与单 query；响应只返回 `{token_id: weight}`，不返回 token 文本。
- 默认 `max_length=1024`。当前 chunk splitter 为 1000 characters，基线最大 chunk 为 2777 UTF-8 bytes；提高到 8192 前必须重新测量内存和尾延迟。
- CPU 默认 `use_fp16=false`；CUDA 环境才允许显式开启 FP16，并必须记录设备与精度差异。
- 服务限制 batch、文本长度、请求体和并发；日志只记录 count、token count、耗时、model identity 和错误分类，不记录企业正文。
- readiness 必须在模型加载后完成一次固定非敏感文本的真实 sparse inference；仅 HTTP 200 或进程存活不能视为 ready。
- 模型按固定 revision 预下载到只读模型目录或持久 cache。生产可设置 offline 模式，启动时不得静默漂移到最新 main。
- backend/worker 对 encoder 设置有限超时和错误分类。indexing 时 sparse 失败使整个文件 job 失败并补偿；query 时 sparse 失败允许 dense-only 降级并写入 diagnostics。

## CI 与真实模型门禁

每次 required CI 都下载并加载 2.3 GB 模型会造成不稳定的外部网络和运行成本，因此测试分两层：

1. 单元测试和 credential-free full-stack E2E 使用同一 HTTP 契约的确定性 fixture encoder，覆盖 schema、写入、hybrid search、隔离、降级和 diagnostics；fixture 不得在 production 配置中启用。
2. T-141/T-144 必须在 Compose 中加载固定 revision 的真实 BGE-M3，运行真实 document/query sparse self-hit、中文/英文/技术标识符样本、restart persistence、资源和质量验收。模型 revision 或运行时依赖变化后必须重跑真实门禁。

fixture 通过不能替代真实 BGE-M3 验收；真实门禁结果记录在版本化 eval 报告中。

## Collection identity 与 schema

现有 identity 为：

```text
user_id | dense_provider | dense_model | dense_dimensions
```

新 identity 增加 sparse 模型与 schema version：

```text
user_id | dense_provider | dense_model | dense_dimensions
| sparse_provider=bge_m3 | sparse_model=BAAI/bge-m3
| sparse_revision=5617a9f... | schema=v2
```

新 collection 使用独立 digest，旧 dense-only collection 不原地加字段。每条 entity schema：

| 字段 | Milvus 类型 | 说明 |
| --- | --- | --- |
| `chunk_id` | `VARCHAR(192)` | child stable primary key，格式为 `{parent_id}:c{child_index}` |
| `embedding` | `FLOAT_VECTOR(dim)` | 当前用户 dense provider 输出 |
| `sparse_embedding` | `SPARSE_FLOAT_VECTOR` | BGE-M3 lexical weights；至少一个非零、index 为非负整数、weight 为有限非负 float |
| `content` | `VARCHAR(65535)` | chunk 正文 |
| `user_id` / `file_id` / `chunk_index` / `index_version` | scalar | 权限、范围和生命周期 |
| `parent_id` / `parent_index` / `child_index` | scalar | parent 聚合、child 去重和上下文扩展 |
| `metadata` | `JSON` | source/OCR/location metadata |

写入前分别校验 dense 与 sparse；两者均生成成功后才删除旧 entities 和 upsert。写后门禁同时执行同 user/file dense top-1 self-hit 与 sparse top-1 self-hit，随后再写 PostgreSQL chunks 并发布 `indexed`。

## Parent/child chunk 契约

T-145 在 v2 schema 写入前固定以下边界：

- Markdown 标题、PDF page、DOCX 标题/段落组优先形成 parent；无可靠结构时以 `2000` 字符、`0` overlap 递归切分 parent。
- 每个 parent 内以 `600` 字符、`100` overlap 切分 child，禁止 overlap 跨 parent；只有 child 生成 dense 与 sparse vector。
- parent ID 为 `{user_id}:{file_id}:v{index_version}:p{parent_index}`，child ID 为 `{parent_id}:c{child_index}`；全局 `chunk_index` 继续兼容 source feedback 和预览 API。
- PostgreSQL `knowledge_file_chunk_parents` 保存 parent 正文，`knowledge_file_chunks.parent_id` 外键保存 child 归属；PostgreSQL 可以提供 source/context，但 T-144 后不参与候选召回或关键词排序。
- T-143 的在线顺序固定为 Milvus child hybrid search、按 parent 限流去重、Cross-Encoder 精排 child、扩展 parent 正文、按 context budget 截断。T-145 只建立数据与 identity 契约，不提前宣称该在线切流已完成。

## Hybrid search 与 diagnostics

一次 Milvus `hybrid_search()` 包含两个 `AnnSearchRequest`：

- dense request：query dense embedding、`anns_field=embedding`、`COSINE`；
- sparse request：query BGE-M3 lexical weights、`anns_field=sparse_embedding`、`IP`；
- 两路使用完全相同的 `user_id` 与可选 `file_id` scalar filter；
- 使用 `RRFRanker` 融合，返回后再次复核 user/file scope；
- 融合候选继续进入现有 Cross-Encoder rerank。

配置/API 将 `fulltext_top_k` 迁移为 `sparse_top_k`，保留一个受控兼容窗口；diagnostics 同步迁移为 `dense_count`、`sparse_count`、`dense_degraded`、`sparse_degraded` 和对应 timing/error。历史消息和 eval 中的 `vector/fulltext` 字段不改写，新消息只写新口径。

query dense 与 sparse 分别缓存。Sparse cache identity 至少包含 model repo、revision、max_length 和规范化 query hash；不得只使用 dense provider identity。

## PostgreSQL 退出关键词检索

T-144 删除：

- `search_chunks()` 的 `to_tsvector` / `websearch_to_tsquery` / `ILIKE` 排序查询；
- `fulltext_retriever.py`；
- `idx_knowledge_file_chunks_search` expression GIN index；
- `idx_knowledge_file_chunks_content_trgm`，前提是全仓静态检查确认无其它业务查询依赖。

`knowledge_file_chunks` 表及其 user/file/version indexes 保留，用于 source context、引用核验、索引 identity 审计、OCR history 衔接和失败补偿。删除索引通过新增 migration 完成，不改写历史 migration。

## Rollout 与 rollback

1. T-141 接入 encoder service 与契约测试，不切现有 retrieval。
2. T-142 在 feature flag 后实现 v2 schema/write，默认仍使用现有 dense-only collection。
3. T-143 实现 Milvus hybrid search 和新 diagnostics，仍不对未重建数据切流。
4. T-144 进入维护窗口：暂停新 indexing、等待 active jobs 为 0、备份 Milvus/PostgreSQL、创建 v2 collections、从源文件重新生成 dense+sparse、逐文件验收。
5. current IDs/count、dense/sparse self-hit、隔离、真实 RAG/indexing eval 和 restart persistence 全部通过后切换默认。
6. 观察期内保留旧 dense-only collections；rollback 只切回旧读路径，不把 v2 数据反向覆盖旧 schema。

由于 sparse vector 无法从旧 dense embedding 推导，迁移必须重新读取源文件并调用当前用户 dense provider，同时调用 BGE-M3。缺少源文件或 dense credential 的文件进入明确失败清单，不能只生成 sparse 后发布半成品。

## 验收门禁

- PostgreSQL current chunk IDs 与 v2 Milvus entities 完全一致，missing/unexpected 均为 0。
- 每个文件至少一次 dense 与 sparse filtered top-1 self-hit；跨用户和非目标文件返回 0。
- 真实中文、英文、数字/版本号和代码标识符 query 都能产生非空 sparse vector，并命中预期 fixture。
- 14-case RAG eval 全部通过；目标文件命中和 sources 不低于冻结基线。
- indexing eval 必须证明新文件通过 sparse 或 dense 通道进入最终 source，不能只检查 job `succeeded`。
- 记录模型下载体积、冷启动、首次/热 query P50/P95、批量 indexing throughput、峰值内存和 CPU/GPU。
- encoder 不可用时 indexing 明确失败并可重试；在线 query dense-only 降级且 diagnostics 可见。
- Docker Compose build/health/log、全量 backend/frontend、credential-free E2E、Milvus restart、备份恢复和 production preflight 通过。

## 后果

正面影响：

- dense、sparse、scalar filter 和 RRF 统一由 Milvus 执行，删除 PostgreSQL 关键词召回双存储编排。
- BGE-M3 learned sparse 对中文、多语言和技术词汇使用统一模型 vocabulary。
- 单独 encoder service 只加载一次模型，并为以后 GPU 化或横向扩容保留边界。

成本与限制：

- 增加大型模型下载、镜像/缓存、冷启动、推理内存和内部服务故障面。
- 首次全量重建必须再次调用用户 dense provider，存在费用和限流。
- 当前 Docker Desktop 约 15.35 GiB，只适合小规模开发验收；真实 BGE-M3 与 Milvus 并行峰值可能超过舒适余量，T-141/T-144 必须实测后再决定默认资源限制。
- 本阶段不使用 BGE-M3 dense 或 ColBERT 输出；未来若替换用户 dense provider，需要独立 ADR 和质量迁移。

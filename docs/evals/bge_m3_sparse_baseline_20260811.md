# BGE-M3 sparse 迁移基线（2026-08-11）

本报告冻结 T-140 开始时 PostgreSQL full-text + Milvus dense + 应用层 RRF 的当前状态。检查不修改业务数据，不读取或输出 API Key、JWT、密码、正文或 embedding 数值。

## Git 与运行数据

| 项目 | 基线 |
| --- | --- |
| Git | `main@badd89a`，PR #60 合并后 |
| Milvus | `milvusdb/milvus:v3.0.0` |
| PyMilvus | `3.0.1` |
| PostgreSQL chunks | 119 |
| active vector index jobs | 0 |
| FirstRAG Milvus collections | 1 |
| Milvus entities | 121 |
| Current collection | `firstrag_u1_4aecfb85286f` |
| Current vector schema | dense `FLOAT_VECTOR` only，HNSW + COSINE |

PostgreSQL 与 Milvus 数量相差 2 不直接定义为异常：Milvus collection 可能包含 probe 或与 PostgreSQL current scope 不同的生命周期记录。T-144 必须按 stable ID/current file scope 做精确集合对账，不能用汇总 count 猜测迁移完成。

## 当前关键词召回实现

```text
query
  ├─ 当前用户 embedding provider -> Milvus dense ANN
  └─ PostgreSQL to_tsvector/websearch_to_tsquery + ILIKE boosts
        -> application reciprocal_rank_fusion
        -> optional Cross-Encoder rerank
```

PostgreSQL 当前职责：

- `knowledge_file_chunks.content` 保存 chunk 正文。
- `idx_knowledge_file_chunks_search` 为 `to_tsvector('simple', content)` expression GIN index。
- `idx_knowledge_file_chunks_content_trgm` 为 `content gin_trgm_ops` GIN index。
- `search_chunks()` 使用 `ts_rank_cd`、`websearch_to_tsquery('simple', query)`、token `ILIKE` 和完整 query `ILIKE` 计算 `fulltext_score`。
- `hybrid_retriever.py` 在线程池并行执行 Milvus vector 与 PostgreSQL full-text，再调用应用层 `reciprocal_rank_fusion()`。

## 待迁移契约

| 当前名称 | 当前含义 | 目标名称/含义 |
| --- | --- | --- |
| `fulltext_top_k` | PostgreSQL lexical 候选数 | `sparse_top_k`，Milvus BGE-M3 sparse 候选数 |
| `vector_count` | Milvus dense 候选数 | `dense_count` |
| `fulltext_count` | PostgreSQL lexical 候选数 | `sparse_count` |
| `vector_degraded/errors` | dense/embedding/Milvus 失败聚合 | `dense_degraded/errors` |
| `fulltext_degraded/errors` | PostgreSQL lexical 失败 | `sparse_degraded/errors` |
| `vector_score` | `1 - cosine similarity`，越小越近 | 暂保留兼容字段；新增明确 dense rank/score 语义 |
| `fulltext_score` | PostgreSQL `ts_rank_cd + ILIKE boosts` | 不复用；BGE-M3 sparse 使用 IP，最终以 rank/RRF 为主 |
| `retrieval_sources=vector/fulltext` | 两路应用层召回 | 新消息使用 `dense/sparse`；历史记录不改写 |

受影响的生产路径至少包括 retrieval settings repository/schema/API、RAG retrieval pipeline、reference serialization、conversation source preview、eval scripts、前端 diagnostics parser、教程和部署文档。迁移期间必须通过明确兼容层处理旧消息和旧 settings，不能直接让历史 JSON 解析失败。

## 测试基线

使用当前正式 backend 镜像只读挂载工作区，运行：

```bash
docker compose run --rm --no-deps \
  -v /Users/bing/Desktop/Github/FirstRAG:/workspace:ro \
  backend sh -c \
  'cd /workspace/backend && PYTHONPATH=/workspace python -m unittest \
    tests.test_retrieval_resilience \
    tests.test_knowledge_base_retrieval_settings \
    tests.test_rag_service \
    tests.test_eval_rag_script \
    tests.test_eval_indexing_script'
```

结果：54/54 通过。覆盖当前 vector/full-text 并行召回、单路失败降级、应用层 RRF、settings、SSE/persistence diagnostics 和 eval 口径。

## 历史真实质量对照

- 当前内置 RAG eval：14 cases。
- 2026-07-20 最新版本化报告：14/14 通过，平均引用 3.36、平均 hybrid retrieval 528.14ms。
- T-136 Milvus 验收：真实 RAG 14/14，`vector_degraded=false`，平均 hybrid retrieval 710.62ms；该值来自后续 Milvus 验收环境，作为当前 vector store 对照。
- T-137 current-data 验收：19 files / 119 entries，35/35 Top-1 一致、最低 Top-K overlap 1.0、filtered ANN self-hit 10/10。

这些指标属于不同日期和运行环境，只作为冻结门槛来源，不能伪装成同一次严格性能对比。T-144 必须在同一环境、同一数据和同一 query 集上重跑旧/新链路，报告 cold/warm 状态。

## BGE-M3 固定输入

| 项目 | 决策 |
| --- | --- |
| repo | `BAAI/bge-m3` |
| revision | `5617a9f61b028005a4858fdac845db406aefb181` |
| license | MIT（以固定 revision model card 为准） |
| dense dimension | 1024；本阶段不使用 BGE-M3 dense 输出 |
| max sequence | 模型支持 8192；FirstRAG 初始限制 1024 |
| weight file | `pytorch_model.bin` 2,271,145,830 bytes |
| runtime starting pin | `FlagEmbedding==1.4.0` |

固定非敏感验收文本至少覆盖：

- 中文：`向量数据库支持企业知识检索`；
- 英文：`hybrid retrieval combines dense and sparse vectors`；
- 技术标识符：`MILVUS_URI text-embedding-v4 RRF-60`；
- 空白、超长和重复文本的错误/稳定性边界。

## 迁移门禁

详细决策见 [ADR-0002](../adr/0002-bge-m3-sparse-milvus-hybrid.md)。最小门禁：

- 新 collection current stable IDs 与 PostgreSQL 完全一致。
- dense 与 sparse filtered self-hit、跨用户/文件隔离全部通过。
- 14-case RAG eval 和 indexing eval 不低于当前质量基线。
- PostgreSQL full-text 查询路径从生产代码移除，但 chunk/source context 继续可用。
- 真实 BGE-M3 的模型下载、启动、推理、资源、restart 和 offline cache 均有版本化证据。

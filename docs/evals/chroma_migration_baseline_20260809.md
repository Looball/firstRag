# Chroma 迁移基线（2026-08-09）

本报告冻结 T-130 执行时可与 Milvus 对照的 Chroma 状态。检查均为只读；没有删除、重建或修改 Chroma/PostgreSQL 数据，也没有读取或输出用户 API Key、JWT、密码、正文或 embedding 数值。

## 运行环境

| 项目 | 值 |
| --- | --- |
| Git 基线 | `main@af559ea`（PR #51） |
| Chroma image | `chromadb/chroma:1.5.9` |
| Chroma 拓扑 | 独立 Compose service，backend/worker 使用 HTTP client |
| Docker Desktop | 29.5.3 / Apple Silicon / 8 vCPU / 16,484,397,056 bytes RAM |
| 宿主工作盘 | 460 GiB，已用 388 GiB，剩余 44 GiB |
| Chroma bind data | 10 MiB |
| uploads | 19 MiB |
| Docker images | 53.07 GB |
| Docker build cache | 26.71 GB |

Milvus Standalone 官方最低 RAM 为 8 GiB、推荐 16 GiB，CPU 推荐至少 4 cores。当前 Docker VM 满足最低要求，但约 15.35 GiB RAM 只在推荐线附近，而且还要同时运行 PostgreSQL、Redis、backend、worker 和 frontend；迁移后的 quickstart 必须做资源门禁。

## PostgreSQL 事实集合

| 指标 | 当前值 |
| --- | ---: |
| 未软删除文件 | indexed=19，pending=1 |
| `knowledge_file_chunks` | 119 |
| 有 chunk 的文件 | 19 |
| 有 chunk 的用户 | 1 |
| `index_version` | 0、2 |
| 最大正文 UTF-8 bytes | 2,777 |
| 最大 metadata JSON bytes | 745 |
| embedding settings | qwen / text-embedding-v4 / dimensions 未显式保存 |

`dimensions` 未显式保存不代表向量维度未知；实际 collection embedding inspection 显示 current collection 为 1024 维。T-131/T-135 需要从 collection 实际维度和 provider settings 双重校验，不能把 NULL/0 当作可接受的任意维度。

## Chroma collections

| Collection | Entries | Users | Files | Dim | PG ID/正文/核心 metadata 匹配 | 最大正文 bytes | 最大 metadata bytes |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| `langchain` | 216 | 3 | 7 | 2048 | 0 / 0 / 0 | 2,777 | 488 |
| `langchain-u1-4aecfb85286f` | 119 | 1 | 19 | 1024 | 119 / 119 / 119 | 2,777 | 745 |

核心 metadata 匹配字段为 `user_id`、`file_id`、`chunk_index`、`index_version`。跨 collection 汇总：

- PostgreSQL current IDs 在 Chroma 中存在：119/119。
- PostgreSQL IDs 缺失：0。
- Chroma IDs 不在当前 PostgreSQL：216，全部来自 legacy `langchain` collection。
- current collection 与 PostgreSQL 的正文和核心 metadata 均 119/119 完全一致。

结论：迁移只导入 119 条 current entries。legacy 216 条定义为历史孤儿数据，只归档、不迁移；不能用它们恢复当前 PostgreSQL 已不存在的文件关系。

## Metadata schema 观察

current collection 实际出现的 metadata keys：

```text
chunk_index, content_format, file_id, file_name, file_type, h1, h2,
index_version, location_type, ocr_attempt, ocr_candidate_count,
ocr_confidence, ocr_dpi, ocr_engine, ocr_languages, ocr_preprocessing,
ocr_psm, ocr_quality, ocr_rotation, ocr_strategy, ocr_text_source,
ocr_word_count, page_count, page_index, page_number, pdf_parse_method,
source, user_id
```

Milvus schema 因此把权限、生命周期和定位所需的字段做成显式 scalar，把其余可变字段保留为 JSON；不启用 dynamic field。

## 真实 filtered ANN

检查方法：每个 collection 读取一个已持久化 embedding，以它作为 query embedding，带相同 `user_id + file_id` filter 连续查询 10 次，要求 top-1 ID 等于自身。该检查不调用外部 embedding provider，不以 collection count 替代 ANN。

| Collection | 10/10 self-hit | Min | Median | P95 | Max |
| --- | --- | ---: | ---: | ---: | ---: |
| `langchain` | 通过 | 1.98ms | 2.29ms | 2.97ms | 2.97ms |
| `langchain-u1-4aecfb85286f` | 通过 | 1.65ms | 1.73ms | 2.28ms | 2.52ms |

这是本机、335 条数据、warmed stored-vector query 的直接 ANN 微基线，不包含 query embedding、PostgreSQL full-text、RRF、rerank 或 LLM 网络耗时，不能外推为生产容量指标。

## 生命周期与检索契约

2026-08-09 本地针对性 unittest：83 项通过，覆盖：

- 上传类型、MIME、size/count/storage quota 和 SHA-256 去重边界。
- 单文件 enqueue、batch quota、worker lock、重复任务、失败状态和安全错误。
- stable chunk ID、HTTP/embedded Chroma client、OCR reindex/correction 与 `index_version`。
- 文件权限、向量删除、永久删除和失败补偿。
- user/file metadata filter、HNSW 短暂不可见重试、用户级 fallback、direct embedding scan、跨文件跳过。
- vector/full-text 并行粗召回、RRF 去重、rerank 降级、query embedding cache 和 diagnostics。
- indexing eval 必须验证 vector channel 和 `vector_degraded=false`，不能只看 job 状态。

运行命令：

```bash
cd backend
conda run -n firstrag python -m unittest \
  tests.test_vector_indexes \
  tests.test_knowledge_files \
  tests.services.test_vector_index_service \
  tests.test_vector_index_worker \
  tests.test_vector_index_failure_recovery \
  tests.test_retrieval_resilience \
  tests.test_eval_indexing_script \
  tests.test_eval_rag_script -v
```

## E2E 与真实 eval 基线

### Credential-free full-stack E2E

PR #51 的 clean GitHub runner 已通过 `Full-stack E2E`，真实覆盖隔离 PostgreSQL、Chroma、注册/登录、TXT 上传、worker 向量化、SSE 回答和 sources，并自动清理临时数据。

本机在 T-130 中再次执行 `scripts/run_full_stack_e2e.sh`，但 backend runtime build 从清华 Debian mirror 下载 `libgif7` 时返回 502，未进入应用测试；同一提交的 GitHub clean runner 已通过，因此将本地结果记录为外部镜像故障，不记录为产品回归。

### 最近真实 RAG eval

[`latest_rag_eval_report.md`](latest_rag_eval_report.md) 记录 2026-07-20 17:04 的真实 provider 基线：

- 14/14 case 通过，失败 case 为 0。
- 平均总耗时 3.83s，平均 first token 1752.67ms。
- 平均 hybrid retrieval 528.14ms，平均 rerank 399.79ms。
- 主检索 case 同时包含 full-text 与 vector channel，`vector_degraded=false`。
- 14/14 是 case 通过数，不是标准 Recall@K。

### 最近真实 indexing eval：negative control

[`latest_indexing_eval_report.md`](latest_indexing_eval_report.md) 随后在 2026-07-20 17:05 运行：upload、文件关联、job `succeeded`、文件 `indexed`、PostgreSQL/full-text 命中和答案 keyword 均成功，但目标文件的 Chroma 单文件 ANN 失败：

- `vector_degraded=true`。
- 目标 source 只有 `fulltext`，没有 `vector`。
- 整体结果为未通过。

这个报告证明“job succeeded”不能替代 similarity search 验收。当前 2026-08-09 stored-vector self-hit 已通过，但由于本地 `.env` 没有配置 `FIRSTRAG_EVAL_USERNAME` / `FIRSTRAG_EVAL_PASSWORD`，T-130 没有冒用账号或重复产生外部 provider 费用；T-136 切换前必须使用仓库所有者提供的登录账号重新跑 RAG 和 indexing eval。

## 可复查方法

服务状态和资源：

```bash
docker compose ps
docker info --format \
  'docker_cpus={{.NCPU}} docker_memory_bytes={{.MemTotal}} docker_version={{.ServerVersion}}'
du -sh vector_db/chroma uploads
df -h .
```

PostgreSQL 聚合在 `postgres` 容器内使用只读 `SELECT` 完成；Chroma 检查在 `backend` 容器内使用 `chromadb.HttpClient` 的 `list_collections`、`get` 和 `query(query_embeddings=..., where=...)` 完成。未来迁移工具必须复用同一事实集合与检查项，并只输出 counts、dimensions、size 和 mismatch，不输出正文或 embedding。

## Milvus 对照门槛

完整门禁由 [ADR-0001](../adr/0001-milvus-migration.md#迁移门禁) 定义。最小要求是：

- Milvus IDs 与 PostgreSQL 119 条 current IDs 完全一致，正文和核心 metadata 100% 匹配。
- legacy 216 条不得进入 Milvus。
- user/file filtered self-hit 10/10，且无跨用户/跨文件泄漏。
- direct ANN warmed p95 不超过 50ms。
- 真实 RAG 14/14、`vector_degraded=false`，平均 hybrid retrieval 不超过 1056.28ms。
- indexing eval 必须由 vector channel 命中目标文件。

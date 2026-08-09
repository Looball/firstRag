# Milvus 全链路验收（2026-08-09）

本报告记录 T-136 的 Milvus 全链路、质量、性能和资源验收。测试期间仅通过进程环境临时把 backend/worker 切到 Milvus；完成后已恢复仓库默认 `VECTOR_STORE_PROVIDER=chroma`。测试未输出账号密码、JWT、API Key、文档正文或 embedding 数值。

## 结论

**通过，可以进入受控 Milvus 默认切换。** [ADR-0001](../adr/0001-milvus-migration.md#迁移门禁) 的数据一致性、真实 ANN、用户/文件隔离、RAG 质量、indexing 生命周期、restart persistence、资源和性能门槛均满足。

本任务不直接修改默认 provider。T-137 应在同一次受控变更中把 Milvus 设为默认并同步架构、部署、教程和运维文档；T-138 观察期完成前继续保留 Chroma adapter、数据和 rollback 能力。

## 环境与固定参数

| 项目 | 值 |
| --- | --- |
| Git 基线 | `main@7a574c4` |
| Milvus / PyMilvus | `milvusdb/milvus:v3.0.0` / `pymilvus==3.0.1` |
| 拓扑 | Milvus Standalone + etcd + MinIO |
| Schema / metric | `FLOAT_VECTOR` / `COSINE` |
| Index | HNSW，`M=16`、`efConstruction=200`、search `ef=64` |
| Consistency | `Strong` |
| Docker Desktop | Apple Silicon，8 vCPU，16,484,397,056 bytes RAM（约 15.35 GiB） |
| 当前数据 | 19 files / 119 current entries / 1 collection / 1024 dimensions |
| 冷热状态 | direct ANN 先 warm-up，再统计 20 次 filtered query |

没有为本轮结果修改 HNSW、search、RRF、rerank 或应用检索参数。

## 数据一致性与直接 ANN

新的 `milvus_acceptance.py` 以 PostgreSQL current chunks 为事实集合，同时读取 Chroma source 和 Milvus target，验证 stable IDs、正文、完整 metadata、维度和 stored embedding。输出只包含聚合值和失败类型。

| 检查 | 结果 |
| --- | ---: |
| PostgreSQL / Chroma / Milvus current IDs | 119 / 119 / 119，missing=0，unexpected=0 |
| 正文与 metadata | 119/119 一致 |
| stored-vector Top-1 | 35/35 一致 |
| 最低 Top-K overlap | 1.00 |
| filtered ANN self-hit | 20/20 |
| 错误用户 / 错误文件 | 均返回 0，2/2 通过 |
| warmed direct ANN p50 | 5.12ms |
| warmed direct ANN p95 | 7.38ms |
| warmed direct ANN max | 14.59ms |
| ADR 门槛 | p95 <= 50ms，通过 |

该延迟只表示本机 119 条 stored-vector filtered ANN 微基准，不包含 query embedding、PostgreSQL full-text、RRF、rerank 或 LLM 网络耗时，不能外推为生产容量指标。

## 真实 RAG 对照

真实应用账号沿用已保存的 LLM/embedding settings，Milvus 读取迁移后的 current vectors。14 个 case 全部通过，主检索 case 同时包含 `vector` 与 `fulltext`，且 `vector_degraded=false`。

| 指标 | Chroma 冻结基线 | Milvus | 变化 | 门槛 |
| --- | ---: | ---: | ---: | ---: |
| Case 通过 | 14/14 | 14/14 | 持平 | 14/14 |
| 平均 sources | 3.36 | 3.36 | 持平 | >= 1 |
| 平均 first token | 1752.67ms | 2085.87ms | +19.0% | <= 8000ms |
| 平均总耗时 | 3.83s | 4.21s | +9.9% | <= 20s |
| 平均 hybrid retrieval | 528.14ms | 710.62ms | +34.6% | <= 1056.28ms，且 <= 3000ms |
| 平均 retrieve | — | 414.25ms | — | <= 5000ms |
| 平均 rerank | 399.79ms | 358.06ms | -10.4% | <= 3000ms |

这些是同一机器、同一评测集上的单轮对照，足以检查 ADR hard gate，不代表统计显著的性能结论。Milvus 的 hybrid retrieval 有可见回退，但仍明显低于冻结门槛；本轮不据此调参。

## 上传、索引与删除生命周期

`eval_indexing.py` 增加 provider-neutral 直接向量计数、删除、重新入队和永久删除门禁。本轮 Milvus 真实链路结果：

- 上传成功，worker job 为 `succeeded`，文件状态为 `indexed`。
- 初次 direct vector count 为 1；聊天 source 命中临时文件并包含 `vector`，`vector_degraded=false`。
- 删除向量后 direct count 为 0，文件回到 `pending`。
- 重新向量化耗时 22.509s，direct count 恢复为 1；再次真实 ANN/source 命中且没有降级。
- 永久删除临时文件后 direct count 为 0；原 retrieval settings 已恢复。
- 聊天耗时 2.46s，动态生成的唯一 marker 被答案正确返回，避免固定文案造成假阳性。

## 隔离、维度与 restart persistence

Milvus credential-free full-stack E2E 使用隔离 Compose project 和 provider stub，验证：

- 浏览器真实完成注册/登录、TXT 上传、worker 索引、SSE 回答和 sources 展示，Playwright 1/1 通过。
- 两个应用用户分别使用 16 和 32 dimensions，collection schema 相互独立；两条 indexing lifecycle 均通过。
- 底层 retrieval probe 另用 3 和 4 dimensions 验证双用户、双 collection、user/file scalar filter、distance 排序与清理。
- Milvus restart 后旧 collection 和 v1 数据仍可检索；随后 v2 replacement、删除与 cleanup 均通过。
- restart 后首次旧 collection query 曾遇到一次 Milvus `503 channel distribution is not serviceable`，第二次成功。CI runner 因此使用 12 次、每次间隔 5 秒的有界 persisted-collection readiness gate；超过上限仍失败，不把错误静默降级为 full-text。

同一 runner 的 Chroma 默认路径也在隔离 Compose project 中复跑，Playwright 1/1 通过。GitHub Actions 保持 required check 名称不变，在一个 `Full-stack E2E` job 内串行执行 Chroma 与 Milvus，避免 provider 覆盖退化。

## 资源与 production preflight

真实 Milvus eval 期间采样 73 次：FirstRAG containers 的内存和峰值为 1,856,126,321 bytes，占 Docker VM 11.26%，低于 ADR 的 90% 门槛；Milvus、etcd、MinIO 无 OOM 和非预期 restart。

production preflight 的运行态检查通过：Milvus container、backend/worker authenticated probe 和 migration dry-run 均正常。静态 production config 通过临时注入、不落盘的强测试 secrets 验证；本地 `.env` 没有被修改。Docker VM 约 15.35 GiB，低于 16 GiB 推荐值，preflight 按设计给出 warning；这台机器适合小规模教程与迁移验收，不代表生产容量充足。

## 自动化回归

| 检查 | 结果 |
| --- | --- |
| Backend container unittest | 421/421 通过 |
| T-136 定向 container unittest | 23/23 通过 |
| Frontend Vitest | 181/181 通过 |
| Frontend ESLint | 通过；2 条既有 `<img>` warning，0 error |
| Frontend production build | 通过 |
| Chroma credential-free full-stack E2E | 1/1 通过 |
| Milvus credential-free full-stack E2E | 1/1 通过 |
| Python compileall | 通过 |
| Tutorial docs / Actions pins | 8 个 Markdown / 13 个 action references，通过 |
| Compose config / runtime health | 通过；验收后 backend 已恢复 `chroma` |
| `git diff --check` | 通过 |

## 切换决定

T-136 给出 **Go**：Milvus 已具备成为默认 provider 的证据。实际切换仍应保持可审计和可回滚：

1. T-137 同步默认配置、Compose、README、架构、部署、教程和 troubleshooting，不让代码与文档在 `main` 上出现长期不一致。
2. 切换时记录 timestamp 与 PostgreSQL `index_version` watermark，恢复 indexing writes 后立即复跑 authenticated health、indexing eval 和 RAG gate。
3. T-138 观察期结束前不删除 Chroma volume、adapter、依赖或 rollback runbook。

# Milvus 默认切换记录（T-137）

## 结论

2026-08-11T04:16:01Z，FirstRAG 默认 vector store 已从 Chroma 切换为 Milvus。`docker compose up -d --build` 不再需要 profile 即启动 Milvus Standalone、etcd、MinIO 与 authenticated health probe；backend 和 worker 的实际 `VECTOR_STORE_PROVIDER` 均为 `milvus`。Chroma 仅保留在 `chroma-rollback` profile，容器已停止，原数据未删除。

## 切换 watermark

| 项目 | 结果 |
| --- | --- |
| cutover timestamp | `2026-08-11T04:16:01Z` |
| PostgreSQL live files | 20 |
| PostgreSQL indexed files | 19 |
| PostgreSQL current chunks | 119 |
| active vector jobs | 0 |
| live file index version range / sum | `0..2` / `2` |

watermark 只记录聚合数量和版本，不包含用户正文、文件名、凭据或 embedding。若观察期内回滚，必须以该时间点之后新建或重建的文件为范围重新生成 Chroma vectors，不能直接切换 provider 后假定两端继续一致。

## Current-data 与 ANN 复验

切换后临时启动只读 Chroma rollback source，复跑 `app.services.vectors.milvus_acceptance`，随后立即停止 Chroma。结果：

| 检查 | 结果 |
| --- | --- |
| scope | 19 files / 119 entries / 1 collection |
| stable ID、正文、metadata、dimension、embedding | 19/19 files 通过 |
| stored-vector Top-1 | 35/35 一致 |
| 最低 Top-K overlap | 1.0 |
| filtered ANN self-hit | 10/10 |
| 用户/文件隔离 | 2/2 |
| warmed ANN latency | p50 6.040ms / p95 8.133ms，门槛 50ms |
| failures | 0 |

## Runtime 状态

- `milvus-etcd`、`milvus-minio`、`milvus-standalone`、PostgreSQL 和 Redis healthy。
- `milvus-health-probe` authenticated round-trip 成功退出；`migrate` 为 `applied=0 skipped=9`。
- backend、worker 和 frontend 正常运行；backend/worker 均确认 provider 为 `milvus`。
- credential-free full-stack E2E 默认不传 provider 也走 Milvus：浏览器主链路 1/1、两轮 indexing eval、restart persistence、双用户/双 dimensions 隔离、v1/v2 replacement 与 probe cleanup 全部通过；隔离 containers/volumes 已自动删除。
- Chroma 容器为 stopped，回滚数据与 bind mount 保留，不执行删除。
- production preflight 的 Compose config、Milvus topology、Docker resources、authenticated runtime health 和 migration dry-run 通过；本机 `.env` 尚未显式注入生产级 `MILVUS_URI` / `MILVUS_TOKEN`，因此完整生产 secret gate 保持失败，正式部署前必须由仓库所有者通过 secret 管理完成凭据轮换。

## Rollback 边界

观察期内只允许按 [`MILVUS_MIGRATION_RUNBOOK.md`](../MILVUS_MIGRATION_RUNBOOK.md) 回滚：暂停 indexing、等待 active jobs 为 0、核对 watermark 后补齐 cutover 后 Chroma vectors，再显式运行：

```bash
VECTOR_STORE_PROVIDER=chroma docker compose --profile chroma-rollback up -d --build
```

T-138 之前不得删除 Chroma adapter、依赖、容器定义或 `vector_db/chroma` 数据；任何数据删除仍需要仓库所有者单独确认。

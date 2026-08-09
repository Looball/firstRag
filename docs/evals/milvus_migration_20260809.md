# T-135 Chroma 到 Milvus 迁移验收（2026-08-09）

本报告记录 T-135 在本地 Compose current data 上完成的 dry-run、备份、真实导入、checkpoint resume 和 rollback-check。迁移直接复制 Chroma stored embeddings，没有调用用户 embedding provider，没有读取或输出 API Key、正文或 embedding 数值，也没有删除或修改 Chroma source。

默认 `VECTOR_STORE_PROVIDER` 继续保持 `chroma`；切换默认流量和完整质量/性能门禁属于 T-136。

## 数据范围

| 项目 | 结果 |
| --- | --- |
| PostgreSQL current files | 19 |
| PostgreSQL current entries | 119 |
| Source collection | `langchain-u1-4aecfb85286f` |
| Target collection | `firstrag_u1_4aecfb85286f` |
| Stored embedding dimensions | 1024 |
| legacy `langchain` entries | 未迁移 |

dry-run 对 19 个未软删除且状态为 `indexed` 的文件完成 ID、正文、核心 metadata 和 embedding 可读性对账，结果为 `19/19` 文件、`119/119` entries、`0` failure、`0` reindex item。

## 维护窗口与备份

执行真实导入前确认 `queued/processing` vector jobs 为 0，并停止 frontend、backend、worker。以下备份保存于仓库忽略目录 `backups/milvus-cutover/t135-20260809/`：

- PostgreSQL custom-format logical dump，已通过 `pg_restore --list`。
- uploads `tar.gz`，已通过 archive list。
- 停止 Chroma 后创建的 Chroma data `tar.gz`，已通过 archive list。
- 优雅停止后复制的 Milvus Standalone、etcd 和 MinIO volume 内容，重启后 authenticated health probe 通过。

backup manifest SHA-256：

```text
4fd1a53901d8764237afbbf0e629cb55d0aaa517a90e6ba7b156720e5dcbaefb
```

备份包含运行数据，不提交 Git。该本地快照用于本次迁移和 rollback 演练，不能代替生产环境的异机、加密和定期恢复策略。

## 真实导入与 resume

首次 import：

| 指标 | 结果 |
| --- | ---: |
| files completed | 19 |
| files failed | 0 |
| entries imported | 119 |
| reindex required | 0 |
| stored-vector ANN samples | 35 |
| Chroma/Milvus self-hit | 35/35 |
| 最低 file-level Top-K overlap | 1.0 |

工具按文件执行 target-only delete、幂等 upsert、flush、ID/count 对账、正文/metadata/embedding 读回验证和 filtered ANN 比较。checkpoint 在每个文件成功后原子写入。

使用相同 scope 和 checkpoint 立即重跑：

| 指标 | 结果 |
| --- | ---: |
| `resumed_verified` files | 19/19 |
| repeated import files | 0 |
| failures | 0 |
| entries | 119 |

这证明已完成文件会重新验证 target 而不是重复 upsert；PostgreSQL 事实集合变化时，scope fingerprint 会拒绝旧 checkpoint。

## Rollback 演练

`--rollback-check` 对 19 个文件重新读取 Chroma embeddings，执行 35 次 user/file filtered stored-vector ANN self-hit，并比较命令前后 source digest：

| 指标 | 结果 |
| --- | --- |
| rollback-ready files | 19/19 |
| Chroma self-hit | 35/35 |
| source unchanged | true（19/19） |
| Chroma mutation | 0 |
| Milvus mutation | 0 |

Compose render 同时确认 backend 和 worker 当前仍使用：

```text
VECTOR_STORE_PROVIDER=chroma
```

因此 T-135 完成的是“可切换、可验证、可回滚”的数据准备，不代表已经批准 Milvus 默认流量。实际 cutover 后，若存在新建或重建文件，切回 Chroma 前仍需依据 cutover timestamp/index-version watermark 重新生成这些 Chroma vectors。

## 自动化回归

新增定向测试覆盖：

- dry-run 不创建 target collection 或 checkpoint。
- precomputed embedding import 不需要 embedding model/API Key。
- target-only failure cleanup 不扫描其它 identity。
- checkpoint resume 验证后不重复 upsert。
- checkpoint scope drift 拒绝续跑。
- source embedding 缺失进入 machine-readable `reindex_required`。
- rollback-check 验证 ANN 和 source digest 且不 mutation。
- 真实 import 强制维护窗口、active-job drain 和四类 verified backup artifacts。

最终验证结果：

- T-135/Milvus 定向 unittest：20/20。
- 完整 backend unittest：418/418。
- credential-free full-stack E2E：1/1，默认 Chroma 路径完成登录、上传、worker indexing、hybrid retrieval、SSE 和 sources。
- Python compileall、8 份教程文档门禁、13 个 GitHub Actions pin、Compose config 和 production preflight 全部通过。
- 完整 Compose 同时保持 Chroma 与 Milvus profile 健康；migration `applied=0 skipped=9`，Milvus authenticated health probe 成功。

完整命令、备份 manifest schema、cutover 和 rollback 步骤见 [`../MILVUS_MIGRATION_RUNBOOK.md`](../MILVUS_MIGRATION_RUNBOOK.md)。

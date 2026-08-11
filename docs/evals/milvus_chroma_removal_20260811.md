# T-138 Milvus-only 切换与恢复演练

日期：2026-08-11
范围：在移除旧 vector store runtime 前冻结 Milvus 数据、完成隔离恢复，并记录可恢复证据。

## 结论

- 维护窗口开始前，PostgreSQL 中 active vector index job 为 `0`。
- Milvus 基线为 `1` 个 collection、`121` 条 entity。
- 三个 Milvus named volume 均已生成独立压缩备份和 SHA-256。
- 备份恢复到隔离 Compose project 后，collection 数、entity 数与基线一致。
- 隔离实例通过 authenticated probe，并对真实恢复数据完成 filtered ANN self-hit。
- 临时恢复容器、network 和临时 volumes 已按精确名称清理；备份归档保留在 Git 忽略目录。
- 当前应用、Compose、CI、依赖和教程入口只支持 Milvus。迁移前 `vector_db/` 不再被 runtime 读取，本任务不删除该目录。

## 备份清单

本地备份目录：`backups/milvus/t138-20260811/`。该目录被 Git 忽略，不应提交到仓库。

| 文件 | SHA-256 | 大小 |
| --- | --- | --- |
| `milvus_data.tgz` | `3e0196bca3c9ee82b1069b09fffd0bb4e91013428a86b2ea0d851c819f13239d` | 444 KiB |
| `milvus_etcd_data.tgz` | `5fb0608fc93e7ef343dda878d977b7dd127d9002a417d86bf1bcd45b52f65cee` | 1.1 MiB |
| `milvus_minio_data.tgz` | `4bce5655b93e89b8e3cb96073db83cb04f3e9715ffa63047c397f44d10c522e` | 1.0 MiB |

> 注：上表 checksum 在演练时生成；合并前的自动校验会再次读取本地归档核对。

## 隔离恢复结果

恢复 project 使用独立名称 `firstrag-t138-restore` 和独立 named volumes，不连接日常
backend、worker 或 PostgreSQL。恢复后观察到：

| 检查项 | 基线 | 恢复实例 | 结果 |
| --- | ---: | ---: | --- |
| collection 数 | 1 | 1 | 通过 |
| entity 数 | 121 | 121 | 通过 |
| collection | `firstrag_u1_4aecfb85286f` | 同名 | 通过 |
| authenticated probe | — | 成功 | 通过 |
| filtered ANN self-hit | — | `true` | 通过 |

恢复实例验证完成后只删除了 `firstrag-t138-restore` 的临时容器、network 和临时
volumes；日常 Compose volumes、迁移前数据目录和备份归档均未删除。

## 生产切换边界

本地 Compose 使用 Milvus Standalone 和仓库 `.env` 中的运行配置完成验证。真正部署到
共享或公网环境前，仍必须在目标环境配置生产级 `MILVUS_URI`、`MILVUS_TOKEN`、
MinIO 凭据和备份保留策略，并运行：

```bash
conda run -n firstrag python scripts/production_preflight.py \
  --env-file .env --migration-method compose --check-runtime-health
```

本记录不包含、打印或复制任何真实 token。目标环境未通过 preflight 时，不应把本地
恢复演练解释为生产部署放行。

# Chroma 到 Milvus 迁移与回滚 Runbook

本文对应 `T-135`，用于维护窗口内把 PostgreSQL current chunks 对应的 Chroma entries 导入 Milvus。默认路径直接复制 stored embeddings，不调用用户 embedding provider，也不读取或打印 API Key。legacy `langchain` collection 不属于 PostgreSQL current ID 集合，不迁移。

默认业务 provider 在 `T-136` 完整验收前仍为 `chroma`。本 runbook 不删除 Chroma、Milvus volume、uploads 或 PostgreSQL 数据，也不执行长期 dual write。

## 1. 工具边界

入口：

```bash
python -m app.services.vectors.chroma_to_milvus_migration --help
```

| 模式 | 写 Chroma | 写 Milvus | 写 checkpoint | 用途 |
| --- | --- | --- | --- | --- |
| `--dry-run` | 否 | 否 | 否 | 对账 PostgreSQL/Chroma、dimension 和预计导入量。 |
| 默认 import | 否 | 是 | 是 | 分文件幂等导入、验证并支持 resume。 |
| `--rollback-check` | 否 | 否 | 否 | 验证 Chroma source fingerprint 与 filtered ANN，证明旧读取路径仍可用。 |

真实 import 必须同时满足：

- `--maintenance-window-confirmed`：frontend、backend、worker 已停止新写入；数据库中 `queued/processing` vector jobs 为 0。
- `--backup-manifest`：PostgreSQL、uploads、Chroma 和 Milvus 四类备份均标记为已验证。
- Chroma ID、正文和核心 metadata 与 PostgreSQL current chunks 一致。
- 每条 embedding 可读、非零、有限且同一 identity dimension 一致。

任一文件失败都写入 report 的 `failures` 与 `reindex_required`，不会静默跳过。报告和 checkpoint 只包含 ID 范围、count、dimension、digest 和错误分类，不包含正文、embedding 数值、API Key 或连接凭据。

## 2. 启动候选运行时并完成 dry-run

先启动完整 Milvus profile，保持业务 provider 为 Chroma：

```bash
docker compose --profile milvus up -d --build
docker compose --profile milvus ps -a
```

dry-run 是只读操作，可以在停止应用写入前执行：

```bash
mkdir -p tmp/vector-migration
docker compose --profile milvus run --rm --no-deps \
  -v "$PWD/tmp:/app/tmp" \
  backend \
  python -m app.services.vectors.chroma_to_milvus_migration \
  --dry-run \
  --report /app/tmp/vector-migration/dry-run.json
```

要求 `files_failed=0`。检查报告时只读取结构化摘要：

```bash
python -m json.tool tmp/vector-migration/dry-run.json
```

## 3. 建立维护窗口和备份

先停止会产生上传、index job 或 vector mutation 的应用服务：

```bash
docker compose stop frontend backend worker
docker compose exec -T postgres sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT status, COUNT(*) FROM vector_index_jobs WHERE status IN ('\''queued'\'', '\''processing'\'') GROUP BY status;"'
```

若查询仍返回记录，先恢复 worker 让任务 drain，再重新进入维护窗口；不要带着 active jobs 运行 import。

以独立时间戳目录保存备份。以下 `<RUN_ID>` 使用同一个实际值替换：

```bash
mkdir -p backups/milvus-cutover/<RUN_ID>
docker compose exec -T postgres sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner' \
  > backups/milvus-cutover/<RUN_ID>/postgres.dump
tar -czf backups/milvus-cutover/<RUN_ID>/uploads.tar.gz uploads
docker compose stop chroma
tar -czf backups/milvus-cutover/<RUN_ID>/chroma.tar.gz -C vector_db chroma
docker compose start chroma
```

Milvus snapshot 必须同时覆盖 Standalone、etcd 和 MinIO。先优雅停止三项，再复制 named-volume 内容并恢复候选运行时：

```bash
docker compose --profile milvus stop milvus-standalone milvus-etcd milvus-minio
docker compose --profile milvus cp \
  milvus-standalone:/var/lib/milvus backups/milvus-cutover/<RUN_ID>/milvus-data
docker compose --profile milvus cp \
  milvus-etcd:/etcd backups/milvus-cutover/<RUN_ID>/milvus-etcd
docker compose --profile milvus cp \
  milvus-minio:/minio_data backups/milvus-cutover/<RUN_ID>/milvus-minio
docker compose --profile milvus start milvus-etcd milvus-minio milvus-standalone
docker compose --profile milvus run --rm milvus-health-probe
```

至少执行以下恢复前检查：

```bash
pg_restore --list backups/milvus-cutover/<RUN_ID>/postgres.dump >/dev/null
tar -tzf backups/milvus-cutover/<RUN_ID>/uploads.tar.gz >/dev/null
tar -tzf backups/milvus-cutover/<RUN_ID>/chroma.tar.gz >/dev/null
test -d backups/milvus-cutover/<RUN_ID>/milvus-data
test -d backups/milvus-cutover/<RUN_ID>/milvus-etcd
test -d backups/milvus-cutover/<RUN_ID>/milvus-minio
```

验证完成后创建 `backups/milvus-cutover/<RUN_ID>/manifest.json`：

```json
{
  "version": 1,
  "verified": true,
  "created_at": "2026-08-09T00:00:00Z",
  "artifacts": {
    "postgres": {
      "location": "backups/milvus-cutover/<RUN_ID>/postgres.dump",
      "verified": true
    },
    "uploads": {
      "location": "backups/milvus-cutover/<RUN_ID>/uploads.tar.gz",
      "verified": true
    },
    "chroma": {
      "location": "backups/milvus-cutover/<RUN_ID>/chroma.tar.gz",
      "verified": true
    },
    "milvus": {
      "location": "backups/milvus-cutover/<RUN_ID>/milvus-data+etcd+minio",
      "verified": true
    }
  }
}
```

`backups/` 和 `tmp/` 已被 `.gitignore` 排除。生产备份应进一步复制到受控的独立磁盘或对象存储，并按现有备份策略加密和审计。

## 4. 执行、resume 和对账

应用服务保持停止，只保留 PostgreSQL、Chroma 和 Milvus profile 依赖：

```bash
docker compose --profile milvus run --rm --no-deps \
  -v "$PWD/backups:/app/backups:ro" \
  -v "$PWD/tmp:/app/tmp" \
  backend \
  python -m app.services.vectors.chroma_to_milvus_migration \
  --maintenance-window-confirmed \
  --backup-manifest /app/backups/milvus-cutover/<RUN_ID>/manifest.json \
  --checkpoint /app/tmp/vector-migration/checkpoint.json \
  --report /app/tmp/vector-migration/import.json \
  --batch-size 256 \
  --sample-top-k 5
```

每个文件完成后原子更新 checkpoint。进程中断时使用完全相同的 scope 和 checkpoint 命令重跑；已完成文件会重新读回 Milvus、验证 ID/正文/metadata/embedding 和 ANN，然后标记为 `resumed_verified`，不会重复 upsert。PostgreSQL 事实集合变化时旧 checkpoint 会被拒绝，必须调查变化并使用新路径，不能覆盖审计证据。

最小通过条件：

- `files_failed=0`，`reindex_required=[]`。
- `entries_total` 等于 dry-run 的 current entries。
- 每个文件的 `self_hits == sample_count`。
- 重跑后已完成文件进入 `resumed_verified`，entry count 不增加。

## 5. rollback-check 与 provider 切换

在恢复业务写入前执行只读 rollback-check：

```bash
docker compose --profile milvus run --rm --no-deps \
  -v "$PWD/tmp:/app/tmp" \
  backend \
  python -m app.services.vectors.chroma_to_milvus_migration \
  --rollback-check \
  --report /app/tmp/vector-migration/rollback-check.json
```

要求所有文件为 `rollback_ready`、`source_unchanged=true`，且 Chroma filtered ANN self-hit 全部通过。该命令不会修改 Chroma 或 Milvus。

T-136 完整验收和仓库所有者批准前，不把 `.env` 的默认值切为 Milvus。获批后的 cutover 使用：

```dotenv
VECTOR_STORE_PROVIDER=milvus
```

然后重建并启动应用服务，执行 T-136 全链路门禁：

```bash
docker compose --profile milvus up -d --build backend worker frontend
```

发生质量、隔离、ANN、资源或稳定性问题时：

1. 再次停止 frontend、backend、worker，等待 active jobs 为 0。
2. 将 `VECTOR_STORE_PROVIDER` 改回 `chroma`。
3. 对 cutover 后新增或重建的文件，依据 cutover watermark 和源文件重新生成 Chroma vectors。
4. 重新运行 `--rollback-check`，确认 Chroma source 未损坏且 ANN 可用。
5. 启动 backend、worker、frontend；Milvus 数据保留用于分析，不删除任何 volume。

```bash
docker compose up -d --build backend worker frontend
```

只切环境变量不能恢复 cutover 后只写入 Milvus 的新版本，因此必须记录 T-136 cutover timestamp 和 `index_version` watermark。删除 Chroma/Milvus 数据不属于本 runbook，必须由仓库所有者另行明确确认。

## 6. 常见失败分类

| code | 含义 | 处理 |
| --- | --- | --- |
| `missing_embedding_identity` | 缺少 current collection identity。 | 检查用户 embedding 设置，不猜测 collection。 |
| `chroma_id_mismatch` | PostgreSQL 与 Chroma ID 集合不同。 | 保留失败报告，按文件重新向量化。 |
| `chroma_embedding_missing` | stored embedding 不可读。 | 使用源文件和已保存用户设置重新向量化。 |
| `settings_dimension_mismatch` | 设置 dimension 与 stored vector 不同。 | 调查设置漂移，不自动改 schema。 |
| `milvus_*_mismatch` | 导入后 ID、正文、metadata 或 embedding 不一致。 | 工具清理该目标文件，修复后 resume。 |
| `ann_self_hit_failed` | Chroma/Milvus filtered ANN 未命中自身。 | 不切 provider，进入 T-136 诊断。 |
| `checkpoint_scope_mismatch` | PostgreSQL 事实集合已变化。 | 新建 checkpoint，保留旧文件审计。 |
| `vector_jobs_not_drained` | 仍有 queued/processing job。 | 退出维护命令，让 worker drain 后重试。 |

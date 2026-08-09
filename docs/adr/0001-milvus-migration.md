# ADR-0001：从 Chroma 迁移到 Milvus

- 状态：`Accepted`
- 决定日期：2026-08-09
- 对应任务：`T-130` 至 `T-138`
- 当前运行时：ChromaDB 1.5.9；本 ADR 不切换生产读写
- 基线证据：[Chroma 迁移基线](../evals/chroma_migration_baseline_20260809.md)

## 背景

FirstRAG 当前通过 Chroma 保存向量，通过 PostgreSQL 保存全文检索 chunk。索引、删除、metadata filter、hybrid retrieval、diagnostics、preflight、清理脚本和教程都直接依赖 Chroma 行为。历史真实验收曾出现 job 已经 `succeeded`、PostgreSQL chunk 已写入，但单文件 ANN 查询仍失败的情况，因此迁移验收不能只检查写入状态或 collection count。

本 ADR 决定 Milvus 的版本、部署拓扑、collection 隔离、schema、索引、metric、consistency、迁移数据范围、切换和 rollback 契约。provider-neutral boundary 的代码形态由 T-131 实现，但不得改变这里确定的应用语义。

## 决策摘要

| 主题 | 决策 |
| --- | --- |
| Milvus server | `milvusdb/milvus:v3.0.0` |
| Python client | `pymilvus==3.0.1` |
| 拓扑 | 官方 Standalone Docker Compose：Milvus + etcd + MinIO，Woodpecker 内嵌于 Milvus |
| 支撑镜像起始 pin | `quay.io/coreos/etcd:v3.5.25`、`minio/minio:RELEASE.2024-05-28T17-19-04Z` |
| 向量类型与 metric | `FLOAT_VECTOR` + `COSINE` |
| 向量索引 | `HNSW`，`M=16`、`efConstruction=200`；初始 search `ef=64` |
| consistency | `Strong` |
| 多租户 | 保持“每个用户 + embedding identity 一个 collection”，不改为共享 partition key |
| rollout | 维护窗口内单次导入和 provider 切换；不做长期 dual write |
| 默认 provider | T-136 全部通过前保持 `chroma` |
| Chroma 保留 | 切换后只读保留到 T-138 观察期和 rollback gate 完成，默认不删除 |

Milvus 官方在 2026-07-29 发布 3.0.0，推荐配套 PyMilvus 3.0.1。T-132 从 v3.0.0 官方 Compose release asset 复制拓扑并移除所有 host port；该 asset 的 SHA-256 基线为 `4518b95ddd719542558f48d84e9a53a5910099888b8ef985ab122524db7d97d1`。若固定的支撑镜像无法通过仓库现有 high/critical 安全门禁，只允许升级到与 Milvus 3.0.0 兼容的安全 patch，并在本 ADR 增补记录，不能使用 `latest`。

参考：

- [Milvus 3.0.0 release notes](https://milvus.io/docs/release_notes.md)
- [PyMilvus 安装与版本建议](https://milvus.io/docs/install-pymilvus.md)
- [Milvus v3.0.0 Standalone Compose release asset](https://github.com/milvus-io/milvus/releases/download/v3.0.0/milvus-standalone-docker-compose.yml)

## 部署与安全边界

T-132 使用三个 Compose service：

```text
backend / worker
  -> milvus-standalone:19530
       -> milvus-etcd:2379
       -> milvus-minio:9000
       -> Woodpecker（Milvus 内嵌，MinIO WAL backend）
```

- `milvus`、`etcd`、`minio` 均只在 Compose 内网访问，不声明 host `ports`。
- Milvus 开启 authentication；backend、worker 和 migration tool 仅通过环境变量读取 token，不记录 token。
- MinIO 不使用官方示例的默认凭据；凭据来自环境变量，不写入仓库或日志。
- Milvus、etcd 和 MinIO 分别使用持久化 volume；日志继续使用仓库统一的 rotation 配置。
- healthcheck 必须验证 Milvus 本身可用；backend/worker 的 probe 还要完成 authenticated client round-trip，不能只检查 TCP 端口。
- Storage V3 初始保持关闭；`content` 使用 `VARCHAR`，不依赖默认关闭的 `TEXT` feature。

选择官方三容器 Compose 而不是单容器 embedded-etcd 模式，是因为真实数据需要可验证的备份和恢复路径。Milvus 官方也建议需要 Backup 的 Standalone 使用 Docker Compose。

## Collection 隔离与命名

保持当前 collection-level 隔离语义，每个不兼容 embedding identity 使用独立 collection：

```text
identity = user_id | provider | model | dimensions
collection = firstrag_u{user_id}_{sha1(identity)[:12]}
```

Milvus 名称使用小写字母、数字和下划线，不沿用 Chroma 名称中的连字符。collection-level 隔离允许不同 dimensions 使用各自固定 schema，也避免跨用户 ANN 候选进入应用层。每条 entity 仍保存 `user_id`，所有 query/delete 仍强制带 `user_id` 和必要的 `file_id`，作为 defense in depth。

当前规模不值得为了减少 collection 数量改为 partition key。Milvus 官方将 collection-level tenancy 定义为强隔离和强 search performance，partition key 更适合百万级 tenant；如果未来用户规模逼近 collection 运维上限，应另写 ADR，不在本次迁移中顺带改变隔离模型。

## Entity schema

| 字段 | Milvus 类型 | 约束与用途 |
| --- | --- | --- |
| `chunk_id` | `VARCHAR(192)` | primary key、`auto_id=false`；沿用 `{user_id}:{file_id}:v{index_version}:{chunk_index}` |
| `embedding` | `FLOAT_VECTOR(dim)` | `dim` 由 collection 对应 embedding settings 固定；不允许 NULL |
| `content` | `VARCHAR(65535)` | chunk 正文；写入前按 UTF-8 bytes 校验，超限视为 indexing failure |
| `user_id` | `INT64` | tenant defense-in-depth filter；建 `INVERTED` scalar index |
| `file_id` | `VARCHAR(64)` | UUID 字符串；建 `INVERTED` scalar index |
| `chunk_index` | `INT64` | 文件内稳定顺序和 source 定位 |
| `index_version` | `INT64` | 重建、OCR 重识别和旧任务隔离；建 `INVERTED` scalar index |
| `metadata` | `JSON` | 可变 source/OCR/location metadata；始终写 object，不使用 dynamic field |

Milvus JSON field 上限为 65,536 bytes。当前最大 metadata 只有 745 bytes；adapter 写入前仍必须执行 UTF-8 JSON size check，避免 provider error 难以定位。常用权限和生命周期字段保持显式 scalar，不依赖 JSON path filter。

## Metric、排序和可观察契约

Milvus 使用 `COSINE`，原始 search result 数值越大越相似。FirstRAG 当前 Chroma `vector_score` 实际保存的是 cosine distance，数值越小越相似。为了避免迁移时改变 sources/diagnostics 语义，provider-neutral adapter 统一返回：

```text
distance = 1 - milvus_cosine_similarity
```

- adapter 内部和 RRF 输入按 `distance` 升序排列。
- 对外历史字段 `vector_score` 暂继续承载 distance；T-137 文档必须明确它不是标准 relevance score。
- 不把 Chroma distance 与 Milvus similarity 原值直接比较。
- 如未来要新增 higher-is-better 的 similarity 字段，必须作为显式 schema/API 变更，不能静默复用 `vector_score`。

HNSW 起始参数固定为 `M=16`、`efConstruction=200`、search `ef=64`。T-136 可以测量但不能为追求单次结果临时调参；任何变更需要独立证据和 ADR amendment。

## Consistency 与文件生命周期

collection 和 search 使用 `Strong` consistency。FirstRAG 在单文件重建、删除后立即允许前端发起检索，弱一致性会重现“job 成功但向量暂不可见”的历史失败。即使 Strong 增加少量延迟，也优先保证教程和数据生命周期的确定性。

每个文件的写入顺序保持：

1. 获取 PostgreSQL advisory lock 并核对 `index_version`。
2. 解析、切分、生成 embeddings 和 stable chunk IDs。
3. 删除同一 `user_id + file_id` 的全部旧 Milvus entities。
4. 插入当前版本并 flush/等待可见。
5. 用至少一个刚写入 embedding 执行同 user/file filtered ANN self-hit。
6. 写入 PostgreSQL chunks 并发布文件 `indexed` 状态。

第 5 步失败即 indexing failure，并进入两边补偿清理；不能只因 insert 返回成功就发布 `indexed`。永久删除、重建和失败补偿都通过相同 adapter contract 执行，并保留现有 advisory lock、active job 和版本检查。

## 数据迁移策略

### 迁移范围

以 PostgreSQL `knowledge_file_chunks` 为事实集合，只迁移同时满足以下条件的 Chroma entry：

- stable `chunk_id` 存在于 PostgreSQL；
- `user_id`、`file_id`、`chunk_index`、`index_version` 与 PostgreSQL 一致；
- content 完全一致；
- embedding dimension 与目标 collection schema 一致；
- 文件未永久删除，且属于当前用户。

2026-08-09 基线中，119 条 current entries 全部满足条件。legacy `langchain` collection 的 216 条 entry 与当前 PostgreSQL chunk ID 零匹配，定义为历史孤儿数据：保留在 Chroma 只读归档中，但不导入 Milvus，也不据此恢复已删除文件。

### 既有 embedding 与重新向量化

- 真实数据默认导入 Chroma 已有 embedding，避免再次调用用户 provider 产生费用、限流和向量漂移。
- 开发、CI 和可删除 fixture 默认从源文件重新向量化。
- entry 缺失、正文/metadata 不一致、维度不匹配或向量不可读取时，不猜测修复；记录文件级失败，并在用户凭据和源文件可用时重新向量化。
- migration tool 必须先支持 dry-run，输出 count、dimension、mismatch 和预计写入量，不输出正文、embedding、API Key 或连接凭据。

## Rollout 与 rollback

不采用长期 dual write，避免两套非事务性 vector store 在失败补偿时产生第三种状态。切换步骤为：

1. T-131 在 Chroma 下建立 provider-neutral boundary，行为不变。
2. T-132 建立固定版本 Milvus runtime、认证、volume 和 preflight，默认 provider 仍为 Chroma。
3. T-133/T-134 接入 Milvus 写入和检索，但不切默认流量。
4. T-135 备份 PostgreSQL、Chroma、Milvus 配置/volumes，暂停新 indexing jobs，等待 worker drain 后 dry-run 和 import。
5. 核对 counts、内容、metadata、filtered ANN self-hit、tenant isolation 和真实 eval 后，将 `VECTOR_STORE_PROVIDER` 切到 Milvus。
6. T-136 完整验收通过后恢复写入，记录 cutover timestamp 和 index version watermark。
7. T-138 观察期结束前 Chroma 数据、依赖和 rollback 命令都保留，不自动删除。

rollback 时先暂停 indexing，切回 Chroma；对 cutover 后新增或重建的文件，依据 PostgreSQL watermark 和源文件重新生成 Chroma vectors，验证 filtered ANN 后再恢复写入。Milvus 数据保留用于分析，不用“切回旧镜像”替代数据恢复。任何删除 Chroma 或 Milvus volume 的动作都必须由仓库所有者显式确认。

## 迁移门禁

T-136 至少满足：

- 目标 Milvus current IDs 与 PostgreSQL 完全相等：missing=0、unexpected=0，正文和核心 metadata 100% 一致。
- 每个迁移 collection 至少 10 次 user/file filtered ANN self-hit 全部 top-1 命中自身；跨用户和非目标文件返回 0。
- 同一 Docker Desktop、同一 stored embedding 的 warmed direct filtered ANN p95 不高于 `max(4 × 2.28ms, 50ms) = 50ms`。
- 真实 RAG 14/14 case 全部通过、`vector_degraded=false`；平均 hybrid retrieval 不高于 Chroma 基线 528.14ms 的 2 倍，即 1056.28ms，同时继续满足现有 3000ms hard gate。
- indexing eval 必须同时通过 job、PostgreSQL chunk、vector entry、目标 source 的 vector channel 和 ANN health；历史 Chroma 的失败报告是 negative control，不是允许的结果。
- upload、单文件重建、永久删除、OCR reindex/correction、失败补偿、worker restart、Milvus restart 和 credential-free full-stack E2E 全部通过。
- Compose 运行期间 Milvus/etcd/MinIO 无 OOM、无非预期 restart，Docker VM memory 峰值低于 90%；低于 16 GiB 推荐资源时 preflight 明确 warning。

## 资源结论

Milvus 官方给出的 Standalone RAM 最低要求为 8 GiB、推荐 16 GiB，CPU 推荐 4 cores 或更多。当前 Docker Desktop 为 8 vCPU、16,484,397,056 bytes（约 15.35 GiB），满足最低要求但只处于推荐线边缘；宿主工作盘剩余约 44 GiB。结论是：当前机器可做小规模教程、迁移和验收，但没有宽裕生产余量。T-132/T-136 必须验证真实峰值并在资源不足时失败或告警，不能静默回退 Chroma 或让 quickstart 卡死。

参考：[Milvus Standalone requirements](https://milvus.io/docs/prerequisite-docker.md)。

## 后果

正面影响：

- schema、metric、consistency、隔离和 rollout 已固定，后续任务可以直接实现。
- 以 PostgreSQL 为迁移事实集合，避免把 216 条历史孤儿 entry 迁入新系统。
- 强制 ANN self-hit，把“写入成功”和“可检索成功”拆成独立门禁。
- Chroma 保留到观察期结束，rollback 不依赖不可逆删除。

成本与限制：

- 三容器 Standalone 比 Chroma 占用更多内存和磁盘，Docker Desktop 资源需要显式管理。
- `Strong` consistency 与写后 self-hit 会增加 indexing 延迟，但换取确定性。
- collection-per-user 不是百万 tenant 的最终形态；本次优先保持当前隔离语义。
- 维护窗口迁移会短暂停止新 indexing；这是避免双写分叉的有意选择。

# Milvus v3 文本切换验收（2026-08-13）

## 结论

T-144 切换通过：PostgreSQL 不再保存或检索知识文件 parent/child 文本；Milvus v3 entity 统一保存 dense/sparse vectors、child `content`、`parent_content`、stable IDs 与位置 metadata。检索链路直接从 Milvus 取得 parent text 构建 LLM context。

## 数据切换

| 检查项 | 结果 |
| --- | --- |
| active indexed files | 19 |
| 同版本 cutover audits | 19 |
| 审计 entities | 163 |
| 缺失审计 | 0 |
| `knowledge_file_chunks` | 已删除 |
| `knowledge_file_chunk_parents` | 已删除 |
| 最新 migration | `012_drop_postgresql_knowledge_text.sql` |

切换前已生成 PostgreSQL logical backup，文件权限为 `600`，SHA-256 为 `559f19b9ceea6cc0b4b06a55566d8b0c5f245cc645603cf65eec59d1cb0d0ff0`。备份位于本机临时目录，不提交仓库。migration 012 在审计缺失时已验证会拒绝删除；19/19 通过后才执行表删除。

每个文件的审计覆盖 user/file/version、entity count、stable child ID、非空 child text、parent identity、非空 parent text 与不含正文的内容摘要。Milvus 重启后再次执行只读审计，结果仍为 19/19，且没有重新生成 embedding。

## 运行时与性能

本机 Docker Desktop 为 8 CPU / 15.35 GiB RAM。空闲资源快照：BGE-M3 sparse encoder 约 789 MiB，Milvus Standalone 约 521 MiB，backend 约 204 MiB，worker 约 175 MiB。标准 sparse encoder runtime image 约 356 MiB（不含 named-volume model cache）。BGE-M3 固定为 `BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181`；模型权重约 2.3 GB，cache 建议预留至少 5 GB。

隔离 probe 使用两个 child，写入阶段包含 dense/sparse generation、Milvus flush、文本/identity 对账与 dense/sparse self-hit：

| 指标 | 样本 | P50 | P95 |
| --- | ---: | ---: | ---: |
| v3 indexing write | 3 | 18,789.20 ms | 19,335.33 ms |
| Milvus hybrid query | 20 | 6.20 ms | 7.63 ms |

hybrid query 指标使用预计算的 dense/sparse query vectors，只衡量 Milvus hybrid search；不包含远程 dense embedding、BGE-M3 query encoding、rerank 或 LLM 时间。

## 验证证据

- Docker Compose production build 通过；PostgreSQL、Redis、Milvus、etcd、MinIO、BGE-M3、backend、worker 与 frontend 正常启动。
- backend unittest `442/442` 通过。
- frontend Vitest `181/181` 通过；ESLint `0 error`，保留 2 个既有 `<img>` warning；Next.js production build 通过。
- BGE-M3 query/document probe 通过；Milvus v3 probe 验证 text fields、dense/sparse/hybrid routes、跨用户隔离、版本重建和删除。
- credential-free full-stack E2E 通过：浏览器用例 `1/1`，两组不同 embedding dimensions 的 indexing/chat eval 均通过。
- Milvus restart 后 authenticated probe 通过；首次业务 collection 查询短暂返回 `channel not serviceable`，有界重试第 2 次成功，随后持久查询全部通过。
- backend 最终改为 `127.0.0.1:18000` loopback bind；production preflight 的 secret、数据库、Redis、Milvus、sparse encoder、端口、Compose、资源、runtime health 和 migration dry-run 全部通过。

本报告不包含知识文件正文、API Key、数据库密码、Milvus token 或用户凭据。真实外部 provider 的 14-case RAG 质量结果未在本轮伪造；本轮质量证据来自 credential-free 全栈 indexing/chat eval，生产发布前仍应使用目标企业语料和生产 provider 单独建立质量基线。

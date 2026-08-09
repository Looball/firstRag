# Milvus filtered ANN 验收报告（2026-08-09）

## 结论

T-134 的 Milvus 检索路径已满足用户、文件和 embedding identity 隔离要求。应用层预计算 query embedding 后，adapter 使用始终包含 `user_id` 的 scalar filter；单文件使用等值条件，多文件使用安全转义的 `in` 条件。Milvus COSINE similarity 统一转换为 `distance = 1 - similarity`，继续保持 `vector_score` 越小越近的既有契约。

默认业务 provider 仍为 Chroma，本任务没有迁移现有数据、切换默认 provider 或删除 Chroma 数据。数据迁移与 rollback 属于 T-135。

## 实现与风险门禁

- Milvus filtered ANN 固定使用 `COSINE + HNSW`，查询参数为 `ef=64`，consistency 为 `Strong`。
- 返回 entity 会再次校验 `user_id` 和允许的 `file_id`；发现范围外候选时整路 vector search 失败，不会返回越权文档。
- 首次 ANN 返回空时，用完全相同的 scalar scope 执行 `count(*)`。只有范围内确有 rows 时才重试一次相同 ANN；仍为空则明确报错并进入 full-text 降级，避免把“已写入但 ANN 不可见”误记为健康零结果。
- 删除 Chroma 的延迟重试、用户级宽过滤、无过滤 ANN 和直接读取全部 embedding 的 fallback。Chroma 也只执行一次严格用户/文件范围查询。
- provider 异常统一输出安全日志、`vector_degraded=true`、provider-aware `vector_errors` 和 `vector_ms`；PostgreSQL full-text、RRF、rerank 与 SSE 字段契约保持不变。

## 真实 Milvus Standalone 验收

环境：Compose profile `milvus`，Milvus `v3.0.0`，PyMilvus `3.0.1`，Strong consistency。专用 probe 使用两个用户 collection：

- `firstrag_t134_probe_u900134_identity`
- `firstrag_t134_probe_u900135_identity`

worker 写入结果：主用户两个文件 3 条 vectors，另一用户同名文件 1 条 vector。backend 使用独立新 client 首次检索结果：

```json
{
  "contents": ["closest", "second", "third"],
  "distances": [0.0, 0.2, 1.0],
  "single_file_count": 1,
  "multi_file_count": 3,
  "other_user_count": 1,
  "ok": true
}
```

这证明 Top-K 排序、单文件、多文件、用户 collection 隔离和跨 backend/worker client 可见性均符合预期。验收后两个 exact-name probe collections 已删除，并再次确认均不存在；没有操作应用 collection 或 Milvus volumes。

## 自动化回归

- T-134 定向回归：28/28 通过，覆盖 scalar expression 转义、多用户/多文件隔离、排序、metadata 转换、首次 ANN visibility、provider error 脱敏和 full-text diagnostics 降级。
- 完整后端：409/409 通过。
- Credential-free full-stack Playwright：1/1 通过，覆盖默认 Chroma 的登录、上传、异步向量化、vector/full-text retrieval、SSE 回答和引用展示。
- Python compileall、教程文档检查、13 个 GitHub Actions pin、Compose config、production preflight 与 `git diff --check` 全部通过。

## 后续边界

T-135 必须在维护窗口中提供 dry-run、checkpoint、对账和 rollback 工具；T-136 再以迁移后的真实数据完成命中率、降级率、P50/P95 latency 和资源验收。当前报告不能替代数据迁移或默认 provider 切换批准。

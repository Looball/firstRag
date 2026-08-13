# FirstRAG 后端说明

FirstRAG 后端基于 FastAPI，主入口为 `backend/app/main.py`，兼容入口为
`backend/main.py`。生产链路使用 PostgreSQL 保存关系数据和任务状态，使用 Milvus
统一保存 dense/sparse vectors、child text 与 parent text；文件向量化由 PostgreSQL
持久任务队列和独立 worker 异步完成。

## 默认启动

在仓库根目录启动完整 Docker Compose 环境：

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 \
  redis postgres milvus-etcd milvus-minio milvus-standalone \
  milvus-health-probe migrate backend worker frontend
```

Compose 会启动 Redis、PostgreSQL、Milvus Standalone 及其 etcd/MinIO、migration、
FastAPI backend、vector index worker 和 Next.js frontend。常规验证以 Compose
容器为准，完整说明见 `docs/DEPLOYMENT.md`。

## 本地专项调试

只调试 API 时可在 `backend/` 目录运行：

```bash
conda activate firstrag
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

只调试异步向量任务时运行：

```bash
conda activate firstrag
python -m app.workers.vector_index_worker
```

本地单独启动仍需要可用的 PostgreSQL、Redis、Milvus 和根目录 `.env`。不要打印或
提交 `.env` 中的密码、token 和用户凭据。

## 关键模块

| 目录 | 职责 |
| --- | --- |
| `app/api/` | FastAPI route、认证、权限检查和 HTTP error。 |
| `app/schemas/` | Pydantic request/response model。 |
| `app/repositories/` | PostgreSQL 数据访问。 |
| `app/services/` | RAG、文件处理、模型 provider、Milvus 和业务编排。 |
| `app/workers/` | vector index background worker。 |
| `app/db/sql/` | 空库基线与增量 migration。 |
| `tests/` | route、service、repository 和脚本回归测试。 |

## RAG 数据流

```text
上传文件
  -> metadata + vector_index_jobs
  -> vector_index_worker
  -> 文档解析 / parent-child chunk / 用户 dense embedding + BGE-M3 sparse embedding
  -> Milvus v3 entities（vectors + child text + parent text）

用户提问
  -> Milvus filtered dense/sparse hybrid search + RRF
  -> optional rerank + Milvus parent context
  -> OpenAI-compatible LLM streaming
  -> SSE token / sources / diagnostics
```

聊天和 embedding provider、model、API Key 由登录用户在设置页保存；API Key 以
密文持久化，读取接口不会返回明文。rerank 支持本地 CrossEncoder 和按用户配置的
远程 provider。

## 验证

后端单测从 `backend/` 运行：

```bash
conda run -n firstrag python -m pytest tests -q
```

代码或配置修改后的默认验收仍应回到仓库根目录执行 Compose 构建、状态检查和相关
smoke test。API、schema、RAG 和部署细节分别见 `docs/API.md`、
`docs/SCHEMAS.md`、`docs/RAG_WORKFLOW.md` 与 `docs/DEPLOYMENT.md`。

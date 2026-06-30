# 部署与本地工作流

本文档记录 FirstRAG 单人开发时的本地启动、日常验收和 Docker Compose 运行方案。敏感信息只放在根目录 `.env`，不要提交真实账号、API Key、JWT secret 或数据库密码。

## 环境变量

根目录 `.env` 是后端运行时配置来源。首次启动前复制模板：

```bash
cp .env.example .env
```

常用配置：

| 变量 | 说明 |
| --- | --- |
| `DATABASE_URL` | 本地 conda 方式运行时使用的 PostgreSQL 连接串。 |
| `COMPOSE_DATABASE_URL` | Docker Compose 方式运行时可选覆盖的 PostgreSQL 连接串；不填时默认连接 compose 内的 `postgres` 服务。 |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Docker Compose 中 PostgreSQL 容器的数据库、用户和密码。 |
| `JWT_SECRET_KEY` | JWT 签名密钥。 |
| `LLM_PROVIDER` / `LLM_MODEL` / `LLM_API_KEY` | 默认平台模型配置。 |
| `USER_SETTINGS_ENCRYPTION_KEY` | 用户 API Key 加密主密钥。 |
| `ZAI_EMD_API` | 智谱 embedding API Key。 |
| `VECTOR_STORE_PATH` | Chroma 持久化路径；本地默认 `./vector_db/chroma`，compose 默认 `/app/vector_db/chroma`。 |
| `RERANKER_MODEL_PATH` | 本地 reranker 模型路径；compose 会把 `./models` 只读挂载到 `/app/models`。 |

## 本地启动

### 1. 启动后端

```bash
cd backend
conda activate firstrag
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端默认读取仓库根目录 `.env`。如果本地数据库为空，请先执行 `backend/app/db/sql/000_initial_schema.sql` 初始化当前完整 schema；后续数据库结构变化会从 `001_xxx.sql` 开始追加增量 migration。

### 2. 启动前端

```bash
cd frontend
npm install
npm run dev
```

默认访问 `http://localhost:3000`。前端 API route 默认代理到 `http://127.0.0.1:8000`。

### 3. 启动 vector index worker

上传文件并需要异步向量化时必须启动 worker：

```bash
cd backend
conda activate firstrag
python -m app.workers.vector_index_worker
```

只做登录、模型设置、普通聊天 UI 调整、静态前端开发时，可以不启动 worker。涉及文件上传、自动向量化、删除向量、indexing eval 或 RAG 真实回归时，应启动 worker。

## 单人开发日常流程

推荐顺序：

1. 同步代码后检查 `.env` 是否仍符合本地环境。
2. 启动后端和前端。
3. 涉及文件向量化或真实 eval 时启动 worker。
4. 完成代码或文档修改。
5. 先运行静态验收。
6. 涉及真实链路时再运行完整验收。
7. 检查 `git status --short`，只提交当前任务相关文件。
8. push 前确认没有 `.env`、上传文件、向量库、模型缓存或 eval 历史 JSON 被提交。

静态验收命令：

```bash
scripts/acceptance_check.sh --skip-real-eval
```

完整验收命令：

```bash
FIRSTRAG_EVAL_USERNAME=你的用户名 \
FIRSTRAG_EVAL_PASSWORD=你的密码 \
scripts/acceptance_check.sh
```

完整验收会额外运行：

- `scripts/rag_eval_gate.sh`
- `scripts/eval_indexing.py`

使用 `--skip-real-eval` 的场景：

- 只改文档、类型、纯前端展示或单元测试。
- 后端服务、worker、数据库、模型 API Key 或真实账号不可用。
- 只需要 push 前快速确认 lint/build/unit test。

必须跑真实验收的场景：

- 修改 RAG 检索、router、rerank、sources、diagnostics、token usage。
- 修改文件上传、向量化、worker、failure recovery。
- 修改 eval 脚本、case 或质量门禁。
- 修改用户模型配置或 API Key 加密链路。

## Docker Compose

仓库根目录提供本地 compose 方案：

```bash
docker compose up --build
```

服务：

| 服务 | 默认地址 | 说明 |
| --- | --- | --- |
| `postgres` | `localhost:5432` | PostgreSQL 16，数据保存在 named volume `postgres_data`。 |
| `backend` | `http://127.0.0.1:8000` | FastAPI 后端。 |
| `frontend` | `http://localhost:3000` | Next.js 前端，容器内代理到 `http://backend:8000`。 |
| `worker` | 不暴露端口 | 消费 `vector_index_jobs` 的向量化 worker。 |

持久化挂载：

| 宿主路径 | 容器路径 | 说明 |
| --- | --- | --- |
| `./uploads` | `/app/uploads` | 上传文件。 |
| `./vector_db` | `/app/vector_db` | Chroma 持久化数据。 |
| `./models` | `/app/models` | 本地 reranker 模型，只读挂载。 |
| `postgres_data` | `/var/lib/postgresql/data` | PostgreSQL 数据。 |

compose 默认让后端和 worker 连接：

```text
postgresql://firstrag:firstrag-password@postgres:5432/first_rag
```

如需覆盖 compose 内数据库连接，使用 `COMPOSE_DATABASE_URL`，不要复用指向宿主机 `localhost` 的 `DATABASE_URL`：

```bash
COMPOSE_DATABASE_URL=postgresql://user:password@postgres:5432/first_rag \
docker compose up --build
```

常用命令：

```bash
docker compose config --quiet
docker compose up --build
docker compose logs -f backend worker
docker compose down
```

当前 compose 不会自动创建业务基础表。新数据库首次运行前，需要执行 `backend/app/db/sql/000_initial_schema.sql` 初始化 `users`、`knowledge_bases`、`messages` 等业务表；后续如果补齐迁移执行脚本，应把该脚本接入 compose 或文档启动流程。

## 端口约定

| 服务 | 默认地址 |
| --- | --- |
| 前端 | `http://localhost:3000` |
| 后端 | `http://127.0.0.1:8000` |
| PostgreSQL | `localhost:5432` |
| Chroma | 本地持久化目录，不单独暴露端口 |

## 部署目录

```text
deploy/
├── docker/
│   ├── backend.Dockerfile
│   └── frontend.Dockerfile
└── nginx/
```

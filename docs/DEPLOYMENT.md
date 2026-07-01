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

后端默认读取仓库根目录 `.env`。如果本地数据库为空，请先运行迁移脚本初始化当前完整 schema；后续数据库结构变化会从 `001_xxx.sql` 开始追加增量 migration。

### 数据库初始化与迁移

迁移脚本默认读取仓库根目录 `.env` 中的 `DATABASE_URL`，不会打印 `.env` 内容或数据库密码。

查看本地 migration 文件：

```bash
conda run -n firstrag python scripts/migrate_db.py --list
```

查看当前数据库待执行 migration：

```bash
conda run -n firstrag python scripts/migrate_db.py --dry-run
```

执行迁移：

```bash
conda run -n firstrag python scripts/migrate_db.py
```

脚本会自动创建 `schema_migrations` 记录表。已执行文件的 checksum 如果发生变化，
脚本会停止并提示不一致，避免继续执行后续 migration。

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

静态验收默认会运行 migration 文件检查、后端 compileall、后端 unittest、前端
lint、前端单测和前端 build。如果当前环境配置了 `DATABASE_URL` 或
`COMPOSE_DATABASE_URL`，脚本会额外执行 migration dry-run；如果没有数据库连接，
则只检查本地 migration 文件列表并提示跳过 dry-run。

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

常用跳过开关：

| 开关 | 说明 |
| --- | --- |
| `--skip-migration-check` | 跳过 migration 文件检查和可选 dry-run。 |
| `--skip-frontend-tests` | 跳过前端 Vitest。 |
| `--skip-frontend-build` | 跳过 Next build。 |
| `FIRSTRAG_SKIP_BACKEND_COMPILE=1` | 跳过后端 compileall。 |
| `FIRSTRAG_SKIP_BACKEND_TESTS=1` | 跳过后端 unittest。 |
| `FIRSTRAG_REQUIRE_MIGRATION_DRY_RUN=1` | 没有数据库连接时让 migration dry-run 阶段失败。 |

## GitHub Actions CI

仓库在 `.github/workflows/ci.yml` 中维护基础 CI，默认在 pull request、`main`
分支 push 和手动触发时运行。

CI 覆盖：

- 后端：安装 `backend/requirements.txt`、`python -m compileall app`、`python -m unittest discover tests -v`、`python scripts/migrate_db.py --list` 和 `docker compose config --quiet`。
- 前端：`npm ci`、`npm run lint`、`npm run test` 和 `npm run build`。

默认 CI 不运行真实 RAG eval 和 indexing eval，因为它们需要后端服务、真实账号、
外部模型 API Key 和可用数据库。发布前仍按本地验收流程显式运行真实评估。

## Docker Compose

仓库根目录提供本地 compose 方案：

```bash
docker compose up --build
```

服务：

| 服务 | 默认地址 | 说明 |
| --- | --- | --- |
| `postgres` | `localhost:5432` | PostgreSQL 16，数据保存在 named volume `postgres_data`。 |
| `migrate` | 不暴露端口 | 执行 `scripts/migrate_db.py`，初始化或升级 PostgreSQL schema。 |
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

compose 会在 `postgres` 健康检查通过后运行一次 `migrate` service。`backend` 和
`worker` 会等待 `migrate` 成功退出后再启动。`migrate`、`backend` 和 `worker`
都使用同一份 compose 内部数据库连接配置：

```text
DATABASE_URL=${COMPOSE_DATABASE_URL:-postgresql://firstrag:firstrag-password@postgres:5432/first_rag}
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
docker compose run --rm migrate python /app/scripts/migrate_db.py --dry-run
docker compose logs -f migrate backend worker
docker compose down
```

新数据库首次运行时，`migrate` 会自动应用 `000_initial_schema.sql` 并创建
`schema_migrations` 记录表。重复启动 compose 时，已应用且 checksum 一致的
migration 会被跳过，不会破坏已有数据。

## 在线演示环境方案

当前仓库尚未发布公开在线 demo。本节记录推荐上线方案、配置清单和剩余阻塞项，避免 README Roadmap 只停留在“待发布”。

### 推荐目标

第一阶段选择“单台云服务器 / VPS + Docker Compose + HTTPS 反向代理”的自托管方案。原因是当前应用由 PostgreSQL、FastAPI backend、Next.js frontend、vector index worker、uploads、Chroma 持久化目录和本地 reranker 模型共同组成，单机 Compose 最容易保证 backend 与 worker 共享同一份 `uploads/`、`vector_db/` 和 `models/`。

暂不优先选择 Vercel + 独立 backend 或纯托管 PaaS。该路线更适合后续拆分静态前端、托管数据库、对象存储和独立 worker 后再推进；现在会额外引入跨服务文件持久化、worker 常驻、模型缓存和内网访问控制问题。

推荐拓扑：

```text
访问者
  -> HTTPS 域名
  -> 反向代理（Caddy / Nginx / Cloudflare Tunnel）
  -> frontend:3000（Next.js 页面和 API proxy）
  -> backend:8000（FastAPI，仅内网或本机可达）
  -> PostgreSQL / uploads / vector_db / worker
```

公网只暴露 80/443。`frontend`、`backend` 和 `postgres` 的宿主机端口应绑定到 `127.0.0.1` 或通过防火墙限制访问，不直接暴露到公网。

### 资源与持久化

| 资源 | 建议 | 说明 |
| --- | --- | --- |
| 云服务器 | 2 vCPU / 4 GB RAM 起步，推荐 4 vCPU / 8 GB RAM | RAG、PDF 解析和 reranker 会占用 CPU 与内存；演示并发不宜过高。 |
| 系统盘 | 30 GB 起步，推荐独立数据盘或快照 | `uploads/`、`vector_db/`、PostgreSQL volume 和 `models/` 都会增长。 |
| PostgreSQL | 使用 compose named volume `postgres_data` | 定期做卷快照或 `pg_dump`，避免误删演示数据。 |
| 上传文件 | 继续挂载 `./uploads:/app/uploads` | 公开 demo 禁止上传私密文件，并需要清理策略。 |
| Chroma 数据 | 继续挂载 `./vector_db:/app/vector_db` | 可从上传文件重建，但保留备份能减少恢复时间。 |
| reranker 模型 | `./models:/app/models:ro` | 模型目录只读挂载；上线前确认模型文件已存在。 |
| 日志 | 先使用 `docker compose logs`，后续接入集中日志 | 日志不得包含 API Key、JWT、数据库密码或用户上传原文。 |

### 配置清单

上线前在服务器本地创建 `.env`，不要把真实值提交到仓库：

| 配置 | 要求 |
| --- | --- |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | 使用非默认强密码；不要沿用模板密码。 |
| `JWT_SECRET_KEY` | 使用随机长密钥；更换后已有登录态会失效。 |
| `USER_SETTINGS_ENCRYPTION_KEY` | 使用 Fernet key，并与 `JWT_SECRET_KEY` 分离；丢失后无法解密已保存的用户 API Key。 |
| `LLM_PROVIDER` / `LLM_MODEL` / `LLM_API_KEY` | 如使用平台默认 Key，只放在服务器 `.env` 或 secret store，不写入 README、issue、日志或截图。 |
| `ZAI_EMD_API` | embedding Key 只放在服务器 `.env` 或 secret store。 |
| `ALLOW_USER_CUSTOM_LLM_BASE_URL` | 公开 demo 保持 `false`，避免用户通过自定义模型地址访问服务器内网。 |
| `MAX_UPLOAD_FILE_SIZE_BYTES` | 公开 demo 建议调低到 10-20 MB，并与反向代理 body size 一致。 |
| `FRONTEND_PORT` / `BACKEND_PORT` / `POSTGRES_PORT` | 建议设为 `127.0.0.1:3000`、`127.0.0.1:8000`、`127.0.0.1:5432`，由反向代理暴露 HTTPS。 |

公开 demo 推荐额外设置：

```bash
FRONTEND_PORT=127.0.0.1:3000
BACKEND_PORT=127.0.0.1:8000
POSTGRES_PORT=127.0.0.1:5432
MAX_UPLOAD_FILE_SIZE_BYTES=20971520
ALLOW_USER_CUSTOM_LLM_BASE_URL=false
```

反向代理要求：

- 终止 TLS，强制 HTTP 跳转 HTTPS。
- 将域名请求转发到 `http://127.0.0.1:3000`。
- 上传 body size 不大于 `MAX_UPLOAD_FILE_SIZE_BYTES`。
- 对登录、注册、上传、聊天和模型设置接口做 IP 级限流。
- 对 SSE streaming 关闭响应缓冲，避免聊天 token 被代理层攒批返回。

### 演示账号和安全边界

- 演示账号在服务器上线后通过 UI 创建，账号和密码只通过可信渠道单独提供，不写入仓库文档。
- 当前应用仍开放注册接口，公开 demo 上线前需要在反向代理层临时加访问控制、Basic Auth、IP allowlist 或实现后端注册开关。
- 不要求访客输入自己的真实 API Key；如果需要测试用户 Key 模式，必须提示只在可信 demo 环境使用，且前端不会持久化完整 Key。
- 上传文件只用于演示，不接收私人、商业或敏感文档。公开 demo 应在页面说明上传数据会被定期清理。
- 后端当前没有通用 rate limit middleware；公网访问必须先由反向代理、WAF 或网关承担限流。

### 数据清理策略

上线前需要准备一个可重复执行的清理流程：

1. 保留预置演示账号和少量脱敏样例知识库。
2. 定期删除临时用户、临时知识库、上传文件、向量索引和对应 chunks。
3. 清理后运行一次最小 smoke test：登录、上传小文件、向量化、提问和查看 sources。
4. 清理脚本未完成前，公开 demo 应只提供给受控测试者。

当前仓库还没有专门的 demo cleanup 脚本，因此这是正式公开上线前的阻塞项。

### 启动步骤

1. 准备云服务器、域名和 TLS 方案，只开放 80/443 和受控 SSH。
2. 在服务器拉取仓库，复制 `.env.example` 为 `.env`，填写非默认密钥和 provider Key。
3. 准备 `models/rerankers/bge-reranker-base`，并确认 `uploads/`、`vector_db/` 可持久化。
4. 运行 `docker compose config --quiet` 检查 Compose 配置。
5. 运行 `docker compose up -d --build` 启动 PostgreSQL、migration、backend、frontend 和 worker。
6. 运行 `docker compose logs -f migrate backend worker frontend`，确认 migration 成功、backend 和 worker 无启动错误。
7. 配置反向代理到 `http://127.0.0.1:3000`，并设置 TLS、body size、SSE buffering 和限流。
8. 创建演示账号，上传脱敏样例文件并完成一次向量化和聊天 smoke test。
9. 在 README 中补充真实 demo URL、使用限制和数据清理说明后，才把 Roadmap 的“发布在线演示环境”标记为完成。

### 当前阻塞项

- 尚未选择真实服务器、域名和 TLS 入口。
- `deploy/nginx/` 仍是占位目录，没有提交可复用的公网反向代理配置。
- 尚未落地注册访问控制、登录/上传/聊天限流和自动清理脚本。
- 尚未创建受控演示账号和脱敏样例知识库。
- 尚未完成公网环境的 smoke test 与真实 RAG eval。

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

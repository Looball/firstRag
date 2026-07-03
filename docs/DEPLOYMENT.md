# 部署与本地工作流

本文档记录 FirstRAG 单人开发时的本地启动、日常验收和 Docker Compose 运行方案。敏感信息只放在根目录 `.env`，不要提交真实账号、API Key、JWT secret 或数据库密码。

## 环境变量

根目录 `.env` 是后端运行时配置来源。首次启动前复制模板：

```bash
cp deploy/compose/.env.example .env
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
| `UPLOADS_DIR` / `VECTOR_DB_DIR` / `MODELS_DIR` | Docker Compose 宿主机持久化目录；生产环境建议指向独立数据盘。 |
| `DOCKER_LOG_MAX_SIZE` / `DOCKER_LOG_MAX_FILE` | Docker stdout/stderr 日志轮转参数。 |

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

- 后端：安装 `backend/requirements.txt`、`python -m compileall app`、`python -m unittest discover tests -v`、`python scripts/migrate_db.py --list` 和 `docker compose --project-directory . --env-file deploy/compose/.env.example -f deploy/compose/docker-compose.yml config --quiet`。
- 前端：`npm ci`、`npm run lint`、`npm run test` 和 `npm run build`。

默认 CI 不运行真实 RAG eval 和 indexing eval，因为它们需要后端服务、真实账号、
外部模型 API Key 和可用数据库。发布前仍按本地验收流程显式运行真实评估。

## Docker Compose

Docker Compose 配置位于 `deploy/compose/docker-compose.yml`，环境变量模板位于 `deploy/compose/.env.example`。完整启动流程、`.env` 准备、reranker 模型下载、日志查看和常见问题见 `docs/docker-startup/README.md`。

```bash
docker compose --project-directory . --env-file .env -f deploy/compose/docker-compose.yml up --build
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
| `${UPLOADS_DIR:-./uploads}` | `/app/uploads` | 上传文件。 |
| `${VECTOR_DB_DIR:-./vector_db}` | `/app/vector_db` | Chroma 持久化数据。 |
| `${MODELS_DIR:-./models}` | `/app/models` | 本地 reranker 模型，只读挂载。 |
| `postgres_data` | `/var/lib/postgresql/data` | PostgreSQL 数据。 |

compose 默认根据 `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` 生成后端、
worker 和 migrate 使用的内部连接串：

```text
postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
```

compose 会在 `postgres` 健康检查通过后运行一次 `migrate` service。`backend` 和
`worker` 会等待 `migrate` 成功退出后再启动。`migrate`、`backend` 和 `worker`
都使用同一份 compose 内部数据库连接配置：

```text
DATABASE_URL=${COMPOSE_DATABASE_URL:-postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}}
```

如需连接外部 PostgreSQL 或自定义 compose 内数据库连接，使用 `COMPOSE_DATABASE_URL`，
不要复用指向宿主机 `localhost` 的 `DATABASE_URL`：

```bash
COMPOSE_DATABASE_URL=postgresql://user:password@postgres:5432/first_rag \
docker compose --project-directory . --env-file .env -f deploy/compose/docker-compose.yml up --build
```

常用命令：

```bash
docker compose --project-directory . --env-file .env -f deploy/compose/docker-compose.yml config --quiet
docker compose --project-directory . --env-file .env -f deploy/compose/docker-compose.yml up --build
docker compose --project-directory . --env-file .env -f deploy/compose/docker-compose.yml run --rm migrate python /app/scripts/migrate_db.py --dry-run
docker compose --project-directory . --env-file .env -f deploy/compose/docker-compose.yml logs -f migrate backend worker
docker compose --project-directory . --env-file .env -f deploy/compose/docker-compose.yml down
```

新数据库首次运行时，`migrate` 会自动应用 `000_initial_schema.sql` 并创建
`schema_migrations` 记录表。重复启动 compose 时，已应用且 checksum 一致的
migration 会被跳过，不会破坏已有数据。

compose 已为所有服务配置 Docker `json-file` 日志轮转，默认 `10m * 5`。生产环境如接入集中日志，应继续保留脱敏规则：日志不得包含完整 API Key、JWT、数据库密码或用户上传原文。

### 日志与基础监控

后端输出统一 JSON 日志事件，日志正文只记录 `method`、`path`、`status_code`、`duration_ms`、`request_id`、`user_id`、`conversation_id`、`knowledge_base_id`、`message_id`、`job_id`、阶段耗时和错误分类等字段，不记录 request body、Authorization header、完整 API Key、JWT、数据库连接串或用户上传原文。响应头会回传 `X-Request-ID`，可用于串联前端报错、后端请求日志和 chat streaming 日志。

重点事件：

| 事件 | 来源 | 用途 |
| --- | --- | --- |
| `http_request` / `http_request_failed` | backend middleware | 统计接口请求量、错误率、P95 响应耗时。 |
| `chat_first_answer_token` | chat streaming | 统计首 token 等待时间。 |
| `chat_stream_completed` / `chat_stream_failed` / `chat_stream_cancelled` | chat streaming | 区分完成、模型失败、客户端中断和回答总耗时。 |
| `retrieval_embedding_failed` | hybrid retrieval | 定位 embedding provider 或网络异常。 |
| `retrieval_vector_failed` / `retrieval_vector_file_failed` | Chroma vector retrieval | 定位 Chroma、HNSW 或单文件向量残留问题。 |
| `retrieval_fulltext_failed` | PostgreSQL full-text retrieval | 定位 PostgreSQL 或全文检索异常。 |
| `retrieval_rerank_failed` | CrossEncoder rerank | 定位 reranker 模型或运行时异常；当前会降级为 RRF 结果。 |
| `vector_index_job_claimed` / `vector_index_job_succeeded` / `vector_index_job_failed` | vector worker | 统计任务吞吐、失败率、处理耗时和失败来源。 |

错误日志统一包含 `error_type`、`error_source` 和 `retryable`。`error_source` 取值优先使用 `llm_provider`、`embedding`、`vector_store`、`postgres`、`rerank`、`document_parse`、`file_storage`、`worker`、`chat_stream` 或 `http`，便于在日志系统中按来源聚合。

最小监控面板建议：

| 指标 | 来源 | 建议告警 |
| --- | --- | --- |
| 接口错误率 | `http_request.status_code >= 500` / 总请求数 | 5 分钟内超过 5%。 |
| P95 接口耗时 | `http_request.duration_ms` | 持续高于平时基线 2 倍。 |
| 平均首 token 时间 | `chat_first_answer_token.duration_ms` 或 `GET /chat/quality-dashboard` 的 `average_first_token_ms` | 连续窗口高于 8s。 |
| 模型调用失败率 | `chat_stream_failed.error_source == "llm_provider"` / chat 请求数 | 连续窗口超过 10%。 |
| 向量化队列长度和 worker 活动 | `GET /chat/vector-index-jobs/health` 的 `queue.active`、`worker.has_recent_activity` | 有 active 任务但 worker 长时间无活动。 |
| 向量化任务失败率 | `vector_index_job_failed` / `vector_index_job_claimed` | 连续窗口超过 10%。 |
| 检索降级次数 | `retrieval_embedding_failed`、`retrieval_vector_failed`、`retrieval_fulltext_failed`、`retrieval_rerank_failed` | 突然高于平时基线。 |

本地排查示例：

```bash
docker compose --project-directory . --env-file .env -f deploy/compose/docker-compose.yml logs backend worker | rg '"event":"chat_stream_failed"|"event":"vector_index_job_failed"'
docker compose --project-directory . --env-file .env -f deploy/compose/docker-compose.yml logs backend | rg '"error_source":"llm_provider"|"error_source":"postgres"|"error_source":"vector_store"'
curl -s -H "Authorization: Bearer <access_token>" http://127.0.0.1:8000/chat/vector-index-jobs/health
```

## 生产安全与数据持久化

本节面向正式部署或公开 demo 的上线前检查。生产 `.env` 只保存在服务器或 secret store，不提交、不截图、不粘贴到 issue；仓库中只维护 `deploy/compose/.env.example` 这类占位模板。

### Secret 管理

| 配置 | 生产要求 | 轮换影响 |
| --- | --- | --- |
| `POSTGRES_PASSWORD` | 使用非默认强密码，通过服务器 `.env`、CI/CD secret 或部署平台 secret 注入。 | 需要同步 PostgreSQL 用户密码；如设置了 `COMPOSE_DATABASE_URL`，也要同步更新连接串，并重启依赖服务。 |
| `JWT_SECRET_KEY` | 使用至少 32 字符随机值，例如 `openssl rand -hex 32`。 | 轮换后已签发 token 全部失效，用户需要重新登录。 |
| `USER_SETTINGS_ENCRYPTION_KEY` | 使用 Fernet key，和 `JWT_SECRET_KEY` 分离，例如 `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`。 | 丢失或更换后无法解密已保存的用户 API Key，必须先清空或重新录入用户凭据。 |
| `LLM_API_KEY` / `DEEPSEEK_API_KEY` | 默认 provider Key 只放在生产 secret 中；如果只允许用户自带 Key，也不能留下占位值覆盖回退逻辑。 | 轮换后重启 backend 和 worker；失败时聊天会返回 provider 配置错误。 |
| `ZAI_EMD_API` | embedding Key 只放在生产 secret 中。 | 轮换后重启 backend 和 worker；失败时向量化会失败。 |
| `ALLOW_USER_CUSTOM_LLM_BASE_URL` | 公开环境默认保持 `false`。 | 开启前必须先完成 SSRF 出口策略、域名 allowlist 或网络隔离。 |
| `DATABASE_URL` | 仅用于宿主机 conda 方式运行或本地 migration dry-run；Docker Compose 内部连接由 compose 环境覆盖。 | 生产只用 compose 时可以删除该项，避免残留模板连接串。 |
| `COMPOSE_DATABASE_URL` | 仅在外部数据库或特殊连接串时设置；否则让 compose 根据 `POSTGRES_*` 构造。 | 设置后必须和 PostgreSQL 实际用户、密码、库名保持一致。 |

上线前执行生产 preflight。该脚本只输出变量名和检查结论，不输出真实 secret：

```bash
conda run -n firstrag python scripts/production_preflight.py --env-file .env --skip-migration-dry-run
```

当 PostgreSQL 已启动且允许临时运行 compose migrate 容器后，执行完整检查：

```bash
conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method compose
```

如果使用宿主机 conda 环境直接访问数据库，也可以改用 local dry-run：

```bash
conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method local
```

preflight 会拦截以下问题：

- `POSTGRES_PASSWORD`、`JWT_SECRET_KEY`、`USER_SETTINGS_ENCRYPTION_KEY`、`LLM_API_KEY`、`ZAI_EMD_API` 仍是模板占位值或明显过短。
- `USER_SETTINGS_ENCRYPTION_KEY` 不是 Fernet key，或与 `JWT_SECRET_KEY` 相同。
- `DATABASE_URL` / `COMPOSE_DATABASE_URL` 仍含模板账号、密码或占位值。
- `FRONTEND_PORT`、`BACKEND_PORT`、`POSTGRES_PORT` 未绑定到 `127.0.0.1` / `localhost`。
- `UPLOADS_DIR`、`VECTOR_DB_DIR`、`MODELS_DIR` 缺失，或 reranker 模型目录不存在。
- `docker compose --project-directory . --env-file .env -f deploy/compose/docker-compose.yml config --quiet` 失败。
- migration dry-run 失败。

### PostgreSQL 备份与恢复

生产环境至少保留以下备份节奏：

| 类型 | 频率 | 保留周期 | 触发时机 |
| --- | --- | --- | --- |
| 逻辑备份 `pg_dump --format=custom` | 每日 1 次 | 最近 7 份每日备份、4 份周备份、3 份月备份 | 定时任务。 |
| 发布前备份 | 每次部署前 | 至少保留到本次发布验证完成后 7 天 | 执行 migration 或升级镜像前。 |
| 目录快照 | 每日或随云盘快照策略 | 与 PostgreSQL 备份周期一致 | 覆盖 `uploads/`、`vector_db/` 和必要模型文件。 |
| 恢复演练 | 每月至少 1 次 | 保留演练记录 | 在 staging 或临时实例恢复最近一次备份。 |

备份文件必须受控保存且不能提交到 Git；本仓库已忽略 `/backups/`，但生产备份更建议放到独立磁盘或对象存储，并开启加密和访问审计。

示例备份命令：

```bash
mkdir -p backups/postgres
docker compose --project-directory . --env-file .env -f deploy/compose/docker-compose.yml exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner' \
  > "backups/postgres/firstrag-$(date +%Y%m%d%H%M%S).dump"
```

恢复前先停止会写入数据库的服务，并优先在 staging 演练：

```bash
docker compose --project-directory . --env-file .env -f deploy/compose/docker-compose.yml stop frontend backend worker
docker compose --project-directory . --env-file .env -f deploy/compose/docker-compose.yml exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' \
  < backups/postgres/firstrag-YYYYMMDDHHMMSS.dump
docker compose --project-directory . --env-file .env -f deploy/compose/docker-compose.yml run --rm migrate python /app/scripts/migrate_db.py --dry-run
docker compose --project-directory . --env-file .env -f deploy/compose/docker-compose.yml up -d backend worker frontend
```

恢复验证：

1. `docker compose --project-directory . --env-file .env -f deploy/compose/docker-compose.yml run --rm migrate python /app/scripts/migrate_db.py --dry-run` 应显示所有已应用 migration 为 skipped，或只显示预期的 pending migration。
2. 登录预置账号，确认知识库、文件 metadata、会话和历史消息存在。
3. 打开文件管理，确认文件状态和 vector index job 状态可读。
4. 对已索引知识库提问，确认回答能返回 sources。
5. 检查 backend、worker、postgres 日志，不应出现数据库连接、Chroma 读取或文件缺失错误。

### 文件、向量库和模型目录

生产环境建议将数据目录放在独立数据盘，例如：

```bash
mkdir -p /srv/firstrag/uploads /srv/firstrag/vector_db /srv/firstrag/models /srv/firstrag/backups
```

`.env` 中设置：

```bash
UPLOADS_DIR=/srv/firstrag/uploads
VECTOR_DB_DIR=/srv/firstrag/vector_db
MODELS_DIR=/srv/firstrag/models
```

目录策略：

- `uploads/` 是用户上传原文，必须和 PostgreSQL metadata 一起备份；恢复时路径结构要保持不变。
- `vector_db/` 保存 Chroma 数据，建议随 `uploads/` 一起备份。理论上可通过重新 vector indexing 重建，但恢复成本高，公开环境优先保留备份。
- `models/` 保存 reranker 模型，生产以只读方式挂载到 `/app/models`。模型文件可从制品仓库或模型源重建，但上线前必须确认 `models/rerankers/bge-reranker-base` 存在。
- 日志当前走 Docker stdout/stderr，由 Docker 日志驱动持久化和轮转；接入集中日志前不要新增会写入 secret 或用户原文的应用文件日志。

迁移数据盘或换机时，顺序为：停止写入服务、完成 PostgreSQL dump、同步 `uploads/` 和 `vector_db/`、同步或重新准备 `models/`、在新机器恢复数据库、运行 migration dry-run、启动服务并完成 smoke test。

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
| 上传文件 | 通过 `UPLOADS_DIR` 挂载到 `/app/uploads` | 公开 demo 禁止上传私密文件，并需要清理策略。 |
| Chroma 数据 | 通过 `VECTOR_DB_DIR` 挂载到 `/app/vector_db` | 可从上传文件重建，但保留备份能减少恢复时间。 |
| reranker 模型 | 通过 `MODELS_DIR` 只读挂载到 `/app/models` | 模型目录只读挂载；上线前确认模型文件已存在。 |
| 日志 | 使用 Docker `json-file` 轮转，后续接入集中日志 | 日志不得包含 API Key、JWT、数据库密码或用户上传原文。 |

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
| `USER_UPLOAD_MAX_FILES` / `USER_UPLOAD_MAX_BYTES` | 设置用户级文件数量和总容量上限；公开 demo 建议保守配置。 |
| `LOGIN_FAILURE_RATE_LIMIT_*` / `*_RATE_LIMIT_MAX_REQUESTS` | 后端进程内限流阈值；多实例部署还要叠加网关或 WAF。 |
| `VECTOR_INDEX_MAX_BATCH_FILES` | 单次知识库批量向量化可提交的最大文件数。 |
| `FRONTEND_PORT` / `BACKEND_PORT` / `POSTGRES_PORT` | 建议设为 `127.0.0.1:3000`、`127.0.0.1:8000`、`127.0.0.1:5432`，由反向代理暴露 HTTPS。 |

公开 demo 推荐额外设置：

```bash
FRONTEND_PORT=127.0.0.1:3000
BACKEND_PORT=127.0.0.1:8000
POSTGRES_PORT=127.0.0.1:5432
MAX_UPLOAD_FILE_SIZE_BYTES=20971520
USER_UPLOAD_MAX_FILES=100
USER_UPLOAD_MAX_BYTES=1073741824
VECTOR_INDEX_MAX_BATCH_FILES=50
LOGIN_FAILURE_RATE_LIMIT_MAX_ATTEMPTS=5
LOGIN_FAILURE_RATE_LIMIT_WINDOW_SECONDS=300
API_RATE_LIMIT_WINDOW_SECONDS=60
CHAT_RATE_LIMIT_MAX_REQUESTS=30
UPLOAD_RATE_LIMIT_MAX_REQUESTS=10
VECTOR_INDEX_RATE_LIMIT_MAX_REQUESTS=20
MODEL_TEST_RATE_LIMIT_MAX_REQUESTS=10
ALLOW_USER_CUSTOM_LLM_BASE_URL=false
UPLOADS_DIR=/srv/firstrag/uploads
VECTOR_DB_DIR=/srv/firstrag/vector_db
MODELS_DIR=/srv/firstrag/models
```

反向代理要求：

- 终止 TLS，强制 HTTP 跳转 HTTPS。
- 将域名请求转发到 `http://127.0.0.1:3000`。
- 上传 body size 不大于 `MAX_UPLOAD_FILE_SIZE_BYTES`。
- 后端已提供进程内限流；反向代理仍建议对登录、注册、上传、聊天和模型设置接口做 IP 级限流，覆盖多进程、多实例和恶意突发流量。
- 对 SSE streaming 关闭响应缓冲，避免聊天 token 被代理层攒批返回。

仓库提供了 Nginx 配置模板，位于 `deploy/nginx/`：

| 文件 | 用途 |
| --- | --- |
| `00-firstrag-shared.conf` | 定义 frontend upstream、WebSocket/SSE 连接变量和公网 IP 级限流 zone。 |
| `firstrag-proxy-locations.inc` | 公共 proxy location 片段，只把公网请求转发到 frontend API proxy，不直接暴露 FastAPI 或 PostgreSQL。 |
| `10-firstrag-public-demo.conf` | 可直接执行 `nginx -t` 的示例配置，适用于 Cloudflare Tunnel、负载均衡器或其它可信 TLS 终止层位于 Nginx 前面的场景。 |
| `firstrag-public-demo.tls.conf.example` | Nginx 直接终止 TLS 时使用的 server block 模板，证书存在后复制为 `.conf` 并替换域名和证书路径。 |

使用方式：

1. 将 `demo.example.com` 替换为真实域名。
2. 保持 `FRONTEND_PORT=127.0.0.1:3000`、`BACKEND_PORT=127.0.0.1:8000`、`POSTGRES_PORT=127.0.0.1:5432`，Nginx 只访问 frontend upstream。
3. 如果 Nginx 前面已有 Cloudflare Tunnel、负载均衡器或其它 TLS 终止层，可以使用 `10-firstrag-public-demo.conf`，但应通过防火墙或内网绑定限制 Nginx 的 HTTP 入口来源。
4. 如果 Nginx 直接暴露公网并终止 TLS，复制 `firstrag-public-demo.tls.conf.example` 为 `.conf`，替换证书路径，然后停用 `10-firstrag-public-demo.conf`，避免 HTTP 明文入口继续代理业务请求。
5. `firstrag-proxy-locations.inc` 中的 `client_max_body_size 20m` 必须与 `.env` 的 `MAX_UPLOAD_FILE_SIZE_BYTES` 保持一致；若公开 demo 调小上传上限，需要同步修改两处。
6. 上线前先在本地或服务器执行语法检查：

```bash
docker run --rm -v "$PWD/deploy/nginx:/etc/nginx/conf.d:ro" nginx:alpine nginx -t
```

如果启用直接 TLS 模板，还需要在证书文件存在的服务器上重新执行 `nginx -t`，确保 `ssl_certificate` 与 `ssl_certificate_key` 路径有效。

### 演示账号和安全边界

- 演示账号在服务器上线后通过 UI 创建，账号和密码只通过可信渠道单独提供，不写入仓库文档。
- 当前应用仍开放注册接口，公开 demo 上线前需要在反向代理层临时加访问控制、Basic Auth、IP allowlist 或实现后端注册开关。
- 不要求访客输入自己的真实 API Key；如果需要测试用户 Key 模式，必须提示只在可信 demo 环境使用，且前端不会持久化完整 Key。
- 上传文件只用于演示，不接收私人、商业或敏感文档。公开 demo 应在页面说明上传数据会被定期清理。
- 进程内限流状态不会跨多实例共享；公网访问仍应由反向代理、WAF 或 API 网关承担全局限流。

### 数据清理策略

上线前需要准备一个可重复执行的清理流程：

1. 保留预置演示账号和少量脱敏样例知识库。
2. 定期删除临时用户、临时知识库、上传文件、向量索引和对应 chunks。
3. 清理后运行一次最小 smoke test：登录、上传小文件、向量化、提问和查看 sources。
4. 清理脚本未完成前，公开 demo 应只提供给受控测试者。

当前仓库还没有专门的 demo cleanup 脚本，因此这是正式公开上线前的阻塞项。

### 启动步骤

1. 准备云服务器、域名和 TLS 方案，只开放 80/443 和受控 SSH。
2. 在服务器拉取仓库，复制 `deploy/compose/.env.example` 为根目录 `.env`，填写非默认密钥和 provider Key。
3. 准备 `MODELS_DIR/rerankers/bge-reranker-base`，并确认 `UPLOADS_DIR`、`VECTOR_DB_DIR` 可持久化。
4. 运行 `conda run -n firstrag python scripts/production_preflight.py --env-file .env --skip-migration-dry-run` 检查 secret、端口和目录。
5. 运行 `docker compose --project-directory . --env-file .env -f deploy/compose/docker-compose.yml config --quiet` 检查 Compose 配置。
6. 运行 `docker compose --project-directory . --env-file .env -f deploy/compose/docker-compose.yml build` 构建镜像。
7. 运行 `docker compose --project-directory . --env-file .env -f deploy/compose/docker-compose.yml up -d postgres` 启动 PostgreSQL。
8. 运行 `conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method compose` 检查 migration dry-run。
9. 运行 `docker compose --project-directory . --env-file .env -f deploy/compose/docker-compose.yml up -d` 启动 migration、backend、frontend 和 worker。
10. 运行 `docker compose --project-directory . --env-file .env -f deploy/compose/docker-compose.yml logs -f migrate backend worker frontend`，确认 migration 成功、backend 和 worker 无启动错误。
11. 配置反向代理到 `http://127.0.0.1:3000`，并设置 TLS、body size、SSE buffering 和限流。
12. 创建演示账号，上传脱敏样例文件并完成一次向量化和聊天 smoke test。
13. 在 README 中补充真实 demo URL、使用限制和数据清理说明后，才把 Roadmap 的“发布在线演示环境”标记为完成。

### 当前阻塞项

- 尚未选择真实服务器、域名和 TLS 入口。
- `deploy/nginx/` 已提供公网反向代理模板，尚需在真实服务器替换域名、证书路径并完成 `nginx -t`。
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

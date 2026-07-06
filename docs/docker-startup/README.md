# Docker 启动流程

本文档记录 FirstRAG 使用 Docker Compose 启动本地完整链路的流程。Compose 会启动 Redis、PostgreSQL、migration、FastAPI backend、Next.js frontend 和 vector index worker。

服务器级 secret 写入仓库根目录 `.env`，不要提交、截图或粘贴真实 JWT secret、数据库密码和用户凭据。聊天模型、向量模型和远程 rerank API Key 在用户登录后的“模型设置”页保存为密文，不再写入 `.env`。

## 1. 前置条件

- Docker Desktop 已启动，或 Linux 服务器上 Docker daemon 正常运行。
- 仓库位于本机可写目录，例如 `/Users/bing/Desktop/Github/FirstRAG`。
- 聊天模型、向量模型和远程 rerank Key 可以登录后配置；未配置时服务仍可启动，但聊天调用、向量化和向量检索会提示先补充用户配置。
- 默认 Docker 镜像不安装 `torch` / `transformers`。本地 CrossEncoder rerank 会自动降级为 RRF 结果；如需启用本地 rerank，再安装可选依赖并下载 Hugging Face 模型 `BAAI/bge-reranker-base`。也可以在设置页改用 Qwen、Voyage、Cohere、Jina 或自定义远程 rerank API。

## 2. 准备目录

在仓库根目录执行：

```bash
cd /Users/bing/Desktop/Github/FirstRAG
mkdir -p uploads vector_db models/rerankers
```

这些目录会挂载到容器内：

| 宿主路径 | 容器路径 | 说明 |
| --- | --- | --- |
| `./uploads` | `/app/uploads` | 用户上传文件。 |
| `./vector_db` | `/app/vector_db` | Chroma 持久化数据。 |
| `./models` | `/app/models` | 可选本地 reranker 模型，只读挂载。 |

## 3. 准备 `.env`

复制模板：

```bash
cp .env.example .env
```

编辑 `.env`，至少替换启动必需的值：

```bash
POSTGRES_PASSWORD=replace-with-a-strong-local-password
JWT_SECRET_KEY=replace-with-a-random-secret
USER_SETTINGS_ENCRYPTION_KEY=replace-with-a-fernet-key
```

聊天模型、向量模型和远程 rerank 的 provider、model、API Key、可选维度或 API 地址在前端“模型设置”页配置。保存后立即影响当前用户后续聊天、向量化和检索精排，不需要重启 backend 或 worker。

可以用下面命令生成本地开发用随机值：

```bash
openssl rand -base64 24
openssl rand -hex 32
conda run -n firstrag python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Docker Compose 运行时还建议确认这些路径配置：

```bash
MODELS_DIR=./models
VECTOR_DB_DIR=./vector_db
UPLOADS_DIR=./uploads
VECTOR_STORE_PATH=/app/vector_db/chroma
RERANKER_MODEL_PATH=/app/models/rerankers/bge-reranker-base
FRONTEND_PORT=127.0.0.1:3000
BACKEND_PORT=127.0.0.1:8000
POSTGRES_PORT=127.0.0.1:5432
```

注意：`DATABASE_URL` 主要用于宿主机 conda 方式运行；Compose 内部默认使用 `POSTGRES_DB`、`POSTGRES_USER` 和 `POSTGRES_PASSWORD` 生成容器网络里的数据库连接。如果需要外部数据库，再设置 `COMPOSE_DATABASE_URL`。

Redis 默认使用 Compose 内置 `redis` service，backend 和 worker 通过
`REDIS_URL=redis://redis:6379/0` 访问。当前 Redis 已接入基础设施健康检查、
RAG 热点共享缓存、后端分布式限流和 vector worker 运行态。Compose 默认不把
Redis 端口映射到宿主机；生产环境如切换托管 Redis，应在 `.env` 中把
`REDIS_URL` 改为内网地址或带认证的 `rediss://` 连接串。

## 4. 可选：配置远程 rerank

推荐在登录后的“模型设置”页配置远程 rerank。当前支持 Qwen、Voyage、Cohere、Jina 和自定义 rerank API；远程 provider 的 Key 会按用户和厂商加密保存。

如需兼容旧的全局 Qwen rerank 环境变量，也可以在 `.env` 中使用下面配置：

```bash
RERANK_PROVIDER=qwen
RERANK_MODEL=qwen3-rerank
# 替换为你的阿里云工作空间 OpenAI-compatible 地址，并按控制台地域调整。
RERANK_BASE_URL=https://<WorkspaceId>.ap-southeast-1.maas.aliyuncs.com/compatible-api/v1
RERANK_API_KEY=your-rerank-api-key
```

修改 `.env` 后重启 backend 和 worker：

```bash
docker compose up -d --force-recreate backend worker
```

注意：切换用户级 embedding provider、模型或维度后，需要重新向量化相关知识文件。系统会按用户和 embedding 配置隔离 Chroma collection，避免不同维度互相污染。

## 5. 可选：启用本地 reranker

最小 Docker 依赖不包含 `torch` 和 `transformers`。不安装它们时，基础聊天、上传、向量化和 RRF 融合检索仍可启动；涉及 CrossEncoder rerank 的检索会自动降级。

若要启用 rerank，先安装可选依赖：

```bash
cd backend
conda activate firstrag
python -m pip install -r requirements-rerank.txt
```

项目中的 reranker 使用 `local_files_only=True` 加载模型，所以运行时不会自动联网下载。还需要把 Hugging Face 模型拉到 `models/rerankers/bge-reranker-base`：

```bash
conda run -n firstrag python -m pip install -U huggingface_hub
conda run -n firstrag hf download BAAI/bge-reranker-base \
  --local-dir models/rerankers/bge-reranker-base
```

也可以使用 Git LFS：

```bash
git lfs install
git clone https://huggingface.co/BAAI/bge-reranker-base \
  models/rerankers/bge-reranker-base
```

如果暂时不安装依赖或不下载该模型，基础聊天、上传和向量化仍可启动；涉及 rerank 的检索会在可观测日志中记录降级原因。

## 6. 启动

先检查 Compose 配置：

```bash
docker compose config --quiet
```

构建并后台启动：

```bash
docker compose up -d --build
```

首次启动时，`redis` 和 `postgres` 健康检查通过后会自动运行 `migrate` service 初始化或升级 schema；`backend` 和 `worker` 会等待 Redis 健康且 migration 成功后再启动。

## 7. 查看状态

```bash
docker compose ps
docker compose logs -f redis migrate backend worker frontend
```

常用访问地址：

| 服务 | 地址 |
| --- | --- |
| 前端 | `http://localhost:3000` |
| 后端文档 | `http://localhost:8000/docs` |
| PostgreSQL | `127.0.0.1:5432` |

推荐 smoke test：

1. 打开 `http://localhost:3000`。
2. 注册并登录本地测试账号。
3. 进入模型设置，配置并测试聊天模型和向量模型 API Key；如需远程 rerank，也在同页选择 provider 并保存对应 Key。
4. 新建知识库，上传一份 `.md`、`.txt`、`.pdf` 或 `.docx` 文件。
5. 触发向量化，等待任务成功。
6. 对知识库提问，确认回答、sources 和任务队列状态正常。

## 8. 常用命令

```bash
# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f redis backend worker frontend

# 只重启后端和 worker
docker compose up -d --build backend worker

# 手动运行 migration dry-run
docker compose run --rm migrate python /app/scripts/migrate_db.py --dry-run

# 停止服务，保留数据
docker compose down

# 停止服务并删除 PostgreSQL volume
docker compose down -v
```

`docker compose down -v` 会删除 PostgreSQL named volume `postgres_data`，只在明确需要重置本地数据库时使用。

## 9. 镜像体积与 worker

`backend`、`migrate` 和 `worker` 都使用 `deploy/docker/backend.Dockerfile` 构建的 Python runtime 镜像。worker 的启动命令不同，但它仍需要文档解析、embedding、Chroma 入库和 PostgreSQL 队列依赖，因此不会比后端小很多。

后端 Dockerfile 使用 multi-stage build：`builder` 阶段安装编译工具并构建 Python virtualenv，最终 `runtime` 镜像只保留运行依赖和 Chroma/ONNX 可能需要的 `libgomp1`。默认最小镜像不安装 `torch`、`transformers` 和本地 CrossEncoder rerank 依赖。

`docker compose images` 可能会分别列出 `backend`、`migrate` 和 `worker` 的镜像大小；这些服务的底层 layer 可复用，不应简单按三份相加估算磁盘占用。修改依赖或 Dockerfile 后，如需释放旧镜像和构建缓存，可在确认不删除数据库 volume 的前提下执行：

```bash
docker compose down --rmi local
docker builder prune
docker compose up -d --build
```

不要使用 `docker compose down -v` 清理镜像；它会删除 PostgreSQL 数据 volume。

## 10. 常见问题

### Docker daemon 未运行

如果出现 `Cannot connect to the Docker daemon`，先启动 Docker Desktop，再重试：

```bash
docker compose ps
```

### 端口被占用

如果 `3000`、`8000` 或 `5432` 已被占用，在 `.env` 中改为其它本机端口：

```bash
FRONTEND_PORT=127.0.0.1:3001
BACKEND_PORT=127.0.0.1:8001
POSTGRES_PORT=127.0.0.1:5433
```

前端容器内部仍通过 `http://backend:8000` 访问后端，不需要改 `BACKEND_ORIGIN`。

### migration 失败

查看 migration 日志：

```bash
docker compose logs migrate
```

确认 `.env` 中 `POSTGRES_DB`、`POSTGRES_USER`、`POSTGRES_PASSWORD` 和可选的 `COMPOSE_DATABASE_URL` 一致。如果是首次本地测试且不需要保留数据，可以在确认影响后重置 volume：

```bash
docker compose down -v
docker compose up -d --build
```

### 上传或向量化失败

确认当前登录用户已在“模型设置”页配置向量模型 provider、model 和 API Key，并查看 worker 日志：

```bash
docker compose logs -f worker
```

如果文件解析成功但检索质量不稳定，确认 reranker 模型目录是否存在：

```bash
ls models/rerankers/bge-reranker-base
```

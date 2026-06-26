# 部署说明

当前仓库已拆分为 `frontend/` 和 `backend/`，本地开发建议分别启动前端、后端和 worker。

## 环境变量

根目录 `.env` 是后端运行时配置来源。请从 `.env.example` 复制：

```bash
cp .env.example .env
```

常用配置：

| 变量 | 说明 |
| --- | --- |
| `DATABASE_URL` | PostgreSQL 连接串。 |
| `JWT_SECRET_KEY` | JWT 签名密钥。 |
| `LLM_PROVIDER` | 默认平台模型厂商。 |
| `LLM_MODEL` | 默认模型名。 |
| `LLM_API_KEY` | 平台模型 API Key。 |
| `USER_SETTINGS_ENCRYPTION_KEY` | 用户 API Key 加密主密钥。 |
| `ZAI_EMD_API` | 智谱 embedding API Key。 |
| `VECTOR_STORE_PATH` | Chroma 持久化路径，默认 `./vector_db/chroma`；相对路径会按项目根目录解析。 |
| `RERANKER_MODEL_PATH` | 本地 reranker 模型路径。 |

敏感信息不要提交到 Git。

## 本地启动

后端：

```bash
cd backend
conda activate firstrag
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev
```

worker：

```bash
cd backend
conda activate firstrag
python -m app.workers.vector_index_worker
```

## 端口约定

| 服务 | 默认地址 |
| --- | --- |
| 前端 | `http://localhost:3000` |
| 后端 | `http://127.0.0.1:8000` |
| PostgreSQL | 由 `DATABASE_URL` 决定 |
| Chroma | 本地持久化目录，不单独暴露端口 |

## 部署目录

`deploy/` 预留部署配置：

```text
deploy/
├── docker/
└── nginx/
```

`docker-compose.yml` 当前是占位骨架，后续可补充 PostgreSQL、后端、前端和 worker 服务。

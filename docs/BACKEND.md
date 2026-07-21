# 后端结构说明

后端位于 `backend/`，使用 FastAPI 提供 HTTP API，使用 PostgreSQL 和 Chroma 完成 RAG 数据存储。

## 目录结构

```text
backend/
├── app/
│   ├── api/             # FastAPI 路由
│   ├── core/            # 配置、安全、密钥加密
│   ├── db/              # 数据库连接、SQL 执行器、迁移 SQL
│   ├── repositories/    # 数据访问层
│   ├── schemas/         # Pydantic 请求模型
│   ├── services/        # 业务逻辑
│   └── workers/         # 后台 worker
├── demo/                # 历史 demo / 兼容入口
├── tests/               # 后端测试
├── main.py              # ASGI app 兼容导出
└── requirements.txt
```

## 启动

默认通过仓库根目录 Docker Compose 启动后端、数据库、migration、前端和 worker：

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 redis migrate backend worker frontend postgres
```

配置从 monorepo 根目录 `.env` 加载，不从 `backend/.env` 加载。常规验证应基于 Compose 容器完成。

本地单独启动 FastAPI 仅用于专项调试：

```bash
cd backend
conda activate firstrag
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 路由模块

| 文件 | 主要职责 |
| --- | --- |
| `auth.py` | 注册、登录、JWT 返回。 |
| `chat.py` | SSE 聊天接口和 RAG 链调用。 |
| `conversations.py` | 会话列表、创建、重命名、删除、消息和诊断读取。 |
| `health.py` | 后端和 Redis 基础设施健康检查，不返回敏感连接串。 |
| `knowledge_bases.py` | 知识库列表、创建、重命名、回收站删除/恢复和文件关联管理。 |
| `knowledge_files.py` | 文件上传、复用、知识文件列表、引用 chunk 上下文、原始文件读取和永久删除入口。 |
| `user_settings.py` | 用户模型厂商、凭据、测试连接和设置保存。 |
| `vector_indexes.py` | 文件/知识库向量化任务、任务状态和向量删除。 |

## 服务模块

| 文件 | 主要职责 |
| --- | --- |
| `chat_service.py` | SSE 事件、消息持久化、回答落库。 |
| `rag_service.py` | RAG 兼容门面，继续导出历史 public function。 |
| `rag/chain_builder.py` | LCEL 链构建、Router chain 和 QA chain。 |
| `rag/retrieval_decision.py` | 检索设置规范化、Router 结果解析和最终检索决策。 |
| `rag/retrieval_pipeline.py` | retrieval settings、知识库画像、文件范围和 hybrid retrieval 编排。 |
| `rag/reference_serializer.py` | prompt context 格式化和 Sources 序列化。 |
| `rag/diagnostics.py` | RAG timing、retrieval settings diagnostics 和 LLM usage 合并。 |
| `rag/streaming.py` | LCEL stream chunk 到 SSE 事件的转换。 |
| `llm_service.py` | OpenAI 兼容模型厂商预设、用户/平台配置解析。 |
| `cache_service.py` | Redis JSON cache adapter，提供 TTL、delete、prefix invalidation 和故障 fallback。 |
| `redis_service.py` | Redis client 封装、连接健康检查和 Redis URL 脱敏。 |
| `core/rate_limit.py` | Redis 优先 sliding-window 限流；输出不含 identifier 的命中、fallback 和 fail-closed 结构化事件。 |
| `file_service.py` | 上传文件大小限制、SHA-256、落盘路径。 |
| `documents/document_service.py` | 文档加载、图片知识文件 vision 解析、切分、向量库构建。 |
| `knowledge_file_lifecycle_service.py` | 在单文件 advisory lock 下编排 Chroma、PostgreSQL 与磁盘的永久删除。 |
| `retrieval/*` | 向量检索、全文检索、RRF 融合、本地 CrossEncoder 或用户级远程 rerank 精排。 |
| `vectors/*` | embedding 模型、向量化队列、索引生命周期和 Redis worker 运行态。 |

## Worker

向量化任务由 Compose 中的 `worker` service 处理。需要本地专项排查时，也可以单独启动 worker：

```bash
cd backend
conda activate firstrag
python -m app.workers.vector_index_worker
```

worker 从 PostgreSQL `vector_index_jobs` 领取任务，解析文件、切分文本、写 Chroma、写 PostgreSQL chunk，并更新任务状态。PDF 逐页解析并保存真实页码，DOCX 从 OOXML 保存原始段落范围；同一文件跨 page/block 的 chunk index 保持全局连续。Compose 中的 backend 与 worker 都通过 HTTP 访问独立 `chroma` service，避免多个 embedded Chroma 进程共享持久化目录导致 HNSW 视图不可见。Redis 只保存短 TTL 运行态：worker 心跳、当前任务摘要、单文件短租约和运行指标；Redis 不可用时 worker 会继续依赖 PostgreSQL 队列处理任务。图片知识文件会在 worker 中通过当前用户的 vision 聊天模型解析为可检索 Markdown；解析失败只会标记当前任务失败，不阻塞后续队列。常规验证仍以 Docker Compose 中的 `worker` service 为准。

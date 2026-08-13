# 后端结构说明

后端位于 `backend/`，使用 FastAPI 提供 HTTP API，并通过 PostgreSQL 与 provider-neutral vector store boundary 完成 RAG 数据存储。Milvus 是唯一受支持的 vector store，已接入写入、重建、删除、filtered ANN、diagnostics 和 authenticated health gate。

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
├── sparse_encoder/      # 独立 BGE-M3 sparse HTTP service 与共享 contract
├── tests/               # 后端测试
├── main.py              # ASGI app 兼容导出
└── requirements.txt
```

## 启动

默认通过仓库根目录 Docker Compose 启动后端、数据库、migration、前端和 worker：

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 redis postgres milvus-etcd milvus-minio milvus-standalone milvus-health-probe sparse-encoder migrate backend worker frontend
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
| `knowledge_files.py` | 文件上传、复用、知识文件列表、引用 chunk 上下文、原始文件读取、PDF 页级 PNG 预览和永久删除入口。 |
| `user_settings.py` | 用户模型厂商、凭据、测试连接和设置保存。 |
| `vector_indexes.py` | 文件/知识库向量化任务、任务状态、向量删除和 PDF OCR 页级质量清单。 |

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
| `knowledge_file_lifecycle_service.py` | 在单文件 advisory lock 下编排 Milvus entities、PostgreSQL metadata 与磁盘原文的永久删除。 |
| `retrieval/*` | Milvus dense/sparse 检索与 RRF、本地 CrossEncoder 或用户级远程 rerank 精排、parent context 扩展。 |
| `vectors/*` | embedding 模型、provider-neutral vector store、Milvus adapter、authenticated probes、向量化队列、索引生命周期和 Redis worker 运行态。 |
| `sparse_encoder_client.py` | backend/query 与 worker/document 共用的内网 sparse encoder client；严格复核 model、revision、mode 和返回数量。 |

## BGE-M3 sparse encoder

`backend/sparse_encoder/` 是独立 FastAPI application，不挂到公开 backend router。real runtime 使用 `FlagEmbedding==1.4.0` 加载固定 Hugging Face snapshot，只返回 lexical weights；CI 的 `fixture` runtime 只验证相同 HTTP contract 和资源门禁，production preflight 会拒绝 fixture。服务限制 batch、单文本字符数、请求体、并发和 timeout，并禁止在异常或访问日志中输出请求正文。Compose 不映射 8090 host port，backend 与 worker 都通过 `http://sparse-encoder:8090` 访问同一个实例。

## Worker

向量化任务由 Compose 中的 `worker` service 处理。需要本地专项排查时，也可以单独启动 worker：

```bash
cd backend
conda activate firstrag
python -m app.workers.vector_index_worker
```

worker 从 PostgreSQL `vector_index_jobs` 领取任务，解析文件、切分 parent/child 文本，通过 Milvus adapter 一次写入 dense/sparse vectors、child `content`、`parent_content`、stable IDs 与位置 metadata，并更新任务状态。PDF 逐页解析并保存真实页码；parser 为纯图片生成的 `picture ... intentionally omitted` 占位提示会先被剔除，无有效文本层的页面才会渲染并调用本地 Tesseract，默认使用 `chi_sim+eng`，一次调用同时产出正文和 TSV confidence，并把字符加权页级置信度写入 metadata，不调用用户 LLM。低质量 OCR 页可通过受控 `vector_index_jobs.options` 强制再次识别；多页选择合并进同一个 `force_ocr_page_numbers`，一次只生成一个版本和一个整文件重建 job，失败重试从原 job 恢复 options。`pdf_ocr_engine.py` 让主动重识别在有界总超时内比较原图、灰度、二值化和旋转候选；首次索引只运行基线，单候选失败不会阻断其他候选，选中结果与候选摘要写入 metadata。每次成功解析还会把页级 Tesseract 原文、SHA-256、confidence、word count、attempt、trigger、strategy/PSM/rotation、候选摘要和 source job 写入 `knowledge_file_ocr_history`；attempt 从历史单调递增。人工修订持久化到 `knowledge_file_ocr_corrections`；worker 在 OCR 后、切分前应用当前 revision，但不会用人工正文覆盖 OCR history。DOCX 从 OOXML 保存原始段落范围；同一文件跨 page/block 的 chunk index 保持全局连续。backend 与 worker 使用各自独立的 authenticated PyMilvus client，并由 Strong consistency、count/identity/text 对账和 dense/sparse self-hit 保证跨进程可见。Redis 只保存短 TTL 运行态：worker 心跳、当前任务摘要、单文件短租约和运行指标；Redis 不可用时 worker 会继续依赖 PostgreSQL 队列处理任务。图片知识文件会在 worker 中通过当前用户的 vision 聊天模型解析为可检索 Markdown；解析失败只会标记当前任务失败，不阻塞后续队列。常规验证仍以 Docker Compose 中的 `worker` service 为准。

OCR 校对工作台不依赖浏览器内置 PDF plugin。`pdf_page_preview_service.py` 在用户权限与 uploads 路径校验后，用 PyMuPDF 将单个目标页即时渲染为最长边不超过 1800px 的 RGB PNG；响应使用私有短缓存且不写入磁盘。无效页码或非 PDF 返回 `400`，损坏或暂时无法渲染的 PDF 返回安全的 `422` 提示。

`pdf_ocr_quality_service.py` 为文件管理提供只读巡检清单。它读取当前用户 Milvus collection 中当前 `index_version` 的 OCR 代表 entities，并合并 `knowledge_file_ocr_corrections` revision；摘要折叠空白并限制为 220 字符。该路径不触发 OCR 或磁盘访问，未索引状态返回 `409`，以避免展示旧版本质量数据。

`pdf_ocr_history_service.py` 按需读取单页最近历史，计算相邻 confidence/word count delta、文本 SHA 是否变化以及改善/下降次数；默认只在用户打开历史面板时请求。repository 查询同时关联未删除文件和 `user_id`，每页保留上限由 `PDF_OCR_HISTORY_MAX_RUNS_PER_PAGE` 控制。

`pdf_ocr_benchmark.py` 根据 versioned JSON manifest 动态生成无文本层的图片型 PDF。v2 默认十个 case，覆盖正常、旋转、低对比度、模糊、中英文混排、轻度倾斜、确定性盐椒噪点、侧边渐变阴影、小字号和表格布局；所有参数都有服务端范围上限，噪点使用 case id 派生的固定种子。评测同时调用生产 `run_pdf_page_ocr` 的基线与自适应模式，不复制候选选择逻辑；逐样本相似度、改善量、允许策略、宏平均质量和总耗时任一超限都会返回非零。报告根据完整 manifest 生成 suite fingerprint；`pdf_ocr_trend.py` 持久化有界 JSON 历史，只在 suite fingerprint、runner OS、CPU arch 和 Tesseract 完整版本都一致时计算最近中位数趋势，历史损坏只产生 warning，不遮蔽当前硬门禁结果。样本只包含固定合成文字，不读取用户上传文件，也不依赖数据库、账号或模型 API。

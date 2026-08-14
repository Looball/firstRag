# 从零构建并上线自己的 RAG

这是一条从理论、代码到上线的 FirstRAG 主线教程。它不另造一套简化版 RAG，而是沿当前仓库的真实实现学习：PostgreSQL 保存业务 metadata 和任务状态，Milvus v3 保存 dense/sparse vectors、child text 与 parent text，worker 异步完成索引，FastAPI 与 Next.js 通过 SSE 返回回答和检索诊断。

## 学习目标与路线

完成本教程后，你应当能够：

- 解释 RAG、Embedding、Chunk、Hybrid Retrieval、Rerank、LCEL 和 SSE 的作用边界。
- 在无外部密钥的隔离环境中跑通注册、上传、索引、检索、流式回答和 sources。
- 沿真实源码修改上传、异步索引、Milvus 检索和 SSE 处理，而不是维护第二套教学实现。
- 接入自己的 OpenAI-compatible LLM、Embedding 和可选 Rerank Provider。
- 使用单台 VPS、Docker Compose、Nginx 和 HTTPS 上线，并完成备份、恢复和回滚演练。

推荐学习顺序：

1. 先阅读第一章，画出“入库”和“提问”两条链路。
2. 完成第二章的 credential-free 实验，确认本机环境和 Compose 基线。
3. 按第三至第七章逐段阅读真实 route、service、worker、Milvus adapter 和前端 proxy。
4. 用第八章接入自己的 Provider，并把回答质量写成可重复评测。
5. 用第九至第十一章完成安全、上线和恢复能力。
6. 用第十二章替换成自己的领域文档，完成毕业验收。

四篇专题深挖可作为配套实验：

- [无外部密钥全链路实验](CREDENTIAL_FREE_QUICKSTART.md)
- [文件入库与异步索引](FILE_INGESTION_AND_INDEXING.md)
- [混合检索与流式回答](HYBRID_RETRIEVAL_AND_STREAMING.md)
- [前端、安全、测试与部署进阶](FRONTEND_SECURITY_TESTING_AND_DEPLOYMENT.md)

整体路径如下：

```text
理解 RAG
  -> 无外部密钥实验
  -> 文件上传与异步索引
  -> parent/child + dense/sparse 写入 Milvus
  -> filtered hybrid search + RRF + rerank
  -> LCEL + SSE + sources/diagnostics
  -> 真实 Provider 验收
  -> VPS + Docker Compose + Nginx + HTTPS
  -> 备份、恢复、回滚与持续评测
```

## 第一章：RAG 的理论模型

### 理论解释和关键决策

语言模型擅长根据参数记忆和上下文生成文本，但它不知道你的最新文档、私有资料和业务权限。RAG 把回答拆成三步：

1. Ingestion：解析文档、切分文本并生成可检索表示。
2. Retrieval：根据问题召回相关片段，再过滤、融合和精排。
3. Generation：把可信片段放进 prompt，让模型生成回答和引用。

Embedding 把文本映射到向量空间；Chunk 是可检索的文本单元；Dense Retrieval 擅长语义相似，Sparse Retrieval 擅长关键词和术语匹配。FirstRAG 将两路结果使用 RRF 融合，再对 child 结果 rerank，最后取对应的 parent context，避免只把很短、缺少上下文的片段交给模型。

当前实现的职责边界是：

| 层 | 当前职责 |
| --- | --- |
| PostgreSQL | 用户、知识库、文件 metadata、索引任务、消息和 provider 设置 |
| Milvus | dense/sparse vector、child text、parent text、用户与文件过滤字段 |
| Redis | 热点缓存、分布式限流和 worker 运行态 |
| LLM | 基于检索上下文生成回答，不负责替代权限过滤 |
| SSE | 把 token、sources、retrieval diagnostics 和失败状态逐步传给前端 |

### 源码入口

从 [RAG 流程文档](../RAG_WORKFLOW.md)、[系统架构](../ARCHITECTURE.md) 开始，再查看 [RAG service](../../backend/app/services/rag_service.py)、[retrieval 目录](../../backend/app/services/retrieval/) 和 [Milvus vector store](../../backend/app/services/vectors/milvus_vector_store.py)。

### 可复制命令

从仓库根目录查看当前 RAG 相关入口：

```bash
rg -n "RRFRanker|parent_content|sparse_embedding|text/event-stream" backend/app docs/RAG_WORKFLOW.md
```

### 预期结果与观察点

你会看到 dense/sparse 请求、RRF、parent context 和 SSE 的实现位置。若看到 PostgreSQL 被描述成当前文本检索源，说明文档或代码理解已经偏离当前基线。

### 三层练习

- 基础练习：画出从问题到回答的五个节点，并标出每个节点的存储。
- 诊断练习：解释为什么只增加 topK 不一定能解决错误引用。
- 扩展练习：为一个业务领域设计 dense、sparse、rerank 和 parent context 的组合策略。

## 第二章：环境准备与第一次运行

### 理论解释和关键决策

先使用 credential-free stub 验证工程链路，再接入真实 Provider。这样可以把“容器、数据库、队列、Milvus、SSE 是否正常”和“模型服务是否可用”分开诊断。隔离实验使用独立 Compose project、端口和 volume，不会把实验数据混入默认开发环境。

### 源码入口

阅读 [credential-free 教程](CREDENTIAL_FREE_QUICKSTART.md)、[完整 E2E 脚本](../../scripts/run_full_stack_e2e.sh) 和 [Compose 配置](../../docker-compose.yml)。

### 可复制命令

在仓库根目录执行：

```bash
docker version
docker compose version
node --version
npm --version
npm ci --prefix frontend
npx --prefix frontend playwright install chromium
FIRSTRAG_E2E_PAUSE_AFTER_TEST=1 bash scripts/run_full_stack_e2e.sh
```

如果只想启动默认开发环境：

```bash
cp .env.example .env
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 redis postgres milvus-etcd milvus-minio milvus-standalone milvus-health-probe sparse-encoder migrate backend worker frontend
```

### 预期结果与观察点

隔离 E2E 应报告注册、登录、上传、向量化、提问、SSE、sources 和 diagnostics 成功。默认 Compose 中，migrate 和 milvus-health-probe 应正常结束，postgres、redis、Milvus、sparse-encoder、backend、worker 和 frontend 应保持运行。

不要把完整 API Key 写进命令行、日志或教程；``` .env``` 只在本机保存，真实 Provider Key 在登录后的模型设置中提交。

### 三层练习

- 基础练习：运行 credential-free E2E，保存服务状态和测试报告。
- 诊断练习：只查看 migrate、milvus-health-probe、backend 和 worker 日志，判断启动失败属于依赖未就绪还是应用错误。
- 扩展练习：复制一份隔离 Compose project，改变端口并证明两套环境的 volume 和数据库互不影响。

## 第三章：文件入库与权限边界

### 理论解释和关键决策

上传不是向量化。上传 route 负责认证、权限、文件落盘和 metadata 持久化；重型解析和 embedding 通过持久化的 vector index job 异步执行。SHA-256 去重可以避免同一用户重复保存相同内容，但不能绕过用户隔离；每次查询仍需带 user_id 和软删除条件。

文件 metadata 通常包括 owner、file hash、原始文件名、大小、mime type、状态、index version 和时间戳。知识库与文件是独立关系，删除时要同时考虑关联关系、活动任务和 Milvus entity。

### 源码入口

阅读 [文件 route](../../backend/app/api/knowledge_files.py)、[文件 repository](../../backend/app/repositories/knowledge_file_repository.py)、[文件 service](../../backend/app/services/file_service.py) 和 [schema SQL](../../backend/app/db/sql/000_initial_schema.sql)。

### 可复制命令

先注册并登录测试用户，再将 token 放在当前 shell 的临时环境变量中。下面的请求只演示接口形状，不包含真实凭据：

```bash
curl -sS -X POST http://localhost:3000/api/chat/knowledge-base/<knowledge-base-id>/files \
  -H "Authorization: Bearer ${FIRSTRAG_TUTORIAL_TOKEN}" \
  -F "files=@docs/tutorials/fixtures/fictional_station.md" \
  -F "auto_index=true"
```

上传后在前端文件列表检查 file_id、hash、状态和所属知识库；不要通过绕过前端直接请求来规避后端权限。

### 预期结果与观察点

成功响应只说明 metadata 和文件已经接受，不代表 Milvus 已经有向量。随后应看到 vector_index_job 进入 queued/running/completed；失败时查看 error_message 和 worker 日志，而不是重复上传同一个文件。

### 三层练习

- 基础练习：上传同一个 fixture 两次，观察 SHA-256 去重和文件列表变化。
- 诊断练习：用另一个用户的 file_id 请求状态接口，确认返回 404 或等效的资源不可见行为。
- 扩展练习：为一个大文件画出“HTTP request 与异步 job”的时间线，并说明为什么不能在 route 内同步 indexing。

## 第四章：异步索引、OCR 与 parent/child chunk

### 理论解释和关键决策

异步索引把用户请求和耗时工作解耦。worker 领取 job 后依次完成读取、解析、OCR、结构化切分、embedding 和 Milvus upsert。任务需要有 status、attempts、error_message、created_at、updated_at 等状态，旧版本任务不能覆盖新版本结果。

Parent/child 是检索粒度与生成上下文的折中：child 负责精确召回和 rerank，parent 保留更完整的段落、标题或页上下文。扫描 PDF 没有文本层时，当前 worker 使用 Tesseract OCR；图片文件可按当前用户 vision model 解析为可检索 Markdown。

### 源码入口

阅读 [vector index worker](../../backend/app/workers/vector_index_worker.py)、[document service](../../backend/app/services/documents/document_service.py)、[vector index service](../../backend/app/services/vectors/vector_index_service.py) 和 [OCR engine](../../backend/app/services/documents/pdf_ocr_engine.py)。

### 可复制命令

查看任务、OCR 和 chunk 相关代码：

```bash
rg -n "vector_index_jobs|attempts|parent|child|Tesseract|OCR" backend/app/services backend/app/workers backend/app/db/sql
conda run -n firstrag python scripts/eval_pdf_ocr.py
```

### 预期结果与观察点

文本文件应跳过不必要的 OCR；扫描 PDF 应在 worker 日志中出现 OCR 阶段；索引完成后，Milvus entity 同时具备 child text 和 parent text。OCR 评测报告应说明 suite、环境、质量和耗时边界，不把合成 fixture 结果当成真实业务文档结论。

### 三层练习

- 基础练习：使用教程 fixture 完成一次索引，记录 job 的状态转换。
- 诊断练习：构造一个 OCR 失败或 Provider 超时场景，确认任务失败可见且 assistant/job 不会伪装成成功。
- 扩展练习：比较小 child、大 parent 与固定窗口切分对引用完整性的影响，保持 embedding 参数不变。

## 第五章：向量写入与 Milvus v3 entity

### 理论解释和关键决策

当前系统的向量写入不是“把所有文本塞进 PostgreSQL”。PostgreSQL 保存关系 metadata 和 job 状态；Milvus v3 entity 保存检索所需的 dense/sparse vectors、child text、parent text 以及 user_id、file_id、index_version 和定位字段。

Dense embedding 来自登录用户保存的 embedding provider；sparse embedding 由 Compose 内固定 revision 的 BGE-M3 service 生成。两路编码可以独立失败和缓存，但写入时必须绑定同一用户、文件和索引版本。

### 源码入口

阅读 [Milvus vector store](../../backend/app/services/vectors/milvus_vector_store.py)、[embedding model](../../backend/app/services/vectors/embedding_model.py)、[sparse encoder client](../../backend/app/services/sparse_encoder_client.py) 和 [sparse encoder service](../../backend/sparse_encoder/)。

### 可复制命令

检查 sparse encoder 和 collection 相关配置：

```bash
rg -n "MILVUS|BGE-M3|collection|dense|sparse|parent_content|index_version" backend docker-compose.yml .env.example
docker compose ps sparse-encoder milvus-standalone
```

### 预期结果与观察点

Milvus collection identity 应与当前 revision 和 schema 一致；entity 中应能区分 dense vector、sparse vector、child_content、parent_content 和过滤字段。换 embedding provider 或 dimensions 后，应重新索引受影响文件，不应把新旧向量混在同一索引版本中。

### 三层练习

- 基础练习：从一条索引日志定位 collection、file_id 和 index_version。
- 诊断练习：解释为什么只检查“embedding 数量”不足以证明 sparse、parent text 和 metadata 都正确。
- 扩展练习：设计 provider/model/dimensions 变化时的 migration 与 re-index 清单。

## 第六章：检索链路——dense/sparse、RRF、rerank 和 parent context

### 理论解释和关键决策

提问时，dense query 和 sparse query 使用相同的 user/file scalar filter，各自发出 ANN 请求，然后由 RRF 融合 child 候选。RRF 可用下式理解：

```text
RRF(d) = Σ 1 / (k + rank_i(d))
```

融合后由 child reranker 精排，最后批量取得对应 parent context。dense 失败时可降级为 sparse-only，sparse 失败时可降级为 dense-only；降级不能扩大过滤范围，也不能回退到 PostgreSQL keyword search。

### 源码入口

阅读 [retrieval service](../../backend/app/services/retrieval/)、[reranker](../../backend/app/services/retrieval/reranker.py) 和 [hybrid 检索教程](HYBRID_RETRIEVAL_AND_STREAMING.md)。

### 可复制命令

```bash
rg -n "AnnSearchRequest|RRFRanker|rerank|parent_content|user_id|file_id" backend/app/services/retrieval backend/app/services
```

### 预期结果与观察点

retrieval diagnostics 应能说明 dense、sparse、融合、rerank 和最终 parent context 的候选数量与降级信息。相同问题在不同用户下不能跨租户命中；同一用户切换知识库时，file filter 应随请求变化。

### 三层练习

- 基础练习：对一个 fixture 问一个精确术语问题，再问一个语义改写问题，比较两路召回。
- 诊断练习：人为让 sparse encoder 不可用，确认 dense-only 仍遵守 user/file filter，并在 diagnostics 标出降级。
- 扩展练习：建立 10 条 query，比较只用 dense、hybrid、hybrid+rerank 的引用命中情况。

## 第七章：LCEL、上下文与 SSE 流式回答

### 理论解释和关键决策

Retrieval 负责找证据，generation 负责基于证据回答。LCEL 把 query、retrieved context、prompt 和 LLM 组织成可组合链路；SSE 让 token、sources、usage、retrieval diagnostics 和最终状态按事件返回。Next.js proxy 必须透传 streaming body，不能先读完整响应，否则用户看不到实时输出。

assistant message 应在流开始时进入持久化状态，正常结束写入 completed；异常则写入 failed 和 error_message，同时保留可诊断的 retrieval 信息。

### 源码入口

阅读 [chat route](../../backend/app/api/chat.py)、[RAG service](../../backend/app/services/rag_service.py)、[RAG streaming](../../backend/app/services/rag/streaming.py) 和 [chat proxy](../../frontend/src/app/api/chat/route.ts)。

### 可复制命令

```bash
rg -n "text/event-stream|X-Accel-Buffering|sources|retrieval|failed|assistant" backend/app frontend/src
curl -N -sS http://localhost:3000/api/chat \
  -H "Authorization: Bearer ${FIRSTRAG_TUTORIAL_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"<conversation-id>","knowledge_base_id":"<knowledge-base-id>","message":"请总结文档中的关键事实"}'
```

### 预期结果与观察点

响应应是连续 SSE event，而不是等待完整 JSON；前端消息最终包含回答、sources 和 retrieval diagnostics。断开连接或 Provider 报错时，数据库中的 assistant message 应可区分 failed，而不是显示为成功空答案。

### 三层练习

- 基础练习：在浏览器网络面板观察 token、sources 和完成事件。
- 诊断练习：模拟上游超时，沿 backend 日志、proxy 响应和 messages 表定位失败点。
- 扩展练习：增加一个不改变协议的 diagnostics 字段，并为前端和后端各写一个回归用例。

## 第八章：接入自己的 Provider 与真实评测

### 理论解释和关键决策

Provider 配置应按“先小后全”的顺序接入：

1. 先配置聊天模型，验证最小回答。
2. 再配置 embedding，重新索引一份小文档。
3. 再开启远程或本地 rerank，比较引用质量。
4. 最后用固定 golden set 评测并记录环境、模型、dimensions、topK 和失败样本。

Recall@K 只能回答“目标文档是否进入候选”，不能单独证明答案正确；还应观察 source hit、引用完整性、首 token 延迟、失败率和 diagnostics。没有真实登录用户和 Provider 的结果，不能宣称完成真实 RAG 验收。

### 源码入口

阅读 [用户设置 API](../../backend/app/api/user_settings.py)、[LLM provider service](../../backend/app/services/llm_service.py)、[embedding model](../../backend/app/services/vectors/embedding_model.py) 和 [评测说明](../evals/README.md)。

### 可复制命令

先查看评测命令和参数，再在已启动 Compose 的真实用户环境运行：

```bash
conda run -n firstrag python scripts/eval_indexing.py --help
conda run -n firstrag python scripts/eval_rag.py --help
conda run -n firstrag python scripts/eval_pdf_ocr.py
```

### 预期结果与观察点

评测报告应记录输入 fixture 或 golden set、Provider、model、dimensions、collection identity、索引版本和样本失败原因。仅凭 stub 通过不能推出真实 Provider 的质量；仅凭单次成功问答也不能推出稳定 Recall@K。

### 三层练习

- 基础练习：配置一个自己的聊天和 embedding provider，索引一份小 Markdown。
- 诊断练习：故意让 embedding dimensions 与 collection schema 不匹配，观察错误如何暴露并恢复。
- 扩展练习：建立 20 条领域 query 的 golden set，比较 Provider、chunk、topK 和 rerank 组合。

## 第九章：安全设计与多租户边界

### 理论解释和关键决策

RAG 的安全边界不是“模型回答得像不像”，而是“用户能否看到不属于自己的证据”。所有资源查询必须带 user_id；软删除资源必须过滤 deleted_at；资源不存在与不属于当前用户都应避免泄露存在性。

用户 API Key 只能在输入后提交给后端，后端使用加密存储；不要写入 localStorage、URL、日志或错误上报。Provider base URL 需要 SSRF 防护；公开部署需要登录保护、请求体和文件大小限制、并发/频率限制、SSE 超时、日志脱敏和安全 header。

### 源码入口

阅读 [认证与安全模块](../../backend/app/core/)、[限流 module](../../backend/app/core/rate_limit.py)、[用户设置 route](../../backend/app/api/user_settings.py) 和 [安全教程](FRONTEND_SECURITY_TESTING_AND_DEPLOYMENT.md)。

### 可复制命令

```bash
rg -n "get_current_user_id|user_id|deleted_at|secret|rate.limit|SSRF|Authorization" backend/app frontend/src docs/DEPLOYMENT.md
docker compose config --quiet
```

### 预期结果与观察点

安全检查应能回答四个问题：谁能读这个 file_id，Key 保存在哪里，外部 URL 是否能访问内网，流式接口如何限速和超时。日志中不应出现完整 API Key、JWT 或数据库密码。

### 三层练习

- 基础练习：审阅一个文件、会话和消息查询，标出 user_id 与 deleted_at 条件。
- 诊断练习：设计跨用户 file_id、恶意 provider URL 和超大上传三个测试用例。
- 扩展练习：为公网部署补充反向代理安全 header、审计事件和告警阈值。

## 第十章：单台 VPS + Docker Compose 上线

### 理论解释和关键决策

默认上线目标是 Ubuntu/Debian 单台 VPS：Nginx 负责 TLS、域名、静态/代理入口和 SSE 缓冲策略，Compose 负责应用进程和内部依赖，数据通过 named volumes 或明确目录持久化。最低资源应结合 embedding、Milvus 和并发决定；可先按 4 vCPU、8 GiB RAM、足够 SSD 作为起点，再用真实负载修正。

生产部署必须固定域名、HTTPS、secret、备份位置和回滚版本。不要把 PostgreSQL、Redis、Milvus、etcd、MinIO 或 sparse encoder 直接暴露到公网。

### 源码入口

阅读 [生产部署文档](../DEPLOYMENT.md)、[Docker startup runbook](../docker-startup/README.md)、[Nginx shared config](../../deploy/nginx/00-firstrag-shared.conf)、[proxy locations](../../deploy/nginx/firstrag-proxy-locations.inc) 和 [public TLS example](../../deploy/nginx/firstrag-public-demo.tls.conf.example)。

### 可复制命令

在 VPS 的项目目录执行，真实 secret 只填入服务器上的 .env：

```bash
mkdir -p /srv/firstrag/uploads /srv/firstrag/models /srv/firstrag/backups
cp .env.example .env
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
docker compose logs --tail=100 redis postgres milvus-etcd milvus-minio milvus-standalone milvus-health-probe sparse-encoder migrate backend worker frontend
```

配置域名后，按 [部署文档](../DEPLOYMENT.md) 的 Nginx 模板生成站点配置，执行 Nginx 配置检查并申请证书。SSE location 必须关闭 proxy buffering，并保留 no-cache 和长连接相关设置。

上线前的应用级前置检查：

```bash
conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method compose --check-runtime-health
```

### 预期结果与观察点

公网只开放 80/443；首页、登录、上传、索引、提问和 SSE 均可用。smoke test 应记录域名、证书、响应头、首 token、sources、失败恢复和资源使用，而不是只截图首页。

### 三层练习

- 基础练习：在本地按生产拓扑启动一次，并验证 Nginx 到 frontend/backend 的路径。
- 诊断练习：分别排查 502、SSE 一直缓冲、证书失败和 Milvus 未就绪。
- 扩展练习：为域名增加健康检查、访问日志采样、告警和受限管理员入口。

## 第十一章：备份、恢复、升级与回滚

### 理论解释和关键决策

可恢复性至少覆盖三类数据：

| 数据 | 作用 | 备份重点 |
| --- | --- | --- |
| PostgreSQL | 用户、metadata、jobs、messages、settings | 逻辑 dump、加密和定期恢复演练 |
| uploads | 原始文件和待处理输入 | 增量/全量备份，并与 metadata 配对 |
| Milvus 相关 volumes | 向量、索引、etcd/MinIO 状态 | 按部署文档冻结服务后备份，记录 collection identity |

恢复顺序通常是基础依赖、PostgreSQL、uploads、Milvus，再启动 worker 和 backend 做一致性检查。升级前固定 Git commit、镜像 digest、migration 版本和备份；回滚要明确应用版本与数据 schema 是否兼容，不能只切换 frontend 镜像。

### 源码入口

阅读 [备份恢复与回滚章节](../DEPLOYMENT.md)、[Compose volumes](../../docker-compose.yml) 和 [production preflight](../../scripts/production_preflight.py)。

### 可复制命令

下面是检查当前服务和卷的起点；具体 dump、恢复和停机窗口按部署环境执行：

```bash
docker compose ps
docker volume ls
docker compose config --quiet
git rev-parse HEAD
docker compose logs --tail=100 migrate milvus-health-probe backend worker
```

### 预期结果与观察点

每份备份都应能回答“来自哪一版本、哪个 collection identity、哪一时间点、是否恢复过”。恢复后必须重新登录、读取文件 metadata、检查 Milvus entity 数量、执行一条检索和一条 SSE 问答。

### 三层练习

- 基础练习：写一页自己的备份清单，包含 PostgreSQL、uploads 和 Milvus 三类数据。
- 诊断练习：模拟只恢复 PostgreSQL 不恢复 Milvus，解释为什么 metadata 可能存在但检索仍失败。
- 扩展练习：做一次 staging 恢复演练，记录 RTO、RPO、缺失数据和回滚决策。

## 第十二章：综合项目——替换成自己的知识库

### 理论解释和关键决策

毕业项目不是把文件上传成功，而是证明一条可解释、可恢复、可上线的闭环。选择一个你有权限使用的领域，例如公司制度、课程资料、产品手册或公开法规，建立固定版本的文档集和 golden set。

### 源码入口

综合回查 [源码地图](CODE_MAP.md)、[API 文档](../API.md)、[schema 文档](../SCHEMAS.md)、[RAG 工作流](../RAG_WORKFLOW.md) 和 [部署文档](../DEPLOYMENT.md)。

### 可复制命令

```bash
python3 scripts/check_tutorial_docs.py
git diff --check
docker compose ps
```

### 预期结果与观察点

提交毕业验收时，至少附上：

- 文档集版本、来源和权限说明。
- Provider、model、embedding dimensions、collection identity 和 index version。
- golden set、Recall@K、source 命中、失败样本和 diagnostics。
- 一次跨用户隔离验证、一次 Provider 失败恢复和一次备份恢复演练。
- VPS 域名、HTTPS、SSE、限流、日志脱敏和回滚记录。

### 三层练习

- 基础练习：替换成自己的 5 份文档，完成上传、索引、提问和引用检查。
- 诊断练习：为一个回答错误建立从 query、召回、rerank、parent context 到 prompt 的证据链。
- 扩展练习：把 golden set 接入 CI 或定期评测，并为质量下降设置人工复核门槛。

## 基础练习

完成以下最短闭环：

1. 阅读第一章，画出当前真实链路。
2. 运行第二章 credential-free E2E。
3. 上传教程 fixture，观察异步 job 和 Milvus entity。
4. 提问并记录回答、sources、retrieval diagnostics。
5. 运行文档检查和 diff 检查。

## 诊断练习

从一个失败现象开始，不直接修改参数：

- 服务启动失败：先看 Compose dependency、migrate 和 health probe。
- 没有引用：区分没有索引、过滤为空、dense/sparse 降级、rerank 过滤和 provider 失败。
- SSE 不流式：检查 Nginx buffering、proxy body 透传、响应头和上游超时。
- 跨用户命中：沿 route、repository、Milvus filter 和缓存 key 检查 user_id。
- 恢复后检索失败：对照 PostgreSQL、uploads、Milvus volumes 和 collection identity。

每次诊断都要保存现象、日志、最小复现命令、根因和验证结果。

## 扩展练习

选择一个方向深入：

- 改造 chunk 或 parent 策略，并用固定 golden set 比较，不同时改变 Provider 和 topK。
- 增加 retrieval feedback，观察 source 命中与回答反馈的关系。
- 为一个 Provider 增加超时、重试、熔断和成本指标。
- 将备份恢复、smoke test 和评测报告纳入上线 checklist。
- 为源码地图中的一个模块补充测试或可观察性，而不复制出第二套 RAG。

## 验证命令与继续阅读

从仓库根目录运行：

```bash
python3 scripts/check_tutorial_docs.py
git diff --check
```

继续阅读：

- [教程导航](README.md)
- [RAG 核心流程](../RAG_WORKFLOW.md)
- [API 文档](../API.md)
- [部署与恢复](../DEPLOYMENT.md)
- [评测说明](../evals/README.md)

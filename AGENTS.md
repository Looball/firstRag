# FirstRAG Agent 协作规范

本文面向 Codex、Claude Code、Copilot Agent 等 AI Agent。正文使用中文，专业术语和工程名词保留 English。

## 当前阶段

- FirstRAG 已进入“功能冻结、教程优先”阶段。默认不增加非必要产品功能，也不为缩短文件继续拆分职责清晰的模块。
- `main` 是唯一长期主线；修改从最新 `main` 创建短期 `codex/...` 分支，经 PR 和 required checks 合并回 `main`。不维护长期 `tutorial` 分支。
- Bug、安全漏洞、依赖兼容和教程可复现性所需的最小修复仍正常维护。
- 教程和示例必须引用当前真实实现、API、schema 和运行行为，不创建与生产链路长期并行的教学实现。产品快照由 `product-v1.0.0` tag 固定。

## 通用原则

- 先读代码、文档、测试和 Git 状态，再修改；优先复用现有模块、helper、repository 和 service。
- 只处理当前任务，避免 unrelated refactor；保留用户已有的未提交改动。
- 不读取或打印 `~/.zshrc`、shell history、SSH private key、完整 `.env` 等敏感内容。
- 根目录 `.env` 仅作为运行时配置来源；不得打印、复制或提交 API Key、JWT、数据库密码、私钥和完整用户凭据。
- 涉及用户数据时必须检查 `user_id`、权限隔离和软删除条件。

## 代码分层

| 目录 | 约束 |
| --- | --- |
| `backend/app/api/` | FastAPI route：参数校验、认证、权限检查和 HTTP 错误转换；不写业务 SQL。 |
| `backend/app/schemas/` | Pydantic request/response model。 |
| `backend/app/services/` | 业务编排、RAG、provider 调用和 indexing；接收基本类型，不接收 FastAPI Request/Response。 |
| `backend/app/repositories/` | 只做数据访问；SQL 通过 `backend/app/db/executor.py` 的 `fetch_all`、`fetch_one`、`execute` 执行。 |
| `backend/app/db/` | 数据库连接、migration、advisory lock 和 SQL。 |
| `backend/app/workers/` | 异步任务 worker。 |
| `backend/sparse_encoder/` | 内网固定 revision BGE-M3 sparse encoder、contract 和 probe。 |
| `frontend/src/app/` | Next.js App Router 页面和 layout。 |
| `frontend/src/components/`、`frontend/src/lib/` | 可复用 UI、auth、API 和 utility。 |
| `frontend/src/app/api/` | 只做代理、header 转发、错误适配和 streaming 透传。 |

## Backend、Frontend 和 API 约定

- 认证统一使用 `Depends(get_current_user_id)` 注入 `user_id`；资源不存在或不属于当前用户时返回 `404`。
- 后端配置从 monorepo 根目录 `.env` 读取；入口为 `backend/app/main.py`，兼容入口为 `backend/main.py`。
- 前端认证请求携带 `Authorization: Bearer <access_token>`；动态 route handler 显式声明 `params` 类型。
- SSE chat proxy 必须保持 streaming body，不得提前读完整响应。响应使用 `text/event-stream`，保留 `Cache-Control: no-cache` 和 `X-Accel-Buffering: no`。
- 用户输入的 API Key 只能提交给后端，不得写入 `localStorage`、`sessionStorage`、URL、日志或错误上报。
- 常用 HTTP 语义：认证失败 `401`，资源不存在 `404`，参数错误 `400`，文件过大 `413`，provider/依赖故障可返回 `502`。

## RAG 与 indexing 约定

- 文件上传只负责落盘、metadata 持久化和 enqueue；重型 parsing、chunk、embedding 和 vector write 必须由 `vector_index_jobs` / `vector_index_worker` 异步完成。
- 同一文件 indexing 使用 PostgreSQL advisory lock 或版本号保护；删除、重建和失败补偿必须同时处理 Milvus entities 与 active jobs。
- Milvus 是唯一受支持的 vector store。PostgreSQL 保存关系型 metadata、任务和审计信息，不保存或检索 parent/child 正文，也不承担关键词召回。
- dense query 使用用户配置的 embedding provider；sparse query 使用固定 revision BGE-M3。Milvus dense/sparse request 必须使用相同的 `user_id` / `file_id` filter，并由 `RRFRanker` 融合 child。
- 每个 parent 限制 child 候选数，先对 child 做 Cross-Encoder rerank，再使用 Milvus entity 的 parent text 构建 context；sources 保留实际命中的 child 和位置。
- dense 或 sparse 单路失败时只能按明确策略降级为另一通道，不得放宽 filter 或回退到 PostgreSQL keyword retrieval；必须保留 diagnostics。
- dense cache identity 包含用户、provider、model 和 dimensions；sparse cache identity 包含 BGE-M3 model、revision、max length 和 query hash，不保存 query 明文。
- LLM streaming 期间持久化 assistant message；失败时写入 `failed` 和 `error_message`。回答的 `sources` 与 retrieval diagnostics 保存到 `messages.sources`、`messages.retrieval`。

## Database 约定

- `backend/app/db/sql/000_initial_schema.sql` 是空库初始化基线；新增表、字段、索引或约束必须新增三位递增 migration，例如 `001_create_message_tags.sql`。
- SQL 参数使用 `%s`，禁止拼接用户输入；涉及用户数据的查询必须带 `user_id`，软删除表必须过滤 `deleted_at IS NULL`。
- 任务表应明确 `status`、`attempts`、`error_message`、`created_at`、`updated_at` 等状态字段。
- 不提交包含 `ALTER TABLE ... OWNER TO ...` 等个人数据库角色绑定的导出语句；不假定数据库被手动修改。
- 修改数据库结构时同步更新 repository、schema、`docs/SCHEMAS.md` 和必要测试。

## 文档与编码

- 文档应描述真实现状，不把计划能力写成已实现能力；架构、API、schema、RAG 或部署变化须同步更新 `docs/`。
- Agent 协作规则同步维护 `docs/AGENT_GUIDE.md` 与本文件；详细专题放在 `docs/backend/` 等目录。
- 类、函数和方法保留 docstring；关键业务逻辑用中文注释说明意图，避免无意义注释。
- Python 优先使用类型注解；TypeScript 避免隐式 `any`；错误信息简洁、安全、可理解；日志不得包含完整 secret。

## Git 工作流

1. 修改前运行 `git status --short`，确认当前分支和已有改动。
2. 从最新 `main` 创建短期 `codex/...` 分支；PR review 修复提交到对应 PR 分支。
3. 只暂存当前任务相关文件，不覆盖或回滚用户改动。
4. 提交前运行 `git diff --cached --check`，使用简洁明确的 commit message。
5. 默认只提交本地；除非用户明确要求，不 push、不开启 force push。

禁止使用以下破坏性命令，除非用户明确、具体要求：`git reset --hard`、`git clean -fd`、`git checkout -- .`。禁止删除 `uploads/`、数据库数据、Milvus volumes、`vector_db/` 或模型缓存，除非用户确认确切范围和影响。

## 验证要求

- 默认验证以 Docker Compose 为准：

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 redis postgres milvus-etcd milvus-minio milvus-standalone milvus-health-probe sparse-encoder migrate backend worker frontend
```

- 涉及数据库、部署、RAG、上传、向量化或认证时，补充运行 `conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method compose --check-runtime-health`，并对受影响链路做 health、登录、上传、indexing、chat、sources smoke test。
- `scripts/acceptance_check.sh` 是补充验收入口；没有 Docker 或只做静态检查时才使用相应 skip 参数，并在最终报告中说明范围。
- 修改 PDF OCR engine、预处理、候选策略、语言包或 Tesseract runtime 时，运行：

```bash
conda run -n firstrag python scripts/eval_pdf_ocr.py
```

必要时同时传入 `--history-dir docs/evals/ocr_runs --trend-report docs/evals/latest_pdf_ocr_trend.md`，并在 Compose backend 容器内复跑。
- Docker、依赖、数据库、服务或外部 API Key 不可用时，不得把未运行的检查写成通过，必须在最终回复中说明原因。

## 常用入口与参考文档

- 完整应用：`docker compose up -d --build`，默认前端 `http://localhost:3000`。
- 后端专项调试：`cd backend && conda activate firstrag && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`。
- 新增 API：schema → repository → service → route → `docs/API.md` / tests。
- 修改 RAG：先读 `docs/RAG_WORKFLOW.md`，重点检查 `backend/app/services/rag_service.py` 和 `backend/app/services/retrieval/`。
- 优先参考：`README.md`、`docs/ARCHITECTURE.md`、`docs/API.md`、`docs/SCHEMAS.md`、`docs/RAG_WORKFLOW.md`、`docs/DEPLOYMENT.md`、`docs/AGENT_GUIDE.md`、`docs/TASKS.md`。

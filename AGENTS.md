# AGENTS.md

本文档面向 Codex、Claude Code、Copilot Agent 等 AI Agent，说明在 FirstRAG 仓库中协作、修改代码、补充文档和处理 Git 的规则。正文使用中文，专业术语和工程名词保留英文。

## 1. Project Overview

FirstRAG 是一个全栈 RAG（Retrieval-Augmented Generation）应用，采用 monorepo 结构组织前端、后端、文档和部署配置。

核心能力：

- 用户注册、登录和 JWT 认证。
- 知识库、知识文件、会话和消息管理。
- 文件上传、SHA-256 去重、异步 vector index job。
- 文档解析、chunk 切分、embedding、Chroma 向量入库。
- PostgreSQL 全文检索、Chroma vector search、RRF 融合、CrossEncoder rerank。
- OpenAI-compatible LLM 流式回答，并通过 SSE 返回 token、sources 和 retrieval diagnostics。
- 用户可配置自己的 LLM provider、model 和 API Key。
- 用户可配置自己的 embedding provider（千问/Qwen 或智谱/ZhipuAI）、model 和 API Key。
- rerank 支持本地 BGE Cross-Encoder 和远程 Qwen rerank API 两种 provider。

核心数据流：

```text
用户上传文件
  -> frontend API proxy
  -> FastAPI route
  -> 文件落盘 + PostgreSQL metadata
  -> vector_index_jobs
  -> vector_index_worker
  -> document_service 解析/切分
  -> Chroma vector store + PostgreSQL full-text chunks
  -> embedding 使用用户配置的 provider（千问/ZhipuAI）

用户提问
  -> frontend API proxy
  -> FastAPI /chat
  -> rag_service 构建 LCEL chain
  -> hybrid retrieval（用户 embedding 向量召回 + 全文检索 + RRF + rerank）
  -> LLM streaming
  -> SSE 返回回答、sources、retrieval diagnostics
```

## 2. Development Principles

- 先阅读现有代码和文档，再修改实现。
- 优先复用已有模块、helper、repository 和 service，不随意引入新抽象。
- 保持分层边界清晰：route 不写业务逻辑，repository 不写业务判断，service 不接收 HTTP 对象。
- 任何涉及用户数据的逻辑必须优先考虑权限隔离和软删除条件。
- 修改行为前确认影响面，避免把 unrelated refactor 混进当前任务。
- 不访问 `~/.zshrc`、全局 shell 配置或其他可能包含 API Key 的敏感文件。
- 根目录 `.env` 是运行时配置来源，不打印、不提交、不复制其中的敏感值。

## 3. Repository Structure

```text
FirstRAG/
├── frontend/                 # Next.js / React frontend
├── backend/                  # FastAPI backend
├── docs/                     # 项目文档
├── deploy/                   # 部署相关
│   ├── docker/
│   └── nginx/
├── scripts/                  # 初始化、迁移、测试脚本
├── .env.example              # 环境变量模板
├── docker-compose.yml        # Docker Compose 配置
├── README.md
└── .gitignore
```

后端关键目录：

| 目录 | 职责 |
| --- | --- |
| `backend/app/api/` | FastAPI route，参数校验、认证、权限检查、HTTP error。 |
| `backend/app/schemas/` | Pydantic request/response model。 |
| `backend/app/services/` | 业务逻辑、RAG chain、LLM 调用、embedding/rerank provider、vector indexing。 |
| `backend/app/repositories/` | 数据访问层，纯 SQL 查询。 |
| `backend/app/db/` | 数据库连接、executor、migration SQL、advisory lock。 |
| `backend/app/core/` | config、security、secret cipher。 |
| `backend/app/workers/` | background worker。 |
| `backend/tests/` | 后端测试。 |

前端关键目录：

| 目录 | 职责 |
| --- | --- |
| `frontend/src/app/` | Next.js App Router 页面和 layout。 |
| `frontend/src/app/api/` | Next.js API proxy。 |
| `frontend/src/components/` | 可复用 UI component。 |
| `frontend/src/lib/` | 前端 utility、auth 和 settings helper。 |

## 4. Backend Conventions

- 后端运行目录为 `backend/`，但配置读取 monorepo 根目录 `.env`。
- FastAPI app 入口为 `backend/app/main.py`，兼容入口为 `backend/main.py`。
- route 文件使用 `APIRouter` 注册，按业务域拆分。
- 认证统一通过 `Depends(get_current_user_id)` 注入 `user_id`。
- 权限校验在 route 层完成，例如知识库、文件、会话是否属于当前用户。
- route 层只调用 repository 做权限查询，不直接写 SQL。
- service 函数接收基本类型参数，例如 `user_id`、`file_id`、`conversation_id`。
- service 层负责复杂业务流程，例如 RAG chain、hybrid retrieval、LLM streaming、vector indexing。
- 外部 API 调用在 service 层封装，包括 LLM provider、embedding provider 和 rerank provider。
- LLM 与 embedding provider 由登录用户在设置页保存 provider/model/API Key；rerank provider 仍通过 `backend/app/core/config.py` 的环境变量选择，默认本地 BGE Cross-Encoder。
- repository 文件按业务域拆分，所有查询通过 `backend/app/db/executor.py` 的 `fetch_all`、`fetch_one`、`execute`。

## 5. Frontend Conventions

- 前端使用 Next.js App Router。
- 页面逻辑放在 `frontend/src/app/`，可复用 UI 放在 `frontend/src/components/`。
- API Route 只做代理、header 转发、错误适配和 streaming 透传，不实现后端业务逻辑。
- 前端请求后端默认通过 `BACKEND_ORIGIN` 和 `BACKEND_API_PREFIX` 配置。
- 所有需要认证的请求必须携带 `Authorization: Bearer <access_token>`。
- SSE chat proxy 必须保持 streaming body，不要把流式响应提前读完整再返回。
- 用户 API Key 只允许在用户输入后提交给后端，不写入 `localStorage`、`sessionStorage`、URL、日志或错误上报。
- 动态 route handler 显式声明 `params` 类型，避免未定义的 `RouteContext`。

## 6. RAG Pipeline Rules

- 文件上传只负责落盘、metadata 持久化和可选 enqueue，不在 HTTP request 中做重型 indexing。
- vector indexing 必须通过 `vector_index_jobs` 和 `vector_index_worker` 异步执行。
- indexing 使用的 embedding 来自用户保存的 provider（千问/ZhipuAI），而非系统级环境变量。
- 同一文件 indexing 需要使用 PostgreSQL advisory lock 或版本号保护，避免旧任务覆盖新结果。
- 删除向量化结果时必须同时处理 Chroma entries、PostgreSQL chunks 和 active jobs。
- RAG retrieval 需要尽量保留 diagnostics，便于前端展示和后续评估。
- hybrid retrieval 的顺序和职责：
  - vector retriever 使用用户配置的 embedding provider 从 Chroma 召回。
  - full-text retriever 从 PostgreSQL 召回。
  - RRF 融合多路结果。
  - reranker 精排：默认本地 BGE Cross-Encoder，可通过 `RERANK_PROVIDER=qwen` 切到阿里云 Qwen rerank API。
- query embedding 按用户、provider、model 和 dimensions 缓存，避免每次查询重新计算。
- LLM streaming 过程中要持久化 assistant message 状态，失败时写入 `failed` 和 `error_message`。
- 回答 sources 和 retrieval diagnostics 应保存到 `messages.sources` 与 `messages.retrieval`。

## 7. Database Rules

- PostgreSQL 存储关系型数据，Chroma 存储向量数据。
- 数据库 SQL 位于 `backend/app/db/sql/`。
- `000_initial_schema.sql` 是当前空库初始化基线；后续新增表、字段、索引或约束从 `001_xxx.sql` 开始新增 migration SQL，不直接假定数据库已手动修改。
- migration 文件按三位编号递增命名，例如 `001_create_message_tags.sql`。
- 不提交本地数据库导出的 `ALTER TABLE ... OWNER TO ...` 这类绑定个人角色的语句。
- SQL 参数使用 `%s` 占位符，禁止拼接用户输入。
- 涉及用户数据的查询必须带 `user_id` 条件。
- 软删除表查询必须过滤 `deleted_at IS NULL`。
- 多表关联时同时检查 `user_id` 和软删除条件。
- 任务型表需要明确 status、attempts、error_message、created_at、updated_at 等状态字段。
- 不确定表结构时优先查看 `backend/app/db/sql/`，必要时再使用 `pg_dump` 查看实际数据库。

核心表：

| 表 | 用途 |
| --- | --- |
| `users` | 用户账户。 |
| `knowledge_bases` | 知识库。 |
| `knowledge_files` | 知识文件 metadata。 |
| `knowledge_base_files` | 知识库与文件关联。 |
| `knowledge_file_chunks` | 文本 chunk 和 full-text search 数据。 |
| `conversations` | 会话。 |
| `messages` | 消息、sources、retrieval diagnostics。 |
| `vector_index_jobs` | 向量化任务队列。 |
| `user_llm_settings` | 用户当前 LLM 设置。 |
| `user_llm_provider_credentials` | 用户按 provider 保存的加密 API Key。 |
| `user_embedding_settings` | 用户当前 embedding/向量模型设置（provider、model、加密 API Key）。 |

## 8. API Rules

- 成功响应统一包含 `success: true`，除历史兼容接口外尽量保持一致。
- 认证失败返回 `401`。
- 资源不存在或不属于当前用户时返回 `404`，避免泄露资源存在性。
- 参数错误返回 `400`。
- 文件过大返回 `413`。
- 后端服务依赖或外部 provider 调用失败时，可返回 `502` 并给出用户可理解的 `detail`。
- ID 参数使用 UUID，由 FastAPI 自动校验。
- 文件上传使用 `multipart/form-data` 和 `UploadFile`。
- Chat 接口使用 `text/event-stream`，响应头保留 `Cache-Control: no-cache` 和 `X-Accel-Buffering: no`。
- 路径约定：
  - auth：`/register`、`/login`
  - chat：`/chat`
  - knowledge base：`/chat/knowledge-base(s)/...`
  - knowledge file：`/chat/knowledge-files/...`
  - vector index：`/chat/knowledge-files/{id}/vectors`、`/chat/vector-index-jobs/{id}`
  - conversations：`/chat/knowledge-bases/{id}/conversations/...`
  - user settings：`/user/settings/...`
  - user embedding settings：`/user/settings/embedding`、`/user/settings/embedding-providers`、`/user/settings/embedding/test`

## 9. Documentation Rules

- 项目级文档放在 `docs/` 顶层。
- 业务专题或历史材料可放在 `docs/backend/` 等子目录。
- 修改架构、API、数据表、RAG 流程、启动方式时，同步更新相关文档。
- 文档正文使用中文，专业术语和名词保留英文。
- 文档应说明真实现状，不写尚未实现的能力为既有能力。
- 长文档优先使用表格、流程图和代码块提高可读性。
- Agent 相关协作规范同步维护 `docs/AGENT_GUIDE.md` 与本文件。

## 10. Coding Standards

- 保持现有代码风格一致。
- 所有类、函数、方法必须有 docstring。
- 关键业务逻辑使用中文注释说明意图。
- 避免无意义注释，例如“给变量赋值”。
- Python 代码优先使用类型注解。
- TypeScript 代码避免隐式 `any` 扩散。
- 错误信息面向用户时应简洁、安全、可理解。
- 内部日志可以保留详细异常，但不得输出完整 API Key、JWT、数据库密码等敏感值。
- 不引入和任务无关的大规模格式化或重构。

## 11. Git Workflow

修改项目文件后：

1. 运行 `git status --short`。
2. 只暂存当前任务相关文件。
3. 不包含 unrelated existing changes。
4. 使用清晰、简洁的 commit message。
5. 提交后在最终回复中报告 commit hash。

注意：

- 可能存在用户未提交改动，禁止擅自 revert。
- 大型改动优先在独立分支完成。
- PR review 修复应提交到对应 PR 分支。
- 不使用 `git reset --hard`、`git checkout --`、`git clean` 等破坏性命令，除非用户明确要求。
- 删除分支前确认内容已合并或最终文件内容一致。

## 12. Testing Requirements

- 后端测试优先在 `backend/` 下运行。
- Python 环境使用 conda，当前环境名为 `firstrag`。
- 轻量语法检查：

```bash
cd backend
conda activate firstrag
python -m compileall app
```

- 后端测试：

```bash
cd backend
conda activate firstrag
python -m pytest tests
```

- 前端检查：

```bash
cd frontend
npm install
npm run lint
npm run build
```

- 如果依赖缺失、服务不可用或外部 API Key 不可用，应在最终回复中明确说明未运行的检查和原因。

## 13. Common Tasks

### 启动后端

```bash
cd backend
conda activate firstrag
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 启动前端

```bash
cd frontend
npm install
npm run dev
```

### 启动 vector index worker

```bash
cd backend
conda activate firstrag
python -m app.workers.vector_index_worker
```

### 新增 API

1. 在 `backend/app/schemas/` 定义 request model。
2. 在 `backend/app/repositories/` 增加 SQL 查询。
3. 在 `backend/app/services/` 编排业务逻辑。
4. 在 `backend/app/api/` 增加 route 和权限检查。
5. 更新 `docs/API.md` 和必要测试。

### 新增数据库字段

1. 新增 `backend/app/db/sql/NNN_description.sql`。
2. 更新 repository 查询和序列化逻辑。
3. 更新 `docs/SCHEMAS.md`。
4. 增加或更新测试。

### 修改 RAG 行为

1. 阅读 `docs/RAG_WORKFLOW.md`。
2. 定位 `backend/app/services/rag_service.py` 和 `backend/app/services/retrieval/`。
3. 保留或更新 retrieval diagnostics。
4. 更新 `docs/RAG_WORKFLOW.md`。

## 14. Documents Reference

优先阅读：

- `README.md`：项目首页和快速开始。
- `docs/README.md`：文档目录说明。
- `docs/ARCHITECTURE.md`：系统架构。
- `docs/API.md`：API 接口。
- `docs/SCHEMAS.md`：数据结构。
- `docs/RAG_WORKFLOW.md`：RAG 流程。
- `docs/FRONTEND.md`：前端说明。
- `docs/BACKEND.md`：后端说明。
- `docs/DEPLOYMENT.md`：部署和启动。
- `docs/AGENT_GUIDE.md`：Agent 协作规范。
- `docs/CODING_STYLE.md`：编码规范。

专项资料：

- `docs/backend/frontend_llm_settings_protocol.md`：前端设置页与后端 LLM settings 协议。
- `docs/backend/user_settings_api.md`：用户模型设置 API 细节。
- `docs/backend/development_design.md`：早期 RAG demo 设计与审查记录。

## 15. Forbidden Operations

禁止执行以下操作，除非用户明确、具体地要求：

- 读取、打印或复制 `~/.zshrc`、shell history、SSH private key、完整 `.env` 等敏感内容。
- 提交 API Key、JWT、数据库密码、私钥或完整用户凭据。
- 使用 `git reset --hard`、`git clean -fd`、`git checkout -- .` 等破坏性命令。
- force push 到共享分支。
- 覆盖或删除用户未提交改动。
- 将前端原始完整 API Key 保存到浏览器持久化存储。
- 绕过 route 层权限检查直接暴露用户数据。
- 在 repository 层拼接用户输入生成 SQL。
- 把长耗时向量化任务放在 HTTP request 中同步执行。
- 删除 `uploads/`、`vector_db/`、数据库数据或模型缓存，除非用户明确要求并确认影响。

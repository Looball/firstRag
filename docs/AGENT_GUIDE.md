# AI Agent 协作规范

本文面向 Codex、Claude Code 等 AI Agent，说明在 FirstRAG 中协作时的边界和优先级。

## 工作原则

- 先读代码再改代码，优先复用现有分层和工具函数。
- 不访问 `~/.zshrc` 等全局敏感配置。
- 根目录 `.env` 含运行配置，不提交、不打印敏感值。
- 修改项目文件后按仓库规范运行 `git status --short`，只暂存当前任务相关文件。
- 不删除或覆盖用户未明确要求处理的本地改动。

## 分层约束

- `backend/app/api/`：只做参数校验、认证、权限检查和 HTTP 错误转换。
- `backend/app/services/`：编排业务流程，不接收 FastAPI Request/Response。
- `backend/app/repositories/`：只写 SQL 查询，所有用户数据查询必须带 `user_id`。
- `backend/app/db/`：所有 SQL 通过 `fetch_all`、`fetch_one`、`execute` 执行。
- `frontend/src/app/api/`：只做代理和浏览器请求适配，不写后端业务逻辑。

## 常见任务入口

| 任务 | 优先阅读 |
| --- | --- |
| 聊天/RAG 问题 | `docs/RAG_WORKFLOW.md`, `backend/app/services/rag_service.py` |
| 文件上传/向量化 | `backend/app/api/knowledge_files.py`, `backend/app/services/vectors/` |
| 会话和消息 | `backend/app/api/conversations.py`, `backend/app/repositories/message_repository.py` |
| 模型设置 | `docs/backend/frontend_llm_settings_protocol.md`, `backend/app/services/user_settings_service.py` |
| 前端页面 | `docs/FRONTEND.md`, `frontend/src/app/page.tsx` |

## Git 约定

- 大改先建分支，分支名前缀优先使用 `codex/`，若本地命名空间冲突可使用 `codex-*`。
- commit message 简短描述本次任务。
- 不使用 `git reset --hard`、`git checkout --` 等破坏性命令，除非用户明确要求。
- PR review 修复应提交到 PR 分支，让 PR 自动更新。

## 验收约定

- 默认先运行 `docker compose up -d --build`，再检查 `docker compose ps` 和 Redis、PostgreSQL、Chroma、migration、backend、worker、frontend 日志。
- 涉及部署、RAG、上传或向量化时，运行 `scripts/production_preflight.py --check-runtime-health`，确认独立 Chroma server 的配置、Compose 拓扑和容器健康状态。
- `scripts/acceptance_check.sh` 默认执行 infrastructure preflight；只有无 Docker、明确只做纯静态检查时才使用 `--skip-infrastructure-check`。

## 文档约定

新增架构、接口、数据结构或流程变更时，同步更新 `docs/` 对应文档。专项细节可以放到 `docs/backend/`，顶层文档保持导航清晰。

## 数据库约定

- `backend/app/db/sql/000_initial_schema.sql` 是当前空库初始化基线。
- 后续新增表、字段、索引或约束时，从 `001_xxx.sql` 开始新增增量 migration。
- migration 文件名使用三位递增编号和英文描述，例如 `001_create_message_tags.sql`。
- 不提交本地数据库导出的 `ALTER TABLE ... OWNER TO ...` 这类绑定个人角色的语句。

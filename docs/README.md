# FirstRAG 文档目录

本目录面向学习者、开发者和 AI Agent，记录 FirstRAG 的架构、接口、数据结构、研发规范与部署约定。项目已进入“功能冻结、教程优先”的维护阶段；当前文档仍以 reference、runbook 和 evaluation 为主，教程入口、源码地图与分层学习路线将在 `PLAN-20260802-01` 的后续任务中补齐。

## 当前维护边界

- `main` 是唯一长期主线，不维护并行的长期 `tutorial` 分支。
- 非必要产品功能和纯粹按行数进行的拆分暂停；Bug、安全、兼容性和教程可复现性修复继续维护。
- 教程内容必须指向当前真实实现，reference 文档继续作为 API、schema、架构和运行行为的事实来源。
- 教程化前的完整产品快照使用 `product-v1.0.0` tag 固定。

在专门的教程导航交付前，建议先阅读 `ARCHITECTURE.md` 和 `RAG_WORKFLOW.md`，再根据关注方向进入前端、后端、API、schema 或部署文档。

## 文档索引

| 文档 | 说明 |
| --- | --- |
| `ARCHITECTURE.md` | 系统架构、模块边界、数据流。 |
| `SCHEMAS.md` | PostgreSQL 表、Pydantic Schema、核心数据结构。 |
| `API.md` | 后端 FastAPI 接口与前端代理接口。 |
| `RAG_WORKFLOW.md` | 文件向量化、混合检索、流式回答流程。 |
| `FRONTEND.md` | Next.js 前端目录、页面、代理层和状态约定。 |
| `BACKEND.md` | FastAPI 后端分层、服务和 worker 说明。 |
| `DEPLOYMENT.md` | 本地启动、环境变量、部署目录约定。 |
| `docker-startup/README.md` | Docker Compose 本地完整链路启动 runbook。 |
| `AGENT_GUIDE.md` | AI Agent / Codex / Claude Code 协作规范。 |
| `CODING_STYLE.md` | 代码风格、提交和测试约定。 |
| `TASKS.md` | 长期任务台账、计划批次、优先级、状态和验收标准。 |
| `evals/README.md` | RAG 真实链路评测集和一键评测脚本说明。 |

## 附录资料

`docs/backend/` 保留历史设计、数据库关系图 PPT 和专项协议文档：

- `development_design.md`：早期 RAG demo 审查与开发计划。
- `frontend_llm_settings_protocol.md`：前端设置页与后端模型设置协议。
- `user_settings_api.md`：用户模型设置接口细节。
- `PostgreSQL六表关系示意图*.pptx`：数据库关系图材料。

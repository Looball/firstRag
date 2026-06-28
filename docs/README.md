# FirstRAG 文档目录

本目录面向开发者和 AI Agent，记录 FirstRAG 的架构、接口、数据结构、研发规范与部署约定。阅读顺序建议从 `ARCHITECTURE.md` 开始，再根据任务进入前端、后端或 RAG 流程文档。

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
| `AGENT_GUIDE.md` | AI Agent / Codex / Claude Code 协作规范。 |
| `CODING_STYLE.md` | 代码风格、提交和测试约定。 |
| `TASKS.md` | 后续任务台账、优先级、状态和验收标准。 |
| `evals/README.md` | RAG 真实链路评测集和一键评测脚本说明。 |

## 附录资料

`docs/backend/` 保留历史设计、数据库关系图 PPT 和专项协议文档：

- `development_design.md`：早期 RAG demo 审查与开发计划。
- `frontend_llm_settings_protocol.md`：前端设置页与后端模型设置协议。
- `user_settings_api.md`：用户模型设置接口细节。
- `PostgreSQL六表关系示意图*.pptx`：数据库关系图材料。

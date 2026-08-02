# FirstRAG 文档目录

本目录面向学习者、开发者和 AI Agent，记录 FirstRAG 的教程、架构、接口、数据结构、研发规范与部署约定。项目已进入“功能冻结、教程优先”的维护阶段；教程负责引导学习和实验，reference、runbook 与 evaluation 继续记录当前工程事实。

## 当前维护边界

- `main` 是唯一长期主线，不维护并行的长期 `tutorial` 分支。
- 非必要产品功能和纯粹按行数进行的拆分暂停；Bug、安全、兼容性和教程可复现性修复继续维护。
- 教程内容必须指向当前真实实现，reference 文档继续作为 API、schema、架构和运行行为的事实来源。
- 教程化前的完整产品快照使用 `product-v1.0.0` tag 固定。

## Tutorial

| 文档 | 说明 |
| --- | --- |
| [`tutorials/README.md`](tutorials/README.md) | 10 分钟导览、四条学习路线、专题交付状态和统一章节模板。 |
| [`tutorials/CREDENTIAL_FREE_QUICKSTART.md`](tutorials/CREDENTIAL_FREE_QUICKSTART.md) | 无真实账号、API Key 或公网模型服务的隔离全栈入门实验。 |
| [`tutorials/FILE_INGESTION_AND_INDEXING.md`](tutorials/FILE_INGESTION_AND_INDEXING.md) | 文件从 HTTP upload 到异步任务、OCR、chunk、Chroma 与 PostgreSQL 的可追踪教程。 |
| [`tutorials/HYBRID_RETRIEVAL_AND_STREAMING.md`](tutorials/HYBRID_RETRIEVAL_AND_STREAMING.md) | 一次提问从 hybrid retrieval、RRF、rerank 到 SSE、落库与 diagnostics 的教程。 |
| [`tutorials/FRONTEND_SECURITY_TESTING_AND_DEPLOYMENT.md`](tutorials/FRONTEND_SECURITY_TESTING_AND_DEPLOYMENT.md) | 前端状态与 proxy、凭据安全、测试门禁、Compose 和生产部署边界教程。 |
| [`tutorials/CODE_MAP.md`](tutorials/CODE_MAP.md) | route、repository、service、worker、前端、测试和部署的纵向源码地图。 |

教程专题尚未全部完成。未交付章节只在导航中标记对应任务，不创建空白页面；状态以 `TASKS.md` 为准。

## Reference

| 文档 | 说明 |
| --- | --- |
| `ARCHITECTURE.md` | 系统架构、模块边界、数据流。 |
| `SCHEMAS.md` | PostgreSQL 表、Pydantic Schema、核心数据结构。 |
| `API.md` | 后端 FastAPI 接口与前端代理接口。 |
| `RAG_WORKFLOW.md` | 文件向量化、混合检索、流式回答流程。 |
| `FRONTEND.md` | Next.js 前端目录、页面、代理层和状态约定。 |
| `BACKEND.md` | FastAPI 后端分层、服务和 worker 说明。 |

## Runbook 与 Evaluation

| 文档 | 说明 |
| --- | --- |
| [`DEPLOYMENT.md`](DEPLOYMENT.md) | 本地工作流、CI、生产安全、备份恢复和在线 demo 前置条件。 |
| [`docker-startup/README.md`](docker-startup/README.md) | Docker Compose 完整链路启动与故障排查 runbook。 |
| [`evals/README.md`](evals/README.md) | RAG、indexing、OCR 评测条件、命令、报告和指标边界。 |

## 协作与任务

| 文档 | 说明 |
| --- | --- |
| [`AGENT_GUIDE.md`](AGENT_GUIDE.md) | AI Agent / Codex / Claude Code 协作规范。 |
| [`CODING_STYLE.md`](CODING_STYLE.md) | 代码风格、提交和测试约定。 |
| [`TASKS.md`](TASKS.md) | 长期任务台账、计划批次、优先级、状态和验收标准。 |

## Historical material

`docs/backend/` 保留历史设计、数据库关系图 PPT 和专项协议文档：

- `development_design.md`：早期 RAG demo 审查与开发计划。
- `frontend_llm_settings_protocol.md`：前端设置页与后端模型设置协议。
- `user_settings_api.md`：用户模型设置接口细节。
- `PostgreSQL六表关系示意图*.pptx`：数据库关系图材料。

# FirstRAG

## 项目介绍

FirstRAG 是一个全栈 RAG（Retrieval-Augmented Generation，检索增强生成）应用，用于构建本地知识库问答系统。项目支持用户注册登录、知识库管理、文件上传、异步向量化、混合检索、模型设置、聊天图片附件和流式回答。

当前仓库采用 monorepo 结构：

- `frontend/`：Next.js / React 前端。
- `backend/`：FastAPI 后端。
- `docs/`：项目架构、接口、数据结构和协作规范文档。

核心流程：

```text
上传文件 -> 解析切分 -> 向量化入库 -> 混合检索 -> LLM 流式回答 -> 展示来源与诊断
```

## 项目截图

以下截图基于当前前端 UI 和脱敏演示数据生成，不包含真实 API Key、JWT、数据库密码或私人文档内容。

### 聊天工作台与高级观察入口

![FirstRAG 聊天工作台与质量看板](docs/assets/firstrag-workspace-dashboard.png)

工作台默认以普通模式展示知识库选择、会话列表、RAG 回答和引用来源。切换到高级模式后，可继续查看诊断、引用反馈、回答反馈、质量看板和检索参数；质量看板用于观察最近窗口内的负反馈、无关引用、平均 sources 和首 token 延迟。

### 知识库文件与任务队列

![FirstRAG 知识库文件与任务队列](docs/assets/firstrag-files-queue.png)

文件管理弹窗用于上传知识文件、复用已上传文件、触发单文件或整个知识库向量化，并查看 vector index worker 的队列状态、失败原因和恢复提示。

### 模型设置

![FirstRAG 模型设置](docs/assets/firstrag-model-settings.png)

模型设置页支持用户按聊天、向量和 rerank 厂商保存自己的 API Key。用户 Key 只在保存或测试时提交给后端，页面只展示脱敏保存状态，不回显完整密钥。

## 最短演示路径

本地最小演示默认使用 Docker Compose，在仓库根目录构建并启动完整链路：

```bash
docker compose up -d --build
```

compose 会先运行 `migrate` service 初始化或升级 PostgreSQL schema，再启动 FastAPI 后端、Next.js 前端和 worker。启动后查看服务状态和关键日志：

```bash
docker compose ps
docker compose logs --tail=100 migrate backend worker frontend postgres
```

完整准备流程见 [`docs/docker-startup/README.md`](docs/docker-startup/README.md)。本地单独启动 FastAPI、Next.js 或 worker 仅作为专项调试方式，不再是默认验证路径。

打开 `http://localhost:3000` 后，推荐试用顺序：

1. 注册并登录一个本地测试账号。
2. 进入“聊天模型设置”，填写自己的 OpenAI-compatible provider。
3. 回到工作台，新建知识库并上传一份 `.md`、`.txt`、`.pdf` 或 `.docx` 文件。
4. 在“文件”弹窗中触发向量化，等待任务队列完成。
5. 对当前知识库提问，检查回答和引用来源；如果当前聊天模型支持 vision，也可以在聊天框附加 PNG、JPEG 或 WebP 图片进行单轮多模态提问。
6. 如需调试检索效果，切换到高级模式后查看 retrieval diagnostics、提交反馈或打开质量看板。

Docker 中的 `backend`、`migrate` 和 `worker` 复用精简后的 Python runtime 镜像；worker 不单独安装 `torch`、`transformers` 等可选 rerank 依赖。

## 技术栈

| 模块 | 技术 |
| --- | --- |
| 前端 | Next.js, React, TypeScript |
| 后端 | FastAPI, Pydantic |
| 数据库 | PostgreSQL |
| 向量库 | Chroma |
| RAG 编排 | LangChain / LCEL |
| 检索 | 向量检索、PostgreSQL 全文检索、RRF、可选本地 CrossEncoder 或用户级远程 rerank |
| 模型接口 | OpenAI 兼容协议，支持 DeepSeek、Qwen、Zhipu、Kimi、Doubao、Minimax 等 |
| 任务处理 | PostgreSQL 队列 + 独立 vector index worker |

## 快速开始

### 1. 准备环境

后端 Python 环境使用 conda，当前项目环境名为 `firstrag`。

```bash
conda activate firstrag
```

复制环境变量模板，并按需填写数据库、JWT 和用户凭据加密密钥。聊天模型、向量模型和远程 rerank 的 provider、model、API Key 都在用户登录后的“模型设置”页保存，不再从 `.env` 读取；Docker 和后端无需这些 provider Key 也能启动。

```bash
cp .env.example .env
```

后端运行时会读取仓库根目录的 `.env`。

首次登录后，请先进入“模型设置”配置聊天模型和向量模型；如需远程 rerank，也在同页配置。未配置前可以登录和上传文件，但聊天模型调用与向量化会提示补充配置。

启动完整本地环境：

```bash
docker compose up -d --build
```

Compose 会启动 PostgreSQL、migration、FastAPI 后端、Next.js 前端和 worker，并挂载 `uploads/`、`vector_db/` 和 `models/`。查看状态：

```bash
docker compose ps
docker compose logs --tail=100 migrate backend worker frontend postgres
```

默认访问：

```text
http://localhost:3000
```

### 2. 可选：本地调试 FastAPI

```bash
cd backend
conda activate firstrag
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

本地单独启动后端只用于专项排查；常规验证请使用 Docker Compose。

### 3. 可选：本地调试 Next.js

```bash
cd frontend
npm install
npm run dev
```

本地单独启动前端只用于页面专项调试；常规验证请使用 Docker Compose。

### 4. 可选：本地调试向量化 Worker

```bash
cd backend
conda activate firstrag
python -m app.workers.vector_index_worker
```

本地单独启动 worker 只用于专项排查；常规验证请使用 Docker Compose。更多细节见 `docs/DEPLOYMENT.md`。

## 项目结构

```text
FirstRAG/
├── frontend/                 # Next.js / React 前端
├── backend/                  # FastAPI 后端
├── docs/                     # 项目文档
├── deploy/                   # 部署相关
│   ├── docker/
│   └── nginx/
├── scripts/                  # 初始化、迁移、测试脚本
├── .env.example              # 环境变量模板
├── docker-compose.yml        # 本地 Docker Compose 配置
├── README.md
└── .gitignore
```

## 文档导航

| 文档 | 说明 |
| --- | --- |
| `docs/README.md` | 文档目录说明。 |
| `docs/ARCHITECTURE.md` | 系统架构和数据流。 |
| `docs/SCHEMAS.md` | 数据库表、Pydantic Schema 和核心结构。 |
| `docs/API.md` | 后端 API 与前端代理说明。 |
| `docs/RAG_WORKFLOW.md` | RAG 入库、检索和生成流程。 |
| `docs/FRONTEND.md` | 前端目录和开发约定。 |
| `docs/BACKEND.md` | 后端分层和服务说明。 |
| `docs/DEPLOYMENT.md` | 本地启动和部署约定。 |
| `docs/AGENT_GUIDE.md` | AI Agent / Codex / Claude Code 协作规范。 |
| `docs/CODING_STYLE.md` | 编码规范。 |

## Roadmap

- [x] 补充完整 Docker Compose 部署配置。
- [x] 增加前后端 CI 检查。
- [x] 完善数据库迁移执行脚本。
- [x] 补充项目截图和本地演示说明。
- [x] 增加 RAG 评估集、批量评估脚本和历史趋势摘要。
- [x] 明确在线演示环境方案与上线阻塞项。
- [x] 建立生产部署安全、备份恢复和持久化 preflight。
- [ ] 发布在线演示环境（待真实服务器、域名/TLS、生产 `.env`、受控演示账号和公网 smoke test 落地）。

## License

当前仓库暂不开放开源授权，详见 [LICENSE](./LICENSE)。代码可用于项目展示、学习和审查；未经版权持有人书面许可，不授予复制、修改、分发、再授权、商业使用或作为服务托管的权利。

后续如项目所有者确定采用 MIT、Apache-2.0、GPL 等开源协议，应替换 `LICENSE` 文件并同步更新本段说明。

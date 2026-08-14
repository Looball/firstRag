# FirstRAG 教程导航

本目录把 FirstRAG 的真实实现组织成可选择的学习路径。教程不维护一套简化版 RAG，也不复制容易失效的大段源码；每个主题都从架构位置、源码入口、可运行验证和故障观察点出发，再链接到 reference 文档。

## 当前可用内容

| 内容 | 用途 |
| --- | --- |
| 本页 | 选择学习路线，了解章节顺序和统一写法。 |
| [无外部密钥入门实验](CREDENTIAL_FREE_QUICKSTART.md) | 在隔离 Compose project 中运行注册、上传、向量化、检索、SSE 和 sources 完整链路。 |
| [文件入库与异步索引](FILE_INGESTION_AND_INDEXING.md) | 从一个 `file_id` 追踪权限、去重、任务队列、worker、OCR、chunk，以及 PostgreSQL metadata/job 与 Milvus child/parent text/vector。 |
| [混合检索与流式回答](HYBRID_RETRIEVAL_AND_STREAMING.md) | 从一次提问追踪两路粗召回、RRF、rerank、SSE、持久化与 diagnostics。 |
| [前端、安全、测试与部署进阶](FRONTEND_SECURITY_TESTING_AND_DEPLOYMENT.md) | 追踪页面状态、API proxy、凭据、限流、测试门禁、Compose 与生产 preflight。 |
| [教程示例素材](fixtures/README.md) | 使用可追溯的 TXT、Markdown 和现场生成 OCR 素材完成练习。 |
| [源码地图](CODE_MAP.md) | 从业务问题定位 route、repository、service、worker、前端和测试入口。 |
| [系统架构](../ARCHITECTURE.md) | 查看模块边界、核心数据流和存储职责。 |
| [RAG 核心流程](../RAG_WORKFLOW.md) | 查看入库、检索、生成与 diagnostics 的当前行为。 |

专题实验、完整章节、练习门禁和授权边界已按 [PLAN-20260802-01](../archive/TASKS_HISTORY.md#t-123-建立教程入口学习路线与源码地图) 全部交付。

## 10 分钟导览

1. 用 2 分钟阅读 [系统架构的核心数据流](../ARCHITECTURE.md#核心数据流)，先建立“上传”和“提问”两条主链路。
2. 用 3 分钟打开 [源码地图](CODE_MAP.md)，找到 FastAPI app、Next.js 工作台、vector worker 和 Compose 入口。
3. 用 5 分钟从下面选择一条路线，阅读其“第一步”和“第二步”；不需要先读完全部 reference 文档。

## 路线一：快速入门

| 项目 | 内容 |
| --- | --- |
| 适合读者 | 第一次接触 RAG，或只想先理解 FirstRAG 如何运行。 |
| 先修条件 | 能使用 Git、Docker 和命令行；不要求先掌握 LangChain。 |
| 预计产出 | 能画出上传与提问两条流程，知道 PostgreSQL、Redis、Milvus、worker 各自负责什么。 |
| 第一步 | 阅读 [系统架构](../ARCHITECTURE.md) 和 [源码地图的全局入口](CODE_MAP.md#全局入口)。 |
| 第二步 | 完成 [无外部密钥入门实验](CREDENTIAL_FREE_QUICKSTART.md)，观察真实全栈链路。 |
| 第三步 | 需要连接真实 provider 时，再按 [Docker Compose 启动 runbook](../docker-startup/README.md) 运行完整应用。 |
| 可以跳过 | API 字段全集、数据库 migration 细节、前端 hook 拆分和 OCR 参数选优。 |

无密钥实验使用隔离 provider stub 验证工程链路；运行完整应用仍需要用户配置自己的聊天与 embedding provider。两种路径的差异见[实验说明](CREDENTIAL_FREE_QUICKSTART.md#与真实-provider-路径的差异)。

## 路线二：后端与 RAG

| 项目 | 内容 |
| --- | --- |
| 适合读者 | 希望掌握 FastAPI 分层、异步 indexing、hybrid retrieval 和 SSE 的后端开发者。 |
| 先修条件 | Python、HTTP、SQL 基础；了解 embedding 和向量相似度更佳。 |
| 预计产出 | 能从 file ID 追踪到 job/chunk/vector，也能从一次提问追踪到 RRF、rerank、sources 和 diagnostics。 |
| 第一步 | 阅读 [RAG 核心流程](../RAG_WORKFLOW.md) 和 [后端结构](../BACKEND.md)。 |
| 第二步 | 完成 [文件入库与异步索引](FILE_INGESTION_AND_INDEXING.md)，从 `file_id` 追踪到 job、chunk 和 Milvus entity。 |
| 第三步 | 完成[混合检索与流式回答](HYBRID_RETRIEVAL_AND_STREAMING.md)，从一次提问追踪到 RRF、SSE 与消息落库。 |
| 可以跳过 | 前端视觉组件、公开 demo 部署和 OCR 校对 UI；需要时再回查。 |

入库章节已由 [T-125](../archive/TASKS_HISTORY.md#t-125-编写文件入库与异步索引教程) 交付；混合检索与流式回答章节已由 [T-126](../archive/TASKS_HISTORY.md#t-126-编写混合检索与流式回答教程) 交付。

## 路线三：前端

| 项目 | 内容 |
| --- | --- |
| 适合读者 | 希望理解 Next.js App Router、API proxy、React hooks 和 SSE 状态回写的前端开发者。 |
| 先修条件 | TypeScript、React hooks 和浏览器 Fetch API 基础。 |
| 预计产出 | 能从 `page.tsx` 定位 UI、状态 hook 和代理 route，解释 token、sources、diagnostics 如何进入消息界面。 |
| 第一步 | 阅读 [前端结构](../FRONTEND.md) 和 [API 约定](../API.md)。 |
| 第二步 | 沿 [前端工作台与 API proxy 源码地图](CODE_MAP.md#前端工作台与-api-proxy) 跟踪请求和状态。 |
| 第三步 | 完成[前端、安全、测试与部署进阶](FRONTEND_SECURITY_TESTING_AND_DEPLOYMENT.md)，再从现有 Vitest 与 Playwright 用例中选择一个交互做回归验证。 |
| 可以跳过 | OCR engine 内部算法、PostgreSQL migration 和远程 provider 实现。 |

前端、安全边界和测试策略的进阶章节已由 [T-127](../archive/TASKS_HISTORY.md#t-127-编写前端安全测试与部署进阶教程) 交付。

## 路线四：工程化

| 项目 | 内容 |
| --- | --- |
| 适合读者 | 关注 Docker Compose、migration、CI、安全审计、评测和生产检查的工程开发者。 |
| 先修条件 | Docker、GitHub Actions 和基础 Linux/网络知识。 |
| 预计产出 | 能解释 Compose services 的启动关系，选择正确的测试门禁，并区分本地验证、真实 RAG eval 与生产 preflight。 |
| 第一步 | 阅读 [部署与本地工作流](../DEPLOYMENT.md) 和 [评测说明](../evals/README.md)。 |
| 第二步 | 沿 [测试、评测与部署源码地图](CODE_MAP.md#测试评测与部署) 查看脚本和 workflow。 |
| 第三步 | 完成[前端、安全、测试与部署进阶](FRONTEND_SECURITY_TESTING_AND_DEPLOYMENT.md)，运行与改动范围匹配的最小验证，再由 PR required checks 完成全量门禁。 |
| 可以跳过 | React 组件细节和 OCR 校对交互；除非变更影响对应链路。 |

工程化进阶章节已由 [T-127](../archive/TASKS_HISTORY.md#t-127-编写前端安全测试与部署进阶教程) 交付，练习素材和文档自动校验由 [T-128](../archive/TASKS_HISTORY.md#t-128-增加练习示例素材与文档回归门禁) 交付。

## 专题交付顺序

| 任务 | 内容 | 当前状态 |
| --- | --- | --- |
| T-123 | 教程入口、四条学习路线、源码地图 | Done |
| T-124 | 无真实 API Key 的隔离入门实验 | Done |
| T-125 | [文件上传、任务队列、worker、解析/OCR、chunk 与向量写入](FILE_INGESTION_AND_INDEXING.md) | Done |
| T-126 | [Milvus dense/sparse hybrid、RRF、rerank、SSE、sources 与 diagnostics](HYBRID_RETRIEVAL_AND_STREAMING.md) | Done |
| T-127 | [前端、安全、测试、CI 与部署](FRONTEND_SECURITY_TESTING_AND_DEPLOYMENT.md) | Done |
| T-128 | [分级练习、示例素材与文档回归门禁](#教程文档回归门禁) | Done |
| T-129 | [License 与公开使用边界](#license-与公开使用边界) | Done |

任务状态以 [docs/TASKS.md](../TASKS.md) 为准。

## 统一章节模板

后续专题使用同一结构，便于读者比较，也便于代码变化后维护：

```text
1. 学习目标与先修条件
2. 这一步在完整架构中的位置
3. 请求、数据或状态的时序
4. 真实源码入口与关键边界
5. 可重复的动手实验
6. 预期结果与观察点
7. 常见故障与诊断方法
8. 基础/诊断/扩展练习
9. Reference 文档与验证命令
```

章节中的命令必须说明运行目录、外部依赖和是否需要真实账号/API Key；结果必须来自当前实现或可复现报告，不能把计划能力、历史数据或熟悉但未计算的指标当成当前结论。

## 教程文档回归门禁

[`tutorial_manifest.json`](tutorial_manifest.json) 以机器可读方式声明核心章节、三级练习和合成素材来源。维护教程后从仓库根目录运行：

```bash
python3 scripts/check_tutorial_docs.py
```

检查器只校验可稳定判断的事实：

- 教程相对链接和 heading anchor 存在。
- Markdown link 与 inline code 中明确写出的 repo-root 源码路径存在。
- shell block 已闭合、使用 `docker compose`，且引用的仓库脚本/文件存在。
- 四个核心章节均在教程索引中，并包含 manifest 声明的基础、诊断和扩展练习。
- fixture 存在且来源字段为仓库自编合成内容。
- 教程和 fixture 不包含 private key、可用 Key 或 JWT 的高置信度模式。
- `.github/workflows/ci.yml` 继续执行同一检查命令。

失败信息包含文件、行号和失效目标。例如删除源码地图引用的文件，会得到 `链接目标不存在`，而不是笼统的“文档失败”。检查器不对自然语言段落做全文快照，也不访问网络。

## License 与公开使用边界

FirstRAG 的项目代码、教程文档和 [`fixtures/`](fixtures/README.md) 中的仓库自编合成素材采用 [Apache License 2.0](../../LICENSE)，版权归属见 [NOTICE](../../NOTICE)。在遵守许可证条款的前提下，读者可以 clone、运行、修改、分发、再授权、商业使用或将项目作为服务托管。

分发原始版本或衍生作品时，需要附带许可证、保留适用的版权与归属声明，并对修改过的文件作出显著说明。Apache-2.0 不授予 FirstRAG 名称或标识的商标使用权，项目按“原样”提供且不附带保证。

以下内容不因仓库采用 Apache-2.0 而被重新授权：

- `package-lock.json`、Python requirements 和容器镜像中声明的第三方依赖；它们继续适用各自许可证。
- LLM、embedding、rerank provider 及其他外部服务；它们继续适用各自服务条款。
- 用户上传的文件、API Key、数据库内容、日志和其他运行时数据；这些内容不属于仓库发行物。

## 阅读约定

- `tutorial` 负责解释“为什么、从哪里开始、如何验证”。
- `reference` 负责记录当前 API、schema、架构和配置事实。
- `runbook` 负责给出可重复执行的启动、部署和故障恢复步骤。
- `evaluation` 负责描述评测条件、报告字段与指标边界。
- 历史材料只用于理解演进过程，不覆盖当前 reference。

遇到文档与代码不一致时，以当前受测试保护的实现为准，并在同一任务中修正文档。

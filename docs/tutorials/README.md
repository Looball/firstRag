# FirstRAG 教程导航

本目录把 FirstRAG 的真实实现组织成可选择的学习路径。教程不维护一套简化版 RAG，也不复制容易失效的大段源码；每个主题都从架构位置、源码入口、可运行验证和故障观察点出发，再链接到 reference 文档。

## 当前可用内容

| 内容 | 用途 |
| --- | --- |
| 本页 | 选择学习路线，了解章节顺序和统一写法。 |
| [无外部密钥入门实验](CREDENTIAL_FREE_QUICKSTART.md) | 在隔离 Compose project 中运行注册、上传、向量化、检索、SSE 和 sources 完整链路。 |
| [源码地图](CODE_MAP.md) | 从业务问题定位 route、repository、service、worker、前端和测试入口。 |
| [系统架构](../ARCHITECTURE.md) | 查看模块边界、核心数据流和存储职责。 |
| [RAG 核心流程](../RAG_WORKFLOW.md) | 查看入库、检索、生成与 diagnostics 的当前行为。 |

专题实验与完整章节会按 [PLAN-20260802-01](../TASKS.md#t-123-建立教程入口学习路线与源码地图) 逐项交付。未完成的任务只在下方标记状态，不创建空白章节或失效链接。

## 10 分钟导览

1. 用 2 分钟阅读 [系统架构的核心数据流](../ARCHITECTURE.md#核心数据流)，先建立“上传”和“提问”两条主链路。
2. 用 3 分钟打开 [源码地图](CODE_MAP.md)，找到 FastAPI app、Next.js 工作台、vector worker 和 Compose 入口。
3. 用 5 分钟从下面选择一条路线，阅读其“第一步”和“第二步”；不需要先读完全部 reference 文档。

## 路线一：快速入门

| 项目 | 内容 |
| --- | --- |
| 适合读者 | 第一次接触 RAG，或只想先理解 FirstRAG 如何运行。 |
| 先修条件 | 能使用 Git、Docker 和命令行；不要求先掌握 LangChain。 |
| 预计产出 | 能画出上传与提问两条流程，知道 PostgreSQL、Redis、Chroma、worker 各自负责什么。 |
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
| 第二步 | 沿 [入库与异步索引源码地图](CODE_MAP.md#文件入库与异步索引) 跟踪调用链。 |
| 第三步 | 沿 [混合检索与流式回答源码地图](CODE_MAP.md#混合检索与流式回答) 跟踪调用链。 |
| 可以跳过 | 前端视觉组件、公开 demo 部署和 OCR 校对 UI；需要时再回查。 |

完整教学章节分别由 [T-125](../TASKS.md#t-125-编写文件入库与异步索引教程) 和 [T-126](../TASKS.md#t-126-编写混合检索与流式回答教程) 交付。

## 路线三：前端

| 项目 | 内容 |
| --- | --- |
| 适合读者 | 希望理解 Next.js App Router、API proxy、React hooks 和 SSE 状态回写的前端开发者。 |
| 先修条件 | TypeScript、React hooks 和浏览器 Fetch API 基础。 |
| 预计产出 | 能从 `page.tsx` 定位 UI、状态 hook 和代理 route，解释 token、sources、diagnostics 如何进入消息界面。 |
| 第一步 | 阅读 [前端结构](../FRONTEND.md) 和 [API 约定](../API.md)。 |
| 第二步 | 沿 [前端工作台与 API proxy 源码地图](CODE_MAP.md#前端工作台与-api-proxy) 跟踪请求和状态。 |
| 第三步 | 从现有 Vitest 与 Playwright 用例中选择一个交互做回归验证。 |
| 可以跳过 | OCR engine 内部算法、PostgreSQL migration 和远程 provider 实现。 |

前端、安全边界和测试策略的进阶章节由 [T-127](../TASKS.md#t-127-编写前端安全测试与部署进阶教程) 交付。

## 路线四：工程化

| 项目 | 内容 |
| --- | --- |
| 适合读者 | 关注 Docker Compose、migration、CI、安全审计、评测和生产检查的工程开发者。 |
| 先修条件 | Docker、GitHub Actions 和基础 Linux/网络知识。 |
| 预计产出 | 能解释七个 Compose service 的启动关系，选择正确的测试门禁，并区分本地验证、真实 RAG eval 与生产 preflight。 |
| 第一步 | 阅读 [部署与本地工作流](../DEPLOYMENT.md) 和 [评测说明](../evals/README.md)。 |
| 第二步 | 沿 [测试、评测与部署源码地图](CODE_MAP.md#测试评测与部署) 查看脚本和 workflow。 |
| 第三步 | 运行与改动范围匹配的最小验证，再由 PR required checks 完成全量门禁。 |
| 可以跳过 | React 组件细节和 OCR 校对交互；除非变更影响对应链路。 |

工程化进阶章节由 [T-127](../TASKS.md#t-127-编写前端安全测试与部署进阶教程) 交付，练习和文档自动校验由 [T-128](../TASKS.md#t-128-增加练习示例素材与文档回归门禁) 交付。

## 专题交付顺序

| 任务 | 内容 | 当前状态 |
| --- | --- | --- |
| T-123 | 教程入口、四条学习路线、源码地图 | Done |
| T-124 | 无真实 API Key 的隔离入门实验 | 当前任务 |
| T-125 | 文件上传、任务队列、worker、解析/OCR、chunk 与向量写入 | Todo |
| T-126 | vector/full-text、RRF、rerank、SSE、sources 与 diagnostics | Todo |
| T-127 | 前端、安全、测试、CI 与部署 | Todo |
| T-128 | 分级练习、示例素材与文档回归门禁 | Todo |
| T-129 | License 与公开使用边界 | Todo |

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

## 阅读约定

- `tutorial` 负责解释“为什么、从哪里开始、如何验证”。
- `reference` 负责记录当前 API、schema、架构和配置事实。
- `runbook` 负责给出可重复执行的启动、部署和故障恢复步骤。
- `evaluation` 负责描述评测条件、报告字段与指标边界。
- 历史材料只用于理解演进过程，不覆盖当前 reference。

遇到文档与代码不一致时，以当前受测试保护的实现为准，并在同一任务中修正文档。

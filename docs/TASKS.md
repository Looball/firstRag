# FirstRAG 任务管理台账

本文档用于长期追踪 FirstRAG 的开发计划、任务状态和验收记录。任何新的功能规划、技术债整理、回归修复、部署优化或文档专项，都可以作为新的计划批次追加到本文档中。

任务应按优先级推进，完成后同步更新状态、完成日期、验证命令和相关 commit。本文档只记录可执行任务，不替代详细设计文档；复杂任务可以先在对应专题文档中完成设计，再回到这里登记追踪项。

## 使用方式

1. 新增计划时，先在“计划批次”中登记计划名称、目标和日期。
2. 将计划拆成可验收的任务，追加到“任务总览”和对应任务详情中。
3. 每个任务使用唯一 ID，后续不复用已删除或已完成的 ID。
4. 开始任务时把状态改为 `Doing`；完成后改为 `Done`，补充完成日期、验证命令和相关 commit。
5. 如果一个任务变大，优先拆出新的任务 ID，不在原任务中无限追加范围。

## 状态说明

| 状态 | 说明 |
| --- | --- |
| `Todo` | 已确认要做，尚未开始。 |
| `Doing` | 正在实现或验证中。 |
| `Blocked` | 被环境、依赖、产品决策或外部服务阻塞。 |
| `Done` | 已完成实现、验证和文档更新。 |

## 优先级说明

| 优先级 | 说明 |
| --- | --- |
| `P0` | 阻塞发布、数据安全或核心链路稳定性的任务。 |
| `P1` | 明显提升可维护性、可观测性或回归稳定性的近期任务。 |
| `P2` | 重要但不阻塞当前迭代，可按节奏推进的增强任务。 |

## ID 规则

| ID 类型 | 说明 | 示例 |
| --- | --- | --- |
| `PLAN-YYYYMMDD-NN` | 一次计划、审查或专项整理的批次编号。 | `PLAN-20260628-01` |
| `T-NNN` | 具体可执行任务，跨计划递增，不复用。 | `T-009` |

新增计划时，不需要重写已有任务；只需要新增计划批次和新的 `T-NNN` 任务即可。若新计划与已有任务重叠，优先更新已有任务的来源计划、范围或验收标准。

## 当前基线

- 2026-07-21 已刷新静态回归验收：后端 311 个 pytest 用例和 30 个 subtests 通过、前端 lint 0 error（保留 2 个 `<img>` 性能 warning）、Vitest 69 个用例通过、Next 16.2.10 production build 通过。
- 2026-07-20 已完成前端依赖安全审计：Next.js 从 16.2.2 升级到 16.2.10，已消除已确认的 high findings；Babel、brace-expansion 和 js-yaml 开发依赖补丁已更新。`npm audit` 仍报告 Next 内嵌 PostCSS 的 2 个 moderate 条目，当前项目没有用户可控 CSS 进入 stringify 的运行路径，且审计器只提供降级到 Next 9.3.3 的 breaking fix，因此保留为已 triage 的不可达例外。
- 2026-07-20 已完成后端与镜像依赖安全审计：PyJWT、python-dotenv 和 python-multipart 已升级到安全补丁版本；`pip-audit` 只剩 ChromaDB 1.5.9 的 no-fix finding，由精确到版本且 2026-08-20 到期的内网不可达例外管理；Trivy 对当前 backend/frontend 镜像的可修复 high/critical OS finding 均为 0。
- 2026-07-20 已完成 GitHub Actions supply chain 固化：7 个外部 Action 引用均固定到官方 release 的 40 位 commit SHA，CI 自动拒绝 tag/branch/短 SHA 和缺失版本注释；Dependabot 每周聚合提出 Action 更新 PR。
- 2026-07-20 已完成 Chroma 跨进程索引可见性真实回归：Compose 使用独立 `chroma` service，worker 重建文件向量后 backend 无需重启即可召回 16 条 vector 结果，`vector_degraded=false`、`vector_errors=[]`，目标资料同时包含 `fulltext` 和 `vector` 来源。
- 当前默认验证路径为 `docker compose up -d --build` 后检查 `docker compose ps` 与 Redis、PostgreSQL、Chroma、migration、backend、worker、frontend 关键日志；`scripts/acceptance_check.sh` 作为补充验收脚本，静态补充检查可运行 `scripts/acceptance_check.sh --skip-real-eval`。
- 当前阶段优先做“可维护性 + 可观测性 + 验收自动化”，避免在关键链路刚稳定后继续堆叠大功能；前端工作台已开始引入 React Query 和 Zod 做请求层集中化与轻量响应校验。
- 修改项目文件后，继续遵守只暂存当前任务相关文件、不混入 unrelated refactor 的规则。

## 计划批次

| 计划 ID | 日期 | 状态 | 目标 | 关联任务 |
| --- | --- | --- | --- | --- |
| `PLAN-20260628-01` | 2026-06-28 | `Done` | 基于代码和功能审查，建立可维护性、可观测性和验收自动化方向的第一批 backlog。 | `T-001` - `T-009` |
| `PLAN-20260628-02` | 2026-06-28 | `Done` | 优化知识库检索速度，优先降低 rerank 对首 token 前等待时间的影响。 | `T-010` |
| `PLAN-20260628-03` | 2026-06-28 | `Done` | 优化 RAG 检索前置阶段，减少 knowledge profile 与文件范围查询开销。 | `T-011` |
| `PLAN-20260628-04` | 2026-06-28 | `Done` | 补强 RAG eval 性能观测，让后续检索优化有稳定报告依据。 | `T-012` |
| `PLAN-20260628-05` | 2026-06-28 | `Done` | 修正 knowledge profile cache diagnostics 在真实 RAG eval 报告中缺失的问题。 | `T-013` |
| `PLAN-20260629-01` | 2026-06-29 | `Done` | RAG 检索性能二阶段优化，继续降低首 token 前等待时间，优先处理 settings 读取、混合检索和重复查询开销。 | `T-014` - `T-018` |
| `PLAN-20260629-02` | 2026-06-29 | `Done` | 基于 `code-review-skill` 仓库级审查，整理安全边界、可维护性和测试补强的后续修改计划。 | `T-019` - `T-025` |
| `PLAN-20260630-01` | 2026-06-30 | `Done` | 建立 RAG 回答质量反馈闭环，把真实用户反馈沉淀为后续 eval 和检索优化依据。 | `T-026` - `T-029` |
| `PLAN-20260630-02` | 2026-06-30 | `Done` | 补强工程化交付闭环，优先解决数据库迁移、Docker Compose 初始化、CI 和发布前验收可运行性。 | `T-030` - `T-036` |
| `PLAN-20260701-01` | 2026-07-01 | `Done` | 发布前收口专项，优先修正文档台账状态、继续降低前端工作台复杂度，并刷新真实链路验收基线。 | `T-037` - `T-041` |
| `PLAN-20260701-02` | 2026-07-01 | `Done` | 正式生产上线补强专项，补齐部署安全、稳定性、风控、可观测性、评测质量和产品化分层。 | `T-042` - `T-047` |
| `PLAN-20260703-01` | 2026-07-03 | `Blocked` | 公开 Demo 上线试运行专项；代码侧前置项已完成，真实部署和公网验收仍等待服务器、域名、TLS 与生产配置。 | `T-048` - `T-052` |
| `PLAN-20260704-01` | 2026-07-04 | `Done` | 聊天图片能力专项；先支持聊天框图片附件和视觉模型调用，再扩展图片/OCR 入知识库。 | `T-054` - `T-055` |
| `PLAN-20260705-01` | 2026-07-05 | `Done` | Redis 基础设施专项；从进程内状态扩展为可多实例共享的缓存、限流、worker 运行态和部署健康检查。 | `T-056` - `T-061` |
| `PLAN-20260720-01` | 2026-07-20 | `Done` | 收口近期模型设置、聊天图片、RAG fixture/复验和 Chroma client-server 修复，刷新任务台账与当前验收基线。 | `T-062` |
| `PLAN-20260720-02` | 2026-07-20 | `Done` | 将独立 Chroma server 纳入 production preflight 和 acceptance check，补齐部署拓扑与运行健康门禁。 | `T-063` |
| `PLAN-20260720-03` | 2026-07-20 | `Done` | 补齐 Redis 限流的前端反馈闭环，统一透传 Retry-After 并为受限操作显示重试倒计时。 | `T-064` |
| `PLAN-20260720-04` | 2026-07-20 | `Done` | 补齐 Redis 限流命中与故障可观测性，让额度耗尽、fallback 和 fail-closed 阻断可聚合、可告警。 | `T-065` |
| `PLAN-20260720-05` | 2026-07-20 | `Done` | 将前端依赖漏洞审计固化到 CI，并为已 triage finding 建立限时例外和自动到期复查。 | `T-066` |
| `PLAN-20260720-06` | 2026-07-20 | `Done` | 将后端 Python 依赖和第一方 Docker 镜像的漏洞审计固化到 CI。 | `T-067` |
| `PLAN-20260720-07` | 2026-07-20 | `Done` | 固化 GitHub Actions 第三方依赖，使用完整 commit SHA 并由 Dependabot 持续更新。 | `T-068` |
| `PLAN-20260721-01` | 2026-07-21 | `Done` | 补齐知识库与知识文件的用户可见生命周期，支持安全删除、恢复和跨存储清理。 | `T-069` |
| `PLAN-20260721-02` | 2026-07-21 | `Done` | 增强回答引用的可核验性，支持按 chunk 查看前后文并安全打开原始文件。 | `T-070` |
| `PLAN-20260721-03` | 2026-07-21 | `Done` | 为 PDF/DOCX 引用补充可验证的位置 metadata，并增强原文定位展示。 | `T-071` |
| `PLAN-20260721-04` | 2026-07-21 | `Done` | 为无文本层的扫描 PDF 增加本地 OCR fallback，并保留页码级引用。 | `T-072` |
| `PLAN-20260721-05` | 2026-07-21 | `Done` | 记录 OCR 置信度、提示低质量页面，并支持单页异步重新识别。 | `T-073` |
| `PLAN-20260721-06` | 2026-07-21 | `Done` | 支持 OCR 页面人工校对、持久化修订和可撤销的异步索引重建。 | `T-074` |
| `PLAN-20260722-01` | 2026-07-22 | `Done` | 将 OCR 校对扩展为原始 PDF 页面、编辑文本和差异结果一体化工作台。 | `T-075` |
| `PLAN-20260722-02` | 2026-07-22 | `Done` | 建立文件级 OCR 质量巡检入口，集中发现低置信度页面并直接进入校对工作台。 | `T-076` |
| `PLAN-20260722-03` | 2026-07-22 | `Done` | 支持从 OCR 巡检中批量选择页面，以单次文件重建任务重新识别并提供进度与失败重试。 | `T-077` |
| `PLAN-20260722-04` | 2026-07-22 | `Doing` | 持久化页级 OCR 识别历史，展示置信度趋势和相邻识别文本差异。 | `T-078` |

## 任务总览

| ID | 来源计划 | 优先级 | 状态 | 标题 | 完成日期 | 相关 commit |
| --- | --- | --- | --- | --- | --- | --- |
| `T-001` | `PLAN-20260628-01` | `P1` | `Done` | 拆分前端聊天工作台基础类型和工具 | 2026-06-28 | `f70e0a6` |
| `T-002` | `PLAN-20260628-01` | `P1` | `Done` | 建立前端解析/状态工具测试底座 | 2026-06-28 | `48a3d53` |
| `T-003` | `PLAN-20260628-01` | `P1` | `Done` | 增加 eval 历史趋势摘要 | 2026-06-28 | `419b10d` |
| `T-004` | `PLAN-20260628-01` | `P1` | `Done` | 产品化 vector worker health 展示 | 2026-06-28 | `c61dcfa` |
| `T-005` | `PLAN-20260628-01` | `P2` | `Done` | 完善 indexing failure recovery 分类与操作闭环 | 2026-06-28 | `5bd9bfe` |
| `T-006` | `PLAN-20260628-01` | `P2` | `Done` | 扩充 RAG eval case 覆盖面 | 2026-06-28 | `9620eee` |
| `T-007` | `PLAN-20260628-01` | `P2` | `Done` | 梳理本地启动与验收工作流文档 | 2026-06-28 | `7c52ae8` |
| `T-008` | `PLAN-20260628-01` | `P2` | `Done` | 为部署目录补齐可运行 Docker Compose 方案 | 2026-06-28 | `7c52ae8` |
| `T-009` | `PLAN-20260628-01` | `P1` | `Done` | 继续拆分前端聊天工作台 UI 面板 | 2026-06-28 | `bdd53c8` |
| `T-010` | `PLAN-20260628-02` | `P1` | `Done` | 优化知识库检索速度，降低 rerank 开销 | 2026-06-28 | `8c9ac21` |
| `T-011` | `PLAN-20260628-03` | `P1` | `Done` | 增加知识库画像进程内轻量缓存 | 2026-06-28 | `9f178fc` |
| `T-012` | `PLAN-20260628-04` | `P1` | `Done` | RAG eval 报告补齐缓存与阶段耗时摘要 | 2026-06-28 | `e123014` |
| `T-013` | `PLAN-20260628-05` | `P1` | `Done` | 修正真实 RAG eval 缓存命中字段为空 | 2026-06-29 | `cf01e5b` |
| `T-014` | `PLAN-20260629-01` | `P1` | `Done` | 定位并优化 retrieval settings 阶段耗时 | 2026-06-29 | `6e3c1d7` |
| `T-015` | `PLAN-20260629-01` | `P1` | `Done` | 为知识库检索设置增加进程内轻量缓存 | 2026-06-29 | `6d1ee1a` |
| `T-016` | `PLAN-20260629-01` | `P1` | `Done` | 优化 hybrid retrieval 粗召回执行路径 | 2026-06-29 | `2477565` |
| `T-017` | `PLAN-20260629-01` | `P2` | `Done` | 增加 query embedding 进程内短 TTL 缓存 | 2026-06-29 | `cbd00d8` |
| `T-018` | `PLAN-20260629-01` | `P2` | `Done` | 固化 RAG eval 性能门槛和趋势字段 | 2026-06-29 | `7793856` |
| `T-019` | `PLAN-20260629-02` | `P1` | `Done` | 加固用户自定义 LLM Base URL SSRF 防护 | 2026-06-29 | `fd64b6d` |
| `T-020` | `PLAN-20260629-02` | `P1` | `Done` | 收紧知识文件上传类型与解析失败反馈 | 2026-06-29 | `fd64b6d` |
| `T-021` | `PLAN-20260629-02` | `P1` | `Done` | 抽取前端 API proxy 共享 helper | 2026-06-29 | `fd64b6d` |
| `T-022` | `PLAN-20260629-02` | `P1` | `Done` | 继续拆分聊天工作台请求与流式状态逻辑 | 2026-06-29 | `017526b`, `cab5f9f` |
| `T-023` | `PLAN-20260629-02` | `P2` | `Done` | 拆分 RAG service 的路由、诊断和引用序列化职责 | 2026-06-30 | `36ad4ee` |
| `T-024` | `PLAN-20260629-02` | `P2` | `Done` | 建立权限、上传和流式代理的回归测试矩阵 | 2026-06-29 | `49e0ba7` |
| `T-025` | `PLAN-20260629-02` | `P1` | `Done` | 引入 React Query 与 Zod 集中前端数据请求层 | 2026-06-29 | `986a9a3` |
| `T-026` | `PLAN-20260630-01` | `P1` | `Done` | 增加聊天回答质量反馈闭环 | 2026-06-30 | `e027079` |
| `T-027` | `PLAN-20260630-01` | `P1` | `Done` | 增强 sources 展示与引用有用性标记 | 2026-06-30 | `ce66821` |
| `T-028` | `PLAN-20260630-01` | `P2` | `Done` | 支持从真实问答沉淀 RAG eval case 草稿 | 2026-06-30 | `d523917` |
| `T-029` | `PLAN-20260630-01` | `P2` | `Done` | 增加回答质量和检索表现看板雏形 | 2026-06-30 | `aa70530` |
| `T-030` | `PLAN-20260630-02` | `P1` | `Done` | 增加数据库迁移执行脚本 | 2026-06-30 | `5d22e59` |
| `T-031` | `PLAN-20260630-02` | `P1` | `Done` | 接入 Docker Compose 初始化流程 | 2026-06-30 | `5d22e59` |
| `T-032` | `PLAN-20260630-02` | `P1` | `Done` | 增加 GitHub Actions CI | 2026-06-30 | `da990bd` |
| `T-033` | `PLAN-20260630-02` | `P2` | `Done` | 强化本地验收脚本为发布前检查入口 | 2026-06-30 | `4a03381` |
| `T-034` | `PLAN-20260630-02` | `P2` | `Done` | 补充 README 截图和演示说明 | 2026-06-30 | `a0bccfa` |
| `T-035` | `PLAN-20260630-02` | `P2` | `Done` | 跑一次真实 RAG eval 与 indexing eval 基线 | 2026-06-30 | `ee845e3` |
| `T-036` | `PLAN-20260630-02` | `P2` | `Done` | 调查 RAG settings 阶段耗时超阈值 | 2026-06-30 | `72f2780` |
| `T-037` | `PLAN-20260701-01` | `P1` | `Done` | 文档与任务台账状态收口 | 2026-07-01 | `f3ab533` |
| `T-038` | `PLAN-20260701-01` | `P1` | `Done` | 继续拆分前端聊天工作台 hooks | 2026-07-01 | `e984977` |
| `T-039` | `PLAN-20260701-01` | `P1` | `Done` | 跑一轮发布前真实链路验收 | 2026-07-01 | `23e32e5` |
| `T-040` | `PLAN-20260701-01` | `P2` | `Done` | 明确 License 与公开发布说明 | 2026-07-01 | `c885659` |
| `T-041` | `PLAN-20260701-01` | `P2` | `Done` | 梳理在线演示环境方案 | 2026-07-01 | `0474178` |
| `T-042` | `PLAN-20260701-02` | `P0` | `Done` | 建立生产部署安全与数据持久化方案 | 2026-07-01 | `1821713` |
| `T-043` | `PLAN-20260701-02` | `P1` | `Done` | 强化文件上传、向量化任务和 worker 异常状态体验 | 2026-07-01 | `6b3b606` |
| `T-044` | `PLAN-20260701-02` | `P0` | `Done` | 补齐认证、限流、配额和用户 API Key 风控 | 2026-07-01 | `2a27a13` |
| `T-045` | `PLAN-20260701-02` | `P1` | `Done` | 建立统一日志、错误定位和基础监控指标 | 2026-07-02 | `60fd39c` |
| `T-046` | `PLAN-20260701-02` | `P1` | `Done` | 准备真实问题集并固化上线前 RAG 质量门禁 | 2026-07-02 | `88d1c49` |
| `T-047` | `PLAN-20260701-02` | `P2` | `Done` | 区分普通用户模式和高级/开发模式 | 2026-07-02 | `c14ae1a` |
| `T-048` | `PLAN-20260703-01` | `P1` | `Done` | 补齐公网反向代理配置 | 2026-07-03 | `309ef7c` |
| `T-049` | `PLAN-20260703-01` | `P0` | `Done` | 增加公开环境注册控制 | 2026-07-04 | `5ccc8a2` |
| `T-050` | `PLAN-20260703-01` | `P0` | `Done` | 增加 demo 数据清理脚本 | `2026-07-04` | `scripts/demo_cleanup.py`、`docs/DEPLOYMENT.md` |
| `T-051` | `PLAN-20260703-01` | `P2` | `Blocked` | 部署到受控 staging/demo 环境 | — | 缺少真实服务器、域名/TLS 和生产 `.env` |
| `T-052` | `PLAN-20260703-01` | `P2` | `Blocked` | 完成公网 smoke test 与真实 RAG eval | — | 依赖 `T-051` 完成真实部署 |
| `T-053` | 用户要求 | `P1` | `Done` | 用户登录后配置 LLM 与向量模型 API | 2026-07-03 | `6124b2d` |
| `T-054` | `PLAN-20260704-01` | `P1` | `Done` | 支持聊天框图片附件和视觉模型调用 | 2026-07-05 | `42f206b` |
| `T-055` | `PLAN-20260704-01` | `P2` | `Done` | 支持图片/OCR 入知识库检索 | 2026-07-05 | `d8cd9ce` |
| `T-056` | `PLAN-20260705-01` | `P0` | `Done` | 引入 Redis 基础设施、配置和健康检查 | 2026-07-05 | `5e8c32c`、`d0aee38` |
| `T-057` | `PLAN-20260705-01` | `P1` | `Done` | 抽象缓存层并迁移 RAG 热点缓存到 Redis | 2026-07-06 | `654899e` |
| `T-058` | `PLAN-20260705-01` | `P0` | `Done` | 将登录和 API 限流升级为 Redis 分布式限流 | 2026-07-06 | `8875eea` |
| `T-059` | `PLAN-20260705-01` | `P1` | `Done` | 为 vector worker 增加 Redis 运行态、锁和队列观测 | 2026-07-06 | `8f454ef` |
| `T-060` | `PLAN-20260705-01` | `P1` | `Done` | 补齐 Redis 生产部署、preflight 和文档 | 2026-07-06 | `f13f9a5` |
| `T-061` | `PLAN-20260705-01` | `P1` | `Done` | 完成 Redis 场景 Docker 验证和核心链路回归 | 2026-07-06 | `858e27f` |
| `T-062` | `PLAN-20260720-01` | `P1` | `Done` | 收口近期功能、Chroma 架构和任务台账 | 2026-07-20 | 见任务详情 |
| `T-063` | `PLAN-20260720-02` | `P1` | `Done` | 将独立 Chroma 纳入 production preflight 与 acceptance check | 2026-07-20 | 见任务详情 |
| `T-064` | `PLAN-20260720-03` | `P1` | `Done` | 前端统一处理限流响应与重试倒计时 | 2026-07-20 | `0e2ec9d` |
| `T-065` | `PLAN-20260720-04` | `P1` | `Done` | 增加限流命中和 Redis 故障可观测性 | 2026-07-20 | `6328c3b` |
| `T-066` | `PLAN-20260720-05` | `P1` | `Done` | 将依赖漏洞审计和例外复查固化到 CI | 2026-07-20 | `a948662` |
| `T-067` | `PLAN-20260720-06` | `P1` | `Done` | 增加 Python 依赖和 Docker 镜像漏洞 CI 门禁 | 2026-07-20 | `fd18c44` |
| `T-068` | `PLAN-20260720-07` | `P1` | `Done` | 固定 GitHub Actions SHA 并启用 Dependabot 更新 | 2026-07-20 | `06c9b61` |
| `T-069` | `PLAN-20260721-01` | `P1` | `Done` | 补齐知识库和知识文件完整生命周期 | 2026-07-21 | `ac4397b` |
| `T-070` | `PLAN-20260721-02` | `P1` | `Done` | 实现来源原文预览与精确引用跳转 | 2026-07-21 | `11ed2e4` |
| `T-071` | `PLAN-20260721-03` | `P1` | `Done` | 持久化 PDF 页码和 DOCX 段落位置 | 2026-07-21 | `d03de10` |
| `T-072` | `PLAN-20260721-04` | `P1` | `Done` | 为扫描 PDF 增加本地 OCR fallback | 2026-07-21 | `2a9ef37` |
| `T-073` | `PLAN-20260721-05` | `P1` | `Done` | 增加 OCR 质量诊断与单页重新识别 | 2026-07-21 | `729e575` |
| `T-074` | `PLAN-20260721-06` | `P1` | `Done` | 支持 OCR 页面人工校对并重新索引 | 2026-07-21 | `e6cc52d` |
| `T-075` | `PLAN-20260722-01` | `P1` | `Done` | 增加 PDF 与 OCR 校对文本并排工作台 | 2026-07-22 | `976214b` |
| `T-076` | `PLAN-20260722-02` | `P1` | `Done` | 增加文件级 OCR 质量巡检 | 2026-07-22 | `ca92e0b` |
| `T-077` | `PLAN-20260722-03` | `P1` | `Done` | 支持批量 OCR 重新识别与失败重试 | 2026-07-22 | `2de3486` |
| `T-078` | `PLAN-20260722-04` | `P1` | `Doing` | 增加 OCR 识别历史、质量趋势与文本差异 | — | — |

## 新计划接入流程

当后续出现新的开发计划时，按以下步骤更新本文档：

1. 在“计划批次”中新增一行，例如 `PLAN-20260705-01`。
2. 为计划拆出的任务分配新的连续 `T-NNN` ID。
3. 在“任务总览”中新增任务行，`来源计划` 填对应计划 ID。
4. 按“任务模板”复制一段详情，补齐目标、范围、验收标准和建议验证命令。
5. 如果新计划只是补充已有任务，不新增 ID；直接更新已有任务的范围、验收标准或优先级，并在任务详情中记录调整原因。

## 任务模板

````markdown
## T-NNN 任务标题

- 来源计划：`PLAN-YYYYMMDD-NN`
- 优先级：`P1`
- 状态：`Done`
- 目标：
- 范围：
- 验收标准：
  -
- 建议验证命令：

```bash
命令
```
````

## T-001 拆分前端聊天工作台基础类型和工具

- 来源计划：`PLAN-20260628-01`
- 优先级：`P1`
- 状态：`Done`
- 目标：降低 `frontend/src/app/page.tsx` 的单文件复杂度，让后续聊天、文件管理、诊断和任务队列迭代更容易审查。
- 范围：拆分类型定义、共享常量、纯解析函数、格式化函数和状态归一化工具；不改变 UI 文案、交互和接口协议。UI 面板继续拆分由 `T-009` 跟进。
- 验收标准：
  - 主要聊天、上传、向量化、诊断展示行为保持不变。
  - 拆出的模块命名清晰，职责边界稳定。
  - `npm run lint` 和 `npm run build` 通过。
- 完成记录：
  - 完成日期：2026-06-28
  - 相关 commit：`f70e0a6`
  - `frontend/src/app/page.tsx` 从 6313 行降至 4590 行。
  - 新增 `frontend/src/lib/chat-workspace/types.ts`、`constants.ts`、`utils.ts`。
- 建议验证命令：

```bash
cd frontend
npm run lint
npm run build
```

## T-002 建立前端解析/状态工具测试底座

- 来源计划：`PLAN-20260628-01`
- 优先级：`P1`
- 状态：`Done`
- 目标：为前端 retrieval、sources、vector health 等解析逻辑建立单元测试，降低后续拆分和协议演进风险。
- 范围：默认使用 Vitest；优先覆盖 retrieval/source/vector health 解析函数和状态归一化逻辑。
- 验收标准：
  - `frontend/package.json` 增加 `npm run test`。
  - 核心解析函数有单元测试覆盖。
  - `scripts/acceptance_check.sh` 增加可选前端测试阶段，默认纳入静态验收。
- 完成记录：
  - 完成日期：2026-06-28
  - 相关 commit：`48a3d53`
  - 新增 Vitest 测试脚本和 `frontend/src/lib/chat-workspace/utils.test.ts`。
  - 覆盖 retrieval、sources、worker health、vector status、retrieval settings 和 diagnostics timing。
  - `scripts/acceptance_check.sh --skip-real-eval` 已包含前端单测阶段并通过。
- 建议验证命令：

```bash
cd frontend
npm run test
npm run lint
npm run build
cd ..
scripts/acceptance_check.sh --skip-real-eval
```

## T-003 增加 eval 历史趋势摘要

- 来源计划：`PLAN-20260628-01`
- 优先级：`P1`
- 状态：`Done`
- 目标：把 RAG 和 indexing eval 的历史结果沉淀成趋势摘要，便于观察回归质量变化。
- 范围：基于 `docs/evals/runs/*.json` 与 `docs/evals/indexing_runs/*.json` 生成 `docs/evals/latest_summary.md`。
- 验收标准：
  - 摘要展示最近 N 次通过率、平均耗时、首 token、平均引用数和 indexing 成功状态。
  - 脚本可重复运行，输出稳定。
  - 报告不包含账号密码、API Key、JWT 或数据库连接串。
- 完成记录：
  - 完成日期：2026-06-28
  - 相关 commit：`419b10d`
  - 新增 `scripts/eval_summary.py` 和 `backend/tests/test_eval_summary_script.py`。
  - 生成 `docs/evals/latest_summary.md`，该报告被 `.gitignore` 忽略，避免本地趋势报告产生无关提交。
  - `scripts/acceptance_check.sh --skip-real-eval` 已通过。
- 建议验证命令：

```bash
conda run -n firstrag python scripts/eval_summary.py
git diff -- docs/evals/latest_summary.md
```

## T-004 产品化 vector worker health 展示

- 来源计划：`PLAN-20260628-01`
- 优先级：`P1`
- 状态：`Done`
- 目标：让前端任务队列区域更清楚地展示 worker 和队列状态，帮助快速判断是否需要启动 worker、等待或处理失败任务。
- 范围：优先复用现有 `GET /chat/vector-index-jobs/health` 返回值，不新增后端 API。
- 验收标准：
  - 空队列、排队中、处理中、疑似卡住、失败任务均有清晰展示。
  - 展示最近检查时间、手动刷新入口、卡住任务数量和建议操作。
  - 用户能从失败状态快速定位相关文件并看到恢复建议。
- 完成记录：
  - 完成日期：2026-06-28
  - 相关 commit：`c61dcfa`
  - 任务队列面板新增手动刷新、最近检查时间、队列指标、疑似卡住数量和建议操作。
  - 新增 `getWorkerHealthDetails` 等前端 helper，并用 Vitest 覆盖 idle、waiting、active、attention_needed 和 failed queue 场景。
  - `scripts/acceptance_check.sh --skip-real-eval` 已通过。
- 建议验证命令：

```bash
cd frontend
npm run test
npm run lint
npm run build
```

## T-005 完善 indexing failure recovery 分类与操作闭环

- 来源计划：`PLAN-20260628-01`
- 优先级：`P2`
- 状态：`Done`
- 目标：提高向量化失败后的可恢复性，让用户知道失败原因和下一步操作。
- 范围：扩展失败类型识别和提示，例如解析失败、embedding 失败、Chroma 写入失败、数据库 chunk 写入失败和任务超时。
- 验收标准：
  - 后端返回稳定的 `failure_type`、`failure_hint` 和 `can_retry`。
  - 前端按失败类型展示重试、删除向量或重新上传建议。
  - 后端测试覆盖主要失败分类。
- 完成记录：
  - 完成日期：2026-06-28
  - 相关 commit：`5bd9bfe`
  - 后端新增 `chunk_write_error`、`task_timeout` 等稳定分类，并调整数据库连接错误优先级。
  - 前端按 `failure_type` 展示恢复动作列表。
  - 新增 `backend/tests/test_vector_index_failure_recovery.py`，前端 Vitest 覆盖恢复动作映射。
  - `scripts/acceptance_check.sh --skip-real-eval` 已通过。
- 建议验证命令：

```bash
cd backend
conda run -n firstrag python -m unittest discover tests -v
cd ../frontend
npm run lint
npm run build
```

## T-006 扩充 RAG eval case 覆盖面

- 来源计划：`PLAN-20260628-01`
- 优先级：`P2`
- 状态：`Done`
- 目标：让真实 RAG 回归覆盖更多高风险路径，减少路由、rerank 和无答案场景的回归盲区。
- 范围：新增多轮追问、无答案或低相关、禁用 rerank、禁用 query router、`retrieval_mode=never` 等 case。
- 验收标准：
  - `docs/evals/rag_eval_cases.jsonl` 新增 case 后仍可稳定运行。
  - `scripts/rag_eval_gate.sh` 继续全 PASS。
  - 新 case 的期望文件、关键词和检索行为定义清晰。
- 完成记录：
  - 完成日期：2026-06-28
  - 相关 commit：`9620eee`
  - `docs/evals/rag_eval_cases.jsonl` 从 6 条扩展到 10 条，新增多轮追问、禁用 rerank、禁用 query router 和 `retrieval_mode=never` 低相关场景。
  - `scripts/eval_rag.py` 新增 `pre_questions`、`expected_reason_keywords` 和 `expected_diagnostics` 检查能力。
  - `scripts/rag_eval_gate.sh` 已通过：10/10 case PASS，质量门禁全部 PASS。
- 建议验证命令：

```bash
FIRSTRAG_EVAL_USERNAME=你的用户名 \
FIRSTRAG_EVAL_PASSWORD=你的密码 \
scripts/rag_eval_gate.sh
```

## T-007 梳理本地启动与验收工作流文档

- 来源计划：`PLAN-20260628-01`
- 优先级：`P2`
- 状态：`Done`
- 目标：把单人开发的启动、开发、验收和 push 流程整理成可重复执行的日常工作流。
- 范围：更新 `docs/DEPLOYMENT.md` 或 `docs/evals/README.md`，串联后端、前端、worker、真实 eval 和一键验收脚本。
- 验收标准：
  - 文档可按顺序完成启动、开发、验收、push。
  - 明确说明何时需要启动 worker，何时可使用 `--skip-real-eval`。
  - 不写入真实账号密码或敏感配置。
- 完成记录：
  - 完成日期：2026-06-28
  - 相关 commit：`7c52ae8`
  - `docs/DEPLOYMENT.md` 已补充本地 conda 启动、worker 使用时机、静态验收、完整真实验收和 push 前检查流程。
  - 文档明确 `--skip-real-eval` 的适用场景，以及 RAG、indexing、用户模型配置等必须跑真实验收的场景。
  - `scripts/acceptance_check.sh --skip-real-eval` 已通过。
- 建议验证命令：

```bash
scripts/acceptance_check.sh --skip-real-eval
```

## T-008 为部署目录补齐可运行 Docker Compose 方案

- 来源计划：`PLAN-20260628-01`
- 优先级：`P2`
- 状态：`Done`
- 目标：把当前占位部署配置推进到可本地运行的 Docker Compose 方案。
- 范围：补齐 PostgreSQL、后端、前端、worker 服务，并明确 Chroma/vector_db 持久化目录。
- 验收标准：
  - 新环境可按文档启动基础服务。
  - 敏感配置仍通过 `.env` 注入，不提交真实密钥。
  - worker 和后端共享必要的上传目录、vector_db 和数据库配置。
- 完成记录：
  - 完成日期：2026-06-28
  - 相关 commit：`7c52ae8`
  - `docker-compose.yml` 已补齐 `postgres`、`backend`、`frontend` 和 `worker` 服务。
  - 新增 `deploy/docker/backend.Dockerfile`、`deploy/docker/frontend.Dockerfile` 和 `.dockerignore`。
  - `.env.example` 增加 compose PostgreSQL 变量和可选 `COMPOSE_DATABASE_URL`，避免容器内误用指向宿主机的 `DATABASE_URL`。
  - 文档已说明 `uploads`、`vector_db`、`models` 和 `postgres_data` 的持久化方式。
  - 当前 compose 不自动创建业务基础表，该限制已在 `docs/DEPLOYMENT.md` 中说明，后续可单独新增迁移执行任务。
  - `docker compose config --quiet` 已通过。
- 建议验证命令：

```bash
docker compose config --quiet
```

## T-009 继续拆分前端聊天工作台 UI 面板

- 来源计划：`PLAN-20260628-01`
- 优先级：`P1`
- 状态：`Done`
- 目标：在 `T-001` 的类型和工具拆分基础上，继续降低 `frontend/src/app/page.tsx` 的 UI 维护成本。
- 范围：拆分文件管理面板、任务队列面板、诊断展示面板等 UI 组件；优先复用 `frontend/src/lib/chat-workspace/` 中的类型和工具，不改变现有接口协议和用户可见行为。
- 验收标准：
  - 主要聊天、上传、向量化、诊断展示行为保持不变。
  - `page.tsx` 只保留页面级状态编排、请求副作用和顶层布局。
  - `npm run lint` 和 `npm run build` 通过。
- 完成记录：
  - 完成日期：2026-06-28
  - 相关 commit：`bdd53c8`
  - 新增 `FileManagerDialog`、`TaskQueuePanel`、`MessageDiagnosticsPanel` 三个聊天工作台组件。
  - `frontend/src/app/page.tsx` 从 4607 行降至 3663 行，文件管理、任务队列和诊断展示 JSX 已外移。
  - `scripts/acceptance_check.sh --skip-real-eval` 已通过。
- 建议验证命令：

```bash
cd frontend
npm run test
npm run lint
npm run build
```

## T-010 优化知识库检索速度，降低 rerank 开销

- 来源计划：`PLAN-20260628-02`
- 优先级：`P1`
- 状态：`Done`
- 目标：降低知识库检索阶段耗时，优先压缩 CrossEncoder rerank 对 `pre_answer_total_ms` 和首 token 前等待时间的影响。
- 范围：将默认 `rrf_k` 从 20 调低到 10；候选数不超过最终 `top_k` 时跳过 CrossEncoder；降低 reranker 默认 `max_length`；保留知识库设置覆盖能力。
- 基线观察：
  - 最新 RAG eval 报告中，启用 rerank 的检索常见为 1.8s 到 7.2s。
  - `rag_core_without_rerank` 的检索耗时约 378ms，说明主要瓶颈在 CrossEncoder rerank。
- 验收标准：
  - 默认 `rrf_k=10`，已有知识库仍可通过 retrieval settings 手动覆盖。
  - 小候选集场景跳过 rerank，并在 diagnostics 中记录跳过原因。
  - 候选数超过 `top_k` 时仍执行 rerank，保证高召回场景排序质量。
  - 后端测试、前端测试、lint 和 build 通过。
- 完成记录：
  - 完成日期：2026-06-28
  - 相关 commit：`8c9ac21`
  - 默认 `rrf_k` 已从 20 调整为 10，并新增 `012_default_retrieval_rrf_k_10.sql` 更新数据库默认值和旧默认记录。
  - `hybrid_retriever` 在候选数不超过 `top_k` 时跳过 CrossEncoder，并写入 `rerank_skipped` 与 `rerank_skip_reason` diagnostics。
  - reranker 默认 `max_length` 从 512 降到 384，减少 CPU 推理输入长度。
  - RAG eval case 已显式覆盖 `rrf_k=10`，报告中真实链路 `fused=10`。
  - 真实 RAG eval 10/10 PASS，平均首 token 等待从 5049.24ms 降至 3494.03ms，平均总耗时从 7.66s 降至 6.50s。
  - `scripts/acceptance_check.sh --skip-real-eval` 已通过。
- 建议验证命令：

```bash
scripts/acceptance_check.sh --skip-real-eval
FIRSTRAG_EVAL_USERNAME=你的用户名 \
FIRSTRAG_EVAL_PASSWORD=你的密码 \
scripts/rag_eval_gate.sh
```

## T-011 增加知识库画像进程内轻量缓存

- 来源计划：`PLAN-20260628-03`
- 优先级：`P1`
- 状态：`Done`
- 目标：减少 RAG 前置阶段重复读取知识库文件列表的开销，降低 `knowledge_profile_ms` 和检索前等待时间。
- 范围：新增进程内短 TTL cache，缓存知识库 profile 文本和已索引 file_ids；文件上传、知识库文件关联变化、向量化状态变化和删除向量结果时主动失效；diagnostics 暴露缓存命中情况。
- 验收标准：
  - 同一知识库的 profile 和 file_ids 复用同一份缓存上下文。
  - 本请求发生过缓存 miss 时，diagnostics 不被后续同请求 hit 误报为 true。
  - 文件关系和索引状态变化后相关缓存会失效。
  - 后端测试、前端 lint/test/build 和 RAG eval 通过。
- 完成记录：
  - 完成日期：2026-06-28
  - 相关 commit：`9f178fc`
  - 新增 `knowledge_profile_cache` 进程内短 TTL cache，缓存知识库 profile 文本和已索引 file_ids。
  - `rag_service` 的 profile 构建和检索文件范围复用同一份缓存上下文。
  - 文件上传、知识库文件关联变化、向量化状态变化和删除向量结果时会主动失效相关缓存。
  - retrieval diagnostics 会合并 `knowledge_profile_cache_hit`、已索引文件数和总文件数。
  - `scripts/acceptance_check.sh --skip-real-eval` 已通过：后端 80 个 unittest、前端 lint/test/build 通过。
  - `scripts/rag_eval_gate.sh` 已通过：10/10 PASS。
- 建议验证命令：

```bash
scripts/acceptance_check.sh --skip-real-eval
FIRSTRAG_EVAL_USERNAME=你的用户名 \
FIRSTRAG_EVAL_PASSWORD=你的密码 \
scripts/rag_eval_gate.sh
```

## T-012 RAG eval 报告补齐缓存与阶段耗时摘要

- 来源计划：`PLAN-20260628-04`
- 优先级：`P1`
- 状态：`Done`
- 目标：让 RAG eval 报告稳定展示检索前置阶段、混合检索和 rerank 耗时，为后续 Query Router、settings、profile 优化提供量化依据。
- 范围：扩展 `scripts/eval_rag.py` 的 summary、Markdown 报告和历史 JSON，展示 `knowledge_profile_cache_hit`、`retrieval_settings_ms`、`knowledge_profile_ms`、`query_router_ms`、`retrieve_documents_ms`、`retrieval_total_ms` 和 `rerank_ms`。
- 验收标准：
  - 报告顶部展示平均阶段耗时和 knowledge profile 缓存命中情况。
  - 报告包含按 case 展示的阶段耗时摘要表。
  - 每个 case 详情展示缓存命中和关键阶段耗时。
  - 单元测试覆盖 summary 字段和 Markdown 输出。
  - 静态验收和真实 RAG eval 通过。
- 完成记录：
  - 完成日期：2026-06-28
  - 相关 commit：`e123014`
  - `scripts/eval_rag.py` 已在 summary 和历史 JSON 中写入平均 settings、profile、router、retrieve、hybrid、rerank 耗时。
  - Markdown 报告新增“阶段耗时摘要”表，并在每个 case 详情展示缓存命中和关键阶段耗时。
  - 新增单元测试覆盖阶段 summary 和 Markdown 输出。
  - `scripts/acceptance_check.sh --skip-real-eval` 已通过：后端 81 个 unittest、前端 lint/test/build 通过。
  - `scripts/rag_eval_gate.sh` 已通过：10/10 PASS，报告已生成阶段耗时摘要。
- 建议验证命令：

```bash
scripts/acceptance_check.sh --skip-real-eval
FIRSTRAG_EVAL_USERNAME=你的用户名 \
FIRSTRAG_EVAL_PASSWORD=你的密码 \
scripts/rag_eval_gate.sh
```

## T-013 修正真实 RAG eval 缓存命中字段为空

- 来源计划：`PLAN-20260628-05`
- 优先级：`P1`
- 状态：`Done`
- 目标：确保 `knowledge_profile_cache_hit`、已索引文件数和总文件数能穿过 LCEL 流式边界，稳定进入真实 RAG eval 报告。
- 范围：修正 `rag_service` 中 cache diagnostics 的传递时机，必要时复用 retrieval diagnostics metadata 兜底路径；补充单元测试。
- 验收标准：
  - `retrieve_documents` 返回的文档 metadata 中包含 knowledge profile cache diagnostics。
  - `stream_rag_response` 在 ContextVar 丢失时仍能从文档 metadata 读到 cache diagnostics。
  - 静态验收和真实 RAG eval 通过。
- 完成记录：
  - 完成日期：2026-06-29
  - 相关 commit：`cf01e5b`
  - `retrieve_documents` 已将 knowledge profile cache diagnostics 合并进文档 metadata，作为 LCEL 流式边界丢失 ContextVar 时的兜底来源。
  - `stream_rag_response` 复用同一合并逻辑，确保 SSE retrieval diagnostics 和 eval 报告能稳定读取缓存命中字段。
  - `conda run -n firstrag python -m unittest tests.test_rag_service -v` 已通过：22 个用例通过。
  - `scripts/acceptance_check.sh --skip-real-eval` 已通过后端 82 个 unittest、前端 lint、Vitest 10 个用例；Next build 在沙箱内因 Turbopack 端口权限限制失败，已单独提权运行 `npm run build` 并通过。
  - `scripts/rag_eval_gate.sh` 已通过：10/10 PASS；最新报告显示 knowledge profile 缓存命中 `7/8（0.88）`，不再是 `0/0（—）`。
- 建议验证命令：

```bash
scripts/acceptance_check.sh --skip-real-eval
FIRSTRAG_EVAL_USERNAME=你的用户名 \
FIRSTRAG_EVAL_PASSWORD=你的密码 \
scripts/rag_eval_gate.sh
```

## T-014 定位并优化 retrieval settings 阶段耗时

- 来源计划：`PLAN-20260629-01`
- 优先级：`P1`
- 状态：`Done`
- 目标：解释并降低最新 RAG eval 报告中 `retrieval_settings_ms` 平均约 2.39s 的异常耗时。
- 范围：补充 settings 子阶段计时，确认耗时来源是数据库连接、SQL 查询、LCEL 调度、真实 eval 设置 PATCH 影响，还是其它链路开销；本任务不引入 Redis。
- 验收标准：
  - RAG eval 报告能区分 settings 子阶段耗时，不再只有不可解释的 `retrieval_settings_ms` 黑盒指标。
  - 若发现明确瓶颈，完成对应轻量优化或拆出新的后续任务。
  - 静态验收和真实 RAG eval 通过。
- 完成记录：
  - 完成日期：2026-06-29
  - 相关 commit：`6e3c1d7`
  - 新增 `retrieval_settings_load_total_ms`、`retrieval_settings_query_ms`、`retrieval_settings_normalize_ms`，并随 `retrieval_settings` Runnable 输出传递，避免 ContextVar 跨 LCEL 边界丢失。
  - RAG eval summary、历史 JSON、Markdown 阶段耗时表和 case 详情均展示 settings 子阶段。
  - 最新真实 RAG eval 10/10 PASS，报告显示平均 `retrieval_settings_ms=926.90ms`，但实际 `settings_load=6.38ms`、`settings_query=6.37ms`、`settings_normalize=0.00ms`。
  - 结论：秒级 `retrieval_settings_ms` 主要不是数据库查询本身，而是 LCEL 外层阶段观测口径包含相邻 Runnable 调度或等待；后续 `T-015` 的检索设置缓存可降低查询抖动，但不应预期单独消除全部外层 settings 等待。
  - `scripts/acceptance_check.sh --skip-real-eval` 已通过后端 83 个 unittest、前端 lint、Vitest 10 个用例；Next build 在沙箱内因 Turbopack 端口权限限制失败，已单独提权运行 `npm run build` 并通过。
- 建议验证命令：

```bash
scripts/acceptance_check.sh --skip-real-eval
FIRSTRAG_EVAL_USERNAME=你的用户名 \
FIRSTRAG_EVAL_PASSWORD=你的密码 \
scripts/rag_eval_gate.sh
```

## T-015 为知识库检索设置增加进程内轻量缓存

- 来源计划：`PLAN-20260629-01`
- 优先级：`P1`
- 状态：`Done`
- 目标：减少每轮聊天重复读取 `knowledge_base_retrieval_settings` 的开销，降低 settings 阶段对首 token 前等待时间的影响。
- 范围：实现进程内短 TTL cache，key 使用 `user_id + knowledge_base_id`；更新 retrieval settings 后主动失效；普通读取路径复用缓存；不新增 Redis。
- 验收标准：
  - 设置更新后下一轮聊天立即读取新配置。
  - 普通聊天路径能命中缓存并在 diagnostics 或测试中可观察。
  - 后端测试覆盖 cache miss、hit、主动失效、TTL 过期和默认值路径。
  - 静态验收和真实 RAG eval 通过。
- 完成记录：
  - 完成日期：2026-06-29
  - 相关 commit：`6d1ee1a`
  - 新增 `retrieval_settings_cache` 进程内短 TTL cache，缓存 key 为 `user_id + knowledge_base_id`；知识库不存在时不缓存 `None`。
  - RAG 读取路径和本地问候短路判断已复用缓存；PATCH retrieval settings 成功后会主动失效对应知识库缓存。
  - diagnostics 和 RAG eval 报告新增 `retrieval_settings_cache_hit`、`retrieval_settings_source` 和 settings 缓存命中率。
  - 最新真实 RAG eval 10/10 PASS，报告显示 retrieval settings 缓存命中 `2/9（0.22）`，settings 子阶段为 `load=9.68ms`、`query=9.67ms`、`normalize=0.00ms`。
  - `scripts/acceptance_check.sh --skip-real-eval` 已通过后端 87 个 unittest、前端 lint、Vitest 10 个用例；Next build 在沙箱内因 Turbopack 端口权限限制失败，已单独提权运行 `npm run build` 并通过。
- 建议验证命令：

```bash
cd backend
conda run -n firstrag python -m unittest discover tests -v
cd ..
scripts/acceptance_check.sh --skip-real-eval
FIRSTRAG_EVAL_USERNAME=你的用户名 \
FIRSTRAG_EVAL_PASSWORD=你的密码 \
scripts/rag_eval_gate.sh
```

## T-016 优化 hybrid retrieval 粗召回执行路径

- 来源计划：`PLAN-20260629-01`
- 优先级：`P1`
- 状态：`Done`
- 目标：压缩 vector、fulltext、RRF 和 rerank 前的检索等待，继续降低启用检索场景的首 token 前耗时。
- 范围：优先评估并实现 vector 与 fulltext 粗召回的安全并行；保留现有权限过滤、软删除过滤、diagnostics、向量降级和单路失败兜底行为。
- 验收标准：
  - RAG eval 继续 10/10 PASS。
  - diagnostics 仍包含 `vector_count`、`fulltext_count`、`fused_count`、`reranked_count` 和阶段耗时。
  - vector 或 fulltext 单路失败时，另一通道仍可返回候选并记录降级信息。
  - 静态验收和真实 RAG eval 通过。
- 完成记录：
  - 完成日期：2026-06-29。
  - 相关 commit：`2477565`。
  - 实现内容：vector 和 fulltext 粗召回改为并行执行；新增 fulltext 降级 diagnostics；单路失败时另一通道仍可兜底进入 RRF/rerank。
  - 验证命令：`cd backend && conda run -n firstrag python -m unittest tests.test_retrieval_resilience -v`；`cd backend && conda run -n firstrag python -m compileall app tests`；`scripts/acceptance_check.sh --skip-real-eval`；`FIRSTRAG_EVAL_USERNAME=... FIRSTRAG_EVAL_PASSWORD=... scripts/rag_eval_gate.sh`。
  - 真实 RAG eval：10/10 PASS，平均 sources 2.60，平均首 token 4164.16ms，平均总耗时 6.07s；报告 `docs/evals/latest_rag_eval_report.md`，历史记录 `docs/evals/runs/20260629_132041.json`。
- 建议验证命令：

```bash
cd backend
conda run -n firstrag python -m unittest discover tests -v
cd ..
scripts/acceptance_check.sh --skip-real-eval
FIRSTRAG_EVAL_USERNAME=你的用户名 \
FIRSTRAG_EVAL_PASSWORD=你的密码 \
scripts/rag_eval_gate.sh
```

## T-017 增加 query embedding 进程内短 TTL 缓存

- 来源计划：`PLAN-20260629-01`
- 优先级：`P2`
- 状态：`Done`
- 目标：减少短时间内重复问题、eval 重跑和多轮相近测试对 embedding provider 的重复调用。
- 范围：缓存 query embedding，不缓存最终答案或用户私密内容；key 使用 provider、model 和 normalized query；embedding 生成失败不写入缓存；不新增 Redis。
- 验收标准：
  - 重复 query 在 TTL 内命中缓存。
  - TTL 过期后会重新生成 embedding。
  - embedding provider 报错时不会污染缓存，后续请求仍可正常重试。
  - 后端测试覆盖命中、过期和失败不缓存路径。
- 完成记录：
  - 完成日期：2026-06-29。
  - 相关 commit：`cbd00d8`。
  - 实现内容：新增 query embedding 短 TTL 进程内缓存，key 使用 provider、model 和 normalized query；缓存命中写入 retrieval diagnostics；embedding 失败不写缓存。
  - 验证命令：`cd backend && conda run -n firstrag python -m unittest tests.test_retrieval_resilience -v`；`cd backend && conda run -n firstrag python -m unittest discover tests -v`；`cd backend && conda run -n firstrag python -m compileall app tests`；`scripts/acceptance_check.sh --skip-real-eval`；`cd frontend && npm run build`；`FIRSTRAG_EVAL_USERNAME=... FIRSTRAG_EVAL_PASSWORD=... scripts/rag_eval_gate.sh`。
  - 真实 RAG eval：10/10 PASS，平均 sources 2.40，平均首 token 3456.01ms，平均总耗时 6.14s；报告 `docs/evals/latest_rag_eval_report.md`，历史记录 `docs/evals/runs/20260629_132659.json`。
- 建议验证命令：

```bash
cd backend
conda run -n firstrag python -m unittest discover tests -v
cd ..
scripts/acceptance_check.sh --skip-real-eval
FIRSTRAG_EVAL_USERNAME=你的用户名 \
FIRSTRAG_EVAL_PASSWORD=你的密码 \
scripts/rag_eval_gate.sh
```

## T-018 固化 RAG eval 性能门槛和趋势字段

- 来源计划：`PLAN-20260629-01`
- 优先级：`P2`
- 状态：`Done`
- 目标：把 RAG 性能优化从单次报告观察升级为可持续追踪，让性能回退在验收报告中显眼暴露。
- 范围：扩展 eval summary/report，记录 settings、profile、retrieve、hybrid、rerank 的最近 N 次均值和变化，并加入建议阈值；不在报告中输出账号密码、API Key、JWT 或数据库连接串。
- 验收标准：
  - `docs/evals/latest_summary.md` 展示阶段耗时趋势。
  - RAG eval Markdown 报告展示关键性能门槛和本次是否通过。
  - 历史 JSON 保留必要字段，便于后续比较。
  - 单元测试覆盖 summary 字段和 Markdown 输出。
- 完成记录：
  - 完成日期：2026-06-29。
  - 相关 commit：`7793856`。
  - 实现内容：RAG eval Markdown 增加建议性能门槛表，历史 JSON 写入 `performance_thresholds`；summary 报告增加最近 N 次 settings、profile、retrieve、hybrid、rerank 阶段耗时趋势和阈值状态。
  - 验证命令：`conda run -n firstrag python scripts/eval_summary.py`；`cd backend && conda run -n firstrag python -m unittest tests.test_eval_rag_script tests.test_eval_summary_script -v`；`cd backend && conda run -n firstrag python -m unittest discover tests -v`；`conda run -n firstrag python -m compileall scripts backend/tests`；`scripts/acceptance_check.sh --skip-real-eval`；`cd frontend && npm run build`；`FIRSTRAG_EVAL_USERNAME=... FIRSTRAG_EVAL_PASSWORD=... scripts/rag_eval_gate.sh`。
  - 真实 RAG eval：10/10 PASS，平均 sources 2.60，平均首 token 5124.83ms，平均总耗时 8.43s；报告 `docs/evals/latest_rag_eval_report.md`，历史记录 `docs/evals/runs/20260629_142851.json`。
- 建议验证命令：

```bash
conda run -n firstrag python scripts/eval_summary.py
cd backend
conda run -n firstrag python -m unittest discover tests -v
cd ..
scripts/acceptance_check.sh --skip-real-eval
FIRSTRAG_EVAL_USERNAME=你的用户名 \
FIRSTRAG_EVAL_PASSWORD=你的密码 \
scripts/rag_eval_gate.sh
```

## T-019 加固用户自定义 LLM Base URL SSRF 防护

- 来源计划：`PLAN-20260629-02`
- 优先级：`P1`
- 状态：`Done`
- 审查依据：`backend/app/services/user_settings_service.py` 已限制自定义 Base URL 开关、HTTPS、本机域名和字面 IP 私网地址，但非 IP 域名解析到私网地址的场景当前依赖部署环境出口策略。
- 目标：补齐应用层 SSRF 防御纵深，避免开启 `ALLOW_USER_CUSTOM_LLM_BASE_URL` 后被构造域名绕过私网地址检查。
- 范围：增强 `_validate_user_base_url`；解析域名 A/AAAA 记录并拒绝 loopback、private、link-local、multicast、reserved 等非公网地址；必要时限制重定向或在模型连通性测试前复核最终请求地址；保留当前厂商预设地址的兼容行为。
- 验收标准：
  - `localhost`、`.localhost`、`.local`、私网字面 IP 和解析到私网 IP 的域名都会被拒绝。
  - 公网 HTTPS 域名在开关开启时仍可保存和测试。
  - 错误信息不泄露用户 API Key、JWT 或内部网络细节。
  - 单元测试覆盖 DNS 解析成功、解析失败、IPv4/IPv6 私网和公网场景。
- 完成记录：
  - 完成日期：2026-06-29
  - 相关 commit：`fd64b6d`
  - `_validate_user_base_url` 已补充 DNS 解析校验，拒绝解析到非公网地址、解析失败和 IPv6 私网地址。
  - 新增服务单测覆盖公网 DNS、DNS 私网目标、DNS 失败和 IPv6 私网。
  - `scripts/acceptance_check.sh --skip-real-eval` 已通过。
- 建议验证命令：

```bash
cd backend
conda run -n firstrag python -m unittest tests.test_user_settings -v
conda run -n firstrag python -m unittest tests.services.test_user_settings_service -v
```

## T-020 收紧知识文件上传类型与解析失败反馈

- 来源计划：`PLAN-20260629-02`
- 优先级：`P1`
- 状态：`Done`
- 审查依据：`backend/app/api/knowledge_files.py` 接收上传后按原始扩展名落盘，`document_service.load_document` 只支持 `.pdf`、`.docx`、`.md`、`.txt`，不支持的文件会到 worker 阶段才表现为“未解析出可入库的文本分块”。
- 目标：在上传或入队前给用户明确、可恢复的文件类型反馈，减少无效 vector job 和失败噪音。
- 范围：统一定义支持的扩展名和 MIME 类型；上传阶段拒绝明显不支持的文件；indexing 阶段保留解析失败分类，区分“不支持类型”“空文档”“解析器异常”；同步更新前端提示和 API 文档。
- 验收标准：
  - 不支持的文件类型返回 `400` 或清晰业务错误，不创建无效 indexing job。
  - 支持的 `.pdf`、`.docx`、`.md`、`.txt` 上传和自动向量化行为保持不变。
  - 失败记录能在任务队列中展示可理解原因。
  - 后端测试覆盖支持类型、不支持类型、空内容和解析异常路径。
- 完成记录：
  - 完成日期：2026-06-29
  - 相关 commit：`fd64b6d`
  - 上传入口会在创建文件记录和 vector job 前拒绝不支持的扩展名或明显不匹配的 MIME 类型。
  - 文档解析层新增 `UnsupportedDocumentTypeError` 和 `EmptyDocumentError`，向量任务失败分类新增 `unsupported_file_type` 与 `empty_document`。
  - `docs/API.md` 已补充支持类型和新增 failure type。
  - `scripts/acceptance_check.sh --skip-real-eval` 已通过。
- 建议验证命令：

```bash
cd backend
conda run -n firstrag python -m unittest tests.test_knowledge_files tests.test_vector_index_failure_recovery -v
cd ..
scripts/acceptance_check.sh --skip-real-eval
```

## T-021 抽取前端 API proxy 共享 helper

- 来源计划：`PLAN-20260629-02`
- 优先级：`P1`
- 状态：`Done`
- 审查依据：`frontend/src/app/api/**/route.ts` 当前约有 23 个 proxy route，重复实现 backend URL 拼接、`Authorization` 转发、`cache: "no-store"`、错误兜底和 streaming header。
- 目标：降低前端 API proxy 的复制粘贴风险，后续调整超时、错误格式、认证 header 或 SSE header 时只改一处。
- 范围：新增 `frontend/src/lib/api-proxy.ts` 或等价 helper；覆盖普通 JSON proxy、multipart upload proxy、DELETE/PATCH/POST 透传和 SSE streaming proxy；保留动态 route handler 的显式 `params` 类型。
- 验收标准：
  - `/api/chat` 继续保持 streaming body，不提前读取完整响应。
  - 普通 API 继续透传后端状态码、`Content-Type` 和安全的错误信息。
  - 23 个 route 中重复样板明显减少，业务路径和方法映射清晰。
  - 前端 lint/build 通过，并补充 proxy helper 单元测试或最小 route 测试。
- 完成记录：
  - 完成日期：2026-06-29
  - 相关 commit：`fd64b6d`
  - 新增 `frontend/src/lib/api-proxy.ts`，集中处理 backend URL、Authorization、文本 body、FormData、Set-Cookie 和 SSE no-buffer header。
  - 23 个 Next API route 已迁移到共享 helper；`/api/chat` 继续直接返回 upstream body，保持 streaming。
  - 新增 `frontend/src/lib/api-proxy.test.ts` 覆盖 JSON、SSE 和 multipart proxy 行为。
  - `scripts/acceptance_check.sh --skip-real-eval` 已通过。
- 建议验证命令：

```bash
cd frontend
npm run lint
npm run test
npm run build
```

## T-022 继续拆分聊天工作台请求与流式状态逻辑

- 来源计划：`PLAN-20260629-02`
- 优先级：`P1`
- 状态：`Done`
- 审查依据：`frontend/src/app/page.tsx` 已从早期规模下降，但仍约 3663 行，包含 30 多个 `useState`、多组 knowledge base/file/vector 请求、轮询、会话管理和 SSE 解析。
- 目标：把页面组件从“大型状态容器”继续拆成可测试 hook 和纯函数，降低后续改聊天流、文件管理、诊断面板时的回归风险。
- 范围：优先抽取认证守卫、knowledge base/file 数据请求、vector job 轮询、chat streaming reducer；保留现有 UI 文案和视觉结构；避免在同一任务中做大规模样式重写。
- 验收标准：
  - `page.tsx` 行数和状态分支明显下降，核心渲染结构更容易扫描。
  - SSE block 解析、done/sources/retrieval 事件合并和 fallback answer 逻辑有单元测试覆盖。
  - 轮询 effect 卸载时继续正确清理 interval，不产生重复请求。
  - 前端 lint/test/build 通过。
- 完成记录：
  - 完成日期：2026-06-29
  - 相关 commit：`017526b`, `cab5f9f`
  - 新增 `frontend/src/lib/chat-workspace/chat-stream.ts`，集中处理 JSON、纯文本和 SSE streaming response，并保留页面侧 assistant 状态更新 callback。
  - 新增 `frontend/src/lib/chat-workspace/chat-stream.test.ts`，覆盖 answer、done、sources、retrieval、分片 SSE、done-only fallback 等流式边界。
  - `frontend/src/app/page.tsx` 从 3663 行降至 3497 行；vector job 轮询 effect 未调整，清理逻辑保持原状。
  - 2026-06-29 复验发现 done event 的最终 answer 与已流式 partial 不一致时，页面 fallback callback 只填空内容，无法修正 partial；`cab5f9f` 已改为替换最后一条 assistant 内容，并补充回归测试。
  - `npm run test`、`npm run lint`、`npm run build` 已通过；复验后前端 Vitest 为 20 个用例。
- 建议验证命令：

```bash
cd frontend
npm run test
npm run lint
npm run build
```

## T-023 拆分 RAG service 的路由、诊断和引用序列化职责

- 来源计划：`PLAN-20260629-02`
- 优先级：`P2`
- 状态：`Done`
- 审查依据：`backend/app/services/rag_service.py` 约 1106 行，同时承担 LLM 配置、Query Router、knowledge profile、retrieval settings diagnostics、retrieval 执行、引用序列化和 LCEL chain 组装。
- 目标：保持 RAG 行为不变的前提下降低单文件复杂度，让后续检索策略、diagnostics 和 prompt 调整更容易局部验证。
- 范围：按职责拆出 `retrieval_decision`、`rag_diagnostics`、`reference_serializer`、`chain_builder` 等模块或同等边界；保留现有 public function 兼容入口；不改变 SSE 协议和 eval 指标字段。
- 验收标准：
  - 现有 RAG 单元测试全部通过，真实 RAG eval 继续 10/10 PASS。
  - diagnostics 字段名称、sources 序列化结构和 message 持久化行为保持兼容。
  - 拆分后模块之间只传基础类型或明确的 dataclass/TypedDict，减少 ContextVar 泄漏风险。
  - 文档同步说明 RAG service 新边界。
- 完成记录：
  - 完成日期：2026-06-30
  - 相关 commit：`36ad4ee`
  - `backend/app/services/rag_service.py` 已收敛为兼容门面，从 1106 行降至约 67 行。
  - 新增 `backend/app/services/rag/` 内部模块：`chain_builder.py`、`retrieval_decision.py`、`retrieval_pipeline.py`、`reference_serializer.py`、`diagnostics.py`、`streaming.py` 和 `types.py`。
  - `docs/RAG_WORKFLOW.md` 与 `docs/BACKEND.md` 已同步记录 RAG service 新边界。
  - `conda run -n firstrag python -m unittest tests.test_rag_service tests.test_retrieval_resilience -v`、`conda run -n firstrag python -m unittest discover tests -v`、`conda run -n firstrag python -m compileall app tests` 已通过。
  - `scripts/acceptance_check.sh --skip-real-eval` 已通过后端 107 个 unittest、前端 lint、Vitest 32 个用例和 Next build。
  - 真实 RAG eval 已通过：10/10 PASS，平均 sources 2.20，平均首 token 3715.19ms，平均总耗时 5.96s；报告 `docs/evals/latest_rag_eval_report.md`，历史记录 `docs/evals/runs/20260630_085703.json`。
- 建议验证命令：

```bash
cd backend
conda run -n firstrag python -m unittest tests.test_rag_service tests.test_retrieval_resilience -v
cd ..
scripts/acceptance_check.sh --skip-real-eval
FIRSTRAG_EVAL_USERNAME=你的用户名 \
FIRSTRAG_EVAL_PASSWORD=你的密码 \
scripts/rag_eval_gate.sh
```

## T-024 建立权限、上传和流式代理的回归测试矩阵

- 来源计划：`PLAN-20260629-02`
- 优先级：`P2`
- 状态：`Done`
- 审查依据：当前后端已有 conversation、knowledge file、vector index、RAG 等测试，前端也有解析工具测试；但跨用户 IDOR、防 unsupported upload、Next API proxy streaming/错误透传这些审查重点仍缺少集中矩阵。
- 目标：把代码审查中最容易回归的边界固化成测试，减少依赖人工抽查。
- 范围：补充后端权限隔离测试、软删除过滤测试、上传类型/大小测试；补充前端 proxy helper、`frontend-api`、`chat-workspace/api` 和 SSE 解析测试；将关键命令纳入 `scripts/acceptance_check.sh --skip-real-eval` 或明确可选开关。
- 验收标准：
  - 跨用户访问知识库、文件、会话、vector job 均返回 `404` 或安全错误。
  - 不支持上传类型、超大文件、空解析结果都有稳定测试。
  - SSE proxy 测试证明 body 不被提前完整读取，错误响应仍保留状态码。
  - 前端请求层测试覆盖 auth header、401 跳转、Zod 响应外壳校验和错误消息解析。
  - 静态验收脚本能一键覆盖新增测试。
- 调整记录：
  - 2026-06-29：`T-025` 已完成前端请求层集中化，后续测试矩阵需要覆盖新的 `frontend/src/lib/frontend-api.ts` 与 `frontend/src/lib/chat-workspace/api.ts` 边界。
- 完成记录：
  - 完成日期：2026-06-29
  - 相关 commit：`49e0ba7`
  - 后端新增会话消息/诊断/重命名的权限隔离测试，补齐 vector job、单文件向量化提交和删除向量的跨用户 404 边界。
  - 上传回归测试补齐超大文件 `413`；worker 测试补齐空文档解析结果失败入库路径。
  - 前端新增 `frontend-api` 与 `chat-workspace/api` 单测，覆盖 auth header、401 清理跳转、Zod 外壳校验、错误解析、chat 原生 Response 和工作台响应归一化。
  - `api-proxy` 新增流式响应非 eager read 测试，确认 SSE body 不会在 proxy 层被提前完整读取。
  - `scripts/acceptance_check.sh --skip-real-eval` 已通过后端 107 个 unittest、前端 lint、Vitest 32 个用例和 Next build。
- 建议验证命令：

```bash
cd backend
conda run -n firstrag python -m unittest discover tests -v
cd ../frontend
npm run test
npm run lint
npm run build
cd ..
scripts/acceptance_check.sh --skip-real-eval
```

## T-025 引入 React Query 与 Zod 集中前端数据请求层

- 来源计划：`PLAN-20260629-02`
- 优先级：`P1`
- 状态：`Done`
- 审查依据：`frontend/src/app/page.tsx` 在完成 SSE streaming 抽取后仍保留大量直接 `fetch`、Authorization 拼接、401 跳转、错误解析、响应外壳判断和高频派生数据计算。
- 目标：把工作台请求样板集中到前端 API 层，引入 React Query 承接可重复读取的 server state，并使用 Zod 对后端响应外壳做轻量运行时校验。
- 范围：安装 `@tanstack/react-query` 和 `zod`；新增全局 `QueryClientProvider`；新增 `frontend-api` 和 `chat-workspace/api`；保留 `/api/chat` 原生 Web Stream 处理，不强行改为 axios；先迁移工作台知识库、文件、vector health、会话、diagnostics 和 chat response 获取入口。
- 验收标准：
  - `frontend/src/app/page.tsx` 不再直接调用 `fetch`，认证 header、401 清理和错误消息解析集中到共享 API helper。
  - `vector index health` 使用 React Query 管理查询状态，页面继续保持原有刷新和轮询行为。
  - Zod 仅做响应外壳轻量校验，不替代现有 domain adapter 和后端安全校验。
  - `npm run test`、`npm run lint`、`npm run build` 通过。
- 完成记录：
  - 完成日期：2026-06-29
  - 相关 commit：`986a9a3`
  - 新增 `frontend/src/app/providers.tsx`，在 `frontend/src/app/layout.tsx` 接入 `QueryClientProvider`。
  - 新增 `frontend/src/lib/frontend-api.ts`，统一 auth header、登录失效跳转、错误响应解析和 fetch wrapper。
  - 新增 `frontend/src/lib/chat-workspace/api.ts`，集中工作台 domain API，并用 Zod 校验 `files`、`knowledge_bases`、`settings` 等响应外壳。
  - `frontend/src/app/page.tsx` 从约 3498 行降至 2699 行，页面内直接 `fetch` 清零；高频派生数据补充 `useMemo`。
  - `npm run test`、`npm run lint`、`npm run build` 已通过；沙箱内 build 因 Turbopack 进程/端口限制失败后，已在提权环境重跑通过。
- 建议验证命令：

```bash
cd frontend
npm run test
npm run lint
npm run build
```

## T-026 增加聊天回答质量反馈闭环

- 来源计划：`PLAN-20260630-01`
- 优先级：`P1`
- 状态：`Done`
- 背景：当前 RAG 性能、检索 diagnostics、worker 和测试体系已经比较完整，但系统缺少真实用户对回答质量的结构化反馈，后续 prompt、retrieval、rerank 和 eval case 优化缺少稳定输入。
- 目标：在每条 assistant message 下提供轻量反馈入口，并把用户反馈安全持久化，形成“回答 -> 反馈 -> 分析 -> 优化”的最小闭环。
- 范围：
  - 新增 `message_feedback` 表或等价结构，记录 `user_id`、`message_id`、评分、原因、备注和必要上下文。
  - 后端新增创建/更新/查询反馈 API；route 层必须校验 message 所属 conversation 和 user 权限。
  - 前端在 assistant message 下增加赞/踩入口；踩时允许选择原因并填写简短备注。
  - 反馈内容不得包含 API Key、JWT、数据库连接串等敏感信息；后端日志只记录安全摘要。
- 建表 SQL 草案：

```sql
CREATE TABLE IF NOT EXISTS message_feedback (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    message_id BIGINT NOT NULL,
    rating TEXT NOT NULL,
    reason TEXT,
    note TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT message_feedback_rating_check
        CHECK (rating IN ('positive', 'negative')),
    CONSTRAINT message_feedback_reason_check
        CHECK (
            reason IS NULL OR reason IN (
                'irrelevant_sources',
                'missing_answer',
                'hallucination',
                'outdated_or_wrong',
                'too_slow',
                'format_issue',
                'other'
            )
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_message_feedback_user_message
ON message_feedback (user_id, message_id);

CREATE INDEX IF NOT EXISTS idx_message_feedback_user_created
ON message_feedback (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_message_feedback_rating_reason
ON message_feedback (rating, reason, created_at DESC);
```

- 验收标准：
  - 用户只能给自己会话中的 assistant message 反馈，跨用户 message 返回 `404` 或安全错误。
  - 同一用户对同一 message 重复反馈时执行 upsert，不产生多条重复记录。
  - 前端刷新会话后能恢复已提交的反馈状态。
  - 后端测试覆盖正反馈、负反馈、原因校验、跨用户隔离和重复提交更新。
  - 前端测试覆盖按钮状态、提交失败回滚或提示、已反馈状态回显。
- 完成记录：
  - 完成日期：2026-06-30
  - 相关 commit：`e027079`
  - 新增 `POST /chat/messages/{message_id}/feedback`，提交前校验当前用户可访问的 assistant message；同一用户同一消息使用 `message_feedback(user_id, message_id)` 唯一约束 upsert。
  - 历史消息接口返回当前用户的 `feedback` 字段，前端刷新会话后可回显已提交反馈。
  - 前端 assistant message 增加“有用 / 有问题”反馈入口；负反馈支持选择原因和填写备注。
  - 已同步更新 `docs/API.md` 与 `docs/SCHEMAS.md`。
  - 验证命令：`cd backend && conda run -n firstrag python -m unittest tests.test_conversations -v`；`cd backend && conda run -n firstrag python -m compileall app tests/test_conversations.py`；`cd backend && conda run -n firstrag python -m unittest discover tests -v`；`cd frontend && npm run test -- chat-workspace/api.test.ts`；`cd frontend && npm run test`；`cd frontend && npm run lint`；`cd frontend && npm run build`。

## T-027 增强 sources 展示与引用有用性标记

- 来源计划：`PLAN-20260630-01`
- 优先级：`P1`
- 状态：`Done`
- 背景：当前回答已返回 sources 和 retrieval diagnostics，但用户只能被动查看引用，无法标记“哪些引用真的有用”。这会限制后续分析检索失败原因和 rerank 调参。
- 目标：让用户能对回答中的单个 source 标记有用/无关，并在前端更清楚地展示来源文件、chunk、score 和 retrieval 来源。
- 范围：
  - 新增 `message_source_feedback` 表或等价结构，记录 source index、文件、chunk、评分和备注。
  - 后端 API 校验 source index 必须存在于 `messages.sources` 当前数组内，避免伪造不存在的引用。
  - 前端 source 面板展示文件名、chunk index、召回通道、rerank score 等关键信息；每个 source 提供有用/无关标记。
  - 保持现有 SSE sources 协议兼容，不改变 `messages.sources` 已保存结构。
- 建表 SQL 草案：

```sql
CREATE TABLE IF NOT EXISTS message_source_feedback (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    message_id BIGINT NOT NULL,
    source_index INTEGER NOT NULL,
    knowledge_file_id UUID,
    chunk_index INTEGER,
    rating TEXT NOT NULL,
    note TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT message_source_feedback_source_index_check
        CHECK (source_index >= 0),
    CONSTRAINT message_source_feedback_rating_check
        CHECK (rating IN ('useful', 'irrelevant'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_message_source_feedback_unique_source
ON message_source_feedback (user_id, message_id, source_index);

CREATE INDEX IF NOT EXISTS idx_message_source_feedback_file_created
ON message_source_feedback (knowledge_file_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_message_source_feedback_rating_created
ON message_source_feedback (rating, created_at DESC);
```

- 验收标准：
  - 用户只能标记自己 message 中真实存在的 source。
  - source feedback 支持重复提交更新，不产生重复记录。
  - sources 展示不遮挡聊天正文，移动端可折叠。
  - 单测覆盖 source index 越界、跨用户隔离、文件已删除或 source 缺少 file id 的兼容路径。
- 完成记录：
  - 完成日期：2026-06-30
  - 相关 commit：`ce66821`
  - 新增 `POST /chat/messages/{message_id}/sources/{source_index}/feedback`，提交前校验当前用户可访问的 assistant message，并校验 source index 存在于当前 `messages.sources`。
  - 历史消息接口会把当前用户的 source feedback 附加到 `sources[].feedback`，前端刷新后可回显“引用有用 / 引用无关”状态。
  - 前端 sources 卡片补充展示 retrieval source、Vector、Fulltext、Rerank、RRF 等分数，并新增单个 source 有用性标记按钮。
  - 已同步更新 `docs/API.md` 与 `docs/SCHEMAS.md`。
  - 验证命令：`cd backend && conda run -n firstrag python -m unittest tests.test_conversations -v`；`cd backend && conda run -n firstrag python -m compileall app tests/test_conversations.py`；`cd backend && conda run -n firstrag python -m unittest discover tests -v`；`cd frontend && npm run test -- chat-workspace/api.test.ts`；`cd frontend && npm run test`；`cd frontend && npm run lint`；`cd frontend && npm run build`。

## T-028 支持从真实问答沉淀 RAG eval case 草稿

- 来源计划：`PLAN-20260630-01`
- 优先级：`P2`
- 状态：`Done`
- 背景：当前 eval 体系已经可以持续追踪性能和回答结果，但 eval case 主要依赖人工维护。真实差评问题如果不能低成本进入 eval，会反复出现同类退化。
- 目标：支持把一次真实问答和反馈转成 eval case 草稿，作为后续人工审核、补充 expected keywords 和批量评估的输入。
- 范围：
  - 后端提供“导出 eval case 草稿”能力，输入 message id，输出 question、answer、sources、retrieval diagnostics、feedback reason 和建议 expected keywords 占位。
  - 草稿默认写入 `docs/evals/cases/drafts/` 或以 JSON 下载，避免自动污染正式 eval case。
  - 前端仅在开发/管理入口展示“加入 eval 草稿”操作，普通用户默认不可见。
  - 不导出敏感凭据、完整 JWT、API Key 或后端内部连接信息。
- 验收标准：
  - 差评回答可一键生成 eval case 草稿。
  - 草稿包含可复现实验所需的最小上下文，但不包含敏感配置。
  - 生成的 JSON 能被后续脚本读取或容易转换为现有 eval case 格式。
  - 测试覆盖正常导出、跨用户隔离、缺少 retrieval/sources 的兼容路径。
- 完成记录：
  - 完成日期：2026-06-30
  - 相关 commit：`d523917`
  - 新增 `GET /chat/messages/{message_id}/eval-case-draft`，从当前用户 assistant message、上一条 user question、sources、retrieval diagnostics 和 message feedback 生成 eval case 草稿。
  - 草稿顶层字段兼容 `docs/evals/rag_eval_cases.jsonl`，原始 answer、feedback、retrieval 和 sources 放入 `draft_metadata` 供人工审核。
  - 前端在负反馈回答上展示“Eval 草稿”入口，点击后下载 JSON 文件，不自动写入正式 eval case。
  - 已同步更新 `docs/API.md` 与 `docs/SCHEMAS.md`。
  - 验证命令：`cd backend && conda run -n firstrag python -m unittest tests.test_conversations -v`；`cd backend && conda run -n firstrag python -m compileall app tests/test_conversations.py`；`cd backend && conda run -n firstrag python -m unittest discover tests -v`；`cd frontend && npm run test -- chat-workspace/api.test.ts`；`cd frontend && npm run test`；`cd frontend && npm run lint`；`cd frontend && npm run build`。

## T-029 增加回答质量和检索表现看板雏形

- 来源计划：`PLAN-20260630-01`
- 优先级：`P2`
- 状态：`Done`
- 背景：反馈数据落库后，需要一个轻量入口帮助判断当前最该优化的是检索、引用质量、回答生成、性能还是前端展示。
- 目标：提供面向开发和运维的质量看板雏形，汇总最近反馈和检索表现，不追求复杂 BI。
- 范围：
  - 后端新增按用户或知识库聚合的反馈统计接口。
  - 指标包括正/负反馈数、负反馈原因分布、source 无关率、平均首 token、平均 sources、失败知识库/文件排行。
  - 前端增加轻量质量面板，可从工作台或开发入口进入。
  - 统计接口必须遵守 user_id 隔离，禁止跨用户聚合泄露。
- 验收标准：
  - 看板能展示最近 7 天或最近 N 条反馈的核心指标。
  - 空数据状态清晰，不把无反馈误导为质量良好。
  - 后端测试覆盖聚合口径、用户隔离和空数据路径。
  - 前端测试覆盖数据加载、空状态和错误状态。
- 完成记录：
  - 完成日期：2026-06-30
  - 相关 commit：`aa70530`
  - 新增 `GET /chat/quality-dashboard`，按当前用户聚合最近窗口内的 message feedback、source feedback、负反馈原因、source 无关率、平均 sources 和平均首 token 等指标。
  - 前端左侧栏新增“质量看板”入口，支持空状态、刷新、负反馈原因分布和无关引用来源排行。
  - 已同步更新 `docs/API.md` 与 `docs/SCHEMAS.md`。
  - 验证命令：`cd backend && conda run -n firstrag python -m unittest tests.test_conversations -v`；`cd backend && conda run -n firstrag python -m compileall app tests/test_conversations.py`；`cd frontend && npm run test -- chat-workspace/api.test.ts`。

## T-030 增加数据库迁移执行脚本

- 来源计划：`PLAN-20260630-02`
- 优先级：`P1`
- 状态：`Done`
- 背景：当前 `backend/app/db/sql/` 已维护基础建表 SQL 和增量 migration，但新数据库首次运行仍依赖人工按顺序执行 SQL，Docker Compose 和新环境验收存在不确定性。
- 目标：提供一个可重复运行的数据库迁移入口，支持从空库初始化完整表结构，并能跳过已经应用的 migration。
- 范围：
  - 已在项目进入生产环境前完成一次 rebaseline，将当前完整结构整理为 `000_initial_schema.sql`。
  - 新增 `scripts/migrate_db.py` 或等价脚本，默认读取仓库根目录 `.env` 中的 `DATABASE_URL`，同时支持通过环境变量覆盖。
  - 建立轻量 `schema_migrations` 记录表，记录 migration 文件名、checksum、执行时间和执行状态。
  - 按文件编号顺序执行 `backend/app/db/sql/*.sql`，包含 `000_initial_schema.sql` 与后续增量 SQL。
  - 迁移失败时停止执行后续 SQL，输出安全、可读的错误信息，不打印数据库密码、API Key、JWT 或完整 `.env` 内容。
  - 提供 dry-run 或 list 模式，便于查看待执行 migration。
- 验收标准：
  - 空数据库可以通过脚本初始化完整业务表结构。
  - 重复运行脚本不会重复执行已应用 migration。
  - migration 文件内容变化时能检测 checksum 不一致并阻止静默跳过。
  - 测试覆盖 migration 排序、跳过已执行项、checksum mismatch 和失败停止场景。
  - 文档说明本地和 compose 环境下的执行方式。
- 进展记录：
  - 2026-06-30：完成 SQL rebaseline，新增 `000_initial_schema.sql` 和 SQL 目录维护说明；历史增量 SQL 已合并进当前基线，后续结构变化从 `001_xxx.sql` 开始。
- 完成记录：
  - 完成日期：2026-06-30
  - 相关 commit：`5d22e59`
  - 新增 `scripts/migrate_db.py`，支持 `--list`、`--dry-run`、按编号执行 migration、自动维护 `schema_migrations` 和 checksum 校验。
  - 新增 `backend/tests/test_migrate_db_script.py`，覆盖 migration 排序、跳过已执行项、checksum mismatch 和失败停止场景。
  - 已同步更新 `README.md`、`docs/DEPLOYMENT.md`、`docs/SCHEMAS.md` 和 `backend/app/db/sql/README.md`。
  - 已使用一次性 PostgreSQL 空库验证：首次执行应用 `000_initial_schema.sql`，二次 `--dry-run` 返回 skipped，并确认 `schema_migrations` 记录和 13 张业务表。
  - 验证命令：`conda run -n firstrag python scripts/migrate_db.py --list`；`conda run -n firstrag python -m unittest backend.tests.test_migrate_db_script -v`；`conda run -n firstrag python -m compileall scripts/migrate_db.py backend/tests/test_migrate_db_script.py`；`cd backend && conda run -n firstrag python -m unittest discover tests -v`。
- 建议验证命令：

```bash
conda run -n firstrag python scripts/migrate_db.py --dry-run
cd backend
conda run -n firstrag python -m unittest discover tests -v
```

## T-031 接入 Docker Compose 初始化流程

- 来源计划：`PLAN-20260630-02`
- 优先级：`P1`
- 状态：`Done`
- 背景：当前 `docs/DEPLOYMENT.md` 明确说明 compose 不会自动创建业务基础表，新环境需要人工初始化数据库，影响项目可交付性。
- 目标：让 Docker Compose 新环境具备清晰、低摩擦的数据库初始化路径，减少首次启动失败。
- 范围：
  - 基于 `T-030` 的迁移脚本，为 compose 提供一键执行迁移的命令或独立 migration service。
  - 明确 `COMPOSE_DATABASE_URL`、`DATABASE_URL` 与 compose 内 `postgres` service 的关系。
  - 必要时调整 backend Dockerfile，确保容器内包含迁移入口和所需 SQL 文件。
  - 更新 `docker-compose.yml`、`deploy/docker/` 或文档中的启动顺序，避免 backend 在数据库未初始化时产生误导性错误。
  - 保持宿主机本地开发流程兼容，不强制所有用户使用 Docker。
- 验收标准：
  - 新 compose 数据卷场景下，可以按文档完成数据库初始化、后端启动、前端访问和 worker 启动。
  - 重复执行初始化命令不会破坏已有数据。
  - `docs/DEPLOYMENT.md` 不再停留在“当前 compose 不会自动创建业务基础表”的未解决描述，而是给出明确流程。
  - 不把数据库密码、JWT、API Key 等敏感值写入日志或提交到仓库。
- 完成记录：
  - 完成日期：2026-06-30
  - 相关 commit：`5d22e59`
  - `docker-compose.yml` 新增 `migrate` service，复用 backend 镜像执行 `/app/scripts/migrate_db.py`。
  - backend 和 worker 会等待 `postgres` 健康检查通过、`migrate` 成功退出后再启动。
  - backend Dockerfile 已复制 `scripts/migrate_db.py` 到容器内，迁移脚本可访问 `/app/backend/app/db/sql/` 中的 SQL 文件。
  - 已同步更新 `README.md` 与 `docs/DEPLOYMENT.md`，说明 `COMPOSE_DATABASE_URL`、`DATABASE_URL`、自动迁移和手动 dry-run 命令。
  - 验证命令：`docker compose config --quiet`；`conda run -n firstrag python -m unittest backend.tests.test_migrate_db_script -v`；`conda run -n firstrag python -m compileall scripts/migrate_db.py backend/tests/test_migrate_db_script.py`。
- 建议验证命令：

```bash
docker compose config --quiet
docker compose run --rm migrate python /app/scripts/migrate_db.py --dry-run
```

## T-032 增加 GitHub Actions CI

- 来源计划：`PLAN-20260630-02`
- 优先级：`P1`
- 状态：`Done`
- 背景：本地已经有 `scripts/acceptance_check.sh` 和前后端测试命令，但仓库缺少自动 CI，协作时容易漏跑检查。
- 目标：为 pull request 和主分支 push 增加基础 CI，覆盖后端语法/单测、前端 lint/test/build 和文档/脚本可执行性检查。
- 范围：
  - 新增 `.github/workflows/ci.yml`。
  - 后端 job 使用 Python 环境安装 `backend/requirements.txt`，运行 `python -m compileall app` 与测试集。
  - 前端 job 使用 Node 环境安装依赖，运行 `npm run lint`、`npm run test`、`npm run build`。
  - 如果真实 RAG eval 依赖外部 API Key，则默认不在 CI 中执行，只保留手动 workflow 或文档说明。
  - 缓存 pip/npm 依赖，控制 CI 耗时。
- 验收标准：
  - PR 和 main push 会触发 CI。
  - CI 不依赖本地 `.env`、外部 LLM API Key 或真实数据库服务即可完成静态检查。
  - 失败日志能明确定位后端、前端或构建阶段。
  - README 或文档补充 CI 覆盖范围说明。
- 完成记录：
  - 完成日期：2026-06-30
  - 相关 commit：`da990bd`
  - 新增 `.github/workflows/ci.yml`，在 pull request、`main` push 和手动触发时运行。
  - 后端 job 安装 `backend/requirements.txt`，运行 `compileall`、`unittest`、migration 文件列表检查和 Docker Compose 配置检查。
  - 前端 job 使用 Node.js 22 和 `npm ci`，运行 lint、Vitest 和 Next build。
  - 默认 CI 不运行真实 RAG eval 或 indexing eval，避免依赖真实账号、模型 API Key、数据库和后端服务。
  - 已同步更新 `README.md` 与 `docs/DEPLOYMENT.md`。
  - 验证命令：`ruby -e 'require "yaml"; YAML.load_file(".github/workflows/ci.yml"); puts "workflow yaml ok"'`；`docker compose config --quiet`；`conda run -n firstrag python -m unittest backend.tests.test_migrate_db_script -v`；`scripts/acceptance_check.sh --skip-real-eval` 已通过 backend、frontend lint 和 frontend test，frontend build 在沙箱中因 Turbopack 端口绑定限制失败；`cd frontend && npm run build` 提升权限后通过。
- 建议验证命令：

```bash
scripts/acceptance_check.sh --skip-real-eval
```

## T-033 强化本地验收脚本为发布前检查入口

- 来源计划：`PLAN-20260630-02`
- 优先级：`P2`
- 状态：`Done`
- 背景：`scripts/acceptance_check.sh` 已覆盖静态验收和可选真实 eval，但随着迁移脚本、CI 和反馈看板增加，需要把本地验收入口继续整理得更适合发布前使用。
- 目标：让开发者可以用一个入口完成发布前核心检查，并能按场景跳过外部依赖或耗时阶段。
- 范围：
  - 在 `acceptance_check.sh` 中接入 migration dry-run、后端 compileall、后端测试、前端 lint/test/build 和可选 eval。
  - 保留 `--skip-real-eval`、`--skip-frontend-tests`、`--skip-frontend-build` 等轻量开关，必要时增加 `--skip-migration-check`。
  - 汇总每个阶段的开始、成功和失败提示，降低排错成本。
  - 不在脚本中打印 `.env` 内容或敏感环境变量。
- 验收标准：
  - 默认静态验收路径能在无外部 API Key 的环境下运行。
  - 发布前完整路径可以显式开启真实 RAG eval 和 indexing eval。
  - 某一阶段失败时脚本返回非零退出码，并保留足够清晰的阶段名称。
  - `docs/DEPLOYMENT.md` 或 `docs/README.md` 更新本地验收说明。
- 完成记录：
  - 完成日期：2026-06-30
  - 相关 commit：`4a03381`
  - `scripts/acceptance_check.sh` 新增 migration check、后端 compileall 和阶段通过提示。
  - migration check 默认运行 `scripts/migrate_db.py --list`；存在 `DATABASE_URL` 或 `COMPOSE_DATABASE_URL` 时额外运行 `--dry-run`；可通过 `FIRSTRAG_REQUIRE_MIGRATION_DRY_RUN=1` 强制要求数据库 dry-run。
  - 新增 `--skip-migration-check`、`FIRSTRAG_SKIP_BACKEND_COMPILE` 等跳过开关，保留原有 `--skip-real-eval`、`--skip-frontend-tests` 和 `--skip-frontend-build`。
  - 已同步更新 `docs/DEPLOYMENT.md` 的本地验收说明。
  - 验证命令：`scripts/acceptance_check.sh --help`；`scripts/acceptance_check.sh --skip-real-eval --skip-frontend-build`；`cd frontend && npm run build`。
- 建议验证命令：

```bash
scripts/acceptance_check.sh --skip-real-eval
scripts/acceptance_check.sh --help
```

## T-034 补充 README 截图和演示说明

- 来源计划：`PLAN-20260630-02`
- 优先级：`P2`
- 状态：`Done`
- 背景：README 当前“项目截图”仍标注暂未提供，外部读者难以快速理解聊天工作台、知识库管理、模型设置和质量看板的实际体验。
- 目标：补齐项目可展示材料，让 README 能清楚呈现 FirstRAG 的核心界面和推荐试用路径。
- 范围：
  - 准备聊天工作台、知识库文件管理、模型设置、任务队列和质量看板的截图。
  - 在 README 中补充截图、功能说明和最短试用路径。
  - 如截图包含本地数据，需避免展示真实 API Key、JWT、数据库密码、私人文档内容或敏感用户信息。
  - 必要时新增 `docs/assets/` 或等价目录管理图片资源。
- 验收标准：
  - README 首屏之后能看到至少一张真实产品截图或明确的界面预览。
  - 截图与当前 UI 一致，不展示未实现功能。
  - 文档说明如何启动最小演示链路，包括后端、前端和 worker。
  - 图片资源命名清晰，体积可控，不影响仓库可维护性。
- 完成记录：
  - 完成日期：2026-06-30
  - 相关 commit：`a0bccfa`
  - 新增 `docs/assets/firstrag-workspace-dashboard.png`、`docs/assets/firstrag-files-queue.png`、`docs/assets/firstrag-model-settings.png`，使用当前前端 UI 与脱敏演示数据生成。
  - README “项目截图”已覆盖聊天工作台、质量看板、知识库文件管理、任务队列和模型设置。
  - README 新增“最短演示路径”，说明数据库迁移、后端、前端和 vector index worker 的本地启动顺序，以及注册、模型设置、上传文件、向量化、提问和反馈看板的试用流程。
  - 已确认截图不包含真实 API Key、JWT、数据库密码或私人文档内容。
- 建议验证命令：

```bash
git status --short
```

## T-035 跑一次真实 RAG eval 与 indexing eval 基线

- 来源计划：`PLAN-20260630-02`
- 优先级：`P2`
- 状态：`Done`
- 背景：前几批任务已经补强 RAG 性能、反馈闭环和质量看板，但工程化收口后需要重新记录一次真实链路质量与性能基线。
- 目标：在迁移、compose 和 CI 补强后，运行真实 RAG eval 与 indexing eval，形成发布前可比较基线。
- 范围：
  - 使用现有 `scripts/eval_rag.py`、`scripts/eval_indexing.py` 和 `scripts/eval_summary.py`。
  - 记录通过率、平均耗时、首 token、平均 sources、缓存命中、检索阶段耗时和 indexing 成功情况。
  - 若真实 API Key 或外部服务不可用，记录阻塞原因，不伪造结果。
  - 更新 `docs/evals/latest_summary.md` 或相关报告生成流程，不提交包含敏感信息的运行输出。
- 验收标准：
  - 至少完成一次真实 RAG eval 和一次 indexing eval，或明确记录外部依赖阻塞原因。
  - eval summary 能生成并展示最近运行趋势。
  - 若发现明显回归，新增后续任务或直接修复。
  - 报告不包含 API Key、JWT、数据库密码或用户私密文档内容。
- 阻塞记录：
  - 记录日期：2026-06-30
  - 相关 commit：`13eb1ff`
  - 本次 preflight 未能运行真实 RAG eval 与 indexing eval：`http://127.0.0.1:8000/docs` 不可访问，且当前 shell 未设置 `FIRSTRAG_EVAL_USERNAME` / `FIRSTRAG_EVAL_PASSWORD`。
  - 已运行 `conda run -n firstrag python scripts/eval_summary.py`，本地历史摘要生成成功：RAG 历史 25 次，Indexing 历史 2 次。
  - 最近 RAG 历史记录：2026-06-30T08:57:03，10/10 通过，通过率 1.00，平均引用 2.20，平均首 token 3715.19ms，平均耗时 5.96s，门禁通过。
  - 最近 Indexing 历史记录：2026-06-28T08:40:37，通过，job 状态 `succeeded`，聊天耗时 3.51s，引用数 1，清理关联完成。
  - 解除阻塞条件：运行 `docker compose up -d --build` 启动完整链路并完成 migration，在当前 shell 设置 eval 测试账号密码；账号还需要可用的 LLM provider / API Key。
  - 解除后建议运行：`FIRSTRAG_EVAL_USERNAME=... FIRSTRAG_EVAL_PASSWORD=... scripts/acceptance_check.sh`，或分别运行 `scripts/rag_eval_gate.sh` 与 `conda run -n firstrag python scripts/eval_indexing.py --base-url http://127.0.0.1:8000`。
- 完成记录：
  - 完成日期：2026-06-30
  - 相关 commit：`ee845e3`
  - 真实 RAG eval gate 已完成：10/10 case 通过，通过率 1.00，平均引用 2.20，平均首 token 3613.84ms，平均耗时 6.50s，平均 token 951.00，质量门禁全部 PASS。
  - RAG 阶段耗时：settings 1716.02ms，profile 0.62ms，router 249.03ms，retrieve 1498.01ms，hybrid 1685.39ms，rerank 1475.41ms；knowledge profile 缓存命中 8/8，retrieval settings 缓存命中 2/9。
  - 真实 indexing eval 已完成：临时 Markdown 上传成功，auto index job `succeeded`，文件状态 `indexed`，聊天检索命中临时文件，聊天耗时 7.20s，展示引用 1，清理关联完成。
  - 已运行 `conda run -n firstrag python scripts/eval_summary.py`，本地趋势摘要刷新为 RAG 历史 26 次、Indexing 历史 3 次。
  - `docs/evals/README.md` 已更新为 2026-06-30 真实链路 eval 基线；latest report 和 runs JSON 仍由 `.gitignore` 忽略，不提交原始运行输出。
  - 趋势摘要显示旧 `settings` 阶段最新均值 1716.02ms，超过 1000ms 建议阈值；后续 `T-036` 已确认该字段是 settings-wait 观测口径，真实 `settings-load` 为 6.40ms。
- 建议验证命令：

```bash
scripts/acceptance_check.sh
conda run -n firstrag python scripts/eval_summary.py
```

## T-036 调查 RAG settings 阶段耗时超阈值

- 来源计划：`PLAN-20260630-02`
- 优先级：`P2`
- 状态：`Done`
- 背景：T-035 的 2026-06-30 真实 RAG eval 质量门禁通过，但趋势摘要显示 `settings` 阶段最新均值 1716.02ms，高于 1000ms 建议阈值；报告中的 settings load/query 子阶段只有个位数毫秒，需要确认指标口径或真实耗时来源。
- 目标：判断 `settings` 阶段超阈值是 instrumentation 口径问题、阶段归因问题、数据库/缓存波动，还是实际性能回退，并给出修复或阈值调整建议。
- 范围：
  - 对比 `scripts/eval_rag.py`、`backend/app/services/rag_service.py` 和 retrieval settings cache diagnostics 的耗时字段来源。
  - 抽查 latest RAG history JSON 中 settings、settings_load、settings_query、settings_normalize 与 retrieval settings cache hit 字段。
  - 必要时补充更细粒度指标或修正 summary/report 字段命名。
  - 不改动 RAG 行为，除非定位到明确 bug。
- 验收标准：
  - 能解释 settings 1716.02ms 与 load/query 子阶段个位数毫秒之间的差异。
  - 若是指标口径问题，报告字段命名或计算逻辑已修正并有测试覆盖。
  - 若是实际性能问题，新增优化任务或完成对应修复。
  - 重新生成 eval summary 后，文档记录结论。
- 完成记录：
  - 完成日期：2026-06-30
  - 相关 commit：`72f2780`
  - 结论：`retrieval_settings_ms` 来自 `backend/app/services/rag/streaming.py` 的 RAG stage chunk 间隔计时，表示 LCEL streaming 外层 settings-wait；`retrieval_settings_load_total_ms`、`retrieval_settings_query_ms` 和 `retrieval_settings_normalize_ms` 来自 `backend/app/services/rag/retrieval_pipeline.py` 的真实 settings 读取、缓存命中检查和 normalize 子阶段。
  - 最新真实历史记录中 `settings-wait=1716.02ms`，但 `settings-load=6.40ms`、`settings-query=6.37ms`、`settings-normalize=0.01ms`，因此没有发现数据库 settings 读取或缓存层的真实性能回退。
  - `scripts/eval_rag.py` 已把建议性能门槛从旧 `settings` 外层间隔改为 `settings-load`，报告中保留旧字段但改名为 `settings-wait`。
  - `scripts/eval_summary.py` 已把 RAG 阶段趋势阈值改为 `settings-load`，重新生成后最新均值 6.40ms，状态为通过。
  - 已补充 `backend/tests/test_eval_rag_script.py` 与 `backend/tests/test_eval_summary_script.py` 覆盖新字段命名和阈值口径。
  - 验证命令：`conda run -n firstrag python scripts/eval_summary.py`；`cd backend && conda run -n firstrag python -m unittest tests.test_eval_rag_script tests.test_eval_summary_script -v`。
- 建议验证命令：

```bash
conda run -n firstrag python scripts/eval_summary.py
cd backend && conda run -n firstrag python -m unittest tests.test_eval_rag_script tests.test_eval_summary_script -v
```

## T-037 文档与任务台账状态收口

- 来源计划：`PLAN-20260701-01`
- 优先级：`P1`
- 状态：`Done`
- 背景：当前核心实现、CI、迁移和 eval 工具链已经比较完整，但部分文档状态和真实进展不一致，容易影响后续排期判断。
- 目标：让 README、任务台账和专题文档准确反映当前项目状态，进入下一轮开发前先把信息源收齐。
- 范围：
  - 修正 `docs/TASKS.md` 中计划批次和任务详情的状态不一致，例如 `PLAN-20260629-01`、`T-029`。
  - 对齐 `README.md` Roadmap 与已完成的 RAG eval、批量评估脚本、CI 和演示说明。
  - 整理 `backend/README.md` 的早期 demo 说明，避免和当前全栈架构说明冲突。
  - 检查 `docs/README.md`、`docs/DEPLOYMENT.md`、`docs/evals/README.md` 是否仍有过期描述。
- 验收标准：
  - `docs/TASKS.md` 中已完成任务和计划批次状态一致。
  - README Roadmap 不再把已实现能力标为未完成。
  - 后端旧 demo 文档明确其历史定位，读者不会误以为它是当前主入口。
  - 文档不声明尚未实现的能力，也不包含 API Key、JWT、数据库密码等敏感信息。
- 建议验证命令：

```bash
rg -n "Todo|Doing|Blocked|待补充|暂未|未实现" README.md docs backend/README.md
git status --short
```
- 完成记录：
  - 完成日期：2026-07-01
  - 相关 commit：`f3ab533`
  - `PLAN-20260629-01` 已从 `Doing` 对齐为 `Done`；`T-029` 详情状态已从 `Todo` 对齐为 `Done`。
  - README Roadmap 已把 RAG 评估集、批量评估脚本和历史趋势摘要标记为已完成。
  - `backend/README.md` 已明确当前 FastAPI 后端主入口，并将原脚本说明定位为早期 demo。
  - `docs/evals/README.md` 已同步 `scripts/acceptance_check.sh` 的当前检查步骤。
  - 验证命令：`rg -n "Todo|Doing|Blocked|待补充|暂未|未实现" README.md docs backend/README.md`；`git diff --check -- README.md backend/README.md docs/TASKS.md docs/evals/README.md`。

## T-038 继续拆分前端聊天工作台 hooks

- 来源计划：`PLAN-20260701-01`
- 优先级：`P1`
- 状态：`Done`
- 背景：`frontend/src/app/page.tsx` 已完成多轮组件和请求层拆分，但仍保留大量页面级 `useState`、`useEffect`、轮询和反馈状态，后续改会话、文件管理、质量看板时审查成本仍偏高。
- 目标：在保持现有 UI 和接口协议不变的前提下，把工作台状态编排继续拆到可测试 hook 和纯函数中。
- 范围：
  - 优先抽取 `useConversations`、`useKnowledgeFiles`、`useVectorJobs`、`useFeedback`、`useQualityDashboard` 或同等边界。
  - 保留 `frontend/src/lib/chat-workspace/api.ts` 的集中请求入口，不重新引入页面内直接 `fetch`。
  - 轮询、卸载清理、SSE 消息合并和反馈提交失败路径需要保持现有行为。
  - 不在本任务中做大规模视觉改版。
- 验收标准：
  - `frontend/src/app/page.tsx` 行数和状态分支明显下降，顶层页面更接近布局和编排职责。
  - 新增 hook 或工具函数有针对性单元测试覆盖。
  - `npm run test`、`npm run lint`、`npm run build` 通过。
  - 主要聊天、文件上传、向量化、feedback、quality dashboard 和 diagnostics 行为保持兼容。
- 建议验证命令：

```bash
cd frontend
npm run test
npm run lint
npm run build
```
- 完成记录：
  - 完成日期：2026-07-01
  - 相关 commit：`e984977`
  - 新增 `frontend/src/lib/chat-workspace/use-knowledge-files.ts`，集中管理知识库文件、可复用文件、向量化任务队列、worker health 查询、上传、关联、解除关联、删除向量和轮询刷新逻辑。
  - `frontend/src/app/page.tsx` 从 3373 行降至 2898 行，文件管理和向量化状态从页面级状态容器中移出。
  - 新增 `frontend/src/lib/chat-workspace/use-knowledge-files.test.ts`，覆盖文件合并、知识库文件关联替换和向量化队列合并 helper。
  - 验证命令：`cd frontend && npm run test -- use-knowledge-files.test.ts`；`cd frontend && npm run test`；`cd frontend && npm run lint`；`cd frontend && npm run build`。
  - 备注：`npm run build` 在沙箱内仍会触发 Turbopack 创建进程/绑定端口权限错误；已按权限流程在非沙箱环境重跑并通过。

## T-039 跑一轮发布前真实链路验收

- 来源计划：`PLAN-20260701-01`
- 优先级：`P1`
- 状态：`Done`
- 背景：最近一次真实 RAG eval 和 indexing eval 基线记录在 2026-06-30；发布、演示或大改前需要刷新真实链路结果，而不仅依赖静态测试。
- 目标：启动真实 backend、frontend、vector index worker 和数据库后，跑完整发布前验收并记录结果。
- 范围：
  - 运行 `scripts/acceptance_check.sh` 的完整路径，包含 migration check、后端检查、前端检查、RAG eval gate 和 indexing eval。
  - 若外部 API Key、账号、数据库或 worker 不可用，记录明确阻塞原因，不伪造结果。
  - 重新生成 eval summary，并把不含敏感信息的摘要同步到 `docs/evals/README.md` 或任务完成记录。
- 验收标准：
  - 静态检查全部通过。
  - 真实 RAG eval gate 通过，或记录可复现的阻塞条件。
  - 真实 indexing eval 通过，或记录可复现的阻塞条件。
  - 运行输出和文档不包含 API Key、JWT、数据库密码或私人文档内容。
- 建议验证命令：

```bash
FIRSTRAG_EVAL_USERNAME=你的用户名 \
FIRSTRAG_EVAL_PASSWORD=你的密码 \
scripts/acceptance_check.sh

conda run -n firstrag python scripts/eval_summary.py
```
- 完成记录：
  - 完成日期：2026-07-01
  - 相关 commit：`23e32e5`
  - 前置检查：本机已有 backend `127.0.0.1:8000`、frontend `:3000`、PostgreSQL `127.0.0.1:5432` 监听；本轮账号凭据仅作为命令环境变量传入验收脚本，未写入文件或文档。
  - `FIRSTRAG_EVAL_USERNAME=... FIRSTRAG_EVAL_PASSWORD=... scripts/acceptance_check.sh` 已完整通过：migration 文件检查、后端 compileall、后端 121 个 unittest、前端 lint、Vitest 41 个用例、Next build、RAG eval gate 和 indexing eval 均通过。
  - migration check 因当前 shell 未设置 `DATABASE_URL` / `COMPOSE_DATABASE_URL`，只检查 migration 文件列表并跳过数据库 dry-run。
  - RAG eval gate：10/10 case 通过，通过率 1.00，平均引用 2.40，平均首 token 3439.74ms，平均耗时 5.98s，质量门禁全部 PASS；历史记录 `docs/evals/runs/20260701_104535.json`。
  - Indexing eval：上传、auto index、worker 完成、文件 indexed、聊天 Sources 命中新文件均通过；job `05e00833-fc27-4fe3-bcda-ca553ce350e6` 状态 `succeeded`，聊天耗时 6.86s，引用数 1；历史记录 `docs/evals/indexing_runs/20260701_104644.json`。
  - 已运行 `conda run -n firstrag python scripts/eval_summary.py`，趋势摘要刷新为 RAG 历史 27 次、Indexing 历史 4 次；报告仍由 `.gitignore` 忽略。
  - `docs/evals/README.md` 已更新 2026-07-01 真实链路 eval 基线摘要，不包含 API Key、JWT、数据库密码或账号密码。

## T-040 明确 License 与公开发布说明

- 来源计划：`PLAN-20260701-01`
- 优先级：`P2`
- 状态：`Done`
- 背景：`README.md` 目前仍写着 License 暂未声明；如果仓库要公开展示、部署在线 demo 或接受协作，需要明确授权边界。
- 目标：根据项目用途选择合适的 License，并在 README 和必要文档中说明公开发布边界。
- 范围：
  - 由项目所有者确认 License 类型，例如 MIT、Apache-2.0、GPL 系列或暂不授权。
  - 新增或更新 `LICENSE` 文件。
  - 更新 `README.md` 的 License 段落。
  - 如暂不公开授权，需要在 README 中写清楚当前状态，避免误导外部使用者。
- 验收标准：
  - 仓库根目录存在清晰的 License 声明或明确的暂不授权说明。
  - README 不再停留在“待补充”。
  - 不引入与依赖许可证明显冲突的声明。
- 建议验证命令：

```bash
git status --short
```
- 完成记录：
  - 完成日期：2026-07-01
  - 相关 commit：`c885659`
  - 根目录新增 `LICENSE`，当前授权边界明确为 all rights reserved / 暂不开放开源授权。
  - `README.md` 的 License 段落已替换为“暂不开放开源授权”说明，并链接到 `LICENSE`，不再保留“待补充”占位文案。
  - 本次未引入新的运行时依赖；授权声明为限制性公开说明，不与现有第三方依赖许可证形成明显冲突。
  - 验证命令：`rg -n "License|授权|待补充|暂未声明|All rights reserved" README.md LICENSE docs/TASKS.md`；`git diff --check -- README.md LICENSE docs/TASKS.md`；`git status --short`。

## T-041 梳理在线演示环境方案

- 来源计划：`PLAN-20260701-01`
- 优先级：`P2`
- 状态：`Done`
- 背景：README Roadmap 仍保留“发布在线演示环境”未完成项；当前 Docker Compose、迁移和 CI 已具备基础，但在线 demo 还需要明确资源、账号和安全边界。
- 目标：形成可执行的在线演示环境方案，必要时完成最小可用部署。
- 范围：
  - 选择部署目标，例如云服务器、Render、Railway、Fly.io、Vercel + 独立 backend 或自托管 Docker Compose。
  - 明确 PostgreSQL、uploads、vector_db、models 和日志的持久化策略。
  - 明确演示账号、用户上传限制、API Key 策略、速率限制和清理策略。
  - 更新 `docs/DEPLOYMENT.md` 和 README Roadmap。
- 验收标准：
  - 有明确的在线 demo 拓扑、配置清单和启动步骤。
  - 不在仓库中提交真实 API Key、JWT、数据库密码或 SSH 私钥。
  - 若完成部署，README 提供可访问地址和演示限制说明；若未部署，文档说明剩余阻塞项。
- 建议验证命令：

```bash
docker compose config --quiet
```
- 完成记录：
  - 完成日期：2026-07-01
  - 相关 commit：`0474178`
  - `docs/DEPLOYMENT.md` 新增在线演示环境方案，选择“单台云服务器 / VPS + Docker Compose + HTTPS 反向代理”作为第一阶段目标。
  - 已明确拓扑、资源规格、PostgreSQL / uploads / vector_db / models / 日志持久化策略、配置清单、演示账号边界、API Key 策略、上传限制、反向代理限流和数据清理策略。
  - `README.md` Roadmap 已新增“明确在线演示环境方案与上线阻塞项”为完成项；真实在线 demo 仍保持未完成，并列明域名/TLS、限流、演示账号和清理策略等剩余条件。
  - `.env.example` 补充了公开 demo 的非敏感端口绑定和上传大小示例，没有提交真实 API Key、JWT、数据库密码或 SSH 私钥。
  - `PLAN-20260701-01` 已随 T-041 完成收口为 `Done`。
  - 验证命令：`docker compose config --quiet`；`env FRONTEND_PORT=127.0.0.1:3000 BACKEND_PORT=127.0.0.1:8000 POSTGRES_PORT=127.0.0.1:5432 docker compose config --quiet`；`git diff --check -- README.md docs/DEPLOYMENT.md .env.example docs/TASKS.md`；`git status --short`。

## T-042 建立生产部署安全与数据持久化方案

- 来源计划：`PLAN-20260701-02`
- 优先级：`P0`
- 状态：`Done`
- 背景：当前项目已具备 Docker Compose、migration、uploads、vector_db 和 Chroma 目录，但正式生产上线前需要明确密钥管理、备份、持久化和恢复策略，避免依赖人工操作或本机临时目录。
- 目标：形成可执行的生产部署安全与数据持久化方案，并把关键检查项固化到启动或验收流程中。
- 范围：
  - 梳理生产 `.env`、JWT secret、数据库密码、LLM API Key、用户 API Key 加密密钥的管理方式。
  - 明确 PostgreSQL 备份和恢复流程，包括备份频率、保留周期、恢复演练步骤。
  - 明确 `uploads/`、`vector_db/`、Chroma 数据、模型缓存和日志目录的持久化挂载策略。
  - 确认 migration 在生产启动流程中稳定执行，避免依赖手工 SQL。
  - 更新 `docs/DEPLOYMENT.md`、`.env.example` 或必要的运维说明。
- 验收标准：
  - 生产部署文档明确哪些配置必须通过 secret / 环境变量注入，仓库不包含真实密钥。
  - 有 PostgreSQL 备份、恢复和验证步骤。
  - 有 uploads、vector_db、Chroma 数据目录的持久化和迁移说明。
  - migration 可通过脚本或部署流程自动执行，失败时能停止后续服务启动。
- 建议验证命令：

```bash
conda run -n firstrag python scripts/migrate_db.py --dry-run
docker compose config --quiet
rg -n "API_KEY|JWT|PASSWORD|SECRET|DATABASE_URL" README.md docs .env.example
```

- 完成记录：
  - 完成日期：2026-07-01
  - 相关 commit：`1821713`
  - 新增 `scripts/production_preflight.py` 与对应单元测试，生产上线前可检查 secret 占位值、端口绑定、持久化目录、Docker Compose 配置和 migration dry-run；脚本不输出真实 secret。
  - `docker-compose.yml` 改为根据 `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` 构造内部连接串，避免修改数据库密码后 backend / worker 仍使用旧默认密码；同时支持 `UPLOADS_DIR`、`VECTOR_DB_DIR`、`MODELS_DIR` 和 Docker 日志轮转配置。
  - `docs/DEPLOYMENT.md` 新增生产安全与数据持久化 runbook，覆盖 secret 管理、PostgreSQL 备份频率、恢复步骤、恢复验证、uploads / vector_db / models 持久化和迁移说明。
  - `.env.example` 补充生产目录、日志轮转和 compose 数据库连接说明；`.gitignore` 忽略 `/backups/`，避免本地备份误提交。
  - `README.md` Roadmap 已新增生产部署安全、备份恢复和持久化 preflight 完成项。

## T-043 强化文件上传、向量化任务和 worker 异常状态体验

- 来源计划：`PLAN-20260701-02`
- 优先级：`P1`
- 状态：`Done`
- 背景：当前已经有 vector worker health、任务队列和 failure recovery，但普通用户在文件过大、坏文件、空文档、重复文件、worker 未启动或 Chroma 异常时仍可能不知道下一步该做什么。
- 目标：让上传和向量化链路在失败、卡住和可恢复场景下给出清晰状态、原因和操作建议。
- 范围：
  - 梳理文件上传失败、解析失败、空文档、重复文件、向量化失败、worker 未启动、任务卡住、Chroma 异常的前后端提示。
  - 前端文件管理面板展示更明确的状态、失败原因、恢复动作和重试入口。
  - 后端继续复用 failure type / hint，不把内部异常或敏感路径直接暴露给用户。
  - 补充边界测试和必要的用户侧文案。
- 验收标准：
  - 常见上传和向量化失败场景均有用户可理解的提示。
  - worker 未启动或任务长时间排队时，前端有明显提醒。
  - 重试、删除向量、解除文件关联等操作路径清晰。
  - 后端日志保留详细错误，前端不展示敏感路径、API Key、数据库信息。
- 建议验证命令：

```bash
cd backend
conda run -n firstrag python -m pytest tests/test_knowledge_files.py tests/test_vector_indexes.py tests/test_vector_index_failure_recovery.py

cd ../frontend
npm run test
npm run lint
```

- 完成记录：
  - 完成日期：2026-07-01
  - 相关 commit：`6b3b606`
  - 后端向量化任务响应改为返回安全错误摘要，`failure_type` / `failure_hint` / `can_retry` 继续保留恢复协议，详细异常只保留在后端日志中，避免前端展示路径、API Key 或数据库连接信息。
  - 删除向量失败时返回安全文案，并在后端日志记录完整异常，避免把 Chroma 路径或底层异常透传给用户。
  - 前端文件管理弹窗补齐上传复用/重复关联提示、413/不支持类型的用户动作建议、empty document / unsupported file type 恢复动作、stale worker 单文件提示、失败任务重试入口和清理残留向量入口。
  - 任务队列面板会继续刷新活跃任务状态，单文件向量化不再只停留在初始排队状态。
  - `docs/API.md` 已说明 `error_message` 是安全摘要，前端应优先使用 `failure_type`、`failure_hint`、`worker_hint` 和 `can_retry` 展示恢复动作。
  - 验证命令：`cd backend && conda run -n firstrag python -m compileall app tests/test_knowledge_files.py tests/test_vector_indexes.py tests/test_vector_index_failure_recovery.py`；`cd backend && conda run -n firstrag python -m pytest tests/test_knowledge_files.py tests/test_vector_indexes.py tests/test_vector_index_failure_recovery.py`；`cd frontend && npm run test`；`cd frontend && npm run lint`。

## T-044 补齐认证、限流、配额和用户 API Key 风控

- 来源计划：`PLAN-20260701-02`
- 优先级：`P0`
- 状态：`Done`
- 背景：当前认证和用户模型设置已经可用，但正式公开环境还需要登录失败保护、API rate limit、上传配额和更严格的用户 API Key 安全边界。
- 目标：降低暴力登录、接口滥用、大文件滥用和用户 API Key 泄露风险。
- 范围：
  - 梳理 JWT 过期、刷新或重新登录策略，确认前端跳转和后端 401 行为一致。
  - 增加登录失败限流和关键 API rate limit 方案，优先覆盖登录、上传、chat、向量化提交、模型测试。
  - 增加用户上传容量、文件数量或单文件大小配额策略。
  - 复核用户自带 API Key 的存储、加密、日志和错误返回路径，确保不落浏览器持久化、不出现在日志或错误提示中。
  - 补充安全回归测试。
- 验收标准：
  - 登录失败和高频请求有可配置限流。
  - 上传和向量化入口有明确配额限制与用户提示。
  - 用户 API Key 不写入 `localStorage`、`sessionStorage`、URL、日志或错误响应。
  - 后端测试覆盖限流、配额和 API Key 脱敏路径。
- 建议验证命令：

```bash
cd backend
conda run -n firstrag python -m pytest tests/test_user_settings.py tests/test_chat_settings.py tests/test_knowledge_files.py

cd ../frontend
npm run test
npm run lint
```

- 完成记录：
  - 完成日期：2026-07-01
  - 相关 commit：`2a27a13`
  - 新增进程内 sliding-window rate limiter，覆盖登录失败、聊天、上传、向量化提交、模型连接测试和厂商模型列表请求；超限统一返回 `429` 和 `Retry-After`。
  - 上传入口新增用户未删除文件数量与总容量配额，继续保留单文件大小限制；重复内容复用已有文件，不重复计入用户全局容量。
  - 知识库批量向量化新增 `VECTOR_INDEX_MAX_BATCH_FILES` 单次提交上限，避免一次性提交过多 vector index job。
  - 用户 API Key 错误响应新增脱敏工具，避免提交值、`api_key=...` 或 Bearer token 形态文本回显；前端文档确认 API Key 只保留在设置页内存状态，不进入浏览器持久化存储。
  - `.env.example`、`docs/API.md`、`docs/DEPLOYMENT.md`、`docs/FRONTEND.md` 和用户设置协议文档已补充限流、配额和 API Key 安全边界。
  - 验证命令：`cd backend && conda run -n firstrag python -m compileall app`；`cd backend && conda run -n firstrag python -m pytest tests`；`cd frontend && npm run test`；`cd frontend && npm run lint`。

## T-045 建立统一日志、错误定位和基础监控指标

- 来源计划：`PLAN-20260701-02`
- 优先级：`P1`
- 状态：`Done`
- 背景：当前 diagnostics 已能帮助定位 RAG 检索阶段，但生产运维还需要统一日志、错误归因和基础指标，知道失败发生在 LLM、embedding、Chroma、PostgreSQL、rerank、worker 还是前端代理。
- 目标：建立最小可用可观测性，让线上错误能被定位、聚合和告警。
- 范围：
  - 统一后端结构化日志字段，例如 request_id、user_id、conversation_id、knowledge_base_id、message_id、job_id、阶段耗时和错误类型。
  - 梳理 chat streaming、vector worker、embedding、Chroma、PostgreSQL、rerank、LLM provider 的错误分类。
  - 增加基础监控指标方案：接口错误率、向量化队列长度、任务失败率、平均首 token 时间、模型调用失败率、worker 最近活动时间。
  - 更新 deployment 文档，说明日志采集和最小监控面板建议。
- 验收标准：
  - 关键后端路径有统一日志字段，且不输出 API Key、JWT、数据库密码。
  - 质量看板或运维文档能说明如何查看队列、失败率和首 token 时间。
  - worker、chat、retrieval、LLM 调用失败能区分主要失败来源。
  - 有针对日志脱敏或错误分类的回归测试或脚本检查。
- 建议验证命令：

```bash
cd backend
conda run -n firstrag python -m pytest tests/test_retrieval_resilience.py tests/test_vector_index_worker.py tests/test_conversations.py
rg -n "api_key|Authorization|password|DATABASE_URL" backend/app
```

- 完成记录：
  - 完成日期：2026-07-02
  - 相关 commit：`60fd39c`
  - 新增 `backend/app/core/observability.py`，统一 JSON 日志事件、`request_id` 上下文、敏感字段脱敏和 `error_source` 分类。
  - FastAPI middleware 为每个请求写入 `X-Request-ID`，并记录 `http_request` / `http_request_failed`，只包含 method、path、status、duration 和 request id，不记录 header、body 或 query。
  - chat streaming 新增 `chat_first_answer_token`、`chat_stream_completed`、`chat_stream_failed`、`chat_stream_cancelled` 事件，保留首 token、总耗时、sources 数和 message/conversation 维度。
  - hybrid retrieval 对 embedding、Chroma vector、PostgreSQL full-text 和 CrossEncoder rerank 失败输出结构化事件；rerank 失败时降级为 RRF 结果并写入 diagnostics。
  - vector index worker 新增任务领取、跳过、完成、取消和失败事件，可用于统计任务吞吐、失败率、处理耗时和 worker 活动。
  - `docs/DEPLOYMENT.md` 新增日志事件、错误来源、最小监控面板和本地排查命令说明。
  - 验证命令：`cd backend && conda run -n firstrag python -m compileall app`；`cd backend && conda run -n firstrag python -m pytest tests/test_retrieval_resilience.py tests/test_vector_index_worker.py tests/test_conversations.py tests/test_observability.py tests/test_chat_service.py`；`cd backend && rg -n "api_key|Authorization|password|DATABASE_URL" backend/app`。

## T-046 准备真实问题集并固化上线前 RAG 质量门禁

- 来源计划：`PLAN-20260701-02`
- 优先级：`P1`
- 状态：`Done`
- 背景：项目已有 eval case、feedback、diagnostics 和质量看板雏形；正式上线前需要用真实文档和真实问题固定质量基线，验证默认检索参数 `4/16/16/8` 的效果。
- 目标：建立一批可复跑的真实问题集和上线前质量门禁，覆盖检索命中、source 相关性、回答引用充分性和不该检索时的跳过行为。
- 范围：
  - 整理真实文档和问题集，补充 `docs/evals/rag_eval_cases.jsonl` 或同等 eval 输入。
  - 覆盖多轮追问、无答案、低相关、禁用/启用 rerank、禁用/启用 query router、不同检索参数组合。
  - 固化 `4/16/16/8` 默认参数的真实链路效果，并和旧基线对比。
  - 把用户反馈和 source feedback 中的 bad case 整理为可复跑 eval case。
  - 更新 eval 报告和任务完成记录。
- 验收标准：
  - 有一批不含敏感信息、可复跑的真实问题集。
  - 上线前验收能输出通过率、平均 sources、平均首 token、失败 case 摘要。
  - 默认参数 `4/16/16/8` 的效果有记录，若效果不达标则给出回滚或调参建议。
  - eval 报告不包含 API Key、JWT、数据库密码或私人文档敏感内容。
- 建议验证命令：

```bash
FIRSTRAG_EVAL_USERNAME=你的用户名 \
FIRSTRAG_EVAL_PASSWORD=你的密码 \
scripts/acceptance_check.sh

conda run -n firstrag python scripts/eval_summary.py
```

- 完成记录：
  - 完成日期：2026-07-02
  - 相关 commit：`88d1c49`
  - `docs/evals/rag_eval_cases.jsonl` 扩展为 14 条非敏感可复跑 case，覆盖默认 `4/16/16/8`、多轮追问、无答案/低相关、rerank/query router 开关、小候选池参数组合和旧 `rrf_k=10` 对照。
  - `scripts/eval_rag.py` 的 summary、历史 JSON、Markdown 报告和命令行输出新增 case 分类/覆盖项、失败 case 摘要和平均 sources/首 token 门禁摘要。
  - `docs/evals/README.md` 固化上线前基线口径、回滚/调参建议和 2026-07-02 真实链路结果。
  - 真实 RAG eval gate：14/14 PASS，通过率 1.00，平均 sources 2.00，平均首 token 2701.22ms，平均耗时 5.90s，失败 case 为 0，质量门禁全部 PASS；报告 `docs/evals/latest_rag_eval_report.md`，历史记录 `docs/evals/runs/20260702_082822.json`。
  - Indexing eval：通过，job `succeeded`，聊天耗时 9.25s，引用数 1；报告 `docs/evals/latest_indexing_eval_report.md`，历史记录 `docs/evals/indexing_runs/20260702_082957.json`。
  - 2026-07-20 复验：补齐并导入 `RAG系统核心技术与实现.md`、`RAG检索策略全面解析.md` 两个 eval fixture，默认知识库最终仅保留这两个 Markdown fixture 和 `中华人民共和国民事诉讼法_20230901.pdf` 三个基线文件参与检索，已解除 `.codex-rerank-*` 历史 smoke 文件关联；真实 RAG eval gate 14/14 PASS，通过率 1.00，平均 sources 3.00，平均首 token 2483.11ms，平均耗时 4.80s，失败 case 为 0，质量门禁全部 PASS；报告 `docs/evals/latest_rag_eval_report.md`，历史记录 `docs/evals/runs/20260720_164813.json`。
  - 验证命令：`conda run -n firstrag python -c 'import json, pathlib; cases=[json.loads(line) for line in pathlib.Path("docs/evals/rag_eval_cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]; print(len(cases))'`；`cd backend && conda run -n firstrag python -m pytest tests/test_eval_rag_script.py`；`conda run -n firstrag python -m compileall scripts backend/tests/test_eval_rag_script.py`；`conda run -n firstrag python scripts/eval_summary.py`；`FIRSTRAG_EVAL_USERNAME=... FIRSTRAG_EVAL_PASSWORD=... scripts/rag_eval_gate.sh`；`FIRSTRAG_EVAL_USERNAME=... FIRSTRAG_EVAL_PASSWORD=... scripts/acceptance_check.sh`。

## T-047 区分普通用户模式和高级/开发模式

- 来源计划：`PLAN-20260701-02`
- 优先级：`P2`
- 状态：`Done`
- 背景：当前前端同时承载普通聊天、诊断、反馈、质量看板、检索参数和 eval 草稿等能力；作为教学项目和研发工具很有价值，但普通用户正式使用时会显得复杂。
- 目标：把普通用户工作流和高级/开发工具分层，降低主界面复杂度，同时保留教学和调试价值。
- 范围：
  - 定义普通模式：聊天、文件、知识库、基础模型设置、必要状态提示。
  - 定义高级/开发模式：诊断、eval 草稿、检索参数、质量看板、source 反馈、详细 retrieval diagnostics。
  - 通过环境变量、用户设置或本地开关控制高级功能显示。
  - 更新前端文案和必要文档，避免普通用户直接看到过多研发术语。
- 验收标准：
  - 默认界面对普通用户更聚焦，研发功能不干扰主聊天流程。
  - 高级/开发模式仍能访问诊断、eval、检索参数和质量分析。
  - 不破坏现有教学项目所需的工程化观察入口。
  - 前端 lint、单测和 build 通过。
- 建议验证命令：

```bash
cd frontend
npm run test
npm run lint
npm run build
```

- 完成记录：
  - 完成日期：2026-07-02
  - 相关 commit：`c14ae1a`
  - 前端新增普通/高级模式本地开关，默认普通模式仅展示聊天、知识库、文件、引用来源和必要状态。
  - 高级模式保留质量看板、回答/引用反馈、eval case 草稿、消息诊断、详细 retrieval diagnostics 和知识库检索参数。
  - 新增 `NEXT_PUBLIC_FIRSTRAG_ADVANCED_MODE_DEFAULT` 环境变量作为新浏览器默认值，用户切换后偏好写入浏览器 `localStorage`。
  - 更新 README、`.env.example` 和 `docs/FRONTEND.md`，明确普通模式与高级/开发模式边界。
  - 验证命令：`cd frontend && npm run test`；`cd frontend && npm run lint`；`cd frontend && npm run build`。

## T-048 补齐公网反向代理配置

- 来源计划：`PLAN-20260703-01`
- 优先级：`P1`
- 状态：`Done`
- 背景：当前 `deploy/nginx/` 仍是占位目录；在线 demo 文档已要求反向代理处理 TLS、上传体积、SSE buffering 和公网限流，但仓库尚未提供可复用配置。
- 目标：提供可审查、可复用的公网反向代理配置模板，为后续 VPS / Docker Compose 公开 demo 减少手工配置风险。
- 范围：
  - 在 `deploy/nginx/` 增加 Nginx 配置模板或示例，覆盖 frontend 反代、HTTPS 跳转、上传 body size、SSE 关闭缓冲和基础安全响应头。
  - 对登录、注册、上传、chat、模型设置等路径配置 IP 级限流示例，与后端进程内限流形成双层保护。
  - 明确 backend、PostgreSQL 不直接暴露公网，只由 frontend API proxy 或内网路径访问。
  - 更新 `docs/DEPLOYMENT.md` 中反向代理章节，说明如何替换域名、证书路径和上游地址。
- 验收标准：
  - 配置模板不包含真实域名、证书私钥、API Key、JWT 或数据库密码。
  - 支持 SSE streaming，不因代理缓冲导致聊天 token 被攒批返回。
  - 上传 body size 与 `MAX_UPLOAD_FILE_SIZE_BYTES` 保持一致或文档明确要求同步调整。
  - 文档说明公网只暴露 80/443，backend 和 PostgreSQL 端口保持 loopback 或防火墙隔离。
- 建议验证命令：

```bash
docker run --rm -v "$PWD/deploy/nginx:/etc/nginx/conf.d:ro" nginx:alpine nginx -t
git diff --check -- deploy/nginx docs/DEPLOYMENT.md docs/TASKS.md
```
- 完成记录：
  - 完成日期：2026-07-03
  - 相关 commit：`309ef7c`
  - 新增 `deploy/nginx/00-firstrag-shared.conf`，集中定义 frontend upstream、SSE/WebSocket 连接变量和公网 IP 级限流 zone。
  - 新增 `deploy/nginx/firstrag-proxy-locations.inc`，复用登录、注册、上传、chat streaming、vector job、模型设置和通用 API 的代理与限流规则；公网只转发到 frontend API proxy，不直接暴露 FastAPI 或 PostgreSQL。
  - 新增 `deploy/nginx/10-firstrag-public-demo.conf`，作为可语法检查的 Nginx 示例，适用于前置 TLS 终止层位于 Nginx 前面的部署。
  - 新增 `deploy/nginx/firstrag-public-demo.tls.conf.example`，作为 Nginx 直接终止 TLS 的模板，包含 HTTP 到 HTTPS 跳转、HSTS 和证书路径占位说明。
  - `docs/DEPLOYMENT.md` 已补充模板文件用途、域名/证书替换方式、body size 同步要求和 `nginx -t` 验证方式。
  - 验证命令：`git diff --check -- deploy/nginx docs/DEPLOYMENT.md docs/TASKS.md`。
  - 验证限制：`docker run --rm -v "$PWD/deploy/nginx:/etc/nginx/conf.d:ro" nginx:alpine nginx -t` 因本机 Docker daemon 未运行无法完成；本机也未安装 `nginx` 命令。后续部署到服务器或启动 Docker Desktop 后需补跑 `nginx -t`。

## T-049 增加公开环境注册控制

- 来源计划：`PLAN-20260703-01`
- 优先级：`P0`
- 状态：`Done`
- 背景：当前应用仍开放注册接口；公开 demo 若允许任意注册，容易带来滥用、上传成本、API 调用成本和数据清理压力。
- 目标：为公开 demo 增加可配置注册开关，让受控演示环境可以只开放预置账号或受邀账号。
- 范围：
  - 新增后端配置，例如 `ALLOW_PUBLIC_REGISTRATION`，默认保持现有开发体验，公开 demo 可设为 `false`。
  - 注册关闭时，后端 `/register` 返回安全、可理解的错误，不泄露内部配置。
  - 前端注册页根据后端响应展示“当前演示环境暂不开放注册”一类提示，并保留登录入口。
  - 更新 `.env.example`、`docs/API.md`、`docs/DEPLOYMENT.md` 和必要测试。
- 验收标准：
  - 注册关闭时无法创建新用户，已有用户登录不受影响。
  - 注册关闭不会影响本地开发环境按配置继续注册。
  - 错误响应不包含 secret、服务器路径或内部异常。
  - 后端和前端测试覆盖注册开启、关闭和用户提示路径。
- 完成记录：
  - 完成日期：2026-07-04
  - 相关 commit：`5ccc8a2`
  - 新增 `ALLOW_PUBLIC_REGISTRATION`，本地默认允许注册，公开 demo 可设为 `false`。
  - 注册关闭时，后端 `POST /register` 返回 `403` 和安全中文提示，不创建用户；`POST /login` 不受影响。
  - 前端注册页沿用后端 `detail` 展示“当前演示环境暂不开放注册，请使用已提供的账号登录。”，并保留登录入口。
  - `.env.example`、`docs/API.md` 和 `docs/DEPLOYMENT.md` 已补充配置与公开 demo 推荐值。
  - 验证命令：`cd backend && conda run -n firstrag python -m compileall app`。
  - 验证命令：`cd backend && conda run -n firstrag python -m unittest -v tests.test_auth_rate_limit`。
  - 验证命令：`cd frontend && npm run test`。
  - 验证命令：`cd frontend && npm run lint`。
- 建议验证命令：

```bash
cd backend
conda run -n firstrag python -m compileall app
conda run -n firstrag python -m pytest tests/test_auth_rate_limit.py

cd ../frontend
npm run test
npm run lint
```

## T-050 增加 demo 数据清理脚本

- 来源计划：`PLAN-20260703-01`
- 优先级：`P0`
- 状态：`Done`
- 背景：在线 demo 文档已把数据清理流程列为正式公开前阻塞项；当前还没有专门脚本清理临时用户、知识库、上传文件、chunks、vector entries 和相关 jobs。
- 目标：提供可 dry-run、可审计、可重复执行的 demo cleanup 脚本，降低公开演示环境的数据累积和误删风险。
- 完成时间：`2026-07-04`
- 交付：
  - 新增 `scripts/demo_cleanup.py`，默认 dry-run，执行模式需要 `--execute --confirm cleanup-demo-data`。
  - 支持保留演示账号、样例知识库和脱敏文件；保留样例知识库时自动保留关联文件和 owner 用户。
  - 支持按创建时间和显式清理用户清理 PostgreSQL metadata、chunks、jobs、Chroma entries 与 uploads 文件。
  - 更新 `docs/DEPLOYMENT.md`，补充执行频率、备份要求、示例命令和清理后 smoke test。
- 范围：
  - 新增 `scripts/demo_cleanup.py` 或同等脚本，默认 dry-run，执行模式需要显式参数确认。
  - 支持保留指定演示账号、样例知识库和脱敏文件，其余临时数据按创建时间或用户白名单清理。
  - 清理 PostgreSQL metadata、knowledge chunks、vector index jobs、Chroma entries 和 uploads 文件，确保权限边界和路径边界安全。
  - 输出清理摘要，只记录数量、ID 和安全路径摘要，不打印用户上传原文、API Key、JWT 或数据库密码。
  - 更新 `docs/DEPLOYMENT.md`，说明执行频率、执行前备份和清理后 smoke test。
- 验收标准：
  - dry-run 能展示将清理的用户、知识库、文件、chunks、jobs 和向量数量。
  - 执行模式不会删除保留账号和保留样例知识库。
  - 文件删除只发生在配置的 `UPLOADS_DIR` 内，禁止越界路径。
  - 清理后可以重新运行最小 smoke test：登录、上传小文件、向量化、提问和查看 sources。
- 建议验证命令：

```bash
conda run -n firstrag python -m compileall backend/app scripts

cd backend
conda run -n firstrag python -m pytest tests/test_migrate_db_script.py tests/test_vector_indexes.py

cd ..
conda run -n firstrag python scripts/demo_cleanup.py --dry-run
```

## T-051 部署到受控 staging/demo 环境

- 来源计划：`PLAN-20260703-01`
- 优先级：`P2`
- 状态：`Blocked`
- 背景：当前用户决策是暂不部署；本任务仅记录资源就绪后的执行步骤，不在没有服务器、域名和 TLS 方案前启动。
- 目标：在真实服务器上完成受控 staging/demo 环境部署，并保持 backend、worker、PostgreSQL、Redis、Chroma、uploads 和 models 的持久化边界清晰。
- 执行尝试：`2026-07-04`
- 当前阻塞：
  - 尚未提供真实云服务器、域名和 TLS 入口。
  - 本机 `.env` 已通过 production preflight，但真实服务器上的生产 `.env`、provider Key 和持久化目录仍未准备。
  - 当前本机 Compose 已将 frontend、backend 和 PostgreSQL 绑定到 `127.0.0.1`，但它仍是本地开发环境，不能替代真实服务器、域名、TLS 和公网入口验收。
- 已验证：
  - `docker compose config --quiet` 通过。
  - `conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method compose --skip-migration-dry-run` 通过，未输出真实 secret。
  - `docker compose ps` 可读取当前本机服务状态，但当前服务不是合格的受控 staging/demo 部署。
- 启动条件：
  - 已选择云服务器、域名和 TLS 入口。
  - 已准备生产 `.env`、非默认 secret、provider Key、持久化目录和 reranker 模型目录。
  - `T-048`、`T-049`、`T-050` 已完成或有明确替代方案。
- 范围：
  - 在服务器执行 production preflight、Docker Compose 配置检查、镜像构建、migration dry-run 和服务启动。
  - 创建受控演示账号和少量脱敏样例知识库，不在仓库中记录真实密码。
  - 确认公网只暴露 80/443，backend 和 PostgreSQL 不直接暴露。
  - 记录服务器资源、持久化目录、备份策略和部署命令，不提交真实 secret。
- 验收标准：
  - `redis`、`postgres`、`chroma`、`migrate`、`backend`、`frontend` 和 `worker` 均正常启动。
  - 生产 preflight 不输出真实 secret，且阻止默认密码、占位 Key 和公网数据库端口。
  - 演示账号可以登录，样例知识库可以完成一次向量化。
  - README 仍不公开账号密码，只说明 demo 访问限制和数据清理边界。
- 建议验证命令：

```bash
conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method compose
docker compose config --quiet
docker compose ps
docker compose logs --tail=100 redis postgres chroma migrate backend worker frontend
```

## T-052 完成公网 smoke test 与真实 RAG eval

- 来源计划：`PLAN-20260703-01`
- 优先级：`P2`
- 状态：`Blocked`
- 背景：公开 demo 是否可用不能只看本机或内网；需要从真实域名验证 TLS、反向代理、上传、SSE、worker、sources 和 RAG 质量门禁。
- 目标：完成一次公网入口验收，确认外部访问者通过真实域名使用 FirstRAG 时核心链路稳定、安全且质量不过度退化。
- 当前阻塞：`T-051` 尚未完成真实 staging/demo 部署，因此当前只能完成本地真实 RAG/indexing eval，不能把它等同于公网 smoke test。2026-07-20 将此前不准确的 `Done` 修正为 `Blocked`。
- 启动条件：
  - `T-051` 已完成 staging/demo 环境部署。
  - 已准备演示账号、脱敏样例知识库和可复跑 eval case。
- 范围：
  - 从公网域名验证 HTTPS、登录、上传小文件、触发向量化、提问、SSE token streaming、sources 展示和失败提示。
  - 使用 `FIRSTRAG_EVAL_BASE_URL` 指向公网 backend 或公开 API 入口，运行 RAG eval gate 和 indexing eval。
  - 检查后端、worker 和反向代理日志，确认无 API Key、JWT、数据库密码或用户上传原文泄露。
  - 记录通过率、平均 sources、平均首 token、失败 case、索引状态和公网访问限制。
- 验收标准：
  - 公网 smoke test 覆盖登录、上传、向量化、聊天和 sources。
  - RAG eval gate 通过，或清楚记录失败 case、回滚/调参建议和是否允许继续公开。
  - Indexing eval 通过，或清楚记录 worker、Chroma、PostgreSQL、embedding provider 的阻塞原因。
  - README Roadmap 只有在真实 demo URL、使用限制和清理策略落地后才标记“发布在线演示环境”为完成。
- 建议验证命令：

```bash
FIRSTRAG_EVAL_BASE_URL=https://api.example.com \
FIRSTRAG_EVAL_USERNAME=演示账号 \
FIRSTRAG_EVAL_PASSWORD=演示密码 \
scripts/rag_eval_gate.sh

conda run -n firstrag python scripts/eval_indexing.py \
  --base-url https://api.example.com \
  --username 演示账号 \
  --password 演示密码
```

## T-053 用户登录后配置 LLM 与向量模型 API

- 来源计划：用户要求“不再从环境变量中加载 LLM API 和向量 API，要求用户登录后配置”。
- 优先级：`P1`
- 状态：`Done`
- 完成日期：`2026-07-03`
- 目标：聊天模型和 embedding/向量化调用都使用当前登录用户保存的 provider/model/API Key。Docker 默认启动不再依赖 `LLM_API_KEY`、`DEEPSEEK_API_KEY`、`ZAI_EMD_API` 或 `EMBEDDING_API_KEY`；`DASHSCOPE_API_KEY` / `QWEN_API_KEY` 仅作为可选远程 Qwen rerank Key。
- 完成内容：
  - `llm_service.py`：聊天模型工厂不再读取服务器环境变量中的 provider/model/API Key，只保留生成参数默认值；创建模型时要求用户 Key。
  - `user_settings_service.py`：业务调用遇到空配置或历史 `platform` 模式时提示用户去设置页配置；保存时不再允许切回平台 Key。
  - 新增 `user_embedding_settings` 表 migration、repository 和 `embedding_settings_service.py`，用于保存用户级 embedding provider/model/API Key/维度/超时/重试。
  - `embedding_model.py`：新增 `create_embedding_model(user_id)` 和 `create_embedding_model_from_settings()`，embedding 调用改为用户配置驱动。
  - `vector_index_service.py`、`hybrid_retriever.py`、`document_service.py`：把 `user_id` 传入 embedding 创建、Chroma collection 隔离与 query embedding cache。
  - `user_settings.py` API：新增 `/user/settings/embedding-providers`、`/user/settings/embedding`、`/user/settings/embedding/test`。
  - `vector_indexes.py`：提交向量化任务前检查当前用户是否已配置向量模型，未配置直接返回 400，避免 worker 延迟失败。
  - 前端设置页：新增“向量模型”配置区块和 `/api/settings/embedding*` 代理路由；聊天模型配置移除“平台 Key”选择。
  - `.env.example`：已移除 LLM/embedding provider Key 的环境变量入口，仅保留聊天生成参数和可选远程 rerank 配置。
  - `production_preflight.py`：移除 LLM/embedding Key 的环境变量检查，仅保留远程 rerank 相关检查。
  - README、部署、Docker 启动、RAG 流程、Schema 和 settings API 文档已同步为登录后配置模型 Key。
- 已验证：
  - `cd backend && conda run -n firstrag python -m compileall app` 已通过。
  - `cd backend && conda run -n firstrag python -m unittest -v tests.services.test_llm_service tests.services.test_embedding_model tests.services.test_embedding_settings_service tests.services.test_user_settings_service tests.test_user_settings tests.test_vector_indexes tests.test_retrieval_resilience tests.test_production_preflight_script` 已通过，70 tests OK。
  - `cd backend && conda run -n firstrag python -m unittest discover -s tests -v` 已通过，172 tests OK。
  - `cd frontend && npm run lint` 已通过。
  - `cd frontend && npm run build` 已通过；sandbox 因 Turbopack 端口绑定限制失败一次，已在授权后重跑通过。
  - `conda run -n firstrag python -m py_compile scripts/production_preflight.py` 已通过。
  - `conda run -n firstrag python scripts/migrate_db.py --list` 已识别 `002_create_user_embedding_settings.sql`。
  - `docker compose --env-file .env.example config --quiet` 已通过。

## T-054 支持聊天框图片附件和视觉模型调用

- 来源计划：`PLAN-20260704-01`
- 优先级：`P1`
- 状态：`Done`
- 背景：当前聊天链路是纯文本：前端输入区只有 `textarea`，`POST /chat` 只提交 `message` 字符串，`messages.content` 只保存文本，RAG chain 也把用户输入作为字符串传给 OpenAI-compatible 文本模型。用户在聊天框中上传图片并提问时，当前没有附件存储、消息结构或视觉模型调用能力。
- 目标：实现聊天图片附件 MVP，让用户可以在当前聊天框中上传少量图片，并在支持 vision 的聊天模型下基于图片内容回答问题。
- 范围：
  - 新增消息附件数据结构，例如 `message_attachments` 表或等价 JSONB metadata，记录 `user_id`、`conversation_id`、`message_id`、文件路径、mime type、size、hash 和创建时间。
  - 后端新增聊天附件上传/绑定流程，限制 `png`、`jpeg`、`webp` 等图片类型，限制单张大小、单轮数量和总大小。
  - `POST /chat` 支持文本问题加图片附件；保存用户消息时保留附件 metadata，历史消息接口返回附件缩略信息。
  - LLM 调用层增加 vision 能力判断和多模态 message payload 构造；当前模型不支持图片时返回清晰的 400 提示，不写入孤立 assistant message。
  - 前端聊天输入区增加图片选择按钮、缩略图预览、删除、上传中/失败状态和移动端布局适配；不把图片 base64 持久化到浏览器存储。
  - SSE streaming、sources、retrieval diagnostics 继续保持可用；图片消息仍可结合当前知识库做文本检索。
  - 日志和错误响应不得输出图片原始 base64、API Key、JWT 或本地绝对路径。
- 非目标：
  - 本任务不做图片入知识库持久检索，不做 OCR chunk 入库。
  - 本任务不要求所有 LLM provider 都支持 vision，只要求对支持 vision 的 OpenAI-compatible provider 形成可用路径，并对不支持模型给出明确提示。
- 验收标准：
  - 用户可以在聊天框附加图片并发送文本问题；支持 vision 的模型能收到多模态输入。
  - 不支持 vision 或未配置模型时，前端展示安全、可理解的错误，不产生半成品消息。
  - 历史消息可展示该轮用户消息的图片附件缩略信息。
  - 权限校验确保用户只能访问自己的图片附件，删除会话或清理用户数据时附件不会越权残留。
  - 文件大小、类型和数量限制在前后端都生效。
- 建议验证命令：

```bash
cd backend
conda run -n firstrag python -m compileall app
conda run -n firstrag python -m pytest tests/test_chat_settings.py tests/test_chat_service.py tests/test_user_settings.py

cd ../frontend
npm run test
npm run build

cd ..
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 migrate backend worker frontend postgres
```
- 完成记录：
  - 完成日期：2026-07-05
  - 相关 commit：`42f206b`
  - 新增 `message_attachments` migration、repository 和 `chat_attachment_service.py`，支持 PNG/JPEG/WebP 上传、magic bytes 校验、单轮数量/大小限制、用户/会话权限校验和安全 metadata 序列化。
  - 新增 `/chat/attachments` 上传接口和 `/chat/attachments/{attachment_id}/content` 读取接口；`POST /chat` 支持 `attachment_ids`，保存用户消息后绑定附件。
  - LLM 调用层增加 vision 模型能力判断；带图片时构造 OpenAI-compatible 多模态 `HumanMessage`，不支持 vision 的模型返回清晰 `400`，不会写入半成品 assistant message。
  - 历史消息接口返回 `messages[].attachments`，前端工作台支持图片选择、缩略图预览、移除、上传中状态、历史图片读取展示和移动端布局适配。
  - README、API、Schema、架构、RAG 流程、前端代理和 `.env.example` 已同步。
  - 已验证：
    - `cd backend && conda run -n firstrag python -m compileall app`
    - `cd backend && conda run -n firstrag python -m pytest`，191 passed。
    - `cd frontend && npm test`，50 passed。
    - `cd frontend && npm run lint` 通过，保留 2 个图片缩略图 `<img>` 性能提示。
    - `cd frontend && npm run build` 已通过；默认沙箱因 Turbopack 创建进程/绑定端口限制失败一次，已在授权后重跑通过。
    - `conda run -n firstrag python scripts/migrate_db.py --list` 已识别 `004_create_message_attachments.sql`。
    - `docker compose --env-file .env.example config --quiet` 通过。
    - `docker compose up -d --build` 已通过；`docker compose ps` 显示 backend、frontend、worker 和 postgres 正常运行。
    - `docker compose logs --tail=100 migrate backend worker frontend postgres` 已确认 `004_create_message_attachments.sql` applied，backend、worker、frontend 和 postgres 无启动错误。
    - `conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method compose` 已执行，Migration dry-run 通过；本地 `.env` 生产 secret 检查失败，原因是 `POSTGRES_PASSWORD` 仍为模板占位值且 `JWT_SECRET_KEY` 长度过短。

## T-055 支持图片/OCR 入知识库检索

- 来源计划：`PLAN-20260704-01`
- 优先级：`P2`
- 状态：`Done`
- 完成日期：`2026-07-05`
- 背景：聊天图片附件解决的是单轮视觉问答；另一类需求是把图片、截图或扫描件作为知识库资料长期保存，并通过 RAG 检索。当前知识库文件上传主要面向 PDF、DOCX、Markdown 和 TXT，图片文件不会被解析成可检索文本 chunk。
- 目标：让知识库可以接收图片资料，通过 OCR 或视觉 caption 转成文本 chunk，再进入现有 embedding、全文检索、RRF、rerank 和 sources 展示链路。
- 启动条件：
  - `T-054` 已明确图片存储、安全边界和模型能力判断策略，或已形成独立的图片文件存储方案。
  - 已选择 OCR/视觉解析 provider 或本地解析方案，并明确费用、速率限制和失败降级。
- 范围：
  - 扩展知识文件上传类型，支持常见图片 mime type，并在上传阶段继续执行大小、hash 去重和权限隔离。
  - document parsing 层为图片生成可检索文本：OCR 原文、视觉 caption、图片 metadata 或多页/多区域结果。
  - vector index worker 将图片解析结果切分为 chunks，写入 PostgreSQL full-text chunks 和 Chroma vector store。
  - sources 展示中标明来源是图片文件，并尽可能保留图片页/区域、OCR 置信度或 caption 类型 metadata。
  - 解析失败时写入安全错误摘要，任务状态可重试，不输出图片原文、provider Key 或本地路径。
  - 更新 RAG eval 或 indexing eval，覆盖至少一个小图片样例。
- 验收标准：
  - 用户可以把图片作为知识库文件上传，并异步完成解析、chunk、embedding 和索引。
  - 对图片内容提问时，检索结果能返回对应图片 source，并展示文件名和可读摘要。
  - 图片解析失败不会阻塞其他文件向量化任务，worker 可继续处理队列。
  - 未配置 OCR/视觉解析 provider 时，上传或向量化阶段给出明确提示。
- 建议验证命令：

```bash
cd backend
conda run -n firstrag python -m compileall app
conda run -n firstrag python -m pytest tests/test_knowledge_files.py tests/test_vector_indexes.py tests/test_vector_index_failure_recovery.py

cd ../frontend
npm run test
npm run build

cd ..
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 migrate backend worker frontend postgres
```
- 完成记录：
  - 相关 commit：`d8cd9ce`。
  - 扩展知识文件上传支持 PNG、JPEG 和 WebP，并在上传阶段校验图片文件头与 MIME/扩展名一致性。
  - `document_service` 新增图片知识文件解析路径：通过当前用户的 vision-capable 聊天模型把图片转为可检索 Markdown，再进入既有 chunk、embedding、PostgreSQL full-text 和 Chroma 链路。
  - 单文件和整库向量化提交会提前检查图片文件所需的 vision 模型配置；`auto_index=true` 入队后仍由 worker 兜底失败并返回 `image_parse_error` 恢复提示。
  - 前端文件上传 accept、上传错误文案和向量化失败恢复动作已同步支持图片知识文件。
  - `scripts/eval_indexing.py` 增加 `--file-kind image` / `FIRSTRAG_INDEXING_EVAL_FILE_KIND=image`，可用最小 PNG 样例覆盖图片上传、vision 解析、向量化和 Sources 命中链路。
  - README、API、RAG 流程、Schema、后端、前端和 eval 文档已同步。
  - 已验证：
    - `cd backend && conda run -n firstrag python -m compileall app ../scripts/eval_indexing.py`
    - `cd backend && conda run -n firstrag python -m pytest tests/services/test_document_service.py tests/test_knowledge_files.py tests/test_vector_indexes.py tests/test_vector_index_failure_recovery.py tests/test_eval_indexing_script.py`，35 passed。
    - `cd backend && conda run -n firstrag python -m pytest`，197 passed。
    - `cd frontend && npm test -- use-knowledge-files.test.ts utils.test.ts`，16 passed。
    - `cd frontend && npm test`，50 passed。
    - `cd frontend && npm run lint` 通过，保留 2 个图片缩略图 `<img>` 性能提示。
    - `cd frontend && npm run build` 沙箱内因 Turbopack 创建进程/绑定端口限制失败一次，授权后重跑通过。
    - `git diff --check` 通过。
  - Docker Compose 验证：
    - 首次 `docker compose up -d --build` 曾因 Docker registry mirror 对 `node:22-slim` 和 `python:3.12-slim` metadata 请求返回 `403 Forbidden` 未完成。
    - 后续重新执行 `docker compose up -d --build` 已通过，backend 和 frontend 镜像均完成构建，`migrate` 正常退出，backend、frontend、worker 和 postgres 均启动。
    - `docker compose ps` 显示 backend、frontend、worker 约 1 分钟前由新镜像启动，postgres 为 healthy。
    - `docker compose logs --tail=100 migrate backend worker frontend postgres` 已确认 migration `skipped=5`，backend、frontend 和 worker 无启动错误。

## T-056 引入 Redis 基础设施、配置和健康检查

- 来源计划：`PLAN-20260705-01`
- 优先级：`P0`
- 状态：`Done`
- 背景：当前缓存、限流和 worker 运行态主要使用进程内状态；单实例可以工作，但多实例部署时无法共享命中、限流计数和 worker 在线状态。
- 目标：为后续缓存、限流和 worker 运行态提供统一 Redis 基础设施，默认 Docker Compose 内置 Redis，并允许生产环境通过 `REDIS_URL` 指向托管 Redis。
- 范围：
  - 新增 Python Redis 依赖和后端 Redis client/service 封装。
  - 新增 `REDIS_URL`、连接超时、命令超时、启用开关和故障策略配置。
  - Docker Compose 增加 `redis` 服务、healthcheck、backend/worker 依赖关系和必要环境变量。
  - 后端暴露或复用健康检查，让 Redis 可用性进入部署诊断和日志。
  - Redis 不可用时返回清晰诊断，不输出 Redis URL、密码或内部连接串。
- 非目标：
  - 本任务不迁移具体业务缓存、限流或 worker 状态；迁移由 `T-057`、`T-058`、`T-059` 承接。
- 验收标准：
  - 本地 Compose 可以启动 Redis，backend 和 worker 能读取 Redis 配置并完成 ping/health 检查。
  - 未配置 Redis 或 Redis 不可用时，错误信息安全且可定位。
  - 单元测试覆盖 Redis URL 脱敏、连接成功、连接失败和禁用配置。
- 建议验证命令：

```bash
cd backend
conda run -n firstrag python -m pytest tests/test_config.py tests/test_observability.py

cd ..
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 redis backend worker
```
- 实现记录：
  - 相关 commit：`5e8c32c`、`d0aee38`。
  - 新增 `redis==5.2.1` 后端依赖。
  - 新增 Redis client/service 封装，支持 `REDIS_URL`、连接超时、命令超时、启用开关、健康检查和 Redis URL 脱敏。
  - 新增公开 `GET /health`，返回后端和 Redis 基础设施的安全健康摘要，不返回 Redis URL、密码、JWT 或数据库连接串。
  - Docker Compose 新增 `redis` service、healthcheck，并让 backend/worker 默认通过 `redis://redis:6379/0` 连接内置 Redis。
  - worker 启动时记录一次 Redis 健康状态，不改变 PostgreSQL 持久任务队列和任务领取语义。
  - README、API、Backend、Deployment、Architecture 和 Docker 启动文档已同步 Redis 基础设施说明。
- 已验证：
  - `cd backend && conda run -n firstrag python -m compileall app tests/test_redis_service.py tests/test_health.py tests/test_config.py tests/test_observability.py`
  - `docker compose config --quiet`
  - `git diff --check`
  - `cd backend && conda run -n firstrag python -m pytest tests/test_redis_service.py tests/test_health.py tests/test_config.py tests/test_observability.py`，15 passed。
  - `cd backend && conda run -n firstrag python -m pytest tests/test_vector_index_worker.py tests/test_vector_indexes.py tests/test_vector_index_failure_recovery.py`，17 passed。
  - `cd backend && conda run -n firstrag python -m pytest`，206 passed。
  - `docker compose build --pull=false backend` 已通过，backend 镜像内 `redis-5.2.1` 安装成功。
  - `docker run --rm firstrag-backend:latest python -c "import redis; print(redis.__version__)"` 输出 `5.2.1`。
  - `docker compose up -d --build` 已由用户重新执行成功。
  - `docker compose ps` 显示 `redis` 为 `healthy`，backend、frontend 和 worker 使用新镜像约 1 分钟前启动，postgres 为 `healthy`。
  - `docker compose logs --tail=100 redis migrate backend worker frontend postgres` 已确认 Redis `Ready to accept connections`，migration `applied=0 skipped=5`，backend、frontend 和 worker 无启动错误。
  - `docker compose exec -T redis redis-cli ping` 输出 `PONG`。
  - `curl -s http://127.0.0.1:8000/health` 返回 `status=healthy` 且 `dependencies.redis.status=healthy`。
  - `conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method compose` 已执行；本地 `.env` 仍因 `POSTGRES_PASSWORD` 是模板占位值、`JWT_SECRET_KEY` 长度过短而未通过生产 secret 检查，且 migration dry-run 提示未通过。该问题属于本地生产配置未达标，不影响本次 Redis 基础设施接入的 Compose 验证结果。
- 历史阻塞：
  - 首次 `docker compose up -d --build` 曾因 Docker registry mirror `vxuhih4a.mirror.aliyuncs.com` 拉取 `redis:7-alpine` manifest 返回 `403 Forbidden` 未完成；后续用户重新构建已解除。

## T-057 抽象缓存层并迁移 RAG 热点缓存到 Redis

- 来源计划：`PLAN-20260705-01`
- 优先级：`P1`
- 状态：`Done`
- 背景：当前 `knowledge_profile_cache`、`retrieval_settings_cache` 和 query embedding cache 使用进程内短 TTL 缓存；多实例时命中率不稳定，worker/backend 之间也无法共享。
- 目标：建立统一 cache adapter，将 RAG 热点缓存迁移到 Redis，同时保留进程内 fallback，确保 Redis 故障不会直接中断核心问答链路。
- 范围：
  - 增加 Redis cache adapter，支持 JSON value、TTL、delete、prefix invalidation 和测试隔离。
  - 迁移 knowledge profile cache，key 包含用户 ID 和 knowledge base ID。
  - 迁移 retrieval settings cache，key 包含用户 ID 和 knowledge base ID，设置更新后主动失效。
  - 迁移 query embedding cache，key 包含用户 ID、provider、model、dimensions 和 normalized query。
  - 保留 diagnostics 字段，例如 cache hit、source、ttl、fallback reason，并继续进入 SSE retrieval diagnostics 和 eval 报告。
- 验收标准：
  - Redis 可用时重复 RAG 请求能跨进程命中缓存。
  - Redis 不可用时自动回退到进程内缓存或数据库/provider 读取，错误被脱敏记录。
  - 文件上传、知识库文件关系变化、索引状态变化、retrieval settings 更新后相关缓存会失效。
  - 后端测试覆盖 miss、hit、TTL 过期、主动失效、Redis 故障 fallback 和用户隔离。
- 建议验证命令：

```bash
cd backend
conda run -n firstrag python -m pytest \
  tests/test_rag_service.py \
  tests/test_retrieval_settings_cache.py \
  tests/services/test_embedding_model.py

cd ..
scripts/rag_eval_gate.sh
```
- 实现记录：
  - 相关 commit：`654899e`。
  - 新增 `backend/app/services/cache_service.py`，统一封装 Redis JSON cache adapter，支持 TTL、单 key 删除、prefix invalidation、测试隔离和短熔断 fallback；Redis 错误会脱敏后进入 fallback diagnostics。
  - `knowledge_profile_cache` 迁移为 Redis 优先、进程内缓存兜底；Redis key 按 `user_id + knowledge_base_id` 隔离，文件上传、知识库文件关系变化、索引状态变化和删除向量结果继续主动失效相关缓存。
  - `retrieval_settings_cache` 迁移为 Redis 优先、进程内缓存兜底；Redis key 按 `user_id + knowledge_base_id` 隔离，设置更新后继续主动失效，缺失设置仍不缓存 `None`。
  - query embedding cache 接入 Redis + 进程内双层缓存；key 仍按 `user_id + embedding provider + model + dimensions + normalized query` 隔离，Redis 实际 key 使用 normalized query 的 sha256 摘要，避免把用户原始问题直接放进 Redis key。
  - retrieval diagnostics 保留原有 `*_cache_hit` 字段，并新增/透传 `knowledge_profile_cache_source`、`retrieval_settings_cache_backend`、`query_embedding_cache_source` 和 `*_cache_fallback_reason`，继续进入 SSE retrieval diagnostics 和 RAG eval 统计。
  - README、Architecture、Backend、Deployment 和 RAG workflow 文档已同步 Redis 现在承接 RAG 热点共享缓存；分布式限流和 worker 运行态仍由 `T-058`、`T-059` 承接。
- 已验证：
  - `cd backend && conda run -n firstrag python -m compileall app`
  - `cd backend && conda run -n firstrag python -m pytest tests/test_cache_service.py tests/test_knowledge_profile_cache.py tests/test_retrieval_settings_cache.py tests/test_retrieval_resilience.py tests/test_rag_service.py tests/test_redis_service.py tests/test_health.py`，57 passed。
  - `cd backend && conda run -n firstrag python -m pytest`，215 passed。
  - `docker compose up -d --build` 已通过，backend 和 frontend 镜像完成构建并重建启动。
  - `docker compose ps` 显示 backend、frontend、worker 均为 `Up`，postgres 和 redis 为 `healthy`。
  - `docker compose logs --tail=100 redis migrate backend worker frontend postgres` 已确认 Redis Ready、migration `applied=0 skipped=5`，backend、frontend 和 worker 无新启动错误；PostgreSQL tail 中仍保留一条此前本地密码不匹配产生的历史认证失败日志，不属于本轮重建新增错误。
  - `docker compose exec -T redis redis-cli ping` 输出 `PONG`。
  - `curl -s http://127.0.0.1:8000/health` 返回 `status=healthy` 且 `dependencies.redis.status=healthy`。
  - `conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method compose` 已通过，包括 Docker Compose config 和 migration dry-run。
  - `docker compose exec -T backend python -c "from app.services import cache_service; ..."` 已完成临时 JSON key 写入、读取和删除，读取结果为 `{'ok': True}`。
  - `git diff --check` 通过。

## T-058 将登录和 API 限流升级为 Redis 分布式限流

- 来源计划：`PLAN-20260705-01`
- 优先级：`P0`
- 状态：`Done`
- 背景：当前登录失败、chat、upload、vector index 和 model test 限流使用进程内计数；多实例部署时用户可以绕过单实例限额。
- 目标：把现有限流升级为 Redis 分布式窗口，在多 backend 实例下共享限流状态，并保留当前 `Retry-After` 与测试隔离能力。
- 范围：
  - 使用 Redis 实现固定窗口或滑动窗口限流，保留现有 `assert_rate_limit_available`、`consume_rate_limit`、`clear_rate_limit`、`reset_rate_limits` 调用语义。
  - 登录失败、chat、upload、vector index、model test 全部接入 Redis 限流。
  - 增加 Redis 故障策略配置：公开环境默认 fail-closed，本地开发可 fail-open。
  - 429 响应继续带 `Retry-After`，错误文案保持安全可理解。
- 验收标准：
  - 多进程或重复 client 场景下共享限流计数。
  - 登录成功后可清除对应失败计数。
  - Redis 故障时按配置 fail-open 或 fail-closed，并输出脱敏结构化日志。
  - 现有限流测试全部通过，并补充 Redis 分布式路径测试。
- 建议验证命令：

```bash
cd backend
conda run -n firstrag python -m pytest \
  tests/test_auth_rate_limit.py \
  tests/test_chat_settings.py \
  tests/test_knowledge_files.py \
  tests/test_vector_indexes.py \
  tests/test_user_settings.py
```
- 实现记录：
  - 相关 commit：`8875eea`。
  - `backend/app/core/rate_limit.py` 升级为 Redis 优先 sliding-window 限流，使用 Redis sorted set 和 Lua 脚本原子完成窗口清理、计数、消耗额度和 `Retry-After` 计算。
  - 保留 `assert_rate_limit_available`、`consume_rate_limit`、`clear_rate_limit`、`reset_rate_limits` 和 `enforce_rate_limit` 调用语义，登录、chat、upload、vector index、model test 的 route 调用点无需改变。
  - Redis 限流 key 使用 `scope + identifier sha256`，不在 Redis key 中暴露 username、IP、user_id 或完整业务 identifier。
  - 新增 `RATE_LIMIT_BACKEND` 和 `RATE_LIMIT_REDIS_FAILURE_MODE` 配置；Docker Compose 默认 `redis + fail_closed`，本地未显式配置时 Redis 故障可 fail-open 到进程内限流，避免 conda 调试被容器 DNS 或 Redis 可用性阻塞。
  - 登录成功后的 `clear_rate_limit` 会同时删除 Redis bucket；`reset_rate_limits` 会清理 Redis `firstrag:rate_limit:*` 命名空间，保留测试隔离能力。
  - README、API、Architecture、Deployment 和 Docker 启动文档已同步 Redis 现在承接后端分布式限流；反向代理/WAF 仍建议保留边缘 IP 级限流。
- 已验证：
  - `cd backend && conda run -n firstrag python -m compileall app tests/test_rate_limit.py`
  - `cd backend && conda run -n firstrag python -m pytest tests/test_rate_limit.py tests/test_auth_rate_limit.py tests/test_chat_settings.py tests/test_knowledge_files.py tests/test_vector_indexes.py tests/test_user_settings.py`，48 passed。
  - `cd backend && conda run -n firstrag python -m pytest`，222 passed。
  - `docker compose up -d --build` 已通过，backend 和 frontend 镜像完成构建并重建启动。
  - `docker compose ps` 显示 backend、frontend、worker 均为 `Up`，postgres 和 redis 为 `healthy`。
  - `docker compose logs --tail=100 redis migrate backend worker frontend postgres` 已确认 Redis Ready、migration `applied=0 skipped=5`，backend、frontend 和 worker 无新启动错误；PostgreSQL tail 中仍保留一条此前本地密码不匹配产生的历史认证失败日志，不属于本轮重建新增错误。
  - `docker compose exec -T redis redis-cli ping` 输出 `PONG`。
  - `curl -s http://127.0.0.1:8000/health` 返回 `status=healthy` 且 `dependencies.redis.status=healthy`。
  - `docker compose exec -T backend python -c "from app.core.rate_limit import ..."` 已完成 Redis 限流 smoke；同一 key 第一次通过、第二次被阻断，输出 `blocked:60`。
  - `conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method compose` 已通过，包括 Docker Compose config 和 migration dry-run。

## T-059 为 vector worker 增加 Redis 运行态、锁和队列观测

- 来源计划：`PLAN-20260705-01`
- 优先级：`P1`
- 状态：`Done`
- 背景：当前 `vector_index_jobs` 使用 PostgreSQL 持久任务表和 `FOR UPDATE SKIP LOCKED` 领取任务，可靠性较好；但前端 health 主要来自任务表，缺少 worker 在线心跳和运行态细节。
- 目标：保留 PostgreSQL 作为持久队列，用 Redis 增加 worker 心跳、短租约锁、运行指标和队列观测缓存，提升多 worker 部署时的可见性。
- 范围：
  - worker 启动和循环处理时写入 Redis 心跳，记录 worker id、hostname、最近活跃时间和当前任务 ID。
  - 增加可选单文件或用户级短租约锁，避免高并发下重复索引同一文件的边界抖动；锁过期后自动释放。
  - 队列 health 接口合并 PostgreSQL 任务统计和 Redis worker 在线状态。
  - 前端任务队列面板展示 worker 在线数量、最近心跳和 Redis 运行态不可用提示。
  - Redis 不可用时仍可依赖 PostgreSQL 队列继续处理任务。
- 非目标：
  - 本任务不把 `vector_index_jobs` 迁移到 Redis stream/list，不改变任务持久化、重试和历史查询语义。
- 验收标准：
  - worker 正常运行时 health 接口可看到在线 worker 和最近心跳。
  - worker 停止或 Redis 重启后，前端能看到明确状态，任务表状态仍保持一致。
  - 重复向量化同一文件时不会因为 Redis 锁导致永久卡住。
  - 后端和前端测试覆盖 Redis 可用、Redis 不可用和 worker 离线场景。
- 建议验证命令：

```bash
cd backend
conda run -n firstrag python -m pytest \
  tests/test_vector_index_worker.py \
  tests/test_vector_indexes.py \
  tests/test_vector_index_failure_recovery.py

cd ../frontend
npm test -- TaskQueuePanel
```
- 实现记录：
  - 相关 commit：`8f454ef`。
  - 新增 `backend/app/services/vectors/vector_worker_runtime_service.py`，Redis 保存短 TTL worker 心跳、在线 worker set、单文件短租约、运行指标和 health summary；Redis 故障会短熔断并降级到 PostgreSQL 队列状态。
  - `vector_index_worker` 启动、轮询、空闲和处理任务时写入运行态心跳；长任务执行期间使用后台 heartbeat loop 定时续写，避免 Redis 心跳 TTL 过期。
  - Redis 文件短租约按 `user_id + file_id` 隔离；锁冲突时通过 `defer_vector_index_job` 短暂退回 PostgreSQL 队列，避免重复索引且不会永久卡住；Redis 锁不可用时继续依赖 PostgreSQL `vector_index_jobs`。
  - `GET /chat/vector-index-jobs/health` 合并 PostgreSQL 队列统计和 Redis runtime，新增 `worker.online_count`、`worker.redis_available`、`worker.last_heartbeat_at`、`worker.last_heartbeat_age_seconds`、`worker.active_file_lock_count` 等字段。
  - 前端任务队列面板解析并展示 Redis 运行态、在线 worker 数、最近 worker 心跳、心跳延迟和活跃文件锁；当 active 任务存在但 Redis 未检测到在线 worker 时给出明确操作建议。
  - `.env.example`、README、Architecture、Backend、Deployment 和 API 文档已同步 Redis worker runtime 现状；明确 Redis 不替代 PostgreSQL 持久任务队列。
- 已验证：
  - `cd backend && conda run -n firstrag python -m compileall app tests/test_vector_worker_runtime_service.py tests/test_vector_index_worker.py tests/test_vector_indexes.py`
  - `cd backend && conda run -n firstrag python -m pytest tests/test_vector_worker_runtime_service.py tests/test_vector_index_worker.py tests/test_vector_indexes.py tests/test_vector_index_failure_recovery.py`，21 passed。
  - `cd backend && conda run -n firstrag python -m pytest`，226 passed。
  - `cd frontend && npm test -- utils.test.ts`，12 passed。
  - `cd frontend && npm test`，51 passed。
  - `git diff --check` 通过。
  - `docker compose config --quiet` 通过。
  - `docker compose up -d --build` 未完成：此前 Codex 沙箱无法访问 Docker socket；后续 Docker 场景完整回归由 `T-061` 继续覆盖。
  - `conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method compose` 中 secret、provider、database、port、persistent directories 和 Docker Compose config 检查通过；migration dry-run 未通过，原因是 compose migration 需要 Docker daemon，而当前环境无法访问 Docker socket。

## T-060 补齐 Redis 生产部署、preflight 和文档

- 来源计划：`PLAN-20260705-01`
- 优先级：`P1`
- 状态：`Done`
- 背景：Redis 成为基础设施后，部署文档、环境变量模板和 production preflight 必须明确本地 Compose Redis 与托管 Redis 的配置差异。
- 目标：把 Redis 的配置、部署、安全检查、故障策略和运维边界写入项目文档和 preflight，避免真实部署时遗漏密码、端口暴露或健康检查。
- 范围：
  - 更新 `.env.example`，补充 Redis URL、开关、超时、故障策略和 Compose 覆盖说明。
  - 更新 README、`docs/DEPLOYMENT.md`、`docs/ARCHITECTURE.md`、`docs/RAG_WORKFLOW.md`、`docs/BACKEND.md` 和 `docs/API.md` 中相关说明。
  - production preflight 检查 Redis URL、默认密码、公开端口、连接可用性和日志脱敏。
  - 明确生产建议：Redis 不直接公网暴露，优先使用内网地址或托管 Redis，开启密码/TLS 时不得记录完整连接串。
- 验收标准：
  - 文档准确区分 Redis 已实现能力、仍由 PostgreSQL 承担的持久队列能力和故障降级策略。
  - preflight 能拦截明显不安全的 Redis 配置，并不输出真实 secret。
  - `.env.example` 可用于 Compose 本地启动，生产覆盖项清晰。
- 建议验证命令：

```bash
conda run -n firstrag python -m pytest backend/tests/test_production_preflight_script.py
conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method compose
docker compose config --quiet
```
- 实现记录：
  - 相关 commit：`f13f9a5`。
  - `scripts/production_preflight.py` 新增 Redis 生产配置检查：`REDIS_URL` 格式、占位值、外部 Redis 认证、默认/弱密码、`RATE_LIMIT_REDIS_FAILURE_MODE=fail_closed`、`REDIS_PORT` 不公网暴露。
  - preflight 新增 Compose Redis service 静态检查：必须存在 `redis` service、配置 healthcheck、复用日志轮转，并禁止在默认 compose 中给 Redis 配置 `ports`。
  - `docker-compose.yml` 显式透传 `VECTOR_WORKER_HEARTBEAT_TTL_SECONDS` 和 `VECTOR_WORKER_FILE_LOCK_TTL_SECONDS` 到 backend/worker，便于生产覆盖。
  - `.env.example`、README、Deployment、Architecture、RAG workflow 和 Docker 启动文档已明确 Compose Redis 与托管 Redis 的差异、认证/TLS 建议、限流 fail-closed、以及 Redis 不保存会话/消息和不替代 PostgreSQL 持久队列。
- 已验证：
  - `conda run -n firstrag python -m py_compile scripts/production_preflight.py`
  - `conda run -n firstrag python -m pytest backend/tests/test_production_preflight_script.py`，15 passed。
  - `cd backend && conda run -n firstrag python -m pytest`，231 passed。
  - `docker compose config --quiet` 通过。
  - `docker compose up -d --build` 通过，backend/frontend 镜像完成构建并重建启动。
  - `docker compose ps` 显示 Redis/PostgreSQL healthy，backend、frontend、worker Up；Redis 未映射宿主机端口。
  - `docker compose logs --tail=100 redis migrate backend worker frontend postgres` 确认 migration `applied=0 skipped=5`，backend/frontend/worker 启动正常；PostgreSQL tail 中仍保留一条此前本地密码不匹配的历史认证失败日志，不属于本轮新增错误。
  - `docker compose exec -T redis redis-cli ping` 输出 `PONG`。
  - `curl -s http://127.0.0.1:8000/health` 返回 `status=healthy` 且 `dependencies.redis.status=healthy`。
  - `conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method compose` 通过，包括 Redis settings、Redis Compose service、Docker Compose config 和 migration dry-run。

## T-061 完成 Redis 场景 Docker 验证和核心链路回归

- 来源计划：`PLAN-20260705-01`
- 优先级：`P1`
- 状态：`Done`
- 背景：Redis 影响缓存、限流、worker 运行态和部署拓扑，必须在 Compose 环境下跑完整链路，而不能只依赖单元测试。
- 目标：完成 Redis 场景的 Docker Compose 验证和核心业务 smoke test，确认新增基础设施没有破坏登录、上传、向量化、聊天和 sources 展示。
- 范围：
  - 构建并启动包含 Redis 的 Compose 环境。
  - 验证登录限流、上传限流、重复 RAG 查询缓存命中、向量化 worker 心跳和 Redis health。
  - 覆盖 Redis 重启或不可用时的降级路径，确认系统按配置 fail-open 或 fail-closed。
  - 运行 RAG eval 和 indexing eval 基线，记录缓存命中、首 token、sources 和索引状态。
- 验收标准：
  - `redis`、`postgres`、`migrate`、`backend`、`worker`、`frontend` 均正常启动。
  - 登录、上传小文件、向量化、提问、SSE streaming 和 sources 展示通过。
  - Redis 故障场景有明确日志和用户可理解错误，不泄露 Redis URL、API Key、JWT 或数据库密码。
  - RAG eval 和 indexing eval 通过，或清楚记录失败 case、原因和回滚建议。
- 建议验证命令：

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 redis migrate backend worker frontend postgres

conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method compose

FIRSTRAG_EVAL_USERNAME=你的用户名 \
FIRSTRAG_EVAL_PASSWORD=你的密码 \
scripts/rag_eval_gate.sh

conda run -n firstrag python scripts/eval_indexing.py \
  --username 你的用户名 \
  --password 你的密码
```
- 实现/验收记录：
  - 相关 commit：`858e27f`。
  - Redis 场景完整 Docker 验证过程中发现并修复 worker runtime 熔断恢复问题：Redis 停止后 worker 每 2 秒心跳会不断续期 5 秒短熔断，导致 Redis 重启后 `online_worker_count` 长期为 0。
  - 修复点：`vector_worker_runtime_service` 对已打开的 runtime circuit 只返回 fallback reason，不再重复调用 `_mark_redis_unavailable` 延长熔断；新增单测覆盖“频繁心跳不应让熔断永久打开”。
  - Compose Redis 场景覆盖：构建启动、服务 health、Redis ping、backend `/health`、worker runtime online、Redis 停止降级、Redis 重启恢复 worker 心跳。
  - 认证/限流 smoke 覆盖：临时用户注册/登录成功；连续失败登录触发 Redis 分布式限流 429，`retry-after` 响应头存在。
  - 上传限流 smoke 覆盖：临时用户向默认知识库重复上传小文本文件，触发 Redis upload 限流 429，`retry-after` 响应头存在。
  - Redis cache adapter smoke 覆盖：容器内写入、读取、删除临时 JSON cache key，读取命中且 value 正确。
  - RAG/indexing 真实 eval 未运行：当前 `.env` 未配置 `FIRSTRAG_EVAL_USERNAME` / `FIRSTRAG_EVAL_PASSWORD`，自动化无法登录已有带模型配置的用户；临时用户没有聊天/embedding/rerank API Key，不能完成真实向量化和 SSE 回答。需补齐 eval 账号和用户模型配置后执行 `scripts/rag_eval_gate.sh` 与 `scripts/eval_indexing.py`。
- 已验证：
  - `docker compose up -d --build` 首次重建遇到 Docker registry mirror `403 Forbidden`，重试后通过；backend/frontend 镜像完成构建并重建启动。
  - `docker compose ps` 显示 Redis/PostgreSQL healthy，backend、frontend、worker Up；Redis 未映射宿主机端口。
  - `docker compose logs --tail=100 redis migrate backend worker frontend postgres` 确认 migration `applied=0 skipped=5`，backend/frontend/worker 启动正常；PostgreSQL tail 中仍有此前本地密码不匹配的历史认证失败日志，不属于本轮新增错误。
  - `conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method compose` 通过。
  - `curl -s http://127.0.0.1:8000/health` 返回 `status=healthy` 且 `dependencies.redis.status=healthy`。
  - `docker compose exec -T redis redis-cli ping` 输出 `PONG`。
  - `docker compose exec -T backend python -c "...get_vector_worker_runtime_summary..."` 返回 `redis_available=True`、`online_worker_count=1`。
  - Redis 停止时 `/health` 返回 `status=degraded`、`redis.status=unavailable`，错误摘要未泄露 Redis URL 或密码；Redis 重启后 `/health` 和 worker runtime 恢复健康。
  - `docker compose exec -T backend python -c "...cache_service..."` 临时 JSON key 读写删除通过。
  - `cd backend && conda run -n firstrag python -m pytest tests/test_vector_worker_runtime_service.py`，4 passed。
  - `cd backend && conda run -n firstrag python -m pytest`，232 passed。
  - `cd frontend && npm test`，51 passed。
  - `git diff --check` 通过。

## T-062 收口近期功能、Chroma 架构和任务台账

- 来源计划：`PLAN-20260720-01`
- 优先级：`P1`
- 状态：`Done`
- 目标：把 `T-061` 之后已经完成但尚未进入任务总览的功能、修复和真实验收结果收口到台账，并恢复计划、任务详情和当前代码基线的一致性。
- 范围：
  - 补录模型列表发现、LLM 生成控制/操作区布局、向量索引原文件名、聊天框图片粘贴、Chroma 短暂失败恢复、RAG fixture/真实复验和 Chroma client-server 架构修复。
  - 刷新后端、前端和 Docker Compose 当前验收基线。
  - 修正 `PLAN-20260703-01`、`T-051` 和 `T-052` 的状态关系；本地真实 eval 不再误记为已完成公网 smoke test。
  - 同步 staging/demo 任务中的独立 Chroma service、持久化和日志检查口径。
- 验收标准：
  - `T-061` 之后的相关提交在任务详情中可追溯。
  - 当前基线中的测试数量、Chroma 拓扑和真实索引回归结果与代码现状一致。
  - 计划总览、任务总览和任务详情中的状态一致。
  - 后端全量测试、前端测试/lint/build、Compose 配置和服务状态检查通过。
- 相关提交：
  - `663d769`：收口 Redis 计划状态。
  - `990ffbc`：恢复模型列表发现。
  - `0f8ef24`、`e4e2add`：将生成控制和聊天模型操作区归入 LLM 配置。
  - `984ad18`：向量索引保留原始文件名。
  - `daa16a7`：聊天输入框支持直接粘贴图片。
  - `8e7ce12`：Chroma 单文件 filter 短暂失败恢复。
  - `56b9294`、`666794a`：补充 RAG eval fixture 并记录 2026-07-20 真实复验。
  - `60fb271`：Compose 改用独立 Chroma server，修复 backend/worker 跨进程索引可见性。
- 完成记录：
  - 完成日期：2026-07-20。
  - `cd backend && conda run -n firstrag python -m pytest`：240 passed。
  - `cd frontend && npm test`：9 个 test files、52 passed。
  - `cd frontend && npm run lint`：0 error，保留 2 个 `<img>` 性能 warning。
  - `cd frontend && npm run build`：沙箱内因 Turbopack 辅助进程端口权限失败，按既有验证规则在非沙箱环境补跑后 production build 通过。
  - `docker compose config --quiet` 通过；`docker compose ps` 显示 Redis、PostgreSQL、Chroma healthy，backend、worker、frontend Up。
  - `conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method compose --skip-migration-dry-run` 通过。
  - Chroma 真实回归：worker 重建索引后 backend 未重启即可召回 16 条 vector 结果，`vector_degraded=false`、`vector_errors=[]`，目标资料同时命中 `fulltext` 与 `vector`。
- 验证命令：

```bash
git log --oneline --reverse 858e27f..HEAD
cd backend && conda run -n firstrag python -m pytest
cd frontend && npm test
cd frontend && npm run lint
cd frontend && npm run build
docker compose config --quiet
docker compose ps
docker compose logs --tail=100 redis postgres chroma migrate backend worker frontend
git diff --check
```

## T-063 将独立 Chroma 纳入 production preflight 与 acceptance check

- 来源计划：`PLAN-20260720-02`
- 优先级：`P1`
- 状态：`Done`
- 目标：让生产前置检查和一键验收主动发现 Chroma server 配置、Compose 拓扑、端口暴露、持久化或运行健康异常，防止 backend/worker 回退为共享 embedded 目录或连接不可用的 Chroma。
- 范围：
  - production preflight 校验 `CHROMA_HOST`、`CHROMA_PORT`、`CHROMA_SSL`。
  - 静态检查 Compose `chroma` service 的私网边界、healthcheck、日志轮转、`/data` 持久化，以及 backend/worker 的 HTTP client 与 `service_healthy` 依赖。
  - 增加可显式启用的 Chroma runtime health 检查，并接入 acceptance check 默认流程。
  - 为无 Docker 的纯静态场景保留明确 skip 开关。
  - 补充单元测试和部署/验收文档。
- 验收标准：
  - preflight 能拦截 localhost、非法端口/SSL、Chroma 公网端口、缺失 healthcheck/持久化及 backend/worker 共享 embedded 目录。
  - Chroma 容器未运行或非 healthy 时 runtime check 失败，正常运行时通过。
  - acceptance check 默认执行基础设施 preflight，并可通过显式参数跳过。
  - 后端相关测试、shell syntax、Compose、production preflight 和真实容器健康检查通过。
- 建议验证命令：

```bash
conda run -n firstrag python -m pytest backend/tests/test_production_preflight_script.py
bash -n scripts/acceptance_check.sh
docker compose config --quiet
conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method compose --skip-migration-dry-run --check-runtime-health
scripts/acceptance_check.sh --skip-real-eval --skip-frontend-build
git diff --check
```
- 完成记录：
  - 完成日期：2026-07-20。
  - `scripts/production_preflight.py` 新增 Chroma 连接参数、Compose service/client-server 拓扑和可选 runtime health 检查；错误输出不包含连接 secret。
  - `scripts/acceptance_check.sh` 默认执行 infrastructure preflight；无 Docker 的纯静态场景可显式使用 `--skip-infrastructure-check`。
  - `conda run -n firstrag python -m pytest backend/tests/test_production_preflight_script.py`：22 passed。
  - `cd backend && conda run -n firstrag python -m pytest`：247 passed。
  - `bash -n scripts/acceptance_check.sh` 与 `docker compose config --quiet` 通过。
  - `--skip-infrastructure-check` 与其它静态 skip 参数组合通过，确认无 Docker 场景仍可显式运行纯静态入口。
  - 带 `--check-runtime-health` 的真实 production preflight 通过，输出 `Chroma settings`、`Chroma Compose service`、`Chroma runtime health` 全部 pass。
  - `scripts/acceptance_check.sh --skip-real-eval --skip-frontend-build` 通过：infrastructure preflight、migration 文件、backend compileall、247 个 unittest、前端 lint 和 52 个 Vitest 用例均通过。
  - `docker compose up -d --build` 重建通过；Redis、PostgreSQL、Chroma healthy，backend、worker、frontend Up，migration `applied=0 skipped=5`，最近启动日志无新增错误。
  - README、Deployment、docker startup、eval 与 Agent 验收文档已同步新的 Chroma 门禁和 skip 边界。

## T-064 前端统一处理限流响应与重试倒计时

- 来源计划：`PLAN-20260720-03`
- 优先级：`P1`
- 状态：`Done`
- 目标：把后端 Redis 限流的 `Retry-After` 反馈完整传递到浏览器，让用户清楚知道何时可以重试，并避免倒计时期间重复提交。
- 范围：
  - Next.js API proxy 安全透传 `Retry-After`。
  - `FrontendApiError` 统一保存 `status` 和 `retryAfterSeconds`，429 文案补充明确剩余时间。
  - 增加按需启动、卸载时清理的共享倒计时 hook，不自动重放请求。
  - 登录、聊天、聊天图片上传、知识文件上传、单文件/整库向量化、聊天模型列表/连接测试、Embedding 测试和 Rerank 测试接入对应 scope 的按钮禁用与秒数提示。
  - 增加响应头透传、错误解析和 Retry-After 格式化测试，同步 API 与前端文档。
- 验收标准：
  - backend 返回 `429 + Retry-After` 后，浏览器响应保留该响应头。
  - 对应操作显示剩余秒数并禁用，倒计时结束后自动恢复；其它独立 scope 不受影响。
  - 模型列表与聊天模型测试共享倒计时，单文件与整库向量化共享倒计时，符合后端 scope 设计。
  - 倒计时不会自动重复发送请求，组件卸载后不会残留 timer。
  - 前端 test、lint、build 和 Docker Compose 相关验证通过。
- 相关提交：`0e2ec9d`。
- 完成记录：
  - 完成日期：2026-07-20。
  - `cd frontend && npm test`：10 个 test files、58 passed。
  - `cd frontend && npm run lint`：0 error，保留 2 个既有 `<img>` 性能 warning。
  - `cd frontend && npm run build`：沙箱内因 Turbopack 临时端口权限失败，沙箱外 production build 通过；Compose image build 同样通过 TypeScript 与 24 个静态页面生成。
  - `docker compose up -d --build`、`docker compose config --quiet` 通过；Redis、PostgreSQL、Chroma healthy，backend、worker、frontend Up，migration `applied=0 skipped=5`。
  - 真实 proxy smoke：随机不存在账号经 `http://127.0.0.1:3000/api/login` 连续失败，前 5 次为 401，第 6 次为 `429 + Retry-After: 300`。
  - 浏览器 UI smoke：登录限流后错误文案显示剩余秒数，提交按钮显示倒计时并保持 disabled，随后秒数正常递减。
- 建议验证命令：

```bash
cd frontend && npm test
cd frontend && npm run lint
cd frontend && npm run build
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 backend frontend redis
git diff --check
```

## T-065 增加限流命中和 Redis 故障可观测性

- 来源计划：`PLAN-20260720-04`
- 优先级：`P1`
- 状态：`Done`
- 目标：让运维可以从统一结构化日志区分并聚合正常额度耗尽、Redis fail-open fallback 和 fail-closed 阻断，同时看见实际限额、窗口和重试时间。
- 范围：
  - 限流命中输出 `rate_limit_exceeded` 事件，包含安全且有界的 `scope`、`backend`、`reason`、`failure_mode`、`limit`、`window_seconds` 和 `retry_after_seconds`。
  - Redis 调用失败的 `rate_limit_redis_failed` 事件补齐 `outcome`、`consume`、限额和窗口字段，区分 `memory_fallback` 与 `request_blocked`。
  - 日志不记录限流 identifier，避免泄露 IP、username、user_id 或 Redis bucket hash。
  - 文档补充事件字段、日志查询示例和建议告警阈值；不新增公开 metrics 接口。
- 验收标准：
  - Redis、memory 和 memory fallback 路径的真实阻断均产生单次可聚合命中事件。
  - Redis 故障事件能区分 fail-open 与 fail-closed，且不会泄露 Redis URL、密码或 identifier。
  - 后端限流、认证和 observability 回归测试通过；Compose 日志 smoke 能观察到结构化事件。
- 相关提交：`6328c3b`。
- 完成记录：
  - 完成日期：2026-07-20。
  - `rate_limit_exceeded` 统一记录 `scope`、`backend`、`outcome`、`reason`、`failure_mode`、`consume`、`limit`、`window_seconds` 和 `retry_after_seconds`，正常额度耗尽标记为 `quota_exceeded`，Redis fail-closed 阻断标记为 `redis_unavailable`。
  - `rate_limit_redis_failed` 补齐 `memory_fallback` / `request_blocked` outcome 和当前限额配置；事件沿用 observability 脱敏规则，不记录 identifier、IP、username、user_id、Redis key 或连接串。
  - `docs/DEPLOYMENT.md` 已补充事件字典、最小监控面板、告警建议和本地日志查询命令；不新增公网 metrics 接口。
  - `cd backend && conda run -n firstrag python -m pytest tests/test_rate_limit.py tests/test_auth_rate_limit.py tests/test_chat_settings.py tests/test_knowledge_files.py tests/test_vector_indexes.py tests/test_user_settings.py tests/test_observability.py`：52 passed。
  - `cd backend && conda run -n firstrag python -m pytest`：247 passed。
  - `docker compose build frontend backend`、`docker compose up -d --force-recreate backend worker frontend` 通过；Redis、PostgreSQL、Chroma healthy，backend、worker、frontend Up，frontend 启动日志确认 Next.js 16.2.10。
  - 真实额度命中 smoke：连续 6 次无效登录返回前 5 次 401、第 6 次 `429 + Retry-After: 300`；backend 生成 `rate_limit_exceeded`，字段为 `scope=login-failures`、`backend=redis`、`reason=quota_exceeded`、`limit=5`、`window_seconds=300`。
  - 真实 Redis 故障 smoke：短暂停止 Redis 后登录返回 `429 + Retry-After: 60`；backend 同时生成 `rate_limit_redis_failed(outcome=request_blocked)` 和 `rate_limit_exceeded(reason=redis_unavailable)`，Redis 随后恢复 healthy，`GET /health` 返回 `status=healthy`。
  - 安全前置审计提交：`49cfa9b` 将 Next.js / eslint-config-next 升级到 16.2.10；`e1c1b60` 修复可安全更新的开发依赖。前端 58 个 Vitest、lint（0 error，2 个既有 warning）和 production build 通过。
- 建议验证命令：

```bash
cd backend
conda run -n firstrag python -m pytest \
  tests/test_rate_limit.py \
  tests/test_auth_rate_limit.py \
  tests/test_observability.py

cd ..
docker compose up -d --build
docker compose logs backend | rg '"event":"rate_limit_exceeded"|"event":"rate_limit_redis_failed"'
git diff --check
```

## T-066 将依赖漏洞审计和例外复查固化到 CI

- 来源计划：`PLAN-20260720-05`
- 优先级：`P1`
- 状态：`Done`
- 目标：让前端 production dependency 新漏洞在合并前被自动发现和阻断，同时避免已 triage 的 PostCSS finding 变成永久白名单。
- 范围：
  - CI 在 pull request、`main` push、手动触发和每周计划任务中运行 npm production dependency audit。
  - `high` / `critical` 永远阻断；未登记的 `moderate` 阻断；`low` / `info` 只提示。
  - 安全例外必须精确匹配 advisory ID、package 和 severity，记录 `reviewed_on`、`expires_on` 与原因，最长有效 31 天。
  - 例外过期、severity 上升、上游修复后遗留无效例外、npm audit 网络/解析失败均阻断。
  - 为策略解析、强阻断、到期和 stale exception 增加单元测试与维护文档。
- 验收标准：
  - 当前 Next.js 16.2.10 production audit 仅通过明确的 PostCSS 限时例外。
  - 模拟 high、未登记 moderate、过期例外和 stale exception 时策略返回失败。
  - CI workflow YAML、策略测试、前端 test/lint/build 和 Compose 验证通过。
- 相关提交：`a948662`。
- 完成记录：
  - 完成日期：2026-07-20。
  - 新增 `scripts/npm_audit_policy.py`，直接运行 `npm audit --omit=dev --json`；registry、命令或 JSON 异常返回错误，不会被误判为零 finding。
  - 策略按实际 advisory 去重；`high` / `critical` 永远阻断，缺少 advisory 对象的 high/critical 传播节点也会保守阻断；未登记 moderate 阻断，low/info 只提示。
  - 新增 `security/npm-audit-exceptions.json` 和维护说明；例外精确匹配 advisory ID、package、severity，最长有效 31 天，过期、severity 变化或 finding 消失后未清理均阻断。
  - PostCSS `GHSA-QX2V-QP2M-JG93` 例外复查截止日为 2026-08-20；只覆盖 `postcss / moderate`，不能覆盖 Next.js 其它 finding。
  - `.github/workflows/ci.yml` 在 PR、`main` push、手动触发和每周一 `01:17 UTC` 定时任务中执行 production dependency audit policy。
  - `python3 scripts/npm_audit_policy.py` 真实在线审计通过，输出 `PASS findings=1 exceptions=1`，唯一 finding 由精确 PostCSS 限时例外放行。
  - `conda run -n firstrag python -m pytest backend/tests/test_npm_audit_policy_script.py`：9 passed；覆盖有效/过期例外、不可豁免 high、字符串传播 high、未登记 moderate、stale exception、severity 变化和最长 31 天限制。
  - `cd backend && conda run -n firstrag python -m pytest`：256 passed。
  - `cd frontend && npm test`：58 passed；`npm run lint`：0 error、2 个既有 `<img>` warning；`npm run build`：Next.js 16.2.10 production build 通过。
  - CI workflow YAML、`docker compose config --quiet` 和 `git diff --check` 通过。
  - `docker compose up -d --build` 通过；Redis、PostgreSQL、Chroma healthy，backend、worker、frontend Up，migration `applied=0 skipped=5`，最近启动日志无新增错误，`GET /health` 返回 healthy。
- 建议验证命令：

```bash
conda run -n firstrag python -m pytest backend/tests/test_npm_audit_policy_script.py
conda run -n firstrag python scripts/npm_audit_policy.py
ruby -e 'require "yaml"; YAML.load_file(".github/workflows/ci.yml"); puts "workflow yaml ok"'
cd frontend && npm test && npm run lint && npm run build
cd .. && docker compose up -d --build
git diff --check
```

## T-067 增加 Python 依赖和 Docker 镜像漏洞 CI 门禁

- 来源计划：`PLAN-20260720-06`
- 优先级：`P1`
- 状态：`Done`
- 目标：让后端 Python production dependencies 和第一方 Docker 镜像中的 OS package 漏洞在合并前自动阻断，并为当前上游无修复版本的 ChromaDB finding 建立可自动到期的审查边界。
- 范围：
  - 使用固定版本 `pip-audit` 严格审计 `backend/requirements.txt`。
  - 有修复版本的 Python finding 禁止例外；no-fix finding 只有完成 triage 后才能登记精确到 advisory/package/version、最长 31 天的例外。
  - 升级当前可修复的 PyJWT、python-dotenv 和 python-multipart 漏洞。
  - 构建当前 backend/frontend Dockerfile，并用固定 SHA 的 Trivy Action 扫描 OS packages。
  - Trivy 阻断有修复版本的 `HIGH` / `CRITICAL`，Python/npm library findings 继续由各自专用策略负责。
- 验收标准：
  - 真实 `pip-audit` 只保留已 triage、未过期且精确匹配的 ChromaDB no-fix finding。
  - 可修复漏洞、未登记 no-fix、过期/版本不匹配/stale exception、scanner/resolver 失败都能阻断。
  - backend/frontend 当前镜像没有可修复的 high/critical OS finding。
  - CI workflow YAML、全量后端测试、Docker Compose build/health 和相关日志检查通过。
- 相关提交：`fd18c44`。
- 完成记录：
  - 完成日期：2026-07-20。
  - PyJWT `2.12.1 -> 2.13.0`、python-dotenv `1.2.1 -> 1.2.2`、python-multipart `0.0.30 -> 0.0.31`；对应可修复 finding 已从真实审计中消失。
  - 新增 `scripts/pip_audit_policy.py` 和 10 个策略测试；`pip-audit==2.10.1 --strict` 的真实在线审计输出 `PASS findings=1 exceptions=1`。
  - `GHSA-F4J7-R4Q5-QW2C / chromadb / 1.5.9` 当前没有修复版本。静态 triage 确认 FirstRAG Compose 不映射 Chroma 端口、Nginx 没有 Chroma upstream、业务代码不接收 `model repository + trust_remote_code` collection configuration，因此保留至 2026-08-20 的限时例外；部署若额外暴露 Chroma，例外立即失效。
  - Trivy Action 使用 `v0.36.0` 完整 commit SHA，Trivy 固定 `v0.72.0`；真实扫描 backend Debian 13.6 和 frontend Debian 12.15，符合门禁范围的 finding 均为 0。
  - `cd backend && conda run -n firstrag python -m pytest -q`：266 passed、28 subtests passed。
  - `docker compose up -d --build` 通过；Redis、PostgreSQL、Chroma healthy，backend、worker、frontend Up，migration `applied=0 skipped=5`，`GET /health` 返回 healthy。
  - CI workflow YAML、Python compileall、`docker compose config --quiet` 和 `git diff --check` 通过。
- 建议验证命令：

```bash
conda run -n firstrag python -m pytest backend/tests/test_pip_audit_policy_script.py
conda run -n firstrag python scripts/pip_audit_policy.py
cd backend && conda run -n firstrag python -m pytest -q
cd .. && docker compose up -d --build
trivy image --scanners vuln --pkg-types os --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 firstrag-backend:latest
trivy image --scanners vuln --pkg-types os --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 firstrag-frontend:latest
docker compose ps
docker compose logs --tail=100 migrate backend worker frontend postgres redis chroma
git diff --check
```

## T-068 固定 GitHub Actions SHA 并启用 Dependabot 更新

- 来源计划：`PLAN-20260720-07`
- 优先级：`P1`
- 状态：`Done`
- 目标：消除 GitHub Actions tag/branch 可移动引用带来的 workflow supply chain 风险，同时保留可审查、可持续更新的维护路径。
- 范围：
  - 将 checkout、setup-python、setup-node 和 Trivy Action 全部固定到官方稳定 release 对应的 40 位 commit SHA。
  - 同一行保留精确 release tag 注释，供人工审查和 Dependabot 更新版本说明。
  - 增加自动扫描所有 workflow/reusable workflow 引用的 SHA pin policy。
  - 新增 `github-actions` Dependabot weekly update，将多个 Action 更新聚合为一个 PR，不自动合并。
  - 同步 CI、deployment 与 security 维护文档。
- 验收标准：
  - 当前所有外部 `uses:` 均为完整 SHA，tag、branch、短 SHA 和缺失 release 注释会失败。
  - Dependabot 配置能覆盖 `.github/workflows`，使用明确时区、频率和 PR 上限。
  - actionlint、YAML 解析、策略测试、全量后端回归和 Docker Compose 验证通过。
- 相关提交：`06c9b61`。
- 完成记录：
  - 完成日期：2026-07-20。
  - 从官方 repository tag 解析并固定：checkout `v6.0.2 -> de0fac2e4500dabe0009e67214ff5f5447ce83dd`、setup-python `v6.3.0 -> ece7cb06caefa5fff74198d8649806c4678c61a1`、setup-node `v6.2.0 -> 6044e13b5dc448c55e2357c09f80417699197238`；Trivy 继续固定 `v0.36.0` 的完整 SHA。
  - `scripts/check_github_actions_pins.py` 扫描 workflow 和 reusable workflow；当前输出 `PASS references=7`。6 个单元测试覆盖完整 SHA、tag、短 SHA、缺失版本注释、引号语法和本地 Action 边界。
  - `.github/dependabot.yml` 每周一 09:00（Asia/Shanghai）检查 `github-actions`，最多保留 5 个 update PR，并将 Action updates 聚合为单个 PR。
  - actionlint 1.7.12、CI/Dependabot YAML 解析、`docker compose config --quiet` 和 `git diff --check` 通过。
  - `cd backend && conda run -n firstrag python -m pytest -q`：272 passed、28 subtests passed。
  - `docker compose up -d --build` 通过；Redis、PostgreSQL、Chroma healthy，backend、worker、frontend Up，migration `applied=0 skipped=5`，最近启动日志无错误，`GET /health` 返回 healthy。
- 建议验证命令：

```bash
conda run -n firstrag python scripts/check_github_actions_pins.py
conda run -n firstrag python -m pytest backend/tests/test_github_actions_pins_script.py
actionlint .github/workflows/ci.yml
ruby -e 'require "yaml"; YAML.load_file(".github/workflows/ci.yml"); YAML.load_file(".github/dependabot.yml")'
cd backend && conda run -n firstrag python -m pytest -q
cd .. && docker compose up -d --build
docker compose ps
docker compose logs --since=10m migrate backend worker frontend postgres redis chroma
git diff --check
```

## T-069 补齐知识库和知识文件完整生命周期

- 来源计划：`PLAN-20260721-01`
- 优先级：`P1`
- 状态：`Done`
- 目标：让用户能够安全地管理知识库和全局知识文件，补齐重命名、回收站恢复与永久删除能力，并避免删除后遗留向量、全文分块、任务或磁盘文件。
- 范围：
  - 支持知识库重命名、软删除、回收站列表和恢复；默认知识库禁止删除。
  - 删除知识库只隐藏知识库及其会话，不连带删除仍可复用的用户文件。
  - 支持用户永久删除知识文件，并同步清理知识库关联、active jobs、PostgreSQL chunks、Chroma vectors、历史 source 引用和磁盘文件。
  - 前端知识库管理和文件管理弹窗提供对应操作、影响范围提示、二次确认和错误反馈。
  - 同步更新 API、Schema、Frontend 文档和回归测试。
- 验收标准：
  - 跨用户资源统一返回 `404`；默认知识库删除返回清晰 `400`。
  - 已删除知识库不会出现在活动列表，恢复后原会话和文件关联重新可见。
  - 永久删除文件后无法再查询或复用，相关向量、chunks、jobs、source feedback 和磁盘文件均已清理。
  - 后端、前端测试和 build 通过，Docker Compose 服务健康，production preflight 通过。
- 相关提交：`ac4397b`。
- 完成记录：
  - 完成日期：2026-07-21。
  - 后端新增知识库重命名、回收站列表、软删除和恢复 API；默认知识库删除返回 `400`，所有生命周期查询和写入均按当前 `user_id` 隔离。
  - 新增知识文件永久删除 service：在 file index lock 内取消 active jobs、删除 Chroma vectors，并事务性清理知识库关联、PostgreSQL chunks、vector jobs、source feedback、历史 `messages.sources` 和主文件记录，最后删除受 uploads 根目录约束的磁盘文件。
  - 前端知识库管理弹窗支持重命名、移入回收站和恢复；文件管理弹窗提供带影响范围说明和二次确认的永久删除操作，并统一展示进行中、成功和失败反馈。
  - 真实 API smoke 使用一次性知识库和 Markdown 文件验证登录、重命名、回收站可见性、恢复、默认知识库保护、异步向量化成功和跨存储永久删除；测试后知识库与文件残留计数均为 0。
  - `cd backend && conda run -n firstrag python -m pytest -q`：282 passed、8 warnings、28 subtests passed。
  - `cd frontend && npm test -- --run`：10 个 test files、61 tests passed；`npm run lint`：0 error、保留 2 个既有 `<img>` performance warnings；Next 16.2.10 production build 通过。
  - `docker compose up -d --build`、`docker compose ps -a` 和最近 10 分钟关键服务日志通过：Redis、PostgreSQL、Chroma healthy，backend、worker、frontend Up，migration `applied=0 skipped=5`。
  - `conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method compose --check-runtime-health` 全部通过；`docker compose config --quiet` 和 `git diff --check` 通过。
- 建议验证命令：

```bash
cd backend && conda run -n firstrag python -m pytest -q
cd ../frontend && npm test && npm run lint && npm run build
cd .. && docker compose up -d --build
docker compose ps
docker compose logs --tail=100 redis postgres chroma migrate backend worker frontend
conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method compose --check-runtime-health
git diff --check
```

## T-070 实现来源原文预览与精确引用跳转

- 来源计划：`PLAN-20260721-02`
- 优先级：`P1`
- 状态：`Done`
- 目标：让用户可以从回答引用直接核验目标 chunk 的完整正文和相邻上下文，并在权限校验后打开原始知识文件。
- 定位边界：当前索引数据没有稳定的 PDF 页码或字符 offset，本任务以 `file_id + chunk_index + index_version` 作为可验证的精确定位键，不展示无法保证准确的页码；旧 source 缺少版本时回退到最新可用 chunk 版本。
- 范围：
  - 后端增加目标 chunk 上下文 API，按当前用户、文件和索引版本查询目标 chunk 及相邻 chunks。
  - 后端增加原始知识文件内容 API，校验文件所属用户并限制磁盘路径位于 uploads 根目录。
  - 前端引用卡片增加“查看原文”操作，按需打开独立预览弹窗并高亮目标 chunk。
  - 预览弹窗支持浏览相邻 chunk、展示可用的标题层级元数据，并安全打开原始文件。
  - 预览组件动态加载，chunk 请求使用 React Query 缓存和去重，避免增加聊天首屏 bundle 和重复请求。
  - 同步更新 API、Frontend、RAG workflow 文档和回归测试。
- 验收标准：
  - 当前用户只能读取自己的文件和 chunks，跨用户或不存在资源统一返回 `404`。
  - API 不返回磁盘 `storage_path`；原始文件路径越界或文件缺失时安全失败。
  - 点击引用后准确高亮 source 对应的 `chunk_index`，并展示至少一个相邻 chunk（存在时）。
  - 历史引用缺少 `file_id` 或 `chunk_index` 时不展示不可用操作，保留现有引用内容。
  - 后端、前端测试和 production build 通过，Docker Compose 真实 smoke 能读取目标 chunk、拒绝跨用户访问并打开原始文件。
- 相关提交：`11ed2e4`。
- 完成记录：
  - 完成日期：2026-07-21。
  - 新生成的 source 现在持久化 `index_version`；后端 chunk context API 使用 `file_id + chunk_index + index_version` 查询目标及相邻 chunks，旧 source 缺少版本时回退到最新可用 chunk 版本。
  - chunk API 只返回正文、目标标记和 `h1`-`h6`/可用页码白名单 metadata，不暴露 `storage_path`；跨用户、文件不存在或指定版本不可用统一返回 `404`。
  - 原始文件 API 复用 uploads 路径边界校验，不信任上传 Content-Type，按扩展名返回安全 MIME，并设置 `Content-Security-Policy: sandbox` 与 `X-Content-Type-Options: nosniff`。
  - 前端引用卡片增加“查看原文”，`SourcePreviewDialog` 使用 dynamic import 按需加载，并通过 React Query 缓存和去重；弹窗自动定位、高亮目标 chunk、展示相邻正文和标题层级，可使用带 Authorization 的 blob 请求打开原始文件。
  - 真实 Compose smoke 使用一次性 Markdown、知识库和第二用户完成异步向量化，目标定位为 Chunk #1 / index version 0；backend context、Next proxy、原始文件安全响应均通过，第二用户访问 context/content 均返回 `404`。
  - smoke 诊断阶段产生的一次性用户和知识库已精确清理；最终测试用户、知识库和文件残留计数均为 0。
  - `cd backend && conda run -n firstrag python -m pytest -q`：287 passed、8 warnings、28 subtests passed；Python compileall 通过。
  - `cd frontend && npm test -- --run`：10 个 test files、63 tests passed；`npm run lint`：0 error、保留 2 个既有 `<img>` performance warnings；Next 16.2.10 production build 通过。
  - `docker compose up -d --build` 通过；Redis、PostgreSQL、Chroma healthy，backend、worker、frontend Up，migration `applied=0 skipped=5`，最近日志只有预期 smoke 请求和跨用户 `404`。
  - production preflight、Docker Compose config、Chroma runtime health、migration dry-run 和 `git diff --check` 全部通过。
- 建议验证命令：

```bash
cd backend && conda run -n firstrag python -m pytest -q
cd ../frontend && npm test -- --run && npm run lint && npm run build
cd .. && docker compose up -d --build
docker compose ps -a
docker compose logs --since=10m redis postgres chroma migrate backend worker frontend
conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method compose --check-runtime-health
git diff --check
```

## T-071 持久化 PDF 页码和 DOCX 段落位置

- 来源计划：`PLAN-20260721-03`
- 优先级：`P1`
- 状态：`Done`
- 目标：让新索引的 PDF/DOCX source 携带可验证的位置 metadata，使引用弹窗能展示真实页码或段落范围，并在打开 PDF 时跳到对应页面。
- 位置语义：
  - PDF 使用解析器逐页输出的 1-based `page_number`，并保留 0-based `page_index` 供内部诊断。
  - DOCX 从 OOXML 文档顺序提取 1-based `paragraph_start` / `paragraph_end`；空段落不进入正文，但原始序号保持不变。
  - PDF 原始文件可使用 `#page=N` 打开到目标页；DOCX 浏览器无法可靠控制 Word 内部光标，只在内置弹窗高亮目标 chunk 并展示段落范围。
- 范围：
  - PDF 改为 `page_chunks=True` 逐页加载，页码 metadata 随 split、PostgreSQL chunks、Chroma vectors 和 sources 持久化。
  - DOCX 从 `word/document.xml` 提取正文段落和 heading style，在不拆散普通短段落的前提下按段落边界组块。
  - 多页/多 block 文档按 `user_id + file_id` 分配全局稳定 chunk index，避免页内 chunk index 重复。
  - source serializer、chunk preview API 和前端类型扩展页码、页索引与段落范围字段。
  - 引用卡片和原文弹窗展示真实位置；打开 PDF 时附加页码 fragment，DOCX 保持安全下载/打开行为。
  - 同步更新 API、Schema、Frontend、RAG workflow、Architecture 文档和回归测试。
- 验收标准：
  - 3 页 PDF 的每个 chunk 保留正确页码，来源定位到第 2 页时打开 URL 包含 `#page=2`。
  - DOCX chunks 的段落范围单调、无越界，目标正文能对应到实际 OOXML 段落序号。
  - 同一 PDF/DOCX 文件的 chunk index 全局唯一且连续，不因 page/block 重置。
  - 现有 Markdown、TXT、图片解析与索引行为保持兼容。
  - 测试、production build、Docker Compose 真实 PDF/DOCX indexing smoke 和 production preflight 通过。
- 相关提交：`d03de10`。
- 完成记录：
  - 完成日期：2026-07-21。
  - PDF 使用 `pymupdf4llm page_chunks=True` 逐页解析，保存 0-based `page_index`、1-based `page_number` 和 `page_count`；DOCX 直接读取 OOXML 主文档，按标题与字符上限组成 block，并保留包含空段落间隔的 1-based 段落范围。
  - `split_documents` 按 `user_id + file_id` 为跨 page/block 的 chunks 分配全局连续序号，位置 metadata 随 PostgreSQL、Chroma、source serializer 和会话诊断完整传递。
  - chunk preview API 白名单扩展 PDF/DOCX 位置字段；真实 smoke 同时发现并修复了未指定 `index_version` 时 PostgreSQL 无法推断 NULL 参数类型的问题，查询参数现显式转换为 `integer`。
  - 前端来源卡片与原文弹窗展示页码或段落范围，目标 chunk 延续高亮和自动滚动；PDF blob URL 使用 `#page=N` 打开目标页，DOCX 保持内置 chunk 高亮与安全原文件打开行为。
  - 真实三页 PDF 完成 Poppler 渲染和逐页目检，三页标题、页序及预期 metadata 均清晰正确。
  - Docker Compose 真实 smoke 使用一次性 PDF/DOCX 完成上传、异步向量化和 chunk preview：PDF 页码为 1/2/3，DOCX 段落范围为 1-2、4-5，chunk index 连续；两份文件永久删除返回 200，最终 PostgreSQL files/chunks/jobs 和 Chroma vectors 残留计数均为 0。
  - `cd backend && conda run -n firstrag python -m pytest -q`：289 passed、8 warnings、28 subtests passed。
  - `cd frontend && npm test -- --run`：10 个 test files、66 tests passed；`npm run lint`：0 error、保留 2 个既有 `<img>` performance warnings；Next 16.2.10 production build 通过。
  - `docker compose up -d --build`、`docker compose ps -a` 和最近关键服务日志通过：Redis、PostgreSQL、Chroma healthy，backend、worker、frontend Up，migration `applied=0 skipped=5`。
  - production preflight、Docker Compose config、Chroma runtime health、migration dry-run 和 `git diff --check` 全部通过。
- 建议验证命令：

```bash
cd backend && conda run -n firstrag python -m pytest -q
cd ../frontend && npm test -- --run && npm run lint && npm run build
cd .. && docker compose up -d --build
docker compose ps -a
docker compose logs --since=10m redis postgres chroma migrate backend worker frontend
conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method compose --check-runtime-health
git diff --check
```

## T-072 为扫描 PDF 增加本地 OCR fallback

- 来源计划：`PLAN-20260721-04`
- 优先级：`P1`
- 状态：`Done`
- 目标：让图片型、无可复制文本层的 PDF 也能进入现有 RAG 索引，并继续提供准确的页码级引用定位。
- 技术边界：
  - 优先使用 `pymupdf4llm` 原生文本；仅低于有效文本阈值的页面渲染为 PNG 并调用本地 Tesseract。
  - OCR 运行在 backend/worker 容器内，不发送到用户 LLM 或第三方 OCR API，不消耗模型额度。
  - 默认识别 `chi_sim+eng`，DPI、语言、单页超时、最少原生文本字符数和单文件最大 OCR 页数均可通过环境变量调整。
  - 超过 OCR 页数上限、Tesseract/语言包不可用或单页超时时，任务返回可理解且不泄露内部路径的失败分类。
- 范围：
  - 扩展 PDF 逐页解析，对无文本层页面执行本地 OCR，并记录 `pdf_parse_method`、OCR engine/languages/DPI metadata。
  - 保持 T-071 的 `page_index/page_number/page_count` 和跨页连续 chunk index 语义。
  - Docker backend image 安装 Tesseract 与简体中文/英文语言数据；本地 conda 调试复用系统 Tesseract。
  - 增加 OCR 配置样例、失败提示、单元测试、真实扫描 PDF smoke 和相关文档。
- 验收标准：
  - 原生文本 PDF 不调用 OCR，现有解析结果和性能路径保持兼容。
  - 至少一份纯图片三页 PDF 能识别目标文字，chunks 保留 1/2/3 页码且 source 可定位对应页面。
  - 混合 PDF 只 OCR 扫描页，原生文本页继续标记为 `native_text`。
  - OCR 不可用、超时或页数超限时任务给出稳定恢复提示，worker 能继续处理后续任务。
  - 后端、前端测试、production build、Docker Compose smoke 和 production preflight 通过。
- 相关提交：`2a9ef37`。
- 完成记录：
  - 完成日期：2026-07-21。
  - PDF 解析显式关闭 `pymupdf4llm` 隐式 OCR，先读取逐页原生文本，仅对低于有效字符阈值的页面按配置 DPI 渲染 PNG 并调用本地 Tesseract；原生文本页和 OCR 页分别标记为 `native_text` 与 `ocr`。
  - 新增 OCR 开关、语言、DPI、单页超时、原生文本阈值和单文件最大 OCR 页数配置；语言参数不经过 shell，缺失引擎、超时、页数超限和识别失败统一归类为安全的 `ocr_error`。
  - OCR metadata 随 PostgreSQL chunks、Chroma vectors、source serializer 和 chunk preview 传递；前端引用卡片和原文弹窗会显示“OCR 识别”，同时继续使用 T-071 的真实页码定位。
  - backend/worker 镜像安装 Tesseract 5.5.0 及 `chi_sim`、`eng` 语言包；Compose 首次构建和 Next.js 16.2.10 production build 通过。
  - 三页纯图片 PDF 已通过 Poppler 逐页渲染和目视检查；本机与 Compose worker 均准确识别三页目标文字，真实异步任务一次成功，chunk 页码为 1/2/3，第二页包含 `PRECISE TARGET`。
  - 真实账号 smoke 完成登录、上传、异步 OCR 索引、三个 chunk preview 和永久删除；清理后 PostgreSQL files/chunks/jobs 与 Chroma vectors 残留计数均为 0。
  - `cd backend && conda run -n firstrag python -m pytest -q`：292 passed、8 warnings、30 subtests passed。
  - `cd frontend && npm test -- --run`：10 个 test files、66 tests passed；`npm run lint`：0 error、保留 2 个既有 `<img>` performance warnings。
  - `docker compose ps -a` 和最近 10 分钟日志通过：Redis、PostgreSQL、Chroma healthy，backend、worker、frontend Up，migration `applied=0 skipped=5`；日志只包含预期 smoke 请求。
  - production preflight、Docker Compose config、Chroma runtime health、migration dry-run 和 `git diff --check` 全部通过。
- 建议验证命令：

```bash
cd backend && conda run -n firstrag python -m pytest -q
cd ../frontend && npm test -- --run && npm run lint && npm run build
cd .. && docker compose up -d --build
docker compose ps -a
docker compose logs --since=10m redis postgres chroma migrate backend worker frontend
conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method compose --check-runtime-health
git diff --check
```

## T-073 增加 OCR 质量诊断与单页重新识别

- 来源计划：`PLAN-20260721-05`
- 优先级：`P1`
- 状态：`Done`
- 完成日期：`2026-07-21`
- 目标：让用户能够判断扫描 PDF 页面的 OCR 可靠程度，并对可疑页面发起可追踪的异步重新识别。
- 技术边界：
  - Tesseract 单次识别同时输出文本和 TSV word confidence，避免为了置信度重复执行 OCR。
  - 页面置信度按有效 word 字符长度加权，阈值可配置；没有有效 word confidence 时不伪造分数。
  - 单页重新识别通过已有 `vector_index_jobs` 异步执行，API 不同步承担 OCR、embedding 或向量写入。
  - 重新识别会递增文件索引版本并重建该文件索引；历史回答引用不被静默改写，用户需重新提问生成新引用。
- 范围：
  - 新增 `ocr_confidence`、`ocr_quality`、`ocr_word_count` 和 `ocr_attempt` metadata，并贯通 chunk、Chroma、source 和 preview。
  - 为 vector index job 增加受限 `options`，仅允许 worker 接收经过后端构造的强制 OCR 页码。
  - 增加当前用户 PDF 页面的重新识别 API，校验文件类型、索引状态、页码和现有 OCR metadata。
  - 原文预览展示 OCR 百分比和低质量告警，并提供排队、处理中、成功、失败反馈。
  - 同步更新 migration、API、Schema、Frontend、RAG workflow、Deployment 文档和回归测试。
- 验收标准：
  - 清晰扫描页持久化 0-100 置信度且识别文本不因 TSV 输出发生退化。
  - 低于阈值的页面在引用卡片和原文预览中有明确警告；原生文本页不展示 OCR 分数。
  - 跨用户、非 PDF、非 OCR 页、越界页或非 indexed 文件不能发起重新识别。
  - 单页操作生成新 index version 的异步任务，worker 消费强制页选项并成功重建索引。
  - 后端、前端测试、production build、Docker Compose migration/smoke 和 production preflight 通过。
- 相关提交：`729e575`。
- 完成记录：
  - Tesseract 每页只执行一次，使用 `txt` 与 `tsv` 两个 output renderer 同时生成正文和 word confidence；页面置信度按有效字符数加权，保存 `ocr_confidence`、`ocr_quality`、`ocr_word_count` 和 `ocr_attempt`，没有有效分数时明确标记 `unknown`。
  - 新增 `PDF_OCR_LOW_CONFIDENCE_THRESHOLD`，引用卡片和原文预览展示 OCR 百分比与低质量警告；弹窗支持提交、排队、处理中、成功、失败、失败重试和查询重试状态，且不会用装饰动画干扰阅读。
  - migration `005_add_vector_index_job_options.sql` 为 vector job 增加内部 `JSONB options`；单页 API 只允许当前用户、已完成索引且现有 metadata 为 OCR 的 PDF 页面，worker 从受控 options 读取强制页并异步重建整个文件索引。
  - 真实两页纯图片 PDF 已通过 Poppler 渲染目检；本机 Tesseract 同次正文/TSV 验证得到 89.30 与 95.35 的页级置信度，文本和 word count 均正常。
  - Docker Compose 真实账号 smoke 完成上传、首次 OCR 索引、第 2 页重新识别、重复提交冲突和永久删除：两次任务均为 `succeeded`，重复提交返回 `409`，index version 从 0 升到 1，第 2 页 `ocr_attempt` 从 1 升到 2；数据库测试文件残留为 0。
  - `cd backend && conda run -n firstrag python -m pytest -q`：302 passed、8 warnings、30 subtests passed；T-073 最终专项回归 8 passed。
  - `cd frontend && npm test -- --run`：10 个 test files、67 tests passed；`npm run lint`：0 error、保留 2 个既有 `<img>` performance warnings；Next 16.2.10 production build 通过。
  - `docker compose up -d --build`、`docker compose ps` 和近期日志通过；migration 首次应用 005，最终重建为 `applied=0 skipped=6`，backend、worker、frontend 均正常启动，Redis、PostgreSQL、Chroma healthy。
  - production preflight、Chroma runtime health、migration dry-run、数据库 `options:jsonb` 检查和 `git diff --check` 全部通过。
- 建议验证命令：

```bash
cd backend && conda run -n firstrag python -m pytest -q
cd ../frontend && npm test -- --run && npm run lint && npm run build
cd .. && docker compose up -d --build
docker compose ps -a
docker compose logs --since=10m redis postgres chroma migrate backend worker frontend
conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method compose --check-runtime-health
git diff --check
```

## T-074 支持 OCR 页面人工校对并重新索引

- 来源计划：`PLAN-20260721-06`
- 优先级：`P1`
- 状态：`Done`
- 目标：允许用户在原文预览中修正 OCR 页面文本，把修订持久化并安全重建索引，同时保留原始 OCR 质量信息和历史引用版本。
- 技术边界：
  - 人工修订按 `user_id + knowledge_file_id + page_number` 持久化，不直接原地修改已有 chunks 或历史 message sources。
  - worker 每次索引仍执行原始 PDF OCR，并在切分前用当前有效人工修订覆盖页面正文；metadata 同时保留 OCR 置信度与人工修订版本。
  - 保存或撤销修订均递增文件 index version，通过现有 `vector_index_jobs` 异步重建整个文件索引。
  - API 只允许当前用户、已完成索引且当前页面确由 OCR 生成的 PDF；修订正文必须非空并受长度限制。
- 范围：
  - 新增页级 OCR correction 表、repository、migration 和文件删除级联清理。
  - 新增读取、保存和撤销人工修订 API，并复用 embedding 配置检查、限流、file advisory lock 和任务状态反馈。
  - document/vector service 应用修订正文并传播 `ocr_correction_applied`、revision、更新时间等白名单 metadata。
  - 原文预览提供编辑、取消、保存、撤销和异步重建状态；成功后提示重新提问获取新引用。
  - 补齐权限、输入边界、版本递增、worker 应用、前端请求与真实 PDF smoke 测试及文档。
- 验收标准：
  - 当前用户可读取 OCR 页的原始/当前文本并提交非空修订；跨用户、非 PDF、原生文本页和无效页码被拒绝。
  - 保存修订后新索引使用人工文本，metadata 保留原 OCR 置信度且标记人工修订版本。
  - 撤销修订后新索引恢复 Tesseract 文本，修订记录被删除且历史 source 不被改写。
  - 重复提交、索引中的文件和异常 worker 状态有明确反馈，不产生并发版本覆盖。
  - 后端、前端测试、production build、Docker Compose migration/smoke 和 production preflight 通过。
- 相关提交：`e6cc52d`。
- 完成记录：
  - 新增 migration `006_create_pdf_ocr_corrections.sql` 和 `knowledge_file_ocr_corrections` 表，以 `user_id + knowledge_file_id + page_number` 保存原始 OCR 文本、人工正文、revision 和时间戳；文件或用户永久删除时由外键级联清理。
  - 新增页级 correction `GET/PATCH/DELETE` API；保存与撤销均校验当前用户、已索引 OCR PDF 页面、embedding 配置和 Redis 限流，并通过 file advisory lock 递增 index version、异步重建完整文件。
  - worker 仍运行 Tesseract 获取文本和置信度，再在切分前应用当前人工正文；新 chunks/source 标记 `ocr_correction_applied`、revision、字符数和更新时间，原 OCR confidence/quality 保持可审计，历史引用继续绑定旧 index version。
  - 原文预览新增完整页编辑、字符计数、无变化阻断、保存状态、两步撤销、失败重试和任务轮询；人工修订后的引用卡片优先展示 revision 与原 OCR 置信度。
  - 两页纯图片 PDF 已通过 Poppler 144 DPI 渲染目检；真实账号 smoke 完成上传与首次 OCR、读取整页、保存人工文本、处理中重复提交 `409`、revision 1 chunk/metadata 验证、撤销后恢复 Tesseract 文本和永久删除，数据库测试文件与 correction 残留均为 0。
  - `cd backend && conda run -n firstrag python -m pytest -q`：311 passed、8 warnings、30 subtests passed。
  - `cd frontend && npm test -- --run`：10 个 test files、69 tests passed；`npm run lint`：0 error、保留 2 个既有 `<img>` performance warnings；Next 16.2.10 production build 通过。
  - `docker compose up -d --build`、服务状态与近期日志检查通过；migration 首次应用 006，backend、worker、frontend 均正常启动，Redis、PostgreSQL、Chroma healthy。
  - production preflight、Chroma runtime health、migration dry-run 和 `git diff --check` 全部通过。
- 建议验证命令：

```bash
cd backend && conda run -n firstrag python -m pytest -q
cd ../frontend && npm test -- --run && npm run lint && npm run build
cd .. && docker compose up -d --build
docker compose ps -a
docker compose logs --since=10m redis postgres chroma migrate backend worker frontend
conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method compose --check-runtime-health
git diff --check
```

## T-075 增加 PDF 与 OCR 校对文本并排工作台

- 来源计划：`PLAN-20260722-01`
- 优先级：`P1`
- 状态：`Done`
- 目标：让用户校对扫描 PDF 时无需在原始文件和文本编辑器之间来回切换，并能快速识别原 OCR 与当前人工文本的差异。
- 技术边界：
  - 复用 T-074 的校对读取、保存、撤销和异步重建 API，不新增同步 OCR、embedding 或索引路径。
  - PDF 目标页通过新增的认证预览接口由 PyMuPDF 即时渲染为受限尺寸 PNG，再以临时 Blob URL 展示；关闭工作台后立即释放 URL，不把页面、文件或 API Key 写入持久化存储。
  - 差异比较在前端完成并限制为线性空间；超长 OCR 文本不能触发无界 LCS 计算或阻塞输入。
  - 历史引用、index version、权限与文件路径安全语义保持不变。
- 范围：
  - 原文预览中的校对区域扩展为桌面双栏、窄屏单栏的 PDF/文本工作台，并自动定位目标页。
  - 编辑区支持编辑视图和差异视图；差异视图按行展示原 OCR 与当前文本，并高亮新增、删除和修改内容。
  - PDF 加载提供骨架、失败提示、重新加载和独立窗口打开入口；保存、取消、字符计数和异步任务状态继续复用现有交互。
  - 补充差异算法、请求状态和关键 UI 文案测试，同步更新 Frontend/API 使用说明和任务台账。
- 验收标准：
  - 打开 OCR 校对后，同一工作台可见目标 PDF 页和完整校对文本；窄屏不会横向溢出或遮挡操作按钮。
  - 原 OCR 与当前草稿一致时明确显示无差异；存在变更时能区分新增、删除和修改行，并显示汇总数量。
  - PDF 读取失败不丢失校对草稿，用户可重新加载或在新窗口打开原始文件。
  - 关闭、切页或卸载组件后 Blob URL 被释放；50,000 字符上限、无变化阻断、保存/撤销/任务轮询保持兼容。
  - 前端测试、lint、production build、Docker Compose 页面 smoke 和 `git diff --check` 通过。
- 相关提交：`976214b`。
- 完成记录：
  - 新增当前用户鉴权的 PDF 页级 PNG 预览 API 与 Next.js streaming proxy；PyMuPDF 只渲染目标页、最长边限制为 1800 像素，超大页面自动下采样，响应禁止公共缓存且不落盘。
  - 原文预览中的校对区域升级为响应式工作台：桌面并排展示 PDF 与文本，窄屏依次展示；包含预览骨架、失败重试、独立窗口打开、编辑/差异视图、只看变化和保存/取消状态。
  - 差异算法使用唯一行锚点与 longest increasing subsequence 固定未变化区域，额外行区分新增/删除，成对变化行继续高亮字符级前后缀；通过 `useDeferredValue` 和线性空间实现避免长页输入阻塞。
  - Blob URL 在请求替换、取消或组件卸载时释放；实际浏览器验证取消工作台后预览节点移除，未保存验收草稿，也未产生 correction 或重建任务。
  - 真实账号完成两页扫描 PDF smoke：第 2 页 PNG 正常显示；人工草稿得到“修改 2 / 新增 1 / 删除 0”和正确字符高亮；390px viewport 下 `clientWidth = scrollWidth = 390`，底层来源评分条同步修正为小屏换行。
  - 浏览器验收创建的 PDF 与临时会话已清理；测试文件永久删除成功，测试会话软删除成功。
  - `cd backend && conda run -n firstrag env PYTHONPATH=. pytest -q`：316 passed、8 warnings、30 subtests passed。
  - `cd frontend && npm test -- --run`：11 个 test files、75 tests passed；`npm run lint`：0 error、保留 2 个既有 `<img>` performance warnings；Next 16.2.10 production build 通过。
  - Docker Compose 最终重建通过；PostgreSQL、Redis、Chroma healthy，migration 0 applied / 7 skipped，backend、worker、frontend 正常启动；production preflight、Chroma runtime health、migration dry-run 与 `git diff --check` 通过。
  - 构建期间 npm 新披露的 Sharp high finding 已通过 override 到 `sharp@0.35.3` 消除；production audit 门禁通过，仅保留截至 2026-08-20 的 PostCSS moderate 限时例外。
- 建议验证命令：

```bash
cd frontend && npm test -- --run && npm run lint && npm run build
cd .. && docker compose up -d --build
docker compose ps -a
docker compose logs --since=10m backend worker frontend
git diff --check
```

## T-076 增加文件级 OCR 质量巡检

- 来源计划：`PLAN-20260722-02`
- 优先级：`P1`
- 状态：`Done`
- 完成日期：`2026-07-22`
- 目标：让用户无需先通过问答命中某个页面，即可从知识文件入口发现并处理低置信度 OCR 页面。
- 技术边界：
  - 只读取当前文件当前 index version 的 PostgreSQL chunk metadata 和现有 correction 记录，不扫描磁盘、不重新运行 OCR、不读取 Chroma。
  - 页级清单、统计与入口必须绑定当前用户和未删除文件；原文、人工校对、重新识别与异步重建继续复用 T-073 至 T-075 的现有接口。
  - 列表只返回安全展示字段和截断摘要，不返回 storage path、完整页正文或内部凭据。
- 范围：
  - 新增文件级 OCR 页面质量清单 API，返回页码、置信度、质量状态、人工修订状态、代表 chunk 和安全摘要。
  - 文件管理中为已索引 PDF 增加 OCR 巡检入口；巡检弹窗展示统计、页码质量刻度、筛选排序和分页质量列表。
  - 点击页面直接打开该页的 PDF/文本校对工作台，并继续支持重新识别、保存修订、撤销和任务状态轮询。
  - 覆盖无 OCR 页面、部分低置信度、已人工校对、加载失败、长列表与窄屏状态。
- 验收标准：
  - 当前用户只能读取自己的未删除文件；跨用户或不存在文件返回 404，未完成索引返回明确冲突提示。
  - 默认优先展示尚未人工修订的低置信度页面，并可切换全部页、待处理页和已校对页以及页码顺序。
  - 点击任一 OCR 页可直接看到 T-075 校对工作台和目标 PDF 页面，不要求先产生聊天引用。
  - 文件没有 OCR 页面时展示可理解空状态；加载失败可重试，不影响文件管理其他操作。
  - 后端、前端测试、lint、production build、Docker Compose 真实页面 smoke、production preflight 和 `git diff --check` 通过。
- 相关提交：`ca92e0b`。
- 完成记录：
  - 新增当前用户文件级 OCR 质量清单 API，只汇总当前 index version 的 PostgreSQL OCR chunk metadata 与人工 correction；响应按页去重，提供置信度、质量、待处理/已校对状态和截断摘要，不读取磁盘、Chroma 或完整页正文。
  - 文件管理为已索引 PDF 增加“OCR 巡检”入口；巡检弹窗提供待处理、已校对、OCR 页数和平均置信度统计，页码质量刻度、全部/待处理/已校对筛选，以及低分优先/按页码排序。
  - 巡检页通过精确的 file、chunk、index version 和 page metadata 复用来源预览；点击页码或列表项无需聊天引用即可打开目标 PDF 页，并自动展开 T-075 校对工作台。
  - 真实账号完成两页纯图片 PDF 上传与索引 smoke：巡检返回 2 个 OCR 页面、文档 2 页、平均置信度 90%，页码刻度分别显示 89% 与 92%；全部页筛选、低分排序和第 1 页直达校对均通过。
  - 390px viewport 下巡检弹窗和直达校对工作台均满足 `clientWidth = scrollWidth = 390`；真实测试文件已通过生命周期服务永久删除，清理 1 个文件、1 个关联、2 个 chunks 和 1 个 job。
  - `cd backend && conda run -n firstrag env PYTHONPATH=. pytest -q`：322 passed、8 warnings、30 subtests passed。
  - `cd frontend && npm test -- --run`：12 个 test files、80 tests passed；`npm run lint`：0 error、保留 2 个既有 `<img>` performance warnings；Next.js 16.2.10 production build 通过。
  - Docker Compose 最终重建通过：PostgreSQL、Redis、Chroma healthy，migration `applied=0 skipped=7`，backend、worker、frontend 正常启动；真实页面请求无本次新增错误。
  - production preflight、Chroma runtime health、migration dry-run 和 `git diff --check` 通过；npm production audit 门禁通过，仅保留截至 2026-08-20 的 PostCSS moderate 限时例外。
- 建议验证命令：

```bash
cd backend && conda run -n firstrag env PYTHONPATH=. pytest -q
cd ../frontend && npm test -- --run && npm run lint && npm run build
cd .. && docker compose up -d --build
docker compose ps -a
docker compose logs --since=10m backend worker frontend
conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method compose --check-runtime-health
git diff --check
```

## T-077 支持批量 OCR 重新识别与失败重试

- 来源计划：`PLAN-20260722-03`
- 优先级：`P1`
- 状态：`Done`
- 目标：允许用户在文件级 OCR 巡检中一次选择多个页面，提交一个可追踪、可恢复的异步重新识别批次。
- 技术边界：
  - 多个目标页合并到同一个 `vector_index_job.options.force_ocr_page_numbers`，只递增一次 index version、只重建一次整份文件；禁止按页创建并发 job，避免版本竞争和重复 embedding。
  - 批次只允许当前用户、已索引 PDF 的现有 OCR 页面；页码去重、排序并受可配置上限约束，原生文本页和越界页不能进入任务。
  - 失败重试必须从当前用户原失败 job 恢复受控 options，不接受前端伪造或扩大重试页集合；不把内部 job options 直接暴露给前端。
  - 继续复用 Redis 提交限流、PostgreSQL 队列、worker heartbeat、文件 advisory lock 和 T-073 的 OCR metadata，不新增同步 OCR 路径。
- 范围：
  - 新增批量 OCR 重新识别 API、批次校验/提交 service 和保留原参数的失败重试 API。
  - 巡检弹窗支持选择待处理页、选择当前筛选、清空选择，并显示批次页码清单与选择上限。
  - 提交后集中展示排队、处理中、成功、失败和查询异常状态；失败可用原 job 参数重试，成功后刷新文件级质量报告。
  - 补齐跨用户、非 OCR 页、超限、重复页、活跃任务、非法失败重试和前端选择/进度测试，并同步文档。
- 验收标准：
  - 一个多页请求只创建一个新 index version 和一个 worker job，job options 包含规范化后的全部页码。
  - 默认可一键选择待处理低置信度页；批量操作期间不能改变选择或重复提交，状态变化有明确、可访问的文字反馈。
  - 失败 job 只能由原用户、原文件在同一 index version 下重试，且新 job 完整保留原批次页码。
  - 成功后巡检报告刷新 OCR confidence/attempt；失败重试和查询重试不会重复创建活跃任务。
  - 后端、前端测试、lint、production build、Docker Compose 多页 OCR smoke、production preflight 和 `git diff --check` 通过。
- 相关提交：`2de3486`。
- 完成记录：
  - 新增批量重新识别与失败重试 API；服务端对页码去重、排序、校验 OCR metadata 和批次上限，只递增一次 index version，并把全部目标页写入一个 PostgreSQL job。失败重试绑定当前用户、原文件、原 index version，并只恢复原 job 的受控 options。
  - OCR 巡检弹窗支持选择待处理、选择当前筛选、逐页勾选、清空选择和上限提示；批次面板集中显示 P01/P02 等页码清单、排队/处理中/成功/失败进度以及原参数重试入口。
  - 真实账号完成两页纯图片 PDF 验收：两页一次提交后均从“第 1 次识别”更新为“第 2 次识别”；数据库确认只新增一个 `pdf_pages_ocr_reindex` job，文件 index version 从 0 增至 1，options 精确为 `[1, 2]`。
  - 390px viewport 下 OCR 批次弹窗满足 `clientWidth = scrollWidth = 390`，页面无横向溢出；浏览器 console 无 error。验收 PDF 及索引随后通过文件生命周期服务永久删除，数据库确认残留记录为 0。
  - `cd backend && conda run -n firstrag env PYTHONPATH=. pytest -q`：331 passed、8 warnings、30 subtests passed；批量 service/route 增量测试 31 passed。
  - `cd frontend && npm test -- --run`：12 个 test files、84 tests passed；`npm run lint`：0 error、保留 2 个既有 `<img>` performance warnings；Next.js 16.2.10 production build 通过。
  - Docker Compose 最终重建通过：PostgreSQL、Redis、Chroma healthy，migration `Exited (0)` 且 `applied=0 skipped=7`，backend、worker、frontend 正常运行；真实批量 API、job 轮询和报告刷新均返回 200。
  - production preflight、Chroma runtime health、migration dry-run、`git diff --check` 和 npm audit policy 通过；依赖审计仅保留截至 2026-08-20 的 PostCSS moderate 限时例外。
- 建议验证命令：

```bash
cd backend && conda run -n firstrag env PYTHONPATH=. pytest -q
cd ../frontend && npm test -- --run && npm run lint && npm run build
cd .. && docker compose up -d --build
docker compose ps -a
docker compose logs --since=10m backend worker frontend
conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method compose --check-runtime-health
git diff --check
```

## T-078 增加 OCR 识别历史、质量趋势与文本差异

- 来源计划：`PLAN-20260722-04`
- 优先级：`P1`
- 状态：`Doing`
- 目标：保留扫描 PDF 页面的每次 OCR 结果，使用户能判断重新识别是否改善置信度和文字内容。
- 技术边界：
  - 历史记录独立于会被替换的 `knowledge_file_chunks`，按当前用户、文件、页码和 index version 持久化；文件或用户永久删除时级联清理。
  - 每条记录保存 OCR 原始文本、SHA-256、confidence、quality、word count、attempt、触发来源和关联 job；人工校对文本不冒充 OCR 原始结果。
  - 识别次数按页面历史单调递增；旧文件首次进入新流程时从现有 chunk metadata 衔接，不把重新识别次数重置为 1。
  - 历史查询只允许当前用户的未删除 PDF；默认限制每页保留最近若干次，避免长期重新识别导致数据库无界增长。
- 范围：
  - 新增 OCR history migration、repository、索引成功记录逻辑和页级历史查询 API。
  - 巡检列表展示历史数量和最近 confidence delta；新增历史面板，展示时间线、最佳/当前置信度、改善/下降次数和相邻文本差异。
  - 复用现有线性空间 OCR diff，长文本差异延迟计算；历史仅在用户打开页面时按需请求。
  - 覆盖首次识别、连续重识别、旧 metadata 衔接、人工校对、跨用户、无历史、保留上限和移动端布局。
- 验收标准：
  - 初次 OCR 建立 baseline；后续成功索引为同页新增一条历史，失败索引不产生伪成功记录。
  - 相邻历史返回可信 confidence/word count delta，文本 SHA 相同则明确标记未变化；attempt 不因批量或人工校对重建而倒退。
  - 用户只能读取自己的文件和页面历史，接口不返回 storage path、API Key 或内部异常。
  - 前端能切换相邻识别记录并查看差异，空历史、单次历史、加载失败和窄屏状态可理解且可恢复。
  - 后端、前端测试、lint、production build、Docker Compose 真实两次 OCR smoke、production preflight 和 `git diff --check` 通过。
- 建议验证命令：

```bash
cd backend && conda run -n firstrag env PYTHONPATH=. pytest -q
cd ../frontend && npm test -- --run && npm run lint && npm run build
cd .. && docker compose up -d --build
docker compose ps -a
docker compose logs --since=10m backend worker frontend
conda run -n firstrag python scripts/production_preflight.py --env-file .env --migration-method compose --check-runtime-health
git diff --check
```

## 更新规则

- 每个任务开始时，将状态从 `Todo` 改为 `Doing`。
- 遇到外部阻塞时，将状态改为 `Blocked`，并在任务下补充阻塞原因。
- 完成后，将状态改为 `Done`，填写完成日期、验证命令和相关 commit。
- 如果任务拆分出新的子任务，优先新增独立 task ID，避免在单个任务中无限追加范围。

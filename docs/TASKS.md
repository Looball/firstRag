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

- 2026-06-29 已完成静态回归验收：后端 107 个 unittest 通过、前端 lint 通过、Vitest 32 个用例通过、Next build 通过；真实 RAG eval 和 indexing eval 可在发布前按需运行。
- 本地 push 前推荐运行 `scripts/acceptance_check.sh`；只做静态检查时可运行 `scripts/acceptance_check.sh --skip-real-eval`。
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
| `PLAN-20260701-02` | 2026-07-01 | `Todo` | 正式生产上线补强专项，补齐部署安全、稳定性、风控、可观测性、评测质量和产品化分层。 | `T-042` - `T-047` |

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
| `T-046` | `PLAN-20260701-02` | `P1` | `Todo` | 准备真实问题集并固化上线前 RAG 质量门禁 |  |  |
| `T-047` | `PLAN-20260701-02` | `P2` | `Todo` | 区分普通用户模式和高级/开发模式 |  |  |

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
  - 解除阻塞条件：启动后端服务、完成数据库迁移、启动 vector index worker，并在当前 shell 设置 eval 测试账号密码；账号还需要可用的 LLM provider / API Key。
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
- 状态：`Todo`
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

## T-047 区分普通用户模式和高级/开发模式

- 来源计划：`PLAN-20260701-02`
- 优先级：`P2`
- 状态：`Todo`
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

## 更新规则

- 每个任务开始时，将状态从 `Todo` 改为 `Doing`。
- 遇到外部阻塞时，将状态改为 `Blocked`，并在任务下补充阻塞原因。
- 完成后，将状态改为 `Done`，填写完成日期、验证命令和相关 commit。
- 如果任务拆分出新的子任务，优先新增独立 task ID，避免在单个任务中无限追加范围。

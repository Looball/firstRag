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

- 2026-06-28 已完成整体回归验收：后端测试通过、前端 lint/build 通过、RAG eval gate 10/10 通过、indexing eval 通过；当前静态验收为后端 78 个 unittest、前端 lint、Vitest 10 个用例和 Next build 通过。
- 本地 push 前推荐运行 `scripts/acceptance_check.sh`；只做静态检查时可运行 `scripts/acceptance_check.sh --skip-real-eval`。
- 当前阶段优先做“可维护性 + 可观测性 + 验收自动化”，避免在关键链路刚稳定后继续堆叠大功能。
- 修改项目文件后，继续遵守只暂存当前任务相关文件、不混入 unrelated refactor 的规则。

## 计划批次

| 计划 ID | 日期 | 状态 | 目标 | 关联任务 |
| --- | --- | --- | --- | --- |
| `PLAN-20260628-01` | 2026-06-28 | `Done` | 基于代码和功能审查，建立可维护性、可观测性和验收自动化方向的第一批 backlog。 | `T-001` - `T-009` |
| `PLAN-20260628-02` | 2026-06-28 | `Done` | 优化知识库检索速度，优先降低 rerank 对首 token 前等待时间的影响。 | `T-010` |
| `PLAN-20260628-03` | 2026-06-28 | `Done` | 优化 RAG 检索前置阶段，减少 knowledge profile 与文件范围查询开销。 | `T-011` |
| `PLAN-20260628-04` | 2026-06-28 | `Done` | 补强 RAG eval 性能观测，让后续检索优化有稳定报告依据。 | `T-012` |
| `PLAN-20260628-05` | 2026-06-28 | `Done` | 修正 knowledge profile cache diagnostics 在真实 RAG eval 报告中缺失的问题。 | `T-013` |
| `PLAN-20260629-01` | 2026-06-29 | `Todo` | RAG 检索性能二阶段优化，继续降低首 token 前等待时间，优先处理 settings 读取、混合检索和重复查询开销。 | `T-014` - `T-018` |

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
| `T-014` | `PLAN-20260629-01` | `P1` | `Todo` | 定位并优化 retrieval settings 阶段耗时 | - | - |
| `T-015` | `PLAN-20260629-01` | `P1` | `Todo` | 为知识库检索设置增加进程内轻量缓存 | - | - |
| `T-016` | `PLAN-20260629-01` | `P1` | `Todo` | 优化 hybrid retrieval 粗召回执行路径 | - | - |
| `T-017` | `PLAN-20260629-01` | `P2` | `Todo` | 增加 query embedding 进程内短 TTL 缓存 | - | - |
| `T-018` | `PLAN-20260629-01` | `P2` | `Todo` | 固化 RAG eval 性能门槛和趋势字段 | - | - |

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
- 状态：`Todo`
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
- 状态：`Todo`
- 目标：解释并降低最新 RAG eval 报告中 `retrieval_settings_ms` 平均约 2.39s 的异常耗时。
- 范围：补充 settings 子阶段计时，确认耗时来源是数据库连接、SQL 查询、LCEL 调度、真实 eval 设置 PATCH 影响，还是其它链路开销；本任务不引入 Redis。
- 验收标准：
  - RAG eval 报告能区分 settings 子阶段耗时，不再只有不可解释的 `retrieval_settings_ms` 黑盒指标。
  - 若发现明确瓶颈，完成对应轻量优化或拆出新的后续任务。
  - 静态验收和真实 RAG eval 通过。
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
- 状态：`Todo`
- 目标：减少每轮聊天重复读取 `knowledge_base_retrieval_settings` 的开销，降低 settings 阶段对首 token 前等待时间的影响。
- 范围：实现进程内短 TTL cache，key 使用 `user_id + knowledge_base_id`；更新 retrieval settings 后主动失效；普通读取路径复用缓存；不新增 Redis。
- 验收标准：
  - 设置更新后下一轮聊天立即读取新配置。
  - 普通聊天路径能命中缓存并在 diagnostics 或测试中可观察。
  - 后端测试覆盖 cache miss、hit、主动失效、TTL 过期和默认值路径。
  - 静态验收和真实 RAG eval 通过。
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
- 状态：`Todo`
- 目标：压缩 vector、fulltext、RRF 和 rerank 前的检索等待，继续降低启用检索场景的首 token 前耗时。
- 范围：优先评估并实现 vector 与 fulltext 粗召回的安全并行；保留现有权限过滤、软删除过滤、diagnostics、向量降级和单路失败兜底行为。
- 验收标准：
  - RAG eval 继续 10/10 PASS。
  - diagnostics 仍包含 `vector_count`、`fulltext_count`、`fused_count`、`reranked_count` 和阶段耗时。
  - vector 或 fulltext 单路失败时，另一通道仍可返回候选并记录降级信息。
  - 静态验收和真实 RAG eval 通过。
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
- 状态：`Todo`
- 目标：减少短时间内重复问题、eval 重跑和多轮相近测试对 embedding provider 的重复调用。
- 范围：缓存 query embedding，不缓存最终答案或用户私密内容；key 使用 provider、model 和 normalized query；embedding 生成失败不写入缓存；不新增 Redis。
- 验收标准：
  - 重复 query 在 TTL 内命中缓存。
  - TTL 过期后会重新生成 embedding。
  - embedding provider 报错时不会污染缓存，后续请求仍可正常重试。
  - 后端测试覆盖命中、过期和失败不缓存路径。
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
- 状态：`Todo`
- 目标：把 RAG 性能优化从单次报告观察升级为可持续追踪，让性能回退在验收报告中显眼暴露。
- 范围：扩展 eval summary/report，记录 settings、profile、retrieve、hybrid、rerank 的最近 N 次均值和变化，并加入建议阈值；不在报告中输出账号密码、API Key、JWT 或数据库连接串。
- 验收标准：
  - `docs/evals/latest_summary.md` 展示阶段耗时趋势。
  - RAG eval Markdown 报告展示关键性能门槛和本次是否通过。
  - 历史 JSON 保留必要字段，便于后续比较。
  - 单元测试覆盖 summary 字段和 Markdown 输出。
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

## 更新规则

- 每个任务开始时，将状态从 `Todo` 改为 `Doing`。
- 遇到外部阻塞时，将状态改为 `Blocked`，并在任务下补充阻塞原因。
- 完成后，将状态改为 `Done`，填写完成日期、验证命令和相关 commit。
- 如果任务拆分出新的子任务，优先新增独立 task ID，避免在单个任务中无限追加范围。

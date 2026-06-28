# FirstRAG 后续任务台账

本文档用于追踪 FirstRAG 单人开发阶段的后续任务。任务应按优先级推进，完成后同步更新状态、完成日期、验证命令和相关 commit。

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

## 当前基线

- 2026-06-28 已完成整体回归验收：后端 71 个测试通过、前端 lint/build 通过、RAG eval gate 6/6 通过、indexing eval 通过。
- 本地 push 前推荐运行 `scripts/acceptance_check.sh`；只做静态检查时可运行 `scripts/acceptance_check.sh --skip-real-eval`。
- 当前阶段优先做“可维护性 + 可观测性 + 验收自动化”，避免在关键链路刚稳定后继续堆叠大功能。
- 修改项目文件后，继续遵守只暂存当前任务相关文件、不混入 unrelated refactor 的规则。

## 任务列表

| ID | 优先级 | 状态 | 标题 | 完成日期 | 相关 commit |
| --- | --- | --- | --- | --- | --- |
| `T-001` | `P1` | `Todo` | 拆分前端聊天工作台，降低 `page.tsx` 维护成本 | - | - |
| `T-002` | `P1` | `Todo` | 建立前端解析/状态工具测试底座 | - | - |
| `T-003` | `P1` | `Todo` | 增加 eval 历史趋势摘要 | - | - |
| `T-004` | `P1` | `Todo` | 产品化 vector worker health 展示 | - | - |
| `T-005` | `P2` | `Todo` | 完善 indexing failure recovery 分类与操作闭环 | - | - |
| `T-006` | `P2` | `Todo` | 扩充 RAG eval case 覆盖面 | - | - |
| `T-007` | `P2` | `Todo` | 梳理本地启动与验收工作流文档 | - | - |
| `T-008` | `P2` | `Todo` | 为部署目录补齐可运行 Docker Compose 方案 | - | - |

## T-001 拆分前端聊天工作台，降低 `page.tsx` 维护成本

- 优先级：`P1`
- 状态：`Todo`
- 目标：降低 `frontend/src/app/page.tsx` 的单文件复杂度，让后续聊天、文件管理、诊断和任务队列迭代更容易审查。
- 范围：第一阶段只拆分纯解析函数、类型定义、文件管理面板、任务队列面板和诊断面板；不改变 UI 文案、交互和接口协议。
- 验收标准：
  - 主要聊天、上传、向量化、诊断展示行为保持不变。
  - 拆出的模块命名清晰，职责边界稳定。
  - `npm run lint` 和 `npm run build` 通过。
- 建议验证命令：

```bash
cd frontend
npm run lint
npm run build
```

## T-002 建立前端解析/状态工具测试底座

- 优先级：`P1`
- 状态：`Todo`
- 目标：为前端 retrieval、sources、vector health 等解析逻辑建立单元测试，降低后续拆分和协议演进风险。
- 范围：默认使用 Vitest；优先覆盖 retrieval/source/vector health 解析函数和状态归一化逻辑。
- 验收标准：
  - `frontend/package.json` 增加 `npm run test`。
  - 核心解析函数有单元测试覆盖。
  - `scripts/acceptance_check.sh` 增加可选前端测试阶段，默认纳入静态验收。
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

- 优先级：`P1`
- 状态：`Todo`
- 目标：把 RAG 和 indexing eval 的历史结果沉淀成趋势摘要，便于观察回归质量变化。
- 范围：基于 `docs/evals/runs/*.json` 与 `docs/evals/indexing_runs/*.json` 生成 `docs/evals/latest_summary.md`。
- 验收标准：
  - 摘要展示最近 N 次通过率、平均耗时、首 token、平均引用数和 indexing 成功状态。
  - 脚本可重复运行，输出稳定。
  - 报告不包含账号密码、API Key、JWT 或数据库连接串。
- 建议验证命令：

```bash
conda run -n firstrag python scripts/eval_summary.py
git diff -- docs/evals/latest_summary.md
```

## T-004 产品化 vector worker health 展示

- 优先级：`P1`
- 状态：`Todo`
- 目标：让前端任务队列区域更清楚地展示 worker 和队列状态，帮助快速判断是否需要启动 worker、等待或处理失败任务。
- 范围：优先复用现有 `GET /chat/vector-index-jobs/health` 返回值，不新增后端 API。
- 验收标准：
  - 空队列、排队中、处理中、疑似卡住、失败任务均有清晰展示。
  - 展示最近检查时间、手动刷新入口、卡住任务数量和建议操作。
  - 用户能从失败状态快速定位相关文件并看到恢复建议。
- 建议验证命令：

```bash
cd frontend
npm run lint
npm run build
```

## T-005 完善 indexing failure recovery 分类与操作闭环

- 优先级：`P2`
- 状态：`Todo`
- 目标：提高向量化失败后的可恢复性，让用户知道失败原因和下一步操作。
- 范围：扩展失败类型识别和提示，例如解析失败、embedding 失败、Chroma 写入失败、数据库 chunk 写入失败和任务超时。
- 验收标准：
  - 后端返回稳定的 `failure_type`、`failure_hint` 和 `can_retry`。
  - 前端按失败类型展示重试、删除向量或重新上传建议。
  - 后端测试覆盖主要失败分类。
- 建议验证命令：

```bash
cd backend
conda run -n firstrag python -m unittest discover tests -v
cd ../frontend
npm run lint
npm run build
```

## T-006 扩充 RAG eval case 覆盖面

- 优先级：`P2`
- 状态：`Todo`
- 目标：让真实 RAG 回归覆盖更多高风险路径，减少路由、rerank 和无答案场景的回归盲区。
- 范围：新增多轮追问、无答案或低相关、禁用 rerank、禁用 query router、`retrieval_mode=never` 等 case。
- 验收标准：
  - `docs/evals/rag_eval_cases.jsonl` 新增 case 后仍可稳定运行。
  - `scripts/rag_eval_gate.sh` 继续全 PASS。
  - 新 case 的期望文件、关键词和检索行为定义清晰。
- 建议验证命令：

```bash
FIRSTRAG_EVAL_USERNAME=你的用户名 \
FIRSTRAG_EVAL_PASSWORD=你的密码 \
scripts/rag_eval_gate.sh
```

## T-007 梳理本地启动与验收工作流文档

- 优先级：`P2`
- 状态：`Todo`
- 目标：把单人开发的启动、开发、验收和 push 流程整理成可重复执行的日常工作流。
- 范围：更新 `docs/DEPLOYMENT.md` 或 `docs/evals/README.md`，串联后端、前端、worker、真实 eval 和一键验收脚本。
- 验收标准：
  - 文档可按顺序完成启动、开发、验收、push。
  - 明确说明何时需要启动 worker，何时可使用 `--skip-real-eval`。
  - 不写入真实账号密码或敏感配置。
- 建议验证命令：

```bash
scripts/acceptance_check.sh --skip-real-eval
```

## T-008 为部署目录补齐可运行 Docker Compose 方案

- 优先级：`P2`
- 状态：`Todo`
- 目标：把当前占位部署配置推进到可本地运行的 Docker Compose 方案。
- 范围：补齐 PostgreSQL、后端、前端、worker 服务，并明确 Chroma/vector_db 持久化目录。
- 验收标准：
  - 新环境可按文档启动基础服务。
  - 敏感配置仍通过 `.env` 注入，不提交真实密钥。
  - worker 和后端共享必要的上传目录、vector_db 和数据库配置。
- 建议验证命令：

```bash
docker compose config
```

## 更新规则

- 每个任务开始时，将状态从 `Todo` 改为 `Doing`。
- 遇到外部阻塞时，将状态改为 `Blocked`，并在任务下补充阻塞原因。
- 完成后，将状态改为 `Done`，填写完成日期、验证命令和相关 commit。
- 如果任务拆分出新的子任务，优先新增独立 task ID，避免在单个任务中无限追加范围。

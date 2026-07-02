# RAG 评测集

这里放项目内置的轻量 RAG 回归评测，用于检查真实后端链路中的检索判断、召回、引用和回答质量。

## 最近整体回归验收

2026-07-02 已刷新一轮真实链路 eval 基线，覆盖 RAG 真实评测门禁、上传与向量化真实链路验收，以及 eval 历史趋势摘要。静态验收入口见 `scripts/acceptance_check.sh`。

`T-046` 已将 RAG 上线前评测集扩展为 14 条非敏感可复跑 case，并把默认检索参数 `top_k/vector_top_k/fulltext_top_k/rrf_k = 4/16/16/8` 写入主基线 case 的 `retrieval_settings` 和 diagnostics 断言。2026-07-01 的旧 10 条 case 基线仅作为历史对照。

| 检查项 | 命令 | 结果 |
| --- | --- | --- |
| RAG eval gate | `FIRSTRAG_EVAL_USERNAME=你的用户名 FIRSTRAG_EVAL_PASSWORD=你的密码 scripts/rag_eval_gate.sh` | 通过，14/14 case 通过；平均引用 2.00，平均首 token 2701.22ms，平均耗时 5.90s，失败 case 为 0，质量门禁全部 PASS。 |
| Indexing eval | `FIRSTRAG_EVAL_USERNAME=你的用户名 FIRSTRAG_EVAL_PASSWORD=你的密码 conda run -n firstrag python scripts/eval_indexing.py --base-url http://127.0.0.1:8000` | 通过，上传、auto index、worker 完成、文件 indexed、聊天 Sources 命中新文件且包含 vector 通道；job `succeeded`，聊天耗时 12.01s，引用数 1，向量降级为否。 |
| Eval summary | `conda run -n firstrag python scripts/eval_summary.py` | 通过，RAG 历史 30 次、Indexing 历史 6 次；RAG 历史平均通过率 0.98，Indexing 历史通过率 1.00。 |

本轮生成的最新报告：

- `docs/evals/latest_rag_eval_report.md`
- `docs/evals/latest_indexing_eval_report.md`
- `docs/evals/latest_summary.md`

本轮 RAG 质量门禁通过。`T-036` 已确认旧趋势摘要中的 `settings=1716.02ms` 是 LCEL streaming 外层 settings-wait 间隔，不是检索设置读取耗时；本轮真实 `settings-load` 最新均值为 7.13ms，低于 1000ms 建议阈值。报告和历史 JSON 默认被 `.gitignore` 忽略，提交时只记录不含敏感信息的摘要。

该记录用于进入文档整理、提交、推送或 PR 前的 release readiness 检查。再次修改 RAG 检索、token usage、eval gate、indexing、worker health、vector failure recovery 或前端文件管理链路后，应重新运行上述验收。

## 一键本地验收

单人开发时，推荐在 push 前使用一键脚本串行运行主要检查：

```bash
FIRSTRAG_EVAL_USERNAME=你的用户名 \
FIRSTRAG_EVAL_PASSWORD=你的密码 \
scripts/acceptance_check.sh
```

该脚本会依次执行：

1. migration 文件检查，存在数据库连接时额外执行 dry-run。
2. 后端 `compileall`。
3. 后端 `unittest discover`。
4. 前端 `npm run lint`。
5. 前端 `npm run test`。
6. 前端 `npm run build`。
7. RAG eval gate。
8. Indexing eval。

只做静态检查、不访问真实后端时可跳过真实 eval：

```bash
scripts/acceptance_check.sh --skip-real-eval
```

如果本地沙箱限制 Turbopack 创建辅助进程或绑定本地端口，`npm run build` 可能需要在非沙箱环境或提权环境中重跑确认。

## 历史趋势摘要

`scripts/eval_summary.py` 会读取本地历史 JSON，生成 RAG 与 indexing eval 的趋势摘要，不访问后端服务，也不需要账号密码：

```bash
conda run -n firstrag python scripts/eval_summary.py
```

默认读取：

- `docs/evals/runs/*.json`
- `docs/evals/indexing_runs/*.json`

默认输出：

- `docs/evals/latest_summary.md`

可通过 `--limit` 控制每类最近展示的运行次数：

```bash
conda run -n firstrag python scripts/eval_summary.py --limit 5
```

趋势摘要报告默认被 `.gitignore` 忽略，避免每次本地验收产生无关提交。报告不输出账号密码、API Key、JWT 或数据库连接串。

## 运行前提

- 后端服务已经启动。
- 数据库迁移已经执行完成。
- vector index worker 已完成目标知识库文件的向量化。
- 当前账号已配置可用的 LLM provider 和 API Key。

## 运行命令

```bash
FIRSTRAG_EVAL_USERNAME=你的用户名 \
FIRSTRAG_EVAL_PASSWORD=你的密码 \
python scripts/eval_rag.py \
  --base-url http://127.0.0.1:8000
```

如果使用 conda 环境：

```bash
conda run -n firstrag python scripts/eval_rag.py \
  --base-url http://127.0.0.1:8000 \
  --username 你的用户名 \
  --password 你的密码
```

默认读取 `docs/evals/rag_eval_cases.jsonl`，并生成：

- `docs/evals/latest_rag_eval_report.md`：最新 Markdown 报告。
- `docs/evals/runs/YYYYMMDD_HHMMSS.json`：带时间戳的历史 JSON 记录。

当前内置评测集覆盖：

- 默认 `4/16/16/8` 基线：法律文档、RAG 核心概念、RRF 检索策略、source 相关性。
- 多轮追问：同一临时会话中先问“什么是诉讼法”，再追问“它的任务是什么”。
- 无答案和低相关：`retrieval_mode=never` 跳过检索，以及低相关问题在强制检索下观察 source 行为。
- rerank 开关：默认开启 rerank，并覆盖 `enable_rerank=false` 的回归 case。
- query router 开关：默认开启 query router，并覆盖 `enable_query_router=false` 的确定性检索路径。
- 参数组合：默认 `4/16/16/8`、小候选池 `3/8/8/4`、旧对照 `4/16/16/10`。
- 用户反馈种子：把 message/source feedback 中常见的 source 相关性 bad case 整理为非敏感可复跑问题。

历史文件默认被 `.gitignore` 忽略，只保留在本地。再次运行评测时，最新报告会自动对比上一轮历史记录。

如果只想生成最新 Markdown 报告，不写历史记录：

```bash
conda run -n firstrag python scripts/eval_rag.py \
  --base-url http://127.0.0.1:8000 \
  --username 你的用户名 \
  --password 你的密码 \
  --no-history
```

## 质量门禁

评测脚本支持在真实链路跑完后检查质量门槛。任一门槛不满足时，脚本会返回非 0 退出码，并在 Markdown 报告和历史 JSON 中记录失败项：

```bash
conda run -n firstrag python scripts/eval_rag.py \
  --base-url http://127.0.0.1:8000 \
  --username 你的用户名 \
  --password 你的密码 \
  --min-pass-rate 1.0 \
  --min-average-sources 1 \
  --max-average-first-token-ms 8000 \
  --max-average-elapsed-seconds 20
```

可用门槛：

| 参数 | 说明 |
| --- | --- |
| `--min-pass-rate` | 最低通过率，取值范围 `0` 到 `1`。不传时沿用默认严格模式：所有 case 必须通过。 |
| `--min-average-sources` | 最低平均引用数。 |
| `--max-average-first-token-ms` | 最高平均首 token 等待时间。优先使用 `first_answer_token_ms`，缺失时使用 `pre_answer_total_ms` 近似。 |
| `--max-average-elapsed-seconds` | 最高平均端到端 case 耗时。 |

脚本标准输出会直接打印通过率、平均 sources、平均首 token 等待和失败 case 摘要；Markdown 报告还会展示评测集覆盖表、失败 case 表、质量门禁表、性能观察项和逐 case 检查项。

## 一键回归门禁

项目提供了推荐门槛的一键脚本：

```bash
FIRSTRAG_EVAL_USERNAME=你的用户名 \
FIRSTRAG_EVAL_PASSWORD=你的密码 \
scripts/rag_eval_gate.sh
```

默认门槛：

| 环境变量 | 默认值 | 说明 |
| --- | ---: | --- |
| `FIRSTRAG_EVAL_MIN_PASS_RATE` | `1.0` | 通过率必须达到 100%。 |
| `FIRSTRAG_EVAL_MIN_AVERAGE_SOURCES` | `1` | 平均至少展示 1 条引用。 |
| `FIRSTRAG_EVAL_MAX_AVERAGE_FIRST_TOKEN_MS` | `10000` | 平均首 token 等待不超过 10 秒。 |
| `FIRSTRAG_EVAL_MAX_AVERAGE_ELAPSED_SECONDS` | `30` | 平均单 case 总耗时不超过 30 秒。 |

## 上线前基线口径

`T-046` 后，`docs/evals/rag_eval_cases.jsonl` 是上线前 RAG 质量门禁的默认输入。主基线 case 明确写入：

```json
{
  "top_k": 4,
  "vector_top_k": 16,
  "fulltext_top_k": 16,
  "rrf_k": 8
}
```

评测报告应重点关注：

- `pass_rate` 是否达到 `1.0`。
- `average_sources` 是否不低于 `1`。
- `average_first_token_ms` 是否不超过 `10000`。
- 失败 case 是否集中在某个 `category` 或 `coverage`，例如 `source_feedback_bad_case`、`low_relevance` 或 `parameter_variant`。
- `rrf_legacy_k10_comparison` 与默认 `rrf_definition` 的 sources、耗时和失败检查差异。

如果默认 `4/16/16/8` 低于目标，建议按顺序处理：

1. 先查看报告中的“失败 Case 摘要”和逐 case diagnostics，确认是召回、rerank、query router 还是答案关键词断言失败。
2. 对 source 相关性失败，优先比较 `rrf_legacy_k10_comparison` 和 `rrf_small_pool_variant`，再决定是否把 `rrf_k` 或两路召回数上调。
3. 对首 token 超时，优先检查 `rerank_ms`、`retrieve_documents_ms`、`retrieval_total_ms`，必要时临时关闭 rerank 或降低候选池验证瓶颈。
4. 如果默认组整体退化且 legacy 对照更稳，可短期回滚到 `4/16/16/10`，但需要在任务记录中说明 source 质量和耗时权衡。
5. 刷新真实基线后运行 `conda run -n firstrag python scripts/eval_summary.py`，确认趋势报告没有异常漂移。

报告、历史 JSON 和 case 文件只允许记录非敏感问题、文件名、diagnostics 摘要和脱敏 answer preview；不要写入 API Key、JWT、数据库密码、私有文档原文或完整用户凭据。

常用覆盖项：

```bash
FIRSTRAG_EVAL_USERNAME=你的用户名 \
FIRSTRAG_EVAL_PASSWORD=你的密码 \
FIRSTRAG_EVAL_BASE_URL=http://127.0.0.1:8000 \
FIRSTRAG_EVAL_MAX_AVERAGE_FIRST_TOKEN_MS=15000 \
scripts/rag_eval_gate.sh
```

脚本不会读取 `.env`，也不要把账号密码写入脚本或提交到仓库。

## case 字段

| 字段 | 说明 |
| --- | --- |
| `id` | 评测用例唯一标识。 |
| `category` | 可选。case 分类，用于报告聚合，例如 `default_baseline`、`no_answer`、`parameter_variant`。 |
| `coverage` | 可选。覆盖标签列表，用于说明该 case 覆盖的风险点或参数组合。 |
| `source` | 可选。case 来源，例如 `real_question_seed`、`feedback_seed`、`tuning_comparison_seed`。 |
| `knowledge_base_name` | 要使用的知识库名称，找不到时会使用默认知识库。 |
| `question` | 用户问题。 |
| `pre_questions` | 可选。同一临时会话中先发送的预热问题，用于覆盖多轮追问。 |
| `retrieval_settings` | 运行该 case 前临时应用的知识库检索策略。评测结束会尽力恢复原设置。 |
| `expect_retrieval` | 期望最终是否检索。 |
| `min_sources` | 期望最少展示引用数量。 |
| `expected_files` | 期望引用命中的文件名列表，命中任意一个即可。 |
| `expected_keywords` | 期望答案中包含的关键词，默认全部需要命中。 |
| `expected_reason_keywords` | 期望 retrieval reason 中包含的关键词，默认全部需要命中。 |
| `expected_diagnostics` | 可选。按点路径检查 diagnostics 中的字段，例如 `settings.enable_rerank` 或 `reranked_count`。 |

## 注意

- 脚本会创建临时会话，用于保存真实聊天结果。
- 脚本会临时 PATCH 知识库检索设置，并在每条 case 完成后恢复原设置。
- 脚本不会读取 `.env`，账号密码请通过环境变量或命令行参数传入。

## 上传与向量化链路验收

`scripts/eval_indexing.py` 用于检查新文件进入知识库后的完整链路：

```text
登录
  -> 选择默认知识库
  -> 上传临时 Markdown 文件
  -> auto_index 提交 vector index job
  -> 等待 worker 完成
  -> 确认文件状态为 indexed
  -> 发起聊天
  -> 确认 Sources 命中刚上传的临时文件，且该 source 包含 vector 通道
  -> 确认本轮聊天没有 vector_degraded 或 vector_errors
  -> 默认解除临时文件与知识库关联
```

运行命令：

```bash
FIRSTRAG_EVAL_USERNAME=你的用户名 \
FIRSTRAG_EVAL_PASSWORD=你的密码 \
conda run -n firstrag python scripts/eval_indexing.py \
  --base-url http://127.0.0.1:8000
```

运行前需要同时启动后端和 vector index worker：

```bash
cd backend
conda activate firstrag
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

cd backend
conda activate firstrag
python -m app.workers.vector_index_worker
```

默认输出：

- `docs/evals/latest_indexing_eval_report.md`：最新 Markdown 报告。
- `docs/evals/indexing_runs/YYYYMMDD_HHMMSS.json`：带时间戳的历史 JSON 记录。

默认情况下，脚本只会解除临时文件和知识库的关联，不会删除全局文件记录、上传目录、chunks 或 Chroma 数据，避免误删用户数据。如果需要保留临时文件关联，可加：

```bash
--keep-file
```

# RAG 评测集

这里放项目内置的轻量 RAG 回归评测，用于检查真实后端链路中的检索判断、召回、引用和回答质量。

## 最近整体回归验收

2026-06-28 已完成一轮关键链路整体回归验收，覆盖后端单元测试、前端静态检查与构建、RAG 真实评测门禁、上传与向量化真实链路验收。

| 检查项 | 命令 | 结果 |
| --- | --- | --- |
| 后端核心测试 | `cd backend && conda run -n firstrag python -m unittest discover tests -v` | 通过，78 个测试全部 OK。 |
| 前端 lint | `cd frontend && npm run lint` | 通过。 |
| 前端 build | `cd frontend && npm run build` | 通过。沙箱环境首次运行因 Turbopack 需要创建辅助进程并绑定本地端口被拦截，提权重跑后通过。 |
| RAG eval gate | `FIRSTRAG_EVAL_USERNAME=你的用户名 FIRSTRAG_EVAL_PASSWORD=你的密码 scripts/rag_eval_gate.sh` | 通过，10/10 case 通过，质量门禁全部 PASS。 |
| Indexing eval | `FIRSTRAG_EVAL_USERNAME=你的用户名 FIRSTRAG_EVAL_PASSWORD=你的密码 conda run -n firstrag python scripts/eval_indexing.py --base-url http://127.0.0.1:8000` | 通过，上传、auto index、worker 完成、文件 indexed、聊天 Sources 命中新文件均通过。 |

本轮生成的最新报告：

- `docs/evals/latest_rag_eval_report.md`
- `docs/evals/latest_indexing_eval_report.md`
- `docs/evals/latest_summary.md`

该记录用于进入文档整理、提交、推送或 PR 前的 release readiness 检查。再次修改 RAG 检索、token usage、eval gate、indexing、worker health、vector failure recovery 或前端文件管理链路后，应重新运行上述验收。

## 一键本地验收

单人开发时，推荐在 push 前使用一键脚本串行运行主要检查：

```bash
FIRSTRAG_EVAL_USERNAME=你的用户名 \
FIRSTRAG_EVAL_PASSWORD=你的密码 \
scripts/acceptance_check.sh
```

该脚本会依次执行：

1. 后端 `unittest discover`。
2. 前端 `npm run lint`。
3. 前端 `npm run build`。
4. RAG eval gate。
5. Indexing eval。

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

- 基础法律文档检索。
- RAG 核心概念和 RRF 检索策略。
- 问候自动跳过检索和强制检索。
- 多轮追问。
- 低相关问题在 `retrieval_mode=never` 下跳过检索。
- 禁用 rerank。
- 禁用 query router。

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
  -> 确认 Sources 命中刚上传的临时文件
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

# RAG 评测集

这里放项目内置的轻量 RAG 回归评测，用于检查真实后端链路中的检索判断、召回、引用和回答质量。

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

历史文件默认被 `.gitignore` 忽略，只保留在本地。再次运行评测时，最新报告会自动对比上一轮历史记录。

如果只想生成最新 Markdown 报告，不写历史记录：

```bash
conda run -n firstrag python scripts/eval_rag.py \
  --base-url http://127.0.0.1:8000 \
  --username 你的用户名 \
  --password 你的密码 \
  --no-history
```

## case 字段

| 字段 | 说明 |
| --- | --- |
| `id` | 评测用例唯一标识。 |
| `knowledge_base_name` | 要使用的知识库名称，找不到时会使用默认知识库。 |
| `question` | 用户问题。 |
| `retrieval_settings` | 运行该 case 前临时应用的知识库检索策略。评测结束会尽力恢复原设置。 |
| `expect_retrieval` | 期望最终是否检索。 |
| `min_sources` | 期望最少展示引用数量。 |
| `expected_files` | 期望引用命中的文件名列表，命中任意一个即可。 |
| `expected_keywords` | 期望答案中包含的关键词，默认全部需要命中。 |

## 注意

- 脚本会创建临时会话，用于保存真实聊天结果。
- 脚本会临时 PATCH 知识库检索设置，并在每条 case 完成后恢复原设置。
- 脚本不会读取 `.env`，账号密码请通过环境变量或命令行参数传入。

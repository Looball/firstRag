# 无外部密钥入门实验

本实验复用 FirstRAG 的真实 FastAPI、Next.js、PostgreSQL、Redis、Chroma、worker 和 Playwright 链路，但把聊天与 embedding provider 替换为 Compose 网络内的确定性 OpenAI-compatible stub。你不需要真实账号、API Key 或公网模型服务，也不会读取仓库根目录 `.env`。

## 学习目标

完成实验后，你将能够：

- 观察注册、登录、TXT 上传、异步向量化、hybrid retrieval、SSE 回答和 sources 展示的完整结果。
- 区分 PostgreSQL 持久任务、worker 运行态、Chroma vectors 和前端 streaming 状态的职责。
- 使用 Compose project、独立 volumes 和 `/dev/null` env file 解释实验为何不会污染默认 FirstRAG 环境。
- 知道确定性 stub 能验证工程链路，但不能替代真实 provider 的质量、延迟、限流和费用评估。

## 预计耗时与先修条件

首次运行通常需要 6–15 分钟，主要时间用于构建镜像、安装或启动依赖以及等待服务健康；已有镜像缓存时会更快。建议至少预留 6 GB 可用内存和 10 GB 磁盘空间。

开始前确认：

```bash
docker version
docker compose version
node --version
npm --version
```

需要 Docker Desktop 或兼容的 Docker daemon、Docker Compose v2、Node.js 22 和 npm。Playwright Chromium 只需安装一次：

```bash
cd frontend
npm ci
npx --no-install playwright install chromium
cd ..
```

所有后续命令都从仓库根目录运行。默认占用以下 loopback 端口：

| 服务 | 默认地址 |
| --- | --- |
| Frontend | `http://127.0.0.1:13000` |
| Backend | `http://127.0.0.1:18080` |
| PostgreSQL | `127.0.0.1:25432` |

## 运行实验

在一个可交互终端中执行：

```bash
FIRSTRAG_E2E_PAUSE_AFTER_TEST=1 scripts/run_full_stack_e2e.sh
```

脚本会依次执行：

```text
创建唯一 Compose project
  -> 构建并启动隔离服务
  -> 等待 backend/frontend 健康
  -> 注册临时用户
  -> 写入仅指向 provider-stub 的模型设置
  -> Playwright 登录并上传合成 TXT
  -> worker 解析、切分、embedding 和写入双存储
  -> 页面提问并接收 SSE 回答
  -> 校验回答和引用来源
  -> 暂停，供学习者检查 UI 与日志
  -> 按 Enter 自动清理 containers、network 和 volumes
```

非交互 CI 不设置 `FIRSTRAG_E2E_PAUSE_AFTER_TEST`，因此验证结束后会立即清理。暂停模式只能在 TTY 中启用，避免 CI 或重定向输入时无限等待。

## 预期结果

Playwright 使用的公开合成数据是：

| 项目 | 值 |
| --- | --- |
| 文件名 | `t089-full-stack-source.txt` |
| 文件内容 | `FirstRAG credential-free full-stack evidence: T089 FULL STACK SOURCE.` |
| 问题 | `请返回资料中的验收标识 T089 FULL STACK SOURCE` |
| 回答 | `FirstRAG 全栈验收标识是 T089 FULL STACK SOURCE。` |
| 引用 | 页面出现“引用来源”和上述文件名 |

验证通过后，终端会打印 Compose project、登录地址和临时账号。保持该终端停在等待提示，在浏览器打开打印的 `/login` 地址并使用临时账号登录。建议依次观察：

1. 默认知识库中的文件已显示“已向量化”。
2. 对话中存在确定性回答，回答下方显示引用来源和文件名。
3. 检索信息展示实际请求留下的 sources/diagnostics，而不是教程预先写死的 UI 数据。
4. 设置页中的 provider 指向隔离网络内的测试模型；临时凭据不会回显完整值。

这里的临时用户名和密码只存在于本次隔离数据库，实验清理后失效，不应复用于其他环境。

## 观察服务与日志

脚本暂停时，复制终端打印的 Compose project 名，在另一个终端执行：

```bash
export FIRSTRAG_TUTORIAL_PROJECT="<打印的 Compose project>"
docker compose \
  --env-file /dev/null \
  -p "${FIRSTRAG_TUTORIAL_PROJECT}" \
  -f docker-compose.yml \
  -f deploy/docker/docker-compose.e2e.yml \
  ps
```

查看入库、provider 和回答日志：

```bash
docker compose \
  --env-file /dev/null \
  -p "${FIRSTRAG_TUTORIAL_PROJECT}" \
  -f docker-compose.yml \
  -f deploy/docker/docker-compose.e2e.yml \
  logs --tail=100 worker backend provider-stub
```

可以重点搜索 `vector_index_jobs` 的状态变化、worker 领取与完成、`/v1/embeddings`、`/v1/chat/completions` 和 `/chat` streaming 请求。日志中不应出现真实 API Key、JWT 或数据库密码。

## 清理与中断恢复

观察完成后回到运行脚本的终端并按 Enter。`run_full_stack_e2e.sh` 的 `EXIT` trap 会只对打印出的 Compose project 执行：

```text
docker compose ... down --volumes --remove-orphans
```

普通失败或 `Ctrl+C` 也会触发同一清理逻辑；失败时诊断日志会写到 `tmp/full-stack-e2e/docker-compose.log`。如果终端被强制关闭、Docker daemon 崩溃或机器断电导致 trap 无法执行，使用打印过的 project 名手动恢复：

```bash
export FIRSTRAG_TUTORIAL_PROJECT="<打印的 Compose project>"
docker compose \
  --env-file /dev/null \
  -p "${FIRSTRAG_TUTORIAL_PROJECT}" \
  -f docker-compose.yml \
  -f deploy/docker/docker-compose.e2e.yml \
  down --volumes --remove-orphans
```

不要对默认 FirstRAG project 执行带 `--volumes` 的清理命令。

## 端口冲突与常见故障

端口被占用时，为本次实验选择其他 loopback 端口：

```bash
FIRSTRAG_E2E_FRONTEND_PORT=13001 \
FIRSTRAG_E2E_BACKEND_PORT=18081 \
FIRSTRAG_E2E_POSTGRES_PORT=25433 \
FIRSTRAG_E2E_PAUSE_AFTER_TEST=1 \
scripts/run_full_stack_e2e.sh
```

| 现象 | 检查与恢复 |
| --- | --- |
| Docker daemon 不可用 | 启动 Docker Desktop，重新运行 `docker version`。 |
| `npx --no-install` 找不到 Playwright | 在 `frontend/` 运行 `npm ci` 和 Playwright Chromium 安装命令。 |
| 服务 180 秒内未健康 | 查看失败日志，检查端口、磁盘空间和镜像构建错误。 |
| 向量化一直等待 | 查看 `worker`、`postgres`、`chroma` 和 `provider-stub` 日志。 |
| 页面回答存在但没有 sources | 查看 browser test 输出、backend streaming 日志和 `MessageSourceList` 对应链路。 |
| 上次异常退出留下资源 | 使用准确的 Compose project 名执行手动清理，再重新运行。 |

## 隔离边界

- `--env-file /dev/null` 且 E2E override 清空 backend/worker 的 `env_file`，不会读取根 `.env`。
- 每次默认使用带进程号的 `firstrag-t089-*` Compose project；PostgreSQL、Chroma 和 uploads 使用该 project 独立 volumes。
- provider stub 只在 Compose 内部网络监听，由 seed 脚本写入测试用户设置；占位 API Key 不是外部服务凭据。
- 清理只使用当前 project 名，不删除默认 `uploads/`、`vector_db/`、数据库或其他 Compose project 的 volumes。

## 与真实 provider 路径的差异

| 无密钥实验 | 真实 provider 验收 |
| --- | --- |
| 固定 16 维 embedding，确保 vector 召回可重复。 | embedding 取决于用户选择的 provider/model/dimensions。 |
| 固定 SSE 回答和 usage，用于验证协议与 UI。 | 回答质量、token、延迟、限流和费用由真实模型决定。 |
| 强制 retrieval、关闭 query router 与 rerank，减少随机性。 | 按知识库设置运行 router、hybrid retrieval 和可选 rerank。 |
| seed 脚本直接写入隔离用户设置。 | 用户通过设置页保存并测试自己的 provider/API Key。 |
| 证明工程链路能工作，不计算 RAG 质量指标。 | 需要按 `docs/evals/README.md` 的条件运行真实 RAG/indexing eval。 |

继续阅读：[文件入库与异步索引](FILE_INGESTION_AND_INDEXING.md)、[源码地图](CODE_MAP.md)、[RAG 核心流程](../RAG_WORKFLOW.md)、[评测说明](../evals/README.md)。

# 前端、安全、测试与部署进阶

本章把 FirstRAG 的工程边界串成一条可验证路径：从浏览器状态进入 Next.js API proxy，经 FastAPI 完成认证、限流与业务编排，再由 worker 和外部 provider 执行异步或远程工作；最后用分层测试、Docker Compose、production preflight 和 GitHub required checks 判断一次改动能否交付。

本章不复制一套简化版前端或部署架构，也不要求任何真实 API Key。命令默认在仓库根目录执行；只有明确写出 `cd frontend` 的命令在前端目录运行。

## 1. 学习目标与先修条件

完成本章后，你应该能够：

- 区分浏览器、Next.js proxy、FastAPI、worker、数据存储和外部 provider 的信任边界。
- 从 `page.tsx` 找到负责请求提交、SSE 解析和消息回写的 hook。
- 解释 JWT、用户 API Key、自定义 provider URL 和 `Retry-After` 分别在哪里处理。
- 为一次改动选择合适的 Vitest、Playwright、credential-free E2E、OCR eval 或真实 RAG/indexing eval。
- 解释七个 Compose service 的职责、migration 的一次性行为和 production preflight 的限制。
- 准确说出 `main` 当前要求的四个 GitHub Actions check。
- 区分“本地 Compose 可运行”“真实 provider 链路通过”和“公网生产环境已交付”。

先修条件：

- 了解 TypeScript、React hooks、HTTP 和 SSE 基础。
- 能使用 Docker Compose、Git 和命令行。
- 已阅读[源码地图](CODE_MAP.md)、[前端说明](../FRONTEND.md)和[部署文档](../DEPLOYMENT.md)。

## 2. 信任边界：请求在哪里改变身份

先不要把整个仓库看成一个进程。一次聊天请求至少跨过五个边界：

```text
Browser
  |  JWT + user input
  v
Next.js API proxy
  |  selected headers + body / streaming response
  v
FastAPI
  |  authenticated user_id + validated business parameters
  +---------------------> PostgreSQL / Redis / Chroma
  |                              ^
  | enqueue job                  | indexed chunks / vectors
  v                              |
vector worker -------------------+
  |
  | decrypted credential only when calling provider
  v
external LLM / embedding / rerank provider
```

| 区域 | 可以信任什么 | 不能信任什么 | 当前保护点 |
| --- | --- | --- | --- |
| Browser | 当前页面自身创建的内存状态 | localStorage、URL 参数、用户输入、服务端响应都可能被篡改或泄露 | 所有资源权限仍由 FastAPI 按 `user_id` 校验。 |
| Next.js proxy | 固定的 backend origin 和仓库内 route 映射 | 浏览器带来的身份与业务字段 | 只转发允许的 header/body，保持 SSE，不实现业务授权。 |
| FastAPI | 已验证 JWT 后得到的 `user_id` | 客户端提交的资源归属、文件类型、provider 地址 | route 权限检查、schema 校验、service 业务规则、rate limit。 |
| Worker | PostgreSQL 中可领取且版本有效的 job | 过期任务、伪造 options、失效用户配置 | job lease、版本和锁保护；重新读取用户 embedding 配置。 |
| External provider | TLS 连接到已选 provider 后的响应格式 | provider 本身、网络、错误正文和自定义地址 | provider service 封装、超时/重试、错误脱敏；公开环境默认禁用自定义地址。 |

关键结论：Next.js proxy 是受控转发层，不是认证真相来源；worker 是独立执行者，不是浏览器请求的延长调用栈；外部 provider 位于系统信任边界之外。

## 3. 前端页面、状态与 API proxy

### 3.1 页面只做装配

`frontend/src/app/page.tsx` 持有当前知识库、会话等顶层选择状态，并装配职责明确的 hooks 和 UI components。学习前端时，先按行为找 owner：

| 行为 | 入口 | 主要职责 |
| --- | --- | --- |
| 工作区初始化 | `use-workspace-bootstrap.ts` | 认证检查、用户信息、初始知识库/会话和选择回退。 |
| 会话操作 | `use-conversation-actions.ts` | 创建、选择、重命名和删除会话。 |
| 文件与索引 | `use-knowledge-files.ts` | 组合 file library、mutation 和 indexing；任务轮询由 `use-vector-index-queue.ts` 处理。 |
| 发起聊天 | `use-chat-submission.ts` | 自动建会话、图片上传、用户消息事务和提交互斥。 |
| 接收回答 | `use-chat-response-stream.ts` | 发起 `/api/chat`、消费 SSE、回写 assistant content、sources、retrieval 和失败状态。 |
| SSE 解析 | `chat-stream.ts` | 把流中事件解析成稳定的前端结构。 |
| 消息呈现 | `ConversationMessageItem.tsx` | 组合正文、引用、diagnostics 与反馈入口。 |

这种划分不是为了让文件更碎，而是让“谁拥有状态、谁发请求、谁解析协议、谁负责展示”可以分别测试。跨领域刷新仍由组合 hook 或页面协调，避免两个 hook 各自维护一份不一致的真相。

### 3.2 一次聊天的状态时序

```text
ChatComposer
  -> useChatSubmission
       -> 必要时创建 conversation
       -> 可选上传图片
       -> 插入 user message
       -> useChatResponseStream
            -> 标记当前 session loading，页面显示 thinking indicator
            -> POST /api/chat
            -> Next.js route -> proxy helper -> FastAPI /chat
            -> chat-stream 逐条解析 SSE
            -> 首个 assistant 事件创建消息，后续 token 累加 content
            -> 回写 message_id / sources / retrieval
            -> success 或 failed，最后清理 loading
```

提交和响应分开管理有两个好处：提交失败不会伪装成流式解析失败；SSE 已经开始后出现的 provider 或网络错误，也能写入对应会话的错误状态。页面的 thinking indicator 由 loading 状态派生，不会为了“占位”提前持久化一条空消息。

### 3.3 Proxy 做什么、不做什么

`frontend/src/app/api/**/route.ts` 使用 `frontend/src/lib/api-proxy.ts` 访问 FastAPI。当前约定是：

- 从服务端配置解析 backend origin，不接受浏览器任意指定上游地址。
- 转发 `Authorization` 和必要的 content header，不无差别复制浏览器 header。
- 普通 JSON 错误做轻量适配；后端 `Retry-After` 原样保留。
- SSE 直接把 upstream body 交给新的 `Response`，不能先读完整再返回。
- 不检查知识库是否属于用户，不拼业务 SQL，也不保存 API Key。

如果在 proxy 中加入资源授权或重试业务，会产生第二份业务规则；如果提前消费 stream，浏览器只能在回答结束后一次性看到内容。

## 4. 认证、API Key 与自定义 provider 安全

### 4.1 JWT 的当前边界

登录后，前端 API client 从 localStorage 读取 `access_token`，以 `Authorization: Bearer <token>` 请求 Next.js proxy。收到 `401`、`403` 或明确的 token 过期错误时，前端清除认证和工作区状态并跳转登录页。

这意味着当前 JWT 不是 HttpOnly cookie：能在页面上下文执行的脚本也可能读取它。因此公网部署仍必须控制第三方脚本、依赖供应链和 XSS 风险；不能因为 FastAPI 校验了 JWT 就忽略浏览器侧防护。

### 4.2 用户 API Key 的生命周期

```text
用户输入
  -> React component memory
  -> HTTPS request through Next.js proxy
  -> FastAPI settings service
  -> Fernet encryption
  -> PostgreSQL ciphertext + masked hint

provider call
  <- service 按需解密
  -> 外部 provider
```

当前约束：

- 完整 API Key 只存在于用户输入后的组件内存、请求处理和实际 provider 调用所需的后端内存中。
- 浏览器不得把 Key 写入 localStorage、sessionStorage、URL、console、日志或错误上报。
- 设置查询只返回 `has_api_key` 与脱敏 hint，不回传密钥明文。
- 后端使用 `USER_SETTINGS_ENCRYPTION_KEY` 加密用户凭据，并要求它与 `JWT_SECRET_KEY` 分离。
- 加密主密钥丢失或错误轮换会使已有密文无法解密；数据库备份必须和受控的 secret 管理、轮换记录一起设计。

教程、测试 fixture 和问题报告都只使用明显的假值。不要把真实 Key 放入 Markdown、截图、shell history、Git commit 或 CI artifact。

### 4.3 自定义 provider URL 的 SSRF 边界

`ALLOW_USER_CUSTOM_LLM_BASE_URL` 默认是 `false`。公开环境应继续保持关闭，除非已经完成更强的出口控制、域名 allowlist 或网络隔离。

开启后，`provider_base_url.py` 仍要求地址：

- 使用 HTTPS；
- 不携带 username/password；
- 不能是 `localhost`、`.localhost`、`.local` 或非公网 IP；
- hostname 必须能解析，且所有解析结果都是公网地址。

这是一层应用校验，不等同于完整的网络出口策略。公网部署还应在基础设施层限制容器访问 metadata service、私网管理面和不必要的目标网段。

## 5. 错误、限流与安全反馈

FastAPI 在 route 层执行按业务 scope 区分的 rate limit。Compose/生产默认使用 Redis 共享状态并配置 `fail_closed`；如果 Redis 不可用，请求会被阻断，而不是绕过限流。后端统一返回 `429` 和 `Retry-After`。

前端链路如下：

```text
FastAPI 429 + Retry-After
  -> Next.js proxy 保留 header
  -> FrontendApiError(status, retryAfterSeconds)
  -> 对应 scope 的 countdown hook
  -> 按钮禁用并显示剩余秒数
  -> 倒计时结束后允许用户手动重试
```

前端不会自动重放登录、聊天、上传、向量化或模型测试。自动重放可能重复创建会话、上传文件、消耗 provider 配额或让用户误以为操作只执行了一次。

日志和 UI 的信息边界也不同：

- UI 展示安全摘要、恢复建议和剩余等待时间。
- 内部日志可记录 request ID、scope、failure type 和异常类型，但不记录 API Key、JWT、数据库密码或明文限流 identifier。
- 前端限流状态只保存 HTTP status 和等待秒数；不同业务 scope 使用独立倒计时。

## 6. 测试金字塔：每个门禁证明什么

一次“测试通过”只证明它覆盖的层次。下面的矩阵同时列出覆盖和盲区：

| 门禁 | 命令/入口 | 主要覆盖 | 不覆盖 |
| --- | --- | --- | --- |
| ESLint | `cd frontend && npm run lint` | TypeScript/React 静态规则和明显错误。 | 运行时交互、真实构建、后端行为。 |
| Vitest | `cd frontend && npm run test` | components、hooks、SSE/parser、proxy helper 和状态转换。 | 浏览器布局、真实 Next server、跨容器链路。 |
| Production build | `cd frontend && npm run build` | Next.js 编译、route bundling、类型/构建期问题。 | 用户操作和外部服务质量。 |
| Fixture Playwright | `cd frontend && CI=1 npm run test:e2e` | 独立 Next dev server 中的页面行为、请求、Blob URL、错误恢复。 | FastAPI、PostgreSQL、worker 和真实 provider；API 由 fixture 控制。 |
| Backend unittest | `cd backend && python -m unittest discover tests -v` | route/service/repository helper、脚本策略和错误边界。 | 浏览器、真实 Compose 网络与外部 provider。 |
| Credential-free full-stack E2E | `scripts/run_full_stack_e2e.sh` | 隔离 Compose project 中的注册、上传、worker、vector、检索、SSE 和 sources。 | 真实 provider 的语义质量、生产 secret/TLS/backup。 |
| OCR regression gate | `conda run -n firstrag python scripts/eval_pdf_ocr.py` | 固定样例的 OCR 质量、退化与趋势门槛。 | 普通文本 RAG 质量、所有现实扫描件。 |
| RAG/indexing eval | `scripts/eval_rag.py`、`scripts/eval_indexing.py` | 当前真实账号、用户 provider 配置和数据上的检索/索引验收。 | 公网 TLS、备份恢复、所有未知语料。 |
| Dependency audit | `scripts/npm_audit_policy.py`、`scripts/pip_audit_policy.py` | production dependency advisory 与限时例外策略。 | 业务逻辑漏洞、容器 OS package、未进入 lock/requirements 的软件。 |
| Container OS Security | CI job | first-party image 中已有修复的 HIGH/CRITICAL OS package finding。 | Python/npm 业务依赖、尚无修复的 OS finding 和应用授权逻辑。 |
| Production preflight | `scripts/production_preflight.py` | 配置、migration 方法、Compose 结构和可选 runtime health。 | 真实用户旅程、provider 回答质量、备份已可恢复、TLS 正确。 |

### 6.1 什么时候必须跑真实 eval

credential-free E2E 适合验证工程链路，不适合宣称模型或检索质量。当改动涉及以下任一项时，需要使用登录用户已经保存的 LLM/embedding 设置运行相应真实验收：

- embedding model、dimensions、chunk 或 vector metadata；
- vector/full-text recall、RRF、rerank 或 query routing；
- prompt、LLM streaming、sources 或 retrieval diagnostics；
- provider 兼容性、超时、配额或错误适配。

真实 eval 不读取或输出完整 API Key。报告中的“evaluation pass”“target-document hit”等指标必须按报告 schema 原样表述，不能改称未计算的标准 Recall@K。

### 6.2 GitHub Actions 与 required checks

`.github/workflows/ci.yml` 在 Pull Request、`main` push、每周 schedule 和手动触发时运行。当前四个稳定 job 名称是：

1. `Backend`
2. `Frontend`
3. `Full-stack E2E`
4. `Container OS Security`

`Protect main` ruleset 要求这四项全部成功、分支与目标分支保持最新、review threads 已解决，并通过 Pull Request squash merge。它没有常驻 bypass actor。

四个 job 的分工：

- `Backend`：Action pin、Python dependency audit、compile、unittest、OCR gate、migration list 和 Compose config。
- `Frontend`：npm production dependency audit、lint、Vitest、build 和 fixture Playwright。
- `Full-stack E2E`：credential-free 隔离 Compose 真实链路；失败时上传 Playwright 与 Compose diagnostics。
- `Container OS Security`：构建 first-party backend/frontend images，再用 Trivy 阻断已有修复的 HIGH/CRITICAL OS package finding；workflow 当前设置 `ignore-unfixed: true`。

PR required checks 是交付门禁，不替代本地最小验证；本地验证便于快速定位，CI 用统一环境完成最终复核。

## 7. Docker Compose、migration 与 preflight

### 7.1 七个 service

运行 `docker compose config --services` 会得到：

```text
redis
chroma
postgres
migrate
worker
backend
frontend
```

| Service | 职责 | 持久化/边界 |
| --- | --- | --- |
| `redis` | shared rate limit、热点缓存、worker runtime 状态。 | 默认不发布 host port；不是业务真相存储。 |
| `postgres` | 用户、知识库、文件 metadata、chunks、jobs、messages 与 settings。 | named volume `postgres_data`；必须备份。 |
| `chroma` | 向量集合和 similarity search。 | `${VECTOR_DB_DIR}/chroma`；不发布 host port。 |
| `migrate` | 在应用启动前执行数据库 migration。 | 一次性 job，成功退出是正常状态。 |
| `backend` | FastAPI route、权限、业务 service、SSE。 | 依赖健康的 Redis/PostgreSQL/Chroma 和成功 migration。 |
| `worker` | 领取 vector index job、解析/OCR、embedding 和双存储写入。 | 与 HTTP request 解耦；需要 uploads/models 和相同后端配置。 |
| `frontend` | Next.js UI 和 API proxy。 | 容器内只访问 `http://backend:8000`。 |

启动与观察：

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 redis postgres chroma migrate backend worker frontend
```

不要把 `migrate` 的 `Exited (0)` 当成服务崩溃；应把非零退出、重复失败或应用等待 migration 视为异常。

### 7.2 Production preflight 的两层检查

先验证 Compose 语法：

```bash
docker compose config --quiet
```

再在 `firstrag` conda 环境运行生产检查：

```bash
conda run -n firstrag python scripts/production_preflight.py \
  --env-file .env \
  --migration-method compose \
  --check-runtime-health
```

preflight 会检查 secret 是否仍为模板/弱值、JWT 与 Fernet key 是否分离、数据库与 Redis 配置、生产限流是否 `fail_closed`、数据目录、端口暴露、Compose config、migration dry-run，以及启用 runtime flag 后的 Chroma 健康状态。它只输出变量名和检查结果，不应输出 secret 值。

通过 preflight 仍不代表部署完成。它不会替你验证域名、TLS、反向代理、真实 provider、用户旅程或备份可恢复性。

## 8. 日志、备份恢复与公网部署

### 8.1 日志和健康检查

常用命令：

```bash
docker compose ps
docker compose logs --tail=100 backend worker frontend
docker compose logs --tail=100 redis postgres chroma migrate
curl -fsS http://127.0.0.1:8000/health
```

排查时用 request ID、job ID、file ID 和 conversation ID 关联事件；不要把完整 token、API Key 或 `.env` 粘进日志与 issue。Compose 的 json-file logging 已设置轮转，但生产环境仍应集中采集、限制访问并配置磁盘告警。

### 8.2 备份和恢复是一组能力

至少同时保护：

- PostgreSQL custom-format dump；
- `uploads/` 原始文件；
- `vector_db/` Chroma 数据；
- 必要时的 `models/`，以及独立保存的 secret/配置恢复流程。

`uploads/` 与 PostgreSQL metadata 必须保持一致。Chroma 理论上可重新 indexing，但重建需要原文件、用户 embedding 配置、provider 可用性和时间成本，因此公开环境仍应备份。

恢复是破坏性运维操作，本教程不让读者在日常实验中执行。按[部署文档的 PostgreSQL 备份与恢复 runbook](../DEPLOYMENT.md#postgresql-备份与恢复)在 staging 演练：停止写入服务、恢复数据库和目录、运行 migration dry-run、启动服务，再验证登录、文件、任务、检索、sources 和日志。

“有备份文件”不等于“可恢复”；需要定期记录恢复演练的时间、备份版本、恢复耗时和 smoke test 结果。

### 8.3 本地、真实验收与公网生产的区别

| 阶段 | 最低证明 | 仍未证明 |
| --- | --- | --- |
| 本地教学 | Compose healthy、credential-free E2E、基础页面可用。 | 真实 provider 兼容性、语义质量、生产安全。 |
| 真实 provider 验收 | 登录用户设置可用，上传/indexing/chat/sources 和真实 eval 通过。 | 域名/TLS、容量、备份恢复、互联网攻击面。 |
| 公网生产 | preflight、required checks、TLS/reverse proxy、只开放 80/443、secret/backup/monitoring、真实 smoke 和回滚方案均完成。 | 持续运营仍需监控、升级和定期恢复演练。 |

当前仓库提供在线 demo 方案和 Nginx 配置模板，但真实服务器、域名/TLS、生产 secret 和公网 smoke test 尚未完成。不能把本地 Compose 截图写成“已上线”。

公网环境还应保证：

- 只公开 80/443，frontend/backend/PostgreSQL 绑定 loopback，Redis/Chroma 不发布 host port；
- 反向代理只面向 frontend，保留 SSE 并关闭 buffering，限制上传体积；
- `ALLOW_PUBLIC_REGISTRATION`、自定义 provider URL、rate limit 和数据清理策略符合环境目标；
- secret 不进入 image、Git、日志和 artifact；
- 发布前备份、migration dry-run、部署后 smoke 和可执行回滚步骤齐全。

## 9. 可重复的工程验证实验

这个实验不需要真实 API Key，但需要 Docker Desktop、Node.js 依赖和 `firstrag` conda 环境已经准备好。

### 第一步：静态与前端行为

```bash
cd frontend
npm run lint
npm run test
npm run build
CI=1 npm run test:e2e
cd ..
```

观察点：lint 无 error；Vitest 全部通过；Next production build 成功；Playwright 使用 fixture 验证 UI，不应访问真实 provider。

### 第二步：Compose 与生产检查

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 redis postgres chroma migrate backend worker frontend
docker compose config --quiet
conda run -n firstrag python scripts/production_preflight.py \
  --env-file .env \
  --migration-method compose \
  --check-runtime-health
```

观察点：`redis`、`postgres`、`chroma`、`backend`、`worker` 和 `frontend` healthy/running；`migrate` 成功退出；preflight 报告通过且不打印 secret。

### 第三步：CI 配置和文档差异

```bash
python3 scripts/check_github_actions_pins.py
python3 scripts/migrate_db.py --list
git diff --check
```

这只能验证 Action 引用已固定、migration 清单可读和 patch 无空白错误。dependency audit 需要访问 advisory 数据源，最终以 CI 的联网运行结果为准。

如需验证完整无密钥业务链路，再执行：

```bash
scripts/run_full_stack_e2e.sh
```

该脚本创建隔离 Compose project 并自动清理。它与当前日常 Compose 的数据库和端口分离，详细行为见[无外部密钥入门实验](CREDENTIAL_FREE_QUICKSTART.md)。

## 10. 常见故障与诊断顺序

| 现象 | 先检查 | 不要直接得出的结论 |
| --- | --- | --- |
| 页面一次性显示完整回答 | proxy 是否提前读取 upstream body、SSE header 是否保留。 | 不要先认定 LLM 没有 streaming。 |
| 登录/聊天返回 429 | `Retry-After`、对应 scope、Redis health 和 failure mode。 | 不要自动循环重试或关闭生产限流。 |
| 设置页显示“已有 Key”但不显示原值 | `has_api_key` 和 `api_key_hint`。 | 这正是安全协议，不是读取失败。 |
| worker 一直没有处理 job | worker health、Redis、job lease、migrate、用户 embedding 配置。 | backend healthy 不代表 worker 可用。 |
| Playwright 通过但真实上传失败 | 测试是否是 fixture E2E，继续跑 credential-free full-stack E2E。 | fixture E2E 不覆盖 FastAPI 与存储。 |
| credential-free E2E 通过但回答质量差 | 使用真实账号运行 RAG/indexing eval，检查 diagnostics。 | stub 只证明协议链路。 |
| preflight 通过但公网不可访问 | 域名、TLS、Nginx、firewall、端口和公网 smoke。 | preflight 不是发布工具。 |
| 有 dump 但恢复失败 | secret、uploads/vector_db 快照时间、migration 和恢复演练记录。 | 文件存在不代表一致且可恢复。 |

## 11. 分级练习

### 基础练习

沿一次聊天请求写出以下文件的调用顺序：`ChatComposer.tsx`、`use-chat-submission.ts`、`use-chat-response-stream.ts`、Next.js chat route、`api-proxy.ts`、FastAPI chat route、`streaming.py`、`chat-stream.ts`。标记 thinking indicator 由什么状态派生、首条 assistant message 何时创建，以及哪一步持久化 sources。

### 诊断练习

在 `api-proxy.test.ts` 和 `frontend-api.test.ts` 中找到 `Retry-After` 用例，再在一个倒计时 hook 或组件测试中确认按钮恢复条件。解释为什么测试不应使用真实 Redis 或等待真实窗口时长。

### 扩展练习

为一个假想的公网发布写验收清单，至少包含 required checks、preflight、反向代理 SSE、端口暴露、secret、备份恢复演练、真实 provider smoke 和回滚。不要修改生产环境，也不要填入真实域名或凭据。

## 12. Reference 与下一步

- 前端组件、hook 与代理事实：[前端说明](../FRONTEND.md)。
- API、认证和错误协议：[API](../API.md)。
- Compose、CI、生产安全与恢复 runbook：[部署文档](../DEPLOYMENT.md)。
- RAG、indexing 和 OCR 门禁：[评测说明](../evals/README.md)。
- 纵向代码入口：[源码地图](CODE_MAP.md)。

下一步是 T-128：增加分级练习的可复用素材，并为教程链接、命令和事实漂移增加文档回归门禁。

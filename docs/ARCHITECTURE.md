# 系统架构

FirstRAG 是一个全栈 RAG 应用，当前采用 monorepo 组织：

```text
FirstRAG/
├── frontend/      # Next.js / React 前端
├── backend/       # FastAPI 后端
├── docs/          # 项目文档
├── deploy/        # 部署配置
│   ├── compose/   # Docker Compose 配置和环境变量模板
│   ├── docker/    # Docker image 构建配置
│   └── nginx/     # Nginx 反向代理模板
├── scripts/       # 初始化、迁移、维护脚本
└── .env           # 本地运行时配置，不提交
```

## 核心数据流

```text
用户上传文件
  -> Next.js API 代理
  -> FastAPI 路由层
  -> 文件落盘 + PostgreSQL 元数据
  -> 创建 vector_index_jobs 队列任务
  -> vector_index_worker 消费任务
  -> document_service 解析/切分
  -> Chroma 写入向量 + PostgreSQL 写入全文检索 chunk

用户提问
  -> Next.js API 代理
  -> FastAPI /chat
  -> rag_service 构建 LCEL 链
  -> 混合检索：向量 + 全文 + RRF + CrossEncoder
  -> LLM 流式生成
  -> SSE 返回 token、来源和检索诊断
  -> messages 持久化回答、sources、retrieval
```

## 分层边界

| 层 | 目录 | 职责 |
| --- | --- | --- |
| 前端页面 | `frontend/src/app` | 登录、注册、聊天工作台、设置页。 |
| 前端代理 | `frontend/src/app/api` | 将浏览器请求转发到后端，统一处理鉴权头与流式响应。 |
| 后端路由 | `backend/app/api` | 参数校验、认证依赖、权限检查、HTTP 错误转换。 |
| Schema | `backend/app/schemas` | Pydantic 请求模型。 |
| 服务层 | `backend/app/services` | RAG 编排、文件处理、模型调用、向量化业务流程。 |
| 仓库层 | `backend/app/repositories` | 纯 SQL 数据访问。 |
| 数据库工具 | `backend/app/db` | 连接、执行器、PostgreSQL advisory lock。 |
| 基础设施 | `backend/app/core` | 配置、JWT、安全和密钥加密。 |
| Worker | `backend/app/workers` | 异步向量化任务消费。 |

## 存储组件

- PostgreSQL：用户、知识库、文件、会话、消息、文本分块、向量化任务队列。
- Chroma：文档分块向量，默认持久化到根目录 `vector_db/chroma`。
- 本地文件系统：上传文件默认保存到根目录 `uploads/users/...`。

## 认证与权限

后端使用 JWT Bearer Token。所有用户数据接口通过 `Depends(get_current_user_id)` 取得当前用户 ID。涉及知识库、文件、会话和任务的查询必须带 `user_id` 权限隔离；不存在或不属于当前用户时统一返回 `404`。

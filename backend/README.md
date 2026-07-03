# FirstRAG 后端说明

当前项目的后端主入口是 FastAPI 应用 `backend/app/main.py`，完整启动、数据库迁移、worker 和验收流程见仓库根目录 `README.md` 与 `docs/DEPLOYMENT.md`。本文件保留早期学习 demo 的说明，方便回顾最初的本地 RAG 脚本；它不再是当前全栈应用的主要运行入口。

早期 demo 主要用于理解“本地知识库 + 向量检索 + 大语言模型回答”的基础流程：以本地文档为知识来源，使用 embedding 模型将文档切分后写入 Chroma 向量数据库，再通过检索到的上下文增强 OpenAI-compatible 模型的回答。

## 当前后端主入口

```bash
cd backend
conda activate firstrag
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

如果需要文件上传和异步向量化，同时启动 worker：

```bash
cd backend
conda activate firstrag
python -m app.workers.vector_index_worker
```

首次运行或数据库结构变化时，先在仓库根目录执行迁移：

```bash
conda run -n firstrag python scripts/migrate_db.py --dry-run
conda run -n firstrag python scripts/migrate_db.py
```

## 早期 demo 目标

- 学习 RAG 的基本工作流程
- 练习本地文档加载、切分和向量化
- 使用本地向量数据库进行相似度检索
- 将检索结果作为上下文传给大模型进行问答
- 对比普通 LLM 问答和知识库增强问答的差异

## 基本流程

```text
本地文档
  -> 文档加载
  -> 文本切分
  -> 生成 embedding
  -> 写入 Chroma 向量数据库
  -> 用户提问
  -> 检索相关片段
  -> 拼接 prompt
  -> LLM 生成回答
```

## demo 文件说明

```text
backend/demo/
├── LLM.py              # 早期 RAG 问答主流程：加载向量库、检索上下文、调用聊天模型
├── loadDoc.py          # 加载本地文档，切分文本，生成 embedding，并写入 Chroma
├── embed.py            # 单独测试智谱 embedding 接口
├── chat.py             # 单独测试 DeepSeek 对话接口和 prompt 示例
└── learn_RAG.ipynb     # RAG 学习过程中的 notebook 记录
```

## 模型配置

聊天模型和 embedding/向量模型不再通过服务端环境变量配置。Docker 或本地服务
启动后，用户登录前端设置页，分别保存当前账号的 provider、model 和 API Key。

聊天模型统一通过 OpenAI 兼容协议调用，内置 `deepseek`、`qwen`、`zhipu`、
`kimi`、`doubao`、`minimax` 六个国内厂商预设，以及
`openai_compatible` 自定义兼容地址。embedding 当前支持阿里云 Qwen
`text-embedding-v4` 和智谱 `embedding-3`。

服务端只保留生成参数默认值、用户设置加密密钥和可选 rerank 配置。远程 rerank
需要 `RERANK_PROVIDER=qwen`，并配置 `RERANK_API_KEY`、`DASHSCOPE_API_KEY`
或 `QWEN_API_KEY`；默认本地 rerank 不需要外部 Key。

首次运行前需要生成并配置独立的用户设置加密主密钥：

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
export USER_SETTINGS_ENCRYPTION_KEY="上一步生成的值"
```

后端提供聊天模型接口 `GET /user/settings/providers`、`GET /user/settings`、
`PATCH /user/settings` 和 `POST /user/settings/test`，以及向量模型接口
`GET /user/settings/embedding-providers`、`GET/PATCH /user/settings/embedding`
和 `POST /user/settings/embedding/test`。厂商列表和预设地址由 settings API
统一提供，用户 API Key 仅以密文保存，读取接口只会返回 `has_api_key` 和类似 `••••abcd` 的
`api_key_hint`，绝不返回明文。为避免 SSRF，用户自定义 `base_url` 默认
关闭；预设厂商不受影响。

每个用户可按厂商保存独立 API Key。`/user/settings/providers` 会为每个
厂商返回 `has_api_key` 与 `api_key_hint`，前端切换厂商时据此复用已保存
凭据，无需获取或重新传输完整 Key。

`POST /user/settings/test` 会优先尝试读取当前 API Key 可访问的模型列表，
并在用户已选择模型时继续执行最小对话请求。部分兼容服务不支持模型列表
接口；此时前端应允许用户手动输入模型名。

个人模式下的测试请求会先加密保存用户刚输入的 API Key 与当前配置草稿，
因此模型名称、地址或网络测试失败时，用户无需重新输入 Key。

## 使用方式

1. 将需要作为知识库的 PDF 或 Markdown 文件放入 demo 脚本约定的本地文档目录。

2. 构建本地向量数据库：

```bash
cd backend/demo
python loadDoc.py
```

3. 运行 RAG 问答示例：

```bash
cd backend/demo
python LLM.py
```

4. 可选：单独测试 embedding 或普通 LLM 调用：

```bash
cd backend/demo
python embed.py
python chat.py
```

## 当前特点

- 使用 `Chroma` 作为本地向量数据库
- 使用登录用户保存的 embedding provider 生成文本向量，支持 Qwen `text-embedding-v4` 和智谱 `embedding-3`
- 通过 OpenAI 兼容接口调用国内大语言模型作为回答模型
- 使用 LangChain LCEL 组合检索链和问答链
- 当前 prompt 更偏向“严格根据知识库回答”，适合观察 RAG 的检索增强效果

## 学习笔记

RAG 并不是对模型进行微调，而是在提问时先从知识库中检索相关内容，再把检索结果作为上下文交给大模型。模型的参数没有被更新，回答会明显受到检索内容和 prompt 约束。

如果希望模型在知识库基础上补充自己的通用知识，可以调整 `LLM.py` 中的 prompt，例如要求模型区分“知识库依据”和“模型补充”。

## demo 与当前应用的关系

早期 demo 中“依赖管理、Web UI、引用展示、批量评估”等改进方向已经在当前全栈应用中以不同形式落地：仓库根目录维护依赖和启动流程，`frontend/` 提供 Next.js 工作台，后端会返回 sources 与 retrieval diagnostics，`scripts/eval_rag.py`、`scripts/eval_indexing.py` 和 `scripts/acceptance_check.sh` 负责真实链路评估与验收。

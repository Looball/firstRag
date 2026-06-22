# FirstRAG

这是我的第一个 RAG（Retrieval-Augmented Generation，检索增强生成）学习项目，主要用于理解“本地知识库 + 向量检索 + 大语言模型回答”的基础流程。

项目当前以本地文档为知识来源，使用 embedding 模型将文档切分后写入 Chroma 向量数据库，再通过检索到的上下文增强 DeepSeek 模型的回答。

## 项目目标

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

## 文件说明

```text
.
├── LLM.py              # RAG 问答主流程：加载向量库、检索上下文、调用 DeepSeek
├── loadDoc.py          # 加载本地文档，切分文本，生成 embedding，并写入 Chroma
├── embed.py            # 单独测试智谱 embedding 接口
├── chat.py             # 单独测试 DeepSeek 对话接口和 prompt 示例
├── learn_RAG.ipynb     # RAG 学习过程中的 notebook 记录
├── 开发文档.txt         # 开发记录或说明文档
├── local_doc/          # 本地知识库文档目录，已被 .gitignore 忽略
└── vector_db/          # Chroma 向量数据库目录，已被 .gitignore 忽略
```

## 环境变量

运行前需要配置 API Key：

```bash
export LLM_PROVIDER="deepseek"
export LLM_MODEL="deepseek-v4-flash"
export LLM_API_KEY="你的模型 API Key"
export ZAI_EMD_API="你的智谱 embedding API Key"
```

聊天模型统一通过 OpenAI 兼容协议调用，内置 `deepseek`、`qwen`、`zhipu`、
`kimi`、`doubao`、`minimax` 六个国内厂商预设，以及
`openai_compatible` 自定义兼容地址。切换厂商时设置 `LLM_PROVIDER`、
`LLM_MODEL` 和 `LLM_API_KEY` 即可；需要自定义地址时额外设置
`LLM_BASE_URL`。旧的 `DEEPSEEK_API_KEY` 仍可作为 DeepSeek 的兼容回退。

如需允许用户配置自己的模型 Key，还需要生成并配置独立的加密主密钥：

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
export USER_SETTINGS_ENCRYPTION_KEY="上一步生成的值"
```

后端提供 `GET /user/settings`、`PATCH /user/settings` 和
`POST /user/settings/test` 三个已认证接口。用户 API Key 仅以密文保存，
读取接口只会返回 `has_api_key` 状态。为避免 SSRF，用户自定义
`base_url` 默认关闭；预设厂商不受影响。

## 使用方式

1. 将需要作为知识库的 PDF 或 Markdown 文件放入 `local_doc/`。

2. 构建本地向量数据库：

```bash
python loadDoc.py
```

3. 运行 RAG 问答示例：

```bash
python LLM.py
```

4. 可选：单独测试 embedding 或普通 LLM 调用：

```bash
python embed.py
python chat.py
```

## 当前特点

- 使用 `Chroma` 作为本地向量数据库
- 使用智谱 `embedding-3` 生成文本向量
- 通过 OpenAI 兼容接口调用国内大语言模型作为回答模型
- 使用 LangChain LCEL 组合检索链和问答链
- 当前 prompt 更偏向“严格根据知识库回答”，适合观察 RAG 的检索增强效果

## 学习笔记

RAG 并不是对模型进行微调，而是在提问时先从知识库中检索相关内容，再把检索结果作为上下文交给大模型。模型的参数没有被更新，回答会明显受到检索内容和 prompt 约束。

如果希望模型在知识库基础上补充自己的通用知识，可以调整 `LLM.py` 中的 prompt，例如要求模型区分“知识库依据”和“模型补充”。

## 后续可以改进

- 增加 `requirements.txt` 管理依赖
- 增加命令行参数，支持用户输入任意问题
- 展示检索到的原始文档片段和来源
- 调整 prompt，让回答区分知识库内容和模型补充
- 增加简单的 Web UI 或 Streamlit 页面
- 增加检索效果评估和不同 `k` 值对比

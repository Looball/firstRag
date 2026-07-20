# RAG 系统核心技术与实现

本文档是 FirstRAG 评测用基线知识文件，用于覆盖 RAG 核心概念、检索质量、召回、精排、上下文组织和 RRF 融合等问题。

## RAG 的核心

RAG（Retrieval-Augmented Generation，检索增强生成）的核心是：检索质量决定生成质量。

一个 RAG 系统并不是只把大模型接到知识库上，而是先从外部知识库中检索出与问题高度相关的上下文，再把这些上下文交给 LLM 生成答案。检索阶段是否能找到准确、完整、低噪声的内容，直接决定最终回答是否可靠。

RAG 的关键目标包括：

- 通过检索把模型回答约束在真实知识来源上，降低幻觉。
- 通过引用 sources 让用户能够追溯答案依据。
- 通过 retrieval diagnostics 观察召回数量、检索通道、rerank 结果和降级状态。
- 通过评测集持续检查回答质量、检索命中文件和首 token 延迟。

## 召回、精排与上下文

RAG 检索通常分为三个层次：

1. 召回阶段保证覆盖率。向量检索适合语义相似问题，全文检索适合关键词、专有名词、编号和法条类问题。
2. 融合阶段整合多路召回结果。RRF 可以把向量检索和全文检索的排名结果合并，减少单一路检索漏召回的风险。
3. 精排阶段保证精确度。CrossEncoder rerank 会逐条比较 query 和候选 chunk 的相关性，筛掉噪声内容。

上下文组织同样重要。即使召回到了正确文件，如果上下文过长、重复或噪声过高，LLM 仍可能忽略关键信息。因此生产系统需要控制 top_k、vector_top_k、fulltext_top_k、rrf_k 和 rerank_score_threshold。

## RRF 的作用

RRF（Reciprocal Rank Fusion，倒数排名融合）是一种排名融合方法。它不直接比较不同检索器的原始分数，而是根据文档在各路召回结果中的排名累加分数。

RRF 适合 RAG 混合检索，因为向量距离、全文 rank 和 BM25 类分数通常不在同一个尺度上。通过排名融合，系统可以让同时被多个通道召回的 chunk 获得更高优先级。

RRF 主要解决的问题是：如何融合向量检索和全文检索结果，得到稳定的候选排序。rerank 解决的是：如何在候选池内进一步判断 query 与 chunk 的语义相关性，得到最终展示给 LLM 的高质量上下文。

## FirstRAG 中的实现要点

FirstRAG 的 RAG pipeline 包含：

- 用户上传文件后异步执行 vector index job。
- 文档解析、chunk 切分后写入 PostgreSQL full-text chunks 和 Chroma vector store。
- 用户提问时先读取当前知识库检索设置。
- Query Router 判断是否需要检索。
- vector retriever 使用用户配置的 embedding provider 召回语义相似 chunk。
- full-text retriever 使用 PostgreSQL 检索关键词和短语命中的 chunk。
- RRF 融合向量检索和全文检索结果。
- reranker 对融合后的候选做精排。
- LLM 使用检索上下文生成回答，并返回 sources 与 retrieval diagnostics。

## 评测关注点

RAG eval 应重点检查：

- 对“RAG 的核心是什么”这类问题，答案应包含“检索”和“生成”。
- 对“RRF 是什么”或“RRF 是如何融合向量检索和全文检索结果的”这类问题，答案应包含“排名”和“融合”。
- sources 应能命中本文件或配套的 RAG 检索策略文档。
- retrieval diagnostics 应保留 top_k、vector_top_k、fulltext_top_k、rrf_k、enable_query_router 和 enable_rerank。


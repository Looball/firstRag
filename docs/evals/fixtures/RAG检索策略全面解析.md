# RAG 检索策略全面解析

本文档是 FirstRAG 评测用基线知识文件，用于覆盖混合检索、RRF 排名融合、Query Router、rerank 精排和检索参数调优等问题。

## 为什么 RAG 需要检索策略

RAG（Retrieval-Augmented Generation，检索增强生成）的回答质量取决于检索阶段是否能把正确、相关、低噪声的上下文交给 LLM。单一路检索通常存在局限：

- 向量检索擅长语义相似问题，但可能漏掉精确关键词、编号、法条和专有名词。
- 全文检索擅长关键词和短语匹配，但不一定理解同义表达和上下文语义。
- rerank 精排更准确，但成本更高，适合在候选池较小之后使用。

因此，生产 RAG 系统通常采用混合检索：先分别做向量检索和全文检索，再通过 RRF 融合排序，最后用 reranker 精排。

## 向量检索

向量检索会把用户问题转换为 query embedding，再在 Chroma vector store 中查找语义距离更近的 chunk。它适合处理表达方式不同但语义接近的问题，例如“RAG 的核心是什么”和“检索增强生成最关键的原则是什么”。

向量检索的关键参数是 `vector_top_k`。这个参数控制从向量库召回多少候选。值太小可能漏召回，值太大则会增加后续融合和 rerank 的成本。

## 全文检索

全文检索使用 PostgreSQL full-text search 和关键词匹配召回 chunk。它适合处理精确词、中文短语、文件中特定概念、编号、法条和配置项，例如 `RRF`、`rerank`、`top_k`、`rrf_k`。

全文检索的关键参数是 `fulltext_top_k`。这个参数控制从 PostgreSQL 文本分块中召回多少候选。它和 `vector_top_k` 一起决定候选池覆盖率。

## RRF 是什么

RRF（Reciprocal Rank Fusion，倒数排名融合）是一种排名融合算法，用来合并多个检索通道的排序结果。它不直接比较向量距离和全文分数，而是根据文档在每一路结果中的排名计算融合分数。

RRF 的核心思想是：一个 chunk 在某一路检索中排名越靠前，贡献越高；如果同一个 chunk 同时被向量检索和全文检索召回，它会获得来自多个通道的排名加分。

RRF 解决的问题是：如何融合向量检索和全文检索结果，得到更稳定的候选排序。它尤其适合分数尺度不同的检索器，因为向量距离、全文 rank、BM25 分数不能直接相加比较。

在 FirstRAG 中，`rrf_k` 是 RRF 的排名平滑参数。较小的 `rrf_k` 会放大头部排名差异，较大的 `rrf_k` 会让不同排名之间的差距更平滑。评测中会比较 `rrf_k=8` 和 legacy `rrf_k=10` 等设置。

## rerank 解决什么问题

RRF 负责融合召回结果，但它仍然主要依赖各通道的排名。rerank 负责进一步判断 query 与 chunk 的语义相关性。

FirstRAG 默认使用 CrossEncoder reranker。CrossEncoder 会同时读取 query 和候选 chunk，输出更精细的相关性分数。它通常比 bi-encoder 向量召回更准确，但速度更慢，因此只应该用于 RRF 融合后的少量候选。

RRF 和 rerank 的分工可以概括为：

- RRF 解决多路召回结果的排名融合问题。
- rerank 解决候选池内最终相关性排序问题。
- RRF 关注覆盖率和稳定融合，rerank 关注精确度和去噪。

## Query Router

Query Router 用来判断一个问题是否需要检索。对于“你好”这类寒暄问题，系统可以跳过检索，直接生成简短回复。对于“RRF 是什么”“RAG 的核心是什么”“民事诉讼法的任务是什么”这类需要知识依据的问题，系统应触发检索。

当 `enable_query_router=false` 时，系统不再依赖 Query Router 判断是否需要检索，而是按 retrieval mode 和当前配置执行。评测中会检查 Query Router 关闭时，diagnostics 是否保留对应设置。

## 检索参数

常见检索参数含义如下：

| 参数 | 含义 |
| --- | --- |
| `top_k` | 最终交给 LLM 或 rerank 后保留的引用数量。 |
| `vector_top_k` | 向量检索召回候选数量。 |
| `fulltext_top_k` | 全文检索召回候选数量。 |
| `rrf_k` | RRF 排名融合平滑参数。 |
| `enable_query_router` | 是否启用 Query Router 判断是否需要检索。 |
| `enable_rerank` | 是否启用 CrossEncoder rerank 精排。 |
| `rerank_score_threshold` | rerank 分数过滤阈值。 |

默认评测配置通常使用 `top_k=4`、`vector_top_k=16`、`fulltext_top_k=16`、`rrf_k=8`、`enable_query_router=true`、`enable_rerank=true`。小候选池变体可能使用 `top_k=3`、`vector_top_k=8`、`fulltext_top_k=8`、`rrf_k=4`。

## 小候选池的影响

当 `vector_top_k` 和 `fulltext_top_k` 较小时，召回覆盖率会下降，相关 chunk 更容易被漏掉。小候选池可以降低计算成本，但会增加回答缺少 sources 或命中文件不稳定的风险。

因此，调参时需要同时观察：

- source 是否命中期望文件。
- retrieved_count、fused_count、reranked_count 是否合理。
- retrieval_sources 是否同时包含 `vector` 和 `fulltext`。
- 平均首 token 延迟和总耗时是否在可接受范围内。

## 评测关注点

RAG eval 中，本文档应支持以下问题：

- “RRF 是什么”：答案应说明 RRF 是倒数排名融合，用于排名融合。
- “RRF 和 rerank 分别解决什么排序问题”：答案应区分 RRF 负责多路召回融合，rerank 负责候选相关性精排。
- “RRF 是如何融合向量检索和全文检索结果的”：答案应包含向量检索、全文检索、排名和融合。
- “RAG 的核心是什么”：可结合配套文档说明检索质量决定生成质量。


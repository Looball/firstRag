from typing import Literal

from pydantic import BaseModel, Field


# 定义新建知识库请求体数据类型
class CreateKnowledgeBaseRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)


class UpdateRetrievalSettingsRequest(BaseModel):
    """知识库级 RAG 检索策略设置。"""

    retrieval_mode: Literal["auto", "always", "never"] | None = None
    enable_query_router: bool | None = None
    enable_rerank: bool | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)
    vector_top_k: int | None = Field(default=None, ge=1, le=100)
    fulltext_top_k: int | None = Field(default=None, ge=1, le=100)
    rrf_k: int | None = Field(default=None, ge=1, le=100)
    rerank_score_threshold: float | None = Field(default=None, ge=-20, le=20)

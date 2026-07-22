from typing import Literal

from pydantic import BaseModel, Field


# 定义新建知识库请求体数据类型
class CreateKnowledgeBaseRequest(BaseModel):
    """创建知识库请求。"""

    name: str = Field(min_length=1, max_length=50)


class RenameKnowledgeBaseRequest(BaseModel):
    """重命名知识库请求。"""

    name: str = Field(min_length=1, max_length=50)


class UpdatePdfOcrCorrectionRequest(BaseModel):
    """保存扫描 PDF 页级人工修订。"""

    corrected_text: str = Field(min_length=1, max_length=50000)


class ReindexPdfOcrPagesRequest(BaseModel):
    """批量重新识别扫描 PDF 页面的请求。"""

    page_numbers: list[int] = Field(min_length=1, max_length=100)


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

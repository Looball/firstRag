"""应用层使用的 provider-neutral vector store 契约。"""

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable
from uuid import UUID

from langchain_core.documents import Document


VectorStoreErrorCategory = Literal[
    "unavailable",
    "invalid_request",
    "internal",
]


@dataclass(frozen=True)
class VectorRecord:
    """一条可审计的向量记录。"""

    id: str
    document: Document
    embedding: list[float] | None = None


@dataclass(frozen=True)
class VectorSearchResult:
    """统一为 cosine distance 语义的检索结果，数值越小越相近。"""

    document: Document
    distance: float


@dataclass(frozen=True)
class VectorSearchIssue:
    """单个过滤范围失败但其它结果仍可返回时的结构化问题。"""

    provider: str
    category: VectorStoreErrorCategory
    message: str
    file_id: str | None = None


@dataclass(frozen=True)
class VectorSearchResponse:
    """向量检索结果及可降级问题。"""

    results: list[VectorSearchResult] = field(default_factory=list)
    issues: list[VectorSearchIssue] = field(default_factory=list)


@dataclass(frozen=True)
class VectorStoreHealth:
    """vector store 健康检查结果。"""

    healthy: bool
    provider: str
    collection_name: str
    detail: str | None = None


class VectorStoreProviderError(RuntimeError):
    """屏蔽 provider 原始异常类型的统一 vector store 错误。"""

    def __init__(
        self,
        *,
        provider: str,
        operation: str,
        category: VectorStoreErrorCategory,
        message: str,
    ) -> None:
        """保存安全、可观测的 provider 错误上下文。"""
        super().__init__(message)
        self.provider = provider
        self.operation = operation
        self.category = category


@runtime_checkable
class VectorStoreBoundary(Protocol):
    """FirstRAG 业务链路实际依赖的最小 vector store 能力。"""

    @property
    def provider(self) -> str:
        """返回 provider 标识。"""
        ...

    @property
    def collection_name(self) -> str:
        """返回当前隔离 collection 名称。"""
        ...

    def ensure_collection(self) -> str:
        """确保 collection 可访问并返回其名称。"""
        ...

    def replace_file_vectors(
        self,
        *,
        user_id: int,
        file_id: UUID | str,
        documents: list[Document],
        ids: list[str],
    ) -> None:
        """幂等替换单个文件的全部向量。"""
        ...

    def delete_file_vectors(
        self,
        *,
        user_id: int,
        file_id: UUID | str,
    ) -> None:
        """删除单个用户文件的全部向量。"""
        ...

    def search_vectors(
        self,
        *,
        query_embedding: list[float],
        user_id: int,
        file_ids: list[UUID | str] | None,
        k: int,
    ) -> VectorSearchResponse:
        """按用户和可选文件范围检索，并按 distance 升序返回。"""
        ...

    def list_file_vectors(
        self,
        *,
        user_id: int,
        file_id: UUID | str,
        include_embeddings: bool = False,
    ) -> list[VectorRecord]:
        """列出单个文件的向量记录，用于审计与迁移。"""
        ...

    def count_vectors(
        self,
        *,
        user_id: int | None = None,
        file_id: UUID | str | None = None,
    ) -> int:
        """统计 collection 或指定用户/文件范围内的向量数量。"""
        ...

    def health_check(self) -> VectorStoreHealth:
        """检查 provider 与 collection 是否可访问。"""
        ...


def build_chunk_ids(chunks: list[Document]) -> list[str]:
    """按应用层 metadata 生成跨 provider 稳定的向量 ID。"""
    chunk_ids = []
    for chunk in chunks:
        user_id = chunk.metadata["user_id"]
        file_id = chunk.metadata["file_id"]
        chunk_index = chunk.metadata["chunk_index"]
        index_version = chunk.metadata["index_version"]
        chunk_ids.append(f"{user_id}:{file_id}:v{index_version}:{chunk_index}")
    return chunk_ids

"""Chroma 对 provider-neutral vector store 契约的适配实现。"""

from typing import Any
from uuid import UUID

from langchain_core.documents import Document

from app.core.sensitive_data import sanitize_sensitive_text
from app.services.vectors.vector_store import (
    VectorRecord,
    VectorSearchResponse,
    VectorSearchResult,
    VectorStoreBoundary,
    VectorStoreHealth,
    VectorStoreProviderError,
)


def _file_filter(user_id: int, file_id: UUID | str) -> dict[str, Any]:
    """构造仅在 Chroma adapter 内可见的单文件 metadata filter。"""
    return {
        "$and": [
            {"user_id": str(user_id)},
            {"file_id": str(file_id)},
        ]
    }


def _search_filter(
    user_id: int,
    file_ids: list[UUID | str] | None,
) -> dict[str, Any]:
    """构造始终包含 user_id 的 Chroma 检索范围。"""
    normalized_file_ids = sorted({str(value) for value in file_ids or []})
    if not normalized_file_ids:
        return {"user_id": str(user_id)}
    file_filter: dict[str, Any]
    if len(normalized_file_ids) == 1:
        file_filter = {"file_id": normalized_file_ids[0]}
    else:
        file_filter = {"file_id": {"$in": normalized_file_ids}}
    return {
        "$and": [
            {"user_id": str(user_id)},
            file_filter,
        ],
    }


class ChromaVectorStore:
    """把 Chroma client、filter 与私有 collection 收口在 adapter 内。"""

    def __init__(self, client: Any, collection_name: str) -> None:
        """保存 LangChain Chroma client 和已解析的 collection 名称。"""
        self._client = client
        self._collection_name = collection_name

    @property
    def provider(self) -> str:
        """返回 provider 标识。"""
        return "chroma"

    @property
    def collection_name(self) -> str:
        """返回当前 collection 名称。"""
        return self._collection_name

    def _provider_error(
        self,
        operation: str,
        exc: Exception,
    ) -> VectorStoreProviderError:
        """把 Chroma 异常分类为稳定的应用层错误。"""
        safe_error = sanitize_sensitive_text(str(exc))
        lowered = safe_error.lower()
        if any(token in lowered for token in ("timeout", "connection", "unavailable")):
            category = "unavailable"
        elif any(token in lowered for token in ("dimension", "invalid", "embedding")):
            category = "invalid_request"
        else:
            category = "internal"
        return VectorStoreProviderError(
            provider=self.provider,
            operation=operation,
            category=category,
            message=f"Chroma {operation} 失败：{safe_error}",
        )

    def _collection(self) -> Any:
        """集中访问 LangChain Chroma 的私有 collection。"""
        collection = getattr(self._client, "_collection", None)
        if collection is None:
            raise VectorStoreProviderError(
                provider=self.provider,
                operation="collection_access",
                category="internal",
                message="Chroma collection 不可访问",
            )
        return collection

    def ensure_collection(self) -> str:
        """确保 Chroma collection 已创建且可访问。"""
        try:
            collection = self._collection()
            resolved_name = str(getattr(collection, "name", "") or "")
            if resolved_name:
                self._collection_name = resolved_name
            return self._collection_name
        except VectorStoreProviderError:
            raise
        except Exception as exc:
            raise self._provider_error("ensure_collection", exc) from exc

    def replace_file_vectors(
        self,
        *,
        user_id: int,
        file_id: UUID | str,
        documents: list[Document],
        ids: list[str],
    ) -> None:
        """先过滤删除旧版本，再使用稳定 ID 写入新版本。"""
        if len(documents) != len(ids):
            raise ValueError("documents 与 ids 数量必须一致")
        try:
            self._client.delete(where=_file_filter(user_id, file_id))
            if documents:
                self._client.add_documents(documents=documents, ids=ids)
        except Exception as exc:
            raise self._provider_error("replace_file_vectors", exc) from exc

    def delete_file_vectors(
        self,
        *,
        user_id: int,
        file_id: UUID | str,
    ) -> None:
        """按用户与文件双重过滤删除全部索引版本。"""
        try:
            self._client.delete(where=_file_filter(user_id, file_id))
        except Exception as exc:
            raise self._provider_error("delete_file_vectors", exc) from exc

    def _raw_search(
        self,
        *,
        query_embedding: list[float],
        k: int,
        metadata_filter: dict[str, Any] | None,
    ) -> list[VectorSearchResult]:
        """调用 Chroma ANN 并转换为 provider-neutral 结果。"""
        options: dict[str, Any] = {
            "embedding": query_embedding,
            "k": k,
        }
        if metadata_filter is not None:
            options["filter"] = metadata_filter
        candidates = self._client.similarity_search_by_vector_with_relevance_scores(
            **options,
        )
        return [
            VectorSearchResult(document=document, distance=float(distance))
            for document, distance in candidates
        ]

    @staticmethod
    def _validate_results_scope(
        results: list[VectorSearchResult],
        *,
        user_id: int,
        file_ids: list[UUID | str] | None,
    ) -> None:
        """对 provider 返回结果执行防御性用户与文件隔离校验。"""
        normalized_user_id = str(user_id)
        allowed_file_ids = {str(value) for value in file_ids or []}
        for result in results:
            metadata = result.document.metadata
            if str(metadata.get("user_id") or "") != normalized_user_id:
                raise RuntimeError("Chroma 返回了查询用户范围外的向量")
            if (
                allowed_file_ids
                and str(metadata.get("file_id") or "") not in allowed_file_ids
            ):
                raise RuntimeError("Chroma 返回了查询文件范围外的向量")

    def search_vectors(
        self,
        *,
        query_embedding: list[float],
        user_id: int,
        file_ids: list[UUID | str] | None,
        k: int,
    ) -> VectorSearchResponse:
        """执行用户隔离检索，并保持 distance 升序语义。"""
        if k < 1:
            raise ValueError("k 必须大于 0")
        try:
            results = self._raw_search(
                query_embedding=query_embedding,
                k=k,
                metadata_filter=_search_filter(user_id, file_ids),
            )
            self._validate_results_scope(
                results,
                user_id=user_id,
                file_ids=file_ids,
            )
        except Exception as exc:
            raise self._provider_error("search_vectors", exc) from exc
        results.sort(key=lambda item: item.distance)
        return VectorSearchResponse(results=results[:k])

    def list_file_vectors(
        self,
        *,
        user_id: int,
        file_id: UUID | str,
        include_embeddings: bool = False,
    ) -> list[VectorRecord]:
        """通过 Chroma collection.get 返回统一审计记录。"""
        include = ["documents", "metadatas"]
        if include_embeddings:
            include.append("embeddings")
        try:
            result = self._collection().get(
                where=_file_filter(user_id, file_id),
                include=include,
            )
        except VectorStoreProviderError:
            raise
        except Exception as exc:
            raise self._provider_error("list_file_vectors", exc) from exc

        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []
        ids = result.get("ids") or [
            f"audit:{index}"
            for index in range(len(documents))
        ]
        embeddings = result.get("embeddings")
        records: list[VectorRecord] = []
        for index, (record_id, content, metadata) in enumerate(zip(
            ids,
            documents,
            metadatas,
            strict=False,
        )):
            embedding = None
            if embeddings is not None and index < len(embeddings):
                embedding = [float(value) for value in embeddings[index]]
            records.append(VectorRecord(
                id=str(record_id),
                document=Document(
                    page_content=str(content or ""),
                    metadata=dict(metadata or {}),
                ),
                embedding=embedding,
            ))
        return records

    def count_vectors(
        self,
        *,
        user_id: int | None = None,
        file_id: UUID | str | None = None,
    ) -> int:
        """统计 collection 或受隔离范围内的向量数量。"""
        if file_id is not None and user_id is None:
            raise ValueError("按文件统计时必须同时提供 user_id")
        try:
            collection = self._collection()
            if user_id is None:
                return int(collection.count())
            where: dict[str, Any] = {"user_id": str(user_id)}
            if file_id is not None:
                where = _file_filter(user_id, file_id)
            result = collection.get(where=where, include=[])
            return len(result.get("ids") or [])
        except VectorStoreProviderError:
            raise
        except Exception as exc:
            raise self._provider_error("count_vectors", exc) from exc

    def health_check(self) -> VectorStoreHealth:
        """以 collection count 验证 Chroma client 的真实可访问性。"""
        try:
            self.count_vectors()
        except Exception as exc:
            return VectorStoreHealth(
                healthy=False,
                provider=self.provider,
                collection_name=self.collection_name,
                detail=str(exc),
            )
        return VectorStoreHealth(
            healthy=True,
            provider=self.provider,
            collection_name=self.collection_name,
        )


def ensure_vector_store_boundary(store: Any) -> VectorStoreBoundary:
    """兼容测试注入的原始 Chroma fake，并确保业务层只使用统一契约。"""
    if isinstance(store, ChromaVectorStore):
        return store
    if isinstance(store, VectorStoreBoundary):
        return store
    collection = getattr(store, "_collection", None)
    collection_name = str(getattr(collection, "name", "") or "langchain")
    return ChromaVectorStore(store, collection_name)

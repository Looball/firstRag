"""Milvus 对 provider-neutral vector store 契约的适配实现。"""

from __future__ import annotations

from collections.abc import Sequence
import json
import math
from typing import Any
from uuid import UUID

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app.core.sensitive_data import sanitize_sensitive_text
from app.services.vectors.vector_store import (
    VectorRecord,
    VectorSearchResponse,
    VectorSearchResult,
    VectorStoreBoundary,
    VectorStoreHealth,
    VectorStoreProviderError,
    build_child_id,
)


CONTENT_MAX_BYTES = 65_535
METADATA_MAX_BYTES = 65_536
CHUNK_ID_MAX_CHARACTERS = 192
FILE_ID_MAX_CHARACTERS = 64
WRITE_BATCH_SIZE = 256
AUDIT_QUERY_BATCH_SIZE = 1_000
VECTOR_INDEX_NAME = "idx_embedding_hnsw"
SCALAR_INDEX_NAMES = {
    "user_id": "idx_user_id_inverted",
    "file_id": "idx_file_id_inverted",
    "index_version": "idx_index_version_inverted",
}


def _string_literal(value: str) -> str:
    """用 JSON string 规则生成不含表达式拼接歧义的 Milvus literal。"""
    return json.dumps(value, ensure_ascii=False)


def _file_filter(user_id: int, file_id: UUID | str) -> str:
    """构造 user/file 双重过滤表达式。"""
    return f"user_id == {int(user_id)} and file_id == {_string_literal(str(file_id))}"


def _user_filter(user_id: int) -> str:
    """构造用户级过滤表达式。"""
    return f"user_id == {int(user_id)}"


def _search_filter(
    user_id: int,
    file_ids: list[UUID | str] | None,
) -> str:
    """安全构造始终带 user_id 的单文件或多文件 scalar filter。"""
    normalized_file_ids = sorted({str(value) for value in file_ids or []})
    if not normalized_file_ids:
        return _user_filter(user_id)
    if any(
        len(file_id) > FILE_ID_MAX_CHARACTERS
        for file_id in normalized_file_ids
    ):
        raise ValueError("file_id 超过 Milvus VARCHAR(64) 限制")
    if len(normalized_file_ids) == 1:
        file_expression = f"file_id == {_string_literal(normalized_file_ids[0])}"
    else:
        literals = ", ".join(
            _string_literal(file_id)
            for file_id in normalized_file_ids
        )
        file_expression = f"file_id in [{literals}]"
    return f"{_user_filter(user_id)} and {file_expression}"


class MilvusVectorStore:
    """实现 Milvus schema、幂等文件替换、删除、审计和健康检查。"""

    def __init__(
        self,
        *,
        client: Any,
        collection_name: str,
        user_collection_prefix: str,
        embedding_model: Embeddings | None,
        dimensions: int | None,
        timeout_seconds: float,
        consistency_level: str,
    ) -> None:
        """保存已认证 client、隔离 collection 和 embedding identity。"""
        self._client = client
        self._collection_name = collection_name
        self._user_collection_prefix = user_collection_prefix
        self._embedding_model = embedding_model
        self._dimensions = dimensions
        self._timeout_seconds = timeout_seconds
        self._consistency_level = consistency_level

    @property
    def provider(self) -> str:
        """返回 provider 标识。"""
        return "milvus"

    @property
    def collection_name(self) -> str:
        """返回当前 collection 名称。"""
        return self._collection_name

    def _provider_error(
        self,
        operation: str,
        exc: Exception,
    ) -> VectorStoreProviderError:
        """将 PyMilvus 异常归类为稳定且脱敏的应用层错误。"""
        safe_error = sanitize_sensitive_text(str(exc))
        lowered = safe_error.lower()
        if any(token in lowered for token in (
            "timeout",
            "connection",
            "unavailable",
            "not ready",
        )):
            category = "unavailable"
        elif any(token in lowered for token in (
            "dimension",
            "schema",
            "invalid",
            "varchar",
            "metadata",
            "content",
        )):
            category = "invalid_request"
        else:
            category = "internal"
        return VectorStoreProviderError(
            provider=self.provider,
            operation=operation,
            category=category,
            message=f"Milvus {operation} 失败：{safe_error}",
        )

    def _expected_schema(self, dimensions: int) -> tuple[Any, Any]:
        """按 ADR 构造关闭 dynamic field 的 schema 和固定 indexes。"""
        from pymilvus import DataType, MilvusClient

        schema = MilvusClient.create_schema(
            auto_id=False,
            enable_dynamic_field=False,
        )
        schema.add_field(
            field_name="chunk_id",
            datatype=DataType.VARCHAR,
            is_primary=True,
            max_length=CHUNK_ID_MAX_CHARACTERS,
        )
        schema.add_field(
            field_name="embedding",
            datatype=DataType.FLOAT_VECTOR,
            dim=dimensions,
        )
        schema.add_field(
            field_name="content",
            datatype=DataType.VARCHAR,
            max_length=CONTENT_MAX_BYTES,
        )
        schema.add_field(field_name="user_id", datatype=DataType.INT64)
        schema.add_field(
            field_name="file_id",
            datatype=DataType.VARCHAR,
            max_length=FILE_ID_MAX_CHARACTERS,
        )
        schema.add_field(field_name="chunk_index", datatype=DataType.INT64)
        schema.add_field(field_name="index_version", datatype=DataType.INT64)
        schema.add_field(field_name="metadata", datatype=DataType.JSON)

        index_params = self._client.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_name=VECTOR_INDEX_NAME,
            index_type="HNSW",
            metric_type="COSINE",
            params={"M": 16, "efConstruction": 200},
        )
        for field_name, index_name in SCALAR_INDEX_NAMES.items():
            index_params.add_index(
                field_name=field_name,
                index_name=index_name,
                index_type="INVERTED",
            )
        return schema, index_params

    def _validate_collection(self, dimensions: int) -> None:
        """拒绝复用 schema、dimension、consistency 或 index 不兼容的 collection。"""
        from pymilvus import DataType

        description = self._client.describe_collection(
            collection_name=self.collection_name,
            timeout=self._timeout_seconds,
        )
        fields = {
            str(field.get("name")): field
            for field in description.get("fields") or []
        }
        expected_types = {
            "chunk_id": DataType.VARCHAR,
            "embedding": DataType.FLOAT_VECTOR,
            "content": DataType.VARCHAR,
            "user_id": DataType.INT64,
            "file_id": DataType.VARCHAR,
            "chunk_index": DataType.INT64,
            "index_version": DataType.INT64,
            "metadata": DataType.JSON,
        }
        if set(fields) != set(expected_types):
            raise ValueError("collection schema fields 与 ADR 不一致")
        for field_name, expected_type in expected_types.items():
            if int(fields[field_name].get("type")) != int(expected_type):
                raise ValueError(f"collection field type 不匹配：{field_name}")
        if fields["chunk_id"].get("is_primary") is not True:
            raise ValueError("chunk_id 必须是 primary key")
        expected_max_lengths = {
            "chunk_id": CHUNK_ID_MAX_CHARACTERS,
            "content": CONTENT_MAX_BYTES,
            "file_id": FILE_ID_MAX_CHARACTERS,
        }
        for field_name, expected_max_length in expected_max_lengths.items():
            actual_max_length = int(
                fields[field_name].get("params", {}).get("max_length") or 0,
            )
            if actual_max_length != expected_max_length:
                raise ValueError(f"collection VARCHAR 长度不匹配：{field_name}")
        if int(fields["embedding"].get("params", {}).get("dim") or 0) != dimensions:
            raise ValueError("collection embedding dimension 不匹配")
        if description.get("enable_dynamic_field") is not False:
            raise ValueError("collection 必须关闭 dynamic field")
        if str(description.get("consistency_level_name") or "") != self._consistency_level:
            raise ValueError("collection consistency level 不匹配")

        index_names = set(self._client.list_indexes(
            collection_name=self.collection_name,
        ))
        expected_indexes = {VECTOR_INDEX_NAME, *SCALAR_INDEX_NAMES.values()}
        if not expected_indexes.issubset(index_names):
            raise ValueError("collection indexes 与 ADR 不一致")
        vector_index = self._client.describe_index(
            collection_name=self.collection_name,
            index_name=VECTOR_INDEX_NAME,
            timeout=self._timeout_seconds,
        )
        if (
            vector_index.get("field_name") != "embedding"
            or vector_index.get("index_type") != "HNSW"
            or vector_index.get("metric_type") != "COSINE"
            or int(vector_index.get("M") or 0) != 16
            or int(vector_index.get("efConstruction") or 0) != 200
        ):
            raise ValueError("embedding HNSW index 参数与 ADR 不一致")
        for field_name, index_name in SCALAR_INDEX_NAMES.items():
            scalar_index = self._client.describe_index(
                collection_name=self.collection_name,
                index_name=index_name,
                timeout=self._timeout_seconds,
            )
            if (
                scalar_index.get("field_name") != field_name
                or scalar_index.get("index_type") != "INVERTED"
            ):
                raise ValueError(f"scalar index 不匹配：{field_name}")

    def _ensure_collection(self, dimensions: int | None = None) -> str:
        """按真实 embedding dimension 创建或严格校验 collection。"""
        resolved_dimensions = dimensions or self._dimensions
        exists = self._client.has_collection(
            collection_name=self.collection_name,
            timeout=self._timeout_seconds,
        )
        if not exists:
            if resolved_dimensions is None or resolved_dimensions < 2:
                raise ValueError("创建 Milvus collection 前必须确定 embedding dimension")
            schema, index_params = self._expected_schema(resolved_dimensions)
            try:
                self._client.create_collection(
                    collection_name=self.collection_name,
                    schema=schema,
                    index_params=index_params,
                    consistency_level=self._consistency_level,
                    timeout=self._timeout_seconds,
                )
            except Exception:
                if not self._client.has_collection(
                    collection_name=self.collection_name,
                    timeout=self._timeout_seconds,
                ):
                    raise
        if resolved_dimensions is None:
            description = self._client.describe_collection(
                collection_name=self.collection_name,
                timeout=self._timeout_seconds,
            )
            vector_field = next(
                (
                    field
                    for field in description.get("fields") or []
                    if field.get("name") == "embedding"
                ),
                None,
            )
            resolved_dimensions = int(
                (vector_field or {}).get("params", {}).get("dim") or 0
            )
        # 新建 collection 的 indexes 可能先对创建 client 可见；先 load 会等待
        # Milvus 完成 index readiness，避免其它 backend/worker client 过早校验。
        self._client.load_collection(
            collection_name=self.collection_name,
            timeout=self._timeout_seconds,
        )
        self._validate_collection(resolved_dimensions)
        self._dimensions = resolved_dimensions
        return self.collection_name

    def ensure_collection(self) -> str:
        """确保 Milvus collection 存在且 schema/index 完全兼容。"""
        try:
            return self._ensure_collection()
        except VectorStoreProviderError:
            raise
        except Exception as exc:
            raise self._provider_error("ensure_collection", exc) from exc

    def _user_collections(self) -> list[str]:
        """只列出当前用户 collection prefix 下的 embedding identities。"""
        return sorted(
            collection
            for collection in self._client.list_collections(
                timeout=self._timeout_seconds,
            )
            if str(collection).startswith(self._user_collection_prefix)
        )

    def _delete_file_from_user_collections(
        self,
        user_id: int,
        file_id: UUID | str,
    ) -> None:
        """从当前用户全部 embedding identity collections 删除同一文件。"""
        expression = _file_filter(user_id, file_id)
        for collection_name in self._user_collections():
            self._client.delete(
                collection_name=collection_name,
                filter=expression,
                timeout=self._timeout_seconds,
            )
            self._client.flush(
                collection_name=collection_name,
                timeout=self._timeout_seconds,
            )

    @staticmethod
    def _normalize_embeddings(
        embeddings: Sequence[Sequence[float]],
        expected_count: int,
    ) -> tuple[list[list[float]], int]:
        """校验 embedding 数量、维度和值域并转成普通 float list。"""
        if len(embeddings) != expected_count:
            raise ValueError("embedding 数量与 documents 不一致")
        normalized = [
            [float(value) for value in embedding]
            for embedding in embeddings
        ]
        dimensions = len(normalized[0]) if normalized else 0
        if dimensions < 2:
            raise ValueError("embedding dimension 必须大于 1")
        if any(len(embedding) != dimensions for embedding in normalized):
            raise ValueError("同一批 embeddings dimension 不一致")
        if any(
            not math.isfinite(value)
            for embedding in normalized
            for value in embedding
        ):
            raise ValueError("embedding 包含非有限值")
        if any(not any(value != 0.0 for value in embedding) for embedding in normalized):
            raise ValueError("COSINE embedding 不能是零向量")
        return normalized, dimensions

    @staticmethod
    def _build_entities(
        *,
        user_id: int,
        file_id: UUID | str,
        documents: list[Document],
        ids: list[str],
        embeddings: list[list[float]],
    ) -> list[dict[str, Any]]:
        """验证隔离字段与大小约束，并转换为 ADR entity schema。"""
        normalized_file_id = str(file_id)
        if len(normalized_file_id) > FILE_ID_MAX_CHARACTERS:
            raise ValueError("file_id 超过 Milvus VARCHAR(64) 限制")
        if len(set(ids)) != len(ids):
            raise ValueError("同一批写入包含重复 chunk_id")
        entities: list[dict[str, Any]] = []
        for document, chunk_id, embedding in zip(
            documents,
            ids,
            embeddings,
            strict=True,
        ):
            metadata = dict(document.metadata)
            if int(metadata.get("user_id")) != int(user_id):
                raise ValueError("document user_id 与写入范围不一致")
            if str(metadata.get("file_id")) != normalized_file_id:
                raise ValueError("document file_id 与写入范围不一致")
            chunk_index = int(metadata["chunk_index"])
            index_version = int(metadata["index_version"])
            if "parent_index" in metadata and "child_index" in metadata:
                expected_id = build_child_id(metadata)
            else:
                # 兼容 T-145 前的 probe/旧调用；生产切分统一走 parent/child ID。
                expected_id = (
                    f"{user_id}:{normalized_file_id}:"
                    f"v{index_version}:{chunk_index}"
                )
            if chunk_id != expected_id:
                raise ValueError("chunk_id 不符合 stable ID 契约")
            if len(chunk_id) > CHUNK_ID_MAX_CHARACTERS:
                raise ValueError("chunk_id 超过 Milvus VARCHAR(192) 限制")
            content = document.page_content
            if len(content.encode("utf-8")) > CONTENT_MAX_BYTES:
                raise ValueError("chunk content 超过 Milvus VARCHAR 上限")
            for key in ("user_id", "file_id", "chunk_index", "index_version"):
                metadata.pop(key, None)
            metadata_bytes = json.dumps(
                metadata,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            if len(metadata_bytes) > METADATA_MAX_BYTES:
                raise ValueError("chunk metadata 超过 Milvus JSON 上限")
            entities.append({
                "chunk_id": chunk_id,
                "embedding": embedding,
                "content": content,
                "user_id": int(user_id),
                "file_id": normalized_file_id,
                "chunk_index": chunk_index,
                "index_version": index_version,
                "metadata": metadata,
            })
        return entities

    def _query_file_rows(
        self,
        *,
        user_id: int,
        file_id: UUID | str,
        output_fields: list[str],
    ) -> list[dict[str, Any]]:
        """查询当前 collection 的单文件记录。"""
        if not self._client.has_collection(
            collection_name=self.collection_name,
            timeout=self._timeout_seconds,
        ):
            return []
        query_iterator = getattr(self._client, "query_iterator", None)
        if query_iterator is None:
            return list(self._client.query(
                collection_name=self.collection_name,
                filter=_file_filter(user_id, file_id),
                output_fields=output_fields,
                timeout=self._timeout_seconds,
                consistency_level=self._consistency_level,
            ))
        iterator = query_iterator(
            collection_name=self.collection_name,
            filter=_file_filter(user_id, file_id),
            output_fields=output_fields,
            batch_size=AUDIT_QUERY_BATCH_SIZE,
            limit=-1,
            timeout=self._timeout_seconds,
            consistency_level=self._consistency_level,
        )
        rows: list[dict[str, Any]] = []
        try:
            while True:
                batch = iterator.next()
                if not batch:
                    break
                rows.extend(batch)
        finally:
            iterator.close()
        return rows

    def _verify_write(
        self,
        *,
        user_id: int,
        file_id: UUID | str,
        ids: list[str],
        embeddings: list[list[float]],
    ) -> None:
        """对账 IDs/count，并执行 filtered ANN top-1 self-hit。"""
        rows = self._query_file_rows(
            user_id=user_id,
            file_id=file_id,
            output_fields=["chunk_id", "index_version"],
        )
        actual_ids = {str(row.get("chunk_id")) for row in rows}
        if len(rows) != len(ids) or actual_ids != set(ids):
            raise RuntimeError("Milvus 写后 ID/count 对账失败")
        if not ids:
            return
        search_results = self._client.search(
            collection_name=self.collection_name,
            data=[embeddings[0]],
            anns_field="embedding",
            filter=_file_filter(user_id, file_id),
            limit=1,
            output_fields=["chunk_id"],
            search_params={
                "metric_type": "COSINE",
                "params": {"ef": 64},
            },
            consistency_level=self._consistency_level,
            timeout=self._timeout_seconds,
        )
        candidate = search_results[0][0] if search_results and search_results[0] else {}
        candidate_id = candidate.get("id") or (
            candidate.get("entity") or {}
        ).get("chunk_id")
        if str(candidate_id) != ids[0]:
            raise RuntimeError("Milvus 写后 filtered ANN self-hit 失败")

    def replace_file_vectors(
        self,
        *,
        user_id: int,
        file_id: UUID | str,
        documents: list[Document],
        ids: list[str],
    ) -> None:
        """生成 embeddings 后删除旧 identities，批量 upsert 并完成写后门禁。"""
        if len(documents) != len(ids):
            raise ValueError("documents 与 ids 数量必须一致")
        if not documents:
            self.delete_file_vectors(user_id=user_id, file_id=file_id)
            return
        if self._embedding_model is None:
            raise ValueError("Milvus 写入需要当前用户的 embedding model")
        mutation_started = False
        try:
            raw_embeddings = self._embedding_model.embed_documents([
                document.page_content
                for document in documents
            ])
            embeddings, dimensions = self._normalize_embeddings(
                raw_embeddings,
                len(documents),
            )
            if self._dimensions is not None and dimensions != self._dimensions:
                raise ValueError("embedding provider 返回的 dimension 与设置不一致")
            entities = self._build_entities(
                user_id=user_id,
                file_id=file_id,
                documents=documents,
                ids=ids,
                embeddings=embeddings,
            )
            self._ensure_collection(dimensions)
            mutation_started = True
            self._delete_file_from_user_collections(user_id, file_id)
            for start in range(0, len(entities), WRITE_BATCH_SIZE):
                self._client.upsert(
                    collection_name=self.collection_name,
                    data=entities[start:start + WRITE_BATCH_SIZE],
                    timeout=self._timeout_seconds,
                )
            self._client.flush(
                collection_name=self.collection_name,
                timeout=self._timeout_seconds,
            )
            self._verify_write(
                user_id=user_id,
                file_id=file_id,
                ids=ids,
                embeddings=embeddings,
            )
        except Exception as exc:
            if mutation_started:
                try:
                    self._delete_file_from_user_collections(user_id, file_id)
                except Exception:
                    pass
            raise self._provider_error("replace_file_vectors", exc) from exc

    def import_file_vectors(
        self,
        *,
        user_id: int,
        file_id: UUID | str,
        documents: list[Document],
        ids: list[str],
        embeddings: Sequence[Sequence[float]],
        batch_size: int = WRITE_BATCH_SIZE,
    ) -> None:
        """使用既有 embeddings 幂等导入单文件，不调用外部 provider。"""
        if len(documents) != len(ids):
            raise ValueError("documents 与 ids 数量必须一致")
        if batch_size < 1 or batch_size > 1_000:
            raise ValueError("batch_size 必须在 1 到 1000 之间")
        mutation_started = False
        try:
            normalized_embeddings, dimensions = self._normalize_embeddings(
                embeddings,
                len(documents),
            )
            if self._dimensions is not None and dimensions != self._dimensions:
                raise ValueError("既有 embedding dimension 与设置不一致")
            entities = self._build_entities(
                user_id=user_id,
                file_id=file_id,
                documents=documents,
                ids=ids,
                embeddings=normalized_embeddings,
            )
            self._ensure_collection(dimensions)
            mutation_started = True
            self._client.delete(
                collection_name=self.collection_name,
                filter=_file_filter(user_id, file_id),
                timeout=self._timeout_seconds,
            )
            for start in range(0, len(entities), batch_size):
                self._client.upsert(
                    collection_name=self.collection_name,
                    data=entities[start:start + batch_size],
                    timeout=self._timeout_seconds,
                )
            self._client.flush(
                collection_name=self.collection_name,
                timeout=self._timeout_seconds,
            )
            self._verify_write(
                user_id=user_id,
                file_id=file_id,
                ids=ids,
                embeddings=normalized_embeddings,
            )
        except Exception as exc:
            if mutation_started:
                try:
                    self._client.delete(
                        collection_name=self.collection_name,
                        filter=_file_filter(user_id, file_id),
                        timeout=self._timeout_seconds,
                    )
                    self._client.flush(
                        collection_name=self.collection_name,
                        timeout=self._timeout_seconds,
                    )
                except Exception:
                    pass
            raise self._provider_error("import_file_vectors", exc) from exc

    def delete_imported_file_vectors(
        self,
        *,
        user_id: int,
        file_id: UUID | str,
    ) -> None:
        """只清理当前迁移目标 collection，不扫描其它 embedding identities。"""
        try:
            if not self._client.has_collection(
                collection_name=self.collection_name,
                timeout=self._timeout_seconds,
            ):
                return
            self._client.delete(
                collection_name=self.collection_name,
                filter=_file_filter(user_id, file_id),
                timeout=self._timeout_seconds,
            )
            self._client.flush(
                collection_name=self.collection_name,
                timeout=self._timeout_seconds,
            )
        except Exception as exc:
            raise self._provider_error(
                "delete_imported_file_vectors",
                exc,
            ) from exc

    def delete_file_vectors(
        self,
        *,
        user_id: int,
        file_id: UUID | str,
    ) -> None:
        """删除当前用户全部 embedding identities 下的文件 entities。"""
        try:
            self._delete_file_from_user_collections(user_id, file_id)
        except Exception as exc:
            raise self._provider_error("delete_file_vectors", exc) from exc

    def search_vectors(
        self,
        *,
        query_embedding: list[float],
        user_id: int,
        file_ids: list[UUID | str] | None,
        k: int,
    ) -> VectorSearchResponse:
        """执行 filtered ANN，并将 COSINE similarity 归一化为 distance。"""
        if k < 1:
            raise ValueError("k 必须大于 0")
        try:
            embeddings, dimensions = self._normalize_embeddings(
                [query_embedding],
                1,
            )
            if self._dimensions is not None and dimensions != self._dimensions:
                raise ValueError("query embedding dimension 与设置不一致")
            allowed_file_ids = {str(value) for value in file_ids or []}
            expression = _search_filter(user_id, file_ids)
            if not self._client.has_collection(
                collection_name=self.collection_name,
                timeout=self._timeout_seconds,
            ):
                return VectorSearchResponse(results=[])
            self._ensure_collection(dimensions)
            output_fields = [
                "chunk_id",
                "content",
                "user_id",
                "file_id",
                "chunk_index",
                "index_version",
                "metadata",
            ]
            search_options = {
                "collection_name": self.collection_name,
                "data": embeddings,
                "anns_field": "embedding",
                "filter": expression,
                "limit": k,
                "output_fields": output_fields,
                "search_params": {
                    "metric_type": "COSINE",
                    "params": {"ef": 64},
                },
                "consistency_level": self._consistency_level,
                "timeout": self._timeout_seconds,
            }
            search_results = self._client.search(**search_options)
            candidates = search_results[0] if search_results else []
            if not candidates:
                count_rows = self._client.query(
                    collection_name=self.collection_name,
                    filter=expression,
                    output_fields=["count(*)"],
                    consistency_level=self._consistency_level,
                    timeout=self._timeout_seconds,
                )
                scoped_count = int(
                    (count_rows[0] if count_rows else {}).get("count(*)") or 0,
                )
                if scoped_count:
                    search_results = self._client.search(**search_options)
                    candidates = search_results[0] if search_results else []
                    if not candidates:
                        raise RuntimeError(
                            "Milvus 范围内存在向量但 ANN 未返回候选",
                        )
            results: list[VectorSearchResult] = []
            for candidate in candidates:
                entity = candidate.get("entity") or candidate
                result_user_id = int(entity.get("user_id"))
                result_file_id = str(entity.get("file_id") or "")
                if result_user_id != int(user_id):
                    raise RuntimeError("Milvus 返回了查询用户范围外的向量")
                if allowed_file_ids and result_file_id not in allowed_file_ids:
                    raise RuntimeError("Milvus 返回了查询文件范围外的向量")
                similarity = float(candidate.get("distance"))
                if not math.isfinite(similarity):
                    raise RuntimeError("Milvus 返回了非有限 COSINE similarity")
                if similarity < -1.000001 or similarity > 1.000001:
                    raise RuntimeError("Milvus 返回了超出范围的 COSINE similarity")
                normalized_similarity = min(1.0, max(-1.0, similarity))
                metadata = dict(entity.get("metadata") or {})
                metadata.update({
                    "chunk_id": str(
                        entity.get("chunk_id") or candidate.get("id") or ""
                    ),
                    "user_id": result_user_id,
                    "file_id": result_file_id,
                    "chunk_index": int(entity.get("chunk_index")),
                    "index_version": int(entity.get("index_version")),
                })
                results.append(VectorSearchResult(
                    document=Document(
                        page_content=str(entity.get("content") or ""),
                        metadata=metadata,
                    ),
                    distance=1.0 - normalized_similarity,
                ))
            results.sort(key=lambda result: result.distance)
            return VectorSearchResponse(results=results[:k])
        except VectorStoreProviderError:
            raise
        except Exception as exc:
            raise self._provider_error("search_vectors", exc) from exc

    def list_file_vectors(
        self,
        *,
        user_id: int,
        file_id: UUID | str,
        include_embeddings: bool = False,
    ) -> list[VectorRecord]:
        """返回当前 identity 的单文件向量记录。"""
        output_fields = [
            "chunk_id",
            "content",
            "user_id",
            "file_id",
            "chunk_index",
            "index_version",
            "metadata",
        ]
        if include_embeddings:
            output_fields.append("embedding")
        try:
            rows = self._query_file_rows(
                user_id=user_id,
                file_id=file_id,
                output_fields=output_fields,
            )
        except Exception as exc:
            raise self._provider_error("list_file_vectors", exc) from exc

        records: list[VectorRecord] = []
        for row in rows:
            metadata = dict(row.get("metadata") or {})
            metadata.update({
                "user_id": row.get("user_id"),
                "file_id": row.get("file_id"),
                "chunk_index": row.get("chunk_index"),
                "index_version": row.get("index_version"),
            })
            embedding = row.get("embedding") if include_embeddings else None
            records.append(VectorRecord(
                id=str(row.get("chunk_id") or ""),
                document=Document(
                    page_content=str(row.get("content") or ""),
                    metadata=metadata,
                ),
                embedding=(
                    [float(value) for value in embedding]
                    if isinstance(embedding, Sequence)
                    else None
                ),
            ))
        records.sort(key=lambda record: record.id)
        return records

    def count_vectors(
        self,
        *,
        user_id: int | None = None,
        file_id: UUID | str | None = None,
    ) -> int:
        """统计当前 identity collection 或用户/文件范围。"""
        if file_id is not None and user_id is None:
            raise ValueError("按文件统计时必须同时提供 user_id")
        try:
            if not self._client.has_collection(
                collection_name=self.collection_name,
                timeout=self._timeout_seconds,
            ):
                return 0
            expression = ""
            if user_id is not None:
                expression = (
                    _file_filter(user_id, file_id)
                    if file_id is not None
                    else _user_filter(user_id)
                )
            rows = self._client.query(
                collection_name=self.collection_name,
                filter=expression,
                output_fields=["count(*)"],
                timeout=self._timeout_seconds,
                consistency_level=self._consistency_level,
            )
            return int((rows[0] if rows else {}).get("count(*)") or 0)
        except Exception as exc:
            raise self._provider_error("count_vectors", exc) from exc

    def health_check(self) -> VectorStoreHealth:
        """验证认证 client 与当前 collection schema 可访问。"""
        try:
            self.ensure_collection()
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

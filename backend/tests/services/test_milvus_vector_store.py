"""Milvus 写入、重建、删除与补偿生命周期测试。"""

import json
import math
import re
import unittest
from unittest.mock import patch

from langchain_core.documents import Document

from app.services.vectors.milvus_vector_store import MilvusVectorStore
from app.services.vectors.vector_store import VectorStoreProviderError


def _matches(expression: str, row: dict[str, object]) -> bool:
    """执行测试所需的 user_id 与 file_id scalar expression。"""
    user_match = re.search(r"user_id == (\d+)", expression)
    file_match = re.search(r"file_id == (\"(?:[^\"\\]|\\.)*\")", expression)
    file_in_match = re.search(r"file_id in (\[(?:.|\n)*\])", expression)
    if user_match and int(row["user_id"]) != int(user_match.group(1)):
        return False
    if file_match and str(row["file_id"]) != json.loads(file_match.group(1)):
        return False
    if file_in_match and str(row["file_id"]) not in json.loads(
        file_in_match.group(1),
    ):
        return False
    return True


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    """计算 fake ANN 使用的 cosine similarity。"""
    dot_product = sum(
        left_value * right_value
        for left_value, right_value in zip(left, right, strict=True)
    )
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return dot_product / (left_norm * right_norm)


class FakeEmbeddings:
    """按正文末尾数字生成确定性向量。"""

    def __init__(self, dimensions: int) -> None:
        """保存输出维度和调用次数。"""
        self.dimensions = dimensions
        self.calls = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """返回非零、同维度向量。"""
        self.calls += 1
        return [
            [float(index + 1), *([0.25] * (self.dimensions - 1))]
            for index, _ in enumerate(texts)
        ]


class FakeSparseEncoder:
    """按输入顺序生成可复现 learned sparse vectors。"""

    def __init__(self) -> None:
        """初始化调用计数和可控失败开关。"""
        self.calls = 0
        self.fail = False

    def encode_documents(self, texts: list[str]) -> list[dict[int, float]]:
        """为每个 child 返回包含共享词和独有词的 sparse vector。"""
        self.calls += 1
        if self.fail:
            raise RuntimeError("sparse encoder unavailable api_key=secret")
        return [
            {7: 0.5, 100 + index: 1.0}
            for index, _text in enumerate(texts)
        ]


class FakeMilvusClient:
    """保存在内存中的 PyMilvus client fake。"""

    def __init__(self) -> None:
        """初始化 collections 和可控写入失败点。"""
        self.collections: dict[str, dict[str, object]] = {}
        self.upsert_calls = 0
        self.fail_upsert_call: int | None = None
        self.search_calls: list[dict[str, object]] = []
        self.hybrid_search_calls: list[dict[str, object]] = []
        self.fail_search = False
        self.empty_search_calls = 0

    def prepare_index_params(self):
        """复用真实 PyMilvus IndexParams 形状。"""
        from pymilvus import MilvusClient

        return MilvusClient.prepare_index_params()

    def has_collection(self, *, collection_name: str, **_: object) -> bool:
        """判断 collection 是否存在。"""
        return collection_name in self.collections

    def create_collection(
        self,
        *,
        collection_name: str,
        schema,
        index_params,
        consistency_level: str,
        **_: object,
    ) -> None:
        """保存 schema、indexes 和 Strong consistency。"""
        description = schema.to_dict()
        description["consistency_level_name"] = consistency_level
        normalized_indexes = [
            item.to_dict() if hasattr(item, "to_dict") else dict(item)
            for item in list(index_params)
        ]
        self.collections[collection_name] = {
            "description": description,
            "indexes": {
                item["index_name"]: dict(item)
                for item in normalized_indexes
            },
            "rows": {},
        }

    def describe_collection(self, *, collection_name: str, **_: object) -> dict:
        """返回 schema 描述。"""
        return dict(self.collections[collection_name]["description"])

    def list_indexes(self, *, collection_name: str, **_: object) -> list[str]:
        """返回 index names。"""
        return list(self.collections[collection_name]["indexes"])

    def describe_index(
        self,
        *,
        collection_name: str,
        index_name: str,
        **_: object,
    ) -> dict:
        """返回 index 参数。"""
        return dict(self.collections[collection_name]["indexes"][index_name])

    def load_collection(self, **_: object) -> None:
        """模拟 collection load。"""

    def list_collections(self, **_: object) -> list[str]:
        """返回全部 collection names。"""
        return list(self.collections)

    def delete(
        self,
        *,
        collection_name: str,
        filter: str,
        **_: object,
    ) -> dict[str, int]:
        """按 user/file filter 删除记录。"""
        rows = self.collections[collection_name]["rows"]
        deleted = [
            row_id
            for row_id, row in rows.items()
            if _matches(filter, row)
        ]
        for row_id in deleted:
            rows.pop(row_id)
        return {"delete_count": len(deleted)}

    def flush(self, **_: object) -> None:
        """模拟 Strong write visibility。"""

    def upsert(
        self,
        *,
        collection_name: str,
        data: list[dict],
        **_: object,
    ) -> dict[str, int]:
        """按 chunk_id 幂等写入，并支持指定 batch 失败。"""
        self.upsert_calls += 1
        if self.fail_upsert_call == self.upsert_calls:
            raise RuntimeError("injected upsert failure")
        rows = self.collections[collection_name]["rows"]
        for row in data:
            rows[row["chunk_id"]] = dict(row)
        return {"upsert_count": len(data)}

    def query(
        self,
        *,
        collection_name: str,
        filter: str,
        output_fields: list[str],
        **_: object,
    ) -> list[dict]:
        """返回过滤后的投影或 count。"""
        rows = [
            row
            for row in self.collections[collection_name]["rows"].values()
            if _matches(filter, row)
        ]
        if output_fields == ["count(*)"]:
            return [{"count(*)": len(rows)}]
        return [
            {field: row.get(field) for field in output_fields}
            for row in rows
        ]

    def search(
        self,
        *,
        collection_name: str,
        data: list[object],
        filter: str,
        limit: int = 10,
        output_fields: list[str] | None = None,
        search_params: dict | None = None,
        **options: object,
    ) -> list[list[dict]]:
        """按 COSINE similarity 返回过滤后的 entity projection。"""
        self.search_calls.append({
            "collection_name": collection_name,
            "filter": filter,
            "limit": limit,
            "output_fields": output_fields,
            "search_params": search_params,
            **options,
        })
        if self.fail_search:
            raise TimeoutError("connection timeout api_key=secret")
        if self.empty_search_calls:
            self.empty_search_calls -= 1
            return [[]]
        rows = [
            row
            for row in self.collections[collection_name]["rows"].values()
            if _matches(filter, row)
        ]
        anns_field = str(options.get("anns_field") or "embedding")
        if anns_field == "sparse_embedding":
            query_sparse = dict(data[0])
            scored_rows = (
                (
                    sum(
                        float(weight) * float(row["sparse_embedding"].get(index, 0.0))
                        for index, weight in query_sparse.items()
                    ),
                    row,
                )
                for row in rows
            )
        else:
            scored_rows = (
                (_cosine_similarity(data[0], row["embedding"]), row)
                for row in rows
            )
        ranked = sorted(
            scored_rows,
            key=lambda item: item[0],
            reverse=True,
        )[:limit]
        return [[
            {
                "id": row["chunk_id"],
                "distance": similarity,
                "entity": {
                    field: row.get(field)
                    for field in output_fields or []
                },
            }
            for similarity, row in ranked
        ]]

    def hybrid_search(
        self,
        *,
        collection_name: str,
        reqs: list[object],
        ranker: object,
        limit: int,
        output_fields: list[str],
        **options: object,
    ) -> list[list[dict]]:
        """模拟 Milvus RRFRanker 对两路 ANN 结果做服务端融合。"""
        self.hybrid_search_calls.append({
            "collection_name": collection_name,
            "reqs": reqs,
            "ranker": ranker,
            "limit": limit,
            "output_fields": output_fields,
            **options,
        })
        rankings: list[list[dict]] = []
        for request in reqs:
            rankings.append(self.search(
                collection_name=collection_name,
                data=request._data,
                anns_field=request._anns_field,
                filter=request._expr,
                limit=request._limit,
                output_fields=output_fields,
                search_params=request._param,
                **options,
            )[0])
        fused: dict[str, tuple[float, dict]] = {}
        for ranking in rankings:
            for position, candidate in enumerate(ranking, start=1):
                chunk_id = str(candidate["id"])
                prior_score, _ = fused.get(chunk_id, (0.0, candidate))
                fused[chunk_id] = (
                    prior_score + 1.0 / (60 + position),
                    candidate,
                )
        ordered = sorted(
            fused.values(),
            key=lambda item: item[0],
            reverse=True,
        )[:limit]
        return [[{
            **candidate,
            "distance": score,
        } for score, candidate in ordered]]


def _document(
    *,
    user_id: int = 1,
    file_id: str = "file-a",
    chunk_index: int = 0,
    index_version: int = 1,
    content: str = "chunk",
) -> Document:
    """创建满足 stable ID 所需 metadata 的文档。"""
    return Document(
        page_content=content,
        metadata={
            "user_id": user_id,
            "file_id": file_id,
            "chunk_index": chunk_index,
            "index_version": index_version,
            "page_number": 1,
        },
    )


def _child_document(
    *,
    user_id: int = 1,
    file_id: str = "file-a",
    parent_index: int = 0,
    child_index: int = 0,
    chunk_index: int = 0,
    index_version: int = 1,
    content: str = "child",
) -> Document:
    """创建满足 T-145 parent/child stable identity 的 child 文档。"""
    parent_id = f"{user_id}:{file_id}:v{index_version}:p{parent_index}"
    return Document(
        page_content=content,
        metadata={
            "user_id": user_id,
            "file_id": file_id,
            "parent_id": parent_id,
            "parent_index": parent_index,
            "child_index": child_index,
            "chunk_index": chunk_index,
            "index_version": index_version,
            "page_number": 1,
        },
    )


def _chunk_id(document: Document) -> str:
    """根据测试文档生成 stable chunk ID。"""
    metadata = document.metadata
    if "parent_index" in metadata and "child_index" in metadata:
        return (
            f"{metadata['user_id']}:{metadata['file_id']}:"
            f"v{metadata['index_version']}:p{metadata['parent_index']}:"
            f"c{metadata['child_index']}"
        )
    return (
        f"{metadata['user_id']}:{metadata['file_id']}:"
        f"v{metadata['index_version']}:{metadata['chunk_index']}"
    )


def _store(
    client: FakeMilvusClient,
    *,
    dimensions: int = 2,
    collection_name: str = "firstrag_u1_identity",
    dense_sparse: bool = False,
    sparse_encoder: FakeSparseEncoder | None = None,
) -> MilvusVectorStore:
    """创建当前用户 Milvus adapter。"""
    return MilvusVectorStore(
        client=client,
        collection_name=collection_name,
        user_collection_prefix="firstrag_u1_",
        embedding_model=FakeEmbeddings(dimensions),
        sparse_encoder=(
            (sparse_encoder or FakeSparseEncoder())
            if dense_sparse
            else None
        ),
        dimensions=dimensions,
        timeout_seconds=10,
        consistency_level="Strong",
    )


class MilvusVectorStoreTests(unittest.TestCase):
    """验证 Milvus lifecycle、filtered ANN 与 ADR schema 门禁。"""

    def test_search_filters_scope_and_normalizes_cosine_distance(self) -> None:
        """多文件搜索不得越权，并按归一化 distance 升序返回。"""
        client = FakeMilvusClient()
        store = _store(client)
        documents = [
            _document(file_id="file-a", chunk_index=0, content="closest"),
            _document(file_id="file-a", chunk_index=1, content="second"),
        ]
        store.replace_file_vectors(
            user_id=1,
            file_id="file-a",
            documents=documents,
            ids=[_chunk_id(document) for document in documents],
        )
        file_b = _document(file_id="file-b", content="third")
        store.replace_file_vectors(
            user_id=1,
            file_id="file-b",
            documents=[file_b],
            ids=[_chunk_id(file_b)],
        )
        rows = client.collections[store.collection_name]["rows"]
        rows["1:file-a:v1:0"]["embedding"] = [1.0, 0.0]
        rows["1:file-a:v1:1"]["embedding"] = [0.8, 0.6]
        rows["1:file-b:v1:0"]["embedding"] = [0.0, 1.0]
        rows["2:file-a:v1:0"] = {
            **rows["1:file-a:v1:0"],
            "chunk_id": "2:file-a:v1:0",
            "user_id": 2,
            "content": "other-user",
        }

        response = store.search_vectors(
            query_embedding=[1.0, 0.0],
            user_id=1,
            file_ids=["file-b", "file-a", "file-a"],
            k=5,
        )

        self.assertEqual(
            [result.document.page_content for result in response.results],
            ["closest", "second", "third"],
        )
        self.assertEqual(
            [round(result.distance, 6) for result in response.results],
            [0.0, 0.2, 1.0],
        )
        self.assertTrue(all(
            result.document.metadata["user_id"] == 1
            for result in response.results
        ))
        search_call = client.search_calls[-1]
        self.assertEqual(
            search_call["filter"],
            'user_id == 1 and file_id in ["file-a", "file-b"]',
        )
        self.assertEqual(search_call["search_params"], {
            "metric_type": "COSINE",
            "params": {"ef": 64},
        })
        self.assertEqual(search_call["consistency_level"], "Strong")

    def test_precomputed_import_cleanup_only_touches_target_identity(self) -> None:
        """迁移清理不得扫描或删除当前用户的其它 Milvus identities。"""
        client = FakeMilvusClient()
        target = MilvusVectorStore(
            client=client,
            collection_name="firstrag_u1_target",
            user_collection_prefix="firstrag_u1_",
            embedding_model=None,
            dimensions=2,
            timeout_seconds=10,
            consistency_level="Strong",
        )
        other = _store(
            client,
            collection_name="firstrag_u1_other_identity",
        )
        document = _document(file_id="file-a", content="stored")
        chunk_id = _chunk_id(document)
        target.import_file_vectors(
            user_id=1,
            file_id="file-a",
            documents=[document],
            ids=[chunk_id],
            embeddings=[[1.0, 0.0]],
            batch_size=1,
        )
        other.replace_file_vectors(
            user_id=1,
            file_id="file-a",
            documents=[document],
            ids=[chunk_id],
        )

        target.delete_imported_file_vectors(user_id=1, file_id="file-a")

        self.assertEqual(
            target.count_vectors(user_id=1, file_id="file-a"),
            0,
        )
        self.assertEqual(
            other.count_vectors(user_id=1, file_id="file-a"),
            1,
        )

    def test_search_escapes_single_file_scalar_literal(self) -> None:
        """特殊字符必须保持为 string literal，不能改变 filter 语义。"""
        client = FakeMilvusClient()
        store = _store(client)
        document = _document(content="seed")
        store.replace_file_vectors(
            user_id=1,
            file_id="file-a",
            documents=[document],
            ids=[_chunk_id(document)],
        )

        response = store.search_vectors(
            query_embedding=[1.0, 0.0],
            user_id=1,
            file_ids=['file-\" or user_id == 2'],
            k=5,
        )

        self.assertEqual(response.results, [])
        self.assertEqual(
            client.search_calls[-1]["filter"],
            'user_id == 1 and file_id == "file-\\\" or user_id == 2"',
        )

    def test_search_missing_collection_is_empty_without_creating(self) -> None:
        """未建立当前 identity collection 时搜索应安全返回空结果。"""
        client = FakeMilvusClient()
        store = _store(client)

        response = store.search_vectors(
            query_embedding=[1.0, 0.0],
            user_id=1,
            file_ids=None,
            k=5,
        )

        self.assertEqual(response.results, [])
        self.assertEqual(client.collections, {})

    def test_search_failure_is_sanitized_and_classified(self) -> None:
        """Milvus search 异常应转为脱敏的 provider-neutral 错误。"""
        client = FakeMilvusClient()
        store = _store(client)
        document = _document()
        store.replace_file_vectors(
            user_id=1,
            file_id="file-a",
            documents=[document],
            ids=[_chunk_id(document)],
        )
        client.fail_search = True

        with self.assertRaises(VectorStoreProviderError) as raised:
            store.search_vectors(
                query_embedding=[1.0, 0.0],
                user_id=1,
                file_ids=["file-a"],
                k=5,
            )

        self.assertEqual(raised.exception.provider, "milvus")
        self.assertEqual(raised.exception.category, "unavailable")
        self.assertNotIn("secret", str(raised.exception))

    def test_search_retries_exact_scope_when_rows_exist_but_ann_is_empty(
        self,
    ) -> None:
        """首次 ANN 暂不可见时只允许在相同 scalar scope 内重试。"""
        client = FakeMilvusClient()
        store = _store(client)
        document = _document(content="visible-after-retry")
        store.replace_file_vectors(
            user_id=1,
            file_id="file-a",
            documents=[document],
            ids=[_chunk_id(document)],
        )
        prior_search_calls = len(client.search_calls)
        client.empty_search_calls = 1

        response = store.search_vectors(
            query_embedding=[1.0, 0.25],
            user_id=1,
            file_ids=["file-a"],
            k=5,
        )

        retry_calls = client.search_calls[prior_search_calls:]
        self.assertEqual(len(retry_calls), 2)
        self.assertEqual(
            {call["filter"] for call in retry_calls},
            {'user_id == 1 and file_id == "file-a"'},
        )
        self.assertEqual(
            response.results[0].document.page_content,
            "visible-after-retry",
        )

    def test_replace_creates_adr_schema_indexes_and_is_idempotent(self) -> None:
        """首次创建应固定 schema/index，重复重建只保留新版本。"""
        client = FakeMilvusClient()
        store = _store(client)
        old = _document(content="old", index_version=1)
        store.replace_file_vectors(
            user_id=1,
            file_id="file-a",
            documents=[old],
            ids=[_chunk_id(old)],
        )

        description = client.describe_collection(
            collection_name=store.collection_name,
        )
        fields = {field["name"]: field for field in description["fields"]}
        self.assertEqual(set(fields), {
            "chunk_id",
            "embedding",
            "content",
            "user_id",
            "file_id",
            "chunk_index",
            "index_version",
            "metadata",
        })
        self.assertFalse(description["enable_dynamic_field"])
        self.assertEqual(description["consistency_level_name"], "Strong")
        vector_index = client.describe_index(
            collection_name=store.collection_name,
            index_name="idx_embedding_hnsw",
        )
        self.assertEqual(vector_index["index_type"], "HNSW")
        self.assertEqual(vector_index["metric_type"], "COSINE")
        self.assertEqual(vector_index["M"], 16)
        self.assertEqual(vector_index["efConstruction"], 200)

        replacement = _document(content="new", index_version=2)
        store.replace_file_vectors(
            user_id=1,
            file_id="file-a",
            documents=[replacement],
            ids=[_chunk_id(replacement)],
        )
        records = store.list_file_vectors(user_id=1, file_id="file-a")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].id, "1:file-a:v2:0")
        self.assertEqual(records[0].document.page_content, "new")
        self.assertEqual(records[0].document.metadata["page_number"], 1)

    def test_dense_sparse_replace_creates_v2_schema_and_audits_both_vectors(
        self,
    ) -> None:
        """v2 写入应保存层级字段并完成 dense/sparse 双 self-hit。"""
        client = FakeMilvusClient()
        sparse_encoder = FakeSparseEncoder()
        store = _store(
            client,
            collection_name="firstrag_u1_v2_identity",
            dense_sparse=True,
            sparse_encoder=sparse_encoder,
        )
        documents = [
            _child_document(child_index=0, chunk_index=0, content="first"),
            _child_document(child_index=1, chunk_index=1, content="second"),
        ]
        ids = [_chunk_id(document) for document in documents]

        store.replace_file_vectors(
            user_id=1,
            file_id="file-a",
            documents=documents,
            ids=ids,
        )

        description = client.describe_collection(
            collection_name=store.collection_name,
        )
        fields = {field["name"]: field for field in description["fields"]}
        self.assertEqual(set(fields), {
            "chunk_id",
            "embedding",
            "sparse_embedding",
            "content",
            "user_id",
            "file_id",
            "chunk_index",
            "index_version",
            "parent_id",
            "parent_index",
            "child_index",
            "metadata",
        })
        sparse_index = client.describe_index(
            collection_name=store.collection_name,
            index_name="idx_sparse_embedding_inverted",
        )
        self.assertEqual(sparse_index["index_type"], "SPARSE_INVERTED_INDEX")
        self.assertEqual(sparse_index["metric_type"], "IP")
        self.assertEqual(sparse_index["inverted_index_algo"], "DAAT_MAXSCORE")
        rows = client.collections[store.collection_name]["rows"]
        self.assertEqual(rows[ids[0]]["parent_id"], "1:file-a:v1:p0")
        self.assertEqual(rows[ids[1]]["child_index"], 1)
        self.assertEqual(rows[ids[0]]["sparse_embedding"], {7: 0.5, 100: 1.0})
        self.assertEqual(sparse_encoder.calls, 1)
        self.assertEqual(
            [call["anns_field"] for call in client.search_calls[-2:]],
            ["embedding", "sparse_embedding"],
        )
        self.assertEqual(
            client.search_calls[-1]["search_params"],
            {"metric_type": "IP", "params": {"drop_ratio_search": 0.0}},
        )

    def test_hybrid_search_uses_one_milvus_rrf_with_identical_scope(
        self,
    ) -> None:
        """dense/sparse 必须共享 filter，并通过一次 Milvus hybrid_search 融合。"""
        client = FakeMilvusClient()
        store = _store(
            client,
            collection_name="firstrag_u1_v2_identity",
            dense_sparse=True,
        )
        documents = [
            _child_document(child_index=0, chunk_index=0, content="first"),
            _child_document(child_index=1, chunk_index=1, content="second"),
        ]
        store.replace_file_vectors(
            user_id=1,
            file_id="file-a",
            documents=documents,
            ids=[_chunk_id(document) for document in documents],
        )

        response = store.hybrid_search_vectors(
            query_embedding=[1.0, 0.25],
            query_sparse_embedding={7: 0.5, 100: 1.0},
            user_id=1,
            file_ids=["file-a"],
            dense_k=8,
            sparse_k=9,
            k=5,
            rrf_rank_constant=60,
        )

        self.assertEqual(len(client.hybrid_search_calls), 1)
        call = client.hybrid_search_calls[0]
        requests = call["reqs"]
        self.assertEqual(
            [request._anns_field for request in requests],
            ["embedding", "sparse_embedding"],
        )
        self.assertEqual(
            {request._expr for request in requests},
            {'user_id == 1 and file_id == "file-a"'},
        )
        self.assertEqual([request._limit for request in requests], [8, 9])
        self.assertEqual(
            [result.document.metadata["retrieval_sources"]
             for result in response.results],
            [["dense", "sparse"], ["dense", "sparse"]],
        )
        self.assertTrue(all(
            result.document.metadata["parent_id"] == "1:file-a:v1:p0"
            for result in response.results
        ))

    def test_hybrid_boundary_supports_dense_and_sparse_single_routes(
        self,
    ) -> None:
        """任一路 query vector 缺失时 adapter 应执行相同 scope 的单路 ANN。"""
        client = FakeMilvusClient()
        store = _store(
            client,
            collection_name="firstrag_u1_v2_identity",
            dense_sparse=True,
        )
        document = _child_document(content="single route")
        store.replace_file_vectors(
            user_id=1,
            file_id="file-a",
            documents=[document],
            ids=[_chunk_id(document)],
        )

        dense = store.hybrid_search_vectors(
            query_embedding=[1.0, 0.25],
            query_sparse_embedding=None,
            user_id=1,
            file_ids=["file-a"],
            dense_k=8,
            sparse_k=9,
            k=5,
            rrf_rank_constant=60,
        )
        sparse = store.hybrid_search_vectors(
            query_embedding=None,
            query_sparse_embedding={7: 1.0},
            user_id=1,
            file_ids=["file-a"],
            dense_k=8,
            sparse_k=9,
            k=5,
            rrf_rank_constant=60,
        )

        self.assertEqual(
            dense.results[0].document.metadata["retrieval_sources"],
            ["dense"],
        )
        self.assertEqual(
            sparse.results[0].document.metadata["retrieval_sources"],
            ["sparse"],
        )
        self.assertEqual(
            {call["filter"] for call in client.search_calls[-2:]},
            {'user_id == 1 and file_id == "file-a"'},
        )

    def test_sparse_generation_failure_preserves_previous_v2_vectors(self) -> None:
        """sparse 生成失败必须发生在 mutation 前并保留上一版本。"""
        client = FakeMilvusClient()
        sparse_encoder = FakeSparseEncoder()
        store = _store(
            client,
            collection_name="firstrag_u1_v2_identity",
            dense_sparse=True,
            sparse_encoder=sparse_encoder,
        )
        original = _child_document(index_version=1, content="original")
        store.replace_file_vectors(
            user_id=1,
            file_id="file-a",
            documents=[original],
            ids=[_chunk_id(original)],
        )
        sparse_encoder.fail = True
        replacement = _child_document(index_version=2, content="replacement")

        with self.assertRaises(VectorStoreProviderError) as raised:
            store.replace_file_vectors(
                user_id=1,
                file_id="file-a",
                documents=[replacement],
                ids=[_chunk_id(replacement)],
            )

        self.assertNotIn("secret", str(raised.exception))
        records = store.list_file_vectors(user_id=1, file_id="file-a")
        self.assertEqual([record.id for record in records], [_chunk_id(original)])

    def test_zero_sparse_vector_is_rejected_before_mutation(self) -> None:
        """空或全零 learned sparse vector 不得进入 Milvus。"""
        client = FakeMilvusClient()
        sparse_encoder = FakeSparseEncoder()
        store = _store(
            client,
            collection_name="firstrag_u1_v2_identity",
            dense_sparse=True,
            sparse_encoder=sparse_encoder,
        )
        document = _child_document()
        with patch.object(
            sparse_encoder,
            "encode_documents",
            return_value=[{7: 0.0}],
        ), self.assertRaisesRegex(VectorStoreProviderError, "零向量"):
            store.replace_file_vectors(
                user_id=1,
                file_id="file-a",
                documents=[document],
                ids=[_chunk_id(document)],
            )

        self.assertEqual(client.collections, {})

    def test_v2_adapter_rejects_dense_only_collection_without_deleting_rows(
        self,
    ) -> None:
        """v2 identity 不得原地复用 dense-only schema。"""
        client = FakeMilvusClient()
        collection_name = "firstrag_u1_shared_identity"
        dense_store = _store(client, collection_name=collection_name)
        legacy = _document(index_version=1, content="legacy")
        dense_store.replace_file_vectors(
            user_id=1,
            file_id="file-a",
            documents=[legacy],
            ids=[_chunk_id(legacy)],
        )
        v2_store = _store(
            client,
            collection_name=collection_name,
            dense_sparse=True,
        )
        child = _child_document(index_version=2, content="v2")

        with self.assertRaisesRegex(VectorStoreProviderError, "schema fields"):
            v2_store.replace_file_vectors(
                user_id=1,
                file_id="file-a",
                documents=[child],
                ids=[_chunk_id(child)],
            )

        records = dense_store.list_file_vectors(user_id=1, file_id="file-a")
        self.assertEqual([record.id for record in records], [_chunk_id(legacy)])

    def test_v2_replace_preserves_separate_dense_only_rollback_identity(
        self,
    ) -> None:
        """写入独立 v2 collection 时不得删除旧 dense-only rollback 数据。"""
        client = FakeMilvusClient()
        dense_store = _store(
            client,
            collection_name="firstrag_u1_dense_identity",
        )
        legacy = _document(index_version=1, content="legacy")
        dense_store.replace_file_vectors(
            user_id=1,
            file_id="file-a",
            documents=[legacy],
            ids=[_chunk_id(legacy)],
        )
        v2_store = _store(
            client,
            collection_name="firstrag_u1_v2_identity",
            dense_sparse=True,
        )
        child = _child_document(index_version=2, content="v2")

        v2_store.replace_file_vectors(
            user_id=1,
            file_id="file-a",
            documents=[child],
            ids=[_chunk_id(child)],
        )

        self.assertEqual(
            dense_store.count_vectors(user_id=1, file_id="file-a"),
            1,
        )
        self.assertEqual(
            v2_store.count_vectors(user_id=1, file_id="file-a"),
            1,
        )
        v2_store.delete_current_file_vectors(user_id=1, file_id="file-a")
        self.assertEqual(
            dense_store.count_vectors(user_id=1, file_id="file-a"),
            1,
        )
        self.assertEqual(
            v2_store.count_vectors(user_id=1, file_id="file-a"),
            0,
        )

    def test_dimension_mismatch_preserves_previous_vectors(self) -> None:
        """schema 不兼容时必须在 delete 前失败，保留上一版本。"""
        client = FakeMilvusClient()
        original_store = _store(client, dimensions=2)
        original = _document(index_version=1)
        original_store.replace_file_vectors(
            user_id=1,
            file_id="file-a",
            documents=[original],
            ids=[_chunk_id(original)],
        )

        incompatible_store = _store(client, dimensions=3)
        replacement = _document(index_version=2)
        with self.assertRaises(VectorStoreProviderError):
            incompatible_store.replace_file_vectors(
                user_id=1,
                file_id="file-a",
                documents=[replacement],
                ids=[_chunk_id(replacement)],
            )

        records = original_store.list_file_vectors(user_id=1, file_id="file-a")
        self.assertEqual([record.id for record in records], ["1:file-a:v1:0"])

    def test_partial_upsert_failure_cleans_all_file_rows(self) -> None:
        """中途写入失败时不得留下半批 entities。"""
        client = FakeMilvusClient()
        client.fail_upsert_call = 2
        store = _store(client)
        documents = [
            _document(chunk_index=0, content="a"),
            _document(chunk_index=1, content="b"),
        ]

        with patch(
            "app.services.vectors.milvus_vector_store.WRITE_BATCH_SIZE",
            1,
        ), self.assertRaises(VectorStoreProviderError):
            store.replace_file_vectors(
                user_id=1,
                file_id="file-a",
                documents=documents,
                ids=[_chunk_id(document) for document in documents],
            )

        self.assertEqual(store.count_vectors(user_id=1, file_id="file-a"), 0)

    def test_delete_cleans_all_user_identities_but_not_other_users(self) -> None:
        """重建/永久删除应清理当前用户旧 dimensions，不越权其它用户。"""
        client = FakeMilvusClient()
        first = _store(client, collection_name="firstrag_u1_first")
        second = _store(client, collection_name="firstrag_u1_second")
        other = MilvusVectorStore(
            client=client,
            collection_name="firstrag_u2_identity",
            user_collection_prefix="firstrag_u2_",
            embedding_model=FakeEmbeddings(2),
            dimensions=2,
            timeout_seconds=10,
            consistency_level="Strong",
        )
        for store, user_id in ((first, 1), (second, 1), (other, 2)):
            document = _document(user_id=user_id, index_version=1)
            store.replace_file_vectors(
                user_id=user_id,
                file_id="file-a",
                documents=[document],
                ids=[_chunk_id(document)],
            )

        first.delete_file_vectors(user_id=1, file_id="file-a")

        self.assertEqual(first.count_vectors(), 0)
        self.assertEqual(second.count_vectors(), 0)
        self.assertEqual(other.count_vectors(user_id=2, file_id="file-a"), 1)

    def test_invalid_payload_does_not_delete_previous_vectors(self) -> None:
        """metadata/payload 校验发生在 mutation 前，旧数据应继续可用。"""
        client = FakeMilvusClient()
        store = _store(client)
        original = _document(index_version=1)
        store.replace_file_vectors(
            user_id=1,
            file_id="file-a",
            documents=[original],
            ids=[_chunk_id(original)],
        )
        invalid = _document(index_version=2)
        invalid.metadata["not_json"] = object()

        with self.assertRaises(VectorStoreProviderError):
            store.replace_file_vectors(
                user_id=1,
                file_id="file-a",
                documents=[invalid],
                ids=[_chunk_id(invalid)],
            )

        records = store.list_file_vectors(user_id=1, file_id="file-a")
        self.assertEqual([record.id for record in records], ["1:file-a:v1:0"])

    def test_duplicate_chunk_ids_are_rejected_before_mutation(self) -> None:
        """重复 stable ID 必须在删除旧版本前失败，避免 count 审计被集合掩盖。"""
        client = FakeMilvusClient()
        store = _store(client)
        original = _document(index_version=1)
        store.replace_file_vectors(
            user_id=1,
            file_id="file-a",
            documents=[original],
            ids=[_chunk_id(original)],
        )
        replacements = [
            _document(chunk_index=0, index_version=2, content="first"),
            _document(chunk_index=0, index_version=2, content="duplicate"),
        ]

        with self.assertRaisesRegex(VectorStoreProviderError, "重复 chunk_id"):
            store.replace_file_vectors(
                user_id=1,
                file_id="file-a",
                documents=replacements,
                ids=[_chunk_id(document) for document in replacements],
            )

        records = store.list_file_vectors(user_id=1, file_id="file-a")
        self.assertEqual([record.id for record in records], ["1:file-a:v1:0"])


if __name__ == "__main__":
    unittest.main()

"""T-142/T-143 真实 Milvus dense+sparse 生命周期与 hybrid search probe。"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app.core.config import (
    MILVUS_CONSISTENCY_LEVEL,
    MILVUS_DATABASE,
    MILVUS_TIMEOUT_SECONDS,
    MILVUS_TOKEN,
    MILVUS_URI,
)
from app.services.sparse_encoder_client import SparseEncoderClient
from app.services.vectors.milvus_vector_store import MilvusVectorStore
from app.services.vectors.vector_store import build_chunk_ids


PROBE_USER_ID = 900_142
OTHER_USER_ID = 900_143
PROBE_FILE_ID = "00000000-0000-0000-0000-000000000142"
PROBE_PREFIX = "firstrag_t142_probe_u900142_"
OTHER_PREFIX = "firstrag_t142_probe_u900143_"
PROBE_COLLECTION = f"{PROBE_PREFIX}v2"
ROLLBACK_COLLECTION = f"{PROBE_PREFIX}dense"
OTHER_COLLECTION = f"{OTHER_PREFIX}v2"
PROBE_DIMENSIONS = 3


class ProbeEmbeddings(Embeddings):
    """为 probe child 生成确定性、非零 dense vectors。"""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """按顺序生成可执行 COSINE self-hit 的 dense vectors。"""
        return [
            [1.0, float(index + 1) / 10.0, 0.25]
            for index, _text in enumerate(texts)
        ]

    def embed_query(self, text: str) -> list[float]:
        """返回首个 child 的固定 dense vector。"""
        del text
        return [1.0, 0.1, 0.25]


def _client() -> Any:
    """创建使用当前 Compose 配置的 authenticated Milvus client。"""
    from pymilvus import MilvusClient

    return MilvusClient(
        uri=MILVUS_URI,
        token=MILVUS_TOKEN,
        db_name=MILVUS_DATABASE,
        timeout=MILVUS_TIMEOUT_SECONDS,
    )


def _store(
    client: Any,
    *,
    collection_name: str,
    prefix: str,
    writable: bool,
    dense_sparse: bool = True,
) -> MilvusVectorStore:
    """构造绑定真实 BGE-M3 sparse encoder 的 v2 probe adapter。"""
    return MilvusVectorStore(
        client=client,
        collection_name=collection_name,
        user_collection_prefix=prefix,
        embedding_model=ProbeEmbeddings() if writable else None,
        sparse_encoder=SparseEncoderClient() if dense_sparse else None,
        dimensions=PROBE_DIMENSIONS,
        timeout_seconds=MILVUS_TIMEOUT_SECONDS,
        consistency_level=MILVUS_CONSISTENCY_LEVEL,
    )


def _documents(
    *,
    user_id: int,
    file_id: str,
    version: int,
    count: int,
) -> list[Document]:
    """构造包含稳定 parent/child identity 的非敏感 probe documents。"""
    parent_id = f"{user_id}:{file_id}:v{version}:p0"
    return [
        Document(
            page_content=(
                f"T-142 learned sparse probe version {version} child {child_index}"
            ),
            metadata={
                "user_id": user_id,
                "file_id": file_id,
                "index_version": version,
                "parent_id": parent_id,
                "parent_index": 0,
                "child_index": child_index,
                "chunk_index": child_index,
                "probe": "T-142",
            },
        )
        for child_index in range(count)
    ]


def _write(
    store: MilvusVectorStore,
    *,
    user_id: int,
    file_id: str,
    version: int,
    count: int,
) -> list[str]:
    """通过生产 adapter 生成双向量并写入一个文件版本。"""
    documents = _documents(
        user_id=user_id,
        file_id=file_id,
        version=version,
        count=count,
    )
    ids = build_chunk_ids(documents)
    store.replace_file_vectors(
        user_id=user_id,
        file_id=file_id,
        documents=documents,
        ids=ids,
    )
    return ids


def run_probe() -> dict[str, object]:
    """执行 v2 schema、双 self-hit、重建、删除和跨用户隔离门禁。"""
    client = _client()
    try:
        for collection_name in (
            PROBE_COLLECTION,
            ROLLBACK_COLLECTION,
            OTHER_COLLECTION,
        ):
            if client.has_collection(collection_name=collection_name):
                client.drop_collection(collection_name=collection_name)

        primary = _store(
            client,
            collection_name=PROBE_COLLECTION,
            prefix=PROBE_PREFIX,
            writable=True,
        )
        rollback = _store(
            client,
            collection_name=ROLLBACK_COLLECTION,
            prefix=PROBE_PREFIX,
            writable=True,
            dense_sparse=False,
        )
        other = _store(
            client,
            collection_name=OTHER_COLLECTION,
            prefix=OTHER_PREFIX,
            writable=True,
        )
        rollback_ids = _write(
            rollback,
            user_id=PROBE_USER_ID,
            file_id=PROBE_FILE_ID,
            version=1,
            count=2,
        )
        first_ids = _write(
            primary,
            user_id=PROBE_USER_ID,
            file_id=PROBE_FILE_ID,
            version=1,
            count=2,
        )
        other_ids = _write(
            other,
            user_id=OTHER_USER_ID,
            file_id=PROBE_FILE_ID,
            version=1,
            count=2,
        )

        rebuilt_ids = _write(
            primary,
            user_id=PROBE_USER_ID,
            file_id=PROBE_FILE_ID,
            version=2,
            count=2,
        )
        query_sparse = SparseEncoderClient().encode_query(
            "T-142 learned sparse probe version 2 child 0",
        )
        hybrid_response = primary.hybrid_search_vectors(
            query_embedding=[1.0, 0.1, 0.25],
            query_sparse_embedding=query_sparse,
            user_id=PROBE_USER_ID,
            file_ids=[PROBE_FILE_ID],
            dense_k=4,
            sparse_k=4,
            k=2,
            rrf_rank_constant=60,
        )
        dense_response = primary.hybrid_search_vectors(
            query_embedding=[1.0, 0.1, 0.25],
            query_sparse_embedding=None,
            user_id=PROBE_USER_ID,
            file_ids=[PROBE_FILE_ID],
            dense_k=4,
            sparse_k=4,
            k=2,
            rrf_rank_constant=60,
        )
        sparse_response = primary.hybrid_search_vectors(
            query_embedding=None,
            query_sparse_embedding=query_sparse,
            user_id=PROBE_USER_ID,
            file_ids=[PROBE_FILE_ID],
            dense_k=4,
            sparse_k=4,
            k=2,
            rrf_rank_constant=60,
        )

        description = client.describe_collection(
            collection_name=PROBE_COLLECTION,
        )
        fields = {
            str(field.get("name"))
            for field in description.get("fields") or []
        }
        indexes = set(client.list_indexes(collection_name=PROBE_COLLECTION))
        records = primary.list_file_vectors(
            user_id=PROBE_USER_ID,
            file_id=PROBE_FILE_ID,
        )
        cross_user_count = primary.count_vectors(
            user_id=OTHER_USER_ID,
            file_id=PROBE_FILE_ID,
        )
        other_count_before_delete = other.count_vectors(
            user_id=OTHER_USER_ID,
            file_id=PROBE_FILE_ID,
        )
        rollback_count_before_delete = rollback.count_vectors(
            user_id=PROBE_USER_ID,
            file_id=PROBE_FILE_ID,
        )
        primary.delete_file_vectors(
            user_id=PROBE_USER_ID,
            file_id=PROBE_FILE_ID,
        )
        deleted_count = primary.count_vectors(
            user_id=PROBE_USER_ID,
            file_id=PROBE_FILE_ID,
        )
        rollback_count_after_delete = rollback.count_vectors(
            user_id=PROBE_USER_ID,
            file_id=PROBE_FILE_ID,
        )
        other_count_after_delete = other.count_vectors(
            user_id=OTHER_USER_ID,
            file_id=PROBE_FILE_ID,
        )

        ok = (
            fields.issuperset({
                "embedding",
                "sparse_embedding",
                "parent_id",
                "parent_index",
                "child_index",
            })
            and indexes.issuperset({
                "idx_embedding_hnsw",
                "idx_sparse_embedding_inverted",
                "idx_parent_id_inverted",
            })
            and first_ids != rebuilt_ids
            and [record.id for record in records] == rebuilt_ids
            and [
                result.document.metadata.get("retrieval_sources")
                for result in hybrid_response.results
            ] == [["dense", "sparse"], ["dense", "sparse"]]
            and all(
                result.document.metadata.get("file_id") == PROBE_FILE_ID
                and result.document.metadata.get("user_id") == PROBE_USER_ID
                for result in hybrid_response.results
            )
            and [
                result.document.metadata.get("retrieval_sources")
                for result in dense_response.results
            ] == [["dense"], ["dense"]]
            and [
                result.document.metadata.get("retrieval_sources")
                for result in sparse_response.results
            ] == [["sparse"], ["sparse"]]
            and all(
                record.document.metadata.get("parent_id")
                for record in records
            )
            and cross_user_count == 0
            and rollback_count_before_delete == len(rollback_ids)
            and other_count_before_delete == len(other_ids)
            and deleted_count == 0
            and rollback_count_after_delete == 0
            and other_count_after_delete == len(other_ids)
        )
        return {
            "ok": ok,
            "collection": PROBE_COLLECTION,
            "fields": sorted(fields),
            "indexes": sorted(indexes),
            "rebuilt_ids": rebuilt_ids,
            "hybrid_result_ids": [
                result.document.metadata.get("child_id")
                for result in hybrid_response.results
            ],
            "dense_result_count": len(dense_response.results),
            "sparse_result_count": len(sparse_response.results),
            "cross_user_count": cross_user_count,
            "rollback_count_before_delete": rollback_count_before_delete,
            "deleted_count": deleted_count,
            "rollback_count_after_delete": rollback_count_after_delete,
            "other_user_count": other_count_after_delete,
        }
    finally:
        for collection_name in (
            PROBE_COLLECTION,
            ROLLBACK_COLLECTION,
            OTHER_COLLECTION,
        ):
            if client.has_collection(collection_name=collection_name):
                client.drop_collection(collection_name=collection_name)
        client.close()


def main() -> int:
    """运行 probe 并输出不含原始企业内容的 JSON 摘要。"""
    result = run_probe()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""T-134 Milvus filtered ANN、隔离、排序与跨 client 可见性 probe。"""

from __future__ import annotations

import argparse
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
from app.services.vectors.milvus_vector_store import MilvusVectorStore


PROBE_USER_ID = 900_134
OTHER_USER_ID = 900_135
PROBE_PREFIX = "firstrag_t134_probe_u900134_"
OTHER_PREFIX = "firstrag_t134_probe_u900135_"
PROBE_COLLECTION = f"{PROBE_PREFIX}identity"
OTHER_COLLECTION = f"{OTHER_PREFIX}identity"
PROBE_DIMENSIONS = 3
OTHER_DIMENSIONS = 4


class ProbeEmbeddings(Embeddings):
    """按 probe 正文生成可复现且排序已知的三维向量。"""

    def __init__(self, dimensions: int = PROBE_DIMENSIONS) -> None:
        """保存当前 probe collection 的固定向量维度。"""
        self.dimensions = dimensions

    def _pad(self, vector: list[float]) -> list[float]:
        """把排序基线向量补齐到目标 identity 的维度。"""
        return [*vector, *([0.0] * (self.dimensions - len(vector)))]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """把四种 probe 正文映射为固定 COSINE vectors。"""
        vectors = {
            "closest": [1.0, 0.0, 0.0],
            "second": [0.8, 0.6, 0.0],
            "third": [0.0, 1.0, 0.0],
            "other-user": [1.0, 0.0, 0.0],
        }
        return [self._pad(vectors[text]) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        """返回与 closest chunk 一致的 query vector。"""
        del text
        return self._pad([1.0, 0.0, 0.0])


def _client() -> Any:
    """创建使用当前 Compose 配置的独立 authenticated client。"""
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
    user_id: int,
    writable: bool,
) -> MilvusVectorStore:
    """构造只绑定一个 probe 用户 collection identity 的 adapter。"""
    is_primary_user = user_id == PROBE_USER_ID
    dimensions = PROBE_DIMENSIONS if is_primary_user else OTHER_DIMENSIONS
    return MilvusVectorStore(
        client=client,
        collection_name=(
            PROBE_COLLECTION if is_primary_user else OTHER_COLLECTION
        ),
        user_collection_prefix=(
            PROBE_PREFIX if is_primary_user else OTHER_PREFIX
        ),
        embedding_model=ProbeEmbeddings(dimensions) if writable else None,
        dimensions=dimensions,
        timeout_seconds=MILVUS_TIMEOUT_SECONDS,
        consistency_level=MILVUS_CONSISTENCY_LEVEL,
    )


def _document(
    *,
    user_id: int,
    file_id: str,
    chunk_index: int,
    content: str,
) -> Document:
    """创建满足生产 stable ID 与隔离字段契约的 probe 文档。"""
    return Document(
        page_content=content,
        metadata={
            "user_id": user_id,
            "file_id": file_id,
            "chunk_index": chunk_index,
            "index_version": 1,
            "probe": "T-134",
        },
    )


def _chunk_id(document: Document) -> str:
    """按生产 stable chunk ID 契约生成 probe ID。"""
    metadata = document.metadata
    return (
        f"{metadata['user_id']}:{metadata['file_id']}:"
        f"v{metadata['index_version']}:{metadata['chunk_index']}"
    )


def _replace_file(
    store: MilvusVectorStore,
    *,
    user_id: int,
    file_id: str,
    documents: list[Document],
) -> None:
    """通过生产 adapter 写入一个 probe 文件。"""
    store.replace_file_vectors(
        user_id=user_id,
        file_id=file_id,
        documents=documents,
        ids=[_chunk_id(document) for document in documents],
    )


def write() -> dict[str, object]:
    """写入两个用户、三个文件的隔离检索 fixture。"""
    client = _client()
    try:
        primary_store = _store(
            client,
            user_id=PROBE_USER_ID,
            writable=True,
        )
        file_a_documents = [
            _document(
                user_id=PROBE_USER_ID,
                file_id="file-a",
                chunk_index=0,
                content="closest",
            ),
            _document(
                user_id=PROBE_USER_ID,
                file_id="file-a",
                chunk_index=1,
                content="second",
            ),
        ]
        _replace_file(
            primary_store,
            user_id=PROBE_USER_ID,
            file_id="file-a",
            documents=file_a_documents,
        )
        _replace_file(
            primary_store,
            user_id=PROBE_USER_ID,
            file_id="file-b",
            documents=[_document(
                user_id=PROBE_USER_ID,
                file_id="file-b",
                chunk_index=0,
                content="third",
            )],
        )
        other_store = _store(
            client,
            user_id=OTHER_USER_ID,
            writable=True,
        )
        _replace_file(
            other_store,
            user_id=OTHER_USER_ID,
            file_id="file-a",
            documents=[_document(
                user_id=OTHER_USER_ID,
                file_id="file-a",
                chunk_index=0,
                content="other-user",
            )],
        )
        return {
            "phase": "write",
            "collections": [PROBE_COLLECTION, OTHER_COLLECTION],
            "primary_count": primary_store.count_vectors(
                user_id=PROBE_USER_ID,
            ),
            "other_count": other_store.count_vectors(user_id=OTHER_USER_ID),
            "dimensions": [PROBE_DIMENSIONS, OTHER_DIMENSIONS],
            "ok": True,
        }
    finally:
        client.close()


def search() -> dict[str, object]:
    """用新 client 验证用户、单/多文件范围和 distance 排序。"""
    client = _client()
    try:
        query_embedding = ProbeEmbeddings(PROBE_DIMENSIONS).embed_query("probe")
        primary_store = _store(
            client,
            user_id=PROBE_USER_ID,
            writable=False,
        )
        all_results = primary_store.search_vectors(
            query_embedding=query_embedding,
            user_id=PROBE_USER_ID,
            file_ids=None,
            k=10,
        ).results
        single_file_results = primary_store.search_vectors(
            query_embedding=query_embedding,
            user_id=PROBE_USER_ID,
            file_ids=["file-b"],
            k=10,
        ).results
        multi_file_results = primary_store.search_vectors(
            query_embedding=query_embedding,
            user_id=PROBE_USER_ID,
            file_ids=["file-b", "file-a", "file-a"],
            k=10,
        ).results
        other_query_embedding = ProbeEmbeddings(OTHER_DIMENSIONS).embed_query(
            "probe",
        )
        other_results = _store(
            client,
            user_id=OTHER_USER_ID,
            writable=False,
        ).search_vectors(
            query_embedding=other_query_embedding,
            user_id=OTHER_USER_ID,
            file_ids=["file-a"],
            k=10,
        ).results
        all_contents = [
            result.document.page_content
            for result in all_results
        ]
        distances = [round(result.distance, 6) for result in all_results]
        ok = (
            all_contents == ["closest", "second", "third"]
            and distances == [0.0, 0.2, 1.0]
            and [
                result.document.page_content
                for result in single_file_results
            ] == ["third"]
            and [
                result.document.page_content
                for result in multi_file_results
            ] == all_contents
            and [
                result.document.page_content
                for result in other_results
            ] == ["other-user"]
            and all(
                result.document.metadata["user_id"] == PROBE_USER_ID
                for result in all_results
            )
        )
        return {
            "phase": "search",
            "contents": all_contents,
            "distances": distances,
            "single_file_count": len(single_file_results),
            "multi_file_count": len(multi_file_results),
            "other_user_count": len(other_results),
            "dimensions": [PROBE_DIMENSIONS, OTHER_DIMENSIONS],
            "ok": ok,
        }
    finally:
        client.close()


def cleanup() -> dict[str, object]:
    """删除两个 exact-name probe collections，不触碰其它数据或 volume。"""
    client = _client()
    try:
        for collection_name in (PROBE_COLLECTION, OTHER_COLLECTION):
            if client.has_collection(collection_name=collection_name):
                client.drop_collection(collection_name=collection_name)
        return {
            "phase": "cleanup",
            "collections": [PROBE_COLLECTION, OTHER_COLLECTION],
            "ok": True,
        }
    finally:
        client.close()


def main() -> int:
    """执行一个可跨 backend/worker process 组合的 acceptance phase。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("write", "search", "cleanup"))
    args = parser.parse_args()
    actions = {
        "write": write,
        "search": search,
        "cleanup": cleanup,
    }
    result = actions[args.phase]()
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""T-133 Milvus 写入、重建、跨 client 可见性与删除验收 probe。"""

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


PROBE_USER_ID = 900_133
PROBE_FILE_ID = "00000000-0000-0000-0000-000000000133"
PROBE_PREFIX = "firstrag_t133_probe_u900133_"
PROBE_COLLECTION = f"{PROBE_PREFIX}identity"
PROBE_DIMENSIONS = 3


class ProbeEmbeddings(Embeddings):
    """生成可复现且非零的三维 acceptance vectors。"""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """按输入顺序生成彼此可区分的向量。"""
        return [
            [1.0, float(index + 1) / 10.0, 0.25]
            for index, _text in enumerate(texts)
        ]

    def embed_query(self, text: str) -> list[float]:
        """返回与首个 probe chunk 一致的 query vector。"""
        del text
        return [1.0, 0.1, 0.25]


def _client() -> Any:
    """创建使用当前 Compose 配置的独立 authenticated client。"""
    from pymilvus import MilvusClient

    return MilvusClient(
        uri=MILVUS_URI,
        token=MILVUS_TOKEN,
        db_name=MILVUS_DATABASE,
        timeout=MILVUS_TIMEOUT_SECONDS,
    )


def _store(client: Any, *, writable: bool) -> MilvusVectorStore:
    """构造只绑定专用 probe collection/prefix 的 adapter。"""
    return MilvusVectorStore(
        client=client,
        collection_name=PROBE_COLLECTION,
        user_collection_prefix=PROBE_PREFIX,
        embedding_model=ProbeEmbeddings() if writable else None,
        dimensions=PROBE_DIMENSIONS,
        timeout_seconds=MILVUS_TIMEOUT_SECONDS,
        consistency_level=MILVUS_CONSISTENCY_LEVEL,
    )


def _documents(version: int) -> list[Document]:
    """为不同索引版本生成确定性文档集合。"""
    chunk_count = 2 if version == 1 else 1
    return [
        Document(
            page_content=f"T-133 probe version {version} chunk {chunk_index}",
            metadata={
                "user_id": PROBE_USER_ID,
                "file_id": PROBE_FILE_ID,
                "chunk_index": chunk_index,
                "index_version": version,
                "probe": True,
            },
        )
        for chunk_index in range(chunk_count)
    ]


def _chunk_ids(documents: list[Document]) -> list[str]:
    """按生产 stable chunk ID 契约生成 probe IDs。"""
    return [
        (
            f"{PROBE_USER_ID}:{PROBE_FILE_ID}:"
            f"v{document.metadata['index_version']}:"
            f"{document.metadata['chunk_index']}"
        )
        for document in documents
    ]


def write(version: int) -> dict[str, object]:
    """写入或重建专用文件，并由 adapter 执行写后 ANN 门禁。"""
    client = _client()
    try:
        documents = _documents(version)
        ids = _chunk_ids(documents)
        _store(client, writable=True).replace_file_vectors(
            user_id=PROBE_USER_ID,
            file_id=PROBE_FILE_ID,
            documents=documents,
            ids=ids,
        )
        return {
            "phase": "write",
            "version": version,
            "collection": PROBE_COLLECTION,
            "ids": ids,
            "ok": True,
        }
    finally:
        client.close()


def verify(version: int) -> dict[str, object]:
    """通过新 client 验证当前版本的 ID、正文、metadata 和数量。"""
    client = _client()
    try:
        documents = _documents(version)
        expected_ids = _chunk_ids(documents)
        records = _store(client, writable=False).list_file_vectors(
            user_id=PROBE_USER_ID,
            file_id=PROBE_FILE_ID,
        )
        actual_ids = [record.id for record in records]
        actual_versions = {
            int(record.document.metadata["index_version"])
            for record in records
        }
        ok = (
            actual_ids == sorted(expected_ids)
            and actual_versions == {version}
            and all(record.document.metadata.get("probe") is True for record in records)
        )
        return {
            "phase": "verify",
            "version": version,
            "collection": PROBE_COLLECTION,
            "ids": actual_ids,
            "ok": ok,
        }
    finally:
        client.close()


def delete() -> dict[str, object]:
    """通过 credential-free adapter 路径删除专用文件 entities。"""
    client = _client()
    try:
        store = _store(client, writable=False)
        store.delete_file_vectors(
            user_id=PROBE_USER_ID,
            file_id=PROBE_FILE_ID,
        )
        ok = store.count_vectors(
            user_id=PROBE_USER_ID,
            file_id=PROBE_FILE_ID,
        ) == 0
        return {
            "phase": "delete",
            "collection": PROBE_COLLECTION,
            "ok": ok,
        }
    finally:
        client.close()


def cleanup() -> dict[str, object]:
    """删除 exact-name probe collection，不触碰应用 collection 或 volume。"""
    client = _client()
    try:
        if client.has_collection(collection_name=PROBE_COLLECTION):
            client.drop_collection(collection_name=PROBE_COLLECTION)
        return {
            "phase": "cleanup",
            "collection": PROBE_COLLECTION,
            "ok": True,
        }
    finally:
        client.close()


def main() -> int:
    """执行一个可跨 backend/worker process 组合的 acceptance phase。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("write", "verify", "delete", "cleanup"))
    parser.add_argument("--version", type=int, choices=(1, 2), default=1)
    args = parser.parse_args()
    actions = {
        "write": lambda: write(args.version),
        "verify": lambda: verify(args.version),
        "delete": delete,
        "cleanup": cleanup,
    }
    result = actions[args.phase]()
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

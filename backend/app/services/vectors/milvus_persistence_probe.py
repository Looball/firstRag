"""Milvus Standalone restart persistence acceptance probe。"""

from __future__ import annotations

import argparse
import json
from typing import Any

from app.core.config import (
    MILVUS_COLLECTION_PREFIX,
    MILVUS_DATABASE,
    MILVUS_TIMEOUT_SECONDS,
    MILVUS_TOKEN,
    MILVUS_URI,
)


PROBE_SUFFIX = "t132_persistence_probe"
PROBE_ID = 132


def _client() -> Any:
    """创建使用当前配置的 authenticated PyMilvus client。"""
    from pymilvus import MilvusClient

    return MilvusClient(
        uri=MILVUS_URI,
        token=MILVUS_TOKEN,
        db_name=MILVUS_DATABASE,
        timeout=MILVUS_TIMEOUT_SECONDS,
    )


def _collection_name() -> str:
    """返回仅供 T-132 acceptance 使用的确定性 collection 名。"""
    return f"{MILVUS_COLLECTION_PREFIX}_{PROBE_SUFFIX}"


def seed() -> dict[str, object]:
    """创建隔离 probe collection 并写入重启标记。"""
    client = _client()
    collection_name = _collection_name()
    try:
        if client.has_collection(collection_name=collection_name):
            client.drop_collection(collection_name=collection_name)
        client.create_collection(
            collection_name=collection_name,
            dimension=2,
            primary_field_name="id",
            id_type="int",
            vector_field_name="vector",
            metric_type="COSINE",
        )
        client.insert(
            collection_name=collection_name,
            data=[{"id": PROBE_ID, "vector": [1.0, 0.0]}],
        )
        client.flush(collection_name=collection_name)
        return {"phase": "seed", "collection": collection_name, "ok": True}
    finally:
        client.close()


def verify() -> dict[str, object]:
    """在 Milvus 重启后读取标记，证明 metadata/object/WAL 持久化。"""
    client = _client()
    collection_name = _collection_name()
    try:
        rows = client.get(
            collection_name=collection_name,
            ids=[PROBE_ID],
            output_fields=["id"],
        )
        ok = any(row.get("id") == PROBE_ID for row in rows)
        return {"phase": "verify", "collection": collection_name, "ok": ok}
    finally:
        client.close()


def cleanup() -> dict[str, object]:
    """删除 exact-name probe collection，不影响任何应用 collection。"""
    client = _client()
    collection_name = _collection_name()
    try:
        if client.has_collection(collection_name=collection_name):
            client.drop_collection(collection_name=collection_name)
        return {"phase": "cleanup", "collection": collection_name, "ok": True}
    finally:
        client.close()


def main() -> int:
    """执行 seed、verify 或 cleanup acceptance phase。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("seed", "verify", "cleanup"))
    args = parser.parse_args()
    result = {"seed": seed, "verify": verify, "cleanup": cleanup}[args.phase]()
    print(json.dumps(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

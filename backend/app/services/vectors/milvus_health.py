"""Milvus candidate runtime 的 authenticated health probe。"""

from __future__ import annotations

import json
from typing import Any, Callable

from app.core.config import (
    MILVUS_COLLECTION_PREFIX,
    MILVUS_DATABASE,
    MILVUS_TIMEOUT_SECONDS,
    MILVUS_TOKEN,
    MILVUS_URI,
)
from app.services.vectors.vector_store import VectorStoreHealth


MilvusClientFactory = Callable[..., Any]


def _load_milvus_client() -> MilvusClientFactory:
    """延迟加载 PyMilvus，避免 Chroma 默认链路承担额外 import 开销。"""
    from pymilvus import MilvusClient

    return MilvusClient


def check_milvus_health(
    *,
    uri: str = MILVUS_URI,
    token: str = MILVUS_TOKEN,
    database: str = MILVUS_DATABASE,
    collection_prefix: str = MILVUS_COLLECTION_PREFIX,
    timeout_seconds: float = MILVUS_TIMEOUT_SECONDS,
    client_factory: MilvusClientFactory | None = None,
) -> VectorStoreHealth:
    """使用认证 client 完成 list-collections round-trip，不泄露连接凭据。"""
    if not uri or not token or not database:
        return VectorStoreHealth(
            healthy=False,
            provider="milvus",
            collection_name=collection_prefix,
            detail="Milvus client configuration is incomplete.",
        )

    factory = client_factory or _load_milvus_client()
    client = None
    try:
        client = factory(
            uri=uri,
            token=token,
            db_name=database,
            timeout=timeout_seconds,
        )
        client.list_collections(timeout=timeout_seconds)
    except Exception:  # noqa: BLE001 - health probe 必须屏蔽 provider 细节和凭据
        return VectorStoreHealth(
            healthy=False,
            provider="milvus",
            collection_name=collection_prefix,
            detail="Authenticated Milvus round-trip failed.",
        )
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:  # noqa: BLE001 - close 失败不覆盖主要健康结果
                pass

    return VectorStoreHealth(
        healthy=True,
        provider="milvus",
        collection_name=collection_prefix,
        detail="Authenticated Milvus round-trip succeeded.",
    )


def check_milvus_authentication_enforced(
    *,
    uri: str = MILVUS_URI,
    database: str = MILVUS_DATABASE,
    timeout_seconds: float = MILVUS_TIMEOUT_SECONDS,
    client_factory: MilvusClientFactory | None = None,
) -> VectorStoreHealth:
    """确认无 token client 被拒绝，防止仅检查正向认证造成假阳性。"""
    if not uri or not database:
        return VectorStoreHealth(
            healthy=False,
            provider="milvus",
            collection_name=None,
            detail="Milvus client configuration is incomplete.",
        )

    factory = client_factory or _load_milvus_client()
    client = None
    try:
        client = factory(
            uri=uri,
            db_name=database,
            timeout=timeout_seconds,
        )
        client.list_collections(timeout=timeout_seconds)
    except Exception:  # noqa: BLE001 - 被拒绝即证明 authentication 生效
        return VectorStoreHealth(
            healthy=True,
            provider="milvus",
            collection_name=None,
            detail="Unauthenticated Milvus client was rejected.",
        )
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:  # noqa: BLE001 - close 失败不影响认证判定
                pass

    return VectorStoreHealth(
        healthy=False,
        provider="milvus",
        collection_name=None,
        detail="Milvus accepted an unauthenticated client.",
    )


def main() -> int:
    """供 Compose backend/worker image 执行安全的 authenticated probe。"""
    authentication = check_milvus_authentication_enforced()
    health = check_milvus_health()
    print(json.dumps({
        "healthy": authentication.healthy and health.healthy,
        "provider": health.provider,
        "collection_prefix": health.collection_name,
        "authentication_enforced": authentication.healthy,
        "detail": health.detail,
    }))
    return 0 if authentication.healthy and health.healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())

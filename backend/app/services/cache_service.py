"""Redis JSON 缓存适配层。

本模块把业务缓存和 Redis client 隔离开：业务模块只关心 hit/miss、
fallback reason 和 JSON value，Redis 配置错误或运行时故障都不会直接
打断 RAG 主链路。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from math import ceil
from threading import RLock
from time import monotonic
from typing import Any
from urllib.parse import quote

from app.services.redis_service import (
    RedisServiceError,
    get_redis_client,
    sanitize_redis_error_message,
)


logger = logging.getLogger(__name__)

CACHE_KEY_PREFIX = "firstrag"
REDIS_CACHE_CIRCUIT_TTL_SECONDS = 5.0

_CIRCUIT_LOCK = RLock()
_UNAVAILABLE_UNTIL = 0.0
_UNAVAILABLE_REASON: str | None = None


@dataclass(frozen=True)
class CacheBackendResult:
    """一次缓存后端访问的安全结果。"""

    hit: bool
    value: Any | None = None
    backend: str = "redis"
    available: bool = True
    fallback_reason: str | None = None


def reset_cache_adapter_state() -> None:
    """重置 Redis cache adapter 的熔断状态，主要用于测试隔离。"""
    global _UNAVAILABLE_UNTIL, _UNAVAILABLE_REASON
    with _CIRCUIT_LOCK:
        _UNAVAILABLE_UNTIL = 0.0
        _UNAVAILABLE_REASON = None


def _encode_cache_key_part(value: object) -> str:
    """把 key 片段编码为 Redis key 中稳定、安全的字符串。"""
    return quote(str(value), safe="")


def build_cache_key(namespace: str, *parts: object) -> str:
    """构造带统一前缀的 Redis cache key。"""
    encoded_parts = [
        CACHE_KEY_PREFIX,
        _encode_cache_key_part(namespace),
        *[
            _encode_cache_key_part(part)
            for part in parts
        ],
    ]
    return ":".join(encoded_parts)


def build_cache_prefix(namespace: str, *parts: object) -> str:
    """构造用于 scan/delete 的 Redis cache key 前缀。"""
    return f"{build_cache_key(namespace, *parts)}:"


def _read_open_circuit() -> CacheBackendResult | None:
    """读取 Redis cache adapter 的短熔断状态。"""
    with _CIRCUIT_LOCK:
        if _UNAVAILABLE_UNTIL > monotonic():
            return CacheBackendResult(
                hit=False,
                available=False,
                fallback_reason=_UNAVAILABLE_REASON,
            )
    return None


def _mark_redis_unavailable(exc: Exception) -> CacheBackendResult:
    """记录 Redis 短熔断状态，并返回可用于 fallback 的结果。"""
    reason = sanitize_redis_error_message(str(exc))
    global _UNAVAILABLE_UNTIL, _UNAVAILABLE_REASON
    with _CIRCUIT_LOCK:
        _UNAVAILABLE_UNTIL = monotonic() + REDIS_CACHE_CIRCUIT_TTL_SECONDS
        _UNAVAILABLE_REASON = reason

    logger.debug("Redis cache 暂不可用，业务缓存将降级：%s", reason)
    return CacheBackendResult(
        hit=False,
        available=False,
        fallback_reason=reason,
    )


def get_json_cache(key: str) -> CacheBackendResult:
    """从 Redis 读取 JSON value；失败时返回 fallback 信息而不是抛错。"""
    open_circuit = _read_open_circuit()
    if open_circuit is not None:
        return open_circuit

    try:
        raw_value = get_redis_client().get(key)
    except RedisServiceError as exc:
        return _mark_redis_unavailable(exc)
    except Exception as exc:  # noqa: BLE001 - cache 层必须兜底 Redis 异常
        return _mark_redis_unavailable(exc)

    if raw_value is None:
        return CacheBackendResult(hit=False)

    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        logger.debug("Redis cache value JSON 解析失败，按 miss 处理：%s", exc)
        delete_cache_key(key)
        return CacheBackendResult(
            hit=False,
            fallback_reason="redis_cache_decode_failed",
        )

    return CacheBackendResult(hit=True, value=value)


def set_json_cache(
    key: str,
    value: Any,
    ttl_seconds: float,
) -> CacheBackendResult:
    """把可 JSON 序列化的 value 写入 Redis，写入失败时返回 fallback 信息。"""
    if ttl_seconds <= 0:
        return delete_cache_key(key)

    open_circuit = _read_open_circuit()
    if open_circuit is not None:
        return open_circuit

    try:
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        get_redis_client().set(
            key,
            payload,
            ex=max(1, int(ceil(ttl_seconds))),
        )
    except (TypeError, ValueError) as exc:
        logger.debug("Redis cache value 不能序列化，跳过写入：%s", exc)
        return CacheBackendResult(
            hit=False,
            fallback_reason="redis_cache_encode_failed",
        )
    except RedisServiceError as exc:
        return _mark_redis_unavailable(exc)
    except Exception as exc:  # noqa: BLE001 - cache 层必须兜底 Redis 异常
        return _mark_redis_unavailable(exc)

    return CacheBackendResult(hit=False)


def delete_cache_key(key: str) -> CacheBackendResult:
    """删除单个 Redis cache key；失败时返回 fallback 信息。"""
    open_circuit = _read_open_circuit()
    if open_circuit is not None:
        return open_circuit

    try:
        get_redis_client().delete(key)
    except RedisServiceError as exc:
        return _mark_redis_unavailable(exc)
    except Exception as exc:  # noqa: BLE001 - cache 层必须兜底 Redis 异常
        return _mark_redis_unavailable(exc)

    return CacheBackendResult(hit=False)


def delete_cache_prefix(prefix: str, batch_size: int = 200) -> CacheBackendResult:
    """按前缀扫描并删除 Redis cache key。"""
    open_circuit = _read_open_circuit()
    if open_circuit is not None:
        return open_circuit

    try:
        client = get_redis_client()
        batch: list[str] = []
        for key in client.scan_iter(match=f"{prefix}*", count=batch_size):
            batch.append(key)
            if len(batch) >= batch_size:
                client.delete(*batch)
                batch = []
        if batch:
            client.delete(*batch)
    except RedisServiceError as exc:
        return _mark_redis_unavailable(exc)
    except Exception as exc:  # noqa: BLE001 - cache 层必须兜底 Redis 异常
        return _mark_redis_unavailable(exc)

    return CacheBackendResult(hit=False)

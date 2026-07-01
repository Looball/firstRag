"""轻量级进程内请求限流工具。"""

from __future__ import annotations

from collections import deque
from collections.abc import Hashable
from math import ceil
from threading import RLock
from time import monotonic

from fastapi import HTTPException, Request


class RateLimitExceededError(Exception):
    """表示当前限流桶已经达到窗口内请求上限。"""

    def __init__(
        self,
        retry_after_seconds: int,
        limit: int,
        window_seconds: int,
    ) -> None:
        """保存客户端可以重试的时间和限流配置。"""
        super().__init__("rate limit exceeded")
        self.retry_after_seconds = retry_after_seconds
        self.limit = limit
        self.window_seconds = window_seconds


_RATE_LIMIT_BUCKETS: dict[str, deque[float]] = {}
_RATE_LIMIT_LOCK = RLock()


def get_client_host(request: Request) -> str:
    """读取请求来源主机，缺失时返回稳定占位值。"""
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def build_rate_limit_identifier(
    request: Request,
    *parts: Hashable,
) -> str:
    """构造包含客户端主机和业务维度的限流键。"""
    key_parts = [get_client_host(request), *parts]
    return ":".join(str(part).strip().lower() for part in key_parts)


def _prune_bucket(
    bucket: deque[float],
    now: float,
    window_seconds: int,
) -> None:
    """移除限流窗口之外的旧请求时间戳。"""
    cutoff = now - window_seconds
    while bucket and bucket[0] <= cutoff:
        bucket.popleft()


def _check_rate_limit(
    scope: str,
    identifier: str,
    limit: int,
    window_seconds: int,
    *,
    consume: bool,
) -> None:
    """检查限流桶，并在需要时消耗一次请求额度。"""
    if limit <= 0 or window_seconds <= 0:
        return

    key = f"{scope}:{identifier}"
    now = monotonic()

    with _RATE_LIMIT_LOCK:
        bucket = _RATE_LIMIT_BUCKETS.setdefault(key, deque())
        _prune_bucket(bucket, now, window_seconds)

        if len(bucket) >= limit:
            retry_after = max(1, ceil(bucket[0] + window_seconds - now))
            raise RateLimitExceededError(
                retry_after_seconds=retry_after,
                limit=limit,
                window_seconds=window_seconds,
            )

        if consume:
            bucket.append(now)


def assert_rate_limit_available(
    scope: str,
    identifier: str,
    limit: int,
    window_seconds: int,
) -> None:
    """只检查限流额度，不记录本次请求。"""
    _check_rate_limit(
        scope,
        identifier,
        limit,
        window_seconds,
        consume=False,
    )


def consume_rate_limit(
    scope: str,
    identifier: str,
    limit: int,
    window_seconds: int,
) -> None:
    """检查并记录一次请求。"""
    _check_rate_limit(
        scope,
        identifier,
        limit,
        window_seconds,
        consume=True,
    )


def clear_rate_limit(scope: str, identifier: str) -> None:
    """清空指定限流桶，用于登录成功后清除失败计数。"""
    with _RATE_LIMIT_LOCK:
        _RATE_LIMIT_BUCKETS.pop(f"{scope}:{identifier}", None)


def reset_rate_limits() -> None:
    """清空全部限流状态，主要供测试隔离使用。"""
    with _RATE_LIMIT_LOCK:
        _RATE_LIMIT_BUCKETS.clear()


def enforce_rate_limit(
    scope: str,
    identifier: str,
    limit: int,
    window_seconds: int,
    detail: str,
) -> None:
    """在 route 层执行限流，超限时返回带 Retry-After 的 429。"""
    try:
        consume_rate_limit(scope, identifier, limit, window_seconds)
    except RateLimitExceededError as exc:
        raise HTTPException(
            status_code=429,
            detail=detail,
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc

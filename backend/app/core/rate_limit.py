"""Redis 优先的请求限流工具。"""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Hashable
from hashlib import sha256
from math import ceil
from threading import RLock
from time import monotonic, time_ns
from urllib.parse import quote

from fastapi import HTTPException, Request

from app.core import config
from app.core.observability import log_exception_event
from app.services.redis_service import RedisServiceError, get_redis_client


logger = logging.getLogger(__name__)

RATE_LIMIT_KEY_PREFIX = "firstrag:rate_limit"
REDIS_RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local window_ms = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local consume = tonumber(ARGV[3])
local member = ARGV[4]

local redis_time = redis.call("TIME")
local now_ms = redis_time[1] * 1000 + math.floor(redis_time[2] / 1000)
local cutoff_ms = now_ms - window_ms

redis.call("ZREMRANGEBYSCORE", key, "-inf", cutoff_ms)

local count = redis.call("ZCARD", key)
if count >= limit then
    local oldest = redis.call("ZRANGE", key, 0, 0, "WITHSCORES")
    local retry_after_ms = window_ms
    if oldest[2] ~= nil then
        retry_after_ms = math.max(1, oldest[2] + window_ms - now_ms)
    end
    redis.call("PEXPIRE", key, window_ms)
    return {0, math.ceil(retry_after_ms / 1000), count}
end

if consume == 1 then
    redis.call("ZADD", key, now_ms, member)
    count = count + 1
    redis.call("PEXPIRE", key, window_ms)
elseif count > 0 then
    redis.call("PEXPIRE", key, window_ms)
end

return {1, 0, count}
"""


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


def _check_memory_rate_limit(
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


def _normalize_backend() -> str:
    """读取当前限流后端，非法值回退到 Redis。"""
    backend = config.RATE_LIMIT_BACKEND.strip().lower()
    if backend in {"memory", "in_memory", "local"}:
        return "memory"
    return "redis"


def _normalize_redis_failure_mode() -> str:
    """读取 Redis 限流故障策略，非法值按 fail-closed 处理。"""
    mode = config.RATE_LIMIT_REDIS_FAILURE_MODE.strip().lower()
    if mode in {"fail_open", "fail-open", "open", "memory"}:
        return "fail_open"
    return "fail_closed"


def _build_redis_rate_limit_key(scope: str, identifier: str) -> str:
    """构造不暴露 username/IP/user_id 明文的 Redis rate limit key。"""
    encoded_scope = quote(scope.strip().lower(), safe="")
    identifier_hash = sha256(identifier.encode("utf-8")).hexdigest()
    return f"{RATE_LIMIT_KEY_PREFIX}:{encoded_scope}:{identifier_hash}"


def _build_redis_rate_limit_prefix(scope: str | None = None) -> str:
    """构造 Redis rate limit key 前缀。"""
    if scope is None:
        return f"{RATE_LIMIT_KEY_PREFIX}:"
    return f"{RATE_LIMIT_KEY_PREFIX}:{quote(scope.strip().lower(), safe='')}:"


def _run_redis_rate_limit(
    scope: str,
    identifier: str,
    limit: int,
    window_seconds: int,
    *,
    consume: bool,
) -> None:
    """在 Redis 中以原子 Lua 脚本执行 sliding-window 限流。"""
    redis_key = _build_redis_rate_limit_key(scope, identifier)
    result = get_redis_client().eval(
        REDIS_RATE_LIMIT_SCRIPT,
        1,
        redis_key,
        int(window_seconds * 1000),
        int(limit),
        1 if consume else 0,
        f"{time_ns()}",
    )
    if not isinstance(result, (list, tuple)) or len(result) < 2:
        raise RedisServiceError("Redis 限流脚本返回格式异常。")

    allowed = bool(int(result[0]))
    retry_after_seconds = max(1, int(result[1] or 0))
    if not allowed:
        raise RateLimitExceededError(
            retry_after_seconds=retry_after_seconds,
            limit=limit,
            window_seconds=window_seconds,
        )


def _handle_redis_rate_limit_failure(
    exc: Exception,
    scope: str,
    identifier: str,
    limit: int,
    window_seconds: int,
    *,
    consume: bool,
) -> None:
    """按配置处理 Redis 限流故障。"""
    failure_mode = _normalize_redis_failure_mode()
    log_exception_event(
        logger,
        "rate_limit_redis_failed",
        exc,
        level=logging.WARNING,
        default_source="redis",
        scope=scope,
        failure_mode=failure_mode,
    )

    if failure_mode == "fail_open":
        _check_memory_rate_limit(
            scope,
            identifier,
            limit,
            window_seconds,
            consume=consume,
        )
        return

    retry_after_seconds = max(1, min(window_seconds, 60))
    raise RateLimitExceededError(
        retry_after_seconds=retry_after_seconds,
        limit=limit,
        window_seconds=window_seconds,
    ) from exc


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

    if _normalize_backend() == "memory":
        _check_memory_rate_limit(
            scope,
            identifier,
            limit,
            window_seconds,
            consume=consume,
        )
        return

    try:
        _run_redis_rate_limit(
            scope,
            identifier,
            limit,
            window_seconds,
            consume=consume,
        )
    except RateLimitExceededError:
        raise
    except Exception as exc:  # noqa: BLE001 - 限流故障按配置 fail-open/closed
        _handle_redis_rate_limit_failure(
            exc,
            scope,
            identifier,
            limit,
            window_seconds,
            consume=consume,
        )


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

    if _normalize_backend() != "redis":
        return

    try:
        get_redis_client().delete(_build_redis_rate_limit_key(scope, identifier))
    except Exception as exc:  # noqa: BLE001 - 登录成功后的清理只做 best effort
        log_exception_event(
            logger,
            "rate_limit_redis_clear_failed",
            exc,
            level=logging.WARNING,
            default_source="redis",
            scope=scope,
        )


def reset_rate_limits() -> None:
    """清空全部限流状态，主要供测试隔离使用。"""
    with _RATE_LIMIT_LOCK:
        _RATE_LIMIT_BUCKETS.clear()

    if _normalize_backend() != "redis":
        return

    try:
        client = get_redis_client()
        batch: list[str] = []
        for key in client.scan_iter(
            match=f"{_build_redis_rate_limit_prefix()}*",
            count=200,
        ):
            batch.append(key)
            if len(batch) >= 200:
                client.delete(*batch)
                batch = []
        if batch:
            client.delete(*batch)
    except Exception as exc:  # noqa: BLE001 - 测试隔离和本地清理不应中断进程
        log_exception_event(
            logger,
            "rate_limit_redis_reset_failed",
            exc,
            level=logging.WARNING,
            default_source="redis",
        )


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

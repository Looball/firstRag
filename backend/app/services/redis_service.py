"""Redis 基础设施连接、脱敏和健康检查工具。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from threading import RLock
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from app.core import config
from app.core.sensitive_data import sanitize_sensitive_text

try:
    from redis import Redis
except ImportError:  # pragma: no cover - 依赖缺失路径由单元测试覆盖行为
    Redis = None  # type: ignore[assignment]


class RedisServiceError(RuntimeError):
    """Redis 基础设施不可用或配置错误。"""


class RedisConfigurationError(RedisServiceError):
    """Redis 配置不完整或显式禁用。"""


class RedisDependencyError(RedisServiceError):
    """运行环境缺少 redis Python 依赖。"""


@dataclass(frozen=True)
class RedisHealth:
    """Redis 健康状态的安全序列化结构。"""

    enabled: bool
    configured: bool
    is_healthy: bool
    status: str
    error_source: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为 API 和日志可直接使用的 dict。"""
        return {
            key: value
            for key, value in asdict(self).items()
            if value is not None
        }


_CLIENT_LOCK = RLock()
_CLIENT: Any | None = None
_CLIENT_CACHE_KEY: tuple[str, float, float] | None = None


def sanitize_redis_url(redis_url: str) -> str:
    """返回不包含密码的 Redis URL 摘要。"""
    raw_url = redis_url.strip()
    if not raw_url:
        return ""

    try:
        parsed = urlsplit(raw_url)
    except ValueError:
        return "[已脱敏]"

    if not parsed.scheme or not parsed.netloc:
        return sanitize_sensitive_text(raw_url, [raw_url])

    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port is not None else ""
    auth = "[已脱敏]@" if parsed.username or parsed.password else ""
    netloc = f"{auth}{host}{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def sanitize_redis_error_message(message: str) -> str:
    """脱敏 Redis 异常文本，避免输出连接串或密码。"""
    return sanitize_sensitive_text(
        message,
        [
            config.REDIS_URL,
            sanitize_redis_url(config.REDIS_URL),
        ],
    )


def reset_redis_client_cache() -> None:
    """清空 Redis client 缓存，主要供测试隔离和配置热切换使用。"""
    global _CLIENT, _CLIENT_CACHE_KEY
    with _CLIENT_LOCK:
        _CLIENT = None
        _CLIENT_CACHE_KEY = None


def get_redis_client() -> Any:
    """按当前配置返回 Redis client，配置变化时自动重建。"""
    if not config.REDIS_ENABLED:
        raise RedisConfigurationError("Redis 未启用。")
    if not config.REDIS_URL:
        raise RedisConfigurationError("已启用 Redis，但未配置 REDIS_URL。")
    if Redis is None:
        raise RedisDependencyError("缺少 redis Python 依赖，请安装后端依赖。")

    cache_key = (
        config.REDIS_URL,
        config.REDIS_CONNECT_TIMEOUT_SECONDS,
        config.REDIS_COMMAND_TIMEOUT_SECONDS,
    )
    with _CLIENT_LOCK:
        global _CLIENT, _CLIENT_CACHE_KEY
        if _CLIENT is not None and _CLIENT_CACHE_KEY == cache_key:
            return _CLIENT

        _CLIENT = Redis.from_url(
            config.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=config.REDIS_CONNECT_TIMEOUT_SECONDS,
            socket_timeout=config.REDIS_COMMAND_TIMEOUT_SECONDS,
        )
        _CLIENT_CACHE_KEY = cache_key
        return _CLIENT


def check_redis_health() -> RedisHealth:
    """执行 Redis ping，返回不含连接串和密码的健康状态。"""
    configured = bool(config.REDIS_URL)
    if not config.REDIS_ENABLED:
        return RedisHealth(
            enabled=False,
            configured=configured,
            is_healthy=True,
            status="disabled",
        )

    try:
        client = get_redis_client()
        if client.ping() is not True:
            raise RedisServiceError("Redis ping 未返回 OK。")
    except RedisDependencyError as exc:
        return RedisHealth(
            enabled=True,
            configured=configured,
            is_healthy=False,
            status="dependency_missing",
            error_source="dependency",
            error_message=sanitize_redis_error_message(str(exc)),
        )
    except RedisConfigurationError as exc:
        return RedisHealth(
            enabled=True,
            configured=configured,
            is_healthy=False,
            status="misconfigured",
            error_source="config",
            error_message=sanitize_redis_error_message(str(exc)),
        )
    except Exception as exc:  # noqa: BLE001 - health check 要兜底依赖异常
        return RedisHealth(
            enabled=True,
            configured=configured,
            is_healthy=False,
            status="unavailable",
            error_source="redis",
            error_message=sanitize_redis_error_message(str(exc)),
        )

    return RedisHealth(
        enabled=True,
        configured=True,
        is_healthy=True,
        status="healthy",
    )

"""知识库检索设置的进程内轻量缓存。"""

from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import Any
from uuid import UUID


DEFAULT_RETRIEVAL_SETTINGS_CACHE_TTL_SECONDS = 60.0
MAX_RETRIEVAL_SETTINGS_CACHE_ENTRIES = 512

_CACHE_LOCK = RLock()
_CACHE: dict[tuple[int, str], "CachedRetrievalSettings"] = {}
_CACHE_DIAGNOSTICS: ContextVar[dict[str, Any] | None] = ContextVar(
    "retrieval_settings_cache_diagnostics",
    default=None,
)


@dataclass(frozen=True)
class CachedRetrievalSettings:
    """缓存值和过期信息。"""

    value: dict[str, Any]
    expires_at: float
    created_at: float


def reset_retrieval_settings_cache_diagnostics() -> None:
    """清理当前请求的 retrieval settings 缓存诊断。"""
    _CACHE_DIAGNOSTICS.set(None)


def get_retrieval_settings_cache_diagnostics() -> dict[str, Any] | None:
    """读取当前请求最近一次 retrieval settings 缓存诊断。"""
    diagnostics = _CACHE_DIAGNOSTICS.get()
    if diagnostics is None:
        return None
    return dict(diagnostics)


def set_cache_diagnostics(
    *,
    hit: bool,
    source: str,
    ttl_seconds: float,
) -> None:
    """记录本次检索设置读取是否命中缓存。"""
    _CACHE_DIAGNOSTICS.set({
        "retrieval_settings_cache_hit": hit,
        "retrieval_settings_source": source,
        "retrieval_settings_cache_ttl_seconds": ttl_seconds,
    })


def prune_expired_cache_entries(now: float) -> None:
    """清理过期缓存，并限制最大条目数。"""
    expired_keys = [
        key
        for key, cached in _CACHE.items()
        if cached.expires_at <= now
    ]
    for key in expired_keys:
        _CACHE.pop(key, None)

    if len(_CACHE) <= MAX_RETRIEVAL_SETTINGS_CACHE_ENTRIES:
        return

    overflow = len(_CACHE) - MAX_RETRIEVAL_SETTINGS_CACHE_ENTRIES
    oldest_keys = sorted(
        _CACHE,
        key=lambda key: _CACHE[key].created_at,
    )[:overflow]
    for key in oldest_keys:
        _CACHE.pop(key, None)


def get_cached_knowledge_base_retrieval_settings(
    *,
    user_id: int,
    knowledge_base_id: UUID,
    load_settings: Callable[[], dict[str, Any] | None],
    ttl_seconds: float = DEFAULT_RETRIEVAL_SETTINGS_CACHE_TTL_SECONDS,
) -> dict[str, Any] | None:
    """读取缓存中的检索设置，缺失或过期时重新加载。"""
    cache_key = (user_id, str(knowledge_base_id))
    now = monotonic()

    with _CACHE_LOCK:
        cached = _CACHE.get(cache_key)
        if cached is not None and cached.expires_at > now:
            set_cache_diagnostics(
                hit=True,
                source="cache",
                ttl_seconds=ttl_seconds,
            )
            return dict(cached.value)

    settings = load_settings()
    if settings is None:
        set_cache_diagnostics(
            hit=False,
            source="missing",
            ttl_seconds=ttl_seconds,
        )
        return None

    expires_at = now + max(0.0, ttl_seconds)
    settings_copy = dict(settings)

    with _CACHE_LOCK:
        prune_expired_cache_entries(now)
        _CACHE[cache_key] = CachedRetrievalSettings(
            value=settings_copy,
            expires_at=expires_at,
            created_at=now,
        )

    set_cache_diagnostics(
        hit=False,
        source="database",
        ttl_seconds=ttl_seconds,
    )
    return dict(settings_copy)


def invalidate_retrieval_settings_cache(
    user_id: int,
    knowledge_base_id: UUID | str | None = None,
) -> None:
    """失效单个用户的知识库检索设置缓存。"""
    with _CACHE_LOCK:
        if knowledge_base_id is None:
            for key in list(_CACHE):
                if key[0] == user_id:
                    _CACHE.pop(key, None)
            return

        _CACHE.pop((user_id, str(knowledge_base_id)), None)

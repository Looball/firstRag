"""知识库画像的 Redis 优先轻量缓存。

缓存内容只用于减少 RAG 前置阶段重复查询知识库文件列表。它不是权威
业务状态，丢失后可以随时从 PostgreSQL 重建。Redis 可用时作为多实例
共享缓存，Redis 不可用时回退到进程内短 TTL 缓存。
"""

from collections.abc import Callable, Sequence
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from threading import RLock
from time import monotonic
from typing import Any
from uuid import UUID

from app.repositories.knowledge_base_repository import (
    get_knowledge_base_ids_for_file,
)
from app.services import cache_service


DEFAULT_PROFILE_CACHE_TTL_SECONDS = 60.0
MAX_PROFILE_CACHE_ENTRIES = 256

_CACHE_LOCK = RLock()
_CACHE: dict[tuple[int, str], "CachedKnowledgeBaseContext"] = {}
_CACHE_DIAGNOSTICS: ContextVar[dict[str, Any] | None] = ContextVar(
    "knowledge_profile_cache_diagnostics",
    default=None,
)


@dataclass(frozen=True)
class KnowledgeBaseContext:
    """RAG 前置阶段需要的知识库轻量上下文。"""

    profile: str
    file_ids: list[str]
    indexed_count: int
    total_count: int


@dataclass(frozen=True)
class CachedKnowledgeBaseContext:
    """缓存值和过期信息。"""

    value: KnowledgeBaseContext
    expires_at: float
    created_at: float


def reset_knowledge_profile_cache_diagnostics() -> None:
    """清理当前请求的知识库画像缓存诊断。"""
    _CACHE_DIAGNOSTICS.set(None)


def get_knowledge_profile_cache_diagnostics() -> dict[str, Any] | None:
    """读取当前请求最近一次知识库画像缓存诊断。"""
    diagnostics = _CACHE_DIAGNOSTICS.get()
    if diagnostics is None:
        return None
    return dict(diagnostics)


def set_cache_diagnostics(
    *,
    hit: bool,
    context: KnowledgeBaseContext,
    source: str,
    ttl_seconds: float,
    fallback_reason: str | None = None,
) -> None:
    """记录本次画像读取是否命中缓存。"""
    existing = _CACHE_DIAGNOSTICS.get()
    if isinstance(existing, dict):
        previous_hit = bool(existing.get("knowledge_profile_cache_hit"))
        hit = previous_hit and hit
        if not previous_hit:
            source = str(
                existing.get("knowledge_profile_cache_source")
                or source
            )
            fallback_reason = (
                existing.get("knowledge_profile_cache_fallback_reason")
                or fallback_reason
            )

    diagnostics = {
        "knowledge_profile_cache_hit": hit,
        "knowledge_profile_cache_source": source,
        "knowledge_profile_cache_ttl_seconds": ttl_seconds,
        "knowledge_profile_indexed_file_count": context.indexed_count,
        "knowledge_profile_total_file_count": context.total_count,
    }
    if fallback_reason:
        diagnostics["knowledge_profile_cache_fallback_reason"] = (
            fallback_reason
        )
    _CACHE_DIAGNOSTICS.set(diagnostics)


def build_redis_cache_key(user_id: int, knowledge_base_id: UUID | str) -> str:
    """构造知识库画像的 Redis cache key。"""
    return cache_service.build_cache_key(
        "knowledge_profile",
        user_id,
        str(knowledge_base_id),
    )


def build_redis_cache_prefix(user_id: int) -> str:
    """构造某个用户全部知识库画像缓存的 Redis key 前缀。"""
    return cache_service.build_cache_prefix("knowledge_profile", user_id)


def deserialize_knowledge_base_context(
    value: Any,
) -> KnowledgeBaseContext | None:
    """从 Redis JSON value 还原知识库画像上下文。"""
    if not isinstance(value, dict):
        return None

    file_ids = value.get("file_ids")
    if not isinstance(file_ids, list):
        return None

    try:
        return KnowledgeBaseContext(
            profile=str(value["profile"]),
            file_ids=[str(file_id) for file_id in file_ids],
            indexed_count=int(value["indexed_count"]),
            total_count=int(value["total_count"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def write_memory_cache(
    cache_key: tuple[int, str],
    context: KnowledgeBaseContext,
    now: float,
    ttl_seconds: float,
) -> None:
    """写入进程内 fallback 缓存。"""
    with _CACHE_LOCK:
        prune_expired_cache_entries(now)
        _CACHE[cache_key] = CachedKnowledgeBaseContext(
            value=context,
            expires_at=now + max(0.0, ttl_seconds),
            created_at=now,
        )


def get_memory_cache(
    cache_key: tuple[int, str],
    now: float,
) -> KnowledgeBaseContext | None:
    """读取进程内 fallback 缓存，过期时自动清理。"""
    with _CACHE_LOCK:
        cached = _CACHE.get(cache_key)
        if cached is None:
            return None
        if cached.expires_at > now:
            return cached.value
        _CACHE.pop(cache_key, None)
    return None


def build_knowledge_base_context(
    rows: Sequence[dict[str, Any]],
    max_profile_files: int,
) -> KnowledgeBaseContext:
    """根据知识库文件行构造 profile 文本和已索引 file_ids。"""
    indexed_rows = [
        row
        for row in rows
        if row.get("status") == "indexed"
    ]
    file_ids = [
        str(row["id"])
        for row in indexed_rows
    ]
    if not indexed_rows:
        return KnowledgeBaseContext(
            profile="当前知识库没有已完成索引的文件。",
            file_ids=file_ids,
            indexed_count=0,
            total_count=len(rows),
        )

    profile_lines = [
        "当前知识库已索引文件：",
    ]
    for index, row in enumerate(
        indexed_rows[:max_profile_files],
        start=1,
    ):
        file_name = row.get("original_name") or "未命名文件"
        mime_type = row.get("mime_type") or "未知类型"
        profile_lines.append(f"{index}. {file_name}（{mime_type}）")

    remaining_count = len(indexed_rows) - max_profile_files
    if remaining_count > 0:
        profile_lines.append(f"...另有 {remaining_count} 个已索引文件。")

    return KnowledgeBaseContext(
        profile="\n".join(profile_lines),
        file_ids=file_ids,
        indexed_count=len(indexed_rows),
        total_count=len(rows),
    )


def prune_expired_cache_entries(now: float) -> None:
    """清理过期缓存，并限制最大条目数。"""
    expired_keys = [
        key
        for key, cached in _CACHE.items()
        if cached.expires_at <= now
    ]
    for key in expired_keys:
        _CACHE.pop(key, None)

    if len(_CACHE) <= MAX_PROFILE_CACHE_ENTRIES:
        return

    overflow = len(_CACHE) - MAX_PROFILE_CACHE_ENTRIES
    oldest_keys = sorted(
        _CACHE,
        key=lambda key: _CACHE[key].created_at,
    )[:overflow]
    for key in oldest_keys:
        _CACHE.pop(key, None)


def get_cached_knowledge_base_context(
    *,
    user_id: int,
    knowledge_base_id: UUID,
    load_rows: Callable[[], Sequence[dict[str, Any]]],
    max_profile_files: int,
    ttl_seconds: float = DEFAULT_PROFILE_CACHE_TTL_SECONDS,
) -> KnowledgeBaseContext:
    """读取缓存中的知识库上下文，缺失或过期时重新加载。"""
    cache_key = (user_id, str(knowledge_base_id))
    redis_key = build_redis_cache_key(user_id, knowledge_base_id)
    now = monotonic()
    redis_result = cache_service.get_json_cache(redis_key)

    if redis_result.hit:
        context = deserialize_knowledge_base_context(redis_result.value)
        if context is not None:
            write_memory_cache(cache_key, context, now, ttl_seconds)
            set_cache_diagnostics(
                hit=True,
                context=context,
                source="redis",
                ttl_seconds=ttl_seconds,
            )
            return context

    fallback_reason = redis_result.fallback_reason
    if not redis_result.available:
        memory_context = get_memory_cache(cache_key, now)
        if memory_context is not None:
            set_cache_diagnostics(
                hit=True,
                context=memory_context,
                source="memory",
                ttl_seconds=ttl_seconds,
                fallback_reason=fallback_reason,
            )
            return memory_context

    rows = [dict(row) for row in load_rows()]
    context = build_knowledge_base_context(
        rows,
        max_profile_files=max_profile_files,
    )
    write_memory_cache(cache_key, context, now, ttl_seconds)
    set_result = cache_service.set_json_cache(
        redis_key,
        asdict(context),
        ttl_seconds,
    )
    fallback_reason = fallback_reason or set_result.fallback_reason

    set_cache_diagnostics(
        hit=False,
        context=context,
        source="database",
        ttl_seconds=ttl_seconds,
        fallback_reason=fallback_reason,
    )
    return context


def invalidate_knowledge_base_context(
    user_id: int,
    knowledge_base_id: UUID | str | None = None,
) -> None:
    """失效单个用户的知识库画像缓存。"""
    with _CACHE_LOCK:
        if knowledge_base_id is None:
            for key in list(_CACHE):
                if key[0] == user_id:
                    _CACHE.pop(key, None)
        else:
            _CACHE.pop((user_id, str(knowledge_base_id)), None)

    if knowledge_base_id is None:
        cache_service.delete_cache_prefix(build_redis_cache_prefix(user_id))
        return

    cache_service.delete_cache_key(
        build_redis_cache_key(user_id, knowledge_base_id),
    )


def invalidate_file_knowledge_base_contexts(
    user_id: int,
    file_id: UUID | str,
) -> None:
    """根据文件 ID 失效所有包含该文件的知识库画像缓存。"""
    knowledge_base_ids = get_knowledge_base_ids_for_file(user_id, file_id)
    for knowledge_base_id in knowledge_base_ids:
        invalidate_knowledge_base_context(user_id, knowledge_base_id)

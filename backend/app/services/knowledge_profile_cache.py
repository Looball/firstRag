"""知识库画像的进程内轻量缓存。

缓存内容只用于减少 RAG 前置阶段重复查询知识库文件列表。它不是权威
业务状态，丢失后可以随时从 PostgreSQL 重建，因此先使用短 TTL 的
进程内缓存，而不引入 Redis 等外部基础设施。
"""

from collections.abc import Callable, Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import Any
from uuid import UUID

from app.repositories.knowledge_base_repository import (
    get_knowledge_base_ids_for_file,
)


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
) -> None:
    """记录本次画像读取是否命中缓存。"""
    existing = _CACHE_DIAGNOSTICS.get()
    if isinstance(existing, dict):
        hit = bool(existing.get("knowledge_profile_cache_hit")) and hit

    _CACHE_DIAGNOSTICS.set({
        "knowledge_profile_cache_hit": hit,
        "knowledge_profile_indexed_file_count": context.indexed_count,
        "knowledge_profile_total_file_count": context.total_count,
    })


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
    now = monotonic()

    with _CACHE_LOCK:
        cached = _CACHE.get(cache_key)
        if cached is not None and cached.expires_at > now:
            set_cache_diagnostics(hit=True, context=cached.value)
            return cached.value

    rows = [dict(row) for row in load_rows()]
    context = build_knowledge_base_context(
        rows,
        max_profile_files=max_profile_files,
    )
    expires_at = now + max(0.0, ttl_seconds)

    with _CACHE_LOCK:
        prune_expired_cache_entries(now)
        _CACHE[cache_key] = CachedKnowledgeBaseContext(
            value=context,
            expires_at=expires_at,
            created_at=now,
        )

    set_cache_diagnostics(hit=False, context=context)
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
            return

        _CACHE.pop((user_id, str(knowledge_base_id)), None)


def invalidate_file_knowledge_base_contexts(
    user_id: int,
    file_id: UUID | str,
) -> None:
    """根据文件 ID 失效所有包含该文件的知识库画像缓存。"""
    knowledge_base_ids = get_knowledge_base_ids_for_file(user_id, file_id)
    for knowledge_base_id in knowledge_base_ids:
        invalidate_knowledge_base_context(user_id, knowledge_base_id)

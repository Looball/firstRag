from contextvars import ContextVar
from time import perf_counter
from typing import Any

from app.services.llm_service import ChatModelSettings, resolve_base_url
from app.services.knowledge_profile_cache import (
    get_knowledge_profile_cache_diagnostics,
)

RETRIEVAL_SETTINGS_DIAGNOSTICS_KEY = "_retrieval_settings_diagnostics"
_retrieval_settings_diagnostics: ContextVar[dict[str, Any] | None] = (
    ContextVar("retrieval_settings_diagnostics", default=None)
)

def elapsed_ms(started_at: float) -> float:
    """计算从指定时间点到当前的毫秒耗时。"""
    return round((perf_counter() - started_at) * 1000, 2)


def reset_retrieval_settings_diagnostics() -> None:
    """重置当前请求的 retrieval settings 子阶段诊断。"""
    _retrieval_settings_diagnostics.set(None)


def get_retrieval_settings_diagnostics() -> dict[str, Any] | None:
    """读取当前请求的 retrieval settings 子阶段诊断。"""
    diagnostics = _retrieval_settings_diagnostics.get()
    if diagnostics is None:
        return None
    return dict(diagnostics)


def extract_retrieval_settings_diagnostics(
    settings: Any,
) -> dict[str, Any] | None:
    """从 retrieval settings 对象中提取随 Runnable 传递的子阶段诊断。"""
    if isinstance(settings, dict):
        diagnostics = settings.get(RETRIEVAL_SETTINGS_DIAGNOSTICS_KEY)
        if isinstance(diagnostics, dict):
            return dict(diagnostics)
    return get_retrieval_settings_diagnostics()


def merge_retrieval_settings_diagnostics(
    diagnostics: dict[str, Any] | None,
    settings_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """将 retrieval settings 子阶段诊断合并进 retrieval diagnostics。"""
    merged = dict(diagnostics or {})
    settings_diagnostics = (
        settings_diagnostics
        if settings_diagnostics is not None
        else get_retrieval_settings_diagnostics()
    )
    if settings_diagnostics is None:
        return merged

    cache_diagnostics = settings_diagnostics.get("cache")
    existing_timing = merged.get("timing")
    if not isinstance(existing_timing, dict):
        existing_timing = {}
    merged["timing"] = {
        **existing_timing,
        "retrieval_settings_query_ms": settings_diagnostics[
            "retrieval_settings_query_ms"
        ],
        "retrieval_settings_normalize_ms": settings_diagnostics[
            "retrieval_settings_normalize_ms"
        ],
        "retrieval_settings_load_total_ms": settings_diagnostics[
            "retrieval_settings_load_total_ms"
        ],
    }
    if isinstance(cache_diagnostics, dict):
        merged["retrieval_settings_cache_hit"] = cache_diagnostics.get(
            "retrieval_settings_cache_hit",
        )
        merged["retrieval_settings_cache_ttl_seconds"] = (
            cache_diagnostics.get("retrieval_settings_cache_ttl_seconds")
        )
        merged["retrieval_settings_source"] = cache_diagnostics.get(
            "retrieval_settings_source",
        )
        merged["retrieval_settings_cache_backend"] = cache_diagnostics.get(
            "retrieval_settings_cache_backend",
        )
        merged["retrieval_settings_cache_fallback_reason"] = (
            cache_diagnostics.get(
                "retrieval_settings_cache_fallback_reason",
            )
        )
        return merged

    merged["retrieval_settings_source"] = settings_diagnostics[
        "retrieval_settings_source"
    ]
    return merged


def merge_diagnostics_timing(
    diagnostics: dict[str, Any] | None,
    timing: dict[str, float],
    llm_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """将 RAG 外层耗时合并进 retrieval diagnostics。"""
    merged = dict(diagnostics or {})
    existing_timing = merged.get("timing")
    if not isinstance(existing_timing, dict):
        existing_timing = {}
    merged["timing"] = {
        **existing_timing,
        **timing,
    }
    if llm_diagnostics is not None:
        merged["llm"] = llm_diagnostics
    return merge_retrieval_settings_diagnostics(merged)


def merge_knowledge_profile_cache_diagnostics(
    diagnostics: dict[str, Any] | None,
) -> dict[str, Any]:
    """将知识库画像缓存诊断合并进 retrieval diagnostics。"""
    merged = dict(diagnostics or {})
    cache_diagnostics = get_knowledge_profile_cache_diagnostics()
    if cache_diagnostics is not None:
        merged.update(cache_diagnostics)
    return merged

def serialize_llm_diagnostics(
    settings: ChatModelSettings,
    credential_mode: str,
) -> dict[str, Any]:
    """生成不含 API Key 的 LLM 调用诊断信息。"""
    return {
        "provider": settings.provider,
        "model": settings.model,
        "credential_mode": credential_mode,
        "base_url": resolve_base_url(settings.provider, settings.base_url),
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
        "timeout_seconds": settings.timeout_seconds,
        "max_retries": settings.max_retries,
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
    }


def normalize_token_usage_value(value: Any) -> int | None:
    """将模型返回的 token usage 值规范化为整数或 None。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def extract_token_usage_from_chunk(chunk: Any) -> dict[str, int | None]:
    """从 LangChain/OpenAI 流式消息块中提取 token usage。"""
    usage = getattr(chunk, "usage_metadata", None)
    if not isinstance(usage, dict):
        response_metadata = getattr(chunk, "response_metadata", None)
        if isinstance(response_metadata, dict):
            usage = (
                response_metadata.get("token_usage")
                or response_metadata.get("usage")
            )
    if not isinstance(usage, dict):
        additional_kwargs = getattr(chunk, "additional_kwargs", None)
        if isinstance(additional_kwargs, dict):
            usage = (
                additional_kwargs.get("token_usage")
                or additional_kwargs.get("usage")
            )

    if not isinstance(usage, dict):
        return {}

    prompt_tokens = (
        usage.get("prompt_tokens")
        if "prompt_tokens" in usage
        else usage.get("input_tokens")
    )
    completion_tokens = (
        usage.get("completion_tokens")
        if "completion_tokens" in usage
        else usage.get("output_tokens")
    )
    total_tokens = usage.get("total_tokens")

    return {
        "prompt_tokens": normalize_token_usage_value(prompt_tokens),
        "completion_tokens": normalize_token_usage_value(completion_tokens),
        "total_tokens": normalize_token_usage_value(total_tokens),
    }


def merge_llm_token_usage(
    llm_diagnostics: dict[str, Any] | None,
    token_usage: dict[str, int | None],
) -> dict[str, Any] | None:
    """把 token usage 合并到 LLM 诊断信息中。"""
    if llm_diagnostics is None or not token_usage:
        return llm_diagnostics

    merged = dict(llm_diagnostics)
    for key, value in token_usage.items():
        if value is not None:
            merged[key] = value
    return merged


def extract_answer_text(chunk: Any) -> str:
    """从模型流式 chunk 中提取可返回给前端的文本内容。"""
    content = getattr(chunk, "content", chunk)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return str(content) if content is not None else ""

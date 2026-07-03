"""统一结构化日志、错误分类和敏感字段脱敏工具。"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping, Sequence
from contextvars import ContextVar, Token
from typing import Any

from app.core.sensitive_data import sanitize_sensitive_text


REDACTED_VALUE = "[已脱敏]"
_REQUEST_CONTEXT: ContextVar[dict[str, Any]] = ContextVar(
    "request_context",
    default={},
)
_DATABASE_URL_PATTERN = re.compile(r"(?i)postgres(?:ql)?://[^\s,;]+")

SENSITIVE_FIELD_NAMES = {
    "api_key",
    "authorization",
    "database_url",
    "jwt",
    "password",
    "secret",
    "access_token",
    "refresh_token",
    "api_key_ciphertext",
}
SENSITIVE_FIELD_SUFFIXES = (
    "_api_key",
    "_authorization",
    "_password",
    "_secret",
    "_token",
    "_ciphertext",
)


def set_request_context(**fields: Any) -> Token[dict[str, Any]]:
    """设置当前请求的日志上下文，并返回可恢复 token。"""
    clean_fields = {
        key: value
        for key, value in fields.items()
        if value is not None
    }
    return _REQUEST_CONTEXT.set(clean_fields)


def reset_request_context(token: Token[dict[str, Any]]) -> None:
    """恢复请求日志上下文。"""
    _REQUEST_CONTEXT.reset(token)


def get_request_context() -> dict[str, Any]:
    """读取当前请求的日志上下文。"""
    return dict(_REQUEST_CONTEXT.get() or {})


def is_sensitive_field_name(name: str) -> bool:
    """判断日志字段名是否表示敏感值。"""
    normalized = name.strip().lower()
    return (
        normalized in SENSITIVE_FIELD_NAMES
        or normalized.endswith(SENSITIVE_FIELD_SUFFIXES)
    )


def sanitize_log_value(value: Any, field_name: str | None = None) -> Any:
    """递归脱敏日志字段值，保留数字、布尔值等可聚合指标。"""
    if field_name and is_sensitive_field_name(field_name):
        return REDACTED_VALUE

    if isinstance(value, str):
        sanitized = sanitize_sensitive_text(value)
        return _DATABASE_URL_PATTERN.sub(REDACTED_VALUE, sanitized)

    if isinstance(value, Mapping):
        return {
            str(key): sanitize_log_value(item, str(key))
            for key, item in value.items()
        }

    if isinstance(value, Sequence) and not isinstance(
        value,
        (bytes, bytearray, str),
    ):
        return [
            sanitize_log_value(item)
            for item in value
        ]

    return value


def classify_exception(
    exc: BaseException,
    default_source: str = "unknown",
) -> dict[str, Any]:
    """按异常类型和消息粗分错误来源，便于日志聚合。"""
    error_type = type(exc).__name__
    text = f"{type(exc).__module__}.{error_type} {exc}".lower()
    source = default_source or "unknown"
    retryable = False

    if isinstance(exc, FileNotFoundError):
        source = "file_storage"
    elif "emptydocument" in text or "未解析出可入库" in text:
        source = "document_parse"
    elif (
        "embedding" in text
        or "zhipu" in text
        or (source != "rerank" and "dashscope" in text)
        or "embed_query" in text
    ):
        source = "embedding"
        retryable = True
    elif "chroma" in text or "hnsw" in text or "vector" in text:
        source = "vector_store"
        retryable = True
    elif source == "rerank" or "rerank" in text or "crossencoder" in text:
        source = "rerank"
        retryable = True
    elif (
        "openai" in text
        or "llm" in text
        or "chatopenai" in text
        or "model" in text
        or "api key" in text
        or "api_key" in text
    ):
        source = "llm_provider"
        retryable = True
    elif (
        "postgres" in text
        or "psycopg" in text
        or "database" in text
        or "sql" in text
    ):
        source = "postgres"
        retryable = True
    elif "worker" in text:
        source = "worker"
        retryable = True

    return {
        "error_type": error_type,
        "error_source": source,
        "retryable": retryable,
    }


def build_log_event(event: str, **fields: Any) -> dict[str, Any]:
    """生成带请求上下文、已脱敏且可 JSON 序列化的日志事件。"""
    payload = {
        "event": event,
        **get_request_context(),
        **fields,
    }
    return {
        key: sanitize_log_value(value, key)
        for key, value in payload.items()
        if value is not None
    }


def log_structured_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    """输出统一 JSON 日志事件。"""
    payload = build_log_event(event, **fields)
    logger.log(
        level,
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ),
    )


def log_exception_event(
    logger: logging.Logger,
    event: str,
    exc: BaseException,
    *,
    level: int = logging.ERROR,
    default_source: str = "unknown",
    **fields: Any,
) -> None:
    """输出包含错误分类和脱敏错误摘要的结构化异常日志。"""
    payload = build_log_event(
        event,
        **fields,
        **classify_exception(exc, default_source),
        error_message=str(exc),
    )
    logger.log(
        level,
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ),
    )

"""敏感字符串脱敏工具。"""

from __future__ import annotations

import re
from collections.abc import Iterable


_SECRET_LIKE_PATTERN = re.compile(
    r"(?i)((?:postgres(?:ql)?|rediss?)://[^\s,;]+|sk-[a-z0-9][a-z0-9_\-]{6,}|bearer\s+[a-z0-9._\-]+|api[_-]?key\s*[:=]\s*[^\s,;]+)"
)


def sanitize_sensitive_text(
    value: str,
    sensitive_values: Iterable[str | None] = (),
) -> str:
    """移除错误消息中可能出现的 API Key、Bearer token 等敏感值。"""
    sanitized = value

    for sensitive_value in sensitive_values:
        if not sensitive_value:
            continue
        secret = sensitive_value.strip()
        if len(secret) >= 4:
            sanitized = sanitized.replace(secret, "[已脱敏]")

    return _SECRET_LIKE_PATTERN.sub("[已脱敏]", sanitized)

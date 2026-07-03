"""用户向量模型设置的业务编排。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from ipaddress import ip_address
import socket
from typing import Any
from urllib.parse import urlparse

from app.core.config import ALLOW_USER_CUSTOM_LLM_BASE_URL
from app.core.secret_cipher import (
    build_secret_hint,
    decrypt_secret,
    encrypt_secret,
)
from app.repositories.user_embedding_settings_repository import (
    get_user_embedding_settings,
    upsert_user_embedding_settings,
)


ZHIPU_EMBEDDING_PROVIDER = "zhipuai"
QWEN_EMBEDDING_PROVIDER = "qwen"
DEFAULT_ZHIPU_EMBEDDING_MODEL = "embedding-3"
DEFAULT_QWEN_EMBEDDING_MODEL = "text-embedding-v4"
DEFAULT_QWEN_EMBEDDING_BASE_URL = (
    "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
DEFAULT_EMBEDDING_PROVIDER = QWEN_EMBEDDING_PROVIDER
DEFAULT_EMBEDDING_TIMEOUT_SECONDS = 60.0
DEFAULT_EMBEDDING_MAX_RETRIES = 2

QWEN_EMBEDDING_PROVIDER_ALIASES = {
    "qwen",
    "dashscope",
    "aliyun",
    "aliyun-qwen",
}
ZHIPU_EMBEDDING_PROVIDER_ALIASES = {"zhipu", "zhipuai", "glm"}

EMBEDDING_PROVIDER_DISPLAY_NAMES = {
    QWEN_EMBEDDING_PROVIDER: "通义千问向量",
    ZHIPU_EMBEDDING_PROVIDER: "智谱 Embedding",
}
EMBEDDING_PROVIDER_BASE_URLS = {
    QWEN_EMBEDDING_PROVIDER: DEFAULT_QWEN_EMBEDDING_BASE_URL,
    ZHIPU_EMBEDDING_PROVIDER: None,
}


@dataclass(frozen=True)
class EmbeddingModelSettings:
    """创建 embedding provider 所需的用户级配置。"""

    provider: str
    model: str
    api_key: str
    base_url: str | None
    dimensions: int | None
    timeout_seconds: float
    max_retries: int


def _as_float(value: float | Decimal) -> float:
    """将数据库 NUMERIC 值标准化为响应可序列化的浮点数。"""
    return float(value)


def normalize_embedding_provider(raw_provider: str | None = None) -> str:
    """归一化 embedding provider 名称。"""
    provider = (
        raw_provider or DEFAULT_EMBEDDING_PROVIDER
    ).strip().lower() or DEFAULT_EMBEDDING_PROVIDER
    if provider in ZHIPU_EMBEDDING_PROVIDER_ALIASES:
        return ZHIPU_EMBEDDING_PROVIDER
    if provider in QWEN_EMBEDDING_PROVIDER_ALIASES:
        return QWEN_EMBEDDING_PROVIDER
    raise ValueError(f"不支持的向量模型厂商：{provider}")


def resolve_embedding_model_name(
    provider: str,
    configured_model: str | None = None,
) -> str:
    """根据 provider 和用户输入解析 embedding 模型名。"""
    model = (configured_model or "").strip()
    if model:
        return model
    if provider == QWEN_EMBEDDING_PROVIDER:
        return DEFAULT_QWEN_EMBEDDING_MODEL
    return DEFAULT_ZHIPU_EMBEDDING_MODEL


def _ensure_public_host(host: str, port: int | None = None) -> None:
    """校验自定义 embedding 主机只能解析到公网地址。"""
    normalized_host = host.rstrip(".").lower()
    if (
        normalized_host == "localhost"
        or normalized_host.endswith(".localhost")
        or normalized_host.endswith(".local")
    ):
        raise ValueError("用户自定义 embedding API 地址不能指向本机地址")

    try:
        host_ip = ip_address(normalized_host)
    except ValueError as exc:
        if normalized_host.replace(".", "").isdigit():
            raise ValueError("embedding API 地址的 IP 地址无效") from exc
    else:
        if not host_ip.is_global:
            raise ValueError("用户自定义 embedding API 地址不能指向私网地址")
        return

    try:
        resolved_addresses = socket.getaddrinfo(
            normalized_host,
            port or 443,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise ValueError("无法解析用户自定义 embedding API 地址主机") from exc

    resolved_ips = {
        address[0]
        for *_, address in resolved_addresses
        if address and address[0]
    }
    if not resolved_ips:
        raise ValueError("无法解析用户自定义 embedding API 地址主机")

    for resolved_ip in resolved_ips:
        try:
            parsed_ip = ip_address(resolved_ip)
        except ValueError as exc:
            raise ValueError("embedding API 地址解析结果无效") from exc

        if not parsed_ip.is_global:
            raise ValueError(
                "用户自定义 embedding API 地址不能解析到私网地址"
            )


def _validate_embedding_base_url(
    provider: str,
    base_url: str | None,
) -> str | None:
    """规范化 embedding API 地址，并避免用户配置内网地址。"""
    if base_url is None:
        return None

    normalized_base_url = base_url.strip().rstrip("/")
    if not normalized_base_url:
        return None

    preset_base_url = EMBEDDING_PROVIDER_BASE_URLS.get(provider)
    if preset_base_url and normalized_base_url == preset_base_url:
        return None
    if provider == ZHIPU_EMBEDDING_PROVIDER:
        raise ValueError("智谱 embedding 当前不支持自定义 API 地址")
    if not ALLOW_USER_CUSTOM_LLM_BASE_URL:
        raise ValueError("当前不允许用户自定义 embedding API 地址")

    parsed_url = urlparse(normalized_base_url)
    host = parsed_url.hostname
    if (
        parsed_url.scheme != "https"
        or parsed_url.username
        or parsed_url.password
        or not host
    ):
        raise ValueError("用户自定义 embedding API 地址必须是不含凭据的 HTTPS 地址")
    _ensure_public_host(host, parsed_url.port)
    return normalized_base_url


def get_supported_embedding_providers() -> list[dict[str, object]]:
    """返回供前端展示的向量模型厂商预设。"""
    return [
        {
            "id": provider,
            "name": EMBEDDING_PROVIDER_DISPLAY_NAMES[provider],
            "base_url": EMBEDDING_PROVIDER_BASE_URLS[provider],
            "requires_base_url": False,
            "enabled": True,
            "default_model": resolve_embedding_model_name(provider),
        }
        for provider in (QWEN_EMBEDDING_PROVIDER, ZHIPU_EMBEDDING_PROVIDER)
    ]


def _build_default_embedding_settings() -> EmbeddingModelSettings:
    """生成设置页默认向量模型参数，不携带 API Key。"""
    provider = DEFAULT_EMBEDDING_PROVIDER
    return EmbeddingModelSettings(
        provider=provider,
        model=resolve_embedding_model_name(provider),
        api_key="",
        base_url=None,
        dimensions=None,
        timeout_seconds=DEFAULT_EMBEDDING_TIMEOUT_SECONDS,
        max_retries=DEFAULT_EMBEDDING_MAX_RETRIES,
    )


def _serialize_embedding_settings(
    settings: EmbeddingModelSettings,
    has_api_key: bool,
    api_key_hint: str | None = None,
) -> dict[str, Any]:
    """将向量设置转换为不会泄露 API Key 的响应结构。"""
    return {
        "provider": settings.provider,
        "model": settings.model,
        "base_url": (
            settings.base_url
            or EMBEDDING_PROVIDER_BASE_URLS.get(settings.provider)
        ),
        "dimensions": settings.dimensions,
        "has_api_key": has_api_key,
        "api_key_hint": api_key_hint,
        "timeout_seconds": settings.timeout_seconds,
        "max_retries": settings.max_retries,
    }


def _build_embedding_settings(
    record: dict[str, Any],
    *,
    decrypt_api_key: bool = True,
) -> EmbeddingModelSettings:
    """将用户密文配置转换为可供 embedding 工厂使用的设置。"""
    provider = normalize_embedding_provider(record["provider"])
    return EmbeddingModelSettings(
        provider=provider,
        model=resolve_embedding_model_name(provider, record["model"]),
        api_key=(
            decrypt_secret(record["api_key_ciphertext"])
            if decrypt_api_key
            else ""
        ),
        base_url=record["base_url"],
        dimensions=record.get("dimensions"),
        timeout_seconds=_as_float(record["timeout_seconds"]),
        max_retries=record["max_retries"],
    )


def get_effective_embedding_model_settings(
    user_id: int,
) -> EmbeddingModelSettings:
    """获取当前用户实际生效的向量模型设置。"""
    record = get_user_embedding_settings(user_id)
    if record is None:
        raise ValueError("请先在设置页配置当前账号的向量模型 API Key")

    return _build_embedding_settings(record)


def get_serialized_user_embedding_settings(user_id: int) -> dict[str, Any]:
    """读取当前用户向量设置，并生成不含敏感信息的响应数据。"""
    record = get_user_embedding_settings(user_id)
    if record is None:
        return _serialize_embedding_settings(
            _build_default_embedding_settings(),
            False,
        )

    settings = _build_embedding_settings(record, decrypt_api_key=False)
    api_key_hint = record.get("api_key_hint")
    if not api_key_hint and record["api_key_ciphertext"]:
        api_key_hint = build_secret_hint(
            decrypt_secret(record["api_key_ciphertext"])
        )
    return _serialize_embedding_settings(
        settings,
        bool(record["api_key_ciphertext"]),
        api_key_hint,
    )


def get_serialized_user_embedding_providers(
    user_id: int,
) -> list[dict[str, Any]]:
    """返回向量厂商目录及当前用户的已保存状态。"""
    record = get_user_embedding_settings(user_id)
    active_provider = (
        normalize_embedding_provider(record["provider"]) if record else None
    )
    providers = []
    for provider in get_supported_embedding_providers():
        has_api_key = (
            record is not None
            and active_provider == provider["id"]
            and bool(record["api_key_ciphertext"])
        )
        providers.append({
            **provider,
            "has_api_key": has_api_key,
            "api_key_hint": record.get("api_key_hint") if has_api_key else None,
        })
    return providers


def _merge_embedding_settings_record(
    current_record: dict[str, Any] | None,
    updates: dict[str, Any],
) -> dict[str, Any]:
    """合并局部更新并生成可直接持久化的向量设置记录。"""
    provider = normalize_embedding_provider(
        updates.get(
            "provider",
            current_record.get("provider") if current_record else None,
        )
    )
    current_provider = (
        normalize_embedding_provider(current_record["provider"])
        if current_record
        else None
    )
    current_model = (
        current_record.get("model")
        if current_record and current_provider == provider
        else None
    )
    model = resolve_embedding_model_name(
        provider,
        updates.get("model", current_model),
    )
    current_base_url = (
        current_record.get("base_url")
        if current_record and current_provider == provider
        else None
    )
    base_url = _validate_embedding_base_url(
        provider,
        updates.get("base_url", current_base_url),
    )
    current_dimensions = (
        current_record.get("dimensions")
        if current_record and current_provider == provider
        else None
    )
    dimensions = updates.get(
        "dimensions",
        current_dimensions,
    )
    if dimensions is not None:
        try:
            dimensions = int(dimensions)
        except (TypeError, ValueError) as exc:
            raise ValueError("向量维度必须是正整数") from exc
        if dimensions <= 0:
            dimensions = None

    timeout_seconds = updates.get(
        "timeout_seconds",
        _as_float(current_record["timeout_seconds"])
        if current_record
        else DEFAULT_EMBEDDING_TIMEOUT_SECONDS,
    )
    max_retries = updates.get(
        "max_retries",
        current_record["max_retries"]
        if current_record
        else DEFAULT_EMBEDDING_MAX_RETRIES,
    )

    if "api_key" in updates:
        api_key_ciphertext = encrypt_secret(updates["api_key"])
        api_key_hint = build_secret_hint(updates["api_key"])
    elif current_record is not None and current_provider == provider:
        api_key_ciphertext = current_record.get("api_key_ciphertext")
        api_key_hint = current_record.get("api_key_hint")
    else:
        api_key_ciphertext = None
        api_key_hint = None

    if not api_key_ciphertext:
        raise ValueError("请先配置当前向量模型厂商的 API Key")

    return {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "dimensions": dimensions,
        "api_key_ciphertext": api_key_ciphertext,
        "api_key_hint": api_key_hint,
        "encryption_key_version": 1,
        "timeout_seconds": timeout_seconds,
        "max_retries": max_retries,
    }


def update_user_embedding_settings(
    user_id: int,
    updates: dict[str, Any],
) -> dict[str, Any]:
    """更新当前用户向量模型设置，并返回不含 API Key 的配置。"""
    current_record = get_user_embedding_settings(user_id)
    settings_record = _merge_embedding_settings_record(current_record, updates)
    saved_record = upsert_user_embedding_settings(user_id, settings_record)
    if saved_record is None:
        raise RuntimeError("保存用户向量模型设置失败")

    return get_serialized_user_embedding_settings(user_id)


def check_user_embedding_settings(
    user_id: int,
    updates: dict[str, Any],
) -> dict[str, Any]:
    """测试当前用户向量模型设置。"""
    current_record = get_user_embedding_settings(user_id)
    if updates:
        settings_record = _merge_embedding_settings_record(
            current_record,
            updates,
        )
        settings = _build_embedding_settings(settings_record)
    else:
        settings = get_effective_embedding_model_settings(user_id)

    # 延迟导入避免 embedding 工厂反向依赖设置服务时形成循环导入。
    from app.services.vectors.embedding_model import (  # pylint: disable=import-outside-toplevel
        create_embedding_model_from_settings,
    )

    embeddings = create_embedding_model_from_settings(settings)
    vector = embeddings.embed_query("FirstRAG embedding connection test")
    if not vector:
        raise RuntimeError("向量模型未返回有效 embedding")

    return {
        "message": "向量模型连接测试成功",
        "provider": settings.provider,
        "model": settings.model,
        "dimensions": len(vector),
    }

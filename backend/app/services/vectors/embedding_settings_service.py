"""用户向量模型设置的业务编排。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.core.config import ALLOW_USER_CUSTOM_LLM_BASE_URL
from app.core.secret_cipher import (
    build_secret_hint,
    decrypt_secret,
    encrypt_secret,
)
from app.repositories.user_embedding_provider_credential_repository import (
    get_user_embedding_provider_credential,
    get_user_embedding_provider_credentials,
    upsert_user_embedding_provider_credential,
)
from app.repositories.user_embedding_settings_repository import (
    get_user_embedding_settings,
    upsert_user_embedding_settings,
)
from app.services.provider_base_url import validate_public_https_base_url


ZHIPU_EMBEDDING_PROVIDER = "zhipuai"
QWEN_EMBEDDING_PROVIDER = "qwen"
OPENAI_EMBEDDING_PROVIDER = "openai"
VOYAGE_EMBEDDING_PROVIDER = "voyage"
COHERE_EMBEDDING_PROVIDER = "cohere"
JINA_EMBEDDING_PROVIDER = "jina"
OPENAI_COMPATIBLE_EMBEDDING_PROVIDER = "openai_compatible"

DEFAULT_ZHIPU_EMBEDDING_MODEL = "embedding-3"
DEFAULT_QWEN_EMBEDDING_MODEL = "text-embedding-v4"
DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_VOYAGE_EMBEDDING_MODEL = "voyage-4"
DEFAULT_COHERE_EMBEDDING_MODEL = "embed-v4.0"
DEFAULT_JINA_EMBEDDING_MODEL = "jina-embeddings-v3"
DEFAULT_QWEN_EMBEDDING_BASE_URL = (
    "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
DEFAULT_OPENAI_EMBEDDING_BASE_URL = "https://api.openai.com/v1"
DEFAULT_VOYAGE_EMBEDDING_BASE_URL = "https://api.voyageai.com/v1"
DEFAULT_COHERE_EMBEDDING_BASE_URL = "https://api.cohere.com"
DEFAULT_JINA_EMBEDDING_BASE_URL = "https://api.jina.ai/v1"
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
OPENAI_EMBEDDING_PROVIDER_ALIASES = {"openai"}
VOYAGE_EMBEDDING_PROVIDER_ALIASES = {"voyage", "voyageai", "voyage-ai"}
COHERE_EMBEDDING_PROVIDER_ALIASES = {"cohere"}
JINA_EMBEDDING_PROVIDER_ALIASES = {"jina", "jinaai", "jina-ai"}
OPENAI_COMPATIBLE_EMBEDDING_PROVIDER_ALIASES = {
    "openai_compatible",
    "openai-compatible",
    "custom",
    "custom_openai",
}

EMBEDDING_PROVIDER_ORDER = (
    QWEN_EMBEDDING_PROVIDER,
    ZHIPU_EMBEDDING_PROVIDER,
    OPENAI_EMBEDDING_PROVIDER,
    VOYAGE_EMBEDDING_PROVIDER,
    COHERE_EMBEDDING_PROVIDER,
    JINA_EMBEDDING_PROVIDER,
    OPENAI_COMPATIBLE_EMBEDDING_PROVIDER,
)
EMBEDDING_PROVIDER_DISPLAY_NAMES = {
    QWEN_EMBEDDING_PROVIDER: "通义千问向量",
    ZHIPU_EMBEDDING_PROVIDER: "智谱 Embedding",
    OPENAI_EMBEDDING_PROVIDER: "OpenAI Embeddings",
    VOYAGE_EMBEDDING_PROVIDER: "Voyage AI Embeddings",
    COHERE_EMBEDDING_PROVIDER: "Cohere Embed",
    JINA_EMBEDDING_PROVIDER: "Jina Embeddings",
    OPENAI_COMPATIBLE_EMBEDDING_PROVIDER: "自定义 OpenAI 兼容向量服务",
}
EMBEDDING_PROVIDER_BASE_URLS = {
    QWEN_EMBEDDING_PROVIDER: DEFAULT_QWEN_EMBEDDING_BASE_URL,
    ZHIPU_EMBEDDING_PROVIDER: None,
    OPENAI_EMBEDDING_PROVIDER: DEFAULT_OPENAI_EMBEDDING_BASE_URL,
    VOYAGE_EMBEDDING_PROVIDER: DEFAULT_VOYAGE_EMBEDDING_BASE_URL,
    COHERE_EMBEDDING_PROVIDER: DEFAULT_COHERE_EMBEDDING_BASE_URL,
    JINA_EMBEDDING_PROVIDER: DEFAULT_JINA_EMBEDDING_BASE_URL,
    OPENAI_COMPATIBLE_EMBEDDING_PROVIDER: None,
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
    if provider in OPENAI_EMBEDDING_PROVIDER_ALIASES:
        return OPENAI_EMBEDDING_PROVIDER
    if provider in VOYAGE_EMBEDDING_PROVIDER_ALIASES:
        return VOYAGE_EMBEDDING_PROVIDER
    if provider in COHERE_EMBEDDING_PROVIDER_ALIASES:
        return COHERE_EMBEDDING_PROVIDER
    if provider in JINA_EMBEDDING_PROVIDER_ALIASES:
        return JINA_EMBEDDING_PROVIDER
    if provider in OPENAI_COMPATIBLE_EMBEDDING_PROVIDER_ALIASES:
        return OPENAI_COMPATIBLE_EMBEDDING_PROVIDER
    raise ValueError(f"不支持的向量模型厂商：{provider}")


def resolve_embedding_model_name(
    provider: str,
    configured_model: str | None = None,
) -> str:
    """根据 provider 和用户输入解析 embedding 模型名。"""
    model = (configured_model or "").strip()
    if model:
        return model
    defaults = {
        QWEN_EMBEDDING_PROVIDER: DEFAULT_QWEN_EMBEDDING_MODEL,
        ZHIPU_EMBEDDING_PROVIDER: DEFAULT_ZHIPU_EMBEDDING_MODEL,
        OPENAI_EMBEDDING_PROVIDER: DEFAULT_OPENAI_EMBEDDING_MODEL,
        VOYAGE_EMBEDDING_PROVIDER: DEFAULT_VOYAGE_EMBEDDING_MODEL,
        COHERE_EMBEDDING_PROVIDER: DEFAULT_COHERE_EMBEDDING_MODEL,
        JINA_EMBEDDING_PROVIDER: DEFAULT_JINA_EMBEDDING_MODEL,
        OPENAI_COMPATIBLE_EMBEDDING_PROVIDER: DEFAULT_OPENAI_EMBEDDING_MODEL,
    }
    return defaults[provider]


def resolve_embedding_base_url(provider: str, base_url: str | None) -> str | None:
    """解析 embedding provider 的实际 API 地址。"""
    if provider == ZHIPU_EMBEDDING_PROVIDER:
        return None
    resolved_base_url = base_url or EMBEDDING_PROVIDER_BASE_URLS.get(provider)
    if not resolved_base_url:
        raise ValueError("自定义 OpenAI 兼容向量服务必须配置 API 地址")
    return resolved_base_url.rstrip("/")


def _requires_base_url(provider: str) -> bool:
    """判断指定向量 provider 是否必须由用户填写 API 地址。"""
    return provider == OPENAI_COMPATIBLE_EMBEDDING_PROVIDER


def _validate_embedding_base_url(
    provider: str,
    base_url: str | None,
) -> str | None:
    """规范化 embedding API 地址，并避免用户配置内网地址。"""
    if base_url is None:
        if _requires_base_url(provider):
            raise ValueError("自定义 OpenAI 兼容向量服务需要填写 API 地址")
        return None

    normalized_base_url = base_url.strip().rstrip("/")
    if not normalized_base_url:
        if _requires_base_url(provider):
            raise ValueError("自定义 OpenAI 兼容向量服务需要填写 API 地址")
        return None

    preset_base_url = EMBEDDING_PROVIDER_BASE_URLS.get(provider)
    if preset_base_url and normalized_base_url == preset_base_url:
        return None
    if provider == ZHIPU_EMBEDDING_PROVIDER:
        raise ValueError("智谱 embedding 当前不支持自定义 API 地址")
    if not ALLOW_USER_CUSTOM_LLM_BASE_URL:
        raise ValueError("当前不允许用户自定义 embedding API 地址")
    return validate_public_https_base_url(normalized_base_url)


def get_supported_embedding_providers() -> list[dict[str, object]]:
    """返回供前端展示的向量模型厂商预设。"""
    providers = []
    for provider in EMBEDDING_PROVIDER_ORDER:
        providers.append({
            "id": provider,
            "name": EMBEDDING_PROVIDER_DISPLAY_NAMES[provider],
            "base_url": EMBEDDING_PROVIDER_BASE_URLS[provider],
            "requires_base_url": _requires_base_url(provider),
            "enabled": (
                provider != OPENAI_COMPATIBLE_EMBEDDING_PROVIDER
                or ALLOW_USER_CUSTOM_LLM_BASE_URL
            ),
            "default_model": resolve_embedding_model_name(provider),
        })
    return providers


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


def _apply_provider_credential(
    record: dict[str, Any],
    credential: dict[str, Any] | None,
) -> dict[str, Any]:
    """优先使用向量厂商凭据表中的 Key，兼容旧设置表中的活动 Key。"""
    if credential is None:
        return record
    return {
        **record,
        "api_key_ciphertext": credential["api_key_ciphertext"],
        "api_key_hint": credential.get("api_key_hint"),
        "encryption_key_version": credential["encryption_key_version"],
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

    provider = normalize_embedding_provider(record["provider"])
    credential = get_user_embedding_provider_credential(user_id, provider)
    record = _apply_provider_credential(record, credential)
    if not record.get("api_key_ciphertext"):
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

    provider = normalize_embedding_provider(record["provider"])
    credential = get_user_embedding_provider_credential(user_id, provider)
    record = _apply_provider_credential(record, credential)
    settings = _build_embedding_settings(record, decrypt_api_key=False)
    api_key_hint = record.get("api_key_hint")
    if not api_key_hint and record.get("api_key_ciphertext"):
        api_key_hint = build_secret_hint(
            decrypt_secret(record["api_key_ciphertext"])
        )
    return _serialize_embedding_settings(
        settings,
        bool(record.get("api_key_ciphertext")),
        api_key_hint,
    )


def get_serialized_user_embedding_providers(
    user_id: int,
) -> list[dict[str, Any]]:
    """返回向量厂商目录及当前用户的已保存状态。"""
    credentials_by_provider = {
        row["provider"]: row
        for row in get_user_embedding_provider_credentials(user_id)
    }
    record = get_user_embedding_settings(user_id)
    active_provider = (
        normalize_embedding_provider(record["provider"]) if record else None
    )
    providers = []
    for provider in get_supported_embedding_providers():
        credential = credentials_by_provider.get(provider["id"])
        legacy_active_key = (
            credential is None
            and record is not None
            and active_provider == provider["id"]
            and bool(record.get("api_key_ciphertext"))
        )
        providers.append({
            **provider,
            "has_api_key": credential is not None or legacy_active_key,
            "api_key_hint": (
                credential.get("api_key_hint")
                if credential
                else (
                    record.get("api_key_hint") if legacy_active_key else None
                )
            ),
        })
    return providers


def _get_provider_credential_for_updates(
    user_id: int,
    current_record: dict[str, Any] | None,
    updates: dict[str, Any],
) -> dict[str, Any] | None:
    """查询本次向量厂商已有凭据，以便切换时自动复用。"""
    provider = normalize_embedding_provider(
        updates.get(
            "provider",
            current_record.get("provider") if current_record else None,
        )
    )
    return get_user_embedding_provider_credential(user_id, provider)


def _merge_embedding_settings_record(
    current_record: dict[str, Any] | None,
    updates: dict[str, Any],
    *,
    provider_credential: dict[str, Any] | None = None,
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
    elif provider_credential is not None:
        api_key_ciphertext = provider_credential["api_key_ciphertext"]
        api_key_hint = provider_credential.get("api_key_hint")
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
    provider_credential = _get_provider_credential_for_updates(
        user_id,
        current_record,
        updates,
    )
    settings_record = _merge_embedding_settings_record(
        current_record,
        updates,
        provider_credential=provider_credential,
    )
    saved_credential = upsert_user_embedding_provider_credential(
        user_id,
        settings_record["provider"],
        settings_record,
    )
    if saved_credential is None:
        raise RuntimeError("保存用户向量厂商凭据失败")

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
    provider_credential = _get_provider_credential_for_updates(
        user_id,
        current_record,
        updates,
    )
    if updates:
        settings_record = _merge_embedding_settings_record(
            current_record,
            updates,
            provider_credential=provider_credential,
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

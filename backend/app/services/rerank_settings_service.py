"""用户 rerank 模型设置的业务编排。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from langchain_core.documents import Document

from app.core import config
from app.core.secret_cipher import (
    build_secret_hint,
    decrypt_secret,
    encrypt_secret,
)
from app.repositories.user_rerank_provider_credential_repository import (
    get_user_rerank_provider_credential,
    get_user_rerank_provider_credentials,
    upsert_user_rerank_provider_credential,
)
from app.repositories.user_rerank_settings_repository import (
    get_user_rerank_settings,
    upsert_user_rerank_settings,
)
from app.services.provider_base_url import validate_public_https_base_url


LOCAL_RERANK_PROVIDER = "local"
QWEN_RERANK_PROVIDER = "qwen"
VOYAGE_RERANK_PROVIDER = "voyage"
COHERE_RERANK_PROVIDER = "cohere"
JINA_RERANK_PROVIDER = "jina"
OPENAI_COMPATIBLE_RERANK_PROVIDER = "openai_compatible"

DEFAULT_LOCAL_RERANK_MODEL = str(config.RERANKER_MODEL_PATH)
DEFAULT_QWEN_RERANK_MODEL = "qwen3-rerank"
DEFAULT_VOYAGE_RERANK_MODEL = "rerank-2.5"
DEFAULT_COHERE_RERANK_MODEL = "rerank-v3.5"
DEFAULT_JINA_RERANK_MODEL = "jina-reranker-v2-base-multilingual"
DEFAULT_VOYAGE_RERANK_BASE_URL = "https://api.voyageai.com/v1"
DEFAULT_COHERE_RERANK_BASE_URL = "https://api.cohere.com"
DEFAULT_JINA_RERANK_BASE_URL = "https://api.jina.ai/v1"
DEFAULT_RERANK_PROVIDER = LOCAL_RERANK_PROVIDER
DEFAULT_RERANK_TIMEOUT_SECONDS = 60.0
DEFAULT_RERANK_MAX_RETRIES = 2

LOCAL_RERANK_PROVIDER_ALIASES = {
    "local",
    "cross_encoder",
    "cross-encoder",
    "bge",
}
QWEN_RERANK_PROVIDER_ALIASES = {
    "qwen",
    "dashscope",
    "aliyun",
    "aliyun-qwen",
}
VOYAGE_RERANK_PROVIDER_ALIASES = {"voyage", "voyageai", "voyage-ai"}
COHERE_RERANK_PROVIDER_ALIASES = {"cohere"}
JINA_RERANK_PROVIDER_ALIASES = {"jina", "jinaai", "jina-ai"}
OPENAI_COMPATIBLE_RERANK_PROVIDER_ALIASES = {
    "openai_compatible",
    "openai-compatible",
    "custom",
    "custom_rerank",
}

RERANK_PROVIDER_ORDER = (
    LOCAL_RERANK_PROVIDER,
    QWEN_RERANK_PROVIDER,
    VOYAGE_RERANK_PROVIDER,
    COHERE_RERANK_PROVIDER,
    JINA_RERANK_PROVIDER,
    OPENAI_COMPATIBLE_RERANK_PROVIDER,
)
RERANK_PROVIDER_DISPLAY_NAMES = {
    LOCAL_RERANK_PROVIDER: "本地 BGE Cross-Encoder",
    QWEN_RERANK_PROVIDER: "通义千问 Rerank",
    VOYAGE_RERANK_PROVIDER: "Voyage AI Rerank",
    COHERE_RERANK_PROVIDER: "Cohere Rerank",
    JINA_RERANK_PROVIDER: "Jina Reranker",
    OPENAI_COMPATIBLE_RERANK_PROVIDER: "自定义 Rerank API",
}
RERANK_PROVIDER_BASE_URLS = {
    LOCAL_RERANK_PROVIDER: None,
    QWEN_RERANK_PROVIDER: config.RERANK_BASE_URL or None,
    VOYAGE_RERANK_PROVIDER: DEFAULT_VOYAGE_RERANK_BASE_URL,
    COHERE_RERANK_PROVIDER: DEFAULT_COHERE_RERANK_BASE_URL,
    JINA_RERANK_PROVIDER: DEFAULT_JINA_RERANK_BASE_URL,
    OPENAI_COMPATIBLE_RERANK_PROVIDER: None,
}


@dataclass(frozen=True)
class RerankModelSettings:
    """创建 rerank provider 所需的用户级配置。"""

    provider: str
    model: str
    api_key: str
    base_url: str | None
    instruct: str | None
    timeout_seconds: float
    max_retries: int


def _as_float(value: float | Decimal) -> float:
    """将数据库 NUMERIC 值标准化为响应可序列化的浮点数。"""
    return float(value)


def normalize_rerank_provider(raw_provider: str | None = None) -> str:
    """归一化 rerank provider 名称。"""
    provider = (
        raw_provider or DEFAULT_RERANK_PROVIDER
    ).strip().lower() or DEFAULT_RERANK_PROVIDER
    if provider in LOCAL_RERANK_PROVIDER_ALIASES:
        return LOCAL_RERANK_PROVIDER
    if provider in QWEN_RERANK_PROVIDER_ALIASES:
        return QWEN_RERANK_PROVIDER
    if provider in VOYAGE_RERANK_PROVIDER_ALIASES:
        return VOYAGE_RERANK_PROVIDER
    if provider in COHERE_RERANK_PROVIDER_ALIASES:
        return COHERE_RERANK_PROVIDER
    if provider in JINA_RERANK_PROVIDER_ALIASES:
        return JINA_RERANK_PROVIDER
    if provider in OPENAI_COMPATIBLE_RERANK_PROVIDER_ALIASES:
        return OPENAI_COMPATIBLE_RERANK_PROVIDER
    raise ValueError(f"不支持的 rerank 厂商：{provider}")


def resolve_rerank_model_name(
    provider: str,
    configured_model: str | None = None,
) -> str:
    """根据 provider 和用户输入解析 rerank 模型名。"""
    model = (configured_model or "").strip()
    if model:
        return model
    defaults = {
        LOCAL_RERANK_PROVIDER: DEFAULT_LOCAL_RERANK_MODEL,
        QWEN_RERANK_PROVIDER: DEFAULT_QWEN_RERANK_MODEL,
        VOYAGE_RERANK_PROVIDER: DEFAULT_VOYAGE_RERANK_MODEL,
        COHERE_RERANK_PROVIDER: DEFAULT_COHERE_RERANK_MODEL,
        JINA_RERANK_PROVIDER: DEFAULT_JINA_RERANK_MODEL,
        OPENAI_COMPATIBLE_RERANK_PROVIDER: DEFAULT_QWEN_RERANK_MODEL,
    }
    return defaults[provider]


def provider_requires_rerank_api_key(provider: str) -> bool:
    """判断指定 rerank provider 是否需要用户 API Key。"""
    return provider != LOCAL_RERANK_PROVIDER


def _requires_base_url(provider: str) -> bool:
    """判断指定 rerank provider 是否必须由用户填写 API 地址。"""
    return provider in {
        QWEN_RERANK_PROVIDER,
        OPENAI_COMPATIBLE_RERANK_PROVIDER,
    }


def resolve_rerank_base_url(provider: str, base_url: str | None) -> str | None:
    """解析 rerank provider 的实际 API 地址。"""
    if provider == LOCAL_RERANK_PROVIDER:
        return None
    resolved_base_url = base_url or RERANK_PROVIDER_BASE_URLS.get(provider)
    if not resolved_base_url:
        raise ValueError("当前 rerank 厂商需要填写 API 地址")
    return resolved_base_url.rstrip("/")


def _validate_rerank_base_url(
    provider: str,
    base_url: str | None,
) -> str | None:
    """规范化 rerank API 地址，并避免用户配置内网地址。"""
    if provider == LOCAL_RERANK_PROVIDER:
        return None
    if base_url is None:
        if _requires_base_url(provider):
            raise ValueError("当前 rerank 厂商需要填写 API 地址")
        return None

    normalized_base_url = base_url.strip().rstrip("/")
    if not normalized_base_url:
        if _requires_base_url(provider):
            raise ValueError("当前 rerank 厂商需要填写 API 地址")
        return None

    preset_base_url = RERANK_PROVIDER_BASE_URLS.get(provider)
    if preset_base_url and normalized_base_url == preset_base_url:
        return None
    return validate_public_https_base_url(normalized_base_url)


def get_supported_rerank_providers() -> list[dict[str, object]]:
    """返回供前端展示的 rerank 模型厂商预设。"""
    return [
        {
            "id": provider,
            "name": RERANK_PROVIDER_DISPLAY_NAMES[provider],
            "base_url": RERANK_PROVIDER_BASE_URLS[provider],
            "requires_base_url": _requires_base_url(provider),
            "requires_api_key": provider_requires_rerank_api_key(provider),
            "enabled": True,
            "default_model": resolve_rerank_model_name(provider),
        }
        for provider in RERANK_PROVIDER_ORDER
    ]


def _build_default_rerank_settings() -> RerankModelSettings:
    """生成设置页默认 rerank 模型参数，不携带 API Key。"""
    provider = DEFAULT_RERANK_PROVIDER
    return RerankModelSettings(
        provider=provider,
        model=resolve_rerank_model_name(provider),
        api_key="",
        base_url=None,
        instruct=config.RERANK_INSTRUCT or None,
        timeout_seconds=DEFAULT_RERANK_TIMEOUT_SECONDS,
        max_retries=DEFAULT_RERANK_MAX_RETRIES,
    )


def _serialize_rerank_settings(
    settings: RerankModelSettings,
    has_api_key: bool,
    api_key_hint: str | None = None,
) -> dict[str, Any]:
    """将 rerank 设置转换为不会泄露 API Key 的响应结构。"""
    return {
        "provider": settings.provider,
        "model": settings.model,
        "base_url": (
            settings.base_url
            or RERANK_PROVIDER_BASE_URLS.get(settings.provider)
        ),
        "instruct": settings.instruct,
        "has_api_key": has_api_key,
        "api_key_hint": api_key_hint,
        "requires_api_key": provider_requires_rerank_api_key(
            settings.provider,
        ),
        "timeout_seconds": settings.timeout_seconds,
        "max_retries": settings.max_retries,
    }


def _apply_provider_credential(
    record: dict[str, Any],
    credential: dict[str, Any] | None,
) -> dict[str, Any]:
    """将 rerank 厂商凭据合并进当前设置记录。"""
    if credential is None:
        return record
    return {
        **record,
        "api_key_ciphertext": credential["api_key_ciphertext"],
        "api_key_hint": credential.get("api_key_hint"),
        "encryption_key_version": credential["encryption_key_version"],
    }


def _build_rerank_settings(
    record: dict[str, Any],
    *,
    decrypt_api_key: bool = True,
) -> RerankModelSettings:
    """将用户密文配置转换为可供 rerank 工厂使用的设置。"""
    provider = normalize_rerank_provider(record["provider"])
    api_key_ciphertext = record.get("api_key_ciphertext")
    return RerankModelSettings(
        provider=provider,
        model=resolve_rerank_model_name(provider, record["model"]),
        api_key=(
            decrypt_secret(api_key_ciphertext)
            if decrypt_api_key and api_key_ciphertext
            else ""
        ),
        base_url=record.get("base_url"),
        instruct=record.get("instruct"),
        timeout_seconds=_as_float(record["timeout_seconds"]),
        max_retries=record["max_retries"],
    )


def get_effective_rerank_model_settings(user_id: int) -> RerankModelSettings:
    """获取当前用户实际生效的 rerank 模型设置。"""
    record = get_user_rerank_settings(user_id)
    if record is None:
        return _build_default_rerank_settings()

    provider = normalize_rerank_provider(record["provider"])
    credential = get_user_rerank_provider_credential(user_id, provider)
    record = _apply_provider_credential(record, credential)
    if provider_requires_rerank_api_key(provider) and not record.get(
        "api_key_ciphertext",
    ):
        raise ValueError("请先在设置页配置当前 rerank 厂商的 API Key")
    return _build_rerank_settings(record)


def get_serialized_user_rerank_settings(user_id: int) -> dict[str, Any]:
    """读取当前用户 rerank 设置，并生成不含敏感信息的响应数据。"""
    record = get_user_rerank_settings(user_id)
    if record is None:
        return _serialize_rerank_settings(_build_default_rerank_settings(), False)

    provider = normalize_rerank_provider(record["provider"])
    credential = get_user_rerank_provider_credential(user_id, provider)
    record = _apply_provider_credential(record, credential)
    settings = _build_rerank_settings(record, decrypt_api_key=False)
    api_key_hint = record.get("api_key_hint")
    if not api_key_hint and record.get("api_key_ciphertext"):
        api_key_hint = build_secret_hint(
            decrypt_secret(record["api_key_ciphertext"])
        )
    return _serialize_rerank_settings(
        settings,
        bool(record.get("api_key_ciphertext")),
        api_key_hint,
    )


def get_serialized_user_rerank_providers(user_id: int) -> list[dict[str, Any]]:
    """返回 rerank 厂商目录及当前用户的已保存状态。"""
    credentials_by_provider = {
        row["provider"]: row
        for row in get_user_rerank_provider_credentials(user_id)
    }
    providers = []
    for provider in get_supported_rerank_providers():
        credential = credentials_by_provider.get(provider["id"])
        requires_api_key = bool(provider["requires_api_key"])
        providers.append({
            **provider,
            "has_api_key": (not requires_api_key) or credential is not None,
            "api_key_hint": (
                credential.get("api_key_hint") if credential else None
            ),
        })
    return providers


def _get_provider_credential_for_updates(
    user_id: int,
    current_record: dict[str, Any] | None,
    updates: dict[str, Any],
) -> dict[str, Any] | None:
    """查询本次 rerank 厂商已有凭据，以便切换时自动复用。"""
    provider = normalize_rerank_provider(
        updates.get(
            "provider",
            current_record.get("provider") if current_record else None,
        )
    )
    if not provider_requires_rerank_api_key(provider):
        return None
    return get_user_rerank_provider_credential(user_id, provider)


def _merge_rerank_settings_record(
    current_record: dict[str, Any] | None,
    updates: dict[str, Any],
    *,
    provider_credential: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """合并局部更新并生成可直接持久化的 rerank 设置记录。"""
    provider = normalize_rerank_provider(
        updates.get(
            "provider",
            current_record.get("provider") if current_record else None,
        )
    )
    current_provider = (
        normalize_rerank_provider(current_record["provider"])
        if current_record
        else None
    )
    current_model = (
        current_record.get("model")
        if current_record and current_provider == provider
        else None
    )
    model = resolve_rerank_model_name(
        provider,
        updates.get("model", current_model),
    )
    current_base_url = (
        current_record.get("base_url")
        if current_record and current_provider == provider
        else None
    )
    base_url = _validate_rerank_base_url(
        provider,
        updates.get("base_url", current_base_url),
    )
    instruct = updates.get(
        "instruct",
        current_record.get("instruct")
        if current_record and current_provider == provider
        else None,
    )
    instruct = instruct.strip() if isinstance(instruct, str) else None
    timeout_seconds = updates.get(
        "timeout_seconds",
        _as_float(current_record["timeout_seconds"])
        if current_record
        else DEFAULT_RERANK_TIMEOUT_SECONDS,
    )
    max_retries = updates.get(
        "max_retries",
        current_record["max_retries"]
        if current_record
        else DEFAULT_RERANK_MAX_RETRIES,
    )

    api_key_ciphertext = None
    api_key_hint = None
    if provider_requires_rerank_api_key(provider):
        if "api_key" in updates:
            api_key_ciphertext = encrypt_secret(updates["api_key"])
            api_key_hint = build_secret_hint(updates["api_key"])
        elif provider_credential is not None:
            api_key_ciphertext = provider_credential["api_key_ciphertext"]
            api_key_hint = provider_credential.get("api_key_hint")

        if not api_key_ciphertext:
            raise ValueError("请先配置当前 rerank 厂商的 API Key")

    return {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "instruct": instruct,
        "api_key_ciphertext": api_key_ciphertext,
        "api_key_hint": api_key_hint,
        "encryption_key_version": 1,
        "timeout_seconds": timeout_seconds,
        "max_retries": max_retries,
    }


def update_user_rerank_settings(
    user_id: int,
    updates: dict[str, Any],
) -> dict[str, Any]:
    """更新当前用户 rerank 模型设置，并返回不含 API Key 的配置。"""
    current_record = get_user_rerank_settings(user_id)
    provider_credential = _get_provider_credential_for_updates(
        user_id,
        current_record,
        updates,
    )
    settings_record = _merge_rerank_settings_record(
        current_record,
        updates,
        provider_credential=provider_credential,
    )
    if settings_record["api_key_ciphertext"]:
        saved_credential = upsert_user_rerank_provider_credential(
            user_id,
            settings_record["provider"],
            settings_record,
        )
        if saved_credential is None:
            raise RuntimeError("保存用户 rerank 厂商凭据失败")

    saved_record = upsert_user_rerank_settings(user_id, settings_record)
    if saved_record is None:
        raise RuntimeError("保存用户 rerank 模型设置失败")

    return get_serialized_user_rerank_settings(user_id)


def check_user_rerank_settings(
    user_id: int,
    updates: dict[str, Any],
) -> dict[str, Any]:
    """测试当前用户 rerank 模型设置。"""
    current_record = get_user_rerank_settings(user_id)
    provider_credential = _get_provider_credential_for_updates(
        user_id,
        current_record,
        updates,
    )
    if updates:
        settings_record = _merge_rerank_settings_record(
            current_record,
            updates,
            provider_credential=provider_credential,
        )
        settings = _build_rerank_settings(settings_record)
    else:
        settings = get_effective_rerank_model_settings(user_id)

    from app.services.retrieval.reranker import (  # pylint: disable=import-outside-toplevel
        create_reranker_from_settings,
    )

    documents = [
        "FirstRAG 是一个 RAG 应用。",
        "这是一段无关文本。",
    ]
    reranked = create_reranker_from_settings(settings).rerank(
        query="FirstRAG 是什么？",
        documents=[
            Document(
                page_content=document,
                metadata={},
            )
            for document in documents
        ],
        top_k=1,
    )
    if not reranked:
        raise RuntimeError("rerank 模型未返回有效排序结果")

    return {
        "message": "Rerank 模型连接测试成功",
        "provider": settings.provider,
        "model": settings.model,
        "top_score": reranked[0].metadata.get("rerank_score"),
    }

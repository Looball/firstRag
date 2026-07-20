"""用户聊天模型设置的业务编排。"""

from dataclasses import dataclass, replace
from decimal import Decimal
from ipaddress import ip_address
import socket
from typing import Any
from urllib.parse import urlparse

from openai import AuthenticationError, OpenAI, PermissionDeniedError

from app.core.config import ALLOW_USER_CUSTOM_LLM_BASE_URL
from app.core.secret_cipher import (
    build_secret_hint,
    decrypt_secret,
    encrypt_secret,
)
from app.repositories.user_llm_settings_repository import (
    get_user_llm_settings,
    upsert_user_llm_settings,
)
from app.repositories.user_llm_provider_credential_repository import (
    get_user_llm_provider_credential,
    get_user_llm_provider_credentials,
    upsert_user_llm_provider_credential,
)
from app.services.llm_service import (
    ChatModelSettings,
    OPENAI_COMPATIBLE_PROVIDER,
    PROVIDER_BASE_URLS,
    build_system_chat_model_settings,
    create_openai_compatible_chat_model,
    get_supported_llm_providers,
    resolve_base_url,
)


USER_CREDENTIAL_MODE = "user"
PLATFORM_CREDENTIAL_MODE = "platform"


@dataclass(frozen=True)
class EffectiveChatModelConfig:
    """当前请求实际生效的聊天模型配置和凭据来源。"""

    settings: ChatModelSettings
    credential_mode: str


def _as_float(value: float | Decimal) -> float:
    """将数据库 NUMERIC 值标准化为响应可序列化的浮点数。"""
    return float(value)


def _validate_provider(provider: str) -> str:
    """校验并规范化受支持的聊天模型厂商标识。"""
    normalized_provider = provider.strip().lower()
    supported_providers = {*PROVIDER_BASE_URLS, OPENAI_COMPATIBLE_PROVIDER}
    if normalized_provider not in supported_providers:
        raise ValueError(f"不支持的 LLM 厂商：{provider}")

    return normalized_provider


def _ensure_public_host(host: str, port: int | None = None) -> None:
    """校验自定义 LLM 主机只能解析到公网地址。"""
    normalized_host = host.rstrip(".").lower()
    if (
        normalized_host == "localhost"
        or normalized_host.endswith(".localhost")
        or normalized_host.endswith(".local")
    ):
        raise ValueError("用户自定义 LLM_BASE_URL 不能指向本机地址")

    try:
        host_ip = ip_address(normalized_host)
    except ValueError as exc:
        if normalized_host.replace(".", "").isdigit():
            raise ValueError("LLM_BASE_URL 的 IP 地址无效") from exc
    else:
        if not host_ip.is_global:
            raise ValueError("用户自定义 LLM_BASE_URL 不能指向私网地址")
        return

    try:
        resolved_addresses = socket.getaddrinfo(
            normalized_host,
            port or 443,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise ValueError("无法解析用户自定义 LLM_BASE_URL 主机") from exc

    resolved_ips = {
        address[0]
        for *_, address in resolved_addresses
        if address and address[0]
    }
    if not resolved_ips:
        raise ValueError("无法解析用户自定义 LLM_BASE_URL 主机")

    for resolved_ip in resolved_ips:
        try:
            parsed_ip = ip_address(resolved_ip)
        except ValueError as exc:
            raise ValueError("LLM_BASE_URL 解析结果无效") from exc

        if not parsed_ip.is_global:
            raise ValueError("用户自定义 LLM_BASE_URL 不能解析到私网地址")


def _validate_user_base_url(provider: str, base_url: str | None) -> str | None:
    """限制用户自定义地址，避免设置接口成为访问内网的跳板。"""
    if base_url is None:
        resolve_base_url(provider, None)
        return None

    normalized_base_url = resolve_base_url(provider, base_url)
    preset_base_url = PROVIDER_BASE_URLS.get(provider)
    if normalized_base_url == preset_base_url:
        # 预设地址无需存储，后续可随厂商地址变更统一维护。
        return None
    if not ALLOW_USER_CUSTOM_LLM_BASE_URL:
        raise ValueError("当前不允许用户自定义 LLM_BASE_URL")

    parsed_url = urlparse(normalized_base_url)
    host = parsed_url.hostname
    if (
        parsed_url.scheme != "https"
        or parsed_url.username
        or parsed_url.password
        or not host
    ):
        raise ValueError("用户自定义 LLM_BASE_URL 必须是不含凭据的 HTTPS 地址")
    _ensure_public_host(host, parsed_url.port)

    return normalized_base_url


def _serialize_settings(
    settings: ChatModelSettings,
    credential_mode: str,
    has_api_key: bool,
    api_key_hint: str | None = None,
) -> dict[str, Any]:
    """将生效设置转换为不会泄露 API Key 的响应结构。"""
    return {
        "credential_mode": credential_mode,
        "provider": settings.provider,
        "model": settings.model,
        "base_url": resolve_base_url(settings.provider, settings.base_url),
        "has_api_key": has_api_key,
        "api_key_hint": api_key_hint,
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
        "timeout_seconds": settings.timeout_seconds,
        "max_retries": settings.max_retries,
    }


def _build_platform_settings(record: dict[str, Any] | None) -> ChatModelSettings:
    """基于系统默认配置和用户参数覆盖构造平台模式设置。"""
    settings = build_system_chat_model_settings()
    if record is None:
        return settings

    return replace(
        settings,
        temperature=_as_float(record["temperature"]),
        max_tokens=record["max_tokens"],
        timeout_seconds=_as_float(record["timeout_seconds"]),
        max_retries=record["max_retries"],
    )


def _build_user_settings(
    record: dict[str, Any],
    *,
    decrypt_api_key: bool = True,
) -> ChatModelSettings:
    """将用户密文配置转换为可供模型工厂使用的设置。"""
    return ChatModelSettings(
        provider=record["provider"],
        model=record["model"],
        # 读取设置页不需要解密 API Key，避免无谓扩大敏感信息的内存暴露范围。
        api_key=(
            decrypt_secret(record["api_key_ciphertext"])
            if decrypt_api_key
            else ""
        ),
        base_url=record["base_url"],
        temperature=_as_float(record["temperature"]),
        max_tokens=record["max_tokens"],
        timeout_seconds=_as_float(record["timeout_seconds"]),
        max_retries=record["max_retries"],
    )


def _apply_provider_credential(
    record: dict[str, Any],
    credential: dict[str, Any] | None,
) -> dict[str, Any]:
    """优先使用厂商凭据表中的 Key，兼容旧设置表中保留的活动 Key。"""
    if credential is None:
        return record

    return {
        **record,
        "api_key_ciphertext": credential["api_key_ciphertext"],
        "api_key_hint": credential.get("api_key_hint"),
        "encryption_key_version": credential["encryption_key_version"],
    }


def _get_requested_provider(
    current_record: dict[str, Any] | None,
    updates: dict[str, Any],
) -> str | None:
    """从局部更新或当前设置中取得本次要使用的厂商标识。"""
    provider = updates.get(
        "provider",
        current_record.get("provider") if current_record else None,
    )
    return _validate_provider(provider) if provider else None


def _get_provider_credential_for_updates(
    user_id: int,
    current_record: dict[str, Any] | None,
    updates: dict[str, Any],
) -> dict[str, Any] | None:
    """在用户模式下查询本次厂商已有凭据，以便切换时自动复用。"""
    credential_mode = updates.get(
        "credential_mode",
        current_record.get("credential_mode")
        if current_record
        else PLATFORM_CREDENTIAL_MODE,
    )
    provider = _get_requested_provider(current_record, updates)
    if credential_mode != USER_CREDENTIAL_MODE or not provider:
        return None

    return get_user_llm_provider_credential(user_id, provider)


def get_effective_chat_model_settings(user_id: int) -> ChatModelSettings:
    """获取当前用户实际生效的聊天模型设置。"""
    return get_effective_chat_model_config(user_id).settings


def get_effective_chat_model_config(user_id: int) -> EffectiveChatModelConfig:
    """获取当前用户实际生效的聊天模型配置及凭据来源。"""
    record = get_user_llm_settings(user_id)
    if record is None or record["credential_mode"] == PLATFORM_CREDENTIAL_MODE:
        raise ValueError(
            "请先在设置页配置当前账号的聊天模型 API Key 和模型名称"
        )

    credential = get_user_llm_provider_credential(user_id, record["provider"])
    return EffectiveChatModelConfig(
        settings=_build_user_settings(
            _apply_provider_credential(record, credential),
        ),
        credential_mode=USER_CREDENTIAL_MODE,
    )


def get_serialized_user_llm_settings(user_id: int) -> dict[str, Any]:
    """读取当前用户设置，并生成不含敏感信息的响应数据。"""
    record = get_user_llm_settings(user_id)
    if record is None or record["credential_mode"] == PLATFORM_CREDENTIAL_MODE:
        settings = _build_platform_settings(record)
        return _serialize_settings(
            settings,
            USER_CREDENTIAL_MODE,
            False,
        )

    credential = get_user_llm_provider_credential(user_id, record["provider"])
    record = _apply_provider_credential(record, credential)
    settings = _build_user_settings(record, decrypt_api_key=False)
    api_key_hint = record.get("api_key_hint")
    if not api_key_hint and record["api_key_ciphertext"]:
        # 兼容已保存的旧记录：仅在服务端计算脱敏提示，不向前端传输明文。
        api_key_hint = build_secret_hint(
            decrypt_secret(record["api_key_ciphertext"])
        )
    return _serialize_settings(
        settings,
        USER_CREDENTIAL_MODE,
        bool(record["api_key_ciphertext"]),
        api_key_hint,
    )


def get_serialized_user_llm_providers(user_id: int) -> list[dict[str, Any]]:
    """返回厂商目录及当前用户在每个厂商下的凭据保存状态。"""
    credentials_by_provider = {
        row["provider"]: row
        for row in get_user_llm_provider_credentials(user_id)
    }
    providers = []
    for provider in get_supported_llm_providers():
        credential = credentials_by_provider.get(provider["id"])
        providers.append({
            **provider,
            "has_api_key": credential is not None,
            "api_key_hint": (
                credential.get("api_key_hint") if credential else None
            ),
        })

    return providers


def get_saved_provider_models(
    user_id: int,
    provider: str,
) -> list[str]:
    """使用当前用户指定厂商已保存的凭据读取模型列表，不修改活动设置。"""
    normalized_provider = _validate_provider(provider)
    credential = get_user_llm_provider_credential(
        user_id,
        normalized_provider,
    )
    if credential is None:
        raise ValueError("该厂商尚未保存 API Key")

    current_record = get_user_llm_settings(user_id)
    base_url = (
        current_record.get("base_url")
        if current_record
        and current_record.get("provider") == normalized_provider
        else None
    )
    if normalized_provider == OPENAI_COMPATIBLE_PROVIDER and not base_url:
        raise ValueError("自定义兼容服务需要先保存 base_url")

    defaults = build_system_chat_model_settings()
    settings = replace(
        defaults,
        provider=normalized_provider,
        model="",
        api_key=decrypt_secret(credential["api_key_ciphertext"]),
        base_url=base_url,
    )
    return _list_available_models(settings)


def _merge_settings_record(
    current_record: dict[str, Any] | None,
    updates: dict[str, Any],
    *,
    require_model: bool = True,
    clear_missing_model: bool = False,
    provider_credential: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """合并局部更新并生成可直接持久化的用户设置记录。"""
    current_mode = (
        current_record["credential_mode"]
        if current_record is not None
        else PLATFORM_CREDENTIAL_MODE
    )
    credential_mode = updates.get("credential_mode", current_mode)
    system_settings = build_system_chat_model_settings()

    temperature = updates.get(
        "temperature",
        _as_float(current_record["temperature"])
        if current_record is not None
        else system_settings.temperature,
    )
    max_tokens = updates.get(
        "max_tokens",
        current_record["max_tokens"]
        if current_record is not None
        else system_settings.max_tokens,
    )
    timeout_seconds = updates.get(
        "timeout_seconds",
        _as_float(current_record["timeout_seconds"])
        if current_record is not None
        else system_settings.timeout_seconds,
    )
    max_retries = updates.get(
        "max_retries",
        current_record["max_retries"]
        if current_record is not None
        else system_settings.max_retries,
    )

    if credential_mode == PLATFORM_CREDENTIAL_MODE:
        raise ValueError("当前版本需要使用当前账号的 API Key，不能切换平台模式")

    provider = updates.get(
        "provider",
        current_record.get("provider") if current_record else None,
    )
    base_url = updates.get(
        "base_url",
        current_record.get("base_url") if current_record else None,
    )
    if not provider:
        raise ValueError("用户模式必须配置 provider")

    provider = _validate_provider(provider)
    base_url = _validate_user_base_url(provider, base_url)
    current_provider = (
        _validate_provider(current_record["provider"])
        if current_record and current_record.get("provider")
        else None
    )
    # 切换厂商后旧模型名通常无效，不能在测试请求中静默沿用。
    model = updates.get(
        "model",
        "" if clear_missing_model or current_provider != provider else (
            current_record.get("model") if current_record else None
        ),
    )
    normalized_model = model.strip() if model else ""
    if require_model and not normalized_model:
        raise ValueError("用户模式必须配置非空 model")

    if "api_key" in updates:
        api_key_ciphertext = encrypt_secret(updates["api_key"])
        api_key_hint = build_secret_hint(updates["api_key"])
    elif provider_credential is not None:
        api_key_ciphertext = provider_credential["api_key_ciphertext"]
        api_key_hint = provider_credential.get("api_key_hint")
    else:
        api_key_ciphertext = (
            current_record.get("api_key_ciphertext")
            if current_record is not None
            else None
        )
        api_key_hint = (
            current_record.get("api_key_hint")
            if current_record is not None
            else None
        )
    if not api_key_ciphertext:
        raise ValueError("用户模式必须配置 API Key")

    return {
        "credential_mode": USER_CREDENTIAL_MODE,
        "provider": provider,
        "model": normalized_model,
        "base_url": base_url,
        "api_key_ciphertext": api_key_ciphertext,
        "api_key_hint": api_key_hint,
        "encryption_key_version": 1,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timeout_seconds": timeout_seconds,
        "max_retries": max_retries,
    }


def update_user_llm_settings(
    user_id: int,
    updates: dict[str, Any],
) -> dict[str, Any]:
    """更新当前用户设置，并返回不含 API Key 的生效配置。"""
    current_record = get_user_llm_settings(user_id)
    provider_credential = _get_provider_credential_for_updates(
        user_id,
        current_record,
        updates,
    )
    settings_record = _merge_settings_record(
        current_record,
        updates,
        provider_credential=provider_credential,
    )
    if settings_record["credential_mode"] == USER_CREDENTIAL_MODE:
        saved_credential = upsert_user_llm_provider_credential(
            user_id,
            settings_record["provider"],
            settings_record,
        )
        if saved_credential is None:
            raise RuntimeError("保存用户厂商凭据失败")
    saved_record = upsert_user_llm_settings(user_id, settings_record)
    if saved_record is None:
        raise RuntimeError("保存用户模型设置失败")

    return get_serialized_user_llm_settings(user_id)


def check_user_llm_settings(
    user_id: int,
    updates: dict[str, Any],
) -> dict[str, Any]:
    """保存个人模式草稿后测试配置，并返回厂商可见的模型列表。"""
    current_record = get_user_llm_settings(user_id)
    provider_credential = _get_provider_credential_for_updates(
        user_id,
        current_record,
        updates,
    )
    api_key_saved = False
    if updates:
        settings_record = _merge_settings_record(
            current_record,
            updates,
            require_model=False,
            clear_missing_model=True,
            provider_credential=provider_credential,
        )
        if settings_record["credential_mode"] == PLATFORM_CREDENTIAL_MODE:
            settings = _build_platform_settings(settings_record)
        else:
            # 先持久化用户刚填写的 Key；模型列表或模型调用失败时仍可保留草稿。
            saved_credential = upsert_user_llm_provider_credential(
                user_id,
                settings_record["provider"],
                settings_record,
            )
            if saved_credential is None:
                raise RuntimeError("保存用户厂商凭据失败")
            saved_record = upsert_user_llm_settings(user_id, settings_record)
            if saved_record is None:
                raise RuntimeError("保存用户模型设置草稿失败")
            api_key_saved = True
            settings = _build_user_settings(settings_record)
    else:
        settings = get_effective_chat_model_settings(user_id)

    model_list_available = True
    try:
        models = _list_available_models(settings)
    except ValueError:
        raise
    except Exception:
        # 不是每个兼容厂商都实现 /models；已选模型仍可继续完成对话连通性测试。
        model_list_available = False
        models = []

    if not settings.model:
        if not model_list_available:
            raise ValueError("该厂商未返回模型列表，请手动填写模型名称")
        return {
            "message": "模型列表获取成功，请选择一个模型",
            "models": models,
            "model_list_available": True,
            "api_key_saved": api_key_saved,
        }

    model = create_openai_compatible_chat_model(settings)
    # 使用最小请求验证认证、模型名称、地址和流式前的基本连通性。
    model.invoke("请只回复：OK")
    return {
        "message": (
            "模型连接测试成功"
            if model_list_available
            else "模型连接测试成功，但当前厂商未提供模型列表"
        ),
        "models": models,
        "model_list_available": model_list_available,
        "api_key_saved": api_key_saved,
    }


def _list_available_models(settings: ChatModelSettings) -> list[str]:
    """通过 OpenAI 兼容的 /models 接口读取 API Key 可访问的模型 ID。"""
    client = OpenAI(
        api_key=settings.api_key,
        base_url=resolve_base_url(settings.provider, settings.base_url),
        timeout=settings.timeout_seconds,
        max_retries=settings.max_retries,
    )
    try:
        available_models = client.models.list().data
    except AuthenticationError as exc:
        raise ValueError("API Key 无效，请检查后重新输入") from exc
    except PermissionDeniedError as exc:
        raise ValueError("API Key 无权访问该厂商的模型列表") from exc

    model_ids = {model.id for model in available_models if model.id}
    return sorted(model_ids)

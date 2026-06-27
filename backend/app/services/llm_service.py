"""OpenAI 兼容聊天模型的配置与创建服务。"""

from dataclasses import dataclass
from urllib.parse import urlparse

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.core import config


OPENAI_COMPATIBLE_PROVIDER = "openai_compatible"

# 国内厂商的预设仅负责提供 OpenAI 兼容入口；模型名称仍由部署配置决定。
PROVIDER_BASE_URLS = {
    "deepseek": "https://api.deepseek.com/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "kimi": "https://api.moonshot.cn/v1",
    "doubao": "https://ark.cn-beijing.volces.com/api/v3",
    "minimax": "https://api.minimaxi.com/v1",
}

PROVIDER_DISPLAY_NAMES = {
    "deepseek": "DeepSeek",
    "qwen": "通义千问",
    "zhipu": "智谱 GLM",
    "kimi": "Kimi",
    "doubao": "豆包",
    "minimax": "MiniMax",
}


@dataclass(frozen=True)
class ChatModelSettings:
    """创建 OpenAI 兼容聊天模型所需的通用配置。"""

    provider: str
    model: str
    api_key: str
    base_url: str | None
    temperature: float
    max_tokens: int
    timeout_seconds: float
    max_retries: int


def get_supported_llm_providers() -> list[dict[str, object]]:
    """返回供前端展示的厂商预设与自定义地址能力。"""
    providers = [
        {
            "id": provider_id,
            "name": PROVIDER_DISPLAY_NAMES[provider_id],
            "base_url": base_url,
            "requires_base_url": False,
            "enabled": True,
        }
        for provider_id, base_url in PROVIDER_BASE_URLS.items()
    ]
    providers.append(
        {
            "id": OPENAI_COMPATIBLE_PROVIDER,
            "name": "自定义 OpenAI 兼容服务",
            "base_url": None,
            "requires_base_url": True,
            # 自定义地址由用户输入，默认关闭以避免后端被用作 SSRF 跳板。
            "enabled": config.ALLOW_USER_CUSTOM_LLM_BASE_URL,
        }
    )
    return providers


def build_system_chat_model_settings() -> ChatModelSettings:
    """从系统环境变量生成默认聊天模型配置。"""
    provider = config.LLM_PROVIDER
    model = config.LLM_MODEL or (
        "deepseek-v4-flash" if provider == "deepseek" else ""
    )

    return ChatModelSettings(
        provider=provider,
        model=model,
        api_key=config.LLM_API_KEY or "",
        base_url=config.LLM_BASE_URL,
        temperature=config.LLM_TEMPERATURE,
        max_tokens=config.LLM_MAX_TOKENS,
        timeout_seconds=config.LLM_TIMEOUT_SECONDS,
        max_retries=config.LLM_MAX_RETRIES,
    )


def resolve_base_url(provider: str, base_url: str | None) -> str:
    """解析配置地址或厂商预设地址，并验证其为有效 HTTP(S) URL。"""
    normalized_provider = provider.strip().lower()
    resolved_url = base_url or PROVIDER_BASE_URLS.get(normalized_provider)

    if not resolved_url:
        if normalized_provider == OPENAI_COMPATIBLE_PROVIDER:
            raise ValueError("openai_compatible 厂商必须配置 LLM_BASE_URL")
        raise ValueError(f"不支持的 LLM 厂商：{provider}")

    parsed_url = urlparse(resolved_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ValueError("LLM_BASE_URL 必须是有效的 HTTP(S) 地址")

    return resolved_url.rstrip("/")


def create_openai_compatible_chat_model(
    settings: ChatModelSettings,
) -> ChatOpenAI:
    """按通用配置创建支持流式输出的 OpenAI 兼容聊天模型。"""
    if not settings.api_key:
        raise ValueError("缺少环境变量 LLM_API_KEY")
    if not settings.model:
        raise ValueError("缺少环境变量 LLM_MODEL")
    if not 0 <= settings.temperature <= 2:
        raise ValueError("LLM_TEMPERATURE 必须在 0 到 2 之间")
    if settings.max_tokens <= 0:
        raise ValueError("LLM_MAX_TOKENS 必须大于 0")
    if settings.timeout_seconds <= 0:
        raise ValueError("LLM_TIMEOUT_SECONDS 必须大于 0")
    if settings.max_retries < 0:
        raise ValueError("LLM_MAX_RETRIES 不能小于 0")

    base_url = resolve_base_url(settings.provider, settings.base_url)
    # ChatOpenAI 使用 OpenAI 协议，DeepSeek 等兼容厂商仅需替换地址与凭据。
    return ChatOpenAI(
        model=settings.model,
        api_key=SecretStr(settings.api_key),
        base_url=base_url,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        timeout=settings.timeout_seconds,
        max_retries=settings.max_retries,
        streaming=True,
        stream_usage=True,
    )


def create_system_chat_model() -> ChatOpenAI:
    """使用系统环境变量创建默认聊天模型。"""
    return create_openai_compatible_chat_model(
        build_system_chat_model_settings()
    )

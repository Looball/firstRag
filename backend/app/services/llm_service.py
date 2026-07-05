"""OpenAI 兼容聊天模型的配置与创建服务。"""

from dataclasses import dataclass
from urllib.parse import urlparse

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.core import config


OPENAI_COMPATIBLE_PROVIDER = "openai_compatible"

# 国内厂商的预设仅负责提供 OpenAI 兼容入口；模型名称和 API Key 由用户登录后配置。
PROVIDER_BASE_URLS = {
    "deepseek": "https://api.deepseek.com/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "kimi": "https://api.moonshot.cn/v1",
    "doubao": "https://ark.cn-beijing.volces.com/api/v3",
    "minimax": "https://api.minimaxi.com/v1",
}

DEFAULT_LLM_PROVIDER = "deepseek"
DEFAULT_LLM_MODEL = "deepseek-v4-flash"

PROVIDER_DISPLAY_NAMES = {
    "deepseek": "DeepSeek",
    "qwen": "通义千问",
    "zhipu": "智谱 GLM",
    "kimi": "Kimi",
    "doubao": "豆包",
    "minimax": "MiniMax",
}

VISION_MODEL_KEYWORDS = (
    "vision",
    "visual",
    "vl",
    "qvq",
    "omni",
    "gpt-4o",
    "gpt-4.1",
    "gpt-4-turbo",
    "o3",
    "o4",
    "glm-4v",
    "glm-4.1v",
    "doubao-vision",
    "moonshot-v1-vision",
)


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
    """生成设置页默认聊天模型参数，不携带环境变量 API Key。"""
    return ChatModelSettings(
        provider=DEFAULT_LLM_PROVIDER,
        model=DEFAULT_LLM_MODEL,
        api_key="",
        base_url=None,
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
        raise ValueError("缺少当前用户的聊天模型 API Key")
    if not settings.model:
        raise ValueError("缺少当前用户的聊天模型名称")
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


def chat_model_supports_images(provider: str, model: str) -> bool:
    """根据 provider/model 名称保守判断当前聊天模型是否支持图片输入。"""
    normalized_provider = provider.strip().lower()
    normalized_model = model.strip().lower()
    if normalized_provider == OPENAI_COMPATIBLE_PROVIDER:
        return any(keyword in normalized_model for keyword in VISION_MODEL_KEYWORDS)
    if normalized_provider == "qwen":
        return any(
            keyword in normalized_model
            for keyword in ("vl", "qvq", "omni")
        )
    if normalized_provider == "zhipu":
        return "glm" in normalized_model and "v" in normalized_model
    if normalized_provider == "doubao":
        return "vision" in normalized_model or "multimodal" in normalized_model
    if normalized_provider == "kimi":
        return "vision" in normalized_model
    if normalized_provider == "minimax":
        return "vision" in normalized_model or "image" in normalized_model
    return any(keyword in normalized_model for keyword in VISION_MODEL_KEYWORDS)


def create_system_chat_model() -> ChatOpenAI:
    """使用系统环境变量创建默认聊天模型。"""
    return create_openai_compatible_chat_model(
        build_system_chat_model_settings()
    )

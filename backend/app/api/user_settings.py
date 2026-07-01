"""用户聊天模型设置接口。"""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.config import (
    API_RATE_LIMIT_WINDOW_SECONDS,
    MODEL_TEST_RATE_LIMIT_MAX_REQUESTS,
)
from app.core.rate_limit import build_rate_limit_identifier, enforce_rate_limit
from app.core.sensitive_data import sanitize_sensitive_text
from app.core.security import get_current_user_id
from app.schemas.user_settings import UpdateUserLLMSettingsRequest
from app.services.user_settings_service import (
    check_user_llm_settings,
    get_saved_provider_models,
    get_serialized_user_llm_settings,
    get_serialized_user_llm_providers,
    update_user_llm_settings,
)


router = APIRouter(prefix="/user", tags=["user-settings"])


def _sanitize_settings_error(
    exc: ValueError,
    api_key: str | None = None,
) -> str:
    """返回不会泄露用户 API Key 的设置错误信息。"""
    return sanitize_sensitive_text(str(exc), [api_key])


@router.get("/settings/providers")
def get_user_settings_providers(
    user_id: int = Depends(get_current_user_id),
):
    """返回可供当前用户选择的模型厂商预设。"""
    return {
        "success": True,
        "providers": get_serialized_user_llm_providers(user_id),
    }


@router.post("/settings/providers/{provider}/models")
def get_provider_models(
    request: Request,
    provider: str,
    user_id: int = Depends(get_current_user_id),
):
    """读取指定厂商已保存 Key 可访问的模型列表，不修改当前设置。"""
    enforce_rate_limit(
        "model-test",
        build_rate_limit_identifier(request, "user", user_id),
        MODEL_TEST_RATE_LIMIT_MAX_REQUESTS,
        API_RATE_LIMIT_WINDOW_SECONDS,
        "模型配置测试过于频繁，请稍后再试。",
    )

    try:
        models = get_saved_provider_models(user_id, provider)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=_sanitize_settings_error(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="获取厂商模型列表失败，请检查 API Key 和网络",
        ) from exc

    return {"success": True, "provider": provider, "models": models}


@router.get("/settings")
def get_user_settings(
    user_id: int = Depends(get_current_user_id),
):
    """获取当前用户的聊天模型设置，不返回 API Key 明文。"""
    try:
        settings = get_serialized_user_llm_settings(user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=_sanitize_settings_error(exc),
        ) from exc

    return {"success": True, "settings": settings}


@router.patch("/settings")
def patch_user_settings(
    req: UpdateUserLLMSettingsRequest,
    user_id: int = Depends(get_current_user_id),
):
    """局部更新当前用户的聊天模型设置。"""
    try:
        settings = update_user_llm_settings(
            user_id,
            req.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=_sanitize_settings_error(exc, req.api_key),
        ) from exc

    return {"success": True, "settings": settings}


@router.post("/settings/test")
def test_user_settings(
    request: Request,
    req: UpdateUserLLMSettingsRequest | None = None,
    user_id: int = Depends(get_current_user_id),
):
    """测试已保存或临时提交的模型设置，不会保存临时配置。"""
    enforce_rate_limit(
        "model-test",
        build_rate_limit_identifier(request, "user", user_id),
        MODEL_TEST_RATE_LIMIT_MAX_REQUESTS,
        API_RATE_LIMIT_WINDOW_SECONDS,
        "模型配置测试过于频繁，请稍后再试。",
    )

    try:
        test_result = check_user_llm_settings(
            user_id,
            req.model_dump(exclude_unset=True) if req else {},
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=_sanitize_settings_error(
                exc,
                req.api_key if req else None,
            ),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="模型连接测试失败，请检查模型配置和 API Key",
        ) from exc

    return {"success": True, **test_result}

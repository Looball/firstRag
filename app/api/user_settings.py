"""用户聊天模型设置接口。"""

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user_id
from app.schemas.user_settings import UpdateUserLLMSettingsRequest
from app.services.user_settings_service import (
    get_saved_provider_models,
    get_serialized_user_llm_settings,
    get_serialized_user_llm_providers,
    test_user_llm_settings,
    update_user_llm_settings,
)


router = APIRouter(prefix="/user", tags=["user-settings"])


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
    provider: str,
    user_id: int = Depends(get_current_user_id),
):
    """读取指定厂商已保存 Key 可访问的模型列表，不修改当前设置。"""
    try:
        models = get_saved_provider_models(user_id, provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"success": True, "settings": settings}


@router.post("/settings/test")
def test_user_settings(
    req: UpdateUserLLMSettingsRequest | None = None,
    user_id: int = Depends(get_current_user_id),
):
    """测试已保存或临时提交的模型设置，不会保存临时配置。"""
    try:
        test_result = test_user_llm_settings(
            user_id,
            req.model_dump(exclude_unset=True) if req else {},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="模型连接测试失败，请检查模型配置和 API Key",
        ) from exc

    return {"success": True, **test_result}

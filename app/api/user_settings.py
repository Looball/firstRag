"""用户聊天模型设置接口。"""

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user_id
from app.schemas.user_settings import UpdateUserLLMSettingsRequest
from app.services.user_settings_service import (
    get_serialized_user_llm_settings,
    test_user_llm_settings,
    update_user_llm_settings,
)


router = APIRouter(prefix="/user", tags=["user-settings"])


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
        test_user_llm_settings(
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

    return {"success": True, "message": "模型连接测试成功"}

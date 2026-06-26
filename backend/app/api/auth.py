from fastapi import APIRouter, HTTPException
from pwdlib import PasswordHash

from app.core.security import create_access_token
from app.repositories.auth_repository import (
    create_user_with_default_knowledge_base,
    get_user_by_username,
)
from app.schemas.auth import LoginRequest, RegisterRequest


router = APIRouter(tags=["auth"])


# 注册界面'/register'接口处理
@router.post("/register")
def register(req: RegisterRequest):
    # 使用hash算法加密密码
    password_hash = PasswordHash.recommended().hash(req.password)

    # 向数据库中插入注册用户的信息，并为用户注册默认知识库
    user = create_user_with_default_knowledge_base(
        req.username,
        password_hash,
    )
    # 检查是否注册成功
    if user is None:
        raise HTTPException(status_code=500, detail="注册失败")

    # 生成token
    token = create_access_token(
        user_id=user["user_id"],
        username=user["username"],
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": dict(user),
    }


# 登录界面接口
@router.post("/login")
def login(req: LoginRequest):
    """
    前端POST的数据格式：
    {username: "monkey", password: "123456"}
    """
    # 用户名不能为空
    if not req.username:
        raise HTTPException(status_code=400, detail="用户名不能为空")

    # 密码不能为空
    if not req.password:
        raise HTTPException(status_code=400, detail="密码不能为空")

    # 从数据库中查询id、username、password_hash
    user = get_user_by_username(req.username)
    # 判断是否存在用户
    if user is None:
        raise HTTPException(status_code=401, detail="用户或密码错误")

    stored_hash = user.get("password_hash")

    # 查到用户，但是没有密码
    if not stored_hash:
        raise HTTPException(status_code=401, detail="用户或密码错误")

    # 创建hash对象并进行密码校验
    try:
        password_valid = PasswordHash.recommended().verify(
            req.password,
            stored_hash,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=401,
            detail="用户名或密码错误",
        ) from exc

    # 密码不正确
    if not password_valid:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 生成token
    token = create_access_token(
        user_id=user["id"],
        username=user["username"],
    )
    return {
        "success": True,
        "message": "登录成功",
        "user": {
            "id": user["id"],
            "username": user["username"],
        },
        "access_token": token,
        "token_type": "bearer",
    }

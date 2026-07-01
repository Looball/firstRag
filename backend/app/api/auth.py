from fastapi import APIRouter, HTTPException, Request
from pwdlib import PasswordHash

from app.core.config import (
    LOGIN_FAILURE_RATE_LIMIT_MAX_ATTEMPTS,
    LOGIN_FAILURE_RATE_LIMIT_WINDOW_SECONDS,
)
from app.core.rate_limit import (
    RateLimitExceededError,
    assert_rate_limit_available,
    build_rate_limit_identifier,
    clear_rate_limit,
    consume_rate_limit,
)
from app.core.security import create_access_token
from app.repositories.auth_repository import (
    create_user_with_default_knowledge_base,
    get_user_by_username,
)
from app.schemas.auth import LoginRequest, RegisterRequest


router = APIRouter(tags=["auth"])
LOGIN_FAILURE_RATE_LIMIT_SCOPE = "login-failures"


def _raise_invalid_login(
    rate_limit_identifier: str,
    detail: str = "用户名或密码错误",
) -> None:
    """记录一次失败登录并返回统一认证错误。"""
    try:
        consume_rate_limit(
            LOGIN_FAILURE_RATE_LIMIT_SCOPE,
            rate_limit_identifier,
            LOGIN_FAILURE_RATE_LIMIT_MAX_ATTEMPTS,
            LOGIN_FAILURE_RATE_LIMIT_WINDOW_SECONDS,
        )
    except RateLimitExceededError as exc:
        raise HTTPException(
            status_code=429,
            detail="登录失败次数过多，请稍后再试。",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    raise HTTPException(status_code=401, detail=detail)


def _enforce_login_failure_limit(rate_limit_identifier: str) -> None:
    """在校验密码前阻断已超过失败次数的登录尝试。"""
    try:
        assert_rate_limit_available(
            LOGIN_FAILURE_RATE_LIMIT_SCOPE,
            rate_limit_identifier,
            LOGIN_FAILURE_RATE_LIMIT_MAX_ATTEMPTS,
            LOGIN_FAILURE_RATE_LIMIT_WINDOW_SECONDS,
        )
    except RateLimitExceededError as exc:
        raise HTTPException(
            status_code=429,
            detail="登录失败次数过多，请稍后再试。",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc


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
def login(request: Request, req: LoginRequest):
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

    normalized_username = req.username.strip().lower()
    rate_limit_identifier = build_rate_limit_identifier(
        request,
        normalized_username,
    )
    _enforce_login_failure_limit(rate_limit_identifier)

    # 从数据库中查询id、username、password_hash
    user = get_user_by_username(req.username)
    # 判断是否存在用户
    if user is None:
        _raise_invalid_login(rate_limit_identifier)

    stored_hash = user.get("password_hash")

    # 查到用户，但是没有密码
    if not stored_hash:
        _raise_invalid_login(rate_limit_identifier)

    # 创建hash对象并进行密码校验
    try:
        password_valid = PasswordHash.recommended().verify(
            req.password,
            stored_hash,
        )
    except Exception as exc:
        try:
            _raise_invalid_login(rate_limit_identifier)
        except HTTPException as http_exc:
            raise http_exc from exc

    # 密码不正确
    if not password_valid:
        _raise_invalid_login(rate_limit_identifier)

    clear_rate_limit(LOGIN_FAILURE_RATE_LIMIT_SCOPE, rate_limit_identifier)

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

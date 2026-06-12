from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Header, HTTPException

from app.core.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
)


def create_access_token(user_id: int, username: str) -> str:
    if not JWT_SECRET_KEY:
        raise RuntimeError("缺少环境变量 JWT_SECRET_KEY")

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    if not JWT_SECRET_KEY:
        raise RuntimeError("缺少环境变量 JWT_SECRET_KEY")

    try:
        return jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="登录已过期") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="无效 token") from exc


def get_current_user_payload(authorization: str = Header(...)) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="认证格式错误")

    token = authorization.removeprefix("Bearer ").strip()
    return decode_access_token(token)


def get_current_user_id(authorization: str = Header(...)) -> int:
    payload = get_current_user_payload(authorization)
    return int(payload["sub"])

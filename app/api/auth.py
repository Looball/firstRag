from fastapi import APIRouter, HTTPException
from pwdlib import PasswordHash

from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, RegisterRequest
from SqlStatement.query import exe_sql


router = APIRouter(tags=["auth"])


@router.post("/register")
def register(req: RegisterRequest):
    password_hash = PasswordHash.recommended().hash(req.password)
    sql = """
    WITH new_user AS (
        INSERT INTO users (username, password_hash)
        VALUES (%s, %s)
        RETURNING id, username, created_at
    ),
    new_knowledge_base AS (
        INSERT INTO knowledge_bases (user_id, name, is_default)
        SELECT id, '默认知识库', TRUE
        FROM new_user
        RETURNING id, user_id, name, is_default, created_at
    )
    SELECT
        new_user.id AS user_id,
        new_user.username,
        new_knowledge_base.id AS knowledge_base_id,
        new_knowledge_base.name AS knowledge_base_name
    FROM new_user
    JOIN new_knowledge_base
      ON new_knowledge_base.user_id = new_user.id
    """
    rows = exe_sql(
        sql_statement=sql,
        args_tuple=(req.username, password_hash),
    )
    if not rows:
        raise HTTPException(status_code=500, detail="注册失败")

    user = rows[0]
    token = create_access_token(
        user_id=user["user_id"],
        username=user["username"],
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": dict(user),
    }


@router.post("/login")
def login(req: LoginRequest):
    if not req.username:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    if not req.password:
        raise HTTPException(status_code=400, detail="密码不能为空")

    rows = exe_sql(
        sql_statement="""
        SELECT u.id, u.username, u.password_hash
        FROM users AS u
        WHERE u.username = %s
        """,
        args_tuple=(req.username,),
    )
    if not rows:
        raise HTTPException(status_code=401, detail="用户或密码错误")

    user = rows[0]
    stored_hash = user.get("password_hash")
    if not stored_hash:
        raise HTTPException(status_code=401, detail="用户或密码错误")

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

    if not password_valid:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

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

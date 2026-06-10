from pydantic import BaseModel, Field
from typing import Annotated,Literal,List
from fastapi import FastAPI, File, Form, UploadFile, HTTPException,Header
from fastapi.responses import StreamingResponse

import jwt,os
from pwdlib import PasswordHash
from datetime import datetime, timedelta, timezone

# 从当前RAG项目文件导入
from assistant import get_chain,get_answer

# SqlStatement
from SqlStatement.query import exe_sql

# ***********************************************************************************
# ——————————————————————————!!! JWT TOKEN 处理 BEGIN !!!———————————————————————————— #
# —————————————————————————————————————————————————————————————————————————————————— #
# 设置JWT配置信息，环境变量中需要有 JWT_SECRET_KEY
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

# 生成token
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

# 解析token，验证token
def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="登录已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效 token")

# 从token中获取payload user_id
def get_current_user_payload(authorization: str = Header(...)) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="认证格式错误")

    token = authorization.removeprefix("Bearer ").strip()
    return decode_access_token(token)
# ——————————————————————————————————————————————————————————————————————————————— #
# ——————————————————————————!!! JWT TOKEN 处理 END !!!———————————————————————————— #
# ***********************************************************************************

app = FastAPI()

# ***********************************************************************************
# ———————————————————!!! 注册界面'/register'接口处理 BEGIN !!!————————————————————————— #
# —————————————————————————————————————————————————————————————————————————————————— #
# 定义用户注册提交的数据类型
class RegisterQuest(BaseModel):
    username: str
    password: str

@app.post('/register')
def register(req:RegisterQuest):

    # 使用hash算法加密密码
    password_hash = PasswordHash.recommended().hash(req.password)

    # 向数据库中插入注册用户的信息
    sql = """
        insert into users (username,password_hash)
        values (%s,%s)
        RETURNING id,username
    """
    res = exe_sql(sql_statement=sql,args_tuple=(req.username,password_hash))
    user = res[0]

    # 生成token
    token = create_access_token(
        user_id=user['id'], username=user['username']
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": dict(user)
    }
# —————————————————————————————————————————————————————————————————————————————————— #
# ———————————————————!!! 注册界面'/register'接口处理 END !!!————————————————————————— #
# ***********************************************************************************


# ***********************************************************************************
# ———————————————————!!! 登录界面'/login'接口处理 BEGIN !!!———————————————————————————— #
# —————————————————————————————————————————————————————————————————————————————————— #
# 定义POST '/login' 请求体数据结构
class Account(BaseModel):
    username: str
    password: str

# 登录界面接口
@app.post('/login')
def login(req:Account):
    """
    前端POST的数据格式
    {username: "monkey", password: "123456"}
    :param req: 请求体
    """

    # 用户名不能为空
    if not req.username:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    username = req.username

    # 密码不能为空
    if not req.password:
        raise HTTPException(status_code=400, detail="密码不能为空")
    password = req.password

    # 从数据库中查询 id username password_hash
    sql = f"""
            SELECT u.id, u.username, u.password_hash
            FROM users AS u
            WHERE u.username = %s
            """
    rows = exe_sql(sql_statement=sql,args_tuple=(username,))
    if not rows:
        raise HTTPException(status_code=401, detail="用户不存在")

    # 取出用户信息，只有一条数据
    user = rows[0]

    # 密码校验 hash比对
    if not PasswordHash.recommended().verify(password,user['password_hash']):
        raise HTTPException(status_code=401, detail="密码错误")

    # 生成token
    token = create_access_token(
        user_id=user['id'], username=user['username']
    )

    return {
        "success": True,
        "message": "登录成功",
        "user": {
            "id": user["id"],
            "username": user["username"],
        },
        "access_token": token,
        "token_type": "bearer"
    }
# ————————————————————————————————————————————————————————————————————————————————— #
# ———————————————————!!! 登录界面'/login'接口处理 END !!!————————————————————————————— #
# ***********************************************************************************

# ***********************************************************************************
# —————————————!!! 聊天界面 发送消息 '/chat' 接口处理 BEGIN !!!————————————————————————— #
# —————————————————————————————————————————————————————————————————————————————————— #
# 定义Message消息类型
class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str

# 定义chat请求类型
class ChatRequest(BaseModel):
    conversation_id: str
    message: str

# 定义存储聊天消息的函数
def save_message(conversation_id: str, role: str, content: str):
    sql = """
    INSERT INTO messages (conversation_id, role, content)
    VALUES (%s, %s, %s)
    RETURNING id;
    """
    exe_sql(sql_statement=sql,args_tuple=(conversation_id, role, content))

# 返回answer 流式消息生成器，在生成器迭代完后，将answer保存到 message表
def stream_answer_and_save(chain, user_input: str, history: list, conversation_id: str):
    full_answer = ""

    for chunk in get_answer(chain, user_input, history):
        full_answer += chunk
        yield chunk

    save_message(conversation_id, "assistant", full_answer)

# 将聊天历史转话语 langchain能够处理的格式 元组列表
def load_chat_history(conversation_id: str) -> list[tuple[str, str]]:
    sql = """
    SELECT role, content
    FROM messages
    WHERE conversation_id = %s
    ORDER BY created_at ASC, id ASC;
    """
    rows = exe_sql(sql_statement=sql, args_tuple=(conversation_id,))

    role_map = {
        "user": "human",
        "assistant": "ai",
    }

    return [
        (role_map[row["role"]], row["content"])
        for row in rows
        if row["role"] in role_map
    ]

# 请求聊天接口
@app.post("/chat")
def chat(
        req:ChatRequest,
        authorization: str = Header(...)
) -> StreamingResponse:

    # 解析验证token，获取user_id
    payload = get_current_user_payload(authorization)
    user_id = int(payload['sub'])

    # 取出请求体中的数据
    conversation_id = req.conversation_id
    message = req.message

    if not message:
        raise HTTPException(status_code=400, detail="message不能为空")

    sql = """
            select id
            from conversations
            where user_id = %s and id = %s
        """

    conversation_exist = exe_sql(sql_statement=sql,args_tuple=(user_id,conversation_id))

    if not conversation_exist:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 取出历史记录
    history = load_chat_history(conversation_id)

    # 保存用户输入
    save_message(conversation_id, "user", message)

    # 创建检索链
    chain = get_chain()

    # 返回流式响应
    return StreamingResponse(
        stream_answer_and_save(
            chain=chain,
            user_input=message,
            history=history,
            conversation_id=conversation_id,
        ),
        media_type="text/plain; charset=utf-8"
    )
# ————————————————————————————————————————————————————————————————————————————————— #
# —————————————!!! 聊天界面 发送消息 '/chat' 接口处理 END !!!—————————————————————————— #
# ***********************************************************************************


# ***********************************************************************************
# ————!!! 聊天界面 加载当前用户全部会话 GET '/chat/conversations' 接口处理 BEGIN !!!—————— #
# —————————————————————————————————————————————————————————————————————————————————— #
@app.get('/chat/conversations')
def get_conversations(authorization: str = Header(...)):
    """
    返回的数据结构
    {
    "success": true,
    "conversations": [{
      "id": "会话UUID",
      "title": "会话标题",
      "messages": [
        {"role": "user","content": "你好"},
        {"role": "assistant","content": "你好，有什么可以帮你？"}]
    }]
    }
    :param authorization:
    :return:
    """

    # 获取payload，并解析id
    payload = get_current_user_payload(authorization)
    user_id = int(payload['sub'])

    # 查询数据
    sql = """
    SELECT
        c.id AS conversation_id,
        c.title,
        c.created_at AS conversation_created_at,
        c.updated_at AS conversation_updated_at,
        m.id AS message_id,
        m.role,
        m.content,
        m.created_at AS message_created_at
    FROM conversations AS c
    LEFT JOIN messages AS m
        ON m.conversation_id = c.id
    WHERE c.user_id = %s
    ORDER BY c.updated_at DESC, m.created_at ASC, m.id ASC;
    """
    rows = exe_sql(sql_statement=sql,args_tuple=(user_id,))

    # 组建返回体消息
    conversations = {}
    for row in rows:
        # 获取会话id
        conversation_id = row['conversation_id']
        # 第一次检查，
        if conversation_id not in conversations:
            conversations[conversation_id] = {
                "id": conversation_id,
                "title": row["title"],
                "created_at": row["conversation_created_at"],
                "updated_at": row["conversation_updated_at"],
                "messages": [],
            }

        # 将消息添加到"messages"
        if row["message_id"] is not None:
            conversations[conversation_id]['messages'].append({
                "id": row["message_id"],
                "role": row["role"],
                "content": row["content"],
                "created_at": row["message_created_at"],
            })

    # 返回数据
    return {
        "success": True,
        "conversations": list(conversations.values()),
    }


# ***********************************************************************************
# ————!!! 聊天界面 加载当前用户全部会话 GET '/chat/conversations' 接口处理 END !!!———————— #
# —————————————————————————————————————————————————————————————————————————————————— #


# ***********************************************************************************
# ——————!!! 聊天界面 新建会话 POST '/chat/conversation' 接口处理 BEGIN !!!——————————————— #
# —————————————————————————————————————————————————————————————————————————————————— #
class CreateConversationRequest(BaseModel):
    title: str | None = '新会话'

@app.post('/chat/conversation')
def create_conservation(
        req:CreateConversationRequest,
        authorization: str = Header(...)
):
    payload = get_current_user_payload(authorization)

    user_id = int(payload['sub'])
    title = req.title

    sql = """
        INSERT INTO conversations (user_id, title)
        VALUES (%s, %s)
        RETURNING id, user_id, title, created_at, updated_at;
        """
    rows = exe_sql(sql_statement=sql, args_tuple=(user_id, title))
    conversion = rows[0]

    return {
        "success": True,
        "message": "会话创建成功",
        "conversation": dict(conversion),
    }
# —————————————————————————————————————————————————————————————————————————————————— #
# ———————!!! 聊天界面 新建会话 POST '/chat/conversation' 接口处理 END !!!———————————————— #


# 上传文件接口
@app.post("/update")
async def update_file(
    file: Annotated[bytes, File()],
    fileb: Annotated[UploadFile, File()],
    token: Annotated[str, Form()],
):
    return {
        "file_size": len(file),
        "token": token,
        "fileb_content_type": fileb.content_type,
    }

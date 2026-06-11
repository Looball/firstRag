from pydantic import BaseModel, Field
from typing import Annotated,Literal,List
from fastapi import FastAPI, File, Form, UploadFile, HTTPException,Header
from fastapi.responses import StreamingResponse

from uuid import UUID,uuid4
import hashlib # 计算文件hash
import jwt,os # 生成token令牌
from pathlib import Path # 拼接路径工具
from pwdlib import PasswordHash
from datetime import datetime, timedelta, timezone

# 从当前RAG项目文件导入
from assistant import get_chain,get_answer

# SqlStatement
from SqlStatement.query import exe_sql


# 设置文件存储路径
UPLOAD_ROOT = Path("./uploads")

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

    # # 向数据库中插入注册用户的信息
    # sql = """
    #     insert into users (username,password_hash)
    #     values (%s,%s)
    #     RETURNING id,username
    # """
    # res = exe_sql(sql_statement=sql,args_tuple=(req.username,password_hash))
    # user = res[0]

    # 向数据库中插入注册用户的信息，并为用户注册默认知识库
    # 使用Common Table Expression # 公共表表达式
    cmt_sql = """
    WITH new_user AS (
    INSERT INTO users (
        username,
        password_hash
    )
    VALUES (%s, %s)
    RETURNING id, username, created_at
    ),
    new_knowledge_base AS (
    INSERT INTO knowledge_bases (
        user_id,
        name,
        is_default
    )
    SELECT
        id,
        '默认知识库',
        TRUE
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
    rows = exe_sql(sql_statement=cmt_sql,args_tuple=(req.username,password_hash))

    # 检查是否注册成功
    if not rows:
        raise HTTPException(status_code=500, detail="注册失败")

    # 取出数据
    user = rows[0]

    # 生成token
    token = create_access_token(
        user_id=user['user_id'], username=user['username']
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

    # 判断是否存在用户
    if not rows:
        raise HTTPException(status_code=401, detail="用户或密码错误")

    # 取出用户信息，只有一条数据
    user = rows[0]
    stored_hash = user.get("password_hash")

    # 查到用户，但是没有密码
    if not stored_hash:
        raise HTTPException(status_code=401, detail="用户或密码错误")

    # 创建hash对象
    password_hash = PasswordHash.recommended()

    # 密码校验 hash比对
    try:
        password_valid = password_hash.verify(
            password,
            stored_hash
        )
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="用户名或密码错误"
        )

    # 密码不正确
    if not password_valid:
        raise HTTPException(
            status_code=401,
            detail="用户名或密码错误"
        )

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
    WHERE c.user_id = %s and c.deleted_at is null
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

# —————————————————————————————————————————————————————————————————————————————————— #
# 会话重命名功能
class RenameConversationRequest(BaseModel):
    title:str

@app.patch('/chat/conversation/{conversation_id}')
def rename_conversation(
        conversation_id: UUID,
        req:RenameConversationRequest,
        authorization: str = Header(...)):

    # 获取重命名后的title
    title = req.title

    # 获取payload，并解析id
    payload = get_current_user_payload(authorization)
    user_id = int(payload['sub'])

    # 更新数据库数据
    sql = """
    update conversations
    set title = %s,
        updated_at = now()
    where id = %s and user_id = %s
    RETURNING id, user_id, title, created_at, updated_at;
    """
    rows = exe_sql(sql_statement=sql, args_tuple=(title,conversation_id,user_id))
    if not rows:
        raise HTTPException(status_code=404, detail="会话不存在")

    return {
        "success": True,
        "conversation": dict(rows[0]),
    }

# ——————————————————————————————————————————————————————————————————————————————————— #
@app.delete('/chat/conversation/{conversation_id}')
def delete_conversation(
        conversation_id:UUID,
        authorization: str = Header(...)
):

    # 获取payload，并解析id
    payload = get_current_user_payload(authorization)
    user_id = int(payload['sub'])

    # 软删除
    sql = """
    update conversations
    set deleted_at = now(),
        updated_at = now()
    where id = %s and user_id = %s and deleted_at IS NULL
    RETURNING id;
    """
    rows = exe_sql(sql_statement=sql,args_tuple=(conversation_id,user_id))

    # 会话是否存在
    if not rows:
        raise HTTPException(
            status_code=404, detail="会话不存在"
        )

    return {
        "success": True,
        "conversation_id": str(conversation_id),
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
# ***********************************************************************************


# ***********************************************************************************
# ————————————!!! 知识库管理 '/chat/knowledge-base' 接口处理 BEGIN !!!——————————————— #
# —————————————————————————————————————————————————————————————————————————————————— #
# 获取用户的知识库
@app.get('/chat/knowledge-bases')
def get_knowledge_bases(
    authorization: str = Header(...)
):

    # 获取用户id
    payload = get_current_user_payload(authorization)
    user_id = int(payload['sub'])

    sql = """
        SELECT
            kb.id,
            kb.name,
            kb.is_default,
            kb.created_at,
            kb.updated_at,
            COUNT(kbf.knowledge_file_id) AS file_count
        FROM knowledge_bases AS kb
        LEFT JOIN knowledge_base_files AS kbf
            ON kbf.knowledge_base_id = kb.id
        WHERE kb.user_id = %s
          AND kb.deleted_at IS NULL
        GROUP BY
            kb.id,
            kb.name,
            kb.is_default,
            kb.created_at,
            kb.updated_at
        ORDER BY
            kb.is_default DESC,
            kb.created_at ASC;
        """
    rows = exe_sql(sql_statement=sql, args_tuple=(user_id,))

    return {
        "success": True,
        "knowledge_bases": [
            {
                "id": str(row["id"]),
                "name": row["name"],
                "is_default": row["is_default"],
                "file_count": row["file_count"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ],
    }


# —————————————————————————————————————————————————————————————————————————————————————— #
# 新建知识库
# 定义请求体数据类型
class CreateKnowledgeBaseRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)

@app.post('/chat/knowledge-base')
def create_knowledge_base(
    req:CreateKnowledgeBaseRequest,
    authorization: str = Header(...)
):

    # 验证token，获取用户id
    payload = get_current_user_payload(authorization)
    user_id = int(payload['sub'])
    name = req.name.strip()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="知识库名称不能为空",
        )

    # 创建知识库
    sql = """
    INSERT INTO knowledge_bases (
        user_id,
        name,
        is_default
    )
    VALUES (%s, %s, FALSE)
    RETURNING
        id,
        name,
        is_default,
        created_at,
        updated_at;
    """
    rows = exe_sql(sql_statement=sql,args_tuple=(user_id,name))

    knowledge_base = rows[0]

    return {
        "success": True,
        "knowledge_base": {
            "id": str(knowledge_base["id"]),
            "name": knowledge_base["name"],
            "is_default": knowledge_base["is_default"],
            "file_count": 0,
            "created_at": knowledge_base["created_at"],
            "updated_at": knowledge_base["updated_at"],
        },
    }




# —————————————————————————————————————————————————————————————————————————————————————— #
# 获取知识库中的文件信息
@app.get('/chat/knowledge-base/{knowledge_base_id}/files')
def get_knowledge_files(
    knowledge_base_id: UUID,
    authorization: str = Header(...)
):
    payload = get_current_user_payload(authorization)
    user_id = int(payload['sub'])

# —————————————————————————————————————————————————————————————————————————————————————— #
# 向知识库上传文件
# 组装文件存储路径
def build_storage_path(
    user_id: int,
    file_id: str,
    file_hash: str,
    original_name: str,
) -> Path:
    extension = Path(original_name).suffix.lower()

    return (
        UPLOAD_ROOT
        / "users"
        / str(user_id)
        / file_hash[:2]
        / file_hash[2:4]
        / file_id
        / f"source{extension}"
    )

# 异步  分批计算单个文件hash值
async def calculate_file_hash(file: UploadFile) -> tuple[str, int]:
    sha256 = hashlib.sha256()
    size_bytes = 0

    while chunk := await file.read(1024 * 1024):
        sha256.update(chunk)
        size_bytes += len(chunk)

    await file.seek(0)
    return sha256.hexdigest(), size_bytes

# API路由
@app.post('/chat/knowledge-base/{knowledge_base_id}/files')
async def upload_knowledge_files(
    knowledge_base_id: UUID,
    files: list[UploadFile] = File(...),
    description: str = Form(""),
    authorization: str = Header(...),
):
    # 解析token，获取用户id
    payload = get_current_user_payload(authorization)
    user_id = int(payload["sub"])

    # 检查知识库存在且属于当前用户
    rows = exe_sql(
        sql_statement="""
        SELECT id
        FROM knowledge_bases
        WHERE id = %s
          AND user_id = %s
          AND deleted_at IS NULL
        """,
        args_tuple=(knowledge_base_id, user_id),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="知识库不存在")

    uploaded_files = []

    # 使用循环处理多个文件
    for file in files:
        # 判断文件名是否存在
        if not file.filename:
            raise HTTPException(status_code=400, detail="文件名不能为空")

        # 计算文件hash值和文件大小
        file_hash, size_bytes = await calculate_file_hash(file)

        # 同一用户上传过相同内容时，复用已有文件，只补充知识库关联。
        existing_files = exe_sql(
            sql_statement="""
            SELECT id, original_name, size_bytes, status
            FROM knowledge_files
            WHERE user_id = %s
              AND file_hash = %s
              AND deleted_at IS NULL
            LIMIT 1;
            """,
            args_tuple=(user_id, file_hash),
        )

        if existing_files:
            existing_file = existing_files[0]

            relation_rows = exe_sql(
                sql_statement="""
                INSERT INTO knowledge_base_files (
                    knowledge_base_id,
                    knowledge_file_id
                )
                VALUES (%s, %s)
                ON CONFLICT (knowledge_base_id, knowledge_file_id)
                DO NOTHING
                RETURNING knowledge_file_id;
                """,
                args_tuple=(knowledge_base_id, existing_file["id"]),
            )

            uploaded_files.append({
                **dict(existing_file),
                "reused": True,
                "already_in_knowledge_base": not bool(relation_rows),
            })
            await file.close()
            continue

        # 为文件生成UUID
        file_id = uuid4()

        # 拼接路径 ROOT_PATH / storage_path
        storage_path = build_storage_path(
            user_id=user_id,
            file_id=str(file_id),
            file_hash=file_hash,
            original_name=file.filename,
        )

        # 创建文件目录
        storage_path.parent.mkdir(parents=True, exist_ok=True)

        # 保存文件，写入本地路径
        try:
            with storage_path.open("wb") as output:
                while chunk := await file.read(1024 * 1024):
                    output.write(chunk)

            # 同时插入文件记录和知识库关联记录
            rows = exe_sql(
                sql_statement="""
                WITH new_file AS (
                    INSERT INTO knowledge_files (
                        id,
                        user_id,
                        original_name,
                        storage_path,
                        mime_type,
                        size_bytes,
                        file_hash,
                        status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
                    RETURNING id, original_name, size_bytes, status
                ),
                new_relation AS (
                    INSERT INTO knowledge_base_files (
                        knowledge_base_id,
                        knowledge_file_id
                    )
                    SELECT %s, id
                    FROM new_file
                )
                SELECT *
                FROM new_file;
                """,
                args_tuple=(
                    file_id,
                    user_id,
                    file.filename,
                    str(storage_path),
                    file.content_type or "application/octet-stream",
                    size_bytes,
                    file_hash,
                    knowledge_base_id,
                ),
            )

            uploaded_files.append(dict(rows[0]))

        except Exception:
            storage_path.unlink(missing_ok=True)
            raise

        finally:
            await file.close()

    return {
        "success": True,
        "description": description,
        "files": uploaded_files,
    }

# —————————————————————————————————————————————————————————————————————————————————————— #
# 解除数据库与文件的关联
@app.delete('/chat/knowledge-base/{knowledge_base_id}/files/{knowledge_file_id}')
def unpacking_knowledge_bases_and_file(
    knowledge_base_id: UUID,
    knowledge_file_id: UUID,
    authorization: str = Header(...)
):

    # 解析token，获取id
    payload = get_current_user_payload(authorization)
    user_id = int(payload['sub'])

    # 解除关联
    sql = """
    DELETE FROM knowledge_base_files AS kbf
    USING knowledge_bases AS kb, knowledge_files AS kf
    WHERE kbf.knowledge_base_id = kb.id
      AND kbf.knowledge_file_id = kf.id
      AND kb.id = %s
      AND kf.id = %s
      AND kb.user_id = %s
      AND kf.user_id = %s
      AND kb.deleted_at IS NULL
      AND kf.deleted_at IS NULL
    RETURNING
        kbf.knowledge_base_id,
        kbf.knowledge_file_id;
    """
    rows = exe_sql(
        sql_statement=sql,
        args_tuple=(
            knowledge_base_id,
            knowledge_file_id,
            user_id,
            user_id
        )
    )
    if not rows:
        raise HTTPException(status_code=404, detail="文件关联不存在")

    return {
        "success": True,
        "knowledge_base_id": str(knowledge_base_id),
        "knowledge_file_id": str(knowledge_file_id),
    }

# —————————————————————————————————————————————————————————————————————————————————————— #
# 获取当前用户下所有知识库文件
@app.get('/chat/knowledge-files')
def get_all_knowledge_files(
    authorization: str = Header(...)
):
    # 解析token，获取用户id
    payload = get_current_user_payload(authorization)
    user_id = int(payload['sub'])

    sql = """
    SELECT id, original_name, size_bytes, status
    FROM knowledge_files
    WHERE user_id = %s 
      AND deleted_at is null
    ORDER BY created_at DESC;
    """
    rows = exe_sql(sql_statement=sql, args_tuple=(user_id,))

    file_list = [ dict(row) for row in rows]

    return {
        "success": True,
        "file_list": file_list
    }


# ***********************************************************************************
# ————————————!!! 知识库管理 '/chat/knowledge-base' 接口处理 END !!!——————————————— #
# —————————————————————————————————————————————————————————————————————————————————— #

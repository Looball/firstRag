from pydantic import BaseModel, Field
from typing import Annotated,Literal,List
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import StreamingResponse

# 从当前项目文件导入
from assistant import get_chain,get_answer

app = FastAPI()

# 定义Message消息类型
class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str

# 定义chat请求类型
class ChatRequest(BaseModel):
    messages: List[Message]
    attachment_context: str = Field(default="", alias="attachmentContext")

# 将聊天历史转话语 langchain能够处理的格式 元组列表
def to_langchain_history(messages: List[Message]) -> list[tuple[str, str]]:
    role_map = {
        "user": "human",
        "assistant": "ai",
    }
    return [(role_map[message.role], message.content) for message in messages]

# 请求聊天接口
@app.post("/chat")
def chat(req:ChatRequest):
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages 不能为空")

    # 取出历史记录
    history = to_langchain_history(req.messages[:-1])
    # 取出用户输入
    user_inputs = req.messages[-1].content
    # 创建检索链
    chain = get_chain()

    return StreamingResponse(
        get_answer(chain,user_inputs,history),
        media_type="text/plain; charset=utf-8",
    )

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

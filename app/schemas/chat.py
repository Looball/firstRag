from pydantic import BaseModel


# 定义chat请求类型
class ChatRequest(BaseModel):
    conversation_id: str
    message: str

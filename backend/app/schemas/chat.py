from uuid import UUID
from pydantic import BaseModel, Field


# 定义chat请求类型
class ChatRequest(BaseModel):
    conversation_id: UUID
    message: str
    knowledge_base_id: UUID
    attachment_ids: list[UUID] = Field(default_factory=list)

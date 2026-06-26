from pydantic import BaseModel
from uuid import UUID

# 会话重命名请求体
class RenameConversationRequest(BaseModel):
    title: str


# 新建会话请求体
class CreateConversationRequest(BaseModel):
    title: str | None = "新会话"

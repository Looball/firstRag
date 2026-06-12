from pydantic import BaseModel


class RenameConversationRequest(BaseModel):
    title: str


class CreateConversationRequest(BaseModel):
    title: str | None = "新会话"

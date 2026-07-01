from typing import Literal

from pydantic import BaseModel, Field
from uuid import UUID

# 会话重命名请求体
class RenameConversationRequest(BaseModel):
    """会话重命名请求。"""

    title: str


# 新建会话请求体
class CreateConversationRequest(BaseModel):
    """新建会话请求。"""

    title: str | None = "新会话"


class LegacyCreateConversationRequest(BaseModel):
    """旧版新建会话请求，允许省略知识库并回退到默认知识库。"""

    knowledge_base_id: UUID | None = None
    title: str | None = "新会话"


class MessageFeedbackRequest(BaseModel):
    """消息质量反馈请求。"""

    rating: Literal["positive", "negative"]
    reason: Literal[
        "irrelevant_sources",
        "missing_answer",
        "hallucination",
        "outdated_or_wrong",
        "too_slow",
        "format_issue",
        "other",
    ] | None = None
    note: str | None = Field(default=None, max_length=1000)


class MessageSourceFeedbackRequest(BaseModel):
    """消息引用来源反馈请求。"""

    rating: Literal["useful", "irrelevant"]
    note: str | None = Field(default=None, max_length=1000)

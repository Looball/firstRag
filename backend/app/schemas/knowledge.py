from pydantic import BaseModel, Field


# 定义新建知识库请求体数据类型
class CreateKnowledgeBaseRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)

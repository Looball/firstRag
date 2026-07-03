"""用户聊天模型设置的请求模型。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UpdateUserLLMSettingsRequest(BaseModel):
    """更新用户聊天模型设置的局部请求。"""

    model_config = ConfigDict(extra="forbid")

    credential_mode: Literal["platform", "user"] | None = None
    provider: str | None = Field(default=None, max_length=50)
    model: str | None = Field(default=None, max_length=200)
    base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, min_length=1, max_length=2000)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, gt=0, le=100_000)
    timeout_seconds: float | None = Field(default=None, gt=0, le=600)
    max_retries: int | None = Field(default=None, ge=0, le=10)


class UpdateUserEmbeddingSettingsRequest(BaseModel):
    """更新用户向量模型设置的局部请求。"""

    model_config = ConfigDict(extra="forbid")

    provider: str | None = Field(default=None, max_length=50)
    model: str | None = Field(default=None, max_length=200)
    base_url: str | None = Field(default=None, max_length=500)
    dimensions: int | None = Field(default=None, ge=1, le=8192)
    api_key: str | None = Field(default=None, min_length=1, max_length=2000)
    timeout_seconds: float | None = Field(default=None, gt=0, le=600)
    max_retries: int | None = Field(default=None, ge=0, le=10)

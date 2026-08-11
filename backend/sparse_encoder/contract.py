"""Sparse encoder 的共享 HTTP contract 与固定模型身份。"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


BGE_M3_MODEL_ID = "BAAI/bge-m3"
BGE_M3_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
SPARSE_CONTRACT_VERSION = 1
EncodeMode = Literal["document", "query"]


class EncodeRequest(BaseModel):
    """批量 sparse encoding 请求。"""

    model_config = ConfigDict(extra="forbid")

    mode: EncodeMode
    texts: list[str] = Field(min_length=1)

    @field_validator("texts")
    @classmethod
    def validate_non_empty_texts(cls, values: list[str]) -> list[str]:
        """拒绝空白文本，避免生成无法审计的空向量。"""
        if any(not value.strip() for value in values):
            raise ValueError("texts 不能包含空文本。")
        return values


class EncodeResponse(BaseModel):
    """Milvus 可直接接收的 sparse vectors 响应。"""

    model_config = ConfigDict(extra="forbid")

    contract_version: int = SPARSE_CONTRACT_VERSION
    model: str
    revision: str
    mode: EncodeMode
    vectors: list[dict[int, float]]

    @field_validator("vectors")
    @classmethod
    def validate_sparse_vectors(
        cls,
        vectors: list[dict[int, float]],
    ) -> list[dict[int, float]]:
        """确保 sparse index 合法且权重有限、非负。"""
        for vector in vectors:
            if not vector:
                raise ValueError("sparse vector 不能为空。")
            for index, weight in vector.items():
                if index < 0:
                    raise ValueError("sparse vector index 不能为负数。")
                if not math.isfinite(weight) or weight < 0:
                    raise ValueError("sparse vector weight 必须有限且非负。")
        return vectors


class HealthResponse(BaseModel):
    """进程、模型加载与真实 inference 健康状态。"""

    status: Literal["live", "loading", "ready", "error"]
    model: str
    revision: str
    runtime: Literal["bge_m3", "fixture"]
    inference_verified: bool
    error_code: str | None = None

"""FirstRAG 内部 BGE-M3 sparse encoder service。"""

from sparse_encoder.contract import (
    BGE_M3_MODEL_ID,
    BGE_M3_REVISION,
    EncodeRequest,
    EncodeResponse,
)

__all__ = [
    "BGE_M3_MODEL_ID",
    "BGE_M3_REVISION",
    "EncodeRequest",
    "EncodeResponse",
]

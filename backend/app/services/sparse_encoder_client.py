"""Backend/worker 共用的内部 sparse encoder HTTP client。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import (
    SPARSE_ENCODER_CLIENT_BATCH_SIZE,
    SPARSE_ENCODER_MODEL,
    SPARSE_ENCODER_REVISION,
    SPARSE_ENCODER_TIMEOUT_SECONDS,
    SPARSE_ENCODER_URL,
)
from sparse_encoder.contract import EncodeMode, EncodeResponse


class SparseEncoderClientError(RuntimeError):
    """表示内部 sparse encoder 不可用或违反 contract。"""


@dataclass(frozen=True)
class SparseEncoderClient:
    """不记录原文的同步内部 HTTP client。"""

    base_url: str = SPARSE_ENCODER_URL
    model: str = SPARSE_ENCODER_MODEL
    revision: str = SPARSE_ENCODER_REVISION
    timeout_seconds: float = SPARSE_ENCODER_TIMEOUT_SECONDS
    batch_size: int = SPARSE_ENCODER_CLIENT_BATCH_SIZE

    def encode_documents(self, texts: list[str]) -> list[dict[int, float]]:
        """为 indexing worker 批量生成 document sparse vectors。"""
        if self.batch_size < 1:
            raise SparseEncoderClientError("Sparse encoder batch size 必须大于 0。")
        vectors: list[dict[int, float]] = []
        for start in range(0, len(texts), self.batch_size):
            vectors.extend(self._encode(
                texts[start:start + self.batch_size],
                mode="document",
            ))
        return vectors

    def encode_query(self, text: str) -> dict[int, float]:
        """为 backend retrieval 生成单条 query sparse vector。"""
        return self._encode([text], mode="query")[0]

    def _encode(
        self,
        texts: list[str],
        *,
        mode: EncodeMode,
    ) -> list[dict[int, float]]:
        """调用内部 contract 并复核模型身份、模式和返回数量。"""
        payload = json.dumps(
            {"mode": mode, "texts": texts},
            ensure_ascii=False,
        ).encode("utf-8")
        request = Request(
            f"{self.base_url.rstrip('/')}/v1/sparse/encode",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                result = EncodeResponse.model_validate_json(response.read())
        except HTTPError as exc:
            raise SparseEncoderClientError(
                f"Sparse encoder 返回 HTTP {exc.code}。"
            ) from exc
        except (URLError, TimeoutError, ValueError) as exc:
            raise SparseEncoderClientError("Sparse encoder 调用失败。") from exc

        if result.model != self.model or result.revision != self.revision:
            raise SparseEncoderClientError("Sparse encoder 模型身份不匹配。")
        if result.mode != mode:
            raise SparseEncoderClientError("Sparse encoder 返回了错误的 encode mode。")
        if len(result.vectors) != len(texts):
            raise SparseEncoderClientError("Sparse encoder 返回数量不匹配。")
        return result.vectors

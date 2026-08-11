"""Sparse encoder runtime 配置读取与约束。"""

from __future__ import annotations

import os
from dataclasses import dataclass

from sparse_encoder.contract import BGE_M3_MODEL_ID, BGE_M3_REVISION


def _read_bool(name: str, default: bool) -> bool:
    """读取严格布尔环境变量。"""
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} 必须是布尔值。")


def _read_positive_int(name: str, default: int) -> int:
    """读取正整数环境变量。"""
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} 必须是正整数。") from exc
    if value <= 0:
        raise ValueError(f"{name} 必须是正整数。")
    return value


def _read_positive_float(name: str, default: float) -> float:
    """读取正浮点环境变量。"""
    try:
        value = float(os.environ.get(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} 必须是正数。") from exc
    if value <= 0:
        raise ValueError(f"{name} 必须是正数。")
    return value


@dataclass(frozen=True)
class SparseEncoderSettings:
    """Sparse encoder service 的受控运行参数。"""

    runtime: str = "bge_m3"
    model_id: str = BGE_M3_MODEL_ID
    revision: str = BGE_M3_REVISION
    cache_dir: str = "/models/huggingface"
    device: str = "cpu"
    use_fp16: bool = False
    offline: bool = False
    batch_size: int = 8
    max_length: int = 1024
    max_batch_size: int = 16
    max_text_characters: int = 20_000
    max_request_bytes: int = 1_048_576
    max_concurrency: int = 1
    request_timeout_seconds: float = 120.0

    def validate(self) -> "SparseEncoderSettings":
        """拒绝会破坏模型身份或资源边界的配置。"""
        if self.runtime not in {"bge_m3", "fixture"}:
            raise ValueError("SPARSE_ENCODER_MODE 必须是 bge_m3 或 fixture。")
        if self.model_id != BGE_M3_MODEL_ID:
            raise ValueError("SPARSE_ENCODER_MODEL 必须固定为 BAAI/bge-m3。")
        if self.revision != BGE_M3_REVISION:
            raise ValueError("SPARSE_ENCODER_REVISION 与冻结 revision 不一致。")
        if self.device != "cpu":
            raise ValueError("当前 sparse encoder 镜像仅支持 CPU runtime。")
        if self.use_fp16:
            raise ValueError("CPU runtime 禁止启用 SPARSE_ENCODER_USE_FP16。")
        for field_name in (
            "batch_size",
            "max_length",
            "max_batch_size",
            "max_text_characters",
            "max_request_bytes",
            "max_concurrency",
        ):
            if int(getattr(self, field_name)) <= 0:
                raise ValueError(f"{field_name} 必须为正整数。")
        if self.request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds 必须为正数。")
        return self

    @classmethod
    def from_env(cls) -> "SparseEncoderSettings":
        """从环境变量创建并校验 service 配置。"""
        return cls(
            runtime=os.environ.get("SPARSE_ENCODER_MODE", "bge_m3").strip(),
            model_id=os.environ.get(
                "SPARSE_ENCODER_MODEL",
                BGE_M3_MODEL_ID,
            ).strip(),
            revision=os.environ.get(
                "SPARSE_ENCODER_REVISION",
                BGE_M3_REVISION,
            ).strip(),
            cache_dir=os.environ.get(
                "SPARSE_ENCODER_CACHE_DIR",
                "/models/huggingface",
            ).strip(),
            device=os.environ.get("SPARSE_ENCODER_DEVICE", "cpu").strip(),
            use_fp16=_read_bool("SPARSE_ENCODER_USE_FP16", False),
            offline=_read_bool("SPARSE_ENCODER_OFFLINE", False),
            batch_size=_read_positive_int("SPARSE_ENCODER_BATCH_SIZE", 8),
            max_length=_read_positive_int("SPARSE_ENCODER_MAX_LENGTH", 1024),
            max_batch_size=_read_positive_int(
                "SPARSE_ENCODER_MAX_BATCH_SIZE",
                16,
            ),
            max_text_characters=_read_positive_int(
                "SPARSE_ENCODER_MAX_TEXT_CHARACTERS",
                20_000,
            ),
            max_request_bytes=_read_positive_int(
                "SPARSE_ENCODER_MAX_REQUEST_BYTES",
                1_048_576,
            ),
            max_concurrency=_read_positive_int(
                "SPARSE_ENCODER_MAX_CONCURRENCY",
                1,
            ),
            request_timeout_seconds=_read_positive_float(
                "SPARSE_ENCODER_REQUEST_TIMEOUT_SECONDS",
                120.0,
            ),
        ).validate()

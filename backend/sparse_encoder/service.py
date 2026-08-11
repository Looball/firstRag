"""只在 Compose 内网暴露的 BGE-M3 sparse encoder HTTP service。"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from sparse_encoder.contract import EncodeRequest, EncodeResponse, HealthResponse
from sparse_encoder.runtime import SparseRuntime, create_runtime
from sparse_encoder.settings import SparseEncoderSettings


logger = logging.getLogger(__name__)


@dataclass
class RuntimeState:
    """保存模型加载状态，不记录任何企业文本。"""

    status: str = "loading"
    inference_verified: bool = False
    error_code: str | None = None


class RuntimeManager:
    """串行管理模型加载与有限并发 inference。"""

    def __init__(
        self,
        settings: SparseEncoderSettings,
        runtime: SparseRuntime,
    ) -> None:
        """初始化状态、并发 gate 和 runtime。"""
        self.settings = settings
        self.runtime = runtime
        self.state = RuntimeState()
        self._semaphore = asyncio.Semaphore(settings.max_concurrency)

    async def load(self) -> None:
        """后台加载模型；load 内的最小 inference 通过后才 ready。"""
        try:
            await asyncio.to_thread(self.runtime.load)
        except Exception:
            self.state.status = "error"
            self.state.error_code = "model_load_failed"
            logger.exception("sparse_encoder_model_load_failed")
            return
        self.state.status = "ready"
        self.state.inference_verified = True
        logger.info(
            "sparse_encoder_ready runtime=%s model=%s revision=%s",
            self.settings.runtime,
            self.settings.model_id,
            self.settings.revision,
        )

    async def encode(self, request: EncodeRequest) -> list[dict[int, float]]:
        """在 queue/inference timeout 内执行单实例受控编码。"""
        if self.state.status != "ready":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Sparse encoder 模型尚未就绪。",
            )

        timeout = self.settings.request_timeout_seconds
        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=timeout)
        except TimeoutError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Sparse encoder 当前繁忙，请稍后重试。",
            ) from exc

        worker = asyncio.create_task(
            asyncio.to_thread(
                self.runtime.encode,
                request.texts,
                mode=request.mode,
            )
        )
        release_immediately = True
        started_at = time.perf_counter()
        try:
            vectors = await asyncio.wait_for(asyncio.shield(worker), timeout=timeout)
        except TimeoutError as exc:
            release_immediately = False
            worker.add_done_callback(lambda _: self._semaphore.release())
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Sparse encoding 超时。",
            ) from exc
        finally:
            if release_immediately:
                self._semaphore.release()

        logger.info(
            "sparse_encoder_request mode=%s batch=%d duration_ms=%.2f",
            request.mode,
            len(request.texts),
            (time.perf_counter() - started_at) * 1000,
        )
        return vectors


def create_app(
    settings: SparseEncoderSettings | None = None,
    runtime: SparseRuntime | None = None,
) -> FastAPI:
    """创建可注入 fixture 的内部 FastAPI application。"""
    resolved_settings = (settings or SparseEncoderSettings.from_env()).validate()
    manager = RuntimeManager(
        resolved_settings,
        runtime or create_runtime(resolved_settings),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """后台加载模型，使 live 与 ready 能明确区分。"""
        load_task = asyncio.create_task(manager.load())
        app.state.load_task = load_task
        try:
            yield
        finally:
            if not load_task.done():
                load_task.cancel()
                with suppress(asyncio.CancelledError):
                    await load_task

    app = FastAPI(
        title="FirstRAG Sparse Encoder",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.runtime_manager = manager

    @app.middleware("http")
    async def limit_request_body(request: Request, call_next):  # type: ignore[no-untyped-def]
        """同时限制 Content-Length 和实际读取到的请求体。"""
        if request.method == "POST":
            raw_length = request.headers.get("content-length")
            if raw_length is not None:
                try:
                    content_length = int(raw_length)
                except ValueError:
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={"detail": "Content-Length 无效。"},
                    )
                if content_length > resolved_settings.max_request_bytes:
                    return JSONResponse(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        content={"detail": "Sparse encoding 请求体过大。"},
                    )
            body = await request.body()
            if len(body) > resolved_settings.max_request_bytes:
                return JSONResponse(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    content={"detail": "Sparse encoding 请求体过大。"},
                )
        return await call_next(request)

    @app.get("/health/live", response_model=HealthResponse)
    async def live() -> HealthResponse:
        """只确认 API 进程仍可响应。"""
        return HealthResponse(
            status="live",
            model=resolved_settings.model_id,
            revision=resolved_settings.revision,
            runtime=resolved_settings.runtime,
            inference_verified=manager.state.inference_verified,
            error_code=manager.state.error_code,
        )

    @app.get("/health/ready", response_model=HealthResponse)
    async def ready() -> HealthResponse:
        """仅在模型加载和最小 sparse inference 均成功后返回 200。"""
        if manager.state.status != "ready":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "status": manager.state.status,
                    "error_code": manager.state.error_code,
                },
            )
        return HealthResponse(
            status="ready",
            model=resolved_settings.model_id,
            revision=resolved_settings.revision,
            runtime=resolved_settings.runtime,
            inference_verified=True,
        )

    @app.post("/v1/sparse/encode", response_model=EncodeResponse)
    async def encode(request: EncodeRequest) -> EncodeResponse:
        """按 document/query 模式批量生成 learned sparse vectors。"""
        if len(request.texts) > resolved_settings.max_batch_size:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="texts 超过 SPARSE_ENCODER_MAX_BATCH_SIZE。",
            )
        if any(
            len(text) > resolved_settings.max_text_characters
            for text in request.texts
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="单条文本超过 SPARSE_ENCODER_MAX_TEXT_CHARACTERS。",
            )
        vectors = await manager.encode(request)
        return EncodeResponse(
            model=resolved_settings.model_id,
            revision=resolved_settings.revision,
            mode=request.mode,
            vectors=vectors,
        )

    return app

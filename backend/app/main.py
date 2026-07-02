import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request

from app.api import (
    auth,
    chat,
    conversations,
    knowledge_bases,
    knowledge_files,
    user_settings,
    vector_indexes,
)
from app.core.observability import (
    log_exception_event,
    log_structured_event,
    reset_request_context,
    set_request_context,
)


http_logger = logging.getLogger("app.observability.http")


def resolve_request_id(request: Request) -> str:
    """读取或生成请求链路标识。"""
    request_id = request.headers.get("X-Request-ID", "").strip()
    if request_id and len(request_id) <= 128:
        return request_id
    return str(uuid4())


def create_app() -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def observability_middleware(request: Request, call_next):
        """记录不含敏感 header/body 的统一 HTTP 请求日志。"""
        request_id = resolve_request_id(request)
        token = set_request_context(request_id=request_id)
        started_at = perf_counter()

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((perf_counter() - started_at) * 1000, 2)
            log_exception_event(
                http_logger,
                "http_request_failed",
                exc,
                default_source="http",
                method=request.method,
                path=request.url.path,
                status_code=500,
                duration_ms=duration_ms,
            )
            reset_request_context(token)
            raise

        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        status_code = response.status_code
        level = logging.INFO
        if status_code >= 500:
            level = logging.ERROR
        elif status_code >= 400:
            level = logging.WARNING
        log_structured_event(
            http_logger,
            level,
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            duration_ms=duration_ms,
        )
        reset_request_context(token)
        return response

    app.include_router(auth.router)
    app.include_router(chat.router)
    app.include_router(conversations.router)
    app.include_router(knowledge_bases.router)
    app.include_router(knowledge_files.router)
    app.include_router(user_settings.router)
    app.include_router(vector_indexes.router)
    return app


app = create_app()

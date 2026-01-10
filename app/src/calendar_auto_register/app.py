"""FastAPI アプリケーションの組み立てを担当するモジュール。"""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from starlette.responses import Response

from .core.logging import log_error
from .core.middleware import api_key_middleware, request_id_middleware
from .core.settings import load_settings
from .features.calendar_events.router_calendar_events import router as calendar_router
from .features.line_notify_post.router_line_notify_post import router as line_router
from .features.llm_extract.router_llm_extract import router as llm_router
from .features.mailparse_post.router_mailparse_post import router as mail_router


def create_app() -> FastAPI:
    """コア設定や共通ミドルウェアを組み込んだ FastAPI アプリを返す。"""

    settings = load_settings()
    log_level = logging.DEBUG if settings.is_local else logging.INFO
    logging.basicConfig(level=log_level, format="%(message)s")
    logging.getLogger("calendar_auto_register").setLevel(log_level)
    app = FastAPI(title="calendar-auto-register", version="0.1.0")
    app.state.settings = settings  # type: ignore[attr-defined]
    app.middleware("http")(api_key_middleware)
    app.middleware("http")(request_id_middleware)

    @app.exception_handler(HTTPException)
    async def http_exception_logger(request: Request, exc: HTTPException) -> Response:
        request_id = getattr(request.state, "request_id", "-")
        started = getattr(request.state, "request_started", None)
        latency_ms = int((time.perf_counter() - started) * 1000) if started else 0
        log_error(
            path=request.url.path,
            status=exc.status_code,
            request_id=request_id,
            latency_ms=latency_ms,
            error=exc.detail,
        )
        return await http_exception_handler(request, exc)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_logger(
        request: Request, exc: RequestValidationError
    ) -> Response:
        request_id = getattr(request.state, "request_id", "-")
        started = getattr(request.state, "request_started", None)
        latency_ms = int((time.perf_counter() - started) * 1000) if started else 0
        log_error(
            path=request.url.path,
            status=422,
            request_id=request_id,
            latency_ms=latency_ms,
            error=exc.errors(),
        )
        return await request_validation_exception_handler(request, exc)

    @app.get("/healthz", tags=["health"])
    def healthz() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    app.include_router(mail_router)
    app.include_router(llm_router)
    app.include_router(calendar_router)
    app.include_router(line_router)

    return app

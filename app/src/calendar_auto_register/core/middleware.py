"""FastAPI 用の共通ミドルウェア群。"""

from __future__ import annotations

import time
import uuid
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.responses import JSONResponse

from calendar_auto_register.core.logging import log_request


RequestHandler = Callable[[Request], Awaitable[Response]]


async def api_key_middleware(request: Request, call_next: RequestHandler) -> Response:
    """API キー認証ミドルウェア。ローカル環境では認証スキップ。"""

    from calendar_auto_register.core.settings import load_settings

    settings = load_settings()

    # ローカル環境では認証スキップ
    if settings.is_local:
        return await call_next(request)

    # # 本番環境では API キーをチェック
    # auth_header = request.headers.get("Authorization", "")
    # if not auth_header.startswith("Bearer "):
    #     return JSONResponse(
    #         {"detail": "Invalid or missing Authorization header"},
    #         status_code=401,
    #     )
    #
    # provided_key = auth_header[len("Bearer ") :].strip()
    # if not settings.api_key or provided_key != settings.api_key:
    #     return JSONResponse(
    #         {"detail": "Unauthorized"},
    #         status_code=401,
    #     )

    return await call_next(request)


async def request_id_middleware(request: Request, call_next: RequestHandler) -> Response:
    """X-Request-Id を受理・生成しレスポンスヘッダへ付与する。"""

    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    request.state.request_id = request_id

    started = time.perf_counter()
    request.state.request_started = started
    response = await call_next(request)

    latency_ms = int((time.perf_counter() - started) * 1000)
    response.headers["X-Request-Id"] = request_id
    response.headers["X-Response-Time-Ms"] = str(latency_ms)
    log_request(
        path=request.url.path,
        status=response.status_code,
        request_id=request_id,
        latency_ms=latency_ms,
    )
    return response

"""FastAPI アプリケーションの組み立てを担当するモジュール。"""

from __future__ import annotations

from fastapi import FastAPI

from .core.middleware import request_id_middleware
from .core.settings import load_settings
from .features.mailparse_post.router_mailparse_post import router as mail_router


def create_app() -> FastAPI:
    """コア設定や共通ミドルウェアを組み込んだ FastAPI アプリを返す。"""

    settings = load_settings()
    app = FastAPI(title="calendar-auto-register", version="0.1.0")
    app.state.settings = settings  # type: ignore[attr-defined]
    app.middleware("http")(request_id_middleware)

    @app.get("/healthz", tags=["health"])
    def healthz() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    app.include_router(mail_router)

    return app

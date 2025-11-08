"""FastAPI アプリケーションの組み立てを担当するモジュール。"""

from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    """最小限の FastAPI アプリと `/healthz` エンドポイントを返す。"""
    app = FastAPI(title="calendar-auto-register", version="0.1.0")

    @app.get("/healthz", tags=["health"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app

"""ローカル/ Lambda エントリポイント。"""

from __future__ import annotations

import os
from typing import Any

import uvicorn
from mangum import Mangum

from .app import create_app

app = create_app()
_handler = Mangum(app)


def lambda_handler(event: dict[str, Any], context: Any) -> Any:
    """AWS Lambda から呼び出されるエントリポイント"""
    return _handler(event, context)


def run_local() -> None:
    """`uv run calendar-auto-register-api` 用のローカル実行関数。"""
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8000"))
    uvicorn.run("calendar_auto_register.main:app", host=host, port=port, reload=True)


if os.getenv("RUN_LOCAL") == "1":
    run_local()

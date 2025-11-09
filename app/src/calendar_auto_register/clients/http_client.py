"""httpx クライアントの共通設定。"""

from __future__ import annotations

import httpx

DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


def create_async_client(*, timeout: httpx.Timeout | None = None) -> httpx.AsyncClient:
    """共通タイムアウト付きの AsyncClient を生成する。"""

    return httpx.AsyncClient(timeout=timeout or DEFAULT_TIMEOUT)


def create_sync_client(*, timeout: httpx.Timeout | None = None) -> httpx.Client:
    """共通タイムアウト付きの同期 Client を生成する。"""

    return httpx.Client(timeout=timeout or DEFAULT_TIMEOUT)

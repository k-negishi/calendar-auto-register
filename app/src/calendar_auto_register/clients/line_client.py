"""LINE Messaging API の通知クライアント。"""

from __future__ import annotations

import json
from typing import Any

import httpx

from calendar_auto_register.clients.http_client import create_sync_client


LINE_PUSH_ENDPOINT = "https://api.line.me/v2/bot/message/push"


class LineApiError(RuntimeError):
    """LINE API のエラーを表す例外。"""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


def push_message(
    *,
    channel_access_token: str,
    user_id: str,
    message: str,
    timeout: httpx.Timeout | None = None,
) -> None:
    """LINE Push API でメッセージを送信する。"""

    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}],
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {channel_access_token}",
    }

    with create_sync_client(timeout=timeout) as client:
        response = client.post(LINE_PUSH_ENDPOINT, json=payload, headers=headers)

    if response.status_code == 200:
        return

    raise LineApiError(_build_error_message(response), response.status_code)


def _build_error_message(response: httpx.Response) -> str:
    try:
        body: dict[str, Any] = response.json()
    except json.JSONDecodeError:
        return f"LINE API呼び出しが失敗しました (Status: {response.status_code})"

    message = str(body.get("message") or "")
    details = body.get("details") or []
    if isinstance(details, list) and details:
        detail = details[0].get("message")
        if detail:
            message = f"{message} (詳細: {detail})"

    if message:
        return f"LINE API呼び出しが失敗しました (Status: {response.status_code}): {message}"

    return f"LINE API呼び出しが失敗しました (Status: {response.status_code})"

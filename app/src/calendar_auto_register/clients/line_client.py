"""LINE Messaging API の通知クライアント。"""

from __future__ import annotations

import json
from typing import Any

from linebot.v3.messaging import (
    ApiClient,
    ApiException,
    Configuration,
    MessagingApi,
    PushMessageRequest,
    TextMessage,
)


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
    timeout: float | None = None,
) -> None:
    """LINE Push API でメッセージを送信する。"""

    configuration = Configuration(access_token=channel_access_token)
    if timeout is not None:
        configuration.timeout = timeout

    request = PushMessageRequest(
        to=user_id,
        messages=[TextMessage(text=message)],
    )

    try:
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).push_message(request)
    except ApiException as exc:
        status_code = exc.status or 0
        raise LineApiError(_build_error_message(exc), status_code) from exc


def _build_error_message(exc: ApiException) -> str:
    try:
        body: dict[str, Any] = json.loads(exc.body or "{}")
    except json.JSONDecodeError:
        return f"LINE API呼び出しが失敗しました (Status: {exc.status})"

    message = str(body.get("message") or "")
    details = body.get("details") or []
    if isinstance(details, list) and details:
        detail = details[0].get("message")
        if detail:
            message = f"{message} (詳細: {detail})"

    if message:
        return f"LINE API呼び出しが失敗しました (Status: {exc.status}): {message}"

    return f"LINE API呼び出しが失敗しました (Status: {exc.status})"

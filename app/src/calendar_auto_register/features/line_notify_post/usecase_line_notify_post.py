"""LINE通知ユースケース。"""

from __future__ import annotations

from datetime import datetime

from calendar_auto_register.clients import line_client
from calendar_auto_register.shared.schemas.calendar_events import CalendarEventResult
from calendar_auto_register.core.settings import Settings


def send_line_notification(
    results: list[CalendarEventResult],
    *,
    settings: Settings,
) -> None:
    """LINE へ通知メッセージを送信する。"""

    if not settings.line_channel_access_token:
        raise ValueError("LINE_CHANNEL_ACCESS_TOKEN が未設定です。")
    if not settings.line_user_id:
        raise ValueError("LINE_USER_ID が未設定です。")

    message = build_line_message(results)
    line_client.push_message(
        channel_access_token=settings.line_channel_access_token,
        user_id=settings.line_user_id,
        message=message,
    )


def build_line_message(results: list[CalendarEventResult]) -> str:
    """LINE通知用の本文を構築する。"""

    created = sum(1 for result in results if result.status == "CREATED")
    duplicated = sum(1 for result in results if result.status == "DUPLICATED")
    failed = sum(1 for result in results if result.status == "FAILED")

    lines: list[str] = []
    lines.append("カレンダー自動登録 結果")
    lines.append("")
    lines.append("🧾 サマリ")
    lines.append(f"登録 {created}件 / 重複 {duplicated}件 / 失敗 {failed}件")
    lines.append("")
    lines.append("🔍 詳細")

    for result in results:
        event = result.event
        label = _status_label(result.status)
        lines.append(f"{label}　{event.summary}")
        lines.append(f"日時　{_format_datetime_range(event.start.dateTime, event.end.dateTime)}")
        if event.location:
            lines.append(f"場所　{event.location}")
        if result.status == "FAILED" and result.error:
            lines.append(f"エラー　{result.error.code} / {result.error.message}")
        lines.append("")

    if lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def _status_label(status: str) -> str:
    return {
        "CREATED": "登録",
        "DUPLICATED": "重複",
        "FAILED": "失敗",
    }.get(status, status)


def _format_datetime_range(start_raw: str, end_raw: str) -> str:
    start_dt = _parse_datetime(start_raw)
    end_dt = _parse_datetime(end_raw)
    if start_dt and end_dt:
        if start_dt.date() == end_dt.date():
            date_str = start_dt.strftime("%Y-%m-%d")
            start_time = start_dt.strftime("%H:%M")
            end_time = end_dt.strftime("%H:%M")
            return f"{date_str} {start_time}-{end_time}"
        start_str = start_dt.strftime("%Y-%m-%d %H:%M")
        end_str = end_dt.strftime("%Y-%m-%d %H:%M")
        return f"{start_str}-{end_str}"

    return f"{start_raw}-{end_raw}"


def _parse_datetime(value: str) -> datetime | None:
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        return None

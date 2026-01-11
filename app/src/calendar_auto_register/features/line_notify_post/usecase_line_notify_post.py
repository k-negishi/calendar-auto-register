"""LINE通知ユースケース。"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from calendar_auto_register.clients import line_client
from calendar_auto_register.core.settings import Settings
from calendar_auto_register.shared.schemas.calendar import DateModel, GoogleCalendarEventModel
from calendar_auto_register.shared.schemas.calendar_events import CalendarEventResult


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

        # 日時フォーマット（終日イベント or 時刻指定イベント）
        if isinstance(event.start, DateModel) and isinstance(event.end, DateModel):
            # 終日イベント
            time_label, time_str = _format_all_day_event(event)
            lines.append(f"{time_label}　{time_str}")
        elif hasattr(event.start, "dateTime") and hasattr(event.end, "dateTime"):
            # 時刻指定イベント（DateTimeModelの場合）
            if _is_payment_deadline_event(event.summary):
                # 支払い期限イベント
                time_str = _format_payment_deadline_datetime(
                    event.start.dateTime, event.end.dateTime
                )
                lines.append(f"期限　{time_str}")
            else:
                # 通常の時刻指定イベント
                time_str = _format_datetime_range(
                    event.start.dateTime, event.end.dateTime
                )
                lines.append(f"日時　{time_str}")

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


def _is_payment_deadline_event(summary: str) -> bool:
    """支払い期限イベントかどうか判定"""
    return "支払い期限 " in summary


def _format_all_day_event(event: GoogleCalendarEventModel) -> tuple[str, str]:
    """
    終日イベントをフォーマット

    Returns:
        (ラベル, 日時文字列)
        例: ("期限", "2025-12-30 23:59")
        例: ("日時", "2025-12-30 (終日)")
    """
    # 型チェック
    if not isinstance(event.start, DateModel) or not isinstance(event.end, DateModel):
        return ("日時", "")

    # 支払い期限イベントの場合
    if _is_payment_deadline_event(event.summary):
        # summary から時刻を抽出: "支払い期限 23:59@..."
        match = re.search(r"支払い期限 (\d{2}:\d{2})", event.summary)
        time_str = match.group(1) if match else "23:59"
        return ("期限", f"{event.start.date} {time_str}")

    # 通常の終日イベント
    if event.start.date == event.end.date:
        return ("日時", f"{event.start.date} (終日)")

    # 複数日にわたる終日イベント
    try:
        start_date = date.fromisoformat(event.start.date)
        end_date = date.fromisoformat(event.end.date)
        # Google Calendarの仕様: 終日イベントのendは翌日
        actual_end = end_date - timedelta(days=1)
        if start_date == actual_end:
            return ("日時", f"{event.start.date} (終日)")
        return ("日時", f"{event.start.date}〜{actual_end.isoformat()} (終日)")
    except (ValueError, AttributeError):
        return ("日時", f"{event.start.date}〜{event.end.date} (終日)")


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


def _format_payment_deadline_datetime(start_raw: str, end_raw: str) -> str:
    """
    支払い期限イベントの日時をフォーマット（YYYY-MM-DD HH:MM形式）

    Args:
        start_raw: 開始日時（支払期限日の00:00:00）
        end_raw: 終了日時（支払期限に指定された時刻）

    Returns:
        フォーマット済み日時文字列（例：2026-01-10 23:59）
    """
    end_dt = _parse_datetime(end_raw)
    if end_dt:
        return end_dt.strftime("%Y-%m-%d %H:%M")
    return end_raw


def _parse_datetime(value: str) -> datetime | None:
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        return None

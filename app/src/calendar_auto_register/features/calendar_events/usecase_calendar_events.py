"""Google Calendar への登録ユースケース（bulk対応）。"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from importlib.util import find_spec
from typing import Any, Iterable

from calendar_auto_register.clients import google_client
from calendar_auto_register.core.settings import Settings
from calendar_auto_register.features.calendar_events.schemas_calendar_events import (
    CalendarEventModel,
)
from calendar_auto_register.shared.schemas.calendar import DateModel, DateTimeModel
from calendar_auto_register.shared.schemas.calendar_events import (
    CalendarEventResult,
    ErrorModel,
)

_DUPLICATE_WINDOW_MINUTES = 15
_SUMMARY_PREFIX = "⚙️ "


def create_calendar_events(
    events: Iterable[CalendarEventModel],
    *,
    settings: Settings,
) -> list[CalendarEventResult]:
    """Google Calendar へイベントを登録し、1件ごとの結果を返す。"""

    events_list = list(events)
    if not events_list:
        return []

    try:
        service = google_client.service_from_settings(settings)
    except ValueError as exc:
        error = ErrorModel(
            code="GOOGLE_AUTH_ERROR",
            message=str(exc),
            retryable=False,
        )
        return [
            CalendarEventResult(
                status="FAILED",
                event=_event_with_default_tz(event, settings),
                error=error,
            )
            for event in events_list
        ]

    results: list[CalendarEventResult] = []
    for event in events_list:
        try:
            normalized_event, start_dt, end_dt = _normalize_event(event, settings)
            duplicate = _find_duplicate_event(
                service,
                settings=settings,
                normalized_event=normalized_event,
                start_dt=start_dt,
                end_dt=end_dt,
            )
            if duplicate:
                results.append(
                    CalendarEventResult(
                        status="DUPLICATED",
                        event=normalized_event,
                        google_event_id=duplicate.get("id"),
                    )
                )
                continue

            created = _insert_event(
                service,
                settings=settings,
                normalized_event=normalized_event,
            )
            results.append(
                CalendarEventResult(
                    status="CREATED",
                    event=normalized_event,
                    google_event_id=created.get("id"),
                )
            )
        except ValueError as exc:
            results.append(
                CalendarEventResult(
                    status="FAILED",
                    event=_event_with_default_tz(event, settings),
                    error=ErrorModel(
                        code="INVALID_EVENT",
                        message=str(exc),
                        retryable=False,
                    ),
                )
            )
        except Exception as exc:  # pragma: no cover - defensive
            http_error = _extract_http_error(exc)
            if http_error:
                status, retryable, message = http_error
                results.append(
                    CalendarEventResult(
                        status="FAILED",
                        event=_event_with_default_tz(event, settings),
                        error=ErrorModel(
                            code="GOOGLE_API_ERROR",
                            message=message,
                            retryable=retryable,
                        ),
                    )
                )
                continue
            results.append(
                CalendarEventResult(
                    status="FAILED",
                    event=_event_with_default_tz(event, settings),
                    error=ErrorModel(
                        code="UNEXPECTED_ERROR",
                        message=str(exc),
                        retryable=False,
                    ),
                )
            )

    return results


def _normalize_event(
    event: CalendarEventModel,
    settings: Settings,
) -> tuple[CalendarEventModel, datetime | date, datetime | date]:
    # 終日イベント（DateModel）の処理
    if isinstance(event.start, DateModel) and isinstance(event.end, DateModel):
        start_date = _parse_date(event.start.date)
        end_date = _parse_date(event.end.date)

        if end_date <= start_date:
            raise ValueError("end.date は start.date より後である必要があります。")

        normalized_event = event.model_copy(
            update={"summary": _apply_summary_prefix(event.summary)}
        )
        return normalized_event, start_date, end_date

    # 時刻指定イベント（DateTimeModel）の処理
    elif isinstance(event.start, DateTimeModel) and isinstance(event.end, DateTimeModel):
        start_tz = event.start.timeZone or settings.timezone_default
        end_tz = event.end.timeZone or start_tz
        start_dt = _parse_datetime(event.start.dateTime)
        end_dt = _parse_datetime(event.end.dateTime)

        if start_dt.tzinfo is None or end_dt.tzinfo is None:
            raise ValueError("start/end.dateTime はタイムゾーン付きで指定してください。")
        if end_dt <= start_dt:
            raise ValueError("end.dateTime は start.dateTime より後である必要があります。")

        normalized_event = event.model_copy(
            update={
                "summary": _apply_summary_prefix(event.summary),
                "start": event.start.model_copy(update={"timeZone": start_tz}),
                "end": event.end.model_copy(update={"timeZone": end_tz}),
            }
        )
        return normalized_event, start_dt, end_dt

    else:
        raise ValueError(
            "start と end は同じ型（DateModel または DateTimeModel）である必要があります。"
        )


def _event_with_default_tz(
    event: CalendarEventModel,
    settings: Settings,
) -> CalendarEventModel:
    # 終日イベント（DateModel）の場合はsummary prefixのみ適用
    if isinstance(event.start, DateModel) and isinstance(event.end, DateModel):
        return event.model_copy(update={"summary": _apply_summary_prefix(event.summary)})

    # 時刻指定イベント（DateTimeModel）の場合
    if isinstance(event.start, DateTimeModel) and isinstance(event.end, DateTimeModel):
        start_tz = event.start.timeZone or settings.timezone_default
        end_tz = event.end.timeZone or start_tz
        if event.start.timeZone and event.end.timeZone:
            return event.model_copy(update={"summary": _apply_summary_prefix(event.summary)})
        return event.model_copy(
            update={
                "summary": _apply_summary_prefix(event.summary),
                "start": event.start.model_copy(update={"timeZone": start_tz}),
                "end": event.end.model_copy(update={"timeZone": end_tz}),
            }
        )

    # 想定外の型
    return event.model_copy(update={"summary": _apply_summary_prefix(event.summary)})


def _find_duplicate_event(
    service: Any,
    *,
    settings: Settings,
    normalized_event: CalendarEventModel,
    start_dt: datetime | date,
    end_dt: datetime | date,
) -> dict[str, Any] | None:
    # 終日イベント（date型）の場合
    if isinstance(start_dt, date) and not isinstance(start_dt, datetime):
        tz_info = timezone.utc
        time_min = datetime.combine(start_dt, datetime.min.time(), tzinfo=tz_info).isoformat()
        time_max = datetime.combine(end_dt, datetime.min.time(), tzinfo=tz_info).isoformat()
    else:
        # 時刻指定イベント（datetime型）の場合
        delta = timedelta(minutes=_DUPLICATE_WINDOW_MINUTES)
        time_min = (start_dt - delta).isoformat()  # type: ignore
        time_max = (end_dt + delta).isoformat()  # type: ignore

    response = (
        service.events()
        .list(
            calendarId=settings.calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    items = response.get("items", [])

    for candidate in items:
        if _is_duplicate(candidate, normalized_event, start_dt, end_dt):
            return candidate
    return None


def _is_duplicate(
    candidate: dict[str, Any],
    normalized_event: CalendarEventModel,
    start_dt: datetime | date,
    end_dt: datetime | date,
) -> bool:
    summary = candidate.get("summary")
    if summary not in (_strip_summary_prefix(normalized_event.summary), normalized_event.summary):
        return False

    # 終日イベント（date型）の比較
    if isinstance(start_dt, date) and not isinstance(start_dt, datetime):
        candidate_start_date = candidate.get("start", {}).get("date")
        candidate_end_date = candidate.get("end", {}).get("date")
        if not candidate_start_date or not candidate_end_date:
            return False
        try:
            candidate_start_parsed = _parse_date(candidate_start_date)
            candidate_end_parsed = _parse_date(candidate_end_date)
            return candidate_start_parsed == start_dt and candidate_end_parsed == end_dt
        except ValueError:
            return False

    # 時刻指定イベント（datetime型）の比較
    candidate_start_dt, candidate_tz = _extract_candidate_datetime(candidate.get("start", {}))
    candidate_end_dt, candidate_end_tz = _extract_candidate_datetime(candidate.get("end", {}))
    if candidate_start_dt is None or candidate_end_dt is None:
        return False

    if isinstance(normalized_event.start, DateTimeModel) and isinstance(
        normalized_event.end, DateTimeModel
    ):
        tz = normalized_event.start.timeZone or normalized_event.end.timeZone
        if candidate_tz and tz and candidate_tz != tz:
            return False
        if candidate_end_tz and tz and candidate_end_tz != tz:
            return False

    # candidate_start_dt と candidate_end_dt は datetime | None で、既に None チェック済み
    # start_dt と end_dt が datetime 型の場合のみ比較可能
    if isinstance(start_dt, datetime) and isinstance(end_dt, datetime):
        return candidate_start_dt == start_dt and candidate_end_dt == end_dt

    return False


def _extract_candidate_datetime(payload: dict[str, Any]) -> tuple[datetime | None, str | None]:
    # dateTime形式の場合
    date_time = payload.get("dateTime")
    if date_time:
        try:
            return _parse_datetime(date_time), payload.get("timeZone")
        except ValueError:
            return None, payload.get("timeZone")

    # date形式の場合は None を返す（呼び出し元で`_is_duplicate`が処理）
    return None, payload.get("timeZone")


def _insert_event(
    service: Any,
    *,
    settings: Settings,
    normalized_event: CalendarEventModel,
) -> dict[str, Any]:
    body = _build_google_event_body(normalized_event)
    return (
        service.events()
        .insert(
            calendarId=settings.calendar_id,
            body=body,
        )
        .execute()
    )


def _build_google_event_body(event: CalendarEventModel) -> dict[str, Any]:
    body: dict[str, Any] = {"summary": event.summary}

    # start/end フィールドの構築（型に応じて異なる構造）
    if isinstance(event.start, DateModel) and isinstance(event.end, DateModel):
        # 終日イベント（date形式）
        body["start"] = {"date": event.start.date}
        body["end"] = {"date": event.end.date}
    elif isinstance(event.start, DateTimeModel) and isinstance(event.end, DateTimeModel):
        # 時刻指定イベント（dateTime形式）
        body["start"] = {"dateTime": event.start.dateTime, "timeZone": event.start.timeZone}
        body["end"] = {"dateTime": event.end.dateTime, "timeZone": event.end.timeZone}

    # オプションフィールド
    if event.location:
        body["location"] = event.location
    if event.description:
        body["description"] = event.description
    if event.eventType:
        body["eventType"] = event.eventType
    return body


def _apply_summary_prefix(summary: str) -> str:
    if summary.startswith(_SUMMARY_PREFIX):
        return summary
    return f"{_SUMMARY_PREFIX}{summary}"


def _strip_summary_prefix(summary: str) -> str:
    if summary.startswith(_SUMMARY_PREFIX):
        return summary[len(_SUMMARY_PREFIX) :]
    return summary


def _parse_datetime(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _parse_date(value: str) -> date:
    """YYYY-MM-DD 形式の日付文字列をパース"""
    return date.fromisoformat(value)


def _extract_http_error(exc: Exception) -> tuple[int, bool, str] | None:
    if not find_spec("googleapiclient.errors"):
        return None
    from googleapiclient.errors import HttpError

    if not isinstance(exc, HttpError):
        return None
    status = exc.resp.status if exc.resp else 500
    retryable = status >= 500 or status in {429, 408}
    return status, retryable, _format_http_error(exc)


def _format_http_error(exc: Exception) -> str:
    resp = getattr(exc, "resp", None)
    if resp is None:
        return str(exc)
    return f"HTTP {resp.status}: {exc}"

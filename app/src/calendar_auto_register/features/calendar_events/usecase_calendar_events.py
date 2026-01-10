"""Google Calendar への登録ユースケース（bulk対応）。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable

from googleapiclient.errors import HttpError

from calendar_auto_register.clients import google_client
from calendar_auto_register.core.settings import Settings
from calendar_auto_register.features.calendar_events.schemas_calendar_events import (
    CalendarEventModel,
)
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
        except HttpError as exc:
            status = exc.resp.status if exc.resp else 500
            retryable = status >= 500 or status in {429, 408}
            results.append(
                CalendarEventResult(
                    status="FAILED",
                    event=_event_with_default_tz(event, settings),
                    error=ErrorModel(
                        code="GOOGLE_API_ERROR",
                        message=_format_http_error(exc),
                        retryable=retryable,
                    ),
                )
            )
        except Exception as exc:  # pragma: no cover - defensive
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
) -> tuple[CalendarEventModel, datetime, datetime]:
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


def _event_with_default_tz(
    event: CalendarEventModel,
    settings: Settings,
) -> CalendarEventModel:
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


def _find_duplicate_event(
    service: Any,
    *,
    settings: Settings,
    normalized_event: CalendarEventModel,
    start_dt: datetime,
    end_dt: datetime,
) -> dict[str, Any] | None:
    delta = timedelta(minutes=_DUPLICATE_WINDOW_MINUTES)
    time_min = (start_dt - delta).isoformat()
    time_max = (end_dt + delta).isoformat()

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
    start_dt: datetime,
    end_dt: datetime,
) -> bool:
    summary = candidate.get("summary")
    if summary not in (_strip_summary_prefix(normalized_event.summary), normalized_event.summary):
        return False

    candidate_start, candidate_tz = _extract_candidate_datetime(candidate.get("start", {}))
    candidate_end, candidate_end_tz = _extract_candidate_datetime(candidate.get("end", {}))
    if candidate_start is None or candidate_end is None:
        return False

    tz = normalized_event.start.timeZone or normalized_event.end.timeZone
    if candidate_tz and tz and candidate_tz != tz:
        return False
    if candidate_end_tz and tz and candidate_end_tz != tz:
        return False

    return candidate_start == start_dt and candidate_end == end_dt


def _extract_candidate_datetime(payload: dict[str, Any]) -> tuple[datetime | None, str | None]:
    date_time = payload.get("dateTime")
    if not date_time:
        return None, payload.get("timeZone")
    try:
        return _parse_datetime(date_time), payload.get("timeZone")
    except ValueError:
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
    body: dict[str, Any] = {
        "summary": event.summary,
        "start": {"dateTime": event.start.dateTime, "timeZone": event.start.timeZone},
        "end": {"dateTime": event.end.dateTime, "timeZone": event.end.timeZone},
    }
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


def _format_http_error(exc: HttpError) -> str:
    if exc.resp is None:
        return str(exc)
    return f"HTTP {exc.resp.status}: {exc}"

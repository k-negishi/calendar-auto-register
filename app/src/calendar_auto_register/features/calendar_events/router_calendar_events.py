"""カレンダー登録エンドポイント（bulk対応）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from calendar_auto_register.core.settings import Settings
from calendar_auto_register.features.calendar_events.schemas_calendar_events import (
    CalendarEventsRequest,
    CalendarEventsResponse,
)
from calendar_auto_register.features.calendar_events.usecase_calendar_events import (
    create_calendar_events,
)

router = APIRouter(prefix="/calendar", tags=["calendar"])


async def get_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[attr-defined]


@router.post("/events", response_model=CalendarEventsResponse)
async def calendar_events(
    payload: CalendarEventsRequest,
    settings: Settings = Depends(get_settings),
) -> CalendarEventsResponse:
    results = create_calendar_events(payload.events, settings=settings)
    return CalendarEventsResponse(results=results)

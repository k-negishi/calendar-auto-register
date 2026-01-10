"""`/calendar/events` のリクエスト/レスポンススキーマ。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from calendar_auto_register.shared.schemas.calendar import (
    GoogleCalendarEventModel as CalendarEventModel,
)
from calendar_auto_register.shared.schemas.calendar_events import (
    CalendarEventResult,
    CalendarEventsResponse,
    ErrorModel,
)


class CalendarEventsRequest(BaseModel):
    """カレンダー登録リクエスト（bulk対応）。"""

    events: list[CalendarEventModel] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


__all__ = [
    "CalendarEventModel",
    "CalendarEventsRequest",
    "CalendarEventResult",
    "CalendarEventsResponse",
    "ErrorModel",
]

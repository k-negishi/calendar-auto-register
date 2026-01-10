"""Calendar events の共有スキーマ。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from calendar_auto_register.shared.schemas.calendar import GoogleCalendarEventModel


class ErrorModel(BaseModel):
    """共通エラーモデル。"""

    code: str
    message: str
    retryable: bool


class CalendarEventResult(BaseModel):
    """1件ごとの処理結果。"""

    status: Literal["CREATED", "DUPLICATED", "FAILED"]
    event: GoogleCalendarEventModel
    google_event_id: str | None = None
    error: ErrorModel | None = None

    model_config = ConfigDict(extra="forbid")


class CalendarEventsResponse(BaseModel):
    """カレンダー登録レスポンス（bulk対応）。"""

    results: list[CalendarEventResult] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

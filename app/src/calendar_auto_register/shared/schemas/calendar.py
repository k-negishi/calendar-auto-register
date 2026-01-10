"""Google Calendar 互換スキーマ。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DateTimeModel(BaseModel):
    """Google Calendar dateTime形式"""

    dateTime: str = Field(..., description="ISO8601形式の日時（例: 2024-12-25T14:00:00+09:00）")
    timeZone: str = Field(..., description="IANA タイムゾーン（例: Asia/Tokyo）")


class AttendeeModel(BaseModel):
    """出席者情報"""

    email: str
    displayName: str | None = None
    responseStatus: str = "needsAction"


class GoogleCalendarEventModel(BaseModel):
    """Google Calendar events.insert() 互換形式"""

    summary: str = Field(..., description="イベント名")
    start: DateTimeModel
    end: DateTimeModel
    location: str | None = None
    description: str | None = None
    attendees: list[AttendeeModel] = Field(default_factory=list)
    eventType: str = "default"

    model_config = ConfigDict(extra="forbid")

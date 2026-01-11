"""Google Calendar 互換スキーマ。"""

from __future__ import annotations

from typing import Union

from pydantic import BaseModel, ConfigDict, Field


class DateModel(BaseModel):
    """Google Calendar date形式（終日イベント）"""

    date: str = Field(..., description="YYYY-MM-DD形式の日付（例: 2024-12-25）")


class DateTimeModel(BaseModel):
    """Google Calendar dateTime形式"""

    dateTime: str = Field(..., description="ISO8601形式の日時（例: 2024-12-25T14:00:00+09:00）")
    timeZone: str = Field(..., description="IANA タイムゾーン（例: Asia/Tokyo）")


class GoogleCalendarEventModel(BaseModel):
    """Google Calendar events.insert() 互換形式"""

    summary: str = Field(..., description="イベント名")
    start: Union[DateModel, DateTimeModel] = Field(
        ...,
        description="イベント開始日時（終日の場合はdate、時刻指定の場合はdateTime）",
    )
    end: Union[DateModel, DateTimeModel] = Field(
        ...,
        description="イベント終了日時（終日の場合はdate、時刻指定の場合はdateTime）",
    )
    location: str | None = None
    description: str | None = None
    eventType: str = "default"

    model_config = ConfigDict(extra="forbid")

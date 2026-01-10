"""`/line/notify` のリクエスト/レスポンススキーマ。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from calendar_auto_register.shared.schemas.calendar_events import CalendarEventResult, ErrorModel


class LineNotifyRequest(BaseModel):
    """LINE通知リクエスト。Google Calendar登録結果を通知する"""

    results: list[CalendarEventResult] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class LineNotifyResponse(BaseModel):
    """LINE通知レスポンス。"""

    status: Literal["SENT"]

    model_config = ConfigDict(extra="forbid")


class LineNotifyErrorResponse(BaseModel):
    """LINE通知エラーレスポンス。"""

    error: ErrorModel

    model_config = ConfigDict(extra="forbid")

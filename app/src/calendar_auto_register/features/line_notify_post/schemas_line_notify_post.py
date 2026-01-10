"""`/line/notify` のリクエスト/レスポンススキーマ。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from calendar_auto_register.shared.schemas.calendar_events import CalendarEventsResponse, ErrorModel


class LineNotifyRequest(CalendarEventsResponse):
    """LINE通知リクエスト。"""


class LineNotifyResponse(BaseModel):
    """LINE通知レスポンス。"""

    status: Literal["SENT"]

    model_config = ConfigDict(extra="forbid")


class LineNotifyErrorResponse(BaseModel):
    """LINE通知エラーレスポンス。"""

    error: ErrorModel

    model_config = ConfigDict(extra="forbid")

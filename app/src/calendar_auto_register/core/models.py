"""ユースケース間で共有するデータモデル。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass(slots=True)
class NormalizedMail:
    """S3上の `.eml` から抽出した統一メールモデル。"""

    from_addr: str | None
    reply_to: str | None
    subject: str | None
    received_at: datetime | None
    text: str | None
    html: str | None
    attachments: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CalendarEvent:
    """Google Calendar SDK へ渡すイベント情報。"""

    summary: str
    start_at: datetime
    end_at: datetime
    timezone: str
    location: str | None = None
    attendees: list[str] = field(default_factory=list)
    description: str | None = None

    def to_google_event(self) -> dict[str, object]:
        """google-api-python-client が受け取るイベント辞書へ変換する。"""

        start_iso = self.start_at.isoformat()
        end_iso = self.end_at.isoformat()
        body: dict[str, object] = {
            "summary": self.summary,
            "start": {"dateTime": start_iso, "timeZone": self.timezone},
            "end": {"dateTime": end_iso, "timeZone": self.timezone},
        }
        if self.location:
            body["location"] = self.location
        if self.description:
            body["description"] = self.description
        if self.attendees:
            body["attendees"] = [{"email": email} for email in self.attendees]
        return body


@dataclass(slots=True)
class NotificationPayload:
    """SESで送付する処理結果のサマリ。"""

    status: Literal["SUCCESS", "FAILURE", "DUPLICATED"]
    request_id: str
    summary: str
    detail: str
    event: CalendarEvent | None = None

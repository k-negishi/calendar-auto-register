"""`/llm/extract-event` のリクエスト/レスポンススキーマ。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from calendar_auto_register.shared.schemas.calendar import GoogleCalendarEventModel


class AttachmentModel(BaseModel):
    name: str | None = None
    content_type: str | None = None
    s3_uri: str | None = None


class NormalizedMailModel(BaseModel):
    """入力: メール解析済みデータ"""

    from_addr: str | None = None
    reply_to: str | None = None
    subject: str | None = None
    received_at: datetime | None = None
    text: str | None = None
    html: str | None = None
    attachments: list[AttachmentModel] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

class LlmExtractEventRequest(BaseModel):
    """LLM 抽出リクエスト"""

    normalized_mail: NormalizedMailModel

    model_config = ConfigDict(extra="forbid")


class LlmExtractEventResponse(BaseModel):
    """LLM 抽出レスポンス"""

    events: list[GoogleCalendarEventModel] = Field(default_factory=list)

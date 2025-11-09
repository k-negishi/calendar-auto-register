"""`/mail/parse` のリクエスト/レスポンススキーマ。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MailParseRequest(BaseModel):
    """S3 上の RAW メールを指すキーのみを受け付ける。"""

    s3_key: str = Field(..., description="RAWメール格納S3キー（必須）")

    model_config = ConfigDict(extra="forbid")


class AttachmentModel(BaseModel):
    name: str | None = None
    content_type: str | None = None
    s3_uri: str | None = None


class NormalizedMailModel(BaseModel):
    from_addr: str | None = None
    reply_to: str | None = None
    subject: str | None = None
    received_at: datetime | None = None
    text: str | None = None
    html: str | None = None
    attachments: list[AttachmentModel] = Field(default_factory=list)


class MailParseResponse(BaseModel):
    normalized_mail: NormalizedMailModel

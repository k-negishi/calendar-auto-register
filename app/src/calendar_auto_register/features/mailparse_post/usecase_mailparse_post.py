"""メール解析ユースケース。"""

from __future__ import annotations

import email
import email.policy
import email.utils
from dataclasses import asdict
from email.message import EmailMessage
from typing import Any

from calendar_auto_register.clients import s3_client
from calendar_auto_register.core.models import NormalizedMail
from calendar_auto_register.core.settings import Settings
from calendar_auto_register.features.mailparse_post.schemas_mailparse_post import (
    MailParseRequest,
)


def parse_mail(
    request: MailParseRequest,
    *,
    settings: Settings,
) -> dict[str, Any]:
    """S3 から `.eml` を取得して NormalizedMail を返す。"""

    raw_eml = _load_eml_from_s3(request.s3_key, settings=settings)
    message = email.message_from_bytes(raw_eml, policy=email.policy.default)
    normalized = _build_normalized_mail(message)
    return asdict(normalized)


def _load_eml_from_s3(s3_key: str, settings: Settings) -> bytes:
    if not settings.raw_mail_bucket:
        raise ValueError("RAWメールバケット名が設定されていません。")
    response = s3_client.get_object(
        bucket=settings.raw_mail_bucket,
        key=s3_key,
        region=settings.region,
    )
    body = response["Body"]
    return body.read()


def _build_normalized_mail(message: EmailMessage) -> NormalizedMail:
    from_addr = message.get("From")
    reply_to = message.get("Reply-To")
    subject = message.get("Subject")
    headers_received = message.get("Date")
    resolved_received = (
        email.utils.parsedate_to_datetime(headers_received) if headers_received else None
    )

    text_body = None
    html_body = None
    attachments: list[str] = []

    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            disposition = part.get_content_disposition()
            if disposition == "attachment" and part.get_filename():
                attachments.append(part.get_filename() or "")
                continue
            if content_type == "text/plain" and text_body is None:
                text_body = part.get_content()
            elif content_type == "text/html" and html_body is None:
                html_body = part.get_content()
    else:
        content_type = message.get_content_type()
        if content_type == "text/html":
            html_body = message.get_content()
        else:
            text_body = message.get_content()

    return NormalizedMail(
        from_addr=from_addr,
        reply_to=reply_to,
        subject=subject,
        received_at=resolved_received,
        text=text_body,
        html=html_body,
        attachments=attachments,
    )

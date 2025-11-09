from __future__ import annotations

import io
from email.message import EmailMessage

import pytest
from fastapi.testclient import TestClient

from calendar_auto_register.app import create_app
from calendar_auto_register.clients import s3_client


def _build_eml(subject: str, text: str, html: str | None = None) -> bytes:
    msg = EmailMessage()
    msg["From"] = "alice@example.com"
    msg["To"] = "bob@example.com"
    msg["Subject"] = subject
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    return msg.as_bytes()


def test_S3取得で正規化できる(monkeypatch: pytest.MonkeyPatch) -> None:
    """S3 から `.eml` を取得して解析できることを検証する。"""

    eml = _build_eml("FromS3", "body")

    def fake_get_object(*, bucket: str, key: str, region: str):
        assert bucket == "calendar-auto-register"
        assert key == "mail.eml"
        assert region == "ap-northeast-1"
        return {"Body": io.BytesIO(eml)}

    monkeypatch.setattr(s3_client, "get_object", fake_get_object)

    client = TestClient(create_app())
    payload = {"s3_key": "mail.eml"}

    res = client.post("/mail/parse", json=payload)

    assert res.status_code == 200
    normalized = res.json()["normalized_mail"]
    assert normalized["subject"] == "FromS3"

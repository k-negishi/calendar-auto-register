"""LINE Webhook ルーターのテスト（unit + integration）。

[D10] usecase が EvB.putEvents のみになったため、
E2E テストは boto3.client().put_events をモックして検証する。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from calendar_auto_register.app import create_app


def _make_signature(body: bytes, secret: str) -> str:
    """テスト用 LINE 署名を生成するヘルパー。"""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _webhook_payload(events: list | None = None) -> dict:
    """テスト用 Webhook ペイロードを生成するヘルパー。"""
    if events is None:
        events = []
    return {"destination": "Udestination", "events": events}


def _text_event(user_id: str = "Uuser", text: str = "テスト") -> dict:
    """テキストメッセージイベントの dict を生成するヘルパー。"""
    return {
        "type": "message",
        "timestamp": 1710000000000,
        "source": {"type": "user", "userId": user_id},
        "replyToken": "reply-token",
        "message": {"type": "text", "id": "msg-001", "text": text},
    }


def _image_event(user_id: str = "Uuser", message_id: str = "img-001") -> dict:
    """画像メッセージイベントの dict を生成するヘルパー。"""
    return {
        "type": "message",
        "timestamp": 1710000000000,
        "source": {"type": "user", "userId": user_id},
        "replyToken": "reply-token",
        "message": {"type": "image", "id": message_id},
    }


# ===== 失敗系テスト（Layer 1 セキュリティ: 先に書く） =====

def test_署名ヘッダなし_403() -> None:
    """[Layer 1] X-Line-Signature ヘッダがない場合は 403 を返すことを確認する。"""
    import os
    os.environ["LINE_CHANNEL_SECRET"] = "test_secret"
    from calendar_auto_register.core.settings import load_settings
    load_settings.cache_clear()

    client = TestClient(create_app())
    body = json.dumps(_webhook_payload()).encode("utf-8")

    res = client.post(
        "/line/webhook",
        content=body,
        headers={"Content-Type": "application/json"},
        # X-Line-Signature ヘッダを意図的に省略
    )

    assert res.status_code == 403


def test_不正署名_403() -> None:
    """[Layer 1] 不正な X-Line-Signature の場合は 403 を返すことを確認する。"""
    import os
    os.environ["LINE_CHANNEL_SECRET"] = "test_secret"
    from calendar_auto_register.core.settings import load_settings
    load_settings.cache_clear()

    client = TestClient(create_app())
    body = json.dumps(_webhook_payload()).encode("utf-8")

    res = client.post(
        "/line/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Line-Signature": "invalid_signature_base64==",
        },
    )

    assert res.status_code == 403


def test_LINE_CHANNEL_SECRET未設定_500() -> None:
    """LINE_CHANNEL_SECRET が未設定の場合は 500 を返すことを確認する。"""
    import os
    os.environ.pop("LINE_CHANNEL_SECRET", None)
    from calendar_auto_register.core.settings import load_settings
    load_settings.cache_clear()

    client = TestClient(create_app())
    body = json.dumps(_webhook_payload()).encode("utf-8")

    res = client.post(
        "/line/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Line-Signature": "some_signature",
        },
    )

    assert res.status_code == 500


# ===== 正常系テスト =====

def test_正常署名_200() -> None:
    """正しい署名の場合は 200 を返すことを確認する。"""
    import os
    secret = "test_channel_secret"
    os.environ["LINE_CHANNEL_SECRET"] = secret
    from calendar_auto_register.core.settings import load_settings
    load_settings.cache_clear()

    payload = _webhook_payload()
    body = json.dumps(payload).encode("utf-8")
    signature = _make_signature(body, secret)

    mock_events_client = MagicMock()
    with patch("boto3.client", return_value=mock_events_client):
        client = TestClient(create_app())
        res = client.post(
            "/line/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Line-Signature": signature,
            },
        )

    assert res.status_code == 200
    assert res.json() == {}


def test_正常署名_process_webhookが呼ばれる() -> None:
    """正しい署名の場合に process_webhook() が呼ばれることを確認する。"""
    import os
    secret = "test_channel_secret"
    os.environ["LINE_CHANNEL_SECRET"] = secret
    from calendar_auto_register.core.settings import load_settings
    load_settings.cache_clear()

    payload = _webhook_payload(events=[_text_event()])
    body = json.dumps(payload).encode("utf-8")
    signature = _make_signature(body, secret)

    with patch(
        "calendar_auto_register.features.line_webhook.router_line_webhook_post.process_webhook"
    ) as mock_process:
        client = TestClient(create_app())
        res = client.post(
            "/line/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Line-Signature": signature,
            },
        )

    assert res.status_code == 200
    mock_process.assert_called_once()


# ===== E2E 統合テスト（D10: usecase は putEvents のみ） =====

def test_E2E_テキストメッセージ完全フロー() -> None:
    """テキストメッセージの完全フロー: Webhook → putEvents → 200。

    [D10] usecase は EventBridge.putEvents のみを実行する。
    LLM/Calendar/通知は SFN が非同期で処理する。
    """
    import os
    secret = "test_channel_secret"
    os.environ["LINE_CHANNEL_SECRET"] = secret
    os.environ.pop("ALLOWLIST_LINE_USER_IDS", None)  # CI環境の残留値をクリア
    from calendar_auto_register.core.settings import load_settings
    load_settings.cache_clear()

    payload = _webhook_payload(events=[_text_event(text="明日10時に会議があります")])
    body = json.dumps(payload).encode("utf-8")
    signature = _make_signature(body, secret)

    mock_events_client = MagicMock()
    with patch("boto3.client", return_value=mock_events_client):
        client = TestClient(create_app())
        res = client.post(
            "/line/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Line-Signature": signature,
            },
        )

    assert res.status_code == 200
    mock_events_client.put_events.assert_called_once()
    entries = mock_events_client.put_events.call_args.kwargs["Entries"]
    detail = json.loads(entries[0]["Detail"])
    assert detail["message_type"] == "text"


def test_E2E_画像メッセージ_putEventsが呼ばれる() -> None:
    """画像メッセージの完全フロー: Webhook → putEvents → 200。"""
    import os
    secret = "test_channel_secret"
    os.environ["LINE_CHANNEL_SECRET"] = secret
    os.environ.pop("ALLOWLIST_LINE_USER_IDS", None)  # CI環境の残留値をクリア
    from calendar_auto_register.core.settings import load_settings
    load_settings.cache_clear()

    payload = _webhook_payload(events=[_image_event(message_id="img-123")])
    body = json.dumps(payload).encode("utf-8")
    signature = _make_signature(body, secret)

    mock_events_client = MagicMock()
    with patch("boto3.client", return_value=mock_events_client):
        client = TestClient(create_app())
        res = client.post(
            "/line/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Line-Signature": signature,
            },
        )

    assert res.status_code == 200
    mock_events_client.put_events.assert_called_once()
    entries = mock_events_client.put_events.call_args.kwargs["Entries"]
    detail = json.loads(entries[0]["Detail"])
    assert detail["message_type"] == "image"
    assert detail["message_id"] == "img-123"


def test_E2E_未認可userId_200でputEventsなし() -> None:
    """[D6] 未認可 userId → 200 OK（putEvents が呼ばれない）。"""
    import os
    import json as json_module
    secret = "test_channel_secret"
    os.environ["LINE_CHANNEL_SECRET"] = secret
    os.environ["ALLOWLIST_LINE_USER_IDS"] = json_module.dumps(["Uallowed"])
    from calendar_auto_register.core.settings import load_settings
    load_settings.cache_clear()

    payload = _webhook_payload(events=[_text_event(user_id="Uunknown")])
    body = json.dumps(payload).encode("utf-8")
    signature = _make_signature(body, secret)

    mock_events_client = MagicMock()
    with patch("boto3.client", return_value=mock_events_client):
        client = TestClient(create_app())
        res = client.post(
            "/line/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Line-Signature": signature,
            },
        )

    assert res.status_code == 200
    mock_events_client.put_events.assert_not_called()

    os.environ.pop("ALLOWLIST_LINE_USER_IDS", None)


def test_E2E_空events_200でputEventsなし() -> None:
    """events が空配列 → 200 OK（putEvents が呼ばれない）。"""
    import os
    secret = "test_channel_secret"
    os.environ["LINE_CHANNEL_SECRET"] = secret
    from calendar_auto_register.core.settings import load_settings
    load_settings.cache_clear()

    payload = _webhook_payload(events=[])
    body = json.dumps(payload).encode("utf-8")
    signature = _make_signature(body, secret)

    mock_events_client = MagicMock()
    with patch("boto3.client", return_value=mock_events_client):
        client = TestClient(create_app())
        res = client.post(
            "/line/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Line-Signature": signature,
            },
        )

    assert res.status_code == 200
    mock_events_client.put_events.assert_not_called()


def test_E2E_followイベント_200でputEventsなし() -> None:
    """follow イベント → 200 OK（putEvents が呼ばれない）。"""
    import os
    secret = "test_channel_secret"
    os.environ["LINE_CHANNEL_SECRET"] = secret
    from calendar_auto_register.core.settings import load_settings
    load_settings.cache_clear()

    follow_event = {
        "type": "follow",
        "timestamp": 1710000000000,
        "source": {"type": "user", "userId": "Uuser"},
        "replyToken": "reply-token",
    }
    payload = _webhook_payload(events=[follow_event])
    body = json.dumps(payload).encode("utf-8")
    signature = _make_signature(body, secret)

    mock_events_client = MagicMock()
    with patch("boto3.client", return_value=mock_events_client):
        client = TestClient(create_app())
        res = client.post(
            "/line/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Line-Signature": signature,
            },
        )

    assert res.status_code == 200
    mock_events_client.put_events.assert_not_called()


def test_E2E_署名失敗_403() -> None:
    """[Layer 1] 署名失敗 → 403（putEvents が呼ばれない）。"""
    import os
    os.environ["LINE_CHANNEL_SECRET"] = "correct_secret"
    from calendar_auto_register.core.settings import load_settings
    load_settings.cache_clear()

    payload = _webhook_payload(events=[_text_event()])
    body = json.dumps(payload).encode("utf-8")
    # 間違ったシークレットで署名
    wrong_signature = _make_signature(body, "wrong_secret")

    mock_events_client = MagicMock()
    with patch("boto3.client", return_value=mock_events_client):
        client = TestClient(create_app())
        res = client.post(
            "/line/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Line-Signature": wrong_signature,
            },
        )

    assert res.status_code == 403
    mock_events_client.put_events.assert_not_called()

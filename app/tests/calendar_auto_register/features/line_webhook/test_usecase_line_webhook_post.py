"""LINE Webhook usecase のテスト。

[D8, D10] usecase は EventBridge.putEvents のみを実行する。
LLM/Calendar/通知は SFN が非同期でオーケストレートする。
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, call, patch

import pytest

from calendar_auto_register.core.settings import Settings


def _make_settings(
    *,
    allowlist_line_user_ids: list[str] | None = None,
    region: str = "ap-northeast-1",
) -> Settings:
    """テスト用 Settings を生成するヘルパー。"""
    from calendar_auto_register.core.settings import load_settings
    load_settings.cache_clear()

    import os
    os.environ["CALENDAR_ID"] = "primary"
    os.environ["GOOGLE_CREDENTIALS"] = "dummy"
    os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "dummy_token"
    os.environ["LINE_USER_ID"] = "Udummy"
    os.environ["S3_RAW_MAIL_BUCKET"] = "test-bucket"
    os.environ["BEDROCK_MODEL_ID"] = "test-model"
    os.environ["AWS_DEFAULT_REGION"] = region
    if allowlist_line_user_ids is not None:
        os.environ["ALLOWLIST_LINE_USER_IDS"] = json.dumps(allowlist_line_user_ids)
    else:
        os.environ.pop("ALLOWLIST_LINE_USER_IDS", None)

    return load_settings()


def _make_text_event(
    user_id: str = "Uauthorized",
    text: str = "明日10時に会議があります",
    message_id: str = "msg-001",
):
    """テキストメッセージイベントを生成するヘルパー。"""
    from calendar_auto_register.features.line_webhook.schemas_line_webhook_post import (
        LineMessage,
        LineSource,
        LineWebhookEvent,
    )
    return LineWebhookEvent(
        type="message",
        timestamp=1710000000000,
        source=LineSource(type="user", userId=user_id),
        replyToken="reply-token",
        message=LineMessage(type="text", id=message_id, text=text),
    )


def _make_image_event(
    user_id: str = "Uauthorized",
    message_id: str = "img-001",
):
    """画像メッセージイベントを生成するヘルパー。"""
    from calendar_auto_register.features.line_webhook.schemas_line_webhook_post import (
        LineMessage,
        LineSource,
        LineWebhookEvent,
    )
    return LineWebhookEvent(
        type="message",
        timestamp=1710000000000,
        source=LineSource(type="user", userId=user_id),
        replyToken="reply-token",
        message=LineMessage(type="image", id=message_id),
    )


def _make_sticker_event(user_id: str = "Uauthorized"):
    """sticker メッセージイベントを生成するヘルパー。"""
    from calendar_auto_register.features.line_webhook.schemas_line_webhook_post import (
        LineMessage,
        LineSource,
        LineWebhookEvent,
    )
    return LineWebhookEvent(
        type="message",
        timestamp=1710000000000,
        source=LineSource(type="user", userId=user_id),
        replyToken="reply-token",
        message=LineMessage(type="sticker", id="sticker-001"),
    )


def _make_follow_event(user_id: str = "Uauthorized"):
    """follow イベントを生成するヘルパー。"""
    from calendar_auto_register.features.line_webhook.schemas_line_webhook_post import (
        LineSource,
        LineWebhookEvent,
    )
    return LineWebhookEvent(
        type="follow",
        timestamp=1710000000000,
        source=LineSource(type="user", userId=user_id),
        replyToken="reply-token",
    )


def _make_webhook_request(events: list):
    """LineWebhookRequest を生成するヘルパー。"""
    from calendar_auto_register.features.line_webhook.schemas_line_webhook_post import (
        LineWebhookRequest,
    )
    return LineWebhookRequest(destination="Udestination", events=events)


# ===== 失敗系テスト（先に書く: D6, D10） =====

def test_未認可userId_putEventsが呼ばれない() -> None:
    """[D6] allowlist に含まれない userId の場合、putEvents が呼ばれないことを確認する。"""
    from calendar_auto_register.features.line_webhook.usecase_line_webhook_post import (
        process_webhook,
    )

    settings = _make_settings(allowlist_line_user_ids=["Uallowed"])
    webhook_request = _make_webhook_request([_make_text_event(user_id="Unotallowed")])

    with patch("boto3.client") as mock_boto3:
        process_webhook(webhook_request, settings=settings)

    mock_boto3.assert_not_called()


def test_followイベント_putEventsが呼ばれない() -> None:
    """message 以外のイベントタイプ（follow）の場合、putEvents が呼ばれないことを確認する。"""
    from calendar_auto_register.features.line_webhook.usecase_line_webhook_post import (
        process_webhook,
    )

    settings = _make_settings()
    webhook_request = _make_webhook_request([_make_follow_event()])

    with patch("boto3.client") as mock_boto3:
        process_webhook(webhook_request, settings=settings)

    mock_boto3.assert_not_called()


def test_未対応メッセージタイプ_putEventsが呼ばれない() -> None:
    """sticker 等の未対応メッセージタイプの場合、putEvents が呼ばれないことを確認する。"""
    from calendar_auto_register.features.line_webhook.usecase_line_webhook_post import (
        process_webhook,
    )

    settings = _make_settings()
    webhook_request = _make_webhook_request([_make_sticker_event()])

    with patch("boto3.client") as mock_boto3:
        process_webhook(webhook_request, settings=settings)

    mock_boto3.assert_not_called()


def test_空events_putEventsが呼ばれない() -> None:
    """events が空リストの場合、putEvents が呼ばれないことを確認する。"""
    from calendar_auto_register.features.line_webhook.usecase_line_webhook_post import (
        process_webhook,
    )

    settings = _make_settings()
    webhook_request = _make_webhook_request([])

    with patch("boto3.client") as mock_boto3:
        process_webhook(webhook_request, settings=settings)

    mock_boto3.assert_not_called()


# ===== 正常系テスト（D10: putEvents のみ） =====

def test_テキストメッセージ_putEventsが呼ばれる() -> None:
    """[D10] テキストメッセージの場合、EventBridge.putEvents が呼ばれることを確認する。"""
    from calendar_auto_register.features.line_webhook.usecase_line_webhook_post import (
        process_webhook,
    )

    settings = _make_settings()
    text = "明日10時に会議があります"
    webhook_request = _make_webhook_request(
        [_make_text_event(user_id="Uuser", text=text, message_id="msg-001")]
    )

    mock_events_client = MagicMock()
    with patch("boto3.client", return_value=mock_events_client):
        process_webhook(webhook_request, settings=settings)

    mock_events_client.put_events.assert_called_once()
    call_args = mock_events_client.put_events.call_args
    entries = call_args.kwargs["Entries"]
    assert len(entries) == 1
    detail = json.loads(entries[0]["Detail"])
    assert detail["message_type"] == "text"
    assert detail["message_id"] == "msg-001"
    assert detail["text"] == text
    assert detail["user_id"] == "Uuser"


def test_画像メッセージ_putEventsが呼ばれる() -> None:
    """[D10] 画像メッセージの場合、EventBridge.putEvents が呼ばれることを確認する。"""
    from calendar_auto_register.features.line_webhook.usecase_line_webhook_post import (
        process_webhook,
    )

    settings = _make_settings()
    webhook_request = _make_webhook_request(
        [_make_image_event(user_id="Uuser", message_id="img-001")]
    )

    mock_events_client = MagicMock()
    with patch("boto3.client", return_value=mock_events_client):
        process_webhook(webhook_request, settings=settings)

    mock_events_client.put_events.assert_called_once()
    call_args = mock_events_client.put_events.call_args
    entries = call_args.kwargs["Entries"]
    assert len(entries) == 1
    detail = json.loads(entries[0]["Detail"])
    assert detail["message_type"] == "image"
    assert detail["message_id"] == "img-001"
    assert detail["user_id"] == "Uuser"


def test_putEventsのイベントソースとDetailType確認() -> None:
    """EventBridge エントリの Source と DetailType が正しいことを確認する。"""
    from calendar_auto_register.features.line_webhook.usecase_line_webhook_post import (
        process_webhook,
    )

    settings = _make_settings()
    webhook_request = _make_webhook_request([_make_text_event()])

    mock_events_client = MagicMock()
    with patch("boto3.client", return_value=mock_events_client):
        process_webhook(webhook_request, settings=settings)

    entries = mock_events_client.put_events.call_args.kwargs["Entries"]
    assert entries[0]["Source"] == "calendar-auto-register.line"
    assert entries[0]["DetailType"] == "LineMessageEvent"


def test_空allowlist_全ユーザーにputEventsが呼ばれる() -> None:
    """[D6] allowlist が空のとき、全ユーザーに対して putEvents が呼ばれることを確認する。"""
    from calendar_auto_register.features.line_webhook.usecase_line_webhook_post import (
        process_webhook,
    )

    settings = _make_settings(allowlist_line_user_ids=[])  # 空リスト = 全許可
    webhook_request = _make_webhook_request([_make_text_event(user_id="Uanyone")])

    mock_events_client = MagicMock()
    with patch("boto3.client", return_value=mock_events_client):
        process_webhook(webhook_request, settings=settings)

    mock_events_client.put_events.assert_called_once()


def test_認可userId_putEventsが呼ばれる() -> None:
    """[D6] allowlist に含まれる userId の場合、putEvents が呼ばれることを確認する。"""
    from calendar_auto_register.features.line_webhook.usecase_line_webhook_post import (
        process_webhook,
    )

    settings = _make_settings(allowlist_line_user_ids=["Uauthorized"])
    webhook_request = _make_webhook_request([_make_text_event(user_id="Uauthorized")])

    mock_events_client = MagicMock()
    with patch("boto3.client", return_value=mock_events_client):
        process_webhook(webhook_request, settings=settings)

    mock_events_client.put_events.assert_called_once()


def test_LLM呼び出しは行われない() -> None:
    """[D10] process_webhook は LLM を呼び出さないことを確認する。"""
    from calendar_auto_register.features.line_webhook.usecase_line_webhook_post import (
        process_webhook,
    )

    settings = _make_settings()
    webhook_request = _make_webhook_request([_make_text_event()])

    # boto3 をモックしてputEventsを受け付ける
    mock_events_client = MagicMock()
    with patch("boto3.client", return_value=mock_events_client), \
         patch("calendar_auto_register.clients.bedrock_client.invoke_model") as mock_bedrock:
        process_webhook(webhook_request, settings=settings)

    mock_bedrock.assert_not_called()

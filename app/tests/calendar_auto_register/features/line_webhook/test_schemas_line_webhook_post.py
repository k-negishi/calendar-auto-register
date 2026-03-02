"""LINE Webhook スキーマのテスト。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


# ===== 失敗系テスト（先に書く） =====

def test_LineSource_userId欠如でValidationError() -> None:
    """LineSource に userId がないと ValidationError になることを確認する。"""
    from calendar_auto_register.features.line_webhook.schemas_line_webhook_post import LineSource

    with pytest.raises(ValidationError):
        LineSource(type="user")  # userId がない


def test_LineWebhookRequest_不正JSONはパース失敗() -> None:
    """LineWebhookRequest に不正な型を渡すと ValidationError になることを確認する。"""
    from calendar_auto_register.features.line_webhook.schemas_line_webhook_post import LineWebhookRequest

    with pytest.raises(ValidationError):
        # events に str を渡す（list[LineWebhookEvent] ではない）
        LineWebhookRequest(destination="xxx", events="not_a_list")  # type: ignore


def test_LineSource_userId必須() -> None:
    """LineSource の userId が必須フィールドであることを確認する。"""
    from calendar_auto_register.features.line_webhook.schemas_line_webhook_post import LineSource

    with pytest.raises(ValidationError) as exc_info:
        LineSource(type="user")

    errors = exc_info.value.errors()
    assert any(e["loc"] == ("userId",) for e in errors)


# ===== 正常系テスト =====

def test_テキストメッセージイベントのパース() -> None:
    """テキストメッセージイベントが正しくパースされることを確認する。"""
    from calendar_auto_register.features.line_webhook.schemas_line_webhook_post import (
        LineWebhookRequest,
    )

    data = {
        "destination": "Uxxxxx",
        "events": [
            {
                "type": "message",
                "timestamp": 1710000000000,
                "source": {"type": "user", "userId": "Uabc123"},
                "replyToken": "reply-token-xxx",
                "message": {
                    "type": "text",
                    "id": "msg-001",
                    "text": "明日10時に会議があります",
                },
            }
        ],
    }
    request = LineWebhookRequest(**data)
    assert request.destination == "Uxxxxx"
    assert len(request.events) == 1
    event = request.events[0]
    assert event.type == "message"
    assert event.source.userId == "Uabc123"
    assert event.message is not None
    assert event.message.type == "text"
    assert event.message.text == "明日10時に会議があります"


def test_画像メッセージイベントのパース() -> None:
    """画像メッセージイベントが正しくパースされることを確認する。"""
    from calendar_auto_register.features.line_webhook.schemas_line_webhook_post import (
        LineWebhookRequest,
    )

    data = {
        "destination": "Uxxxxx",
        "events": [
            {
                "type": "message",
                "timestamp": 1710000000000,
                "source": {"type": "user", "userId": "Uabc123"},
                "replyToken": "reply-token-xxx",
                "message": {
                    "type": "image",
                    "id": "img-001",
                },
            }
        ],
    }
    request = LineWebhookRequest(**data)
    event = request.events[0]
    assert event.message is not None
    assert event.message.type == "image"
    assert event.message.text is None  # 画像は text なし


def test_followイベントはmessageフィールドなしでパース() -> None:
    """follow イベント（message フィールドなし）が正しくパースされることを確認する。"""
    from calendar_auto_register.features.line_webhook.schemas_line_webhook_post import (
        LineWebhookRequest,
    )

    data = {
        "destination": "Uxxxxx",
        "events": [
            {
                "type": "follow",
                "timestamp": 1710000000000,
                "source": {"type": "user", "userId": "Uabc123"},
                "replyToken": "reply-token-xxx",
                # message フィールドなし
            }
        ],
    }
    request = LineWebhookRequest(**data)
    event = request.events[0]
    assert event.type == "follow"
    assert event.message is None


def test_未知のメッセージタイプもパースできる() -> None:
    """LineMessage.type が "sticker" などの未知の値でもパースできることを確認する。

    type は str 型なので、どんな値でもパースエラーにならない。
    usecase 側でフィルタする設計。
    """
    from calendar_auto_register.features.line_webhook.schemas_line_webhook_post import LineMessage

    msg = LineMessage(type="sticker", id="sticker-001")
    assert msg.type == "sticker"
    assert msg.text is None


def test_eventsが空配列でもパースできる() -> None:
    """events が空配列の場合もパースできることを確認する。"""
    from calendar_auto_register.features.line_webhook.schemas_line_webhook_post import (
        LineWebhookRequest,
    )

    data = {"destination": "Uxxxxx", "events": []}
    request = LineWebhookRequest(**data)
    assert request.events == []


def test_複数イベントのパース() -> None:
    """複数のイベントが正しくパースされることを確認する。"""
    from calendar_auto_register.features.line_webhook.schemas_line_webhook_post import (
        LineWebhookRequest,
    )

    data = {
        "destination": "Uxxxxx",
        "events": [
            {
                "type": "message",
                "timestamp": 1710000000000,
                "source": {"type": "user", "userId": "U111"},
                "replyToken": "token-1",
                "message": {"type": "text", "id": "msg-1", "text": "テスト1"},
            },
            {
                "type": "follow",
                "timestamp": 1710000000001,
                "source": {"type": "user", "userId": "U222"},
                "replyToken": "token-2",
            },
        ],
    }
    request = LineWebhookRequest(**data)
    assert len(request.events) == 2
    assert request.events[0].type == "message"
    assert request.events[1].type == "follow"

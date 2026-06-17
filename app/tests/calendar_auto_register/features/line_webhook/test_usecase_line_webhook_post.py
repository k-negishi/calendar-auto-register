"""LINE Webhook usecase のテスト。

[D8, D10] usecase は SFN.start_execution のみを実行する。
LLM/Calendar/通知は SFN が非同期でオーケストレートする。

[Dedup] message_id を SFN 実行名に使うことで LINE リトライによる多重起動を防ぐ。
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from calendar_auto_register.core.settings import Settings


def _make_settings(
    *,
    allowlist_line_user_ids: list[str] | None = None,
    region: str = "ap-northeast-1",
    line_sm_arn: str = "arn:aws:states:ap-northeast-1:123456789012:stateMachine:calendar-auto-register-line-sm",
) -> Settings:
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
    os.environ["LINE_SM_ARN"] = line_sm_arn
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
    from calendar_auto_register.features.line_webhook.schemas_line_webhook_post import (
        LineWebhookRequest,
    )
    return LineWebhookRequest(destination="Udestination", events=events)


def _make_client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, "StartExecution")


# ===== スキップ系テスト =====

def test_未認可userId_start_executionが呼ばれない() -> None:
    from calendar_auto_register.features.line_webhook.usecase_line_webhook_post import process_webhook

    settings = _make_settings(allowlist_line_user_ids=["Uallowed"])
    webhook_request = _make_webhook_request([_make_text_event(user_id="Unotallowed")])

    with patch("boto3.client") as mock_boto3:
        process_webhook(webhook_request, settings=settings)

    mock_boto3.assert_not_called()


def test_followイベント_start_executionが呼ばれない() -> None:
    from calendar_auto_register.features.line_webhook.usecase_line_webhook_post import process_webhook

    settings = _make_settings()
    webhook_request = _make_webhook_request([_make_follow_event()])

    with patch("boto3.client") as mock_boto3:
        process_webhook(webhook_request, settings=settings)

    mock_boto3.assert_not_called()


def test_未対応メッセージタイプ_start_executionが呼ばれない() -> None:
    from calendar_auto_register.features.line_webhook.usecase_line_webhook_post import process_webhook

    settings = _make_settings()
    webhook_request = _make_webhook_request([_make_sticker_event()])

    with patch("boto3.client") as mock_boto3:
        process_webhook(webhook_request, settings=settings)

    mock_boto3.assert_not_called()


def test_空events_start_executionが呼ばれない() -> None:
    from calendar_auto_register.features.line_webhook.usecase_line_webhook_post import process_webhook

    settings = _make_settings()
    webhook_request = _make_webhook_request([])

    with patch("boto3.client") as mock_boto3:
        process_webhook(webhook_request, settings=settings)

    mock_boto3.assert_not_called()


# ===== 正常系テスト =====

def test_テキストメッセージ_start_executionが呼ばれる() -> None:
    from calendar_auto_register.features.line_webhook.usecase_line_webhook_post import process_webhook

    sm_arn = "arn:aws:states:ap-northeast-1:123:stateMachine:line-sm"
    settings = _make_settings(line_sm_arn=sm_arn)
    text = "明日10時に会議があります"
    webhook_request = _make_webhook_request(
        [_make_text_event(user_id="Uuser", text=text, message_id="msg-001")]
    )

    mock_sfn = MagicMock()
    with patch("boto3.client", return_value=mock_sfn):
        process_webhook(webhook_request, settings=settings)

    mock_sfn.start_execution.assert_called_once()
    kwargs = mock_sfn.start_execution.call_args.kwargs
    assert kwargs["stateMachineArn"] == sm_arn
    assert kwargs["name"] == "msg-001"
    detail = json.loads(kwargs["input"])["detail"]
    assert detail["message_type"] == "text"
    assert detail["message_id"] == "msg-001"
    assert detail["text"] == text
    assert detail["user_id"] == "Uuser"


def test_画像メッセージ_start_executionが呼ばれる() -> None:
    from calendar_auto_register.features.line_webhook.usecase_line_webhook_post import process_webhook

    sm_arn = "arn:aws:states:ap-northeast-1:123:stateMachine:line-sm"
    settings = _make_settings(line_sm_arn=sm_arn)
    webhook_request = _make_webhook_request(
        [_make_image_event(user_id="Uuser", message_id="img-001")]
    )

    mock_sfn = MagicMock()
    with patch("boto3.client", return_value=mock_sfn):
        process_webhook(webhook_request, settings=settings)

    mock_sfn.start_execution.assert_called_once()
    kwargs = mock_sfn.start_execution.call_args.kwargs
    assert kwargs["name"] == "img-001"
    detail = json.loads(kwargs["input"])["detail"]
    assert detail["message_type"] == "image"
    assert detail["message_id"] == "img-001"
    assert detail["user_id"] == "Uuser"


def test_空allowlist_全ユーザーにstart_executionが呼ばれる() -> None:
    from calendar_auto_register.features.line_webhook.usecase_line_webhook_post import process_webhook

    settings = _make_settings(allowlist_line_user_ids=[])
    webhook_request = _make_webhook_request([_make_text_event(user_id="Uanyone")])

    mock_sfn = MagicMock()
    with patch("boto3.client", return_value=mock_sfn):
        process_webhook(webhook_request, settings=settings)

    mock_sfn.start_execution.assert_called_once()


def test_認可userId_start_executionが呼ばれる() -> None:
    from calendar_auto_register.features.line_webhook.usecase_line_webhook_post import process_webhook

    settings = _make_settings(allowlist_line_user_ids=["Uauthorized"])
    webhook_request = _make_webhook_request([_make_text_event(user_id="Uauthorized")])

    mock_sfn = MagicMock()
    with patch("boto3.client", return_value=mock_sfn):
        process_webhook(webhook_request, settings=settings)

    mock_sfn.start_execution.assert_called_once()


# ===== 冪等性テスト（Dedup） =====

def test_重複messageId_ExecutionAlreadyExists_は正常終了() -> None:
    """LINE リトライで同一 message_id が来た場合、例外を上げずに無視する。"""
    from calendar_auto_register.features.line_webhook.usecase_line_webhook_post import process_webhook

    settings = _make_settings()
    webhook_request = _make_webhook_request([_make_text_event(message_id="dup-001")])

    mock_sfn = MagicMock()
    mock_sfn.start_execution.side_effect = _make_client_error("ExecutionAlreadyExists")
    with patch("boto3.client", return_value=mock_sfn):
        process_webhook(webhook_request, settings=settings)  # 例外が出ないこと


def test_その他ClientError_は再送出される() -> None:
    """ExecutionAlreadyExists 以外の ClientError は呼び出し元に伝播する。"""
    from calendar_auto_register.features.line_webhook.usecase_line_webhook_post import process_webhook

    settings = _make_settings()
    webhook_request = _make_webhook_request([_make_text_event()])

    mock_sfn = MagicMock()
    mock_sfn.start_execution.side_effect = _make_client_error("AccessDeniedException")
    with patch("boto3.client", return_value=mock_sfn):
        with pytest.raises(ClientError):
            process_webhook(webhook_request, settings=settings)


def test_LLM呼び出しは行われない() -> None:
    from calendar_auto_register.features.line_webhook.usecase_line_webhook_post import process_webhook

    settings = _make_settings()
    webhook_request = _make_webhook_request([_make_text_event()])

    mock_sfn = MagicMock()
    with patch("boto3.client", return_value=mock_sfn), \
         patch("calendar_auto_register.clients.bedrock_client.invoke_model") as mock_bedrock:
        process_webhook(webhook_request, settings=settings)

    mock_bedrock.assert_not_called()

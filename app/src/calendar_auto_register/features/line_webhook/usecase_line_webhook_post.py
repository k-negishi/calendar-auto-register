"""LINE Webhook ユースケース。

[D8, D10] このモジュールは EventBridge.putEvents のみを実行する。
LLM 抽出・カレンダー登録・LINE 通知は Step Functions がオーケストレートする。
"""

from __future__ import annotations

import json
import logging

import boto3

from calendar_auto_register.core.settings import Settings
from calendar_auto_register.features.line_webhook.schemas_line_webhook_post import (
    LineWebhookEvent,
    LineWebhookRequest,
)

logger = logging.getLogger(__name__)

# EventBridge に送信するソース識別子
_EVENT_SOURCE = "calendar-auto-register.line"
_EVENT_DETAIL_TYPE = "LineMessageEvent"

# SFN の Choice ステートで処理できるメッセージタイプ
_SUPPORTED_MESSAGE_TYPES = frozenset({"text", "image"})


def process_webhook(
    request: LineWebhookRequest,
    *,
    settings: Settings,
) -> None:
    """LINE Webhook イベントを処理する。

    メッセージイベントのみを対象に、以下を実行:
      1. [Layer 2] source.userId allowlist 検証
      2. サポートされるメッセージタイプ（text/image）の確認
      3. EventBridge.putEvents でイベントを発行（非同期処理は SFN が担当）

    Args:
        request: LINE Webhook リクエスト
        settings: アプリケーション設定
    """
    for event in request.events:
        # message イベント以外はスキップ
        if event.type != "message" or event.message is None:
            logger.info("message 以外のイベントをスキップ: type=%s", event.type)
            continue

        # 未対応メッセージタイプはスキップ（sticker, location, etc.）
        if event.message.type not in _SUPPORTED_MESSAGE_TYPES:
            logger.info(
                "未対応のメッセージタイプをスキップ: type=%s", event.message.type
            )
            continue

        # [Layer 2] userId allowlist 検証（空リストは全ユーザー許可）
        if settings.allowlist_line_user_ids and \
                event.source.userId not in settings.allowlist_line_user_ids:
            logger.warning(
                "未認可の userId からのメッセージをスキップ: userId=%s",
                event.source.userId,
            )
            continue

        _put_line_event(event, settings=settings)


def _put_line_event(
    event: LineWebhookEvent,
    *,
    settings: Settings,
) -> None:
    """EventBridge に LINE イベントを発行する。

    SFN の LINE State Machine がこのイベントをトリガーとして起動し、
    LLM 抽出・カレンダー登録・LINE 通知を HTTP Task で順番に処理する。
    """
    assert event.message is not None

    client = boto3.client("events", region_name=settings.region)
    client.put_events(
        Entries=[
            {
                "Source": _EVENT_SOURCE,
                "DetailType": _EVENT_DETAIL_TYPE,
                "Detail": json.dumps(
                    {
                        "message_type": event.message.type,
                        "message_id": event.message.id,
                        "text": event.message.text,
                        "user_id": event.source.userId,
                    }
                ),
                "EventBusName": "default",
            }
        ]
    )
    logger.info(
        "EventBridge にイベントを発行: userId=%s, messageType=%s, messageId=%s",
        event.source.userId,
        event.message.type,
        event.message.id,
    )

"""LINE Webhook ユースケース。

[D8, D10] このモジュールは SFN.start_execution のみを実行する。
LLM 抽出・カレンダー登録・LINE 通知は Step Functions がオーケストレートする。

[Dedup] message_id を SFN 実行名に使用することで、LINE Platform のリトライによる
多重起動を防ぐ。同一 message_id での 2 回目の start_execution は
ExecutionAlreadyExists で無害に終了する。
"""

from __future__ import annotations

import json
import logging

import boto3
from botocore.exceptions import ClientError

from calendar_auto_register.core.settings import Settings
from calendar_auto_register.features.line_webhook.schemas_line_webhook_post import (
    LineWebhookEvent,
    LineWebhookRequest,
)

logger = logging.getLogger(__name__)

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
      3. SFN.start_execution でパイプラインを起動（非同期処理は SFN が担当）
         実行名に message_id を使用し、LINE リトライによる多重起動を防ぐ。

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

        _start_line_sm(event, settings=settings)


def _start_line_sm(
    event: LineWebhookEvent,
    *,
    settings: Settings,
) -> None:
    """LINE SM を message_id を実行名として直接起動する。

    LINE Platform は応答が遅延すると同一イベントをリトライするが、
    SFN は同名実行が存在する場合 ExecutionAlreadyExists を返すため、
    重複起動を自動的に排除できる。
    """
    assert event.message is not None
    assert settings.line_sm_arn, "LINE_SM_ARN が未設定です"

    # LINE SM は EventBridge 経由時と同じ $.detail.* 形式を期待する
    sfn_input = json.dumps(
        {
            "detail": {
                "message_type": event.message.type,
                "message_id": event.message.id,
                "text": event.message.text,
                "user_id": event.source.userId,
            }
        }
    )

    client = boto3.client("stepfunctions", region_name=settings.region)
    try:
        client.start_execution(
            stateMachineArn=settings.line_sm_arn,
            name=event.message.id,
            input=sfn_input,
        )
        logger.info(
            "LINE SM を起動: userId=%s, messageType=%s, messageId=%s",
            event.source.userId,
            event.message.type,
            event.message.id,
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ExecutionAlreadyExists":
            logger.info(
                "重複リクエストをスキップ（LINE リトライ）: messageId=%s",
                event.message.id,
            )
            return
        raise

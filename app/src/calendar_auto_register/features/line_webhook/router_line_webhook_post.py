"""LINE Webhook ルーター。"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request

from calendar_auto_register.core.line_signature import verify_line_signature
from calendar_auto_register.features.line_webhook.schemas_line_webhook_post import (
    LineWebhookRequest,
)
from calendar_auto_register.features.line_webhook.usecase_line_webhook_post import (
    process_webhook,
)

router = APIRouter(prefix="/line", tags=["line-webhook"])


@router.post("/webhook")
async def line_webhook_post(request: Request) -> dict[str, str]:
    """LINE Messaging API Webhook 受信エンドポイント。

    署名検証 -> パース -> usecase 呼び出し -> 200 OK

    設計判断:
    - Depends(get_settings) を使わず request.app.state.settings を参照する理由:
      request.body() を先に読む必要があり、FastAPI の Body パラメータと競合するため。
    - response_model を指定しない理由:
      LINE Platform はレスポンスボディを使用しない。空の dict を返せば十分。
    """
    from calendar_auto_register.core.settings import Settings
    settings: Settings = request.app.state.settings  # type: ignore[attr-defined]

    # 1. raw body 読み取り（署名検証に必要）
    body = await request.body()

    # 2. LINE_CHANNEL_SECRET の確認
    if not settings.line_channel_secret:
        raise HTTPException(status_code=500, detail="LINE_CHANNEL_SECRET が未設定です")

    # 3. 署名検証（Layer 1）
    signature = request.headers.get("X-Line-Signature", "")
    if not verify_line_signature(
        body=body,
        signature=signature,
        channel_secret=settings.line_channel_secret,
    ):
        raise HTTPException(status_code=403, detail="Invalid signature")

    # 4. パース
    webhook_request = LineWebhookRequest(**json.loads(body))

    # 5. 処理
    process_webhook(webhook_request, settings=settings)

    # 6. 200 OK（LINE Platform はレスポンスボディを使わない）
    return {}

# LINE Webhook実装 - 設計書

## 1. アーキテクチャ概要

### 1.1 運用構成

- **トリガー**: LINE Messaging API Webhook（API Gateway経由）
- **実行環境**: AWS Lambda (Python 3.12、既存Lambdaに統合)
- **タイムアウト**: 120秒
- **メモリ**: 1024MB

### 1.2 処理パイプライン

#### テキストメッセージフロー（3ステップ）

```
┌─────────────────┐
│ LINE Platform   │
└────┬────────────┘
     │ Webhook POST
     ▼
┌─────────────────────────────────┐
│ Lambda: POST /line/webhook       │
│ - 署名検証                       │
│ - イベント判定                   │
└────┬────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ Vision LLM (Bedrock Haiku)       │
│ - テキストからイベント抽出        │
└────┬────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ POST /calendar/events (既存)     │
│ - Google Calendar登録             │
└────┬────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ POST /line/notify (既存)         │
│ - LINE通知送信                    │
└─────────────────────────────────┘
```

#### 画像メッセージフロー（4ステップ）

```
┌─────────────────┐
│ LINE Platform   │
└────┬────────────┘
     │ Webhook POST
     ▼
┌─────────────────────────────────┐
│ Lambda: POST /line/webhook       │
│ - 署名検証                       │
│ - 画像メッセージ判定              │
└────┬────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ LINE Content API                 │
│ - 画像バイナリダウンロード        │
└────┬────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ Vision LLM (Bedrock Haiku)       │
│ - 画像から直接イベント抽出        │
└────┬────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ POST /calendar/events (既存)     │
└────┬────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ POST /line/notify (既存)         │
└─────────────────────────────────┘
```

---

## 2. コンポーネント設計

### 2.1 レイヤードアーキテクチャ

既存のアーキテクチャパターンを踏襲：

```
router層 (API endpoint)
    ↓
schemas層 (Pydantic models)
    ↓
usecase層 (business logic)
    ↓
clients層 (external API clients)
    ↓
config層 (settings)
```

### 2.2 新規ファイル構成

```
app/src/calendar_auto_register/
├── features/
│   └── line_webhook/
│       ├── __init__.py
│       ├── router_line_webhook_post.py      # Webhook受信ルーター
│       ├── schemas_line_webhook_post.py     # リクエスト/レスポンススキーマ
│       └── usecase_line_webhook_post.py     # ビジネスロジック
├── clients/
│   ├── line_content_client.py              # LINE Content API クライアント
│   └── bedrock_vision_client.py            # Bedrock Vision クライアント
└── middleware/
    └── line_signature_verifier.py          # 署名検証ミドルウェア
```

---

## 3. 詳細設計

### 3.1 Webhook受信処理

#### router_line_webhook_post.py

```python
from fastapi import APIRouter, Request, HTTPException, Depends
from calendar_auto_register.features.line_webhook.schemas_line_webhook_post import (
    LineWebhookRequest,
    LineWebhookResponse
)
from calendar_auto_register.features.line_webhook.usecase_line_webhook_post import (
    LineWebhookUsecase
)
from calendar_auto_register.middleware.line_signature_verifier import verify_line_signature

router = APIRouter()

@router.post("/line/webhook", response_model=LineWebhookResponse)
async def line_webhook_post(
    request: Request,
    webhook_request: LineWebhookRequest,
    usecase: LineWebhookUsecase = Depends()
):
    """LINE Messaging API Webhook受信"""
    # 署名検証
    signature = request.headers.get("X-Line-Signature")
    body = await request.body()

    if not verify_line_signature(body, signature, settings.LINE_CHANNEL_SECRET):
        raise HTTPException(status_code=403, detail="Invalid signature")

    # イベント処理
    await usecase.handle_webhook_events(webhook_request.events)

    return LineWebhookResponse()
```

---

### 3.2 署名検証

#### middleware/line_signature_verifier.py

```python
import hmac
import hashlib
import base64

def verify_line_signature(body: bytes, signature: str, channel_secret: str) -> bool:
    """
    LINE Webhook署名検証

    Args:
        body: リクエストボディ（bytes）
        signature: X-Line-Signatureヘッダー値
        channel_secret: LINE Channel Secret

    Returns:
        True if valid, False otherwise
    """
    hash_digest = hmac.new(
        channel_secret.encode('utf-8'),
        body,
        hashlib.sha256
    ).digest()

    expected_signature = base64.b64encode(hash_digest).decode('utf-8')

    return hmac.compare_digest(signature, expected_signature)
```

---

### 3.3 Webhookイベント処理

#### usecase_line_webhook_post.py

```python
from calendar_auto_register.features.line_webhook.schemas_line_webhook_post import (
    LineMessageEvent
)
from calendar_auto_register.clients.line_content_client import LineContentClient
from calendar_auto_register.clients.bedrock_vision_client import BedrockVisionClient
from calendar_auto_register.features.llm_extract.usecase_llm_extract_post import (
    LlmExtractUsecase
)
from calendar_auto_register.features.calendar_events.usecase_calendar_events_post import (
    CalendarEventsUsecase
)
from calendar_auto_register.features.line_notify.usecase_line_notify_post import (
    LineNotifyUsecase
)

class LineWebhookUsecase:
    def __init__(
        self,
        line_content_client: LineContentClient,
        bedrock_vision_client: BedrockVisionClient,
        llm_extract_usecase: LlmExtractUsecase,
        calendar_events_usecase: CalendarEventsUsecase,
        line_notify_usecase: LineNotifyUsecase
    ):
        self.line_content_client = line_content_client
        self.bedrock_vision_client = bedrock_vision_client
        self.llm_extract_usecase = llm_extract_usecase
        self.calendar_events_usecase = calendar_events_usecase
        self.line_notify_usecase = line_notify_usecase

    async def handle_webhook_events(self, events: list[LineMessageEvent]):
        """Webhookイベントを順次処理"""
        for event in events:
            if event.type != "message":
                continue  # メッセージイベント以外はスキップ

            try:
                if event.message.type == "text":
                    await self._handle_text_message(event)
                elif event.message.type == "image":
                    await self._handle_image_message(event)
                else:
                    # 未対応メッセージタイプ
                    pass
            except Exception as e:
                # エラーをLINEで通知
                await self._notify_error(event, str(e))

    async def _handle_text_message(self, event: LineMessageEvent):
        """テキストメッセージ処理"""
        text = event.message.text

        # Vision LLMでイベント抽出
        events = await self.bedrock_vision_client.extract_events_from_text(text)

        # カレンダー登録
        results = await self.calendar_events_usecase.create_events(events)

        # LINE通知
        await self.line_notify_usecase.notify_results(results)

    async def _handle_image_message(self, event: LineMessageEvent):
        """画像メッセージ処理"""
        message_id = event.message.id

        # LINE Content APIで画像取得
        image_bytes = await self.line_content_client.get_message_content(message_id)

        # Vision LLMで直接イベント抽出
        events = await self.bedrock_vision_client.extract_events_from_image(image_bytes)

        # カレンダー登録
        results = await self.calendar_events_usecase.create_events(events)

        # LINE通知
        await self.line_notify_usecase.notify_results(results)

    async def _notify_error(self, event: LineMessageEvent, error_message: str):
        """エラー通知"""
        await self.line_notify_usecase.send_error_notification(error_message)
```

---

### 3.4 LINE Content API クライアント

#### clients/line_content_client.py

```python
import httpx
from calendar_auto_register.config.settings import settings

class LineContentClient:
    """LINE Content API クライアント"""

    BASE_URL = "https://api-data.line.me/v2/bot/message"

    def __init__(self):
        self.access_token = settings.LINE_CHANNEL_ACCESS_TOKEN

    async def get_message_content(self, message_id: str) -> bytes:
        """
        画像バイナリを取得

        Args:
            message_id: LINE message ID

        Returns:
            画像バイナリ（bytes）

        Raises:
            httpx.HTTPError: API呼び出し失敗
        """
        url = f"{self.BASE_URL}/{message_id}/content"
        headers = {"Authorization": f"Bearer {self.access_token}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.content
```

---

### 3.5 Bedrock Vision クライアント

#### clients/bedrock_vision_client.py

```python
import json
import base64
import boto3
from calendar_auto_register.config.settings import settings
from calendar_auto_register.features.calendar_events.schemas_calendar_events_post import (
    CalendarEvent
)

class BedrockVisionClient:
    """Bedrock Vision API クライアント"""

    def __init__(self):
        self.client = boto3.client('bedrock-runtime', region_name=settings.AWS_REGION)
        self.model_id = settings.BEDROCK_VISION_MODEL_ID

    async def extract_events_from_text(self, text: str) -> list[CalendarEvent]:
        """
        テキストからイベント抽出

        Args:
            text: 入力テキスト

        Returns:
            CalendarEventのリスト
        """
        prompt = self._build_extraction_prompt(text)

        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            })
        )

        result = json.loads(response['body'].read())
        extracted_text = result['content'][0]['text']

        # JSON解析してCalendarEventに変換
        events_data = json.loads(extracted_text)
        return [CalendarEvent(**event) for event in events_data]

    async def extract_events_from_image(self, image_bytes: bytes) -> list[CalendarEvent]:
        """
        画像から直接イベント抽出

        Args:
            image_bytes: 画像バイナリ

        Returns:
            CalendarEventのリスト
        """
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')

        prompt = self._build_extraction_prompt("")

        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_base64
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            })
        )

        result = json.loads(response['body'].read())
        extracted_text = result['content'][0]['text']

        # JSON解析してCalendarEventに変換
        events_data = json.loads(extracted_text)
        return [CalendarEvent(**event) for event in events_data]

    def _build_extraction_prompt(self, text: str) -> str:
        """イベント抽出プロンプト構築"""
        return f"""
この画像/テキストからカレンダーイベント情報を抽出してください。

【抽出対象】
- イベント名（summary）
- 開始日時（start.dateTime または start.date）
- 終了日時（end.dateTime または end.date）
- 場所（location）
- 説明（description）
- 支払い期限がある場合は別イベントとして追加

【出力形式】JSON配列
[
  {{
    "summary": "イベント名",
    "start": {{
      "dateTime": "2025-01-15T18:30:00+09:00",
      "timeZone": "Asia/Tokyo"
    }},
    "end": {{
      "dateTime": "2025-01-15T21:00:00+09:00",
      "timeZone": "Asia/Tokyo"
    }},
    "location": "場所",
    "description": "説明"
  }}
]

テキスト:
{text if text else "(画像から抽出)"}
"""
```

---

### 3.6 データモデル

#### schemas_line_webhook_post.py

```python
from pydantic import BaseModel, Field
from typing import Literal

class LineSource(BaseModel):
    """LINEメッセージソース"""
    type: Literal["user", "group", "room"]
    user_id: str = Field(alias="userId")

class LineMessage(BaseModel):
    """LINEメッセージ"""
    type: Literal["text", "image"]
    id: str
    text: str | None = None

class LineMessageEvent(BaseModel):
    """LINEメッセージイベント"""
    type: Literal["message"]
    message: LineMessage
    timestamp: int
    source: LineSource
    reply_token: str = Field(alias="replyToken")

class LineWebhookRequest(BaseModel):
    """LINE Webhook リクエスト"""
    destination: str
    events: list[LineMessageEvent]

class LineWebhookResponse(BaseModel):
    """LINE Webhook レスポンス（空）"""
    pass
```

---

## 4. エラーハンドリング戦略

### 4.1 段階的エラー対応

1. **署名検証失敗**: 403 Forbiddenを返却、CloudWatch Logsに記録
2. **LINE Content API失敗**: ユーザーに「画像取得に失敗しました」と通知
3. **Vision LLM失敗**: 最大5回リトライ（エクスポネンシャルバックオフ）
4. **Calendar API失敗**: 最大3回リトライ、失敗時はエラー詳細を通知
5. **LINE通知失敗**: CloudWatch Logsに記録（ユーザー通知不可）

### 4.2 リトライロジック

```python
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60)
)
async def extract_events_with_retry(client, image_bytes):
    """Vision LLM呼び出し（リトライ付き）"""
    return await client.extract_events_from_image(image_bytes)
```

---

## 5. テスト戦略

### 5.1 単体テスト（pytest）

**対象**:
- `verify_line_signature()` - 署名検証ロジック
- `LineContentClient.get_message_content()` - モックレスポンス
- `BedrockVisionClient.extract_events_from_text()` - モックレスポンス
- `BedrockVisionClient.extract_events_from_image()` - モックレスポンス

**ツール**:
- `pytest`
- `pytest-asyncio`
- `pytest-mock`
- `httpx.AsyncClient` モック

### 5.2 統合テスト

**シナリオ**:
1. テキストメッセージ → カレンダー登録 → 通知
2. 画像メッセージ → Vision LLM → カレンダー登録 → 通知
3. 署名検証失敗 → 403 Forbidden
4. Vision LLM失敗 → エラー通知

### 5.3 品質保証

- テストカバレッジ: **≥80%**
- mypy strict mode: **エラーゼロ**
- ruff: **エラーゼロ**

---

## 6. インフラ設定

### 6.1 API Gateway設定

**新規パス**: `POST /line/webhook`

**認証**: なし（署名検証をアプリケーション層で実施）

**タイムアウト**: 29秒（API Gatewayの制限）

### 6.2 IAM ポリシー追加

Lambda実行ロールに以下を追加：

```yaml
Policies:
  - Statement:
      - Effect: Allow
        Action:
          - bedrock:InvokeModel
        Resource:
          - arn:aws:bedrock:*::foundation-model/anthropic.claude-3-haiku-*
```

### 6.3 環境変数

| 変数名 | 説明 |
|---|---|
| `LINE_CHANNEL_SECRET` | Webhook署名検証用 |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Content API用 |
| `BEDROCK_VISION_MODEL_ID` | `anthropic.claude-3-haiku-20240307-v1:0` |

---

## 7. パフォーマンス目標

| メトリクス | 目標値 |
|---|---|
| Webhook応答時間 | 5秒以内 |
| テキストメッセージ処理 | 平均10秒 |
| 画像メッセージ処理 | 平均20秒 |
| Lambda実行時間 | 120秒以内 |
| Vision LLM呼び出し | 5秒以内 |

---

## 8. コスト試算

**月間想定**（個人利用）:
- Lambda実行: 200回/月 × 20秒 = 4,000秒
- Bedrock Vision (Haiku): 100回/月
- Bedrock LLM (Haiku): 100回/月
- Google Calendar API: 200回/月（無料枠）
- LINE Messaging API: 200通/月（無料枠）

**推定コスト**: $2-5/月

---

## 9. 監視・運用

### 9.1 CloudWatch メトリクス

| メトリクス | 閾値 | アラート |
|---|---|---|
| Lambda エラー率 | 5%以上 | CloudWatch Alarm |
| Webhook署名検証失敗 | 10件/時間 | CloudWatch Alarm |
| Vision LLM失敗率 | 10%以上 | CloudWatch Alarm |

### 9.2 ログ出力

- リクエストID付きトレーシング
- エラースタックトレース
- Vision LLM抽出結果
- Calendar API レスポンス

---

## 10. デプロイ計画

### 10.1 段階的リリース

**Phase 1**: テキストメッセージ対応
- Webhook受信
- 署名検証
- Vision LLM統合
- 既存フローとの統合

**Phase 2**: 画像メッセージ対応
- LINE Content API統合
- Vision LLM画像処理

**Phase 3**: 最適化
- パフォーマンスチューニング
- エラーハンドリング改善

---

## 11. 技術的制約

### 11.1 LINE Messaging API

- Webhook応答タイムアウト: **5秒**
- Content API画像保持期間: **数日間**
- 画像サイズ上限: **10MB**

### 11.2 Bedrock Vision

- 画像サイズ上限: **5MB**
- サポート形式: JPEG, PNG, GIF, WebP
- 最大トークン: 4096

### 11.3 API Gateway

- タイムアウト: **29秒**
- ペイロードサイズ: **10MB**

---

## 12. 参考資料

- [LINE Messaging API](https://developers.line.biz/ja/reference/messaging-api/)
- [AWS Bedrock Claude 3](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-anthropic-claude-messages.html)
- [Google Calendar API](https://developers.google.com/calendar/api/v3/reference)

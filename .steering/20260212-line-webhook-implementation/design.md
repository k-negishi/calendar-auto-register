# LINE Webhook実装 - 設計書

## 1. アーキテクチャ概要

### 1.1 運用構成

- **トリガー**: LINE Messaging API Webhook（API Gateway経由）
- **実行環境**: AWS Lambda (Python 3.12、既存Lambdaに統合)
- **タイムアウト**: 120秒
- **メモリ**: 1024MB

### 1.2 処理パイプライン

#### アーキテクチャパターン：非同期オーケストレーション

既存のメール処理フローと同様に、**Step Functions**を使用してオーケストレーション。

**重要**: LINE Webhookは5秒以内に応答が必要なため、Webhook受信後、即座に200 OKを返却し、Step Functionsを非同期起動する。

#### テキストメッセージフロー（Step Functions）

```
┌─────────────────┐
│ LINE Platform   │
└────┬────────────┘
     │ Webhook POST
     ▼
┌─────────────────────────────────┐
│ API Gateway                      │
│ POST /line/webhook               │
└────┬────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ Lambda: Webhook受信              │
│ - 署名検証                       │
│ - Step Functions起動             │
│ - 即座に 200 OK 返却             │
└────┬────────────────────────────┘
     │
     ▼ (非同期)
┌─────────────────────────────────┐
│ Step Functions                   │
│ LineWebhookWorkflow              │
└────┬────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ [Task 1]                         │
│ Lambda: Vision LLM呼び出し        │
│ - テキストからイベント抽出        │
└────┬────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ [Task 2]                         │
│ Lambda: POST /calendar/events    │
│ - Google Calendar登録             │
└────┬────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ [Task 3]                         │
│ Lambda: POST /line/notify        │
│ - LINE通知送信                    │
└─────────────────────────────────┘
```

### 1.3 実装アプローチ（TDD）

実装は Kent Beck の TDD を前提に進める。全ての機能追加・変更は、以下のサイクルを1単位として進行する。

1. **RED**
   - 期待仕様を先にテストとして記述し、失敗を確認する
   - 正常系だけでなく、署名不一致・外部API失敗・タイムアウトを先に固定化する
2. **GREEN**
   - 失敗テストを最短で通す最小実装を行う
   - 新規ロジックは副作用境界（HTTPクライアント、AWS SDK呼び出し）を薄く保つ
3. **REFACTOR**
   - 重複除去、責務分離、命名改善を実施する
   - テストの可読性と保守性（fixture整理、モック責務の明確化）を同時に改善する

**完了条件（各サイクル共通）**
- 追加したテストが再現性を持って成功する
- 既存テストが回帰なく成功する
- mypy/ruffの静的チェックを通過する

#### 画像メッセージフロー（Step Functions）

```
┌─────────────────┐
│ LINE Platform   │
└────┬────────────┘
     │ Webhook POST
     ▼
┌─────────────────────────────────┐
│ API Gateway                      │
│ POST /line/webhook               │
└────┬────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ Lambda: Webhook受信              │
│ - 署名検証                       │
│ - 画像メッセージ判定              │
│ - Step Functions起動             │
│ - 即座に 200 OK 返却             │
└────┬────────────────────────────┘
     │
     ▼ (非同期)
┌─────────────────────────────────┐
│ Step Functions                   │
│ LineWebhookWorkflow              │
└────┬────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ [Task 1]                         │
│ Lambda: LINE Content API         │
│ - 画像バイナリダウンロード        │
└────┬────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ [Task 2]                         │
│ Lambda: Vision LLM呼び出し        │
│ - 画像から直接イベント抽出        │
└────┬────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ [Task 3]                         │
│ Lambda: POST /calendar/events    │
└────┬────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ [Task 4]                         │
│ Lambda: POST /line/notify        │
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

### 3.3 Webhookイベント処理（Step Functions起動）

#### usecase_line_webhook_post.py

**重要**: Webhook受信後、Step Functionsを非同期起動し、即座に200 OKを返却する。

```python
import boto3
import json
import time
import random
from calendar_auto_register.features.line_webhook.schemas_line_webhook_post import (
    LineMessageEvent
)
from calendar_auto_register.config.settings import settings

class LineWebhookUsecase:
    """
    LINE Webhook受信後、Step Functionsを非同期起動するユースケース
    """
    def __init__(self):
        self.sfn_client = boto3.client('stepfunctions', region_name=settings.AWS_REGION)
        self.state_machine_arn = settings.LINE_WEBHOOK_STATE_MACHINE_ARN

    async def handle_webhook_events(self, events: list[LineMessageEvent]):
        """
        Webhookイベントを受け取り、Step Functionsを起動

        Args:
            events: LINE Webhookイベントリスト
        """
        for event in events:
            if event.type != "message":
                continue  # メッセージイベント以外はスキップ

            # Step Functions起動用のペイロード作成
            execution_input = {
                "event": event.dict(),
                "source": "line_webhook",
                "timestamp": int(time.time())
            }

            # 実行名生成（ユニーク性確保）
            execution_name = f"line-webhook-{int(time.time())}-{random.randint(1000, 9999)}"

            try:
                # Step Functions非同期起動
                response = self.sfn_client.start_execution(
                    stateMachineArn=self.state_machine_arn,
                    name=execution_name,
                    input=json.dumps(execution_input)
                )

                # ログ出力
                print(f"Step Functions started: {response['executionArn']}")

            except Exception as e:
                # 起動失敗時はログに記録（ユーザー通知は不可）
                print(f"Failed to start Step Functions: {str(e)}")
                # CloudWatch Alarmでモニタリング
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

### 3.7 Step Functions State Machine定義

#### infra/sam/statemachine/line_webhook_workflow.asl.json

Amazon States Language（ASL）でState Machineを定義。

```json
{
  "Comment": "LINE Webhook処理ワークフロー",
  "StartAt": "DetermineMessageType",
  "States": {
    "DetermineMessageType": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.event.message.type",
          "StringEquals": "text",
          "Next": "ExtractEventsFromText"
        },
        {
          "Variable": "$.event.message.type",
          "StringEquals": "image",
          "Next": "DownloadImage"
        }
      ],
      "Default": "UnsupportedMessageType"
    },
    "ExtractEventsFromText": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "${LambdaFunctionArn}",
        "Payload": {
          "body": {
            "text": "$.event.message.text"
          },
          "path": "/llm/extract-event",
          "httpMethod": "POST"
        }
      },
      "ResultPath": "$.extractedEvents",
      "Retry": [
        {
          "ErrorEquals": ["Lambda.ServiceException", "Lambda.SdkClientException"],
          "IntervalSeconds": 2,
          "MaxAttempts": 3,
          "BackoffRate": 2
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "Next": "NotifyError"
        }
      ],
      "Next": "CreateCalendarEvents"
    },
    "DownloadImage": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "${LambdaFunctionArn}",
        "Payload": {
          "body": {
            "message_id": "$.event.message.id"
          },
          "path": "/line/download-image",
          "httpMethod": "POST"
        }
      },
      "ResultPath": "$.imageData",
      "Retry": [
        {
          "ErrorEquals": ["Lambda.ServiceException"],
          "IntervalSeconds": 2,
          "MaxAttempts": 2,
          "BackoffRate": 2
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "Next": "NotifyError"
        }
      ],
      "Next": "ExtractEventsFromImage"
    },
    "ExtractEventsFromImage": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "${LambdaFunctionArn}",
        "Payload": {
          "body": {
            "image_bytes": "$.imageData.Payload.body.image_bytes"
          },
          "path": "/vision/extract-events",
          "httpMethod": "POST"
        }
      },
      "ResultPath": "$.extractedEvents",
      "Retry": [
        {
          "ErrorEquals": ["Lambda.ServiceException"],
          "IntervalSeconds": 2,
          "MaxAttempts": 5,
          "BackoffRate": 2
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "Next": "NotifyError"
        }
      ],
      "Next": "CreateCalendarEvents"
    },
    "CreateCalendarEvents": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "${LambdaFunctionArn}",
        "Payload": {
          "body": {
            "events": "$.extractedEvents.Payload.body.events"
          },
          "path": "/calendar/events",
          "httpMethod": "POST"
        }
      },
      "ResultPath": "$.calendarResults",
      "Retry": [
        {
          "ErrorEquals": ["Lambda.ServiceException"],
          "IntervalSeconds": 2,
          "MaxAttempts": 3,
          "BackoffRate": 2
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "Next": "NotifyError"
        }
      ],
      "Next": "NotifySuccess"
    },
    "NotifySuccess": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "${LambdaFunctionArn}",
        "Payload": {
          "body": {
            "results": "$.calendarResults.Payload.body.results"
          },
          "path": "/line/notify",
          "httpMethod": "POST"
        }
      },
      "End": true
    },
    "NotifyError": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "${LambdaFunctionArn}",
        "Payload": {
          "body": {
            "error_message": "$.Error"
          },
          "path": "/line/notify-error",
          "httpMethod": "POST"
        }
      },
      "End": true
    },
    "UnsupportedMessageType": {
      "Type": "Succeed",
      "Comment": "未対応のメッセージタイプ（スキップ）"
    }
  }
}
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
  - Statement:
      - Effect: Allow
        Action:
          - states:StartExecution
        Resource:
          - !GetAtt LineWebhookStateMachine.Arn
```

### 6.3 Step Functions設定

#### SAM template.yaml

```yaml
LineWebhookStateMachine:
  Type: AWS::Serverless::StateMachine
  Properties:
    Name: LineWebhookWorkflow
    DefinitionUri: statemachine/line_webhook_workflow.asl.json
    DefinitionSubstitutions:
      LambdaFunctionArn: !GetAtt CalendarAutoRegisterFunction.Arn
    Role: !GetAtt StepFunctionsRole.Arn
    Logging:
      Level: ALL
      IncludeExecutionData: true
      Destinations:
        - CloudWatchLogsLogGroup:
            LogGroupArn: !GetAtt LineWebhookWorkflowLogGroup.Arn
    Tracing:
      Enabled: true

StepFunctionsRole:
  Type: AWS::IAM::Role
  Properties:
    AssumeRolePolicyDocument:
      Version: "2012-10-17"
      Statement:
        - Effect: Allow
          Principal:
            Service: states.amazonaws.com
          Action: sts:AssumeRole
    Policies:
      - PolicyName: StepFunctionsExecutionPolicy
        PolicyDocument:
          Version: "2012-10-17"
          Statement:
            - Effect: Allow
              Action:
                - lambda:InvokeFunction
              Resource:
                - !GetAtt CalendarAutoRegisterFunction.Arn
            - Effect: Allow
              Action:
                - logs:CreateLogDelivery
                - logs:GetLogDelivery
                - logs:UpdateLogDelivery
                - logs:DeleteLogDelivery
                - logs:ListLogDeliveries
                - logs:PutResourcePolicy
                - logs:DescribeResourcePolicies
                - logs:DescribeLogGroups
              Resource: "*"
            - Effect: Allow
              Action:
                - xray:PutTraceSegments
                - xray:PutTelemetryRecords
              Resource: "*"

LineWebhookWorkflowLogGroup:
  Type: AWS::Logs::LogGroup
  Properties:
    LogGroupName: /aws/vendedlogs/states/LineWebhookWorkflow
    RetentionInDays: 7
```

### 6.4 環境変数

| 変数名 | 説明 |
|---|---|
| `LINE_CHANNEL_SECRET` | Webhook署名検証用 |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Content API用 |
| `BEDROCK_VISION_MODEL_ID` | `anthropic.claude-3-haiku-20240307-v1:0` |
| `LINE_WEBHOOK_STATE_MACHINE_ARN` | Step Functions State Machine ARN（SAMで自動設定） |
| `AWS_REGION` | AWSリージョン（例: `ap-northeast-1`） |

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
- **Step Functions**: 200実行/月 × 4ステップ = 800ステートトランジション
- Bedrock Vision (Haiku): 100回/月
- Bedrock LLM (Haiku): 100回/月
- Google Calendar API: 200回/月（無料枠）
- LINE Messaging API: 200通/月（無料枠）

**推定コスト**:
- Lambda: ~$0.50
- Step Functions: ~$0.02（最初の4,000ステートトランジションは無料枠）
- Bedrock Vision (Haiku): ~$0.40
- Bedrock LLM (Haiku): ~$0.25
- **合計: $1-2/月**

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

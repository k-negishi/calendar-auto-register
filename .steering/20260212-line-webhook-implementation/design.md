# LINE Webhook実装 - 設計書

## 1. アーキテクチャ概要

### 1.1 全体構成

本プロジェクトは以下の 3 層で構成される。

```
┌─────────────────────────────────────────────────────────┐
│  Lambdalith（単一 Lambda + FastAPI + Mangum）            │
│  ─ 各処理ステップを独立した HTTP API として提供          │
│  ─ ビジネスロジックはここに集約                         │
└─────────────────────────────────────────────────────────┘
             ▲ HTTP (API Gateway 経由)
             │  SFN HTTP Task で呼び出す
┌─────────────────────────────────────────────────────────┐
│  Step Functions（オーケストレーター）                    │
│  ─ Mail State Machine                                   │
│  ─ LINE State Machine                                   │
└─────────────────────────────────────────────────────────┘
             ▲ StartExecution
┌─────────────────────────────────────────────────────────┐
│  EventBridge                                            │
│  ─ S3 Event → Mail SM を起動                           │
│  ─ LINE Webhook → LINE SM を起動                       │
└─────────────────────────────────────────────────────────┘
```

**設計方針:**

- **Lambdalith** = 単一 Lambda が全 API ルートを処理（FastAPI + Mangum）。ビジネスロジックの単位は HTTP エンドポイント
- **SFN** = オーケストレーター。各ステップを HTTP Task で Lambdalith の API を順番に呼ぶ
- **EventBridge** = SFN の起動トリガー（S3 Event → Mail SM のみ）
- **Python 関数直接呼び出しによるオーケストレーションは行わない**。各ステップは API を経由する

### 1.2 メール処理フロー

```
SES → S3
  ↓ S3 Event Notification
EventBridge
  ↓ Rule: source=aws.s3, bucket=calendar-auto-register → StartExecution
Mail State Machine (Step Functions)
  → POST /mail/parse              （S3 bucket/key → NormalizedMail）
  → POST /llm/extract-event       （NormalizedMail → events）
  → POST /calendar/events         （events → results）
  → POST /line/notify             （results → LINE 通知）
```

### 1.3 LINE Webhook フロー

```
LINE Platform
  ↓ POST /line/webhook（X-Line-Signature ヘッダ付き）
API Gateway → Lambda（Lambdalith）
  ↓ [Layer 1] HMAC-SHA256 署名検証 → NG: 403
  ↓ [Layer 2] userId allowlist 検証 → NG: スキップ（200 OK）
  ↓ SFN.StartExecution(name=message_id)  ← 重複排除: 同一 message_id は ExecutionAlreadyExists で無視
  ↓ 200 OK ← LINE Platform に即返却

LINE State Machine (Step Functions)
  → Choice: message.type?
      text  → POST /llm/extract-event        （text → events）
      image → POST /llm/extract-event-image  （message_id → 画像DL → events）
  → POST /calendar/events
  → POST /line/notify
```

> **設計変更（2026-06-17）**: 当初は EvB.putEvents → EventBridge Rule → SFN の間接起動だったが、
> Lambda コールドスタートで LINE Platform がリトライし同一 message_id が二重起動する問題が判明。
> Lambda から SFN を直接 `StartExecution(name=message_id)` で起動する方式に変更。
> EventBridge の LINE Rule は不要となり削除。

### 1.4 実装アプローチ（TDD）

Kent Beck の TDD を前提に進める。

1. **RED** - 期待仕様を先にテストとして記述し、失敗を確認する
2. **GREEN** - テストを通す最小実装のみ行う
3. **REFACTOR** - 重複除去、責務分離、命名改善を実施する

---

## 2. エンドポイント設計

### 2.1 エンドポイント一覧

| Endpoint | Input | Output | 用途 |
|---|---|---|---|
| `POST /mail/parse` | S3 bucket/key | NormalizedMail | メール正規化（既存） |
| `POST /llm/extract-event` | text + 任意でメールコンテキスト | events | LLM 抽出（統合・拡張） |
| `POST /llm/extract-event-image` | message_id | events | 画像 LLM 抽出（新規） |
| `POST /calendar/events` | events | results | カレンダー登録（既存） |
| `POST /line/notify` | results | - | LINE 通知（既存） |
| `POST /line/webhook` | LINE Webhook body | 200 OK | Webhook 受付（新規・薄いGW） |

### 2.2 `POST /llm/extract-event` スキーマ統合

メールとテキストの両方を 1 エンドポイントで処理する。

```python
class LlmExtractEventRequest(BaseModel):
    # 必須（LINE テキスト / メール本文）
    text: str

    # メール固有（任意）
    html: str | None = None           # HTML 版。存在すれば前処理（タグ除去・Unsubscribe 削除）を適用
    from_addr: str | None = None      # LLM プロンプトのコンテキストとして使用
    subject: str | None = None
    received_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")
```

**コードパス:**

| リクエスト | 処理 |
|---|---|
| `text` のみ | `extract_events_from_raw_text(text)` ← LINE テキストパス |
| `text` + `from_addr` / `subject` 等 | `extract_events(NormalizedMail(...))` ← メールパス（前処理あり） |

**既存の `NormalizedMailModel` ラッパーは廃止。** `text` 必須という明確な入力契約に統一する。

### 2.3 `POST /llm/extract-event-image`（新規）

```python
class LlmExtractImageEventRequest(BaseModel):
    message_id: str    # LINE Content API のメッセージ ID
    model_config = ConfigDict(extra="forbid")

class LlmExtractImageEventResponse(BaseModel):
    events: list[GoogleCalendarEventModel]
```

**処理フロー:**

1. `line_client.get_message_content(message_id)` → `bytes`
2. `bedrock_client.invoke_model_with_image(image_bytes, prompt=CALENDAR_EVENT_EXTRACTION_SYSTEM)` → raw response
3. `_parse_llm_response(response)` → `list[GoogleCalendarEventModel]`
4. `normalize_event_to_half_width(event)` を各イベントに適用（D4）
5. リトライ: `@retry(stop=stop_after_attempt(5), wait=wait_exponential_jitter(1, 10))` (D5)

### 2.4 `POST /line/webhook`（薄い Gateway）

```python
@router.post("/webhook")
async def line_webhook_post(request: Request) -> dict:
    # 1. raw body 読み取り
    body = await request.body()

    # 2. LINE_CHANNEL_SECRET 確認
    if not settings.line_channel_secret:
        raise HTTPException(status_code=500, ...)

    # 3. [Layer 1] HMAC-SHA256 署名検証
    if not verify_line_signature(body=body, ...):
        raise HTTPException(status_code=403, ...)

    # 4. パース
    webhook_request = LineWebhookRequest(**json.loads(body))

    # 5. [Layer 2] userId チェック + SFN.StartExecution
    process_webhook(webhook_request, settings=settings)

    # 6. 200 OK（即返却）
    return {}
```

```python
def process_webhook(request: LineWebhookRequest, *, settings: Settings) -> None:
    """userId 検証 + SFN.StartExecution(name=message_id)。LLM/Calendar/LINE 通知はここでは行わない。"""
    for event in request.events:
        if event.type != "message" or event.message is None:
            continue

        # [Layer 2] userId allowlist
        if settings.allowlist_line_user_ids and \
                event.source.userId not in settings.allowlist_line_user_ids:
            logger.warning("未認可 userId: %s", event.source.userId)
            continue

        _start_line_sm(event, settings=settings)


def _start_line_sm(event: LineWebhookEvent, *, settings: Settings) -> None:
    """LINE SM を message_id を実行名として直接起動する。"""
    import boto3, json
    from botocore.exceptions import ClientError
    client = boto3.client("stepfunctions", region_name=settings.region)
    try:
        client.start_execution(
            stateMachineArn=settings.line_sm_arn,
            name=event.message.id,  # LINE message_id = 実行名 → 重複排除
            input=json.dumps({"detail": {
                "message_type": event.message.type,
                "message_id": event.message.id,
                "text": event.message.text,
                "user_id": event.source.userId,
            }}),
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ExecutionAlreadyExists":
            return  # LINE リトライによる重複を無視
        raise
```

---

## 3. セキュリティ設計

### 3.1 2 層防御（LINE Webhook）

```
[Layer 1] X-Line-Signature 検証 (router 層)
  HMAC-SHA256 で署名を検証。偽造 Webhook を完全遮断。
  → NG: 403 Forbidden（LINE Platform は再送しない）

[Layer 2] source.userId allowlist 検証 (usecase 層)
  allowlist_line_user_ids に含まれない userId のイベントをスキップ。
  LINE URL・Channel Secret 流出時の不正利用を防止。
  → NG: 200 OK（LINE 要件を満たす）+ WARNING ログ + StartExecution スキップ
```

### 3.2 SFN → API Gateway 認証

SFN HTTP Task は API Gateway を呼ぶ際に `X-API-Key` ヘッダを付与する。
API Key は SFN の State 定義の Parameters に SecureString 参照で設定する（SSM Parameter Store）。

---

## 4. SFN State Machine 設計

### 4.1 Mail State Machine

**トリガー:** EventBridge Rule（`source: aws.s3`, `detail-type: Object Created`）

```json
{
  "Comment": "Mail processing pipeline",
  "StartAt": "ParseMail",
  "States": {
    "ParseMail": {
      "Type": "Task",
      "Resource": "arn:aws:states:::http:invoke",
      "Parameters": {
        "ApiEndpoint": "${ApiBaseUrl}/mail/parse",
        "Method": "POST",
        "Headers": { "X-API-Key.$": "$.api_key" },
        "RequestBody.$": "$.s3_event"
      },
      "ResultPath": "$.normalized_mail",
      "Next": "ExtractEvents"
    },
    "ExtractEvents": {
      "Type": "Task",
      "Resource": "arn:aws:states:::http:invoke",
      "Parameters": {
        "ApiEndpoint": "${ApiBaseUrl}/llm/extract-event",
        "Method": "POST",
        "Headers": { "X-API-Key.$": "$.api_key" },
        "RequestBody.$": "$.normalized_mail"
      },
      "ResultPath": "$.events",
      "Next": "CreateCalendarEvents"
    },
    "CreateCalendarEvents": {
      "Type": "Task",
      "Resource": "arn:aws:states:::http:invoke",
      "Parameters": {
        "ApiEndpoint": "${ApiBaseUrl}/calendar/events",
        "Method": "POST",
        "Headers": { "X-API-Key.$": "$.api_key" },
        "RequestBody.$": "$.events"
      },
      "ResultPath": "$.results",
      "Next": "NotifyLine"
    },
    "NotifyLine": {
      "Type": "Task",
      "Resource": "arn:aws:states:::http:invoke",
      "Parameters": {
        "ApiEndpoint": "${ApiBaseUrl}/line/notify",
        "Method": "POST",
        "Headers": { "X-API-Key.$": "$.api_key" },
        "RequestBody.$": "$.results"
      },
      "End": true
    }
  }
}
```

### 4.2 LINE State Machine

**トリガー:** EventBridge Rule（`source: calendar-auto-register.line`）

```json
{
  "Comment": "LINE message processing pipeline",
  "StartAt": "CheckMessageType",
  "States": {
    "CheckMessageType": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.detail.message_type",
          "StringEquals": "text",
          "Next": "ExtractFromText"
        },
        {
          "Variable": "$.detail.message_type",
          "StringEquals": "image",
          "Next": "ExtractFromImage"
        }
      ],
      "Default": "Unsupported"
    },
    "ExtractFromText": {
      "Type": "Task",
      "Resource": "arn:aws:states:::http:invoke",
      "Parameters": {
        "ApiEndpoint": "${ApiBaseUrl}/llm/extract-event",
        "Method": "POST",
        "Headers": { "X-API-Key.$": "$.api_key" },
        "RequestBody": {
          "text.$": "$.detail.text"
        }
      },
      "ResultPath": "$.events",
      "Next": "CreateCalendarEvents"
    },
    "ExtractFromImage": {
      "Type": "Task",
      "Resource": "arn:aws:states:::http:invoke",
      "Parameters": {
        "ApiEndpoint": "${ApiBaseUrl}/llm/extract-event-image",
        "Method": "POST",
        "Headers": { "X-API-Key.$": "$.api_key" },
        "RequestBody": {
          "message_id.$": "$.detail.message_id"
        }
      },
      "ResultPath": "$.events",
      "Next": "CreateCalendarEvents"
    },
    "CreateCalendarEvents": {
      "Type": "Task",
      "Resource": "arn:aws:states:::http:invoke",
      "Parameters": {
        "ApiEndpoint": "${ApiBaseUrl}/calendar/events",
        "Method": "POST",
        "Headers": { "X-API-Key.$": "$.api_key" },
        "RequestBody.$": "$.events"
      },
      "ResultPath": "$.results",
      "Next": "NotifyLine"
    },
    "NotifyLine": {
      "Type": "Task",
      "Resource": "arn:aws:states:::http:invoke",
      "Parameters": {
        "ApiEndpoint": "${ApiBaseUrl}/line/notify",
        "Method": "POST",
        "Headers": { "X-API-Key.$": "$.api_key" },
        "RequestBody.$": "$.results"
      },
      "End": true
    },
    "Unsupported": {
      "Type": "Succeed"
    }
  }
}
```

---

## 5. 設計判断まとめ（D1〜D7 + 追加）

| ID | 決定 | 理由 |
|---|---|---|
| D1 | `CalendarEventModel(**e.model_dump())` 削除 | エイリアスなので変換不要 |
| D2 | `send_line_notification()` 直接使用 | `build_line_message` + 手動 push の重複排除 |
| D3 | `extract_events_from_raw_text()` 新設 | メール前処理（Unsubscribe 削除等）を LINE テキストに適用しない |
| D4 | `normalize_event_to_half_width()` を画像パスにも適用 | テキストパスとの一貫性 |
| D5 | 画像 LLM に `@retry` (tenacity, 5回) | テキストパスの LangChain retry と同一ポリシー |
| D6 | `allowlist_line_user_ids` による 2 層防御 | `allowlist_senders`（メール）と対称的な設計 |
| D7 | `_run_extraction_chain()` で LangChain チェーン共通化 | メール・LINE テキストで同一チェーンを共有 |
| D8 | SFN = オーケストレーター、EvB = トリガー | Python 関数直接呼び出しによるオーケストレーションを排除。各ステップが独立した HTTP API として存在することで単体テスト・再実行が容易 |
| D9 | `POST /llm/extract-event` をテキスト/メール共通化 | `text` 必須、メールコンテキストは任意。LINE テキスト・メールで分岐 |
| D10 | `POST /line/webhook` は SFN.StartExecution(name=message_id) のみ | LINE コールドスタートリトライによる二重起動を排除。ExecutionAlreadyExists で同一 message_id を自動スキップ。LLM/Calendar/通知は SFN が非同期で処理 |
| D11 | 2 つの SM（Mail SM / LINE SM）を別々に定義 | 入力スキーマが根本的に異なる。フローが独立して読みやすい |

---

## 6. インフラ設計

### 6.1 新規追加リソース（SAM）

```yaml
# EventBridge Rule: S3 → Mail SM
MailEventRule:
  Type: AWS::Events::Rule
  Properties:
    EventPattern:
      source: ["aws.s3"]
      detail-type: ["Object Created"]
      detail:
        bucket:
          name: [!Ref S3RawMailBucketName]
    Targets:
      - Arn: !GetAtt MailStateMachine.Arn
        RoleArn: !GetAtt EventBridgeRole.Arn

# EventBridge Rule: LINE Webhook → LINE SM
LineEventRule:
  Type: AWS::Events::Rule
  Properties:
    EventPattern:
      source: ["calendar-auto-register.line"]
    Targets:
      - Arn: !GetAtt LineStateMachine.Arn
        RoleArn: !GetAtt EventBridgeRole.Arn

# Mail State Machine
MailStateMachine:
  Type: AWS::Serverless::StateMachine
  Properties:
    Definition: ...  # 4.1 の ASL
    Policies:
      - Statement:
          Effect: Allow
          Action: states:InvokeHTTPEndpoint
          Resource: "*"

# LINE State Machine
LineStateMachine:
  Type: AWS::Serverless::StateMachine
  Properties:
    Definition: ...  # 4.2 の ASL
    Policies:
      - Statement:
          Effect: Allow
          Action: states:InvokeHTTPEndpoint
          Resource: "*"
```

### 6.2 Lambda IAM 追加

```yaml
# Lambda が LINE SM を直接起動できるよう追加（重複排除: name=message_id）
- Statement:
    Effect: Allow
    Action: "states:StartExecution"
    Resource: !Ref LineStateMachine

# Bedrock: Vision モデル追加
- Statement:
    Effect: Allow
    Action: "bedrock:InvokeModel"
    Resource:
      - !Sub "arn:aws:bedrock:${AWS::Region}::foundation-model/anthropic.claude-3-5-sonnet-20240620-v1:0"
      - !Sub "arn:aws:bedrock:${AWS::Region}::foundation-model/anthropic.claude-3-haiku-*"
```

### 6.3 環境変数（SSM dotenv 追記）

| 変数名 | 説明 | 区分 |
|---|---|---|
| `LINE_CHANNEL_SECRET` | Layer 1: HMAC-SHA256 署名検証 | **追加** |
| `ALLOWLIST_LINE_USER_IDS` | Layer 2: 許可 userId リスト（JSON 配列）| **追加** |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Push / Content API | 既存 |
| `LINE_USER_ID` | LINE 通知先 | 既存 |
| `BEDROCK_MODEL_ID` | テキスト + 画像兼用モデル ID | 既存 |
| `API_KEY` | SFN → API GW 認証 | 既存（要 SFN 側設定） |

---

## 7. テスト戦略

### 7.1 単体テスト（モック使用）

| テスト対象 | 確認内容 |
|---|---|
| `verify_line_signature()` | 正常/不正署名 |
| `process_webhook()` | userId check + StartExecution(name=message_id) 呼び出し |
| `POST /line/webhook` router | 署名 NG→403、secret 未設定→500、正常→200 |
| `POST /llm/extract-event` | text のみ→raw text パス、mail フィールドあり→mail パス |
| `POST /llm/extract-event-image` | message_id → LINE DL → Bedrock → events |

### 7.2 統合テスト（FastAPI TestClient）

| シナリオ | 期待結果 |
|---|---|
| 正常テキスト Webhook | 200 OK + StartExecution 呼び出し |
| 正常画像 Webhook | 200 OK + StartExecution 呼び出し |
| 署名検証失敗 | 403 |
| 未認可 userId | 200 OK（StartExecution されない）|
| events 空配列 | 200 OK |
| LINE_CHANNEL_SECRET 未設定 | 500 |

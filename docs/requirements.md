# カレンダー自動登録システム 要求仕様書

## 1. プロジェクト概要

### 1.1 目的
LINEメッセージからカレンダーイベント情報を自動抽出し、Google Calendarに登録、結果をLINEで通知するシステム。

### 1.2 システム名
Calendar Auto Register

### 1.3 対象ユーザー
個人ユーザー（LINE連携可能なユーザー）

---

## 2. 既存システムの概要

### 2.1 現在の機能（メールベースフロー）

```
メール受信（S3） → メール解析 → LLM予定抽出 → カレンダー登録 → LINE通知
```

#### 2.1.1 実装済みエンドポイント

| エンドポイント | メソッド | 機能 |
|---|---|---|
| `/mail/parse` | POST | S3からメール取得・解析 |
| `/llm/extract-event` | POST | Bedrock LLMでイベント抽出 |
| `/calendar/events` | POST | Google Calendarに登録 |
| `/line/notify` | POST | LINE通知送信 |
| `/healthz` | GET | ヘルスチェック |

#### 2.1.2 主要機能

**メール解析**
- S3から`.eml`ファイル取得
- HTML/テキスト本文抽出
- 添付ファイル名リスト化
- 送信元ドメインのホワイトリストチェック

**LLM予定抽出**
- AWS Bedrock (Claude Haiku) による自然言語処理
- メール本文からイベント情報の構造化抽出
  - イベント名、日時、場所、説明
  - 支払い期限の自動検出（別イベントとして追加）
- 全角→半角の自動正規化
- 最大5回リトライ（エクスポネンシャルバックオフ）

**カレンダー登録**
- Google Calendar API によるイベント作成
- 重複チェック（±15分の時間窓で同名イベント検索）
- 終日イベント/時刻指定イベントの自動判別
- タイムゾーン: Asia/Tokyo 固定
- イベント名に `⚙️` プレフィックス自動付与
- バルク登録対応（複数イベント同時処理）

**LINE通知**
- LINE Messaging API によるプッシュ通知
- 登録結果サマリー（成功/重複/失敗件数）
- イベント詳細（日時、場所、エラー情報）

#### 2.1.3 技術スタック

**アプリケーション**
- Python 3.12
- FastAPI 0.115+
- Pydantic 2.8+
- LangChain 1.2+ / LangChain-aws 1.2+
- Mangum（ASGI to Lambda アダプター）

**外部API**
- Google Calendar API
- AWS Bedrock (Claude Haiku)
- LINE Messaging API

**インフラ**
- AWS Lambda (Docker Image, arm64)
- Amazon S3（RAWメール保存）
- AWS Systems Manager Parameter Store（環境変数管理）
- API Gateway（HTTPエンドポイント）

**開発環境**
- uv（パッケージマネージャー）
- Docker / Docker Compose
- pytest / mypy / ruff
- GitHub Actions（CI/CD）

---

## 3. 新規要件：LINEメッセージ受信フロー

### 3.1 機能概要

```
LINE受信 → Webhook処理 → テキスト・画像解析 → LLM予定抽出 → カレンダー登録 → LINE通知
```

### 3.2 ユースケース

#### UC-1: テキストメッセージからカレンダー登録

**トリガー**: ユーザーがLINE BOTにテキストメッセージを送信

**前提条件**:
- ユーザーがLINE BOTと友だち登録済み
- メッセージにイベント情報が含まれる（例: "明日14時から営業会議"）

**フロー**:
1. LINE Messaging APIからWebhookを受信
2. Webhook署名検証
3. テキストメッセージを抽出
4. LLM（Bedrock）でイベント情報を抽出
5. Google Calendarに登録（重複チェック含む）
6. 登録結果をLINEで通知

**成功時の出力**:
```
カレンダー自動登録 結果

🧾 サマリ
登録 1件 / 重複 0件 / 失敗 0件

🔍 詳細
登録　⚙️ 営業会議
日時　2024-12-26 14:00-15:00
```

**失敗時の出力**:
```
カレンダー自動登録 結果

🧾 サマリ
登録 0件 / 重複 0件 / 失敗 1件

🔍 詳細
失敗　営業会議
エラー　イベント情報を抽出できませんでした
```

---

#### UC-2: 画像メッセージからカレンダー登録

**トリガー**: ユーザーがLINE BOTに画像を送信（スクリーンショット、チラシ、招待状など）

**前提条件**:
- ユーザーがLINE BOTと友だち登録済み
- 画像にイベント情報のテキストが含まれる

**フロー**:
1. LINE Messaging APIからWebhookを受信
2. Webhook署名検証
3. 画像メッセージIDを取得
4. LINE Content APIで画像バイナリをダウンロード
5. 画像をS3に一時保存（オプション）
6. OCR/Vision APIで画像からテキスト抽出
   - **選択肢1**: AWS Textract
   - **選択肢2**: Bedrock Vision (Claude 3 Opus/Sonnet)
   - **選択肢3**: Google Cloud Vision API
7. 抽出したテキストをLLMでイベント情報に構造化
8. Google Calendarに登録（重複チェック含む）
9. 登録結果をLINEで通知

**成功時の出力**:
```
カレンダー自動登録 結果

🧾 サマリ
登録 2件 / 重複 0件 / 失敗 0件

🔍 詳細
登録　⚙️ 新年会
日時　2025-01-15 18:30-21:00
場所　渋谷〇〇ビル 3F

登録　⚙️ 新年会 参加費支払い期限
日時　2025-01-10
```

---

#### UC-3: 複数メッセージの一括処理

**トリガー**: ユーザーが短時間に複数のテキスト/画像を送信

**フロー**:
- 各メッセージを個別に処理
- 同時実行を避けるため、順次処理またはキューイング
- 各メッセージごとに結果を通知

---

### 3.3 非機能要件

#### 3.3.1 パフォーマンス
- Webhook応答時間: 5秒以内（LINE Messaging API タイムアウト回避）
- 画像処理時間: 30秒以内
- Lambda最大実行時間: 120秒

#### 3.3.2 セキュリティ
- Webhook署名検証必須（LINE Channel Secret使用）
- 画像の一時保存はプライベートS3バケット
- S3オブジェクトは24時間後に自動削除（ライフサイクルポリシー）
- API Key認証（既存ミドルウェア継続使用）

#### 3.3.3 可用性
- エラー時でもユーザーへのフィードバック必須
- リトライ可能なエラーは自動リトライ
- CloudWatch Logsによるエラートラッキング

#### 3.3.4 保守性
- 既存のアーキテクチャパターンを踏襲
- テストカバレッジ維持
- 型安全性（mypy strict mode）

---

## 4. 新規実装の詳細設計

### 4.1 新規エンドポイント

#### 4.1.1 LINE Webhook受信

**エンドポイント**: `POST /line/webhook`

**リクエスト**:
```json
{
  "destination": "xxxxxxxxxx",
  "events": [
    {
      "type": "message",
      "message": {
        "type": "text",
        "id": "1234567890",
        "text": "明日14時から営業会議"
      },
      "timestamp": 1640000000000,
      "source": {
        "type": "user",
        "userId": "U1234567890abcdef"
      },
      "replyToken": "xxxxx"
    }
  ]
}
```

**ヘッダー**:
- `X-Line-Signature`: 署名（HMAC-SHA256）

**処理**:
1. 署名検証
2. イベントタイプ判定（message/follow/unfollowなど）
3. メッセージタイプ判定（text/image/videoなど）
4. 非同期処理キック（Lambda非同期呼び出しまたはSQS）
5. 即座に200 OKを返却

**レスポンス**: `200 OK` (空ボディ)

---

#### 4.1.2 画像からテキスト抽出

**エンドポイント**: `POST /vision/extract-text`

**リクエスト**:
```json
{
  "image_source": {
    "type": "line_message",
    "message_id": "1234567890"
  }
}
```

または

```json
{
  "image_source": {
    "type": "s3",
    "bucket": "my-bucket",
    "key": "images/example.jpg"
  }
}
```

**レスポンス**:
```json
{
  "extracted_text": "イベント名: 新年会\n日時: 2025年1月15日 18:30-21:00\n場所: 渋谷〇〇ビル 3F\n参加費: ¥5,000（1月10日までに振込）"
}
```

---

### 4.2 データモデル

#### 4.2.1 LINE Webhook Event（Pydantic）

```python
class LineMessageEvent(BaseModel):
    type: Literal["message"]
    message: LineMessage
    timestamp: int
    source: LineSource
    reply_token: str

class LineMessage(BaseModel):
    type: Literal["text", "image", "video", "audio", "file", "location", "sticker"]
    id: str
    text: str | None = None  # type="text"の場合

class LineSource(BaseModel):
    type: Literal["user", "group", "room"]
    user_id: str
```

#### 4.2.2 画像解析結果

```python
class ExtractedText(BaseModel):
    text: str
    confidence: float | None = None
    method: Literal["textract", "bedrock_vision", "google_vision"]
```

---

### 4.3 クライアント実装

#### 4.3.1 LINE Content API Client

**ファイル**: `app/src/calendar_auto_register/clients/line_content_client.py`

**機能**:
- LINE Content APIから画像バイナリ取得
- `GET https://api-data.line.me/v2/bot/message/{messageId}/content`
- Authorization: `Bearer {LINE_CHANNEL_ACCESS_TOKEN}`

**メソッド**:
```python
def get_message_content(message_id: str, access_token: str) -> bytes:
    """画像バイナリを取得"""
    pass
```

---

#### 4.3.2 Vision API Client（画像解析）

**ファイル**: `app/src/calendar_auto_register/clients/vision_client.py`

**選択肢1: AWS Textract**
```python
def extract_text_textract(image_bytes: bytes, region: str) -> str:
    """Textractでテキスト抽出"""
    client = boto3.client('textract', region_name=region)
    response = client.detect_document_text(
        Document={'Bytes': image_bytes}
    )
    # Block抽出・テキスト結合
    pass
```

**選択肢2: Bedrock Vision（推奨）**
```python
def extract_text_bedrock_vision(image_bytes: bytes, model_id: str, region: str) -> str:
    """Bedrock Vision (Claude 3)でテキスト抽出"""
    client = boto3.client('bedrock-runtime', region_name=region)
    # Base64エンコード
    image_base64 = base64.b64encode(image_bytes).decode('utf-8')

    response = client.invoke_model(
        modelId=model_id,  # e.g., "anthropic.claude-3-sonnet-20240229-v1:0"
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
                            "text": "この画像からイベント情報（日時、場所、イベント名など）を抽出してください。"
                        }
                    ]
                }
            ]
        })
    )
    # レスポンスパース
    pass
```

---

### 4.4 フィーチャー実装

#### 4.4.1 LINE Webhook処理

**ディレクトリ**: `app/src/calendar_auto_register/features/line_webhook/`

**ファイル**:
- `router_line_webhook_post.py` - ルーター
- `schemas_line_webhook_post.py` - リクエスト/レスポンススキーマ
- `usecase_line_webhook_post.py` - ビジネスロジック

**処理フロー**:
1. 署名検証（`X-Line-Signature` vs HMAC-SHA256）
2. イベントタイプ判定
   - `message` → メッセージ処理
   - `follow` / `unfollow` → ログのみ
3. メッセージタイプ判定
   - `text` → テキスト処理フロー
   - `image` → 画像処理フロー
   - その他 → 未対応メッセージ
4. オーケストレーション
   - テキスト抽出 → LLM抽出 → カレンダー登録 → LINE通知
5. エラーハンドリング
   - ユーザーにエラーメッセージ返信

---

#### 4.4.2 Vision抽出

**ディレクトリ**: `app/src/calendar_auto_register/features/vision_extract/`

**ファイル**:
- `router_vision_extract_post.py`
- `schemas_vision_extract_post.py`
- `usecase_vision_extract_post.py`

**処理**:
1. 画像ソース判定（LINE / S3）
2. 画像バイナリ取得
3. Vision APIでテキスト抽出
4. テキスト返却

---

### 4.5 環境変数追加

#### 4.5.1 新規環境変数

| 変数名 | 説明 | 例 |
|---|---|---|
| `LINE_CHANNEL_SECRET` | Webhook署名検証用シークレット | `abcdef1234567890...` |
| `VISION_METHOD` | 画像解析方法 | `bedrock_vision` / `textract` / `google_vision` |
| `BEDROCK_VISION_MODEL_ID` | Bedrock Visionモデル | `anthropic.claude-3-sonnet-20240229-v1:0` |
| `S3_IMAGE_BUCKET` | 画像一時保存バケット | `my-calendar-images` |

#### 4.5.2 既存環境変数（継続使用）

- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_USER_ID`
- `CALENDAR_ID`
- `GOOGLE_CREDENTIALS`
- `BEDROCK_MODEL_ID`（テキスト抽出用）

---

## 5. インフラ設定

### 5.1 AWS リソース追加

#### 5.1.1 S3 バケット（画像一時保存）

**バケット名**: `calendar-auto-register-images-{ACCOUNT_ID}`

**設定**:
- プライベートバケット
- ライフサイクルポリシー: 24時間後に自動削除
- 暗号化: AES-256

**SAM template.yaml 追加**:
```yaml
ImageBucket:
  Type: AWS::S3::Bucket
  Properties:
    BucketName: !Sub 'calendar-auto-register-images-${AWS::AccountId}'
    PublicAccessBlockConfiguration:
      BlockPublicAcls: true
      BlockPublicPolicy: true
      IgnorePublicAcls: true
      RestrictPublicBuckets: true
    LifecycleConfiguration:
      Rules:
        - Id: DeleteAfter24Hours
          Status: Enabled
          ExpirationInDays: 1
```

---

#### 5.1.2 IAM ポリシー追加

**Lambda実行ロール**:
```yaml
Policies:
  - S3ReadPolicy:
      BucketName: !Ref ImageBucket  # 画像バケット読み書き
  - Statement:
      - Effect: Allow
        Action:
          - bedrock:InvokeModel
        Resource:
          - arn:aws:bedrock:*::foundation-model/anthropic.claude-3-sonnet-*  # Vision用
  - Statement:
      - Effect: Allow
        Action:
          - textract:DetectDocumentText  # Textract使用の場合
        Resource: '*'
```

---

#### 5.1.3 API Gateway設定

**新規パス**: `POST /line/webhook`

**認証**: なし（署名検証をアプリケーション層で実施）

**タイムアウト**: 29秒（API Gatewayの制限）

---

### 5.2 LINE Messaging API設定

#### 5.2.1 Webhook URL

**URL**: `https://{API_GATEWAY_ENDPOINT}/line/webhook`

**設定場所**: LINE Developers Console > Messaging API > Webhook URL

**Webhook送信**: 有効化

**Webhook再送**: 有効化（障害時のリトライ）

---

#### 5.2.2 必要な権限

- メッセージ送受信
- 画像コンテンツ取得

---

## 6. データフロー図

### 6.1 テキストメッセージフロー

```
┌─────────┐
│ユーザー │
└────┬────┘
     │ テキスト送信
     ▼
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
│ Lambda (FastAPI)                 │
│ - 署名検証                       │
│ - イベント判定                   │
└────┬────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ POST /llm/extract-event          │
│ (既存エンドポイント)              │
│ - Bedrock LLM呼び出し             │
│ - イベント情報抽出                │
└────┬────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ POST /calendar/events            │
│ (既存エンドポイント)              │
│ - 重複チェック                    │
│ - Google Calendar登録             │
└────┬────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ POST /line/notify                │
│ (既存エンドポイント)              │
│ - LINE通知送信                    │
└────┬────────────────────────────┘
     │
     ▼
┌─────────┐
│ユーザー │ ← 結果通知
└─────────┘
```

---

### 6.2 画像メッセージフロー

```
┌─────────┐
│ユーザー │
└────┬────┘
     │ 画像送信
     ▼
┌─────────────────┐
│ LINE Platform   │
└────┬────────────┘
     │ Webhook POST (message_id含む)
     ▼
┌─────────────────────────────────┐
│ API Gateway                      │
│ POST /line/webhook               │
└────┬────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ Lambda (FastAPI)                 │
│ - 署名検証                       │
│ - 画像タイプ判定                 │
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
│ POST /vision/extract-text        │
│ (新規エンドポイント)              │
│ - Bedrock Vision / Textract      │
│ - テキスト抽出                    │
└────┬────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ POST /llm/extract-event          │
│ - 抽出テキストからイベント情報    │
└────┬────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ POST /calendar/events            │
│ - Google Calendar登録             │
└────┬────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ POST /line/notify                │
│ - LINE通知送信                    │
└────┬────────────────────────────┘
     │
     ▼
┌─────────┐
│ユーザー │ ← 結果通知
└─────────┘
```

---

## 7. エラーハンドリング

### 7.1 エラーケース

| エラー | 原因 | 対応 |
|---|---|---|
| 署名検証失敗 | 不正なWebhook | 403 Forbidden、ログ記録 |
| LINE Content API失敗 | メッセージ期限切れ | エラー通知をLINE送信 |
| Vision API失敗 | 画像読み取り不可 | エラー通知をLINE送信 |
| LLM抽出失敗 | イベント情報なし | エラー通知をLINE送信 |
| Calendar API失敗 | 認証エラー | CloudWatchアラート、ユーザーに通知 |
| タイムアウト | 処理時間超過 | 非同期処理への切り替え検討 |

---

### 7.2 リトライポリシー

| 処理 | リトライ回数 | バックオフ |
|---|---|---|
| LLM抽出 | 5回 | エクスポネンシャル（既存） |
| Google Calendar登録 | 3回 | 2秒間隔 |
| LINE通知 | 3回 | 2秒間隔 |
| Vision API | 2回 | 3秒間隔 |

---

## 8. テスト計画

### 8.1 単体テスト

**対象**:
- 署名検証ロジック
- LINE Webhook パース
- Vision API クライアント
- 画像処理フロー

**ツール**: pytest

---

### 8.2 統合テスト

**シナリオ**:
1. テキストメッセージ → カレンダー登録 → 通知
2. 画像メッセージ → OCR → カレンダー登録 → 通知
3. エラーケース（署名失敗、画像読み取り失敗）

**モック**:
- LINE Messaging API
- Bedrock Vision
- Google Calendar API

---

### 8.3 E2Eテスト

**環境**: ステージング環境（AWS SAM デプロイ）

**手順**:
1. 実際のLINE BOTにメッセージ送信
2. カレンダーイベント登録確認
3. LINE通知受信確認

---

## 9. デプロイ計画

### 9.1 段階的リリース

**Phase 1**: テキストメッセージ対応
- Webhook受信
- テキスト抽出
- 既存フローとの統合

**Phase 2**: 画像メッセージ対応
- Vision API統合
- 画像処理フロー

**Phase 3**: 最適化
- パフォーマンスチューニング
- エラーハンドリング改善

---

### 9.2 ロールバック計画

- SAM CloudFormationスタックのバージョン管理
- 前バージョンへの即座のロールバック可能
- LINE Webhook URLの切り替え

---

## 10. 運用・監視

### 10.1 監視項目

| メトリクス | 閾値 | アラート |
|---|---|---|
| Lambda エラー率 | 5%以上 | CloudWatch Alarm |
| Lambda実行時間 | 100秒以上 | CloudWatch Alarm |
| Webhook署名検証失敗 | 10件/時間 | CloudWatch Alarm |
| Calendar登録失敗率 | 10%以上 | CloudWatch Alarm |

---

### 10.2 ログ

**CloudWatch Logs**:
- リクエストID付きトレーシング
- エラースタックトレース
- LLM抽出結果
- Calendar API レスポンス

---

### 10.3 コスト試算

**月間想定**:
- Lambda実行: 1,000回/月 × 30秒 = 30,000秒
- Bedrock Vision: 100回/月
- Bedrock LLM (Haiku): 1,000回/月
- Google Calendar API: 1,000回/月（無料枠）
- LINE Messaging API: 1,000通/月（無料枠）

**推定コスト**: $10-20/月

---

## 11. 今後の拡張可能性

### 11.1 機能拡張

- 音声メッセージ対応（Speech-to-Text）
- 動画メッセージ対応（フレーム抽出 + OCR）
- リマインダー設定
- カレンダー削除・編集機能
- 複数カレンダー対応

### 11.2 技術的改善

- SQS導入による非同期処理
- Step Functions によるオーケストレーション
- DynamoDBによるイベント履歴管理
- キャッシュ機能（ElastiCache）

---

## 12. 参考資料

### 12.1 API ドキュメント

- [LINE Messaging API](https://developers.line.biz/ja/reference/messaging-api/)
- [Google Calendar API](https://developers.google.com/calendar/api/v3/reference)
- [AWS Bedrock API](https://docs.aws.amazon.com/bedrock/latest/userguide/what-is-bedrock.html)
- [AWS Textract](https://docs.aws.amazon.com/textract/)

### 12.2 既存コードベース

- `/home/user/calendar-auto-register/app/src/calendar_auto_register/`
- `/home/user/calendar-auto-register/infra/sam/template.yaml`

---

## 13. 変更履歴

| 日付 | バージョン | 変更内容 | 作成者 |
|---|---|---|---|
| 2024-12-XX | 1.0 | 初版作成 | Claude |

---

**承認**:
- [ ] 要件定義完了
- [ ] 技術設計完了
- [ ] インフラ設計完了
- [ ] 実装開始承認

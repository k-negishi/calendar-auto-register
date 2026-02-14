# LINE Webhook実装 - 要求仕様書

## 概要

LINEメッセージ（テキスト・画像）からカレンダーイベント情報を自動抽出し、Google Calendarに登録、結果をLINEで通知するシステムを実装する。

## GitHub Issue

- 未紐付け（2026-02-14 時点）

## issue 内容

- タイトル: LINE Webhook実装
- 本文: LINEメッセージ（テキスト・画像）を入力として予定抽出し、Google Calendar登録とLINE通知まで完結させる
- ラベル: なし

## プロジェクトコンテキスト

既存のメールベースフローに加えて、LINEメッセージをトリガーとする新しいフローを追加する。

```
既存: メール受信（S3） → メール解析 → LLM予定抽出 → カレンダー登録 → LINE通知
新規: LINE受信 → Webhook処理 → テキスト・画像解析 → LLM予定抽出 → カレンダー登録 → LINE通知
```

## 実装方針

- Kent Beck の TDD（Test-Driven Development）で実装する
- RED → GREEN → REFACTOR のサイクルを全実装タスクで遵守する
- テストを先に書き、最小限の実装でパスさせてから設計改善を行う
- 1タスク1目的を徹底し、複数責務を同一サイクルに混在させない
- 外部API連携（LINE / Bedrock / Calendar）はモック前提で失敗系を先にテストする

## 主要機能

### 1. テキストメッセージ対応

**入力**: ユーザーがLINE BOTにテキストメッセージを送信（例: "明日14時から営業会議"）

**処理フロー**:
1. LINE Messaging APIからWebhookを受信
2. Webhook署名検証（HMAC-SHA256）
3. テキストメッセージを抽出
4. Vision LLM（Bedrock Claude 3 Haiku）で直接イベント情報を抽出
5. Google Calendarに登録（重複チェック含む）
6. 登録結果をLINEで通知

**成功時の出力例**:
```
カレンダー自動登録 結果

🧾 サマリ
登録 1件 / 重複 0件 / 失敗 0件

🔍 詳細
登録　⚙️ 営業会議
日時　2024-12-26 14:00-15:00
```

---

### 2. 画像メッセージ対応

**入力**: ユーザーがLINE BOTに画像を送信（スクリーンショット、チラシ、招待状など）

**処理フロー**:
1. LINE Messaging APIからWebhookを受信
2. Webhook署名検証
3. 画像メッセージIDを取得
4. LINE Content APIで画像バイナリをダウンロード
5. **Vision LLM（Bedrock Claude 3 Haiku）で直接画像からイベント情報を抽出**
   - OCRステップは不要（1ステップで完結）
6. Google Calendarに登録（重複チェック含む）
7. 登録結果をLINEで通知

**成功時の出力例**:
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

## 非機能要件

### パフォーマンス
- Webhook応答時間: **5秒以内**（LINE Messaging API タイムアウト回避）
- 画像処理時間: **30秒以内**
- Lambda最大実行時間: **120秒**

### セキュリティ
- Webhook署名検証必須（LINE Channel Secret使用）
- API Key認証（既存ミドルウェア継続使用）

### 可用性
- エラー時でもユーザーへのフィードバック必須
- リトライ可能なエラーは自動リトライ（最大5回、エクスポネンシャルバックオフ）
- CloudWatch Logsによるエラートラッキング

### 保守性
- 既存のアーキテクチャパターンを踏襲
- テストカバレッジ維持
- 型安全性（mypy strict mode）

---

## 技術選定：Vision LLM アプローチ（推奨）

### 選定理由

**1. シンプルなアーキテクチャ**
- 既存の `/llm/extract-event` と同じパターンで実装可能
- OCR→LLMの2ステップではなく、1ステップで完結

**2. 高い精度**
- LINEで送られてくる画像は多様（スクリーンショット、チラシ、手書きメモなど）
- Vision LLMは文脈を理解して柔軟に対応

**3. 開発効率**
- 既存のプロンプトエンジニアリング資産を活用
- `/vision/extract-text` エンドポイントは不要

**4. コスト**
- 個人利用レベル（月100-200枚）なら数十円程度
- Bedrock Claude 3 Haiku (Vision): ~$0.40/1000リクエスト

---

## 新規エンドポイント

### POST /line/webhook

**機能**: LINE Messaging APIからのWebhookを受信し、イベント処理をオーケストレーション

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

**レスポンス**: `200 OK` (空ボディ)

---

## データモデル

### LINE Webhook Event（Pydantic）

```python
class LineMessageEvent(BaseModel):
    type: Literal["message"]
    message: LineMessage
    timestamp: int
    source: LineSource
    reply_token: str

class LineMessage(BaseModel):
    type: Literal["text", "image"]
    id: str
    text: str | None = None  # type="text"の場合

class LineSource(BaseModel):
    type: Literal["user", "group", "room"]
    user_id: str
```

---

## 環境変数追加

| 変数名 | 説明 | 例 |
|---|---|---|
| `LINE_CHANNEL_SECRET` | Webhook署名検証用シークレット | `abcdef1234567890...` |
| `BEDROCK_VISION_MODEL_ID` | Bedrock Visionモデル | `anthropic.claude-3-haiku-20240307-v1:0` |

### 既存環境変数（継続使用）

- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_USER_ID`
- `CALENDAR_ID`
- `GOOGLE_CREDENTIALS`
- `BEDROCK_MODEL_ID`（テキスト抽出用）

---

## エラーハンドリング

| エラー | 原因 | 対応 |
|---|---|---|
| 署名検証失敗 | 不正なWebhook | 403 Forbidden、ログ記録 |
| LINE Content API失敗 | メッセージ期限切れ | エラー通知をLINE送信 |
| Vision LLM失敗 | 画像読み取り不可 | エラー通知をLINE送信 |
| LLM抽出失敗 | イベント情報なし | エラー通知をLINE送信 |
| Calendar API失敗 | 認証エラー | CloudWatchアラート、ユーザーに通知 |

---

## リトライポリシー

| 処理 | リトライ回数 | バックオフ |
|---|---|---|
| Vision LLM抽出 | 5回 | エクスポネンシャル |
| Google Calendar登録 | 3回 | 2秒間隔 |
| LINE通知 | 3回 | 2秒間隔 |

---

## 成功指標

- Webhook応答成功率: **≥95%**
- イベント抽出精度: **≥90%**
- カレンダー登録成功率: **≥95%**
- 実行時間: **平均20秒以内**
- テストカバレッジ: **≥80%**

---

## スコープ外

以下は今回の実装スコープには含まない：

- 音声メッセージ対応（Speech-to-Text）
- 動画メッセージ対応
- リマインダー設定
- カレンダー削除・編集機能
- 複数カレンダー対応
- SQS/Step Functions導入による非同期処理

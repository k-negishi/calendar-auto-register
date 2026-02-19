# プロジェクト用語集 (Glossary)

## 概要

このドキュメントは、Calendar Auto Registerプロジェクト内で使用される用語の定義を管理します。

**更新日**: 2026-02-15

## ドメイン用語

### カレンダー自動登録

**定義**: メールやLINEメッセージに含まれるイベント情報をLLMで自動抽出し、Google Calendarに登録する一連の処理

**説明**: ユーザーがメールを受信したり、LINE BOTにメッセージを送信すると、システムが自動的にイベント名・日時・場所を抽出し、Google Calendarに登録して結果をLINE通知する

**関連用語**: イベント抽出、重複チェック、LINE通知

**英語表記**: Calendar Auto Register

### イベント抽出

**定義**: 非構造化テキストまたは画像からイベント情報（イベント名、日時、場所、説明）を構造化データとして抽出する処理

**説明**: AWS Bedrock (Claude Haiku) を使用し、メール本文やLINEメッセージから日時・場所などを抽出する。支払い期限も自動検出して別イベントとして追加する

**関連用語**: LLM、Bedrock、構造化抽出

**英語表記**: Event Extraction

### 重複チェック

**定義**: カレンダー登録前に、同一イベントが既に登録されていないかを確認する処理

**説明**: イベント開始時刻の±15分の時間窓で同名イベントを検索し、重複を防止する

**関連用語**: カレンダー登録、Google Calendar API

**英語表記**: Duplicate Check

### Webhook署名検証

**定義**: LINE PlatformからのWebhookリクエストが正当なものであることを検証する処理

**説明**: LINE Channel Secretを鍵としてリクエストボディのHMAC-SHA256ハッシュを計算し、`X-Line-Signature` ヘッダーの値と比較する

**関連用語**: LINE Messaging API、HMAC-SHA256、Channel Secret

**英語表記**: Webhook Signature Verification

### NormalizedMail

**定義**: S3に保存された `.eml` ファイルから抽出・正規化されたメールデータ

**説明**: from_addr, subject, text, html, attachments等のフィールドを持つdataclass。メール解析の出力として、LLM抽出の入力となる

**関連用語**: メール解析、.eml

**使用例**:
- `POST /mail/parse` のレスポンスとして返却
- `POST /llm/extract-event` のリクエストとして入力

**英語表記**: Normalized Mail

### CalendarEvent

**定義**: Google Calendar APIに登録するイベント情報を表すデータモデル

**説明**: summary, start_at, end_at, timezone, location, descriptionを持つdataclass。終日イベントと時刻指定イベントの両方に対応

**関連用語**: GoogleCalendarEventModel、Google Calendar API

**英語表記**: Calendar Event

## 技術用語

### FastAPI

**定義**: Python用の高速なWebフレームワーク

**公式サイト**: https://fastapi.tiangolo.com/

**本プロジェクトでの用途**: APIエンドポイントの実装。Pydanticと統合してリクエスト/レスポンスの型安全なバリデーションを実現

**バージョン**: 0.115+

### Pydantic

**定義**: Pythonのデータバリデーションライブラリ

**公式サイト**: https://docs.pydantic.dev/

**本プロジェクトでの用途**: APIスキーマ定義 (`BaseModel`)、`ConfigDict(extra="forbid")` による厳密なバリデーション

**バージョン**: 2.8+

### Mangum

**定義**: PythonのASGIアプリケーションをAWS Lambdaで実行するためのアダプタ

**公式サイト**: https://mangum.fastapiexpert.com/

**本プロジェクトでの用途**: FastAPIアプリをLambda関数として実行するための変換層

**バージョン**: 0.17+

### LangChain

**定義**: LLMアプリケーション開発フレームワーク

**公式サイト**: https://python.langchain.com/

**本プロジェクトでの用途**: AWS Bedrock経由でClaude Haikuを呼び出し、テキストからイベント情報を構造化抽出

**バージョン**: 1.2+

### AWS Bedrock

**定義**: AWSが提供するフルマネージドのAI/ML基盤サービス

**公式サイト**: https://aws.amazon.com/bedrock/

**本プロジェクトでの用途**: Claude Haikuモデルによるテキストからのイベント抽出、Claude 3 Visionモデルによる画像からのテキスト抽出

**関連ドキュメント**: `docs/architecture.md`

### Google Calendar API

**定義**: Google Calendarのイベント操作を行うREST API

**公式サイト**: https://developers.google.com/calendar/api/v3/reference

**本プロジェクトでの用途**: イベントの作成、重複チェック（events.list + events.insert）

**バージョン**: v3

### LINE Messaging API

**定義**: LINEプラットフォーム上でメッセージの送受信を行うAPI

**公式サイト**: https://developers.line.biz/ja/reference/messaging-api/

**本プロジェクトでの用途**: Webhook受信（メッセージ受信）、Push Message（結果通知）、Content API（画像取得）

### AWS SAM (Serverless Application Model)

**定義**: サーバーレスアプリケーションのデプロイ・管理フレームワーク

**公式サイト**: https://aws.amazon.com/serverless/sam/

**本プロジェクトでの用途**: Lambda関数、API Gateway、IAMロールの定義・デプロイ (`infra/sam/template.yaml`)

### uv

**定義**: Rust製の高速Pythonパッケージマネージャー

**公式サイト**: https://docs.astral.sh/uv/

**本プロジェクトでの用途**: 依存関係管理、仮想環境管理、スクリプト実行 (`uv run pytest`, `uv run ruff` 等)

## 略語・頭字語

### LLM

**正式名称**: Large Language Model

**意味**: 大規模言語モデル。大量のテキストデータで訓練されたAIモデル

**本プロジェクトでの使用**: AWS Bedrock経由でClaude Haikuを使用し、テキストからイベント情報を抽出

### OCR

**正式名称**: Optical Character Recognition

**意味**: 光学文字認識。画像からテキストを抽出する技術

**本プロジェクトでの使用**: Bedrock Vision (Claude 3) による画像内テキストの抽出

### SSM

**正式名称**: AWS Systems Manager

**意味**: AWSリソースの管理サービス

**本プロジェクトでの使用**: Parameter Store (SecureString) でアプリケーション設定（dotenv）を暗号化保存

### ASGI

**正式名称**: Asynchronous Server Gateway Interface

**意味**: Pythonの非同期Webサーバーインターフェース仕様

**本プロジェクトでの使用**: FastAPIが準拠するインターフェース。Mangumを介してLambdaで実行

### HMAC

**正式名称**: Hash-based Message Authentication Code

**意味**: 秘密鍵とハッシュ関数を使ったメッセージ認証コード

**本プロジェクトでの使用**: LINE Webhook署名検証 (HMAC-SHA256)

## アーキテクチャ用語

### Lambdalith

**定義**: 単一のAWS Lambda関数に複数のAPIエンドポイントを持たせるアーキテクチャパターン

**本プロジェクトでの適用**: FastAPI + Mangumで単一Lambda上に `/healthz`, `/mail/parse`, `/llm/extract-event`, `/calendar/events`, `/line/notify`, `/line/webhook`, `/vision/extract-text` の7エンドポイントを配置

**関連コンポーネント**: Lambda, API Gateway, Mangum, FastAPI

```
API Gateway → Lambda (Mangum → FastAPI → 各エンドポイント)
```

### フィーチャーベースアーキテクチャ

**定義**: 機能（フィーチャー）単位でコードをモジュール化するアーキテクチャパターン

**本プロジェクトでの適用**: `features/` ディレクトリ内に各エンドポイントのrouter/schemas/usecaseを配置。各フィーチャーは独立して開発・テスト可能

**関連コンポーネント**: `features/mailparse_post/`, `features/llm_extract/`, `features/calendar_events/` 等

## ステータス・状態

### カレンダー登録結果ステータス

| ステータス | 意味 | 遷移条件 |
|----------|------|---------|
| `CREATED` | イベント登録成功 | Google Calendar APIで正常に作成された |
| `DUPLICATE` | 重複イベント | ±15分の時間窓で同名イベントが既に存在 |
| `FAILED` | 登録失敗 | API呼び出しエラー、バリデーションエラー |

## データモデル用語

### GoogleCalendarEventModel

**定義**: Google Calendar events.insert() API互換のPydanticスキーマ

**主要フィールド**:
- `summary`: イベント名
- `start`: 開始日時 (DateModel | DateTimeModel)
- `end`: 終了日時 (DateModel | DateTimeModel)
- `location`: 場所（任意）
- `description`: 説明（任意）

**関連エンティティ**: CalendarEvent, CalendarEventResult

### Settings

**定義**: アプリケーション全体で共有する設定値のdataclass

**主要フィールド**:
- `app_env`: 実行環境 ("local" / "prod")
- `region`: AWSリージョン
- `calendar_id`: Google Calendar ID
- `google_credentials`: Google認証情報JSON
- `bedrock_model_id`: BedrockモデルID
- `line_channel_access_token`: LINEアクセストークン
- `line_user_id`: 通知先ユーザーID

**制約**: `load_settings()` で一度だけ生成され `lru_cache` でキャッシュ

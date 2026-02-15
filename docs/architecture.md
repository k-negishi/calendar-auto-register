# 技術仕様書 (Architecture Design Document)

## テクノロジースタック

### 言語・ランタイム

| 技術 | バージョン | 選定理由 |
|------|-----------|----------|
| Python | 3.12 | 型ヒント機能が充実、LangChain/boto3エコシステムとの親和性が高い |
| uv | latest | 高速なパッケージ管理、pip互換で導入コストが低い |

### フレームワーク・ライブラリ

| 技術 | バージョン | 用途 | 選定理由 |
|------|-----------|------|----------|
| FastAPI | 0.115+ | APIフレームワーク | 非同期対応、Pydantic統合による型安全なスキーマ定義、自動OpenAPI生成 |
| Pydantic | 2.8+ | データバリデーション | FastAPIとの統合、高速バリデーション、JSON Schema生成 |
| Mangum | 0.17+ | Lambda ASGI アダプタ | FastAPIをAWS Lambda上で動作させるための変換層 |
| LangChain | 1.2+ | LLMインターフェース | Bedrock統合、プロンプト管理、出力パーサー |
| LangChain-aws | 1.2+ | AWS Bedrock統合 | LangChainからBedrockモデルを呼び出すためのプロバイダー |
| boto3 | 1.34+ | AWS SDK | S3/Bedrock/SSM/Textract APIアクセス |
| google-api-python-client | 2.132+ | Google Calendar API | イベントのCRUD操作 |
| google-auth | 2.35+ | Google認証 | サービスアカウント認証 |
| line-bot-sdk | 3.12+ | LINE Messaging API | Webhook検証、メッセージ送受信 |
| httpx | 0.27+ | HTTPクライアント | 非同期HTTP通信、LINE Content API画像取得 |
| beautifulsoup4 | 4.12+ | HTML解析 | メール本文のHTML→テキスト変換 |

### 開発ツール

| 技術 | バージョン | 用途 | 選定理由 |
|------|-----------|------|----------|
| uv | latest | パッケージ管理 | 高速な依存解決、pip互換 |
| pytest | 8.3+ | テストフレームワーク | Python標準テストフレームワーク、豊富なプラグイン |
| pytest-asyncio | 0.23+ | 非同期テスト | async/awaitテスト対応 |
| mypy | 1.11+ | 型チェック | 静的型解析でバグを事前検出 |
| ruff | 0.6+ | Linter/Formatter | Rust製高速リンター、Flake8/Black/isort統合 |
| Docker / Docker Compose | latest | コンテナ環境 | 開発・本番環境の統一 |

## アーキテクチャパターン

### Lambdalithパターン

単一のAWS Lambda関数上でFastAPIアプリケーションを動作させ、複数のAPIエンドポイントを提供するアーキテクチャ。

```
┌──────────────────────────────────────────┐
│  AWS Lambda (Docker Image, arm64)        │
│  ┌────────────────────────────────────┐  │
│  │  Mangum (ASGI Adapter)             │  │
│  │  ┌──────────────────────────────┐  │  │
│  │  │  FastAPI Application          │  │  │
│  │  │  ├─ /healthz                  │  │  │
│  │  │  ├─ /mail/parse               │  │  │
│  │  │  ├─ /llm/extract-event        │  │  │
│  │  │  ├─ /calendar/events          │  │  │
│  │  │  ├─ /line/notify              │  │  │
│  │  │  ├─ /line/webhook     (新規)  │  │  │
│  │  │  └─ /vision/extract-text(新規)│  │  │
│  │  └──────────────────────────────┘  │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

### フィーチャーベースアーキテクチャ

```
┌─────────────────────────────────────────────────┐
│  ミドルウェア層                                    │
│  (API Key認証, リクエストID, ロギング)              │
├─────────────────────────────────────────────────┤
│  フィーチャー層 (各機能が独立したモジュール)         │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │mailparse │ │llm_extract│ │calendar_events  │ │
│  │  router  │ │  router   │ │  router          │ │
│  │  schemas │ │  schemas  │ │  schemas         │ │
│  │  usecase │ │  usecase  │ │  usecase         │ │
│  └──────────┘ └──────────┘ └──────────────────┘ │
│  ┌──────────┐ ┌───────────┐ ┌────────────────┐  │
│  │line_notify│ │line_webhook│ │vision_extract │  │
│  │  router   │ │  router    │ │  router        │  │
│  │  schemas  │ │  schemas   │ │  schemas       │  │
│  │  usecase  │ │  usecase   │ │  usecase       │  │
│  └──────────┘ └───────────┘ └────────────────┘  │
├─────────────────────────────────────────────────┤
│  共有層 (shared/)                                 │
│  schemas/calendar.py, schemas/calendar_events.py │
├─────────────────────────────────────────────────┤
│  クライアント層 (clients/)                         │
│  bedrock_client, google_client, line_client,     │
│  s3_client, http_client                          │
├─────────────────────────────────────────────────┤
│  コア層 (core/)                                   │
│  settings, middleware, logging, models, prompts  │
└─────────────────────────────────────────────────┘
```

#### フィーチャー層
- **責務**: 各エンドポイントの入出力定義とビジネスロジック
- **構成**: router (ルーティング) / schemas (Pydanticスキーマ) / usecase (ビジネスロジック)
- **許可される操作**: クライアント層・共有層・コア層の呼び出し
- **禁止される操作**: 他のフィーチャーへの直接依存（オーケストレーション時を除く）

#### クライアント層
- **責務**: 外部APIとの通信を抽象化
- **許可される操作**: コア層(settings)の参照、外部API呼び出し
- **禁止される操作**: フィーチャー層への依存

#### コア層
- **責務**: アプリケーション設定、共通ミドルウェア、ロギング
- **許可される操作**: 外部ライブラリの利用
- **禁止される操作**: フィーチャー層・クライアント層への依存

## データ永続化戦略

### ストレージ方式

| データ種別 | ストレージ | フォーマット | 理由 |
|-----------|----------|-------------|------|
| RAWメール | S3 | .eml | メール受信トリガーでS3に保存済み |
| 一時画像 | S3 | JPEG/PNG | LINE Content APIから取得した画像の一時保存 |
| アプリ設定 | SSM Parameter Store | dotenv (SecureString) | Lambda起動時に読み込み、暗号化保存 |
| Google認証情報 | 環境変数 (SSM経由) | JSON文字列 | サービスアカウントキー |

### S3ライフサイクルポリシー

- 画像一時保存バケット: 24時間後に自動削除
- RAWメールバケット: 保持（既存運用に従う）

## パフォーマンス要件

### レスポンスタイム

| 操作 | 目標時間 | 測定環境 |
|------|---------|---------|
| Webhook応答 (200 OK) | 5秒以内 | Lambda (arm64) |
| テキストメッセージ処理全体 | 10秒以内 | Lambda (arm64) |
| 画像メッセージ処理全体 | 30秒以内 | Lambda (arm64) |
| LLM抽出 (1回あたり) | 5秒以内 | Bedrock Claude Haiku |
| カレンダー登録 (1イベント) | 2秒以内 | Google Calendar API |

### リソース使用量

| リソース | 上限 | 理由 |
|---------|------|------|
| Lambda メモリ | 512MB | 画像処理を含むため標準より多め |
| Lambda タイムアウト | 120秒 | 画像処理+LLM+カレンダー登録の合計 |
| API Gateway タイムアウト | 29秒 | API Gateway制限 |

## セキュリティアーキテクチャ

### データ保護

- **Webhook署名検証**: LINE Channel Secretを用いたHMAC-SHA256署名で、不正なリクエストを検知・拒否
- **S3アクセス制御**: プライベートバケット、パブリックアクセス完全ブロック
- **機密情報管理**: SSM Parameter Store (SecureString) に一元管理、Lambda起動時にos.environへ展開

### 入力検証

- **Pydanticバリデーション**: `ConfigDict(extra="forbid")` で未定義フィールドを拒否
- **署名検証**: Webhookエンドポイントで `X-Line-Signature` を必須チェック
- **ホワイトリスト**: メール送信元ドメインのホワイトリストチェック

## スケーラビリティ設計

### 処理量への対応

- **想定処理量**: 月間1,000リクエスト
- **Lambda同時実行**: デフォルト設定（必要に応じてリザーブド同時実行設定）
- **非同期処理**: 将来的にSQS/Step Functionsによるキューイングを検討

### 機能拡張性

- **フィーチャーベース**: 新機能追加時は `features/` に新ディレクトリを作成
- **クライアント追加**: 新しい外部APIはクライアント層に追加
- **環境変数追加**: SSM dotenvに追記するだけで新設定を追加可能

## テスト戦略

### ユニットテスト
- **フレームワーク**: pytest + pytest-asyncio
- **対象**: 各フィーチャーのusecase、クライアントのロジック、ミドルウェア
- **カバレッジ目標**: 80%以上（重要なビジネスロジックは90%以上）

### 統合テスト
- **方法**: FastAPI TestClientを使用
- **対象**: エンドポイント全体のリクエスト→レスポンスフロー（外部APIはモック）

### E2Eテスト
- **環境**: AWS SAMステージング環境
- **シナリオ**: 実際のLINE BOTからメッセージ送信→カレンダー登録→通知受信

## 技術的制約

### 環境要件
- **OS**: Amazon Linux 2 (Lambda Docker arm64)
- **ランタイム**: Python 3.12
- **コンテナ**: Docker (arm64ベースイメージ)

### パフォーマンス制約
- API Gatewayタイムアウト: 29秒（LINE Webhookは5秒以内の応答推奨）
- Lambda最大実行時間: 120秒

### セキュリティ制約
- LINE Webhook URLは認証なし（署名検証をアプリケーション層で実施）
- Google Calendar APIはサービスアカウント認証

## 依存関係管理

| ライブラリ | 用途 | バージョン管理方針 |
|-----------|------|-------------------|
| fastapi | APIフレームワーク | `>=0.115.0,<1.0.0` (メジャー固定) |
| pydantic | バリデーション | `>=2.8.0,<3.0.0` (メジャー固定) |
| mangum | Lambda ASGI | `>=0.17.0,<0.19.0` (マイナー範囲) |
| boto3 | AWS SDK | `>=1.34.0,<2.0.0` (メジャー固定) |
| langchain | LLM | `>=1.2.3,<1.3.0` (マイナー固定) |
| langchain-aws | Bedrock統合 | `>=1.2.0,<1.3.0` (マイナー固定) |
| line-bot-sdk | LINE SDK | `>=3.12.0,<4.0.0` (メジャー固定) |
| google-api-python-client | Google API | `>=2.132.0,<3.0.0` (メジャー固定) |

**方針**:
- 安定したライブラリはメジャーバージョンで範囲固定
- 破壊的変更のリスクが高いライブラリ (LangChain) はマイナーバージョンで固定
- `uv.lock` で厳密なバージョンを再現

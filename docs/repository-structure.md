# リポジトリ構造定義書 (Repository Structure Document)

## プロジェクト構造

```
calendar-auto-register/
├── app/                          # アプリケーションコード
│   ├── src/                      # ソースコード
│   │   └── calendar_auto_register/
│   │       ├── __init__.py
│   │       ├── app.py            # FastAPIアプリ組み立て
│   │       ├── main.py           # エントリポイント (Lambda / ローカル)
│   │       ├── clients/          # 外部APIクライアント
│   │       ├── core/             # アプリ共通基盤
│   │       ├── features/         # フィーチャーモジュール
│   │       └── shared/           # フィーチャー間共有スキーマ
│   └── tests/                    # テストコード
│       ├── conftest.py
│       └── calendar_auto_register/
│           ├── app/              # アプリレベルテスト
│           ├── core/             # コアモジュールテスト
│           └── features/         # フィーチャーテスト
├── docker/                       # Dockerfile群
├── docs/                         # プロジェクトドキュメント
├── infra/                        # インフラ定義
│   └── sam/                      # AWS SAMテンプレート
├── scripts/                      # ビルド・デプロイスクリプト
├── .claude/                      # Claude Code設定
│   ├── commands/                 # スラッシュコマンド
│   ├── skills/                   # タスクモード別スキル
│   └── agents/                   # サブエージェント定義
├── .steering/                    # ステアリングファイル (作業単位)
├── .github/                      # GitHub Actions
├── pyproject.toml                # プロジェクト設定・依存管理
├── docker-compose.yml            # Docker Compose設定
└── README.md                     # プロジェクト概要
```

## ディレクトリ詳細

### app/src/calendar_auto_register/ (ソースコードディレクトリ)

#### core/

**役割**: アプリケーション全体で共有する基盤コード

**配置ファイル**:
- `settings.py`: 環境変数・SSMからの設定読み込み
- `middleware.py`: API Key認証、リクエストIDミドルウェア
- `logging.py`: 構造化ロギング
- `models.py`: ユースケース間で共有するdataclass
- `prompts.py`: LLMプロンプトテンプレート

**命名規則**:
- ファイル名: snake_case
- 他フィーチャーに依存しない共通機能のみ配置

**依存関係**:
- 依存可能: 外部ライブラリ (boto3, fastapi等)
- 依存禁止: clients/, features/, shared/

#### clients/

**役割**: 外部APIとの通信を抽象化するクライアント群

**配置ファイル**:
- `bedrock_client.py`: AWS Bedrock (LLM / Vision) クライアント
- `google_client.py`: Google Calendar APIクライアント
- `line_client.py`: LINE Messaging APIクライアント
- `s3_client.py`: AWS S3クライアント
- `http_client.py`: 汎用HTTPクライアント (httpx)

**命名規則**:
- パターン: `{サービス名}_client.py`

**依存関係**:
- 依存可能: core/ (settings)
- 依存禁止: features/, shared/

#### features/

**役割**: 各エンドポイントの機能をモジュール化

**配置ファイル**: 各フィーチャーディレクトリに以下の3ファイル:
- `router_{feature_name}.py`: FastAPIルーター定義
- `schemas_{feature_name}.py`: Pydanticリクエスト/レスポンススキーマ
- `usecase_{feature_name}.py`: ビジネスロジック

**命名規則**:
- ディレクトリ名: snake_case (例: `line_webhook/`, `vision_extract/`)
- ファイル名: `{role}_{feature_name}.py`

**依存関係**:
- 依存可能: core/, clients/, shared/
- 依存禁止: 他のfeatures/ への直接依存（オーケストレーション時を除く）

**現在のフィーチャー**:
```
features/
├── mailparse_post/        # POST /mail/parse (メール解析)
├── llm_extract/           # POST /llm/extract-event (LLM抽出)
├── calendar_events/       # POST /calendar/events (カレンダー登録)
├── line_notify_post/      # POST /line/notify (LINE通知)
├── line_webhook/          # POST /line/webhook (新規: Webhook受信)
└── vision_extract/        # POST /vision/extract-text (新規: 画像テキスト抽出)
```

#### shared/

**役割**: 複数のフィーチャーで共有するPydanticスキーマ

**配置ファイル**:
- `schemas/calendar.py`: Google Calendar互換スキーマ (GoogleCalendarEventModel等)
- `schemas/calendar_events.py`: カレンダーイベント結果スキーマ (CalendarEventResult等)

**命名規則**:
- パターン: `schemas/{domain}.py`

**依存関係**:
- 依存可能: core/
- 依存禁止: clients/, features/

### app/tests/ (テストディレクトリ)

**構造**: ソースコードのディレクトリ構造をミラーリング

```
tests/
├── conftest.py                           # 共通フィクスチャ
└── calendar_auto_register/
    ├── app/
    │   └── test_healthz.py
    ├── core/
    │   └── test_middleware.py
    └── features/
        ├── calendar_events/
        │   └── test_calendar_events.py
        ├── line_notify_post/
        │   └── test_line_notify_post.py
        ├── llm_extract/
        │   └── test_llm_extract.py
        └── mailparse_post/
            └── test_mailparse_post.py
```

**命名規則**:
- パターン: `test_{テスト対象ファイル名}.py`
- 例: `usecase_llm_extract.py` → `test_llm_extract.py`

### docs/ (ドキュメントディレクトリ)

**配置ドキュメント**:
- `product-requirements.md`: プロダクト要求定義書
- `functional-design.md`: 機能設計書
- `architecture.md`: アーキテクチャ設計書
- `repository-structure.md`: リポジトリ構造定義書（本ドキュメント）
- `development-guidelines.md`: 開発ガイドライン
- `glossary.md`: 用語集
- `requirements.md`: 初期要求仕様書

### infra/sam/ (インフラ定義)

**配置ファイル**:
- `template.yaml`: AWS SAM テンプレート (Lambda, API Gateway, IAM等)
- `samconfig.toml`: SAM CLI設定

### scripts/ (スクリプトディレクトリ)

**配置ファイル**:
- デプロイスクリプト (`sam-deploy.sh`)
- 開発補助スクリプト

### docker/ (Dockerファイル)

**配置ファイル**:
- `Dockerfile.local`: 開発用 (uv, pytest, ruff, mypy含む)
- `Dockerfile.prod`: 本番用 (最小構成)

## ファイル配置規則

### ソースファイル

| ファイル種別 | 配置先 | 命名規則 | 例 |
|------------|--------|---------|-----|
| エントリポイント | app/src/calendar_auto_register/ | snake_case | `main.py`, `app.py` |
| ルーター | features/{name}/ | `router_{feature}.py` | `router_line_webhook_post.py` |
| スキーマ | features/{name}/ | `schemas_{feature}.py` | `schemas_line_webhook_post.py` |
| ユースケース | features/{name}/ | `usecase_{feature}.py` | `usecase_line_webhook_post.py` |
| クライアント | clients/ | `{service}_client.py` | `bedrock_client.py` |
| 共有スキーマ | shared/schemas/ | `{domain}.py` | `calendar.py` |

### テストファイル

| テスト種別 | 配置先 | 命名規則 | 例 |
|-----------|--------|---------|-----|
| フィーチャーテスト | tests/calendar_auto_register/features/{name}/ | `test_{feature}.py` | `test_llm_extract.py` |
| コアテスト | tests/calendar_auto_register/core/ | `test_{module}.py` | `test_middleware.py` |
| アプリテスト | tests/calendar_auto_register/app/ | `test_{target}.py` | `test_healthz.py` |

## 命名規則

### ディレクトリ名
- **レイヤーディレクトリ**: 複数形、snake_case
  - 例: `clients/`, `features/`
- **フィーチャーディレクトリ**: snake_case、機能を表す名前
  - 例: `line_webhook/`, `vision_extract/`, `calendar_events/`

### ファイル名
- **モジュールファイル**: snake_case
  - 例: `bedrock_client.py`, `usecase_llm_extract.py`
- **定数**: ファイル名はsnake_case、ファイル内の定数はUPPER_SNAKE_CASE

### Python命名
- **クラス**: PascalCase (例: `GoogleCalendarEventModel`)
- **関数・メソッド**: snake_case (例: `extract_text_from_image`)
- **変数**: snake_case (例: `channel_secret`)
- **定数**: UPPER_SNAKE_CASE (例: `_DEFAULT_REGION`)
- **Boolean**: `is_`, `has_` で始める (例: `is_local`)

## 依存関係のルール

### レイヤー間の依存

```
features/ (フィーチャー層)
    ↓ (OK)
clients/ (クライアント層)    shared/ (共有層)
    ↓ (OK)                    ↓ (OK)
core/ (コア層)
```

**禁止される依存**:
- core/ → features/ / clients/ / shared/
- clients/ → features/ / shared/
- shared/ → features/ / clients/

### モジュール間の依存
- フィーチャー間の直接依存は原則禁止
- オーケストレーション（line_webhookが他フィーチャーのusecaseを呼ぶ）は許可

## スケーリング戦略

### 機能の追加

新しいエンドポイントを追加する場合:

1. `features/` に新ディレクトリを作成
2. `router_*.py`, `schemas_*.py`, `usecase_*.py` の3ファイルを配置
3. `app.py` でルーターを登録
4. `tests/` にミラー構造でテストを追加

### ファイルサイズの管理

- 1ファイル: 300行以下を推奨
- 300-500行: リファクタリングを検討
- 500行以上: 分割を推奨

## 特殊ディレクトリ

### .steering/ (ステアリングファイル)

**役割**: 特定の開発作業における作業計画・タスクリスト

**構造**:
```
.steering/
└── YYYYMMDD-task-name/
    ├── requirements.md      # 作業の要求内容
    ├── design.md            # 変更内容の設計
    └── tasklist.md          # タスクリスト
```

### .claude/ (Claude Code設定)

**役割**: Claude Code設定とカスタマイズ

**構造**:
```
.claude/
├── commands/                # スラッシュコマンド定義
├── skills/                  # タスクモード別スキル定義
└── agents/                  # サブエージェント定義
```

## 除外設定

### .gitignore

- `__pycache__/`, `*.py[cod]`
- `.venv/`, `venv/`
- `dist/`, `build/`, `*.egg-info/`
- `.env`, `.env.prod`, `.env.deploy`
- `*.log`
- `.DS_Store`
- `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`

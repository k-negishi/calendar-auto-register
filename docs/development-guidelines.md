# 開発ガイドライン (Development Guidelines)

## コーディング規約

### 命名規則

#### 変数・関数

```python
# 変数: snake_case、名詞または名詞句
channel_secret = os.getenv("LINE_CHANNEL_SECRET")
extracted_events: list[GoogleCalendarEventModel] = []

# 関数: snake_case、動詞で始める
def extract_text_from_image(image_bytes: bytes) -> str: ...
def validate_webhook_signature(body: bytes, signature: str) -> bool: ...
async def handle_webhook_events(events: list[LineWebhookEvent]) -> None: ...

# 定数: UPPER_SNAKE_CASE
_DEFAULT_REGION = "ap-northeast-1"
_DEFAULT_TZ = "Asia/Tokyo"

# Boolean: is_, has_ で始める
is_local = app_env == "local"
has_attachments = len(mail.attachments) > 0
```

#### クラス・型定義

```python
from typing import Literal, TypeAlias
from pydantic import BaseModel

# クラス: PascalCase
class GoogleCalendarEventModel(BaseModel): ...
class LineMessageEvent(BaseModel): ...

# dataclass: PascalCase
@dataclass(slots=True)
class NormalizedMail: ...
class CalendarEvent: ...

# 型エイリアス: PascalCase
EventStatus: TypeAlias = Literal["CREATED", "DUPLICATE", "FAILED"]
```

### コードフォーマット

- **インデント**: 4スペース (PEP 8準拠)
- **行の長さ**: 最大100文字 (`pyproject.toml` の `ruff.line-length = 100`)
- **フォーマッター**: ruff format
- **インポート順序**: ruff isort (標準ライブラリ → サードパーティ → ファーストパーティ)

```python
# インポート順序の例
from __future__ import annotations

import logging
import time
from typing import Awaitable, Callable

from fastapi import Request, Response
from pydantic import BaseModel

from calendar_auto_register.core.settings import load_settings
```

### Pydanticスキーマ規約

```python
from pydantic import BaseModel, ConfigDict, Field

class ExampleRequest(BaseModel):
    """リクエストスキーマの説明"""

    field_name: str = Field(..., description="フィールドの説明")
    optional_field: str | None = None

    # extra="forbid" で未定義フィールドを拒否
    model_config = ConfigDict(extra="forbid")
```

### コメント規約

**関数・クラスのドキュメント (Googleスタイル)**:
```python
def extract_events_from_text(
    text: str,
    model_id: str,
    region: str,
) -> list[GoogleCalendarEventModel]:
    """テキストからイベント情報をLLMで抽出する。

    Args:
        text: 解析対象のテキスト
        model_id: Bedrock モデルID
        region: AWSリージョン

    Returns:
        抽出されたイベントのリスト

    Raises:
        BedrockInvocationError: LLM呼び出しに失敗した場合
    """
    ...
```

**インラインコメント**:
```python
# なぜそうするかを説明する
# ±15分の時間窓で同名イベントを検索し、重複を防止
existing = search_events(start - timedelta(minutes=15), start + timedelta(minutes=15))

# コードを見れば分かることは書かない
# ❌ リストに追加する
events.append(event)
```

### エラーハンドリング

**原則**:
- 予期されるエラー: 適切にキャッチし、ユーザーにフィードバック
- 予期しないエラー: ログに記録して上位に伝播
- `except Exception:` は避け、具体的な例外型を指定
- エラー時でもユーザー（LINE通知）へのフィードバックを必ず行う

```python
from fastapi import HTTPException

# 予期されるエラーの処理
try:
    events = await extract_events(text, settings)
except BedrockInvocationError:
    logger.exception("LLM抽出に失敗")
    # ユーザーにエラー通知
    await notify_error(user_id, "イベント情報を抽出できませんでした")
    return

# HTTPExceptionは具体的なステータスコードで
if not verify_signature(body, signature, channel_secret):
    raise HTTPException(status_code=403, detail="Invalid signature")
```

## Git運用ルール

### ブランチ戦略

- `main`: 本番環境にデプロイ可能な状態
- `feature/{機能名}`: 新機能開発
- `fix/{修正内容}`: バグ修正
- `refactor/{対象}`: リファクタリング
- `claude/{作業名}-{session_id}`: Claude Codeによる自動作業

### コミットメッセージ規約

**フォーマット**:
```
<prefix>: <subject>
```

**Prefix**:
| prefix | 用途 |
|--------|------|
| `add` | 新機能追加 |
| `fix` | バグ修正 |
| `docs` | ドキュメント変更 |
| `refactor` | リファクタリング |
| `test` | テスト追加・修正 |
| `chore` | ビルド、補助ツール等 |
| `perf` | パフォーマンス改善 |
| `build` | ビルドシステム変更 |
| `ci` | CI設定変更 |
| `revert` | コミット取り消し |
| `style` | コードフォーマット |

**例**:
```
add: LINE Webhook受信エンドポイントを追加

fix: 重複チェックの時間窓を修正

docs: アーキテクチャ設計書を更新
```

### プルリクエストプロセス

**作成前のチェック**:
- [ ] `uv run pytest` が全てパス
- [ ] `uv run ruff check` でLintエラーがない
- [ ] `uv run mypy app/src` で型チェックがパス

## テスト戦略

### テストの種類

#### ユニットテスト

**対象**: 各フィーチャーのusecase、クライアントのロジック
**カバレッジ目標**: 80%以上

```python
import pytest
from unittest.mock import AsyncMock, Mock

class TestLineWebhookUsecase:
    """LINE Webhookユースケースのテスト"""

    async def test_text_message_creates_calendar_event(
        self,
        mock_bedrock_client: AsyncMock,
        mock_google_client: AsyncMock,
    ) -> None:
        """テキストメッセージからカレンダーイベントが登録される"""
        mock_bedrock_client.extract_events.return_value = [sample_event]
        mock_google_client.create_event.return_value = {"id": "event-1"}

        result = await handle_text_message("明日14時から営業会議", settings)

        assert result.status == "CREATED"
        mock_google_client.create_event.assert_called_once()
```

#### 統合テスト

**対象**: エンドポイント全体のリクエスト→レスポンス

```python
from fastapi.testclient import TestClient

class TestLineWebhookEndpoint:
    """LINE Webhookエンドポイントの統合テスト"""

    def test_valid_webhook_returns_200(
        self, client: TestClient
    ) -> None:
        """有効な署名のWebhookリクエストは200を返す"""
        response = client.post(
            "/line/webhook",
            json=sample_webhook_body,
            headers={"X-Line-Signature": valid_signature},
        )
        assert response.status_code == 200
```

### テスト命名規則

**パターン**: `test_{対象}_{条件}_{期待結果}` または日本語docstring

```python
# 関数名で意図を表現
def test_verify_signature_invalid_signature_returns_false() -> None: ...
def test_extract_events_empty_text_returns_empty_list() -> None: ...

# 日本語docstringで補足
async def test_handle_image_message(self) -> None:
    """画像メッセージからカレンダーイベントが登録される"""
    ...
```

### モック・スタブの使用

**原則**:
- 外部API (Bedrock, Google Calendar, LINE, S3) はモック化
- ビジネスロジックは実装を使用
- フィクスチャは `conftest.py` に集約

```python
@pytest.fixture
def mock_settings() -> Settings:
    """テスト用Settings"""
    return Settings(
        app_env="local",
        region="ap-northeast-1",
        raw_mail_bucket="test-bucket",
        timezone_default="Asia/Tokyo",
        calendar_id="test-calendar",
        google_credentials="{}",
        allowlist_senders=[],
        bedrock_model_id="anthropic.claude-3-haiku",
        line_channel_access_token="test-token",
        line_user_id="test-user",
        api_key=None,
    )
```

## 開発環境セットアップ

### 必要なツール

| ツール | バージョン | インストール方法 |
|--------|-----------|-----------------|
| Docker | latest | 公式サイトからインストール |
| Docker Compose | latest | Docker Desktop に同梱 |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

### セットアップ手順

```bash
# 1. リポジトリのクローン
git clone https://github.com/k-negishi/calendar-auto-register.git
cd calendar-auto-register

# 2. ローカルコンテナのビルド
docker compose build local

# 3. 環境変数の設定
cp .env.example .env
# .env ファイルを編集 (CALENDAR_ID, GOOGLE_CREDENTIALS 等)

# 4. テスト実行
docker compose run --rm local uv run pytest

# 5. Lint / 型チェック
docker compose run --rm local uv run ruff check --fix
docker compose run --rm local uv run mypy app/src

# 6. ローカルサーバー起動
docker compose run --rm --service-ports local-web \
  uv run uvicorn calendar_auto_register.main:app \
  --host 0.0.0.0 --port 8000 --reload
```

## コードレビュー基準

### レビューポイント

**機能性**:
- [ ] PRDの要件を満たしているか
- [ ] エッジケースが考慮されているか
- [ ] エラーハンドリングが適切か（ユーザーへの通知含む）

**可読性**:
- [ ] 命名が明確か
- [ ] Pydanticスキーマに `extra="forbid"` が設定されているか
- [ ] 複雑なロジックにコメントがあるか

**保守性**:
- [ ] フィーチャーベースのディレクトリ構造に従っているか
- [ ] 依存関係のルールに違反していないか

**パフォーマンス**:
- [ ] 不要なAPI呼び出しがないか
- [ ] リトライポリシーが適切か

**セキュリティ**:
- [ ] 機密情報がハードコードされていないか
- [ ] 入力バリデーションが適切か
- [ ] Webhook署名検証が実装されているか

# 開発ガイドライン (Development Guidelines)

## コーディング規約

### 命名規則

#### 変数・関数

**Python**:
```python
# ✅ 良い例
user_profile_data = fetch_user_profile()
def calculate_total_price(items: list[CartItem]) -> float:
    ...

# ❌ 悪い例
data = fetch()
def calc(arr: list[Any]) -> float:
    ...
```

**原則**:
- 変数: snake_case、名詞または名詞句
- 関数: snake_case、動詞で始める
- 定数: UPPER_SNAKE_CASE
- Boolean: `is_`, `has_`, `should_`で始める
- クラス: PascalCase

#### クラス・Protocol・型エイリアス

```python
from typing import Protocol, Literal, TypeAlias

# クラス: PascalCase、名詞
class TaskManager:
    ...

class UserAuthenticationService:
    ...

# Protocol: PascalCase (インターフェースの代わり)
class TaskRepository(Protocol):
    def save(self, task: Task) -> None:
        ...

# 型エイリアス: PascalCase
TaskStatus: TypeAlias = Literal["todo", "in_progress", "completed"]
```

### コードフォーマット

**インデント**: 4スペース (PEP 8準拠)

**行の長さ**: 最大88文字 (Black標準) または 120文字

**例**:
```python
# Black + Ruffによる自動整形例
from collections.abc import Sequence


def process_items(
    items: Sequence[str],
    max_length: int = 100,
    include_metadata: bool = False,
) -> list[dict[str, str | int]]:
    """アイテムを処理して辞書のリストを返す。

    Args:
        items: 処理対象のアイテムリスト
        max_length: 最大長制限
        include_metadata: メタデータを含めるか

    Returns:
        処理済みアイテムの辞書リスト
    """
    return [
        {"value": item[:max_length], "length": len(item)}
        for item in items
        if len(item) > 0
    ]
```

### コメント規約

**関数・クラスのドキュメント (Googleスタイル)**:
```python
def count_tasks(
    tasks: Sequence[Task],
    filter: TaskFilter | None = None,
) -> int:
    """タスクの合計数を計算する。

    Args:
        tasks: 計算対象のタスクシーケンス
        filter: フィルター条件(オプション)

    Returns:
        タスクの合計数

    Raises:
        ValidationError: タスク配列が不正な場合
    """
    # 実装
    pass
```

**インラインコメント**:
```python
# ✅ 良い例: なぜそうするかを説明
# キャッシュを無効化して、最新データを取得
cache.clear()

# ❌ 悪い例: 何をしているか(コードを見れば分かる)
# キャッシュをクリアする
cache.clear()
```

### エラーハンドリング

**原則**:
- 予期されるエラー: 適切なエラークラスを定義
- 予期しないエラー: 上位に伝播
- エラーを無視しない
- `except Exception:` は避け、具体的な例外型を指定

**例**:
```python
from dataclasses import dataclass
from typing import Any


# エラークラス定義
@dataclass
class ValidationError(Exception):
    """検証エラー"""

    message: str
    field: str
    value: Any

    def __str__(self) -> str:
        return f"検証エラー [{self.field}]: {self.message}"


# エラーハンドリング
async def create_task_with_error_handling(
    data: dict[str, Any]
) -> Task:
    """エラーハンドリングを含むタスク作成"""
    try:
        task = await task_service.create(data)
    except ValidationError as error:
        # 予期されるエラー: 適切に処理
        logger.error(str(error))
        # ユーザーにフィードバック
        raise
    except Exception as error:
        # 予期しないエラー: ログに記録して上位に伝播
        logger.exception("予期しないエラー: %s", error)
        raise

    return task
```

## Git運用ルール

### ブランチ戦略

**ブランチ種別**:
- `main`: 本番環境にデプロイ可能な状態
- `develop`: 開発の最新状態
- `feature/[機能名]`: 新機能開発
- `fix/[修正内容]`: バグ修正
- `refactor/[対象]`: リファクタリング

**フロー**:
```
main
  └─ develop
      ├─ feature/task-management
      ├─ feature/user-auth
      └─ fix/task-validation
```

### コミットメッセージ規約

**フォーマット**:
```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type**:
- `feat`: 新機能
- `fix`: バグ修正
- `docs`: ドキュメント
- `style`: コードフォーマット
- `refactor`: リファクタリング
- `test`: テスト追加・修正
- `chore`: ビルド、補助ツール等

**例**:
```
feat(task): タスクの優先度設定機能を追加

ユーザーがタスクに優先度(高/中/低)を設定できるようにしました。
- Taskモデルにpriorityフィールドを追加
- CLIに--priorityオプションを追加
- 優先度によるソート機能を実装

Closes #123
```

### プルリクエストプロセス

**作成前のチェック**:
- [ ] 全てのテストがパス
- [ ] Lintエラーがない
- [ ] 型チェックがパス
- [ ] 競合が解決されている

**PRテンプレート**:
```markdown
## 概要
[変更内容の簡潔な説明]

## 変更理由
[なぜこの変更が必要か]

## 変更内容
- [変更点1]
- [変更点2]

## テスト
- [ ] ユニットテスト追加
- [ ] 手動テスト実施

## スクリーンショット(該当する場合)
[画像]

## 関連Issue
Closes #[Issue番号]
```

**レビュープロセス**:
1. セルフレビュー
2. 自動テスト実行
3. レビュアーアサイン
4. レビューフィードバック対応
5. 承認後マージ

## テスト戦略

### テストの種類

#### ユニットテスト

**対象**: 個別の関数・クラス

**カバレッジ目標**: 80%以上 (重要なビジネスロジックは90%以上)

**例**:
```python
import pytest
from unittest.mock import Mock


class TestTaskService:
    """TaskServiceのテストスイート"""

    class TestCreate:
        """createメソッドのテスト"""

        async def test_create_with_valid_data(
            self, mock_repository: Mock
        ) -> None:
            """正常なデータでタスクを作成できる"""
            service = TaskService(mock_repository)
            task = await service.create({
                "title": "テストタスク",
                "description": "説明",
            })

            assert task.id is not None
            assert task.title == "テストタスク"

        async def test_create_with_empty_title_raises_error(
            self, mock_repository: Mock
        ) -> None:
            """タイトルが空の場合ValidationErrorを送出する"""
            service = TaskService(mock_repository)

            with pytest.raises(ValidationError):
                await service.create({"title": ""})
```

#### 統合テスト

**対象**: 複数コンポーネントの連携

**例**:
```python
import pytest


@pytest.mark.integration
class TestTaskCRUD:
    """タスクCRUD操作の統合テスト"""

    async def test_full_crud_operations(
        self, task_service: TaskService
    ) -> None:
        """タスクの作成・取得・更新・削除ができる"""
        # 作成
        created = await task_service.create({"title": "テスト"})

        # 取得
        found = await task_service.find_by_id(created.id)
        assert found is not None
        assert found.title == "テスト"

        # 更新
        await task_service.update(created.id, {"title": "更新後"})
        updated = await task_service.find_by_id(created.id)
        assert updated is not None
        assert updated.title == "更新後"

        # 削除
        await task_service.delete(created.id)
        deleted = await task_service.find_by_id(created.id)
        assert deleted is None
```

#### E2Eテスト

**対象**: ユーザーシナリオ全体

**例**:
```python
import pytest
from click.testing import CliRunner


@pytest.mark.e2e
class TestTaskManagementFlow:
    """タスク管理フローのE2Eテスト"""

    def test_user_can_add_and_complete_task(
        self, cli_runner: CliRunner
    ) -> None:
        """ユーザーがタスクを追加して完了できる"""
        # タスク追加
        result = cli_runner.invoke(cli, ["add", "新しいタスク"])
        assert result.exit_code == 0
        assert "タスクを追加しました" in result.output

        # タスク一覧表示
        result = cli_runner.invoke(cli, ["list"])
        assert result.exit_code == 0
        assert "新しいタスク" in result.output

        # タスク完了
        result = cli_runner.invoke(cli, ["complete", "1"])
        assert result.exit_code == 0
        assert "タスクを完了しました" in result.output
```

### テスト命名規則

**パターン**: `test_[対象]_[条件]_[期待結果]`

**例**:
```python
# ✅ 良い例
def test_create_empty_title_raises_validation_error() -> None:
    ...

def test_find_by_id_existing_id_returns_task() -> None:
    ...

def test_delete_non_existent_id_raises_not_found_error() -> None:
    ...

# ❌ 悪い例
def test_1() -> None:
    ...

def test_works() -> None:
    ...

def test_should_work_correctly() -> None:
    ...
```

### モック・スタブの使用

**原則**:
- 外部依存(API、DB、ファイルシステム)はモック化
- ビジネスロジックは実装を使用

**例**:
```python
import pytest
from unittest.mock import Mock, AsyncMock
from typing import Protocol


# リポジトリのProtocol定義
class TaskRepository(Protocol):
    async def save(self, task: Task) -> None: ...
    async def find_by_id(self, task_id: int) -> Task | None: ...
    async def find_all(self) -> list[Task]: ...
    async def delete(self, task_id: int) -> None: ...


# Fixture でモックを提供
@pytest.fixture
def mock_repository() -> Mock:
    """モック化されたリポジトリ"""
    mock = AsyncMock(spec=TaskRepository)
    mock.save.return_value = None
    mock.find_by_id.return_value = None
    mock.find_all.return_value = []
    mock.delete.return_value = None
    return mock


# サービスは実際の実装を使用
def test_service_with_mock(mock_repository: Mock) -> None:
    service = TaskService(mock_repository)
    # テスト実装
```

## コードレビュー基準

### レビューポイント

**機能性**:
- [ ] 要件を満たしているか
- [ ] エッジケースが考慮されているか
- [ ] エラーハンドリングが適切か

**可読性**:
- [ ] 命名が明確か
- [ ] コメントが適切か
- [ ] 複雑なロジックが説明されているか

**保守性**:
- [ ] 重複コードがないか
- [ ] 責務が明確に分離されているか
- [ ] 変更の影響範囲が限定的か

**パフォーマンス**:
- [ ] 不要な計算がないか
- [ ] メモリリークの可能性がないか
- [ ] データベースクエリが最適化されているか

**セキュリティ**:
- [ ] 入力検証が適切か
- [ ] 機密情報がハードコードされていないか
- [ ] 権限チェックが実装されているか

### レビューコメントの書き方

**建設的なフィードバック**:
```markdown
## ✅ 良い例
この実装だと、タスク数が増えた時にパフォーマンスが劣化する可能性があります。
代わりに、インデックスを使った検索を検討してはどうでしょうか？

## ❌ 悪い例
この書き方は良くないです。
```

**優先度の明示**:
- `[必須]`: 修正必須
- `[推奨]`: 修正推奨
- `[提案]`: 検討してほしい
- `[質問]`: 理解のための質問

## 開発環境セットアップ

### 必要なツール

| ツール | バージョン | インストール方法 |
|--------|-----------|-----------------|
| [ツール1] | [バージョン] | [コマンド] |
| [ツール2] | [バージョン] | [コマンド] |

### セットアップ手順

```bash
# 1. リポジトリのクローン
git clone [URL]
cd [project-name]

# 2. 依存関係のインストール
[インストールコマンド]

# 3. 環境変数の設定
cp .env.example .env
# .envファイルを編集

# 4. 開発サーバーの起動
[起動コマンド]
```

### 推奨開発ツール(該当する場合)

- [ツール1]: [説明]
- [ツール2]: [説明]
# アーキテクチャ設計ガイド

## 基本原則

### 1. 技術選定には理由を明記

**悪い例**:
```
- Node.js
- TypeScript
```

**良い例**:
```
- Python 3.11+
  - 2027年10月までの長期サポート保証により、本番環境での安定稼働が期待できる
  - 型ヒント機能が充実しており、mypy等の静的解析ツールで品質を担保
  - 豊富なエコシステムとライブラリが利用可能

- Poetry 1.7+
  - pyproject.tomlによる依存関係の一元管理
  - 仮想環境の自動管理により、環境の再現性が高い
  - poetry.lockによる厳密なバージョン固定が可能

- Ruff
  - Rust製の高速リンター/フォーマッター
  - Flake8、Black、isortなど複数のツールを統合
  - 設定が簡潔でメンテナンスコストが低い
```

### 2. レイヤー分離の原則

各レイヤーの責務を明確にし、依存関係を一方向に保ちます:

```
UI → Service → Data (OK)
UI ← Service (NG)
UI → Data (NG)
```

### 3. 測定可能な要件

すべてのパフォーマンス要件は測定可能な形で記述します。

## レイヤードアーキテクチャの設計

### 各レイヤーの責務

**UIレイヤー**:
```python
from dataclasses import dataclass

@dataclass
class Task:
    """タスクデータモデル。"""
    id: str
    title: str

class CLI:
    """CLIインターフェース。

    責務: ユーザー入力の受付とバリデーション
    """

    def __init__(self, task_service: TaskService) -> None:
        self.task_service = task_service

    # OK: サービスレイヤーを呼び出す
    async def add_task(self, title: str) -> None:
        """タスクを追加する。

        Args:
            title: タスクのタイトル
        """
        task = await self.task_service.create({'title': title})
        print(f'Created: {task.id}')

    # NG: データレイヤーを直接呼び出す
    async def add_task_wrong(self, title: str) -> None:
        task = await self.repository.save({'title': title})  # ❌
```

**サービスレイヤー**:
```python
from typing import Any

class TaskService:
    """タスクサービス。

    責務: ビジネスロジックの実装
    """

    def __init__(self, repository: TaskRepository) -> None:
        self.repository = repository

    async def create(self, data: dict[str, Any]) -> Task:
        """タスクを作成する。

        ビジネスロジック: 優先度の自動推定

        Args:
            data: タスク作成データ

        Returns:
            作成されたタスク
        """
        task_data = {
            **data,
            'estimated_priority': self._estimate_priority(data),
        }
        return await self.repository.save(task_data)

    def _estimate_priority(self, data: dict[str, Any]) -> str:
        """優先度を推定する（内部メソッド）。"""
        # 推定ロジック
        return 'medium'
```

**データレイヤー**:
```python
class TaskRepository:
    """タスクリポジトリ。

    責務: データの永続化
    """

    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    async def save(self, task: dict[str, Any]) -> None:
        """タスクを保存する。

        Args:
            task: 保存するタスクデータ
        """
        await self.storage.write(task)
```

## パフォーマンス要件の設定

### 具体的な数値目標

```
コマンド実行時間: 100ms以内(平均的なPC環境で)
└─ 測定方法: console.timeでCLI起動から結果表示まで計測
└─ 測定環境: CPU Core i5相当、メモリ8GB、SSD

タスク一覧表示: 1000件まで1秒以内
└─ 測定方法: 1000件のダミーデータで計測
└─ 許容範囲: 100件で100ms、1000件で1秒、10000件で10秒
```

## セキュリティ設計

### データ保護の3原則

1. **最小権限の原則**
```bash
# ファイルパーミッション
chmod 600 ~/.devtask/tasks.json  # 所有者のみ読み書き
```

2. **入力検証**
```python
class ValidationError(Exception):
    """バリデーションエラー。"""
    pass

def validate_title(title: str) -> None:
    """タイトルをバリデーションする。

    Args:
        title: バリデーション対象のタイトル

    Raises:
        ValidationError: バリデーションに失敗した場合
    """
    if not title or len(title) == 0:
        raise ValidationError('タイトルは必須です')
    if len(title) > 200:
        raise ValidationError('タイトルは200文字以内です')
```

3. **機密情報の管理**
```python
import os

# 環境変数で管理
api_key = os.getenv('DEVTASK_API_KEY')  # コード内にハードコードしない

# または.envファイルとpython-dotenvを使用
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('DEVTASK_API_KEY')
```

## スケーラビリティ設計

### データ増加への対応

**想定データ量**: [例: 10,000件のタスク]

**対策**:
- データのページネーション
- 古いデータのアーカイブ
- インデックスの最適化

```python
from datetime import datetime
from collections.abc import Sequence

class ArchiveService:
    """アーカイブサービス。"""

    def __init__(
        self,
        repository: TaskRepository,
        archive_storage: ArchiveStorage
    ) -> None:
        self.repository = repository
        self.archive_storage = archive_storage

    async def archive_completed_tasks(self, older_than: datetime) -> None:
        """完了済みタスクをアーカイブする。

        古いタスクを別ファイルに移動する。

        Args:
            older_than: この日時より古いタスクをアーカイブ
        """
        old_tasks = await self.repository.find_completed(older_than)
        await self.archive_storage.save(old_tasks)
        task_ids = [task.id for task in old_tasks]
        await self.repository.delete_many(task_ids)
```

## 依存関係管理

### バージョン管理方針

```toml
# pyproject.toml
[tool.poetry.dependencies]
python = "^3.12"
fastapi = "^0.104.0"      # マイナーバージョンアップは自動
pydantic = "2.5.0"        # 破壊的変更のリスクがある場合は固定

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.0"
mypy = "^1.7.0"
ruff = "^0.1.0"
```

**方針**:
- 安定版は`^`でマイナーバージョンまで許可
- 破壊的変更のリスクがある場合は完全固定
- poetry.lockで厳密なバージョン管理
- Python本体のバージョンは`^3.12`で3.12以上を指定

## チェックリスト

- [ ] すべての技術選定に理由が記載されている
- [ ] レイヤードアーキテクチャが明確に定義されている
- [ ] パフォーマンス要件が測定可能である
- [ ] セキュリティ考慮事項が記載されている
- [ ] スケーラビリティが考慮されている
- [ ] バックアップ戦略が定義されている
- [ ] 依存関係管理のポリシーが明確である
- [ ] テスト戦略が定義されている
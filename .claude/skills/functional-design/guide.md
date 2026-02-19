# 機能設計書作成ガイド

このガイドは、プロダクト要求定義書(PRD)に基づいて機能設計書を作成するための実践的な指針を提供します。

## 機能設計書の目的

機能設計書は、PRDで定義された「何を作るか」を「どう実現するか」に落とし込むドキュメントです。

**主な内容**:
- システム構成図
- データモデル
- コンポーネント設計
- アルゴリズム設計（該当する場合）
- UI設計
- エラーハンドリング

## 作成の基本フロー

### ステップ1: PRDの確認

機能設計書を作成する前に、必ずPRDを確認します。

```
Claude CodeにPRDから機能設計書を作成してもらう際のプロンプト例:

PRDの内容に基づいて機能設計書を作成してください。
特に優先度P0(MVP)の機能に焦点を当ててください。
```

### ステップ2: システム構成図の作成

#### Mermaid記法の使用

システム構成図はMermaid記法で記述します。

**基本的な3層アーキテクチャの例**:
```mermaid
graph TB
    User[ユーザー]
    CLI[CLIレイヤー]
    Service[サービスレイヤー]
    Data[データレイヤー]

    User --> CLI
    CLI --> Service
    Service --> Data
```

**より詳細な例**:
```mermaid
graph TB
    User[ユーザー]
    CLI[CLIインターフェース]
    Commander[Commander.js]
    TaskManager[TaskManager]
    PriorityEstimator[PriorityEstimator]
    FileStorage[FileStorage]
    JSON[(tasks.json)]

    User --> CLI
    CLI --> Commander
    Commander --> TaskManager
    TaskManager --> PriorityEstimator
    TaskManager --> FileStorage
    FileStorage --> JSON
```

### ステップ3: データモデル定義

#### Python型定義で明確に

データモデルはPythonのdataclassで定義します。

**基本的なTask型の例**:
```python
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, TypeAlias

# 型エイリアスで可読性を向上
TaskStatus: TypeAlias = Literal["todo", "in_progress", "completed"]
TaskPriority: TypeAlias = Literal["high", "medium", "low"]

@dataclass
class StatusChange:
    """ステータス変更履歴."""
    from_status: TaskStatus
    to_status: TaskStatus
    changed_at: datetime

@dataclass
class Task:
    """タスクエンティティ.

    Attributes:
        id: UUID v4形式のタスクID
        title: タスクのタイトル (1-200文字)
        status: タスクの現在のステータス
        priority: タスクの優先度
        created_at: タスク作成日時
        updated_at: タスク最終更新日時
        description: タスクの詳細説明 (Markdown形式)
        estimated_priority: 自動推定された優先度
        due_date: タスクの期限
        status_history: ステータス変更履歴
    """
    id: str                                    # UUID v4
    title: str                                 # 1-200文字
    status: TaskStatus                         # 'todo' | 'in_progress' | 'completed'
    priority: TaskPriority                     # 'high' | 'medium' | 'low'
    created_at: datetime                       # 作成日時
    updated_at: datetime                       # 更新日時
    description: str | None = None             # オプション、Markdown形式
    estimated_priority: TaskPriority | None = None  # 自動推定された優先度
    due_date: datetime | None = None           # 期限
    status_history: list[StatusChange] | None = None  # ステータス変更履歴
```

**重要なポイント**:
- dataclassでボイラープレートを削減
- Googleスタイルのdocstringで説明を追加
- 制約（文字数、形式など）を明記
- オプションフィールドには`| None`とデフォルト値を設定
- 型エイリアスとLiteralで可読性を向上

#### ER図の作成

複数のエンティティがある場合、ER図で関連を示します。

```mermaid
erDiagram
    TASK ||--o{ SUBTASK : has
    TASK ||--o{ TAG : has
    USER ||--o{ TASK : creates

    TASK {
        string id PK
        string title
        string status
        datetime createdAt
    }
    SUBTASK {
        string id PK
        string taskId FK
        string title
    }
```

### ステップ4: コンポーネント設計

各レイヤーの責務を明確にします。

#### CLIレイヤー

**責務**: ユーザー入力の受付、バリデーション、結果の表示

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class Command:
    """コマンドデータ."""
    action: str
    params: dict[str, Any]

@dataclass
class Result:
    """実行結果."""
    success: bool
    message: str
    data: Any = None

class CLI:
    """コマンドラインインターフェース."""

    def parse_arguments(self) -> Command:
        """ユーザー入力を受け付ける.

        Returns:
            パースされたコマンドオブジェクト
        """
        ...

    def display_result(self, result: Result) -> None:
        """結果を表示する.

        Args:
            result: 実行結果
        """
        ...

    def display_error(self, error: Exception) -> None:
        """エラーを表示する.

        Args:
            error: エラーオブジェクト
        """
        ...
```

#### サービスレイヤー

**責務**: ビジネスロジックの実装

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class CreateTaskData:
    """タスク作成データ."""
    title: str
    description: str | None = None
    priority: TaskPriority | None = None
    due_date: datetime | None = None

@dataclass
class UpdateTaskData:
    """タスク更新データ."""
    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None

@dataclass
class FilterOptions:
    """フィルタオプション."""
    status: TaskStatus | None = None
    priority: TaskPriority | None = None

class TaskManager:
    """タスク管理サービス."""

    def create_task(self, data: CreateTaskData) -> Task:
        """タスクを作成する.

        Args:
            data: タスク作成データ

        Returns:
            作成されたタスク
        """
        ...

    def list_tasks(self, filter_options: FilterOptions | None = None) -> list[Task]:
        """タスク一覧を取得する.

        Args:
            filter_options: フィルタオプション

        Returns:
            タスクのリスト
        """
        ...

    def update_task(self, task_id: str, data: UpdateTaskData) -> Task:
        """タスクを更新する.

        Args:
            task_id: タスクID
            data: 更新データ

        Returns:
            更新されたタスク
        """
        ...

    def delete_task(self, task_id: str) -> None:
        """タスクを削除する.

        Args:
            task_id: 削除するタスクのID
        """
        ...
```

#### データレイヤー

**責務**: データの永続化と取得

```python
from typing import Any
from pathlib import Path

class FileStorage:
    """ファイルストレージ."""

    def __init__(self, file_path: Path) -> None:
        """ストレージを初期化する.

        Args:
            file_path: データファイルのパス
        """
        self._file_path = file_path

    def save(self, data: Any) -> None:
        """データを保存する.

        Args:
            data: 保存するデータ
        """
        ...

    def load(self) -> Any:
        """データを読み込む.

        Returns:
            読み込んだデータ
        """
        ...

    def exists(self) -> bool:
        """ファイルが存在するか確認する.

        Returns:
            ファイルが存在する場合True
        """
        ...
```

### ステップ5: アルゴリズム設計（該当する場合）

複雑なロジック（例: 優先度自動推定）は詳細に設計します。

#### 優先度自動推定アルゴリズムの例

**目的**: タスクの期限、作成日時、ステータスから優先度を自動推定

**計算ロジック**:

##### ステップ1: 期限スコア計算（0-100点）
```
- 期限超過: 100点（最高）
- 期限まで0-3日: 90点
- 期限まで4-7日: 70点
- 期限まで8-14日: 50点
- 期限まで14日以上: 30点
- 期限設定なし: 20点
```

**計算式**:
```python
from datetime import datetime, timedelta

def calculate_deadline_score(due_date: datetime | None) -> int:
    """期限スコアを計算する.

    Args:
        due_date: タスクの期限

    Returns:
        期限スコア (0-100点)
    """
    if due_date is None:
        return 20

    now = datetime.now()
    days_remaining = (due_date - now).days

    if days_remaining < 0:
        return 100  # 期限超過
    if days_remaining <= 3:
        return 90
    if days_remaining <= 7:
        return 70
    if days_remaining <= 14:
        return 50
    return 30
```

##### ステップ2: 経過時間スコア計算（0-100点）
```
- 作成から30日以上: 100点（最高）
- 作成から21-30日: 80点
- 作成から14-21日: 60点
- 作成から7-14日: 40点
- 作成から7日未満: 20点
```

**計算式**:
```python
def calculate_age_score(created_at: datetime) -> int:
    """経過時間スコアを計算する.

    Args:
        created_at: タスク作成日時

    Returns:
        経過時間スコア (0-100点)
    """
    now = datetime.now()
    days_old = (now - created_at).days

    if days_old >= 30:
        return 100
    if days_old >= 21:
        return 80
    if days_old >= 14:
        return 60
    if days_old >= 7:
        return 40
    return 20
```

##### ステップ3: ステータススコア計算（0-100点）
```
- 進行中 (in_progress): 100点（最高優先）
- 未着手 (todo): 50点
- 完了 (completed): 0点
```

**計算式**:
```python
def calculate_status_score(status: TaskStatus) -> int:
    """ステータススコアを計算する.

    Args:
        status: タスクのステータス

    Returns:
        ステータススコア (0-100点)
    """
    if status == "in_progress":
        return 100
    if status == "todo":
        return 50
    return 0  # completed
```

##### ステップ4: 総合スコア計算

**加重平均**:
```
総合スコア = (期限スコア × 50%) + (経過時間スコア × 20%) + (ステータススコア × 30%)
```

**計算式**:
```python
def calculate_total_score(task: Task) -> float:
    """総合スコアを計算する.

    Args:
        task: 評価対象のタスク

    Returns:
        総合スコア (0-100点)
    """
    deadline_score = calculate_deadline_score(task.due_date)
    age_score = calculate_age_score(task.created_at)
    status_score = calculate_status_score(task.status)

    return (deadline_score * 0.5) + (age_score * 0.2) + (status_score * 0.3)
```

##### ステップ5: 優先度分類

**閾値による分類**:
```
- 70点以上: high（高優先度）
- 40-70点: medium（中優先度）
- 40点未満: low（低優先度）
```

**計算式**:
```python
def estimate_priority(task: Task) -> TaskPriority:
    """優先度を推定する.

    Args:
        task: 評価対象のタスク

    Returns:
        推定された優先度
    """
    score = calculate_total_score(task)

    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"
```

**完全な実装例**:
```python
from datetime import datetime

class PriorityEstimator:
    """タスクの優先度を自動推定するクラス."""

    def estimate(self, task: Task) -> TaskPriority:
        """タスクの優先度を推定する.

        Args:
            task: 評価対象のタスク

        Returns:
            推定された優先度
        """
        deadline_score = self._calculate_deadline_score(task.due_date)
        age_score = self._calculate_age_score(task.created_at)
        status_score = self._calculate_status_score(task.status)

        total_score = (deadline_score * 0.5) + (age_score * 0.2) + (status_score * 0.3)

        if total_score >= 70:
            return "high"
        if total_score >= 40:
            return "medium"
        return "low"

    def _calculate_deadline_score(self, due_date: datetime | None) -> int:
        """期限スコアを計算する.

        Args:
            due_date: タスクの期限

        Returns:
            期限スコア (0-100点)
        """
        if due_date is None:
            return 20

        now = datetime.now()
        days_remaining = (due_date - now).days

        if days_remaining < 0:
            return 100  # 期限超過
        if days_remaining <= 3:
            return 90
        if days_remaining <= 7:
            return 70
        if days_remaining <= 14:
            return 50
        return 30

    def _calculate_age_score(self, created_at: datetime) -> int:
        """経過時間スコアを計算する.

        Args:
            created_at: タスク作成日時

        Returns:
            経過時間スコア (0-100点)
        """
        now = datetime.now()
        days_old = (now - created_at).days

        if days_old >= 30:
            return 100
        if days_old >= 21:
            return 80
        if days_old >= 14:
            return 60
        if days_old >= 7:
            return 40
        return 20

    def _calculate_status_score(self, status: TaskStatus) -> int:
        """ステータススコアを計算する.

        Args:
            status: タスクのステータス

        Returns:
            ステータススコア (0-100点)
        """
        if status == "in_progress":
            return 100
        if status == "todo":
            return 50
        return 0  # completed
```

### ステップ6: ユースケース図

主要なユースケースをシーケンス図で表現します。

**タスク追加のフロー**:
```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant TaskManager
    participant PriorityEstimator
    participant FileStorage

    User->>CLI: devtask add "タスク"
    CLI->>CLI: 入力をバリデーション
    CLI->>TaskManager: createTask(data)
    TaskManager->>TaskManager: タスクオブジェクト作成
    TaskManager->>PriorityEstimator: estimate(task)
    PriorityEstimator-->>TaskManager: 推定優先度
    TaskManager->>FileStorage: save(task)
    FileStorage-->>TaskManager: 成功
    TaskManager-->>CLI: 作成されたタスク
    CLI-->>User: "タスクを作成しました (ID: xxx)"
```

### ステップ7: UI設計（該当する場合）

CLIツールの場合、テーブル表示やカラーコーディングを定義します。

#### テーブル表示

```
┌──────────┬──────────────────┬────────────┬──────────┬───────────────┐
│ ID       │ タイトル          │ ステータス   │ 優先度    │ 期限           │
├──────────┼──────────────────┼────────────┼──────────┼───────────────┤
│ 7a5c6ff0 │ 牛乳を買って帰る.   │ 未着手      │ 高       │ 2025-11-05    │
│          │                  │            │          │ (あと1日)      │
└──────────┴──────────────────┴────────────┴──────────┴───────────────┘
```

#### カラーコーディング

**ステータスの色分け**:
- 完了 (completed): 緑
- 進行中 (in_progress): 黄
- 未着手 (todo): 白

**優先度の色分け**:
- 高 (high): 赤
- 中 (medium): 黄
- 低 (low): 青

### ステップ8: ファイル構造（該当する場合）

データの保存形式を定義します。

**例: CLIツールのデータ保存**:
```
.devtask/
├── tasks.json      # タスクデータ
└── config.json     # 設定データ
```

**tasks.json の例**:
```json
{
  "tasks": [
    {
      "id": "7a5c6ff0-5f55-474e-baf7-ea13624d73a4",
      "title": "牛乳を買って帰る",
      "description": "",
      "status": "todo",
      "priority": "high",
      "estimatedPriority": "medium",
      "dueDate": "2025-11-05T00:00:00.000Z",
      "createdAt": "2025-11-04T10:00:00.000Z",
      "updatedAt": "2025-11-04T10:00:00.000Z"
    }
  ]
}
```

### ステップ9: エラーハンドリング

エラーの種類と処理方法を定義します。

| エラー種別 | 処理 | ユーザーへの表示 |
|-----------|------|-----------------|
| 入力検証エラー | 処理を中断、エラーメッセージ表示 | "タイトルは1-200文字で入力してください" |
| ファイル読み込みエラー | 空の初期データで継続 | "データファイルが見つかりません。新規作成します" |
| タスクが見つからない | 処理を中断、エラーメッセージ表示 | "タスクが見つかりません (ID: xxx)" |

## 機能設計書のレビュー

### レビュー観点

Claude Codeにレビューを依頼します:

```
この機能設計書を評価してください。以下の観点で確認してください:

1. PRDの要件を満たしているか
2. データモデルは具体的か
3. コンポーネントの責務は明確か
4. アルゴリズムは実装可能なレベルまで詳細化されているか
5. エラーハンドリングは網羅されているか
```

### 改善の実施

Claude Codeの指摘に基づいて改善します。

## まとめ

機能設計書作成の成功のポイント:

1. **PRDとの整合性**: PRDで定義された要件を正確に反映
2. **Mermaid記法の活用**: 図表で視覚的に表現
3. **TypeScript型定義**: データモデルを明確に
4. **詳細なアルゴリズム設計**: 複雑なロジックは具体的に
5. **レイヤー分離**: 各コンポーネントの責務を明確に
6. **実装可能なレベル**: 開発者が迷わず実装できる詳細度
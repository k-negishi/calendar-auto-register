# リポジトリ構造定義書作成ガイド

## 基本原則

### 1. 役割の明確化

各ディレクトリは単一の明確な役割を持つべきです。

**悪い例**:
```
src/
├── stuff/           # 曖昧
├── misc/            # 雑多
└── utils/           # 汎用的すぎる
```

**良い例**:
```
src/
├── commands/        # CLIコマンド実装
├── services/        # ビジネスロジック
├── repositories/    # データ永続化
└── validators/      # 入力検証
```

### 2. レイヤー分離の徹底

アーキテクチャのレイヤー構造をディレクトリ構造に反映させます:

```
src/
├── ui/              # UIレイヤー
│   └── cli/         # CLI実装
├── services/        # サービスレイヤー
│   └── task/        # タスク管理サービス
└── repositories/    # データレイヤー
    └── task/        # タスクリポジトリ
```

### 3. 技術要素ベースの分割(基本)

関連する技術要素ごとにディレクトリを分割します:

**基本構造**:
```
src/
├── commands/        # CLIコマンド
├── services/        # ビジネスロジック
├── repositories/    # データ永続化
└── types/           # 型定義
```

**レイヤー構造との対応**:
```
CLI/UIレイヤー      → commands/, cli/
サービスレイヤー    → services/
データレイヤー      → repositories/, storage/
```

**Pythonの場合の補足**:
- 各ディレクトリには`__init__.py`を配置してパッケージ化
- ファイル名はsnake_caseを使用（例: `task_service.py`）
- クラス名はPascalCase（例: `TaskService`）

## ディレクトリ構造の設計

### レイヤー構造の表現

```python
# 悪い例: 平坦な構造
src/
├── task_cli.py
├── task_service.py
├── task_repository.py
├── user_cli.py
├── user_service.py
└── user_repository.py

# 良い例: レイヤーを明確に
src/
├── __init__.py
├── cli/
│   ├── __init__.py
│   ├── task_cli.py
│   └── user_cli.py
├── services/
│   ├── __init__.py
│   ├── task_service.py
│   └── user_service.py
└── repositories/
    ├── __init__.py
    ├── task_repository.py
    └── user_repository.py
```

### テストディレクトリの配置

**推奨構造**:
```
project/
├── src/
│   └── services/
│       ├── __init__.py
│       └── task_service.py
└── tests/
    ├── __init__.py
    ├── unit/
    │   ├── __init__.py
    │   └── services/
    │       ├── __init__.py
    │       └── test_task_service.py
    ├── integration/
    │   └── __init__.py
    └── e2e/
        └── __init__.py
```

**理由**:
- テストコードが本番コードと分離
- ビルド時にテストを除外しやすい
- テストタイプごとに整理可能

## 命名規則のベストプラクティス

### ディレクトリ名の原則

**1. 複数形を使う (レイヤーディレクトリ)**
```
✅ services/
✅ repositories/
✅ controllers/

❌ service/
❌ repository/
❌ controller/
```

理由: 複数のファイルを格納するため

**2. kebab-caseを使う**
```
✅ task-management/
✅ user-authentication/

❌ TaskManagement/
❌ userAuthentication/
```

理由: URL、ファイルシステムとの互換性

**3. 具体的な名前を使う**
```
✅ validators/       # 入力検証
✅ formatters/       # データ整形
✅ parsers/          # データ解析

❌ utils/            # 汎用的すぎる
❌ helpers/          # 曖昧
❌ common/           # 意味不明
```

### ファイル名の原則

**1. クラスファイル: snake_case (Pythonの標準)**
```python
# サービスクラス
task_service.py
user_authentication_service.py

# リポジトリクラス
task_repository.py
user_repository.py

# コントローラークラス
task_controller.py
```

**2. 関数ファイル: snake_case + 動詞で始める**
```python
# ユーティリティ関数
format_date.py
validate_email.py
parse_command_arguments.py
```

**3. 型定義ファイル: snake_case**
```python
# 型定義（dataclass、Protocol、TypedDictなど）
task.py
user_profile.py

# 型定義集
task_types.py
api_types.py
```

**4. 定数ファイル: snake_case (ファイル名) / UPPER_SNAKE_CASE (変数名)**
```python
# 定数定義ファイル
api_endpoints.py
error_messages.py

# ファイル内では定数名をUPPER_SNAKE_CASEで定義
# api_endpoints.py
BASE_URL = "https://api.example.com"
DEFAULT_TIMEOUT = 30
```

## 依存関係の管理

### レイヤー間の依存ルール

```python
# ✅ 良い例: 上位レイヤーから下位レイヤーへの依存
# cli/task_cli.py
from ..services.task_service import TaskService

class TaskCLI:
    """CLIインターフェース。"""

    def __init__(self, task_service: TaskService) -> None:
        self.task_service = task_service

# ❌ 悪い例: 下位レイヤーから上位レイヤーへの依存
# services/task_service.py
from ..cli.task_cli import TaskCLI  # 禁止！
```

### 循環依存の回避

**問題のあるコード**:
```python
# services/task_service.py
from .user_service import UserService

class TaskService:
    def __init__(self, user_service: UserService) -> None:
        self.user_service = user_service

# services/user_service.py
from .task_service import TaskService  # 循環依存！

class UserService:
    def __init__(self, task_service: TaskService) -> None:
        self.task_service = task_service
```

**解決策1: Protocolを使った抽象化**
```python
# types/service_protocols.py
from typing import Protocol

class ITaskService(Protocol):
    """タスクサービスのインターフェース。"""
    def create_task(self, title: str) -> None: ...

class IUserService(Protocol):
    """ユーザーサービスのインターフェース。"""
    def get_user(self, user_id: int) -> dict[str, str]: ...

# services/task_service.py
from ..types.service_protocols import IUserService

class TaskService:
    def __init__(self, user_service: IUserService) -> None:
        self.user_service = user_service

# services/user_service.py
from ..types.service_protocols import ITaskService

class UserService:
    def __init__(self, task_service: ITaskService) -> None:
        self.task_service = task_service
```

**解決策2: 依存関係を見直す**
```python
# 共通の機能を別サービスに抽出
# services/notification_service.py
class NotificationService:
    """通知サービス。"""

    def notify_task_assignment(self, task_id: str, user_id: str) -> None:
        """タスク割り当ての通知を送信する。

        Args:
            task_id: タスクID
            user_id: ユーザーID
        """
        # 通知処理

# services/task_service.py
from .notification_service import NotificationService

class TaskService:
    def __init__(self, notification_service: NotificationService) -> None:
        self.notification_service = notification_service

# services/user_service.py
from .notification_service import NotificationService

class UserService:
    def __init__(self, notification_service: NotificationService) -> None:
        self.notification_service = notification_service
```

## スケーリング戦略

### 推奨構造

**標準パターン**:
```
src/
├── __init__.py
├── commands/
│   ├── __init__.py
│   └── task_command.py
├── services/
│   ├── __init__.py
│   ├── task_service.py
│   └── user_service.py
├── repositories/
│   ├── __init__.py
│   ├── task_repository.py
│   └── user_repository.py
├── types/
│   ├── __init__.py
│   ├── task.py
│   └── user.py
└── validators/
    ├── __init__.py
    └── task_validator.py
```

**理由**:
- レイヤーごとに責務が明確
- 後からのリファクタリングが不要
- チーム開発で統一しやすい

### モジュール分離のタイミング

**分離を検討する兆候**:
1. ディレクトリ内のファイル数が10個以上
2. 関連する機能がまとまっている
3. 独立してテスト可能
4. 他の機能への依存が少ない

**分離の手順**:
```python
# Before: 全てservices/に配置
services/
├── __init__.py
├── task_service.py
├── task_validation_service.py
├── task_notification_service.py
├── user_service.py
└── user_auth_service.py

# After: 機能ごとにモジュール化
modules/
├── __init__.py
├── task/
│   ├── __init__.py
│   ├── task_service.py
│   ├── task_validation_service.py
│   └── task_notification_service.py
└── user/
    ├── __init__.py
    ├── user_service.py
    └── user_auth_service.py
```

## 特殊なケースの対応

### 共有コードの配置

**shared/ または common/ ディレクトリ**
```
src/
├── shared/
│   ├── utils/           # 汎用ユーティリティ
│   ├── types/           # 共通型定義
│   └── constants/       # 共通定数
├── commands/
├── services/
└── repositories/
```

**ルール**:
- 本当に複数のレイヤーで使われるもののみ
- 単一レイヤーでしか使わないものは含めない

### 設定ファイルの管理(該当する場合)

```
config/
├── default.ts           # デフォルト設定
└── constants.ts         # 定数定義
```

### スクリプトの管理(該当する場合)

```
scripts/
├── build.sh             # ビルドスクリプト
└── dev-tools.ts         # 開発補助スクリプト
```

## ドキュメント配置

### ドキュメントの種類と配置先

**プロジェクトルート**:
- `README.md`: プロジェクト概要
- `CONTRIBUTING.md`: 貢献ガイド
- `LICENSE`: ライセンス

**docs/ ディレクトリ**:
- `product-requirements.md`: PRD
- `functional-design.md`: 機能設計書
- `architecture.md`: アーキテクチャ設計書
- `repository-structure.md`: 本ドキュメント
- `development-guidelines.md`: 開発ガイドライン
- `glossary.md`: 用語集

**ソースコード内**:
- TSDoc/JSDocコメント: 関数・クラスの説明

## チェックリスト

- [ ] 各ディレクトリの役割が明確に定義されている
- [ ] レイヤー構造がディレクトリに反映されている
- [ ] 命名規則が一貫している
- [ ] テストコードの配置方針が決まっている
- [ ] 依存関係のルールが明確である
- [ ] 循環依存がない
- [ ] スケーリング戦略が考慮されている
- [ ] 共有コードの配置ルールが定義されている
- [ ] 設定ファイルの管理方法が決まっている
- [ ] ドキュメントの配置場所が明確である

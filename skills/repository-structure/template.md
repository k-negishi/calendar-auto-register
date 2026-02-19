# リポジトリ構造定義書 (Repository Structure Document)

## プロジェクト構造

```
project-root/
├── src/                   # ソースコード
│   ├── [layer1]/          # [説明]
│   ├── [layer2]/          # [説明]
│   └── [layer3]/          # [説明]
├── tests/                 # テストコード
│   ├── unit/              # ユニットテスト
│   ├── integration/       # 統合テスト
│   └── e2e/               # E2Eテスト
├── docs/                  # プロジェクトドキュメント
├── config/                # 設定ファイル
└── scripts/               # ビルド・デプロイスクリプト
```

## ディレクトリ詳細

### src/ (ソースコードディレクトリ)

#### [ディレクトリ1]

**役割**: [説明]

**配置ファイル**:
- [ファイルパターン1]: [説明]
- [ファイルパターン2]: [説明]

**命名規則**:
- [規則1]
- [規則2]

**依存関係**:
- 依存可能: [ディレクトリ名]
- 依存禁止: [ディレクトリ名]

**例**:
```
[ディレクトリ名]/
├── __init__.py
├── [example_file1].py
└── [example_file2].py
```

#### [ディレクトリ2]

**役割**: [説明]

**配置ファイル**:
- [ファイルパターン1]: [説明]

**命名規則**:
- [規則1]

**依存関係**:
- 依存可能: [ディレクトリ名]
- 依存禁止: [ディレクトリ名]

### tests/ (テストディレクトリ)

#### unit/

**役割**: ユニットテストの配置

**構造**:
```
tests/unit/
└── src/                    # srcディレクトリと同じ構造
    └── [layer]/
        └── [filename].test.ts
```

**命名規則**:
- パターン: `test_[テスト対象ファイル名].py`
- 例: `task_service.py` → `test_task_service.py`

#### integration/

**役割**: 統合テストの配置

**構造**:
```
tests/integration/
└── [feature]/              # 機能単位でディレクトリ分割
    └── [scenario].test.ts
```

#### e2e/

**役割**: E2Eテストの配置

**構造**:
```
tests/e2e/
└── [user-scenario]/        # ユーザーシナリオ単位
    └── [flow].test.ts
```

### docs/ (ドキュメントディレクトリ)

**配置ドキュメント**:
- `product-requirements.md`: プロダクト要求定義書
- `functional-design.md`: 機能設計書
- `architecture.md`: アーキテクチャ設計書
- `repository-structure.md`: リポジトリ構造定義書(本ドキュメント)
- `development-guidelines.md`: 開発ガイドライン
- `glossary.md`: 用語集

### config/ (設定ファイルディレクトリ - 該当する場合)

**配置ファイル**:
- 設定ファイル
- 定数定義ファイル

**例**:
```
config/
├── default.ts
└── constants.ts
```

### scripts/ (スクリプトディレクトリ - 該当する場合)

**配置ファイル**:
- ビルドスクリプト
- 開発補助スクリプト

## ファイル配置規則

### ソースファイル

| ファイル種別 | 配置先 | 命名規則 | 例 |
|------------|--------|---------|-----|
| [種別1] | [ディレクトリ] | [規則] | [例] |
| [種別2] | [ディレクトリ] | [規則] | [例] |

### テストファイル

| テスト種別 | 配置先 | 命名規則 | 例 |
|-----------|--------|---------|-----|
| ユニットテスト | tests/unit/ | test_[対象].py | test_task_service.py |
| 統合テスト | tests/integration/ | test_[機能].py | test_task_crud.py |
| E2Eテスト | tests/e2e/ | test_[シナリオ].py | test_user_workflow.py |

### 設定ファイル

| ファイル種別 | 配置先 | 命名規則 |
|------------|--------|---------|
| 環境設定 | config/environments/ | [環境名].ts |
| ツール設定 | プロジェクトルート | [ツール名].config.js |
| 型定義 | src/types/ | [対象].d.ts |

## 命名規則

### ディレクトリ名

- **レイヤーディレクトリ**: 複数形、kebab-case
  - 例: `services/`, `repositories/`, `controllers/`
- **機能ディレクトリ**: 単数形、kebab-case
  - 例: `task-management/`, `user-authentication/`

### ファイル名

- **モジュールファイル**: snake_case
  - 例: `task_service.py`, `user_repository.py`
- **関数ファイル**: snake_case
  - 例: `format_date.py`, `validate_email.py`
- **定数ファイル**: snake_case (ファイル名)
  - 例: `api_endpoints.py`, `error_messages.py`
  - 注: ファイル内の定数名はUPPER_SNAKE_CASEを使用

### テストファイル名

- パターン: `test_[テスト対象].py`
- 例: `test_task_service.py`, `test_format_date.py`

## 依存関係のルール

### レイヤー間の依存

```
UIレイヤー
    ↓ (OK)
サービスレイヤー
    ↓ (OK)
データレイヤー
```

**禁止される依存**:
- データレイヤー → サービスレイヤー (❌)
- データレイヤー → UIレイヤー (❌)
- サービスレイヤー → UIレイヤー (❌)

### モジュール間の依存

**循環依存の禁止**:
```python
# ❌ 悪い例: 循環依存
# file_a.py
from .file_b import func_b

# file_b.py
from .file_a import func_a  # 循環依存
```

**解決策**:
```python
# ✅ 良い例: 共通モジュールの抽出
# shared.py
from typing import Protocol

class SharedType(Protocol):
    """共通インターフェース。"""
    ...

# file_a.py
from .shared import SharedType

# file_b.py
from .shared import SharedType
```

## スケーリング戦略

### 機能の追加

新しい機能を追加する際の配置方針:

1. **小規模機能**: 既存ディレクトリに配置
2. **中規模機能**: レイヤー内にサブディレクトリを作成
3. **大規模機能**: 独立したモジュールとして分離

**例**:
```
src/
├── services/
│   ├── __init__.py
│   ├── task_service.py          # 既存機能
│   └── task_management/         # 中規模機能の分離
│       ├── __init__.py
│       ├── task_service.py
│       ├── subtask_service.py
│       └── task_category_service.py
```

### ファイルサイズの管理

**ファイル分割の目安**:
- 1ファイル: 300行以下を推奨
- 300-500行: リファクタリングを検討
- 500行以上: 分割を強く推奨

**分割方法**:
```typescript
// 悪い例: 1ファイルに全機能
// TaskService.ts (800行)

// 良い例: 責務ごとに分割
// TaskService.ts (200行) - CRUD操作
// TaskValidationService.ts (150行) - バリデーション
// TaskNotificationService.ts (100行) - 通知処理
```

## 特殊ディレクトリ

### .steering/ (ステアリングファイル)

**役割**: 特定の開発作業における「今回何をするか」を定義

**構造**:
```
.steering/
└── [YYYYMMDD]-[task-name]/
    ├── requirements.md      # 今回の作業の要求内容
    ├── design.md            # 変更内容の設計
    └── tasklist.md          # タスクリスト
```

**命名規則**: `20250115-add-user-profile` 形式

### .claude/ (Claude Code設定)

**役割**: Claude Code設定とカスタマイズ

**構造**:
```
.claude/
├── commands/                # スラッシュコマンド
├── skills/                  # タスクモード別スキル
└── agents/                  # サブエージェント定義
```


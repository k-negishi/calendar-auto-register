# プロセスガイド (Process Guide)

## 基本原則

### 1. 具体例を豊富に含める

抽象的なルールだけでなく、具体的なコード例を提示します。

**悪い例**:
```
変数名は分かりやすくすること
```

**良い例**:
```python
# ✅ 良い例: 役割が明確
user_authentication = UserAuthenticationService()
task_repository = TaskRepository()

# ❌ 悪い例: 曖昧
auth = Service()
repo = Repository()
```

### 2. 理由を説明する

「なぜそうするのか」を明確にします。

**例**:
```
## エラーを無視しない

理由: エラーを無視すると、問題の原因究明が困難になります。
予期されるエラーは適切に処理し、予期しないエラーは上位に伝播させて
ログに記録できるようにします。
```

### 3. 測定可能な基準を設定

曖昧な表現を避け、具体的な数値を示します。

**悪い例**:
```
コードカバレッジは高く保つこと
```

**良い例**:
```
コードカバレッジ目標:
- ユニットテスト: 80%以上
- 統合テスト: 60%以上
- E2Eテスト: 主要フロー100%
```

## Git運用ルール

### ブランチ戦略（Git Flow採用）

**Git Flowとは**:
Vincent Driessenが提唱した、機能開発・リリース・ホットフィックスを体系的に管理するブランチモデル。明確な役割分担により、チーム開発での並行作業と安定したリリースを実現します。

**ブランチ構成**:
```
main (本番環境)
└── develop (開発・統合環境)
    ├── feature/* (新機能開発)
    ├── fix/* (バグ修正)
    └── release/* (リリース準備)※必要に応じて
```

**運用ルール**:
- **main**: 本番リリース済みの安定版コードのみを保持。タグでバージョン管理
- **develop**: 次期リリースに向けた最新の開発コードを統合。CIでの自動テスト実施
- **feature/\*、fix/\***: developから分岐し、作業完了後にPRでdevelopへマージ
- **直接コミット禁止**: すべてのブランチでPRレビューを必須とし、コード品質を担保
- **マージ方針**: feature→develop は squash merge、develop→main は merge commit を推奨

**Git Flowのメリット**:
- ブランチの役割が明確で、複数人での並行開発がしやすい
- 本番環境(main)が常にクリーンな状態に保たれる
- 緊急対応時はhotfixブランチで迅速に対応可能（必要に応じて導入）

### コミットメッセージの規約

**Conventional Commitsを推奨**:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type一覧**:
```
feat: 新機能 (minor version up)
fix: バグ修正 (patch version up)
docs: ドキュメント
style: フォーマット (コードの動作に影響なし)
refactor: リファクタリング
perf: パフォーマンス改善
test: テスト追加・修正
build: ビルドシステム
ci: CI/CD設定
chore: その他 (依存関係更新など)

BREAKING CHANGE: 破壊的変更 (major version up)
```

**良いコミットメッセージの例**:

```
feat(task): 優先度設定機能を追加

ユーザーがタスクに優先度(高/中/低)を設定できるようになりました。

実装内容:
- Taskモデルにpriorityフィールド追加
- CLI に --priority オプション追加
- 優先度によるソート機能実装

破壊的変更:
- Task型の構造が変更されました
- 既存のタスクデータはマイグレーションが必要です

Closes #123
BREAKING CHANGE: Task型にpriority必須フィールド追加
```

### プルリクエストのテンプレート

**効果的なPRテンプレート**:

```markdown
## 変更の種類
- [ ] 新機能 (feat)
- [ ] バグ修正 (fix)
- [ ] リファクタリング (refactor)
- [ ] ドキュメント (docs)
- [ ] その他 (chore)

## 変更内容
### 何を変更したか
[簡潔な説明]

### なぜ変更したか
[背景・理由]

### どのように変更したか
- [変更点1]
- [変更点2]

## テスト
### 実施したテスト
- [ ] ユニットテスト追加
- [ ] 統合テスト追加
- [ ] 手動テスト実施

### テスト結果
[テスト結果の説明]

## 関連Issue
Closes #[番号]
Refs #[番号]

## レビューポイント
[レビュアーに特に見てほしい点]
```

## テスト戦略

### テストピラミッド

```
       /\
      /E2E\       少 (遅い、高コスト)
     /------\
    / 統合   \     中
   /----------\
  / ユニット   \   多 (速い、低コスト)
 /--------------\
```

**目標比率**:
- ユニットテスト: 70%
- 統合テスト: 20%
- E2Eテスト: 10%

### テストの書き方

**Given-When-Then パターン**:

```python
class TestTaskService:
    """TaskServiceのテストスイート"""

    class TestTaskCreation:
        """タスク作成のテスト"""

        async def test_create_with_valid_data(
            self, mock_repository: TaskRepository
        ) -> None:
            """正常なデータの場合、タスクを作成できる"""
            # Given: 準備
            service = TaskService(mock_repository)
            valid_data = {"title": "テスト"}

            # When: 実行
            result = await service.create(valid_data)

            # Then: 検証
            assert result.id is not None
            assert result.title == "テスト"

        async def test_create_with_empty_title_raises_error(
            self, mock_repository: TaskRepository
        ) -> None:
            """タイトルが空の場合、ValidationErrorを送出する"""
            # Given: 準備
            service = TaskService(mock_repository)
            invalid_data = {"title": ""}

            # When/Then: 実行と検証
            with pytest.raises(ValidationError):
                await service.create(invalid_data)
```

### カバレッジ目標

**測定可能な目標**:

```toml
# pyproject.toml
[tool.coverage.run]
branch = true
source = ["src"]

[tool.coverage.report]
fail_under = 80
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]

[tool.coverage.paths]
source = ["src"]

# より厳密なカバレッジ要求領域
# pytest --cov=src --cov-fail-under=90 tests/unit/services/
```

**理由**:
- 重要なビジネスロジック(services/)は高いカバレッジを要求
- UI層は低めでも許容
- 100%を目指さない (コストと効果のバランス)

## コードレビュープロセス

### レビューの目的

1. **品質保証**: バグの早期発見
2. **知識共有**: チーム全体でコードベースを理解
3. **学習機会**: ベストプラクティスの共有

### 効果的なレビューのポイント

**レビュアー向け**:

1. **建設的なフィードバック**
```markdown
## ❌ 悪い例
このコードはダメです。

## ✅ 良い例
この実装だと O(n²) の時間計算量になります。
辞書を使うと O(n) に改善できます:

```python
task_map = {task.id: task for task in tasks}
result = [task_map[task_id] for task_id in ids]
```
```

2. **優先度の明示**
```markdown
[必須] セキュリティ: パスワードがログに出力されています
[推奨] パフォーマンス: ループ内でのDB呼び出しを避けましょう
[提案] 可読性: この関数名をもっと明確にできませんか？
[質問] この処理の意図を教えてください
```

3. **ポジティブなフィードバックも**
```markdown
✨ この実装は分かりやすいですね！
👍 エッジケースがしっかり考慮されています
💡 このパターンは他でも使えそうです
```

**レビュイー向け**:

1. **セルフレビューを実施**
   - PR作成前に自分でコードを見直す
   - 説明が必要な箇所にコメントを追加

2. **小さなPRを心がける**
   - 1PR = 1機能
   - 変更ファイル数: 10ファイル以内を推奨
   - 変更行数: 300行以内を推奨

3. **説明を丁寧に**
   - なぜこの実装にしたか
   - 検討した代替案
   - 特に見てほしいポイント

### レビュー時間の目安

- 小規模PR (100行以下): 15分
- 中規模PR (100-300行): 30分
- 大規模PR (300行以上): 1時間以上

**原則**: 大規模PRは避け、分割する

## 自動化の推進（該当する場合）

### 品質チェックの自動化

**自動化項目と採用ツール**:

1. **Lintチェック**
   - **Ruff**
     - Rust製の高速リンター・フォーマッター
     - Flake8、isort、pyupgrade等の機能を統合
     - 設定ファイル: `pyproject.toml`

2. **コードフォーマット**
   - **Black** + **Ruff**
     - Black: コードスタイルを自動整形し、レビュー時の議論を削減
     - Ruff: インポート順序整理やコードスタイルチェック
     - 設定ファイル: `pyproject.toml`

3. **型チェック**
   - **Mypy**
     - `mypy --strict`で厳密な型チェックを実施
     - ビルドとは独立して型安全性を検証
     - 設定ファイル: `pyproject.toml`

4. **テスト実行**
   - **Pytest**
     - Python標準のテストフレームワーク
     - プラグインエコシステムが豊富
     - カバレッジ測定（pytest-cov）が利用可能
     - 設定ファイル: `pyproject.toml`

5. **依存関係管理**
   - **Poetry** または **pip + pip-tools**
     - Poetry: 依存関係とパッケージングを一元管理
     - 設定ファイル: `pyproject.toml`

**実装方法**:

**1. CI/CD (GitHub Actions)**
```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install Poetry
        run: |
          curl -sSL https://install.python-poetry.org | python3 -
          echo "$HOME/.local/bin" >> $GITHUB_PATH
      - name: Install dependencies
        run: poetry install
      - name: Lint with ruff
        run: poetry run ruff check .
      - name: Format check with black
        run: poetry run black --check .
      - name: Type check with mypy
        run: poetry run mypy .
      - name: Test with pytest
        run: poetry run pytest --cov --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v4
```

**2. Pre-commit フック (pre-commit)**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/psf/black
    rev: 24.1.1
    hooks:
      - id: black

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-requests]
```

```toml
# pyproject.toml
[tool.poetry.scripts]
lint = "ruff check ."
format = "black ."
typecheck = "mypy ."
test = "pytest"
```

**導入効果**:
- コミット前に自動チェックが走り、不具合コードの混入を防止
- PR作成時に自動でCI実行され、マージ前に品質を担保
- 早期発見により、修正コストを最大80%削減（バグ検出が本番後の場合と比較）

**この構成を選んだ理由**:
- 2025年時点でのPythonエコシステムにおける標準的かつモダンな構成
- Ruffは高速で、複数ツールの機能を統合している
- ツール間の互換性が高く、設定の衝突が少ない
- 開発体験と実行速度のバランスが優れている

## チェックリスト

- [ ] ブランチ戦略が決まっている
- [ ] コミットメッセージ規約が明確である
- [ ] PRテンプレートが用意されている
- [ ] テストの種類とカバレッジ目標が設定されている
- [ ] コードレビュープロセスが定義されている
- [ ] CI/CDパイプラインが構築されている

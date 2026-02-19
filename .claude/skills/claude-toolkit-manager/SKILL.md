# Claude Toolkit Manager

**目的**: Claude Code のコマンド・スキル・エージェントファイルを作成・更新し、共通リポジトリとプロジェクト固有ファイルを適切に管理する

**使用タイミング**: ユーザーが新しいコマンド/スキル/エージェントを作成・更新したい時に明示的に呼び出す

---

## スキルの動作フロー

### 1. ユーザーからの入力を受け取る

- **ファイルタイプ**: コマンド / スキル / エージェント
- **操作**: 新規作成 / 更新
- **ファイル名**: 作成・更新するファイル名
- **内容**: ファイルの内容（新規作成の場合）または変更内容（更新の場合）

### 2. 内容を分析して配置先を自動判断

以下の基準で分析：

**プロジェクト固有と判断する要素:**
- プロジェクト固有のファイルパス・ディレクトリ名への言及
- プロジェクト固有の環境変数・設定値
- プロジェクト固有の技術スタック（例: 特定のフレームワーク名）
- プロジェクト名やドメイン固有の用語
- 具体的なデプロイ手順・インフラ構成

**共通リポジトリと判断する要素:**
- 汎用的なワークフロー・パターンの説明
- プロジェクトに依存しない抽象的なガイドライン
- 複数プロジェクトで再利用可能な手順
- 言語・フレームワーク非依存の内容

**分割が必要と判断する要素:**
- 一部に汎用的な手順、一部にプロジェクト固有の記述がある
- テンプレート + プロジェクト固有のカスタマイズが混在

### 3. ユーザーに確認

自動判断した結果を提示し、以下を確認：
- 共通リポジトリ（`.claude-shared/`）に配置
- プロジェクト固有（`.claude/`）に配置
- 分割（共通 + 固有）

分割の場合：
- どの部分を共通化するか
- どの部分をプロジェクト固有にするか

### 4. ファイルを作成・更新

**共通リポジトリの場合:**
1. `.claude-shared/commands|skills|agents/` に配置
2. Git commit
3. `make claude-push` で共通リポジトリにプッシュ
4. `make claude-link` でsymlinkを再作成

**プロジェクト固有の場合:**
1. `.claude/commands|skills|agents/` に配置
2. Git commit
3. プロジェクトリポジトリにプッシュ

**分割の場合:**
1. 共通部分を `.claude-shared/` に配置
2. 固有部分を `.claude/` に配置（共通部分を参照する構造）
3. 両方を Git commit
4. 共通リポジトリに `make claude-push`
5. プロジェクトリポジトリにプッシュ

---

## 実装ガイドライン

### ステップ1: ユーザー入力の収集

`AskUserQuestion` を使用して以下を収集：
- ファイルタイプ（コマンド/スキル/エージェント）
- 操作（新規作成/更新）
- ファイル名

### ステップ2: 内容の取得

- **新規作成**: ユーザーに内容を入力してもらう、または対話的に生成
- **更新**: 既存ファイルを Read して内容を確認し、変更内容をユーザーと確認

### ステップ3: 内容分析と配置先判断

以下のキーワード・パターンを検出：

```python
# プロジェクト固有キーワード（例）
project_specific_patterns = [
    r'ai-curated-newsletter',  # プロジェクト名
    r'\.env',  # 環境変数ファイル
    r'AWS Lambda',  # 特定インフラ
    r'Bedrock',  # 特定サービス
    r'src/handler\.py',  # 具体的なファイルパス
    r'SES',  # プロジェクト固有サービス
]

# 汎用キーワード（例）
generic_patterns = [
    r'ステアリングファイル',
    r'PRD',
    r'機能設計',
    r'アーキテクチャ設計',
    r'Git commit',
    r'品質チェック',
]
```

判断ロジック：
- プロジェクト固有キーワードが多い → 固有
- 汎用キーワードのみ → 共通
- 両方が混在 → 分割を提案

### ステップ4: ユーザー確認

`AskUserQuestion` で以下を確認：

```
質問: "このファイルの配置先はどうしますか？"
選択肢:
1. 共通リポジトリ（推奨）- 理由: [自動判断の理由]
2. プロジェクト固有 - 理由: [自動判断の理由]
3. 分割（共通 + 固有）
```

### ステップ5: ファイル作成・Git操作

**共通リポジトリの場合:**

```bash
# ファイルを作成
Write(.claude-shared/commands/example.md)

# Git commit
git add .claude-shared/
git commit -m "feat: Add example command to shared toolkit"

# 共通リポジトリにプッシュ
make claude-push

# symlink を再作成
make claude-link
```

**プロジェクト固有の場合:**

```bash
# ファイルを作成
Write(.claude/commands/local-example.md)

# Git commit
git add .claude/
git commit -m "feat: Add project-specific example command"

# プロジェクトリポジトリにプッシュ
git push origin main
```

**分割の場合:**

```bash
# 共通部分
Write(.claude-shared/skills/example/SKILL.md)
git add .claude-shared/
git commit -m "feat: Add example skill (shared part)"
make claude-push

# 固有部分
Write(.claude/skills/example/local-config.md)
git add .claude/
git commit -m "feat: Add example skill (project-specific part)"
git push origin main

# symlink を再作成
make claude-link
```

---

## 使用例

### 例1: 新しいコマンドを作成

```
ユーザー: "デプロイコマンドを作成したい"

スキル:
1. ファイルタイプ: コマンド
2. 操作: 新規作成
3. ファイル名: deploy.md
4. 内容をユーザーと対話的に作成
5. 内容を分析 → プロジェクト固有と判断（AWS Lambda固有の手順）
6. ユーザーに確認 → プロジェクト固有を選択
7. .claude/commands/deploy.md に作成
8. Git commit & push
```

### 例2: 既存のスキルを更新

```
ユーザー: "steeringスキルを更新したい"

スキル:
1. ファイルタイプ: スキル
2. 操作: 更新
3. ファイル名: steering
4. 既存ファイルを Read
5. 変更内容をユーザーと確認
6. 内容を分析 → 汎用的なワークフローと判断
7. ユーザーに確認 → 共通リポジトリを選択
8. .claude-shared/skills/steering/SKILL.md を更新
9. Git commit
10. make claude-push で共通リポジトリにプッシュ
```

### 例3: スキルを分割

```
ユーザー: "Python品質チェックスキルを作成したい"

スキル:
1. ファイルタイプ: スキル
2. 操作: 新規作成
3. ファイル名: python-qa
4. 内容をユーザーと対話的に作成
5. 内容を分析 → 汎用部分とプロジェクト固有部分が混在
   - 汎用: pytest, ruff, mypyの基本的な使い方
   - 固有: プロジェクト固有のruff設定、特定のテストパス
6. ユーザーに確認 → 分割を選択
7. 共通部分: .claude-shared/skills/python-qa/SKILL.md
   固有部分: .claude/skills/local-python-qa/SKILL.md
8. 両方を Git commit
9. make claude-push + git push
```

---

## 注意事項

- **symlink の扱い**: 共通ファイルを更新した後、必ず `make claude-link` でsymlinkを再作成
- **Git コンフリクト**: 共通リポジトリとプロジェクトリポジトリで同時に変更が発生した場合、マージコンフリクトに注意
- **命名規則**: プロジェクト固有ファイルには `local-` プレフィックスを推奨（視認性向上のため）
- **ドキュメント更新**: 新しいコマンド/スキル/エージェントを追加した場合、README.mdの更新も検討

---

## 実装時の重要なポイント

1. **AskUserQuestion を活用**: 自動判断した結果を必ずユーザーに確認
2. **Git 操作の自動化**: 共通ファイル更新時は `make claude-push` を必ず実行
3. **エラーハンドリング**: Git 操作でエラーが発生した場合、ユーザーに明確に報告
4. **変更履歴の記録**: コミットメッセージは明確に（feat/fix/docs などのプレフィックスを使用）

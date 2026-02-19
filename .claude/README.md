# Claude Python Toolkit

Pythonプロジェクト向けの Claude Code ワークフロー共通リポジトリ

## 概要

このリポジトリは、複数のPythonプロジェクトで共有する Claude Code のワークフロー（コマンド、スキル、エージェント）を提供します。Git Subtree + symlink を使用してプロジェクトに統合することで、以下の利点があります：

- **一貫性**: プロジェクト間で統一されたワークフローを維持
- **効率化**: ワークフロー改善を1箇所で行い、全プロジェクトに波及
- **迅速な立ち上げ**: 新規プロジェクトでの設定時間を大幅短縮
- **明確な分離**: 共通ファイルとプロジェクト固有ファイルがsymlinkで明確に区別

## アーキテクチャ

```
プロジェクト/
├── .claude-shared/              # git subtreeで共通リポを配置
│   ├── commands/                # 共通コマンド（実ファイル）
│   ├── skills/                  # 共通スキル（実ファイル）
│   └── agents/                  # 共通エージェント（実ファイル）
├── .claude/                     # Claude Codeが認識するディレクトリ
│   ├── commands/                # symlink（共通） + 実ファイル（プロジェクト固有）
│   ├── skills/                  # symlink（共通） + 実ファイル（プロジェクト固有）
│   ├── agents/                  # symlink（共通） + 実ファイル（プロジェクト固有）
│   └── settings.json            # プロジェクト固有設定
└── Makefile                     # Subtree + symlink管理
```

**ポイント:**
- `.claude-shared/` には共通リポジトリの実ファイルが配置される（git subtree）
- `.claude/` には共通リポジトリへの symlink と、プロジェクト固有ファイルが配置される
- Makefileの `claude-link` が自動的にsymlinkを作成（既存ファイルはスキップ）
- Git は symlink をサポートしているため、通常の Git 操作でコミット可能

## ディレクトリ構造

```
claude-python-toolkit/
├── README.md                     # このファイル
├── .gitignore                    # .idea/, __pycache__/ などを除外
├── Makefile.example              # Subtree + symlink操作用Makefileテンプレート
├── commands/                     # Claude Codeコマンド定義
│   ├── add-feature.md
│   ├── spec-plan.md              # ステアリングファイル作成
│   ├── review-docs.md
│   ├── commit-push-close.md
│   ├── research-plan.md
│   └── setup-project.md
├── skills/                       # Claude Codeスキル定義
│   ├── steering/                 # ステアリングファイル管理
│   ├── prd-writing/              # PRD作成
│   ├── functional-design/        # 機能設計
│   ├── architecture-design/      # アーキテクチャ設計
│   ├── repository-structure/     # リポジトリ構造定義
│   ├── glossary-creation/        # 用語集作成
│   ├── git-commit/               # Gitコミット支援
│   ├── close-issue/              # Issue クローズ
│   ├── feedback-response/        # フィードバック対応
│   └── python-pro/               # Python開発ベストプラクティス
├── agents/                       # Claude Code エージェント定義
│   ├── doc-reviewer.md           # ドキュメントレビュー
│   └── implementation-validator.md  # 実装検証
├── settings.example.json         # Claude Code設定テンプレート
└── CLAUDE.md.template            # プロジェクトCLAUDE.mdテンプレート
```

## 使用方法

### 1. 初回セットアップ

#### ステップ1: Makefile を作成

```bash
# プロジェクトルートで実行
cd your-project

# Makefile.example をダウンロード
curl -O https://raw.githubusercontent.com/k-negishi/claude-python-toolkit/main/Makefile.example

# Makefile にリネーム
mv Makefile.example Makefile

# k-negishi を実際のGitHubユーザー名に置換（必要に応じて）
sed -i '' 's/k-negishi/your-github-username/g' Makefile
```

#### ステップ2: Subtree を追加

```bash
# Makefileを使用（推奨）
make claude-init

# または、直接コマンドを実行
# git subtree add --prefix=.claude-shared https://github.com/k-negishi/claude-python-toolkit.git main --squash
```

`make claude-init` は以下を自動実行します：
1. `.claude-shared/` に Subtree を追加
2. `.claude/` ディレクトリ構造を作成
3. symlink を自動作成

#### ステップ3: プロジェクト固有ファイルを追加

```bash
# 設定ファイルを作成
cp .claude-shared/settings.example.json .claude/settings.json
# ... 編集

# プロジェクト固有のスキルを作成（例）
mkdir -p .claude/skills/local-python-qa
cat > .claude/skills/local-python-qa/SKILL.md <<EOF
# Python品質チェックスキル
...
EOF
```

**重要**: プロジェクト固有ファイルは `.claude/` に直接配置してください。
- Makefileの `claude-link` は、既存ファイルをスキップするため、プロジェクト固有ファイルが優先されます
- ファイル名に特別なプレフィックスは不要です（symlink と実ファイルで自動的に区別されます）

#### ステップ4: コミット

```bash
git add .claude-shared/ .claude/ Makefile .gitignore
git commit -m "Integrate claude-python-toolkit via Git Subtree + symlink"
git push origin main
```

### 2. 共通リポジトリの更新を取得

```bash
# Makefileを使用（推奨）
make claude-update

# または、直接コマンドを実行
# git subtree pull --prefix=.claude-shared https://github.com/k-negishi/claude-python-toolkit.git main --squash
# make claude-link  # symlink を再作成
```

`make claude-update` は以下を自動実行します：
1. `.claude-shared/` の Subtree を更新
2. symlink を再作成（既存ファイルはスキップ）

### 3. ローカルの変更を共通リポジトリにプッシュ

共通ファイル（`.claude-shared/` 内）に改善を加えた場合、共通リポジトリにプッシュできます。

```bash
# 共通ファイルを編集
vim .claude-shared/commands/spec-plan.md

# 変更をコミット
git add .claude-shared/
git commit -m "Improve spec-plan command"

# 共通リポジトリにプッシュ
make claude-push

# または、直接コマンドを実行
# git subtree push --prefix=.claude-shared https://github.com/k-negishi/claude-python-toolkit.git main
```

**注意**: `.claude/` 内のsymlinkは、`.claude-shared/` の実ファイルを参照しているため、`.claude-shared/` を編集してください。

### 4. symlink の管理

```bash
# symlink を再作成（既存ファイルはスキップ）
make claude-link

# symlink を削除（実ファイルは保持）
make claude-clean

# Subtree の状態確認
make claude-status
```

## プロジェクト側の構成例

Subtree + symlink 統合後のプロジェクト側の構成:

```
your-project/
├── Makefile                      # Subtree + symlink管理
├── src/
├── .claude-shared/               # git subtree（共通リポジトリの実ファイル）
│   ├── commands/
│   ├── skills/
│   └── agents/
└── .claude/                      # Claude Code認識ディレクトリ
    ├── commands/
    │   ├── add-feature.md        # ← symlink（共通）
    │   ├── spec-plan.md          # ← symlink（共通）
    │   └── my-deploy.md          # ← 実ファイル（プロジェクト固有）
    ├── skills/
    │   ├── steering/             # ← symlink（共通）
    │   ├── python-pro/           # ← symlink（共通）
    │   └── local-python-qa/      # ← 実ディレクトリ（プロジェクト固有）
    ├── agents/
    │   └── doc-reviewer.md       # ← symlink（共通）
    └── settings.json             # ← 実ファイル（プロジェクト固有）
```

**symlink の確認:**

```bash
ls -la .claude/commands/
# lrwxr-xr-x  1 user  staff   47 Feb 15 18:03 add-feature.md -> ../../.claude-shared/commands/add-feature.md
# -rw-r--r--  1 user  staff  123 Feb 15 18:03 my-deploy.md
```

## 必須ファイル一覧

プロジェクト側で最低限必要なファイル:

- `Makefile` - Subtree + symlink操作用（Makefile.exampleから作成）
- `.claude/settings.json` - プロジェクト固有の設定
- `CLAUDE.md` - プロジェクト固有のドキュメント（CLAUDE.md.templateをベースに作成）
- `.gitignore` - `.claude-shared/.gitignore` を除外する設定

**.gitignore の例:**

```gitignore
# Claude Code - 共通リポジトリの.gitignoreは除外
.claude-shared/.gitignore
```

## 開発ワークフロー

このツールキットを統合したプロジェクトでの、Claude Code を使った開発ワークフローです。

### 初回: プロジェクト立ち上げ

新規プロジェクトを開始する場合の流れです。

```
┌─────────────────────────────────────────────────┐
│ 1. ツールキット統合                                │
│    make claude-init                              │
│                                                  │
│ 2. アイデアを書き出す（任意）                       │
│    docs/ideas/ にメモを配置                        │
│                                                  │
│ 3. /setup-project                                │
│    → 6つの永続ドキュメントを対話的に作成            │
│                                                  │
│ 4. /spec-plan [最初の機能]                         │
│    → ステアリングファイルを対話的に作成              │
│                                                  │
│ 5. /implement [ステアリングディレクトリパス]          │
│    → TDD実装 → 品質チェック                        │
│                                                  │
│ 6. /commit-push-close                            │
│    → コミット → push → issue クローズ              │
└─────────────────────────────────────────────────┘
```

#### 具体例: タスク管理APIを新規開発する場合

```bash
# ── ステップ1: ツールキット統合 ──
make claude-init
cp .claude-shared/settings.example.json .claude/settings.json
cp .claude-shared/CLAUDE.md.template CLAUDE.md
git add . && git commit -m "chore: claude-python-toolkitを統合"

# ── ステップ2: アイデアを書き出す（任意） ──
mkdir -p docs/ideas
cat > docs/ideas/initial-requirements.md << 'EOF'
# タスク管理API

- ユーザーがタスクを作成・編集・削除できる REST API
- FastAPI + PostgreSQL
- 認証はJWT
- タスクにはラベルと期限を設定できる
EOF

# ── ステップ3: Claude Code で対話的にドキュメント作成 ──
claude
> /setup-project
# → docs/ideas/ の内容を元に、以下の6ファイルを対話的に作成:
#   ✅ docs/product-requirements.md   （PRD）
#   ✅ docs/functional-design.md      （機能設計）
#   ✅ docs/architecture.md           （アーキテクチャ）
#   ✅ docs/repository-structure.md   （リポジトリ構造）
#   ✅ docs/development-guidelines.md （開発ガイドライン）
#   ✅ docs/glossary.md               （用語集）

# ── ステップ4: 最初の機能を計画 ──
> /spec-plan タスクのCRUDを実装
# → タスクボリュームを判定（大規模/中規模/小規模）
# → ユーザーにファイル範囲を確認
# → .steering/20260215-タスクのCRUDを実装/ にステアリングファイルを作成
#   ├── requirements.md（要件）
#   ├── design.md（設計）
#   └── tasklist.md（タスクリスト）

# （内容を確認し、必要に応じて修正を依頼）
> requirements.md の非機能要件にレスポンス200ms以内を追加して

# ── ステップ5: 実装 ──
> /implement .steering/20260215-タスクのCRUDを実装/
# → TDD (RED → GREEN → REFACTOR) で実装
# → pytest, ruff, mypy が全てパス

# ── ステップ6: コミットしてpush ──
> /commit-push-close
```

### 2回目以降: 機能追加・改修

プロジェクトの永続ドキュメント（`docs/`）が既にある状態で、新しい機能追加や改修を行う場合の流れです。2つのパターンがあります。

#### パターンA: 標準フロー（/spec-plan → /implement）

機能追加や複数ファイルにまたがる改修に使います。

```
/spec-plan [機能名 or issue URL]
    ├── プロジェクト理解（CLAUDE.md, docs/ を読む）
    ├── 既存パターン調査（Grepでソースコード検索）
    ├── 影響範囲の事前調査
    ├── タスクボリューム判定 → ユーザーに確認
    └── ステアリングファイル作成
        └── .steering/[YYYYMMDD]-[機能名]/
            ├── requirements.md（要件）  ← 大規模のみ
            ├── design.md（設計）        ← 大規模・中規模
            └── tasklist.md（タスクリスト）← 常に作成
    ↓
  （ユーザーが内容を確認・修正）
    ↓
/implement [ステアリングディレクトリパス]
    ├── TDDサイクル（RED → GREEN → REFACTOR）
    ├── 品質チェック（pytest, ruff, mypy）
    └── 実装検証（implementation-validator）
    ↓
/commit-push-close
```

**具体例1: GitHub issue から機能追加**

```bash
claude
# ── 計画フェーズ ──
> /spec-plan https://github.com/owner/task-api/issues/12
# issue「タスクに優先度フィールドを追加」を自動取得
#
# タスクボリューム: 【大規模】と判定
#   - 新機能追加である
#   - models, API, テストの複数ファイルに影響
# → ユーザーが【大】requirements + design + tasklist を選択
#
# .steering/20260215-タスクに優先度フィールドを追加/ を作成
#   → requirements.md: issue内容 + 実装方針（TDD）
#   → design.md: Priority enum定義、DB migration、API変更
#   → tasklist.md: 全タスクをTDDサブタスク付きで列挙

# （内容を確認してOK）

# ── 実装フェーズ ──
> /implement .steering/20260215-タスクに優先度フィールドを追加/
#   → RED: test_priority.py に失敗するテストを書く
#   → GREEN: models.py に Priority enum を追加、テストをパス
#   → REFACTOR: コード整理
#   → pytest ✅  ruff ✅  mypy ✅

# ── コミット ──
> /commit-push-close
# → add: タスクに優先度フィールドを追加
# → docs: タスクに優先度フィールドを追加のステアリングファイルを追加
# → git push
# → Issue #12 クローズ
```

**具体例2: 認証機能のように慎重に設計したい場合**

```bash
claude
# ── 計画フェーズ（対話的） ──
> /spec-plan ログイン機能を追加

# Claude が質問:
#   「認証方式をどれにしますか?」
#   - JWT (推奨: ステートレスで拡張性が高い)
#   - セッションベース (シンプルだがサーバー負荷が高い)
# → JWT を選択

# ステアリングファイルが生成される:
#   .steering/20260215-ログイン機能を追加/
#   ├── requirements.md
#   ├── design.md
#   └── tasklist.md

# （ユーザーが内容を確認し、必要に応じて修正を依頼）
> design.md のトークン有効期限を30分に変更して

# ── 実装フェーズ ──
> /implement .steering/20260215-ログイン機能を追加/
# → TDD サイクルで実装
# → 全テスト・品質チェックがパス

# ── コミット ──
> /commit-push-close
```

**具体例3: バグ修正（小規模タスク）**

```bash
claude
> /spec-plan 日付のタイムゾーン変換バグを修正

# タスクボリューム: 【小規模】と判定
#   - バグフィックスである
#   - 単一ファイルの修正
# → ユーザーが【小】tasklist のみ を選択
#
# .steering/20260215-日付のタイムゾーン変換バグを修正/ を作成
#   → tasklist.md のみ（シンプルなタスクリスト）

> /implement .steering/20260215-日付のタイムゾーン変換バグを修正/
# → RED: 失敗するテストを書く
# → GREEN: UTC→JST変換を修正、テストをパス
# → pytest ✅  ruff ✅  mypy ✅

> /commit-push-close
```

#### パターンB: 小さな修正・ドキュメント更新

ステアリングファイルが不要な軽微な変更は、コマンドを使わず会話で直接依頼します。

```bash
claude
# ── ドキュメント更新 ──
> PRDに通知機能の要件を追加して
> architecture.md のパフォーマンス要件を見直して
> glossary.md に「優先度」の定義を追加して

# ── リファクタリング ──
> TaskService の重複したバリデーションロジックを共通化して

# ── typo修正 ──
> README.md の誤字を直して

# ── コミット ──
> /commit-push-close
```

### ワークフローの使い分け早見表

| 状況 | 使うコマンド | ステアリングファイル |
|------|-------------|-------------------|
| 新規プロジェクト立ち上げ | `/setup-project` → `/spec-plan` → `/implement` | 作成される |
| 新機能追加 | `/spec-plan` → `/implement` | 対話的に作成 |
| GitHub issue の実装 | `/spec-plan [issue URL]` → `/implement` | 対話的に作成 |
| バグ修正（原因調査が必要） | `/spec-plan` → `/implement` | tasklist のみ |
| 軽微な修正・ドキュメント更新 | 会話で直接依頼 | 不要 |
| コミット・push・issue閉じ | `/commit-push-close` | — |
| ドキュメントレビュー | `/review-docs [パス]` | — |

## トラブルシューティング

### Subtree追加時にコンフリクトが発生した場合

```bash
# --allow-unrelated-histories を追加
git subtree add --prefix=.claude-shared https://github.com/k-negishi/claude-python-toolkit.git main --squash --allow-unrelated-histories
```

### symlink が壊れている場合

```bash
# symlink を再作成
make claude-clean
make claude-link
```

### 既存の `.claude/` を新しいアーキテクチャに移行する場合

詳細は[移行ガイド](docs/migration-guide.md)を参照してください。

基本的な手順：
1. 既存の `.claude/` をバックアップ
2. プロジェクト固有ファイルを退避
3. `.claude/` を削除
4. 新しいSubtreeを `.claude-shared/` に追加
5. symlink を作成
6. プロジェクト固有ファイルを復元

## Makefileコマンド一覧

| コマンド | 説明 |
|---------|------|
| `make claude-init` | 初回セットアップ（Subtree追加 + symlink作成） |
| `make claude-update` | 共通リポジトリの更新を取得 + symlink再作成 |
| `make claude-push` | ローカルの変更を共通リポジトリにプッシュ |
| `make claude-link` | symlink を作成（既存ファイルはスキップ） |
| `make claude-clean` | symlink を削除（実ファイルは保持） |
| `make claude-status` | Subtree の状態確認 |

## 謝辞（参考元ライセンス情報）

以下のリポジトリのアイデア・構成・実装方針を参考にしています。

- https://github.com/GenerativeAgents/claude-code-book-chapter8
- https://github.com/Jeffallan/claude-skills

上記リポジトリはいずれも MIT License で公開されています。


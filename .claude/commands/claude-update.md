---
description: 共通リポジトリ（claude-python-toolkit）から最新の更新を取得し、symlinkを再作成する
---

# Claude Update コマンド

共通リポジトリ（claude-python-toolkit）の最新の変更をプロジェクトに反映します。

## 実行内容

1. `.claude-shared/` の Subtree を更新（`git subtree pull`）
2. symlink を再作成（既存ファイルはスキップ）

## 使用方法

```bash
/claude-update
```

または

```bash
make claude-update
```

## 実行フロー

### ステップ1: 現在の状態を確認

まず、未コミットの変更がないか確認します。

```bash
git status
```

**重要**: 作業ツリーに変更がある場合、Subtree pull が失敗します。先にコミットしてください。

### ステップ2: Subtree pull を実行

```bash
git subtree pull --prefix=.claude-shared https://github.com/k-negishi/claude-python-toolkit.git main --squash
```

**エラーハンドリング:**
- `working tree has modifications` エラーが発生した場合 → 変更をコミットしてから再実行
- マージコンフリクトが発生した場合 → コンフリクトを解決してコミット

### ステップ3: symlink を再作成

```bash
# Makefileを使用
make claude-link
```

これにより、`.claude-shared/` の新しいファイルへのsymlinkが `.claude/` に作成されます。
既存のファイル（プロジェクト固有ファイル）はスキップされます。

### ステップ4: 更新内容を確認

```bash
git log --oneline -5
```

最新のSubtreeマージコミットを確認します。

## コンフリクト解決

マージコンフリクトが発生した場合：

```bash
# コンフリクトファイルを確認
git status

# 手動でコンフリクトを解決、または一方を採用
git checkout --theirs .claude-shared/path/to/file  # リモート優先
git checkout --ours .claude-shared/path/to/file    # ローカル優先

# 解決後、ステージングしてコミット
git add .claude-shared/
git commit -m "Merge subtree updates from claude-python-toolkit"
```

## 実装

以下のコマンドを順次実行します：

```bash
# 1. 作業ツリーの状態を確認
echo "Checking working tree status..."
git_status=$(git status --porcelain)

if [ -n "$git_status" ]; then
    echo "Warning: You have uncommitted changes."
    echo "Please commit or stash them before running claude-update."
    echo ""
    git status
    exit 1
fi

# 2. Subtree pull を実行
echo "Pulling updates from claude-python-toolkit..."
git subtree pull --prefix=.claude-shared https://github.com/k-negishi/claude-python-toolkit.git main --squash

# エラーチェック
if [ $? -ne 0 ]; then
    echo ""
    echo "Error: Subtree pull failed."
    echo "Please resolve any conflicts and commit the merge."
    echo "After resolving, run 'make claude-link' to update symlinks."
    exit 1
fi

# 3. symlink を再作成
echo ""
echo "Updating symlinks..."
make claude-link

# 4. 完了メッセージ
echo ""
echo "✅ Update completed successfully!"
echo ""
echo "Changes pulled from claude-python-toolkit:"
git log --oneline --grep="git-subtree-dir: .claude-shared" -1
```

## 使用例

### 通常の更新

```
$ /claude-update

Checking working tree status...
Pulling updates from claude-python-toolkit...
From https://github.com/k-negishi/claude-python-toolkit
 * branch            main       -> FETCH_HEAD

Updating symlinks...
Creating symlinks from .claude-shared/ to .claude/...
  Skip (exists): .claude/commands/add-feature.md
  Link: .claude/skills/new-skill -> .claude-shared/skills/new-skill

✅ Update completed successfully!
```

### エラー: 未コミットの変更がある場合

```
$ /claude-update

Checking working tree status...
Warning: You have uncommitted changes.
Please commit or stash them before running claude-update.

Changes not staged for commit:
  modified:   README.md
```

### マージコンフリクトが発生した場合

```
$ /claude-update

Pulling updates from claude-python-toolkit...
Auto-merging .claude-shared/README.md
CONFLICT (content): Merge conflict in .claude-shared/README.md

Error: Subtree pull failed.
Please resolve any conflicts and commit the merge.
After resolving, run 'make claude-link' to update symlinks.
```

解決手順：

```bash
# コンフリクトを解決
git checkout --theirs .claude-shared/README.md
git add .claude-shared/README.md
git commit -m "Merge subtree updates from claude-python-toolkit"

# symlink を再作成
make claude-link
```

## 注意事項

- **定期的な更新**: 共通リポジトリの改善を活用するため、定期的に `/claude-update` を実行することを推奨
- **プロジェクト固有ファイルは保持**: symlink 再作成時、`.claude/` 内のプロジェクト固有ファイルは自動的にスキップされます
- **コンフリクトに注意**: 共通ファイルをローカルでカスタマイズしている場合、更新時にコンフリクトが発生する可能性があります

## 関連コマンド

- `/claude-push` - ローカルの変更を共通リポジトリにプッシュ
- `make claude-status` - Subtree の状態を確認
- `make claude-link` - symlink のみを再作成
- `make claude-clean` - symlink を削除

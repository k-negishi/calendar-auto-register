---
description: 変更をコミットし、リモートにpushし、GitHub issueをクローズする
argument-hint: issue番号（オプション）
---

# Commit, Push, Close コマンド

変更をコミットし、リモートにpushし、関連するGitHub issueをクローズする一連の操作を自動実行するコマンドです。

## 使い方

```bash
/commit-push-close [issue番号] [ステアリングディレクトリパス]
```

**引数** (すべてオプション):
- `issue番号`: クローズするGitHub issueの番号。省略した場合は**会話から自動検出**。
- `ステアリングディレクトリパス`: コミットするステアリングファイルのディレクトリパス。省略した場合は**会話から自動検出**。

**自動検出の仕組み**:
- **issue番号**: 会話の中で `/plan https://github.com/.../issues/32` や `/implement` 実行時の issue 参照から検出
- **ステアリングディレクトリパス**: 会話の中で `/implement .steering/20260215-linter強化/` を実行していた場合、そのパスを検出

**例**:
```bash
# 基本的な使い方（推奨）: 引数なしで自動検出
/commit-push-close
# → 会話から issue番号とステアリングファイルを自動検出
# → 実装コミット → ステアリングファイルコミット → push → issueクローズ

# 明示的に指定（上書き）
/commit-push-close 17 .steering/20260215-メールの体裁変更/
# → 指定されたissue番号とステアリングファイルを使用

# issue番号のみ明示的に指定
/commit-push-close 17
# → issue #17をクローズ、ステアリングファイルは会話から検出
```

## 実行フロー

### ステップ1: Git Commit（実装ファイル）

`Skill('git-commit')` を呼び出してコミットを作成します。

- 変更内容を確認（`git status`, `git diff`）
- 適切なprefixを判定（add/fix/docs/refactor/test/chore/perf/build/ci/revert/style）
- コミットメッセージを作成・実行

### ステップ2: Git Commit（ステアリングファイル）

**会話から検出または引数で指定されたステアリングディレクトリパス**がある場合、別コミットとして追加します。

```bash
# ステアリングディレクトリパスが存在する場合のみコミット
if [ -n "$STEERING_PATH" ] && [ -d "$STEERING_PATH" ]; then
  git add "$STEERING_PATH"
  git commit -m "docs: [タスク名]のステアリングファイルを追加

- requirements.md: 要件定義
- design.md: 設計
- tasklist.md: タスクリスト

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
fi
```

**重要**:
- ステアリングファイルは実装コミットとは別に管理されます（git-commitスキルのルール）
- **その回のタスクに関連するステアリングファイルのみ**をコミットします
- 会話から検出されない場合、ステアリングファイルはコミットされません

### ステップ3: Git Push

リモートリポジトリ（main）にpushします。

```bash
git push origin main
```

### ステップ4: GitHub Issue Close（オプション）

引数で指定されたissue番号がある場合、`close-issue` スキルを使用してissueをクローズします。

```
Skill('close-issue', args='<issue番号>')
```

**close-issueスキルが自動的に行うこと**:
- 最新のコミット情報を取得
- ステアリングファイル名を記録（`.steering/[YYYYMMDD]-[タスク名]/`）
- 実装サマリを生成（変更内容、品質チェック結果）
- Issueにコメントを追加
- Issueをクローズ
- **クローズしたissueのURLを出力**

**⚠️ 重要**: close-issueスキルは、以下の形式でissueのURLを出力します:

```
✅ Issue Closed: https://github.com/<owner>/<repo>/issues/<番号>
```

例:
```
✅ Issue Closed: https://github.com/k-negishi/ai-curated-newsletter/issues/17
```

## 注意事項

- **コミット前の確認**: 必ず変更内容を確認してから実行してください
- **自動検出の便利さ**: 通常は引数なしで実行し、会話から自動検出させるのが便利です
- **ステアリングファイルのコミット**: 会話から検出されたステアリングファイルが、実装コミットとは別にコミットされます（prefix: docs）
- **検出結果の確認**: コマンド実行時に検出結果が表示されるので、意図しない値が検出された場合は引数で上書きできます
- **複数issue対応**: 1つのコミットが複数issueに関連する場合は、代表的なissue番号を引数で明示してください
- **issueクローズのタイミング**: issue番号が検出または指定された場合、必ずpush後にクローズされます
- **リモートブランチ**: デフォルトで `main` ブランチにpushします
- **URL出力**: issueをクローズした場合、必ずそのURLを出力します

## 失敗時の対処

### コミットが失敗した場合
- `git status` で変更内容を確認
- 必要に応じてファイルをステージング（`git add`）
- コミットメッセージを見直して再実行

### Pushが失敗した場合
- リモートとの競合を確認（`git pull --rebase`）
- 認証情報を確認
- ネットワーク接続を確認

### Issue Closeが失敗した場合
- issue番号が正しいか確認
- `gh` コマンドの認証状態を確認（`gh auth status`）
- 手動でissueをクローズすることも可能

## 関連コマンド

- `/git-commit`: コミットのみ実行
- `git push`: pushのみ実行
- `gh issue close <番号>`: issueクローズのみ実行

## ベストプラクティス

1. **作業単位でコミット**: 1つの機能・修正ごとにこのコマンドを実行
2. **issue番号の記録**: コミットメッセージにissue番号を含める習慣をつける
3. **テスト実行後に実行**: 必ずテストがパスしてからコミット・push
4. **振り返りを記録**: ステアリングファイルの振り返りセクションを更新してから実行

## 実装の流れ（内部処理）

```text
1. コンテキスト解析と引数の処理

   a) 引数を取得
      - 第1引数: issue番号（オプション）
      - 第2引数: ステアリングディレクトリパス（オプション）

   b) 会話履歴から自動検出
      - issue番号が未指定の場合:
        * 会話内で `/plan https://github.com/.../issues/XX` を検索
        * 会話内で issue番号の言及を検索
        * 見つかった場合、その番号を使用

      - ステアリングディレクトリパスが未指定の場合:
        * 会話内で `/implement .steering/YYYYMMDD-*/` を検索
        * 最近使用されたステアリングディレクトリを検出
        * 見つかった場合、そのパスを使用

   c) 検出結果をユーザーに通知
      ```
      📋 検出結果:
      - Issue番号: #32 (会話から検出)
      - ステアリングファイル: .steering/20260215-linter強化/ (会話から検出)
      ```
   ↓
2. Skill('git-commit') を実行（実装ファイルのコミット）
   ↓
3. [ステアリングディレクトリパスが存在する場合]
   git add [パス]
   git commit（ステアリングファイルのコミット、prefix: docs）

   コミットメッセージ例:
   ```
   docs: [タスク名]のステアリングファイルを追加

   - requirements.md: 要件定義
   - design.md: 設計
   - tasklist.md: タスクリスト

   Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
   ```
   ↓
4. git push origin main を実行
   ↓
5. [issue番号が存在する場合]
   Skill('close-issue', args='<issue番号>') を実行
   - 最新のコミット情報を取得
   - ステアリングファイル名を記録
   - 実装サマリを生成
   - Issueにコメントを追加
   - Issueをクローズ
   - issueのURLを出力
   ↓
6. 完了報告
```

## 使用例

### 例1: 基本的な使い方（推奨）- 会話から自動検出

```bash
# 会話の流れ:
# 1. /plan https://github.com/.../issues/17
# 2. /implement .steering/20260215-メールの体裁変更/
# 3. 実装完了
# 4. ↓このコマンドを実行

/commit-push-close
```

実行結果:
```
📋 検出結果:
- Issue番号: #17 (会話から検出)
- ステアリングファイル: .steering/20260215-メールの体裁変更/ (会話から検出)

✅ Commit (実装): add: メール本文に公開日を追加し体裁を改善
✅ Commit (ステアリング): docs: メールの体裁変更のステアリングファイルを追加
✅ Push: リモートリポジトリ（main）にpush完了

### GitHub Issue更新
- ✅ コメント追加: https://github.com/k-negishi/ai-curated-newsletter/issues/17#issuecomment-xxx
- ✅ Issue #17クローズ: メールの体裁変更

### 実装サマリ
- コミット: 5bae879, 6289767
- ステアリングファイル: .steering/20260215-メールの体裁変更/
- 変更ファイル: 13 files
- 品質チェック: 全てパス

✅ Issue Closed: https://github.com/k-negishi/ai-curated-newsletter/issues/17

すべての作業が正常に完了しました。
```

### 例2: 引数で明示的に指定（上書き）

```bash
/commit-push-close 17 .steering/20260215-メールの体裁変更/
```

実行結果:
```
📋 指定された値を使用:
- Issue番号: #17
- ステアリングファイル: .steering/20260215-メールの体裁変更/

✅ Commit (実装): add: メール本文に公開日を追加し体裁を改善
✅ Commit (ステアリング): docs: メールの体裁変更のステアリングファイルを追加
✅ Push: リモートリポジトリ（main）にpush完了
...
```

### 例3: ステアリングファイルなし、issueのみクローズ

```bash
# 会話でissue番号のみ言及、ステアリングファイルなし
/commit-push-close
```

実行結果:
```
📋 検出結果:
- Issue番号: #17 (会話から検出)
- ステアリングファイル: なし

✅ Commit: add: メール本文に公開日を追加し体裁を改善
✅ Push: リモートリポジトリ（main）にpush完了

### GitHub Issue更新
- ✅ Issue #17クローズ

✅ Issue Closed: https://github.com/k-negishi/ai-curated-newsletter/issues/17
```

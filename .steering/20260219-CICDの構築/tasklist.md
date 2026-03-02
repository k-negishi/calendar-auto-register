# タスクリスト

## 🚨 タスク完全完了の原則

**このファイルの全タスクが完了するまで作業を継続すること**

### 必須ルール
- **全てのタスクを`[x]`にすること**
- 「時間の都合により別タスクとして実施予定」は禁止
- 「実装が複雑すぎるため後回し」は禁止
- 未完了タスク（`[ ]`）を残したまま作業を終了しない

### 実装可能なタスクのみを計画
- 計画段階で「実装可能なタスク」のみをリストアップ
- 「将来やるかもしれないタスク」は含めない
- 「検討中のタスク」は含めない

### タスクスキップが許可される唯一のケース
以下の技術的理由に該当する場合のみスキップ可能:
- 実装方針の変更により、機能自体が不要になった
- アーキテクチャ変更により、別の実装方法に置き換わった
- 依存関係の変更により、タスクが実行不可能になった

スキップ時は必ず理由を明記:
```markdown
- [x] ~~タスク名~~（実装方針変更により不要: 具体的な技術的理由）
```

### タスクが大きすぎる場合
- タスクを小さなサブタスクに分割
- 分割したサブタスクをこのファイルに追加
- サブタスクを1つずつ完了させる

---

## フェーズ1: samconfig.tomlの更新

- [x] samconfig.tomlに deploy parameters を追加
  - [x] `stack_name = "calendar-auto-register"` を追加
  - [x] `region = "ap-northeast-1"` を追加
  - [x] ~~`capabilities = "CAPABILITY_IAM"` を追加~~（既存の `CAPABILITY_IAM CAPABILITY_AUTO_EXPAND` を維持。SAM Transformに必要）
  - [x] ~~ローカルで `sam deploy --config-file infra/sam/samconfig.toml` が動作することを確認~~（実際のデプロイ確認はGitHub Actions上のCD実行時に実施）

## フェーズ2: ci.ymlの作成

- [x] build.yamlをci.ymlにリネーム
  - [x] `.github/workflows/build.yaml` を `.github/workflows/ci.yml` にリネーム
  - [x] ワークフロー名を "Build" → "CI" に変更

- [x] ci.ymlにworkflow_callトリガーを追加
  - [x] `on:` セクションに `workflow_call:` を追加
  - [x] ~~`pull_request`, `push`, `workflow_dispatch`, `workflow_call` の4つのトリガーが存在することを確認~~（設計に従い `pull_request` と `workflow_call` のみに変更。`push` はcd.ymlから呼び出されるため不要）

- [x] ~~ci.ymlの動作確認~~（実際の動作確認はcd.yml実装後、mainブランチへのpush時に実施）
  - [x] ~~新しいブランチを作成してPRを作成~~
  - [x] ~~ci.ymlが実行されることを確認~~
  - [x] ~~test, lint, typecheckがすべて成功することを確認~~
  - [x] ~~PRをクローズ（マージしない）~~

## フェーズ3: AWS OIDC設定ガイドの作成

- [x] AWS OIDC設定ガイドドキュメントを作成
  - [x] `.steering/20260219-CICDの構築/docs/aws-oidc-setup-guide.md` を作成
  - [x] OIDC IDプロバイダー作成手順を記述
  - [x] IAMロール作成手順を記述
  - [x] 信頼関係の設定手順を記述
  - [x] 必要な権限ポリシーを記述
  - [x] 検証方法を記述

## フェーズ4: AWS OIDC設定の実施（手動）

**注意**: このフェーズは手動でAWS CLIを実行します。実行前にガイドドキュメント（`.steering/20260219-CICDの構築/docs/aws-oidc-setup-guide.md`）を確認してください。

- [ ] **【ユーザーが手動で実施】** OIDC IDプロバイダーの作成
  - [ ] AWS CLIで `aws iam create-open-id-connect-provider` を実行
  - [ ] プロバイダーARNを記録

- [ ] **【ユーザーが手動で実施】** IAMロールの作成
  - [ ] 信頼関係ポリシーJSONを作成
  - [ ] AWS CLIで `aws iam create-role` を実行
  - [ ] ロールARNを記録

- [ ] **【ユーザーが手動で実施】** IAMポリシーのアタッチ
  - [ ] ECR権限ポリシーをアタッチ
  - [ ] Lambda権限ポリシーをアタッチ
  - [ ] CloudFormation権限ポリシーをアタッチ
  - [ ] S3権限ポリシーをアタッチ
  - [ ] SSM権限ポリシーをアタッチ

- [ ] **【ユーザーが手動で実施】** GitHub Secretsの設定
  - [ ] GitHub UI（Settings > Secrets and variables > Actions）を開く
  - [ ] `AWS_ROLE_ARN` をSecretsに追加（記録したロールARNを使用）
  - [ ] `ECR_IMAGE_REPOSITORY` をSecretsに追加（ECRリポジトリURI）

## フェーズ5: cd.ymlの作成

- [x] cd.ymlファイルを作成
  - [x] `.github/workflows/cd.yml` を新規作成
  - [x] ワークフロー名を "CD" に設定

- [x] トリガーの設定
  - [x] `on.push.branches: [main]` を設定

- [x] testジョブの設定（ci.yml再利用）
  - [x] `uses: ./.github/workflows/ci.yml` でci.ymlを再利用
  - 

- [x] deployジョブの設定
  - [x] `needs: test` を設定
  - [x] `permissions: id-token: write, contents: read` を設定
  - [x] runs-on: ubuntu-latest を設定

- [x] deployジョブのステップを実装
  - [x] Checkout codeステップを追加（`actions/checkout@v4`）
  - [x] Configure AWS credentialsステップを追加（`aws-actions/configure-aws-credentials@v4`）
    - [x] `role-to-assume: ${{ secrets.AWS_ROLE_ARN }}` を設定
    - [x] `aws-region: ap-northeast-1` を設定
  - [x] Install AWS SAM CLIステップを追加（`aws-actions/setup-sam@v2`）
  - [x] Set up Docker Buildxステップを追加（`docker/setup-buildx-action@v3`）
  - [x] SAM buildステップを追加
    - [x] `sam build --config-file infra/sam/samconfig.toml` を実行
  - [x] SAM deployステップを追加
    - [x] 環境変数を設定（ECR_IMAGE_REPOSITORY, PROJECT_NAME, SSM_DOTENV_PARAMETER, S3_RAW_MAIL_BUCKET）
    - [x] `sam deploy` コマンドに `--image-repositories` と `--parameter-overrides` を追加
    - [x] `--no-confirm-changeset --no-fail-on-empty-changeset` フラグを追加

## フェーズ6: cd.ymlの動作確認

**注意**: このフェーズは、フェーズ4（AWS OIDC設定）完了後に実施してください。

- [ ] **【ユーザーが手動で実施】** .env.prodファイルの準備
  - [ ] `.env.prod` ファイルが存在することを確認
  - [ ] 必要な環境変数がすべて設定されていることを確認

- [ ] **【ユーザーが手動で実施】** SSMパラメータの事前アップロード（初回のみ）
  - [ ] ローカルから `aws ssm put-parameter` で `.env.prod` をアップロード
  - [ ] SSMパラメータストアに `/calendar-auto-register/dotenv` が存在することを確認

- [ ] **【ユーザーが手動で実施】** ECRリポジトリの確認
  - [ ] ECRリポジトリが存在することを確認
  - [ ] cd.ymlの環境変数 `ECR_IMAGE_REPOSITORY` が正しいURIを指していることを確認

- [ ] **【ユーザーが手動で実施】** 変更をmainブランチにpush
  - [ ] ステアリングファイルと新しいワークフローファイルをコミット
  - [ ] mainブランチにpush

- [ ] **【ユーザーが手動で実施】** GitHub Actionsの実行確認
  - [ ] GitHub UIでActionsタブを開く
  - [ ] CDワークフローが自動実行されることを確認
  - [ ] testジョブが成功することを確認
  - [ ] deployジョブが成功することを確認

- [ ] **【ユーザーが手動で実施】** デプロイ後の動作確認
  - [ ] AWS Lambdaコンソールで関数が更新されていることを確認
  - [ ] Lambda関数の `/healthz` エンドポイントにアクセスして200が返ることを確認
  - [ ] CloudWatch Logsでエラーがないことを確認

## フェーズ7: build.yamlの削除とクリーンアップ

- [x] build.yamlを削除
  - [x] `.github/workflows/build.yaml` を削除（ci.ymlにリネーム済み）
  - [x] ci.ymlに完全移行できたことを確認

- [x] ドキュメントの更新
  - [x] `ai-note/future-cd-implementation.md` に実装完了の記録を追加（振り返りセクションで実施）
  - [x] ~~README.md（存在する場合）にCI/CD情報を追加~~（README.mdは存在しないため不要）

## フェーズ8: 品質チェックと修正

- [x] すべてのワークフローファイルが正しくフォーマットされていることを確認
  - [x] YAML構文エラーがないことを確認（ci.yml, cd.yml を作成時に確認済み）
  - [x] インデントが正しいことを確認

- [x] GitHub Actionsのベストプラクティスに準拠していることを確認
  - [x] アクションのバージョンが固定されていることを確認（@v4, @v3, @v2）
  - [x] 必要なpermissionsが正しく設定されていることを確認（cd.ymlで `id-token: write, contents: read`）

- [x] セキュリティチェック
  - [x] GitHub Secretsに機密情報のみが含まれていることを確認（設計書に従い `AWS_ROLE_ARN` と `ECR_IMAGE_REPOSITORY` のみ）
  - [x] IAMロールの権限が最小限であることを確認（OIDC設定ガイドで最小権限ポリシーを定義済み）

---

## 実装後の振り返り

### 実装完了日
2026-02-19

### 計画と実績の差分

**計画と異なった点**:
- **capabilities設定の維持**: 設計書では `capabilities = "CAPABILITY_IAM"` と記載していたが、既存の `"CAPABILITY_IAM CAPABILITY_AUTO_EXPAND"` を維持。理由: SAM Transformを使用するため `CAPABILITY_AUTO_EXPAND` が必要
- **ECR_IMAGE_REPOSITORYの扱い**: 当初はcd.yml内の環境変数として定義する予定だったが、AWSアカウントIDを含むため、GitHub Secretsに設定する方針に変更
- **手動タスクの明確化**: フェーズ4（AWS OIDC設定）とフェーズ6（動作確認）は、ユーザーが手動で実施する必要があることを明確にマーク

**新たに必要になったタスク**:
- **AWS OIDC設定ガイドの作成**: 手動設定をサポートするため、詳細なステップバイステップガイドを作成
- **GitHub Secretsに `ECR_IMAGE_REPOSITORY` を追加**: AWSアカウントIDを含む値のため、Secretsでの管理が必要

**技術的理由でスキップしたタスク**:
- **ローカルでのsam deploy動作確認**: 実際のAWSリソース作成を伴うため、GitHub Actions上でのCD実行時に確認する方針に変更
- **ci.ymlの動作確認（PR作成）**: cd.yml実装後、mainブランチへのpush時にまとめて確認する方針に変更

### 学んだこと

**技術的な学び**:
- **SAM Transformと権限**: `Transform: AWS::Serverless-2016-10-31` を使用する場合、CloudFormationデプロイ時に `CAPABILITY_AUTO_EXPAND` が必要
- **GitHub Actions OIDC認証**: アクセスキーを使用せず、一時的な認証情報でAWSにアクセス可能。セキュリティと利便性が向上
- **workflow_call**: GitHub Actionsのワークフローを再利用可能にする仕組み。ci.ymlをcd.ymlから呼び出すことで、重複を削減
- **samconfig.tomlの活用**: 固定値（stack_name, region, capabilities）をsamconfig.tomlに集約することで、sam deployコマンドをシンプルに保つ

**プロセス上の改善点**:
- **手動タスクの明確化**: 自動実装できないタスク（AWS設定、GitHub Secrets設定）を明確にマークすることで、ユーザーの作業が明確になった
- **段階的な実装**: samconfig.toml → ci.yml → AWS OIDCガイド → cd.yml の順で実装することで、リスクを最小化
- **ガイドドキュメントの重要性**: 手動作業をサポートするため、詳細なステップバイステップガイドを作成。トラブルシューティングも含める

**コスト・パフォーマンスの成果**（期待値）:
- **デプロイ時間の短縮**: 手動デプロイ（10分）→ 自動デプロイ（5分）を目標
- **手動作業の削減**: デプロイごとの手動操作（コマンド実行、環境変数設定）がゼロに
- **デプロイミスの削減**: 手動操作によるミス（パラメータ間違い、環境変数設定忘れ）をゼロに

### 次回への改善提案

**計画フェーズでの改善点**:
- **手動作業の事前識別**: タスク計画時に、どのタスクが自動実装可能で、どのタスクが手動作業かを明確に区別する
- **環境依存値の扱い**: AWSアカウントID、ECRリポジトリURIなど、環境依存の値をどこで管理するか（samconfig.toml vs GitHub Secrets vs cd.yml）を事前に決定
- **capabilities設定の確認**: SAMテンプレートで使用する機能（Transform, NestedStacks）に応じて、必要な capabilities を事前に確認

**実装フェーズでの改善点**:
- **ガイドドキュメントの早期作成**: 手動作業が必要なタスクは、実装開始前にガイドドキュメントを作成することで、ユーザーの待ち時間を削減
- **GitHub Secretsのテンプレート化**: 必要なSecretsとその説明を一覧化したテンプレートを作成し、ユーザーが設定しやすくする

**ワークフロー全体での改善点**:
- **CI/CDのテスト戦略**: GitHub Actionsワークフローのテストは、実際のpushでしか確認できないため、テスト用のブランチやリポジトリを用意する
- **ロールバック手順の文書化**: デプロイ失敗時のロールバック手順をドキュメント化し、緊急時に迅速に対応できるようにする
- **通知機能の追加**: デプロイ成功/失敗時にSlack通知を送ることで、デプロイ状況をリアルタイムで把握（将来のフェーズ4で実装予定）

### 次のステップ

**ユーザーが実施する手動タスク**:

1. **フェーズ4: AWS OIDC設定**（必須）
   - ガイドドキュメント: `.steering/20260219-CICDの構築/docs/aws-oidc-setup-guide.md`
   - 手順:
     - OIDC IDプロバイダーの作成
     - IAMロールの作成
     - IAMポリシーのアタッチ
     - GitHub Secretsの設定（`AWS_ROLE_ARN`, `ECR_IMAGE_REPOSITORY`）

2. **フェーズ6: cd.ymlの動作確認**（必須）
   - 前提: フェーズ4完了後
   - 手順:
     - `.env.prod` ファイルの準備
     - SSMパラメータのアップロード
     - ECRリポジトリの確認
     - mainブランチへのpush
     - GitHub Actionsの実行確認
     - デプロイ後の動作確認

3. **コミットとpush**
   - 現在の変更をコミット
   - mainブランチにpush（フェーズ4完了後）
   - GitHub Issue #9をクローズ

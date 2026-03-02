# 要求内容

## GitHub Issue
https://github.com/k-negishi/calendar-auto-register/issues/9

## issue 内容
- **タイトル**: CICDの構築
- **本文**:
  - https://github.com/k-negishi/ai-curated-newsletter/tree/main/.github/workflows と同様に実施
  - aws oidc認証のIAM設定をCLIで実施
- **ラベル**: なし

## 実装方針
- Kent Beck の TDD (Test-Driven Development) で実装する
- RED → GREEN → REFACTOR のサイクルを遵守
- テストを先に書き、最小限の実装でパスさせ、その後リファクタリング

---

## 概要

GitHub ActionsによるCI/CDパイプラインを構築し、mainブランチへのpush時にAWS Lambdaへの自動デプロイを実現する。

## 背景

現在、以下の課題があります：
- **CIのみ実装済み**: test, lint, typecheck の3ジョブがDocker Composeベースで実行されている（`.github/workflows/build.yaml`）
- **CDが未実装**: AWSへのデプロイは手動で `scripts/sam-deploy.sh` を実行する必要がある
- **デプロイ頻度の増加**: 機能追加が進むにつれ、デプロイ頻度が増加し、手動デプロイが負担になっている

参考リポジトリ（ai-curated-newsletter）では、ci.ymlとcd.ymlを分離し、AWS OIDC認証を使用した自動デプロイが実現されています。同様のパターンを導入し、デプロイプロセスを自動化します。

## 実装対象の機能

### 1. CI/CDワークフローの分離
- 現在の `build.yaml` を `ci.yml` にリネーム
- `cd.yml` を新規作成し、mainブランチへのpush時に自動デプロイを実行
- `ci.yml` は `cd.yml` から再利用可能にする（workflow_call）

### 2. AWS OIDC認証の設定
- GitHub ActionsからAWSへのアクセスにOIDC（OpenID Connect）認証を使用
- IAMロールとIDプロバイダーをAWS CLIで手動設定
- GitHub Secretsには `AWS_ROLE_ARN` のみを設定（最小限のシークレット管理）

### 3. samconfig.tomlの設定
- `stack_name`, `region`, `capabilities` などの固定値をsamconfig.tomlに記載
- sam deployコマンドをシンプルに保つ

### 4. デプロイパラメータの環境変数化
- ECRリポジトリURI、プロジェクト名、SSMパラメータ名などをcd.yml内で環境変数として管理
- GitHub Secretsを最小限に抑える

## 受け入れ条件

### CI/CDワークフローの分離
- [ ] `ci.yml` が存在し、PR時にtest, lint, typecheckが実行される
- [ ] `cd.yml` が存在し、mainブランチへのpush時にci.ymlを再利用してテストを実行する
- [ ] `cd.yml` でテスト成功後、AWS Lambdaへのデプロイが自動実行される

### AWS OIDC認証の設定
- [ ] AWS IAMにOIDC IDプロバイダーが設定されている
- [ ] GitHub Actions用のIAMロールが作成され、必要な権限が付与されている
- [ ] GitHub Secretsに `AWS_ROLE_ARN` が設定されている
- [ ] cd.ymlでOIDC認証を使用してAWSにアクセスできる

### samconfig.tomlの設定
- [ ] samconfig.tomlに `stack_name`, `region`, `capabilities`, `resolve_s3` が設定されている
- [ ] sam deployコマンドが追加の引数なしで実行できる（`--image-repositories`と`--parameter-overrides`は除く）

### デプロイパラメータの環境変数化
- [ ] cd.yml内でECRリポジトリURI、プロジェクト名などが環境変数として定義されている
- [ ] sam deployコマンドで環境変数を使用してパラメータを渡している

### 動作確認
- [ ] mainブランチへのpush後、GitHub ActionsでCI/CDが自動実行される
- [ ] CIジョブ（test, lint, typecheck）がすべて成功する
- [ ] デプロイジョブがCIジョブ成功後に実行される
- [ ] AWS Lambdaに新しいバージョンがデプロイされる
- [ ] デプロイ後、Lambda関数が正常に動作する

## 成功指標

- **デプロイ時間の短縮**: 手動デプロイ（10分）→ 自動デプロイ（5分）
- **デプロイミスの削減**: 手動操作によるミスをゼロにする
- **デプロイ頻度の向上**: 1週間に1回 → 1日に数回可能にする

## スコープ外

以下はこのフェーズでは実装しません:

- **手動承認フロー**: GitHub Environmentsを使った承認フローは将来的に追加
- **ステージング環境**: 本番環境のみ対象（ステージング環境は将来的に追加）
- **ロールバック機能**: CloudFormationスタックのロールバックは将来的に検討
- **通知機能**: Slack通知などは将来的に追加

## 参照ドキュメント

- `ai-note/future-cd-implementation.md` - CI/CD実装の将来構想
- `ai-note/specs/aws-deploy.md` - AWSデプロイのTODO
- [参考リポジトリ: ai-curated-newsletter](https://github.com/k-negishi/ai-curated-newsletter/tree/main/.github/workflows)
- [GitHub Actions: AWS Credentials](https://github.com/aws-actions/configure-aws-credentials)
- [GitHub OIDC with AWS](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)

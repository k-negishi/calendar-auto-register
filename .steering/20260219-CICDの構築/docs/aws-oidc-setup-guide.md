# AWS OIDC設定ガイド

このガイドでは、GitHub ActionsからAWSへのセキュアなアクセスを実現するため、OIDC（OpenID Connect）認証を設定する手順を説明します。

## 概要

OIDC認証を使用することで、以下のメリットがあります：

- **セキュリティ向上**: アクセスキー/シークレットキーを使用せず、一時的な認証情報を使用
- **最小権限の原則**: 特定のリポジトリとブランチからのみアクセスを許可
- **GitHub Secretsの最小化**: `AWS_ROLE_ARN` のみをSecretsに保存

## 前提条件

- AWS CLIがインストールされ、適切な権限を持つIAMユーザーでログイン済み
- `aws sts get-caller-identity` でアカウントIDが確認できること
- GitHubリポジトリの管理者権限

## ステップ1: OIDC IDプロバイダーの作成

### 1-1. サムプリントの取得

OIDC IDプロバイダーには、GitHubのOIDCエンドポイントのサムプリントが必要です。

```bash
# GitHubのOIDCプロバイダーURL
OIDC_URL="https://token.actions.githubusercontent.com"

# サムプリント（固定値）
THUMBPRINT="6938fd4d98bab03faadb97b34396831e3780aea1"
```

**注意**: GitHubのOIDCプロバイダーのサムプリントは固定値です。上記の値を使用してください。

### 1-2. OIDC IDプロバイダーの作成

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

**出力例**:
```json
{
    "OpenIDConnectProviderArn": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
}
```

**プロバイダーARNを記録**してください。

### 1-3. 既存のプロバイダーを確認（オプション）

既にプロバイダーが存在するか確認する場合：

```bash
aws iam list-open-id-connect-providers
```

## ステップ2: IAMロールの作成

### 2-1. 信頼関係ポリシーJSONの作成

以下の内容で `trust-policy.json` ファイルを作成します：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::YOUR_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:YOUR_GITHUB_USERNAME/calendar-auto-register:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

**置き換える値**:
- `YOUR_ACCOUNT_ID`: AWSアカウントID（`aws sts get-caller-identity` で確認）
- `YOUR_GITHUB_USERNAME`: GitHubのユーザー名またはOrganization名

**Conditionの説明**:
- `token.actions.githubusercontent.com:aud`: 固定値 `sts.amazonaws.com`
- `token.actions.githubusercontent.com:sub`: `repo:ユーザー名/リポジトリ名:ref:refs/heads/ブランチ名`
  - この例では、mainブランチからのみアクセスを許可

### 2-2. IAMロールの作成

```bash
aws iam create-role \
  --role-name GitHubActionsDeployRole \
  --assume-role-policy-document file://trust-policy.json \
  --description "Role for GitHub Actions to deploy calendar-auto-register"
```

**出力例**:
```json
{
    "Role": {
        "RoleName": "GitHubActionsDeployRole",
        "Arn": "arn:aws:iam::123456789012:role/GitHubActionsDeployRole",
        ...
    }
}
```

**ロールARNを記録**してください。このARNは後でGitHub Secretsに設定します。

## ステップ3: IAMポリシーのアタッチ

### 3-1. 必要な権限の概要

GitHub Actionsからのデプロイには、以下のAWSサービスへのアクセス権限が必要です：

- **ECR**: Dockerイメージのpush
- **Lambda**: 関数の作成・更新
- **CloudFormation**: スタックの作成・更新
- **S3**: デプロイメント用バケットへのアクセス、RAWメールバケットへの読み取り
- **SSM**: Parameter Storeへのアクセス
- **IAM**: ロールの作成（CloudFormation経由）

### 3-2. カスタムポリシーの作成

以下の内容で `deploy-policy.json` ファイルを作成します：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "lambda:CreateFunction",
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration",
        "lambda:GetFunction",
        "lambda:DeleteFunction",
        "lambda:AddPermission",
        "lambda:RemovePermission",
        "lambda:InvokeFunction"
      ],
      "Resource": "arn:aws:lambda:ap-northeast-1:*:function:calendar-auto-register*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:CreateStack",
        "cloudformation:UpdateStack",
        "cloudformation:DeleteStack",
        "cloudformation:DescribeStacks",
        "cloudformation:DescribeStackEvents",
        "cloudformation:DescribeStackResources",
        "cloudformation:GetTemplate",
        "cloudformation:ValidateTemplate"
      ],
      "Resource": "arn:aws:cloudformation:ap-northeast-1:*:stack/calendar-auto-register*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::aws-sam-cli-managed-default-samclisourcebucket-*",
        "arn:aws:s3:::aws-sam-cli-managed-default-samclisourcebucket-*/*",
        "arn:aws:s3:::calendar-auto-register*",
        "arn:aws:s3:::calendar-auto-register*/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:PutParameter"
      ],
      "Resource": "arn:aws:ssm:ap-northeast-1:*:parameter/calendar-auto-register/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:GetRole",
        "iam:PassRole",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:GetRolePolicy"
      ],
      "Resource": "arn:aws:iam::*:role/calendar-auto-register*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "apigateway:GET",
        "apigateway:POST",
        "apigateway:PUT",
        "apigateway:DELETE",
        "apigateway:PATCH"
      ],
      "Resource": "arn:aws:apigateway:ap-northeast-1::/restapis*"
    }
  ]
}
```

**ポリシーの作成**:

```bash
aws iam create-policy \
  --policy-name GitHubActionsDeployPolicy \
  --policy-document file://deploy-policy.json \
  --description "Policy for GitHub Actions to deploy calendar-auto-register"
```

**出力例**:
```json
{
    "Policy": {
        "PolicyName": "GitHubActionsDeployPolicy",
        "Arn": "arn:aws:iam::123456789012:policy/GitHubActionsDeployPolicy",
        ...
    }
}
```

**ポリシーARNを記録**してください。

### 3-3. ポリシーをロールにアタッチ

```bash
aws iam attach-role-policy \
  --role-name GitHubActionsDeployRole \
  --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/GitHubActionsDeployPolicy
```

`YOUR_ACCOUNT_ID` を自分のAWSアカウントIDに置き換えてください。

## ステップ4: GitHub Secretsの設定

### 4-1. GitHub UIでの設定

1. GitHubリポジトリのページを開く
2. **Settings** タブをクリック
3. 左サイドバーの **Secrets and variables** > **Actions** をクリック
4. **New repository secret** ボタンをクリック
5. 以下の情報を入力:
   - **Name**: `AWS_ROLE_ARN`
   - **Secret**: ステップ2-2で記録したロールARN（例: `arn:aws:iam::123456789012:role/GitHubActionsDeployRole`）
6. **Add secret** ボタンをクリック

### 4-2. 設定の確認

Secretsページに `AWS_ROLE_ARN` が追加されていることを確認してください。

## ステップ5: 検証

### 5-1. IAMロールの確認

```bash
aws iam get-role --role-name GitHubActionsDeployRole
```

信頼関係が正しく設定されていることを確認してください。

### 5-2. ポリシーのアタッチ確認

```bash
aws iam list-attached-role-policies --role-name GitHubActionsDeployRole
```

`GitHubActionsDeployPolicy` がアタッチされていることを確認してください。

### 5-3. GitHub Actionsでの動作確認

cd.ymlを実装後、mainブランチにpushして、以下を確認してください：

1. GitHub Actionsが正常に起動する
2. `Configure AWS credentials` ステップが成功する
3. デプロイが正常に完了する

## トラブルシューティング

### エラー: "No OpenIDConnect provider found"

**原因**: OIDC IDプロバイダーが作成されていない、またはARNが間違っている

**対処法**:
```bash
aws iam list-open-id-connect-providers
```
でプロバイダーの存在を確認し、`trust-policy.json` のARNを修正してください。

### エラー: "Not authorized to perform sts:AssumeRoleWithWebIdentity"

**原因**: 信頼関係ポリシーの条件が一致していない

**対処法**:
- `trust-policy.json` の `token.actions.githubusercontent.com:sub` を確認
- リポジトリ名、ブランチ名が正しいか確認
- GitHub Actionsのログで `sub` クレームの値を確認

### エラー: "Access Denied" (デプロイ中)

**原因**: IAMポリシーに必要な権限が不足している

**対処法**:
- CloudWatch Logsでエラー詳細を確認
- 不足している権限を `deploy-policy.json` に追加
- ポリシーを更新:
  ```bash
  aws iam create-policy-version \
    --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/GitHubActionsDeployPolicy \
    --policy-document file://deploy-policy.json \
    --set-as-default
  ```

## セキュリティのベストプラクティス

1. **最小権限の原則**: 必要な権限のみを付与
2. **リソースの制限**: ポリシーで `Resource` を具体的に指定
3. **条件の活用**: 信頼関係ポリシーでリポジトリとブランチを制限
4. **定期的なレビュー**: 権限が適切か定期的に確認

## 参考リンク

- [GitHub Actions: Configuring OpenID Connect in AWS](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- [AWS: Creating OpenID Connect (OIDC) identity providers](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html)
- [AWS SAM CLI: Deploying](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-deploying.html)

## まとめ

このガイドに従って設定を完了すると、GitHub ActionsからAWSへのセキュアなアクセスが実現されます。OIDC認証により、アクセスキーを使用せず、一時的な認証情報でデプロイが可能になります。

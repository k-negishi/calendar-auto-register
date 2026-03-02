# 設計書

## アーキテクチャ概要

GitHub ActionsによるCI/CDパイプラインを構築し、参考リポジトリ（ai-curated-newsletter）のパターンを踏襲しつつ、現在のDocker Composeベースのビルド環境を維持します。

```
┌─────────────────────────────────────────────────────────────┐
│ GitHub Repository (calendar-auto-register)                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  PR → main                         main へ push             │
│      │                                   │                  │
│      ▼                                   ▼                  │
│  ┌──────────┐                      ┌──────────┐            │
│  │ ci.yml   │◄─────────────────────│ cd.yml   │            │
│  │          │   workflow_call      │          │            │
│  └──────────┘                      └──────────┘            │
│      │                                   │                  │
│      ▼                                   ▼                  │
│  Docker Compose                     Docker Compose          │
│  - test                             - test (ci.yml再利用)   │
│  - lint                                  │                  │
│  - typecheck                             ▼                  │
│                                     AWS OIDC認証            │
│                                          │                  │
│                                          ▼                  │
│                                     sam build               │
│                                          │                  │
│                                          ▼                  │
│                                     sam deploy              │
│                                          │                  │
└──────────────────────────────────────────┼──────────────────┘
                                           │
                                           ▼
                              ┌────────────────────────┐
                              │ AWS                    │
                              ├────────────────────────┤
                              │ - ECR (Docker Image)   │
                              │ - Lambda (Function)    │
                              │ - API Gateway          │
                              │ - CloudFormation       │
                              └────────────────────────┘
```

## コンポーネント設計

### 1. ci.yml（継続的インテグレーション）

**責務**:
- コード品質チェック（test, lint, typecheck）
- PR時およびcd.ymlから呼び出された時に実行
- 既存のDocker Composeベースのビルド環境を維持

**実装の要点**:
- トリガー: `pull_request` (branches: main) と `workflow_call`
- ジョブ: test, lint, typecheck（既存のbuild.yamlから移行）
- Docker Composeを使用してテストを実行
- キャッシュ戦略: Docker layersのキャッシュを活用

**ファイルパス**: `.github/workflows/ci.yml`

---

### 2. cd.yml（継続的デプロイメント）

**責務**:
- mainブランチへのpush時に自動デプロイ
- CIジョブの再利用とデプロイジョブの実行
- AWS OIDC認証を使用した安全なデプロイ

**実装の要点**:
- トリガー: `push` (branches: main)
- ジョブ:
  - `test`: ci.ymlを再利用（`uses: ./.github/workflows/ci.yml`）
  - `deploy`: testジョブ成功後に実行
- permissions: `id-token: write`, `contents: read`（OIDC認証用）
- AWS認証後、sam build & deployを実行

**ファイルパス**: `.github/workflows/cd.yml`

---

### 3. samconfig.toml（SAM設定）

**責務**:
- SAM CLIの設定を集約
- stack_name, region, capabilitiesなどの固定値を管理

**実装の要点**:
- `[default.deploy.parameters]` セクションに以下を追加:
  - `stack_name = "calendar-auto-register"`
  - `region = "ap-northeast-1"`
  - `capabilities = "CAPABILITY_IAM"`
  - `resolve_s3 = true`

**ファイルパス**: `infra/sam/samconfig.toml`

---

### 4. AWS OIDC設定（手動設定）

**責務**:
- GitHub ActionsからAWSへの安全なアクセスを提供
- IAMロールとOIDC IDプロバイダーの設定

**実装の要点**:
- OIDC IDプロバイダーの作成（`token.actions.githubusercontent.com`）
- IAMロールの作成（`GitHubActionsDeployRole`）
- 信頼関係の設定（特定のリポジトリとブランチからのみアクセス許可）
- 必要な権限の付与（ECR, Lambda, CloudFormation, S3, SSM）

**設定方法**: AWS CLIを使用した手動設定（ガイドドキュメントを作成）

---

## データフロー

### PR時のフロー
```
1. 開発者がPRを作成
2. ci.ymlがトリガーされる
3. Docker Composeでtest, lint, typecheckを実行
4. すべて成功したらPRをマージ可能
```

### デプロイフロー（mainブランチへのpush時）
```
1. mainブランチにpush（PRマージ）
2. cd.ymlがトリガーされる
3. testジョブ: ci.ymlを再利用してtest, lint, typecheckを実行
4. deployジョブ:
   a. AWS OIDC認証（configure-aws-credentials）
   b. SAM CLIセットアップ
   c. sam build（Docker containerを使用）
   d. sam deploy（CloudFormationスタックを更新）
      - ECRにDockerイメージをpush
      - Lambda関数を更新
      - API Gatewayを更新
5. デプロイ完了
```

## エラーハンドリング戦略

### CI失敗時
- PRマージをブロック
- GitHub UIでエラー内容を表示
- 開発者が修正してpush

### デプロイ失敗時
- CloudFormationのロールバック機能により、前のバージョンに自動ロールバック
- GitHub ActionsのジョブステータスをFailedに設定
- CloudWatch Logsでエラー詳細を確認可能

## テスト戦略

### ローカルテスト
- 既存のDocker Composeベースのテスト環境を維持
- `docker compose run --rm local uv run pytest`
- `docker compose run --rm local uv run ruff check`
- `docker compose run --rm local uv run mypy app/src`

### CI/CDテスト
- ci.ymlで同じテストコマンドを実行
- PRごとに品質チェック
- mainブランチへのマージ前に品質保証

### デプロイテスト
- デプロイ後、Lambda関数の `/healthz` エンドポイントを確認
- CloudWatch Logsでエラーがないことを確認

## TDDサイクル

この実装ではTDDを適用しますが、インフラコード（GitHub ActionsワークフローとAWS設定）のため、以下のように解釈します：

1. **RED**: ワークフローファイルを作成し、まずテストジョブを定義（期待する動作を記述）
2. **GREEN**: ワークフローを実行し、テストが通ることを確認
3. **REFACTOR**: ワークフローの構造を改善、重複を削除

具体的なTDDサイクル：
- **ci.yml**: テストジョブを定義 → PRで実行 → 成功を確認 → リファクタリング
- **cd.yml**: デプロイジョブを定義 → mainにpush → デプロイ成功を確認 → リファクタリング

## 依存ライブラリ

新しいライブラリの追加はありません。GitHub Actionsのアクションのみ使用します：

- `actions/checkout@v4`
- `docker/setup-buildx-action@v3`
- `actions/cache@v4`
- `aws-actions/configure-aws-credentials@v4`
- `aws-actions/setup-sam@v2`

## ディレクトリ構造

```
.github/
└── workflows/
    ├── ci.yml (新規作成: build.yamlをリネーム+修正)
    └── cd.yml (新規作成)

infra/
└── sam/
    ├── samconfig.toml (修正: deploy parametersを追加)
    └── template.yaml (変更なし)

scripts/
└── sam-deploy.sh (変更なし: ローカルデプロイ用として維持)

.steering/
└── 20260219-CICDの構築/
    ├── requirements.md
    ├── design.md
    ├── tasklist.md
    └── docs/
        └── aws-oidc-setup-guide.md (新規作成: OIDC設定ガイド)
```

## 実装の順序

1. **samconfig.tomlの更新**（リスクが低い）
2. **ci.ymlの作成**（build.yamlをベースにリネーム+修正）
3. **ci.ymlのテスト**（PRを作成して動作確認）
4. **AWS OIDC設定ガイドの作成**（手動設定のドキュメント化）
5. **AWS OIDC設定の実施**（手動でAWS CLIを実行）
6. **cd.ymlの作成**（デプロイジョブを追加）
7. **cd.ymlのテスト**（mainにpushして動作確認）
8. **build.yamlの削除**（ci.ymlに完全移行後）

## セキュリティ考慮事項

- **OIDC認証の使用**: アクセスキー/シークレットキーを使用せず、一時的な認証情報を使用
- **最小権限の原則**: IAMロールには必要最小限の権限のみを付与
- **リポジトリとブランチの制限**: 信頼関係で特定のリポジトリとmainブランチからのみアクセスを許可
- **GitHub Secretsの最小化**: `AWS_ROLE_ARN` のみをSecretsに保存
- **環境変数の管理**: 機密情報はすべてAWS SSM Parameter Storeで管理

## パフォーマンス考慮事項

- **Docker layerのキャッシュ**: GitHub Actionsのcacheアクションを使用してビルド時間を短縮
- **並列実行**: test, lint, typecheckは並列実行可能（現在は直列だが、将来的に改善可能）
- **sam buildのキャッシュ**: SAM CLIのビルドキャッシュを活用

## 将来の拡張性

### フェーズ2: 手動承認フロー（本番運用向け）
- GitHub Environmentsを設定（`production`）
- Required reviewersを設定
- cd.ymlの`deploy`ジョブに`environment: production`を追加

### フェーズ3: ステージング環境
- `cd-staging.yml`を作成
- developブランチへのpush時にステージング環境へデプロイ
- 本番デプロイ前の検証環境

### フェーズ4: 通知機能
- Slack通知（デプロイ成功/失敗）
- GitHub Issue自動作成（デプロイ失敗時）

### フェーズ5: パフォーマンス改善
- test, lint, typecheckの並列実行
- ビルドキャッシュの最適化

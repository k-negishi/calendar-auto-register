# LINE Webhook実装 - タスクリスト（TDD運用版）

## 重要原則

- このファイルの全タスクが完了するまで作業を継続する
- すべての実装タスクを `RED → GREEN → REFACTOR` で進める
- タスク開始時に `[ ]` から `[x]` へ更新する
- スキップ時は理由を明記する（技術制約・優先度変更・スコープ変更）
- 失敗系テスト（署名不一致、外部API失敗、タイムアウト）を正常系より先に書く

## TDD運用ルール

- `RED`: 失敗するテストを先に追加し、失敗理由を確認する
- `GREEN`: テストを通す最小実装のみ行う
- `REFACTOR`: 重複削除、責務分離、命名改善を行いテストを再実行する
- 1サイクルごとに `pytest` を実行し、フェーズ完了時に `ruff` と `mypy` を実行する

---

## Phase 0: 基盤準備（TDD前提の土台）

### 0.1 環境変数・設定

- [ ] `LINE_CHANNEL_SECRET` を環境変数に追加
- [ ] `BEDROCK_VISION_MODEL_ID` を環境変数に追加
- [ ] `config/settings.py` に新規環境変数を追加
- [ ] `.env.example` を更新

### 0.2 ディレクトリ構造

- [ ] `features/line_webhook/` を作成
- [ ] `features/line_webhook/__init__.py` を作成
- [ ] `clients/` 配下に新規クライアントファイルを配置可能な状態にする

---

## Phase 1: スキーマ実装（Story 1）

- [ ] Story 1: LINE Webhookスキーマを定義する
  - [ ] RED: `tests/features/line_webhook/test_schemas_line_webhook_post.py` を作成し、以下の失敗テストを追加
  - [ ] RED: `LineSource` の必須項目不足・不正値テストを追加
  - [ ] RED: `LineMessage` の `text` / `image` バリエーションテストを追加
  - [ ] RED: `LineWebhookRequest` の複数イベントパーステストを追加
  - [ ] GREEN: `features/line_webhook/schemas_line_webhook_post.py` を実装しテストを通す
  - [ ] REFACTOR: バリデーションロジックと型注釈を整理し可読性を向上

---

## Phase 2: 署名検証実装（Story 2）

- [ ] Story 2: LINE署名検証を実装する
  - [ ] RED: `tests/middleware/test_line_signature_verifier.py` を作成
  - [ ] RED: 正常署名・不正署名・シークレット不一致・空ボディの失敗テストを追加
  - [ ] GREEN: `middleware/line_signature_verifier.py` に `verify_line_signature()` を実装
  - [ ] GREEN: HMAC-SHA256 + Base64比較を実装しテストを通す
  - [ ] REFACTOR: 共通処理抽出と入力ガード（`None` / 空文字）を整理

---

## Phase 3: 外部APIクライアント（Story 3-4）

- [ ] Story 3: LINE Content APIクライアントを実装する
  - [ ] RED: `tests/clients/test_line_content_client.py` を作成
  - [ ] RED: 正常系、404、タイムアウト、認証エラーの失敗テストを追加
  - [ ] GREEN: `clients/line_content_client.py` を実装し `get_message_content()` を追加
  - [ ] GREEN: タイムアウト（30秒）とHTTPエラーハンドリングを実装
  - [ ] REFACTOR: 例外種別とログ文言を整理

- [ ] Story 4: Bedrock Visionクライアントを実装する
  - [ ] RED: `tests/clients/test_bedrock_vision_client.py` を作成
  - [ ] RED: テキスト抽出、画像抽出、JSON解析失敗、最大リトライ超過の失敗テストを追加
  - [ ] GREEN: `clients/bedrock_vision_client.py` を実装
  - [ ] GREEN: `extract_events_from_text()` / `extract_events_from_image()` / プロンプト生成を実装
  - [ ] GREEN: tenacityベースのリトライを実装
  - [ ] REFACTOR: プロンプト構築とレスポンスパース責務を分離

---

## Phase 4: ユースケース実装（Story 5）

- [ ] Story 5: Webhookユースケースを実装する
  - [ ] RED: `tests/features/line_webhook/test_usecase_line_webhook_post.py` を作成
  - [ ] RED: テキスト処理正常系、画像処理正常系、未対応メッセージスキップの失敗テストを追加
  - [ ] RED: Vision失敗・Calendar失敗時のエラー通知テストを追加
  - [ ] GREEN: `features/line_webhook/usecase_line_webhook_post.py` を実装
  - [ ] GREEN: `handle_webhook_events()` / `_handle_text_message()` / `_handle_image_message()` / `_notify_error()` を実装
  - [ ] REFACTOR: 分岐ロジックと依存注入境界を整理

---

## Phase 5: ルーター実装（Story 6）

- [ ] Story 6: `/line/webhook` APIを実装する
  - [ ] RED: ルーターテストを追加（署名OKで200、署名NGで403）
  - [ ] RED: Usecase呼び出し回数・引数の失敗テストを追加
  - [ ] GREEN: `features/line_webhook/router_line_webhook_post.py` を実装
  - [ ] GREEN: 署名検証とUsecase呼び出しを統合
  - [ ] GREEN: `main.py` にルーターを登録
  - [ ] REFACTOR: 依存解決・レスポンス定義・例外ハンドリングを整理

---

## Phase 6: Step Functions + インフラ（Story 7）

- [ ] Story 7: 非同期オーケストレーションを実装する
  - [ ] RED: Step Functions起動ペイロードのユニットテストを追加
  - [ ] RED: 起動失敗時のログ・エラー分岐テストを追加
  - [ ] GREEN: `usecase_line_webhook_post.py` に `stepfunctions.start_execution()` 起動処理を実装
  - [ ] GREEN: 実行名生成（`line-webhook-{timestamp}-{random}`）を実装
  - [ ] REFACTOR: 実行入力生成ロジックを分離

- [ ] `infra/sam/statemachine/line_webhook_workflow.asl.json` を作成
- [ ] `infra/sam/template.yaml` に以下を追加
- [ ] `LINE_CHANNEL_SECRET` / `BEDROCK_VISION_MODEL_ID` の環境変数定義
- [ ] `AWS::Serverless::StateMachine` 定義（`LineWebhookWorkflow`）
- [ ] IAM追加（`bedrock:InvokeModel` / `states:StartExecution` / `lambda:InvokeFunction`）
- [ ] API Gatewayに `POST /line/webhook` を追加

---

## Phase 7: 統合テスト（Story 8）

- [ ] Story 8: E2Eシナリオを固定化する
  - [ ] RED: `tests/integration/test_line_webhook_e2e.py` を作成し失敗状態を確認
  - [ ] RED: テキスト完全フロー、画像完全フロー、署名失敗403、複数イベント、エラー通知のテストを追加
  - [ ] GREEN: 既存実装調整でE2Eを通過
  - [ ] REFACTOR: テストデータ生成・モック構成を共通化

- [ ] Docker Composeでローカル疎通確認
- [ ] `/line/webhook` に対する `curl` 検証
- [ ] CloudWatch Logsフォーマット確認

---

## Phase 8: 品質ゲート

- [ ] `ruff check --fix` を実行
- [ ] `mypy app/src` を実行（strict mode）
- [ ] `pytest --cov=calendar_auto_register --cov-report=term` を実行
- [ ] テストカバレッジ 80%以上を確認
- [ ] テキスト処理時間（目標10秒以内）を測定
- [ ] 画像処理時間（目標20秒以内）を測定

---

## Phase 9: ドキュメント・デプロイ準備

- [ ] `README.md` を更新（機能、アーキテクチャ、環境変数、ローカル検証、トラブルシュート）
- [ ] FastAPI `/docs` で `POST /line/webhook` の仕様を確認
- [ ] AWS SSM Parameter Storeへ新規環境変数を登録
- [ ] `scripts/sam-deploy.sh` 実行前チェックリストを完了
- [ ] LINE Developers ConsoleのWebhook設定を更新

---

## Phase 10: 本番検証・運用設定

- [ ] 実機LINEでテキスト送信テストを実施
- [ ] 実機LINEで画像送信テストを実施
- [ ] 不正署名・抽出失敗・タイムアウトのエラーケースを検証
- [ ] CloudWatch Alarm（Lambdaエラー率、署名検証失敗）を設定

---

## 実装完了後の振り返り

### 完了日
<!-- 実装完了日を記入 -->

### 計画との差分
<!-- 計画時の想定と異なった部分を記載 -->

### 新規追加タスク
<!-- 実装中に追加で必要になったタスクを記載 -->

### スキップしたタスク
<!-- スキップしたタスクと理由を記載 -->

### 技術的学習
<!-- 実装を通じて学んだ技術的知見を記載 -->

### プロセス改善提案
<!-- 次回のステアリングファイル運用への改善提案を記載 -->

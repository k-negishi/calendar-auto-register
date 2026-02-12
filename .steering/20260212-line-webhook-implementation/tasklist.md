# LINE Webhook実装 - タスクリスト

## 重要原則

**このファイルの全タスクが完了するまで作業を継続すること**

- タスク開始時に `[ ]` → `[x]` へ更新
- タスク完了時に即座にチェックマーク更新
- スキップする場合は技術的理由を明記
- 全タスク完了後に振り返りセクションを記入

---

## Phase 1: 基盤準備

### 1.1 環境変数・設定

- [ ] `LINE_CHANNEL_SECRET` を環境変数に追加
- [ ] `BEDROCK_VISION_MODEL_ID` を環境変数に追加
- [ ] `config/settings.py` に新規環境変数を追加
- [ ] `.env.example` を更新（新規環境変数の例を追加）

### 1.2 ディレクトリ構造作成

- [ ] `features/line_webhook/` ディレクトリ作成
- [ ] `features/line_webhook/__init__.py` 作成
- [ ] `clients/` に新規クライアント用スペース確保

---

## Phase 2: データモデル定義

### 2.1 LINE Webhook スキーマ

- [ ] `features/line_webhook/schemas_line_webhook_post.py` 作成
  - [ ] `LineSource` モデル
  - [ ] `LineMessage` モデル
  - [ ] `LineMessageEvent` モデル
  - [ ] `LineWebhookRequest` モデル
  - [ ] `LineWebhookResponse` モデル

### 2.2 スキーマ単体テスト

- [ ] `tests/features/line_webhook/test_schemas_line_webhook_post.py` 作成
  - [ ] `LineSource` のバリデーションテスト
  - [ ] `LineMessage` のバリデーションテスト（text/image）
  - [ ] `LineWebhookRequest` の完全なパースフローテスト

---

## Phase 3: セキュリティ・ミドルウェア

### 3.1 署名検証実装

- [ ] `middleware/line_signature_verifier.py` 作成
  - [ ] `verify_line_signature()` 関数実装
  - [ ] HMAC-SHA256 署名検証ロジック

### 3.2 署名検証テスト

- [ ] `tests/middleware/test_line_signature_verifier.py` 作成
  - [ ] 正常署名のテスト
  - [ ] 不正署名のテスト
  - [ ] シークレット不一致のテスト
  - [ ] 空ボディのエッジケーステスト

---

## Phase 4: 外部APIクライアント実装

### 4.1 LINE Content API クライアント

- [ ] `clients/line_content_client.py` 作成
  - [ ] `LineContentClient` クラス実装
  - [ ] `get_message_content()` メソッド実装
  - [ ] HTTPエラーハンドリング
  - [ ] タイムアウト設定（30秒）

### 4.2 LINE Content API クライアントテスト

- [ ] `tests/clients/test_line_content_client.py` 作成
  - [ ] 正常系テスト（httpx モック使用）
  - [ ] 404エラーテスト（メッセージ期限切れ）
  - [ ] タイムアウトテスト
  - [ ] 認証エラーテスト

### 4.3 Bedrock Vision クライアント

- [ ] `clients/bedrock_vision_client.py` 作成
  - [ ] `BedrockVisionClient` クラス実装
  - [ ] `extract_events_from_text()` メソッド実装
  - [ ] `extract_events_from_image()` メソッド実装
  - [ ] `_build_extraction_prompt()` プライベートメソッド
  - [ ] JSON解析エラーハンドリング
  - [ ] リトライロジック（tenacity使用）

### 4.4 Bedrock Vision クライアントテスト

- [ ] `tests/clients/test_bedrock_vision_client.py` 作成
  - [ ] テキスト抽出の正常系テスト（boto3 モック）
  - [ ] 画像抽出の正常系テスト
  - [ ] JSON解析失敗時のリトライテスト
  - [ ] 最大リトライ超過時のエラーテスト
  - [ ] プロンプト生成のテスト

---

## Phase 5: ビジネスロジック（Usecase）

### 5.1 Webhook Usecase 実装

- [ ] `features/line_webhook/usecase_line_webhook_post.py` 作成
  - [ ] `LineWebhookUsecase` クラス実装
  - [ ] `handle_webhook_events()` メソッド
  - [ ] `_handle_text_message()` メソッド
  - [ ] `_handle_image_message()` メソッド
  - [ ] `_notify_error()` メソッド

### 5.2 Webhook Usecase 単体テスト

- [ ] `tests/features/line_webhook/test_usecase_line_webhook_post.py` 作成
  - [ ] テキストメッセージ処理の正常系テスト
  - [ ] 画像メッセージ処理の正常系テスト
  - [ ] Vision LLM失敗時のエラー通知テスト
  - [ ] 未対応メッセージタイプのスキップテスト
  - [ ] Calendar API失敗時のエラー処理テスト

---

## Phase 6: API Router実装

### 6.1 Webhook Router

- [ ] `features/line_webhook/router_line_webhook_post.py` 作成
  - [ ] `line_webhook_post()` エンドポイント実装
  - [ ] 署名検証ロジック統合
  - [ ] Usecase呼び出し
  - [ ] HTTPException（403）処理

### 6.2 Router統合

- [ ] `main.py` に `line_webhook` ルーターを追加
- [ ] `/line/webhook` パスの登録確認

---

## Phase 7: 統合テスト

### 7.1 E2Eテスト（FastAPI TestClient）

- [ ] `tests/integration/test_line_webhook_e2e.py` 作成
  - [ ] テキストメッセージ → カレンダー登録 → 通知の完全フロー
  - [ ] 画像メッセージ → Vision LLM → カレンダー登録 → 通知の完全フロー
  - [ ] 署名検証失敗 → 403 Forbiddenテスト
  - [ ] 複数イベント抽出のテスト
  - [ ] エラー時のLINE通知テスト

### 7.2 モック環境での動作確認

- [ ] Docker Compose環境でローカル起動
- [ ] `/line/webhook` エンドポイントへのcurlリクエスト確認
- [ ] CloudWatch Logsフォーマット確認

---

## Phase 8: インフラ設定（SAM）

### 8.1 SAM template更新

- [ ] `infra/sam/template.yaml` に新規環境変数追加
  - [ ] `LINE_CHANNEL_SECRET` の SSM Parameter参照
  - [ ] `BEDROCK_VISION_MODEL_ID` のデフォルト値設定

### 8.2 IAMポリシー追加

- [ ] Lambda実行ロールに `bedrock:InvokeModel` 権限追加
  - [ ] `anthropic.claude-3-haiku-*` リソース指定

### 8.3 API Gateway設定

- [ ] `/line/webhook` パスの追加
- [ ] 認証なし設定（署名検証はアプリケーション層）
- [ ] タイムアウト設定確認（29秒）

### 8.4 Step Functions設定（オプション）

> **注**: 現在のメール処理フローはStep Functionsを使用しているが、LINE Webhook処理は同期的に完結するため、Step Functions統合は必須ではない。将来的な非同期処理への拡張を見据える場合のみ実装。

- [ ] Step Functions State Machine定義の確認
  - [ ] 既存のメール処理ワークフローを確認
  - [ ] LINE Webhook用の新規State Machineが必要か判断
- [ ] EventBridge Rule設定（必要な場合）
  - [ ] LINE Webhook → Step Functions トリガー設定
  - [ ] イベントパターン定義
- [ ] Step Functions IAMロール設定（必要な場合）
  - [ ] Lambda呼び出し権限
  - [ ] CloudWatch Logs書き込み権限

---

## Phase 9: 品質チェック

### 9.1 Lint & Type Check

- [ ] `ruff check --fix` 実行
- [ ] `mypy app/src` 実行（strict mode）
- [ ] エラーゼロ確認

### 9.2 テストカバレッジ

- [ ] `pytest --cov=calendar_auto_register --cov-report=term` 実行
- [ ] カバレッジ80%以上確認
- [ ] 未カバー箇所の確認・必要に応じて追加テスト

### 9.3 パフォーマンステスト

- [ ] テキストメッセージ処理時間測定（目標: 10秒以内）
- [ ] 画像メッセージ処理時間測定（目標: 20秒以内）

---

## Phase 10: ドキュメント更新

### 10.1 README更新

- [ ] `README.md` の「機能」セクション更新
  - [ ] LINE Webhook対応を追加（テキスト・画像メッセージ）
  - [ ] Vision LLMアプローチの説明
  - [ ] メールベースフローとの違いを明記
- [ ] `README.md` の「アーキテクチャ図」更新
  - [ ] `docs/architecture.png` に LINE Webhook フローを追加（または別図作成）
  - [ ] テキストベースのフロー図を追加
- [ ] `README.md` の「環境変数」セクション更新
  - [ ] `LINE_CHANNEL_SECRET` の説明追加
  - [ ] `BEDROCK_VISION_MODEL_ID` の説明追加
  - [ ] 既存環境変数との関係性を明記
- [ ] `README.md` の「ローカル動作確認」セクション更新
  - [ ] `/line/webhook` エンドポイントへのcurlリクエスト例追加
  - [ ] テキストメッセージのリクエスト例
  - [ ] 画像メッセージのリクエスト例（モックデータ）
- [ ] `README.md` の「デプロイメント」セクション更新
  - [ ] LINE Developers Consoleでの設定手順追加
  - [ ] Webhook URL設定方法
  - [ ] 署名検証の注意事項
- [ ] `README.md` に「トラブルシューティング」セクション追加
  - [ ] 署名検証失敗時の対処法
  - [ ] Vision LLM抽出失敗時の対処法
  - [ ] タイムアウト時の対処法

### 10.2 APIドキュメント

- [ ] FastAPI自動生成ドキュメント（`/docs`）確認
  - [ ] `/line/webhook` のリクエスト/レスポンス例確認
  - [ ] スキーマ定義の正確性確認
- [ ] `docs/requirements.md` の更新確認
  - [ ] 実装内容との整合性チェック

### 10.3 開発者向けドキュメント

- [ ] コード内コメント・docstring確認
  - [ ] 各クラス・メソッドのdocstring追加
  - [ ] 複雑なロジックへのインラインコメント
- [ ] `CHANGELOG.md` 更新（存在する場合）
  - [ ] LINE Webhook機能追加を記録
  - [ ] Vision LLMアプローチ採用を記録

---

## Phase 11: デプロイ準備

### 11.1 環境変数設定

- [ ] AWS SSM Parameter Storeに新規環境変数追加
  - [ ] `LINE_CHANNEL_SECRET`
  - [ ] `BEDROCK_VISION_MODEL_ID`

### 11.2 デプロイ

- [ ] `scripts/sam-deploy.sh` 実行
- [ ] CloudFormation Stack更新確認
- [ ] API Gateway URL確認

### 11.3 LINE Developers Console設定

- [ ] Webhook URL設定（API Gateway URL + `/line/webhook`）
- [ ] Webhook送信を有効化
- [ ] Webhook検証実行

---

## Phase 12: 本番検証

### 12.1 手動テスト

- [ ] 実際のLINE BOTにテキストメッセージ送信
- [ ] Google Calendarにイベント登録確認
- [ ] LINE通知受信確認

### 12.2 画像テスト

- [ ] 実際のLINE BOTに画像送信（スクリーンショット）
- [ ] Vision LLMによるイベント抽出確認
- [ ] Google Calendarにイベント登録確認
- [ ] LINE通知受信確認

### 12.3 エラーケーステスト

- [ ] 不正な署名でWebhook送信（403確認）
- [ ] イベント情報がないテキスト送信（エラー通知確認）
- [ ] 読み取り不可能な画像送信（エラー通知確認）

---

## Phase 13: 監視・運用設定

### 13.1 CloudWatch Alarms

- [ ] Lambda エラー率アラーム設定（閾値: 5%）
- [ ] Webhook署名検証失敗アラーム（閾値: 10件/時間）

### 13.2 ログ確認

- [ ] CloudWatch Logsでリクエストトレーシング確認
- [ ] エラースタックトレースの出力確認

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

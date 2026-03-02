# LINE Webhook実装 - タスクリスト（TDD運用版）

## 重要原則

- このファイルの全タスクが完了するまで作業を継続する
- すべての実装タスクを `RED → GREEN → REFACTOR` で進める
- タスク開始時に `[ ]` から `[x]` へ更新する
- スキップ時は理由を明記する（技術制約・優先度変更・スコープ変更）
- 失敗系テスト（署名不一致、userId 未認可、外部 API 失敗）を正常系より先に書く

## TDD運用ルール

- `RED`: 失敗するテストを先に追加し、失敗理由を確認する
- `GREEN`: テストを通す最小実装のみ行う
- `REFACTOR`: 重複削除、責務分離、命名改善を行いテストを再実行する
- 1サイクルごとに `pytest` を実行し、フェーズ完了時に `ruff` と `mypy` を実行する

## 設計判断の参照

各タスクの `[Dx]` タグは design.md の設計判断と対応する:

- **D1**: 型変換排除（`CalendarEventModel(**e.model_dump())` 不要）
- **D2**: `send_line_notification()` 直接使用（メール処理フローのみ）
- **D3**: `extract_events_from_raw_text()` 新設（メール前処理なし）
- **D4**: 画像パスに `normalize_event_to_half_width()` 適用
- **D5**: 画像 LLM に tenacity リトライ（5回）
- **D6**: `allowlist_line_user_ids` による 2層セキュリティ
- **D7**: `_run_extraction_chain()` で LangChain チェーン共通化
- **D8**: SFN = オーケストレーター、EvB = トリガー。Python 関数直接呼び出しによるオーケストレーション禁止
- **D9**: `POST /llm/extract-event` をテキスト/メール共通化
- **D10**: `POST /line/webhook` は EvB.putEvents のみ（LLM/Calendar/通知は SFN が非同期処理）
- **D11**: 2 つの SM（Mail SM / LINE SM）を別々に定義

---

## Phase 0: 基盤準備 ✅ 完了

### 0.1 環境変数・設定（`core/settings.py`）

- [x] `core/settings.py` の `Settings` dataclass に以下を追加:
  - [x] `line_channel_secret: str | None`（Layer 1 署名検証用）[D6]
  - [x] `allowlist_line_user_ids: list[str]`（Layer 2 送信者制限用）[D6]
- [x] `load_settings()` に以下を追加:
  - [x] `line_channel_secret=os.getenv("LINE_CHANNEL_SECRET")`
  - [x] `allowlist_line_user_ids=_load_json_list(os.getenv("ALLOWLIST_LINE_USER_IDS"))`
    （`_load_json_list` は既存関数を再利用）[D6]
- [x] `.env.example` に以下を追記:
  - [x] `LINE_CHANNEL_SECRET=`
  - [x] `ALLOWLIST_LINE_USER_IDS=["U..."]`
  - [x] ~~`BEDROCK_VISION_MODEL_ID`~~ は追加しない（`BEDROCK_MODEL_ID` 兼用）[YAGNI]

### 0.2 ディレクトリ構造

- [x] `features/line_webhook/` ディレクトリを作成
- [x] `features/line_webhook/__init__.py` を作成

---

## Phase 1: 署名検証（Story 1）[Layer 1] ✅ 完了

- [x] Story 1: LINE Webhook 署名検証を実装する
  - [x] RED: `tests/calendar_auto_register/core/test_line_signature.py` を作成
  - [x] RED: 以下の失敗テストを追加（失敗系を先に書く）
    - [x] 不正署名 → `False`
    - [x] `signature` が空文字 → `False`
    - [x] `channel_secret` が不一致 → `False`
    - [x] ボディが空バイト → `False`
  - [x] RED: 正常署名 → `True` テストを追加
  - [x] GREEN: `core/line_signature.py` に `verify_line_signature(*, body, signature, channel_secret)` を実装
  - [x] GREEN: HMAC-SHA256 + Base64 + `hmac.compare_digest()` を実装
  - [x] REFACTOR: 入力ガード（`None` / 空文字）と型注釈を整理

---

## Phase 2: スキーマ定義（Story 2）✅ 完了

- [x] Story 2: LINE Webhook スキーマを定義する
  - [x] RED: `tests/calendar_auto_register/features/line_webhook/test_schemas_line_webhook_post.py` を作成
  - [x] RED: 以下の失敗テストを追加
    - [x] `LineWebhookRequest` の JSON パースが失敗する状態を確認
    - [x] `LineSource` の必須項目（`userId`）が欠如したとき `ValidationError`
    - [x] `LineMessage.type` が `"sticker"` など未知の値でもパースできる（`str` 型）
    - [x] `events` が空配列でもパースできる
  - [x] RED: 以下の正常系テストを追加
    - [x] テキストメッセージイベントのパース
    - [x] 画像メッセージイベントのパース
    - [x] `follow` イベント（`message` フィールドなし）のパース
    - [x] 複数イベントのパース
  - [x] GREEN: `features/line_webhook/schemas_line_webhook_post.py` を実装
    - [x] `LineSource(BaseModel)`: `type`, `userId`（LINE API のキー名そのまま）
    - [x] `LineMessage(BaseModel)`: `type: str`, `id: str`, `text: str | None`
    - [x] `LineWebhookEvent(BaseModel)`: `type: str`, `message: LineMessage | None`, `timestamp`, `source`, `replyToken`
    - [x] `LineWebhookRequest(BaseModel)`: `destination: str`, `events: list[LineWebhookEvent]`
  - [x] REFACTOR: 設計判断をコメントで明記（`type: str` にした理由など）

---

## Phase 3: 既存クライアントの拡張（Story 3-4）✅ 完了

> **注意**: 新規ファイルを作成しない。既存ファイルに関数を追加する（lambdalith パターン）。

### Story 3: `clients/line_client.py` に `get_message_content()` を追加

- [x] Story 3: LINE Content API で画像バイナリを取得する
  - [x] RED: `tests/calendar_auto_register/clients/test_line_client.py` に以下を追加
    - [x] `get_message_content()` が存在しない状態を確認（テストが RED になることを確認）
    - [x] API エラー → `LineApiError` テスト
    - [x] 404 Not Found（メッセージ期限切れ）→ `LineApiError` テスト
  - [x] RED: 正常系: `get_message_content()` が `bytes` を返すテストを追加
  - [x] GREEN: `clients/line_client.py` に `get_message_content(*, channel_access_token, message_id) -> bytes` を追加
    - [x] `MessagingApiBlob` を使用（`linebot.v3.messaging` からインポート）
    - [x] 既存の `LineApiError`, `_build_error_message()` を再利用
  - [x] REFACTOR: `MessagingApiBlob` のインポートを既存インポートブロックに整理

### Story 4: `clients/bedrock_client.py` に `invoke_model_with_image()` を追加

- [x] Story 4: Bedrock に画像付きリクエストを送信する
  - [x] RED: `tests/calendar_auto_register/clients/test_bedrock_client.py` に以下を追加
    - [x] `invoke_model_with_image()` が存在しない状態を確認
    - [x] 画像 base64 エンコードが正しくリクエストボディに含まれるテスト
    - [x] `invoke_model()` が内部で呼ばれることのテスト（重複実装しないことを確認）
  - [x] GREEN: `clients/bedrock_client.py` に `invoke_model_with_image(*, region, model_id, image_bytes, prompt, media_type, max_tokens)` を追加
    - [x] 画像を base64 エンコードしてリクエストボディを構築
    - [x] 内部で既存の `invoke_model()` を呼び出す（HTTP 通信の重複を避ける）
  - [x] REFACTOR: `media_type` のデフォルト値（`"image/jpeg"`）の妥当性を確認

---

## Phase 4: LLM 共通化（Story 5）[D3, D7] ✅ 完了

> **目的**: メール固有処理（Unsubscribe 除去・HTML 解析）を LINE テキストに混入させない。
> LangChain チェーン（retry・正規化）をメール・LINE で共有する。

### Story 5a: `core/prompts.py` に LINE 用プロンプトを追加 [D3]

- [x] Story 5a: LINE テキスト用のユーザーメッセージを構築する
  - [x] RED: `tests/calendar_auto_register/core/test_prompts.py` に以下を追加
    - [x] `build_line_text_user_message()` が存在しない状態を確認
    - [x] 返り値に入力テキストが含まれるテスト
    - [x] 返り値に "件名" や "送信者" などメール固有の語句が含まれないテスト
  - [x] GREEN: `core/prompts.py` に `build_line_text_user_message(text: str) -> str` を追加
    - [x] メール用の `build_extraction_user_message()` と分離
    - [x] `CALENDAR_EVENT_EXTRACTION_SYSTEM` はシステムプロンプトとして共用
  - [x] REFACTOR: プロンプトインジェクション対策のコメントを追加

### Story 5b: `llm_extract/usecase_llm_extract.py` を共通化 [D3, D7]

- [x] Story 5b: LangChain チェーンを共通化し、LINE テキスト用の関数を追加する
  - [x] RED: `tests/calendar_auto_register/features/llm_extract/test_usecase_llm_extract.py` に以下を追加
    - [x] `extract_events_from_raw_text()` が存在しない状態を確認
    - [x] `extract_events_from_raw_text()` が `NormalizedMail` 経由でなく呼べるテスト
    - [x] `extract_events_from_raw_text()` のテキストに "Unsubscribe" が含まれても切れないテスト
    - [x] 既存 `extract_events()` テストが引き続き通ることを確認（回帰テスト）
  - [x] GREEN: `_run_extraction_chain(user_message_text, *, settings)` を追加 [D7]
    - [x] LangChain チェーン（ChatBedrock + NormalizedJsonOutputParser + retry）を共通実装
    - [x] 既存の `extract_events()` をリファクタリングして `_run_extraction_chain()` を使うよう変更
  - [x] GREEN: `extract_events_from_raw_text(text, *, settings)` を追加 [D3]
    - [x] `_preprocess_mail_body()` を呼ばない（メール前処理を適用しない）
    - [x] `build_line_text_user_message()` でユーザーメッセージを構築
    - [x] `_run_extraction_chain()` を呼び出す
  - [x] GREEN: `normalize_event_to_half_width` を公開エイリアスとして追加 [D4]
    - [x] `normalize_event_to_half_width = _normalize_event_to_half_width`
  - [x] REFACTOR: 既存 `extract_events()` の重複コードを `_run_extraction_chain()` に統合
  - [x] REFACTOR: 公開 API（`extract_events`, `extract_events_from_raw_text`, `normalize_event_to_half_width`）と内部実装の境界を明確化

---

## Phase 5: usecase 実装（Story 6）[D6, D8, D10] ✅ 完了

> **アーキテクチャ変更**: usecase は EvB.putEvents のみ実行する。
> LLM/Calendar/通知の呼び出しは行わない（オーケストレーターは SFN）。[D8, D10]

- [x] Story 6: LINE Webhook usecase を EventBridge.putEvents のみに書き直す
  - [x] RED: `tests/calendar_auto_register/features/line_webhook/test_usecase_line_webhook_post.py` を新アーキテクチャに合わせて書き直す
    - [x] **[D6]** `allowlist_line_user_ids` に含まれない `userId` → `_put_line_event` が呼ばれない
    - [x] **[D6]** `allowlist_line_user_ids` が空リスト → 全ユーザーに対して `_put_line_event` が呼ばれる
    - [x] `event.type != "message"` → `_put_line_event` が呼ばれない（`follow` イベントなど）
    - [x] 未対応メッセージタイプ（`sticker`）→ `_put_line_event` が呼ばれない
    - [x] **[D10]** テキストメッセージ → EventBridge.putEvents が呼ばれる（LLM は呼ばれない）
    - [x] **[D10]** 画像メッセージ → EventBridge.putEvents が呼ばれる（LINE DL は呼ばれない）
    - [x] EventBridge.putEvents のペイロードに `message_type`, `message_id`, `text`, `user_id` が含まれる
    - [x] 空 events リスト → putEvents が呼ばれない
  - [x] GREEN: `features/line_webhook/usecase_line_webhook_post.py` を書き直す
    - [x] **[D10]** LLM/Calendar/通知の呼び出しをすべて削除
    - [x] `_put_line_event(event, *, settings)`: EventBridge.putEvents を呼ぶ
      - [x] `boto3.client("events", region_name=settings.region)` でクライアント生成
      - [x] Source: `"calendar-auto-register.line"`, DetailType: `"LineMessageEvent"`
      - [x] Detail: `{"message_type", "message_id", "text", "user_id"}` の JSON
    - [x] 未対応メッセージタイプ（text/image 以外）のフィルタリングを追加
    - [x] `_process_message_event`, `_extract_events_from_image`, `_download_image`, `_notify_error`, `_parse_llm_response` を削除
  - [x] REFACTOR: 不要な import（bedrock_client, line_client, calendar_events, llm_extract 等）を削除

---

## Phase 6: ルーター実装（Story 7）✅ 完了

- [x] Story 7: `POST /line/webhook` エンドポイントを実装する
  - [x] RED: `tests/calendar_auto_register/features/line_webhook/test_router_line_webhook_post.py` を作成
  - [x] RED: 失敗系テスト（署名なし→403、署名不正→403、SECRET未設定→500）
  - [x] GREEN: `features/line_webhook/router_line_webhook_post.py` を実装
  - [x] GREEN: `app.py` に `line_webhook_router` を `include_router()` で登録
  - [x] REFACTOR: `request.app.state.settings` からの settings 取得パターンを既存 router と統一
- [x] E2E テスト更新: usecase が EvB.putEvents のみになったため、テストのモック対象を更新
  - [x] `test_E2E_テキストメッセージ完全フロー()` → boto3 putEvents をモックしてアサート
  - [x] `test_E2E_未認可userId_200でスキップ()` → putEvents が呼ばれないことをアサート
  - [x] `test_E2E_空events_200()` → putEvents が呼ばれないことをアサート
  - [x] `test_E2E_followイベント_200()` → putEvents が呼ばれないことをアサート

---

## Phase 7: `/llm/extract-event` スキーマ統合（Story 8）[D9] ✅ 完了

> **目的**: メールとテキストを単一エンドポイントで処理する。`text` 必須、メールコンテキストは任意。

- [x] Story 8: `POST /llm/extract-event` エンドポイントを統合スキーマに変更する
  - [x] RED: `test_llm_extract.py` に以下を追加
    - [x] `LlmExtractEventRequest` スキーマ: `text` なし → 422
    - [x] `text` のみ → `extract_events_from_raw_text()` が呼ばれる（LINE テキストパス）
    - [x] `text` + `from_addr` 等 → `extract_events()` が呼ばれる（メールパス）
  - [x] GREEN: `features/llm_extract/schemas_llm_extract.py` を更新
    - [x] `LlmExtractEventRequest(BaseModel)` を更新:
      - [x] `text: str` (必須)
      - [x] `html: str | None = None`
      - [x] `from_addr: str | None = None`
      - [x] `reply_to: str | None = None`
      - [x] `subject: str | None = None`
      - [x] `received_at: datetime | None = None`
      - [x] `model_config = ConfigDict(extra="forbid")`
    - [x] `LlmExtractImageEventRequest` を追加（Phase 8 準備）
    - [x] `NormalizedMailModel` を廃止（フラット構造に統合）
  - [x] GREEN: `features/llm_extract/router_llm_extract.py` を更新
    - [x] `POST /llm/extract-event` ルートで新スキーマを受け付ける
    - [x] メールフィールドが存在すれば `extract_events(NormalizedMail(...))` を呼ぶ
    - [x] `text` のみなら `extract_events_from_raw_text(text)` を呼ぶ
  - [x] REFACTOR: 既存のメール処理テストを新スキーマ形式（フラット構造）に更新。72 テスト全 GREEN

---

## Phase 8: `/llm/extract-event-image` 新規実装（Story 9）[D4, D5] ✅ 完了

> **目的**: LINE 画像メッセージの LLM 抽出。LINE SM から HTTP Task で呼び出される。

- [x] Story 9: `POST /llm/extract-event-image` エンドポイントを新設する
  - [x] RED: `test_llm_extract.py` に以下を追加
    - [x] `message_id` なし → 422
    - [x] `LINE_CHANNEL_ACCESS_TOKEN` 未設定 → 500
    - [x] LINE Content API 失敗 → 500
    - [x] 正常系: `message_id` → 画像DL → Bedrock → events レスポンス
  - [x] GREEN: `features/llm_extract/schemas_llm_extract.py` に追加（Phase 7 で先行追加済み）
    - [x] `LlmExtractImageEventRequest(BaseModel)`: `message_id: str`, `ConfigDict(extra="forbid")`
  - [x] GREEN: `features/llm_extract/usecase_llm_extract.py` に追加
    - [x] `extract_events_from_image(message_id, *, settings) -> list[GoogleCalendarEventModel]`
      - [x] `line_client.get_message_content(message_id)` で画像 bytes 取得
      - [x] `bedrock_client.invoke_model_with_image(image_bytes, prompt=CALENDAR_EVENT_EXTRACTION_SYSTEM)` で推論
      - [x] `_parse_image_llm_response(response)` でパース
      - [x] **[D4]** `_normalize_event_to_half_width(e)` を各イベントに適用
      - [x] **[D5]** `@retry(stop=stop_after_attempt(5), wait=wait_exponential_jitter(1, 10))` デコレータ（tenacity）
  - [x] GREEN: `features/llm_extract/router_llm_extract.py` に `POST /llm/extract-event-image` を追加
  - [x] REFACTOR: `_parse_image_llm_response()` を llm_extract usecase に配置（Bedrock レスポンス形式依存）

---

## Phase 9: 品質ゲート ✅ 完了（カバレッジ確認のみ保留）

- [x] `uv run ruff check --fix src/calendar_auto_register/` でエラーゼロを確認
- [x] `uv run mypy src/calendar_auto_register/` でエラーゼロを確認（39 files）
- [x] `uv run pytest` で 76 テスト全通過を確認
- [ ] テストカバレッジ **80% 以上**を確認 ← `pytest-cov` 未インストールのためスキップ（別途確認推奨）
- [x] 既存テスト（`mailparse_post`, `llm_extract`, `calendar_events`, `line_notify_post`）が回帰なく通ることを確認

---

## Phase 10: インフラ・デプロイ準備

> [D8, D11] SFN + EvB による非同期オーケストレーション構成。

- [x] SAM `template.yaml` の更新
  - [x] Lambda IAM: `events:PutEvents` 権限を追加
  - [x] Lambda IAM: Bedrock Vision モデル ARN を追加（`anthropic.claude-3-5-sonnet-20240620-v1:0` 兼用）
  - [x] EventBridge Rule: LINE Webhook イベント → LINE SM トリガー（`LineEventRule`）
  - [x] EventBridge Rule: S3 Event → Mail SM トリガー（`MailEventRule`、InputTransformer で s3_key/bucket を変換）
  - [x] SFN: Mail State Machine 定義（`MailStateMachine`、フラットスキーマ + DefinitionSubstitutions）
  - [x] SFN: LINE State Machine 定義（`LineStateMachine`、Choice state: text/image/Unsupported）
  - [x] SFN IAM: `SfnExecutionRole`（execute-api:Invoke + X-Ray）
  - [x] EvB IAM: `EvbToSfnRole`（states:StartExecution、Mail SM + LINE SM）
  - [x] API エンドポイントをシークレット化（`DefinitionSubstitutions` で `!Sub` を使用、git に API ID をハードコードしない）
- [ ] SSM Parameter Store に新規環境変数を登録
  - [ ] `LINE_CHANNEL_SECRET`
  - [ ] `ALLOWLIST_LINE_USER_IDS` (`["U..."]` の JSON 形式で登録)
- [ ] LINE Developers Console の Webhook URL を更新・有効化

---

## Phase 11: 本番検証

- [ ] 実機 LINE でテキストメッセージ送信テストを実施（正常系）
- [ ] 実機 LINE で画像送信テストを実施（チラシ・スクリーンショット）
- [ ] **[D6]** 未認可アカウントからメッセージを送り、処理されないことを確認
- [ ] 不正署名 Webhook を `curl` で送り、403 が返ることを確認（Layer 1）
- [ ] CloudWatch Logs で WARNING ログ（未認可 userId）が記録されることを確認
- [ ] CloudWatch Alarm（Lambda エラー率）が設定されていることを確認

---

## 実装完了後の振り返り

### 完了日
<!-- 実装完了日を記入 -->

### 計画との差分
<!-- 計画時の想定と異なった部分を記載 -->

アーキテクチャ変更: 当初 Python 関数直接呼び出しによるオーケストレーションを想定していたが、
「すべてAPI化・SFN がオーケストレーター」に変更。design.md を全面改訂（D8-D11 追加）。

### 新規追加タスク
- Phase 7: `/llm/extract-event` スキーマ統合（メール/テキスト共通化）[D9]
- Phase 8: `/llm/extract-event-image` 新規実装（画像 LLM 抽出専用エンドポイント）[D4, D5]
- Phase 10 に SFN・EventBridge・SAM の更新タスクを追加

### スキップしたタスク
<!-- スキップしたタスクと理由を記載 -->

### 技術的学習
<!-- 実装を通じて学んだ技術的知見を記載 -->

### プロセス改善提案
<!-- 次回のステアリングファイルの運用への改善提案を記載 -->

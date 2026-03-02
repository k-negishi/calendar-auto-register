"""`/llm/extract-event` と `/llm/extract-event-image` のリクエスト/レスポンススキーマ。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from calendar_auto_register.shared.schemas.calendar import GoogleCalendarEventModel


class LlmExtractEventRequest(BaseModel):
    """LLM イベント抽出リクエスト（LINE テキストとメールを統合）。

    [D9] メールコンテキストフィールドが存在するか否かでパスを分岐。
    - メールパス（from_addr/html/subject 等あり）: text は null 可（html から前処理）
    - LINE テキストパス（コンテキストなし）: text は必須（ルーターで検証）
    """

    # LINE テキスト / メール本文（メールパスでは null 可 = html を使用）
    text: str | None = None

    # メール固有（任意）。存在すれば HTML 前処理（タグ除去・Unsubscribe 削除）を適用する
    html: str | None = None
    from_addr: str | None = None
    reply_to: str | None = None
    subject: str | None = None
    received_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")


class LlmExtractEventResponse(BaseModel):
    """LLM 抽出レスポンス"""

    events: list[GoogleCalendarEventModel] = Field(default_factory=list)


class LlmExtractImageEventRequest(BaseModel):
    """画像からのイベント抽出リクエスト（LINE 画像メッセージ用）。

    [D5, Phase 8] LINE Content API の message_id を受け取り、画像をダウンロードして
    Bedrock Vision LLM でイベントを抽出する。
    """

    message_id: str  # LINE Content API のメッセージ ID

    model_config = ConfigDict(extra="forbid")

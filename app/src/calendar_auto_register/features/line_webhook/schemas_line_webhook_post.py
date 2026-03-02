"""LINE Webhook スキーマ定義。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LineSource(BaseModel):
    """LINE メッセージソース。

    LINE API のフィールド名 (userId, groupId, roomId) をそのまま使用する。
    Python の命名規則 (user_id) への変換より、LINE Platform との互換性を優先。
    """

    type: Literal["user", "group", "room"]
    userId: str


class LineMessage(BaseModel):
    """LINE メッセージ。

    type を str にした理由: "text", "image" 以外の未知のメッセージタイプ
    (sticker, video 等) もパースエラーにせず、usecase 側でスキップする設計。
    """

    type: str
    id: str
    text: str | None = None


class LineWebhookEvent(BaseModel):
    """LINE Webhook イベント。

    type を str にした理由: "message" 以外に "follow", "unfollow" 等がある。
    message を Optional にした理由: "follow" イベント等には message フィールドがない。
    """

    type: str
    message: LineMessage | None = None
    timestamp: int
    source: LineSource
    replyToken: str | None = Field(default=None)


class LineWebhookRequest(BaseModel):
    """LINE Webhook リクエスト。"""

    destination: str
    events: list[LineWebhookEvent]

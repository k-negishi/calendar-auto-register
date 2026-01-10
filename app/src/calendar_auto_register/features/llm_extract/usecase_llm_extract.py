"""予定抽出ユースケース: メール本文を LLM で解析。"""

from __future__ import annotations

import json
from typing import Any

import boto3  # type: ignore[import-untyped]

try:  # テスト時にパッチできるようにモジュール変数として保持する
    from langchain_aws import ChatBedrock as ChatBedrock
except ModuleNotFoundError:  # pragma: no cover - 環境依存
    ChatBedrock = None
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from calendar_auto_register.core.models import NormalizedMail
from calendar_auto_register.core.prompts import (
    CALENDAR_EVENT_EXTRACTION_SYSTEM,
    build_extraction_user_message,
)
from calendar_auto_register.core.settings import Settings
from calendar_auto_register.features.llm_extract.schemas_llm_extract import (
    GoogleCalendarEventModel,
)


class EventExtractionResponse(BaseModel):
    """LLM抽出レスポンス"""

    events: list[GoogleCalendarEventModel] = Field(default_factory=list)


def extract_events(
    normalized_mail: NormalizedMail,
    *,
    settings: Settings,
) -> list[GoogleCalendarEventModel]:
    """
    メール本文から Bedrock (Claude) を使って予定情報を抽出する。

    LangChain ChatAnthropic を使用してプロンプトベースで JSON を取得し、
    Pydantic で検証して Google Calendar API 互換形式で応答。

    Args:
        normalized_mail: 正規化されたメール情報
        settings: アプリケーション設定

    Returns:
        抽出された予定リスト（Google Calendar API 互換形式）

    Raises:
        ValueError: LLM 出力が無効な場合
        RuntimeError: Bedrock API エラー
    """

    if not settings.bedrock_model_id:
        raise ValueError("Bedrock モデルID が設定されていません")

    try:
        # AWS Bedrock クライアントを初期化（東京リージョン固定）
        bedrock_client = boto3.client("bedrock-runtime", region_name=settings.region)

        if ChatBedrock is None:
            raise RuntimeError("langchain_aws がインストールされていません。")

        chat = ChatBedrock(
            model_id=settings.bedrock_model_id,
            client=bedrock_client,
            model_kwargs={"max_tokens": 2048},
        )

        # プロンプト構築
        user_message_text = build_extraction_user_message(normalized_mail)

        # メッセージの構築
        messages = [
            SystemMessage(content=CALENDAR_EVENT_EXTRACTION_SYSTEM),
            HumanMessage(content=user_message_text),
        ]

        # LLM 呼び出し（自動リトライ: LangChain デフォルト）
        response = chat.invoke(messages)

        # レスポンスのテキストを取得
        response_text: str = response.content  # type: ignore[assignment]

        # JSON を抽出してパース
        json_str = _extract_json_from_text(response_text)
        parsed_json = json.loads(json_str)

        # Pydantic で検証
        events = _extract_events_from_response(parsed_json)

        return events

    except ValueError as exc:
        raise exc
    except Exception as exc:
        raise RuntimeError(f"LLM 呼び出し失敗: {exc}") from exc


def _extract_json_from_text(text: str) -> str:
    """
    テキストから JSON オブジェクトを抽出。

    LLM が Markdown のコードブロック内に JSON を返す場合に対応。

    Args:
        text: LLM の出力テキスト

    Returns:
        JSON 文字列
    """

    text = text.strip()

    # ```json ... ``` 形式の場合は除去
    if text.startswith("```json"):
        text = text[7:]  # "```json" を除去
    if text.startswith("```"):
        text = text[3:]  # "```" を除去
    if text.endswith("```"):
        text = text[:-3]  # "```" を除去

    return text.strip()


def _extract_events_from_response(
    response: dict[str, Any],
) -> list[GoogleCalendarEventModel]:
    """
    LLM レスポンスから予定オブジェクトを抽出・検証。

    Args:
        response: {"events": [...]} 形式の JSON

    Returns:
        Pydantic で検証済みの GoogleCalendarEventModel リスト

    Raises:
        ValueError: スキーマ検証に失敗した場合
    """

    try:
        events_data = response.get("events", [])
        if not isinstance(events_data, list):
            raise ValueError('"events" はリストである必要があります')

        # 各予定を Pydantic で検証
        events = []
        for event_data in events_data:
            try:
                event = GoogleCalendarEventModel(**event_data)
                events.append(event)
            except Exception as exc:
                raise ValueError(
                    f"予定データの検証に失敗しました: {event_data} - {exc}"
                ) from exc

        return events

    except ValueError as exc:
        raise ValueError(f"LLM 出力の検証に失敗しました: {exc}") from exc

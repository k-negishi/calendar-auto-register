"""予定抽出ユースケース: メール本文を LLM で解析。"""

from __future__ import annotations

import unicodedata
from typing import Any

import boto3  # type: ignore[import-untyped]
from langchain_core.runnables.retry import ExponentialJitterParams

try:  # テスト時にパッチできるようにモジュール変数として保持する
    from langchain_aws import ChatBedrock
except ModuleNotFoundError:  # pragma: no cover - 環境依存
    ChatBedrock = None  # type: ignore
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
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


def _normalize_to_half_width(text: str) -> str:
    """
    全角文字を半角に正規化する。

    NFKC (Compatibility Decomposition) を使用して、全角の英数字・記号を半角に変換。

    Args:
        text: 正規化対象のテキスト

    Returns:
        半角に正規化されたテキスト
    """
    return unicodedata.normalize("NFKC", text)


def _normalize_event_to_half_width(event: GoogleCalendarEventModel) -> GoogleCalendarEventModel:
    """
    GoogleCalendarEventModel のテキストフィールドを半角に正規化する。

    Args:
        event: 正規化対象のイベント

    Returns:
        半角に正規化されたイベント
    """
    # 更新するフィールドを集める
    update_data: dict[str, Any] = {}

    # summary（必須）- メール本文から抽出されるため全角の可能性あり
    update_data["summary"] = _normalize_to_half_width(event.summary)

    # location（任意）- メール本文から抽出されるため全角の可能性あり
    if event.location:
        update_data["location"] = _normalize_to_half_width(event.location)

    # description（任意）- メール本文から抽出されるため全角の可能性あり
    if event.description:
        update_data["description"] = _normalize_to_half_width(event.description)

    return event.model_copy(update=update_data)


class NormalizedJsonOutputParser(JsonOutputParser):
    """
    LangChain JsonOutputParser の拡張版。

    JSON パース後、自動的に GoogleCalendarEventModel の全フィールドを
    半角正規化する。LangChain の runnable chain に統合。
    """

    def parse(self, text: str) -> dict[str, Any]:
        """
        JSON をパースして、イベントを正規化して返す。

        Args:
            text: LLM からの出力テキスト（JSON形式）

        Returns:
            正規化済みの dict（{events: [...]}）
        """
        # 基底クラスの parse メソッドで JSON をパース
        parsed_dict = super().parse(text)

        # events キーが存在するかチェック
        if "events" not in parsed_dict:
            return parsed_dict

        events_data = parsed_dict["events"]
        if not isinstance(events_data, list):
            return parsed_dict

        # 各イベントを GoogleCalendarEventModel に変換して正規化
        normalized_events = []
        for event_data in events_data:
            # dict → GoogleCalendarEventModel に変換
            event = GoogleCalendarEventModel(**event_data)
            # 正規化して追加
            normalized_event = _normalize_event_to_half_width(event)
            normalized_events.append(normalized_event.model_dump())

        parsed_dict["events"] = normalized_events
        return parsed_dict


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

    LangChain ChatBedrock と NormalizedJsonOutputParser を使用してプロンプトベースで
    JSON を取得。パーサーが自動的に LLM レスポンスの全フィールドを半角正規化し、
    Pydantic で検証して Google Calendar API 互換形式で応答。

    Args:
        normalized_mail: 正規化されたメール情報
        settings: アプリケーション設定

    Returns:
        抽出された予定リスト（Google Calendar API 互換形式、半角正規化済み）

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

        chat: Any = ChatBedrock(
            model=settings.bedrock_model_id,
            client=bedrock_client,
            model_kwargs={"max_tokens": 2048},
        )

        # カスタム出力パーサーを初期化（半角正規化付き）
        output_parser = NormalizedJsonOutputParser(pydantic_object=EventExtractionResponse)

        # Runnable チェーン（LLM → カスタムパーサー → 正規化）
        # リトライ機能付き: 最大5回、エクスポーネンシャルバックオフ
        chain = (chat | output_parser).with_retry(
            retry_if_exception_type=(ValueError, RuntimeError),
            stop_after_attempt=5,
            wait_exponential_jitter=True,
            exponential_jitter_params=ExponentialJitterParams(
                initial=1,
                max=10,
                exp_base=2,
            ),
        )

        # プロンプト構築
        user_message_text = build_extraction_user_message(normalized_mail)

        # メッセージの構築
        messages = [
            SystemMessage(content=CALENDAR_EVENT_EXTRACTION_SYSTEM),
            HumanMessage(content=user_message_text),
        ]

        # チェーン実行（リトライ付き）
        # NormalizedJsonOutputParser が parse メソッドで正規化を実施
        parsed_dict = chain.invoke(messages)

        # Pydantic で検証
        parsed_response = EventExtractionResponse(**parsed_dict)

        # 正規化済みの予定を返す
        return parsed_response.events

    except ValueError as exc:
        raise exc
    except Exception as exc:
        raise RuntimeError(f"LLM 呼び出し失敗: {exc}") from exc

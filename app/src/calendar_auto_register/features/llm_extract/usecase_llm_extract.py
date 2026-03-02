"""予定抽出ユースケース: メール本文・テキスト・画像を LLM で解析。"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

import boto3  # type: ignore[import-untyped]
from bs4 import BeautifulSoup
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


def _preprocess_mail_body(normalized_mail: NormalizedMail) -> str:
    """
    メール本文を前処理：HTML タグ削除、ノイズ除去。

    URL 前後の説明文脈を保持することで、LLM が URL の意味を正確に理解できる。
    LLM への入力を最小化しトークン削減とタイムアウト回避を実現。

    Args:
        normalized_mail: 正規化されたメール情報

    Returns:
        前処理済みテキスト（URL の文脈付き）
    """
    # HTML が優先、なければ text を使用
    body = normalized_mail.html or normalized_mail.text or ""

    # BeautifulSoup で HTML タグを削除（テキストと URL の関連性は保持）
    soup = BeautifulSoup(body, "html.parser")
    text = soup.get_text(separator="\n")

    # Unsubscribe 以降を削除（不要な購読管理情報）
    if "Unsubscribe" in text:
        text = text.split("Unsubscribe")[0]

    # 複数改行を正規化（トークン削減）
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 余計な空白削除
    text = "\n".join(line.rstrip() for line in text.split("\n") if line.strip())

    return text


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


def _run_extraction_chain(
    user_message_text: str,
    *,
    settings: Settings,
) -> list[GoogleCalendarEventModel]:
    """LangChain チェーン（ChatBedrock + retry + 正規化）を実行する共通実装。

    extract_events() と extract_events_from_raw_text() の両方から呼び出される。
    LLM・リトライ・正規化の設定を一箇所に集約する。

    Args:
        user_message_text: LLM に渡すユーザーメッセージ
        settings: アプリケーション設定

    Returns:
        抽出された予定リスト（Google Calendar API 互換形式、半角正規化済み）
    """
    if not settings.bedrock_model_id:
        raise ValueError("Bedrock モデルID が設定されていません")

    try:
        bedrock_boto3 = boto3.client("bedrock-runtime", region_name=settings.region)

        if ChatBedrock is None:
            raise RuntimeError("langchain_aws がインストールされていません。")

        chat: Any = ChatBedrock(
            model=settings.bedrock_model_id,
            client=bedrock_boto3,
            model_kwargs={"max_tokens": 2048},
        )
        output_parser = NormalizedJsonOutputParser(pydantic_object=EventExtractionResponse)
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
        messages = [
            SystemMessage(content=CALENDAR_EVENT_EXTRACTION_SYSTEM),
            HumanMessage(content=user_message_text),
        ]
        parsed_dict = chain.invoke(messages)
        parsed_response = EventExtractionResponse(**parsed_dict)
        return [_normalize_event_to_half_width(e) for e in parsed_response.events]

    except ValueError as exc:
        raise exc
    except Exception as exc:
        raise RuntimeError(f"LLM 呼び出し失敗: {exc}") from exc


def extract_events(
    normalized_mail: NormalizedMail,
    *,
    settings: Settings,
) -> list[GoogleCalendarEventModel]:
    """
    メール本文から Bedrock (LLM) を使って予定情報を抽出する。

    **30秒タイムアウト対応**: メール本文を事前に処理（HTML除去、ノイズ削除）
    してから LLM に投げることで、トークン削減と高速処理を実現。

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
    # Step 1: メール本文を前処理（HTML削除、ノイズ除去）
    cleaned_text = _preprocess_mail_body(normalized_mail)

    # 前処理済みメール情報を作成
    preprocessed_mail = NormalizedMail(
        from_addr=normalized_mail.from_addr,
        reply_to=normalized_mail.reply_to,
        subject=normalized_mail.subject,
        received_at=normalized_mail.received_at,
        text=cleaned_text,
        html=None,
        attachments=[],
    )

    # Step 2: プロンプト構築（前処理済みメール）
    user_message_text = build_extraction_user_message(preprocessed_mail)

    return _run_extraction_chain(user_message_text, settings=settings)


def extract_events_from_raw_text(
    text: str,
    *,
    settings: Settings,
) -> list[GoogleCalendarEventModel]:
    """raw テキストから LLM でイベント情報を抽出する（メール前処理なし）。

    LINE テキストなど、メール以外の入力に対して使用する。
    _preprocess_mail_body() を経由しないため、Unsubscribe 除去・HTML 解析が行われない。
    _run_extraction_chain() を通じてリトライ・正規化を共有する。

    Args:
        text: 入力テキスト（HTML 解析・Unsubscribe 除去なし）
        settings: アプリケーション設定

    Returns:
        抽出された予定リスト（半角正規化済み）

    Raises:
        ValueError: LLM 出力が無効な場合
        RuntimeError: Bedrock API エラー
    """
    from calendar_auto_register.core.prompts import build_line_text_user_message

    user_message = build_line_text_user_message(text)
    return _run_extraction_chain(user_message, settings=settings)


# D4: 画像パスでも normalize_event_to_half_width() を使えるよう公開エイリアスを定義
normalize_event_to_half_width = _normalize_event_to_half_width


def _parse_image_llm_response(
    response: dict[str, object],
) -> list[GoogleCalendarEventModel]:
    """Bedrock Vision レスポンスをパースして GoogleCalendarEventModel のリストを返す。

    Anthropic Messages API 形式（content リスト → text → JSON）でパースする。
    """
    content = response.get("content", [])
    if not isinstance(content, list) or not content:
        return []

    first = content[0]
    text = first.get("text", "") if isinstance(first, dict) else ""
    if not text:
        return []

    try:
        parsed = json.loads(str(text))
    except (json.JSONDecodeError, ValueError):
        return []

    events_data = parsed.get("events", [])
    return [GoogleCalendarEventModel(**e) for e in events_data]


def extract_events_from_image(
    message_id: str,
    *,
    settings: Settings,
) -> list[GoogleCalendarEventModel]:
    """LINE 画像メッセージから Vision LLM でイベント情報を抽出する。

    [D4] テキストパスと同一の正規化（normalize_event_to_half_width）を適用する。
    [D5] tenacity @retry（5回、指数バックオフ+ジッター）でリトライする。

    Args:
        message_id: LINE Content API のメッセージ ID
        settings: アプリケーション設定

    Returns:
        抽出された予定リスト（半角正規化済み）

    Raises:
        ValueError: LINE_CHANNEL_ACCESS_TOKEN または BEDROCK_MODEL_ID が未設定
        RuntimeError: LINE Content API または Bedrock API エラー
    """
    from tenacity import retry, stop_after_attempt, wait_exponential_jitter

    from calendar_auto_register.clients import bedrock_client, line_client
    from calendar_auto_register.core.prompts import CALENDAR_EVENT_EXTRACTION_SYSTEM

    if not settings.line_channel_access_token:
        raise ValueError("LINE_CHANNEL_ACCESS_TOKEN が未設定です")
    if not settings.bedrock_model_id:
        raise ValueError("BEDROCK_MODEL_ID が未設定です")

    try:
        image_bytes = line_client.get_message_content(
            channel_access_token=settings.line_channel_access_token,
            message_id=message_id,
        )
    except Exception as exc:
        raise RuntimeError(f"LINE 画像取得失敗: {exc}") from exc

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=10),
        reraise=True,
    )
    def _invoke_with_retry() -> list[GoogleCalendarEventModel]:
        response = bedrock_client.invoke_model_with_image(
            region=settings.region,
            model_id=settings.bedrock_model_id,  # type: ignore[arg-type]
            image_bytes=image_bytes,
            prompt=CALENDAR_EVENT_EXTRACTION_SYSTEM,
        )
        events = _parse_image_llm_response(response)
        # [D4] テキストパスと同一の正規化を適用
        return [_normalize_event_to_half_width(e) for e in events]

    try:
        return _invoke_with_retry()
    except Exception as exc:
        raise RuntimeError(f"画像 LLM 抽出失敗: {exc}") from exc

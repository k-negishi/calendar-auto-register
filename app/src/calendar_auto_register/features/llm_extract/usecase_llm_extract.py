"""予定抽出ユースケース: メール本文・テキスト・画像を LLM で解析。"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

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
from calendar_auto_register.core.relative_dates import (
    RelativeDateResolution,
    format_relative_date_context,
    resolve_relative_dates,
)
from calendar_auto_register.core.settings import Settings
from calendar_auto_register.features.llm_extract.schemas_llm_extract import (
    GoogleCalendarEventModel,
)
from calendar_auto_register.shared.schemas.calendar import DateModel, DateTimeModel


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

    # HTMLリンクは表示文言と href を残してからテキスト化する。
    soup = BeautifulSoup(body, "html.parser")
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href", "")).strip()
        if not href or href.startswith(("#", "javascript:", "data:")):
            continue
        label = anchor.get_text(" ", strip=True) or "リンク"
        if href not in label:
            anchor.replace_with(f"{label} ({href})")
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
    全角ASCII英数字・記号を半角にする。

    NFKC全体変換は丸数字なども変換するため、全角ASCII範囲だけを対象にする。

    Args:
        text: 正規化対象のテキスト

    Returns:
        半角に正規化されたテキスト
    """
    return "".join(
        chr(ord(char) - 0xFEE0)
        if "\uff01" <= char <= "\uff5e"
        else "¥"
        if char == "\uffe5"
        else char
        for char in text
    )


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
    reference_datetime = _reference_datetime_for_mail(normalized_mail, settings)
    user_message_text += format_relative_date_context(
        resolve_relative_dates(cleaned_text, reference_datetime=reference_datetime)
    )

    events = _run_extraction_chain(user_message_text, settings=settings)
    resolutions = resolve_relative_dates(cleaned_text, reference_datetime=reference_datetime)
    events = _apply_single_relative_date_resolution(events, resolutions)
    events = _align_event_description_weekdays(events)
    return _apply_concert_arrival_target(events, cleaned_text)


def extract_events_from_raw_text(
    text: str,
    *,
    settings: Settings,
    reference_datetime: datetime | None = None,
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

    reference_datetime = _normalize_reference_datetime(reference_datetime, settings)
    resolutions = resolve_relative_dates(text, reference_datetime=reference_datetime)
    user_message = build_line_text_user_message(
        text,
        current_datetime=reference_datetime.isoformat(timespec="seconds"),
    ) + format_relative_date_context(
        resolutions
    )
    events = _run_extraction_chain(user_message, settings=settings)
    events = _apply_single_relative_date_resolution(events, resolutions)
    events = _align_event_description_weekdays(events)
    return _apply_concert_arrival_target(events, text)


def _apply_single_relative_date_resolution(
    events: list[GoogleCalendarEventModel],
    resolutions: list[RelativeDateResolution],
) -> list[GoogleCalendarEventModel]:
    """対応関係が一意な場合に限り、LLMが誤った相対日付を返した結果を補正する。"""
    if len(events) != 1 or len(resolutions) != 1:
        return events

    event = events[0]
    expected_date = resolutions[0].resolved_date
    description = _replace_description_event_date(event.description, expected_date)

    if isinstance(event.start, DateModel) and isinstance(event.end, DateModel):
        try:
            actual_start = date.fromisoformat(event.start.date)
            actual_end = date.fromisoformat(event.end.date)
        except ValueError:
            return events
        day_delta = expected_date - actual_start
        if not day_delta.days:
            if description != event.description:
                return [event.model_copy(update={"description": description})]
            return events
        corrected = event.model_copy(
            update={
                "start": event.start.model_copy(update={"date": expected_date.isoformat()}),
                "end": event.end.model_copy(
                    update={"date": (actual_end + day_delta).isoformat()}
                ),
                "description": description,
            }
        )
        return [corrected]

    if isinstance(event.start, DateTimeModel) and isinstance(event.end, DateTimeModel):
        try:
            actual_start = datetime.fromisoformat(event.start.dateTime.replace("Z", "+00:00"))
            actual_end = datetime.fromisoformat(event.end.dateTime.replace("Z", "+00:00"))
        except ValueError:
            return events
        day_delta = expected_date - actual_start.date()
        if not day_delta.days:
            if description != event.description:
                return [event.model_copy(update={"description": description})]
            return events
        corrected = event.model_copy(
            update={
                "start": event.start.model_copy(
                    update={"dateTime": (actual_start + timedelta(days=day_delta.days)).isoformat()}
                ),
                "end": event.end.model_copy(
                    update={"dateTime": (actual_end + timedelta(days=day_delta.days)).isoformat()}
                ),
                "description": description,
            }
        )
        return [corrected]

    return events


def _replace_description_event_date(description: str | None, event_date: date) -> str | None:
    """説明欄の先頭にある開催日時も、補正後の日付に揃える。"""
    if not description:
        return description
    date_label = f"{event_date.year}年{event_date.month}月{event_date.day}日"
    weekday = "月火水木金土日"[event_date.weekday()]
    date_label_with_weekday = f"{date_label}({weekday})"
    return re.sub(
        r"^((?:開催日時|開始時刻):\s*)\d{4}年\d{1,2}月\d{1,2}日(?:\([月火水木金土日]\))?",
        lambda match: f"{match.group(1)}{date_label_with_weekday}",
        description,
        count=1,
    )


def _align_event_description_weekdays(
    events: list[GoogleCalendarEventModel],
) -> list[GoogleCalendarEventModel]:
    """説明欄先頭の開催日・曜日をイベント開始日に揃える。"""
    aligned: list[GoogleCalendarEventModel] = []
    for event in events:
        if isinstance(event.start, DateModel):
            try:
                event_date = date.fromisoformat(event.start.date)
            except ValueError:
                aligned.append(event)
                continue
        elif isinstance(event.start, DateTimeModel):
            try:
                event_date = datetime.fromisoformat(
                    event.start.dateTime.replace("Z", "+00:00")
                ).date()
            except ValueError:
                aligned.append(event)
                continue
        else:
            aligned.append(event)
            continue

        description = _replace_description_event_date(event.description, event_date)
        aligned.append(
            event if description == event.description else event.model_copy(
                update={"description": description}
            )
        )
    return aligned


def _apply_concert_arrival_target(
    events: list[GoogleCalendarEventModel],
    source_text: str,
) -> list[GoogleCalendarEventModel]:
    """本文の OPEN/START からコンサートの到着目標時刻を確定する。

    LLMが開場時刻をイベント開始時刻として返すことがあるため、
    開場1時間前を到着目標として決定論的に補正する。受付・発売イベントは
    公演日が異なるため、日時が公演日のイベントだけを対象にする。
    """
    match = re.search(
        r"(?:OPEN|開場)\s*(\d{1,2}):(\d{2})\s*[/／]\s*"
        r"(?:START|開演)\s*(\d{1,2}):(\d{2})",
        source_text,
        flags=re.IGNORECASE,
    )
    if not match:
        return events

    open_hour, open_minute, start_hour, start_minute = (
        int(value) for value in match.groups()
    )
    has_explicit_end = bool(re.search(r"終演", source_text))
    adjusted: list[GoogleCalendarEventModel] = []

    for event in events:
        if not isinstance(event.start, DateTimeModel) or not isinstance(event.end, DateTimeModel):
            adjusted.append(event)
            continue
        if any(keyword in event.summary for keyword in ("受付", "発売", "支払い期限")):
            adjusted.append(event)
            continue

        try:
            event_start = datetime.fromisoformat(event.start.dateTime.replace("Z", "+00:00"))
        except ValueError:
            adjusted.append(event)
            continue

        opening = event_start.replace(hour=open_hour, minute=open_minute, second=0, microsecond=0)
        show_start = event_start.replace(
            hour=start_hour, minute=start_minute, second=0, microsecond=0
        )
        arrival_target = opening - timedelta(hours=1)
        end = event.end
        if not has_explicit_end:
            end_datetime = show_start + timedelta(hours=3)
            end = end.model_copy(update={"dateTime": end_datetime.isoformat()})

        arrival_description = (
            f"到着目標: {arrival_target.strftime('%Y-%m-%d %H:%M')}（開場1時間前）\n"
            f"開場: {opening.strftime('%H:%M')} / 開演: {show_start.strftime('%H:%M')}"
        )
        description = event.description or ""
        description = re.sub(r"到着目標:.*(?:\n|$)", "", description).lstrip()
        if description:
            description = f"{arrival_description}\n{description}"
        else:
            description = arrival_description

        adjusted.append(
            event.model_copy(
                update={
                    "start": event.start.model_copy(
                        update={"dateTime": arrival_target.isoformat()}
                    ),
                    "end": end,
                    "description": description,
                }
            )
        )

    return adjusted


# D4: 画像パスでも normalize_event_to_half_width() を使えるよう公開エイリアスを定義
normalize_event_to_half_width = _normalize_event_to_half_width


def _normalize_reference_datetime(
    reference_datetime: datetime | None,
    settings: Settings,
) -> datetime:
    """入力受信時刻を設定タイムゾーンへ揃える。未指定なら現在時刻を使う。"""
    zone = ZoneInfo(settings.timezone_default)
    if reference_datetime is None:
        return datetime.now(zone)
    if reference_datetime.tzinfo is None:
        return reference_datetime.replace(tzinfo=zone)
    return reference_datetime.astimezone(zone)


def _reference_datetime_for_mail(normalized_mail: NormalizedMail, settings: Settings) -> datetime:
    """メールの受信日時を相対日付の基準にする。未指定なら現在日時を使う。"""
    zone = ZoneInfo(settings.timezone_default)
    received_at = normalized_mail.received_at
    if received_at is None:
        return datetime.now(zone)
    if received_at.tzinfo is None:
        return received_at.replace(tzinfo=zone)
    return received_at.astimezone(zone)


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
    reference_datetime: datetime | None = None,
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

    reference_datetime = _normalize_reference_datetime(reference_datetime, settings)

    if not settings.line_channel_access_token:
        raise ValueError("LINE_CHANNEL_ACCESS_TOKEN が未設定です")
    vision_model_id = settings.bedrock_vision_model_id or settings.bedrock_model_id
    if not vision_model_id:
        raise ValueError("BEDROCK_VISION_MODEL_ID または BEDROCK_MODEL_ID が未設定です")

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
            model_id=vision_model_id,
            image_bytes=image_bytes,
            system=CALENDAR_EVENT_EXTRACTION_SYSTEM,
            prompt=(
                "この画像からカレンダーの予定情報を抽出してください。\n"
                f"現在日時: {reference_datetime.isoformat(timespec='seconds')}\n"
                "相対日付は現在日時を基準に解決してください。"
                "「次の水曜」「今度の水曜」は基準日より後の直近の水曜、"
                "「来週水曜」は翌週、「再来週水曜」は翌々週（月曜始まり）の水曜を指します。"
            ),
        )
        events = _parse_image_llm_response(response)
        # [D4] テキストパスと同一の正規化を適用
        normalized = [_normalize_event_to_half_width(e) for e in events]
        return _align_event_description_weekdays(normalized)

    try:
        return _invoke_with_retry()
    except Exception as exc:
        raise RuntimeError(f"画像 LLM 抽出失敗: {exc}") from exc

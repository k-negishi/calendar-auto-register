"""日本語の相対日付解決テスト。"""

from datetime import datetime
from zoneinfo import ZoneInfo

from calendar_auto_register.core.relative_dates import (
    format_relative_date_context,
    resolve_relative_dates,
)
from calendar_auto_register.features.llm_extract.usecase_llm_extract import (
    _align_event_description_weekdays,
    _apply_single_relative_date_resolution,
)
from calendar_auto_register.shared.schemas.calendar import GoogleCalendarEventModel


def test_相対日付を基準日時から解決する() -> None:
    reference = datetime(2026, 9, 26, 12, 0, tzinfo=ZoneInfo("Asia/Tokyo"))

    results = resolve_relative_dates(
        "明後日、次の水曜、来週水曜、再来週水曜日に予定",
        reference_datetime=reference,
    )

    assert [(result.phrase, result.resolved_date.isoformat()) for result in results] == [
        ("明後日", "2026-09-28"),
        ("次の水曜", "2026-09-30"),
        ("来週水曜", "2026-09-30"),
        ("再来週水曜日", "2026-10-07"),
    ]


def test_曜日指定の表記ゆれと日数指定を解決する() -> None:
    reference = datetime(2026, 9, 26, 12, 0, tzinfo=ZoneInfo("Asia/Tokyo"))

    results = resolve_relative_dates(
        "今週の水曜日、3日後、３日後、2週間後、明々後日に予定",
        reference_datetime=reference,
    )

    assert [(result.phrase, result.resolved_date.isoformat()) for result in results] == [
        ("今週の水曜日", "2026-09-23"),
        ("3日後", "2026-09-29"),
        ("３日後", "2026-09-29"),
        ("2週間後", "2026-10-10"),
        ("明々後日", "2026-09-29"),
    ]


def test_解決結果をプロンプト用に整形する() -> None:
    reference = datetime(2026, 9, 25, 12, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    resolutions = resolve_relative_dates("来週水曜", reference_datetime=reference)

    result = format_relative_date_context(resolutions)

    assert "来週水曜" in result
    assert "2026-09-30 (水)" in result


def test_未対応の曖昧表現を推測で確定しない() -> None:
    reference = datetime(2026, 9, 26, 12, 0, tzinfo=ZoneInfo("Asia/Tokyo"))

    assert resolve_relative_dates("今週末", reference_datetime=reference) == []


def test_単一イベントの日付を解決済み日付へ補正する() -> None:
    reference = datetime(2026, 9, 25, 12, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    resolutions = resolve_relative_dates("来週水曜", reference_datetime=reference)
    event = GoogleCalendarEventModel(
        summary="歯医者",
        start={"dateTime": "2026-10-01T19:00:00+09:00", "timeZone": "Asia/Tokyo"},
        end={"dateTime": "2026-10-01T19:30:00+09:00", "timeZone": "Asia/Tokyo"},
        description="開催日時: 2026年10月1日(水) 19:00",
    )

    corrected = _apply_single_relative_date_resolution(
        [event], resolutions, "歯医者は来週水曜19時です。"
    )

    assert corrected[0].start.dateTime == "2026-09-30T19:00:00+09:00"
    assert corrected[0].end.dateTime == "2026-09-30T19:30:00+09:00"
    assert corrected[0].description == "開催日時: 2026年9月30日(水) 19:00"


def test_日付語が複合語の一部なら相対日付として扱わない() -> None:
    reference = datetime(2026, 9, 26, 12, 0, tzinfo=ZoneInfo("Asia/Tokyo"))

    assert resolve_relative_dates(
        "明日葉をテーマにしたライブは10月10日19時", reference_datetime=reference
    ) == []


def test_期限文や明示日付のある文を根拠にイベント日を上書きしない() -> None:
    reference = datetime(2026, 9, 26, 12, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    resolutions = resolve_relative_dates(
        "明日までに返信ください。歯医者は10月5日19時です。",
        reference_datetime=reference,
    )
    event = GoogleCalendarEventModel(
        summary="歯医者",
        start={"dateTime": "2026-10-05T19:00:00+09:00", "timeZone": "Asia/Tokyo"},
        end={"dateTime": "2026-10-05T19:30:00+09:00", "timeZone": "Asia/Tokyo"},
    )

    result = _apply_single_relative_date_resolution(
        [event], resolutions, "明日までに返信ください。歯医者は10月5日19時です。"
    )

    assert result[0].start.dateTime == "2026-10-05T19:00:00+09:00"


def test_説明欄の曜日をイベント開始日に揃える() -> None:
    event = GoogleCalendarEventModel(
        summary="歯医者",
        start={"dateTime": "2026-10-01T19:00:00+09:00", "timeZone": "Asia/Tokyo"},
        end={"dateTime": "2026-10-01T20:00:00+09:00", "timeZone": "Asia/Tokyo"},
        description="開催日時: 2026年10月1日(水) 19:00",
    )

    aligned = _align_event_description_weekdays([event])

    assert aligned[0].description == "開催日時: 2026年10月1日(木) 19:00"

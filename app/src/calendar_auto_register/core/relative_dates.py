"""入力本文に含まれる代表的な日本語の相対日付を解決する。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

_WEEKDAYS = {
    "月": 0,
    "火": 1,
    "水": 2,
    "木": 3,
    "金": 4,
    "土": 5,
    "日": 6,
}
_WEEKDAY_PATTERN = r"(?:月|火|水|木|金|土|日)(?:曜(?:日)?)?"
_RELATIVE_DATE_PATTERN = re.compile(
    rf"(?P<relative>明々後日|しあさって|明後日|あさって|明日|あした|今日|本日|"
    rf"(?:(?:再来週|今度|次|来週|今週)(?:の)?{_WEEKDAY_PATTERN})|"
    r"[0-9０-９]+日後|[0-9０-９]+週間後)"
)


@dataclass(frozen=True, slots=True)
class RelativeDateResolution:
    """本文中の日付表現と解決した日付。"""

    phrase: str
    resolved_date: date

    @property
    def weekday_ja(self) -> str:
        return "月火水木金土日"[self.resolved_date.weekday()]

    def as_prompt_line(self) -> str:
        return (
            f"- 「{self.phrase}」= {self.resolved_date.isoformat()} "
            f"({self.weekday_ja})"
        )


def resolve_relative_dates(
    text: str,
    *,
    reference_datetime: datetime,
) -> list[RelativeDateResolution]:
    """相対日付を日本語の週ルールに従って日付へ解決する。

    「次の/今度の曜日」は基準日より後の直近曜日、
    「来週の曜日」は翌週（月曜始まり）、「再来週の曜日」はその次の週の曜日として扱う。
    """
    reference_date = reference_datetime.date()
    resolutions: list[RelativeDateResolution] = []

    for match in _RELATIVE_DATE_PATTERN.finditer(text):
        phrase = match.group("relative")
        resolved = _resolve_phrase(phrase, reference_date)
        if resolved is not None:
            resolutions.append(RelativeDateResolution(phrase, resolved))

    return resolutions


def format_relative_date_context(
    resolutions: list[RelativeDateResolution],
) -> str:
    """LLMへ渡す、アプリ側で確定した相対日付一覧を作る。"""
    if not resolutions:
        return ""

    lines = "\n".join(resolution.as_prompt_line() for resolution in resolutions)
    return (
        "\n\n【アプリ側で解決した相対日付】\n"
        f"{lines}\n"
        "該当する表現は必ずこの日付として扱ってください。"
        "曜日も括弧内の曜日と一致させてください。"
    )


def _resolve_phrase(phrase: str, reference_date: date) -> date | None:
    if phrase in {"今日", "本日"}:
        return reference_date
    if phrase in {"明日", "あした"}:
        return reference_date + timedelta(days=1)
    if phrase in {"明後日", "あさって"}:
        return reference_date + timedelta(days=2)
    if phrase in {"明々後日", "しあさって"}:
        return reference_date + timedelta(days=3)

    days_after = re.fullmatch(r"([0-9０-９]+)日後", phrase)
    if days_after:
        days = _parse_digits(days_after.group(1))
        return reference_date + timedelta(days=days)

    weeks_after = re.fullmatch(r"([0-9０-９]+)週間後", phrase)
    if weeks_after:
        weeks = _parse_digits(weeks_after.group(1))
        return reference_date + timedelta(weeks=weeks)

    match = re.fullmatch(
        rf"(?P<scope>再来週|今度|次|来週|今週)(?:の)?(?P<weekday>{_WEEKDAY_PATTERN})",
        phrase,
    )
    if not match:
        return None

    weekday_text = match.group("weekday")
    target_weekday = _WEEKDAYS[weekday_text[0]]
    scope = match.group("scope")

    if scope in {"次", "今度"}:
        days_ahead = (target_weekday - reference_date.weekday()) % 7
        return reference_date + timedelta(days=days_ahead or 7)

    monday = reference_date - timedelta(days=reference_date.weekday())
    if scope == "来週":
        monday += timedelta(days=7)
    elif scope == "再来週":
        monday += timedelta(days=14)
    return monday + timedelta(days=target_weekday)


def _parse_digits(value: str) -> int:
    """ASCII数字と全角数字を整数にする。"""
    normalized = "".join(
        chr(ord(char) - 0xFEE0) if "０" <= char <= "９" else char
        for char in value
    )
    return int(normalized)

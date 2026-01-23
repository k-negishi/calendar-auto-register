"""Google Calendar SDK を扱うヘルパー。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from calendar_auto_register.core.settings import Settings

if TYPE_CHECKING:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import Resource

GOOGLE_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"


def build_credentials_from_service_account(
    *,
    raw_credentials: str,
    scopes: Sequence[str] | None = None,
) -> Credentials:
    """Service Account を利用して Google API 認証情報を構築する。"""

    from google.oauth2.service_account import Credentials

    scopes = list(scopes or [GOOGLE_CALENDAR_SCOPE])
    raw_credentials = raw_credentials.strip()

    if raw_credentials.startswith("{"):
        info = json.loads(raw_credentials)
        return Credentials.from_service_account_info(info, scopes=scopes)

    path = Path(raw_credentials).expanduser()
    if not path.exists():
        raise ValueError("GOOGLE_CREDENTIALS に指定されたファイルが見つかりません。")

    return Credentials.from_service_account_file(path, scopes=scopes)


def build_calendar_service(*, credentials: Credentials) -> Resource:
    """google-api-python-client の Calendar Service を生成する。"""

    from googleapiclient.discovery import build

    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def service_from_settings(settings: Settings) -> Resource:
    """Settings から必要情報を取り出して Calendar Service を生成する。"""

    if not settings.google_credentials:
        raise ValueError("GOOGLE_CREDENTIALS が未設定です。")

    credentials = build_credentials_from_service_account(
        raw_credentials=settings.google_credentials,
    )
    return build_calendar_service(credentials=credentials)

"""Google Calendar SDK を扱うヘルパー。"""

from __future__ import annotations

from typing import Sequence

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build

from calendar_auto_register.core.settings import Settings

GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"


def build_credentials(
    *,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    scopes: Sequence[str] | None = None,
) -> Credentials:
    """Refresh Token を利用して Google API 認証情報を構築する。"""

    scopes = list(scopes or [GOOGLE_CALENDAR_SCOPE])
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri=GOOGLE_TOKEN_URI,
        scopes=scopes,
    )


def build_calendar_service(*, credentials: Credentials) -> Resource:
    """google-api-python-client の Calendar Service を生成する。"""

    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def service_from_settings(settings: Settings) -> Resource:
    """Settings から必要情報を取り出して Calendar Service を生成する。"""

    if not (
        settings.google_client_id
        and settings.google_client_secret
        and settings.google_refresh_token
    ):
        raise ValueError("Google API 用のクライアント資格情報が不足しています。")

    credentials = build_credentials(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        refresh_token=settings.google_refresh_token,
    )
    return build_calendar_service(credentials=credentials)

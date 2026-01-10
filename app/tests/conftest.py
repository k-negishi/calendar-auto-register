from __future__ import annotations

import os

os.environ.setdefault("CALENDAR_ID", "primary")
os.environ.setdefault("GOOGLE_CREDENTIALS", "dummy")
os.environ.setdefault("LINE_CHANNEL_ACCESS_TOKEN", "dummy")
os.environ.setdefault("LINE_USER_ID", "dummy")
os.environ.setdefault("S3_RAW_MAIL_BUCKET", "calendar-auto-register")

import pytest

from calendar_auto_register.core import settings as core_settings


@pytest.fixture(autouse=True)
def basic_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """アプリ初期化に必要な環境変数をテスト時にセットする。"""

    monkeypatch.setenv("CALENDAR_ID", "primary")
    monkeypatch.setenv("GOOGLE_CREDENTIALS", "dummy")
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "dummy")
    monkeypatch.setenv("LINE_USER_ID", "dummy")
    monkeypatch.setenv("S3_RAW_MAIL_BUCKET", "calendar-auto-register")
    monkeypatch.delenv("APP_ENV", raising=False)
    core_settings.load_settings.cache_clear()

from __future__ import annotations

import os

os.environ.setdefault("GCAL_CALENDAR_ID", "primary")
os.environ.setdefault("S3_RAW_MAIL_BUCKET", "calendar-auto-register")

import pytest

from calendar_auto_register.core import settings as core_settings


@pytest.fixture(autouse=True)
def basic_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """アプリ初期化に必要な環境変数をテスト時にセットする。"""

    monkeypatch.setenv("GCAL_CALENDAR_ID", "primary")
    monkeypatch.setenv("S3_RAW_MAIL_BUCKET", "calendar-auto-register")
    monkeypatch.delenv("APP_ENV", raising=False)
    core_settings.load_settings.cache_clear()

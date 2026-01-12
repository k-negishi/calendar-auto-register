"""API キー認証ミドルウェアのテスト。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from calendar_auto_register.app import create_app
from calendar_auto_register.core.settings import load_settings


# テスト実行前に環境変数をセット
@pytest.fixture(scope="session", autouse=True)
def setup_env() -> None:
    """テスト用の環境変数をセット。.env.localから読み込む。"""
    env_path = Path(__file__).parent.parent.parent.parent.parent / ".env.local"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        # .env.localが無い場合はデフォルト値を設定
        os.environ.setdefault("APP_ENV", "local")
        os.environ.setdefault("REGION", "ap-northeast-1")
        os.environ.setdefault("CALENDAR_ID", "test-calendar-id")
        os.environ.setdefault("GOOGLE_CREDENTIALS", "dummy")
        os.environ.setdefault("ALLOWLIST_SENDERS", "[]")
        os.environ.setdefault("S3_RAW_MAIL_BUCKET", "test-bucket")

    # キャッシュをクリア
    load_settings.cache_clear()


class TestApiKeyAuthenticationLocal:
    """ローカル環境（APP_ENV=local）でのテスト - 認証スキップ"""

    def test_local_env_no_auth_required_healthz(self) -> None:
        """ローカル環境では Authorization ヘッダーなしでアクセス可能。"""
        os.environ["APP_ENV"] = "local"
        load_settings.cache_clear()

        app = create_app()
        client = TestClient(app)

        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["env"] == "local"



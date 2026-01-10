"""API キー認証ミドルウェアのテスト。"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

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


class TestApiKeyAuthenticationProd:
    """本番環境（APP_ENV=prod）でのテスト - 認証必須"""

    @patch("calendar_auto_register.core.settings._load_dotenv_from_ssm")
    def test_prod_env_no_auth_header_returns_401(
        self, mock_load_ssm: MagicMock
    ) -> None:
        """本番環境では Authorization ヘッダーなしの場合 401を返す。"""
        os.environ["APP_ENV"] = "prod"
        os.environ["API_KEY"] = "test-api-key-12345"
        load_settings.cache_clear()

        app = create_app()
        client = TestClient(app)

        response = client.get("/healthz")
        assert response.status_code == 401
        assert "detail" in response.json()

    @patch("calendar_auto_register.core.settings._load_dotenv_from_ssm")
    def test_prod_env_invalid_auth_header_format_returns_401(
        self, mock_load_ssm: MagicMock
    ) -> None:
        """本番環境では Bearer フォーマット以外の Authorization ヘッダーは 401を返す。"""
        os.environ["APP_ENV"] = "prod"
        os.environ["API_KEY"] = "test-api-key-12345"
        load_settings.cache_clear()

        app = create_app()
        client = TestClient(app)

        response = client.get("/healthz", headers={"Authorization": "Basic xyz"})
        assert response.status_code == 401

    @patch("calendar_auto_register.core.settings._load_dotenv_from_ssm")
    def test_prod_env_wrong_api_key_returns_401(
        self, mock_load_ssm: MagicMock
    ) -> None:
        """本番環境では間違ったAPI キーの場合 401を返す。"""
        os.environ["APP_ENV"] = "prod"
        os.environ["API_KEY"] = "correct-api-key-12345"
        load_settings.cache_clear()

        app = create_app()
        client = TestClient(app)

        response = client.get(
            "/healthz", headers={"Authorization": "Bearer wrong-api-key"}
        )
        assert response.status_code == 401

    @patch("calendar_auto_register.core.settings._load_dotenv_from_ssm")
    def test_prod_env_correct_api_key_returns_200(
        self, mock_load_ssm: MagicMock
    ) -> None:
        """本番環境では正しいAPI キーでアクセス可能。"""
        os.environ["APP_ENV"] = "prod"
        os.environ["API_KEY"] = "correct-api-key-12345"
        load_settings.cache_clear()

        app = create_app()
        client = TestClient(app)

        response = client.get(
            "/healthz", headers={"Authorization": "Bearer correct-api-key-12345"}
        )
        assert response.status_code == 200
        assert response.json()["env"] == "prod"

    @patch("calendar_auto_register.core.settings._load_dotenv_from_ssm")
    def test_prod_env_api_key_with_spaces_stripped(
        self, mock_load_ssm: MagicMock
    ) -> None:
        """本番環境では API キーの前後の空白はストリップされる。"""
        os.environ["APP_ENV"] = "prod"
        os.environ["API_KEY"] = "test-api-key-with-spaces"
        load_settings.cache_clear()

        app = create_app()
        client = TestClient(app)

        # スペース付きで送信
        response = client.get(
            "/healthz", headers={"Authorization": "Bearer  test-api-key-with-spaces  "}
        )
        assert response.status_code == 200

    @patch("calendar_auto_register.core.settings._load_dotenv_from_ssm")
    def test_prod_env_no_api_key_in_settings_returns_401(
        self, mock_load_ssm: MagicMock
    ) -> None:
        """本番環境で API_KEY が設定されていない場合 401を返す。"""
        os.environ["APP_ENV"] = "prod"
        # API_KEY を削除
        if "API_KEY" in os.environ:
            del os.environ["API_KEY"]
        load_settings.cache_clear()

        app = create_app()
        client = TestClient(app)

        response = client.get(
            "/healthz", headers={"Authorization": "Bearer some-key"}
        )
        assert response.status_code == 401

    @patch("calendar_auto_register.core.settings._load_dotenv_from_ssm")
    def test_prod_env_auth_header_case_insensitive(
        self, mock_load_ssm: MagicMock
    ) -> None:
        """本番環境では Authorization ヘッダー名の大文字小文字は区別されない。"""
        os.environ["APP_ENV"] = "prod"
        os.environ["API_KEY"] = "test-api-key-12345"
        load_settings.cache_clear()

        app = create_app()
        client = TestClient(app)

        # 小文字で送信
        response = client.get(
            "/healthz",
            headers={"authorization": "Bearer test-api-key-12345"},
        )
        assert response.status_code == 200

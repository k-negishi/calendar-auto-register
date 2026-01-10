"""LLM 予定抽出エンドポイントのテスト。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from calendar_auto_register.app import create_app
from calendar_auto_register.core.settings import load_settings


def _create_mock_response(text: str) -> MagicMock:
    """LangChain response をモック"""
    mock_response = MagicMock()
    mock_response.content = text
    return mock_response


# テスト実行前に環境変数をセット
@pytest.fixture(scope="session", autouse=True)
def setup_env() -> None:
    """テスト用の環境変数をセット。.env.localから読み込む。"""
    # プロジェクトルートの.env.localを読み込む
    env_path = Path(__file__).parent.parent.parent.parent.parent.parent.parent / ".env.local"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        # .env.localが無い場合はデフォルト値を設定
        os.environ.setdefault("APP_ENV", "local")
        os.environ.setdefault("REGION", "ap-northeast-1")
        os.environ.setdefault("CALENDAR_ID", "test-calendar-id")
        os.environ.setdefault("GOOGLE_CREDENTIALS", "dummy")
        os.environ.setdefault("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20240620-v1:0")
        os.environ.setdefault("ALLOWLIST_SENDERS", "[]")
        os.environ.setdefault("S3_RAW_MAIL_BUCKET", "test-bucket")

    # キャッシュをクリア
    load_settings.cache_clear()


def test_正常な予定を抽出できる() -> None:
    """メール本文から予定情報を正常に抽出できることを検証する。"""

    response_text = json.dumps({
        "events": [
            {
                "summary": "営業会議",
                "start": {
                    "dateTime": "2024-12-25T14:00:00+09:00",
                    "timeZone": "Asia/Tokyo",
                },
                "end": {
                    "dateTime": "2024-12-25T15:00:00+09:00",
                    "timeZone": "Asia/Tokyo",
                },
                "location": "オンライン",
                "description": None
            }
        ]
    })

    with patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.ChatBedrock"
    ) as mock_chat_class:
        mock_chat_instance = MagicMock()
        mock_chat_class.return_value = mock_chat_instance
        mock_chat_instance.invoke.return_value = _create_mock_response(response_text)

        client = TestClient(create_app())
        payload = {
            "normalized_mail": {
                "from_addr": "alice@example.com",
                "reply_to": None,
                "subject": "12月25日の会議について",
                "received_at": "2024-12-20T10:00:00Z",
                "text": "営業会議を12月25日14:00から15:00で開催します。",
                "html": None,
                "attachments": [],
            }
        }

        res = client.post("/llm/extract-event", json=payload)

        assert res.status_code == 200
        data = res.json()
        assert len(data["events"]) == 1
        assert data["events"][0]["summary"] == "営業会議"
        assert data["events"][0]["location"] == "オンライン"
        assert "start" in data["events"][0]
        assert "end" in data["events"][0]


def test_複数の予定を抽出できる() -> None:
    """複数の予定が含まれるメールから全て抽出できることを検証する。"""

    response_text = json.dumps({
        "events": [
            {
                "summary": "朝礼",
                "start": {
                    "dateTime": "2024-12-25T09:00:00+09:00",
                    "timeZone": "Asia/Tokyo",
                },
                "end": {
                    "dateTime": "2024-12-25T09:30:00+09:00",
                    "timeZone": "Asia/Tokyo",
                },
                "location": None,
                "description": None
            },
            {
                "summary": "営業会議",
                "start": {
                    "dateTime": "2024-12-25T14:00:00+09:00",
                    "timeZone": "Asia/Tokyo",
                },
                "end": {
                    "dateTime": "2024-12-25T15:00:00+09:00",
                    "timeZone": "Asia/Tokyo",
                },
                "location": "オンライン",
                "description": "四半期決算について"
            },
        ]
    })

    with patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.ChatBedrock"
    ) as mock_chat_class:
        mock_chat_instance = MagicMock()
        mock_chat_class.return_value = mock_chat_instance
        mock_chat_instance.invoke.return_value = _create_mock_response(response_text)

        client = TestClient(create_app())
        payload = {
            "normalized_mail": {
                "from_addr": "alice@example.com",
                "reply_to": None,
                "subject": "複数の予定",
                "received_at": "2024-12-20T10:00:00Z",
                "text": "明日は朝礼9:00と営業会議14:00があります。",
                "html": None,
                "attachments": [],
            }
        }

        res = client.post("/llm/extract-event", json=payload)

        assert res.status_code == 200
        data = res.json()
        assert len(data["events"]) == 2
        assert data["events"][0]["summary"] == "朝礼"
        assert data["events"][1]["summary"] == "営業会議"
        assert data["events"][1]["location"] == "オンライン"


def test_予定がない場合は空配列を返す() -> None:
    """予定が抽出されない場合、空配列を返すことを検証する。"""

    response_text = json.dumps({"events": []})

    with patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.ChatBedrock"
    ) as mock_chat_class:
        mock_chat_instance = MagicMock()
        mock_chat_class.return_value = mock_chat_instance
        mock_chat_instance.invoke.return_value = _create_mock_response(response_text)

        client = TestClient(create_app())
        payload = {
            "normalized_mail": {
                "from_addr": "alice@example.com",
                "reply_to": None,
                "subject": "雑談メール",
                "received_at": "2024-12-20T10:00:00Z",
                "text": "最近どうですか？",
                "html": None,
                "attachments": [],
            }
        }

        res = client.post("/llm/extract-event", json=payload)

        assert res.status_code == 200
        data = res.json()
        assert len(data["events"]) == 0


def test_LLMが無効なJSONを返した場合は400エラー() -> None:
    """LLM が無効な JSON を返した場合、400 エラーになることを検証する。"""

    response_text = "This is not valid JSON {invalid}"

    with patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.ChatBedrock"
    ) as mock_chat_class:
        mock_chat_instance = MagicMock()
        mock_chat_class.return_value = mock_chat_instance
        mock_chat_instance.invoke.return_value = _create_mock_response(response_text)

        client = TestClient(create_app())
        payload = {
            "normalized_mail": {
                "from_addr": "alice@example.com",
                "reply_to": None,
                "subject": "テスト",
                "received_at": "2024-12-20T10:00:00Z",
                "text": "テスト",
                "html": None,
                "attachments": [],
            }
        }

        res = client.post("/llm/extract-event", json=payload)

        assert res.status_code == 400


def test_LLMが必須フィールドを欠いた場合は400エラー() -> None:
    """LLM が必須フィールド（summary）を省略した場合、400 エラーになることを検証する。"""

    response_text = json.dumps({
        "events": [
            {
                "start": {
                    "dateTime": "2024-12-25T14:00:00+09:00",
                    "timeZone": "Asia/Tokyo",
                },
                "end": {
                    "dateTime": "2024-12-25T15:00:00+09:00",
                    "timeZone": "Asia/Tokyo",
                },
            }
        ]
    })

    with patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.ChatBedrock"
    ) as mock_chat_class:
        mock_chat_instance = MagicMock()
        mock_chat_class.return_value = mock_chat_instance
        mock_chat_instance.invoke.return_value = _create_mock_response(response_text)

        client = TestClient(create_app())
        payload = {
            "normalized_mail": {
                "from_addr": "alice@example.com",
                "reply_to": None,
                "subject": "テスト",
                "received_at": "2024-12-20T10:00:00Z",
                "text": "テスト",
                "html": None,
                "attachments": [],
            }
        }

        res = client.post("/llm/extract-event", json=payload)

        assert res.status_code == 400


def test_LLMエラーは500エラーになる() -> None:
    """LLM API エラーが 500 エラーになることを検証する。"""

    with patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.ChatBedrock"
    ) as mock_chat_class:
        mock_chat_instance = MagicMock()
        mock_chat_class.return_value = mock_chat_instance
        # API エラーをシミュレート
        mock_chat_instance.invoke.side_effect = RuntimeError("Bedrock API is unavailable")

        client = TestClient(create_app())
        payload = {
            "normalized_mail": {
                "from_addr": "alice@example.com",
                "reply_to": None,
                "subject": "テスト",
                "received_at": "2024-12-20T10:00:00Z",
                "text": "テスト",
                "html": None,
                "attachments": [],
            }
        }

        res = client.post("/llm/extract-event", json=payload)

        assert res.status_code == 500


def test_入力に不要なフィールドがある場合は拒否() -> None:
    """リクエストに予期しないフィールドがある場合、Pydantic により拒否されることを検証する。"""

    client = TestClient(create_app())
    payload = {
        "normalized_mail": {
            "from_addr": "alice@example.com",
            "reply_to": None,
            "subject": "テスト",
            "received_at": "2024-12-20T10:00:00Z",
            "text": "テスト",
            "html": None,
            "attachments": [],
            "unknown_field": "should_be_rejected",
        }
    }

    res = client.post("/llm/extract-event", json=payload)

    assert res.status_code == 422  # Pydantic validation error


def test_Google_Calendar形式を検証() -> None:
    """抽出されたイベントがGoogle Calendar API互換形式であることを検証する。"""

    response_text = json.dumps({
        "events": [
            {
                "summary": "診察 - 内科",
                "start": {
                    "dateTime": "2024-12-25T14:00:00+09:00",
                    "timeZone": "Asia/Tokyo",
                },
                "end": {
                    "dateTime": "2024-12-25T14:30:00+09:00",
                    "timeZone": "Asia/Tokyo",
                },
                "location": "太郎クリニック",
                "description": "患者名: 山田太郎\n症状: 風邪"
            }
        ]
    })

    with patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.ChatBedrock"
    ) as mock_chat_class:
        mock_chat_instance = MagicMock()
        mock_chat_class.return_value = mock_chat_instance
        mock_chat_instance.invoke.return_value = _create_mock_response(response_text)

        client = TestClient(create_app())
        payload = {
            "normalized_mail": {
                "from_addr": "alice@example.com",
                "reply_to": None,
                "subject": "医者予約",
                "received_at": "2024-12-20T10:00:00Z",
                "text": "12月25日14:00に内科の診察を予約しました。",
                "html": None,
                "attachments": [],
            }
        }

        res = client.post("/llm/extract-event", json=payload)

        assert res.status_code == 200
        data = res.json()
        event = data["events"][0]

        # Google Calendar API形式の検証
        assert "summary" in event
        assert "start" in event
        assert "end" in event
        assert "dateTime" in event["start"]
        assert "timeZone" in event["start"]
        assert "dateTime" in event["end"]
        assert "timeZone" in event["end"]
        assert event["start"]["timeZone"] == "Asia/Tokyo"

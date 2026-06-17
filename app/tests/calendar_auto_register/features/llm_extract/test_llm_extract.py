"""LLM 予定抽出エンドポイントのテスト。

[D9] POST /llm/extract-event は text 必須 + メールコンテキスト任意のフラット構造。
- text のみ → extract_events_from_raw_text()（LINE テキストパス）
- text + from_addr 等 → extract_events()（メールパス、HTML 前処理あり）
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
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


def _mock_bedrock_chain(response_dict: dict[str, Any]) -> MagicMock:
    """LangChain チェーン (chat | output_parser).with_retry() をモック"""
    mock_chat_instance = MagicMock()
    mock_chat_instance.__or__ = MagicMock()
    mock_pipe_output = MagicMock()
    mock_pipe_output.with_retry = MagicMock(return_value=MagicMock(
        invoke=MagicMock(return_value=response_dict)
    ))
    mock_chat_instance.__or__.return_value = mock_pipe_output
    return mock_chat_instance


def _mock_bedrock_chain_with_exception(exc: Exception) -> MagicMock:
    """LangChain チェーン (chat | output_parser).with_retry() をモック（例外発生版）"""
    mock_chat_instance = MagicMock()
    mock_chat_instance.__or__ = MagicMock()
    mock_pipe_output = MagicMock()
    mock_pipe_output.with_retry = MagicMock(return_value=MagicMock(
        invoke=MagicMock(side_effect=exc)
    ))
    mock_chat_instance.__or__.return_value = mock_pipe_output
    return mock_chat_instance


# テスト実行前に環境変数をセット
@pytest.fixture(scope="session", autouse=True)
def setup_env() -> None:
    """テスト用の環境変数をセット。.env.localから読み込む。"""
    env_path = Path(__file__).parent.parent.parent.parent.parent.parent.parent / ".env.local"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        os.environ.setdefault("APP_ENV", "local")
        os.environ.setdefault("REGION", "ap-northeast-1")
        os.environ.setdefault("CALENDAR_ID", "test-calendar-id")
        os.environ.setdefault("GOOGLE_CREDENTIALS", "dummy")
        os.environ.setdefault("BEDROCK_MODEL_ID", "test-bedrock-model")
        os.environ.setdefault("ALLOWLIST_SENDERS", "[]")
        os.environ.setdefault("S3_RAW_MAIL_BUCKET", "test-bucket")

    load_settings.cache_clear()


# ===== メールパス テスト（text + メールコンテキスト） =====

def _mail_payload(**overrides: Any) -> dict:
    """メールコンテキスト付きのテスト用ペイロードを生成するヘルパー。"""
    base = {
        "text": "営業会議を12月25日14:00から15:00で開催します。",
        "from_addr": "alice@example.com",
        "reply_to": None,
        "subject": "12月25日の会議について",
        "received_at": "2024-12-20T10:00:00Z",
        "html": None,
    }
    base.update(overrides)
    return base


def test_正常な予定を抽出できる() -> None:
    """メール本文から予定情報を正常に抽出できることを検証する。"""
    response_text = json.dumps({
        "events": [
            {
                "summary": "営業会議",
                "start": {"dateTime": "2024-12-25T14:00:00+09:00", "timeZone": "Asia/Tokyo"},
                "end": {"dateTime": "2024-12-25T15:00:00+09:00", "timeZone": "Asia/Tokyo"},
                "location": "オンライン",
                "description": None,
            }
        ]
    })

    with patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.ChatBedrock"
    ) as mock_chat_class, patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.boto3.client"
    ) as mock_boto_client:
        mock_chat_instance = MagicMock()
        mock_chat_class.return_value = mock_chat_instance
        mock_boto_client.return_value = MagicMock()

        mock_chat_instance.__or__ = MagicMock()
        mock_pipe_output = MagicMock()
        mock_pipe_output.with_retry = MagicMock(return_value=MagicMock(
            invoke=MagicMock(return_value=json.loads(response_text))
        ))
        mock_chat_instance.__or__.return_value = mock_pipe_output

        client = TestClient(create_app())
        res = client.post("/llm/extract-event", json=_mail_payload())

        assert res.status_code == 200
        data = res.json()
        assert len(data["events"]) == 1
        assert data["events"][0]["summary"] == "営業会議"
        assert data["events"][0]["location"] == "オンライン"
        assert "start" in data["events"][0]
        assert "end" in data["events"][0]


def test_複数の予定を抽出できる() -> None:
    """複数の予定が含まれるメールから全て抽出できることを検証する。"""
    response_dict = {
        "events": [
            {
                "summary": "朝礼",
                "start": {"dateTime": "2024-12-25T09:00:00+09:00", "timeZone": "Asia/Tokyo"},
                "end": {"dateTime": "2024-12-25T09:30:00+09:00", "timeZone": "Asia/Tokyo"},
                "location": None,
                "description": None,
            },
            {
                "summary": "営業会議",
                "start": {"dateTime": "2024-12-25T14:00:00+09:00", "timeZone": "Asia/Tokyo"},
                "end": {"dateTime": "2024-12-25T15:00:00+09:00", "timeZone": "Asia/Tokyo"},
                "location": "オンライン",
                "description": "四半期決算について",
            },
        ]
    }

    with patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.ChatBedrock"
    ) as mock_chat_class, patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.boto3.client"
    ) as mock_boto_client:
        mock_chat_instance = _mock_bedrock_chain(response_dict)
        mock_chat_class.return_value = mock_chat_instance
        mock_boto_client.return_value = MagicMock()

        client = TestClient(create_app())
        res = client.post(
            "/llm/extract-event",
            json=_mail_payload(text="明日は朝礼9:00と営業会議14:00があります。"),
        )

        assert res.status_code == 200
        data = res.json()
        assert len(data["events"]) == 2
        assert data["events"][0]["summary"] == "朝礼"
        assert data["events"][1]["summary"] == "営業会議"
        assert data["events"][1]["location"] == "オンライン"


def test_予定がない場合は空配列を返す() -> None:
    """予定が抽出されない場合、空配列を返すことを検証する。"""
    response_dict = {"events": []}

    with patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.ChatBedrock"
    ) as mock_chat_class, patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.boto3.client"
    ) as mock_boto_client:
        mock_chat_instance = _mock_bedrock_chain(response_dict)
        mock_chat_class.return_value = mock_chat_instance
        mock_boto_client.return_value = MagicMock()

        client = TestClient(create_app())
        res = client.post(
            "/llm/extract-event",
            json=_mail_payload(text="最近どうですか？", subject="雑談メール"),
        )

        assert res.status_code == 200
        assert len(res.json()["events"]) == 0


def test_LLMが無効なJSONを返した場合は400エラー() -> None:
    """LLM が無効な JSON を返した場合、400 エラーになることを検証する。"""
    with patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.ChatBedrock"
    ) as mock_chat_class, patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.boto3.client"
    ) as mock_boto_client:
        mock_chat_instance = _mock_bedrock_chain_with_exception(
            ValueError("Invalid JSON format")
        )
        mock_chat_class.return_value = mock_chat_instance
        mock_boto_client.return_value = MagicMock()

        client = TestClient(create_app())
        res = client.post("/llm/extract-event", json=_mail_payload())

        assert res.status_code == 400


def test_LLMが必須フィールドを欠いた場合は400エラー() -> None:
    """LLM が必須フィールド（summary）を省略した場合、400 エラーになることを検証する。"""
    with patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.ChatBedrock"
    ) as mock_chat_class, patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.boto3.client"
    ) as mock_boto_client:
        mock_chat_instance = _mock_bedrock_chain_with_exception(
            ValueError("Missing required field: summary")
        )
        mock_chat_class.return_value = mock_chat_instance
        mock_boto_client.return_value = MagicMock()

        client = TestClient(create_app())
        res = client.post("/llm/extract-event", json=_mail_payload())

        assert res.status_code == 400


def test_LLMエラーは500エラーになる() -> None:
    """LLM API エラーが 500 エラーになることを検証する。"""
    with patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.ChatBedrock"
    ) as mock_chat_class, patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.boto3.client"
    ) as mock_boto_client:
        mock_chat_instance = _mock_bedrock_chain_with_exception(
            RuntimeError("Bedrock API is unavailable")
        )
        mock_chat_class.return_value = mock_chat_instance
        mock_boto_client.return_value = MagicMock()

        client = TestClient(create_app())
        res = client.post("/llm/extract-event", json=_mail_payload())

        assert res.status_code == 500


def test_入力に不要なフィールドがある場合は拒否() -> None:
    """リクエストに予期しないフィールドがある場合、Pydantic により拒否されることを検証する。"""
    client = TestClient(create_app())
    payload = {
        "text": "テスト",
        "from_addr": "alice@example.com",
        "unknown_field": "should_be_rejected",  # extra="forbid" により拒否される
    }

    res = client.post("/llm/extract-event", json=payload)

    assert res.status_code == 422  # Pydantic validation error


def test_Google_Calendar形式を検証() -> None:
    """抽出されたイベントがGoogle Calendar API互換形式であることを検証する。"""
    response_dict = {
        "events": [
            {
                "summary": "診察 - 内科",
                "start": {"dateTime": "2024-12-25T14:00:00+09:00", "timeZone": "Asia/Tokyo"},
                "end": {"dateTime": "2024-12-25T14:30:00+09:00", "timeZone": "Asia/Tokyo"},
                "location": "太郎クリニック",
                "description": "患者名: 山田太郎\n症状: 風邪",
            }
        ]
    }

    with patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.ChatBedrock"
    ) as mock_chat_class, patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.boto3.client"
    ) as mock_boto_client:
        mock_chat_instance = _mock_bedrock_chain(response_dict)
        mock_chat_class.return_value = mock_chat_instance
        mock_boto_client.return_value = MagicMock()

        client = TestClient(create_app())
        res = client.post(
            "/llm/extract-event",
            json=_mail_payload(
                text="12月25日14:00に内科の診察を予約しました。",
                subject="医者予約",
            ),
        )

        assert res.status_code == 200
        data = res.json()
        event = data["events"][0]

        assert "summary" in event
        assert "start" in event
        assert "end" in event
        assert "dateTime" in event["start"]
        assert "timeZone" in event["start"]
        assert "dateTime" in event["end"]
        assert "timeZone" in event["end"]
        assert event["start"]["timeZone"] == "Asia/Tokyo"


def test_支払い期限イベントを抽出できる() -> None:
    """支払い期限イベントを dateTime 形式で抽出できることを検証する。"""
    response_dict = {
        "events": [
            {
                "summary": "コンサート@サンプルアリーナ東京",
                "start": {"dateTime": "2026-04-03T19:00:00+09:00", "timeZone": "Asia/Tokyo"},
                "end": {"dateTime": "2026-04-03T22:00:00+09:00", "timeZone": "Asia/Tokyo"},
                "location": "サンプルアリーナ東京",
                "description": "コンサートイベント",
            },
            {
                "summary": "支払い期限 23:59@コンサート@サンプルアリーナ東京",
                "start": {"dateTime": "2025-12-30T20:00:00+09:00", "timeZone": "Asia/Tokyo"},
                "end": {"dateTime": "2025-12-30T23:59:00+09:00", "timeZone": "Asia/Tokyo"},
                "description": "支払い期限: 2025年12月30日 23:59\n支払い方法: コンビニ支払い\n払込票番号: 1234-5678-9012\n合計金額: ¥5,000",
            },
        ]
    }

    with patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.ChatBedrock"
    ) as mock_chat_class, patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.boto3.client"
    ) as mock_boto_client:
        mock_chat_instance = _mock_bedrock_chain(response_dict)
        mock_chat_class.return_value = mock_chat_instance
        mock_boto_client.return_value = MagicMock()

        client = TestClient(create_app())
        res = client.post(
            "/llm/extract-event",
            json=_mail_payload(
                text="コンサートに当選しました。支払い期限は12月30日23:59までです。",
                from_addr="ticket@example.com",
                subject="チケット当選のお知らせ",
                received_at="2025-12-27T09:00:00Z",
            ),
        )

        assert res.status_code == 200
        data = res.json()
        assert len(data["events"]) == 2

        main_event = data["events"][0]
        assert main_event["summary"] == "コンサート@サンプルアリーナ東京"
        assert "dateTime" in main_event["start"]
        assert "timeZone" in main_event["start"]

        payment_event = data["events"][1]
        assert payment_event["summary"] == "支払い期限 23:59@コンサート@サンプルアリーナ東京"
        assert payment_event["start"]["dateTime"] == "2025-12-30T20:00:00+09:00"
        assert payment_event["end"]["dateTime"] == "2025-12-30T23:59:00+09:00"
        assert payment_event.get("location") is None


def test_全角文字を半角に正規化できる() -> None:
    """LLM が返した全角英数字・記号を半角に正規化できることを検証する。"""
    response_dict = {
        "events": [
            {
                "summary": "Ｚｅｐｐ　ＤｉｖｅｒＣｉｔｙ（ＴＯＫＹＯ）",
                "start": {"dateTime": "2026-04-03T19:00:00+09:00", "timeZone": "Asia/Tokyo"},
                "end": {"dateTime": "2026-04-03T22:00:00+09:00", "timeZone": "Asia/Tokyo"},
                "location": "Ｚｅｐｐ　ＤｉｖｅｒＣｉｔｙ（ＴＯＫＹＯ） (東京都)",
                "description": "料金：４，５００円\n座席：１Ｆスタンディング",
            }
        ]
    }

    with patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.ChatBedrock"
    ) as mock_chat_class, patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.boto3.client"
    ) as mock_boto_client:
        mock_chat_instance = _mock_bedrock_chain(response_dict)
        mock_chat_class.return_value = mock_chat_instance
        mock_boto_client.return_value = MagicMock()

        client = TestClient(create_app())
        res = client.post(
            "/llm/extract-event",
            json=_mail_payload(
                text="Zepp DiverCity(TOKYO)でのライブイベント",
                from_addr="ticket@example.com",
                subject="チケット当選のお知らせ",
                received_at="2026-01-10T17:40:00Z",
            ),
        )

        assert res.status_code == 200
        data = res.json()
        event = data["events"][0]

        assert event["summary"] == "Zepp DiverCity(TOKYO)", \
            f"Expected 'Zepp DiverCity(TOKYO)' but got '{event['summary']}'"
        assert event["location"] == "Zepp DiverCity(TOKYO) (東京都)", \
            f"Expected 'Zepp DiverCity(TOKYO) (東京都)' but got '{event['location']}'"
        assert "4,500円" in event["description"], \
            f"Description should contain '4,500円' but got '{event['description']}'"
        assert "1Fスタンディング" in event["description"], \
            f"Description should contain '1Fスタンディング' but got '{event['description']}'"


# ===== extract_events_from_raw_text テスト（Phase 4b: D3, D7） =====

def test_extract_events_from_raw_text_関数が存在する() -> None:
    """extract_events_from_raw_text() 関数が存在することを確認する。"""
    from calendar_auto_register.features.llm_extract.usecase_llm_extract import (
        extract_events_from_raw_text,  # noqa: F401
    )


def test_extract_events_from_raw_text_NormalizedMailを経由せずに呼べる() -> None:
    """NormalizedMail を経由せずに raw text から呼べることを確認する。"""
    from calendar_auto_register.core.settings import load_settings
    from calendar_auto_register.features.llm_extract.usecase_llm_extract import (
        extract_events_from_raw_text,
    )

    response_dict = {
        "events": [
            {
                "summary": "朝礼",
                "start": {"dateTime": "2024-12-25T09:00:00+09:00", "timeZone": "Asia/Tokyo"},
                "end": {"dateTime": "2024-12-25T09:30:00+09:00", "timeZone": "Asia/Tokyo"},
                "location": None,
                "description": None,
            }
        ]
    }

    with patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.ChatBedrock"
    ) as mock_chat_class, patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.boto3.client"
    ) as mock_boto_client:
        mock_chat_instance = _mock_bedrock_chain(response_dict)
        mock_chat_class.return_value = mock_chat_instance
        mock_boto_client.return_value = MagicMock()

        os.environ.setdefault("BEDROCK_MODEL_ID", "test-model")
        load_settings.cache_clear()
        settings = load_settings()

        result = extract_events_from_raw_text("朝礼の予定があります", settings=settings)

    assert len(result) == 1
    assert result[0].summary == "朝礼"


def test_extract_events_from_raw_text_Unsubscribeが含まれても処理される() -> None:
    """テキストに 'Unsubscribe' が含まれても、除去せずにそのまま処理されることを確認する。

    メール前処理 (_preprocess_mail_body) は適用しない設計 (D3)。
    """
    from calendar_auto_register.core.settings import load_settings
    from calendar_auto_register.features.llm_extract.usecase_llm_extract import (
        extract_events_from_raw_text,
    )

    response_dict = {
        "events": [
            {
                "summary": "テストイベント",
                "start": {"dateTime": "2024-12-25T09:00:00+09:00", "timeZone": "Asia/Tokyo"},
                "end": {"dateTime": "2024-12-25T10:00:00+09:00", "timeZone": "Asia/Tokyo"},
                "location": None,
                "description": None,
            }
        ]
    }

    captured_messages: list[Any] = []

    def capture_invoke(messages: Any) -> Any:
        captured_messages.extend(messages)
        return response_dict

    with patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.ChatBedrock"
    ) as mock_chat_class, patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.boto3.client"
    ) as mock_boto_client:
        mock_chat_instance = MagicMock()
        mock_chat_instance.__or__ = MagicMock()
        mock_pipe_output = MagicMock()
        mock_pipe_output.with_retry = MagicMock(return_value=MagicMock(
            invoke=MagicMock(side_effect=capture_invoke)
        ))
        mock_chat_instance.__or__.return_value = mock_pipe_output
        mock_chat_class.return_value = mock_chat_instance
        mock_boto_client.return_value = MagicMock()

        os.environ.setdefault("BEDROCK_MODEL_ID", "test-model")
        load_settings.cache_clear()
        settings = load_settings()

        text_with_unsubscribe = "テストイベント 9:00\n\nUnsubscribe from this list"
        extract_events_from_raw_text(text_with_unsubscribe, settings=settings)

    human_msg = next(
        m for m in captured_messages
        if hasattr(m, "content") and "Unsubscribe" in str(m.content)
    )
    assert "Unsubscribe" in str(human_msg.content)


def test_normalize_event_to_half_width_が公開されている() -> None:
    """normalize_event_to_half_width が公開エイリアスとして存在することを確認する。"""
    from calendar_auto_register.features.llm_extract.usecase_llm_extract import (
        normalize_event_to_half_width,  # noqa: F401
    )
    assert callable(normalize_event_to_half_width)


# ===== POST /llm/extract-event 統合スキーマ テスト（Phase 7: D9） =====
# [D9] text 必須・メールコンテキスト任意のフラット構造に統合

def test_新スキーマ_textのみ_raw_textパスが呼ばれる() -> None:
    """[D9] text のみのリクエストで extract_events_from_raw_text() が呼ばれることを確認する。"""
    response_dict = {
        "events": [
            {
                "summary": "朝礼",
                "start": {"dateTime": "2024-12-25T09:00:00+09:00", "timeZone": "Asia/Tokyo"},
                "end": {"dateTime": "2024-12-25T09:30:00+09:00", "timeZone": "Asia/Tokyo"},
                "location": None,
                "description": None,
            }
        ]
    }

    with patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.ChatBedrock"
    ) as mock_chat_class, patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.boto3.client"
    ) as mock_boto_client:
        mock_chat_instance = _mock_bedrock_chain(response_dict)
        mock_chat_class.return_value = mock_chat_instance
        mock_boto_client.return_value = MagicMock()

        client = TestClient(create_app())
        # text のみのフラット構造（LINE テキストパス）
        payload = {"text": "明日9時から朝礼があります"}

        res = client.post("/llm/extract-event", json=payload)

    assert res.status_code == 200
    assert len(res.json()["events"]) == 1


def test_新スキーマ_textとメールフィールドあり_メールパスが呼ばれる() -> None:
    """[D9] text + from_addr がある場合、extract_events()（メールパス）が呼ばれることを確認する。"""
    response_dict = {
        "events": [
            {
                "summary": "営業会議",
                "start": {"dateTime": "2024-12-25T14:00:00+09:00", "timeZone": "Asia/Tokyo"},
                "end": {"dateTime": "2024-12-25T15:00:00+09:00", "timeZone": "Asia/Tokyo"},
                "location": None,
                "description": None,
            }
        ]
    }

    with patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.ChatBedrock"
    ) as mock_chat_class, patch(
        "calendar_auto_register.features.llm_extract.usecase_llm_extract.boto3.client"
    ) as mock_boto_client:
        mock_chat_instance = _mock_bedrock_chain(response_dict)
        mock_chat_class.return_value = mock_chat_instance
        mock_boto_client.return_value = MagicMock()

        client = TestClient(create_app())
        # text + メールコンテキスト（メールパス）
        payload = {
            "text": "営業会議を12月25日14:00から開催します。",
            "from_addr": "alice@example.com",
            "subject": "12月25日の会議について",
            "received_at": "2024-12-20T10:00:00Z",
        }

        res = client.post("/llm/extract-event", json=payload)

    assert res.status_code == 200
    assert len(res.json()["events"]) == 1


def test_新スキーマ_メールコンテキストなしでtextなし_400エラー() -> None:
    """[D9] メールコンテキストなし・text なしのリクエストは 400 エラーになることを確認する。

    LINE テキストパスでは text は必須。ルーターで ValueError を raise して 400 を返す。
    Pydantic レベルでは text は str | None なので 422 にはならない。
    """
    client = TestClient(create_app())
    payload = {}  # text もメールコンテキストもない

    res = client.post("/llm/extract-event", json=payload)

    assert res.status_code == 400


# ===== POST /llm/extract-event-image テスト（Phase 8: D4, D5） =====

def test_extract_event_image_messageIdなし_422エラー() -> None:
    """[Phase 8] message_id なしのリクエストは 422 エラーになることを確認する。"""
    client = TestClient(create_app())
    res = client.post("/llm/extract-event-image", json={})
    assert res.status_code == 422


def test_extract_event_image_LINE_TOKEN未設定_500エラー() -> None:
    """[Phase 8] LINE_CHANNEL_ACCESS_TOKEN が未設定の場合は 500 エラーになることを確認する。"""
    import os
    os.environ.pop("LINE_CHANNEL_ACCESS_TOKEN", None)
    from calendar_auto_register.core.settings import load_settings
    load_settings.cache_clear()

    client = TestClient(create_app())
    res = client.post("/llm/extract-event-image", json={"message_id": "img-001"})
    assert res.status_code == 500


def test_extract_event_image_LINE_API失敗_500エラー() -> None:
    """[Phase 8] LINE Content API 失敗時に 500 エラーになることを確認する。"""
    import os
    os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "dummy_token"
    os.environ["BEDROCK_MODEL_ID"] = "test-model"
    from calendar_auto_register.core.settings import load_settings
    load_settings.cache_clear()

    from calendar_auto_register.clients.line_client import LineApiError

    with patch(
        "calendar_auto_register.clients.line_client.get_message_content",
        side_effect=LineApiError("LINE API エラー", 404),
    ):
        client = TestClient(create_app())
        res = client.post("/llm/extract-event-image", json={"message_id": "img-001"})

    assert res.status_code == 500


def test_extract_event_image_正常系() -> None:
    """[Phase 8] 正常な画像から予定を抽出できることを確認する。"""
    import os
    os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "dummy_token"
    os.environ["BEDROCK_MODEL_ID"] = "test-model"
    from calendar_auto_register.core.settings import load_settings
    load_settings.cache_clear()

    image_bytes = b"\xff\xd8\xff"  # JPEG magic bytes

    bedrock_response = {
        "content": [
            {
                "type": "text",
                "text": json.dumps({
                    "events": [
                        {
                            "summary": "セミナー",
                            "start": {"dateTime": "2024-12-25T10:00:00+09:00", "timeZone": "Asia/Tokyo"},
                            "end": {"dateTime": "2024-12-25T12:00:00+09:00", "timeZone": "Asia/Tokyo"},
                            "location": None,
                            "description": None,
                        }
                    ]
                }),
            }
        ]
    }

    with patch(
        "calendar_auto_register.clients.line_client.get_message_content",
        return_value=image_bytes,
    ), patch(
        "calendar_auto_register.clients.bedrock_client.invoke_model_with_image",
        return_value=bedrock_response,
    ):
        client = TestClient(create_app())
        res = client.post("/llm/extract-event-image", json={"message_id": "img-001"})

    assert res.status_code == 200
    data = res.json()
    assert "events" in data
    assert len(data["events"]) == 1
    assert data["events"][0]["summary"] == "セミナー"


def test_extract_event_image_VISIONモデルIDが使われる() -> None:
    """BEDROCK_VISION_MODEL_ID が設定されている場合、invoke_model_with_image にそのモデル ID が渡る。"""
    os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "dummy_token"
    os.environ["BEDROCK_MODEL_ID"] = "haiku-model"
    os.environ["BEDROCK_VISION_MODEL_ID"] = "sonnet-vision-model"
    from calendar_auto_register.core.settings import load_settings
    load_settings.cache_clear()

    bedrock_response = {"content": [{"type": "text", "text": json.dumps({"events": []})}]}
    mock_invoke = MagicMock(return_value=bedrock_response)

    with patch(
        "calendar_auto_register.clients.line_client.get_message_content",
        return_value=b"\xff\xd8\xff",
    ), patch(
        "calendar_auto_register.clients.bedrock_client.invoke_model_with_image",
        mock_invoke,
    ):
        from fastapi.testclient import TestClient
        from calendar_auto_register.app import create_app
        client = TestClient(create_app())
        client.post("/llm/extract-event-image", json={"message_id": "img-001"})

    mock_invoke.assert_called_once()
    assert mock_invoke.call_args.kwargs["model_id"] == "sonnet-vision-model"

    os.environ.pop("BEDROCK_VISION_MODEL_ID", None)

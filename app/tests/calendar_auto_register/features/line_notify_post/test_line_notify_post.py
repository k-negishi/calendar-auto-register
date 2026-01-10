"""LINE通知エンドポイントのテスト。"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from calendar_auto_register.app import create_app
from calendar_auto_register.clients.line_client import LineApiError


def test_line_notify_success() -> None:
    with patch(
        "calendar_auto_register.features.line_notify_post.usecase_line_notify_post.line_client.push_message"
    ) as mock_push:
        client = TestClient(create_app())
        payload = {
            "results": [
                {
                    "status": "CREATED",
                    "event": {
                        "summary": "⚙️ 営業会議",
                        "start": {
                            "dateTime": "2024-12-25T14:00:00+09:00",
                            "timeZone": "Asia/Tokyo",
                        },
                        "end": {
                            "dateTime": "2024-12-25T15:00:00+09:00",
                            "timeZone": "Asia/Tokyo",
                        },
                        "location": "オンライン",
                        "description": "議題: 四半期決算",
                        "attendees": [],
                        "eventType": "default",
                    },
                    "google_event_id": "event-1",
                }
            ]
        }

        res = client.post("/line/notify", json=payload)

        assert res.status_code == 200
        assert res.json()["status"] == "SENT"
        assert mock_push.called
        message = mock_push.call_args.kwargs["message"]
        assert "カレンダー自動登録 結果" in message
        assert "🧾 サマリ" in message
        assert "登録 1件 / 重複 0件 / 失敗 0件" in message
        assert "🔍 詳細" in message
        assert "登録　⚙️ 営業会議" in message


def test_line_notify_failure() -> None:
    with patch(
        "calendar_auto_register.features.line_notify_post.usecase_line_notify_post.line_client.push_message",
        side_effect=LineApiError("boom", 500),
    ):
        client = TestClient(create_app())
        payload = {
            "results": [
                {
                    "status": "FAILED",
                    "event": {
                        "summary": "⚙️ 夕礼",
                        "start": {
                            "dateTime": "2024-12-25T17:00:00+09:00",
                            "timeZone": "Asia/Tokyo",
                        },
                        "end": {
                            "dateTime": "2024-12-25T17:30:00+09:00",
                            "timeZone": "Asia/Tokyo",
                        },
                        "location": "",
                        "description": None,
                        "attendees": [],
                        "eventType": "default",
                    },
                    "error": {
                        "code": "GOOGLE_API_ERROR",
                        "message": "failed",
                        "retryable": False,
                    },
                }
            ]
        }

        res = client.post("/line/notify", json=payload)

        assert res.status_code == 502
        data = res.json()
        assert data["detail"]["error"]["code"] == "LINE_API_ERROR"

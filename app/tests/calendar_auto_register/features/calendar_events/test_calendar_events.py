"""Calendar events エンドポイントのテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from calendar_auto_register.app import create_app


def _build_service_mock(
    *,
    list_items: list[dict[str, object]] | None = None,
    insert_results: list[object] | None = None,
) -> MagicMock:
    service = MagicMock()
    events_resource = service.events.return_value

    list_call = events_resource.list.return_value
    list_call.execute.return_value = {"items": list_items or []}

    insert_call = events_resource.insert.return_value
    if insert_results is None:
        insert_call.execute.return_value = {"id": "event-1"}
    else:
        insert_call.execute.side_effect = insert_results

    return service


def test_bulk_create_event() -> None:
    service = _build_service_mock()

    with patch(
        "calendar_auto_register.features.calendar_events.usecase_calendar_events.google_client.service_from_settings",
        return_value=service,
    ):
        client = TestClient(create_app())
        payload = {
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
                    "description": "議題: 四半期決算",
                    "attendees": [{"email": "bob@example.com"}],
                }
            ]
        }

        res = client.post("/calendar/events", json=payload)

        assert res.status_code == 200
        data = res.json()
        assert len(data["results"]) == 1
        result = data["results"][0]
        assert result["status"] == "CREATED"
        assert result["google_event_id"] == "event-1"
        assert result["event"]["summary"] == "⚙️ 営業会議"


def test_bulk_duplicate_event() -> None:
    candidate = {
        "id": "event-dup",
        "summary": "営業会議",
        "start": {
            "dateTime": "2024-12-25T14:00:00+09:00",
            "timeZone": "Asia/Tokyo",
        },
        "end": {
            "dateTime": "2024-12-25T15:00:00+09:00",
            "timeZone": "Asia/Tokyo",
        },
    }
    service = _build_service_mock(list_items=[candidate])

    with patch(
        "calendar_auto_register.features.calendar_events.usecase_calendar_events.google_client.service_from_settings",
        return_value=service,
    ):
        client = TestClient(create_app())
        payload = {
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
                }
            ]
        }

        res = client.post("/calendar/events", json=payload)

        assert res.status_code == 200
        data = res.json()
        result = data["results"][0]
        assert result["status"] == "DUPLICATED"
        assert result["google_event_id"] == "event-dup"
        assert result["event"]["summary"] == "⚙️ 営業会議"


def test_bulk_partial_failure() -> None:
    service = _build_service_mock(insert_results=[{"id": "event-ok"}, RuntimeError("boom")])

    with patch(
        "calendar_auto_register.features.calendar_events.usecase_calendar_events.google_client.service_from_settings",
        return_value=service,
    ):
        client = TestClient(create_app())
        payload = {
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
                },
                {
                    "summary": "夕礼",
                    "start": {
                        "dateTime": "2024-12-25T17:00:00+09:00",
                        "timeZone": "Asia/Tokyo",
                    },
                    "end": {
                        "dateTime": "2024-12-25T17:30:00+09:00",
                        "timeZone": "Asia/Tokyo",
                    },
                },
            ]
        }

        res = client.post("/calendar/events", json=payload)

        assert res.status_code == 200
        data = res.json()
        assert data["results"][0]["status"] == "CREATED"
        assert data["results"][0]["google_event_id"] == "event-ok"
        assert data["results"][1]["status"] == "FAILED"
        assert data["results"][1]["event"]["summary"] == "⚙️ 夕礼"
        assert data["results"][1]["error"]["code"] == "UNEXPECTED_ERROR"

from fastapi.testclient import TestClient

from calendar_auto_register.app import create_app


def test_ヘルスチェックが成功する() -> None:
    """`/healthz` がローカル環境で 200 / 期待 JSON を返すことを検証する。"""

    client = TestClient(create_app())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "env": "local"}

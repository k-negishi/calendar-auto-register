"""Bedrock クライアントのテスト。"""

from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock, patch


# ===== invoke_model_with_image テスト =====

def test_invoke_model_with_image_base64エンコードが正しくリクエストに含まれる() -> None:
    """画像が base64 エンコードされてリクエストボディに含まれることを確認する。"""
    from calendar_auto_register.clients.bedrock_client import invoke_model_with_image

    fake_image_bytes = b"fake_jpeg_data"
    expected_b64 = base64.b64encode(fake_image_bytes).decode("utf-8")

    captured_body: dict = {}

    def fake_invoke_model(*, region: str, model_id: str, body: bytes, **kwargs) -> dict:
        captured_body.update(json.loads(body.decode("utf-8")))
        return {"content": [{"type": "text", "text": '{"events": []}'}]}

    with patch(
        "calendar_auto_register.clients.bedrock_client.invoke_model",
        side_effect=fake_invoke_model,
    ):
        invoke_model_with_image(
            region="ap-northeast-1",
            model_id="anthropic.claude-3-haiku-20240307-v1:0",
            image_bytes=fake_image_bytes,
            prompt="予定を抽出してください",
        )

    # base64 データが含まれているか確認
    messages = captured_body.get("messages", [])
    assert len(messages) == 1
    content = messages[0]["content"]
    image_block = next(c for c in content if c["type"] == "image")
    assert image_block["source"]["data"] == expected_b64
    assert image_block["source"]["type"] == "base64"


def test_invoke_model_with_image_media_typeがリクエストに含まれる() -> None:
    """media_type がリクエストボディの image ブロックに含まれることを確認する。"""
    from calendar_auto_register.clients.bedrock_client import invoke_model_with_image

    captured_body: dict = {}

    def fake_invoke_model(*, region: str, model_id: str, body: bytes, **kwargs) -> dict:
        captured_body.update(json.loads(body.decode("utf-8")))
        return {"content": [{"type": "text", "text": '{"events": []}'}]}

    with patch(
        "calendar_auto_register.clients.bedrock_client.invoke_model",
        side_effect=fake_invoke_model,
    ):
        invoke_model_with_image(
            region="ap-northeast-1",
            model_id="test-model",
            image_bytes=b"fake_png_data",
            prompt="テスト",
            media_type="image/png",
        )

    messages = captured_body.get("messages", [])
    content = messages[0]["content"]
    image_block = next(c for c in content if c["type"] == "image")
    assert image_block["source"]["media_type"] == "image/png"


def test_invoke_model_with_image_内部でinvoke_modelを呼ぶ() -> None:
    """invoke_model() が内部で呼ばれることを確認する（HTTP 重複実装がないことを保証）。"""
    from calendar_auto_register.clients.bedrock_client import invoke_model_with_image

    with patch(
        "calendar_auto_register.clients.bedrock_client.invoke_model",
    ) as mock_invoke:
        mock_invoke.return_value = {"content": []}

        invoke_model_with_image(
            region="ap-northeast-1",
            model_id="test-model",
            image_bytes=b"fake_data",
            prompt="テスト",
        )

    # invoke_model が 1 回だけ呼ばれたことを確認
    mock_invoke.assert_called_once()
    call_kwargs = mock_invoke.call_args.kwargs
    assert call_kwargs["region"] == "ap-northeast-1"
    assert call_kwargs["model_id"] == "test-model"


def test_invoke_model_with_image_レスポンスを返す() -> None:
    """invoke_model() のレスポンスをそのまま返すことを確認する。"""
    from calendar_auto_register.clients.bedrock_client import invoke_model_with_image

    expected_response = {"content": [{"type": "text", "text": '{"events": []}'}]}

    with patch(
        "calendar_auto_register.clients.bedrock_client.invoke_model",
        return_value=expected_response,
    ):
        result = invoke_model_with_image(
            region="ap-northeast-1",
            model_id="test-model",
            image_bytes=b"fake_data",
            prompt="テスト",
        )

    assert result == expected_response

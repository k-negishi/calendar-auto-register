"""LINE クライアントのテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ===== get_message_content 失敗系テスト（先に書く） =====

def test_get_message_content_APIエラーでLineApiError() -> None:
    """LINE API エラー時に LineApiError が送出されることを確認する。"""
    from linebot.v3.messaging import ApiException

    from calendar_auto_register.clients.line_client import LineApiError, get_message_content

    with patch(
        "calendar_auto_register.clients.line_client.ApiClient"
    ) as mock_api_client_class:
        mock_api_client = MagicMock()
        mock_api_client_class.return_value.__enter__ = MagicMock(return_value=mock_api_client)
        mock_api_client_class.return_value.__exit__ = MagicMock(return_value=False)

        mock_blob = MagicMock()
        mock_blob.get_message_content.side_effect = ApiException(status=500, reason="Server Error")

        with patch(
            "calendar_auto_register.clients.line_client.MessagingApiBlob",
            return_value=mock_blob,
        ):
            with pytest.raises(LineApiError) as exc_info:
                get_message_content(
                    channel_access_token="dummy_token",
                    message_id="msg-001",
                )
            assert exc_info.value.status_code == 500


def test_get_message_content_404エラーでLineApiError() -> None:
    """404 Not Found（期限切れメッセージ）で LineApiError が送出されることを確認する。"""
    from linebot.v3.messaging import ApiException

    from calendar_auto_register.clients.line_client import LineApiError, get_message_content

    with patch(
        "calendar_auto_register.clients.line_client.ApiClient"
    ) as mock_api_client_class:
        mock_api_client = MagicMock()
        mock_api_client_class.return_value.__enter__ = MagicMock(return_value=mock_api_client)
        mock_api_client_class.return_value.__exit__ = MagicMock(return_value=False)

        mock_blob = MagicMock()
        mock_blob.get_message_content.side_effect = ApiException(status=404, reason="Not Found")

        with patch(
            "calendar_auto_register.clients.line_client.MessagingApiBlob",
            return_value=mock_blob,
        ):
            with pytest.raises(LineApiError) as exc_info:
                get_message_content(
                    channel_access_token="dummy_token",
                    message_id="msg-expired",
                )
            assert exc_info.value.status_code == 404


# ===== get_message_content 正常系テスト =====

def test_get_message_content_bytesを返す() -> None:
    """正常なレスポンスで bytes を返すことを確認する。"""
    from calendar_auto_register.clients.line_client import get_message_content

    fake_image_bytes = b"\x89PNG\r\n\x1a\nfake_image_data"

    with patch(
        "calendar_auto_register.clients.line_client.ApiClient"
    ) as mock_api_client_class:
        mock_api_client = MagicMock()
        mock_api_client_class.return_value.__enter__ = MagicMock(return_value=mock_api_client)
        mock_api_client_class.return_value.__exit__ = MagicMock(return_value=False)

        mock_blob = MagicMock()
        mock_blob.get_message_content.return_value = fake_image_bytes

        with patch(
            "calendar_auto_register.clients.line_client.MessagingApiBlob",
            return_value=mock_blob,
        ):
            result = get_message_content(
                channel_access_token="dummy_token",
                message_id="msg-001",
            )

    assert result == fake_image_bytes
    assert isinstance(result, bytes)

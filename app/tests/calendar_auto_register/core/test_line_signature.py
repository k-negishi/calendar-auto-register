"""LINE Webhook 署名検証のテスト。"""

from __future__ import annotations

import base64
import hashlib
import hmac

import pytest


def _make_valid_signature(body: bytes, secret: str) -> str:
    """テスト用の正しい署名を生成する。"""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


# ===== 失敗系テスト（先に書く） =====

def test_不正な署名はFalseを返す() -> None:
    """不正な署名文字列を渡すと False を返すことを確認する。"""
    from calendar_auto_register.core.line_signature import verify_line_signature

    result = verify_line_signature(
        body=b'{"events": []}',
        signature="invalid_signature",
        channel_secret="my_channel_secret",
    )
    assert result is False


def test_空の署名はFalseを返す() -> None:
    """空文字列の署名を渡すと False を返すことを確認する。"""
    from calendar_auto_register.core.line_signature import verify_line_signature

    result = verify_line_signature(
        body=b'{"events": []}',
        signature="",
        channel_secret="my_channel_secret",
    )
    assert result is False


def test_異なるchannel_secretはFalseを返す() -> None:
    """間違った channel_secret を渡すと False を返すことを確認する。"""
    from calendar_auto_register.core.line_signature import verify_line_signature

    body = b'{"events": []}'
    valid_sig = _make_valid_signature(body, "correct_secret")

    result = verify_line_signature(
        body=body,
        signature=valid_sig,
        channel_secret="wrong_secret",
    )
    assert result is False


def test_空ボディへの不正署名はFalseを返す() -> None:
    """ボディが空バイトで不正な署名のとき False を返すことを確認する。"""
    from calendar_auto_register.core.line_signature import verify_line_signature

    result = verify_line_signature(
        body=b"",
        signature="invalid",
        channel_secret="my_channel_secret",
    )
    assert result is False


# ===== 正常系テスト =====

def test_正常な署名はTrueを返す() -> None:
    """正しい署名を渡すと True を返すことを確認する。"""
    from calendar_auto_register.core.line_signature import verify_line_signature

    body = b'{"destination": "xxx", "events": []}'
    secret = "my_channel_secret"
    valid_sig = _make_valid_signature(body, secret)

    result = verify_line_signature(
        body=body,
        signature=valid_sig,
        channel_secret=secret,
    )
    assert result is True


def test_空ボディへの正しい署名はTrueを返す() -> None:
    """ボディが空バイトでも正しい署名なら True を返すことを確認する。"""
    from calendar_auto_register.core.line_signature import verify_line_signature

    body = b""
    secret = "my_channel_secret"
    valid_sig = _make_valid_signature(body, secret)

    result = verify_line_signature(
        body=body,
        signature=valid_sig,
        channel_secret=secret,
    )
    assert result is True

"""LINE Webhook 署名検証。"""

from __future__ import annotations

import base64
import hashlib
import hmac


def verify_line_signature(
    *,
    body: bytes,
    signature: str,
    channel_secret: str,
) -> bool:
    """LINE Webhook の HMAC-SHA256 署名を検証する。

    Args:
        body: リクエストボディ (bytes)
        signature: X-Line-Signature ヘッダ値
        channel_secret: LINE Channel Secret

    Returns:
        署名が一致すれば True
    """
    if not signature:
        return False

    hash_digest = hmac.new(
        channel_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).digest()
    expected = base64.b64encode(hash_digest).decode("utf-8")
    return hmac.compare_digest(signature, expected)

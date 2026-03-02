"""Amazon Bedrock Runtime へのアクセスラッパー。"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import boto3
from botocore.client import BaseClient


@lru_cache(maxsize=None)
def get_client(region: str) -> BaseClient:
    """リージョンごとの Bedrock Runtime クライアントを返す。"""

    return boto3.client("bedrock-runtime", region_name=region)


def invoke_model(
    *,
    region: str,
    model_id: str,
    body: bytes,
    content_type: str = "application/json",
) -> dict[str, Any]:
    """Bedrock モデルを呼び出して JSON レスポンスを返す"""

    client = get_client(region)
    response = client.invoke_model(
        modelId=model_id,
        body=body,
        contentType=content_type,
        accept="application/json",
    )
    payload = response.get("body")
    if payload is None:  # pragma: no cover - defensive
        return {}

    raw: Any
    if hasattr(payload, "read"):
        raw = payload.read()
    else:
        raw = payload

    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        return json.loads(raw)

    return raw  # pragma: no cover - boto3 stubでdictが返るケース


def invoke_model_with_image(
    *,
    region: str,
    model_id: str,
    image_bytes: bytes,
    prompt: str,
    media_type: str = "image/jpeg",
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """画像付きで Bedrock モデルを呼び出す。

    Anthropic Messages API 形式でリクエストを構築し、
    画像とテキストプロンプトを同時に送信する。

    設計判断: invoke_model() を内部で呼び出す。ボディ構築のみが責務であり、
    HTTP 通信の重複を避ける。

    Args:
        region: AWS リージョン
        model_id: Bedrock モデル ID
        image_bytes: 画像バイナリ
        prompt: テキストプロンプト
        media_type: 画像の MIME タイプ (デフォルト: image/jpeg)
        max_tokens: 最大トークン数

    Returns:
        Bedrock レスポンス (dict)
    """
    import base64

    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            }
        ],
    }).encode("utf-8")

    return invoke_model(
        region=region,
        model_id=model_id,
        body=body,
    )

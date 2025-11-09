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

"""SES 送信に利用する boto3 クライアントラッパー。"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Iterable

import boto3
from botocore.client import BaseClient


@lru_cache(maxsize=None)
def get_client(region: str) -> BaseClient:
    """リージョン固定の SES クライアントを返す。"""

    return boto3.client("ses", region_name=region)


def send_email(
    *,
    region: str,
    source: str,
    to_addresses: Iterable[str],
    subject: str,
    body_text: str | None = None,
    body_html: str | None = None,
) -> dict[str, Any]:
    """テキスト/HTML混在の単純なメール送信を行う。"""

    client = get_client(region)
    body: dict[str, dict[str, str]] = {}
    if body_text:
        body["Text"] = {"Charset": "UTF-8", "Data": body_text}
    if body_html:
        body["Html"] = {"Charset": "UTF-8", "Data": body_html}

    return client.send_email(
        Source=source,
        Destination={"ToAddresses": list(to_addresses)},
        Message={"Subject": {"Charset": "UTF-8", "Data": subject}, "Body": body},
    )

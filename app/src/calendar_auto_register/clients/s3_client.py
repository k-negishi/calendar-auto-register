"""S3 とのやり取りに使う boto3 クライアントのラッパー。"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import boto3
from botocore.client import BaseClient


@lru_cache(maxsize=None)
def get_client(region: str) -> BaseClient:
    """リージョンに紐づく S3 クライアントを返す。"""

    return boto3.client("s3", region_name=region)


def get_object(bucket: str, key: str, *, region: str) -> dict[str, Any]:
    """S3 からオブジェクトを取得するヘルパー。"""

    client = get_client(region)
    return client.get_object(Bucket=bucket, Key=key)

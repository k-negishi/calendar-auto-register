"""アプリ全体で共有する設定読み込みロジック。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import boto3
from botocore.exceptions import ClientError


_DEFAULT_REGION = "ap-northeast-1"
_DEFAULT_TZ = "Asia/Tokyo"
_LOCAL_ENV = "local"
@dataclass(slots=True)
class Settings:
    """環境非依存で参照できる設定値の集合。"""

    app_env: str
    region: str
    raw_mail_bucket: str
    timezone_default: str
    gcal_calendar_id: str
    google_client_id: str | None
    google_client_secret: str | None
    google_refresh_token: str | None
    mail_from: list[str]
    notify_recipients: list[str]
    allowlist_senders: list[str]
    bedrock_model_id: str | None

    @property
    def is_local(self) -> bool:
        return self.app_env == _LOCAL_ENV


def _load_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ValueError("JSON 文字列のパースに失敗しました。") from exc
    if not isinstance(parsed, list):  # pragma: no cover - defensive
        raise ValueError("JSON 文字列は配列である必要があります。")
    return [str(item) for item in parsed]


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        raise ValueError(f"環境変数 {name} が未設定です。")
    return value


def _load_dotenv_from_ssm(*, region: str) -> None:
    """SSM に保存した dotenv 文字列を読み込み `os.environ` に適用する。"""

    parameter_path = os.getenv("SSM_DOTENV_PARAMETER")
    if not parameter_path:
        raise RuntimeError(
            "SSM_DOTENV_PARAMETER is not set. Configure it via Lambda environment variables or `.env.deploy`."
        )
    client = boto3.client("ssm", region_name=region)
    try:
        response = client.get_parameter(Name=parameter_path, WithDecryption=True)
    except ClientError as exc:  # pragma: no cover - boto3 例外ラップ
        raise RuntimeError(
            f"Failed to load dotenv parameter from SSM: {parameter_path}"
        ) from exc

    blob = response["Parameter"]["Value"]
    for raw_line in blob.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        os.environ.setdefault(key, value.strip())


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    """環境に応じて `.env` または SSM から設定を構築する。"""

    app_env = os.getenv("APP_ENV", _LOCAL_ENV)
    region = os.getenv("REGION", _DEFAULT_REGION)
    if app_env != _LOCAL_ENV:
        _load_dotenv_from_ssm(region=region)

    raw_mail_bucket = os.getenv("S3_RAW_MAIL_BUCKET", "")
    # タイムゾーンは JST 固定運用とする。
    timezone_default = _DEFAULT_TZ

    mail_from_values = _load_json_list(os.getenv("MAIL_FROM"))
    if not mail_from_values:
        raise ValueError("環境変数 MAIL_FROM が未設定です。")

    return Settings(
        app_env=app_env,
        region=region,
        raw_mail_bucket=raw_mail_bucket,
        timezone_default=timezone_default,
        gcal_calendar_id=_get_required_env("GCAL_CALENDAR_ID"),
        google_client_id=os.getenv("GOOGLE_OAUTH_CLIENT_ID"),
        google_client_secret=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET"),
        google_refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
        mail_from=mail_from_values,
        notify_recipients=_load_json_list(os.getenv("NOTIFY_RECIPIENTS")),
        allowlist_senders=_load_json_list(os.getenv("ALLOWLIST_SENDERS")),
        bedrock_model_id=os.getenv("BEDROCK_MODEL_ID"),
    )

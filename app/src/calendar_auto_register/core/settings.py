"""アプリ全体で共有する設定読み込みロジック。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterable

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
    mail_from: str | None
    notify_recipients: list[str]
    allowlist_senders: list[str]
    bedrock_model_id: str | None
    ssm_path_prefix: str | None = None

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


def _fetch_ssm_parameters(
    region: str, names: Iterable[str], prefix: str
) -> dict[str, str]:
    name_list = [f"{prefix}/{name}" for name in names]
    client = boto3.client("ssm", region_name=region)
    try:
        resp = client.get_parameters(Names=name_list, WithDecryption=True)
    except ClientError as exc:  # pragma: no cover - boto3 例外ラップ
        raise RuntimeError("SSM パラメータ取得に失敗しました。") from exc

    found = {item["Name"]: item["Value"] for item in resp.get("Parameters", [])}
    missing = {name for name in name_list if name not in found}
    if missing:
        raise ValueError(f"SSM パラメータ未設定: {', '.join(sorted(missing))}")
    return found


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    """環境に応じて `.env` または SSM から設定を構築する。"""

    app_env = os.getenv("APP_ENV", _LOCAL_ENV)
    region = os.getenv("REGION", _DEFAULT_REGION)
    raw_mail_bucket = os.getenv("S3_RAW_MAIL_BUCKET", "")
    # タイムゾーンは JST 固定運用とする。
    timezone_default = _DEFAULT_TZ

    if app_env == _LOCAL_ENV:
        return Settings(
            app_env=app_env,
            region=region,
            raw_mail_bucket=raw_mail_bucket,
            timezone_default=timezone_default,
            gcal_calendar_id=_get_required_env("GCAL_CALENDAR_ID"),
            google_client_id=os.getenv("GOOGLE_OAUTH_CLIENT_ID"),
            google_client_secret=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET"),
            google_refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
            mail_from=os.getenv("MAIL_FROM"),
            notify_recipients=_load_json_list(os.getenv("NOTIFY_RECIPIENTS")),
            allowlist_senders=_load_json_list(os.getenv("ALLOWLIST_SENDERS")),
            bedrock_model_id=os.getenv("BEDROCK_MODEL_ID"),
            ssm_path_prefix=None,
        )

    prefix = os.getenv("SSM_PATH_PREFIX", "/app/prod")
    required_keys = [
        "google/oauth_client_id",
        "google/oauth_client_secret",
        "google/refresh_token",
        "google/calendar_id",
        "mail/from",
        "mail/notify_recipients",
        "allowlist_senders",
        "bedrock/model_id",
    ]
    values = _fetch_ssm_parameters(region=region, names=required_keys, prefix=prefix)

    def from_ssm(key: str) -> str:
        return values[f"{prefix}/{key}"]

    return Settings(
        app_env=app_env,
        region=region,
        raw_mail_bucket=raw_mail_bucket,
        timezone_default=timezone_default,
        gcal_calendar_id=from_ssm("google/calendar_id"),
        google_client_id=from_ssm("google/oauth_client_id"),
        google_client_secret=from_ssm("google/oauth_client_secret"),
        google_refresh_token=from_ssm("google/refresh_token"),
        mail_from=from_ssm("mail/from"),
        notify_recipients=_load_json_list(from_ssm("mail/notify_recipients")),
        allowlist_senders=_load_json_list(from_ssm("allowlist_senders")),
        bedrock_model_id=from_ssm("bedrock/model_id"),
        ssm_path_prefix=prefix,
    )

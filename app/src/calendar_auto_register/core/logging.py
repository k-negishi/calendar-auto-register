"""JSONロギングの共通ヘルパー。"""

from __future__ import annotations

import json
import logging
import traceback
from typing import Any

_LOGGER = logging.getLogger("calendar_auto_register")


def log_request(*, path: str, status: int, request_id: str, latency_ms: int) -> None:
    payload = {
        "level": "INFO",
        "path": path,
        "status": status,
        "request_id": request_id,
        "latency_ms": latency_ms,
    }
    _LOGGER.info(json.dumps(payload, ensure_ascii=False))


def log_error(
    *,
    path: str,
    status: int,
    request_id: str,
    latency_ms: int,
    error: Any,
) -> None:
    payload = {
        "level": "ERROR",
        "path": path,
        "status": status,
        "request_id": request_id,
        "latency_ms": latency_ms,
        "error_json": _to_error_json(error),
        "traceback": traceback.format_exc(),
    }
    _LOGGER.error(json.dumps(payload, ensure_ascii=False))


def _to_error_json(error: Any) -> str:
    if isinstance(error, (dict, list)):
        return json.dumps(error, ensure_ascii=False)
    return json.dumps({"message": str(error)}, ensure_ascii=False)

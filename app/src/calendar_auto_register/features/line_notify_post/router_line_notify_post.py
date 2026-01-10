"""LINE通知エンドポイント。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from calendar_auto_register.clients.line_client import LineApiError
from calendar_auto_register.core.settings import Settings
from calendar_auto_register.features.line_notify_post.schemas_line_notify_post import (
    LineNotifyErrorResponse,
    LineNotifyRequest,
    LineNotifyResponse,
)
from calendar_auto_register.features.line_notify_post.usecase_line_notify_post import (
    send_line_notification,
)
from calendar_auto_register.shared.schemas.calendar_events import ErrorModel

router = APIRouter(prefix="/line", tags=["line"])


async def get_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[attr-defined]


@router.post(
    "/notify",
    response_model=LineNotifyResponse,
    responses={502: {"model": LineNotifyErrorResponse}, 400: {"model": LineNotifyErrorResponse}},
)
async def line_notify(
    payload: LineNotifyRequest,
    settings: Settings = Depends(get_settings),
) -> LineNotifyResponse:
    try:
        send_line_notification(payload.results, settings=settings)
    except ValueError as exc:
        error = ErrorModel(code="INVALID_REQUEST", message=str(exc), retryable=False)
        raise HTTPException(status_code=400, detail={"error": error.model_dump()}) from exc
    except LineApiError as exc:
        retryable = exc.status_code >= 500 or exc.status_code in {408, 429}
        error = ErrorModel(code="LINE_API_ERROR", message=str(exc), retryable=retryable)
        raise HTTPException(status_code=502, detail={"error": error.model_dump()}) from exc
    return LineNotifyResponse(status="SENT")

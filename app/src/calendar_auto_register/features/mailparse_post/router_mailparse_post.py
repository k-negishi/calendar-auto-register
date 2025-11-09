"""FastAPI ルータ定義。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from calendar_auto_register.core.settings import Settings
from calendar_auto_register.features.mailparse_post.schemas_mailparse_post import (
    MailParseRequest,
    MailParseResponse,
)
from calendar_auto_register.features.mailparse_post.usecase_mailparse_post import (
    parse_mail,
)

router = APIRouter(prefix="/mail", tags=["mail"])


async def get_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[attr-defined]


@router.post("/parse", response_model=MailParseResponse)
async def mail_parse(
    payload: MailParseRequest,
    settings: Settings = Depends(get_settings),
) -> MailParseResponse:
    try:
        normalized = parse_mail(payload, settings=settings)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MailParseResponse(normalized_mail=normalized)

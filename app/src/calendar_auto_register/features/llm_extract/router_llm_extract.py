"""LLM 予定抽出エンドポイント。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from calendar_auto_register.core.settings import Settings
from calendar_auto_register.features.llm_extract.schemas_llm_extract import (
    LlmExtractEventRequest,
    LlmExtractEventResponse,
)
from calendar_auto_register.features.llm_extract.usecase_llm_extract import (
    extract_events,
)

router = APIRouter(prefix="/llm", tags=["llm"])


async def _get_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[attr-defined]


@router.post("/extract-event", response_model=LlmExtractEventResponse)
async def llm_extract_event(
    request: Request,
    payload: LlmExtractEventRequest,
) -> LlmExtractEventResponse:
    """
    メール本文から予定情報を LLM で抽出する。

    Args:
        request: FastAPI リクエストオブジェクト
        payload: 正規化されたメール情報

    Returns:
        抽出された予定リスト

    Raises:
        HTTPException: 入力不正（400）、Bedrock エラー（500）
    """

    try:
        settings = await _get_settings(request)

        # NormalizedMail ドメインモデルに変換
        from calendar_auto_register.core.models import NormalizedMail

        normalized_mail = NormalizedMail(
            from_addr=payload.normalized_mail.from_addr,
            reply_to=payload.normalized_mail.reply_to,
            subject=payload.normalized_mail.subject,
            received_at=payload.normalized_mail.received_at,
            text=payload.normalized_mail.text,
            html=payload.normalized_mail.html,
            attachments=[],  # API からは添付情報は不要
        )

        events = extract_events(normalized_mail, settings=settings)

        return LlmExtractEventResponse(events=events)

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

"""LLM 予定抽出エンドポイント。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from calendar_auto_register.core.settings import Settings
from calendar_auto_register.features.llm_extract.schemas_llm_extract import (
    LlmExtractEventRequest,
    LlmExtractEventResponse,
    LlmExtractImageEventRequest,
)
from calendar_auto_register.features.llm_extract.usecase_llm_extract import (
    extract_events,
    extract_events_from_image,
    extract_events_from_raw_text,
)

router = APIRouter(prefix="/llm", tags=["llm"])


async def _get_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[attr-defined]


@router.post("/extract-event", response_model=LlmExtractEventResponse)
async def llm_extract_event(
    request: Request,
    payload: LlmExtractEventRequest,
) -> LlmExtractEventResponse:
    """テキスト（または正規化済みメール）から予定情報を LLM で抽出する。

    [D9] text 必須、メールコンテキストは任意。
    - text のみ: LINE テキストパス（`extract_events_from_raw_text`）
    - text + from_addr 等: メールパス（`extract_events`、HTML 前処理あり）

    Args:
        request: FastAPI リクエストオブジェクト
        payload: 抽出対象テキスト（+ 任意のメールコンテキスト）

    Returns:
        抽出された予定リスト

    Raises:
        HTTPException: 入力不正（400）、Bedrock エラー（500）
    """
    try:
        settings = await _get_settings(request)

        # メールコンテキストが存在するかどうかでパスを分岐する
        has_mail_context = any([
            payload.from_addr,
            payload.reply_to,
            payload.subject,
            payload.received_at,
            payload.html,
        ])

        if has_mail_context:
            # メールパス: HTML 前処理（Unsubscribe 除去・タグ削除）を適用
            # text は null 可（html が存在すれば _preprocess_mail_body で html を優先使用）
            from calendar_auto_register.core.models import NormalizedMail

            normalized_mail = NormalizedMail(
                from_addr=payload.from_addr,
                reply_to=payload.reply_to,
                subject=payload.subject,
                received_at=payload.received_at,
                text=payload.text,
                html=payload.html,
                attachments=[],
            )
            events = extract_events(normalized_mail, settings=settings)
        else:
            # LINE テキストパス: 前処理なし・text は必須
            if not payload.text:
                raise ValueError("LINE テキストパスでは text は必須です")
            events = extract_events_from_raw_text(payload.text, settings=settings)

        return LlmExtractEventResponse(events=events)

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/extract-event-image", response_model=LlmExtractEventResponse)
async def llm_extract_event_image(
    request: Request,
    payload: LlmExtractImageEventRequest,
) -> LlmExtractEventResponse:
    """LINE 画像メッセージから予定情報を Vision LLM で抽出する。

    [D4, D5] LINE Content API で画像を取得し、Bedrock Vision LLM で抽出する。
    テキストパスと同一の正規化（半角変換）を適用し、tenacity リトライ（5回）で実行する。

    Args:
        request: FastAPI リクエストオブジェクト
        payload: LINE メッセージ ID

    Returns:
        抽出された予定リスト

    Raises:
        HTTPException: 設定不足（500）、LINE/Bedrock API エラー（500）
    """
    try:
        settings = await _get_settings(request)
        events = extract_events_from_image(payload.message_id, settings=settings)
        return LlmExtractEventResponse(events=events)

    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

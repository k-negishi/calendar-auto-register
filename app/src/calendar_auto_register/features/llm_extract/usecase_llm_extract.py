"""予定抽出ユースケース: メール本文を LLM で解析。"""

from __future__ import annotations

from typing import Any

import boto3  # type: ignore[import-untyped]
from langchain_core.runnables.retry import ExponentialJitterParams

try:  # テスト時にパッチできるようにモジュール変数として保持する
    from langchain_aws import ChatBedrock
except ModuleNotFoundError:  # pragma: no cover - 環境依存
    ChatBedrock = None  # type: ignore
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from calendar_auto_register.core.models import NormalizedMail
from calendar_auto_register.core.prompts import (
    CALENDAR_EVENT_EXTRACTION_SYSTEM,
    build_extraction_user_message,
)
from calendar_auto_register.core.settings import Settings
from calendar_auto_register.features.llm_extract.schemas_llm_extract import (
    GoogleCalendarEventModel,
)


class EventExtractionResponse(BaseModel):
    """LLM抽出レスポンス"""

    events: list[GoogleCalendarEventModel] = Field(default_factory=list)


def extract_events(
    normalized_mail: NormalizedMail,
    *,
    settings: Settings,
) -> list[GoogleCalendarEventModel]:
    """
    メール本文から Bedrock (Claude) を使って予定情報を抽出する。

    LangChain ChatBedrock と JsonOutputParser を使用してプロンプトベースで JSON を取得し、
    Pydantic で検証して Google Calendar API 互換形式で応答。

    Args:
        normalized_mail: 正規化されたメール情報
        settings: アプリケーション設定

    Returns:
        抽出された予定リスト（Google Calendar API 互換形式）

    Raises:
        ValueError: LLM 出力が無効な場合
        RuntimeError: Bedrock API エラー
    """

    if not settings.bedrock_model_id:
        raise ValueError("Bedrock モデルID が設定されていません")

    try:
        # AWS Bedrock クライアントを初期化（東京リージョン固定）
        bedrock_client = boto3.client("bedrock-runtime", region_name=settings.region)

        if ChatBedrock is None:
            raise RuntimeError("langchain_aws がインストールされていません。")

        chat: Any = ChatBedrock(
            model=settings.bedrock_model_id,
            client=bedrock_client,
            model_kwargs={"max_tokens": 2048},
        )

        # JSON 出力パーサーを初期化
        output_parser = JsonOutputParser(pydantic_object=EventExtractionResponse)

        # Runnable チェーン（LLM → JSON パーサー）
        # リトライ機能付き: 最大5回、エクスポーネンシャルバックオフ
        chain = (chat | output_parser).with_retry(
            retry_if_exception_type=(ValueError, RuntimeError),
            stop_after_attempt=5,
            wait_exponential_jitter=True,
            exponential_jitter_params=ExponentialJitterParams(
                initial=1,
                max=10,
                exp_base=2,
            ),
        )

        # プロンプト構築
        user_message_text = build_extraction_user_message(normalized_mail)

        # メッセージの構築
        messages = [
            SystemMessage(content=CALENDAR_EVENT_EXTRACTION_SYSTEM),
            HumanMessage(content=user_message_text),
        ]

        # チェーン実行（リトライ付き）
        parsed_dict = chain.invoke(messages)

        # JsonOutputParser は dict を返すため、Pydantic で検証
        parsed_response = EventExtractionResponse(**parsed_dict)

        # 抽出された予定を返す
        return parsed_response.events

    except ValueError as exc:
        raise exc
    except Exception as exc:
        raise RuntimeError(f"LLM 呼び出し失敗: {exc}") from exc

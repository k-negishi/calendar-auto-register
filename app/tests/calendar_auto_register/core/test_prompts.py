"""プロンプト構築のテスト。"""

from __future__ import annotations

import re

# ===== _get_today_date_str テスト =====

def test_get_today_date_str_フォーマット() -> None:
    """_get_today_date_str() が 'YYYY-MM-DD (曜日)' 形式を返すことを確認する。"""
    from calendar_auto_register.core.prompts import _get_today_date_str

    result = _get_today_date_str()
    assert re.match(r"\d{4}-\d{2}-\d{2} \([月火水木金土日]\)", result)


# ===== 失敗系テスト（先に書く） =====

def test_build_line_text_user_message_は存在する() -> None:
    """build_line_text_user_message() 関数が存在することを確認する。"""
    from calendar_auto_register.core.prompts import build_line_text_user_message  # noqa: F401


def test_build_line_text_user_message_メール固有語句を含まない() -> None:
    """返り値に件名・送信者などメール固有の語句が含まれないことを確認する。"""
    from calendar_auto_register.core.prompts import build_line_text_user_message

    result = build_line_text_user_message("明日10時に会議があります")

    # メール固有のコンテキストが含まれていないことを確認
    assert "件名" not in result
    assert "送信者" not in result
    assert "受信日時" not in result
    assert "from_addr" not in result


# ===== 正常系テスト =====

def test_build_line_text_user_message_入力テキストが含まれる() -> None:
    """返り値に入力テキストが含まれることを確認する。"""
    from calendar_auto_register.core.prompts import build_line_text_user_message

    text = "明日10時に会議があります"
    result = build_line_text_user_message(text)

    assert text in result


def test_build_line_text_user_message_文字列を返す() -> None:
    """文字列を返すことを確認する。"""
    from calendar_auto_register.core.prompts import build_line_text_user_message

    result = build_line_text_user_message("テスト")
    assert isinstance(result, str)
    assert len(result) > 0


# ===== 本日の日付が含まれることのテスト =====

def test_build_line_text_user_message_本日の日付が含まれる() -> None:
    """LINE テキスト用メッセージに本日の日付が含まれることを確認する。"""
    from calendar_auto_register.core.prompts import build_line_text_user_message

    result = build_line_text_user_message("3/10 予定")
    assert "本日の日付:" in result


def test_build_extraction_user_message_本日の日付が含まれる() -> None:
    """メールパスのメッセージに本日の日付が含まれることを確認する。"""
    from calendar_auto_register.core.models import NormalizedMail
    from calendar_auto_register.core.prompts import build_extraction_user_message

    mail = NormalizedMail(
        from_addr="test@example.com",
        reply_to=None,
        subject="テスト",
        received_at="2026-03-01T10:00:00Z",
        text="3月10日に会議があります",
        html=None,
        attachments=[],
    )
    result = build_extraction_user_message(mail)
    assert "本日の日付:" in result


def test_build_image_extraction_prompt_本日の日付が含まれる() -> None:
    """画像パスのプロンプトに本日の日付が含まれることを確認する。"""
    from calendar_auto_register.core.prompts import build_image_extraction_prompt

    result = build_image_extraction_prompt()
    assert "本日の日付:" in result
    # システムプロンプトの内容も含まれている
    assert "Google Calendar" in result

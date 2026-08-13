"""プロンプト構築のテスト。"""

from __future__ import annotations

from calendar_auto_register.core.prompts import build_line_text_user_message

# ===== 失敗系テスト（先に書く） =====

def test_build_line_text_user_message_は存在する() -> None:
    """build_line_text_user_message() 関数が存在することを確認する。"""
    assert callable(build_line_text_user_message)


def test_build_line_text_user_message_メール固有語句を含まない() -> None:
    """返り値に件名・送信者などメール固有の語句が含まれないことを確認する。"""
    result = build_line_text_user_message("明日10時に会議があります")

    # メール固有のコンテキストが含まれていないことを確認
    assert "件名" not in result
    assert "送信者" not in result
    assert "受信日時" not in result
    assert "from_addr" not in result


# ===== 正常系テスト =====

def test_build_line_text_user_message_入力テキストが含まれる() -> None:
    """返り値に入力テキストが含まれることを確認する。"""
    text = "明日10時に会議があります"
    result = build_line_text_user_message(text)

    assert text in result


def test_build_line_text_user_message_現在日時を含められる() -> None:
    """相対日付を解決するための現在日時を含められることを確認する。"""
    result = build_line_text_user_message(
        "明日10時に会議があります",
        current_datetime="2026-08-13T18:00:00+09:00",
    )

    assert "【現在日時】" in result
    assert "2026-08-13T18:00:00+09:00" in result
    assert "相対日付" in result


def test_build_line_text_user_message_文字列を返す() -> None:
    """文字列を返すことを確認する。"""
    result = build_line_text_user_message("テスト")
    assert isinstance(result, str)
    assert len(result) > 0

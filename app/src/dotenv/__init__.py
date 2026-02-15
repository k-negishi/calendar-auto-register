"""軽量な dotenv ローダー。

python-dotenv が利用できない環境向けに最小限の load_dotenv を提供する。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


def load_dotenv(path: str | os.PathLike[str] | None = None) -> bool:
    """dotenv ファイルを読み込み環境変数に反映する。

    Args:
        path: dotenv ファイルのパス。省略時はカレントディレクトリの `.env` を読む。

    Returns:
        読み込みに成功した場合は True、ファイルが存在しない場合は False。
    """

    dotenv_path = Path(path) if path is not None else Path(".env")
    if not dotenv_path.exists():
        return False

    for line in _read_lines(dotenv_path):
        key, value = _parse_line(line)
        if not key:
            continue
        os.environ.setdefault(key, value)
    return True


def _read_lines(path: Path) -> Iterable[str]:
    with path.open(encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            yield line


def _parse_line(line: str) -> tuple[str, str]:
    if "=" not in line:
        return "", ""
    key, value = line.split("=", 1)
    return key.strip(), value.strip().strip('"').strip("'")

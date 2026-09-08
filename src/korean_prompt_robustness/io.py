"""문제 JSONL을 읽는 공통 도구."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"{path}:{line_number} JSON 형식 오류: {error}"
                ) from error
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} 항목은 객체여야 합니다.")
            records.append(value)
    return records

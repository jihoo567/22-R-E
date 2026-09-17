"""JSONL 읽기와 문제 검증을 한 곳에서 처리합니다."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Problem:
    id: str
    prompt: str
    metadata: dict[str, Any]

    @classmethod
    def from_dict(cls, value: dict[str, Any], index: int) -> "Problem":
        problem_id = value.get("id")
        prompt = value.get("prompt")
        metadata = value.get("metadata", {})
        if not isinstance(problem_id, str) or not problem_id.strip():
            raise ValueError(f"항목 {index}: id가 필요합니다.")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(f"항목 {index}: prompt가 필요합니다.")
        if not isinstance(metadata, dict):
            raise ValueError(f"항목 {index}: metadata는 객체여야 합니다.")
        return cls(problem_id, prompt, metadata)


def _validated_problems(records: Iterable[dict[str, Any]]) -> Iterator[Problem]:
    seen: set[str] = set()
    for index, record in enumerate(records, 1):
        if not isinstance(record, dict):
            raise ValueError(f"항목 {index}: 문제는 객체여야 합니다.")
        problem = Problem.from_dict(record, index)
        if problem.id in seen:
            raise ValueError("문제 id는 중복될 수 없습니다.")
        seen.add(problem.id)
        yield problem
    if not seen:
        raise ValueError("입력 JSONL에 문제가 없습니다.")


def validate_dataset(records: Iterable[dict[str, Any]]) -> list[Problem]:
    return list(_validated_problems(records))


def _read_records(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number} JSON 형식 오류: {error}") from error
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} 항목은 객체여야 합니다.")
            yield value


def load_and_validate_dataset(path: Path, *, limit: int | None = None) -> list[Problem]:
    """파일 전체를 검증하되 실행할 문제 본문만 보관합니다."""
    if limit is not None and limit <= 0:
        raise ValueError("--limit은 1 이상의 정수여야 합니다.")
    return [
        problem
        for index, problem in enumerate(_validated_problems(_read_records(path)))
        if limit is None or index < limit
    ]

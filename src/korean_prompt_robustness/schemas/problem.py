"""최소 문제 데이터 스키마."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..io import read_jsonl


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
        if not isinstance(problem_id, str) or not problem_id:
            raise ValueError(f"항목 {index}: id가 필요합니다.")
        if not isinstance(prompt, str) or not prompt:
            raise ValueError(f"항목 {index}: prompt가 필요합니다.")
        if not isinstance(metadata, dict):
            raise ValueError(f"항목 {index}: metadata는 객체여야 합니다.")
        return cls(problem_id, prompt, metadata)


def validate_dataset(records: list[dict[str, Any]]) -> list[Problem]:
    if not records:
        raise ValueError("입력 JSONL에 문제가 없습니다.")
    problems = [Problem.from_dict(value, index) for index, value in enumerate(records, 1)]
    ids = [problem.id for problem in problems]
    if len(ids) != len(set(ids)):
        raise ValueError("문제 id는 중복될 수 없습니다.")
    return problems


def load_and_validate_dataset(path: Path) -> list[Problem]:
    return validate_dataset(read_jsonl(path))

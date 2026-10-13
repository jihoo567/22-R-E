"""저장된 테스트 모델 답변 JSONL을 읽고 검증합니다."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .dataset import Problem


RESPONSE_FILE_PATTERN = "test-responses-*.jsonl"


@dataclass(frozen=True)
class SavedResponse:
    problem: Problem
    test_model_response: str

    @classmethod
    def from_dict(cls, value: dict[str, Any], index: int) -> "SavedResponse":
        problem = Problem.from_dict(value, index)
        response = value.get("test_model_response")
        if not isinstance(response, str) or not response:
            raise ValueError(
                f"저장 응답 {index}: test_model_response가 필요합니다."
            )
        return cls(problem=problem, test_model_response=response)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.problem.id,
            "prompt": self.problem.prompt,
            "metadata": self.problem.metadata,
            "test_model_response": self.test_model_response,
        }


def load_saved_responses(path: Path) -> list[SavedResponse]:
    responses: list[SavedResponse] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"{path}:{line_number} 저장 응답 JSON 형식 오류: {error}"
                ) from error
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} 저장 응답은 객체여야 합니다.")
            saved = SavedResponse.from_dict(value, line_number)
            if saved.problem.id in seen:
                raise ValueError("저장 응답의 문제 id는 중복될 수 없습니다.")
            seen.add(saved.problem.id)
            responses.append(saved)
    if not responses:
        raise ValueError(f"저장된 테스트 모델 답변이 없습니다: {path}")
    return responses


def latest_response_file(directory: Path) -> Path:
    candidates = [
        path for path in directory.glob(RESPONSE_FILE_PATTERN) if path.is_file()
    ]
    if not candidates:
        raise ValueError(
            f"평가할 테스트 모델 답변 파일이 없습니다: {directory}. "
            "answer 명령을 먼저 실행하세요."
        )
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.name))

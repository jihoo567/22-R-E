"""API 키가 필요 없는 결정론적 Mock 모델."""

from __future__ import annotations

from ..config import ProviderSettings
from ..schemas import Problem
from .base import ModelAdapter, ModelOutput


class MockModel(ModelAdapter):
    def __init__(self) -> None:
        self.call_count = 0

    def generate(self, problem: Problem, settings: ProviderSettings) -> ModelOutput:
        self.call_count += 1
        configured = problem.metadata.get("mock_response")
        text = configured if isinstance(configured, str) else f"Mock 응답: {problem.prompt}"
        return ModelOutput(
            text=text,
            raw_provider_response={"provider": "mock", "text": text},
        )


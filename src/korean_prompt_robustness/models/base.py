"""답변 생성 모델의 공통 인터페이스."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ..config import ProviderSettings
from ..schemas import Problem


@dataclass(frozen=True)
class ModelOutput:
    text: str
    raw_provider_response: Any


class ModelAdapter(ABC):
    @abstractmethod
    def generate(self, problem: Problem, settings: ProviderSettings) -> ModelOutput:
        """입력 prompt를 바꾸지 않고 모델에 전달합니다."""


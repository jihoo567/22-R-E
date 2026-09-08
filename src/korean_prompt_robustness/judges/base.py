"""답변 생성 모델과 분리된 Judge 공통 인터페이스."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import ProviderSettings
from ..schemas import Problem


class JudgeAdapter(ABC):
    @abstractmethod
    def judge(
        self,
        problem: Problem,
        response: str,
        rendered_prompt: str,
        settings: ProviderSettings,
    ) -> str:
        """Judge가 생성한 텍스트 원문을 반환합니다."""

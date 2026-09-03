"""답변 생성 모델과 분리된 Judge 공통 인터페이스."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import JudgeSettings
from ..schemas import Problem


class JudgeAdapter(ABC):
    @abstractmethod
    def judge(
        self,
        problem: Problem,
        response: str,
        rendered_prompt: str,
        settings: JudgeSettings,
    ) -> str:
        """구조화 결과를 담은 JSON 원문을 반환합니다."""


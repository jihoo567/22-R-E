"""OpenAI 호환 API를 사용하는 Judge 어댑터."""

from __future__ import annotations

from ..config import ProviderSettings
from ..models.openai_compatible import call_openai_compatible, extract_openai_text
from ..schemas import Problem
from .base import JudgeAdapter


class OpenAICompatibleJudge(JudgeAdapter):
    def judge(
        self,
        problem: Problem,
        response: str,
        rendered_prompt: str,
        settings: ProviderSettings,
    ) -> str:
        raw = call_openai_compatible(
            prompt=rendered_prompt,
            settings=settings,
            system_instruction="당신은 테스트 모델의 답변을 검토하는 독립 평가자입니다.",
        )
        return extract_openai_text(raw)

"""표준 입력/출력 기반 로컬 Judge 어댑터."""

from __future__ import annotations

from ..config import ProviderSettings
from ..local_process import run_local_command
from ..schemas import Problem
from .base import JudgeAdapter


class LocalCommandJudge(JudgeAdapter):
    """Judge 프롬프트를 로컬 명령의 stdin으로 전달합니다."""

    def judge(
        self,
        problem: Problem,
        response: str,
        rendered_prompt: str,
        settings: ProviderSettings,
    ) -> str:
        if not settings.command:
            raise ValueError("local Judge에는 judge_model.command가 필요합니다.")
        return run_local_command(
            settings.command,
            rendered_prompt,
            settings.timeout_seconds,
            label="로컬 Judge",
        )

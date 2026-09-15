"""표준 입력/출력 기반 로컬 모델 어댑터."""

from __future__ import annotations

from ..config import ProviderSettings
from ..local_process import run_local_command
from ..schemas import Problem
from .base import ModelAdapter


class LocalCommandModel(ModelAdapter):
    def generate(self, problem: Problem, settings: ProviderSettings) -> str:
        if not settings.command:
            raise ValueError("local provider에는 model.command가 필요합니다.")
        return run_local_command(
            settings.command,
            problem.prompt,
            settings.timeout_seconds,
            label="로컬 모델",
        )

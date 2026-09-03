"""표준 입력/출력 기반 로컬 모델 어댑터."""

from __future__ import annotations

import shlex
import subprocess

from ..config import ProviderSettings
from ..schemas import Problem
from .base import ModelAdapter, ModelOutput


class LocalCommandModel(ModelAdapter):
    def generate(self, problem: Problem, settings: ProviderSettings) -> ModelOutput:
        if not settings.command:
            raise ValueError("local provider에는 model.command가 필요합니다.")
        command = shlex.split(settings.command)
        if not command:
            raise ValueError("로컬 모델 명령이 비어 있습니다.")
        completed = subprocess.run(
            command,
            input=problem.prompt,
            text=True,
            capture_output=True,
            timeout=settings.timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            error = completed.stderr.strip() or "오류 내용 없음"
            raise RuntimeError(f"로컬 모델 종료 코드 {completed.returncode}: {error}")
        # strip이나 후처리를 하지 않아 stdout 원문을 그대로 보존합니다.
        if completed.stdout == "":
            raise RuntimeError("로컬 모델이 빈 stdout을 반환했습니다.")
        return ModelOutput(
            text=completed.stdout,
            raw_provider_response={
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "returncode": completed.returncode,
            },
        )


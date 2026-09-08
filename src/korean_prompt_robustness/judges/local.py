"""표준 입력/출력 기반 로컬 Judge 어댑터."""

from __future__ import annotations

import subprocess

from ..config import ProviderSettings
from ..local_process import prepare_command
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
        command = prepare_command(settings.command)
        completed = subprocess.run(
            command,
            input=rendered_prompt,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=settings.timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            error = completed.stderr.strip() or "오류 내용 없음"
            raise RuntimeError(
                f"로컬 Judge 종료 코드 {completed.returncode}: {error}"
            )
        if completed.stdout == "":
            raise RuntimeError("로컬 Judge가 빈 stdout을 반환했습니다.")
        # 후처리하지 않고 Judge의 stdout 원문을 그대로 보존합니다.
        return completed.stdout

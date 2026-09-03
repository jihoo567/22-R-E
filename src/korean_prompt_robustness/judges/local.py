"""표준 입력/출력 기반 로컬 Judge 어댑터."""

from __future__ import annotations

import shlex
import subprocess

from ..config import JudgeSettings
from ..schemas import Problem
from .base import JudgeAdapter


class LocalCommandJudge(JudgeAdapter):
    """Judge 프롬프트를 로컬 명령의 stdin으로 전달합니다."""

    def judge(
        self,
        problem: Problem,
        response: str,
        rendered_prompt: str,
        settings: JudgeSettings,
    ) -> str:
        if not settings.command:
            raise ValueError("local Judge에는 judge_model.command가 필요합니다.")
        command = shlex.split(settings.command)
        if not command:
            raise ValueError("로컬 Judge 명령이 비어 있습니다.")
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
        # JSON 파싱과 스키마 검증은 공통 Judge runner가 수행합니다.
        return completed.stdout

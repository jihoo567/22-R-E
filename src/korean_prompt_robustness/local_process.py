"""로컬 모델 명령을 운영체제에 맞게 준비합니다."""

from __future__ import annotations

import os
import shlex
import subprocess


def prepare_command(command: str, *, platform: str | None = None) -> str | list[str]:
    """Windows는 원문 명령줄을, Unix 계열은 분리한 인자 목록을 반환합니다.

    Windows의 ``CreateProcess``가 따옴표와 공백 포함 경로를 직접 해석하게
    두어 Python 설치 경로가 깨지는 문제를 피합니다.
    """
    current_platform = platform or os.name
    if current_platform == "nt":
        return command
    arguments = shlex.split(command)
    if not arguments:
        raise ValueError("로컬 모델 명령이 비어 있습니다.")
    return arguments


def command_executable(command: str, *, platform: str | None = None) -> str:
    """사전 점검에 사용할 실행 파일 이름 또는 경로를 반환합니다."""
    current_platform = platform or os.name
    arguments = shlex.split(command, posix=current_platform != "nt")
    if not arguments:
        raise ValueError("로컬 모델 명령이 비어 있습니다.")
    return arguments[0].strip('"')


def run_local_command(
    command: str,
    input_text: str,
    timeout_seconds: float,
    *,
    label: str,
) -> str:
    """UTF-8 stdin/stdout으로 로컬 명령을 한 번 실행합니다."""
    completed = subprocess.run(
        prepare_command(command),
        input=input_text,
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    if completed.returncode != 0:
        error = completed.stderr.strip() or "오류 내용 없음"
        raise RuntimeError(f"{label} 종료 코드 {completed.returncode}: {error}")
    if completed.stdout == "":
        raise RuntimeError(f"{label}이 빈 stdout을 반환했습니다.")
    return completed.stdout

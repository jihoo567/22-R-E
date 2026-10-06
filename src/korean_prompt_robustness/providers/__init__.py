"""역할에 관계없이 같은 함수로 모델을 호출합니다."""

from __future__ import annotations

from ..config import ProviderSettings
from ..local_process import run_local_command
from .gemini import call_gemini, extract_text
from .openai_compatible import call_openai_compatible, extract_openai_text


def generate_text(
    prompt: str,
    settings: ProviderSettings,
    *,
    system_instruction: str | None = None,
) -> str:
    """prompt를 설정된 모델에 전달하고 텍스트만 반환합니다."""
    instruction = (
        system_instruction
        if system_instruction is not None
        else settings.system_instruction
    )
    if settings.provider == "local":
        if not settings.command:
            raise ValueError("local 방식에는 실행 command가 필요합니다.")
        local_prompt = (
            f"{instruction}\n\n{prompt}" if instruction is not None else prompt
        )
        return run_local_command(
            settings.command,
            local_prompt,
            settings.timeout_seconds,
            label="로컬 모델",
        )
    if settings.provider == "gemini":
        response = call_gemini(
            prompt=prompt, settings=settings, system_instruction=instruction
        )
        return extract_text(response)
    if settings.provider == "openai-compatible":
        response = call_openai_compatible(
            prompt=prompt, settings=settings, system_instruction=instruction
        )
        return extract_openai_text(response)
    raise ValueError(f"지원하지 않는 provider: {settings.provider}")

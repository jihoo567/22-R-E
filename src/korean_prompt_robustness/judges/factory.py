from __future__ import annotations

from ..config import ProviderSettings
from .base import JudgeAdapter
from .gemini import GeminiJudge
from .local import LocalCommandJudge
from .openai_compatible import OpenAICompatibleJudge


def create_judge(
    settings: ProviderSettings,
) -> JudgeAdapter:
    adapters: dict[str, type[JudgeAdapter]] = {
        "gemini": GeminiJudge,
        "local": LocalCommandJudge,
        "openai-compatible": OpenAICompatibleJudge,
    }
    try:
        return adapters[settings.provider]()
    except KeyError as error:
        raise ValueError(
            f"지원하지 않는 Judge provider: {settings.provider}"
        ) from error

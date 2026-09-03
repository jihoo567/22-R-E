from __future__ import annotations

from ..config import JudgeSettings
from .base import JudgeAdapter
from .gemini import GeminiJudge
from .local import LocalCommandJudge
from .mock import MockJudge


def create_judge(
    settings: JudgeSettings, *, allow_mock_judge: bool = False
) -> JudgeAdapter:
    adapters: dict[str, type[JudgeAdapter]] = {
        "gemini": GeminiJudge,
        "local": LocalCommandJudge,
    }
    if settings.provider == "mock":
        if not allow_mock_judge:
            raise ValueError(
                "Mock Judge는 allow_mock_judge=true인 자동 테스트에서만 사용할 수 있습니다."
            )
        return MockJudge()
    try:
        return adapters[settings.provider]()
    except KeyError as error:
        raise ValueError(
            f"지원하지 않는 Judge provider: {settings.provider}"
        ) from error

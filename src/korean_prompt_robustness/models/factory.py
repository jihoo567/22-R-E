from __future__ import annotations

from ..config import ProviderSettings
from .base import ModelAdapter
from .gemini import GeminiModel
from .local import LocalCommandModel
from .openai_compatible import OpenAICompatibleModel


def create_model(settings: ProviderSettings) -> ModelAdapter:
    adapters: dict[str, type[ModelAdapter]] = {
        "local": LocalCommandModel,
        "gemini": GeminiModel,
        "openai-compatible": OpenAICompatibleModel,
    }
    try:
        return adapters[settings.provider]()
    except KeyError as error:
        raise ValueError(f"지원하지 않는 모델 provider: {settings.provider}") from error

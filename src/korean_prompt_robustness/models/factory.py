from __future__ import annotations

from ..config import ProviderSettings
from .base import ModelAdapter
from .gemini import GeminiModel
from .local import LocalCommandModel
from .mock import MockModel


def create_model(settings: ProviderSettings) -> ModelAdapter:
    adapters: dict[str, type[ModelAdapter]] = {
        "mock": MockModel,
        "local": LocalCommandModel,
        "gemini": GeminiModel,
    }
    try:
        return adapters[settings.provider]()
    except KeyError as error:
        raise ValueError(f"지원하지 않는 모델 provider: {settings.provider}") from error


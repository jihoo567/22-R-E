"""Gemini generateContent REST 어댑터(외부 SDK 의존성 없음)."""

from __future__ import annotations

import urllib.parse
from typing import Any

from ..auth import require_api_key
from ..config import ProviderSettings
from .http import post_json


def call_gemini(
    *,
    prompt: str,
    settings: ProviderSettings,
    system_instruction: str | None = None,
) -> dict[str, Any]:
    api_key = require_api_key(settings)
    model_id = urllib.parse.quote(settings.model_id, safe="-._")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model_id}:generateContent"
    )
    generation_config: dict[str, Any] = {
        "temperature": settings.temperature,
        "maxOutputTokens": settings.max_tokens,
    }
    if settings.seed is not None:
        generation_config["seed"] = settings.seed
    body: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": generation_config,
    }
    if system_instruction:
        body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
    return post_json(
        url,
        body,
        {"x-goog-api-key": api_key},
        timeout=settings.timeout_seconds,
        label="Gemini API",
    )


def extract_text(response: dict[str, Any]) -> str:
    try:
        parts = response["candidates"][0]["content"]["parts"]
        texts = [
            part["text"]
            for part in parts
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        ]
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError("Gemini 응답에서 텍스트 candidate를 찾지 못했습니다.") from error
    text = "".join(texts)
    if not text:
        raise RuntimeError("Gemini가 빈 텍스트 응답을 반환했습니다.")
    return text

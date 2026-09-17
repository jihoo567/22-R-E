"""OpenAI 호환 Chat Completions API 어댑터."""

from __future__ import annotations
from typing import Any

from ..auth import require_api_key
from ..config import ProviderSettings
from .http import post_json


def call_openai_compatible(
    *,
    prompt: str,
    settings: ProviderSettings,
    system_instruction: str | None = None,
) -> dict[str, Any]:
    """설정한 호환 서버의 ``/chat/completions``를 호출합니다."""
    if not settings.base_url:
        raise ValueError("openai-compatible에는 base_url이 필요합니다.")
    api_key = require_api_key(settings)
    base_url = settings.base_url.rstrip("/")
    url = (
        base_url
        if base_url.endswith("/chat/completions")
        else f"{base_url}/chat/completions"
    )

    messages: list[dict[str, str]] = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})
    body: dict[str, Any] = {
        "model": settings.model_id,
        "messages": messages,
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
    }
    if settings.seed is not None:
        body["seed"] = settings.seed

    return post_json(
        url,
        body,
        {"Authorization": f"Bearer {api_key}"},
        timeout=settings.timeout_seconds,
        label="OpenAI 호환 API",
    )


def extract_openai_text(response: dict[str, Any]) -> str:
    """일반 문자열 및 텍스트 블록 형태의 content를 읽습니다."""
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError("OpenAI 호환 응답에서 message content를 찾지 못했습니다.") from error

    if isinstance(content, str) and content:
        return content
    if isinstance(content, list):
        texts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        ]
        text = "".join(texts)
        if text:
            return text
    raise RuntimeError("OpenAI 호환 API가 빈 텍스트 응답을 반환했습니다.")

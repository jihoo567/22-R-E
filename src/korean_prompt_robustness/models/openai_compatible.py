"""OpenAI 호환 Chat Completions API 어댑터."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from ..auth import require_api_key
from ..config import ProviderSettings
from ..schemas import Problem
from .base import ModelAdapter, ModelOutput


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

    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        # 응답 본문에 민감한 요청 정보가 있을 수 있어 상태 코드만 노출합니다.
        raise RuntimeError(f"OpenAI 호환 API HTTP 오류: {error.code}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"OpenAI 호환 API 연결 오류: {error.reason}") from error
    except json.JSONDecodeError as error:
        raise RuntimeError("OpenAI 호환 API 응답이 JSON이 아닙니다.") from error


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


class OpenAICompatibleModel(ModelAdapter):
    def generate(self, problem: Problem, settings: ProviderSettings) -> ModelOutput:
        response = call_openai_compatible(prompt=problem.prompt, settings=settings)
        return ModelOutput(extract_openai_text(response), response)

"""Gemini generateContent REST 어댑터(외부 SDK 의존성 없음)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ..config import ProviderSettings
from ..schemas import Problem
from .base import ModelAdapter, ModelOutput


def call_gemini(
    *,
    prompt: str,
    settings: ProviderSettings,
    system_instruction: str | None = None,
    response_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY 환경변수가 없습니다.")
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
    if response_schema is not None:
        generation_config["responseMimeType"] = "application/json"
        generation_config["responseSchema"] = response_schema
    body: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": generation_config,
    }
    if system_instruction:
        body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        # 응답 본문에는 요청/키 정보가 섞일 수 있어 상태 코드만 기록합니다.
        raise RuntimeError(f"Gemini API HTTP 오류: {error.code}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Gemini API 연결 오류: {error.reason}") from error
    except json.JSONDecodeError as error:
        raise RuntimeError("Gemini API 응답이 JSON이 아닙니다.") from error


def extract_text(response: dict[str, Any]) -> str:
    try:
        parts = response["candidates"][0]["content"]["parts"]
        texts = [part["text"] for part in parts if isinstance(part.get("text"), str)]
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError("Gemini 응답에서 텍스트 candidate를 찾지 못했습니다.") from error
    if not texts:
        raise RuntimeError("Gemini가 빈 텍스트 응답을 반환했습니다.")
    return "".join(texts)


class GeminiModel(ModelAdapter):
    def generate(self, problem: Problem, settings: ProviderSettings) -> ModelOutput:
        response = call_gemini(prompt=problem.prompt, settings=settings)
        return ModelOutput(extract_text(response), response)


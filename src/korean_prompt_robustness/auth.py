"""API 키 값을 파일에 저장하지 않고 환경변수에서만 읽습니다."""

from __future__ import annotations

import os

from .config import ProviderSettings


FALLBACK_KEY_ENVS = {
    "gemini": "GEMINI_API_KEY",
    "openai-compatible": "OPENAI_API_KEY",
}


def find_api_key(settings: ProviderSettings) -> tuple[str | None, str | None]:
    """키와 실제로 사용한 환경변수 이름을 반환합니다.

    역할별 키를 우선 사용하고, 기존 도구와의 호환성을 위해 제공업체의
    일반 환경변수를 두 번째로 확인합니다.
    """
    candidates = [settings.api_key_env, FALLBACK_KEY_ENVS.get(settings.provider)]
    for name in candidates:
        if not name:
            continue
        value = os.getenv(name, "").strip()
        if value:
            return value, name
    return None, None


def require_api_key(settings: ProviderSettings) -> str:
    """키가 없으면 실제 API 요청 전에 명확한 오류를 냅니다."""
    key, _ = find_api_key(settings)
    if key:
        return key
    names = [settings.api_key_env, FALLBACK_KEY_ENVS.get(settings.provider)]
    expected = " 또는 ".join(name for name in dict.fromkeys(names) if name)
    raise RuntimeError(f"API 키 환경변수가 없습니다: {expected}")

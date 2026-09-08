"""CLI에서 먼저 저장하는 테스트 모델·Judge 모델 설정."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


SUPPORTED_PROVIDERS = frozenset({"local", "gemini", "openai-compatible"})


@dataclass(frozen=True)
class ProviderSettings:
    """한 모델의 실행 방식과 생성 설정입니다.

    ``local``은 stdin/stdout 기반 로컬 명령, ``gemini``는 Gemini API,
    ``openai-compatible``은 OpenAI 호환 Chat Completions API를 뜻합니다.
    """

    provider: str
    model_id: str
    command: str | None = None
    base_url: str | None = None
    api_key_env: str | None = None
    temperature: float = 0.0
    seed: int | None = None
    max_tokens: int = 1024
    max_retries: int = 2
    retry_delay_seconds: float = 1.0
    timeout_seconds: float = 120.0

    @classmethod
    def from_dict(cls, value: dict[str, Any], field_name: str) -> "ProviderSettings":
        if not isinstance(value, dict):
            raise ValueError(f"{field_name} 설정은 객체여야 합니다.")

        provider = value.get("provider")
        model_id = value.get("model_id")
        if provider not in SUPPORTED_PROVIDERS:
            supported = ", ".join(sorted(SUPPORTED_PROVIDERS))
            raise ValueError(f"{field_name}.provider는 {supported} 중 하나여야 합니다.")
        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError(f"{field_name}.model_id가 필요합니다.")

        command = value.get("command")
        if provider == "local" and (not isinstance(command, str) or not command.strip()):
            raise ValueError(f"local {field_name}에는 command가 필요합니다.")
        base_url = value.get("base_url")
        if provider == "openai-compatible" and (
            not isinstance(base_url, str)
            or not base_url.strip().startswith(("http://", "https://"))
        ):
            raise ValueError(
                f"openai-compatible {field_name}에는 http(s) base_url이 필요합니다."
            )
        api_key_env = value.get("api_key_env")
        if provider != "local" and (
            not isinstance(api_key_env, str) or not api_key_env.strip()
        ):
            raise ValueError(f"API 방식의 {field_name}에는 api_key_env가 필요합니다.")

        settings = cls(
            provider=provider,
            model_id=model_id.strip(),
            command=command.strip() if isinstance(command, str) else None,
            base_url=base_url.rstrip("/") if isinstance(base_url, str) else None,
            api_key_env=api_key_env.strip() if isinstance(api_key_env, str) else None,
            temperature=float(value.get("temperature", 0.0)),
            seed=value.get("seed"),
            max_tokens=int(value.get("max_tokens", 1024)),
            max_retries=int(value.get("max_retries", 2)),
            retry_delay_seconds=float(value.get("retry_delay_seconds", 1.0)),
            timeout_seconds=float(value.get("timeout_seconds", 120.0)),
        )
        if settings.seed is not None and (
            isinstance(settings.seed, bool) or not isinstance(settings.seed, int)
        ):
            raise ValueError(f"{field_name}.seed는 정수 또는 null이어야 합니다.")
        if settings.max_tokens <= 0 or settings.max_retries < 0:
            raise ValueError("max_tokens는 양수, max_retries는 0 이상이어야 합니다.")
        if settings.timeout_seconds <= 0 or settings.retry_delay_seconds < 0:
            raise ValueError("timeout_seconds는 양수, retry_delay_seconds는 0 이상이어야 합니다.")
        return settings

    def public_dict(self) -> dict[str, Any]:
        """API 키가 들어가지 않는 저장용 설정을 반환합니다."""
        return asdict(self)


@dataclass(frozen=True)
class RunConfig:
    test_model: ProviderSettings
    judge_model: ProviderSettings

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RunConfig":
        if not isinstance(value, dict):
            raise ValueError("설정 최상위 값은 객체여야 합니다.")
        return cls(
            test_model=ProviderSettings.from_dict(
                value.get("test_model", {}), "test_model"
            ),
            judge_model=ProviderSettings.from_dict(
                value.get("judge_model", {}), "judge_model"
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_model": self.test_model.public_dict(),
            "judge_model": self.judge_model.public_dict(),
        }


def save_config(path: Path, config: RunConfig) -> None:
    """사전 설정을 UTF-8 JSON으로 저장합니다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(config.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_config(path: Path) -> RunConfig:
    if not path.exists():
        raise ValueError(
            "사전 설정이 없습니다. 먼저 'kpr configure' 명령을 실행하세요."
        )
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"설정 파일의 JSON 형식이 잘못되었습니다: {path}") from error
    return RunConfig.from_dict(value)


def make_provider_settings(
    provider: str,
    model_id: str,
    command: str | None,
    *,
    base_url: str | None,
    api_key_env: str | None,
    timeout_seconds: float,
) -> ProviderSettings:
    """configure 명령의 인자로 모델 설정을 만듭니다."""
    if provider == "local" and not command:
        command = f"ollama run {model_id}"
    return ProviderSettings.from_dict(
        {
            "provider": provider,
            "model_id": model_id,
            "command": command,
            "base_url": base_url,
            "api_key_env": api_key_env,
            "timeout_seconds": timeout_seconds,
        },
        "model",
    )

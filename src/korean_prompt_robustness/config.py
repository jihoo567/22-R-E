"""실행 설정 스키마."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .io import read_json


TEST_MODEL_PROVIDERS = frozenset({"gemini", "local", "mock"})
JUDGE_PROVIDERS = frozenset({"gemini", "local"})


@dataclass(frozen=True)
class ProviderSettings:
    provider: str
    model_id: str
    temperature: float = 0.0
    seed: int | None = None
    max_tokens: int = 1024
    max_retries: int = 2
    retry_delay_seconds: float = 1.0
    timeout_seconds: float = 60.0
    command: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ProviderSettings":
        if not isinstance(value, dict):
            raise ValueError("모델 설정은 객체여야 합니다.")
        provider = value.get("provider")
        model_id = value.get("model_id")
        if not isinstance(provider, str) or not provider:
            raise ValueError("provider가 필요합니다.")
        if not isinstance(model_id, str) or not model_id:
            raise ValueError("model_id가 필요합니다.")
        settings = cls(
            provider=provider,
            model_id=model_id,
            temperature=float(value.get("temperature", 0.0)),
            seed=value.get("seed"),
            max_tokens=int(value.get("max_tokens", 1024)),
            max_retries=int(value.get("max_retries", 2)),
            retry_delay_seconds=float(value.get("retry_delay_seconds", 1.0)),
            timeout_seconds=float(value.get("timeout_seconds", 60.0)),
            command=value.get("command"),
        )
        if settings.seed is not None and (
            isinstance(settings.seed, bool) or not isinstance(settings.seed, int)
        ):
            raise ValueError("seed는 정수 또는 null이어야 합니다.")
        if settings.max_tokens <= 0 or settings.max_retries < 0:
            raise ValueError("max_tokens는 양수, max_retries는 0 이상이어야 합니다.")
        return settings

    def public_dict(self) -> dict[str, Any]:
        """비밀값을 포함하지 않는 저장·fingerprint용 설정입니다."""
        return asdict(self)


@dataclass(frozen=True)
class JudgeSettings(ProviderSettings):
    prompt_version: str = "judge-ko-v1"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "JudgeSettings":
        base = ProviderSettings.from_dict(value)
        prompt_version = value.get("prompt_version", "judge-ko-v1")
        if not isinstance(prompt_version, str) or not prompt_version:
            raise ValueError("judge.prompt_version이 필요합니다.")
        return cls(**asdict(base), prompt_version=prompt_version)


@dataclass(frozen=True)
class RunConfig:
    dataset_version: str
    scoring_mode: str
    rule_evaluator_version: str
    pass_threshold: float
    test_model: ProviderSettings
    judge_model: JudgeSettings
    allow_mock_judge: bool = False

    @property
    def model(self) -> ProviderSettings:
        """이전 코드용 별칭입니다. 새 코드에서는 test_model을 사용합니다."""
        return self.test_model

    @property
    def judge(self) -> JudgeSettings:
        """이전 코드용 별칭입니다. 새 코드에서는 judge_model을 사용합니다."""
        return self.judge_model

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RunConfig":
        mode = value.get("scoring_mode", "hybrid")
        if mode not in {"rule_only", "judge_only", "hybrid"}:
            raise ValueError("scoring_mode은 rule_only, judge_only, hybrid 중 하나입니다.")
        dataset_version = value.get("dataset_version")
        evaluator_version = value.get("rule_evaluator_version", "1.0.0")
        if not isinstance(dataset_version, str) or not dataset_version:
            raise ValueError("dataset_version이 필요합니다.")
        if not isinstance(evaluator_version, str) or not evaluator_version:
            raise ValueError("rule_evaluator_version이 필요합니다.")
        threshold = float(value.get("pass_threshold", 100.0))
        if not 0 <= threshold <= 100:
            raise ValueError("pass_threshold는 0~100이어야 합니다.")
        test_model_value = value.get("test_model", value.get("model", {}))
        judge_model_value = value.get("judge_model", value.get("judge", {}))
        test_model = ProviderSettings.from_dict(test_model_value)
        judge_model = JudgeSettings.from_dict(judge_model_value)
        allow_mock_judge = value.get("allow_mock_judge", False)
        if not isinstance(allow_mock_judge, bool):
            raise ValueError("allow_mock_judge는 true 또는 false여야 합니다.")
        if test_model.provider not in TEST_MODEL_PROVIDERS:
            supported = ", ".join(sorted(TEST_MODEL_PROVIDERS))
            raise ValueError(f"지원하지 않는 test_model provider입니다: {test_model.provider} ({supported})")
        if test_model.provider == "local" and not test_model.command:
            raise ValueError("local test_model에는 command가 필요합니다.")
        if judge_model.provider == "mock":
            if not allow_mock_judge:
                raise ValueError(
                    "Mock Judge는 자동 테스트 전용입니다. 테스트 구성에서 "
                    "allow_mock_judge=true를 명시하세요."
                )
        elif judge_model.provider not in JUDGE_PROVIDERS:
            supported = ", ".join(sorted(JUDGE_PROVIDERS))
            raise ValueError(
                f"지원하지 않는 judge_model provider입니다: "
                f"{judge_model.provider} (지원: {supported})"
            )
        if judge_model.provider == "local" and not judge_model.command:
            raise ValueError("local judge_model에는 command가 필요합니다.")
        return cls(
            dataset_version=dataset_version,
            scoring_mode=mode,
            rule_evaluator_version=evaluator_version,
            pass_threshold=threshold,
            test_model=test_model,
            judge_model=judge_model,
            allow_mock_judge=allow_mock_judge,
        )


def load_config(path: Path) -> RunConfig:
    return RunConfig.from_dict(read_json(path))

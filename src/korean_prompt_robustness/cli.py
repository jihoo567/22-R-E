"""사전 설정 후 콘솔에서 실행하는 최소 벤치마크 CLI."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

from .auth import FALLBACK_KEY_ENVS, find_api_key
from .config import (
    RunConfig,
    load_config,
    make_provider_settings,
    save_config,
)
from .judges import create_judge
from .local_process import command_executable
from .models import create_model
from .runners import run_benchmark
from .schemas import load_and_validate_dataset


# 모든 안내와 Windows 래퍼는 프로젝트 루트에서 CLI를 실행합니다.
# 설치 위치가 아닌 실행 위치를 기준으로 .env와 .kpr을 찾습니다.
PROJECT_ROOT = Path.cwd()
DEFAULT_SETTINGS_PATH = PROJECT_ROOT / ".kpr" / "config.json"
DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"
DEFAULT_LOCAL_MODEL = "qwen2.5:14b"
PROVIDER_CHOICES = ("local", "gemini", "openai-compatible")


def _load_env_file(path: Path) -> None:
    """간단한 KEY=VALUE 파일에서 아직 없는 환경변수만 읽습니다."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


def _model_id(provider: str, requested: str | None, role: str) -> str:
    if requested:
        return requested
    if provider == "gemini":
        return DEFAULT_GEMINI_MODEL
    if provider == "local":
        return DEFAULT_LOCAL_MODEL
    raise ValueError(f"{role}에 openai-compatible을 선택하면 모델 ID가 필요합니다.")


def _validate_runtime(config: RunConfig) -> None:
    """첫 문제를 보내기 전에 API 키와 로컬 명령을 검사합니다."""
    for role, settings in (
        ("테스트 모델", config.test_model),
        ("Judge 모델", config.judge_model),
    ):
        if settings.provider != "local":
            api_key, _ = find_api_key(settings)
            if not api_key:
                fallback = FALLBACK_KEY_ENVS.get(settings.provider)
                expected = settings.api_key_env
                alternatives = " 또는 ".join(
                    name for name in (expected, fallback) if name
                )
                raise ValueError(
                    f"{role}({settings.provider}) API 키가 없습니다. "
                    f".env에 {alternatives}=실제키를 입력하세요."
                )
            continue

        assert settings.command is not None
        executable = command_executable(settings.command)
        if shutil.which(executable) is None:
            raise ValueError(
                f"{role}의 로컬 실행 파일을 찾을 수 없습니다: {executable}"
            )


def _add_settings_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--settings",
        type=Path,
        default=DEFAULT_SETTINGS_PATH,
        help=argparse.SUPPRESS,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kpr",
        description="사전 설정한 테스트 모델과 Judge 모델을 콘솔에서 실행합니다.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    configure = subparsers.add_parser(
        "configure", help="테스트 모델과 Judge 모델을 먼저 설정"
    )
    configure.add_argument(
        "--test", choices=PROVIDER_CHOICES, required=True, help="테스트 모델 방식"
    )
    configure.add_argument(
        "--judge", choices=PROVIDER_CHOICES, required=True, help="Judge 모델 방식"
    )
    configure.add_argument("--test-model", help="테스트 모델 ID")
    configure.add_argument("--judge-model", help="Judge 모델 ID")
    configure.add_argument(
        "--test-command", help="테스트 로컬 명령(기본값: ollama run <모델 ID>)"
    )
    configure.add_argument(
        "--judge-command", help="Judge 로컬 명령(기본값: ollama run <모델 ID>)"
    )
    configure.add_argument(
        "--test-base-url", help="테스트 OpenAI 호환 API의 base URL"
    )
    configure.add_argument(
        "--judge-base-url", help="Judge OpenAI 호환 API의 base URL"
    )
    _add_settings_argument(configure)

    show = subparsers.add_parser("show-config", help="현재 사전 설정 표시")
    _add_settings_argument(show)

    validate = subparsers.add_parser("validate", help="문제 JSONL 검증")
    validate.add_argument("input", type=Path, help="문제 JSONL 경로")

    run = subparsers.add_parser(
        "run", help="문제 → 테스트 모델 → Judge 실행 후 콘솔 출력"
    )
    run.add_argument("input", type=Path, help="문제 JSONL 경로")
    run.add_argument("--limit", type=int, help="앞에서부터 실행할 문제 수")
    _add_settings_argument(run)
    return parser


def _configure(args: argparse.Namespace) -> None:
    test_model_id = _model_id(args.test, args.test_model, "테스트 모델")
    judge_model_id = _model_id(args.judge, args.judge_model, "Judge 모델")
    config = RunConfig(
        test_model=make_provider_settings(
            args.test,
            test_model_id,
            args.test_command,
            base_url=args.test_base_url,
            api_key_env=(
                "KPR_TEST_API_KEY" if args.test != "local" else None
            ),
            timeout_seconds=300.0 if args.test == "local" else 120.0,
        ),
        judge_model=make_provider_settings(
            args.judge,
            judge_model_id,
            args.judge_command,
            base_url=args.judge_base_url,
            api_key_env=(
                "KPR_JUDGE_API_KEY" if args.judge != "local" else None
            ),
            timeout_seconds=300.0 if args.judge == "local" else 120.0,
        ),
    )
    save_config(args.settings, config)
    print(f"사전 설정 완료: {args.settings}")
    print(f"테스트 모델: {args.test} / {test_model_id}")
    print(f"Judge 모델: {args.judge} / {judge_model_id}")
    if args.test != "local":
        print("테스트 API 키: .env의 KPR_TEST_API_KEY")
    if args.judge != "local":
        print("Judge API 키: .env의 KPR_JUDGE_API_KEY")


def _run(args: argparse.Namespace) -> None:
    config = load_config(args.settings)
    _validate_runtime(config)
    problems = load_and_validate_dataset(args.input)
    if args.limit is not None:
        if args.limit <= 0:
            raise ValueError("--limit은 1 이상의 정수여야 합니다.")
        problems = problems[: args.limit]
    if not problems:
        raise ValueError("실행할 문제가 없습니다.")

    print(
        f"테스트 모델: {config.test_model.provider} / {config.test_model.model_id}"
    )
    print(
        f"Judge 모델: {config.judge_model.provider} / {config.judge_model.model_id}"
    )
    failed = run_benchmark(
        problems,
        config,
        create_model(config.test_model),
        create_judge(config.judge_model),
    )
    if failed:
        raise RuntimeError(f"{failed}개 문제에서 모델 실행 또는 평가가 실패했습니다.")


def main(argv: list[str] | None = None) -> None:
    _load_env_file(PROJECT_ROOT / ".env")
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "configure":
            _configure(args)
        elif args.command == "show-config":
            config = load_config(args.settings)
            print(json.dumps(config.to_dict(), ensure_ascii=False, indent=2))
        elif args.command == "validate":
            problems = load_and_validate_dataset(args.input)
            print(f"검증 성공: {len(problems)}개 문제")
        else:
            _run(args)
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()

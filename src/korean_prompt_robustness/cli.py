"""사전 설정 후 콘솔에서 실행하는 최소 벤치마크 CLI."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

from .auth import FALLBACK_KEY_ENVS, find_api_key
from .config import RunConfig, load_config
from .dataset import load_and_validate_dataset
from .local_process import command_executable
from .pipeline import run_benchmark


# 모든 런처는 프로젝트 루트에서 CLI를 실행합니다. 사용자가 일반 편집기로
# 바로 수정할 수 있도록 설정 파일을 숨김 폴더 밖에 둡니다.
DEFAULT_SETTINGS_PATH = Path("kpr-config.json")


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
        epilog="설정 파일: kpr-config.json | 설정 설명: CONFIG_GUIDE.md",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

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


def _run(args: argparse.Namespace) -> None:
    config = load_config(args.settings)
    _validate_runtime(config)
    problems = load_and_validate_dataset(args.input, limit=args.limit)

    print(
        f"테스트 모델: {config.test_model.provider} / {config.test_model.model_id}"
    )
    print(
        f"Judge 모델: {config.judge_model.provider} / {config.judge_model.model_id}"
    )
    failed = run_benchmark(problems, config)
    if failed:
        raise RuntimeError(f"{failed}개 문제에서 모델 실행 또는 평가가 실패했습니다.")


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        _load_env_file(Path(".env"))
        if args.command == "show-config":
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

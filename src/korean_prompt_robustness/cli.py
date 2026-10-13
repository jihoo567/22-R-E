"""사전 설정 후 콘솔에서 실행하는 최소 벤치마크 CLI."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from .auth import FALLBACK_KEY_ENVS, find_api_key
from .config import ProviderSettings, RunConfig, load_config
from .dataset import load_and_validate_dataset
from .local_process import command_executable
from .pipeline import evaluate_answers, generate_answers
from .responses import latest_response_file, load_saved_responses


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


def _validate_model(settings: ProviderSettings, role: str) -> None:
    """호출할 모델 하나의 API 키 또는 로컬 명령을 검사합니다."""
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
        return

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

    answer = subparsers.add_parser(
        "answer", help="문제를 테스트 모델에 보내 답변 생성 및 저장"
    )
    answer.add_argument(
        "input",
        type=Path,
        nargs="?",
        help="문제 JSONL 경로(생략하면 설정의 input_path 사용)",
    )
    answer.add_argument("--limit", type=int, help="앞에서부터 실행할 문제 수")
    _add_settings_argument(answer)

    test = subparsers.add_parser(
        "test", help="가장 최근에 저장된 테스트 답변을 Judge로 평가"
    )
    _add_settings_argument(test)
    return parser


def _output_dir(config: RunConfig, settings_path: Path) -> Path:
    output_dir = Path(config.output_dir).expanduser()
    if not output_dir.is_absolute():
        output_dir = settings_path.parent / output_dir
    return output_dir


def _answer(args: argparse.Namespace) -> None:
    config = load_config(args.settings)
    _validate_model(config.test_model, "테스트 모델")
    input_path = args.input
    if input_path is None:
        if config.input_path is None:
            raise ValueError(
                "문제 JSONL 경로가 없습니다. answer 뒤에 경로를 입력하거나 "
                "kpr-config.json의 input_path를 설정하세요."
            )
        input_path = Path(config.input_path).expanduser()
        if not input_path.is_absolute():
            input_path = args.settings.parent / input_path
    problems = load_and_validate_dataset(input_path, limit=args.limit)

    print(
        f"테스트 모델: {config.test_model.provider} / {config.test_model.model_id}"
    )
    output_dir = _output_dir(config, args.settings)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
    response_path = output_dir / f"test-responses-{timestamp}.jsonl"
    print(f"테스트 모델 응답 저장: {response_path}")
    with response_path.open("x", encoding="utf-8") as response_output:
        failed = generate_answers(
            problems,
            config.test_model,
            response_output=response_output,
        )
    if failed:
        raise RuntimeError(f"{failed}개 문제에서 답변 생성이 실패했습니다.")


def _test(args: argparse.Namespace) -> None:
    config = load_config(args.settings)
    _validate_model(config.judge_model, "Judge 모델")
    response_path = latest_response_file(_output_dir(config, args.settings))
    responses = load_saved_responses(response_path)
    print(
        f"Judge 모델: {config.judge_model.provider} / {config.judge_model.model_id}"
    )
    print(f"평가 대상 응답 파일: {response_path}")
    failed = evaluate_answers(responses, config.judge_model)
    if failed:
        raise RuntimeError(f"{failed}개 답변 평가가 실패했습니다.")


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
        elif args.command == "answer":
            _answer(args)
        else:
            _test(args)
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()

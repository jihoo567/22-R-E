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

    variants = subparsers.add_parser(
        "variants",
        help="원본 문제의 조사·생략 변형 문제 JSONL 생성",
        description=(
            "원본 문제마다 조사 변형(particle)과 생략 변형(omission)을 만들어 "
            "answer에서 바로 쓸 수 있는 문제 JSONL로 저장합니다."
        ),
    )
    variants.add_argument(
        "input",
        type=Path,
        nargs="?",
        help="원본 문제 JSONL 경로(생략하면 설정의 input_path 사용)",
    )
    variants.add_argument(
        "-o",
        "--output",
        type=Path,
        help="저장할 JSONL 경로(생략하면 입력 옆 '<이름>-variants.jsonl')",
    )
    variants.add_argument(
        "--types",
        default="particle,omission",
        help="만들 변형 종류를 쉼표로 (기본: %(default)s)",
    )
    variants.add_argument(
        "--per-type", type=int, default=3, help="종류별 변형 수 (기본: %(default)s)"
    )
    variants.add_argument(
        "--mixed",
        type=int,
        default=8,
        help="여러 종류를 섞은 변형 수, 0이면 만들지 않음 (기본: %(default)s)",
    )
    variants.add_argument("--seed", type=int, default=0, help="난수 시드 (기본: %(default)s)")
    variants.add_argument(
        "--keep-existing",
        action="store_true",
        help="입력에 있던 변형 문제도 함께 저장(새 번호는 기존 번호 뒤에 이어 붙임)",
    )
    variants.add_argument(
        "--force", action="store_true", help="출력 파일이 이미 있으면 덮어쓰기"
    )
    _add_settings_argument(variants)
    return parser


def _output_dir(config: RunConfig, settings_path: Path) -> Path:
    output_dir = Path(config.output_dir).expanduser()
    if not output_dir.is_absolute():
        output_dir = settings_path.parent / output_dir
    return output_dir


def _input_path(args: argparse.Namespace, config: RunConfig | None) -> Path:
    """명령행 경로를 우선하고, 없으면 설정의 input_path를 씁니다."""
    if args.input is not None:
        return args.input
    if config is None:
        config = load_config(args.settings)
    if config.input_path is None:
        raise ValueError(
            f"문제 JSONL 경로가 없습니다. {args.command} 뒤에 경로를 입력하거나 "
            "kpr-config.json의 input_path를 설정하세요."
        )
    input_path = Path(config.input_path).expanduser()
    if not input_path.is_absolute():
        input_path = args.settings.parent / input_path
    return input_path


def _answer(args: argparse.Namespace) -> None:
    config = load_config(args.settings)
    _validate_model(config.test_model, "테스트 모델")
    input_path = _input_path(args, config)
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


def _variants(args: argparse.Namespace) -> None:
    input_path = _input_path(args, None)
    output_path = args.output or input_path.with_name(f"{input_path.stem}-variants.jsonl")
    if output_path.resolve() == input_path.resolve():
        raise ValueError("출력 경로가 입력 문제 파일과 같습니다. -o로 다른 경로를 지정하세요.")
    if output_path.exists() and not args.force:
        raise ValueError(f"출력 파일이 이미 있습니다: {output_path} (덮어쓰려면 --force)")
    for name in ("per_type", "mixed"):
        if getattr(args, name) < 0:
            raise ValueError(f"--{name.replace('_', '-')}은 0 이상이어야 합니다.")

    # kiwipiepy를 불러오므로 이 명령에서만 import합니다.
    try:
        from .variants import export
    except ImportError as error:
        raise RuntimeError(
            f"변형 생성에 필요한 패키지를 불러오지 못했습니다({error.name}). "
            "./kpr --help 또는 kpr.bat --help를 한 번 실행하면 자동으로 설치됩니다."
        ) from error

    load_and_validate_dataset(input_path)  # answer와 같은 규칙으로 먼저 검사
    with input_path.open(encoding="utf-8") as file:
        records = [json.loads(line) for line in file if line.strip()]
    print(f"변형 생성 중: {input_path}", flush=True)
    problems = export(
        records,
        types=[t.strip() for t in args.types.split(",") if t.strip()],
        per_type=args.per_type,
        mixed=args.mixed,
        seed=args.seed,
        keep_existing=args.keep_existing,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as output:
        for problem in problems:
            output.write(json.dumps(problem, ensure_ascii=False, separators=(",", ":")))
            output.write("\n")

    counts: dict[str, int] = {}
    for problem in problems:
        variant_type = problem["metadata"].get("variant_type", "?")
        counts[variant_type] = counts.get(variant_type, 0) + 1
    summary = ", ".join(f"{name} {count}" for name, count in counts.items())
    print(f"저장: {output_path} ({len(problems)}개 문제: {summary})")
    print(f"실행: kpr answer {output_path}")


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
        elif args.command == "variants":
            _variants(args)
        else:
            _test(args)
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()

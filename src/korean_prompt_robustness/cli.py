"""단계별 실행이 가능한 명령행 인터페이스."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from .config import RunConfig, load_config
from .io import make_run_id, read_json, read_jsonl, replace_jsonl, write_json
from .judges import create_judge
from .metrics import calculate_robustness
from .models import create_model
from .reports import create_csv_reports, print_console_summary
from .runners import (
    finalize_scores,
    generate_responses,
    judge_responses,
    score_rule_responses,
)
from .schemas import load_and_validate_dataset


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PROJECT_ROOT.parent


def _judge_stage_label(config: RunConfig) -> str:
    if config.judge_model.provider == "mock":
        return "Mock Judge 평가(자동 테스트 전용)"
    if config.judge_model.provider == "local":
        return "로컬 Judge 평가"
    return "API Judge 평가"


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


def _paths(base: Path, run_id: str) -> dict[str, Path]:
    return {
        "responses": base / "responses" / f"{run_id}.jsonl",
        "response_cache": base / "responses" / "cache.jsonl",
        "judgments": base / "judgments" / f"{run_id}.jsonl",
        "judge_cache": base / "judgments" / "cache.jsonl",
        "rules": base / "scores" / f"{run_id}.rules.jsonl",
        "final": base / "scores" / f"{run_id}.final.jsonl",
        "pairs": base / "scores" / f"{run_id}.comparisons.jsonl",
        "metrics": base / "scores" / f"{run_id}.metrics.json",
        "reports": base / "reports" / run_id,
    }


def run_pipeline(
    input_path: Path,
    config: RunConfig,
    run_id: str,
    result_base: Path,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    problems = load_and_validate_dataset(input_path)
    paths = _paths(result_base, run_id)
    print(
        f"[1/5] 테스트 모델 응답 생성: "
        f"{config.test_model.provider}/{config.test_model.model_id}",
        flush=True,
    )
    responses, generation_counts = generate_responses(
        problems,
        config,
        create_model(config.test_model),
        run_id,
        paths["responses"],
        paths["response_cache"],
        repo_root,
    )
    rule_scores = (
        score_rule_responses(
            problems, responses, config, run_id, paths["rules"], repo_root
        )
        if config.scoring_mode != "judge_only"
        else []
    )
    if config.scoring_mode != "judge_only":
        print(f"[2/5] 규칙 채점 완료: {len(rule_scores)}건", flush=True)
    judgments: list[dict[str, Any]] = []
    judge_counts = {"judged": 0, "cached": 0, "skipped": 0, "failed": 0}
    if config.scoring_mode != "rule_only":
        print(
            f"[3/5] {_judge_stage_label(config)}: "
            f"{config.judge_model.provider}/{config.judge_model.model_id}",
            flush=True,
        )
        judgments, judge_counts = judge_responses(
            problems,
            responses,
            config,
            create_judge(
                config.judge_model, allow_mock_judge=config.allow_mock_judge
            ),
            run_id,
            paths["judgments"],
            paths["judge_cache"],
            repo_root,
        )
    final_records = finalize_scores(
        problems,
        responses,
        rule_scores,
        judgments,
        config,
        run_id,
        paths["final"],
        repo_root,
    )
    pairs, summary = calculate_robustness(final_records, config.pass_threshold)
    print("[4/5] 원본·변형 강건성 지표 계산 완료", flush=True)
    replace_jsonl(paths["pairs"], pairs)
    write_json(paths["metrics"], summary)
    report_paths = create_csv_reports(final_records, pairs, summary, paths["reports"])
    print(f"[5/5] CSV 보고서 생성 완료: {paths['reports']}", flush=True)
    print_console_summary(summary)
    return {
        "run_id": run_id,
        "paths": {key: str(value) for key, value in paths.items()},
        "generation_counts": generation_counts,
        "judge_counts": judge_counts,
        "summary": summary,
        "report_paths": [str(path) for path in report_paths],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kpr", description="준비된 원본·변형 문제 실행/채점/비교 도구"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="입력 JSONL 검증")
    validate.add_argument("--input", type=Path, required=True)

    common_help = "설정 JSON"
    generate = subparsers.add_parser("generate", help="모델 응답 생성")
    generate.add_argument("--input", type=Path, required=True)
    generate.add_argument("--config", type=Path, required=True, help=common_help)
    generate.add_argument("--run-id", required=True)
    generate.add_argument("--result-base", type=Path, default=PROJECT_ROOT / "results")

    rules = subparsers.add_parser("score-rules", help="저장 응답 규칙 재채점")
    rules.add_argument("--input", type=Path, required=True)
    rules.add_argument("--responses", type=Path, required=True)
    rules.add_argument("--config", type=Path, required=True, help=common_help)
    rules.add_argument("--run-id", required=True)
    rules.add_argument("--output", type=Path, required=True)

    judge = subparsers.add_parser("score-judge", help="저장 응답 Judge 채점")
    judge.add_argument("--input", type=Path, required=True)
    judge.add_argument("--responses", type=Path, required=True)
    judge.add_argument("--config", type=Path, required=True, help=common_help)
    judge.add_argument("--run-id", required=True)
    judge.add_argument("--output", type=Path, required=True)
    judge.add_argument("--cache", type=Path, required=True)

    metrics = subparsers.add_parser("metrics", help="최종 점수와 강건성 지표 계산")
    metrics.add_argument("--input", type=Path, required=True)
    metrics.add_argument("--responses", type=Path, required=True)
    metrics.add_argument("--rule-scores", type=Path)
    metrics.add_argument("--judgments", type=Path)
    metrics.add_argument("--config", type=Path, required=True, help=common_help)
    metrics.add_argument("--run-id", required=True)
    metrics.add_argument("--final-output", type=Path, required=True)
    metrics.add_argument("--pairs-output", type=Path, required=True)
    metrics.add_argument("--summary-output", type=Path, required=True)

    report = subparsers.add_parser("report", help="CSV 보고서 생성")
    report.add_argument("--scores", type=Path, required=True)
    report.add_argument("--comparisons", type=Path, required=True)
    report.add_argument("--summary", type=Path, required=True)
    report.add_argument("--output-dir", type=Path, required=True)

    all_parser = subparsers.add_parser("run-all", help="전체 평가 파이프라인")
    all_parser.add_argument("--input", type=Path, required=True)
    all_parser.add_argument("--config", type=Path, required=True, help=common_help)
    all_parser.add_argument("--run-id")
    all_parser.add_argument("--result-base", type=Path, default=PROJECT_ROOT / "results")
    return parser


def main(argv: list[str] | None = None) -> None:
    _load_env_file(PROJECT_ROOT / ".env")
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        problems = load_and_validate_dataset(args.input)
        print(f"검증 성공: {len(problems)}개 문제, {len({p.parent_id for p in problems})}개 parent_id")
        return
    if args.command == "generate":
        config = load_config(args.config)
        problems = load_and_validate_dataset(args.input)
        paths = _paths(args.result_base, args.run_id)
        print(
            f"테스트 모델 응답 생성: "
            f"{config.test_model.provider}/{config.test_model.model_id}",
            flush=True,
        )
        _, counts = generate_responses(
            problems,
            config,
            create_model(config.test_model),
            args.run_id,
            paths["responses"],
            paths["response_cache"],
            REPO_ROOT,
        )
        print(f"응답 파일: {paths['responses']}")
        print(f"처리 결과: {counts}")
        return
    if args.command == "score-rules":
        config = load_config(args.config)
        records = score_rule_responses(
            load_and_validate_dataset(args.input),
            read_jsonl(args.responses),
            config,
            args.run_id,
            args.output,
            REPO_ROOT,
        )
        print(f"규칙 채점 완료: {len(records)}건, {args.output}")
        return
    if args.command == "score-judge":
        config = load_config(args.config)
        print(
            f"{_judge_stage_label(config)}: "
            f"{config.judge_model.provider}/{config.judge_model.model_id}",
            flush=True,
        )
        records, counts = judge_responses(
            load_and_validate_dataset(args.input),
            read_jsonl(args.responses),
            config,
            create_judge(
                config.judge_model, allow_mock_judge=config.allow_mock_judge
            ),
            args.run_id,
            args.output,
            args.cache,
            REPO_ROOT,
        )
        print(f"Judge 채점 완료: {len(records)}건, {counts}, {args.output}")
        return
    if args.command == "metrics":
        config = load_config(args.config)
        problems = load_and_validate_dataset(args.input)
        final_records = finalize_scores(
            problems,
            read_jsonl(args.responses),
            read_jsonl(args.rule_scores, missing_ok=True) if args.rule_scores else [],
            read_jsonl(args.judgments, missing_ok=True) if args.judgments else [],
            config,
            args.run_id,
            args.final_output,
            REPO_ROOT,
        )
        pairs, summary = calculate_robustness(final_records, config.pass_threshold)
        replace_jsonl(args.pairs_output, pairs)
        write_json(args.summary_output, summary)
        print_console_summary(summary)
        return
    if args.command == "report":
        paths = create_csv_reports(
            read_jsonl(args.scores),
            read_jsonl(args.comparisons),
            read_json(args.summary),
            args.output_dir,
        )
        print(f"CSV 보고서 {len(paths)}개 생성: {args.output_dir}")
        return
    if args.command == "run-all":
        run_id = args.run_id or make_run_id("experiment")
        result = run_pipeline(
            args.input, load_config(args.config), run_id, args.result_base
        )
        print(f"실행 ID: {result['run_id']}")
        print(f"결과 디렉터리: {args.result_base}")

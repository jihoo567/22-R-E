"""사람이 확인하기 쉬운 7개 CSV 보고서와 콘솔 요약."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    field: json.dumps(value, ensure_ascii=False)
                    if isinstance(value, (dict, list))
                    else value
                    for field, value in row.items()
                }
            )


def create_csv_reports(
    final_records: list[dict[str, Any]],
    pairs: list[dict[str, Any]],
    summary: dict[str, Any],
    output_dir: Path,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    delta_by_variant = {pair.get("variant_id"): pair.get("score_difference") for pair in pairs}
    details = [
        {
            **record,
            "score_difference": delta_by_variant.get(record["problem_id"]),
            "rule_result": record.get("rule_result"),
            "judge_result": record.get("judge_result"),
        }
        for record in final_records
    ]
    files: list[tuple[str, list[dict[str, Any]], list[str]]] = [
        (
            "problem_details.csv",
            details,
            [
                "run_id", "problem_id", "parent_id", "variant_type", "category",
                "model_id", "input_prompt", "raw_model_response", "rule_score",
                "judge_score", "final_score", "score_difference", "conflict",
                "human_review_required", "rule_result", "judge_result",
                "generation_attempts", "judge_attempts",
            ],
        ),
        (
            "pair_comparisons.csv",
            pairs,
            [
                "parent_id", "original_id", "variant_id", "variant_type", "category",
                "original_score", "variant_score", "score_difference", "score_drop",
                "both_succeeded", "original_pass_variant_fail", "success_consistent",
                "excluded", "exclusion_reason",
            ],
        ),
        (
            "model_summary.csv",
            [summary],
            [
                "model_id", "original_average_score", "variant_average_score",
                "average_score_difference", "average_score_drop", "both_succeeded_rate",
                "original_pass_variant_fail_rate", "success_consistency_rate",
                "robust_accuracy", "conflict_count", "human_review_count",
                "robust_parent_count", "robust_parent_denominator",
                "eligible_pair_count", "excluded_pair_count",
            ],
        ),
        (
            "variant_type_summary.csv",
            [{"variant_type": key, **value} for key, value in summary["variant_type_summary"].items()],
            [
                "variant_type", "pair_count", "average_original_score",
                "average_variant_score", "average_score_difference", "average_score_drop",
            ],
        ),
        (
            "category_summary.csv",
            [{"category": key, **value} for key, value in summary["category_summary"].items()],
            [
                "category", "pair_count", "average_original_score",
                "average_variant_score", "average_score_difference", "average_score_drop",
            ],
        ),
        (
            "conflicts.csv",
            [record for record in details if record.get("conflict")],
            [
                "problem_id", "parent_id", "variant_type", "rule_score", "judge_score",
                "conflict", "human_review_required", "rule_result", "judge_result",
            ],
        ),
        (
            "human_review.csv",
            [record for record in details if record.get("human_review_required")],
            [
                "problem_id", "parent_id", "variant_type", "rule_score", "judge_score",
                "final_score", "conflict", "generation_error", "judge_error",
                "rule_result", "judge_result",
            ],
        ),
    ]
    paths: list[Path] = []
    for filename, rows, fields in files:
        path = output_dir / filename
        _write_csv(path, rows, fields)
        paths.append(path)
    return paths


def _number(value: Any) -> str:
    return "N/A" if value is None else f"{value:.1f}"


def print_console_summary(summary: dict[str, Any]) -> None:
    print(f"모델: {summary.get('model_id') or '알 수 없음'}")
    print(f"원본 평균 점수: {_number(summary.get('original_average_score'))}")
    print(f"변형 평균 점수: {_number(summary.get('variant_average_score'))}")
    print(f"평균 점수 변화: {_number(summary.get('average_score_difference'))}")
    robust = summary.get("robust_accuracy")
    print(f"강건 정확도: {'N/A' if robust is None else f'{robust:.1f}%'}")
    print(f"평가 충돌: {summary.get('conflict_count', 0)}건")
    print(f"사람 검토 필요: {summary.get('human_review_count', 0)}건")

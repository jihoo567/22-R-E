"""parent_id 기반 원본·변형 강건성 지표."""

from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any


def _average(values: list[float]) -> float | None:
    return mean(values) if values else None


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator * 100.0 if denominator else None


def calculate_robustness(
    final_records: list[dict[str, Any]], pass_threshold: float = 100.0
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in final_records:
        by_parent[record["parent_id"]].append(record)
    pairs: list[dict[str, Any]] = []
    eligible_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    robustness_candidate_parents: set[str] = set()
    parent_lowest: dict[str, float] = {}
    for parent_id, group in by_parent.items():
        originals = [item for item in group if item["variant_type"] == "original"]
        variants = [item for item in group if item["variant_type"] != "original"]
        if len(originals) != 1:
            for variant in variants or [{}]:
                pairs.append(
                    {
                        "parent_id": parent_id,
                        "original_id": None,
                        "variant_id": variant.get("problem_id"),
                        "excluded": True,
                        "exclusion_reason": "original 레코드가 정확히 하나가 아님",
                    }
                )
            continue
        original = originals[0]
        if variants:
            robustness_candidate_parents.add(parent_id)
        for variant in variants:
            reason = None
            if original["comparison_condition_key"] != variant["comparison_condition_key"]:
                reason = "모델/Judge/채점기/데이터셋 비교 조건이 다름"
            elif original.get("final_score") is None or variant.get("final_score") is None:
                reason = "최종 점수가 없거나 사람 검토가 필요함"
            original_score = original.get("final_score")
            variant_score = variant.get("final_score")
            record = {
                "record_type": "pair_comparison",
                "run_id": variant["run_id"],
                "parent_id": parent_id,
                "original_id": original["problem_id"],
                "variant_id": variant["problem_id"],
                "variant_type": variant["variant_type"],
                "category": variant.get("category"),
                "model_id": variant.get("model_id"),
                "comparison_condition_key": variant["comparison_condition_key"],
                "original_score": original_score,
                "variant_score": variant_score,
                "score_difference": (
                    variant_score - original_score
                    if reason is None
                    else None
                ),
                "score_drop": (
                    max(original_score - variant_score, 0.0)
                    if reason is None
                    else None
                ),
                "original_passed": original_score is not None
                and original_score >= pass_threshold,
                "variant_passed": variant_score is not None
                and variant_score >= pass_threshold,
                "excluded": reason is not None,
                "exclusion_reason": reason,
            }
            if reason is None:
                record["both_succeeded"] = record["original_passed"] and record["variant_passed"]
                record["original_pass_variant_fail"] = record["original_passed"] and not record["variant_passed"]
                record["success_consistent"] = record["original_passed"] == record["variant_passed"]
                eligible_by_parent[parent_id].append(record)
            else:
                record.update(
                    both_succeeded=None,
                    original_pass_variant_fail=None,
                    success_consistent=None,
                )
            pairs.append(record)
        eligible_scores = [
            item["variant_score"] for item in eligible_by_parent.get(parent_id, [])
        ]
        if eligible_scores:
            parent_lowest[parent_id] = min(eligible_scores)
    eligible = [pair for pair in pairs if not pair["excluded"]]
    original_records = [
        record
        for record in final_records
        if record["variant_type"] == "original" and record.get("final_score") is not None
    ]
    variant_records = [
        record
        for record in final_records
        if record["variant_type"] != "original" and record.get("final_score") is not None
    ]
    all_pairs_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pair in pairs:
        all_pairs_by_parent[pair["parent_id"]].append(pair)
    robust_parent_count = sum(
        bool(all_pairs_by_parent[parent_id])
        and all(
            not pair["excluded"]
            and pair["original_passed"]
            and pair["variant_passed"]
            for pair in all_pairs_by_parent[parent_id]
        )
        for parent_id in robustness_candidate_parents
    )
    robust_parent_denominator = len(robustness_candidate_parents)
    variant_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    category_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pair in eligible:
        variant_groups[str(pair.get("variant_type") or "")].append(pair)
        category_groups[str(pair.get("category") or "")].append(pair)

    def group_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "pair_count": len(items),
            "average_original_score": _average([item["original_score"] for item in items]),
            "average_variant_score": _average([item["variant_score"] for item in items]),
            "average_score_difference": _average([item["score_difference"] for item in items]),
            "average_score_drop": _average([item["score_drop"] for item in items]),
        }

    summary = {
        "model_id": final_records[0].get("model_id") if final_records else None,
        "original_average_score": _average([item["final_score"] for item in original_records]),
        "variant_average_score": _average([item["final_score"] for item in variant_records]),
        "average_score_difference": _average([pair["score_difference"] for pair in eligible]),
        "average_score_drop": _average([pair["score_drop"] for pair in eligible]),
        "both_succeeded_rate": _rate(sum(pair["both_succeeded"] for pair in eligible), len(eligible)),
        "original_pass_variant_fail_rate": _rate(
            sum(pair["original_pass_variant_fail"] for pair in eligible), len(eligible)
        ),
        "success_consistency_rate": _rate(
            sum(pair["success_consistent"] for pair in eligible), len(eligible)
        ),
        "robust_accuracy": _rate(robust_parent_count, robust_parent_denominator),
        "robust_parent_count": robust_parent_count,
        "robust_parent_denominator": robust_parent_denominator,
        "parent_lowest_variant_scores": parent_lowest,
        "eligible_pair_count": len(eligible),
        "excluded_pair_count": len(pairs) - len(eligible),
        "conflict_count": sum(bool(item.get("conflict")) for item in final_records),
        "human_review_count": sum(
            bool(item.get("human_review_required")) for item in final_records
        ),
        "variant_type_summary": {
            key: group_summary(items) for key, items in sorted(variant_groups.items())
        },
        "category_summary": {
            key: group_summary(items) for key, items in sorted(category_groups.items())
        },
    }
    return pairs, summary

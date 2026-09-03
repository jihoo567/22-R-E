"""설정한 채점 방식으로 규칙·Judge 결과를 결합합니다."""

from __future__ import annotations

from typing import Any


def combine_scores(
    mode: str,
    rule_result: dict[str, Any] | None,
    judge_result: dict[str, Any] | None,
    pass_threshold: float = 100.0,
) -> dict[str, Any]:
    rule_score = rule_result.get("score") if rule_result else None
    judge_score = (
        float(judge_result["score"]) * 100.0 if judge_result is not None else None
    )
    rule_pass = rule_score is not None and rule_score >= pass_threshold
    judge_pass = judge_result is not None and judge_result.get("verdict") == "pass"
    conflict = (
        rule_score is not None and judge_score is not None and rule_pass != judge_pass
    )
    human_review = False
    final_score: float | None
    if mode == "rule_only":
        final_score = rule_score
        human_review = final_score is None or bool(rule_result and rule_result["error_count"])
    elif mode == "judge_only":
        final_score = judge_score
        human_review = final_score is None
    elif mode == "hybrid":
        if rule_score is None or judge_score is None or conflict:
            final_score = None
            human_review = True
        else:
            final_score = (rule_score + judge_score) / 2.0
            human_review = bool(rule_result and rule_result["error_count"])
    else:
        raise ValueError(f"지원하지 않는 채점 방식: {mode}")
    return {
        "scoring_mode": mode,
        "rule_score": rule_score,
        "judge_score": judge_score,
        "conflict": conflict,
        "human_review_required": human_review,
        "final_score": final_score,
        "passed": final_score is not None and final_score >= pass_threshold,
    }


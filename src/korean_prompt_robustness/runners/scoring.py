"""저장 응답 재채점과 최종 점수 레코드 생성."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import RunConfig
from ..evaluators import combine_scores, evaluate_rules
from ..io import git_commit, replace_jsonl, stable_hash, utc_now
from ..schemas import Problem


def _latest_by_problem(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """재시도 이력은 보존하되 파생 채점에는 문제별 마지막 응답만 사용합니다."""
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        problem_id = record.get("problem_id")
        if isinstance(problem_id, str):
            latest[problem_id] = record
    return list(latest.values())


def score_rule_responses(
    problems: list[Problem],
    responses: list[dict[str, Any]],
    config: RunConfig,
    run_id: str,
    output_path: Path,
    repo_root: Path,
) -> list[dict[str, Any]]:
    by_id = {problem.id: problem for problem in problems}
    records: list[dict[str, Any]] = []
    for response in _latest_by_problem(responses):
        if response.get("status") != "complete":
            continue
        problem = by_id[response["problem_id"]]
        result = evaluate_rules(
            problem.evaluation_rules,
            response["response"],
            {"problem": problem.raw, "response_record": response},
        )
        records.append(
            {
                "record_type": "rule_score",
                "run_id": run_id,
                "run_at": utc_now(),
                "dataset_version": config.dataset_version,
                "git_commit": git_commit(repo_root),
                "problem_id": problem.id,
                "parent_id": problem.parent_id,
                "variant_type": problem.variant_type,
                "category": problem.metadata.get("category"),
                "response_fingerprint": response["request_fingerprint"],
                "rule_evaluator_version": config.rule_evaluator_version,
                "rule_fingerprint": stable_hash(
                    {
                        "response": response["response"],
                        "rules": [rule.raw for rule in problem.evaluation_rules],
                        "version": config.rule_evaluator_version,
                    }
                ),
                **result,
            }
        )
    # 점수는 응답이 아닌 파생 산출물이므로 같은 명령의 재실행에서 원자적으로 재작성합니다.
    replace_jsonl(output_path, records)
    return records


def finalize_scores(
    problems: list[Problem],
    responses: list[dict[str, Any]],
    rule_scores: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
    config: RunConfig,
    run_id: str,
    output_path: Path,
    repo_root: Path,
) -> list[dict[str, Any]]:
    by_problem = {problem.id: problem for problem in problems}
    rules_by_id = {record["problem_id"]: record for record in rule_scores}
    # 실패 후 재시도 이력까지 최종 사람 검토 레코드에 남기기 위해 마지막
    # Judge 레코드를 상태와 관계없이 보존합니다.
    judges_by_id = {record["problem_id"]: record for record in judgments}
    final_records: list[dict[str, Any]] = []
    for response in _latest_by_problem(responses):
        problem = by_problem[response["problem_id"]]
        rule_record = rules_by_id.get(problem.id)
        judge_record = judges_by_id.get(problem.id)
        structured_judgment = (
            judge_record.get("structured_result")
            if judge_record and judge_record.get("status") == "complete"
            else None
        )
        combined = combine_scores(
            config.scoring_mode,
            rule_record,
            structured_judgment,
            config.pass_threshold,
        )
        condition = {
            "dataset_version": config.dataset_version,
            "model_provider": response["model_provider"],
            "model_id": response["model_id"],
            "model_settings": response["model_settings"],
            "scoring_mode": config.scoring_mode,
            "rule_evaluator_version": config.rule_evaluator_version,
            "judge_provider": config.judge_model.provider
            if config.scoring_mode != "rule_only"
            else None,
            "judge_model_id": config.judge_model.model_id
            if config.scoring_mode != "rule_only"
            else None,
            "judge_settings": config.judge_model.public_dict()
            if config.scoring_mode != "rule_only"
            else None,
            "judge_prompt_version": config.judge_model.prompt_version
            if config.scoring_mode != "rule_only"
            else None,
        }
        final_records.append(
            {
                "record_type": "final_score",
                "run_id": run_id,
                "run_at": utc_now(),
                "dataset_version": config.dataset_version,
                "git_commit": git_commit(repo_root),
                "problem_id": problem.id,
                "parent_id": problem.parent_id,
                "variant_type": problem.variant_type,
                "category": problem.metadata.get("category"),
                "source": problem.metadata.get("source"),
                "input_prompt": problem.prompt,
                "reference_answer": problem.reference_answer,
                "evaluation_rules": [rule.raw for rule in problem.evaluation_rules],
                "raw_model_response": response.get("response"),
                "raw_provider_response": response.get("raw_provider_response"),
                "model_provider": response["model_provider"],
                "model_id": response["model_id"],
                "model_settings": response["model_settings"],
                "generation_attempts": response.get("attempts", []),
                "generation_error": response.get("error"),
                "rule_evaluator_version": config.rule_evaluator_version,
                "rule_result": rule_record,
                "rule_criterion_ids": [
                    item["rule_id"] for item in (rule_record or {}).get("rule_results", [])
                ],
                "judge_provider": judge_record.get("judge_provider") if judge_record else None,
                "judge_model_id": judge_record.get("judge_model_id") if judge_record else None,
                "judge_settings": judge_record.get("judge_settings") if judge_record else None,
                "judge_prompt_version": judge_record.get("judge_prompt_version")
                if judge_record
                else None,
                "judge_result": structured_judgment,
                "judge_criterion_ids": [
                    item["criterion_id"]
                    for item in (structured_judgment or {}).get("criteria", [])
                ],
                "judge_attempts": judge_record.get("attempts", []) if judge_record else [],
                "judge_error": judge_record.get("error") if judge_record else None,
                "comparison_condition": condition,
                "comparison_condition_key": stable_hash(condition),
                **combined,
            }
        )
    replace_jsonl(output_path, final_records)
    return final_records

"""저장 응답을 Judge로 평가하며 JSON 오류도 제한적으로 재시도합니다."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ..config import RunConfig
from ..io import append_jsonl, git_commit, read_jsonl, stable_hash, utc_now
from ..judges import JudgeAdapter, parse_judge_json
from ..judges.prompt import JUDGE_SCHEMA_VERSION, build_judge_prompt
from ..schemas import Problem


def _latest_complete_by_problem(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        if record.get("status") == "complete" and isinstance(
            record.get("problem_id"), str
        ):
            latest[record["problem_id"]] = record
    return list(latest.values())


def judge_responses(
    problems: list[Problem],
    responses: list[dict[str, Any]],
    config: RunConfig,
    judge: JudgeAdapter,
    run_id: str,
    output_path: Path,
    cache_path: Path,
    repo_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    by_id = {problem.id: problem for problem in problems}
    existing = {
        item["judge_fingerprint"]: item
        for item in read_jsonl(output_path, missing_ok=True)
        if item.get("status") == "complete"
    }
    cache = {
        item["judge_fingerprint"]: item
        for item in read_jsonl(cache_path, missing_ok=True)
        if item.get("status") == "complete"
    }
    results: list[dict[str, Any]] = []
    counts = {"judged": 0, "cached": 0, "skipped": 0, "failed": 0}
    settings = config.judge_model.public_dict()
    for response_record in _latest_complete_by_problem(responses):
        problem = by_id[response_record["problem_id"]]
        expected_ids = [rule.rule_id for rule in problem.evaluation_rules]
        rendered_prompt = build_judge_prompt(
            problem, response_record["response"], config.judge_model.prompt_version
        )
        fingerprint = stable_hash(
            {
                "response_fingerprint": response_record["request_fingerprint"],
                "response": response_record["response"],
                "rubric": [rule.raw for rule in problem.evaluation_rules],
                "judge": settings,
                "prompt_version": config.judge_model.prompt_version,
                "schema_version": JUDGE_SCHEMA_VERSION,
                "rendered_prompt": rendered_prompt,
            }
        )
        if fingerprint in existing:
            results.append(existing[fingerprint])
            counts["skipped"] += 1
            continue
        if fingerprint in cache:
            record = {
                **cache[fingerprint],
                "run_id": run_id,
                "run_at": utc_now(),
                "dataset_version": config.dataset_version,
                "git_commit": git_commit(repo_root),
                "problem_id": problem.id,
                "parent_id": problem.parent_id,
                "variant_type": problem.variant_type,
                "category": problem.metadata.get("category"),
                "response_fingerprint": response_record["request_fingerprint"],
                "judge_prompt": rendered_prompt,
                "cache_hit": True,
                "attempts": [],
            }
            append_jsonl(output_path, record)
            results.append(record)
            counts["cached"] += 1
            continue
        attempts: list[dict[str, Any]] = []
        parsed = None
        raw_judgment = None
        for attempt in range(1, config.judge_model.max_retries + 2):
            try:
                raw_judgment = judge.judge(
                    problem,
                    response_record["response"],
                    rendered_prompt,
                    config.judge_model,
                )
                parsed = parse_judge_json(raw_judgment, expected_ids)
                attempts.append({"attempt": attempt, "at": utc_now(), "status": "success"})
                break
            except Exception as error:
                attempts.append(
                    {
                        "attempt": attempt,
                        "at": utc_now(),
                        "status": "error",
                        "error": f"{type(error).__name__}: {error}",
                    }
                )
                if attempt <= config.judge_model.max_retries:
                    time.sleep(config.judge_model.retry_delay_seconds)
        record: dict[str, Any] = {
            "record_type": "judge_result",
            "run_id": run_id,
            "run_at": utc_now(),
            "dataset_version": config.dataset_version,
            "git_commit": git_commit(repo_root),
            "problem_id": problem.id,
            "parent_id": problem.parent_id,
            "variant_type": problem.variant_type,
            "category": problem.metadata.get("category"),
            "response_fingerprint": response_record["request_fingerprint"],
            "judge_fingerprint": fingerprint,
            "judge_role": (
                "local_judge"
                if config.judge_model.provider == "local"
                else "api_judge"
            ),
            "judge_provider": config.judge_model.provider,
            "judge_model_id": config.judge_model.model_id,
            "judge_settings": settings,
            "judge_prompt_version": config.judge_model.prompt_version,
            "judge_prompt": rendered_prompt,
            "raw_judgment": raw_judgment,
            "structured_result": parsed,
            "attempts": attempts,
            "cache_hit": False,
            "status": "complete" if parsed else "error",
            "error": None if parsed else attempts[-1]["error"],
        }
        append_jsonl(output_path, record)
        if parsed:
            append_jsonl(cache_path, record)
            counts["judged"] += 1
        else:
            counts["failed"] += 1
        results.append(record)
    return results, counts

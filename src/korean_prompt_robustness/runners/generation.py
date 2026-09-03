"""모델 호출, 재시도, 캐시, 중단 후 재실행."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ..config import RunConfig
from ..io import append_jsonl, git_commit, read_jsonl, stable_hash, utc_now
from ..models import ModelAdapter
from ..schemas import Problem


def _latest_complete(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        record["request_fingerprint"]: record
        for record in records
        if record.get("status") == "complete" and record.get("request_fingerprint")
    }


def generate_responses(
    problems: list[Problem],
    config: RunConfig,
    model: ModelAdapter,
    run_id: str,
    output_path: Path,
    cache_path: Path,
    repo_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    existing_records = read_jsonl(output_path, missing_ok=True)
    existing = _latest_complete(existing_records)
    cache = _latest_complete(read_jsonl(cache_path, missing_ok=True))
    completed: list[dict[str, Any]] = []
    counts = {"generated": 0, "cached": 0, "skipped": 0, "failed": 0}
    settings = config.test_model.public_dict()
    for problem in problems:
        fingerprint = stable_hash(
            {
                "problem_id": problem.id,
                "prompt": problem.prompt,
                "test_model": settings,
                "schema": "response-v1",
            }
        )
        if fingerprint in existing:
            completed.append(existing[fingerprint])
            counts["skipped"] += 1
            continue
        if fingerprint in cache:
            source = cache[fingerprint]
            record = {
                **source,
                "run_id": run_id,
                "run_at": utc_now(),
                "dataset_version": config.dataset_version,
                "git_commit": git_commit(repo_root),
                "problem_id": problem.id,
                "parent_id": problem.parent_id,
                "variant_type": problem.variant_type,
                "category": problem.metadata.get("category"),
                "input_prompt": problem.prompt,
                "cache_hit": True,
                "attempts": [],
            }
            append_jsonl(output_path, record)
            completed.append(record)
            counts["cached"] += 1
            continue
        attempts: list[dict[str, Any]] = []
        output = None
        for attempt in range(1, config.test_model.max_retries + 2):
            try:
                output = model.generate(problem, config.test_model)
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
                if attempt <= config.test_model.max_retries:
                    time.sleep(config.test_model.retry_delay_seconds)
        record: dict[str, Any] = {
            "record_type": "model_response",
            "run_id": run_id,
            "run_at": utc_now(),
            "dataset_version": config.dataset_version,
            "git_commit": git_commit(repo_root),
            "problem_id": problem.id,
            "parent_id": problem.parent_id,
            "variant_type": problem.variant_type,
            "category": problem.metadata.get("category"),
            "input_prompt": problem.prompt,
            "model_role": "test_model",
            "model_provider": config.test_model.provider,
            "model_id": config.test_model.model_id,
            "model_settings": settings,
            "request_fingerprint": fingerprint,
            "cache_hit": False,
            "attempts": attempts,
        }
        if output is None:
            record.update(
                status="error",
                response=None,
                raw_provider_response=None,
                error=attempts[-1]["error"],
            )
            counts["failed"] += 1
        else:
            record.update(
                status="complete",
                response=output.text,
                raw_provider_response=output.raw_provider_response,
                error=None,
            )
            counts["generated"] += 1
        append_jsonl(output_path, record)
        if record["status"] == "complete":
            append_jsonl(cache_path, record)
        completed.append(record)
    return completed, counts

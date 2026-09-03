"""Judge JSON을 이유 문장이 아닌 구조화 값으로 검증합니다."""

from __future__ import annotations

import json
from typing import Any


def parse_judge_json(raw: str, expected_ids: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"Judge 응답 JSON 오류: {error}") from error
    if not isinstance(value, dict):
        raise ValueError("Judge 응답은 JSON 객체여야 합니다.")
    verdict = value.get("verdict")
    score = value.get("score")
    reason = value.get("reason")
    criteria = value.get("criteria")
    if verdict not in {"pass", "fail"}:
        raise ValueError("Judge verdict는 pass 또는 fail이어야 합니다.")
    if isinstance(score, bool) or score not in {0, 1}:
        raise ValueError("Judge score는 0 또는 1이어야 합니다.")
    if (verdict == "pass") != (score == 1):
        raise ValueError("Judge verdict와 score가 서로 모순됩니다.")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("Judge reason은 비어 있지 않은 문자열이어야 합니다.")
    if not isinstance(criteria, list):
        raise ValueError("Judge criteria는 배열이어야 합니다.")
    parsed: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, criterion in enumerate(criteria):
        if not isinstance(criterion, dict):
            raise ValueError(f"criteria[{index}]는 객체여야 합니다.")
        criterion_id = criterion.get("criterion_id")
        passed = criterion.get("passed")
        criterion_reason = criterion.get("reason")
        if not isinstance(criterion_id, str) or not criterion_id:
            raise ValueError(f"criteria[{index}].criterion_id가 필요합니다.")
        if not isinstance(passed, bool):
            raise ValueError(f"criteria[{index}].passed는 boolean이어야 합니다.")
        if not isinstance(criterion_reason, str) or not criterion_reason.strip():
            raise ValueError(f"criteria[{index}].reason이 필요합니다.")
        if criterion_id in seen:
            raise ValueError(f"criterion_id가 중복되었습니다: {criterion_id}")
        seen.add(criterion_id)
        parsed.append(
            {"criterion_id": criterion_id, "passed": passed, "reason": criterion_reason}
        )
    missing = set(expected_ids) - seen
    if missing:
        raise ValueError(f"Judge criteria 누락: {sorted(missing)}")
    return {"verdict": verdict, "score": score, "reason": reason, "criteria": parsed}


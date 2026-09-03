"""API 키 없이 구조화 Judge 흐름을 검증하는 Mock."""

from __future__ import annotations

import json

from ..config import JudgeSettings
from ..schemas import Problem
from .base import JudgeAdapter


class MockJudge(JudgeAdapter):
    def __init__(self) -> None:
        self.call_count = 0

    def judge(
        self,
        problem: Problem,
        response: str,
        rendered_prompt: str,
        settings: JudgeSettings,
    ) -> str:
        self.call_count += 1
        configured = problem.metadata.get("mock_judge_result")
        if isinstance(configured, dict):
            return json.dumps(configured, ensure_ascii=False)
        criteria = [
            {
                "criterion_id": rule.rule_id,
                "passed": bool(response),
                "reason": "Mock Judge의 결정론적 판정입니다.",
            }
            for rule in problem.evaluation_rules
        ]
        passed = bool(response) and all(item["passed"] for item in criteria)
        return json.dumps(
            {
                "verdict": "pass" if passed else "fail",
                "score": 1 if passed else 0,
                "reason": "Mock Judge의 결정론적 전체 판정입니다.",
                "criteria": criteria,
            },
            ensure_ascii=False,
        )


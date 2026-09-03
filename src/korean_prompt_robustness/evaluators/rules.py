"""KITE식 하위 조건 규칙 채점기."""

from __future__ import annotations

import importlib
import re
from typing import Any

from ..schemas import Rule


SUPPORTED_RULES = {
    "must_include",
    "must_exclude",
    "line_count",
    "sentence_count",
    "line_starts",
    "regex",
    "custom_python",
}


def _count_matches(actual: int, expected: Any) -> tuple[bool, str]:
    if isinstance(expected, bool):
        raise ValueError("개수 규칙에 boolean은 사용할 수 없습니다.")
    if isinstance(expected, int):
        return actual == expected, f"실제 {actual}, 기대 {expected}"
    if not isinstance(expected, dict):
        raise ValueError("개수 규칙 value는 정수 또는 {exact|min|max} 객체여야 합니다.")
    checks: list[bool] = []
    descriptions: list[str] = []
    if "exact" in expected:
        checks.append(actual == int(expected["exact"]))
        descriptions.append(f"exact={expected['exact']}")
    if "min" in expected:
        checks.append(actual >= int(expected["min"]))
        descriptions.append(f"min={expected['min']}")
    if "max" in expected:
        checks.append(actual <= int(expected["max"]))
        descriptions.append(f"max={expected['max']}")
    if not checks:
        raise ValueError("개수 규칙 객체에는 exact, min, max 중 하나가 필요합니다.")
    return all(checks), f"실제 {actual}, 기대 {', '.join(descriptions)}"


def _sentence_count(text: str) -> int:
    # 종결 부호가 없는 비어 있지 않은 마지막 문장도 한 문장으로 셉니다.
    fragments = [part for part in re.split(r"[.!?]+", text) if part.strip()]
    return len(fragments)


def _custom_python(path: Any, response: str, context: dict[str, Any]) -> tuple[str, str]:
    if not isinstance(path, str) or ":" not in path:
        raise ValueError("custom_python value는 'module:function' 형식이어야 합니다.")
    module_name, function_name = path.split(":", 1)
    function = getattr(importlib.import_module(module_name), function_name)
    result = function(response, context)
    if isinstance(result, bool):
        return ("pass" if result else "fail"), "사용자 정의 채점기 boolean 결과"
    if isinstance(result, dict):
        status = result.get("status")
        reason = result.get("reason", "사용자 정의 채점기 결과")
        if status not in {"pass", "fail", "indeterminate"}:
            raise ValueError("사용자 정의 채점기 status가 올바르지 않습니다.")
        return status, str(reason)
    if result is None:
        return "indeterminate", "사용자 정의 채점기가 None을 반환했습니다."
    raise ValueError("사용자 정의 채점기는 bool, dict 또는 None을 반환해야 합니다.")


def evaluate_rule(rule: Rule, response: str, context: dict[str, Any]) -> dict[str, Any]:
    try:
        if rule.type == "must_include":
            values = rule.value if isinstance(rule.value, list) else [rule.value]
            if not all(isinstance(value, str) for value in values):
                raise ValueError("must_include value는 문자열 또는 문자열 배열이어야 합니다.")
            passed = all(value in response for value in values)
            reason = f"필수 표현 포함 여부: {values}"
        elif rule.type == "must_exclude":
            values = rule.value if isinstance(rule.value, list) else [rule.value]
            if not all(isinstance(value, str) for value in values):
                raise ValueError("must_exclude value는 문자열 또는 문자열 배열이어야 합니다.")
            passed = all(value not in response for value in values)
            reason = f"금지 표현 제외 여부: {values}"
        elif rule.type == "line_count":
            actual = len(response.splitlines())
            passed, reason = _count_matches(actual, rule.value)
        elif rule.type == "sentence_count":
            passed, reason = _count_matches(_sentence_count(response), rule.value)
        elif rule.type == "line_starts":
            lines = response.splitlines()
            starts = rule.value
            if isinstance(starts, str):
                passed = bool(lines) and all(line.startswith(starts) for line in lines)
                reason = f"모든 줄 시작 글자: {starts!r}"
            elif isinstance(starts, list) and all(isinstance(item, str) for item in starts):
                passed = len(lines) == len(starts) and all(
                    line.startswith(prefix) for line, prefix in zip(lines, starts)
                )
                reason = f"줄별 시작 글자: {starts}"
            else:
                raise ValueError("line_starts value는 문자열 또는 문자열 배열이어야 합니다.")
        elif rule.type == "regex":
            pattern = rule.value.get("pattern") if isinstance(rule.value, dict) else rule.value
            flags_text = rule.value.get("flags", "") if isinstance(rule.value, dict) else ""
            if not isinstance(pattern, str) or not isinstance(flags_text, str):
                raise ValueError("regex value 형식이 올바르지 않습니다.")
            flags = re.IGNORECASE if "i" in flags_text else 0
            flags |= re.MULTILINE if "m" in flags_text else 0
            passed = re.search(pattern, response, flags) is not None
            reason = f"정규표현식 일치 여부: {pattern!r}"
        elif rule.type == "custom_python":
            status, reason = _custom_python(rule.value, response, context)
            return {
                "rule_id": rule.rule_id,
                "type": rule.type,
                "status": status,
                "value": 1 if status == "pass" else 0 if status == "fail" else None,
                "reason": reason,
            }
        else:
            return {
                "rule_id": rule.rule_id,
                "type": rule.type,
                "status": "indeterminate",
                "value": None,
                "reason": "지원하지 않는 규칙 유형이며 Judge 평가 대상으로 남겼습니다.",
            }
        status = "pass" if passed else "fail"
        return {
            "rule_id": rule.rule_id,
            "type": rule.type,
            "status": status,
            "value": 1 if passed else 0,
            "reason": reason,
        }
    except Exception as error:  # 규칙 하나의 오류가 나머지 채점을 막지 않습니다.
        return {
            "rule_id": rule.rule_id,
            "type": rule.type,
            "status": "error",
            "value": None,
            "reason": f"{type(error).__name__}: {error}",
        }


def evaluate_rules(
    rules: tuple[Rule, ...], response: str, context: dict[str, Any] | None = None
) -> dict[str, Any]:
    results = [evaluate_rule(rule, response, context or {}) for rule in rules]
    evaluated = [item for item in results if item["status"] in {"pass", "fail"}]
    passed_count = sum(item["status"] == "pass" for item in evaluated)
    score = (passed_count / len(evaluated) * 100.0) if evaluated else None
    return {
        "score": score,
        "passed_count": passed_count,
        "evaluated_count": len(evaluated),
        "indeterminate_count": sum(item["status"] == "indeterminate" for item in results),
        "error_count": sum(item["status"] == "error" for item in results),
        "rule_results": results,
    }


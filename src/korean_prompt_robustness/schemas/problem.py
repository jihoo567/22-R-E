"""입력 JSONL 스키마. 입력값을 정규화하거나 고쳐 쓰지 않습니다."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..io import read_jsonl


@dataclass(frozen=True)
class Rule:
    rule_id: str
    type: str
    value: Any
    raw: dict[str, Any]

    @classmethod
    def from_dict(cls, value: dict[str, Any], location: str) -> "Rule":
        if not isinstance(value, dict):
            raise ValueError(f"{location}: evaluation_rules 항목은 객체여야 합니다.")
        rule_id = value.get("rule_id")
        rule_type = value.get("type")
        if not isinstance(rule_id, str) or not rule_id:
            raise ValueError(f"{location}: rule_id가 필요합니다.")
        if not isinstance(rule_type, str) or not rule_type:
            raise ValueError(f"{location}: 규칙 type이 필요합니다.")
        if "value" not in value:
            raise ValueError(f"{location}: 규칙 value가 필요합니다.")
        return cls(rule_id, rule_type, value["value"], dict(value))


@dataclass(frozen=True)
class Problem:
    id: str
    parent_id: str
    variant_type: str
    prompt: str
    reference_answer: str | None
    evaluation_rules: tuple[Rule, ...]
    metadata: dict[str, Any]
    raw: dict[str, Any]

    @property
    def is_original(self) -> bool:
        return self.variant_type == "original"

    @classmethod
    def from_dict(cls, value: dict[str, Any], location: str) -> "Problem":
        required_strings = ("id", "parent_id", "variant_type", "prompt")
        for field in required_strings:
            if not isinstance(value.get(field), str) or not value[field]:
                raise ValueError(f"{location}: {field}는 비어 있지 않은 문자열이어야 합니다.")
        reference = value.get("reference_answer")
        if reference is not None and not isinstance(reference, str):
            raise ValueError(f"{location}: reference_answer는 문자열 또는 null이어야 합니다.")
        raw_rules = value.get("evaluation_rules")
        if not isinstance(raw_rules, list):
            raise ValueError(f"{location}: evaluation_rules는 배열이어야 합니다.")
        metadata = value.get("metadata")
        if not isinstance(metadata, dict):
            raise ValueError(f"{location}: metadata는 객체여야 합니다.")
        for field in ("category", "source"):
            if not isinstance(metadata.get(field), str) or not metadata[field]:
                raise ValueError(
                    f"{location}: metadata.{field}는 비어 있지 않은 문자열이어야 합니다."
                )
        rules = tuple(
            Rule.from_dict(rule, f"{location}.evaluation_rules[{index}]")
            for index, rule in enumerate(raw_rules)
        )
        rule_ids = [rule.rule_id for rule in rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError(f"{location}: rule_id가 중복되었습니다.")
        return cls(
            id=value["id"],
            parent_id=value["parent_id"],
            variant_type=value["variant_type"],
            prompt=value["prompt"],
            reference_answer=reference,
            evaluation_rules=rules,
            metadata=dict(metadata),
            raw=dict(value),
        )


def validate_dataset(records: list[dict[str, Any]]) -> list[Problem]:
    problems = [Problem.from_dict(item, f"line {index}") for index, item in enumerate(records, 1)]
    ids = [problem.id for problem in problems]
    if len(ids) != len(set(ids)):
        raise ValueError("문제 id가 중복되었습니다.")
    by_parent: dict[str, list[Problem]] = {}
    for problem in problems:
        by_parent.setdefault(problem.parent_id, []).append(problem)
    for parent_id, group in by_parent.items():
        originals = [problem for problem in group if problem.is_original]
        if len(originals) != 1:
            raise ValueError(
                f"parent_id={parent_id!r}에는 original이 정확히 하나 있어야 합니다."
            )
        if originals[0].id == originals[0].parent_id:
            # 허용은 하지만 id와 parent_id가 다른 예시를 강제하지는 않습니다.
            pass
    return problems


def load_and_validate_dataset(path: Path) -> list[Problem]:
    return validate_dataset(read_jsonl(path))

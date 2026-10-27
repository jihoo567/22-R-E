"""원본 문제로 조사·생략 변형 문제 레코드를 만듭니다.

`data/examples/problems.jsonl` 과 같은 스키마로 내보냅니다.

    원본  {base_id}-original           track=baseline
    변형  {base_id}-{variant_type}-NN  track=controlled_operator  (변형 종류 하나)
    혼합  {base_id}-mixed-NN           track=synthetic_naturalistic (여러 종류)

변형 하나는 자리 하나만 바꿉니다. 혼합은 서로 다른 종류의 편집을 겹치지 않게
2개 이상 합칩니다. 원문과 같거나 이미 만든 변형과 같은 결과는 버리므로,
프롬프트에 따라 종류별 개수가 모자랄 수 있습니다.
"""

from __future__ import annotations

import random
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..dataset import validate_dataset
from .core import Edit, apply_edits, group_sites, transforms

__all__ = [
    "FAMILIES",
    "Candidate",
    "Family",
    "candidates",
    "edit_operations",
    "export",
    "protected_spans",
    "variants_for",
]

#: 생성기 이름. metadata 의 `generator` 에 남습니다.
GENERATOR = "prompt_modify"

#: 원본 metadata 를 물려줄 때 빼는 키. 변형마다 새로 씁니다.
VARIANT_KEYS = frozenset({
    "variant_type", "variant_label", "track", "realization", "changed_features",
    "edit_operations", "semantic_preservation", "synthetic", "human_validated",
    "generator",
})


@dataclass(frozen=True)
class Family:
    """변형 종류 하나와 그것을 만드는 변형기들."""

    variant_type: str
    label: str
    transforms: tuple[str, ...]
    features: Mapping[str, tuple[str, ...]]     # 변형기 -> changed_features


FAMILIES: tuple[Family, ...] = (
    Family("particle", "조사·주제화", ("josa_omit", "josa_swap"),
           {"josa_omit": ("particle", "omission_or_coordination"),
            "josa_swap": ("particle",)}),
    Family("omission", "생략·압축", ("subject_drop", "deixis_drop"),
           {"subject_drop": ("omission",), "deixis_drop": ("omission",)}),
)
_BY_TYPE = {f.variant_type: f for f in FAMILIES}


@dataclass(frozen=True)
class Candidate:
    """변형 하나를 이루는 편집."""

    family: Family
    edits: tuple[Edit, ...]

    @property
    def features(self) -> tuple[str, ...]:
        out: list[str] = []
        for e in self.edits:
            out += self.family.features.get(e.kind, ())
        return tuple(dict.fromkeys(out))


# --- 손대지 않을 구간 ----------------------------------------------------------

_CODE = re.compile(r"```.*?```|`[^`\n]+`", re.S)
_URL = re.compile(r"https?://\S+")


def protected_spans(text: str) -> list[tuple[int, int]]:
    """코드 블록·인라인 코드·URL 구간. 이 안을 건드리는 편집은 버립니다."""
    return [m.span() for pat in (_CODE, _URL) for m in pat.finditer(text)]


def _safe(edit: Edit, spans: Sequence[tuple[int, int]]) -> bool:
    return not any(edit.start < e and s < max(edit.end, edit.start + 1) for s, e in spans)


# --- 후보 만들기 ---------------------------------------------------------------

def candidates(
    text: str,
    family: Family,
    options: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[Candidate]:
    """`text` 에서 `family` 로 만들 수 있는 변형 후보들(원문 순서)."""
    opts = options or {}
    spans = protected_spans(text)
    out: list[Candidate] = []
    for transform in transforms(family.transforms):
        for site in group_sites(transform.find(text, **opts.get(transform.name, {}))):
            for edit in site.options:
                if _safe(edit, spans):
                    out.append(Candidate(family, (edit,)))
    out.sort(key=lambda c: c.edits[0].start)
    return out


def _overlaps(a: Iterable[Edit], b: Iterable[Edit]) -> bool:
    return any(x.overlaps(y) for x in a for y in b)


def _rng(seed: int, *parts: str) -> random.Random:
    return random.Random(":".join([str(seed), *parts]))


def variants_for(
    text: str,
    base_id: str,
    types: Sequence[str] = tuple(_BY_TYPE),
    per_type: int = 3,
    mixed: int = 8,
    seed: int = 0,
    options: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[tuple[str, list[Candidate]]]:
    """원문 하나의 변형들을 (variant_type, 후보 목록) 꼴로 돌려줍니다.

    단일 종류는 자리 중 `per_type` 개를 무작위로 고르고 원문 순서로 번호를
    매깁니다. mixed 는 후보가 있는 종류에서 하나씩 골라 겹치지 않게 합칩니다.
    """
    unknown = [t for t in types if t not in _BY_TYPE]
    if unknown:
        raise ValueError(f"없는 변형 종류: {unknown} (사용 가능: {', '.join(_BY_TYPE)})")

    pools = {t: candidates(text, _BY_TYPE[t], options) for t in types}
    seen = {text}
    out: list[tuple[str, list[Candidate]]] = []

    def fresh(combo: list[Candidate]) -> bool:
        result = apply_edits(text, [e for c in combo for e in c.edits])
        if result in seen:
            return False
        seen.add(result)
        return True

    for vtype in types:
        pool = pools[vtype]
        chosen: list[Candidate] = []
        for cand in _rng(seed, base_id, vtype).sample(pool, len(pool)):
            if len(chosen) >= per_type:
                break
            if fresh([cand]):
                chosen.append(cand)
        chosen.sort(key=lambda c: c.edits[0].start)
        out += [(vtype, [c]) for c in chosen]

    available = [t for t in types if pools[t]]
    if len(available) >= 2:
        r = _rng(seed, base_id, "mixed")
        made = tries = 0
        while made < mixed and tries < mixed * 30:
            tries += 1
            k = r.randint(2, min(3, len(available)))
            combo: list[Candidate] = []
            for vtype in sorted(r.sample(available, k), key=available.index):
                cand = r.choice(pools[vtype])
                if not _overlaps(cand.edits, [e for c in combo for e in c.edits]):
                    combo.append(cand)
            if len(combo) >= 2 and fresh(combo):
                out.append(("mixed", combo))
                made += 1
    return out


# --- 레코드 ---------------------------------------------------------------------

def _word_span(text: str, start: int, end: int) -> tuple[int, int]:
    """편집 구간을 공백 경계까지 넓힙니다(사람이 읽을 before/after 용).

    어절을 공백째 지운 편집(`이것이 ` -> ``)은 이미 경계에 닿아 있어 그대로 둡니다.
    """
    while start > 0 and not text[start - 1].isspace():
        start -= 1
    if end == start or not text[end - 1].isspace():
        while end < len(text) and not text[end].isspace():
            end += 1
    return start, end


def edit_operations(text: str, combo: Sequence[Candidate], with_family: bool) -> list[dict]:
    """`edit_operations` 형식으로 바꿉니다. 같은 어절에 걸친 편집은 하나로 합칩니다."""
    tagged = sorted(
        ((e, c.family.variant_type) for c in combo for e in c.edits),
        key=lambda p: p[0].start,
    )
    groups: list[tuple[int, int, list[tuple[Edit, str]]]] = []
    for edit, family in tagged:
        s, e = _word_span(text, edit.start, edit.end)
        if groups and s < groups[-1][1]:
            gs, ge, members = groups[-1]
            groups[-1] = (gs, max(ge, e), members + [(edit, family)])
        else:
            groups.append((s, e, [(edit, family)]))

    ops = []
    for s, e, members in groups:
        local = [
            Edit(m.start - s, m.end - s, m.replacement, m.kind, m.label) for m, _ in members
        ]
        op: dict[str, Any] = {}
        if with_family:
            op["family"] = members[0][1]
        op.update({
            "before": text[s:e],
            "after": apply_edits(text[s:e], local),
            "occurrences": 1,
            "start": s,
            "transforms": list(dict.fromkeys(m.kind for m, _ in members)),
            "labels": [m.label for m, _ in members],
        })
        ops.append(op)
    return ops


def _base_id(record: Mapping[str, Any]) -> str:
    md = record.get("metadata") or {}
    if md.get("base_id"):
        return str(md["base_id"])
    rid = str(record["id"])
    return rid[: -len("-original")] if rid.endswith("-original") else rid


def is_original(record: Mapping[str, Any]) -> bool:
    return (record.get("metadata") or {}).get("variant_type", "original") == "original"


def original_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """원본 레코드. 이미 있는 값은 두고 기준선 필드만 채웁니다."""
    md = dict(record.get("metadata") or {})
    base_id = _base_id(record)
    md.setdefault("base_id", base_id)
    md.setdefault("task_card_id", base_id)
    md.setdefault("synthetic", False)
    md.setdefault("human_validated", False)
    md.setdefault("variant_type", "original")
    md.setdefault("track", "baseline")
    md.setdefault("realization", 0)
    md.setdefault("changed_features", [])
    md.setdefault("edit_operations", [])
    md.setdefault("semantic_preservation", "source_original")
    return {"id": record["id"], "prompt": record["prompt"], "metadata": md}


def variant_record(
    original: Mapping[str, Any], vtype: str, combo: Sequence[Candidate], realization: int
) -> dict[str, Any]:
    text = original["prompt"]
    base_md = {k: v for k, v in original["metadata"].items() if k not in VARIANT_KEYS}
    base_id = base_md["base_id"]
    mixed = vtype == "mixed"
    features: list[str] = []
    for c in combo:
        features += c.features
    md = {**base_md, "synthetic": True, "human_validated": False, "variant_type": vtype}
    if not mixed:
        md["variant_label"] = combo[0].family.label
    md.update({
        "track": "synthetic_naturalistic" if mixed else "controlled_operator",
        "realization": realization,
        "changed_features": sorted(set(features)) if mixed else list(dict.fromkeys(features)),
        "edit_operations": edit_operations(text, combo, with_family=mixed),
        "semantic_preservation": "pending_human_review",
        "generator": {
            "name": GENERATOR,
            "transforms": sorted({e.kind for c in combo for e in c.edits}),
        },
    })
    return {
        "id": f"{base_id}-{vtype}-{realization:02d}",
        "prompt": apply_edits(text, [e for c in combo for e in c.edits]),
        "metadata": md,
    }


def export(
    records: Iterable[Mapping[str, Any]],
    types: Sequence[str] = tuple(_BY_TYPE),
    per_type: int = 3,
    mixed: int = 8,
    seed: int = 0,
    keep_existing: bool = False,
    options: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """원본 문제들로 문제 레코드(원본 + 변형)를 만듭니다.

    `variant_type` 이 `original` 이거나 없는 레코드를 원본으로 씁니다.
    `keep_existing` 이면 입력의 기존 변형도 원본 바로 뒤에 그대로 내보내고, 새
    변형 번호는 같은 문제·종류의 기존 번호 뒤에서 이어 매겨 id 가 겹치지 않게 합니다.
    """
    originals: dict[str, Mapping[str, Any]] = {}
    existing: dict[str, list[Mapping[str, Any]]] = {}
    for rec in records:
        base_id = _base_id(rec)
        existing.setdefault(base_id, [])
        if is_original(rec):
            originals.setdefault(base_id, rec)
        else:
            existing[base_id].append(rec)

    out: list[dict[str, Any]] = []
    for base_id, olds in existing.items():
        used: dict[str, int] = {}               # variant_type -> 마지막 번호
        if keep_existing:
            for rec in olds:
                md = rec.get("metadata") or {}
                vtype = str(md.get("variant_type"))
                used[vtype] = max(used.get(vtype, 0), int(md.get("realization") or 0))
        if base_id in originals:
            original = original_record(originals[base_id])
            out.append(original)
        if keep_existing:
            out += [dict(r) for r in olds]
        if base_id not in originals:
            continue
        made = variants_for(original["prompt"], base_id, types, per_type, mixed, seed, options)
        for vtype, combo in made:
            used[vtype] = n = used.get(vtype, 0) + 1
            out.append(variant_record(original, vtype, combo, n))

    validate_dataset(out)  # answer 가 읽을 때와 같은 규칙
    return out

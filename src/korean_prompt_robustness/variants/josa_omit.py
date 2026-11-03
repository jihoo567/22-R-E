# -*- coding: utf-8 -*-
"""주격/목적격 조사 생략 변형.

kiwipiepy 형태소 분석 결과의 토큰 span 을 이용해 조사만 정확히 떼어낸다.
축약된 형태(`날` = 나 + ᆯ, `내가` = 나 + 가)도 체언 원형으로 복원한다.

    >>> omit_josa("내가 밥을 먹었다.")
    '나 밥 먹었다.'
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Sequence

from .core import (
    Edit,
    Transform,
    apply_edits,
    generate_variants,
    group_sites,
    pick_random,
    register,
)
from ._common import get_kiwi

__all__ = [
    "Candidate",
    "DEFAULT_TARGETS",
    "JosaOmit",
    "find_candidates",
    "omit_josa",
    "omit_josa_variants",
]

# 조사 태그 -> 생략 대상으로 삼는 대표 표기.
# 'ᆯ'(U+11AF), 'ᆫ'(U+11AB) 은 `날`, `난` 처럼 앞 음절에 축약된 형태.
CANONICAL_FORMS = {
    "JKS": {"이", "가"},          # 주격: 철수가, 맛이
    "JKO": {"을", "를", "ᆯ"},     # 목적격: 밥을, 영희를, 날
    "JKC": {"이", "가"},          # 보격: 얼음이 되다 (기본 비대상)
    "JX": {"은", "는", "ᆫ"},      # 보조사: 나는, 난 (기본 비대상)
}

#: 기본 생략 대상 - 주격 조사와 목적격 조사.
DEFAULT_TARGETS = ("JKS", "JKO")

# 조사가 붙을 수 없는 앞 토큰(용언/어미/기호)은 오분석으로 보고 건너뛴다.
_BLOCKED_HEAD_TAGS = {"EP", "EF", "EC", "ETM"}
_ALLOWED_SYMBOL_TAGS = {"SL", "SH", "SN"}

def _can_host_josa(tag: str) -> bool:
    """`tag` 인 토큰 뒤에 조사가 붙을 수 있는가."""
    if tag in _ALLOWED_SYMBOL_TAGS:  # AI가, 3을 처럼 로마자/숫자 뒤
        return True
    if tag in _BLOCKED_HEAD_TAGS:
        return False
    return not tag.startswith(("V", "S", "W"))


@dataclass(frozen=True)
class Candidate:
    """생략 가능한 조사 하나."""

    tag: str            # JKS / JKO / ...
    josa: str           # 조사 형태 (이, 가, 을, 를, ᆯ ...)
    head: str           # 조사가 붙은 체언의 원형 (나, 너, 철수 ...)
    surface: str        # 원문에서의 표기 (내가, 날, 철수가 ...)
    start: int          # 원문에서 바꿔 쓸 구간 시작
    end: int            # 원문에서 바꿔 쓸 구간 끝
    replacement: str    # 그 구간을 대체할 문자열

    @property
    def is_contracted(self) -> bool:
        """`날`, `내가` 처럼 체언 표기까지 바뀌는 경우."""
        return self.replacement != ""

    def to_edit(self) -> Edit:
        """엔진이 다루는 공통 편집 단위로 바꾼다."""
        return Edit(
            start=self.start,
            end=self.end,
            replacement=self.replacement,
            kind=JosaOmit.name,
            label=f"{self.surface} -> {self.head} ({self.tag} {self.josa} 생략)",
        )


def find_candidates(
    text: str,
    targets: Sequence[str] = DEFAULT_TARGETS,
    canonical_only: bool = True,
) -> list[Candidate]:
    """`text` 안에서 생략 가능한 조사를 등장 순서대로 반환한다.

    Args:
        text: 원문.
        targets: 대상 조사 태그. 기본은 주격(JKS) + 목적격(JKO).
        canonical_only: True면 이/가/을/를(및 축약형)만 다룬다.
            False면 `께서`, `에서`(단체 주격) 같은 형태까지 포함한다.
    """
    targets = tuple(targets)
    unknown = [t for t in targets if t not in CANONICAL_FORMS]
    if unknown:
        raise ValueError(f"지원하지 않는 조사 태그: {unknown}")

    tokens = get_kiwi().tokenize(text)
    out: list[Candidate] = []
    for i, tok in enumerate(tokens):
        if tok.tag not in targets or i == 0:
            continue
        if canonical_only and tok.form not in CANONICAL_FORMS[tok.tag]:
            continue

        head = tokens[i - 1]
        if not _can_host_josa(head.tag):
            continue
        if head.start > tok.start:  # 분석 결과가 뒤엉킨 경우 방어
            continue

        head_surface = text[head.start : head.end]
        if tok.start >= head.end and head_surface == head.form:
            # 조사가 독립 음절 -> 그 자리만 지우면 된다. (밥을 -> 밥)
            start, end, replacement = tok.start, tok.end, ""
        else:
            # 축약/이형태 -> 체언 원형으로 되돌린다. (날 -> 나, 내가 -> 나)
            start, end, replacement = head.start, tok.end, head.form

        out.append(
            Candidate(
                tag=tok.tag,
                josa=tok.form,
                head=head.form,
                surface=text[head.start : tok.end],
                start=start,
                end=end,
                replacement=replacement,
            )
        )
    return out


@register
class JosaOmit(Transform):
    """주격/목적격 조사 생략 변형기."""

    name = "josa_omit"
    description = "주격/목적격 조사 생략 (철수가 밥을 먹었다 -> 철수 밥 먹었다)"

    def find(
        self,
        text: str,
        targets: Sequence[str] = DEFAULT_TARGETS,
        canonical_only: bool = True,
        **_: Any,
    ) -> list[Edit]:
        return [c.to_edit() for c in find_candidates(text, targets, canonical_only)]

    @classmethod
    def add_arguments(cls, parser: Any) -> None:
        parser.add_argument(
            "--josa-targets",
            default=",".join(DEFAULT_TARGETS),
            metavar="TAGS",
            help="대상 조사 태그. 예: JKS,JKO,JX (기본: %(default)s)",
        )
        parser.add_argument(
            "--josa-all-forms",
            action="store_true",
            help="께서/에서 등 비표준 주격까지 생략",
        )

    @classmethod
    def options_from_args(cls, args: Any) -> dict[str, Any]:
        return {
            "targets": [
                t.strip().upper() for t in args.josa_targets.split(",") if t.strip()
            ],
            "canonical_only": not args.josa_all_forms,
        }


def omit_josa(
    text: str,
    targets: Sequence[str] = DEFAULT_TARGETS,
    prob: float = 1.0,
    canonical_only: bool = True,
    rng: random.Random | None = None,
) -> str:
    """주격/목적격 조사를 생략한 문장을 돌려준다.

    Args:
        text: 원문.
        targets: 대상 조사 태그.
        prob: 각 조사를 생략할 확률. 1.0이면 전부 생략.
        canonical_only: `find_candidates` 참고.
        rng: 재현 가능한 무작위 선택을 위한 난수기.
    """
    sites = group_sites(JosaOmit().find(text, targets=targets, canonical_only=canonical_only))
    return apply_edits(text, pick_random(sites, prob, rng))


def omit_josa_variants(
    text: str,
    targets: Sequence[str] = DEFAULT_TARGETS,
    max_variants: int | None = None,
    canonical_only: bool = True,
    include_original: bool = True,
    rng: random.Random | None = None,
    strategy: str = "ordered",
) -> list[str]:
    """조사 생략 조합으로 만들 수 있는 변형들을 반환한다.

    여러 변형기를 섞으려면 `modify.variants()` 를 쓴다.
    """
    sites = group_sites(JosaOmit().find(text, targets=targets, canonical_only=canonical_only))
    return generate_variants(text, sites, max_variants, include_original, rng, strategy)

# -*- coding: utf-8 -*-
"""앞에서 이미 나온 주어를 생략하는 변형.

한국어는 문맥으로 알 수 있는 주어를 잘 생략한다. 같은 체언이 앞에서 나온 뒤
다시 주어로 쓰이면 그 어절을 통째로 지운다.

    >>> drop_subjects("철수가 학교에 갔다. 철수가 밥을 먹었다.")
    '철수가 학교에 갔다. 밥을 먹었다.'

앞에 나왔는지만 보고 판단한다. 지운 주어가 정말 그 앞의 것을 가리키는지,
문맥이 자연스러운지는 검수하지 않는다.
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
from ._common import content_end, get_kiwi, nominal_key, widen_deletion, words

__all__ = [
    "DEFAULT_MARKERS",
    "RepeatedSubject",
    "SubjectDrop",
    "drop_subjects",
    "drop_subjects_variants",
    "find_repeated_subjects",
]

# 주어 표지로 볼 조사. 값이 None 이면 그 태그의 모든 형태를 받는다.
MARKER_FORMS: dict[str, set[str] | None] = {
    "JKS": None,                   # 주격: 이/가/께서
    "JX": {"은", "는", "ᆫ"},        # 주제: 은/는, 난 (도/만/조차는 뜻이 사라지니 제외)
}

#: 기본 주어 표지 - 주격 조사와 주제 보조사.
DEFAULT_MARKERS = ("JKS", "JX")

# 앞 어절이 이런 태그로 끝나면 그 어절이 주어를 꾸미고 있다. 주어만 지우면
# 꾸미는 말이 붕 떠서 건너뛴다. (그 책이 -> 그 ...)
_MODIFIER_TAGS = frozenset({"MM", "ETM", "JKG"})


@dataclass(frozen=True)
class RepeatedSubject:
    """다시 나온 주어 어절 하나."""

    key: str        # 체언 부분. 철수가 -> 철수, 선생님께서 -> 선생님
    surface: str    # 어절 표기. 철수가, 난, 선생님께서
    start: int      # 지울 구간 시작
    end: int        # 지울 구간 끝 (붙은 공백까지)
    first_at: int   # 같은 체언이 처음 나온 위치

    def to_edit(self) -> Edit:
        """엔진이 다루는 공통 편집 단위로 바꾼다."""
        return Edit(
            start=self.start,
            end=self.end,
            replacement="",
            kind=SubjectDrop.name,
            label=f"{self.surface} 생략 (앞의 '{self.key}' 반복)",
        )


def find_repeated_subjects(
    text: str,
    markers: Sequence[str] = DEFAULT_MARKERS,
) -> list[RepeatedSubject]:
    """`text` 에서 앞에 나온 체언이 다시 주어로 쓰인 어절을 찾는다.

    Args:
        text: 원문.
        markers: 주어 표지로 볼 조사 태그. 기본은 주격(JKS) + 주제(JX).
    """
    selected = tuple(markers)
    unknown = [m for m in selected if m not in MARKER_FORMS]
    if unknown:
        raise ValueError(
            f"주어 표지로 쓸 수 없는 태그: {unknown} (사용 가능: {', '.join(MARKER_FORMS)})"
        )

    tokens = get_kiwi().tokenize(text)
    grouped = words(text, tokens)

    seen: dict[str, int] = {}  # 체언 -> 처음 나온 위치
    out: list[RepeatedSubject] = []
    for i, word in enumerate(grouped):
        key = nominal_key(word)
        if key and key in seen and _is_subject(word, selected):
            previous = grouped[i - 1] if i else None
            if previous is None or previous[-1].tag not in _MODIFIER_TAGS:
                start, end = widen_deletion(text, word[0].start, content_end(word))
                out.append(
                    RepeatedSubject(
                        key=key,
                        surface=text[word[0].start : content_end(word)],
                        start=start,
                        end=end,
                        first_at=seen[key],
                    )
                )
        if key:
            seen.setdefault(key, word[0].start)
    return out


def _is_subject(word: Sequence[Any], markers: Sequence[str]) -> bool:
    """어절에 주어 표지가 붙어 있는가."""
    for tok in word:
        if tok.tag not in markers:
            continue
        allowed = MARKER_FORMS[tok.tag]
        if allowed is None or tok.form in allowed:
            return True
    return False


@register
class SubjectDrop(Transform):
    """반복 주어 생략 변형기."""

    name = "subject_drop"
    description = "앞에서 나온 주어를 다시 쓸 때 생략 (철수가 갔다. 철수가 웃었다 -> 웃었다)"

    def find(
        self,
        text: str,
        markers: Sequence[str] = DEFAULT_MARKERS,
        **_: Any,
    ) -> list[Edit]:
        return [s.to_edit() for s in find_repeated_subjects(text, markers)]

    @classmethod
    def add_arguments(cls, parser: Any) -> None:
        parser.add_argument(
            "--subject-markers",
            default=",".join(DEFAULT_MARKERS),
            metavar="TAGS",
            help="주어 표지로 볼 조사 태그. 예: JKS (기본: %(default)s)",
        )

    @classmethod
    def options_from_args(cls, args: Any) -> dict[str, Any]:
        return {
            "markers": [
                m.strip().upper() for m in args.subject_markers.split(",") if m.strip()
            ]
        }


def drop_subjects(
    text: str,
    markers: Sequence[str] = DEFAULT_MARKERS,
    prob: float = 1.0,
    rng: random.Random | None = None,
) -> str:
    """반복된 주어를 생략한 글을 돌려준다."""
    sites = group_sites(SubjectDrop().find(text, markers=markers))
    return apply_edits(text, pick_random(sites, prob, rng))


def drop_subjects_variants(
    text: str,
    markers: Sequence[str] = DEFAULT_MARKERS,
    max_variants: int | None = None,
    include_original: bool = True,
    rng: random.Random | None = None,
    strategy: str = "ordered",
) -> list[str]:
    """반복 주어 생략 조합으로 만들 수 있는 변형들을 반환한다.

    여러 변형기를 섞으려면 `modify.variants()` 를 쓴다.
    """
    sites = group_sites(SubjectDrop().find(text, markers=markers))
    return generate_variants(text, sites, max_variants, include_original, rng, strategy)

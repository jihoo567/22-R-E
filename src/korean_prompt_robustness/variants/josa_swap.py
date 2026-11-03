# -*- coding: utf-8 -*-
"""의미가 같은 조사끼리 치환하는 변형.

뜻은 그대로고 문체만 달라지는 조사들을 묶어(`EquivalenceGroup`) 서로 바꾼다.

    >>> swap_josa("철수에게 사과처럼 생긴 걸 줬다.")
    '철수한테 사과같이 생긴 걸 줬다.'

받침 여부에 따라 형태가 갈리는 조사(과/와, 이랑/랑)는 앞 글자를 보고 맞춰 쓴다.

    >>> swap_josa_variants("동생과 놀았다.")
    ['동생과 놀았다.', '동생이랑 놀았다.', '동생하고 놀았다.']
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
    "DEFAULT_GROUPS",
    "GROUPS",
    "JosaSwap",
    "find_swaps",
    "swap_josa",
    "swap_josa_variants",
]


@dataclass(frozen=True)
class JosaForm:
    """조사 하나. 받침 뒤/모음 뒤 형태가 다르면 둘 다 적는다."""

    after_consonant: str          # 받침 뒤: 동생'과', 동생'이랑'
    after_vowel: str = ""         # 모음 뒤: 철수'와', 철수'랑' (빈 값이면 같음)

    @property
    def forms(self) -> tuple[str, ...]:
        """이 조사가 원문에 나타날 수 있는 표기들."""
        if not self.after_vowel or self.after_vowel == self.after_consonant:
            return (self.after_consonant,)
        return (self.after_consonant, self.after_vowel)

    @property
    def has_allomorph(self) -> bool:
        """받침에 따라 표기가 갈리는가."""
        return len(self.forms) > 1

    def surface(self, prev_char: str) -> str | None:
        """`prev_char` 뒤에 붙을 표기. 받침을 판단할 수 없으면 `None`."""
        if not self.has_allomorph:
            return self.after_consonant
        final = has_final(prev_char)
        if final is None:
            return None
        return self.after_consonant if final else self.after_vowel


@dataclass(frozen=True)
class EquivalenceGroup:
    """뜻이 같아 서로 바꿔 쓸 수 있는 조사 묶음."""

    name: str
    description: str
    members: tuple[JosaForm, ...]


#: 조사 동의 묶음. 각 묶음 안에서는 어느 것으로든 바꿀 수 있다.
GROUPS: tuple[EquivalenceGroup, ...] = (
    EquivalenceGroup(
        "dative",
        "여격 - 철수에게 / 철수한테",
        (JosaForm("에게"), JosaForm("한테")),
    ),
    EquivalenceGroup(
        "dative_source",
        "출발점 - 철수에게서 / 철수한테서",
        (JosaForm("에게서"), JosaForm("한테서")),
    ),
    EquivalenceGroup(
        "comitative",
        "공동/접속 - 동생과 / 동생이랑 / 동생하고",
        (JosaForm("과", "와"), JosaForm("이랑", "랑"), JosaForm("하고")),
    ),
    EquivalenceGroup(
        "simile",
        "비유 - 바보처럼 / 바보같이",
        (JosaForm("처럼"), JosaForm("같이")),
    ),
    EquivalenceGroup(
        "extent",
        "정도 - 너만큼 / 너만치",
        (JosaForm("만큼"), JosaForm("만치")),
    ),
    EquivalenceGroup(
        "even",
        "극단 - 너조차 / 너마저",
        (JosaForm("조차"), JosaForm("마저")),
    ),
)

#: 기본으로 쓰는 묶음 - 지금은 전부.
DEFAULT_GROUPS = tuple(g.name for g in GROUPS)

# 표기 -> (묶음, 그 표기를 낸 조사) 색인.
_INDEX: dict[str, tuple[EquivalenceGroup, JosaForm]] = {}
for _group in GROUPS:
    for _member in _group.members:
        for _form in _member.forms:
            _INDEX.setdefault(_form, (_group, _member))

# 한글이 아닌 글자의 받침 여부는 읽는 법으로 정한다. 숫자만 다룬다.
_DIGIT_HAS_FINAL = {
    "0": True,   # 영
    "1": True,   # 일
    "2": False,  # 이
    "3": True,   # 삼
    "4": False,  # 사
    "5": False,  # 오
    "6": True,   # 육
    "7": True,   # 칠
    "8": True,   # 팔
    "9": False,  # 구
}

def has_final(char: str) -> bool | None:
    """`char` 에 받침이 있는가. 판단할 수 없으면 `None`.

    로마자처럼 읽는 법이 정해지지 않은 글자는 `None` 이다. 이때는 받침에 따라
    형태가 갈리는 조사(과/와)로는 바꾸지 않는다.
    """
    if not char:
        return None
    if "가" <= char <= "힣":
        return (ord(char) - 0xAC00) % 28 != 0
    return _DIGIT_HAS_FINAL.get(char)


def find_swaps(
    text: str,
    groups: Sequence[str] = DEFAULT_GROUPS,
) -> list[Edit]:
    """`text` 안에서 바꿔 쓸 수 있는 조사를 찾아 편집 목록으로 반환한다.

    한 자리에 대안이 여럿이면 그만큼 편집이 나온다. 엔진이 배타적 선택지로
    묶어 주므로(`core.group_sites`) 그중 하나만 쓰인다.

    Args:
        text: 원문.
        groups: 쓸 동의 묶음 이름. 기본은 전부.
    """
    selected = tuple(groups)
    unknown = [g for g in selected if g not in DEFAULT_GROUPS]
    if unknown:
        raise ValueError(
            f"없는 동의 묶음: {unknown} (사용 가능: {', '.join(DEFAULT_GROUPS)})"
        )

    edits: list[Edit] = []
    for tok in get_kiwi().tokenize(text):
        if not tok.tag.startswith("J"):  # 조사만 (같이/만큼의 부사·의존명사 용법 제외)
            continue
        found = _INDEX.get(tok.form)
        if found is None:
            continue
        group, member = found
        if group.name not in selected:
            continue
        if text[tok.start : tok.end] != tok.form:  # 축약 등 표기가 어긋나면 건너뛴다
            continue

        prev_char = text[tok.start - 1] if tok.start > 0 else ""
        for other in group.members:
            if other is member:
                continue
            alt = other.surface(prev_char)
            if alt is None or alt == tok.form:
                continue
            edits.append(
                Edit(
                    start=tok.start,
                    end=tok.end,
                    replacement=alt,
                    kind=JosaSwap.name,
                    label=f"{tok.form} -> {alt} ({group.name})",
                )
            )
    return edits


@register
class JosaSwap(Transform):
    """의미가 같은 조사끼리 치환하는 변형기."""

    name = "josa_swap"
    description = "의미가 같은 조사끼리 치환 (철수에게 -> 철수한테, 동생과 -> 동생이랑)"

    def find(
        self,
        text: str,
        groups: Sequence[str] = DEFAULT_GROUPS,
        **_: Any,
    ) -> list[Edit]:
        return find_swaps(text, groups)

    @classmethod
    def add_arguments(cls, parser: Any) -> None:
        parser.add_argument(
            "--swap-groups",
            default="all",
            metavar="NAMES",
            help="쓸 동의 묶음을 쉼표로. all 이면 전부 (기본: %(default)s). "
            + " / ".join(g.name for g in GROUPS),
        )

    @classmethod
    def options_from_args(cls, args: Any) -> dict[str, Any]:
        raw = args.swap_groups.strip()
        if raw == "all":
            return {"groups": DEFAULT_GROUPS}
        return {"groups": [g.strip() for g in raw.split(",") if g.strip()]}


def swap_josa(
    text: str,
    groups: Sequence[str] = DEFAULT_GROUPS,
    prob: float = 1.0,
    rng: random.Random | None = None,
) -> str:
    """조사를 같은 뜻의 다른 조사로 바꾼 글을 돌려준다.

    자리마다 대안이 여럿이므로 하나를 골라 쓴다. `rng` 를 주지 않으면 각 묶음에
    적힌 첫 대안을 쓴다(결과가 늘 같다).
    """
    sites = group_sites(find_swaps(text, groups))
    if rng is None and prob >= 1.0:
        return apply_edits(text, [s.options[0] for s in sites])
    return apply_edits(text, pick_random(sites, prob, rng))


def swap_josa_variants(
    text: str,
    groups: Sequence[str] = DEFAULT_GROUPS,
    max_variants: int | None = None,
    include_original: bool = True,
    rng: random.Random | None = None,
    strategy: str = "ordered",
) -> list[str]:
    """조사 치환 조합으로 만들 수 있는 변형들을 반환한다.

    여러 변형기를 섞으려면 `modify.variants()` 를 쓴다.
    """
    sites = group_sites(find_swaps(text, groups))
    return generate_variants(text, sites, max_variants, include_original, rng, strategy)

# -*- coding: utf-8 -*-
"""지시어를 생략하는 변형.

앞뒤 문맥으로 알 수 있는 지시어는 빼도 말이 된다.

    >>> drop_deixis("그는 그 책을 그렇게 읽었다.")
    '책을 읽었다.'

지시 대상이 실제로 문맥에 있는지, 빼도 뜻이 유지되는지는 검수하지 않는다.
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
from ._common import get_kiwi, is_punct, same_word, widen_deletion, words

__all__ = [
    "DEFAULT_KINDS",
    "Deixis",
    "DeixisDrop",
    "drop_deixis",
    "drop_deixis_variants",
    "find_deixis",
]

#: 지시관형사(MM). 뒤에 오는 말을 꾸미기만 하므로 그 낱말만 지운다.
DETERMINERS = frozenset(
    {
        "이", "그", "저",
        "이런", "그런", "저런",
        "이러한", "그러한", "저러한",
        "요", "고", "조",           # 구어: 요 녀석, 고 녀석
    }
)

#: 지시대명사(NP). 붙은 조사까지 어절째로 지운다.
#: 1인칭 겸양 '저'와 헷갈리는 것을 피하려고 홀로 쓰인 '저'는 넣지 않았다.
PRONOUNS = frozenset(
    {
        "이", "그",
        "이것", "그것", "저것",
        "이거", "그거", "저거",
        "여기", "거기", "저기",
        "이곳", "그곳", "저곳",
        "이쪽", "그쪽", "저쪽",
        "이분", "그분", "저분",
        "이이", "그이", "저이",
    }
)

#: 지시부사(MAG).
ADVERBS = frozenset({"이리", "그리", "저리", "이처럼", "그처럼", "이만큼", "그만큼", "저만큼"})

#: `그렇게` 는 그렇/VA-I + 게/EC 로 분석된다. 어간과 어미를 함께 지운다.
MANNER_STEMS = frozenset({"이렇", "그렇", "저렇"})
_MANNER_ENDINGS = frozenset({"게"})

#: 지시어 갈래 이름.
KINDS = ("determiner", "pronoun", "adverb")

#: 기본으로 쓰는 갈래 - 지금은 전부.
DEFAULT_KINDS = KINDS


@dataclass(frozen=True)
class Deixis:
    """생략 가능한 지시어 하나."""

    kind: str       # determiner / pronoun / adverb
    surface: str    # 지울 표기. 그, 그것을, 그렇게
    start: int      # 지울 구간 시작
    end: int        # 지울 구간 끝 (붙은 공백까지)

    def to_edit(self) -> Edit:
        """엔진이 다루는 공통 편집 단위로 바꾼다."""
        return Edit(
            start=self.start,
            end=self.end,
            replacement="",
            kind=DeixisDrop.name,
            label=f"{self.surface} 생략 (지시 {self.kind})",
        )


def find_deixis(
    text: str,
    kinds: Sequence[str] = DEFAULT_KINDS,
) -> list[Deixis]:
    """`text` 에서 생략 가능한 지시어를 등장 순서대로 찾는다.

    Args:
        text: 원문.
        kinds: 다룰 갈래. `determiner`(이/그/저 + 명사), `pronoun`(그것, 여기),
            `adverb`(그렇게, 그리) 중에서 고른다. 기본은 전부.
    """
    selected = tuple(kinds)
    unknown = [k for k in selected if k not in KINDS]
    if unknown:
        raise ValueError(f"없는 지시어 갈래: {unknown} (사용 가능: {', '.join(KINDS)})")

    tokens = get_kiwi().tokenize(text)
    grouped = words(text, tokens)

    out: list[Deixis] = []
    for word in grouped:
        for pos, tok in enumerate(word):
            found = _match(text, word, pos, tok, selected)
            if found is not None:
                out.append(found)
                break  # 한 어절에서 한 군데만
    return out


def _match(
    text: str, word: Sequence[Any], pos: int, tok: Any, kinds: Sequence[str]
) -> Deixis | None:
    """어절 `word` 의 `pos` 번째 토큰이 생략 가능한 지시어인지 본다."""
    # 지시관형사: 홀로 한 어절을 이룰 때만 지운다.
    # (그때, 그동안처럼 한 낱말로 굳은 것을 쪼개지 않으려고.)
    if "determiner" in kinds and tok.tag == "MM" and tok.form in DETERMINERS:
        if len(word) == 1:
            return _make("determiner", text, tok.start, tok.end)
        return None

    # 지시대명사: 붙은 접미사와 조사까지 어절째로.
    if "pronoun" in kinds and tok.tag == "NP" and tok.form in PRONOUNS:
        return _make("pronoun", text, tok.start, _tail_end(text, word, pos))

    if "adverb" in kinds and tok.tag == "MAG" and tok.form in ADVERBS:
        return _make("adverb", text, tok.start, tok.end)

    # 그렇게 / 이렇게: 그렇(VA-I) + 게(EC)
    if (
        "adverb" in kinds
        and tok.tag.startswith("VA")
        and tok.form in MANNER_STEMS
        and pos + 1 < len(word)
        and word[pos + 1].tag == "EC"
        and word[pos + 1].form in _MANNER_ENDINGS
    ):
        return _make("adverb", text, tok.start, word[pos + 1].end)

    return None


def _make(kind: str, text: str, start: int, end: int) -> Deixis:
    wide_start, wide_end = widen_deletion(text, start, end)
    return Deixis(kind=kind, surface=text[start:end], start=wide_start, end=wide_end)


def _tail_end(text: str, word: Sequence[Any], pos: int) -> int:
    """`pos` 번째 토큰부터 붙어 있는 접미사·조사의 끝. 문장부호는 뺀다.

    그들은 -> 그(NP) 들(XSN) 은(JX) 까지, 그것으로는 -> 조사 둘 다.
    """
    end = word[pos].end
    for tok in word[pos + 1 :]:
        if is_punct(tok.tag):
            break
        if tok.tag == "XSN" or tok.tag.startswith("J"):
            end = max(end, tok.end)
            continue
        break
    return end


@register
class DeixisDrop(Transform):
    """지시어 생략 변형기."""

    name = "deixis_drop"
    description = "지시어 생략 (그는 그 책을 그렇게 읽었다 -> 책을 읽었다)"

    def find(
        self,
        text: str,
        kinds: Sequence[str] = DEFAULT_KINDS,
        **_: Any,
    ) -> list[Edit]:
        return [d.to_edit() for d in find_deixis(text, kinds)]

    @classmethod
    def add_arguments(cls, parser: Any) -> None:
        parser.add_argument(
            "--deixis-kinds",
            default="all",
            metavar="KINDS",
            help="다룰 지시어 갈래를 쉼표로. all 이면 전부 (기본: %(default)s). "
            + " / ".join(KINDS),
        )

    @classmethod
    def options_from_args(cls, args: Any) -> dict[str, Any]:
        raw = args.deixis_kinds.strip()
        if raw == "all":
            return {"kinds": DEFAULT_KINDS}
        return {"kinds": [k.strip() for k in raw.split(",") if k.strip()]}


def drop_deixis(
    text: str,
    kinds: Sequence[str] = DEFAULT_KINDS,
    prob: float = 1.0,
    rng: random.Random | None = None,
) -> str:
    """지시어를 생략한 글을 돌려준다."""
    sites = group_sites(DeixisDrop().find(text, kinds=kinds))
    return apply_edits(text, pick_random(sites, prob, rng))


def drop_deixis_variants(
    text: str,
    kinds: Sequence[str] = DEFAULT_KINDS,
    max_variants: int | None = None,
    include_original: bool = True,
    rng: random.Random | None = None,
    strategy: str = "ordered",
) -> list[str]:
    """지시어 생략 조합으로 만들 수 있는 변형들을 반환한다.

    여러 변형기를 섞으려면 `modify.variants()` 를 쓴다.
    """
    sites = group_sites(DeixisDrop().find(text, kinds=kinds))
    return generate_variants(text, sites, max_variants, include_original, rng, strategy)

# -*- coding: utf-8 -*-
"""변형기들이 함께 쓰는 도구.

이름이 `_` 로 시작하는 내부 모듈이며 변형기가 아니다.
"""

from __future__ import annotations

import unicodedata
from typing import Any, Iterable, Sequence

from kiwipiepy import Kiwi

__all__ = [
    "NOMINAL_TAGS",
    "content_end",
    "get_kiwi",
    "is_punct",
    "nominal_key",
    "same_word",
    "widen_deletion",
    "words",
]

#: 체언 및 체언에 붙는 접미사 태그 - 조사가 붙을 수 있는 몸통.
NOMINAL_TAGS = frozenset(
    {"NNG", "NNP", "NNB", "NR", "NP", "XSN", "XR", "ETN", "SL", "SH", "SN"}
)

# 로마자(SL)·한자(SH)·숫자(SN)는 기호가 아니라 낱말이다.
_WORDLIKE_S_TAGS = frozenset({"SL", "SH", "SN"})

_kiwi: Kiwi | None = None


def get_kiwi() -> Kiwi:
    """Kiwi 인스턴스 하나를 모든 변형기가 함께 쓴다(초기화 비용이 크다)."""
    global _kiwi
    if _kiwi is None:
        _kiwi = Kiwi()
    return _kiwi


def is_punct(tag: str) -> bool:
    """문장부호·기호 태그인가."""
    return tag.startswith("S") and tag not in _WORDLIKE_S_TAGS


def same_word(text: str, prev: Any, cur: Any) -> bool:
    """두 토큰이 같은 어절에 속하는가(사이에 공백이 없는가).

    `날` = 나 + ᆯ 처럼 구간이 겹치는 축약형도 같은 어절로 본다.
    """
    if cur.start < prev.end:
        return True
    return not any(ch.isspace() for ch in text[prev.end : cur.start])


def words(text: str, tokens: Sequence[Any]) -> list[list[Any]]:
    """토큰을 공백 기준 어절로 묶는다."""
    out: list[list[Any]] = []
    for tok in tokens:
        if out and same_word(text, out[-1][-1], tok):
            out[-1].append(tok)
        else:
            out.append([tok])
    return out


def nominal_key(tokens: Iterable[Any]) -> str:
    """어절에서 체언 부분만 이어 붙인다. `선생님께서` -> `선생님`."""
    return "".join(t.form for t in tokens if t.tag in NOMINAL_TAGS)


def content_end(tokens: Sequence[Any]) -> int:
    """어절에서 문장부호를 뺀 끝 위치. `철수가,` 의 경우 쉼표 앞."""
    ends = [t.end for t in tokens if not is_punct(t.tag)]
    return max(ends) if ends else tokens[-1].end


def widen_deletion(text: str, start: int, end: int) -> tuple[int, int]:
    """어절을 지울 때 공백이 겹치지 않게 구간을 넓힌다.

    뒤에 붙은 공백을 먹고, 없으면 앞에 붙은 공백을 먹는다. 줄바꿈은 건드리지
    않아 문단 구조가 유지된다. 지운 자리 뒤에 문장부호가 남는 경우
    (`철수가, 웃었다`)에는 앞 공백을 그대로 두어 부호가 앞말에 달라붙지 않게 한다.
    """
    wider = end
    while wider < len(text) and text[wider] in " \t":
        wider += 1
    if wider > end:
        return start, wider

    if end < len(text) and unicodedata.category(text[end]).startswith("P"):
        return start, end

    narrower = start
    while narrower > 0 and text[narrower - 1] in " \t":
        narrower -= 1
    return narrower, end

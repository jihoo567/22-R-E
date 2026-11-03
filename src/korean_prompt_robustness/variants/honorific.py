# -*- coding: utf-8 -*-
"""높임법(상대높임법 화계) 변형.

문장을 끝맺는 어미를 다른 화계로 바꿔 준다. 어미 활용은 koparadigm 이 맡으므로
불규칙 활용이 알아서 처리된다(듣다 -> 들으십시오, 돕다 -> 도우세요).

    >>> swap_honorific("밥을 먹었다.", "formal")
    '밥을 먹었습니다.'
    >>> swap_honorific("학교에 갑니다.", "banmal")
    '학교에 가.'

어미를 다시 만드는 길이 세 가지다.

1. `었/겠` 뒤 - 시제 선어말어미가 마지막이면 그 뒤 어미 결합은 규칙적이라
   어미만 갈아 끼운다. (먹었다 -> 먹었습니다, 가셨다 -> 가셨습니다)
2. `시` 뒤 - 주체높임이 마지막이면 `시`까지 함께 갈아 끼운다.
   (가신다 -> 가십니다, 먹으신다 -> 먹으십니다)
3. 그 밖 - 어간부터 koparadigm 으로 다시 활용한다. (갑니다 -> 간다)

낮춤 화계(해라체·해체)로 바꿀 때는 주체높임 `시` 를 뗀다. 상대를 낮추면서
주체를 높이면 화계가 흐려지기 때문이다.

    >>> swap_honorific("그렇게 하십시오.", "plain")   # 하셔라가 아니라
    '그렇게 해라.'
    >>> swap_honorific("선생님이 가셨다.", "banmal")   # 가셨어가 아니라
    '선생님이 갔어.'

서법(평서/의문/명령/청유)은 원문 어미와 문장부호로 어림한다. `세요` 처럼
평서와 명령을 겸하는 어미는 평서로 본다.
"""

from __future__ import annotations

import dataclasses
import functools
import random
from dataclasses import dataclass, field
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
from ._common import get_kiwi, is_punct, words

__all__ = [
    "DEFAULT_LEVELS",
    "Ending",
    "Honorific",
    "LEVELS",
    "find_endings",
    "swap_honorific",
    "swap_honorific_variants",
]

#: 서법.
MOODS = ("평서", "의문", "명령", "청유")


@dataclass(frozen=True)
class Level:
    """상대높임법 한 등급.

    `endings` 는 koparadigm 어미 키 후보(앞에서부터 있는 것을 쓴다),
    `after_tense` 는 `었/겠` 뒤에 붙일 어미, `after_si` 는 `시`까지 갈아 끼울
    어미다. `after_si` 값이 짝이면 (동사형, 형용사·계사형)이다.

    `drop_si` 가 참이면 낮춤 화계로 보아 주체높임 `시` 를 떼고 만든다.
    (하십시오 -> 해라, 하세요 -> 해) 이때 `after_si` 는 쓰이지 않는다.
    """

    name: str
    korean: str
    endings: dict[str, tuple[str, ...]]
    after_tense: dict[str, str] = field(default_factory=dict)
    after_si: dict[str, str | tuple[str, str]] = field(default_factory=dict)
    drop_si: bool = False


#: 상대높임법 여섯 등급. koparadigm 어미 키는 호환 자모(`ㅂ니다`)를 쓴다.
LEVELS: tuple[Level, ...] = (
    Level(
        "formal",
        "합쇼체",
        {
            "평서": ("습니다", "ㅂ니다"),
            "의문": ("습니까", "ㅂ니까"),
            "명령": ("으십시오", "십시오"),
            "청유": ("읍시다", "ㅂ시다"),
        },
        {"평서": "습니다", "의문": "습니까"},
        {"평서": "십니다", "의문": "십니까", "명령": "십시오", "청유": "십시다"},
    ),
    Level(
        "polite",
        "해요체",
        {
            "평서": ("어요", "아요", "여요"),
            "의문": ("어요", "아요", "여요"),
            "명령": ("으세요", "세요"),
            "청유": ("어요", "아요", "여요"),
        },
        {"평서": "어요", "의문": "어요"},
        {"평서": "세요", "의문": "세요", "명령": "세요", "청유": "시죠"},
    ),
    Level(
        "hao",
        "하오체",
        {
            "평서": ("으오", "오"),
            "의문": ("으오", "오"),
            # koparadigm 에 `으시오` 키는 없다. 하오체 명령은 `-오` 로도 된다.
            "명령": ("으시오", "시오", "으오", "오"),
            "청유": ("읍시다", "ㅂ시다"),
        },
        {"평서": "소", "의문": "소"},
        {"평서": "시오", "의문": "시오", "명령": "시오", "청유": "십시다"},
    ),
    Level(
        "familiar",
        "하게체",
        {
            "평서": ("네",),
            "의문": ("나",),
            "명령": ("게",),
            "청유": ("으세", "세"),
        },
        {"평서": "네", "의문": "나"},
        {"평서": "시네", "의문": "시나", "명령": "시게", "청유": "시세"},
    ),
    Level(
        "plain",
        "해라체",
        {
            "평서": ("는다", "ㄴ다", "다"),
            "의문": ("느냐", "냐", "니"),
            "명령": ("어라", "아라", "여라", "으라"),
            "청유": ("자",),
        },
        {"평서": "다", "의문": "냐"},
        {},  # 낮춤 화계 - 시를 뗀다
        drop_si=True,
    ),
    Level(
        "banmal",
        "해체",
        {
            "평서": ("어", "아", "여"),
            "의문": ("어", "아", "여"),
            "명령": ("어", "아", "여"),
            "청유": ("어", "아", "여"),
        },
        {"평서": "어", "의문": "어"},
        {},  # 낮춤 화계 - 시를 뗀다
        drop_si=True,
    ),
)

#: 기본으로 만들 화계 - 지금은 전부.
DEFAULT_LEVELS = tuple(lv.name for lv in LEVELS)

_BY_NAME = {lv.name: lv for lv in LEVELS}

# 서술어 어간 태그 -> koparadigm 활용 부류.
_PARADIGM_CLASS = {
    "VV": "Action Verb",
    "VX": "Action Verb",
    "XSV": "Action Verb",
    "VA": "Descriptive Verb",
    "XSA": "Descriptive Verb",
    "VCN": "Descriptive Verb",
    "VCP": "Copula",
}

# 시제·추측 선어말어미. 이게 마지막이면 어미만 갈아 끼운다.
_TENSE_FORMS = frozenset({"었", "았", "었었", "겠"})
# 시제 선어말어미 형태 -> 어간을 그 시제로 만들 koparadigm 어미 키 후보.
_TENSE_KEYS = {
    "었": ("었", "았", "였"),
    "았": ("았", "었", "였"),
    "었었": ("었었", "었", "았", "였"),
    "겠": ("겠",),
}
# 주체높임 선어말어미.
_SI_FORMS = frozenset({"시", "으시"})
# 선어말어미 없이도 주체높임이 녹아 있는 종결어미.
_SI_ENDINGS = frozenset({"세요", "으세요", "셔요", "으셔요", "시어요"})

# kiwi 어미 형태 앞에 붙는 자모(ᆸ니다, ᆫ다)를 떼고 견주기 위한 것.
_JAMO = "".join(chr(c) for c in range(0x11A8, 0x11C3)) + "".join(
    chr(c) for c in range(0x3131, 0x314F)
)

_INTERROGATIVE = frozenset(
    {"냐", "느냐", "니", "나", "까", "니까", "습니까", "는가", "은가", "가",
     "나요", "는지", "은지", "던가", "을까", "을래", "습디까"}
)
_IMPERATIVE = frozenset(
    {"어라", "아라", "여라", "라", "으라", "렴", "으렴", "려무나", "으려무나",
     "시오", "으시오", "십시오", "으십시오", "구려"}
)
_PROPOSITIVE = frozenset({"자", "자꾸나", "시다", "읍시다", "으세", "세"})


def _norm(form: str) -> str:
    """어미 형태 앞의 자모를 뗀다. `ᆸ니다` -> `니다`."""
    return form.lstrip(_JAMO)


@dataclass(frozen=True)
class Ending:
    """문장을 끝맺는 어미 한 자리."""

    stem: str        # 어간 원형. 먹, 가, 하, 이
    tag: str         # 어간 품사. VV / VA / VCP ...
    mood: str        # 평서 / 의문 / 명령 / 청유
    surface: str     # 원문 표기. 먹었습니다
    stem_start: int  # 어간 시작 (3번 길에서 다시 만들 시작점)
    ef_start: int    # 종결어미 시작 (1번 길에서 갈아 끼울 시작점)
    si_start: int    # 주체높임 `시` 시작. 없으면 -1
    end: int         # 어미 끝 (문장부호 앞)
    tense_end: int   # 시제 선어말어미 끝. 없으면 -1
    tense: str = ""  # 시제 선어말어미 형태. 었 / 았 / 겠 ...
    ambiguous: bool = False  # `세요` 처럼 평서·명령을 겸해 서법을 어림한 자리

    @property
    def path(self) -> str:
        """어미를 다시 만드는 길: `tense` / `si` / `stem`."""
        if self.tense_end >= 0:
            return "tense"
        if self.si_start >= 0:
            return "si"
        return "stem"


@functools.lru_cache(maxsize=1)
def _paradigm():
    """koparadigm 을 지연 로딩한다(xlsx 를 읽어 무겁다)."""
    # koparadigm 은 xlrd 1.2 로 xlsx 를 읽는데, xlrd 가 파이썬 3.9 에서 사라진
    # ElementTree.getiterator() 를 부른다. import 전에 되살려 준다.
    import xml.etree.ElementTree as ElementTree

    if not hasattr(ElementTree.ElementTree, "getiterator"):
        ElementTree.ElementTree.getiterator = ElementTree.ElementTree.iter

    from koparadigm import Paradigm

    return Paradigm()


@functools.lru_cache(maxsize=4096)
def _conjugations(stem: str, tag: str) -> dict[str, tuple[str, ...]]:
    """`stem` 의 활용표. 어미 키 -> 만들어진 형태들(축약형이 앞).

    품사에 맞는 부류를 고르고, 없으면 첫 부류를 쓴다.
    """
    try:
        table = _paradigm().conjugate(stem)
    except Exception:  # koparadigm 이 모르는 어간
        return {}
    if not table:
        return {}

    wanted = _PARADIGM_CLASS.get(tag.split("-")[0], "Action Verb")
    pairs = next((p for cls, p in table if wanted in cls), table[0][1])
    # '하여요/해요' 처럼 여러 형태가 오면 줄임형을 앞세운다.
    return {ending: tuple(reversed(form.split("/"))) for ending, form in pairs}


def _mood(ending_form: str, text: str, end: int) -> str:
    """어미 형태와 뒤따르는 문장부호로 서법을 어림한다."""
    form = _norm(ending_form)
    if form in _IMPERATIVE:
        return "명령"
    if form in _PROPOSITIVE:
        return "청유"
    if form in _INTERROGATIVE:
        return "의문"
    if "?" in text[end : end + 3]:
        return "의문"
    return "평서"


def find_endings(text: str) -> list[Ending]:
    """`text` 에서 문장을 끝맺는 어미를 등장 순서대로 찾는다."""
    out: list[Ending] = []
    for word in words(text, get_kiwi().tokenize(text)):
        found = _read_ending(text, word)
        if found is not None:
            out.append(found)
    return out


def _read_ending(text: str, word: Sequence[Any]) -> Ending | None:
    """어절 하나에서 종결어미를 읽는다. 아니면 `None`."""
    body = [t for t in word if not is_punct(t.tag)]
    if not body:
        return None

    last = body[-1]
    if last.tag == "EF":
        pass
    elif last.tag == "EC":
        # 연결어미는 문장 끝일 때만 종결어미로 본다. (먹니? / 먹지)
        tail = text[max(t.end for t in word) :].lstrip()
        if not any(ch in ".?!…" for ch in text[last.end : last.end + 2]) and tail:
            return None
    else:
        return None

    stem = None
    tense_end = -1
    tense = ""
    si_start = -1
    for tok in reversed(body[:-1]):
        if tok.tag == "EP":
            if tok.form in _TENSE_FORMS and tense_end < 0:
                tense_end, tense = tok.end, tok.form
            elif tok.form in _SI_FORMS:
                si_start = tok.start
            continue
        if tok.tag.split("-")[0] in _PARADIGM_CLASS:
            stem = tok
        break

    if stem is None:
        return None
    if tense_end < 0 and si_start < 0 and last.form in _SI_ENDINGS:
        si_start = last.start  # 세요처럼 어미에 녹아 있는 주체높임

    end = max(t.end for t in body)
    mood = _mood(last.form, text, end)
    return Ending(
        stem=stem.form,
        tag=stem.tag,
        mood=mood,
        ambiguous=mood == "평서" and last.form in _SI_ENDINGS,
        surface=text[min(stem.start, last.start) : end],
        stem_start=min(stem.start, last.start),
        ef_start=last.start,
        si_start=si_start,
        end=end,
        tense_end=tense_end,
        tense=tense,
    )


def _pick(value: str | tuple[str, str], tag: str) -> str:
    """`after_si` 값에서 품사에 맞는 것을 고른다."""
    if isinstance(value, str):
        return value
    return value[1] if tag.split("-")[0] in ("VA", "XSA", "VCP", "VCN") else value[0]


def _rebuild(text: str, ending: Ending, level: Level) -> tuple[int, str] | None:
    """`level` 로 바꾼 결과를 (갈아 끼울 시작 위치, 새 표기) 로 돌려준다."""
    drop_si = level.drop_si and ending.si_start >= 0

    if ending.path == "tense":
        # 었/겠 뒤 - 어미만. 명령·청유는 시제와 결합하지 않으므로 없다.
        form = level.after_tense.get(ending.mood)
        if not form:
            return None
        if not drop_si:
            return ending.ef_start, form
        # 낮춤 화계 + 주체높임 -> 시를 떼려면 어간부터 다시 만든다.
        # (가셨습니다 -> 갔다) 시제는 어간에 다시 입힌다.
        table = _conjugations(ending.stem, ending.tag)
        for key in _TENSE_KEYS.get(ending.tense, ()):
            if key in table:
                return ending.stem_start, table[key][0] + form
        return None

    if ending.path == "si" and not drop_si:
        form = level.after_si.get(ending.mood)
        if not form:
            return None
        honorific = _conjugations(ending.stem, ending.tag)
        base = next(
            (f[0] for key in ("으시", "시") for f in [honorific.get(key, ())] if f),
            None,
        )
        if base is None or not base.endswith("시"):
            return None
        return ending.stem_start, base[:-1] + _pick(form, ending.tag)

    # 어간부터 다시 활용한다. 낮춤 화계에서 시를 떼는 경우도 여기로 온다.
    table = _conjugations(ending.stem, ending.tag)
    for key in level.endings.get(ending.mood, ()):
        if key in table:
            return ending.stem_start, table[key][0]
    return None


@register
class Honorific(Transform):
    """상대높임법 화계 변형기."""

    name = "honorific"
    description = "높임법(화계) 변형 (먹었다 -> 먹었습니다 / 먹었어요 / 먹었네)"

    def find(
        self,
        text: str,
        levels: Sequence[str] = DEFAULT_LEVELS,
        ambiguous_mood: str = "평서",
        **_: Any,
    ) -> list[Edit]:
        """`ambiguous_mood` 는 `세요` 처럼 평서·명령을 겸하는 어미를 어느 서법으로
        볼지 정한다. 요청문이 대부분인 글(프롬프트)이면 `"명령"` 을 준다.
        """
        selected = tuple(levels)
        unknown = [lv for lv in selected if lv not in _BY_NAME]
        if unknown:
            raise ValueError(
                f"없는 화계: {unknown} (사용 가능: {', '.join(DEFAULT_LEVELS)})"
            )
        if ambiguous_mood not in MOODS:
            raise ValueError(f"없는 서법: {ambiguous_mood!r} (사용 가능: {', '.join(MOODS)})")

        edits: list[Edit] = []
        for ending in find_endings(text):
            if ending.ambiguous:
                ending = dataclasses.replace(ending, mood=ambiguous_mood)
            for name in selected:
                level = _BY_NAME[name]
                built = _rebuild(text, ending, level)
                if built is None:
                    continue
                start, form = built
                if text[start : ending.end] == form:
                    continue  # 원문과 같다
                edits.append(
                    Edit(
                        start=start,
                        end=ending.end,
                        replacement=form,
                        kind=self.name,
                        label=f"{ending.surface} -> "
                        f"{text[ending.stem_start:start]}{form}"
                        f" ({level.korean} {ending.mood})",
                    )
                )
        return edits

    @classmethod
    def add_arguments(cls, parser: Any) -> None:
        parser.add_argument(
            "--honorific-levels",
            default="all",
            metavar="NAMES",
            help="만들 화계를 쉼표로. all 이면 전부 (기본: %(default)s). "
            + " / ".join(f"{lv.name}({lv.korean})" for lv in LEVELS),
        )
        parser.add_argument(
            "--honorific-ambiguous-mood",
            default="평서",
            choices=MOODS,
            help="'세요' 처럼 평서·명령을 겸하는 어미를 볼 서법 (기본: %(default)s). "
            "요청문이면 명령",
        )

    @classmethod
    def options_from_args(cls, args: Any) -> dict[str, Any]:
        raw = args.honorific_levels.strip()
        mood = {"ambiguous_mood": args.honorific_ambiguous_mood}
        if raw == "all":
            return {"levels": DEFAULT_LEVELS, **mood}
        return {"levels": [n.strip() for n in raw.split(",") if n.strip()], **mood}


def swap_honorific(
    text: str,
    level: str,
    prob: float = 1.0,
    rng: random.Random | None = None,
) -> str:
    """글의 화계를 `level` 하나로 바꾼다."""
    sites = group_sites(Honorific().find(text, levels=(level,)))
    if rng is None and prob >= 1.0:
        return apply_edits(text, [s.options[0] for s in sites])
    return apply_edits(text, pick_random(sites, prob, rng))


def swap_honorific_variants(
    text: str,
    levels: Sequence[str] = DEFAULT_LEVELS,
    max_variants: int | None = None,
    include_original: bool = True,
    rng: random.Random | None = None,
    strategy: str = "ordered",
) -> list[str]:
    """화계를 바꾼 변형들을 반환한다.

    여러 변형기를 섞으려면 `modify.variants()` 를 쓴다.
    """
    sites = group_sites(Honorific().find(text, levels=levels))
    return generate_variants(text, sites, max_variants, include_original, rng, strategy)

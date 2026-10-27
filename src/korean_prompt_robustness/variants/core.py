# -*- coding: utf-8 -*-
"""변형기 공통 뼈대.

모든 글 변형은 "원문의 어떤 구간을 무엇으로 바꾼다"는 `Edit` 목록으로 표현한다.
같은 구간을 노리는 편집들은 `Site`(자리) 하나로 묶이고, 한 자리에서는 대안 중
하나만 골라 쓴다. 그래서 조사 생략처럼 대안이 하나인 변형과 조사 치환처럼
대안이 여럿인 변형을 같은 방식으로 다룰 수 있다.

    원문:  철수에게 밥을 줬다.
    자리1: [에게] -> 한테                    (대안 1개)
    자리2: [밥을] -> 밥                      (대안 1개)
    가능한 변형 = (1+1) * (1+1) = 4가지

변형기가 이 형태로만 결과를 내놓으면, 서로 다른 파일에 구현된 변형기들의
편집을 한데 모아 적용하거나 조합할 수 있다(`variants.export` 참고).

새 변형기 추가법:

    # variants/my_transform.py
    from .core import Edit, Transform, register

    @register
    class MyTransform(Transform):
        name = "my_transform"
        description = "무엇을 바꾸는지 한 줄 설명"

        def find(self, text, **options):
            return [Edit(0, 1, "바꿀말", self.name, "원말 -> 바꿀말")]

파일을 만든 뒤 `variants/__init__.py` 의 `_TRANSFORM_MODULES` 에 모듈 이름을
더하면 등록된다.

prompt_modify 프로젝트의 `core.py` 를 그대로 옮겨 온 것이다.
"""

from __future__ import annotations

import abc
import itertools
import math
import random
from dataclasses import dataclass
from typing import Any, ClassVar, Iterable, Sequence

__all__ = [
    "Edit",
    "Site",
    "Transform",
    "apply_edits",
    "count_variants",
    "generate_variants",
    "get",
    "group_sites",
    "names",
    "pick_random",
    "register",
    "transforms",
]

#: 전수 조합을 허용하는 변형 개수 상한. 넘으면 `max_variants` 를 요구한다.
MAX_EXHAUSTIVE_VARIANTS = 1 << 14

#: `generate_variants` 의 고르기 방식.
STRATEGIES = ("ordered", "random")


@dataclass(frozen=True)
class Edit:
    """원문 `[start, end)` 구간을 `replacement` 로 바꾸는 편집 하나."""

    start: int
    end: int
    replacement: str
    kind: str = ""       # 이 편집을 만든 변형기 이름
    label: str = ""      # 사람이 읽을 설명. 예: "내가 -> 나"

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"잘못된 구간: [{self.start}, {self.end})")

    def overlaps(self, other: "Edit | Site") -> bool:
        """구간이 겹치는가. 맞닿아 있기만 한 경우는 겹치지 않는다."""
        return self.start < other.end and other.start < self.end


@dataclass(frozen=True)
class Site:
    """원문의 한 자리와, 그 자리에 쓸 수 있는 대안 편집들.

    대안은 서로 배타적이다. 한 자리에서 고를 수 있는 선택지는
    `원문 유지` + 대안 개수만큼이다.
    """

    start: int
    end: int
    options: tuple[Edit, ...]

    @property
    def kinds(self) -> list[str]:
        """이 자리에 대안을 낸 변형기 이름들(중복 제거, 등장 순서)."""
        return list(dict.fromkeys(e.kind for e in self.options))


def apply_edits(text: str, edits: Iterable[Edit]) -> str:
    """`edits` 를 모두 적용한다. 구간이 겹치면 `ValueError`.

    뒤에서부터 바꿔야 앞쪽 인덱스가 밀리지 않는다.
    """
    ordered = sorted(edits, key=lambda e: (e.start, e.end))
    for prev, cur in zip(ordered, ordered[1:]):
        if prev.overlaps(cur):
            raise ValueError(f"편집 구간이 겹친다: {prev} / {cur}")
    for edit in reversed(ordered):
        text = text[: edit.start] + edit.replacement + text[edit.end :]
    return text


def group_sites(edits: Iterable[Edit]) -> list[Site]:
    """편집들을 자리(`Site`)로 묶어 원문 순서대로 반환한다.

    구간이 완전히 같은 편집은 한 자리의 대안으로 모으고, 이미 잡힌 자리와
    어긋나게 겹치는 편집은 버린다(앞쪽 자리를 우선, 같은 자리면 먼저 넘어온
    편집 = 먼저 선택된 변형기를 우선).
    """
    ordered = sorted(enumerate(edits), key=lambda p: (p[1].start, p[1].end, p[0]))

    grouped: list[tuple[int, int, list[Edit]]] = []
    for _, edit in ordered:
        if grouped and (grouped[-1][0], grouped[-1][1]) == (edit.start, edit.end):
            if edit.replacement not in {e.replacement for e in grouped[-1][2]}:
                grouped[-1][2].append(edit)
            continue
        if grouped and grouped[-1][1] > edit.start:  # 어긋나게 겹친다
            continue
        grouped.append((edit.start, edit.end, [edit]))

    return [Site(start, end, tuple(opts)) for start, end, opts in grouped]


def count_variants(sites: Sequence[Site], include_original: bool = True) -> int:
    """`sites` 로 만들 수 있는 변형 개수(원문 포함 여부 반영)."""
    total = math.prod(1 + len(s.options) for s in sites)
    return total if include_original else max(total - 1, 0)


def pick_random(
    sites: Sequence[Site], prob: float, rng: random.Random | None = None
) -> list[Edit]:
    """자리마다 `prob` 확률로 바꾸고, 바꿀 때는 대안 중 하나를 무작위로 고른다."""
    if prob <= 0.0:
        return []
    r = rng or random
    chosen = []
    for site in sites:
        if prob >= 1.0 or r.random() < prob:
            chosen.append(site.options[0] if len(site.options) == 1 else r.choice(site.options))
    return chosen


def _combinations(text: str, sites: Sequence[Site]) -> Iterable[str]:
    """바꾼 자리 수가 적은 것부터 모든 변형을 만든다(원문 제외, 지연 평가)."""
    for k in range(1, len(sites) + 1):
        for combo in itertools.combinations(sites, k):
            for choices in itertools.product(*(s.options for s in combo)):
                yield apply_edits(text, choices)


def generate_variants(
    text: str,
    sites: Sequence[Site],
    max_variants: int | None = None,
    include_original: bool = True,
    rng: random.Random | None = None,
    strategy: str = "ordered",
) -> list[str]:
    """자리마다 대안을 골라 적용하는 조합으로 변형들을 만든다.

    Args:
        text: 원문.
        sites: `group_sites` 로 묶은 자리들(서로 겹치지 않아야 한다).
        max_variants: 반환 개수 상한. `None` 이면 가능한 전부.
        include_original: 원문 자체를 결과에 포함할지.
        rng: 재현 가능한 무작위 선택을 위한 난수기.
        strategy: `"ordered"` 면 바꾼 자리 수가 적은 것부터(원문에 가까운 순),
            `"random"` 이면 가능한 변형 전체에서 무작위로 고른다.
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"strategy 는 {STRATEGIES} 중 하나여야 한다: {strategy!r}")
    if max_variants is not None and max_variants < 1:
        return []

    total = count_variants(sites)
    if max_variants is None and total > MAX_EXHAUSTIVE_VARIANTS:
        raise ValueError(
            f"가능한 변형이 {total}가지라 전부 만들기엔 너무 많다. "
            "max_variants 를 지정해 개수를 제한하라."
        )

    r = rng or random
    ordered: list[str] = []
    known: set[str] = set()

    def push(s: str) -> bool:
        """반환값: 아직 채울 자리가 남았는지."""
        if s not in known:
            known.add(s)
            ordered.append(s)
        return max_variants is None or len(ordered) < max_variants

    if strategy == "random" and total > MAX_EXHAUSTIVE_VARIANTS:
        # 전수 열거가 불가능한 규모 -> 무작위 표본추출.
        assert max_variants is not None
        if include_original and not push(text):
            return ordered
        for _ in range(max_variants * 20):
            changed = r.sample(list(sites), r.randint(1, len(sites)))
            combo = [r.choice(s.options) for s in changed]
            if not push(apply_edits(text, combo)):
                return ordered
        return ordered

    if strategy == "random":
        # 전부 만든 뒤 섞어서 잘라낸다 -> 전체에서 고르게 뽑힌다.
        pool = list(dict.fromkeys(_combinations(text, sites)))
        pool = [v for v in pool if v != text]
        r.shuffle(pool)
        if include_original:
            push(text)
        for variant in pool:
            if not push(variant):
                break
        return ordered

    if include_original and not push(text):
        return ordered
    for variant in _combinations(text, sites):  # 필요한 만큼만 만들어진다
        if not push(variant):
            break
    return ordered


class Transform(abc.ABC):
    """글 변형기 인터페이스. 변형기마다 파일 하나."""

    #: 레지스트리 키 겸 CLI 이름. 파일명과 같게 두는 것을 권한다.
    name: ClassVar[str] = ""
    #: `--list` 에 표시할 한 줄 설명.
    description: ClassVar[str] = ""

    @abc.abstractmethod
    def find(self, text: str, **options: Any) -> list[Edit]:
        """`text` 에서 적용 가능한 편집을 등장 순서대로 반환한다.

        같은 구간에 대안이 여럿이면 그 구간의 `Edit` 을 여러 개 내놓으면 된다.
        엔진이 한 자리의 배타적 선택지로 묶어 준다.
        """

    def __call__(self, text: str, **options: Any) -> str:
        """찾은 편집을 적용한다. 자리마다 첫 대안을 쓴다."""
        sites = group_sites(self.find(text, **options))
        return apply_edits(text, [s.options[0] for s in sites])

    # --- CLI 확장 훅 (선택) ---------------------------------------------
    @classmethod
    def add_arguments(cls, parser: Any) -> None:
        """이 변형기 전용 CLI 옵션을 등록한다.

        다른 변형기와 충돌하지 않게 `--<이름>-...` 꼴로 붙이는 것을 권한다.
        """

    @classmethod
    def options_from_args(cls, args: Any) -> dict[str, Any]:
        """파싱된 CLI 인자를 `find()` 에 넘길 옵션 딕셔너리로 바꾼다."""
        return {}

    def __repr__(self) -> str:  # pragma: no cover - 디버깅 편의
        return f"<Transform {self.name}>"


_REGISTRY: dict[str, Transform] = {}


def register(transform: Any) -> Any:
    """변형기를 등록한다. 클래스 데코레이터로도, 인스턴스로도 쓸 수 있다."""
    obj = transform() if isinstance(transform, type) else transform
    if not isinstance(obj, Transform):
        raise TypeError(f"Transform 하위 클래스가 아니다: {transform!r}")
    if not obj.name:
        raise ValueError(f"{type(obj).__name__} 에 name 이 없다")
    _REGISTRY[obj.name] = obj
    return transform  # 데코레이터로 쓸 때 원래 클래스를 그대로 돌려준다


def get(name: str) -> Transform:
    """등록된 변형기를 이름으로 찾는다."""
    try:
        return _REGISTRY[name]
    except KeyError:
        raise KeyError(
            f"등록되지 않은 변형기: {name!r} (사용 가능: {', '.join(names())})"
        ) from None


def names() -> list[str]:
    """등록된 변형기 이름 목록."""
    return sorted(_REGISTRY)


def transforms(selected: Sequence[str] | None = None) -> list[Transform]:
    """`selected` 순서대로 변형기를 돌려준다. `None` 이면 등록된 전부."""
    if selected is None:
        return [_REGISTRY[n] for n in names()]
    return [get(n) for n in selected]

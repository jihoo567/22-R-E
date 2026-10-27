"""문제 프롬프트의 조사·생략 변형을 만들어 KPR 문제 JSONL로 내보냅니다.

변형기 구현은 prompt_modify 프로젝트에서 옮겨 왔습니다. 형태소 분석에
kiwipiepy를 쓰므로, 다른 명령이 무거워지지 않도록 `kpr variants` 를 실행할 때만
이 패키지를 불러옵니다.

    particle  조사·주제화  josa_omit(조사 생략), josa_swap(같은 뜻 조사 치환)
    omission  생략·압축    subject_drop(반복 주어 생략), deixis_drop(지시어 생략)
"""

from __future__ import annotations

import importlib

#: 등록할 변형기 모듈. 새 변형기 파일을 만들면 여기에 이름을 더합니다.
_TRANSFORM_MODULES = ("josa_omit", "josa_swap", "subject_drop", "deixis_drop")

for _name in _TRANSFORM_MODULES:
    importlib.import_module(f"{__name__}.{_name}")

from .export import FAMILIES, export  # noqa: E402

__all__ = ["FAMILIES", "export"]

"""문제 → 테스트 모델 → Judge를 메모리에서 순서대로 실행합니다."""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import TextIO

from .config import RunConfig
from .dataset import Problem
from .providers import generate_text


def build_judge_prompt(problem: Problem, response: str) -> str:
    return f"""다음 문제와 테스트 모델의 답변을 검토하고 평가 결과를 작성하세요.
별도의 채점 기준이나 점수 형식은 제공되지 않습니다.

<problem>
{problem.prompt}
</problem>

<test_model_response>
{response}
</test_model_response>
"""


def run_benchmark(
    problems: list[Problem],
    config: RunConfig,
    *,
    output: TextIO | None = None,
    generate: Callable[..., str] = generate_text,
) -> int:
    """결과 파일 없이 두 모델의 원문 응답을 콘솔에 출력합니다."""
    stream = output or sys.stdout
    failures = 0
    total = len(problems)

    for index, problem in enumerate(problems, 1):
        print("=" * 72, file=stream)
        print(f"[{index}/{total}] 문제 ID: {problem.id}", file=stream)
        print("\n[문제]", file=stream)
        print(problem.prompt, file=stream, flush=True)

        try:
            test_response = generate(
                problem.prompt,
                config.test_model,
                system_instruction=config.test_model.system_instruction,
            )
        except Exception as error:
            print("\n[테스트 모델 답변]", file=stream)
            print(f"생성 실패: {type(error).__name__}: {error}", file=stream, flush=True)
            failures += 1
            continue

        print("\n[테스트 모델 답변]", file=stream)
        print(test_response, file=stream, flush=True)

        rendered_prompt = build_judge_prompt(problem, test_response)
        print("\n[Judge 모델 답변]", file=stream)
        try:
            judge_response = generate(
                rendered_prompt,
                config.judge_model,
                system_instruction=config.judge_model.system_instruction,
            )
        except Exception as error:
            failures += 1
            print(
                f"평가 실패: {type(error).__name__}: {error}",
                file=stream,
                flush=True,
            )
        else:
            print(judge_response, file=stream, flush=True)

    print("=" * 72, file=stream)
    summary = f"실행 완료: {total}개 문제"
    if failures:
        summary += f", 실패 {failures}개"
    print(summary, file=stream, flush=True)
    return failures

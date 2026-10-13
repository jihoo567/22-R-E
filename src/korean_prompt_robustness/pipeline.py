"""테스트 답변 생성과 저장된 답변 평가를 서로 분리해 실행합니다."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import TextIO

from .config import ProviderSettings
from .dataset import Problem
from .providers import generate_text
from .responses import SavedResponse


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


def generate_answers(
    problems: list[Problem],
    settings: ProviderSettings,
    *,
    output: TextIO | None = None,
    response_output: TextIO | None = None,
    generate: Callable[..., str] = generate_text,
) -> int:
    """테스트 모델 답변을 생성하고 콘솔과 JSONL에 기록합니다."""
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
                settings,
                system_instruction=settings.system_instruction,
            )
        except Exception as error:
            print("\n[테스트 모델 답변]", file=stream)
            print(f"생성 실패: {type(error).__name__}: {error}", file=stream, flush=True)
            failures += 1
            continue

        print("\n[테스트 모델 답변]", file=stream)
        print(test_response, file=stream, flush=True)
        if response_output is not None:
            json.dump(
                SavedResponse(problem, test_response).to_dict(),
                response_output,
                ensure_ascii=False,
            )
            response_output.write("\n")
            response_output.flush()

    print("=" * 72, file=stream)
    summary = f"답변 생성 완료: {total}개 문제"
    if failures:
        summary += f", 실패 {failures}개"
    print(summary, file=stream, flush=True)
    return failures


def evaluate_answers(
    responses: list[SavedResponse],
    settings: ProviderSettings,
    *,
    output: TextIO | None = None,
    generate: Callable[..., str] = generate_text,
) -> int:
    """저장된 테스트 답변을 Judge 모델로 평가해 콘솔에 출력합니다."""
    stream = output or sys.stdout
    failures = 0
    total = len(responses)

    for index, saved in enumerate(responses, 1):
        problem = saved.problem
        print("=" * 72, file=stream)
        print(f"[{index}/{total}] 문제 ID: {problem.id}", file=stream)
        print("\n[문제]", file=stream)
        print(problem.prompt, file=stream)
        print("\n[테스트 모델 답변]", file=stream)
        print(saved.test_model_response, file=stream)
        print("\n[Judge 모델 답변]", file=stream)
        rendered_prompt = build_judge_prompt(problem, saved.test_model_response)
        try:
            judge_response = generate(
                rendered_prompt,
                settings,
                system_instruction=settings.system_instruction,
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
    summary = f"평가 완료: {total}개 답변"
    if failures:
        summary += f", 실패 {failures}개"
    print(summary, file=stream, flush=True)
    return failures

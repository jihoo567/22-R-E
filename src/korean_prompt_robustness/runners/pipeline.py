"""문제 → 테스트 모델 → Judge를 메모리에서 순서대로 실행합니다."""

from __future__ import annotations

import sys
from typing import TextIO

from ..config import RunConfig
from ..judges import JudgeAdapter
from ..judges.prompt import build_judge_prompt
from ..models import ModelAdapter
from ..schemas import Problem


def run_benchmark(
    problems: list[Problem],
    config: RunConfig,
    model: ModelAdapter,
    judge: JudgeAdapter,
    *,
    output: TextIO | None = None,
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
            test_response = model.generate(problem, config.test_model)
        except Exception as error:
            print("\n[테스트 모델 답변]", file=stream)
            print(f"생성 실패: {type(error).__name__}: {error}", file=stream, flush=True)
            failures += 1
            continue

        print("\n[테스트 모델 답변]", file=stream)
        print(test_response, file=stream, flush=True)

        rendered_prompt = build_judge_prompt(problem, test_response)
        judge_error: Exception | None = None
        try:
            judge_response = judge.judge(
                problem,
                test_response,
                rendered_prompt,
                config.judge_model,
            )
        except Exception as error:
            judge_response = None
            judge_error = error
            failures += 1

        print("\n[Judge 모델 답변]", file=stream)
        if judge_response is None:
            assert judge_error is not None
            print(
                f"평가 실패: {type(judge_error).__name__}: {judge_error}",
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

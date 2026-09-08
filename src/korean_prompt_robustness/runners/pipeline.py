"""문제 → 테스트 모델 → Judge를 메모리에서 순서대로 실행합니다."""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from typing import Any, TextIO, TypeVar

from ..config import ProviderSettings, RunConfig
from ..judges import JudgeAdapter
from ..judges.prompt import build_judge_prompt
from ..models import ModelAdapter
from ..schemas import Problem


T = TypeVar("T")


def _call_with_retries(
    call: Callable[[], T],
    settings: ProviderSettings,
    label: str,
    output: TextIO,
) -> T:
    """제한된 횟수만 재시도하고 오류는 콘솔에 표시합니다."""
    last_error: Exception | None = None
    for attempt in range(1, settings.max_retries + 2):
        try:
            return call()
        except Exception as error:  # API와 로컬 프로세스 오류를 함께 처리합니다.
            last_error = error
            print(
                f"[{label} 오류] {attempt}/{settings.max_retries + 1}: "
                f"{type(error).__name__}: {error}",
                file=output,
                flush=True,
            )
            if attempt <= settings.max_retries:
                time.sleep(settings.retry_delay_seconds)
    assert last_error is not None
    raise last_error


def run_benchmark(
    problems: list[Problem],
    config: RunConfig,
    model: ModelAdapter,
    judge: JudgeAdapter,
    *,
    output: TextIO | None = None,
) -> list[dict[str, Any]]:
    """결과 파일 없이 두 모델의 원문 응답을 콘솔에 출력합니다."""
    stream = output or sys.stdout
    results: list[dict[str, Any]] = []
    total = len(problems)

    for index, problem in enumerate(problems, 1):
        print("=" * 72, file=stream)
        print(f"[{index}/{total}] 문제 ID: {problem.id}", file=stream)
        print("\n[문제]", file=stream)
        print(problem.prompt, file=stream, flush=True)

        try:
            model_output = _call_with_retries(
                lambda: model.generate(problem, config.test_model),
                config.test_model,
                "테스트 모델",
                stream,
            )
        except Exception as error:
            print("\n[테스트 모델 답변]", file=stream)
            print(f"생성 실패: {type(error).__name__}: {error}", file=stream, flush=True)
            results.append(
                {
                    "problem_id": problem.id,
                    "test_response": None,
                    "judge_response": None,
                    "error": str(error),
                }
            )
            continue

        test_response = model_output.text
        print("\n[테스트 모델 답변]", file=stream)
        print(test_response, file=stream, flush=True)

        rendered_prompt = build_judge_prompt(problem, test_response)
        judge_error: Exception | None = None
        try:
            judge_response = _call_with_retries(
                lambda: judge.judge(
                    problem,
                    test_response,
                    rendered_prompt,
                    config.judge_model,
                ),
                config.judge_model,
                "Judge 모델",
                stream,
            )
        except Exception as error:
            judge_response = None
            judge_error = error

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

        results.append(
            {
                "problem_id": problem.id,
                "test_response": test_response,
                "judge_response": judge_response,
                "error": str(judge_error) if judge_error else None,
            }
        )

    print("=" * 72, file=stream)
    print(f"실행 완료: {total}개 문제", file=stream, flush=True)
    return results

"""문제와 테스트 모델 응답을 Judge에 전달하는 최소 템플릿."""

from __future__ import annotations

from ..schemas import Problem


JUDGE_PROMPT_VERSION = "judge-basic-v1"


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

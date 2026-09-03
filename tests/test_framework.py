from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from korean_prompt_robustness.config import JudgeSettings, ProviderSettings, RunConfig
from korean_prompt_robustness.evaluators.final import combine_scores
from korean_prompt_robustness.evaluators.rules import evaluate_rules
from korean_prompt_robustness.judges.base import JudgeAdapter
from korean_prompt_robustness.judges.factory import create_judge
from korean_prompt_robustness.judges.local import LocalCommandJudge
from korean_prompt_robustness.judges.validation import parse_judge_json
from korean_prompt_robustness.metrics.robustness import calculate_robustness
from korean_prompt_robustness.models.mock import MockModel
from korean_prompt_robustness.models.local import LocalCommandModel
from korean_prompt_robustness.models.base import ModelAdapter, ModelOutput
from korean_prompt_robustness.runners.generation import generate_responses
from korean_prompt_robustness.runners.judging import judge_responses
from korean_prompt_robustness.runners.scoring import score_rule_responses
from korean_prompt_robustness.cli import run_pipeline
from korean_prompt_robustness.io import read_jsonl
from korean_prompt_robustness.schemas.problem import Problem, Rule, validate_dataset


def custom_contains(response: str, context: dict) -> bool:
    return "맞춤" in response


def problem_record(
    problem_id: str,
    parent_id: str,
    variant_type: str,
    response: str = "필수 문장.",
) -> dict:
    return {
        "id": problem_id,
        "parent_id": parent_id,
        "variant_type": variant_type,
        "prompt": f"{problem_id} 프롬프트",
        "reference_answer": None,
        "evaluation_rules": [
            {"rule_id": "r1", "type": "must_include", "value": "필수"}
        ],
        "metadata": {
            "category": "test",
            "source": "test",
            "mock_response": response,
        },
    }


def config(mode: str = "hybrid", retries: int = 1, version: str = "1.0") -> RunConfig:
    return RunConfig(
        dataset_version="test-v1",
        scoring_mode=mode,
        rule_evaluator_version=version,
        pass_threshold=100.0,
        test_model=ProviderSettings(
            provider="mock",
            model_id="mock-model",
            max_retries=retries,
            retry_delay_seconds=0,
        ),
        judge_model=JudgeSettings(
            provider="mock",
            model_id="mock-judge",
            max_retries=retries,
            retry_delay_seconds=0,
            prompt_version="judge-ko-v1",
        ),
        allow_mock_judge=True,
    )


class SequenceJudge(JudgeAdapter):
    def __init__(self, outputs: list[str]):
        self.outputs = outputs
        self.call_count = 0

    def judge(self, problem, response, rendered_prompt, settings):
        output = self.outputs[self.call_count]
        self.call_count += 1
        return output


class FailOnceModel(ModelAdapter):
    def __init__(self):
        self.call_count = 0

    def generate(self, problem, settings):
        self.call_count += 1
        if self.call_count == 1:
            raise RuntimeError("의도한 첫 실행 중단")
        return ModelOutput("필수 문장.", {"text": "필수 문장."})


class SchemaTests(unittest.TestCase):
    def test_input_schema_validation(self):
        records = [
            problem_record("p-original", "p", "original"),
            problem_record("p-v1", "p", "particle_omission"),
        ]
        problems = validate_dataset(records)
        self.assertEqual(2, len(problems))
        broken = [dict(records[1])]
        with self.assertRaisesRegex(ValueError, "original"):
            validate_dataset(broken)

    def test_parent_id_links_original_and_variants(self):
        problems = validate_dataset(
            [
                problem_record("p-original", "p", "original"),
                problem_record("p-v1", "p", "word_order"),
                problem_record("p-v2", "p", "honorific_change"),
            ]
        )
        group = [item for item in problems if item.parent_id == "p"]
        self.assertEqual(1, sum(item.is_original for item in group))
        self.assertEqual(2, sum(not item.is_original for item in group))

    def test_test_model_and_judge_providers_are_independent(self):
        value = {
            "dataset_version": "test-v1",
            "test_model": {
                "provider": "local",
                "model_id": "local-test",
                "command": "local-llm-command",
            },
            "judge_model": {
                "provider": "gemini",
                "model_id": "gemini-judge",
            },
        }
        parsed = RunConfig.from_dict(value)
        self.assertEqual("local", parsed.test_model.provider)
        self.assertEqual("gemini", parsed.judge_model.provider)

        value["judge_model"] = {
            "provider": "local",
            "model_id": "local-judge",
            "command": "/bin/cat",
        }
        parsed = RunConfig.from_dict(value)
        self.assertEqual("local", parsed.test_model.provider)
        self.assertEqual("local", parsed.judge_model.provider)
        self.assertIsInstance(create_judge(parsed.judge_model), LocalCommandJudge)

        value["judge_model"].pop("command")
        with self.assertRaisesRegex(ValueError, "command"):
            RunConfig.from_dict(value)

    def test_mock_judge_needs_explicit_test_flag(self):
        settings = JudgeSettings(provider="mock", model_id="mock-judge")
        with self.assertRaisesRegex(ValueError, "Mock Judge"):
            create_judge(settings)
        self.assertIsNotNone(create_judge(settings, allow_mock_judge=True))


class RuleTests(unittest.TestCase):
    def test_basic_rule_evaluators_and_indeterminate(self):
        raw_rules = [
            {"rule_id": "i", "type": "must_include", "value": "맞춤"},
            {"rule_id": "e", "type": "must_exclude", "value": "금지"},
            {"rule_id": "l", "type": "line_count", "value": 2},
            {"rule_id": "s", "type": "sentence_count", "value": 2},
            {"rule_id": "b", "type": "line_starts", "value": ["가", "나"]},
            {"rule_id": "r", "type": "regex", "value": "끝\\.$"},
            {
                "rule_id": "c",
                "type": "custom_python",
                "value": "test_framework:custom_contains",
            },
            {"rule_id": "u", "type": "semantic", "value": "의미"},
        ]
        rules = tuple(
            Rule.from_dict(value, f"rule[{index}]")
            for index, value in enumerate(raw_rules)
        )
        result = evaluate_rules(rules, "가 맞춤 문장.\n나 끝.")
        self.assertEqual(7, result["passed_count"])
        self.assertEqual(7, result["evaluated_count"])
        self.assertEqual(1, result["indeterminate_count"])
        self.assertEqual(100.0, result["score"])

    def test_saved_response_can_be_rescored_without_model(self):
        problems = validate_dataset([problem_record("p-original", "p", "original")])
        response = {
            "status": "complete",
            "problem_id": "p-original",
            "request_fingerprint": "saved-response",
            "response": "필수 문장.",
        }
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            first = score_rule_responses(
                problems, [response], config("rule_only", version="1.0"),
                "score-v1", base / "v1.jsonl", base
            )
            second = score_rule_responses(
                problems, [response], config("rule_only", version="2.0"),
                "score-v2", base / "v2.jsonl", base
            )
        self.assertEqual(100.0, first[0]["score"])
        self.assertEqual("2.0", second[0]["rule_evaluator_version"])


class JudgeTests(unittest.TestCase):
    def test_judge_json_validation(self):
        raw = json.dumps(
            {
                "verdict": "pass",
                "score": 1,
                "reason": "충족",
                "criteria": [
                    {"criterion_id": "r1", "passed": True, "reason": "충족"}
                ],
            },
            ensure_ascii=False,
        )
        self.assertEqual("pass", parse_judge_json(raw, ["r1"])["verdict"])
        with self.assertRaises(ValueError):
            parse_judge_json('{"verdict":"pass"}', ["r1"])

    def test_invalid_judge_response_is_retried(self):
        problems = validate_dataset([problem_record("p-original", "p", "original")])
        response = {
            "status": "complete",
            "problem_id": "p-original",
            "request_fingerprint": "response-key",
            "response": "필수 문장.",
        }
        valid = json.dumps(
            {
                "verdict": "pass",
                "score": 1,
                "reason": "충족",
                "criteria": [
                    {"criterion_id": "r1", "passed": True, "reason": "충족"}
                ],
            },
            ensure_ascii=False,
        )
        judge = SequenceJudge(["not-json", valid])
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            records, counts = judge_responses(
                problems, [response], config(retries=1), judge, "judge-run",
                base / "judge.jsonl", base / "cache.jsonl", base
            )
        self.assertEqual(2, judge.call_count)
        self.assertEqual(1, counts["judged"])
        self.assertEqual(2, len(records[0]["attempts"]))

    def test_rule_judge_conflict_requires_human_review(self):
        combined = combine_scores(
            "hybrid",
            {"score": 0.0, "error_count": 0},
            {"verdict": "pass", "score": 1},
        )
        self.assertTrue(combined["conflict"])
        self.assertTrue(combined["human_review_required"])
        self.assertIsNone(combined["final_score"])


class RunnerAndMetricTests(unittest.TestCase):
    def test_local_model_receives_prompt_through_stdin(self):
        problems = validate_dataset([problem_record("p-original", "p", "original")])
        settings = ProviderSettings(
            provider="local",
            model_id="local-cat",
            command="/bin/cat",
        )
        output = LocalCommandModel().generate(problems[0], settings)
        self.assertEqual(problems[0].prompt, output.text)

    def test_local_judge_receives_rendered_prompt_through_stdin(self):
        problems = validate_dataset([problem_record("p-original", "p", "original")])
        settings = JudgeSettings(
            provider="local",
            model_id="local-cat",
            command="/bin/cat",
        )
        rendered_prompt = "Judge에 전달할 구조화 평가 프롬프트"
        output = LocalCommandJudge().judge(
            problems[0], "모델 응답", rendered_prompt, settings
        )
        self.assertEqual(rendered_prompt, output)

    def test_response_cache_and_resume(self):
        original = problem_record("p-original", "p", "original")
        variant = problem_record("p-v1", "p", "word_order")
        variant["prompt"] = original["prompt"]  # 같은 문구여도 문제 ID는 보존되어야 합니다.
        problems = validate_dataset([original, variant])
        model = MockModel()
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            first, first_counts = generate_responses(
                problems, config(), model, "run-1", base / "run-1.jsonl",
                base / "cache.jsonl", base
            )
            second, second_counts = generate_responses(
                problems, config(), model, "run-1", base / "run-1.jsonl",
                base / "cache.jsonl", base
            )
            third, third_counts = generate_responses(
                problems, config(), model, "run-2", base / "run-2.jsonl",
                base / "cache.jsonl", base
            )
        self.assertEqual(2, model.call_count)
        self.assertEqual(2, first_counts["generated"])
        self.assertEqual(2, second_counts["skipped"])
        self.assertEqual(2, third_counts["cached"])
        self.assertEqual(2, len(first))
        self.assertEqual(2, len(second))
        self.assertEqual(2, len(third))
        self.assertEqual({"p-original", "p-v1"}, {item["problem_id"] for item in third})

    def test_interrupted_failure_resumes_and_rescores_latest_response(self):
        problems = validate_dataset([problem_record("p-original", "p", "original")])
        model = FailOnceModel()
        run_config = config("rule_only", retries=0)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            output = base / "responses.jsonl"
            cache = base / "cache.jsonl"
            first, first_counts = generate_responses(
                problems, run_config, model, "resume", output, cache, base
            )
            second, second_counts = generate_responses(
                problems, run_config, model, "resume", output, cache, base
            )
            scores = score_rule_responses(
                problems, read_jsonl(output), run_config, "rescore",
                base / "rules.jsonl", base
            )
        self.assertEqual("error", first[0]["status"])
        self.assertEqual(1, first_counts["failed"])
        self.assertEqual("complete", second[0]["status"])
        self.assertEqual(1, second_counts["generated"])
        self.assertEqual(1, len(scores))
        self.assertEqual(100.0, scores[0]["score"])

    def test_score_difference_and_robust_accuracy(self):
        def final(problem_id, parent, variant, score):
            return {
                "run_id": "r",
                "problem_id": problem_id,
                "parent_id": parent,
                "variant_type": variant,
                "category": "cat",
                "model_id": "m",
                "comparison_condition_key": "same",
                "final_score": score,
                "conflict": False,
                "human_review_required": False,
            }

        records = [
            final("a-o", "a", "original", 100.0),
            final("a-v", "a", "word_order", 80.0),
            final("b-o", "b", "original", 100.0),
            final("b-v", "b", "word_order", 100.0),
        ]
        pairs, summary = calculate_robustness(records)
        pair_a = next(pair for pair in pairs if pair["parent_id"] == "a")
        self.assertEqual(-20.0, pair_a["score_difference"])
        self.assertEqual(20.0, pair_a["score_drop"])
        self.assertEqual(50.0, summary["robust_accuracy"])

    def test_incompatible_conditions_are_excluded(self):
        records = [
            {
                "run_id": "r", "problem_id": "o", "parent_id": "p",
                "variant_type": "original", "category": "c", "model_id": "m",
                "comparison_condition_key": "one", "final_score": 100,
                "conflict": False, "human_review_required": False,
            },
            {
                "run_id": "r", "problem_id": "v", "parent_id": "p",
                "variant_type": "word_order", "category": "c", "model_id": "m",
                "comparison_condition_key": "two", "final_score": 100,
                "conflict": False, "human_review_required": False,
            },
        ]
        pairs, summary = calculate_robustness(records)
        self.assertTrue(pairs[0]["excluded"])
        self.assertIn("조건", pairs[0]["exclusion_reason"])
        self.assertEqual(1, summary["excluded_pair_count"])

    def test_mock_end_to_end_pipeline(self):
        records = [
            problem_record("p-original", "p", "original"),
            problem_record("p-v1", "p", "word_order"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            input_path = base / "input.jsonl"
            input_path.write_text(
                "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records),
                encoding="utf-8",
            )
            result = run_pipeline(input_path, config(), "e2e", base / "results", base)
            self.assertEqual(100.0, result["summary"]["robust_accuracy"])
            self.assertEqual(1, result["summary"]["robust_parent_count"])
            self.assertEqual(7, len(result["report_paths"]))
            self.assertEqual(
                2, len(read_jsonl(base / "results" / "scores" / "e2e.final.jsonl"))
            )


if __name__ == "__main__":
    unittest.main()

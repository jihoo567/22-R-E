from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from korean_prompt_robustness.cli import main
from korean_prompt_robustness.config import (
    ProviderSettings,
    RunConfig,
    load_config,
    make_provider_settings,
    save_config,
)
from korean_prompt_robustness.judges.base import JudgeAdapter
from korean_prompt_robustness.judges.local import LocalCommandJudge
from korean_prompt_robustness.judges.prompt import build_judge_prompt
from korean_prompt_robustness.local_process import command_executable, prepare_command
from korean_prompt_robustness.models.base import ModelAdapter, ModelOutput
from korean_prompt_robustness.models.local import LocalCommandModel
from korean_prompt_robustness.models.openai_compatible import (
    call_openai_compatible,
    extract_openai_text,
)
from korean_prompt_robustness.runners import run_benchmark
from korean_prompt_robustness.schemas.problem import validate_dataset


def problem_record(problem_id: str = "problem-001") -> dict:
    return {
        "id": problem_id,
        "prompt": f"{problem_id}의 질문입니다.",
        "metadata": {"category": "test"},
    }


def stdin_echo_command() -> str:
    return f'"{sys.executable}" -c "import sys;sys.stdout.write(sys.stdin.read())"'


def local_settings(model_id: str = "local-test") -> ProviderSettings:
    return ProviderSettings(
        provider="local",
        model_id=model_id,
        command=stdin_echo_command(),
        max_retries=0,
    )


class StaticModel(ModelAdapter):
    def generate(self, problem, settings):
        text = f"테스트 답변: {problem.id}"
        return ModelOutput(text, {"text": text})


class StaticJudge(JudgeAdapter):
    def __init__(self) -> None:
        self.received_response: str | None = None

    def judge(self, problem, response, rendered_prompt, settings):
        self.received_response = response
        return f"Judge 답변: {response}를 검토했습니다."


class SchemaAndConfigTests(unittest.TestCase):
    def test_minimal_problem_schema(self):
        problems = validate_dataset([problem_record()])
        self.assertEqual("problem-001", problems[0].id)
        self.assertIn("질문", problems[0].prompt)

    def test_duplicate_problem_id_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "중복"):
            validate_dataset([problem_record(), problem_record()])

    def test_configure_supports_gemini_and_local_separately(self):
        config = RunConfig(
            test_model=make_provider_settings(
                "local",
                "qwen2.5:14b",
                None,
                base_url=None,
                api_key_env=None,
                timeout_seconds=600,
            ),
            judge_model=make_provider_settings(
                "gemini",
                "gemini-3.6-flash",
                None,
                base_url=None,
                api_key_env="KPR_JUDGE_API_KEY",
                timeout_seconds=120,
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            save_config(path, config)
            loaded = load_config(path)

        self.assertEqual("local", loaded.test_model.provider)
        self.assertEqual("ollama run qwen2.5:14b", loaded.test_model.command)
        self.assertEqual("gemini", loaded.judge_model.provider)
        self.assertEqual("gemini-3.6-flash", loaded.judge_model.model_id)
        self.assertIsNone(loaded.judge_model.command)

    def test_openai_compatible_requires_model_base_url_and_key_name(self):
        settings = make_provider_settings(
            "openai-compatible",
            "example-model",
            None,
            base_url="https://example.test/v1/",
            api_key_env="KPR_TEST_API_KEY",
            timeout_seconds=120,
        )
        self.assertEqual("https://example.test/v1", settings.base_url)
        with self.assertRaisesRegex(ValueError, "base_url"):
            make_provider_settings(
                "openai-compatible",
                "example-model",
                None,
                base_url=None,
                api_key_env="KPR_TEST_API_KEY",
                timeout_seconds=120,
            )

    def test_run_refuses_to_start_before_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            input_path = base / "problems.jsonl"
            input_path.write_text(
                json.dumps(problem_record(), ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            stderr = io.StringIO()
            with redirect_stderr(stderr), self.assertRaises(SystemExit):
                main(
                    [
                        "run",
                        str(input_path),
                        "--settings",
                        str(base / "missing.json"),
                    ]
                )

        self.assertIn("먼저 'kpr configure'", stderr.getvalue())


class AdapterTests(unittest.TestCase):
    def test_windows_command_keeps_quoted_path_intact(self):
        command = '"C:\\Program Files\\Python\\python.exe" -c "print(1)"'
        self.assertEqual(command, prepare_command(command, platform="nt"))
        self.assertEqual(
            "C:\\Program Files\\Python\\python.exe",
            command_executable(command, platform="nt"),
        )

    def test_local_model_preserves_utf8_stdin_and_stdout(self):
        problem = validate_dataset([problem_record()])[0]
        output = LocalCommandModel().generate(problem, local_settings())
        self.assertEqual(problem.prompt, output.text)

    def test_local_judge_preserves_utf8_stdin_and_stdout(self):
        problem = validate_dataset([problem_record()])[0]
        rendered = "한글 Judge 입력"
        output = LocalCommandJudge().judge(
            problem, "한글 답변", rendered, local_settings()
        )
        self.assertEqual(rendered, output)

    def test_judge_prompt_contains_problem_and_test_response(self):
        problem = validate_dataset([problem_record()])[0]
        rendered = build_judge_prompt(problem, "테스트 모델의 답변")
        self.assertIn(problem.prompt, rendered)
        self.assertIn("테스트 모델의 답변", rendered)

    def test_openai_compatible_request_and_response(self):
        settings = ProviderSettings.from_dict(
            {
                "provider": "openai-compatible",
                "model_id": "example-model",
                "base_url": "https://example.test/v1",
                "api_key_env": "KPR_TEST_API_KEY",
                "max_retries": 0,
            },
            "test_model",
        )
        captured: dict = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(
                    {"choices": [{"message": {"content": "API 답변"}}]},
                    ensure_ascii=False,
                ).encode("utf-8")

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["authorization"] = request.get_header("Authorization")
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse()

        with patch.dict(os.environ, {"KPR_TEST_API_KEY": "secret-test-key"}), patch(
            "urllib.request.urlopen", side_effect=fake_urlopen
        ):
            response = call_openai_compatible(prompt="한글 문제", settings=settings)

        self.assertEqual("API 답변", extract_openai_text(response))
        self.assertEqual("https://example.test/v1/chat/completions", captured["url"])
        self.assertEqual("Bearer secret-test-key", captured["authorization"])
        self.assertEqual("example-model", captured["body"]["model"])
        self.assertEqual("한글 문제", captured["body"]["messages"][0]["content"])


class PipelineTests(unittest.TestCase):
    def test_pipeline_prints_both_answers_without_result_files(self):
        problems = validate_dataset([problem_record()])
        judge = StaticJudge()
        config = RunConfig(local_settings("test"), local_settings("judge"))
        output = io.StringIO()

        results = run_benchmark(
            problems, config, StaticModel(), judge, output=output
        )

        printed = output.getvalue()
        self.assertIn("[테스트 모델 답변]", printed)
        self.assertIn("테스트 답변: problem-001", printed)
        self.assertIn("[Judge 모델 답변]", printed)
        self.assertIn("Judge 답변:", printed)
        self.assertEqual(results[0]["test_response"], judge.received_response)

    def test_configure_then_run_uses_console_only(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            settings_path = base / "config.json"
            input_path = base / "problems.jsonl"
            input_path.write_text(
                json.dumps(problem_record(), ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            command = stdin_echo_command()
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                main(
                    [
                        "configure",
                        "--test",
                        "local",
                        "--judge",
                        "local",
                        "--test-model",
                        "echo-test",
                        "--judge-model",
                        "echo-judge",
                        "--test-command",
                        command,
                        "--judge-command",
                        command,
                        "--settings",
                        str(settings_path),
                    ]
                )
                main(["run", str(input_path), "--settings", str(settings_path)])

            created_files = sorted(path.name for path in base.iterdir())

        self.assertEqual(["config.json", "problems.jsonl"], created_files)
        self.assertIn("[테스트 모델 답변]", stdout.getvalue())
        self.assertIn("[Judge 모델 답변]", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from korean_prompt_robustness.cli import DEFAULT_SETTINGS_PATH, main
from korean_prompt_robustness.config import (
    ProviderSettings,
    RunConfig,
    load_config,
)
from korean_prompt_robustness.local_process import command_executable, prepare_command
from korean_prompt_robustness.providers import generate_text
from korean_prompt_robustness.providers.gemini import extract_text
from korean_prompt_robustness.pipeline import (
    build_judge_prompt,
    evaluate_answers,
    generate_answers,
)
from korean_prompt_robustness.responses import SavedResponse, load_saved_responses
from korean_prompt_robustness.dataset import load_and_validate_dataset, validate_dataset


def load_bootstrap_module():
    path = Path(__file__).resolve().parents[1] / "kpr.py"
    spec = importlib.util.spec_from_file_location("kpr_bootstrap", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def problem_record(problem_id: str = "problem-001") -> dict:
    return {
        "id": problem_id,
        "prompt": f"{problem_id}의 질문입니다.",
        "metadata": {"category": "test"},
    }


def stdin_echo_command() -> str:
    return f'"{sys.executable}" -c "import sys;sys.stdout.write(sys.stdin.read())"'


def local_settings(
    model_id: str = "local-test",
    system_instruction: str | None = None,
) -> ProviderSettings:
    return ProviderSettings(
        provider="local",
        model_id=model_id,
        command=stdin_echo_command(),
        system_instruction=system_instruction,
    )


def write_config(path: Path, config: RunConfig) -> None:
    path.write_text(
        json.dumps(config.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


class SchemaAndConfigTests(unittest.TestCase):
    def test_default_settings_are_stored_in_the_working_project(self):
        self.assertEqual(
            Path.cwd() / "kpr-config.json", DEFAULT_SETTINGS_PATH.resolve()
        )

    def test_minimal_problem_schema(self):
        problems = validate_dataset([problem_record()])
        self.assertEqual("problem-001", problems[0].id)
        self.assertIn("질문", problems[0].prompt)

    def test_duplicate_problem_id_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "중복"):
            validate_dataset([problem_record(), problem_record()])

    def test_blank_prompt_is_rejected(self):
        record = problem_record()
        record["prompt"] = "   "
        with self.assertRaisesRegex(ValueError, "prompt"):
            validate_dataset([record])

    def test_limit_retains_only_requested_problems_but_validates_the_whole_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "문제.jsonl"
            records = [problem_record(str(index)) for index in range(100)]
            path.write_text(
                "\n".join(json.dumps(record) for record in records), encoding="utf-8"
            )
            self.assertEqual(1, len(load_and_validate_dataset(path, limit=1)))
            with self.assertRaisesRegex(ValueError, "1 이상"):
                load_and_validate_dataset(path, limit=0)
            with path.open("a", encoding="utf-8") as file:
                file.write("\n" + json.dumps(records[0]))
            with self.assertRaisesRegex(ValueError, "중복"):
                load_and_validate_dataset(path, limit=1)

    def test_default_paths_follow_working_directory_after_import(self):
        original = Path.cwd()
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ):
            base = Path(directory)
            (base / ".env").write_text("KPR_PATH_TEST=loaded\n", encoding="utf-8")
            write_config(
                base / "kpr-config.json",
                RunConfig(local_settings("test"), local_settings("judge")),
            )
            os.environ.pop("KPR_PATH_TEST", None)
            try:
                os.chdir(base)
                with redirect_stdout(io.StringIO()):
                    main(["show-config"])
                self.assertEqual("loaded", os.environ["KPR_PATH_TEST"])
            finally:
                os.chdir(original)

    def test_config_file_supports_gemini_and_local_separately(self):
        config = RunConfig(
            test_model=ProviderSettings(
                provider="local",
                model_id="qwen2.5:14b",
                command="ollama run qwen2.5:14b",
                timeout_seconds=600,
            ),
            judge_model=ProviderSettings(
                provider="gemini",
                model_id="gemini-3.6-flash",
                api_key_env="KPR_JUDGE_API_KEY",
                timeout_seconds=120,
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            write_config(path, config)
            loaded = load_config(path)

        self.assertEqual("local", loaded.test_model.provider)
        self.assertEqual("ollama run qwen2.5:14b", loaded.test_model.command)
        self.assertEqual("gemini", loaded.judge_model.provider)
        self.assertEqual("gemini-3.6-flash", loaded.judge_model.model_id)
        self.assertIsNone(loaded.judge_model.command)

    def test_example_config_is_valid(self):
        path = Path(__file__).resolve().parents[1] / "kpr-config.example.json"
        config = load_config(path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual("local", config.test_model.provider)
        self.assertEqual("qwen2.5:14b", config.test_model.model_id)
        self.assertEqual("local", config.judge_model.provider)
        self.assertEqual("data/examples/problems.jsonl", config.input_path)
        self.assertEqual("results", config.output_dir)
        self.assertFalse(any(key.startswith("_") for key in raw))
        self.assertNotIn("api_examples", raw)

    def test_config_stores_test_and_judge_system_instructions(self):
        config = RunConfig.from_dict(
            {
                "test_model": {
                    "provider": "local",
                    "model_id": "test",
                    "command": stdin_echo_command(),
                    "system_instruction": "테스트 모델 지시문",
                },
                "judge_model": {
                    "provider": "local",
                    "model_id": "judge",
                    "command": stdin_echo_command(),
                    "system_instruction": "Judge 지시문",
                },
            }
        )
        self.assertEqual(
            "테스트 모델 지시문", config.test_model.system_instruction
        )
        self.assertEqual("Judge 지시문", config.judge_model.system_instruction)

    def test_blank_system_instruction_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "system_instruction"):
            ProviderSettings.from_dict(
                {
                    "provider": "local",
                    "model_id": "test",
                    "command": stdin_echo_command(),
                    "system_instruction": "   ",
                },
                "test_model",
            )

    def test_blank_input_path_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "input_path"):
            RunConfig.from_dict(
                {
                    "input_path": "   ",
                    "test_model": {
                        "provider": "local",
                        "model_id": "test",
                        "command": stdin_echo_command(),
                    },
                    "judge_model": {
                        "provider": "local",
                        "model_id": "judge",
                        "command": stdin_echo_command(),
                    },
                }
            )

    def test_blank_output_dir_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "output_dir"):
            RunConfig.from_dict(
                {
                    "output_dir": "   ",
                    "test_model": {
                        "provider": "local",
                        "model_id": "test",
                        "command": stdin_echo_command(),
                    },
                    "judge_model": {
                        "provider": "local",
                        "model_id": "judge",
                        "command": stdin_echo_command(),
                    },
                }
            )

    def test_help_points_to_markdown_config_guide(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout), self.assertRaises(SystemExit) as exit_context:
            main(["--help"])
        self.assertEqual(0, exit_context.exception.code)
        self.assertIn("CONFIG_GUIDE.md", stdout.getvalue())

    def test_openai_compatible_requires_model_base_url_and_key_name(self):
        settings = ProviderSettings.from_dict(
            {
                "provider": "openai-compatible",
                "model_id": "example-model",
                "base_url": "https://example.test/v1/",
                "api_key_env": "KPR_TEST_API_KEY",
                "timeout_seconds": 120,
            },
            "test_model",
        )
        self.assertEqual("https://example.test/v1", settings.base_url)
        with self.assertRaisesRegex(ValueError, "base_url"):
            ProviderSettings.from_dict(
                {
                    "provider": "openai-compatible",
                    "model_id": "example-model",
                    "base_url": None,
                    "api_key_env": "KPR_TEST_API_KEY",
                    "timeout_seconds": 120,
                },
                "test_model",
            )

    def test_answer_refuses_to_start_without_config_file(self):
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
                        "answer",
                        str(input_path),
                        "--settings",
                        str(base / "missing.json"),
                    ]
                )

        self.assertIn("kpr-config.json", stderr.getvalue())


class AdapterTests(unittest.TestCase):
    def test_unknown_provider_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "지원하지 않는"):
            generate_text("질문", ProviderSettings("unknown", "model"))

    def test_windows_command_keeps_quoted_path_intact(self):
        command = '"C:\\Program Files\\Python\\python.exe" -c "print(1)"'
        self.assertEqual(command, prepare_command(command, platform="nt"))
        self.assertEqual(
            "C:\\Program Files\\Python\\python.exe",
            command_executable(command, platform="nt"),
        )

    def test_local_model_preserves_utf8_stdin_and_stdout(self):
        problem = validate_dataset([problem_record()])[0]
        output = generate_text(problem.prompt, local_settings())
        self.assertEqual(problem.prompt, output)

    def test_local_judge_preserves_utf8_stdin_and_stdout(self):
        rendered = "한글 Judge 입력"
        output = generate_text(
            rendered,
            local_settings(system_instruction="로컬 Judge 지시문"),
        )
        self.assertEqual(f"로컬 Judge 지시문\n\n{rendered}", output)

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
            text = generate_text("한글 문제", settings)

        self.assertEqual("API 답변", text)
        self.assertEqual("https://example.test/v1/chat/completions", captured["url"])
        self.assertEqual("Bearer secret-test-key", captured["authorization"])
        self.assertEqual("example-model", captured["body"]["model"])
        self.assertEqual("한글 문제", captured["body"]["messages"][0]["content"])

    def test_gemini_uses_the_same_call_for_judge_with_system_instruction(self):
        settings = ProviderSettings(
            "gemini",
            "example-model",
            api_key_env="TEST_KEY",
            system_instruction="설정에서 읽은 Judge 지시문",
        )
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                response = {"candidates": [{"content": {"parts": [
                    {"text": "평가"}, {"text": " 결과"}
                ]}}]}
                return json.dumps(response).encode("utf-8")

        def urlopen(request, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["url"] = request.full_url
            return FakeResponse()

        with patch.dict(os.environ, {"TEST_KEY": "fake-key"}), patch(
            "urllib.request.urlopen", side_effect=urlopen
        ):
            text = generate_text("문제와 답변", settings)
        self.assertEqual("평가 결과", text)
        self.assertTrue(captured["url"].endswith("example-model:generateContent"))
        self.assertEqual(
            "문제와 답변", captured["body"]["contents"][0]["parts"][0]["text"]
        )
        self.assertEqual(
            "설정에서 읽은 Judge 지시문",
            captured["body"]["systemInstruction"]["parts"][0]["text"],
        )

    def test_empty_gemini_response_is_rejected(self):
        for parts in ([], [{"text": ""}], [None]):
            with self.subTest(parts=parts), self.assertRaises(RuntimeError):
                extract_text({"candidates": [{"content": {"parts": parts}}]})

    def test_api_errors_do_not_expose_sensitive_details(self):
        settings = ProviderSettings("gemini", "example-model", api_key_env="TEST_KEY")
        errors = [
            urllib.error.HTTPError("https://example", 401, "sensitive", {}, None),
            urllib.error.URLError("sensitive"),
        ]
        for error in errors:
            with self.subTest(error=type(error).__name__), patch.dict(
                os.environ, {"TEST_KEY": "fake-key"}
            ), patch("urllib.request.urlopen", side_effect=error):
                with self.assertRaises(RuntimeError) as raised:
                    generate_text("질문", settings)
                self.assertNotIn("sensitive", str(raised.exception))
                self.assertNotIn("fake-key", str(raised.exception))


class PipelineTests(unittest.TestCase):
    def test_answer_uses_input_path_from_config(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            settings_path = base / "kpr-config.json"
            input_path = base / "problems.jsonl"
            input_path.write_text(
                json.dumps(problem_record(), ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            write_config(
                settings_path,
                RunConfig(
                    local_settings("test"),
                    ProviderSettings(
                        provider="local",
                        model_id="unused-judge",
                        command="missing-judge-command",
                    ),
                    input_path="problems.jsonl",
                    output_dir="saved-responses",
                ),
            )
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                main(["answer", "--settings", str(settings_path)])
            response_paths = list((base / "saved-responses").glob("*.jsonl"))
            saved_record = json.loads(
                response_paths[0].read_text(encoding="utf-8")
            )

        self.assertIn("[테스트 모델 답변]", stdout.getvalue())
        self.assertNotIn("[Judge 모델 답변]", stdout.getvalue())
        self.assertIn("테스트 모델 응답 저장:", stdout.getvalue())
        self.assertEqual(1, len(response_paths))
        self.assertEqual("problem-001", saved_record["id"])
        self.assertEqual(problem_record()["prompt"], saved_record["prompt"])
        self.assertEqual(
            problem_record()["prompt"], saved_record["test_model_response"]
        )

    def test_answer_requires_command_or_config_input_path(self):
        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "kpr-config.json"
            write_config(
                settings_path,
                RunConfig(local_settings("test"), local_settings("judge")),
            )
            stderr = io.StringIO()
            with redirect_stderr(stderr), self.assertRaises(SystemExit):
                main(["answer", "--settings", str(settings_path)])

        self.assertIn("input_path", stderr.getvalue())

    def test_answer_command_input_overrides_config_input_path(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            settings_path = base / "kpr-config.json"
            input_path = base / "problems.jsonl"
            input_path.write_text(
                json.dumps(problem_record(), ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            write_config(
                settings_path,
                RunConfig(
                    local_settings("test"),
                    local_settings("judge"),
                    input_path="missing.jsonl",
                ),
            )
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                main(["answer", str(input_path), "--settings", str(settings_path)])

        self.assertIn("[테스트 모델 답변]", stdout.getvalue())
        self.assertNotIn("[Judge 모델 답변]", stdout.getvalue())

    def test_failures_are_counted_and_later_problems_continue(self):
        problems = validate_dataset([problem_record("first"), problem_record("second")])
        config = RunConfig(local_settings("test"), local_settings("judge"))
        calls = []

        def generate(prompt, settings, **kwargs):
            calls.append(prompt)
            if "first" in prompt:
                raise RuntimeError("예상된 실패")
            return "답변"

        output = io.StringIO()
        response_output = io.StringIO()
        failures = generate_answers(
            problems,
            config.test_model,
            generate=generate,
            output=output,
            response_output=response_output,
        )
        self.assertEqual(1, failures)
        self.assertEqual(2, len(calls))
        self.assertIn("실패 1개", output.getvalue())
        saved_records = [
            json.loads(line) for line in response_output.getvalue().splitlines()
        ]
        self.assertEqual(["second"], [record["id"] for record in saved_records])

    def test_generate_answers_prints_and_saves_test_response(self):
        problems = validate_dataset([problem_record()])
        config = RunConfig(
            local_settings("test", "테스트 모델 지시문"),
            local_settings("judge", "Judge 모델 지시문"),
        )
        output = io.StringIO()
        response_output = io.StringIO()
        calls = []

        def generate(prompt, settings, **kwargs):
            calls.append((prompt, settings, kwargs))
            return "테스트 답변: problem-001"

        failures = generate_answers(
            problems,
            config.test_model,
            generate=generate,
            output=output,
            response_output=response_output,
        )

        printed = output.getvalue()
        self.assertIn("[테스트 모델 답변]", printed)
        self.assertIn("테스트 답변: problem-001", printed)
        self.assertNotIn("[Judge 모델 답변]", printed)
        self.assertEqual(0, failures)
        self.assertEqual(problems[0].prompt, calls[0][0])
        self.assertEqual(
            "테스트 모델 지시문", calls[0][2]["system_instruction"]
        )
        saved = json.loads(response_output.getvalue())
        self.assertEqual(problem_record()["prompt"], saved["prompt"])
        self.assertEqual("테스트 답변: problem-001", saved["test_model_response"])
        self.assertEqual(1, len(calls))

    def test_evaluate_answers_calls_only_judge_model(self):
        problem = validate_dataset([problem_record()])[0]
        responses = [SavedResponse(problem, "저장된 테스트 답변")]
        settings = local_settings("judge", "Judge 모델 지시문")
        calls = []

        def generate(prompt, received_settings, **kwargs):
            calls.append((prompt, received_settings, kwargs))
            return "Judge 평가 결과"

        output = io.StringIO()
        failures = evaluate_answers(
            responses,
            settings,
            output=output,
            generate=generate,
        )

        self.assertEqual(0, failures)
        self.assertEqual(1, len(calls))
        self.assertEqual("judge", calls[0][1].model_id)
        self.assertIn("저장된 테스트 답변", calls[0][0])
        self.assertEqual("Judge 모델 지시문", calls[0][2]["system_instruction"])
        self.assertIn("Judge 평가 결과", output.getvalue())

    def test_test_command_uses_most_recent_saved_answers(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            results = base / "results"
            results.mkdir()
            problem = validate_dataset([problem_record()])[0]
            older = results / "test-responses-older.jsonl"
            newer = results / "test-responses-newer.jsonl"
            older.write_text(
                json.dumps(
                    SavedResponse(problem, "오래된 답변").to_dict(),
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            newer.write_text(
                json.dumps(
                    SavedResponse(problem, "가장 최근 답변").to_dict(),
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            os.utime(older, ns=(1_000_000_000, 1_000_000_000))
            os.utime(newer, ns=(2_000_000_000, 2_000_000_000))
            settings_path = base / "kpr-config.json"
            write_config(
                settings_path,
                RunConfig(
                    ProviderSettings(
                        provider="local",
                        model_id="unused-test",
                        command="missing-test-command",
                    ),
                    local_settings("judge"),
                    output_dir="results",
                ),
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                main(["test", "--settings", str(settings_path)])

        printed = stdout.getvalue()
        self.assertIn(str(newer), printed)
        self.assertIn("가장 최근 답변", printed)
        self.assertNotIn("오래된 답변", printed)

    def test_test_command_requires_saved_answers(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            settings_path = base / "kpr-config.json"
            write_config(
                settings_path,
                RunConfig(
                    local_settings("test"),
                    local_settings("judge"),
                    output_dir="results",
                ),
            )
            stderr = io.StringIO()
            with redirect_stderr(stderr), self.assertRaises(SystemExit):
                main(["test", "--settings", str(settings_path)])

        self.assertIn("answer 명령을 먼저 실행", stderr.getvalue())

    def test_saved_response_file_round_trip(self):
        problem = validate_dataset([problem_record()])[0]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test-responses-example.jsonl"
            path.write_text(
                json.dumps(
                    SavedResponse(problem, "원본 답변").to_dict(),
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            loaded = load_saved_responses(path)

        self.assertEqual(problem, loaded[0].problem)
        self.assertEqual("원본 답변", loaded[0].test_model_response)

    def test_cli_exits_with_error_when_a_model_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            settings_path = base / "config.json"
            input_path = base / "problems.jsonl"
            input_path.write_text(
                json.dumps(problem_record(), ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            failing_command = f'"{sys.executable}" -c "raise SystemExit(1)"'
            write_config(
                settings_path,
                RunConfig(
                    ProviderSettings(
                        provider="local",
                        model_id="failing-test",
                        command=failing_command,
                    ),
                    local_settings("judge"),
                ),
            )
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr), self.assertRaises(
                SystemExit
            ) as raised:
                main(["answer", str(input_path), "--settings", str(settings_path)])

        self.assertEqual(2, raised.exception.code)
        self.assertIn(
            "1개 문제에서 답변 생성이 실패했습니다",
            stderr.getvalue(),
        )


class BootstrapTests(unittest.TestCase):
    def test_venv_python_is_platform_specific(self):
        bootstrap = load_bootstrap_module()
        root = Path("project")
        self.assertEqual(
            root / ".venv" / "Scripts" / "python.exe",
            bootstrap.venv_python(root, platform="nt"),
        )
        self.assertEqual(
            root / ".venv" / "bin" / "python",
            bootstrap.venv_python(root, platform="posix"),
        )

    def test_project_fingerprint_changes_with_source(self):
        bootstrap = load_bootstrap_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "src" / "example"
            source.mkdir(parents=True)
            (root / "pyproject.toml").write_text("version = '1'\n", encoding="utf-8")
            module = source / "module.py"
            module.write_text("VALUE = 1\n", encoding="utf-8")
            first = bootstrap.project_fingerprint(root)
            module.write_text("VALUE = 2\n", encoding="utf-8")
            second = bootstrap.project_fingerprint(root)

        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()

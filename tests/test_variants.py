"""조사·생략 변형기와 `kpr variants` 명령을 검증합니다."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from korean_prompt_robustness.cli import main
from korean_prompt_robustness.dataset import load_and_validate_dataset
from korean_prompt_robustness.variants import FAMILIES, export
from korean_prompt_robustness.variants.deixis_drop import drop_deixis
from korean_prompt_robustness.variants.export import (
    candidates,
    edit_operations,
    protected_spans,
)
from korean_prompt_robustness.variants.josa_omit import omit_josa
from korean_prompt_robustness.variants.josa_swap import swap_josa
from korean_prompt_robustness.variants.subject_drop import drop_subjects

PROMPT = (
    "다음 문제를 푸는 것을 도와주세요. 직관적이고 이해하기 쉬운 해결책을 단계별로 "
    "제공해주세요:\n\n크기가 각각 m과 n인 두 정렬된 배열의 중앙값을 반환하세요.\n\n"
)
ORIGINAL = {
    "id": "math-001-original",
    "prompt": PROMPT,
    "metadata": {"category": "math_reasoning", "base_id": "math-001", "variant_type": "original"},
}
FAMILY = {family.variant_type: family for family in FAMILIES}


class TransformTests(unittest.TestCase):
    def test_josa_omit(self):
        cases = [
            ("나는 밥을 먹었다.", "나는 밥 먹었다."),       # 는(JX)은 기본 대상이 아님
            ("내가 그것을 했다.", "나 그것 했다."),         # 내가 -> 나
            ("날 좀 봐줘.", "나 좀 봐줘."),                 # 축약 목적격
            ("철수가 영희를 좋아한다.", "철수 영희 좋아한다."),
            ("AI가 세상을 바꾼다.", "AI 세상 바꾼다."),
            ("그는 학생이다.", "그는 학생이다."),           # 서술격 이다
            ("물이 얼음이 되었다.", "물 얼음이 되었다."),   # 보격 유지
            ("이 옷이 좋다.", "이 옷 좋다."),               # 관형사 이
        ]
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(omit_josa(source), expected)

    def test_josa_swap(self):
        self.assertEqual(
            swap_josa("철수에게 사과처럼 생긴 걸 줬다."), "철수한테 사과같이 생긴 걸 줬다."
        )
        self.assertEqual(swap_josa("동생과 놀았다."), "동생이랑 놀았다.")
        self.assertEqual(swap_josa("철수와 놀았다."), "철수랑 놀았다.")  # 받침에 맞춤
        self.assertEqual(swap_josa("우리 같이 가자."), "우리 같이 가자.")  # 부사 같이
        self.assertEqual(swap_josa("먹을 만큼 담아라."), "먹을 만큼 담아라.")  # 의존명사

    def test_subject_drop(self):
        self.assertEqual(
            drop_subjects("철수가 학교에 갔다. 철수가 밥을 먹었다."),
            "철수가 학교에 갔다. 밥을 먹었다.",
        )
        self.assertEqual(drop_subjects("나는 갔다. 난 웃었다."), "나는 갔다. 웃었다.")
        self.assertEqual(drop_subjects("철수가 밥을 먹었다."), "철수가 밥을 먹었다.")
        self.assertEqual(  # 꾸미는 말이 남으면 어색하므로 건너뜀
            drop_subjects("책을 봤다. 두꺼운 책이 좋다."), "책을 봤다. 두꺼운 책이 좋다."
        )

    def test_deixis_drop(self):
        self.assertEqual(drop_deixis("그 책을 읽었다."), "책을 읽었다.")
        self.assertEqual(drop_deixis("그것을 봤다."), "봤다.")
        self.assertEqual(drop_deixis("그렇게 말했다."), "말했다.")
        self.assertEqual(drop_deixis("그때 일이 있었다."), "그때 일이 있었다.")
        self.assertEqual(drop_deixis("저는 학생입니다."), "저는 학생입니다.")


class ExportTests(unittest.TestCase):
    def test_original_kept_first(self):
        records = export([ORIGINAL], mixed=0)
        first = records[0]
        self.assertEqual(first["id"], "math-001-original")
        self.assertEqual(first["prompt"], PROMPT)
        self.assertEqual(first["metadata"]["track"], "baseline")
        self.assertEqual(first["metadata"]["category"], "math_reasoning")

    def test_bare_original_gets_base_id(self):
        records = export([{"id": "q-7", "prompt": "책을 읽고 철수에게 주세요."}], mixed=0)
        self.assertEqual(records[0]["metadata"]["base_id"], "q-7")
        self.assertIn("q-7-particle-01", [record["id"] for record in records])

    def test_particle_variant_metadata(self):
        records = [r for r in export([ORIGINAL], types=("particle",), mixed=0)[1:]]
        self.assertEqual(len(records), 3)
        self.assertEqual(
            [r["id"] for r in records],
            ["math-001-particle-01", "math-001-particle-02", "math-001-particle-03"],
        )
        for record in records:
            metadata = record["metadata"]
            self.assertEqual(metadata["variant_type"], "particle")
            self.assertEqual(metadata["variant_label"], "조사·주제화")
            self.assertEqual(metadata["track"], "controlled_operator")
            self.assertEqual(metadata["semantic_preservation"], "pending_human_review")
            self.assertTrue(metadata["synthetic"])
            self.assertFalse(metadata["human_validated"])
            self.assertEqual(len(metadata["edit_operations"]), 1)
            self.assertNotEqual(record["prompt"], PROMPT)
        self.assertEqual(len({r["prompt"] for r in records}), 3)

    def test_omission_deletes_whole_word(self):
        text = "철수가 학교에 갔다. 철수가 밥을 먹었다."
        found = candidates(text, FAMILY["omission"])
        operations = edit_operations(text, found[:1], with_family=False)
        self.assertEqual((operations[0]["before"], operations[0]["after"]), ("철수가 ", ""))

    def test_mixed_combines_families(self):
        text = "그 사람이 철수에게 책을 줬다. 그 사람이 웃었다."
        records = [r for r in export([{"id": "x", "prompt": text}], mixed=3) if "-mixed-" in r["id"]]
        self.assertTrue(records)
        for record in records:
            metadata = record["metadata"]
            self.assertEqual(metadata["track"], "synthetic_naturalistic")
            self.assertNotIn("variant_label", metadata)
            families = {operation["family"] for operation in metadata["edit_operations"]}
            self.assertEqual(families, {"particle", "omission"})

    def test_same_seed_same_output(self):
        self.assertEqual(export([ORIGINAL], seed=5), export([ORIGINAL], seed=5))

    def test_keep_existing_continues_numbering(self):
        old = {
            "id": "math-001-particle-01",
            "prompt": "사람이 만든 변형",
            "metadata": {"base_id": "math-001", "variant_type": "particle", "realization": 1},
        }
        merged = export([ORIGINAL, old], types=("particle",), mixed=0, keep_existing=True)
        self.assertEqual(
            [r["id"] for r in merged[:3]],
            ["math-001-original", "math-001-particle-01", "math-001-particle-02"],
        )
        fresh = export([ORIGINAL, old], types=("particle",), mixed=0)
        self.assertNotIn("사람이 만든 변형", [r["prompt"] for r in fresh])
        self.assertEqual(fresh[1]["id"], "math-001-particle-01")

    def test_code_is_not_touched(self):
        text = "다음 코드를 고쳐 주세요.\n```python\n# 밥을 먹었다\nprint('철수가 왔다')\n```\n"
        spans = protected_spans(text)
        for family in FAMILIES:
            for candidate in candidates(text, family):
                for edit in candidate.edits:
                    self.assertFalse(any(start <= edit.start < end for start, end in spans))

    def test_unknown_type(self):
        with self.assertRaises(ValueError):
            export([ORIGINAL], types=("typo",))


class VariantsCommandTests(unittest.TestCase):
    def test_writes_dataset_answer_can_read(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "problems.jsonl"
            input_path.write_text(json.dumps(ORIGINAL, ensure_ascii=False) + "\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()) as output:
                main(["variants", str(input_path)])
            output_path = Path(directory) / "problems-variants.jsonl"
            self.assertIn(str(output_path), output.getvalue())
            problems = load_and_validate_dataset(output_path)
            self.assertEqual(problems[0].id, "math-001-original")
            self.assertTrue(any(p.metadata["variant_type"] == "particle" for p in problems))

    def test_refuses_to_overwrite_without_force(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "problems.jsonl"
            input_path.write_text(json.dumps(ORIGINAL, ensure_ascii=False) + "\n", encoding="utf-8")
            output_path = Path(directory) / "out.jsonl"
            output_path.write_text("keep\n", encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["variants", str(input_path), "-o", str(output_path)])
            self.assertEqual(output_path.read_text(encoding="utf-8"), "keep\n")
            with contextlib.redirect_stdout(io.StringIO()):
                main(["variants", str(input_path), "-o", str(output_path), "--force"])
            self.assertNotEqual(output_path.read_text(encoding="utf-8"), "keep\n")


if __name__ == "__main__":
    unittest.main()

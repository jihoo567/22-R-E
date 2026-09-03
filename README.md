# 한국어 프롬프트 강건성 최소 벤치마크

연구자가 **이미 만든** 원본 KITE 문제와 문법 변형 문제를 동일한 조건으로 실행하고, 규칙 및 선택한 Judge로 채점한 뒤 `parent_id`로 비교합니다. 이 프로젝트는 변형 문제를 만들거나 입력 프롬프트를 고치는 기능을 포함하지 않습니다.

## 1. 설치

Python 3.10 이상만 필요합니다. 외부 Python 패키지와 웹 서버, 데이터베이스는 사용하지 않습니다.

```bash
cd korean_prompt_robustness
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Windows 연구컴에서는 배포 ZIP을 푼 뒤 `install_windows.bat`을 더블클릭하세요. 자세한 내용은 `WINDOWS_INSTALL.md`에 있습니다.

실제 Gemini 호출 때만 키가 필요합니다. `.env.example`을 `.env`로 복사하거나 셸 환경변수로 설정하세요. `.env`는 Git에서 제외되며 키는 결과나 로그에 저장하지 않습니다.

```text
GEMINI_API_KEY=발급받은-키
```

## 2. 입력 JSONL

각 줄은 `id`, `parent_id`, `variant_type`, `prompt`, `reference_answer`, `evaluation_rules`, `metadata`를 가진 JSON 객체입니다. 한 `parent_id`에는 `variant_type`이 `original`인 항목이 정확히 하나 있어야 합니다. 변형들은 같은 `parent_id`를 사용합니다.

```json
{"id":"kite-001-original","parent_id":"kite-001","variant_type":"original","prompt":"원본 KITE 문제","reference_answer":null,"evaluation_rules":[{"rule_id":"rule-1","type":"must_include","value":"필수 표현"}],"metadata":{"category":"honorific","source":"KITE"}}
```

```json
{"id":"kite-001-variant-01","parent_id":"kite-001","variant_type":"particle_omission","prompt":"연구자가 준비한 변형 문제","reference_answer":null,"evaluation_rules":[],"metadata":{"category":"honorific","source":"researcher"}}
```

프레임워크는 이 값을 읽고 검증할 뿐 새 변형을 만들거나 입력을 수정하지 않습니다.

## 3. 빠른 Mock 실행

```bash
kpr validate --input data/examples/kite_pairs.jsonl
kpr run-all \
  --input data/examples/kite_pairs.jsonl \
  --config configs/mock.json \
  --run-id mock-demo
```

각 단계도 따로 실행할 수 있습니다.

```bash
# 1) 모델 응답 생성(같은 run-id 재실행 시 완료 요청 건너뜀)
kpr generate --input data/examples/kite_pairs.jsonl --config configs/mock.json \
  --run-id step-demo

# 2) 저장 응답 규칙 재채점
kpr score-rules --input data/examples/kite_pairs.jsonl \
  --responses results/responses/step-demo.jsonl --config configs/mock.json \
  --run-id rescore-v2 --output results/scores/rescore-v2.rules.jsonl

# 3) 저장 응답 Judge 재평가
kpr score-judge --input data/examples/kite_pairs.jsonl \
  --responses results/responses/step-demo.jsonl --config configs/mock.json \
  --run-id rejudge-v2 --output results/judgments/rejudge-v2.jsonl \
  --cache results/judgments/cache.jsonl

# 4) 최종 점수와 강건성 지표
kpr metrics --input data/examples/kite_pairs.jsonl \
  --responses results/responses/step-demo.jsonl \
  --rule-scores results/scores/rescore-v2.rules.jsonl \
  --judgments results/judgments/rejudge-v2.jsonl --config configs/mock.json \
  --run-id analysis-v2 --final-output results/scores/analysis-v2.final.jsonl \
  --pairs-output results/scores/analysis-v2.comparisons.jsonl \
  --summary-output results/scores/analysis-v2.metrics.json

# 5) CSV 보고서만 다시 생성
kpr report --scores results/scores/analysis-v2.final.jsonl \
  --comparisons results/scores/analysis-v2.comparisons.jsonl \
  --summary results/scores/analysis-v2.metrics.json \
  --output-dir results/reports/analysis-v2
```

실제 Gemini는 설정만 바꿉니다. 테스트 대상 모델과 Judge는 완전히 분리된 설정을 사용합니다.

```bash
kpr run-all --input /path/to/researcher-data.jsonl \
  --config configs/gemini.json --run-id gemini-kite-v1
```

### 테스트 모델과 Judge 모델 선택

`test_model`은 벤치마크 문제에 답하는 평가 대상이고 `judge_model`은 저장된 답변을 채점합니다. 두 역할은 서로 독립적으로 `gemini` API 또는 `local`을 선택할 수 있습니다. 테스트 대상에는 개발 확인용 `mock`도 사용할 수 있습니다. Mock Judge는 `configs/mock.json`처럼 `allow_mock_judge: true`를 둔 자동 테스트 구성에서만 허용됩니다.

Gemini를 테스트하고 Gemini API로 채점하려면:

```bash
kpr run-all --input data/examples/kite_pairs.jsonl \
  --config configs/gemini.json --run-id gemini-test-api-judge
```

이때 설정의 역할은 다음처럼 분리됩니다.

```json
{
  "test_model": {
    "provider": "gemini",
    "model_id": "gemini-3.6-flash"
  },
  "judge_model": {
    "provider": "gemini",
    "model_id": "gemini-3.6-flash",
    "prompt_version": "judge-ko-v1"
  }
}
```

로컬 LLM을 테스트하고 Gemini API로 채점하려면 Ollama를 실행한 뒤 제공된 설정을 사용합니다.

```bash
ollama pull gemma3:4b
kpr run-all --input data/examples/kite_pairs.jsonl \
  --config configs/local_test_gemini_judge.json \
  --run-id local-gemma3-api-judge
```

테스트 모델과 Judge를 모두 로컬로 실행하려면 다음과 같이 실행합니다. 예제 설정은 테스트 모델에 `gemma3:4b`, Judge에 `qwen3:8b`를 사용하므로 두 모델을 먼저 준비합니다.

```bash
ollama pull gemma3:4b
ollama pull qwen3:8b
kpr run-all --input data/examples/kite_pairs.jsonl \
  --config configs/local_test_local_judge.json \
  --run-id local-test-local-judge
```

로컬 어댑터는 프롬프트를 설정의 `command` 표준 입력으로 전달합니다. 테스트 모델의 stdout은 원문 그대로 저장됩니다. 로컬 Judge의 stdout은 반드시 Judge 프롬프트에 명시된 JSON 객체여야 하며, 공통 스키마 검증에 실패하면 제한된 횟수만큼 다시 실행됩니다. 다른 Ollama 모델이나 로컬 실행기를 쓰려면 각 역할의 `model_id`와 `command`를 독립적으로 변경하세요. 로컬 Judge만 사용할 때는 `GEMINI_API_KEY`가 필요하지 않습니다.

## 4. 채점

규칙 채점기는 `must_include`, `must_exclude`, `line_count`, `sentence_count`, `line_starts`, `regex`, `custom_python`을 지원합니다. `custom_python` 값은 신뢰할 수 있는 `module:function`이어야 하며 함수는 `(response, context)`를 받아 `bool`, `{"status": ..., "reason": ...}` 또는 `None`을 반환합니다. 신뢰하지 않는 데이터의 Python 경로를 실행하지 마세요.

각 하위 결과는 `pass=1`, `fail=0`, `indeterminate`, `error` 중 하나입니다. 점수는 `pass 수 / (pass+fail 수) × 100`이며 판정 불가와 오류는 분모에서 제외되고 별도 개수로 저장됩니다.

- `rule_only`: 규칙 점수만 사용
- `judge_only`: Judge 구조화 점수만 사용
- `hybrid`: 둘의 성공 여부가 일치할 때 평균, 충돌하거나 한쪽 점수가 없으면 최종 점수를 임의 선택하지 않고 사람 검토로 표시

Judge 프롬프트에는 대상 모델 이름을 넣지 않습니다. 프롬프트, 원응답, 참고 답안, 전체 rubric, 범주, 변형 유형을 전달하고 `verdict`, `score`, `criteria`를 검증합니다. 이유 문장은 감사용으로 저장하지만 계산은 `verdict`와 `score`를 사용합니다. 잘못된 JSON도 설정된 횟수만큼 재시도합니다.

## 5. 강건성 지표와 결과

조건이 같은 원본·변형 쌍에 대해 점수 차이(`변형-원본`), 하락 폭, 동시 성공률, 원본 성공/변형 실패율, 성공 일관성, parent별 최저 변형 점수를 계산합니다. 강건 정확도는 **원본과 해당 parent의 모든 비교 가능한 변형이 통과한 parent 비율**입니다. 변형 유형·문제 범주별 평균 점수와 평균 하락 폭도 제공합니다.

데이터셋 버전, 생성 모델/설정, 채점 방식, 채점기 버전, Judge 모델/설정/프롬프트 버전 중 하나라도 다르면 해당 쌍을 제외하고 이유를 `comparisons.jsonl`에 기록합니다.

- `results/responses/`: 원응답과 생성 재시도, 공유 캐시
- `results/judgments/`: Judge 원문·구조화 결과·재시도·공유 캐시
- `results/scores/`: 규칙/최종/쌍 비교 JSONL과 지표 JSON
- `results/reports/<run-id>/`: 문제 상세, 쌍 비교, 모델·변형 유형·범주 요약, 충돌, 사람 검토 CSV

응답 파일은 append-only입니다. 같은 실행을 이어서 실행하면 완료 fingerprint를 건너뛰고, 새 실행에서도 공개 설정과 입력이 완전히 같은 경우 캐시를 사용합니다. 저장 응답은 모델 호출 없이 여러 채점기 버전/run-id로 재채점할 수 있습니다.

## 6. 새 어댑터 연결 위치

- 테스트 대상 모델: `src/korean_prompt_robustness/models/base.py`의 `ModelAdapter` 구현 후 `models/factory.py`에 등록
- 로컬 테스트 모델: `models/local.py`의 stdin/stdout 명령 어댑터와 `test_model.command`
- Gemini 테스트 모델: `models/gemini.py`의 `GeminiModel`
- Judge 공통 인터페이스: `judges/base.py`의 `JudgeAdapter`
- 로컬 Judge: `judges/local.py`의 stdin/stdout 명령 어댑터와 `judge_model.command`
- 새 API Judge: `JudgeAdapter` 구현 후 `judges/factory.py`와 provider 허용 목록에 등록
- Gemini Judge와 JSON schema: `judges/gemini.py`, `judges/prompt.py`

## 7. 테스트

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

# KPR 설정 안내

KPR은 프로젝트 루트의 `kpr-config.json`을 읽습니다. 처음 실행할 때
`kpr-config.example.json`이 이 이름으로 자동 복사됩니다. JSON은 주석을
지원하지 않으므로 변수 설명과 복사용 예시는 이 문서에 정리합니다.

- `test_model`: 문제에 답하는 모델
- `judge_model`: 문제와 테스트 모델 답변을 검토하는 모델
- `input_path`: `run`에서 사용할 문제 JSONL 경로
- `.env`: API 키 저장 파일. 실제 키를 JSON에 직접 쓰지 않습니다.

## 변수 설명

| 변수 | 설명 |
| --- | --- |
| `input_path` | 문제 JSONL 경로입니다. 상대 경로는 `kpr-config.json`이 있는 폴더를 기준으로 합니다. 명령행에 경로를 쓰면 명령행 값이 우선합니다. |
| `provider` | `local`, `gemini`, `openai-compatible` 중 하나입니다. |
| `model_id` | 호출할 모델 이름입니다. 로컬에서는 `command`의 모델 이름과 맞춥니다. |
| `command` | 로컬 모델 실행 명령입니다. API 모델에서는 `null`입니다. |
| `base_url` | OpenAI 호환 API의 기본 주소입니다. 그 외에는 `null`입니다. |
| `api_key_env` | 키 값이 아니라 `.env`에서 키를 찾을 환경변수 이름입니다. 로컬에서는 `null`입니다. |
| `system_instruction` | 해당 모델에 항상 전달할 지시문입니다. 사용하지 않으려면 `null`입니다. |
| `temperature` | API 생성 무작위성입니다. Judge에는 보통 `0.0`을 사용합니다. |
| `seed` | API가 지원하는 경우 사용할 선택적 정수 seed입니다. |
| `max_tokens` | API가 한 번에 생성할 최대 토큰 수입니다. |
| `timeout_seconds` | 모델 호출 한 번의 제한 시간(초)입니다. |

`system_instruction`은 API 모델에서는 별도의 system instruction으로 전달됩니다.
Ollama 같은 로컬 명령은 system 채널이 없으므로 프로그램이 다음처럼 하나의
UTF-8 입력으로 합칩니다.

```text
system_instruction

문제 또는 Judge 입력
```

테스트 모델 지시문과 Judge 지시문은 서로 독립적으로 지정할 수 있습니다.

## 예시 1: 테스트와 Judge 모두 로컬

```json
{
  "input_path": "data/examples/problems.jsonl",
  "test_model": {
    "provider": "local",
    "model_id": "qwen2.5:14b",
    "command": "ollama run qwen2.5:14b",
    "base_url": null,
    "api_key_env": null,
    "system_instruction": "문제의 요구사항을 정확히 지켜 한국어로 답하세요.",
    "temperature": 0.0,
    "seed": null,
    "max_tokens": 1024,
    "timeout_seconds": 300.0
  },
  "judge_model": {
    "provider": "local",
    "model_id": "qwen2.5:14b",
    "command": "ollama run qwen2.5:14b",
    "base_url": null,
    "api_key_env": null,
    "system_instruction": "당신은 테스트 모델의 답변을 검토하는 독립 평가자입니다.",
    "temperature": 0.0,
    "seed": null,
    "max_tokens": 1024,
    "timeout_seconds": 300.0
  }
}
```

## 예시 2: 로컬 테스트 모델과 Gemini Judge

```json
{
  "input_path": "data/examples/problems.jsonl",
  "test_model": {
    "provider": "local",
    "model_id": "llama3.2:1b",
    "command": "ollama run llama3.2:1b",
    "base_url": null,
    "api_key_env": null,
    "system_instruction": "질문에 간결하게 답하세요.",
    "temperature": 0.0,
    "seed": null,
    "max_tokens": 1024,
    "timeout_seconds": 300.0
  },
  "judge_model": {
    "provider": "gemini",
    "model_id": "gemini-3.6-flash",
    "command": null,
    "base_url": null,
    "api_key_env": "KPR_JUDGE_API_KEY",
    "system_instruction": "문제와 답변을 비교하여 정확성과 지시 준수 여부를 평가하세요.",
    "temperature": 0.0,
    "seed": null,
    "max_tokens": 1024,
    "timeout_seconds": 120.0
  }
}
```

`.env`에는 실제 Gemini 키를 저장합니다.

```dotenv
KPR_JUDGE_API_KEY=여기에_실제_Gemini_API_키
```

Gemini를 테스트 모델로 사용할 때는 `test_model`에도 같은 형식을 사용하고
`api_key_env`를 `KPR_TEST_API_KEY`로 지정합니다. 두 역할이 같은 키를 공유하면
`.env`의 `GEMINI_API_KEY`를 공용으로 사용할 수도 있습니다.

## 예시 3: OpenAI 호환 API 모델

다음 객체를 `test_model` 또는 `judge_model` 자리에 넣고 모델 ID와 주소를
제공업체가 안내한 값으로 바꿉니다.

```json
{
  "provider": "openai-compatible",
  "model_id": "실제-모델-ID",
  "command": null,
  "base_url": "https://제공업체.example/v1",
  "api_key_env": "KPR_JUDGE_API_KEY",
  "system_instruction": "문제와 답변을 객관적으로 검토하세요.",
  "temperature": 0.0,
  "seed": null,
  "max_tokens": 1024,
  "timeout_seconds": 120.0
}
```

Judge 용도라면 `.env`에 다음처럼 저장합니다.

```dotenv
KPR_JUDGE_API_KEY=여기에_실제_API_키
```

테스트 모델 용도라면 `KPR_TEST_API_KEY`를 사용합니다. 두 역할이 같은 키를
공유하면 `.env`의 `OPENAI_API_KEY`를 공용으로 사용할 수도 있습니다.

## 설정 확인과 실행

macOS/Linux:

```bash
./kpr show-config
./kpr run --limit 1
```

Windows:

```bat
kpr.bat show-config
kpr.bat run --limit 1
```

설정과 다른 파일을 한 번만 실행하려면 경로를 직접 입력합니다.

```bash
./kpr run data/examples/other-problems.jsonl --limit 1
```

# 최소 LLM 벤치마크

이 프로그램은 준비된 문제를 테스트 모델에 보내고, 테스트 모델의 답변을
Judge 모델에 전달한 뒤 두 모델의 원문 답변을 콘솔에 출력하는 최소
벤치마크 뼈대입니다.

```text
문제 JSONL
  → 테스트 모델
  → 테스트 모델 답변
  → Judge 모델
  → Judge 모델 답변
  → 콘솔 출력
```

다음 기능은 포함하지 않습니다.

- 문제 또는 변형 프롬프트 생성
- 정답 및 별도 채점 기준
- 규칙 기반 채점과 점수 계산
- 지표 및 CSV 보고서
- Mock 모델
- 모델 답변 및 Judge 답변 파일 저장

## 1. 설치

### Windows

[GitHub Releases](https://github.com/jihoo567/22-R-E/releases/latest)에서 최신
Windows ZIP을 받은 뒤 압축을 완전히 풀고 `install_windows.bat`을
실행합니다. 설치 후의 모델 설정과 실행 방법은 `WINDOWS_INSTALL.md`에
자세히 설명되어 있습니다.

Git으로 받은 경우에도 저장소 폴더에서 `install_windows.bat`을 실행하면
됩니다.

### macOS 또는 Linux

프로젝트 폴더에서 가상환경을 만들고 프로그램을 설치합니다.

```bash
cd 22-R-E
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

이미 설치했다면 다음 실행부터는 프로젝트 폴더로 이동해 가상환경만
활성화하면 됩니다.

```bash
cd 22-R-E
source .venv/bin/activate
```

명령어가 설치됐는지 확인합니다.

```bash
kpr --help
```

## 2. 문제 데이터 준비

입력은 UTF-8 JSONL 파일입니다. JSONL에서는 한 줄이 문제 하나입니다.
각 줄에는 `id`와 `prompt`가 반드시 있어야 합니다. `metadata`는 선택
사항이며, 그 밖의 필드는 읽더라도 문제나 답변 생성에 사용하지 않습니다.

```json
{"id":"problem-001","prompt":"대한민국의 수도는 어디인가요?","metadata":{"category":"knowledge"}}
{"id":"problem-002","prompt":"물의 화학식을 간단히 설명하세요.","metadata":{"category":"science"}}
```

주의 사항:

- 각 문제는 한 줄에 작성합니다.
- `id`는 중복되면 안 됩니다.
- 파일 인코딩은 UTF-8이어야 합니다.
- 프로그램은 입력된 `prompt`를 수정하지 않습니다.

예제 5문제는 `data/examples/problems.jsonl`에 있습니다. 실행 전에 형식을
검증할 수 있습니다.

```bash
kpr validate data/examples/problems.jsonl
```

정상이면 다음과 같이 출력됩니다.

```text
검증 성공: 5개 문제
```

## 3. 지원하는 모델 연결 방식

테스트 모델과 Judge 모델은 각각 다음 세 방식 중 하나를 독립적으로 선택할
수 있습니다.

| 설정값 | 용도 | 추가로 필요한 정보 |
|---|---|---|
| `local` | Ollama 등의 로컬 LLM | 모델 ID 또는 실행 명령 |
| `gemini` | Google Gemini API | Gemini API 키 |
| `openai-compatible` | OpenAI 호환 Chat Completions API | API 키, 모델 ID, Base URL |

### 3.1 `local`

`local`은 프롬프트를 로컬 명령의 표준 입력(stdin)으로 전달하고, 표준
출력(stdout)을 모델 답변으로 사용합니다.

모델 ID를 생략하면 다음 기본값을 사용합니다.

```text
모델 ID: qwen2.5:14b
실행 명령: ollama run qwen2.5:14b
```

따라서 컴퓨터에 Ollama와 `qwen2.5:14b`가 설치되어 있다면 별도 실행
명령을 입력할 필요가 없습니다.

```bash
ollama list
```

Ollama가 아닌 로컬 실행기를 사용할 때는 해당 프로그램이 UTF-8 프롬프트를
stdin으로 받고 답변을 stdout으로 출력해야 합니다.

### 3.2 `gemini`

`gemini`는 Gemini 전용 REST API 형식으로 요청합니다. 모델 ID를 생략하면
`gemini-3.6-flash`를 사용합니다. `gemini-3.7-flash`를 사용하려면
`--test-model` 또는 `--judge-model`로 명시합니다.

Gemini는 API 서버 주소가 정해져 있으므로 사용자가 Base URL을 입력할
필요가 없습니다.

### 3.3 `openai-compatible`

`openai-compatible`은 OpenAI 호환 Chat Completions 형식을 사용하는 API에
연결합니다. 프로그램은 다음 형식으로 요청합니다.

```text
POST <Base URL>/chat/completions
Authorization: Bearer <API key>
Content-Type: application/json
```

요청 본문에는 `model`, `messages`, `temperature`, `max_tokens`가 들어갑니다.
응답은 일반적인 `choices[0].message.content` 형식이어야 합니다.

## 4. OpenAI 호환 방식이 더 복잡한 이유

`openai-compatible`은 특정 회사 하나의 이름이 아니라 여러 API 제공업체가
공유하는 요청 형식을 뜻합니다. API 키만 보고는 다음 내용을 알아낼 수
없습니다.

1. 어느 회사의 서버로 요청해야 하는지
2. 그 회사에서 어떤 모델 ID를 제공하는지
3. 해당 API의 Base URL이 무엇인지

따라서 OpenAI 호환 방식에는 다음 세 값이 필요합니다.

```text
API 키 + 모델 ID + Base URL
```

공식 OpenAI API를 사용하는 경우 Base URL 예시는 다음과 같습니다.

```text
https://api.openai.com/v1
```

다른 제공업체를 사용하는 경우 그 제공업체 문서에 나온 OpenAI 호환 Base
URL과 모델 ID를 입력해야 합니다. 프로그램에는 다음 중 어느 형태를 넣어도
됩니다.

```text
https://제공업체.example/v1
https://제공업체.example/v1/chat/completions
```

첫 번째 형태를 입력하면 프로그램이 `/chat/completions`를 자동으로
붙입니다. 두 번째처럼 전체 주소를 입력하면 그대로 사용합니다.

이름에 OpenAI가 들어가더라도 모든 AI API가 호환되는 것은 아닙니다. 다음
조건을 만족하는 서비스만 연결할 수 있습니다.

- Bearer API 키 인증을 지원해야 합니다.
- `POST /chat/completions` 요청을 지원해야 합니다.
- 요청의 `messages` 형식을 지원해야 합니다.
- 응답에 `choices[0].message.content`가 있어야 합니다.

OAuth, 클라우드 서명 인증, 완전히 다른 요청 형식을 사용하는 API는 별도
어댑터 없이는 연결할 수 없습니다.

## 5. 반드시 먼저 모델 설정하기

`run` 전에 `configure`를 한 번 실행해야 합니다. 설정하지 않고 실행하면
모델을 호출하지 않고 중단됩니다.

```text
사전 설정이 없습니다. 먼저 'kpr configure' 명령을 실행하세요.
```

설정은 `.kpr/config.json`에 저장됩니다. `configure`를 다시 실행하면 이전
모델 설정을 새 설정으로 교체합니다.

현재 설정 확인:

```bash
kpr show-config
```

API 키 값은 이 설정 파일에 저장되지 않습니다. 설정 파일에는 어떤
환경변수에서 키를 읽을지만 기록됩니다.

## 6. 모델 조합별 설정 예시

### 6.1 로컬 Qwen 테스트 / Gemini Judge

가장 간단하게 사용할 수 있는 조합입니다.

```bash
kpr configure --test local --judge gemini
```

명시적으로 모델 ID를 지정하려면 다음과 같이 실행합니다.

```bash
kpr configure \
  --test local --test-model qwen2.5:14b \
  --judge gemini --judge-model gemini-3.6-flash
```

### 6.2 테스트와 Judge 모두 Gemini

```bash
kpr configure --test gemini --judge gemini
```

테스트는 3.6, Judge는 3.7을 사용하려면 다음처럼 지정합니다.

```bash
kpr configure \
  --test gemini --test-model gemini-3.6-flash \
  --judge gemini --judge-model gemini-3.7-flash
```

### 6.3 테스트와 Judge 모두 로컬 Qwen

```bash
kpr configure --test local --judge local
```

이 경우 Ollama가 순차적으로 두 번 호출됩니다. 첫 번째 호출은 문제 답변을
생성하고, 두 번째 호출은 문제와 첫 번째 답변을 전달받아 검토합니다.

### 6.4 로컬 테스트 / OpenAI 호환 Judge

```bash
kpr configure \
  --test local \
  --test-model qwen2.5:14b \
  --judge openai-compatible \
  --judge-model 사용할-Judge-모델-ID \
  --judge-base-url https://제공업체.example/v1
```

### 6.5 OpenAI 호환 테스트 / Gemini Judge

```bash
kpr configure \
  --test openai-compatible \
  --test-model 사용할-테스트-모델-ID \
  --test-base-url https://제공업체.example/v1 \
  --judge gemini
```

### 6.6 테스트와 Judge 모두 OpenAI 호환 API

같은 서비스와 같은 키를 사용해도 되고, 서로 다른 서비스와 키를 사용해도
됩니다.

```bash
kpr configure \
  --test openai-compatible \
  --test-model 테스트-모델-ID \
  --test-base-url https://테스트-제공업체.example/v1 \
  --judge openai-compatible \
  --judge-model Judge-모델-ID \
  --judge-base-url https://Judge-제공업체.example/v1
```

### 6.7 Ollama 이외의 로컬 실행기

```bash
kpr configure \
  --test local \
  --test-model my-local-model \
  --test-command "테스트-모델-실행-명령" \
  --judge local \
  --judge-model my-local-judge \
  --judge-command "Judge-모델-실행-명령"
```

## 7. API 키 입력 방법

프로젝트 루트의 `.env` 파일을 사용합니다.

```text
KPR_TEST_API_KEY=테스트_모델_API_키
KPR_JUDGE_API_KEY=Judge_모델_API_키
```

테스트와 Judge가 같은 API 키를 사용한다면 두 줄에 같은 값을 넣어도
됩니다. 한쪽이 `local`이면 그 역할의 API 키는 필요 없습니다.

프로그램은 다음 순서로 키를 찾습니다.

| 역할과 방식 | 첫 번째로 확인 | 없을 때 확인 |
|---|---|---|
| 테스트 `gemini` | `KPR_TEST_API_KEY` | `GEMINI_API_KEY` |
| Judge `gemini` | `KPR_JUDGE_API_KEY` | `GEMINI_API_KEY` |
| 테스트 `openai-compatible` | `KPR_TEST_API_KEY` | `OPENAI_API_KEY` |
| Judge `openai-compatible` | `KPR_JUDGE_API_KEY` | `OPENAI_API_KEY` |

예를 들어 로컬 테스트 모델과 Gemini Judge를 사용한다면 기존 Gemini 키
하나만 입력해도 됩니다.

```text
GEMINI_API_KEY=실제_Gemini_API_키
```

OpenAI 호환 테스트 모델과 Gemini Judge에 서로 다른 키를 사용한다면 다음과
같이 입력합니다.

```text
KPR_TEST_API_KEY=OpenAI_호환_서비스의_키
KPR_JUDGE_API_KEY=Gemini_API_키
```

주의 사항:

- 실제 키를 `.env.example`에 입력하지 마세요.
- `.env`를 Git에 커밋하지 마세요.
- 명령행에 키를 직접 입력하면 셸 기록에 남을 수 있으므로 사용하지 마세요.
- 프로그램은 API 키를 콘솔이나 `.kpr/config.json`에 출력하지 않습니다.

## 8. 실행

설정과 문제 검증이 끝난 후 실행합니다.

한 문제만 빠르게 시험:

```bash
kpr run data/examples/problems.jsonl --limit 1
```

앞의 5문제 실행:

```bash
kpr run data/examples/problems.jsonl --limit 5
```

입력 파일의 전체 문제 실행:

```bash
kpr run data/examples/problems.jsonl
```

실행하기 전에 프로그램은 다음을 확인합니다.

1. `.kpr/config.json` 사전 설정 존재 여부
2. API 방식에서 필요한 키 존재 여부
3. 로컬 방식에서 실행 파일 존재 여부
4. 문제 JSONL 형식

검사를 통과하면 문제별로 다음처럼 출력합니다.

```text
========================================================================
[1/1] 문제 ID: problem-001

[문제]
대한민국의 수도를 한 문장으로 답하세요.

[테스트 모델 답변]
대한민국의 수도는 서울입니다.

[Judge 모델 답변]
답변이 질문에 적절하게 응답했습니다.
========================================================================
실행 완료: 1개 문제
```

테스트 모델 답변은 파일을 거치지 않고 같은 프로세스의 메모리에서 바로
Judge 모델로 전달됩니다. 새 실행은 `results/`나 별도의 JSONL 결과 파일을
생성하지 않습니다.

## 9. 자주 발생하는 오류

### 사전 설정이 없다는 오류

```bash
kpr configure --test local --judge gemini
```

예전 버전의 `api` 설정이 남아 있다는 오류가 나도 위 명령으로 다시
설정하면 됩니다. 현재 허용되는 값은 `local`, `gemini`,
`openai-compatible`뿐입니다.

### API 키가 없다는 오류

`.env` 파일 위치가 프로젝트 루트인지 확인하고, 선택한 역할에 맞는 키를
입력합니다. 이후 프로그램을 다시 실행합니다.

### HTTP 401 또는 403 오류

API 키가 올바른지, 해당 키에 선택한 모델을 호출할 권한이 있는지
확인합니다.

### HTTP 404 또는 모델을 찾을 수 없다는 오류

`model ID`와 `Base URL`을 제공업체 문서에서 다시 확인합니다. Base URL에
`/chat/completions`를 중복해서 붙이지 않았는지도 확인합니다.

### 로컬 실행 파일을 찾을 수 없다는 오류

```bash
ollama --version
ollama list
```

Ollama가 실행 가능한 상태인지, 설정한 모델이 설치되어 있는지 확인합니다.

### 응답 형식이 맞지 않는 오류

연결한 서비스가 OpenAI 호환 Chat Completions 형식인지 확인합니다. Responses
API만 지원하거나 자체 JSON 형식을 사용하는 서비스는 현재 어댑터와 직접
호환되지 않습니다.

### 호출이 오래 걸리는 경우

로컬 14B 모델은 컴퓨터 성능에 따라 생성 시간이 오래 걸릴 수 있습니다.
먼저 `--limit 1`로 확인한 다음 문제 수를 늘리는 것이 좋습니다.

## 10. 테스트

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

현재 테스트는 문제 스키마, 사전 설정 필수 여부, 세 제공 방식 설정,
UTF-8 로컬 입출력, OpenAI 호환 요청·응답 형식, 테스트 답변의 Judge 전달,
콘솔 출력 및 결과 파일 미생성을 확인합니다.

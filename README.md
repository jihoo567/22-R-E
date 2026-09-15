# 최소 LLM 벤치마크

준비된 문제를 테스트 모델에 보내고, 테스트 모델의 답변을 Judge 모델에
전달한 뒤 두 응답을 콘솔에 출력하는 최소 Python 벤치마크입니다.

```text
문제 JSONL → 테스트 모델 → 테스트 답변 → Judge 모델 → Judge 답변 → 콘솔
```

문제 생성, 규칙 채점, 점수 계산, 보고서, Mock 모델, 결과 파일 저장 기능은
포함하지 않습니다.

## 현재 파일 구성

GitHub 저장소의 현재 주요 파일은 다음과 같습니다.

```text
22-R-E/
├── .env.example
├── .github/
│   └── workflows/
│       └── tests.yml
├── data/
│   └── examples/
│       └── problems.jsonl
├── src/
│   └── korean_prompt_robustness/
│       ├── models/
│       ├── judges/
│       ├── runners/
│       ├── schemas/
│       ├── auth.py
│       ├── cli.py
│       └── config.py
├── tests/
│   └── test_framework.py
├── install_windows.bat
├── kpr.bat
├── run_gemini_5_windows.bat
├── run_local_windows.bat
├── WINDOWS_INSTALL.md
├── pyproject.toml
└── README.md
```

이전 버전에 있던 `configs/`, `results/`, `run_mock_windows.bat`은 현재
프로그램에서 사용하지 않습니다.

## 지원 방식

테스트 모델과 Judge 모델은 각각 다음 중 하나를 선택합니다.

| 이름 | 설명 | 필요한 값 |
|---|---|---|
| `local` | Ollama 또는 stdin/stdout 기반 로컬 명령 | 모델 ID 또는 실행 명령 |
| `gemini` | Google Gemini API | Gemini API 키 |
| `openai-compatible` | OpenAI 호환 Chat Completions API | API 키, 모델 ID, Base URL |

기본 로컬 모델은 `qwen2.5:14b`, 기본 Gemini 모델은
`gemini-3.6-flash`입니다. 다른 모델은 `--test-model`과
`--judge-model`로 지정합니다.

## Windows 설치

### Git으로 받은 경우

```bat
git clone https://github.com/jihoo567/22-R-E.git
cd 22-R-E
install_windows.bat
```

### ZIP으로 받은 경우

1. [최신 GitHub 릴리스](https://github.com/jihoo567/22-R-E/releases/latest)에서 ZIP을 받습니다.
2. ZIP을 완전히 압축 해제합니다.
3. 압축을 푼 폴더에서 `install_windows.bat`을 실행합니다.

Windows 설치 과정은 `.venv`를 만들고 프로그램과 테스트를 설치합니다.
자세한 안내는 [WINDOWS_INSTALL.md](WINDOWS_INSTALL.md)를 참고하세요.

### Windows에서 `kpr`을 인식하지 못할 때

`kpr`은 Windows 전체 PATH에 등록되지 않습니다. 또한 pip가 만드는
`.venv\Scripts\kpr.exe`는 한글·공백 경로에서 인코딩 오류가 날 수 있어
사용하지 않습니다. 프로젝트 루트의 UTF-8 안전 실행 파일을 사용하세요.

```bat
kpr.bat --help
```

모든 Windows 예시는 `kpr.bat`를 기준으로 합니다. PowerShell에서는
`kpr.bat` 앞에 `.\`를 붙여 `.\kpr.bat --help`로 실행합니다. 또는 다음
명령으로 가상환경을 활성화한 뒤 Python 모듈을 직접 실행할 수 있습니다.

```bat
.venv\Scripts\activate.bat
python -m korean_prompt_robustness --help
```

## macOS 설치

```bash
git clone https://github.com/jihoo567/22-R-E.git
cd 22-R-E
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/kpr --help
```

가상환경을 활성화하려면 다음 명령을 사용합니다.

```bash
source .venv/bin/activate
```

활성화하지 않아도 `.venv/bin/kpr`로 직접 실행할 수 있습니다.

## 문제 파일

입력은 UTF-8 JSONL입니다. 한 줄에 문제 하나를 작성하며 `id`와 `prompt`가
필수입니다. `metadata`는 선택입니다.

```json
{"id":"problem-001","prompt":"대한민국의 수도는 어디인가요?","metadata":{"category":"knowledge"}}
{"id":"problem-002","prompt":"물의 화학식을 설명하세요.","metadata":{"category":"science"}}
```

기본 예제 파일의 정확한 이름은 다음과 같습니다.

```text
data/examples/problems.jsonl
```

macOS 검증:

```bash
.venv/bin/kpr validate data/examples/problems.jsonl
```

Windows 검증:

```bat
kpr.bat validate data\examples\problems.jsonl
```

## API 키 입력

`.env.example`을 복사해 프로젝트 최상위에 `.env`를 만들고 실제 키를
입력합니다. API 키는 Git에 올리거나 설정 JSON에 직접 넣지 않습니다.

```text
KPR_TEST_API_KEY=
KPR_JUDGE_API_KEY=
GEMINI_API_KEY=
OPENAI_API_KEY=
```

키를 찾는 순서는 다음과 같습니다.

| 역할 | 방식 | 우선 사용 | 대체 키 |
|---|---|---|---|
| 테스트 | `gemini` | `KPR_TEST_API_KEY` | `GEMINI_API_KEY` |
| Judge | `gemini` | `KPR_JUDGE_API_KEY` | `GEMINI_API_KEY` |
| 테스트 | `openai-compatible` | `KPR_TEST_API_KEY` | `OPENAI_API_KEY` |
| Judge | `openai-compatible` | `KPR_JUDGE_API_KEY` | `OPENAI_API_KEY` |

예를 들어 테스트 모델이 로컬이고 Judge만 Gemini라면 다음 한 줄이면
충분합니다.

```text
GEMINI_API_KEY=실제_Gemini_API_키
```

## 모델 사전 설정

`run` 전에 반드시 `configure`를 실행해야 합니다. 설정은 Git에 올라가지
않는 `.kpr/config.json`에 저장됩니다.

### 로컬 Llama 테스트 / Gemini Judge

macOS:

```bash
.venv/bin/kpr configure \
  --test local --test-model llama3.2:1b \
  --judge gemini --judge-model gemini-3.6-flash
```

Windows:

```bat
kpr.bat configure ^
  --test local --test-model llama3.2:1b ^
  --judge gemini --judge-model gemini-3.6-flash
```

모델 이름은 `ollama list`의 `NAME`을 정확히 사용합니다. 프로그램은 위
설정에서 `ollama run llama3.2:1b` 명령을 자동으로 만듭니다.

### Gemini 3.6 테스트 / Gemini 3.7 Judge

```bash
.venv/bin/kpr configure \
  --test gemini --test-model gemini-3.6-flash \
  --judge gemini --judge-model gemini-3.7-flash
```

Windows에서는 `run_gemini_5_windows.bat`을 실행해도 같은 모델 조합으로
예제 5문제를 실행합니다.

### 테스트와 Judge 모두 로컬

```bash
.venv/bin/kpr configure \
  --test local --test-model llama3.2:1b \
  --judge local --judge-model llama3.2:1b
```

`run_local_windows.bat`은 `qwen2.5:14b`를 테스트와 Judge 양쪽에 사용하는
Windows 편의 파일입니다. 다른 모델을 사용하려면 위처럼 직접
`configure`하세요.

### OpenAI 호환 API 사용

OpenAI 호환 방식은 API 키만으로 서버와 모델을 알 수 없으므로 모델 ID와
Base URL이 필수입니다.

```bash
.venv/bin/kpr configure \
  --test local --test-model llama3.2:1b \
  --judge openai-compatible \
  --judge-model 실제-Judge-모델-ID \
  --judge-base-url https://제공업체.example/v1
```

이 방식은 Bearer 인증과 `POST /chat/completions`, 그리고
`choices[0].message.content` 응답 형식을 지원하는 API에만 사용할 수
있습니다.

## 설정 확인

macOS:

```bash
.venv/bin/kpr show-config
```

Windows:

```bat
kpr.bat show-config
```

허용되는 방식은 `local`, `gemini`, `openai-compatible`뿐입니다. 예전
버전의 `api` 값이 남아 있다는 오류가 나오면 `configure`를 다시 실행하세요.

## 실행

macOS에서 한 문제 실행:

```bash
.venv/bin/kpr run data/examples/problems.jsonl --limit 1
```

Windows에서 한 문제 실행:

```bat
kpr.bat run data\examples\problems.jsonl --limit 1
```

앞의 5문제 실행:

```bash
.venv/bin/kpr run data/examples/problems.jsonl --limit 5
```

전체 문제 실행:

```bash
.venv/bin/kpr run data/examples/problems.jsonl
```

각 문제마다 다음 내용이 콘솔에 표시됩니다.

```text
[문제]
대한민국의 수도를 한 문장으로 답하세요.

[테스트 모델 답변]
대한민국의 수도는 서울입니다.

[Judge 모델 답변]
답변이 질문에 적절하게 응답했습니다.
```

답변은 파일을 거치지 않고 메모리에서 Judge로 전달됩니다. 새 결과 JSONL,
점수 파일, CSV 보고서는 생성하지 않습니다. 실행을 다시 시작하면 첫
문제부터 모델을 다시 호출합니다.

## 현재 CLI 명령

```text
kpr configure    테스트 모델과 Judge 모델 설정
kpr show-config  현재 설정 확인
kpr validate     문제 JSONL 검증
kpr run          테스트 모델과 Judge 실행
```

도움말:

```bash
.venv/bin/kpr --help
.venv/bin/kpr configure --help
.venv/bin/kpr run --help
```

## 테스트

macOS 또는 Linux:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Windows:

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

GitHub Actions에서도 Windows와 Linux의 Python 3.10 및 3.13 조합을
검증합니다.

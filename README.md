# Korean Prompt Robustness

준비된 JSONL 문제를 테스트 모델에 보내고, 그 답변을 Judge 모델에 전달한 뒤
두 응답을 콘솔에 출력하는 최소 Python 벤치마크입니다. 현재 버전은 `0.6.0`입니다.

```text
문제 JSONL → 테스트 모델 → 테스트 답변 → Judge 모델 → Judge 답변 → 콘솔
```

문제 생성, 점수 계산, 결과 파일 저장, 그래프와 보고서 기능은 포함하지
않습니다. 테스트 모델과 Judge 모델은 로컬 Ollama, Gemini API,
OpenAI 호환 API 중에서 각각 독립적으로 선택할 수 있습니다.

## 가장 빠른 시작

### 공통 준비물

- Git
- Python 3.10 이상
- 로컬 모델을 사용할 경우 Ollama와 내려받은 모델
- API 모델을 사용할 경우 해당 API 키

가상환경을 직접 만들거나 활성화하고 `pip install`을 실행할 필요는 없습니다.
처음 명령을 실행하면 저장소 안의 `.venv`를 자동으로 만들고 프로그램을
설치합니다. 소스가 변경된 뒤 실행하면 필요한 경우 자동으로 다시 설치합니다.

### macOS 또는 Linux

```bash
git clone https://github.com/jihoo567/22-R-E.git
cd 22-R-E
./kpr --help
```

실행 권한이 제거된 ZIP 파일을 받은 경우에만 처음 한 번 다음 명령을 사용하세요.

```bash
chmod +x kpr
./kpr --help
```

`python3 kpr.py --help`도 동일하게 작동합니다.

### Windows PowerShell

```powershell
git clone https://github.com/jihoo567/22-R-E.git
Set-Location .\22-R-E
.\kpr.bat --help
```

### Windows CMD

```bat
git clone https://github.com/jihoo567/22-R-E.git
cd 22-R-E
kpr.bat --help
```

## 첫 실행에서 자동으로 하는 일

`kpr`, `kpr.bat`, `kpr.py`는 모두 같은 공통 부트스트랩을 사용합니다.

1. Python 3.10 이상인지 확인합니다.
2. 프로젝트의 `.venv`가 없으면 자동 생성합니다.
3. 현재 프로그램이 설치되지 않았거나 소스가 변경됐으면 자동 설치합니다.
4. `.env`가 없으면 `.env.example`을 복사합니다.
5. `kpr-config.json`이 없으면 직접 편집할 수 있는 예제 설정을 복사합니다.
6. 준비된 가상환경에서 실제 `kpr` 명령을 실행합니다.

`.venv`, `.env`, `kpr-config.json`은 Git에 올라가지 않습니다. 기존
API 키와 모델 설정도 자동 업데이트 과정에서 덮어쓰지 않습니다.

Python 자체가 없는 컴퓨터에서는 부트스트랩도 실행할 수 없습니다. 이 경우
Python 3.10 이상을 먼저 설치하고, Windows에서는 설치 화면의
`Add Python to PATH`를 선택하세요.

## 설정 파일 직접 수정

별도의 설정 명령을 입력할 필요가 없습니다. 첫 실행 후 프로젝트 루트에 생긴
`kpr-config.json`을 VS Code나 메모장으로 직접 수정하세요. 기본 설정은 테스트와
Judge 모두 `qwen2.5:14b`를 사용하는 다음 구조입니다.

```json
{
  "input_path": "data/examples/problems.jsonl",
  "test_model": {
    "provider": "local",
    "model_id": "qwen2.5:14b",
    "command": "ollama run qwen2.5:14b",
    "base_url": null,
    "api_key_env": null,
    "system_instruction": null,
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

원본 예시는 `kpr-config.example.json`에 있습니다. 이 파일은 참고용이고 실제
실행에서는 `kpr-config.json`을 읽습니다. 모든 변수 설명과
Local·Gemini·OpenAI 호환 API 예시는 [CONFIG_GUIDE.md](CONFIG_GUIDE.md)에
있습니다. 같은 문서 경로는 `./kpr --help` 또는 `kpr.bat --help`에도 표시됩니다.

`input_path`에는 평소 실행할 문제 JSONL 경로를 저장합니다. 상대 경로는
`kpr-config.json`이 있는 폴더를 기준으로 합니다. 이 값을 설정하면 `run` 뒤에
문제 파일 경로를 반복해서 작성하지 않아도 됩니다.

각 모델의 `system_instruction`을 수정하면 테스트 모델 지시문과 Judge 지시문을
서로 독립적으로 설정할 수 있습니다. 지시문을 사용하지 않으려면 `null`로
지정합니다. API 모델에는 system instruction으로 전달되고, 로컬 모델에는
문제 앞에 붙여 하나의 표준 입력으로 전달됩니다.

### 테스트와 Judge 모두 로컬

위 기본 설정에서 `model_id`와 `command`를 `ollama list`에 표시된 모델에 맞게
수정합니다. 두 값의 모델 이름은 서로 같아야 합니다.

사용 가능한 Ollama 모델 이름은 다음 명령으로 확인합니다.

```bash
ollama list
```

### 로컬 테스트 모델과 Gemini Judge

`kpr-config.json`의 `judge_model`을 다음처럼 바꿉니다.

```json
"judge_model": {
  "provider": "gemini",
  "model_id": "gemini-3.6-flash",
  "command": null,
  "base_url": null,
  "api_key_env": "KPR_JUDGE_API_KEY",
  "system_instruction": "당신은 테스트 모델의 답변을 검토하는 독립 평가자입니다.",
  "temperature": 0.0,
  "seed": null,
  "max_tokens": 1024,
  "timeout_seconds": 120.0
}
```

프로젝트 루트의 `.env`를 열어 키를 입력합니다.

```text
KPR_JUDGE_API_KEY=실제_Gemini_API_키
```

또는 공용 Gemini 키를 사용할 수 있습니다.

```text
GEMINI_API_KEY=실제_Gemini_API_키
```

### OpenAI 호환 API

OpenAI 호환 방식은 Bearer 인증, `POST /chat/completions`,
`choices[0].message.content` 응답 형식을 지원하는 서버에 사용할 수 있습니다.
모델 ID와 Base URL을 함께 지정해야 합니다. 예를 들어 Judge 설정을 다음처럼
직접 작성합니다.

```json
"judge_model": {
  "provider": "openai-compatible",
  "model_id": "실제-모델-ID",
  "command": null,
  "base_url": "https://제공업체.example/v1",
  "api_key_env": "KPR_JUDGE_API_KEY",
  "system_instruction": "당신은 테스트 모델의 답변을 검토하는 독립 평가자입니다.",
  "temperature": 0.0,
  "seed": null,
  "max_tokens": 1024,
  "timeout_seconds": 120.0
}
```

API 키는 `.env`의 `KPR_JUDGE_API_KEY` 또는 `OPENAI_API_KEY`에 저장합니다.

## 문제 파일

입력은 UTF-8 JSONL이며 한 줄에 문제 하나를 작성합니다. `id`와 `prompt`는
필수이고 `metadata`는 선택입니다.

```json
{"id":"problem-001","prompt":"대한민국의 수도는 어디인가요?","metadata":{"category":"knowledge"}}
{"id":"problem-002","prompt":"물의 화학식을 설명하세요.","metadata":{"category":"science"}}
```

기본 예제는 `data/examples/problems.jsonl`에 있습니다.

macOS/Linux:

```bash
./kpr validate data/examples/problems.jsonl
./kpr run --limit 1
```

Windows PowerShell:

```powershell
.\kpr.bat validate data\examples\problems.jsonl
.\kpr.bat run --limit 1
```

`--limit 1`을 빼면 파일의 모든 문제를 실행합니다. 문제와 모델 응답, Judge
응답은 콘솔에만 표시되며 별도 결과 파일을 만들지 않습니다.
명령행에 문제 경로를 직접 쓰면 설정의 `input_path`보다 우선합니다.

```bash
./kpr run data/examples/other-problems.jsonl --limit 1
```

## 명령 목록

| 명령 | 역할 |
|---|---|
| `show-config` | 현재 설정 출력 |
| `validate` | 문제 JSONL 검사 |
| `run` | 테스트 모델 답변 생성 후 Judge 실행 |

예시:

```bash
./kpr show-config
./kpr run --help
```

Windows에서는 `./kpr`을 `.\kpr.bat`으로 바꾸면 됩니다.

모델 설정은 `kpr-config.json`을 직접 수정합니다.

## API 키를 찾는 순서

| 역할 | 방식 | 우선 확인 | 대체 키 |
|---|---|---|---|
| 테스트 | `gemini` | `KPR_TEST_API_KEY` | `GEMINI_API_KEY` |
| Judge | `gemini` | `KPR_JUDGE_API_KEY` | `GEMINI_API_KEY` |
| 테스트 | `openai-compatible` | `KPR_TEST_API_KEY` | `OPENAI_API_KEY` |
| Judge | `openai-compatible` | `KPR_JUDGE_API_KEY` | `OPENAI_API_KEY` |

API 키를 `kpr-config.json`에 직접 넣지 마세요. 설정에는 API 키 값이 아니라
키를 읽을 환경변수 이름만 작성합니다. 실제 키는 `.env`에 저장하며 Git에서
제외됩니다.

## 프로그램 구조

```text
22-R-E/
├── kpr                         macOS/Linux 자동 준비 런처
├── kpr.bat                     Windows 자동 준비 런처
├── kpr.py                      공통 가상환경·설치 부트스트랩
├── kpr-config.example.json     직접 편집할 모델 설정 예시
├── kpr-config.json             첫 실행 때 생성되는 실제 설정(Git 제외)
├── CONFIG_GUIDE.md             설정 변수와 Local/API 예시 설명
├── data/examples/problems.jsonl
├── src/korean_prompt_robustness/
│   ├── cli.py                  CLI 명령
│   ├── config.py               모델 설정
│   ├── dataset.py              JSONL 검증
│   ├── local_process.py        로컬 모델 실행
│   ├── pipeline.py             테스트 → Judge 흐름
│   └── providers/              모델 제공업체 연결
├── tests/test_framework.py
└── pyproject.toml
```

`kpr.py`는 `pyproject.toml`과 `src/**/*.py`의 지문을 저장합니다. `git pull`
또는 코드 수정으로 지문이 달라지면 다음 실행에서 패키지를 자동 갱신합니다.

## 업데이트

가상환경을 다시 만들거나 `pip install`을 직접 실행할 필요가 없습니다.

```bash
git pull --ff-only origin main
./kpr --help
```

Windows:

```powershell
git pull --ff-only origin main
.\kpr.bat --help
```

## 자동 테스트

부트스트랩을 한 번 실행한 뒤 다음과 같이 테스트합니다.

macOS/Linux:

```bash
./kpr --help
.venv/bin/python -m unittest discover -s tests -v
```

Windows PowerShell:

```powershell
.\kpr.bat --help
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

GitHub Actions는 Linux와 Windows의 Python 3.10 및 3.13에서, 수동 설치 없이
부트스트랩부터 전체 테스트까지 확인합니다. Windows에서는 한글 경로도 함께
검증합니다.

## 문제 해결

### Python을 찾을 수 없음

Python 3.10 이상을 설치하고 터미널을 다시 여세요.

```bash
python3 --version
```

Windows에서는 다음도 확인합니다.

```powershell
py --version
```

### macOS/Linux에서 `Permission denied`

ZIP 압축 과정에서 실행 권한이 사라진 경우입니다.

```bash
chmod +x kpr
./kpr --help
```

또는 실행 권한 없이 공통 런처를 직접 사용할 수 있습니다.

```bash
python3 kpr.py --help
```

### 로컬 모델을 찾지 못함

```bash
ollama --version
ollama list
```

설정한 모델 ID가 `ollama list`의 `NAME`과 정확히 같아야 합니다.

### API 키가 없음

프로젝트 루트의 `.env`에 역할별 키 또는 제공업체 공용 키를 입력하세요.

### 자동 설치를 처음부터 다시 실행

가상환경이 손상된 경우에만 `.venv`를 삭제한 뒤 런처를 다시 실행합니다.
평소에는 삭제할 필요가 없습니다.

macOS/Linux:

```bash
rm -rf .venv
./kpr --help
```

Windows PowerShell:

```powershell
Remove-Item -Recurse -Force .\.venv
.\kpr.bat --help
```

Windows의 자세한 화면별 설명은 [WINDOWS_INSTALL.md](WINDOWS_INSTALL.md)를
참고하세요.

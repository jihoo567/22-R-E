# Korean Prompt Robustness

준비된 문제를 한 모델에 질문하고, 그 답변을 다른 모델이 검토하도록 하는
간단한 Python 벤치마크입니다. 프로젝트 버전은 `0.4.0`입니다.

```text
문제 파일(JSONL)
    ↓
테스트 모델이 답변 생성
    ↓
문제와 답변을 Judge 모델에 전달
    ↓
테스트 답변과 Judge 평가를 콘솔에 출력
```

여기서 **테스트 모델**은 성능을 확인할 대상이고, **Judge 모델**은 테스트
모델의 답변을 읽고 평가하는 모델입니다. 두 역할에는 로컬 Ollama 모델,
Gemini API 또는 OpenAI 호환 API를 각각 독립적으로 선택할 수 있습니다.

이 프로그램은 답변과 평가를 확인하는 최소 실행 도구입니다. 점수 계산,
순위 결정, 결과 파일 저장, 그래프와 보고서 생성 기능은 포함하지 않습니다.

## 1. 가장 빠르게 실행하기: Windows 로컬 모델

처음 실행한다면 아래 순서를 그대로 따르면 됩니다.

### 준비물

- Windows 10 또는 11
- Python 3.10 이상
- [Ollama](https://ollama.com/)
- 실행할 Ollama 모델

Python과 Ollama가 설치됐는지 확인합니다.

```powershell
python --version
ollama --version
ollama list
```

`ollama list`가 비어 있다면 모델을 먼저 받습니다. 기본 모델은
`qwen2.5:14b`이지만 컴퓨터 사양에 맞는 다른 모델을 사용해도 됩니다.

```powershell
ollama pull qwen2.5:14b
```

### 설치

아직 저장소를 받지 않았다면 Git으로 내려받습니다.

```powershell
git clone https://github.com/jihoo567/22-R-E.git
Set-Location .\22-R-E
.\install_windows.bat
```

ZIP으로 받은 경우에는 완전히 압축 해제한 뒤 설치하세요. 이미 저장소가 있다면
PowerShell에서 프로젝트 폴더로 이동한 뒤 설치 파일을 실행합니다.

```powershell
Set-Location "C:\프로젝트를\받은\경로\22-R-E"
.\install_windows.bat
```

설치 파일은 다음 작업을 자동으로 수행합니다.

1. Python 버전을 확인합니다.
2. 프로젝트 안에 `.venv` 가상환경을 만듭니다.
3. 프로그램을 설치합니다.
4. `.env`가 없으면 예제 파일을 복사합니다.
5. 자동 테스트와 Windows 실행 파일을 검사합니다.

### 테스트 모델과 Judge 모델 설정

다음 명령은 두 역할 모두에 `qwen2.5:14b`를 사용합니다.

```powershell
.\kpr.bat configure --test local --test-model qwen2.5:14b --judge local --judge-model qwen2.5:14b
```

설정이 올바르게 저장됐는지 확인합니다.

```powershell
.\kpr.bat show-config
```

### 예제 문제 실행

입력 파일을 먼저 검증한 다음 한 문제만 실행합니다.

```powershell
.\kpr.bat validate data\examples\problems.jsonl
.\kpr.bat run data\examples\problems.jsonl --limit 1
```

정상 실행되면 다음 세 항목이 콘솔에 표시됩니다.

```text
[문제]
대한민국의 수도를 한 문장으로 답하세요.

[테스트 모델 답변]
대한민국의 수도는 서울입니다.

[Judge 모델 답변]
답변이 정확하고 질문의 조건을 충족합니다.
```

## 2. 권장 조합: 로컬 테스트 모델과 Gemini Judge

테스트 모델은 컴퓨터에서 실행하고 평가만 Gemini API에 맡길 수 있습니다.

### API 키 저장

프로젝트 루트의 `.env` 파일을 열고 다음 중 하나를 입력합니다.

```text
KPR_JUDGE_API_KEY=실제_Gemini_API_키
```

또는 Gemini 공용 키 이름을 사용할 수 있습니다.

```text
GEMINI_API_KEY=실제_Gemini_API_키
```

`.env`는 Git에서 제외됩니다. API 키를 소스 코드, 명령행 인자,
`.kpr/config.json`에 넣지 마세요.

### 설정과 실행

```powershell
.\kpr.bat configure --test local --test-model qwen2.5:14b --judge gemini --judge-model gemini-3.6-flash
.\kpr.bat run data\examples\problems.jsonl --limit 1
```

이 조합에서는 테스트 문제만 로컬 Ollama에 전달됩니다. 로컬 모델이 만든
답변과 원래 문제는 Judge 평가를 위해 Gemini API로 전송됩니다.

## 3. 지원하는 모델 방식

테스트 모델과 Judge 모델에 아래 방식 중 하나를 각각 선택합니다.

| 설정값 | 실행 위치 | 필요한 값 |
|---|---|---|
| `local` | 현재 컴퓨터 | Ollama 모델 이름 또는 로컬 실행 명령 |
| `gemini` | Google Gemini API | API 키와 Gemini 모델 ID |
| `openai-compatible` | 지정한 API 서버 | API 키, 모델 ID, Base URL |

기본 모델은 다음과 같습니다.

- 로컬: `qwen2.5:14b`
- Gemini: `gemini-3.6-flash`

`local`에서 모델 이름을 생략하면 기본 로컬 모델을 사용합니다. 실제로 설치된
모델 이름은 `ollama list`의 `NAME` 열에서 확인하세요.

### 자주 쓰는 설정 예시

테스트와 Judge 모두 로컬:

```powershell
.\kpr.bat configure --test local --test-model qwen2.5:14b --judge local --judge-model qwen2.5:14b
```

테스트는 로컬, Judge는 Gemini:

```powershell
.\kpr.bat configure --test local --test-model qwen2.5:14b --judge gemini --judge-model gemini-3.6-flash
```

테스트와 Judge 모두 Gemini:

```powershell
.\kpr.bat configure --test gemini --test-model gemini-3.6-flash --judge gemini --judge-model gemini-3.6-flash
```

로컬 테스트와 OpenAI 호환 Judge:

```powershell
.\kpr.bat configure --test local --test-model qwen2.5:14b --judge openai-compatible --judge-model 실제-모델-ID --judge-base-url https://제공업체.example/v1
```

OpenAI 호환 방식은 Bearer 인증, `POST /chat/completions`,
`choices[0].message.content` 형식을 지원하는 서버에 사용할 수 있습니다.
프로젝트 루트의 `.env`에는 해당 서버가 발급한 키를 저장합니다.

```text
OPENAI_API_KEY=실제_OpenAI_호환_서버_API_키
```

## 4. 문제 파일 만들기

문제 파일은 UTF-8로 저장한 JSONL 파일입니다. JSONL은 JSON 객체를 한 줄에
하나씩 기록하는 형식입니다. 빈 줄은 무시합니다.

```json
{"id":"problem-001","prompt":"대한민국의 수도는 어디인가요?","metadata":{"category":"knowledge"}}
{"id":"problem-002","prompt":"물의 화학식을 설명하세요.","metadata":{"category":"science"}}
```

각 필드의 의미는 다음과 같습니다.

| 필드 | 필수 여부 | 설명 |
|---|---|---|
| `id` | 필수 | 문제를 구분하는 중복되지 않는 문자열 |
| `prompt` | 필수 | 테스트 모델에 그대로 전달할 질문 |
| `metadata` | 선택 | 분류 등 문제의 추가 정보 객체 |

기본 예제는 `data/examples/problems.jsonl`에 있습니다.

파일을 실행하기 전에 형식을 확인할 수 있습니다.

```powershell
.\kpr.bat validate data\examples\problems.jsonl
```

## 5. CLI 사용 방법

프로그램에는 네 가지 명령이 있습니다.

| 명령 | 역할 |
|---|---|
| `configure` | 테스트 모델과 Judge 모델 설정 |
| `show-config` | 현재 설정 출력 |
| `validate` | 문제 JSONL 형식 검사 |
| `run` | 테스트 모델과 Judge 실행 |

전체 도움말:

```powershell
.\kpr.bat --help
```

명령별 도움말:

```powershell
.\kpr.bat configure --help
.\kpr.bat run --help
```

앞에서부터 한 문제만 실행:

```powershell
.\kpr.bat run data\examples\problems.jsonl --limit 1
```

앞에서부터 다섯 문제 실행:

```powershell
.\kpr.bat run data\examples\problems.jsonl --limit 5
```

파일의 모든 문제 실행:

```powershell
.\kpr.bat run data\examples\problems.jsonl
```

모든 명령은 프로젝트 루트에서 실행해야 합니다. `configure`가 만든 설정은
프로젝트 루트의 `.kpr/config.json`에 저장됩니다.

## 6. 프로그램 작동 방식

실행 준비는 모델 호출 전에 한 번만 수행합니다.

1. 현재 작업 폴더의 `.env`와 `.kpr/config.json`에서 키와 모델 설정을 읽습니다.
2. API 키 또는 로컬 실행 파일이 준비됐는지 확인합니다.
3. JSONL 전체의 형식과 중복 ID를 검사하고, 실행할 문제만 보관합니다.

이후 각 문제마다 다음 순서를 반복합니다.

1. `prompt`를 변경하지 않고 테스트 모델에 전달합니다.
2. 테스트 모델의 답변을 콘솔에 출력합니다.
3. 원래 문제와 테스트 답변을 하나의 Judge 프롬프트로 만듭니다.
4. 같은 모델 호출 함수에 Judge 설정과 프롬프트를 전달합니다.
5. Judge 응답을 콘솔에 출력하고 다음 문제로 이동합니다.

답변과 평가는 새 파일에 저장되지 않습니다. 한 문제가 실패하면 오류를
출력하고 다음 문제를 계속 처리합니다. 하나 이상의 문제가 실패한 실행은
마지막에 0이 아닌 종료 코드를 반환하므로 배치 파일이나 CI에서도 실패를
감지할 수 있습니다.

모델 호출은 자동으로 재시도하지 않습니다. 설정 오류나 네트워크 문제를 먼저
확인한 뒤 다시 실행하면 됩니다. 기본 제한 시간은 로컬 모델 300초, API 모델
120초입니다.

## 7. 소스 코드 구조

```text
22-R-E/
├── data/examples/problems.jsonl       예제 문제
├── src/korean_prompt_robustness/
│   ├── cli.py                         CLI 명령과 전체 실행 진입점
│   ├── config.py                      모델 설정 검증과 저장
│   ├── auth.py                        환경변수에서 API 키 조회
│   ├── dataset.py                     JSONL 읽기와 문제 검증
│   ├── local_process.py               로컬 명령 공통 실행
│   ├── providers/                     테스트와 Judge가 공유하는 모델 호출
│   │   ├── __init__.py                generate_text() 제공자 선택
│   │   ├── gemini.py                  Gemini REST API
│   │   ├── openai_compatible.py       OpenAI 호환 API
│   │   └── http.py                    공통 JSON HTTP 통신
│   └── pipeline.py                    테스트 → Judge 순서와 평가 프롬프트
├── tests/test_framework.py            자동 테스트
├── install_windows.bat                Windows 설치
├── kpr.bat                            Windows UTF-8 안전 CLI 실행
├── run_local_windows.bat              로컬 모델 5문제 편의 실행
├── run_gemini_5_windows.bat            Gemini 5문제 편의 실행
├── WINDOWS_INSTALL.md                 상세 Windows 안내
└── pyproject.toml                     Python 패키지 정보
```

코드를 처음 읽을 때는 `cli.py → pipeline.py → providers/` 순서로 보면 됩니다.
`cli.py`는 사용자의 명령을 받고, `pipeline.py`는 문제별 실행과 Judge 프롬프트를
담당하며, `providers/`는 실제 모델과 통신합니다. 테스트와 Judge는 별도 클래스가
아니라 같은 `generate_text()` 함수에 다른 입력과 설정을 전달하는 두 역할입니다.

| 읽는 순서 | 파일 | 확인할 내용 |
|---|---|---|
| 1 | `cli.py` | 명령을 받고 설정·입력을 준비하는 부분 |
| 2 | `pipeline.py` | 테스트 답변을 Judge에 전달하는 전체 흐름 |
| 3 | `providers/__init__.py` | 설정에 따라 실제 호출 방식을 선택하는 부분 |
| 4 | `providers/gemini.py`, `providers/openai_compatible.py` | API 요청·응답 형식 |
| 필요할 때 | `dataset.py`, `config.py`, `auth.py`, `local_process.py` | 데이터·설정·인증·로컬 실행 |

0.4.0에서는 기존 `models/`와 `judges/`의 중복 클래스·factory를 공통 제공자
함수로 합쳤습니다. `schemas/`와 `runners/`는 각각 `dataset.py`와
`pipeline.py`로 정리했습니다. CLI 명령과 저장된 모델 설정 형식은 유지되지만,
소스 코드를 직접 import하는 경우에는 새 파일 경로를 사용해야 합니다.

JSONL은 한 줄씩 읽고 검증합니다. `--limit 1`을 쓰면 파일 전체의 형식과 중복
ID는 검사하지만 실행할 한 문제의 본문만 보관합니다. 따라서 큰 데이터 파일의
일부만 시험할 때 불필요한 메모리 사용을 줄입니다. 모델 응답도 문제별로만
사용하고 누적하지 않습니다.

## 8. API 키를 찾는 순서

프로그램은 역할별 키를 먼저 확인하고, 없으면 일반 제공업체 키를 확인합니다.

| 역할 | 방식 | 우선 확인 | 대체 키 |
|---|---|---|---|
| 테스트 | `gemini` | `KPR_TEST_API_KEY` | `GEMINI_API_KEY` |
| Judge | `gemini` | `KPR_JUDGE_API_KEY` | `GEMINI_API_KEY` |
| 테스트 | `openai-compatible` | `KPR_TEST_API_KEY` | `OPENAI_API_KEY` |
| Judge | `openai-compatible` | `KPR_JUDGE_API_KEY` | `OPENAI_API_KEY` |

테스트 모델과 Judge 모델에 서로 다른 키를 사용하려면 역할별 키 두 개를
설정하세요. 같은 키를 사용한다면 `GEMINI_API_KEY` 또는 `OPENAI_API_KEY`
하나만 설정해도 됩니다.
이미 터미널 환경변수에 설정된 값은 `.env`가 덮어쓰지 않습니다.

## 9. Windows 편의 실행 파일

Windows에서는 `.venv\Scripts\kpr.exe` 대신 프로젝트의 `kpr.bat`을
사용하세요. `kpr.bat`은 UTF-8 환경을 준비한 뒤 가상환경의 Python으로
프로그램을 실행하므로 한글과 공백이 포함된 경로에서도 안전합니다.

- `run_local_windows.bat`: `qwen2.5:14b`를 두 역할에 설정하고 예제 5문제 실행
- `run_gemini_5_windows.bat`: Gemini 테스트/Judge 조합으로 예제 5문제 실행

직접 설정을 선택하려면 편의 파일 대신 `kpr.bat configure`와
`kpr.bat run`을 사용하세요.

## 10. macOS와 Linux

```bash
git clone https://github.com/jihoo567/22-R-E.git
cd 22-R-E
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/kpr --help
```

로컬 모델과 Judge를 설정하고 한 문제를 실행하는 예시는 다음과 같습니다.

```bash
.venv/bin/kpr configure \
  --test local --test-model qwen2.5:14b \
  --judge local --judge-model qwen2.5:14b
.venv/bin/kpr run data/examples/problems.jsonl --limit 1
```

## 11. 자동 테스트

Windows:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

macOS 또는 Linux:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

GitHub Actions는 Windows와 Linux에서 Python 3.10 및 3.13 조합을 검사하며,
Windows 한글 경로에서 설정 파일이 올바른 위치에 생성되는지도 확인합니다.

### 프로그램 업데이트 후에는 다시 설치하세요

이 프로그램은 `pip install .`로 설치하므로 소스 파일을 바꾼 것만으로는
가상환경의 설치본이 갱신되지 않습니다. 업데이트하거나 직접 코드를 수정한 뒤
다시 설치해야 합니다. 기존 `.env`와 모델 설정은 그대로 사용합니다.

Windows:

```powershell
git pull --ff-only origin main
.\install_windows.bat
```

macOS 또는 Linux:

```bash
git pull --ff-only origin main
.venv/bin/python -m pip install .
```

## 12. 자주 발생하는 문제

### `kpr` 명령을 찾을 수 없습니다

Windows 전체 PATH에 설치되는 명령이 아닙니다. 프로젝트 루트에서 다음처럼
실행하세요.

```powershell
.\kpr.bat --help
```

### 가상환경이 없다는 오류가 표시됩니다

```powershell
.\install_windows.bat
```

### 로컬 실행 파일 또는 모델을 찾지 못합니다

```powershell
ollama --version
ollama list
```

설정에 입력한 모델 ID가 `ollama list`의 `NAME`과 정확히 같은지 확인하세요.

### API 키가 없다는 오류가 표시됩니다

프로젝트 루트의 `.env`를 확인하세요. Judge만 Gemini라면
`KPR_JUDGE_API_KEY` 또는 `GEMINI_API_KEY` 중 하나가 필요합니다.

### API HTTP 401 또는 403

API 키가 정확한지, 해당 키에 모델 접근 권한이 있는지 확인하세요.

### API HTTP 404

`configure`에 입력한 모델 ID와 Base URL이 현재 제공업체에서 실제로
지원되는 값인지 확인하세요.

### 한글 출력이 깨집니다

Windows에서는 `kpr.bat`을 사용하세요. 직접 Python을 실행해야 한다면 먼저
UTF-8 환경변수를 설정할 수 있습니다.

```powershell
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"
```

더 자세한 Windows 설치 설명은 [WINDOWS_INSTALL.md](WINDOWS_INSTALL.md)를
참고하세요.

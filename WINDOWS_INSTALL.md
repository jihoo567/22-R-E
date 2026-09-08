# Windows 설치 및 실행

이 문서는 GitHub 릴리스 ZIP을 내려받은 Windows 사용자를 기준으로
설명합니다. 프로그램은 테스트 모델과 Judge 모델의 답변을 콘솔에만
출력하며 결과 파일을 만들지 않습니다.

## 1. 준비물

- Windows 10 또는 Windows 11
- Python 3.10 이상
- Gemini 또는 OpenAI 호환 API를 사용할 경우 해당 API 키
- 로컬 모델을 사용할 경우 Ollama와 사용할 모델

Python 설치 화면에서는 `Add Python to PATH`를 선택하세요.

## 2. 설치

1. GitHub Releases에서 최신 `korean-prompt-robustness-windows-*.zip`을 받습니다.
2. ZIP 파일을 원하는 폴더에 완전히 압축 해제합니다.
3. 압축을 푼 폴더에서 `install_windows.bat`을 실행합니다.
4. Windows 보호 화면이 나오면 파일 출처를 확인한 뒤 실행을 선택합니다.
5. 마지막 테스트가 `OK`로 끝나는지 확인합니다.

설치 프로그램은 `.venv` 가상환경을 만들고 패키지를 설치한 다음 전체 단위
테스트를 실행합니다. 기존 `.env`가 없다면 빈 예제 파일을 복사합니다.

## 3. 모델 방식

테스트 모델과 Judge 모델은 각각 다음 중 하나를 선택합니다.

```text
local
gemini
openai-compatible
```

실행 전에 반드시 `configure`가 필요합니다. 명령 프롬프트에서 프로젝트
폴더로 이동한 뒤 아래 명령을 사용합니다. 경로에 공백이나 한글이 있어도
가상환경의 Python을 직접 호출하므로 사용할 수 있습니다.

## 4. API 키 입력

프로젝트 폴더의 `.env`를 메모장으로 엽니다.

```bat
notepad .env
```

역할별로 다른 키를 사용할 때:

```text
KPR_TEST_API_KEY=테스트_모델_API_키
KPR_JUDGE_API_KEY=Judge_모델_API_키
```

Gemini 키 하나를 양쪽에서 사용할 때는 다음 한 줄만 있어도 됩니다.

```text
GEMINI_API_KEY=실제_Gemini_API_키
```

OpenAI 호환 키 하나를 양쪽에서 사용할 때는 다음 한 줄도 지원합니다.

```text
OPENAI_API_KEY=실제_OpenAI_호환_API_키
```

키는 `.kpr\config.json`에 저장되지 않으며 결과 파일에도 기록되지 않습니다.

## 5. 자주 쓰는 설정

### 로컬 Qwen 테스트 / Gemini 3.7 Judge

```bat
.venv\Scripts\python.exe -m korean_prompt_robustness configure ^
  --test local --test-model qwen2.5:14b ^
  --judge gemini --judge-model gemini-3.7-flash
```

### Gemini 3.6 테스트 / Gemini 3.7 Judge

```bat
.venv\Scripts\python.exe -m korean_prompt_robustness configure ^
  --test gemini --test-model gemini-3.6-flash ^
  --judge gemini --judge-model gemini-3.7-flash
```

이 조합은 `run_gemini_5_windows.bat`을 실행해도 됩니다.

### 테스트와 Judge 모두 로컬 Qwen

먼저 모델을 설치합니다.

```bat
ollama pull qwen2.5:14b
```

그런 다음 설정합니다.

```bat
.venv\Scripts\python.exe -m korean_prompt_robustness configure ^
  --test local --test-model qwen2.5:14b ^
  --judge local --judge-model qwen2.5:14b
```

이 조합은 `run_local_windows.bat`을 실행해도 됩니다.

### 로컬 테스트 / OpenAI 호환 Judge

아래의 모델 ID와 Base URL을 실제 제공업체의 값으로 바꾸세요.

```bat
.venv\Scripts\python.exe -m korean_prompt_robustness configure ^
  --test local --test-model qwen2.5:14b ^
  --judge openai-compatible ^
  --judge-model 실제-Judge-모델-ID ^
  --judge-base-url https://제공업체.example/v1
```

OpenAI 호환 방식은 Bearer 인증과 `POST /chat/completions` 형식을 지원하는
API에만 연결할 수 있습니다.

## 6. 설정 확인

```bat
.venv\Scripts\python.exe -m korean_prompt_robustness show-config
```

허용되는 방식은 `local`, `gemini`, `openai-compatible`뿐입니다. 이전
버전의 `api` 설정 오류가 나오면 `configure`를 다시 실행하세요.

## 7. 문제 파일과 실행

예제 문제 검증:

```bat
.venv\Scripts\python.exe -m korean_prompt_robustness validate data\examples\problems.jsonl
```

한 문제만 시험:

```bat
.venv\Scripts\python.exe -m korean_prompt_robustness run data\examples\problems.jsonl --limit 1
```

앞의 5문제 실행:

```bat
.venv\Scripts\python.exe -m korean_prompt_robustness run data\examples\problems.jsonl --limit 5
```

각 문제의 원문, 테스트 모델 답변, Judge 모델 답변이 순서대로 콘솔에
표시됩니다. 프로그램은 답변 JSONL, 점수, 보고서를 생성하지 않습니다.

## 8. 중단 및 다시 실행

실행 중 중단하려면 `Ctrl+C`를 누릅니다. 결과를 파일에 저장하지 않기 때문에
다시 실행하면 첫 문제부터 모델을 다시 호출합니다.

## 9. 오류 해결

### Python을 찾을 수 없음

Python 3.10 이상을 다시 설치하고 `Add Python to PATH`를 선택한 뒤
`install_windows.bat`을 다시 실행합니다.

### UnicodeDecodeError 또는 한글 깨짐

새 명령 프롬프트를 열고 배치 파일을 다시 실행하세요. 제공 배치 파일은
UTF-8 코드 페이지와 `PYTHONUTF8=1`을 자동 설정합니다.

### Gemini HTTP 404

현재 사용 가능한 모델 ID인지 확인하세요. 기본 모델은
`gemini-3.6-flash`이며 3.7은 `gemini-3.7-flash`로 명시할 수 있습니다.

### API HTTP 401 또는 403

`.env`의 키와 해당 모델 사용 권한을 확인하세요.

### 로컬 실행 파일을 찾을 수 없음

```bat
ollama --version
ollama list
```

Ollama가 PATH에 등록되어 있는지, 설정한 모델이 설치되어 있는지 확인하세요.

# Windows 설치 및 실행 가이드

이 문서는 Windows 10/11에서 저장소를 내려받아 설치하고, 테스트 모델과
Judge 모델을 설정한 뒤 문제를 실행하는 전체 과정을 설명합니다.

프로그램의 실행 흐름은 다음과 같습니다.

```text
문제 파일 → 테스트 모델 답변 → Judge 모델 답변 → 콘솔 출력
```

모델 답변은 파일로 저장하지 않습니다.

## 1. 설치 전 준비

필수:

- Windows 10 또는 Windows 11
- Python 3.10 이상

선택:

- Git으로 내려받으려면 Git for Windows
- 로컬 모델을 사용하려면 Ollama
- Gemini를 사용하려면 Gemini API 키
- OpenAI 호환 API를 사용하려면 해당 서비스의 API 키, 모델 ID, Base URL

### Python 확인

명령 프롬프트(CMD)나 PowerShell을 열고 다음 중 하나를 실행합니다.

```bat
py --version
```

또는:

```bat
python --version
```

`Python 3.10` 이상이 표시되어야 합니다. Python을 새로 설치한다면 설치
화면에서 `Add Python to PATH`를 선택하세요.

### Git 확인

Git 방식으로 설치할 때만 필요합니다.

```bat
git --version
```

Git을 찾을 수 없으면 Git for Windows를 설치하거나 아래의 ZIP 설치 방식을
사용하세요.

## 2. 프로그램 내려받기

Git과 ZIP 중 한 가지 방법만 선택하면 됩니다.

### 방법 A: Git clone

원하는 상위 폴더에서 다음을 실행합니다.

```bat
git clone https://github.com/jihoo567/22-R-E.git
cd 22-R-E
```

경로에 공백이나 한글이 있으면 따옴표를 사용합니다.

```bat
cd /d "C:\Users\사용자이름\Desktop\22기 R&E\22-R-E"
```

PowerShell에서는 다음처럼 이동할 수 있습니다.

```powershell
Set-Location "C:\Users\사용자이름\Desktop\22기 R&E\22-R-E"
```

### 방법 B: GitHub ZIP

1. [최신 GitHub 릴리스](https://github.com/jihoo567/22-R-E/releases/latest)를 엽니다.
2. `korean-prompt-robustness-windows-*.zip` 파일을 받습니다.
3. ZIP을 원하는 폴더에 완전히 압축 해제합니다.
4. 압축을 푼 폴더를 엽니다.

ZIP 내부 파일을 압축된 상태로 직접 실행하면 설치가 실패할 수 있습니다.
반드시 먼저 압축을 해제하세요.

## 3. 자동 설치

프로젝트 최상위 폴더에는 다음 파일이 있어야 합니다.

```text
install_windows.bat
pyproject.toml
README.md
WINDOWS_INSTALL.md
data\examples\problems.jsonl
```

`install_windows.bat`을 더블클릭하거나 터미널에서 실행합니다.

CMD:

```bat
install_windows.bat
```

PowerShell:

```powershell
.\install_windows.bat
```

설치 프로그램은 다음 작업을 수행합니다.

1. Python 3.10 이상 확인
2. 프로젝트 안에 `.venv` 가상환경 생성
3. 벤치마크 프로그램 설치
4. `.env`가 없으면 `.env.example`을 복사
5. 단위 테스트 실행

마지막에 다음 문구가 표시되면 설치가 완료된 것입니다.

```text
Installation completed successfully.
```

## 4. `kpr` 명령을 찾지 못하는 이유

설치 직후 새 터미널에서 다음 명령이 실패할 수 있습니다.

```bat
kpr --help
```

이것은 설치 실패가 아닐 수 있습니다. 프로그램은 Windows 전체가 아니라
프로젝트의 `.venv` 안에 설치되며, `install_windows.bat`이 종료되면 그
가상환경이 현재 터미널에 자동으로 유지되지 않습니다.

가장 확실한 실행 방법은 가상환경 안의 `kpr.exe`를 직접 사용하는 것입니다.

CMD:

```bat
.venv\Scripts\kpr.exe --help
```

PowerShell:

```powershell
.\.venv\Scripts\kpr.exe --help
```

아래 문서의 명령에서 CMD는 `.venv\Scripts\kpr.exe`, PowerShell은
`.\.venv\Scripts\kpr.exe`를 사용하면 됩니다.

### 가상환경을 활성화해서 `kpr`만 사용하기

CMD:

```bat
.venv\Scripts\activate.bat
kpr --help
```

PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
kpr --help
```

PowerShell 실행 정책 오류가 발생하면 활성화를 시도하지 말고
`.\.venv\Scripts\kpr.exe`를 직접 사용하세요.

### 설치 파일 확인

CMD:

```bat
dir .venv\Scripts\kpr.exe
```

PowerShell:

```powershell
Get-Item .\.venv\Scripts\kpr.exe
```

파일이 없다면 프로젝트 폴더에서 `install_windows.bat`을 다시 실행합니다.

## 5. 지원하는 모델 방식

테스트 모델과 Judge 모델은 각각 다음 세 방식 중 하나를 선택합니다.

| 설정값 | 설명 |
|---|---|
| `local` | Ollama 또는 stdin/stdout 기반 로컬 모델 |
| `gemini` | Google Gemini API |
| `openai-compatible` | OpenAI 호환 Chat Completions API |

실행 전에 두 모델을 `configure`로 반드시 설정해야 합니다. 설정하지 않으면
`run`은 모델을 호출하지 않고 중단됩니다.

## 6. API 키 입력

API 모델을 사용할 때만 필요합니다. 프로젝트 폴더의 `.env`를 메모장으로
엽니다.

```bat
notepad .env
```

### Gemini 키 하나를 사용

테스트와 Judge가 모두 Gemini이거나 Judge만 Gemini인 경우 다음처럼
입력할 수 있습니다.

```text
GEMINI_API_KEY=실제_Gemini_API_키
```

### 테스트와 Judge 키를 분리

```text
KPR_TEST_API_KEY=테스트_모델_API_키
KPR_JUDGE_API_KEY=Judge_모델_API_키
```

테스트 모델이 로컬이고 Judge가 Gemini라면 `KPR_TEST_API_KEY`는 사용되지
않습니다. 이 경우 `KPR_JUDGE_API_KEY` 또는 `GEMINI_API_KEY`에 Gemini 키를
넣어야 합니다.

### OpenAI 호환 공통 키

```text
OPENAI_API_KEY=OpenAI_호환_API_키
```

키를 입력할 때 주의하세요.

- `=` 뒤에 실제 키를 입력합니다.
- 키 앞뒤에 불필요한 공백을 넣지 않습니다.
- `.env.example`이 아니라 `.env`를 수정합니다.
- `.env`를 GitHub에 올리지 않습니다.
- API 키를 명령행 인자로 입력하지 않습니다.

프로그램은 API 키를 `.kpr\config.json`이나 출력 결과에 저장하지 않습니다.

## 7. 로컬 모델 준비

Ollama가 설치되어 있는지 확인합니다.

```bat
ollama --version
```

현재 설치된 모델 확인:

```bat
ollama list
```

출력의 `NAME`을 설정 명령에 정확히 사용합니다. 예를 들어 다음처럼
표시된다면 모델 이름은 `llama3.2:1b`입니다.

```text
NAME           ID
llama3.2:1b    baf6a787fdff
```

새 모델 설치 예시:

```bat
ollama pull llama3.2:1b
```

## 8. 모델 설정

### 로컬 Llama 테스트 / Gemini Judge

CMD:

```bat
.venv\Scripts\kpr.exe configure ^
  --test local --test-model llama3.2:1b ^
  --judge gemini --judge-model gemini-3.6-flash
```

PowerShell에서는 한 줄로 실행하는 것이 간단합니다.

```powershell
.\.venv\Scripts\kpr.exe configure --test local --test-model llama3.2:1b --judge gemini --judge-model gemini-3.6-flash
```

### Gemini 3.6 테스트 / Gemini 3.7 Judge

CMD:

```bat
.venv\Scripts\kpr.exe configure ^
  --test gemini --test-model gemini-3.6-flash ^
  --judge gemini --judge-model gemini-3.7-flash
```

예제 5문제를 이 조합으로 바로 실행하려면 `run_gemini_5_windows.bat`을
사용할 수도 있습니다.

### 테스트와 Judge 모두 같은 로컬 모델

```bat
.venv\Scripts\kpr.exe configure ^
  --test local --test-model llama3.2:1b ^
  --judge local --judge-model llama3.2:1b
```

`run_local_windows.bat`은 `qwen2.5:14b`를 사용하는 편의 파일입니다. 다른
로컬 모델을 사용할 때는 위처럼 직접 설정하세요.

### 테스트와 Judge가 서로 다른 로컬 모델

```bat
.venv\Scripts\kpr.exe configure ^
  --test local --test-model 테스트-모델-NAME ^
  --judge local --judge-model Judge-모델-NAME
```

### 로컬 테스트 / OpenAI 호환 Judge

모델 ID와 Base URL은 API 제공업체 문서의 실제 값으로 바꿔야 합니다.

```bat
.venv\Scripts\kpr.exe configure ^
  --test local --test-model llama3.2:1b ^
  --judge openai-compatible ^
  --judge-model 실제-Judge-모델-ID ^
  --judge-base-url https://제공업체.example/v1
```

OpenAI 호환 방식은 Bearer 인증, `POST /chat/completions`,
`choices[0].message.content` 형식을 지원하는 API에만 연결할 수 있습니다.

## 9. 설정 확인

CMD:

```bat
.venv\Scripts\kpr.exe show-config
```

PowerShell:

```powershell
.\.venv\Scripts\kpr.exe show-config
```

예전 버전의 `api` 설정이 남아 있다는 오류가 나오면 위의 `configure`
명령을 다시 실행하세요. 현재 허용되는 값은 `local`, `gemini`,
`openai-compatible`입니다.

## 10. 문제 파일 확인

기본 예제 문제 파일의 정확한 경로는 다음과 같습니다.

```text
data\examples\problems.jsonl
```

입력은 UTF-8 JSONL이며 한 줄에 문제 하나를 작성합니다.

```json
{"id":"problem-001","prompt":"대한민국의 수도는 어디인가요?"}
```

파일 검증:

```bat
.venv\Scripts\kpr.exe validate data\examples\problems.jsonl
```

정상이면 다음처럼 표시됩니다.

```text
검증 성공: 5개 문제
```

## 11. 실행

한 문제만 먼저 시험하는 것을 권장합니다.

```bat
.venv\Scripts\kpr.exe run data\examples\problems.jsonl --limit 1
```

앞의 5문제 실행:

```bat
.venv\Scripts\kpr.exe run data\examples\problems.jsonl --limit 5
```

전체 문제 실행:

```bat
.venv\Scripts\kpr.exe run data\examples\problems.jsonl
```

콘솔에는 문제별로 다음 내용이 순서대로 표시됩니다.

```text
[문제]
...

[테스트 모델 답변]
...

[Judge 모델 답변]
...
```

프로그램은 답변 JSONL, 점수 파일, CSV 보고서를 생성하지 않습니다. 실행을
중단하려면 `Ctrl+C`를 누릅니다. 다시 실행하면 첫 문제부터 호출합니다.

## 12. Git으로 받은 프로그램 업데이트

프로젝트 폴더에서 다음을 실행합니다.

```bat
git pull origin main
install_windows.bat
```

`install_windows.bat`은 기존 `.env`를 덮어쓰지 않습니다. 업데이트 후 CLI
사용법이 바뀌었다면 모델 설정을 다시 실행하세요.

## 13. 오류 해결

### `kpr`은 내부 또는 외부 명령이 아닙니다

```bat
.venv\Scripts\kpr.exe --help
```

PowerShell에서는:

```powershell
.\.venv\Scripts\kpr.exe --help
```

### `.venv\Scripts\kpr.exe`를 찾을 수 없습니다

현재 폴더에 `install_windows.bat`이 있는지 확인한 뒤 다시 실행합니다.

```bat
install_windows.bat
```

### `GEMINI_API_KEY` 또는 `KPR_JUDGE_API_KEY`가 없다는 오류

테스트 모델이 로컬이고 Judge가 Gemini라면 `.env`에 다음 중 하나가 있어야
합니다.

```text
GEMINI_API_KEY=실제키
```

또는:

```text
KPR_JUDGE_API_KEY=실제키
```

### Gemini HTTP 404

모델 ID를 확인합니다. 이 프로그램의 기본 Gemini 모델은
`gemini-3.6-flash`이며 `gemini-3.7-flash`도 명시적으로 선택할 수 있습니다.

### API HTTP 401 또는 403

API 키가 올바른지, 해당 키에 모델 접근 권한이 있는지 확인합니다.

### 로컬 모델을 찾을 수 없음

```bat
ollama list
```

설정의 모델 ID가 목록의 `NAME`과 완전히 같은지 확인합니다.

### 한글이 깨지거나 `UnicodeDecodeError`가 발생함

제공된 배치 파일은 UTF-8 코드 페이지와 `PYTHONUTF8=1`을 설정합니다. 새
CMD 창을 열고 프로젝트 폴더에서 다시 실행하세요. 직접 실행할 때는 다음을
먼저 입력할 수 있습니다.

```bat
chcp 65001
set PYTHONUTF8=1
```

PowerShell:

```powershell
$env:PYTHONUTF8="1"
```

### 호출이 오래 걸림

로컬 모델은 모델 크기와 컴퓨터 성능에 따라 오래 걸릴 수 있습니다. 먼저
`--limit 1`로 실행하고, 정상 작동을 확인한 뒤 문제 수를 늘리세요.

## 14. 설치 테스트 직접 실행

CMD:

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

PowerShell:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

모든 테스트가 `OK`로 끝나면 설치와 기본 실행 환경이 정상입니다.

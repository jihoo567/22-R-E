# Windows 자동 실행 안내

Windows 10/11에서 저장소를 받은 뒤 가상환경을 직접 만들거나 활성화할 필요는
없습니다. `kpr.bat`이 필요한 준비를 자동으로 수행합니다.

## 1. 준비물

- Python 3.10 이상
- Git으로 받을 경우 Git for Windows
- 로컬 모델을 사용할 경우 Ollama
- API 모델을 사용할 경우 API 키

버전을 확인합니다.

```powershell
py --version
git --version
```

Python을 새로 설치할 때는 `Add Python to PATH`를 선택하세요.

## 2. Git clone 후 바로 실행

```powershell
git clone https://github.com/jihoo567/22-R-E.git
Set-Location .\22-R-E
.\kpr.bat --help
```

첫 실행에는 `.venv` 생성과 프로그램 설치 때문에 시간이 조금 더 걸립니다.
이후 실행은 바로 시작되며, `git pull`로 코드가 바뀌면 자동으로 갱신됩니다.

## 3. 자동 준비 내용

`kpr.bat`은 공통 런처 `kpr.py`를 호출하고 다음을 수행합니다.

1. Python 버전 확인
2. `.venv` 자동 생성
3. 프로그램 자동 설치 또는 소스 변경 후 자동 갱신
4. `.env`가 없으면 `.env.example` 복사
5. `kpr-config.json`이 없으면 편집 가능한 설정 파일 생성
6. UTF-8 환경에서 실제 CLI 실행

가상환경 활성화 명령과 `.venv\Scripts\kpr.exe`는 사용하지 않아도 됩니다.
특히 한글 경로에서는 항상 저장소 루트의 `kpr.bat`을 사용하세요.

## 4. 로컬 모델 설정과 실행

Ollama와 모델을 확인합니다.

```powershell
ollama --version
ollama list
```

필요하면 모델을 받습니다.

```powershell
ollama pull qwen2.5:14b
```

첫 실행 때 생성된 설정 파일을 메모장으로 엽니다.

```powershell
notepad kpr-config.json
```

기본 파일은 테스트와 Judge 모두 `qwen2.5:14b`를 사용합니다. 다른 모델을
사용하려면 각 모델의 `model_id`와 `command`를 직접 수정한 뒤 실행합니다.
모든 설정 변수와 Local·Gemini·OpenAI 호환 API 예시는
[CONFIG_GUIDE.md](CONFIG_GUIDE.md)에 있습니다. 문서 경로는
`kpr.bat --help`에서도 확인할 수 있습니다.

```powershell
.\kpr.bat run data\examples\problems.jsonl --limit 1
```

## 5. Gemini Judge 사용

메모장으로 자동 생성된 `.env`를 엽니다.

```powershell
notepad .env
```

키를 입력하고 저장합니다.

```text
KPR_JUDGE_API_KEY=실제_Gemini_API_키
```

`kpr-config.json`의 `judge_model`을 다음처럼 직접 수정합니다.

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

저장한 뒤 실행합니다.

```powershell
.\kpr.bat run data\examples\problems.jsonl --limit 1
```

## 6. 문제 파일 확인

```powershell
.\kpr.bat validate data\examples\problems.jsonl
```

입력 파일은 UTF-8 JSONL이며 각 줄에 `id`와 `prompt`가 필요합니다.

```json
{"id":"problem-001","prompt":"대한민국의 수도는 어디인가요?"}
```

## 7. 업데이트

```powershell
git pull --ff-only origin main
.\kpr.bat --help
```

두 번째 명령이 변경된 소스를 감지해 자동으로 재설치합니다. `.env`와
`kpr-config.json`은 유지됩니다.

## 8. 문제 해결

### Python을 찾을 수 없음

```powershell
py --version
python --version
```

둘 다 실패하면 Python 3.10 이상을 설치한 뒤 PowerShell을 다시 여세요.

### 로컬 실행 파일을 찾을 수 없음

Ollama가 설치되고 실행 중인지 확인합니다.

```powershell
ollama --version
ollama list
```

### API 키가 없다고 표시됨

`.env.example`이 아니라 프로젝트 루트의 `.env`를 수정했는지 확인하세요.
API 키는 Git에 커밋하지 마세요.

### 가상환경이 손상됨

다른 `kpr` 프로세스를 종료한 다음 `.venv`만 삭제하고 다시 실행합니다.

```powershell
Remove-Item -Recurse -Force .\.venv
.\kpr.bat --help
```

### `Fatal Python error` 또는 `UnicodeDecodeError`

`.venv\Scripts\kpr.exe` 대신 저장소 루트의 다음 명령을 사용하세요.

```powershell
.\kpr.bat --help
```

`kpr.bat`은 UTF-8 환경과 공통 부트스트랩을 사용하므로 한글과 공백이 포함된
경로에서도 실행되도록 설계되어 있습니다.

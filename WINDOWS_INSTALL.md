# Windows 연구컴 설치 안내

## 준비물

- Windows 10 또는 11
- Python 3.10 이상
- Gemini API 사용 시 인터넷 연결과 Gemini API 키
- 로컬 LLM 사용 시 Ollama와 사용할 모델

## 설치

1. 배포 ZIP의 압축을 원하는 폴더에 풉니다.
2. `install_windows.bat`을 더블클릭합니다.
3. 설치가 끝나면 Mock 테스트 16개가 자동으로 실행됩니다.
4. Gemini를 사용하려면 메모장으로 `.env`를 열어 아래처럼 키를 입력합니다.

```text
GEMINI_API_KEY=실제-키
```

API 키는 `.env`에만 저장하고 다른 사람에게 전달할 ZIP이나 결과 폴더에는 넣지 마세요.

## 실행 파일

- `run_mock_windows.bat`: API 없이 전체 흐름 확인
- `run_gemini_5_windows.bat`: Gemini로 예제 5문제 생성 및 Gemini Judge 평가
- `run_local_windows.bat`: Ollama의 로컬 테스트 모델과 로컬 Judge 사용

로컬 실행 전 PowerShell 또는 명령 프롬프트에서 모델을 준비합니다.

```powershell
ollama pull gemma3:4b
ollama pull qwen3:8b
```

## 연구 데이터 사용

실제 JSONL 파일을 프로젝트의 `data` 폴더에 넣은 뒤 명령 프롬프트에서 실행합니다.

```bat
.venv\Scripts\kpr.exe validate --input data\my_kite_data.jsonl
.venv\Scripts\kpr.exe run-all --input data\my_kite_data.jsonl --config configs\gemini.json --run-id experiment-001
```

로컬 Judge를 사용하려면 두 번째 명령의 설정을 `configs\local_test_local_judge.json`으로 바꿉니다. 테스트 모델과 Judge의 종류는 설정 JSON의 `test_model.provider`와 `judge_model.provider`에서 서로 독립적으로 선택합니다.

## 중단 후 재실행

같은 명령과 같은 `--run-id`를 다시 실행하면 완료된 요청은 건너뛰고 중단된 항목부터 이어서 처리합니다. 실행 중 중단하려면 `Ctrl+C`를 누릅니다.

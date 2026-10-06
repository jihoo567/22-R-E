#!/usr/bin/env python3
"""저장소를 처음 받은 컴퓨터에서도 바로 실행되는 공통 런처.

프로젝트 전용 가상환경을 자동으로 만들고, 소스가 변경됐을 때만 패키지를
다시 설치한 다음 실제 CLI를 실행한다.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


MINIMUM_PYTHON = (3, 10)
PROJECT_ROOT = Path(__file__).resolve().parent
VENV_DIR = PROJECT_ROOT / ".venv"
STAMP_PATH = VENV_DIR / ".kpr-bootstrap.json"


def venv_python(root: Path = PROJECT_ROOT, platform: str = os.name) -> Path:
    """운영체제에 맞는 가상환경 Python 경로를 반환한다."""
    if platform == "nt":
        return root / ".venv" / "Scripts" / "python.exe"
    return root / ".venv" / "bin" / "python"


def project_fingerprint(root: Path = PROJECT_ROOT) -> str:
    """설치 결과에 영향을 주는 파일들의 지문을 계산한다."""
    files = [root / "pyproject.toml"]
    files.extend(sorted((root / "src").rglob("*.py")))

    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _runtime_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.setdefault("PYTHONUTF8", "1")
    environment.setdefault("PYTHONIOENCODING", "utf-8")
    environment.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")
    return environment


def _installed_fingerprint(stamp_path: Path = STAMP_PATH) -> str | None:
    try:
        data = json.loads(stamp_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    value = data.get("fingerprint")
    return value if isinstance(value, str) else None


def _write_stamp(fingerprint: str, stamp_path: Path = STAMP_PATH) -> None:
    temporary = stamp_path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {
                "fingerprint": fingerprint,
                "python": ".".join(str(part) for part in sys.version_info[:3]),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(stamp_path)


def ensure_environment(root: Path = PROJECT_ROOT) -> Path:
    """가상환경과 최신 프로젝트 설치를 준비하고 Python 경로를 반환한다."""
    if sys.version_info < MINIMUM_PYTHON:
        required = ".".join(str(part) for part in MINIMUM_PYTHON)
        current = ".".join(str(part) for part in sys.version_info[:3])
        raise RuntimeError(f"Python {required} 이상이 필요합니다. 현재 버전: {current}")

    python = venv_python(root)
    environment = _runtime_environment()
    if not python.is_file():
        print("[kpr] 전용 가상환경을 처음 한 번만 생성합니다...", file=sys.stderr)
        subprocess.run(
            [sys.executable, "-m", "venv", str(root / ".venv")],
            cwd=root,
            env=environment,
            check=True,
        )

    fingerprint = project_fingerprint(root)
    stamp = root / ".venv" / ".kpr-bootstrap.json"
    if _installed_fingerprint(stamp) != fingerprint:
        print("[kpr] 프로그램을 설치하거나 최신 상태로 갱신합니다...", file=sys.stderr)
        subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                str(root),
            ],
            cwd=root,
            env=environment,
            check=True,
        )
        _write_stamp(fingerprint, stamp)

    example = root / ".env.example"
    env_file = root / ".env"
    if example.is_file() and not env_file.exists():
        shutil.copyfile(example, env_file)

    config_file = root / "kpr-config.json"
    config_example = root / "kpr-config.example.json"
    if not config_file.exists() and config_example.is_file():
        shutil.copyfile(config_example, config_file)
        print(
            "[kpr] 편집 가능한 kpr-config.json을 만들었습니다.",
            file=sys.stderr,
        )
        print("[kpr] 설정 설명: CONFIG_GUIDE.md", file=sys.stderr)

    return python


def run(arguments: list[str]) -> int:
    python = ensure_environment()
    command = [str(python), "-m", "korean_prompt_robustness", *arguments]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=_runtime_environment(),
        check=False,
    )
    return completed.returncode


def main() -> int:
    try:
        return run(sys.argv[1:])
    except FileNotFoundError as error:
        print(f"[kpr] 필요한 실행 파일을 찾을 수 없습니다: {error.filename}", file=sys.stderr)
    except subprocess.CalledProcessError as error:
        print(f"[kpr] 자동 설치에 실패했습니다(종료 코드 {error.returncode}).", file=sys.stderr)
    except (OSError, RuntimeError) as error:
        print(f"[kpr] {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

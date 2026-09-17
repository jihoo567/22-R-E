"""두 API 제공자가 공유하는 JSON POST 통신."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


def post_json(
    url: str,
    body: dict[str, Any],
    headers: dict[str, str],
    *,
    timeout: float,
    label: str,
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        # 응답 본문에는 민감한 정보가 있을 수 있어 상태 코드만 표시합니다.
        raise RuntimeError(f"{label} HTTP 오류: {error.code}") from None
    except urllib.error.URLError:
        raise RuntimeError(f"{label} 연결 오류: 네트워크 연결을 확인하세요.") from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise RuntimeError(f"{label} 응답이 UTF-8 JSON이 아닙니다.") from None
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} 응답은 JSON 객체여야 합니다.")
    return value

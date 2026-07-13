from __future__ import annotations

from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import http_adapters


class _Response:
    def __init__(self, body: bytes, *, status: int = 200, content_type: str = "application/json") -> None:
        self.body = body
        self.status = status
        self.headers = {"content-type": content_type}

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def read(self, limit: int) -> bytes:
        return self.body[:limit]


def test_shared_http_adapters_keep_json_and_status_transport_behavior() -> None:
    requests: list[tuple[str, float]] = []

    def json_open(request: Any, timeout: float) -> _Response:
        requests.append((request.full_url, timeout))
        return _Response(b'{"ok": true}')

    json_result = http_adapters.json_request(
        "http://127.0.0.1:8080/health",
        timeout=2.0,
        urlopen=json_open,
        monotonic=iter([1.0, 1.01]).__next__,
    )
    status_result = http_adapters.status_request(
        "http://127.0.0.1:8080/ready",
        urlopen=lambda _request, timeout: _Response(b"ready", content_type="text/plain"),
        monotonic=iter([2.0, 2.02]).__next__,
    )

    assert requests == [("http://127.0.0.1:8080/health", 2.0)]
    assert json_result["json"] == {"ok": True}
    assert json_result["elapsed_ms"] == 10.0
    assert status_result["ok"] is True
    assert status_result["text_preview"] == "ready"

from __future__ import annotations

import json
import time
from typing import Any, Callable
import urllib.error
import urllib.request


MonotonicPort = Callable[[], float]


def json_request(
    url: str,
    timeout: float = 1.5,
    max_bytes: int = 262144,
    method: str = "GET",
    *,
    urlopen: Callable[..., Any] = urllib.request.urlopen,
    monotonic: MonotonicPort = time.monotonic,
) -> dict[str, Any]:
    started = monotonic()
    request = urllib.request.Request(url, headers={"Accept": "application/json"}, method=str(method or "GET").upper())
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(max_bytes + 1)
            truncated = len(raw) > max_bytes
            if truncated:
                raw = raw[:max_bytes]
            text = raw.decode("utf-8", errors="replace")
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                return {
                    "ok": False,
                    "url": url,
                    "status_code": getattr(response, "status", None),
                    "content_type": response.headers.get("content-type"),
                    "elapsed_ms": round((monotonic() - started) * 1000.0, 1),
                    "error": f"invalid JSON: {exc}",
                    "truncated": truncated,
                    "text_preview": text[:400],
                }
            return {
                "ok": True,
                "url": url,
                "status_code": getattr(response, "status", None),
                "content_type": response.headers.get("content-type"),
                "elapsed_ms": round((monotonic() - started) * 1000.0, 1),
                "truncated": truncated,
                "json": parsed,
            }
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "url": url,
            "status_code": exc.code,
            "elapsed_ms": round((monotonic() - started) * 1000.0, 1),
            "error": str(exc),
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "ok": False,
            "url": url,
            "elapsed_ms": round((monotonic() - started) * 1000.0, 1),
            "error": str(exc),
        }


def status_request(
    url: str,
    timeout: float = 1.5,
    max_bytes: int = 65536,
    method: str = "GET",
    *,
    urlopen: Callable[..., Any] = urllib.request.urlopen,
    monotonic: MonotonicPort = time.monotonic,
) -> dict[str, Any]:
    started = monotonic()
    request = urllib.request.Request(url, headers={"Accept": "*/*"}, method=str(method or "GET").upper())
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(max_bytes + 1)
            truncated = len(raw) > max_bytes
            if truncated:
                raw = raw[:max_bytes]
            text = raw.decode("utf-8", errors="replace")
            status_code = getattr(response, "status", None)
            return {
                "ok": bool(status_code is not None and 200 <= int(status_code) < 300),
                "url": url,
                "status_code": status_code,
                "content_type": response.headers.get("content-type"),
                "elapsed_ms": round((monotonic() - started) * 1000.0, 1),
                "truncated": truncated,
                "text_preview": text[:400],
            }
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "url": url,
            "status_code": exc.code,
            "elapsed_ms": round((monotonic() - started) * 1000.0, 1),
            "error": str(exc),
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "ok": False,
            "url": url,
            "elapsed_ms": round((monotonic() - started) * 1000.0, 1),
            "error": str(exc),
        }

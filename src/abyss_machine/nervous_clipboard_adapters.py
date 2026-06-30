from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Mapping


RunnerPort = Callable[..., dict[str, Any]]
CommandExistsPort = Callable[[str], bool]
SourceEnabledPort = Callable[[dict[str, Any], str], bool]
VirtualSourcePort = Callable[[str, dict[str, Any]], dict[str, Any]]
TextPayloadPort = Callable[..., dict[str, Any]]
PathExistsPort = Callable[[Path], bool]
NowIsoPort = Callable[[], str]


def wayland_clipboard_socket(
    *,
    environ: Mapping[str, str] | None = None,
    path_exists: PathExistsPort = Path.exists,
) -> tuple[Path | None, dict[str, Any]]:
    env = environ or os.environ
    runtime_dir = env.get("XDG_RUNTIME_DIR")
    wayland_display = env.get("WAYLAND_DISPLAY")
    wayland_socket = None
    if runtime_dir and wayland_display:
        display_path = Path(wayland_display)
        wayland_socket = display_path if display_path.is_absolute() else Path(runtime_dir) / wayland_display
    status = {
        "runtime_dir_present": bool(runtime_dir),
        "wayland_display_present": bool(wayland_display),
        "socket_path": str(wayland_socket) if wayland_socket else None,
        "socket_exists": bool(wayland_socket and path_exists(wayland_socket)),
    }
    return (wayland_socket if status["socket_exists"] else None), status


def clipboard_fact(
    *,
    sources: dict[str, Any],
    trigger: str | None = None,
    source_enabled: SourceEnabledPort,
    command_exists: CommandExistsPort,
    runner: RunnerPort,
    virtual_source: VirtualSourcePort,
    text_payload: TextPayloadPort,
    environ: Mapping[str, str] | None = None,
    path_exists: PathExistsPort = Path.exists,
    now_iso: NowIsoPort,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    source_id = "clipboard"
    if not source_enabled(sources, source_id):
        return None, {"source": source_id, "reason": "disabled_by_source_policy"}
    if not command_exists("wl-paste"):
        return {
            "name": "clipboard",
            "source_id": source_id,
            "ok": False,
            "observed_at": now_iso(),
            "sensitivity": "local_private_redacted",
            "error": "wl-paste not installed",
            "source": virtual_source(source_id, {"error": "wl-paste not installed"}),
        }, None

    _socket, socket_status = wayland_clipboard_socket(environ=environ, path_exists=path_exists)
    if not socket_status["socket_exists"]:
        return None, {
            "source": source_id,
            "reason": "wayland_clipboard_unavailable",
            "runtime_dir_present": socket_status["runtime_dir_present"],
            "wayland_display_present": socket_status["wayland_display_present"],
        }

    types_result = runner(["wl-paste", "--list-types"], timeout=1.5)
    mime_types = str(types_result.get("stdout") or "").splitlines() if types_result.get("ok") else []
    text_type = next((item for item in mime_types if item.startswith("text/") or item == "UTF8_STRING"), None)
    payload: dict[str, Any] = {"mime_types": mime_types[:20], "has_text": bool(text_type)}
    fact: dict[str, Any] = {
        "name": "clipboard",
        "source_id": source_id,
        "ok": bool(types_result.get("ok")),
        "observed_at": now_iso(),
        "sensitivity": "local_private_redacted",
        "summary": {
            "mime_types": len(mime_types),
            "has_text": bool(text_type),
            "text_captured": False,
            "binary_content_captured": False,
            "timer_capture": trigger == "timer",
            "backend": "wl-paste",
            "backend_quality": "usable_with_known_gnome_shell_log_noise",
        },
        "mime_types": mime_types[:20],
        "backend": {
            "tool": "wl-paste",
            "timer_capture": trigger == "timer",
            "quality": "usable_with_known_gnome_shell_log_noise",
            "policy": "capture_and_record_quality_do_not_silently_disable",
            "limitations": [
                "GNOME compositor does not support wl-paste watch/data-control on this session",
                "single clipboard reads can create GNOME Shell assertion log noise",
            ],
        },
    }
    if not types_result.get("ok") and any(
        marker in str(types_result.get("stderr") or "").lower()
        for marker in ("wayland", "compositor", "display", "socket")
    ):
        return None, {
            "source": source_id,
            "reason": "wayland_clipboard_unavailable",
            "stderr": str(types_result.get("stderr") or "")[:240],
        }
    if text_type:
        text_result = runner(["wl-paste", "--no-newline"], timeout=1.5)
        if text_result.get("ok"):
            redacted = text_payload(str(text_result.get("stdout") or ""), max_chars=8000)
            payload["text"] = redacted
            fact["text"] = redacted["text"]
            fact["text_sha256"] = redacted["text_sha256"]
            fact["text_length"] = redacted["text_length"]
            fact["redaction"] = redacted["redaction"]
            fact["summary"]["text_captured"] = True
        else:
            fact["error"] = str(text_result.get("stderr") or "")[:400]
    elif not types_result.get("ok"):
        fact["error"] = str(types_result.get("stderr") or "")[:400]
    fact["source"] = virtual_source(source_id, payload)
    return fact, None

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli
from abyss_machine import nervous_clipboard_adapters as adapters


def fake_text_payload(text: str, max_chars: int = 8000) -> dict[str, Any]:
    clipped = text[:max_chars]
    return {
        "text": clipped,
        "text_sha256": f"sha:{len(clipped)}",
        "text_length": len(text),
        "redaction": {"matches": 0, "classes": []},
    }


def test_clipboard_fact_respects_source_policy_before_live_ports() -> None:
    fact, error = adapters.clipboard_fact(
        sources={"clipboard": {"enabled": False}},
        source_enabled=lambda _sources, _source_id: False,
        command_exists=lambda _name: (_ for _ in ()).throw(AssertionError("should not check commands")),
        runner=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not run")),
        virtual_source=lambda source_id, payload: {"source_id": source_id, "payload": payload},
        text_payload=fake_text_payload,
        now_iso=lambda: "2026-06-30T03:20:00+00:00",
    )

    assert fact is None
    assert error == {"source": "clipboard", "reason": "disabled_by_source_policy"}


def test_clipboard_fact_reports_missing_wl_paste_as_public_safe_fact() -> None:
    fact, error = adapters.clipboard_fact(
        sources={"clipboard": {"enabled": True}},
        source_enabled=lambda _sources, _source_id: True,
        command_exists=lambda name: name != "wl-paste",
        runner=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not run")),
        virtual_source=lambda source_id, payload: {"source_id": source_id, "payload": payload},
        text_payload=fake_text_payload,
        now_iso=lambda: "2026-06-30T03:20:00+00:00",
    )

    assert error is None
    assert fact is not None
    assert fact["ok"] is False
    assert fact["error"] == "wl-paste not installed"
    assert fact["source"] == {"source_id": "clipboard", "payload": {"error": "wl-paste not installed"}}


def test_clipboard_fact_skips_when_wayland_socket_is_absent() -> None:
    fact, error = adapters.clipboard_fact(
        sources={"clipboard": {"enabled": True}},
        source_enabled=lambda _sources, _source_id: True,
        command_exists=lambda name: name == "wl-paste",
        runner=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not run")),
        virtual_source=lambda source_id, payload: {"source_id": source_id, "payload": payload},
        text_payload=fake_text_payload,
        environ={"XDG_RUNTIME_DIR": "/run/user/1000", "WAYLAND_DISPLAY": "wayland-1"},
        path_exists=lambda _path: False,
        now_iso=lambda: "2026-06-30T03:20:00+00:00",
    )

    assert fact is None
    assert error is not None
    assert error["reason"] == "wayland_clipboard_unavailable"
    assert error["runtime_dir_present"] is True
    assert error["wayland_display_present"] is True


def test_clipboard_fact_captures_text_through_fake_wl_paste_ports() -> None:
    calls: list[list[str]] = []

    def runner(cmd, timeout=None):
        calls.append(cmd)
        if cmd == ["wl-paste", "--list-types"]:
            return {"ok": True, "returncode": 0, "stdout": "image/png\ntext/plain\n", "stderr": ""}
        assert cmd == ["wl-paste", "--no-newline"]
        return {"ok": True, "returncode": 0, "stdout": "redacted clipboard text", "stderr": ""}

    fact, error = adapters.clipboard_fact(
        sources={"clipboard": {"enabled": True}},
        trigger="timer",
        source_enabled=lambda _sources, _source_id: True,
        command_exists=lambda name: name == "wl-paste",
        runner=runner,
        virtual_source=lambda source_id, payload: {"source_id": source_id, "payload": payload},
        text_payload=fake_text_payload,
        environ={"XDG_RUNTIME_DIR": "/run/user/1000", "WAYLAND_DISPLAY": "wayland-1"},
        path_exists=lambda path: path == Path("/run/user/1000/wayland-1"),
        now_iso=lambda: "2026-06-30T03:20:00+00:00",
    )

    assert error is None
    assert fact is not None
    assert calls == [["wl-paste", "--list-types"], ["wl-paste", "--no-newline"]]
    assert fact["ok"] is True
    assert fact["summary"]["timer_capture"] is True
    assert fact["summary"]["has_text"] is True
    assert fact["summary"]["text_captured"] is True
    assert fact["summary"]["binary_content_captured"] is False
    assert fact["text"] == "redacted clipboard text"
    assert fact["text_sha256"] == "sha:23"
    assert fact["source"]["payload"]["has_text"] is True
    assert fact["source"]["payload"]["text"]["text"] == "redacted clipboard text"


def test_clipboard_fact_converts_wayland_backend_failure_to_skip() -> None:
    calls: list[list[str]] = []

    def runner(cmd, timeout=None):
        calls.append(cmd)
        return {"ok": False, "returncode": 1, "stdout": "", "stderr": "Compositor does not support the wl_data_control protocol"}

    fact, error = adapters.clipboard_fact(
        sources={"clipboard": {"enabled": True}},
        source_enabled=lambda _sources, _source_id: True,
        command_exists=lambda name: name == "wl-paste",
        runner=runner,
        virtual_source=lambda source_id, payload: {"source_id": source_id, "payload": payload},
        text_payload=fake_text_payload,
        environ={"XDG_RUNTIME_DIR": "/run/user/1000", "WAYLAND_DISPLAY": "wayland-1"},
        path_exists=lambda _path: True,
        now_iso=lambda: "2026-06-30T03:20:00+00:00",
    )

    assert fact is None
    assert error is not None
    assert error["reason"] == "wayland_clipboard_unavailable"
    assert calls == [["wl-paste", "--list-types"]]


def test_cli_clipboard_fact_binds_adapter_ports(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_clipboard_fact(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "name": "clipboard"}, None

    monkeypatch.setattr(cli.nervous_clipboard_adapters, "clipboard_fact", fake_clipboard_fact)

    fact, error = cli.nervous_clipboard_fact({"clipboard": {"enabled": True}}, "manual")

    assert fact == {"ok": True, "name": "clipboard"}
    assert error is None
    assert captured["source_enabled"] is cli.nervous_source_enabled
    assert captured["command_exists"] is cli.command_exists
    assert captured["runner"] is cli.run
    assert captured["virtual_source"] is cli.nervous_virtual_source
    assert captured["text_payload"] is cli.nervous_text_payload
    assert captured["environ"] is cli.os.environ
    assert captured["now_iso"] is cli.now_iso

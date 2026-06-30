from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli
from abyss_machine import nervous_screenshot_adapters as adapters


def test_extension_status_uses_stable_locale_and_enabled_list() -> None:
    calls: list[tuple[list[str], dict[str, str]]] = []

    def runner(cmd, timeout=None, env=None):
        calls.append((cmd, dict(env or {})))
        if cmd[:2] == ["gnome-extensions", "info"]:
            return {"ok": True, "returncode": 0, "stdout": "State: ACTIVE\nEnabled: No\n", "stderr": ""}
        return {"ok": True, "returncode": 0, "stdout": "allow-gnome-screenshot@siddh.me\n", "stderr": ""}

    data = adapters.gnome_screenshot_extension_status(
        command_exists=lambda name: name == "gnome-extensions",
        runner=runner,
        environ={"LANG": "ru_RU.UTF-8"},
    )

    assert data["active"] is True
    assert data["reason"] == "active"
    assert data["enabled_list_contains"] is True
    assert calls[0][1]["LC_ALL"] == "C.UTF-8"
    assert calls[0][1]["LANGUAGE"] == "C"


def test_x11_active_window_info_uses_fake_ports_and_process_classifier() -> None:
    def runner(cmd, timeout=None):
        if cmd[:2] == ["xprop", "-root"]:
            return {
                "ok": True,
                "returncode": 0,
                "stdout": "_NET_ACTIVE_WINDOW(WINDOW): window id # 0x4200001\n_NET_CLIENT_LIST_STACKING(WINDOW): 0x1, 0x4200001\n",
                "stderr": "",
            }
        assert cmd[:3] == ["xprop", "-id", "0x4200001"]
        return {
            "ok": True,
            "returncode": 0,
            "stdout": 'WM_CLASS(STRING) = "steam", "Steam"\n_NET_WM_NAME(UTF8_STRING) = "Dragon Age Origins"\n_NET_WM_STATE(ATOM) = _NET_WM_STATE_FULLSCREEN\n_NET_WM_PID(CARDINAL) = 123\n',
            "stderr": "",
        }

    data = adapters.x11_active_window_info(
        environ={"DISPLAY": ":0"},
        command_exists=lambda name: name == "xprop",
        runner=runner,
        process_info=lambda pid: {"pid": pid, "comm": "DAOrigins.exe", "cmdline": "/games/Dragon Age/DAOrigins.exe", "cwd": "/games", "exe": "/games/DAOrigins.exe"},
        game_role=lambda *_args: "active_game",
        workload_hint=lambda *_args: "game",
        text_haystack=lambda *parts: " ".join(str(part or "") for part in parts).lower(),
        strong_game_signal=lambda text: "dragon age" in text or "daorigins" in text or "steam" in text,
    )

    assert data["ok"] is True
    assert data["window_id"] == "0x4200001"
    assert data["fullscreen"] is True
    assert data["game_like"] is True
    assert data["process"]["pid"] == 123
    assert data["process"]["game_role"] == "active_game"


def test_screenshot_fact_executes_game_safe_plan_with_fake_ports(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    now = dt.datetime(2026, 6, 29, 20, 45, 30, tzinfo=dt.timezone.utc)

    def runner(cmd, timeout=None):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"fake png bytes")
        return {"ok": True, "returncode": 0, "stdout": "", "stderr": ""}

    fact, error = adapters.screenshot_fact(
        sources={"screenshots": {"enabled": True}},
        trigger="timer",
        screenshot_root=tmp_path / "screenshots",
        source_enabled=lambda sources, source_id: bool(sources[source_id]["enabled"]),
        virtual_source=lambda source_id, payload: {"source_id": source_id, "payload_ok": payload["ok"]},
        file_source=lambda path: {"path": str(path), "stat": {"size_bytes": path.stat().st_size}},
        command_exists=lambda name: name == "magick",
        runner=runner,
        process_game_guard=lambda: {"ok": True, "active": True, "summary": {"gamemode_global_active": True}},
        active_x11_info=lambda: {"ok": True, "window_id": "0x4200001", "game_like": True},
        x11_game_window_risk=lambda _game_guard: {"ok": True, "risk": False, "windows": []},
        extension_status_reader=lambda: (_ for _ in ()).throw(AssertionError("timer should use extension query skip status")),
        environ={},
        now=lambda: now,
        now_iso=lambda: "2026-06-29T20:45:30+00:00",
    )

    assert error is None
    assert fact is not None
    assert fact["ok"] is True
    assert fact["summary"]["captured"] is True
    assert fact["summary"]["capture_tool"] == "imagemagick-x11-active-window-game-safe"
    assert fact["summary"]["game_safe_capture"] is True
    assert fact["summary"]["operator_visible"] is False
    assert calls == [["magick", "x:0x4200001", str(tmp_path / "screenshots" / "2026" / "06" / "2026-06-29T204530+0000.png")]]
    assert fact["source"] == {"source_id": "screenshots", "payload_ok": True}


def test_screenshot_fact_skips_without_silent_backend_and_never_runs_noisy_tool(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    fact, error = adapters.screenshot_fact(
        sources={"screenshots": {"enabled": True}},
        trigger="timer",
        screenshot_root=tmp_path / "screenshots",
        source_enabled=lambda sources, source_id: bool(sources[source_id]["enabled"]),
        virtual_source=lambda source_id, payload: {"source_id": source_id, "payload": payload},
        file_source=lambda path: {"path": str(path)},
        command_exists=lambda _name: False,
        runner=lambda cmd, timeout=None: calls.append(cmd) or {"ok": False, "returncode": 1, "stdout": "", "stderr": "should not run"},
        process_game_guard=lambda: {"ok": True, "active": False, "summary": {}},
        active_x11_info=lambda: {"ok": False, "reason": "x11_unavailable_or_xprop_missing"},
        x11_game_window_risk=lambda _game_guard: {"ok": False, "risk": False, "reason": "x11_unavailable_or_xprop_missing"},
        extension_status_reader=lambda: {"uuid": "allow-gnome-screenshot@siddh.me", "active": False, "reason": "missing"},
        environ={},
        now=lambda: dt.datetime(2026, 6, 29, 20, 45, tzinfo=dt.timezone.utc),
        now_iso=lambda: "2026-06-29T20:45:00+00:00",
    )

    assert fact is None
    assert error is not None
    assert error["reason"] == "screenshot_silent_backend_unavailable"
    assert error["operator_visible_capture_avoided"] is True
    assert calls == []
    assert any(item["tool"] == "gnome-screenshot" and item["skipped"] for item in error["attempts"])


def test_cli_screenshot_fact_binds_adapter_ports(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_screenshot_fact(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "name": "screenshot"}, None

    monkeypatch.setattr(cli.nervous_screenshot_adapters, "screenshot_fact", fake_screenshot_fact)

    fact, error = cli.nervous_screenshot_fact({"screenshots": {"enabled": True}}, "manual")

    assert fact == {"ok": True, "name": "screenshot"}
    assert error is None
    assert captured["screenshot_root"] == cli.NERVOUS_SCREENSHOT_ROOT
    assert captured["source_enabled"] is cli.nervous_source_enabled
    assert captured["virtual_source"] is cli.nervous_virtual_source
    assert captured["command_exists"] is cli.command_exists
    assert captured["runner"] is cli.run
    assert captured["active_x11_info"] is cli.nervous_x11_active_window_info
    assert captured["x11_game_window_risk"] is cli.nervous_x11_game_window_risk_info

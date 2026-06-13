from __future__ import annotations

import pytest


pytestmark = [pytest.mark.quick, pytest.mark.contract]


def test_active_game_screenshot_skips_gnome_shell_backend(monkeypatch, tmp_path, abyss_machine_module) -> None:
    screenshot_root = tmp_path / "screenshots"
    monkeypatch.setattr(abyss_machine_module, "NERVOUS_SCREENSHOT_ROOT", screenshot_root)
    monkeypatch.setattr(abyss_machine_module, "nervous_source_enabled", lambda _sources, _source_id: True)
    monkeypatch.setattr(
        abyss_machine_module,
        "nervous_gnome_screenshot_extension_status",
        lambda: {"active": True, "reason": "active"},
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "process_game_guard",
        lambda write_latest=True: {"ok": True, "active": True, "summary": {"active_game_processes": 1}},
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "nervous_x11_active_window_info",
        lambda: {
            "ok": True,
            "window_id": "0x4200001",
            "fullscreen": True,
            "game_like": True,
            "summary": "WM_NAME = \"Dragon Age Origins\"",
        },
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "nervous_x11_game_window_risk_info",
        lambda _game_guard: {"ok": True, "risk": True, "reason": "x11_game_window_risk", "windows": [{"window_id": "0x4200001"}]},
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "command_exists",
        lambda name: name in {"magick", "grim", "gdbus", "gnome-screenshot"},
    )
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], timeout: float = 3.0, env=None):
        calls.append(cmd)
        if cmd[0] == "magick":
            # The implementation passes the actual generated path as the final arg.
            target = abyss_machine_module.Path(cmd[-1])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"\x89PNG\r\n\x1a\n")
            return {"ok": True, "returncode": 0, "stdout": "", "stderr": ""}
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(abyss_machine_module, "run", fake_run)

    fact, skip = abyss_machine_module.nervous_screenshot_fact({}, "timer")

    assert skip is None
    assert fact is not None
    assert fact["summary"]["captured"] is True
    assert fact["summary"]["game_safe_capture"] is True
    assert fact["summary"]["capture_tool"] == "imagemagick-x11-active-window-game-safe"
    assert calls == [["magick", "x:0x4200001", fact["artifact"]["path"]]]
    assert all("__abyss_internal_gnome_shell_screenshot_allowlisted_bus__" not in call for call in calls)
    assert any(
        item["tool"] == "gnome-shell-screenshot-allowlisted-bus-silent"
        and item["skipped"]
        and item["reason"] == "skipped_for_game_safe_capture_to_avoid_fullscreen_minimize"
        for item in fact["attempts"]
    )


def test_x11_game_window_risk_skips_gnome_shell_backend(monkeypatch, tmp_path, abyss_machine_module) -> None:
    screenshot_root = tmp_path / "screenshots"
    monkeypatch.setattr(abyss_machine_module, "NERVOUS_SCREENSHOT_ROOT", screenshot_root)
    monkeypatch.setattr(abyss_machine_module, "nervous_source_enabled", lambda _sources, _source_id: True)
    monkeypatch.setattr(
        abyss_machine_module,
        "nervous_gnome_screenshot_extension_status",
        lambda: {"active": True, "reason": "active"},
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "process_game_guard",
        lambda write_latest=True: {
            "ok": True,
            "active": False,
            "platform_present": True,
            "summary": {"active_game_processes": 0, "game_platform_processes": 1},
        },
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "nervous_x11_active_window_info",
        lambda: {
            "ok": True,
            "window_id": "0x2600040",
            "fullscreen": False,
            "game_like": False,
            "summary": "WM_CLASS(STRING) = \"steamwebhelper\", \"steam\"",
        },
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "nervous_x11_game_window_risk_info",
        lambda _game_guard: {
            "ok": True,
            "risk": True,
            "reason": "x11_game_window_risk",
            "windows": [
                {
                    "window_id": "0x7700007",
                    "active": False,
                    "fullscreen": True,
                    "game_like": True,
                    "summary": "WM_CLASS(STRING) = \"DAOrigins.exe\", \"steam_app_47810\"",
                }
            ],
        },
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "command_exists",
        lambda name: name in {"magick", "grim", "gdbus", "gnome-screenshot"},
    )
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], timeout: float = 3.0, env=None):
        calls.append(cmd)
        if cmd[0] == "magick":
            target = abyss_machine_module.Path(cmd[-1])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"\x89PNG\r\n\x1a\n")
            return {"ok": True, "returncode": 0, "stdout": "", "stderr": ""}
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(abyss_machine_module, "run", fake_run)

    fact, skip = abyss_machine_module.nervous_screenshot_fact({}, "timer")

    assert skip is None
    assert fact is not None
    assert fact["summary"]["captured"] is True
    assert fact["summary"]["game_safe_capture"] is True
    assert fact["summary"]["game_safe_reason"] == "x11_game_window_risk"
    assert fact["summary"]["x11_game_window_risk"] is True
    assert fact["summary"]["capture_tool"] == "imagemagick-x11-active-window-game-safe"
    assert calls == [["magick", "x:0x7700007", fact["artifact"]["path"]]]
    assert all("__abyss_internal_gnome_shell_screenshot_allowlisted_bus__" not in call for call in calls)
    assert any(
        item["tool"] == "gnome-shell-screenshot-allowlisted-bus-silent"
        and item["skipped"]
        and item["reason"] == "skipped_for_game_safe_capture_to_avoid_fullscreen_minimize"
        for item in fact["attempts"]
    )

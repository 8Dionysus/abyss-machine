from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine.nervous_screenshot import (  # noqa: E402
    ALLOW_EXTENSION_UUID,
    ALLOWLISTED_BUS_MARKER,
    capture_plan,
    extension_query_skip_status,
)


def test_recurring_screenshot_extension_query_skip_status_is_module_owned() -> None:
    status = extension_query_skip_status("timer", query_extensions_on_timer=False)

    assert status is not None
    assert status["uuid"] == ALLOW_EXTENSION_UUID
    assert status["active"] is False
    assert status["reason"] == "not_queried_for_recurring_timer"
    assert status["policy"]["direct_gnome_extensions_client_created"] is False
    assert extension_query_skip_status("manual", query_extensions_on_timer=False) is None


def test_game_safe_screenshot_plan_prefers_x11_magick_and_skips_gnome_shell() -> None:
    plan = capture_plan(
        trigger="timer",
        path="/tmp/screenshot.png",
        extension_status={"active": True, "reason": "active"},
        command_available={"magick": True, "grim": True, "gdbus": True, "gnome-screenshot": True},
        allow_interactive=False,
        allow_noisy=False,
        allow_shell_dbus=False,
        game_guard={"ok": True, "active": True, "summary": {"active_game_processes": 1}},
        active_x11={"ok": True, "window_id": "0x4200001", "game_like": True},
        x11_game_window_risk={"ok": True, "risk": True, "reason": "x11_game_window_risk", "windows": [{"window_id": "0x4200001"}]},
    )

    assert plan["game_safe_capture"] is True
    assert plan["game_safe_reason"] == "game_guard_active"
    assert plan["commands"][0] == {
        "tool": "imagemagick-x11-active-window-game-safe",
        "argv": ["magick", "x:0x4200001", "/tmp/screenshot.png"],
        "timeout": 6.0,
    }
    assert all(command["argv"][0] != ALLOWLISTED_BUS_MARKER for command in plan["commands"])
    assert any(
        attempt["tool"] == "gnome-shell-screenshot-allowlisted-bus-silent"
        and attempt["skipped"] is True
        and attempt["reason"] == "skipped_for_game_safe_capture_to_avoid_fullscreen_minimize"
        for attempt in plan["attempts"]
    )


def test_non_game_silent_screenshot_plan_preserves_privacy_defaults() -> None:
    plan = capture_plan(
        trigger="manual",
        path="/tmp/screenshot.png",
        extension_status={"active": True, "reason": "active"},
        command_available={"magick": True, "grim": True, "gdbus": True, "gnome-screenshot": True},
        allow_interactive=False,
        allow_noisy=False,
        allow_shell_dbus=False,
        game_guard={"ok": True, "active": False, "summary": {"active_game_processes": 0}},
        active_x11={"ok": True, "window_id": "0x123", "game_like": False},
        x11_game_window_risk={"ok": True, "risk": False, "reason": "no_x11_game_window_risk", "windows": []},
    )

    assert plan["game_safe_capture"] is False
    assert plan["commands"][0] == {
        "tool": "gnome-shell-screenshot-allowlisted-bus-silent",
        "argv": [ALLOWLISTED_BUS_MARKER, "/tmp/screenshot.png"],
        "timeout": 6.0,
    }
    assert any(
        attempt["tool"] == "gnome-screenshot"
        and attempt["skipped"] is True
        and attempt["reason"] == "noisy_or_operator_visible_backend_disabled_by_default"
        for attempt in plan["attempts"]
    )
    assert any(
        attempt["tool"] == "gnome-shell-screenshot-dbus"
        and attempt["skipped"] is True
        and attempt["reason"] == "disabled_by_default_requires_ABYSS_NERVOUS_ALLOW_SHELL_SCREENSHOT_DBUS"
        for attempt in plan["attempts"]
    )

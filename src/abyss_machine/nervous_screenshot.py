from __future__ import annotations

from typing import Any, Mapping


ALLOW_EXTENSION_UUID = "allow-gnome-screenshot@siddh.me"
RECURRING_TRIGGERS = {"timer", "typing_nervous_refresh"}
ALLOWLISTED_BUS_MARKER = "__abyss_internal_gnome_shell_screenshot_allowlisted_bus__"


def extension_query_skip_status(trigger: str, query_extensions_on_timer: bool) -> dict[str, Any] | None:
    if trigger not in RECURRING_TRIGGERS or query_extensions_on_timer:
        return None
    return {
        "uuid": ALLOW_EXTENSION_UUID,
        "active": False,
        "reason": "not_queried_for_recurring_timer",
        "query_skipped": True,
        "policy": {
            "direct_gnome_extensions_client_created": False,
            "manual_query_override_env": "ABYSS_NERVOUS_QUERY_GNOME_EXTENSIONS_ON_TIMER=1",
        },
    }


def capture_plan(
    *,
    trigger: str,
    path: str,
    extension_status: Mapping[str, Any],
    command_available: Mapping[str, bool],
    allow_interactive: bool,
    allow_noisy: bool,
    allow_shell_dbus: bool,
    game_guard: Mapping[str, Any],
    active_x11: Mapping[str, Any],
    x11_game_window_risk: Mapping[str, Any],
) -> dict[str, Any]:
    extension_active = bool(extension_status.get("active"))
    risk_windows = x11_game_window_risk.get("windows") if isinstance(x11_game_window_risk.get("windows"), list) else []
    risk_window_id = str(risk_windows[0].get("window_id")) if risk_windows and isinstance(risk_windows[0], dict) and risk_windows[0].get("window_id") else None
    active_game = bool(game_guard.get("active") or _nested_get(game_guard, ["summary", "gamemode_global_active"]))
    active_x11_game_window = bool(active_x11.get("game_like"))
    x11_risk = bool(x11_game_window_risk.get("risk"))
    game_safe_capture = active_game or active_x11_game_window or x11_risk
    if active_game:
        game_safe_reason = "game_guard_active"
    elif active_x11_game_window:
        game_safe_reason = "active_x11_game_window"
    elif x11_risk:
        game_safe_reason = str(x11_game_window_risk.get("reason") or "x11_game_window_risk")
    else:
        game_safe_reason = None
    active_window_id = str(active_x11.get("window_id")) if active_x11.get("window_id") else None
    game_window_id = active_window_id if active_x11.get("game_like") else (risk_window_id or active_window_id)

    commands: list[dict[str, Any]] = []
    if game_safe_capture and command_available.get("magick") and game_window_id:
        commands.append({
            "tool": "imagemagick-x11-active-window-game-safe",
            "argv": ["magick", f"x:{game_window_id}", path],
            "timeout": 6.0,
        })
    if game_safe_capture and command_available.get("magick"):
        commands.append({"tool": "imagemagick-x11-root-game-safe", "argv": ["magick", "x:root", path], "timeout": 6.0})
    if extension_active and not game_safe_capture:
        commands.append({
            "tool": "gnome-shell-screenshot-allowlisted-bus-silent",
            "argv": [ALLOWLISTED_BUS_MARKER, path],
            "timeout": 6.0,
        })
    if command_available.get("grim"):
        commands.append({"tool": "grim-silent", "argv": ["grim", path], "timeout": 10.0})

    dbus_skipped_reason = None
    if command_available.get("gdbus") and not game_safe_capture:
        if allow_shell_dbus:
            commands.append({
                "tool": "gnome-shell-screenshot-dbus-silent-opt-in",
                "argv": [
                    "gdbus",
                    "call",
                    "--session",
                    "--dest",
                    "org.gnome.Shell.Screenshot",
                    "--object-path",
                    "/org/gnome/Shell/Screenshot",
                    "--method",
                    "org.gnome.Shell.Screenshot.Screenshot",
                    "false",
                    "false",
                    path,
                ],
                "timeout": 4.0,
            })
        else:
            dbus_skipped_reason = "disabled_by_default_requires_ABYSS_NERVOUS_ALLOW_SHELL_SCREENSHOT_DBUS"
    if command_available.get("gnome-screenshot") and (allow_noisy or allow_interactive):
        tool_name = "gnome-screenshot-noisy-explicit-opt-in" if allow_noisy else "gnome-screenshot-interactive-opt-in"
        if not game_safe_capture:
            commands.append({"tool": tool_name, "argv": ["gnome-screenshot", "-f", path], "timeout": 6.0})

    attempts: list[dict[str, Any]] = [{
        "tool": "allow-gnome-screenshot-extension",
        "ok": extension_active,
        "skipped": False,
        "status": dict(extension_status),
        "automatic_backend_allowed": bool(extension_active and not game_safe_capture),
        "reason": (
            "skipped_for_game_safe_capture"
            if extension_active and game_safe_capture
            else ("enables_gnome_shell_silent_allowlisted_bus" if extension_active else "extension_not_active")
        ),
    }]
    attempts.append({
        "tool": "game-safe-screenshot-route",
        "ok": game_safe_capture,
        "skipped": not game_safe_capture,
        "reason": game_safe_reason or "no_active_game_or_x11_game_window_risk",
        "game_guard": {
            "ok": game_guard.get("ok"),
            "active": game_guard.get("active"),
            "summary": game_guard.get("summary"),
        },
        "active_x11": dict(active_x11),
        "x11_game_window_risk": dict(x11_game_window_risk),
        "policy": "active games or X11 game-window risk skip GNOME Shell screenshot backends; try non-focus X11/Xwayland capture first, then grim, then skip",
    })
    if game_safe_capture:
        attempts.append({
            "tool": "gnome-shell-screenshot-allowlisted-bus-silent",
            "ok": False,
            "skipped": True,
            "reason": "skipped_for_game_safe_capture_to_avoid_fullscreen_minimize",
            "extension_active": extension_active,
        })
    if not allow_noisy and not allow_interactive:
        attempts.append({
            "tool": "gnome-screenshot",
            "ok": False,
            "skipped": True,
            "reason": "noisy_or_operator_visible_backend_disabled_by_default",
            "required_env": "ABYSS_NERVOUS_ALLOW_NOISY_SCREENSHOT=1",
        })
    elif allow_interactive and not extension_active:
        attempts.append({
            "tool": "gnome-screenshot",
            "ok": False,
            "skipped": False,
            "reason": "interactive_opt_in_without_allow_extension",
        })
    else:
        attempts.append({
            "tool": "gnome-screenshot",
            "ok": None,
            "skipped": False,
            "reason": "explicit_noisy_or_interactive_opt_in",
        })
    if dbus_skipped_reason:
        attempts.append({
            "tool": "gnome-shell-screenshot-dbus",
            "ok": False,
            "skipped": True,
            "reason": dbus_skipped_reason,
        })

    return {
        "commands": commands,
        "attempts": attempts,
        "game_safe_capture": game_safe_capture,
        "game_safe_reason": game_safe_reason,
        "active_window_id": active_window_id,
        "game_window_id": game_window_id,
        "extension_active": extension_active,
        "operator_visible_capture_avoided": not allow_noisy and not allow_interactive,
    }


def _nested_get(value: Mapping[str, Any], path: list[str]) -> Any:
    current: Any = value
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current

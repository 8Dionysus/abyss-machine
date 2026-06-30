from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import re
from typing import Any, Callable, Mapping

from . import nervous_screenshot


RunnerPort = Callable[..., dict[str, Any]]
CommandExistsPort = Callable[[str], bool]
ProcessInfoPort = Callable[[int], dict[str, Any] | None]
GameRolePort = Callable[[str, str, str | None, str | None], str]
WorkloadHintPort = Callable[[str, str, str | None, str | None], str]
TextHaystackPort = Callable[..., str]
StrongGameSignalPort = Callable[[str], bool]
GameGuardPort = Callable[[], dict[str, Any]]
SourceEnabledPort = Callable[[dict[str, Any], str], bool]
VirtualSourcePort = Callable[[str, dict[str, Any]], dict[str, Any]]
FileSourcePort = Callable[[Path], dict[str, Any]]
AllowlistedBusPort = Callable[[Path, float], dict[str, Any]]
NowPort = Callable[[], dt.datetime]
NowIsoPort = Callable[[], str]


def gnome_screenshot_extension_status(
    *,
    command_exists: CommandExistsPort,
    runner: RunnerPort,
    environ: Mapping[str, str] | None = None,
    uuid: str = nervous_screenshot.ALLOW_EXTENSION_UUID,
) -> dict[str, Any]:
    if not command_exists("gnome-extensions"):
        return {"uuid": uuid, "active": False, "reason": "gnome-extensions_missing"}
    stable_env = dict(environ or os.environ)
    stable_env.update({"LC_ALL": "C.UTF-8", "LANG": "C.UTF-8", "LANGUAGE": "C"})
    result = runner(["gnome-extensions", "info", uuid], timeout=1.5, env=stable_env)
    enabled_result = runner(["gnome-extensions", "list", "--enabled"], timeout=1.5, env=stable_env)
    text = f"{result.get('stdout') or ''}\n{result.get('stderr') or ''}"
    enabled_lines = {line.strip() for line in str(enabled_result.get("stdout") or "").splitlines()}
    enabled_list_contains = uuid in enabled_lines
    state_active = bool(re.search(r"(?mi)^\s*(State|Состояние):\s*ACTIVE\s*$", text))
    enabled_text = bool(re.search(r"(?mi)^\s*(Enabled|Включено):\s*(Yes|Да)\s*$", text))
    active = bool(result.get("ok")) and state_active and (enabled_text or enabled_list_contains)
    if active:
        reason = "active"
    elif "doesn't exist" in text or "does not exist" in text:
        reason = "extension_missing_or_not_loaded"
    elif not result.get("ok"):
        reason = "extension_status_failed"
    else:
        reason = "extension_not_active"
    return {
        "uuid": uuid,
        "active": active,
        "reason": reason,
        "returncode": result.get("returncode"),
        "enabled_list_ok": bool(enabled_result.get("ok")),
        "enabled_list_contains": enabled_list_contains,
        "stdout": str(result.get("stdout") or "")[:240],
        "stderr": str(result.get("stderr") or "")[:240],
    }


def gnome_shell_screenshot_allowlisted_bus(path: Path, timeout: float = 6.0) -> dict[str, Any]:
    try:
        import gi  # type: ignore
        from gi.repository import Gio, GLib  # type: ignore
    except Exception as exc:
        return {
            "ok": False,
            "returncode": 1,
            "stderr": f"gi_import_failed: {exc!r}"[:400],
            "stdout": "",
        }

    state: dict[str, Any] = {"done": False, "ok": False, "reply": None, "error": None}
    loop = GLib.MainLoop()
    timeout_ms = max(1000, int(timeout * 1000))

    def finish() -> bool:
        if not state["done"]:
            state["done"] = True
            loop.quit()
        return False

    def call_shell(conn: Any) -> bool:
        try:
            result = conn.call_sync(
                "org.gnome.Shell.Screenshot",
                "/org/gnome/Shell/Screenshot",
                "org.gnome.Shell.Screenshot",
                "Screenshot",
                GLib.Variant("(bbs)", (False, False, str(path))),
                GLib.VariantType.new("(bs)"),
                Gio.DBusCallFlags.NONE,
                timeout_ms,
                None,
            )
            reply = result.unpack()
            state["reply"] = reply
            state["ok"] = bool(reply[0]) and path.exists() and path.stat().st_size > 0
        except Exception as exc:
            state["error"] = repr(exc)[:400]
        finish()
        return False

    def acquired(conn: Any, _name: str) -> None:
        GLib.timeout_add(350, call_shell, conn)

    def lost(_conn: Any, _name: str) -> None:
        if not state["done"]:
            state["error"] = "bus_name_lost"
            finish()

    owner = Gio.bus_own_name(
        Gio.BusType.SESSION,
        "org.gnome.Screenshot",
        Gio.BusNameOwnerFlags.NONE,
        acquired,
        None,
        lost,
    )
    GLib.timeout_add(timeout_ms, finish)
    loop.run()
    Gio.bus_unown_name(owner)
    return {
        "ok": bool(state["ok"]),
        "returncode": 0 if state["ok"] else 1,
        "stdout": json.dumps({"reply": state.get("reply")}, ensure_ascii=False)[:400],
        "stderr": str(state.get("error") or "")[:400],
    }


def x11_window_details(
    window_id: str,
    prop_text: str,
    *,
    process_info: ProcessInfoPort,
    game_role: GameRolePort,
    workload_hint: WorkloadHintPort,
    text_haystack: TextHaystackPort,
    strong_game_signal: StrongGameSignalPort,
) -> dict[str, Any]:
    lower = prop_text.lower()
    pid_match = re.search(r"_NET_WM_PID\(CARDINAL\)\s*=\s*([0-9]+)", prop_text)
    pid = int(pid_match.group(1)) if pid_match else None
    proc_summary: dict[str, Any] | None = None
    process_game_like = False
    if pid is not None:
        proc = process_info(pid)
        if isinstance(proc, dict):
            proc_role = game_role(
                str(proc.get("cmdline") or ""),
                str(proc.get("comm") or ""),
                proc.get("cwd"),
                proc.get("exe"),
            )
            proc_workload = workload_hint(
                str(proc.get("cmdline") or ""),
                str(proc.get("comm") or ""),
                proc.get("cwd"),
                proc.get("exe"),
            )
            proc_text = text_haystack(proc.get("comm"), proc.get("cmdline"), proc.get("cwd"), proc.get("exe"))
            process_game_like = proc_role == "active_game" or proc_workload == "game" or strong_game_signal(proc_text)
            proc_summary = {
                "pid": pid,
                "comm": proc.get("comm"),
                "name": proc.get("name"),
                "game_role": proc_role,
                "workload_hint": proc_workload,
                "cwd": proc.get("cwd"),
                "exe": proc.get("exe"),
                "cmdline_excerpt": str(proc.get("cmdline") or "")[:300],
            }
    prop_game_like = strong_game_signal(lower) or any(token in lower for token in (
        "dragon age",
        "daorigins",
        "daorigins.exe",
        "dragonage",
        "steam_app_",
        "wine",
        "proton",
        "gamescope",
        "lutris",
        "heroic",
        "bottles",
    ))
    fullscreen = "_net_wm_state_fullscreen" in lower
    return {
        "window_id": window_id,
        "pid": pid,
        "fullscreen": fullscreen,
        "game_like": bool(prop_game_like or process_game_like),
        "prop_game_like": bool(prop_game_like),
        "process_game_like": bool(process_game_like),
        "process": proc_summary,
        "summary": prop_text[:600],
    }


def x11_active_window_info(
    *,
    environ: Mapping[str, str],
    command_exists: CommandExistsPort,
    runner: RunnerPort,
    process_info: ProcessInfoPort,
    game_role: GameRolePort,
    workload_hint: WorkloadHintPort,
    text_haystack: TextHaystackPort,
    strong_game_signal: StrongGameSignalPort,
    timeout: float = 1.2,
) -> dict[str, Any]:
    if not environ.get("DISPLAY") or not command_exists("xprop"):
        return {"ok": False, "reason": "x11_unavailable_or_xprop_missing"}
    root = runner(["xprop", "-root", "_NET_ACTIVE_WINDOW", "_NET_CLIENT_LIST_STACKING"], timeout=timeout)
    text = str(root.get("stdout") or root.get("stderr") or "")
    if not root.get("ok"):
        return {"ok": False, "reason": "active_window_unavailable", "stdout": text[:240], "returncode": root.get("returncode")}
    candidate_ids: list[str] = []
    active = re.search(r"_NET_ACTIVE_WINDOW\(WINDOW\): window id #\s*(0x[0-9a-fA-F]+)", text)
    if active:
        candidate_ids.append(active.group(1))
    stacking = re.search(r"_NET_CLIENT_LIST_STACKING\(WINDOW\):\s*(.*)", text)
    if stacking:
        candidate_ids.extend(re.findall(r"0x[0-9a-fA-F]+", stacking.group(1))[::-1])
    seen: set[str] = set()
    candidates = [item for item in candidate_ids if item.lower() not in seen and not seen.add(item.lower())]
    for window_id in candidates:
        if window_id.lower() in {"0x0", "0x0000000", "0x00000000"}:
            continue
        props = runner(["xprop", "-id", window_id, "WM_CLASS", "WM_NAME", "_NET_WM_NAME", "_NET_WM_STATE", "_NET_WM_PID"], timeout=timeout)
        prop_text = str(props.get("stdout") or props.get("stderr") or "")
        has_property_value = bool(re.search(r"(?m)^(WM_CLASS|WM_NAME|_NET_WM_NAME|_NET_WM_STATE|_NET_WM_PID)[^=\n]*=", prop_text))
        if not props.get("ok") or not has_property_value:
            continue
        details = x11_window_details(
            window_id,
            prop_text,
            process_info=process_info,
            game_role=game_role,
            workload_hint=workload_hint,
            text_haystack=text_haystack,
            strong_game_signal=strong_game_signal,
        )
        details.update({
            "ok": True,
            "returncode": props.get("returncode"),
            "candidates": candidates[:8],
        })
        return details
    return {"ok": False, "reason": "no_usable_x11_window", "candidates": candidates[:8], "stdout": text[:400]}


def x11_game_window_risk_info(
    *,
    game_guard: Mapping[str, Any] | None,
    environ: Mapping[str, str],
    command_exists: CommandExistsPort,
    runner: RunnerPort,
    process_info: ProcessInfoPort,
    game_role: GameRolePort,
    workload_hint: WorkloadHintPort,
    text_haystack: TextHaystackPort,
    strong_game_signal: StrongGameSignalPort,
    timeout: float = 1.2,
) -> dict[str, Any]:
    if not environ.get("DISPLAY") or not command_exists("xprop"):
        return {"ok": False, "risk": False, "reason": "x11_unavailable_or_xprop_missing"}
    root = runner(["xprop", "-root", "_NET_ACTIVE_WINDOW", "_NET_CLIENT_LIST_STACKING"], timeout=timeout)
    text = str(root.get("stdout") or root.get("stderr") or "")
    if not root.get("ok"):
        return {"ok": False, "risk": False, "reason": "x11_window_list_unavailable", "stdout": text[:240], "returncode": root.get("returncode")}
    active_match = re.search(r"_NET_ACTIVE_WINDOW\(WINDOW\): window id #\s*(0x[0-9a-fA-F]+)", text)
    active_window_id = active_match.group(1) if active_match else None
    candidate_ids: list[str] = []
    stacking = re.search(r"_NET_CLIENT_LIST_STACKING\(WINDOW\):\s*(.*)", text)
    if stacking:
        candidate_ids.extend(re.findall(r"0x[0-9a-fA-F]+", stacking.group(1))[::-1])
    if active_window_id:
        candidate_ids.insert(0, active_window_id)
    seen: set[str] = set()
    candidates = [item for item in candidate_ids if item.lower() not in seen and not seen.add(item.lower())]
    platform_present = bool(game_guard.get("platform_present")) if isinstance(game_guard, Mapping) else False
    risk_windows: list[dict[str, Any]] = []
    inspected = 0
    for window_id in candidates[:40]:
        if window_id.lower() in {"0x0", "0x0000000", "0x00000000"}:
            continue
        props = runner(["xprop", "-id", window_id, "WM_CLASS", "WM_NAME", "_NET_WM_NAME", "_NET_WM_STATE", "_NET_WM_PID"], timeout=timeout)
        prop_text = str(props.get("stdout") or props.get("stderr") or "")
        has_property_value = bool(re.search(r"(?m)^(WM_CLASS|WM_NAME|_NET_WM_NAME|_NET_WM_STATE|_NET_WM_PID)[^=\n]*=", prop_text))
        if not props.get("ok") or not has_property_value:
            continue
        inspected += 1
        details = x11_window_details(
            window_id,
            prop_text,
            process_info=process_info,
            game_role=game_role,
            workload_hint=workload_hint,
            text_haystack=text_haystack,
            strong_game_signal=strong_game_signal,
        )
        fullscreen_platform_risk = bool(details.get("fullscreen") and platform_present)
        if details.get("game_like") or fullscreen_platform_risk:
            risk_windows.append({
                "window_id": details.get("window_id"),
                "active": window_id == active_window_id,
                "fullscreen": details.get("fullscreen"),
                "game_like": details.get("game_like"),
                "prop_game_like": details.get("prop_game_like"),
                "process_game_like": details.get("process_game_like"),
                "risk_reason": "game_like_x11_window" if details.get("game_like") else "fullscreen_x11_window_while_game_platform_present",
                "process": details.get("process"),
                "summary": details.get("summary"),
            })
    return {
        "ok": True,
        "risk": bool(risk_windows),
        "reason": "x11_game_window_risk" if risk_windows else "no_x11_game_window_risk",
        "active_window_id": active_window_id,
        "platform_present": platform_present,
        "inspected_windows": inspected,
        "windows": risk_windows[:8],
        "candidates": candidates[:12],
    }


def screenshot_fact(
    *,
    sources: dict[str, Any],
    trigger: str,
    screenshot_root: Path,
    source_enabled: SourceEnabledPort,
    virtual_source: VirtualSourcePort,
    file_source: FileSourcePort,
    command_exists: CommandExistsPort,
    runner: RunnerPort,
    process_game_guard: GameGuardPort,
    active_x11_info: Callable[[], dict[str, Any]],
    x11_game_window_risk: Callable[[dict[str, Any]], dict[str, Any]],
    extension_status_reader: Callable[[], dict[str, Any]],
    allowlisted_bus: AllowlistedBusPort = gnome_shell_screenshot_allowlisted_bus,
    capture_plan: Callable[..., dict[str, Any]] = nervous_screenshot.capture_plan,
    environ: Mapping[str, str] | None = None,
    now: NowPort | None = None,
    now_iso: NowIsoPort | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    source_id = "screenshots"
    if not source_enabled(sources, source_id):
        return None, {"source": source_id, "reason": "disabled_by_source_policy"}
    current = (now or (lambda: dt.datetime.now(dt.timezone.utc).astimezone()))()
    current_iso = (now_iso or (lambda: dt.datetime.now(dt.timezone.utc).astimezone().isoformat()))()
    daily_root = screenshot_root / f"{current.year:04d}" / f"{current.month:02d}"
    daily_root.mkdir(parents=True, exist_ok=True)
    path = daily_root / (current.strftime("%Y-%m-%dT%H%M%S%z") + ".png")
    env = environ or os.environ
    allow_interactive = env.get("ABYSS_NERVOUS_ALLOW_INTERACTIVE_SCREENSHOT") == "1"
    allow_noisy = env.get("ABYSS_NERVOUS_ALLOW_NOISY_SCREENSHOT") == "1"
    query_extensions_on_timer = env.get("ABYSS_NERVOUS_QUERY_GNOME_EXTENSIONS_ON_TIMER") == "1"
    extension_status = nervous_screenshot.extension_query_skip_status(trigger, query_extensions_on_timer)
    if extension_status is None:
        extension_status = extension_status_reader()
    allow_shell_dbus = env.get("ABYSS_NERVOUS_ALLOW_SHELL_SCREENSHOT_DBUS") == "1"
    game_guard = process_game_guard()
    active_x11 = active_x11_info()
    x11_risk = x11_game_window_risk(game_guard)
    plan = capture_plan(
        trigger=trigger,
        path=str(path),
        extension_status=extension_status,
        command_available={
            "magick": command_exists("magick"),
            "grim": command_exists("grim"),
            "gdbus": command_exists("gdbus"),
            "gnome-screenshot": command_exists("gnome-screenshot"),
        },
        allow_interactive=allow_interactive,
        allow_noisy=allow_noisy,
        allow_shell_dbus=allow_shell_dbus,
        game_guard=game_guard,
        active_x11=active_x11,
        x11_game_window_risk=x11_risk,
    )
    commands: list[tuple[str, list[str], float]] = [
        (str(item.get("tool")), [str(part) for part in item.get("argv", [])], float(item.get("timeout") or 6.0))
        for item in plan.get("commands", [])
        if isinstance(item, dict) and isinstance(item.get("argv"), list)
    ]
    attempts = list(plan.get("attempts", [])) if isinstance(plan.get("attempts"), list) else []
    game_safe_capture = bool(plan.get("game_safe_capture"))
    game_safe_reason = plan.get("game_safe_reason")
    result: dict[str, Any] | None = None
    for tool, cmd, timeout in commands:
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass
        if cmd and cmd[0] == nervous_screenshot.ALLOWLISTED_BUS_MARKER:
            result = allowlisted_bus(path, timeout)
        else:
            result = runner(cmd, timeout=timeout)
        attempt_ok = bool(result.get("ok")) and path.exists() and path.stat().st_size > 0
        attempts.append({
            "tool": tool,
            "ok": attempt_ok,
            "returncode": result.get("returncode"),
            "stderr": str(result.get("stderr") or "")[:400],
            "stdout": str(result.get("stdout") or "")[:400],
        })
        if attempt_ok:
            break
    if result is None:
        return None, {
            "source": source_id,
            "reason": "screenshot_silent_backend_unavailable",
            "path": str(path),
            "attempts": attempts,
            "operator_visible_capture_avoided": True,
        }
    ok = bool(result.get("ok")) and path.exists() and path.stat().st_size > 0
    artifact = file_source(path) if path.exists() else {"path": str(path), "exists": False}
    payload = {"artifact": artifact, "trigger": trigger, "ok": ok, "attempts": attempts, "stderr": str(result.get("stderr") or "")[:400]}
    if not ok:
        attempt_text = " ".join(
            str(item.get("stderr") or "") + " " + str(item.get("stdout") or "")
            for item in attempts
        )
        if "AccessDenied" in attempt_text or "Screenshot is not allowed" in attempt_text:
            reason = "screenshot_access_denied"
        elif "Unable to capture" in attempt_text or "width > 0" in attempt_text:
            reason = "screenshot_wayland_capture_unavailable"
        else:
            reason = "screenshot_capture_failed"
        return None, {
            "source": source_id,
            "reason": reason,
            "path": str(path),
            "attempts": attempts,
            "operator_visible_capture_avoided": not allow_noisy and not allow_interactive,
            "game_safe_capture": game_safe_capture,
        }
    capture_tool = next(
        (item.get("tool") for item in attempts if item.get("ok") and item.get("returncode") is not None),
        None,
    )
    operator_visible = bool(str(capture_tool or "").startswith("gnome-screenshot"))
    backend_quality = "silent_noninteractive" if not operator_visible else "operator_visible_explicit_opt_in"
    return {
        "name": "screenshot",
        "source_id": source_id,
        "ok": ok,
        "observed_at": current_iso,
        "sensitivity": "local_private_artifact",
        "summary": {
            "captured": ok,
            "bytes": _nested_get(artifact, ["stat", "size_bytes"]),
            "raw_pixels_indexed": False,
            "artifact_root": str(screenshot_root),
            "attempts": len(attempts),
            "timer_capture": trigger == "timer",
            "backend_quality": backend_quality,
            "capture_tool": capture_tool,
            "operator_visible": operator_visible,
            "game_safe_capture": game_safe_capture,
            "game_safe_reason": game_safe_reason,
            "x11_game_window_risk": bool(x11_risk.get("risk")),
        },
        "artifact": artifact,
        "attempts": attempts,
        "backend": {
            "timer_capture": trigger == "timer",
            "quality": backend_quality,
            "policy": "automatic_capture_uses_silent_backend_or_skips_with_evidence",
            "dbus_fallback": "disabled_by_default_requires_ABYSS_NERVOUS_ALLOW_SHELL_SCREENSHOT_DBUS",
            "gnome_screenshot": "disabled_by_default_requires_ABYSS_NERVOUS_ALLOW_NOISY_SCREENSHOT",
            "limitations": [
                "gnome-screenshot can flash, make sound, or steal attention and is not used automatically",
                "GNOME Shell screenshot backends are skipped during active game or X11 game-window risk contexts to avoid minimizing the game",
                "game-safe capture first tries non-focus X11/Xwayland window capture and then grim; if both fail it skips instead of disturbing the operator",
                "direct GNOME Shell DBus screenshot fallback is not used unless explicitly enabled",
                "when no silent backend is available the screenshot source is skipped instead of disturbing the operator",
            ],
        },
        "error": None if ok else str(result.get("stderr") or "")[:400],
        "source": virtual_source(source_id, payload),
    }, None


def _nested_get(value: Any, path: list[str]) -> Any:
    current = value
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current

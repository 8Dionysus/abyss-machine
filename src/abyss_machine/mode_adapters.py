from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Callable, Sequence

from . import mode_contracts


CommandExistsPort = Callable[[str], bool]
CommandRunnerPort = Callable[[Sequence[str], float], dict[str, Any]]
GameModeStatusPort = Callable[[], dict[str, Any]]
GameGuardPort = Callable[[], dict[str, Any]]
WriteJsonDocument = Callable[[Path, dict[str, Any], int], None]


def tool_available(command: str) -> bool:
    return shutil.which(command) is not None


def run_tool_process(command: Sequence[str], timeout: float) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            list(command),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": 124, "stdout": "", "stderr": "timeout"}
    except OSError as exc:
        return {"ok": False, "returncode": 127, "stdout": "", "stderr": str(exc)}


def default_state(
    *,
    state_file: Path,
    schema_prefix: str,
    version: str,
    generated_at: str,
    current_profile: str | None,
) -> dict[str, Any]:
    state = mode_contracts.default_state(
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
        current_profile=current_profile,
    )
    state["state_file"] = str(state_file)
    return state


def load_state(
    state_file: Path,
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    current_profile: str | None,
) -> dict[str, Any]:
    state = default_state(
        state_file=state_file,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
        current_profile=current_profile,
    )
    if state_file.exists():
        try:
            loaded = json.loads(state_file.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state.update(loaded)
        except (OSError, json.JSONDecodeError):
            state["state_error"] = "invalid mode-state.json"
    return mode_contracts.sanitize_state(state)


def state_payload(
    state: dict[str, Any],
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    updated_by: str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_mode_state_v1",
        "version": version,
        "selected_mode": state.get("selected_mode", "balanced"),
        "last_non_ai_mode": state.get("last_non_ai_mode", "balanced"),
        "forced_saver_on_battery": bool(state.get("forced_saver_on_battery", False)),
        "updated_at": generated_at,
        "updated_by": updated_by,
    }


def save_state(
    state_file: Path,
    state: dict[str, Any],
    *,
    updated_by: str,
    schema_prefix: str,
    version: str,
    generated_at: str,
    write_json_document: WriteJsonDocument,
    mode: int = 0o664,
) -> None:
    write_json_document(
        state_file,
        state_payload(
            state,
            schema_prefix=schema_prefix,
            version=version,
            generated_at=generated_at,
            updated_by=updated_by,
        ),
        mode,
    )


def power_profile(
    *,
    command_exists: CommandExistsPort = tool_available,
    runner: CommandRunnerPort = run_tool_process,
    cache: dict[str, Any] | None = None,
) -> str | None:
    if cache is not None and cache.get("ready"):
        value = cache.get("value")
        return str(value) if value is not None else None
    if not command_exists("powerprofilesctl"):
        if cache is not None:
            cache["ready"] = True
            cache["value"] = None
        return None
    out = runner(["powerprofilesctl", "get"], 2.0)
    value = str(out.get("stdout") or "").strip() if out.get("ok") and out.get("stdout") else None
    if cache is not None:
        cache["ready"] = True
        cache["value"] = value
    return value


def set_power_profile(
    target: str,
    *,
    command_exists: CommandExistsPort = tool_available,
    runner: CommandRunnerPort = run_tool_process,
    cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not command_exists("powerprofilesctl"):
        return {"ok": False, "target": target, "error": "powerprofilesctl not found"}
    current = power_profile(command_exists=command_exists, runner=runner, cache=cache)
    if current == target:
        return {"ok": True, "changed": False, "current": current, "target": target}
    out = runner(["powerprofilesctl", "set", target], 5.0)
    if out.get("ok") and cache is not None:
        cache["ready"] = True
        cache["value"] = target
    return {
        "ok": bool(out.get("ok")),
        "changed": bool(out.get("ok")),
        "current": current,
        "target": target,
        "stdout": out.get("stdout") or "",
        "stderr": out.get("stderr") or "",
        "returncode": out.get("returncode"),
    }


def gamemode_recent_power_profile_activity(
    seconds: int = 120,
    *,
    command_exists: CommandExistsPort = tool_available,
    runner: CommandRunnerPort = run_tool_process,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "active": False,
        "seconds": seconds,
        "matched": [],
        "source": "journalctl _COMM=gamemoded",
    }
    if not command_exists("journalctl"):
        data["error"] = "journalctl not found"
        return data
    out = runner(
        ["journalctl", "--since", f"{int(seconds)} seconds ago", "--no-pager", "-o", "cat", "_COMM=gamemoded"],
        2.0,
    )
    text = "\n".join(part for part in (str(out.get("stdout") or ""), str(out.get("stderr") or "")) if part)
    if not out.get("ok") and not text:
        data["error"] = out.get("stderr") or "journalctl failed"
        data["returncode"] = out.get("returncode")
        return data
    indicators = (
        "powerprofilesctl set",
        "Entering Game Mode",
        "Leaving Game Mode",
        "Requesting update of governor policy",
        "Executing script [powerprofilesctl",
        "Adding game:",
        "Removing game:",
        "client [",
        "Skipping ioprio",
        "Pinning process",
    )
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    matches = [line for line in lines if any(indicator in line for indicator in indicators)]
    if not matches and lines:
        matches = lines[-6:]
    data["matched"] = matches[-12:]
    data["active"] = bool(matches)
    return data


def external_power_profile_guard(
    current_profile: str | None,
    target_profile: str | None,
    *,
    command_exists: CommandExistsPort = tool_available,
    runner: CommandRunnerPort = run_tool_process,
    gamemode_status: GameModeStatusPort,
    game_guard: GameGuardPort,
    recent_seconds: int = 120,
) -> dict[str, Any]:
    if not current_profile or current_profile == target_profile:
        return {"active": False, "reason": "no_profile_drift"}
    recent = gamemode_recent_power_profile_activity(
        recent_seconds,
        command_exists=command_exists,
        runner=runner,
    )
    try:
        gamemode = gamemode_status()
    except Exception as exc:
        gamemode = {"available": False, "error": repr(exc)}
    guard: dict[str, Any] = {"checked": False}
    guard_active = False
    if mode_contracts.power_profile_rank(current_profile) > mode_contracts.power_profile_rank(target_profile):
        try:
            guard_data = game_guard()
            guard = {
                "checked": True,
                "ok": guard_data.get("ok"),
                "active": guard_data.get("active"),
                "summary": guard_data.get("summary"),
            }
            guard_active = bool(
                guard_data.get("active")
                or (
                    isinstance(guard_data.get("summary"), dict)
                    and guard_data["summary"].get("gamemode_global_active")
                )
            )
        except Exception as exc:
            guard = {"checked": True, "ok": False, "error": repr(exc)}
    data = mode_contracts.external_power_profile_guard(
        current_profile=current_profile,
        target_profile=target_profile,
        gamemode=gamemode,
        recent=recent,
        game_guard=guard,
        game_guard_active=guard_active,
    )
    if isinstance(data.get("gamemode"), dict):
        data["gamemode"]["status_text"] = gamemode.get("global_status_text")
    data["policy"] = "Suppress selected-mode inference from recent transient GameMode profile flips; preserve a stronger profile while GameMode or active game-guard evidence reports a protected game/operator workload."
    return data

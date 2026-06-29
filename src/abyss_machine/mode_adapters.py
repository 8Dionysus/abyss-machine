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
BatterySummaryPort = Callable[[], dict[str, Any]]
PowerProfilePort = Callable[[], str | None]
TargetProfilePort = Callable[[str, bool], tuple[str, str, str | None]]
ProfilePolicyPort = Callable[[str], dict[str, Any]]
CurrentModePort = Callable[[str | None], str | None]
ExternalProfileGuardPort = Callable[[str | None, str | None], dict[str, Any]]
CoolingRecommendPort = Callable[[], dict[str, Any]]
CoolingProfileTargetsPort = Callable[[str], tuple[str, dict[str, Any], Any]]
ThermalClassPort = Callable[[dict[str, Any]], str]
CpuThermalMapPort = Callable[[bool], dict[str, Any]]
CpuRoutedHeavyPort = Callable[..., dict[str, Any]]
LoadJsonDocumentPort = Callable[[Path], tuple[Any, Any]]
PathExistsPort = Callable[[Path], bool]
AiDevicesPort = Callable[[], dict[str, Any]]
SensorsSummaryPort = Callable[[], dict[str, Any]]
ModePlanPort = Callable[[], dict[str, Any]]


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


def nested_get(data: Any, path: Sequence[str]) -> Any:
    current = data
    for item in path:
        if not isinstance(current, dict):
            return None
        current = current.get(item)
    return current


def latest_json_summary(
    path: Path,
    *,
    load_json_document: LoadJsonDocumentPort,
    path_exists: PathExistsPort = lambda path: path.exists(),
    kind: str,
) -> dict[str, Any]:
    data, error = load_json_document(path)
    summary: Any = None
    if isinstance(data, dict):
        if kind == "memory_plan":
            summary = {
                "class": data.get("class"),
                "reasons": data.get("reasons"),
                "recommended_new_work": data.get("recommended_new_work"),
            }
        else:
            summary = data.get("summary")
    return {
        "path": str(path),
        "exists": path_exists(path),
        "load_error": error,
        "summary": summary,
    }


def collect_plan_inputs(
    *,
    state: dict[str, Any],
    battery_summary: BatterySummaryPort,
    target_profile: TargetProfilePort,
    profile_policy: ProfilePolicyPort,
    power_profile: PowerProfilePort,
    current_mode_from_power_profile: CurrentModePort,
    external_profile_guard: ExternalProfileGuardPort,
    cooling_recommend: CoolingRecommendPort,
    cooling_profile_targets: CoolingProfileTargetsPort,
    thermal_class_from_summary: ThermalClassPort,
    cpu_thermal_map: CpuThermalMapPort,
    cpu_routed_heavy_policy: CpuRoutedHeavyPort,
    load_json_document: LoadJsonDocumentPort,
    storage_pressure_path: Path,
    memory_plan_path: Path,
    process_latest_path: Path,
    path_exists: PathExistsPort = lambda path: path.exists(),
    write_latest: bool = True,
) -> dict[str, Any]:
    battery = battery_summary()
    ac_online = bool(battery.get("ac_online"))
    selected = str(state.get("selected_mode", "balanced"))
    effective, target_profile_name, degraded_reason = target_profile(selected, ac_online)
    profile = profile_policy(effective)
    current_profile = power_profile()
    current_mode = current_mode_from_power_profile(current_profile)
    guard = external_profile_guard(current_profile, target_profile_name)
    cooling = cooling_recommend()
    cooling_profile = str(cooling.get("recommended_profile") or profile.get("cooling_profile") or effective)
    cooling_normalized, cooling_target, _ = cooling_profile_targets(cooling_profile)
    temperature = cooling.get("temperature", {}) if isinstance(cooling.get("temperature"), dict) else {}
    thermal_class = thermal_class_from_summary(
        {
            "class": temperature.get("class") or nested_get(temperature, ["cpu_hotspot", "class"]),
            "temperature_c_max": temperature.get("temperature_c_max"),
        }
    )
    cpu_map = cpu_thermal_map(write_latest)
    cpu_routed_heavy = cpu_routed_heavy_policy(
        cpu_map,
        thermal_class,
        effective,
        ac_online,
        capacity_percent=battery.get("capacity_percent"),
        trend=str(nested_get(temperature, ["cpu_hotspot", "trend"]) or "unknown"),
    )
    return {
        "state": state,
        "battery": battery,
        "ac_online": ac_online,
        "selected": selected,
        "effective": effective,
        "target_profile_name": target_profile_name,
        "degraded_reason": degraded_reason,
        "profile": profile,
        "current_profile": current_profile,
        "current_mode": current_mode,
        "external_profile_guard": guard,
        "cooling": cooling,
        "cooling_normalized": cooling_normalized,
        "cooling_target": cooling_target,
        "temperature": temperature,
        "thermal_class": thermal_class,
        "cpu_thermal_map": cpu_map,
        "cpu_routed_heavy": cpu_routed_heavy,
        "storage_pressure_latest": latest_json_summary(
            storage_pressure_path,
            load_json_document=load_json_document,
            path_exists=path_exists,
            kind="storage_pressure",
        ),
        "memory_plan_latest": latest_json_summary(
            memory_plan_path,
            load_json_document=load_json_document,
            path_exists=path_exists,
            kind="memory_plan",
        ),
        "process_latest": latest_json_summary(
            process_latest_path,
            load_json_document=load_json_document,
            path_exists=path_exists,
            kind="process_latest",
        ),
    }


def collect_status_inputs(
    *,
    state: dict[str, Any],
    battery_summary: BatterySummaryPort,
    target_profile: TargetProfilePort,
    power_profile: PowerProfilePort,
    external_profile_guard: ExternalProfileGuardPort,
    ai_devices: AiDevicesPort,
    sensors_summary: SensorsSummaryPort,
    mode_plan: ModePlanPort,
) -> dict[str, Any]:
    battery = battery_summary()
    ac_online = bool(battery.get("ac_online"))
    selected = str(state.get("selected_mode", "balanced"))
    effective, target_profile_name, degraded_reason = target_profile(selected, ac_online)
    current_profile = power_profile()
    guard = external_profile_guard(current_profile, target_profile_name)
    ai = ai_devices()
    sensors = sensors_summary()
    ai_ready = bool(ai.get("dev_dri_present") and ai.get("dev_accel_present") and ai.get("openvino_venv_exists"))
    return {
        "state": state,
        "battery": battery,
        "ac_online": ac_online,
        "selected": selected,
        "effective": effective,
        "target_profile_name": target_profile_name,
        "degraded_reason": degraded_reason,
        "current_profile": current_profile,
        "external_profile_guard": guard,
        "ai": ai,
        "sensors": sensors,
        "ai_ready": ai_ready,
        "plan": mode_plan(),
    }


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

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import validation_contracts


VALID_MODES = {"saver", "balanced", "performance", "ai"}
VALID_SET_MODES = VALID_MODES | {"previous"}
VALID_POWER_PROFILES = {"power-saver", "balanced", "performance"}
VALID_COOLING_PROFILES = {"auto", "saver", "balanced", "performance", "emergency", "firmware-auto"}
VALID_WORKLOAD_CLASSES = {"probe", "light", "medium", "heavy", "sustained"}

POWER_PROFILE_TO_MODE = {
    "power-saver": "saver",
    "balanced": "balanced",
    "performance": "performance",
}
MODE_TO_POWER_PROFILE = {
    "saver": "power-saver",
    "balanced": "balanced",
    "performance": "performance",
    "ai": "performance",
}
WORKLOAD_LEVELS = {
    "blocked": -1,
    "none": -1,
    "background": 0,
    "probe": 0,
    "light": 1,
    "interactive": 2,
    "medium": 2,
    "heavy": 3,
    "sustained": 4,
}


def _schema(schema_prefix: str, suffix: str) -> str:
    return f"{schema_prefix}_{suffix}"


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def current_mode_from_power_profile(profile: str | None) -> str | None:
    if profile is None:
        return None
    return POWER_PROFILE_TO_MODE.get(profile)


def default_state(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    current_profile: str | None,
) -> dict[str, Any]:
    selected = current_mode_from_power_profile(current_profile) or "balanced"
    if selected == "saver":
        selected = "balanced"
    return {
        "schema": _schema(schema_prefix, "mode_state_v1"),
        "version": version,
        "selected_mode": selected,
        "last_non_ai_mode": selected if selected in {"balanced", "performance", "saver"} else "balanced",
        "forced_saver_on_battery": False,
        "updated_at": generated_at,
        "updated_by": "default",
    }


def sanitize_state(state: dict[str, Any]) -> dict[str, Any]:
    clean = dict(state)
    if clean.get("selected_mode") not in VALID_MODES:
        clean["selected_mode"] = "balanced"
    if clean.get("last_non_ai_mode") not in {"saver", "balanced", "performance"}:
        clean["last_non_ai_mode"] = "balanced"
    clean["forced_saver_on_battery"] = bool(clean.get("forced_saver_on_battery", False))
    return clean


def default_policy(*, schema_prefix: str, version: str, generated_at: str) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "mode_policy_v1"),
        "version": version,
        "generated_at": generated_at,
        "purpose": "Abyss Machine work-mode contract tying GNOME power profiles to host hardware, thermal, AI and agent launch policy.",
        "profiles": {
            "saver": {
                "power_profile": "power-saver",
                "cooling_profile": "saver",
                "ac_allowed": True,
                "battery_allowed": True,
                "ai_overlay": False,
                "max_unattended_class_ac": "light",
                "max_unattended_class_battery": "probe",
                "description": "battery-first, quiet, cool, low background pressure",
            },
            "balanced": {
                "power_profile": "balanced",
                "cooling_profile": "balanced",
                "ac_allowed": True,
                "battery_allowed": "armed",
                "ai_overlay": False,
                "max_unattended_class_ac": "medium",
                "max_unattended_class_battery": "probe",
                "description": "daily AC/default work mode; battery reconciles to saver",
            },
            "performance": {
                "power_profile": "performance",
                "cooling_profile": "performance",
                "ac_allowed": True,
                "battery_allowed": "armed",
                "ai_overlay": False,
                "max_unattended_class_ac": "heavy",
                "max_unattended_class_battery": "probe",
                "description": "AC high-performance mode; cooling and launch policy remain thermal-aware",
            },
            "ai": {
                "power_profile": "performance",
                "cooling_profile": "performance",
                "ac_allowed": True,
                "battery_allowed": "armed",
                "ai_overlay": True,
                "max_unattended_class_ac": "heavy",
                "max_unattended_class_battery": "probe",
                "description": "Abyss AI overlay over performance with GPU/NPU/OpenVINO readiness checks",
            },
        },
        "thermal_launch_policy": {
            "green": {"max_unattended_class_cap": "sustained", "new_heavy": "allow_by_mode"},
            "warm": {
                "max_unattended_class_cap": "heavy",
                "new_heavy": "allow_if_mode_performance_or_ai_or_controlled_balanced",
                "new_heavy_cpu_routed": "allow_if_cpu_route_has_safe_cpuset",
            },
            "hot": {
                "max_unattended_class_cap": "medium",
                "new_heavy": "operator_controlled_routed_by_trend_duration_and_hotspot",
                "new_heavy_cpu_routed": "allow_operator_controlled_unless_broad_or_emergency_heat",
            },
            "critical": {
                "max_unattended_class_cap": "probe",
                "new_heavy": "defer_new_unattended_work_at_emergency_boundary",
                "new_heavy_cpu_routed": "operator_only_if_explicit_and_recovering",
            },
            "unknown": {"max_unattended_class_cap": "light", "new_heavy": "defer_until_telemetry"},
        },
        "battery_policy": {
            "discharging_effective_mode": "saver",
            "restore_selected_mode_on_ac": True,
            "min_battery_percent_for_heavy": 35,
        },
        "cooling_policy": {
            "apply": "abyss-machine cooling apply --profile auto --json",
            "critical_strategy": "preserve selected power profile, monitor 100-105C as active range, route above 105C by trend/duration, and reserve hard gates for 109-110C emergency range",
        },
        "agent_policy": {
            "do_not_kill_running_tasks": True,
            "gate_new_unattended_tasks": True,
            "operator_force_requires_explicit_flag": True,
        },
        "non_claims": [
            "The GNOME panel exposes power-saver/balanced/performance; ai is a host overlay selected through abyss-machine mode set ai.",
            "Mode policy returns launch gates and routes; callers must apply taskset/env hints explicitly.",
            "Thermal policy watches trend and duration: 100-105C is monitored active range, above 105C is watch/routing range, and 109-110C is the hard emergency gate for new work.",
        ],
    }


def policy_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    path: str,
    loaded: Any,
    load_error: Any,
) -> dict[str, Any]:
    base = default_policy(schema_prefix=schema_prefix, version=version, generated_at=generated_at)
    if isinstance(loaded, dict):
        merged = deep_merge(base, loaded)
        merged["path"] = path
        merged["exists"] = True
        merged["load_error"] = None
        return merged
    base["path"] = path
    base["exists"] = False
    base["load_error"] = load_error or "missing"
    return base


def profile_policy(policy: dict[str, Any], mode_name: str) -> dict[str, Any]:
    profiles = policy.get("profiles", {}) if isinstance(policy.get("profiles"), dict) else {}
    profile = profiles.get(mode_name)
    if not isinstance(profile, dict):
        profile = profiles.get("balanced", {})
    return dict(profile) if isinstance(profile, dict) else {}


def workload_level(name: str | None) -> int:
    return WORKLOAD_LEVELS.get(str(name or "light").strip().lower(), 1)


def workload_name_for_level(level: int) -> str:
    if level <= -1:
        return "blocked"
    if level == 0:
        return "probe"
    if level == 1:
        return "light"
    if level == 2:
        return "medium"
    if level == 3:
        return "heavy"
    return "sustained"


def thermal_class_from_summary(summary: dict[str, Any], thresholds: dict[str, Any] | None = None) -> str:
    raw = str(summary.get("class") or summary.get("thermal_class") or "unknown").lower()
    if raw in {"ok", "green", "cool"}:
        return "green"
    if raw in {"warm", "hot", "critical"}:
        return raw
    temp = summary.get("temperature_c_max")
    if isinstance(temp, (int, float)) and not isinstance(temp, bool):
        threshold_data = thresholds if isinstance(thresholds, dict) else {}
        critical = float(threshold_data.get("critical_temperature_c", 109.0))
        hot = float(threshold_data.get("hot_temperature_c", 106.0))
        if temp >= critical:
            return "critical"
        if temp >= hot:
            return "hot"
        if temp >= 80:
            return "warm"
        return "green"
    return "unknown"


def max_unattended_class(
    *,
    profile: dict[str, Any],
    thermal_class: str,
    effective_mode: str,
    ac_online: bool,
    policy: dict[str, Any],
) -> str:
    base_key = "max_unattended_class_ac" if ac_online else "max_unattended_class_battery"
    base = str(profile.get(base_key) or ("medium" if ac_online else "probe"))
    thermal_policy = policy.get("thermal_launch_policy", {}) if isinstance(policy.get("thermal_launch_policy"), dict) else {}
    thermal_item = thermal_policy.get(thermal_class) if isinstance(thermal_policy.get(thermal_class), dict) else {}
    cap = str(thermal_item.get("max_unattended_class_cap") or "light")
    max_level = min(workload_level(base), workload_level(cap))
    if effective_mode == "saver":
        max_level = min(max_level, workload_level("light" if ac_online else "probe"))
    return workload_name_for_level(max_level)


def power_profile_rank(profile: str | None) -> int:
    return {
        "power-saver": 0,
        "balanced": 1,
        "performance": 2,
    }.get(str(profile or ""), -1)


def external_power_profile_guard(
    *,
    current_profile: str | None,
    target_profile: str | None,
    gamemode: dict[str, Any],
    recent: dict[str, Any],
    game_guard: dict[str, Any],
    game_guard_active: bool,
) -> dict[str, Any]:
    if not current_profile or current_profile == target_profile:
        return {"active": False, "reason": "no_profile_drift"}
    global_active = bool(gamemode.get("global_active"))
    recent_active = bool(recent.get("active"))
    active = global_active or recent_active
    reason = "none"
    if global_active:
        reason = "gamemode_active"
    elif recent_active:
        reason = "recent_gamemode_power_profile_activity"
    elif game_guard_active:
        active = True
        reason = "active_game_guard"
    return {
        "active": active,
        "reason": reason,
        "current_profile": current_profile,
        "target_profile": target_profile,
        "preserve_external_boost": (global_active or game_guard_active)
        and power_profile_rank(current_profile) > power_profile_rank(target_profile),
        "restore_selected_target": active and power_profile_rank(current_profile) < power_profile_rank(target_profile),
        "gamemode": {
            "available": gamemode.get("available"),
            "global_active": global_active,
        },
        "recent": recent,
        "game_guard": game_guard,
    }


def mode_commands() -> dict[str, str]:
    return {
        "status": "abyss-machine mode status --json",
        "plan": "abyss-machine mode plan --json",
        "policy": "abyss-machine mode policy --json",
        "paths": "abyss-machine mode paths --json",
        "validate": "abyss-machine mode validate --json",
        "reconcile": "abyss-machine mode reconcile --json",
        "set_ai": "abyss-machine mode set ai --json",
        "set_previous": "abyss-machine mode set previous --json",
    }


def paths_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    refs: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "mode_paths_v1"),
        "version": version,
        "generated_at": generated_at,
        "root": str(refs["root"]),
        "agent_entrypoint": str(refs["agent_entrypoint"]),
        "index": str(refs["index"]),
        "latest": str(refs["latest"]),
        "state": str(refs["state"]),
        "policy": str(refs["policy"]),
        "plans": {
            "root": str(refs["plan_root"]),
            "latest": str(refs["plan_latest"]),
            "daily_glob": str(Path(str(refs["plan_root"])) / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        },
        "validate": {
            "root": str(refs["validate_root"]),
            "latest": str(refs["validate_latest"]),
            "daily_glob": str(Path(str(refs["validate_root"])) / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        },
        "commands": mode_commands(),
        "systemd": {
            "service": str(refs["cooling_service"]),
            "timer": str(refs["cooling_timer"]),
        },
        "policy_contract": {
            "host_mutation": False,
            "mode_set_requires_explicit_command": True,
            "live_collectors_enabled": False,
            "artifact_provenance_lane": False,
        },
    }


def index_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    refs: dict[str, Any],
    status_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "mode_index_v1"),
        "version": version,
        "generated_at": generated_at,
        "root": str(refs["root"]),
        "agent_entrypoint": str(refs["agent_entrypoint"]),
        "state": str(refs["state"]),
        "policy": str(refs["policy"]),
        "latest": str(refs["latest"]),
        "plan_latest": str(refs["plan_latest"]),
        "validate_latest": str(refs["validate_latest"]),
        "commands": mode_commands(),
        "latest_status": {
            "selected_mode": status_data.get("selected_mode") if isinstance(status_data, dict) else None,
            "effective_mode": status_data.get("effective_mode") if isinstance(status_data, dict) else None,
            "generated_at": status_data.get("generated_at") if isinstance(status_data, dict) else None,
        },
    }


def mode_validate_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    checks: list[dict[str, Any]],
    strict: bool,
    paths: dict[str, Any],
    plan: dict[str, Any] | None,
    thermal_class: str,
) -> dict[str, Any]:
    plan_data = plan if isinstance(plan, dict) else {}
    return validation_contracts.validation_document(
        schema=_schema(schema_prefix, "mode_validate_v1"),
        version=version,
        generated_at=generated_at,
        checks=checks,
        strict=strict,
        scope="Abyss Machine work-mode contract",
        extra={
            "paths": dict(paths) if isinstance(paths, dict) else {},
            "plan": {
                "selected_mode": plan_data.get("selected_mode"),
                "effective_mode": plan_data.get("effective_mode"),
                "thermal_class": thermal_class,
                "hardware_targets": plan_data.get("hardware_targets"),
                "launch_policy": plan_data.get("launch_policy"),
                "reasons": plan_data.get("reasons"),
            },
            "non_claims": [
                "Mode validation does not run heavy workloads.",
                "Warnings about current fan/power state may clear on the next root timer reconcile.",
                "The AI mode is a host overlay, not a GNOME fourth power-profile entry.",
            ],
        },
    )


def definitions(policy: dict[str, Any]) -> list[dict[str, Any]]:
    profiles = policy.get("profiles", {}) if isinstance(policy.get("profiles"), dict) else {}
    items: list[dict[str, Any]] = []
    for name in ("saver", "balanced", "performance", "ai"):
        profile = profiles.get(name, {}) if isinstance(profiles.get(name), dict) else {}
        items.append(
            {
                "name": name,
                "power_profile": profile.get("power_profile") or MODE_TO_POWER_PROFILE[name],
                "cooling_profile": profile.get("cooling_profile"),
                "ac_allowed": profile.get("ac_allowed", True),
                "battery_allowed": profile.get("battery_allowed", "armed" if name != "saver" else True),
                "ai_overlay": bool(profile.get("ai_overlay", name == "ai")),
                "max_unattended_class_ac": profile.get("max_unattended_class_ac"),
                "max_unattended_class_battery": profile.get("max_unattended_class_battery"),
                "description": profile.get("description") or "",
            }
        )
    return items


def target_profile(selected_mode: str, ac_online: bool, policy: dict[str, Any]) -> tuple[str, str, str | None]:
    if not ac_online and selected_mode != "saver":
        return "saver", "power-saver", "battery"
    effective = selected_mode if selected_mode in VALID_MODES else "balanced"
    profile = profile_policy(policy, effective)
    return effective, str(profile.get("power_profile") or MODE_TO_POWER_PROFILE[effective]), None


def latest_summary(value: Any, keys: tuple[str, ...]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {key: value.get(key) for key in keys}


def plan_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    selected: str,
    effective: str,
    state_file: str,
    policy_path: str,
    profile: dict[str, Any],
    target_profile_name: str,
    current_profile: str | None,
    current_mode: str | None,
    external_profile_guard: dict[str, Any],
    cooling: dict[str, Any],
    cooling_normalized: str,
    cooling_target: dict[str, Any],
    temperature: dict[str, Any],
    thermal_class: str,
    battery: dict[str, Any],
    cpu_routed_heavy: dict[str, Any],
    degraded_reason: str | None,
    storage_pressure_latest: dict[str, Any],
    memory_plan_latest: dict[str, Any],
    process_latest: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    ac_online = bool(battery.get("ac_online"))
    max_unattended = max_unattended_class(
        profile=profile,
        thermal_class=thermal_class,
        effective_mode=effective,
        ac_online=ac_online,
        policy=policy,
    )
    max_level = workload_level(max_unattended)
    heavy_allowed = max_level >= workload_level("heavy")
    sustained_allowed = max_level >= workload_level("sustained")
    reasons: list[str] = []
    if degraded_reason:
        reasons.append(f"effective_degraded:{degraded_reason}")
    if current_profile != target_profile_name:
        if ac_online and external_profile_guard.get("preserve_external_boost"):
            reasons.append(f"power_profile_external_boost:{current_profile}->{target_profile_name}")
        else:
            reasons.append(f"power_profile_drift:{current_profile}->{target_profile_name}")
    if thermal_class in {"hot", "critical"}:
        reasons.append(f"thermal_gate:{thermal_class}")
    if not ac_online:
        reasons.append("battery_discharging")
    if storage_pressure_latest.get("load_error"):
        reasons.append("storage_pressure_unavailable")
    if memory_plan_latest.get("load_error"):
        reasons.append("memory_plan_unavailable")
    if process_latest.get("load_error"):
        reasons.append("process_snapshot_unavailable")

    return {
        "schema": _schema(schema_prefix, "mode_plan_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "selected_mode": selected,
        "effective_mode": effective,
        "state_file": state_file,
        "policy": {
            "path": policy_path,
            "profile": profile,
            "contract": "GNOME power profile selects the base mode; Abyss Machine adds cooling, launch-gate and routing policy.",
        },
        "hardware_targets": {
            "power_profile": target_profile_name,
            "cooling_profile": cooling_normalized,
            "platform_profile": cooling_target.get("platform_profile"),
            "fan_mode": cooling_target.get("fan_mode"),
            "current_power_profile": current_profile,
            "current_mode_from_power_profile": current_mode,
            "profile_matches_target": current_profile == target_profile_name,
            "external_power_profile_guard": external_profile_guard,
            "cooling_recommendation": {
                "recommended_profile": cooling.get("recommended_profile"),
                "reasons": cooling.get("reasons"),
                "current": cooling.get("current"),
            },
        },
        "operating": {
            "thermal_class": thermal_class,
            "temperature": temperature,
            "battery": battery,
            "storage_pressure_latest": storage_pressure_latest,
            "memory_plan_latest": memory_plan_latest,
            "process_latest": process_latest,
        },
        "launch_policy": {
            "max_unattended_class": max_unattended,
            "can_start_heavy_unattended": heavy_allowed,
            "can_start_sustained_unattended": sustained_allowed,
            "operator_force_supported": True,
            "do_not_kill_running_tasks": True,
            "gate_new_unattended_tasks": True,
            "cpu_route_commands": {
                "probe": "abyss-machine ai cpu route --class probe --json",
                "light": "abyss-machine ai cpu route --class light --json",
                "medium": "abyss-machine ai cpu route --class medium --json",
                "heavy": "abyss-machine ai cpu route --class heavy --json",
                "sustained": "abyss-machine ai cpu route --class sustained --json",
            },
            "cpu_routed_heavy": {
                "can_start": bool(cpu_routed_heavy.get("allowed")),
                "can_start_unattended": bool(cpu_routed_heavy.get("unattended_allowed")),
                "requires_route_application": bool(cpu_routed_heavy.get("requires_routing")),
                "command": "abyss-machine ai cpu route --class heavy --json",
                "policy": cpu_routed_heavy,
            },
            "ai_policy_command": "abyss-machine ai policy --json",
            "memory_gate_command": "abyss-machine memory plan --json",
            "storage_write_gate": "abyss-machine storage write-preflight --kind KIND --bytes BYTES --target PATH --json",
        },
        "actions_on_reconcile": [
            {"action": "set_power_profile", "target": target_profile_name, "needed": current_profile != target_profile_name},
            {"action": "cooling_apply", "target": "auto", "recommended_profile": cooling.get("recommended_profile")},
        ],
        "reasons": reasons,
        "non_claims": [
            "Mode plan does not start or stop workloads.",
            "Hot/critical states defer new unattended heavy work but do not terminate already running operator work.",
            "CPU routes are hints that callers must apply explicitly.",
        ],
    }


def status_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    refs: dict[str, Any],
    state: dict[str, Any],
    selected: str,
    effective: str,
    target_profile_name: str,
    current_profile: str | None,
    external_profile_guard: dict[str, Any],
    degraded_reason: str | None,
    battery: dict[str, Any],
    sensors: dict[str, Any],
    ai_ready: bool,
    ai: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    ac_online = bool(battery.get("ac_online"))
    protected_external_boost = bool(ac_online and external_profile_guard.get("preserve_external_boost"))
    degraded_reasons: list[str] = []
    if degraded_reason:
        degraded_reasons.append(degraded_reason)
    if selected == "ai" and not ai_ready:
        degraded_reasons.append("ai_stack_incomplete")
    if current_profile != target_profile_name and not protected_external_boost:
        degraded_reasons.append("power_profile_drift")
    return {
        "schema": _schema(schema_prefix, "mode_status_v1"),
        "version": version,
        "generated_at": generated_at,
        "root": str(refs["root"]),
        "agent_entrypoint": str(refs["agent_entrypoint"]),
        "state_file": str(refs["state"]),
        "policy": str(refs["policy"]),
        "selected_mode": selected,
        "effective_mode": effective,
        "last_non_ai_mode": state.get("last_non_ai_mode", "balanced"),
        "ai_selected": selected == "ai",
        "ai_active": selected == "ai" and effective == "ai" and current_profile == "performance",
        "degraded": bool(degraded_reasons),
        "degraded_reasons": degraded_reasons,
        "target_power_profile": target_profile_name,
        "actual_power_profile": current_profile,
        "profile_matches_target": current_profile == target_profile_name,
        "power_profile_external_boost": protected_external_boost,
        "external_power_profile_guard": external_profile_guard,
        "forced_saver_on_battery": bool(state.get("forced_saver_on_battery", False)),
        "battery": battery,
        "thermal": sensors,
        "ai": {
            "ready": ai_ready,
            "dev_dri_present": ai.get("dev_dri_present"),
            "dev_accel_present": ai.get("dev_accel_present"),
            "openvino_venv_exists": ai.get("openvino_venv_exists"),
            "openvino_python": ai.get("openvino_python"),
            "openvino_benchmark": ai.get("openvino_benchmark"),
        },
        "operating": plan.get("operating"),
        "hardware_targets": plan.get("hardware_targets"),
        "launch_policy": plan.get("launch_policy"),
        "plan_latest": str(refs["plan_latest"]),
        "validate_latest": str(refs["validate_latest"]),
    }


def reconcile_light_status_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    refs: dict[str, Any],
    state: dict[str, Any],
    battery: dict[str, Any],
    selected: str,
    effective: str,
    target_profile_name: str,
    current_profile: str | None,
    degraded_reason: str | None,
    external_profile_guard: dict[str, Any],
    actions: list[dict[str, Any]],
) -> dict[str, Any]:
    ac_online = bool(battery.get("ac_online"))
    protected_external_boost = bool(ac_online and external_profile_guard.get("preserve_external_boost"))
    degraded_reasons: list[str] = []
    if degraded_reason:
        degraded_reasons.append(degraded_reason)
    if current_profile != target_profile_name and not protected_external_boost:
        degraded_reasons.append("power_profile_drift")
    return {
        "schema": _schema(schema_prefix, "mode_reconcile_light_status_v1"),
        "version": version,
        "generated_at": generated_at,
        "root": str(refs["root"]),
        "state_file": str(refs["state"]),
        "policy": str(refs["policy"]),
        "selected_mode": selected,
        "effective_mode": effective,
        "last_non_ai_mode": state.get("last_non_ai_mode", "balanced"),
        "ai_selected": selected == "ai",
        "ai_active": selected == "ai" and effective == "ai" and current_profile == "performance",
        "degraded": bool(degraded_reasons),
        "degraded_reasons": degraded_reasons,
        "target_power_profile": target_profile_name,
        "actual_power_profile": current_profile,
        "profile_matches_target": current_profile == target_profile_name,
        "power_profile_external_boost": protected_external_boost,
        "external_power_profile_guard": external_profile_guard,
        "forced_saver_on_battery": bool(state.get("forced_saver_on_battery", False)),
        "battery": battery,
        "actions": actions,
        "full_status_command": "abyss-machine mode status --json",
        "policy_note": "Light reconcile is used by the periodic timer; it avoids full mode plan/status rebuilds under load.",
    }


def modes_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    status_data: dict[str, Any],
    available_modes: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "modes_v1"),
        "version": version,
        "generated_at": generated_at,
        "current_power_profile": status_data["actual_power_profile"],
        "selected_mode": status_data["selected_mode"],
        "effective_mode": status_data["effective_mode"],
        "battery": status_data["battery"],
        "host_policy": {
            "service": "abyss-power-profile-auto",
            "battery_policy": "force power-saver while discharging",
            "ac_policy": "preserve or restore operator-selected balanced/performance/ai",
        },
        "available_modes": available_modes,
    }


def path_strings(value: Any) -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for item in value.values():
            paths.extend(path_strings(item))
    elif isinstance(value, list):
        for item in value:
            paths.extend(path_strings(item))
    elif isinstance(value, str) and value.startswith("/"):
        paths.append(value)
    return paths


def policy_validation(policy: dict[str, Any], valid_cooling_profiles: set[str] | None = None) -> dict[str, Any]:
    valid_cooling = valid_cooling_profiles or VALID_COOLING_PROFILES
    profiles = policy.get("profiles", {}) if isinstance(policy.get("profiles"), dict) else {}
    missing_profiles = [name for name in ("saver", "balanced", "performance", "ai") if name not in profiles]
    invalid_profiles: list[dict[str, Any]] = []
    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            invalid_profiles.append({"profile": name, "issue": "profile is not an object"})
            continue
        power = profile.get("power_profile")
        if power not in VALID_POWER_PROFILES:
            invalid_profiles.append({"profile": name, "issue": "invalid power_profile", "value": power})
        cooling = profile.get("cooling_profile")
        if cooling and cooling not in valid_cooling:
            invalid_profiles.append({"profile": name, "issue": "invalid cooling_profile", "value": cooling})
        for key in ("max_unattended_class_ac", "max_unattended_class_battery"):
            if profile.get(key) not in VALID_WORKLOAD_CLASSES:
                invalid_profiles.append({"profile": name, "issue": f"invalid {key}", "value": profile.get(key)})

    thermal_policy = policy.get("thermal_launch_policy", {}) if isinstance(policy.get("thermal_launch_policy"), dict) else {}
    missing_thermal = [name for name in ("green", "warm", "hot", "critical", "unknown") if name not in thermal_policy]
    invalid_thermal: list[dict[str, Any]] = []
    for name, item in thermal_policy.items():
        if not isinstance(item, dict):
            invalid_thermal.append({"class": name, "issue": "thermal policy item is not an object"})
            continue
        cap = item.get("max_unattended_class_cap")
        if cap not in VALID_WORKLOAD_CLASSES:
            invalid_thermal.append({"class": name, "issue": "invalid max_unattended_class_cap", "value": cap})
    return {
        "missing_profiles": missing_profiles,
        "invalid_profiles": invalid_profiles,
        "missing_thermal": missing_thermal,
        "invalid_thermal": invalid_thermal,
    }

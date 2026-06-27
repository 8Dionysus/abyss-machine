from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any


VALID_COOLING_PROFILES = {"auto", "saver", "balanced", "performance", "emergency", "firmware-auto"}
LENOVO_FAN_MODE_LABELS = {
    0: "super_silent",
    1: "standard",
    2: "dust_cleaning",
    4: "efficient_thermal_dissipation",
    16: "firmware_auto_observed",
}
BROKEN_ACPI_COOLING_PATHS = {
    r"\_TZ_.FAN0",
    r"\_TZ_.FAN1",
    r"\_TZ_.FAN2",
    r"\_TZ_.FAN3",
    r"\_TZ_.FAN4",
    r"\VFAN",
}
DEFAULT_PROFILES = {
    "saver": {"platform_profile": "low-power", "fan_mode": 0},
    "balanced": {"platform_profile": "balanced", "fan_mode": 1},
    "performance": {"platform_profile": "performance", "fan_mode": 4},
    "emergency": {"platform_profile": None, "fan_mode": 4},
    "firmware-auto": {"platform_profile": None, "fan_mode": None},
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


def nested_get(data: Any, path: list[str]) -> Any:
    value = data
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def float_config(config: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(config.get(key, default))
    except (TypeError, ValueError):
        return default


def int_config(config: dict[str, Any], key: str, default: int) -> int:
    try:
        return int(config.get(key, default))
    except (TypeError, ValueError):
        return default


def default_config(schema_prefix: str, version: str) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "cooling_config_v1"),
        "version": version,
        "profiles": dict(DEFAULT_PROFILES),
        "auto": {
            "hot_temperature_c": 106.0,
            "critical_temperature_c": 109.0,
            "recovery_temperature_c": 96.0,
            "hold_emergency_above_c": 100.0,
            "use_selected_mode_after_recovery": True,
        },
        "rapl_smoothing": {
            "enabled": False,
            "backend": "intel-rapl-mmio",
            "apply_modes": ["performance", "ai"],
            "normal_pl1_uw": 35000000,
            "cap_pl1_uw": 28000000,
            "engage_temperature_c": 106.0,
            "engage_package_throttle_per_s": 1200.0,
            "engage_sample_count": 2,
            "release_temperature_c": 102.0,
            "release_package_throttle_per_s": 250.0,
            "release_sample_count": 2,
            "min_sample_seconds": 5.0,
            "max_sample_seconds": 180.0,
            "restore_when_not_applicable": True,
        },
        "notes": [
            "fan_mode 4 is documented by the ideapad-laptop ABI as Efficient Thermal Dissipation Mode.",
            "fan_mode 1 is documented standard mode and is the balanced writable target.",
            "fan_mode 0 is documented super-silent mode and is the saver writable target.",
            "fan_mode 16 was observed as a firmware-default readback value on this machine, but writing it returned EINVAL on 2026-05-06; do not use 16 as an auto-policy write target.",
            "Do not read acpi_fan fan*_input on this BIOS because it emits ACPI \\VFAN._FST / \\_SB.FANL errors.",
            "Do not read or write ACPI cooling devices \\_TZ_.FAN0..FAN4 or \\VFAN on this BIOS; FAN0..FAN4 emit missing \\_SB.PC00.LPCB.UPFS errors and VFAN emits missing \\_SB.FANL errors.",
            "100-105C is a monitored active operating range for this thin laptop; route by trend, duration, and throttle evidence instead of treating a stable high package temperature as a failure.",
            "RAPL smoothing is an optional temporary PL1 cap for heat-saturated performance/ai sessions above the watch range; it must restore the normal PL1 and never change TCC offset, BD PROCHOT, raw EC/PWM, or running process affinity.",
        ],
    }


def config_document(
    *,
    schema_prefix: str,
    version: str,
    loaded: Any,
    load_error: Any,
) -> dict[str, Any]:
    defaults = default_config(schema_prefix, version)
    if isinstance(loaded, dict):
        return deep_merge(defaults, loaded)
    if load_error and load_error != "missing":
        defaults["_load_error"] = load_error
    return defaults


def rapl_smoothing_config(config: dict[str, Any]) -> dict[str, Any]:
    raw = config.get("rapl_smoothing", {})
    overrides = raw if isinstance(raw, dict) else {}
    defaults = default_config(str(config.get("schema", "abyss_machine")).removesuffix("_cooling_config_v1"), str(config.get("version", ""))).get("rapl_smoothing", {})
    return deep_merge(defaults if isinstance(defaults, dict) else {}, overrides)


def paths_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    refs: dict[str, Any],
    daily_paths: dict[str, Any],
) -> dict[str, Any]:
    action_root = Path(str(refs["action_root"]))
    audit_root = Path(str(refs["thermal_audit_root"]))
    validate_root = Path(str(refs["fan_validate_root"]))
    series_root = Path(str(refs["fan_series_root"]))
    rapl_root = Path(str(refs["rapl_smoothing_root"]))
    return {
        "schema": _schema(schema_prefix, "cooling_paths_v1"),
        "version": version,
        "generated_at": generated_at,
        "root": str(refs["root"]),
        "agent_entrypoint": str(refs["agent_entrypoint"]),
        "index": str(refs["index"]),
        "config": str(refs["config"]),
        "latest": str(refs["latest"]),
        "actions": {
            "root": str(action_root),
            "today": str(daily_paths["actions_today"]),
            "daily_glob": str(action_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        },
        "thermal_audit": {
            "root": str(audit_root),
            "latest": str(refs["thermal_audit_latest"]),
            "today": str(daily_paths["thermal_audit_today"]),
            "daily_glob": str(audit_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        },
        "fan_validate": {
            "root": str(validate_root),
            "latest": str(refs["fan_validate_latest"]),
            "today": str(daily_paths["fan_validate_today"]),
            "daily_glob": str(validate_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        },
        "fan_series": {
            "root": str(series_root),
            "latest": str(refs["fan_series_latest"]),
            "today": str(daily_paths["fan_series_today"]),
            "daily_glob": str(series_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        },
        "rapl_smoothing": {
            "root": str(rapl_root),
            "latest": str(refs["rapl_smoothing_latest"]),
            "state": str(refs["rapl_smoothing_state"]),
            "today": str(daily_paths["rapl_smoothing_today"]),
            "daily_glob": str(rapl_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        },
        "systemd": {
            "service": str(refs["service"]),
            "timer": str(refs["timer"]),
        },
        "commands": {
            "status": "abyss-machine cooling status --json",
            "paths": "abyss-machine cooling paths --json",
            "recommend": "abyss-machine cooling recommend --json",
            "apply_auto": "abyss-machine cooling apply --profile auto --json",
            "validate": "abyss-machine cooling validate --json",
            "rapl_smoothing": "abyss-machine cooling rapl-smoothing --json",
        },
        "policy_contract": {
            "host_mutation": False,
            "apply_requires_explicit_command": True,
            "live_collectors_enabled_by_paths": False,
            "repo_mutation": False,
        },
    }


def state_document(*, schema_prefix: str, version: str, raw_state: Any) -> dict[str, Any]:
    state = raw_state if isinstance(raw_state, dict) else {}
    return {
        "schema": _schema(schema_prefix, "cooling_rapl_smoothing_state_v1"),
        "version": version,
        "active": bool(state.get("active", False)),
        "last_sample_epoch": state.get("last_sample_epoch"),
        "last_package_throttle_count": state.get("last_package_throttle_count"),
        "engage_count": int(state.get("engage_count") or 0),
        "release_count": int(state.get("release_count") or 0),
        "baseline_pl1_uw": state.get("baseline_pl1_uw"),
        "updated_at": state.get("updated_at"),
        "updated_by": state.get("updated_by"),
        "last_action": state.get("last_action"),
    }


def state_payload(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    state: dict[str, Any],
    updated_by: str,
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "cooling_rapl_smoothing_state_v1"),
        "version": version,
        "active": bool(state.get("active", False)),
        "last_sample_epoch": state.get("last_sample_epoch"),
        "last_package_throttle_count": state.get("last_package_throttle_count"),
        "engage_count": int(state.get("engage_count") or 0),
        "release_count": int(state.get("release_count") or 0),
        "baseline_pl1_uw": state.get("baseline_pl1_uw"),
        "updated_at": generated_at,
        "updated_by": updated_by,
        "last_action": state.get("last_action"),
    }


def rapl_smoothing_status_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    config: dict[str, Any],
    state: dict[str, Any],
    rapl_mmio: dict[str, Any],
    package_throttle_count: int | None,
    refs: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "cooling_rapl_smoothing_status_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "enabled": bool(config.get("enabled", False)),
        "config": {
            "apply_modes": config.get("apply_modes"),
            "normal_pl1_uw": config.get("normal_pl1_uw"),
            "cap_pl1_uw": config.get("cap_pl1_uw"),
            "engage_temperature_c": config.get("engage_temperature_c"),
            "engage_package_throttle_per_s": config.get("engage_package_throttle_per_s"),
            "release_temperature_c": config.get("release_temperature_c"),
            "release_package_throttle_per_s": config.get("release_package_throttle_per_s"),
        },
        "state": state,
        "rapl_mmio": rapl_mmio,
        "package_throttle_count": package_throttle_count,
        "paths": {
            "latest": str(refs["latest"]),
            "state": str(refs["state"]),
            "daily_glob": str(Path(str(refs["root"])) / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        },
        "policy": {
            "automation_route": "existing abyss-power-profile-auto.timer via cooling apply auto",
            "temporary_only": True,
            "never_changes": ["TCC offset", "BD PROCHOT", "raw EC/PWM", "running process affinity"],
        },
    }


def status_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    paths: dict[str, Any],
    config_path: str,
    config_exists: bool,
    config_load_error: Any,
    temperature: dict[str, Any],
    episode: dict[str, Any],
    fan: dict[str, Any],
    cooling_devices: list[dict[str, Any]],
    rapl_smoothing: dict[str, Any],
    power: dict[str, Any],
    services: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "cooling_status_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "paths": paths,
        "config": {
            "path": config_path,
            "exists": config_exists,
            "load_error": config_load_error,
        },
        "temperature": {
            "class": temperature.get("class"),
            "summary": {key: value for key, value in temperature.items() if key not in {"hwmon", "thermal_zones"}},
            "episode": episode,
            "thermal_zones": temperature.get("thermal_zones", []),
        },
        "fan": fan,
        "cooling_devices": cooling_devices,
        "rapl_smoothing": rapl_smoothing,
        "power": power,
        "services": services,
        "policy": {
            "backend": "platform_profile + Lenovo VPC2004 fan_mode",
            "rpm_reading": "not used; acpi_fan fan*_input is known-broken on this BIOS",
            "safe_control_rule": "Only write documented platform_profile values and Lenovo fan_mode values from config; never force raw EC/PWM registers.",
        },
    }


def mode_from_power_profile_name(profile: str | None) -> str:
    if profile == "performance":
        return "performance"
    if profile == "power-saver":
        return "saver"
    return "balanced"


def selected_mode_for_recommendation(
    *,
    selected_mode: str | None,
    power_profile_name: str | None,
    ac_online: bool,
) -> str:
    mode = str(selected_mode or "balanced")
    if mode not in {"saver", "balanced", "performance", "ai"}:
        mode = mode_from_power_profile_name(power_profile_name)
    if not ac_online:
        mode = "saver"
    if mode == "ai":
        mode = "performance"
    return mode


def recommendation_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    status_data: dict[str, Any],
    config: dict[str, Any],
    selected_mode: str,
    recent_emergency: dict[str, Any],
    config_path: str,
) -> dict[str, Any]:
    auto = config.get("auto", {}) if isinstance(config.get("auto"), dict) else {}
    current_fan = nested_get(status_data, ["fan", "fan_mode"])
    temp = nested_get(status_data, ["temperature", "summary", "temperature_c_max"])
    thermal_class = nested_get(status_data, ["temperature", "class"]) or "unknown"
    profile = selected_mode
    reasons: list[str] = [f"selected_mode={selected_mode}"]
    hysteresis_recent = recent_emergency
    if isinstance(temp, (int, float)):
        critical = float(auto.get("critical_temperature_c", 109.0))
        hot = float(auto.get("hot_temperature_c", 106.0))
        hold = float(auto.get("hold_emergency_above_c", 100.0))
        recovery = float(auto.get("recovery_temperature_c", 96.0))
        min_hold_seconds = float(auto.get("min_emergency_hold_seconds", 0.0))
        if temp >= critical or thermal_class == "critical":
            profile = "emergency"
            reasons.append(f"temperature_c_max>={critical}")
        elif temp >= hot or thermal_class == "hot":
            profile = "emergency"
            reasons.append(f"temperature_c_max>={hot}")
        elif recent_emergency.get("active"):
            profile = "emergency"
            reasons.append(
                "min_emergency_hold_"
                f"{int(min_hold_seconds)}s_since_origin_elapsed_{recent_emergency.get('elapsed_seconds')}s"
            )
        elif current_fan == 4 and temp >= hold:
            profile = "emergency"
            reasons.append(f"hold_emergency_until_below_{hold}C")
        elif current_fan == 4 and temp > recovery:
            profile = "emergency"
            reasons.append(f"hysteresis_emergency_until_below_{recovery}C")
        elif temp <= recovery:
            reasons.append(f"recovered_below_{recovery}C")
    else:
        hysteresis_recent = {}
        reasons.append("temperature_unknown_use_selected_mode")

    return {
        "schema": _schema(schema_prefix, "cooling_recommendation_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "recommended_profile": profile,
        "reasons": reasons,
        "temperature": {
            **(status_data.get("temperature", {}).get("summary", {}) if isinstance(status_data.get("temperature"), dict) else {}),
            "episode": nested_get(status_data, ["temperature", "episode"]),
        },
        "hysteresis": {
            "recent_emergency": hysteresis_recent,
            "min_emergency_hold_seconds": nested_get(auto, ["min_emergency_hold_seconds"]),
        },
        "current": {
            "fan_mode": current_fan,
            "platform_profile": nested_get(status_data, ["power", "platform_profile", "current"]),
            "power_profile": nested_get(status_data, ["power", "powerprofilesctl"]),
        },
        "config_path": config_path,
    }


def profile_targets(
    *,
    profile: str,
    config: dict[str, Any],
    recommendation: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    normalized = str(profile or "auto").strip().lower()
    if normalized not in VALID_COOLING_PROFILES:
        normalized = "auto"
    if normalized == "auto" and isinstance(recommendation, dict):
        normalized = str(recommendation.get("recommended_profile") or "balanced")
    profiles = config.get("profiles", {}) if isinstance(config.get("profiles"), dict) else {}
    target = profiles.get(normalized)
    if not isinstance(target, dict):
        target = DEFAULT_PROFILES.get(normalized, {})
    return normalized, dict(target)


def apply_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    requested_profile: str,
    applied_profile: str,
    updated_by: str,
    permission_required: bool,
    actions: list[dict[str, Any]],
    recommendation: dict[str, Any] | None,
    status_before: dict[str, Any],
    status_after: dict[str, Any],
    paths: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "cooling_apply_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": all(bool(action.get("ok")) for action in actions) if actions else True,
        "requested_profile": requested_profile,
        "applied_profile": applied_profile,
        "updated_by": updated_by,
        "permission_required": permission_required,
        "actions": actions,
        "recommendation": recommendation,
        "status_before": {
            "temperature": status_before.get("temperature", {}).get("summary", {}),
            "fan": status_before.get("fan", {}),
            "power": status_before.get("power", {}),
        },
        "status_after": status_after,
        "paths": paths,
    }


def parse_levels(raw: str | list[int] | tuple[int, ...] | None) -> list[int]:
    if raw is None:
        return [50]
    if isinstance(raw, (list, tuple)):
        return [int(item) for item in raw]
    levels: list[int] = []
    for part in str(raw).split(","):
        part = part.strip()
        if not part:
            continue
        levels.append(int(part))
    return levels or [50]


def normalize_fan_series_inputs(
    *,
    level: int,
    repeats: int,
    seconds: float,
    interval: float,
    cooldown: float,
    state_label: str,
) -> dict[str, Any]:
    return {
        "level": int(level),
        "repeats": max(1, min(int(repeats), 10)),
        "seconds": max(1.0, min(float(seconds), 60.0)),
        "interval": max(0.5, min(float(interval), 10.0)),
        "cooldown": max(0.0, min(float(cooldown), 60.0)),
        "state_label": re.sub(r"[^a-zA-Z0-9_.:-]+", "_", str(state_label or "current")).strip("_") or "current",
    }


def fan_series_decision(
    *,
    compact_results: list[dict[str, Any]],
    repeats: int,
    permission_required: bool,
) -> dict[str, Any]:
    deltas = [
        nested_get(item, ["action", "temperature_c_max_delta"])
        for item in compact_results
        if isinstance(nested_get(item, ["action", "temperature_c_max_delta"]), (int, float))
    ]
    kernel_ok_count = sum(1 for item in compact_results if nested_get(item, ["action", "kernel_ok"]) is True)
    write_ok_count = sum(1 for item in compact_results if item.get("ok") is True)
    possible_effect_count = sum(
        1 for item in compact_results
        if nested_get(item, ["action", "verdict"]) == "write_path_ok_possible_cooling_effect"
    )
    repeated_write_ok = write_ok_count == len(compact_results) and len(compact_results) == repeats
    repeated_kernel_ok = kernel_ok_count == len(compact_results) and len(compact_results) == repeats
    repeated_possible_effect = possible_effect_count >= max(2, math.ceil(repeats * 0.6)) if repeats >= 2 else possible_effect_count == 1
    automation_candidate = bool(repeated_write_ok and repeated_kernel_ok and repeated_possible_effect)
    decision_reason = "insufficient repeated evidence"
    if automation_candidate:
        decision_reason = "repeated write path and short-window cooling effect observed; still requires separate operator approval before automation"
    if permission_required:
        decision_reason = "root permission required"
    return {
        "summary": {
            "runs": len(compact_results),
            "write_ok_count": write_ok_count,
            "kernel_ok_count": kernel_ok_count,
            "possible_effect_count": possible_effect_count,
            "temperature_c_max_delta_avg": round(sum(float(item) for item in deltas) / len(deltas), 1) if deltas else None,
            "temperature_c_max_delta_min": round(min(float(item) for item in deltas), 1) if deltas else None,
            "temperature_c_max_delta_max": round(max(float(item) for item in deltas), 1) if deltas else None,
            "compact_results": compact_results,
        },
        "decision": {
            "automation_candidate": automation_candidate,
            "automation_allowed": False,
            "production_ready": False,
            "reason": decision_reason,
            "next_gate": "Only add TFN1 to auto-policy after explicit operator approval and a guarded hysteresis design.",
        },
    }

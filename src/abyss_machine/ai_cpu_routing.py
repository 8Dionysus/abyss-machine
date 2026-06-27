from __future__ import annotations

from typing import Any


def _nested_get(data: Any, path: list[str]) -> Any:
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def bool_value(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() not in {"0", "false", "no", "off"}
    if value is None:
        return default
    return bool(value)


def int_config_value(config: dict[str, Any], key: str, default: int, minimum: int = 0) -> int:
    try:
        value = int(config.get(key, default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


def compress_cpu_list(cpus: list[int] | tuple[int, ...] | set[int]) -> str:
    ordered = sorted({int(cpu) for cpu in cpus})
    if not ordered:
        return ""
    ranges: list[str] = []
    start = ordered[0]
    previous = ordered[0]
    for cpu in ordered[1:]:
        if cpu == previous + 1:
            previous = cpu
            continue
        ranges.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = cpu
    ranges.append(str(start) if start == previous else f"{start}-{previous}")
    return ",".join(ranges)


def workload_level(name: str | None) -> int:
    values = {
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
    return values.get(str(name or "light").strip().lower(), 1)


def class_from_capacity(capacity: int | None, max_capacity: int | None, max_freq_khz: int | None) -> tuple[str, str]:
    if capacity is not None and max_capacity:
        ratio = float(capacity) / float(max_capacity)
        if ratio >= 0.85:
            return "p_core", "cpu_capacity_ratio>=0.85"
        if ratio <= 0.35:
            return "lp_e_core", "cpu_capacity_ratio<=0.35"
        return "e_core", "cpu_capacity_ratio"
    if max_freq_khz is not None:
        if max_freq_khz >= 5_000_000:
            return "p_core", "cpuinfo_max_freq>=5000000"
        if max_freq_khz <= 3_000_000:
            return "lp_e_core", "cpuinfo_max_freq<=3000000"
        return "e_core", "cpuinfo_max_freq"
    return "unknown", "missing_capacity_and_frequency"


def normalize_workload(workload_class: str) -> str:
    aliases = {
        "bg": "background",
        "small": "light",
        "normal": "medium",
        "interactive": "interactive",
        "long": "sustained",
    }
    workload = aliases.get(str(workload_class).strip().lower(), str(workload_class).strip().lower())
    if workload not in {"background", "probe", "light", "interactive", "medium", "heavy", "sustained"}:
        return "medium"
    return workload


def normalize_latency(latency: str | None) -> str:
    value = str(latency or "balanced").strip().lower()
    if value not in {"background", "balanced", "interactive"}:
        return "balanced"
    return value


def thread_limit(config: dict[str, Any], workload_class: str, selected_cpus: list[int]) -> int:
    routing_config = config.get("cpu_routing", {}) if isinstance(config.get("cpu_routing"), dict) else {}
    limits = routing_config.get("thread_limits", {}) if isinstance(routing_config.get("thread_limits"), dict) else {}
    default = int(limits.get(workload_class, limits.get("medium", 4)) or 4)
    if not selected_cpus:
        return 0
    return max(1, min(default, len(selected_cpus)))


def env_for_threads(limit: int) -> dict[str, str]:
    value = str(max(1, int(limit)))
    return {
        "OMP_NUM_THREADS": value,
        "MKL_NUM_THREADS": value,
        "OPENBLAS_NUM_THREADS": value,
        "NUMEXPR_NUM_THREADS": value,
        "TOKENIZERS_PARALLELISM": "false",
    }


def select_route_cpus(
    workload_class: str,
    latency: str,
    thermal_map: dict[str, Any],
    *,
    config: dict[str, Any],
    force: bool = False,
) -> tuple[list[int], str]:
    available = thermal_map.get("available_by_role", {}) if isinstance(thermal_map.get("available_by_role"), dict) else {}
    p = [int(cpu) for cpu in available.get("p_cores", [])]
    e = [int(cpu) for cpu in available.get("e_cores", [])]
    lp = [int(cpu) for cpu in available.get("lp_e_cores", [])]
    unknown = [int(cpu) for cpu in available.get("unknown", [])]
    thermal_class = str(thermal_map.get("class") or "unknown")
    package_temp = _nested_get(thermal_map, ["summary", "package_temperature_c_max"])
    routing_config = config.get("cpu_routing", {}) if isinstance(config.get("cpu_routing"), dict) else {}
    package_critical_threshold = float(
        routing_config.get(
            "package_critical_temperature_c",
            _nested_get(thermal_map, ["thresholds", "package_critical_temperature_c"]) or 109.0,
        )
    )

    if workload_class == "background":
        cpus = lp or e[:2] or unknown[:2] or p[:1]
        return cpus, "lp_e_first_background"
    if workload_class == "probe":
        cpus = (lp + e[:2]) or e or unknown[:2] or p[:1]
        return cpus, "low_pressure_probe"
    if workload_class == "light":
        if latency == "interactive" and thermal_class in {"green", "warm"}:
            cpus = p[:1] + e[:3] + lp
            return cpus or e or lp, "interactive_light_with_one_cool_p_core"
        return (e[:3] + lp) or p[:1] or unknown[:2], "e_core_light"
    if workload_class == "interactive":
        if thermal_class in {"green", "warm"}:
            cpus = p[:2] + e[:4] + lp
            return cpus or e or lp, "latency_with_bounded_p_cores"
        cpus = e[:4] + lp
        return cpus or p[:1] or unknown[:2], "hot_latency_avoid_hot_p_cores"
    if workload_class == "medium":
        if thermal_class in {"hot", "critical"}:
            cpus = e + lp
            return cpus or p[:1] or unknown[:2], "hot_medium_e_lp_only"
        cpus = e[:4] + p[:2] + lp
        return cpus or unknown[:2], "balanced_medium_hybrid_safe"
    if workload_class == "heavy":
        if thermal_class in {"hot", "critical"} and not force:
            cpus = e + lp
            return cpus, "heavy_deferred_hot_report_safe_cpu_set"
        if isinstance(package_temp, (int, float)) and package_temp >= package_critical_threshold and not force:
            cpus = e + lp
            return cpus, "heavy_deferred_package_critical_report_safe_cpu_set"
        cpus = p[:2] + e[:6] + lp
        return cpus or unknown[:4], "heavy_bounded_hybrid"
    if workload_class == "sustained":
        if thermal_class in {"hot", "critical"} and not force:
            cpus = e + lp
            return cpus, "sustained_deferred_hot_report_safe_cpu_set"
        cpus = e[:6] + p[:2] + lp
        return cpus or unknown[:4], "sustained_bounded_hybrid"
    return (e[:4] + lp) or p[:1] or unknown[:2], "fallback_e_lp_first"


def routed_heavy_policy(
    thermal_map: dict[str, Any],
    policy_class: str,
    effective_mode: str | None,
    ac_online: bool,
    *,
    config: dict[str, Any],
    capacity_percent: Any = None,
    trend: str = "unknown",
) -> dict[str, Any]:
    thermal_config = config.get("thermal_policy", {}) if isinstance(config.get("thermal_policy"), dict) else {}
    routing_config = config.get("cpu_routing", {}) if isinstance(config.get("cpu_routing"), dict) else {}
    min_battery = int_config_value(thermal_config, "min_battery_percent_for_heavy", 35, 0)
    min_cpus = int_config_value(routing_config, "routed_heavy_min_cpus", 4, 1)
    max_hot_cpus = int_config_value(routing_config, "routed_heavy_max_hot_cpus", 2, 0)
    max_critical_cpus = int_config_value(routing_config, "routed_heavy_max_critical_cpus", 1, 0)
    broad_hot_count = int_config_value(routing_config, "routed_heavy_broad_heat_hot_core_count", 4, 1)
    broad_avoid_count = int_config_value(routing_config, "routed_heavy_broad_heat_avoid_cpu_count", 6, 1)
    block_on_package_hot = bool_value(routing_config.get("routed_heavy_block_on_package_hot"), False)
    thresholds = thermal_map.get("thresholds", {}) if isinstance(thermal_map.get("thresholds"), dict) else {}
    hot_temp = float(thresholds.get("hot_temperature_c", thermal_config.get("hot_temperature_c", 90.0)))
    package_critical_temp = float(
        thresholds.get(
            "package_critical_temperature_c",
            routing_config.get("package_critical_temperature_c", thermal_config.get("critical_temperature_c", 100.0)),
        )
    )
    summary = thermal_map.get("summary", {}) if isinstance(thermal_map.get("summary"), dict) else {}
    route_avoid_cpus = sorted({int(cpu) for cpu in summary.get("route_avoid_cpus", [])})
    hard_avoid_cpus = sorted({int(cpu) for cpu in summary.get("hard_avoid_cpus", [])})
    hot_cpus = sorted({int(cpu) for cpu in summary.get("hot_cpus", [])})
    critical_cpus = sorted({int(cpu) for cpu in summary.get("critical_cpus", [])})
    package_temp = summary.get("package_temperature_c_max")
    mapped_core_sensors = int(summary.get("mapped_core_sensors") or 0)
    cpus, route_basis = select_route_cpus("heavy", "balanced", thermal_map, config=config, force=False)
    cpus = sorted({int(cpu) for cpu in cpus})
    limit = thread_limit(config, "heavy", cpus)
    route_cpuset = compress_cpu_list(cpus)
    thermal_class = str(thermal_map.get("class") or "unknown")
    effective = str(effective_mode or "unknown")
    policy_value = str(policy_class or "unknown")
    trend_value = str(trend or "unknown")

    reasons: list[str] = [route_basis]
    if thermal_class in {"warm", "hot", "critical"}:
        reasons.append(f"cpu_thermal_class={thermal_class}")
    if route_avoid_cpus:
        reasons.append(f"route_avoid_cpus={compress_cpu_list(route_avoid_cpus)}")
    if hard_avoid_cpus:
        reasons.append(f"hard_avoid_cpus={compress_cpu_list(hard_avoid_cpus)}")

    try:
        capacity_ok = not isinstance(capacity_percent, int) or capacity_percent >= min_battery
    except TypeError:
        capacity_ok = True
    package_critical = isinstance(package_temp, (int, float)) and package_temp >= package_critical_temp
    package_hot = isinstance(package_temp, (int, float)) and package_temp >= hot_temp
    broad_heat = (
        len(hot_cpus) >= broad_hot_count
        or len(route_avoid_cpus) >= broad_avoid_count
        or (block_on_package_hot and package_hot)
    )
    too_many_hot = len(hot_cpus) > max_hot_cpus
    too_many_critical = len(critical_cpus) > max_critical_cpus
    enough_cpus = len(cpus) >= min_cpus and limit > 0
    telemetry_ok = bool(thermal_map.get("ok")) and mapped_core_sensors > 0
    mode_ok = effective in {"balanced", "performance", "ai"}
    battery_ok = bool(ac_online) and capacity_ok
    degraded = policy_value in {"degraded", "battery_saver"} or effective == "saver"

    allowed = telemetry_ok and mode_ok and battery_ok and not degraded and enough_cpus and not package_critical and not broad_heat and not too_many_hot and not too_many_critical
    unattended_allowed = bool(
        allowed
        and not critical_cpus
        and policy_value in {"green", "warm"}
        and trend_value in {"falling", "stable", "unknown"}
    )

    if not telemetry_ok:
        reasons.append("telemetry_missing_or_unmapped")
    if not mode_ok or degraded:
        reasons.append(f"mode_or_policy_deferred:mode={effective}:policy={policy_value}")
    if not battery_ok:
        reasons.append("battery_or_capacity_deferred")
    if not enough_cpus:
        reasons.append(f"insufficient_safe_cpus:{len(cpus)}<min={min_cpus}")
    if package_critical:
        reasons.append(f"package_critical:{package_temp}>=threshold={package_critical_temp}")
    if broad_heat:
        reasons.append(
            "broad_heat:"
            f"hot_cpus={len(hot_cpus)}/threshold={broad_hot_count}:"
            f"avoid_cpus={len(route_avoid_cpus)}/threshold={broad_avoid_count}:"
            f"package_hot={package_hot}"
        )
    if too_many_hot:
        reasons.append(f"too_many_hot_cpus:{len(hot_cpus)}>max={max_hot_cpus}")
    if too_many_critical:
        reasons.append(f"too_many_critical_cpus:{len(critical_cpus)}>max={max_critical_cpus}")
    if allowed and not unattended_allowed:
        reasons.append("operator_controlled_routed_heavy_only")
    if allowed:
        reasons.append(f"routed_heavy_available:cpuset={route_cpuset}:threads={limit}")

    if package_critical:
        decision = "defer_package_critical"
    elif broad_heat or too_many_hot or too_many_critical:
        decision = "defer_broad_heat"
    elif not allowed:
        decision = "defer"
    elif route_avoid_cpus or hot_cpus or critical_cpus:
        decision = "allow_routed_hotspot"
    else:
        decision = "allow_routed_warm_or_balanced"

    return {
        "allowed": allowed,
        "unattended_allowed": unattended_allowed,
        "requires_routing": allowed,
        "decision": decision,
        "route": {
            "basis": route_basis,
            "cpus": cpus,
            "cpuset": route_cpuset,
            "thread_limit": limit,
            "taskset_command_prefix": ["taskset", "-c", route_cpuset] if route_cpuset else [],
            "shell_prefix": f"taskset -c {route_cpuset}" if route_cpuset else "",
        },
        "distribution": {
            "thermal_class": thermal_class,
            "mapped_core_sensors": mapped_core_sensors,
            "package_temperature_c_max": package_temp,
            "core_temperature_c_max": summary.get("core_temperature_c_max"),
            "route_avoid_cpus": route_avoid_cpus,
            "hard_avoid_cpus": hard_avoid_cpus,
            "hot_cpus": hot_cpus,
            "critical_cpus": critical_cpus,
            "hot_cpu_count": len(hot_cpus),
            "critical_cpu_count": len(critical_cpus),
            "broad_heat": broad_heat,
            "package_hot": package_hot,
            "package_critical": package_critical,
        },
        "thresholds": {
            "routed_heavy_min_cpus": min_cpus,
            "routed_heavy_max_hot_cpus": max_hot_cpus,
            "routed_heavy_max_critical_cpus": max_critical_cpus,
            "routed_heavy_broad_heat_hot_core_count": broad_hot_count,
            "routed_heavy_broad_heat_avoid_cpu_count": broad_avoid_count,
            "package_hot_temperature_c": hot_temp,
            "package_critical_temperature_c": package_critical_temp,
            "routed_heavy_block_on_package_hot": block_on_package_hot,
        },
        "reasons": reasons,
        "policy": {
            "facts_only": True,
            "rule": "100-105C package temperature is monitored active range on this thin laptop; route on per-core/broad heat and reserve hard package deferral for the configured emergency threshold.",
        },
    }


def thermal_unattended_cap(mode_policy: dict[str, Any], thermal_class: str) -> str:
    thermal_policy = mode_policy.get("thermal_launch_policy", {}) if isinstance(mode_policy.get("thermal_launch_policy"), dict) else {}
    item = thermal_policy.get(str(thermal_class or "unknown").strip().lower())
    if not isinstance(item, dict):
        item = thermal_policy.get("unknown") if isinstance(thermal_policy.get("unknown"), dict) else {}
    cap = str(item.get("max_unattended_class_cap") or "light").strip().lower()
    if cap not in {"blocked", "none", "background", "probe", "light", "interactive", "medium", "heavy", "sustained"}:
        cap = "light"
    return cap


def thermal_allows_unattended(workload_class: str, thermal_class: str, mode_policy: dict[str, Any]) -> tuple[bool, str]:
    cap = thermal_unattended_cap(mode_policy, thermal_class)
    return workload_level(workload_class) <= workload_level(cap), cap


def build_route(
    *,
    workload_class: str,
    latency: str,
    force: bool,
    thermal_map: dict[str, Any],
    policy: dict[str, Any],
    mode: dict[str, Any],
    battery: dict[str, Any],
    config: dict[str, Any],
    mode_policy: dict[str, Any],
    source_refs: dict[str, str],
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str,
) -> dict[str, Any]:
    workload = normalize_workload(workload_class)
    latency_value = normalize_latency(latency)
    cpus, route_basis = select_route_cpus(workload, latency_value, thermal_map, config=config, force=force)
    cpus = sorted({int(cpu) for cpu in cpus})
    limit = thread_limit(config, workload, cpus)
    thermal_class = str(thermal_map.get("class") or "unknown")
    ac_online = bool(battery.get("ac_online")) if isinstance(battery, dict) else False
    reasons: list[str] = [route_basis]
    if thermal_class in {"hot", "critical"}:
        reasons.append(f"thermal_class={thermal_class}")
    if not ac_online:
        reasons.append("battery_discharging")
    if mode.get("effective_mode"):
        reasons.append(f"effective_mode={mode.get('effective_mode')}")

    heavy_like = workload in {"heavy", "sustained"}
    allowed = bool(cpus)
    unattended_allowed = allowed
    routed_heavy = policy.get("cpu_routing", {}).get("routed_heavy", {}) if isinstance(policy.get("cpu_routing"), dict) else {}
    routed_heavy_allowed = bool(policy.get("can_run_routed_heavy")) and bool(routed_heavy.get("allowed"))
    routed_heavy_unattended_allowed = bool(policy.get("can_run_routed_heavy_unattended")) and bool(routed_heavy.get("unattended_allowed"))
    routing_required = heavy_like and routed_heavy_allowed and not bool(policy.get("can_run_heavy"))
    if heavy_like and not ac_online and not force:
        allowed = False
        unattended_allowed = False
        reasons.append("heavy_cpu_start_deferred_on_battery")
    elif heavy_like and bool(policy.get("can_run_heavy")):
        allowed = bool(cpus)
        unattended_allowed = bool(cpus)
        reasons.append("ai_policy_can_run_heavy=true")
    elif heavy_like and routed_heavy_allowed and not force:
        allowed = bool(cpus)
        unattended_allowed = bool(cpus) and routed_heavy_unattended_allowed
        reasons.append("ai_policy_can_run_routed_heavy=true")
        if thermal_class in {"hot", "critical"}:
            reasons.append("thermal_hotspot_routed_away_from_avoid_cpus")
        if not unattended_allowed:
            reasons.append("routed_heavy_operator_controlled_only")
    elif heavy_like and thermal_class in {"hot", "critical"} and not force:
        allowed = False
        unattended_allowed = False
        reasons.append("heavy_cpu_start_deferred_until_thermal_recovery")
    elif heavy_like and not bool(policy.get("can_run_heavy")) and not force:
        allowed = False
        unattended_allowed = False
        reasons.append("ai_policy_can_run_heavy=false")
    elif not heavy_like:
        thermal_unattended_ok, cap = thermal_allows_unattended(workload, thermal_class, mode_policy)
        if not thermal_unattended_ok and not force:
            unattended_allowed = False
            reasons.append(f"thermal_{thermal_class}_unattended_cap_{cap}")

    cpuset = compress_cpu_list(cpus)
    env = env_for_threads(limit) if limit else {}
    return {
        "schema": f"{schema_prefix}_ai_cpu_route_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": bool(cpus),
        "allowed": allowed or bool(force and cpus),
        "forced": bool(force and not allowed and cpus),
        "unattended_allowed": unattended_allowed,
        "requested": {
            "class": workload_class,
            "normalized_class": workload,
            "latency": latency_value,
        },
        "route": {
            "basis": route_basis,
            "cpus": cpus,
            "cpuset": cpuset,
            "avoid_cpus": _nested_get(thermal_map, ["summary", "route_avoid_cpus"]) or [],
            "hard_avoid_cpus": _nested_get(thermal_map, ["summary", "hard_avoid_cpus"]) or [],
            "thread_limit": limit,
            "routing_required": routing_required,
            "taskset_command_prefix": ["taskset", "-c", cpuset] if cpuset else [],
            "shell_prefix": f"taskset -c {cpuset}" if cpuset else "",
            "env": env,
            "openvino_cpu_runtime_hints": {
                "INFERENCE_NUM_THREADS": limit,
                "AFFINITY": "CORE",
                "CPU_BIND_THREAD": "YES",
            } if limit else {},
        },
        "reasons": reasons,
        "thermal": {
            "class": thermal_class,
            "summary": thermal_map.get("summary", {}),
            "available_by_role_cpuset": thermal_map.get("available_by_role_cpuset", {}),
        },
        "policy": {
            "ai_policy_class": policy.get("class"),
            "can_run_heavy": policy.get("can_run_heavy"),
            "can_run_routed_heavy": policy.get("can_run_routed_heavy"),
            "can_run_routed_heavy_unattended": policy.get("can_run_routed_heavy_unattended"),
            "heavy_policy": policy.get("heavy_policy"),
            "routing_required": routing_required,
            "routed_heavy": routed_heavy,
            "mode": mode.get("effective_mode"),
            "facts_only": True,
            "application_rule": "Route returns taskset/env/runtime hints; callers must apply them explicitly before starting work.",
            "non_claims": [
                "This route does not change governors, fan curves, service state, or abyss-stack routing.",
                "Per-core thermal mapping uses sysfs hwmon labels and sysfs core_id; package temperature is a global risk signal, not a command to disable every CPU.",
            ],
        },
        "source_refs": source_refs,
    }

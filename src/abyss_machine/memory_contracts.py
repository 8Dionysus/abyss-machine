from __future__ import annotations

import re
from typing import Any, Iterable


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


def nested_get(data: Any, path: list[str]) -> Any:
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def kib_to_mib(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return round(float(value) / 1024.0, 1)
    except (TypeError, ValueError):
        return None


def bytes_to_mib(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return round(float(value) / 1024.0 / 1024.0, 1)
    except (TypeError, ValueError):
        return None


def safe_ratio(numerator: Any, denominator: Any, digits: int = 3) -> float | None:
    if isinstance(numerator, bool) or isinstance(denominator, bool):
        return None
    try:
        numerator_f = float(numerator)
        denominator_f = float(denominator)
    except (TypeError, ValueError):
        return None
    if denominator_f <= 0:
        return None
    return round(numerator_f / denominator_f, digits)


def float_value(value: Any, default: float | None = None) -> float | None:
    if isinstance(value, bool) or value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def workload_level(name: str | None) -> int:
    return WORKLOAD_LEVELS.get(str(name or "light").strip().lower(), 1)


def default_residency_policy() -> dict[str, Any]:
    return {
        "enabled": True,
        "facts_only": True,
        "auto_apply_cgroup": False,
        "purpose": "Classify protected resident capabilities and surface cgroup residency gaps without stopping or mutating running services.",
        "classes": {
            "hot_interactive": {
                "description": "Operator-facing first-response paths that should stay warm enough for low-latency use.",
                "target_slice": "abyss-machine-hot.slice",
                "runtime_pilot": {
                    "memory_low_mib": 768,
                    "memory_high_mib": 4096,
                    "memory_swap_max": "measure_after_restart",
                },
            },
            "warm_resident": {
                "description": "Resident model/server capabilities that may keep cold pages in zram but should stay observable and bounded.",
                "target_slice": "abyss-machine-resident.slice",
                "runtime_pilot": {
                    "memory_low_mib": 256,
                    "memory_high_mib": 6144,
                    "memory_swap_max": "measure_after_restart",
                },
            },
            "cold_background": {
                "description": "Maintenance and indexing work should use resource launch gates and remain deferrable.",
                "target_slice": "abyss-machine-background.slice",
                "runtime_pilot": {
                    "memory_low_mib": 0,
                    "memory_high_mib": 2048,
                    "memory_swap_max": "unbounded_until_measured",
                },
            },
        },
        "services": [
            {
                "unit": "abyss-tts-server.service",
                "scope": "user",
                "class": "hot_interactive",
                "capability": "tts",
                "protected": True,
                "reason": "Warm TTS is an operator-facing capability; never disable it as memory relief.",
            },
            {
                "unit": "abyss-dictation-server.service",
                "scope": "user",
                "class": "hot_interactive",
                "capability": "dictation",
                "protected": True,
                "reason": "Dictation is an operator-facing capability; never disable it as memory relief.",
            },
            {
                "unit": "abyss-gemma4-spark.service",
                "scope": "user",
                "class": "warm_resident",
                "capability": "resident_llm",
                "protected": True,
                "reason": "Resident LLM is a promoted machine capability; route new work around it instead of stopping it by default.",
            },
        ],
        "thresholds": {
            "protected_swap_warn_mib": 512,
            "hot_interactive_swap_warn_mib": 256,
            "swap_to_pss_ratio_warn": 4.0,
            "zram_ratio_warn_below": 1.5,
            "zram_free_warn_below_mib": 2048,
            "psi_some_warn_above": 2.0,
            "psi_full_warn_above": 0.5,
        },
        "pilot_rules": {
            "runtime_only_first": True,
            "requires_operator_approval": True,
            "requires_ancestor_memory_low": True,
            "do_not_set_memory_swap_max_on_live_high_swap_services": True,
            "do_not_restart_or_stop_services_from_memory_residency": True,
        },
    }


def default_policy(*, schema_prefix: str, version: str) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "memory_policy_v1"),
        "version": version,
        "owner": "abyss-machine",
        "purpose": "Host-side memory pressure and swap-reserve facts. Pressure never assigns workload importance or authorizes process mutation.",
        "classes": ["green", "watch", "warm", "hot", "critical"],
        "thresholds": {
            "mem_available_percent": {
                "watch_below": 30,
                "warm_below": 22,
                "hot_below": 14,
                "critical_below": 8,
            },
            "psi_some_avg10": {
                "watch_above": 0.2,
                "warm_above": 2.0,
                "hot_above": 8.0,
                "critical_above": 20.0,
            },
            "psi_full_avg10": {
                "watch_above": 0.05,
                "warm_above": 0.5,
                "hot_above": 2.0,
                "critical_above": 8.0,
            },
        },
        "swap_reserve": {
            "enabled": True,
            "target_free_mib": 2048,
            "reason": "Zram occupancy describes logical reserve debt. It remains separate from active pressure and never identifies a workload to mutate.",
        },
        "protected_workloads": {
            "games": "Game guard is authoritative for active games; memory policy must not mutate or kill game processes.",
            "dictation": "Warm dictation may be large but is operator-facing; report it before suggesting stop/restart.",
            "persistent_models": "Promoted resident model servers and stack model containers are protected capabilities; route new work around them instead of demoting them to on-demand or stopping them as default relief.",
            "project_repos": "Do not write memory state into abyss-stack, /work, or game roots.",
        },
        "actions": {
            "automatic_kill": False,
            "automatic_oomd_enable": False,
            "automatic_sysctl_tuning": False,
            "automatic_zram_reconfigure": False,
            "numeric_workload_gating": False,
            "owner_offer_required_for_existing_process_action": True,
        },
        "residency": default_residency_policy(),
    }


def policy_document(
    *,
    schema_prefix: str,
    version: str,
    loaded: Any,
    config_error: Any,
) -> dict[str, Any]:
    if isinstance(loaded, dict):
        defaults = default_policy(schema_prefix=schema_prefix, version=version)
        data = dict(loaded)
        defaults_applied: list[str] = []
        data.setdefault("schema", _schema(schema_prefix, "memory_policy_v1"))
        data["version"] = version
        data["purpose"] = defaults["purpose"]
        thresholds = dict(data.get("thresholds")) if isinstance(data.get("thresholds"), dict) else {}
        thresholds.pop("swap_used_percent", None)
        for key in ("mem_available_percent", "psi_some_avg10", "psi_full_avg10"):
            current = thresholds.get(key) if isinstance(thresholds.get(key), dict) else {}
            thresholds[key] = {**defaults["thresholds"][key], **current}
        data["thresholds"] = thresholds
        actions = data.get("actions") if isinstance(data.get("actions"), dict) else {}
        data["actions"] = {**defaults["actions"], **actions}
        data["actions"].pop("launch_gate_only", None)
        for key, value in defaults["actions"].items():
            data["actions"][key] = value
        data.pop("launch_gates", None)
        data.pop("zram_swap_relief", None)
        if not isinstance(data.get("residency"), dict):
            data["residency"] = default_residency_policy()
            defaults_applied.append("residency")
        if not isinstance(data.get("swap_reserve"), dict):
            data["swap_reserve"] = dict(defaults["swap_reserve"])
            defaults_applied.append("swap_reserve")
        else:
            data["swap_reserve"] = {**defaults["swap_reserve"], **data["swap_reserve"]}
        data["defaults_applied"] = defaults_applied
        data["config_exists"] = True
        data["config_error"] = None
        return data
    data = default_policy(schema_prefix=schema_prefix, version=version)
    data["config_exists"] = False
    data["config_error"] = config_error or "missing"
    return data


def _latest_only(root: Any, latest: Any, **extra: Any) -> dict[str, Any]:
    return {
        "root": str(root),
        "latest": str(latest),
        "retention": "latest_only",
        **extra,
    }


def paths_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    refs: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "memory_paths_v3"),
        "version": version,
        "generated_at": generated_at,
        "root": str(refs["root"]),
        "agent_entrypoint": str(refs["agent_entrypoint"]),
        "index": str(refs["index"]),
        "latest": str(refs["latest"]),
        "policy": str(refs["policy"]),
        "status": _latest_only(refs["status_root"], refs["latest"]),
        "pressure": _latest_only(refs["pressure_root"], refs["pressure_latest"]),
        "processes": _latest_only(refs["process_root"], refs["process_latest"]),
        "plan": _latest_only(refs["plan_root"], refs["plan_latest"]),
        "headroom": _latest_only(refs["headroom_root"], refs["headroom_latest"]),
        "residency": _latest_only(
            refs["residency_root"],
            refs["residency_latest"],
            spec=str(refs["residency_spec"]),
        ),
        "hotpath": _latest_only(refs["hotpath_root"], refs["hotpath_latest"]),
        "validate": _latest_only(refs["validate_root"], refs["validate_latest"]),
        "commands": {
            "paths": "abyss-machine memory paths --json",
            "status": "abyss-machine memory status --json",
            "pressure": "abyss-machine memory pressure --json",
            "processes": "abyss-machine memory processes --json",
            "plan": "abyss-machine memory plan --json",
            "headroom": "abyss-machine memory headroom --json",
            "residency": "abyss-machine memory residency --json",
            "hotpath_probe": "abyss-machine memory hotpath-probe --json",
            "validate": "abyss-machine memory validate --json",
        },
        "policy_contract": {
            "facts_only": True,
            "automatic_kill": False,
            "automatic_sysctl_tuning": False,
            "automatic_zram_reconfigure": False,
            "repo_mutation": False,
        },
    }


def class_rank(name: str | None) -> int:
    values = {"green": 0, "watch": 1, "warm": 2, "hot": 3, "critical": 4}
    return values.get(str(name or "green"), 0)


def class_name(rank: int) -> str:
    if rank <= 0:
        return "green"
    if rank == 1:
        return "watch"
    if rank == 2:
        return "warm"
    if rank == 3:
        return "hot"
    return "critical"


def promote(current: int, target: str, reason: str, reasons: list[str]) -> int:
    rank = class_rank(target)
    if rank > current:
        reasons.append(reason)
        return rank
    if rank == current and target != "green":
        reasons.append(reason)
    return current


def swap_is_zram_only(swap: dict[str, Any]) -> bool:
    devices = swap.get("devices")
    if not isinstance(devices, list) or not devices:
        return False
    for item in devices:
        if not isinstance(item, dict):
            return False
        name = str(item.get("name") or "")
        if not re.fullmatch(r"/dev/zram\d+", name):
            return False
    return True


def pressure_class(mem: dict[str, Any], psi: dict[str, Any], swap: dict[str, Any], policy: dict[str, Any]) -> tuple[str, list[str]]:
    thresholds = policy.get("thresholds", {}) if isinstance(policy.get("thresholds"), dict) else {}
    mem_available_percent = nested_get(mem, ["summary", "mem_available_percent"])
    psi_some_avg10 = nested_get(psi, ["some", "avg10"])
    psi_full_avg10 = nested_get(psi, ["full", "avg10"])
    reasons: list[str] = []
    rank = 0

    mem_thresholds = thresholds.get("mem_available_percent", {}) if isinstance(thresholds.get("mem_available_percent"), dict) else {}
    if isinstance(mem_available_percent, (int, float)):
        if mem_available_percent < float(mem_thresholds.get("critical_below", 8)):
            rank = promote(rank, "critical", f"mem_available_percent={mem_available_percent}<critical", reasons)
        elif mem_available_percent < float(mem_thresholds.get("hot_below", 14)):
            rank = promote(rank, "hot", f"mem_available_percent={mem_available_percent}<hot", reasons)
        elif mem_available_percent < float(mem_thresholds.get("warm_below", 22)):
            rank = promote(rank, "warm", f"mem_available_percent={mem_available_percent}<warm", reasons)
        elif mem_available_percent < float(mem_thresholds.get("watch_below", 30)):
            rank = promote(rank, "watch", f"mem_available_percent={mem_available_percent}<watch", reasons)

    some_thresholds = thresholds.get("psi_some_avg10", {}) if isinstance(thresholds.get("psi_some_avg10"), dict) else {}
    if isinstance(psi_some_avg10, (int, float)):
        if psi_some_avg10 > float(some_thresholds.get("critical_above", 20.0)):
            rank = promote(rank, "critical", f"psi_some_avg10={psi_some_avg10}>critical", reasons)
        elif psi_some_avg10 > float(some_thresholds.get("hot_above", 8.0)):
            rank = promote(rank, "hot", f"psi_some_avg10={psi_some_avg10}>hot", reasons)
        elif psi_some_avg10 > float(some_thresholds.get("warm_above", 2.0)):
            rank = promote(rank, "warm", f"psi_some_avg10={psi_some_avg10}>warm", reasons)
        elif psi_some_avg10 > float(some_thresholds.get("watch_above", 0.2)):
            rank = promote(rank, "watch", f"psi_some_avg10={psi_some_avg10}>watch", reasons)

    full_thresholds = thresholds.get("psi_full_avg10", {}) if isinstance(thresholds.get("psi_full_avg10"), dict) else {}
    if isinstance(psi_full_avg10, (int, float)):
        if psi_full_avg10 > float(full_thresholds.get("critical_above", 8.0)):
            rank = promote(rank, "critical", f"psi_full_avg10={psi_full_avg10}>critical", reasons)
        elif psi_full_avg10 > float(full_thresholds.get("hot_above", 2.0)):
            rank = promote(rank, "hot", f"psi_full_avg10={psi_full_avg10}>hot", reasons)
        elif psi_full_avg10 > float(full_thresholds.get("warm_above", 0.5)):
            rank = promote(rank, "warm", f"psi_full_avg10={psi_full_avg10}>warm", reasons)
        elif psi_full_avg10 > float(full_thresholds.get("watch_above", 0.05)):
            rank = promote(rank, "watch", f"psi_full_avg10={psi_full_avg10}>watch", reasons)

    if not reasons:
        reasons.append("no_active_memory_pressure_observed")
    return class_name(rank), reasons


def swap_reserve_status(swap: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    summary = swap.get("summary") if isinstance(swap.get("summary"), dict) else {}
    reserve_policy = policy.get("swap_reserve") if isinstance(policy.get("swap_reserve"), dict) else {}
    free_mib = float_value(summary.get("free_mib"), None)
    total_mib = float_value(summary.get("total_mib"), None)
    used_mib = float_value(summary.get("used_mib"), None)
    used_percent = float_value(summary.get("used_percent"), None)
    target_free_mib = max(0.0, float(reserve_policy.get("target_free_mib", 2048)))
    shortfall_mib = None if free_mib is None else max(0.0, target_free_mib - free_mib)
    if free_mib is None:
        state = "unavailable"
    elif shortfall_mib > 0:
        state = "below_target"
    else:
        state = "within_target"
    return {
        "state": state,
        "total_mib": None if total_mib is None else round(total_mib, 1),
        "used_mib": None if used_mib is None else round(used_mib, 1),
        "used_percent": None if used_percent is None else round(used_percent, 3),
        "free_mib": None if free_mib is None else round(free_mib, 1),
        "target_free_mib": round(target_free_mib, 1),
        "shortfall_mib": None if shortfall_mib is None else round(shortfall_mib, 1),
        "all_swap_devices_are_zram": swap_is_zram_only(swap),
        "pressure_authority": False,
        "action_authority": False,
    }


def headroom_process_buckets(processes: dict[str, Any], protected_roles: Iterable[str]) -> dict[str, Any]:
    protected_role_set = {str(item) for item in protected_roles}
    top_swap = nested_get(processes, ["top", "swap"])
    if not isinstance(top_swap, list):
        top_swap = []
    top_cgroup_swap = nested_get(processes, ["top", "cgroup_swap"])
    if not isinstance(top_cgroup_swap, list):
        top_cgroup_swap = []
    buckets: dict[tuple[str, str], dict[str, Any]] = {}
    protected_swap_kib = 0
    owner_state_unknown_swap_kib = 0
    top: list[dict[str, Any]] = []
    for item in top_cgroup_swap:
        if not isinstance(item, dict):
            continue
        swap_kib = int(item.get("swap_current_kib") or 0)
        pss_kib = int(item.get("process_pss_rollup_kib") or 0)
        workload = str(item.get("workload_hint") or "normal")
        role = str(item.get("capability_role") or "none")
        protected = bool(item.get("protected")) or role in protected_role_set or workload == "game"
        if protected:
            route = "preserve_protected_owner_context"
            protected_swap_kib += swap_kib
        else:
            route = "owner_state_required_before_action"
            owner_state_unknown_swap_kib += swap_kib
        key = (workload, role)
        bucket = buckets.setdefault(
            key,
            {
                "workload_hint": workload,
                "capability_role": role,
                "processes": 0,
                "swap_kib": 0,
                "pss_kib": 0,
                "protected": protected,
                "route": route,
            },
        )
        bucket["processes"] += 1
        bucket["swap_kib"] += swap_kib
        bucket["pss_kib"] += pss_kib
        if len(top) < 15:
            top.append(
                {
                    "cgroup": item.get("cgroup"),
                    "unit": item.get("unit"),
                    "pids": item.get("pids"),
                    "names": item.get("names"),
                    "workload_hint": workload,
                    "capability_role": role,
                    "protected": protected,
                    "route": route,
                    "action_authority": False,
                    "pss_mib": kib_to_mib(pss_kib),
                    "swap_mib": kib_to_mib(swap_kib),
                    "process_swap_rollup_mib": item.get("process_swap_rollup_mib"),
                }
            )
    process_top: list[dict[str, Any]] = []
    for item in top_swap:
        if not isinstance(item, dict):
            continue
        swap_kib = int(item.get("swap_kib") or 0)
        pss_kib = int(item.get("pss_kib") or 0)
        workload = str(item.get("workload_hint") or "normal")
        role = str(item.get("capability_role") or "none")
        protected = role in protected_role_set or workload == "game"
        if protected:
            route = "preserve_protected_owner_context"
        else:
            route = "owner_state_required_before_action"
        if len(process_top) < 15:
            process_top.append(
                {
                    "pid": item.get("pid"),
                    "name": item.get("name"),
                    "workload_hint": workload,
                    "capability_role": role,
                    "protected": protected,
                    "route": route,
                    "action_authority": False,
                    "pss_mib": kib_to_mib(pss_kib),
                    "swap_mib": kib_to_mib(swap_kib),
                }
            )
    bucket_items = []
    for bucket in buckets.values():
        bucket_items.append(
            {
                "workload_hint": bucket["workload_hint"],
                "capability_role": bucket["capability_role"],
                "processes": bucket["processes"],
                "swap_mib": kib_to_mib(bucket["swap_kib"]),
                "pss_mib": kib_to_mib(bucket["pss_kib"]),
                "protected": bucket["protected"],
                "route": bucket["route"],
                "action_authority": False,
            }
        )
    bucket_items.sort(key=lambda item: float(item.get("swap_mib") or 0), reverse=True)
    return {
        "coverage": "cgroup_swap_current_primary_with_process_rollup_detail",
        "protected_owner_context_swap_mib": kib_to_mib(protected_swap_kib),
        "owner_state_unknown_swap_mib": kib_to_mib(owner_state_unknown_swap_kib),
        "buckets": bucket_items,
        "top_cgroup_swap": top,
        "top_swap": process_top,
        "action_authority": False,
        "importance_inference": False,
    }


def plan_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    pressure: dict[str, Any],
    policy: dict[str, Any],
    mode: dict[str, Any],
    game_guard: dict[str, Any],
    paths: dict[str, Any],
    pressure_latest: Any,
    game_guard_latest: Any,
) -> dict[str, Any]:
    memory_class = str(pressure.get("class") or nested_get(pressure, ["summary", "class"]) or "green")
    return {
        "schema": _schema(schema_prefix, "memory_plan_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": bool(pressure.get("ok", True)),
        "class": memory_class,
        "reasons": pressure.get("reasons"),
        "pressure": {
            "latest": str(pressure_latest),
            "summary": pressure.get("summary"),
        },
        "mode": {
            "selected_mode": mode.get("selected_mode"),
            "effective_mode": mode.get("effective_mode"),
        },
        "game_guard": {
            "active": game_guard.get("active"),
            "platform_present": game_guard.get("platform_present"),
            "summary": game_guard.get("summary"),
            "latest": str(game_guard_latest),
        },
        "commands": {
            "status": "abyss-machine memory status --json",
            "pressure": "abyss-machine memory pressure --json",
            "processes": "abyss-machine memory processes --json",
            "plan": "abyss-machine memory plan --json",
            "launch": "abyss-machine resource launch --class CLASS --kind KIND -- COMMAND...",
        },
        "policy": {
            "automation": "advisory_machine_pressure_only",
            "numeric_workload_gating": False,
            "workload_importance_is_owner_declared": True,
            "do_not_kill_existing_processes": True,
            "do_not_tune_zram_or_sysctl_from_plan": True,
            "operator_force_supported_by_launchers": True,
            "future_stack_consumption": "abyss-stack may consume memory plan before stack-owned launch decisions without abyss-machine importing the stack.",
        },
        "paths": paths,
        "non_claims": [
            "This plan does not mutate running processes.",
            "This plan does not enable systemd-oomd, tune sysctl, or reconfigure zram.",
        ],
    }

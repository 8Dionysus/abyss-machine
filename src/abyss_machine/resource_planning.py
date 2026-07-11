from __future__ import annotations

import os
import math
import re
import time
from typing import Any, Mapping


RESOURCE_CLASSES = {"probe", "light", "medium", "heavy", "sustained"}
RESOURCE_KINDS = {"ai", "agent", "benchmark", "indexing", "generic"}


def _nested_get(data: Any, path: list[str]) -> Any:
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _float_value(value: Any, default: float | None = None) -> float | None:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


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


def default_policy(*, schema_prefix: str = "abyss_machine", version: str = "") -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_resource_policy_v1",
        "version": version,
        "owner": "abyss-machine",
        "purpose": "Unified host resource planning and systemd-run launch policy for new local work.",
        "classes": ["probe", "light", "medium", "heavy", "sustained"],
        "kinds": ["ai", "agent", "benchmark", "indexing", "generic"],
        "kind_slices": {
            "ai": "abyss-machine-ai.slice",
            "agent": "abyss-machine-agents.slice",
            "benchmark": "abyss-machine-benchmarks.slice",
            "indexing": "abyss-machine-indexing.slice",
            "generic": "abyss-machine-work.slice",
        },
        "class_defaults": {
            "probe": {"cpu_weight": 100, "io_weight": 100, "memory_high_percent_total": None, "memory_high_min_mib": None},
            "light": {"cpu_weight": 100, "io_weight": 100, "memory_high_percent_total": None, "memory_high_min_mib": None},
            "medium": {"cpu_weight": 85, "io_weight": 100, "memory_high_percent_total": 75, "memory_high_min_mib": 8192},
            "heavy": {"cpu_weight": 90, "io_weight": 100, "memory_high_percent_total": 85, "memory_high_min_mib": 16384},
            "sustained": {"cpu_weight": 65, "io_weight": 75, "memory_high_percent_total": 75, "memory_high_min_mib": 12288},
        },
        "gates": {
            "game_guard": {
                "block_classes_when_active": ["heavy", "sustained"],
                "block_unattended_at_or_above": "medium",
            },
            "thermal": {
                "sample_seconds_for_medium_or_above": 2.0,
                "sample_interval_sec": 0.5,
                "block_unattended_heavy_on_hot_or_critical": True,
                "operator_controlled_routed_work_may_continue": True,
                "thin_laptop_semantics": "100-105C stable is monitored active range; above 105C is watch/routing range; hard new-work gates are reserved for 109-110C emergency range or sustained/broad heat evidence.",
            },
            "storage": {
                "block_write_preflight_denied": True,
                "warn_on_root_watch": True,
                "block_on_root_critical_without_force": False,
            },
        },
        "launch": {
            "runner": "systemd-run",
            "default_unit_type": "service",
            "service_args": ["--user", "--wait", "--pipe", "--collect"],
            "scope_args": ["--user", "--scope", "--collect"],
            "same_dir_by_default": True,
            "memory_max_by_default": False,
            "cpu_quota_by_default": False,
            "applies_to_new_processes_only": True,
        },
        "startup_admission": {
            "enabled": True,
            "runtime_only": True,
            "known_demand_ttl_sec": 120,
            "unknown_demand_ttl_sec": 15,
            "unknown_wait_timeout_sec": 20,
            "default_demand_mib": {
                "agent": {"medium": 2048, "heavy": 4096, "sustained": 4096},
                "indexing": {"medium": 2048, "heavy": 4096, "sustained": 6144},
                "benchmark": {"medium": 2048, "heavy": 4096, "sustained": 8192},
                "generic": {"medium": 1024, "heavy": 2048, "sustained": 4096},
            },
            "explicit_demand_expected_for": {"ai": ["medium", "heavy", "sustained"]},
        },
        "protected_contexts": {
            "games": "Active games defer new heavy/sustained work and unattended medium-or-heavier starts.",
            "existing_processes": "Do not kill, throttle, re-affinitize, or migrate running user processes from this layer.",
            "project_roots": "Do not write resource artifacts into abyss-stack, /work, /srv/work, or game roots.",
        },
    }


def normalize_class(name: str | None) -> str:
    value = str(name or "medium").strip().lower()
    value = {"background": "sustained", "interactive": "medium"}.get(value, value)
    return value if value in RESOURCE_CLASSES else "medium"


def normalize_kind(name: str | None) -> str:
    value = str(name or "generic").strip().lower()
    return value if value in RESOURCE_KINDS else "generic"


def force_effective_for_request(force: bool, unattended: bool) -> bool:
    return bool(force) and not bool(unattended)


def resolve_startup_demand(
    policy: dict[str, Any],
    *,
    workload_class: str,
    kind: str,
    explicit_mib: float | int | None,
    demand_key: str | None = None,
    demand_owner: str | None = None,
    estimate_source: str | None = None,
    estimate_confidence: str | None = None,
) -> dict[str, Any]:
    normalized_class = normalize_class(workload_class)
    normalized_kind = normalize_kind(kind)
    startup = policy.get("startup_admission") if isinstance(policy.get("startup_admission"), dict) else {}
    enabled = bool(startup.get("enabled", True))
    reservation_required = enabled and workload_level(normalized_class) >= workload_level("medium")
    demand_mib: float | None = None
    source = str(estimate_source or "").strip()
    confidence = str(estimate_confidence or "").strip().lower()
    invalid_reason: str | None = None
    if explicit_mib is not None:
        try:
            explicit_value = float(explicit_mib)
        except (TypeError, ValueError):
            explicit_value = float("nan")
        if not math.isfinite(explicit_value) or explicit_value < 0.0:
            invalid_reason = "memory_demand_mib_must_be_finite_and_nonnegative"
        else:
            demand_mib = explicit_value
        source = source or "explicit_owner_estimate"
        confidence = confidence or "owner_provided"
    else:
        defaults = startup.get("default_demand_mib") if isinstance(startup.get("default_demand_mib"), dict) else {}
        kind_defaults = defaults.get(normalized_kind) if isinstance(defaults.get(normalized_kind), dict) else {}
        default_value = kind_defaults.get(normalized_class)
        if isinstance(default_value, (int, float)) and not isinstance(default_value, bool):
            demand_mib = max(0.0, float(default_value))
            source = source or "resource_policy_class_kind_default"
            confidence = confidence or "conservative_default"
    if demand_mib == 0.0:
        reservation_required = False
    return {
        "enabled": enabled,
        "valid": invalid_reason is None,
        "invalid_reason": invalid_reason,
        "reservation_required": reservation_required,
        "known": demand_mib is not None,
        "demand_mib": None if demand_mib is None else round(demand_mib, 3),
        "key": str(demand_key or "").strip() or None,
        "owner": str(demand_owner or normalized_kind).strip() or normalized_kind,
        "estimate_source": source or "unknown",
        "estimate_confidence": confidence or "unknown",
        "class": normalized_class,
        "kind": normalized_kind,
        "unknown_startup_lane": reservation_required and demand_mib is None,
    }


def _memory_pressure_rank(name: str | None) -> int:
    return {"green": 0, "watch": 1, "warm": 2, "hot": 3, "critical": 4}.get(str(name or "green"), 0)


def _memory_pressure_name(rank: int) -> str:
    return {0: "green", 1: "watch", 2: "warm", 3: "hot", 4: "critical"}.get(max(0, min(int(rank), 4)), "critical")


def startup_demand_projection(
    *,
    memory_summary: Mapping[str, Any],
    current_memory_class: str,
    memory_policy: Mapping[str, Any],
    demand: Mapping[str, Any],
    reservations: Mapping[str, Any],
) -> dict[str, Any]:
    current_available = max(0.0, _float_value(memory_summary.get("mem_available_mib"), 0.0) or 0.0)
    total_mib = max(0.0, _float_value(memory_summary.get("mem_total_mib"), 0.0) or 0.0)
    reservation_summary = reservations.get("summary") if isinstance(reservations.get("summary"), dict) else {}
    outstanding_mib = max(0.0, _float_value(reservation_summary.get("outstanding_mib"), 0.0) or 0.0)
    unknown_count = max(0, int(_float_value(reservation_summary.get("unknown_count"), 0.0) or 0))
    requested = _float_value(demand.get("demand_mib"), None)
    requested_mib = max(0.0, requested) if requested is not None else 0.0
    projected_available = max(0.0, current_available - outstanding_mib - requested_mib)
    projected_percent = (projected_available * 100.0 / total_mib) if total_mib > 0 else None
    projected_rank = _memory_pressure_rank(current_memory_class)
    thresholds = memory_policy.get("thresholds") if isinstance(memory_policy.get("thresholds"), dict) else {}
    mem_thresholds = thresholds.get("mem_available_percent") if isinstance(thresholds.get("mem_available_percent"), dict) else {}
    if projected_percent is not None:
        if projected_percent < float(mem_thresholds.get("critical_below", 8)):
            projected_rank = max(projected_rank, _memory_pressure_rank("critical"))
        elif projected_percent < float(mem_thresholds.get("hot_below", 14)):
            projected_rank = max(projected_rank, _memory_pressure_rank("hot"))
        elif projected_percent < float(mem_thresholds.get("warm_below", 22)):
            projected_rank = max(projected_rank, _memory_pressure_rank("warm"))
        elif projected_percent < float(mem_thresholds.get("watch_below", 30)):
            projected_rank = max(projected_rank, _memory_pressure_rank("watch"))
    return {
        "current": {
            "memory_class": current_memory_class,
            "mem_available_mib": round(current_available, 3),
            "mem_total_mib": round(total_mib, 3),
        },
        "requested": dict(demand),
        "reservations": {
            "active_count": int(_float_value(reservation_summary.get("active_count"), 0.0) or 0),
            "known_count": int(_float_value(reservation_summary.get("known_count"), 0.0) or 0),
            "unknown_count": unknown_count,
            "outstanding_mib": round(outstanding_mib, 3),
        },
        "projected": {
            "memory_class": _memory_pressure_name(projected_rank),
            "mem_available_mib": round(projected_available, 3),
            "mem_available_percent": None if projected_percent is None else round(projected_percent, 3),
        },
        "unknown_startup_conflict": bool(unknown_count and demand.get("reservation_required")),
        "policy": {
            "zram_free_not_counted_as_ram": True,
            "materialized_memory_not_double_counted": True,
            "current_pressure_class_is_floor": True,
        },
    }


def memory_high_value(policy: dict[str, Any], workload_class: str, total_mem_kib: int | None) -> str | None:
    classes = policy.get("class_defaults", {}) if isinstance(policy.get("class_defaults"), dict) else {}
    item = classes.get(workload_class) if isinstance(classes.get(workload_class), dict) else {}
    percent = item.get("memory_high_percent_total")
    if percent is None or not isinstance(total_mem_kib, int) or total_mem_kib <= 0:
        return None
    try:
        mib = int((total_mem_kib / 1024) * (float(percent) / 100.0))
    except (TypeError, ValueError):
        return None
    min_mib = item.get("memory_high_min_mib")
    if isinstance(min_mib, (int, float)):
        mib = max(mib, int(min_mib))
    return f"{max(mib, 512)}M"


def scope_for_kind(policy: dict[str, Any], kind: str) -> str:
    slices = policy.get("kind_slices", {}) if isinstance(policy.get("kind_slices"), dict) else {}
    value = str(slices.get(kind) or slices.get("generic") or "abyss-machine-work.slice")
    if not value.endswith(".slice"):
        value = f"{value}.slice"
    return value


def systemd_plan(
    policy: dict[str, Any],
    kind: str,
    workload_class: str,
    route: dict[str, Any],
    unit_type: str,
    *,
    total_mem_kib: int | None,
    environ: Mapping[str, str] | None = None,
    unattended: bool = False,
) -> dict[str, Any]:
    source_env = os.environ if environ is None else environ
    classes = policy.get("class_defaults", {}) if isinstance(policy.get("class_defaults"), dict) else {}
    class_policy = classes.get(workload_class) if isinstance(classes.get(workload_class), dict) else {}
    cpuset = _nested_get(route, ["route", "cpuset"])
    env = _nested_get(route, ["route", "env"])
    properties: dict[str, str] = {}
    if cpuset:
        properties["AllowedCPUs"] = str(cpuset)
    cpu_weight = class_policy.get("cpu_weight")
    io_weight = class_policy.get("io_weight")
    if isinstance(cpu_weight, (int, float)):
        properties["CPUWeight"] = str(int(cpu_weight))
    if isinstance(io_weight, (int, float)):
        properties["IOWeight"] = str(int(io_weight))
    memory_high = memory_high_value(policy, workload_class, total_mem_kib)
    if memory_high:
        properties["MemoryHigh"] = memory_high
    if kind == "indexing" and workload_level(workload_class) >= workload_level("medium"):
        properties["MemoryHigh"] = source_env.get("ABYSS_MACHINE_INDEXING_MEMORY_HIGH", "4096M")
        indexing_memory_max = str(source_env.get("ABYSS_MACHINE_INDEXING_MEMORY_MAX") or "").strip()
        if indexing_memory_max:
            properties["MemoryMax"] = indexing_memory_max
    return {
        "runner": "systemd-run",
        "unit_type": unit_type if unit_type in {"service", "scope"} else "service",
        "slice": scope_for_kind(policy, kind),
        "properties": properties,
        "env": {str(key): str(value) for key, value in env.items()} if isinstance(env, dict) else {},
        "policy": {
            "memory_high_is_soft": "MemoryHigh" in properties,
            "memory_max_not_set": "MemoryMax" not in properties,
            "memory_max_set_for_indexing": "MemoryMax" in properties and kind == "indexing",
            "generic_unattended_hard_caps_not_applied": True,
            "cpu_quota_not_set": True,
            "allowed_cpus_from_ai_cpu_route": bool(cpuset),
        },
    }


def storage_gate(storage_data: dict[str, Any], write_preflight: dict[str, Any] | None) -> tuple[list[str], list[str], list[str]]:
    blocked: list[str] = []
    denied: list[str] = []
    warnings: list[str] = []
    if isinstance(write_preflight, dict):
        decision = str(write_preflight.get("decision") or "")
        allowed = bool(write_preflight.get("allowed"))
        if not allowed:
            reason = f"storage_write_preflight_{decision or 'blocked'}"
            if decision == "deny":
                denied.append(reason)
            else:
                blocked.append(reason)
    summary = storage_data.get("summary", {}) if isinstance(storage_data.get("summary"), dict) else {}
    root_class = str(summary.get("root_pressure_class") or "")
    srv_class = str(summary.get("srv_pressure_class") or "")
    if root_class in {"watch", "warning"}:
        warnings.append(f"root_storage_pressure_{root_class}")
    if srv_class in {"watch", "warning"}:
        warnings.append(f"srv_storage_pressure_{srv_class}")
    if root_class == "critical":
        warnings.append("root_storage_pressure_critical")
    if srv_class == "critical":
        warnings.append("srv_storage_pressure_critical")
    return blocked, denied, warnings


def game_guard_block_reasons(
    policy: dict[str, Any],
    normalized_class: str,
    unattended: bool,
    active_game: bool,
    force: bool,
) -> list[str]:
    if not active_game or force:
        return []
    gates = policy.get("gates", {}).get("game_guard", {}) if isinstance(policy.get("gates"), dict) else {}
    blocked: list[str] = []
    block_classes = gates.get("block_classes_when_active", ["heavy", "sustained"]) if isinstance(gates, dict) else ["heavy", "sustained"]
    if normalized_class in set(str(item) for item in block_classes):
        blocked.append("game_guard_active")
    unattended_cap = str(gates.get("block_unattended_at_or_above") or "medium") if isinstance(gates, dict) else "medium"
    if unattended and workload_level(normalized_class) >= workload_level(unattended_cap):
        blocked.append("game_guard_unattended_medium_or_heavier")
    return blocked


def indexing_swap_pressure_block_reasons(
    memory_data: dict[str, Any],
    normalized_kind: str,
    normalized_class: str,
    unattended: bool,
    force: bool,
    *,
    environ: Mapping[str, str] | None = None,
) -> list[str]:
    if force or not unattended or normalized_kind != "indexing":
        return []
    if workload_level(normalized_class) < workload_level("medium"):
        return []
    source_env = os.environ if environ is None else environ
    summary = _nested_get(memory_data, ["pressure", "summary"])
    if not isinstance(summary, dict):
        summary = memory_data.get("summary") if isinstance(memory_data.get("summary"), dict) else {}
    blocked: list[str] = []
    max_swap_used_percent = float(source_env.get("ABYSS_MACHINE_INDEXING_MAX_SWAP_USED_PERCENT", "35"))
    min_swap_free_mib = float(source_env.get("ABYSS_MACHINE_INDEXING_MIN_SWAP_FREE_MIB", "4096"))
    min_mem_available_percent = float(source_env.get("ABYSS_MACHINE_INDEXING_MIN_MEM_AVAILABLE_PERCENT", "30"))
    max_psi_some_avg10 = float(source_env.get("ABYSS_MACHINE_INDEXING_MAX_PSI_SOME_AVG10", "2"))
    max_psi_full_avg10 = float(source_env.get("ABYSS_MACHINE_INDEXING_MAX_PSI_FULL_AVG10", "0.5"))
    swap_used_percent = _float_value(summary.get("swap_used_percent"), None)
    swap_free_mib = swap_free_mib_from_summary(summary)
    mem_available_percent = _float_value(summary.get("mem_available_percent"), None)
    psi_some_avg10 = _float_value(summary.get("psi_some_avg10"), None)
    psi_full_avg10 = _float_value(summary.get("psi_full_avg10"), None)
    cooled_residual_debt = residual_swap_debt_is_cooled(
        swap_free_mib=swap_free_mib,
        mem_available_percent=mem_available_percent,
        psi_some_avg10=psi_some_avg10,
        psi_full_avg10=psi_full_avg10,
        min_swap_free_mib=min_swap_free_mib,
        min_mem_available_percent=min_mem_available_percent,
        max_psi_some_avg10=max_psi_some_avg10,
        max_psi_full_avg10=max_psi_full_avg10,
    )
    if swap_used_percent is not None and swap_used_percent > max_swap_used_percent and not cooled_residual_debt:
        blocked.append("indexing_unattended_swap_used_pressure")
    if swap_free_mib is not None and swap_free_mib < min_swap_free_mib:
        blocked.append("indexing_unattended_swap_free_below_floor")
    if psi_some_avg10 is not None and psi_some_avg10 >= max_psi_some_avg10:
        blocked.append("indexing_unattended_psi_some_stall")
    if psi_full_avg10 is not None and psi_full_avg10 >= max_psi_full_avg10:
        blocked.append("indexing_unattended_psi_full_stall")
    return blocked


def residual_swap_debt_is_cooled(
    *,
    swap_free_mib: float | None,
    mem_available_percent: float | None,
    psi_some_avg10: float | None,
    psi_full_avg10: float | None,
    min_swap_free_mib: float,
    min_mem_available_percent: float,
    max_psi_some_avg10: float,
    max_psi_full_avg10: float,
) -> bool:
    return bool(
        swap_free_mib is not None
        and mem_available_percent is not None
        and psi_some_avg10 is not None
        and psi_full_avg10 is not None
        and swap_free_mib >= min_swap_free_mib
        and mem_available_percent >= min_mem_available_percent
        and psi_some_avg10 < max_psi_some_avg10
        and psi_full_avg10 < max_psi_full_avg10
    )


def swap_free_mib_from_summary(summary: Mapping[str, Any]) -> float | None:
    swap_free_mib = _float_value(summary.get("swap_free_mib"), None)
    if swap_free_mib is not None:
        return swap_free_mib
    swap_used_mib = _float_value(summary.get("swap_used_mib"), None)
    swap_used_percent = _float_value(summary.get("swap_used_percent"), None)
    if (
        swap_used_mib is None
        or swap_used_percent is None
        or swap_used_percent <= 0.0
        or swap_used_percent >= 100.0
    ):
        return None
    swap_total_mib = swap_used_mib * 100.0 / swap_used_percent
    return max(0.0, swap_total_mib - swap_used_mib)


def background_ai_swap_debt_block_reasons(
    memory_data: dict[str, Any],
    normalized_kind: str,
    normalized_class: str,
    unattended: bool,
    force: bool,
    *,
    environ: Mapping[str, str] | None = None,
) -> list[str]:
    if force or not unattended or normalized_kind != "ai":
        return []
    if workload_level(normalized_class) < workload_level("medium"):
        return []
    source_env = os.environ if environ is None else environ
    summary = _nested_get(memory_data, ["pressure", "summary"])
    if not isinstance(summary, dict):
        summary = memory_data.get("summary") if isinstance(memory_data.get("summary"), dict) else {}
    if not isinstance(summary, dict):
        summary = {}
    blocked: list[str] = []
    max_swap_used_percent = float(
        source_env.get(
            "ABYSS_MACHINE_BACKGROUND_AI_MAX_SWAP_USED_PERCENT",
            source_env.get("ABYSS_MACHINE_UNATTENDED_MEDIUM_MAX_SWAP_USED_PERCENT", "35"),
        )
    )
    min_swap_free_mib = float(
        source_env.get(
            "ABYSS_MACHINE_BACKGROUND_AI_MIN_SWAP_FREE_MIB",
            source_env.get("ABYSS_MACHINE_UNATTENDED_MEDIUM_MIN_SWAP_FREE_MIB", "2048"),
        )
    )
    max_psi_some_avg10 = float(
        source_env.get(
            "ABYSS_MACHINE_BACKGROUND_AI_MAX_PSI_SOME_AVG10",
            source_env.get("ABYSS_MACHINE_UNATTENDED_MEDIUM_MAX_PSI_SOME_AVG10", "1"),
        )
    )
    max_psi_full_avg10 = float(
        source_env.get(
            "ABYSS_MACHINE_BACKGROUND_AI_MAX_PSI_FULL_AVG10",
            source_env.get("ABYSS_MACHINE_UNATTENDED_MEDIUM_MAX_PSI_FULL_AVG10", "0.5"),
        )
    )
    min_mem_available_percent = float(
        source_env.get(
            "ABYSS_MACHINE_BACKGROUND_AI_MIN_MEM_AVAILABLE_PERCENT",
            source_env.get("ABYSS_MACHINE_UNATTENDED_MEDIUM_MIN_MEM_AVAILABLE_PERCENT", "30"),
        )
    )
    swap_used_percent = _float_value(summary.get("swap_used_percent"), None)
    swap_free_mib = swap_free_mib_from_summary(summary)
    target_swap_free_mib = _float_value(summary.get("target_swap_free_mib"), min_swap_free_mib)
    mem_available_percent = _float_value(summary.get("mem_available_percent"), None)
    psi_some_avg10 = _float_value(summary.get("psi_some_avg10"), None)
    psi_full_avg10 = _float_value(summary.get("psi_full_avg10"), None)
    effective_swap_floor_mib = max(min_swap_free_mib, target_swap_free_mib or min_swap_free_mib)
    cooled_residual_debt = residual_swap_debt_is_cooled(
        swap_free_mib=swap_free_mib,
        mem_available_percent=mem_available_percent,
        psi_some_avg10=psi_some_avg10,
        psi_full_avg10=psi_full_avg10,
        min_swap_free_mib=effective_swap_floor_mib,
        min_mem_available_percent=min_mem_available_percent,
        max_psi_some_avg10=max_psi_some_avg10,
        max_psi_full_avg10=max_psi_full_avg10,
    )
    if swap_used_percent is not None and swap_used_percent >= max_swap_used_percent and not cooled_residual_debt:
        blocked.append("background_ai_unattended_swap_debt")
    if swap_free_mib is not None and target_swap_free_mib is not None and swap_free_mib < target_swap_free_mib:
        blocked.append("background_ai_unattended_swap_free_below_target")
    if psi_some_avg10 is not None and psi_some_avg10 >= max_psi_some_avg10:
        blocked.append("background_ai_unattended_psi_some_stall")
    if psi_full_avg10 is not None and psi_full_avg10 >= max_psi_full_avg10:
        blocked.append("background_ai_unattended_psi_full_stall")
    return blocked


def thermal_plan_gate_reasons(
    thermal_plan: dict[str, Any] | None,
    normalized_class: str,
    unattended: bool,
    force: bool,
    active_game: bool,
    sample_thermal: bool,
    *,
    thermal_unattended_cap: str,
) -> tuple[list[str], list[str]]:
    if not isinstance(thermal_plan, dict):
        return [], []
    blocked: list[str] = []
    warnings: list[str] = []
    thermal_class = str(_nested_get(thermal_plan, ["thermal", "class"]) or "")
    thermal_rec = _nested_get(thermal_plan, ["recommended_new_work", normalized_class])
    if isinstance(thermal_rec, dict):
        thermal_rec_allowed = bool(thermal_rec.get("allowed"))
        thermal_rec_game_guarded = bool(thermal_rec.get("game_guarded"))
        thermal_rec_route_would_allow = thermal_rec.get("route_would_allow")
        thermal_rec_game_only_denial = thermal_rec_game_guarded and (
            thermal_rec_allowed or thermal_rec_route_would_allow is True
        )
        if thermal_rec_game_only_denial and not active_game and not bool(sample_thermal):
            warnings.append("ignored_stale_thermal_plan_game_guard")
        if not thermal_rec_allowed and not force and not thermal_rec_game_only_denial:
            blocked.append("thermal_plan_denied")
        if (
            unattended
            and not bool(thermal_rec.get("unattended_allowed", thermal_rec.get("allowed")))
            and not force
            and not thermal_rec_game_only_denial
        ):
            blocked.append("thermal_plan_unattended_denied")
    if unattended and workload_level(normalized_class) > workload_level(thermal_unattended_cap) and not force:
        blocked.append(f"thermal_{thermal_class}_unattended_cap_{thermal_unattended_cap}")
    return blocked, warnings


def should_sample_thermal(normalized_class: str) -> bool:
    return workload_level(normalized_class) >= workload_level("medium")


def build_plan(
    *,
    workload_class: str,
    kind: str,
    latency: str,
    unattended: bool,
    force: bool,
    bytes_required: int | None,
    target: str | None,
    unit_type: str,
    sample_thermal: bool,
    policy: dict[str, Any],
    mode: dict[str, Any],
    memory: dict[str, Any],
    storage: dict[str, Any],
    game_guard: dict[str, Any],
    route: dict[str, Any],
    thermal_plan: dict[str, Any] | None,
    write_preflight: dict[str, Any] | None,
    paths: dict[str, Any],
    input_latest_paths: dict[str, str],
    thermal_unattended_cap: str,
    total_mem_kib: int | None,
    environ: Mapping[str, str] | None = None,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str,
    startup_demand: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_class = normalize_class(workload_class)
    normalized_kind = normalize_kind(kind)
    force_effective = force_effective_for_request(force, unattended)
    blocked: list[str] = []
    denied: list[str] = []
    warnings: list[str] = []
    if bool(force) and not force_effective:
        warnings.append("unattended_force_not_operator_effective")
    if not bool(route.get("ok")) or (not bool(route.get("allowed")) and not force_effective):
        blocked.append("cpu_route_denied")
    if unattended and not bool(route.get("unattended_allowed")) and not force_effective:
        blocked.append("cpu_route_unattended_denied")

    active_game = bool(game_guard.get("active"))
    blocked.extend(game_guard_block_reasons(policy, normalized_class, unattended, active_game, force_effective))

    memory_rec = _nested_get(memory, ["recommended_new_work", normalized_class])
    memory_unattended_blocked = False
    if isinstance(memory_rec, dict):
        if not bool(memory_rec.get("allowed")) and not force_effective:
            blocked.extend(str(item) for item in memory_rec.get("blocked_reasons", []) or ["memory_gate_denied"])
        if unattended and not bool(memory_rec.get("unattended_allowed")) and not force_effective:
            memory_unattended_blocked = True
            blocked.extend(str(item) for item in memory_rec.get("unattended_blocked_reasons", []) or ["memory_gate_unattended_denied"])
    demand_data = startup_demand if isinstance(startup_demand, dict) else {}
    demand_gate = demand_data.get("gate") if isinstance(demand_data.get("gate"), dict) else {}
    blocked.extend(str(item) for item in demand_gate.get("blocked_reasons", []) or [])
    denied.extend(str(item) for item in demand_gate.get("denied_reasons", []) or [])
    warnings.extend(str(item) for item in demand_gate.get("warnings", []) or [])
    blocked.extend(indexing_swap_pressure_block_reasons(memory, normalized_kind, normalized_class, unattended, force_effective, environ=environ))
    if not memory_unattended_blocked:
        blocked.extend(background_ai_swap_debt_block_reasons(memory, normalized_kind, normalized_class, unattended, force_effective, environ=environ))

    launch_policy = mode.get("launch_policy", {}) if isinstance(mode.get("launch_policy"), dict) else {}
    max_unattended = str(launch_policy.get("max_unattended_class") or "probe")
    if unattended and workload_level(normalized_class) > workload_level(max_unattended) and not force_effective:
        blocked.append(f"mode_unattended_cap_{max_unattended}")

    thermal_blocked, thermal_warnings = thermal_plan_gate_reasons(
        thermal_plan,
        normalized_class,
        unattended,
        force_effective,
        active_game,
        bool(sample_thermal),
        thermal_unattended_cap=thermal_unattended_cap,
    )
    blocked.extend(thermal_blocked)
    warnings.extend(thermal_warnings)

    storage_blocked, storage_denied, storage_warnings = storage_gate(storage, write_preflight)
    blocked.extend(storage_blocked)
    denied.extend(storage_denied)
    warnings.extend(storage_warnings)
    blocked = list(dict.fromkeys(blocked))
    denied = list(dict.fromkeys(denied))
    warnings = list(dict.fromkeys(warnings))

    overridden = list(blocked) if force_effective else []
    effective_blocked = [] if force_effective else blocked
    if denied:
        decision = "deny"
    elif effective_blocked:
        decision = "force_required"
    else:
        decision = "allow"

    systemd = systemd_plan(
        policy,
        normalized_kind,
        normalized_class,
        route,
        unit_type,
        total_mem_kib=total_mem_kib,
        environ=environ,
        unattended=unattended,
    )
    return {
        "schema": f"{schema_prefix}_resource_plan_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": decision == "allow",
        "decision": decision,
        "forced": bool(force),
        "force_effective": bool(force_effective),
        "unattended": bool(unattended),
        "request": {
            "class": workload_class,
            "normalized_class": normalized_class,
            "kind": kind,
            "normalized_kind": normalized_kind,
            "latency": latency,
            "unit_type": unit_type,
            "bytes_required": bytes_required,
            "target": target,
            "sample_thermal": bool(sample_thermal),
            "memory_demand_mib": _nested_get(demand_data, ["requested", "demand_mib"]),
            "demand_key": _nested_get(demand_data, ["requested", "key"]),
            "demand_owner": _nested_get(demand_data, ["requested", "owner"]),
        },
        "blocked_reasons": effective_blocked,
        "denied_reasons": denied,
        "overridden_reasons": overridden,
        "warnings": warnings,
        "systemd": systemd,
        "inputs": {
            "mode": {
                "effective_mode": mode.get("effective_mode"),
                "thermal_class": _nested_get(mode, ["operating", "thermal_class"]),
                "launch_policy": mode.get("launch_policy"),
                "latest": input_latest_paths.get("mode"),
            },
            "memory": {
                "class": memory.get("class"),
                "summary": _nested_get(memory, ["pressure", "summary"]),
                "recommended": memory_rec,
                "latest": input_latest_paths.get("memory"),
            },
            "storage": {
                "summary": storage.get("summary"),
                "write_preflight": write_preflight,
                "latest": input_latest_paths.get("storage"),
            },
            "game_guard": {
                "active": game_guard.get("active"),
                "platform_present": game_guard.get("platform_present"),
                "summary": game_guard.get("summary"),
                "latest": input_latest_paths.get("game_guard"),
            },
            "thermal_plan": {
                "sampled": bool(sample_thermal),
                "thermal": thermal_plan.get("thermal") if isinstance(thermal_plan, dict) else None,
                "recommended": _nested_get(thermal_plan, ["recommended_new_work", normalized_class]) if isinstance(thermal_plan, dict) else None,
                "incident": thermal_plan.get("incident") if isinstance(thermal_plan, dict) else None,
                "latest": input_latest_paths.get("thermal_plan"),
            },
            "cpu_route": route,
            "startup_demand": demand_data or None,
        },
        "commands": {
            "launch_dry_run": f"abyss-machine resource launch --class {normalized_class} --kind {normalized_kind} --dry-run -- COMMAND...",
            "launch": f"abyss-machine resource launch --class {normalized_class} --kind {normalized_kind} -- COMMAND...",
            "validate": "abyss-machine resource validate --json",
        },
        "paths": paths,
        "policy": {
            "new_processes_only": True,
            "does_not_mutate_existing_processes": True,
            "does_not_mutate_games": True,
            "does_not_mutate_stack": True,
            "memory_high_is_soft": True,
            "memory_max_not_set_by_default": "MemoryMax" not in (systemd.get("properties") if isinstance(systemd.get("properties"), dict) else {}),
            "memory_max_set_for_indexing": bool(_nested_get(systemd, ["policy", "memory_max_set_for_indexing"])),
            "generic_unattended_hard_caps_not_applied": True,
            "cpu_quota_not_set_by_default": True,
            "force_does_not_override_storage_denials": True,
            "force_effective_only_when_unattended_false": True,
            "unattended_indexing_blocks_on_swap_pressure": True,
            "background_ai_unattended_blocks_on_swap_debt": True,
            "swap_occupancy_alone_is_not_active_pressure": True,
            "startup_demand_reservations": True,
            "startup_reservations_runtime_only": True,
            "zram_free_not_counted_as_ram": True,
        },
    }


def systemd_command(plan: dict[str, Any], command: list[str], unit: str | None, same_dir: bool) -> list[str]:
    systemd = plan.get("systemd", {}) if isinstance(plan.get("systemd"), dict) else {}
    unit_type = str(systemd.get("unit_type") or "service")
    argv = ["systemd-run", "--user"]
    if unit_type == "scope":
        argv.extend(["--scope", "--collect"])
    else:
        argv.extend(["--wait", "--pipe", "--collect"])
    if unit:
        argv.extend(["--unit", unit])
    if same_dir:
        argv.append("--same-dir")
    slice_name = systemd.get("slice")
    if slice_name:
        argv.append(f"--slice={slice_name}")
    properties = systemd.get("properties", {}) if isinstance(systemd.get("properties"), dict) else {}
    for key in sorted(properties):
        value = properties[key]
        if value is not None and str(value):
            argv.extend(["-p", f"{key}={value}"])
    env = systemd.get("env", {}) if isinstance(systemd.get("env"), dict) else {}
    env = {
        **env,
        "ABYSS_RESOURCE_CLASS": str(_nested_get(plan, ["request", "normalized_class"]) or ""),
        "ABYSS_RESOURCE_KIND": str(_nested_get(plan, ["request", "normalized_kind"]) or ""),
    }
    for key in sorted(env):
        value = env[key]
        if key and value is not None:
            argv.extend(["-E", f"{key}={value}"])
    argv.extend(command)
    return argv


def parse_systemd_run_output(text: str) -> dict[str, Any]:
    unit = None
    result = None
    status = None
    memory_peak = None
    cpu_time = None
    runtime = None
    for line in text.splitlines():
        stripped = line.strip()
        match = re.search(r"Running as unit: ([^\s;]+)", stripped)
        if match:
            unit = match.group(1)
        if stripped.startswith("Finished with result:"):
            result = stripped.partition(":")[2].strip()
        if stripped.startswith("Main processes terminated with:"):
            status = stripped.partition(":")[2].strip()
        if stripped.startswith("Service runtime:"):
            runtime = stripped.partition(":")[2].strip()
        if stripped.startswith("CPU time consumed:"):
            cpu_time = stripped.partition(":")[2].strip()
        if stripped.startswith("Memory peak:"):
            memory_peak = stripped.partition(":")[2].strip()
    return {
        "unit": unit,
        "result": result,
        "main_status": status,
        "service_runtime": runtime,
        "cpu_time_consumed": cpu_time,
        "memory_peak": memory_peak,
    }


def sanitize_unit_part(value: str, fallback: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "").strip()).strip(".-")
    return sanitized[:48] or fallback


def generated_unit_name(kind: str, workload_class: str, unit_type: str, *, token: str | None = None) -> str:
    suffix = "scope" if unit_type == "scope" else "service"
    kind_part = sanitize_unit_part(kind, "generic")
    class_part = sanitize_unit_part(workload_class, "medium")
    value = token or f"{int(time.time() * 1000):x}-{os.getpid()}"
    return f"abyss-machine-{kind_part}-{class_part}-{value}.{suffix}"

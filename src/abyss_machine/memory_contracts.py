from __future__ import annotations

import re
from pathlib import Path
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
        "purpose": "Host-side memory pressure classification and launch gating. Facts and gates only; no automatic process killing.",
        "classes": ["green", "watch", "warm", "hot", "critical"],
        "thresholds": {
            "mem_available_percent": {
                "watch_below": 30,
                "warm_below": 22,
                "hot_below": 14,
                "critical_below": 8,
            },
            "swap_used_percent": {
                "watch_above": 5,
                "warm_above": 15,
                "hot_above": 35,
                "critical_above": 65,
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
        "zram_swap_relief": {
            "enabled": True,
            "applies_when_all_swap_devices_are_zram": True,
            "swap_max_class": "warm",
            "critical_swap_max_class": "warm",
            "requires_mem_available_percent_at_or_above": 30,
            "requires_mem_available_percent_for_headroom_relief_at_or_above": 22,
            "requires_swap_free_mib_at_or_above": 2048,
            "requires_psi_some_avg10_at_or_below": 2.0,
            "requires_psi_full_avg10_at_or_below": 2.0,
            "reason": "High zram occupancy alone is a launch-risk signal, not an OOM-risk signal, while MemAvailable or real zram headroom is present and PSI stalls stay below hot-pressure thresholds. Mild PSI should soften routing instead of promoting healthy zram occupancy to hot or critical.",
        },
        "launch_gates": {
            "green": {
                "block_classes": [],
                "block_unattended_at_or_above": None,
                "reason": "No memory pressure.",
            },
            "watch": {
                "block_classes": [],
                "block_unattended_at_or_above": "sustained",
                "reason": "Keep sustained background work from making early pressure worse.",
            },
            "warm": {
                "block_classes": ["sustained"],
                "block_unattended_at_or_above": "heavy",
                "reason": "Defer sustained work and heavy unattended starts while memory is constrained.",
            },
            "hot": {
                "block_classes": ["heavy", "sustained"],
                "block_unattended_at_or_above": "medium",
                "reason": "Protect interactive work under memory pressure.",
            },
            "critical": {
                "block_classes": ["medium", "heavy", "sustained"],
                "block_unattended_at_or_above": "light",
                "reason": "Avoid new pressure while OOM risk is high.",
            },
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
            "launch_gate_only": True,
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
        data = dict(loaded)
        defaults_applied: list[str] = []
        data.setdefault("schema", _schema(schema_prefix, "memory_policy_v1"))
        data.setdefault("version", version)
        if not isinstance(data.get("residency"), dict):
            data["residency"] = default_residency_policy()
            defaults_applied.append("residency")
        data["defaults_applied"] = defaults_applied
        data["config_exists"] = True
        data["config_error"] = None
        return data
    data = default_policy(schema_prefix=schema_prefix, version=version)
    data["config_exists"] = False
    data["config_error"] = config_error or "missing"
    return data


def _daily_glob(root: Any) -> str:
    return str(Path(str(root)) / "YYYY" / "MM" / "YYYY-MM-DD.jsonl")


def paths_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    refs: dict[str, Any],
    today_paths: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "memory_paths_v1"),
        "version": version,
        "generated_at": generated_at,
        "root": str(refs["root"]),
        "agent_entrypoint": str(refs["agent_entrypoint"]),
        "index": str(refs["index"]),
        "latest": str(refs["latest"]),
        "policy": str(refs["policy"]),
        "status": {
            "root": str(refs["status_root"]),
            "latest": str(refs["latest"]),
            "today": str(today_paths["status"]),
            "daily_glob": _daily_glob(refs["status_root"]),
        },
        "pressure": {
            "root": str(refs["pressure_root"]),
            "latest": str(refs["pressure_latest"]),
            "today": str(today_paths["pressure"]),
            "daily_glob": _daily_glob(refs["pressure_root"]),
        },
        "processes": {
            "root": str(refs["process_root"]),
            "latest": str(refs["process_latest"]),
            "today": str(today_paths["processes"]),
            "daily_glob": _daily_glob(refs["process_root"]),
        },
        "plan": {
            "root": str(refs["plan_root"]),
            "latest": str(refs["plan_latest"]),
            "today": str(today_paths["plan"]),
            "daily_glob": _daily_glob(refs["plan_root"]),
        },
        "headroom": {
            "root": str(refs["headroom_root"]),
            "latest": str(refs["headroom_latest"]),
            "today": str(today_paths["headroom"]),
            "daily_glob": _daily_glob(refs["headroom_root"]),
        },
        "residency": {
            "root": str(refs["residency_root"]),
            "latest": str(refs["residency_latest"]),
            "spec": str(refs["residency_spec"]),
            "today": str(today_paths["residency"]),
            "daily_glob": _daily_glob(refs["residency_root"]),
        },
        "hotpath": {
            "root": str(refs["hotpath_root"]),
            "latest": str(refs["hotpath_latest"]),
            "today": str(today_paths["hotpath"]),
            "daily_glob": _daily_glob(refs["hotpath_root"]),
        },
        "orchestrate": {
            "root": str(refs["orchestrate_root"]),
            "latest": str(refs["orchestrate_latest"]),
            "today": str(today_paths["orchestrate"]),
            "daily_glob": _daily_glob(refs["orchestrate_root"]),
            "apply": {
                "root": str(refs["orchestrate_apply_root"]),
                "latest": str(refs["orchestrate_apply_latest"]),
                "today": str(today_paths["orchestrate_apply"]),
                "daily_glob": _daily_glob(refs["orchestrate_apply_root"]),
            },
            "idle": {
                "root": str(refs["orchestrate_idle_root"]),
                "latest": str(refs["orchestrate_idle_latest"]),
                "today": str(today_paths["orchestrate_idle"]),
                "daily_glob": _daily_glob(refs["orchestrate_idle_root"]),
            },
            "confirm": {
                "root": str(refs["orchestrate_confirm_root"]),
                "latest": str(refs["orchestrate_confirm_latest"]),
                "today": str(today_paths["orchestrate_confirm"]),
                "daily_glob": _daily_glob(refs["orchestrate_confirm_root"]),
            },
            "executor": {
                "root": str(refs["orchestrate_executor_root"]),
                "latest": str(refs["orchestrate_executor_latest"]),
                "today": str(today_paths["orchestrate_executor"]),
                "daily_glob": _daily_glob(refs["orchestrate_executor_root"]),
            },
            "live": {
                "root": str(refs["orchestrate_live_root"]),
                "latest": str(refs["orchestrate_live_latest"]),
                "today": str(today_paths["orchestrate_live"]),
                "daily_glob": _daily_glob(refs["orchestrate_live_root"]),
            },
        },
        "validate": {
            "root": str(refs["validate_root"]),
            "latest": str(refs["validate_latest"]),
            "daily_glob": _daily_glob(refs["validate_root"]),
        },
        "commands": {
            "paths": "abyss-machine memory paths --json",
            "status": "abyss-machine memory status --json",
            "pressure": "abyss-machine memory pressure --json",
            "processes": "abyss-machine memory processes --json",
            "plan": "abyss-machine memory plan --json",
            "headroom": "abyss-machine memory headroom --json",
            "residency": "abyss-machine memory residency --json",
            "hotpath_probe": "abyss-machine memory hotpath-probe --json",
            "orchestrate_plan": "abyss-machine memory orchestrate plan --json",
            "orchestrate_idle": "abyss-machine memory orchestrate idle --candidate ID --json",
            "orchestrate_confirm_dry_run": "abyss-machine memory orchestrate confirm --candidate ID --operator NAME --reason TEXT --acknowledge-protected --dry-run --json",
            "orchestrate_apply_dry_run": "abyss-machine memory orchestrate apply --candidate ID --dry-run --json",
            "orchestrate_apply_confirm": "abyss-machine memory orchestrate apply --candidate ID --confirm --json",
            "orchestrate_apply_live": "abyss-machine memory orchestrate apply --candidate ID --confirm --execute-live --acknowledge-live-restart --operator NAME --reason TEXT --json",
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


def zram_swap_relief_class(
    mem_available_percent: Any,
    psi_some_avg10: Any,
    psi_full_avg10: Any,
    swap: dict[str, Any],
    policy: dict[str, Any],
) -> str | None:
    relief = policy.get("zram_swap_relief", {}) if isinstance(policy.get("zram_swap_relief"), dict) else {}
    if not relief.get("enabled", False):
        return None
    if relief.get("applies_when_all_swap_devices_are_zram", True) and not swap_is_zram_only(swap):
        return None
    required_mem = float(relief.get("requires_mem_available_percent_at_or_above", 30))
    headroom_mem = float(relief.get("requires_mem_available_percent_for_headroom_relief_at_or_above", 22))
    required_swap_free_mib = float(relief.get("requires_swap_free_mib_at_or_above", 2048))
    max_psi_some = float(relief.get("requires_psi_some_avg10_at_or_below", 0.2))
    max_psi_full = float(relief.get("requires_psi_full_avg10_at_or_below", 0.05))
    swap_free_mib = nested_get(swap, ["summary", "free_mib"])
    if not isinstance(mem_available_percent, (int, float)):
        return None
    has_mem_relief = float(mem_available_percent) >= required_mem
    has_headroom_relief = (
        float(mem_available_percent) >= headroom_mem
        and isinstance(swap_free_mib, (int, float))
        and float(swap_free_mib) >= required_swap_free_mib
    )
    if not has_mem_relief and not has_headroom_relief:
        return None
    if not isinstance(psi_some_avg10, (int, float)) or float(psi_some_avg10) > max_psi_some:
        return None
    if not isinstance(psi_full_avg10, (int, float)) or float(psi_full_avg10) > max_psi_full:
        return None
    target = str(relief.get("swap_max_class") or "warm").strip().lower()
    if class_rank(target) >= class_rank("critical"):
        target = "hot"
    return target


def pressure_class(mem: dict[str, Any], psi: dict[str, Any], swap: dict[str, Any], policy: dict[str, Any]) -> tuple[str, list[str]]:
    thresholds = policy.get("thresholds", {}) if isinstance(policy.get("thresholds"), dict) else {}
    mem_available_percent = nested_get(mem, ["summary", "mem_available_percent"])
    swap_used_percent = nested_get(swap, ["summary", "used_percent"])
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

    swap_thresholds = thresholds.get("swap_used_percent", {}) if isinstance(thresholds.get("swap_used_percent"), dict) else {}
    if isinstance(swap_used_percent, (int, float)):
        if swap_used_percent > float(swap_thresholds.get("critical_above", 65)):
            relief_class = zram_swap_relief_class(mem_available_percent, psi_some_avg10, psi_full_avg10, swap, policy)
            if relief_class:
                rank = promote(
                    rank,
                    relief_class,
                    (
                        f"swap_used_percent={swap_used_percent}>critical"
                        f"_but_zram_only_relief_to_{relief_class}"
                        f"(mem_available_percent={mem_available_percent},"
                        f"swap_free_mib={nested_get(swap, ['summary', 'free_mib'])},"
                        f"psi_some_avg10={psi_some_avg10},psi_full_avg10={psi_full_avg10})"
                    ),
                    reasons,
                )
            else:
                rank = promote(rank, "critical", f"swap_used_percent={swap_used_percent}>critical", reasons)
        elif swap_used_percent > float(swap_thresholds.get("hot_above", 35)):
            relief_class = zram_swap_relief_class(mem_available_percent, psi_some_avg10, psi_full_avg10, swap, policy)
            if relief_class and class_rank(relief_class) < class_rank("hot"):
                rank = promote(
                    rank,
                    relief_class,
                    (
                        f"swap_used_percent={swap_used_percent}>hot"
                        f"_but_zram_only_relief_to_{relief_class}"
                        f"(mem_available_percent={mem_available_percent},"
                        f"swap_free_mib={nested_get(swap, ['summary', 'free_mib'])},"
                        f"psi_some_avg10={psi_some_avg10},psi_full_avg10={psi_full_avg10})"
                    ),
                    reasons,
                )
            else:
                rank = promote(rank, "hot", f"swap_used_percent={swap_used_percent}>hot", reasons)
        elif swap_used_percent > float(swap_thresholds.get("warm_above", 15)):
            rank = promote(rank, "warm", f"swap_used_percent={swap_used_percent}>warm", reasons)
        elif swap_used_percent > float(swap_thresholds.get("watch_above", 5)):
            rank = promote(rank, "watch", f"swap_used_percent={swap_used_percent}>watch", reasons)

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
        reasons.append("no_memory_pressure_observed")
    return class_name(rank), reasons


def launch_gate_for_class(memory_class: str, workload_class: str, unattended: bool, policy: dict[str, Any]) -> dict[str, Any]:
    gates = policy.get("launch_gates", {}) if isinstance(policy.get("launch_gates"), dict) else {}
    gate = gates.get(memory_class) if isinstance(gates.get(memory_class), dict) else {}
    normalized = str(workload_class or "medium").strip().lower()
    if normalized == "interactive":
        normalized = "medium"
    blocked: list[str] = []
    block_classes = set(str(item) for item in gate.get("block_classes", []) if isinstance(item, str))
    if normalized in block_classes:
        blocked.append(f"memory_{memory_class}_blocks_{normalized}")
    unattended_at = gate.get("block_unattended_at_or_above")
    if unattended and unattended_at and workload_level(normalized) >= workload_level(str(unattended_at)):
        blocked.append(f"memory_{memory_class}_blocks_unattended_{normalized}")
    return {
        "allowed": not blocked,
        "blocked_reasons": blocked,
        "memory_class": memory_class,
        "workload_class": normalized,
        "unattended": bool(unattended),
        "gate": gate,
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
    operator_review_swap_kib = 0
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
            route = str(item.get("route") or "route_new_work_around_protected_capability")
            protected_swap_kib += swap_kib
        elif workload == "game_platform":
            route = str(item.get("route") or "operator_review_game_platform_only")
            operator_review_swap_kib += swap_kib
        elif workload in {"development", "browser", "normal"}:
            route = str(item.get("route") or "operator_review_candidate")
            operator_review_swap_kib += swap_kib
        else:
            route = str(item.get("route") or "observe")
            operator_review_swap_kib += swap_kib
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
            route = "route_new_work_around_protected_capability"
        elif workload == "game_platform":
            route = "operator_review_game_platform_only"
        elif workload in {"development", "browser", "normal"}:
            route = "operator_review_candidate"
        else:
            route = "observe"
        if len(process_top) < 15:
            process_top.append(
                {
                    "pid": item.get("pid"),
                    "name": item.get("name"),
                    "workload_hint": workload,
                    "capability_role": role,
                    "protected": protected,
                    "route": route,
                    "pss_mib": kib_to_mib(pss_kib),
                    "swap_mib": kib_to_mib(swap_kib),
                    "cmdline_preview": str(item.get("cmdline") or "")[:180],
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
            }
        )
    bucket_items.sort(key=lambda item: float(item.get("swap_mib") or 0), reverse=True)
    return {
        "coverage": "cgroup_swap_current_primary_with_process_rollup_detail",
        "protected_swap_mib": kib_to_mib(protected_swap_kib),
        "operator_review_swap_mib": kib_to_mib(operator_review_swap_kib),
        "buckets": bucket_items,
        "top_cgroup_swap": top,
        "top_swap": process_top,
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
    recommended: dict[str, Any] = {}
    for workload in ("probe", "light", "medium", "heavy", "sustained"):
        gate = launch_gate_for_class(memory_class, workload, unattended=False, policy=policy)
        unattended_gate = launch_gate_for_class(memory_class, workload, unattended=True, policy=policy)
        recommended[workload] = {
            "allowed": bool(gate.get("allowed")),
            "unattended_allowed": bool(unattended_gate.get("allowed")),
            "blocked_reasons": gate.get("blocked_reasons"),
            "unattended_blocked_reasons": unattended_gate.get("blocked_reasons"),
        }
    if game_guard.get("active"):
        for workload in ("heavy", "sustained"):
            recommended[workload]["game_guarded"] = True
            recommended[workload]["allowed"] = False
            recommended[workload].setdefault("blocked_reasons", []).append("game_guard_active")
        for workload in ("medium", "heavy", "sustained"):
            recommended[workload]["unattended_allowed"] = False
            recommended[workload].setdefault("unattended_blocked_reasons", []).append("game_guard_active")

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
        "recommended_new_work": recommended,
        "commands": {
            "status": "abyss-machine memory status --json",
            "pressure": "abyss-machine memory pressure --json",
            "processes": "abyss-machine memory processes --json",
            "plan": "abyss-machine memory plan --json",
            "launch": "abyss-machine ai cpu launch --class CLASS -- COMMAND...",
        },
        "policy": {
            "automation": "gate_new_work_only",
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

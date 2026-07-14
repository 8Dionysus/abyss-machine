from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from typing import Any, Mapping


RESOURCE_CLASSES = {"probe", "light", "medium", "heavy", "sustained"}
RESOURCE_KINDS = {"ai", "agent", "benchmark", "indexing", "generic"}
OWNER_ACTIVITIES = {"foreground", "background", "maintenance", "unspecified"}
_OWNER_IDENTITY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/@+~-]*$")


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
        "purpose": "Owner-cooperative host resource planning for new local work. Numeric pressure facts protect reserve but never assign workload importance.",
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
            "probe": {"cpu_weight": 100, "io_weight": 100},
            "light": {"cpu_weight": 100, "io_weight": 100},
            "medium": {"cpu_weight": 85, "io_weight": 100},
            "heavy": {"cpu_weight": 90, "io_weight": 100},
            "sustained": {"cpu_weight": 65, "io_weight": 75},
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
            "hard_mem_available_floor_mib": 2048,
            "unknown_mem_available_floor_mib": 4096,
            "unknown_psi_some_avg10_at_or_above": 2.0,
            "unknown_psi_full_avg10_at_or_above": 0.5,
            "observed_peak_multiplier": 1.25,
            "profile_max_entries": 64,
            "profile_max_samples": 16,
            "bootstrap_demand_mib": {
                "agent": {"medium": 2048, "heavy": 4096, "sustained": 4096},
                "indexing": {"medium": 2048, "heavy": 4096, "sustained": 6144},
                "benchmark": {"medium": 2048, "heavy": 4096, "sustained": 8192},
                "generic": {"medium": 1024, "heavy": 2048, "sustained": 4096},
            },
            "explicit_demand_expected_for": {"ai": ["medium", "heavy", "sustained"]},
        },
        "runtime_admission": {
            "enabled": True,
            "runtime_only": True,
            "cold_load_lease_ttl_sec": 120,
            "cold_load_lease_max_ttl_sec": 300,
            "socket_mode": "0600",
            "max_request_bytes": 65536,
            "thermal_emergency_c": 109.0,
            "require_explicit_owner_activity": True,
            "fail_closed_when_unavailable": True,
        },
        "protected_contexts": {
            "games": "Active games defer new heavy/sustained work and unattended medium-or-heavier starts.",
            "existing_processes": "Do not kill, throttle, re-affinitize, or migrate running user processes from this layer.",
            "project_roots": "Do not write resource artifacts into abyss-stack, /work, /srv/work, or game roots.",
        },
        "memory_orchestration": {
            "importance_source": "stable_owner_identity_and_owner_declared_state",
            "pressure_is_not_importance": True,
            "swap_occupancy_is_reserve_debt_not_pressure": True,
            "static_memory_caps": False,
        },
    }


def normalize_class(name: str | None) -> str:
    value = str(name or "medium").strip().lower()
    value = {"background": "sustained", "interactive": "medium"}.get(value, value)
    return value if value in RESOURCE_CLASSES else "medium"


def normalize_kind(name: str | None) -> str:
    value = str(name or "generic").strip().lower()
    return value if value in RESOURCE_KINDS else "generic"


def owner_activity(activity: str | None, *, unattended: bool = False) -> dict[str, Any]:
    raw = str(activity or "").strip().lower()
    explicit = bool(raw)
    normalized = raw if raw in OWNER_ACTIVITIES else "unspecified"
    errors: list[str] = []
    if explicit and raw not in OWNER_ACTIVITIES:
        errors.append("owner_activity_invalid")
    if not explicit and unattended:
        normalized = "background"
    if normalized == "foreground" and unattended:
        errors.append("owner_activity_conflicts_with_unattended")
    background = bool(unattended) or normalized in {"background", "maintenance"}
    return {
        "valid": not errors,
        "errors": errors,
        "explicit": explicit,
        "requested": raw or None,
        "normalized": normalized,
        "foreground": normalized == "foreground" and not bool(unattended),
        "background": background,
        "importance_source": "owner_declared_state",
        "pressure_facts_assign_importance": False,
    }


def runtime_admission_request(request: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []

    def identity(name: str, max_length: int) -> str:
        value = str(request.get(name) or "").strip()
        if not value:
            errors.append(f"{name}_required")
        elif len(value) > max_length or not _OWNER_IDENTITY_RE.fullmatch(value):
            errors.append(f"{name}_invalid")
        return value

    owner = identity("owner", 160)
    workload_id = identity("workload_id", 240)
    request_id = identity("request_id", 160)
    release_token = str(request.get("release_token") or "")
    if len(release_token) < 24 or len(release_token) > 512:
        errors.append("release_token_invalid")

    operation = str(request.get("operation") or "cold_load").strip().lower()
    if operation != "cold_load":
        errors.append("operation_unsupported")

    activity_data = owner_activity(str(request.get("activity") or ""), unattended=False)
    if not activity_data.get("valid"):
        errors.extend(str(item) for item in activity_data.get("errors", []))
    if not activity_data.get("explicit") or activity_data.get("normalized") == "unspecified":
        errors.append("owner_activity_required")

    raw_class = str(request.get("class") or "heavy").strip().lower()
    if raw_class not in RESOURCE_CLASSES:
        errors.append("class_invalid")
    workload_class = normalize_class(raw_class)
    raw_kind = str(request.get("kind") or "ai").strip().lower()
    if raw_kind not in RESOURCE_KINDS:
        errors.append("kind_invalid")
    kind = normalize_kind(raw_kind)
    latency = str(request.get("latency") or ("interactive" if activity_data.get("foreground") else "balanced")).strip().lower()
    if latency not in {"low", "balanced", "interactive"}:
        errors.append("latency_invalid")

    try:
        demand_mib = float(request.get("memory_demand_mib"))
    except (TypeError, ValueError):
        demand_mib = float("nan")
    if not math.isfinite(demand_mib) or demand_mib <= 0.0:
        errors.append("memory_demand_mib_must_be_finite_and_positive")

    normalized = {
        "operation": operation,
        "owner": owner,
        "workload_id": workload_id,
        "request_id": request_id,
        "activity": str(activity_data.get("normalized") or "unspecified"),
        "unattended": bool(activity_data.get("background")),
        "class": workload_class,
        "kind": kind,
        "latency": latency,
        "memory_demand_mib": None if not math.isfinite(demand_mib) else round(demand_mib, 3),
        "estimate_source": str(request.get("estimate_source") or "explicit_owner_estimate").strip()[:160],
        "estimate_confidence": str(request.get("estimate_confidence") or "owner_provided").strip()[:80],
    }
    identity_material = "\0".join((owner, workload_id, request_id))
    lease_id = f"runtime-cold-load:{hashlib.sha256(identity_material.encode('utf-8')).hexdigest()[:32]}" if all((owner, workload_id, request_id)) else None
    digest = hashlib.sha256(
        json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    token_sha256 = hashlib.sha256(release_token.encode("utf-8")).hexdigest() if release_token else None
    return {
        "valid": not errors,
        "errors": list(dict.fromkeys(errors)),
        "request": normalized,
        "activity": activity_data,
        "lease_id": lease_id,
        "request_digest": digest,
        "release_token_sha256": token_sha256,
        "policy": {
            "explicit_owner_activity_required": True,
            "release_token_not_returned": True,
            "pressure_facts_assign_importance": False,
        },
    }


def command_demand_key(command: list[str], explicit_key: str | None = None) -> str | None:
    explicit = str(explicit_key or "").strip()
    if explicit:
        return explicit[:160]
    clean = [str(item).strip() for item in command if str(item).strip() and str(item).strip() != "--"]
    if not clean:
        return None
    executable = os.path.basename(clean[0]) or "command"
    if executable == "env":
        tail = clean[1:]
        while tail:
            token = tail[0]
            if token == "--":
                tail = tail[1:]
                break
            if token in {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"}:
                tail = tail[2:]
                continue
            if token.startswith(("--unset=", "--chdir=", "--split-string=")) or token.startswith("-") or "=" in token:
                tail = tail[1:]
                continue
            break
        return command_demand_key(tail)
    if executable in {"bash", "sh", "zsh", "fish"} and len(clean) >= 3 and clean[1] in {"-c", "-lc"}:
        digest = hashlib.sha256(clean[2].encode("utf-8", errors="replace")).hexdigest()[:12]
        return f"{executable}:script:{digest}"
    route = [executable]
    if executable.startswith("python") and len(clean) > 1:
        if clean[1] == "-m" and len(clean) > 2:
            route.extend(["module", clean[2]])
        elif not clean[1].startswith("-"):
            route.append(os.path.basename(clean[1]))
    elif executable in {"abyss-machine", "aoa-session-memory", "aoa_session_memory"}:
        for token in clean[1:]:
            if token.startswith("-"):
                break
            route.append(os.path.basename(token) if "/" in token else token)
            if len(route) >= 3:
                break
    elif len(clean) > 1:
        digest = hashlib.sha256("\0".join(clean[1:]).encode("utf-8", errors="replace")).hexdigest()[:12]
        route.append(f"argv-{digest}")
    normalized = [re.sub(r"[^A-Za-z0-9_.-]+", "-", item).strip("-.") for item in route]
    return ":".join(item for item in normalized if item)[:160] or None


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
    learned_profile: Mapping[str, Any] | None = None,
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
    used_explicit = False
    used_learned = False
    used_bootstrap = False
    if explicit_mib is not None:
        try:
            explicit_value = float(explicit_mib)
        except (TypeError, ValueError):
            explicit_value = float("nan")
        if not math.isfinite(explicit_value) or explicit_value < 0.0:
            invalid_reason = "memory_demand_mib_must_be_finite_and_nonnegative"
        else:
            demand_mib = explicit_value
            used_explicit = True
        source = source or "explicit_owner_estimate"
        confidence = confidence or "owner_provided"
    elif isinstance(learned_profile, Mapping):
        learned_value = _float_value(learned_profile.get("estimate_mib"), None)
        if learned_value is not None and math.isfinite(learned_value) and learned_value >= 0.0:
            demand_mib = learned_value
            used_learned = True
            source = source or "runtime_observed_unit_peak"
            confidence = confidence or "observed"
            reservation_required = enabled and demand_mib > 0.0
    if explicit_mib is None and demand_mib is None:
        defaults = startup.get("bootstrap_demand_mib") if isinstance(startup.get("bootstrap_demand_mib"), dict) else {}
        kind_defaults = defaults.get(normalized_kind) if isinstance(defaults.get(normalized_kind), dict) else {}
        default_value = kind_defaults.get(normalized_class)
        if isinstance(default_value, (int, float)) and not isinstance(default_value, bool):
            demand_mib = max(0.0, float(default_value))
            used_bootstrap = True
            source = source or "bootstrap_class_kind_estimate"
            confidence = confidence or "uncalibrated"
    if enabled and demand_mib is not None and demand_mib > 0.0 and (used_explicit or used_learned):
        reservation_required = True
    if demand_mib == 0.0:
        reservation_required = False
    calibrated = used_explicit or used_learned
    return {
        "enabled": enabled,
        "valid": invalid_reason is None,
        "invalid_reason": invalid_reason,
        "reservation_required": reservation_required,
        "known": calibrated,
        "estimate_available": demand_mib is not None,
        "demand_mib": None if demand_mib is None else round(demand_mib, 3),
        "key": str(demand_key or "").strip() or None,
        "owner": str(demand_owner or normalized_kind).strip() or normalized_kind,
        "estimate_source": source or "unknown",
        "estimate_confidence": confidence or "unknown",
        "calibration": "owner" if used_explicit else ("learned" if used_learned else "bootstrap_uncalibrated" if used_bootstrap else "unknown"),
        "calibrated": calibrated,
        "learned_sample_count": int(_float_value(learned_profile.get("sample_count"), 0.0) or 0) if isinstance(learned_profile, Mapping) else 0,
        "class": normalized_class,
        "kind": normalized_kind,
        "unknown_startup_lane": reservation_required and not calibrated,
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
    unattended: bool = False,
    admission_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    raw_current_available = _float_value(memory_summary.get("mem_available_mib"), None)
    availability_known = raw_current_available is not None
    current_available = max(0.0, raw_current_available or 0.0)
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
    startup = admission_policy if isinstance(admission_policy, Mapping) else {}
    hard_floor_mib = max(0.0, _float_value(startup.get("hard_mem_available_floor_mib"), 2048.0) or 2048.0)
    unknown_floor_mib = max(hard_floor_mib, _float_value(startup.get("unknown_mem_available_floor_mib"), 4096.0) or 4096.0)
    psi_some = _float_value(memory_summary.get("psi_some_avg10"), None)
    psi_full = _float_value(memory_summary.get("psi_full_avg10"), None)
    psi_some_thresholds = thresholds.get("psi_some_avg10") if isinstance(thresholds.get("psi_some_avg10"), dict) else {}
    psi_full_thresholds = thresholds.get("psi_full_avg10") if isinstance(thresholds.get("psi_full_avg10"), dict) else {}
    active_stall_some_threshold = max(0.0, _float_value(psi_some_thresholds.get("hot_above"), 8.0) or 8.0)
    active_stall_full_threshold = max(0.0, _float_value(psi_full_thresholds.get("hot_above"), 2.0) or 2.0)
    active_stall = bool(
        (psi_some is not None and psi_some >= active_stall_some_threshold)
        or (psi_full is not None and psi_full >= active_stall_full_threshold)
    )
    unknown_some_threshold = max(0.0, _float_value(startup.get("unknown_psi_some_avg10_at_or_above"), 2.0) or 2.0)
    unknown_full_threshold = max(0.0, _float_value(startup.get("unknown_psi_full_avg10_at_or_above"), 0.5) or 0.5)
    safety_blocks: list[str] = []
    safety_denials: list[str] = []
    reservation_state_ok = reservations.get("ok") is not False
    if not reservation_state_ok:
        safety_denials.append("reservation_state_invalid")
    estimate_available = bool(demand.get("estimate_available", demand.get("known")))
    if availability_known and demand.get("reservation_required") and estimate_available and projected_available < hard_floor_mib:
        safety_blocks.append("projected_mem_available_below_hard_reserve")
    if demand.get("reservation_required") and unattended and active_stall:
        safety_blocks.append("new_unattended_work_during_active_memory_stall")
    if demand.get("unknown_startup_lane"):
        unreserved_available = max(0.0, current_available - outstanding_mib)
        if availability_known and unreserved_available < unknown_floor_mib:
            safety_blocks.append("unknown_demand_with_low_physical_headroom")
        if not active_stall and (
            (psi_some is not None and psi_some >= unknown_some_threshold)
            or (psi_full is not None and psi_full >= unknown_full_threshold)
        ):
            safety_blocks.append("unknown_demand_during_active_memory_stall")
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
        "admission": {
            "allowed": not safety_blocks and not safety_denials,
            "blocked_reasons": safety_blocks,
            "denied_reasons": safety_denials,
            "availability_known": availability_known,
            "active_stall": active_stall,
            "psi_some_avg10": psi_some,
            "psi_full_avg10": psi_full,
            "active_stall_psi_some_avg10_at_or_above": round(active_stall_some_threshold, 3),
            "active_stall_psi_full_avg10_at_or_above": round(active_stall_full_threshold, 3),
            "unattended_start": bool(unattended),
            "hard_mem_available_floor_mib": round(hard_floor_mib, 3),
            "unknown_mem_available_floor_mib": round(unknown_floor_mib, 3),
            "pressure_facts_assign_importance": False,
            "reservation_state_ok": reservation_state_ok,
        },
        "policy": {
            "zram_free_not_counted_as_ram": True,
            "materialized_memory_not_double_counted": True,
            "current_pressure_class_is_floor": True,
            "projected_pressure_class_is_advisory": True,
            "hard_floor_protects_host_reserve_not_workload_priority": True,
        },
    }


def runtime_cold_load_plan(
    *,
    request: Mapping[str, Any],
    memory_summary: Mapping[str, Any],
    current_memory_class: str,
    memory_policy: Mapping[str, Any],
    resource_policy: dict[str, Any],
    reservations: Mapping[str, Any],
    thermal_safety: Mapping[str, Any],
    generated_at: str,
    schema_prefix: str = "abyss_machine",
    version: str = "",
) -> dict[str, Any]:
    activity_data = owner_activity(
        str(request.get("activity") or ""),
        unattended=bool(request.get("unattended")),
    )
    demand = resolve_startup_demand(
        resource_policy,
        workload_class=str(request.get("class") or "heavy"),
        kind=str(request.get("kind") or "ai"),
        explicit_mib=request.get("memory_demand_mib"),
        demand_key=f"{request.get('owner')}:{request.get('workload_id')}",
        demand_owner=str(request.get("owner") or ""),
        estimate_source=str(request.get("estimate_source") or "explicit_owner_estimate"),
        estimate_confidence=str(request.get("estimate_confidence") or "owner_provided"),
    )
    startup_policy = resource_policy.get("startup_admission") if isinstance(resource_policy.get("startup_admission"), dict) else {}
    projection = startup_demand_projection(
        memory_summary=memory_summary,
        current_memory_class=current_memory_class,
        memory_policy=memory_policy,
        demand=demand,
        reservations=reservations,
        unattended=bool(activity_data.get("background")),
        admission_policy=startup_policy,
    )
    admission = projection.get("admission") if isinstance(projection.get("admission"), dict) else {}
    blocked = [f"runtime_{item}" for item in admission.get("blocked_reasons", [])]
    denied = [f"runtime_{item}" for item in admission.get("denied_reasons", [])]
    denied.extend(activity_data.get("errors") or [])
    if demand.get("valid") is False:
        denied.append("runtime_demand_invalid")
    if projection.get("unknown_startup_conflict"):
        blocked.append("runtime_unknown_demand_in_progress")
    if thermal_safety.get("available") is not True:
        denied.append("thermal_safety_unavailable")
    elif thermal_safety.get("emergency") is True:
        blocked.append("thermal_emergency")
    blocked = list(dict.fromkeys(str(item) for item in blocked))
    denied = list(dict.fromkeys(str(item) for item in denied))
    if denied:
        decision = "deny"
    elif blocked:
        decision = "force_required"
    else:
        decision = "allow"
    return {
        "schema": f"{schema_prefix}_resource_runtime_cold_load_plan_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": decision == "allow",
        "decision": decision,
        "request": {
            "owner": request.get("owner"),
            "workload_id": request.get("workload_id"),
            "request_id": request.get("request_id"),
            "class": demand.get("class"),
            "kind": demand.get("kind"),
            "activity": activity_data,
            "memory_demand_mib": demand.get("demand_mib"),
        },
        "blocked_reasons": blocked,
        "denied_reasons": denied,
        "warnings": [],
        "inputs": {
            "startup_demand": {**projection, "requested": demand},
            "thermal_safety": dict(thermal_safety),
        },
        "policy": {
            "fresh_physical_memory_and_psi_per_request": True,
            "zram_free_not_counted_as_ram": True,
            "outstanding_runtime_leases_counted": True,
            "battery_and_power_mode_are_advisory_not_admission_authority": True,
            "thermal_emergency_is_authoritative": True,
            "pressure_facts_assign_workload_importance": False,
            "existing_processes_mutated": False,
            "resident_memory_controller_required": False,
        },
    }


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
    return {
        "runner": "systemd-run",
        "unit_type": unit_type if unit_type in {"service", "scope"} else "service",
        "slice": scope_for_kind(policy, kind),
        "properties": properties,
        "env": {str(key): str(value) for key, value in env.items()} if isinstance(env, dict) else {},
        "policy": {
            "static_memory_caps_applied": False,
            "memory_high_not_set": True,
            "memory_max_not_set": True,
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
        explicit_allowed = write_preflight.get("allowed")
        allowed = (
            explicit_allowed
            if isinstance(explicit_allowed, bool)
            else bool(write_preflight.get("ok")) and decision == "allow"
        )
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


def thermal_plan_gate_reasons(
    thermal_plan: dict[str, Any] | None,
    normalized_class: str,
    unattended: bool,
    force: bool,
    active_game: bool,
    sample_thermal: bool,
    *,
    thermal_unattended_cap: str,
    activity: str | None = None,
) -> tuple[list[str], list[str]]:
    if not isinstance(thermal_plan, dict):
        return [], []
    blocked: list[str] = []
    warnings: list[str] = []
    activity_data = owner_activity(activity, unattended=unattended)
    foreground = bool(activity_data.get("foreground"))
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
        foreground_allowed = thermal_rec.get("foreground_allowed") is True
        if not thermal_rec_allowed and not force and not thermal_rec_game_only_denial:
            if foreground and foreground_allowed:
                warnings.append("thermal_plan_owner_foreground_advisory_defer")
            else:
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
    activity: str | None = None,
) -> dict[str, Any]:
    normalized_class = normalize_class(workload_class)
    normalized_kind = normalize_kind(kind)
    activity_data = owner_activity(activity, unattended=unattended)
    effective_unattended = bool(activity_data.get("background"))
    foreground = bool(activity_data.get("foreground"))
    force_effective = force_effective_for_request(force, effective_unattended)
    blocked: list[str] = []
    denied: list[str] = []
    warnings: list[str] = []
    denied.extend(str(item) for item in activity_data.get("errors", []))
    if bool(force) and not force_effective:
        warnings.append("unattended_force_not_operator_effective")
    route_available = bool(route.get("ok"))
    route_allowed = bool(route.get("allowed"))
    route_foreground_allowed = route.get("foreground_allowed") is True
    if not route_available:
        blocked.append("cpu_route_denied")
    elif not route_allowed and not force_effective:
        if foreground and route_foreground_allowed:
            warnings.append("cpu_route_owner_foreground_advisory_defer")
        else:
            blocked.append("cpu_route_denied")
    if effective_unattended and not bool(route.get("unattended_allowed")) and not force_effective:
        blocked.append("cpu_route_unattended_denied")

    active_game = bool(game_guard.get("active"))
    blocked.extend(game_guard_block_reasons(policy, normalized_class, effective_unattended, active_game, force_effective))

    demand_data = startup_demand if isinstance(startup_demand, dict) else {}
    demand_gate = demand_data.get("gate") if isinstance(demand_data.get("gate"), dict) else {}
    blocked.extend(str(item) for item in demand_gate.get("blocked_reasons", []) or [])
    denied.extend(str(item) for item in demand_gate.get("denied_reasons", []) or [])
    warnings.extend(str(item) for item in demand_gate.get("warnings", []) or [])

    launch_policy = mode.get("launch_policy", {}) if isinstance(mode.get("launch_policy"), dict) else {}
    max_unattended = str(launch_policy.get("max_unattended_class") or "probe")
    if effective_unattended and workload_level(normalized_class) > workload_level(max_unattended) and not force_effective:
        blocked.append(f"mode_unattended_cap_{max_unattended}")

    thermal_blocked, thermal_warnings = thermal_plan_gate_reasons(
        thermal_plan,
        normalized_class,
        effective_unattended,
        force_effective,
        active_game,
        bool(sample_thermal),
        thermal_unattended_cap=thermal_unattended_cap,
        activity=str(activity_data.get("normalized") or "unspecified"),
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
        unattended=effective_unattended,
    )
    return {
        "schema": f"{schema_prefix}_resource_plan_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": decision == "allow",
        "decision": decision,
        "forced": bool(force),
        "force_effective": bool(force_effective),
        "unattended": effective_unattended,
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
            "activity": activity_data,
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
            "static_memory_caps_applied": False,
            "memory_high_not_set": "MemoryHigh" not in (systemd.get("properties") if isinstance(systemd.get("properties"), dict) else {}),
            "memory_max_not_set": "MemoryMax" not in (systemd.get("properties") if isinstance(systemd.get("properties"), dict) else {}),
            "cpu_quota_not_set_by_default": True,
            "force_does_not_override_storage_denials": True,
            "force_effective_only_when_unattended_false": True,
            "numeric_memory_class_gating": False,
            "swap_occupancy_gating": False,
            "pressure_facts_assign_workload_importance": False,
            "owner_declared_foreground_can_bypass_advisory_power_defer_only": True,
            "foreground_never_bypasses_memory_reserve_or_emergency_route_denial": True,
            "legacy_memory_recommendations_are_advisory": True,
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

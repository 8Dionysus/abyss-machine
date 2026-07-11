from __future__ import annotations

from copy import deepcopy
import math
from pathlib import PurePosixPath
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import unquote, urlsplit


PRESSURE_RANK = {"healthy": 0, "watch": 1, "warm": 2, "hot": 3, "critical": 4}
ACTION_ORDER = {
    "queue_control": 0,
    "cooperative_cache_release": 1,
    "managed_dehydrate": 2,
    "owner_restart": 3,
    "observe": 99,
}
LIFECYCLE_ACTION_ROUTE = {
    "cooperative_cache_release": ("cache_release", "checkpoint"),
    "managed_dehydrate": ("dehydrate",),
    "owner_restart": ("restart",),
}
MUTATION_ROUTE_NAMES = frozenset({"cache_release", "checkpoint", "dehydrate", "rehydrate", "restart", "rollback"})
PROBE_ROUTE_NAMES = frozenset({"activity", "health"})
SUPPORTED_ROUTE_KIND = "local_http_json_v1"
_EXPECTATION_PATH_PARTS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.")


def default_policy() -> dict[str, Any]:
    return {
        "schema": "abyss_machine_memory_controller_policy_v1",
        "version": "1",
        "mode": "shadow",
        "rollout": {"stage": "shadow", "live_actuator_count": 0, "requires_natural_load_hours": 6},
        "event_loop": {
            "heartbeat_sec": 10.0,
            "debounce_ms": 200,
            "max_coalesce_ms": 1_000,
            "systemd": {"managed_prefixes": ["abyss-machine-"]},
            "psi": {
                "some": {"threshold_usec": 100_000, "window_usec": 2_000_000},
                "full": {"threshold_usec": 20_000, "window_usec": 2_000_000},
            },
        },
        "forecast": {
            "horizons_sec": [10, 30, 120],
            "minimum_samples": 3,
            "minimum_span_sec": 60.0,
            "freshness_sec": 30.0,
            "sample_window_limit": 512,
            "sample_window_sec": 600.0,
            "memory_bands_percent": {"watch": 35.0, "warm": 25.0, "hot": 15.0, "critical": 10.0},
            "active_stall_percent": {"some": 2.0, "full": 0.5},
            "major_faults_per_sec": 20.0,
            "swap_in_pages_per_sec": 128.0,
            "swap_churn_pages_per_sec": 256.0,
            "stall_persistence": {"active_sec": 10.0, "severe_sec": 30.0, "major_fault_multiplier": 4.0},
            "residual_zram_swap_percent": 30.0,
            "target_swap_free_mib": 2_048.0,
        },
        "utility": {
            "ram_benefit_per_mib": 0.025,
            "stall_relief_bonus": 120.0,
            "work_admission_bonus": 80.0,
            "rehydrate_ms_cost": 0.01,
            "cache_loss_mib_cost": 0.01,
            "rehydrate_energy_mwh_cost": 0.1,
            "stateful_penalty": 500.0,
            "uncertainty_penalty": 100.0,
            "minimum_score": 1.0,
        },
        "queue": {"starvation_sec": 4.0, "grant_ttl_sec": 5.0, "maximum_wait_sec": 120.0},
        "history": {
            "sample_limit": 30_000,
            "decision_limit": 30_000,
            "retention_hours": 24.0,
            "processed_event_limit": 512,
        },
        "calibration": {"maximum_step_ratio": 0.15, "minimum_mib": 64.0, "maximum_mib": 131_072.0},
        "safety": {
            "unknown_preserved": True,
            "protected_preserved": True,
            "one_relief_action_at_a_time": True,
            "generic_kill": False,
            "swapoff": False,
            "drop_caches": False,
            "automatic_oomd": False,
            "live_zram_resize": False,
            "generic_root_shell": False,
        },
        "actions": {
            "queue_control": {"enabled": True, "live_enabled": False},
            "cooperative_cache_release": {"enabled": True, "live_enabled": False},
            "managed_dehydrate": {"enabled": True, "live_enabled": False},
            "owner_restart": {"enabled": False, "live_enabled": False},
        },
        "execution": {
            "enrolled": False,
            "typed_plans_only": True,
            "local_http_literal_only": True,
            "action_plan_ttl_sec": 5.0,
            "generic_process_mutation": False,
        },
        "adviser": {
            "enabled": False,
            "mutation_capability": False,
            "requires_shadow_ab_benefit": True,
        },
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _bounded(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def _merge(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(base))
    for key, value in overlay.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = _merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _json_pointer(document: Any, path: str) -> tuple[bool, Any]:
    current = document
    for part in str(path).split("."):
        if not part or not isinstance(current, Mapping) or part not in current:
            return False, None
        current = current[part]
    return True, current


def validate_lifecycle_route(name: str, raw: Any) -> dict[str, Any]:
    route = deepcopy(dict(raw)) if isinstance(raw, Mapping) else {}
    issues: list[str] = []
    normalized_name = str(name or "")
    if normalized_name not in MUTATION_ROUTE_NAMES | PROBE_ROUTE_NAMES:
        issues.append("route_name_invalid")
    if route.get("kind") != SUPPORTED_ROUTE_KIND:
        issues.append("route_kind_invalid")
    url = str(route.get("url") or "")
    if len(url) > 2_048 or any(ord(character) < 32 or ord(character) == 127 for character in url):
        issues.append("route_url_invalid")
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
    except ValueError:
        parsed = urlsplit("")
        hostname = None
        issues.append("route_url_invalid")
    try:
        port = parsed.port
    except ValueError:
        port = None
        issues.append("route_port_invalid")
    if parsed.scheme != "http":
        issues.append("route_scheme_must_be_http")
    if hostname not in {"127.0.0.1", "::1"}:
        issues.append("route_host_must_be_loopback_literal")
    if port is None or not 1 <= port <= 65_535:
        issues.append("route_explicit_port_required")
    if parsed.username or parsed.password:
        issues.append("route_userinfo_forbidden")
    if parsed.fragment:
        issues.append("route_fragment_forbidden")
    decoded_path = unquote(parsed.path or "")
    if not decoded_path.startswith("/") or any(part == ".." for part in decoded_path.split("/")):
        issues.append("route_path_invalid")
    expected_method = "POST" if normalized_name in MUTATION_ROUTE_NAMES else "GET"
    method = str(route.get("method") or expected_method).upper()
    if method != expected_method:
        issues.append(f"route_method_must_be_{expected_method.lower()}")
    timeout_ms = _finite(route.get("timeout_ms"))
    if timeout_ms is None:
        timeout_ms = 2_000.0
    if not 50.0 <= timeout_ms <= 5_000.0:
        issues.append("route_timeout_out_of_bounds")
    maximum_bytes = _finite(route.get("maximum_response_bytes"))
    if maximum_bytes is None:
        maximum_bytes = 65_536.0
    if not 256.0 <= maximum_bytes <= 262_144.0:
        issues.append("route_response_limit_out_of_bounds")
    expect = _mapping(route.get("expect"))
    json_equals = _mapping(expect.get("json_equals"))
    for path in json_equals:
        if not path or any(character not in _EXPECTATION_PATH_PARTS for character in str(path)) or ".." in str(path):
            issues.append("route_expectation_path_invalid")
    if normalized_name in PROBE_ROUTE_NAMES and not json_equals:
        issues.append("probe_expectation_required")
    normalized = {
        "kind": SUPPORTED_ROUTE_KIND,
        "url": url,
        "method": method,
        "timeout_ms": int(timeout_ms),
        "maximum_response_bytes": int(maximum_bytes),
        "expect": {"json_equals": json_equals},
    }
    return {"valid": not issues, "issues": sorted(set(issues)), "route": normalized}


def evaluate_route_response(route: Mapping[str, Any], document: Any) -> dict[str, Any]:
    expectations = _mapping(_mapping(route.get("expect")).get("json_equals"))
    mismatches: list[dict[str, Any]] = []
    for path, expected in expectations.items():
        present, observed = _json_pointer(document, str(path))
        if not present or observed != expected:
            mismatches.append({"path": str(path), "expected": expected, "observed": observed, "present": present})
    return {
        "ok": not mismatches,
        "status": "expectations_met" if not mismatches else "expectation_mismatch",
        "mismatches": mismatches,
    }


def validate_measurement_contract(raw: Any) -> dict[str, Any]:
    measurement = _mapping(raw)
    issues: list[str] = []
    if measurement.get("kind") != "cgroup_v2_v1":
        issues.append("measurement_kind_invalid")
    uid = _finite(measurement.get("uid"))
    if uid is None or uid < 0 or not float(uid).is_integer():
        issues.append("measurement_uid_invalid")
        resolved_uid = -1
    else:
        resolved_uid = int(uid)
    path = str(measurement.get("path") or "")
    normalized_path = str(PurePosixPath(path)) if path else ""
    expected_prefix = f"/sys/fs/cgroup/user.slice/user-{resolved_uid}.slice/"
    if (
        not path.startswith(expected_prefix)
        or normalized_path != path
        or any(part == ".." for part in PurePosixPath(path).parts)
    ):
        issues.append("measurement_path_not_exact_user_cgroup")
    return {
        "valid": not issues,
        "issues": sorted(set(issues)),
        "measurement": {"kind": "cgroup_v2_v1", "uid": resolved_uid, "path": path},
    }


def resolve_policy(raw: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return _merge(default_policy(), raw or {})


def validate_policy(raw: Mapping[str, Any] | None = None) -> dict[str, Any]:
    supplied = dict(raw) if isinstance(raw, Mapping) else {}
    policy = resolve_policy(supplied)
    issues: list[str] = []
    if supplied and supplied.get("schema") != "abyss_machine_memory_controller_policy_v1":
        issues.append("policy_schema_invalid")
    mode = str(policy.get("mode") or "")
    if mode not in {"shadow", "live"}:
        issues.append("policy_mode_invalid")
    safety = _mapping(policy.get("safety"))
    for name in ("unknown_preserved", "protected_preserved", "one_relief_action_at_a_time"):
        if safety.get(name) is not True:
            issues.append(f"required_safety_invariant_disabled:{name}")
    for name in ("generic_kill", "swapoff", "drop_caches", "automatic_oomd", "live_zram_resize", "generic_root_shell"):
        if safety.get(name) is not False:
            issues.append(f"forbidden_safety_capability_enabled:{name}")
    actions = _mapping(policy.get("actions"))
    for name in ACTION_ORDER:
        if name == "observe":
            continue
        action = _mapping(actions.get(name))
        if action.get("live_enabled") is True and action.get("enabled") is not True:
            issues.append(f"live_action_not_enabled:{name}")
    adviser = _mapping(policy.get("adviser"))
    if adviser.get("mutation_capability") not in {None, False}:
        issues.append("adviser_mutation_capability_forbidden")
    execution = _mapping(policy.get("execution"))
    if execution.get("typed_plans_only") is not True:
        issues.append("typed_action_plans_required")
    if execution.get("local_http_literal_only") is not True:
        issues.append("local_http_literal_routes_required")
    if execution.get("generic_process_mutation") is not False:
        issues.append("generic_process_mutation_forbidden")
    if mode == "live" and execution.get("enrolled") is not True:
        issues.append("live_mode_requires_enrolled_executor")
    numeric_specs = (
        (("event_loop", "heartbeat_sec"), 1.0, 3_600.0),
        (("event_loop", "debounce_ms"), 0.0, 60_000.0),
        (("event_loop", "max_coalesce_ms"), 0.0, 60_000.0),
        (("event_loop", "psi", "some", "threshold_usec"), 1.0, 1_000_000_000.0),
        (("event_loop", "psi", "some", "window_usec"), 1.0, 1_000_000_000.0),
        (("event_loop", "psi", "full", "threshold_usec"), 1.0, 1_000_000_000.0),
        (("event_loop", "psi", "full", "window_usec"), 1.0, 1_000_000_000.0),
        (("forecast", "minimum_samples"), 2.0, 10_000.0),
        (("forecast", "minimum_span_sec"), 0.0, 86_400.0),
        (("forecast", "freshness_sec"), 1.0, 3_600.0),
        (("forecast", "sample_window_limit"), 3.0, 30_000.0),
        (("forecast", "sample_window_sec"), 60.0, 3_600.0),
        (("forecast", "active_stall_percent", "some"), 0.0, 100.0),
        (("forecast", "active_stall_percent", "full"), 0.0, 100.0),
        (("forecast", "major_faults_per_sec"), 0.0, 1_000_000.0),
        (("forecast", "swap_in_pages_per_sec"), 0.0, 1_000_000.0),
        (("forecast", "swap_churn_pages_per_sec"), 0.0, 1_000_000.0),
        (("forecast", "stall_persistence", "active_sec"), 0.0, 60.0),
        (("forecast", "stall_persistence", "severe_sec"), 0.0, 120.0),
        (("forecast", "stall_persistence", "major_fault_multiplier"), 1.0, 20.0),
        (("forecast", "residual_zram_swap_percent"), 0.0, 100.0),
        (("forecast", "target_swap_free_mib"), 0.0, 1_000_000.0),
        (("queue", "starvation_sec"), 1.0, 3_600.0),
        (("queue", "grant_ttl_sec"), 1.0, 60.0),
        (("queue", "maximum_wait_sec"), 1.0, 3_600.0),
        (("history", "sample_limit"), 3.0, 1_000_000.0),
        (("history", "decision_limit"), 3.0, 1_000_000.0),
        (("history", "retention_hours"), 6.0, 8_760.0),
        (("history", "processed_event_limit"), 32.0, 1_000_000.0),
        (("execution", "action_plan_ttl_sec"), 1.0, 60.0),
        (("calibration", "maximum_step_ratio"), 0.0, 1.0),
        (("calibration", "minimum_mib"), 0.0, 1_000_000.0),
        (("calibration", "maximum_mib"), 1.0, 1_000_000.0),
    )

    def policy_value(path: tuple[str, ...]) -> Any:
        current: Any = policy
        for key in path:
            current = current.get(key) if isinstance(current, Mapping) else None
        return current

    for path, minimum, maximum in numeric_specs:
        value = _finite(policy_value(path))
        if value is None or value < minimum or value > maximum:
            issues.append(f"policy_number_invalid:{'.'.join(path)}")
    horizons = _mapping(policy.get("forecast")).get("horizons_sec")
    if (
        not isinstance(horizons, list)
        or not horizons
        or any((_finite(item) or 0.0) <= 0 or (_finite(item) or 0.0) > 3_600 for item in horizons)
        or len({int(_finite(item) or 0) for item in horizons}) != len(horizons)
    ):
        issues.append("forecast_horizons_invalid")
    bands = _mapping(_mapping(policy.get("forecast")).get("memory_bands_percent"))
    ordered_bands = [_finite(bands.get(name)) for name in ("critical", "hot", "warm", "watch")]
    if any(value is None or value <= 0 or value >= 100 for value in ordered_bands) or ordered_bands != sorted(ordered_bands):
        issues.append("forecast_memory_bands_invalid")
    persistence = _mapping(_mapping(policy.get("forecast")).get("stall_persistence"))
    if (_finite(persistence.get("severe_sec")) or 0.0) < (_finite(persistence.get("active_sec")) or 0.0):
        issues.append("stall_persistence_order_invalid")
    queue = _mapping(policy.get("queue"))
    if (_finite(queue.get("starvation_sec")) or math.inf) * 4 > (_finite(queue.get("maximum_wait_sec")) or 0.0):
        issues.append("queue_starvation_window_exceeds_maximum_wait")
    calibration = _mapping(policy.get("calibration"))
    if (_finite(calibration.get("minimum_mib")) or math.inf) > (_finite(calibration.get("maximum_mib")) or 0.0):
        issues.append("calibration_bounds_invalid")
    return {"valid": not issues, "issues": sorted(set(issues)), "policy": policy}


def validate_workload_contract(raw: Mapping[str, Any]) -> dict[str, Any]:
    contract = deepcopy(dict(raw))
    issues: list[str] = []
    if not str(contract.get("id") or "").strip():
        issues.append("identity_required")
    if not str(contract.get("owner") or "").strip():
        issues.append("owner_required")
    raw_lifecycle = _mapping(contract.get("lifecycle"))
    lifecycle: dict[str, Any] = {}
    for route_name, route_value in raw_lifecycle.items():
        checked_route = validate_lifecycle_route(str(route_name), route_value)
        if not checked_route["valid"]:
            issues.extend(f"lifecycle_route_invalid:{route_name}:{issue}" for issue in checked_route["issues"])
        lifecycle[str(route_name)] = checked_route["route"]
    mutation_routes = {name for name in ("cache_release", "checkpoint", "dehydrate", "restart") if lifecycle.get(name)}
    if mutation_routes and not lifecycle.get("activity"):
        issues.append("activity_route_required")
    if mutation_routes and not lifecycle.get("health"):
        issues.append("health_route_required")
    if mutation_routes and not lifecycle.get("rollback"):
        issues.append("rollback_route_required")
    if lifecycle.get("dehydrate") and not lifecycle.get("rehydrate"):
        issues.append("rehydrate_route_required")
    if mutation_routes and lifecycle.get("health"):
        health_expect = _mapping(_mapping(lifecycle["health"].get("expect")).get("json_equals"))
        if not {"service", "workload_id", "capability_id"} & set(health_expect):
            issues.append("health_identity_expectation_required")
    enrollment = _mapping(contract.get("enrollment"))
    measurement_checked = validate_measurement_contract(contract.get("measurement"))
    if enrollment:
        if enrollment.get("status") not in {"enrolled", "disabled"}:
            issues.append("enrollment_status_invalid")
        if enrollment.get("status") == "enrolled":
            if not str(enrollment.get("id") or ""):
                issues.append("enrollment_id_required")
            if enrollment.get("owner_approved") is not True:
                issues.append("enrollment_owner_approval_required")
            enrolled_actions = enrollment.get("allowed_actions") if isinstance(enrollment.get("allowed_actions"), list) else []
            if not enrolled_actions or any(str(item) not in LIFECYCLE_ACTION_ROUTE for item in enrolled_actions):
                issues.append("enrollment_allowed_actions_invalid")
            expiry = _finite(enrollment.get("expires_epoch"))
            if enrollment.get("expires_epoch") is not None and (expiry is None or expiry <= 0):
                issues.append("enrollment_expiry_invalid")
            if not measurement_checked["valid"]:
                issues.extend(measurement_checked["issues"])
    expected_mib = _finite(_mapping(contract.get("memory")).get("expected_mib"))
    if expected_mib is not None and expected_mib < 0:
        issues.append("memory_envelope_invalid")
    normalized = {
        "id": str(contract.get("id") or "").strip(),
        "owner": str(contract.get("owner") or "").strip(),
        "organ": str(contract.get("organ") or contract.get("owner") or "").strip(),
        "role": str(contract.get("role") or "unknown"),
        "importance": str(contract.get("importance") or "unknown"),
        "posture": str(contract.get("posture") or "unknown"),
        "statefulness": str(contract.get("statefulness") or "unknown"),
        "protected": bool(contract.get("protected", False)),
        "registry_status": str(contract.get("registry_status") or "unresolved"),
        "memory": _mapping(contract.get("memory")),
        "activity": _mapping(contract.get("activity")),
        "sla": _mapping(contract.get("sla")),
        "lifecycle": lifecycle,
        "enrollment": enrollment,
        "measurement": measurement_checked["measurement"] if contract.get("measurement") is not None else {},
        "residency": _mapping(contract.get("residency")),
        "metadata": _mapping(contract.get("metadata")),
    }
    return {"valid": not issues, "issues": sorted(set(issues)), "contract": normalized}


def _rule_matches(rule: Mapping[str, Any], observed: Mapping[str, Any]) -> bool:
    match = _mapping(rule.get("match"))
    if not match:
        return False
    for key, allowed in match.items():
        values = allowed if isinstance(allowed, Sequence) and not isinstance(allowed, (str, bytes)) else [allowed]
        if str(observed.get(key) or "") not in {str(value) for value in values}:
            return False
    return True


def _allowed_actions(contract: Mapping[str, Any]) -> list[str]:
    if bool(contract.get("protected")) or str(contract.get("importance")) in {"protected", "unknown"}:
        return ["observe"]
    lifecycle = _mapping(contract.get("lifecycle"))
    actions = ["observe"]
    if lifecycle.get("cache_release") or lifecycle.get("checkpoint"):
        actions.append("cooperative_cache_release")
    if lifecycle.get("dehydrate") and lifecycle.get("rehydrate") and lifecycle.get("health") and lifecycle.get("rollback"):
        actions.append("managed_dehydrate")
    if lifecycle.get("restart") and lifecycle.get("health") and lifecycle.get("rollback"):
        actions.append("owner_restart")
    return actions


def lifecycle_action_enrolled(contract: Mapping[str, Any], action: str, *, now_epoch: float) -> dict[str, Any]:
    normalized_action = str(action or "")
    enrollment = _mapping(contract.get("enrollment"))
    metadata = _mapping(contract.get("metadata"))
    allowed = enrollment.get("allowed_actions") if isinstance(enrollment.get("allowed_actions"), list) else []
    expiry = _finite(enrollment.get("expires_epoch"))
    checks = {
        "workload_not_protected": not bool(contract.get("protected")) and str(contract.get("importance")) not in {"protected", "unknown"},
        "exact_static_contract": contract.get("registry_status") == "exact" and metadata.get("registry_source") == "static",
        "trusted_static_projection": metadata.get("registry_trusted_for_lifecycle") is True,
        "owner_approved": enrollment.get("owner_approved") is True,
        "enrollment_active": enrollment.get("status") == "enrolled",
        "action_allowlisted": normalized_action in {str(item) for item in allowed},
        "not_expired": expiry is None or expiry > float(now_epoch),
    }
    return {
        "authorized": all(checks.values()),
        "action": normalized_action,
        "checks": checks,
        "enrollment_id": str(enrollment.get("id") or ""),
        "expires_epoch": expiry,
    }


def unknown_preserve_contract(observed: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **deepcopy(dict(observed)),
        "id": str(observed.get("id") or "unknown"),
        "owner": str(observed.get("owner") or "unknown"),
        "organ": str(observed.get("organ") or "unknown"),
        "role": str(observed.get("role") or "unknown"),
        "importance": "unknown",
        "posture": str(observed.get("posture") or "unknown"),
        "statefulness": "unknown",
        "protected": True,
        "registry_status": "unknown_preserve",
        "allowed_actions": ["observe"],
    }


def _merge_observed_facts(contract: Mapping[str, Any], observed: Mapping[str, Any]) -> dict[str, Any]:
    merged = deepcopy(dict(contract))
    for name in ("memory", "activity", "metadata"):
        if isinstance(observed.get(name), Mapping):
            merged[name] = _merge(_mapping(merged.get(name)), _mapping(observed.get(name)))
    return merged


def resolve_workload(registry: Mapping[str, Any], observed: Mapping[str, Any]) -> dict[str, Any]:
    observed_id = str(observed.get("id") or "")
    for raw in registry.get("workloads", []) if isinstance(registry.get("workloads"), list) else []:
        if isinstance(raw, Mapping) and str(raw.get("id") or "") == observed_id:
            checked = validate_workload_contract(_merge_observed_facts(raw, observed))
            if not checked["valid"]:
                preserved = unknown_preserve_contract(observed)
                preserved["contract_issues"] = checked["issues"]
                return preserved
            contract = checked["contract"]
            contract["registry_status"] = "exact"
            contract["allowed_actions"] = _allowed_actions(contract)
            return contract
    for rule in registry.get("rules", []) if isinstance(registry.get("rules"), list) else []:
        if isinstance(rule, Mapping) and _rule_matches(rule, observed):
            contract = _merge_observed_facts(_mapping(rule.get("contract")), observed)
            contract.setdefault("id", observed_id or f"rule:{rule.get('id') or 'matched'}")
            contract.setdefault("owner", str(_mapping(rule.get("contract")).get("owner") or "unknown"))
            contract["registry_status"] = f"rule:{rule.get('id') or 'matched'}"
            contract["allowed_actions"] = _allowed_actions(contract)
            return contract
    return unknown_preserve_contract(observed)


def _linear_slope(samples: Sequence[Mapping[str, Any]], field: str) -> float | None:
    points = [(float(item["epoch"]), value) for item in samples if (value := _finite(item.get(field))) is not None]
    if len(points) < 2:
        return None
    origin = points[0][0]
    xs = [point[0] - origin for point in points]
    ys = [point[1] for point in points]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    denominator = sum((value - mean_x) ** 2 for value in xs)
    if denominator <= 0:
        return None
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True)) / denominator


def _counter_rate(samples: Sequence[Mapping[str, Any]], field: str) -> float:
    points = [(float(item["epoch"]), value) for item in samples if (value := _finite(item.get(field))) is not None]
    if len(points) < 2:
        return 0.0
    first, last = points[-2], points[-1]
    elapsed = last[0] - first[0]
    return 0.0 if elapsed <= 0 else max(0.0, last[1] - first[1]) / elapsed


def _band_for_percent(percent: float, policy: Mapping[str, Any]) -> str:
    bands = _mapping(_mapping(policy.get("forecast")).get("memory_bands_percent"))
    if percent <= float(bands.get("critical", 10.0)):
        return "critical"
    if percent <= float(bands.get("hot", 15.0)):
        return "hot"
    if percent <= float(bands.get("warm", 25.0)):
        return "warm"
    if percent <= float(bands.get("watch", 35.0)):
        return "watch"
    return "healthy"


def _max_band(*bands: str) -> str:
    return max(bands, key=lambda item: PRESSURE_RANK.get(item, 0))


def build_forecast(
    samples: Iterable[Mapping[str, Any]],
    *,
    outstanding_mib: float,
    queued_demand_mib: float,
    policy: Mapping[str, Any] | None = None,
    now_epoch: float | None = None,
) -> dict[str, Any]:
    resolved_policy = resolve_policy(policy)
    forecast_policy = _mapping(resolved_policy.get("forecast"))
    ordered = sorted((dict(item) for item in samples if _finite(item.get("epoch")) is not None), key=lambda item: float(item["epoch"]))
    if not ordered:
        return {
            "ok": False,
            "status": "missing_samples",
            "confidence": "none",
            "confidence_reasons": ["missing_samples"],
            "active_memory_relief_needed": False,
            "new_work_control_needed": False,
            "pressure_band": "unknown",
            "projections": {},
        }
    current = ordered[-1]
    current_epoch = float(current["epoch"])
    resolved_now = current_epoch if now_epoch is None else float(now_epoch)
    key_fields = ("mem_total_mib", "mem_available_mib", "psi_some_total_usec", "psi_full_total_usec", "pgmajfault")
    invalid_count = sum(1 for item in ordered for field in key_fields if _finite(item.get(field)) is None)
    span = max(0.0, current_epoch - float(ordered[0]["epoch"]))
    freshness = max(0.0, resolved_now - current_epoch)
    minimum_samples = int(forecast_policy.get("minimum_samples", 3))
    minimum_span = float(forecast_policy.get("minimum_span_sec", 60.0))
    freshness_limit = float(forecast_policy.get("freshness_sec", 30.0))
    confidence_reasons: list[str] = []
    if invalid_count:
        confidence_reasons.append("invalid_or_missing_samples")
    if len(ordered) < minimum_samples:
        confidence_reasons.append("insufficient_samples")
    if span < minimum_span:
        confidence_reasons.append("insufficient_span")
    if freshness > freshness_limit:
        confidence_reasons.append("stale_latest_sample")
    if not confidence_reasons:
        confidence = "high"
    elif freshness <= freshness_limit and len(ordered) >= 2:
        confidence = "medium"
    else:
        confidence = "low"
    total_mib = _finite(current.get("mem_total_mib")) or 0.0
    available_mib = _finite(current.get("mem_available_mib")) or 0.0
    declared_mib = max(0.0, _finite(outstanding_mib) or 0.0) + max(0.0, _finite(queued_demand_mib) or 0.0)
    trend_ready = len(ordered) >= minimum_samples and span >= minimum_span and freshness <= freshness_limit
    available_slope = (_linear_slope(ordered, "mem_available_mib") or 0.0) if trend_ready else 0.0
    zram_slope = (_linear_slope(ordered, "zram_resident_mib") or 0.0) if trend_ready else 0.0
    swap_slope = (_linear_slope(ordered, "swap_used_mib") or 0.0) if trend_ready else 0.0
    some_percent = _counter_rate(ordered, "psi_some_total_usec") / 1_000_000.0 * 100.0
    full_percent = _counter_rate(ordered, "psi_full_total_usec") / 1_000_000.0 * 100.0
    major_faults_per_sec = _counter_rate(ordered, "pgmajfault")
    swap_in_pages_per_sec = _counter_rate(ordered, "pswpin")
    swap_out_pages_per_sec = _counter_rate(ordered, "pswpout")
    oom_delta = _counter_rate(ordered, "oom_kill")
    projections: dict[str, Any] = {}
    projected_bands: list[str] = []
    for raw_horizon in forecast_policy.get("horizons_sec", [10, 30, 120]):
        horizon = max(0, int(raw_horizon))
        projected_available = max(0.0, available_mib - declared_mib + available_slope * horizon)
        percent = 0.0 if total_mib <= 0 else projected_available / total_mib * 100.0
        band = _band_for_percent(percent, resolved_policy)
        projected_bands.append(band)
        projections[str(horizon)] = {
            "mem_available_mib": round(projected_available, 3),
            "mem_available_percent": round(percent, 3),
            "pressure_band": band,
        }
    current_percent = 0.0 if total_mib <= 0 else available_mib / total_mib * 100.0
    current_band = _band_for_percent(current_percent, resolved_policy)
    stall_thresholds = _mapping(forecast_policy.get("active_stall_percent"))
    active_some = some_percent >= float(stall_thresholds.get("some", 2.0))
    active_full = full_percent >= float(stall_thresholds.get("full", 0.5))
    active_faults = major_faults_per_sec >= float(forecast_policy.get("major_faults_per_sec", 20.0))
    swap_in_threshold = float(forecast_policy.get("swap_in_pages_per_sec", 128.0))
    swap_churn_threshold = float(forecast_policy.get("swap_churn_pages_per_sec", 256.0))
    active_swap_churn = swap_in_pages_per_sec >= swap_in_threshold and (
        swap_out_pages_per_sec >= swap_churn_threshold
        or some_percent > 0.0
        or PRESSURE_RANK.get(current_band, 0) >= PRESSURE_RANK["hot"]
    )
    active_oom = oom_delta > 0.0
    active_pressure = active_some or active_full or active_faults or active_swap_churn or active_oom
    persistence = _mapping(forecast_policy.get("stall_persistence"))
    active_persistence_sec = max(0.0, min(60.0, float(persistence.get("active_sec", 10.0))))
    severe_persistence_sec = max(
        active_persistence_sec,
        min(120.0, float(persistence.get("severe_sec", 30.0))),
    )
    major_fault_multiplier = max(1.0, min(20.0, float(persistence.get("major_fault_multiplier", 4.0))))
    severe_pressure = (
        active_some
        or active_full
        or active_oom
        or major_faults_per_sec >= float(forecast_policy.get("major_faults_per_sec", 20.0)) * major_fault_multiplier
    )
    for raw_horizon, projection in projections.items():
        horizon = float(raw_horizon)
        reasons: list[str] = []
        if PRESSURE_RANK.get(str(projection.get("pressure_band") or "unknown"), 0) >= PRESSURE_RANK["warm"]:
            reasons.append("projected_memory_band")
        if active_pressure and horizon <= active_persistence_sec:
            reasons.append("active_stall_persistence")
        if severe_pressure and horizon <= severe_persistence_sec:
            reasons.append("severe_stall_persistence")
        projection["pressure_expected"] = bool(reasons)
        projection["pressure_reasons"] = reasons
    pressure_band = _max_band(current_band, *projected_bands)
    if active_some or active_faults or active_swap_churn:
        pressure_band = _max_band(pressure_band, "hot")
    if active_full or active_oom:
        pressure_band = "critical"
    active_relief = active_pressure or PRESSURE_RANK.get(current_band, 0) >= PRESSURE_RANK["hot"]
    new_work_control = active_relief or any(PRESSURE_RANK.get(item, 0) >= PRESSURE_RANK["warm"] for item in projected_bands)
    swap_total = _finite(current.get("swap_total_mib")) or 0.0
    swap_used = _finite(current.get("swap_used_mib")) or 0.0
    swap_free = _finite(current.get("swap_free_mib")) or max(0.0, swap_total - swap_used)
    swap_percent = 0.0 if swap_total <= 0 else swap_used / swap_total * 100.0
    zram_data = _finite(current.get("zram_data_mib")) or 0.0
    zram_resident = _finite(current.get("zram_resident_mib")) or 0.0
    zram_incompressible = _finite(current.get("zram_incompressible_mib")) or 0.0
    zram_overhead = _finite(current.get("zram_allocator_metadata_overhead_mib")) or 0.0
    zram_physical_savings = _finite(current.get("zram_physical_savings_mib")) or max(0.0, zram_data - zram_resident)
    residual_zram = (
        swap_percent >= float(forecast_policy.get("residual_zram_swap_percent", 30.0))
        and not active_relief
        and swap_free >= float(forecast_policy.get("target_swap_free_mib", 2_048.0))
    )
    effective_available = available_mib - declared_mib
    time_to_threshold: dict[str, float | None] = {}
    for name in ("warm", "hot", "critical"):
        floor = total_mib * float(_mapping(forecast_policy.get("memory_bands_percent")).get(name, 0.0)) / 100.0
        value = None
        if effective_available <= floor:
            value = 0.0
        elif trend_ready and available_slope < 0:
            value = max(0.0, (effective_available - floor) / -available_slope)
        time_to_threshold[name] = None if value is None else round(value, 3)
    return {
        "ok": True,
        "status": "forecast_ready",
        "sample_count": len(ordered),
        "sample_span_sec": round(span, 3),
        "sample_age_sec": round(freshness, 3),
        "confidence": confidence,
        "confidence_reasons": confidence_reasons,
        "trend_ready": trend_ready,
        "current": {
            "mem_total_mib": round(total_mib, 3),
            "mem_available_mib": round(available_mib, 3),
            "mem_available_percent": round(current_percent, 3),
            "pressure_band": current_band,
            "declared_unmaterialized_demand_mib": round(declared_mib, 3),
            "swap_used_mib": round(swap_used, 3),
            "swap_free_mib": round(swap_free, 3),
        },
        "slopes": {
            "mem_available_mib_per_sec": round(available_slope, 6),
            "zram_resident_mib_per_sec": round(zram_slope, 6),
            "swap_used_mib_per_sec": round(swap_slope, 6),
        },
        "stall_rates": {
            "some_percent": round(some_percent, 3),
            "full_percent": round(full_percent, 3),
            "major_faults_per_sec": round(major_faults_per_sec, 3),
            "swap_in_pages_per_sec": round(swap_in_pages_per_sec, 3),
            "swap_out_pages_per_sec": round(swap_out_pages_per_sec, 3),
            "active_swap_churn": active_swap_churn,
            "oom_kills_per_sec": round(oom_delta, 6),
        },
        "projections": projections,
        "time_to_warm_sec": time_to_threshold["warm"],
        "time_to_threshold_sec": time_to_threshold,
        "pressure_band": pressure_band,
        "active_memory_relief_needed": active_relief,
        "new_work_control_needed": new_work_control,
        "residual_zram_debt": residual_zram,
        "zram": {
            "logical_data_mib": round(zram_data, 3),
            "resident_mib": round(zram_resident, 3),
            "physical_savings_mib": round(zram_physical_savings, 3),
            "allocator_metadata_overhead_mib": round(zram_overhead, 3),
            "incompressible_mib": round(zram_incompressible, 3),
            "logical_to_resident_ratio": None if zram_resident <= 0 else round(zram_data / zram_resident, 3),
            "incompressible_percent_of_logical": 0.0 if zram_data <= 0 else round(zram_incompressible / zram_data * 100.0, 3),
            "resident_percent_of_ram": 0.0 if total_mib <= 0 else round(zram_resident / total_mib * 100.0, 3),
            "backing_write_mib": round(_finite(current.get("zram_backing_write_mib")) or 0.0, 3),
        },
        "composition": {
            "cached_mib": round(_finite(current.get("cached_mib")) or 0.0, 3),
            "sreclaimable_mib": round(_finite(current.get("sreclaimable_mib")) or 0.0, 3),
            "commit_percent": round(_finite(current.get("commit_percent")) or 0.0, 3),
            "cgroup_memory_mib": round(_finite(current.get("cgroup_memory_mib")) or 0.0, 3),
            "cgroup_swap_mib": round(_finite(current.get("cgroup_swap_mib")) or 0.0, 3),
        },
        "policy": {
            "cold_zram_is_not_active_pressure": True,
            "nominal_zram_size_is_not_preallocated_ram": True,
            "declared_demand_is_not_counted_as_ram": True,
            "current_pressure_is_not_hidden_by_future_projection": True,
            "stall_pressure_has_bounded_persistence_projection": True,
        },
    }


def _workload_benefit_mib(workload: Mapping[str, Any]) -> float:
    memory = _mapping(workload.get("memory"))
    return max(0.0, _finite(memory.get("observed_mib")) or _finite(memory.get("expected_mib")) or 0.0)


def _lifecycle_utility(action: str, workload: Mapping[str, Any], forecast: Mapping[str, Any], policy: Mapping[str, Any]) -> dict[str, Any]:
    weights = _mapping(policy.get("utility"))
    memory = _mapping(workload.get("memory"))
    sla = _mapping(workload.get("sla"))
    components = {
        "ram_benefit": _workload_benefit_mib(workload) * float(weights.get("ram_benefit_per_mib", 0.025)),
        "stall_relief": float(weights.get("stall_relief_bonus", 120.0)) if forecast.get("active_memory_relief_needed") else 0.0,
        "work_admission": float(weights.get("work_admission_bonus", 80.0)) if forecast.get("new_work_control_needed") else 0.0,
        "cooperative_bonus": 20.0 if action == "cooperative_cache_release" else 0.0,
        "rehydrate_latency_cost": -max(0.0, _finite(sla.get("rehydrate_p95_ms")) or 0.0) * float(weights.get("rehydrate_ms_cost", 0.01)),
        "cache_loss_cost": -max(0.0, _finite(memory.get("cache_loss_mib")) or 0.0) * float(weights.get("cache_loss_mib_cost", 0.01)),
        "energy_cost": -max(0.0, _finite(sla.get("rehydrate_energy_mwh")) or 0.0) * float(weights.get("rehydrate_energy_mwh_cost", 0.1)),
        "stateful_cost": -float(weights.get("stateful_penalty", 500.0)) if str(workload.get("statefulness")) not in {"reconstructable", "stateless"} else 0.0,
        "uncertainty_cost": -float(weights.get("uncertainty_penalty", 100.0)) if str(_mapping(workload.get("activity")).get("confidence") or "unknown") != "high" else 0.0,
        "owner_sla_cost": -max(0.0, _finite(sla.get("owner_penalty")) or 0.0),
    }
    return {
        "score": round(sum(components.values()), 3),
        "components": {key: round(value, 3) for key, value in components.items()},
    }


def _cooldown_active(workload: Mapping[str, Any], state: Mapping[str, Any], now_epoch: float) -> bool:
    last = _mapping(_mapping(state.get("last_actions")).get(str(workload.get("id") or "")))
    last_epoch = _finite(last.get("epoch"))
    cooldown = max(0.0, _finite(_mapping(workload.get("residency")).get("cooldown_sec")) or 0.0)
    return last_epoch is not None and now_epoch - last_epoch < cooldown


def build_decision(
    *,
    forecast: Mapping[str, Any],
    workloads: Iterable[Mapping[str, Any]],
    controller_state: Mapping[str, Any],
    policy: Mapping[str, Any] | None = None,
    now_epoch: float,
) -> dict[str, Any]:
    resolved_policy = resolve_policy(policy)
    alternatives: list[dict[str, Any]] = [{"action": "observe", "score": 0.0, "safe": True}]
    actions = _mapping(resolved_policy.get("actions"))
    pending_queue = max(0, int(_finite(forecast.get("pending_queue_count")) or 0))
    if pending_queue and _mapping(actions.get("queue_control")).get("enabled", True):
        alternatives.append({
            "action": "queue_control",
            "score": float(_mapping(resolved_policy.get("utility")).get("work_admission_bonus", 80.0)),
            "safe": True,
            "reason": "pending_queue_requires_new_work_coordination",
        })
    if forecast.get("active_memory_relief_needed"):
        for raw in workloads:
            workload = deepcopy(dict(raw))
            checked = validate_workload_contract(workload)
            if not checked["valid"]:
                continue
            workload = checked["contract"]
            allowed = set(_allowed_actions(workload))
            if bool(workload.get("protected")) or str(workload.get("importance")) in {"protected", "unknown"}:
                continue
            activity = _mapping(workload.get("activity"))
            if activity.get("state") != "idle" or activity.get("confidence") != "high":
                continue
            if _cooldown_active(workload, controller_state, float(now_epoch)):
                continue
            for action in ("cooperative_cache_release", "managed_dehydrate", "owner_restart"):
                action_policy = _mapping(actions.get(action))
                if action not in allowed or not action_policy.get("enabled", False):
                    continue
                utility = _lifecycle_utility(action, workload, forecast, resolved_policy)
                score = float(utility["score"])
                if score < float(_mapping(resolved_policy.get("utility")).get("minimum_score", 1.0)):
                    continue
                lifecycle = _mapping(workload.get("lifecycle"))
                route_names = LIFECYCLE_ACTION_ROUTE[action]
                action_route_name = next((name for name in route_names if lifecycle.get(name)), "")
                enrollment = lifecycle_action_enrolled(workload, action, now_epoch=float(now_epoch))
                alternatives.append({
                    "action": action,
                    "workload_id": workload.get("id"),
                    "owner": workload.get("owner"),
                    "importance": workload.get("importance"),
                    "protected": bool(workload.get("protected")),
                    "score": score,
                    "utility": utility,
                    "safe": True,
                    "expected_freed_mib": round(_workload_benefit_mib(workload), 3),
                    "lifecycle_plan": {
                        "action_route_name": action_route_name,
                        "action_route": lifecycle.get(action_route_name),
                        "activity_route": lifecycle.get("activity"),
                        "health_route": lifecycle.get("health"),
                        "rollback_route": lifecycle.get("rollback"),
                        "rehydrate_route": lifecycle.get("rehydrate"),
                        "measurement": _mapping(workload.get("measurement")),
                    },
                    "enrollment": enrollment,
                    "stop_conditions": [
                        "forecast_or_sample_stale",
                        "activity_not_idle_high_confidence",
                        "health_or_identity_probe_failed",
                        "owner_enrollment_changed_or_expired",
                        "another_relief_action_active",
                        "action_plan_expired",
                    ],
                })
    actionable = [item for item in alternatives if item["action"] != "observe"]
    relief_actions = [item for item in actionable if item["action"] in LIFECYCLE_ACTION_ROUTE]
    selection_pool = relief_actions if forecast.get("active_memory_relief_needed") and relief_actions else actionable
    selected = min(selection_pool, key=lambda item: (ACTION_ORDER.get(str(item["action"]), 50), -float(item.get("score") or 0.0))) if selection_pool else alternatives[0]
    mode = str(resolved_policy.get("mode") or "shadow")
    action_policy = _mapping(actions.get(str(selected.get("action"))))
    lifecycle_enrollment = _mapping(selected.get("enrollment"))
    execution_policy = _mapping(resolved_policy.get("execution"))
    queue_execution_enrolled = selected.get("action") == "queue_control" and execution_policy.get("enrolled") is True
    lifecycle_enrollment_authorized = (
        selected.get("action") in LIFECYCLE_ACTION_ROUTE and lifecycle_enrollment.get("authorized") is True
    )
    enrollment_authorized = queue_execution_enrolled or lifecycle_enrollment_authorized
    live_authorized = bool(
        selected.get("action") != "observe"
        and mode == "live"
        and action_policy.get("live_enabled") is True
        and forecast.get("confidence") == "high"
        and enrollment_authorized
    )
    selected = {
        **selected,
        "execution": "live_authorized" if live_authorized else ("observe_only" if selected.get("action") == "observe" else "shadow_only"),
    }
    return {
        "schema": "abyss_machine_memory_controller_decision_v1",
        "ok": True,
        "mode": mode,
        "selected": selected,
        "alternatives": sorted(alternatives, key=lambda item: (ACTION_ORDER.get(str(item["action"]), 50), -float(item.get("score") or 0.0))),
        "live_action_authorized": live_authorized,
        "reason": {
            "pressure_band": forecast.get("pressure_band"),
            "confidence": forecast.get("confidence"),
            "active_memory_relief_needed": bool(forecast.get("active_memory_relief_needed")),
            "new_work_control_needed": bool(forecast.get("new_work_control_needed")),
            "pending_queue_count": pending_queue,
            "queue_hold_active": bool(pending_queue and forecast.get("active_memory_relief_needed")),
            "residual_zram_debt": bool(forecast.get("residual_zram_debt")),
            "selected_by": "cheapest_safe_reversible_action_then_utility",
            "action_enrollment_authorized": bool(enrollment_authorized),
            "queue_execution_enrolled": bool(queue_execution_enrolled),
            "lifecycle_enrollment_authorized": bool(lifecycle_enrollment_authorized),
        },
        "policy": {
            "unknown_preserved": True,
            "protected_preserved": True,
            "one_relief_action_at_a_time": True,
            "generic_process_mutation": False,
        },
    }


def order_queue(requests: Iterable[Mapping[str, Any]], *, now_epoch: float, starvation_sec: float) -> list[dict[str, Any]]:
    resolved_starvation = max(1.0, float(starvation_sec))
    ranked: list[dict[str, Any]] = []
    for raw in requests:
        item = deepcopy(dict(raw))
        created_value = _finite(item.get("created_epoch"))
        created = float(now_epoch) if created_value is None else created_value
        wait = max(0.0, float(now_epoch) - created)
        age_steps = int(wait // resolved_starvation)
        base = int(_finite(item.get("priority")) or 0)
        posture_bonus = 100 if item.get("posture") == "interactive" else 0
        effective = base + posture_bonus + min(40, age_steps * 10)
        item.update({
            "created_epoch": created,
            "wait_sec": round(wait, 3),
            "aged": age_steps > 0,
            "effective_priority": effective,
        })
        ranked.append(item)
    return sorted(ranked, key=lambda item: (-int(item["effective_priority"]), float(item["created_epoch"]), str(item.get("id") or "")))


def plan_queue(
    requests: Iterable[Mapping[str, Any]],
    *,
    samples: Iterable[Mapping[str, Any]],
    outstanding_mib: float,
    active_grants: Iterable[Mapping[str, Any]],
    policy: Mapping[str, Any] | None,
    now_epoch: float,
) -> dict[str, Any]:
    resolved_policy = resolve_policy(policy)
    queue_policy = _mapping(resolved_policy.get("queue"))
    ordered = order_queue(
        requests,
        now_epoch=float(now_epoch),
        starvation_sec=float(queue_policy.get("starvation_sec", 300.0)),
    )
    sample_list = [dict(item) for item in samples]
    active = [
        dict(item)
        for item in active_grants
        if (_finite(item.get("expires_epoch")) or 0.0) > float(now_epoch)
    ]
    decisions: list[dict[str, Any]] = []
    selected: dict[str, Any] | None = None
    for request in ordered:
        request_id = str(request.get("id") or "")
        demand_mib = _finite(request.get("demand_mib"))
        deadline = _finite(request.get("deadline_epoch"))
        base = {
            "request_id": request_id,
            "owner": request.get("owner"),
            "demand_mib": demand_mib,
            "effective_priority": request.get("effective_priority"),
            "wait_sec": request.get("wait_sec"),
        }
        if not request_id or demand_mib is None or demand_mib < 0:
            decisions.append({**base, "status": "reject", "reason": "invalid_request"})
            continue
        if deadline is not None and deadline <= float(now_epoch):
            decisions.append({**base, "status": "expired", "reason": "deadline_elapsed"})
            continue
        if active:
            decisions.append({**base, "status": "defer", "reason": "another_grant_is_active"})
            continue
        trial = build_forecast(
            sample_list,
            outstanding_mib=float(outstanding_mib),
            queued_demand_mib=demand_mib,
            policy=resolved_policy,
            now_epoch=float(now_epoch),
        )
        if trial.get("confidence") != "high":
            decisions.append({**base, "status": "defer", "reason": "insufficient_forecast_confidence"})
            continue
        if trial.get("active_memory_relief_needed") or trial.get("new_work_control_needed"):
            decisions.append({
                **base,
                "status": "defer",
                "reason": "request_would_cross_safe_headroom",
                "trial_pressure_band": trial.get("pressure_band"),
            })
            continue
        if selected is None:
            selected = {
                **base,
                "status": "grant",
                "reason": "highest_ranked_request_fits_safe_headroom",
                "expires_epoch": round(float(now_epoch) + float(queue_policy.get("grant_ttl_sec", 5.0)), 6),
                "trial_pressure_band": trial.get("pressure_band"),
            }
            decisions.append(selected)
        else:
            decisions.append({**base, "status": "defer", "reason": "waiting_for_higher_ranked_request_grant"})
    return {
        "schema": "abyss_machine_memory_controller_queue_plan_v1",
        "ok": True,
        "selected": selected,
        "decisions": decisions,
        "active_grant_count": len(active),
        "request_count": len(ordered),
        "policy": {
            "one_grant_at_a_time": True,
            "deadline_does_not_override_safety": True,
            "fresh_high_confidence_required": True,
            "starvation_aging_enabled": True,
        },
    }


def calibrate_envelope(*, current_mib: float, outcome: Mapping[str, Any], policy: Mapping[str, Any] | None = None) -> dict[str, Any]:
    resolved_policy = resolve_policy(policy)
    calibration = _mapping(resolved_policy.get("calibration"))
    current = max(float(calibration.get("minimum_mib", 64.0)), _finite(current_mib) or 0.0)
    observed = _finite(outcome.get("observed_peak_mib"))
    if outcome.get("ok") is not True or observed is None or observed <= 0:
        return {"changed": False, "bounded": False, "previous_mib": round(current, 3), "calibrated_mib": round(current, 3), "reason": "outcome_not_eligible"}
    maximum_step = current * float(calibration.get("maximum_step_ratio", 0.15))
    target = _bounded(observed, current - maximum_step, current + maximum_step)
    target = _bounded(target, float(calibration.get("minimum_mib", 64.0)), float(calibration.get("maximum_mib", 131_072.0)))
    return {
        "changed": not math.isclose(target, current),
        "bounded": not math.isclose(target, observed),
        "previous_mib": round(current, 3),
        "observed_peak_mib": round(observed, 3),
        "calibrated_mib": round(target, 3),
        "reason": "bounded_successful_outcome",
    }


def build_launch_outcome(
    *,
    event_id: str,
    event_epoch: float,
    details: Mapping[str, Any],
    workloads: Iterable[Mapping[str, Any]],
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    workload_id = str(details.get("workload_id") or "unknown")
    requested = max(0.0, _finite(details.get("requested_mib")) or 0.0)
    observed = _finite(details.get("observed_peak_mib"))
    current_envelope = requested
    for raw in workloads:
        if isinstance(raw, Mapping) and str(raw.get("id") or "") == workload_id:
            current_envelope = max(
                0.0,
                _finite(_mapping(raw.get("memory")).get("expected_mib")) or requested,
            )
            break
    calibration = calibrate_envelope(
        current_mib=current_envelope,
        outcome={"ok": details.get("ok") is True, "observed_peak_mib": observed},
        policy=policy,
    )
    error_mib = None if observed is None else round(observed - requested, 3)
    error_ratio = None if observed is None or requested <= 0 else round((observed - requested) / requested, 6)
    if observed is None:
        classification = "peak_unavailable"
    elif requested <= 0:
        classification = "unmodeled_demand"
    elif error_ratio > 0.25:
        classification = "envelope_underestimate"
    elif error_ratio < -0.25:
        classification = "envelope_overestimate"
    else:
        classification = "envelope_within_tolerance"
    return {
        "schema": "abyss_machine_memory_controller_launch_outcome_v1",
        "event_id": str(event_id),
        "epoch": float(event_epoch),
        "workload_id": workload_id,
        "owner": str(details.get("owner") or "unknown"),
        "ok": details.get("ok") is True,
        "requested_mib": round(requested, 3),
        "observed_peak_mib": None if observed is None else round(observed, 3),
        "demand_error_mib": error_mib,
        "demand_error_ratio": error_ratio,
        "queue_delay_sec": round(max(0.0, _finite(details.get("queue_delay_sec")) or 0.0), 3),
        "elapsed_sec": round(max(0.0, _finite(details.get("elapsed_sec")) or 0.0), 3),
        "queue_granted": details.get("queue_granted") is True,
        "classification": classification,
        "calibration_recommendation": calibration,
        "policy": {
            "recommendation_only": True,
            "owner_contract_not_modified": True,
            "safety_invariants_not_modified": True,
            "rollback": "retain_previous_envelope",
        },
    }

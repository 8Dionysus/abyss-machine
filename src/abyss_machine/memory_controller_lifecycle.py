from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import time
from typing import Any

try:
    from . import memory_controller_adapters as adapters
    from . import memory_controller_contracts as contracts
except ImportError:  # Supports bootstrap-installed direct module copies.
    from abyss_machine import memory_controller_adapters as adapters
    from abyss_machine import memory_controller_contracts as contracts


EpochPort = Callable[[], float]
MonotonicPort = Callable[[], float]
SleepPort = Callable[[float], None]
SamplePort = Callable[[], dict[str, Any]]
RoutePort = Callable[[Mapping[str, Any]], dict[str, Any]]
MeasurementPort = Callable[[Mapping[str, Any]], dict[str, Any]]


class ActionLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.fd: int | None = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            return False
        self.fd = fd
        return True

    def close(self) -> None:
        if self.fd is None:
            return
        try:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
        finally:
            os.close(self.fd)
            self.fd = None


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


def _canonical_digest(document: Mapping[str, Any]) -> str:
    payload = json.dumps(dict(document), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sample_metrics(sample: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: sample.get(key)
        for key in (
            "epoch",
            "mem_available_mib",
            "swap_used_mib",
            "swap_free_mib",
            "zram_data_mib",
            "zram_resident_mib",
            "psi_some_avg10",
            "psi_full_avg10",
            "psi_some_total_usec",
            "psi_full_total_usec",
            "pgmajfault",
            "oom_kill",
        )
    }


def _unlink_owned_regular(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return True
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
        return False
    path.unlink()
    return True


def _outcome_pending_resolved(outcome: Mapping[str, Any]) -> bool:
    if "pending_resolved" in outcome:
        return outcome.get("pending_resolved") is True
    return str(outcome.get("status") or "") in {
        "action_completed_verified",
        "action_failed_rolled_back",
        "recovered_health_verified",
        "recovery_rollback_verified",
    }


def probe_route(name: str, route: Mapping[str, Any], *, route_port: RoutePort) -> dict[str, Any]:
    checked = contracts.validate_lifecycle_route(name, route)
    if not checked["valid"]:
        return {
            "ok": False,
            "status": "route_contract_invalid",
            "route_name": name,
            "issues": checked["issues"],
        }
    normalized = checked["route"]
    transport = route_port(normalized)
    if transport.get("ok") is not True:
        return {
            "ok": False,
            "status": "route_transport_failed",
            "route_name": name,
            "transport": transport,
        }
    expectation = contracts.evaluate_route_response(normalized, transport.get("document"))
    return {
        "ok": expectation["ok"],
        "status": "route_verified" if expectation["ok"] else "route_expectation_failed",
        "route_name": name,
        "transport": transport,
        "expectation": expectation,
    }


def build_action_plan(
    selected: Mapping[str, Any],
    *,
    event_id: str,
    sequence: int,
    now_epoch: float,
    ttl_sec: float = 5.0,
) -> dict[str, Any]:
    lifecycle_plan = _mapping(selected.get("lifecycle_plan"))
    action = str(selected.get("action") or "")
    workload_id = str(selected.get("workload_id") or "")
    owner = str(selected.get("owner") or "")
    nonce = hashlib.sha256(f"{workload_id}\0{owner}\0{action}\0{sequence}\0{event_id}".encode("utf-8")).hexdigest()
    routes = {
        key: deepcopy(value)
        for key, value in lifecycle_plan.items()
        if key.endswith("_route") and isinstance(value, Mapping)
    }
    measurement = deepcopy(_mapping(lifecycle_plan.get("measurement")))
    return {
        "schema": "abyss_machine_memory_controller_action_plan_v1",
        "status": "prepared",
        "nonce": nonce,
        "event_id": str(event_id),
        "controller_sequence": int(sequence),
        "issued_epoch": float(now_epoch),
        "expires_epoch": float(now_epoch) + max(1.0, min(30.0, float(ttl_sec))),
        "workload_id": workload_id,
        "owner": owner,
        "importance": str(selected.get("importance") or "unknown"),
        "protected": bool(selected.get("protected", True)),
        "action": action,
        "action_route_name": str(lifecycle_plan.get("action_route_name") or ""),
        "predicted_freed_mib": max(0.0, float(selected.get("expected_freed_mib") or 0.0)),
        "enrollment": deepcopy(_mapping(selected.get("enrollment"))),
        "routes": routes,
        "routes_sha256": _canonical_digest(routes),
        "measurement": measurement,
        "contract_sha256": _canonical_digest({"routes": routes, "measurement": measurement}),
        "policy": {
            "typed_local_http_only": True,
            "one_relief_action_at_a_time": True,
            "never_repeat_action_during_recovery": True,
            "rollback_on_failed_post_health": True,
        },
    }


def validate_action_plan(plan: Mapping[str, Any], *, now_epoch: float, allow_expired_recovery: bool = False) -> dict[str, Any]:
    issues: list[str] = []
    if plan.get("schema") != "abyss_machine_memory_controller_action_plan_v1":
        issues.append("plan_schema_invalid")
    action = str(plan.get("action") or "")
    if action not in contracts.LIFECYCLE_ACTION_ROUTE:
        issues.append("plan_action_invalid")
    if bool(plan.get("protected", True)) or str(plan.get("importance") or "unknown") in {"protected", "unknown"}:
        issues.append("plan_workload_not_mutable")
    enrollment = _mapping(plan.get("enrollment"))
    if enrollment.get("authorized") is not True:
        issues.append("plan_owner_enrollment_not_authorized")
    for field in ("nonce", "event_id", "workload_id", "owner", "action_route_name", "routes_sha256", "contract_sha256"):
        if not str(plan.get(field) or ""):
            issues.append(f"plan_{field}_required")
    expires = _finite(plan.get("expires_epoch"))
    if expires is None:
        issues.append("plan_expiry_invalid")
    elif not allow_expired_recovery and expires <= float(now_epoch):
        issues.append("plan_expired")
    routes = _mapping(plan.get("routes"))
    if _canonical_digest(routes) != str(plan.get("routes_sha256") or ""):
        issues.append("plan_route_digest_mismatch")
    measurement = _mapping(plan.get("measurement"))
    checked_measurement = contracts.validate_measurement_contract(measurement)
    if not checked_measurement["valid"]:
        issues.extend(f"plan_{item}" for item in checked_measurement["issues"])
    if _canonical_digest({"routes": routes, "measurement": measurement}) != str(plan.get("contract_sha256") or ""):
        issues.append("plan_contract_digest_mismatch")
    action_route_name = str(plan.get("action_route_name") or "")
    required = {
        "action_route": action_route_name,
        "activity_route": "activity",
        "health_route": "health",
        "rollback_route": "rollback",
    }
    if action == "managed_dehydrate":
        required["rehydrate_route"] = "rehydrate"
    for key, route_name in required.items():
        route = routes.get(key)
        if not isinstance(route, Mapping):
            issues.append(f"plan_{key}_required")
            continue
        checked = contracts.validate_lifecycle_route(route_name, route)
        if not checked["valid"]:
            issues.extend(f"plan_{key}_invalid:{item}" for item in checked["issues"])
    return {"valid": not issues, "issues": sorted(set(issues))}


def _post_health(
    route: Mapping[str, Any],
    *,
    route_port: RoutePort,
    attempts: int,
    interval_sec: float,
    sleep_port: SleepPort,
) -> dict[str, Any]:
    observed: list[dict[str, Any]] = []
    for attempt in range(max(1, int(attempts))):
        result = probe_route("health", route, route_port=route_port)
        observed.append(result)
        if result.get("ok") is True:
            return {"ok": True, "status": "post_health_verified", "attempts": observed}
        if attempt + 1 < attempts:
            sleep_port(max(0.0, interval_sec))
    return {"ok": False, "status": "post_health_failed", "attempts": observed}


def execute_action_plan(
    plan: Mapping[str, Any],
    *,
    pending_path: Path,
    lock_path: Path,
    store: adapters.EvidenceStore,
    route_port: RoutePort = adapters.local_http_json,
    measurement_port: MeasurementPort = adapters.safe_user_cgroup_snapshot,
    sample_port: SamplePort,
    history_limit: int,
    retention_hours: float,
    epoch_port: EpochPort = time.time,
    monotonic_port: MonotonicPort = time.monotonic,
    sleep_port: SleepPort = time.sleep,
) -> dict[str, Any]:
    now_epoch = float(epoch_port())
    checked = validate_action_plan(plan, now_epoch=now_epoch)
    if not checked["valid"]:
        return {"ok": False, "status": "action_plan_rejected", "issues": checked["issues"]}
    nonce = str(plan["nonce"])
    if store.has_action_nonce(nonce):
        return {"ok": True, "status": "duplicate_action_suppressed", "nonce": nonce}
    lock = ActionLock(lock_path)
    if not lock.acquire():
        return {"ok": False, "status": "another_relief_action_active", "nonce": nonce}
    routes = _mapping(plan.get("routes"))
    try:
        if pending_path.exists():
            return {"ok": False, "status": "unrecovered_action_present", "nonce": nonce}
        activity = probe_route("activity", _mapping(routes.get("activity_route")), route_port=route_port)
        health_before = probe_route("health", _mapping(routes.get("health_route")), route_port=route_port)
        if activity.get("ok") is not True or health_before.get("ok") is not True:
            return {
                "ok": False,
                "status": "live_preflight_failed",
                "nonce": nonce,
                "activity": activity,
                "health_before": health_before,
            }
        if float(epoch_port()) >= float(plan["expires_epoch"]):
            return {"ok": False, "status": "live_preflight_expired", "nonce": nonce}
        measurement = _mapping(plan.get("measurement"))
        measurement_before = measurement_port(measurement)
        before = sample_port()
        pending = {**deepcopy(dict(plan)), "status": "executing", "execution_started_epoch": float(epoch_port())}
        adapters.atomic_write_json(pending_path, pending)
        started = float(monotonic_port())
        action_route_name = str(plan["action_route_name"])
        action_result = probe_route(action_route_name, _mapping(routes.get("action_route")), route_port=route_port)
        health_after = _post_health(
            _mapping(routes.get("health_route")),
            route_port=route_port,
            attempts=3,
            interval_sec=0.1,
            sleep_port=sleep_port,
        )
        rollback: dict[str, Any] = {"ok": True, "status": "not_needed"}
        if action_result.get("ok") is not True or health_after.get("ok") is not True:
            rollback_action = probe_route("rollback", _mapping(routes.get("rollback_route")), route_port=route_port)
            rollback_health = _post_health(
                _mapping(routes.get("health_route")),
                route_port=route_port,
                attempts=3,
                interval_sec=0.1,
                sleep_port=sleep_port,
            )
            rollback = {
                "ok": rollback_action.get("ok") is True and rollback_health.get("ok") is True,
                "status": "rollback_verified" if rollback_action.get("ok") is True and rollback_health.get("ok") is True else "rollback_failed",
                "action": rollback_action,
                "health": rollback_health,
            }
        after = sample_port()
        measurement_after = measurement_port(measurement)
        before_available = _finite(before.get("mem_available_mib")) or 0.0
        after_available = _finite(after.get("mem_available_mib")) or 0.0
        global_available_delta = max(0.0, after_available - before_available)
        measurement_ready = measurement_before.get("ok") is True and measurement_after.get("ok") is True
        measured_before_mib = _finite(measurement_before.get("memory_mib")) or 0.0
        measured_after_mib = _finite(measurement_after.get("memory_mib")) or 0.0
        observed_freed = max(0.0, measured_before_mib - measured_after_mib) if measurement_ready else 0.0
        action_ok = action_result.get("ok") is True and health_after.get("ok") is True
        completed_epoch = float(epoch_port())
        outcome = {
            "schema": "abyss_machine_memory_controller_action_outcome_v1",
            "ok": action_ok,
            "status": "action_completed_verified" if action_ok else ("action_failed_rolled_back" if rollback.get("ok") else "action_failed_rollback_failed"),
            "nonce": nonce,
            "epoch": completed_epoch,
            "workload_id": plan["workload_id"],
            "owner": plan["owner"],
            "action": plan["action"],
            "predicted_freed_mib": round(float(plan.get("predicted_freed_mib") or 0.0), 3),
            "observed_freed_mib": round(observed_freed, 3),
            "benefit_verified": bool(measurement_ready and observed_freed > 0.0),
            "global_mem_available_delta_mib": round(global_available_delta, 3),
            "duration_ms": round(max(0.0, float(monotonic_port()) - started) * 1_000.0, 3),
            "activity_preflight": activity,
            "health_before": health_before,
            "action_result": action_result,
            "health_after": health_after,
            "rollback": rollback,
            "before": _sample_metrics(before),
            "after": _sample_metrics(after),
            "measurement_before": measurement_before,
            "measurement_after": measurement_after,
            "classification": "true_positive" if action_ok and measurement_ready and observed_freed > 0 else ("no_measured_relief" if action_ok and measurement_ready else ("benefit_unverified" if action_ok else "action_failure")),
            "policy": {
                "safety_and_owner_contracts_not_self_modified": True,
                "global_mem_available_delta_is_noisy": True,
            },
        }
        pending_resolved = action_ok or rollback.get("ok") is True
        outcome["pending_resolved"] = pending_resolved
        outcome["pending_removed"] = False
        outcome["pending_status"] = "verified_resolution_pending_cleanup" if pending_resolved else "owner_recovery_required"
        if not pending_resolved:
            adapters.atomic_write_json(
                pending_path,
                {
                    **pending,
                    "status": "owner_recovery_required",
                    "last_outcome_status": outcome["status"],
                    "last_rollback_status": rollback.get("status"),
                    "last_attempt_epoch": completed_epoch,
                },
            )
        store.append_action_outcome(outcome, limit=history_limit, retention_hours=retention_hours)
        if pending_resolved:
            outcome["pending_removed"] = _unlink_owned_regular(pending_path)
            outcome["pending_status"] = "cleared" if outcome["pending_removed"] else "verified_but_pending_path_not_owned"
            store.append_action_outcome(outcome, limit=history_limit, retention_hours=retention_hours)
        return outcome
    finally:
        lock.close()


def recover_pending_action(
    *,
    pending_path: Path,
    store: adapters.EvidenceStore,
    registry: Mapping[str, Any],
    route_port: RoutePort = adapters.local_http_json,
    history_limit: int,
    retention_hours: float,
    epoch_port: EpochPort = time.time,
    sleep_port: SleepPort = time.sleep,
) -> dict[str, Any]:
    pending, error = adapters.load_json(pending_path)
    if error:
        if not pending_path.exists():
            return {"ok": True, "status": "no_pending_action"}
        return {"ok": False, "status": "pending_action_unreadable", "error": error}
    plan = _mapping(pending)
    nonce = str(plan.get("nonce") or "")
    prior_outcome = store.action_outcome(nonce) if nonce else None
    if prior_outcome is not None and _outcome_pending_resolved(prior_outcome):
        removed = _unlink_owned_regular(pending_path)
        return {"ok": removed, "status": "completed_pending_action_cleaned" if removed else "completed_pending_action_not_owned"}
    checked = validate_action_plan(plan, now_epoch=float(epoch_port()), allow_expired_recovery=True)
    if not checked["valid"]:
        return {"ok": False, "status": "pending_action_invalid_owner_review", "issues": checked["issues"]}
    workload_id = str(plan.get("workload_id") or "")
    action = str(plan.get("action") or "")
    candidates = [item for item in registry.get("workloads", []) if isinstance(item, Mapping) and str(item.get("id") or "") == workload_id]
    if len(candidates) != 1:
        return {"ok": False, "status": "pending_action_identity_not_current", "workload_id": workload_id}
    resolved = contracts.resolve_workload({"workloads": candidates, "rules": []}, {"id": workload_id})
    enrollment = contracts.lifecycle_action_enrolled(resolved, action, now_epoch=float(epoch_port()))
    lifecycle = _mapping(resolved.get("lifecycle"))
    route_names = contracts.LIFECYCLE_ACTION_ROUTE.get(action, ())
    action_route_name = next((name for name in route_names if lifecycle.get(name)), "")
    current_routes = {
        "action_route": lifecycle.get(action_route_name),
        "activity_route": lifecycle.get("activity"),
        "health_route": lifecycle.get("health"),
        "rollback_route": lifecycle.get("rollback"),
    }
    if lifecycle.get("rehydrate"):
        current_routes["rehydrate_route"] = lifecycle.get("rehydrate")
    current_measurement = _mapping(resolved.get("measurement"))
    current_contract_digest = _canonical_digest({"routes": current_routes, "measurement": current_measurement})
    if enrollment.get("authorized") is not True or current_contract_digest != str(plan.get("contract_sha256") or ""):
        return {
            "ok": False,
            "status": "pending_action_owner_reenrollment_required",
            "workload_id": workload_id,
            "enrollment": enrollment,
        }
    health = _post_health(
        _mapping(current_routes.get("health_route")),
        route_port=route_port,
        attempts=2,
        interval_sec=0.1,
        sleep_port=sleep_port,
    )
    rollback: dict[str, Any] = {"ok": True, "status": "not_needed_recovered_healthy"}
    if health.get("ok") is not True:
        rollback_action = probe_route("rollback", _mapping(current_routes.get("rollback_route")), route_port=route_port)
        rollback_health = _post_health(
            _mapping(current_routes.get("health_route")),
            route_port=route_port,
            attempts=3,
            interval_sec=0.1,
            sleep_port=sleep_port,
        )
        rollback = {
            "ok": rollback_action.get("ok") is True and rollback_health.get("ok") is True,
            "status": "recovery_rollback_verified" if rollback_action.get("ok") is True and rollback_health.get("ok") is True else "recovery_rollback_failed",
            "action": rollback_action,
            "health": rollback_health,
        }
    pending_resolved = health.get("ok") is True or rollback.get("ok") is True
    outcome = {
        "schema": "abyss_machine_memory_controller_action_outcome_v1",
        "ok": pending_resolved,
        "status": "recovered_health_verified" if health.get("ok") is True else rollback["status"],
        "nonce": nonce,
        "epoch": float(epoch_port()),
        "workload_id": workload_id,
        "owner": plan.get("owner"),
        "action": action,
        "predicted_freed_mib": float((prior_outcome or {}).get("predicted_freed_mib") or plan.get("predicted_freed_mib") or 0.0),
        "observed_freed_mib": float((prior_outcome or {}).get("observed_freed_mib") or 0.0),
        "rollback": rollback,
        "recovery": {"action_was_not_repeated": True, "health": health},
        "prior_outcome_status": (prior_outcome or {}).get("status"),
        "pending_resolved": pending_resolved,
        "pending_removed": False,
        "pending_status": "verified_resolution_pending_cleanup" if pending_resolved else "owner_recovery_required",
    }
    if not pending_resolved:
        adapters.atomic_write_json(
            pending_path,
            {
                **dict(plan),
                "status": "owner_recovery_required",
                "last_outcome_status": outcome["status"],
                "last_rollback_status": rollback.get("status"),
                "last_attempt_epoch": outcome["epoch"],
            },
        )
    store.append_action_outcome(outcome, limit=history_limit, retention_hours=retention_hours)
    if pending_resolved:
        outcome["pending_removed"] = _unlink_owned_regular(pending_path)
        outcome["pending_status"] = "cleared" if outcome["pending_removed"] else "verified_but_pending_path_not_owned"
        store.append_action_outcome(outcome, limit=history_limit, retention_hours=retention_hours)
    return outcome

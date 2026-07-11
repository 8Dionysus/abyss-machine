from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
import fcntl
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import re
import resource
import select
import signal
import stat
import time
from typing import Any

try:
    from . import memory_controller_adapters as adapters
    from . import memory_controller_contracts as contracts
    from . import memory_controller_lifecycle as lifecycle
    from . import resource_adapters
except ImportError:  # Supports bootstrap-installed direct module copies.
    from abyss_machine import memory_controller_adapters as adapters
    from abyss_machine import memory_controller_contracts as contracts
    from abyss_machine import memory_controller_lifecycle as lifecycle
    from abyss_machine import resource_adapters


EpochPort = Callable[[], float]
MonotonicPort = Callable[[], float]
SamplePort = Callable[..., dict[str, Any]]
ReservationsPort = Callable[[], dict[str, Any]]


@dataclass(frozen=True)
class ControllerPaths:
    policy: Path
    registry: Path
    runtime_root: Path
    evidence_root: Path

    @property
    def runtime_registry(self) -> Path:
        return self.runtime_root / "registry"

    @property
    def queue(self) -> Path:
        return self.runtime_root / "queue"

    @property
    def grants(self) -> Path:
        return self.runtime_root / "grants"

    @property
    def admission(self) -> Path:
        return self.runtime_root / "admission.json"

    @property
    def socket(self) -> Path:
        return self.runtime_root / "events.sock"

    @property
    def latest(self) -> Path:
        return self.evidence_root / "latest.json"

    @property
    def state(self) -> Path:
        return self.evidence_root / "state.json"

    @property
    def window(self) -> Path:
        return self.evidence_root / "window.json"

    @property
    def database(self) -> Path:
        return self.evidence_root / "evidence.sqlite3"

    @property
    def pending_action(self) -> Path:
        return self.runtime_root / "pending-action.json"

    @property
    def action_lock(self) -> Path:
        return self.runtime_root / "lifecycle-action.lock"


def default_paths(environ: Mapping[str, str] | None = None) -> ControllerPaths:
    env = os.environ if environ is None else environ
    runtime_base = Path(env.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")
    return ControllerPaths(
        policy=Path(env.get("ABYSS_MEMORY_CONTROLLER_POLICY") or "/etc/abyss-machine/memory-controller-policy.json"),
        registry=Path(env.get("ABYSS_MEMORY_CONTROLLER_REGISTRY") or "/etc/abyss-machine/memory-controller-registry.json"),
        runtime_root=Path(env.get("ABYSS_MEMORY_CONTROLLER_RUNTIME") or runtime_base / "abyss-machine" / "memory-controller"),
        evidence_root=Path(env.get("ABYSS_MEMORY_CONTROLLER_EVIDENCE") or "/srv/abyss-machine/tmp/memory-steward/controller"),
    )


@dataclass(frozen=True)
class ControllerEvent:
    source: str
    kind: str
    event_id: str
    epoch: float
    monotonic: float
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "kind": self.kind,
            "event_id": self.event_id,
            "epoch": self.epoch,
            "monotonic": self.monotonic,
            "details": dict(self.details),
        }


class EventCoalescer:
    def __init__(self, *, debounce_ms: int, max_coalesce_ms: int, maximum_events: int = 256) -> None:
        self.debounce_sec = max(0.0, int(debounce_ms) / 1_000.0)
        self.max_coalesce_sec = max(self.debounce_sec, int(max_coalesce_ms) / 1_000.0)
        self.maximum_events = max(1, int(maximum_events))
        self._events: list[ControllerEvent] = []
        self._dropped = 0
        self._last_monotonic: float | None = None

    @staticmethod
    def _priority(event: ControllerEvent) -> int:
        if event.source == "socket" or event.kind in {
            "resource_launch_outcome",
            "lifecycle_contract_registered",
            "lifecycle_contract_unregistered",
        }:
            return 2
        if event.source in {
            "cgroup_memory_events",
            "configuration",
            "psi",
            "queue",
            "registry",
            "reservations",
            "systemd",
        }:
            return 1
        return 0

    @staticmethod
    def _bounded_count(value: Any) -> int:
        try:
            resolved = int(value)
        except (TypeError, ValueError, OverflowError):
            return 1
        return max(1, min(1_000_000, resolved))

    def add(self, event: ControllerEvent) -> None:
        self._last_monotonic = event.monotonic
        if event.source in {
            "cgroup_memory_events",
            "configuration",
            "queue",
            "registry",
            "reservations",
        }:
            for index, existing in enumerate(self._events):
                if existing.source == event.source and existing.kind == event.kind:
                    repeat_count = min(
                        1_000_000,
                        self._bounded_count(existing.details.get("coalesced_repeat_count")) + 1,
                    )
                    existing_raw_count = self._bounded_count(
                        existing.details.get("raw_change_count")
                        or existing.details.get("change_count")
                        or 1
                    )
                    incoming_raw_count = self._bounded_count(event.details.get("change_count"))
                    self._events[index] = ControllerEvent(
                        existing.source,
                        existing.kind,
                        existing.event_id,
                        existing.epoch,
                        existing.monotonic,
                        {
                            **existing.details,
                            "coalesced_repeat_count": repeat_count,
                            "raw_change_count": existing_raw_count + incoming_raw_count,
                            "latest_event_id": event.event_id,
                            "latest_epoch": event.epoch,
                        },
                    )
                    return
        if len(self._events) >= self.maximum_events:
            incoming_priority = self._priority(event)
            minimum_priority = min(self._priority(existing) for existing in self._events)
            if minimum_priority > incoming_priority:
                self._dropped += 1
                return
            drop_index = next(
                index for index, existing in enumerate(self._events) if self._priority(existing) == minimum_priority
            )
            self._events.pop(drop_index)
            self._dropped += 1
        self._events.append(event)

    def ready(self, now_monotonic: float) -> bool:
        if not self._events:
            return False
        first = self._events[0].monotonic
        last = self._last_monotonic if self._last_monotonic is not None else self._events[-1].monotonic
        return now_monotonic - last >= self.debounce_sec or now_monotonic - first >= self.max_coalesce_sec

    def remaining_ms(self, now_monotonic: float) -> int | None:
        if not self._events:
            return None
        last = self._last_monotonic if self._last_monotonic is not None else self._events[-1].monotonic
        debounce_due = last + self.debounce_sec
        cap_due = self._events[0].monotonic + self.max_coalesce_sec
        return max(0, math.ceil((min(debounce_due, cap_due) - now_monotonic) * 1_000.0))

    def pop(self, now_monotonic: float) -> ControllerEvent:
        if not self._events:
            raise RuntimeError("cannot pop an empty event coalescer")
        events, self._events = self._events, []
        self._last_monotonic = None
        dropped, self._dropped = self._dropped, 0
        if len(events) == 1 and dropped == 0:
            return events[0]
        identifiers = list(dict.fromkeys(item.event_id for item in events))
        digest = hashlib.sha256("\0".join(identifiers).encode("utf-8")).hexdigest()[:20]
        first = min(events, key=lambda item: item.monotonic)
        return ControllerEvent(
            source="coalescer",
            kind="coalesced",
            event_id=f"coalesced:{digest}",
            epoch=first.epoch,
            monotonic=first.monotonic,
            details={
                "event_ids": identifiers,
                "sources": list(dict.fromkeys(item.source for item in events)),
                "kinds": list(dict.fromkeys(item.kind for item in events)),
                "event_count": len(events),
                "raw_event_count": sum(
                    self._bounded_count(item.details.get("raw_change_count") or item.details.get("change_count"))
                    for item in events
                ),
                "dropped_event_count": dropped,
                "coalesced_at_monotonic": now_monotonic,
                "events": [
                    {
                        "source": item.source,
                        "kind": item.kind,
                        "event_id": item.event_id,
                        "epoch": item.epoch,
                        "details": (
                            dict(item.details)
                            if item.kind == "resource_launch_outcome"
                            else {
                                key: item.details[key]
                                for key in ("change_count", "coalesced_repeat_count", "raw_change_count")
                                if key in item.details
                            }
                        ),
                    }
                    for item in events
                ],
            },
        )


def _load_policy(path: Path) -> tuple[dict[str, Any], list[str]]:
    document, error = adapters.load_json(path)
    if error:
        return contracts.default_policy(), [f"policy_load_error:{error}"]
    checked = contracts.validate_policy(document)
    if not checked["valid"]:
        return contracts.default_policy(), list(checked["issues"])
    return checked["policy"], []


def queue_snapshot(
    root: Path,
    *,
    now_epoch: float | None = None,
    cleanup: bool = False,
    maximum_wait_sec: float = 120.0,
    pid_alive_port: resource_adapters.PidAlivePort = resource_adapters.pid_alive,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    removed: list[str] = []
    expired: list[str] = []
    orphaned: list[str] = []
    now = float(time.time() if now_epoch is None else now_epoch)
    maximum_wait = max(1.0, min(3_600.0, float(maximum_wait_sec)))
    if root.is_dir():
        for path in sorted(root.glob("*.json")):
            document, error = adapters.load_json(path)
            if error:
                errors.append({"path": str(path), "error": error})
                continue
            request_id = str(document.get("id") or "")
            owner = str(document.get("owner") or "")
            posture = str(document.get("posture") or "")
            try:
                demand_value = float(document.get("demand_mib"))
                created_value = float(document.get("created_epoch"))
                priority_value = int(document.get("priority"))
                deadline_value = float(document.get("deadline_epoch"))
                launcher_pid = int(document.get("launcher_pid"))
            except (TypeError, ValueError):
                errors.append({"path": str(path), "error": "queue_numeric_contract_invalid"})
                continue
            reason = ""
            if document.get("schema") != "abyss_machine_memory_controller_queue_request_v1":
                reason = "queue_schema_invalid"
            elif not request_id:
                reason = "queue_request_id_missing"
            elif not owner:
                reason = "queue_owner_missing"
            elif posture != "background":
                reason = "queue_posture_not_background"
            elif not math.isfinite(demand_value) or demand_value < 0:
                reason = "demand_mib_invalid"
            elif not math.isfinite(created_value) or created_value < 0:
                reason = "created_epoch_invalid"
            elif not math.isfinite(deadline_value) or deadline_value <= 0:
                reason = "deadline_epoch_invalid"
            elif deadline_value < created_value or deadline_value - created_value > maximum_wait:
                reason = "queue_deadline_outside_policy"
            elif launcher_pid <= 0:
                reason = "queue_launcher_pid_invalid"
            if reason:
                errors.append({"path": str(path), "error": reason})
                continue
            if deadline_value <= now:
                expired.append(str(path))
                if cleanup:
                    try:
                        path.unlink()
                        removed.append(str(path))
                    except OSError as exc:
                        errors.append({"path": str(path), "error": f"expired_request_cleanup_failed:{exc}"})
                continue
            if not pid_alive_port(launcher_pid):
                orphaned.append(str(path))
                if cleanup:
                    try:
                        path.unlink()
                        removed.append(str(path))
                    except OSError as exc:
                        errors.append({"path": str(path), "error": f"orphaned_request_cleanup_failed:{exc}"})
                continue
            items.append({
                **document,
                "id": request_id,
                "owner": owner,
                "posture": posture,
                "demand_mib": round(demand_value, 3),
                "created_epoch": created_value,
                "priority": priority_value,
                "deadline_epoch": deadline_value,
                "launcher_pid": launcher_pid,
                "path": str(path),
            })
    return {
        "schema": "abyss_machine_memory_controller_queue_snapshot_v1",
        "ok": not errors,
        "items": items,
        "errors": errors,
        "expired": expired,
        "orphaned": orphaned,
        "removed": removed,
        "summary": {
            "count": len(items),
            "demand_mib": round(sum(float(item["demand_mib"]) for item in items), 3),
            "error_count": len(errors),
            "expired_count": len(expired),
            "orphaned_count": len(orphaned),
            "removed_count": len(removed),
        },
    }


def safe_reservations_snapshot(port: ReservationsPort) -> dict[str, Any]:
    try:
        raw = port()
    except Exception as exc:
        return {"ok": False, "summary": {}, "errors": [{"error": f"reservation_port_failed:{exc}"}]}
    if not isinstance(raw, Mapping):
        return {"ok": False, "summary": {}, "errors": [{"error": "reservation_document_not_object"}]}
    summary = raw.get("summary") if isinstance(raw.get("summary"), Mapping) else {}
    try:
        outstanding_mib = float(summary.get("outstanding_mib"))
    except (TypeError, ValueError):
        outstanding_mib = math.nan
    errors = list(raw.get("errors")) if isinstance(raw.get("errors"), list) else []
    if not math.isfinite(outstanding_mib) or outstanding_mib < 0:
        errors.append({"error": "reservation_outstanding_mib_invalid"})
        outstanding_mib = 0.0
    return {
        **dict(raw),
        "ok": raw.get("ok") is True and not errors,
        "summary": {**dict(summary), "outstanding_mib": round(outstanding_mib, 3)},
        "errors": errors,
    }


def grant_snapshot(root: Path, *, now_epoch: float, cleanup: bool, maximum_ttl_sec: float = 5.0) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    removed: list[str] = []
    maximum_ttl = max(1.0, min(60.0, float(maximum_ttl_sec)))
    if root.is_dir():
        for path in sorted(root.glob("*.json")):
            document, error = adapters.load_json(path)
            if error:
                errors.append({"path": str(path), "error": error})
                continue
            request_id = str(document.get("request_id") or "")
            owner = str(document.get("owner") or "")
            nonce = str(document.get("nonce") or "")
            try:
                issued = float(document.get("issued_epoch"))
                expires = float(document.get("expires_epoch"))
                controller_sequence = int(document.get("controller_sequence"))
            except (TypeError, ValueError):
                errors.append({"path": str(path), "error": "grant_numeric_contract_invalid"})
                continue
            reason = ""
            if document.get("schema") != "abyss_machine_memory_controller_queue_grant_v1":
                reason = "grant_schema_invalid"
            elif not request_id or not owner:
                reason = "grant_identity_invalid"
            elif len(nonce) != 64 or any(character not in "0123456789abcdef" for character in nonce):
                reason = "grant_nonce_invalid"
            elif not math.isfinite(issued) or not math.isfinite(expires) or issued <= 0 or expires <= issued:
                reason = "grant_epoch_invalid"
            elif expires - issued > maximum_ttl + 0.001:
                reason = "grant_ttl_outside_policy"
            elif controller_sequence <= 0:
                reason = "grant_controller_sequence_invalid"
            if reason:
                errors.append({"path": str(path), "error": reason})
                continue
            if expires <= float(now_epoch):
                if cleanup:
                    try:
                        path.unlink()
                        removed.append(str(path))
                    except OSError as exc:
                        errors.append({"path": str(path), "error": str(exc)})
                continue
            items.append({
                **document,
                "request_id": request_id,
                "owner": owner,
                "issued_epoch": issued,
                "expires_epoch": expires,
                "controller_sequence": controller_sequence,
                "nonce": nonce,
                "path": str(path),
            })
    return {
        "schema": "abyss_machine_memory_controller_grant_snapshot_v1",
        "ok": not errors,
        "items": items,
        "errors": errors,
        "removed": removed,
        "summary": {"active_count": len(items), "removed_count": len(removed), "error_count": len(errors)},
    }


def runtime_contract_path(root: Path, workload_id: str) -> Path:
    normalized = str(workload_id).strip()
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", normalized).strip("-.")[:48] or "workload"
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return root / f"{slug}-{digest}.json"


def _notify_if_running(paths: ControllerPaths, *, kind: str, event_id: str, details: Mapping[str, Any]) -> dict[str, Any]:
    if not paths.socket.exists():
        return {"sent": False, "status": "controller_not_running"}
    try:
        adapters.send_event_socket(
            paths.socket,
            {
                "schema": "abyss_machine_memory_controller_event_v1",
                "kind": kind,
                "event_id": event_id,
                "details": dict(details),
            },
        )
    except OSError as exc:
        return {"sent": False, "status": "notify_failed", "error": str(exc)}
    return {"sent": True, "status": "event_sent"}


def register_runtime_contract(
    paths: ControllerPaths,
    raw: Mapping[str, Any],
    *,
    epoch_port: EpochPort = time.time,
) -> dict[str, Any]:
    checked = contracts.validate_workload_contract(raw)
    if not checked["valid"]:
        return {
            "schema": "abyss_machine_memory_controller_registration_v1",
            "ok": False,
            "status": "contract_invalid",
            "issues": checked["issues"],
        }
    contract = checked["contract"]
    workload_id = str(contract["id"])
    static, _error = adapters.load_json(paths.registry)
    static_workloads = static.get("workloads", []) if isinstance(static, Mapping) and isinstance(static.get("workloads"), list) else []
    if any(isinstance(item, Mapping) and str(item.get("id") or "") == workload_id for item in static_workloads):
        return {
            "schema": "abyss_machine_memory_controller_registration_v1",
            "ok": False,
            "status": "static_identity_owned",
            "workload_id": workload_id,
        }
    paths.runtime_registry.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = runtime_contract_path(paths.runtime_registry, workload_id)
    existing, existing_error = adapters.load_json(path)
    if existing_error is None and existing is not None and str(existing.get("owner") or "") != str(contract["owner"]):
        return {
            "schema": "abyss_machine_memory_controller_registration_v1",
            "ok": False,
            "status": "runtime_identity_owner_conflict",
            "workload_id": workload_id,
            "existing_owner": existing.get("owner"),
            "requested_owner": contract["owner"],
        }
    epoch = float(epoch_port())
    metadata = contract.get("metadata") if isinstance(contract.get("metadata"), Mapping) else {}
    document = {
        **contract,
        "metadata": {
            **metadata,
            "registered_epoch": epoch,
            "registrant_uid": os.getuid(),
            "registrant_pid": os.getpid(),
            "runtime_only": True,
        },
    }
    adapters.atomic_write_json(path, document)
    notification = _notify_if_running(
        paths,
        kind="lifecycle_contract_registered",
        event_id=f"register:{workload_id}:{epoch:.9f}",
        details={"workload_id": workload_id, "owner": contract["owner"], "path": str(path)},
    )
    return {
        "schema": "abyss_machine_memory_controller_registration_v1",
        "ok": True,
        "status": "runtime_contract_registered",
        "workload_id": workload_id,
        "owner": contract["owner"],
        "path": str(path),
        "allowed_actions": contracts.resolve_workload({"workloads": [document], "rules": []}, {"id": workload_id})["allowed_actions"],
        "notification": notification,
    }


def unregister_runtime_contract(paths: ControllerPaths, workload_id: str, *, epoch_port: EpochPort = time.time) -> dict[str, Any]:
    normalized = str(workload_id).strip()
    if not normalized:
        return {"schema": "abyss_machine_memory_controller_registration_v1", "ok": False, "status": "workload_id_required"}
    path = runtime_contract_path(paths.runtime_registry, normalized)
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return {
            "schema": "abyss_machine_memory_controller_registration_v1",
            "ok": True,
            "status": "runtime_contract_already_absent",
            "workload_id": normalized,
            "path": str(path),
        }
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
        return {
            "schema": "abyss_machine_memory_controller_registration_v1",
            "ok": False,
            "status": "runtime_contract_path_not_owned_regular_file",
            "workload_id": normalized,
            "path": str(path),
        }
    existing, error = adapters.load_json(path)
    if error or str((existing or {}).get("id") or "") != normalized:
        return {
            "schema": "abyss_machine_memory_controller_registration_v1",
            "ok": False,
            "status": "runtime_contract_identity_mismatch",
            "workload_id": normalized,
            "path": str(path),
        }
    path.unlink()
    epoch = float(epoch_port())
    notification = _notify_if_running(
        paths,
        kind="lifecycle_contract_unregistered",
        event_id=f"unregister:{normalized}:{epoch:.9f}",
        details={"workload_id": normalized, "path": str(path)},
    )
    return {
        "schema": "abyss_machine_memory_controller_registration_v1",
        "ok": True,
        "status": "runtime_contract_removed",
        "workload_id": normalized,
        "path": str(path),
        "notification": notification,
    }


def registry_contract_issues(registry: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    identities: set[str] = set()
    for index, raw in enumerate(registry.get("workloads", []) if isinstance(registry.get("workloads"), list) else []):
        if not isinstance(raw, Mapping):
            issues.append(f"registry_workload_not_object:{index}")
            continue
        checked = contracts.validate_workload_contract(raw)
        workload_id = str(raw.get("id") or f"index-{index}")
        if not checked["valid"]:
            issues.extend(f"registry_workload_invalid:{workload_id}:{item}" for item in checked["issues"])
        if workload_id in identities:
            issues.append(f"registry_workload_identity_duplicate:{workload_id}")
        identities.add(workload_id)
    return sorted(set(issues))


def validate_controller_configuration(paths: ControllerPaths) -> dict[str, Any]:
    raw_policy, policy_error = adapters.load_json(paths.policy)
    errors: list[str] = []
    if policy_error:
        errors.append(f"policy_load_error:{policy_error}")
        policy = contracts.default_policy()
    else:
        checked = contracts.validate_policy(raw_policy)
        policy = checked["policy"]
        errors.extend(checked["issues"])
    registry = adapters.load_registry(paths.registry, paths.runtime_registry)
    if not registry["ok"]:
        errors.extend(f"registry_load_error:{item['path']}:{item['error']}" for item in registry["errors"])
    errors.extend(registry_contract_issues(registry))
    return {
        "schema": "abyss_machine_memory_controller_validation_v1",
        "ok": not errors,
        "errors": sorted(set(errors)),
        "policy_mode": policy.get("mode"),
        "registry": {
            "ok": registry["ok"],
            "workload_count": len(registry["workloads"]),
            "rule_count": len(registry["rules"]),
            "runtime_count": registry["runtime_count"],
        },
        "safety": {
            "fail_closed_to_shadow": True,
            "unknown_preserved": True,
            "generic_process_mutation": False,
        },
    }


def registered_systemd_units(registry: Mapping[str, Any]) -> set[str]:
    units: set[str] = set()
    for workload in registry.get("workloads", []) if isinstance(registry.get("workloads"), list) else []:
        if not isinstance(workload, Mapping):
            continue
        metadata = workload.get("metadata") if isinstance(workload.get("metadata"), Mapping) else {}
        one = str(metadata.get("systemd_unit") or "").strip()
        if one:
            units.add(one)
        many = metadata.get("systemd_units") if isinstance(metadata.get("systemd_units"), list) else []
        units.update(str(item).strip() for item in many if str(item).strip())
    for rule in registry.get("rules", []) if isinstance(registry.get("rules"), list) else []:
        if not isinstance(rule, Mapping):
            continue
        match = rule.get("match") if isinstance(rule.get("match"), Mapping) else {}
        for key in ("unit", "systemd_unit"):
            value = match.get(key)
            values = value if isinstance(value, list) else [value]
            units.update(str(item).strip() for item in values if str(item or "").strip())
    return units


def systemd_unit_relevance(unit: str, policy: Mapping[str, Any], registry: Mapping[str, Any]) -> dict[str, Any]:
    normalized = str(unit or "").strip()
    if normalized in registered_systemd_units(registry):
        return {"relevant": True, "reason": "exact_registry_identity"}
    event_loop = policy.get("event_loop") if isinstance(policy.get("event_loop"), Mapping) else {}
    systemd_policy = event_loop.get("systemd") if isinstance(event_loop.get("systemd"), Mapping) else {}
    prefixes = systemd_policy.get("managed_prefixes") if isinstance(systemd_policy.get("managed_prefixes"), list) else ["abyss-machine-"]
    if any(normalized.startswith(str(prefix)) for prefix in prefixes if str(prefix)):
        return {"relevant": True, "reason": "managed_prefix"}
    return {"relevant": False, "reason": "unregistered_unit_preserved_without_immediate_decision"}


class ControllerLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.fd: int | None = None

    def acquire(self) -> bool:
        if self.fd is not None:
            return True
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            return False
        os.ftruncate(fd, 0)
        os.write(fd, f"{os.getpid()}\n".encode("ascii"))
        os.fsync(fd)
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


class LinuxEventSources:
    def __init__(
        self,
        paths: ControllerPaths,
        policy: Mapping[str, Any],
        *,
        enable_psi: bool = True,
        enable_systemd: bool = True,
        cgroup_events: Path | None = None,
        reservations_root: Path | None = None,
        registry: Mapping[str, Any] | None = None,
        reservations: Mapping[str, Any] | None = None,
        epoch_port: EpochPort = time.time,
        monotonic_port: MonotonicPort = time.monotonic,
    ) -> None:
        self.paths = paths
        self.policy = dict(policy)
        self.registry = dict(registry or {})
        self.reservation_units = {
            str(item.get("unit") or "").strip()
            for item in (reservations or {}).get("items", [])
            if isinstance(item, Mapping) and str(item.get("unit") or "").strip()
        }
        self.systemd_units = registered_systemd_units(self.registry) | self.reservation_units
        self.enable_systemd = bool(enable_systemd)
        self.epoch_port = epoch_port
        self.monotonic_port = monotonic_port
        self.poller = select.poll()
        self._kinds: dict[int, tuple[str, str]] = {}
        self._counter = 0
        self._closed = False
        self._systemd_parser = adapters.DbusSystemdMonitorParser()
        self._systemd_monitor: Any = None
        self._systemd_retry_monotonic = 0.0
        self.errors: list[dict[str, Any]] = []
        self.ignored_systemd_events = 0
        self.psi_registration_edges_drained = 0
        paths.runtime_registry.mkdir(mode=0o700, parents=True, exist_ok=True)
        paths.queue.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._wake_read, self._wake_write = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
        self._register(self._wake_read, "wake", "wake", select.POLLIN)
        self.event_socket = adapters.open_event_socket(paths.socket)
        self._register(self.event_socket.fileno(), "socket", "event", select.POLLIN)
        self.inotify = adapters.InotifyWatcher()
        self._register(self.inotify.fd, "inotify", "change", select.POLLIN)
        watched_directories: set[Path] = set()
        for path, source in ((paths.runtime_registry, "registry"), (paths.queue, "queue")):
            self._add_watch(path, source, watched_directories)
        configuration_root = paths.policy.parent
        if configuration_root.is_dir():
            self._add_watch(configuration_root, "configuration", watched_directories)
        if reservations_root is not None:
            reservations_root.mkdir(mode=0o700, parents=True, exist_ok=True)
            self._add_watch(reservations_root, "reservations", watched_directories)
        if cgroup_events is not None and cgroup_events.exists():
            try:
                self.inotify.add(cgroup_events, source="cgroup_memory_events")
            except OSError as exc:
                self.errors.append({"source": "cgroup_memory_events", "error": str(exc)})
        self.psi_fds: list[int] = []
        if enable_psi:
            psi_policy = self.policy.get("event_loop", {}).get("psi", {})
            for kind in ("some", "full"):
                item = psi_policy.get(kind, {}) if isinstance(psi_policy.get(kind), Mapping) else {}
                result = adapters.open_psi_trigger(
                    Path("/proc/pressure/memory"),
                    kind=kind,
                    threshold_usec=int(item.get("threshold_usec", 100_000 if kind == "some" else 20_000)),
                    window_usec=int(item.get("window_usec", 2_000_000)),
                )
                if result.get("ok"):
                    fd = int(result["fd"])
                    self.psi_fds.append(fd)
                    initial = select.poll()
                    initial.register(fd, select.POLLPRI | select.POLLERR)
                    if initial.poll(0):
                        try:
                            os.lseek(fd, 0, os.SEEK_SET)
                            os.read(fd, 4_096)
                            self.psi_registration_edges_drained += 1
                        except OSError as exc:
                            self.errors.append({"source": f"psi:{kind}", "error": str(exc)})
                    self._register(fd, "psi", kind, select.POLLPRI | select.POLLERR)
                else:
                    self.errors.append({"source": f"psi:{kind}", "error": result.get("error"), "status": result.get("status")})
        if self.enable_systemd:
            self._start_systemd_monitor()

    def _register(self, fd: int, source: str, kind: str, mask: int) -> None:
        self.poller.register(fd, mask | select.POLLHUP | select.POLLNVAL)
        self._kinds[fd] = (source, kind)

    def _add_watch(self, path: Path, source: str, watched: set[Path]) -> None:
        resolved = path.resolve()
        if resolved in watched:
            return
        try:
            self.inotify.add(path, source=source)
            watched.add(resolved)
        except OSError as exc:
            self.errors.append({"source": source, "path": str(path), "error": str(exc)})

    def _start_systemd_monitor(self) -> None:
        if not self.systemd_units or self._systemd_monitor is not None or self.monotonic_port() < self._systemd_retry_monotonic:
            return
        try:
            monitor = adapters.start_systemd_monitor(self.systemd_units)
            if monitor.stdout is None:
                raise OSError("systemd monitor stdout is unavailable")
            fd = monitor.stdout.fileno()
            os.set_blocking(fd, False)
            self._systemd_monitor = monitor
            self._register(fd, "systemd", "signal", select.POLLIN)
        except OSError as exc:
            self.errors.append({"source": "systemd", "error": str(exc)})
            self._systemd_retry_monotonic = self.monotonic_port() + 5.0

    def _stop_systemd_monitor(self) -> None:
        monitor, self._systemd_monitor = self._systemd_monitor, None
        if monitor is None:
            return
        if monitor.stdout is not None:
            fd = monitor.stdout.fileno()
            try:
                self.poller.unregister(fd)
            except (KeyError, OSError):
                pass
            self._kinds.pop(fd, None)
        if monitor.poll() is None:
            monitor.terminate()
            try:
                monitor.wait(timeout=1.0)
            except Exception:
                monitor.kill()
                monitor.wait(timeout=1.0)
        self._systemd_retry_monotonic = self.monotonic_port() + 1.0

    def _event(self, source: str, kind: str, *, details: Mapping[str, Any] | None = None) -> ControllerEvent:
        epoch = float(self.epoch_port())
        monotonic = float(self.monotonic_port())
        self._counter += 1
        digest = hashlib.sha256(f"{source}\0{kind}\0{monotonic:.9f}\0{self._counter}".encode("utf-8")).hexdigest()[:20]
        return ControllerEvent(source, kind, f"{source}:{digest}", epoch, monotonic, dict(details or {}))

    def update_registry(self, registry: Mapping[str, Any], reservations: Mapping[str, Any] | None = None) -> None:
        new_registry = dict(registry)
        if reservations is not None:
            self.reservation_units = {
                str(item.get("unit") or "").strip()
                for item in reservations.get("items", [])
                if isinstance(item, Mapping) and str(item.get("unit") or "").strip()
            }
        new_units = registered_systemd_units(new_registry) | self.reservation_units
        self.registry = new_registry
        if new_units == self.systemd_units:
            return
        self.systemd_units = new_units
        self._stop_systemd_monitor()
        self._systemd_retry_monotonic = 0.0
        self._start_systemd_monitor()

    def _learn_identity_from_change(self, item: Mapping[str, Any]) -> None:
        name = str(item.get("name") or "")
        if not name.endswith(".json"):
            return
        document, error = adapters.load_json(Path(str(item.get("path") or "")) / name)
        if error or not isinstance(document, Mapping):
            return
        source = str(item.get("source") or "")
        if source == "reservations":
            unit = str(document.get("unit") or "").strip()
            if unit and unit not in self.reservation_units:
                self.reservation_units.add(unit)
                self.update_registry(self.registry)
        elif source == "registry":
            merged = {**self.registry, "workloads": [*self.registry.get("workloads", []), dict(document)]}
            self.update_registry(merged)

    def poll(self, timeout_ms: int) -> list[ControllerEvent]:
        if self._closed:
            return []
        if self.enable_systemd and self._systemd_monitor is None:
            self._start_systemd_monitor()
        events: list[ControllerEvent] = []
        for fd, flags in self.poller.poll(max(0, int(timeout_ms))):
            source, kind = self._kinds.get(fd, ("unknown", "unknown"))
            if source == "wake":
                try:
                    os.read(fd, 4096)
                except BlockingIOError:
                    pass
                continue
            if source == "inotify":
                cgroup_changes: list[dict[str, Any]] = []
                for item in self.inotify.read_events():
                    self._learn_identity_from_change(item)
                    if item["source"] == "cgroup_memory_events":
                        cgroup_changes.append(item)
                    else:
                        events.append(self._event(str(item["source"]), "filesystem_change", details=item))
                if cgroup_changes:
                    events.append(self._event(
                        "cgroup_memory_events",
                        "filesystem_change",
                        details={
                            **cgroup_changes[-1],
                            "change_count": len(cgroup_changes),
                            "first_mask": cgroup_changes[0].get("mask"),
                        },
                    ))
                continue
            if source == "socket":
                while True:
                    received = adapters.read_event_socket(self.event_socket, expected_uid=os.getuid())
                    if received.get("status") == "no_event":
                        break
                    if received.get("ok"):
                        item = received["event"]
                        events.append(ControllerEvent(
                            "socket",
                            str(item["kind"]),
                            str(item["event_id"]),
                            float(self.epoch_port()),
                            float(self.monotonic_port()),
                            {**dict(item["details"]), "peer_pid": received["pid"], "peer_uid": received["uid"]},
                        ))
                    else:
                        events.append(self._event("socket", "event_rejected", details=received))
                continue
            if source == "psi":
                try:
                    os.lseek(fd, 0, os.SEEK_SET)
                    current = os.read(fd, 4_096).decode("utf-8", errors="replace")
                except OSError as exc:
                    current = ""
                    self.errors.append({"source": f"psi:{kind}", "error": str(exc)})
                events.append(self._event("psi", kind, details={"current": current, "poll_flags": flags}))
                continue
            if source == "systemd":
                if flags & (select.POLLHUP | select.POLLERR | select.POLLNVAL):
                    events.append(self._event("systemd", "monitor_lost", details={"poll_flags": flags}))
                    self._stop_systemd_monitor()
                    continue
                try:
                    chunk = os.read(fd, 64 * 1024)
                except BlockingIOError:
                    chunk = b""
                if not chunk:
                    continue
                for parsed in self._systemd_parser.feed(chunk.decode("utf-8", errors="replace")):
                    relevance = systemd_unit_relevance(str(parsed.get("unit") or ""), self.policy, self.registry)
                    if relevance["relevant"] or str(parsed.get("unit") or "") in self.reservation_units:
                        events.append(self._event("systemd", str(parsed["kind"]), details={**parsed, "relevance": relevance["reason"]}))
                    else:
                        self.ignored_systemd_events += 1
        return events

    def wake(self) -> None:
        try:
            os.write(self._wake_write, b"x")
        except BlockingIOError:
            pass

    def status(self) -> dict[str, Any]:
        return {
            "psi_trigger_count": len(self.psi_fds),
            "systemd_monitor": self._systemd_monitor is not None,
            "inotify": self.inotify.fd >= 0,
            "event_socket": str(self.paths.socket),
            "registered_systemd_unit_count": len(registered_systemd_units(self.registry)),
            "exact_systemd_subscription_count": len(self.systemd_units),
            "systemd_subscription_mode": "exact_server_side",
            "ignored_systemd_events": self.ignored_systemd_events,
            "psi_registration_edges_drained": self.psi_registration_edges_drained,
            "errors": list(self.errors),
        }

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._stop_systemd_monitor()
        for fd in self.psi_fds:
            try:
                os.close(fd)
            except OSError:
                pass
        self.psi_fds = []
        self.inotify.close()
        self.event_socket.close()
        try:
            metadata = self.paths.socket.lstat()
            if metadata.st_uid == os.getuid():
                self.paths.socket.unlink()
        except FileNotFoundError:
            pass
        for fd in (self._wake_read, self._wake_write):
            try:
                os.close(fd)
            except OSError:
                pass


class ControllerEngine:
    def __init__(
        self,
        paths: ControllerPaths,
        *,
        sample_port: SamplePort = adapters.collect_memory_sample,
        reservations_port: ReservationsPort = adapters.default_reservations_port,
        lifecycle_route_port: adapters.HttpRoutePort = adapters.local_http_json,
        lifecycle_measurement_port: lifecycle.MeasurementPort = adapters.safe_user_cgroup_snapshot,
        epoch_port: EpochPort = time.time,
        monotonic_port: MonotonicPort = time.monotonic,
    ) -> None:
        self.paths = paths
        self.sample_port = sample_port
        self.reservations_port = reservations_port
        self.lifecycle_route_port = lifecycle_route_port
        self.lifecycle_measurement_port = lifecycle_measurement_port
        self.epoch_port = epoch_port
        self.monotonic_port = monotonic_port
        self.paths.evidence_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.paths.runtime_registry.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.paths.queue.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.paths.grants.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.store = adapters.EvidenceStore(paths.database)
        raw_policy, _policy_errors = _load_policy(paths.policy)
        history = raw_policy.get("history") if isinstance(raw_policy.get("history"), Mapping) else {}
        self.samples = self._load_forecast_samples(raw_policy)
        state, _error = adapters.load_json(paths.state)
        state_sequence = int(state.get("sequence") or 0) if isinstance(state, Mapping) else 0
        self.sequence = max(state_sequence, self.store.latest_sequence())
        identifiers = state.get("processed_event_ids") if isinstance(state, Mapping) else []
        self.processed_event_ids = [str(item) for item in identifiers] if isinstance(identifiers, list) else []
        last_actions = state.get("last_actions") if isinstance(state, Mapping) else {}
        self.last_actions = dict(last_actions) if isinstance(last_actions, Mapping) else {}
        try:
            signature = inspect.signature(sample_port)
            parameters = signature.parameters.values()
            self.sample_accepts_context = any(item.kind == inspect.Parameter.VAR_KEYWORD for item in parameters) or {
                "reservations_port",
                "queued_demand_mib",
                "epoch_port",
                "monotonic_port",
            }.issubset(signature.parameters)
        except (TypeError, ValueError):
            self.sample_accepts_context = True
        registry = adapters.load_registry(self.paths.registry, self.paths.runtime_registry)
        self.lifecycle_recovery = lifecycle.recover_pending_action(
            pending_path=self.paths.pending_action,
            store=self.store,
            registry=registry,
            route_port=self.lifecycle_route_port,
            history_limit=max(3, int(history.get("decision_limit", 30_000))),
            retention_hours=max(6.0, float(history.get("retention_hours", 24.0))),
            epoch_port=self.epoch_port,
        )
        recovered_workload = str(self.lifecycle_recovery.get("workload_id") or "")
        if recovered_workload and self.lifecycle_recovery.get("status") not in {"no_pending_action", "completed_pending_action_cleaned"}:
            self.last_actions[recovered_workload] = {
                "epoch": float(self.epoch_port()),
                "action": self.lifecycle_recovery.get("action"),
                "nonce": self.lifecycle_recovery.get("nonce"),
                "status": self.lifecycle_recovery.get("status"),
                "recovered": True,
            }

    def _load_forecast_samples(self, policy: Mapping[str, Any]) -> list[dict[str, Any]]:
        history = policy.get("history") if isinstance(policy.get("history"), Mapping) else {}
        forecast = policy.get("forecast") if isinstance(policy.get("forecast"), Mapping) else {}
        retention_limit = max(3, int(history.get("sample_limit", 30_000)))
        compute_limit = max(3, min(retention_limit, int(forecast.get("sample_window_limit", 512))))
        window_sec = max(60.0, min(3_600.0, float(forecast.get("sample_window_sec", 600.0))))
        samples = self.store.load_samples(limit=compute_limit)
        if not samples:
            return []
        latest_epoch = max(float(item.get("epoch") or 0.0) for item in samples)
        return [item for item in samples if float(item.get("epoch") or 0.0) >= latest_epoch - window_sec]

    def _collect_sample(self, *, reservations: Mapping[str, Any], queued_demand_mib: float) -> dict[str, Any]:
        if not self.sample_accepts_context:
            return self.sample_port()
        return self.sample_port(
            reservations_port=lambda: dict(reservations),
            queued_demand_mib=float(queued_demand_mib),
            epoch_port=self.epoch_port,
            monotonic_port=self.monotonic_port,
        )

    def _fresh_action_sample(self) -> dict[str, Any]:
        reservations = safe_reservations_snapshot(self.reservations_port)
        queue = queue_snapshot(self.paths.queue, now_epoch=float(self.epoch_port()), cleanup=True)
        return self._collect_sample(
            reservations=reservations,
            queued_demand_mib=float(queue["summary"]["demand_mib"]),
        )

    def decide(self, event: ControllerEvent) -> dict[str, Any]:
        if event.event_id in self.processed_event_ids or self.store.has_event(event.event_id):
            return {
                "ok": True,
                "status": "duplicate_event_ignored",
                "event_id": event.event_id,
                "sequence": self.sequence,
            }
        decision_started_monotonic = float(self.monotonic_port())
        decision_started_cpu = time.process_time()
        now_epoch = float(self.epoch_port())
        policy, configuration_errors = _load_policy(self.paths.policy)
        registry = adapters.load_registry(self.paths.registry, self.paths.runtime_registry)
        configuration_errors = [*configuration_errors, *registry_contract_issues(registry)]
        queue_policy = policy.get("queue") if isinstance(policy.get("queue"), Mapping) else {}
        queue = queue_snapshot(
            self.paths.queue,
            now_epoch=now_epoch,
            cleanup=True,
            maximum_wait_sec=float(queue_policy.get("maximum_wait_sec", 120.0)),
        )
        reservations = safe_reservations_snapshot(self.reservations_port)
        reservation_summary = reservations.get("summary") if isinstance(reservations.get("summary"), Mapping) else {}
        queued_demand = float(queue["summary"]["demand_mib"])
        current = self._collect_sample(reservations=reservations, queued_demand_mib=queued_demand)
        history = policy.get("history") if isinstance(policy.get("history"), Mapping) else {}
        sample_limit = max(3, int(history.get("sample_limit", 30_000)))
        decision_limit = max(3, int(history.get("decision_limit", 30_000)))
        retention_hours = max(6.0, float(history.get("retention_hours", 24.0)))
        self.store.append_sample(current, limit=sample_limit, retention_hours=retention_hours)
        self.samples = self._load_forecast_samples(policy)
        baseline_forecast = contracts.build_forecast(
            self.samples,
            outstanding_mib=float(reservation_summary.get("outstanding_mib") or 0.0),
            queued_demand_mib=0.0,
            policy=policy,
            now_epoch=now_epoch,
        )
        forecast = contracts.build_forecast(
            self.samples,
            outstanding_mib=float(reservation_summary.get("outstanding_mib") or 0.0),
            queued_demand_mib=queued_demand,
            policy=policy,
            now_epoch=now_epoch,
        )
        forecast["pending_queue_count"] = int(queue["summary"]["count"])
        grants = grant_snapshot(
            self.paths.grants,
            now_epoch=now_epoch,
            cleanup=True,
            maximum_ttl_sec=float(queue_policy.get("grant_ttl_sec", 5.0)),
        )
        runtime_evidence_errors: list[str] = []
        if queue.get("ok") is not True:
            runtime_evidence_errors.append("queue_evidence_invalid")
        if grants.get("ok") is not True:
            runtime_evidence_errors.append("grant_evidence_invalid")
        if reservations.get("ok") is not True:
            runtime_evidence_errors.append("reservation_evidence_invalid")
        queue_plan = contracts.plan_queue(
            queue["items"],
            samples=self.samples,
            outstanding_mib=float(reservation_summary.get("outstanding_mib") or 0.0),
            active_grants=grants["items"],
            policy=policy,
            now_epoch=now_epoch,
        )
        workloads = [item for item in registry["workloads"] if isinstance(item, Mapping)] if registry["ok"] else []
        event_members: list[Mapping[str, Any]] = [event.as_dict()]
        if event.kind == "coalesced" and isinstance(event.details.get("events"), list):
            event_members = [item for item in event.details["events"] if isinstance(item, Mapping)]
        launch_outcomes: list[dict[str, Any]] = []
        for member in event_members:
            if member.get("kind") != "resource_launch_outcome":
                continue
            details = member.get("details") if isinstance(member.get("details"), Mapping) else {}
            launch_outcomes.append(contracts.build_launch_outcome(
                event_id=str(member.get("event_id") or event.event_id),
                event_epoch=float(member.get("epoch") or event.epoch),
                details=details,
                workloads=workloads,
                policy=policy,
            ))
        decision = contracts.build_decision(
            forecast=forecast,
            workloads=workloads,
            controller_state={"last_actions": self.last_actions},
            policy=policy,
            now_epoch=now_epoch,
        )
        if configuration_errors or runtime_evidence_errors or not registry["ok"] or current.get("ok") is not True:
            decision["live_action_authorized"] = False
            decision["selected"] = {**decision["selected"], "execution": "shadow_only"}
        selected_document = decision.get("selected") if isinstance(decision.get("selected"), Mapping) else {}
        selected_action = str(selected_document.get("action") or "observe")
        if selected_action in contracts.LIFECYCLE_ACTION_ROUTE and self.paths.pending_action.exists():
            decision["live_action_authorized"] = False
            decision["selected"] = {**decision["selected"], "execution": "shadow_only"}
            decision["reason"]["lifecycle_block"] = "unrecovered_action_present"
        queue_execution: dict[str, Any] = {
            "status": "runtime_evidence_invalid" if runtime_evidence_errors else "shadow_or_not_authorized",
            "grant_written": False,
        }
        selected_request = queue_plan.get("selected") if isinstance(queue_plan.get("selected"), Mapping) else None
        next_sequence = self.sequence + 1
        if (
            selected_request is not None
            and decision.get("live_action_authorized") is True
            and decision.get("selected", {}).get("action") == "queue_control"
        ):
            request_id = str(selected_request["request_id"])
            nonce = hashlib.sha256(f"{request_id}\0{next_sequence}\0{event.event_id}".encode("utf-8")).hexdigest()
            grant = {
                "schema": "abyss_machine_memory_controller_queue_grant_v1",
                "request_id": request_id,
                "owner": selected_request.get("owner"),
                "issued_epoch": now_epoch,
                "expires_epoch": selected_request["expires_epoch"],
                "controller_sequence": next_sequence,
                "controller_event_id": event.event_id,
                "nonce": nonce,
                "reason": selected_request.get("reason"),
                "policy": {"one_grant_at_a_time": True, "fresh_plan_required_before_launch": True},
            }
            grant_path = resource_adapters.atomic_write_controller_queue_grant(self.paths.runtime_root, grant)
            queue_execution = {
                "status": "grant_written",
                "grant_written": True,
                "request_id": request_id,
                "path": str(grant_path),
                "nonce": nonce,
                "expires_epoch": grant["expires_epoch"],
            }
        completed_monotonic = float(self.monotonic_port())
        latency_ms = round(max(0.0, completed_monotonic - event.monotonic) * 1_000.0, 3)
        self.sequence += 1
        processed_limit = max(32, int(history.get("processed_event_limit", 512)))
        self.processed_event_ids = [*self.processed_event_ids, event.event_id][-processed_limit:]
        packet = {
            "schema": "abyss_machine_memory_controller_reason_packet_v1",
            "ok": True,
            "status": "decision_recorded",
            "sequence": self.sequence,
            "epoch": now_epoch,
            "event": event.as_dict(),
            "timing": {
                "decision_completed_monotonic": completed_monotonic,
                "event_to_decision_ms": latency_ms,
                "target_ms": 2_000.0,
                "within_target": latency_ms <= 2_000.0,
                "scope": "controller_control_plane",
                "interactive_latency_claim": "not_measured_by_controller_event_latency",
            },
            "sample": current,
            "forecast": forecast,
            "baseline_forecast": baseline_forecast,
            "decision": decision,
            "registry": {
                "ok": registry["ok"],
                "workload_count": len(registry["workloads"]),
                "rule_count": len(registry["rules"]),
                "runtime_count": registry["runtime_count"],
                "errors": registry["errors"],
            },
            "reservations": {
                "ok": bool(reservations.get("ok", True)),
                "summary": dict(reservation_summary),
            },
            "queue": queue,
            "grants": grants,
            "queue_plan": queue_plan,
            "queue_execution": queue_execution,
            "launch_outcome": launch_outcomes[0] if len(launch_outcomes) == 1 else None,
            "launch_outcomes": launch_outcomes,
            "configuration": {
                "policy_path": str(self.paths.policy),
                "registry_path": str(self.paths.registry),
                "fail_closed": bool(configuration_errors or runtime_evidence_errors or not registry["ok"]),
                "errors": configuration_errors,
                "runtime_evidence_errors": runtime_evidence_errors,
            },
            "integrity": {
                "unknown_workloads_preserved": True,
                "protected_workloads_preserved": True,
                "generic_process_mutation": False,
                "action_executor_present": True,
                "action_executor_typed_local_http_only": True,
                "reason_packet_atomic": True,
            },
            "lifecycle_recovery": self.lifecycle_recovery,
        }
        lifecycle_execution: dict[str, Any] = {
            "ok": True,
            "status": "not_selected_or_not_authorized",
        }
        if selected_action in contracts.LIFECYCLE_ACTION_ROUTE and decision.get("live_action_authorized") is True:
            execution_policy = policy.get("execution") if isinstance(policy.get("execution"), Mapping) else {}
            action_plan = lifecycle.build_action_plan(
                decision["selected"],
                event_id=event.event_id,
                sequence=self.sequence,
                now_epoch=now_epoch,
                ttl_sec=float(execution_policy.get("action_plan_ttl_sec", 5.0)),
            )
            lifecycle_execution = lifecycle.execute_action_plan(
                action_plan,
                pending_path=self.paths.pending_action,
                lock_path=self.paths.action_lock,
                store=self.store,
                route_port=self.lifecycle_route_port,
                measurement_port=self.lifecycle_measurement_port,
                sample_port=self._fresh_action_sample,
                history_limit=decision_limit,
                retention_hours=retention_hours,
                epoch_port=self.epoch_port,
                monotonic_port=self.monotonic_port,
            )
            execution_status = str(lifecycle_execution.get("status") or "")
            if execution_status in {
                "action_completed_verified",
                "action_failed_rolled_back",
                "action_failed_rollback_failed",
                "live_preflight_failed",
            }:
                self.last_actions[str(decision["selected"].get("workload_id") or "")] = {
                    "epoch": float(self.epoch_port()),
                    "action": selected_action,
                    "nonce": lifecycle_execution.get("nonce"),
                    "status": execution_status,
                }
        packet["lifecycle_execution"] = lifecycle_execution
        packet["forecast_outcomes"] = self.store.reconcile_forecasts(
            packet,
            limit=decision_limit,
            retention_hours=retention_hours,
        )
        work_completed_monotonic = float(self.monotonic_port())
        usage = resource.getrusage(resource.RUSAGE_SELF)
        packet["controller_overhead"] = {
            "decision_compute_wall_ms": round(max(0.0, completed_monotonic - decision_started_monotonic) * 1_000.0, 3),
            "total_pre_persist_wall_ms": round(max(0.0, work_completed_monotonic - decision_started_monotonic) * 1_000.0, 3),
            "process_cpu_ms": round(max(0.0, time.process_time() - decision_started_cpu) * 1_000.0, 3),
            "process_peak_rss_mib": round(max(0.0, float(usage.ru_maxrss)) / 1_024.0, 3),
            "energy_mwh": None,
            "energy_status": "per_process_energy_not_attributable_without_owner_probe",
            "policy": {
                "bounded_in_process_measurement": True,
                "no_rapl_or_privileged_probe_in_hot_path": True,
            },
        }
        state = {
            "schema": "abyss_machine_memory_controller_state_v1",
            "sequence": self.sequence,
            "processed_event_ids": self.processed_event_ids,
            "last_actions": self.last_actions,
            "last_checkpoint_epoch": now_epoch,
        }
        actions = policy.get("actions") if isinstance(policy.get("actions"), Mapping) else {}
        queue_action = actions.get("queue_control") if isinstance(actions.get("queue_control"), Mapping) else {}
        event_loop = policy.get("event_loop") if isinstance(policy.get("event_loop"), Mapping) else {}
        queue_live = bool(
            policy.get("mode") == "live"
            and queue_action.get("live_enabled") is True
            and forecast.get("confidence") == "high"
            and not configuration_errors
            and not runtime_evidence_errors
            and registry["ok"]
            and current.get("ok") is True
        )
        admission = {
            "schema": "abyss_machine_memory_controller_admission_v1",
            "ok": True,
            "epoch": now_epoch,
            "fresh_until_epoch": now_epoch + max(15.0, float(event_loop.get("heartbeat_sec", 10.0)) * 3.0),
            "controller_sequence": next_sequence,
            "mode": policy.get("mode"),
            "queue_live": queue_live,
            "pressure_band": forecast.get("pressure_band"),
            "confidence": forecast.get("confidence"),
            "active_memory_relief_needed": forecast.get("active_memory_relief_needed"),
            "new_work_control_needed": forecast.get("new_work_control_needed"),
            "request_root": str(self.paths.queue),
            "grant_root": str(self.paths.grants),
            "policy": {
                "new_background_starts_only": True,
                "fallback_to_existing_resource_plan_when_stale": True,
                "no_existing_process_mutation": True,
            },
        }
        self.store.append_decision(packet, limit=decision_limit, retention_hours=retention_hours)
        for launch_outcome in launch_outcomes:
            self.store.append_launch_outcome(launch_outcome, limit=decision_limit, retention_hours=retention_hours)
        resource_adapters.atomic_write_controller_admission(self.paths.runtime_root, admission)
        adapters.atomic_write_json(self.paths.state, state)
        adapters.atomic_write_json(self.paths.latest, packet)
        return packet

    def close(self) -> None:
        self.store.close()


class ControllerRunner:
    def __init__(
        self,
        paths: ControllerPaths,
        *,
        epoch_port: EpochPort = time.time,
        monotonic_port: MonotonicPort = time.monotonic,
    ) -> None:
        self.paths = paths
        self.epoch_port = epoch_port
        self.monotonic_port = monotonic_port
        self.stopping = False
        self.sources: LinuxEventSources | None = None

    def stop(self) -> None:
        self.stopping = True
        if self.sources is not None:
            self.sources.wake()

    def run(self, *, maximum_decisions: int | None = None) -> dict[str, Any]:
        lock = ControllerLock(self.paths.runtime_root / "controller.lock")
        if not lock.acquire():
            return {
                "schema": "abyss_machine_memory_controller_run_v1",
                "ok": False,
                "status": "controller_already_running",
            }
        previous_handlers: dict[int, Any] = {}
        engine: ControllerEngine | None = None
        try:
            policy, configuration_errors = _load_policy(self.paths.policy)
            engine = ControllerEngine(self.paths, epoch_port=self.epoch_port, monotonic_port=self.monotonic_port)
            registry = adapters.load_registry(self.paths.registry, self.paths.runtime_registry)
            reservations = adapters.default_reservations_port()
            cgroup_events = adapters.default_user_cgroup_path() / "memory.events"
            self.sources = LinuxEventSources(
                self.paths,
                policy,
                cgroup_events=cgroup_events,
                reservations_root=adapters.default_reservations_root(),
                registry=registry,
                reservations=reservations,
                epoch_port=self.epoch_port,
                monotonic_port=self.monotonic_port,
            )
            for signum in (signal.SIGTERM, signal.SIGINT):
                try:
                    previous_handlers[signum] = signal.getsignal(signum)
                    signal.signal(signum, lambda _signum, _frame: self.stop())
                except ValueError:
                    previous_handlers.clear()
                    break
            event_loop = policy.get("event_loop") if isinstance(policy.get("event_loop"), Mapping) else {}
            coalescer = EventCoalescer(
                debounce_ms=int(event_loop.get("debounce_ms", 200)),
                max_coalesce_ms=int(event_loop.get("max_coalesce_ms", 1_000)),
            )
            heartbeat_sec = max(1.0, float(event_loop.get("heartbeat_sec", 10.0)))
            started_epoch = float(self.epoch_port())
            started_monotonic = float(self.monotonic_port())
            startup = ControllerEvent(
                "controller",
                "startup_recovery",
                f"startup:{os.getpid()}:{started_epoch:.6f}",
                started_epoch,
                started_monotonic,
                {
                    "event_sources": self.sources.status(),
                    "configuration_errors": configuration_errors,
                    "recovered_sequence": engine.sequence,
                    "recovered_sample_count": len(engine.samples),
                },
            )
            latest = engine.decide(startup)
            decisions = 1
            next_heartbeat = float(self.monotonic_port()) + heartbeat_sec
            while not self.stopping and (maximum_decisions is None or decisions < maximum_decisions):
                now = float(self.monotonic_port())
                due_values = [max(0.0, next_heartbeat - now)]
                coalesce_ms = coalescer.remaining_ms(now)
                if coalesce_ms is not None:
                    due_values.append(coalesce_ms / 1_000.0)
                timeout_ms = min(1_000, max(0, math.ceil(min(due_values) * 1_000.0)))
                for item in self.sources.poll(timeout_ms):
                    coalescer.add(item)
                now = float(self.monotonic_port())
                if now >= next_heartbeat:
                    epoch = float(self.epoch_port())
                    coalescer.add(ControllerEvent(
                        "controller",
                        "recovery_heartbeat",
                        f"heartbeat:{epoch:.6f}",
                        epoch,
                        now,
                        {"event_sources": self.sources.status()},
                    ))
                    next_heartbeat = now + heartbeat_sec
                if coalescer.ready(now):
                    latest = engine.decide(coalescer.pop(now))
                    decisions += 1
                    self.sources.update_registry(
                        adapters.load_registry(self.paths.registry, self.paths.runtime_registry),
                        adapters.default_reservations_port(),
                    )
            return {
                "schema": "abyss_machine_memory_controller_run_v1",
                "ok": True,
                "status": "stopped" if self.stopping else "maximum_decisions_reached",
                "pid": os.getpid(),
                "decisions": decisions,
                "started_epoch": started_epoch,
                "stopped_epoch": float(self.epoch_port()),
                "last_sequence": latest.get("sequence"),
            }
        finally:
            for signum, handler in previous_handlers.items():
                signal.signal(signum, handler)
            if self.sources is not None:
                self.sources.close()
                self.sources = None
            if engine is not None:
                engine.close()
            lock.close()


def controller_status(paths: ControllerPaths) -> dict[str, Any]:
    latest, error = adapters.load_json(paths.latest)
    if error:
        return {
            "schema": "abyss_machine_memory_controller_status_v1",
            "ok": True,
            "status": "not_started",
            "latest": str(paths.latest),
        }
    evidence = controller_evidence(paths) if paths.database.is_file() else None
    return {
        "schema": "abyss_machine_memory_controller_status_v1",
        "ok": True,
        "status": "running_or_last_checkpoint",
        "sequence": int(latest.get("sequence") or 0),
        "epoch": latest.get("epoch"),
        "mode": latest.get("decision", {}).get("mode"),
        "selected": latest.get("decision", {}).get("selected"),
        "timing": latest.get("timing"),
        "evidence": evidence,
        "latest": str(paths.latest),
    }


def controller_evidence(paths: ControllerPaths) -> dict[str, Any]:
    if not paths.database.is_file():
        return {
            "schema": "abyss_machine_memory_controller_evidence_summary_v1",
            "ok": True,
            "status": "not_started",
            "database": str(paths.database),
        }
    store = adapters.EvidenceStore(paths.database)
    try:
        return {"ok": True, "status": "evidence_ready", **store.summary()}
    finally:
        store.close()


def _event(kind: str, *, epoch_port: EpochPort = time.time, monotonic_port: MonotonicPort = time.monotonic) -> ControllerEvent:
    epoch = float(epoch_port())
    monotonic = float(monotonic_port())
    digest = hashlib.sha256(f"{kind}\0{epoch:.9f}\0{os.getpid()}".encode("utf-8")).hexdigest()[:20]
    return ControllerEvent(source="cli", kind=kind, event_id=f"cli:{digest}", epoch=epoch, monotonic=monotonic)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="abyss-machine memory controller")
    parser.add_argument("command", choices=("run", "once", "status", "evidence", "validate", "notify", "register", "unregister"))
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--kind", default="external_event")
    parser.add_argument("--event-id", default="")
    parser.add_argument("--details-json", default="{}")
    parser.add_argument("--maximum-decisions", type=int)
    parser.add_argument("--contract-file", type=Path)
    parser.add_argument("--workload-id", default="")
    parser.add_argument("--json", action="store_true")
    return parser


def _paths_from_args(args: argparse.Namespace) -> ControllerPaths:
    base = default_paths()
    return ControllerPaths(
        policy=args.policy or base.policy,
        registry=args.registry or base.registry,
        runtime_root=args.runtime_root or base.runtime_root,
        evidence_root=args.evidence_root or base.evidence_root,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    paths = _paths_from_args(args)
    if args.command == "validate":
        result = validate_controller_configuration(paths)
    elif args.command == "status":
        result = controller_status(paths)
    elif args.command == "evidence":
        result = controller_evidence(paths)
    elif args.command == "run":
        result = ControllerRunner(paths).run(maximum_decisions=args.maximum_decisions)
    elif args.command == "notify":
        try:
            details = json.loads(args.details_json)
        except json.JSONDecodeError as exc:
            result = {"ok": False, "status": "invalid_details_json", "error": str(exc)}
        else:
            if not isinstance(details, Mapping):
                result = {"ok": False, "status": "details_must_be_object"}
            else:
                epoch = time.time()
                identifier = args.event_id or f"notify:{os.getpid()}:{epoch:.9f}"
                document = {
                    "schema": "abyss_machine_memory_controller_event_v1",
                    "kind": args.kind,
                    "event_id": identifier,
                    "details": dict(details),
                }
                try:
                    adapters.send_event_socket(paths.socket, document)
                except OSError as exc:
                    result = {"ok": False, "status": "notify_failed", "error": str(exc)}
                else:
                    result = {"ok": True, "status": "event_sent", "event_id": identifier, "socket": str(paths.socket)}
    elif args.command == "register":
        if args.contract_file is None:
            result = {"ok": False, "status": "contract_file_required"}
        else:
            document, error = adapters.load_json(args.contract_file)
            result = {"ok": False, "status": "contract_load_failed", "error": error} if error else register_runtime_contract(paths, document or {})
    elif args.command == "unregister":
        result = unregister_runtime_contract(paths, args.workload_id)
    else:
        engine = ControllerEngine(paths)
        try:
            result = engine.decide(_event("manual_once"))
        finally:
            engine.close()
    print(json.dumps(result, indent=2 if not args.json else None, sort_keys=True, allow_nan=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import hmac
import json
import os
from pathlib import Path
import socket
import socketserver
import time
from typing import Any, Callable, Mapping

from . import resource_adapters, resource_planning


PlanPort = Callable[[Mapping[str, Any], dict[str, Any]], dict[str, Any]]
ReliefPort = Callable[[Mapping[str, Any], Mapping[str, Any]], dict[str, Any]]
DispatchPort = Callable[[Mapping[str, Any]], tuple[dict[str, Any], bool]]
SocketFactoryPort = Callable[..., socket.socket]
TimestampPort = Callable[[], str]


def socket_path(environ: Mapping[str, str] | None = None, *, uid: int | None = None) -> Path:
    source = os.environ if environ is None else environ
    configured = source.get("ABYSS_MACHINE_RESOURCE_ADMISSION_SOCKET")
    if configured:
        return Path(configured)
    root = resource_adapters.runtime_root(source, uid=uid)
    return root / "abyss-machine" / "resource" / "admission.sock"


def client_request(
    payload: Mapping[str, Any],
    *,
    path: Path,
    timeout_sec: float = 5.0,
    max_response_bytes: int = 256 * 1024,
    path_exists: Callable[[Path], bool] = Path.exists,
    socket_factory: SocketFactoryPort = socket.socket,
) -> dict[str, Any]:
    if not path_exists(path):
        return {
            "ok": False,
            "decision": "deny",
            "error": "runtime_admission_unavailable",
            "socket": str(path),
            "policy": {"fail_closed": True},
        }
    try:
        encoded = json.dumps(dict(payload), sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        with socket_factory(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(max(0.1, float(timeout_sec)))
            client.connect(str(path))
            client.sendall(encoded)
            client.shutdown(socket.SHUT_WR)
            chunks: list[bytes] = []
            received = 0
            while True:
                chunk = client.recv(min(65536, max_response_bytes + 1 - received))
                if not chunk:
                    break
                chunks.append(chunk)
                received += len(chunk)
                if received > max_response_bytes:
                    return {
                        "ok": False,
                        "decision": "deny",
                        "error": "runtime_admission_response_too_large",
                        "policy": {"fail_closed": True},
                    }
    except OSError as exc:
        return {
            "ok": False,
            "decision": "deny",
            "error": "runtime_admission_transport_error",
            "error_type": type(exc).__name__,
            "socket": str(path),
            "policy": {"fail_closed": True},
        }
    try:
        response = json.loads(b"".join(chunks).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        response = None
    if not isinstance(response, dict):
        return {
            "ok": False,
            "decision": "deny",
            "error": "runtime_admission_response_invalid",
            "policy": {"fail_closed": True},
        }
    return response


def _lease_receipt(lease: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": lease.get("id"),
        "lease_kind": lease.get("lease_kind"),
        "owner": lease.get("owner"),
        "workload_id": lease.get("workload_id"),
        "request_id": lease.get("request_id"),
        "activity": lease.get("activity"),
        "class": lease.get("class"),
        "kind": lease.get("kind"),
        "operation": lease.get("operation"),
        "importance_class": lease.get("importance_class"),
        "data_risk": lease.get("data_risk"),
        "recoverability": lease.get("recoverability"),
        "owner_pid": lease.get("owner_pid"),
        "owner_cgroup": lease.get("owner_cgroup"),
        "demand_mib": lease.get("demand_mib"),
        "created_at": lease.get("created_at"),
        "expires_at_epoch": lease.get("expires_at_epoch"),
        "runtime_only": True,
    }


def _plan_receipt(plan: Mapping[str, Any]) -> dict[str, Any]:
    inputs = plan.get("inputs") if isinstance(plan.get("inputs"), dict) else {}
    demand = inputs.get("startup_demand", {})
    projected = demand.get("projected") if isinstance(demand, dict) and isinstance(demand.get("projected"), dict) else {}
    swap_reserve = inputs.get("swap_reserve") if isinstance(inputs.get("swap_reserve"), dict) else {}
    activity = plan.get("request", {}).get("activity", {}) if isinstance(plan.get("request"), dict) else {}
    return {
        "decision": plan.get("decision"),
        "blocked_reasons": list(plan.get("blocked_reasons") or []),
        "denied_reasons": list(plan.get("denied_reasons") or []),
        "warnings": list(plan.get("warnings") or []),
        "projected_memory": {
            "class": projected.get("memory_class"),
            "mem_available_mib": projected.get("mem_available_mib"),
        },
        "swap_reserve": {
            "state": swap_reserve.get("state"),
            "free_mib": swap_reserve.get("free_mib"),
            "target_free_mib": swap_reserve.get("target_free_mib"),
            "shortfall_mib": swap_reserve.get("shortfall_mib"),
        },
        "activity": activity,
    }


def reserve_runtime_demand(
    request: Mapping[str, Any],
    *,
    reservation_root: Path,
    runtime_policy: Mapping[str, Any],
    plan_port: PlanPort,
    relief_port: ReliefPort | None = None,
    now_epoch: float | None = None,
    timestamp: TimestampPort,
) -> dict[str, Any]:
    contract = resource_planning.runtime_admission_request(request)
    if not bool(runtime_policy.get("enabled", True)):
        return {
            "ok": False,
            "decision": "deny",
            "command": "reserve",
            "denied_reasons": ["runtime_admission_disabled"],
            "policy": {"fail_closed": True, "runtime_only": True},
        }
    if not contract.get("valid"):
        return {
            "ok": False,
            "decision": "deny",
            "command": "reserve",
            "denied_reasons": ["owner_contract_invalid"],
            "contract_errors": list(contract.get("errors") or []),
            "policy": {"fail_closed": True, "runtime_only": True},
        }

    normalized = contract["request"]
    lease_id = str(contract["lease_id"])
    resolved_now = time.time() if now_epoch is None else float(now_epoch)
    operation = str(normalized.get("operation") or "cold_load")
    ttl_prefix = "cold_load" if operation == "cold_load" else "workload"
    ttl_default = max(1.0, float(runtime_policy.get(f"{ttl_prefix}_lease_ttl_sec", 120.0 if operation == "cold_load" else 21600.0)))
    ttl_max = max(ttl_default, float(runtime_policy.get(f"{ttl_prefix}_lease_max_ttl_sec", 300.0 if operation == "cold_load" else 86400.0)))
    ttl_sec = min(ttl_default, ttl_max)

    with resource_adapters.admission_lock(reservation_root):
        snapshot = resource_adapters.reservation_snapshot(
            reservation_root,
            cleanup=True,
            cleanup_invalid=False,
            now_epoch=resolved_now,
        )
        if not snapshot.get("ok"):
            return {
                "ok": False,
                "decision": "deny",
                "command": "reserve",
                "denied_reasons": ["lease_state_invalid"],
                "lease_state_error_count": int(snapshot.get("summary", {}).get("error_count") or 0),
                "policy": {"fail_closed": True, "runtime_only": True},
            }
        existing_path = resource_adapters.lease_path(reservation_root, lease_id)
        if existing_path.is_file():
            try:
                existing = json.loads(existing_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                existing = None
            if isinstance(existing, dict):
                same_request = hmac.compare_digest(
                    str(existing.get("request_digest") or ""),
                    str(contract.get("request_digest") or ""),
                )
                same_token = hmac.compare_digest(
                    str(existing.get("release_token_sha256") or ""),
                    str(contract.get("release_token_sha256") or ""),
                )
                if same_request and same_token:
                    return {
                        "ok": True,
                        "decision": "allow",
                        "command": "reserve",
                        "idempotent_replay": True,
                        "lease": _lease_receipt(existing),
                        "policy": {
                            "runtime_only": True,
                            "release_after_materialization": True,
                            "pressure_facts_assign_importance": False,
                        },
                    }
                return {
                    "ok": False,
                    "decision": "deny",
                    "command": "reserve",
                    "denied_reasons": ["request_identity_conflict"],
                    "policy": {"fail_closed": True, "runtime_only": True},
                }

        try:
            plan = plan_port(normalized, snapshot)
        except Exception as exc:
            return {
                "ok": False,
                "decision": "deny",
                "command": "reserve",
                "denied_reasons": ["host_plan_unavailable"],
                "error_type": type(exc).__name__,
                "policy": {"fail_closed": True, "runtime_only": True},
            }
        relief: dict[str, Any] | None = None
        if (
            (plan.get("decision") != "allow" or not plan.get("ok"))
            and relief_port is not None
            and bool(runtime_policy.get("owner_relief_enabled", False))
        ):
            try:
                relief = relief_port(normalized, plan)
            except Exception as exc:
                relief = {"ok": False, "action_executed": False, "reason": "relief_port_failed", "error_type": type(exc).__name__}
            if relief.get("action_executed") is True:
                refreshed = resource_adapters.reservation_snapshot(
                    reservation_root,
                    cleanup=True,
                    cleanup_invalid=False,
                    now_epoch=resolved_now,
                )
                if refreshed.get("ok"):
                    try:
                        plan = plan_port(normalized, refreshed)
                    except Exception as exc:
                        plan = {"ok": False, "decision": "deny", "denied_reasons": ["host_remeasure_unavailable"], "error_type": type(exc).__name__}
        if plan.get("decision") != "allow" or not plan.get("ok"):
            receipt = _plan_receipt(plan)
            return {
                "ok": False,
                "decision": str(plan.get("decision") or "deny"),
                "command": "reserve",
                "blocked_reasons": receipt["blocked_reasons"],
                "denied_reasons": receipt["denied_reasons"],
                "warnings": receipt["warnings"],
                "plan": receipt,
                "relief": relief,
                "policy": {"fail_closed": True, "runtime_only": True},
            }

        lease = {
            "schema": "abyss_machine_resource_runtime_lease_v1",
            "lease_kind": "runtime_cold_load" if operation == "cold_load" else "runtime_workload",
            "id": lease_id,
            "created_at": timestamp(),
            "created_at_epoch": resolved_now,
            "expires_at_epoch": resolved_now + ttl_sec,
            "owner": normalized["owner"],
            "workload_id": normalized["workload_id"],
            "request_id": normalized["request_id"],
            "activity": normalized["activity"],
            "class": normalized["class"],
            "kind": normalized["kind"],
            "operation": operation,
            "importance_class": normalized["importance_class"],
            "data_risk": normalized["data_risk"],
            "recoverability": normalized["recoverability"],
            "owner_pid": normalized["owner_pid"],
            "owner_cgroup": normalized["owner_cgroup"],
            "demand_mib": normalized["memory_demand_mib"],
            "demand_owner": normalized["owner"],
            "demand_key": normalized.get("demand_key") or f"{normalized['owner']}:{normalized['workload_id']}",
            "estimate_source": normalized["estimate_source"],
            "estimate_confidence": normalized["estimate_confidence"],
            "request_digest": contract["request_digest"],
            "release_token_sha256": contract["release_token_sha256"],
            "unknown_demand": False,
            "runtime_only": True,
        }
        resource_adapters.atomic_write_lease(reservation_root, lease)
        return {
            "ok": True,
            "decision": "allow",
            "command": "reserve",
            "idempotent_replay": False,
            "lease": _lease_receipt(lease),
            "plan": _plan_receipt(plan),
            "relief": relief,
            "policy": {
                "runtime_only": True,
                "release_after_materialization": True,
                "expires_fail_closed_if_owner_disappears": True,
                "pressure_facts_assign_importance": False,
            },
        }


def reserve_cold_load(
    request: Mapping[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    return reserve_runtime_demand(request, **kwargs)


def release_runtime_demand(
    request: Mapping[str, Any],
    *,
    reservation_root: Path,
) -> dict[str, Any]:
    lease_id = str(request.get("lease_id") or "").strip()
    release_token = str(request.get("release_token") or "")
    if not lease_id or len(release_token) < 24:
        return {
            "ok": False,
            "decision": "deny",
            "command": "release",
            "denied_reasons": ["release_contract_invalid"],
        }
    with resource_adapters.admission_lock(reservation_root):
        path = resource_adapters.lease_path(reservation_root, lease_id)
        try:
            lease = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {
                "ok": True,
                "decision": "allow",
                "command": "release",
                "released": False,
                "already_absent": True,
            }
        except (OSError, json.JSONDecodeError):
            return {
                "ok": False,
                "decision": "deny",
                "command": "release",
                "denied_reasons": ["lease_state_invalid"],
            }
        if not isinstance(lease, dict) or lease.get("lease_kind") not in {"runtime_cold_load", "runtime_workload"}:
            return {
                "ok": False,
                "decision": "deny",
                "command": "release",
                "denied_reasons": ["lease_kind_not_releasable"],
            }
        supplied = resource_planning.runtime_admission_request(
            {
                "owner": lease.get("owner"),
                "workload_id": lease.get("workload_id"),
                "request_id": lease.get("request_id"),
                "release_token": release_token,
                "activity": lease.get("activity"),
                "class": lease.get("class"),
                "kind": lease.get("kind"),
                "memory_demand_mib": lease.get("demand_mib"),
                "operation": lease.get("operation") or "cold_load",
                "importance_class": lease.get("importance_class") or "protected",
                "data_risk": bool(lease.get("data_risk")),
                "recoverability": lease.get("recoverability") or "preserve",
                "owner_pid": lease.get("owner_pid"),
                "owner_cgroup": lease.get("owner_cgroup"),
                "demand_key": lease.get("demand_key"),
            }
        )
        token_matches = hmac.compare_digest(
            str(lease.get("release_token_sha256") or ""),
            str(supplied.get("release_token_sha256") or ""),
        )
        if not token_matches:
            return {
                "ok": False,
                "decision": "deny",
                "command": "release",
                "denied_reasons": ["release_capability_invalid"],
            }
        released = resource_adapters.remove_lease(reservation_root, lease_id)
        return {
            "ok": released,
            "decision": "allow" if released else "deny",
            "command": "release",
            "released": released,
            "lease": _lease_receipt(lease),
        }


def release_cold_load(
    request: Mapping[str, Any],
    *,
    reservation_root: Path,
) -> dict[str, Any]:
    return release_runtime_demand(request, reservation_root=reservation_root)


def status(*, reservation_root: Path, now_epoch: float | None = None) -> dict[str, Any]:
    with resource_adapters.admission_lock(reservation_root):
        snapshot = resource_adapters.reservation_snapshot(
            reservation_root,
            cleanup=True,
            cleanup_invalid=False,
            now_epoch=now_epoch,
        )
    leases = [
        _lease_receipt(item)
        for item in snapshot.get("items", [])
        if isinstance(item, dict) and item.get("lease_kind") in {"runtime_cold_load", "runtime_workload"}
    ]
    cold_load_count = sum(item.get("lease_kind") == "runtime_cold_load" for item in leases)
    workload_count = sum(item.get("lease_kind") == "runtime_workload" for item in leases)
    return {
        "ok": bool(snapshot.get("ok")),
        "decision": "observe",
        "command": "status",
        "leases": leases,
        "summary": {
            "active_cold_load_leases": cold_load_count,
            "active_workload_leases": workload_count,
            "active_runtime_leases": len(leases),
            "outstanding_mib": round(sum(float(item.get("demand_mib") or 0.0) for item in leases), 3),
        },
        "policy": {
            "runtime_only": True,
            "release_capabilities_hidden": True,
            "no_process_mutation": True,
        },
    }


def dispatch(
    payload: Mapping[str, Any],
    *,
    server_state: Mapping[str, Any],
    reserve_port: Callable[[Mapping[str, Any]], dict[str, Any]],
    release_port: Callable[[Mapping[str, Any]], dict[str, Any]],
    status_port: Callable[[], dict[str, Any]],
    allow_shutdown: bool = False,
) -> tuple[dict[str, Any], bool]:
    command = str(payload.get("command") or "status").strip().lower()
    if command == "ping":
        return {**dict(server_state), "ok": True, "command": "ping"}, False
    if command == "status":
        return dict(status_port()), False
    request = payload.get("request") if isinstance(payload.get("request"), dict) else {}
    if command == "reserve":
        return dict(reserve_port(request)), False
    if command == "release":
        return dict(release_port(request)), False
    if command == "shutdown" and allow_shutdown:
        return {"ok": True, "decision": "allow", "command": "shutdown"}, True
    return {
        "ok": False,
        "decision": "deny",
        "command": command,
        "denied_reasons": ["command_unsupported"],
    }, False


def run_server_loop(
    *,
    path: Path,
    dispatch_port: DispatchPort,
    chmod_mode: int = 0o600,
    max_request_bytes: int = 65536,
    maintenance_port: Callable[[], None] | None = None,
) -> dict[str, Any]:
    path = Path(path).expanduser()
    if chmod_mode != 0o600:
        raise ValueError("runtime admission socket mode must be 0600")
    if len(os.fsencode(path)) >= 104:
        raise ValueError("runtime admission socket path is too long")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.exists():
        if path.is_symlink():
            raise FileExistsError(f"runtime admission socket path is a symlink: {path}")
        if not path.is_socket():
            raise FileExistsError(f"runtime admission socket path is not a socket: {path}")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.2)
            try:
                probe.connect(str(path))
            except ConnectionRefusedError:
                path.unlink()
            except OSError as exc:
                raise OSError(f"cannot safely classify existing runtime admission socket: {path}") from exc
            else:
                raise OSError(f"runtime admission socket is already active: {path}")

    class Handler(socketserver.StreamRequestHandler):
        def handle(self) -> None:
            should_shutdown = False
            self.connection.settimeout(5.0)
            try:
                raw = self.rfile.readline(max_request_bytes + 1)
            except (OSError, TimeoutError):
                raw = None
            if raw is None:
                response = {
                    "ok": False,
                    "decision": "deny",
                    "denied_reasons": ["request_read_failed"],
                }
            elif len(raw) > max_request_bytes:
                response = {
                    "ok": False,
                    "decision": "deny",
                    "denied_reasons": ["request_too_large"],
                }
            else:
                try:
                    payload = json.loads(raw.decode("utf-8"))
                    if not isinstance(payload, dict):
                        raise ValueError("request_not_object")
                    response, should_shutdown = dispatch_port(payload)
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
                    response = {
                        "ok": False,
                        "decision": "deny",
                        "denied_reasons": ["malformed_request"],
                    }
            if should_shutdown:
                self.server.should_shutdown = True  # type: ignore[attr-defined]
            try:
                self.wfile.write(json.dumps(response, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n")
            except OSError:
                pass

    class UnixServer(socketserver.UnixStreamServer):
        allow_reuse_address = True

    server: UnixServer | None = None
    try:
        server = UnixServer(str(path), Handler)
        server.should_shutdown = False  # type: ignore[attr-defined]
        server.timeout = 1.0
        os.chmod(path, 0o600)
        while not getattr(server, "should_shutdown", False):
            server.handle_request()
            if maintenance_port is not None:
                maintenance_port()
    finally:
        if server is not None:
            server.server_close()
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    return {"ok": True, "socket": str(path), "stopped": True}

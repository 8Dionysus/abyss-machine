from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import tempfile
import time
from typing import Any, Callable, Iterable, Mapping


UnitStatePort = Callable[[str], dict[str, Any]]
PidAlivePort = Callable[[int], bool]


def runtime_root(
    environ: Mapping[str, str] | None = None,
    *,
    uid: int | None = None,
    path_exists: Callable[[Path], bool] = Path.is_dir,
) -> Path:
    source = os.environ if environ is None else environ
    configured = source.get("XDG_RUNTIME_DIR")
    if configured:
        return Path(configured)
    resolved_uid = os.getuid() if uid is None else int(uid)
    candidate = Path(f"/run/user/{resolved_uid}")
    if path_exists(candidate):
        return candidate
    return Path(tempfile.gettempdir()) / f"abyss-machine-{resolved_uid}"


def reservations_root(
    environ: Mapping[str, str] | None = None,
    *,
    uid: int | None = None,
) -> Path:
    return runtime_root(environ, uid=uid) / "abyss-machine" / "resource" / "reservations"


def memory_controller_runtime_root(environ: Mapping[str, str] | None = None, *, uid: int | None = None) -> Path:
    source = os.environ if environ is None else environ
    configured = source.get("ABYSS_MEMORY_CONTROLLER_RUNTIME")
    if configured:
        return Path(configured)
    return runtime_root(source, uid=uid) / "abyss-machine" / "memory-controller"


def controller_queue_root(root: Path) -> Path:
    return root / "queue"


def controller_grants_root(root: Path) -> Path:
    return root / "grants"


def controller_admission_path(root: Path) -> Path:
    return root / "admission.json"


def parse_systemd_memory_peak_mib(value: Any) -> float | None:
    text = str(value or "").partition("(")[0].strip()
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*([KMGTPE]?)(?:i?B)?", text, flags=re.IGNORECASE)
    if not match:
        return None
    number = float(match.group(1))
    power = {"": 0, "K": 1, "M": 2, "G": 3, "T": 4, "P": 5, "E": 6}[match.group(2).upper()]
    bytes_value = number * (1024.0**power)
    return round(bytes_value / 1024.0 / 1024.0, 3)


def notify_memory_controller(root: Path, event: Mapping[str, Any]) -> dict[str, Any]:
    path = root / "events.sock"
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return {"sent": False, "status": "controller_not_running"}
    if not stat.S_ISSOCK(metadata.st_mode) or metadata.st_uid != os.getuid():
        return {"sent": False, "status": "controller_socket_not_owned"}
    payload = json.dumps(dict(event), sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(payload) > 16_384:
        return {"sent": False, "status": "event_too_large"}
    client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        client.connect(str(path))
        sent = client.send(payload)
    except OSError as exc:
        return {"sent": False, "status": "notify_failed", "error": str(exc)}
    finally:
        client.close()
    return {"sent": sent == len(payload), "status": "event_sent" if sent == len(payload) else "partial_event_send"}


def admission_lock_path(root: Path) -> Path:
    return root.parent / "admission.lock"


@contextmanager
def admission_lock(root: Path) -> Iterable[None]:
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_path = admission_lock_path(root)
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def lease_filename(lease_id: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(lease_id)).strip("-.") or "lease"
    digest = hashlib.sha256(str(lease_id).encode("utf-8")).hexdigest()[:12]
    return f"{normalized[:80]}-{digest}.json"


def lease_path(root: Path, lease_id: str) -> Path:
    return root / lease_filename(lease_id)


def atomic_write_lease(root: Path, lease: dict[str, Any]) -> Path:
    lease_id = str(lease.get("id") or "")
    if not lease_id:
        raise ValueError("lease id is required")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination = lease_path(root, lease_id)
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=str(root))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(lease, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return destination


def _atomic_write_runtime_document(destination: Path, document: Mapping[str, Any]) -> Path:
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=str(destination.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(dict(document), handle, sort_keys=True, separators=(",", ":"), allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return destination


def controller_queue_request_path(root: Path, request_id: str) -> Path:
    return controller_queue_root(root) / lease_filename(request_id)


def controller_queue_grant_path(root: Path, request_id: str) -> Path:
    return controller_grants_root(root) / lease_filename(request_id)


def atomic_write_controller_queue_request(root: Path, request: Mapping[str, Any]) -> Path:
    request_id = str(request.get("id") or "")
    if not request_id:
        raise ValueError("queue request id is required")
    return _atomic_write_runtime_document(controller_queue_request_path(root, request_id), request)


def atomic_write_controller_queue_grant(root: Path, grant: Mapping[str, Any]) -> Path:
    request_id = str(grant.get("request_id") or "")
    if not request_id:
        raise ValueError("queue grant request_id is required")
    return _atomic_write_runtime_document(controller_queue_grant_path(root, request_id), grant)


def atomic_write_controller_admission(root: Path, admission: Mapping[str, Any]) -> Path:
    return _atomic_write_runtime_document(controller_admission_path(root), admission)


def remove_controller_queue_request(root: Path, request_id: str) -> bool:
    try:
        controller_queue_request_path(root, request_id).unlink()
        return True
    except FileNotFoundError:
        return False


def remove_controller_queue_grant(root: Path, request_id: str) -> bool:
    try:
        controller_queue_grant_path(root, request_id).unlink()
        return True
    except FileNotFoundError:
        return False


def controller_queue_grant(root: Path, request_id: str, *, now_epoch: float | None = None) -> dict[str, Any]:
    resolved_now = time.time() if now_epoch is None else float(now_epoch)
    path = controller_queue_grant_path(root, request_id)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"status": "missing", "request_id": request_id, "path": str(path)}
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "invalid", "request_id": request_id, "path": str(path), "error": str(exc)}
    if not isinstance(document, dict) or str(document.get("request_id") or "") != str(request_id):
        return {"status": "invalid", "request_id": request_id, "path": str(path), "error": "grant_identity_mismatch"}
    try:
        expires_epoch = float(document.get("expires_epoch") or 0.0)
    except (TypeError, ValueError):
        expires_epoch = 0.0
    status = "granted" if expires_epoch > resolved_now else "expired"
    return {**document, "status": status, "path": str(path)}


def controller_admission_snapshot(root: Path, *, now_epoch: float | None = None) -> dict[str, Any]:
    resolved_now = time.time() if now_epoch is None else float(now_epoch)
    path = controller_admission_path(root)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"ok": False, "status": "missing", "path": str(path), "queue_live": False}
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "status": "invalid", "path": str(path), "queue_live": False, "error": str(exc)}
    if not isinstance(document, dict):
        return {"ok": False, "status": "invalid", "path": str(path), "queue_live": False, "error": "document_not_object"}
    fresh_until = float(document.get("fresh_until_epoch") or 0.0)
    fresh = fresh_until > resolved_now
    socket_path = root / "events.sock"
    try:
        socket_metadata = socket_path.lstat()
        controller_available = stat.S_ISSOCK(socket_metadata.st_mode) and socket_metadata.st_uid == os.getuid()
    except FileNotFoundError:
        controller_available = False
    queue_declared = bool(document.get("queue_live"))
    queue_live = queue_declared and fresh and controller_available
    return {
        **document,
        "ok": bool(document.get("ok")) and fresh and (not queue_declared or controller_available),
        "status": "controller_unavailable" if queue_declared and fresh and not controller_available else ("fresh" if fresh else "stale"),
        "queue_live": queue_live,
        "controller_socket": str(socket_path),
        "controller_available": controller_available,
        "path": str(path),
    }


def remove_lease(root: Path, lease_id: str) -> bool:
    try:
        lease_path(root, lease_id).unlink()
        return True
    except FileNotFoundError:
        return False


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def systemd_user_unit_state(unit: str) -> dict[str, Any]:
    if not unit:
        return {"exists": False, "active": False, "state": "missing", "memory_current_mib": 0.0}
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "show", unit, "--property=LoadState", "--property=ActiveState", "--property=MemoryCurrent"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=2.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"exists": False, "active": False, "state": "unknown", "memory_current_mib": 0.0, "error": str(exc)}
    properties: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            properties[key] = value
    active_state = properties.get("ActiveState", "unknown")
    load_state = properties.get("LoadState", "not-found")
    raw_memory = properties.get("MemoryCurrent", "0")
    try:
        memory_current_mib = max(0.0, float(raw_memory) / 1024.0 / 1024.0)
    except (TypeError, ValueError):
        memory_current_mib = 0.0
    return {
        "exists": load_state not in {"", "not-found"},
        "active": active_state in {"active", "activating", "reloading"},
        "state": active_state,
        "load_state": load_state,
        "memory_current_mib": round(memory_current_mib, 3),
        "returncode": proc.returncode,
        "error": proc.stderr.strip() or None,
    }


def lease_status(
    lease: dict[str, Any],
    *,
    now_epoch: float,
    pid_alive_port: PidAlivePort = pid_alive,
    unit_state_port: UnitStatePort = systemd_user_unit_state,
) -> dict[str, Any]:
    lease_id = str(lease.get("id") or "")
    try:
        launcher_pid = int(lease.get("launcher_pid") or 0)
    except (TypeError, ValueError):
        launcher_pid = 0
    try:
        expires_at = float(lease.get("expires_at_epoch") or 0.0)
    except (TypeError, ValueError):
        expires_at = 0.0
    raw_demand = lease.get("demand_mib")
    demand_mib: float | None
    try:
        demand_mib = None if raw_demand is None else max(0.0, float(raw_demand))
    except (TypeError, ValueError):
        demand_mib = None
    launcher_alive = pid_alive_port(launcher_pid)
    unit = str(lease.get("unit") or "")
    unit_state = unit_state_port(unit) if unit else {
        "exists": False,
        "active": False,
        "state": "pending",
        "memory_current_mib": 0.0,
    }
    unit_active = bool(unit_state.get("active"))
    expired = expires_at <= 0.0 or now_epoch >= expires_at
    invalid = not lease_id or launcher_pid <= 0
    stale = invalid or expired or (not launcher_alive and not unit_active)
    if invalid:
        stale_reason = "invalid_identity"
    elif expired:
        stale_reason = "startup_deadline_elapsed"
    elif not launcher_alive and not unit_active:
        stale_reason = "launcher_dead_and_unit_inactive"
    else:
        stale_reason = None
    materialized_mib = max(0.0, float(unit_state.get("memory_current_mib") or 0.0))
    outstanding_mib = None if demand_mib is None else max(0.0, demand_mib - materialized_mib)
    return {
        **lease,
        "launcher_alive": launcher_alive,
        "unit_state": unit_state,
        "expired": expired,
        "stale": stale,
        "stale_reason": stale_reason,
        "demand_mib": demand_mib,
        "materialized_mib": round(materialized_mib, 3),
        "outstanding_mib": None if outstanding_mib is None else round(outstanding_mib, 3),
        "unknown_demand": demand_mib is None,
    }


def reservation_snapshot(
    root: Path,
    *,
    cleanup: bool = False,
    now_epoch: float | None = None,
    pid_alive_port: PidAlivePort = pid_alive,
    unit_state_port: UnitStatePort = systemd_user_unit_state,
) -> dict[str, Any]:
    resolved_now = time.time() if now_epoch is None else float(now_epoch)
    items: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    if root.is_dir():
        for path in sorted(root.glob("*.json")):
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                errors.append({"path": str(path), "error": str(exc)})
                if cleanup:
                    try:
                        path.unlink()
                        removed.append({"path": str(path), "reason": "invalid_json"})
                    except OSError:
                        pass
                continue
            if not isinstance(document, dict):
                errors.append({"path": str(path), "error": "lease_not_object"})
                continue
            status = lease_status(
                document,
                now_epoch=resolved_now,
                pid_alive_port=pid_alive_port,
                unit_state_port=unit_state_port,
            )
            status["path"] = str(path)
            if status.get("stale"):
                if cleanup:
                    try:
                        path.unlink()
                        removed.append({"id": status.get("id"), "path": str(path), "reason": status.get("stale_reason")})
                    except OSError as exc:
                        errors.append({"path": str(path), "error": str(exc)})
                continue
            items.append(status)
    outstanding_mib = sum(float(item.get("outstanding_mib") or 0.0) for item in items)
    unknown_count = sum(1 for item in items if item.get("unknown_demand"))
    return {
        "schema": "abyss_machine_resource_reservation_snapshot_v1",
        "ok": not errors,
        "root": str(root),
        "items": items,
        "removed": removed,
        "errors": errors,
        "summary": {
            "active_count": len(items),
            "known_count": len(items) - unknown_count,
            "unknown_count": unknown_count,
            "outstanding_mib": round(outstanding_mib, 3),
            "removed_count": len(removed),
            "error_count": len(errors),
        },
        "policy": {
            "runtime_only": True,
            "materialized_memory_not_double_counted": True,
            "no_process_mutation": True,
        },
    }

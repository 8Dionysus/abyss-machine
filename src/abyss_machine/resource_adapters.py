from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
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

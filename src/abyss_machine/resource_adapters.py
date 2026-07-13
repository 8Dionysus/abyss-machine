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
RunPort = Callable[..., subprocess.CompletedProcess[str]]


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


def demand_profiles_path(
    environ: Mapping[str, str] | None = None,
    *,
    uid: int | None = None,
) -> Path:
    return runtime_root(environ, uid=uid) / "abyss-machine" / "resource" / "demand-profiles.json"


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


def atomic_write_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(document, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
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


def load_demand_profiles(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        document = {}
    profiles = document.get("profiles") if isinstance(document, dict) else None
    return {
        "schema": "abyss_machine_resource_demand_profiles_v1",
        "runtime_only": True,
        "profiles": profiles if isinstance(profiles, dict) else {},
    }


def demand_profile(document: Mapping[str, Any], key: str | None) -> dict[str, Any] | None:
    if not key:
        return None
    profiles = document.get("profiles") if isinstance(document.get("profiles"), dict) else {}
    profile = profiles.get(key)
    return dict(profile) if isinstance(profile, dict) else None


def update_demand_profiles(
    document: Mapping[str, Any],
    *,
    key: str,
    owner: str,
    kind: str,
    memory_peak_mib: float,
    memory_swap_peak_mib: float,
    observed_at_epoch: float,
    multiplier: float = 1.25,
    max_entries: int = 64,
    max_samples: int = 16,
) -> dict[str, Any]:
    profiles_source = document.get("profiles") if isinstance(document.get("profiles"), dict) else {}
    profiles = {str(name): dict(value) for name, value in profiles_source.items() if isinstance(value, dict)}
    profile = dict(profiles.get(key) or {})
    old_samples = profile.get("samples") if isinstance(profile.get("samples"), list) else []
    footprint_mib = max(0.0, float(memory_peak_mib)) + max(0.0, float(memory_swap_peak_mib))
    sample = {
        "observed_at_epoch": round(float(observed_at_epoch), 3),
        "memory_peak_mib": round(max(0.0, float(memory_peak_mib)), 3),
        "memory_swap_peak_mib": round(max(0.0, float(memory_swap_peak_mib)), 3),
        "footprint_peak_mib": round(footprint_mib, 3),
    }
    samples = [dict(item) for item in old_samples if isinstance(item, dict)] + [sample]
    samples = samples[-max(1, min(int(max_samples), 64)):]
    observed_max = max(float(item.get("footprint_peak_mib") or 0.0) for item in samples)
    profile.update(
        {
            "key": key,
            "owner": owner,
            "kind": kind,
            "updated_at_epoch": round(float(observed_at_epoch), 3),
            "sample_count": len(samples),
            "observed_max_mib": round(observed_max, 3),
            "estimate_mib": round(observed_max * max(1.0, float(multiplier)), 3),
            "estimate_source": "runtime_observed_unit_peak",
            "samples": samples,
        }
    )
    profiles[key] = profile
    bounded_entries = max(1, min(int(max_entries), 256))
    if len(profiles) > bounded_entries:
        ordered = sorted(profiles.items(), key=lambda item: float(item[1].get("updated_at_epoch") or 0.0), reverse=True)
        profiles = dict(ordered[:bounded_entries])
    return {
        "schema": "abyss_machine_resource_demand_profiles_v1",
        "runtime_only": True,
        "profiles": profiles,
    }


def record_demand_observation(
    path: Path,
    *,
    key: str,
    owner: str,
    kind: str,
    memory_peak_mib: float,
    memory_swap_peak_mib: float,
    observed_at_epoch: float,
    multiplier: float = 1.25,
    max_entries: int = 64,
    max_samples: int = 16,
) -> dict[str, Any]:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_path = path.with_suffix(".lock")
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        updated = update_demand_profiles(
            load_demand_profiles(path),
            key=key,
            owner=owner,
            kind=kind,
            memory_peak_mib=memory_peak_mib,
            memory_swap_peak_mib=memory_swap_peak_mib,
            observed_at_epoch=observed_at_epoch,
            multiplier=multiplier,
            max_entries=max_entries,
            max_samples=max_samples,
        )
        atomic_write_json(path, updated)
        profile = demand_profile(updated, key) or {}
        return {"ok": True, "path": str(path), "profile": profile, "runtime_only": True}
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def journal_unit_resource_peaks(
    unit: str,
    *,
    since_epoch: float | None = None,
    run_port: RunPort = subprocess.run,
) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_.:@\\-]+\.(?:service|scope)", str(unit or "")):
        return {"ok": False, "unit": unit, "error": "invalid_unit_identity"}
    try:
        command = ["journalctl", "--user", "--unit", unit]
        if since_epoch is not None:
            command.extend(["--since", f"@{max(0.0, float(since_epoch)):.6f}"])
        command.extend(["--output=json", "--no-pager", "--all", "--lines=128"])
        proc = run_port(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "unit": unit, "error": str(exc)}
    memory_peak = 0
    memory_swap_peak = 0
    matched_records = 0
    for line in proc.stdout.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        record_unit = str(item.get("USER_UNIT") or item.get("_SYSTEMD_USER_UNIT") or "")
        if record_unit and record_unit != unit:
            continue
        found = False
        for key, current in (("MEMORY_PEAK", "memory"), ("MEMORY_SWAP_PEAK", "swap")):
            try:
                value = max(0, int(item.get(key) or 0))
            except (TypeError, ValueError):
                value = 0
            if value:
                found = True
                if current == "memory":
                    memory_peak = max(memory_peak, value)
                else:
                    memory_swap_peak = max(memory_swap_peak, value)
        if found:
            matched_records += 1
    return {
        "ok": proc.returncode == 0 and bool(memory_peak or memory_swap_peak),
        "unit": unit,
        "memory_peak_bytes": memory_peak,
        "memory_swap_peak_bytes": memory_swap_peak,
        "memory_peak_mib": round(memory_peak / 1024.0 / 1024.0, 3),
        "memory_swap_peak_mib": round(memory_swap_peak / 1024.0 / 1024.0, 3),
        "footprint_peak_mib": round((memory_peak + memory_swap_peak) / 1024.0 / 1024.0, 3),
        "matched_records": matched_records,
        "returncode": proc.returncode,
        "error": proc.stderr.strip() or (None if memory_peak or memory_swap_peak else "resource_peak_not_found"),
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
    unknown_demand = bool(lease.get("unknown_demand")) or demand_mib is None
    startup_deadline_elapsed = expired and (unknown_demand or not unit_active)
    stale = invalid or startup_deadline_elapsed or (not launcher_alive and not unit_active)
    if invalid:
        stale_reason = "invalid_identity"
    elif startup_deadline_elapsed:
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
        "phase": "active_unit" if unit_active else "startup",
        "expired": expired,
        "stale": stale,
        "stale_reason": stale_reason,
        "demand_mib": demand_mib,
        "materialized_mib": round(materialized_mib, 3),
        "outstanding_mib": None if outstanding_mib is None else round(outstanding_mib, 3),
        "unknown_demand": unknown_demand,
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

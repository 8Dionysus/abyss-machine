"""Small, explicit write-capacity reservations for host-owned storage routes.

Reservations are accounting leases only.  They do not create files, hold
filesystem space, or grant permission to mutate a target.  The caller must
still run write-preflight and its owner-specific hooks immediately before the
write.  A single flock-protected directory makes acquire/release/expiry
updates atomic for concurrent user processes without introducing a resident
resource controller.  A resource launch may hold a lease past its nominal
TTL until its systemd unit has a confirmed terminal state; expiry never
silently releases such a lease.
"""

from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Callable, Mapping

from .storage_adapters import disk_usage_summary, existing_ancestor


SCHEMA = "abyss_machine_storage_write_reservation_v1"
TERMINAL_RETENTION_LIMIT = 128


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _parse_time(value: Any) -> dt.datetime | None:
    if isinstance(value, dt.datetime):
        result = value
    elif isinstance(value, str) and value.strip():
        try:
            result = dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=dt.timezone.utc)
    return result.astimezone(dt.timezone.utc)


def _iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat()


def _safe_id(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "")).strip("-")
    digest = hashlib.sha256(str(value or "").encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"{clean[:80] or 'reservation'}-{digest}"


def _reservation_path(root: Path, reservation_id: str) -> Path:
    return root / "records" / f"{_safe_id(reservation_id)}.json"


def _atomic_write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(dict(value), handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_name, 0o664)
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def _read(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _filesystem_key(path: Path) -> str:
    anchor = existing_ancestor(path)
    try:
        return _filesystem_key_for_device(int(anchor.stat().st_dev))
    except OSError:
        return f"anchor:{anchor}"


def _filesystem_key_for_device(st_dev: int) -> str:
    """Build the shared accounting key from one validated device identity."""
    return f"dev:{int(st_dev)}"


def _target_filesystem_device(target: Path) -> int | None:
    """Read the target's current filesystem device from one path snapshot."""
    try:
        return int(existing_ancestor(target).stat().st_dev)
    except OSError:
        return None


def _route_filesystem_device(target: Path, route_metadata: Mapping[str, Any] | None) -> int | None:
    """Validate route identity and return the same device used for accounting.

    Route identity is receipt metadata only.  Capacity accounting continues to
    use the shared ``filesystem_key`` so leases from every route aggregate on
    one filesystem.  The returned device is read under the reservation lock so
    a path remount cannot leave a lease in a pre-lock bucket.
    """
    actual_device = _target_filesystem_device(target)
    if actual_device is None:
        return None
    if not route_metadata:
        return actual_device
    identity = route_metadata.get("archive_binding")
    if not isinstance(identity, Mapping):
        return None
    expected_device = identity.get("st_dev")
    if isinstance(expected_device, bool) or not isinstance(expected_device, int):
        return None
    return actual_device if actual_device == expected_device else None


def _route_filesystem_identity_ok(target: Path, route_metadata: Mapping[str, Any] | None) -> bool:
    """Compatibility predicate for callers that only need the guard result."""
    return _route_filesystem_device(target, route_metadata) is not None


def _lock(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    handle = open(root / ".lock", "a+", encoding="utf-8")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    return handle


def _records_unlocked(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted((root / "records").glob("*.json")):
        record = _read(path)
        if record and record.get("schema") == SCHEMA:
            records.append(record)
    return records


def _state_errors_unlocked(root: Path) -> list[dict[str, Any]]:
    """Report malformed lease files so unknown accounting cannot be ignored."""
    errors: list[dict[str, Any]] = []
    records_root = root / "records"
    for path in sorted(records_root.glob("*.json")):
        if path.is_symlink():
            errors.append({"path": str(path), "error": "reservation_record_symlink"})
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append({"path": str(path), "error": str(exc)[:500]})
            continue
        if not isinstance(value, dict):
            errors.append({"path": str(path), "error": "reservation_record_not_object"})
            continue
        if value.get("schema") != SCHEMA:
            errors.append({"path": str(path), "error": "reservation_schema_invalid"})
            continue
        reservation_id = str(value.get("reservation_id") or "").strip()
        if not reservation_id:
            errors.append({"path": str(path), "error": "reservation_id_missing"})
        elif path.name != _reservation_path(root, reservation_id).name:
            errors.append({"path": str(path), "error": "reservation_filename_mismatch"})
        requested = value.get("requested_bytes")
        if isinstance(requested, bool) or not isinstance(requested, int) or requested < 0:
            errors.append({"path": str(path), "error": "requested_bytes_invalid"})
        if not isinstance(value.get("active"), bool):
            errors.append({"path": str(path), "error": "active_flag_invalid"})
        if value.get("active") is True and _parse_time(value.get("expires_at")) is None:
            errors.append({"path": str(path), "error": "active_expiry_invalid"})
        if "hold_until_terminal" in value and not isinstance(value.get("hold_until_terminal"), bool):
            errors.append({"path": str(path), "error": "hold_until_terminal_invalid"})
        if not str(value.get("filesystem_key") or ""):
            errors.append({"path": str(path), "error": "filesystem_key_missing"})
    return errors


def _expire_unlocked(root: Path, now: dt.datetime) -> list[dict[str, Any]]:
    expired: list[dict[str, Any]] = []
    for record in _records_unlocked(root):
        if record.get("active") is not True:
            continue
        deadline = _parse_time(record.get("expires_at"))
        if deadline is None:
            record["status"] = "invalid_expiry"
            _atomic_write(_reservation_path(root, str(record.get("reservation_id") or "")), record)
            continue
        if deadline > now:
            continue
        if record.get("hold_until_terminal") is True:
            if record.get("expiry_deferred") is not True:
                record["expiry_deferred"] = True
                record["expiry_deferred_at"] = _iso(now)
                record["status"] = "active_terminal_hold"
                _atomic_write(_reservation_path(root, str(record.get("reservation_id") or "")), record)
            continue
        record["active"] = False
        record["status"] = "expired"
        record["expired_at"] = _iso(now)
        _atomic_write(_reservation_path(root, str(record.get("reservation_id") or "")), record)
        expired.append(record)
    return expired


def _terminal_time(record: Mapping[str, Any]) -> dt.datetime:
    for field in ("released_at", "expired_at", "finished_at", "issued_at"):
        parsed = _parse_time(record.get(field))
        if parsed is not None:
            return parsed
    return dt.datetime.min.replace(tzinfo=dt.timezone.utc)


def _prune_terminal_unlocked(
    root: Path,
    *,
    retention_limit: int = TERMINAL_RETENTION_LIMIT,
) -> list[dict[str, Any]]:
    """Keep active state intact while bounding completed lease metadata."""
    limit = max(1, int(retention_limit))
    terminal: list[tuple[Path, dict[str, Any]]] = []
    records_root = root / "records"
    for path in sorted(records_root.glob("*.json")):
        if path.is_symlink():
            continue
        record = _read(path)
        if not isinstance(record, dict):
            continue
        if record.get("schema") != SCHEMA or record.get("active") is not False:
            continue
        if record.get("status") not in {"released", "expired"}:
            continue
        terminal.append((path, record))
    terminal.sort(key=lambda item: (_terminal_time(item[1]), item[0].name))
    removed: list[dict[str, Any]] = []
    for path, record in terminal[:-limit]:
        try:
            path.unlink()
        except OSError:
            continue
        removed.append(
            {
                "reservation_id": record.get("reservation_id"),
                "status": record.get("status"),
                "path": str(path),
            }
        )
    return removed


def _expiry_deferred_unlocked(root: Path, now: dt.datetime) -> list[dict[str, Any]]:
    deferred: list[dict[str, Any]] = []
    for record in _records_unlocked(root):
        if record.get("active") is not True or record.get("hold_until_terminal") is not True:
            continue
        deadline = _parse_time(record.get("expires_at"))
        if deadline is not None and deadline <= now:
            deferred.append(record)
    return deferred


def _capacity(
    target: Path,
    *,
    disk_usage: Callable[..., Mapping[str, Any]] = disk_usage_summary,
) -> dict[str, Any]:
    try:
        return dict(disk_usage(target, statvfs=os.statvfs))
    except TypeError:
        return dict(disk_usage(target))


def list_reservations(
    root: Path,
    *,
    now: dt.datetime | None = None,
    terminal_retention_limit: int = TERMINAL_RETENTION_LIMIT,
) -> dict[str, Any]:
    now = now or _now()
    with _lock(root) as handle:
        try:
            expired = _expire_unlocked(root, now)
            pruned = _prune_terminal_unlocked(
                root,
                retention_limit=terminal_retention_limit,
            )
            records = _records_unlocked(root)
            state_errors = _state_errors_unlocked(root)
            deferred = _expiry_deferred_unlocked(root, now)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    active = [item for item in records if item.get("active") is True]
    return {
        "schema": SCHEMA,
        "ok": not state_errors,
        "generated_at": _iso(now),
        "records": records,
        "active": active,
        "expired_count": len(expired),
        "expiry_deferred_count": len(deferred),
        "expiry_deferred": deferred,
        "pruned_count": len(pruned),
        "terminal_retention_limit": max(1, int(terminal_retention_limit)),
        "state_errors": state_errors[:200],
        "active_reserved_bytes": sum(max(0, int(item.get("requested_bytes") or 0)) for item in active),
        "automatic_write": False,
    }


def capacity_snapshot(root: Path, target: Path, *, now: dt.datetime | None = None) -> dict[str, Any]:
    """Return capacity after active leases for ``target`` without acquiring one."""
    target = Path(target).expanduser()
    if not root.exists():
        usage = _capacity(target)
        available = usage.get("available_to_user_bytes")
        if not isinstance(available, int):
            available = usage.get("free_bytes") if isinstance(usage.get("free_bytes"), int) else None
        return {
            "ok": True,
            "usage": usage,
            "filesystem_key": _filesystem_key(target),
            "active_reserved_bytes": 0,
            "available_to_user_bytes": available,
            "available_after_reservations_bytes": available,
            "active_reservation_ids": [],
            "expired_count": 0,
        }
    listing = list_reservations(root, now=now)
    filesystem_key = _filesystem_key(target)
    active = [
        item for item in listing.get("active", [])
        if str(item.get("filesystem_key") or "") == filesystem_key
    ]
    usage = _capacity(target)
    available = usage.get("available_to_user_bytes")
    if not isinstance(available, int):
        available = usage.get("free_bytes") if isinstance(usage.get("free_bytes"), int) else None
    reserved = sum(max(0, int(item.get("requested_bytes") or 0)) for item in active)
    return {
        "ok": bool(listing.get("ok", True)),
        "usage": usage,
        "filesystem_key": filesystem_key,
        "active_reserved_bytes": reserved,
        "available_to_user_bytes": available,
        "available_after_reservations_bytes": max(0, int(available) - reserved) if isinstance(available, int) else None,
        "active_reservation_ids": [str(item.get("reservation_id")) for item in active],
        "expired_count": listing.get("expired_count", 0),
        "state_errors": listing.get("state_errors", []),
    }


def acquire_reservation(
    root: Path,
    *,
    reservation_id: str,
    kind: str,
    requested_bytes: int,
    target: Path,
    owner: str,
    ttl_seconds: int = 3600,
    min_free_after: int = 0,
    hold_until_terminal: bool = False,
    execution_identity: str | None = None,
    route_metadata: Mapping[str, Any] | None = None,
    now: dt.datetime | None = None,
    disk_usage: Callable[..., Mapping[str, Any]] = disk_usage_summary,
) -> dict[str, Any]:
    now = now or _now()
    reservation_id = str(reservation_id or "").strip()
    requested_bytes = max(0, int(requested_bytes))
    if not reservation_id or not str(owner or "").strip():
        return {"schema": SCHEMA, "ok": False, "decision": "invalid", "error": "reservation_id_and_owner_required"}
    if int(ttl_seconds) <= 0:
        return {"schema": SCHEMA, "ok": False, "decision": "invalid", "error": "ttl_must_be_positive", "reservation_id": reservation_id}
    target = Path(target).expanduser()
    normalized_route_metadata = dict(route_metadata) if isinstance(route_metadata, Mapping) else None
    with _lock(root) as handle:
        try:
            expired = _expire_unlocked(root, now)
            pruned = _prune_terminal_unlocked(root)
            records = _records_unlocked(root)
            state_errors = _state_errors_unlocked(root)
            if state_errors:
                return {
                    "schema": SCHEMA,
                    "ok": False,
                    "decision": "blocked",
                    "reservation_id": reservation_id,
                    "error": "reservation_state_invalid",
                    "state_errors": state_errors[:200],
                    "expired_count": len(expired),
                }
            # Do not derive the accounting bucket before taking the shared
            # lock.  A mount can change while waiting for the lock; archive
            # route identity and capacity must use this same post-lock device
            # snapshot or a lease can be counted against the wrong filesystem.
            filesystem_device = _route_filesystem_device(target, normalized_route_metadata)
            if filesystem_device is None:
                return {
                    "schema": SCHEMA,
                    "ok": False,
                    "decision": "blocked",
                    "reservation_id": reservation_id,
                    "error": (
                        "route_filesystem_identity_mismatch"
                        if normalized_route_metadata
                        else "target_filesystem_unavailable"
                    ),
                }
            filesystem_key = _filesystem_key_for_device(filesystem_device)
            existing = next((item for item in records if item.get("reservation_id") == reservation_id), None)
            if existing and existing.get("active") is True:
                same_request = (
                    int(existing.get("requested_bytes") or 0) == requested_bytes
                    and str(existing.get("target") or "") == str(target)
                    and str(existing.get("owner") or "") == str(owner)
                    and existing.get("route_metadata") == normalized_route_metadata
                )
                if same_request:
                    if hold_until_terminal and existing.get("hold_until_terminal") is not True:
                        existing["hold_until_terminal"] = True
                        existing["status"] = "active_terminal_hold"
                        if execution_identity and not existing.get("execution_identity"):
                            existing["execution_identity"] = str(execution_identity)[:240]
                        _atomic_write(_reservation_path(root, reservation_id), existing)
                    return {
                        "schema": SCHEMA,
                        "ok": True,
                        "decision": "already_reserved",
                        "reservation": existing,
                        "expired_count": len(expired),
                        "pruned_count": len(pruned),
                    }
                return {"schema": SCHEMA, "ok": False, "decision": "conflict", "reservation_id": reservation_id, "error": "active_reservation_id_conflict"}

            usage = _capacity(target, disk_usage=disk_usage)
            # Capacity is path-based, so ensure the path still names the same
            # device after the capacity read.  This closes a remount window
            # without retaining a pre-lock key or silently oversubscribing a
            # route-specific namespace.
            capacity_device = _target_filesystem_device(target)
            if capacity_device != filesystem_device:
                return {
                    "schema": SCHEMA,
                    "ok": False,
                    "decision": "blocked",
                    "reservation_id": reservation_id,
                    "error": "target_filesystem_changed_during_capacity",
                    "filesystem_key": filesystem_key,
                }
            available = usage.get("available_to_user_bytes")
            if not isinstance(available, int):
                available = usage.get("free_bytes") if isinstance(usage.get("free_bytes"), int) else None
            active_reserved = sum(
                max(0, int(item.get("requested_bytes") or 0))
                for item in records
                if item.get("active") is True and str(item.get("filesystem_key") or "") == filesystem_key
            )
            available_after = int(available) - active_reserved - requested_bytes if isinstance(available, int) else None
            if available_after is None:
                return {"schema": SCHEMA, "ok": False, "decision": "blocked", "reservation_id": reservation_id, "error": "capacity_unavailable", "usage": usage}
            if available_after < max(0, int(min_free_after)):
                return {
                    "schema": SCHEMA,
                    "ok": False,
                    "decision": "blocked",
                    "reservation_id": reservation_id,
                    "error": "available_capacity_after_reservations_below_policy",
                    "usage": usage,
                    "active_reserved_bytes": active_reserved,
                    "available_after_bytes": available_after,
                }
            expires = now + dt.timedelta(seconds=int(ttl_seconds))
            record = {
                "schema": SCHEMA,
                "version": 1,
                "reservation_id": reservation_id,
                "kind": str(kind or "unknown"),
                "requested_bytes": requested_bytes,
                "target": str(target),
                "owner": str(owner),
                "issued_at": _iso(now),
                "expires_at": _iso(expires),
                "active": True,
                "status": "active",
                "filesystem_key": filesystem_key,
                "route_metadata": normalized_route_metadata,
                "hold_until_terminal": bool(hold_until_terminal),
                "execution_identity": str(execution_identity)[:240] if execution_identity else None,
                "capacity": {
                    "available_to_user_bytes": available,
                    "active_reserved_bytes_before": active_reserved,
                    "available_after_bytes": available_after,
                    "basis": "available_to_user_bytes" if usage.get("available_to_user_bytes") is not None else "free_bytes",
                },
                "automatic_write": False,
            }
            _atomic_write(_reservation_path(root, reservation_id), record)
            return {
                "schema": SCHEMA,
                "ok": True,
                "decision": "reserved",
                "reservation": record,
                "expired_count": len(expired),
                "pruned_count": len(pruned),
            }
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def release_reservation(
    root: Path,
    reservation_id: str,
    *,
    owner: str | None = None,
    execution_identity: str | None = None,
    now: dt.datetime | None = None,
    terminal_retention_limit: int = TERMINAL_RETENTION_LIMIT,
) -> dict[str, Any]:
    now = now or _now()
    with _lock(root) as handle:
        try:
            _expire_unlocked(root, now)
            pruned = _prune_terminal_unlocked(
                root,
                retention_limit=terminal_retention_limit,
            )
            path = _reservation_path(root, reservation_id)
            record = _read(path)
            if record is None:
                return {"schema": SCHEMA, "ok": False, "decision": "missing", "reservation_id": reservation_id, "error": "reservation_not_found"}
            if owner is not None and str(record.get("owner") or "") != str(owner):
                return {
                    "schema": SCHEMA,
                    "ok": False,
                    "decision": "blocked",
                    "reservation_id": reservation_id,
                    "error": "reservation_owner_mismatch",
                }
            if execution_identity is not None and str(record.get("execution_identity") or "") != str(execution_identity):
                return {
                    "schema": SCHEMA,
                    "ok": False,
                    "decision": "blocked",
                    "reservation_id": reservation_id,
                    "error": "reservation_execution_identity_mismatch",
                }
            if record.get("active") is not True:
                return {
                    "schema": SCHEMA,
                    "ok": True,
                    "decision": "already_released",
                    "reservation_id": reservation_id,
                    "reservation": record,
                    "pruned_count": len(pruned),
                }
            record["active"] = False
            record["status"] = "released"
            record["released_at"] = _iso(now)
            record["hold_until_terminal"] = False
            _atomic_write(path, record)
            pruned.extend(
                _prune_terminal_unlocked(
                    root,
                    retention_limit=terminal_retention_limit,
                )
            )
            return {
                "schema": SCHEMA,
                "ok": True,
                "decision": "released",
                "reservation_id": reservation_id,
                "reservation": record,
                "pruned_count": len(pruned),
            }
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def expire_reservations(
    root: Path,
    *,
    now: dt.datetime | None = None,
    terminal_retention_limit: int = TERMINAL_RETENTION_LIMIT,
) -> dict[str, Any]:
    now = now or _now()
    with _lock(root) as handle:
        try:
            expired = _expire_unlocked(root, now)
            pruned = _prune_terminal_unlocked(
                root,
                retention_limit=terminal_retention_limit,
            )
            state_errors = _state_errors_unlocked(root)
            deferred = _expiry_deferred_unlocked(root, now)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return {
        "schema": SCHEMA,
        "ok": not state_errors,
        "decision": "expired" if not state_errors else "blocked",
        "generated_at": _iso(now),
        "expired": expired,
        "expired_count": len(expired),
        "expiry_deferred_count": len(deferred),
        "expiry_deferred": deferred,
        "pruned_count": len(pruned),
        "terminal_retention_limit": max(1, int(terminal_retention_limit)),
        "state_errors": state_errors[:200],
    }

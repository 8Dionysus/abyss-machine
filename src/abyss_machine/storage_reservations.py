"""Small, explicit write-capacity reservations for host-owned storage routes.

Reservations are accounting leases only.  They do not create files, hold
filesystem space, or grant permission to mutate a target.  The caller must
still run write-preflight and its owner-specific hooks immediately before the
write.  A single flock-protected directory makes acquire/release/expiry
updates atomic for concurrent user processes without introducing a resident
resource controller.
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
        return f"dev:{int(anchor.stat().st_dev)}"
    except OSError:
        return f"anchor:{anchor}"


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
        record["active"] = False
        record["status"] = "expired"
        record["expired_at"] = _iso(now)
        _atomic_write(_reservation_path(root, str(record.get("reservation_id") or "")), record)
        expired.append(record)
    return expired


def _capacity(
    target: Path,
    *,
    disk_usage: Callable[..., Mapping[str, Any]] = disk_usage_summary,
) -> dict[str, Any]:
    try:
        return dict(disk_usage(target, statvfs=os.statvfs))
    except TypeError:
        return dict(disk_usage(target))


def list_reservations(root: Path, *, now: dt.datetime | None = None) -> dict[str, Any]:
    now = now or _now()
    with _lock(root) as handle:
        try:
            expired = _expire_unlocked(root, now)
            records = _records_unlocked(root)
            state_errors = _state_errors_unlocked(root)
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
    filesystem_key = _filesystem_key(target)
    with _lock(root) as handle:
        try:
            expired = _expire_unlocked(root, now)
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
            existing = next((item for item in records if item.get("reservation_id") == reservation_id), None)
            if existing and existing.get("active") is True:
                same_request = (
                    int(existing.get("requested_bytes") or 0) == requested_bytes
                    and str(existing.get("target") or "") == str(target)
                    and str(existing.get("owner") or "") == str(owner)
                )
                if same_request:
                    return {"schema": SCHEMA, "ok": True, "decision": "already_reserved", "reservation": existing, "expired_count": len(expired)}
                return {"schema": SCHEMA, "ok": False, "decision": "conflict", "reservation_id": reservation_id, "error": "active_reservation_id_conflict"}

            usage = _capacity(target, disk_usage=disk_usage)
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
                "capacity": {
                    "available_to_user_bytes": available,
                    "active_reserved_bytes_before": active_reserved,
                    "available_after_bytes": available_after,
                    "basis": "available_to_user_bytes" if usage.get("available_to_user_bytes") is not None else "free_bytes",
                },
                "automatic_write": False,
            }
            _atomic_write(_reservation_path(root, reservation_id), record)
            return {"schema": SCHEMA, "ok": True, "decision": "reserved", "reservation": record, "expired_count": len(expired)}
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def release_reservation(root: Path, reservation_id: str, *, now: dt.datetime | None = None) -> dict[str, Any]:
    now = now or _now()
    with _lock(root) as handle:
        try:
            _expire_unlocked(root, now)
            path = _reservation_path(root, reservation_id)
            record = _read(path)
            if record is None:
                return {"schema": SCHEMA, "ok": False, "decision": "missing", "reservation_id": reservation_id, "error": "reservation_not_found"}
            if record.get("active") is not True:
                return {"schema": SCHEMA, "ok": True, "decision": "already_released", "reservation_id": reservation_id, "reservation": record}
            record["active"] = False
            record["status"] = "released"
            record["released_at"] = _iso(now)
            _atomic_write(path, record)
            return {"schema": SCHEMA, "ok": True, "decision": "released", "reservation_id": reservation_id, "reservation": record}
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def expire_reservations(root: Path, *, now: dt.datetime | None = None) -> dict[str, Any]:
    now = now or _now()
    with _lock(root) as handle:
        try:
            expired = _expire_unlocked(root, now)
            state_errors = _state_errors_unlocked(root)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return {
        "schema": SCHEMA,
        "ok": not state_errors,
        "decision": "expired" if not state_errors else "blocked",
        "generated_at": _iso(now),
        "expired": expired,
        "expired_count": len(expired),
        "state_errors": state_errors[:200],
    }

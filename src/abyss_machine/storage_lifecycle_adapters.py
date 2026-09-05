from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import os
import re
from contextlib import contextmanager
from pathlib import Path
import secrets
import shutil
import stat
from typing import Any, Iterator, Mapping

from . import storage_candidate_adapters
from . import storage_lifecycle_contracts as contracts
from . import resource_adapters
from . import storage_process_probe


LEASE_TOKEN_PREFIX = "lease-"
DEFAULT_REAP_SCAN_LIMIT = 8
MAX_REAP_SCAN_LIMIT = 32
REAPER_STATE_SCHEMA = "abyss_machine_storage_workspace_reaper_state_v1"


def _new_lease_token() -> str:
    """Mint a CLI-safe capability without changing its random payload."""
    return f"{LEASE_TOKEN_PREFIX}{secrets.token_urlsafe(32)}"


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def now_iso() -> str:
    return now_utc().astimezone().isoformat(timespec="seconds")


def atomic_write_json(path: Path, document: Mapping[str, Any], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(6)}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, mode)
    os.replace(temporary, path)


@contextmanager
def registry_lock(root: Path) -> Iterator[None]:
    root.mkdir(parents=True, exist_ok=True)
    fd = os.open(root / ".lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


@contextmanager
def workspace_lock(root: Path, workspace_id: str, *, blocking: bool = True) -> Iterator[bool]:
    locks = root / "locks"
    locks.mkdir(parents=True, exist_ok=True)
    fd = os.open(locks / f"{workspace_id}.lock", os.O_RDWR | os.O_CREAT, 0o600)
    acquired = False
    try:
        operation = fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB
        try:
            fcntl.flock(fd, operation)
            acquired = True
        except BlockingIOError:
            pass
        yield acquired
    finally:
        if acquired:
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def record_path(root: Path, workspace_id: str) -> Path:
    return root / "workspaces" / f"{workspace_id}.json"


def callback_path(root: Path, workspace_id: str) -> Path:
    return root / "callbacks" / f"{workspace_id}.json"


def receipt_path(root: Path, workspace_id: str) -> Path:
    stamp = now_utc().strftime("%Y%m%dT%H%M%S.%fZ")
    return root / "receipts" / f"{workspace_id}-{stamp}.json"


def execution_journal_path(root: Path, workspace_id: str) -> Path:
    return root / "executions" / f"{workspace_id}.json"


def reaper_state_path(root: Path) -> Path:
    """Return the owner-local cursor state beside the lifecycle registry."""
    return root / "reaper-state.json"


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _read_reaper_state(root: Path) -> dict[str, Any]:
    path = reaper_state_path(root)
    if not path.exists():
        return {
            "cursor": None,
            "revision": 0,
            "status": "missing",
            "reason": "state_missing",
        }
    value = read_json(path)
    if value is None:
        return {
            "cursor": None,
            "revision": 0,
            "status": "invalid",
            "reason": "state_unreadable",
        }
    if value.get("schema") != REAPER_STATE_SCHEMA:
        return {
            "cursor": None,
            "revision": 0,
            "status": "invalid",
            "reason": "state_schema_mismatch",
        }
    if "cursor" not in value:
        return {
            "cursor": None,
            "revision": 0,
            "status": "invalid",
            "reason": "state_cursor_missing",
        }
    cursor = value.get("cursor")
    revision = value.get("revision", 0)
    if cursor is not None and (not isinstance(cursor, str) or not cursor):
        return {
            "cursor": None,
            "revision": 0,
            "status": "invalid",
            "reason": "state_cursor_invalid",
        }
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        return {
            "cursor": None,
            "revision": 0,
            "status": "invalid",
            "reason": "state_revision_invalid",
        }
    return {
        "cursor": cursor,
        "revision": revision,
        "status": "valid",
        "reason": None,
    }


def _rotated_records(
    records: list[dict[str, Any]],
    cursor: str | None,
) -> tuple[list[dict[str, Any]], str | None]:
    ordered: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for record in records:
        workspace_id = str(record.get("workspace_id") or "")
        if workspace_id and workspace_id not in seen_ids:
            ordered.append(record)
            seen_ids.add(workspace_id)
    if not ordered or cursor is None:
        return ordered, None
    for index, record in enumerate(ordered):
        if str(record.get("workspace_id") or "") == cursor:
            return ordered[index + 1 :] + ordered[: index + 1], None
    return ordered, "cursor_missing"


def load_records(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted((root / "workspaces").glob("*.json")):
        value = read_json(path)
        if value is not None:
            records.append(value)
    return records


def _mount_boundary_error(
    item: Path,
    root: Path,
    root_device: int,
    mount_points: set[str],
    item_stat: os.stat_result,
) -> str | None:
    """Return a reason when an entry would cross a mount boundary.

    ``st_dev`` catches ordinary cross-device mounts.  The mountpoint list is
    also required because bind mounts can report the same device as their
    parent.  The root itself is allowed unless it is a non-root mountpoint;
    nested mountpoints are always rejected before they can be traversed.
    """
    item_name = os.path.normpath(str(item))
    root_name = os.path.normpath(str(root))
    if item_name != root_name and item_name in mount_points:
        return "nested_mount_boundary"
    if item_stat.st_dev != root_device:
        return "cross_device_boundary"
    return None


def _fingerprint_failure(
    *,
    max_entries: int,
    errors: list[dict[str, str]],
    content_hashed: bool = False,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "digest": None,
        "complete": False,
        "entries": 0,
        "max_entries": max_entries,
        "truncated": False,
        "errors": errors[:20],
    }
    if content_hashed:
        result["content_hashed"] = True
    else:
        result["rename_stable_root_identity"] = True
    return result


def _restore_walk_groups(
    path: Path, original_root: Path | None, current_path: Path,
    dirnames: list[str], filenames: list[str], errors: list[dict[str, str]],
) -> None:
    if original_root is not None and original_root != path:
        # os.walk groups links by the target's type. A self-absolute
        # directory link becomes broken after detach, changing the
        # legacy digest order despite unchanged lstat/readlink bytes.
        # Reconstruct only that grouping in the recorded namespace;
        # never traverse links or replace the original sealed digest.
        original_dirs = set(dirnames)
        for name in [*dirnames, *filenames]:
            item = current_path / name
            try:
                if not item.is_symlink():
                    continue
                link = Path(os.readlink(item))
                logical_parent = original_root / current_path.relative_to(path)
                target = Path(os.path.normpath(str(link if link.is_absolute() else logical_parent / link)))
                try:
                    relative_target = target.relative_to(original_root)
                except ValueError:
                    continue
                if (path / relative_target).is_dir():
                    original_dirs.add(name)
                else:
                    original_dirs.discard(name)
            except OSError as exc:
                errors.append({"path": str(item), "error": str(exc)})
        names = set(dirnames) | set(filenames)
        dirnames[:] = sorted(original_dirs)
        filenames[:] = sorted(names - original_dirs)


def workspace_identity_fingerprint(
    path: Path, *, max_entries: int = 100_000, original_root: Path | None = None,
) -> dict[str, Any]:
    digest = hashlib.sha256()
    entries = 0
    errors: list[dict[str, str]] = []
    truncated = False

    try:
        root_stat = path.lstat()
    except OSError as exc:
        return _fingerprint_failure(
            max_entries=max_entries,
            errors=[{"path": str(path), "error": str(exc)}],
        )
    mount_points, mount_errors = _mount_points_snapshot()
    if mount_points is None:
        return _fingerprint_failure(
            max_entries=max_entries,
            errors=[{"path": str(path), "error": error} for error in mount_errors],
        )
    root_name = os.path.normpath(str(path))
    if root_name != "/" and root_name in mount_points:
        errors.append({"path": str(path), "error": "workspace_root_mount_boundary"})

    def include(item: Path, relative: str, *, root: bool = False) -> tuple[bool, os.stat_result | None]:
        nonlocal entries, truncated
        if entries >= max(1, max_entries):
            truncated = True
            return False, None
        try:
            item_stat = item.lstat()
        except OSError as exc:
            errors.append({"path": str(item), "error": str(exc)})
            return False, None
        boundary = _mount_boundary_error(item, path, root_stat.st_dev, mount_points, item_stat)
        if boundary is not None:
            errors.append({"path": str(item), "error": boundary})
            return False, item_stat
        row = [
            relative,
            stat.S_IFMT(item_stat.st_mode),
            item_stat.st_dev,
            item_stat.st_ino,
            item_stat.st_mode,
            item_stat.st_size,
            item_stat.st_mtime_ns,
        ]
        if not root:
            row.append(item_stat.st_ctime_ns)
        if stat.S_ISLNK(item_stat.st_mode):
            try:
                row.append(os.readlink(item))
            except OSError as exc:
                errors.append({"path": str(item), "error": str(exc)})
        digest.update((json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode())
        entries += 1
        return True, item_stat

    _included, _ = include(path, ".", root=True)
    if stat.S_ISDIR(root_stat.st_mode) and not stat.S_ISLNK(root_stat.st_mode):
        def onerror(exc: OSError) -> None:
            errors.append({"path": str(getattr(exc, "filename", path)), "error": str(exc)})

        for current, dirnames, filenames in os.walk(path, topdown=True, followlinks=False, onerror=onerror):
            current_path = Path(current)
            _restore_walk_groups(path, original_root, current_path, dirnames, filenames, errors)
            dirnames.sort()
            filenames.sort()
            for name in list(dirnames):
                included, child_stat = include(
                    current_path / name,
                    str((current_path / name).relative_to(path)),
                )
                if (not included or child_stat is None
                        or not stat.S_ISDIR(child_stat.st_mode)
                        or stat.S_ISLNK(child_stat.st_mode)):
                    dirnames.remove(name)
                if truncated:
                    break
            if truncated:
                break
            for name in filenames:
                include(
                    current_path / name,
                    str((current_path / name).relative_to(path)),
                )
                if truncated:
                    break
            if truncated:
                break
    return {
        "digest": digest.hexdigest() if entries else None,
        "complete": bool(entries and not errors and not truncated),
        "entries": entries,
        "max_entries": max_entries,
        "truncated": truncated,
        "errors": errors[:20],
        "rename_stable_root_identity": True,
    }


def workspace_content_fingerprint(
    path: Path, *, max_entries: int = 100_000, original_root: Path | None = None,
) -> dict[str, Any]:
    digest = hashlib.sha256()
    entries = 0
    errors: list[dict[str, str]] = []
    truncated = False

    try:
        root_stat = path.lstat()
    except OSError as exc:
        return _fingerprint_failure(
            max_entries=max_entries,
            errors=[{"path": str(path), "error": str(exc)}],
            content_hashed=True,
        )
    mount_points, mount_errors = _mount_points_snapshot()
    if mount_points is None:
        return _fingerprint_failure(
            max_entries=max_entries,
            errors=[{"path": str(path), "error": error} for error in mount_errors],
            content_hashed=True,
        )
    root_name = os.path.normpath(str(path))
    if root_name != "/" and root_name in mount_points:
        errors.append({"path": str(path), "error": "workspace_root_mount_boundary"})

    def include(item: Path, relative: str) -> tuple[bool, os.stat_result | None]:
        nonlocal entries, truncated
        if entries >= max(1, max_entries):
            truncated = True
            return False, None
        try:
            item_stat = item.lstat()
            boundary = _mount_boundary_error(item, path, root_stat.st_dev, mount_points, item_stat)
            if boundary is not None:
                errors.append({"path": str(item), "error": boundary})
                return False, item_stat
            kind = stat.S_IFMT(item_stat.st_mode)
            stable_size = item_stat.st_size if stat.S_ISREG(item_stat.st_mode) or stat.S_ISLNK(item_stat.st_mode) else None
            digest.update((json.dumps([relative, kind, item_stat.st_mode, stable_size], separators=(",", ":")) + "\n").encode())
            if stat.S_ISREG(item_stat.st_mode):
                with item.open("rb") as handle:
                    while chunk := handle.read(1024 * 1024):
                        digest.update(chunk)
            elif stat.S_ISLNK(item_stat.st_mode):
                digest.update(os.readlink(item).encode("utf-8", errors="surrogateescape"))
            elif not stat.S_ISDIR(item_stat.st_mode):
                errors.append({"path": str(item), "error": "unsupported_special_file"})
        except OSError as exc:
            errors.append({"path": str(item), "error": str(exc)})
            entries += 1
            return False, None
        entries += 1
        return True, item_stat

    _included, _ = include(path, ".")
    if stat.S_ISDIR(root_stat.st_mode) and not stat.S_ISLNK(root_stat.st_mode):
        def onerror(exc: OSError) -> None:
            errors.append({"path": str(getattr(exc, "filename", path)), "error": str(exc)})

        for current, dirnames, filenames in os.walk(path, topdown=True, followlinks=False, onerror=onerror):
            current_path = Path(current)
            _restore_walk_groups(path, original_root, current_path, dirnames, filenames, errors)
            dirnames.sort()
            filenames.sort()
            for name in list(dirnames):
                included, child_stat = include(
                    current_path / name,
                    str((current_path / name).relative_to(path)),
                )
                if (not included or child_stat is None
                        or not stat.S_ISDIR(child_stat.st_mode)
                        or stat.S_ISLNK(child_stat.st_mode)):
                    dirnames.remove(name)
                if truncated:
                    break
            if truncated:
                break
            for name in filenames:
                include(
                    current_path / name,
                    str((current_path / name).relative_to(path)),
                )
                if truncated:
                    break
            if truncated:
                break
    return {
        "digest": digest.hexdigest() if entries else None,
        "complete": bool(entries and not errors and not truncated),
        "entries": entries,
        "max_entries": max_entries,
        "truncated": truncated,
        "errors": errors[:20],
        "content_hashed": True,
    }


def register_workspace(
    root: Path,
    *,
    owner: str,
    workspace: Path,
    unit: str | None,
    lease_seconds: int = 300,
    create: bool = True,
    now_time: dt.datetime | None = None,
) -> dict[str, Any]:
    workspace = workspace.expanduser().absolute()
    if not owner.strip():
        return {"ok": False, "errors": ["owner_required"]}
    if workspace.exists() and not workspace.is_dir():
        return {"ok": False, "errors": ["workspace_must_be_directory"]}
    token = _new_lease_token()
    nonce = secrets.token_hex(16)
    launcher_created = False
    if not workspace.exists() and create:
        workspace.mkdir(mode=0o700, parents=True, exist_ok=False)
        launcher_created = True
    opened = now_time or now_utc()
    provisional_id = contracts.workspace_id(owner=owner, path=str(workspace), nonce=nonce)
    callback = callback_path(root, provisional_id)
    record = contracts.open_workspace(
        owner=owner,
        path=str(workspace),
        nonce=nonce,
        lease_token_sha256=hashlib.sha256(token.encode()).hexdigest(),
        opened_at=opened.astimezone().isoformat(timespec="seconds"),
        lease_expires_at=(opened + dt.timedelta(seconds=max(1, lease_seconds))).astimezone().isoformat(timespec="seconds"),
        unit=unit,
        launcher_created=launcher_created,
        callback_path=str(callback),
    )
    if not record["valid"]:
        return {"ok": False, "record": record, "errors": record["errors"]}
    try:
        with registry_lock(root):
            atomic_write_json(record_path(root, record["workspace_id"]), record)
    except OSError as exc:
        if launcher_created:
            try:
                workspace.rmdir()
            except OSError:
                pass
        return {"ok": False, "record": record, "errors": [f"registry_write_failed:{exc}"]}
    return {
        "ok": True,
        "record": record,
        "lease_token": token,
        "environment": {
            "ABYSS_MANAGED_WORKSPACE_ID": record["workspace_id"],
            "ABYSS_MANAGED_WORKSPACE_PATH": record["path"],
            "ABYSS_MANAGED_WORKSPACE_DISPOSITION": str(callback),
        },
    }


def renew_registered_workspace(
    root: Path,
    *,
    workspace_id: str,
    lease_token: str,
    lease_seconds: int = 300,
    now_time: dt.datetime | None = None,
) -> dict[str, Any]:
    """Renew one managed workspace lease while holding its lifecycle locks."""
    if not isinstance(workspace_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", workspace_id):
        return {"ok": False, "errors": ["workspace_id_invalid"]}
    try:
        duration = max(1, int(lease_seconds))
    except (TypeError, ValueError):
        return {"ok": False, "errors": ["lease_seconds_invalid"]}
    resolved_now = now_time or now_utc()
    if resolved_now.tzinfo is None:
        return {"ok": False, "errors": ["timezone_aware_time_required"]}
    updated_at = resolved_now.astimezone(dt.timezone.utc).isoformat(timespec="seconds")
    expires_at = (resolved_now + dt.timedelta(seconds=duration)).astimezone(dt.timezone.utc).isoformat(timespec="seconds")
    path = record_path(root, workspace_id)
    with workspace_lock(root, workspace_id) as acquired:
        if not acquired:
            return {"ok": False, "errors": ["workspace_lock_unavailable"]}
        with registry_lock(root):
            record = read_json(path)
            if record is None:
                return {"ok": False, "errors": ["workspace_record_not_found"]}
            result = contracts.renew_lease(
                record,
                token=lease_token,
                expires_at=expires_at,
                updated_at=updated_at,
            )
            if result.get("ok") is True:
                atomic_write_json(path, result["record"])
            return result


def seal_registered_workspace(
    root: Path,
    *,
    workspace_id: str,
    lease_token: str,
    max_entries: int = 100_000,
) -> dict[str, Any]:
    path = record_path(root, workspace_id)
    with workspace_lock(root, workspace_id) as acquired:
        if not acquired:
            return {"ok": False, "errors": ["workspace_lock_unavailable"]}
        with registry_lock(root):
            record = read_json(path)
            if record is None:
                return {"ok": False, "errors": ["workspace_record_not_found"]}
        workspace = Path(str(record.get("path") or ""))
        fingerprint = workspace_identity_fingerprint(workspace, max_entries=max_entries)
        physical, physical_evidence = storage_candidate_adapters.physical_size_bytes(workspace)
        if physical is None:
            return {"ok": False, "errors": ["physical_size_unavailable"], "evidence": physical_evidence}
        result = contracts.seal_workspace(
            record,
            token=lease_token,
            fingerprint=fingerprint,
            physical_bytes=physical,
            sealed_at=now_iso(),
        )
        atomic_write_json(path, result["record"])
        return result


def consume_owner_callback(
    root: Path,
    *,
    workspace_id: str,
    grace_seconds: int = 60,
) -> dict[str, Any]:
    path = record_path(root, workspace_id)
    callback = callback_path(root, workspace_id)
    with workspace_lock(root, workspace_id) as acquired:
        if not acquired:
            return {"ok": False, "errors": ["workspace_lock_unavailable"]}
        with registry_lock(root):
            record = read_json(path)
            if record is None:
                return {"ok": False, "errors": ["workspace_record_not_found"]}
        owner_value = read_json(callback) or {"decision": "UNKNOWN", "plan": {}}
        normalized = contracts.disposition_document(owner_value)
        if normalized["decision"] in {"KEEP", "UNKNOWN"}:
            record["disposition"] = {**normalized, "released": False}
            record["updated_at"] = now_iso()
            atomic_write_json(path, record)
            return {"ok": True, "released": False, "record": record}
        result = contracts.release_workspace(
            record,
            disposition=normalized,
            released_at=now_iso(),
            grace_seconds=grace_seconds,
        )
        atomic_write_json(path, result["record"])
        return {**result, "released": result["ok"]}


def finalize_managed_workspace(
    root: Path,
    lifecycle: Mapping[str, Any],
    *,
    grace_seconds: int = 60,
) -> dict[str, Any]:
    workspace_id = str(lifecycle.get("workspace_id") or "")
    lease_token = str(lifecycle.get("lease_token") or "")
    sealed = seal_registered_workspace(
        root,
        workspace_id=workspace_id,
        lease_token=lease_token,
    )
    if not sealed.get("ok"):
        return {"ok": False, "workspace_id": workspace_id, "sealed": sealed, "released": False}
    callback = consume_owner_callback(
        root,
        workspace_id=workspace_id,
        grace_seconds=grace_seconds,
    )
    return {
        "ok": bool(callback.get("ok")),
        "workspace_id": workspace_id,
        "sealed": True,
        "released": callback.get("released") is True,
        "state": callback.get("record", {}).get("state") if isinstance(callback.get("record"), Mapping) else "sealed",
        "disposition": callback.get("record", {}).get("disposition") if isinstance(callback.get("record"), Mapping) else None,
        "errors": callback.get("errors") or [],
    }


def _path_has_live_refs(path: Path) -> dict[str, Any]:
    text = str(path)
    try:
        process_result = storage_process_probe.owner_process_references([text])
        process_value = process_result.get(text, {}) if isinstance(process_result, Mapping) else {}
        process = process_value if isinstance(process_value, Mapping) else {"checked": False, "active": False, "errors": ["invalid_probe"]}
    except Exception as exc:  # a failed safety probe must never authorize cleanup
        process = {"checked": False, "active": False, "refs": [], "errors": [str(exc)]}
    try:
        mount_value = storage_candidate_adapters.mount_references(path)
        mount = mount_value if isinstance(mount_value, Mapping) else {"checked": False, "active": False, "errors": ["invalid_probe"]}
    except Exception as exc:  # a failed safety probe must never authorize cleanup
        mount = {"checked": False, "active": False, "refs": [], "errors": [str(exc)]}

    def checked(probe: Any) -> bool:
        return (
            isinstance(probe, Mapping)
            and probe.get("checked") is True
            and not probe.get("errors")
            and not probe.get("error")
        )

    probe_errors: list[Any] = []
    for probe_name, probe in (("process", process), ("mount", mount)):
        if not checked(probe):
            probe_errors.append({"probe": probe_name, "errors": probe.get("errors") if isinstance(probe, Mapping) else ["invalid_probe"]})
    return {
        "active": process.get("active") is True or mount.get("active") is True,
        "checked": checked(process) and checked(mount),
        "errors": probe_errors,
        "process": process,
        "mount": mount,
    }


def _atomic_detach(workspace: Path, workspace_id: str, expected_inode: int) -> Path:
    tombstone = workspace.parent / f".abyss-released-{workspace_id}"
    if tombstone.exists():
        raise FileExistsError(f"tombstone exists: {tombstone}")
    current = workspace.stat(follow_symlinks=False)
    if current.st_ino != expected_inode:
        raise RuntimeError("workspace inode drift before detach")
    os.rename(workspace, tombstone)
    if tombstone.stat(follow_symlinks=False).st_ino != expected_inode:
        raise RuntimeError("workspace inode drift during detach")
    return tombstone


def _read_mountinfo() -> str:
    return Path("/proc/self/mountinfo").read_text()


def _decode_mountinfo_path(value: str) -> str:
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match.group(1), 8)), value)


def _mount_points_snapshot() -> tuple[set[str] | None, list[str]]:
    """Read mountpoints once and fail closed if the snapshot is unusable."""
    try:
        raw = _read_mountinfo()
    except (OSError, TypeError, ValueError) as exc:
        return None, [f"mountinfo_unavailable:{exc}"]
    if not isinstance(raw, str) or not raw.strip():
        return None, ["mountinfo_empty"]
    points: set[str] = set()
    for line_number, line in enumerate(raw.splitlines(), start=1):
        fields = line.split()
        if not fields:
            continue
        try:
            separator = fields.index("-")
        except ValueError:
            return None, [f"mountinfo_invalid_line:{line_number}"]
        if separator < 6 or separator + 2 >= len(fields) or len(fields) < 6:
            return None, [f"mountinfo_invalid_line:{line_number}"]
        mountpoint = _decode_mountinfo_path(fields[4])
        if not mountpoint.startswith("/"):
            return None, [f"mountinfo_invalid_mountpoint:{line_number}"]
        points.add(os.path.normpath(mountpoint))
    if not points:
        return None, ["mountinfo_empty"]
    return points, []


def _safe_receipt_path(root: Path, workspace_id: str, value: Any) -> tuple[Path | None, str | None]:
    candidate = Path(str(value or ""))
    receipts_root = (root / "receipts").absolute()
    if not candidate.is_absolute():
        return None, "execution_receipt_path_not_absolute"
    candidate = candidate.absolute()
    if candidate.parent != receipts_root:
        return None, "execution_receipt_path_outside_receipts"
    expected_name = re.fullmatch(
        rf"{re.escape(workspace_id)}-\d{{8}}T\d{{6}}\.\d{{6}}Z\.json",
        candidate.name,
    )
    if expected_name is None:
        return None, "execution_receipt_path_invalid"
    for parent in (receipts_root, candidate):
        try:
            if parent.is_symlink():
                return None, "execution_receipt_path_symlink"
        except OSError:
            return None, "execution_receipt_path_unavailable"
    return candidate, None


def _validated_execution_receipt(
    root: Path,
    workspace_id: str,
    expected_digest: Any,
    journal: Mapping[str, Any],
    decision: Any,
    archive_target: Path | None,
) -> tuple[dict[str, Any] | None, Path | None, list[str]]:
    raw_receipt = journal.get("receipt")
    if not isinstance(raw_receipt, Mapping):
        return None, None, ["execution_receipt_missing"]
    receipt = dict(raw_receipt)
    required = (
        receipt.get("schema") == "abyss_machine_storage_workspace_receipt_v1",
        receipt.get("workspace_id") == workspace_id,
        receipt.get("seal_fingerprint_digest") == expected_digest,
        receipt.get("action") == str(decision).lower(),
        receipt.get("valid") is True,
    )
    if not all(required):
        return None, None, ["execution_receipt_identity_mismatch"]
    persisted, path_error = _safe_receipt_path(root, workspace_id, journal.get("receipt_path"))
    if persisted is None:
        return None, None, [path_error or "execution_receipt_path_invalid"]
    if archive_target is not None:
        if str(receipt.get("archive_target") or "") != str(archive_target):
            return None, None, ["execution_receipt_archive_target_mismatch"]
        binding = receipt.get("archive_mount_binding")
        digest = receipt.get("archive_content_digest")
        if not isinstance(binding, Mapping) or not isinstance(binding.get("identity"), Mapping):
            return None, None, ["execution_receipt_archive_binding_missing"]
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            return None, None, ["execution_receipt_archive_digest_missing"]
    elif receipt.get("archive_target") not in {None, ""}:
        return None, None, ["execution_receipt_archive_target_unexpected"]
    return receipt, persisted, []


def _persist_execution_receipt(path: Path, receipt: Mapping[str, Any]) -> bool:
    try:
        if path.exists():
            return read_json(path) == dict(receipt)
        atomic_write_json(path, receipt)
        return True
    except OSError:
        return False


def _verify_archive_state(
    target: Path,
    required_mount: Path,
    expected_binding: Mapping[str, Any] | None,
    expected_digest: Any,
    *,
    max_entries: int,
    original_root: Path,
) -> dict[str, Any]:
    expected_identity = expected_binding.get("identity") if isinstance(expected_binding, Mapping) else None
    if not isinstance(expected_identity, Mapping):
        return {"ok": False, "reasons": ["archive_binding_identity_missing"]}
    first = archive_mount_binding(target, required_mount)
    if not first.get("ok"):
        return {"ok": False, "reasons": ["archive_mount_unavailable", *first.get("reasons", [])], "archive_binding": first}
    if first.get("identity") != dict(expected_identity):
        return {"ok": False, "reasons": ["archive_mount_changed"], "archive_binding": first}
    if not target.exists():
        return {"ok": False, "reasons": ["archive_target_missing"], "archive_binding": first}
    archived = workspace_content_fingerprint(target, max_entries=max_entries, original_root=original_root)
    if archived.get("complete") is not True or archived.get("digest") != expected_digest:
        return {"ok": False, "reasons": ["archive_target_digest_mismatch"], "archive": archived}
    second = archive_mount_binding(target, required_mount)
    if not second.get("ok"):
        return {"ok": False, "reasons": ["archive_mount_changed", *second.get("reasons", [])], "archive_binding": second}
    if second.get("identity") != dict(expected_identity):
        return {"ok": False, "reasons": ["archive_mount_changed"], "archive_binding": second}
    return {"ok": True, "archive_binding": second, "archive": archived}


def archive_mount_binding(target: Path, required_mount: Path) -> dict[str, Any]:
    """Bind an offload destination to a real mount, never its root fallback."""
    reasons: list[str] = []
    if (not target.is_absolute() or not required_mount.is_absolute()
            or required_mount == Path("/") or ".." in target.parts
            or ".." in required_mount.parts or target == required_mount
            or not target.is_relative_to(required_mount)):
        return {"ok": False, "reasons": ["archive_target_outside_required_mount"]}
    try:
        for path in (*reversed(target.parents), target):
            if path.is_symlink():
                return {"ok": False, "reasons": ["archive_symlink_path"]}
        matches = []
        for line in _read_mountinfo().splitlines():
            fields = line.split()
            if "-" not in fields or len(fields) < 10:
                continue
            separator = fields.index("-")
            mountpoint = re.sub(r"\\([0-7]{3})", lambda match: chr(int(match.group(1), 8)), fields[4])
            if Path(mountpoint) == required_mount:
                matches.append((fields, separator))
        if len(matches) != 1:
            return {"ok": False, "reasons": ["archive_required_mount_absent_or_ambiguous"]}
        fields, separator = matches[0]
        if "rw" not in fields[5].split(","):
            reasons.append("archive_mount_read_only")
        info = required_mount.stat()
        existing = target
        while not existing.exists():
            existing = existing.parent
        if existing.stat().st_dev != info.st_dev:
            reasons.append("archive_nested_mount_mismatch")
        return {
            "ok": not reasons, "reasons": reasons,
            "identity": {"required_mount": str(required_mount), "mount_id": fields[0],
                         "device": fields[2], "fs_root": fields[3],
                         "filesystem": fields[separator + 1], "source": fields[separator + 2],
                         "st_dev": info.st_dev, "st_ino": info.st_ino},
        }
    except (OSError, IndexError, ValueError) as exc:
        return {"ok": False, "reasons": ["archive_mount_binding_unavailable"], "error": str(exc)}


def execute_released_workspace(
    root: Path,
    record: Mapping[str, Any],
    *,
    now_time: dt.datetime | None = None,
    max_entries: int = 100_000,
) -> dict[str, Any]:
    resolved_now = now_time or now_utc()
    eligibility = contracts.execution_eligibility(record, now_time=resolved_now)
    workspace_id = str(record.get("workspace_id") or "")
    if not eligibility["eligible"]:
        return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": eligibility["reasons"]}

    workspace = Path(str(record.get("path") or ""))
    tombstone = workspace.parent / f".abyss-released-{workspace_id}"
    expected = ((record.get("seal") or {}).get("fingerprint") or {}).get("digest")
    journal_path = execution_journal_path(root, workspace_id)
    journal = read_json(journal_path)
    journal_valid = bool(
        journal
        and journal.get("workspace_id") == workspace_id
        and journal.get("seal_fingerprint_digest") == expected
        and journal.get("phase") in {"detached", "applied"}
    )
    if workspace.exists() and tombstone.exists():
        return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": ["workspace_and_tombstone_both_exist"]}

    raw_disposition = record.get("disposition")
    disposition: Mapping[str, Any] = raw_disposition if isinstance(raw_disposition, Mapping) else {}
    decision = disposition.get("decision")
    raw_plan = disposition.get("plan")
    plan: Mapping[str, Any] = raw_plan if isinstance(raw_plan, Mapping) else {}
    archive_target = Path(str(plan.get("target") or "")) if decision == "ARCHIVE" else None
    archive_mount = Path(str(plan.get("required_mount") or "/abyss"))
    archive_binding = archive_mount_binding(archive_target, archive_mount) if archive_target else None
    if archive_binding is not None and not archive_binding["ok"]:
        return {
            "ok": False,
            "workspace_id": workspace_id,
            "decision": "blocked",
            "reasons": archive_binding["reasons"],
            "archive_binding": archive_binding,
        }

    detached = not workspace.exists() and tombstone.exists()
    subject = tombstone if detached else workspace
    if not subject.exists():
        if journal_valid and journal is not None:
            recovered_receipt, recovered_receipt_path, receipt_errors = _validated_execution_receipt(
                root, workspace_id, expected, journal, decision, archive_target,
            )
            if recovered_receipt is None or recovered_receipt_path is None:
                return {
                    "ok": False,
                    "workspace_id": workspace_id,
                    "decision": "blocked",
                    "reasons": receipt_errors,
                }
            if archive_target is not None:
                verification = _verify_archive_state(
                    archive_target,
                    archive_mount,
                    recovered_receipt.get("archive_mount_binding") if isinstance(recovered_receipt.get("archive_mount_binding"), Mapping) else None,
                    recovered_receipt.get("archive_content_digest"),
                    max_entries=max_entries,
                    original_root=workspace,
                )
                if not verification["ok"]:
                    return {
                        "ok": False,
                        "workspace_id": workspace_id,
                        "decision": "blocked",
                        "reasons": ["archive_not_verified_after_detach", *verification.get("reasons", [])],
                        "archive": verification,
                    }
            if not _persist_execution_receipt(recovered_receipt_path, recovered_receipt):
                return {
                    "ok": False,
                    "workspace_id": workspace_id,
                    "decision": "blocked",
                    "reasons": ["execution_receipt_persistence_mismatch"],
                }
            journal["phase"] = "applied"
            journal["updated_at"] = now_iso()
            atomic_write_json(journal_path, journal)
            return {"ok": True, "workspace_id": workspace_id, "decision": "applied", "receipt": recovered_receipt}
        return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": ["workspace_missing_without_receipt"]}

    refs = _path_has_live_refs(subject)
    if refs.get("active") is True or refs.get("checked") is not True:
        reason = "live_reference" if refs.get("active") is True else "reference_probe_unavailable"
        return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": [reason], "references": refs}

    receipt: dict[str, Any]
    persisted_receipt: Path
    archive_content_digest: str | None = None
    if journal_valid and journal is not None and journal.get("phase") == "detached":
        receipt_value, persisted_receipt_value, receipt_errors = _validated_execution_receipt(
            root, workspace_id, expected, journal, decision, archive_target,
        )
        if receipt_value is None or persisted_receipt_value is None:
            return {
                "ok": False,
                "workspace_id": workspace_id,
                "decision": "blocked",
                "reasons": receipt_errors,
            }
        receipt = receipt_value
        persisted_receipt = persisted_receipt_value
        before = receipt.get("before_bytes")
        if not isinstance(before, int) or before < 0:
            return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": ["execution_receipt_size_invalid"]}
        archive_content_digest = receipt.get("archive_content_digest") if archive_target is not None else None
        if archive_target is not None:
            verification = _verify_archive_state(
                archive_target,
                archive_mount,
                receipt.get("archive_mount_binding") if isinstance(receipt.get("archive_mount_binding"), Mapping) else None,
                archive_content_digest,
                max_entries=max_entries,
                original_root=workspace,
            )
            if not verification["ok"]:
                return {
                    "ok": False,
                    "workspace_id": workspace_id,
                    "decision": "blocked",
                    "reasons": ["resumed_archive_not_verified", *verification.get("reasons", [])],
                    "archive": verification,
                }
            source_content = workspace_content_fingerprint(subject, max_entries=max_entries, original_root=workspace)
            if source_content.get("complete") is not True or source_content.get("digest") != archive_content_digest:
                return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": ["resumed_archive_not_verified"]}
    else:
        if journal_valid and journal is not None and journal.get("phase") == "applied":
            return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": ["execution_journal_already_applied"]}
        fingerprint = workspace_identity_fingerprint(subject, max_entries=max_entries, original_root=workspace)
        if fingerprint.get("complete") is not True or fingerprint.get("digest") != expected:
            return {
                "ok": False,
                "workspace_id": workspace_id,
                "decision": "blocked",
                "reasons": ["fingerprint_drift"],
                "fingerprint": fingerprint,
            }
        before_value, before_evidence = storage_candidate_adapters.physical_size_bytes(subject)
        if before_value is None:
            return {
                "ok": False,
                "workspace_id": workspace_id,
                "decision": "blocked",
                "reasons": ["physical_size_unavailable"],
                "evidence": before_evidence,
            }
        before = before_value
        if archive_target is not None:
            workspace_real = subject.resolve(strict=True)
            target_real = archive_target.resolve(strict=False)
            if target_real == workspace_real or workspace_real in target_real.parents or target_real in workspace_real.parents:
                return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": ["archive_target_overlaps_workspace"]}
            partial = archive_target.with_name(f".{archive_target.name}.{workspace_id}.partial")
            if partial.exists():
                return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": ["archive_partial_requires_owner_review"]}
            if archive_target.exists():
                source_content = workspace_content_fingerprint(subject, max_entries=max_entries, original_root=workspace)
                archived = workspace_content_fingerprint(archive_target, max_entries=max_entries, original_root=workspace)
                if source_content.get("complete") is not True or archived.get("complete") is not True or archived.get("digest") != source_content.get("digest"):
                    return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": ["archive_target_conflict"]}
                archive_content_digest = source_content.get("digest")
            else:
                partial.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(subject, partial, symlinks=True)
                source_content = workspace_content_fingerprint(subject, max_entries=max_entries, original_root=workspace)
                archived = workspace_content_fingerprint(partial, max_entries=max_entries, original_root=workspace)
                if source_content.get("complete") is not True or archived.get("complete") is not True or archived.get("digest") != source_content.get("digest"):
                    partial_identity = workspace_identity_fingerprint(partial, max_entries=max_entries)
                    if partial_identity.get("complete") is True:
                        try:
                            shutil.rmtree(partial)
                        except OSError:
                            pass
                    return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": ["archive_fingerprint_mismatch"]}
                archive_content_digest = source_content.get("digest")
                os.rename(partial, archive_target)
            verification = _verify_archive_state(
                archive_target,
                archive_mount,
                archive_binding,
                archive_content_digest,
                max_entries=max_entries,
                original_root=workspace,
            )
            if not verification["ok"]:
                return {
                    "ok": False,
                    "workspace_id": workspace_id,
                    "decision": "blocked",
                    "reasons": ["archive_mount_changed_before_detach", *verification.get("reasons", [])],
                    "archive": verification,
                }
            archive_binding = verification.get("archive_binding", archive_binding)

    # The initial probe is deliberately repeated immediately before detach.
    final_refs = _path_has_live_refs(subject)
    if final_refs.get("active") is True or final_refs.get("checked") is not True:
        reason = "live_reference_before_detach" if final_refs.get("active") is True else "reference_probe_unavailable_before_detach"
        return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": [reason], "references": final_refs}
    final_identity = workspace_identity_fingerprint(subject, max_entries=max_entries, original_root=workspace)
    if final_identity.get("complete") is not True or final_identity.get("digest") != expected:
        return {
            "ok": False,
            "workspace_id": workspace_id,
            "decision": "blocked",
            "reasons": ["fingerprint_drift_before_detach"],
            "fingerprint": final_identity,
        }

    if not detached:
        try:
            inode = subject.stat(follow_symlinks=False).st_ino
            tombstone = _atomic_detach(workspace, workspace_id, inode)
        except (OSError, RuntimeError) as exc:
            return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": ["detach_failed"], "error": str(exc)}

    if not (journal_valid and journal is not None and journal.get("phase") == "detached"):
        applied_at = now_iso()
        receipt = {
            "schema": "abyss_machine_storage_workspace_receipt_v1",
            "workspace_id": workspace_id,
            "owner": record.get("owner"),
            "action": str(decision).lower(),
            "applied_at": applied_at,
            "before_bytes": before,
            "after_bytes": 0,
            "reclaimed_bytes": before,
            "seal_fingerprint_digest": expected,
            "subject_identity_digest": expected,
            "archive_target": str(archive_target) if archive_target else None,
            "archive_content_digest": archive_content_digest,
            "archive_mount_binding": archive_binding,
            "owner_evidence_refs": disposition.get("owner_evidence_refs") or [],
            "valid": True,
        }
        persisted_receipt = (receipt_path(root, workspace_id)).absolute()
        journal = {
            "schema": "abyss_machine_storage_workspace_execution_v1",
            "workspace_id": workspace_id,
            "phase": "detached",
            "seal_fingerprint_digest": expected,
            "receipt_path": str(persisted_receipt),
            "receipt": receipt,
            "updated_at": applied_at,
        }
        atomic_write_json(journal_path, journal)

    if archive_target is not None:
        verification = _verify_archive_state(
            archive_target,
            archive_mount,
            receipt.get("archive_mount_binding") if isinstance(receipt.get("archive_mount_binding"), Mapping) else archive_binding,
            receipt.get("archive_content_digest"),
            max_entries=max_entries,
            original_root=workspace,
        )
        if not verification["ok"]:
            return {
                "ok": False,
                "workspace_id": workspace_id,
                "decision": "blocked",
                "reasons": ["archive_mount_changed_before_local_removal", *verification.get("reasons", [])],
                "archive": verification,
            }

    removal_refs = _path_has_live_refs(tombstone)
    if removal_refs.get("active") is True or removal_refs.get("checked") is not True:
        reason = "live_reference_before_cleanup" if removal_refs.get("active") is True else "reference_probe_unavailable_before_cleanup"
        return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": [reason], "references": removal_refs}
    removal_identity = workspace_identity_fingerprint(tombstone, max_entries=max_entries, original_root=workspace)
    if removal_identity.get("complete") is not True or removal_identity.get("digest") != expected:
        return {
            "ok": False,
            "workspace_id": workspace_id,
            "decision": "blocked",
            "reasons": ["tombstone_identity_changed_before_cleanup"],
            "fingerprint": removal_identity,
        }
    try:
        shutil.rmtree(tombstone)
    except OSError as exc:
        return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": ["detached_cleanup_incomplete"], "error": str(exc)}

    if not _persist_execution_receipt(persisted_receipt, receipt):
        return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": ["execution_receipt_persistence_mismatch"]}
    journal["phase"] = "applied"
    journal["updated_at"] = now_iso()
    atomic_write_json(journal_path, journal)
    return {"ok": True, "workspace_id": workspace_id, "decision": "applied", "receipt": receipt}


def reap(
    root: Path,
    *,
    limit: int = 1,
    scan_limit: int = DEFAULT_REAP_SCAN_LIMIT,
    now_time: dt.datetime | None = None,
) -> dict[str, Any]:
    applied: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    recovered: list[dict[str, Any]] = []
    resolved_now = now_time or now_utc()
    examined = 0
    scanned = 0
    mutations = 0
    resolved_limit = max(1, limit)
    resolved_scan_limit = max(1, min(int(scan_limit), MAX_REAP_SCAN_LIMIT))
    with registry_lock(root):
        state_before = _read_reaper_state(root)
        records = load_records(root)
    rotated_records, cursor_reset_reason = _rotated_records(records, state_before.get("cursor"))
    cursor_before = state_before.get("cursor")
    cursor_after = cursor_before
    for listed_record in rotated_records:
        if scanned >= resolved_scan_limit:
            break
        workspace_id = str(listed_record.get("workspace_id") or "")
        if not workspace_id:
            continue
        scanned += 1
        cursor_after = workspace_id
        with workspace_lock(root, workspace_id, blocking=False) as acquired:
            if not acquired:
                continue
            with registry_lock(root):
                record = read_json(record_path(root, workspace_id))
            if record is None:
                continue
            if record.get("state") == "open":
                expiry = contracts.parse_time((record.get("lease") or {}).get("expires_at")) if isinstance(record.get("lease"), Mapping) else None
                unit = str(record.get("unit") or "")
                unit_state = resource_adapters.systemd_user_unit_state(unit) if unit else {"exists": False, "active": False, "state": "not-found"}
                if expiry is not None and expiry <= resolved_now.astimezone(dt.timezone.utc) and unit_state.get("active") is False and unit_state.get("state") not in {"unknown", "failed-to-read"}:
                    workspace = Path(str(record.get("path") or ""))
                    if not workspace.exists():
                        continue
                    examined += 1
                    refs = _path_has_live_refs(workspace) if workspace.exists() else {"active": False}
                    if workspace.exists() and (refs.get("active") is True or refs.get("checked") is not True):
                        reason = "live_reference" if refs.get("active") is True else "reference_probe_unavailable"
                        blocked.append({"workspace_id": record.get("workspace_id"), "decision": "blocked", "reasons": [reason], "references": refs})
                    elif workspace.exists() and refs.get("active") is False and refs.get("checked") is True:
                        fingerprint = workspace_identity_fingerprint(workspace, max_entries=100_000)
                        physical, evidence = storage_candidate_adapters.physical_size_bytes(workspace)
                        recovery = contracts.recover_abandoned_workspace(
                            record,
                            fingerprint=fingerprint,
                            physical_bytes=physical if physical is not None else -1,
                            recovered_at=resolved_now.astimezone().isoformat(timespec="seconds"),
                        )
                        if recovery.get("ok"):
                            with registry_lock(root):
                                current = read_json(record_path(root, workspace_id))
                                if current is not None and current.get("state") == "open":
                                    atomic_write_json(record_path(root, workspace_id), recovery["record"])
                            recovered.append({"workspace_id": record.get("workspace_id"), "decision": "sealed_unknown"})
                            mutations += 1
                        elif physical is None:
                            blocked.append({"workspace_id": record.get("workspace_id"), "decision": "blocked", "reasons": ["physical_size_unavailable", *(recovery.get("errors") or [])], "evidence": evidence, "fingerprint": fingerprint})
                        else:
                            blocked.append({"workspace_id": record.get("workspace_id"), "decision": "blocked", "reasons": recovery.get("errors") or ["recovery_blocked"], "evidence": evidence, "fingerprint": fingerprint})
                    if mutations >= resolved_limit or scanned >= resolved_scan_limit:
                        break
                continue
            if record.get("state") != "released" or isinstance(record.get("execution"), Mapping):
                continue
            examined += 1
            result = execute_released_workspace(root, record, now_time=resolved_now)
            if result.get("ok"):
                record["execution"] = {
                    "applied": True,
                    "receipt": result.get("receipt"),
                }
                record["updated_at"] = result.get("receipt", {}).get("applied_at")
                with registry_lock(root):
                    atomic_write_json(record_path(root, workspace_id), record)
                applied.append(result)
                mutations += 1
            else:
                blocked.append(result)
            if mutations >= resolved_limit or scanned >= resolved_scan_limit:
                break
    cursor_commit: dict[str, Any] = {
        "path": str(reaper_state_path(root)),
        "before": cursor_before,
        "after": cursor_after,
        "committed": False,
        "revision_before": int(state_before.get("revision") or 0),
        "revision_after": None,
        "reset_reason": state_before.get("reason") or cursor_reset_reason,
        "reason": "no_records_scanned",
    }
    if scanned:
        with registry_lock(root):
            current_state = _read_reaper_state(root)
            expected_revision = int(state_before.get("revision") or 0)
            current_revision = int(current_state.get("revision") or 0)
            if current_revision != expected_revision:
                cursor_commit["reason"] = "cursor_changed_concurrently"
                cursor_commit["current"] = current_state.get("cursor")
                cursor_commit["revision_after"] = current_revision
            else:
                next_state = {
                    "schema": REAPER_STATE_SCHEMA,
                    "cursor": cursor_after,
                    "revision": expected_revision + 1,
                    "updated_at": now_iso(),
                }
                try:
                    atomic_write_json(reaper_state_path(root), next_state)
                except OSError as exc:
                    cursor_commit["reason"] = "cursor_persist_failed"
                    cursor_commit["error"] = str(exc)
                else:
                    cursor_commit["committed"] = True
                    cursor_commit["reason"] = None
                    cursor_commit["revision_after"] = expected_revision + 1
    return {
        "schema": "abyss_machine_storage_workspace_reap_v1",
        "ok": True,
        "applied": applied,
        "blocked": blocked,
        "recovered": recovered,
        "cursor": cursor_commit,
        "summary": {
            "scanned": scanned,
            "examined": examined,
            "scan_limit": resolved_scan_limit,
            "mutations": mutations,
            "applied": len(applied),
            "blocked": len(blocked),
            "recovered": len(recovered),
            "reclaimed_bytes": sum(int(item.get("receipt", {}).get("reclaimed_bytes") or 0) for item in applied),
        },
    }


def status(root: Path) -> dict[str, Any]:
    records = load_records(root)
    buckets = {"active_managed_bytes": 0, "sealed_reclaimable_bytes": 0, "blocked_bytes": 0, "unmanaged_bytes": None}
    counts = {"open": 0, "sealed": 0, "released": 0}
    for record in records:
        state = str(record.get("state") or "")
        if state in counts:
            counts[state] += 1
        seal = record.get("seal") if isinstance(record.get("seal"), Mapping) else {}
        size = int(seal.get("physical_bytes") or 0)
        if state == "open":
            path = Path(str(record.get("path") or ""))
            measured, _evidence = storage_candidate_adapters.physical_size_bytes(path) if path.exists() else (0, {})
            size = int(measured or 0)
            buckets["active_managed_bytes"] += size
        elif state == "released" and not isinstance(record.get("execution"), Mapping):
            buckets["sealed_reclaimable_bytes"] += size
        elif state == "sealed":
            buckets["blocked_bytes"] += size
    return {"schema": "abyss_machine_storage_workspace_status_v1", "ok": True, "root": str(root), "counts": counts, "bytes": buckets, "policy": {"unmanaged_requires_bounded_owner_inventory": True}}

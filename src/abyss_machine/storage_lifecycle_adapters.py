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


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def load_records(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted((root / "workspaces").glob("*.json")):
        value = read_json(path)
        if value is not None:
            records.append(value)
    return records


def workspace_identity_fingerprint(path: Path, *, max_entries: int = 100_000) -> dict[str, Any]:
    digest = hashlib.sha256()
    entries = 0
    errors: list[dict[str, str]] = []
    truncated = False

    def include(item: Path, relative: str, *, root: bool = False) -> None:
        nonlocal entries, truncated
        if entries >= max(1, max_entries):
            truncated = True
            return
        try:
            item_stat = item.lstat()
        except OSError as exc:
            errors.append({"path": str(item), "error": str(exc)})
            return
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

    include(path, ".", root=True)
    if path.is_dir() and not path.is_symlink():
        for current, dirnames, filenames in os.walk(path, topdown=True, followlinks=False):
            current_path = Path(current)
            dirnames.sort()
            filenames.sort()
            for name in [*dirnames, *filenames]:
                include(current_path / name, str((current_path / name).relative_to(path)))
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


def workspace_content_fingerprint(path: Path, *, max_entries: int = 100_000) -> dict[str, Any]:
    digest = hashlib.sha256()
    entries = 0
    errors: list[dict[str, str]] = []
    truncated = False

    def include(item: Path, relative: str) -> None:
        nonlocal entries, truncated
        if entries >= max(1, max_entries):
            truncated = True
            return
        try:
            item_stat = item.lstat()
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

    include(path, ".")
    if path.is_dir() and not path.is_symlink():
        for current, dirnames, filenames in os.walk(path, topdown=True, followlinks=False):
            current_path = Path(current)
            dirnames.sort()
            filenames.sort()
            for name in [*dirnames, *filenames]:
                include(current_path / name, str((current_path / name).relative_to(path)))
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
) -> dict[str, Any]:
    workspace = workspace.expanduser().absolute()
    if not owner.strip():
        return {"ok": False, "errors": ["owner_required"]}
    if workspace.exists() and not workspace.is_dir():
        return {"ok": False, "errors": ["workspace_must_be_directory"]}
    token = secrets.token_urlsafe(32)
    nonce = secrets.token_hex(16)
    launcher_created = False
    if not workspace.exists() and create:
        workspace.mkdir(parents=True, exist_ok=False)
        launcher_created = True
    opened = now_utc()
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
    process = storage_candidate_adapters.process_references([text]).get(text, {})
    mount = storage_candidate_adapters.mount_references(path)
    return {
        "active": process.get("active") is True or mount.get("active") is True,
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
    detached = not workspace.exists() and tombstone.exists()
    subject = tombstone if detached else workspace
    if not subject.exists():
        if journal_valid:
            receipt = journal.get("receipt") if isinstance(journal.get("receipt"), Mapping) else None
            persisted_receipt = Path(str(journal.get("receipt_path") or ""))
            if receipt is not None and persisted_receipt.is_absolute():
                if not persisted_receipt.exists():
                    atomic_write_json(persisted_receipt, receipt)
                journal["phase"] = "applied"
                journal["updated_at"] = now_iso()
                atomic_write_json(journal_path, journal)
                return {"ok": True, "workspace_id": workspace_id, "decision": "applied", "receipt": receipt}
        return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": ["workspace_missing_without_receipt"]}
    refs = _path_has_live_refs(subject)
    if refs["active"]:
        return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": ["live_reference"], "references": refs}
    disposition = record.get("disposition") if isinstance(record.get("disposition"), Mapping) else {}
    decision = disposition.get("decision")
    plan = disposition.get("plan") if isinstance(disposition.get("plan"), Mapping) else {}
    archive_target = Path(str(plan.get("target") or "")) if decision == "ARCHIVE" else None
    archive_mount = Path(str(plan.get("required_mount") or "/abyss"))
    archive_binding = archive_mount_binding(archive_target, archive_mount) if archive_target else None
    if archive_binding is not None and not archive_binding["ok"]:
        return {"ok": False, "workspace_id": workspace_id, "decision": "blocked",
                "reasons": archive_binding["reasons"], "archive_binding": archive_binding}
    if journal_valid and journal is not None and journal.get("phase") == "detached":
        receipt = dict(journal.get("receipt") if isinstance(journal.get("receipt"), Mapping) else {})
        if archive_target is not None:
            source_content = workspace_content_fingerprint(subject, max_entries=max_entries)
            archived = workspace_content_fingerprint(archive_target, max_entries=max_entries)
            if not source_content.get("complete") or not archived.get("complete") or source_content.get("digest") != archived.get("digest"):
                return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": ["resumed_archive_not_verified"]}
    else:
        fingerprint = workspace_identity_fingerprint(subject, max_entries=max_entries)
        if fingerprint.get("complete") is not True or fingerprint.get("digest") != expected:
            return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": ["fingerprint_drift"], "fingerprint": fingerprint}
        before_value, before_evidence = storage_candidate_adapters.physical_size_bytes(subject)
        if before_value is None:
            return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": ["physical_size_unavailable"], "evidence": before_evidence}
        before = before_value
        inode = subject.stat(follow_symlinks=False).st_ino
        if archive_target is not None:
            workspace_real = subject.resolve(strict=True)
            target_real = archive_target.resolve(strict=False)
            if target_real == workspace_real or workspace_real in target_real.parents or target_real in workspace_real.parents:
                return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": ["archive_target_overlaps_workspace"]}
            partial = archive_target.with_name(f".{archive_target.name}.{workspace_id}.partial")
            if partial.exists():
                return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": ["archive_partial_requires_owner_review"]}
            if archive_target.exists():
                source_content = workspace_content_fingerprint(subject, max_entries=max_entries)
                archived = workspace_content_fingerprint(archive_target, max_entries=max_entries)
                if source_content.get("complete") is not True or archived.get("complete") is not True or archived.get("digest") != source_content.get("digest"):
                    return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": ["archive_target_conflict"]}
            else:
                partial.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(subject, partial, symlinks=True)
                source_content = workspace_content_fingerprint(subject, max_entries=max_entries)
                archived = workspace_content_fingerprint(partial, max_entries=max_entries)
                if source_content.get("complete") is not True or archived.get("complete") is not True or archived.get("digest") != source_content.get("digest"):
                    shutil.rmtree(partial)
                    return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": ["archive_fingerprint_mismatch"]}
                os.rename(partial, archive_target)
            rebound = archive_mount_binding(archive_target, archive_mount)
            if not rebound["ok"] or rebound.get("identity") != archive_binding.get("identity"):
                return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": ["archive_mount_changed_before_detach"], "archive_binding": rebound}
            unchanged = workspace_identity_fingerprint(subject, max_entries=max_entries)
            if not unchanged.get("complete") or unchanged.get("digest") != expected:
                return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": ["workspace_changed_during_archive"]}
        if not detached:
            tombstone = _atomic_detach(workspace, workspace_id, inode)
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
            "archive_target": str(archive_target) if archive_target else None,
            "archive_mount_binding": archive_binding,
            "owner_evidence_refs": disposition.get("owner_evidence_refs") or [],
            "valid": True,
        }
        journal = {
            "schema": "abyss_machine_storage_workspace_execution_v1",
            "workspace_id": workspace_id,
            "phase": "detached",
            "seal_fingerprint_digest": expected,
            "receipt_path": str(receipt_path(root, workspace_id)),
            "receipt": receipt,
            "updated_at": applied_at,
        }
        atomic_write_json(journal_path, journal)
    if archive_target is not None:
        rebound = archive_mount_binding(archive_target, archive_mount)
        if not rebound["ok"] or rebound.get("identity") != archive_binding.get("identity"):
            return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": ["archive_mount_changed_before_local_removal"]}
    try:
        shutil.rmtree(tombstone)
    except OSError as exc:
        return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": ["detached_cleanup_incomplete"], "error": str(exc)}
    persisted_receipt = Path(str((journal or {}).get("receipt_path") or ""))
    if not persisted_receipt.is_absolute():
        return {"ok": False, "workspace_id": workspace_id, "decision": "blocked", "reasons": ["execution_journal_invalid"]}
    atomic_write_json(persisted_receipt, receipt)
    journal["phase"] = "applied"
    journal["updated_at"] = now_iso()
    atomic_write_json(journal_path, journal)
    return {"ok": True, "workspace_id": workspace_id, "decision": "applied", "receipt": receipt}


def reap(root: Path, *, limit: int = 1, now_time: dt.datetime | None = None) -> dict[str, Any]:
    applied: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    recovered: list[dict[str, Any]] = []
    resolved_now = now_time or now_utc()
    examined = 0
    resolved_limit = max(1, limit)
    with registry_lock(root):
        records = load_records(root)
    for listed_record in records:
        workspace_id = str(listed_record.get("workspace_id") or "")
        if not workspace_id:
            continue
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
                    refs = _path_has_live_refs(workspace) if workspace.exists() else {"active": False}
                    if workspace.exists() and refs.get("active") is False:
                        examined += 1
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
                        elif physical is None:
                            blocked.append({"workspace_id": record.get("workspace_id"), "decision": "blocked", "reasons": ["physical_size_unavailable"], "evidence": evidence})
                        if examined >= resolved_limit:
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
            else:
                blocked.append(result)
            if examined >= resolved_limit:
                break
    return {
        "schema": "abyss_machine_storage_workspace_reap_v1",
        "ok": True,
        "applied": applied,
        "blocked": blocked,
        "recovered": recovered,
        "summary": {"examined": examined, "applied": len(applied), "blocked": len(blocked), "recovered": len(recovered), "reclaimed_bytes": sum(int(item.get("receipt", {}).get("reclaimed_bytes") or 0) for item in applied)},
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

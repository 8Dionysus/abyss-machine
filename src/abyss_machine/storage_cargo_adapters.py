"""Explicit source-bound Cargo target executor; no discovery or automatic cleanup."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
from typing import Any, Callable, Mapping

from . import storage_candidate_adapters as candidates
from . import storage_process_probe


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cargo_preflight(candidate: Mapping[str, Any], *, cache_root: Path,
                    attestation_path: Path) -> dict[str, Any]:
    reasons: list[str] = []
    target = Path(str(candidate.get("path") or ""))
    root = cache_root / "cargo" / "target"
    try:
        relative = target.relative_to(root)
        if len(relative.parts) != 3 or relative.parts[1] != "source-bound":
            reasons.append("source_bound_target_required")
    except ValueError:
        reasons.append("outside_cargo_target_root")
    if not target.is_absolute() or target.resolve() != target or root.resolve() != root:
        reasons.append("symlink_or_noncanonical_target")
    if not target.is_dir():
        reasons.append("target_directory_required")
    if candidate.get("kind") != "cargo_target" or candidate.get("executor", {}).get("type") != "cargo_target_cleanup_v1":
        reasons.append("cargo_executor_required")
    if reasons:
        return {"ok": False, "reasons": reasons, "path": str(target),
                "attestation": str(attestation_path)}
    manifest = candidate.get("evidence", {}).get("manifest", {})
    digest = None
    document: dict[str, Any] = {}
    try:
        if attestation_path.resolve().is_relative_to(target.resolve()) or attestation_path.is_symlink():
            reasons.append("attestation_must_be_preserved_outside_target")
        digest = file_digest(attestation_path)
        document = json.loads(attestation_path.read_text())
        if not isinstance(document, dict):
            raise ValueError("attestation_object_required")
    except (OSError, ValueError) as exc:
        document = {}
        reasons.append("attestation_unreadable:" + str(exc))
    if manifest.get("replacement", {}).get("ref") != "sha256:" + str(digest):
        reasons.append("attestation_digest_not_manifest_bound")
    for key, expected in (("schema", "abyss_machine_cargo_target_retirement_v1"),
                          ("path", str(target)), ("source_id", candidate.get("source_id")),
                          ("owner", candidate.get("owner")), ("terminal", True),
                          ("future_consumers_independent", True), ("unique_data_clear", True)):
        matches = document.get(key) is expected if isinstance(expected, bool) else document.get(key) == expected
        if not matches:
            reasons.append("attestation_" + key + "_mismatch")
    if not document.get("recovery_command"):
        reasons.append("reproducible_recovery_command_required")
    preserved = document.get("preserved_files")
    if not isinstance(preserved, list) or not preserved:
        reasons.append("preserved_files_required")
    else:
        roles: set[str] = set()
        for record in preserved:
            try:
                path = Path(record["path"])
                if not path.is_absolute() or path.resolve().is_relative_to(target.resolve()) or path.is_symlink():
                    raise ValueError("preserved_file_outside_target_required")
                if file_digest(path) != record["sha256"]:
                    raise ValueError("preserved_file_digest_mismatch")
                roles.add(record["role"])
            except (OSError, KeyError, TypeError, ValueError) as exc:
                reasons.append("preservation_invalid:" + str(exc))
        if not {"product", "proof", "terminal_receipt"}.issubset(roles):
            reasons.append("product_proof_terminal_receipt_required")
    fingerprint = candidates.filesystem_fingerprint(target, max_entries=200_000)
    if not fingerprint.get("complete") or fingerprint.get("symlinks"):
        reasons.append("target_fingerprint_incomplete_or_symlink")
    if fingerprint.get("digest") != candidate.get("fingerprint", {}).get("digest"):
        reasons.append("filesystem_fingerprint_drift")
    outside_links: list[str] = []
    try:
        outside_links = external_hardlinks(target)
        if outside_links:
            reasons.append("external_hardlinks_reclaim_uncertain")
    except OSError as exc:
        reasons.append("hardlink_scan_incomplete:" + str(exc))
    return {"ok": not reasons, "reasons": reasons, "path": str(target),
            "external_hardlink_paths": outside_links[:20],
            "attestation": str(attestation_path), "attestation_digest": digest,
            "fingerprint": fingerprint}


def external_hardlinks(target: Path) -> list[str]:
    """Do not mistake allocations kept alive outside the candidate for reclaim."""
    counts: dict[tuple[int, int], int] = {}
    links: dict[tuple[int, int], tuple[int, str]] = {}
    for current, directories, files in os.walk(target, followlinks=False):
        for name in files:
            path = Path(current) / name
            info = path.lstat()
            if stat.S_ISREG(info.st_mode):
                key = (info.st_dev, info.st_ino)
                counts[key] = counts.get(key, 0) + 1
                links[key] = (info.st_nlink, str(path))
    return [path for key, (nlink, path) in links.items() if nlink > counts[key]]


def execute_cargo_target(candidate: Mapping[str, Any], *, cache_root: Path,
                         attestation_path: Path, dry_run: bool = True,
                         admission_check: Callable[[], Mapping[str, Any]] | None = None) -> dict[str, Any]:
    preflight = cargo_preflight(candidate, cache_root=cache_root, attestation_path=attestation_path)
    result = {**preflight, "dry_run": dry_run, "executor": "cargo_target_cleanup_v1"}
    if not preflight["ok"] or dry_run:
        return result
    target = Path(preflight["path"])
    locks: list[int] = []
    try:
        # Cargo's cooperating writers hold these locks during compilation.
        # O_NOFOLLOW and rmtree's fd traversal preserve the symlink boundary.
        if not shutil.rmtree.avoids_symlink_attacks:
            raise ValueError("fd_safe_rmtree_required")
        for lock in sorted(target.rglob(".cargo-lock")):
            fd = os.open(lock, os.O_RDWR | os.O_NOFOLLOW)
            locks.append(fd)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        final = cargo_preflight(candidate, cache_root=cache_root, attestation_path=attestation_path)
        if not final["ok"]:
            raise ValueError("final_preflight_failed:" + ",".join(final["reasons"]))
        before, measured = candidates.physical_size_bytes(target)
        if not measured.get("ok") or before is None:
            raise ValueError("physical_size_unknown")
        outside_links = external_hardlinks(target)
        if outside_links:
            result["external_hardlink_paths"] = outside_links[:20]
            raise ValueError("external_hardlinks_reclaim_uncertain")
        process = storage_process_probe.owner_process_references([str(target)], max_refs_per_path=32)[str(target)]
        result["process_refs"] = process
        # Our own .cargo-lock descriptors are intentional, not active writers.
        refs = [ref for ref in process.get("refs", []) if ref.get("pid") != os.getpid()]
        if process.get("checked") is not True or refs:
            raise ValueError("active_or_incomplete_process_scan")
        admission = admission_check() if admission_check is not None else {"ok": False, "reason": "admission_check_required"}
        result["immediate_admission"] = dict(admission)
        if admission.get("ok") is not True:
            raise ValueError("immediate_claim_or_approval_not_clear")
        result["before_bytes"] = before
        capacity_before = os.statvfs(cache_root)
        available_before = capacity_before.f_bavail * capacity_before.f_frsize
        shutil.rmtree(target)
        capacity_after = os.statvfs(cache_root)
        available_after = capacity_after.f_bavail * capacity_after.f_frsize
        result["available_bytes_before"] = available_before
        result["available_bytes_after"] = available_after
        result["net_available_delta_bytes"] = available_after - available_before
        result["capacity_delta_is_not_exclusive_attribution"] = True
        result.update(ok=True, applied=True, after_bytes=0, reclaimed_bytes=before)
    except (OSError, ValueError) as exc:
        result.update(ok=False, applied=False, error=str(exc))
    finally:
        for fd in locks:
            os.close(fd)
    return result

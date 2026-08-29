"""Deterministic offline Node provider archive and admitted installation route."""

from __future__ import annotations

from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
import posixpath
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile
from typing import Any, Mapping

from .code_intelligence_provider import (
    ARTIFACT_CLASS,
    BUNDLE_MANIFEST_REF,
    CONTRACT_SURFACE_ID,
    DEFAULT_REGISTRY_DIR,
    DEFAULT_RUNTIME_ROOT,
    DEFAULT_SOURCE_ROOT,
    _artifact_tools,
    _canonical_json,
    _digest_file,
    _safe_source_ref,
    _subject_binding,
    _summarize_verify,
    _trust_gate,
    run_owner_preflights,
)


ARCHIVE_SCHEMA = "abyss_machine_code_intelligence_node_provider_archive_v1"
INSTALLATION_SCHEMA = "abyss_machine_code_intelligence_node_provider_installation_v1"
PROVIDER_ID = "node-providers"
PROVIDER_IDS = ("tree-sitter", "scip", "lsp")
METADATA_NAME = "provider.json"
LOCK_NAME = "provider-lock.json"
RUNTIME_PREFIX = "runtime/"
MAX_ARCHIVE_BYTES = 768 * 1024 * 1024
MAX_MEMBER_BYTES = 256 * 1024 * 1024
MAX_FILES = 20000


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name and not path.is_absolute() and ".." not in path.parts and "\\" not in name)


def _safe_symlink(name: str, target: str, *, required_prefix: str = "") -> bool:
    if not target or PurePosixPath(target).is_absolute() or "\\" in target:
        return False
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
    return _safe_member(resolved) and (not required_prefix or resolved.startswith(required_prefix))


def _read_lock(path: str | Path) -> dict[str, Any]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema") != "abyss_machine_code_intelligence_node_provider_lock_v1":
        raise ValueError("node provider lock schema mismatch")
    packages = document.get("packages")
    if not isinstance(packages, list) or {str(item.get("provider")) for item in packages if isinstance(item, Mapping)} != set(PROVIDER_IDS):
        raise ValueError("node provider lock must bind Tree-sitter, SCIP, and LSP")
    return document


def _installed_lock(runtime: Path) -> dict[str, Any]:
    path = runtime / "node_modules" / ".package-lock.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("lockfileVersion") != 3 or not isinstance(document.get("packages"), dict):
        raise ValueError("installed Node package lock is missing or unsupported")
    return document


def _verify_locked_runtime(runtime: Path, lock: Mapping[str, Any]) -> None:
    installed = _installed_lock(runtime)["packages"]
    for package in lock["packages"]:
        name = str(package["name"])
        entry = installed.get(f"node_modules/{name}")
        if not isinstance(entry, Mapping):
            raise ValueError(f"locked Node package is missing: {name}")
        if entry.get("version") != package.get("version") or entry.get("integrity") != package.get("integrity"):
            raise ValueError(f"locked Node package identity mismatch: {name}")
    for executable in ("tree-sitter", "scip-typescript", "typescript-language-server"):
        path = runtime / "node_modules" / ".bin" / executable
        if not path.exists() or not os.access(path, os.X_OK):
            raise ValueError(f"Node provider executable is missing: {executable}")


def _tar_info(name: str, *, size: int = 0, mode: int = 0o644, linkname: str = "") -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.size = size
    info.mode = mode
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.type = tarfile.SYMTYPE if linkname else tarfile.REGTYPE
    info.linkname = linkname
    info.pax_headers = {}
    return info


def build_node_provider_archive(
    runtime_dir: str | Path,
    output: str | Path,
    *,
    lock_path: str | Path,
    source_ref: str,
    platform: str,
) -> dict[str, Any]:
    if not _safe_source_ref(source_ref):
        raise ValueError("source_ref must be a qualified source: or commit: reference")
    runtime = Path(runtime_dir).resolve()
    lock = _read_lock(lock_path)
    _verify_locked_runtime(runtime, lock)
    entries: list[tuple[str, bytes | None, str, int]] = []
    files: list[dict[str, Any]] = []
    for path in sorted(runtime.rglob("*"), key=lambda item: item.relative_to(runtime).as_posix()):
        relative = path.relative_to(runtime).as_posix()
        name = RUNTIME_PREFIX + relative
        if path.is_symlink():
            target = os.readlink(path)
            if not _safe_member(relative) or not _safe_symlink(relative, target):
                raise ValueError(f"unsafe Node runtime symlink: {relative}")
            entries.append((name, None, target, 0o777))
            files.append({"path": name, "kind": "symlink", "target": target})
        elif path.is_file():
            payload = path.read_bytes()
            if len(payload) > MAX_MEMBER_BYTES:
                raise ValueError(f"Node runtime member exceeds bounded size: {relative}")
            mode = 0o755 if os.access(path, os.X_OK) else 0o644
            entries.append((name, payload, "", mode))
            files.append({"path": name, "kind": "file", "sha256": _sha256_bytes(payload), "bytes": len(payload), "mode": mode})
    if not entries or len(entries) > MAX_FILES:
        raise ValueError("Node runtime file set is empty or exceeds the bounded count")
    metadata = {
        "schema": ARCHIVE_SCHEMA,
        "provider_id": PROVIDER_ID,
        "providers": list(PROVIDER_IDS),
        "source_ref": source_ref,
        "platform": platform,
        "offline_install": True,
        "files": files,
        "lock_digest": _sha256_bytes(_canonical_json(lock)),
        "claim_limits": [
            "This unsigned archive is only a provider candidate.",
            "Installation requires exact bundle verification and registry trust-gate admission.",
            "Runnable providers do not establish semantic proof or owner acceptance.",
        ],
    }
    control_entries = [
        (METADATA_NAME, _canonical_json(metadata) + b"\n", "", 0o644),
        (LOCK_NAME, _canonical_json(lock) + b"\n", "", 0o644),
    ]
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w", format=tarfile.GNU_FORMAT) as archive:
        for name, payload, linkname, mode in sorted(control_entries + entries, key=lambda item: item[0]):
            info = _tar_info(name, size=len(payload or b""), mode=mode, linkname=linkname)
            archive.addfile(info, None if payload is None else io.BytesIO(payload))
    compressed = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed, mode="wb", filename="", mtime=0, compresslevel=9) as stream:
        stream.write(tar_buffer.getvalue())
    archive_bytes = compressed.getvalue()
    if len(archive_bytes) > MAX_ARCHIVE_BYTES:
        raise ValueError("Node provider archive exceeds bounded size")
    target = Path(output).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() != archive_bytes:
        raise FileExistsError(f"refusing to replace provider artifact: {target}")
    status = "already_present" if target.exists() else "built"
    if not target.exists():
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent))
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            temporary.write_bytes(archive_bytes)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    return {
        "schema": "abyss_machine_code_intelligence_node_provider_build_v1",
        "status": status,
        "provider_id": PROVIDER_ID,
        "output": str(target),
        "archive_sha256": _sha256_bytes(archive_bytes),
        "archive_bytes": len(archive_bytes),
        "metadata": metadata,
        "admission_status": "not_admitted",
    }


def read_node_provider_archive(path: str | Path) -> dict[str, Any]:
    archive_path = Path(path).resolve()
    if not archive_path.is_file() or archive_path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("Node provider archive is missing or too large")
    members: dict[str, dict[str, Any]] = {}
    with tarfile.open(archive_path, mode="r:gz") as archive:
        for member in archive.getmembers():
            if member.name in members or not _safe_member(member.name) or not (member.isreg() or member.issym()):
                raise ValueError(f"unsafe Node provider archive member: {member.name}")
            if member.name not in {METADATA_NAME, LOCK_NAME} and not member.name.startswith(RUNTIME_PREFIX):
                raise ValueError(f"unexpected Node provider archive member: {member.name}")
            if member.issym():
                if not _safe_symlink(member.name, member.linkname, required_prefix=RUNTIME_PREFIX):
                    raise ValueError(f"unsafe Node provider symlink target: {member.name}")
                members[member.name] = {"kind": "symlink", "target": member.linkname, "mode": member.mode}
            else:
                stream = archive.extractfile(member)
                payload = b"" if stream is None else stream.read(MAX_MEMBER_BYTES + 1)
                if len(payload) > MAX_MEMBER_BYTES:
                    raise ValueError(f"oversized Node provider member: {member.name}")
                members[member.name] = {"kind": "file", "payload": payload, "mode": member.mode}
    if METADATA_NAME not in members or LOCK_NAME not in members or len(members) > MAX_FILES + 2:
        raise ValueError("Node provider archive member set is incomplete")
    metadata = json.loads(members[METADATA_NAME]["payload"])
    lock = json.loads(members[LOCK_NAME]["payload"])
    if metadata.get("schema") != ARCHIVE_SCHEMA or metadata.get("providers") != list(PROVIDER_IDS):
        raise ValueError("Node provider metadata identity mismatch")
    if metadata.get("lock_digest") != _sha256_bytes(_canonical_json(lock)):
        raise ValueError("Node provider lock digest mismatch")
    expected = {str(item["path"]): item for item in metadata.get("files", []) if isinstance(item, Mapping)}
    actual = {name for name in members if name.startswith(RUNTIME_PREFIX)}
    if set(expected) != actual:
        raise ValueError("Node provider inventory mismatch")
    for name, item in expected.items():
        member = members[name]
        if item.get("kind") != member["kind"]:
            raise ValueError(f"Node provider member kind mismatch: {name}")
        if member["kind"] == "file" and (item.get("sha256") != _sha256_bytes(member["payload"]) or item.get("bytes") != len(member["payload"])):
            raise ValueError(f"Node provider file identity mismatch: {name}")
        if member["kind"] == "symlink" and item.get("target") != member["target"]:
            raise ValueError(f"Node provider symlink identity mismatch: {name}")
    return {
        "provider_id": PROVIDER_ID,
        "archive_path": str(archive_path),
        "archive_sha256": _digest_file(archive_path),
        "archive_bytes": archive_path.stat().st_size,
        "metadata": metadata,
        "lock": lock,
        "members": members,
    }


def inspect_node_provider_artifact(
    archive_path: str | Path,
    bundle_dir: str | Path,
    *,
    subject_root: str | Path,
    registry_dir: str | Path,
    source_root: str | Path = DEFAULT_SOURCE_ROOT,
    expected_source_ref: str = "",
) -> dict[str, Any]:
    result: dict[str, Any] = {"schema": "abyss_machine_code_intelligence_node_provider_inspection_v1", "provider_id": PROVIDER_ID, "status": "blocked", "checks": {}}
    try:
        archive = read_node_provider_archive(archive_path)
    except Exception as exc:
        result["checks"]["archive"] = {"ok": False, "error_type": type(exc).__name__, "reason": str(exc)}
        return result
    result["checks"]["archive"] = {"ok": True}
    try:
        binding = _subject_binding(archive, Path(bundle_dir).resolve(), subject_root=Path(subject_root).resolve(), source_root=Path(source_root).resolve())
    except Exception as exc:
        binding = {"ok": False, "errors": [f"subject binding unreadable:{type(exc).__name__}"]}
    result["subject_binding"] = binding
    result["checks"]["subject_binding"] = {"ok": binding.get("ok") is True, "errors": binding.get("errors", [])}
    source_ref = expected_source_ref or str(binding.get("source_ref") or archive["metadata"].get("source_ref") or "")
    if expected_source_ref and expected_source_ref != str(binding.get("source_ref") or ""):
        result["checks"]["subject_binding"]["ok"] = False
        result["checks"]["subject_binding"]["errors"].append("expected source_ref does not match bundle source_ref")
    subject_digest = str(binding.get("subject_digest") or "")
    result["artifact"] = {"subject_digest": subject_digest or None, "source_ref": source_ref or None}
    try:
        verification = _artifact_tools().verify_bundle(Path(bundle_dir).resolve(), subject_root=Path(subject_root).resolve(), repo_root=Path(source_root).resolve(), write=False)
        result["checks"]["bundle_verify"] = _summarize_verify(verification)
    except Exception as exc:
        result["checks"]["bundle_verify"] = {"ok": False, "error_type": type(exc).__name__}
    if subject_digest and _safe_source_ref(source_ref):
        try:
            gate = _trust_gate(Path(registry_dir).resolve(), subject_digest=subject_digest, source_ref=source_ref)
            result["trust_gate"] = {"ok": gate.get("ok") is True and gate.get("verdict") == "allow", "verdict": gate.get("verdict"), "record_id": gate.get("record_id"), "latest_record_id": gate.get("latest_record_id"), "reasons": list(gate.get("reasons", []))[:16], "blockers": list(gate.get("blockers", []))[:16]}
        except Exception as exc:
            result["trust_gate"] = {"ok": False, "verdict": "unknown", "error_type": type(exc).__name__}
    else:
        result["trust_gate"] = {"ok": False, "verdict": "unknown", "reasons": ["subject_binding_not_ready"]}
    if all(result["checks"].get(name, {}).get("ok") is True for name in ("archive", "subject_binding", "bundle_verify")) and result["trust_gate"].get("ok") is True:
        result["status"] = "admitted"
    return result


def install_node_provider_artifact(
    archive_path: str | Path,
    bundle_dir: str | Path,
    *,
    subject_root: str | Path,
    registry_dir: str | Path = DEFAULT_REGISTRY_DIR,
    runtime_root: str | Path = DEFAULT_RUNTIME_ROOT,
    source_root: str | Path = DEFAULT_SOURCE_ROOT,
    expected_source_ref: str = "",
    apply: bool = False,
) -> dict[str, Any]:
    inspection = inspect_node_provider_artifact(archive_path, bundle_dir, subject_root=subject_root, registry_dir=registry_dir, source_root=source_root, expected_source_ref=expected_source_ref)
    result: dict[str, Any] = {"schema": "abyss_machine_code_intelligence_node_provider_install_v1", "provider_id": PROVIDER_ID, "status": "blocked", "inspection": inspection, "written": [], "claim_limit": "Installation is not deployment, semantic proof, or owner acceptance."}
    if inspection.get("status") != "admitted":
        result["blocking_reasons"] = ["exact_node_provider_artifact_not_admitted"]
        return result
    archive = read_node_provider_archive(archive_path)
    runtime_base = Path(runtime_root).resolve()
    target = runtime_base / "providers" / PROVIDER_ID
    identity_path = target / "installation.json"
    if identity_path.is_file():
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        if identity.get("subject_digest") == inspection.get("artifact", {}).get("subject_digest"):
            result.update({"status": "already_installed", "installation": identity})
            return result
    if target.exists() or target.is_symlink():
        result["blocking_reasons"] = ["different_node_provider_installation_exists"]
        return result
    if not apply:
        result.update({"status": "ready_to_install", "would_install": str(target)})
        return result
    preflight = run_owner_preflights(archive_bytes=archive["archive_bytes"], runtime_root=runtime_base)
    result["preflight"] = preflight
    if preflight.get("ok") is not True:
        result["blocking_reasons"] = ["owner_write_preflight_denied"]
        return result
    providers_dir = runtime_base / "providers"
    providers_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{PROVIDER_ID}.staging-", dir=str(providers_dir)))
    try:
        for name, member in sorted(archive["members"].items()):
            if not name.startswith(RUNTIME_PREFIX):
                continue
            relative = PurePosixPath(name.removeprefix(RUNTIME_PREFIX))
            destination = staging.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if member["kind"] == "symlink":
                destination.symlink_to(member["target"])
            else:
                destination.write_bytes(member["payload"])
                destination.chmod(int(member["mode"]) & 0o777)
        bin_root = staging / "node_modules" / ".bin"
        versions = {}
        for provider, executable in (("tree-sitter", "tree-sitter"), ("scip", "scip-typescript"), ("lsp", "typescript-language-server")):
            if not (bin_root / executable).exists():
                raise ValueError(f"installed Node provider executable missing: {executable}")
            versions[provider] = next(str(item["version"]) for item in archive["lock"]["packages"] if item.get("provider") == provider and item.get("executable"))
        identity = {"schema": INSTALLATION_SCHEMA, "provider_id": PROVIDER_ID, "providers": list(PROVIDER_IDS), "owner": "abyss-machine", "artifact_class": ARTIFACT_CLASS, "contract_surface_id": CONTRACT_SURFACE_ID, "bundle_manifest_ref": BUNDLE_MANIFEST_REF, "subject_digest": inspection["artifact"]["subject_digest"], "archive_sha256": archive["archive_sha256"], "source_ref": inspection["artifact"]["source_ref"], "versions": versions, "installed_at": _utc_now(), "bin_root": str(target / "node_modules" / ".bin")}
        (staging / METADATA_NAME).write_bytes(_canonical_json(archive["metadata"]) + b"\n")
        (staging / "installation.json").write_bytes(_canonical_json(identity) + b"\n")
        os.rename(staging, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    result.update({"status": "installed", "installation": identity, "written": [str(target)]})
    return result


__all__ = ["ARCHIVE_SCHEMA", "build_node_provider_archive", "inspect_node_provider_artifact", "install_node_provider_artifact", "read_node_provider_archive"]

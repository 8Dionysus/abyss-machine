"""Artifact route for Security, SBOM, provenance, and document providers.

The archive contains an exact offline wheelhouse.  It is a candidate until the
existing artifact bundle verifier and registry trust gate admit the aggregate
subject.  Installation never resolves packages from the network.
"""

from __future__ import annotations

from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile
from typing import Any, Callable, Mapping, Sequence

from .code_intelligence_provider import (
    ARTIFACT_CLASS,
    BUNDLE_MANIFEST_REF,
    CONTRACT_SURFACE_ID,
    DEFAULT_ARTIFACT_ROOT,
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


ARCHIVE_SCHEMA = "abyss_machine_code_intelligence_adjacent_provider_archive_v1"
INSTALLATION_SCHEMA = "abyss_machine_code_intelligence_adjacent_provider_installation_v1"
PROVIDER_ID = "adjacent-python-providers"
PROVIDER_IDS = ("semgrep", "syft", "in-toto", "markitdown")
METADATA_NAME = "provider.json"
LOCK_NAME = "provider-lock.json"
MAX_ARCHIVE_BYTES = 1024 * 1024 * 1024
MAX_MEMBER_BYTES = 256 * 1024 * 1024
MAX_FILES = 256


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name and not path.is_absolute() and ".." not in path.parts and "\\" not in name)


def _read_lock(path: str | Path) -> dict[str, Any]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema") != "abyss_machine_code_intelligence_adjacent_provider_lock_v1":
        raise ValueError("adjacent provider lock schema mismatch")
    packages = document.get("packages")
    binaries = document.get("binaries")
    package_providers = {str(item.get("provider")) for item in packages if isinstance(item, Mapping)} if isinstance(packages, list) else set()
    binary_providers = {str(item.get("provider")) for item in binaries if isinstance(item, Mapping)} if isinstance(binaries, list) else set()
    if not isinstance(packages, list) or not isinstance(binaries, list) or package_providers | binary_providers != set(PROVIDER_IDS):
        raise ValueError("adjacent provider lock must bind Semgrep, Syft, in-toto, and MarkItDown")
    for package in packages:
        if not isinstance(package, Mapping):
            raise ValueError("adjacent provider package entry must be an object")
        digest = str(package.get("sha256") or "")
        filename = str(package.get("filename") or "")
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError("adjacent provider package sha256 is invalid")
        if not _safe_member(filename) or PurePosixPath(filename).name != filename:
            raise ValueError("adjacent provider package filename is invalid")
    for binary in binaries:
        if not isinstance(binary, Mapping) or not _safe_member(str(binary.get("executable") or "")):
            raise ValueError("adjacent provider binary entry is invalid")
        digest = str(binary.get("binary_sha256") or "")
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError("adjacent provider binary sha256 is invalid")
    return document


def _tar_info(name: str, payload: bytes, mode: int = 0o644) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    info.mode = mode
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.type = tarfile.REGTYPE
    info.pax_headers = {}
    return info


def build_adjacent_provider_archive(
    wheelhouse: str | Path,
    binary_root: str | Path,
    output: str | Path,
    *,
    lock_path: str | Path,
    source_ref: str,
    platform: str,
) -> dict[str, Any]:
    """Build a deterministic offline wheelhouse artifact from downloaded wheels."""

    if not _safe_source_ref(source_ref):
        raise ValueError("source_ref must be a qualified source: or commit: reference")
    lock = _read_lock(lock_path)
    wheel_root = Path(wheelhouse).resolve()
    binary_base = Path(binary_root).resolve()
    wheels = sorted(path for path in wheel_root.glob("*.whl") if path.is_file())
    if not wheels or len(wheels) > MAX_FILES:
        raise ValueError("wheelhouse must contain a bounded non-empty wheel set")
    files: list[dict[str, Any]] = []
    payloads: dict[str, bytes] = {}
    for wheel in wheels:
        payload = wheel.read_bytes()
        if len(payload) > MAX_MEMBER_BYTES:
            raise ValueError(f"wheel exceeds bounded size: {wheel.name}")
        digest = hashlib.sha256(payload).hexdigest()
        name = f"wheelhouse/{wheel.name}"
        files.append({"path": name, "sha256": f"sha256:{digest}", "bytes": len(payload)})
        payloads[name] = payload
    by_name = {item["path"].split("/", 1)[1]: item["sha256"].split(":", 1)[1] for item in files}
    for package in lock["packages"]:
        if by_name.get(str(package["filename"])) != str(package["sha256"]):
            raise ValueError(f"locked wheel missing or digest mismatch: {package['filename']}")
    for binary in lock["binaries"]:
        executable = str(binary["executable"])
        path = binary_base / executable
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if digest != str(binary["binary_sha256"]):
            raise ValueError(f"locked binary missing or digest mismatch: {executable}")
        name = f"bin/{executable}"
        files.append({"path": name, "sha256": f"sha256:{digest}", "bytes": len(payload), "mode": 493})
        payloads[name] = payload
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
            "Runtime health does not establish semantic proof or owner acceptance."
        ],
    }
    entries = {METADATA_NAME: _canonical_json(metadata) + b"\n", LOCK_NAME: _canonical_json(lock) + b"\n", **payloads}
    tar_buffer = io.BytesIO()
    # Python wheels may legitimately exceed USTAR's 100-byte name field.
    # GNU long-name records stay deterministic here because entry order,
    # ownership, permissions, and timestamps are all fixed explicitly.
    with tarfile.open(fileobj=tar_buffer, mode="w", format=tarfile.GNU_FORMAT) as archive:
        for name in sorted(entries):
            payload = entries[name]
            archive.addfile(_tar_info(name, payload), io.BytesIO(payload))
    compressed = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed, mode="wb", filename="", mtime=0, compresslevel=9) as stream:
        stream.write(tar_buffer.getvalue())
    archive_bytes = compressed.getvalue()
    if len(archive_bytes) > MAX_ARCHIVE_BYTES:
        raise ValueError("adjacent provider archive exceeds bounded size")
    target = Path(output).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.read_bytes() != archive_bytes:
            raise FileExistsError(f"refusing to replace provider artifact: {target}")
        status = "already_present"
    else:
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent))
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            temporary.write_bytes(archive_bytes)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        status = "built"
    return {
        "schema": "abyss_machine_code_intelligence_adjacent_provider_build_v1",
        "status": status,
        "provider_id": PROVIDER_ID,
        "output": str(target),
        "archive_sha256": _sha256_bytes(archive_bytes),
        "archive_bytes": len(archive_bytes),
        "metadata": metadata,
        "admission_status": "not_admitted",
    }


def read_adjacent_provider_archive(path: str | Path) -> dict[str, Any]:
    archive_path = Path(path).resolve()
    if not archive_path.is_file() or archive_path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("adjacent provider archive is missing or too large")
    members: dict[str, bytes] = {}
    with tarfile.open(archive_path, mode="r:gz") as archive:
        for member in archive.getmembers():
            if not member.isreg() or not _safe_member(member.name) or member.name in members:
                raise ValueError(f"unsafe adjacent provider archive member: {member.name}")
            if member.name not in {METADATA_NAME, LOCK_NAME} and not member.name.startswith(("wheelhouse/", "bin/")):
                raise ValueError(f"unexpected adjacent provider archive member: {member.name}")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError(f"unreadable adjacent provider archive member: {member.name}")
            payload = stream.read(MAX_MEMBER_BYTES + 1)
            if len(payload) > MAX_MEMBER_BYTES:
                raise ValueError(f"oversized adjacent provider archive member: {member.name}")
            members[member.name] = payload
    if METADATA_NAME not in members or LOCK_NAME not in members or len(members) > MAX_FILES + 2:
        raise ValueError("adjacent provider archive member set is incomplete")
    metadata = json.loads(members[METADATA_NAME])
    lock = json.loads(members[LOCK_NAME])
    if not isinstance(metadata, dict) or metadata.get("schema") != ARCHIVE_SCHEMA:
        raise ValueError("adjacent provider metadata schema mismatch")
    if metadata.get("provider_id") != PROVIDER_ID or metadata.get("providers") != list(PROVIDER_IDS):
        raise ValueError("adjacent provider metadata identity mismatch")
    if metadata.get("lock_digest") != _sha256_bytes(_canonical_json(lock)):
        raise ValueError("adjacent provider lock digest mismatch")
    files = metadata.get("files")
    if not isinstance(files, list):
        raise ValueError("adjacent provider file inventory missing")
    expected = {str(item.get("path")): item for item in files if isinstance(item, Mapping)}
    actual_payloads = {name for name in members if name.startswith(("wheelhouse/", "bin/"))}
    if set(expected) != actual_payloads:
        raise ValueError("adjacent provider payload inventory mismatch")
    for name, item in expected.items():
        payload = members[name]
        if item.get("sha256") != _sha256_bytes(payload) or item.get("bytes") != len(payload):
            raise ValueError(f"adjacent provider wheel identity mismatch: {name}")
    return {
        "provider_id": PROVIDER_ID,
        "archive_path": str(archive_path),
        "archive_sha256": _digest_file(archive_path),
        "archive_bytes": archive_path.stat().st_size,
        "metadata": metadata,
        "lock": lock,
        "members": members,
    }


def inspect_adjacent_provider_artifact(
    archive_path: str | Path,
    bundle_dir: str | Path,
    *,
    subject_root: str | Path,
    registry_dir: str | Path,
    source_root: str | Path = DEFAULT_SOURCE_ROOT,
    expected_source_ref: str = "",
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": "abyss_machine_code_intelligence_adjacent_provider_inspection_v1",
        "provider_id": PROVIDER_ID,
        "status": "blocked",
        "checks": {},
    }
    try:
        archive = read_adjacent_provider_archive(archive_path)
    except Exception as exc:
        result["checks"]["archive"] = {"ok": False, "error_type": type(exc).__name__, "reason": str(exc)}
        return result
    result["checks"]["archive"] = {"ok": True}
    bundle = Path(bundle_dir).resolve()
    subject_base = Path(subject_root).resolve()
    source_base = Path(source_root).resolve()
    try:
        binding = _subject_binding(archive, bundle, subject_root=subject_base, source_root=source_base)
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
        verification = _artifact_tools().verify_bundle(bundle, subject_root=subject_base, repo_root=source_base, write=False)
        result["checks"]["bundle_verify"] = _summarize_verify(verification)
    except Exception as exc:
        result["checks"]["bundle_verify"] = {"ok": False, "error_type": type(exc).__name__}
    if subject_digest and _safe_source_ref(source_ref):
        try:
            gate = _trust_gate(Path(registry_dir).resolve(), subject_digest=subject_digest, source_ref=source_ref)
            result["trust_gate"] = {
                "ok": gate.get("ok") is True and gate.get("verdict") == "allow",
                "verdict": gate.get("verdict"),
                "record_id": gate.get("record_id"),
                "latest_record_id": gate.get("latest_record_id"),
                "reasons": list(gate.get("reasons", []))[:16],
                "blockers": list(gate.get("blockers", []))[:16],
            }
        except Exception as exc:
            result["trust_gate"] = {"ok": False, "verdict": "unknown", "error_type": type(exc).__name__}
    else:
        result["trust_gate"] = {"ok": False, "verdict": "unknown", "reasons": ["subject_binding_not_ready"]}
    if all(result["checks"].get(name, {}).get("ok") is True for name in ("archive", "subject_binding", "bundle_verify")) and result["trust_gate"].get("ok") is True:
        result["status"] = "admitted"
    return result


def install_adjacent_provider_artifact(
    archive_path: str | Path,
    bundle_dir: str | Path,
    *,
    subject_root: str | Path,
    registry_dir: str | Path = DEFAULT_REGISTRY_DIR,
    runtime_root: str | Path = DEFAULT_RUNTIME_ROOT,
    source_root: str | Path = DEFAULT_SOURCE_ROOT,
    expected_source_ref: str = "",
    apply: bool = False,
    preflight: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    inspection = inspect_adjacent_provider_artifact(
        archive_path, bundle_dir, subject_root=subject_root, registry_dir=registry_dir,
        source_root=source_root, expected_source_ref=expected_source_ref,
    )
    result: dict[str, Any] = {
        "schema": "abyss_machine_code_intelligence_adjacent_provider_install_v1",
        "provider_id": PROVIDER_ID,
        "status": "blocked",
        "inspection": inspection,
        "written": [],
        "claim_limit": "Installation is not deployment, semantic proof, or owner acceptance.",
    }
    if inspection.get("status") != "admitted":
        result["blocking_reasons"] = ["exact_adjacent_provider_artifact_not_admitted"]
        return result
    archive = read_adjacent_provider_archive(archive_path)
    runtime_base = Path(runtime_root).resolve()
    target = runtime_base / "providers" / PROVIDER_ID
    identity_path = target / "installation.json"
    if identity_path.is_file():
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        if identity.get("subject_digest") == inspection.get("artifact", {}).get("subject_digest"):
            result.update({"status": "already_installed", "installation": identity})
            return result
    if target.exists() or target.is_symlink():
        result["blocking_reasons"] = ["different_adjacent_provider_installation_exists"]
        return result
    if not apply:
        result.update({"status": "ready_to_install", "would_install": str(target)})
        return result
    preflight_result = (preflight(archive_bytes=archive["archive_bytes"], runtime_root=runtime_base) if preflight else run_owner_preflights(archive_bytes=archive["archive_bytes"], runtime_root=runtime_base))
    result["preflight"] = preflight_result
    if preflight_result.get("ok") is not True:
        result["blocking_reasons"] = ["owner_write_preflight_denied"]
        return result
    providers_dir = runtime_base / "providers"
    providers_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{PROVIDER_ID}.staging-", dir=str(providers_dir)))
    try:
        wheelhouse = staging / "wheelhouse"
        wheelhouse.mkdir()
        for name, payload in archive["members"].items():
            if name.startswith("wheelhouse/"):
                (wheelhouse / PurePosixPath(name).name).write_bytes(payload)
        venv = staging / "runtime"
        subprocess.run([os.environ.get("PYTHON", "python3"), "-m", "venv", str(venv)], check=True, timeout=120)
        packages = [f"{item['name']}=={item['version']}" for item in archive["lock"]["packages"]]
        subprocess.run(
            [str(venv / "bin" / "python"), "-m", "pip", "install", "--no-index", "--find-links", str(wheelhouse), *packages],
            check=True, timeout=600, stdout=subprocess.DEVNULL,
        )
        versions: dict[str, str] = {}
        for item in archive["lock"]["packages"]:
            executable = venv / "bin" / str(item["executable"])
            if not executable.is_file() or not os.access(executable, os.X_OK):
                raise ValueError(f"installed provider executable missing: {item['executable']}")
            versions[str(item["provider"])] = str(item["version"])
        for item in archive["lock"]["binaries"]:
            executable = venv / "bin" / str(item["executable"])
            executable.write_bytes(archive["members"][f"bin/{item['executable']}"])
            executable.chmod(0o755)
            versions[str(item["provider"])] = str(item["version"])
        identity = {
            "schema": INSTALLATION_SCHEMA,
            "provider_id": PROVIDER_ID,
            "providers": list(PROVIDER_IDS),
            "owner": "abyss-machine",
            "artifact_class": ARTIFACT_CLASS,
            "contract_surface_id": CONTRACT_SURFACE_ID,
            "bundle_manifest_ref": BUNDLE_MANIFEST_REF,
            "subject_digest": inspection["artifact"]["subject_digest"],
            "archive_sha256": archive["archive_sha256"],
            "source_ref": inspection["artifact"]["source_ref"],
            "versions": versions,
            "installed_at": _utc_now(),
        }
        (staging / METADATA_NAME).write_bytes(_canonical_json(archive["metadata"]) + b"\n")
        (staging / "installation.json").write_bytes(_canonical_json(identity) + b"\n")
        shutil.rmtree(wheelhouse)
        os.rename(staging, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    result.update({"status": "installed", "installation": identity, "written": [str(target)]})
    return result


__all__ = [
    "ARCHIVE_SCHEMA",
    "build_adjacent_provider_archive",
    "inspect_adjacent_provider_artifact",
    "install_adjacent_provider_artifact",
    "read_adjacent_provider_archive",
]

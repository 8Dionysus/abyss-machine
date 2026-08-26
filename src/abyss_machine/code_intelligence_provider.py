"""Owner-controlled Universal Ctags provider packaging and consumption.

This module is the narrow MACHINE implementation for the first real
code-intelligence provider artifact.  It can build a deterministic archive
from an already installed Universal Ctags executable, bind that archive to an
artifact bundle, and consume it only after the existing OS Abyss artifact
trust-gate allows the exact subject.  It deliberately does not create trust
roots, sign artifacts, publish registries, start services, or claim semantic
proof.
"""

from __future__ import annotations

from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import selectors
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from typing import Any, Callable, Mapping, Sequence

from .code_intelligence_contracts import MACHINE_CONSUMER_ABI, code_intelligence_config


PROVIDER_ID = "universal-ctags"
ARTIFACT_CLASS = "runtime_or_container_artifact"
CONTRACT_SURFACE_ID = "code-intelligence-provider-route"
BUNDLE_MANIFEST_REF = "manifests/artifact_bundles/code_intelligence_provider.bundle.json"
ARCHIVE_SCHEMA = "abyss_machine_code_intelligence_provider_archive_v1"
INSTALLATION_SCHEMA = "abyss_machine_code_intelligence_installed_identity_v1"
PROVIDER_METADATA_NAME = "provider.json"
INSTALLATION_IDENTITY_NAME = "installation.json"
ARCHIVE_BINARY_NAME = "bin/ctags"
MAX_VERSION_OUTPUT_BYTES = 4096
MAX_SYMBOL_OUTPUT_BYTES = 512 * 1024
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_BINARY_BYTES = 128 * 1024 * 1024
DEFAULT_ARTIFACT_ROOT = Path("/srv/abyss-machine/artifacts/code-intelligence")
DEFAULT_RUNTIME_ROOT = Path("/srv/abyss-machine/runtimes/code-intelligence")
DEFAULT_REGISTRY_DIR = Path("/var/lib/abyss-machine/artifacts/bundle-registry")
DEFAULT_SUBJECT_STORE = Path("/var/lib/abyss-machine/artifacts/subjects")
DEFAULT_SOURCE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_FILE = Path("src/abyss_machine/code_intelligence_contracts.py")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _safe_source_ref(value: Any) -> bool:
    text = value if isinstance(value, str) else ""
    return bool(
        text
        and text == text.strip()
        and "\x00" not in text
        and not any(character.isspace() for character in text)
        and text.startswith(("source:", "commit:"))
    )


def _safe_relative(value: Any) -> bool:
    text = value if isinstance(value, str) else ""
    if not text or text != text.strip() or "\x00" in text or "\\" in text:
        return False
    path = PurePosixPath(text)
    return not path.is_absolute() and ".." not in path.parts and text != "."


def _bounded_process(
    command: Sequence[str],
    *,
    timeout: float,
    max_output_bytes: int,
) -> dict[str, Any]:
    """Run one local probe while retaining only bounded output prefixes."""

    process = subprocess.Popen(
        list(command),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        close_fds=True,
    )
    selector = selectors.DefaultSelector()
    buffers: dict[str, bytearray] = {"stdout": bytearray(), "stderr": bytearray()}
    streams: dict[int, tuple[str, Any]] = {}
    truncated = False
    timed_out = False
    try:
        assert process.stdout is not None
        assert process.stderr is not None
        for name, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, data=name)
            streams[stream.fileno()] = (name, stream)
        deadline = time.monotonic() + max(0.01, float(timeout))
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                process.kill()
                break
            events = selector.select(min(remaining, 0.25))
            if not events:
                continue
            for key, _ in events:
                stream = key.fileobj
                name = str(key.data)
                try:
                    chunk = os.read(stream.fileno(), 8192)
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(stream)
                    stream.close()
                    continue
                available = max_output_bytes - len(buffers[name])
                if available > 0:
                    buffers[name].extend(chunk[:available])
                if len(chunk) > max(0, available):
                    truncated = True
        if timed_out:
            process.kill()
        returncode = process.wait()
    finally:
        selector.close()
        if process.poll() is None:
            process.kill()
            process.wait()
        for _fd, (_name, stream) in list(streams.items()):
            if not stream.closed:
                stream.close()
    return {
        "returncode": returncode,
        "stdout": bytes(buffers["stdout"]),
        "stderr": bytes(buffers["stderr"]),
        "stdout_bytes": len(buffers["stdout"]),
        "stderr_bytes": len(buffers["stderr"]),
        "output_truncated": truncated,
        "timed_out": timed_out,
    }


def _decode(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value or "")


def _version_line(result: Mapping[str, Any]) -> str | None:
    for stream_name in ("stdout", "stderr"):
        for line in _decode(result.get(stream_name)).splitlines():
            normalized = " ".join(line.strip().split())
            if "Universal Ctags" in normalized:
                return normalized[:256]
    return None


def _require_executable(executable: str | Path) -> Path:
    path = Path(executable).expanduser().resolve()
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError(f"Universal Ctags executable is not runnable: {path}")
    if path.stat().st_size > MAX_BINARY_BYTES:
        raise ValueError("Universal Ctags executable exceeds the bounded provider size")
    return path


def _probe_version(executable: Path) -> str:
    result = _bounded_process(
        [str(executable), "--version"],
        timeout=5.0,
        max_output_bytes=MAX_VERSION_OUTPUT_BYTES,
    )
    version = _version_line(result)
    if result.get("timed_out") or result.get("returncode") != 0 or not version:
        raise ValueError("Universal Ctags version probe did not produce a healthy version")
    if result.get("output_truncated"):
        raise ValueError("Universal Ctags version probe output was truncated")
    return version


def _provider_metadata(executable: Path, *, version: str, source_ref: str, platform: str) -> dict[str, Any]:
    binary_digest = _digest_file(executable)
    return {
        "schema": ARCHIVE_SCHEMA,
        "provider_id": PROVIDER_ID,
        "display_name": "Universal Ctags",
        "version": version,
        "source_ref": source_ref,
        "platform": platform,
        "content_addressed": True,
        "archive_entries": [ARCHIVE_BINARY_NAME, PROVIDER_METADATA_NAME],
        "binary": {
            "path": ARCHIVE_BINARY_NAME,
            "sha256": binary_digest,
            "bytes": executable.stat().st_size,
        },
        "interface": {
            "format": "json-lines",
            "command": [
                "PROVIDER",
                "--output-format=json",
                "--fields=+ne",
                "--extras=+q",
                "--languages=Python",
                "-o",
                "-",
                "SOURCE_FILE",
            ],
            "raw_output": "discarded",
        },
        "claim_limits": [
            "The archive supplies a bounded symbol-navigation provider only.",
            "The provider does not establish semantic usefulness, proof, or eval acceptance.",
            "The provider is consumed only after the exact OS Abyss artifact trust-gate allows it.",
        ],
    }


def _tar_member(name: str, payload: bytes, *, mode: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    info.mode = mode
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.type = tarfile.REGTYPE
    info.pax_headers = {}
    return info


def _deterministic_archive(binary: bytes, metadata: Mapping[str, Any]) -> bytes:
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        metadata_bytes = _canonical_json(metadata) + b"\n"
        archive.addfile(_tar_member(ARCHIVE_BINARY_NAME, binary, mode=0o755), io.BytesIO(binary))
        archive.addfile(_tar_member(PROVIDER_METADATA_NAME, metadata_bytes, mode=0o644), io.BytesIO(metadata_bytes))
    gzip_buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=gzip_buffer, mode="wb", filename="", mtime=0, compresslevel=9) as compressed:
        compressed.write(tar_buffer.getvalue())
    return gzip_buffer.getvalue()


def _write_new_file(path: Path, payload: bytes, *, mode: int | None = None) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.is_file() and path.read_bytes() == payload:
            return False
        raise FileExistsError(f"refusing to replace an existing provider artifact: {path}")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        temporary.write_bytes(payload)
        if mode is not None:
            os.chmod(temporary, mode)
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return True


def build_provider_archive(
    executable: str | Path,
    output: str | Path,
    *,
    source_ref: str,
    platform: str | None = None,
) -> dict[str, Any]:
    """Build one deterministic, unsigned Universal Ctags archive."""

    if not _safe_source_ref(source_ref):
        raise ValueError("source_ref must be a qualified source: or commit: reference")
    binary_path = _require_executable(executable)
    version = _probe_version(binary_path)
    metadata = _provider_metadata(
        binary_path,
        version=version,
        source_ref=source_ref,
        platform=platform or sys.platform,
    )
    binary = binary_path.read_bytes()
    archive_bytes = _deterministic_archive(binary, metadata)
    output_path = Path(output).expanduser().resolve()
    if len(archive_bytes) > MAX_ARCHIVE_BYTES:
        raise ValueError("provider archive exceeds the bounded artifact size")
    written = _write_new_file(output_path, archive_bytes)
    return {
        "schema": "abyss_machine_code_intelligence_provider_build_v1",
        "status": "built" if written else "already_present",
        "provider_id": PROVIDER_ID,
        "artifact_class": ARTIFACT_CLASS,
        "output": str(output_path),
        "archive_sha256": _digest_bytes(archive_bytes),
        "archive_bytes": len(archive_bytes),
        "metadata": metadata,
        "signature_status": "not_signed",
        "promotion_status": "not_promoted",
        "admission_status": "not_admitted",
        "claim_limit": "Build output is an unsigned candidate and cannot be consumed as a trusted provider.",
    }


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def read_provider_archive(path: str | Path) -> dict[str, Any]:
    """Read and validate the exact two-file provider archive without extracting it."""

    archive_path = Path(path).expanduser().resolve()
    if not archive_path.is_file():
        raise FileNotFoundError(archive_path)
    if archive_path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("provider archive exceeds the bounded artifact size")
    members: dict[str, bytes] = {}
    with tarfile.open(archive_path, mode="r:gz") as archive:
        for member in archive.getmembers():
            name = member.name
            if not _safe_relative(name) or name not in {ARCHIVE_BINARY_NAME, PROVIDER_METADATA_NAME}:
                raise ValueError(f"provider archive contains an unsafe or unexpected member: {name}")
            if name in members or not member.isreg():
                raise ValueError(f"provider archive member is not one regular file: {name}")
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ValueError(f"provider archive member cannot be read: {name}")
            limit = MAX_BINARY_BYTES if name == ARCHIVE_BINARY_NAME else 256 * 1024
            payload = extracted.read(limit + 1)
            if len(payload) > limit:
                raise ValueError(f"provider archive member exceeds its bounded size: {name}")
            members[name] = payload
    expected_members = {ARCHIVE_BINARY_NAME, PROVIDER_METADATA_NAME}
    if set(members) != expected_members:
        raise ValueError("provider archive must contain exactly bin/ctags and provider.json")
    try:
        metadata = json.loads(members[PROVIDER_METADATA_NAME].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("provider.json is not valid UTF-8 JSON") from exc
    if not isinstance(metadata, dict):
        raise ValueError("provider.json must be an object")
    if metadata.get("schema") != ARCHIVE_SCHEMA or metadata.get("provider_id") != PROVIDER_ID:
        raise ValueError("provider.json does not identify the Universal Ctags provider archive")
    if not _safe_source_ref(metadata.get("source_ref")):
        raise ValueError("provider.json source_ref is not qualified")
    if metadata.get("archive_entries") != [ARCHIVE_BINARY_NAME, PROVIDER_METADATA_NAME]:
        raise ValueError("provider.json archive_entries are not canonical")
    binary = members[ARCHIVE_BINARY_NAME]
    binary_record = metadata.get("binary") if isinstance(metadata.get("binary"), dict) else {}
    if binary_record.get("path") != ARCHIVE_BINARY_NAME:
        raise ValueError("provider.json binary path is not canonical")
    if binary_record.get("sha256") != _digest_bytes(binary) or binary_record.get("bytes") != len(binary):
        raise ValueError("provider.json binary identity does not match the archive")
    if "Universal Ctags" not in str(metadata.get("version") or ""):
        raise ValueError("provider.json version is not a Universal Ctags version")
    interface = metadata.get("interface") if isinstance(metadata.get("interface"), dict) else {}
    if interface.get("format") != "json-lines" or interface.get("raw_output") != "discarded":
        raise ValueError("provider.json interface does not declare the bounded JSON-lines contract")
    command = interface.get("command")
    if command != [
        "PROVIDER",
        "--output-format=json",
        "--fields=+ne",
        "--extras=+q",
        "--languages=Python",
        "-o",
        "-",
        "SOURCE_FILE",
    ]:
        raise ValueError("provider.json interface command is not canonical")
    return {
        "provider_id": PROVIDER_ID,
        "archive_path": str(archive_path),
        "archive_sha256": _digest_file(archive_path),
        "archive_bytes": archive_path.stat().st_size,
        "metadata": metadata,
        "binary": binary,
    }


def _artifact_tools() -> Any:
    from . import artifact_bundles

    return artifact_bundles


def _subject_binding(
    archive: Mapping[str, Any],
    bundle_dir: Path,
    *,
    subject_root: Path,
    source_root: Path,
) -> dict[str, Any]:
    tools = _artifact_tools()
    subjects_path = bundle_dir / "artifact.subjects.json"
    identity_path = bundle_dir / "artifact.identity.json"
    subjects = _read_json(subjects_path)
    identity = _read_json(identity_path)
    files = subjects.get("files")
    errors: list[str] = []
    if subjects.get("schema") != "abyss_machine_artifact_subjects_v1":
        errors.append("artifact.subjects.json schema mismatch")
    if identity.get("artifact_class") != ARTIFACT_CLASS:
        errors.append("artifact.identity.json artifact_class mismatch")
    if identity.get("contract_surface_id") != CONTRACT_SURFACE_ID:
        errors.append("artifact.identity.json contract_surface_id mismatch")
    if identity.get("bundle_manifest_ref") != BUNDLE_MANIFEST_REF:
        errors.append("artifact.identity.json bundle_manifest_ref mismatch")
    if not isinstance(files, list) or not files:
        errors.append("artifact.subjects.json files are missing")
        files = []
    aggregate = tools._stable_digest(files)
    if subjects.get("aggregate_digest") != aggregate:
        errors.append("artifact.subjects.json aggregate_digest mismatch")
    try:
        archive_relative = Path(str(archive.get("archive_path") or "")).resolve()
        archive_relative = archive_relative.relative_to(subject_root.resolve()).as_posix()
    except (ValueError, OSError) as exc:
        errors.append(f"archive is outside the supplied subject root: {type(exc).__name__}")
        archive_relative = ""
    matched = [item for item in files if isinstance(item, dict) and item.get("path") == archive_relative]
    if len(matched) != 1:
        errors.append("artifact.subjects.json does not bind exactly the selected provider archive")
    elif matched[0].get("sha256") != archive.get("archive_sha256"):
        errors.append("artifact.subjects.json archive digest mismatch")
    source_ref = str(identity.get("source_ref") or archive.get("metadata", {}).get("source_ref") or "")
    if not _safe_source_ref(source_ref):
        errors.append("provider source_ref is missing or unqualified")
    return {
        "ok": not errors,
        "archive_relative_path": archive_relative,
        "subject_digest": subjects.get("aggregate_digest"),
        "source_ref": source_ref,
        "artifact_identity": {
            "artifact_class": identity.get("artifact_class"),
            "contract_surface_id": identity.get("contract_surface_id"),
            "bundle_manifest_ref": identity.get("bundle_manifest_ref"),
            "source_ref": identity.get("source_ref"),
        },
        "errors": errors,
        "source_root": str(source_root),
    }


def _summarize_verify(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ok": result.get("ok") is True,
        "missing": [str(item) for item in result.get("missing", []) if str(item)][:16],
        "errors": [str(item) for item in result.get("errors", []) if str(item)][:16],
        "warnings": [str(item) for item in result.get("warnings", []) if str(item)][:16],
        "required_controls": [str(item) for item in result.get("required_controls", []) if str(item)],
    }


def _trust_gate(
    registry_dir: Path,
    *,
    subject_digest: str,
    source_ref: str,
) -> dict[str, Any]:
    tools = _artifact_tools()
    return tools.trust_gate(
        registry_dir,
        artifact_class=ARTIFACT_CLASS,
        subject_digest=subject_digest,
        consumer_intent="runtime",
        expected_source_repo="abyss-machine",
        expected_source_ref=source_ref,
        expected_trust_root_mode="oci_registry",
        require_latest=True,
    )


def inspect_provider_artifact(
    archive_path: str | Path,
    bundle_dir: str | Path,
    *,
    subject_root: str | Path,
    registry_dir: str | Path,
    source_root: str | Path = DEFAULT_SOURCE_ROOT,
    expected_source_ref: str = "",
) -> dict[str, Any]:
    """Inspect one candidate and return the exact trust/admission posture."""

    archive_file = Path(archive_path).expanduser().resolve()
    bundle = Path(bundle_dir).expanduser().resolve()
    subject_base = Path(subject_root).expanduser().resolve()
    source_base = Path(source_root).expanduser().resolve()
    result: dict[str, Any] = {
        "schema": "abyss_machine_code_intelligence_provider_inspection_v1",
        "operation": "inspect",
        "provider_id": PROVIDER_ID,
        "artifact_class": ARTIFACT_CLASS,
        "status": "blocked",
        "checks": {},
        "claim_limits": [
            "Source readiness, producer validation, registry promotion, consumer admission, installation, runtime health, semantic proof, landing, and owner acceptance remain separate claims.",
            "An absent or denied trust-gate never permits provider execution or installation.",
        ],
    }
    try:
        archive = read_provider_archive(archive_file)
        result["archive"] = {
            "ok": True,
            "path": str(archive_file),
            "sha256": archive["archive_sha256"],
            "bytes": archive["archive_bytes"],
            "version": archive["metadata"].get("version"),
            "source_ref": archive["metadata"].get("source_ref"),
            "binary_sha256": archive["metadata"].get("binary", {}).get("sha256"),
        }
    except Exception as exc:
        result["checks"]["archive"] = {"ok": False, "error_type": type(exc).__name__, "reason": str(exc)}
        return result
    result["checks"]["archive"] = {"ok": True}
    try:
        binding = _subject_binding(archive, bundle, subject_root=subject_base, source_root=source_base)
    except Exception as exc:
        binding = {"ok": False, "errors": [f"subject binding could not be read: {type(exc).__name__}"]}
    result["subject_binding"] = binding
    result["checks"]["subject_binding"] = {"ok": binding.get("ok") is True, "errors": binding.get("errors", [])}
    subject_digest = str(binding.get("subject_digest") or "")
    source_ref = expected_source_ref or str(binding.get("source_ref") or archive["metadata"].get("source_ref") or "")
    if expected_source_ref and source_ref != str(binding.get("source_ref") or ""):
        result["checks"]["subject_binding"]["errors"].append("expected source_ref does not match bundle source_ref")
        result["subject_binding"]["ok"] = False
    result["artifact"] = {
        "subject_digest": subject_digest or None,
        "source_ref": source_ref or None,
        "bundle_dir": str(bundle),
        "manifest_ref": BUNDLE_MANIFEST_REF,
    }
    try:
        verify = _artifact_tools().verify_bundle(
            bundle,
            subject_root=subject_base,
            repo_root=source_base,
            write=False,
        )
        result["checks"]["bundle_verify"] = _summarize_verify(verify)
    except Exception as exc:
        result["checks"]["bundle_verify"] = {"ok": False, "error_type": type(exc).__name__}
    if subject_digest and source_ref and _safe_source_ref(source_ref):
        try:
            gate = _trust_gate(Path(registry_dir).expanduser().resolve(), subject_digest=subject_digest, source_ref=source_ref)
            result["trust_gate"] = {
                "ok": gate.get("ok") is True and gate.get("verdict") == "allow",
                "verdict": gate.get("verdict"),
                "record_id": gate.get("record_id"),
                "latest_record_id": gate.get("latest_record_id"),
                "reasons": [str(item) for item in gate.get("reasons", []) if str(item)][:16],
                "blockers": [str(item) for item in gate.get("blockers", []) if str(item)][:16],
                "manual_review": [str(item) for item in gate.get("manual_review", []) if str(item)][:16],
                "warnings": [str(item) for item in gate.get("warnings", []) if str(item)][:16],
            }
        except Exception as exc:
            result["trust_gate"] = {"ok": False, "verdict": "unknown", "error_type": type(exc).__name__}
    else:
        result["trust_gate"] = {"ok": False, "verdict": "unknown", "reasons": ["subject_binding_not_ready"]}
    if (
        result["checks"].get("archive", {}).get("ok") is True
        and result["checks"].get("subject_binding", {}).get("ok") is True
        and result["checks"].get("bundle_verify", {}).get("ok") is True
        and result.get("trust_gate", {}).get("ok") is True
    ):
        result["status"] = "admitted"
    return result


def _installed_identity(runtime_root: Path) -> dict[str, Any]:
    target = runtime_root / "providers" / PROVIDER_ID
    identity_path = target / INSTALLATION_IDENTITY_NAME
    metadata_path = target / PROVIDER_METADATA_NAME
    executable = target / ARCHIVE_BINARY_NAME
    if target.is_symlink() or not identity_path.is_file() or not metadata_path.is_file() or executable.is_symlink() or not executable.is_file():
        return {"ok": False, "target": str(target), "errors": ["installed provider identity or executable is missing"]}
    try:
        identity = _read_json(identity_path)
        metadata = _read_json(metadata_path)
    except Exception as exc:
        return {"ok": False, "target": str(target), "errors": [f"installed identity unreadable:{type(exc).__name__}"]}
    errors: list[str] = []
    if identity.get("schema") != INSTALLATION_SCHEMA or identity.get("provider_id") != PROVIDER_ID:
        errors.append("installed identity schema/provider mismatch")
    if metadata.get("schema") != ARCHIVE_SCHEMA or metadata.get("provider_id") != PROVIDER_ID:
        errors.append("installed provider metadata mismatch")
    actual_digest = _digest_file(executable)
    expected_digest = str(metadata.get("binary", {}).get("sha256") or "")
    if actual_digest != expected_digest or identity.get("digest") != actual_digest:
        errors.append("installed executable digest mismatch")
    if not os.access(executable, os.X_OK):
        errors.append("installed executable is not runnable")
    return {
        "ok": not errors,
        "target": str(target),
        "executable": str(executable),
        "identity": identity,
        "metadata": metadata,
        "errors": errors,
    }


def _preflight_summary(document: Mapping[str, Any], *, command: str, returncode: int | None) -> dict[str, Any]:
    return {
        "command": command,
        "returncode": returncode,
        "ok": document.get("ok") is True and returncode == 0,
        "status": document.get("status"),
        "blockers": [str(item) for item in document.get("blockers", []) if str(item)][:16],
        "errors": [str(item) for item in document.get("errors", []) if str(item)][:16],
        "warnings": [str(item) for item in document.get("warnings", []) if str(item)][:16],
    }


def run_owner_preflights(*, archive_bytes: int, runtime_root: Path) -> dict[str, Any]:
    """Run the two read-only owner controls required before durable install."""

    executable = shutil.which("abyss-machine") or "/usr/local/bin/abyss-machine"
    if not Path(executable).is_file() or not os.access(executable, os.X_OK):
        return {"ok": False, "preflights": [{"command": "abyss-machine", "ok": False, "reason": "owner command not found"}]}
    commands = [
        (
            "storage-write-preflight",
            [
                "storage",
                "write-preflight",
                "--kind",
                "artifact",
                "--bytes",
                str(max(1, archive_bytes)),
                "--target",
                str(runtime_root),
                "--json",
            ],
        ),
        (
            "changes-preflight",
            [
                "changes",
                "preflight",
                "--intent",
                "install exact Universal Ctags code-intelligence provider artifact",
                "--surface",
                "runtimes/code-intelligence",
                "--json",
            ],
        ),
    ]
    summaries: list[dict[str, Any]] = []
    for label, arguments in commands:
        result = _bounded_process([executable, *arguments], timeout=30.0, max_output_bytes=64 * 1024)
        try:
            document = json.loads(_decode(result.get("stdout")))
        except (json.JSONDecodeError, TypeError):
            document = {}
        if not isinstance(document, dict):
            document = {}
        summaries.append(_preflight_summary(document, command=label, returncode=result.get("returncode")))
    return {"ok": all(item.get("ok") is True for item in summaries), "preflights": summaries}


def install_provider(
    archive_path: str | Path,
    bundle_dir: str | Path,
    *,
    subject_root: str | Path,
    runtime_root: str | Path = DEFAULT_RUNTIME_ROOT,
    registry_dir: str | Path = DEFAULT_REGISTRY_DIR,
    source_root: str | Path = DEFAULT_SOURCE_ROOT,
    expected_source_ref: str = "",
    apply: bool = False,
    preflight: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Install only a provider whose exact bundle and trust-gate are admitted."""

    inspection = inspect_provider_artifact(
        archive_path,
        bundle_dir,
        subject_root=subject_root,
        registry_dir=registry_dir,
        source_root=source_root,
        expected_source_ref=expected_source_ref,
    )
    result: dict[str, Any] = {
        "schema": "abyss_machine_code_intelligence_provider_install_v1",
        "operation": "install",
        "provider_id": PROVIDER_ID,
        "status": "blocked",
        "inspection": inspection,
        "written": [],
        "claim_limit": "Installation is not deployment, lifecycle acceptance, semantic proof, or owner acceptance.",
    }
    if inspection.get("status") != "admitted":
        result["blocking_reasons"] = ["exact_provider_artifact_not_admitted"]
        return result
    runtime_base = Path(runtime_root).expanduser().resolve()
    archive = read_provider_archive(archive_path)
    target = runtime_base / "providers" / PROVIDER_ID
    existing = _installed_identity(runtime_base)
    if existing.get("ok") is True:
        identity = existing.get("identity") if isinstance(existing.get("identity"), dict) else {}
        if identity.get("subject_digest") == inspection.get("artifact", {}).get("subject_digest"):
            result.update({"status": "already_installed", "installation": existing})
            return result
    if target.exists() or target.is_symlink():
        result["blocking_reasons"] = ["different_provider_installation_exists; replacement is not implicit"]
        result["existing"] = existing
        return result
    if not apply:
        result.update(
            {
                "status": "ready_to_install",
                "would_install": {
                    "target": str(target),
                    "subject_digest": inspection.get("artifact", {}).get("subject_digest"),
                    "source_ref": inspection.get("artifact", {}).get("source_ref"),
                },
            }
        )
        return result
    preflight_result = (
        preflight(archive_bytes=int(archive["archive_bytes"]), runtime_root=runtime_base)
        if preflight is not None
        else run_owner_preflights(archive_bytes=int(archive["archive_bytes"]), runtime_root=runtime_base)
    )
    result["preflight"] = preflight_result
    if preflight_result.get("ok") is not True:
        result["blocking_reasons"] = ["owner_write_preflight_denied"]
        return result
    providers_dir = runtime_base / "providers"
    providers_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{PROVIDER_ID}.staging-", dir=str(providers_dir)))
    target_claimed = False
    try:
        binary_path = staging / ARCHIVE_BINARY_NAME
        binary_path.parent.mkdir(parents=True, exist_ok=True)
        binary_path.write_bytes(archive["binary"])
        os.chmod(binary_path, 0o755)
        (staging / PROVIDER_METADATA_NAME).write_bytes(_canonical_json(archive["metadata"]) + b"\n")
        identity = {
            "schema": INSTALLATION_SCHEMA,
            "provider_id": PROVIDER_ID,
            "owner": "abyss-machine",
            "artifact_class": ARTIFACT_CLASS,
            "contract_surface_id": CONTRACT_SURFACE_ID,
            "bundle_manifest_ref": BUNDLE_MANIFEST_REF,
            "subject_digest": inspection.get("artifact", {}).get("subject_digest"),
            "archive_sha256": archive["archive_sha256"],
            "source_ref": inspection.get("artifact", {}).get("source_ref"),
            "version": archive["metadata"].get("version"),
            "executable_or_path": f"providers/{PROVIDER_ID}/{ARCHIVE_BINARY_NAME}",
            "digest": archive["metadata"].get("binary", {}).get("sha256"),
            "installed_at": _utc_now(),
            "trust_gate": {
                "verdict": inspection.get("trust_gate", {}).get("verdict"),
                "record_id": inspection.get("trust_gate", {}).get("record_id"),
                "latest_record_id": inspection.get("trust_gate", {}).get("latest_record_id"),
            },
        }
        (staging / INSTALLATION_IDENTITY_NAME).write_bytes(_canonical_json(identity) + b"\n")
        # Claim the final directory without replacement.  The earlier
        # existence check is useful for a clear result, but mkdir is the
        # no-overwrite operation that closes the race with another installer.
        target.mkdir(mode=0o755)
        target_claimed = True
        (target / "bin").mkdir(mode=0o755)
        for relative in (ARCHIVE_BINARY_NAME, PROVIDER_METADATA_NAME, INSTALLATION_IDENTITY_NAME):
            staged_file = staging / relative
            installed_file = target / relative
            os.link(staged_file, installed_file)
            staged_file.unlink()
        (staging / "bin").rmdir()
        staging.rmdir()
    except Exception:
        if target_claimed:
            shutil.rmtree(target, ignore_errors=True)
        shutil.rmtree(staging, ignore_errors=True)
        raise
    result.update(
        {
            "status": "installed",
            "installation": {
                "target": str(target),
                "subject_digest": identity["subject_digest"],
                "source_ref": identity["source_ref"],
                "version": identity["version"],
                "digest": identity["digest"],
            },
            "written": [
                f"providers/{PROVIDER_ID}/{ARCHIVE_BINARY_NAME}",
                f"providers/{PROVIDER_ID}/{PROVIDER_METADATA_NAME}",
                f"providers/{PROVIDER_ID}/{INSTALLATION_IDENTITY_NAME}",
            ],
        }
    )
    return result


def _parse_symbol_output(stdout: str) -> dict[str, Any]:
    names: list[str] = []
    count = 0
    invalid = 0
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            invalid += 1
            continue
        if not isinstance(item, dict) or item.get("_type") != "tag":
            invalid += 1
            continue
        count += 1
        name = item.get("name")
        if isinstance(name, str) and name and len(names) < 8:
            names.append(name)
    return {"tag_count": count, "sample_names": names, "invalid_records": invalid}


def exercise_provider(
    bundle_dir: str | Path,
    *,
    archive_path: str | Path,
    subject_root: str | Path,
    runtime_root: str | Path = DEFAULT_RUNTIME_ROOT,
    registry_dir: str | Path = DEFAULT_REGISTRY_DIR,
    source_root: str | Path = DEFAULT_SOURCE_ROOT,
    source_file: str | Path = DEFAULT_SOURCE_FILE,
    expected_source_ref: str = "",
) -> dict[str, Any]:
    """Run a bounded version and JSON symbol probe after trust-gate admission."""

    inspection = inspect_provider_artifact(
        archive_path,
        bundle_dir,
        subject_root=subject_root,
        registry_dir=registry_dir,
        source_root=source_root,
        expected_source_ref=expected_source_ref,
    )
    result: dict[str, Any] = {
        "schema": "abyss_machine_code_intelligence_provider_exercise_v1",
        "operation": "exercise",
        "provider_id": PROVIDER_ID,
        "status": "blocked",
        "inspection": inspection,
        "semantic": {
            "status": "unproven",
            "proof_owner": "aoa-evals",
            "claim_limit": "A symbol smoke is a runtime health fact, not semantic proof or an eval verdict.",
        },
        "consumer_abi": dict(MACHINE_CONSUMER_ABI),
    }
    if inspection.get("status") != "admitted":
        result["blocking_reasons"] = ["exact_provider_artifact_not_admitted"]
        return result
    installed = _installed_identity(Path(runtime_root).expanduser().resolve())
    result["installation"] = {
        "ok": installed.get("ok") is True,
        "target": installed.get("target"),
        "errors": installed.get("errors", []),
    }
    installed_identity = installed.get("identity") if isinstance(installed.get("identity"), dict) else {}
    if installed.get("ok") is not True:
        result["blocking_reasons"] = ["provider_not_installed_or_identity_invalid"]
        return result
    if installed_identity.get("subject_digest") != inspection.get("artifact", {}).get("subject_digest"):
        result["blocking_reasons"] = ["installed_subject_digest_mismatch"]
        return result
    executable = Path(str(installed.get("executable"))).resolve()
    version_result = _bounded_process([str(executable), "--version"], timeout=5.0, max_output_bytes=MAX_VERSION_OUTPUT_BYTES)
    reported_version = _version_line(version_result)
    version_ok = (
        version_result.get("returncode") == 0
        and not version_result.get("timed_out")
        and not version_result.get("output_truncated")
        and reported_version == installed.get("metadata", {}).get("version")
    )
    source_base = Path(source_root).expanduser().resolve()
    source_relative = Path(source_file)
    if source_relative.is_absolute() or not _safe_relative(source_relative.as_posix()):
        result["blocking_reasons"] = ["source_file_must_be_safe_relative_path"]
        return result
    source_path = (source_base / source_relative).resolve()
    try:
        source_path.relative_to(source_base)
    except ValueError:
        result["blocking_reasons"] = ["source_file_escapes_source_root"]
        return result
    symbol_result: dict[str, Any] = {"returncode": None, "timed_out": False, "output_truncated": False}
    parsed_symbols = {"tag_count": 0, "sample_names": [], "invalid_records": 0}
    if version_ok and source_path.is_file():
        symbol_result = _bounded_process(
            [
                str(executable),
                "--output-format=json",
                "--fields=+ne",
                "--extras=+q",
                "--languages=Python",
                "-o",
                "-",
                str(source_path),
            ],
            timeout=15.0,
            max_output_bytes=MAX_SYMBOL_OUTPUT_BYTES,
        )
        parsed_symbols = _parse_symbol_output(_decode(symbol_result.get("stdout")))
    symbol_ok = (
        source_path.is_file()
        and symbol_result.get("returncode") == 0
        and not symbol_result.get("timed_out")
        and not symbol_result.get("output_truncated")
        and parsed_symbols.get("tag_count", 0) > 0
    )
    healthy = version_ok and symbol_ok
    result["health"] = "healthy" if healthy else "failed"
    result["version_probe"] = {
        "ok": version_ok,
        "version": reported_version,
        "returncode": version_result.get("returncode"),
        "timed_out": version_result.get("timed_out"),
    }
    result["symbol_probe"] = {
        "ok": symbol_ok,
        "source_file": source_relative.as_posix(),
        "returncode": symbol_result.get("returncode"),
        "timed_out": symbol_result.get("timed_out"),
        "tag_count": parsed_symbols.get("tag_count"),
        "sample_names": parsed_symbols.get("sample_names"),
        "invalid_records": parsed_symbols.get("invalid_records"),
    }
    if not healthy:
        result["blocking_reasons"] = ["bounded_provider_health_probe_failed"]
        return result

    from .code_intelligence_adapters import collect_owner_admission_receipt, collect_provider_observation
    from .code_intelligence_contracts import provider_admission

    def resolver(_name: str) -> str:
        return str(executable)

    def runner(command: Sequence[str], timeout: float) -> Mapping[str, Any]:
        return _bounded_process(command, timeout=timeout, max_output_bytes=MAX_VERSION_OUTPUT_BYTES)

    config = code_intelligence_config()
    observed_at = _utc_now()
    observation = collect_provider_observation(
        config,
        PROVIDER_ID,
        observed_at=observed_at,
        evidence_ref="runtime:abyss-machine/code-intelligence/universal-ctags/exercise",
        executable_resolver=resolver,
        command_runner=runner,
    )
    gate = _trust_gate(
        Path(registry_dir).expanduser().resolve(),
        subject_digest=str(inspection.get("artifact", {}).get("subject_digest") or ""),
        source_ref=str(inspection.get("artifact", {}).get("source_ref") or ""),
    )
    receipt_route = collect_owner_admission_receipt(
        config,
        PROVIDER_ID,
        observation,
        registry_dir=registry_dir,
        subject_digest=str(inspection.get("artifact", {}).get("subject_digest") or ""),
        record_id=str(gate.get("record_id") or ""),
    )
    admission = None
    if receipt_route.get("status") == "receipt_ready" and receipt_route.get("receipt") is not None:
        admission = provider_admission(config, PROVIDER_ID, observation, admission_receipt=receipt_route["receipt"])
    result["owner_admission"] = {
        "status": receipt_route.get("status"),
        "receipt_digest": receipt_route.get("receipt_digest"),
        "blocking_reasons": receipt_route.get("blocking_reasons", []),
        "admission_status": admission.get("status") if isinstance(admission, dict) else "not_evaluated",
        "admission_blocking_reasons": admission.get("blocking_reasons", []) if isinstance(admission, dict) else [],
    }
    result["status"] = "healthy" if isinstance(admission, dict) and admission.get("status") == "admitted" else "healthy_not_owner_admitted"
    return result


__all__ = [
    "ARCHIVE_SCHEMA",
    "ARTIFACT_CLASS",
    "BUNDLE_MANIFEST_REF",
    "CONTRACT_SURFACE_ID",
    "DEFAULT_ARTIFACT_ROOT",
    "DEFAULT_REGISTRY_DIR",
    "DEFAULT_RUNTIME_ROOT",
    "DEFAULT_SOURCE_ROOT",
    "DEFAULT_SUBJECT_STORE",
    "PROVIDER_ID",
    "build_provider_archive",
    "exercise_provider",
    "inspect_provider_artifact",
    "install_provider",
    "read_provider_archive",
    "run_owner_preflights",
]

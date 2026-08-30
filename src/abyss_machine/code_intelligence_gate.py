"""Issue one owner-authenticated runtime evidence gate for code intelligence.

The issuer never creates a key or trust anchor.  It consumes an explicitly
provisioned Ed25519 private key and the matching root-owned public anchor only
after the artifact registry, installed runtime, and a bounded LSP probe agree.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .artifact_bundles import trust_gate


GATE_BUNDLE_SCHEMA = "abyss-stack-machine-code-intelligence-gate-v1"
EVIDENCE_SCHEMA = "abyss-stack-machine-code-intelligence-evidence-v1"
REGISTRY_SCHEMA = "abyss-machine-content-addressed-registry-record-v1"
GATE_SCHEMA = "abyss-machine-admission-gate-v1"
SIGNED_PAYLOAD_SCHEMA = "abyss-machine-admission-gate-signed-payload-v1"
PUBLIC_KEY_SCHEMA = "abyss-machine-code-intelligence-gate-public-key-v1"
ALGORITHM = "ed25519"
VERIFICATION_METHOD = "ed25519-owner-signature-v1"
ARTIFACT_CLASS = "code_intelligence_provider_bundle"
LSP_PROVIDER_ID = "typescript-lsp"
MAX_LSP_OUTPUT_BYTES = 8 * 1024 * 1024
MAX_SOURCE_FILES = 20_000


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _digest_payload(value: object) -> str:
    return _digest_bytes(_canonical_json(value))


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _without_digest(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    payload = dict(value)
    payload.pop(field, None)
    return payload


def evidence_digest(value: Mapping[str, Any]) -> str:
    return _digest_payload(_without_digest(value, "receipt_digest"))


def gate_digest(value: Mapping[str, Any]) -> str:
    return _digest_payload(_without_digest(value, "gate_digest"))


def bundle_digest(value: Mapping[str, Any]) -> str:
    return _digest_payload(_without_digest(value, "bundle_digest"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not readable JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _safe_regular_file(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if path.is_symlink() or not resolved.is_file():
        raise ValueError(f"{label} must be a real regular file")
    return resolved


def _load_signing_identity(
    private_key_path: str | Path,
    trust_anchor_path: str | Path,
    *,
    require_root_owned: bool,
) -> tuple[Ed25519PrivateKey, str, str, bytes]:
    key_path = _safe_regular_file(Path(private_key_path), "private key")
    anchor_path = _safe_regular_file(Path(trust_anchor_path), "trust anchor")
    for path, label in ((key_path, "private key"), (anchor_path, "trust anchor")):
        metadata = path.stat()
        if metadata.st_mode & 0o022:
            raise ValueError(f"{label} must not be group/world writable")
        if require_root_owned and metadata.st_uid != 0:
            raise ValueError(f"{label} must be root-owned for live issuance")
    if key_path.stat().st_mode & 0o077:
        raise ValueError("private key must not be group/world readable")
    raw_anchor = anchor_path.read_bytes()
    anchor = _read_object(anchor_path, "trust anchor")
    if set(anchor) != {"schema_version", "owner", "key_id", "algorithm", "public_key"}:
        raise ValueError("trust anchor does not match the exact public-key schema")
    if (
        anchor.get("schema_version") != PUBLIC_KEY_SCHEMA
        or anchor.get("owner") != "abyss-machine"
        or anchor.get("algorithm") != ALGORITHM
        or not isinstance(anchor.get("key_id"), str)
        or not anchor["key_id"]
    ):
        raise ValueError("trust anchor identity is invalid")
    try:
        public_key = base64.b64decode(str(anchor["public_key"]), validate=True)
    except ValueError as exc:
        raise ValueError("trust anchor public key is not valid base64") from exc
    if len(public_key) != 32:
        raise ValueError("trust anchor public key must contain 32 bytes")
    try:
        loaded = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError("private key must be an unencrypted PEM Ed25519 key") from exc
    if not isinstance(loaded, Ed25519PrivateKey):
        raise ValueError("private key must be Ed25519")
    actual_public = loaded.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    if actual_public != public_key:
        raise ValueError("private key does not match the fixed trust anchor")
    return loaded, str(anchor["key_id"]), _digest_bytes(raw_anchor), public_key


def _provider_identity(config: Mapping[str, Any]) -> dict[str, Any]:
    provider = config.get("provider")
    if not isinstance(provider, Mapping):
        raise ValueError("stack provider config lacks provider identity")
    required = {
        "id",
        "version",
        "language",
        "mode",
        "observation_schema",
        "boundary_schema",
        "executable",
        "entrypoint",
        "protocol",
        "operations",
    }
    if set(provider) != required or provider.get("id") != "python-ast-bootstrap":
        raise ValueError("stack provider config identity is unsupported")
    return dict(provider)


def _stack_config_identity(config: Mapping[str, Any], provider_source_digest: str) -> dict[str, Any]:
    source = config.get("source")
    state = config.get("state")
    machine_binding = config.get("machine_binding")
    owner_boundaries = config.get("owner_boundaries")
    if not all(isinstance(value, Mapping) for value in (source, state, machine_binding, owner_boundaries)):
        raise ValueError("stack provider config is incomplete")
    return {
        "schema_version": "abyss-stack-live-code-intelligence-provider-v1",
        "provider": _provider_identity(config),
        "provider_source_digest": provider_source_digest,
        "source": {
            "include_suffixes": list(source["include_suffixes"]),
            "exclude_dirs": list(source["exclude_dirs"]),
            "max_file_bytes": source["max_file_bytes"],
        },
        "state": {
            "relative_root": state["relative_root"],
            "promotion": state["promotion"],
            "fallback": state["fallback"],
        },
        "machine_binding": dict(machine_binding),
        "owner_boundaries": dict(owner_boundaries),
    }


def _source_epoch(source_root: Path) -> str:
    excluded = {".git", ".hg", ".venv", "__pycache__", "node_modules"}
    suffixes = {".py", ".ts", ".tsx", ".js", ".jsx"}
    entries: list[dict[str, str]] = []
    for path in sorted(source_root.rglob("*")):
        relative = path.relative_to(source_root)
        if any(part in excluded for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError("source epoch refuses symlinked source entries")
        if path.is_file() and path.suffix in suffixes:
            entries.append({"path": relative.as_posix(), "digest": _digest_file(path)})
            if len(entries) > MAX_SOURCE_FILES:
                raise ValueError("source epoch exceeds the bounded file count")
    if not entries:
        raise ValueError("source root contains no supported Python or JS/TS files")
    return _digest_payload(entries)


def _parse_lsp_messages(payload: bytes) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    cursor = 0
    while cursor < len(payload):
        boundary = payload.find(b"\r\n\r\n", cursor)
        if boundary < 0:
            break
        headers = payload[cursor:boundary].decode("ascii", errors="strict").split("\r\n")
        length = None
        for header in headers:
            name, _, value = header.partition(":")
            if name.lower() == "content-length":
                length = int(value.strip())
        if length is None or length < 0 or length > MAX_LSP_OUTPUT_BYTES:
            raise ValueError("LSP response has an invalid Content-Length")
        start = boundary + 4
        end = start + length
        if end > len(payload):
            raise ValueError("LSP response is truncated")
        value = json.loads(payload[start:end])
        if isinstance(value, dict):
            messages.append(value)
        cursor = end
    return messages


def _frame_lsp(payload: Mapping[str, Any]) -> bytes:
    body = _canonical_json(payload)
    return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body


def _probe_lsp(command: Sequence[str], source_root: Path) -> dict[str, Any]:
    requests = b"".join(
        (
            _frame_lsp(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "processId": None,
                        "rootUri": source_root.as_uri(),
                        "capabilities": {},
                    },
                }
            ),
            _frame_lsp({"jsonrpc": "2.0", "method": "initialized", "params": {}}),
            _frame_lsp({"jsonrpc": "2.0", "id": 2, "method": "shutdown", "params": None}),
            _frame_lsp({"jsonrpc": "2.0", "method": "exit", "params": None}),
        )
    )
    try:
        completed = subprocess.run(
            list(command),
            input=requests,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"bounded LSP probe failed: {type(exc).__name__}") from exc
    if len(completed.stdout) > MAX_LSP_OUTPUT_BYTES or len(completed.stderr) > 256 * 1024:
        raise ValueError("bounded LSP probe output exceeded its limit")
    messages = _parse_lsp_messages(completed.stdout)
    by_id = {item.get("id"): item for item in messages if "id" in item}
    if (
        completed.returncode != 0
        or not isinstance(by_id.get(1), Mapping)
        or "result" not in by_id[1]
        or not isinstance(by_id.get(2), Mapping)
        or by_id[2].get("result") is not None
    ):
        raise ValueError("LSP initialize/shutdown probe did not complete cleanly")
    return {"returncode": completed.returncode, "message_count": len(messages)}


def _atomic_write(path: Path, value: Mapping[str, Any]) -> None:
    target = path.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=True, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def issue_runtime_gate(
    *,
    registry_dir: str | Path,
    runtime_root: str | Path,
    source_root: str | Path,
    stack_provider_source: str | Path,
    stack_provider_config: str | Path,
    private_key_path: str | Path,
    trust_anchor_path: str | Path,
    output_path: str | Path,
    require_root_owned_identity: bool = True,
) -> dict[str, Any]:
    """Probe the admitted provider and issue one exact runtime evidence bundle."""

    runtime = Path(runtime_root).expanduser().resolve()
    source = Path(source_root).expanduser().resolve()
    if not runtime.is_dir() or not source.is_dir():
        raise ValueError("runtime_root and source_root must exist")
    provider_source = _safe_regular_file(Path(stack_provider_source), "stack provider source")
    provider_config_path = _safe_regular_file(Path(stack_provider_config), "stack provider config")
    provider_config = _read_object(provider_config_path, "stack provider config")
    provider_source_digest = _digest_file(provider_source)
    config_identity = _stack_config_identity(provider_config, provider_source_digest)
    config_digest = _digest_payload(config_identity)

    installation_path = runtime / "providers" / "node-providers" / "installation.json"
    installation = _read_object(installation_path, "node provider installation")
    artifact_subject = str(installation.get("subject_digest") or "")
    source_ref = str(installation.get("source_ref") or "")
    gate_result = trust_gate(
        registry_dir,
        artifact_class=ARTIFACT_CLASS,
        subject_digest=artifact_subject,
        consumer_intent="runtime",
        expected_source_repo="abyss-machine",
        expected_source_ref=source_ref,
        expected_trust_root_mode="github_oidc",
        require_latest=True,
    )
    if gate_result.get("ok") is not True or gate_result.get("verdict") != "allow":
        raise ValueError("exact provider artifact is not admitted for runtime consumption")

    bin_root = Path(str(installation.get("bin_root") or "")).resolve()
    executable = (bin_root / "typescript-language-server").resolve()
    try:
        executable.relative_to(runtime)
    except ValueError as exc:
        raise ValueError("LSP executable escapes the admitted runtime root") from exc
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise ValueError("installed TypeScript language server is not runnable")
    executable_digest = _digest_file(executable)
    command = [str(executable), "--stdio"]
    epoch = _source_epoch(source)
    first_probe = _probe_lsp(command, source)
    second_probe = _probe_lsp(command, source)
    observed_at = _utc_now()
    record_id = str(gate_result.get("record_id") or "")
    if not record_id.startswith("sha256:"):
        raise ValueError("artifact trust gate did not return a content-addressed record")

    evidence: dict[str, Any] = {
        "schema_version": EVIDENCE_SCHEMA,
        "evidence_class": "machine-owned-verification",
        "issuer": "abyss-machine",
        "receipt_id": "machine-receipt:live-code-intelligence:" + executable_digest[7:23],
        "observed_at": observed_at,
        "subject": {
            "provider": _provider_identity(provider_config),
            "provider_source_digest": provider_source_digest,
            "config_digest": config_digest,
            "artifact_digest": executable_digest,
            "artifact_ref": "artifact://abyss-machine/code-intelligence/typescript-lsp",
        },
        "installation": {
            "owner": "abyss-machine",
            "state": "verified",
            "identity": "installation://abyss-machine/code-intelligence/node-providers",
            "artifact_digest": executable_digest,
            "evidence_ref": "receipt://abyss-machine/code-intelligence/installation",
        },
        "admission": {
            "owner": "abyss-machine",
            "state": "admitted",
            "trust_state": "trusted",
            "admission_ref": f"trust://abyss-machine/artifact-registry/{record_id}",
        },
        "health": {
            "owner": "abyss-machine",
            "state": "healthy",
            "measurement_ref": "runtime://abyss-machine/code-intelligence/lsp-probe",
            "observed_at": observed_at,
        },
        "verification": {
            "owner": "abyss-machine",
            "state": "verified",
            "method": "abyss-machine-owner-receipt-v1",
            "verification_ref": f"trust://abyss-machine/artifact-registry/{record_id}",
        },
        "providers": [
            {
                "id": "python-ast-bootstrap",
                "version": str(provider_config["provider"]["version"]),
                "language": "python",
                "protocol": str(provider_config["provider"]["protocol"]),
                "observation_state": "available",
            },
            {
                "id": LSP_PROVIDER_ID,
                "version": str(installation.get("versions", {}).get("lsp") or "unknown"),
                "language": "typescript",
                "protocol": "lsp",
                "observation_state": "observed",
            },
        ],
        "lsp_sessions": [
            {
                "session_id": "lsp-session:typescript:" + epoch[7:23],
                "provider_id": LSP_PROVIDER_ID,
                "language": "typescript",
                "state": "observed",
                "transport": "stdio",
                "source_epoch": epoch,
                "evidence_ref": "runtime://abyss-machine/code-intelligence/lsp-initialize",
                "source_root": str(source),
                "command_digest": _digest_payload(command),
                "artifact_digest": executable_digest,
            }
        ],
        "observations": [
            {
                "provider_id": LSP_PROVIDER_ID,
                "language": "typescript",
                "state": "observed",
                "source_epoch": epoch,
                "observation_ref": "runtime://abyss-machine/code-intelligence/typescript-observation",
                "semantic_owner": "aoa-kag",
            }
        ],
        "lifecycle": {
            "state": "ready",
            "restart": {"state": "observed", "evidence_ref": "runtime://abyss-machine/code-intelligence/lsp-restart"},
            "last_good": {"state": "available", "evidence_ref": "runtime://abyss-machine/code-intelligence/lsp-first-good"},
            "canary": {"state": "passed", "evidence_ref": "runtime://abyss-machine/code-intelligence/lsp-canary"},
            "rollback": {"state": "ready", "evidence_ref": "runtime://abyss-machine/code-intelligence/provider-installation"},
        },
        "owner_boundaries": dict(provider_config["owner_boundaries"]),
        "claim_limits": [
            "machine runtime evidence is not KAG semantic meaning or aoa-evals proof",
            "the signed gate applies only to the exact provider, config, source epoch, executable, and artifact admission record",
        ],
    }
    evidence["receipt_digest"] = evidence_digest(evidence)

    private_key, key_id, key_digest, _ = _load_signing_identity(
        private_key_path,
        trust_anchor_path,
        require_root_owned=require_root_owned_identity,
    )
    evidence_record_digest = _digest_payload(evidence)
    record_ref = f"cas://{evidence_record_digest}"
    verification_ref = f"cas://{record_id}"
    subject_digest = _digest_payload(evidence["subject"])
    gate_id = "gate:abyss-machine/code-intelligence:" + evidence_record_digest[7:23]
    signed_payload = {
        "schema_version": SIGNED_PAYLOAD_SCHEMA,
        "owner": "abyss-machine",
        "gate_id": gate_id,
        "state": "authenticated",
        "algorithm": ALGORITHM,
        "verification_method": VERIFICATION_METHOD,
        "key_id": key_id,
        "key_digest": key_digest,
        "verification_ref": verification_ref,
        "registry_record_ref": record_ref,
        "registry_record_digest": evidence_record_digest,
        "evidence_digest": evidence_record_digest,
        "subject_digest": subject_digest,
        "provider_source_digest": provider_source_digest,
        "config_digest": config_digest,
        "claim_limits_digest": _digest_payload(evidence["claim_limits"]),
    }
    gate: dict[str, Any] = {
        "schema_version": GATE_SCHEMA,
        "owner": "abyss-machine",
        "state": "authenticated",
        "algorithm": ALGORITHM,
        "verification_method": VERIFICATION_METHOD,
        "key_id": key_id,
        "key_digest": key_digest,
        "gate_id": gate_id,
        "verification_ref": verification_ref,
        "subject_digest": subject_digest,
        "signed_payload": signed_payload,
        "signature": base64.b64encode(private_key.sign(_canonical_json(signed_payload))).decode("ascii"),
    }
    gate["gate_digest"] = gate_digest(gate)
    bundle: dict[str, Any] = {
        "schema_version": GATE_BUNDLE_SCHEMA,
        "registry": {
            "schema_version": REGISTRY_SCHEMA,
            "owner": "abyss-machine",
            "record_ref": record_ref,
            "record_digest": evidence_record_digest,
            "gate_ref": f"cas://{gate['gate_digest']}",
            "gate_digest": gate["gate_digest"],
        },
        "evidence": evidence,
        "gate": gate,
    }
    bundle["bundle_digest"] = bundle_digest(bundle)
    _atomic_write(Path(output_path), bundle)
    return {
        "schema": "abyss_machine_code_intelligence_runtime_gate_issue_v1",
        "status": "issued",
        "output": str(Path(output_path).expanduser().resolve()),
        "bundle_digest": bundle["bundle_digest"],
        "evidence_digest": evidence_record_digest,
        "gate_digest": gate["gate_digest"],
        "artifact_record_id": record_id,
        "artifact_subject_digest": artifact_subject,
        "executable_digest": executable_digest,
        "source_epoch": epoch,
        "lsp_probe": {"first": first_probe, "restart": second_probe},
        "claim_limit": "Issued machine evidence is runtime admission evidence, not KAG meaning, aoa-evals proof, or owner acceptance.",
    }


__all__ = [
    "bundle_digest",
    "evidence_digest",
    "gate_digest",
    "issue_runtime_gate",
]

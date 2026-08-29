"""Read-only host observations for the machine code-intelligence contract.

The contract module owns declarations and admission rules; this module owns
the narrow boundary where those declarations can be compared with a host.
Every operation is injectable for tests, bounded by source policy, and avoids
installation, service lifecycle, network access, trust grants, source
synchronization, and persistence of raw command output.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import shutil
import stat
import subprocess
import time
from typing import Any, Callable, Mapping, Sequence

from .code_intelligence_contracts import (
    VERSION,
    _owner_admission_receipt_from_verified_gate,
    admit_provider,
    code_intelligence_config,
    validate_provider_config,
)


OBSERVATION_COLLECTION_SCHEMA = "abyss_machine_code_intelligence_host_observations_v1"
PROJECTION_SCHEMA = "abyss_machine_code_intelligence_source_install_projection_v1"
_DEFAULT_MAX_OUTPUT_BYTES = 4096
_DEFAULT_MAX_DIGEST_BYTES = 128 * 1024 * 1024
_DEFAULT_TIMEOUT_SECONDS = 5.0
_MAX_PREVIEW_CHARS = 256
_CHUNK_SIZE = 64 * 1024
_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")

CommandRunnerPort = Callable[[Sequence[str], float], Any]
ExecutableResolverPort = Callable[[str], str | None]
DigestReaderPort = Callable[[Path, int], Mapping[str, Any]]
MemoryProbePort = Callable[[], Mapping[str, Any]]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _config_digest(config: Mapping[str, Any]) -> str | None:
    try:
        encoded = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError):
        return None
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _valid_digest(value: Any) -> bool:
    return isinstance(value, str) and _SHA256_PATTERN.fullmatch(value) is not None


def _bounded_limit(value: Any, default: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    try:
        normalized = int(value)
    except (OverflowError, ValueError):
        return default
    if isinstance(value, float) and not math.isfinite(value):
        return default
    return max(1, min(normalized, maximum))


def _observation_policy(config: Mapping[str, Any]) -> Mapping[str, Any]:
    policy = config.get("observation")
    return policy if isinstance(policy, Mapping) else {}


def _provider(config: Mapping[str, Any], provider_id: str) -> Mapping[str, Any] | None:
    providers = config.get("providers")
    if not isinstance(providers, list):
        return None
    for candidate in providers:
        if isinstance(candidate, Mapping) and candidate.get("id") == provider_id:
            return candidate
    return None


def _text_output(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _bounded_output(value: Any, max_bytes: int) -> tuple[str, int, bool]:
    text = _text_output(value)
    encoded = text.encode("utf-8", errors="replace")
    truncated = len(encoded) > max_bytes
    if truncated:
        text = encoded[:max_bytes].decode("utf-8", errors="ignore")
    return text, len(encoded), truncated


def _version_from_output(provider_id: str, stdout: str, stderr: str) -> str | None:
    if provider_id == "syft" and stdout.strip():
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, Mapping) and isinstance(payload.get("version"), str):
            return str(payload["version"]).strip() or None
    for stream in (stdout, stderr):
        for line in stream.splitlines():
            normalized = " ".join(character for character in line.strip().split())
            if normalized:
                return normalized[:_MAX_PREVIEW_CHARS]
    return None


def _default_command_runner(command: Sequence[str], timeout: float) -> Mapping[str, Any]:
    """Run a version command while retaining only bounded pipe prefixes."""

    process = subprocess.Popen(
        list(command),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        close_fds=True,
    )
    selector = selectors.DefaultSelector()
    streams: dict[int, bytearray] = {}
    names: dict[int, str] = {}
    truncated = False
    try:
        assert process.stdout is not None
        assert process.stderr is not None
        for name, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, data=name)
            streams[stream.fileno()] = bytearray()
            names[stream.fileno()] = name
        deadline = time.monotonic() + max(0.01, float(timeout))
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.kill()
                process.wait()
                return {
                    "returncode": None,
                    "stdout": bytes(streams[next(fd for fd, name in names.items() if name == "stdout")]),
                    "stderr": bytes(streams[next(fd for fd, name in names.items() if name == "stderr")]),
                    "timed_out": True,
                    "output_truncated": truncated,
                }
            events = selector.select(remaining)
            if not events:
                process.kill()
                process.wait()
                return {
                    "returncode": None,
                    "stdout": bytes(streams[next(fd for fd, name in names.items() if name == "stdout")]),
                    "stderr": bytes(streams[next(fd for fd, name in names.items() if name == "stderr")]),
                    "timed_out": True,
                    "output_truncated": truncated,
                }
            for key, _ in events:
                stream = key.fileobj
                try:
                    chunk = os.read(stream.fileno(), 8192)
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(stream)
                    stream.close()
                    continue
                buffer = streams[stream.fileno()]
                available = _DEFAULT_MAX_OUTPUT_BYTES - len(buffer)
                if available > 0:
                    buffer.extend(chunk[:available])
                if len(chunk) > max(0, available):
                    truncated = True
        returncode = process.wait()
        stdout_fd = next(fd for fd, name in names.items() if name == "stdout")
        stderr_fd = next(fd for fd, name in names.items() if name == "stderr")
        return {
            "returncode": returncode,
            "stdout": bytes(streams[stdout_fd]),
            "stderr": bytes(streams[stderr_fd]),
            "output_truncated": truncated,
        }
    finally:
        selector.close()
        for stream in (process.stdout, process.stderr):
            if stream is not None and not stream.closed:
                stream.close()


def _normalize_command_result(
    result: Any,
    *,
    max_output_bytes: int,
) -> dict[str, Any]:
    if isinstance(result, Mapping):
        returncode = result.get("returncode")
        stdout_value = result.get("stdout")
        stderr_value = result.get("stderr")
        timed_out = bool(result.get("timed_out") or result.get("timeout"))
        error_type = result.get("error_type")
        runner_truncated = bool(result.get("output_truncated"))
    else:
        returncode = getattr(result, "returncode", None)
        stdout_value = getattr(result, "stdout", None)
        stderr_value = getattr(result, "stderr", None)
        timed_out = bool(getattr(result, "timed_out", False))
        error_type = getattr(result, "error_type", None)
        runner_truncated = bool(getattr(result, "output_truncated", False))

    normalized_returncode: int | None
    if isinstance(returncode, bool) or not isinstance(returncode, int):
        normalized_returncode = None
    else:
        normalized_returncode = returncode
    stdout, stdout_bytes, stdout_truncated = _bounded_output(stdout_value, max_output_bytes)
    stderr, stderr_bytes, stderr_truncated = _bounded_output(stderr_value, max_output_bytes)
    normalized_error_type = str(error_type) if error_type else None
    return {
        "returncode": normalized_returncode,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_bytes": stdout_bytes,
        "stderr_bytes": stderr_bytes,
        "output_truncated": runner_truncated or stdout_truncated or stderr_truncated,
        "timed_out": timed_out,
        "error_type": normalized_error_type,
    }


def _run_version_probe(
    command: Sequence[str],
    *,
    timeout: float,
    max_output_bytes: int,
    command_runner: CommandRunnerPort,
) -> dict[str, Any]:
    try:
        result = command_runner(command, timeout)
    except subprocess.TimeoutExpired:
        return {
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "stdout_bytes": 0,
            "stderr_bytes": 0,
            "output_truncated": False,
            "timed_out": True,
            "error_type": "TimeoutExpired",
        }
    except Exception as exc:
        return {
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "stdout_bytes": 0,
            "stderr_bytes": 0,
            "output_truncated": False,
            "timed_out": False,
            "error_type": type(exc).__name__,
        }
    return _normalize_command_result(result, max_output_bytes=max_output_bytes)


def _gate(ok: bool | None, observed_at: str, evidence_ref: str) -> dict[str, Any]:
    return {
        "ok": ok,
        "observed_at": observed_at,
        "evidence_ref": evidence_ref,
    }


def host_memory_snapshot(*, sysconf: Callable[[str], int] = os.sysconf) -> dict[str, Any]:
    """Read coarse capacity from sysconf without changing host state."""

    try:
        page_size = int(sysconf("SC_PAGE_SIZE"))
        available_pages = int(sysconf("SC_AVPHYS_PAGES"))
        total_pages = int(sysconf("SC_PHYS_PAGES"))
    except (OSError, TypeError, ValueError):
        return {
            "status": "unknown",
            "source": "sysconf_read_only",
            "measurement_kind": "capacity_only",
            "read_only": True,
        }
    if page_size <= 0 or available_pages < 0 or total_pages <= 0:
        return {
            "status": "unknown",
            "source": "sysconf_read_only",
            "measurement_kind": "capacity_only",
            "read_only": True,
        }
    mib = 1024 * 1024
    return {
        "status": "observed",
        "source": "sysconf_read_only",
        "measurement_kind": "capacity_only",
        "total_mib": round((page_size * total_pages) / mib, 2),
        "available_mib": round((page_size * available_pages) / mib, 2),
        "read_only": True,
    }


def digest_file(path: Path, max_bytes: int = _DEFAULT_MAX_DIGEST_BYTES) -> dict[str, Any]:
    """Hash one regular file up to a bounded size, returning no file content."""

    target = Path(path)
    limit = _bounded_limit(max_bytes, _DEFAULT_MAX_DIGEST_BYTES, 512 * 1024 * 1024)
    result: dict[str, Any] = {"path": str(target)}
    try:
        metadata = target.stat()
    except FileNotFoundError:
        return {**result, "status": "missing"}
    except OSError as exc:
        return {**result, "status": "unreadable", "error_type": type(exc).__name__}
    if not stat.S_ISREG(metadata.st_mode):
        return {**result, "status": "not_regular_file", "size_bytes": int(metadata.st_size)}
    size_bytes = int(metadata.st_size)
    if size_bytes > limit:
        return {**result, "status": "too_large", "size_bytes": size_bytes, "max_bytes": limit}

    hasher = hashlib.sha256()
    bytes_read = 0
    try:
        with target.open("rb") as handle:
            while True:
                chunk = handle.read(min(_CHUNK_SIZE, limit - bytes_read))
                if not chunk:
                    break
                bytes_read += len(chunk)
                hasher.update(chunk)
                if bytes_read > limit:
                    return {**result, "status": "too_large", "size_bytes": bytes_read, "max_bytes": limit}
    except OSError as exc:
        return {**result, "status": "unreadable", "size_bytes": size_bytes, "error_type": type(exc).__name__}
    try:
        final_metadata = target.stat()
    except OSError as exc:
        return {**result, "status": "changed_during_read", "size_bytes": size_bytes, "error_type": type(exc).__name__}
    if (
        int(final_metadata.st_dev) != int(metadata.st_dev)
        or int(final_metadata.st_ino) != int(metadata.st_ino)
        or int(final_metadata.st_size) != size_bytes
        or int(final_metadata.st_mtime_ns) != int(metadata.st_mtime_ns)
    ):
        return {**result, "status": "changed_during_read", "size_bytes": int(final_metadata.st_size)}
    return {
        **result,
        "status": "read",
        "size_bytes": size_bytes,
        "bytes_read": bytes_read,
        "sha256": "sha256:" + hasher.hexdigest(),
    }


def _projection_status(source: Mapping[str, Any], installed: Mapping[str, Any]) -> tuple[str, bool | None]:
    source_status = source.get("status")
    installed_status = installed.get("status")
    if source_status != "read":
        return "source_" + str(source_status or "unknown"), None
    if installed_status != "read":
        return "installed_" + str(installed_status or "unknown"), None
    if source.get("sha256") == installed.get("sha256"):
        return "current", True
    return "drifted", False


def compare_source_install_projection(
    source_path: Path,
    installed_path: Path,
    *,
    max_bytes: int = _DEFAULT_MAX_DIGEST_BYTES,
    source_ref: str = "source:owner-repository/code-intelligence-config",
    installed_ref: str = "installed:host/etc/abyss-machine/code-intelligence.json",
    digest_reader: DigestReaderPort = digest_file,
) -> dict[str, Any]:
    """Compare source and installed projections without copying either one."""

    try:
        source = dict(digest_reader(Path(source_path), max_bytes))
    except Exception as exc:
        source = {"path": str(source_path), "status": "unreadable", "error_type": type(exc).__name__}
    try:
        installed = dict(digest_reader(Path(installed_path), max_bytes))
    except Exception as exc:
        installed = {"path": str(installed_path), "status": "unreadable", "error_type": type(exc).__name__}
    status, current = _projection_status(source, installed)
    return {
        "schema": PROJECTION_SCHEMA,
        "version": VERSION,
        "source_ref": source_ref,
        "installed_ref": installed_ref,
        "source": source,
        "installed": installed,
        "status": status,
        "current": current,
        "read_only": True,
        "mutation_performed": False,
        "synchronization_performed": False,
        "claim_limit": "projection parity is not installation or deployment evidence",
    }


def _provider_probe(
    provider: Mapping[str, Any],
    *,
    observed_at: str,
    evidence_ref: str,
    timeout: float,
    max_output_bytes: int,
    max_digest_bytes: int,
    executable_resolver: ExecutableResolverPort,
    command_runner: CommandRunnerPort,
    digest_reader: DigestReaderPort,
    memory: Mapping[str, Any],
) -> dict[str, Any]:
    provider_id = str(provider.get("id") or "")
    host_owner = str(provider.get("host_owner") or "")
    consumer_owner = str(provider.get("consumer_owner") or "")
    installation = provider.get("installation") if isinstance(provider.get("installation"), Mapping) else {}
    artifact = provider.get("artifact") if isinstance(provider.get("artifact"), Mapping) else {}
    declared_executable = installation.get("executable")
    declared_executable = str(declared_executable) if declared_executable else None
    version_command = installation.get("version_command")
    command_shape = list(version_command) if isinstance(version_command, list) else None
    resolved_path: str | None = None
    digest: str | None = None
    digest_status = "not_attempted"
    if declared_executable:
        try:
            resolved = executable_resolver(declared_executable)
        except Exception:
            resolved = None
        if resolved:
            resolved_path = str(resolved)
            try:
                digest_result = dict(digest_reader(Path(resolved_path), max_digest_bytes))
            except Exception as exc:
                digest_result = {"status": "unreadable", "error_type": type(exc).__name__}
            digest_status = str(digest_result.get("status") or "unknown")
            if isinstance(digest_result.get("sha256"), str):
                digest = str(digest_result["sha256"])

    command_result: dict[str, Any] = {
        "returncode": None,
        "stdout": "",
        "stderr": "",
        "stdout_bytes": 0,
        "stderr_bytes": 0,
        "output_truncated": False,
        "timed_out": False,
        "error_type": None,
    }
    attempted = False
    command: list[str] | None = None
    if resolved_path and isinstance(version_command, list) and version_command and all(isinstance(item, str) for item in version_command):
        command = [str(item) for item in version_command]
        command[0] = resolved_path
        attempted = True
        command_result = _run_version_probe(
            command,
            timeout=timeout,
            max_output_bytes=max_output_bytes,
            command_runner=command_runner,
        )
    reported_version = _version_from_output(provider_id, command_result["stdout"], command_result["stderr"])
    probe_succeeded = attempted and command_result["returncode"] == 0 and bool(reported_version)
    if not declared_executable:
        probe_status = "not_configured"
    elif not resolved_path:
        probe_status = "executable_not_found"
    elif not attempted:
        probe_status = "version_probe_not_configured"
    elif command_result["timed_out"]:
        probe_status = "timeout"
    elif command_result["returncode"] != 0:
        probe_status = "failed"
    elif not reported_version:
        probe_status = "version_missing"
    else:
        probe_status = "healthy"

    installed_ok: bool | None
    if not resolved_path:
        installed_ok = None
    else:
        installed_ok = probe_succeeded and (not artifact.get("required") or bool(digest))
    runnable_ok: bool | None = None if not resolved_path else probe_succeeded
    artifact_ok: bool | None
    if artifact.get("required") is True:
        artifact_ok = None if not resolved_path else bool(digest)
    else:
        artifact_ok = True

    resource = provider.get("resource") if isinstance(provider.get("resource"), Mapping) else {}
    route_ref = f"route:abyss-machine/code-intelligence/{provider_id}"
    health = "healthy" if probe_succeeded else ("unknown" if not attempted else "failed")
    observation: dict[str, Any] = {
        "schema": OBSERVATION_COLLECTION_SCHEMA,
        "version": VERSION,
        "provider_id": provider_id,
        "observed_at": observed_at,
        "evidence_ref": evidence_ref,
        "owner_boundary": {
            "host_owner": host_owner,
            "consumer_owner": consumer_owner,
            "host_layer_mutates_stack": False,
        },
        "installed": {
            "executable": declared_executable,
            "path": resolved_path,
            "version": reported_version,
            "digest": digest,
        },
        "installation_identity": {
            "provider_id": provider_id,
            "owner": host_owner,
            "version": reported_version,
            "executable_or_path": resolved_path or declared_executable,
            "digest": digest,
        },
        "artifact_identity": {
            "provider_id": provider_id,
            "owner": host_owner,
            "class": artifact.get("class"),
            "subject_digest": digest,
            "source_ref": None,
            "digest_status": digest_status,
        },
        "trust": {
            "provider_id": provider_id,
            "owner": host_owner,
            "verdict": None,
            "subject_digest": digest,
            "evidence_ref": None,
        },
        "resource": {
            "provider_id": provider_id,
            "owner": host_owner,
            "kind": resource.get("kind"),
            "class": resource.get("class"),
            "demand_mib": resource.get("startup_demand_mib"),
            "profile_ref": resource.get("profile_ref"),
            "route_ref": route_ref,
            "host_memory": dict(memory),
        },
        "live_measurement": {
            "schema": "abyss_machine_code_intelligence_live_measurement_v1",
            "provider_id": provider_id,
            "owner": host_owner,
            "observed_at": observed_at,
            "evidence_ref": evidence_ref,
            "version": reported_version,
            "health": health,
        },
        "probe": {
            "status": probe_status,
            "attempted": attempted,
            "command_shape": command_shape,
            "returncode": command_result["returncode"],
            "stdout_bytes": command_result["stdout_bytes"],
            "stderr_bytes": command_result["stderr_bytes"],
            "output_truncated": command_result["output_truncated"],
            "timed_out": command_result["timed_out"],
            "error_type": command_result["error_type"],
            "raw_output": "discarded",
        },
        "gates": {
            "artifact_identity": _gate(artifact_ok, observed_at, evidence_ref),
            "trust_gate": _gate(None if artifact.get("required") is True else True, observed_at, evidence_ref),
            "installed_identity": _gate(installed_ok, observed_at, evidence_ref),
            "runnable_health": _gate(runnable_ok, observed_at, evidence_ref),
            "resource_route": _gate(True, observed_at, route_ref),
        },
        "policy": {
            "read_only": True,
            "network_used": False,
            "service_mutated": False,
            "trust_granted": False,
            "raw_command_output_persisted": False,
            "semantic_usefulness": "unproven",
        },
    }
    observation["admission"] = admit_provider(provider, observation)
    return observation


def collect_provider_observation(
    config: Mapping[str, Any],
    provider_id: str,
    *,
    observed_at: str | None = None,
    evidence_ref: str | None = None,
    executable_resolver: ExecutableResolverPort = shutil.which,
    command_runner: CommandRunnerPort = _default_command_runner,
    digest_reader: DigestReaderPort = digest_file,
    memory_probe: MemoryProbePort = host_memory_snapshot,
    resource_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Collect one provider's bounded host facts and evaluate them fail-closed."""

    validation = validate_provider_config(config)
    provider = _provider(config, provider_id)
    timestamp = observed_at or _utc_now()
    ref = evidence_ref or f"runtime:abyss-machine/code-intelligence/{provider_id}"
    if not validation["ok"] or provider is None:
        return {
            "schema": OBSERVATION_COLLECTION_SCHEMA,
            "version": VERSION,
            "provider_id": provider_id,
            "observed_at": timestamp,
            "evidence_ref": ref,
            "validation": validation,
            "status": "invalid_source" if not validation["ok"] else "unknown_provider",
            "admission": {
                "decision": "deny",
                "status": "not_admitted",
                "blocking_reasons": ["source_config_invalid" if not validation["ok"] else "unknown_provider"],
            },
            "policy": {"read_only": True, "network_used": False, "service_mutated": False, "trust_granted": False},
        }

    policy = _observation_policy(config)
    timeout = float(policy.get("version_probe_timeout_seconds", _DEFAULT_TIMEOUT_SECONDS))
    max_output_bytes = _bounded_limit(policy.get("max_version_output_bytes"), _DEFAULT_MAX_OUTPUT_BYTES, 1024 * 1024)
    max_digest_bytes = _bounded_limit(policy.get("max_file_digest_bytes"), _DEFAULT_MAX_DIGEST_BYTES, 512 * 1024 * 1024)
    if resource_snapshot is None:
        try:
            memory = dict(memory_probe())
        except Exception as exc:
            memory = {"status": "unknown", "source": "sysconf_read_only", "error_type": type(exc).__name__}
    else:
        memory = dict(resource_snapshot)
    return _provider_probe(
        provider,
        observed_at=timestamp,
        evidence_ref=ref,
        timeout=timeout,
        max_output_bytes=max_output_bytes,
        max_digest_bytes=max_digest_bytes,
        executable_resolver=executable_resolver,
        command_runner=command_runner,
        digest_reader=digest_reader,
        memory=memory,
    )


def collect_owner_admission_receipt(
    config: Mapping[str, Any],
    provider_id: str,
    observation: Mapping[str, Any],
    *,
    registry_dir: str | Path,
    subject_digest: str,
    record_id: str = "",
) -> dict[str, Any]:
    """Read the owner registry/trust boundary and prepare one bound receipt.

    This route never writes the registry and never turns an executable digest
    into an artifact subject digest. The caller must provide the exact bundle
    subject it wants the owner trust gate to inspect; the registry record and
    gate response remain the authority for admission.
    """

    validation = validate_provider_config(config)
    provider = _provider(config, provider_id)
    result: dict[str, Any] = {
        "schema": "abyss_machine_code_intelligence_owner_admission_route_v1",
        "version": VERSION,
        "provider_id": provider_id,
        "status": "not_admitted",
        "receipt": None,
        "validation": validation,
        "claim_limit": (
            "A receipt-ready result is an owner-bound source input only; it does not establish "
            "installation, deployment, runtime, semantic proof, landing, or acceptance."
        ),
    }
    if not validation["ok"] or provider is None:
        result["blocking_reasons"] = [
            "source_config_invalid" if not validation["ok"] else "unknown_provider"
        ]
        return result
    if not isinstance(observation, Mapping):
        result["blocking_reasons"] = ["owner_admission_observation_missing"]
        return result
    if not _valid_digest(subject_digest):
        result["blocking_reasons"] = ["owner_admission_subject_digest_required"]
        return result
    if record_id and not _valid_digest(record_id):
        result["blocking_reasons"] = ["owner_admission_record_id_invalid"]
        return result

    admission = config.get("admission") if isinstance(config.get("admission"), Mapping) else {}
    route = admission.get("owner_admission_boundary") if isinstance(admission.get("owner_admission_boundary"), Mapping) else {}
    try:
        from .artifact_bundles import trust_gate

        gate = trust_gate(
            registry_dir,
            artifact_class=str(route.get("artifact_class") or ""),
            subject_digest=subject_digest,
            record_id=record_id,
            consumer_intent=str(route.get("trust_gate", {}).get("consumer_intent") or "runtime"),
            expected_source_repo=str(route.get("trust_gate", {}).get("expected_source_repo") or "abyss-machine"),
            expected_trust_root_mode=str(route.get("trust_gate", {}).get("expected_trust_root_mode") or "oci_registry"),
            require_latest=route.get("trust_gate", {}).get("require_latest") is True,
        )
    except Exception as exc:
        result["blocking_reasons"] = [f"owner_admission_trust_gate_error:{type(exc).__name__}"]
        result["gate"] = {"ok": False, "verdict": "unknown", "error_type": type(exc).__name__}
        return result

    result["gate"] = gate
    record = gate.get("record") if isinstance(gate, Mapping) else None
    required_verdict = str(route.get("trust_gate", {}).get("required_verdict") or "allow")
    if (
        not isinstance(gate, Mapping)
        or gate.get("ok") is not True
        or gate.get("verdict") != required_verdict
        or not isinstance(record, Mapping)
    ):
        reasons = gate.get("reasons") if isinstance(gate, Mapping) else None
        result["blocking_reasons"] = [str(item) for item in reasons] if isinstance(reasons, list) and reasons else [
            "owner_admission_trust_gate_not_allow"
        ]
        return result

    gate_registry_ref = str(gate.get("registry_dir") or "").strip()
    if not gate_registry_ref:
        result["blocking_reasons"] = ["owner_admission_registry_ref_missing"]
        return result
    registry_ref = gate_registry_ref if gate_registry_ref.startswith("registry:") else "registry:" + gate_registry_ref
    try:
        receipt = _owner_admission_receipt_from_verified_gate(
            provider,
            observation,
            gate,
            record,
            source_config_digest=_config_digest(config) or "",
            registry_ref=registry_ref,
        )
    except ValueError as exc:
        result["blocking_reasons"] = [f"owner_admission_receipt_issue_failed:{str(exc)}"]
        return result
    result.update(
        {
            "status": "receipt_ready",
            "receipt": receipt,
            "receipt_digest": receipt["receipt_digest"],
            "record_id": record.get("record_id"),
        }
    )
    return result


def collect_code_intelligence_observations(
    config: Mapping[str, Any] | None = None,
    *,
    observed_at: str | None = None,
    source_epoch: str | None = None,
    source_config_path: Path | None = None,
    installed_config_path: Path | None = None,
    executable_resolver: ExecutableResolverPort = shutil.which,
    command_runner: CommandRunnerPort = _default_command_runner,
    digest_reader: DigestReaderPort = digest_file,
    memory_probe: MemoryProbePort = host_memory_snapshot,
) -> dict[str, Any]:
    """Collect the whole configured direction sequentially under its read-only policy."""

    effective_config = config if isinstance(config, Mapping) else code_intelligence_config()
    timestamp = observed_at or _utc_now()
    validation = validate_provider_config(effective_config)
    source = effective_config.get("source") if isinstance(effective_config.get("source"), Mapping) else {}
    source_config_ref = str(source.get("config_ref") or "config-templates/etc/abyss-machine/code-intelligence.json")
    source_ref = "source:" + source_config_ref.lstrip("/")
    source_epoch_binding_status = (
        "bound" if _valid_digest(source_epoch) else ("invalid" if source_epoch else "unbound")
    )
    try:
        memory = dict(memory_probe())
    except Exception as exc:
        memory = {"status": "unknown", "source": "sysconf_read_only", "error_type": type(exc).__name__}

    providers: dict[str, dict[str, Any]] = {}
    if validation["ok"]:
        configured = effective_config.get("providers")
        for provider in configured if isinstance(configured, list) else []:
            if not isinstance(provider, Mapping):
                continue
            provider_id = str(provider.get("id") or "")
            if not provider_id:
                continue
            providers[provider_id] = collect_provider_observation(
                effective_config,
                provider_id,
                observed_at=timestamp,
                evidence_ref=f"runtime:abyss-machine/code-intelligence/{provider_id}",
                executable_resolver=executable_resolver,
                command_runner=command_runner,
                digest_reader=digest_reader,
                memory_probe=memory_probe,
                resource_snapshot=memory,
            )

    if source_config_path is not None and installed_config_path is not None:
        projection_limit = _bounded_limit(
            _observation_policy(effective_config).get("max_file_digest_bytes"),
            _DEFAULT_MAX_DIGEST_BYTES,
            512 * 1024 * 1024,
        )
        projection = compare_source_install_projection(
            source_config_path,
            installed_config_path,
            max_bytes=projection_limit,
            source_ref=source_ref,
            installed_ref="installed:host/etc/abyss-machine/code-intelligence.json",
            digest_reader=digest_reader,
        )
    else:
        projection = {
            "schema": PROJECTION_SCHEMA,
            "version": VERSION,
            "status": "not_requested",
            "current": None,
            "read_only": True,
            "mutation_performed": False,
            "synchronization_performed": False,
            "claim_limit": "both source and installed paths are required for projection comparison",
        }

    admissions = [item.get("admission", {}) for item in providers.values()]
    admitted = sum(1 for admission in admissions if isinstance(admission, Mapping) and admission.get("status") == "admitted")
    healthy = sum(
        1
        for item in providers.values()
        if isinstance(item.get("live_measurement"), Mapping) and item["live_measurement"].get("health") == "healthy"
    )
    return {
        "schema": OBSERVATION_COLLECTION_SCHEMA,
        "version": VERSION,
        "observed_at": timestamp,
        "source": {
            "owner": "abyss-machine",
            "config_ref": source_config_ref,
            "config_digest": _config_digest(effective_config),
            "source_epoch": source_epoch,
            "source_epoch_binding_status": source_epoch_binding_status,
            "binding_is_not_landing": True,
        },
        "validation": validation,
        "host_capacity": memory,
        "source_install_projection": projection,
        "providers": providers,
        "summary": {
            "provider_count": len(providers),
            "healthy_version_probes": healthy,
            "admitted_by_machine_contract": admitted,
            "not_admitted_by_machine_contract": len(providers) - admitted,
            "semantic_usefulness_proven": False,
        },
        "policy": {
            "mode": "bounded_read_only",
            "network_used": False,
            "service_mutated": False,
            "trust_granted": False,
            "source_or_install_synchronized": False,
            "raw_command_output_persisted": False,
            "provider_lifecycle_owner": "abyss-stack",
            "normalized_observation_consumer": "aoa-kag",
            "semantic_proof_owner": "aoa-evals",
        },
        "non_claims": [
            "A version probe is not a provider lifecycle or semantic symbol probe.",
            "A source/install projection is not installation, deployment, or landing evidence.",
            "Machine admission is facts-only and does not establish semantic proof or owner acceptance.",
        ],
    }


collect_code_intelligence_snapshot = collect_code_intelligence_observations


__all__ = [
    "OBSERVATION_COLLECTION_SCHEMA",
    "PROJECTION_SCHEMA",
    "collect_code_intelligence_observations",
    "collect_code_intelligence_snapshot",
    "collect_owner_admission_receipt",
    "collect_provider_observation",
    "compare_source_install_projection",
    "digest_file",
    "host_memory_snapshot",
]

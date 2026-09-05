"""Bounded host admission for the AoA raw-block storage owner.

This module is deliberately a small bridge.  The AoA repository owns session
selection, generation guards, staging, publication, and cursor semantics.  The
host layer only admits the pinned public bundle, checks the Vault preflight,
obtains the existing memory/indexing resource lease, and records a compact
child outcome.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import selectors
import signal
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, Mapping, Sequence


SCHEMA = "abyss_machine_aoa_session_memory_storage_runner_v1"
VERSION = "0.1.0"
ARTIFACT_CLASS = "aoa_session_memory_portable_bundle"
SUBJECT_DIGEST = "sha256:f10095e20e5140237e12f5e535e9ab4a2b0ca0c288d350d2e29924f31b079a2b"
SOURCE_REPO = "aoa-session-memory"
SOURCE_REF = "92a89973698f281033ac37ae93959b15b3a6a2a2"
TRUST_ROOT_MODE = "public_release"
CONSUMER_INTENT = "runtime"
OWNER_SCRIPT_RELATIVE = Path("scripts/aoa_session_memory.py")
OWNER_JOB = "raw-block-storage-compact"
RESOURCE_DEMAND_KEY = "aoa-session-memory:raw-block-storage-compact"
RESOURCE_DEMAND_OWNER = "aoa-session-memory"
RESOURCE_ESTIMATE_SOURCE = "owner-capped-sealed-block-run"
RESOURCE_ESTIMATE_CONFIDENCE = "medium"
RESOURCE_CLASS = "medium"
RESOURCE_KIND = "indexing"
RESOURCE_MEMORY_DEMAND_MIB = 2048
MAX_PLAIN_BYTES = 1 * 1024 * 1024 * 1024
MAX_RETRY_DEADLINE_SEC = 15 * 60
RETRY_DELAYS_SEC = (5, 15, 30)
MAX_CHILD_CAPTURE_BYTES = 8 * 1024 * 1024
MAX_CHILD_SUMMARY_BYTES = 3500
# The resource command performs policy planning and lease admission before it
# calls systemd-run.  Keep that phase, the adapter's own wait margin, and a
# bounded post-timeout unit probe inside the single runner deadline.
RESOURCE_PRELAUNCH_RESERVE_SEC = 45
RESOURCE_POST_TIMEOUT_PROBE_SEC = 15
RESOURCE_TIMEOUT_RESERVE_SEC = (
    RESOURCE_PRELAUNCH_RESERVE_SEC + RESOURCE_POST_TIMEOUT_PROBE_SEC
)
RESOURCE_MIN_TIMEOUT_SEC = 1
DEFAULT_CONFIG_PATH = Path("/etc/abyss-machine/aoa-session-memory-storage.json")
DEFAULT_REGISTRY_DIR = Path("/var/lib/abyss-machine/artifacts/bundle-registry")
# Subject materialization is large and follows the host's writable storage
# route.  The selected registry record remains authoritative for the final
# bundle directory, so this is only the rendered-config/default lookup root.
DEFAULT_SUBJECT_STORE_ROOT = Path("/srv/abyss-machine/storage/artifacts/subjects")
DEFAULT_STATE_DIR = Path(
    "/var/lib/abyss-machine/storage/aoa-session-memory-raw-block-compact"
)
DEFAULT_WORKSPACE_ROOT = Path("/srv/AbyssOS")
DEFAULT_AOA_ROOT = DEFAULT_WORKSPACE_ROOT / ".aoa"
DEFAULT_HOST_CLI = Path("/usr/local/bin/abyss-machine")
DEFAULT_BACKUP_CLI = Path("/usr/local/bin/abyss-backup")
DEFAULT_PYTHON = Path("/usr/bin/python3")
LIVE_ARCHIVE_ROOT = Path("/srv/AbyssOS/.aoa")
OWNER_ARTIFACT_TYPE = "session_memory_raw_block_storage_compact"
OWNER_MAINTENANCE_ARTIFACT_TYPE = "session_memory_raw_block_storage_maintenance"
OWNER_LOCK_CONFLICT_ARTIFACT_TYPE = "session_memory_maintenance_lock_conflict"
OWNER_ARTIFACT_TYPES = {
    OWNER_ARTIFACT_TYPE,
    OWNER_MAINTENANCE_ARTIFACT_TYPE,
    OWNER_LOCK_CONFLICT_ARTIFACT_TYPE,
}
RETRYABLE_OWNER_STATUSES = {"skipped_lock_held", "deferred_conflicting_lease"}
SAFE_DEFERRED_STATUSES = {
    "skipped_lock_held",
    "deferred_conflicting_lease",
    "deferred_session_lease",
    "skipped_live_deferred",
}
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


RunPort = Callable[..., subprocess.CompletedProcess[str]]
SleepPort = Callable[[float], None]
ClockPort = Callable[[], float]


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def _path_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return True


def _is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def _as_path(value: Any, default: Path) -> Path:
    text = str(value if value is not None else "").strip()
    return Path(text).expanduser() if text else default


def _config_int(
    raw: Mapping[str, Any],
    key: str,
    default: int,
    errors: list[str],
) -> int:
    """Read a JSON integer without silently accepting malformed config."""
    if key not in raw:
        return default
    value = raw[key]
    if type(value) is not int:  # bool is an int subclass, but not valid here.
        errors.append(f"{key}_must_be_integer")
        return default
    return value


@dataclass(frozen=True)
class RunnerConfig:
    config_path: Path = DEFAULT_CONFIG_PATH
    enabled: bool = False
    record_id: str = ""
    mode: str = "pilot"
    reclaim_plain: bool = False
    pilot_verified: bool = False
    pilot_evidence_ref: str = ""
    artifact_class: str = ARTIFACT_CLASS
    subject_digest: str = SUBJECT_DIGEST
    source_repo: str = SOURCE_REPO
    source_ref: str = SOURCE_REF
    registry_dir: Path = DEFAULT_REGISTRY_DIR
    subject_store_root: Path = DEFAULT_SUBJECT_STORE_ROOT
    state_dir: Path = DEFAULT_STATE_DIR
    workspace_root: Path = DEFAULT_WORKSPACE_ROOT
    aoa_root: Path = DEFAULT_AOA_ROOT
    host_cli: Path = DEFAULT_HOST_CLI
    backup_cli: Path = DEFAULT_BACKUP_CLI
    python_executable: Path = DEFAULT_PYTHON
    include_open_tail: bool = True
    session_limit: int = 4
    scan_limit: int = 32
    max_plain_bytes: int = MAX_PLAIN_BYTES
    sample_limit: int = 8
    memory_demand_mib: int = RESOURCE_MEMORY_DEMAND_MIB
    retry_delays_sec: tuple[int, ...] = RETRY_DELAYS_SEC
    retry_deadline_sec: int = MAX_RETRY_DEADLINE_SEC

    @property
    def bundle_dir(self) -> Path:
        digest = self.subject_digest.removeprefix("sha256:")
        return self.subject_store_root / self.artifact_class / digest

    @property
    def owner_script(self) -> Path:
        return self.bundle_dir / OWNER_SCRIPT_RELATIVE


def _reclaim_authorized(config: RunnerConfig) -> bool:
    return bool(
        config.mode == "reclaim"
        and config.reclaim_plain
        and config.pilot_verified
        and config.pilot_evidence_ref.strip()
    )


def _configuration_from_mapping(path: Path, raw: Mapping[str, Any]) -> tuple[RunnerConfig, list[str]]:
    errors: list[str] = []

    if raw.get("schema") != SCHEMA:
        errors.append("schema_mismatch")

    def fixed_text(key: str, expected: str) -> str:
        value = raw.get(key, expected)
        value_text = str(value or "")
        if value_text != expected:
            errors.append(f"{key}_mismatch")
        return value_text

    enabled_value = raw.get("enabled", False)
    if not _is_bool(enabled_value):
        errors.append("enabled_must_be_boolean")
        enabled = False
    else:
        enabled = bool(enabled_value)

    reclaim_value = raw.get("reclaim_plain", False)
    if not _is_bool(reclaim_value):
        errors.append("reclaim_plain_must_be_boolean")
        reclaim_plain = False
    else:
        reclaim_plain = bool(reclaim_value)

    pilot_verified_value = raw.get("pilot_verified", False)
    if not _is_bool(pilot_verified_value):
        errors.append("pilot_verified_must_be_boolean")
        pilot_verified = False
    else:
        pilot_verified = bool(pilot_verified_value)

    mode_value = raw.get("mode", "pilot")
    if not isinstance(mode_value, str):
        errors.append("mode_must_be_string")
        mode = ""
    else:
        mode = mode_value
    if mode not in {"pilot", "reclaim"}:
        errors.append("mode_unknown")
    if mode == "reclaim" and not reclaim_plain:
        errors.append("reclaim_mode_requires_reclaim_plain")
    if mode == "pilot" and reclaim_plain:
        errors.append("pilot_mode_cannot_remove_plain")
    pilot_evidence_value = raw.get("pilot_evidence_ref", "")
    if not isinstance(pilot_evidence_value, str):
        errors.append("pilot_evidence_ref_must_be_string")
        pilot_evidence_ref = ""
    else:
        pilot_evidence_ref = pilot_evidence_value.strip()
    record_id_value = raw.get("record_id", "")
    if not isinstance(record_id_value, str):
        errors.append("record_id_must_be_string")
        record_id = ""
    else:
        record_id = record_id_value.strip()
    if reclaim_plain and (not pilot_verified or not pilot_evidence_ref):
        errors.append("reclaim_requires_verified_pilot_evidence")
    if enabled and not record_id:
        errors.append("record_id_required_when_enabled")

    artifact_class = fixed_text("artifact_class", ARTIFACT_CLASS)
    subject_digest = fixed_text("subject_digest", SUBJECT_DIGEST)
    source_repo = fixed_text("source_repo", SOURCE_REPO)
    source_ref = fixed_text("source_ref", SOURCE_REF)
    if not _SHA256_RE.fullmatch(subject_digest):
        errors.append("subject_digest_must_be_sha256")

    registry_dir = _as_path(raw.get("registry_dir"), DEFAULT_REGISTRY_DIR)
    if registry_dir != DEFAULT_REGISTRY_DIR:
        errors.append("registry_dir_must_use_authoritative_store")

    include_open_tail_value = raw.get("include_open_tail", True)
    if not _is_bool(include_open_tail_value):
        errors.append("include_open_tail_must_be_boolean")
        include_open_tail = True
    else:
        include_open_tail = bool(include_open_tail_value)

    retry_delays_raw = raw.get("retry_delays_sec", list(RETRY_DELAYS_SEC))
    if (
        not isinstance(retry_delays_raw, list)
        or any(type(item) is not int for item in retry_delays_raw)
        or tuple(retry_delays_raw) != RETRY_DELAYS_SEC
    ):
        errors.append("retry_delays_must_be_5_15_30")
    retry_delays = RETRY_DELAYS_SEC
    retry_deadline_sec = _config_int(
        raw, "retry_deadline_sec", MAX_RETRY_DEADLINE_SEC, errors
    )
    if retry_deadline_sec < 1 or retry_deadline_sec > MAX_RETRY_DEADLINE_SEC:
        errors.append("retry_deadline_exceeds_15_minutes")

    session_limit = _config_int(raw, "session_limit", 4, errors)
    scan_limit = _config_int(raw, "scan_limit", 32, errors)
    max_plain_bytes = _config_int(raw, "max_plain_bytes", MAX_PLAIN_BYTES, errors)
    sample_limit = _config_int(raw, "sample_limit", 8, errors)
    memory_demand_mib = _config_int(
        raw, "memory_demand_mib", RESOURCE_MEMORY_DEMAND_MIB, errors
    )
    if not 1 <= session_limit <= 4:
        errors.append("session_limit_out_of_bounds")
    if not 1 <= scan_limit <= 32:
        errors.append("scan_limit_out_of_bounds")
    if not 1 <= max_plain_bytes <= MAX_PLAIN_BYTES:
        errors.append("max_plain_bytes_out_of_bounds")
    if not 1 <= sample_limit <= 8:
        errors.append("sample_limit_out_of_bounds")
    if not 1 <= memory_demand_mib <= 4096:
        errors.append("memory_demand_mib_out_of_bounds")

    reservation = raw.get("reservation")
    if not isinstance(reservation, Mapping):
        errors.append("reservation_contract_required")
    else:
        if reservation.get("status") != "reservation_not_supported_for_owner_path":
            errors.append("reservation_status_mismatch")
        if reservation.get("hard_bytes_reservation") is not False:
            errors.append("hard_bytes_reservation_must_be_false")

    return (
        RunnerConfig(
            config_path=path,
            enabled=enabled,
            record_id=record_id,
            mode=mode,
            reclaim_plain=reclaim_plain,
            pilot_verified=pilot_verified,
            pilot_evidence_ref=pilot_evidence_ref,
            artifact_class=artifact_class,
            subject_digest=subject_digest,
            source_repo=source_repo,
            source_ref=source_ref,
            registry_dir=registry_dir,
            subject_store_root=_as_path(raw.get("subject_store_root"), DEFAULT_SUBJECT_STORE_ROOT),
            state_dir=_as_path(raw.get("state_dir"), DEFAULT_STATE_DIR),
            workspace_root=_as_path(raw.get("workspace_root"), DEFAULT_WORKSPACE_ROOT),
            aoa_root=_as_path(raw.get("aoa_root"), DEFAULT_AOA_ROOT),
            host_cli=_as_path(raw.get("host_cli"), DEFAULT_HOST_CLI),
            backup_cli=_as_path(raw.get("backup_cli"), DEFAULT_BACKUP_CLI),
            python_executable=_as_path(raw.get("python_executable"), DEFAULT_PYTHON),
            include_open_tail=include_open_tail,
            session_limit=session_limit,
            scan_limit=scan_limit,
            max_plain_bytes=max_plain_bytes,
            sample_limit=sample_limit,
            memory_demand_mib=memory_demand_mib,
            retry_delays_sec=retry_delays,
            retry_deadline_sec=retry_deadline_sec,
        ),
        sorted(set(errors)),
    )


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> tuple[RunnerConfig | None, list[str]]:
    """Load one rendered host config without accepting a live-script fallback."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, ["configuration_missing"]
    except (OSError, UnicodeDecodeError):
        return None, ["configuration_unreadable"]
    except json.JSONDecodeError:
        return None, ["configuration_invalid_json"]
    if not isinstance(raw, dict):
        return None, ["configuration_must_be_object"]
    config, errors = _configuration_from_mapping(path, raw)
    return config, errors


def trust_gate_argv(config: RunnerConfig) -> list[str]:
    return [
        str(config.host_cli),
        "artifacts",
        "trust-gate",
        "--registry-dir",
        str(config.registry_dir),
        "--artifact-class",
        config.artifact_class,
        "--subject-digest",
        config.subject_digest,
        "--record-id",
        config.record_id,
        "--consumer-intent",
        CONSUMER_INTENT,
        "--source-repo",
        config.source_repo,
        "--source-ref",
        config.source_ref,
        "--trust-root-mode",
        TRUST_ROOT_MODE,
        "--json",
    ]


def vault_preflight_argv(config: RunnerConfig) -> list[str]:
    # The owner backup CLI has no JSON flag for timer-preflight.  Its exit code
    # is the guard; stdout is deliberately discarded by the bridge summary.
    return [str(config.backup_cli), "timer-preflight", "sessions"]


def _resource_unit_name(attempt: int) -> str:
    """Return a unique, stable transient unit identity for one attempt."""
    # The PID prevents a later runner invocation from probing or stopping an
    # earlier unit.  The attempt number lets lock retries remain distinguishable
    # while keeping the identity free of session names or private paths.
    return f"aoa-session-memory-raw-block-compact-{os.getpid()}-{attempt}.service"


def owner_resource_argv(
    config: RunnerConfig,
    *,
    bundle_dir: Path | None = None,
    outer_timeout_sec: float | None = None,
    attempt: int = 1,
) -> list[str]:
    admitted_bundle = bundle_dir if bundle_dir is not None else config.bundle_dir
    owner_script = admitted_bundle / OWNER_SCRIPT_RELATIVE
    outer_timeout = (
        max(
            float(RESOURCE_MIN_TIMEOUT_SEC),
            float(config.retry_deadline_sec)
            - float(RESOURCE_POST_TIMEOUT_PROBE_SEC),
        )
        if outer_timeout_sec is None
        else max(0.0, float(outer_timeout_sec))
    )
    resource_timeout = max(
        float(RESOURCE_MIN_TIMEOUT_SEC),
        min(
            float(config.retry_deadline_sec),
            outer_timeout - float(RESOURCE_PRELAUNCH_RESERVE_SEC),
        ),
    )
    resource_timeout_text = (
        str(int(resource_timeout))
        if resource_timeout.is_integer()
        else f"{resource_timeout:.3f}".rstrip("0").rstrip(".")
    )
    command = [
        str(config.host_cli),
        "resource",
        "launch",
        "--class",
        RESOURCE_CLASS,
        "--kind",
        RESOURCE_KIND,
        "--unattended",
        "--timeout",
        resource_timeout_text,
        "--memory-demand-mib",
        str(config.memory_demand_mib),
        "--demand-key",
        RESOURCE_DEMAND_KEY,
        "--demand-owner",
        RESOURCE_DEMAND_OWNER,
        "--estimate-source",
        RESOURCE_ESTIMATE_SOURCE,
        "--estimate-confidence",
        RESOURCE_ESTIMATE_CONFIDENCE,
        "--success-on-block",
        "--no-thermal-sample",
        "--unit",
        _resource_unit_name(attempt),
        "--json",
        "--",
        str(config.host_cli),
        "storage",
        "aoa-session-memory-compact-child",
        "--python",
        str(config.python_executable),
        "--owner-script",
        str(owner_script),
        "--",
        str(config.python_executable),
        str(owner_script),
        "raw-block-storage-compact",
        "all",
        "--workspace-root",
        str(config.workspace_root),
        "--aoa-root",
        str(config.aoa_root),
        "--scheduled",
        "--limit",
        str(config.session_limit),
        "--scan-limit",
        str(config.scan_limit),
        "--max-plain-bytes",
        str(config.max_plain_bytes),
        "--sample-limit",
        str(config.sample_limit),
        "--apply",
        "--write-report",
    ]
    if config.include_open_tail:
        command.append("--include-open-tail")
    if _reclaim_authorized(config):
        command.append("--confirm-remove-plain")
    return command


def _json_documents(value: str, *, max_chars: int = 131072) -> list[dict[str, Any]]:
    text = str(value or "")[-max_chars:]
    if not text:
        return []
    documents: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(candidate: Any) -> None:
        if not isinstance(candidate, dict):
            return
        encoded = json.dumps(candidate, sort_keys=True, separators=(",", ":"), default=str)
        if encoded not in seen:
            seen.add(encoded)
            documents.append(candidate)

    try:
        add(json.loads(text))
    except json.JSONDecodeError:
        pass
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            add(json.loads(line))
        except json.JSONDecodeError:
            continue
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            candidate, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        add(candidate)
    return documents


def _resource_result_indicates_timeout(result: Mapping[str, Any]) -> bool:
    """Recognize both an outer wait timeout and adapter-reported timeout."""
    try:
        top_returncode = int(result.get("returncode", 1))
    except (TypeError, ValueError):
        top_returncode = 1
    if result.get("error") == "command_timeout" or top_returncode == 124:
        return True
    documents = _json_documents(str(result.get("stdout") or ""))

    def visit(value: Any) -> bool:
        if isinstance(value, Mapping):
            try:
                if int(value.get("returncode", -1)) == 124:
                    return True
            except (TypeError, ValueError):
                pass
            if value.get("error") == "command_timeout":
                return True
            return any(visit(item) for item in value.values())
        if isinstance(value, list):
            return any(visit(item) for item in value)
        return False

    return any(visit(document) for document in documents)


def _owner_like(value: Mapping[str, Any]) -> bool:
    artifact_type = str(value.get("artifact_type") or "")
    if artifact_type:
        return artifact_type in OWNER_ARTIFACT_TYPES
    return "storage_mode" in value and "status" in value and "plain_bytes" in value


def _find_owner_payload(value: Any, *, depth: int = 0) -> dict[str, Any] | None:
    if depth > 6:
        return None
    if isinstance(value, Mapping):
        if _owner_like(value):
            return dict(value)
        for key in (
            "execution",
            "child",
            "result",
            "payload",
            "output",
            "owner",
            "compact",
            "maintenance",
            "stdout",
            "stdout_tail",
            "stderr_tail",
        ):
            if key in value:
                found = _find_owner_payload(value[key], depth=depth + 1)
                if found is not None:
                    return found
        return None
    if isinstance(value, str):
        for document in _json_documents(value):
            found = _find_owner_payload(document, depth=depth + 1)
            if found is not None:
                return found
    return None


def _owner_status(payload: Mapping[str, Any]) -> str:
    """Resolve maintenance status while retaining a nested lock conflict."""
    compact = payload.get("compact")
    compact_payload = compact if isinstance(compact, Mapping) else {}
    compact_artifact_type = str(compact_payload.get("artifact_type") or "")
    compact_status = str(compact_payload.get("status") or "")
    if (
        compact_artifact_type == OWNER_LOCK_CONFLICT_ARTIFACT_TYPE
        and compact_status in RETRYABLE_OWNER_STATUSES
    ):
        return compact_status
    return str(payload.get("status") or compact_status or "unknown")


def _string_list(value: Any, *, limit: int = 20) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value[:limit]:
        text = str(item).replace("\n", " ").strip()
        if text:
            result.append(text[:240])
    return result


def _safe_summary_value(value: Any, *, depth: int = 0) -> Any:
    """Bound cursor/ref-shaped values without copying owner-private payloads."""
    if depth > 2:
        return None
    if isinstance(value, bool) or isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return value.replace("\n", " ")[:512]
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key, item in list(value.items())[:32]:
            safe_item = _safe_summary_value(item, depth=depth + 1)
            if safe_item is not None:
                output[str(key).replace("\n", " ")[:240]] = safe_item
        return output
    if isinstance(value, list):
        return [
            safe_item
            for item in value[:32]
            if (safe_item := _safe_summary_value(item, depth=depth + 1)) is not None
        ]
    return None


def _payload_value(
    payload: Mapping[str, Any], compact: Mapping[str, Any], key: str
) -> Any:
    value = payload.get(key)
    return compact.get(key) if value is None else value


def _status_counts(value: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not isinstance(value, list):
        return counts
    for row in value[:64]:
        if isinstance(row, Mapping):
            status = str(row.get("status") or "unknown")[:120]
            counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def sanitize_owner_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Keep owner status and counters while dropping private/raw fields."""
    compact_value = payload.get("compact")
    compact = compact_value if isinstance(compact_value, Mapping) else {}
    artifact_type_value = payload.get("artifact_type")
    artifact_type = (
        str(artifact_type_value)
        if str(artifact_type_value or "") in OWNER_ARTIFACT_TYPES
        else OWNER_ARTIFACT_TYPE
    )
    result: dict[str, Any] = {
        "artifact_type": artifact_type,
        "status": str(_payload_value(payload, compact, "status") or "unknown"),
        "ok": _payload_value(payload, compact, "ok") is True,
        "mutates": _payload_value(payload, compact, "mutates") is True,
    }
    nested_artifact_type = str(compact.get("artifact_type") or "")
    if nested_artifact_type in OWNER_ARTIFACT_TYPES and nested_artifact_type != artifact_type:
        result["nested_artifact_type"] = nested_artifact_type
    for key in (
        "apply",
        "confirm_remove_plain",
        "storage_mutates",
        "conflict_kind",
        "deferred_reason",
        "lock_wait_ms",
        "lock_timeout_sec",
        "scanned_count",
        "selected_count",
        "selected_block_counts",
        "selected_plain_bytes",
        "eligible_plain_bytes",
        "estimated_compressed_bytes",
        "successful_publish_session_ids",
        "deferred_session_count",
        "skipped_live_deferred_count",
        "apply_failure_count",
        "planned_count",
        "compressed_count",
        "removed_plain_count",
        "plain_bytes",
        "compressed_bytes",
        "created_compressed_bytes",
        "removed_plain_bytes",
        "net_reclaim_bytes",
        "cursor_before",
        "cursor_after",
        "cursor_committed",
        "session_cursor_committed",
        "block_cursor_before",
        "block_cursor_after",
        "block_cursor_committed",
        "owner_payload_complete",
        "child_returncode",
        "child_stdout_bytes",
        "child_stderr_bytes",
        "child_capture_limit_bytes",
        "child_summary_truncated",
    ):
        value = _payload_value(payload, compact, key)
        safe_value = _safe_summary_value(value)
        if safe_value is not None:
            result[key] = safe_value
    diagnostic_values = _string_list(payload.get("diagnostics"), limit=24)
    diagnostic_values.extend(_string_list(compact.get("diagnostics"), limit=24))
    result["diagnostic_codes"] = list(
        dict.fromkeys(str(item).split(":", 1)[0][:160] for item in diagnostic_values)
    )
    compact_rows = compact.get("results")
    result_rows = compact_rows if isinstance(compact_rows, list) else payload.get("results")
    result["result_status_counts"] = _status_counts(result_rows)
    result["scanned_status_counts"] = _status_counts(payload.get("scanned"))
    for audit_key in ("preflight_raw_block_ref_audit", "post_apply_raw_block_ref_audit"):
        audit = _payload_value(payload, compact, audit_key)
        if not isinstance(audit, Mapping):
            continue
        result[audit_key] = {
            key: audit.get(key)
            for key in ("ok", "status", "checked_count", "missing_count", "mismatch_count")
            if key in audit and isinstance(audit[key], (bool, int, float, str))
        }
    return result


def _child_failure_payload(
    status: str,
    *,
    diagnostic: str,
    returncode: int | None = None,
    stdout_bytes: int | None = None,
    stderr_bytes: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "artifact_type": OWNER_MAINTENANCE_ARTIFACT_TYPE,
        "status": status,
        "ok": False,
        "mutates": False,
        "owner_payload_complete": False,
        "diagnostic_codes": [diagnostic],
    }
    if returncode is not None:
        payload["child_returncode"] = returncode
    if stdout_bytes is not None:
        payload["child_stdout_bytes"] = stdout_bytes
    if stderr_bytes is not None:
        payload["child_stderr_bytes"] = stderr_bytes
    payload["child_capture_limit_bytes"] = MAX_CHILD_CAPTURE_BYTES
    return payload


def _bounded_child_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Keep the wrapper result below the resource adapter's 4 KiB tail."""
    candidate = dict(payload)
    if len(json.dumps(candidate, ensure_ascii=False, sort_keys=True).encode("utf-8")) <= MAX_CHILD_SUMMARY_BYTES:
        return candidate

    diagnostics = candidate.get("diagnostic_codes")
    if isinstance(diagnostics, list):
        candidate["diagnostic_codes"] = [str(item)[:80] for item in diagnostics[:8]]
    candidate["scanned_status_counts"] = {}
    candidate["child_summary_truncated"] = True
    if len(json.dumps(candidate, ensure_ascii=False, sort_keys=True).encode("utf-8")) <= MAX_CHILD_SUMMARY_BYTES:
        return candidate

    essential_keys = (
        "artifact_type",
        "status",
        "ok",
        "mutates",
        "storage_mutates",
        "cursor_before",
        "cursor_after",
        "cursor_committed",
        "block_cursor_before",
        "block_cursor_after",
        "block_cursor_committed",
        "owner_payload_complete",
        "child_returncode",
        "child_stdout_bytes",
        "child_stderr_bytes",
        "child_capture_limit_bytes",
    )
    bounded = {
        key: candidate[key]
        for key in essential_keys
        if key in candidate
    }
    bounded["diagnostic_codes"] = ["child_summary_truncated"]
    bounded["child_summary_truncated"] = True
    if len(json.dumps(bounded, ensure_ascii=False, sort_keys=True).encode("utf-8")) > MAX_CHILD_SUMMARY_BYTES:
        bounded = {
            key: bounded[key]
            for key in (
                "artifact_type",
                "status",
                "ok",
                "mutates",
                "child_summary_truncated",
            )
            if key in bounded
        }
        bounded["diagnostic_codes"] = ["child_summary_truncated"]
    return bounded


def _emit_child_payload(payload: Mapping[str, Any]) -> None:
    print(json.dumps(_bounded_child_summary(payload), ensure_ascii=False, sort_keys=True))


def _signal_owner_process(process: subprocess.Popen[Any], signal_number: int) -> None:
    """Signal the owner and its descendants without relying on output limits."""
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal_number)
        return
    except (OSError, ProcessLookupError):
        pass
    try:
        process.send_signal(signal_number)
    except (OSError, ProcessLookupError):
        return


def _capture_owner_json(
    argv: Sequence[str],
    *,
    max_bytes: int,
) -> tuple[int, str | None, int, int, str | None]:
    """Run the owner with bounded streaming capture, never retaining raw output.

    Both pipes are drained concurrently so a verbose owner cannot deadlock on
    the other stream.  Once either stream crosses the cap, the owner process
    group is terminated and subsequent bytes are discarded; the temporary
    files therefore stay bounded while cleanup still reaches a terminal child.
    """
    stdout_bytes = 0
    stderr_bytes = 0
    capture_error: str | None = None
    try:
        with tempfile.TemporaryFile(mode="w+b") as stdout_file, tempfile.TemporaryFile(
            mode="w+b"
        ) as stderr_file:
            process = subprocess.Popen(
                list(argv),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            selector = selectors.DefaultSelector()
            streams: dict[Any, tuple[str, Any]] = {}
            stdout_stream: Any = process.stdout
            stderr_stream: Any = process.stderr
            if stdout_stream is not None:
                selector.register(stdout_stream, selectors.EVENT_READ, "stdout")
                streams[stdout_stream] = ("stdout", stdout_file)
            if stderr_stream is not None:
                selector.register(stderr_stream, selectors.EVENT_READ, "stderr")
                streams[stderr_stream] = ("stderr", stderr_file)

            stop_deadline: float | None = None
            kill_deadline: float | None = None
            try:
                while streams:
                    now = time.monotonic()
                    if capture_error is not None:
                        if stop_deadline is not None and now >= stop_deadline:
                            _signal_owner_process(process, signal.SIGKILL)
                            if kill_deadline is None:
                                kill_deadline = now + 1.0
                        if kill_deadline is not None and now >= kill_deadline:
                            # A descendant that inherited a pipe can keep EOF
                            # from arriving.  The process group was already
                            # killed; closing our descriptors bounds cleanup.
                            for registered_stream in list(streams):
                                try:
                                    selector.unregister(registered_stream)
                                except (KeyError, ValueError):
                                    pass
                                try:
                                    registered_stream.close()
                                except OSError:
                                    pass
                                streams.pop(registered_stream, None)
                            break

                    timeout = 0.1
                    if stop_deadline is not None:
                        timeout = max(0.0, min(timeout, stop_deadline - now))
                    if kill_deadline is not None:
                        timeout = max(0.0, min(timeout, kill_deadline - now))
                    events = selector.select(timeout)
                    if not events:
                        continue
                    for key, _mask in events:
                        stream: Any = key.fileobj
                        stream_info = streams.get(stream)
                        if stream_info is None:
                            continue
                        stream_name, target = stream_info
                        try:
                            read1 = getattr(stream, "read1", stream.read)
                            chunk = read1(65536)
                        except OSError:
                            chunk = b""
                        if not chunk:
                            try:
                                selector.unregister(stream)
                            except (KeyError, ValueError):
                                pass
                            streams.pop(stream, None)
                            try:
                                stream.close()
                            except OSError:
                                pass
                            continue

                        if stream_name == "stdout":
                            previous = stdout_bytes
                            stdout_bytes = min(max_bytes + 1, previous + len(chunk))
                        else:
                            previous = stderr_bytes
                            stderr_bytes = min(max_bytes + 1, previous + len(chunk))
                        allowed = max(0, max_bytes - previous)
                        if allowed:
                            try:
                                target.write(chunk[:allowed])
                            except OSError:
                                if capture_error is None:
                                    capture_error = "child_capture_write_error"
                                    _signal_owner_process(process, signal.SIGTERM)
                                    stop_deadline = time.monotonic() + 2.0
                        if previous + len(chunk) > max_bytes and capture_error is None:
                            capture_error = "child_output_oversize"
                            _signal_owner_process(process, signal.SIGTERM)
                            stop_deadline = time.monotonic() + 2.0
            finally:
                selector.close()

            if process.poll() is None:
                # Normal completion should have closed both pipes.  Oversize
                # cleanup has a short, explicit terminal wait before KILL.
                wait_timeout = 1.0 if capture_error is not None else 2.0
                try:
                    returncode = int(process.wait(timeout=wait_timeout))
                except subprocess.TimeoutExpired:
                    _signal_owner_process(process, signal.SIGKILL)
                    try:
                        returncode = int(process.wait(timeout=1.0))
                    except subprocess.TimeoutExpired:
                        returncode = 124
                        if capture_error is None:
                            capture_error = "child_process_timeout"
            else:
                returncode = int(process.returncode)

            if capture_error is not None:
                return returncode, None, stdout_bytes, stderr_bytes, capture_error
            stdout_file.seek(0)
            output = stdout_file.read(max_bytes + 1)
    except FileNotFoundError:
        return 127, None, 0, 0, "owner_command_not_found"
    except OSError as exc:
        return 126, None, 0, 0, type(exc).__name__
    try:
        return returncode, output.decode("utf-8"), stdout_bytes, stderr_bytes, None
    except UnicodeDecodeError:
        return returncode, None, stdout_bytes, stderr_bytes, "child_output_not_utf8"


def build_child_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture one owner storage command under the existing resource lease."
    )
    parser.add_argument("--python", dest="python_executable", type=Path, required=True)
    parser.add_argument("--owner-script", type=Path, required=True)
    parser.add_argument(
        "--max-capture-bytes",
        type=int,
        default=MAX_CHILD_CAPTURE_BYTES,
    )
    parser.add_argument("owner_argv", nargs=argparse.REMAINDER)
    return parser


def child_main(argv: Sequence[str] | None = None) -> int:
    """Run the owner once and emit only its bounded, sanitized outcome.

    This command is dispatched by the immutable host launcher as the child of
    ``resource launch``.  Its temporary files therefore share the same lease
    and lifetime, while the resource adapter only sees a small JSON summary.
    """
    args = build_child_parser().parse_args(list(argv) if argv is not None else None)
    owner_args = list(args.owner_argv)
    if owner_args and owner_args[0] == "--":
        owner_args = owner_args[1:]
    max_bytes = args.max_capture_bytes
    if max_bytes < 1 or max_bytes > MAX_CHILD_CAPTURE_BYTES:
        _emit_child_payload(
            _child_failure_payload(
                "child_configuration_invalid",
                diagnostic="child_capture_limit_out_of_bounds",
            )
        )
        return 2
    if not owner_args:
        _emit_child_payload(
            _child_failure_payload(
                "child_configuration_invalid",
                diagnostic="owner_command_missing",
            )
        )
        return 2
    try:
        python_executable = args.python_executable.expanduser().resolve(strict=True)
        owner_script = args.owner_script.expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        _emit_child_payload(
            _child_failure_payload(
                "child_configuration_invalid",
                diagnostic="owner_path_unresolvable",
            )
        )
        return 2
    if not python_executable.is_file() or not owner_script.is_file():
        _emit_child_payload(
            _child_failure_payload(
                "child_configuration_invalid",
                diagnostic="owner_path_not_file",
            )
        )
        return 2
    if _path_inside(owner_script, LIVE_ARCHIVE_ROOT):
        _emit_child_payload(
            _child_failure_payload(
                "child_configuration_invalid",
                diagnostic="owner_script_must_not_be_live_archive",
            )
        )
        return 2

    returncode, output, stdout_bytes, stderr_bytes, capture_error = _capture_owner_json(
        [str(python_executable), str(owner_script), *owner_args],
        max_bytes=max_bytes,
    )
    if capture_error is not None:
        _emit_child_payload(
            _child_failure_payload(
                "child_capture_failed",
                diagnostic=capture_error,
                returncode=returncode,
                stdout_bytes=stdout_bytes,
                stderr_bytes=stderr_bytes,
            )
        )
        return 1
    assert output is not None
    owner_documents = _json_documents(output, max_chars=max_bytes)
    owner_payload: dict[str, Any] | None = None
    for document in owner_documents:
        owner_payload = _find_owner_payload(document)
        if owner_payload is not None:
            break
    if owner_payload is None:
        _emit_child_payload(
            _child_failure_payload(
                "child_json_missing",
                diagnostic="owner_payload_missing",
                returncode=returncode,
                stdout_bytes=stdout_bytes,
                stderr_bytes=stderr_bytes,
            )
        )
        return 1
    sanitized = sanitize_owner_payload(owner_payload)
    sanitized.update(
        {
            "owner_payload_complete": True,
            "child_returncode": returncode,
            "child_stdout_bytes": stdout_bytes,
            "child_stderr_bytes": stderr_bytes,
            "child_capture_limit_bytes": max_bytes,
        }
    )
    if returncode != 0 and sanitized.get("ok") is True:
        sanitized["ok"] = False
        diagnostics = sanitized.setdefault("diagnostic_codes", [])
        if isinstance(diagnostics, list) and "child_returncode_nonzero" not in diagnostics:
            diagnostics.append("child_returncode_nonzero")
    _emit_child_payload(sanitized)
    return 0 if sanitized.get("ok") is True else 1


def _run_command(
    argv: Sequence[str],
    *,
    run_port: RunPort,
    timeout_sec: float,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    try:
        run_kwargs: dict[str, Any] = {
            "text": True,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "timeout": max(0.1, timeout_sec),
            "check": False,
        }
        if env is not None:
            run_kwargs["env"] = dict(env)
        completed = run_port(list(argv), **run_kwargs)
    except FileNotFoundError:
        return {"returncode": 127, "stdout": "", "stderr": "", "error": "command_not_found"}
    except subprocess.TimeoutExpired:
        return {"returncode": 124, "stdout": "", "stderr": "", "error": "command_timeout"}
    except OSError as exc:
        return {"returncode": 126, "stdout": "", "stderr": "", "error": type(exc).__name__}
    return {
        "returncode": int(getattr(completed, "returncode", 1)),
        "stdout": str(getattr(completed, "stdout", "") or ""),
        "stderr": str(getattr(completed, "stderr", "") or ""),
    }


def _parse_systemd_unit_properties(value: str) -> dict[str, str]:
    properties: dict[str, str] = {}
    for line in str(value or "").splitlines():
        key, separator, item = line.partition("=")
        if separator and key in {"LoadState", "ActiveState", "SubState"}:
            properties[key] = item.strip()
    return properties


def _unit_timeout_probe(
    result: Mapping[str, Any],
    *,
    unit: str,
) -> dict[str, Any]:
    """Classify only explicit systemd terminal state as safe cleanup."""
    properties = _parse_systemd_unit_properties(str(result.get("stdout") or ""))
    load_state = properties.get("LoadState", "unknown").lower()
    active_state = properties.get("ActiveState", "unknown").lower()
    active = active_state in {"active", "activating", "reloading", "deactivating"}
    terminal = active_state in {"inactive", "failed", "dead", "exited"}
    # A show response with LoadState=not-found is explicit evidence that the
    # unique transient unit is gone, even when systemctl uses rc=1 for it.
    missing = load_state == "not-found" and active_state in {"", "unknown", "inactive"}
    confirmed = bool(
        not result.get("error")
        and not active
        and (terminal or missing)
    )
    return {
        "unit": unit,
        "confirmed_terminal": confirmed,
        "pending": not confirmed,
        "state": {
            key: properties[key]
            for key in ("LoadState", "ActiveState", "SubState")
            if key in properties
        },
        "confirmation": "unit_terminal" if confirmed else "unit_still_active_or_unknown",
    }


def _recover_timed_out_resource_unit(
    unit: str,
    *,
    run_port: RunPort,
    budget_sec: float,
) -> dict[str, Any]:
    """Stop and probe one timed-out transient unit within a fixed budget.

    The unit name is supplied by this runner and is unique for the attempt.
    A failed stop or an inconclusive probe is retained as pending evidence;
    callers must not retry while the unit's terminal state is unknown.
    """
    normalized_unit = str(unit or "").strip()
    if not normalized_unit:
        return {
            "unit": None,
            "confirmed_terminal": False,
            "pending": True,
            "confirmation": "unit_identity_unavailable",
        }
    budget = max(0.0, float(budget_sec))
    if budget < 0.2:
        return {
            "unit": normalized_unit,
            "confirmed_terminal": False,
            "pending": True,
            "confirmation": "terminal_probe_budget_exhausted",
        }
    started = time.monotonic()
    stop_timeout = min(5.0, max(0.1, budget * 0.4))
    stop_result = _run_command(
        ["systemctl", "--user", "stop", "--no-block", normalized_unit],
        run_port=run_port,
        timeout_sec=stop_timeout,
    )
    elapsed = max(0.0, time.monotonic() - started)
    probe_budget = budget - elapsed
    if probe_budget <= 0.1:
        probe_result: dict[str, Any] = {
            "returncode": 124,
            "stdout": "",
            "stderr": "",
            "error": "terminal_probe_budget_exhausted",
        }
    else:
        probe_result = _run_command(
            [
                "systemctl",
                "--user",
                "show",
                normalized_unit,
                "--property=LoadState",
                "--property=ActiveState",
                "--property=SubState",
                "--no-pager",
            ],
            run_port=run_port,
            timeout_sec=probe_budget,
        )
    probe = _unit_timeout_probe(probe_result, unit=normalized_unit)
    return {
        "unit": normalized_unit,
        "stop": _command_summary(stop_result),
        "probe": {
            **_command_summary(probe_result),
            "state": probe["state"],
        },
        "confirmed_terminal": probe["confirmed_terminal"],
        "pending": probe["pending"],
        "confirmation": probe["confirmation"],
    }


def _command_summary(command_result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "returncode": int(command_result.get("returncode", 1)),
        **({"error": str(command_result["error"])} if command_result.get("error") else {}),
    }


def _trust_gate_summary(result: Mapping[str, Any], config: RunnerConfig) -> tuple[dict[str, Any], bool]:
    documents = _json_documents(str(result.get("stdout") or ""))
    gate = next(
        (
            document
            for document in documents
            if "verdict" in document or "artifact_class" in document
        ),
        documents[0] if documents else {},
    )
    record_value = gate.get("record")
    record: Mapping[str, Any] = record_value if isinstance(record_value, Mapping) else {}
    reasons = _string_list(gate.get("reasons"), limit=12)
    verdict = str(gate.get("verdict") or "unknown")
    source_repo = str(gate.get("source_repo") or record.get("source_repo") or "")
    source_ref = str(gate.get("source_ref") or record.get("source_ref") or "")
    trust_root_mode = str(
        gate.get("trust_root_mode") or record.get("trust_root_mode") or ""
    )
    subject_store_value = record.get("artifact_subject_store")
    subject_store = (
        subject_store_value if isinstance(subject_store_value, Mapping) else {}
    )
    subject_store_path_value = subject_store.get("path")
    subject_store_path = (
        subject_store_path_value.strip()
        if isinstance(subject_store_path_value, str) and subject_store_path_value.strip()
        else None
    )
    matched = (
        gate.get("artifact_class") == config.artifact_class
        and gate.get("subject_digest") == config.subject_digest
        and gate.get("record_id") == config.record_id
        and gate.get("consumer_intent") == CONSUMER_INTENT
        and source_repo == config.source_repo
        and source_ref == config.source_ref
        and trust_root_mode == TRUST_ROOT_MODE
    )
    allowed = (
        int(result.get("returncode", 1)) == 0
        and gate.get("ok") is True
        and verdict in {"allow", "warn"}
        and matched
    )
    return (
        {
            **_command_summary(result),
            "ok": allowed,
            "verdict": verdict,
            "artifact_class": gate.get("artifact_class"),
            "subject_digest": gate.get("subject_digest"),
            "record_id": gate.get("record_id"),
            "consumer_intent": gate.get("consumer_intent"),
            "source_repo": source_repo or None,
            "source_ref": source_ref or None,
            "trust_root_mode": trust_root_mode or None,
            "subject_store": (
                {
                    "required": subject_store.get("required") is True,
                    "ok": subject_store.get("ok") is True,
                    "path": subject_store_path,
                }
                if isinstance(subject_store_value, Mapping)
                else None
            ),
            "subject_store_path": subject_store_path,
            "reasons": reasons,
        },
        allowed,
    )


def _vault_summary(result: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
    mounted = int(result.get("returncode", 1)) == 0
    return ({**_command_summary(result), "ok": mounted, "mounted": mounted}, mounted)


def _classify_resource_result(result: Mapping[str, Any]) -> tuple[str, dict[str, Any] | None, dict[str, Any]]:
    documents = _json_documents(str(result.get("stdout") or ""))
    outer = documents[0] if documents else {}
    blocked = _string_list(outer.get("blocked_reasons"), limit=12)
    denied = _string_list(outer.get("denied_reasons"), limit=12)
    if denied:
        return "resource_admission_denied", None, {
            **_command_summary(result),
            "blocked_reasons": blocked,
            "denied_reasons": denied,
        }
    if blocked:
        return "deferred_resource_admission", None, {
            **_command_summary(result),
            "blocked_reasons": blocked,
        }
    owner = _find_owner_payload(outer)
    if owner is None:
        # A resource admission block is a safe deferral, but a missing child
        # document must remain an error when the launcher claims it ran.
        return "resource_child_json_missing", None, {
            **_command_summary(result),
            "blocked_reasons": blocked,
            "denied_reasons": denied,
        }
    owner_summary = sanitize_owner_payload(owner)
    owner_status = _owner_status(owner)
    resource_ok = int(result.get("returncode", 1)) == 0
    owner_ok = owner.get("ok") is True
    if not resource_ok:
        classification = "resource_child_failed"
    elif owner_status in RETRYABLE_OWNER_STATUSES and owner_ok:
        classification = "deferred_lock_busy"
    elif owner_status == "deferred_session_lease" and owner_ok:
        classification = "deferred_session_lease"
    elif owner_status == "no_eligible_candidates" and owner_ok:
        classification = "no_eligible_candidates"
    elif owner_status == "skipped_live_deferred" and owner_ok:
        classification = "deferred_live_session"
    elif owner_status == "applied" and owner_ok:
        classification = "applied"
    elif owner_status == "planned":
        classification = "owner_dry_run_unexpected"
    else:
        classification = "owner_failed"
    return classification, owner_summary, {**_command_summary(result), "owner": owner_summary}


def _write_state(path: Path, payload: Mapping[str, Any]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    target = path / "latest.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, target)


def _base_summary(config: RunnerConfig) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "generated_at": now_iso(),
        "artifact": {
            "class": config.artifact_class,
            "subject_digest": config.subject_digest,
            "source_repo": config.source_repo,
            "source_ref": config.source_ref,
            "trust_root_mode": TRUST_ROOT_MODE,
            "consumer_intent": CONSUMER_INTENT,
            "record_id": config.record_id or None,
        },
        "mode": config.mode,
        "reclaim_plain": config.reclaim_plain,
        "reservation": {
            "status": "reservation_not_supported_for_owner_path",
            "resource_lease": {
                "class": RESOURCE_CLASS,
                "kind": RESOURCE_KIND,
                "memory_demand_mib": config.memory_demand_mib,
            },
            "hard_bytes_reservation": False,
            "bytes": config.max_plain_bytes,
            "target": str(config.aoa_root),
        },
        "retry_policy": {
            "delays_sec": list(config.retry_delays_sec),
            "deadline_sec": min(config.retry_deadline_sec, MAX_RETRY_DEADLINE_SEC),
            "retry_statuses": sorted(RETRYABLE_OWNER_STATUSES),
            "resource_timeout_reserve_sec": RESOURCE_TIMEOUT_RESERVE_SEC,
            "resource_prelaunch_reserve_sec": RESOURCE_PRELAUNCH_RESERVE_SEC,
            "resource_post_timeout_probe_sec": RESOURCE_POST_TIMEOUT_PROBE_SEC,
        },
        "paths": {
            "config": str(config.config_path),
            "registry_dir": str(config.registry_dir),
            "subject_store_root": str(config.subject_store_root),
            "bundle_dir": str(config.bundle_dir),
            "state_dir": str(config.state_dir),
            "workspace_root": str(config.workspace_root),
            "aoa_root": str(config.aoa_root),
        },
    }


def _subject_store_path_from_trust_summary(
    trust_summary: Mapping[str, Any],
    config: RunnerConfig,
) -> tuple[Path | None, list[str]]:
    store_value = trust_summary.get("subject_store")
    if not isinstance(store_value, Mapping):
        return None, ["subject_store_record_missing"]
    if store_value.get("required") is not True:
        return None, ["subject_store_record_not_required"]
    if store_value.get("ok") is not True:
        return None, ["subject_store_record_not_verified"]
    path_value = trust_summary.get("subject_store_path")
    if not isinstance(path_value, str) or not path_value.strip():
        return None, ["subject_store_record_path_missing"]
    path = Path(path_value).expanduser()
    digest_token = config.subject_digest.removeprefix("sha256:")
    errors: list[str] = []
    if not path.is_absolute():
        errors.append("subject_store_record_path_must_be_absolute")
    if path.name != digest_token:
        errors.append("subject_store_record_path_digest_mismatch")
    if path.parent.name != config.artifact_class:
        errors.append("subject_store_record_path_artifact_class_mismatch")
    return (path if not errors else None), errors


def _trust_gate_environment(config: RunnerConfig) -> dict[str, str]:
    """Make the configured host subject root the first owner-store lookup."""
    environment = os.environ.copy()
    configured_root = str(config.subject_store_root)
    environment["ABYSS_MACHINE_ARTIFACT_SUBJECT_STORE_ROOTS"] = configured_root
    environment["ABYSS_MACHINE_ARTIFACT_SUBJECT_STORE_ROOT"] = configured_root
    return environment


def _validate_runtime_paths(
    config: RunnerConfig,
    *,
    bundle_dir: Path | None = None,
    require_bundle: bool = True,
) -> tuple[Path | None, list[str]]:
    errors: list[str] = []
    admitted_bundle = bundle_dir if bundle_dir is not None else config.bundle_dir
    admitted_owner_script = admitted_bundle / OWNER_SCRIPT_RELATIVE
    if config.registry_dir != DEFAULT_REGISTRY_DIR:
        errors.append("registry_dir_must_use_authoritative_store")
    if _path_inside(admitted_bundle, LIVE_ARCHIVE_ROOT):
        errors.append("bundle_dir_must_not_be_live_archive")
    if _path_inside(admitted_owner_script, LIVE_ARCHIVE_ROOT):
        errors.append("owner_script_must_not_be_live_archive")
    try:
        bundle = admitted_bundle.resolve(strict=True)
    except (OSError, RuntimeError):
        if require_bundle:
            return None, [*errors, "admitted_bundle_missing"]
        return None, errors
    if not bundle.is_dir():
        errors.append("admitted_bundle_not_directory")
        return None, errors
    try:
        script = admitted_owner_script.resolve(strict=True)
    except (OSError, RuntimeError):
        if require_bundle:
            return None, [*errors, "admitted_owner_script_missing"]
        return None, errors
    if not script.is_file():
        errors.append("admitted_owner_script_not_file")
    if not _path_inside(script, bundle):
        errors.append("admitted_owner_script_escapes_bundle")
    if config.aoa_root == LIVE_ARCHIVE_ROOT and _path_inside(admitted_owner_script, LIVE_ARCHIVE_ROOT):
        errors.append("live_owner_script_fallback_rejected")
    return (script if not errors else None), errors


def run_once(
    config: RunnerConfig,
    *,
    run_port: RunPort = subprocess.run,
    sleep_port: SleepPort = time.sleep,
    clock_port: ClockPort = time.monotonic,
    write_state: bool = True,
) -> dict[str, Any]:
    """Run one bounded admitted owner attempt, returning a truthful summary."""
    summary = _base_summary(config)
    summary["ok"] = False
    summary["mutates"] = False
    started = clock_port()
    deadline = started + min(config.retry_deadline_sec, MAX_RETRY_DEADLINE_SEC)

    if config.reclaim_plain and not _reclaim_authorized(config):
        summary.update({
            "status": "blocked_configuration",
            "errors": ["reclaim_requires_verified_pilot_evidence"],
        })
        if write_state:
            _write_state(config.state_dir, summary)
        return summary

    _configured_script, path_errors = _validate_runtime_paths(
        config,
        require_bundle=False,
    )
    if path_errors:
        summary.update({"status": "blocked_bundle", "errors": path_errors})
        if write_state:
            _write_state(config.state_dir, summary)
        return summary

    trust_result = _run_command(
        trust_gate_argv(config),
        run_port=run_port,
        timeout_sec=min(30, max(0.1, deadline - clock_port())),
        env=_trust_gate_environment(config),
    )
    trust_summary, trust_ok = _trust_gate_summary(trust_result, config)
    summary["trust_gate"] = trust_summary
    if not trust_ok:
        summary.update({"status": "blocked_trust_gate", "errors": ["runtime_trust_gate_not_admitted"]})
        if write_state:
            _write_state(config.state_dir, summary)
        return summary

    admitted_store_path, store_errors = _subject_store_path_from_trust_summary(
        trust_summary,
        config,
    )
    if store_errors:
        summary.update({"status": "blocked_subject_store", "errors": store_errors})
        if write_state:
            _write_state(config.state_dir, summary)
        return summary
    assert admitted_store_path is not None
    summary["paths"]["subject_store_record_path"] = str(admitted_store_path)
    summary["paths"]["subject_store_root"] = str(admitted_store_path.parent.parent)
    summary["paths"]["bundle_dir"] = str(admitted_store_path)
    script, path_errors = _validate_runtime_paths(
        config,
        bundle_dir=admitted_store_path,
    )
    if path_errors:
        summary.update({"status": "blocked_bundle", "errors": path_errors})
        if write_state:
            _write_state(config.state_dir, summary)
        return summary
    assert script is not None

    vault_result = _run_command(
        vault_preflight_argv(config),
        run_port=run_port,
        timeout_sec=min(30, max(0.1, deadline - clock_port())),
    )
    vault_summary, vault_ok = _vault_summary(vault_result)
    summary["vault_preflight"] = vault_summary
    if not vault_ok:
        summary.update({"status": "deferred_vault_not_mounted", "deferred": True, "mutates": False})
        if write_state:
            _write_state(config.state_dir, summary)
        return summary

    if clock_port() >= deadline:
        summary.update({
            "status": "deferred_retry_deadline",
            "ok": True,
            "deferred": True,
            "mutates": False,
            "elapsed_sec": round(max(0.0, clock_port() - started), 3),
        })
        if write_state:
            _write_state(config.state_dir, summary)
        return summary

    attempts: list[dict[str, Any]] = []
    classification = "resource_child_json_missing"
    owner_summary: dict[str, Any] | None = None
    resource_summary: dict[str, Any] = {}
    for attempt in range(len(config.retry_delays_sec) + 1):
        remaining = deadline - clock_port()
        # Reserve the post-timeout stop/probe before assigning the resource
        # command its outer wait.  The inner timeout then leaves a separate
        # pre-launch/adapter margin for planning and systemd-run's own +5s.
        if remaining <= RESOURCE_TIMEOUT_RESERVE_SEC + RESOURCE_MIN_TIMEOUT_SEC:
            classification = "deferred_retry_deadline"
            break
        outer_timeout = remaining - float(RESOURCE_POST_TIMEOUT_PROBE_SEC)
        resource_unit = _resource_unit_name(attempt + 1)
        resource_argv = owner_resource_argv(
            config,
            bundle_dir=admitted_store_path,
            outer_timeout_sec=outer_timeout,
            attempt=attempt + 1,
        )
        result = _run_command(
            resource_argv,
            run_port=run_port,
            timeout_sec=outer_timeout,
        )
        if _resource_result_indicates_timeout(result):
            timeout_recovery = _recover_timed_out_resource_unit(
                resource_unit,
                run_port=run_port,
                budget_sec=min(
                    float(RESOURCE_POST_TIMEOUT_PROBE_SEC),
                    max(0.0, deadline - clock_port()),
                ),
            )
            classification = (
                "resource_launch_timeout"
                if timeout_recovery.get("confirmed_terminal") is True
                else "resource_launch_timeout_pending"
            )
            owner_summary = None
            resource_summary = {
                **_command_summary(result),
                "resource_unit": resource_unit,
                "timeout_source": (
                    "outer_wait"
                    if result.get("error") == "command_timeout"
                    else "resource_execution"
                ),
                "timeout_recovery": timeout_recovery,
            }
        else:
            classification, owner_summary, resource_summary = _classify_resource_result(result)
            resource_summary["resource_unit"] = resource_unit
        attempts.append({
            "number": attempt + 1,
            "classification": classification,
            "returncode": resource_summary.get("returncode"),
            "owner_status": owner_summary.get("status") if owner_summary else None,
            "resource_unit": resource_unit,
            "terminal_confirmed": (
                resource_summary.get("timeout_recovery", {}).get("confirmed_terminal")
                if isinstance(resource_summary.get("timeout_recovery"), Mapping)
                else None
            ),
        })
        if classification != "deferred_lock_busy":
            break
        if attempt >= len(config.retry_delays_sec):
            classification = "deferred_lock_retry_exhausted"
            break
        delay = config.retry_delays_sec[attempt]
        remaining = deadline - clock_port()
        if remaining < delay:
            classification = "deferred_retry_deadline"
            break
        sleep_port(delay)

    summary["attempts"] = attempts
    summary["resource_launch"] = resource_summary
    if owner_summary is not None:
        summary["owner"] = owner_summary
    summary["elapsed_sec"] = round(max(0.0, clock_port() - started), 3)
    if classification == "applied":
        summary.update({
            "status": "applied",
            "ok": True,
            "mutates": bool(owner_summary and owner_summary.get("mutates") is True),
        })
    elif classification == "no_eligible_candidates":
        summary.update({
            "status": classification,
            "ok": True,
            "deferred": False,
            "mutates": bool(owner_summary and owner_summary.get("mutates") is True),
        })
    elif classification in SAFE_DEFERRED_STATUSES or classification.startswith("deferred_"):
        summary.update({
            "status": classification,
            "ok": True,
            "deferred": True,
            "mutates": bool(owner_summary and owner_summary.get("mutates") is True),
        })
    elif classification == "resource_launch_timeout_pending":
        # Keep the unit handle visible and fail closed.  The host lease cleanup
        # path may still be pending, so a retry here could overlap live work.
        summary.update({
            "status": classification,
            "ok": False,
            "deferred": True,
            "mutates": False,
            "errors": ["resource_unit_terminal_state_unknown"],
        })
    elif classification == "resource_launch_timeout":
        summary.update({
            "status": classification,
            "ok": False,
            "deferred": False,
            "mutates": False,
            "errors": [classification],
        })
    else:
        summary.update({"status": classification, "errors": [classification], "mutates": False})
    if write_state:
        _write_state(config.state_dir, summary)
    return summary


def _disabled_summary(config_path: Path, status: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "generated_at": now_iso(),
        "ok": True,
        "mutates": False,
        "status": status,
        "config": str(config_path),
        "reservation": {
            "status": "reservation_not_supported_for_owner_path",
            "hard_bytes_reservation": False,
        },
    }


def run(config_path: Path = DEFAULT_CONFIG_PATH, *, run_port: RunPort = subprocess.run) -> tuple[int, dict[str, Any]]:
    config, errors = load_config(config_path)
    if config is None and errors == ["configuration_missing"]:
        return 0, _disabled_summary(config_path, "disabled_configuration_missing")
    if config is None:
        return 1, {**_disabled_summary(config_path, "blocked_configuration"), "ok": False, "errors": errors}
    if errors:
        payload = _base_summary(config)
        payload.update({"ok": False, "mutates": False, "status": "blocked_configuration", "errors": errors})
        return 1, payload
    if not config.enabled:
        return 0, _disabled_summary(config_path, "disabled_configuration")
    payload = run_once(config, run_port=run_port)
    return (0 if payload.get("ok") else 1), payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the admitted AoA raw-block storage owner through host gates."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    exit_code, payload = run(args.config)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return exit_code


def _main_dispatch(argv: Sequence[str] | None = None) -> int:
    selected = list(argv) if argv is not None else list(sys.argv[1:])
    if selected and selected[0] == "child":
        return child_main(selected[1:])
    return main(selected)


if __name__ == "__main__":
    raise SystemExit(_main_dispatch())

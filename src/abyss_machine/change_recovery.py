from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import changes_contracts


@dataclass(frozen=True)
class RecoveryDependencies:
    schema_prefix: str
    version: str
    change_root: Path
    change_active_root: Path
    change_closed_root: Path
    change_history_root: Path
    change_index_path: Path
    change_latest_path: Path
    abyss_machine_root: Path
    abyss_stack_user_source_root: Path
    now_iso: Callable[[], str]
    change_id_valid: Callable[[str], bool]
    change_record_dir: Callable[[str], Path]
    load_json_document: Callable[..., Any]
    read_text: Callable[..., Any]
    sha256_path: Callable[..., str]
    safe_atomic_write_json: Callable[..., Any]
    write_text_if_missing: Callable[..., Any]
    safe_append_jsonl: Callable[..., Any]
    ai_daily_jsonl_path: Callable[..., Path]
    changes_index: Callable[..., Any]
    change_paths: Callable[..., dict[str, Any]]


def _path_is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _filesystem_mtime_iso(value: float) -> str:
    return dt.datetime.fromtimestamp(value, dt.timezone.utc).astimezone().isoformat(timespec="microseconds")


def _read_jsonl_events(
    path: Path,
    read_text: Callable[..., Any],
) -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None]:
    if path.is_symlink() or not path.is_file():
        return None, {
            "path": str(path),
            "error": "existing JSONL path is not a regular file",
        }
    raw = read_text(path)
    if not isinstance(raw, str):
        return None, {
            "path": str(path),
            "error": "existing JSONL path could not be read",
        }
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            return None, {
                "path": str(path),
                "error": "existing JSONL path contains malformed JSON",
                "line": line_number,
                "detail": str(exc),
            }
        if not isinstance(event, dict):
            return None, {
                "path": str(path),
                "error": "existing JSONL path contains a non-object event",
                "line": line_number,
            }
        events.append(event)
    return events, None


def _ensure_record_json(
    path: Path,
    expected: dict[str, Any],
    *,
    load_json_document: Callable[..., Any],
    safe_atomic_write_json: Callable[..., Any],
) -> tuple[dict[str, Any] | None, bool]:
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file():
            return {
                "path": str(path),
                "error": "existing recovery record is not a regular file",
            }, False
        existing, load_error = load_json_document(path)
        if existing != expected:
            return {
                "path": str(path),
                "error": "existing recovery record differs; refusing overwrite",
                "detail": load_error,
            }, False
        return None, False
    error = safe_atomic_write_json(path, expected, 0o664)
    return error, error is None


def _ensure_text_file(
    path: Path,
    text: str,
    *,
    write_text_if_missing: Callable[..., Any],
) -> tuple[dict[str, Any] | None, bool]:
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file():
            return {
                "path": str(path),
                "error": "existing recovery text path is not a regular file",
            }, False
        return None, False
    error = write_text_if_missing(path, text)
    return error, error is None


def _ensure_jsonl_event(
    path: Path,
    event: dict[str, Any],
    *,
    read_text: Callable[..., Any],
    safe_append_jsonl: Callable[..., Any],
    matches: Callable[[dict[str, Any]], bool],
    allow_existing_other: bool,
) -> tuple[dict[str, Any] | None, bool]:
    if path.exists() or path.is_symlink():
        events, read_error = _read_jsonl_events(path, read_text)
        if read_error:
            return read_error, False
        assert events is not None
        if any(matches(item) for item in events):
            return None, False
        if events and not allow_existing_other:
            return {
                "path": str(path),
                "error": "existing recovery actions do not match the resumable event",
            }, False
    error = safe_append_jsonl(path, event, 0o664)
    return error, error is None


def _recovery_records_compatible(
    existing: dict[str, Any],
    expected: dict[str, Any],
) -> bool:
    for key in (
        "schema",
        "version",
        "id",
        "title",
        "intent",
        "surfaces",
        "status",
        "path",
        "files",
        "project_readonly_roots",
    ):
        if existing.get(key) != expected.get(key):
            return False
    existing_reconstruction = existing.get("reconstruction")
    expected_reconstruction = expected.get("reconstruction")
    if not isinstance(existing_reconstruction, dict) or not isinstance(
        expected_reconstruction,
        dict,
    ):
        return False
    for key in (
        "method",
        "source_state",
        "source_path",
        "corrective_change_id",
        "title",
        "intent",
        "surfaces",
        "evidence",
        "gaps",
    ):
        if existing_reconstruction.get(key) != expected_reconstruction.get(key):
            return False
    return True


def _target_recovery_event_matches(
    item: dict[str, Any],
    expected: dict[str, Any],
) -> bool:
    reconstruction = item.get("reconstruction")
    expected_reconstruction = expected.get("reconstruction")
    return (
        item.get("change_id") == expected.get("change_id")
        and item.get("event") == "reconstructed"
        and item.get("title") == expected.get("title")
        and item.get("status") == expected.get("status")
        and item.get("surfaces") == expected.get("surfaces")
        and isinstance(reconstruction, dict)
        and isinstance(expected_reconstruction, dict)
        and reconstruction.get("corrective_change_id")
        == expected_reconstruction.get("corrective_change_id")
        and reconstruction.get("source_state")
        == expected_reconstruction.get("source_state")
        and reconstruction.get("gaps") == expected_reconstruction.get("gaps")
        and reconstruction.get("evidence_paths")
        == expected_reconstruction.get("evidence_paths")
    )


def _corrective_recovery_event_matches(
    item: dict[str, Any],
    expected: dict[str, Any],
) -> bool:
    recovery_target = item.get("recovery_target")
    expected_target = expected.get("recovery_target")
    return (
        item.get("change_id") == expected.get("change_id")
        and item.get("event") == "recovery_applied"
        and isinstance(recovery_target, dict)
        and isinstance(expected_target, dict)
        and recovery_target.get("id") == expected_target.get("id")
        and recovery_target.get("state") == expected_target.get("state")
        and recovery_target.get("source_path") == expected_target.get("source_path")
        and recovery_target.get("provenance_gaps")
        == expected_target.get("provenance_gaps")
    )


def _change_recovery_error(
    *,
    deps: "RecoveryDependencies",
    target_id: str,
    target_state: str,
    source_path: Path,
    corrective_change_id: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    errors = [{"message": message, **(details or {})}]
    SCHEMA_PREFIX = deps.schema_prefix
    VERSION = deps.version
    now_iso = deps.now_iso
    change_paths = deps.change_paths
    return changes_contracts.recovery_document(
        schema_prefix=SCHEMA_PREFIX,
        version=VERSION,
        generated_at=now_iso(),
        ok=False,
        changed=False,
        target_id=target_id,
        target_state=target_state,
        source_path=source_path,
        corrective_change_id=corrective_change_id,
        record=None,
        event=None,
        provenance={"method": "evidence_bound_missing_canonical_lifecycle"},
        before={},
        after={},
        paths=change_paths(include_index=False),
        errors=errors,
    )


def recover(
    *,
    deps: "RecoveryDependencies",
    change_id: str,
    state: str,
    source_dir: str,
    corrective_change_id: str,
    title: str,
    surfaces: list[str],
    evidence_paths: list[str],
    provenance_gaps: list[str],
    note: str | None = None,
    write_latest: bool = True,
) -> dict[str, Any]:
    """Reconstruct only missing lifecycle files from explicit host evidence.

    This command never moves, closes, deletes, or overwrites a record.  The
    caller must name the exact active/closed directory, an existing active
    corrective change, every evidence file, and every known provenance gap.
    """
    CHANGE_ROOT = deps.change_root
    CHANGE_ACTIVE_ROOT = deps.change_active_root
    CHANGE_CLOSED_ROOT = deps.change_closed_root
    CHANGE_HISTORY_ROOT = deps.change_history_root
    CHANGE_INDEX_PATH = deps.change_index_path
    CHANGE_LATEST_PATH = deps.change_latest_path
    ABYSS_MACHINE_ROOT = deps.abyss_machine_root
    ABYSS_STACK_USER_SOURCE_ROOT = deps.abyss_stack_user_source_root
    SCHEMA_PREFIX = deps.schema_prefix
    VERSION = deps.version
    now_iso = deps.now_iso
    change_id_valid = deps.change_id_valid
    change_record_dir = deps.change_record_dir
    load_json_document = deps.load_json_document
    read_text = deps.read_text
    sha256_path = deps.sha256_path
    safe_atomic_write_json = deps.safe_atomic_write_json
    write_text_if_missing = deps.write_text_if_missing
    safe_append_jsonl = deps.safe_append_jsonl
    ai_daily_jsonl_path = deps.ai_daily_jsonl_path
    changes_index = deps.changes_index
    change_paths = deps.change_paths
    state = str(state).strip().lower()
    source_path = Path(source_dir).expanduser()
    if state not in {"active", "closed"}:
        return _change_recovery_error(
            deps=deps,
            target_id=change_id,
            target_state=state,
            source_path=source_path,
            corrective_change_id=corrective_change_id,
            message="state must be active or closed",
        )
    try:
        if not change_id_valid(change_id) or not change_id_valid(corrective_change_id):
            raise ValueError("invalid change id")
    except ValueError as exc:
        return _change_recovery_error(
            deps=deps,
            target_id=change_id,
            target_state=state,
            source_path=source_path,
            corrective_change_id=corrective_change_id,
            message=str(exc),
        )
    if change_id == corrective_change_id:
        return _change_recovery_error(
            deps=deps,
            target_id=change_id,
            target_state=state,
            source_path=source_path,
            corrective_change_id=corrective_change_id,
            message="target and corrective change ids must differ",
        )

    expected_root = CHANGE_ACTIVE_ROOT if state == "active" else CHANGE_CLOSED_ROOT
    expected_path = (expected_root / change_id).absolute()
    try:
        lexical_source = source_path.absolute()
        resolved_source = source_path.resolve()
        resolved_expected_root = expected_root.resolve()
    except OSError as exc:
        return _change_recovery_error(
            deps=deps,
            target_id=change_id,
            target_state=state,
            source_path=source_path,
            corrective_change_id=corrective_change_id,
            message="unable to resolve source directory",
            details={"error": str(exc)},
        )
    if lexical_source != expected_path:
        return _change_recovery_error(
            deps=deps,
            target_id=change_id,
            target_state=state,
            source_path=source_path,
            corrective_change_id=corrective_change_id,
            message="source directory is not the exact expected active/closed target",
            details={"expected": str(expected_path), "actual": str(lexical_source)},
        )
    if lexical_source.is_symlink():
        return _change_recovery_error(
            deps=deps,
            target_id=change_id,
            target_state=state,
            source_path=source_path,
            corrective_change_id=corrective_change_id,
            message="source directory must not be a symlink",
            details={"path": str(lexical_source)},
        )
    if not _path_is_under(resolved_source, resolved_expected_root):
        return _change_recovery_error(
            deps=deps,
            target_id=change_id,
            target_state=state,
            source_path=source_path,
            corrective_change_id=corrective_change_id,
            message="resolved source directory escapes the selected ledger root",
            details={"root": str(resolved_expected_root), "actual": str(resolved_source)},
        )
    if not resolved_source.is_dir():
        return _change_recovery_error(
            deps=deps,
            target_id=change_id,
            target_state=state,
            source_path=resolved_source,
            corrective_change_id=corrective_change_id,
            message="source directory is missing",
        )

    corrective_root = change_record_dir(corrective_change_id)
    corrective_record, corrective_error = load_json_document(corrective_root / "change.json")
    if not corrective_record or corrective_record.get("status") != "active":
        return _change_recovery_error(
            deps=deps,
            target_id=change_id,
            target_state=state,
            source_path=resolved_source,
            corrective_change_id=corrective_change_id,
            message="an active canonical corrective change record is required",
            details={"path": str(corrective_root / "change.json"), "error": corrective_error},
        )

    canonical_paths = {
        "change": resolved_source / "change.json",
        "actions": resolved_source / "actions.jsonl",
    }

    gaps = sorted({str(item).strip() for item in provenance_gaps if str(item).strip()})
    if not gaps:
        return _change_recovery_error(
            deps=deps,
            target_id=change_id,
            target_state=state,
            source_path=resolved_source,
            corrective_change_id=corrective_change_id,
            message="at least one explicit provenance gap is required",
        )
    clean_surfaces = sorted({str(item).strip() for item in surfaces if str(item).strip()})
    if not clean_surfaces:
        return _change_recovery_error(
            deps=deps,
            target_id=change_id,
            target_state=state,
            source_path=resolved_source,
            corrective_change_id=corrective_change_id,
            message="at least one reconstructed surface is required",
        )
    clean_title = str(title).strip()
    if not clean_title:
        return _change_recovery_error(
            deps=deps,
            target_id=change_id,
            target_state=state,
            source_path=resolved_source,
            corrective_change_id=corrective_change_id,
            message="a derived title is required and must be explicit",
        )

    intent_path = resolved_source / "intent.md"
    intent_raw = read_text(intent_path)
    if not intent_raw:
        return _change_recovery_error(
            deps=deps,
            target_id=change_id,
            target_state=state,
            source_path=resolved_source,
            corrective_change_id=corrective_change_id,
            message="surviving intent.md is required to reconstruct the intent field",
            details={"path": str(intent_path)},
        )
    intent_lines = intent_raw.splitlines()
    if intent_lines and intent_lines[0].strip().lower() == "# intent":
        intent_lines = intent_lines[1:]
    intent = "\n".join(intent_lines).strip()
    if not intent:
        return _change_recovery_error(
            deps=deps,
            target_id=change_id,
            target_state=state,
            source_path=resolved_source,
            corrective_change_id=corrective_change_id,
            message="intent.md has no recoverable body",
            details={"path": str(intent_path)},
        )

    allowed_evidence_roots = [
        CHANGE_ROOT.resolve(),
        ABYSS_MACHINE_ROOT.resolve(),
        Path("/abyss").resolve(),
    ]
    evidence = []
    seen_evidence: set[Path] = set()
    for raw_path in evidence_paths:
        candidate = Path(str(raw_path)).expanduser()
        if not candidate.is_absolute():
            candidate = resolved_source / candidate
        try:
            resolved_evidence = candidate.resolve()
        except OSError as exc:
            return _change_recovery_error(
            deps=deps,
                target_id=change_id,
                target_state=state,
                source_path=resolved_source,
                corrective_change_id=corrective_change_id,
                message="unable to resolve evidence path",
                details={"path": str(candidate), "error": str(exc)},
            )
        if not any(_path_is_under(resolved_evidence, root) for root in allowed_evidence_roots):
            return _change_recovery_error(
            deps=deps,
                target_id=change_id,
                target_state=state,
                source_path=resolved_source,
                corrective_change_id=corrective_change_id,
                message="evidence path is outside the host-owned evidence roots",
                details={"path": str(resolved_evidence)},
            )
        if not resolved_evidence.is_file():
            return _change_recovery_error(
            deps=deps,
                target_id=change_id,
                target_state=state,
                source_path=resolved_source,
                corrective_change_id=corrective_change_id,
                message="evidence path is not a regular file",
                details={"path": str(resolved_evidence)},
            )
        if resolved_evidence in seen_evidence:
            continue
        seen_evidence.add(resolved_evidence)
        try:
            stat = resolved_evidence.stat()
            evidence.append(
                {
                    "path": str(resolved_evidence),
                    "size_bytes": stat.st_size,
                    "mode": oct(stat.st_mode & 0o7777),
                    "mtime": _filesystem_mtime_iso(stat.st_mtime),
                    "sha256": sha256_path(resolved_evidence),
                }
            )
        except OSError as exc:
            return _change_recovery_error(
            deps=deps,
                target_id=change_id,
                target_state=state,
                source_path=resolved_source,
                corrective_change_id=corrective_change_id,
                message="unable to collect evidence metadata",
                details={"path": str(resolved_evidence), "error": str(exc)},
            )
    if intent_path.resolve() not in seen_evidence:
        return _change_recovery_error(
            deps=deps,
            target_id=change_id,
            target_state=state,
            source_path=resolved_source,
            corrective_change_id=corrective_change_id,
            message="intent.md must be named explicitly in the evidence set",
            details={"path": str(intent_path)},
        )

    metadata_files = []
    for candidate in sorted(resolved_source.iterdir(), key=lambda path: path.name):
        if not candidate.is_file():
            continue
        try:
            stat = candidate.stat()
        except OSError as exc:
            return _change_recovery_error(
            deps=deps,
                target_id=change_id,
                target_state=state,
                source_path=resolved_source,
                corrective_change_id=corrective_change_id,
                message="unable to collect source filesystem metadata",
                details={"path": str(candidate), "error": str(exc)},
            )
        metadata_files.append(
            {
                "path": str(candidate),
                "size_bytes": stat.st_size,
                "mode": oct(stat.st_mode & 0o7777),
                "mtime": _filesystem_mtime_iso(stat.st_mtime),
            }
        )
    if not metadata_files:
        return _change_recovery_error(
            deps=deps,
            target_id=change_id,
            target_state=state,
            source_path=resolved_source,
            corrective_change_id=corrective_change_id,
            message="source directory has no surviving regular-file evidence",
        )
    created_basis = min(metadata_files, key=lambda item: str(item["mtime"]))
    updated_basis = max(metadata_files, key=lambda item: str(item["mtime"]))
    created_at = str(created_basis["mtime"])
    updated_at = str(updated_basis["mtime"])
    provenance = {
        "method": "evidence_bound_missing_canonical_lifecycle",
        "source_state": state,
        "source_path": str(resolved_source),
        "corrective_change_id": corrective_change_id,
        "title": {
            "value": clean_title,
            "derived": True,
            "basis": "operator-supplied summary grounded in named producer/actor evidence",
        },
        "intent": {
            "derived": False,
            "basis": str(intent_path),
        },
        "surfaces": {
            "values": clean_surfaces,
            "derived": True,
            "basis": "named producer/actor evidence and surviving intent/rollback documents",
        },
        "timestamps": {
            "created_at": created_at,
            "updated_at": updated_at,
            "basis": "filesystem mtime bounds of surviving files; not asserted as original lifecycle timestamps",
            "created_from": created_basis,
            "updated_from": updated_basis,
        },
        "evidence": evidence,
        "filesystem_metadata": metadata_files,
        "gaps": gaps,
    }
    record = changes_contracts.record_document(
        schema_prefix=SCHEMA_PREFIX,
        version=VERSION,
        change_id=change_id,
        title=f"Reconstructed lifecycle: {clean_title}",
        intent=intent,
        surfaces=clean_surfaces,
        status_value=state,
        created_at=created_at,
        updated_at=updated_at,
        root=resolved_source,
        project_readonly_roots=["/srv/AbyssOS", "/srv/abyss-stack", str(ABYSS_STACK_USER_SOURCE_ROOT)],
    )
    record["reconstruction"] = dict(provenance)
    event = changes_contracts.event_document(
        schema_prefix=SCHEMA_PREFIX,
        version=VERSION,
        generated_at=now_iso(),
        change_id=change_id,
        event="reconstructed",
        title=record["title"],
        status=state,
        surfaces=clean_surfaces,
        note=note or f"Evidence-bound canonical lifecycle reconstruction under corrective change {corrective_change_id}.",
    )
    event["reconstruction"] = {
        "corrective_change_id": corrective_change_id,
        "source_state": state,
        "gaps": gaps,
        "evidence_paths": [item["path"] for item in evidence],
    }
    existing_record: dict[str, Any] | None = None
    if canonical_paths["change"].exists() or canonical_paths["change"].is_symlink():
        if canonical_paths["change"].is_symlink() or not canonical_paths["change"].is_file():
            return _change_recovery_error(
                deps=deps,
                target_id=change_id,
                target_state=state,
                source_path=resolved_source,
                corrective_change_id=corrective_change_id,
                message="existing recovery record is not a regular file",
                details={"path": str(canonical_paths["change"])},
            )
        existing_record, existing_record_error = load_json_document(canonical_paths["change"])
        if not isinstance(existing_record, dict) or not _recovery_records_compatible(
            existing_record,
            record,
        ):
            return _change_recovery_error(
                deps=deps,
                target_id=change_id,
                target_state=state,
                source_path=resolved_source,
                corrective_change_id=corrective_change_id,
                message="existing recovery record differs; refusing overwrite",
                details={
                    "path": str(canonical_paths["change"]),
                    "error": existing_record_error,
                },
            )
        record = existing_record

    existing_target_events: list[dict[str, Any]] | None = None
    if canonical_paths["actions"].exists() or canonical_paths["actions"].is_symlink():
        existing_target_events, actions_error = _read_jsonl_events(
            canonical_paths["actions"],
            read_text,
        )
        if actions_error:
            return _change_recovery_error(
                deps=deps,
                target_id=change_id,
                target_state=state,
                source_path=resolved_source,
                corrective_change_id=corrective_change_id,
                message="existing recovery actions cannot be resumed safely",
                details=actions_error,
            )
        assert existing_target_events is not None
        target_event_exists = any(
            _target_recovery_event_matches(item, event)
            for item in existing_target_events
        )
        if existing_target_events and not target_event_exists:
            return _change_recovery_error(
                deps=deps,
                target_id=change_id,
                target_state=state,
                source_path=resolved_source,
                corrective_change_id=corrective_change_id,
                message="existing recovery actions do not match the resumable event",
                details={"path": str(canonical_paths["actions"])},
            )
        if not existing_target_events and existing_record is None:
            return _change_recovery_error(
                deps=deps,
                target_id=change_id,
                target_state=state,
                source_path=resolved_source,
                corrective_change_id=corrective_change_id,
                message="empty recovery actions have no resumable canonical record",
                details={"path": str(canonical_paths["actions"])},
            )

    recovery_mode = "resume" if existing_record is not None or existing_target_events else "new"
    provenance["recovery_mode"] = recovery_mode
    event["reconstruction"]["recovery_mode"] = recovery_mode
    before = {
        "change_json": {
            "path": str(canonical_paths["change"]),
            "exists": canonical_paths["change"].is_file() and not canonical_paths["change"].is_symlink(),
            "sha256": sha256_path(canonical_paths["change"])
            if canonical_paths["change"].is_file() and not canonical_paths["change"].is_symlink()
            else None,
        },
        "actions_jsonl": {
            "path": str(canonical_paths["actions"]),
            "exists": canonical_paths["actions"].is_file() and not canonical_paths["actions"].is_symlink(),
            "sha256": sha256_path(canonical_paths["actions"])
            if canonical_paths["actions"].is_file() and not canonical_paths["actions"].is_symlink()
            else None,
        },
    }
    errors: list[dict[str, Any]] = []
    changed = False
    error, wrote = _ensure_record_json(
        canonical_paths["change"],
        record,
        load_json_document=load_json_document,
        safe_atomic_write_json=safe_atomic_write_json,
    )
    if error:
        errors.append(error)
    changed = changed or wrote
    validation_placeholder = (
        "# Validation\n\n"
        "No original validation artifact survived. This explicit placeholder records the gap; "
        "it is not a claim that the original lifecycle was validated.\n\n"
        + "\n".join(f"- provenance gap: {item}" for item in gaps)
        + "\n"
    )
    closeout_placeholder = (
        "# Closeout\n\n"
        "No original closeout artifact survived. This file is a reconstruction placeholder; "
        "the recovered state is taken only from the named evidence and current directory state.\n\n"
        + "\n".join(f"- provenance gap: {item}" for item in gaps)
        + "\n"
    )
    for path, text in [
        (resolved_source / "validation.md", validation_placeholder),
        (resolved_source / "closeout.md", closeout_placeholder),
    ]:
        error, wrote = _ensure_text_file(
            path,
            text,
            write_text_if_missing=write_text_if_missing,
        )
        if error:
            errors.append(error)
        changed = changed or wrote
    error, wrote = _ensure_jsonl_event(
        canonical_paths["actions"],
        event,
        read_text=read_text,
        safe_append_jsonl=safe_append_jsonl,
        matches=lambda item: _target_recovery_event_matches(item, event),
        allow_existing_other=False,
    )
    if error:
        errors.append(error)
    changed = changed or wrote

    corrective_event = changes_contracts.event_document(
        schema_prefix=SCHEMA_PREFIX,
        version=VERSION,
        generated_at=now_iso(),
        change_id=corrective_change_id,
        event="recovery_applied",
        title=corrective_record.get("title"),
        status="active",
        surfaces=corrective_record.get("surfaces", []),
        note=f"Reconstructed missing canonical lifecycle for {change_id} from explicit evidence; no move, close, delete, or overwrite performed.",
    )
    corrective_event["recovery_target"] = {
        "id": change_id,
        "state": state,
        "source_path": str(resolved_source),
        "provenance_gaps": gaps,
        "record_sha256": sha256_path(canonical_paths["change"]) if canonical_paths["change"].exists() else None,
        "actions_sha256": sha256_path(canonical_paths["actions"]) if canonical_paths["actions"].exists() else None,
    }
    for path, payload, matcher in [
        (
            corrective_root / "actions.jsonl",
            corrective_event,
            lambda item: _corrective_recovery_event_matches(item, corrective_event),
        ),
        (
            ai_daily_jsonl_path(CHANGE_HISTORY_ROOT),
            event,
            lambda item: _target_recovery_event_matches(item, event),
        ),
        (
            ai_daily_jsonl_path(CHANGE_HISTORY_ROOT),
            corrective_event,
            lambda item: _corrective_recovery_event_matches(item, corrective_event),
        ),
    ]:
        error, wrote = _ensure_jsonl_event(
            path,
            payload,
            read_text=read_text,
            safe_append_jsonl=safe_append_jsonl,
            matches=matcher,
            allow_existing_other=True,
        )
        if error:
            errors.append(error)
        changed = changed or wrote

    after = {
        "change_json": {
            "path": str(canonical_paths["change"]),
            "exists": canonical_paths["change"].exists(),
            "sha256": sha256_path(canonical_paths["change"]) if canonical_paths["change"].exists() else None,
        },
        "actions_jsonl": {
            "path": str(canonical_paths["actions"]),
            "exists": canonical_paths["actions"].exists(),
            "sha256": sha256_path(canonical_paths["actions"]) if canonical_paths["actions"].exists() else None,
        },
    }
    result = changes_contracts.recovery_document(
        schema_prefix=SCHEMA_PREFIX,
        version=VERSION,
        generated_at=now_iso(),
        ok=not errors,
        changed=changed,
        target_id=change_id,
        target_state=state,
        source_path=resolved_source,
        corrective_change_id=corrective_change_id,
        record=record,
        event=event,
        provenance=provenance,
        before=before,
        after=after,
        paths=change_paths(include_index=False),
        errors=errors,
    )
    if write_latest:
        latest_error = safe_atomic_write_json(CHANGE_LATEST_PATH, result, 0o664)
        if latest_error:
            errors.append(latest_error)
        index = changes_index(write_latest=True)
        if not index.get("ok"):
            errors.append({"path": str(CHANGE_INDEX_PATH), "error": "changes index refresh failed"})
        result["index_summary"] = index.get("summary")
        if errors:
            result["ok"] = False
            result["errors"] = errors
        return result
    return result

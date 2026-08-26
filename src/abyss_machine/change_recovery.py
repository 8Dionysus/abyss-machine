from __future__ import annotations

import datetime as dt
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
    expected_path = (expected_root / change_id).resolve()
    try:
        resolved_source = source_path.resolve()
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
    if resolved_source != expected_path:
        return _change_recovery_error(
            deps=deps,
            target_id=change_id,
            target_state=state,
            source_path=source_path,
            corrective_change_id=corrective_change_id,
            message="source directory is not the exact expected active/closed target",
            details={"expected": str(expected_path), "actual": str(resolved_source)},
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
    existing_canonical = [str(path) for path in canonical_paths.values() if path.exists()]
    if existing_canonical:
        return _change_recovery_error(
            deps=deps,
            target_id=change_id,
            target_state=state,
            source_path=resolved_source,
            corrective_change_id=corrective_change_id,
            message="canonical recovery target is partially or fully present; refusing overwrite",
            details={"existing": existing_canonical},
        )

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
    record["reconstruction"] = provenance
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
    before = {
        "change_json": {"path": str(canonical_paths["change"]), "exists": False, "sha256": None},
        "actions_jsonl": {"path": str(canonical_paths["actions"]), "exists": False, "sha256": None},
    }
    errors: list[dict[str, Any]] = []
    changed = False
    for path, payload in [(canonical_paths["change"], record)]:
        error = safe_atomic_write_json(path, payload, 0o664)
        if error:
            errors.append(error)
        else:
            changed = True
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
        error = write_text_if_missing(path, text)
        if error:
            errors.append(error)
        elif path.exists():
            changed = True
    error = safe_append_jsonl(canonical_paths["actions"], event, 0o664)
    if error:
        errors.append(error)
    else:
        changed = True

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
    for path, payload in [
        (corrective_root / "actions.jsonl", corrective_event),
        (ai_daily_jsonl_path(CHANGE_HISTORY_ROOT), event),
        (ai_daily_jsonl_path(CHANGE_HISTORY_ROOT), corrective_event),
    ]:
        error = safe_append_jsonl(path, payload, 0o664)
        if error:
            errors.append(error)
        else:
            changed = True

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
    if write_latest:
        index = changes_index(write_latest=True)
        if not index.get("ok"):
            errors.append({"path": str(CHANGE_INDEX_PATH), "error": "changes index refresh failed"})
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
        latest_error = safe_atomic_write_json(CHANGE_LATEST_PATH, result, 0o664)
        if latest_error:
            result["ok"] = False
            result["errors"] = list(result.get("errors", [])) + [latest_error]
        return result
    return changes_contracts.recovery_document(
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

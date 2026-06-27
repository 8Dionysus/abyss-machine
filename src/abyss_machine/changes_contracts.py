from __future__ import annotations

import re
from pathlib import Path
from typing import Any


CHANGE_DECISION_REVIEW_CHOICES = {"added", "existing", "no-record-needed", "backfill-required"}
DURABLE_SURFACE_CLASSES = {
    "host_config",
    "host_state",
    "host_large_root",
    "host_binary",
    "host_public_seed",
    "host_system_systemd",
    "host_user_systemd",
}
ROLLBACK_SENSITIVE_CLASSES = {
    "host_config",
    "host_binary",
    "host_public_seed",
    "host_system_systemd",
    "host_user_systemd",
}


def _schema(schema_prefix: str, suffix: str) -> str:
    return f"{schema_prefix}_{suffix}"


def validation_check(level: str, key: str, message: str, data: Any = None) -> dict[str, Any]:
    item: dict[str, Any] = {"level": level, "key": key, "message": message}
    if data is not None:
        item["data"] = data
    return item


def validation_summary(checks: list[dict[str, Any]]) -> dict[str, Any]:
    fails = sum(1 for item in checks if item.get("level") == "fail")
    warnings = sum(1 for item in checks if item.get("level") == "warn")
    return {
        "status": "fail" if fails else "warn" if warnings else "ok",
        "fails": fails,
        "warnings": warnings,
        "checks": len(checks),
    }


def paths_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    change_root: Path,
    agents_path: Path,
    index_path: Path,
    latest_path: Path,
    active_root: Path,
    closed_root: Path,
    history_root: Path,
    history_today: Path,
    include_index: bool = True,
    index_exists: bool | None = None,
    index_load_error: str | None = None,
    indexed_summary: Any = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "schema": _schema(schema_prefix, "changes_paths_v1"),
        "version": version,
        "generated_at": generated_at,
        "root": str(change_root),
        "agent_entrypoint": str(agents_path),
        "index": str(index_path),
        "latest": str(latest_path),
        "active": str(active_root),
        "closed": str(closed_root),
        "history": str(history_root),
        "history_today": str(history_today),
        "history_daily_glob": str(history_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        "record_layout": {
            "change_json": "active/CHANGE_ID/change.json",
            "intent_md": "active/CHANGE_ID/intent.md",
            "actions_jsonl": "active/CHANGE_ID/actions.jsonl",
            "validation_md": "active/CHANGE_ID/validation.md",
            "rollback_md": "active/CHANGE_ID/rollback.md",
            "closeout_md": "active/CHANGE_ID/closeout.md",
        },
        "commands": {
            "status": "abyss-machine changes status --json",
            "paths": "abyss-machine changes paths --json",
            "record": "abyss-machine changes record --id ID --title TITLE --intent TEXT --surface SURFACE --json",
            "close": "abyss-machine changes close --id ID --decision-review existing --decision-ref DECISION --note TEXT --json",
            "latest": "abyss-machine changes latest --json",
            "index": "abyss-machine changes index --json",
            "preflight": "abyss-machine changes preflight --intent TEXT --surface SURFACE --json",
        },
    }
    if include_index:
        data["index_exists"] = bool(index_exists)
        data["index_load_error"] = index_load_error
        if indexed_summary is not None:
            data["indexed_summary"] = indexed_summary
    return data


def change_id_valid(change_id: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{1,120}", change_id or ""))


def normalize_decision_ref(decision_ref: str | None, *, decisions_root: Path) -> str | None:
    if not decision_ref:
        return None
    value = decision_ref.strip()
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = decisions_root / value
    return str(path)


def decision_review_payload(
    decision_review: str | None,
    decision_ref: str | None = None,
    decision_reason: str | None = None,
    *,
    decisions_root: Path,
    reviewed_at: str,
    decision_ref_exists: bool | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    review = (decision_review or "").strip()
    ref = normalize_decision_ref(decision_ref, decisions_root=decisions_root)
    reason = (decision_reason or "").strip() or None
    issues: list[str] = []
    if not review:
        issues.append("decision review is required; pass --decision-review added|existing|no-record-needed|backfill-required")
        return None, issues
    if review not in CHANGE_DECISION_REVIEW_CHOICES:
        issues.append(f"decision review must be one of: {', '.join(sorted(CHANGE_DECISION_REVIEW_CHOICES))}")
    if review in {"added", "existing"}:
        if not ref:
            issues.append("--decision-ref is required when --decision-review added or existing")
        elif decision_ref_exists is False:
            issues.append(f"decision ref does not exist: {ref}")
    if review in {"no-record-needed", "backfill-required"} and not reason:
        issues.append("--decision-reason is required for no-record-needed or backfill-required")
    payload = {
        "status": review or None,
        "decision_ref": ref,
        "reason": reason,
        "reviewed_at": reviewed_at,
        "contract": "host change close requires explicit decision review",
    }
    return payload, issues


def decision_review_closeout_text(payload: dict[str, Any]) -> str:
    lines = [
        "",
        "## Decision Review",
        "",
        f"- status: `{payload.get('status')}`",
    ]
    if payload.get("decision_ref"):
        lines.append(f"- decision_ref: `{payload.get('decision_ref')}`")
    if payload.get("reason"):
        lines.append(f"- reason: {payload.get('reason')}")
    lines.append(f"- reviewed_at: `{payload.get('reviewed_at')}`")
    lines.append("")
    return "\n".join(lines)


def record_summary(path: Path, data: dict[str, Any] | None, error: str | None) -> dict[str, Any]:
    if not data:
        return {"id": path.name, "path": str(path), "ok": False, "error": error or "missing change.json"}
    return {
        "id": data.get("id", path.name),
        "path": str(path),
        "ok": True,
        "title": data.get("title"),
        "status": data.get("status"),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
        "surfaces": data.get("surfaces", []),
        "decision_review": data.get("decision_review"),
    }


def index_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    paths: dict[str, Any],
    active_items: list[dict[str, Any]],
    closed_items: list[dict[str, Any]],
    latest: dict[str, Any] | None,
    latest_error: str | None,
    history_file_count: int,
    recent_history_lines: int,
    latest_exists: bool,
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "changes_index_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "paths": paths,
        "summary": {
            "active_records": len(active_items),
            "closed_records": len(closed_items),
            "history_files": history_file_count,
            "recent_history_lines": recent_history_lines,
            "latest_exists": latest_exists,
        },
        "active": active_items,
        "closed": closed_items[-20:],
        "latest": latest,
        "latest_load_error": latest_error,
        "rules": [
            "Record host-layer changes here before future agents rely on them.",
            "This ledger describes machine-side changes only; project repos keep their own history.",
            "No private transcripts, secrets, or project-owned source truth belong in this ledger.",
        ],
    }


def status_document(index: dict[str, Any], *, schema_prefix: str) -> dict[str, Any]:
    data = dict(index)
    data["schema"] = _schema(schema_prefix, "changes_status_v1")
    return data


def record_document(
    *,
    schema_prefix: str,
    version: str,
    change_id: str,
    title: str,
    intent: str,
    surfaces: list[str],
    status_value: str,
    created_at: str,
    updated_at: str,
    root: Path,
    project_readonly_roots: list[str],
) -> dict[str, Any]:
    path = root / "change.json"
    return {
        "schema": _schema(schema_prefix, "change_record_v1"),
        "version": version,
        "id": change_id,
        "title": title,
        "status": status_value,
        "created_at": created_at,
        "updated_at": updated_at,
        "owner": "abyss-machine",
        "layer": "host-machine",
        "intent": intent,
        "surfaces": surfaces,
        "path": str(root),
        "files": {
            "change": str(path),
            "intent": str(root / "intent.md"),
            "actions": str(root / "actions.jsonl"),
            "validation": str(root / "validation.md"),
            "rollback": str(root / "rollback.md"),
            "closeout": str(root / "closeout.md"),
        },
        "boundaries": {
            "machine_owned": True,
            "mutates_project_repos": False,
            "project_roots_readonly_by_default": project_readonly_roots,
        },
    }


def event_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    change_id: str,
    event: str,
    title: str | None,
    status: str,
    surfaces: list[str],
    note: str | None,
    decision_review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "schema": _schema(schema_prefix, "change_event_v1"),
        "version": version,
        "generated_at": generated_at,
        "change_id": change_id,
        "event": event,
        "title": title,
        "status": status,
        "surfaces": surfaces,
        "note": note,
    }
    if decision_review is not None:
        data["decision_review"] = decision_review
    return data


def record_result_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    ok: bool,
    created: bool,
    record: dict[str, Any],
    event: dict[str, Any],
    paths: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "change_record_result_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": ok,
        "created": created,
        "record": record,
        "event": event,
        "paths": paths,
    }


def latest_missing_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    latest_path: Path,
    error: str | None,
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "changes_latest_read_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "path": str(latest_path),
        "error": error or "missing",
    }


def latest_read_document(data: dict[str, Any], *, read_at: str) -> dict[str, Any]:
    payload = dict(data)
    payload["read_at"] = read_at
    return payload


def surface_path_class(
    path_text: str,
    *,
    state_dir: Path,
    machine_root: Path,
    user_systemd_dir: Path,
    fallback_protection: dict[str, Any],
) -> dict[str, Any]:
    path = Path(path_text).expanduser()
    resolved_text = str(path)
    if resolved_text.startswith("/etc/abyss-machine") or resolved_text == "/etc/abyss-machine":
        return {"class": "host_config", "decision": "allow_candidate", "owner": "abyss-machine", "path": resolved_text}
    if resolved_text.startswith(str(state_dir)) or resolved_text == str(state_dir):
        return {"class": "host_state", "decision": "allow_candidate", "owner": "abyss-machine", "path": resolved_text}
    if resolved_text.startswith(str(machine_root)) or resolved_text == str(machine_root):
        return {"class": "host_large_root", "decision": "allow_candidate", "owner": "abyss-machine", "path": resolved_text}
    if (
        resolved_text == "/usr/local/bin/abyss-machine"
        or resolved_text == "/usr/local/libexec/abyss-machine"
        or resolved_text.startswith("/usr/local/libexec/abyss-")
        or resolved_text == "/usr/local/libexec/abyss_machine"
        or resolved_text.startswith("/usr/local/libexec/abyss_machine/")
    ):
        return {"class": "host_binary", "decision": "allow_candidate", "owner": "abyss-machine", "path": resolved_text}
    if resolved_text == "/usr/local/share/abyss-machine" or resolved_text.startswith("/usr/local/share/abyss-machine/"):
        return {"class": "host_public_seed", "decision": "allow_candidate", "owner": "abyss-machine", "path": resolved_text}
    if resolved_text.startswith("/etc/systemd/system/abyss-"):
        return {"class": "host_system_systemd", "decision": "allow_candidate", "owner": "abyss-machine", "path": resolved_text}
    if resolved_text.startswith(str(user_systemd_dir / "abyss-")):
        return {"class": "host_user_systemd", "decision": "allow_candidate", "owner": "abyss-machine", "path": resolved_text}
    if resolved_text == "/run/abyss-machine" or resolved_text.startswith("/run/abyss-machine/"):
        return {"class": "host_runtime", "decision": "allow_candidate", "owner": "abyss-machine", "path": resolved_text}
    return {"path": resolved_text, **fallback_protection}


def preflight_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    surfaces: list[str],
    intent: str,
    change_id: str | None,
    rollback: str | None,
    owner_route: bool,
    classified_surfaces: list[dict[str, Any]],
    active_ids: list[str],
    topology_summary: dict[str, Any],
    latest_path: Path,
    history_root: Path,
    change_index_path: Path,
    hooks_etc_dir: Path,
    hooks_srv_dir: Path,
    hard_deny_without_owner_route: list[str],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for item in classified_surfaces:
        decision = item.get("decision")
        cls = str(item.get("class") or "")
        path = str(item.get("path") or "")
        if decision == "deny" and not owner_route:
            checks.append(validation_check("fail", f"surface_boundary:{path}", f"{path} is protected for host-layer mutation", item))
        elif decision == "deny" and owner_route:
            checks.append(validation_check("warn", f"surface_owner_route:{path}", f"{path} requires owner route; not machine-owned", item))
        elif cls == "system_root":
            checks.append(validation_check("warn", f"surface_system_root:{path}", f"{path} is system-root-adjacent; keep writes compact and reversible", item))
        else:
            checks.append(validation_check("ok", f"surface_allowed:{path}", f"{path} is an allowed host-layer candidate", item))

    active_id_set = set(active_ids)
    durable = any(str(item.get("class")) in DURABLE_SURFACE_CLASSES for item in classified_surfaces)
    if change_id:
        if change_id in active_id_set:
            checks.append(validation_check("ok", "change_record_active", f"active change record {change_id} exists"))
        else:
            checks.append(validation_check("warn", "change_record_missing", f"change record {change_id} is not active", {"active_ids": sorted(active_id_set)}))
    elif durable:
        checks.append(validation_check("warn", "change_record_recommended", "durable host-layer mutation should have an active change record", {"active_ids": sorted(active_id_set)}))
    else:
        checks.append(validation_check("ok", "change_record_not_required", "no durable host-layer mutation detected"))

    rollback_sensitive = [
        item for item in classified_surfaces
        if str(item.get("class")) in ROLLBACK_SENSITIVE_CLASSES
    ]
    if rollback_sensitive and not rollback:
        checks.append(validation_check(
            "warn",
            "rollback_route_recommended",
            "config, binary, and systemd surfaces should carry a rollback route",
            {"surfaces": rollback_sensitive},
        ))
    else:
        checks.append(validation_check("ok", "rollback_route", "rollback route supplied or not required", {"rollback": rollback}))

    topology_fails = int(topology_summary.get("fails") or 0) if isinstance(topology_summary, dict) else 0
    checks.append(validation_check(
        "fail" if topology_fails else "ok",
        "topology_preflight",
        "topology validator has no fails" if not topology_fails else "topology validator has fails",
        topology_summary,
    ))
    summary = validation_summary(checks)
    decision = "deny" if summary["fails"] else "warn" if summary["warnings"] else "allow"
    return {
        "schema": _schema(schema_prefix, "changes_preflight_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": decision != "deny",
        "decision": decision,
        "intent": intent,
        "change_id": change_id,
        "surfaces": surfaces,
        "classified_surfaces": classified_surfaces,
        "owner_route": owner_route,
        "rollback": rollback,
        "summary": summary,
        "checks": checks,
        "paths": {
            "latest": str(latest_path),
            "daily_glob": str(history_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "change_index": str(change_index_path),
        },
        "hooks": {
            "etc": str(hooks_etc_dir),
            "srv": str(hooks_srv_dir),
            "automatic_execution": False,
        },
        "policy": {
            "hard_deny_without_owner_route": hard_deny_without_owner_route,
            "warnings_do_not_block": True,
            "owner_route_is_explicit": owner_route,
        },
    }

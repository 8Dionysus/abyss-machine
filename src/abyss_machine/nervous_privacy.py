from __future__ import annotations

from typing import Any, Mapping


def default_privacy(schema_prefix: str, version: str, *, browser_raw_storage_root: str) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_nervous_privacy_v1",
        "version": version,
        "mode": "closed-by-default",
        "global_pause": False,
        "private_mode": False,
        "controls_required_before_daemon": [
            "global pause",
            "private mode",
            "per-source disable",
            "forget last N minutes",
            "redaction dry-run",
            "visible active-source status",
        ],
        "redaction": {
            "enabled": True,
            "dry_run_required_for_new_sources": False,
            "connector_specific_controls": True,
            "patterns": [
                "environment secrets",
                "private keys",
                "tokens",
                "password-like fields",
                "browser cookies",
                "container environment",
                "browser login/password pages",
            ],
        },
        "retention": {
            "raw_events_days": 14,
            "private_capture_artifacts_days": 14,
            "facts_days": 90,
            "retrieval_packs_days": 30,
            "summaries_days": 365,
            "evals_days": 365,
            "operator_review_required_for_longer_raw_retention": True,
        },
        "browser_content": {
            "form_values_captured": False,
            "cookies_captured": False,
            "local_storage_captured": False,
            "skip_body_text_when": [
                "password-like form fields are present",
                "URL or title matches login/sign-in/auth/password/2FA/billing/bank/token patterns",
            ],
            "raw_storage_root": browser_raw_storage_root,
        },
    }


def default_state(schema_prefix: str, version: str) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_nervous_privacy_state_v1",
        "version": version,
        "global_pause": False,
        "private_mode": False,
        "active_since": None,
        "updated_at": None,
        "updated_by": "default",
        "reason": "initial default",
        "last_change_id": None,
    }


def audit_record(
    event: Mapping[str, Any],
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_nervous_privacy_audit_v1",
        "version": version,
        "generated_at": generated_at,
        **dict(event),
    }


def state_document(
    *,
    defaults: Mapping[str, Any],
    loaded: Mapping[str, Any] | None,
    load_error: str | None,
    path: str,
    exists: bool,
) -> dict[str, Any]:
    if loaded is None:
        state = dict(defaults)
        if load_error != "missing":
            state["_load_error"] = load_error
    else:
        state = _deep_merge(dict(defaults), dict(loaded))
    state["global_pause"] = bool(state.get("global_pause"))
    state["private_mode"] = bool(state.get("private_mode"))
    state["path"] = path
    state["exists"] = exists
    return state


def saved_state_document(
    state: Mapping[str, Any],
    *,
    updated_by: str,
    reason: str | None,
    change_id: str,
    updated_at: str,
    schema_prefix: str,
    version: str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_nervous_privacy_state_v1",
        "version": version,
        "global_pause": bool(state.get("global_pause")),
        "private_mode": bool(state.get("private_mode")),
        "active_since": state.get("active_since"),
        "updated_at": updated_at,
        "updated_by": updated_by,
        "reason": reason,
        "last_change_id": change_id,
    }


def effective_privacy(config: Mapping[str, Any], state: Mapping[str, Any], *, state_path: str) -> dict[str, Any]:
    effective = dict(config)
    effective["global_pause"] = bool(config.get("global_pause")) or bool(state.get("global_pause"))
    effective["private_mode"] = bool(config.get("private_mode")) or bool(state.get("private_mode"))
    effective["state"] = dict(state)
    effective["state_path"] = state_path
    effective["effective_source"] = "config_or_state"
    return effective


def status_document(
    *,
    effective: Mapping[str, Any],
    config: Mapping[str, Any],
    config_path: str,
    state_path: str,
    audit_glob: str,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    state = effective.get("state", {}) if isinstance(effective.get("state"), dict) else {}
    return {
        "schema": f"{schema_prefix}_nervous_privacy_status_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": effective.get("_load_error") is None and state.get("_load_error") is None,
        "config_path": config_path,
        "state_path": state_path,
        "audit_glob": audit_glob,
        "global_pause": bool(effective.get("global_pause")),
        "private_mode": bool(effective.get("private_mode")),
        "config": {
            "mode": effective.get("mode"),
            "global_pause": bool(config.get("global_pause")),
            "private_mode": bool(config.get("private_mode")),
        },
        "state": state,
        "behavior": {
            "global_pause": "snapshot writes only an audit heartbeat and does not update facts/latest.json",
            "private_mode": "snapshot writes a minimal heartbeat with no detailed facts",
            "normal": "snapshot writes safe_now facts with source provenance",
        },
    }


def set_error(schema_prefix: str, version: str, generated_at: str) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_nervous_privacy_set_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "error": "target must be pause or private-mode",
    }


def set_transition(
    target: str,
    enabled: bool,
    before_state: Mapping[str, Any],
    *,
    active_since: str | None,
) -> dict[str, Any]:
    field = target_field(target)
    if field is None:
        return {"ok": False}
    after = dict(before_state)
    before_value = bool(after.get(field))
    after[field] = enabled
    if enabled and not before_value and not after.get("active_since"):
        after["active_since"] = active_since
    if not after.get("global_pause") and not after.get("private_mode"):
        after["active_since"] = None
    return {
        "ok": True,
        "target": target,
        "field": field,
        "before": before_value,
        "after": enabled,
        "state": after,
    }


def set_audit_event(
    *,
    change_id: Any,
    target: str,
    field: str,
    before: bool,
    after: bool,
    reason: str | None,
) -> dict[str, Any]:
    return {
        "event": "privacy_state_changed",
        "change_id": change_id,
        "target": target,
        "field": field,
        "before": before,
        "after": after,
        "reason": reason,
    }


def set_result(
    *,
    target: str,
    field: str,
    before: bool,
    after: bool,
    state: Mapping[str, Any],
    audit: Mapping[str, Any],
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_nervous_privacy_set_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "target": target,
        "field": field,
        "changed": before != after,
        "state": dict(state),
        "audit": dict(audit),
    }


def target_field(target: str) -> str | None:
    if target == "pause":
        return "global_pause"
    if target == "private-mode":
        return "private_mode"
    return None


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result

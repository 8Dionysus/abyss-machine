from __future__ import annotations

import re
from typing import Any, Mapping


def _nested_get(data: Any, path: list[str]) -> Any:
    current = data
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def compact_validation(data: Mapping[str, Any]) -> dict[str, Any]:
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    checks = data.get("checks") if isinstance(data.get("checks"), list) else []
    non_ok = [
        item for item in checks
        if isinstance(item, dict) and item.get("level") != "ok"
    ][:12]
    return {"ok": data.get("ok"), "summary": summary, "non_ok_checks": non_ok}


def validation_map(validations: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {name: compact_validation(data) for name, data in validations.items()}


def derived_refresh_status_document(
    *,
    passive_unit: Mapping[str, Any],
    derived_unit: Mapping[str, Any],
    passive_show: Mapping[str, Any],
    derived_show: Mapping[str, Any],
    passive_service: str,
    derived_service: str,
    dropin_path: str,
    dropin_exists: bool,
    expected_exec_fragments: list[str] | None = None,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    fragments = expected_exec_fragments or [
        "nervous quality-audit --refresh --json",
        "resource launch --class medium --kind indexing",
        "nervous index-build --json",
    ]
    passive_properties = passive_show.get("properties") if isinstance(passive_show.get("properties"), dict) else {}
    derived_properties = derived_show.get("properties") if isinstance(derived_show.get("properties"), dict) else {}
    on_success_raw = str(passive_properties.get("OnSuccess") or "")
    exec_start_raw = str(derived_properties.get("ExecStart") or "")
    on_success_units = [item for item in re.split(r"\s+", on_success_raw.strip()) if item]
    exec_fragments_present = {fragment: fragment in exec_start_raw for fragment in fragments}
    load_state = str(derived_properties.get("LoadState") or "")
    on_success_ok = derived_service in on_success_units or derived_service in on_success_raw
    exec_ok = all(exec_fragments_present.values())
    loaded_ok = load_state == "loaded" or bool(derived_unit.get("is_enabled"))
    ok = bool(on_success_ok and exec_ok and loaded_ok)
    return {
        "schema": f"{schema_prefix}_nervous_derived_refresh_status_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": ok,
        "service": derived_service,
        "passive_chronicle_service": passive_service,
        "dropin": {
            "path": dropin_path,
            "exists": bool(dropin_exists),
        },
        "units": {
            "passive_chronicle": dict(passive_unit),
            "derived_refresh": dict(derived_unit),
        },
        "systemd": {
            "passive_show": dict(passive_show),
            "derived_show": {
                key: value for key, value in derived_show.items()
                if key != "properties"
            },
            "on_success": on_success_raw,
            "on_success_units": on_success_units,
            "load_state": load_state,
            "fragment_path": derived_properties.get("FragmentPath"),
            "exec_fragments_present": exec_fragments_present,
        },
        "policy": {
            "deterministic_refresh_first": True,
            "index_refresh_resource_gated": True,
            "automatic_action": False,
            "repo_mutation": False,
        },
    }


def add_check(checks: list[dict[str, Any]], level: str, key: str, message: str, details: dict[str, Any] | None = None) -> None:
    item: dict[str, Any] = {"level": level, "key": key, "message": message}
    if details is not None:
        item["details"] = details
    checks.append(item)


def audit_checks(
    *,
    validations: Mapping[str, Mapping[str, Any]],
    timers: Mapping[str, Mapping[str, Any]],
    derived_refresh_status: Mapping[str, Any],
    status_data: Mapping[str, Any],
    privacy_status: Mapping[str, Any],
    redaction_summary: Mapping[str, Any],
    browser_latest: Mapping[str, Any] | None,
    browser_error: str | None,
    browser_path: str,
    capture_status: Mapping[str, Any],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for name, item in validations.items():
        summary = item.get("summary") if isinstance(item.get("summary"), dict) else {}
        fails = int(summary.get("fails") or 0)
        warnings = int(summary.get("warnings") or 0)
        if fails:
            add_check(checks, "fail", f"{name}_validate", f"{name} validation has failures", {"summary": summary, "non_ok_checks": item.get("non_ok_checks")})
        elif warnings:
            add_check(checks, "warn", f"{name}_validate", f"{name} validation has warnings", {"summary": summary, "non_ok_checks": item.get("non_ok_checks")})
        else:
            add_check(checks, "ok", f"{name}_validate", f"{name} validation is clean", {"summary": summary})

    for key, unit in timers.items():
        add_check(checks, "ok" if unit.get("is_active") else "fail", f"timer:{key}", f"{key} timer active", dict(unit))
    add_check(
        checks,
        "ok" if derived_refresh_status.get("ok") else "fail",
        "derived_refresh",
        "passive chronicle triggers derived refresh"
        if derived_refresh_status.get("ok")
        else "passive chronicle derived-refresh contract is incomplete",
        dict(derived_refresh_status),
    )
    add_check(checks, "ok" if status_data.get("ok") else "fail", "status", "nervous status is ok", {"phase": status_data.get("phase"), "warnings": status_data.get("warnings")})
    add_check(checks, "fail" if privacy_status.get("global_pause") else "ok", "privacy_pause", "global pause is not active", {"global_pause": privacy_status.get("global_pause"), "private_mode": privacy_status.get("private_mode")})
    add_check(checks, "ok" if int(redaction_summary.get("matches") or 0) >= 2 else "fail", "redaction_smoke", "redaction catches token/password-like text", {"summary": dict(redaction_summary)})
    add_check(checks, "ok" if isinstance(browser_latest, dict) else "warn", "browser_content_latest", "browser content latest is readable", {
        "path": browser_path,
        "error": browser_error,
        "ok": browser_latest.get("ok") if isinstance(browser_latest, dict) else None,
        "summary": browser_latest.get("summary") if isinstance(browser_latest, dict) else None,
    })
    capture_storage = capture_status.get("storage") if isinstance(capture_status.get("storage"), dict) else {}
    add_check(checks, "ok" if capture_status.get("ok") else "warn", "capture_status", "capture storage/status is readable", {"summary": capture_storage})
    return checks


def audit_document(
    *,
    refresh_requested: bool,
    refresh_index_requested: bool,
    refresh_results: Mapping[str, Any],
    validations: Mapping[str, Mapping[str, Any]],
    timers: Mapping[str, Mapping[str, Any]],
    status_data: Mapping[str, Any],
    capture_status: Mapping[str, Any],
    derived_refresh_status: Mapping[str, Any],
    privacy_status: Mapping[str, Any],
    sources: Mapping[str, Any],
    index_status: Mapping[str, Any],
    semantic_maintain: Mapping[str, Any],
    browser_latest: Mapping[str, Any] | None,
    browser_error: str | None,
    browser_path: str,
    redaction_summary: Mapping[str, Any],
    privacy_state_path: str,
    index_db_path: str,
    latest_path: str,
    daily_glob: str,
    commands: Mapping[str, str],
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    compact_validations = validation_map(validations)
    checks = audit_checks(
        validations=compact_validations,
        timers=timers,
        derived_refresh_status=derived_refresh_status,
        status_data=status_data,
        privacy_status=privacy_status,
        redaction_summary=redaction_summary,
        browser_latest=browser_latest,
        browser_error=browser_error,
        browser_path=browser_path,
        capture_status=capture_status,
    )
    fails = sum(1 for item in checks if item["level"] == "fail")
    warnings = sum(1 for item in checks if item["level"] == "warn")
    return {
        "schema": f"{schema_prefix}_nervous_quality_audit_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": fails == 0,
        "refresh": {"requested": bool(refresh_requested), "index_requested": bool(refresh_index_requested), "results": dict(refresh_results)},
        "summary": {"status": "ok" if fails == 0 else "fail", "fails": fails, "warnings": warnings, "checks": len(checks)},
        "checks": checks,
        "validations": compact_validations,
        "status": {
            "phase": status_data.get("phase"),
            "ok": status_data.get("ok"),
            "enabled_safe_sources": _nested_get(status_data, ["sources", "enabled_safe_sources"]),
            "enabled_private_connector_sources": _nested_get(status_data, ["sources", "enabled_private_connector_sources"]),
        },
        "privacy": {
            "global_pause": privacy_status.get("global_pause"),
            "private_mode": privacy_status.get("private_mode"),
            "state_path": privacy_state_path,
        },
        "sources": {
            "safe_now": list((sources.get("safe_now") or {}).keys()) if isinstance(sources.get("safe_now"), dict) else [],
            "private_connectors": list((sources.get("deferred_until_privacy_controls") or {}).keys()) if isinstance(sources.get("deferred_until_privacy_controls"), dict) else [],
        },
        "capture": {
            "status": dict(capture_status),
            "browser_content_latest": {
                "path": browser_path,
                "ok": browser_latest.get("ok") if isinstance(browser_latest, dict) else None,
                "summary": browser_latest.get("summary") if isinstance(browser_latest, dict) else None,
                "error": browser_error,
            },
        },
        "automation": {
            "derived_refresh": dict(derived_refresh_status),
            "semantic_maintain": dict(semantic_maintain),
        },
        "index": {
            "status": dict(index_status),
            "db": index_db_path,
        },
        "paths": {
            "latest": latest_path,
            "daily_glob": daily_glob,
        },
        "commands": {
            "audit": commands.get("audit", "abyss-machine nervous quality-audit --json"),
            "refresh": commands.get("refresh", "abyss-machine nervous quality-audit --refresh --json"),
            "refresh_index": commands.get("refresh_index", "abyss-machine nervous quality-audit --refresh --refresh-index --json"),
            "validate": commands.get("validate", "abyss-machine nervous validate --json"),
        },
        "policy": {
            "raw_private_content": False,
            "automatic_action": False,
            "automatic_repo_write": False,
            "refresh_rebuilds_derived_records_only": True,
            "redaction_smoke_omits_raw_secret_text": True,
        },
    }

from __future__ import annotations

from pathlib import Path
from typing import Any


def _schema(schema_prefix: str, suffix: str) -> str:
    return f"{schema_prefix}_{suffix}"


def paths_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    refs: dict[str, Any],
    year: str,
    month: str,
    date_name: str,
) -> dict[str, Any]:
    thermal_root = Path(str(refs["thermal_root"]))
    return {
        "schema": _schema(schema_prefix, "observability_paths_v1"),
        "version": version,
        "generated_at": generated_at,
        "root": str(refs["root"]),
        "agent_entrypoint": str(refs["agent_entrypoint"]),
        "index": str(refs["index"]),
        "config": str(refs["config"]),
        "collector": str(refs["collector"]),
        "thermal_battery": {
            "root": str(thermal_root),
            "latest": str(thermal_root / "latest.json"),
            "state": str(thermal_root / "state.json"),
            "today_samples": str(thermal_root / "samples" / year / month / f"{date_name}.jsonl"),
            "today_events": str(thermal_root / "events" / year / month / f"{date_name}.jsonl"),
            "today_summary": str(thermal_root / "summaries" / year / month / f"{date_name}.json"),
            "samples_glob": str(thermal_root / "samples" / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "events_glob": str(thermal_root / "events" / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "summaries_glob": str(thermal_root / "summaries" / "YYYY" / "MM" / "YYYY-MM-DD.json"),
        },
        "systemd": {
            "timer": str(refs["timer"]),
            "service": str(refs["service"]),
        },
        "commands": {
            "status": "abyss-machine observability status --json",
            "paths": "abyss-machine observability paths --json",
            "latest": "abyss-machine observability latest --json",
            "collect": "abyss-machine observability collect --json",
        },
        "policy_contract": {
            "read_only_by_default": True,
            "collect_requires_explicit_command": True,
            "automatic_permission_changes": False,
            "repo_mutation": False,
        },
    }


def latest_read_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    path: str,
    data: Any,
    error: Any,
) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {
            "schema": _schema(schema_prefix, "observability_latest_read_v1"),
            "version": version,
            "generated_at": generated_at,
            "ok": False,
            "path": path,
            "error": error or "missing",
        }
    payload = dict(data)
    payload.setdefault("schema", _schema(schema_prefix, "observability_latest_v1"))
    payload["read_at"] = generated_at
    return payload


def manual_collect_probe_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    collector: str,
    collector_exists: bool,
    current_euid: int,
    current_egid: int,
    current_groups: list[int],
    missing_or_unwritable: list[str],
    directories: list[dict[str, Any]],
) -> dict[str, Any]:
    status = "ready" if not missing_or_unwritable and collector_exists else "operator_authorization_required"
    return {
        "schema": _schema(schema_prefix, "observability_manual_collect_probe_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": status == "ready",
        "status": status,
        "collector": collector,
        "collector_exists": collector_exists,
        "current_euid": current_euid,
        "current_egid": current_egid,
        "current_groups": sorted(current_groups),
        "missing_or_unwritable": missing_or_unwritable,
        "directories": directories,
        "manual_command": "abyss-machine observability collect --json",
        "operator_route": "authorize root-owned collector permission normalization or chmod the affected observability daily directories to group-writable setgid 2775",
        "policy": {
            "read_only_probe": True,
            "does_not_run_collector": True,
            "does_not_change_permissions": True,
            "automatic_action": False,
        },
    }


def sample_temperature(sample: dict[str, Any]) -> float | None:
    thermal = sample.get("thermal") if isinstance(sample.get("thermal"), dict) else {}
    sensors = thermal.get("sensors") if isinstance(thermal.get("sensors"), dict) else {}
    value = sensors.get("temperature_c_max")
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def latest_summary(latest: dict[str, Any], latest_age_sec: float | None) -> dict[str, Any]:
    sample = latest.get("sample") if isinstance(latest.get("sample"), dict) else {}
    thermal = sample.get("thermal") if isinstance(sample.get("thermal"), dict) else {}
    sensors = thermal.get("sensors") if isinstance(thermal.get("sensors"), dict) else {}
    power = sample.get("power") if isinstance(sample.get("power"), dict) else {}
    return {
        "ok": latest.get("ok", True),
        "updated_at": latest.get("updated_at"),
        "age_sec": latest_age_sec,
        "class": sample.get("class") if sample else None,
        "temperature_c_max": sensors.get("temperature_c_max"),
        "battery": power.get("battery") if power else None,
        "error": latest.get("error"),
    }


def status_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    root_exists: bool,
    agent_entrypoint_exists: bool,
    index_exists: bool,
    config_exists: bool,
    collector_exists: bool,
    timer: dict[str, Any],
    service: dict[str, Any],
    manual_collect: dict[str, Any],
    paths: dict[str, Any],
    latest: dict[str, Any],
    latest_age_sec: float | None,
    today: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "observability_status_v1"),
        "version": version,
        "generated_at": generated_at,
        "root_exists": root_exists,
        "agent_entrypoint_exists": agent_entrypoint_exists,
        "index_exists": index_exists,
        "config_exists": config_exists,
        "collector_exists": collector_exists,
        "timer": timer,
        "service": service,
        "manual_collect": manual_collect,
        "paths": paths,
        "latest": latest_summary(latest, latest_age_sec),
        "today": today,
    }

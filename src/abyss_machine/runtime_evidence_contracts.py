from __future__ import annotations

import collections
import datetime as dt
from pathlib import Path
from typing import Any

from . import validation_contracts


REACTION_SEVERITY_ORDER = {
    "info": 0,
    "notice": 1,
    "warning": 2,
    "watch": 3,
    "critical": 4,
}

HEARTBEAT_BRIDGE_STABLE_FIELDS = (
    "source_freshness",
    "rhythm",
    "candidate_lifecycle",
    "pressure_context",
    "capture_health",
    "ai_hygiene",
    "e2b_breath",
    "self_awareness_breath",
)

HEARTBEAT_BRIDGE_REQUIRED_VALIDATE_CHECKS = (
    "policy_non_executing",
    "no_automatic_actions",
    "source_freshness_schema",
    "source_freshness_sources",
    "source_freshness_items",
    "rhythm_schema",
    "rhythm_expected_interval",
    "rhythm_recurring_timer",
    "rhythm_no_missed_beats",
    "candidate_lifecycle_schema",
    "pressure_context_schema",
    "pressure_context_route",
    "pressure_context_psi_evidence",
    "pressure_context_non_mutating",
    "capture_health_schema",
    "capture_health_web_context_quality",
    "capture_health_non_mutating",
    "capture_health_owner_gated_routes",
    "ai_hygiene_schema",
    "ai_hygiene_non_executing",
    "ai_hygiene_owner_gated_routes",
    "e2b_breath_schema",
    "e2b_breath_inputs",
    "e2b_breath_outputs",
    "e2b_breath_non_executing",
    "self_awareness_breath_schema",
    "self_awareness_breath_counts",
    "self_awareness_breath_non_executing",
)


def _schema(schema_prefix: str, suffix: str) -> str:
    return f"{schema_prefix}_{suffix}"


def nested_get(data: Any, path: list[str]) -> Any:
    cursor: Any = data
    for key in path:
        if not isinstance(cursor, dict):
            return None
        cursor = cursor.get(key)
    return cursor


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float | None = None) -> float | None:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_iso(value: Any) -> dt.datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = dt.datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    except (TypeError, ValueError):
        return None


def age_seconds(generated_at: Any, *, now: dt.datetime | None = None) -> float | None:
    parsed = parse_iso(generated_at)
    if parsed is None:
        return None
    current = now or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=dt.timezone.utc)
    return round(max(0.0, (current.astimezone(dt.timezone.utc) - parsed).total_seconds()), 1)


def freshness_class(ok: bool, age_sec: float | None, ttl_sec: int, aging_sec: int, error: Any = None) -> str:
    if not ok:
        if str(error or "").lower() == "missing":
            return "missing"
        return "invalid"
    if age_sec is None:
        return "invalid"
    if age_sec > ttl_sec:
        return "stale"
    if age_sec > aging_sec:
        return "aging"
    return "fresh"


def heartbeat_input_ref(
    name: str,
    path: Any,
    data: dict[str, Any],
    status: Any = None,
    *,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    generated_at = data.get("generated_at")
    if status is None:
        status = data.get("status")
    if status is None and isinstance(data.get("summary"), dict):
        status = data.get("summary", {}).get("status")
    return {
        "name": name,
        "path": str(path),
        "ok": bool(data.get("ok")),
        "status": status,
        "generated_at": generated_at,
        "age_sec": age_seconds(generated_at, now=now),
        "error": data.get("error"),
    }


def heartbeat_source_freshness_ttls(expected_interval_sec: int) -> dict[str, dict[str, int]]:
    return {
        "nervous_brief": {"aging_sec": 900, "ttl_sec": 3600},
        "nervous_events": {"aging_sec": 1200, "ttl_sec": 3600},
        "doctor": {"aging_sec": 1800, "ttl_sec": 7200},
        "doctor_machine_report": {"aging_sec": 1800, "ttl_sec": 7200},
        "resource_orchestrator": {"aging_sec": 900, "ttl_sec": 3600},
        "memory_pressure": {"aging_sec": 900, "ttl_sec": 3600},
        "memory_plan": {"aging_sec": 900, "ttl_sec": 3600},
        "processes_game_guard": {"aging_sec": 900, "ttl_sec": 3600},
        "nervous_capture": {"aging_sec": 900, "ttl_sec": 3600},
        "nervous_browser_content": {"aging_sec": 300, "ttl_sec": 900},
        "typing": {"aging_sec": 900, "ttl_sec": 3600},
        "typing_coverage": {"aging_sec": 900, "ttl_sec": 3600},
        "typing_process": {"aging_sec": 900, "ttl_sec": 3600},
        "typing_nervous_refresh": {"aging_sec": 1800, "ttl_sec": 7200},
        "nervous_retention": {"aging_sec": 86400, "ttl_sec": 172800},
        "ai_llm_validate": {"aging_sec": 3600, "ttl_sec": 21600},
        "ai_resident_candidates": {"aging_sec": 900, "ttl_sec": 3600},
        "ai_resident_evals": {"aging_sec": 3600, "ttl_sec": 21600},
        "ai_workhorse_validate": {"aging_sec": 3600, "ttl_sec": 21600},
        "ai_workhorse_review": {"aging_sec": 3600, "ttl_sec": 21600},
        "ai_resident_candidates_validate": {"aging_sec": 3600, "ttl_sec": 21600},
        "ai_resident_evals_validate": {"aging_sec": 3600, "ttl_sec": 21600},
        "self_awareness_autolink": {"aging_sec": expected_interval_sec * 2, "ttl_sec": expected_interval_sec * 4},
        "reactions": {"aging_sec": 300, "ttl_sec": 900},
        "responses": {"aging_sec": 300, "ttl_sec": 900},
        "changes": {"aging_sec": 300, "ttl_sec": 900},
    }


def heartbeat_source_freshness(
    *,
    schema_prefix: str,
    inputs: dict[str, dict[str, Any]],
    ttl_config: dict[str, dict[str, int]],
    previous_latest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    previous_sources = nested_get(previous_latest or {}, ["source_freshness", "sources"])
    previous_by_name = previous_sources if isinstance(previous_sources, dict) else {}
    sources: dict[str, dict[str, Any]] = {}
    counts: dict[str, int] = {}
    for name, ref in inputs.items():
        ttl = ttl_config.get(name, {"aging_sec": 900, "ttl_sec": 3600})
        ref_age_sec = ref.get("age_sec")
        readable = bool(ref.get("ok")) or (ref.get("generated_at") is not None and not ref.get("error"))
        current_class = freshness_class(
            readable,
            float(ref_age_sec) if isinstance(ref_age_sec, (int, float)) else None,
            int(ttl["ttl_sec"]),
            int(ttl["aging_sec"]),
            ref.get("error"),
        )
        previous = previous_by_name.get(name) if isinstance(previous_by_name.get(name), dict) else {}
        stale_streak = int(previous.get("stale_streak") or 0) + 1 if current_class == "stale" else 0
        last_ok_at = ref.get("generated_at") if readable else previous.get("last_ok_at")
        counts[current_class] = counts.get(current_class, 0) + 1
        sources[name] = {
            "name": name,
            "path": ref.get("path"),
            "ok": bool(ref.get("ok")),
            "readable": readable,
            "status": ref.get("status"),
            "generated_at": ref.get("generated_at"),
            "age_sec": ref_age_sec,
            "aging_sec": int(ttl["aging_sec"]),
            "ttl_sec": int(ttl["ttl_sec"]),
            "freshness_class": current_class,
            "stale_streak": stale_streak,
            "last_ok_at": last_ok_at,
            "error": ref.get("error"),
        }
    class_rank = {"fresh": 0, "aging": 1, "stale": 2, "missing": 3, "invalid": 3}
    worst = max(sources.values(), key=lambda item: class_rank.get(str(item.get("freshness_class")), 0), default={})
    return {
        "schema": _schema(schema_prefix, "heartbeat_source_freshness_v1"),
        "sources": sources,
        "summary": {
            "status": worst.get("freshness_class") or "unknown",
            "by_class": counts,
            "stale_sources": [name for name, item in sources.items() if item.get("freshness_class") == "stale"],
            "aging_sources": [name for name, item in sources.items() if item.get("freshness_class") == "aging"],
            "missing_or_invalid_sources": [
                name for name, item in sources.items() if item.get("freshness_class") in {"missing", "invalid"}
            ],
        },
    }


def parse_user_jobs(text: str) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("JOB "):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        job_id, unit, job_type, state = parts[:4]
        if not job_id.isdigit():
            continue
        jobs.append({
            "job": int(job_id),
            "unit": unit,
            "type": job_type,
            "state": state,
            "raw": line,
        })
    return jobs


def parse_timer_line(line: str, *, heartbeat_timer: str) -> dict[str, Any]:
    parts = str(line or "").split()
    data: dict[str, Any] = {
        "next_beat_at": None,
        "left": None,
        "last_trigger": None,
        "passed": None,
    }
    if not parts or heartbeat_timer not in parts:
        return data
    unit_index = parts.index(heartbeat_timer)
    if len(parts) >= 5 and parts[0] != "-":
        data["next_beat_at"] = " ".join(parts[0:4])
        data["left"] = parts[4]
    elif parts[0] == "-":
        data["left"] = parts[1] if len(parts) > 1 else None
    if unit_index >= 9:
        data["last_trigger"] = " ".join(parts[5:9])
        data["passed"] = " ".join(parts[9:unit_index])
    elif unit_index > 5:
        data["last_trigger"] = " ".join(parts[5:unit_index])
    return data


def heartbeat_systemd_job_causality(
    *,
    heartbeat_service: str,
    jobs: dict[str, Any],
    service_props: dict[str, Any],
) -> dict[str, Any]:
    after_units = set(str(service_props.get("properties", {}).get("After") or "").split())
    running_jobs = [job for job in jobs.get("jobs", []) if job.get("state") == "running"]
    waiting_jobs = [job for job in jobs.get("waiting_heartbeat_jobs", [])]
    blockers = [job for job in running_jobs if str(job.get("unit")) in after_units]
    return {
        "status": "waiting" if waiting_jobs else "clear",
        "waiting_heartbeat_jobs": waiting_jobs,
        "running_jobs": running_jobs,
        "blocking_candidates": blockers,
        "heartbeat_after_units": sorted(after_units),
        "heartbeat_service": heartbeat_service,
        "heartbeat_service_properties": service_props,
    }


def heartbeat_rhythm_document(
    *,
    schema_prefix: str,
    expected_interval_sec: int,
    previous_latest: dict[str, Any] | None,
    heartbeat_timer: dict[str, Any],
    jobs: dict[str, Any],
    generated_at: str,
    timer_list: dict[str, Any],
) -> dict[str, Any]:
    previous_generated_at = previous_latest.get("generated_at") if isinstance(previous_latest, dict) else None
    current_dt = parse_iso(generated_at)
    previous_dt = parse_iso(previous_generated_at)
    observed_interval = None
    drift = None
    missed_beats = 0
    if current_dt is not None and previous_dt is not None:
        observed_interval = round(max(0.0, (current_dt - previous_dt).total_seconds()), 1)
        drift = round(observed_interval - expected_interval_sec, 1)
        missed_beats = max(0, int(observed_interval // expected_interval_sec) - 1)
    pending_heartbeat_jobs = jobs.get("heartbeat_jobs") if isinstance(jobs.get("heartbeat_jobs"), list) else []
    waiting_heartbeat_jobs = jobs.get("waiting_heartbeat_jobs") if isinstance(jobs.get("waiting_heartbeat_jobs"), list) else []
    return {
        "schema": _schema(schema_prefix, "heartbeat_rhythm_v1"),
        "status": "waiting" if waiting_heartbeat_jobs else ("missed" if missed_beats > 0 else "steady"),
        "last_beat_at": previous_generated_at,
        "this_beat_at": generated_at,
        "next_beat_at": timer_list.get("next_beat_at"),
        "expected_interval_sec": expected_interval_sec,
        "observed_interval_sec": observed_interval,
        "drift_sec": drift,
        "missed_beats": missed_beats,
        "timer_active": bool(heartbeat_timer.get("is_active")),
        "timer_enabled": bool(heartbeat_timer.get("is_enabled")),
        "pending_heartbeat_job": bool(pending_heartbeat_jobs),
        "waiting_heartbeat_job": bool(waiting_heartbeat_jobs),
        "timer_list": timer_list,
    }


def heartbeat_candidate_lifecycle(
    *,
    schema_prefix: str,
    candidates: list[dict[str, Any]],
    previous_latest: dict[str, Any] | None,
    generated_at: str,
) -> dict[str, Any]:
    previous_active_list = nested_get(previous_latest or {}, ["candidate_lifecycle", "active"])
    previous_resolved_list = nested_get(previous_latest or {}, ["candidate_lifecycle", "recently_resolved"])
    previous_active = {
        str(item.get("id")): item
        for item in previous_active_list
        if isinstance(item, dict) and item.get("id")
    } if isinstance(previous_active_list, list) else {}
    previous_resolved = {
        str(item.get("id")): item
        for item in previous_resolved_list
        if isinstance(item, dict) and item.get("id")
    } if isinstance(previous_resolved_list, list) else {}
    active: list[dict[str, Any]] = []
    current_ids: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict) or not candidate.get("id"):
            continue
        candidate_id = str(candidate.get("id"))
        current_ids.add(candidate_id)
        previous = previous_active.get(candidate_id) or previous_resolved.get(candidate_id) or {}
        was_active = candidate_id in previous_active
        severity = str(candidate.get("severity") or "")
        previous_history = previous.get("severity_history") if isinstance(previous.get("severity_history"), list) else []
        severity_history = list(previous_history)
        if not severity_history or severity_history[-1] != severity:
            severity_history.append(severity)
        active.append({
            "id": candidate_id,
            "active": True,
            "first_seen_at": previous.get("first_seen_at") or generated_at,
            "last_seen_at": generated_at,
            "consecutive_beats": int(previous.get("consecutive_beats") or 0) + 1 if was_active else 1,
            "total_beats": int(previous.get("total_beats") or 0) + 1,
            "severity": severity,
            "severity_history": severity_history[-12:],
            "category": candidate.get("category"),
            "owner_route": candidate.get("owner_route"),
            "command": candidate.get("command"),
            "reason": candidate.get("reason"),
            "resolved_at": None,
        })
    recently_resolved: list[dict[str, Any]] = []
    for candidate_id, previous in previous_active.items():
        if candidate_id in current_ids:
            continue
        resolved = dict(previous)
        resolved["active"] = False
        resolved["resolved_at"] = generated_at
        resolved["last_seen_at"] = previous.get("last_seen_at")
        recently_resolved.append(resolved)
    return {
        "schema": _schema(schema_prefix, "heartbeat_candidate_lifecycle_v1"),
        "active": active,
        "recently_resolved": recently_resolved,
        "summary": {
            "active": len(active),
            "recently_resolved": len(recently_resolved),
            "persistent": len([item for item in active if int(item.get("consecutive_beats") or 0) > 1]),
        },
    }


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def reaction_candidate(
    schema_prefix: str,
    candidate_id: str,
    *,
    title: str,
    severity: str,
    category: str,
    reason: str,
    command: str | None,
    evidence: list[dict[str, Any]],
    owner_route: str = "abyss-machine",
    action_mode: str = "operator_review",
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "reaction_candidate_v1"),
        "id": candidate_id,
        "title": title,
        "severity": severity,
        "category": category,
        "owner_route": owner_route,
        "action_mode": action_mode,
        "automatic": False,
        "command": command,
        "reason": reason,
        "evidence": evidence,
    }


def add_reaction_candidate(candidates: list[dict[str, Any]], candidate: dict[str, Any]) -> None:
    if any(item.get("id") == candidate.get("id") for item in candidates):
        return
    candidates.append(candidate)


def reaction_overall_status(candidates: list[dict[str, Any]]) -> str:
    if not candidates:
        return "quiet"
    highest = max(REACTION_SEVERITY_ORDER.get(str(item.get("severity")), 0) for item in candidates)
    if highest >= REACTION_SEVERITY_ORDER["critical"]:
        return "blocked"
    if highest >= REACTION_SEVERITY_ORDER["watch"]:
        return "watch"
    if highest >= REACTION_SEVERITY_ORDER["warning"]:
        return "attention"
    return "notice"


def heartbeat_status_from(
    *,
    nervous_brief: dict[str, Any],
    doctor_latest: dict[str, Any],
    machine_report: dict[str, Any],
    reactions: dict[str, Any],
    changes: dict[str, Any],
) -> str:
    readiness = nervous_brief.get("readiness") if isinstance(nervous_brief.get("readiness"), dict) else {}
    reaction_status_value = str(nested_get(reactions, ["summary", "status"]) or reactions.get("status") or "")
    doctor_warnings = int(nested_get(doctor_latest, ["summary", "warnings"]) or 0)
    active_changes = int(nested_get(changes, ["summary", "active_records"]) or 0)
    machine_status = str(machine_report.get("status") or "")
    if not nervous_brief.get("ok") or readiness.get("status") not in (None, "ready"):
        return "watch"
    if reaction_status_value in {"blocked", "watch"}:
        return "watch"
    if reaction_status_value == "attention" or doctor_warnings > 0 or machine_status in {"watch", "warn"}:
        return "attention"
    if active_changes > 0:
        return "attention"
    return "steady"


def heartbeat_promote_status(
    status: str,
    pressure_context: dict[str, Any],
    capture_health: dict[str, Any],
    ai_hygiene: dict[str, Any] | None = None,
) -> str:
    rank = {"steady": 0, "attention": 1, "watch": 2}.get(str(status), 0)
    pressure_route = str(pressure_context.get("route") or "")
    if pressure_route in {"block", "defer"}:
        rank = max(rank, 2)
    elif pressure_route in {"soften", "observe"}:
        rank = max(rank, 1)
    capture_status = str(capture_health.get("status") or "")
    if capture_status == "watch":
        rank = max(rank, 2)
    elif capture_status == "attention":
        rank = max(rank, 1)
    ai_status = str((ai_hygiene or {}).get("status") or "")
    if ai_status == "watch":
        rank = max(rank, 2)
    elif ai_status == "attention":
        rank = max(rank, 1)
    if rank >= 2:
        return "watch"
    if rank == 1:
        return "attention"
    return "steady"


def heartbeats_paths_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    refs: dict[str, Any],
    inputs: dict[str, Any],
) -> dict[str, Any]:
    root = Path(str(refs["root"]))
    validate_root = Path(str(refs["validate_root"]))
    return {
        "schema": _schema(schema_prefix, "heartbeats_paths_v1"),
        "version": version,
        "generated_at": generated_at,
        "root": str(root),
        "agent_entrypoint": str(refs["agent_entrypoint"]),
        "latest": str(refs["latest"]),
        "history_daily_glob": str(root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        "validate": {
            "root": str(validate_root),
            "latest": str(refs["validate_latest"]),
            "daily_glob": str(validate_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        },
        "systemd_user": {
            "service": str(refs["service_path"]),
            "timer": str(refs["timer_path"]),
            "service_unit": str(refs["service_unit"]),
            "timer_unit": str(refs["timer_unit"]),
        },
        "commands": {
            "pulse": "abyss-machine heartbeats pulse --json",
            "status": "abyss-machine heartbeats --json",
            "paths": "abyss-machine heartbeats paths --json",
            "validate": "abyss-machine heartbeats validate --json",
        },
        "naming": {
            "subsystem": "heartbeats",
            "unit_record": "heartbeat_pulse",
            "timer": str(refs["timer_unit"]),
            "principle": "plural subsystem for recurring pulses; singular pulse for one observed system beat",
        },
        "inputs": {key: str(value) for key, value in inputs.items()},
        "policy": {
            "read_model": True,
            "recurring": True,
            "automatic_action": False,
            "executes_reaction_commands": False,
            "executes_response_commands": False,
            "repo_mutation": False,
        },
    }


def reaction_paths_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    refs: dict[str, Any],
    inputs: dict[str, Any],
) -> dict[str, Any]:
    root = Path(str(refs["root"]))
    validate_root = Path(str(refs["validate_root"]))
    return {
        "schema": _schema(schema_prefix, "reactions_paths_v1"),
        "version": version,
        "generated_at": generated_at,
        "root": str(root),
        "agent_entrypoint": str(refs["agent_entrypoint"]),
        "latest": str(refs["latest"]),
        "history_daily_glob": str(root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        "validate": {
            "root": str(validate_root),
            "latest": str(refs["validate_latest"]),
            "daily_glob": str(validate_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        },
        "commands": {
            "status": "abyss-machine reactions --json",
            "paths": "abyss-machine reactions paths --json",
            "validate": "abyss-machine reactions validate --json",
        },
        "inputs": {key: str(value) if not isinstance(value, list) else [str(item) for item in value] for key, value in inputs.items()},
        "policy": {
            "read_model": True,
            "automatic_action": False,
            "repo_mutation": False,
            "execution_authority": "none",
        },
    }


def response_paths_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    refs: dict[str, Any],
    inputs: dict[str, Any],
) -> dict[str, Any]:
    root = Path(str(refs["root"]))
    validate_root = Path(str(refs["validate_root"]))
    return {
        "schema": _schema(schema_prefix, "responses_paths_v1"),
        "version": version,
        "generated_at": generated_at,
        "root": str(root),
        "agent_entrypoint": str(refs["agent_entrypoint"]),
        "latest": str(refs["latest"]),
        "history_daily_glob": str(root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        "validate": {
            "root": str(validate_root),
            "latest": str(refs["validate_latest"]),
            "daily_glob": str(validate_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        },
        "commands": {
            "status": "abyss-machine responses --json",
            "paths": "abyss-machine responses paths --json",
            "validate": "abyss-machine responses validate --json",
        },
        "naming": {
            "subsystem": "responses",
            "unit_record": "response_route",
            "chain": "heartbeats -> reactions -> responses -> explicit owner-approved action",
            "principle": "plural subsystem for available response routes; singular response_route for one gated route from one reaction candidate",
        },
        "inputs": {key: str(value) for key, value in inputs.items()},
        "policy": {
            "read_model": True,
            "automatic_action": False,
            "automatic_response": False,
            "executes_commands": False,
            "requires_owner_gate": True,
            "repo_mutation": False,
        },
    }


def _runtime_validate_document(
    *,
    schema_prefix: str,
    schema_suffix: str,
    version: str,
    generated_at: str,
    checks: list[dict[str, Any]],
    strict: bool,
    scope: str,
    paths: dict[str, Any],
) -> dict[str, Any]:
    return validation_contracts.validation_document(
        schema=_schema(schema_prefix, schema_suffix),
        version=version,
        generated_at=generated_at,
        checks=checks,
        strict=strict,
        scope=scope,
        extra={"paths": dict(paths) if isinstance(paths, dict) else {}},
    )


def heartbeats_validate_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    checks: list[dict[str, Any]],
    strict: bool,
    paths: dict[str, Any],
) -> dict[str, Any]:
    return _runtime_validate_document(
        schema_prefix=schema_prefix,
        schema_suffix="heartbeats_validate_v1",
        version=version,
        generated_at=generated_at,
        checks=checks,
        strict=strict,
        scope="OS Abyss recurring Heartbeats readmodel",
        paths=paths,
    )


def reactions_validate_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    checks: list[dict[str, Any]],
    strict: bool,
    paths: dict[str, Any],
) -> dict[str, Any]:
    return _runtime_validate_document(
        schema_prefix=schema_prefix,
        schema_suffix="reactions_validate_v1",
        version=version,
        generated_at=generated_at,
        checks=checks,
        strict=strict,
        scope="Abyss Machine reaction candidate readmodel",
        paths=paths,
    )


def responses_validate_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    checks: list[dict[str, Any]],
    strict: bool,
    paths: dict[str, Any],
) -> dict[str, Any]:
    return _runtime_validate_document(
        schema_prefix=schema_prefix,
        schema_suffix="responses_validate_v1",
        version=version,
        generated_at=generated_at,
        checks=checks,
        strict=strict,
        scope="OS Abyss owner-gated response routes readmodel",
        paths=paths,
    )


def response_command_profile(command: str | None) -> dict[str, Any]:
    command_text = str(command or "").strip()
    if not command_text:
        return {
            "kind": "missing_command",
            "scope": "review",
            "mutating_if_run": False,
            "requires_change_preflight": False,
            "requires_operator": True,
        }
    mutation_markers = [
        " --repair",
        " --apply",
        " --confirm",
        " --execute-live",
        " reset-failed ",
        " systemctl start ",
        " systemctl stop ",
        " systemctl restart ",
        " pkexec ",
        " sudo ",
        " rm ",
    ]
    mutating_if_run = any(marker in f" {command_text} " for marker in mutation_markers)
    if command_text.startswith("abyss-machine processes desktop-compositor "):
        kind = "read_only_probe"
        scope = "observe"
    elif command_text.startswith("abyss-machine doctor --json"):
        kind = "read_model_probe"
        scope = "observe"
    elif command_text.startswith("abyss-machine nervous recall "):
        kind = "read_model_probe"
        scope = "observe"
    elif command_text.startswith("abyss-machine nervous retention-apply --dry-run"):
        kind = "owner_gated_retention_dry_run"
        scope = "privacy_retention"
        mutating_if_run = False
    elif command_text.startswith("abyss-machine nervous web-performance-diagnostic "):
        kind = "owner_gated_web_performance_diagnostic"
        scope = "web_diagnostic"
        mutating_if_run = False
    elif command_text.startswith("abyss-machine ai llm workhorse review --json"):
        kind = "owner_gated_ai_hygiene_review"
        scope = "ai_hygiene"
        mutating_if_run = False
    elif command_text.startswith("abyss-machine ai llm workhorse validate --json"):
        kind = "read_model_probe"
        scope = "ai_hygiene"
        mutating_if_run = False
    elif command_text.startswith("abyss-machine self-awareness brief "):
        kind = "self_awareness_brief"
        scope = "self_awareness"
        mutating_if_run = False
    elif command_text.startswith("abyss-machine self-awareness investigate ") or command_text.startswith("abyss-machine self-awareness replay ") or command_text.startswith("abyss-machine self-awareness validate "):
        kind = "self_awareness_readmodel_probe"
        scope = "self_awareness"
        mutating_if_run = False
    elif command_text.startswith("abyss-machine stack-bridge sync-static --dry-run"):
        kind = "host_static_bridge_sync_dry_run"
        scope = "host_bridge_review"
        mutating_if_run = False
    elif command_text.startswith("abyss-backup status "):
        kind = "backup_status_probe"
        scope = "backup"
        mutating_if_run = False
    elif command_text.startswith("abyss-machine observability status "):
        kind = "host_observability_status_probe"
        scope = "host_observability"
        mutating_if_run = False
    elif command_text.startswith("abyss-machine nervous retention-plan "):
        kind = "read_model_probe"
        scope = "privacy_retention"
    elif command_text.startswith("abyss-machine memory hotpath-probe "):
        kind = "operator_measurement"
        scope = "measure"
    elif command_text.startswith("abyss-machine nervous quality-audit ") or command_text.startswith("abyss-machine nervous semantic-maintain "):
        kind = "gated_maintenance"
        scope = "maintain"
    else:
        kind = "operator_review"
        scope = "review"
    return {
        "kind": kind,
        "scope": scope,
        "mutating_if_run": mutating_if_run,
        "requires_change_preflight": mutating_if_run,
        "requires_operator": True,
    }


def response_route_from_candidate(schema_prefix: str, candidate: dict[str, Any]) -> dict[str, Any]:
    candidate_id = str(candidate.get("id") or "unknown-candidate")
    command = candidate.get("command")
    command_profile = response_command_profile(str(command) if command is not None else None)
    owner_route = str(candidate.get("owner_route") or "abyss-machine")
    action_mode = str(candidate.get("action_mode") or "operator_review")
    route = {
        "schema": _schema(schema_prefix, "response_route_v1"),
        "id": f"{candidate_id}-response-route",
        "route_id": f"{candidate_id}-response-route",
        "record": "response_route",
        "candidate_id": candidate_id,
        "title": f"Response route for {candidate.get('title') or candidate_id}",
        "severity": candidate.get("severity"),
        "category": candidate.get("category"),
        "owner_route": owner_route,
        "action_mode": action_mode,
        "automatic": False,
        "executes": False,
        "approval": {
            "required": True,
            "route": owner_route,
            "reason": "reaction candidates are not authority to execute; responses only preserve the owner-gated route",
        },
        "suggestion": {
            "command": command,
            "command_profile": command_profile,
            "reason": candidate.get("reason"),
        },
        "evidence": candidate.get("evidence") if isinstance(candidate.get("evidence"), list) else [],
        "policy": {
            "read_model": True,
            "automatic_response": False,
            "executes_commands": False,
            "repo_mutation": False,
            "host_layer_mutates_stack": False,
            "requires_owner_gate": True,
        },
    }
    response_contract = candidate.get("response_contract") if isinstance(candidate.get("response_contract"), dict) else {}
    if candidate.get("category") == "self-awareness" and response_contract:
        route.update({
            "response_contract": response_contract,
            "validated_episode": response_contract.get("validated_episode"),
            "source_event": response_contract.get("source_event"),
            "investigation": response_contract.get("investigation"),
            "replay": response_contract.get("replay"),
            "body_trace": response_contract.get("body_trace"),
            "entity_event_document_context": response_contract.get("entity_event_document_context"),
            "stack_requirement_route": response_contract.get("stack_requirement_route") if isinstance(response_contract.get("stack_requirement_route"), dict) else {},
            "activation_gap_route": response_contract.get("activation_gap_route") if isinstance(response_contract.get("activation_gap_route"), dict) else {},
            "risk": response_contract.get("risk"),
            "blast_radius": response_contract.get("blast_radius"),
            "rollback": response_contract.get("rollback"),
            "runbook_candidate": response_contract.get("runbook_candidate"),
            "evidence_refs": response_contract.get("evidence_refs"),
        })
        route["suggestion"]["runbook_candidate"] = response_contract.get("runbook_candidate")
        route["suggestion"]["acceptance_verifiers"] = nested_get(response_contract, ["runbook_candidate", "acceptance_verifiers"]) or []
        route["policy"]["self_awareness_response_contract_required"] = True
    for key in ("host_owner_gap", "resource_gate", "doctor_warning_route", "memory_hotpath_route", "desktop_compositor_route", "nervous_retention_route", "backup_plane_route", "stack_requirement_route", "activation_gap_route", "safe_next_action", "runbook_candidate", "risk", "blast_radius", "rollback"):
        value = candidate.get(key)
        if isinstance(value, (dict, list)):
            route[key] = value
    if isinstance(candidate.get("host_owner_gap"), dict):
        route["policy"]["host_owner_gap_route"] = True
        route["policy"]["requires_root_operator_approval"] = True
    if isinstance(candidate.get("backup_plane_route"), dict):
        route["policy"]["backup_plane_route"] = True
        route["policy"]["requires_backup_operator_approval"] = True
    return route


def reaction_status_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    candidates: list[dict[str, Any]],
    inputs: dict[str, Any],
    paths: dict[str, Any],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    ordered_candidates = sorted(candidates, key=lambda item: REACTION_SEVERITY_ORDER.get(str(item.get("severity")), 0), reverse=True)
    severity_counts = collections.Counter(str(item.get("severity") or "unknown") for item in ordered_candidates)
    category_counts = collections.Counter(str(item.get("category") or "unknown") for item in ordered_candidates)
    status_value = reaction_overall_status(ordered_candidates)
    return {
        "schema": _schema(schema_prefix, "reactions_status_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "status": status_value,
        "summary": {
            "status": status_value,
            "candidates": len(ordered_candidates),
            "by_severity": dict(sorted(severity_counts.items())),
            "by_category": dict(sorted(category_counts.items())),
            "self_awareness_response_depth": safe_int(metrics.get("self_awareness_response_depth"), 0),
            "working_stack_activation_gap_candidates": safe_int(metrics.get("working_stack_activation_gap_candidates"), 0),
            "stack_requirement_handoff_candidates": safe_int(metrics.get("stack_requirement_handoff_candidates"), 0),
            "memory_hotpath_candidates": safe_int(metrics.get("memory_hotpath_candidates"), 0),
            "doctor_warning_candidates": safe_int(metrics.get("doctor_warning_candidates"), 0),
            "desktop_compositor_pressure_candidates": safe_int(metrics.get("desktop_compositor_pressure_candidates"), 0),
            "nervous_retention_privacy_candidates": safe_int(metrics.get("nervous_retention_privacy_candidates"), 0),
            "abyssvault_backup_plane_candidates": safe_int(metrics.get("abyssvault_backup_plane_candidates"), 0),
            "host_owner_gap_candidates": safe_int(metrics.get("host_owner_gap_candidates"), 0),
            "static_bridge_sync_candidates": sum(1 for item in ordered_candidates if nested_get(item, ["host_owner_gap", "kind"]) == "static_bridge_sync"),
            "observability_permission_candidates": sum(1 for item in ordered_candidates if nested_get(item, ["host_owner_gap", "kind"]) == "observability_manual_collect_permission"),
            "automatic_actions": 0,
        },
        "candidates": ordered_candidates,
        "inputs": inputs,
        "paths": paths,
        "policy": {
            "read_model": True,
            "evidence_first": True,
            "automatic_action": False,
            "automatic_repo_write": False,
            "executes_commands": False,
            "candidates_require_operator_or_owner_route": True,
        },
    }


def response_status_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    routes: list[dict[str, Any]],
    reactions: dict[str, Any],
    heartbeat: dict[str, Any],
    changes: dict[str, Any],
    paths: dict[str, Any],
    metrics: dict[str, Any],
    self_awareness_refs: list[dict[str, Any]],
) -> dict[str, Any]:
    candidates = reactions.get("candidates") if isinstance(reactions.get("candidates"), list) else []
    severity_counts = collections.Counter(str(item.get("severity") or "unknown") for item in routes)
    category_counts = collections.Counter(str(item.get("category") or "unknown") for item in routes)
    self_awareness_routes = [item for item in routes if isinstance(item, dict) and item.get("category") == "self-awareness"]
    host_owner_gap_routes = [item for item in routes if isinstance(item, dict) and isinstance(item.get("host_owner_gap"), dict)]
    mutating_if_run = [
        str(item.get("id"))
        for item in routes
        if bool(nested_get(item, ["suggestion", "command_profile", "mutating_if_run"]))
    ]
    body_trace_route_ids = [str(item) for item in as_list(metrics.get("self_awareness_body_trace_route_ids")) if str(item)]
    entity_event_document_route_ids = [
        str(item)
        for item in as_list(metrics.get("self_awareness_entity_event_document_route_ids"))
        if str(item)
    ]
    status_value = reaction_overall_status(routes)
    return {
        "schema": _schema(schema_prefix, "responses_status_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "status": status_value,
        "summary": {
            "status": status_value,
            "routes": len(routes),
            "reaction_status": nested_get(reactions, ["summary", "status"]) or reactions.get("status"),
            "reaction_candidates": len(candidates),
            "by_severity": dict(sorted(severity_counts.items())),
            "by_category": dict(sorted(category_counts.items())),
            "approval_required": len(routes),
            "self_awareness_response_routes": len(self_awareness_routes),
            "self_awareness_response_depth": safe_int(metrics.get("self_awareness_response_depth"), 0),
            "self_awareness_body_trace_routes": len(body_trace_route_ids),
            "self_awareness_body_trace_missing": len(self_awareness_routes) - len(body_trace_route_ids),
            "self_awareness_entity_event_document_routes": len(entity_event_document_route_ids),
            "self_awareness_entity_event_document_missing": len(self_awareness_routes) - len(entity_event_document_route_ids),
            "working_stack_activation_gap_routes": safe_int(metrics.get("working_stack_activation_gap_routes"), 0),
            "stack_requirement_handoff_routes": safe_int(metrics.get("stack_requirement_handoff_routes"), 0),
            "memory_hotpath_routes": safe_int(metrics.get("memory_hotpath_routes"), 0),
            "doctor_warning_routes": safe_int(metrics.get("doctor_warning_routes"), 0),
            "desktop_compositor_pressure_routes": safe_int(metrics.get("desktop_compositor_pressure_routes"), 0),
            "nervous_retention_privacy_routes": safe_int(metrics.get("nervous_retention_privacy_routes"), 0),
            "abyssvault_backup_plane_routes": safe_int(metrics.get("abyssvault_backup_plane_routes"), 0),
            "host_owner_gap_routes": len(host_owner_gap_routes),
            "static_bridge_sync_routes": sum(1 for item in host_owner_gap_routes if nested_get(item, ["host_owner_gap", "kind"]) == "static_bridge_sync"),
            "observability_permission_routes": sum(1 for item in host_owner_gap_routes if nested_get(item, ["host_owner_gap", "kind"]) == "observability_manual_collect_permission"),
            "automatic_responses": 0,
            "routes_with_mutating_command_if_run": len(mutating_if_run),
            "active_changes": int(nested_get(changes, ["summary", "active_records"]) or 0),
        },
        "routes": routes,
        "self_awareness": {
            "schema": _schema(schema_prefix, "responses_self_awareness_body_trace_v1"),
            "routes": len(self_awareness_routes),
            "body_trace_routes": len(body_trace_route_ids),
            "body_trace_missing": len(self_awareness_routes) - len(body_trace_route_ids),
            "entity_event_document_routes": len(entity_event_document_route_ids),
            "entity_event_document_missing": len(self_awareness_routes) - len(entity_event_document_route_ids),
            "route_ids": [str(item.get("id")) for item in self_awareness_routes if item.get("id")],
            "body_trace_route_ids": body_trace_route_ids,
            "entity_event_document_route_ids": entity_event_document_route_ids,
            "evidence_refs": self_awareness_refs,
            "policy": {
                "read_only": True,
                "automatic_response": False,
                "executes_commands": False,
                "host_layer_mutates_stack": False,
            },
        },
        "inputs": {
            "heartbeats": {
                "path": metrics.get("heartbeats_path"),
                "ok": heartbeat.get("ok"),
                "status": heartbeat.get("status"),
                "generated_at": heartbeat.get("generated_at"),
            },
            "reactions": {
                "path": metrics.get("reactions_path"),
                "ok": reactions.get("ok"),
                "status": nested_get(reactions, ["summary", "status"]) or reactions.get("status"),
                "generated_at": reactions.get("generated_at"),
            },
            "changes": {
                "path": metrics.get("changes_path"),
                "ok": changes.get("ok"),
                "active_records": nested_get(changes, ["summary", "active_records"]),
                "generated_at": changes.get("generated_at"),
            },
        },
        "paths": paths,
        "policy": {
            "read_model": True,
            "evidence_first": True,
            "automatic_action": False,
            "automatic_response": False,
            "automatic_repo_write": False,
            "executes_commands": False,
            "routes_require_operator_or_owner_gate": True,
            "commands_are_suggestions_only": True,
        },
    }

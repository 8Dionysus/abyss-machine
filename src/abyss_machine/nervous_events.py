from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import Any, Callable


SEVERITY_RANK = {
    "info": 0,
    "notice": 1,
    "watch": 2,
    "warning": 3,
    "critical": 4,
}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def nested_get(data: Any, path: list[str]) -> Any:
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def parse_time(value: Any) -> dt.datetime | None:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.datetime.now().astimezone().tzinfo)
    return parsed


def severity_max(values: list[str]) -> str:
    if not values:
        return "info"
    return max(values, key=lambda item: SEVERITY_RANK.get(str(item), 0))


def find_fact(record: dict[str, Any], name: str) -> dict[str, Any] | None:
    facts = record.get("facts") if isinstance(record.get("facts"), list) else []
    for fact in facts:
        if isinstance(fact, dict) and fact.get("name") == name:
            return fact
    return None


def systemd_facts_from_snapshot(record: dict[str, Any]) -> list[dict[str, Any]]:
    facts = record.get("facts") if isinstance(record.get("facts"), list) else []
    return [fact for fact in facts if isinstance(fact, dict) and fact.get("name") == "systemd_unit"]


def default_fact_source_id(fact: dict[str, Any]) -> str:
    source = fact.get("source") if isinstance(fact.get("source"), dict) else {}
    return str(fact.get("source_id") or source.get("id") or fact.get("name") or "unknown")


def compact_json(value: Any, max_chars: int = 6000) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    if len(text) > max_chars:
        return text[: max(0, max_chars - 3)] + "..."
    return text


def fact_evidence(fact: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(fact, dict):
        return None
    if fact.get("name") == "systemd_unit":
        return {
            "kind": "systemd_metadata",
            "scope": fact.get("scope"),
            "unit": fact.get("unit"),
            "observed_at": fact.get("observed_at"),
        }
    source = fact.get("source") if isinstance(fact.get("source"), dict) else {}
    return {
        "kind": "file_fact",
        "fact_name": fact.get("name"),
        "path": fact.get("path") or source.get("path"),
        "source_sha256": source.get("sha256"),
        "source_read_at": source.get("read_at"),
        "fact_generated_at": fact.get("generated_at") or fact.get("updated_at"),
    }


def snapshot_evidence(item: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "fact_snapshot",
        "path": item.get("path"),
        "line": item.get("line"),
        "record_sha256": item.get("record_sha256"),
        "source_sha256": item.get("source_sha256"),
        "generated_at": record.get("generated_at"),
        "schema": record.get("schema"),
    }


def event_record(
    *,
    event_type: str,
    category: str,
    observed_at: str | None,
    title: str,
    summary: str,
    severity: str,
    confidence: str,
    source_ids: list[str],
    evidence: list[dict[str, Any] | None],
    payload: dict[str, Any] | None = None,
    subject: str | None = None,
    sensitivity: str = "machine_metadata",
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str | None = None,
) -> dict[str, Any]:
    subject = subject or title
    safe_evidence = [item for item in evidence if isinstance(item, dict)]
    identity = json.dumps({
        "event_type": event_type,
        "category": category,
        "observed_at": observed_at,
        "subject": subject,
        "evidence": safe_evidence,
    }, ensure_ascii=False, sort_keys=True, default=str)
    event_id = "evt-" + hashlib.sha256(identity.encode("utf-8", errors="replace")).hexdigest()[:24]
    safe_source_ids = sorted({str(source_id) for source_id in source_ids if source_id})
    return {
        "schema": f"{schema_prefix}_nervous_event_v1",
        "version": version,
        "event_id": event_id,
        "generated_at": generated_at or now_iso(),
        "observed_at": observed_at,
        "event_type": event_type,
        "category": category,
        "subject": subject,
        "severity": severity,
        "confidence": confidence,
        "sensitivity": sensitivity,
        "source_ids": safe_source_ids,
        "title": title,
        "summary": summary,
        "evidence": safe_evidence,
        "payload": payload or {},
        "derived_by": "nervous_events_build_v1",
        "raw_private_content": False,
        "automatic_action": False,
    }


def storage_event(
    item: dict[str, Any],
    record: dict[str, Any],
    previous: dict[str, Any] | None,
    *,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str | None = None,
) -> list[dict[str, Any]]:
    fact = find_fact(record, "storage_latest")
    if not isinstance(fact, dict):
        return []
    summary = fact.get("summary") if isinstance(fact.get("summary"), dict) else {}
    root_used = summary.get("root_used_percent")
    srv_used = summary.get("srv_used_percent")
    severity = "info"
    try:
        root_float = float(root_used)
        if root_float >= 90.0:
            severity = "critical"
        elif root_float >= 80.0:
            severity = "warning"
        elif root_float >= 75.0:
            severity = "watch"
    except (TypeError, ValueError):
        root_float = None
    events: list[dict[str, Any]] = []
    if severity != "info":
        events.append(event_record(
            event_type="storage.pressure",
            category="storage",
            observed_at=record.get("generated_at"),
            title=f"root storage pressure {root_used}%",
            summary=f"Root filesystem is at {root_used}% used; /srv is at {srv_used}% used.",
            severity=severity,
            confidence="high",
            source_ids=["abyss_machine_facts"],
            evidence=[snapshot_evidence(item, record), fact_evidence(fact)],
            payload={
                "root_used_percent": root_used,
                "srv_used_percent": srv_used,
                "root_warning": summary.get("root_warning"),
                "root_critical": summary.get("root_critical"),
                "podman_migration_status": summary.get("podman_migration_status"),
            },
            subject="root_storage_pressure",
            schema_prefix=schema_prefix,
            version=version,
            generated_at=generated_at,
        ))
    previous_apply = previous.get("apply_latest") if isinstance(previous, dict) else None
    current_apply = summary.get("apply_latest")
    if current_apply and previous_apply and current_apply != previous_apply:
        events.append(event_record(
            event_type="storage.cleanup_apply_changed",
            category="storage",
            observed_at=record.get("generated_at"),
            title="storage cleanup/apply evidence changed",
            summary=f"Latest storage apply evidence moved from {previous_apply} to {current_apply}.",
            severity="notice",
            confidence="medium",
            source_ids=["abyss_machine_facts"],
            evidence=[snapshot_evidence(item, record), fact_evidence(fact)],
            payload={"previous_apply_latest": previous_apply, "apply_latest": current_apply},
            subject="storage_apply_latest",
            schema_prefix=schema_prefix,
            version=version,
            generated_at=generated_at,
        ))
    return events


def thermal_episode_float(data: dict[str, Any], key: str, default: float) -> float:
    value = data.get(key)
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


def thermal_event_thresholds(thresholds: dict[str, Any] | None = None) -> dict[str, float]:
    data = thresholds if isinstance(thresholds, dict) else {}
    active_range = data.get("thin_laptop_active_range_c")
    active_low = 100.0
    active_high = 105.0
    if isinstance(active_range, list) and len(active_range) >= 2:
        try:
            active_low = float(active_range[0])
            active_high = float(active_range[1])
        except (TypeError, ValueError):
            active_low = 100.0
            active_high = 105.0
    warm = thermal_episode_float(data, "warm_temperature_c", 80.0)
    hot = thermal_episode_float(data, "hot_temperature_c", 106.0)
    critical = thermal_episode_float(data, "critical_temperature_c", 109.0)
    watch = thermal_episode_float(data, "watch_above_c", active_high)
    hard = thermal_episode_float(data, "hard_emergency_temperature_c", critical)
    if active_high < active_low:
        active_high = active_low
    if watch < active_low:
        watch = active_high
    if hot < watch:
        hot = watch
    if critical < hot:
        critical = hot
    if hard < critical:
        hard = critical
    return {
        "warm_c": warm,
        "active_low_c": active_low,
        "active_high_c": active_high,
        "watch_c": watch,
        "hot_c": hot,
        "critical_c": critical,
        "hard_emergency_c": hard,
    }


def thermal_event_classification(
    temp_float: float | None,
    raw_thermal_class: str,
    thresholds: dict[str, float] | None = None,
) -> tuple[str, str, dict[str, float]]:
    thermal_thresholds = thresholds if isinstance(thresholds, dict) else thermal_event_thresholds()
    raw_class = str(raw_thermal_class or "unknown").strip().lower()
    if temp_float is None:
        severity = "notice" if raw_class not in {"ok", "green", "unknown"} else "info"
        return raw_class or "unknown", severity, thermal_thresholds
    if temp_float >= thermal_thresholds["critical_c"]:
        return "critical", "critical", thermal_thresholds
    if temp_float >= thermal_thresholds["hot_c"]:
        return "hot", "warning", thermal_thresholds
    if temp_float >= thermal_thresholds["watch_c"]:
        return "watch", "watch", thermal_thresholds
    if temp_float >= thermal_thresholds["active_low_c"]:
        return "active_high", "notice", thermal_thresholds
    if temp_float >= thermal_thresholds["warm_c"]:
        return "warm", "watch", thermal_thresholds
    return "ok", "info", thermal_thresholds


def power_thermal_events(
    item: dict[str, Any],
    record: dict[str, Any],
    previous_power_token: tuple[Any, ...] | None,
    previous_thermal_class: str | None,
    *,
    thresholds: dict[str, float] | None = None,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str | None = None,
) -> tuple[list[dict[str, Any]], tuple[Any, ...] | None, str | None]:
    fact = find_fact(record, "observability_thermal_battery_latest")
    if not isinstance(fact, dict):
        return [], previous_power_token, previous_thermal_class
    events: list[dict[str, Any]] = []
    classes = fact.get("class") if isinstance(fact.get("class"), dict) else {}
    battery = fact.get("battery") if isinstance(fact.get("battery"), dict) else {}
    thermal = fact.get("thermal") if isinstance(fact.get("thermal"), dict) else {}
    capacity = battery.get("capacity_percent")
    ac_online = battery.get("ac_online")
    status = battery.get("status")
    try:
        capacity_int = int(capacity)
    except (TypeError, ValueError):
        capacity_int = None
    power_token = (bool(ac_online), status, None if capacity_int is None else capacity_int // 10)
    if previous_power_token is None or power_token[:2] != previous_power_token[:2] or (capacity_int is not None and capacity_int <= 30 and power_token != previous_power_token):
        severity = "warning" if capacity_int is not None and capacity_int <= 15 else "watch" if capacity_int is not None and capacity_int <= 30 else "notice"
        events.append(event_record(
            event_type="power.state",
            category="power",
            observed_at=record.get("generated_at"),
            title=f"power state {status} capacity={capacity} ac={ac_online}",
            summary=f"Battery status is {status}, capacity is {capacity}%, AC online is {ac_online}.",
            severity=severity,
            confidence="high",
            source_ids=["abyss_machine_facts"],
            evidence=[snapshot_evidence(item, record), fact_evidence(fact)],
            payload={
                "ac_online": ac_online,
                "status": status,
                "capacity_percent": capacity,
                "power_w": battery.get("power_w"),
                "health_percent": battery.get("health_percent"),
            },
            subject="power_state",
            schema_prefix=schema_prefix,
            version=version,
            generated_at=generated_at,
        ))
    raw_thermal_class = str(classes.get("thermal") or "unknown")
    temp_max = thermal.get("temperature_c_max")
    try:
        temp_float = float(temp_max)
    except (TypeError, ValueError):
        temp_float = None
    thermal_class, thermal_severity, thermal_thresholds = thermal_event_classification(temp_float, raw_thermal_class, thresholds)
    if thermal_severity != "info" or (previous_thermal_class and thermal_class != previous_thermal_class):
        events.append(event_record(
            event_type="thermal.state",
            category="thermal",
            observed_at=record.get("generated_at"),
            title=f"thermal state {thermal_class} max={temp_max}C",
            summary=(
                f"Thermal policy class is {thermal_class}; max observed sensor temperature is {temp_max}C; "
                f"active_high={thermal_thresholds['active_high_c']}C hot={thermal_thresholds['hot_c']}C "
                f"critical={thermal_thresholds['critical_c']}C."
            ),
            severity=thermal_severity,
            confidence="medium",
            source_ids=["abyss_machine_facts"],
            evidence=[snapshot_evidence(item, record), fact_evidence(fact)],
            payload={
                "thermal_class": thermal_class,
                "raw_thermal_class": raw_thermal_class,
                "temperature_c_max": temp_max,
                "thresholds": thermal_thresholds,
                "hottest": thermal.get("hottest", [])[:8] if isinstance(thermal.get("hottest"), list) else [],
            },
            subject="thermal_state",
            schema_prefix=schema_prefix,
            version=version,
            generated_at=generated_at,
        ))
    return events, power_token, thermal_class


def process_ai_events(
    item: dict[str, Any],
    record: dict[str, Any],
    previous_tokens: dict[str, Any],
    *,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    events: list[dict[str, Any]] = []
    process_fact = find_fact(record, "process_latest")
    if isinstance(process_fact, dict):
        summary = process_fact.get("summary") if isinstance(process_fact.get("summary"), dict) else {}
        token = (
            summary.get("ai_runtime_processes"),
            summary.get("container_processes"),
            summary.get("development_processes"),
        )
        if previous_tokens.get("process") != token and any(value for value in token if isinstance(value, int) and value > 0):
            events.append(event_record(
                event_type="process.snapshot_summary",
                category="processes",
                observed_at=record.get("generated_at"),
                title="process snapshot workload shape changed",
                summary=(
                    f"Processes={summary.get('processes')}, threads={summary.get('threads')}, "
                    f"development={summary.get('development_processes')}, ai_runtime={summary.get('ai_runtime_processes')}, "
                    f"containers={summary.get('container_processes')}."
                ),
                severity="notice",
                confidence="medium",
                source_ids=["abyss_machine_facts"],
                evidence=[snapshot_evidence(item, record), fact_evidence(process_fact)],
                payload=summary,
                subject="process_snapshot_summary",
                schema_prefix=schema_prefix,
                version=version,
                generated_at=generated_at,
            ))
        previous_tokens["process"] = token
    workload_fact = find_fact(record, "ai_workload_latest")
    if isinstance(workload_fact, dict):
        summary = workload_fact.get("summary") if isinstance(workload_fact.get("summary"), dict) else {}
        declared = summary.get("by_declared_class") if isinstance(summary.get("by_declared_class"), dict) else {}
        token = (summary.get("records"), declared.get("heavy"), declared.get("medium"), declared.get("light"))
        if previous_tokens.get("ai_workload") != token and summary.get("records"):
            events.append(event_record(
                event_type="ai.workload_catalog",
                category="ai",
                observed_at=record.get("generated_at"),
                title="AI workload catalog observed",
                summary=(
                    f"AI workload stats contain {summary.get('records')} records across {summary.get('groups')} groups; "
                    f"heavy={declared.get('heavy')} medium={declared.get('medium')} light={declared.get('light')}."
                ),
                severity="notice",
                confidence="high",
                source_ids=["abyss_machine_facts"],
                evidence=[snapshot_evidence(item, record), fact_evidence(workload_fact)],
                payload=summary,
                subject="ai_workload_catalog",
                schema_prefix=schema_prefix,
                version=version,
                generated_at=generated_at,
            ))
        previous_tokens["ai_workload"] = token
    return events, previous_tokens


def systemd_events(
    item: dict[str, Any],
    record: dict[str, Any],
    previous_units: dict[str, tuple[Any, ...]],
    *,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, tuple[Any, ...]]]:
    events: list[dict[str, Any]] = []
    for fact in systemd_facts_from_snapshot(record):
        state = fact.get("state") if isinstance(fact.get("state"), dict) else {}
        unit = str(fact.get("unit") or state.get("name") or "unknown")
        token = (state.get("active"), state.get("enabled"), bool(state.get("is_active")), bool(state.get("is_enabled")))
        previous = previous_units.get(unit)
        if previous is None or previous != token:
            active = state.get("active")
            enabled = state.get("enabled")
            severity = "warning" if enabled in {"enabled", "static"} and active in {"failed"} else "notice" if active == "active" or enabled in {"enabled", "static"} else "info"
            events.append(event_record(
                event_type="systemd.unit_state",
                category="systemd",
                observed_at=fact.get("observed_at") or record.get("generated_at"),
                title=f"{unit} {active}/{enabled}",
                summary=f"{fact.get('scope')} unit {unit} is active={active}, enabled={enabled}.",
                severity=severity,
                confidence="high",
                source_ids=["systemd_metadata"],
                evidence=[snapshot_evidence(item, record), fact_evidence(fact)],
                payload={"scope": fact.get("scope"), "unit": unit, "state": state, "previous": previous},
                subject=f"systemd:{unit}",
                schema_prefix=schema_prefix,
                version=version,
                generated_at=generated_at,
            ))
        previous_units[unit] = token
    return events, previous_units


def private_capture_events(
    item: dict[str, Any],
    record: dict[str, Any],
    *,
    fact_source_id: Callable[[dict[str, Any]], str] = default_fact_source_id,
    deferred_source_ids: set[str] | None = None,
    compact_json_func: Callable[..., str] = compact_json,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str | None = None,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    summaries = {
        "filesystem_metadata": ("capture.filesystem_metadata", "machine", "filesystem metadata snapshot"),
        "git_explicit_repositories": ("capture.git_repositories", "machine", "git repository status snapshot"),
        "podman_metadata": ("capture.podman_metadata", "machine", "podman metadata snapshot"),
        "browser_active_tab": ("capture.browser_recent_history", "activity", "browser recent history snapshot"),
        "terminal_stdout_stderr": ("capture.terminal_activity", "activity", "terminal activity snapshot"),
        "clipboard": ("capture.clipboard", "activity", "clipboard snapshot"),
        "screenshots": ("capture.screenshot", "activity", "screenshot artifact snapshot"),
        "audio_transcript_autolog": ("capture.audio_transcript", "activity", "dictation transcript snapshot"),
    }
    deferred = deferred_source_ids or set()
    for fact in record.get("facts", []) if isinstance(record.get("facts"), list) else []:
        if not isinstance(fact, dict):
            continue
        source_id = fact_source_id(fact)
        spec = summaries.get(source_id)
        if spec is None:
            continue
        event_type, category, label = spec
        summary = fact.get("summary") if isinstance(fact.get("summary"), dict) else {}
        ok = bool(fact.get("ok", True))
        severity = "info" if ok else "watch"
        sensitivity = str(fact.get("sensitivity") or "machine_metadata")
        if source_id in deferred and sensitivity == "machine_metadata":
            sensitivity = "local_private_redacted"
        events.append(event_record(
            event_type=event_type,
            category=category,
            observed_at=fact.get("observed_at") or record.get("generated_at"),
            title=label,
            summary=f"{label}: ok={ok}, summary={compact_json_func(summary, max_chars=900)}",
            severity=severity,
            confidence="high" if ok else "medium",
            source_ids=[source_id],
            evidence=[snapshot_evidence(item, record), fact_evidence(fact)],
            payload={
                "fact_name": fact.get("name"),
                "source_id": source_id,
                "summary": summary,
                "coverage": fact.get("coverage"),
                "sensitivity": sensitivity,
            },
            subject=f"capture:{source_id}",
            sensitivity=sensitivity,
            schema_prefix=schema_prefix,
            version=version,
            generated_at=generated_at,
        ))
    return events


def events_from_fact_records(
    items: list[dict[str, Any]],
    *,
    thresholds: dict[str, float] | None = None,
    fact_source_id: Callable[[dict[str, Any]], str] = default_fact_source_id,
    deferred_source_ids: set[str] | None = None,
    compact_json_func: Callable[..., str] = compact_json,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    event_generated_at = generated_at or now_iso()
    events: list[dict[str, Any]] = []
    previous_storage: dict[str, Any] | None = None
    previous_power_token: tuple[Any, ...] | None = None
    previous_thermal_class: str | None = None
    previous_units: dict[str, tuple[Any, ...]] = {}
    previous_tokens: dict[str, Any] = {}
    for item in items:
        record = item.get("record") if isinstance(item.get("record"), dict) else {}
        if record.get("schema") != f"{schema_prefix}_nervous_fact_snapshot_v1":
            continue
        capture = record.get("capture") if isinstance(record.get("capture"), dict) else {}
        privacy = record.get("privacy") if isinstance(record.get("privacy"), dict) else {}
        summary = record.get("summary") if isinstance(record.get("summary"), dict) else {}
        events.append(event_record(
            event_type="nervous.snapshot_recorded",
            category="nervous",
            observed_at=record.get("generated_at"),
            title=f"nervous snapshot {record.get('generated_at')}",
            summary=f"Fact snapshot captured {summary.get('facts')} facts and skipped {summary.get('skipped')} sources.",
            severity="info",
            confidence="high",
            source_ids=list(capture.get("sources", [])) if isinstance(capture.get("sources"), list) else ["abyss_machine_facts"],
            evidence=[snapshot_evidence(item, record)],
            payload={
                "capture": {
                    "trigger": capture.get("trigger"),
                    "manual": capture.get("manual"),
                    "timer": capture.get("timer"),
                    "heartbeat": capture.get("heartbeat"),
                },
                "privacy": {
                    "global_pause": privacy.get("global_pause"),
                    "private_mode": privacy.get("private_mode"),
                },
                "summary": summary,
            },
            subject="nervous_snapshot",
            schema_prefix=schema_prefix,
            version=version,
            generated_at=event_generated_at,
        ))
        storage_fact = find_fact(record, "storage_latest")
        storage_summary = storage_fact.get("summary") if isinstance(storage_fact, dict) and isinstance(storage_fact.get("summary"), dict) else None
        events.extend(storage_event(item, record, previous_storage, schema_prefix=schema_prefix, version=version, generated_at=event_generated_at))
        previous_storage = storage_summary if isinstance(storage_summary, dict) else previous_storage
        thermal_events, previous_power_token, previous_thermal_class = power_thermal_events(
            item,
            record,
            previous_power_token,
            previous_thermal_class,
            thresholds=thresholds,
            schema_prefix=schema_prefix,
            version=version,
            generated_at=event_generated_at,
        )
        events.extend(thermal_events)
        process_events, previous_tokens = process_ai_events(
            item,
            record,
            previous_tokens,
            schema_prefix=schema_prefix,
            version=version,
            generated_at=event_generated_at,
        )
        events.extend(process_events)
        systemd_event_items, previous_units = systemd_events(
            item,
            record,
            previous_units,
            schema_prefix=schema_prefix,
            version=version,
            generated_at=event_generated_at,
        )
        events.extend(systemd_event_items)
        events.extend(private_capture_events(
            item,
            record,
            fact_source_id=fact_source_id,
            deferred_source_ids=deferred_source_ids,
            compact_json_func=compact_json_func,
            schema_prefix=schema_prefix,
            version=version,
            generated_at=event_generated_at,
        ))

    deduped: dict[str, dict[str, Any]] = {}
    for event in events:
        deduped[str(event["event_id"])] = event
    final_events = sorted(deduped.values(), key=lambda item: (item.get("observed_at") or "", item.get("event_id") or ""))
    categories = sorted({str(event.get("category")) for event in final_events})
    severities = sorted({str(event.get("severity")) for event in final_events})
    return final_events, {
        "input_snapshots": len(items),
        "events": len(final_events),
        "by_category": {category: sum(1 for event in final_events if event.get("category") == category) for category in categories},
        "by_severity": {severity: sum(1 for event in final_events if event.get("severity") == severity) for severity in severities},
    }


def events_build_refused_result(
    *,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str | None = None,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_nervous_events_build_v1",
        "version": version,
        "generated_at": generated_at or now_iso(),
        "ok": False,
        "refused": True,
        "error": "global_pause is active; event build did not touch derived event files",
    }


def event_latest_projection(event: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(event, dict):
        return None
    return {
        "event_id": event.get("event_id"),
        "observed_at": event.get("observed_at"),
        "event_type": event.get("event_type"),
        "category": event.get("category"),
        "severity": event.get("severity"),
        "title": event.get("title"),
    }


def events_build_document(
    *,
    items: list[dict[str, Any]],
    parse_errors: list[dict[str, Any]],
    events: list[dict[str, Any]],
    event_summary: dict[str, Any],
    write_report: dict[str, Any],
    facts_root: str,
    latest_path: str,
    daily_glob: str,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str | None = None,
) -> dict[str, Any]:
    latest_event = events[-1] if events else None
    return {
        "schema": f"{schema_prefix}_nervous_events_build_v1",
        "version": version,
        "generated_at": generated_at or now_iso(),
        "ok": not parse_errors and int(write_report.get("error_count") or 0) == 0,
        "source": {
            "facts_root": facts_root,
            "records_seen": len(items),
            "parse_errors": len(parse_errors),
        },
        "summary": event_summary,
        "write": write_report,
        "latest_event": event_latest_projection(latest_event),
        "paths": {
            "latest": latest_path,
            "daily_glob": daily_glob,
        },
        "parse_errors": parse_errors[:20],
        "policy": {
            "derived": True,
            "raw_private_content": False,
            "automatic_action": False,
            "private_sources_allowed_when_policy_enabled": True,
        },
    }


def _add_check(checks: list[dict[str, Any]], level: str, key: str, message: str, details: dict[str, Any] | None = None) -> None:
    item: dict[str, Any] = {"level": level, "key": key, "message": message}
    if details is not None:
        item["details"] = details
    checks.append(item)


def events_validate_document(
    *,
    latest: Any,
    latest_error: Any,
    items: list[dict[str, Any]],
    parse_errors: list[dict[str, Any]],
    allowed_sources: set[str],
    latest_path: str,
    daily_glob: str,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    _add_check(checks, "ok" if isinstance(latest, dict) else "fail", "latest", "events latest exists", {"path": latest_path, "error": latest_error})
    event_ids: set[str] = set()
    duplicates: list[str] = []
    missing: list[dict[str, Any]] = []
    forbidden_hits: list[dict[str, Any]] = []
    for item in items:
        record = item.get("record") if isinstance(item.get("record"), dict) else {}
        event_id = str(record.get("event_id") or "")
        if event_id in event_ids:
            duplicates.append(event_id)
        event_ids.add(event_id)
        for key in ("schema", "event_id", "observed_at", "event_type", "category", "severity", "confidence", "sensitivity", "title", "summary"):
            if not record.get(key):
                missing.append({"path": item.get("path"), "line": item.get("line"), "event_id": event_id, "missing": key})
        if record.get("schema") != f"{schema_prefix}_nervous_event_v1":
            missing.append({"path": item.get("path"), "line": item.get("line"), "event_id": event_id, "missing": "expected_event_schema"})
        source_ids = set(record.get("source_ids", [])) if isinstance(record.get("source_ids"), list) else set()
        if source_ids - allowed_sources or record.get("raw_private_content") is not False:
            forbidden_hits.append({"path": item.get("path"), "line": item.get("line"), "event_id": event_id, "source_ids": sorted(source_ids), "raw_private_content": record.get("raw_private_content")})
    _add_check(checks, "ok" if not parse_errors else "fail", "jsonl_parse", "event JSONL parses", {"parse_errors": parse_errors[:20], "parse_error_count": len(parse_errors)})
    _add_check(checks, "ok" if not duplicates else "fail", "unique_event_ids", "event ids are unique", {"duplicates": duplicates[:20], "duplicate_count": len(duplicates)})
    _add_check(checks, "ok" if not missing else "fail", "required_fields", "event records have required fields", {"missing": missing[:20], "missing_count": len(missing)})
    _add_check(checks, "ok" if not forbidden_hits else "fail", "privacy_sources", "events contain only enabled allowed sources and no raw private content", {"forbidden_hits": forbidden_hits[:20], "forbidden_count": len(forbidden_hits)})
    _add_check(checks, "ok" if items else "warn", "event_count", "event records exist", {"events": len(items)})
    fails = sum(1 for item in checks if item["level"] == "fail")
    warnings = sum(1 for item in checks if item["level"] == "warn")
    return {
        "schema": f"{schema_prefix}_nervous_events_validate_v1",
        "version": version,
        "generated_at": generated_at or now_iso(),
        "ok": fails == 0,
        "checks": checks,
        "summary": {
            "fails": fails,
            "warnings": warnings,
            "checks": len(checks),
            "events": len(items),
            "parse_errors": len(parse_errors),
        },
        "paths": {
            "latest": latest_path,
            "daily_glob": daily_glob,
        },
    }


def episode_record(
    category: str,
    events: list[dict[str, Any]],
    day: str,
    *,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str | None = None,
) -> dict[str, Any]:
    severities = [str(event.get("severity") or "info") for event in events]
    severity = severity_max(severities)
    observed_times = [event.get("observed_at") for event in events if event.get("observed_at")]
    start_at = min(observed_times) if observed_times else None
    end_at = max(observed_times) if observed_times else None
    event_ids = [str(event.get("event_id")) for event in events if event.get("event_id")]
    identity = json.dumps({"category": category, "day": day, "event_ids": event_ids}, ensure_ascii=False, sort_keys=True)
    episode_id = "eps-" + hashlib.sha256(identity.encode("utf-8", errors="replace")).hexdigest()[:24]
    event_types = sorted({str(event.get("event_type")) for event in events if event.get("event_type")})
    summary = (
        f"{category} episode for {day}: {len(events)} events, "
        f"highest severity {severity}, window {start_at} .. {end_at}, "
        f"event types: {', '.join(event_types[:8])}."
    )
    source_ids = sorted({str(source_id) for event in events for source_id in (event.get("source_ids") if isinstance(event.get("source_ids"), list) else [])})
    sensitivity = "machine_metadata"
    if any(event.get("sensitivity") != "machine_metadata" for event in events):
        sensitivity = "mixed_machine_metadata"
    return {
        "schema": f"{schema_prefix}_nervous_episode_v1",
        "version": version,
        "episode_id": episode_id,
        "generated_at": generated_at or now_iso(),
        "start_at": start_at,
        "end_at": end_at,
        "day": day,
        "category": category,
        "severity": severity,
        "confidence": "medium" if len(events) == 1 else "high",
        "sensitivity": sensitivity,
        "source_ids": source_ids,
        "title": f"{category} episode {day}",
        "summary": summary,
        "event_count": len(events),
        "event_ids": event_ids,
        "event_types": event_types,
        "evidence": [
            {
                "event_id": event.get("event_id"),
                "observed_at": event.get("observed_at"),
                "event_type": event.get("event_type"),
                "severity": event.get("severity"),
                "title": event.get("title"),
            }
            for event in events[:50]
        ],
        "derived_by": "nervous_episodes_build_v1",
        "raw_private_content": False,
        "automatic_action": False,
    }


def episodes_from_events(
    events: list[dict[str, Any]],
    *,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str | None = None,
    now: dt.datetime | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    episode_generated_at = generated_at or now_iso()
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for event in events:
        observed = parse_time(event.get("observed_at")) or parse_time(event.get("generated_at")) or now or dt.datetime.now(dt.timezone.utc).astimezone()
        day = observed.astimezone().strftime("%Y-%m-%d")
        category = str(event.get("category") or "misc")
        grouped.setdefault((day, category), []).append(event)
    episodes = [
        episode_record(
            category,
            sorted(items, key=lambda event: (event.get("observed_at") or "", event.get("event_id") or "")),
            day,
            schema_prefix=schema_prefix,
            version=version,
            generated_at=episode_generated_at,
        )
        for (day, category), items in sorted(grouped.items())
    ]
    episodes.sort(key=lambda item: (item.get("start_at") or "", item.get("episode_id") or ""))
    categories = sorted({str(episode.get("category")) for episode in episodes})
    severities = sorted({str(episode.get("severity")) for episode in episodes})
    return episodes, {
        "input_events": len(events),
        "episodes": len(episodes),
        "by_category": {category: sum(1 for episode in episodes if episode.get("category") == category) for category in categories},
        "by_severity": {severity: sum(1 for episode in episodes if episode.get("severity") == severity) for severity in severities},
    }


def episodes_build_refused_result(
    *,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str | None = None,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_nervous_episodes_build_v1",
        "version": version,
        "generated_at": generated_at or now_iso(),
        "ok": False,
        "refused": True,
        "error": "global_pause is active; episode build did not touch derived episode files",
    }


def event_records_from_items(items: list[dict[str, Any]], *, schema_prefix: str = "abyss_machine") -> list[dict[str, Any]]:
    return [
        item["record"] for item in items
        if isinstance(item.get("record"), dict) and item["record"].get("schema") == f"{schema_prefix}_nervous_event_v1"
    ]


def episode_latest_projection(episode: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(episode, dict):
        return None
    return {
        "episode_id": episode.get("episode_id"),
        "start_at": episode.get("start_at"),
        "end_at": episode.get("end_at"),
        "category": episode.get("category"),
        "severity": episode.get("severity"),
        "title": episode.get("title"),
    }


def episodes_build_document(
    *,
    event_items: list[dict[str, Any]],
    parse_errors: list[dict[str, Any]],
    events_refresh: dict[str, Any] | None,
    episodes: list[dict[str, Any]],
    episode_summary: dict[str, Any],
    write_report: dict[str, Any],
    events_root: str,
    latest_path: str,
    daily_glob: str,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str | None = None,
) -> dict[str, Any]:
    latest_episode = episodes[-1] if episodes else None
    return {
        "schema": f"{schema_prefix}_nervous_episodes_build_v1",
        "version": version,
        "generated_at": generated_at or now_iso(),
        "ok": not parse_errors and int(write_report.get("error_count") or 0) == 0 and (events_refresh is None or bool(events_refresh.get("ok"))),
        "source": {
            "events_root": events_root,
            "records_seen": len(event_items),
            "parse_errors": len(parse_errors),
            "events_refresh": {
                "ok": events_refresh.get("ok"),
                "events": nested_get(events_refresh, ["summary", "events"]),
            } if isinstance(events_refresh, dict) else None,
        },
        "summary": episode_summary,
        "write": write_report,
        "latest_episode": episode_latest_projection(latest_episode),
        "paths": {
            "latest": latest_path,
            "daily_glob": daily_glob,
        },
        "parse_errors": parse_errors[:20],
        "policy": {
            "derived": True,
            "raw_private_content": False,
            "automatic_action": False,
            "private_sources_allowed_when_policy_enabled": True,
        },
    }


def episodes_validate_document(
    *,
    latest: Any,
    latest_error: Any,
    items: list[dict[str, Any]],
    parse_errors: list[dict[str, Any]],
    allowed_sources: set[str],
    latest_path: str,
    daily_glob: str,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    _add_check(checks, "ok" if isinstance(latest, dict) else "fail", "latest", "episodes latest exists", {"path": latest_path, "error": latest_error})
    episode_ids: set[str] = set()
    duplicates: list[str] = []
    missing: list[dict[str, Any]] = []
    forbidden_hits: list[dict[str, Any]] = []
    for item in items:
        record = item.get("record") if isinstance(item.get("record"), dict) else {}
        episode_id = str(record.get("episode_id") or "")
        if episode_id in episode_ids:
            duplicates.append(episode_id)
        episode_ids.add(episode_id)
        for key in ("schema", "episode_id", "start_at", "end_at", "category", "severity", "confidence", "sensitivity", "title", "summary", "event_ids"):
            if not record.get(key):
                missing.append({"path": item.get("path"), "line": item.get("line"), "episode_id": episode_id, "missing": key})
        if record.get("schema") != f"{schema_prefix}_nervous_episode_v1":
            missing.append({"path": item.get("path"), "line": item.get("line"), "episode_id": episode_id, "missing": "expected_episode_schema"})
        source_ids = set(record.get("source_ids", [])) if isinstance(record.get("source_ids"), list) else set()
        if source_ids - allowed_sources or record.get("raw_private_content") is not False:
            forbidden_hits.append({"path": item.get("path"), "line": item.get("line"), "episode_id": episode_id, "source_ids": sorted(source_ids), "raw_private_content": record.get("raw_private_content")})
    _add_check(checks, "ok" if not parse_errors else "fail", "jsonl_parse", "episode JSONL parses", {"parse_errors": parse_errors[:20], "parse_error_count": len(parse_errors)})
    _add_check(checks, "ok" if not duplicates else "fail", "unique_episode_ids", "episode ids are unique", {"duplicates": duplicates[:20], "duplicate_count": len(duplicates)})
    _add_check(checks, "ok" if not missing else "fail", "required_fields", "episode records have required fields", {"missing": missing[:20], "missing_count": len(missing)})
    _add_check(checks, "ok" if not forbidden_hits else "fail", "privacy_sources", "episodes contain only enabled allowed sources and no raw private content", {"forbidden_hits": forbidden_hits[:20], "forbidden_count": len(forbidden_hits)})
    _add_check(checks, "ok" if items else "warn", "episode_count", "episode records exist", {"episodes": len(items)})
    fails = sum(1 for item in checks if item["level"] == "fail")
    warnings = sum(1 for item in checks if item["level"] == "warn")
    return {
        "schema": f"{schema_prefix}_nervous_episodes_validate_v1",
        "version": version,
        "generated_at": generated_at or now_iso(),
        "ok": fails == 0,
        "checks": checks,
        "summary": {
            "fails": fails,
            "warnings": warnings,
            "checks": len(checks),
            "episodes": len(items),
            "parse_errors": len(parse_errors),
        },
        "paths": {
            "latest": latest_path,
            "daily_glob": daily_glob,
        },
    }

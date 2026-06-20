from __future__ import annotations

import datetime as dt
from typing import Any


TYPING_NERVOUS_INDEX_RESOURCE_GATE_REASONS = frozenset(
    {
        "mode_unattended_cap_probe",
        "memory_critical_blocks_medium",
        "memory_critical_blocks_unattended_medium",
        "game_guard_unattended_medium_or_heavier",
        "game_guard_active",
        "thermal_plan_unattended_denied",
        "thermal_plan_denied",
        "cpu_route_unattended_denied",
        "indexing_unattended_swap_used_pressure",
        "indexing_unattended_swap_free_below_floor",
    }
)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float | None = None) -> float | None:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_time(value: Any) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.datetime.now().astimezone().tzinfo)
    return parsed


def _now(now: dt.datetime | None = None) -> dt.datetime:
    if now is not None:
        if now.tzinfo is None:
            return now.replace(tzinfo=dt.datetime.now().astimezone().tzinfo)
        return now.astimezone()
    return dt.datetime.now(dt.timezone.utc).astimezone()


def _now_iso(now: dt.datetime | None = None) -> str:
    return _now(now).isoformat(timespec="seconds")


def _age_seconds_from_iso(value: Any, *, now: dt.datetime | None = None) -> float | None:
    parsed = _parse_time(value)
    if parsed is None:
        return None
    return round((_now(now) - parsed).total_seconds(), 1)


def typing_nervous_index_resource_gated(index_launch: Any) -> bool:
    if not isinstance(index_launch, dict) or index_launch.get("ok") is True:
        return False
    blocked = {
        str(item)
        for item in (index_launch.get("blocked_reasons") or [])
        if str(item or "").strip()
    }
    denied = [
        str(item)
        for item in (index_launch.get("denied_reasons") or [])
        if str(item or "").strip()
    ]
    return bool(
        blocked
        and blocked.issubset(TYPING_NERVOUS_INDEX_RESOURCE_GATE_REASONS)
        and not denied
    )


def typing_nervous_refresh_needed(
    latest_event: dict[str, Any],
    fact_state: dict[str, Any],
    process: dict[str, Any],
    index_status: dict[str, Any],
    processing: dict[str, Any],
) -> dict[str, Any]:
    latest_event_at = latest_event.get("generated_at") if isinstance(latest_event, dict) else None
    facts_at = fact_state.get("generated_at") if isinstance(fact_state, dict) else None
    latest_event_time = _parse_time(latest_event_at)
    facts_time = _parse_time(facts_at)
    facts_cover_latest_event = bool(not latest_event_time or (facts_time and facts_time >= latest_event_time))

    process_summary = process.get("summary") if isinstance(process.get("summary"), dict) else {}
    fact_process_summary = (
        fact_state.get("typed_process_summary")
        if isinstance(fact_state.get("typed_process_summary"), dict)
        else {}
    )
    process_summary_changed = bool(process_summary and process_summary != fact_process_summary)
    snapshot_needed = bool(
        latest_event_time
        and (
            not fact_state.get("exists")
            or not fact_state.get("typed_fact_exists")
            or not facts_cover_latest_event
            or process_summary_changed
        )
    )
    freshness = index_status.get("freshness") if isinstance(index_status.get("freshness"), dict) else {}
    records_lag = _safe_int(freshness.get("records_lag"), 0)
    index_stale = bool(freshness.get("stale")) or bool(freshness.get("records_lag_stale"))
    index_needed = bool(index_stale or processing.get("ok") is not True)
    return {
        "latest_event_generated_at": latest_event_at,
        "facts_generated_at": facts_at,
        "facts_cover_latest_event": facts_cover_latest_event,
        "process_summary_changed_since_fact": process_summary_changed,
        "snapshot_needed": snapshot_needed,
        "index_needed": index_needed,
        "index_stale": index_stale,
        "records_lag": records_lag,
        "processing_ok": processing.get("ok"),
        "index_freshness": freshness,
    }


def typing_nervous_deferred_recent_index_safe(summary: Any) -> bool:
    summary = summary if isinstance(summary, dict) else {}
    if summary.get("index_deferred_recent_attempt") is not True:
        return False
    lag = _safe_int(summary.get("index_records_lag"), _safe_int(summary.get("global_index_records_lag"), 0))
    tolerance = _safe_int(
        summary.get("index_records_lag_tolerance"),
        _safe_int(summary.get("global_index_records_lag_tolerance"), 4),
    )
    if lag <= tolerance:
        return True
    previous_age = _safe_float(summary.get("index_previous_attempt_age_sec"), None)
    min_interval = _safe_float(summary.get("index_min_interval_sec"), None)
    if previous_age is None or min_interval is None or previous_age >= min_interval:
        return False
    allowance = max(tolerance, min(64, max(tolerance + 8, tolerance * 3)))
    return bool(lag <= allowance)


def typing_nervous_refresh_latest_status(
    *,
    latest: Any,
    latest_error: Any,
    timer: Any,
    service: Any,
    latest_path: Any,
    max_age_sec: float = 900.0,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str | None = None,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    latest_data = latest if isinstance(latest, dict) else {}
    latest_summary = latest_data.get("summary") if isinstance(latest_data.get("summary"), dict) else {}
    latest_policy = latest_data.get("policy") if isinstance(latest_data.get("policy"), dict) else {}
    timer_data = timer if isinstance(timer, dict) else {}
    service_data = service if isinstance(service, dict) else {}
    latest_age_sec = _age_seconds_from_iso(
        latest_data.get("finished_at") or latest_data.get("generated_at"),
        now=now,
    )
    latest_status = str(latest_data.get("status") or "missing")
    deferred_recent_index_safe = typing_nervous_deferred_recent_index_safe(latest_summary)
    acceptable_latest = bool(
        isinstance(latest, dict)
        and latest_data.get("ok") is True
        and (
            latest_status in {"fresh", "pending_existing_index_build", "resource_gated_index"}
            or (latest_status == "deferred_recent_index_attempt" and deferred_recent_index_safe)
        )
    )
    latest_fresh = bool(latest_age_sec is not None and latest_age_sec <= float(max_age_sec))
    timer_ok = bool(timer_data.get("is_active") and timer_data.get("is_enabled"))
    policy_ok = bool(
        latest_policy.get("raw_keylogging") is False
        and latest_policy.get("password_fields_captured") is False
        and latest_policy.get("widens_capture") is False
        and latest_policy.get("automatic_action") is False
        and latest_policy.get("internet_access") is False
    )
    if not isinstance(latest, dict):
        status = "missing"
    elif latest_error:
        status = "unreadable"
    elif not timer_ok:
        status = "timer_inactive"
    elif not policy_ok:
        status = "policy_violation"
    elif not acceptable_latest:
        status = latest_status if latest_status != "missing" else "degraded"
    elif not latest_fresh:
        status = "stale"
    else:
        status = latest_status
    return {
        "schema": f"{schema_prefix}_typing_nervous_refresh_status_v1",
        "version": version,
        "generated_at": generated_at or _now_iso(now),
        "ok": bool(
            status in {"fresh", "pending_existing_index_build", "resource_gated_index"}
            or (status == "deferred_recent_index_attempt" and deferred_recent_index_safe)
        ),
        "status": status,
        "summary": {
            "latest_exists": isinstance(latest, dict),
            "latest_error": latest_error,
            "latest_ok": latest_data.get("ok") if isinstance(latest, dict) else None,
            "latest_status": latest_data.get("status") if isinstance(latest, dict) else None,
            "latest_generated_at": latest_data.get("generated_at") if isinstance(latest, dict) else None,
            "latest_finished_at": latest_data.get("finished_at") if isinstance(latest, dict) else None,
            "latest_age_sec": latest_age_sec,
            "max_age_sec": float(max_age_sec),
            "timer_active": timer_data.get("is_active"),
            "timer_enabled": timer_data.get("is_enabled"),
            "service_active": service_data.get("is_active"),
            "snapshot_needed": latest_summary.get("snapshot_needed"),
            "index_needed": latest_summary.get("index_needed"),
            "index_deferred_recent_attempt": latest_summary.get("index_deferred_recent_attempt"),
            "nervous_processing_ok": latest_summary.get("nervous_processing_ok"),
            "index_resource_launch_attempted": latest_summary.get("index_resource_launch_attempted"),
            "index_resource_launch_ok": latest_summary.get("index_resource_launch_ok"),
            "index_resource_allowed": latest_summary.get("index_resource_allowed"),
            "index_resource_blocked": latest_summary.get("index_resource_blocked"),
            "index_resource_denied": latest_summary.get("index_resource_denied"),
            "index_resource_soft_gated": latest_summary.get(
                "index_resource_soft_gated",
                latest_summary.get("index_resource_gated"),
            ),
            "index_resource_decision": latest_summary.get("index_resource_decision"),
            "index_resource_sample_thermal": latest_summary.get("index_resource_sample_thermal"),
            "index_resource_gated": latest_summary.get("index_resource_gated"),
            "index_launch_blocked_reasons": latest_summary.get("index_launch_blocked_reasons"),
            "index_records_lag": latest_summary.get("index_records_lag"),
            "index_records_lag_tolerance": latest_summary.get("index_records_lag_tolerance"),
            "index_stale": latest_summary.get("index_stale"),
            "index_deferred_recent_attempt_safe": deferred_recent_index_safe,
        },
        "latest": {
            "path": str(latest_path),
            "generated_at": latest_data.get("generated_at") if isinstance(latest, dict) else None,
            "finished_at": latest_data.get("finished_at") if isinstance(latest, dict) else None,
            "status": latest_data.get("status") if isinstance(latest, dict) else None,
            "ok": latest_data.get("ok") if isinstance(latest, dict) else None,
            "summary": latest_summary,
        },
        "timer": timer_data,
        "service": service_data,
        "policy": {
            "raw_keylogging": latest_policy.get("raw_keylogging"),
            "password_fields_captured": latest_policy.get("password_fields_captured"),
            "widens_capture": latest_policy.get("widens_capture"),
            "automatic_action": latest_policy.get("automatic_action"),
            "internet_access": latest_policy.get("internet_access"),
        },
    }


def typing_nervous_recent_index_debounce_safe(
    *,
    index_needed: bool,
    force_index: bool,
    previous_index_launch_attempted: bool,
    previous_index_attempt_age_sec: Any,
    index_min_interval_sec: Any,
    index_records_lag: Any,
    index_records_lag_tolerance: Any,
    index_stale: Any,
) -> bool:
    previous_age = _safe_float(previous_index_attempt_age_sec, None)
    min_interval = _safe_float(index_min_interval_sec, None)
    if (
        not index_needed
        or force_index
        or not previous_index_launch_attempted
        or previous_age is None
        or min_interval is None
        or previous_age >= min_interval
    ):
        return False
    return typing_nervous_deferred_recent_index_safe(
        {
            "index_deferred_recent_attempt": True,
            "index_previous_attempt_age_sec": previous_age,
            "index_min_interval_sec": min_interval,
            "index_records_lag": index_records_lag,
            "index_records_lag_tolerance": index_records_lag_tolerance,
            "index_stale": index_stale,
            "global_index_records_lag": index_records_lag,
            "global_index_records_lag_tolerance": index_records_lag_tolerance,
            "global_index_stale": index_stale,
        }
    )

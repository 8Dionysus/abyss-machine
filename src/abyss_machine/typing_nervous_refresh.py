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

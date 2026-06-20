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


def _nested_get(data: Any, path: list[str]) -> Any:
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


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


def typing_nervous_refresh_index_attempt_context(
    *,
    index_needed: bool,
    force_index: bool,
    previous_refresh: Any,
    index_status: Any,
    assessment: Any,
    index_min_interval_sec: Any,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    previous_refresh_data = previous_refresh if isinstance(previous_refresh, dict) else {}
    previous_refresh_summary = (
        previous_refresh_data.get("summary")
        if isinstance(previous_refresh_data.get("summary"), dict)
        else {}
    )
    assessment_data = assessment if isinstance(assessment, dict) else {}
    min_interval = max(0.0, _safe_float(index_min_interval_sec, 900.0) or 0.0)
    previous_refresh_age_sec = _age_seconds_from_iso(previous_refresh_data.get("finished_at"), now=now)
    previous_index_launch_attempted = bool(
        previous_refresh_summary.get("index_resource_launch_attempted")
        or previous_refresh_summary.get("index_deferred_recent_attempt")
    )
    previous_index_attempt_age_basis = "previous_refresh_finished_at"
    previous_index_attempt_age_sec = previous_refresh_age_sec
    if previous_refresh_summary.get("index_deferred_recent_attempt"):
        deferred_age = _safe_float(previous_refresh_summary.get("index_previous_attempt_age_sec"), None)
        if deferred_age is not None:
            previous_index_attempt_age_sec = deferred_age + (previous_refresh_age_sec or 0.0)
            previous_index_attempt_age_basis = "previous_deferred_attempt_age_plus_refresh_age"

    debounce_candidate_records_lag = _nested_get(index_status, ["freshness", "records_lag"])
    if debounce_candidate_records_lag is None:
        debounce_candidate_records_lag = assessment_data.get("records_lag")
    debounce_candidate_records_lag_tolerance = _nested_get(index_status, ["freshness", "records_lag_tolerance"])
    if debounce_candidate_records_lag_tolerance is None:
        debounce_candidate_records_lag_tolerance = 4
    debounce_candidate_index_stale = bool(
        _nested_get(index_status, ["freshness", "stale"])
        or assessment_data.get("index_stale")
    )
    recent_index_debounce_candidate = bool(
        index_needed
        and not force_index
        and previous_index_launch_attempted
        and previous_index_attempt_age_sec is not None
        and previous_index_attempt_age_sec < min_interval
    )
    index_deferred_recent_attempt = typing_nervous_recent_index_debounce_safe(
        index_needed=index_needed,
        force_index=force_index,
        previous_index_launch_attempted=previous_index_launch_attempted,
        previous_index_attempt_age_sec=previous_index_attempt_age_sec,
        index_min_interval_sec=min_interval,
        index_records_lag=debounce_candidate_records_lag,
        index_records_lag_tolerance=debounce_candidate_records_lag_tolerance,
        index_stale=debounce_candidate_index_stale,
    )
    return {
        "index_min_interval_sec": min_interval,
        "previous_refresh_age_sec": previous_refresh_age_sec,
        "previous_index_launch_attempted": previous_index_launch_attempted,
        "previous_index_attempt_age_basis": previous_index_attempt_age_basis,
        "previous_index_attempt_age_sec": previous_index_attempt_age_sec,
        "debounce_candidate_records_lag": debounce_candidate_records_lag,
        "debounce_candidate_records_lag_tolerance": debounce_candidate_records_lag_tolerance,
        "debounce_candidate_index_stale": debounce_candidate_index_stale,
        "recent_index_debounce_candidate": recent_index_debounce_candidate,
        "index_deferred_recent_attempt": index_deferred_recent_attempt,
        "index_debounce_bypassed_for_lag": bool(
            recent_index_debounce_candidate and not index_deferred_recent_attempt
        ),
    }


def typing_nervous_refresh_snapshot_action(
    *,
    snapshot: Any,
    force_snapshot: bool,
) -> dict[str, Any]:
    snapshot_data = snapshot if isinstance(snapshot, dict) else None
    if snapshot_data is None:
        return {"action": "nervous_snapshot", "status": "not_needed"}
    return {
        "action": "nervous_snapshot",
        "reason": "forced" if force_snapshot else "typed_event_or_process_not_in_facts",
        "ok": snapshot_data.get("ok"),
        "generated_at": snapshot_data.get("generated_at"),
        "summary": snapshot_data.get("summary") if isinstance(snapshot_data.get("summary"), dict) else {},
    }


def typing_nervous_refresh_index_action(
    *,
    action_status: str,
    previous_refresh: Any = None,
    previous_index_attempt_age_sec: Any = None,
    index_min_interval_sec: Any = None,
    index_service: Any = None,
    dynamic_index_units: Any = None,
    index_launch: Any = None,
    force_index: bool = False,
    index_launch_already_running: bool = False,
    index_debounce_bypassed_for_lag: bool = False,
    debounce_candidate_records_lag: Any = None,
    debounce_candidate_records_lag_tolerance: Any = None,
) -> dict[str, Any]:
    if action_status == "deferred_recent_index_attempt":
        previous_refresh_data = previous_refresh if isinstance(previous_refresh, dict) else {}
        return {
            "action": "nervous_index_build",
            "status": "deferred_recent_index_attempt",
            "reason": "typing_refresh_index_debounce",
            "previous_refresh_finished_at": previous_refresh_data.get("finished_at"),
            "previous_attempt_age_sec": previous_index_attempt_age_sec,
            "min_interval_sec": index_min_interval_sec,
        }
    if action_status == "deferred_existing_index_build_running":
        return {
            "action": "nervous_index_build",
            "status": "deferred_existing_index_build_running",
            "service": index_service,
            "dynamic_resource_units": dynamic_index_units,
        }
    if action_status == "launched":
        launch_data = index_launch if isinstance(index_launch, dict) else {}
        return {
            "action": "nervous_index_build",
            "status": "deferred_existing_index_lock" if index_launch_already_running else None,
            "reason": "forced" if force_index else "facts_or_index_freshness_required_refresh",
            "ok": launch_data.get("ok"),
            "debounce_bypassed_for_lag": index_debounce_bypassed_for_lag,
            "debounce_candidate_records_lag": debounce_candidate_records_lag,
            "debounce_candidate_records_lag_tolerance": debounce_candidate_records_lag_tolerance,
            "blocked_reasons": launch_data.get("blocked_reasons"),
            "denied_reasons": launch_data.get("denied_reasons"),
            "resource_decision": _nested_get(launch_data, ["plan", "decision"]),
            "resource_sample_thermal": _nested_get(launch_data, ["plan", "request", "sample_thermal"]),
            "elapsed_sec": launch_data.get("elapsed_sec"),
            "execution": launch_data.get("execution"),
        }
    return {"action": "nervous_index_build", "status": "not_needed"}


def typing_nervous_refresh_index_retry_action(index_retry_launch: Any) -> dict[str, Any]:
    retry_data = index_retry_launch if isinstance(index_retry_launch, dict) else {}
    return {
        "action": "nervous_index_build",
        "status": "retry_after_typed_fact_changed_during_index",
        "reason": "first_index_build_finished_before_latest_typed_fact",
        "ok": retry_data.get("ok"),
        "blocked_reasons": retry_data.get("blocked_reasons"),
        "denied_reasons": retry_data.get("denied_reasons"),
        "resource_decision": _nested_get(retry_data, ["plan", "decision"]),
        "resource_sample_thermal": _nested_get(retry_data, ["plan", "request", "sample_thermal"]),
        "elapsed_sec": retry_data.get("elapsed_sec"),
        "execution": retry_data.get("execution"),
    }


def typing_nervous_refresh_synthesis_action(
    *,
    synthesis_needed: bool,
    index_needed: bool,
    final_context: Any,
    synthesis_refresh: Any = None,
    synthesis_validation: Any = None,
) -> dict[str, Any]:
    if synthesis_needed:
        synthesis_data = synthesis_refresh if isinstance(synthesis_refresh, dict) else {}
        validation_data = synthesis_validation if isinstance(synthesis_validation, dict) else {}
        return {
            "action": "nervous_synthesis_build",
            "reason": "typed_facts_index_refresh_completed",
            "ok": synthesis_data.get("ok"),
            "candidate_id": synthesis_data.get("candidate_id"),
            "summary": synthesis_data.get("summary") if isinstance(synthesis_data.get("summary"), dict) else {},
            "validation_ok": validation_data.get("ok"),
            "validation_summary": (
                validation_data.get("summary") if isinstance(validation_data.get("summary"), dict) else {}
            ),
        }
    if index_needed:
        final_data = final_context if isinstance(final_context, dict) else {}
        return {
            "action": "nervous_synthesis_build",
            "status": final_data.get("synthesis_action_status"),
            "reason": "index_refresh_not_confirmed_fresh_yet",
        }
    return {"action": "nervous_synthesis_build", "status": "not_needed"}


def typing_nervous_refresh_final_context(
    *,
    process: Any,
    latest_event: Any,
    assessment_before: Any,
    processing_after: Any,
    fact_after_snapshot: Any,
    index_after: Any,
    index_launch: Any,
    index_needed: bool,
    force_index: bool,
    index_deferred_recent_attempt: bool,
    index_service_running: bool,
    index_launch_already_running: bool,
    previous_index_attempt_age_sec: Any,
    previous_index_attempt_age_basis: Any,
    previous_refresh_age_sec: Any,
    index_min_interval_sec: Any,
    recent_index_debounce_candidate: bool,
    index_debounce_bypassed_for_lag: bool,
    debounce_candidate_records_lag: Any,
    debounce_candidate_records_lag_tolerance: Any,
    synthesis_refresh: Any = None,
    synthesis_validation: Any = None,
) -> dict[str, Any]:
    process_data = process if isinstance(process, dict) else {}
    latest_event_data = latest_event if isinstance(latest_event, dict) else {}
    assessment_data = assessment_before if isinstance(assessment_before, dict) else {}
    processing_data = processing_after if isinstance(processing_after, dict) else {}
    fact_data = fact_after_snapshot if isinstance(fact_after_snapshot, dict) else {}
    index_data = index_after if isinstance(index_after, dict) else {}
    launch_data = index_launch if isinstance(index_launch, dict) else {}
    synthesis_data = synthesis_refresh if isinstance(synthesis_refresh, dict) else None
    synthesis_validation_data = synthesis_validation if isinstance(synthesis_validation, dict) else None

    final_pending = bool(
        processing_data.get("ok") is not True
        and index_needed
        and not index_deferred_recent_attempt
        and (index_service_running or index_launch_already_running)
        and not force_index
    )
    index_resource_gated = bool(
        processing_data.get("ok") is not True
        and index_needed
        and not index_deferred_recent_attempt
        and not force_index
        and typing_nervous_index_resource_gated(index_launch)
        and process_data.get("ok") is True
        and fact_data.get("exists") is True
        and fact_data.get("typed_fact_exists") is True
    )
    index_resource_launch_attempted = isinstance(index_launch, dict)
    index_launch_blocked_reasons = launch_data.get("blocked_reasons") if index_resource_launch_attempted else None
    index_launch_denied_reasons = launch_data.get("denied_reasons") if index_resource_launch_attempted else None
    index_resource_blocked = bool(index_launch_blocked_reasons)
    index_resource_denied = bool(index_launch_denied_reasons)
    index_resource_launch_ok = bool(index_resource_launch_attempted and launch_data.get("ok") is True)
    index_resource_allowed = bool(index_resource_launch_ok and not index_resource_blocked and not index_resource_denied)
    index_resource_decision = _nested_get(launch_data, ["plan", "decision"]) if index_resource_launch_attempted else None
    index_resource_sample_thermal = (
        _nested_get(launch_data, ["plan", "request", "sample_thermal"])
        if index_resource_launch_attempted
        else None
    )
    synthesis_needed = bool(index_needed and processing_data.get("ok") is True and not final_pending)
    synthesis_action_status = (
        "deferred_resource_gated_index"
        if index_resource_gated
        else (
            "deferred_recent_index_attempt"
            if index_deferred_recent_attempt
            else ("deferred_index_pending" if final_pending else "not_run_index_not_fresh")
        )
    )
    synthesis_ok_for_status = bool(
        not synthesis_needed
        or (
            synthesis_data is not None
            and synthesis_data.get("ok") is True
            and synthesis_validation_data is not None
            and synthesis_validation_data.get("ok") is True
        )
    )
    status = (
        "fresh"
        if processing_data.get("ok") is True
        else (
            "pending_existing_index_build"
            if final_pending
            else (
                "deferred_recent_index_attempt"
                if index_deferred_recent_attempt
                else ("resource_gated_index" if index_resource_gated else "degraded")
            )
        )
    )
    if status == "fresh" and not synthesis_ok_for_status:
        status = "degraded"

    global_index_records_lag = _nested_get(index_data, ["freshness", "records_lag"])
    global_index_stale = _nested_get(index_data, ["freshness", "stale"])
    global_index_records_lag_tolerance = _nested_get(index_data, ["freshness", "records_lag_tolerance"])
    typed_index_fresh = bool(processing_data.get("ok") is True)
    typed_index_records_lag = 0 if typed_index_fresh else global_index_records_lag
    typed_index_stale = False if typed_index_fresh else global_index_stale
    index_deferred_recent_attempt_safe = typing_nervous_deferred_recent_index_safe(
        {
            "index_deferred_recent_attempt": index_deferred_recent_attempt,
            "index_previous_attempt_age_sec": previous_index_attempt_age_sec,
            "index_min_interval_sec": index_min_interval_sec,
            "index_records_lag": typed_index_records_lag,
            "index_records_lag_tolerance": global_index_records_lag_tolerance,
            "index_stale": typed_index_stale,
            "global_index_records_lag": global_index_records_lag,
            "global_index_records_lag_tolerance": global_index_records_lag_tolerance,
            "global_index_stale": global_index_stale,
        }
    )
    summary = {
        "status": status,
        "process_status": process_data.get("status"),
        "process_records": _nested_get(process_data, ["summary", "records_processed"]),
        "process_lanes": _nested_get(process_data, ["summary", "lanes"]),
        "latest_event_generated_at": latest_event_data.get("generated_at"),
        "snapshot_needed": bool(assessment_data.get("snapshot_needed")),
        "index_needed": index_needed,
        "index_deferred_recent_attempt": index_deferred_recent_attempt,
        "index_deferred_recent_attempt_safe": index_deferred_recent_attempt_safe,
        "index_previous_attempt_age_sec": previous_index_attempt_age_sec,
        "index_previous_attempt_age_basis": previous_index_attempt_age_basis,
        "index_previous_refresh_age_sec": previous_refresh_age_sec,
        "index_min_interval_sec": index_min_interval_sec,
        "index_recent_debounce_candidate": recent_index_debounce_candidate,
        "index_debounce_bypassed_for_lag": index_debounce_bypassed_for_lag,
        "index_debounce_candidate_records_lag": debounce_candidate_records_lag,
        "index_debounce_candidate_records_lag_tolerance": debounce_candidate_records_lag_tolerance,
        "nervous_processing_ok": processing_data.get("ok"),
        "index_resource_launch_attempted": index_resource_launch_attempted,
        "index_resource_launch_ok": index_resource_launch_ok if index_resource_launch_attempted else None,
        "index_resource_allowed": index_resource_allowed if index_resource_launch_attempted else None,
        "index_resource_blocked": index_resource_blocked if index_resource_launch_attempted else None,
        "index_resource_denied": index_resource_denied if index_resource_launch_attempted else None,
        "index_resource_soft_gated": index_resource_gated,
        "index_resource_gated": index_resource_gated,
        "index_resource_decision": index_resource_decision,
        "index_resource_sample_thermal": index_resource_sample_thermal,
        "index_launch_blocked_reasons": index_launch_blocked_reasons,
        "index_launch_denied_reasons": index_launch_denied_reasons,
        "index_records_lag": typed_index_records_lag,
        "index_records_lag_tolerance": global_index_records_lag_tolerance,
        "index_stale": typed_index_stale,
        "global_index_records_lag": global_index_records_lag,
        "global_index_records_lag_tolerance": global_index_records_lag_tolerance,
        "global_index_stale": global_index_stale,
        "synthesis_needed": synthesis_needed,
        "synthesis_ok": synthesis_data.get("ok") if synthesis_data is not None else None,
        "synthesis_validation_ok": (
            synthesis_validation_data.get("ok") if synthesis_validation_data is not None else None
        ),
    }
    return {
        "ok": bool(
            process_data.get("ok")
            and (
                processing_data.get("ok") is True
                or final_pending
                or index_resource_gated
                or index_deferred_recent_attempt_safe
            )
            and synthesis_ok_for_status
        ),
        "status": status,
        "summary": summary,
        "final_pending": final_pending,
        "index_resource_gated": index_resource_gated,
        "index_resource_launch_attempted": index_resource_launch_attempted,
        "index_launch_blocked_reasons": index_launch_blocked_reasons,
        "index_launch_denied_reasons": index_launch_denied_reasons,
        "index_resource_blocked": index_resource_blocked,
        "index_resource_denied": index_resource_denied,
        "index_resource_launch_ok": index_resource_launch_ok,
        "index_resource_allowed": index_resource_allowed,
        "index_resource_decision": index_resource_decision,
        "index_resource_sample_thermal": index_resource_sample_thermal,
        "synthesis_needed": synthesis_needed,
        "synthesis_action_status": synthesis_action_status,
        "synthesis_ok_for_status": synthesis_ok_for_status,
        "global_index_records_lag": global_index_records_lag,
        "global_index_stale": global_index_stale,
        "global_index_records_lag_tolerance": global_index_records_lag_tolerance,
        "typed_index_records_lag": typed_index_records_lag,
        "typed_index_stale": typed_index_stale,
        "index_deferred_recent_attempt_safe": index_deferred_recent_attempt_safe,
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

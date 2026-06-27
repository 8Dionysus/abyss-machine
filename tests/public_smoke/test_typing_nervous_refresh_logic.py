from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli
from abyss_machine.typing_nervous_refresh import (
    TYPING_NERVOUS_INDEX_RESOURCE_GATE_REASONS,
    typing_nervous_deferred_recent_index_safe,
    typing_nervous_index_resource_gated,
    typing_nervous_processing_acceptance_status,
    typing_nervous_processing_status_document,
    typing_nervous_refresh_document,
    typing_nervous_refresh_index_action,
    typing_nervous_refresh_fact_state,
    typing_nervous_refresh_final_context,
    typing_nervous_refresh_index_attempt_context,
    typing_nervous_refresh_index_retry_action,
    typing_nervous_refresh_latest_status,
    typing_nervous_refresh_status_naming,
    typing_nervous_recent_index_debounce_safe,
    typing_nervous_refresh_needed,
    typing_nervous_refresh_snapshot_action,
    typing_nervous_refresh_synthesis_action,
    typing_nervous_source_facts,
)


def test_typing_nervous_resource_gate_accepts_only_known_soft_resource_blocks() -> None:
    assert "indexing_unattended_swap_used_pressure" in TYPING_NERVOUS_INDEX_RESOURCE_GATE_REASONS
    assert "indexing_unattended_swap_free_below_floor" in TYPING_NERVOUS_INDEX_RESOURCE_GATE_REASONS

    assert typing_nervous_index_resource_gated(
        {
            "ok": False,
            "blocked_reasons": ["indexing_unattended_swap_used_pressure"],
            "denied_reasons": [],
        }
    )
    assert not typing_nervous_index_resource_gated(
        {
            "ok": False,
            "blocked_reasons": ["indexing_unattended_swap_used_pressure"],
            "denied_reasons": ["storage_denied"],
        }
    )
    assert not typing_nervous_index_resource_gated(
        {
            "ok": False,
            "blocked_reasons": ["unexpected_block"],
            "denied_reasons": [],
        }
    )


def test_typing_nervous_deferred_recent_index_policy_is_bounded() -> None:
    bounded = {
        "index_deferred_recent_attempt": True,
        "index_previous_attempt_age_sec": 225,
        "index_min_interval_sec": 900,
        "index_records_lag": 6,
        "index_records_lag_tolerance": 4,
        "global_index_records_lag": 6,
        "global_index_records_lag_tolerance": 4,
    }
    assert typing_nervous_deferred_recent_index_safe(bounded)

    unbounded = dict(bounded)
    unbounded["index_records_lag"] = 65
    unbounded["global_index_records_lag"] = 65
    assert not typing_nervous_deferred_recent_index_safe(unbounded)

    outside_debounce = dict(bounded)
    outside_debounce["index_previous_attempt_age_sec"] = 900
    assert not typing_nervous_deferred_recent_index_safe(outside_debounce)


def test_typing_nervous_recent_index_debounce_bypasses_large_lag() -> None:
    common = {
        "index_needed": True,
        "force_index": False,
        "previous_index_launch_attempted": True,
        "previous_index_attempt_age_sec": 725,
        "index_min_interval_sec": 900,
        "index_records_lag_tolerance": 4,
        "index_stale": True,
    }

    assert typing_nervous_recent_index_debounce_safe(**common, index_records_lag=6)
    assert not typing_nervous_recent_index_debounce_safe(**common, index_records_lag=17)

    forced = dict(common, force_index=True)
    assert not typing_nervous_recent_index_debounce_safe(**forced, index_records_lag=6)


def test_typing_nervous_refresh_index_attempt_context_defers_bounded_recent_attempt() -> None:
    context = typing_nervous_refresh_index_attempt_context(
        index_needed=True,
        force_index=False,
        previous_refresh={
            "finished_at": "2026-06-20T05:00:00+00:00",
            "summary": {"index_resource_launch_attempted": True},
        },
        index_status={"freshness": {"records_lag": 6, "records_lag_tolerance": 4, "stale": True}},
        assessment={"records_lag": 9, "index_stale": True},
        index_min_interval_sec=900,
        now=dt.datetime.fromisoformat("2026-06-20T05:05:00+00:00"),
    )

    assert context["previous_refresh_age_sec"] == 300.0
    assert context["previous_index_launch_attempted"] is True
    assert context["previous_index_attempt_age_basis"] == "previous_refresh_finished_at"
    assert context["previous_index_attempt_age_sec"] == 300.0
    assert context["debounce_candidate_records_lag"] == 6
    assert context["debounce_candidate_records_lag_tolerance"] == 4
    assert context["debounce_candidate_index_stale"] is True
    assert context["recent_index_debounce_candidate"] is True
    assert context["index_deferred_recent_attempt"] is True
    assert context["index_debounce_bypassed_for_lag"] is False


def test_typing_nervous_refresh_index_attempt_context_bypasses_large_lag_and_accumulates_age() -> None:
    context = typing_nervous_refresh_index_attempt_context(
        index_needed=True,
        force_index=False,
        previous_refresh={
            "finished_at": "2026-06-20T05:05:00+00:00",
            "summary": {
                "index_deferred_recent_attempt": True,
                "index_previous_attempt_age_sec": 225,
            },
        },
        index_status={"freshness": {"records_lag": 17, "records_lag_tolerance": 4, "stale": True}},
        assessment={"records_lag": 2, "index_stale": False},
        index_min_interval_sec=900,
        now=dt.datetime.fromisoformat("2026-06-20T05:10:00+00:00"),
    )

    assert context["previous_refresh_age_sec"] == 300.0
    assert context["previous_index_attempt_age_basis"] == "previous_deferred_attempt_age_plus_refresh_age"
    assert context["previous_index_attempt_age_sec"] == 525.0
    assert context["recent_index_debounce_candidate"] is True
    assert context["index_deferred_recent_attempt"] is False
    assert context["index_debounce_bypassed_for_lag"] is True


def test_typing_nervous_refresh_index_attempt_context_falls_back_to_assessment_and_honors_force() -> None:
    context = typing_nervous_refresh_index_attempt_context(
        index_needed=True,
        force_index=True,
        previous_refresh={
            "finished_at": "2026-06-20T05:00:00+00:00",
            "summary": {"index_resource_launch_attempted": True},
        },
        index_status={"freshness": {"stale": False}},
        assessment={"records_lag": 6, "index_stale": True},
        index_min_interval_sec=900,
        now=dt.datetime.fromisoformat("2026-06-20T05:05:00+00:00"),
    )

    assert context["debounce_candidate_records_lag"] == 6
    assert context["debounce_candidate_records_lag_tolerance"] == 4
    assert context["debounce_candidate_index_stale"] is True
    assert context["recent_index_debounce_candidate"] is False
    assert context["index_deferred_recent_attempt"] is False
    assert context["index_debounce_bypassed_for_lag"] is False


def test_typing_nervous_refresh_snapshot_action_records_public_shape() -> None:
    action = typing_nervous_refresh_snapshot_action(
        snapshot={
            "ok": True,
            "generated_at": "2026-06-20T05:00:00+00:00",
            "summary": {"facts": 3},
        },
        force_snapshot=True,
    )

    assert action == {
        "action": "nervous_snapshot",
        "reason": "forced",
        "ok": True,
        "generated_at": "2026-06-20T05:00:00+00:00",
        "summary": {"facts": 3},
    }
    assert typing_nervous_refresh_snapshot_action(snapshot=None, force_snapshot=False) == {
        "action": "nervous_snapshot",
        "status": "not_needed",
    }


def test_typing_nervous_refresh_index_action_records_defer_launch_and_idle_shapes() -> None:
    deferred = typing_nervous_refresh_index_action(
        action_status="deferred_recent_index_attempt",
        previous_refresh={"finished_at": "2026-06-20T05:00:15+00:00"},
        previous_index_attempt_age_sec=225,
        index_min_interval_sec=900,
    )
    assert deferred == {
        "action": "nervous_index_build",
        "status": "deferred_recent_index_attempt",
        "reason": "typing_refresh_index_debounce",
        "previous_refresh_finished_at": "2026-06-20T05:00:15+00:00",
        "previous_attempt_age_sec": 225,
        "min_interval_sec": 900,
    }

    running = typing_nervous_refresh_index_action(
        action_status="deferred_existing_index_build_running",
        index_service={"active": "active"},
        dynamic_index_units=["abyss-machine-indexing@1.service"],
    )
    assert running == {
        "action": "nervous_index_build",
        "status": "deferred_existing_index_build_running",
        "service": {"active": "active"},
        "dynamic_resource_units": ["abyss-machine-indexing@1.service"],
    }

    launch = typing_nervous_refresh_index_action(
        action_status="launched",
        index_launch={
            "ok": False,
            "blocked_reasons": ["indexing_unattended_swap_used_pressure"],
            "denied_reasons": [],
            "plan": {"decision": "blocked", "request": {"sample_thermal": False}},
            "elapsed_sec": 2.5,
            "execution": {"returncode": 0},
        },
        force_index=False,
        index_launch_already_running=True,
        index_debounce_bypassed_for_lag=True,
        debounce_candidate_records_lag=17,
        debounce_candidate_records_lag_tolerance=4,
    )
    assert launch == {
        "action": "nervous_index_build",
        "status": "deferred_existing_index_lock",
        "reason": "facts_or_index_freshness_required_refresh",
        "ok": False,
        "debounce_bypassed_for_lag": True,
        "debounce_candidate_records_lag": 17,
        "debounce_candidate_records_lag_tolerance": 4,
        "blocked_reasons": ["indexing_unattended_swap_used_pressure"],
        "denied_reasons": [],
        "resource_decision": "blocked",
        "resource_sample_thermal": False,
        "elapsed_sec": 2.5,
        "execution": {"returncode": 0},
    }

    assert typing_nervous_refresh_index_action(action_status="not_needed") == {
        "action": "nervous_index_build",
        "status": "not_needed",
    }


def test_typing_nervous_refresh_index_retry_action_records_public_shape() -> None:
    action = typing_nervous_refresh_index_retry_action(
        {
            "ok": True,
            "blocked_reasons": [],
            "denied_reasons": [],
            "plan": {"decision": "allowed", "request": {"sample_thermal": True}},
            "elapsed_sec": 4.25,
            "execution": {"returncode": 0},
        }
    )

    assert action == {
        "action": "nervous_index_build",
        "status": "retry_after_typed_fact_changed_during_index",
        "reason": "first_index_build_finished_before_latest_typed_fact",
        "ok": True,
        "blocked_reasons": [],
        "denied_reasons": [],
        "resource_decision": "allowed",
        "resource_sample_thermal": True,
        "elapsed_sec": 4.25,
        "execution": {"returncode": 0},
    }


def test_typing_nervous_refresh_synthesis_action_records_run_defer_and_idle_shapes() -> None:
    run_action = typing_nervous_refresh_synthesis_action(
        synthesis_needed=True,
        index_needed=True,
        final_context={"synthesis_action_status": "unused"},
        synthesis_refresh={"ok": True, "candidate_id": "candidate-1", "summary": {"facts": 3}},
        synthesis_validation={"ok": True, "summary": {"checks": 4}},
    )
    assert run_action == {
        "action": "nervous_synthesis_build",
        "reason": "typed_facts_index_refresh_completed",
        "ok": True,
        "candidate_id": "candidate-1",
        "summary": {"facts": 3},
        "validation_ok": True,
        "validation_summary": {"checks": 4},
    }

    deferred = typing_nervous_refresh_synthesis_action(
        synthesis_needed=False,
        index_needed=True,
        final_context={"synthesis_action_status": "deferred_index_pending"},
    )
    assert deferred == {
        "action": "nervous_synthesis_build",
        "status": "deferred_index_pending",
        "reason": "index_refresh_not_confirmed_fresh_yet",
    }
    assert typing_nervous_refresh_synthesis_action(
        synthesis_needed=False,
        index_needed=False,
        final_context={},
    ) == {"action": "nervous_synthesis_build", "status": "not_needed"}


def test_typing_nervous_refresh_document_records_public_refresh_shape() -> None:
    document = typing_nervous_refresh_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-20T05:00:00+00:00",
        finished_at="2026-06-20T05:00:15+00:00",
        final_context={
            "ok": True,
            "status": "fresh",
            "summary": {"status": "fresh", "index_needed": False},
            "synthesis_needed": False,
        },
        latest_event={
            "generated_at": "2026-06-20T04:59:59+00:00",
            "event_id": "event-1",
            "source_adapter": "saved_text_snapshot",
            "status": "committed",
        },
        latest_error=None,
        process={"ok": True, "status": "processed", "generated_at": "now", "summary": {"records": 2}},
        fact_before={"exists": True},
        fact_after_snapshot={"exists": True, "typed_fact_exists": True},
        index_before={"ok": True, "ready": True, "warnings": [], "freshness": {"records_lag": 0}, "counts": {"rows": 2}},
        index_after={"ok": True, "ready": True, "warnings": [], "freshness": {"records_lag": 0}, "counts": {"rows": 2}},
        index_service={"active": "inactive"},
        index_launch=None,
        index_retry_launch=None,
        index_launch_already_running=False,
        index_wait_observations=[],
        previous_refresh={"status": "fresh", "finished_at": "2026-06-20T04:00:00+00:00"},
        previous_refresh_error=None,
        previous_index_launch_attempted=False,
        synthesis_refresh=None,
        synthesis_validation=None,
        processing_before={"ok": True},
        processing_after_snapshot={"ok": True},
        processing_after={"ok": True},
        assessment_before={"snapshot_needed": False},
        assessment_after_snapshot={"snapshot_needed": False},
        assessment_after={"snapshot_needed": False},
        actions=[{"action": "nervous_snapshot", "status": "not_needed"}],
        latest_path="/var/lib/abyss-machine/typing-nervous-refresh/latest.json",
        daily_glob_path="/var/lib/abyss-machine/typing-nervous-refresh/YYYY/MM/YYYY-MM-DD.jsonl",
        typing_process_path="/var/lib/abyss-machine/typing/process/latest.json",
        nervous_facts_path="/var/lib/abyss-machine/nervous/facts/latest.json",
        nervous_index_path="/var/lib/abyss-machine/nervous/search-index/latest.json",
    )

    assert document["schema"] == "abyss_machine_typing_nervous_refresh_v1"
    assert document["version"] == "test"
    assert document["ok"] is True
    assert document["status"] == "fresh"
    assert document["summary"] == {"status": "fresh", "index_needed": False}
    assert document["latest_event"]["exists"] is True
    assert document["latest_event"]["event_id"] == "event-1"
    assert document["process"]["summary"] == {"records": 2}
    assert document["facts"]["after_snapshot"]["typed_fact_exists"] is True
    assert document["index"]["previous_refresh"]["index_resource_launch_attempted"] is False
    assert document["synthesis"]["needed"] is False
    assert document["actions"] == [{"action": "nervous_snapshot", "status": "not_needed"}]
    assert document["paths"]["latest"].endswith("/typing-nervous-refresh/latest.json")
    assert document["policy"]["raw_keylogging"] is False
    assert document["policy"]["resource_gated_index_work"] is True
    assert document["non_claims"][0].startswith("This tick processes already-stored committed-text events")


def _final_context(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "process": {"ok": True, "status": "ok", "summary": {"records_processed": 5, "lanes": 2}},
        "latest_event": {"generated_at": "2026-06-20T05:00:00+00:00"},
        "assessment_before": {"snapshot_needed": False},
        "processing_after": {"ok": True},
        "fact_after_snapshot": {"exists": True, "typed_fact_exists": True},
        "index_after": {"freshness": {"records_lag": 9, "records_lag_tolerance": 4, "stale": True}},
        "index_launch": None,
        "index_needed": True,
        "force_index": False,
        "index_deferred_recent_attempt": False,
        "index_service_running": False,
        "index_launch_already_running": False,
        "previous_index_attempt_age_sec": 225,
        "previous_index_attempt_age_basis": "previous_refresh_finished_at",
        "previous_refresh_age_sec": 300.0,
        "index_min_interval_sec": 900.0,
        "recent_index_debounce_candidate": True,
        "index_debounce_bypassed_for_lag": False,
        "debounce_candidate_records_lag": 6,
        "debounce_candidate_records_lag_tolerance": 4,
        "synthesis_refresh": {"ok": True},
        "synthesis_validation": {"ok": True},
    }
    base.update(overrides)
    return typing_nervous_refresh_final_context(**base)  # type: ignore[arg-type]


def test_typing_nervous_refresh_final_context_reports_fresh_with_synthesis_success() -> None:
    context = _final_context()

    assert context["ok"] is True
    assert context["status"] == "fresh"
    assert context["synthesis_needed"] is True
    assert context["synthesis_ok_for_status"] is True
    assert context["typed_index_records_lag"] == 0
    assert context["typed_index_stale"] is False
    assert context["summary"]["status"] == "fresh"
    assert context["summary"]["process_records"] == 5
    assert context["summary"]["index_records_lag"] == 0
    assert context["summary"]["global_index_records_lag"] == 9
    assert context["summary"]["synthesis_ok"] is True
    assert context["summary"]["synthesis_validation_ok"] is True


def test_typing_nervous_refresh_final_context_degrades_when_synthesis_fails() -> None:
    context = _final_context(
        synthesis_refresh={"ok": True},
        synthesis_validation={"ok": False},
    )

    assert context["ok"] is False
    assert context["status"] == "degraded"
    assert context["synthesis_needed"] is True
    assert context["synthesis_ok_for_status"] is False
    assert context["summary"]["synthesis_ok"] is True
    assert context["summary"]["synthesis_validation_ok"] is False


def test_typing_nervous_refresh_final_context_accepts_soft_resource_gate() -> None:
    context = _final_context(
        processing_after={"ok": False, "status": "facts_ready_index_stale"},
        index_launch={
            "ok": False,
            "blocked_reasons": ["indexing_unattended_swap_used_pressure"],
            "denied_reasons": [],
            "plan": {"decision": "blocked", "request": {"sample_thermal": False}},
        },
        synthesis_refresh=None,
        synthesis_validation=None,
    )

    assert context["ok"] is True
    assert context["status"] == "resource_gated_index"
    assert context["index_resource_gated"] is True
    assert context["synthesis_needed"] is False
    assert context["synthesis_action_status"] == "deferred_resource_gated_index"
    assert context["summary"]["index_resource_launch_attempted"] is True
    assert context["summary"]["index_resource_blocked"] is True
    assert context["summary"]["index_resource_denied"] is False
    assert context["summary"]["index_resource_decision"] == "blocked"
    assert context["summary"]["index_records_lag"] == 9
    assert context["summary"]["index_stale"] is True


def test_typing_nervous_refresh_final_context_preserves_pending_and_deferred_ok_states() -> None:
    pending = _final_context(
        processing_after={"ok": False},
        index_service_running=True,
        synthesis_refresh=None,
        synthesis_validation=None,
    )
    assert pending["ok"] is True
    assert pending["status"] == "pending_existing_index_build"
    assert pending["final_pending"] is True
    assert pending["synthesis_action_status"] == "deferred_index_pending"

    deferred = _final_context(
        processing_after={"ok": False},
        index_deferred_recent_attempt=True,
        index_after={"freshness": {"records_lag": 6, "records_lag_tolerance": 4, "stale": True}},
        synthesis_refresh=None,
        synthesis_validation=None,
    )
    assert deferred["ok"] is True
    assert deferred["status"] == "deferred_recent_index_attempt"
    assert deferred["index_deferred_recent_attempt_safe"] is True
    assert deferred["synthesis_action_status"] == "deferred_recent_index_attempt"


def test_typing_nervous_refresh_assessment_skips_snapshot_when_facts_cover_event() -> None:
    assessment = typing_nervous_refresh_needed(
        latest_event={"generated_at": "2026-06-20T05:00:00+00:00"},
        fact_state={
            "exists": True,
            "typed_fact_exists": True,
            "generated_at": "2026-06-20T05:01:00+00:00",
            "typed_process_summary": {"records_processed": 4, "lanes": 2},
        },
        process={"summary": {"records_processed": 4, "lanes": 2}},
        index_status={"freshness": {"records_lag": "0", "stale": False}},
        processing={"ok": True},
    )

    assert assessment["facts_cover_latest_event"] is True
    assert assessment["process_summary_changed_since_fact"] is False
    assert assessment["snapshot_needed"] is False
    assert assessment["index_needed"] is False
    assert assessment["records_lag"] == 0


def test_typing_nervous_refresh_assessment_requests_snapshot_for_stale_facts() -> None:
    assessment = typing_nervous_refresh_needed(
        latest_event={"generated_at": "2026-06-20T05:00:00+00:00"},
        fact_state={
            "exists": True,
            "typed_fact_exists": True,
            "generated_at": "2026-06-20T04:59:00+00:00",
            "typed_process_summary": {"records_processed": 4, "lanes": 2},
        },
        process={"summary": {"records_processed": 4, "lanes": 2}},
        index_status={"freshness": {"records_lag": 1, "stale": False}},
        processing={"ok": True},
    )

    assert assessment["facts_cover_latest_event"] is False
    assert assessment["snapshot_needed"] is True
    assert assessment["index_needed"] is False


def test_typing_nervous_refresh_assessment_detects_process_and_index_drift() -> None:
    assessment = typing_nervous_refresh_needed(
        latest_event={"generated_at": "2026-06-20T05:00:00+00:00"},
        fact_state={
            "exists": True,
            "typed_fact_exists": True,
            "generated_at": "2026-06-20T05:01:00+00:00",
            "typed_process_summary": {"records_processed": 4, "lanes": 2},
        },
        process={"summary": {"records_processed": 5, "lanes": 3}},
        index_status={"freshness": {"records_lag": "7", "records_lag_stale": True}},
        processing={"ok": False},
    )

    assert assessment["facts_cover_latest_event"] is True
    assert assessment["process_summary_changed_since_fact"] is True
    assert assessment["snapshot_needed"] is True
    assert assessment["index_stale"] is True
    assert assessment["index_needed"] is True
    assert assessment["records_lag"] == 7
    assert assessment["processing_ok"] is False


def _fresh_status_latest(**overrides: object) -> dict[str, object]:
    latest: dict[str, object] = {
        "ok": True,
        "status": "fresh",
        "generated_at": "2026-06-20T05:00:00+00:00",
        "finished_at": "2026-06-20T05:00:15+00:00",
        "summary": {
            "snapshot_needed": False,
            "index_needed": False,
            "nervous_processing_ok": True,
            "index_records_lag": 0,
            "index_records_lag_tolerance": 4,
            "index_stale": False,
        },
        "policy": {
            "raw_keylogging": False,
            "password_fields_captured": False,
            "widens_capture": False,
            "automatic_action": False,
            "internet_access": False,
        },
    }
    latest.update(overrides)
    return latest


def _active_timer() -> dict[str, object]:
    return {"is_active": True, "is_enabled": True}


def test_typing_nervous_refresh_latest_status_accepts_fresh_latest() -> None:
    status = typing_nervous_refresh_latest_status(
        latest=_fresh_status_latest(),
        latest_error=None,
        timer=_active_timer(),
        service={"is_active": False},
        latest_path="/var/lib/abyss-machine/typing-nervous-refresh/latest.json",
        max_age_sec=900,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-20T05:01:00+00:00",
        now=dt.datetime.fromisoformat("2026-06-20T05:01:00+00:00"),
    )

    assert status["schema"] == "abyss_machine_typing_nervous_refresh_status_v1"
    assert status["version"] == "test"
    assert status["ok"] is True
    assert status["status"] == "fresh"
    assert status["summary"]["latest_age_sec"] == 45.0
    assert status["summary"]["timer_active"] is True
    assert status["summary"]["index_deferred_recent_attempt_safe"] is False


def test_typing_nervous_refresh_latest_status_preserves_deferred_recent_success() -> None:
    latest = _fresh_status_latest(
        status="deferred_recent_index_attempt",
        summary={
            "index_deferred_recent_attempt": True,
            "index_previous_attempt_age_sec": 225,
            "index_min_interval_sec": 900,
            "index_records_lag": 6,
            "index_records_lag_tolerance": 4,
            "global_index_records_lag": 6,
            "global_index_records_lag_tolerance": 4,
        },
    )
    status = typing_nervous_refresh_latest_status(
        latest=latest,
        latest_error=None,
        timer=_active_timer(),
        service={"is_active": False},
        latest_path="latest.json",
        generated_at="2026-06-20T05:01:00+00:00",
        now=dt.datetime.fromisoformat("2026-06-20T05:01:00+00:00"),
    )

    assert status["ok"] is True
    assert status["status"] == "deferred_recent_index_attempt"
    assert status["summary"]["index_deferred_recent_attempt_safe"] is True


def test_typing_nervous_refresh_latest_status_flags_timer_policy_and_stale_latest() -> None:
    now = dt.datetime.fromisoformat("2026-06-20T05:30:00+00:00")

    timer_status = typing_nervous_refresh_latest_status(
        latest=_fresh_status_latest(),
        latest_error=None,
        timer={"is_active": False, "is_enabled": True},
        service={},
        latest_path="latest.json",
        now=now,
    )
    assert timer_status["ok"] is False
    assert timer_status["status"] == "timer_inactive"

    unsafe_policy = _fresh_status_latest(
        policy={
            "raw_keylogging": True,
            "password_fields_captured": False,
            "widens_capture": False,
            "automatic_action": False,
            "internet_access": False,
        }
    )
    policy_status = typing_nervous_refresh_latest_status(
        latest=unsafe_policy,
        latest_error=None,
        timer=_active_timer(),
        service={},
        latest_path="latest.json",
        now=now,
    )
    assert policy_status["ok"] is False
    assert policy_status["status"] == "policy_violation"

    stale_status = typing_nervous_refresh_latest_status(
        latest=_fresh_status_latest(),
        latest_error=None,
        timer=_active_timer(),
        service={},
        latest_path="latest.json",
        max_age_sec=60,
        now=now,
    )
    assert stale_status["ok"] is False
    assert stale_status["status"] == "stale"


def test_typing_nervous_refresh_status_naming_requires_resource_fields_when_latest_exists() -> None:
    assert typing_nervous_refresh_status_naming({}) == {
        "ok": True,
        "latest_exists": False,
        "fields": {
            "index_resource_launch_attempted": False,
            "index_resource_allowed": False,
            "index_resource_blocked": False,
            "index_resource_denied": False,
            "index_resource_soft_gated": False,
        },
    }

    status = typing_nervous_refresh_status_naming(
        {
            "latest_exists": True,
            "index_resource_launch_attempted": False,
            "index_resource_allowed": False,
            "index_resource_blocked": False,
            "index_resource_denied": False,
            "index_resource_soft_gated": False,
        }
    )
    assert status["ok"] is True
    assert all(status["fields"].values())

    missing = typing_nervous_refresh_status_naming(
        {
            "latest_exists": True,
            "index_resource_launch_attempted": False,
            "index_resource_allowed": False,
            "index_resource_blocked": False,
            "index_resource_denied": False,
        }
    )
    assert missing["ok"] is False
    assert missing["fields"]["index_resource_soft_gated"] is False


def test_typing_nervous_processing_acceptance_preserves_resource_gate_and_debounce_contracts() -> None:
    processing = {"ok": False, "summary": {"facts_ready": True}}

    resource_gated = typing_nervous_processing_acceptance_status(
        nervous_processing=processing,
        nervous_refresh_status={"ok": True, "status": "resource_gated_index", "summary": {}},
    )
    assert resource_gated["ok"] is True
    assert resource_gated["resource_gated_index_accepted"] is True
    assert resource_gated["deferred_recent_index_accepted"] is False

    deferred_recent = typing_nervous_processing_acceptance_status(
        nervous_processing=processing,
        nervous_refresh_status={
            "ok": True,
            "status": "deferred_recent_index_attempt",
            "summary": {
                "index_deferred_recent_attempt": True,
                "index_previous_attempt_age_sec": 120,
                "index_min_interval_sec": 900,
                "index_records_lag": 5,
                "index_records_lag_tolerance": 4,
            },
        },
    )
    assert deferred_recent["ok"] is True
    assert deferred_recent["resource_gated_index_accepted"] is False
    assert deferred_recent["deferred_recent_index_accepted"] is True

    no_facts = typing_nervous_processing_acceptance_status(
        nervous_processing={"ok": False, "summary": {"facts_ready": False}},
        nervous_refresh_status={"ok": True, "status": "resource_gated_index", "summary": {}},
    )
    assert no_facts["ok"] is False
    assert no_facts["facts_ready"] is False

    unsafe_deferred = typing_nervous_processing_acceptance_status(
        nervous_processing=processing,
        nervous_refresh_status={
            "ok": True,
            "status": "deferred_recent_index_attempt",
            "summary": {
                "index_deferred_recent_attempt": True,
                "index_previous_attempt_age_sec": 950,
                "index_min_interval_sec": 900,
                "index_records_lag": 128,
                "index_records_lag_tolerance": 4,
            },
        },
    )
    assert unsafe_deferred["ok"] is False
    assert unsafe_deferred["deferred_recent_index_accepted"] is False


def test_typing_nervous_refresh_fact_state_preserves_recursive_fact_shape() -> None:
    state = typing_nervous_refresh_fact_state(
        facts_latest={
            "generated_at": "2026-06-20T05:00:00+00:00",
            "bundle": {
                "facts": [
                    {"source_id": "other_source", "summary": {"records": 99}},
                    {
                        "source_id": "typed_text_autolog",
                        "observed_at": "2026-06-20T04:59:30+00:00",
                        "summary": {"records": 2, "latest_text_event": "event-2"},
                        "process": {"summary": {"processed_records": 2, "skipped_records": 0}},
                        "entries": [
                            {"generated_at": "2026-06-20T04:58:00+00:00", "event_id": "event-1"},
                            "ignored",
                            {"generated_at": "2026-06-20T04:59:00+00:00", "event_id": "event-2"},
                        ],
                    },
                ]
            },
        },
        facts_error=None,
        latest_path=Path("/var/lib/abyss-machine/nervous/facts/latest.json"),
    )

    assert state == {
        "latest": "/var/lib/abyss-machine/nervous/facts/latest.json",
        "exists": True,
        "error": None,
        "generated_at": "2026-06-20T05:00:00+00:00",
        "typed_fact_exists": True,
        "typed_observed_at": "2026-06-20T04:59:30+00:00",
        "typed_summary": {"records": 2, "latest_text_event": "event-2"},
        "typed_process_summary": {"processed_records": 2, "skipped_records": 0},
        "typed_latest_entry_generated_at": "2026-06-20T04:59:00+00:00",
    }


def test_typing_nervous_refresh_fact_state_preserves_missing_fact_shape() -> None:
    state = typing_nervous_refresh_fact_state(
        facts_latest=None,
        facts_error="missing",
        latest_path="latest.json",
    )

    assert state == {
        "latest": "latest.json",
        "exists": False,
        "error": "missing",
        "generated_at": None,
        "typed_fact_exists": False,
        "typed_observed_at": None,
        "typed_summary": {},
        "typed_process_summary": {},
        "typed_latest_entry_generated_at": None,
    }


def test_typing_nervous_processing_status_document_reports_indexed_without_raw_text() -> None:
    facts_latest = {
        "generated_at": "2026-06-20T05:00:00+00:00",
        "facts": [
            {
                "source_id": "typed_text_autolog",
                "observed_at": "2026-06-20T04:59:30+00:00",
                "summary": {"latest_exists": True, "entries_indexed": 2, "parse_errors": 0},
                "process": {"summary": {"lanes": 1}},
                "entries": [
                    {
                        "event_id": "event-1",
                        "generated_at": "2026-06-20T04:59:00+00:00",
                        "text": "private text must not escape",
                    }
                ],
            }
        ],
    }
    index_latest = {
        "generated_at": "2026-06-20T05:01:00+00:00",
        "finished_at": "2026-06-20T05:01:00+00:00",
        "sources": {"enabled_private_connector_sources": ["typed_text_autolog"]},
        "summary": {"records_indexed": 5, "chunks_indexed": 7},
        "counts": {"fts_chunks": 7, "meta": {"built_at": "2026-06-20T05:01:00+00:00"}},
    }
    status = typing_nervous_processing_status_document(
        source={"enabled": True, "allowed": True, "group": "typing", "content": "typed_text"},
        facts_latest=facts_latest,
        facts_error=None,
        index_latest=index_latest,
        index_error=None,
        facts_latest_path="/var/lib/abyss-machine/nervous/facts/latest.json",
        index_latest_path="/var/lib/abyss-machine/nervous/search/latest.json",
        version="test-version",
        generated_at="2026-06-20T05:02:00+00:00",
    )

    assert typing_nervous_source_facts(facts_latest, "typed_text_autolog")[0]["source_id"] == "typed_text_autolog"
    assert status["schema"] == "abyss_machine_typing_nervous_processing_v1"
    assert status["version"] == "test-version"
    assert status["generated_at"] == "2026-06-20T05:02:00+00:00"
    assert status["ok"] is True
    assert status["status"] == "indexed"
    assert status["summary"]["facts_ready"] is True
    assert status["summary"]["index_ready"] is True
    assert status["summary"]["index_covers_latest_fact"] is True
    assert status["summary"]["typed_latest_entry_at"] == "2026-06-20T04:59:00+00:00"
    assert status["summary"]["entries_indexed"] == 2
    assert status["summary"]["records_indexed"] == 5
    assert status["summary"]["fts_chunks"] == 7
    assert status["search_index"]["source_enabled_in_index"] is True
    assert status["policy"]["raw_private_content"] is False
    assert "private text must not escape" not in str(status)


def test_typing_nervous_processing_status_document_distinguishes_stale_and_missing_index() -> None:
    facts_latest = {
        "generated_at": "2026-06-20T05:00:00+00:00",
        "facts": [
            {
                "source_id": "typed_text_autolog",
                "observed_at": "2026-06-20T05:00:00+00:00",
                "summary": {"latest_exists": True, "entries_indexed": 1, "parse_errors": 0},
                "entries": [{"event_id": "event-1", "generated_at": "2026-06-20T05:00:00+00:00"}],
            }
        ],
    }
    stale = typing_nervous_processing_status_document(
        source={"enabled": True, "allowed": True},
        facts_latest=facts_latest,
        facts_error=None,
        index_latest={
            "finished_at": "2026-06-20T04:59:00+00:00",
            "sources": {"enabled_sources": ["typed_text_autolog"]},
            "summary": {"records_indexed": 3, "fts_chunks": 3},
        },
        index_error=None,
        facts_latest_path="facts.json",
        index_latest_path="index.json",
    )
    missing = typing_nervous_processing_status_document(
        source={"enabled": True, "allowed": True},
        facts_latest=facts_latest,
        facts_error=None,
        index_latest={"summary": {"records_indexed": 3}, "counts": {"fts_chunks": 3}},
        index_error=None,
        facts_latest_path="facts.json",
        index_latest_path="index.json",
    )

    assert stale["ok"] is False
    assert stale["status"] == "facts_ready_index_stale"
    assert stale["summary"]["facts_ready"] is True
    assert stale["summary"]["index_covers_latest_fact"] is False
    assert missing["ok"] is False
    assert missing["status"] == "facts_ready_index_missing"
    assert missing["search_index"]["source_enabled_in_index"] is False


def test_cli_typing_nervous_processing_status_uses_module_document(monkeypatch) -> None:
    source = {"enabled": True, "allowed": True, "group": "typing", "content": "typed_text"}
    facts_latest = {
        "generated_at": "2026-06-20T05:00:00+00:00",
        "facts": [
            {
                "source_id": "typed_text_autolog",
                "observed_at": "2026-06-20T04:59:30+00:00",
                "summary": {"latest_exists": True, "entries_indexed": 2, "parse_errors": 0},
                "process": {"summary": {"lanes": 1}},
                "entries": [{"event_id": "event-1", "generated_at": "2026-06-20T04:59:00+00:00"}],
            }
        ],
    }
    index_latest = {
        "generated_at": "2026-06-20T05:01:00+00:00",
        "finished_at": "2026-06-20T05:01:00+00:00",
        "sources": {"enabled_private_connector_sources": ["typed_text_autolog"]},
        "summary": {"records_indexed": 5, "chunks_indexed": 7},
        "counts": {"fts_chunks": 7, "meta": {"built_at": "2026-06-20T05:01:00+00:00"}},
    }

    def fake_load_json_document(path: Path) -> tuple[dict, None]:
        if path == cli.NERVOUS_FACTS_LATEST_PATH:
            return facts_latest, None
        if path == cli.NERVOUS_SEARCH_INDEX_LATEST_PATH:
            return index_latest, None
        return {}, None

    monkeypatch.setattr(cli, "nervous_source_lookup", lambda source_id: source)
    monkeypatch.setattr(cli, "load_json_document", fake_load_json_document)
    monkeypatch.setattr(cli, "nervous_index_db_counts", lambda: {"fts_chunks": 0})
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-20T05:02:00+00:00")

    assert cli.typing_nervous_processing_status() == typing_nervous_processing_status_document(
        source=source,
        facts_latest=facts_latest,
        facts_error=None,
        index_latest=index_latest,
        index_error=None,
        facts_latest_path=cli.NERVOUS_FACTS_LATEST_PATH,
        index_latest_path=cli.NERVOUS_SEARCH_INDEX_LATEST_PATH,
        counts_fallback=index_latest["counts"],
        extra_index_source_ids=set(),
        version=cli.VERSION,
        generated_at="2026-06-20T05:02:00+00:00",
    )


def test_cli_exports_typing_nervous_refresh_helpers_from_module() -> None:
    assert cli.typing_nervous_index_resource_gated is typing_nervous_index_resource_gated
    assert cli.typing_nervous_deferred_recent_index_safe is typing_nervous_deferred_recent_index_safe
    assert cli.typing_nervous_processing_acceptance_status is typing_nervous_processing_acceptance_status
    assert cli.build_typing_nervous_processing_status_document is typing_nervous_processing_status_document
    assert cli.typing_nervous_source_facts is typing_nervous_source_facts
    assert cli.typing_nervous_recent_index_debounce_safe is typing_nervous_recent_index_debounce_safe
    assert cli.typing_nervous_refresh_needed is typing_nervous_refresh_needed
    assert cli.typing_nervous_refresh_document is typing_nervous_refresh_document
    assert cli.typing_nervous_refresh_index_attempt_context is typing_nervous_refresh_index_attempt_context
    assert cli.typing_nervous_refresh_snapshot_action is typing_nervous_refresh_snapshot_action
    assert cli.typing_nervous_refresh_index_action is typing_nervous_refresh_index_action
    assert cli.typing_nervous_refresh_index_retry_action is typing_nervous_refresh_index_retry_action
    assert cli.typing_nervous_refresh_synthesis_action is typing_nervous_refresh_synthesis_action
    assert cli.typing_nervous_refresh_final_context is typing_nervous_refresh_final_context
    assert cli.build_typing_nervous_refresh_fact_state is typing_nervous_refresh_fact_state
    assert cli.build_typing_nervous_refresh_latest_status is typing_nervous_refresh_latest_status
    assert cli.typing_nervous_refresh_status_naming is typing_nervous_refresh_status_naming

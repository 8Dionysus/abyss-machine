#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import inspect
import sys

from _common import REPO_ROOT, fail, ok, require


SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli  # noqa: E402
from abyss_machine.typing_nervous_refresh import (  # noqa: E402
    TYPING_NERVOUS_INDEX_RESOURCE_GATE_REASONS,
    typing_nervous_deferred_recent_index_safe,
    typing_nervous_index_resource_gated,
    typing_nervous_refresh_index_action,
    typing_nervous_refresh_final_context,
    typing_nervous_refresh_index_attempt_context,
    typing_nervous_refresh_index_retry_action,
    typing_nervous_refresh_latest_status,
    typing_nervous_recent_index_debounce_safe,
    typing_nervous_refresh_needed,
    typing_nervous_refresh_snapshot_action,
    typing_nervous_refresh_synthesis_action,
)


def main() -> int:
    failures: list[str] = []

    require(
        "indexing_unattended_swap_used_pressure" in TYPING_NERVOUS_INDEX_RESOURCE_GATE_REASONS,
        "swap-used pressure must remain an accepted soft resource gate",
        failures,
    )
    require(
        "indexing_unattended_swap_free_below_floor" in TYPING_NERVOUS_INDEX_RESOURCE_GATE_REASONS,
        "swap-free floor must remain an accepted soft resource gate",
        failures,
    )
    require(
        typing_nervous_index_resource_gated(
            {
                "ok": False,
                "blocked_reasons": ["indexing_unattended_swap_used_pressure"],
                "denied_reasons": [],
            }
        ),
        "known soft resource block should be accepted",
        failures,
    )
    require(
        not typing_nervous_index_resource_gated(
            {
                "ok": False,
                "blocked_reasons": ["indexing_unattended_swap_used_pressure"],
                "denied_reasons": ["storage_denied"],
            }
        ),
        "denied resource launch must not be accepted as soft-gated",
        failures,
    )

    bounded = {
        "index_deferred_recent_attempt": True,
        "index_previous_attempt_age_sec": 225,
        "index_min_interval_sec": 900,
        "index_records_lag": 6,
        "index_records_lag_tolerance": 4,
        "global_index_records_lag": 6,
        "global_index_records_lag_tolerance": 4,
    }
    require(
        typing_nervous_deferred_recent_index_safe(bounded),
        "bounded recent-index debounce should be accepted",
        failures,
    )
    unbounded = dict(bounded, index_records_lag=65, global_index_records_lag=65)
    require(
        not typing_nervous_deferred_recent_index_safe(unbounded),
        "unbounded recent-index lag should not be accepted",
        failures,
    )

    common = {
        "index_needed": True,
        "force_index": False,
        "previous_index_launch_attempted": True,
        "previous_index_attempt_age_sec": 725,
        "index_min_interval_sec": 900,
        "index_records_lag_tolerance": 4,
        "index_stale": True,
    }
    require(
        typing_nervous_recent_index_debounce_safe(**common, index_records_lag=6),
        "bounded recent-index debounce should defer safely",
        failures,
    )
    require(
        not typing_nervous_recent_index_debounce_safe(**common, index_records_lag=17),
        "large lag should bypass recent-index debounce",
        failures,
    )
    now = dt.datetime.fromisoformat("2026-06-20T05:10:00+00:00")
    attempt_context = typing_nervous_refresh_index_attempt_context(
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
        now=now,
    )
    require(
        attempt_context.get("previous_refresh_age_sec") == 300.0
        and attempt_context.get("previous_index_attempt_age_sec") == 525.0
        and attempt_context.get("previous_index_attempt_age_basis") == "previous_deferred_attempt_age_plus_refresh_age",
        "index attempt context must accumulate previous deferred attempt age",
        failures,
    )
    require(
        attempt_context.get("recent_index_debounce_candidate") is True
        and attempt_context.get("index_deferred_recent_attempt") is False
        and attempt_context.get("index_debounce_bypassed_for_lag") is True,
        "large lag should bypass deferred recent-index attempt in context",
        failures,
    )
    forced_context = typing_nervous_refresh_index_attempt_context(
        index_needed=True,
        force_index=True,
        previous_refresh={
            "finished_at": "2026-06-20T05:00:00+00:00",
            "summary": {"index_resource_launch_attempted": True},
        },
        index_status={"freshness": {"stale": False}},
        assessment={"records_lag": 6, "index_stale": True},
        index_min_interval_sec=900,
        now=now,
    )
    require(
        forced_context.get("debounce_candidate_records_lag") == 6
        and forced_context.get("debounce_candidate_records_lag_tolerance") == 4
        and forced_context.get("debounce_candidate_index_stale") is True
        and forced_context.get("index_deferred_recent_attempt") is False,
        "forced index context must use assessment fallback without deferring",
        failures,
    )
    snapshot_action = typing_nervous_refresh_snapshot_action(
        snapshot={"ok": True, "generated_at": "2026-06-20T05:00:00+00:00", "summary": {"facts": 3}},
        force_snapshot=False,
    )
    require(
        snapshot_action.get("action") == "nervous_snapshot"
        and snapshot_action.get("reason") == "typed_event_or_process_not_in_facts"
        and snapshot_action.get("summary") == {"facts": 3},
        "snapshot action builder must preserve public action shape",
        failures,
    )
    require(
        typing_nervous_refresh_snapshot_action(snapshot=None, force_snapshot=False).get("status") == "not_needed",
        "snapshot action builder must preserve not-needed shape",
        failures,
    )
    deferred_index_action = typing_nervous_refresh_index_action(
        action_status="deferred_recent_index_attempt",
        previous_refresh={"finished_at": "2026-06-20T05:00:15+00:00"},
        previous_index_attempt_age_sec=225,
        index_min_interval_sec=900,
    )
    require(
        deferred_index_action.get("reason") == "typing_refresh_index_debounce"
        and deferred_index_action.get("previous_refresh_finished_at") == "2026-06-20T05:00:15+00:00"
        and deferred_index_action.get("previous_attempt_age_sec") == 225,
        "index action builder must preserve recent-attempt debounce action shape",
        failures,
    )
    running_index_action = typing_nervous_refresh_index_action(
        action_status="deferred_existing_index_build_running",
        index_service={"active": "active"},
        dynamic_index_units=["abyss-machine-indexing@1.service"],
    )
    require(
        running_index_action.get("status") == "deferred_existing_index_build_running"
        and running_index_action.get("service") == {"active": "active"}
        and running_index_action.get("dynamic_resource_units") == ["abyss-machine-indexing@1.service"],
        "index action builder must preserve existing-running action shape",
        failures,
    )
    launch_index_action = typing_nervous_refresh_index_action(
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
    require(
        launch_index_action.get("status") == "deferred_existing_index_lock"
        and launch_index_action.get("reason") == "facts_or_index_freshness_required_refresh"
        and launch_index_action.get("resource_decision") == "blocked"
        and launch_index_action.get("resource_sample_thermal") is False
        and launch_index_action.get("debounce_bypassed_for_lag") is True,
        "index action builder must preserve launch action shape",
        failures,
    )
    retry_index_action = typing_nervous_refresh_index_retry_action(
        {
            "ok": True,
            "blocked_reasons": [],
            "denied_reasons": [],
            "plan": {"decision": "allowed", "request": {"sample_thermal": True}},
            "elapsed_sec": 4.25,
            "execution": {"returncode": 0},
        }
    )
    require(
        retry_index_action.get("status") == "retry_after_typed_fact_changed_during_index"
        and retry_index_action.get("reason") == "first_index_build_finished_before_latest_typed_fact"
        and retry_index_action.get("resource_decision") == "allowed"
        and retry_index_action.get("resource_sample_thermal") is True,
        "index retry action builder must preserve retry action shape",
        failures,
    )
    synthesis_action = typing_nervous_refresh_synthesis_action(
        synthesis_needed=True,
        index_needed=True,
        final_context={"synthesis_action_status": "unused"},
        synthesis_refresh={"ok": True, "candidate_id": "candidate-1", "summary": {"facts": 3}},
        synthesis_validation={"ok": True, "summary": {"checks": 4}},
    )
    require(
        synthesis_action.get("reason") == "typed_facts_index_refresh_completed"
        and synthesis_action.get("candidate_id") == "candidate-1"
        and synthesis_action.get("validation_summary") == {"checks": 4},
        "synthesis action builder must preserve run action shape",
        failures,
    )
    synthesis_deferred = typing_nervous_refresh_synthesis_action(
        synthesis_needed=False,
        index_needed=True,
        final_context={"synthesis_action_status": "deferred_index_pending"},
    )
    require(
        synthesis_deferred.get("status") == "deferred_index_pending"
        and synthesis_deferred.get("reason") == "index_refresh_not_confirmed_fresh_yet",
        "synthesis action builder must preserve deferred action shape",
        failures,
    )
    final_context = typing_nervous_refresh_final_context(
        process={"ok": True, "status": "ok", "summary": {"records_processed": 5, "lanes": 2}},
        latest_event={"generated_at": "2026-06-20T05:00:00+00:00"},
        assessment_before={"snapshot_needed": False},
        processing_after={"ok": True},
        fact_after_snapshot={"exists": True, "typed_fact_exists": True},
        index_after={"freshness": {"records_lag": 9, "records_lag_tolerance": 4, "stale": True}},
        index_launch=None,
        index_needed=True,
        force_index=False,
        index_deferred_recent_attempt=False,
        index_service_running=False,
        index_launch_already_running=False,
        previous_index_attempt_age_sec=225,
        previous_index_attempt_age_basis="previous_refresh_finished_at",
        previous_refresh_age_sec=300.0,
        index_min_interval_sec=900.0,
        recent_index_debounce_candidate=True,
        index_debounce_bypassed_for_lag=False,
        debounce_candidate_records_lag=6,
        debounce_candidate_records_lag_tolerance=4,
        synthesis_refresh={"ok": True},
        synthesis_validation={"ok": True},
    )
    require(
        final_context.get("ok") is True
        and final_context.get("status") == "fresh"
        and final_context.get("summary", {}).get("index_records_lag") == 0
        and final_context.get("summary", {}).get("global_index_records_lag") == 9,
        "final context must report fresh typed processing while preserving global lag",
        failures,
    )
    degraded_context = typing_nervous_refresh_final_context(
        process={"ok": True, "status": "ok", "summary": {"records_processed": 5, "lanes": 2}},
        latest_event={"generated_at": "2026-06-20T05:00:00+00:00"},
        assessment_before={"snapshot_needed": False},
        processing_after={"ok": True},
        fact_after_snapshot={"exists": True, "typed_fact_exists": True},
        index_after={"freshness": {"records_lag": 0, "records_lag_tolerance": 4, "stale": False}},
        index_launch=None,
        index_needed=True,
        force_index=False,
        index_deferred_recent_attempt=False,
        index_service_running=False,
        index_launch_already_running=False,
        previous_index_attempt_age_sec=225,
        previous_index_attempt_age_basis="previous_refresh_finished_at",
        previous_refresh_age_sec=300.0,
        index_min_interval_sec=900.0,
        recent_index_debounce_candidate=False,
        index_debounce_bypassed_for_lag=False,
        debounce_candidate_records_lag=0,
        debounce_candidate_records_lag_tolerance=4,
        synthesis_refresh={"ok": True},
        synthesis_validation={"ok": False},
    )
    require(
        degraded_context.get("ok") is False
        and degraded_context.get("status") == "degraded"
        and degraded_context.get("synthesis_ok_for_status") is False,
        "final context must degrade fresh processing when synthesis validation fails",
        failures,
    )
    gated_context = typing_nervous_refresh_final_context(
        process={"ok": True, "status": "ok", "summary": {"records_processed": 5, "lanes": 2}},
        latest_event={"generated_at": "2026-06-20T05:00:00+00:00"},
        assessment_before={"snapshot_needed": True},
        processing_after={"ok": False},
        fact_after_snapshot={"exists": True, "typed_fact_exists": True},
        index_after={"freshness": {"records_lag": 9, "records_lag_tolerance": 4, "stale": True}},
        index_launch={
            "ok": False,
            "blocked_reasons": ["indexing_unattended_swap_used_pressure"],
            "denied_reasons": [],
            "plan": {"decision": "blocked", "request": {"sample_thermal": False}},
        },
        index_needed=True,
        force_index=False,
        index_deferred_recent_attempt=False,
        index_service_running=False,
        index_launch_already_running=False,
        previous_index_attempt_age_sec=225,
        previous_index_attempt_age_basis="previous_refresh_finished_at",
        previous_refresh_age_sec=300.0,
        index_min_interval_sec=900.0,
        recent_index_debounce_candidate=False,
        index_debounce_bypassed_for_lag=False,
        debounce_candidate_records_lag=9,
        debounce_candidate_records_lag_tolerance=4,
    )
    require(
        gated_context.get("ok") is True
        and gated_context.get("status") == "resource_gated_index"
        and gated_context.get("index_resource_gated") is True
        and gated_context.get("synthesis_action_status") == "deferred_resource_gated_index",
        "final context must preserve soft resource-gated index acceptance",
        failures,
    )
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
    require(assessment.get("snapshot_needed") is False, "covered facts must not request snapshot", failures)
    require(assessment.get("index_needed") is False, "fresh processing must not request index", failures)
    stale_assessment = typing_nervous_refresh_needed(
        latest_event={"generated_at": "2026-06-20T05:00:00+00:00"},
        fact_state={
            "exists": True,
            "typed_fact_exists": True,
            "generated_at": "2026-06-20T04:59:00+00:00",
            "typed_process_summary": {"records_processed": 4, "lanes": 2},
        },
        process={"summary": {"records_processed": 5, "lanes": 3}},
        index_status={"freshness": {"records_lag": "7", "records_lag_stale": True}},
        processing={"ok": False},
    )
    require(stale_assessment.get("snapshot_needed") is True, "stale facts must request snapshot", failures)
    require(stale_assessment.get("index_needed") is True, "stale index or processing must request index", failures)
    require(stale_assessment.get("records_lag") == 7, "records lag must be coerced to int", failures)

    latest_base = {
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
    timer = {"is_active": True, "is_enabled": True}
    now = dt.datetime.fromisoformat("2026-06-20T05:01:00+00:00")
    latest_status = typing_nervous_refresh_latest_status(
        latest=latest_base,
        latest_error=None,
        timer=timer,
        service={"is_active": False},
        latest_path="/var/lib/abyss-machine/typing-nervous-refresh/latest.json",
        max_age_sec=900,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-20T05:01:00+00:00",
        now=now,
    )
    require(latest_status.get("ok") is True, "fresh latest-status document should be ok", failures)
    require(latest_status.get("status") == "fresh", "fresh latest-status should remain fresh", failures)
    require(
        latest_status.get("summary", {}).get("latest_age_sec") == 45.0,
        "latest-status age must be computed from finished_at",
        failures,
    )
    deferred_status = typing_nervous_refresh_latest_status(
        latest={
            **latest_base,
            "status": "deferred_recent_index_attempt",
            "summary": {
                "index_deferred_recent_attempt": True,
                "index_previous_attempt_age_sec": 225,
                "index_min_interval_sec": 900,
                "index_records_lag": 6,
                "index_records_lag_tolerance": 4,
                "global_index_records_lag": 6,
                "global_index_records_lag_tolerance": 4,
            },
        },
        latest_error=None,
        timer=timer,
        service={},
        latest_path="latest.json",
        now=now,
    )
    require(
        deferred_status.get("ok") is True
        and deferred_status.get("status") == "deferred_recent_index_attempt"
        and deferred_status.get("summary", {}).get("index_deferred_recent_attempt_safe") is True,
        "bounded deferred recent-index latest-status should remain acceptable",
        failures,
    )
    require(
        typing_nervous_refresh_latest_status(
            latest=latest_base,
            latest_error=None,
            timer={"is_active": False, "is_enabled": True},
            service={},
            latest_path="latest.json",
            now=now,
        ).get("status")
        == "timer_inactive",
        "inactive timer must be reported by latest-status classifier",
        failures,
    )

    require(
        cli.typing_nervous_index_resource_gated is typing_nervous_index_resource_gated,
        "CLI must re-export module resource-gate helper",
        failures,
    )
    require(
        cli.typing_nervous_deferred_recent_index_safe is typing_nervous_deferred_recent_index_safe,
        "CLI must re-export module deferred-index helper",
        failures,
    )
    require(
        cli.typing_nervous_recent_index_debounce_safe is typing_nervous_recent_index_debounce_safe,
        "CLI must re-export module recent-index debounce helper",
        failures,
    )
    require(
        cli.typing_nervous_refresh_needed is typing_nervous_refresh_needed,
        "CLI must re-export module refresh assessment helper",
        failures,
    )
    require(
        cli.typing_nervous_refresh_index_attempt_context is typing_nervous_refresh_index_attempt_context,
        "CLI must re-export module index attempt context helper",
        failures,
    )
    require(
        cli.typing_nervous_refresh_snapshot_action is typing_nervous_refresh_snapshot_action,
        "CLI must re-export module snapshot action helper",
        failures,
    )
    require(
        cli.typing_nervous_refresh_index_action is typing_nervous_refresh_index_action,
        "CLI must re-export module index action helper",
        failures,
    )
    require(
        cli.typing_nervous_refresh_index_retry_action is typing_nervous_refresh_index_retry_action,
        "CLI must re-export module index retry action helper",
        failures,
    )
    require(
        cli.typing_nervous_refresh_synthesis_action is typing_nervous_refresh_synthesis_action,
        "CLI must re-export module synthesis action helper",
        failures,
    )
    require(
        cli.typing_nervous_refresh_final_context is typing_nervous_refresh_final_context,
        "CLI must re-export module final context helper",
        failures,
    )
    require(
        cli.build_typing_nervous_refresh_latest_status is typing_nervous_refresh_latest_status,
        "CLI must import module latest-status builder",
        failures,
    )

    cli_source = (REPO_ROOT / "src" / "abyss_machine" / "cli.py").read_text(encoding="utf-8")
    for name in (
        "typing_nervous_index_resource_gated",
        "typing_nervous_deferred_recent_index_safe",
        "typing_nervous_recent_index_debounce_safe",
        "typing_nervous_refresh_needed",
        "typing_nervous_refresh_index_attempt_context",
        "typing_nervous_refresh_snapshot_action",
        "typing_nervous_refresh_index_action",
        "typing_nervous_refresh_index_retry_action",
        "typing_nervous_refresh_synthesis_action",
        "typing_nervous_refresh_final_context",
    ):
        require(f"def {name}" not in cli_source, f"CLI must not redefine {name}", failures)
    status_wrapper_source = inspect.getsource(cli.typing_nervous_refresh_latest_status)
    require(
        "build_typing_nervous_refresh_latest_status" in status_wrapper_source,
        "CLI latest-status wrapper must delegate to module builder",
        failures,
    )
    require(
        "latest_policy" not in status_wrapper_source and "acceptable_latest" not in status_wrapper_source,
        "CLI latest-status wrapper must not keep status classification logic",
        failures,
    )
    refresh_source = inspect.getsource(cli.typing_nervous_refresh)
    require(
        "typing_nervous_refresh_index_attempt_context" in refresh_source,
        "CLI refresh orchestration must delegate index attempt context to module helper",
        failures,
    )
    require(
        "previous_refresh_summary" not in refresh_source,
        "CLI refresh orchestration must not keep previous-refresh debounce context parsing",
        failures,
    )
    require(
        "typing_nervous_refresh_final_context" in refresh_source,
        "CLI refresh orchestration must delegate final status summary to module helper",
        failures,
    )
    for name in (
        "typing_nervous_refresh_snapshot_action",
        "typing_nervous_refresh_index_action",
        "typing_nervous_refresh_index_retry_action",
        "typing_nervous_refresh_synthesis_action",
    ):
        require(name in refresh_source, f"CLI refresh orchestration must use {name}", failures)
    for stale_marker in (
        '"reason": "typed_event_or_process_not_in_facts"',
        '"reason": "typing_refresh_index_debounce"',
        '"reason": "facts_or_index_freshness_required_refresh"',
        '"status": "retry_after_typed_fact_changed_during_index"',
        '"reason": "typed_facts_index_refresh_completed"',
    ):
        require(stale_marker not in refresh_source, f"CLI refresh must not inline {stale_marker}", failures)
    require(
        "index_resource_launch_attempted = isinstance" not in refresh_source
        and "global_index_records_lag = nested_get(index_after" not in refresh_source,
        "CLI refresh orchestration must not keep final status summary assembly",
        failures,
    )

    if failures:
        return fail("typing/nervous refresh logic validation failed", failures)
    return ok("typing/nervous refresh logic validation passed")


if __name__ == "__main__":
    raise SystemExit(main())

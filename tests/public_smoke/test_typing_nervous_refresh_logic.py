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
    typing_nervous_refresh_index_attempt_context,
    typing_nervous_refresh_latest_status,
    typing_nervous_recent_index_debounce_safe,
    typing_nervous_refresh_needed,
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


def test_cli_exports_typing_nervous_refresh_helpers_from_module() -> None:
    assert cli.typing_nervous_index_resource_gated is typing_nervous_index_resource_gated
    assert cli.typing_nervous_deferred_recent_index_safe is typing_nervous_deferred_recent_index_safe
    assert cli.typing_nervous_recent_index_debounce_safe is typing_nervous_recent_index_debounce_safe
    assert cli.typing_nervous_refresh_needed is typing_nervous_refresh_needed
    assert cli.typing_nervous_refresh_index_attempt_context is typing_nervous_refresh_index_attempt_context
    assert cli.build_typing_nervous_refresh_latest_status is typing_nervous_refresh_latest_status

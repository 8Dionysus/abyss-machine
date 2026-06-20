from __future__ import annotations

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


def test_cli_exports_typing_nervous_refresh_helpers_from_module() -> None:
    assert cli.typing_nervous_index_resource_gated is typing_nervous_index_resource_gated
    assert cli.typing_nervous_deferred_recent_index_safe is typing_nervous_deferred_recent_index_safe
    assert cli.typing_nervous_recent_index_debounce_safe is typing_nervous_recent_index_debounce_safe
    assert cli.typing_nervous_refresh_needed is typing_nervous_refresh_needed

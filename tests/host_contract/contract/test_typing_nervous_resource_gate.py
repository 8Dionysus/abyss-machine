from __future__ import annotations

import pytest


@pytest.mark.quick
@pytest.mark.contract
@pytest.mark.regression
def test_typing_nervous_refresh_accepts_unattended_swap_pressure_as_resource_gate(abyss_machine_module):
    for reason in {
        "indexing_unattended_swap_used_pressure",
        "indexing_unattended_swap_free_below_floor",
    }:
        assert (
            abyss_machine_module.typing_nervous_index_resource_gated(
                {"ok": False, "blocked_reasons": [reason], "denied_reasons": []}
            )
            is True
        )


@pytest.mark.quick
@pytest.mark.contract
@pytest.mark.regression
def test_typing_nervous_refresh_rejects_unknown_or_denied_resource_gate(abyss_machine_module):
    assert (
        abyss_machine_module.typing_nervous_index_resource_gated(
            {"ok": False, "blocked_reasons": ["unexpected_block"], "denied_reasons": []}
        )
        is False
    )
    assert (
        abyss_machine_module.typing_nervous_index_resource_gated(
            {
                "ok": False,
                "blocked_reasons": ["indexing_unattended_swap_used_pressure"],
                "denied_reasons": ["storage_denied"],
            }
        )
        is False
    )
    assert (
        abyss_machine_module.typing_nervous_index_resource_gated(
            {"ok": True, "blocked_reasons": ["indexing_unattended_swap_used_pressure"], "denied_reasons": []}
        )
        is False
    )


@pytest.mark.quick
@pytest.mark.contract
@pytest.mark.regression
def test_typing_nervous_refresh_accepts_bounded_recent_index_debounce(abyss_machine_module):
    assert (
        abyss_machine_module.typing_nervous_deferred_recent_index_safe(
            {
                "index_deferred_recent_attempt": True,
                "index_previous_attempt_age_sec": 225,
                "index_min_interval_sec": 900,
                "index_records_lag": 6,
                "index_records_lag_tolerance": 4,
                "index_stale": True,
                "global_index_records_lag": 6,
                "global_index_records_lag_tolerance": 4,
                "global_index_stale": True,
            }
        )
        is True
    )


@pytest.mark.quick
@pytest.mark.contract
@pytest.mark.regression
def test_typing_nervous_refresh_rejects_unbounded_recent_index_debounce(abyss_machine_module):
    base_summary = {
        "index_deferred_recent_attempt": True,
        "index_previous_attempt_age_sec": 225,
        "index_min_interval_sec": 900,
        "index_records_lag": 65,
        "index_records_lag_tolerance": 4,
        "index_stale": True,
        "global_index_records_lag": 65,
        "global_index_records_lag_tolerance": 4,
        "global_index_stale": True,
    }
    assert abyss_machine_module.typing_nervous_deferred_recent_index_safe(base_summary) is False

    outside_debounce = dict(base_summary)
    outside_debounce["index_previous_attempt_age_sec"] = 900
    outside_debounce["index_records_lag"] = 6
    outside_debounce["global_index_records_lag"] = 6
    assert abyss_machine_module.typing_nervous_deferred_recent_index_safe(outside_debounce) is False


@pytest.mark.quick
@pytest.mark.contract
@pytest.mark.regression
def test_typing_nervous_refresh_bypasses_debounce_when_lag_exceeds_safe_allowance(abyss_machine_module):
    common = {
        "index_needed": True,
        "force_index": False,
        "previous_index_launch_attempted": True,
        "previous_index_attempt_age_sec": 725,
        "index_min_interval_sec": 900,
        "index_records_lag_tolerance": 4,
        "index_stale": True,
    }
    assert (
        abyss_machine_module.typing_nervous_recent_index_debounce_safe(
            **common,
            index_records_lag=6,
        )
        is True
    )
    assert (
        abyss_machine_module.typing_nervous_recent_index_debounce_safe(
            **common,
            index_records_lag=17,
        )
        is False
    )

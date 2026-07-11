from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import memory_controller_contracts as contracts


def local_route(path: str, *, method: str, expect: dict | None = None) -> dict:
    return {
        "kind": "local_http_json_v1",
        "url": f"http://127.0.0.1:5405{path}",
        "method": method,
        "timeout_ms": 1000,
        "maximum_response_bytes": 65536,
        "expect": {"json_equals": expect or {}},
    }


def sample(
    epoch: float,
    *,
    available_mib: float = 16_000.0,
    psi_some_total_usec: int = 0,
    psi_full_total_usec: int = 0,
    major_faults: int = 0,
    zram_resident_mib: float = 3_000.0,
    swap_used_mib: float = 7_000.0,
    pswpin: int = 0,
    pswpout: int = 0,
) -> dict:
    return {
        "epoch": epoch,
        "mem_total_mib": 32_000.0,
        "mem_available_mib": available_mib,
        "swap_total_mib": 20_000.0,
        "swap_used_mib": swap_used_mib,
        "swap_free_mib": 20_000.0 - swap_used_mib,
        "zram_data_mib": swap_used_mib,
        "zram_resident_mib": zram_resident_mib,
        "zram_allocator_metadata_overhead_mib": 100.0,
        "zram_physical_savings_mib": max(0.0, swap_used_mib - zram_resident_mib),
        "zram_incompressible_mib": 500.0,
        "zram_backing_write_mib": 0.0,
        "psi_some_avg10": 0.0,
        "psi_full_avg10": 0.0,
        "psi_some_total_usec": psi_some_total_usec,
        "psi_full_total_usec": psi_full_total_usec,
        "pgmajfault": major_faults,
        "pswpin": pswpin,
        "pswpout": pswpout,
        "oom_kill": 0,
    }


def managed_model(*, busy: bool = False, protected: bool = False) -> dict:
    return {
        "id": "model:reranker",
        "owner": "abyss-machine-ai",
        "role": "managed_model",
        "importance": "normal",
        "posture": "background",
        "statefulness": "reconstructable",
        "protected": protected,
        "memory": {"expected_mib": 3_000.0, "observed_mib": 2_800.0},
        "activity": {"state": "busy" if busy else "idle", "confidence": "high"},
        "sla": {"rehydrate_p95_ms": 1_200.0, "max_cold_start_ms": 3_000.0},
        "lifecycle": {
            "activity": local_route("/health", method="GET", expect={"active_requests": 0}),
            "dehydrate": local_route("/admin/unload", method="POST", expect={"ok": True}),
            "rehydrate": local_route("/admin/rehydrate", method="POST", expect={"ok": True}),
            "health": local_route("/health", method="GET", expect={"ok": True, "service": "rerank-api"}),
            "rollback": local_route("/admin/rehydrate", method="POST", expect={"ok": True}),
        },
        "enrollment": {
            "id": "enroll-reranker",
            "status": "enrolled",
            "owner_approved": True,
            "allowed_actions": ["managed_dehydrate"],
        },
        "measurement": {
            "kind": "cgroup_v2_v1",
            "uid": os.getuid(),
            "path": f"/sys/fs/cgroup/user.slice/user-{os.getuid()}.slice/user@{os.getuid()}.service/app.slice/reranker.scope",
        },
        "residency": {"minimum_sec": 60, "cooldown_sec": 300},
        "registry_status": "exact",
        "metadata": {"registry_source": "static", "registry_trusted_for_lifecycle": True},
    }


def test_unknown_workload_defaults_to_preserve() -> None:
    resolved = contracts.resolve_workload({"workloads": [], "rules": []}, {"id": "pid:42", "comm": "mystery"})

    assert resolved["registry_status"] == "unknown_preserve"
    assert resolved["importance"] == "unknown"
    assert resolved["protected"] is True
    assert resolved["allowed_actions"] == ["observe"]


def test_policy_validation_rejects_malformed_numbers_and_broken_ordering() -> None:
    malformed = contracts.default_policy()
    malformed["forecast"]["stall_persistence"]["active_sec"] = "soon"
    malformed_result = contracts.validate_policy(malformed)
    unfair = contracts.default_policy()
    unfair["queue"]["starvation_sec"] = 40
    unfair["queue"]["maximum_wait_sec"] = 120
    unfair_result = contracts.validate_policy(unfair)

    assert malformed_result["valid"] is False
    assert "policy_number_invalid:forecast.stall_persistence.active_sec" in malformed_result["issues"]
    assert unfair_result["valid"] is False
    assert "queue_starvation_window_exceeds_maximum_wait" in unfair_result["issues"]


def test_lifecycle_contract_requires_owner_health_and_rollback() -> None:
    raw = managed_model()
    raw["owner"] = ""
    raw["lifecycle"].pop("health")
    raw["lifecycle"].pop("rollback")

    result = contracts.validate_workload_contract(raw)

    assert result["valid"] is False
    assert set(result["issues"]) >= {"owner_required", "health_route_required", "rollback_route_required"}


def test_lifecycle_routes_reject_remote_generic_and_wrong_method_targets() -> None:
    raw = managed_model()
    raw["lifecycle"]["dehydrate"] = {
        "kind": "command",
        "url": "https://example.com/unload",
        "method": "GET",
    }

    result = contracts.validate_workload_contract(raw)

    assert result["valid"] is False
    assert set(result["issues"]) >= {
        "lifecycle_route_invalid:dehydrate:route_kind_invalid",
        "lifecycle_route_invalid:dehydrate:route_scheme_must_be_http",
        "lifecycle_route_invalid:dehydrate:route_host_must_be_loopback_literal",
        "lifecycle_route_invalid:dehydrate:route_method_must_be_post",
    }


def test_route_expectations_are_exact_and_fail_closed() -> None:
    route = local_route("/health", method="GET", expect={"ok": True, "active_requests": 0})

    accepted = contracts.evaluate_route_response(route, {"ok": True, "active_requests": 0, "loaded": True})
    rejected = contracts.evaluate_route_response(route, {"ok": True, "active_requests": 1})

    assert accepted["ok"] is True
    assert rejected["ok"] is False
    assert rejected["mismatches"] == [{"path": "active_requests", "expected": 0, "observed": 1, "present": True}]


def test_mutating_contract_requires_health_identity_not_only_generic_ok() -> None:
    raw = managed_model()
    raw["lifecycle"]["health"] = local_route("/health", method="GET", expect={"ok": True})

    result = contracts.validate_workload_contract(raw)

    assert result["valid"] is False
    assert "health_identity_expectation_required" in result["issues"]


def test_registry_exact_identity_overrides_fallback_rule() -> None:
    registry = {
        "workloads": [managed_model()],
        "rules": [
            {
                "id": "protect-model-role",
                "match": {"role": ["managed_model"]},
                "contract": {"owner": "fallback", "importance": "protected", "protected": True},
            }
        ],
    }

    resolved = contracts.resolve_workload(registry, {"id": "model:reranker", "role": "managed_model"})

    assert resolved["registry_status"] == "exact"
    assert resolved["owner"] == "abyss-machine-ai"
    assert resolved["protected"] is False


def test_observation_cannot_override_registry_owner_or_protection() -> None:
    protected = managed_model(protected=True)
    protected["importance"] = "protected"
    registry = {"workloads": [protected], "rules": []}

    resolved = contracts.resolve_workload(
        registry,
        {
            "id": "model:reranker",
            "owner": "untrusted-observer",
            "importance": "disposable",
            "protected": False,
            "memory": {"observed_mib": 2048},
            "activity": {"state": "idle", "confidence": "high"},
        },
    )

    assert resolved["owner"] == "abyss-machine-ai"
    assert resolved["importance"] == "protected"
    assert resolved["protected"] is True
    assert resolved["memory"]["observed_mib"] == 2048
    assert resolved["allowed_actions"] == ["observe"]


def test_declared_allowed_actions_cannot_bypass_missing_lifecycle_routes() -> None:
    forecast = contracts.build_forecast(
        [sample(0), sample(30), sample(60, psi_full_total_usec=1_800_000)],
        outstanding_mib=0,
        queued_demand_mib=0,
        policy=contracts.default_policy(),
        now_epoch=60,
    )
    workload = managed_model()
    workload["lifecycle"] = {}
    workload["allowed_actions"] = ["managed_dehydrate"]

    decision = contracts.build_decision(
        forecast=forecast,
        workloads=[workload],
        controller_state={},
        policy={"actions": {"queue_control": {"enabled": False}, "managed_dehydrate": {"enabled": True}}},
        now_epoch=60,
    )

    assert decision["selected"]["action"] == "observe"
    assert decision["live_action_authorized"] is False


def test_cold_zram_without_stalls_is_not_active_relief() -> None:
    policy = contracts.default_policy()
    forecast = contracts.build_forecast(
        [sample(0), sample(30, zram_resident_mib=3_050), sample(60, zram_resident_mib=3_100)],
        outstanding_mib=0,
        queued_demand_mib=0,
        policy=policy,
        now_epoch=60,
    )

    assert forecast["pressure_band"] == "healthy"
    assert forecast["active_memory_relief_needed"] is False
    assert forecast["residual_zram_debt"] is True
    assert forecast["confidence"] == "high"
    assert forecast["zram"]["physical_savings_mib"] == 3900.0
    assert forecast["zram"]["resident_percent_of_ram"] == 9.688
    assert forecast["policy"]["nominal_zram_size_is_not_preallocated_ram"] is True


def test_concurrent_declared_demand_projects_hot_headroom() -> None:
    forecast = contracts.build_forecast(
        [sample(0), sample(30), sample(60)],
        outstanding_mib=6_000,
        queued_demand_mib=6_000,
        policy=contracts.default_policy(),
        now_epoch=60,
    )

    assert forecast["pressure_band"] == "hot"
    assert forecast["active_memory_relief_needed"] is False
    assert forecast["new_work_control_needed"] is True
    assert forecast["projections"]["10"]["mem_available_mib"] == 4_000.0


def test_short_noisy_history_does_not_extrapolate_a_false_pressure_trend() -> None:
    forecast = contracts.build_forecast(
        [sample(0, available_mib=16_000), sample(1, available_mib=15_900), sample(2, available_mib=15_850)],
        outstanding_mib=0,
        queued_demand_mib=0,
        policy=contracts.default_policy(),
        now_epoch=2,
    )

    assert forecast["confidence"] == "medium"
    assert forecast["slopes"]["mem_available_mib_per_sec"] == 0.0
    assert forecast["pressure_band"] == "healthy"
    assert forecast["new_work_control_needed"] is False
    assert forecast["time_to_warm_sec"] is None


def test_stable_decline_projects_ordered_warm_hot_and_critical_horizons() -> None:
    forecast = contracts.build_forecast(
        [sample(0, available_mib=16_000), sample(30, available_mib=14_000), sample(60, available_mib=12_000)],
        outstanding_mib=0,
        queued_demand_mib=0,
        policy=contracts.default_policy(),
        now_epoch=60,
    )

    thresholds = forecast["time_to_threshold_sec"]
    assert thresholds["warm"] == 60.0
    assert thresholds["hot"] == 108.0
    assert thresholds["critical"] == 132.0


def test_real_stall_growth_marks_active_pressure() -> None:
    forecast = contracts.build_forecast(
        [sample(0), sample(30, psi_some_total_usec=0), sample(60, psi_some_total_usec=1_800_000)],
        outstanding_mib=0,
        queued_demand_mib=0,
        policy=contracts.default_policy(),
        now_epoch=60,
    )

    assert forecast["stall_rates"]["some_percent"] == 6.0
    assert forecast["active_memory_relief_needed"] is True
    assert forecast["pressure_band"] in {"hot", "critical"}
    assert forecast["projections"]["10"]["pressure_expected"] is True
    assert forecast["projections"]["30"]["pressure_expected"] is True
    assert forecast["projections"]["120"]["pressure_expected"] is False


def test_ordinary_major_fault_pressure_has_short_bounded_persistence() -> None:
    forecast = contracts.build_forecast(
        [sample(0), sample(30, major_faults=0), sample(60, major_faults=600)],
        outstanding_mib=0,
        queued_demand_mib=0,
        policy=contracts.default_policy(),
        now_epoch=60,
    )

    assert forecast["stall_rates"]["major_faults_per_sec"] == 20.0
    assert forecast["projections"]["10"]["pressure_expected"] is True
    assert forecast["projections"]["30"]["pressure_expected"] is False
    assert forecast["projections"]["120"]["pressure_expected"] is False


def test_swap_churn_requires_swapin_and_correlated_reclaim_not_occupancy_alone() -> None:
    healthy = contracts.build_forecast(
        [sample(0, swap_used_mib=15_000), sample(30, swap_used_mib=15_000), sample(60, swap_used_mib=15_000)],
        outstanding_mib=0,
        queued_demand_mib=0,
        policy=contracts.default_policy(),
        now_epoch=60,
    )
    churning = contracts.build_forecast(
        [sample(0), sample(30), sample(60, pswpin=20_000, pswpout=20_000)],
        outstanding_mib=0,
        queued_demand_mib=0,
        policy=contracts.default_policy(),
        now_epoch=60,
    )

    assert healthy["active_memory_relief_needed"] is False
    assert healthy["stall_rates"]["active_swap_churn"] is False
    assert churning["stall_rates"]["active_swap_churn"] is True
    assert churning["active_memory_relief_needed"] is True
    assert churning["pressure_band"] == "hot"


def test_shadow_decision_uses_queue_control_before_lifecycle() -> None:
    forecast = contracts.build_forecast(
        [sample(0), sample(30), sample(60)],
        outstanding_mib=6_000,
        queued_demand_mib=6_000,
        policy=contracts.default_policy(),
        now_epoch=60,
    )
    forecast["pending_queue_count"] = 1

    decision = contracts.build_decision(
        forecast=forecast,
        workloads=[managed_model()],
        controller_state={},
        policy=contracts.default_policy(),
        now_epoch=60,
    )

    assert decision["selected"]["action"] == "queue_control"
    assert decision["selected"]["execution"] == "shadow_only"
    assert decision["live_action_authorized"] is False
    assert decision["reason"]["queue_execution_enrolled"] is False
    assert decision["reason"]["lifecycle_enrollment_authorized"] is False
    assert "managed_dehydrate" not in {item["action"] for item in decision["alternatives"]}


def test_live_queue_requires_exact_execution_enrollment_in_policy_kernel() -> None:
    forecast = contracts.build_forecast(
        [sample(0), sample(30), sample(60)],
        outstanding_mib=6_000,
        queued_demand_mib=6_000,
        policy=contracts.default_policy(),
        now_epoch=60,
    )
    forecast["pending_queue_count"] = 1
    policy = contracts.default_policy()
    policy["mode"] = "live"
    policy["actions"]["queue_control"]["live_enabled"] = True

    unenrolled = contracts.build_decision(
        forecast=forecast,
        workloads=[],
        controller_state={},
        policy=policy,
        now_epoch=60,
    )
    policy["execution"]["enrolled"] = True
    enrolled = contracts.build_decision(
        forecast=forecast,
        workloads=[],
        controller_state={},
        policy=policy,
        now_epoch=60,
    )

    assert unenrolled["live_action_authorized"] is False
    assert unenrolled["reason"]["action_enrollment_authorized"] is False
    assert enrolled["live_action_authorized"] is True
    assert enrolled["reason"]["queue_execution_enrolled"] is True


def test_busy_or_protected_model_is_never_dehydration_candidate() -> None:
    policy = contracts.default_policy()
    forecast = contracts.build_forecast(
        [sample(0), sample(30), sample(60, psi_full_total_usec=1_800_000)],
        outstanding_mib=0,
        queued_demand_mib=0,
        policy=policy,
        now_epoch=60,
    )

    decision = contracts.build_decision(
        forecast=forecast,
        workloads=[managed_model(busy=True), managed_model(protected=True)],
        controller_state={},
        policy=policy,
        now_epoch=60,
    )

    assert all(item.get("workload_id") != "model:reranker" for item in decision["alternatives"] if item["action"] == "managed_dehydrate")
    assert decision["live_action_authorized"] is False


def test_active_pressure_holds_pending_queue_then_selects_lifecycle_relief() -> None:
    policy = contracts.default_policy()
    forecast = contracts.build_forecast(
        [sample(0), sample(30), sample(60, psi_full_total_usec=1_800_000)],
        outstanding_mib=0,
        queued_demand_mib=1024,
        policy=policy,
        now_epoch=60,
    )
    forecast["pending_queue_count"] = 1

    decision = contracts.build_decision(
        forecast=forecast,
        workloads=[managed_model()],
        controller_state={},
        policy=policy,
        now_epoch=60,
    )

    assert decision["reason"]["queue_hold_active"] is True
    assert decision["selected"]["action"] == "managed_dehydrate"
    assert "queue_control" in {item["action"] for item in decision["alternatives"]}


def test_live_lifecycle_requires_trusted_static_owner_enrollment() -> None:
    policy = contracts.default_policy()
    policy["mode"] = "live"
    policy["execution"] = {"enrolled": True}
    policy["actions"]["queue_control"]["enabled"] = False
    policy["actions"]["managed_dehydrate"]["live_enabled"] = True
    forecast = contracts.build_forecast(
        [sample(0), sample(30), sample(60, psi_full_total_usec=1_800_000)],
        outstanding_mib=0,
        queued_demand_mib=0,
        policy=policy,
        now_epoch=60,
    )
    enrolled = managed_model()
    runtime_only = deepcopy(enrolled)
    runtime_only["metadata"]["registry_source"] = "runtime"
    runtime_only["metadata"]["registry_trusted_for_lifecycle"] = False

    accepted = contracts.build_decision(
        forecast=forecast,
        workloads=[enrolled],
        controller_state={},
        policy=policy,
        now_epoch=60,
    )
    rejected = contracts.build_decision(
        forecast=forecast,
        workloads=[runtime_only],
        controller_state={},
        policy=policy,
        now_epoch=60,
    )

    assert accepted["selected"]["action"] == "managed_dehydrate"
    assert accepted["live_action_authorized"] is True
    assert accepted["selected"]["utility"]["components"]["ram_benefit"] == 70.0
    assert "owner_enrollment_changed_or_expired" in accepted["selected"]["stop_conditions"]
    assert rejected["selected"]["action"] == "managed_dehydrate"
    assert rejected["live_action_authorized"] is False
    assert rejected["selected"]["enrollment"]["checks"]["trusted_static_projection"] is False


def test_cooldown_prevents_repeated_lifecycle_action() -> None:
    policy = contracts.default_policy()
    forecast = contracts.build_forecast(
        [sample(0), sample(30), sample(60, psi_full_total_usec=1_800_000)],
        outstanding_mib=0,
        queued_demand_mib=0,
        policy=policy,
        now_epoch=60,
    )
    state = {"last_actions": {"model:reranker": {"epoch": 50, "action": "managed_dehydrate"}}}

    decision = contracts.build_decision(
        forecast=forecast,
        workloads=[managed_model()],
        controller_state=state,
        policy=policy,
        now_epoch=60,
    )

    assert all(item["action"] != "managed_dehydrate" for item in decision["alternatives"])


def test_queue_order_ages_background_without_beating_operator_work() -> None:
    requests = [
        {"id": "old-background", "owner": "indexer", "priority": 10, "created_epoch": 0, "posture": "background"},
        {"id": "new-operator", "owner": "operator", "priority": 50, "created_epoch": 590, "posture": "interactive"},
        {"id": "new-background", "owner": "indexer", "priority": 10, "created_epoch": 590, "posture": "background"},
    ]

    ordered = contracts.order_queue(requests, now_epoch=600, starvation_sec=300)

    assert [item["id"] for item in ordered] == ["new-operator", "old-background", "new-background"]
    assert ordered[1]["aged"] is True


def test_queue_order_is_total_when_created_epoch_is_missing() -> None:
    ordered = contracts.order_queue(
        [{"id": "incomplete", "priority": 1, "posture": "background"}],
        now_epoch=600,
        starvation_sec=300,
    )

    assert ordered[0]["created_epoch"] == 600
    assert ordered[0]["wait_sec"] == 0


def test_default_queue_aging_closes_full_background_priority_gap() -> None:
    policy = contracts.default_policy()
    starvation_sec = policy["queue"]["starvation_sec"]
    ordered = contracts.order_queue(
        [
            {"id": "old-benchmark", "priority": 10, "created_epoch": 0, "posture": "background"},
            {"id": "new-agent", "priority": 50, "created_epoch": 16, "posture": "background"},
        ],
        now_epoch=16,
        starvation_sec=starvation_sec,
    )

    assert [item["id"] for item in ordered] == ["old-benchmark", "new-agent"]
    assert ordered[0]["effective_priority"] == 50


def test_queue_plan_grants_one_highest_utility_request_only_when_headroom_fits() -> None:
    requests = [
        {"id": "low", "owner": "index", "demand_mib": 1024, "priority": 10, "created_epoch": 10, "deadline_epoch": 200},
        {"id": "high", "owner": "model", "demand_mib": 2048, "priority": 50, "created_epoch": 20, "deadline_epoch": 200},
    ]
    plan = contracts.plan_queue(
        requests,
        samples=[sample(0), sample(30), sample(60)],
        outstanding_mib=0,
        active_grants=[],
        policy=contracts.default_policy(),
        now_epoch=60,
    )

    assert plan["selected"]["request_id"] == "high"
    assert plan["selected"]["status"] == "grant"
    assert plan["decisions"][0]["request_id"] == "high"
    assert plan["decisions"][1]["status"] == "defer"
    assert plan["policy"]["one_grant_at_a_time"] is True


def test_queue_plan_defers_on_pressure_or_existing_unconsumed_grant() -> None:
    request = {"id": "one", "owner": "index", "demand_mib": 1024, "priority": 10, "created_epoch": 10, "deadline_epoch": 200}
    pressure = contracts.plan_queue(
        [request],
        samples=[sample(0), sample(30), sample(60, available_mib=3_000)],
        outstanding_mib=0,
        active_grants=[],
        policy=contracts.default_policy(),
        now_epoch=60,
    )
    occupied = contracts.plan_queue(
        [request],
        samples=[sample(0), sample(30), sample(60)],
        outstanding_mib=0,
        active_grants=[{"request_id": "other", "expires_epoch": 90}],
        policy=contracts.default_policy(),
        now_epoch=60,
    )

    assert pressure["selected"] is None
    assert pressure["decisions"][0]["reason"] == "request_would_cross_safe_headroom"
    assert occupied["selected"] is None
    assert occupied["decisions"][0]["reason"] == "another_grant_is_active"


def test_envelope_calibration_is_bounded_and_ignores_failed_outcome() -> None:
    policy = contracts.default_policy()
    first = contracts.calibrate_envelope(
        current_mib=2_000,
        outcome={"ok": True, "observed_peak_mib": 4_000},
        policy=policy,
    )
    failed = contracts.calibrate_envelope(
        current_mib=first["calibrated_mib"],
        outcome={"ok": False, "observed_peak_mib": 9_000},
        policy=policy,
    )

    assert first["calibrated_mib"] == 2_300.0
    assert first["bounded"] is True
    assert failed["calibrated_mib"] == 2_300.0
    assert failed["changed"] is False


def test_launch_outcome_keeps_bounded_calibration_as_recommendation_only() -> None:
    outcome = contracts.build_launch_outcome(
        event_id="launch-1",
        event_epoch=100,
        details={
            "workload_id": "model:reranker",
            "owner": "model-owner",
            "requested_mib": 2000,
            "observed_peak_mib": 4000,
            "queue_delay_sec": 0.75,
            "elapsed_sec": 2.5,
            "ok": True,
            "queue_granted": True,
        },
        workloads=[managed_model()],
        policy=contracts.default_policy(),
    )

    assert outcome["classification"] == "envelope_underestimate"
    assert outcome["calibration_recommendation"]["bounded"] is True
    assert outcome["calibration_recommendation"]["calibrated_mib"] == 3450.0
    assert outcome["policy"]["recommendation_only"] is True


def test_property_more_declared_demand_never_improves_projected_headroom_or_pressure() -> None:
    policy = contracts.default_policy()
    rank = contracts.PRESSURE_RANK
    for available_mib in (4_000, 8_000, 16_000, 24_000):
        samples = [sample(0, available_mib=available_mib), sample(30, available_mib=available_mib), sample(60, available_mib=available_mib)]
        previous_available = float("inf")
        previous_rank = -1
        for demand_mib in (0, 512, 2_048, 8_192, 16_384):
            forecast = contracts.build_forecast(
                samples,
                outstanding_mib=demand_mib,
                queued_demand_mib=0,
                policy=policy,
                now_epoch=60,
            )
            projected = forecast["projections"]["10"]
            assert projected["mem_available_mib"] <= previous_available
            assert rank[projected["pressure_band"]] >= previous_rank
            previous_available = projected["mem_available_mib"]
            previous_rank = rank[projected["pressure_band"]]


def test_property_unknown_and_protected_workloads_never_gain_mutation_actions() -> None:
    for importance in ("unknown", "protected"):
        for protected in (False, True):
            raw = managed_model(protected=protected)
            raw["importance"] = importance
            resolved = contracts.resolve_workload({"workloads": [raw], "rules": []}, {"id": raw["id"]})
            assert resolved["allowed_actions"] == ["observe"]
            enrollment = contracts.lifecycle_action_enrolled(resolved, "managed_dehydrate", now_epoch=60)
            assert enrollment["authorized"] is False
            assert "managed_dehydrate" not in resolved["allowed_actions"]


def test_invalid_nonfinite_samples_reduce_confidence_without_crashing() -> None:
    broken = sample(30)
    broken["mem_available_mib"] = float("nan")

    forecast = contracts.build_forecast(
        [sample(0), broken, sample(60)],
        outstanding_mib=0,
        queued_demand_mib=0,
        policy=deepcopy(contracts.default_policy()),
        now_epoch=60,
    )

    assert forecast["ok"] is True
    assert forecast["confidence"] != "high"
    assert "invalid_or_missing_samples" in forecast["confidence_reasons"]

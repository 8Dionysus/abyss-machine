from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import resource_planning


def _light_maintenance_policy(identity: str) -> dict[str, object]:
    policy = resource_planning.default_policy(version="test")
    policy["startup_admission"]["bounded_light_maintenance"] = {
        "enabled": True,
        "contract_allowlist": [
            {
                "owner": "abyss-machine",
                "demand_key": "storage-capacity",
                "command_identity": identity,
            }
        ],
        "max_estimate_mib": 64,
        "min_successful_samples": 3,
        "max_profile_age_sec": 300,
        "max_elapsed_sec": 5,
    }
    return policy


def _light_profile(
    identity: str,
    *,
    missing_duration: bool = False,
    mixed_identity: bool = False,
    observed_epochs: list[float] | None = None,
    failed_sample: bool = False,
) -> dict[str, object]:
    samples: list[dict[str, object]] = []
    for index in range(3):
        sample: dict[str, object] = {
            "observed_at_epoch": (
                observed_epochs or [990.0, 991.0, 992.0]
            )[index],
            "memory_peak_mib": 24.0,
            "memory_swap_peak_mib": 0.0,
            "footprint_peak_mib": 24.0,
            "execution_succeeded": not failed_sample or index != 0,
            "execution_returncode": 0 if not failed_sample or index != 0 else 1,
            "command_identity": (
                identity
                if not mixed_identity or index < 2
                else f"{identity}-other"
            ),
        }
        if (not missing_duration or index) and (
            not failed_sample or index != 0
        ):
            sample["elapsed_sec"] = 0.5
        samples.append(sample)
    return {
        "key": "storage-capacity",
        "owner": "abyss-machine",
        "kind": "generic",
        "sample_count": 3,
        "observed_max_mib": 24.0,
        "failed_demand_floor_mib": 0.0,
        "estimate_mib": 30.0,
        "estimate_source": "runtime_observed_unit_peak",
        "samples": samples,
    }


def test_resource_command_identity_hashes_caller_argv_without_retaining_it() -> None:
    first = resource_planning.command_identity(["--", "storage", "capacity"])
    second = resource_planning.command_identity(["storage", "capacity"])
    empty_arg = resource_planning.command_identity(["storage", "", "capacity"])
    changed = resource_planning.command_identity(["storage", "capacity", "--json"])

    assert first != second
    assert second != empty_arg
    assert first is not None
    assert first.startswith("argv-sha256:")
    assert len(first) == len("argv-sha256:") + 64
    assert changed != first
    assert resource_planning.command_identity("aoa-session-memory") is None


def test_resource_owner_activity_requires_explicit_foreground_and_rejects_conflicts() -> None:
    unspecified = resource_planning.owner_activity(None, unattended=False)
    legacy_background = resource_planning.owner_activity(None, unattended=True)
    foreground = resource_planning.owner_activity("foreground", unattended=False)
    conflict = resource_planning.owner_activity("foreground", unattended=True)

    assert unspecified["normalized"] == "unspecified"
    assert unspecified["foreground"] is False
    assert legacy_background["normalized"] == "background"
    assert legacy_background["background"] is True
    assert foreground["valid"] is True
    assert foreground["explicit"] is True
    assert foreground["foreground"] is True
    assert conflict["valid"] is False
    assert conflict["errors"] == ["owner_activity_conflicts_with_unattended"]


def test_resource_runtime_admission_request_is_owner_explicit_and_secret_safe() -> None:
    request = resource_planning.runtime_admission_request(
        {
            "operation": "cold_load",
            "owner": "abyss-stack",
            "workload_id": "llama-cpp:gemma4-e2b",
            "request_id": "req-123",
            "release_token": "fixture-release-token-1234567890",
            "activity": "foreground",
            "class": "heavy",
            "kind": "ai",
            "memory_demand_mib": 4096,
        }
    )

    assert request["valid"] is True
    assert request["request"]["activity"] == "foreground"
    assert request["request"]["unattended"] is False
    assert request["request"]["latency"] == "interactive"
    assert request["lease_id"].startswith("runtime-cold-load:")
    assert request["release_token_sha256"] != "fixture-release-token-1234567890"
    assert "release_token" not in request["request"]

    missing_activity = resource_planning.runtime_admission_request(
        {
            "owner": "abyss-stack",
            "workload_id": "llama-cpp:gemma4-e2b",
            "request_id": "req-124",
            "release_token": "fixture-release-token-1234567890",
            "memory_demand_mib": 4096,
        }
    )
    assert missing_activity["valid"] is False
    assert missing_activity["errors"] == ["owner_activity_required"]


def test_resource_startup_demand_resolution_keeps_model_owner_authoritative() -> None:
    policy = resource_planning.default_policy(version="test")

    agent = resource_planning.resolve_startup_demand(
        policy,
        workload_class="medium",
        kind="agent",
        explicit_mib=None,
    )
    model = resource_planning.resolve_startup_demand(
        policy,
        workload_class="medium",
        kind="ai",
        explicit_mib=None,
    )
    explicit_model = resource_planning.resolve_startup_demand(
        policy,
        workload_class="medium",
        kind="ai",
        explicit_mib=6144,
        demand_key="small-model",
        demand_owner="model-registry",
    )
    learned_probe = resource_planning.resolve_startup_demand(
        policy,
        workload_class="probe",
        kind="indexing",
        explicit_mib=None,
        demand_key="abyss-machine:nervous:index-build",
        learned_profile={"estimate_mib": 3328, "sample_count": 4},
    )

    assert agent["demand_mib"] == 2048.0
    assert agent["estimate_source"] == "bootstrap_class_kind_estimate"
    assert agent["calibration"] == "bootstrap_uncalibrated"
    assert agent["calibrated"] is False
    assert agent["known"] is False
    assert agent["estimate_available"] is True
    assert agent["unknown_startup_lane"] is True
    assert model["unknown_startup_lane"] is True
    assert explicit_model["demand_mib"] == 6144.0
    assert explicit_model["known"] is True
    assert explicit_model["key"] == "small-model"
    assert explicit_model["owner"] == "model-registry"
    assert learned_probe["demand_mib"] == 3328.0
    assert learned_probe["reservation_required"] is True
    assert learned_probe["calibration"] == "learned"
    assert learned_probe["calibrated"] is True
    assert learned_probe["known"] is True
    assert learned_probe["unknown_startup_lane"] is False


def test_resource_startup_demand_rejects_nonfinite_or_negative_values() -> None:
    policy = resource_planning.default_policy(version="test")

    for value in (-1, float("nan"), float("inf")):
        demand = resource_planning.resolve_startup_demand(
            policy,
            workload_class="medium",
            kind="ai",
            explicit_mib=value,
        )
        assert demand["valid"] is False
        assert demand["demand_mib"] is None
        assert demand["invalid_reason"] == "memory_demand_mib_must_be_finite_and_nonnegative"


def test_resource_startup_projection_counts_only_unmaterialized_ram() -> None:
    projection = resource_planning.startup_demand_projection(
        memory_summary={"mem_total_mib": 16000, "mem_available_mib": 12000},
        current_memory_class="green",
        memory_policy={
            "thresholds": {
                "mem_available_percent": {"watch_below": 30, "warm_below": 22, "hot_below": 14, "critical_below": 8}
            }
        },
        demand={"reservation_required": True, "known": True, "demand_mib": 8000},
        reservations={"summary": {"active_count": 1, "known_count": 1, "unknown_count": 0, "outstanding_mib": 2500}},
        admission_policy={"hard_mem_available_floor_mib": 2048},
    )

    assert projection["projected"]["mem_available_mib"] == 1500.0
    assert projection["projected"]["memory_class"] == "hot"
    assert projection["policy"]["zram_free_not_counted_as_ram"] is True
    assert projection["policy"]["materialized_memory_not_double_counted"] is True
    assert projection["admission"]["allowed"] is False
    assert projection["admission"]["blocked_reasons"] == ["projected_mem_available_below_hard_reserve"]
    assert projection["admission"]["pressure_facts_assign_importance"] is False


def test_resource_startup_projection_defers_only_new_unattended_work_during_active_stall() -> None:
    memory_policy = {
        "thresholds": {
            "mem_available_percent": {"watch_below": 30, "warm_below": 22, "hot_below": 14, "critical_below": 8},
            "psi_some_avg10": {"hot_above": 8.0},
            "psi_full_avg10": {"hot_above": 2.0},
        }
    }
    demand = {
        "reservation_required": True,
        "known": True,
        "estimate_available": True,
        "demand_mib": 512,
        "unknown_startup_lane": False,
    }
    reservations = {"summary": {"active_count": 0, "known_count": 0, "unknown_count": 0, "outstanding_mib": 0}}

    unattended_active_stall = resource_planning.startup_demand_projection(
        memory_summary={
            "mem_total_mib": 32000,
            "mem_available_mib": 13000,
            "psi_some_avg10": 0.0,
            "psi_full_avg10": 3.0,
        },
        current_memory_class="critical",
        memory_policy=memory_policy,
        demand=demand,
        reservations=reservations,
        unattended=True,
        admission_policy={"hard_mem_available_floor_mib": 2048},
    )
    foreground_active_stall = resource_planning.startup_demand_projection(
        memory_summary={
            "mem_total_mib": 32000,
            "mem_available_mib": 13000,
            "psi_some_avg10": 0.0,
            "psi_full_avg10": 3.0,
        },
        current_memory_class="critical",
        memory_policy=memory_policy,
        demand=demand,
        reservations=reservations,
        unattended=False,
        admission_policy={"hard_mem_available_floor_mib": 2048},
    )
    quiet_unattended = resource_planning.startup_demand_projection(
        memory_summary={
            "mem_total_mib": 32000,
            "mem_available_mib": 13000,
            "psi_some_avg10": 0.0,
            "psi_full_avg10": 0.0,
        },
        current_memory_class="critical",
        memory_policy=memory_policy,
        demand=demand,
        reservations=reservations,
        unattended=True,
        admission_policy={"hard_mem_available_floor_mib": 2048},
    )

    assert unattended_active_stall["admission"]["allowed"] is False
    assert unattended_active_stall["admission"]["active_stall"] is True
    assert unattended_active_stall["admission"]["blocked_reasons"] == [
        "new_unattended_work_during_active_memory_stall"
    ]
    assert unattended_active_stall["admission"]["pressure_facts_assign_importance"] is False
    assert foreground_active_stall["admission"]["allowed"] is True
    assert foreground_active_stall["admission"]["active_stall"] is True
    assert foreground_active_stall["admission"]["unattended_start"] is False
    assert quiet_unattended["admission"]["allowed"] is True
    assert quiet_unattended["admission"]["active_stall"] is False


def test_resource_bounded_light_maintenance_requires_measured_identity_and_duration() -> None:
    identity = resource_planning.command_identity(
        ["/usr/local/bin/abyss-machine", "storage", "capacity", "--json"]
    )
    assert identity is not None
    policy = _light_maintenance_policy(identity)
    demand = resource_planning.resolve_startup_demand(
        policy,
        workload_class="light",
        kind="generic",
        explicit_mib=None,
        demand_key="storage-capacity",
        demand_owner="abyss-machine",
        learned_profile=_light_profile(identity),
        command_identity=identity,
    )
    projection = resource_planning.startup_demand_projection(
        memory_summary={
            "mem_total_mib": 32000,
            "mem_available_mib": 13000,
            "psi_some_avg10": 0.0,
            "psi_full_avg10": 3.0,
        },
        current_memory_class="critical",
        memory_policy={
            "thresholds": {
                "mem_available_percent": {
                    "watch_below": 30,
                    "warm_below": 22,
                    "hot_below": 14,
                    "critical_below": 8,
                },
                "psi_some_avg10": {"hot_above": 8.0},
                "psi_full_avg10": {"hot_above": 2.0},
            }
        },
        demand=demand,
        reservations={
            "summary": {
                "active_count": 0,
                "known_count": 0,
                "unknown_count": 0,
                "outstanding_mib": 0,
            }
        },
        unattended=True,
        activity="maintenance",
        admission_policy=policy["startup_admission"],
        now_epoch=1000.0,
    )

    assert projection["admission"]["bounded_light_maintenance"]["eligible"] is True
    assert projection["admission"]["bounded_light_maintenance"]["observed_max_elapsed_sec"] == 0.5
    assert projection["admission"]["blocked_reasons"] == []
    assert projection["admission"]["active_stall"] is True

    actual_compactor = resource_planning.resolve_startup_demand(
        policy,
        workload_class="medium",
        kind="indexing",
        explicit_mib=2048,
        demand_key="aoa-session-memory:raw-block-storage-compact",
        demand_owner="aoa-session-memory",
    )
    actual_compactor_projection = resource_planning.startup_demand_projection(
        memory_summary={"mem_total_mib": 32000, "mem_available_mib": 13000, "psi_full_avg10": 3.0},
        current_memory_class="critical",
        memory_policy={"thresholds": {"psi_full_avg10": {"hot_above": 2.0}}},
        demand=actual_compactor,
        reservations={"summary": {"unknown_count": 0, "outstanding_mib": 0}},
        unattended=True,
        activity="maintenance",
        admission_policy=policy["startup_admission"],
        now_epoch=1000.0,
    )
    assert actual_compactor_projection["admission"]["bounded_light_maintenance"]["reason"] == (
        "bounded_light_maintenance_requires_light_class"
    )
    assert actual_compactor_projection["admission"]["blocked_reasons"] == [
        "new_unattended_work_during_active_memory_stall"
    ]


def test_resource_bounded_light_maintenance_preserves_hard_reserve_and_rejects_stale_profiles() -> None:
    identity = resource_planning.command_identity(
        ["/usr/local/bin/abyss-machine", "storage", "capacity", "--json"]
    )
    assert identity is not None
    policy = _light_maintenance_policy(identity)
    demand = resource_planning.resolve_startup_demand(
        policy,
        workload_class="light",
        kind="generic",
        explicit_mib=None,
        demand_key="storage-capacity",
        demand_owner="abyss-machine",
        learned_profile=_light_profile(identity),
        command_identity=identity,
    )
    reserve_projection = resource_planning.startup_demand_projection(
        memory_summary={"mem_total_mib": 32000, "mem_available_mib": 2000, "psi_full_avg10": 3.0},
        current_memory_class="critical",
        memory_policy={"thresholds": {"psi_full_avg10": {"hot_above": 2.0}}},
        demand=demand,
        reservations={"summary": {"unknown_count": 0, "outstanding_mib": 0}},
        unattended=True,
        activity="maintenance",
        admission_policy=policy["startup_admission"],
        now_epoch=1000.0,
    )
    assert reserve_projection["admission"]["bounded_light_maintenance"]["eligible"] is True
    assert reserve_projection["admission"]["blocked_reasons"] == [
        "projected_mem_available_below_hard_reserve"
    ]

    old_demand = resource_planning.resolve_startup_demand(
        policy,
        workload_class="light",
        kind="generic",
        explicit_mib=None,
        demand_key="storage-capacity",
        demand_owner="abyss-machine",
        learned_profile=_light_profile(identity, missing_duration=True),
        command_identity=identity,
    )
    old_eligibility = resource_planning.bounded_light_maintenance_eligibility(
        demand=old_demand,
        activity="maintenance",
        unattended=True,
        admission_policy=policy["startup_admission"],
        now_epoch=1000.0,
    )
    assert old_eligibility["reason"] == "bounded_light_maintenance_profile_duration_missing"

    stale_profile = _light_profile(identity)
    for sample in stale_profile["samples"]:
        sample["observed_at_epoch"] = 600.0
    stale_demand = resource_planning.resolve_startup_demand(
        policy,
        workload_class="light",
        kind="generic",
        explicit_mib=None,
        demand_key="storage-capacity",
        demand_owner="abyss-machine",
        learned_profile=stale_profile,
        command_identity=identity,
    )
    stale_eligibility = resource_planning.bounded_light_maintenance_eligibility(
        demand=stale_demand,
        activity="maintenance",
        unattended=True,
        admission_policy=policy["startup_admission"],
        now_epoch=1000.0,
    )
    assert stale_eligibility["reason"] == (
        "bounded_light_maintenance_profile_fresh_samples_insufficient"
    )

    implicit_activity = resource_planning.bounded_light_maintenance_eligibility(
        demand=demand,
        activity=None,
        unattended=True,
        admission_policy=policy["startup_admission"],
        now_epoch=1000.0,
    )
    assert implicit_activity["reason"] == (
        "bounded_light_maintenance_requires_explicit_maintenance"
    )

    mixed_demand = resource_planning.resolve_startup_demand(
        policy,
        workload_class="light",
        kind="generic",
        explicit_mib=None,
        demand_key="storage-capacity",
        demand_owner="abyss-machine",
        learned_profile=_light_profile(identity, mixed_identity=True),
        command_identity=identity,
    )
    mixed_eligibility = resource_planning.bounded_light_maintenance_eligibility(
        demand=mixed_demand,
        activity="maintenance",
        unattended=True,
        admission_policy=policy["startup_admission"],
        now_epoch=1000.0,
    )
    assert mixed_eligibility["reason"] == (
        "bounded_light_maintenance_profile_command_identity_mismatch"
    )


def test_resource_bounded_light_maintenance_rejects_failed_and_nonfresh_samples() -> None:
    identity = resource_planning.command_identity(
        ["/usr/local/bin/abyss-machine", "storage", "capacity", "--json"]
    )
    assert identity is not None
    policy = _light_maintenance_policy(identity)

    def eligibility(profile: dict[str, object]) -> dict[str, object]:
        demand = resource_planning.resolve_startup_demand(
            policy,
            workload_class="light",
            kind="generic",
            explicit_mib=None,
            demand_key="storage-capacity",
            demand_owner="abyss-machine",
            learned_profile=profile,
            command_identity=identity,
        )
        return resource_planning.bounded_light_maintenance_eligibility(
            demand=demand,
            activity="maintenance",
            unattended=True,
            admission_policy=policy["startup_admission"],
            now_epoch=1000.0,
        )

    failed_profile = _light_profile(identity)
    failed_profile["samples"].append(
        {
            "observed_at_epoch": 999.0,
            "execution_succeeded": False,
            "execution_returncode": 1,
            "command_identity": identity,
            "requested_demand_mib": 0.0,
        }
    )
    failed = eligibility(failed_profile)
    assert failed["reason"] == "bounded_light_maintenance_profile_has_failed_samples"

    ancient_and_fresh = eligibility(
        _light_profile(identity, observed_epochs=[600.0, 601.0, 999.0])
    )
    assert ancient_and_fresh["reason"] == (
        "bounded_light_maintenance_profile_fresh_samples_insufficient"
    )
    assert ancient_and_fresh["fresh_successful_sample_count"] == 1

    future = eligibility(
        _light_profile(identity, observed_epochs=[990.0, 991.0, 1001.0])
    )
    assert future["reason"] == (
        "bounded_light_maintenance_profile_fresh_samples_insufficient"
    )
    assert future["fresh_successful_sample_count"] == 2


def test_resource_bounded_light_maintenance_rejects_malformed_policy_and_cross_product() -> None:
    identity = resource_planning.command_identity(
        ["/usr/local/bin/abyss-machine", "storage", "capacity", "--json"]
    )
    assert identity is not None
    policy = _light_maintenance_policy(identity)
    policy["startup_admission"]["bounded_light_maintenance"][
        "min_successful_samples"
    ] = float("nan")
    demand = resource_planning.resolve_startup_demand(
        policy,
        workload_class="light",
        kind="generic",
        explicit_mib=None,
        demand_key="storage-capacity",
        demand_owner="abyss-machine",
        learned_profile=_light_profile(identity),
        command_identity=identity,
    )
    malformed = resource_planning.bounded_light_maintenance_eligibility(
        demand=demand,
        activity="maintenance",
        unattended=True,
        admission_policy=policy["startup_admission"],
        now_epoch=1000.0,
    )
    assert malformed["reason"] == (
        "bounded_light_maintenance_policy_min_samples_invalid"
    )

    cross_product_policy = _light_maintenance_policy(identity)
    cross_product_policy["startup_admission"]["bounded_light_maintenance"][
        "contract_allowlist"
    ].append(
        {
            "owner": "other-owner",
            "demand_key": "other-key",
            "command_identity": "argv-sha256:" + ("b" * 64),
        }
    )
    cross_profile = _light_profile(identity)
    cross_profile["key"] = "other-key"
    cross_profile["owner"] = "abyss-machine"
    cross_demand = resource_planning.resolve_startup_demand(
        cross_product_policy,
        workload_class="light",
        kind="generic",
        explicit_mib=None,
        demand_key="other-key",
        demand_owner="abyss-machine",
        learned_profile=cross_profile,
        command_identity=identity,
    )
    cross_product = resource_planning.bounded_light_maintenance_eligibility(
        demand=cross_demand,
        activity="maintenance",
        unattended=True,
        admission_policy=cross_product_policy["startup_admission"],
        now_epoch=1000.0,
    )
    assert cross_product["reason"] == "bounded_light_maintenance_identity_not_allowlisted"


def test_runtime_cold_load_plan_preserves_reserve_and_uses_owner_activity() -> None:
    policy = resource_planning.default_policy(version="test")
    memory_policy = {
        "thresholds": {
            "mem_available_percent": {"watch_below": 30, "warm_below": 22, "hot_below": 14, "critical_below": 8},
            "psi_some_avg10": {"hot_above": 8.0},
            "psi_full_avg10": {"hot_above": 2.0},
        }
    }
    common = {
        "memory_summary": {
            "mem_total_mib": 32000,
            "mem_available_mib": 12000,
            "swap_free_mib": 4096,
            "target_swap_free_mib": 2048,
            "swap_free_shortfall_mib": 0,
            "swap_reserve_state": "within_target",
            "psi_some_avg10": 0.0,
            "psi_full_avg10": 3.0,
        },
        "current_memory_class": "hot",
        "memory_policy": memory_policy,
        "resource_policy": policy,
        "reservations": {"summary": {"active_count": 0, "known_count": 0, "unknown_count": 0, "outstanding_mib": 0}},
        "thermal_safety": {"available": True, "emergency": False, "temperature_c_max": 55.0},
        "generated_at": "2026-07-13T12:00:00Z",
    }
    request = {
        "owner": "abyss-stack",
        "workload_id": "llama-cpp:gemma4-e2b",
        "request_id": "request-123",
        "class": "heavy",
        "kind": "ai",
        "memory_demand_mib": 4096,
        "estimate_source": "explicit_owner_estimate",
        "estimate_confidence": "owner_provided",
    }

    def reserve_plan(*, activity: str, state: str, request_id: str) -> dict[str, object]:
        reserve_facts = (
            {}
            if state == "unavailable"
            else {
                "swap_free_mib": 64,
                "target_swap_free_mib": 2048,
                "swap_free_shortfall_mib": 1984,
                "swap_reserve_state": state,
            }
        )
        return resource_planning.runtime_cold_load_plan(
            request={**request, "request_id": request_id, "activity": activity, "unattended": False},
            **{
                **common,
                "memory_summary": {
                    "mem_total_mib": 32000,
                    "mem_available_mib": 12000,
                    "psi_some_avg10": 0.0,
                    "psi_full_avg10": 0.0,
                    **reserve_facts,
                },
                "current_memory_class": "green",
            },
        )

    foreground = resource_planning.runtime_cold_load_plan(
        request={**request, "activity": "foreground", "unattended": False},
        **common,
    )
    background = resource_planning.runtime_cold_load_plan(
        request={**request, "request_id": "request-124", "activity": "background", "unattended": True},
        **common,
    )
    reserve_blocked = resource_planning.runtime_cold_load_plan(
        request={**request, "request_id": "request-125", "activity": "foreground", "unattended": False, "memory_demand_mib": 11200},
        **common,
    )
    thermal_blocked = resource_planning.runtime_cold_load_plan(
        request={**request, "request_id": "request-126", "activity": "foreground", "unattended": False},
        **{**common, "thermal_safety": {"available": True, "emergency": True, "temperature_c_max": 109.5}},
    )
    corrupt_state = resource_planning.runtime_cold_load_plan(
        request={**request, "request_id": "request-127", "activity": "foreground", "unattended": False},
        **{
            **common,
            "reservations": {
                "ok": False,
                "summary": {"active_count": 0, "known_count": 0, "unknown_count": 0, "outstanding_mib": 0},
            },
        },
    )
    reserve_debt_background = reserve_plan(activity="maintenance", state="below_target", request_id="request-128")
    reserve_debt_foreground = reserve_plan(activity="foreground", state="below_target", request_id="request-129")
    reserve_unavailable_background = reserve_plan(activity="background", state="unavailable", request_id="request-130")
    reserve_unavailable_foreground = reserve_plan(activity="foreground", state="unavailable", request_id="request-131")

    assert foreground["decision"] == "allow"
    assert foreground["policy"]["battery_and_power_mode_are_advisory_not_admission_authority"] is True
    assert background["decision"] == "force_required"
    assert background["blocked_reasons"] == ["runtime_new_unattended_work_during_active_memory_stall"]
    assert reserve_blocked["decision"] == "force_required"
    assert reserve_blocked["blocked_reasons"] == ["runtime_projected_mem_available_below_hard_reserve"]
    assert thermal_blocked["decision"] == "force_required"
    assert thermal_blocked["blocked_reasons"] == ["thermal_emergency"]
    assert corrupt_state["decision"] == "deny"
    assert corrupt_state["denied_reasons"] == ["runtime_reservation_state_invalid"]
    assert reserve_debt_background["decision"] == "force_required"
    assert reserve_debt_background["blocked_reasons"] == [
        "runtime_swap_reserve_below_target_for_background_cold_load"
    ]
    assert reserve_debt_foreground["decision"] == "allow"
    assert reserve_debt_foreground["warnings"] == ["swap_reserve_below_target_foreground_owner_activity"]
    assert reserve_debt_background["policy"]["swap_reserve_gates_only_background_cold_loads"] is True
    assert reserve_debt_background["policy"]["swap_reserve_assigns_workload_importance"] is False
    assert reserve_unavailable_background["decision"] == "deny"
    assert reserve_unavailable_background["denied_reasons"] == [
        "runtime_swap_reserve_unavailable_for_background_cold_load"
    ]
    assert reserve_unavailable_foreground["decision"] == "allow"
    assert reserve_unavailable_foreground["warnings"] == [
        "swap_reserve_unavailable_foreground_owner_activity"
    ]


def test_resource_planning_builds_indexing_systemd_contract_without_cli_state() -> None:
    policy = resource_planning.default_policy(version="test")
    route = {
        "ok": True,
        "allowed": True,
        "unattended_allowed": True,
        "route": {
            "cpuset": "2-5",
            "env": {"OMP_NUM_THREADS": "4"},
            "routing_required": True,
        },
    }

    plan = resource_planning.systemd_plan(
        policy,
        "indexing",
        "medium",
        route,
        "service",
        total_mem_kib=64 * 1024 * 1024,
        environ={"ABYSS_MACHINE_INDEXING_MEMORY_HIGH": "3072M", "ABYSS_MACHINE_INDEXING_MEMORY_MAX": "5120M"},
    )
    argv = resource_planning.systemd_command(
        {"request": {"normalized_class": "medium", "normalized_kind": "indexing"}, "systemd": plan},
        ["python", "-m", "fixture"],
        unit="abyss-machine-indexing-medium-test.service",
        same_dir=True,
    )

    assert plan["slice"] == "abyss-machine-indexing.slice"
    assert plan["properties"]["AllowedCPUs"] == "2-5"
    assert "MemoryHigh" not in plan["properties"]
    assert "MemoryMax" not in plan["properties"]
    assert plan["policy"]["static_memory_caps_applied"] is False
    assert "-p" in argv
    assert not any(item.startswith("MemoryHigh=") or item.startswith("MemoryMax=") for item in argv)
    assert not any("MemorySwapMax=" in item for item in argv)
    assert "-E" in argv
    assert "ABYSS_RESOURCE_KIND=indexing" in argv


def test_resource_planning_keeps_unattended_medium_agent_free_of_generic_hard_caps() -> None:
    policy = resource_planning.default_policy(version="test")
    route = {
        "ok": True,
        "allowed": True,
        "unattended_allowed": True,
        "route": {"cpuset": "0-1", "env": {}},
    }

    plan = resource_planning.build_plan(
        workload_class="medium",
        kind="agent",
        latency="balanced",
        unattended=True,
        force=False,
        bytes_required=None,
        target=None,
        unit_type="service",
        sample_thermal=False,
        policy=policy,
        mode={"launch_policy": {"max_unattended_class": "medium"}},
        memory={
            "class": "green",
            "recommended_new_work": {
                "medium": {
                    "allowed": True,
                    "unattended_allowed": True,
                    "blocked_reasons": [],
                    "unattended_blocked_reasons": [],
                }
            },
        },
        storage={"summary": {"root_pressure_class": "green", "srv_pressure_class": "green"}},
        game_guard={"active": False},
        route=route,
        thermal_plan={"thermal": {"class": "green"}},
        write_preflight=None,
        paths={"latest": "/state/resource/latest.json"},
        input_latest_paths={},
        thermal_unattended_cap="medium",
        total_mem_kib=32 * 1024 * 1024,
        environ={},
        version="test",
        generated_at="2026-06-30T12:00:00+00:00",
    )

    props = plan["systemd"]["properties"]
    assert plan["decision"] == "allow"
    assert "MemoryHigh" not in props
    assert "MemoryMax" not in props
    assert "MemorySwapMax" not in props
    assert plan["systemd"]["policy"]["static_memory_caps_applied"] is False
    assert plan["policy"]["static_memory_caps_applied"] is False


def test_resource_planning_keeps_unattended_medium_ai_free_of_generic_hard_caps() -> None:
    plan = resource_planning.build_plan(
        workload_class="medium",
        kind="ai",
        latency="balanced",
        unattended=True,
        force=False,
        bytes_required=None,
        target=None,
        unit_type="service",
        sample_thermal=False,
        policy=resource_planning.default_policy(version="test"),
        mode={"launch_policy": {"max_unattended_class": "medium"}},
        memory={
            "class": "green",
            "recommended_new_work": {
                "medium": {
                    "allowed": True,
                    "unattended_allowed": True,
                    "blocked_reasons": [],
                    "unattended_blocked_reasons": [],
                }
            },
        },
        storage={"summary": {"root_pressure_class": "green", "srv_pressure_class": "green"}},
        game_guard={"active": False},
        route={"ok": True, "allowed": True, "unattended_allowed": True, "route": {"cpuset": "0-1", "env": {}}},
        thermal_plan={"thermal": {"class": "green"}},
        write_preflight=None,
        paths={"latest": "/state/resource/latest.json"},
        input_latest_paths={},
        thermal_unattended_cap="medium",
        total_mem_kib=32 * 1024 * 1024,
        environ={},
        version="test",
        generated_at="2026-06-30T12:00:00+00:00",
    )

    props = plan["systemd"]["properties"]
    assert plan["decision"] == "allow"
    assert "MemoryHigh" not in props
    assert "MemoryMax" not in props
    assert "MemorySwapMax" not in props
    assert plan["systemd"]["policy"]["static_memory_caps_applied"] is False


def test_resource_plan_honors_owner_routed_heavy_over_base_mode_cap() -> None:
    common = {
        "workload_class": "heavy",
        "kind": "agent",
        "latency": "balanced",
        "unattended": True,
        "force": False,
        "bytes_required": None,
        "target": None,
        "unit_type": "service",
        "sample_thermal": False,
        "policy": resource_planning.default_policy(version="test"),
        "memory": {"class": "green"},
        "storage": {"summary": {"root_pressure_class": "green", "srv_pressure_class": "green"}},
        "game_guard": {"active": False},
        "thermal_plan": {"thermal": {"class": "warm"}},
        "write_preflight": None,
        "paths": {"latest": "/state/resource/latest.json"},
        "input_latest_paths": {},
        "thermal_unattended_cap": "heavy",
        "total_mem_kib": 32 * 1024 * 1024,
        "environ": {},
        "version": "test",
        "generated_at": "2026-07-23T12:00:00+00:00",
    }
    route = {
        "ok": True,
        "allowed": True,
        "unattended_allowed": True,
        "route": {
            "cpuset": "0-1,6-11,14-15",
            "env": {},
            "routing_required": True,
        },
    }
    authorized = resource_planning.build_plan(
        mode={
            "launch_policy": {
                "max_unattended_class": "medium",
                "cpu_routed_heavy": {
                    "can_start_unattended": True,
                    "requires_route_application": True,
                },
            }
        },
        route=route,
        **common,
    )
    missing_owner_authority = resource_planning.build_plan(
        mode={
            "launch_policy": {
                "max_unattended_class": "medium",
                "cpu_routed_heavy": {
                    "can_start_unattended": False,
                    "requires_route_application": True,
                },
            }
        },
        route=route,
        **common,
    )
    malformed_owner_route = resource_planning.build_plan(
        mode={
            "launch_policy": {
                "max_unattended_class": "medium",
                "cpu_routed_heavy": {
                    "can_start_unattended": True,
                    "requires_route_application": True,
                },
            }
        },
        route={
            "ok": True,
            "allowed": True,
            "unattended_allowed": True,
            "route": {"cpuset": "0-1,6-11,14-15", "env": {}},
        },
        **common,
    )

    assert authorized["decision"] == "allow"
    assert authorized["systemd"]["properties"]["AllowedCPUs"] == "0-1,6-11,14-15"
    assert authorized["policy"]["owner_routed_heavy_can_satisfy_base_mode_unattended_cap"] is True
    assert missing_owner_authority["decision"] == "force_required"
    assert missing_owner_authority["blocked_reasons"] == ["mode_unattended_cap_medium"]
    assert malformed_owner_route["decision"] == "force_required"
    assert malformed_owner_route["blocked_reasons"] == ["mode_unattended_cap_medium"]


def test_resource_planning_keeps_advisory_cpu_route_uncapped_when_placement_is_not_required() -> None:
    plan = resource_planning.systemd_plan(
        resource_planning.default_policy(version="test"),
        "benchmark",
        "heavy",
        {
            "route": {
                "cpuset": "0-1,6-11,14-15",
                "env": {"OMP_NUM_THREADS": "6"},
                "routing_required": False,
                "avoid_cpus": [],
                "hard_avoid_cpus": [],
            }
        },
        "service",
        total_mem_kib=32 * 1024 * 1024,
        environ={},
        unattended=True,
    )

    assert "AllowedCPUs" not in plan["properties"]
    assert plan["env"] == {}
    assert plan["policy"]["cpu_placement_required"] is False
    assert plan["policy"]["advisory_cpuset_not_applied"] is True
    assert plan["policy"]["thread_env_from_ai_cpu_route"] is False


def test_resource_planning_applies_cpu_route_when_live_thermal_avoidance_requires_it() -> None:
    plan = resource_planning.systemd_plan(
        resource_planning.default_policy(version="test"),
        "benchmark",
        "medium",
        {
            "route": {
                "cpuset": "6-15",
                "env": {"OMP_NUM_THREADS": "4"},
                "routing_required": False,
                "avoid_cpus": [0, 1],
                "hard_avoid_cpus": [],
            }
        },
        "service",
        total_mem_kib=32 * 1024 * 1024,
        environ={},
        unattended=True,
    )

    assert plan["properties"]["AllowedCPUs"] == "6-15"
    assert plan["env"] == {"OMP_NUM_THREADS": "4"}
    assert plan["policy"]["cpu_placement_required"] is True
    assert plan["policy"]["cpu_placement_reasons"] == ["thermal_route_avoid_cpus"]


def test_resource_planning_keeps_operator_visible_medium_agent_uncapped_by_swap_budget() -> None:
    plan = resource_planning.systemd_plan(
        resource_planning.default_policy(version="test"),
        "agent",
        "medium",
        {"route": {"cpuset": "0-1", "env": {}}},
        "service",
        total_mem_kib=32 * 1024 * 1024,
        environ={},
        unattended=False,
    )

    assert "MemoryHigh" not in plan["properties"]
    assert "MemoryMax" not in plan["properties"]
    assert "MemorySwapMax" not in plan["properties"]
    assert plan["policy"]["static_memory_caps_applied"] is False


def test_resource_planning_keeps_operator_visible_medium_ai_uncapped_by_swap_budget() -> None:
    plan = resource_planning.systemd_plan(
        resource_planning.default_policy(version="test"),
        "ai",
        "medium",
        {"route": {"cpuset": "0-1", "env": {}}},
        "service",
        total_mem_kib=32 * 1024 * 1024,
        environ={},
        unattended=False,
    )

    assert "MemoryHigh" not in plan["properties"]
    assert "MemoryMax" not in plan["properties"]
    assert "MemorySwapMax" not in plan["properties"]
    assert plan["policy"]["static_memory_caps_applied"] is False


def test_resource_plan_keeps_storage_denial_authoritative_even_when_forced() -> None:
    data = resource_planning.build_plan(
        workload_class="medium",
        kind="indexing",
        latency="balanced",
        unattended=False,
        force=True,
        bytes_required=1024,
        target="/srv/abyss-machine/index",
        unit_type="service",
        sample_thermal=False,
        policy=resource_planning.default_policy(version="test"),
        mode={"launch_policy": {"max_unattended_class": "probe"}},
        memory={"pressure": {"summary": {"swap_used_percent": 80, "swap_free_mib": 512}}},
        storage={"summary": {"root_pressure_class": "green", "srv_pressure_class": "green"}},
        game_guard={"active": True},
        route={"ok": False, "allowed": False, "unattended_allowed": False, "route": {}},
        thermal_plan=None,
        write_preflight={"allowed": False, "decision": "deny"},
        paths={"latest": "/state/resource/latest.json"},
        input_latest_paths={},
        thermal_unattended_cap="light",
        total_mem_kib=16 * 1024 * 1024,
        environ={},
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
    )

    assert data["decision"] == "deny"
    assert data["ok"] is False
    assert data["blocked_reasons"] == []
    assert "cpu_route_denied" in data["overridden_reasons"]
    assert data["denied_reasons"] == ["storage_write_preflight_deny"]
    assert data["policy"]["force_does_not_override_storage_denials"] is True


def test_resource_plan_owner_foreground_bypasses_only_advisory_power_defer() -> None:
    common = {
        "workload_class": "heavy",
        "kind": "ai",
        "latency": "interactive",
        "unattended": False,
        "force": False,
        "bytes_required": None,
        "target": None,
        "unit_type": "service",
        "sample_thermal": False,
        "policy": resource_planning.default_policy(version="test"),
        "mode": {"launch_policy": {"max_unattended_class": "probe"}},
        "memory": {"pressure": {"summary": {}}},
        "storage": {"summary": {"root_pressure_class": "green", "srv_pressure_class": "green"}},
        "game_guard": {"active": False},
        "thermal_plan": {
            "thermal": {"class": "warm"},
            "recommended_new_work": {
                "heavy": {
                    "allowed": False,
                    "unattended_allowed": False,
                    "foreground_allowed": True,
                }
            },
        },
        "write_preflight": None,
        "paths": {"latest": "/state/resource/latest.json"},
        "input_latest_paths": {},
        "thermal_unattended_cap": "probe",
        "total_mem_kib": 32 * 1024 * 1024,
        "environ": {},
        "version": "test",
        "generated_at": "2026-07-13T12:00:00+00:00",
        "activity": "foreground",
    }

    advisory = resource_planning.build_plan(
        route={
            "ok": True,
            "allowed": False,
            "unattended_allowed": False,
            "foreground_allowed": True,
            "foreground_blocked_reasons": [],
            "reasons": ["battery_discharging", "heavy_cpu_start_deferred_on_battery"],
            "route": {"cpuset": "4-11", "env": {}},
        },
        **common,
    )
    emergency = resource_planning.build_plan(
        route={
            "ok": True,
            "allowed": False,
            "unattended_allowed": False,
            "foreground_allowed": False,
            "foreground_blocked_reasons": ["package_critical"],
            "route": {"cpuset": "4-11", "env": {}},
        },
        **common,
    )

    assert advisory["decision"] == "allow"
    assert advisory["warnings"] == [
        "cpu_route_owner_foreground_advisory_defer",
        "thermal_plan_owner_foreground_advisory_defer",
    ]
    assert advisory["request"]["activity"]["foreground"] is True
    assert emergency["decision"] == "force_required"
    assert emergency["blocked_reasons"] == ["cpu_route_denied"]
    assert emergency["policy"]["foreground_never_bypasses_memory_reserve_or_emergency_route_denial"] is True


def test_resource_plan_accepts_storage_owner_allow_contract() -> None:
    blocked, denied, warnings = resource_planning.storage_gate(
        {"summary": {"root_pressure_class": "green", "srv_pressure_class": "green"}},
        {"ok": True, "decision": "allow", "reasons": ["target_matches_policy"]},
    )

    assert blocked == []
    assert denied == []
    assert warnings == []


def test_resource_plan_blocks_failed_storage_owner_allow_contract() -> None:
    blocked, denied, warnings = resource_planning.storage_gate(
        {"summary": {"root_pressure_class": "green", "srv_pressure_class": "green"}},
        {"ok": False, "decision": "allow", "reasons": ["target_matches_policy"]},
    )

    assert blocked == ["storage_write_preflight_allow"]
    assert denied == []
    assert warnings == []


def test_resource_plan_does_not_treat_unattended_force_as_background_permission() -> None:
    data = resource_planning.build_plan(
        workload_class="medium",
        kind="indexing",
        latency="balanced",
        unattended=True,
        force=True,
        bytes_required=None,
        target=None,
        unit_type="service",
        sample_thermal=False,
        policy=resource_planning.default_policy(version="test"),
        mode={"launch_policy": {"max_unattended_class": "medium"}},
        memory={"pressure": {"summary": {"swap_used_percent": 80, "swap_free_mib": 512}}},
        storage={"summary": {"root_pressure_class": "green", "srv_pressure_class": "green"}},
        game_guard={"active": False},
        route={"ok": True, "allowed": True, "unattended_allowed": True, "route": {}},
        thermal_plan=None,
        write_preflight=None,
        paths={"latest": "/state/resource/latest.json"},
        input_latest_paths={},
        thermal_unattended_cap="medium",
        total_mem_kib=16 * 1024 * 1024,
        environ={},
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
    )

    assert data["forced"] is True
    assert data["force_effective"] is False
    assert data["decision"] == "allow"
    assert data["blocked_reasons"] == []
    assert data["overridden_reasons"] == []
    assert data["warnings"] == ["unattended_force_not_operator_effective"]
    assert data["policy"]["force_effective_only_when_unattended_false"] is True


def test_resource_plan_ignores_legacy_numeric_memory_recommendation() -> None:
    data = resource_planning.build_plan(
        workload_class="medium",
        kind="ai",
        latency="balanced",
        unattended=True,
        force=False,
        bytes_required=None,
        target=None,
        unit_type="service",
        sample_thermal=False,
        policy=resource_planning.default_policy(version="test"),
        mode={"launch_policy": {"max_unattended_class": "medium"}},
        memory={
            "recommended_new_work": {
                "medium": {
                    "allowed": True,
                    "unattended_allowed": False,
                    "blocked_reasons": [],
                    "unattended_blocked_reasons": ["memory_zram_headroom_blocks_unattended_medium"],
                }
            },
            "pressure": {"summary": {"swap_used_percent": 88, "swap_free_mib": 1790}},
        },
        storage={"summary": {"root_pressure_class": "green", "srv_pressure_class": "green"}},
        game_guard={"active": False},
        route={"ok": True, "allowed": True, "unattended_allowed": True, "route": {}},
        thermal_plan=None,
        write_preflight=None,
        paths={"latest": "/state/resource/latest.json"},
        input_latest_paths={},
        thermal_unattended_cap="medium",
        total_mem_kib=16 * 1024 * 1024,
        environ={},
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
    )

    assert data["decision"] == "allow"
    assert data["blocked_reasons"] == []
    assert data["denied_reasons"] == []
    assert data["policy"]["legacy_memory_recommendations_are_advisory"] is True


def test_resource_plan_does_not_infer_background_ai_importance_from_swap_debt() -> None:
    data = resource_planning.build_plan(
        workload_class="medium",
        kind="ai",
        latency="balanced",
        unattended=True,
        force=False,
        bytes_required=None,
        target=None,
        unit_type="service",
        sample_thermal=False,
        policy=resource_planning.default_policy(version="test"),
        mode={"launch_policy": {"max_unattended_class": "medium"}},
        memory={
            "pressure": {
                "summary": {
                    "swap_used_percent": 47.0,
                    "swap_free_mib": 10800.0,
                    "target_swap_free_mib": 2048.0,
                    "psi_some_avg10": 0.0,
                    "psi_full_avg10": 0.0,
                }
            }
        },
        storage={"summary": {"root_pressure_class": "green", "srv_pressure_class": "green"}},
        game_guard={"active": False},
        route={"ok": True, "allowed": True, "unattended_allowed": True, "route": {}},
        thermal_plan=None,
        write_preflight=None,
        paths={"latest": "/state/resource/latest.json"},
        input_latest_paths={},
        thermal_unattended_cap="medium",
        total_mem_kib=16 * 1024 * 1024,
        environ={},
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
    )

    assert data["decision"] == "allow"
    assert data["blocked_reasons"] == []
    assert data["policy"]["swap_occupancy_gating"] is False
    assert data["policy"]["pressure_facts_assign_workload_importance"] is False


def test_resource_command_demand_key_is_stable_and_does_not_store_arguments() -> None:
    first = resource_planning.command_demand_key(
        ["/usr/bin/abyss-machine", "nervous", "index-build", "--token", "secret-a"]
    )
    second = resource_planning.command_demand_key(
        ["/usr/bin/abyss-machine", "nervous", "index-build", "--token", "secret-b"]
    )
    env_wrapped = resource_planning.command_demand_key(
        ["/usr/bin/env", "PRIVATE_TOKEN=secret-c", "/usr/bin/abyss-machine", "nervous", "index-build"]
    )
    env_unset = resource_planning.command_demand_key(
        ["/usr/bin/env", "-u", "PRIVATE_TOKEN", "/usr/bin/abyss-machine", "nervous", "index-build"]
    )

    assert first == second == "abyss-machine:nervous:index-build"
    assert env_wrapped == first
    assert env_unset == first
    assert "secret" not in first


def test_resource_plan_does_not_apply_background_ai_swap_gate_to_agents() -> None:
    data = resource_planning.build_plan(
        workload_class="medium",
        kind="agent",
        latency="balanced",
        unattended=True,
        force=False,
        bytes_required=None,
        target=None,
        unit_type="service",
        sample_thermal=False,
        policy=resource_planning.default_policy(version="test"),
        mode={"launch_policy": {"max_unattended_class": "medium"}},
        memory={"pressure": {"summary": {"swap_used_percent": 47.0, "swap_free_mib": 10800.0}}},
        storage={"summary": {"root_pressure_class": "green", "srv_pressure_class": "green"}},
        game_guard={"active": False},
        route={"ok": True, "allowed": True, "unattended_allowed": True, "route": {}},
        thermal_plan=None,
        write_preflight=None,
        paths={"latest": "/state/resource/latest.json"},
        input_latest_paths={},
        thermal_unattended_cap="medium",
        total_mem_kib=16 * 1024 * 1024,
        environ={},
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
    )

    assert data["decision"] == "allow"
    assert data["blocked_reasons"] == []


def test_resource_plan_keeps_probe_and_operator_visible_work_outside_swap_debt_gate() -> None:
    memory = {
        "pressure": {
            "summary": {
                "swap_used_percent": 99.9,
                "swap_free_mib": 9.0,
                "target_swap_free_mib": 2048.0,
                "psi_some_avg10": 6.0,
                "psi_full_avg10": 3.0,
            }
        }
    }
    common = {
        "latency": "balanced",
        "force": False,
        "bytes_required": None,
        "target": None,
        "unit_type": "service",
        "sample_thermal": False,
        "policy": resource_planning.default_policy(version="test"),
        "mode": {"launch_policy": {"max_unattended_class": "medium"}},
        "memory": memory,
        "storage": {"summary": {"root_pressure_class": "green", "srv_pressure_class": "green"}},
        "game_guard": {"active": False},
        "route": {"ok": True, "allowed": True, "unattended_allowed": True, "route": {}},
        "thermal_plan": None,
        "write_preflight": None,
        "paths": {"latest": "/state/resource/latest.json"},
        "input_latest_paths": {},
        "thermal_unattended_cap": "medium",
        "total_mem_kib": 16 * 1024 * 1024,
        "environ": {},
        "version": "test",
        "generated_at": "2026-06-25T12:00:00+00:00",
    }

    probe = resource_planning.build_plan(
        workload_class="probe",
        kind="ai",
        unattended=True,
        **common,
    )
    foreground = resource_planning.build_plan(
        workload_class="medium",
        kind="ai",
        unattended=False,
        **common,
    )

    assert probe["decision"] == "allow"
    assert foreground["decision"] == "allow"


def test_resource_thermal_stale_game_guarded_plan_warns_without_thermal_block() -> None:
    blocked, warnings = resource_planning.thermal_plan_gate_reasons(
        {
            "thermal": {"class": "warm"},
            "recommended_new_work": {
                "medium": {
                    "allowed": True,
                    "unattended_allowed": False,
                    "game_guarded": True,
                },
            },
        },
        "medium",
        unattended=True,
        force=False,
        active_game=False,
        sample_thermal=False,
        thermal_unattended_cap="medium",
    )

    assert blocked == []
    assert warnings == ["ignored_stale_thermal_plan_game_guard"]


def test_resource_thermal_admission_projects_only_gate_relevant_route_evidence() -> None:
    attestation = resource_planning.thermal_admission_attestation(
        workload_class="medium",
        thermal_map={
            "ok": True,
            "class": "warm",
            "summary": {
                "mapped_core_sensors": 16,
                "route_avoid_cpus": [7],
                "hard_avoid_cpus": [],
            },
            "episode": {"class": "warm_background"},
            "available_by_role_cpuset": {"p_cores": "0-6"},
        },
        route={
            "schema": "abyss_machine_ai_cpu_route_v1",
            "generated_at": "2026-08-12T09:00:00-06:00",
            "ok": True,
            "allowed": True,
            "unattended_allowed": False,
            "foreground_allowed": True,
            "foreground_blocked_reasons": [],
            "requested": {"normalized_class": "medium"},
            "route": {"cpuset": "0-6", "thread_limit": 4},
            "reasons": ["thermal_hotspot_routed_away_from_avoid_cpus"],
        },
        generated_at="2026-08-12T09:00:00-06:00",
        version="test",
    )

    assert attestation["ok"] is True
    assert attestation["thermal"]["class"] == "warm"
    assert attestation["recommended_new_work"]["medium"] == {
        "allowed": True,
        "unattended_allowed": False,
        "foreground_allowed": True,
        "foreground_blocked_reasons": [],
        "cpuset": "0-6",
        "thread_limit": 4,
    }
    assert attestation["cpu_route"]["requested"] == {
        "normalized_class": "medium"
    }
    assert attestation["diagnostics"]["process_attribution"] == {
        "collected": False,
        "role": "diagnostic_only",
        "command": "abyss-machine processes thermal-attribution --json",
    }
    assert attestation["policy"][
        "diagnostics_are_not_admission_dependencies"
    ] is True


def test_resource_thermal_admission_fails_closed_on_missing_or_mismatched_evidence() -> None:
    attestation = resource_planning.thermal_admission_attestation(
        workload_class="heavy",
        thermal_map={
            "ok": False,
            "class": "unknown",
            "summary": {},
        },
        route={
            "ok": True,
            "allowed": True,
            "unattended_allowed": True,
            "foreground_allowed": True,
            "foreground_blocked_reasons": [],
            "requested": {"normalized_class": "medium"},
            "route": {"cpuset": "0-3", "thread_limit": 4},
        },
        generated_at="2026-08-12T09:00:00-06:00",
        version="test",
    )

    assert attestation["ok"] is False
    assert attestation["evidence_errors"] == [
        "thermal_map_unavailable",
        "cpu_route_request_mismatch",
    ]
    assert attestation["recommended_new_work"]["heavy"]["allowed"] is False
    blocked, warnings = resource_planning.thermal_plan_gate_reasons(
        attestation,
        "heavy",
        unattended=False,
        force=False,
        active_game=False,
        sample_thermal=True,
        thermal_unattended_cap="light",
        activity="foreground",
    )
    assert blocked == [
        "thermal_attestation_unavailable",
        "thermal_plan_denied",
    ]
    assert warnings == []


def test_resource_thermal_admission_fails_closed_on_route_identity_mismatch() -> None:
    attestation = resource_planning.thermal_admission_attestation(
        workload_class="medium",
        latency="interactive",
        force=False,
        thermal_map={"ok": True, "class": "green", "summary": {}},
        route={
            "ok": True,
            "allowed": True,
            "forced": True,
            "unattended_allowed": True,
            "foreground_allowed": True,
            "foreground_blocked_reasons": [],
            "requested": {
                "normalized_class": "medium",
                "latency": "balanced",
            },
            "route": {"cpuset": "0-3", "thread_limit": 4},
        },
        generated_at="2026-08-12T09:00:00-06:00",
        version="test",
    )

    assert attestation["ok"] is False
    assert attestation["evidence_errors"] == [
        "cpu_route_latency_mismatch",
        "cpu_route_force_mismatch",
    ]
    assert attestation["recommended_new_work"]["medium"]["allowed"] is False


def test_resource_thermal_admission_fails_closed_on_malformed_route_payload() -> None:
    attestation = resource_planning.thermal_admission_attestation(
        workload_class="medium",
        thermal_map={"ok": True, "class": "green", "summary": {}},
        route={
            "ok": True,
            "allowed": "true",
            "unattended_allowed": "true",
            "foreground_allowed": True,
            "foreground_blocked_reasons": [],
            "requested": {
                "normalized_class": "medium",
                "latency": "balanced",
            },
            "route": {},
        },
        generated_at="2026-08-12T09:00:00-06:00",
        version="test",
    )

    assert attestation["ok"] is False
    assert attestation["evidence_errors"] == [
        "cpu_route_payload_unavailable"
    ]
    assert attestation["recommended_new_work"]["medium"]["allowed"] is False
    assert (
        attestation["recommended_new_work"]["medium"][
            "unattended_allowed"
        ]
        is False
    )


def test_resource_parse_systemd_run_output_contract() -> None:
    parsed = resource_planning.parse_systemd_run_output(
        "Running as unit: fixture.service; invocation ID: abc\n"
        "Finished with result: success\n"
        "Main processes terminated with: code=exited/status=0\n"
        "Service runtime: 1.234s\n"
        "CPU time consumed: 2.000s\n"
        "Memory peak: 64M\n"
    )

    assert parsed == {
        "unit": "fixture.service",
        "result": "success",
        "main_status": "code=exited/status=0",
        "service_runtime": "1.234s",
        "cpu_time_consumed": "2.000s",
        "memory_peak": "64M",
    }

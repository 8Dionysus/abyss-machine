from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import resource_planning


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


def test_resource_planning_builds_indexing_systemd_contract_without_cli_state() -> None:
    policy = resource_planning.default_policy(version="test")
    route = {
        "ok": True,
        "allowed": True,
        "unattended_allowed": True,
        "route": {"cpuset": "2-5", "env": {"OMP_NUM_THREADS": "4"}},
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

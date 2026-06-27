from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import ai_cpu_routing


def thermal_map_fixture(thermal_class: str = "warm") -> dict:
    return {
        "ok": True,
        "class": thermal_class,
        "available_by_role": {
            "p_cores": [0, 1, 2, 3],
            "e_cores": [4, 5, 6, 7, 8, 9],
            "lp_e_cores": [10, 11],
            "unknown": [],
        },
        "summary": {
            "package_temperature_c_max": 101.0,
            "core_temperature_c_max": 86.0,
            "mapped_core_sensors": 8,
            "route_avoid_cpus": [0, 1],
            "hard_avoid_cpus": [],
            "hot_cpus": [0],
            "critical_cpus": [],
        },
        "thresholds": {
            "hot_temperature_c": 106.0,
            "package_critical_temperature_c": 109.0,
        },
    }


def test_ai_cpu_route_selects_safe_hot_heavy_cpu_set_without_forcing() -> None:
    cpus, basis = ai_cpu_routing.select_route_cpus(
        "heavy",
        "balanced",
        thermal_map_fixture("hot"),
        config={"cpu_routing": {"package_critical_temperature_c": 109.0}},
        force=False,
    )

    assert cpus == [4, 5, 6, 7, 8, 9, 10, 11]
    assert basis == "heavy_deferred_hot_report_safe_cpu_set"


def test_ai_cpu_route_contract_defers_heavy_on_battery_and_preserves_hints() -> None:
    data = ai_cpu_routing.build_route(
        workload_class="heavy",
        latency="balanced",
        force=False,
        thermal_map=thermal_map_fixture("warm"),
        policy={"class": "warm", "can_run_heavy": True},
        mode={"effective_mode": "balanced"},
        battery={"ac_online": False},
        config={"cpu_routing": {"thread_limits": {"heavy": 6}}},
        mode_policy={"thermal_launch_policy": {"unknown": {"max_unattended_class_cap": "light"}}},
        source_refs={"route_latest": "/state/ai/cpu/route/latest.json"},
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
    )

    assert data["schema"] == "abyss_machine_ai_cpu_route_v1"
    assert data["ok"] is True
    assert data["allowed"] is False
    assert data["unattended_allowed"] is False
    assert "heavy_cpu_start_deferred_on_battery" in data["reasons"]
    assert data["route"]["thread_limit"] == 6
    assert data["route"]["env"]["OMP_NUM_THREADS"] == "6"
    assert data["policy"]["application_rule"].startswith("Route returns taskset")


def test_ai_cpu_routed_heavy_policy_blocks_broad_heat() -> None:
    thermal = thermal_map_fixture("warm")
    thermal["summary"]["route_avoid_cpus"] = [0, 1, 2, 3, 4, 5]

    policy = ai_cpu_routing.routed_heavy_policy(
        thermal,
        "warm",
        "balanced",
        True,
        config={
            "thermal_policy": {"min_battery_percent_for_heavy": 35},
            "cpu_routing": {
                "thread_limits": {"heavy": 6},
                "routed_heavy_min_cpus": 4,
                "routed_heavy_broad_heat_avoid_cpu_count": 6,
            },
        },
        capacity_percent=80,
        trend="stable",
    )

    assert policy["allowed"] is False
    assert policy["decision"] == "defer_broad_heat"
    assert policy["distribution"]["broad_heat"] is True

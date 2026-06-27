from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import resource_planning


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
        environ={
            "ABYSS_MACHINE_INDEXING_MEMORY_HIGH": "3072M",
            "ABYSS_MACHINE_INDEXING_MEMORY_MAX": "5120M",
        },
    )
    argv = resource_planning.systemd_command(
        {"request": {"normalized_class": "medium", "normalized_kind": "indexing"}, "systemd": plan},
        ["python", "-m", "fixture"],
        unit="abyss-machine-indexing-medium-test.service",
        same_dir=True,
    )

    assert plan["slice"] == "abyss-machine-indexing.slice"
    assert plan["properties"]["AllowedCPUs"] == "2-5"
    assert plan["properties"]["MemoryHigh"] == "3072M"
    assert plan["properties"]["MemoryMax"] == "5120M"
    assert "-p" in argv
    assert "MemoryMax=5120M" in argv
    assert "-E" in argv
    assert "ABYSS_RESOURCE_KIND=indexing" in argv


def test_resource_plan_keeps_storage_denial_authoritative_even_when_forced() -> None:
    data = resource_planning.build_plan(
        workload_class="medium",
        kind="indexing",
        latency="balanced",
        unattended=True,
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

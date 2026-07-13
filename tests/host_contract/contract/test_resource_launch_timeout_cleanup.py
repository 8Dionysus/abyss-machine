from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time


def test_resource_plan_keeps_unattended_medium_indexing_under_soft_memory_high(abyss_machine_module):
    plan = abyss_machine_module.resource_plan(
        workload_class="medium",
        kind="indexing",
        unattended=True,
        sample_thermal=False,
        write_latest=False,
        mode_data={"effective_mode": "balanced", "launch_policy": {"max_unattended_class": "medium"}},
        memory_data={
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
        storage_data={"summary": {}},
        game_guard_data={"active": False},
        route_data={
            "ok": True,
            "allowed": True,
            "unattended_allowed": True,
            "route": {"cpuset": "0-1", "env": {}},
        },
        thermal_plan_data={"thermal": {"class": "green"}},
    )

    props = plan["systemd"]["properties"]
    assert props["MemoryHigh"] == "4096M"
    assert "MemoryMax" not in props
    assert "MemorySwapMax" not in props
    assert plan["systemd"]["policy"]["memory_max_not_set"] is True
    assert plan["systemd"]["policy"]["memory_max_set_for_indexing"] is False
    assert plan["policy"]["memory_max_not_set_by_default"] is True
    assert plan["policy"]["memory_max_set_for_indexing"] is False


def test_resource_plan_reuses_bounded_inputs_but_refreshes_memory_and_game_guard(
    monkeypatch,
    tmp_path,
    abyss_machine_module,
):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    generated_at = abyss_machine_module.now_iso()
    latest_documents = {
        "mode": {
            "schema": "abyss_machine_mode_plan_v1",
            "generated_at": generated_at,
            "ok": True,
            "effective_mode": "balanced",
            "launch_policy": {"max_unattended_class": "medium"},
        },
        "storage": {
            "schema": "abyss_machine_storage_pressure_v1",
            "generated_at": generated_at,
            "ok": True,
            "summary": {"root_pressure_class": "green", "srv_pressure_class": "green"},
        },
        "route": {
            "schema": "abyss_machine_ai_cpu_route_v1",
            "generated_at": generated_at,
            "ok": True,
            "allowed": True,
            "unattended_allowed": True,
            "forced": False,
            "requested": {"normalized_class": "light", "latency": "balanced"},
            "route": {"cpuset": "0-1", "env": {}},
        },
        "pressure": {
            "schema": "abyss_machine_memory_pressure_v1",
            "generated_at": generated_at,
            "ok": True,
            "processes": {"summary": {"processes": 123, "cgroup_memory_read": 20, "cgroup_swap_read": 20}},
        },
    }
    paths = {}
    for name, document in latest_documents.items():
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        paths[name] = path
    monkeypatch.setattr(abyss_machine_module, "MODE_PLAN_LATEST_PATH", paths["mode"])
    monkeypatch.setattr(abyss_machine_module, "STORAGE_PRESSURE_LATEST_PATH", paths["storage"])
    monkeypatch.setattr(abyss_machine_module, "AI_CPU_ROUTE_LATEST_PATH", paths["route"])
    monkeypatch.setattr(abyss_machine_module, "MEMORY_PRESSURE_LATEST_PATH", paths["pressure"])

    current_status = {
        "generated_at": generated_at,
        "ok": True,
        "class": "warm",
        "reasons": ["current_live_status"],
        "meminfo": {"summary": {"mem_available_mib": 16000.0, "mem_available_percent": 50.0, "swap_used_mib": 8400.0, "swap_used_percent": 42.0, "swap_free_mib": 11600.0}},
        "psi": {"some": {"avg10": 0.0}, "full": {"avg10": 0.0}},
        "swap": {"devices": [{"name": "/dev/zram0"}], "summary": {"free_mib": 11600.0}},
        "zram": {"summary": {"data_mib": 8000.0, "total_memory_mib": 4000.0, "logical_to_memory_ratio": 2.0}},
        "zswap": {},
        "oomd": {},
    }
    game_guard = {"ok": True, "active": False, "platform_present": False, "summary": {}}
    monkeypatch.setattr(abyss_machine_module, "memory_status", lambda **_kwargs: current_status)
    monkeypatch.setattr(abyss_machine_module, "process_game_guard", lambda **_kwargs: game_guard)

    def unexpected_refresh(**_kwargs):
        raise AssertionError("fresh bounded input should have been reused")

    monkeypatch.setattr(abyss_machine_module, "mode_plan", unexpected_refresh)
    monkeypatch.setattr(abyss_machine_module, "storage_pressure", unexpected_refresh)
    monkeypatch.setattr(abyss_machine_module, "ai_cpu_route", unexpected_refresh)
    captured = {}

    def fake_memory_plan(**kwargs):
        captured.update(kwargs)
        pressure = kwargs["pressure_input"]
        return {
            "ok": True,
            "class": pressure["class"],
            "pressure": {"summary": pressure["summary"]},
            "recommended_new_work": {
                "light": {"allowed": True, "unattended_allowed": True, "blocked_reasons": [], "unattended_blocked_reasons": []}
            },
        }

    monkeypatch.setattr(abyss_machine_module, "memory_plan", fake_memory_plan)
    plan = abyss_machine_module.resource_plan(
        workload_class="light",
        kind="agent",
        unattended=True,
        sample_thermal=False,
        write_latest=False,
        policy_data=abyss_machine_module.resource_planning.default_policy(version="test"),
        thermal_plan_data={"thermal": {"class": "green"}},
    )

    assert plan["input_freshness"]["mode"]["status"] == "fresh_latest_reused"
    assert plan["input_freshness"]["storage"]["status"] == "fresh_latest_reused"
    assert plan["input_freshness"]["cpu_route"]["status"] == "fresh_latest_reused"
    assert plan["input_freshness"]["memory"]["status"] == "live_status_with_bounded_attribution"
    assert plan["input_freshness"]["memory"]["live_status"]["status"] == "live_refresh"
    assert plan["input_freshness"]["game_guard"]["status"] == "live_refresh"
    assert plan["policy"]["subsecond_live_input_coalescing"] is True
    assert captured["pressure_input"]["summary"]["swap_used_percent"] == 42.0
    assert captured["pressure_input"]["summary"]["processes"] == 123


def test_resource_subsecond_latest_input_uses_precise_file_age(tmp_path, abyss_machine_module):
    path = tmp_path / "live.json"
    document = {
        "schema": "abyss_machine_memory_status_v1",
        "generated_at": abyss_machine_module.now_iso(),
        "ok": True,
    }
    path.write_text(json.dumps(document), encoding="utf-8")

    current, freshness = abyss_machine_module.resource_subsecond_latest_input(path, max_age_sec=1.0)
    assert current == document
    assert freshness["status"] == "fresh_latest_reused"
    assert freshness["age_source"] == "file_mtime_ns"

    old_ns = time.time_ns() - 3_000_000_000
    os.utime(path, ns=(old_ns, old_ns))
    stale, freshness = abyss_machine_module.resource_subsecond_latest_input(path, max_age_sec=1.0)
    assert stale is None
    assert freshness["status"] == "latest_stale"


def test_resource_plan_keeps_unattended_medium_agent_free_of_generic_hard_caps(abyss_machine_module):
    plan = abyss_machine_module.resource_plan(
        workload_class="medium",
        kind="agent",
        unattended=True,
        sample_thermal=False,
        write_latest=False,
        mode_data={"effective_mode": "balanced", "launch_policy": {"max_unattended_class": "medium"}},
        memory_data={
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
        storage_data={"summary": {}},
        game_guard_data={"active": False},
        route_data={
            "ok": True,
            "allowed": True,
            "unattended_allowed": True,
            "route": {"cpuset": "0-1", "env": {}},
        },
        thermal_plan_data={"thermal": {"class": "green"}},
    )

    props = plan["systemd"]["properties"]
    assert props["MemoryHigh"] == "23628M"
    assert "MemoryMax" not in props
    assert "MemorySwapMax" not in props
    assert plan["systemd"]["policy"]["generic_unattended_hard_caps_not_applied"] is True
    assert plan["policy"]["generic_unattended_hard_caps_not_applied"] is True


def test_resource_plan_keeps_unattended_medium_ai_free_of_generic_hard_caps(abyss_machine_module):
    plan = abyss_machine_module.resource_plan(
        workload_class="medium",
        kind="ai",
        unattended=True,
        sample_thermal=False,
        write_latest=False,
        mode_data={"effective_mode": "balanced", "launch_policy": {"max_unattended_class": "medium"}},
        memory_data={
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
        storage_data={"summary": {}},
        game_guard_data={"active": False},
        route_data={
            "ok": True,
            "allowed": True,
            "unattended_allowed": True,
            "route": {"cpuset": "0-1", "env": {}},
        },
        thermal_plan_data={"thermal": {"class": "green"}},
    )

    props = plan["systemd"]["properties"]
    assert props["MemoryHigh"] == "23628M"
    assert "MemoryMax" not in props
    assert "MemorySwapMax" not in props
    assert plan["systemd"]["policy"]["generic_unattended_hard_caps_not_applied"] is True
    assert plan["policy"]["generic_unattended_hard_caps_not_applied"] is True


def test_resource_plan_blocks_unattended_medium_indexing_under_swap_pressure(abyss_machine_module):
    plan = abyss_machine_module.resource_plan(
        workload_class="medium",
        kind="indexing",
        unattended=True,
        sample_thermal=False,
        write_latest=False,
        mode_data={"effective_mode": "balanced", "launch_policy": {"max_unattended_class": "medium"}},
        memory_data={
            "class": "green",
            "pressure": {"summary": {"swap_used_percent": 46.0, "swap_free_mib": 8192}},
            "recommended_new_work": {
                "medium": {
                    "allowed": True,
                    "unattended_allowed": True,
                    "blocked_reasons": [],
                    "unattended_blocked_reasons": [],
                }
            },
        },
        storage_data={"summary": {}},
        game_guard_data={"active": False},
        route_data={
            "ok": True,
            "allowed": True,
            "unattended_allowed": True,
            "route": {"cpuset": "0-1", "env": {}},
        },
        thermal_plan_data={"thermal": {"class": "green"}},
    )

    assert plan["ok"] is False
    assert plan["decision"] == "force_required"
    assert "indexing_unattended_swap_used_pressure" in plan["blocked_reasons"]
    assert plan["policy"]["unattended_indexing_blocks_on_swap_pressure"] is True


def test_resource_plan_does_not_force_unattended_indexing_under_swap_pressure(abyss_machine_module):
    plan = abyss_machine_module.resource_plan(
        workload_class="medium",
        kind="indexing",
        unattended=True,
        force=True,
        sample_thermal=False,
        write_latest=False,
        mode_data={"effective_mode": "balanced", "launch_policy": {"max_unattended_class": "medium"}},
        memory_data={
            "class": "green",
            "pressure": {"summary": {"swap_used_percent": 46.0, "swap_free_mib": 8192}},
            "recommended_new_work": {
                "medium": {
                    "allowed": True,
                    "unattended_allowed": True,
                    "blocked_reasons": [],
                    "unattended_blocked_reasons": [],
                }
            },
        },
        storage_data={"summary": {}},
        game_guard_data={"active": False},
        route_data={
            "ok": True,
            "allowed": True,
            "unattended_allowed": True,
            "route": {"cpuset": "0-1", "env": {}},
        },
        thermal_plan_data={"thermal": {"class": "green"}},
    )

    assert plan["forced"] is True
    assert plan["force_effective"] is False
    assert plan["ok"] is False
    assert plan["decision"] == "force_required"
    assert plan["blocked_reasons"] == ["indexing_unattended_swap_used_pressure"]
    assert plan["overridden_reasons"] == []
    assert plan["warnings"] == ["unattended_force_not_operator_effective"]


def test_resource_launch_timeout_stops_transient_unit(abyss_machine_module, monkeypatch, tmp_path):
    calls: list[list[str]] = []
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))

    def fake_plan(**kwargs):
        return {
            "systemd": {
                "unit_type": kwargs.get("unit_type") or "service",
                "slice": "abyss-machine-ai.slice",
                "properties": {},
                "env": {},
            },
            "request": {
                "normalized_class": kwargs.get("workload_class") or "heavy",
                "normalized_kind": kwargs.get("kind") or "ai",
            },
            "blocked_reasons": [],
            "denied_reasons": [],
        }

    def fake_command_exists(name: str) -> bool:
        return name in {"systemd-run", "systemctl"}

    def fake_run(cmd, **kwargs):
        command = [str(item) for item in cmd]
        calls.append(command)
        if command[0] == "systemd-run":
            assert "--unit" in command
            unit = command[command.index("--unit") + 1]
            assert unit.startswith("abyss-machine-ai-heavy-")
            assert unit.endswith(".service")
            raise subprocess.TimeoutExpired(
                cmd=command,
                timeout=kwargs.get("timeout"),
                output=f"Running as unit: {unit}\n",
                stderr="",
            )
        if command[:3] == ["systemctl", "--user", "stop"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[:3] == ["systemctl", "--user", "is-active"]:
            return subprocess.CompletedProcess(command, 3, "inactive\n", "")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(abyss_machine_module, "resource_plan", fake_plan)
    monkeypatch.setattr(abyss_machine_module, "command_exists", fake_command_exists)
    monkeypatch.setattr(abyss_machine_module.subprocess, "run", fake_run)

    result = abyss_machine_module.resource_launch(
        ["/bin/sleep", "60"],
        workload_class="heavy",
        kind="ai",
        timeout_sec=0.1,
        write_latest=False,
    )

    cleanup = result["execution"]["timeout_cleanup"]
    assert result["ok"] is False
    assert result["execution"]["returncode"] == 124
    assert result["request"]["launch_unit"].startswith("abyss-machine-ai-heavy-")
    assert result["execution"]["systemd"]["unit"] == result["request"]["launch_unit"]
    assert cleanup["attempted"] is True
    assert cleanup["unit"] == result["request"]["launch_unit"]
    assert cleanup["stop"]["returncode"] == 0
    assert cleanup["state"]["value"] == "inactive"
    assert any(call[:3] == ["systemctl", "--user", "stop"] for call in calls)


def test_resource_launch_releases_startup_lease_after_submit(monkeypatch, tmp_path, abyss_machine_module):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    policy = abyss_machine_module.resource_planning.default_policy(version="test")
    monkeypatch.setattr(abyss_machine_module, "resource_policy_document", lambda: policy)

    def fake_plan(**kwargs):
        requested = abyss_machine_module.resource_planning.resolve_startup_demand(
            policy,
            workload_class=kwargs["workload_class"],
            kind=kwargs["kind"],
            explicit_mib=kwargs.get("memory_demand_mib"),
            demand_key=kwargs.get("demand_key"),
        )
        return {
            "ok": True,
            "decision": "allow",
            "blocked_reasons": [],
            "denied_reasons": [],
            "request": {"normalized_class": "medium", "normalized_kind": "ai"},
            "inputs": {"startup_demand": {"requested": requested}},
            "systemd": {"unit_type": "service", "slice": "abyss-machine-ai.slice", "properties": {}, "env": {}},
        }

    monkeypatch.setattr(abyss_machine_module, "resource_plan", fake_plan)
    monkeypatch.setattr(
        abyss_machine_module.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 0, "Finished with result: success\n", ""),
    )

    result = abyss_machine_module.resource_launch(
        ["/usr/bin/true"],
        workload_class="medium",
        kind="ai",
        memory_demand_mib=4096,
        write_latest=False,
    )

    assert result["ok"] is True
    assert result["startup_admission"]["lease"]["demand_mib"] == 4096.0
    assert result["startup_admission"]["lease_released"] is True
    reservation_root = Path(result["startup_admission"]["reservation_root"])
    assert list(reservation_root.glob("*.json")) == []


def test_resource_control_plane_paths_are_latest_only(abyss_machine_module) -> None:
    paths = abyss_machine_module.resource_paths()

    for lane in ("plans", "runs", "orchestrator"):
        assert paths[lane]["retention"] == "latest_only"
        assert "daily_glob" not in paths[lane]


def test_unattended_resource_launch_uses_direct_reservation_without_resident_controller(
    monkeypatch,
    tmp_path,
    abyss_machine_module,
):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    policy = abyss_machine_module.resource_planning.default_policy(version="test")
    monkeypatch.setattr(abyss_machine_module, "resource_policy_document", lambda: policy)

    def fake_plan(**kwargs):
        requested = abyss_machine_module.resource_planning.resolve_startup_demand(
            policy,
            workload_class=kwargs["workload_class"],
            kind=kwargs["kind"],
            explicit_mib=kwargs.get("memory_demand_mib"),
            demand_key=kwargs.get("demand_key"),
            demand_owner=kwargs.get("demand_owner"),
        )
        return {
            "ok": True,
            "decision": "allow",
            "blocked_reasons": [],
            "denied_reasons": [],
            "request": {"normalized_class": "medium", "normalized_kind": "agent"},
            "inputs": {"startup_demand": {"requested": requested}},
            "systemd": {"unit_type": "service", "slice": "abyss-machine-agents.slice", "properties": {}, "env": {}},
        }

    monkeypatch.setattr(abyss_machine_module, "resource_plan", fake_plan)
    monkeypatch.setattr(
        abyss_machine_module.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 0, "Finished with result: success\n", ""),
    )

    result = abyss_machine_module.resource_launch(
        ["/usr/bin/true"],
        workload_class="medium",
        kind="agent",
        unattended=True,
        memory_demand_mib=2048,
        demand_owner="agent-owner",
        startup_wait_sec=1,
        write_latest=False,
    )

    assert result["ok"] is True
    assert result["startup_admission"]["lease"]["demand_owner"] == "agent-owner"
    assert result["startup_admission"]["lease_released"] is True
    assert "controller_queue" not in result["startup_admission"]
    assert result["policy"]["resident_memory_controller_required"] is False
    assert not (tmp_path / "run" / "abyss-machine" / "memory-controller").exists()

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import subprocess
import time

import pytest


def test_ai_cpu_launch_is_only_a_resource_launch_compatibility_wrapper(abyss_machine_module, monkeypatch):
    captured: dict[str, object] = {}

    def fake_resource_launch(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return {
            "schema": "abyss_machine_resource_launch_v1",
            "ok": True,
            "started_at": "2026-07-13T04:00:00-06:00",
            "dry_run": True,
            "request": {"force": False, "unattended": False, "demand_key": "fixture"},
            "blocked_reasons": [],
            "denied_reasons": [],
            "plan": {
                "decision": "allow",
                "inputs": {
                    "cpu_route": {"route": {"cpuset": "0-1"}},
                    "game_guard": {"active": False},
                    "memory": {"class": "green", "summary": {"mem_available_mib": 8192}},
                    "startup_demand": {"admission": {"allowed": True}},
                },
                "systemd": {"env": {}},
            },
            "argv": ["systemd-run", "--user", "/usr/bin/true"],
            "execution": None,
            "elapsed_sec": 0.0,
            "startup_admission": {"runtime_only": True},
            "paths": {"latest": "/tmp/resource/latest.json"},
        }

    monkeypatch.setattr(abyss_machine_module, "resource_launch", fake_resource_launch)

    result = abyss_machine_module.ai_cpu_launch(
        ["/usr/bin/true"],
        workload_class="heavy",
        dry_run=True,
        write_latest=False,
    )

    assert captured["command"] == ["/usr/bin/true"]
    assert captured["kwargs"]["kind"] == "ai"
    assert captured["kwargs"]["unit_type"] == "service"
    assert result["ok"] is True
    assert result["policy"]["compatibility_wrapper_only"] is True
    assert result["policy"]["single_execution_route"] == "abyss-machine resource launch --kind ai"
    assert "gate" not in result["memory"]


def test_resource_plan_keeps_unattended_medium_indexing_without_static_memory_caps(abyss_machine_module):
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
    assert "MemoryHigh" not in props
    assert "MemoryMax" not in props
    assert "MemorySwapMax" not in props
    assert plan["systemd"]["policy"]["static_memory_caps_applied"] is False
    assert plan["systemd"]["policy"]["memory_max_not_set"] is True
    assert plan["policy"]["static_memory_caps_applied"] is False
    assert plan["policy"]["memory_max_not_set"] is True


def test_storage_write_preflight_no_write_is_transitive(
    abyss_machine_module,
    monkeypatch,
    tmp_path,
):
    calls: dict[str, object] = {}
    target = tmp_path / "artifact.bin"
    usage = {
        "total_bytes": 40 * 1024**3,
        "used_bytes": 10 * 1024**3,
        "free_bytes": 30 * 1024**3,
        "used_percent": 25.0,
    }

    def fake_storage_monitor(**kwargs):
        calls["monitor"] = kwargs
        return {
            "ok": True,
            "summary": {
                "root_pressure_class": "green",
                "srv_pressure_class": "green",
            },
        }

    def unexpected_write(*_args, **_kwargs):
        pytest.fail("write_latest=False must not persist storage state")

    monkeypatch.setattr(abyss_machine_module, "storage_monitor", fake_storage_monitor)
    monkeypatch.setattr(
        abyss_machine_module,
        "storage_path_protection",
        lambda _path: {"class": "host_owned_allowed", "decision": "allow_candidate"},
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "storage_preflight_recommended_target",
        lambda _kind, _target: str(target),
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "storage_preflight_recommended_base",
        lambda _kind: str(tmp_path),
    )
    monkeypatch.setattr(abyss_machine_module, "disk_usage_summary", lambda _path: usage)
    monkeypatch.setattr(abyss_machine_module, "storage_protected_roots", lambda: [])
    monkeypatch.setattr(
        abyss_machine_module,
        "run_storage_hooks",
        lambda *_args, **_kwargs: {"ok": True},
    )
    monkeypatch.setattr(abyss_machine_module, "safe_atomic_write_json", unexpected_write)
    monkeypatch.setattr(abyss_machine_module, "safe_append_jsonl", unexpected_write)

    result = abyss_machine_module.storage_write_preflight(
        kind="artifact",
        bytes_required=1024,
        target=str(target),
        write_latest=False,
    )

    assert calls["monitor"] == {
        "process_guard": True,
        "interval": 0.0,
        "top": 30,
        "write_latest": False,
    }
    assert result["ok"] is True
    assert result["decision"] == "allow"


def test_storage_monitor_no_write_is_transitive(
    abyss_machine_module,
    monkeypatch,
):
    calls: dict[str, dict[str, object]] = {}

    def fake_collector(name, result):
        def collect(**kwargs):
            calls[name] = kwargs
            return result

        return collect

    def unexpected_write(*_args, **_kwargs):
        pytest.fail("write_latest=False must not persist nested storage state")

    monkeypatch.setattr(
        abyss_machine_module,
        "storage_inventory",
        fake_collector("inventory", {"ok": True, "summary": {}}),
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "storage_pressure",
        fake_collector(
            "pressure",
            {
                "ok": True,
                "summary": {
                    "root_pressure_class": "green",
                    "srv_pressure_class": "green",
                },
            },
        ),
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "storage_cleanup_plan",
        fake_collector("cleanup", {"ok": True, "summary": {}, "guard": {}}),
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "storage_status",
        fake_collector("status", {"ok": True, "summary": {}}),
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "artifacts_snapshot",
        fake_collector("artifacts", {"ok": True, "summary": {}}),
    )
    monkeypatch.setattr(abyss_machine_module, "safe_atomic_write_json", unexpected_write)
    monkeypatch.setattr(abyss_machine_module, "safe_append_jsonl", unexpected_write)

    result = abyss_machine_module.storage_monitor(write_latest=False)

    assert calls["inventory"]["write_latest"] is False
    assert calls["pressure"]["write_latest"] is False
    assert calls["cleanup"]["write_latest"] is False
    assert calls["status"]["write_latest"] is False
    assert calls["artifacts"]["write_latest"] is False
    assert result["ok"] is True


@pytest.mark.parametrize("refresh", [False, True])
def test_storage_inventory_refresh_honors_no_write(
    abyss_machine_module,
    monkeypatch,
    refresh,
):
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        abyss_machine_module,
        "load_json_document",
        lambda _path: (None, "missing"),
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "storage_inventory",
        lambda **kwargs: calls.append(kwargs) or {"ok": True, "items": []},
    )

    inventory, _error = abyss_machine_module.storage_inventory_latest_or_refresh(
        refresh=refresh,
        write_latest=False,
    )

    assert inventory["ok"] is True
    assert calls == [
        {
            "full": False,
            "include_home_review": False,
            "write_latest": False,
        }
    ]


def test_storage_pressure_no_write_propagates_to_inventory(
    abyss_machine_module,
    monkeypatch,
):
    calls: dict[str, object] = {}

    def fake_inventory(**kwargs):
        calls["inventory"] = kwargs
        return {"ok": True, "items": []}, None

    monkeypatch.setattr(
        abyss_machine_module,
        "storage_inventory_latest_or_refresh",
        fake_inventory,
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "storage_status",
        lambda **_kwargs: {
            "ok": True,
            "roots": {
                "system": {
                    "total_bytes": 100,
                    "used_bytes": 10,
                    "free_bytes": 90,
                    "used_percent": 10.0,
                },
                "srv": {
                    "total_bytes": 100,
                    "used_bytes": 10,
                    "free_bytes": 90,
                    "used_percent": 10.0,
                },
            },
        },
    )

    result = abyss_machine_module.storage_pressure(write_latest=False)

    assert calls["inventory"] == {
        "refresh": False,
        "write_latest": False,
    }
    assert result["ok"] is True


def test_storage_cleanup_plan_no_write_propagates_to_process_guard(
    abyss_machine_module,
    monkeypatch,
):
    calls: dict[str, object] = {}

    def fake_process_guard(paths, **kwargs):
        calls["paths"] = paths
        calls["guard"] = kwargs
        return {
            "ok": True,
            "paths": [],
            "summary": {
                "paths": 0,
                "active_paths": 0,
                "active_process_refs": 0,
            },
        }

    def unexpected_write(*_args, **_kwargs):
        pytest.fail("write_latest=False must not persist process-guard state")

    monkeypatch.setattr(
        abyss_machine_module,
        "storage_inventory_latest_or_refresh",
        lambda **_kwargs: ({"ok": True, "items": []}, None),
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "storage_pressure",
        lambda **kwargs: calls.setdefault("pressure", kwargs)
        and {
            "ok": True,
            "summary": {
                "root_pressure_class": "green",
                "srv_pressure_class": "green",
            },
        },
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "storage_process_path_usage",
        fake_process_guard,
    )
    monkeypatch.setattr(abyss_machine_module, "safe_atomic_write_json", unexpected_write)
    monkeypatch.setattr(abyss_machine_module, "safe_append_jsonl", unexpected_write)

    result = abyss_machine_module.storage_cleanup_plan(
        process_guard=True,
        write_latest=False,
    )

    assert calls["paths"] == []
    assert calls["pressure"] == {
        "refresh_inventory": False,
        "write_latest": False,
    }
    assert calls["guard"] == {
        "interval": 0.5,
        "top": 30,
        "write_latest": False,
    }
    assert result["ok"] is True


def test_resource_plan_no_write_propagates_to_storage_preflight(
    abyss_machine_module,
    monkeypatch,
):
    calls: dict[str, object] = {}
    target = "/srv/abyss-machine/tmp/no-write-probe"

    def fake_storage_write_preflight(**kwargs):
        calls["preflight"] = kwargs
        return {"ok": True, "decision": "allow", "reasons": []}

    monkeypatch.setattr(
        abyss_machine_module,
        "storage_write_preflight",
        fake_storage_write_preflight,
    )

    plan = abyss_machine_module.resource_plan(
        workload_class="medium",
        kind="agent",
        unattended=False,
        bytes_required=1024,
        target=target,
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
        storage_data={
            "summary": {
                "root_pressure_class": "green",
                "srv_pressure_class": "green",
            }
        },
        game_guard_data={"active": False},
        route_data={
            "ok": True,
            "allowed": True,
            "unattended_allowed": True,
            "route": {"cpuset": "0-1", "env": {}},
        },
        thermal_plan_data={"thermal": {"class": "green"}},
    )

    assert calls["preflight"] == {
        "kind": "artifact",
        "bytes_required": 1024,
        "target": target,
        "write_latest": False,
    }
    assert plan["decision"] == "allow"


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
    assert "MemoryHigh" not in props
    assert "MemoryMax" not in props
    assert "MemorySwapMax" not in props
    assert plan["systemd"]["policy"]["static_memory_caps_applied"] is False
    assert plan["policy"]["static_memory_caps_applied"] is False


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
    assert "MemoryHigh" not in props
    assert "MemoryMax" not in props
    assert "MemorySwapMax" not in props
    assert plan["systemd"]["policy"]["static_memory_caps_applied"] is False
    assert plan["policy"]["static_memory_caps_applied"] is False


def test_resource_plan_does_not_block_indexing_from_swap_occupancy(abyss_machine_module):
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

    assert plan["ok"] is True
    assert plan["decision"] == "allow"
    assert plan["blocked_reasons"] == []
    assert plan["policy"]["swap_occupancy_gating"] is False


def test_resource_plan_does_not_turn_unattended_force_into_permission(abyss_machine_module):
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
    assert plan["ok"] is True
    assert plan["decision"] == "allow"
    assert plan["blocked_reasons"] == []
    assert plan["overridden_reasons"] == []
    assert plan["warnings"] == [
        "unattended_force_not_operator_effective",
        "startup_demand_bootstrap_uncalibrated",
    ]


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
    monkeypatch.setattr(
        abyss_machine_module.resource_adapters,
        "journal_unit_resource_peaks",
        lambda unit, **_kwargs: {"ok": False, "unit": unit, "error": "fixture_no_peak"},
    )

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


def test_unattended_resource_launch_remeasures_after_active_stall(
    abyss_machine_module,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    policy = abyss_machine_module.resource_planning.default_policy(version="test")
    monkeypatch.setattr(abyss_machine_module, "resource_policy_document", lambda: policy)
    plan_calls = 0

    def fake_plan(**kwargs):
        nonlocal plan_calls
        plan_calls += 1
        requested = abyss_machine_module.resource_planning.resolve_startup_demand(
            policy,
            workload_class=kwargs["workload_class"],
            kind=kwargs["kind"],
            explicit_mib=kwargs.get("memory_demand_mib"),
            demand_key=kwargs.get("demand_key"),
            demand_owner=kwargs.get("demand_owner"),
        )
        blocked = ["startup_new_unattended_work_during_active_memory_stall"] if plan_calls == 1 else []
        return {
            "ok": not blocked,
            "decision": "force_required" if blocked else "allow",
            "blocked_reasons": blocked,
            "denied_reasons": [],
            "request": {"normalized_class": "medium", "normalized_kind": "agent"},
            "inputs": {"startup_demand": {"requested": requested}},
            "systemd": {
                "unit_type": "service",
                "slice": "abyss-machine-agents.slice",
                "properties": {},
                "env": {},
            },
        }

    monkeypatch.setattr(abyss_machine_module, "resource_plan", fake_plan)
    monkeypatch.setattr(
        abyss_machine_module.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(
            command,
            0,
            "Finished with result: success\n",
            "",
        ),
    )
    monkeypatch.setattr(
        abyss_machine_module.resource_adapters,
        "journal_unit_resource_peaks",
        lambda unit, **_kwargs: {"ok": False, "unit": unit, "error": "fixture_no_peak"},
    )

    result = abyss_machine_module.resource_launch(
        ["/usr/bin/true"],
        workload_class="medium",
        kind="agent",
        unattended=True,
        memory_demand_mib=512,
        demand_owner="agent-owner",
        startup_wait_sec=1,
        write_latest=False,
    )

    assert plan_calls == 2
    assert result["ok"] is True
    assert result["request"]["force"] is False
    assert result["startup_admission"]["wait_attempts"] == 1
    assert result["execution"]["returncode"] == 0


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
    monkeypatch.setattr(
        abyss_machine_module.resource_adapters,
        "journal_unit_resource_peaks",
        lambda unit, **_kwargs: {
            "ok": True,
            "unit": unit,
            "memory_peak_mib": 512.0,
            "memory_swap_peak_mib": 128.0,
            "footprint_peak_mib": 640.0,
        },
    )

    result = abyss_machine_module.resource_launch(
        ["/usr/bin/true"],
        workload_class="medium",
        kind="ai",
        unit="explicit-fixture",
        memory_demand_mib=4096,
        write_latest=False,
    )

    assert result["ok"] is True
    assert result["request"]["unit"] == "explicit-fixture"
    assert result["request"]["launch_unit"] == "explicit-fixture.service"
    assert result["startup_admission"]["lease"]["unit"] == "explicit-fixture.service"
    assert result["startup_admission"]["demand_observation"]["peaks"]["unit"] == "explicit-fixture.service"
    assert result["startup_admission"]["lease"]["demand_mib"] == 4096.0
    assert result["startup_admission"]["lease_released"] is True
    assert result["startup_admission"]["demand_observation"]["recorded"] is True
    assert result["startup_admission"]["demand_observation"]["record"]["profile"]["key"] == "true"
    assert result["startup_admission"]["demand_observation"]["record"]["profile"]["estimate_mib"] == 800.0
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
    monkeypatch.setattr(
        abyss_machine_module.resource_adapters,
        "journal_unit_resource_peaks",
        lambda unit, **_kwargs: {"ok": False, "unit": unit, "error": "fixture_no_peak"},
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


def test_resource_launch_exec_handoff_uses_memfd_without_runtime_file(abyss_machine_module, monkeypatch):
    captured: dict[str, object] = {}

    class ExecCalled(Exception):
        pass

    def fake_execve(executable, argv, environ):
        fd = int(environ["ABYSS_RESOURCE_LAUNCH_HANDOFF_FD"])
        seals = fcntl.fcntl(fd, fcntl.F_GET_SEALS)
        expected_seals = fcntl.F_SEAL_SEAL | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_GROW | fcntl.F_SEAL_WRITE
        captured["sealed"] = seals & expected_seals == expected_seals
        os.lseek(fd, 0, os.SEEK_SET)
        captured["payload"] = json.loads(os.read(fd, 1024 * 1024).decode("utf-8"))
        captured["executable"] = executable
        captured["argv"] = argv
        raise ExecCalled

    monkeypatch.setattr(abyss_machine_module.os, "execve", fake_execve)

    with pytest.raises(ExecCalled):
        abyss_machine_module.resource_launch_exec_handoff(
            {"schema": "abyss_machine_resource_launch_handoff_v1", "document": {}},
            output_json=True,
            success_on_block=False,
        )

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["output"] == {"json": True, "success_on_block": False}
    assert captured["sealed"] is True
    assert str(captured["argv"][1]).endswith("resource_runner.py")


def test_lightweight_resource_runner_finishes_receipt_and_bounded_writes(
    abyss_machine_module,
    monkeypatch,
    tmp_path,
):
    from abyss_machine import resource_runner

    monkeypatch.setattr(
        resource_runner.resource_adapters,
        "execute_systemd_launch",
        lambda **_kwargs: {
            "elapsed_sec": 3.25,
            "execution": {"ok": True, "returncode": 0, "systemd": {"unit": "fixture.service"}},
            "lease_released": True,
            "demand_observation": {"recorded": True},
        },
    )
    latest = tmp_path / "runs" / "latest.json"
    index = tmp_path / "index.json"
    handoff = {
        "document": {
            "ok": False,
            "blocked_reasons": [],
            "denied_reasons": [],
            "startup_admission": {"lease_released": False},
            "policy": {"long_waiter": "inline_cli"},
        },
        "execution": {
            "systemd_command": ["systemd-run", "--user", "/usr/bin/true"],
            "launch_unit": "fixture.service",
            "generated_unit": None,
            "unit_type": "service",
            "timeout_sec": 5,
            "lease": None,
            "reservation_root": str(tmp_path / "reservations"),
            "demand_profile_path": str(tmp_path / "profiles.json"),
            "demand_key": "fixture",
            "demand_owner": "fixture-owner",
            "kind": "generic",
            "observed_peak_multiplier": 1.25,
            "profile_max_entries": 64,
            "profile_max_samples": 16,
        },
        "write_latest": True,
        "latest_path": str(latest),
        "index_path": str(index),
        "index_document": {"schema": "fixture_index_v1"},
    }

    result = resource_runner.finish_document(handoff)

    assert result["ok"] is True
    assert result["elapsed_sec"] == 3.25
    assert result["startup_admission"]["lease_released"] is True
    assert result["startup_admission"]["demand_observation"] == {"recorded": True}
    assert result["policy"]["long_waiter"] == "lightweight_exec_handoff"
    assert json.loads(latest.read_text(encoding="utf-8"))["execution"]["returncode"] == 0
    assert json.loads(index.read_text(encoding="utf-8"))["schema"] == "fixture_index_v1"


def test_resource_launch_releases_lease_when_exec_handoff_fails(abyss_machine_module, monkeypatch, tmp_path):
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
            "systemd": {
                "unit_type": "service",
                "slice": "abyss-machine-agents.slice",
                "properties": {},
                "env": {},
            },
        }

    monkeypatch.setattr(abyss_machine_module, "resource_plan", fake_plan)

    class HandoffFailed(Exception):
        pass

    def fail_handoff(_payload):
        raise HandoffFailed

    with pytest.raises(HandoffFailed):
        abyss_machine_module.resource_launch(
            ["/usr/bin/true"],
            workload_class="medium",
            kind="agent",
            unattended=True,
            memory_demand_mib=512,
            demand_owner="fixture-owner",
            startup_wait_sec=0,
            write_latest=False,
            execution_delegate=fail_handoff,
        )

    reservation_root = tmp_path / "run" / "abyss-machine" / "resource" / "reservations"
    assert list(reservation_root.glob("*.json")) == []


def test_lightweight_resource_runner_releases_lease_on_failure(monkeypatch, tmp_path):
    from abyss_machine import resource_runner

    root = tmp_path / "reservations"
    lease = {"id": "fixture-lease"}
    resource_runner.resource_adapters.atomic_write_lease(root, lease)
    handoff = {
        "document": {},
        "execution": {
            "lease": lease,
            "reservation_root": str(root),
        },
    }
    monkeypatch.setattr(resource_runner, "read_handoff", lambda: handoff)
    monkeypatch.setattr(resource_runner, "finish_document", lambda _handoff: (_ for _ in ()).throw(RuntimeError("fixture")))

    assert resource_runner.main() == 1
    assert not resource_runner.resource_adapters.lease_path(root, "fixture-lease").exists()

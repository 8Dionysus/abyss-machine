from __future__ import annotations

import contextlib
import fcntl
import json
import os
from pathlib import Path
import subprocess
import threading
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


def test_resource_thermal_admission_uses_fresh_gate_inputs_without_diagnostics(
    abyss_machine_module,
    monkeypatch,
):
    thermal_map = {
        "ok": True,
        "class": "warm",
        "summary": {
            "mapped_core_sensors": 16,
            "route_avoid_cpus": [],
            "hard_avoid_cpus": [],
        },
        "episode": {"class": "warm_background"},
        "available_by_role_cpuset": {"p_cores": "0-3"},
    }
    route = {
        "schema": "abyss_machine_ai_cpu_route_v1",
        "generated_at": "2026-08-12T09:00:00-06:00",
        "ok": True,
        "allowed": True,
        "unattended_allowed": True,
        "foreground_allowed": True,
        "foreground_blocked_reasons": [],
        "requested": {
            "normalized_class": "medium",
            "latency": "balanced",
        },
        "route": {"cpuset": "0-3", "thread_limit": 4},
        "reasons": ["balanced_medium_hybrid_safe"],
    }
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        abyss_machine_module,
        "ai_cpu_thermal_map",
        lambda **_kwargs: thermal_map,
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "ai_policy",
        lambda **_kwargs: {
            "ok": True,
            "current": {
                "mode": {
                    "effective": "balanced",
                    "selected": "balanced",
                },
                "battery": {"ac_online": True},
            },
        },
    )

    def collect_route(**kwargs):
        captured.update(kwargs)
        return route

    monkeypatch.setattr(abyss_machine_module, "ai_cpu_route", collect_route)
    monkeypatch.setattr(
        abyss_machine_module,
        "process_thermal_attribution",
        lambda **_kwargs: pytest.fail(
            "process attribution is diagnostic, not launch admission"
        ),
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "process_desktop_compositor_bounded",
        lambda **_kwargs: pytest.fail(
            "desktop analysis is diagnostic, not launch admission"
        ),
    )

    result = abyss_machine_module.resource_thermal_admission_attestation(
        workload_class="medium",
        latency="balanced",
        write_latest=False,
    )

    assert result["ok"] is True
    assert result["schema"] == (
        "abyss_machine_resource_thermal_admission_attestation_v1"
    )
    assert result["recommended_new_work"]["medium"]["allowed"] is True
    assert result["diagnostics"]["process_attribution"]["collected"] is False
    assert result["diagnostics"]["desktop_compositor"]["collected"] is False
    assert captured["cpu_thermal_map"] is thermal_map
    assert captured["mode_data"] == {
        "effective_mode": "balanced",
        "selected_mode": "balanced",
    }


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

    def fake_storage_pressure(**kwargs):
        calls["pressure"] = kwargs
        return {
            "ok": True,
            "schema": "abyss_machine_storage_pressure_v1",
            "generated_at": "2026-08-12T09:00:00-06:00",
            "summary": {
                "root_pressure_class": "green",
                "srv_pressure_class": "green",
            },
            "roots": {
                "system": {"used_percent": 25.0},
                "srv": {"used_percent": 25.0},
            },
        }

    def unexpected_write(*_args, **_kwargs):
        pytest.fail("write_latest=False must not persist storage state")

    monkeypatch.setattr(
        abyss_machine_module,
        "storage_pressure",
        fake_storage_pressure,
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "storage_monitor",
        lambda **_kwargs: pytest.fail(
            "write admission must not run the cleanup monitor"
        ),
    )
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

    assert calls["pressure"] == {
        "refresh_inventory": False,
        "write_latest": False,
    }
    assert result["ok"] is True
    assert result["decision"] == "allow"
    assert result["policy"]["full_cleanup_monitor_not_required"] is True


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


def test_resource_plan_reuses_supplied_storage_and_thermal_attestations(
    abyss_machine_module,
    monkeypatch,
):
    monkeypatch.setattr(
        abyss_machine_module,
        "storage_write_preflight",
        lambda **_kwargs: pytest.fail(
            "supplied storage proof must not be recomputed"
        ),
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "resource_thermal_admission_attestation",
        lambda **_kwargs: pytest.fail(
            "supplied thermal proof must not be recomputed"
        ),
    )
    storage_proof = {
        "ok": True,
        "decision": "allow",
        "reasons": ["target_matches_policy"],
    }
    thermal_proof = {
        "schema": "abyss_machine_resource_thermal_admission_attestation_v1",
        "ok": True,
        "request": {
            "normalized_class": "medium",
            "normalized_route_latency": "balanced",
            "force": False,
        },
        "thermal": {"class": "green"},
        "recommended_new_work": {
            "medium": {
                "allowed": True,
                "unattended_allowed": True,
            }
        },
        "evidence_errors": [],
        "policy": {
            "fail_closed_on_missing_gate_evidence": True,
        },
    }

    plan = abyss_machine_module.resource_plan(
        workload_class="medium",
        kind="agent",
        bytes_required=1024,
        target="/srv/abyss-machine/tmp/fixture",
        sample_thermal=True,
        write_latest=False,
        mode_data={
            "effective_mode": "balanced",
            "launch_policy": {"max_unattended_class": "medium"},
        },
        memory_data={
            "class": "green",
            "pressure": {
                "summary": {
                    "class": "green",
                    "mem_available_mib": 8192,
                    "mem_total_mib": 16384,
                    "psi_some_avg10": 0.0,
                    "psi_full_avg10": 0.0,
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
        thermal_plan_data=thermal_proof,
        write_preflight_data=storage_proof,
    )

    assert plan["decision"] == "allow"
    assert plan["inputs"]["storage"]["write_preflight"] == storage_proof
    assert plan["inputs"]["thermal_plan"]["ok"] is True
    assert plan["inputs"]["thermal_plan"]["request"] is thermal_proof[
        "request"
    ]
    assert plan["inputs"]["thermal_plan"]["policy"] is thermal_proof[
        "policy"
    ]
    assert plan["policy"]["provided_thermal_attestation_reused"] is True
    assert plan["policy"]["provided_storage_preflight_reused"] is True


def test_resource_launch_collects_attestation_dag_outside_atomic_lock(
    abyss_machine_module,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    policy = abyss_machine_module.resource_planning.default_policy(
        version="test"
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "resource_policy_document",
        lambda: policy,
    )
    inside_lock = False
    collector_barrier = threading.Barrier(4)
    collector_threads: set[int] = set()

    def collect_thermal_map(**_kwargs):
        assert inside_lock is False
        collector_threads.add(threading.get_ident())
        collector_barrier.wait(timeout=1)
        return {
            "ok": True,
            "schema": "fixture_thermal_map_v1",
            "generated_at": "2026-08-12T09:00:00-06:00",
            "class": "green",
        }

    def assemble_thermal(**kwargs):
        assert inside_lock is False
        assert kwargs["thermal_map_data"]["schema"] == (
            "fixture_thermal_map_v1"
        )
        assert kwargs["mode_data"]["schema"] == "fixture_mode_plan_v1"
        return {
            "ok": True,
            "schema": "fixture_thermal_plan_v1",
            "generated_at": "2026-08-12T09:00:00-06:00",
            "thermal": {"class": "green"},
            "cpu_route": {
                "ok": True,
                "schema": "fixture_cpu_route_v1",
                "requested": {"normalized_class": "medium"},
                "allowed": True,
                "unattended_allowed": True,
                "route": {"cpuset": "0-1", "env": {}},
            },
        }

    def collect_storage(**_kwargs):
        assert inside_lock is False
        collector_threads.add(threading.get_ident())
        collector_barrier.wait(timeout=1)
        return {
            "ok": True,
            "schema": "fixture_storage_preflight_v1",
            "generated_at": "2026-08-12T09:00:00-06:00",
            "decision": "allow",
            "reasons": ["target_matches_policy"],
        }

    def collect_mode(**_kwargs):
        assert inside_lock is False
        collector_threads.add(threading.get_ident())
        collector_barrier.wait(timeout=1)
        return {
            "ok": True,
            "schema": "fixture_mode_plan_v1",
            "generated_at": "2026-08-12T09:00:00-06:00",
            "effective_mode": "balanced",
            "launch_policy": {"max_unattended_class": "medium"},
        }

    def collect_game_guard(**_kwargs):
        assert inside_lock is False
        collector_threads.add(threading.get_ident())
        collector_barrier.wait(timeout=1)
        return {
            "ok": True,
            "schema": "fixture_game_guard_v1",
            "generated_at": "2026-08-12T09:00:00-06:00",
            "active": False,
        }

    @contextlib.contextmanager
    def observed_lock(_root):
        nonlocal inside_lock
        assert inside_lock is False
        inside_lock = True
        try:
            yield
        finally:
            inside_lock = False

    def fake_plan(**kwargs):
        assert inside_lock is True
        assert kwargs["force_fresh_live_inputs"] is True
        assert kwargs["thermal_plan_data"]["schema"] == (
            "fixture_thermal_plan_v1"
        )
        assert kwargs["route_data"] is kwargs["thermal_plan_data"]["cpu_route"]
        assert kwargs["route_data"]["schema"] == "fixture_cpu_route_v1"
        assert kwargs["mode_data"]["schema"] == "fixture_mode_plan_v1"
        assert kwargs["game_guard_data"]["schema"] == "fixture_game_guard_v1"
        assert kwargs["write_preflight_data"]["schema"] == (
            "fixture_storage_preflight_v1"
        )
        requested = (
            abyss_machine_module.resource_planning.resolve_startup_demand(
                policy,
                workload_class=kwargs["workload_class"],
                kind=kwargs["kind"],
                explicit_mib=kwargs.get("memory_demand_mib"),
                demand_key=kwargs.get("demand_key"),
                demand_owner=kwargs.get("demand_owner"),
            )
        )
        return {
            "ok": True,
            "decision": "allow",
            "blocked_reasons": [],
            "denied_reasons": [],
            "request": {
                "normalized_class": "medium",
                "normalized_kind": "benchmark",
                "activity": {"normalized": "foreground"},
            },
            "inputs": {"startup_demand": {"requested": requested}},
            "systemd": {
                "unit_type": "service",
                "slice": "abyss-machine-benchmarks.slice",
                "properties": {},
                "env": {},
            },
        }

    monkeypatch.setattr(
        abyss_machine_module,
        "resource_thermal_admission_attestation",
        assemble_thermal,
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "ai_cpu_thermal_map",
        collect_thermal_map,
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "storage_write_preflight",
        collect_storage,
    )
    monkeypatch.setattr(abyss_machine_module, "mode_plan", collect_mode)
    monkeypatch.setattr(
        abyss_machine_module,
        "process_game_guard",
        collect_game_guard,
    )
    monkeypatch.setattr(
        abyss_machine_module.resource_adapters,
        "admission_lock",
        observed_lock,
    )
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
        lambda unit, **_kwargs: {
            "ok": False,
            "unit": unit,
            "error": "fixture_no_peak",
        },
    )

    result = abyss_machine_module.resource_launch(
        ["/usr/bin/true"],
        workload_class="medium",
        kind="benchmark",
        activity="foreground",
        bytes_required=1024,
        target="/srv/abyss-machine/tmp/fixture",
        sample_thermal=True,
        memory_demand_mib=512,
        demand_owner="fixture-owner",
        write_latest=False,
    )

    assert result["ok"] is True
    assert len(collector_threads) == 4
    assert result["planning"]["pre_admission_dag"]["rounds"][0][
        "parallel"
    ] is True
    assert result["planning"]["pre_admission_dag"]["rounds"][0][
        "nodes"
    ]["thermal_admission"]["schema"] == "fixture_thermal_plan_v1"
    assert set(
        result["planning"]["pre_admission_dag"]["rounds"][0]["nodes"]
    ) == {
        "mode_plan",
        "game_guard",
        "thermal_map",
        "thermal_admission",
        "storage_write_preflight",
    }
    assert result["planning"]["pre_admission_dag"]["rounds"][0][
        "waves"
    ] == [
        {
            "wave": 1,
            "parallel": True,
            "nodes": [
                "mode_plan",
                "game_guard",
                "thermal_map",
                "storage_write_preflight",
            ],
        },
        {
            "wave": 2,
            "parallel": False,
            "nodes": ["thermal_admission"],
            "depends_on": ["thermal_map", "mode_plan"],
        },
    ]
    assert result["planning"]["admission_lock"][
        "contains_expensive_preflight"
    ] is False
    assert result["planning"]["admission_lock"]["attempts"] == 1
    assert result["total_elapsed_sec"] >= result["elapsed_sec"]


def test_resource_launch_refreshes_attestation_that_ages_during_atomic_plan(
    abyss_machine_module,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    policy = abyss_machine_module.resource_planning.default_policy(
        version="test"
    )
    policy["startup_admission"]["launch_attestation_max_age_sec"] = 1.0
    monkeypatch.setattr(
        abyss_machine_module,
        "resource_policy_document",
        lambda: policy,
    )
    inside_lock = False
    collector_calls = 0
    plan_calls = 0

    def collect_storage(**_kwargs):
        nonlocal collector_calls
        assert inside_lock is False
        collector_calls += 1
        return {
            "ok": True,
            "schema": "fixture_storage_preflight_v1",
            "generated_at": "2026-08-12T09:00:00-06:00",
            "decision": "allow",
            "reasons": ["target_matches_policy"],
        }

    @contextlib.contextmanager
    def observed_lock(_root):
        nonlocal inside_lock
        assert inside_lock is False
        inside_lock = True
        try:
            yield
        finally:
            inside_lock = False

    def fake_plan(**kwargs):
        nonlocal plan_calls
        assert inside_lock is True
        assert kwargs["write_preflight_data"]["schema"] == (
            "fixture_storage_preflight_v1"
        )
        plan_calls += 1
        if plan_calls == 1:
            time.sleep(1.05)
        return {
            "ok": True,
            "decision": "allow",
            "blocked_reasons": [],
            "denied_reasons": [],
            "request": {
                "normalized_class": "medium",
                "normalized_kind": "benchmark",
                "activity": {"normalized": "foreground"},
            },
            "inputs": {
                "startup_demand": {
                    "requested": {
                        "demand_mib": 512,
                        "reservation_required": False,
                    }
                }
            },
            "systemd": {
                "unit_type": "service",
                "slice": "abyss-machine-benchmarks.slice",
                "properties": {},
                "env": {},
            },
        }

    monkeypatch.setattr(
        abyss_machine_module,
        "storage_write_preflight",
        collect_storage,
    )
    monkeypatch.setattr(
        abyss_machine_module.resource_adapters,
        "admission_lock",
        observed_lock,
    )
    monkeypatch.setattr(abyss_machine_module, "resource_plan", fake_plan)
    monkeypatch.setattr(
        abyss_machine_module.resource_adapters,
        "execute_systemd_launch",
        lambda **_kwargs: {
            "elapsed_sec": 0.01,
            "execution": {"ok": True, "returncode": 0},
            "lease_released": True,
            "demand_observation": None,
        },
    )

    result = abyss_machine_module.resource_launch(
        ["/usr/bin/true"],
        workload_class="medium",
        kind="benchmark",
        activity="foreground",
        bytes_required=1024,
        target="/srv/abyss-machine/tmp/fixture",
        sample_thermal=False,
        memory_demand_mib=512,
        demand_owner="fixture-owner",
        write_latest=False,
    )

    assert result["ok"] is True
    assert collector_calls == 2
    assert plan_calls == 2
    assert result["planning"]["pre_admission_dag"]["refresh_count"] == 2
    assert result["planning"]["admission_lock"]["attempts"] == 2
    assert result["planning"]["pre_admission_dag"][
        "age_at_admission_sec"
    ] <= 1.0


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
        sample_thermal=False,
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
    assert result["planning"]["pre_admission_dag"]["refresh_count"] == 0
    assert result["planning"]["pre_admission_dag"]["rounds"] == []
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
        sample_thermal=False,
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
        sample_thermal=False,
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
        sample_thermal=False,
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
    monkeypatch.setattr(resource_runner, "monotonic", lambda: 100.0)
    latest = tmp_path / "runs" / "latest.json"
    index = tmp_path / "index.json"
    handoff = {
        "document": {
            "ok": False,
            "blocked_reasons": [],
            "denied_reasons": [],
            "planning": {"elapsed_sec": 1.5},
            "startup_admission": {"lease_released": False},
            "policy": {"long_waiter": "inline_cli"},
        },
        "execution": {
            "systemd_command": ["systemd-run", "--user", "/usr/bin/true"],
            "request_started_monotonic": 90.0,
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
    assert result["total_elapsed_sec"] == 10.0
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
            sample_thermal=False,
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

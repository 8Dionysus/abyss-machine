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
    monkeypatch.setenv("ABYSS_MACHINE_RESOURCE_LIVE_INPUT_COALESCE_SEC", "1.0")
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
    plan_calls = 0

    class MonotonicClock:
        def __init__(self):
            self.offset = 0.0

        def monotonic(self):
            return time.monotonic() + self.offset

        def advance(self, seconds):
            self.offset += seconds

        def __getattr__(self, name):
            return getattr(time, name)

    clock = MonotonicClock()
    monkeypatch.setattr(abyss_machine_module, "time", clock)

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
        nonlocal plan_calls
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
        plan_calls += 1
        if plan_calls == 1:
            clock.advance(1.05)
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
    assert plan_calls == 1
    assert result["planning"]["pre_admission_dag"]["refresh_count"] == 1
    assert result["planning"]["pre_admission_dag"][
        "configured_max_age_sec"
    ] == 120.0
    assert result["planning"]["pre_admission_dag"]["max_age_sec"] == 120.0
    assert result["planning"]["pre_admission_dag"][
        "age_at_admission_sec"
    ] > 1.0
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

    class MonotonicClock:
        def __init__(self):
            self.offset = 0.0

        def monotonic(self):
            return time.monotonic() + self.offset

        def advance(self, seconds):
            self.offset += seconds

        def __getattr__(self, name):
            return getattr(time, name)

    clock = MonotonicClock()
    monkeypatch.setattr(abyss_machine_module, "time", clock)

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
            clock.advance(1.05)
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
            "storage_reservation_release": {
                "requested": True,
                "ok": True,
                "decision": "released",
                "release_pending": False,
            },
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


@pytest.mark.parametrize(
    ("configured_ttl", "expected_refresh_count"),
    [(5.0, 1), (1.0, 2)],
)
def test_resource_launch_thermal_attestation_ttl_is_independent_of_live_input_coalescing(
    abyss_machine_module,
    monkeypatch,
    tmp_path,
    configured_ttl,
    expected_refresh_count,
):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    policy = abyss_machine_module.resource_planning.default_policy(
        version="test"
    )
    policy["startup_admission"]["launch_attestation_max_age_sec"] = configured_ttl
    monkeypatch.setattr(
        abyss_machine_module,
        "resource_policy_document",
        lambda: policy,
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "resource_live_input_coalesce_seconds",
        lambda: 1.0,
    )
    # The no-storage request is intentional.  Keep the pre-fix accidental
    # Path("None") branch fail-closed during this thermal-only regression so
    # the test remains about the independent attestation TTL.
    monkeypatch.setattr(
        abyss_machine_module,
        "storage_path_protection",
        lambda _path: {"decision": "deny", "class": "unknown"},
    )

    generated_at = "2026-08-12T09:00:00-06:00"
    mode_data = {
        "ok": True,
        "schema": "fixture_mode_plan_v1",
        "generated_at": generated_at,
        "effective_mode": "balanced",
    }
    game_guard_data = {
        "ok": True,
        "schema": "fixture_game_guard_v1",
        "generated_at": generated_at,
        "active": False,
    }
    thermal_map_data = {
        "ok": True,
        "schema": "fixture_thermal_map_v1",
        "generated_at": generated_at,
        "class": "green",
    }
    thermal_plan_data = {
        "ok": True,
        "schema": "fixture_thermal_plan_v1",
        "generated_at": generated_at,
        "thermal": {"class": "green"},
        "cpu_route": {
            "ok": True,
            "schema": "fixture_cpu_route_v1",
            "requested": {
                "normalized_class": "medium",
                "latency": "balanced",
            },
            "allowed": True,
            "unattended_allowed": True,
            "route": {"cpuset": "0-1", "env": {}},
        },
    }
    collector_calls = {
        "mode": 0,
        "game_guard": 0,
        "thermal_map": 0,
        "thermal_admission": 0,
    }

    def collect(name, document):
        def _collect(**_kwargs):
            collector_calls[name] += 1
            return document

        return _collect

    monkeypatch.setattr(
        abyss_machine_module,
        "mode_plan",
        collect("mode", mode_data),
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "process_game_guard",
        collect("game_guard", game_guard_data),
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "ai_cpu_thermal_map",
        collect("thermal_map", thermal_map_data),
    )

    def collect_thermal_admission(**_kwargs):
        collector_calls["thermal_admission"] += 1
        return thermal_plan_data

    monkeypatch.setattr(
        abyss_machine_module,
        "resource_thermal_admission_attestation",
        collect_thermal_admission,
    )

    plan_calls = 0

    def fake_plan(**kwargs):
        nonlocal plan_calls
        assert kwargs["force_fresh_live_inputs"] is True
        assert kwargs["thermal_plan_data"] is thermal_plan_data
        plan_calls += 1
        if plan_calls == 1:
            # Longer than the one-second cache coalescing horizon, but shorter
            # than the five-second receipt TTL in the first parameter case.
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
                        "demand_mib": 512.0,
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
        sample_thermal=True,
        memory_demand_mib=512,
        demand_owner="fixture-owner",
        startup_wait_sec=0,
        write_latest=False,
    )

    assert result["ok"] is True
    assert plan_calls == expected_refresh_count
    assert result["planning"]["pre_admission_dag"]["refresh_count"] == expected_refresh_count
    assert result["planning"]["pre_admission_dag"]["configured_max_age_sec"] == configured_ttl
    assert result["planning"]["pre_admission_dag"]["max_age_sec"] == configured_ttl
    assert collector_calls["mode"] == expected_refresh_count
    assert collector_calls["game_guard"] == expected_refresh_count
    assert collector_calls["thermal_map"] == expected_refresh_count
    assert collector_calls["thermal_admission"] == expected_refresh_count
    if configured_ttl == 5.0:
        assert result["planning"]["pre_admission_dag"]["age_at_admission_sec"] > 1.0
        assert result["planning"]["pre_admission_dag"]["age_at_admission_sec"] <= configured_ttl
    else:
        assert result["planning"]["pre_admission_dag"]["age_at_admission_sec"] <= configured_ttl


def test_resource_launch_denies_when_attestation_expires_before_execute(
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
    target = tmp_path / "target"
    collector_calls = 0
    acquire_calls: list[dict[str, object]] = []
    release_calls: list[str] = []
    execute_calls = 0

    def collect_storage(**_kwargs):
        nonlocal collector_calls
        collector_calls += 1
        return {
            "ok": True,
            "schema": "fixture_storage_preflight_v1",
            "generated_at": "2026-08-12T09:00:00-06:00",
            "decision": "allow",
        }

    def fake_plan(**kwargs):
        assert kwargs["force_fresh_live_inputs"] is True
        assert kwargs["write_preflight_data"]["schema"] == (
            "fixture_storage_preflight_v1"
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
            "inputs": {
                "startup_demand": {
                    "requested": {
                        "demand_mib": 512.0,
                        "reservation_required": True,
                        "calibrated": True,
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
    monkeypatch.setattr(abyss_machine_module, "resource_plan", fake_plan)
    monkeypatch.setattr(
        abyss_machine_module,
        "storage_path_protection",
        lambda _path: {"decision": "allow_candidate", "class": "host_owned_allowed"},
    )

    def acquire(_root, **kwargs):
        acquire_calls.append(dict(kwargs))
        return {
            "schema": abyss_machine_module.storage_reservations.SCHEMA,
            "ok": True,
            "decision": "reserved",
            "reservation": {
                "reservation_id": str(kwargs["reservation_id"]),
                "owner": "fixture-owner",
                "execution_identity": str(kwargs["execution_identity"]),
                "requested_bytes": 1024,
                "target": str(target),
                "kind": "artifact",
            },
        }

    def release(_root, reservation_id, **_kwargs):
        release_calls.append(str(reservation_id))
        return {"ok": True, "decision": "released", "reservation_id": str(reservation_id)}

    monkeypatch.setattr(
        abyss_machine_module.storage_reservations,
        "acquire_reservation",
        acquire,
    )
    monkeypatch.setattr(
        abyss_machine_module.storage_reservations,
        "release_reservation",
        release,
    )

    def slow_systemd_command(*_args, **_kwargs):
        # Simulate bounded post-admission command preparation crossing the
        # configured receipt TTL.  No systemd unit should be submitted.
        time.sleep(1.05)
        return ["systemd-run", "--user", "/usr/bin/true"]

    monkeypatch.setattr(
        abyss_machine_module,
        "resource_systemd_command",
        slow_systemd_command,
    )

    def execute(**_kwargs):
        nonlocal execute_calls
        execute_calls += 1
        return {
            "elapsed_sec": 0.01,
            "execution": {"ok": True, "returncode": 0},
            "lease_released": True,
            "demand_observation": None,
        }

    monkeypatch.setattr(
        abyss_machine_module.resource_adapters,
        "execute_systemd_launch",
        execute,
    )

    result = abyss_machine_module.resource_launch(
        ["/usr/bin/true"],
        workload_class="medium",
        kind="benchmark",
        activity="foreground",
        bytes_required=1024,
        target=str(target),
        sample_thermal=False,
        memory_demand_mib=512,
        demand_owner="fixture-owner",
        startup_wait_sec=0,
        write_latest=False,
    )

    assert collector_calls == 1
    assert len(acquire_calls) == 1
    assert len(release_calls) == 1
    assert execute_calls == 0
    assert result["ok"] is False
    assert "launch_attestation_expired_before_execute" in result["denied_reasons"]
    assert result["execution"] is None
    assert result["startup_admission"]["lease"] is None
    assert result["startup_admission"]["lease_released"] is True
    assert list(Path(result["startup_admission"]["reservation_root"]).glob("*.json")) == []
    assert result["planning"]["pre_admission_dag"]["age_before_execute_sec"] > 1.0


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
            "launch_attestation": {
                "required": False,
                "deadline_monotonic": None,
            },
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
    lifecycle_root = tmp_path / "lifecycle"
    workspace = tmp_path / "managed-workspace"
    monkeypatch.setattr(abyss_machine_module, "STORAGE_LIFECYCLE_ROOT", lifecycle_root)
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
            workspace_path=str(workspace),
            workspace_owner="fixture-owner",
        )

    reservation_root = tmp_path / "run" / "abyss-machine" / "resource" / "reservations"
    assert list(reservation_root.glob("*.json")) == []
    records = list((lifecycle_root / "workspaces").glob("*.json"))
    assert len(records) == 1
    record = json.loads(records[0].read_text(encoding="utf-8"))
    assert record["state"] == "sealed"
    assert record["lease"] is None
    assert record["disposition"]["decision"] == "UNKNOWN"
    assert record["disposition"]["failure"]["execution_started"] is None
    assert record["disposition"]["failure"]["execution_status"] == "unknown"
    assert record["disposition"]["failure"]["cleanup_report"]["memory_lease"]["released"] is True


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


def test_resource_launch_stale_attestation_seals_managed_workspace_before_execute(
    abyss_machine_module,
    monkeypatch,
    tmp_path,
):
    """A post-registration freshness denial must close the owner lifecycle record."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    policy = abyss_machine_module.resource_planning.default_policy(version="test")
    policy["startup_admission"]["launch_attestation_max_age_sec"] = 1.0
    monkeypatch.setattr(abyss_machine_module, "resource_policy_document", lambda: policy)

    lifecycle_root = tmp_path / "lifecycle"
    target = tmp_path / "target"
    workspace = tmp_path / "managed-workspace"
    monkeypatch.setattr(abyss_machine_module, "STORAGE_LIFECYCLE_ROOT", lifecycle_root)

    class Clock:
        expired = False

        def monotonic(self):
            return 2.0 if self.expired else 0.0

        def __getattr__(self, name):
            return getattr(time, name)

    clock = Clock()
    monkeypatch.setattr(abyss_machine_module, "time", clock)
    monkeypatch.setattr(
        abyss_machine_module,
        "storage_write_preflight",
        lambda **_kwargs: {
            "ok": True,
            "schema": "fixture_storage_preflight_v1",
            "decision": "allow",
        },
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "storage_path_protection",
        lambda _path: {"decision": "allow_candidate", "class": "host_owned_allowed"},
    )

    def fake_plan(**_kwargs):
        return {
            "ok": True,
            "decision": "allow",
            "blocked_reasons": [],
            "denied_reasons": [],
            "request": {"normalized_class": "medium", "normalized_kind": "benchmark"},
            "inputs": {
                "startup_demand": {
                    "requested": {
                        "demand_mib": 512.0,
                        "reservation_required": True,
                        "calibrated": True,
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

    monkeypatch.setattr(abyss_machine_module, "resource_plan", fake_plan)

    def acquire(_root, **kwargs):
        return {
            "schema": abyss_machine_module.storage_reservations.SCHEMA,
            "ok": True,
            "decision": "reserved",
            "reservation": {
                "reservation_id": str(kwargs["reservation_id"]),
                "owner": "fixture-owner",
                "execution_identity": str(kwargs["execution_identity"]),
                "requested_bytes": 1024,
                "target": str(target),
                "kind": "artifact",
            },
        }

    monkeypatch.setattr(abyss_machine_module.storage_reservations, "acquire_reservation", acquire)
    monkeypatch.setattr(
        abyss_machine_module.storage_reservations,
        "release_reservation",
        lambda _root, reservation_id, **_kwargs: {
            "ok": True,
            "decision": "released",
            "reservation_id": str(reservation_id),
        },
    )

    def command_after_expiry(*_args, **_kwargs):
        clock.expired = True
        return ["systemd-run", "--user", "/usr/bin/true"]

    monkeypatch.setattr(abyss_machine_module, "resource_systemd_command", command_after_expiry)
    monkeypatch.setattr(
        abyss_machine_module.resource_adapters,
        "execute_systemd_launch",
        lambda **_kwargs: pytest.fail("stale managed workspace must not execute"),
    )

    result = abyss_machine_module.resource_launch(
        ["/usr/bin/true"],
        workload_class="medium",
        kind="benchmark",
        bytes_required=1024,
        target=str(target),
        sample_thermal=False,
        memory_demand_mib=512,
        demand_owner="fixture-owner",
        startup_wait_sec=0,
        workspace_path=str(workspace),
        workspace_owner="fixture-owner",
        write_latest=False,
    )

    assert result["ok"] is False
    assert "launch_attestation_expired_before_execute" in result["denied_reasons"]
    records = list((lifecycle_root / "workspaces").glob("*.json"))
    assert len(records) == 1
    record = json.loads(records[0].read_text(encoding="utf-8"))
    assert record["state"] == "sealed"
    assert record["lease"] is None
    assert record["disposition"]["decision"] == "UNKNOWN"
    assert record["disposition"]["released"] is False


def test_lightweight_resource_runner_rejects_expired_handoff_before_execute(
    monkeypatch,
    tmp_path,
):
    """The delegated child must enforce the same expiry and lifecycle closeout."""
    from abyss_machine import resource_runner
    from abyss_machine import storage_lifecycle_adapters

    lifecycle_root = tmp_path / "lifecycle"
    workspace = tmp_path / "managed-workspace"
    registered = storage_lifecycle_adapters.register_workspace(
        lifecycle_root,
        owner="fixture-owner",
        workspace=workspace,
        unit="fixture.service",
        lease_seconds=300,
    )
    assert registered["ok"] is True
    record = registered["record"]
    lifecycle = {
        "workspace_id": record["workspace_id"],
        "path": record["path"],
        "owner": record["owner"],
        "launcher_created": record["launcher_created"],
        "callback_path": record["callback_path"],
        "lease_token": registered["lease_token"],
        "grace_seconds": 0,
        "root": str(lifecycle_root),
    }

    reservation_root = tmp_path / "reservations"
    lease = {"id": "fixture-lease"}
    resource_runner.resource_adapters.atomic_write_lease(reservation_root, lease)
    storage_root = tmp_path / "storage-reservations"
    target = tmp_path / "target"
    storage = resource_runner.resource_adapters.storage_reservations.acquire_reservation(
        storage_root,
        reservation_id="fixture-storage",
        kind="artifact",
        requested_bytes=0,
        target=target,
        owner="fixture-owner",
        ttl_seconds=60,
        hold_until_terminal=True,
        execution_identity="fixture-execution",
        disk_usage=lambda *_args, **_kwargs: {
            "available_to_user_bytes": 1_000_000,
            "free_bytes": 1_000_000,
        },
    )
    assert storage["ok"] is True

    monkeypatch.setattr(resource_runner, "monotonic", lambda: 101.0)
    monkeypatch.setattr(
        resource_runner.resource_adapters,
        "execute_systemd_launch",
        lambda **_kwargs: pytest.fail("expired delegated handoff must not execute"),
    )

    handoff = {
        "document": {
            "ok": True,
            "blocked_reasons": [],
            "denied_reasons": [],
            "planning": {"elapsed_sec": 1.0},
            "startup_admission": {"lease_released": False},
        },
        "execution": {
            "systemd_command": ["systemd-run", "--user", "/usr/bin/true"],
            "request_started_monotonic": 90.0,
            "launch_attestation": {
                "required": True,
                "deadline_monotonic": 100.0,
            },
            "launch_unit": "fixture.service",
            "generated_unit": None,
            "unit_type": "service",
            "timeout_sec": 5,
            "lease": lease,
            "reservation_root": str(reservation_root),
            "demand_profile_path": str(tmp_path / "profiles.json"),
            "demand_key": "fixture",
            "demand_owner": "fixture-owner",
            "kind": "generic",
            "observed_peak_multiplier": 1.25,
            "profile_max_entries": 64,
            "profile_max_samples": 16,
            "workspace_lifecycle": lifecycle,
            "storage_reservation": storage["reservation"],
            "storage_reservation_root": str(storage_root),
        },
        "write_latest": False,
    }

    result = resource_runner.finish_document(handoff)

    assert result["ok"] is False
    assert "launch_attestation_expired_before_execute" in result["denied_reasons"]
    assert not resource_runner.resource_adapters.lease_path(
        reservation_root,
        "fixture-lease",
    ).exists()
    listed = resource_runner.resource_adapters.storage_reservations.list_reservations(storage_root)
    assert listed["records"][0]["active"] is False
    lifecycle_record = json.loads(
        next((lifecycle_root / "workspaces").glob("*.json")).read_text(encoding="utf-8")
    )
    assert lifecycle_record["state"] == "sealed"
    assert lifecycle_record["lease"] is None
    assert lifecycle_record["disposition"]["decision"] == "UNKNOWN"


@pytest.mark.parametrize(
    ("launch_attestation", "expected_reason"),
    [
        (None, "launch_attestation_handoff_missing"),
        ({"required": "yes", "deadline_monotonic": 100.0}, "launch_attestation_handoff_malformed"),
        ({"required": True, "deadline_monotonic": None}, "launch_attestation_handoff_malformed"),
        ({"required": False, "deadline_monotonic": 100.0}, "launch_attestation_handoff_malformed"),
    ],
)
def test_lightweight_resource_runner_rejects_missing_or_malformed_attestation(
    monkeypatch,
    tmp_path,
    launch_attestation,
    expected_reason,
):
    from abyss_machine import resource_runner

    monkeypatch.setattr(resource_runner, "monotonic", lambda: 101.0)
    monkeypatch.setattr(
        resource_runner.resource_adapters,
        "execute_systemd_launch",
        lambda **_kwargs: pytest.fail("invalid delegated handoff must not execute"),
    )
    result = resource_runner.finish_document(
        {
            "document": {
                "ok": True,
                "blocked_reasons": [],
                "denied_reasons": [],
            },
            "execution": {
                "systemd_command": ["systemd-run", "--user", "/usr/bin/true"],
                "request_started_monotonic": 90.0,
                "launch_attestation": launch_attestation,
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
                "storage_reservation": None,
                "storage_reservation_root": str(tmp_path / "storage-reservations"),
            },
            "write_latest": False,
        }
    )

    assert result["ok"] is False
    assert expected_reason in result["denied_reasons"]
    assert result["execution"] is None


def test_lightweight_resource_runner_seals_workspace_when_abort_cleanup_steps_fail(
    monkeypatch,
    tmp_path,
):
    """A stale delegated handoff must attempt each owned cleanup independently."""
    from abyss_machine import resource_runner
    from abyss_machine import storage_lifecycle_adapters

    lifecycle_root = tmp_path / "lifecycle"
    workspace = tmp_path / "managed-workspace"
    registered = storage_lifecycle_adapters.register_workspace(
        lifecycle_root,
        owner="fixture-owner",
        workspace=workspace,
        unit="fixture.service",
        lease_seconds=300,
    )
    assert registered["ok"] is True
    record = registered["record"]
    lifecycle = {
        "workspace_id": record["workspace_id"],
        "path": record["path"],
        "owner": record["owner"],
        "launcher_created": record["launcher_created"],
        "callback_path": record["callback_path"],
        "lease_token": registered["lease_token"],
        "grace_seconds": 0,
        "root": str(lifecycle_root),
    }
    monkeypatch.setattr(resource_runner, "monotonic", lambda: 101.0)
    monkeypatch.setattr(
        resource_runner.resource_adapters,
        "execute_systemd_launch",
        lambda **_kwargs: pytest.fail("stale delegated handoff must not execute"),
    )
    monkeypatch.setattr(
        resource_runner.resource_adapters,
        "remove_lease",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("lease busy")),
    )
    monkeypatch.setattr(
        resource_runner.resource_adapters,
        "_release_storage_reservation",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("reservation busy")),
    )

    result = resource_runner.finish_document(
        {
            "document": {
                "ok": True,
                "blocked_reasons": [],
                "denied_reasons": [],
                "planning": {"elapsed_sec": 1.0},
                "startup_admission": {"lease_released": False},
            },
            "execution": {
                "systemd_command": ["systemd-run", "--user", "/usr/bin/true"],
                "request_started_monotonic": 90.0,
                "launch_attestation": {
                    "required": True,
                    "deadline_monotonic": 100.0,
                },
                "launch_unit": "fixture.service",
                "generated_unit": None,
                "unit_type": "service",
                "timeout_sec": 5,
                "lease": {"id": "fixture-lease"},
                "reservation_root": str(tmp_path / "reservations"),
                "demand_profile_path": str(tmp_path / "profiles.json"),
                "demand_key": "fixture",
                "demand_owner": "fixture-owner",
                "kind": "generic",
                "observed_peak_multiplier": 1.25,
                "profile_max_entries": 64,
                "profile_max_samples": 16,
                "workspace_lifecycle": lifecycle,
                "storage_reservation": {
                    "reservation_id": "fixture-storage",
                    "owner": "fixture-owner",
                    "execution_identity": "fixture-execution",
                },
                "storage_reservation_root": str(tmp_path / "storage"),
            },
            "write_latest": False,
        }
    )

    assert result["ok"] is False
    assert "startup_lease_release_failed" in result["denied_reasons"]
    assert "storage_reservation_release_failed" in result["denied_reasons"]
    assert result["managed_workspace_cleanup"]["ok"] is True
    cleanup = result["planning"]["pre_admission_dag"]["handoff_validation"]["cleanup"]
    assert cleanup["memory_lease"]["error"] == "lease busy"
    assert cleanup["storage_reservation"]["error"] == "storage_reservation_release_error"
    lifecycle_record = json.loads(
        next((lifecycle_root / "workspaces").glob("*.json")).read_text(encoding="utf-8")
    )
    assert lifecycle_record["state"] == "sealed"
    assert lifecycle_record["lease"] is None
    assert lifecycle_record["disposition"]["decision"] == "UNKNOWN"


def test_resource_launch_bounds_repeated_expired_attestation_refreshes(
    abyss_machine_module,
    monkeypatch,
    tmp_path,
):
    """Repeatedly stale plans must end in a typed denial, not an unbounded loop."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    policy = abyss_machine_module.resource_planning.default_policy(version="test")
    policy["startup_admission"]["launch_attestation_max_age_sec"] = 1.0
    monkeypatch.setattr(abyss_machine_module, "resource_policy_document", lambda: policy)
    target = tmp_path / "target"

    class AdvancingClock:
        now = 0.0
        expire = False

        def monotonic(self):
            if self.expire:
                self.now += 2.0
            return self.now

        def __getattr__(self, name):
            return getattr(time, name)

    clock = AdvancingClock()
    monkeypatch.setattr(abyss_machine_module, "time", clock)
    monkeypatch.setattr(
        abyss_machine_module,
        "storage_write_preflight",
        lambda **_kwargs: {
            "ok": True,
            "schema": "fixture_storage_preflight_v1",
            "decision": "allow",
        },
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "storage_path_protection",
        lambda _path: {"decision": "allow_candidate", "class": "host_owned_allowed"},
    )
    plan_calls = 0

    def fake_plan(**_kwargs):
        nonlocal plan_calls
        plan_calls += 1
        clock.expire = True
        return {
            "ok": True,
            "decision": "allow",
            "blocked_reasons": [],
            "denied_reasons": [],
            "request": {"normalized_class": "medium", "normalized_kind": "benchmark"},
            "inputs": {
                "startup_demand": {
                    "requested": {
                        "demand_mib": 0.0,
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

    monkeypatch.setattr(abyss_machine_module, "resource_plan", fake_plan)
    monkeypatch.setattr(
        abyss_machine_module,
        "resource_systemd_command",
        lambda *_args, **_kwargs: pytest.fail(
            "freshness budget must deny before command preparation"
        ),
    )
    result = abyss_machine_module.resource_launch(
        ["/usr/bin/true"],
        workload_class="medium",
        kind="benchmark",
        bytes_required=1024,
        target=str(target),
        sample_thermal=False,
        memory_demand_mib=0,
        demand_owner="fixture-owner",
        startup_wait_sec=0,
        write_latest=False,
    )

    assert result["ok"] is False
    assert "launch_attestation_refresh_exhausted" in result["denied_reasons"]
    assert 1 <= plan_calls <= 4
    assert result["planning"]["pre_admission_dag"]["refresh_count"] == 4
    assert result["planning"]["pre_admission_dag"]["refresh_budget"] == {
        "max_retries_after_initial": 3,
        "retries_used": 3,
        "exhausted": True,
    }
    assert result["execution"] is None

from __future__ import annotations

import pytest


pytestmark = [pytest.mark.quick, pytest.mark.contract]


def _psi(cpu_some: float = 0.0, memory_some: float = 0.0, memory_full: float = 0.0, io_some: float = 0.0, io_full: float = 0.0) -> dict:
    return {
        "cpu": {"exists": True, "some": {"avg10": cpu_some}, "full": {"avg10": 0.0}},
        "memory": {"exists": True, "some": {"avg10": memory_some}, "full": {"avg10": memory_full}},
        "io": {"exists": True, "some": {"avg10": io_some}, "full": {"avg10": io_full}},
    }


def test_heartbeat_pressure_context_high_swap_without_psi_stall_does_not_block(abyss_machine_module) -> None:
    memory_pressure = {
        "ok": True,
        "class": "green",
        "reasons": ["no_active_memory_pressure_observed"],
        "generated_at": "2026-05-19T10:00:00+00:00",
        "summary": {
            "class": "green",
            "mem_available_mib": 8192.0,
            "mem_available_percent": 32.0,
            "swap_used_mib": 12288.0,
            "swap_used_percent": 75.0,
            "zram_data_mib": 12288.0,
            "zram_resident_mib": 4096.0,
            "zram_logical_to_memory_ratio": 3.0,
        },
        "status": {
            "swap": {"summary": {"free_mib": 4096.0}},
            "swap_reserve": {"state": "within_target", "free_mib": 4096.0, "target_free_mib": 2048.0, "shortfall_mib": 0.0},
        },
        "processes": {"top": {"cgroup_memory": [], "cgroup_swap": []}},
        "source": {
            "kind": "live_readonly_memory_status",
            "primary_path": "/proc/meminfo",
            "process_attribution": "not_collected",
        },
    }

    result = abyss_machine_module.heartbeat_pressure_context_from(
        memory_pressure=memory_pressure,
        memory_plan={"generated_at": "2026-05-19T10:00:00+00:00"},
        resource_orchestrator={"summary": {"status": "ok"}, "inputs": {"game_guard": {"active": False}}},
        game_guard={"active": False, "generated_at": "2026-05-19T10:00:00+00:00"},
        psi=_psi(),
        generated_at="2026-05-19T10:01:00+00:00",
    )

    assert result["route"] == "allow"
    assert result["route"] != "block"
    assert result["memory"]["occupied_swap_without_stall"] is True
    assert result["attribution"]["available"] is False
    assert result["attribution"]["unavailable_reason"] == "not_collected"
    assert result["sources"]["memory_pressure"]["path"] == "/proc/meminfo"
    assert result["classification_evidence"]["memory_class_source"] == "live_readonly_memory_status"
    assert result["classification_evidence"]["psi_citation"]


def test_heartbeat_live_memory_pressure_projects_status_without_process_attribution(abyss_machine_module) -> None:
    status = {
        "schema": "abyss_machine_memory_status_v1",
        "generated_at": "2026-07-12T20:00:00+00:00",
        "ok": True,
        "class": "green",
        "reasons": ["no_active_memory_pressure_observed"],
        "meminfo": {
            "summary": {
                "mem_available_mib": 12288.0,
                "mem_available_percent": 39.0,
                "swap_used_mib": 9600.0,
                "swap_used_percent": 48.0,
            }
        },
        "psi": {"some": {"avg10": 0.0}, "full": {"avg10": 0.0}},
        "swap": {"summary": {"free_mib": 10080.0}},
        "swap_reserve": {"state": "within_target", "free_mib": 10080.0, "target_free_mib": 2048.0, "shortfall_mib": 0.0},
        "zram": {
            "summary": {
                "data_mib": 9360.0,
                "total_memory_mib": 4190.0,
                "logical_to_memory_ratio": 2.234,
            }
        },
        "zswap": {"enabled": False},
        "oomd": {"policy": "observe_only"},
    }

    result = abyss_machine_module.heartbeat_live_memory_pressure_from_status(status)

    assert result["schema"] == "abyss_machine_heartbeat_live_memory_pressure_v1"
    assert result["generated_at"] == status["generated_at"]
    assert result["class"] == "green"
    assert result["summary"]["mem_available_mib"] == 12288.0
    assert result["summary"]["swap_used_mib"] == 9600.0
    assert result["summary"]["zram_resident_mib"] == 4190.0
    assert result["status"]["swap"] is status["swap"]
    assert result["status"]["swap_reserve"] is status["swap_reserve"]
    assert result["processes"]["attribution_available"] is False
    assert result["processes"]["top"] == {}
    assert result["source"] == {
        "kind": "live_readonly_memory_status",
        "primary_path": "/proc/meminfo",
        "paths": [
            "/proc/meminfo",
            "/proc/pressure/memory",
            "/proc/swaps",
            "/sys/block/zram*",
        ],
        "process_attribution": "not_collected",
        "writes_memory_state": False,
    }


def test_heartbeat_live_memory_inputs_do_not_scan_processes_or_write_memory_state(monkeypatch, abyss_machine_module) -> None:
    machine = abyss_machine_module
    calls: dict[str, object] = {}
    status = {
        "generated_at": "2026-07-12T20:00:00+00:00",
        "ok": True,
        "class": "green",
        "reasons": [],
        "meminfo": {"summary": {}},
        "psi": {},
        "swap": {"summary": {}},
        "zram": {"summary": {}},
    }

    def fake_status(*, write_latest=False):
        calls["status_write_latest"] = write_latest
        return status

    def fake_pressure(*args, **kwargs):
        raise AssertionError("heartbeat must not run the process-attributing memory pressure scan")

    def fake_plan(**kwargs):
        calls["plan_kwargs"] = kwargs
        return {
            "schema": "abyss_machine_memory_plan_v1",
            "generated_at": "2026-07-12T20:00:01+00:00",
            "ok": True,
            "class": kwargs["pressure_input"]["class"],
        }

    monkeypatch.setattr(machine, "memory_status", fake_status)
    monkeypatch.setattr(machine, "memory_pressure", fake_pressure)
    monkeypatch.setattr(machine, "memory_plan", fake_plan)

    pressure, plan = machine.heartbeat_live_memory_inputs({"active": False})

    assert calls["status_write_latest"] is False
    assert calls["plan_kwargs"]["write_latest"] is False
    assert calls["plan_kwargs"]["pressure_input"] is pressure
    assert calls["plan_kwargs"]["game_guard_input"] == {"active": False}
    assert plan["source"]["kind"] == "derived_live_readonly_memory_plan"
    assert plan["source"]["writes_memory_state"] is False


def test_heartbeat_pressure_context_io_full_pressure_defers_new_work(abyss_machine_module) -> None:
    memory_pressure = {
        "ok": True,
        "class": "green",
        "reasons": ["no_memory_pressure_observed"],
        "summary": {"class": "green", "swap_used_percent": 1.0},
        "status": {"swap": {"summary": {"free_mib": 12000.0}}},
        "processes": {"top": {"cgroup_memory": [], "cgroup_swap": []}},
    }

    result = abyss_machine_module.heartbeat_pressure_context_from(
        memory_pressure=memory_pressure,
        memory_plan={},
        resource_orchestrator={"summary": {"status": "ok"}, "inputs": {"game_guard": {"active": True}}},
        game_guard={"active": True},
        psi=_psi(io_full=3.0),
        generated_at="2026-05-19T10:01:00+00:00",
    )

    assert result["status"] == "hot"
    assert result["route"] == "defer"
    assert any("io_psi_full_avg10_hot" in reason for reason in result["reasons"])


def test_heartbeat_capture_health_retention_route_is_owner_gated(abyss_machine_module) -> None:
    capture_status = {
        "ok": True,
        "latest": {
            "generated_at": "2026-05-19T10:00:00+00:00",
            "summary": {"facts": 12, "facts_ok": 12, "facts_missing_or_failed": 0, "skipped": 1},
        },
        "browser_content_latest": {
            "generated_at": "2026-05-19T10:00:00+00:00",
            "skipped": True,
            "skip_reason": "login_sensitive",
            "summary": {
                "captures": 0,
                "errors": 0,
                "skipped_text": 2,
                "text_records": 0,
                "accessibility_ok": True,
                "accessibility_skipped": True,
                "bidi_attempted": False,
                "bidi_ok": False,
            },
        },
        "storage": {
            "screenshots_count": 10,
            "screenshots_bytes": 100 * 1024 * 1024,
            "browser_content_jsonl_files": 2,
            "browser_content_bytes": 4 * 1024 * 1024,
            "private_root_bytes": 128 * 1024 * 1024,
        },
    }
    retention_plan = {
        "generated_at": "2026-05-19T10:00:00+00:00",
        "ok": True,
        "policy": {"facts_delete_behavior": "explicit forget only", "default_apply": "dry-run"},
        "summary": {"files": 30, "bytes": 512 * 1024 * 1024, "candidates": 2, "candidate_bytes": 64 * 1024 * 1024, "route_errors": 0},
    }

    result = abyss_machine_module.heartbeat_capture_health_from(
        capture_status=capture_status,
        retention_plan=retention_plan,
        privacy_status={"global_pause": False, "private_mode": False},
        generated_at="2026-05-19T10:01:00+00:00",
    )

    route = result["owner_gated_routes"][0]
    assert result["status"] == "attention"
    assert result["privacy"]["sensitive_skips"] == 3
    assert route["active"] is True
    assert route["requires_owner_gate"] is True
    assert route["automatic"] is False
    assert route["executes_from_heartbeat"] is False
    assert result["policy"]["does_not_delete_or_forget"] is True


def test_retention_dry_run_response_profile_is_non_mutating_and_owner_required(abyss_machine_module) -> None:
    profile = abyss_machine_module.response_command_profile("abyss-machine nervous retention-apply --dry-run --json")

    assert profile["kind"] == "owner_gated_retention_dry_run"
    assert profile["scope"] == "privacy_retention"
    assert profile["mutating_if_run"] is False
    assert profile["requires_operator"] is True

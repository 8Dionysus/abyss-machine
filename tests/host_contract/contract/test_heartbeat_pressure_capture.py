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
        "class": "warm",
        "reasons": ["swap_used_percent=75>critical_but_zram_only_relief_to_warm"],
        "generated_at": "2026-05-19T10:00:00+00:00",
        "summary": {
            "class": "warm",
            "mem_available_mib": 8192.0,
            "mem_available_percent": 32.0,
            "swap_used_mib": 12288.0,
            "swap_used_percent": 75.0,
            "zram_data_mib": 12288.0,
            "zram_resident_mib": 4096.0,
            "zram_logical_to_memory_ratio": 3.0,
        },
        "status": {"swap": {"summary": {"free_mib": 4096.0}}},
        "processes": {"top": {"cgroup_memory": [], "cgroup_swap": []}},
    }

    result = abyss_machine_module.heartbeat_pressure_context_from(
        memory_pressure=memory_pressure,
        memory_plan={"generated_at": "2026-05-19T10:00:00+00:00"},
        resource_orchestrator={"summary": {"status": "ok"}, "inputs": {"game_guard": {"active": False}}},
        game_guard={"active": False, "generated_at": "2026-05-19T10:00:00+00:00"},
        psi=_psi(),
        generated_at="2026-05-19T10:01:00+00:00",
    )

    assert result["route"] == "soften"
    assert result["route"] != "block"
    assert result["memory"]["occupied_swap_without_stall"] is True
    assert result["classification_evidence"]["psi_citation"]


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

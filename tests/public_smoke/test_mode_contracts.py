from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import mode_contracts


def _refs(root: str = "/var/lib/abyss-machine/mode") -> dict[str, str]:
    return {
        "root": root,
        "agent_entrypoint": f"{root}/AGENTS.md",
        "index": f"{root}/index.json",
        "latest": f"{root}/latest.json",
        "state": "/var/lib/abyss-machine/mode-state.json",
        "policy": "/etc/abyss-machine/mode-policy.json",
        "plan_root": f"{root}/plans",
        "plan_latest": f"{root}/plans/latest.json",
        "validate_root": f"{root}/validate",
        "validate_latest": f"{root}/validate/latest.json",
        "cooling_service": "abyss-power-profile-auto.service",
        "cooling_timer": "abyss-power-profile-auto.timer",
    }


def test_mode_policy_paths_and_definitions_are_module_owned() -> None:
    policy = mode_contracts.policy_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        path="/etc/abyss-machine/mode-policy.json",
        loaded={"profiles": {"balanced": {"max_unattended_class_ac": "light"}}},
        load_error=None,
    )
    paths = mode_contracts.paths_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        refs=_refs(),
    )
    definitions = mode_contracts.definitions(policy)
    balanced = next(item for item in definitions if item["name"] == "balanced")

    assert policy["schema"] == "abyss_machine_mode_policy_v1"
    assert policy["exists"] is True
    assert policy["profiles"]["balanced"]["max_unattended_class_ac"] == "light"
    assert policy["profiles"]["balanced"]["power_profile"] == "balanced"
    assert paths["schema"] == "abyss_machine_mode_paths_v1"
    assert paths["commands"]["set_ai"] == "abyss-machine mode set ai --json"
    assert paths["policy_contract"]["host_mutation"] is False
    assert balanced["power_profile"] == "balanced"
    assert balanced["ai_overlay"] is False


def test_mode_target_thermal_and_launch_contracts_are_module_owned() -> None:
    policy = mode_contracts.default_policy(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
    )
    effective, power_profile, degraded = mode_contracts.target_profile("performance", False, policy)
    hot = mode_contracts.thermal_class_from_summary(
        {"temperature_c_max": 107.0},
        thresholds={"hot_temperature_c": 106.0, "critical_temperature_c": 109.0},
    )
    max_class = mode_contracts.max_unattended_class(
        profile=mode_contracts.profile_policy(policy, "performance"),
        thermal_class=hot,
        effective_mode="performance",
        ac_online=True,
        policy=policy,
    )

    assert (effective, power_profile, degraded) == ("saver", "power-saver", "battery")
    assert hot == "hot"
    assert max_class == "medium"
    assert mode_contracts.workload_level(max_class) < mode_contracts.workload_level("heavy")


def test_mode_plan_status_and_external_guard_contracts_are_module_owned() -> None:
    policy = mode_contracts.default_policy(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
    )
    guard = mode_contracts.external_power_profile_guard(
        current_profile="performance",
        target_profile="balanced",
        gamemode={"available": True, "global_active": True},
        recent={"active": False},
        game_guard={"checked": True, "active": True},
        game_guard_active=True,
    )
    plan = mode_contracts.plan_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        selected="balanced",
        effective="balanced",
        state_file="/var/lib/abyss-machine/mode-state.json",
        policy_path="/etc/abyss-machine/mode-policy.json",
        profile=mode_contracts.profile_policy(policy, "balanced"),
        target_profile_name="balanced",
        current_profile="performance",
        current_mode="performance",
        external_profile_guard=guard,
        cooling={"recommended_profile": "balanced", "reasons": ["fixture"], "current": {"fan_mode": 2}},
        cooling_normalized="balanced",
        cooling_target={"platform_profile": "balanced", "fan_mode": 2},
        temperature={"temperature_c_max": 88.0},
        thermal_class="warm",
        battery={"ac_online": True, "capacity_percent": 80},
        cpu_routed_heavy={"allowed": True, "unattended_allowed": True, "requires_routing": True, "route": {"cpuset": "0-3"}},
        degraded_reason=None,
        storage_pressure_latest={"path": "/var/lib/abyss-machine/storage/pressure/latest.json", "exists": False, "load_error": "missing", "summary": None},
        memory_plan_latest={"path": "/var/lib/abyss-machine/memory/plan/latest.json", "exists": True, "load_error": None, "summary": {"class": "green"}},
        process_latest={"path": "/var/lib/abyss-machine/processes/latest.json", "exists": True, "load_error": None, "summary": {"processes": 3}},
        policy=policy,
    )
    status = mode_contracts.status_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        refs=_refs(),
        state={"last_non_ai_mode": "balanced", "forced_saver_on_battery": False},
        selected="balanced",
        effective="balanced",
        target_profile_name="balanced",
        current_profile="performance",
        external_profile_guard=guard,
        degraded_reason=None,
        battery={"ac_online": True},
        sensors={"temperature_c_max": 88.0},
        ai_ready=False,
        ai={"dev_dri_present": False, "dev_accel_present": False, "openvino_venv_exists": False},
        plan=plan,
    )

    assert guard["preserve_external_boost"] is True
    assert plan["schema"] == "abyss_machine_mode_plan_v1"
    assert "power_profile_external_boost:performance->balanced" in plan["reasons"]
    assert "storage_pressure_unavailable" in plan["reasons"]
    assert plan["launch_policy"]["max_unattended_class"] == "medium"
    assert plan["launch_policy"]["can_start_heavy_unattended"] is False
    assert status["schema"] == "abyss_machine_mode_status_v1"
    assert status["power_profile_external_boost"] is True
    assert status["degraded"] is False


def test_mode_validate_document_is_module_owned_with_cli_adapter(monkeypatch) -> None:
    from abyss_machine import cli

    generated_at = "2026-06-26T14:40:00Z"
    checks = [
        {"level": "ok", "key": "mode_plan", "message": "mode plan computes", "data": {"schema": "abyss_machine_mode_plan_v1"}},
        {"level": "warn", "key": "storage_pressure_input", "message": "storage pressure latest is unavailable to mode plan", "data": {"exists": False}},
    ]
    paths = {"schema": "abyss_machine_mode_paths_v1", "commands": {"validate": "abyss-machine mode validate --json"}}
    plan = {
        "selected_mode": "ai",
        "effective_mode": "ai",
        "hardware_targets": {"power_profile": "performance"},
        "launch_policy": {"max_unattended_class": "heavy"},
        "reasons": ["storage_pressure_unavailable"],
    }
    expected = mode_contracts.mode_validate_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at=generated_at,
        checks=checks,
        strict=True,
        paths=paths,
        plan=plan,
        thermal_class="warm",
    )
    monkeypatch.setattr(cli, "now_iso", lambda: generated_at)

    assert cli.mode_validate_document_from_checks(
        checks,
        strict=True,
        paths=paths,
        plan=plan,
        thermal_class="warm",
    ) == expected
    assert expected["schema"] == "abyss_machine_mode_validate_v1"
    assert expected["scope"] == "Abyss Machine work-mode contract"
    assert expected["ok"] is False
    assert expected["summary"] == {"status": "warn", "fails": 0, "warnings": 1, "checks": 2}
    assert expected["plan"]["selected_mode"] == "ai"
    assert expected["plan"]["thermal_class"] == "warm"
    assert "does not run heavy workloads" in expected["non_claims"][0]


def test_mode_paths_cli_uses_public_contract_shape_without_live_apply() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC_ROOT)
    result = subprocess.run(
        [sys.executable, "-m", "abyss_machine.cli", "mode", "paths", "--json"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema"] == "abyss_machine_mode_paths_v1"
    assert payload["commands"]["plan"] == "abyss-machine mode plan --json"
    assert payload["policy_contract"]["host_mutation"] is False

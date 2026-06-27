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

from abyss_machine import cooling_contracts


def _refs(root: str = "/var/lib/abyss-machine/cooling") -> dict[str, str]:
    return {
        "root": root,
        "agent_entrypoint": f"{root}/AGENTS.md",
        "index": f"{root}/index.json",
        "config": "/etc/abyss-machine/cooling/config.json",
        "latest": f"{root}/latest.json",
        "action_root": f"{root}/actions",
        "thermal_audit_root": f"{root}/thermal-audit",
        "thermal_audit_latest": f"{root}/thermal-audit/latest.json",
        "fan_validate_root": f"{root}/fan-validate",
        "fan_validate_latest": f"{root}/fan-validate/latest.json",
        "fan_series_root": f"{root}/fan-series",
        "fan_series_latest": f"{root}/fan-series/latest.json",
        "rapl_smoothing_root": f"{root}/rapl-smoothing",
        "rapl_smoothing_latest": f"{root}/rapl-smoothing/latest.json",
        "rapl_smoothing_state": f"{root}/rapl-smoothing/state.json",
        "service": "abyss-power-profile-auto.service",
        "timer": "abyss-power-profile-auto.timer",
    }


def _daily(root: str = "/var/lib/abyss-machine/cooling") -> dict[str, str]:
    return {
        "actions_today": f"{root}/actions/2026/06/2026-06-25.jsonl",
        "thermal_audit_today": f"{root}/thermal-audit/2026/06/2026-06-25.jsonl",
        "fan_validate_today": f"{root}/fan-validate/2026/06/2026-06-25.jsonl",
        "fan_series_today": f"{root}/fan-series/2026/06/2026-06-25.jsonl",
        "rapl_smoothing_today": f"{root}/rapl-smoothing/2026/06/2026-06-25.jsonl",
    }


def test_cooling_config_and_paths_are_module_owned() -> None:
    config = cooling_contracts.config_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        loaded={"profiles": {"balanced": {"fan_mode": 2}}, "auto": {"hot_temperature_c": 105.0}},
        load_error=None,
    )
    paths = cooling_contracts.paths_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        refs=_refs(),
        daily_paths=_daily(),
    )

    assert config["schema"] == "abyss_machine_cooling_config_v1"
    assert config["profiles"]["balanced"]["fan_mode"] == 2
    assert config["profiles"]["balanced"]["platform_profile"] == "balanced"
    assert config["auto"]["hot_temperature_c"] == 105.0
    assert paths["schema"] == "abyss_machine_cooling_paths_v1"
    assert paths["commands"]["apply_auto"] == "abyss-machine cooling apply --profile auto --json"
    assert paths["policy_contract"]["host_mutation"] is False


def test_cooling_recommendation_and_profile_targets_are_module_owned() -> None:
    config = cooling_contracts.default_config("abyss_machine", "0.8.test")
    status = {
        "temperature": {
            "class": "warm",
            "summary": {"temperature_c_max": 101.0, "package_temperature_c_max": 99.0},
            "episode": {"class": "watch"},
        },
        "fan": {"fan_mode": 4},
        "power": {"platform_profile": {"current": "performance"}, "powerprofilesctl": "performance"},
    }
    selected = cooling_contracts.selected_mode_for_recommendation(
        selected_mode="ai",
        power_profile_name="performance",
        ac_online=True,
    )
    recommendation = cooling_contracts.recommendation_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        status_data=status,
        config=config,
        selected_mode=selected,
        recent_emergency={"active": False},
        config_path="/etc/abyss-machine/cooling/config.json",
    )
    normalized, target = cooling_contracts.profile_targets(
        profile="auto",
        config=config,
        recommendation=recommendation,
    )

    assert selected == "performance"
    assert recommendation["schema"] == "abyss_machine_cooling_recommendation_v1"
    assert recommendation["recommended_profile"] == "emergency"
    assert "hold_emergency_until_below_100.0C" in recommendation["reasons"]
    assert normalized == "emergency"
    assert target["fan_mode"] == 4


def test_cooling_rapl_state_status_and_apply_document_shapes_are_module_owned() -> None:
    state = cooling_contracts.state_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        raw_state={"active": True, "engage_count": "2", "last_action": "hold_cap"},
    )
    status = cooling_contracts.rapl_smoothing_status_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        config={"enabled": True, "apply_modes": ["performance"], "normal_pl1_uw": 35000000, "cap_pl1_uw": 28000000},
        state=state,
        rapl_mmio={"available": True, "pl1_uw": 28000000},
        package_throttle_count=7,
        refs={"root": "/var/lib/abyss-machine/cooling/rapl-smoothing", "latest": "/tmp/latest.json", "state": "/tmp/state.json"},
    )
    apply_doc = cooling_contracts.apply_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        requested_profile="performance",
        applied_profile="performance",
        updated_by="test",
        permission_required=True,
        actions=[{"action": "set_fan_mode", "ok": False, "error": "root permission required"}],
        recommendation=None,
        status_before={"temperature": {"summary": {"temperature_c_max": 88.0}}, "fan": {}, "power": {}},
        status_after={"temperature": {"temperature_c_max": 88.0}, "fan": {}, "platform_profile": {}},
        paths={"schema": "abyss_machine_cooling_paths_v1"},
    )

    assert state["active"] is True
    assert state["engage_count"] == 2
    assert status["schema"] == "abyss_machine_cooling_rapl_smoothing_status_v1"
    assert status["policy"]["temporary_only"] is True
    assert apply_doc["schema"] == "abyss_machine_cooling_apply_v1"
    assert apply_doc["ok"] is False
    assert apply_doc["permission_required"] is True


def test_cooling_fan_series_contracts_are_module_owned() -> None:
    assert cooling_contracts.parse_levels("25, 50,,") == [25, 50]
    normalized = cooling_contracts.normalize_fan_series_inputs(
        level=50,
        repeats=99,
        seconds=0.1,
        interval=99.0,
        cooldown=-1,
        state_label="hot label / unsafe",
    )
    decision = cooling_contracts.fan_series_decision(
        compact_results=[
            {"ok": True, "action": {"kernel_ok": True, "verdict": "write_path_ok_possible_cooling_effect", "temperature_c_max_delta": -3.0}},
            {"ok": True, "action": {"kernel_ok": True, "verdict": "write_path_ok_possible_cooling_effect", "temperature_c_max_delta": -2.5}},
            {"ok": True, "action": {"kernel_ok": True, "verdict": "write_path_ok_effect_unproven", "temperature_c_max_delta": -0.5}},
        ],
        repeats=3,
        permission_required=False,
    )

    assert normalized["repeats"] == 10
    assert normalized["seconds"] == 1.0
    assert normalized["interval"] == 10.0
    assert normalized["cooldown"] == 0.0
    assert normalized["state_label"] == "hot_label_unsafe"
    assert decision["summary"]["possible_effect_count"] == 2
    assert decision["decision"]["automation_candidate"] is True
    assert decision["decision"]["automation_allowed"] is False


def test_cooling_paths_cli_uses_public_contract_shape_without_live_apply() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC_ROOT)
    result = subprocess.run(
        [sys.executable, "-m", "abyss_machine.cli", "cooling", "paths", "--json"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema"] == "abyss_machine_cooling_paths_v1"
    assert payload["commands"]["recommend"] == "abyss-machine cooling recommend --json"
    assert payload["policy_contract"]["host_mutation"] is False

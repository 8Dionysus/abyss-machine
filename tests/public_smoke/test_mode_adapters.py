from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import mode_adapters


def test_mode_state_load_and_save_use_fake_state_file_and_writer(tmp_path: Path) -> None:
    state_file = tmp_path / "mode-state.json"
    state_file.write_text(
        json.dumps(
            {
                "selected_mode": "ai",
                "last_non_ai_mode": "performance",
                "forced_saver_on_battery": True,
            }
        ),
        encoding="utf-8",
    )
    state = mode_adapters.load_state(
        state_file,
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-29T10:00:00Z",
        current_profile="balanced",
    )
    writes: list[tuple[Path, dict[str, Any], int]] = []

    mode_adapters.save_state(
        state_file,
        state,
        updated_by="set:ai",
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-29T10:01:00Z",
        write_json_document=lambda path, data, mode: writes.append((path, data, mode)),
        mode=0o660,
    )

    assert state["selected_mode"] == "ai"
    assert state["last_non_ai_mode"] == "performance"
    assert writes == [
        (
            state_file,
            {
                "schema": "abyss_machine_mode_state_v1",
                "version": "0.8.test",
                "selected_mode": "ai",
                "last_non_ai_mode": "performance",
                "forced_saver_on_battery": True,
                "updated_at": "2026-06-29T10:01:00Z",
                "updated_by": "set:ai",
            },
            0o660,
        )
    ]


def test_power_profile_get_and_set_use_fake_runner_with_cache() -> None:
    calls: list[tuple[list[str], float]] = []

    def runner(command: Sequence[str], timeout: float) -> dict[str, Any]:
        calls.append((list(command), timeout))
        if list(command) == ["powerprofilesctl", "get"]:
            return {"ok": True, "stdout": "balanced\n", "stderr": "", "returncode": 0}
        if list(command) == ["powerprofilesctl", "set", "performance"]:
            return {"ok": True, "stdout": "", "stderr": "", "returncode": 0}
        raise AssertionError(command)

    cache: dict[str, Any] = {}
    current = mode_adapters.power_profile(
        command_exists=lambda name: name == "powerprofilesctl",
        runner=runner,
        cache=cache,
    )
    result = mode_adapters.set_power_profile(
        "performance",
        command_exists=lambda name: name == "powerprofilesctl",
        runner=runner,
        cache=cache,
    )

    assert current == "balanced"
    assert result["ok"] is True
    assert result["changed"] is True
    assert result["current"] == "balanced"
    assert cache == {"ready": True, "value": "performance"}
    assert calls == [
        (["powerprofilesctl", "get"], 2.0),
        (["powerprofilesctl", "set", "performance"], 5.0),
    ]


def test_set_power_profile_noops_when_target_is_cached_current() -> None:
    calls: list[list[str]] = []
    result = mode_adapters.set_power_profile(
        "balanced",
        command_exists=lambda name: name == "powerprofilesctl",
        runner=lambda command, timeout: calls.append(list(command)) or {"ok": True, "stdout": "", "stderr": "", "returncode": 0},
        cache={"ready": True, "value": "balanced"},
    )

    assert result == {"ok": True, "changed": False, "current": "balanced", "target": "balanced"}
    assert calls == []


def test_gamemode_recent_power_profile_activity_reads_journal_through_fake_runner() -> None:
    calls: list[tuple[list[str], float]] = []

    def runner(command: Sequence[str], timeout: float) -> dict[str, Any]:
        calls.append((list(command), timeout))
        return {
            "ok": True,
            "stdout": "noise\nEntering Game Mode\nExecuting script [powerprofilesctl set performance]\n",
            "stderr": "",
            "returncode": 0,
        }

    recent = mode_adapters.gamemode_recent_power_profile_activity(
        45,
        command_exists=lambda name: name == "journalctl",
        runner=runner,
    )

    assert recent["active"] is True
    assert recent["matched"] == ["Entering Game Mode", "Executing script [powerprofilesctl set performance]"]
    assert calls == [
        (
            ["journalctl", "--since", "45 seconds ago", "--no-pager", "-o", "cat", "_COMM=gamemoded"],
            2.0,
        )
    ]


def test_external_power_profile_guard_uses_gamemode_and_game_guard_ports() -> None:
    guard = mode_adapters.external_power_profile_guard(
        "performance",
        "balanced",
        command_exists=lambda name: name == "journalctl",
        runner=lambda command, timeout: {"ok": True, "stdout": "", "stderr": "", "returncode": 0},
        gamemode_status=lambda: {
            "available": True,
            "global_active": False,
            "global_status_text": "inactive",
        },
        game_guard=lambda: {
            "ok": True,
            "active": True,
            "summary": {"gamemode_global_active": False},
        },
    )

    assert guard["active"] is True
    assert guard["reason"] == "active_game_guard"
    assert guard["preserve_external_boost"] is True
    assert guard["game_guard"]["checked"] is True
    assert guard["gamemode"]["status_text"] == "inactive"
    assert "transient GameMode profile flips" in guard["policy"]


def test_collect_plan_inputs_routes_live_reads_through_fake_ports(tmp_path: Path) -> None:
    storage_path = tmp_path / "storage" / "latest.json"
    memory_path = tmp_path / "memory" / "latest.json"
    process_path = tmp_path / "processes" / "latest.json"
    calls: list[Any] = []
    latest_by_path: dict[Path, tuple[Any, Any]] = {
        storage_path: ({"summary": {"class": "green", "free_gib": 64}}, None),
        memory_path: (
            {
                "class": "yellow",
                "reasons": ["fixture_pressure"],
                "recommended_new_work": {"heavy": "defer"},
            },
            None,
        ),
        process_path: ({"summary": {"processes": 17}}, None),
    }

    def target_profile(selected: str, ac_online: bool) -> tuple[str, str, str | None]:
        calls.append(("target_profile", selected, ac_online))
        return ("ai", "performance", None)

    def cpu_routed_heavy_policy(*args: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append(("cpu_routed_heavy_policy", args, kwargs))
        return {
            "allowed": True,
            "unattended_allowed": True,
            "route": {"cpuset": "0-3"},
            "trend": kwargs["trend"],
        }

    inputs = mode_adapters.collect_plan_inputs(
        state={"selected_mode": "ai"},
        battery_summary=lambda: {"ac_online": True, "capacity_percent": 82},
        target_profile=target_profile,
        profile_policy=lambda effective: {"name": effective, "cooling_profile": "balanced"},
        power_profile=lambda: "balanced",
        current_mode_from_power_profile=lambda profile: "balanced" if profile == "balanced" else None,
        external_profile_guard=lambda current, target: {"active": False, "current": current, "target": target},
        cooling_recommend=lambda: {
            "recommended_profile": "performance",
            "temperature": {
                "temperature_c_max": 91.2,
                "cpu_hotspot": {"class": "warm", "trend": "rising"},
            },
        },
        cooling_profile_targets=lambda profile: (profile, {"platform_profile": profile, "fan_mode": 4}, None),
        thermal_class_from_summary=lambda summary: calls.append(("thermal_class", summary)) or "warm",
        cpu_thermal_map=lambda write_latest: calls.append(("cpu_thermal_map", write_latest)) or {"summary": "cpu"},
        cpu_routed_heavy_policy=cpu_routed_heavy_policy,
        load_json_document=lambda path: latest_by_path[path],
        storage_pressure_path=storage_path,
        memory_plan_path=memory_path,
        process_latest_path=process_path,
        path_exists=lambda path: path != process_path,
        write_latest=False,
    )

    assert inputs["selected"] == "ai"
    assert inputs["effective"] == "ai"
    assert inputs["target_profile_name"] == "performance"
    assert inputs["profile"] == {"name": "ai", "cooling_profile": "balanced"}
    assert inputs["current_mode"] == "balanced"
    assert inputs["external_profile_guard"] == {"active": False, "current": "balanced", "target": "performance"}
    assert inputs["cooling_normalized"] == "performance"
    assert inputs["cooling_target"] == {"platform_profile": "performance", "fan_mode": 4}
    assert inputs["thermal_class"] == "warm"
    assert inputs["cpu_routed_heavy"]["trend"] == "rising"
    assert inputs["storage_pressure_latest"] == {
        "path": str(storage_path),
        "exists": True,
        "load_error": None,
        "summary": {"class": "green", "free_gib": 64},
    }
    assert inputs["memory_plan_latest"] == {
        "path": str(memory_path),
        "exists": True,
        "load_error": None,
        "summary": {
            "class": "yellow",
            "reasons": ["fixture_pressure"],
            "recommended_new_work": {"heavy": "defer"},
        },
    }
    assert inputs["process_latest"] == {
        "path": str(process_path),
        "exists": False,
        "load_error": None,
        "summary": {"processes": 17},
    }
    assert ("target_profile", "ai", True) in calls
    assert ("cpu_thermal_map", False) in calls
    assert ("thermal_class", {"class": "warm", "temperature_c_max": 91.2}) in calls
    assert calls[-1][0] == "cpu_routed_heavy_policy"
    assert calls[-1][2] == {"capacity_percent": 82, "trend": "rising"}


def test_collect_status_inputs_routes_status_reads_through_fake_ports() -> None:
    calls: list[Any] = []
    plan = {"schema": "abyss_machine_mode_plan_v1", "fixture": True}

    inputs = mode_adapters.collect_status_inputs(
        state={"selected_mode": "performance"},
        battery_summary=lambda: {"ac_online": True},
        target_profile=lambda selected, ac_online: calls.append(("target_profile", selected, ac_online)) or ("performance", "performance", None),
        power_profile=lambda: calls.append("power_profile") or "performance",
        external_profile_guard=lambda current, target: calls.append(("guard", current, target)) or {"active": False},
        ai_devices=lambda: {
            "dev_dri_present": True,
            "dev_accel_present": True,
            "openvino_venv_exists": True,
        },
        sensors_summary=lambda: {"temperature_c_max": 72.5},
        mode_plan=lambda: calls.append("mode_plan") or plan,
    )

    assert inputs["selected"] == "performance"
    assert inputs["effective"] == "performance"
    assert inputs["target_profile_name"] == "performance"
    assert inputs["current_profile"] == "performance"
    assert inputs["external_profile_guard"] == {"active": False}
    assert inputs["ai_ready"] is True
    assert inputs["sensors"] == {"temperature_c_max": 72.5}
    assert inputs["plan"] is plan
    assert calls == [
        ("target_profile", "performance", True),
        "power_profile",
        ("guard", "performance", "performance"),
        "mode_plan",
    ]

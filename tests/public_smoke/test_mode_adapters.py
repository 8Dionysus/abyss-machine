from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

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

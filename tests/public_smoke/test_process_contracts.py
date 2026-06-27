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

from abyss_machine import process_contracts


def _refs(root: str = "/var/lib/abyss-machine/processes") -> dict[str, str]:
    return {
        "root": root,
        "agent_entrypoint": f"{root}/AGENTS.md",
        "index": f"{root}/index.json",
        "latest": f"{root}/latest.json",
        "snapshot_root": f"{root}/snapshots",
        "thermal_attribution_root": f"{root}/thermal-attribution",
        "thermal_attribution_latest": f"{root}/thermal-attribution/latest.json",
        "thermal_plan_root": f"{root}/thermal-plan",
        "thermal_plan_latest": f"{root}/thermal-plan/latest.json",
        "desktop_compositor_root": f"{root}/desktop-compositor",
        "desktop_compositor_latest": f"{root}/desktop-compositor/latest.json",
        "game_guard_root": f"{root}/game-guard",
        "game_guard_latest": f"{root}/game-guard/latest.json",
        "container_root": f"{root}/containers",
        "container_latest": f"{root}/containers/latest.json",
        "service": "abyss-process-snapshot.service",
        "timer": "abyss-process-snapshot.timer",
    }


def _daily(root: str = "/var/lib/abyss-machine/processes") -> dict[str, str]:
    return {
        "thermal_attribution_today": f"{root}/thermal-attribution/2026/06/2026-06-25.jsonl",
        "thermal_plan_today": f"{root}/thermal-plan/2026/06/2026-06-25.jsonl",
        "desktop_compositor_today": f"{root}/desktop-compositor/2026/06/2026-06-25.jsonl",
        "game_guard_today": f"{root}/game-guard/2026/06/2026-06-25.jsonl",
        "container_today": f"{root}/containers/2026/06/2026-06-25.jsonl",
    }


def test_process_paths_and_latest_read_shapes_are_module_owned() -> None:
    paths = process_contracts.paths_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        refs=_refs(),
        daily_paths=_daily(),
    )
    missing = process_contracts.latest_read_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        path="/var/lib/abyss-machine/processes/latest.json",
        latest=None,
        error="missing",
    )
    present = process_contracts.latest_summary_document(
        path="/var/lib/abyss-machine/processes/latest.json",
        latest={"generated_at": "now", "summary": {"processes": 2}},
        error=None,
    )

    assert paths["schema"] == "abyss_machine_process_paths_v1"
    assert paths["commands"]["game_guard"] == "abyss-machine processes game-guard --json"
    assert paths["policy_contract"]["mutates_existing_processes"] is False
    assert missing["schema"] == "abyss_machine_process_latest_read_v1"
    assert missing["ok"] is False
    assert present["summary"]["processes"] == 2


def test_process_role_and_workload_classification_are_module_owned() -> None:
    roots = ["/srv/games", "/home/agent/Games"]

    assert process_contracts.capability_role("/opt/llama-server --model x", "llama-server") == "persistent_model"
    assert process_contracts.capability_role("uvicorn app:api --port 5001", "uvicorn") == "persistent_ai_service"
    assert process_contracts.workload_hint("abyss-dictation-server", "python") == "abyss_machine"
    assert process_contracts.game_role("/srv/games/example/game.exe", "game.exe", "/srv/games/example", "/srv/games/example/game.exe", game_roots=roots) == "active_game"
    assert process_contracts.workload_hint("steam -no-cef-sandbox", "steam", "/home/agent/.steam", "/usr/bin/steam", game_roots=roots) == "game_platform"
    assert process_contracts.game_role(
        r"C:\windows\system32\explorer.exe /desktop",
        "explorer.exe",
        "/home/agent/.local/share/bottles/bottles/AdobeCC/drive_c/windows/system32",
        "/home/agent/.local/share/bottles/runners/wine/bin/wine-preloader",
        game_roots=roots,
    ) == "none"


def test_process_game_guard_document_is_module_owned() -> None:
    processes = [
        {"pid": 10, "comm": "steam", "cmdline": "steam", "cwd": "/home/agent/.steam", "exe": "/usr/bin/steam", "vmrss_kib": 10, "cpu_system_percent": 1.0},
        {"pid": 20, "comm": "game.exe", "cmdline": "/srv/games/example/game.exe", "cwd": "/srv/games/example", "exe": "/srv/games/example/game.exe", "vmrss_kib": 50, "cpu_system_percent": 9.0},
        {"pid": 30, "comm": "gamemoded", "cmdline": "gamemoded", "vmrss_kib": 5, "cpu_system_percent": 0.1},
    ]
    entries = process_contracts.game_entries(processes, game_roots=["/srv/games"])
    guard = process_contracts.game_guard_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        entries=entries,
        inaccessible=1,
        source="provided_process_list",
        gamemode={"available": True, "global_active": True},
        protected_roots=[{"path": "/srv/games", "exists": True, "operator_owned": True}],
        latest_path="/var/lib/abyss-machine/processes/game-guard/latest.json",
        daily_glob="/var/lib/abyss-machine/processes/game-guard/YYYY/MM/YYYY-MM-DD.jsonl",
    )

    assert guard["schema"] == "abyss_machine_process_game_guard_v1"
    assert guard["active"] is True
    assert guard["summary"]["active_game_processes"] == 1
    assert guard["summary"]["game_platform_processes"] == 1
    assert guard["summary"]["game_service_processes"] == 1
    assert guard["routing_policy"]["when_active"]["block_default_heavy_and_sustained_ai_launches"] is True
    assert guard["non_claims"]


def test_process_snapshot_document_is_module_owned() -> None:
    snapshot = process_contracts.snapshot_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        paths={"schema": "abyss_machine_process_paths_v1"},
        top=2,
        interval=0.5,
        system={"loadavg": [1.0, 2.0, 3.0], "memory": {"MemTotal": 1000}},
        inaccessible=1,
        processes=[
            {"pid": 1, "threads": 2, "vmrss_kib": 100, "io": {"read_bytes": 4, "write_bytes": 1}, "cpu_system_percent": 0.1, "workload_hint": "normal", "capability_role": "none"},
            {"pid": 2, "threads": 4, "vmrss_kib": 400, "io": {"read_bytes": 1, "write_bytes": 8}, "cpu_system_percent": 9.0, "workload_hint": "ai_runtime", "capability_role": "persistent_model"},
            {"pid": 3, "threads": 1, "vmrss_kib": 200, "io": {"read_bytes": 9, "write_bytes": 0}, "cpu_system_percent": 2.0, "workload_hint": "game", "capability_role": "none"},
        ],
    )

    assert snapshot["schema"] == "abyss_machine_process_snapshot_v1"
    assert snapshot["summary"]["processes"] == 3
    assert snapshot["summary"]["threads"] == 7
    assert snapshot["summary"]["protected_capability_processes"] == 1
    assert snapshot["summary"]["game_processes"] == 1
    assert [item["pid"] for item in snapshot["top"]["rss"]] == [2, 3]
    assert [item["pid"] for item in snapshot["top"]["cpu"]] == [2, 3]
    assert snapshot["capture"]["facts_only"] is True


def test_processes_paths_cli_uses_public_contract_shape_without_live_snapshot() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC_ROOT)
    result = subprocess.run(
        [sys.executable, "-m", "abyss_machine.cli", "processes", "paths", "--json"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema"] == "abyss_machine_process_paths_v1"
    assert payload["commands"]["thermal_plan"] == "abyss-machine processes thermal-plan --json"
    assert payload["policy_contract"]["mutates_existing_processes"] is False

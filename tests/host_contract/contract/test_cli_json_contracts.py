from __future__ import annotations

import os
import subprocess
import sys

import pytest

from conftest import SRC_ROOT, parse_json_stdout


pytestmark = [pytest.mark.quick, pytest.mark.contract]


@pytest.mark.parametrize(
    ("args", "timeout", "allowed_returncodes"),
    [
        (("enter", "--json"), 20.0, {0}),
        (("storage", "paths", "--json"), 20.0, {0}),
        (("changes", "paths", "--json"), 20.0, {0}),
        (("maps", "paths", "--json"), 20.0, {0}),
        (("maps", "query", "--axis", "by-freshness", "--query", "semantic", "--json"), 20.0, {0}),
        (("typing", "status", "--compact", "--json"), 60.0, {0, 1}),
        (("typing", "capture-gate", "--source", "manual_cli_args", "--json"), 20.0, {0}),
        (("typing", "coverage", "--json"), 60.0, {0}),
        (("typing", "zsh-hook-status", "--json"), 20.0, {0}),
        (("typing", "codex-hook-status", "--json"), 20.0, {0}),
        (("dictation", "profile", "list", "--json"), 20.0, {0}),
        (("ai", "llm", "workhorse", "paths", "--json"), 20.0, {0}),
    ],
)
def test_core_readonly_cli_commands_emit_json_objects(
    run_abyss_machine,
    args: tuple[str, ...],
    timeout: float,
    allowed_returncodes: set[int],
) -> None:
    result = run_abyss_machine(*args, timeout=timeout)

    assert result.returncode in allowed_returncodes, result.stderr[-1000:]
    payload = parse_json_stdout(result)
    assert payload
    if args[:2] == ("typing", "status"):
        assert payload.get("schema") == "abyss_machine_typing_status_compact_v1"
        assert payload.get("source_schema") == "abyss_machine_typing_status_v1"
        assert result.returncode == (0 if payload.get("ok") is True else 1)


@pytest.mark.parametrize(
    ("args", "expected_schema"),
    [
        (("memory", "plan", "--json"), "abyss_machine_memory_plan_v1"),
        (
            ("resource", "plan", "--class", "probe", "--kind", "generic", "--json"),
            "abyss_machine_resource_plan_v1",
        ),
    ],
)
def test_planning_commands_are_facts_or_plan_outputs_not_apply_outputs(
    run_abyss_machine,
    args: tuple[str, ...],
    expected_schema: str,
) -> None:
    result = run_abyss_machine(*args, timeout=30.0)

    assert result.returncode == 0, result.stderr[-1000:]
    payload = parse_json_stdout(result)
    assert payload.get("schema") == expected_schema
    assert isinstance(payload.get("version"), str) and payload["version"]
    assert payload.get("ok") is True
    assert payload.get("permission_required") is not True
    assert payload.get("executed") is None
    assert payload.get("dry_run") is not False
    if args[:2] == ("memory", "plan"):
        assert isinstance(payload.get("pressure"), dict)
        assert "recommended_new_work" not in payload
        assert payload["policy"]["numeric_workload_gating"] is False


def test_selected_command_keeps_unrelated_cli_organs_lazy() -> None:
    script = """
from abyss_machine import cli
assert type(vars(cli)["artifact_bundles"]).__name__ == "_LazyModule"
assert type(vars(cli)["self_awareness_adapters"]).__name__ == "_LazyModule"
assert cli.main(["storage", "paths", "--json"]) == 0
assert type(vars(cli)["artifact_bundles"]).__name__ == "_LazyModule"
assert type(vars(cli)["self_awareness_adapters"]).__name__ == "_LazyModule"
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC_ROOT) + os.pathsep + env.get("PYTHONPATH", "")

    result = subprocess.run(
        [sys.executable, "-c", script],
        text=True,
        capture_output=True,
        timeout=20.0,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr[-1000:]


def test_cli_eager_startup_switch_is_a_compatibility_rollback() -> None:
    script = """
from abyss_machine import cli
assert type(vars(cli)["artifact_bundles"]).__name__ != "_LazyModule"
assert type(vars(cli)["self_awareness_adapters"]).__name__ != "_LazyModule"
assert cli.main(["storage", "paths", "--json"]) == 0
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["ABYSS_MACHINE_CLI_EAGER_STARTUP"] = "1"

    result = subprocess.run(
        [sys.executable, "-c", script],
        text=True,
        capture_output=True,
        timeout=20.0,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr[-1000:]


def test_cli_help_keeps_full_root_catalog_and_selected_subcommand_help(run_abyss_machine) -> None:
    root_help = run_abyss_machine("--help")
    storage_help = run_abyss_machine("storage", "--help")

    assert root_help.returncode == 0, root_help.stderr[-1000:]
    assert storage_help.returncode == 0, storage_help.stderr[-1000:]
    for command in ("doctor", "storage", "artifacts", "resource", "self-awareness", "typing"):
        assert command in root_help.stdout
    for command in ("status", "paths", "policy", "validate", "write-preflight"):
        assert command in storage_help.stdout


def test_enter_uses_only_bounded_read_surfaces(monkeypatch, abyss_machine_module) -> None:
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        abyss_machine_module,
        "status",
        lambda: pytest.fail("enter must not build the unused full host status"),
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "topology_status",
        lambda write_latest=True: calls.append(("topology", write_latest))
        or {"ok": True, "write_policy": {}, "surface_states": []},
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "mode_status",
        lambda write_latest=True: pytest.fail(
            "a valid mode latest must avoid live mode collection"
        ),
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "cooling_status",
        lambda write_latest=True: pytest.fail(
            "a valid cooling latest must avoid live cooling collection"
        ),
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "dictation_status",
        lambda: {"hotkeys": {"toggle": "fixture"}},
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "systemd_unit",
        lambda name: {"name": name, "active": True},
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "load_json_document",
        lambda path: (
            {
                "schema": "abyss_machine_changes_index_v1",
                "generated_at": "2026-08-12T00:00:00+00:00",
                "ok": True,
                "summary": {"active_records": 2},
            },
            None,
        )
        if path == abyss_machine_module.CHANGE_INDEX_PATH
        else (
            {
                "schema": "abyss_machine_mode_status_v1",
                "generated_at": "2026-08-12T00:00:00+00:00",
                "selected_mode": "balanced",
                "effective_mode": "balanced",
                "actual_power_profile": "balanced",
                "battery": {"ac_online": True},
            },
            None,
        )
        if path == abyss_machine_module.MODE_LATEST_PATH
        else (
            {
                "schema": "abyss_machine_cooling_status_v1",
                "generated_at": "2026-08-12T00:00:00+00:00",
                "ok": True,
                "profile": "balanced",
            },
            None,
        )
        if path == abyss_machine_module.COOLING_LATEST_PATH
        else ({"summary": {}}, None),
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "changes_status",
        lambda write_latest=True: pytest.fail(
            "a valid owner index must avoid a live change-ledger rescan"
        ),
    )

    payload = abyss_machine_module.enter_status()

    assert payload["ok"] is True
    assert calls == [("topology", False)]
    assert payload["status"]["mode"]["basis"] == "persisted_owner_latest"
    assert payload["status"]["cooling"]["basis"] == "persisted_owner_latest"
    assert payload["status"]["changes"] == {"active_records": 2}
    assert payload["status"]["changes_index"]["basis"] == "persisted_owner_index"
    assert payload["status"]["changes_index"]["full_status_command"] == (
        "abyss-machine changes status --json"
    )

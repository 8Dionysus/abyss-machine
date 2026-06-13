from __future__ import annotations

import pytest

from conftest import parse_json_stdout


pytestmark = [pytest.mark.quick, pytest.mark.contract]


@pytest.mark.parametrize(
    "args",
    [
        ("enter", "--json"),
        ("storage", "paths", "--json"),
        ("memory", "policy", "--json"),
        ("resource", "policy", "--json"),
        ("changes", "paths", "--json"),
        ("maps", "paths", "--json"),
        ("maps", "query", "--axis", "by-freshness", "--query", "semantic", "--json"),
        ("maps", "packet", "--axis", "by-eval-packet", "--consumer", "aoa-evals", "--json"),
        ("typing", "status", "--json"),
        ("typing", "capture-gate", "--source", "manual_cli_args", "--json"),
        ("typing", "coverage", "--json"),
        ("typing", "zsh-hook-status", "--json"),
        ("typing", "codex-hook-status", "--json"),
        ("dictation", "profile", "list", "--json"),
        ("ai", "llm", "workhorse", "paths", "--json"),
    ],
)
def test_core_readonly_cli_commands_emit_json_objects(run_abyss_machine, args: tuple[str, ...]) -> None:
    result = run_abyss_machine(*args)

    assert result.returncode == 0, result.stderr[-1000:]
    payload = parse_json_stdout(result)
    assert payload


@pytest.mark.parametrize(
    "args",
    [
        ("memory", "plan", "--json"),
        ("resource", "plan", "--class", "probe", "--kind", "generic", "--json"),
    ],
)
def test_planning_commands_are_facts_or_plan_outputs_not_apply_outputs(run_abyss_machine, args: tuple[str, ...]) -> None:
    result = run_abyss_machine(*args, timeout=30.0)

    assert result.returncode == 0, result.stderr[-1000:]
    payload = parse_json_stdout(result)
    assert payload.get("ok") is not False
    assert payload.get("permission_required") is not True
    assert payload.get("executed") is not True
    assert payload.get("dry_run") is not False

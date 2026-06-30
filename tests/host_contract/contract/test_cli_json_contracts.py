from __future__ import annotations

import pytest

from conftest import parse_json_stdout


pytestmark = [pytest.mark.quick, pytest.mark.contract]


@pytest.mark.parametrize(
    ("args", "timeout"),
    [
        (("enter", "--json"), 20.0),
        (("storage", "paths", "--json"), 20.0),
        (("memory", "policy", "--json"), 20.0),
        (("resource", "policy", "--json"), 20.0),
        (("changes", "paths", "--json"), 20.0),
        (("maps", "paths", "--json"), 20.0),
        (("maps", "query", "--axis", "by-freshness", "--query", "semantic", "--json"), 20.0),
        (("maps", "packet", "--axis", "by-eval-packet", "--consumer", "aoa-evals", "--json"), 20.0),
        (("typing", "status", "--json"), 60.0),
        (("typing", "capture-gate", "--source", "manual_cli_args", "--json"), 20.0),
        (("typing", "coverage", "--json"), 60.0),
        (("typing", "zsh-hook-status", "--json"), 20.0),
        (("typing", "codex-hook-status", "--json"), 20.0),
        (("dictation", "profile", "list", "--json"), 20.0),
        (("ai", "llm", "workhorse", "paths", "--json"), 20.0),
    ],
)
def test_core_readonly_cli_commands_emit_json_objects(
    run_abyss_machine,
    args: tuple[str, ...],
    timeout: float,
) -> None:
    result = run_abyss_machine(*args, timeout=timeout)

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

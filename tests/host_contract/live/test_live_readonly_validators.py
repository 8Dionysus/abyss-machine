from __future__ import annotations

import pytest

from conftest import parse_json_stdout


pytestmark = [pytest.mark.live, pytest.mark.contract]


@pytest.mark.parametrize(
    "args",
    [
        ("docs", "mesh-validate", "--json"),
        ("docs", "audit", "--json"),
        ("topology", "validate", "--json"),
        ("graph", "validate", "--json"),
        ("memory", "validate", "--json"),
        ("resource", "validate", "--json"),
        ("stack-bridge", "validate", "--json"),
        ("dictation", "validate", "--json"),
    ],
)
def test_live_readonly_validators_return_no_fails(run_abyss_machine, args: tuple[str, ...]) -> None:
    result = run_abyss_machine(*args, timeout=60.0)

    assert result.returncode in {0, 2}, result.stderr[-1000:]
    payload = parse_json_stdout(result)
    summary = payload.get("summary", {})
    assert summary.get("fails", 0) == 0

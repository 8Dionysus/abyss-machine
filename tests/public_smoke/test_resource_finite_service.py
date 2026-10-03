from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from abyss_machine import cli, resource_planning


def test_finite_service_properties_survive_creation_argv_and_do_not_mutate_default():
    plan = {"systemd": {"unit_type": "service", "properties": {"CPUWeight": "50"}}}
    before = resource_planning.systemd_command(plan, ["/usr/bin/true"], "finite-test", False)
    assert not any("RuntimeMax" in value or "TimeoutStop" in value for value in before)
    plan["systemd"]["properties"].update(resource_planning.finite_service_properties("service", 895, 5))
    argv = resource_planning.systemd_command(plan, ["/usr/bin/true"], "finite-test", False)
    for property_value in ("RuntimeMaxSec=895000000us", "TimeoutStopSec=5000000us", "RuntimeRandomizedExtraSec=0", "KillMode=control-group", "SendSIGKILL=yes", "Restart=no"):
        assert property_value in argv
        assert argv[argv.index(property_value) - 1] == "-p"
    assert resource_planning.finite_service_properties("scope", None, None) == {}
    assert resource_planning.finite_service_properties("service", 1.0000009, 1)["RuntimeMaxSec"] == "1000000us"


@pytest.mark.parametrize("unit_type,runtime,stop", [("scope", 1, 1), ("service", None, 1), ("service", 1, None), ("service", 0, 1), ("service", 1, -1), ("service", float("inf"), 1), ("service", float("nan"), 1), ("service", 1e-10, 1), ("service", 2**64, 1)])
def test_invalid_service_lifetime_rejected_before_any_admission(unit_type, runtime, stop, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("invalid request reached admission")
    monkeypatch.setattr(cli, "resource_policy_document", forbidden)
    with pytest.raises(ValueError):
        cli.resource_launch(["/usr/bin/true"], unit_type=unit_type, runtime_max_sec=runtime, timeout_stop_sec=stop)


def test_cli_scope_finite_rejected_before_launch(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("invalid request launched")
    monkeypatch.setattr(cli, "resource_launch", forbidden)
    with pytest.raises(SystemExit) as exc:
        cli.main(["resource", "launch", "--scope", "--runtime-max-sec", "1", "--timeout-stop-sec", "1", "--", "/usr/bin/true"])
    assert exc.value.code == 2

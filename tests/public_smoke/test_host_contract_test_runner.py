from __future__ import annotations

import runpy
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER = runpy.run_path(str(REPO_ROOT / "tools" / "abyss-machine-test"))


def test_quick_runner_admits_only_exact_pinned_bounded_scheduler() -> None:
    scheduler_plan = RUNNER["scheduler_plan"]

    admitted = scheduler_plan("quick", "auto", xdist_version="3.8.0")
    stale = scheduler_plan("quick", "auto", xdist_version="3.7.0")
    missing = scheduler_plan("quick", "auto", xdist_version=None)
    explicit_bad = scheduler_plan("quick", "xdist-3", xdist_version="3.7.0")

    assert admitted == {
        "ok": True,
        "requested": "auto",
        "effective": "xdist-3",
        "reason": "measured_bounded_quick_scheduler",
        "pytest_args": ["-n", "3", "--dist", "load"],
    }
    assert stale["effective"] == missing["effective"] == "serial"
    assert stale["reason"] == missing["reason"] == (
        "safe_serial_fallback_without_exact_xdist_pin"
    )
    assert explicit_bad["ok"] is False
    assert explicit_bad["reason"] == "pytest_xdist_pin_unavailable"


def test_unmeasured_lanes_and_explicit_rollback_stay_serial() -> None:
    scheduler_plan = RUNNER["scheduler_plan"]

    for lane in ("full", "live", "long", "manual"):
        automatic = scheduler_plan(lane, "auto", xdist_version="3.8.0")
        refused = scheduler_plan(lane, "xdist-3", xdist_version="3.8.0")
        assert automatic["effective"] == "serial"
        assert automatic["reason"] == "non_quick_lane_keeps_serial_authority"
        assert refused["ok"] is False
        assert refused["reason"] == "scheduler_not_admitted_for_lane"

    rollback = scheduler_plan("quick", "serial", xdist_version="3.8.0")
    assert rollback["effective"] == "serial"
    assert rollback["reason"] == "explicit_serial_rollback"


def test_scheduler_changes_only_order_not_quick_selection() -> None:
    scheduler = RUNNER["scheduler_plan"](
        "quick",
        "auto",
        xdist_version="3.8.0",
    )
    command = RUNNER["pytest_command"](
        "quick",
        scheduler=scheduler,
        extra_args=["--maxfail=1"],
    )

    assert command[:4] == [sys.executable, "-m", "pytest", "-q"]
    assert command[4:8] == ["-n", "3", "--dist", "load"]
    marker_index = command.index("-m", 8)
    assert command[marker_index + 1] == "quick and not live and not long and not manual"
    assert command[-1] == "--maxfail=1"

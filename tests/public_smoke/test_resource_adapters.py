from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import resource_adapters


def test_resource_reservation_snapshot_subtracts_materialized_memory(tmp_path: Path) -> None:
    root = tmp_path / "reservations"
    lease = {
        "id": "model-a",
        "launcher_pid": 4242,
        "unit": "model-a.service",
        "demand_mib": 4096,
        "expires_at_epoch": 200.0,
    }
    path = resource_adapters.atomic_write_lease(root, lease)

    snapshot = resource_adapters.reservation_snapshot(
        root,
        now_epoch=100.0,
        pid_alive_port=lambda pid: pid == 4242,
        unit_state_port=lambda unit: {
            "exists": True,
            "active": True,
            "state": "active",
            "memory_current_mib": 1536.0,
        },
    )

    assert oct(path.stat().st_mode & 0o777) == "0o600"
    assert snapshot["summary"]["active_count"] == 1
    assert snapshot["summary"]["outstanding_mib"] == 2560.0
    assert snapshot["items"][0]["materialized_mib"] == 1536.0


def test_resource_reservation_snapshot_cleans_expired_and_dead_leases(tmp_path: Path) -> None:
    root = tmp_path / "reservations"
    resource_adapters.atomic_write_lease(
        root,
        {"id": "expired", "launcher_pid": 1, "unit": "", "demand_mib": 1024, "expires_at_epoch": 99.0},
    )
    resource_adapters.atomic_write_lease(
        root,
        {"id": "dead", "launcher_pid": 2, "unit": "dead.service", "demand_mib": None, "expires_at_epoch": 200.0},
    )

    snapshot = resource_adapters.reservation_snapshot(
        root,
        cleanup=True,
        now_epoch=100.0,
        pid_alive_port=lambda _pid: False,
        unit_state_port=lambda _unit: {"exists": False, "active": False, "state": "inactive", "memory_current_mib": 0.0},
    )

    assert snapshot["summary"]["active_count"] == 0
    assert snapshot["summary"]["removed_count"] == 2
    assert list(root.glob("*.json")) == []


def test_resource_reservation_snapshot_keeps_active_unit_after_startup_deadline(tmp_path: Path) -> None:
    root = tmp_path / "reservations"
    resource_adapters.atomic_write_lease(
        root,
        {
            "id": "long-agent-task",
            "launcher_pid": 4242,
            "unit": "long-agent-task.service",
            "demand_mib": 4096,
            "expires_at_epoch": 99.0,
        },
    )

    snapshot = resource_adapters.reservation_snapshot(
        root,
        cleanup=True,
        now_epoch=100.0,
        pid_alive_port=lambda _pid: False,
        unit_state_port=lambda _unit: {
            "exists": True,
            "active": True,
            "state": "active",
            "memory_current_mib": 1536.0,
        },
    )

    assert snapshot["summary"]["active_count"] == 1
    assert snapshot["summary"]["removed_count"] == 0
    assert snapshot["summary"]["outstanding_mib"] == 2560.0
    assert snapshot["items"][0]["phase"] == "active_unit"
    assert snapshot["items"][0]["expired"] is True
    assert snapshot["items"][0]["stale"] is False


def test_resource_unknown_demand_lease_expires_after_startup_even_while_unit_runs(tmp_path: Path) -> None:
    root = tmp_path / "reservations"
    resource_adapters.atomic_write_lease(
        root,
        {
            "id": "unknown-long-task",
            "launcher_pid": 4242,
            "unit": "unknown-long-task.service",
            "demand_mib": None,
            "expires_at_epoch": 99.0,
        },
    )

    snapshot = resource_adapters.reservation_snapshot(
        root,
        cleanup=True,
        now_epoch=100.0,
        pid_alive_port=lambda _pid: True,
        unit_state_port=lambda _unit: {
            "exists": True,
            "active": True,
            "state": "active",
            "memory_current_mib": 1536.0,
        },
    )

    assert snapshot["summary"]["active_count"] == 0
    assert snapshot["summary"]["removed_count"] == 1
    assert snapshot["removed"][0]["reason"] == "startup_deadline_elapsed"


def test_resource_uncalibrated_estimate_lease_is_still_startup_bounded(tmp_path: Path) -> None:
    root = tmp_path / "reservations"
    resource_adapters.atomic_write_lease(
        root,
        {
            "id": "bootstrap-task",
            "launcher_pid": 4242,
            "unit": "bootstrap-task.service",
            "demand_mib": 2048.0,
            "unknown_demand": True,
            "expires_at_epoch": 99.0,
        },
    )

    snapshot = resource_adapters.reservation_snapshot(
        root,
        cleanup=True,
        now_epoch=100.0,
        pid_alive_port=lambda _pid: True,
        unit_state_port=lambda _unit: {
            "exists": True,
            "active": True,
            "state": "active",
            "memory_current_mib": 1024.0,
        },
    )

    assert snapshot["summary"]["active_count"] == 0
    assert snapshot["summary"]["removed_count"] == 1
    assert snapshot["removed"][0]["reason"] == "startup_deadline_elapsed"


def test_resource_runtime_root_prefers_xdg_and_uses_uid_scoped_fallback(tmp_path: Path) -> None:
    assert resource_adapters.runtime_root({"XDG_RUNTIME_DIR": str(tmp_path)}, uid=1234) == tmp_path
    assert resource_adapters.runtime_root({}, uid=1234, path_exists=lambda _path: False).name == "abyss-machine-1234"


def test_resource_demand_profiles_are_bounded_and_use_observed_footprint() -> None:
    document: dict[str, object] = {}
    for index in range(70):
        document = resource_adapters.update_demand_profiles(
            document,
            key=f"route-{index}",
            owner="fixture",
            kind="indexing",
            memory_peak_mib=100 + index,
            memory_swap_peak_mib=20,
            observed_at_epoch=float(index),
            multiplier=1.25,
            max_entries=64,
            max_samples=16,
        )
    for index in range(20):
        document = resource_adapters.update_demand_profiles(
            document,
            key="route-69",
            owner="fixture",
            kind="indexing",
            memory_peak_mib=200 + index,
            memory_swap_peak_mib=30,
            observed_at_epoch=100.0 + index,
            multiplier=1.25,
            max_entries=64,
            max_samples=16,
        )

    profiles = document["profiles"]
    assert isinstance(profiles, dict)
    assert len(profiles) == 64
    profile = profiles["route-69"]
    assert len(profile["samples"]) == 16
    assert profile["observed_max_mib"] == 249.0
    assert profile["estimate_mib"] == 311.25


def test_resource_journal_peak_parser_uses_exact_unit_and_memory_plus_swap() -> None:
    unit = "abyss-machine-indexing-probe-fixture.service"
    commands: list[list[str]] = []
    stdout = "\n".join(
        [
            json.dumps({"USER_UNIT": "other.service", "MEMORY_PEAK": str(9 * 1024**3)}),
            json.dumps({"USER_UNIT": unit, "MEMORY_PEAK": str(512 * 1024**2), "MEMORY_SWAP_PEAK": str(128 * 1024**2)}),
        ]
    )

    def run_port(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess([], 0, stdout=stdout, stderr="")

    peaks = resource_adapters.journal_unit_resource_peaks(unit, since_epoch=123.5, run_port=run_port)

    assert peaks["ok"] is True
    assert peaks["memory_peak_mib"] == 512.0
    assert peaks["memory_swap_peak_mib"] == 128.0
    assert peaks["footprint_peak_mib"] == 640.0
    assert peaks["matched_records"] == 1
    assert commands[0][commands[0].index("--since") + 1] == "@123.500000"

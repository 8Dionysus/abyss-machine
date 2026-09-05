from __future__ import annotations

import datetime as dt
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli
from abyss_machine import resource_adapters
from abyss_machine import resource_runner
from abyss_machine import storage_reservations


def _fake_capacity(_path: Path, **_kwargs: object) -> dict[str, int]:
    return {
        "available_to_user_bytes": 10_000_000_000,
        "free_bytes": 10_000_000_000,
    }


def test_allowed_srv_write_remains_green_when_root_pressure_is_a_finding(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "abyss-machine" / "validation"
    monkeypatch.setattr(
        cli,
        "storage_pressure",
        lambda **_kwargs: {
            "ok": False,
            "schema": "abyss_machine_storage_pressure_v1",
            "summary": {
                "root_pressure_class": "critical",
                "srv_pressure_class": "warning",
            },
            "roots": {},
        },
    )
    monkeypatch.setattr(
        cli,
        "storage_path_protection",
        lambda _path: {
            "decision": "allow_candidate",
            "class": "host_owned_allowed",
        },
    )
    monkeypatch.setattr(
        cli,
        "storage_preflight_recommended_target",
        lambda _kind, requested: str(requested),
    )
    monkeypatch.setattr(
        cli,
        "storage_preflight_recommended_base",
        lambda _kind: target.parent,
    )
    monkeypatch.setattr(cli, "disk_usage_summary", _fake_capacity)
    monkeypatch.setattr(
        cli.storage_reservations,
        "capacity_snapshot",
        lambda *_args, **_kwargs: {
            "ok": True,
            "available_to_user_bytes": 10_000_000_000,
            "available_after_reservations_bytes": 10_000_000_000,
        },
    )
    monkeypatch.setattr(cli, "run_storage_hooks", lambda *_args, **_kwargs: {"ok": True})

    result = cli.storage_write_preflight(
        kind="artifact",
        bytes_required=512 * 1024 * 1024,
        target=str(target),
        write_latest=False,
    )

    assert result["decision"] == "allow"
    assert result["ok"] is True
    assert result["runtime_errors"] == []
    assert {item["scope"] for item in result["pressure_findings"]} == {"root", "srv"}
    assert result["pressure"]["status"] == "finding"


def test_resource_launch_acquires_explicit_storage_reservation_before_execution(monkeypatch, tmp_path: Path) -> None:
    events: list[str] = []
    lock_state = {"held": False}
    storage_root = tmp_path / "storage-reservations"
    memory_root = tmp_path / "memory-reservations"
    target = tmp_path / "abyss-machine" / "generated"

    @contextmanager
    def fake_admission_lock(_root: Path):
        lock_state["held"] = True
        events.append("lock_enter")
        try:
            yield
        finally:
            events.append("lock_exit")
            lock_state["held"] = False

    monkeypatch.setattr(cli.resource_adapters, "admission_lock", fake_admission_lock)
    monkeypatch.setattr(cli.resource_adapters, "reservations_root", lambda *_args, **_kwargs: memory_root)
    monkeypatch.setattr(cli.resource_adapters, "demand_profiles_path", lambda *_args, **_kwargs: tmp_path / "profiles.json")
    monkeypatch.setattr(
        cli.resource_adapters,
        "reservation_snapshot",
        lambda *_args, **_kwargs: {"ok": True, "summary": {"active_count": 0, "outstanding_mib": 0}},
    )
    monkeypatch.setattr(cli, "storage_write_preflight", lambda **_kwargs: {"ok": True, "decision": "allow"})
    monkeypatch.setattr(
        cli,
        "storage_path_protection",
        lambda _path: {"decision": "allow_candidate", "class": "host_owned_allowed"},
    )
    monkeypatch.setattr(
        cli,
        "resource_policy_document",
        lambda: {"startup_admission": {"enabled": False}},
    )
    monkeypatch.setattr(
        cli,
        "resource_plan",
        lambda **_kwargs: {
            "blocked_reasons": [],
            "denied_reasons": [],
            "inputs": {"startup_demand": {"requested": {"reservation_required": False}}},
            "request": {"activity": {"normalized": "foreground"}},
            "systemd": {"unit_type": "service"},
        },
    )
    monkeypatch.setattr(cli, "resource_systemd_command", lambda *_args, **_kwargs: ["systemd-run", "--user", "/bin/true"])

    def acquire(_root: Path, **kwargs: object) -> dict[str, object]:
        events.append("acquire")
        assert lock_state["held"] is True
        assert kwargs["requested_bytes"] == 123
        assert kwargs["target"] == target
        assert kwargs["owner"] == "generic"
        assert kwargs["hold_until_terminal"] is True
        return {
            "schema": storage_reservations.SCHEMA,
            "ok": True,
            "decision": "reserved",
            "reservation": {
                "reservation_id": str(kwargs["reservation_id"]),
                "owner": "generic",
                "execution_identity": str(kwargs["execution_identity"]),
                "requested_bytes": 123,
                "target": str(target),
                "kind": "artifact",
            },
        }

    monkeypatch.setattr(cli.storage_reservations, "acquire_reservation", acquire)

    def execute(**kwargs: object) -> dict[str, object]:
        events.append("execute")
        assert lock_state["held"] is False
        reservation = kwargs["storage_reservation"]
        assert isinstance(reservation, dict)
        assert reservation["requested_bytes"] == 123
        return {
            "elapsed_sec": 0.1,
            "execution": {"ok": True, "returncode": 0, "systemd": {}},
            "lease_released": True,
            "demand_observation": None,
            "storage_reservation_release": {
                "requested": True,
                "ok": True,
                "decision": "released",
                "release_pending": False,
            },
        }

    monkeypatch.setattr(cli.resource_adapters, "execute_systemd_launch", execute)

    result = cli.resource_launch(
        command=["/bin/true"],
        workload_class="probe",
        kind="generic",
        sample_thermal=False,
        bytes_required=123,
        target=str(target),
        write_latest=False,
        execution_delegate=None,
    )

    assert result["ok"] is True
    assert events.index("acquire") < events.index("lock_exit") < events.index("execute")
    assert result["request"]["bytes_required"] == 123
    assert result["request"]["target"] == str(target)
    assert result["storage_reservation"]["accounting_complete"] is True


def test_resource_runner_handoff_carries_reservation_and_release_receipt(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def execute(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "elapsed_sec": 0.1,
            "execution": {"ok": True, "returncode": 0, "systemd": {}},
            "lease_released": True,
            "demand_observation": None,
            "storage_reservation_release": {
                "requested": True,
                "ok": True,
                "decision": "released",
                "release_pending": False,
            },
        }

    monkeypatch.setattr(resource_runner.resource_adapters, "execute_systemd_launch", execute)
    reservation_root = tmp_path / "storage-reservations"
    handoff = {
        "document": {
            "blocked_reasons": [],
            "denied_reasons": [],
            "planning": {"elapsed_sec": 0.1},
            "startup_admission": {},
            "policy": {},
            "request": {},
            "storage_reservation": {"requested": True},
        },
        "execution": {
            "systemd_command": ["true"],
            "unit_type": "service",
            "timeout_sec": 1,
            "reservation_root": str(tmp_path / "memory-reservations"),
            "demand_profile_path": str(tmp_path / "profiles.json"),
            "kind": "generic",
            "storage_reservation_root": str(reservation_root),
            "storage_reservation": {
                "reservation_id": "resource-launch-fixture",
                "owner": "generic",
                "execution_identity": "resource-launch-fixture:execution",
                "requested_bytes": 123,
                "target": str(tmp_path / "target"),
            },
        },
        "write_latest": False,
    }

    result = resource_runner.finish_document(handoff)

    assert captured["storage_reservation_root"] == reservation_root
    assert captured["storage_reservation"]["reservation_id"] == "resource-launch-fixture"
    assert result["storage_reservation"]["accounting_complete"] is True
    assert result["storage_reservation"]["release"]["decision"] == "released"


def test_timeout_keeps_storage_reservation_when_unit_state_is_still_active(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage-reservations"
    target = tmp_path / "target"
    acquired = storage_reservations.acquire_reservation(
        storage_root,
        reservation_id="timeout-fixture",
        kind="artifact",
        requested_bytes=123,
        target=target,
        owner="fixture",
        ttl_seconds=1,
        hold_until_terminal=True,
        execution_identity="timeout-fixture:execution",
        disk_usage=_fake_capacity,
    )
    assert acquired["ok"] is True

    calls = 0

    def run_port(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise subprocess.TimeoutExpired(command, 1, output="Running as unit: timeout-fixture.service\n", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="active\n", stderr="")

    outcome = resource_adapters.execute_systemd_launch(
        systemd_command=["systemd-run", "--user", "/bin/true"],
        launch_unit="timeout-fixture.service",
        generated_unit=None,
        unit_type="service",
        timeout_sec=1,
        lease=None,
        reservation_root=tmp_path / "memory-reservations",
        demand_profile_path=tmp_path / "profiles.json",
        demand_key=None,
        demand_owner=None,
        kind="generic",
        observed_peak_multiplier=1.25,
        profile_max_entries=64,
        profile_max_samples=16,
        parse_output=lambda _text: {"unit": "timeout-fixture.service"},
        run_port=run_port,
        unit_state_port=lambda _unit: {"exists": True, "active": True, "state": "active"},
        storage_reservation={
            "reservation_id": "timeout-fixture",
            "owner": "fixture",
            "execution_identity": "timeout-fixture:execution",
        },
        storage_reservation_root=storage_root,
    )

    assert outcome["completion"]["confirmed_terminal"] is False
    assert outcome["storage_reservation_release"]["decision"] == "deferred_until_terminal"
    listing = storage_reservations.list_reservations(
        storage_root,
        now=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=5),
    )
    assert listing["expiry_deferred_count"] == 1
    assert listing["active_reserved_bytes"] == 123


def test_runner_error_releases_reservation_when_no_unit_started(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage-reservations"
    target = tmp_path / "target"
    assert storage_reservations.acquire_reservation(
        storage_root,
        reservation_id="runner-error-fixture",
        kind="artifact",
        requested_bytes=123,
        target=target,
        owner="fixture",
        ttl_seconds=60,
        hold_until_terminal=True,
        execution_identity="runner-error-fixture:execution",
        disk_usage=_fake_capacity,
    )["ok"]

    def run_port(_command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise PermissionError("systemd user runner unavailable")

    outcome = resource_adapters.execute_systemd_launch(
        systemd_command=["systemd-run", "--user", "/bin/true"],
        launch_unit="runner-error-fixture.service",
        generated_unit=None,
        unit_type="service",
        timeout_sec=1,
        lease=None,
        reservation_root=tmp_path / "memory-reservations",
        demand_profile_path=tmp_path / "profiles.json",
        demand_key=None,
        demand_owner=None,
        kind="generic",
        observed_peak_multiplier=1.25,
        profile_max_entries=64,
        profile_max_samples=16,
        parse_output=lambda _text: {},
        run_port=run_port,
        storage_reservation={
            "reservation_id": "runner-error-fixture",
            "owner": "fixture",
            "execution_identity": "runner-error-fixture:execution",
        },
        storage_reservation_root=storage_root,
    )

    assert outcome["completion"]["confirmation"] == "systemd_runner_error"
    assert outcome["storage_reservation_release"]["decision"] == "released"
    assert storage_reservations.list_reservations(storage_root)["active_reserved_bytes"] == 0


def test_scope_state_probe_error_does_not_release_reservation(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage-reservations"
    target = tmp_path / "target"
    assert storage_reservations.acquire_reservation(
        storage_root,
        reservation_id="scope-probe-fixture",
        kind="artifact",
        requested_bytes=123,
        target=target,
        owner="fixture",
        ttl_seconds=1,
        hold_until_terminal=True,
        execution_identity="scope-probe-fixture:execution",
        disk_usage=_fake_capacity,
    )["ok"]

    outcome = resource_adapters.execute_systemd_launch(
        systemd_command=["systemd-run", "--user", "--scope", "/bin/true"],
        launch_unit="scope-probe-fixture.scope",
        generated_unit=None,
        unit_type="scope",
        timeout_sec=1,
        lease=None,
        reservation_root=tmp_path / "memory-reservations",
        demand_profile_path=tmp_path / "profiles.json",
        demand_key=None,
        demand_owner=None,
        kind="generic",
        observed_peak_multiplier=1.25,
        profile_max_entries=64,
        profile_max_samples=16,
        parse_output=lambda _text: {"unit": "scope-probe-fixture.scope"},
        run_port=lambda command, **_kwargs: subprocess.CompletedProcess(
            command,
            0,
            stdout="",
            stderr="",
        ),
        unit_state_port=lambda _unit: {
            "exists": False,
            "active": False,
            "state": "unknown",
            "error": "systemd probe unavailable",
        },
        storage_reservation={
            "reservation_id": "scope-probe-fixture",
            "owner": "fixture",
            "execution_identity": "scope-probe-fixture:execution",
        },
        storage_reservation_root=storage_root,
    )

    assert outcome["completion"]["confirmed_terminal"] is False
    assert outcome["storage_reservation_release"]["decision"] == "deferred_until_terminal"
    assert storage_reservations.list_reservations(storage_root)["active_reserved_bytes"] == 123


def test_resource_runner_direct_script_path_has_package_safe_imports() -> None:
    environment = {"PATH": os.environ.get("PATH", "")}
    result = subprocess.run(
        [sys.executable, str(ROOT / "src" / "abyss_machine" / "resource_runner.py")],
        cwd=ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 1
    assert "missing resource launch handoff fd" in result.stdout
    assert "attempted relative import" not in result.stdout
    assert "storage_lifecycle_adapters" not in result.stderr


def test_completed_reservation_records_are_bounded(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage-reservations"
    target = tmp_path / "target"
    base = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    for index in range(10):
        now = base + dt.timedelta(seconds=index)
        reservation_id = f"terminal-{index}"
        assert storage_reservations.acquire_reservation(
            storage_root,
            reservation_id=reservation_id,
            kind="artifact",
            requested_bytes=1,
            target=target,
            owner="fixture",
            ttl_seconds=60,
            now=now,
            disk_usage=_fake_capacity,
        )["ok"]
        assert storage_reservations.release_reservation(
            storage_root,
            reservation_id,
            owner="fixture",
            now=now,
        )["ok"]

    listing = storage_reservations.list_reservations(
        storage_root,
        now=base + dt.timedelta(seconds=20),
        terminal_retention_limit=3,
    )
    assert listing["pruned_count"] == 7
    assert listing["terminal_retention_limit"] == 3
    assert len(listing["records"]) == 3
    assert all(item["active"] is False for item in listing["records"])

from __future__ import annotations

import datetime as dt
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli
from abyss_machine import resource_planning
from abyss_machine import resource_adapters
from abyss_machine import resource_runner
from abyss_machine import storage_reservations


def _fake_capacity(_path: Path, **_kwargs: object) -> dict[str, int]:
    return {
        "available_to_user_bytes": 10_000_000_000,
        "free_bytes": 10_000_000_000,
    }


def test_project_preflight_keeps_write_denied_but_admits_capacity_only(
    monkeypatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "project" / "generated"
    target.mkdir(parents=True)
    monkeypatch.setattr(
        cli,
        "storage_path_protection",
        lambda _path: {
            "decision": "deny",
            "class": "protected_read_only",
            "owner": "project-owner",
            "reason": "project writes stay owner-local",
        },
    )
    monkeypatch.setattr(
        cli,
        "storage_pressure",
        lambda **_kwargs: {
            "ok": True,
            "policy_ok": True,
            "summary": {"root_pressure_class": "green", "srv_pressure_class": "green"},
            "roots": {},
        },
    )
    monkeypatch.setattr(cli, "storage_preflight_recommended_target", lambda _kind, requested: str(requested))
    monkeypatch.setattr(cli, "storage_preflight_recommended_base", lambda _kind: target.parent)
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
        bytes_required=128,
        target=str(target),
        write_latest=False,
    )

    assert result["ok"] is True
    assert result["decision"] == "allow"
    assert result["capacity_only"] is True
    assert result["write_permission"] is False
    assert result["cleanup_authority"] is False
    assert result["strict_write_decision"] == "deny"
    assert result["recommendation"]["use_recommended_target"] is False
    assert result["target"]["protection"]["decision"] == "deny"
    assert result["capacity_admission"]["ok"] is True
    assert result["capacity_admission"]["capacity_only"] is True
    assert result["capacity_admission"]["write_permission"] is False
    blocked, denied, warnings = resource_planning.storage_gate(
        {},
        result,
    )
    assert blocked == []
    assert denied == []
    assert "storage_capacity_admitted_without_host_write_authority" in warnings


def test_user_project_reservation_records_identity_and_shares_capacity_bucket(
    monkeypatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "project" / "generated"
    target.mkdir(parents=True)
    storage_root = tmp_path / "reservations"
    capacity = lambda _path, **_kwargs: {
        "available_to_user_bytes": 1_000,
        "free_bytes": 1_000,
    }
    monkeypatch.setattr(
        cli,
        "storage_path_protection",
        lambda _path: {
            "decision": "deny",
            "class": "protected_read_only",
            "owner": "project-owner",
        },
    )
    protection = cli.storage_capacity_path_protection("artifact", target)
    assert protection["class"] == "user_project_capacity"
    metadata = {
        "route_kind": "user_project_capacity",
        "target": str(target),
        "target_identity": protection["target_identity"],
        "owner_uid": protection["owner_uid"],
        "capacity_only": True,
        "write_permission": False,
        "cleanup_authority": False,
    }
    first = storage_reservations.acquire_reservation(
        storage_root,
        reservation_id="project-first",
        kind="artifact",
        requested_bytes=600,
        target=target,
        owner="tree-of-sophia",
        ttl_seconds=60,
        min_free_after=100,
        route_metadata=metadata,
        disk_usage=capacity,
    )
    assert first["ok"] is True
    metadata = first["reservation"]["route_metadata"]
    assert metadata["route_kind"] == "user_project_capacity"
    assert metadata["capacity_only"] is True
    assert metadata["write_permission"] is False
    assert metadata["cleanup_authority"] is False
    assert metadata["target_identity"]["type"] == "directory"

    second = storage_reservations.acquire_reservation(
        storage_root,
        reservation_id="project-second",
        kind="artifact",
        requested_bytes=350,
        target=target,
        owner="tree-of-sophia",
        ttl_seconds=60,
        min_free_after=100,
        route_metadata=metadata,
        disk_usage=capacity,
    )
    assert second["ok"] is False
    assert second["error"] == "available_capacity_after_reservations_below_policy"


def test_user_project_reservation_rejects_directory_replacement(tmp_path: Path) -> None:
    target = tmp_path / "project" / "generated"
    target.mkdir(parents=True)
    match = storage_reservations._capacity_target_identity_ok
    metadata = {
        "route_kind": "user_project_capacity",
        "target": str(target),
        "target_identity": {
            "st_dev": target.stat().st_dev,
            "st_ino": target.stat().st_ino,
            "st_uid": target.stat().st_uid,
            "type": "directory",
        },
        "capacity_only": True,
        "write_permission": False,
        "cleanup_authority": False,
    }
    target.rename(target.with_name("generated-old"))
    target.mkdir()

    assert match(target, metadata) is False
    result = storage_reservations.acquire_reservation(
        tmp_path / "reservations",
        reservation_id="project-replaced",
        kind="artifact",
        requested_bytes=1,
        target=target,
        owner="tree-of-sophia",
        ttl_seconds=60,
        route_metadata=metadata,
        disk_usage=_fake_capacity,
    )
    assert result["ok"] is False
    assert result["error"] == "capacity_target_identity_mismatch"


def test_user_project_reservation_rechecks_identity_after_capacity_read(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "project" / "generated"
    target.mkdir(parents=True)
    identity = target.stat()
    metadata = {
        "route_kind": "user_project_capacity",
        "target": str(target),
        "target_identity": {
            "st_dev": identity.st_dev,
            "st_ino": identity.st_ino,
            "st_uid": identity.st_uid,
            "type": "directory",
        },
        "capacity_only": True,
        "write_permission": False,
        "cleanup_authority": False,
    }
    swapped = {"done": False}

    def replace_during_capacity(_path: Path, **_kwargs: object) -> dict[str, int]:
        if not swapped["done"]:
            swapped["done"] = True
            target.rename(target.with_name("generated-old"))
            target.mkdir()
        return _fake_capacity(target)

    result = storage_reservations.acquire_reservation(
        tmp_path / "reservations",
        reservation_id="project-capacity-replaced",
        kind="artifact",
        requested_bytes=1,
        target=target,
        owner="tree-of-sophia",
        ttl_seconds=60,
        route_metadata=metadata,
        disk_usage=replace_during_capacity,
    )
    assert result["ok"] is False
    assert result["error"] == "capacity_target_identity_changed_during_capacity"


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


@pytest.mark.parametrize("requested_bytes", [123, 0])
def test_resource_launch_acquires_explicit_storage_reservation_before_execution(
    monkeypatch,
    tmp_path: Path,
    requested_bytes: int,
) -> None:
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
        assert kwargs["requested_bytes"] == requested_bytes
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
                "requested_bytes": requested_bytes,
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
        assert reservation["requested_bytes"] == requested_bytes
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
        bytes_required=requested_bytes,
        target=str(target),
        write_latest=False,
        execution_delegate=None,
    )

    assert result["ok"] is True
    assert events.index("acquire") < events.index("lock_exit") < events.index("execute")
    assert result["request"]["bytes_required"] == requested_bytes
    assert result["request"]["target"] == str(target)
    assert result["storage_reservation"]["accounting_complete"] is True


def test_resource_launch_without_storage_request_does_not_create_zero_byte_reservation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    lock_state = {"held": False}
    acquire_calls: list[dict[str, object]] = []
    memory_root = tmp_path / "memory-reservations"

    @contextmanager
    def fake_admission_lock(_root: Path):
        lock_state["held"] = True
        try:
            yield
        finally:
            lock_state["held"] = False

    monkeypatch.setattr(cli.resource_adapters, "admission_lock", fake_admission_lock)
    monkeypatch.setattr(cli.resource_adapters, "reservations_root", lambda *_args, **_kwargs: memory_root)
    monkeypatch.setattr(cli.resource_adapters, "demand_profiles_path", lambda *_args, **_kwargs: tmp_path / "profiles.json")
    monkeypatch.setattr(
        cli.resource_adapters,
        "reservation_snapshot",
        lambda *_args, **_kwargs: {"ok": True, "summary": {"active_count": 0, "outstanding_mib": 0}},
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
    monkeypatch.setattr(
        cli,
        "storage_path_protection",
        lambda _path: {"decision": "allow_candidate", "class": "host_owned_allowed"},
    )

    def acquire(_root: Path, **kwargs: object) -> dict[str, object]:
        acquire_calls.append(dict(kwargs))
        return {
            "schema": storage_reservations.SCHEMA,
            "ok": False,
            "decision": "blocked",
            "error": "fixture_unexpected_storage_request",
        }

    monkeypatch.setattr(cli.storage_reservations, "acquire_reservation", acquire)
    monkeypatch.setattr(
        cli,
        "resource_systemd_command",
        lambda *_args, **_kwargs: ["systemd-run", "--user", "/bin/true"],
    )
    monkeypatch.setattr(
        cli.resource_adapters,
        "execute_systemd_launch",
        lambda **kwargs: {
            "elapsed_sec": 0.01,
            "execution": {"ok": True, "returncode": 0},
            "lease_released": True,
            "demand_observation": None,
            "storage_reservation_release": None,
        },
    )

    result = cli.resource_launch(
        command=["/bin/true"],
        workload_class="probe",
        kind="generic",
        sample_thermal=False,
        write_latest=False,
    )

    assert lock_state["held"] is False
    assert result["ok"] is True
    assert acquire_calls == []
    assert result["request"]["storage_reservation_requested"] is False
    assert result["storage_reservation"]["requested"] is False
    assert result["storage_reservation"]["reservation"] is None
    assert result["storage_reservation"]["acquire"] is None


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
            "launch_attestation": {
                "required": False,
                "deadline_monotonic": None,
            },
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


def test_archive_route_metadata_does_not_split_shared_filesystem_accounting(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage-reservations"
    target = tmp_path / "vault" / "result.json"
    assert storage_reservations.acquire_reservation(
        storage_root,
        reservation_id="generic-shared-fs",
        kind="artifact",
        requested_bytes=100,
        target=target,
        owner="generic",
        ttl_seconds=60,
        disk_usage=_fake_capacity,
    )["ok"]

    route_metadata = {
        "route_id": "owner-vault",
        "owner": "fixture-owner",
        "required_mount": str(tmp_path / "vault"),
        "archive_binding": {
            "st_dev": int(tmp_path.stat().st_dev),
            "mount_id": "42",
            "fs_root": "/",
            "uuid": "runtime-uuid",
            "mapper": "/dev/mapper/fixture",
            "label": "FIXTURE",
        },
    }
    blocked = storage_reservations.acquire_reservation(
        storage_root,
        reservation_id="archive-shared-fs",
        kind="vault-archive",
        requested_bytes=9_999_999_950,
        target=target,
        owner="fixture-owner",
        ttl_seconds=60,
        route_metadata=route_metadata,
        disk_usage=_fake_capacity,
    )
    assert blocked["ok"] is False
    assert blocked["error"] == "available_capacity_after_reservations_below_policy"

    listing = storage_reservations.list_reservations(storage_root)
    assert listing["active_reserved_bytes"] == 100
    assert listing["active"][0]["filesystem_key"].startswith("dev:")


def test_archive_route_metadata_rejects_stale_target_device(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage-reservations"
    target = tmp_path / "target"
    stale = {
        "route_id": "owner-vault",
        "archive_binding": {"st_dev": int(tmp_path.stat().st_dev) + 1},
    }
    result = storage_reservations.acquire_reservation(
        storage_root,
        reservation_id="archive-stale-device",
        kind="vault-archive",
        requested_bytes=1,
        target=target,
        owner="fixture-owner",
        ttl_seconds=60,
        route_metadata=stale,
        disk_usage=_fake_capacity,
    )
    assert result["ok"] is False
    assert result["error"] == "route_filesystem_identity_mismatch"


def test_archive_reservation_rechecks_filesystem_after_capacity_read(monkeypatch, tmp_path: Path) -> None:
    storage_root = tmp_path / "storage-reservations"
    target = tmp_path / "target"
    devices = iter((7, 8))
    monkeypatch.setattr(storage_reservations, "_target_filesystem_device", lambda _target: next(devices))
    route_metadata = {
        "route_id": "owner-vault",
        "owner": "fixture-owner",
        "required_mount": str(tmp_path),
        "archive_binding": {"st_dev": 7},
    }
    result = storage_reservations.acquire_reservation(
        storage_root,
        reservation_id="archive-device-changed",
        kind="vault-archive",
        requested_bytes=1,
        target=target,
        owner="fixture-owner",
        ttl_seconds=60,
        route_metadata=route_metadata,
        disk_usage=_fake_capacity,
    )
    assert result["ok"] is False
    assert result["error"] == "target_filesystem_changed_during_capacity"
    assert not (storage_root / "records").exists()

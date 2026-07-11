from __future__ import annotations

import os
from pathlib import Path
import socket
import sys
import tempfile


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


def test_resource_runtime_root_prefers_xdg_and_uses_uid_scoped_fallback(tmp_path: Path) -> None:
    assert resource_adapters.runtime_root({"XDG_RUNTIME_DIR": str(tmp_path)}, uid=1234) == tmp_path
    assert resource_adapters.runtime_root({}, uid=1234, path_exists=lambda _path: False).name == "abyss-machine-1234"


def test_memory_controller_queue_request_and_grant_paths_are_atomic_and_exact(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    request = {
        "schema": "abyss_machine_memory_controller_queue_request_v1",
        "id": "request:1",
        "owner": "indexer",
        "demand_mib": 2048,
    }
    request_path = resource_adapters.atomic_write_controller_queue_request(runtime, request)
    grant_path = resource_adapters.atomic_write_controller_queue_grant(
        runtime,
        {"schema": "abyss_machine_memory_controller_queue_grant_v1", "request_id": "request:1", "expires_epoch": 200},
    )

    assert request_path.parent == runtime / "queue"
    assert grant_path.parent == runtime / "grants"
    assert oct(request_path.stat().st_mode & 0o777) == "0o600"
    assert resource_adapters.controller_queue_grant(runtime, "request:1", now_epoch=100)["status"] == "granted"
    assert resource_adapters.controller_queue_grant(runtime, "request:1", now_epoch=201)["status"] == "expired"
    assert resource_adapters.remove_controller_queue_request(runtime, "request:1") is True


def test_live_queue_admission_requires_fresh_state_and_live_owned_socket() -> None:
    with tempfile.TemporaryDirectory(prefix="amc-", dir=f"/run/user/{os.getuid()}") as temporary:
        runtime = Path(temporary)
        resource_adapters.atomic_write_controller_admission(
            runtime,
            {"ok": True, "queue_live": True, "fresh_until_epoch": 200},
        )
        absent = resource_adapters.controller_admission_snapshot(runtime, now_epoch=100)
        server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            server.bind(str(runtime / "events.sock"))
            live = resource_adapters.controller_admission_snapshot(runtime, now_epoch=100)
        finally:
            server.close()
            (runtime / "events.sock").unlink(missing_ok=True)

    assert absent["queue_live"] is False
    assert absent["status"] == "controller_unavailable"
    assert live["queue_live"] is True
    assert live["status"] == "fresh"

from __future__ import annotations

from pathlib import Path
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


def test_resource_runtime_root_prefers_xdg_and_uses_uid_scoped_fallback(tmp_path: Path) -> None:
    assert resource_adapters.runtime_root({"XDG_RUNTIME_DIR": str(tmp_path)}, uid=1234) == tmp_path
    assert resource_adapters.runtime_root({}, uid=1234, path_exists=lambda _path: False).name == "abyss-machine-1234"

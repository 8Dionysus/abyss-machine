from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import sys
import threading
import time

import pytest


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import resource_admission_adapters, resource_admission_server


TOKEN = "fixture-release-token-1234567890"


def cold_load_request(**overrides: object) -> dict[str, object]:
    request: dict[str, object] = {
        "owner": "abyss-stack",
        "workload_id": "llama-cpp:gemma4-e2b",
        "request_id": "request-123",
        "release_token": TOKEN,
        "activity": "foreground",
        "class": "heavy",
        "kind": "ai",
        "memory_demand_mib": 4096,
    }
    request.update(overrides)
    return request


def allowed_plan(_request: object, snapshot: dict[str, object]) -> dict[str, object]:
    assert snapshot["summary"]["active_count"] == 0
    return {
        "ok": True,
        "decision": "allow",
        "blocked_reasons": [],
        "denied_reasons": [],
        "warnings": ["cpu_route_owner_foreground_advisory_defer"],
        "request": {"activity": {"normalized": "foreground", "foreground": True}},
        "inputs": {
            "startup_demand": {
                "projected": {"memory_class": "watch", "mem_available_mib": 7168.0}
            }
        },
    }


def test_runtime_admission_reserve_is_atomic_idempotent_and_secret_safe(tmp_path: Path) -> None:
    root = tmp_path / "reservations"
    first = resource_admission_adapters.reserve_cold_load(
        cold_load_request(),
        reservation_root=root,
        runtime_policy={"enabled": True, "cold_load_lease_ttl_sec": 120},
        plan_port=allowed_plan,
        now_epoch=100.0,
        timestamp=lambda: "2026-07-13T12:00:00Z",
    )
    replay = resource_admission_adapters.reserve_cold_load(
        cold_load_request(),
        reservation_root=root,
        runtime_policy={"enabled": True, "cold_load_lease_ttl_sec": 120},
        plan_port=lambda _request, _snapshot: (_ for _ in ()).throw(AssertionError("plan must not repeat")),
        now_epoch=101.0,
        timestamp=lambda: "2026-07-13T12:00:01Z",
    )

    assert first["ok"] is True
    assert first["decision"] == "allow"
    assert first["idempotent_replay"] is False
    assert first["lease"]["runtime_only"] is True
    assert first["plan"]["projected_memory"]["mem_available_mib"] == 7168.0
    assert "release_token" not in repr(first)
    assert TOKEN not in repr(first)
    assert replay["ok"] is True
    assert replay["idempotent_replay"] is True
    assert replay["lease"]["id"] == first["lease"]["id"]


def test_runtime_admission_identity_conflict_and_release_capability_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "reservations"
    granted = resource_admission_adapters.reserve_cold_load(
        cold_load_request(),
        reservation_root=root,
        runtime_policy={"enabled": True},
        plan_port=allowed_plan,
        now_epoch=100.0,
        timestamp=lambda: "2026-07-13T12:00:00Z",
    )
    lease_id = str(granted["lease"]["id"])
    conflict = resource_admission_adapters.reserve_cold_load(
        cold_load_request(memory_demand_mib=8192),
        reservation_root=root,
        runtime_policy={"enabled": True},
        plan_port=lambda _request, _snapshot: {},
        now_epoch=101.0,
        timestamp=lambda: "2026-07-13T12:00:01Z",
    )
    wrong = resource_admission_adapters.release_cold_load(
        {"lease_id": lease_id, "release_token": "wrong-release-token-1234567890"},
        reservation_root=root,
    )
    released = resource_admission_adapters.release_cold_load(
        {"lease_id": lease_id, "release_token": TOKEN},
        reservation_root=root,
    )
    repeated = resource_admission_adapters.release_cold_load(
        {"lease_id": lease_id, "release_token": TOKEN},
        reservation_root=root,
    )

    assert conflict["decision"] == "deny"
    assert conflict["denied_reasons"] == ["request_identity_conflict"]
    assert wrong["decision"] == "deny"
    assert wrong["denied_reasons"] == ["release_capability_invalid"]
    assert released["released"] is True
    assert repeated == {
        "ok": True,
        "decision": "allow",
        "command": "release",
        "released": False,
        "already_absent": True,
    }


def test_runtime_admission_denial_and_unavailable_transport_create_no_lease(tmp_path: Path) -> None:
    root = tmp_path / "reservations"
    blocked = resource_admission_adapters.reserve_cold_load(
        cold_load_request(activity="background"),
        reservation_root=root,
        runtime_policy={"enabled": True},
        plan_port=lambda _request, _snapshot: {
            "ok": False,
            "decision": "force_required",
            "blocked_reasons": ["startup_projected_mem_available_below_hard_reserve"],
            "denied_reasons": [],
            "warnings": [],
        },
        now_epoch=100.0,
        timestamp=lambda: "2026-07-13T12:00:00Z",
    )
    unavailable = resource_admission_adapters.client_request(
        {"command": "ping"},
        path=tmp_path / "missing.sock",
    )
    owner_unavailable = resource_admission_adapters.reserve_cold_load(
        cold_load_request(request_id="request-owner-unavailable"),
        reservation_root=root,
        runtime_policy={"enabled": True},
        plan_port=lambda _request, _snapshot: (_ for _ in ()).throw(RuntimeError("owner unavailable")),
        now_epoch=101.0,
        timestamp=lambda: "2026-07-13T12:00:01Z",
    )

    assert blocked["ok"] is False
    assert blocked["decision"] == "force_required"
    assert list(root.glob("*.json")) == []
    assert unavailable["decision"] == "deny"
    assert unavailable["error"] == "runtime_admission_unavailable"
    assert unavailable["policy"]["fail_closed"] is True
    assert owner_unavailable["decision"] == "deny"
    assert owner_unavailable["denied_reasons"] == ["host_plan_unavailable"]
    assert list(root.glob("*.json")) == []


def test_runtime_admission_preserves_corrupt_lease_and_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "reservations"
    root.mkdir()
    corrupt = root / "corrupt.json"
    corrupt.write_text("{", encoding="utf-8")

    result = resource_admission_adapters.reserve_cold_load(
        cold_load_request(),
        reservation_root=root,
        runtime_policy={"enabled": True},
        plan_port=lambda _request, _snapshot: (_ for _ in ()).throw(AssertionError("plan must not run")),
        now_epoch=100.0,
        timestamp=lambda: "2026-07-13T12:00:00Z",
    )
    observed = resource_admission_adapters.status(reservation_root=root, now_epoch=100.0)

    assert result["decision"] == "deny"
    assert result["denied_reasons"] == ["lease_state_invalid"]
    assert result["lease_state_error_count"] == 1
    assert observed["ok"] is False
    assert corrupt.read_text(encoding="utf-8") == "{"


def test_runtime_admission_dispatch_exposes_no_release_capabilities(tmp_path: Path) -> None:
    response, stop = resource_admission_adapters.dispatch(
        {"command": "status"},
        server_state={"pid": 42},
        reserve_port=lambda _request: {"ok": True},
        release_port=lambda _request: {"ok": True},
        status_port=lambda: {"ok": True, "leases": []},
    )
    shutdown, should_stop = resource_admission_adapters.dispatch(
        {"command": "shutdown"},
        server_state={"pid": 42},
        reserve_port=lambda _request: {"ok": True},
        release_port=lambda _request: {"ok": True},
        status_port=lambda: {"ok": True},
        allow_shutdown=True,
    )

    assert response == {"ok": True, "leases": []}
    assert stop is False
    assert shutdown["command"] == "shutdown"
    assert should_stop is True


def test_runtime_admission_unix_transport_is_private_bounded_and_stoppable() -> None:
    path = Path("/tmp") / f"abyss-ra-{os.getpid()}-{time.time_ns()}.sock"
    outcome: dict[str, object] = {}

    def dispatch_port(payload: dict[str, object]) -> tuple[dict[str, object], bool]:
        command = str(payload.get("command") or "")
        return {"ok": True, "decision": "allow", "command": command}, command == "shutdown"

    def run() -> None:
        outcome.update(
            resource_admission_adapters.run_server_loop(
                path=path,
                dispatch_port=dispatch_port,
                chmod_mode=0o600,
                max_request_bytes=4096,
            )
        )

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 2.0
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(0.01)

    assert path.exists()
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as malformed_client:
        malformed_client.connect(str(path))
        malformed_client.sendall(b"{\n")
        malformed_client.shutdown(socket.SHUT_WR)
        malformed = json.loads(malformed_client.makefile("rb").readline())
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as oversized_client:
        oversized_client.connect(str(path))
        oversized_client.sendall(b"x" * 4097 + b"\n")
        oversized_client.shutdown(socket.SHUT_WR)
        oversized = json.loads(oversized_client.makefile("rb").readline())
    ping = resource_admission_adapters.client_request({"command": "ping"}, path=path)
    shutdown = resource_admission_adapters.client_request({"command": "shutdown"}, path=path)
    thread.join(timeout=2.0)

    assert ping == {"ok": True, "decision": "allow", "command": "ping"}
    assert malformed["denied_reasons"] == ["malformed_request"]
    assert oversized["denied_reasons"] == ["request_too_large"]
    assert shutdown == {"ok": True, "decision": "allow", "command": "shutdown"}
    assert thread.is_alive() is False
    assert outcome["ok"] is True
    assert path.exists() is False


def test_runtime_admission_rejects_insecure_socket_mode(tmp_path: Path) -> None:
    path = tmp_path / "admission.sock"

    with pytest.raises(ValueError, match="must be 0600"):
        resource_admission_adapters.run_server_loop(
            path=path,
            dispatch_port=lambda _payload: ({"ok": True}, False),
            chmod_mode=0o666,
        )

    assert path.exists() is False


def test_lightweight_server_reads_fresh_memory_and_cpu_emergency_facts(tmp_path: Path) -> None:
    meminfo = tmp_path / "meminfo"
    pressure = tmp_path / "pressure"
    hwmon = tmp_path / "hwmon" / "hwmon0"
    hwmon.mkdir(parents=True)
    meminfo.write_text(
        "MemTotal:       32768000 kB\nMemAvailable:   16384000 kB\nSwapTotal:      20971520 kB\nSwapFree:       8388608 kB\n",
        encoding="utf-8",
    )
    pressure.write_text("some avg10=0.00 avg60=0.00 avg300=0.00 total=1\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=1\n", encoding="utf-8")
    (hwmon / "name").write_text("coretemp\n", encoding="utf-8")
    (hwmon / "temp1_label").write_text("Package id 0\n", encoding="utf-8")
    (hwmon / "temp1_input").write_text("55000\n", encoding="utf-8")
    (hwmon / "temp1_crit_alarm").write_text("0\n", encoding="utf-8")

    policy = resource_admission_server.memory_policy({"ABYSS_MACHINE_MEMORY_POLICY": str(tmp_path / "missing.json")})
    summary, current_class = resource_admission_server.fresh_memory_facts(
        meminfo_path=meminfo,
        pressure_path=pressure,
        policy=policy,
    )
    thermal = resource_admission_server.fresh_thermal_safety(hwmon_root=tmp_path / "hwmon", emergency_c=109.0)
    (hwmon / "temp2_label").write_text("Core 0\n", encoding="utf-8")
    (hwmon / "temp2_input").write_text("60000\n", encoding="utf-8")
    (hwmon / "temp2_crit_alarm").write_text("1\n", encoding="utf-8")
    emergency = resource_admission_server.fresh_thermal_safety(hwmon_root=tmp_path / "hwmon", emergency_c=109.0)

    assert summary["mem_total_mib"] == 32000.0
    assert summary["mem_available_mib"] == 16000.0
    assert summary["psi_full_avg10"] == 0.0
    assert current_class == "green"
    assert thermal["available"] is True
    assert thermal["temperature_c_max"] == 55.0
    assert thermal["emergency"] is False
    assert emergency["emergency"] is True

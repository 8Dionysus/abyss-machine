from __future__ import annotations

import json
import os
from pathlib import Path
import select
import socket
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import memory_controller_adapters as adapters
from abyss_machine import resource_adapters


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_collect_sample_reads_proc_zram_cgroup_and_reservations(tmp_path: Path) -> None:
    proc = tmp_path / "proc"
    sys_root = tmp_path / "sys"
    cgroup = tmp_path / "cgroup"
    write(
        proc / "meminfo",
        "MemTotal:       32768000 kB\nMemAvailable:   16384000 kB\n"
        "SwapTotal:      20971520 kB\nSwapFree:       12582912 kB\n"
        "Cached:          4096000 kB\nSReclaimable:     512000 kB\n"
        "Committed_AS:  37748736 kB\nCommitLimit:    26214400 kB\n",
    )
    write(proc / "pressure" / "memory", "some avg10=0.10 avg60=0.20 avg300=0.30 total=120000\nfull avg10=0.01 avg60=0.02 avg300=0.03 total=30000\n")
    write(proc / "vmstat", "pswpin 10\npswpout 20\npgmajfault 30\noom_kill 0\n")
    write(proc / "swaps", "Filename Type Size Used Priority\n/dev/zram0 partition 20971520 8388608 100\n")
    write(sys_root / "block" / "zram0" / "disksize", "21474836480\n")
    write(sys_root / "block" / "zram0" / "mm_stat", "8589934592 4294967296 4509715660 0 4600000000 0 0 131072 200000\n")
    write(sys_root / "block" / "zram0" / "bd_stat", "1 2 3\n")
    write(sys_root / "block" / "zram0" / "io_stat", "0 1 2 3\n")
    write(sys_root / "block" / "zram0" / "comp_algorithm", "lzo [lzo-rle] zstd\n")
    write(cgroup / "memory.current", "4294967296\n")
    write(cgroup / "memory.swap.current", "1073741824\n")
    write(cgroup / "memory.events", "low 0\nhigh 2\nmax 0\noom 0\noom_kill 0\n")

    sample = adapters.collect_memory_sample(
        proc_root=proc,
        sys_root=sys_root,
        cgroup_path=cgroup,
        reservations_port=lambda: {"summary": {"active_count": 2, "outstanding_mib": 3072.0}},
        queued_demand_mib=1024.0,
        epoch_port=lambda: 100.0,
        monotonic_port=lambda: 50.0,
    )

    assert sample["ok"] is True
    assert sample["mem_total_mib"] == 32000.0
    assert sample["mem_available_mib"] == 16000.0
    assert sample["swap_used_mib"] == 8192.0
    assert sample["zram_data_mib"] == 8192.0
    assert sample["zram_resident_mib"] == 4300.8
    assert sample["zram_allocator_metadata_overhead_mib"] == 204.8
    assert sample["zram_physical_savings_mib"] == 3891.2
    assert sample["zram_incompressible_mib"] == 512.0
    assert sample["zram_backing_write_mib"] == 0.012
    assert sample["zram_logical_to_resident_ratio"] == 1.905
    assert sample["psi_some_total_usec"] == 120000
    assert sample["cgroup_memory_mib"] == 4096.0
    assert sample["reservation_outstanding_mib"] == 3072.0
    assert sample["queued_demand_mib"] == 1024.0


def test_open_psi_trigger_uses_unprivileged_two_second_window_and_nul() -> None:
    calls: dict[str, object] = {}

    def open_port(path: str, flags: int) -> int:
        calls["open"] = (path, flags)
        return 42

    def write_port(fd: int, payload: bytes) -> int:
        calls["write"] = (fd, payload)
        return len(payload)

    result = adapters.open_psi_trigger(
        Path("/proc/pressure/memory"),
        kind="some",
        threshold_usec=100_000,
        window_usec=2_000_000,
        open_port=open_port,
        write_port=write_port,
    )

    assert result["ok"] is True
    assert result["fd"] == 42
    assert calls["write"] == (42, b"some 100000 2000000\0")


def test_open_psi_trigger_rejects_invalid_window_before_syscall() -> None:
    result = adapters.open_psi_trigger(
        Path("/proc/pressure/memory"),
        kind="some",
        threshold_usec=100_000,
        window_usec=1_000_000,
        open_port=lambda path, flags: (_ for _ in ()).throw(AssertionError("must not open")),
    )

    assert result == {
        "ok": False,
        "status": "invalid_unprivileged_window",
        "error": "unprivileged PSI windows must be a positive multiple of 2000000 usec",
    }


def test_parse_systemd_monitor_line_keeps_only_lifecycle_signals() -> None:
    event = adapters.parse_systemd_monitor_line(json.dumps({
        "type": "signal",
        "timestamp-realtime": 1234567,
        "interface": "org.freedesktop.systemd1.Manager",
        "member": "UnitNew",
        "payload": {"type": "so", "data": ["model.service", "/unit/model"]},
    }))
    ignored = adapters.parse_systemd_monitor_line(json.dumps({
        "type": "method_call",
        "interface": "org.freedesktop.systemd1.Manager",
        "member": "UnitNew",
        "payload": {"data": ["wrong.service"]},
    }))

    assert event == {
        "source": "systemd",
        "kind": "unit_new",
        "unit": "model.service",
        "result": None,
        "realtime_usec": 1234567,
    }
    assert ignored is None


def test_dbus_systemd_monitor_parser_emits_exact_lifecycle_messages() -> None:
    parser = adapters.DbusSystemdMonitorParser()
    events = parser.feed(
        "signal time=100.125 sender=:1.1 path=/org/freedesktop/systemd1; "
        "interface=org.freedesktop.systemd1.Manager; member=UnitNew\n"
        "   string \"model.service\"\n"
        "   object path \"/org/freedesktop/systemd1/unit/model_2eservice\"\n"
        "signal time=100.250 sender=:1.1 path=/org/freedesktop/systemd1; "
        "interface=org.freedesktop.systemd1.Manager; member=JobRemoved\n"
        "   uint32 42\n"
        "   object path \"/org/freedesktop/systemd1/job/42\"\n"
        "   string \"model.service\"\n"
        "   string \"done\"\n"
    )

    assert events == [
        {"source": "systemd", "kind": "unit_new", "unit": "model.service", "result": None, "epoch": 100.125},
        {"source": "systemd", "kind": "job_removed", "unit": "model.service", "result": "done", "epoch": 100.25},
    ]


def test_systemd_monitor_argv_uses_server_side_exact_unit_matches() -> None:
    argv = adapters.systemd_monitor_argv(["model.service", "worker.scope"])

    assert argv[:2] == ["dbus-monitor", "--session"]
    assert len(argv) == 6
    assert any("arg0='model.service'" in item for item in argv)
    assert any("arg2='worker.scope'" in item for item in argv)
    assert all("libpod-" not in item for item in argv)


def test_bounded_window_is_atomic_and_drops_oldest(tmp_path: Path) -> None:
    path = tmp_path / "window.json"
    for value in range(5):
        adapters.append_bounded_window(path, {"value": value}, limit=3)

    document = json.loads(path.read_text(encoding="utf-8"))

    assert [item["value"] for item in document["items"]] == [2, 3, 4]
    assert document["limit"] == 3
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    assert list(tmp_path.glob(".*.tmp")) == []


def test_registry_loader_merges_runtime_contracts_and_reports_invalid(tmp_path: Path) -> None:
    static = tmp_path / "registry.json"
    runtime = tmp_path / "runtime"
    write(static, json.dumps({"schema": "registry", "workloads": [{"id": "static", "owner": "host"}], "rules": [{"id": "preserve"}]}))
    write(runtime / "runtime.json", json.dumps({"id": "runtime", "owner": "agent"}))
    write(runtime / "broken.json", "{")

    result = adapters.load_registry(static, runtime)

    assert [item["id"] for item in result["workloads"]] == ["static", "runtime"]
    assert result["runtime_count"] == 1
    assert result["error_count"] == 1
    assert result["ok"] is False
    static_workload, runtime_workload = result["workloads"]
    assert static_workload["metadata"]["registry_source"] == "static"
    assert static_workload["metadata"]["registry_trusted_for_lifecycle"] is False
    assert runtime_workload["metadata"]["registry_source"] == "runtime"
    assert runtime_workload["metadata"]["registry_trusted_for_lifecycle"] is False


def test_inotify_watcher_reports_directory_change_without_polling_files(tmp_path: Path) -> None:
    watcher = adapters.InotifyWatcher()
    try:
        watcher.add(tmp_path, source="queue")
        (tmp_path / "request.json").write_text("{}\n", encoding="utf-8")
        poller = select.poll()
        poller.register(watcher.fd, select.POLLIN)
        assert poller.poll(1_000)
        events = watcher.read_events()
    finally:
        watcher.close()
    assert any(item["source"] == "queue" and item["name"] == "request.json" for item in events)


def test_unix_event_socket_accepts_same_uid_structured_event(tmp_path: Path) -> None:
    path = tmp_path / "events.sock"
    server = adapters.open_event_socket(path)
    client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        payload = {
            "schema": "abyss_machine_memory_controller_event_v1",
            "kind": "demand_registered",
            "event_id": "demand-1",
            "details": {"demand_mib": 1024},
        }
        client.sendto(json.dumps(payload).encode("utf-8"), str(path))
        result = adapters.read_event_socket(server, expected_uid=os.getuid())
    finally:
        client.close()
        server.close()
        path.unlink(missing_ok=True)
    assert result["ok"] is True
    assert result["uid"] == os.getuid()
    assert result["event"]["event_id"] == "demand-1"


def test_unix_event_socket_rejects_invalid_schema(tmp_path: Path) -> None:
    path = tmp_path / "events.sock"
    server = adapters.open_event_socket(path)
    client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        client.sendto(json.dumps({"schema": "wrong", "kind": "event"}).encode("utf-8"), str(path))
        result = adapters.read_event_socket(server, expected_uid=os.getuid())
    finally:
        client.close()
        server.close()
        path.unlink(missing_ok=True)
    assert result["ok"] is False
    assert result["status"] == "invalid_event_schema"


def test_resource_outcome_peak_parser_and_controller_notification(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runtime = Path("controller")
    runtime.mkdir()
    server = adapters.open_event_socket(runtime / "events.sock")
    event = {
        "schema": "abyss_machine_memory_controller_event_v1",
        "kind": "resource_launch_outcome",
        "event_id": "launch-1",
        "details": {"observed_peak_mib": 1536.0},
    }
    try:
        notification = resource_adapters.notify_memory_controller(runtime, event)
        received = adapters.read_event_socket(server, expected_uid=os.getuid())
    finally:
        server.close()
        (runtime / "events.sock").unlink(missing_ok=True)

    assert resource_adapters.parse_systemd_memory_peak_mib("1.5G") == 1536.0
    assert resource_adapters.parse_systemd_memory_peak_mib("1.3M (swap: 0B)") == 1.3
    assert resource_adapters.parse_systemd_memory_peak_mib("invalid") is None
    assert notification == {"sent": True, "status": "event_sent"}
    assert received["event"]["kind"] == "resource_launch_outcome"


def test_evidence_store_is_bounded_crash_recoverable_and_summarizes_latency(tmp_path: Path) -> None:
    database = tmp_path / "evidence.sqlite3"
    store = adapters.EvidenceStore(database)
    try:
        for sequence in range(1, 6):
            store.append_sample({"epoch": float(sequence), "value": sequence}, limit=3, retention_hours=24)
            store.append_decision(
                {
                    "sequence": sequence,
                    "epoch": float(sequence),
                    "event": {"event_id": f"event-{sequence}", "source": "test", "kind": "tick"},
                    "timing": {"event_to_decision_ms": float(sequence * 100), "within_target": True},
                    "forecast": {"pressure_band": "healthy"},
                    "decision": {"selected": {"action": "observe", "execution": "observe_only"}},
                    "sample": {"large": "not duplicated into decision history"},
                },
                limit=3,
                retention_hours=24,
            )
        assert [item["value"] for item in store.load_samples(limit=10)] == [3, 4, 5]
        assert store.has_event("event-1") is False
        assert store.has_event("event-5") is True
        summary = store.summary()
    finally:
        store.close()

    assert summary["samples"]["count"] == 3
    assert summary["decisions"]["count"] == 3
    assert summary["decisions"]["latency_ms"]["p95"] == 490.0
    assert summary["decisions"]["within_target_percent"] == 100.0
    assert database.is_file()

    recovered = adapters.EvidenceStore(database)
    try:
        assert recovered.latest_sequence() == 5
        assert recovered.recent_event_ids(2) == ["event-4", "event-5"]
    finally:
        recovered.close()


def test_evidence_store_reconciles_forecast_false_positive_and_false_negative(tmp_path: Path) -> None:
    store = adapters.EvidenceStore(tmp_path / "forecast-evidence.sqlite3")

    def decision(sequence: int, epoch: float, *, band: str, available_mib: float) -> dict:
        return {
            "sequence": sequence,
            "epoch": epoch,
            "event": {"event_id": f"forecast-{sequence}", "source": "test", "kind": "tick"},
            "timing": {"event_to_decision_ms": 10.0, "within_target": True},
            "forecast": {
                "confidence": "high",
                "pressure_band": band,
                "projections": {"10": {"pressure_band": band, "mem_available_mib": available_mib}},
            },
            "decision": {"selected": {"action": "observe", "execution": "observe_only"}},
        }

    def actual(epoch: float, *, band: str, available_mib: float, active: bool) -> dict:
        return {
            "epoch": epoch,
            "sample": {"mem_available_mib": available_mib},
            "forecast": {
                "current": {"pressure_band": band, "mem_available_mib": available_mib},
                "active_memory_relief_needed": active,
                "stall_rates": {"some_percent": 0.0, "full_percent": 0.0, "major_faults_per_sec": 0.0},
            },
        }

    try:
        store.append_decision(decision(1, 100.0, band="warm", available_mib=1_000.0), limit=20, retention_hours=24)
        false_positive = store.reconcile_forecasts(
            actual(110.5, band="healthy", available_mib=2_000.0, active=False),
            limit=20,
            retention_hours=24,
        )
        duplicate = store.reconcile_forecasts(
            actual(111.0, band="healthy", available_mib=2_100.0, active=False),
            limit=20,
            retention_hours=24,
        )
        store.append_decision(decision(2, 200.0, band="healthy", available_mib=2_000.0), limit=20, retention_hours=24)
        false_negative = store.reconcile_forecasts(
            actual(210.5, band="hot", available_mib=900.0, active=True),
            limit=20,
            retention_hours=24,
        )
        summary = store.summary()
        user_version = store.connection.execute("PRAGMA user_version").fetchone()[0]
    finally:
        store.close()

    assert false_positive[0]["classification"] == "false_positive"
    assert false_positive[0]["prediction_error_mib"] == 1_000.0
    assert duplicate == []
    assert false_negative[0]["classification"] == "false_negative"
    assert false_negative[0]["prediction_error_mib"] == -1_100.0
    assert summary["forecast_outcomes"]["count"] == 2
    assert summary["forecast_outcomes"]["classifications"] == {"false_negative": 1, "false_positive": 1}
    assert summary["forecast_outcomes"]["mean_absolute_error_mib"] == 1_050.0
    assert user_version == 4


def test_forecast_outcome_prefers_explicit_stall_projection_over_memory_band(tmp_path: Path) -> None:
    store = adapters.EvidenceStore(tmp_path / "forecast-stall-evidence.sqlite3")
    decision = {
        "sequence": 1,
        "epoch": 100.0,
        "event": {"event_id": "forecast-stall", "source": "test", "kind": "tick"},
        "timing": {"event_to_decision_ms": 10.0, "within_target": True},
        "forecast": {
            "confidence": "high",
            "pressure_band": "hot",
            "projections": {
                "10": {
                    "pressure_band": "healthy",
                    "pressure_expected": True,
                    "pressure_reasons": ["active_stall_persistence"],
                    "mem_available_mib": 20_000.0,
                },
            },
        },
        "decision": {"selected": {"action": "queue_control", "execution": "shadow_only"}},
    }
    actual = {
        "epoch": 110.5,
        "sample": {"mem_available_mib": 19_900.0},
        "forecast": {
            "current": {"pressure_band": "healthy", "mem_available_mib": 19_900.0},
            "active_memory_relief_needed": True,
            "stall_rates": {"some_percent": 0.0, "full_percent": 0.0, "major_faults_per_sec": 30.0},
        },
    }
    try:
        store.append_decision(decision, limit=20, retention_hours=24)
        outcomes = store.reconcile_forecasts(actual, limit=20, retention_hours=24)
    finally:
        store.close()

    assert outcomes[0]["classification"] == "true_positive"
    assert outcomes[0]["predicted"]["pressure_reasons"] == ["active_stall_persistence"]

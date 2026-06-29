from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import memory_adapters


def test_podman_snapshot_reads_container_through_fake_runner() -> None:
    calls: list[tuple[list[str], float]] = []
    target = {"cgroup": "/machine.slice/libpod-abcdef1234567890.scope"}

    def runner(command: list[str], timeout: float) -> dict[str, Any]:
        calls.append((command, timeout))
        return {
            "ok": True,
            "returncode": 0,
            "stdout": json.dumps(
                [
                    {
                        "Id": "abcdef1234567890",
                        "Name": "/rerank-api",
                        "State": {"Status": "running", "Running": True, "Pid": 4242},
                        "NetworkSettings": {"Ports": {"5405/tcp": [{"HostIp": "0.0.0.0", "HostPort": "15405"}]}},
                        "Config": {"Env": ["SECRET=value"]},
                    }
                ]
            ),
            "stderr": "",
        }

    snapshot = memory_adapters.podman_snapshot(
        target,
        command_exists=lambda name: name == "podman",
        runner=runner,
    )

    assert calls == [(["podman", "inspect", "abcdef1234567890"], 8.0)]
    assert snapshot["ok"] is True
    assert snapshot["container_id"] == "abcdef123456"
    assert snapshot["container"]["name"] == "/rerank-api"
    assert "SECRET" not in json.dumps(snapshot)


def test_target_snapshot_uses_fake_proc_systemd_and_podman_ports(tmp_path: Path) -> None:
    proc_root = tmp_path / "proc"
    (proc_root / "123").mkdir(parents=True)
    candidate = {
        "target": {
            "unit": "model.service",
            "cgroup": "/user.slice/user-1000.slice/model.service",
            "pids": [123, 999],
        }
    }
    systemd_calls: list[tuple[str, bool]] = []

    def systemd_props(unit: str, properties: list[str], user: bool, timeout: float) -> dict[str, Any]:
        systemd_calls.append((unit, user))
        assert "MemoryCurrent" in properties
        assert timeout == 2.0
        return {
            "ok": True,
            "properties": {
                "ActiveState": "active",
                "MainPID": "123",
                "MemoryCurrent": "1048576",
                "MemorySwapCurrent": "0",
            },
        }

    snapshot = memory_adapters.target_snapshot(
        candidate,
        cgroup_snapshot=lambda cgroup: {"exists": True, "pids": [123]},
        process_info=lambda pid: {
            "name": "model",
            "workload_hint": "ai_runtime",
            "capability_role": "persistent_model",
            "vmrss_kib": 2048,
            "cmdline": "model --serve",
        },
        systemd_unit_properties=systemd_props,
        memory_control_value=lambda raw: {"raw": raw, "mib": 1.0 if raw == "1048576" else 0.0},
        kib_to_mib=lambda raw: round(float(raw) / 1024.0, 1),
        proc_root=proc_root,
        podman_snapshot_port=lambda target: {"available": False, "reason": "test"},
    )

    assert systemd_calls == [("model.service", True)]
    assert snapshot["pids"]["alive"] == [123]
    assert snapshot["pids"]["sampled_processes"][0]["rss_mib"] == 2.0
    assert snapshot["systemd"]["memory_current"] == {"raw": "1048576", "mib": 1.0}


def test_cgroup_cpu_sample_reads_fake_cpu_stat(tmp_path: Path) -> None:
    cgroup = tmp_path / "user.slice" / "model.service"
    cgroup.mkdir(parents=True)
    (cgroup / "cpu.stat").write_text("usage_usec 1000\nuser_usec 700\nsystem_usec 300\n", encoding="utf-8")
    times = iter([10.0, 10.5])

    def fake_sleep(seconds: float) -> None:
        assert seconds == 0.5
        (cgroup / "cpu.stat").write_text("usage_usec 101000\nuser_usec 90000\nsystem_usec 11000\n", encoding="utf-8")

    sample = memory_adapters.cgroup_cpu_sample(
        "/user.slice/model.service",
        sample_sec=0.5,
        cgroup_root=tmp_path,
        sleep=fake_sleep,
        monotonic=lambda: next(times),
        cpu_count=lambda: 4,
    )

    assert sample["available"] is True
    assert sample["usage_delta_usec"] == 100000
    assert sample["cpu_cores"] == 0.2
    assert sample["cpu_percent_of_system"] == 5.0
    assert sample["idle"] is False


def test_llama_http_idle_ignores_stale_remaining_token_without_processing() -> None:
    def fake_http_json(url: str, timeout: float, max_bytes: int, method: str) -> dict[str, Any]:
        if url.endswith("/health"):
            return {"ok": True, "json": {"status": "ok"}, "elapsed_ms": 1.0}
        if url.endswith("/slots"):
            return {
                "ok": True,
                "json": [
                    {
                        "id": 0,
                        "is_processing": False,
                        "next_token": [{"has_next_token": False, "n_remain": 7, "n_decoded": 3}],
                    }
                ],
            }
        if url.endswith("/v1/models"):
            return {"ok": True, "json": {"data": [{"id": "model-a"}]}}
        raise AssertionError(url)

    idle = memory_adapters.llama_http_idle(
        {"available": True, "base_url": "http://127.0.0.1:8080"},
        http_json_port=fake_http_json,
    )

    assert idle["idle"] is True
    assert idle["slots"]["items"][0]["stale_n_remain_ignored"] is True
    assert idle["models"]["ids"] == ["model-a"]


def test_live_lock_acquire_blocks_duplicate_and_release_cleans_runtime_dir(tmp_path: Path) -> None:
    first = memory_adapters.live_lock_acquire(
        "candidate_model",
        "operator",
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: "2026-06-29T00:00:00Z",
        pid=lambda: 123,
        runtime_dir=tmp_path,
    )
    second = memory_adapters.live_lock_acquire(
        "candidate_model",
        "operator",
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: "2026-06-29T00:00:01Z",
        pid=lambda: 124,
        runtime_dir=tmp_path,
    )
    released = memory_adapters.live_lock_release(first, runtime_dir=tmp_path)

    assert first["acquired"] is True
    assert first["payload"]["pid"] == 123
    assert second["acquired"] is False
    assert second["reason"] == "live_executor_lock_exists"
    assert released == {"released": True, "path": first["path"]}
    assert not Path(first["path"]).exists()


def test_live_execute_command_routes_only_registered_executors() -> None:
    http = memory_adapters.live_execute_command(
        {"command_template": ["http_post_json", "http://127.0.0.1:5405/admin/unload?exit_process=true"]},
        60,
        http_json_port=lambda url, timeout, max_bytes, method: {
            "ok": True,
            "json": {"ok": True},
            "url": url,
            "timeout": timeout,
            "method": method,
        },
        monotonic=iter([1.0, 1.25]).__next__,
    )
    podman = memory_adapters.live_execute_command(
        {"command_template": ["podman", "restart", "model"]},
        60,
        runner=lambda command, timeout: {"ok": True, "returncode": 0, "stdout": "model\n", "stderr": ""},
        monotonic=iter([2.0, 2.1]).__next__,
    )
    rejected = memory_adapters.live_execute_command({"command_template": ["systemctl", "restart", "model.service"]}, 60)

    assert http["ok"] is True
    assert http["returncode"] == 0
    assert http["method"] == "POST"
    assert podman["command"] == ["podman", "restart", "model"]
    assert podman["elapsed_sec"] == 0.1
    assert rejected["error"] == "unsupported_live_executor_command"


def test_live_wait_rehydrate_stops_when_health_summary_ready() -> None:
    calls: list[str] = []

    result = memory_adapters.live_wait_rehydrate(
        {"id": "candidate_model"},
        30,
        target_snapshot=lambda candidate: {"target": candidate, "podman": {"container": {"pid": 555, "running": True}}},
        idle_probe=lambda candidate, snapshot, sample: {"registered": True, "idle": True, "status": "idle"},
        health_summary=lambda snapshot, idle: {
            "ready": True,
            "podman_running": True,
            "pid": 555,
            "http_health_ok": True,
            "idle": idle.get("idle"),
            "idle_status": idle.get("status"),
        },
        monotonic=iter([5.0, 5.25, 5.25]).__next__,
        sleep=lambda seconds: calls.append(f"unexpected:{seconds}"),
    )

    assert result["ok"] is True
    assert result["status"] == "ready"
    assert result["attempt_count"] == 1
    assert calls == []

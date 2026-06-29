from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from abyss_machine import storage_adapters


def test_storage_path_text_matches_preserves_deleted_and_absolute_path_behavior() -> None:
    assert storage_adapters.path_text_matches("/srv/abyss-machine/cache", "/srv/abyss-machine/cache/model.bin")
    assert storage_adapters.path_text_matches("/srv/abyss-machine/cache", "/srv/abyss-machine/cache/model.bin (deleted)")
    assert storage_adapters.path_text_matches("/tmp/cache", "python worker --cache /tmp/cache/run")
    assert not storage_adapters.path_text_matches("/srv/abyss-machine/cache", "")


def test_storage_process_path_usage_uses_fake_snapshot_and_fd_ports() -> None:
    snapshot_calls: list[tuple[int, float]] = []
    fd_calls: list[tuple[int, int]] = []

    def fake_snapshot(top: int, interval: float) -> dict[str, Any]:
        snapshot_calls.append((top, interval))
        return {
            "ok": True,
            "generated_at": "2026-06-29T00:00:00+00:00",
            "summary": {"processes": 3},
            "processes": [
                {
                    "pid": 101,
                    "ppid": 1,
                    "uid": 1000,
                    "name": "python",
                    "comm": "python",
                    "cmdline": "python build.py --cache /srv/abyss-machine/cache/model-a",
                    "cwd": "/workspace/project",
                    "exe": "/usr/bin/python3",
                    "cgroup": ["0::/user.slice"],
                    "workload_hint": "ai",
                    "vmrss_kib": 2048,
                    "cpu_system_percent": 12.5,
                },
                {
                    "pid": 202,
                    "ppid": 1,
                    "uid": 1000,
                    "name": "worker",
                    "comm": "worker",
                    "cmdline": "worker",
                    "cwd": "/tmp",
                    "exe": "/usr/bin/worker",
                    "cgroup": [],
                },
                {"pid": "not-int", "cmdline": "/srv/abyss-machine/cache/ignored"},
            ],
        }

    def fake_fd_targets(pid: int, limit: int) -> tuple[list[str], bool]:
        fd_calls.append((pid, limit))
        if pid == 101:
            return ["/tmp/unused"], False
        return ["/srv/abyss-machine/tmp/live-output (deleted)"], True

    document = storage_adapters.process_path_usage_document(
        paths=["", "/", "/srv/abyss-machine/cache", "/srv/abyss-machine/tmp"],
        process_snapshot=fake_snapshot,
        generated_at="2026-06-29T00:00:00+00:00",
        schema_prefix="abyss_machine",
        version="test",
        process_latest_path=Path("/var/lib/abyss-machine/processes/latest.json"),
        interval=0.25,
        top=5,
        fd_targets=fake_fd_targets,
    )

    by_path = {item["path"]: item for item in document["paths"]}
    assert snapshot_calls == [(30, 0.25)]
    assert fd_calls == [(101, 512), (202, 512)]
    assert document["summary"] == {"paths": 2, "active_paths": 2, "active_process_refs": 2}
    assert document["capture"]["fd_scan_errors"] == 1
    assert by_path["/srv/abyss-machine/cache"]["status"] == "blocked_active_process"
    assert by_path["/srv/abyss-machine/cache"]["match_sources"] == [{"pid": 101, "source": "cmdline"}]
    assert by_path["/srv/abyss-machine/tmp"]["match_sources"] == [{"pid": 202, "source": "fd"}]
    assert by_path["/srv/abyss-machine/tmp"]["active_processes"][0]["cmdline"] == "worker"

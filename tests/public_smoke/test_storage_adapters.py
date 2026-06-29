from __future__ import annotations

from pathlib import Path
import os
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


def test_storage_execute_cleanup_action_uses_fake_command_runner_and_euid() -> None:
    calls: list[tuple[list[str], float]] = []

    def runner(command: list[str], timeout: float) -> dict[str, Any]:
        calls.append((command, timeout))
        return {"ok": True, "argv": command, "timeout": timeout}

    blocked = storage_adapters.execute_cleanup_action(
        {"id": "var_cache_libdnf5", "action_type": "package_manager_clean", "path": "/var/cache/libdnf5"},
        age_days=7.0,
        abyss_machine_tmp_root=Path("/srv/abyss-machine/tmp"),
        command_runner=runner,
        euid=lambda: 1000,
    )
    assert blocked == {"ok": False, "blocked": True, "reason": "requires_root_pkexec"}
    assert calls == []

    cleaned = storage_adapters.execute_cleanup_action(
        {"id": "var_cache_libdnf5", "action_type": "package_manager_clean", "path": "/var/cache/libdnf5"},
        age_days=7.0,
        abyss_machine_tmp_root=Path("/srv/abyss-machine/tmp"),
        command_runner=runner,
        euid=lambda: 0,
    )
    assert cleaned["ok"] is True
    assert cleaned["command"] == ["dnf5", "clean", "all"]
    assert calls == [(["dnf5", "clean", "all"], 120.0)]


def test_storage_execute_cleanup_action_keeps_npm_verify_as_cleanup_gate() -> None:
    calls: list[list[str]] = []

    def runner(command: list[str], timeout: float) -> dict[str, Any]:
        _ = timeout
        calls.append(command)
        return {"ok": command != ["npm", "cache", "verify"], "argv": command}

    result = storage_adapters.execute_cleanup_action(
        {"id": "home_npm_cache", "action_type": "rebuildable_cache_pressure_valve", "path": "/home/user/.npm"},
        age_days=7.0,
        abyss_machine_tmp_root=Path("/srv/abyss-machine/tmp"),
        command_runner=runner,
    )
    assert result["ok"] is False
    assert result["commands"][1] == {"ok": False, "skipped": True, "reason": "npm cache verify failed"}
    assert calls == [["npm", "cache", "verify"]]


def test_storage_execute_cleanup_action_removes_only_old_generated_tmp_files(tmp_path: Path) -> None:
    tmp_root = tmp_path / "abyss-tmp"
    target = tmp_root / "cleanup"
    target.mkdir(parents=True)
    old_file = target / "old.txt"
    old_file.write_text("old", encoding="utf-8")
    fresh_file = target / "fresh.txt"
    fresh_file.write_text("fresh", encoding="utf-8")
    old_empty_dir = target / "old-empty"
    old_empty_dir.mkdir()
    symlink = target / "old-link"
    symlink.symlink_to(old_file)

    now = 2_000_000.0
    old_time = now - (10 * 86400.0)
    os.utime(old_file, (old_time, old_time))
    os.utime(old_empty_dir, (old_time, old_time))
    os.utime(fresh_file, (now, now))

    result = storage_adapters.execute_cleanup_action(
        {"id": "tmp_cleanup", "action_type": "age_based_generated_temp_cleanup", "path": str(target)},
        age_days=7.0,
        abyss_machine_tmp_root=tmp_root,
        command_runner=lambda command, timeout: {"ok": False, "unexpected": [list(command), timeout]},
        clock=lambda: now,
    )

    assert result["ok"] is True
    assert result["removed_file_count"] == 1
    assert result["removed_dir_count"] == 1
    assert str(old_file) in result["removed_files"]
    assert str(old_empty_dir) in result["removed_dirs"]
    assert not old_file.exists()
    assert fresh_file.exists()
    assert symlink.is_symlink()


def test_storage_execute_cleanup_action_blocks_unallowlisted_actions() -> None:
    result = storage_adapters.execute_cleanup_action(
        {"id": "unknown", "action_type": "delete_everything", "path": "/srv/abyss-machine/tmp"},
        age_days=7.0,
        abyss_machine_tmp_root=Path("/srv/abyss-machine/tmp"),
        command_runner=lambda command, timeout: {"ok": False, "unexpected": [list(command), timeout]},
    )
    assert result == {"ok": False, "blocked": True, "reason": "manual_review_only_or_not_allowlisted"}

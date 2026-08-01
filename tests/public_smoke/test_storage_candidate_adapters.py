from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
import subprocess

from abyss_machine import storage_candidate_adapters as adapters
from abyss_machine import storage_candidate_contracts as contracts


def test_physical_size_uses_du_blocks_not_apparent_bytes(tmp_path: Path) -> None:
    sparse = tmp_path / "sparse.bin"
    with sparse.open("wb") as handle:
        handle.seek((128 * 1024 * 1024) - 1)
        handle.write(b"\0")

    physical, evidence = adapters.physical_size_bytes(sparse)

    assert evidence["ok"] is True
    assert evidence["physical"] is True
    assert physical is not None
    assert physical < sparse.stat().st_size


def test_physical_size_command_is_explicit_and_cross_filesystem_bounded(tmp_path: Path) -> None:
    target = tmp_path / "cache"
    target.mkdir()
    calls: list[tuple[list[str], float]] = []

    def runner(command, timeout):
        calls.append((list(command), timeout))
        return {"ok": True, "stdout": f"4096\t{target}\n", "stderr": ""}

    physical, evidence = adapters.physical_size_bytes(target, timeout=3.0, runner=runner)

    assert physical == 4096
    assert evidence["method"] == "du -sx -B1"
    assert calls == [(["du", "-sx", "-B1", "--", str(target)], 3.0)]


def test_filesystem_fingerprint_changes_and_truncation_is_not_complete(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    root.mkdir()
    (root / "a.txt").write_text("a", encoding="utf-8")
    first = adapters.filesystem_fingerprint(root, max_entries=100)
    (root / "b.txt").write_text("b", encoding="utf-8")
    second = adapters.filesystem_fingerprint(root, max_entries=100)
    truncated = adapters.filesystem_fingerprint(root, max_entries=1)

    assert first["complete"] is True
    assert second["complete"] is True
    assert first["digest"] != second["digest"]
    assert truncated["complete"] is False
    assert truncated["truncated"] is True


def test_process_reference_scan_checks_all_fixture_pids_and_exact_ancestry(tmp_path: Path) -> None:
    target = tmp_path / "candidate"
    target.mkdir()
    proc_root = tmp_path / "proc"
    pid_root = proc_root / "123"
    (pid_root / "fd").mkdir(parents=True)
    (pid_root / "cwd").symlink_to(target, target_is_directory=True)
    (pid_root / "maps").write_text("", encoding="utf-8")
    (pid_root / "cmdline").write_bytes(b"fixture\0worker\0")

    result = adapters.process_references([str(target), str(tmp_path / "other")], proc_root=proc_root)

    assert result[str(target)]["checked"] is True
    assert result[str(target)]["active"] is True
    assert result[str(target)]["refs"][0]["pid"] == 123
    assert result[str(tmp_path / "other")]["active"] is False


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def test_git_adapter_distinguishes_clean_linked_worktree_from_dirty_unique_data(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _git("init", cwd=source)
    _git("config", "user.name", "Fixture", cwd=source)
    _git("config", "user.email", "fixture@example.invalid", cwd=source)
    (source / "tracked.txt").write_text("tracked", encoding="utf-8")
    _git("add", "tracked.txt", cwd=source)
    _git("commit", "-m", "fixture", cwd=source)
    worktree = tmp_path / "linked"
    _git("worktree", "add", "-b", "fixture-worktree", str(worktree), cwd=source)

    clean = adapters.git_worktree_evidence(worktree)
    (worktree / "unique.patch").write_text("patch", encoding="utf-8")
    dirty = adapters.git_worktree_evidence(worktree)

    assert clean["linked_worktree"] is True
    assert clean["unique_data"]["status"] == "clear"
    assert clean["recovery"]["verified"] is True
    assert clean["executor"]["type"] == "git_worktree_remove"
    assert dirty["unique_data"]["status"] == "present"
    assert any("unique.patch" in line for line in dirty["status_lines"])


def test_podman_verbose_parser_uses_unique_image_bytes_and_never_assumes_volume_data_is_disposable() -> None:
    payload = """Images space usage:

REPOSITORY                 TAG      IMAGE ID      CREATED     SIZE      SHARED SIZE  UNIQUE SIZE  CONTAINERS
localhost/example          latest   abcdef123456  3 days      173.2MB   173.2MB      10.33kB      0
<none>                     <none>   deadbeef1234  6 days      123.4MB   123.4MB      8.376kB      0

Local Volumes space usage:

VOLUME NAME       LINKS       SIZE
unused-volume     0           51.86MB
"""

    parsed = adapters.parse_podman_df_verbose(payload)
    specs = adapters.podman_specs(payload)

    assert parsed["images"][0]["unique_bytes"] == 10_330
    tagged = next(item for item in specs if item["path"] == "podman://image/abcdef123456")
    dangling = next(item for item in specs if item["path"] == "podman://image/deadbeef1234")
    volume = next(item for item in specs if item["path"] == "podman://volume/unused-volume")
    assert tagged["reclaimable_bytes"] == 10_330
    assert tagged["recovery"]["verified"] is True
    assert dangling["unique_data"]["status"] == "unknown"
    assert volume["unique_data"]["status"] == "unknown"
    assert volume["unique_data"]["archivable"] is True


def test_aoa_adapter_consumes_owner_safe_to_remove_verdict_without_reclassifying_raw_data() -> None:
    document = {
        "status": "blocked_raw_authority_unresolved",
        "lock_active": False,
        "session_projection_stages": {
            "status": "blocked_raw_authority_unresolved",
            "entries": [
                {
                    "path": "/srv/AbyssOS/.aoa/sessions/.stage",
                    "status": "orphaned_raw_authority_unresolved",
                    "safe_to_remove": False,
                    "size_bytes": 5_000_000_000,
                    "raw_authority": {"verified": False},
                }
            ],
        },
    }

    spec = adapters.aoa_specs(document)[0]

    assert spec["owner_verdict"]["authoritative"] is True
    assert spec["owner_verdict"]["safe_to_remove"] is False
    assert spec["reclaimable_bytes"] == 0
    assert spec["unique_data"]["status"] == "unknown"


def test_backup_lane_coverage_is_not_fresh_when_candidate_changed_after_success(tmp_path: Path) -> None:
    candidate = tmp_path / "cache" / "model"
    candidate.mkdir(parents=True)
    lane = {
        "lane": "heavy",
        "status": "ok",
        "finished_at": "2026-06-12T21:00:16+00:00",
        "results": [
            {
                "source": str(tmp_path / "cache"),
                "destination": "/abyss/Backups/heavy/latest/cache",
                "status": "ok",
            }
        ],
    }

    backup, restore = adapters.backup_evidence_for_path(
        candidate,
        lane_documents=[("heavy/latest-success.json", lane)],
        candidate_mtime="2026-07-20T00:00:00+00:00",
        archive_manifest={
            "digest_match": True,
            "restore_verified": True,
            "restore_command": "restore fixture",
        },
    )

    assert backup["fresh"] is False
    assert backup["digest_match"] is True
    assert backup["status"] == "covered_but_stale_or_digest_unverified"
    assert restore["verified"] is True


def test_light_observation_cannot_become_delete_ready_without_deep_reference_checks(tmp_path: Path) -> None:
    candidate = tmp_path / "cache"
    candidate.mkdir()
    (candidate / "file").write_text("data", encoding="utf-8")
    spec = {
        "path": str(candidate),
        "owner": "abyss-machine",
        "kind": "generated_tmp",
        "source_id": "fixture",
        "source_adapter": "fixture",
        "executor": {"type": "age_bounded_tmp_cleanup", "owner_specific": True},
        "unique_data": {"status": "clear"},
        "recovery": {"verified": True, "command": "rebuild fixture"},
        "replacement": {"verified": False},
    }
    observation = adapters.collect_observation(
        spec,
        protection={"decision": "allow_candidate"},
        process_refs={"checked": True, "active": False, "refs": []},
        claims=[],
        runtime_documents=[],
        lane_documents=[],
        deep=False,
        generated_at="2026-08-01T16:00:00+00:00",
        max_fingerprint_entries=100,
    )
    record = contracts.candidate_record(
        observation,
        configured_policy={
            "by_kind": {"generated_tmp": {"minimum_observations": 1, "quiet_seconds": 0}}
        },
        now_time=dt.datetime(2026, 8, 1, 16, 0, tzinfo=dt.timezone.utc),
    )

    assert record["verdict"] == "blocked_unknown"
    codes = {item["code"] for item in record["blockers"]}
    assert "mount_refs_not_checked" in codes
    assert "runtime_refs_not_checked" in codes

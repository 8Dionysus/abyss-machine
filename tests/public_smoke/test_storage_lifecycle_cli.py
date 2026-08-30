from __future__ import annotations

import json
from pathlib import Path

from abyss_machine import cli


ROOT = Path(__file__).resolve().parents[2]


def _run(capsys, *args: str) -> tuple[int, dict]:
    returncode = cli.main(["storage", "lifecycle", *args, "--json"])
    captured = capsys.readouterr()
    return returncode, json.loads(captured.out)


def test_storage_lifecycle_cli_open_seal_release_and_status(monkeypatch, capsys, tmp_path: Path) -> None:
    state = tmp_path / "state"
    monkeypatch.setattr(cli, "STORAGE_LIFECYCLE_ROOT", state)
    workspace = tmp_path / "work" / "job"
    returncode, opened = _run(capsys, "open", "--owner", "fixture", "--workspace", str(workspace))
    assert returncode == 0
    (workspace / "derived").write_text("payload", encoding="utf-8")
    returncode, sealed = _run(
        capsys,
        "seal",
        "--workspace-id", opened["record"]["workspace_id"],
        "--lease-token", opened["lease_token"],
    )
    assert returncode == 0
    assert sealed["record"]["state"] == "sealed"
    returncode, released = _run(
        capsys,
        "release",
        "--workspace-id", opened["record"]["workspace_id"],
        "--decision", "DELETE",
        "--grace-seconds", "0",
    )
    assert returncode == 0
    assert released["record"]["state"] == "released"
    returncode, status = _run(capsys, "status")
    assert returncode == 0
    assert status["counts"]["released"] == 1
    assert status["bytes"]["sealed_reclaimable_bytes"] > 0


def test_lifecycle_reaper_timer_is_core_and_bounded() -> None:
    service = (ROOT / "systemd" / "user" / "abyss-storage-lifecycle-reaper.service").read_text(encoding="utf-8")
    timer = (ROOT / "systemd" / "user" / "abyss-storage-lifecycle-reaper.timer").read_text(encoding="utf-8")
    bootstrap = (ROOT / "scripts" / "abyss-machine-bootstrap").read_text(encoding="utf-8")
    assert "storage lifecycle reap --limit 1 --json" in service
    assert "OnUnitInactiveSec=5min" in timer
    assert '"abyss-storage-lifecycle-reaper.timer"' in bootstrap

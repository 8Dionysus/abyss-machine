from __future__ import annotations

import hashlib
import json
from pathlib import Path

from abyss_machine import cli
from abyss_machine import storage_lifecycle_adapters


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


def test_storage_lifecycle_cli_prefixes_generated_token_before_open_seal(monkeypatch, capsys, tmp_path: Path) -> None:
    state = tmp_path / "state"
    monkeypatch.setattr(cli, "STORAGE_LIFECYCLE_ROOT", state)
    monkeypatch.setattr(storage_lifecycle_adapters.secrets, "token_urlsafe", lambda _bytes: "-")
    workspace = tmp_path / "work" / "job"

    returncode, opened = _run(capsys, "open", "--owner", "fixture", "--workspace", str(workspace))
    assert returncode == 0
    assert opened["lease_token"] == "lease--"
    assert opened["record"]["lease"]["token_sha256"] == hashlib.sha256(b"lease--").hexdigest()

    (workspace / "derived").write_text("payload", encoding="utf-8")
    returncode, sealed = _run(
        capsys,
        "seal",
        "--workspace-id", opened["record"]["workspace_id"],
        "--lease-token", opened["lease_token"],
    )
    assert returncode == 0
    assert sealed["record"]["state"] == "sealed"


def test_storage_lifecycle_preserves_validation_for_legacy_token(tmp_path: Path) -> None:
    root = tmp_path / "state"
    workspace = tmp_path / "work" / "job"
    opened = storage_lifecycle_adapters.register_workspace(root, owner="fixture", workspace=workspace, unit=None)
    legacy_token = "-legacy-token"
    record_path = storage_lifecycle_adapters.record_path(root, opened["record"]["workspace_id"])
    record = storage_lifecycle_adapters.read_json(record_path)
    assert record is not None
    record["lease"]["token_sha256"] = hashlib.sha256(legacy_token.encode()).hexdigest()
    storage_lifecycle_adapters.atomic_write_json(record_path, record)
    (workspace / "derived").write_text("payload", encoding="utf-8")

    sealed = storage_lifecycle_adapters.seal_registered_workspace(
        root,
        workspace_id=opened["record"]["workspace_id"],
        lease_token=legacy_token,
    )
    assert sealed["ok"] is True
    assert sealed["record"]["state"] == "sealed"


def test_storage_lifecycle_cli_reap_passes_mutation_and_scan_bounds(monkeypatch, capsys, tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(cli, "STORAGE_LIFECYCLE_ROOT", tmp_path / "state")

    def fake_reap(root: Path, *, limit: int, scan_limit: int) -> dict[str, object]:
        captured.update({"root": root, "limit": limit, "scan_limit": scan_limit})
        return {"schema": "abyss_machine_storage_workspace_reap_v1", "ok": True, "summary": {}}

    monkeypatch.setattr(cli.storage_lifecycle_adapters, "reap", fake_reap)
    returncode, _ = _run(capsys, "reap", "--limit", "1", "--scan-limit", "2")

    assert returncode == 0
    assert captured == {"root": tmp_path / "state", "limit": 1, "scan_limit": 2}


def test_lifecycle_reaper_timer_is_core_and_bounded() -> None:
    service = (ROOT / "systemd" / "user" / "abyss-storage-lifecycle-reaper.service").read_text(encoding="utf-8")
    timer = (ROOT / "systemd" / "user" / "abyss-storage-lifecycle-reaper.timer").read_text(encoding="utf-8")
    bootstrap = (ROOT / "scripts" / "abyss-machine-bootstrap").read_text(encoding="utf-8")
    assert "storage lifecycle reap --limit 1 --scan-limit 8 --json" in service
    assert "OnUnitInactiveSec=5min" in timer
    assert '"abyss-storage-lifecycle-reaper.timer"' in bootstrap

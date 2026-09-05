from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def _run(state_root: Path, *args: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["ABYSS_MACHINE_STORAGE_CANDIDATES_ROOT"] = str(state_root / "storage" / "candidates")
    completed = subprocess.run(
        [sys.executable, "-m", "abyss_machine.cli", "storage", "candidates", *args, "--json"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    return completed, json.loads(completed.stdout)


def test_candidate_cli_light_refresh_register_claim_and_release(tmp_path: Path) -> None:
    completed, refresh = _run(tmp_path, "refresh")
    assert completed.returncode == 0, completed.stderr
    assert refresh["deep"] is False
    assert refresh["light_refresh"]["needs_deep_seed"] is True

    subject = tmp_path / "subject"
    subject.mkdir()
    completed, registration = _run(
        tmp_path,
        "register",
        "--path", str(subject),
        "--owner", "fixture-owner",
        "--kind", "generated_tmp",
        "--purpose", "fixture",
        "--producer", "pytest",
        "--source-id", "fixture-1",
        "--recovery-command", "fixture rebuild",
    )
    assert completed.returncode == 0, completed.stderr
    candidate_id = registration["manifest"]["candidate_id"]
    assert Path(registration["manifest_path"]).exists()

    completed, claim = _run(
        tmp_path,
        "claim",
        "--claim-id", "fixture-claim",
        "--candidate-id", candidate_id,
        "--owner", "fixture-session",
        "--purpose", "test active work",
        "--ttl-seconds", "600",
    )
    assert completed.returncode == 0, completed.stderr
    assert claim["claim"]["absence_or_expiry_is_not_delete_permission"] is True

    completed, release = _run(tmp_path, "release", "--claim-id", "fixture-claim")
    assert completed.returncode == 0, completed.stderr
    assert release["release_is_not_delete_permission"] is True

    completed, second_refresh = _run(tmp_path, "refresh")
    assert completed.returncode == 0, completed.stderr
    assert second_refresh["summary"]["changed"] == 0
    assert second_refresh["light_refresh"]["pending_manifest_candidate_ids"] == [candidate_id]


def test_bounded_deep_timer_is_installed_by_core_profile() -> None:
    service = (ROOT / "systemd" / "user" / "abyss-storage-candidates-deep.service").read_text(encoding="utf-8")
    timer = (ROOT / "systemd" / "user" / "abyss-storage-candidates-deep.timer").read_text(encoding="utf-8")
    bootstrap = (ROOT / "scripts" / "abyss-machine-bootstrap").read_text(encoding="utf-8")

    assert "storage candidates refresh --deep --if-due --json" in service
    assert "TimeoutStartSec=6min" in service
    assert "OnCalendar=*:0/10" in timer
    assert '"abyss-storage-candidates-deep.timer"' in bootstrap

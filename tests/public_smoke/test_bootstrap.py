from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = ROOT / "scripts" / "abyss-machine-bootstrap"


def run_bootstrap(*args: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(BOOTSTRAP), *args, "--json"],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr[-1000:]
    payload = json.loads(result.stdout)
    assert payload["schema"] == "abyss_machine_bootstrap_v1"
    assert payload["ok"] is True
    return payload


def test_bootstrap_doctor_dry_run() -> None:
    payload = run_bootstrap("doctor", "--dry-run")
    assert payload["checks"]["cli_source_exists"] is True
    assert payload["checks"]["etc_templates_exist"] is True


def test_bootstrap_render_dry_run_uses_render_actions() -> None:
    payload = run_bootstrap("render", "--profile", "linux-systemd-core", "--dry-run")
    assert payload["dry_run"] is True
    assert any(action["action"] == "render" for action in payload["actions"])


def test_typing_profile_is_opt_in() -> None:
    payload = run_bootstrap("enable-profile", "--profile", "typing-intake", "--dry-run")
    units = {action["unit"] for action in payload["actions"]}
    assert "abyss-machine-typing-atspi-text-events.service" in units
    assert payload["dry_run"] is True

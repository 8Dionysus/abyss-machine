from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts" / "validators" / "first_run_installed_projection.py"


def run_validator(tmp_path: Path) -> dict:
    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--tmp-root",
            str(tmp_path),
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr[-1000:]
    payload = json.loads(result.stdout)
    assert payload["schema"] == "abyss_machine_first_run_installed_projection_v1"
    assert payload["ok"] is True
    return payload


@pytest.fixture(scope="module")
def projection_payload(tmp_path_factory: pytest.TempPathFactory) -> dict:
    return run_validator(tmp_path_factory.mktemp("first-run-projection"))


def test_first_run_projection_report_is_machine_readable(projection_payload: dict) -> None:
    payload = projection_payload
    assert payload["bootstrap"]["command"] == "install"
    assert payload["bootstrap"]["dry_run"] is False
    assert payload["roots"]["status"] == "ok"
    assert payload["package_projection"]["status"] == "ok"
    assert payload["module_import"]["status"] == "ok"
    assert payload["module_import"]["uses_source_checkout"] is False


def test_first_run_projection_keeps_cli_surfaces_in_parity(projection_payload: dict) -> None:
    payload = projection_payload
    assert payload["source_cli"]["surfaces"]["top-level"] == payload["temp_installed_cli"]["surfaces"]["top-level"]
    assert payload["source_cli"]["surfaces"]["artifacts"] == payload["temp_installed_cli"]["surfaces"]["artifacts"]
    assert payload["source_cli"]["surfaces"]["typing"] == payload["temp_installed_cli"]["surfaces"]["typing"]
    assert payload["source_cli"]["surfaces"]["nervous"] == payload["temp_installed_cli"]["surfaces"]["nervous"]
    assert payload["host_installed_cli"]["status"] in {"ok", "unavailable", "failed"}
    assert payload["host_installed_cli"].get("required") is False


def test_typing_nervous_bootstrap_proof_is_opt_in(projection_payload: dict) -> None:
    payload = projection_payload
    proof = payload["typing_nervous"]
    assert proof["status"] == "ok"
    assert proof["collector_activation"] == "not_performed"
    assert proof["raw_text_or_browser_capture"] == "not_collected"
    typing_units = proof["enable_profile_dry_runs"]["typing-intake"]["units"]
    nervous_units = proof["enable_profile_dry_runs"]["nervous-local"]["units"]
    assert "abyss-machine-typing-nervous-refresh.timer" in typing_units
    assert "abyss-nervous-browser-content-capture.timer" in nervous_units

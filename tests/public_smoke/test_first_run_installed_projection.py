from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts" / "validators" / "first_run_installed_projection.py"


def load_validator_module():
    spec = importlib.util.spec_from_file_location("first_run_installed_projection_under_test", VALIDATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(VALIDATOR.parent))
    spec.loader.exec_module(module)
    return module


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
        timeout=120,
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
    assert payload["temp_installed_content_parity"]["status"] == "ok"
    assert payload["temp_installed_content_parity"]["failures"] == []
    assert payload["module_import"]["status"] == "ok"
    assert payload["module_import"]["uses_source_checkout"] is False
    assert payload["portability_scan"]["status"] == "ok"
    assert payload["portability_scan"]["findings"] == []


def test_content_parity_report_detects_installed_cli_digest_drift(tmp_path: Path) -> None:
    module = load_validator_module()
    libexec = tmp_path / "libexec"
    share_root = tmp_path / "share" / "abyss-machine"
    libexec.mkdir(parents=True)
    shutil.copy2(ROOT / "src" / "abyss_machine" / "cli.py", libexec / "abyss-machine")
    shutil.copytree(ROOT / "src" / "abyss_machine", libexec / "abyss_machine")
    shutil.copytree(ROOT / "manifests", share_root / "manifests")
    shutil.copytree(ROOT / "generated", share_root / "generated")
    with (libexec / "abyss-machine").open("a", encoding="utf-8") as handle:
        handle.write("\n# installed drift fixture\n")

    report = module.content_parity_report(
        label="fixture-installed",
        installed_cli=libexec / "abyss-machine",
        installed_package_root=libexec / "abyss_machine",
        installed_share_root=share_root,
    )

    assert report["status"] == "failed"
    assert report["cli"]["status"] == "digest_mismatch"
    assert any("fixture-installed CLI digest mismatch" in failure for failure in report["failures"])


def test_first_run_projection_keeps_cli_surfaces_in_parity(projection_payload: dict) -> None:
    payload = projection_payload
    assert payload["source_cli"]["surfaces"]["top-level"] == payload["temp_installed_cli"]["surfaces"]["top-level"]
    assert payload["source_cli"]["surfaces"]["artifacts"] == payload["temp_installed_cli"]["surfaces"]["artifacts"]
    assert payload["source_cli"]["surfaces"]["typing"] == payload["temp_installed_cli"]["surfaces"]["typing"]
    assert payload["source_cli"]["surfaces"]["nervous"] == payload["temp_installed_cli"]["surfaces"]["nervous"]
    assert payload["host_installed_cli"]["status"] in {"ok", "unavailable", "failed", "skipped"}
    assert payload["host_installed_cli"].get("required") is False


def test_first_run_projection_checks_artifact_trust_option_surfaces(projection_payload: dict) -> None:
    payload = projection_payload
    source_options = payload["source_critical_help_options"]["commands"]
    installed_options = payload["temp_installed_critical_help_options"]["commands"]
    for report in (payload["source_critical_help_options"], payload["temp_installed_critical_help_options"]):
        assert report["status"] == "ok"
        assert report["failures"] == []

    materialize_required = {
        "--registry-dir",
        "--consumer-intent",
        "--source-repo",
        "--trust-root-mode",
        "--record-id",
        "--allow-non-latest",
        "--json",
    }
    for commands in (source_options, installed_options):
        materialize = commands["artifacts materialize-subjects"]
        trust_gate = commands["artifacts trust-gate"]
        trust_coverage = commands["artifacts trust-coverage"]
        registry_latest = commands["artifacts registry-latest"]
        scenarios = commands["artifacts scenarios"]
        update_verify = commands["artifacts update-verify"]
        update_repo_verify = commands["artifacts update-repo-verify"]
        scitt_verify = commands["artifacts scitt-verify"]
        oci_verify = commands["artifacts oci-verify"]
        assert set(materialize["required_options"]) == materialize_required
        assert materialize["missing_options"] == []
        assert trust_gate["missing_options"] == []
        assert "--durable-only" in trust_coverage["required_options"]
        assert trust_coverage["missing_options"] == []
        assert "--consumer-intent" in registry_latest["required_options"]
        assert registry_latest["missing_options"] == []
        assert "--scenario-id" in scenarios["required_options"]
        assert "--artifact-class" in scenarios["required_options"]
        assert scenarios["missing_options"] == []
        assert "--require-trust-gate" in update_verify["required_options"]
        assert "--registry-dir" in update_verify["required_options"]
        assert "--subject-digest" in update_verify["required_options"]
        assert update_verify["missing_options"] == []
        assert "--target-path" in update_repo_verify["required_options"]
        assert "--artifact-class" in update_repo_verify["required_options"]
        assert "--target-digest" in update_repo_verify["required_options"]
        assert "--require-trust-gate" in update_repo_verify["required_options"]
        assert update_repo_verify["missing_options"] == []
        assert "--receipt" in scitt_verify["required_options"]
        assert "--external-relying-party" in scitt_verify["required_options"]
        assert "--statement-class" in scitt_verify["required_options"]
        assert "--artifact-digest" in scitt_verify["required_options"]
        assert "--transparency-service" in scitt_verify["required_options"]
        assert scitt_verify["missing_options"] == []
        assert "--required-referrer-type" in oci_verify["required_options"]
        assert "--require-trust-gate" in oci_verify["required_options"]
        assert oci_verify["missing_options"] == []


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

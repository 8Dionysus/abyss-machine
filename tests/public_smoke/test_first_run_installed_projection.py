from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts" / "validators" / "first_run_installed_projection.py"
VALIDATOR_TIMEOUT_SEC = 300


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
        timeout=VALIDATOR_TIMEOUT_SEC,
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


def test_command_result_reports_timeout_without_raising(tmp_path: Path) -> None:
    module = load_validator_module()

    result = module.command_result(
        [sys.executable, "-c", "import time; time.sleep(1)"],
        cwd=tmp_path,
        env={},
        timeout=0.05,
    )

    assert result["returncode"] == 124
    assert result["timed_out"] is True
    assert "timed out" in result["stderr"]


def test_optional_host_installed_report_skips_heavy_critical_checks(tmp_path: Path) -> None:
    module = load_validator_module()
    host_cli = tmp_path / "abyss-machine"
    host_cli.write_text(
        "#!/usr/bin/env python3\n"
        "print('usage: abyss-machine {doctor,storage,resource,ai,artifacts,nervous,typing,dictation} ...')\n",
        encoding="utf-8",
    )
    host_cli.chmod(0o755)
    paths = module.projection_paths(tmp_path / "projection")
    paths["home"].mkdir(parents=True, exist_ok=True)
    args = SimpleNamespace(
        host_cli=str(host_cli),
        host_libexec_dir=str(tmp_path / "libexec"),
        host_share_root=str(tmp_path / "share"),
        require_host_installed=False,
        host_advisory_timeout=0.1,
    )

    report = module.host_installed_report(args, paths)

    assert report["required"] is False
    assert report["critical_help_options"]["status"] == "skipped"
    assert report["mode"] == "skipped_non_required_host_installed_projection"


def test_first_run_projection_keeps_cli_surfaces_in_parity(projection_payload: dict) -> None:
    payload = projection_payload
    assert payload["source_cli"]["surfaces"]["top-level"] == payload["temp_installed_cli"]["surfaces"]["top-level"]
    assert payload["source_cli"]["surfaces"]["artifacts"] == payload["temp_installed_cli"]["surfaces"]["artifacts"]
    assert payload["source_cli"]["surfaces"]["changes"] == payload["temp_installed_cli"]["surfaces"]["changes"]
    assert payload["source_cli"]["surfaces"]["docs"] == payload["temp_installed_cli"]["surfaces"]["docs"]
    assert payload["source_cli"]["surfaces"]["topology"] == payload["temp_installed_cli"]["surfaces"]["topology"]
    assert payload["source_cli"]["surfaces"]["graph"] == payload["temp_installed_cli"]["surfaces"]["graph"]
    assert payload["source_cli"]["surfaces"]["maps"] == payload["temp_installed_cli"]["surfaces"]["maps"]
    assert payload["source_cli"]["surfaces"]["rag"] == payload["temp_installed_cli"]["surfaces"]["rag"]
    assert payload["source_cli"]["surfaces"]["stack-bridge"] == payload["temp_installed_cli"]["surfaces"]["stack-bridge"]
    assert payload["source_cli"]["surfaces"]["storage"] == payload["temp_installed_cli"]["surfaces"]["storage"]
    assert payload["source_cli"]["surfaces"]["typing"] == payload["temp_installed_cli"]["surfaces"]["typing"]
    assert payload["source_cli"]["surfaces"]["nervous"] == payload["temp_installed_cli"]["surfaces"]["nervous"]
    assert payload["source_cli"]["surfaces"]["resource"] == payload["temp_installed_cli"]["surfaces"]["resource"]
    assert payload["source_cli"]["surfaces"]["mode"] == payload["temp_installed_cli"]["surfaces"]["mode"]
    assert payload["source_cli"]["surfaces"]["observability"] == payload["temp_installed_cli"]["surfaces"]["observability"]
    assert payload["source_cli"]["surfaces"]["cooling"] == payload["temp_installed_cli"]["surfaces"]["cooling"]
    assert payload["source_cli"]["surfaces"]["processes"] == payload["temp_installed_cli"]["surfaces"]["processes"]
    assert payload["source_cli"]["surfaces"]["heartbeats"] == payload["temp_installed_cli"]["surfaces"]["heartbeats"]
    assert payload["source_cli"]["surfaces"]["reactions"] == payload["temp_installed_cli"]["surfaces"]["reactions"]
    assert payload["source_cli"]["surfaces"]["responses"] == payload["temp_installed_cli"]["surfaces"]["responses"]
    assert payload["source_cli"]["surfaces"]["ai"] == payload["temp_installed_cli"]["surfaces"]["ai"]
    assert payload["source_cli"]["surfaces"]["ai cpu"] == payload["temp_installed_cli"]["surfaces"]["ai cpu"]
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


def test_first_run_projection_checks_resource_and_synthesis_option_surfaces(projection_payload: dict) -> None:
    payload = projection_payload
    for report in (payload["source_critical_help_options"], payload["temp_installed_critical_help_options"]):
        commands = report["commands"]
        synthesis = commands["nervous synthesis-build"]
        semantic_build = commands["nervous semantic-build"]
        semantic_maintain = commands["nervous semantic-maintain"]
        semantic_search = commands["nervous semantic-search"]
        resource_plan = commands["resource plan"]
        resource_launch = commands["resource launch"]
        ai_cpu_route = commands["ai cpu route"]

        assert "--scope" in synthesis["required_options"]
        assert "--date" in synthesis["required_options"]
        assert "--hour" in synthesis["required_options"]
        assert synthesis["missing_options"] == []

        assert "--batch-size" in semantic_build["required_options"]
        assert "--rebuild" in semantic_build["required_options"]
        assert semantic_build["missing_options"] == []

        assert "--dry-run" in semantic_maintain["required_options"]
        assert "--refresh-index-first" in semantic_maintain["required_options"]
        assert "--no-refresh-index-first" in semantic_maintain["required_options"]
        assert semantic_maintain["missing_options"] == []

        assert "--query" in semantic_search["required_options"]
        assert "--no-dedupe" in semantic_search["required_options"]
        assert "--force" in semantic_search["required_options"]
        assert semantic_search["missing_options"] == []

        assert "--no-thermal-sample" in resource_plan["required_options"]
        assert "--bytes" in resource_plan["required_options"]
        assert resource_plan["missing_options"] == []

        assert "--dry-run" in resource_launch["required_options"]
        assert "--success-on-block" in resource_launch["required_options"]
        assert "--timeout" in resource_launch["required_options"]
        assert resource_launch["missing_options"] == []

        assert "--class" in ai_cpu_route["required_options"]
        assert "--latency" in ai_cpu_route["required_options"]
        assert "--force" in ai_cpu_route["required_options"]
        assert ai_cpu_route["missing_options"] == []


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

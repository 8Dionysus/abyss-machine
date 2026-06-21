from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = ROOT / "scripts" / "abyss-machine-bootstrap"


def run_bootstrap(*args: str, env: dict[str, str] | None = None) -> dict:
    result = subprocess.run(
        [sys.executable, str(BOOTSTRAP), *args, "--json"],
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, **(env or {})},
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
    assert payload["checks"]["package_source_exists"] is True
    assert payload["checks"]["config_templates_exist"] is True
    assert payload["checks"]["systemd_templates_exist"] is True
    assert payload["checks"]["artifact_policy_exists"] is True
    assert payload["checks"]["contract_abi_exists"] is True


def test_bootstrap_render_dry_run_uses_render_actions() -> None:
    payload = run_bootstrap("render", "--profile", "linux-systemd-core", "--dry-run")
    assert payload["dry_run"] is True
    assert any(action["action"] == "render" for action in payload["actions"])


def test_bootstrap_install_derives_user_systemd_dir_from_explicit_home_under_root_env(tmp_path: Path) -> None:
    home = tmp_path / "home" / "agent"
    payload = run_bootstrap(
        "install",
        "--profile",
        "linux-systemd-core",
        "--dry-run",
        "--user",
        "agent",
        "--home",
        str(home),
        env={"USER": "root", "HOME": "/root"},
    )
    user_targets = [
        action["target"]
        for action in payload["actions"]
        if action.get("action") == "render" and "/systemd/user/" in action.get("source", "")
    ]
    assert user_targets
    assert all(target.startswith(str(home / ".config/systemd/user")) for target in user_targets)
    assert not any(target.startswith("/root/.config/systemd/user") for target in user_targets)


def test_typing_profile_is_opt_in() -> None:
    payload = run_bootstrap("enable-profile", "--profile", "typing-intake", "--dry-run")
    units = {action["unit"] for action in payload["actions"]}
    assert "abyss-machine-typing-atspi-text-events.service" in units
    assert "abyss-machine-typing-nervous-refresh.timer" in units
    assert payload["dry_run"] is True


def test_bootstrap_install_projects_cli_modules_and_public_seed(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    libexec_dir = tmp_path / "libexec"
    etc_root = tmp_path / "etc" / "abyss-machine"
    state_root = tmp_path / "var" / "lib" / "abyss-machine"
    srv_root = tmp_path / "srv" / "abyss-machine"
    run_root = tmp_path / "run" / "abyss-machine"
    systemd_system_dir = tmp_path / "systemd" / "system"
    systemd_user_dir = tmp_path / "systemd" / "user"
    payload = run_bootstrap(
        "install",
        "--profile",
        "linux-systemd-core",
        "--apply",
        "--local-bin-dir",
        str(bin_dir),
        "--local-libexec-dir",
        str(libexec_dir),
        "--etc-root",
        str(etc_root),
        "--state-root",
        str(state_root),
        "--srv-root",
        str(srv_root),
        "--run-root",
        str(run_root),
        "--systemd-system-dir",
        str(systemd_system_dir),
        "--systemd-user-dir",
        str(systemd_user_dir),
    )
    actions = {action["action"]: action for action in payload["actions"]}
    assert "install_cli" in actions
    assert "install_public_seed" in actions
    assert (libexec_dir / "abyss-machine").is_file()
    assert (libexec_dir / "abyss_machine" / "artifact_bundles.py").is_file()
    assert run_root.is_dir()
    assert (tmp_path / "share" / "abyss-machine" / "manifests" / "artifact_signature_policy.manifest.json").is_file()
    assert (tmp_path / "share" / "abyss-machine" / "generated" / "contract_abi_signatures.min.json").is_file()

    env = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "ABYSS_MACHINE_ETC_ROOT": str(etc_root),
        "ABYSS_MACHINE_STATE_ROOT": str(state_root),
        "ABYSS_MACHINE_ROOT": str(srv_root),
        "ABYSS_MACHINE_RUN_ROOT": str(run_root),
        "ABYSS_MACHINE_ARTIFACT_TRUST_RUNTIME_ROOT": str(srv_root / "runtimes" / "artifact-trust"),
        "ABYSS_MACHINE_ARTIFACT_TRUST_CACHE_ROOT": str(srv_root / "cache" / "artifact-trust"),
    }
    installed = bin_dir / "abyss-machine"
    trust_bin = srv_root / "runtimes" / "artifact-trust" / "bin"
    trust_bin.mkdir(parents=True)
    fake_cosign = trust_bin / "cosign"
    fake_cosign.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' '{\"gitVersion\":\"v-test\",\"platform\":\"linux/amd64\"}'\n",
        encoding="utf-8",
    )
    fake_cosign.chmod(0o755)
    fake_cdxgen = trust_bin / "cdxgen"
    fake_cdxgen.write_text(
        "#!/bin/sh\n"
        "printf '\\033[1mCycloneDX Generator 12.6.0\\033[0m\\n'\n"
        "printf 'Runtime: Node.js, Version: 22.22.2\\n'\n",
        encoding="utf-8",
    )
    fake_cdxgen.chmod(0o755)

    help_result = subprocess.run(
        [str(installed), "artifacts", "--help"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert help_result.returncode == 0, help_result.stderr[-1000:]
    assert "build-sidecars" in help_result.stdout
    assert "release-check" in help_result.stdout
    assert "bundle-register" in help_result.stdout
    assert "bundle-registry" in help_result.stdout
    assert "bundle-registry-upgrade" in help_result.stdout
    assert "evidence-promote" in help_result.stdout
    assert "requirements" in help_result.stdout
    assert "affected" in help_result.stdout
    assert "trust-gate" in help_result.stdout
    assert "trust-tools" in help_result.stdout
    assert "trust-coverage" in help_result.stdout

    trust_result = subprocess.run(
        [str(installed), "artifacts", "trust-tools", "--json"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert trust_result.returncode == 0, trust_result.stderr[-1000:]
    trust_data = json.loads(trust_result.stdout)
    assert trust_data["ok"] is True
    assert trust_data["summary"]["status"] == "partial"
    assert "cosign" in trust_data["summary"]["available_tools"]
    assert "c2pa" in trust_data["summary"]["missing_controls"]
    assert "ml_bom" not in trust_data["summary"]["missing_controls"]
    assert trust_data["tools"]["cosign"]["source"] == "host-managed-runtime"
    assert trust_data["tools"]["cosign"]["version"]["gitVersion"] == "v-test"
    assert trust_data["tools"]["cdxgen"]["source"] == "host-managed-runtime"
    assert trust_data["tools"]["cdxgen"]["version"]["version"] == "12.6.0"
    assert any(
        "cdxgen exit status alone is not an ML-BOM trust gate" in claim
        for claim in trust_data["claim_limits"]
    )

    bundle = tmp_path / "bundle"
    for args in (
        ("artifacts", "build-sidecars", "--bundle-dir", str(bundle), "--json"),
        ("artifacts", "sign", str(bundle), "--json"),
        ("artifacts", "verify", str(bundle), "--json"),
        ("artifacts", "release-check", str(bundle), "--json"),
    ):
        result = subprocess.run(
            [str(installed), *args],
            cwd=tmp_path,
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr[-1000:]
        data = json.loads(result.stdout)
        assert data["ok"] is True

    registry = tmp_path / "registry"
    register_result = subprocess.run(
        [
            str(installed),
            "artifacts",
            "bundle-register",
            str(bundle),
            "--registry-dir",
            str(registry),
            "--lifecycle-state",
            "manually-verified",
            "--consumer-ref",
            "pytest:installed-cli",
            "--evidence-ref",
            "pytest:manual-positive",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert register_result.returncode == 0, register_result.stderr[-1000:]
    register_data = json.loads(register_result.stdout)
    assert register_data["ok"] is True
    assert register_data["record"]["latest_eligible"] is True

    registry_result = subprocess.run(
        [
            str(installed),
            "artifacts",
            "bundle-registry",
            "--registry-dir",
            str(registry),
            "--artifact-class",
            "public_source_seed",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert registry_result.returncode == 0, registry_result.stderr[-1000:]
    registry_data = json.loads(registry_result.stdout)
    assert registry_data["latest_by_artifact_class"]["public_source_seed"]["record_id"] == register_data["record"]["record_id"]

    trust_gate_result = subprocess.run(
        [
            str(installed),
            "artifacts",
            "trust-gate",
            "--registry-dir",
            str(registry),
            "--artifact-class",
            "public_source_seed",
            "--consumer-intent",
            "agent",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert trust_gate_result.returncode == 0, trust_gate_result.stderr[-1000:]
    trust_gate_data = json.loads(trust_gate_result.stdout)
    assert trust_gate_data["schema"] == "abyss_machine_artifact_trust_gate_v1"
    assert trust_gate_data["verdict"] == "allow"
    assert trust_gate_data["decision"]["model"] == "fail_closed_consumer_admission"
    assert trust_gate_data["inspected_claims"]["registry_latest"]["selected_record_is_latest"] is True

    requirements_result = subprocess.run(
        [
            str(installed),
            "artifacts",
            "requirements",
            "--registry-dir",
            str(registry),
            "--artifact-class",
            "public_source_seed",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert requirements_result.returncode == 0, requirements_result.stderr[-1000:]
    requirements_data = json.loads(requirements_result.stdout)
    requirements_row = requirements_data["rows"][0]
    assert requirements_data["schema"] == "abyss_machine_artifact_requirements_v1"
    assert requirements_row["source_route"]["contract_surface_status"] == "local_contract_surface"
    assert requirements_row["registry_status"]["has_latest"] is True
    assert requirements_row["trust_gate_status"]["verdict"] == "allow"

    affected_result = subprocess.run(
        [
            str(installed),
            "artifacts",
            "affected",
            "--registry-dir",
            str(registry),
            "--artifact-class",
            "public_source_seed",
            "--changed-path",
            "src/abyss_machine/artifact_bundles.py",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert affected_result.returncode == 0, affected_result.stderr[-1000:]
    affected_data = json.loads(affected_result.stdout)
    affected_row = affected_data["rows"][0]
    assert affected_data["schema"] == "abyss_machine_artifact_affected_v1"
    assert affected_row["verdict"] == "needs_rebuild"
    assert affected_row["freshness"] == "stale"
    assert affected_row["trust_gate"]["verdict"] == "allow"

    registry_upgrade_result = subprocess.run(
        [
            str(installed),
            "artifacts",
            "bundle-registry-upgrade",
            "--registry-dir",
            str(registry),
            "--dry-run",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert registry_upgrade_result.returncode == 0, registry_upgrade_result.stderr[-1000:]
    registry_upgrade_data = json.loads(registry_upgrade_result.stdout)
    assert registry_upgrade_data["schema"] == "abyss_machine_artifact_bundle_registry_upgrade_v1"
    assert registry_upgrade_data["dry_run"] is True
    assert registry_upgrade_data["summary"]["upgraded"] == 0
    assert registry_upgrade_data["summary"]["unchanged"] == 1
    assert registry_upgrade_data["written"] == []

    manual_root = srv_root / "tmp" / "pytest-manual-artifact-trust-20260620"
    manual_root.mkdir(parents=True)
    (manual_root / "positive-verify.json").write_text(
        json.dumps({"artifact_class": "public_source_seed", "ok": True}) + "\n",
        encoding="utf-8",
    )
    (manual_root / "missing-abi-verify.json").write_text(
        json.dumps({"artifact_class": "public_source_seed", "ok": False, "missing": ["artifact.abi.json"]}) + "\n",
        encoding="utf-8",
    )
    coverage_result = subprocess.run(
        [
            str(installed),
            "artifacts",
            "trust-coverage",
            "--registry-dir",
            str(registry),
            "--manual-evidence-root",
            str(srv_root / "tmp"),
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert coverage_result.returncode == 0, coverage_result.stderr[-1000:]
    coverage_data = json.loads(coverage_result.stdout)
    assert coverage_data["schema"] == "abyss_machine_artifacts_trust_coverage_v1"
    assert coverage_data["summary"]["artifact_classes"] == 21
    assert coverage_data["summary"]["fully_covered"] == 1
    coverage_rows = {row["artifact_class"]: row for row in coverage_data["rows"]}
    assert coverage_rows["public_source_seed"]["status"] == "FULLY_COVERED"
    assert coverage_rows["public_source_seed"]["persistent_registry_status"]["has_latest"] is True
    assert coverage_rows["bootstrap_install_bundle"]["status"] == "DEFERRED_WITH_REAL_BLOCKER"
    assert coverage_rows["bootstrap_install_bundle"]["remaining_blocker"]

    revoke_result = subprocess.run(
        [
            str(installed),
            "artifacts",
            "bundle-register",
            str(bundle),
            "--registry-dir",
            str(registry),
            "--lifecycle-state",
            "revoked",
            "--revocation-reason",
            "pytest manual negative",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert revoke_result.returncode == 0, revoke_result.stderr[-1000:]

    revoked_registry_result = subprocess.run(
        [
            str(installed),
            "artifacts",
            "bundle-registry",
            "--registry-dir",
            str(registry),
            "--artifact-class",
            "public_source_seed",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert revoked_registry_result.returncode == 0, revoked_registry_result.stderr[-1000:]
    revoked_registry_data = json.loads(revoked_registry_result.stdout)
    assert revoked_registry_data["latest_by_artifact_class"] == {}

from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = ROOT / "scripts" / "abyss-machine-bootstrap"
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import artifact_bundles


def _current_bootstrap_install_abi_subject_digest() -> str:
    requirements = artifact_bundles.artifact_requirements("bootstrap_install_bundle")
    row = requirements["rows"][0]
    surfaces = row["source_route"]["generated_contract_surfaces"]
    for surface in surfaces:
        digest = str(surface.get("source_tree_hash") or "")
        if digest:
            return digest
    raise AssertionError("bootstrap_install_bundle ABI subject digest is unavailable")


def run_bootstrap_process(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(BOOTSTRAP), *args, "--json"],
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, **(env or {})},
        timeout=30,
    )


def run_bootstrap(*args: str, env: dict[str, str] | None = None) -> dict:
    result = run_bootstrap_process(*args, env=env)
    assert result.returncode == 0, result.stderr[-1000:]
    payload = json.loads(result.stdout)
    assert payload["schema"] == "abyss_machine_bootstrap_v1"
    assert payload["ok"] is True
    return payload


def _bootstrap_install_registry_record(
    tmp_path: Path,
    *,
    lifecycle_state: str = "release-ready",
    subject_digest: str = "sha256:" + ("1" * 64),
    abi_subject_digest: str | None = None,
    trust_root_mode: str = "github_oidc",
    privacy_boundary: str = "public-safe bootstrap install material",
    created_at: str = "2026-06-25T00:00:00Z",
) -> tuple[Path, str, str]:
    registry = tmp_path / "bundle-registry"
    records = registry / artifact_bundles.BUNDLE_REGISTRY_RECORDS_DIR
    records.mkdir(parents=True, exist_ok=True)
    source_ref = "manifests/artifact_bundles/bootstrap_install_bundle.bundle.json"
    record_id = "sha256:" + hashlib.sha256(f"bootstrap_install_bundle:{subject_digest}:{lifecycle_state}".encode()).hexdigest()
    trust_root_evidence = {
        "schema": "pytest_bootstrap_trust_root_evidence_v1",
        "mode": trust_root_mode,
        "issuer": "https://token.actions.githubusercontent.com",
        "subject": "repo:8Dionysus/abyss-machine:ref:refs/heads/main",
        "source_repo": "abyss-machine",
        "source_ref": source_ref,
        "subject_digest": subject_digest,
        "verifier": "pytest-github-oidc-verifier",
        "evidence_ref": f"pytest:github_oidc:{subject_digest}",
    }
    record = {
        "schema": "abyss_machine_artifact_bundle_registry_record_v1",
        "record_id": record_id,
        "artifact_class": "bootstrap_install_bundle",
        "bundle_layout": artifact_bundles.BUNDLE_LAYOUT,
        "bundle_ref": "pytest/bootstrap-install-bundle",
        "bundle_manifest_ref": source_ref,
        "subject_digest": subject_digest,
        "artifact_subjects_digest": subject_digest,
        "abi_subject_digest": abi_subject_digest or _current_bootstrap_install_abi_subject_digest(),
        "lifecycle_state": lifecycle_state,
        "latest_eligible": lifecycle_state == "release-ready",
        "terminal_state": lifecycle_state in artifact_bundles.BUNDLE_TERMINAL_STATES,
        "verification_ok": True,
        "required_controls": ["abi_signature", "sbom", "slsa_in_toto", "sigstore_cosign"],
        "verified_controls": ["abi_signature", "sbom", "slsa_in_toto", "sigstore_cosign"],
        "present_controls": ["abi_signature", "sbom", "slsa_in_toto", "sigstore_cosign"],
        "controls": {
            "required": ["abi_signature", "sbom", "slsa_in_toto", "sigstore_cosign"],
            "verified": ["abi_signature", "sbom", "slsa_in_toto", "sigstore_cosign"],
            "present": ["abi_signature", "sbom", "slsa_in_toto", "sigstore_cosign"],
        },
        "verification_errors": [],
        "verification_missing": [],
        "verification_warnings": [],
        "source_repo": "abyss-machine",
        "source_ref": source_ref,
        "source_refs": [source_ref],
        "producer": "pytest bootstrap install publisher",
        "producer_command": "pytest",
        "trust_root_mode": trust_root_mode,
        "trust_root_evidence": trust_root_evidence,
        "verifier_versions": {"pytest": "bootstrap-install-admission"},
        "privacy_boundary": privacy_boundary,
        "artifact_subject_store": {
            "required": True,
            "ok": True,
            "aggregate_digest": subject_digest,
            "path_basis": "pytest",
        },
        "consumer_contract": {
            "stable_interface": "abyss-machine artifacts trust-gate --artifact-class bootstrap_install_bundle --consumer-intent installer --json",
            "admission_gate": "fail_closed_consumer_admission",
            "subject_store_required": True,
        },
        "consumer_refs": ["pytest:bootstrap-install"],
        "evidence_refs": ["pytest:bootstrap-install-admission"],
        "supersedes": [],
        "revocation_reason": "pytest revoked install material" if lifecycle_state == "revoked" else "",
        "created_at": created_at,
        "policy_ref": artifact_bundles.POLICY_REF,
        "abi_ref": artifact_bundles.ABI_REF,
    }
    (records / f"{record_id.removeprefix('sha256:')}.json").write_text(
        json.dumps(record, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return registry, subject_digest, record_id


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


def test_install_docs_refresh_code_examples_include_artifact_selector() -> None:
    install_docs = (ROOT / "docs" / "install" / "README.md").read_text(encoding="utf-8")
    assert "refresh-code --dry-run --skip-artifact-trust-gate --json" in install_docs
    assert "refresh-code --apply --artifact-record-id <bootstrap-install-bundle-record-id> --json" in install_docs
    assert "refresh-code --apply --artifact-subject-digest sha256:<bootstrap-install-bundle-subject> --json" in install_docs


def test_bootstrap_install_derives_user_systemd_dir_from_explicit_home_under_root_env(tmp_path: Path) -> None:
    home = tmp_path / "home" / "agent"
    payload = run_bootstrap(
        "install",
        "--profile",
        "linux-systemd-core",
        "--dry-run",
        "--skip-artifact-trust-gate",
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


def test_bootstrap_install_requires_artifact_trust_gate_by_default(tmp_path: Path) -> None:
    result = run_bootstrap_process(
        "install",
        "--dry-run",
        "--artifact-registry-dir",
        str(tmp_path / "missing-registry"),
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["artifact_admission"]["required"] is True
    assert payload["artifact_admission"]["verdict"] == "deny"
    assert payload["artifact_admission"]["errors"] == ["artifact_trust_gate_selector_required"]
    assert payload["actions"] == [
        {
            "action": "artifact_trust_gate",
            "artifact_class": "bootstrap_install_bundle",
            "consumer_intent": "installer",
            "latest_record_id": None,
            "record_id": None,
            "registry_dir": str(tmp_path / "missing-registry"),
            "required": True,
            "verdict": "deny",
        }
    ]


def test_bootstrap_install_local_development_skip_is_explicit(tmp_path: Path) -> None:
    payload = run_bootstrap(
        "install",
        "--dry-run",
        "--skip-artifact-trust-gate",
        "--artifact-registry-dir",
        str(tmp_path / "missing-registry"),
    )

    admission = payload["artifact_admission"]
    assert admission["ok"] is True
    assert admission["required"] is False
    assert admission["verdict"] == "not_required"
    assert admission["trust_gate"] is None
    assert "explicit local-development opt-out" in admission["claim_limit"]
    assert payload["actions"][0]["required"] is False


def test_bootstrap_refresh_code_local_development_skip_is_explicit(tmp_path: Path) -> None:
    payload = run_bootstrap(
        "refresh-code",
        "--dry-run",
        "--skip-artifact-trust-gate",
        "--artifact-registry-dir",
        str(tmp_path / "missing-registry"),
    )

    action_names = [action["action"] for action in payload["actions"]]
    admission = payload["artifact_admission"]
    assert payload["command"] == "refresh-code"
    assert payload["dry_run"] is True
    assert payload["mutation_scope"] == "cli_package_and_public_seed_only"
    assert payload["config_rendered"] is False
    assert payload["systemd_rendered"] is False
    assert admission["ok"] is True
    assert admission["required"] is False
    assert admission["verdict"] == "not_required"
    assert admission["trust_gate"] is None
    assert "explicit local-development opt-out" in admission["claim_limit"]
    assert "install_cli" in action_names
    assert "install_public_seed" in action_names
    assert "render" not in action_names
    assert "copy_binary" not in action_names
    assert "mkdir" not in action_names


def test_bootstrap_install_rejects_trust_gate_skip_for_live_apply() -> None:
    result = run_bootstrap_process(
        "install",
        "--apply",
        "--skip-artifact-trust-gate",
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["artifact_admission"]["verdict"] == "skip_rejected"
    assert payload["artifact_admission"]["errors"] == ["artifact_trust_gate_skip_not_allowed_for_live_apply"]
    assert "isolated from live default roots" in payload["artifact_admission"]["claim_limit"]
    assert not any(action["action"] == "ensure_root" for action in payload["actions"])


def test_bootstrap_refresh_code_rejects_trust_gate_skip_for_live_apply() -> None:
    result = run_bootstrap_process(
        "refresh-code",
        "--apply",
        "--skip-artifact-trust-gate",
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["command"] == "refresh-code"
    assert payload["mutation_scope"] == "cli_package_and_public_seed_only"
    assert payload["config_rendered"] is False
    assert payload["systemd_rendered"] is False
    assert payload["artifact_admission"]["verdict"] == "skip_rejected"
    assert payload["artifact_admission"]["errors"] == ["artifact_trust_gate_skip_not_allowed_for_live_apply"]
    assert not any(action["action"] == "install_cli" for action in payload["actions"])


def test_bootstrap_refresh_code_skip_checks_only_refresh_mutation_targets(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    libexec_dir = tmp_path / "libexec"

    payload = run_bootstrap(
        "refresh-code",
        "--apply",
        "--skip-artifact-trust-gate",
        "--local-bin-dir",
        str(bin_dir),
        "--local-libexec-dir",
        str(libexec_dir),
    )

    action_names = [action["action"] for action in payload["actions"]]
    assert payload["command"] == "refresh-code"
    assert payload["ok"] is True
    assert payload["artifact_admission"]["verdict"] == "not_required"
    assert payload["mutation_scope"] == "cli_package_and_public_seed_only"
    assert "install_cli" in action_names
    assert "install_public_seed" in action_names
    assert "ensure_root" not in action_names
    assert "render" not in action_names
    assert (bin_dir / "abyss-machine").is_symlink()
    assert (libexec_dir / "abyss-machine").is_file()
    assert (tmp_path / "share" / "abyss-machine" / "manifests" / "artifact_signature_policy.manifest.json").is_file()


def test_refreshed_cli_execs_admission_server_from_installed_package(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    libexec_dir = tmp_path / "libexec"
    socket_suffix = hashlib.sha256(str(tmp_path).encode()).hexdigest()[:10]
    socket_path = Path("/tmp") / f"abyss-admission-{os.getpid()}-{socket_suffix}.sock"
    runtime_dir = tmp_path / "runtime"
    run_bootstrap(
        "refresh-code",
        "--apply",
        "--skip-artifact-trust-gate",
        "--local-bin-dir",
        str(bin_dir),
        "--local-libexec-dir",
        str(libexec_dir),
    )
    runtime_dir.mkdir()
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    env["XDG_RUNTIME_DIR"] = str(runtime_dir)
    server = subprocess.Popen(
        [
            str(bin_dir / "abyss-machine"),
            "resource",
            "admission",
            "serve",
            "--socket",
            str(socket_path),
            "--allow-shutdown",
        ],
        cwd="/",
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not socket_path.exists() and server.poll() is None:
            time.sleep(0.05)
        assert socket_path.is_socket(), server.communicate(timeout=1)[1]
        shutdown = subprocess.run(
            [
                str(bin_dir / "abyss-machine"),
                "resource",
                "admission",
                "shutdown",
                "--socket",
                str(socket_path),
                "--json",
            ],
            cwd="/",
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
        assert shutdown.returncode == 0, shutdown.stderr
        assert json.loads(shutdown.stdout)["decision"] == "allow"
        assert server.wait(timeout=5) == 0
    finally:
        if server.poll() is None:
            server.terminate()
            server.wait(timeout=5)
        socket_path.unlink(missing_ok=True)


def test_bootstrap_install_allows_trust_gate_skip_for_tmp_projection_apply(tmp_path: Path) -> None:
    live_srv_root = tmp_path / "live" / "srv" / "abyss-machine"
    live_tmp_root = live_srv_root / "tmp"
    projection = live_tmp_root / "first-run-projection"
    env = {
        "ABYSS_MACHINE_ROOT": str(live_srv_root),
        "ABYSS_MACHINE_TMP_ROOT": str(live_tmp_root),
    }

    result = run_bootstrap_process(
        "install",
        "--profile",
        "linux-systemd-core",
        "--apply",
        "--skip-artifact-trust-gate",
        "--user",
        "agent",
        "--home",
        str(projection / "home" / "agent"),
        "--etc-root",
        str(projection / "etc" / "abyss-machine"),
        "--state-root",
        str(projection / "var" / "lib" / "abyss-machine"),
        "--srv-root",
        str(projection / "srv" / "abyss-machine"),
        "--run-root",
        str(projection / "run" / "abyss-machine"),
        "--abyss-os-root",
        str(projection / "srv" / "AbyssOS"),
        "--vault-mount",
        str(projection / "abyss"),
        "--local-bin-dir",
        str(projection / "usr" / "local" / "bin"),
        "--local-libexec-dir",
        str(projection / "usr" / "local" / "libexec"),
        "--systemd-system-dir",
        str(projection / "etc" / "systemd" / "system"),
        "--systemd-user-dir",
        str(projection / "home" / "agent" / ".config" / "systemd" / "user"),
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["artifact_admission"]["verdict"] == "not_required"
    assert any(action["action"] == "ensure_root" for action in payload["actions"])


def test_bootstrap_install_can_require_artifact_trust_gate(tmp_path: Path) -> None:
    registry, subject_digest, record_id = _bootstrap_install_registry_record(tmp_path)

    payload = run_bootstrap(
        "install",
        "--dry-run",
        "--require-artifact-trust-gate",
        "--artifact-registry-dir",
        str(registry),
        "--artifact-subject-digest",
        subject_digest,
        "--artifact-record-id",
        record_id,
        "--artifact-trust-root-mode",
        "github_oidc",
    )

    admission = payload["artifact_admission"]
    assert admission["ok"] is True
    assert admission["verdict"] == "allow"
    assert admission["trust_gate"]["decision"]["model"] == "fail_closed_consumer_admission"
    assert admission["freshness_gate"]["verdict"] == "allow"
    assert admission["trust_gate"]["inspected_claims"]["source"]["source_repo_matched"] is True
    assert admission["trust_gate"]["inspected_claims"]["trust_root"]["trust_root_mode_matched"] is True
    assert payload["actions"][0]["action"] == "artifact_trust_gate"
    assert payload["actions"][0]["verdict"] == "allow"
    assert payload["actions"][0]["freshness_verdict"] == "allow"
    assert any(action["action"] == "ensure_root" for action in payload["actions"])


def test_bootstrap_install_requires_artifact_selector_for_trust_gate(tmp_path: Path) -> None:
    registry, _subject_digest, _record_id = _bootstrap_install_registry_record(tmp_path)

    result = run_bootstrap_process(
        "install",
        "--dry-run",
        "--require-artifact-trust-gate",
        "--artifact-registry-dir",
        str(registry),
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["artifact_admission"]["verdict"] == "deny"
    assert payload["artifact_admission"]["errors"] == ["artifact_trust_gate_selector_required"]
    assert not any(action["action"] == "ensure_root" for action in payload["actions"])


def test_bootstrap_install_fails_closed_on_stale_abi_subject(tmp_path: Path) -> None:
    registry, subject_digest, record_id = _bootstrap_install_registry_record(
        tmp_path,
        abi_subject_digest="sha256:" + ("0" * 64),
    )
    result = run_bootstrap_process(
        "install",
        "--dry-run",
        "--require-artifact-trust-gate",
        "--artifact-registry-dir",
        str(registry),
        "--artifact-subject-digest",
        subject_digest,
        "--artifact-record-id",
        record_id,
        "--artifact-trust-root-mode",
        "github_oidc",
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    admission = payload["artifact_admission"]
    assert admission["ok"] is False
    assert admission["verdict"] == "deny"
    assert admission["trust_gate"]["verdict"] == "allow"
    assert admission["freshness_gate"]["verdict"] == "deny"
    assert admission["freshness_gate"]["blocking_rows"][0]["reasons"] == ["abi_subject_digest_stale"]
    assert admission["errors"] == ["artifact_source_freshness_blocking:bootstrap_install_bundle:abi_subject_digest_stale"]
    assert not any(action["action"] == "ensure_root" for action in payload["actions"])


def test_bootstrap_install_freshness_checks_selected_non_latest_record(tmp_path: Path) -> None:
    registry, stale_subject_digest, stale_record_id = _bootstrap_install_registry_record(
        tmp_path,
        subject_digest="sha256:" + ("3" * 64),
        abi_subject_digest="sha256:" + ("0" * 64),
        created_at="2026-06-25T00:00:00Z",
    )
    _registry, _fresh_subject_digest, fresh_record_id = _bootstrap_install_registry_record(
        tmp_path,
        subject_digest="sha256:" + ("4" * 64),
        abi_subject_digest=_current_bootstrap_install_abi_subject_digest(),
        created_at="2026-06-26T00:00:00Z",
    )

    result = run_bootstrap_process(
        "install",
        "--dry-run",
        "--require-artifact-trust-gate",
        "--allow-non-latest-artifact",
        "--artifact-registry-dir",
        str(registry),
        "--artifact-subject-digest",
        stale_subject_digest,
        "--artifact-record-id",
        stale_record_id,
        "--artifact-trust-root-mode",
        "github_oidc",
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    admission = payload["artifact_admission"]
    blocking_registry = admission["freshness_gate"]["blocking_rows"][0]["registry"]
    assert admission["trust_gate"]["verdict"] == "allow"
    assert admission["trust_gate"]["latest_record_id"] == fresh_record_id
    assert admission["freshness_gate"]["verdict"] == "deny"
    assert blocking_registry["latest_record_id"] == fresh_record_id
    assert blocking_registry["freshness_record_id"] == stale_record_id
    assert blocking_registry["freshness_record_is_latest"] is False
    assert admission["errors"] == ["artifact_source_freshness_blocking:bootstrap_install_bundle:abi_subject_digest_stale"]
    assert not any(action["action"] == "ensure_root" for action in payload["actions"])


def test_bootstrap_install_fails_closed_when_required_registry_is_missing(tmp_path: Path) -> None:
    result = run_bootstrap_process(
        "install",
        "--dry-run",
        "--require-artifact-trust-gate",
        "--artifact-registry-dir",
        str(tmp_path / "missing-registry"),
        "--artifact-record-id",
        "sha256:" + ("9" * 64),
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["artifact_admission"]["verdict"] == "unknown"
    assert payload["artifact_admission"]["errors"] == ["no_registry_record"]
    assert payload["actions"] == [
        {
            "action": "artifact_trust_gate",
            "artifact_class": "bootstrap_install_bundle",
            "consumer_intent": "installer",
            "latest_record_id": None,
            "record_id": "sha256:" + ("9" * 64),
            "registry_dir": str(tmp_path / "missing-registry"),
            "required": True,
            "verdict": "unknown",
        }
    ]


def test_bootstrap_install_fails_closed_on_wrong_artifact_digest(tmp_path: Path) -> None:
    registry, _subject_digest, record_id = _bootstrap_install_registry_record(tmp_path)
    wrong_digest = "sha256:" + ("f" * 64)
    result = run_bootstrap_process(
        "install",
        "--dry-run",
        "--require-artifact-trust-gate",
        "--artifact-registry-dir",
        str(registry),
        "--artifact-record-id",
        record_id,
        "--artifact-subject-digest",
        wrong_digest,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["artifact_admission"]["verdict"] == "deny"
    assert "subject_digest_mismatch" in payload["artifact_admission"]["errors"]
    assert not any(action["action"] == "ensure_root" for action in payload["actions"])


def test_bootstrap_install_fails_closed_on_revoked_record(tmp_path: Path) -> None:
    registry, subject_digest, record_id = _bootstrap_install_registry_record(tmp_path, lifecycle_state="revoked")
    result = run_bootstrap_process(
        "install",
        "--dry-run",
        "--require-artifact-trust-gate",
        "--artifact-registry-dir",
        str(registry),
        "--artifact-record-id",
        record_id,
        "--artifact-subject-digest",
        subject_digest,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["artifact_admission"]["verdict"] == "deny"
    assert "terminal_lifecycle_state:revoked" in payload["artifact_admission"]["errors"]
    assert "no_latest_record" in payload["artifact_admission"]["errors"]
    assert not any(action["action"] == "ensure_root" for action in payload["actions"])


def test_bootstrap_install_fails_closed_on_wrong_trust_root(tmp_path: Path) -> None:
    registry, subject_digest, record_id = _bootstrap_install_registry_record(tmp_path)
    result = run_bootstrap_process(
        "install",
        "--dry-run",
        "--require-artifact-trust-gate",
        "--artifact-registry-dir",
        str(registry),
        "--artifact-record-id",
        record_id,
        "--artifact-subject-digest",
        subject_digest,
        "--artifact-trust-root-mode",
        "public_release",
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["artifact_admission"]["verdict"] == "deny"
    assert "trust_root_mode_mismatch" in payload["artifact_admission"]["errors"]
    assert not any(action["action"] == "ensure_root" for action in payload["actions"])


def test_bootstrap_install_fails_closed_on_private_public_boundary(tmp_path: Path) -> None:
    registry, subject_digest, record_id = _bootstrap_install_registry_record(
        tmp_path,
        privacy_boundary="private host evidence; not public repo content",
    )
    result = run_bootstrap_process(
        "install",
        "--dry-run",
        "--require-artifact-trust-gate",
        "--artifact-registry-dir",
        str(registry),
        "--artifact-record-id",
        record_id,
        "--artifact-subject-digest",
        subject_digest,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["artifact_admission"]["verdict"] == "manual_review_required"
    assert "production_consumer_requires_public_privacy_boundary" in payload["artifact_admission"]["errors"]
    assert not any(action["action"] == "ensure_root" for action in payload["actions"])


def test_bootstrap_install_bundle_archive_is_self_contained(tmp_path: Path) -> None:
    manifest_path = ROOT / "manifests" / "artifact_bundles" / "bootstrap_install_bundle.bundle.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tar_command = next(
        command
        for command in manifest["consumer_command"]
        if command.startswith("tar ") and "abyss-machine-bootstrap-VERSION.tar.gz" in command
    )
    parts = shlex.split(tar_command)
    output_index = parts.index("-czf") + 1
    archive_inputs = parts[output_index + 1 :]

    required_inputs = {
        "scripts/abyss-machine-bootstrap",
        "src/abyss_machine",
        "config-templates",
        "systemd",
        "schemas/bootstrap-report.schema.json",
        "manifests",
        "generated",
    }
    assert required_inputs.issubset(set(archive_inputs))

    archive = tmp_path / "abyss-machine-bootstrap-test.tar.gz"
    create_result = subprocess.run(
        [
            "tar",
            "--sort=name",
            "--mtime=@0",
            "--owner=0",
            "--group=0",
            "--numeric-owner",
            "-czf",
            str(archive),
            *archive_inputs,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert create_result.returncode == 0, create_result.stderr[-1000:]

    extracted = tmp_path / "extracted"
    extracted.mkdir()
    extract_result = subprocess.run(
        ["tar", "-xzf", str(archive), "-C", str(extracted)],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert extract_result.returncode == 0, extract_result.stderr[-1000:]
    assert (extracted / "manifests" / "artifact_signature_policy.manifest.json").is_file()
    assert (extracted / "generated" / "contract_abi_signatures.min.json").is_file()

    doctor_result = subprocess.run(
        [
            sys.executable,
            str(extracted / "scripts" / "abyss-machine-bootstrap"),
            "doctor",
            "--dry-run",
            "--json",
        ],
        cwd=extracted,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert doctor_result.returncode == 0, doctor_result.stderr[-1000:]
    payload = json.loads(doctor_result.stdout)
    assert payload["ok"] is True
    assert payload["checks"]["artifact_policy_exists"] is True
    assert payload["checks"]["contract_abi_exists"] is True


def test_bootstrap_install_abi_surface_tracks_packaged_manifest_and_generated_roots() -> None:
    policy = json.loads((ROOT / "manifests" / "artifact_signature_policy.manifest.json").read_text(encoding="utf-8"))
    bootstrap_surface = next(
        surface
        for surface in policy["contract_surfaces"]
        if surface["id"] == "bootstrap-install-seed"
    )
    assert "manifests" in bootstrap_surface["source_paths"]
    assert "generated" in bootstrap_surface["source_paths"]
    assert "manifests/bootstrap_profiles.manifest.json" not in bootstrap_surface["source_paths"]

    abi = json.loads((ROOT / "generated" / "contract_abi_signatures.min.json").read_text(encoding="utf-8"))
    generated_surface = next(
        surface
        for surface in abi["contract_surfaces"]
        if surface["id"] == "bootstrap-install-seed"
    )
    source_files = {entry["path"] for entry in generated_surface["source_files"]}

    assert "manifests/artifact_signature_policy.manifest.json" in source_files
    assert "manifests/artifact_bundles/bootstrap_install_bundle.bundle.json" in source_files
    assert "generated/scaffold_index.min.json" in source_files
    assert "generated/contract_abi_signatures.min.json" not in source_files


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
        "--skip-artifact-trust-gate",
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
    assert (libexec_dir / "abyss-machine").read_bytes() == (
        ROOT / "src" / "abyss_machine" / "cli.py"
    ).read_bytes()
    assert (libexec_dir / "abyss_machine" / "artifact_bundles.py").is_file()
    assert Path(actions["install_cli"]["compiled_cli"]).is_file()
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
    assert "registry-latest" in help_result.stdout
    assert "bundle-registry-upgrade" in help_result.stdout
    assert "evidence-promote" in help_result.stdout
    assert "requirements" in help_result.stdout
    assert "scenarios" in help_result.stdout
    assert "affected" in help_result.stdout
    assert "trust-gate" in help_result.stdout
    assert "trust-tools" in help_result.stdout
    assert "trust-tools-python" in help_result.stdout
    assert "update-repo-verify" in help_result.stdout
    assert "scitt-verify" in help_result.stdout
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

    registry_latest_result = subprocess.run(
        [
            str(installed),
            "artifacts",
            "registry-latest",
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
    assert registry_latest_result.returncode == 0, registry_latest_result.stderr[-1000:]
    registry_latest_data = json.loads(registry_latest_result.stdout)
    assert registry_latest_data["schema"] == "abyss_machine_artifact_registry_latest_v1"
    assert registry_latest_data["latest_record_id"] == register_data["record"]["record_id"]
    assert registry_latest_data["trust_gate"]["verdict"] == "allow"

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
    assert affected_data["gate"]["enabled"] is False
    assert affected_data["gate"]["exit_code"] == 0

    affected_gate_result = subprocess.run(
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
            "--fail-on-blocking",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert affected_gate_result.returncode == 2, affected_gate_result.stderr[-1000:]
    affected_gate_data = json.loads(affected_gate_result.stdout)
    assert affected_gate_data["gate"]["enabled"] is True
    assert affected_gate_data["gate"]["allowed"] is False
    assert affected_gate_data["gate"]["reasons"] == ["operationally_blocking:1"]

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

    durable_coverage_result = subprocess.run(
        [
            str(installed),
            "artifacts",
            "trust-coverage",
            "--registry-dir",
            str(registry),
            "--durable-only",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert durable_coverage_result.returncode == 0, durable_coverage_result.stderr[-1000:]
    durable_coverage_data = json.loads(durable_coverage_result.stdout)
    assert durable_coverage_data["evidence_mode"] == "durable_registry_only"
    assert durable_coverage_data["manual_evidence_roots"] == []
    assert durable_coverage_data["summary"]["fully_covered"] == 0
    assert durable_coverage_data["summary"]["durable_gate_covered"] == 1
    durable_rows = {row["artifact_class"]: row for row in durable_coverage_data["rows"]}
    assert durable_rows["public_source_seed"]["status"] == "DURABLE_GATE_COVERED"
    assert durable_rows["public_source_seed"]["installed_verification"]["evidence_mode"] == "durable_registry_only"
    assert durable_rows["public_source_seed"]["manual_positive_evidence"] == []
    assert durable_rows["public_source_seed"]["manual_negative_evidence"] == []

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

    revoked_latest_result = subprocess.run(
        [
            str(installed),
            "artifacts",
            "registry-latest",
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
    assert revoked_latest_result.returncode == 1
    revoked_latest_data = json.loads(revoked_latest_result.stdout)
    assert revoked_latest_data["has_latest"] is False
    assert revoked_latest_data["errors"] == ["no_latest_record"]


def test_bootstrap_refresh_code_projects_only_cli_modules_and_public_seed(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    libexec_dir = tmp_path / "libexec"
    etc_root = tmp_path / "etc" / "abyss-machine"
    state_root = tmp_path / "var" / "lib" / "abyss-machine"
    srv_root = tmp_path / "srv" / "abyss-machine"
    run_root = tmp_path / "run" / "abyss-machine"
    systemd_system_dir = tmp_path / "systemd" / "system"
    systemd_user_dir = tmp_path / "systemd" / "user"
    payload = run_bootstrap(
        "refresh-code",
        "--apply",
        "--skip-artifact-trust-gate",
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
    action_names = [action["action"] for action in payload["actions"]]
    assert payload["command"] == "refresh-code"
    assert payload["ok"] is True
    assert payload["dry_run"] is False
    assert payload["mutation_scope"] == "cli_package_and_public_seed_only"
    assert payload["config_rendered"] is False
    assert payload["systemd_rendered"] is False
    assert "install_cli" in actions
    assert "install_public_seed" in actions
    assert "render" not in action_names
    assert "mkdir" not in action_names
    assert (libexec_dir / "abyss-machine").is_file()
    assert (libexec_dir / "abyss_machine" / "artifact_bundles.py").is_file()
    assert (bin_dir / "abyss-machine").is_symlink()
    assert (tmp_path / "share" / "abyss-machine" / "manifests" / "artifact_signature_policy.manifest.json").is_file()
    assert (tmp_path / "share" / "abyss-machine" / "generated" / "contract_abi_signatures.min.json").is_file()
    assert not etc_root.exists()
    assert not state_root.exists()
    assert not srv_root.exists()
    assert not run_root.exists()
    assert not systemd_system_dir.exists()
    assert not systemd_user_dir.exists()


def test_linux_systemd_core_profile_has_no_resident_memory_controller() -> None:
    payload = run_bootstrap("enable-profile", "--profile", "linux-systemd-core", "--dry-run")
    units = {(action["scope"], action["unit"]) for action in payload["actions"]}
    assert ("user", "abyss-memory-controller.service") not in units
    assert ("user", "abyss-resource-admission.service") in units


def test_resource_admission_user_unit_is_unprivileged_and_uncapped() -> None:
    unit = (ROOT / "systemd" / "user" / "abyss-resource-admission.service").read_text(encoding="utf-8")

    assert "ExecStart={{ABYSS_LOCAL_BIN_DIR}}/abyss-machine resource admission serve" in unit
    assert "UMask=0077" in unit
    assert "NoNewPrivileges=yes" in unit
    assert "RestrictAddressFamilies=AF_UNIX" in unit
    assert "ProtectSystem=strict" in unit
    assert "MemoryMax=" not in unit
    assert "MemoryHigh=" not in unit
    assert "MemoryLimit=" not in unit

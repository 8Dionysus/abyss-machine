from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import artifact_bundles
from abyss_machine import cli


def _write_fake_cosign(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import hashlib
import json
import sys
from pathlib import Path


def option_value(args, name):
    index = args.index(name)
    return args[index + 1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


args = sys.argv[1:]
command = args[0]
if command == "sign-blob":
    bundle = Path(option_value(args, "--bundle"))
    subject = args[-1]
    sha = digest(subject)
    bundle.write_text(json.dumps({"schema": "fake_sigstore_bundle_v1", "sha256": sha}) + "\\n", encoding="utf-8")
    print("fake-signature:" + sha)
    sys.exit(0)
if command == "verify-blob":
    bundle = json.loads(Path(option_value(args, "--bundle")).read_text(encoding="utf-8"))
    subject = args[-1]
    sys.exit(0 if bundle.get("sha256") == digest(subject) else 1)
sys.exit(2)
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _trust_root_evidence(mode: str, *, subject_digest: str, source_repo: str, source_ref: str) -> dict[str, str]:
    base = {
        "schema": "pytest_artifact_trust_root_evidence_v1",
        "mode": mode,
        "source_repo": source_repo,
        "source_ref": source_ref,
        "subject_digest": subject_digest,
        "verifier": f"pytest-{mode}-verifier",
        "evidence_ref": f"pytest:{mode}:{subject_digest}",
    }
    if mode == "github_oidc":
        return {
            **base,
            "issuer": "https://token.actions.githubusercontent.com",
            "subject": f"repo:8Dionysus/{source_repo}:ref:refs/heads/main",
            "workflow_ref": f"8Dionysus/{source_repo}/.github/workflows/release.yml@refs/heads/main",
        }
    if mode == "oci_registry":
        return {
            **base,
            "registry_ref": f"ghcr.io/8dionysus/{source_repo}/{source_ref.replace('/', '-')}",
            "digest": subject_digest,
        }
    if mode == "public_release":
        return {
            **base,
            "release_ref": f"https://github.com/8Dionysus/{source_repo}/releases/tag/pytest",
            "asset_ref": source_ref.rsplit("/", 1)[-1] or "pytest-artifact",
            "asset_digest": subject_digest,
        }
    raise AssertionError(f"unsupported test trust root mode: {mode}")


def _bundle_subject_digest(bundle: Path) -> str:
    signature_path = bundle / artifact_bundles.SIGNATURE_DECISION_SIDECAR
    if signature_path.is_file():
        signature = json.loads(signature_path.read_text(encoding="utf-8"))
        if signature.get("subject_digest"):
            return str(signature["subject_digest"])
    subjects_path = bundle / artifact_bundles.SUBJECTS_SIDECAR
    if subjects_path.is_file():
        subjects = json.loads(subjects_path.read_text(encoding="utf-8"))
        if subjects.get("aggregate_digest"):
            return str(subjects["aggregate_digest"])
    provenance = json.loads((bundle / artifact_bundles.PROVENANCE_SIDECAR).read_text(encoding="utf-8"))
    return str(provenance["subject"]["digest"])


def _write_fake_c2patool(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path


capture = os.environ.get("FAKE_C2PA_ARGV_CAPTURE")
if capture:
    Path(capture).write_text(json.dumps(sys.argv[1:]) + "\\n", encoding="utf-8")

state = os.environ.get("FAKE_C2PA_STATE")
if state == "invalid":
    print(json.dumps({
        "validation_state": "Invalid",
        "validation_status": [{"code": "assertion.dataHash.mismatch"}],
    }))
    sys.exit(0)
if state == "trusted":
    print(json.dumps({
        "validation_state": "Valid",
        "validation_results": {
            "activeManifest": {
                "success": [{"code": "signingCredential.trusted"}],
                "failure": [],
            }
        },
        "argv": sys.argv[1:],
    }))
    sys.exit(0)
if state == "expired":
    print(json.dumps({
        "validation_state": "Valid",
        "validation_status": [{"code": "signingCredential.expired"}],
        "argv": sys.argv[1:],
    }))
    sys.exit(0)
if state == "revoked":
    print(json.dumps({
        "validation_state": "Valid",
        "validation_status": [{"code": "signingCredential.revoked"}],
        "argv": sys.argv[1:],
    }))
    sys.exit(0)
if state == "no_trust_code":
    print(json.dumps({
        "validation_state": "Valid",
        "validation_status": [],
        "argv": sys.argv[1:],
    }))
    sys.exit(0)
print(json.dumps({
    "validation_state": "Valid",
    "validation_status": [{"code": "signingCredential.untrusted"}],
    "argv": sys.argv[1:],
}))
sys.exit(0)
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_public_source_seed_bundle_roundtrip(tmp_path: Path) -> None:
    bundle = tmp_path / "public-source-seed"

    build = artifact_bundles.build_sidecars_from_manifest(bundle)
    sign = artifact_bundles.sign_bundle(bundle)
    verify = artifact_bundles.verify_bundle(bundle)
    release = artifact_bundles.release_check(bundle, enforcement="blocking")

    assert build["ok"] is True
    assert build["bundle_manifest_ref"] == artifact_bundles.DEFAULT_BUNDLE_MANIFEST_REF
    assert sign["ok"] is True
    assert sign["status"] == "not_required"
    assert verify["ok"] is True
    assert verify["required_controls"] == ["abi_signature"]
    assert verify["verified_controls"] == ["abi_signature"]
    assert release["ok"] is True
    assert (bundle / artifact_bundles.IDENTITY_SIDECAR).is_file()
    assert (bundle / artifact_bundles.ABI_SIDECAR).is_file()
    assert (bundle / artifact_bundles.PROVENANCE_SIDECAR).is_file()
    assert (bundle / artifact_bundles.SIGNATURE_DECISION_SIDECAR).is_file()
    assert (bundle / artifact_bundles.VERIFY_SIDECAR).is_file()


def test_abyss_machine_manifests_declare_full_consumer_registry_path() -> None:
    manifest_dir = ROOT / "manifests" / "artifact_bundles"
    production_trust_root_modes = {
        "bootstrap_install_bundle": "github_oidc",
        "runtime_or_container_artifact": "oci_registry",
        "ai_model_or_runtime_bundle": "oci_registry",
        "browser_extension_package": "public_release",
        "public_media_export": "public_release",
    }

    for manifest_path in sorted(manifest_dir.glob("*.bundle.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        commands = [str(command) for command in manifest["consumer_command"]]
        command_text = " ".join(commands)
        artifact_class = str(manifest.get("artifact_class") or "")
        expected_trust_root_mode = production_trust_root_modes.get(artifact_class, "host_managed")

        assert manifest.get("owner_repo") == "abyss-machine", manifest_path
        assert manifest.get("consumer_contract", {}).get("registry_required") is True, manifest_path
        assert (
            manifest.get("consumer_contract", {}).get("admission_gate")
            == "fail_closed_consumer_admission"
        ), manifest_path
        assert (
            manifest.get("consumer_contract", {}).get("consumer_verdict")
            == "allow_or_deny_required_before_use"
        ), manifest_path
        assert "bundle-registry --artifact-class" not in command_text, manifest_path
        assert "evidence-promote BUNDLE_DIR" in command_text, manifest_path
        assert "--registry-dir REGISTRY_DIR" in command_text, manifest_path
        assert "--source-repo abyss-machine" in command_text, manifest_path
        assert f"--trust-root-mode {expected_trust_root_mode}" in command_text, manifest_path
        if expected_trust_root_mode in artifact_bundles.PRODUCTION_RELEASE_TRUST_ROOT_MODES:
            assert "--trust-root-evidence-json @TRUST_ROOT_EVIDENCE_JSON" in command_text, manifest_path
        else:
            assert "--trust-root-evidence-json" not in command_text, manifest_path
        assert "trust-gate --registry-dir REGISTRY_DIR" in command_text, manifest_path
        assert "registry-latest --registry-dir REGISTRY_DIR" in command_text, manifest_path
        assert "--json" in command_text, manifest_path
        if manifest.get("artifact_subjects"):
            assert manifest.get("consumer_contract", {}).get("subject_store_required") is True, manifest_path
            assert "materialize-subjects BUNDLE_DIR" in command_text, manifest_path
            assert "--store-root SUBJECT_STORE_ROOT" in command_text, manifest_path
        else:
            assert manifest.get("consumer_contract", {}).get("subject_store_required") is False, manifest_path
            assert manifest.get("consumer_contract", {}).get("subject_store_deferred_reason"), manifest_path
            assert "materialize-subjects BUNDLE_DIR" not in command_text, manifest_path


def test_artifact_scenario_matrix_covers_required_os_trust_loop() -> None:
    matrix = artifact_bundles.artifact_scenario_matrix()

    assert matrix["ok"] is True
    assert matrix["schema"] == "abyss_machine_artifact_scenario_matrix_v1"
    assert matrix["summary"]["scenarios"] == 8
    rows = {row["scenario_id"]: row for row in matrix["rows"]}
    assert set(rows) == {
        "bootstrap_install",
        "runtime_container",
        "ai_runtime_model",
        "public_source_seed",
        "public_media_export",
        "eval_report",
        "browser_extension",
        "host_local_evidence",
    }
    assert rows["bootstrap_install"]["artifact_class"] == "bootstrap_install_bundle"
    assert rows["runtime_container"]["consumer_intent"] == "runtime"
    assert rows["ai_runtime_model"]["update_lane_applies"] is True
    assert rows["public_source_seed"]["coverage_tier"] == "synthetic_executable"
    assert rows["host_local_evidence"]["required_controls"] == ["local_provenance"]
    assert rows["eval_report"]["artifact_class"] == "aoa_evals_generated_report_index_bundle"
    assert rows["eval_report"]["coverage_tier"] == "policy_or_owner_declared"
    assert rows["eval_report"]["manual_or_owner_evidence_required"] is True
    assert rows["public_media_export"]["coverage_status"] == "policy_declared_c2pa_binding_tests"
    assert rows["public_media_export"]["manual_or_owner_evidence_required"] is True
    for row in rows.values():
        assert row["agent_loop"]["trust_gate"].startswith("abyss-machine artifacts trust-gate")
        assert row["agent_loop"]["inspect_requirements"].endswith("--json")
        assert row["claim_limit"]
    assert "run trust-gate before any consumer use" in matrix["agent_loop"]
    assert matrix["summary"]["owner_or_manual_evidence_required"] == 2


def test_artifacts_scenarios_cli_writes_latest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    scenarios_root = tmp_path / "scenarios"
    monkeypatch.setattr(cli, "ARTIFACTS_SCENARIOS_ROOT", scenarios_root)
    monkeypatch.setattr(cli, "ARTIFACTS_SCENARIOS_LATEST_PATH", scenarios_root / "latest.json")
    monkeypatch.setattr(cli, "ARTIFACTS_INDEX_PATH", tmp_path / "index.json")

    rc = cli.main(["artifacts", "scenarios", "--scenario-id", "eval_report", "--json"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert rc == 0
    assert data["schema"] == "abyss_machine_artifact_scenario_matrix_v1"
    assert data["scenario_filter"] == "eval_report"
    assert data["rows"][0]["manual_or_owner_evidence_required"] is True
    latest = json.loads((scenarios_root / "latest.json").read_text(encoding="utf-8"))
    assert latest["rows"][0]["scenario_id"] == "eval_report"


@pytest.mark.parametrize(
    ("manifest_ref", "subject_path", "artifact_class", "consumer_intent", "requires_cosign"),
    [
        (
            "manifests/artifact_bundles/bootstrap_install_bundle.bundle.json",
            "dist/abyss-machine-bootstrap-pytest-subject.tar.gz",
            "bootstrap_install_bundle",
            "installer",
            True,
        ),
        (
            "manifests/artifact_bundles/runtime_tools_bundle.bundle.json",
            "dist/abyss-machine-runtime-tools-pytest-subject.tar.gz",
            "runtime_or_container_artifact",
            "runtime",
            True,
        ),
        (
            "manifests/artifact_bundles/ai_runtime_config_bundle.bundle.json",
            "dist/abyss-machine-ai-runtime-config-pytest-subject.tar.gz",
            "ai_model_or_runtime_bundle",
            "runtime",
            True,
        ),
        (
            "manifests/artifact_bundles/browser_extension_package.bundle.json",
            "tools/typing/firefox-extension/build/abyss-machine-typing-firefox-extension-pytest-subject.zip",
            "browser_extension_package",
            "release_consumer",
            False,
        ),
    ],
)
def test_abyss_machine_official_subject_manifests_roundtrip_registry_materialize(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    manifest_ref: str,
    subject_path: str,
    artifact_class: str,
    consumer_intent: str,
    requires_cosign: bool,
) -> None:
    subject = ROOT / subject_path
    subject.parent.mkdir(parents=True, exist_ok=True)
    subject.write_text(f"pytest synthetic subject for {artifact_class}\n", encoding="utf-8")
    bundle = tmp_path / "bundle"
    registry = tmp_path / "registry"
    store_root = tmp_path / "subject-store"
    monkeypatch.setenv("ABYSS_MACHINE_ARTIFACT_SUBJECT_STORE_ROOT", str(store_root))

    if requires_cosign:
        fake_cosign = tmp_path / "cosign"
        _write_fake_cosign(fake_cosign)
        key = tmp_path / "local-test.key"
        public_key = tmp_path / "local-test.pub"
        key.write_text("fake-private-key\n", encoding="utf-8")
        public_key.write_text("fake-public-key\n", encoding="utf-8")
        monkeypatch.setenv("ABYSS_MACHINE_COSIGN_BINARY", str(fake_cosign))
        monkeypatch.setenv("ABYSS_MACHINE_COSIGN_KEY", str(key))
        monkeypatch.setenv("ABYSS_MACHINE_COSIGN_PUB", str(public_key))

    try:
        build = artifact_bundles.build_sidecars(bundle, manifest_ref=manifest_ref)
        sign = artifact_bundles.sign_bundle(bundle, backend="cosign-local-key" if requires_cosign else "policy")
        verify = artifact_bundles.verify_bundle(bundle)
        release = artifact_bundles.release_check(bundle, enforcement="blocking")
        subjects = json.loads((bundle / artifact_bundles.SUBJECTS_SIDECAR).read_text(encoding="utf-8"))
        trust_root_mode = (
            "oci_registry"
            if artifact_class in {"runtime_or_container_artifact", "ai_model_or_runtime_bundle"}
            else "github_oidc"
            if requires_cosign
            else "public_release"
        )
        trust_root_evidence = _trust_root_evidence(
            trust_root_mode,
            subject_digest=str(subjects["aggregate_digest"]),
            source_repo="abyss-machine",
            source_ref=manifest_ref,
        )
        promoted = artifact_bundles.promote_bundle_evidence(
            bundle,
            registry,
            lifecycle_state="release-ready",
            source_repo="abyss-machine",
            source_ref=manifest_ref,
            producer=f"pytest official {artifact_class} manifest",
            trust_root_mode=trust_root_mode,
            trust_root_evidence=trust_root_evidence,
        )
        materialized = artifact_bundles.materialize_artifact_subjects(
            bundle,
            store_root=store_root,
            registry_dir=registry,
            manifest_ref=manifest_ref,
            consumer_intent=consumer_intent,
            expected_source_repo="abyss-machine",
            expected_trust_root_mode=trust_root_mode,
        )
        registered = artifact_bundles.promote_bundle_evidence(
            bundle,
            registry,
            lifecycle_state="release-ready",
            source_repo="abyss-machine",
            source_ref=manifest_ref,
            producer=f"pytest official {artifact_class} manifest",
            trust_root_mode=trust_root_mode,
            trust_root_evidence=trust_root_evidence,
        )
        latest = cli.artifacts_registry_latest(
            artifact_class=artifact_class,
            registry_dir=registry,
            consumer_intent=consumer_intent,
            subject_digest=str(subjects["aggregate_digest"]),
            expected_source_repo="abyss-machine",
            expected_trust_root_mode=trust_root_mode,
        )

        assert build["ok"] is True
        assert sign["ok"] is True
        assert verify["ok"] is True
        assert release["ok"] is True
        assert promoted["ok"] is True
        assert promoted["record"]["source_ref"] == manifest_ref
        assert promoted["record"]["source_repo"] == "abyss-machine"
        assert promoted["record"]["artifact_subject_store"]["ok"] is False
        assert materialized["ok"] is True
        assert materialized["consumer_intent"] == consumer_intent
        assert materialized["materialization_admission"]["verdict"] == "allow"
        assert materialized["materialization_admission"]["reason"] == "only_required_subject_store_missing"
        assert materialized["trust_gate"]["verdict"] == "deny"
        assert artifact_bundles.REQUIRED_SUBJECT_STORE_BLOCKER in materialized["trust_gate"]["blockers"]
        assert registered["ok"] is True
        assert registered["record"]["artifact_subject_store"]["ok"] is True
        assert latest["ok"] is True
        assert latest["trust_gate"]["verdict"] == "allow"
        assert latest["trust_gate"]["inspected_claims"]["trust_root_evidence"]["ok"] is True
        assert any(item["path"] == subject_path for item in subjects["files"])
        assert (store_root / artifact_class / subjects["aggregate_digest"].removeprefix("sha256:")).is_dir()
    finally:
        subject.unlink(missing_ok=True)
        try:
            subject.parent.rmdir()
        except OSError:
            pass


def test_trust_coverage_collects_package_named_evidence_dirs(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "browser-extension-package-20260621T051601Z"
    negative_dir = evidence_dir / "negative"
    negative_dir.mkdir(parents=True)
    positive = evidence_dir / "verify.source.json"
    negative = negative_dir / "missing-slsa.verify.source.json"
    positive.write_text(
        json.dumps(
            {
                "schema": "abyss_machine_artifact_bundle_verify_v1",
                "artifact_class": "browser_extension_package",
                "ok": True,
            }
        ),
        encoding="utf-8",
    )
    negative.write_text(
        json.dumps(
            {
                "schema": "abyss_machine_artifact_bundle_verify_v1",
                "artifact_class": "browser_extension_package",
                "ok": False,
            }
        ),
        encoding="utf-8",
    )

    evidence = cli.artifact_trust_coverage_collect_manual_evidence([str(tmp_path)])

    bucket = evidence["browser_extension_package"]
    assert str(positive) in bucket["positive"]
    assert str(negative) in bucket["negative"]


def _public_source_seed_registry(tmp_path: Path) -> tuple[Path, Path]:
    bundle = tmp_path / "public-source-seed"
    registry = tmp_path / "registry"

    artifact_bundles.build_sidecars_from_manifest(bundle)
    artifact_bundles.sign_bundle(bundle)
    promoted = artifact_bundles.promote_bundle_evidence(
        bundle,
        registry,
        lifecycle_state="release-ready",
        trust_root_mode="host_managed",
    )

    assert promoted["ok"] is True
    return bundle, registry


def _rewrite_latest_record(registry: Path, **updates: object) -> dict[str, object]:
    record_path = next((registry / artifact_bundles.BUNDLE_REGISTRY_RECORDS_DIR).glob("*.json"))
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record.update(updates)
    record_path.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return record


def _write_role_registry_source_manifest(workspace: Path, *, consumer_contract: dict[str, object]) -> Path:
    manifest_dir = workspace / "aoa-agents" / "manifests" / "artifact_bundles"
    manifest_dir.mkdir(parents=True)
    manifest_path = manifest_dir / "role_contract_registry.bundle.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema": "abyss_machine_artifact_bundle_manifest_v1",
                "id": "aoa-agents-role-contract-registry",
                "artifact_class": "role_contract_registry",
                "owner_repo": "aoa-agents",
                "policy_ref": artifact_bundles.POLICY_REF,
                "mode": "os_abyss_local",
                "public_safe": True,
                "subject_repo_root": "../..",
                "abi_subject": {
                    "path": "generated/agent_registry.min.json",
                    "artifact_identity_pointer": "/artifact_identity",
                },
                "consumer_contract": consumer_contract,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest_path


def _write_role_registry_latest(
    registry: Path,
    *,
    consumer_contract: dict[str, object],
    source_repo: str = "aoa-agents",
) -> None:
    subject_store_required = consumer_contract.get("subject_store_required") is True
    record = {
        "schema": "abyss_machine_artifact_bundle_registry_record_v1",
        "record_id": "sha256:" + "c" * 64,
        "artifact_class": "role_contract_registry",
        "bundle_layout": "abyss_machine_artifact_bundle_v1",
        "bundle_ref": "aoa-agents/dist/abyss-artifact-bundle/aoa-agents-role-registry",
        "bundle_manifest_ref": "manifests/artifact_bundles/role_contract_registry.bundle.json",
        "subject_digest": "sha256:" + "d" * 64,
        "lifecycle_state": "release-ready",
        "latest_eligible": True,
        "terminal_state": False,
        "verification_ok": True,
        "verification_errors": [],
        "verification_missing": [],
        "verification_warnings": [],
        "required_controls": ["abi_signature", "slsa_in_toto"],
        "verified_controls": ["abi_signature", "slsa_in_toto"],
        "present_controls": ["abi_signature", "slsa_in_toto"],
        "source_repo": source_repo,
        "source_ref": "manifests/artifact_bundles/role_contract_registry.bundle.json",
        "source_refs": ["manifests/artifact_bundles/role_contract_registry.bundle.json", "commit:current"],
        "producer": "aoa-agents-role-registry-builder",
        "producer_command": "python scripts/validate_abyss_machine_role_registry_bundle.py --json",
        "trust_root_mode": "host_managed",
        "verifier_versions": {"test": "cross-repo-source-freshness"},
        "consumer_contract": consumer_contract,
        "artifact_subject_store": {
            "required": subject_store_required,
            "ok": True,
            "aggregate_digest": "sha256:" + "d" * 64,
            "path_basis": "synthetic_test_evidence",
        },
        "created_at": "2026-06-25T00:00:00Z",
        "policy_ref": artifact_bundles.POLICY_REF,
        "abi_ref": artifact_bundles.ABI_REF,
    }
    records = registry / artifact_bundles.BUNDLE_REGISTRY_RECORDS_DIR
    records.mkdir(parents=True)
    (records / "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc.json").write_text(
        json.dumps(record, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_trust_coverage_blocks_stale_abi_registry_latest(tmp_path: Path) -> None:
    _bundle, registry = _public_source_seed_registry(tmp_path)
    _rewrite_latest_record(registry, abi_subject_digest="sha256:" + "0" * 64)

    coverage = cli.artifacts_trust_coverage(
        registry_dir=registry,
        manual_evidence_roots=[],
        durable_only=True,
        write_latest=False,
    )
    row = next(item for item in coverage["rows"] if item["artifact_class"] == "public_source_seed")

    assert row["installed_verification"]["trust_gate_verdict"] == "allow"
    assert row["source_freshness"]["freshness"] == "stale"
    assert row["source_freshness"]["reasons"] == ["abi_subject_digest_stale"]
    assert row["status"] == "DEFERRED_WITH_REAL_BLOCKER"
    assert "stale against current source contracts" in row["remaining_blocker"]


def test_trust_coverage_blocks_stale_manifest_consumer_contract(tmp_path: Path) -> None:
    _bundle, registry = _public_source_seed_registry(tmp_path)
    _rewrite_latest_record(
        registry,
        consumer_contract={"stable_interface": "abyss-machine artifacts bundle-registry --artifact-class public_source_seed --json"},
    )

    coverage = cli.artifacts_trust_coverage(
        registry_dir=registry,
        manual_evidence_roots=[],
        durable_only=True,
        write_latest=False,
    )
    row = next(item for item in coverage["rows"] if item["artifact_class"] == "public_source_seed")

    assert row["installed_verification"]["trust_gate_verdict"] == "allow"
    assert row["source_freshness"]["freshness"] == "stale"
    assert row["source_freshness"]["reasons"] == ["consumer_contract_stale"]
    assert row["source_freshness"]["current_consumer_contract"]["admission_gate"] == "fail_closed_consumer_admission"
    assert row["status"] == "DEFERRED_WITH_REAL_BLOCKER"


@pytest.mark.parametrize(
    "warning",
    [
        "C2PA signing credential is untrusted; this is local integrity evidence, not production trust-list proof",
        "C2PA signing credential trust was not proven by trust-list validation; this is local integrity evidence, not production trust-list proof",
        "C2PA signing credential is trusted only by configured allowed-list end-entity; this is not production trust-list proof",
        "C2PA trust verdict is not structured; production trust-list status is unproven",
        "C2PA signing credential is trusted by a custom trust anchor store; this is not production C2PA Trust List proof",
        "C2PA production trust anchors are not configured; set ABYSS_MACHINE_C2PA_TRUST_ANCHORS or C2PATOOL_TRUST_ANCHORS before production publication",
    ],
)
def test_trust_coverage_keeps_c2pa_credential_trust_gap_as_production_blocker(warning: str) -> None:
    status, blocker = cli.artifact_trust_coverage_row_status(
        "public_media_export",
        latest={
            "verification_ok": True,
            "verified_controls": ["c2pa"],
        },
        records=[],
        required_controls=["c2pa"],
        manual_positive=["public-media.verify.json"],
        manual_negative=["public-media.tampered-c2pa.verify.json"],
        gate={
            "ok": True,
            "verdict": "warn",
            "warnings": [warning],
        },
    )

    assert status == "DEFERRED_WITH_REAL_BLOCKER"
    assert "C2PA signing credential is not production trust-list trusted" in blocker


def test_trust_coverage_keeps_structured_c2pa_trust_gap_as_production_blocker() -> None:
    status, blocker = cli.artifact_trust_coverage_row_status(
        "public_media_export",
        latest={
            "verification_ok": True,
            "verified_controls": ["c2pa"],
        },
        records=[],
        required_controls=["c2pa"],
        manual_positive=["public-media.verify.json"],
        manual_negative=["public-media.tampered-c2pa.verify.json"],
        gate={
            "ok": True,
            "verdict": "warn",
            "warnings": [],
            "inspected_claims": {
                "c2pa_trust": {
                    "schema": "abyss_machine_c2pa_trust_verdict_v1",
                    "trust_tier": "custom_trust_anchor_store",
                    "production_trust_list_trusted": False,
                },
            },
        },
    )

    assert status == "DEFERRED_WITH_REAL_BLOCKER"
    assert "C2PA signing credential is not production trust-list trusted" in blocker


def test_trust_coverage_checks_cross_repo_manifest_consumer_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = tmp_path / "registry"
    workspace = tmp_path / "workspace"
    consumer_contract = {
        "stable_interface": "abyss-machine artifacts trust-gate --artifact-class role_contract_registry --consumer-intent agent --json",
        "admission_gate": "fail_closed_consumer_admission",
        "subject_store_required": True,
    }
    _write_role_registry_source_manifest(workspace, consumer_contract=consumer_contract)
    _write_role_registry_latest(registry, consumer_contract=consumer_contract)
    monkeypatch.setenv("ABYSS_MACHINE_ARTIFACT_WORKSPACE_ROOTS", str(workspace))

    coverage = cli.artifacts_trust_coverage(
        registry_dir=registry,
        manual_evidence_roots=[],
        durable_only=True,
        write_latest=False,
    )
    row = next(item for item in coverage["rows"] if item["artifact_class"] == "role_contract_registry")

    assert row["source_freshness"]["checked"] is True
    assert row["source_freshness"]["freshness"] == "fresh"
    assert row["source_freshness"]["source_repo"] == "aoa-agents"
    assert row["source_freshness"]["manifest_resolution"]["resolved"] is True
    assert row["source_freshness"]["manifest_resolution"]["path"].endswith(
        "aoa-agents/manifests/artifact_bundles/role_contract_registry.bundle.json"
    )
    assert row["status"] == "DURABLE_GATE_COVERED"


def test_trust_coverage_falls_back_to_durable_source_ref_for_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = tmp_path / "registry"
    workspace = tmp_path / "workspace"
    consumer_contract = {
        "stable_interface": "abyss-machine artifacts trust-gate --artifact-class role_contract_registry --consumer-intent agent --json",
        "admission_gate": "fail_closed_consumer_admission",
        "subject_store_required": True,
    }
    manifest_path = _write_role_registry_source_manifest(workspace, consumer_contract=consumer_contract)
    _write_role_registry_latest(registry, consumer_contract=consumer_contract)
    _rewrite_latest_record(
        registry,
        bundle_manifest_ref="ephemeral/role_contract_registry.bundle.json",
        source_ref=str(manifest_path),
    )
    monkeypatch.setenv("ABYSS_MACHINE_ARTIFACT_WORKSPACE_ROOTS", str(workspace))

    coverage = cli.artifacts_trust_coverage(
        registry_dir=registry,
        manual_evidence_roots=[],
        durable_only=True,
        write_latest=False,
    )
    row = next(item for item in coverage["rows"] if item["artifact_class"] == "role_contract_registry")

    assert row["source_freshness"]["checked"] is True
    assert row["source_freshness"]["freshness"] == "fresh"
    assert row["source_freshness"]["manifest_resolution"]["resolved"] is True
    assert row["source_freshness"]["manifest_resolution"]["path"] == str(manifest_path)
    assert row["status"] == "DURABLE_GATE_COVERED"


def test_trust_coverage_blocks_stale_cross_repo_manifest_consumer_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = tmp_path / "registry"
    workspace = tmp_path / "workspace"
    current_contract = {
        "stable_interface": "abyss-machine artifacts trust-gate --artifact-class role_contract_registry --consumer-intent agent --json",
        "admission_gate": "fail_closed_consumer_admission",
        "subject_store_required": True,
    }
    stale_contract = {
        "stable_interface": "abyss-machine artifacts bundle-registry --artifact-class role_contract_registry --json",
        "admission_gate": "fail_closed_consumer_admission",
        "subject_store_required": True,
    }
    _write_role_registry_source_manifest(workspace, consumer_contract=current_contract)
    _write_role_registry_latest(registry, consumer_contract=stale_contract)
    monkeypatch.setenv("ABYSS_MACHINE_ARTIFACT_WORKSPACE_ROOTS", str(workspace))

    coverage = cli.artifacts_trust_coverage(
        registry_dir=registry,
        manual_evidence_roots=[],
        durable_only=True,
        write_latest=False,
    )
    row = next(item for item in coverage["rows"] if item["artifact_class"] == "role_contract_registry")

    assert row["source_freshness"]["freshness"] == "stale"
    assert row["source_freshness"]["reasons"] == ["consumer_contract_stale"]
    assert row["source_freshness"]["current_consumer_contract"] == current_contract
    assert row["source_freshness"]["latest_consumer_contract"] == stale_contract
    assert row["status"] == "DEFERRED_WITH_REAL_BLOCKER"


def test_trust_coverage_blocks_unresolved_cross_repo_manifest(tmp_path: Path) -> None:
    registry = tmp_path / "registry"
    consumer_contract = {
        "stable_interface": "abyss-machine artifacts trust-gate --artifact-class role_contract_registry --consumer-intent agent --json",
        "admission_gate": "fail_closed_consumer_admission",
        "subject_store_required": True,
    }
    _write_role_registry_latest(registry, consumer_contract=consumer_contract, source_repo="aoa-agents-missing")

    coverage = cli.artifacts_trust_coverage(
        registry_dir=registry,
        manual_evidence_roots=[],
        durable_only=True,
        write_latest=False,
    )
    row = next(item for item in coverage["rows"] if item["artifact_class"] == "role_contract_registry")

    assert row["source_freshness"]["freshness"] == "stale"
    assert row["source_freshness"]["reasons"] == ["source_manifest_unresolved"]
    assert row["status"] == "DEFERRED_WITH_REAL_BLOCKER"


def _build_public_media_export_test_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    fake_state: str | None = None,
    trust_anchors: str | None = None,
    trust_anchors_ref: str | None = None,
    trust_anchors_profile: str | None = None,
    allowed_list: str | None = None,
    capture_argv: bool = False,
) -> tuple[Path, Path | None]:
    asset = tmp_path / "media.png"
    asset.write_bytes(b"not-a-real-png-for-fake-c2pa")
    manifest = tmp_path / "public_media_export.bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": "abyss_machine_artifact_bundle_manifest_v1",
                "id": "public-media-export-test",
                "artifact_class": "public_media_export",
                "owner_repo": "abyss-machine",
                "policy_ref": artifact_bundles.POLICY_REF,
                "mode": "os_abyss_local",
                "public_safe": True,
                "subject_repo_root": ".",
                "artifact_subjects": [{"path": "media.png", "role": "public_media_export"}],
                "c2pa": {
                    "manifest_sidecar": artifact_bundles.C2PA_MANIFEST_SIDECAR,
                    "validation_report": artifact_bundles.C2PA_REPORT_SIDECAR,
                    "required_validation_state": "Valid",
                },
            }
        ),
        encoding="utf-8",
    )
    fake_c2pa = tmp_path / "c2patool"
    _write_fake_c2patool(fake_c2pa)
    monkeypatch.setenv("ABYSS_MACHINE_C2PATOOL_BINARY", str(fake_c2pa))
    if fake_state:
        monkeypatch.setenv("FAKE_C2PA_STATE", fake_state)
    else:
        monkeypatch.delenv("FAKE_C2PA_STATE", raising=False)
    if trust_anchors_ref is not None:
        monkeypatch.setenv(artifact_bundles.C2PA_TRUST_ANCHORS_ENV, trust_anchors_ref)
    elif trust_anchors is not None:
        anchors = tmp_path / "c2pa-trust-anchors.pem"
        anchors.write_text(trust_anchors, encoding="utf-8")
        monkeypatch.setenv(artifact_bundles.C2PA_TRUST_ANCHORS_ENV, str(anchors))
    else:
        monkeypatch.delenv(artifact_bundles.C2PA_TRUST_ANCHORS_ENV, raising=False)
        monkeypatch.delenv("C2PATOOL_TRUST_ANCHORS", raising=False)
    if trust_anchors_profile is not None:
        monkeypatch.setenv(artifact_bundles.C2PA_TRUST_ANCHORS_PROFILE_ENV, trust_anchors_profile)
    else:
        monkeypatch.delenv(artifact_bundles.C2PA_TRUST_ANCHORS_PROFILE_ENV, raising=False)
    if allowed_list is not None:
        allowed = tmp_path / "c2pa-allowed-list.pem"
        allowed.write_text(allowed_list, encoding="utf-8")
        monkeypatch.setenv(artifact_bundles.C2PA_ALLOWED_LIST_ENV, str(allowed))
    else:
        monkeypatch.delenv(artifact_bundles.C2PA_ALLOWED_LIST_ENV, raising=False)
        monkeypatch.delenv("C2PATOOL_ALLOWED_LIST", raising=False)
    argv_capture = tmp_path / "c2pa-argv.json" if capture_argv else None
    if argv_capture is not None:
        monkeypatch.setenv("FAKE_C2PA_ARGV_CAPTURE", str(argv_capture))
    else:
        monkeypatch.delenv("FAKE_C2PA_ARGV_CAPTURE", raising=False)
    bundle = tmp_path / "bundle"

    artifact_bundles.build_sidecars(bundle, manifest_ref=manifest)
    artifact_bundles.sign_bundle(bundle)
    (bundle / artifact_bundles.C2PA_MANIFEST_SIDECAR).write_bytes(b"fake-c2pa")
    (bundle / artifact_bundles.C2PA_REPORT_SIDECAR).write_text(
        json.dumps({"validation_state": "Valid"}),
        encoding="utf-8",
    )
    return bundle, argv_capture


def test_public_media_export_verifies_c2pa_asset_binding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle, argv_capture = _build_public_media_export_test_bundle(tmp_path, monkeypatch, capture_argv=True)

    verify = artifact_bundles.verify_bundle(bundle)
    assert verify["ok"] is True
    assert "c2pa" in verify["verified_controls"]
    assert any("untrusted" in warning for warning in verify["warnings"])
    assert verify["control_evidence"]["c2pa"]["trust"]["trust_tier"] == "untrusted"
    assert verify["control_evidence"]["c2pa"]["trust"]["production_trust_list_trusted"] is False
    assert argv_capture is not None
    argv = json.loads(argv_capture.read_text(encoding="utf-8"))
    assert "trust" in argv

    monkeypatch.setenv("FAKE_C2PA_STATE", "invalid")
    invalid = artifact_bundles.verify_bundle(bundle)
    assert invalid["ok"] is False
    assert invalid["verified_controls"] == []
    assert "c2pa" in invalid["present_controls"]
    assert any("asset hash mismatch" in error for error in invalid["errors"])


def test_public_media_export_rejects_missing_c2pa_manifest_sidecar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle, _ = _build_public_media_export_test_bundle(tmp_path, monkeypatch)
    (bundle / artifact_bundles.C2PA_MANIFEST_SIDECAR).unlink()

    verify = artifact_bundles.verify_bundle(bundle)

    assert verify["ok"] is False
    assert "c2pa" in verify["present_controls"]
    assert any("C2PA manifest sidecar is missing" in error for error in verify["errors"])
    assert verify["verified_controls"] == []


def test_public_media_export_passes_without_production_warning_when_c2pa_credential_trusted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle, argv_capture = _build_public_media_export_test_bundle(
        tmp_path,
        monkeypatch,
        fake_state="trusted",
        trust_anchors_ref=artifact_bundles.C2PA_OFFICIAL_TRUST_LIST_URL,
        capture_argv=True,
    )

    verify = artifact_bundles.verify_bundle(bundle)

    assert verify["ok"] is True
    assert "c2pa" in verify["verified_controls"]
    assert not any("production trust-list proof" in warning for warning in verify["warnings"])
    assert not any("production trust anchors are not configured" in warning for warning in verify["warnings"])
    c2pa_trust = verify["control_evidence"]["c2pa"]["trust"]
    assert c2pa_trust["trust_tier"] == "production_trust_list"
    assert c2pa_trust["production_trust_list_configured"] is True
    assert c2pa_trust["production_trust_list_trusted"] is True
    assert c2pa_trust["trust_anchor_profile"] == "official_c2pa_trust_list"
    assert argv_capture is not None
    argv = json.loads(argv_capture.read_text(encoding="utf-8"))
    assert "trust" in argv
    assert "--trust_anchors" in argv
    assert artifact_bundles.C2PA_OFFICIAL_TRUST_LIST_URL in argv


def test_public_media_export_custom_trust_anchors_are_not_production_trust_list(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle, argv_capture = _build_public_media_export_test_bundle(
        tmp_path,
        monkeypatch,
        fake_state="trusted",
        trust_anchors="-----BEGIN CERTIFICATE-----\\npytest\\n-----END CERTIFICATE-----\\n",
        capture_argv=True,
    )

    verify = artifact_bundles.verify_bundle(bundle)

    assert verify["ok"] is True
    assert "c2pa" in verify["verified_controls"]
    assert any("custom trust anchor store" in warning for warning in verify["warnings"])
    c2pa_trust = verify["control_evidence"]["c2pa"]["trust"]
    assert c2pa_trust["trust_tier"] == "custom_trust_anchor_store"
    assert c2pa_trust["trust_anchor_profile"] == "custom_trust_anchor_store"
    assert c2pa_trust["production_trust_list_configured"] is False
    assert c2pa_trust["production_trust_list_trusted"] is False
    assert argv_capture is not None
    argv = json.loads(argv_capture.read_text(encoding="utf-8"))
    assert "--trust_anchors" in argv
    assert str(tmp_path / "c2pa-trust-anchors.pem") in argv


def test_public_media_export_allowed_list_trust_is_not_production_trust_list(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle, argv_capture = _build_public_media_export_test_bundle(
        tmp_path,
        monkeypatch,
        fake_state="trusted",
        allowed_list="pytest-end-entity\n",
        capture_argv=True,
    )

    verify = artifact_bundles.verify_bundle(bundle)

    assert verify["ok"] is True
    assert "c2pa" in verify["verified_controls"]
    assert any("allowed-list end-entity" in warning for warning in verify["warnings"])
    c2pa_trust = verify["control_evidence"]["c2pa"]["trust"]
    assert c2pa_trust["trust_tier"] == "allowed_list_end_entity"
    assert c2pa_trust["allowed_list_end_entity_configured"] is True
    assert c2pa_trust["production_trust_list_trusted"] is False
    assert argv_capture is not None
    argv = json.loads(argv_capture.read_text(encoding="utf-8"))
    assert "--allowed_list" in argv
    assert str(tmp_path / "c2pa-allowed-list.pem") in argv


def test_public_media_export_warns_when_c2pa_credential_trust_is_not_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle, _ = _build_public_media_export_test_bundle(
        tmp_path,
        monkeypatch,
        fake_state="no_trust_code",
    )

    verify = artifact_bundles.verify_bundle(bundle)

    assert verify["ok"] is True
    assert any("trust was not proven by trust-list validation" in warning for warning in verify["warnings"])
    assert any("production trust anchors are not configured" in warning for warning in verify["warnings"])
    assert verify["control_evidence"]["c2pa"]["trust"]["trust_tier"] == "not_reported"


@pytest.mark.parametrize(
    ("fake_state", "expected_error"),
    [
        ("expired", "signing credential is expired"),
        ("revoked", "signing credential is revoked"),
    ],
)
def test_public_media_export_rejects_expired_or_revoked_c2pa_credential(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_state: str,
    expected_error: str,
) -> None:
    bundle, _ = _build_public_media_export_test_bundle(
        tmp_path,
        monkeypatch,
        fake_state=fake_state,
        trust_anchors="-----BEGIN CERTIFICATE-----\\npytest\\n-----END CERTIFICATE-----\\n",
    )

    verify = artifact_bundles.verify_bundle(bundle)

    assert verify["ok"] is False
    assert "c2pa" in verify["present_controls"]
    assert any(expected_error in error for error in verify["errors"])


def _write_public_media_registry_record(
    registry: Path,
    *,
    c2pa_trust: dict[str, object],
    verification_warnings: list[str] | None = None,
) -> dict[str, object]:
    source_ref = "manifests/artifact_bundles/public_media_export.bundle.json"
    subject_digest = "sha256:" + ("e" * 64)
    record_id = "sha256:" + ("f" * 64)
    record = {
        "schema": "abyss_machine_artifact_bundle_registry_record_v1",
        "record_id": record_id,
        "artifact_class": "public_media_export",
        "bundle_layout": "abyss_machine_artifact_bundle_v1",
        "bundle_ref": "public-media/export-bundle",
        "bundle_manifest_ref": source_ref,
        "subject_digest": subject_digest,
        "lifecycle_state": "release-ready",
        "latest_eligible": True,
        "terminal_state": False,
        "verification_ok": True,
        "verification_errors": [],
        "verification_missing": [],
        "verification_warnings": verification_warnings or [],
        "required_controls": ["c2pa"],
        "verified_controls": ["c2pa"],
        "present_controls": ["c2pa"],
        "source_repo": "abyss-machine",
        "source_ref": source_ref,
        "source_refs": [source_ref],
        "producer": "pytest-public-media-export",
        "producer_command": "pytest public media fixture",
        "trust_root_mode": "public_release",
        "trust_root_evidence": _trust_root_evidence(
            "public_release",
            subject_digest=subject_digest,
            source_repo="abyss-machine",
            source_ref=source_ref,
        ),
        "verifier_versions": {"pytest": "public-media-c2pa"},
        "privacy_boundary": "public-safe media export test fixture",
        "artifact_subject_store": {"required": False, "ok": True, "aggregate_digest": subject_digest},
        "consumer_contract": {"admission_gate": "fail_closed_consumer_admission", "subject_store_required": False},
        "control_evidence": {"c2pa": {"trust": c2pa_trust}},
        "c2pa_trust": c2pa_trust,
        "created_at": "2026-06-25T00:00:00Z",
        "policy_ref": artifact_bundles.POLICY_REF,
        "abi_ref": artifact_bundles.ABI_REF,
    }
    records = registry / artifact_bundles.BUNDLE_REGISTRY_RECORDS_DIR
    records.mkdir(parents=True, exist_ok=True)
    (records / f"{record_id.removeprefix('sha256:')}.json").write_text(
        json.dumps(record, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return record


def test_trust_gate_warns_on_allowed_list_c2pa_from_structured_verdict(tmp_path: Path) -> None:
    c2pa_trust = {
        "schema": "abyss_machine_c2pa_trust_verdict_v1",
        "validation_state": "Valid",
        "credential_status": "trusted",
        "trust_tier": "allowed_list_end_entity",
        "production_trust_list_configured": False,
        "production_trust_list_trusted": False,
        "allowed_list_end_entity_configured": True,
        "trust_sources": {"allowed_list": "ABYSS_MACHINE_C2PA_ALLOWED_LIST"},
        "status_codes": ["signingCredential.trusted"],
    }
    _write_public_media_registry_record(tmp_path / "registry", c2pa_trust=c2pa_trust)

    gate = artifact_bundles.trust_gate(
        tmp_path / "registry",
        artifact_class="public_media_export",
        consumer_intent="release_consumer",
        expected_trust_root_mode="public_release",
    )

    assert gate["ok"] is True
    assert gate["verdict"] == "warn"
    assert gate["manual_review"] == []
    assert any("allowed-list end-entity" in warning for warning in gate["warnings"])
    assert gate["inspected_claims"]["c2pa_trust"]["trust_tier"] == "allowed_list_end_entity"


def test_trust_gate_allows_public_media_with_production_c2pa_trust_list(tmp_path: Path) -> None:
    c2pa_trust = {
        "schema": "abyss_machine_c2pa_trust_verdict_v1",
        "validation_state": "Valid",
        "credential_status": "trusted",
        "trust_tier": "production_trust_list",
        "production_trust_list_configured": True,
        "production_trust_list_trusted": True,
        "allowed_list_end_entity_configured": False,
        "trust_anchor_profile": "official_c2pa_trust_list",
        "trust_sources": {
            "trust_anchors": "ABYSS_MACHINE_C2PA_TRUST_ANCHORS",
            "trust_anchors_ref": artifact_bundles.C2PA_OFFICIAL_TRUST_LIST_URL,
            "trust_anchors_profile": "official_c2pa_trust_list",
            "trust_anchors_profile_source": "auto:official_c2pa_trust_list_url",
        },
        "status_codes": ["signingCredential.trusted"],
    }
    _write_public_media_registry_record(tmp_path / "registry", c2pa_trust=c2pa_trust)

    gate = artifact_bundles.trust_gate(
        tmp_path / "registry",
        artifact_class="public_media_export",
        consumer_intent="release_consumer",
        expected_trust_root_mode="public_release",
    )

    assert gate["ok"] is True
    assert gate["verdict"] == "allow"
    assert gate["warnings"] == []
    assert gate["inspected_claims"]["c2pa_trust"]["production_trust_list_trusted"] is True


def test_artifact_requirements_reports_sibling_producer_profile() -> None:
    requirements = artifact_bundles.artifact_requirements("aoa_sdk_python_distribution")
    row = requirements["rows"][0]

    assert requirements["ok"] is True
    assert requirements["schema"] == "abyss_machine_artifact_requirements_v1"
    assert row["owner_repo"] == "aoa-sdk"
    assert row["producer_profile"]["producer"]
    assert row["producer_profile"]["automation_profile_ids"] == ["aoa-sdk"]
    assert row["producer_profiles"][0]["owner_repo"] == "aoa-sdk"
    assert row["producer_profiles"][0]["release_export_triggers"]
    assert row["source_route"]["contract_surface_status"] == "external_subject_or_owner_bundle_required"
    assert row["controls"]["required"] == ["abi_signature", "sbom", "slsa_in_toto"]
    assert row["controls"]["deferred"]["sigstore_cosign"]["required"] is False
    assert row["trust_roots"]["local_dev"]["production_consumer_result"] == "manual_review_required"
    assert "producer_profiles" in row["agent_loop"]
    assert "affected" in row["agent_loop"]
    assert "GitHub OIDC is one producer adapter" in row["claim_limits"][2]


def test_artifact_producer_profiles_cover_os_abyss_owner_repos() -> None:
    profiles = artifact_bundles.artifact_producer_profiles()
    rows = profiles["rows"]
    owners = {row["owner_repo"] for row in rows}

    assert profiles["ok"] is True
    assert profiles["schema"] == "abyss_machine_artifact_producer_profiles_v1"
    assert {
        "abyss-machine",
        "abyss-stack",
        "aoa-agents",
        "aoa-evals",
        "aoa-kag",
        "aoa-memo",
        "aoa-playbooks",
        "aoa-routing",
        "aoa-sdk",
        "aoa-session-memory",
        "aoa-skills",
        "aoa-stats",
        "aoa-techniques",
        "Dionysus",
        "Tree-of-Sophia",
    } <= owners
    assert profiles["summary"]["artifact_class_count"] == 21
    assert "producer_profiles" in profiles["agent_loop"]
    assert all(row["validator_commands"] for row in rows)
    assert all(row["produced_sidecars"] for row in rows)
    assert all(row["consumer_expectations"] for row in rows)
    assert all(row["owner_boundaries"] for row in rows)


def test_artifact_producer_profiles_filter_by_artifact_class() -> None:
    profiles = artifact_bundles.artifact_producer_profiles(artifact_class="public_media_export")

    assert profiles["ok"] is True
    assert {row["owner_repo"] for row in profiles["rows"]} >= {
        "abyss-machine",
        "Tree-of-Sophia",
        "Dionysus",
        "aoa-evals",
    }


def test_artifact_affected_marks_contract_source_as_stale(tmp_path: Path) -> None:
    bundle = tmp_path / "public-source-seed"
    registry = tmp_path / "registry"

    artifact_bundles.build_sidecars_from_manifest(bundle)
    artifact_bundles.sign_bundle(bundle)
    artifact_bundles.promote_bundle_evidence(
        bundle,
        registry,
        lifecycle_state="release-ready",
        trust_root_mode="host_managed",
    )

    affected = artifact_bundles.artifact_affected(
        ["src/abyss_machine/artifact_bundles.py"],
        artifact_class="public_source_seed",
        registry_dir=registry,
    )
    row = affected["rows"][0]

    assert affected["ok"] is True
    assert affected["schema"] == "abyss_machine_artifact_affected_v1"
    assert affected["summary"]["status_counts"] == {"needs_rebuild": 1}
    assert row["affected"] is True
    assert row["verdict"] == "needs_rebuild"
    assert row["freshness"] == "stale"
    assert row["registry"]["has_latest"] is True
    assert row["trust_gate"]["verdict"] == "allow"
    assert row["matches"][0]["matched_ref"] == "src/abyss_machine"


def test_artifact_affected_marks_missing_registry_latest_as_stale(tmp_path: Path) -> None:
    affected = artifact_bundles.artifact_affected(
        [],
        artifact_class="public_source_seed",
        registry_dir=tmp_path / "empty-registry",
    )
    row = affected["rows"][0]

    assert affected["ok"] is True
    assert row["affected"] is True
    assert row["verdict"] == "needs_rebuild"
    assert row["freshness"] == "stale"
    assert row["reasons"] == []
    assert row["registry"]["has_latest"] is False
    assert row["drift"]["status"] == "missing_durable_evidence"
    assert row["drift"]["operationally_blocking"] is True
    assert row["drift"]["evidence_state"] == "durable_latest_missing"


def test_artifact_affected_policy_change_requires_all_classes_to_reverify() -> None:
    affected = artifact_bundles.artifact_affected(["manifests/artifact_signature_policy.manifest.json"])

    assert affected["ok"] is True
    assert affected["summary"]["artifact_classes"] == 21
    assert affected["summary"]["status_counts"] == {"needs_reverify": 21}
    assert all(row["freshness"] == "stale" for row in affected["rows"])
    assert all(row["reasons"] == ["policy_manifest_changed"] for row in affected["rows"])


def test_artifact_affected_distinguishes_sibling_lag() -> None:
    blocked = artifact_bundles.artifact_affected(
        [],
        artifact_class="aoa_sdk_python_distribution",
        changed_source_repo="aoa-sdk",
    )
    accepted = artifact_bundles.artifact_affected(
        [],
        artifact_class="aoa_sdk_python_distribution",
        changed_source_repo="aoa-sdk",
        accept_sibling_lag=True,
    )

    assert blocked["rows"][0]["verdict"] == "blocked_by_missing_sibling"
    assert blocked["rows"][0]["next_actions"][1] == "run the producer profile in owner repo aoa-sdk"
    assert blocked["rows"][0]["drift"]["status"] == "blocked_missing_sibling"
    assert blocked["rows"][0]["drift"]["operationally_blocking"] is True
    assert blocked["rows"][0]["drift"]["lag_policy"] == "blocked"
    assert accepted["rows"][0]["verdict"] == "accepted_lag"
    assert accepted["accept_sibling_lag"] is True
    assert accepted["rows"][0]["drift"]["status"] == "accepted_lag"
    assert accepted["rows"][0]["drift"]["operationally_blocking"] is False
    assert accepted["rows"][0]["drift"]["lag_policy"] == "accepted"
    assert accepted["summary"]["accepted_lag"] == 1


def test_artifact_affected_infers_sibling_repo_from_absolute_path() -> None:
    affected = artifact_bundles.artifact_affected(
        ["/srv/AbyssOS/bundles/aoa-session-memory/src/aoa_session_memory.py"],
        artifact_class="aoa_session_memory_portable_bundle",
    )
    row = affected["rows"][0]

    assert affected["changed_source_repo"] == "aoa-session-memory"
    assert affected["changed_source_repo_inferred"] == "aoa-session-memory"
    assert affected["changed_paths"] == ["src/aoa_session_memory.py"]
    assert affected["changed_path_analysis"][0]["source_repo_inferred"] is True
    assert row["changed_source_repo"] == "aoa-session-memory"
    assert row["changed_source_repo_inferred"] == "aoa-session-memory"
    assert row["verdict"] == "blocked_by_missing_sibling"
    assert row["drift"]["status"] == "blocked_missing_sibling"
    assert row["drift"]["source_ref_state"] == "not_requested"
    assert row["drift"]["operationally_blocking"] is True


def test_artifact_affected_keeps_raw_to_normalized_path_mapping_for_sibling_paths() -> None:
    affected = artifact_bundles.artifact_affected(
        [
            "/srv/AbyssOS/aoa-sdk/pyproject.toml",
            "/srv/AbyssOS/aoa-sdk/sdk/distribution/package-contract/README.md",
        ],
        artifact_class="aoa_sdk_python_distribution",
    )

    assert affected["changed_source_repo"] == "aoa-sdk"
    assert affected["changed_paths"] == [
        "pyproject.toml",
        "sdk/distribution/package-contract/README.md",
    ]
    assert [
        (row["raw"], row["normalized"])
        for row in affected["changed_path_analysis"]
    ] == [
        ("/srv/AbyssOS/aoa-sdk/pyproject.toml", "pyproject.toml"),
        (
            "/srv/AbyssOS/aoa-sdk/sdk/distribution/package-contract/README.md",
            "sdk/distribution/package-contract/README.md",
        ),
    ]


def test_artifact_affected_detects_profile_owner_for_shared_media_class() -> None:
    affected = artifact_bundles.artifact_affected(
        ["ToS/derived-exports/root_entry_map.min.json"],
        artifact_class="public_media_export",
        changed_source_repo="Tree-of-Sophia",
    )
    row = affected["rows"][0]

    assert row["verdict"] == "blocked_by_missing_sibling"
    assert row["freshness"] == "stale"
    assert "producer_profile_owner_changed" in row["reasons"]
    assert row["matches"][0]["reason"] == "producer_profile_route_changed"
    assert row["next_actions"][1] == "run the producer profile in owner repo Tree-of-Sophia"


def _write_verified_registry_record(registry: Path, *, evidence_refs: list[str]) -> None:
    record = {
        "schema": "abyss_machine_artifact_bundle_registry_record_v1",
        "record_id": "sha256:" + "a" * 64,
        "artifact_class": "aoa_sdk_python_distribution",
        "bundle_layout": "abyss_machine_artifact_bundle_v1",
        "bundle_ref": "aoa-sdk/dist/abyss-artifact-bundle",
        "bundle_manifest_ref": "sdk/distribution/manifests/python_distribution.bundle.json",
        "subject_digest": "sha256:" + "b" * 64,
        "lifecycle_state": "release-ready",
        "latest_eligible": True,
        "terminal_state": False,
        "verification_ok": True,
        "verification_errors": [],
        "verification_missing": [],
        "verification_warnings": [],
        "required_controls": ["abi_signature", "sbom", "slsa_in_toto"],
        "verified_controls": ["abi_signature", "sbom", "slsa_in_toto"],
        "present_controls": ["abi_signature", "sbom", "slsa_in_toto"],
        "source_repo": "aoa-sdk",
        "source_ref": "sdk/distribution/manifests/python_distribution.bundle.json",
        "source_refs": [
            "sdk/distribution/manifests/python_distribution.bundle.json",
            *evidence_refs,
        ],
        "producer": "aoa-sdk:release-audit-publish-helper@commit:current",
        "producer_command": "python mechanics/release-support/parts/release-audit-publish-helper/scripts/validate_abyss_machine_package_artifact_bundle.py --json",
        "trust_root_mode": "host_managed",
        "verifier_versions": {"test": "source-ref-freshness"},
        "evidence_refs": evidence_refs,
        "created_at": "2026-06-21T00:00:00Z",
        "policy_ref": artifact_bundles.POLICY_REF,
        "abi_ref": artifact_bundles.ABI_REF,
    }
    records = registry / artifact_bundles.BUNDLE_REGISTRY_RECORDS_DIR
    records.mkdir(parents=True)
    (records / "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.json").write_text(
        json.dumps(record, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_artifact_affected_source_ref_closes_sibling_lag_after_promotion(tmp_path: Path) -> None:
    registry = tmp_path / "registry"
    _write_verified_registry_record(registry, evidence_refs=["commit:current"])

    affected = artifact_bundles.artifact_affected(
        ["sdk/distribution/manifests/python_distribution.bundle.json"],
        artifact_class="aoa_sdk_python_distribution",
        changed_source_repo="aoa-sdk",
        changed_source_ref="commit:current",
        registry_dir=registry,
    )
    row = affected["rows"][0]

    assert affected["summary"]["status_counts"] == {"fresh": 1}
    assert row["affected"] is False
    assert row["verdict"] == "fresh"
    assert row["freshness"] == "fresh"
    assert row["source_ref_status"]["matched"] is True
    assert row["source_ref_status"]["matched_ref"] == "commit:current"
    assert row["drift"]["status"] == "fresh"
    assert row["drift"]["operationally_blocking"] is False
    assert row["drift"]["source_ref_state"] == "proved_current"
    assert row["registry"]["latest_record_id"] == "sha256:" + "a" * 64
    assert row["trust_gate"]["verdict"] == "allow"
    assert row["next_actions"] == [
        "abyss-machine artifacts requirements --artifact-class aoa_sdk_python_distribution --json"
    ]


def test_artifact_affected_wrong_source_ref_keeps_sibling_blocked(tmp_path: Path) -> None:
    registry = tmp_path / "registry"
    _write_verified_registry_record(registry, evidence_refs=["commit:previous"])

    affected = artifact_bundles.artifact_affected(
        ["sdk/distribution/manifests/python_distribution.bundle.json"],
        artifact_class="aoa_sdk_python_distribution",
        changed_source_repo="aoa-sdk",
        changed_source_ref="commit:current",
        registry_dir=registry,
    )
    row = affected["rows"][0]

    assert row["affected"] is True
    assert row["verdict"] == "blocked_by_missing_sibling"
    assert row["freshness"] == "stale"
    assert row["reasons"] == ["owner_repo_changed"]
    assert row["source_ref_status"]["matched"] is False
    assert row["source_ref_status"]["expected"] == "commit:current"
    assert row["source_ref_status"]["known_refs"]
    assert row["next_actions"][1] == "run the producer profile in owner repo aoa-sdk"


def test_artifact_affected_scopes_sibling_paths_to_matching_owner_repo() -> None:
    local = artifact_bundles.artifact_affected(
        ["manifests/artifact_bundles/portable_bundle.bundle.json"],
        artifact_class="public_source_seed",
        changed_source_repo="aoa-session-memory",
    )
    sibling = artifact_bundles.artifact_affected(
        ["manifests/artifact_bundles/portable_bundle.bundle.json"],
        artifact_class="aoa_session_memory_portable_bundle",
        changed_source_repo="aoa-session-memory",
    )
    local_policy_path_from_sibling = artifact_bundles.artifact_affected(
        ["manifests/artifact_signature_policy.manifest.json"],
        artifact_class="public_source_seed",
        changed_source_repo="aoa-session-memory",
    )

    assert local["rows"][0]["verdict"] == "fresh"
    assert local["rows"][0]["reasons"] == []
    assert local["rows"][0]["matches"] == []
    assert sibling["rows"][0]["verdict"] == "blocked_by_missing_sibling"
    assert sibling["rows"][0]["reasons"] == ["owner_repo_changed"]
    assert local_policy_path_from_sibling["rows"][0]["verdict"] == "fresh"
    assert local_policy_path_from_sibling["rows"][0]["reasons"] == []


def _update_metadata(**overrides: object) -> dict[str, object]:
    metadata: dict[str, object] = {
        "schema": "abyss_machine_tuf_update_metadata_v1",
        "artifact_class": "bootstrap_install_bundle",
        "target": {
            "path": "dist/abyss-machine-bootstrap-2026.06.21.tar.gz",
            "sha256": "sha256:" + ("a" * 64),
        },
        "version": 2,
        "snapshot_version": 2,
        "timestamp_version": 2,
        "generated_at": "2026-06-21T00:00:00Z",
        "expires_at": "2026-06-28T00:00:00Z",
    }
    metadata.update(overrides)
    return metadata


def _canonical_tuf_bytes(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _write_tuf_json(path: Path, payload: dict[str, object]) -> tuple[str, int]:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _tuf_role(
    role: str,
    signed: dict[str, object],
    signing_keys: dict[str, Ed25519PrivateKey],
    *,
    keyid: str | None = None,
    extra_signatures: dict[str, Ed25519PrivateKey] | None = None,
    tamper_signature: bool = False,
) -> dict[str, object]:
    signed_payload = {
        "_type": role,
        "spec_version": "1.0.31",
        **signed,
    }
    signature = signing_keys[role].sign(_canonical_tuf_bytes(signed_payload)).hex()
    if tamper_signature:
        signature = ("00" if signature[:2] != "00" else "ff") + signature[2:]
    signatures = [{"keyid": keyid or f"{role}-key", "sig": signature}]
    for extra_keyid, extra_key in (extra_signatures or {}).items():
        signatures.append({"keyid": extra_keyid, "sig": extra_key.sign(_canonical_tuf_bytes(signed_payload)).hex()})
    return {
        "signed": signed_payload,
        "signatures": signatures,
    }


def _write_tuf_repository(
    tmp_path: Path,
    *,
    target_path: str = "dist/abyss-machine-bootstrap-pytest-update-target.tar.gz",
    role_versions: dict[str, int] | None = None,
    role_expires: dict[str, str] | None = None,
    key_prefix: str = "",
    extra_root_signatures: dict[str, Ed25519PrivateKey] | None = None,
    tamper_signature_role: str = "",
) -> dict[str, object]:
    repo = tmp_path / "tuf-repository"
    metadata_dir = repo / "metadata"
    targets_dir = repo / "targets"
    versions = {"root": 2, "targets": 2, "snapshot": 2, "timestamp": 2}
    versions.update(role_versions or {})
    expires = {
        "root": "2027-06-21T00:00:00Z",
        "targets": "2027-06-21T00:00:00Z",
        "snapshot": "2026-06-28T00:00:00Z",
        "timestamp": "2026-06-28T00:00:00Z",
    }
    expires.update(role_expires or {})
    target_file = targets_dir / target_path
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_bytes(b"pytest bootstrap update target\n")
    target_hash = hashlib.sha256(target_file.read_bytes()).hexdigest()
    target_length = target_file.stat().st_size
    signing_keys = {
        role: Ed25519PrivateKey.generate()
        for role in ("root", "targets", "snapshot", "timestamp")
    }
    public_keys = {
        role: signing_keys[role].public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex()
        for role in signing_keys
    }

    root = _tuf_role(
        "root",
        {
            "version": versions["root"],
            "expires": expires["root"],
            "keys": {
                f"{key_prefix}{role}-key": {
                    "keytype": "ed25519",
                    "scheme": "ed25519",
                    "keyval": {"public": public_keys[role]},
                }
                for role in ("root", "targets", "snapshot", "timestamp")
            },
            "roles": {
                role: {"keyids": [f"{key_prefix}{role}-key"], "threshold": 1}
                for role in ("root", "targets", "snapshot", "timestamp")
            },
        },
        signing_keys,
        keyid=f"{key_prefix}root-key",
        extra_signatures=extra_root_signatures,
        tamper_signature=tamper_signature_role == "root",
    )
    _write_tuf_json(metadata_dir / "root.json", root)

    targets = _tuf_role(
        "targets",
        {
            "version": versions["targets"],
            "expires": expires["targets"],
            "targets": {
                target_path: {
                    "length": target_length,
                    "hashes": {"sha256": target_hash},
                }
            },
        },
        signing_keys,
        keyid=f"{key_prefix}targets-key",
        tamper_signature=tamper_signature_role == "targets",
    )
    targets_hash, targets_length = _write_tuf_json(metadata_dir / "targets.json", targets)

    snapshot = _tuf_role(
        "snapshot",
        {
            "version": versions["snapshot"],
            "expires": expires["snapshot"],
            "meta": {
                "targets.json": {
                    "version": versions["targets"],
                    "length": targets_length,
                    "hashes": {"sha256": targets_hash},
                }
            },
        },
        signing_keys,
        keyid=f"{key_prefix}snapshot-key",
        tamper_signature=tamper_signature_role == "snapshot",
    )
    snapshot_hash, snapshot_length = _write_tuf_json(metadata_dir / "snapshot.json", snapshot)

    timestamp = _tuf_role(
        "timestamp",
        {
            "version": versions["timestamp"],
            "expires": expires["timestamp"],
            "meta": {
                "snapshot.json": {
                    "version": versions["snapshot"],
                    "length": snapshot_length,
                    "hashes": {"sha256": snapshot_hash},
                }
            },
        },
        signing_keys,
        keyid=f"{key_prefix}timestamp-key",
        tamper_signature=tamper_signature_role == "timestamp",
    )
    timestamp_hash, _timestamp_length = _write_tuf_json(metadata_dir / "timestamp.json", timestamp)

    return {
        "repo": repo,
        "target_path": target_path,
        "target_digest": f"sha256:{target_hash}",
        "timestamp_sha256": f"sha256:{timestamp_hash}",
        "role_versions": versions,
        "root_metadata": root,
        "signing_keys": signing_keys,
        "key_prefix": key_prefix,
    }


def _scitt_statement(
    *,
    digest: str = "sha256:" + ("a" * 64),
    record_id: str = "",
) -> dict[str, object]:
    subject: dict[str, object] = {
        "artifact_class": "bootstrap_install_bundle",
        "artifact_digest": digest,
        "source_repo": "abyss-machine",
        "source_ref": "release:test",
    }
    if record_id:
        subject["record_id"] = record_id
    return {
        "schema": artifact_bundles.SCITT_SIGNED_STATEMENT_SCHEMA,
        "statement_class": "release_update_artifact",
        "issuer": "did:web:abyss.example:issuer:release",
        "issued_at": "2026-06-21T00:00:00Z",
        "subject": subject,
        "statement": {
            "predicate_type": "https://abyss.example/scitt/release-update-artifact/v1",
            "verdict": "release-ready",
        },
    }


def _scitt_receipt(statement: dict[str, object], *, digest: str | None = None) -> dict[str, object]:
    return {
        "schema": artifact_bundles.SCITT_RECEIPT_SCHEMA,
        "statement_digest": digest or artifact_bundles._stable_digest(statement),
        "registered_at": "2026-06-21T00:01:00Z",
        "transparency_service": {
            "id": "did:web:transparency.abyss.example",
            "issuer": "did:web:transparency.abyss.example",
        },
        "log_entry_id": "pytest-entry-1",
        "receipt_ref": "scitt://transparency.abyss.example/entries/pytest-entry-1",
    }


def _write_scitt_registry_record(tmp_path: Path, *, record_id: str, digest: str) -> Path:
    registry = tmp_path / "scitt-registry"
    records = registry / artifact_bundles.BUNDLE_REGISTRY_RECORDS_DIR
    records.mkdir(parents=True, exist_ok=True)
    (records / f"{record_id.removeprefix('sha256:')}.json").write_text(
        json.dumps(
            {
                "schema": "abyss_machine_artifact_bundle_registry_record_v1",
                "record_id": record_id,
                "artifact_class": "bootstrap_install_bundle",
                "lifecycle_state": "release-ready",
                "latest_eligible": True,
                "terminal_state": False,
                "verification_ok": True,
                "subject_digest": digest,
                "source_repo": "abyss-machine",
                "source_ref": "manifests/artifact_bundles/bootstrap_install_bundle.bundle.json",
                "trust_root_mode": "github_oidc",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry


def _write_oci_runtime_registry_record(tmp_path: Path) -> tuple[Path, str, str]:
    registry = tmp_path / "oci-registry"
    records = registry / artifact_bundles.BUNDLE_REGISTRY_RECORDS_DIR
    records.mkdir(parents=True, exist_ok=True)
    record_id = "sha256:" + ("a" * 64)
    subject_digest = "sha256:" + ("b" * 64)
    source_ref = "manifests/artifact_bundles/runtime_tools_bundle.bundle.json"
    trust_root_evidence = _trust_root_evidence(
        "oci_registry",
        subject_digest=subject_digest,
        source_repo="abyss-machine",
        source_ref=source_ref,
    )
    record = {
        "schema": "abyss_machine_artifact_bundle_registry_record_v1",
        "record_id": record_id,
        "artifact_class": "runtime_or_container_artifact",
        "bundle_layout": "abyss_machine_artifact_bundle_v1",
        "bundle_ref": "runtime-tools/bundle",
        "bundle_manifest_ref": source_ref,
        "subject_digest": subject_digest,
        "artifact_subjects_digest": "sha256:" + ("c" * 64),
        "abi_subject_digest": "sha256:" + ("d" * 64),
        "lifecycle_state": "release-ready",
        "latest_eligible": True,
        "terminal_state": False,
        "verification_ok": True,
        "verification_errors": [],
        "verification_missing": [],
        "verification_warnings": [],
        "required_controls": ["abi_signature", "sbom", "slsa_in_toto", "sigstore_cosign"],
        "verified_controls": ["abi_signature", "sbom", "slsa_in_toto", "sigstore_cosign"],
        "present_controls": ["abi_signature", "sbom", "slsa_in_toto", "sigstore_cosign"],
        "source_repo": "abyss-machine",
        "source_ref": source_ref,
        "producer": "pytest-runtime-oci-publisher",
        "trust_root_mode": "oci_registry",
        "trust_root_evidence": trust_root_evidence,
        "verifier_versions": {"pytest": "oci-publication"},
        "privacy_boundary": "public-safe runtime helper bundle",
        "created_at": "2026-06-21T00:00:00Z",
        "policy_ref": artifact_bundles.POLICY_REF,
    }
    (records / f"{record_id.removeprefix('sha256:')}.json").write_text(
        json.dumps(record, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return registry, record_id, subject_digest


def _oci_publication_evidence(
    *,
    registry_ref: str = "ghcr.io/8dionysus/abyss-machine/runtime-tools@sha256:1111111111111111111111111111111111111111111111111111111111111111",
    subject_digest: str = "sha256:" + ("1" * 64),
    record_id: str = "",
    record_subject_digest: str = "",
    discovery_method: str = "v1.1-referrers-api",
    fallback_verified: bool | None = None,
    referrers: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    discovery: dict[str, object] = {
        "method": discovery_method,
        "status": "verified",
    }
    if fallback_verified is not None:
        discovery["fallback_verified"] = fallback_verified
    return {
        "schema": artifact_bundles.OCI_PUBLICATION_EVIDENCE_SCHEMA,
        "artifact_class": "runtime_or_container_artifact",
        "registry_ref": registry_ref,
        "record_id": record_id,
        "record_subject_digest": record_subject_digest,
        "subject": {
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "digest": subject_digest,
            "reference": registry_ref,
            "size": 512,
        },
        "referrers_discovery": discovery,
        "referrers": referrers
        if referrers is not None
        else [
            {
                "artifactType": "application/vnd.dev.sigstore.bundle.v0.3+json",
                "digest": "sha256:" + ("2" * 64),
                "subject_digest": subject_digest,
            },
            {
                "artifactType": "application/vnd.cyclonedx+json",
                "digest": "sha256:" + ("3" * 64),
                "subject_digest": subject_digest,
            },
            {
                "artifactType": "application/vnd.in-toto+jsonl",
                "digest": "sha256:" + ("4" * 64),
                "subject_digest": subject_digest,
            },
        ],
    }


def _bootstrap_update_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    fake_cosign = tmp_path / "cosign"
    _write_fake_cosign(fake_cosign)
    key = tmp_path / "local-test.key"
    public_key = tmp_path / "local-test.pub"
    key.write_text("fake-private-key\n", encoding="utf-8")
    public_key.write_text("fake-public-key\n", encoding="utf-8")
    monkeypatch.setenv("ABYSS_MACHINE_COSIGN_BINARY", str(fake_cosign))
    monkeypatch.setenv("ABYSS_MACHINE_COSIGN_KEY", str(key))
    monkeypatch.setenv("ABYSS_MACHINE_COSIGN_PUB", str(public_key))

    subject = ROOT / "dist" / "abyss-machine-bootstrap-pytest-update-target.tar.gz"
    subject.parent.mkdir(parents=True, exist_ok=True)
    subject.write_text("bootstrap update target\n", encoding="utf-8")
    bundle = tmp_path / "bootstrap-update-bundle"
    registry = tmp_path / "registry"
    store_root = tmp_path / "subject-store"
    monkeypatch.setenv("ABYSS_MACHINE_ARTIFACT_SUBJECT_STORE_ROOT", str(store_root))
    try:
        build = artifact_bundles.build_sidecars(
            bundle,
            manifest_ref="manifests/artifact_bundles/bootstrap_install_bundle.bundle.json",
        )
        sign = artifact_bundles.sign_bundle(bundle, backend="cosign-local-key")
        verify = artifact_bundles.verify_bundle(bundle)
        subjects = json.loads((bundle / artifact_bundles.SUBJECTS_SIDECAR).read_text(encoding="utf-8"))
        trust_root_mode = "github_oidc"
        trust_root_evidence = _trust_root_evidence(
            trust_root_mode,
            subject_digest=str(subjects["aggregate_digest"]),
            source_repo="abyss-machine",
            source_ref="manifests/artifact_bundles/bootstrap_install_bundle.bundle.json",
        )
        promoted = artifact_bundles.promote_bundle_evidence(
            bundle,
            registry,
            lifecycle_state="release-ready",
            source_repo="abyss-machine",
            source_ref="manifests/artifact_bundles/bootstrap_install_bundle.bundle.json",
            producer="pytest bootstrap update publisher",
            trust_root_mode=trust_root_mode,
            trust_root_evidence=trust_root_evidence,
        )
        materialized = artifact_bundles.materialize_artifact_subjects(
            bundle,
            store_root=store_root,
            registry_dir=registry,
            manifest_ref="manifests/artifact_bundles/bootstrap_install_bundle.bundle.json",
            consumer_intent="update_client",
            expected_source_repo="abyss-machine",
            expected_trust_root_mode=trust_root_mode,
        )
        registered = artifact_bundles.promote_bundle_evidence(
            bundle,
            registry,
            lifecycle_state="release-ready",
            source_repo="abyss-machine",
            source_ref="manifests/artifact_bundles/bootstrap_install_bundle.bundle.json",
            producer="pytest bootstrap update publisher",
            trust_root_mode=trust_root_mode,
            trust_root_evidence=trust_root_evidence,
        )
    finally:
        subject.unlink(missing_ok=True)

    subject_digest = str(subjects["aggregate_digest"])
    gate = artifact_bundles.trust_gate(
        registry,
        artifact_class="bootstrap_install_bundle",
        consumer_intent="update_client",
        subject_digest=subject_digest,
        expected_source_repo="abyss-machine",
        expected_trust_root_mode="github_oidc",
    )

    assert build["ok"] is True
    assert sign["ok"] is True
    assert verify["ok"] is True
    assert promoted["ok"] is True
    assert promoted["record"]["artifact_subject_store"]["ok"] is False
    assert materialized["ok"] is True
    assert materialized["materialization_admission"]["verdict"] == "allow"
    assert registered["ok"] is True
    assert registered["record"]["artifact_subject_store"]["ok"] is True
    assert gate["ok"] is True
    assert gate["verdict"] == "allow"
    return registry, subject_digest


def test_update_lane_status_exposes_tuf_and_scitt_boundaries() -> None:
    status = artifact_bundles.update_lane_status()

    assert status["ok"] is True
    assert status["schema"] == "abyss_machine_update_transparency_lane_status_v1"
    assert status["summary"]["tuf_status"] == "external_repository_producer_v1"
    assert status["summary"]["blocking_v1"] is False
    assert "bootstrap_install_bundle" in [row["artifact_class"] for row in status["rows"]]
    assert "aoa_session_memory_portable_bundle" in [row["artifact_class"] for row in status["rows"]]
    assert status["tuf"]["metadata_sidecar"] == artifact_bundles.TUF_UPDATE_METADATA_SIDECAR
    assert "external TUF repository producer/verifier v1" in status["claim_limits"][0]
    assert status["tuf"]["external_repository_verifier"]["status"] == "crypto_verifier_v1"
    assert status["tuf"]["external_repository_producer"]["status"] == "producer_v1"
    assert status["tuf"]["not_full_tuf_repository_yet"] is False
    assert status["tuf"]["external_repository_verifier"]["cryptographic_signature_verifier"]["status"] == "ed25519_v1"
    assert "local statement/receipt binding stub" in status["claim_limits"][1]
    assert status["scitt"]["status"] == "local_stub_fail_closed_external_v1"


def test_scitt_receipt_verifier_allows_external_relying_party_with_bound_receipt(tmp_path: Path) -> None:
    statement = _scitt_statement()
    receipt = _scitt_receipt(statement)
    statement_path = tmp_path / "statement.json"
    receipt_path = tmp_path / "receipt.json"
    statement_path.write_text(json.dumps(statement), encoding="utf-8")
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    subject = statement["subject"]
    assert isinstance(subject, dict)
    artifact_digest = str(subject["artifact_digest"])

    result = artifact_bundles.verify_scitt_receipt(
        statement,
        receipt=receipt,
        external_relying_party=True,
        expected_statement_class="release_update_artifact",
        expected_artifact_digest=artifact_digest,
        expected_issuer="did:web:abyss.example:issuer:release",
        expected_transparency_service="did:web:transparency.abyss.example",
        now="2026-06-21T00:00:00Z",
    )
    cli_result = cli.artifacts_scitt_verify(
        statement_path,
        receipt_path=receipt_path,
        external_relying_party=True,
        expected_statement_class="release_update_artifact",
        expected_artifact_digest=artifact_digest,
        expected_issuer="did:web:abyss.example:issuer:release",
        expected_transparency_service="did:web:transparency.abyss.example",
        now="2026-06-21T00:00:00Z",
        write_latest=False,
    )

    assert result["ok"] is True
    assert result["verdict"] == "allow"
    assert result["receipt_required"] is True
    assert result["receipt_ok"] is True
    assert result["errors"] == []
    assert cli_result["ok"] is True
    assert cli_result["verdict"] == "allow"


def test_scitt_receipt_verifier_allows_external_relying_party_with_registry_link(tmp_path: Path) -> None:
    record_id = "sha256:" + ("1" * 64)
    artifact_digest = "sha256:" + ("2" * 64)
    registry = _write_scitt_registry_record(tmp_path, record_id=record_id, digest=artifact_digest)
    statement = _scitt_statement(digest=artifact_digest, record_id=record_id)
    receipt = _scitt_receipt(statement)
    statement_path = tmp_path / "statement.json"
    receipt_path = tmp_path / "receipt.json"
    statement_path.write_text(json.dumps(statement), encoding="utf-8")
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    result = artifact_bundles.verify_scitt_receipt(
        statement,
        receipt=receipt,
        external_relying_party=True,
        registry_dir=registry,
        expected_record_id=record_id,
        require_registry_link=True,
        expected_statement_class="release_update_artifact",
        expected_artifact_digest=artifact_digest,
        now="2026-06-21T00:00:00Z",
    )
    cli_result = cli.artifacts_scitt_verify(
        statement_path,
        receipt_path=receipt_path,
        external_relying_party=True,
        registry_dir=registry,
        expected_record_id=record_id,
        require_registry_link=True,
        expected_statement_class="release_update_artifact",
        expected_artifact_digest=artifact_digest,
        now="2026-06-21T00:00:00Z",
        write_latest=False,
    )

    assert result["ok"] is True
    assert result["registry_link"]["record_found"] is True
    assert result["registry_link"]["digest_match"] is True
    assert result["registry_link"]["record_id"] == record_id
    assert result["registry_link"]["errors"] == []
    assert cli_result["ok"] is True
    assert cli_result["registry_link"]["digest_match"] is True


def test_scitt_receipt_verifier_denies_missing_or_unbound_receipt_for_external_relying_party() -> None:
    statement = _scitt_statement()

    missing = artifact_bundles.verify_scitt_receipt(
        statement,
        external_relying_party=True,
        now="2026-06-21T00:00:00Z",
    )
    wrong_receipt = artifact_bundles.verify_scitt_receipt(
        statement,
        receipt=_scitt_receipt(statement, digest="sha256:" + ("b" * 64)),
        external_relying_party=True,
        now="2026-06-21T00:00:00Z",
    )
    wrong_artifact = artifact_bundles.verify_scitt_receipt(
        statement,
        receipt=_scitt_receipt(statement),
        external_relying_party=True,
        expected_artifact_digest="sha256:" + ("c" * 64),
        now="2026-06-21T00:00:00Z",
    )

    assert missing["ok"] is False
    assert missing["verdict"] == "deny"
    assert "scitt_receipt_required" in missing["errors"]
    assert wrong_receipt["ok"] is False
    assert wrong_receipt["verdict"] == "deny"
    assert "receipt_statement_digest_mismatch" in wrong_receipt["errors"]
    assert wrong_artifact["ok"] is False
    assert wrong_artifact["verdict"] == "deny"
    assert "artifact_digest_mismatch" in wrong_artifact["errors"]


def test_scitt_receipt_verifier_denies_missing_or_wrong_registry_link(tmp_path: Path) -> None:
    record_id = "sha256:" + ("1" * 64)
    artifact_digest = "sha256:" + ("2" * 64)
    registry = _write_scitt_registry_record(tmp_path, record_id=record_id, digest=artifact_digest)
    statement = _scitt_statement(digest=artifact_digest, record_id=record_id)
    receipt = _scitt_receipt(statement)
    wrong_digest_statement = _scitt_statement(digest="sha256:" + ("3" * 64), record_id=record_id)

    missing_registry = artifact_bundles.verify_scitt_receipt(
        statement,
        receipt=receipt,
        external_relying_party=True,
        require_registry_link=True,
        now="2026-06-21T00:00:00Z",
    )
    wrong_record = artifact_bundles.verify_scitt_receipt(
        statement,
        receipt=receipt,
        external_relying_party=True,
        registry_dir=registry,
        expected_record_id="sha256:" + ("4" * 64),
        require_registry_link=True,
        now="2026-06-21T00:00:00Z",
    )
    wrong_digest = artifact_bundles.verify_scitt_receipt(
        wrong_digest_statement,
        receipt=_scitt_receipt(wrong_digest_statement),
        external_relying_party=True,
        registry_dir=registry,
        expected_record_id=record_id,
        require_registry_link=True,
        now="2026-06-21T00:00:00Z",
    )

    assert missing_registry["ok"] is False
    assert "scitt_registry_required" in missing_registry["errors"]
    assert wrong_record["ok"] is False
    assert "registry_record_id_mismatch" in wrong_record["errors"]
    assert wrong_digest["ok"] is False
    assert "artifact_digest_registry_mismatch" in wrong_digest["errors"]


def test_oci_publication_verifier_allows_digest_pinned_referrers_with_trust_gate(tmp_path: Path) -> None:
    registry, record_id, record_subject_digest = _write_oci_runtime_registry_record(tmp_path)
    subject_digest = "sha256:" + ("1" * 64)
    evidence = _oci_publication_evidence(
        subject_digest=subject_digest,
        record_id=record_id,
        record_subject_digest=record_subject_digest,
    )
    evidence_path = tmp_path / "oci-publication.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    result = artifact_bundles.verify_oci_publication(
        evidence,
        expected_artifact_class="runtime_or_container_artifact",
        expected_subject_digest=subject_digest,
        required_referrer_types=[
            "application/vnd.dev.sigstore.bundle.v0.3+json",
            "application/vnd.cyclonedx+json",
            "application/vnd.in-toto+jsonl",
        ],
        registry_dir=registry,
        expected_record_id=record_id,
        expected_source_repo="abyss-machine",
        expected_trust_root_mode="oci_registry",
        require_trust_gate=True,
    )
    cli_result = cli.artifacts_oci_verify(
        evidence_path,
        artifact_class="runtime_or_container_artifact",
        subject_digest=subject_digest,
        required_referrer_types=[
            "application/vnd.dev.sigstore.bundle.v0.3+json",
            "application/vnd.cyclonedx+json",
            "application/vnd.in-toto+jsonl",
        ],
        registry_dir=registry,
        record_id=record_id,
        source_repo="abyss-machine",
        trust_root_mode="oci_registry",
        require_trust_gate=True,
        write_latest=False,
    )

    assert result["ok"] is True
    assert result["verdict"] == "allow"
    assert result["digest_pinned"] is True
    assert result["referrers"]["missing_types"] == []
    assert result["consumer_admission"]["trust_gate"]["verdict"] == "allow"
    assert cli_result["ok"] is True
    assert cli_result["consumer_admission"]["trust_gate"]["inspected_claims"]["trust_root_evidence"]["ok"] is True


def test_oci_publication_verifier_denies_tag_only_consumption() -> None:
    tag_only = _oci_publication_evidence(
        registry_ref="ghcr.io/8dionysus/abyss-machine/runtime-tools:latest",
    )

    result = artifact_bundles.verify_oci_publication(
        tag_only,
        expected_artifact_class="runtime_or_container_artifact",
        required_referrer_types=["application/vnd.dev.sigstore.bundle.v0.3+json"],
    )

    assert result["ok"] is False
    assert result["verdict"] == "deny"
    assert "tag_only_reference_denied" in result["errors"]


def test_oci_publication_verifier_denies_malformed_digest_reference() -> None:
    malformed = _oci_publication_evidence(
        registry_ref="ghcr.io/8dionysus/abyss-machine/runtime-tools@sha256:not-a-real-digest",
    )

    result = artifact_bundles.verify_oci_publication(
        malformed,
        expected_artifact_class="runtime_or_container_artifact",
        required_referrer_types=["application/vnd.dev.sigstore.bundle.v0.3+json"],
    )

    assert result["ok"] is False
    assert result["verdict"] == "deny"
    assert "registry_ref_digest_invalid" in result["errors"]


def test_oci_publication_verifier_denies_missing_required_referrer() -> None:
    evidence = _oci_publication_evidence(
        referrers=[
            {
                "artifactType": "application/vnd.dev.sigstore.bundle.v0.3+json",
                "digest": "sha256:" + ("2" * 64),
                "subject_digest": "sha256:" + ("1" * 64),
            }
        ]
    )

    result = artifact_bundles.verify_oci_publication(
        evidence,
        expected_artifact_class="runtime_or_container_artifact",
        required_referrer_types=[
            "application/vnd.dev.sigstore.bundle.v0.3+json",
            "application/vnd.cyclonedx+json",
        ],
    )

    assert result["ok"] is False
    assert result["verdict"] == "deny"
    assert "missing_oci_referrer_types:application/vnd.cyclonedx+json" in result["errors"]


def test_oci_publication_verifier_warns_for_referrers_tag_fallback() -> None:
    evidence = _oci_publication_evidence(
        discovery_method="v1.1-referrers-tag",
        fallback_verified=True,
    )

    result = artifact_bundles.verify_oci_publication(
        evidence,
        expected_artifact_class="runtime_or_container_artifact",
        required_referrer_types=["application/vnd.dev.sigstore.bundle.v0.3+json"],
    )

    assert result["ok"] is True
    assert result["verdict"] == "warn"
    assert "oci_referrers_tag_fallback_requires_race_review" in result["warnings"]


def test_tuf_repository_builder_creates_client_bootstrap_and_consumes_with_trust_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, registry_subject_digest = _bootstrap_update_registry(tmp_path, monkeypatch)
    target = tmp_path / "update-target.tar.gz"
    target.write_bytes(b"external tuf update target\n")
    tuf_repo = tmp_path / "published-tuf-repository"

    build = cli.artifacts_update_repo_build(
        tuf_repo,
        target_file=target,
        target_path="dist/update-target.tar.gz",
        artifact_class="bootstrap_install_bundle",
        version=2,
        generate_missing_keys=True,
        now="2026-06-21T00:00:00Z",
        write_latest=False,
    )
    verify = cli.artifacts_update_repo_verify(
        tuf_repo,
        target_path="dist/update-target.tar.gz",
        artifact_class="bootstrap_install_bundle",
        target_digest=str(build["target_digest"]),
        trusted_root_path=Path(str(build["trusted_root_path"])),
        previous_trusted_path=Path(str(build["client_state_path"])),
        registry_dir=registry,
        subject_digest=registry_subject_digest,
        expected_source_repo="abyss-machine",
        expected_trust_root_mode="github_oidc",
        require_trusted_root=True,
        require_trust_gate=True,
        now="2026-06-21T00:00:00Z",
        write_latest=False,
    )

    assert build["ok"] is True
    assert build["schema"] == "abyss_machine_tuf_repository_build_v1"
    assert build["role_metadata"]["timestamp"]["sha256"].startswith("sha256:")
    assert Path(str(build["trusted_root_path"])).is_file()
    assert Path(str(build["client_state_path"])).is_file()
    assert "ephemeral_tuf_signing_keys_generated; use a host-managed key-dir for durable production channels" in build["warnings"]
    assert verify["ok"] is True
    assert verify["verdict"] == "allow"
    assert verify["trusted_root"]["trusted_root_match"] is True
    assert verify["consumer_admission"]["trust_gate"]["verdict"] == "allow"


def test_tuf_repository_builder_denies_keyless_production_build(tmp_path: Path) -> None:
    target = tmp_path / "update-target.tar.gz"
    target.write_bytes(b"external tuf update target\n")

    result = artifact_bundles.build_tuf_repository(
        tmp_path / "published-tuf-repository",
        target_file=target,
        target_path="dist/update-target.tar.gz",
        artifact_class="bootstrap_install_bundle",
        now="2026-06-21T00:00:00Z",
    )

    assert result["ok"] is False
    assert result["verdict"] == "deny"
    assert "tuf_key_dir_required_or_dev_generate_keys" in result["errors"]

    source_repo_output = artifact_bundles.build_tuf_repository(
        ROOT / "tuf-repository-should-not-live-in-source",
        target_file=target,
        target_path="dist/update-target.tar.gz",
        artifact_class="bootstrap_install_bundle",
        generate_missing_keys=True,
        now="2026-06-21T00:00:00Z",
    )
    assert source_repo_output["ok"] is False
    assert "tuf_repository_dir_must_be_outside_source_repo" in source_repo_output["errors"]


def test_external_tuf_repository_verifier_allows_cryptographically_signed_repo(tmp_path: Path) -> None:
    tuf_repo = _write_tuf_repository(tmp_path)
    previous = {
        "artifact_class": "bootstrap_install_bundle",
        "role_versions": {"root": 1, "targets": 1, "snapshot": 1, "timestamp": 1},
        "timestamp_sha256": "sha256:not-this-timestamp",
        "last_seen_at": "2026-06-20T00:00:00Z",
    }
    previous_path = tmp_path / "previous-tuf-client-state.json"
    trusted_root_path = tmp_path / "trusted-root.json"
    previous_path.write_text(json.dumps(previous), encoding="utf-8")
    trusted_root_path.write_text(json.dumps(tuf_repo["root_metadata"]), encoding="utf-8")

    result = artifact_bundles.verify_tuf_repository(
        tuf_repo["repo"],
        target_path=str(tuf_repo["target_path"]),
        artifact_class="bootstrap_install_bundle",
        target_digest=str(tuf_repo["target_digest"]),
        trusted_root=tuf_repo["root_metadata"],
        previous_trusted=previous,
        require_trusted_root=True,
        now="2026-06-21T00:00:00Z",
    )
    cli_result = cli.artifacts_update_repo_verify(
        tuf_repo["repo"],
        target_path=str(tuf_repo["target_path"]),
        artifact_class="bootstrap_install_bundle",
        target_digest=str(tuf_repo["target_digest"]),
        trusted_root_path=trusted_root_path,
        previous_trusted_path=previous_path,
        require_trusted_root=True,
        now="2026-06-21T00:00:00Z",
        write_latest=False,
    )

    assert result["ok"] is True
    assert result["verdict"] == "allow"
    assert result["errors"] == []
    assert result["timestamp_sha256"] == tuf_repo["timestamp_sha256"]
    assert all(item["threshold_met"] for item in result["signature_thresholds"])
    assert all(item["valid_signed_keyids"] == [f"{item['role']}-key"] for item in result["signature_thresholds"])
    assert all(item["cryptographic_signature_verification"] == "ed25519_v1" for item in result["signature_thresholds"])
    assert result["trusted_root"]["trusted_root_match"] is True
    assert result["trusted_root"]["rotation"] is False
    assert "cryptographically valid Ed25519 signatures" in result["claim_limits"][1]
    assert cli_result["ok"] is True
    assert cli_result["trusted_root_path"] == str(trusted_root_path)
    assert cli_result["previous_trusted_path"] == str(previous_path)


def test_external_tuf_repository_verifier_denies_bad_digest_expiry_rollback_freeze_and_missing_gate(
    tmp_path: Path,
) -> None:
    tuf_repo = _write_tuf_repository(tmp_path)
    bad_digest = artifact_bundles.verify_tuf_repository(
        tuf_repo["repo"],
        target_path=str(tuf_repo["target_path"]),
        artifact_class="bootstrap_install_bundle",
        target_digest="sha256:" + ("b" * 64),
        now="2026-06-21T00:00:00Z",
    )
    expired = artifact_bundles.verify_tuf_repository(
        _write_tuf_repository(tmp_path / "expired", role_expires={"timestamp": "2026-06-20T00:00:00Z"})["repo"],
        target_path=str(tuf_repo["target_path"]),
        artifact_class="bootstrap_install_bundle",
        now="2026-06-21T00:00:00Z",
    )
    rollback = artifact_bundles.verify_tuf_repository(
        _write_tuf_repository(tmp_path / "rollback", role_versions={"snapshot": 1})["repo"],
        target_path=str(tuf_repo["target_path"]),
        artifact_class="bootstrap_install_bundle",
        previous_trusted={"role_versions": {"snapshot": 2}},
        now="2026-06-21T00:00:00Z",
    )
    frozen = artifact_bundles.verify_tuf_repository(
        tuf_repo["repo"],
        target_path=str(tuf_repo["target_path"]),
        artifact_class="bootstrap_install_bundle",
        previous_trusted={
            "timestamp_sha256": tuf_repo["timestamp_sha256"],
            "last_seen_at": "2026-06-01T00:00:00Z",
        },
        now="2026-06-21T00:00:00Z",
    )
    bad_signature = artifact_bundles.verify_tuf_repository(
        _write_tuf_repository(tmp_path / "bad-signature", tamper_signature_role="timestamp")["repo"],
        target_path=str(tuf_repo["target_path"]),
        artifact_class="bootstrap_install_bundle",
        now="2026-06-21T00:00:00Z",
    )
    missing_trusted_root = artifact_bundles.verify_tuf_repository(
        tuf_repo["repo"],
        target_path=str(tuf_repo["target_path"]),
        artifact_class="bootstrap_install_bundle",
        require_trusted_root=True,
        now="2026-06-21T00:00:00Z",
    )
    missing_gate = artifact_bundles.verify_tuf_repository(
        tuf_repo["repo"],
        target_path=str(tuf_repo["target_path"]),
        artifact_class="bootstrap_install_bundle",
        require_trust_gate=True,
        now="2026-06-21T00:00:00Z",
    )

    assert bad_digest["ok"] is False
    assert "target_digest_mismatch" in bad_digest["errors"]
    assert expired["ok"] is False
    assert "timestamp_expired" in expired["errors"]
    assert rollback["ok"] is False
    assert "rollback_snapshot_version" in rollback["errors"]
    assert frozen["ok"] is False
    assert "freeze_attack_or_stale_timestamp" in frozen["errors"]
    assert bad_signature["ok"] is False
    assert "timestamp_signature_threshold_not_met" in bad_signature["errors"]
    assert bad_signature["signature_thresholds"][3]["invalid_signatures"][0]["error"] == "signature_invalid"
    assert missing_trusted_root["ok"] is False
    assert "trusted_root_required" in missing_trusted_root["errors"]
    assert missing_gate["ok"] is False
    assert "trust_gate_registry_required" in missing_gate["errors"]


def test_external_tuf_repository_verifier_allows_root_rotation_with_old_and_new_thresholds(
    tmp_path: Path,
) -> None:
    old_repo = _write_tuf_repository(tmp_path / "old", key_prefix="old-")
    rotated_repo = _write_tuf_repository(
        tmp_path / "rotated",
        key_prefix="new-",
        role_versions={"root": 3, "targets": 3, "snapshot": 3, "timestamp": 3},
        extra_root_signatures={"old-root-key": old_repo["signing_keys"]["root"]},
    )
    bad_rotation = _write_tuf_repository(
        tmp_path / "bad-rotation",
        key_prefix="bad-",
        role_versions={"root": 3, "targets": 3, "snapshot": 3, "timestamp": 3},
    )

    result = artifact_bundles.verify_tuf_repository(
        rotated_repo["repo"],
        target_path=str(rotated_repo["target_path"]),
        artifact_class="bootstrap_install_bundle",
        target_digest=str(rotated_repo["target_digest"]),
        trusted_root=old_repo["root_metadata"],
        previous_trusted={
            "artifact_class": "bootstrap_install_bundle",
            "role_versions": old_repo["role_versions"],
            "timestamp_sha256": "sha256:not-this-timestamp",
            "last_seen_at": "2026-06-20T00:00:00Z",
        },
        require_trusted_root=True,
        now="2026-06-21T00:00:00Z",
    )
    denied = artifact_bundles.verify_tuf_repository(
        bad_rotation["repo"],
        target_path=str(bad_rotation["target_path"]),
        artifact_class="bootstrap_install_bundle",
        target_digest=str(bad_rotation["target_digest"]),
        trusted_root=old_repo["root_metadata"],
        require_trusted_root=True,
        now="2026-06-21T00:00:00Z",
    )

    assert result["ok"] is True
    assert result["trusted_root"]["trusted_root_match"] is False
    assert result["trusted_root"]["rotation"] is True
    assert result["trusted_root"]["old_root_threshold"]["threshold_met"] is True
    assert result["trusted_root"]["old_root_threshold"]["valid_signed_keyids"] == ["old-root-key"]
    assert result["signature_thresholds"][0]["valid_signed_keyids"] == ["new-root-key"]
    assert denied["ok"] is False
    assert "root_rotation_old_threshold_not_met" in denied["errors"]


def test_update_metadata_verifier_allows_current_update_metadata(tmp_path: Path) -> None:
    metadata = _update_metadata()
    previous = {
        "version": 1,
        "snapshot_version": 1,
        "timestamp_version": 1,
        "metadata_sha256": "sha256:not-this-metadata",
        "last_seen_at": "2026-06-20T00:00:00Z",
    }
    metadata_path = tmp_path / artifact_bundles.TUF_UPDATE_METADATA_SIDECAR
    previous_path = tmp_path / "previous-trusted.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    previous_path.write_text(json.dumps(previous), encoding="utf-8")

    result = artifact_bundles.verify_update_metadata(
        metadata,
        previous_trusted=previous,
        now="2026-06-21T00:00:00Z",
    )
    cli_result = cli.artifacts_update_verify(
        metadata_path,
        previous_trusted_path=previous_path,
        now="2026-06-21T00:00:00Z",
        write_latest=False,
    )

    assert result["ok"] is True
    assert result["verdict"] == "allow"
    assert result["errors"] == []
    assert cli_result["ok"] is True
    assert cli_result["metadata_path"] == str(metadata_path)
    assert cli_result["previous_trusted_path"] == str(previous_path)


def test_update_metadata_consumption_requires_trust_gate_when_requested() -> None:
    result = artifact_bundles.verify_update_metadata(
        _update_metadata(),
        now="2026-06-21T00:00:00Z",
        require_trust_gate=True,
    )

    assert result["ok"] is False
    assert result["metadata_ok"] is True
    assert result["consumer_admission"]["required"] is True
    assert result["consumer_admission"]["verdict"] == "deny"
    assert "trust_gate_registry_required" in result["errors"]


def test_update_metadata_consumption_allows_after_trust_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, subject_digest = _bootstrap_update_registry(tmp_path, monkeypatch)
    metadata = _update_metadata(target={
        "path": "dist/abyss-machine-bootstrap-pytest-update-target.tar.gz",
        "sha256": subject_digest,
    })
    previous = {
        "version": 1,
        "snapshot_version": 1,
        "timestamp_version": 1,
        "metadata_sha256": "sha256:not-this-metadata",
        "last_seen_at": "2026-06-20T00:00:00Z",
    }
    metadata_path = tmp_path / artifact_bundles.TUF_UPDATE_METADATA_SIDECAR
    previous_path = tmp_path / "previous-trusted.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    previous_path.write_text(json.dumps(previous), encoding="utf-8")

    result = artifact_bundles.verify_update_metadata(
        metadata,
        previous_trusted=previous,
        now="2026-06-21T00:00:00Z",
        registry_dir=registry,
        subject_digest=subject_digest,
        expected_source_repo="abyss-machine",
        expected_trust_root_mode="github_oidc",
        require_trust_gate=True,
    )
    cli_result = cli.artifacts_update_verify(
        metadata_path,
        previous_trusted_path=previous_path,
        now="2026-06-21T00:00:00Z",
        registry_dir=registry,
        subject_digest=subject_digest,
        expected_source_repo="abyss-machine",
        expected_trust_root_mode="github_oidc",
        require_trust_gate=True,
        write_latest=False,
    )

    assert result["ok"] is True
    assert result["verdict"] == "allow"
    assert result["metadata_ok"] is True
    assert result["consumer_admission"]["verdict"] == "allow"
    assert result["consumer_admission"]["trust_gate"]["verdict"] == "allow"
    assert cli_result["ok"] is True
    assert cli_result["consumer_admission"]["verdict"] == "allow"


def test_update_metadata_consumption_preserves_warn_trust_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, subject_digest = _bootstrap_update_registry(tmp_path, monkeypatch)
    record_paths = sorted((registry / "records").glob("*.json"))
    assert record_paths
    record = json.loads(record_paths[0].read_text(encoding="utf-8"))
    record["verification_warnings"] = ["pytest advisory warning"]
    record_paths[0].write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    metadata = _update_metadata(target={
        "path": "dist/abyss-machine-bootstrap-pytest-update-target.tar.gz",
        "sha256": subject_digest,
    })

    result = artifact_bundles.verify_update_metadata(
        metadata,
        now="2026-06-21T00:00:00Z",
        registry_dir=registry,
        subject_digest=subject_digest,
        expected_source_repo="abyss-machine",
        expected_trust_root_mode="github_oidc",
        require_trust_gate=True,
    )

    assert result["ok"] is True
    assert result["verdict"] == "allow"
    assert result["consumer_admission"]["verdict"] == "warn"
    assert result["consumer_admission"]["trust_gate"]["verdict"] == "warn"


def test_update_metadata_verifier_denies_rollback_expiry_freeze_and_zero_versions() -> None:
    rollback = artifact_bundles.verify_update_metadata(
        _update_metadata(version=1),
        previous_trusted={"version": 2, "snapshot_version": 1, "timestamp_version": 1},
        now="2026-06-21T00:00:00Z",
    )
    expired = artifact_bundles.verify_update_metadata(
        _update_metadata(expires_at="2026-06-20T00:00:00Z"),
        now="2026-06-21T00:00:00Z",
    )
    zero_version = artifact_bundles.verify_update_metadata(
        _update_metadata(version=0),
        now="2026-06-21T00:00:00Z",
    )
    frozen_metadata = _update_metadata()
    frozen_first_seen = artifact_bundles.verify_update_metadata(
        frozen_metadata,
        now="2026-06-21T00:00:00Z",
    )
    frozen = artifact_bundles.verify_update_metadata(
        frozen_metadata,
        previous_trusted={
            "version": 2,
            "snapshot_version": 2,
            "timestamp_version": 2,
            "metadata_sha256": frozen_first_seen["metadata_sha256"],
            "last_seen_at": "2026-06-01T00:00:00Z",
        },
        now="2026-06-21T00:00:00Z",
    )

    assert rollback["ok"] is False
    assert rollback["verdict"] == "deny"
    assert "rollback_version" in rollback["errors"]
    assert expired["ok"] is False
    assert "expired_metadata" in expired["errors"]
    assert zero_version["ok"] is False
    assert "version_missing" in zero_version["errors"]
    assert frozen["ok"] is False
    assert "freeze_attack_or_stale_metadata" in frozen["errors"]


def test_bundle_registry_tracks_latest_and_terminal_state(tmp_path: Path) -> None:
    bundle = tmp_path / "public-source-seed"
    registry = tmp_path / "registry"

    artifact_bundles.build_sidecars_from_manifest(bundle)
    artifact_bundles.sign_bundle(bundle)
    artifact_bundles.verify_bundle(bundle)
    registered = artifact_bundles.write_bundle_registry_record(
        bundle,
        registry,
        lifecycle_state="manually-verified",
        consumer_refs=["pytest:consumer"],
        evidence_refs=["pytest:manual-positive"],
    )

    assert registered["ok"] is True
    assert registered["record"]["latest_eligible"] is True
    assert registered["record"]["source_repo"] == "abyss-machine"
    assert registered["record"]["source_ref"] == artifact_bundles.DEFAULT_BUNDLE_MANIFEST_REF
    assert registered["record"]["producer"]
    assert registered["record"]["trust_root_mode"] == "local_dev"
    assert registered["record"]["verifier_versions"]["artifact_bundle_verifier"]["schema"] == "abyss_machine_artifact_bundle_verify_v1"
    assert len(registered["written"]) == 2

    index = artifact_bundles.read_bundle_registry(registry, artifact_class="public_source_seed")
    persisted_index = json.loads((registry / artifact_bundles.BUNDLE_REGISTRY_INDEX).read_text(encoding="utf-8"))
    public_index_payload = json.dumps(persisted_index, sort_keys=True)
    assert str(tmp_path) not in public_index_payload
    assert persisted_index["registry_dir"] == "registry"
    assert persisted_index["records_dir"] == "registry/records"
    assert persisted_index["index_ref"] == "registry/index.json"
    latest = index["latest_by_artifact_class"]["public_source_seed"]
    assert latest["record_id"] == registered["record"]["record_id"]
    assert latest["lifecycle_state"] == "manually-verified"

    revoked = artifact_bundles.write_bundle_registry_record(
        bundle,
        registry,
        lifecycle_state="revoked",
        revocation_reason="pytest manual negative",
    )
    assert revoked["ok"] is True

    after_revoke = artifact_bundles.read_bundle_registry(registry, artifact_class="public_source_seed")
    assert after_revoke["latest_by_artifact_class"] == {}
    assert after_revoke["summary"]["state_counts"] == {"revoked": 1}


def test_evidence_promotion_trust_gate_survives_tmp_bundle_removal(tmp_path: Path) -> None:
    bundle = tmp_path / "scratch-public-source-seed"
    registry = tmp_path / "durable-registry"

    artifact_bundles.build_sidecars_from_manifest(bundle)
    artifact_bundles.sign_bundle(bundle)
    promoted = artifact_bundles.promote_bundle_evidence(
        bundle,
        registry,
        lifecycle_state="manually-verified",
        consumer_refs=["pytest:agent-consumer"],
        evidence_refs=["pytest:manual-positive"],
        source_ref="pytest-source-ref",
        producer="pytest artifact producer",
        trust_root_mode="host_managed",
    )
    subject_digest = promoted["record"]["subject_digest"]
    shutil.rmtree(bundle)

    gate = artifact_bundles.trust_gate(
        registry,
        artifact_class="public_source_seed",
        subject_digest=subject_digest,
        consumer_intent="agent",
        expected_source_repo="abyss-machine",
        expected_trust_root_mode="host_managed",
    )

    assert promoted["ok"] is True
    assert promoted["schema"] == "abyss_machine_artifact_evidence_promotion_v1"
    assert not bundle.exists()
    assert gate["ok"] is True
    assert gate["verdict"] == "allow"
    assert gate["decision"]["model"] == "fail_closed_consumer_admission"
    assert gate["decision"]["allow"] is True
    assert gate["inspected_claims"]["registry_latest"]["selected_record_is_latest"] is True
    assert gate["inspected_claims"]["subject_identity"]["subject_digest_matched"] is True
    assert gate["inspected_claims"]["controls"]["required_controls_missing"] == []
    assert gate["inspected_claims"]["trust_root"]["trust_root_mode_matched"] is True
    assert gate["record"]["source_ref"] == "pytest-source-ref"
    assert gate["record"]["producer"] == "pytest artifact producer"
    assert gate["record"]["trust_root_mode"] == "host_managed"


def test_trust_gate_denies_digest_mismatch_and_revoked_records(tmp_path: Path) -> None:
    bundle = tmp_path / "public-source-seed"
    registry = tmp_path / "registry"

    artifact_bundles.build_sidecars_from_manifest(bundle)
    artifact_bundles.sign_bundle(bundle)
    promoted = artifact_bundles.promote_bundle_evidence(
        bundle,
        registry,
        lifecycle_state="manually-verified",
        trust_root_mode="host_managed",
    )

    wrong_digest = artifact_bundles.trust_gate(
        registry,
        artifact_class="public_source_seed",
        subject_digest="sha256:" + "0" * 64,
        consumer_intent="agent",
    )
    revoked = artifact_bundles.promote_bundle_evidence(
        bundle,
        registry,
        lifecycle_state="revoked",
        revocation_reason="pytest revoked negative",
        trust_root_mode="host_managed",
    )
    revoked_gate = artifact_bundles.trust_gate(
        registry,
        artifact_class="public_source_seed",
        record_id=promoted["record"]["record_id"],
        consumer_intent="agent",
    )

    assert wrong_digest["ok"] is False
    assert wrong_digest["verdict"] == "deny"
    assert wrong_digest["decision"]["allow"] is False
    assert wrong_digest["inspected_claims"]["subject_identity"]["subject_digest_matched"] is False
    assert "subject_digest_mismatch" in wrong_digest["blockers"]
    assert revoked["ok"] is True
    assert revoked_gate["ok"] is False
    assert revoked_gate["verdict"] == "deny"
    assert revoked_gate["decision"]["allow"] is False
    assert revoked_gate["inspected_claims"]["lifecycle"]["terminal_state"] is True
    assert "terminal_lifecycle_state:revoked" in revoked_gate["blockers"]


def test_trust_gate_denies_missing_required_subject_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = tmp_path / "bootstrap-install"
    registry = tmp_path / "registry"
    fake_cosign = tmp_path / "cosign"
    _write_fake_cosign(fake_cosign)
    key = tmp_path / "local-test.key"
    public_key = tmp_path / "local-test.pub"
    key.write_text("fake-private-key\n", encoding="utf-8")
    public_key.write_text("fake-public-key\n", encoding="utf-8")
    monkeypatch.setenv("ABYSS_MACHINE_COSIGN_BINARY", str(fake_cosign))
    monkeypatch.setenv("ABYSS_MACHINE_COSIGN_KEY", str(key))
    monkeypatch.setenv("ABYSS_MACHINE_COSIGN_PUB", str(public_key))
    subject = ROOT / "dist" / "abyss-machine-bootstrap-pytest-subject-store.tar.gz"
    subject.parent.mkdir(parents=True, exist_ok=True)
    subject.write_text("bootstrap subject-store gate\n", encoding="utf-8")
    try:
        artifact_bundles.build_sidecars(
            bundle,
            manifest_ref="manifests/artifact_bundles/bootstrap_install_bundle.bundle.json",
        )
        sign = artifact_bundles.sign_bundle(bundle, backend="cosign-local-key")
        verify = artifact_bundles.verify_bundle(bundle)
        promoted = artifact_bundles.promote_bundle_evidence(
            bundle,
            registry,
            lifecycle_state="release-ready",
            trust_root_mode="host_managed",
        )
    finally:
        subject.unlink(missing_ok=True)
        try:
            subject.parent.rmdir()
        except OSError:
            pass

    gate = artifact_bundles.trust_gate(
        registry,
        artifact_class="bootstrap_install_bundle",
        subject_digest=promoted["record"]["subject_digest"],
        consumer_intent="installer",
        expected_trust_root_mode="host_managed",
    )

    assert sign["ok"] is True
    assert verify["ok"] is True
    assert promoted["ok"] is True
    assert promoted["record"]["consumer_contract"]["subject_store_required"] is True
    assert promoted["record"]["artifact_subject_store"]["ok"] is False
    assert gate["ok"] is False
    assert gate["verdict"] == "deny"
    assert "required_artifact_subject_store_not_verified" in gate["blockers"]
    assert gate["inspected_claims"]["artifact_subject_store"]["ok"] is False


def test_trust_gate_requires_manual_review_for_local_dev_production_consumers(tmp_path: Path) -> None:
    bundle = tmp_path / "public-source-seed"
    registry = tmp_path / "registry"

    artifact_bundles.build_sidecars_from_manifest(bundle)
    artifact_bundles.sign_bundle(bundle)
    artifact_bundles.promote_bundle_evidence(bundle, registry, lifecycle_state="manually-verified")

    gate = artifact_bundles.trust_gate(
        registry,
        artifact_class="public_source_seed",
        consumer_intent="installer",
    )

    assert gate["ok"] is False
    assert gate["verdict"] == "manual_review_required"
    assert gate["decision"]["allow"] is False
    assert gate["decision"]["manual_review"] == gate["manual_review"]
    assert "production_consumer_requires_non_local_trust_root" in gate["manual_review"]
    assert "production_consumer_requires_release_lifecycle" in gate["manual_review"]


def test_trust_gate_allows_public_boundary_with_private_exclusions_for_release_consumers(tmp_path: Path) -> None:
    bundle = tmp_path / "public-source-seed"
    registry = tmp_path / "registry"

    artifact_bundles.build_sidecars_from_manifest(bundle)
    artifact_bundles.sign_bundle(bundle)
    subject_digest = _bundle_subject_digest(bundle)
    artifact_bundles.promote_bundle_evidence(
        bundle,
        registry,
        lifecycle_state="release-ready",
        source_repo="abyss-machine",
        source_ref="manifests/artifact_bundles/public_source_seed.bundle.json",
        producer="pytest public seed publisher",
        trust_root_mode="public_release",
        trust_root_evidence=_trust_root_evidence(
            "public_release",
            subject_digest=subject_digest,
            source_repo="abyss-machine",
            source_ref="manifests/artifact_bundles/public_source_seed.bundle.json",
        ),
    )

    gate = artifact_bundles.trust_gate(
        registry,
        artifact_class="public_source_seed",
        consumer_intent="public_release",
        expected_trust_root_mode="public_release",
    )

    assert gate["ok"] is True
    assert gate["verdict"] == "allow"
    assert gate["manual_review"] == []
    assert "private captures" in gate["inspected_claims"]["privacy_boundary"]["value"]
    assert gate["inspected_claims"]["privacy_boundary"]["production_public_ready"] is True
    assert gate["inspected_claims"]["trust_root_evidence"]["ok"] is True


def test_trust_gate_requires_manual_review_for_host_managed_public_release_consumers(tmp_path: Path) -> None:
    bundle = tmp_path / "public-source-seed"
    registry = tmp_path / "registry"

    artifact_bundles.build_sidecars_from_manifest(bundle)
    artifact_bundles.sign_bundle(bundle)
    artifact_bundles.promote_bundle_evidence(
        bundle,
        registry,
        lifecycle_state="release-ready",
        trust_root_mode="host_managed",
    )

    gate = artifact_bundles.trust_gate(
        registry,
        artifact_class="public_source_seed",
        consumer_intent="public_release",
    )

    assert gate["ok"] is False
    assert gate["verdict"] == "manual_review_required"
    assert "production_consumer_requires_release_trust_root" in gate["manual_review"]
    assert gate["inspected_claims"]["trust_root"]["production_trust_root_ready"] is False


def test_trust_gate_denies_public_release_without_trust_root_evidence(tmp_path: Path) -> None:
    bundle = tmp_path / "public-source-seed"
    registry = tmp_path / "registry"

    artifact_bundles.build_sidecars_from_manifest(bundle)
    artifact_bundles.sign_bundle(bundle)
    artifact_bundles.promote_bundle_evidence(
        bundle,
        registry,
        lifecycle_state="release-ready",
        source_repo="abyss-machine",
        source_ref="manifests/artifact_bundles/public_source_seed.bundle.json",
        producer="pytest public seed publisher",
        trust_root_mode="public_release",
    )

    gate = artifact_bundles.trust_gate(
        registry,
        artifact_class="public_source_seed",
        consumer_intent="public_release",
        expected_trust_root_mode="public_release",
    )

    assert gate["ok"] is False
    assert gate["verdict"] == "deny"
    assert "production_trust_root_evidence_missing" in gate["blockers"]
    assert gate["inspected_claims"]["trust_root_evidence"]["ok"] is False


def test_trust_gate_requires_manual_review_for_private_production_boundary(tmp_path: Path) -> None:
    bundle = tmp_path / "public-source-seed"
    registry = tmp_path / "registry"

    artifact_bundles.build_sidecars_from_manifest(bundle)
    artifact_bundles.sign_bundle(bundle)
    subject_digest = _bundle_subject_digest(bundle)
    promoted = artifact_bundles.promote_bundle_evidence(
        bundle,
        registry,
        lifecycle_state="release-ready",
        source_repo="abyss-machine",
        source_ref="manifests/artifact_bundles/public_source_seed.bundle.json",
        producer="pytest public seed publisher",
        trust_root_mode="public_release",
        trust_root_evidence=_trust_root_evidence(
            "public_release",
            subject_digest=subject_digest,
            source_repo="abyss-machine",
            source_ref="manifests/artifact_bundles/public_source_seed.bundle.json",
        ),
    )
    record_path = (
        registry
        / artifact_bundles.BUNDLE_REGISTRY_RECORDS_DIR
        / f"{promoted['record']['record_id'].removeprefix('sha256:')}.json"
    )
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["privacy_boundary"] = "private host evidence; not public repo content and not release-signed by default"
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    gate = artifact_bundles.trust_gate(
        registry,
        artifact_class="public_source_seed",
        consumer_intent="public_release",
        expected_trust_root_mode="public_release",
    )

    assert gate["ok"] is False
    assert gate["verdict"] == "manual_review_required"
    assert gate["manual_review"] == ["production_consumer_requires_public_privacy_boundary"]
    assert gate["inspected_claims"]["privacy_boundary"]["production_public_ready"] is False


def test_trust_gate_fails_closed_when_registry_record_is_absent(tmp_path: Path) -> None:
    gate = artifact_bundles.trust_gate(
        tmp_path / "empty-registry",
        artifact_class="public_source_seed",
        consumer_intent="agent",
    )

    assert gate["ok"] is False
    assert gate["verdict"] == "unknown"
    assert gate["decision"]["model"] == "fail_closed_consumer_admission"
    assert gate["decision"]["blocks_on_unknown"] is True
    assert gate["decision"]["allow"] is False
    assert gate["reasons"] == ["no_registry_record"]
    assert gate["decision"]["blockers"] == ["no_registry_record"]
    assert gate["blockers"] == ["no_registry_record"]
    assert gate["inspected_claims"]["registry_latest"]["selected_record_id"] is None


def test_legacy_registry_upgrade_makes_missing_evidence_fields_explicit(tmp_path: Path) -> None:
    bundle = tmp_path / "public-source-seed"
    registry = tmp_path / "registry"

    artifact_bundles.build_sidecars_from_manifest(bundle)
    artifact_bundles.sign_bundle(bundle)
    promoted = artifact_bundles.promote_bundle_evidence(bundle, registry, lifecycle_state="manually-verified")
    record_id = promoted["record"]["record_id"]
    record_path = registry / artifact_bundles.BUNDLE_REGISTRY_RECORDS_DIR / f"{record_id.removeprefix('sha256:')}.json"
    legacy_record = json.loads(record_path.read_text(encoding="utf-8"))
    for field in artifact_bundles.DURABLE_EVIDENCE_FIELDS:
        legacy_record.pop(field, None)
    record_path.write_text(json.dumps(legacy_record, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    denied = artifact_bundles.trust_gate(registry, artifact_class="public_source_seed", consumer_intent="agent")
    dry_run = artifact_bundles.upgrade_legacy_bundle_registry(registry, dry_run=True)
    still_denied = artifact_bundles.trust_gate(registry, artifact_class="public_source_seed", consumer_intent="agent")
    upgraded = artifact_bundles.upgrade_legacy_bundle_registry(registry, trust_root_mode="host_managed")
    allowed = artifact_bundles.trust_gate(
        registry,
        artifact_class="public_source_seed",
        consumer_intent="agent",
        expected_trust_root_mode="host_managed",
    )
    missing_blocker = "record_missing_durable_evidence_fields:source_repo,source_ref,producer,trust_root_mode,verifier_versions"

    assert denied["ok"] is False
    assert denied["verdict"] == "deny"
    assert denied["blockers"] == [missing_blocker]
    assert dry_run["ok"] is True
    assert dry_run["summary"]["upgraded"] == 1
    assert dry_run["written"] == []
    assert dry_run["upgrades"][0]["initial_missing_fields"] == list(artifact_bundles.DURABLE_EVIDENCE_FIELDS)
    assert still_denied["ok"] is False
    assert upgraded["ok"] is True
    assert upgraded["summary"]["upgraded"] == 1
    assert upgraded["upgrades"][0]["remaining_missing_fields"] == []
    assert allowed["ok"] is True
    assert allowed["verdict"] == "allow"
    assert allowed["inspected_claims"]["trust_root"]["trust_root_mode_actual"] == "host_managed"
    assert allowed["record"]["legacy_evidence_upgrade"]["missing_fields"] == list(artifact_bundles.DURABLE_EVIDENCE_FIELDS)


def test_bundle_registry_rejects_unverified_latest_candidate(tmp_path: Path) -> None:
    bundle = tmp_path / "unsigned-public-source-seed"
    registry = tmp_path / "registry"

    artifact_bundles.build_sidecars_from_manifest(bundle)
    registered = artifact_bundles.write_bundle_registry_record(
        bundle,
        registry,
        lifecycle_state="manually-verified",
    )

    assert registered["ok"] is False
    assert registered["written"] == []
    assert any("successful bundle verification" in item for item in registered["errors"])
    assert not (registry / artifact_bundles.BUNDLE_REGISTRY_INDEX).exists()


def test_required_cosign_bundle_roundtrip_and_tamper_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_cosign = tmp_path / "cosign"
    _write_fake_cosign(fake_cosign)
    key = tmp_path / "local-test.key"
    public_key = tmp_path / "local-test.pub"
    key.write_text("fake-private-key\n", encoding="utf-8")
    public_key.write_text("fake-public-key\n", encoding="utf-8")
    monkeypatch.setenv("ABYSS_MACHINE_COSIGN_BINARY", str(fake_cosign))
    monkeypatch.setenv("ABYSS_MACHINE_COSIGN_KEY", str(key))
    monkeypatch.setenv("ABYSS_MACHINE_COSIGN_PUB", str(public_key))

    dist = tmp_path / "dist"
    dist.mkdir()
    artifact = dist / "abyss-machine-bootstrap.tar"
    artifact.write_text("bootstrap payload\n", encoding="utf-8")
    manifest = {
        "schema": "abyss_machine_artifact_bundle_manifest_v1",
        "id": "bootstrap-install-bundle-contract",
        "artifact_class": "bootstrap_install_bundle",
        "owner_repo": "abyss-machine",
        "policy_ref": artifact_bundles.POLICY_REF,
        "mode": "os_abyss_local",
        "public_safe": True,
        "subject_repo_root": ".",
        "artifact_subjects": [
            {"path": "dist/abyss-machine-bootstrap.tar", "role": "bootstrap_install_bundle"},
        ],
        "build_type": "urn:abyssos:buildtype:bootstrap-install-bundle:v1",
        "package": {
            "ecosystem": "bootstrap",
            "name": "abyss-machine-bootstrap",
            "purl": "pkg:generic/abyss-machine-bootstrap@0",
        },
        "consumer_contract": {
            "stable_interface": "abyss-machine artifacts trust-gate --artifact-class bootstrap_install_bundle --consumer-intent installer --json",
            "admission_gate": "fail_closed_consumer_admission",
            "subject_store_required": True,
        },
    }
    manifest_path = tmp_path / "bootstrap_install.bundle.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    bundle = tmp_path / "bundle"

    build = artifact_bundles.build_sidecars(bundle, manifest_ref=manifest_path)
    sign = artifact_bundles.sign_bundle(bundle, backend="cosign-local-key")
    verify = artifact_bundles.verify_bundle(bundle)
    decision_payload = (bundle / artifact_bundles.SIGNATURE_DECISION_SIDECAR).read_text(encoding="utf-8")

    assert build["ok"] is True
    assert sign["ok"] is True
    assert sign["status"] == "signed"
    assert sign["subject_ref"] == artifact_bundles.SUBJECTS_SIDECAR
    assert verify["ok"] is True
    assert verify["required_controls"] == ["abi_signature", "sbom", "slsa_in_toto", "sigstore_cosign"]
    assert verify["verified_controls"] == ["abi_signature", "sbom", "slsa_in_toto", "sigstore_cosign"]
    assert str(key) not in decision_payload
    assert (bundle / artifact_bundles.SIGSTORE_BUNDLE_SIDECAR).is_file()
    assert (bundle / artifact_bundles.COSIGN_SIGNATURE_SIDECAR).is_file()
    assert (bundle / artifact_bundles.COSIGN_PUBLIC_KEY_SIDECAR).is_file()

    (bundle / artifact_bundles.COSIGN_PUBLIC_KEY_SIDECAR).unlink()
    missing_public_key = artifact_bundles.verify_bundle(bundle, write=False)
    assert missing_public_key["ok"] is False
    assert missing_public_key["verified_controls"] == []
    assert "sigstore_cosign" in missing_public_key["present_controls"]
    assert artifact_bundles.COSIGN_PUBLIC_KEY_SIDECAR in missing_public_key["missing"]
    (bundle / artifact_bundles.COSIGN_PUBLIC_KEY_SIDECAR).write_text(public_key.read_text(encoding="utf-8"), encoding="utf-8")

    subjects_path = bundle / artifact_bundles.SUBJECTS_SIDECAR
    subjects = json.loads(subjects_path.read_text(encoding="utf-8"))
    subjects["tampered"] = True
    subjects_path.write_text(json.dumps(subjects, sort_keys=True) + "\n", encoding="utf-8")
    tampered = artifact_bundles.verify_bundle(bundle, write=False)

    assert tampered["ok"] is False
    assert any("subject_digest does not match" in item for item in tampered["errors"])
    assert any("cosign verify-blob failed" in item for item in tampered["errors"])


def test_materialized_artifact_subject_store_supports_installed_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_cosign = tmp_path / "cosign"
    _write_fake_cosign(fake_cosign)
    key = tmp_path / "local-test.key"
    public_key = tmp_path / "local-test.pub"
    key.write_text("fake-private-key\n", encoding="utf-8")
    public_key.write_text("fake-public-key\n", encoding="utf-8")
    store_root = tmp_path / "subject-store"
    monkeypatch.setenv("ABYSS_MACHINE_COSIGN_BINARY", str(fake_cosign))
    monkeypatch.setenv("ABYSS_MACHINE_COSIGN_KEY", str(key))
    monkeypatch.setenv("ABYSS_MACHINE_COSIGN_PUB", str(public_key))
    monkeypatch.setenv("ABYSS_MACHINE_ARTIFACT_SUBJECT_STORE_ROOT", str(store_root))

    dist = tmp_path / "dist"
    dist.mkdir()
    artifact = dist / "abyss-machine-bootstrap.tar"
    artifact.write_text("bootstrap payload\n", encoding="utf-8")
    manifest = {
        "schema": "abyss_machine_artifact_bundle_manifest_v1",
        "id": "bootstrap-install-bundle-contract",
        "artifact_class": "bootstrap_install_bundle",
        "owner_repo": "abyss-machine",
        "policy_ref": artifact_bundles.POLICY_REF,
        "mode": "os_abyss_local",
        "public_safe": True,
        "subject_repo_root": ".",
        "artifact_subjects": [
            {"path": "dist/abyss-machine-bootstrap.tar", "role": "bootstrap_install_bundle"},
        ],
        "build_type": "urn:abyssos:buildtype:bootstrap-install-bundle:v1",
        "package": {
            "ecosystem": "bootstrap",
            "name": "abyss-machine-bootstrap",
            "purl": "pkg:generic/abyss-machine-bootstrap@0",
        },
        "consumer_contract": {
            "stable_interface": "abyss-machine artifacts trust-gate --artifact-class bootstrap_install_bundle --consumer-intent installer --json",
            "admission_gate": "fail_closed_consumer_admission",
            "subject_store_required": True,
        },
    }
    manifest_path = tmp_path / "bootstrap_install.bundle.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    bundle = tmp_path / "bundle"
    registry = tmp_path / "registry"

    artifact_bundles.build_sidecars(bundle, manifest_ref=manifest_path)
    artifact_bundles.sign_bundle(bundle, backend="cosign-local-key")
    trust_root_mode = "github_oidc"
    trust_root_evidence = _trust_root_evidence(
        trust_root_mode,
        subject_digest=_bundle_subject_digest(bundle),
        source_repo="abyss-machine",
        source_ref=str(manifest_path),
    )
    pre_materialize_promotion = artifact_bundles.promote_bundle_evidence(
        bundle,
        registry,
        lifecycle_state="release-ready",
        source_repo="abyss-machine",
        source_ref=str(manifest_path),
        producer="pytest bootstrap bundle",
        trust_root_mode=trust_root_mode,
        trust_root_evidence=trust_root_evidence,
    )
    materialized = artifact_bundles.materialize_artifact_subjects(
        bundle,
        store_root=store_root,
        registry_dir=registry,
        manifest_ref=manifest_path,
        expected_trust_root_mode=trust_root_mode,
    )
    artifact.unlink()

    verify = artifact_bundles.verify_bundle(bundle)
    registered = artifact_bundles.promote_bundle_evidence(
        bundle,
        registry,
        lifecycle_state="release-ready",
        source_repo="abyss-machine",
        source_ref=str(manifest_path),
        producer="pytest bootstrap bundle",
        trust_root_mode=trust_root_mode,
        trust_root_evidence=trust_root_evidence,
    )

    assert pre_materialize_promotion["ok"] is True
    assert materialized["ok"] is True
    assert materialized["consumer_intent"] == "installer"
    assert materialized["materialization_admission"]["verdict"] == "allow"
    assert materialized["materialization_admission"]["reason"] == "only_required_subject_store_missing"
    assert materialized["trust_gate"]["verdict"] == "deny"
    assert artifact_bundles.REQUIRED_SUBJECT_STORE_BLOCKER in materialized["trust_gate"]["blockers"]
    assert verify["ok"] is True
    assert verify["artifact_subject_resolution"][0]["source"] == "artifact_subject_store"
    assert str(tmp_path.resolve()) not in (bundle / artifact_bundles.VERIFY_SIDECAR).read_text(encoding="utf-8")
    assert registered["ok"] is True
    assert registered["record"]["artifact_subject_store"]["ok"] is True

    subjects = json.loads((bundle / artifact_bundles.SUBJECTS_SIDECAR).read_text(encoding="utf-8"))
    stored_artifact = (
        store_root
        / "bootstrap_install_bundle"
        / subjects["aggregate_digest"].removeprefix("sha256:")
        / "dist"
        / "abyss-machine-bootstrap.tar"
    )
    stored_artifact.write_text("tampered bootstrap payload\n", encoding="utf-8")
    tampered = artifact_bundles.verify_bundle(bundle, write=False)

    assert tampered["ok"] is False
    assert any("artifact subject store digest mismatch" in item for item in tampered["errors"])


def test_materialize_subjects_fails_closed_without_consumer_trust_gate(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    artifact = dist / "abyss-machine-bootstrap.tar"
    artifact.write_text("bootstrap payload\n", encoding="utf-8")
    manifest = {
        "schema": "abyss_machine_artifact_bundle_manifest_v1",
        "id": "bootstrap-install-bundle-contract",
        "artifact_class": "bootstrap_install_bundle",
        "owner_repo": "abyss-machine",
        "policy_ref": artifact_bundles.POLICY_REF,
        "mode": "os_abyss_local",
        "public_safe": True,
        "subject_repo_root": ".",
        "artifact_subjects": [
            {"path": "dist/abyss-machine-bootstrap.tar", "role": "bootstrap_install_bundle"},
        ],
        "build_type": "urn:abyssos:buildtype:bootstrap-install-bundle:v1",
        "package": {
            "ecosystem": "bootstrap",
            "name": "abyss-machine-bootstrap",
            "purl": "pkg:generic/abyss-machine-bootstrap@0",
        },
    }
    manifest_path = tmp_path / "bootstrap_install.bundle.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    bundle = tmp_path / "bundle"
    store_root = tmp_path / "subject-store"

    artifact_bundles.build_sidecars(bundle, manifest_ref=manifest_path)
    artifact_bundles.sign_bundle(bundle)

    missing_registry = artifact_bundles.materialize_artifact_subjects(
        bundle,
        store_root=store_root,
        manifest_ref=manifest_path,
    )
    empty_registry = artifact_bundles.materialize_artifact_subjects(
        bundle,
        store_root=store_root,
        registry_dir=tmp_path / "empty-registry",
        manifest_ref=manifest_path,
    )

    assert missing_registry["ok"] is False
    assert missing_registry["written"] == []
    assert "artifact subject materialization requires registry_dir for consumer trust-gate" in missing_registry["errors"]
    assert missing_registry["trust_gate"] is None
    assert empty_registry["ok"] is False
    assert empty_registry["written"] == []
    assert empty_registry["trust_gate"]["verdict"] == "unknown"
    assert empty_registry["trust_gate"]["blockers"] == ["no_registry_record"]
    assert not store_root.exists()


def _build_ai_runtime_ml_bom_test_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    manifest_mutator=None,
) -> tuple[Path, dict, dict, dict]:
    fake_cosign = tmp_path / "cosign"
    _write_fake_cosign(fake_cosign)
    key = tmp_path / "local-test.key"
    public_key = tmp_path / "local-test.pub"
    key.write_text("fake-private-key\n", encoding="utf-8")
    public_key.write_text("fake-public-key\n", encoding="utf-8")
    monkeypatch.setenv("ABYSS_MACHINE_COSIGN_BINARY", str(fake_cosign))
    monkeypatch.setenv("ABYSS_MACHINE_COSIGN_KEY", str(key))
    monkeypatch.setenv("ABYSS_MACHINE_COSIGN_PUB", str(public_key))

    artifact_dir = tmp_path / "artifacts" / "ai"
    artifact_dir.mkdir(parents=True)
    artifact = artifact_dir / "abyss-machine-ai-runtime-config.bundle"
    artifact.write_text("ai runtime config bundle\n", encoding="utf-8")
    manifest = {
        "schema": "abyss_machine_artifact_bundle_manifest_v1",
        "id": "ai-runtime-config-bundle-contract",
        "artifact_class": "ai_model_or_runtime_bundle",
        "contract_surface_id": "host-ai-runtime-route",
        "owner_repo": "abyss-machine",
        "policy_ref": artifact_bundles.POLICY_REF,
        "mode": "os_abyss_local",
        "public_safe": True,
        "subject_repo_root": ".",
        "artifact_subjects": [
            {"path": "artifacts/ai/abyss-machine-ai-runtime-config.bundle", "role": "framework_config_bundle"},
        ],
        "build_type": "urn:abyssos:buildtype:ai-runtime-config-bundle:v1",
        "package": {
            "ecosystem": "ai-runtime-config",
            "name": "abyss-machine-ai-runtime-config",
            "purl": "pkg:generic/abyss-machine-ai-runtime-config@0",
        },
        "ml_bom": {
            "name": "abyss-machine-ai-runtime-config",
            "scope": "framework_config_bundle_no_model_weights",
            "models": [
                {
                    "name": "Qwen3-Embedding-0.6B-int8-ov",
                    "version": "0.6B",
                    "role": "referenced_embedding_model",
                    "included": False,
                    "source_ref": "{{ABYSS_OS_ROOT}}/abyss-stack/Models/ovms/OpenVINO/Qwen3-Embedding-0.6B-int8-ov",
                }
            ],
            "conversions": [
                {
                    "name": "Qwen3-TTS CustomVoice OpenVINO cache",
                    "role": "referenced_openvino_conversion",
                    "included": False,
                    "source_ref": "{{ABYSS_MACHINE_SRV}}/cache/ai/tts/qwen3-openvino/customvoice-1p7b-fp16-ov",
                    "framework": "OpenVINO",
                    "precision": "fp16",
                }
            ],
            "framework_configs": [
                {
                    "name": "abyss-machine-ai-runtime-config",
                    "role": "framework_config_bundle",
                    "subject_path": "artifacts/ai/abyss-machine-ai-runtime-config.bundle",
                    "framework": "abyss-machine",
                }
            ],
            "datasets": [],
            "not_applicable": {
                "datasets": "no dataset artifact is distributed by this framework-config bundle"
            },
        },
    }
    if manifest_mutator is not None:
        manifest_mutator(manifest)
    manifest_path = tmp_path / "ai_runtime_config.bundle.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    bundle = tmp_path / "bundle"

    build = artifact_bundles.build_sidecars(bundle, manifest_ref=manifest_path)
    sign = artifact_bundles.sign_bundle(bundle, backend="cosign-local-key")
    verify = artifact_bundles.verify_bundle(bundle)
    ml_bom = json.loads((bundle / artifact_bundles.MLBOM_CYCLONEDX_SIDECAR).read_text(encoding="utf-8"))
    assert build["ok"] is True
    assert sign["ok"] is True
    return bundle, ml_bom, verify, build


def _ml_bom_component(ml_bom: dict, category: str) -> dict:
    for component in ml_bom["components"]:
        properties = {
            prop.get("name"): prop.get("value")
            for prop in component.get("properties", [])
            if isinstance(prop, dict)
        }
        if properties.get("abyss.ml_bom.category") == category:
            return component
    raise AssertionError(f"ML-BOM component category not found: {category}")


def _remove_ml_bom_property(component: dict, name: str) -> None:
    component["properties"] = [
        prop for prop in component.get("properties", []) if not (isinstance(prop, dict) and prop.get("name") == name)
    ]


def _write_ml_bom(bundle: Path, ml_bom: dict) -> None:
    (bundle / artifact_bundles.MLBOM_CYCLONEDX_SIDECAR).write_text(
        json.dumps(ml_bom, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_ai_model_runtime_bundle_generates_semantic_ml_bom_and_required_release_controls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle, ml_bom, verify, build = _build_ai_runtime_ml_bom_test_bundle(tmp_path, monkeypatch)

    assert artifact_bundles.MLBOM_CYCLONEDX_SIDECAR in build["written"]
    assert verify["ok"] is True
    assert verify["required_controls"] == ["abi_signature", "sbom", "ml_bom", "slsa_in_toto", "sigstore_cosign"]
    assert verify["verified_controls"] == ["abi_signature", "sbom", "ml_bom", "slsa_in_toto", "sigstore_cosign"]
    categories = {
        prop["value"]
        for component in ml_bom["components"]
        for prop in component.get("properties", [])
        if prop.get("name") == "abyss.ml_bom.category"
    }
    assert {"models", "conversions", "framework_configs"} <= categories
    tool_components = ml_bom["metadata"]["tools"]["components"]
    assert tool_components[0]["name"] == "abyss-machine"
    assert tool_components[0]["version"]
    dependency_map = {item["ref"]: set(item["dependsOn"]) for item in ml_bom["dependencies"]}
    component_refs = {component["bom-ref"] for component in ml_bom["components"]}
    metadata_ref = ml_bom["metadata"]["component"]["bom-ref"]
    assert component_refs <= dependency_map[metadata_ref]
    framework_ref = _ml_bom_component(ml_bom, "framework_configs")["bom-ref"]
    assert _ml_bom_component(ml_bom, "models")["bom-ref"] in dependency_map[framework_ref]
    assert _ml_bom_component(ml_bom, "conversions")["bom-ref"] in dependency_map[framework_ref]


def test_ai_model_runtime_bundle_rejects_missing_model_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle, ml_bom, _verify, _build = _build_ai_runtime_ml_bom_test_bundle(tmp_path, monkeypatch)
    _remove_ml_bom_property(_ml_bom_component(ml_bom, "models"), "abyss.ml_bom.source_ref")
    _write_ml_bom(bundle, ml_bom)

    verify = artifact_bundles.verify_bundle(bundle, write=False)

    assert verify["ok"] is False
    assert any("model component" in error and "source_ref or subject_digest" in error for error in verify["errors"])


def test_ai_model_runtime_bundle_rejects_missing_framework_config_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle, ml_bom, _verify, _build = _build_ai_runtime_ml_bom_test_bundle(tmp_path, monkeypatch)
    _remove_ml_bom_property(_ml_bom_component(ml_bom, "framework_configs"), "abyss.ml_bom.framework")
    _write_ml_bom(bundle, ml_bom)

    verify = artifact_bundles.verify_bundle(bundle, write=False)

    assert verify["ok"] is False
    assert any("framework config component" in error and "must define framework" in error for error in verify["errors"])


def test_ai_model_runtime_bundle_rejects_missing_conversion_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle, ml_bom, _verify, _build = _build_ai_runtime_ml_bom_test_bundle(tmp_path, monkeypatch)
    conversion = _ml_bom_component(ml_bom, "conversions")
    _remove_ml_bom_property(conversion, "abyss.ml_bom.source_ref")
    _remove_ml_bom_property(conversion, "abyss.ml_bom.precision")
    _write_ml_bom(bundle, ml_bom)

    verify = artifact_bundles.verify_bundle(bundle, write=False)

    assert verify["ok"] is False
    assert any("conversion component" in error and "source_ref or subject_digest" in error for error in verify["errors"])
    assert any("conversion component" in error and "precision or format" in error for error in verify["errors"])


def test_ai_model_runtime_bundle_rejects_missing_dependency_relationship(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle, ml_bom, _verify, _build = _build_ai_runtime_ml_bom_test_bundle(tmp_path, monkeypatch)
    ml_bom["dependencies"] = []
    _write_ml_bom(bundle, ml_bom)

    verify = artifact_bundles.verify_bundle(bundle, write=False)

    assert verify["ok"] is False
    assert any("dependency graph metadata component must depend" in error for error in verify["errors"])


def test_ai_model_runtime_bundle_rejects_missing_dataset_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle, ml_bom, _verify, _build = _build_ai_runtime_ml_bom_test_bundle(tmp_path, monkeypatch)
    dataset_ref = "ml-bom:datasets:training-data"
    ml_bom["components"].append(
        {
            "bom-ref": dataset_ref,
            "type": "data",
            "name": "training-data",
            "version": "snapshot",
            "properties": [
                {"name": "abyss.ml_bom.category", "value": "datasets"},
                {"name": "abyss.ml_bom.role", "value": "training_dataset"},
                {"name": "abyss.ml_bom.included", "value": "false"},
            ],
        }
    )
    for dependency in ml_bom["dependencies"]:
        if dependency["ref"] in {
            ml_bom["metadata"]["component"]["bom-ref"],
            _ml_bom_component(ml_bom, "framework_configs")["bom-ref"],
        }:
            dependency["dependsOn"].append(dataset_ref)
    _write_ml_bom(bundle, ml_bom)

    verify = artifact_bundles.verify_bundle(bundle, write=False)

    assert verify["ok"] is False
    assert any("dataset component" in error and "dataset provenance" in error for error in verify["errors"])


def test_ai_model_runtime_bundle_rejects_missing_ml_bom_tool_versions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle, ml_bom, _verify, _build = _build_ai_runtime_ml_bom_test_bundle(tmp_path, monkeypatch)
    ml_bom["metadata"].pop("tools")
    _write_ml_bom(bundle, ml_bom)

    verify = artifact_bundles.verify_bundle(bundle, write=False)

    assert verify["ok"] is False
    assert any("metadata.tools must identify tool name and version" in error for error in verify["errors"])


def test_host_local_evidence_bundle_roundtrip_uses_local_provenance(tmp_path: Path) -> None:
    bundle = tmp_path / "host-local-evidence"

    build = artifact_bundles.build_sidecars(
        bundle,
        manifest_ref="manifests/artifact_bundles/host_local_evidence.sample.bundle.json",
    )
    sign = artifact_bundles.sign_bundle(bundle)
    verify = artifact_bundles.verify_bundle(bundle)

    assert build["ok"] is True
    assert sign["ok"] is True
    assert verify["ok"] is True
    assert verify["required_controls"] == ["local_provenance"]
    assert verify["verified_controls"] == ["local_provenance"]
    assert not (bundle / artifact_bundles.ABI_SIDECAR).exists()
    assert (bundle / artifact_bundles.LOCAL_PROVENANCE_SIDECAR).is_file()


def test_external_release_manifest_subject_roundtrip(tmp_path: Path) -> None:
    sibling = tmp_path / "aoa-skills"
    generated = sibling / "generated"
    manifest_dir = sibling / "manifests" / "artifact_bundles"
    generated.mkdir(parents=True)
    manifest_dir.mkdir(parents=True)
    release_manifest = {
        "schema_version": 4,
        "artifact_identity": {
            "artifact_class": "aoa_skills_release_manifest",
            "abi_epoch": "aoa_skills_release_manifest_v1",
        },
    }
    (generated / "release_manifest.json").write_text(
        json.dumps(release_manifest, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema": "abyss_machine_artifact_bundle_manifest_v1",
        "id": "aoa-skills-release-manifest",
        "artifact_class": "aoa_skills_release_manifest",
        "owner_repo": "aoa-skills",
        "policy_ref": artifact_bundles.POLICY_REF,
        "mode": "os_abyss_local",
        "subject_repo_root": "../..",
        "abi_subject": {
            "path": "generated/release_manifest.json",
            "artifact_identity_pointer": "/artifact_identity",
        },
    }
    manifest_path = manifest_dir / "release_manifest.bundle.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    bundle = tmp_path / "bundle"

    build = artifact_bundles.build_sidecars(bundle, manifest_ref=manifest_path)
    sign = artifact_bundles.sign_bundle(bundle)
    verify = artifact_bundles.verify_bundle(bundle)
    abi = json.loads((bundle / artifact_bundles.ABI_SIDECAR).read_text(encoding="utf-8"))

    assert build["ok"] is True
    assert sign["ok"] is True
    assert verify["ok"] is True
    assert verify["required_controls"] == ["abi_signature"]
    assert abi["external_subject"]["artifact_class"] == "aoa_skills_release_manifest"
    assert abi["external_subject"]["artifact_identity"]["abi_epoch"] == "aoa_skills_release_manifest_v1"


def test_aoa_stats_summary_catalog_generates_abi_and_sbom_lite(tmp_path: Path) -> None:
    sibling = tmp_path / "aoa-stats"
    generated = sibling / "generated"
    manifest_dir = sibling / "manifests" / "artifact_bundles"
    generated.mkdir(parents=True)
    manifest_dir.mkdir(parents=True)
    catalog = {
        "schema_version": "aoa_stats_summary_surface_catalog_v2",
        "artifact_identity": {
            "artifact_class": "derived_observability_readmodel_catalog",
            "abi_epoch": "aoa_stats_summary_surface_catalog_v2",
        },
        "surfaces": [],
    }
    (generated / "summary_surface_catalog.min.json").write_text(
        json.dumps(catalog, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema": "abyss_machine_artifact_bundle_manifest_v1",
        "id": "aoa-stats-summary-surface-catalog",
        "artifact_class": "derived_observability_readmodel_catalog",
        "owner_repo": "aoa-stats",
        "policy_ref": artifact_bundles.POLICY_REF,
        "mode": "os_abyss_local",
        "public_safe": True,
        "subject_repo_root": "../..",
        "abi_subject": {
            "path": "generated/summary_surface_catalog.min.json",
            "artifact_identity_pointer": "/artifact_identity",
        },
        "artifact_subjects": [
            {"path": "generated/summary_surface_catalog.min.json", "role": "summary_surface_catalog"},
        ],
        "package": {
            "ecosystem": "observability-readmodel",
            "name": "aoa-stats-summary-surface-catalog",
            "purl": "pkg:generic/aoa-stats-summary-surface-catalog@0",
        },
    }
    manifest_path = manifest_dir / "summary_surface_catalog.bundle.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    bundle = tmp_path / "bundle"

    build = artifact_bundles.build_sidecars(bundle, manifest_ref=manifest_path)
    sign = artifact_bundles.sign_bundle(bundle)
    verify = artifact_bundles.verify_bundle(bundle)
    abi = json.loads((bundle / artifact_bundles.ABI_SIDECAR).read_text(encoding="utf-8"))
    cdx = json.loads((bundle / artifact_bundles.SBOM_CYCLONEDX_SIDECAR).read_text(encoding="utf-8"))

    assert build["ok"] is True
    assert sign["ok"] is True
    assert verify["ok"] is True
    assert verify["required_controls"] == ["abi_signature", "sbom"]
    assert verify["verified_controls"] == ["abi_signature", "sbom"]
    assert abi["external_subject"]["artifact_class"] == "derived_observability_readmodel_catalog"
    assert abi["external_subject"]["artifact_identity"]["abi_epoch"] == "aoa_stats_summary_surface_catalog_v2"
    assert cdx["components"][0]["name"] == "generated/summary_surface_catalog.min.json"
    assert not (bundle / artifact_bundles.SLSA_INTOTO_SIDECAR).exists()


def test_aoa_agents_role_registry_generates_abi_and_slsa_provenance(tmp_path: Path) -> None:
    sibling = tmp_path / "aoa-agents"
    generated = sibling / "generated"
    schemas = sibling / "schemas"
    agents = sibling / "agents" / "roles"
    manifest_dir = sibling / "manifests" / "artifact_bundles"
    generated.mkdir(parents=True)
    schemas.mkdir(parents=True)
    agents.mkdir(parents=True)
    manifest_dir.mkdir(parents=True)
    registry = {
        "version": 2,
        "layer": "aoa-agents",
        "artifact_identity": {
            "artifact_class": "role_contract_registry",
            "abi_epoch": "aoa_agents_role_registry_v2",
        },
        "agents": [],
    }
    (generated / "agent_registry.min.json").write_text(
        json.dumps(registry, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (schemas / "agent-registry.schema.json").write_text("{}\n", encoding="utf-8")
    (agents / "AGENTS.md").write_text("# roles\n", encoding="utf-8")
    manifest = {
        "schema": "abyss_machine_artifact_bundle_manifest_v1",
        "id": "aoa-agents-role-contract-registry",
        "artifact_class": "role_contract_registry",
        "owner_repo": "aoa-agents",
        "policy_ref": artifact_bundles.POLICY_REF,
        "mode": "os_abyss_local",
        "public_safe": True,
        "subject_repo_root": "../..",
        "abi_subject": {
            "path": "generated/agent_registry.min.json",
            "artifact_identity_pointer": "/artifact_identity",
        },
        "artifact_subjects": [
            {"path": "generated/agent_registry.min.json", "role": "role_contract_registry"},
            {"path": "schemas/agent-registry.schema.json", "role": "schema"},
            {"path": "agents/roles/AGENTS.md", "role": "authority_doc"},
        ],
        "build_type": "https://abyssos.local/buildtypes/aoa-agents-role-registry/v1",
        "package": {
            "ecosystem": "generated-readmodel",
            "name": "aoa-agents-role-contract-registry",
            "purl": "pkg:generic/aoa-agents-role-contract-registry@0",
        },
    }
    manifest_path = manifest_dir / "role_contract_registry.bundle.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    bundle = tmp_path / "bundle"

    build = artifact_bundles.build_sidecars(bundle, manifest_ref=manifest_path)
    sign = artifact_bundles.sign_bundle(bundle)
    verify = artifact_bundles.verify_bundle(bundle)
    abi = json.loads((bundle / artifact_bundles.ABI_SIDECAR).read_text(encoding="utf-8"))
    subjects = json.loads((bundle / artifact_bundles.SUBJECTS_SIDECAR).read_text(encoding="utf-8"))
    slsa_line = (bundle / artifact_bundles.SLSA_INTOTO_SIDECAR).read_text(encoding="utf-8").splitlines()[0]
    slsa = json.loads(slsa_line)

    assert build["ok"] is True
    assert sign["ok"] is True
    assert verify["ok"] is True
    assert verify["required_controls"] == ["abi_signature", "slsa_in_toto"]
    assert verify["verified_controls"] == ["abi_signature", "slsa_in_toto"]
    assert abi["external_subject"]["artifact_class"] == "role_contract_registry"
    assert abi["external_subject"]["artifact_identity"]["abi_epoch"] == "aoa_agents_role_registry_v2"
    assert {item["role"] for item in subjects["files"]} == {"authority_doc", "role_contract_registry", "schema"}
    assert slsa["predicateType"] == "https://slsa.dev/provenance/v1"
    assert len(slsa["subject"]) == 3
    assert not (bundle / artifact_bundles.SBOM_CYCLONEDX_SIDECAR).exists()


def test_aoa_techniques_kag_export_generates_abi_and_slsa_provenance(tmp_path: Path) -> None:
    sibling = tmp_path / "aoa-techniques"
    generated = sibling / "generated"
    docs = sibling / "docs" / "source-lift"
    scripts = sibling / "scripts"
    validators = scripts / "validators"
    manifest_dir = docs / "artifact-bundles"
    generated.mkdir(parents=True)
    docs.mkdir(parents=True)
    scripts.mkdir(parents=True)
    validators.mkdir(parents=True)
    manifest_dir.mkdir(parents=True)
    export = {
        "owner_repo": "aoa-techniques",
        "kind": "technique",
        "object_id": "AOA-T-0043",
        "artifact_identity": {
            "artifact_class": "source_owned_kag_export_capsule",
            "abi_epoch": "aoa_techniques_kag_export_v1",
        },
    }
    (generated / "kag_export.min.json").write_text(
        json.dumps(export, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (docs / "KAG_EXPORT.md").write_text("# KAG Export\n", encoding="utf-8")
    (scripts / "build_kag_export.py").write_text("# builder\n", encoding="utf-8")
    (validators / "projection_kag.py").write_text("# validator\n", encoding="utf-8")
    manifest = {
        "schema": "abyss_machine_artifact_bundle_manifest_v1",
        "id": "aoa-techniques-kag-export-capsule",
        "artifact_class": "source_owned_kag_export_capsule",
        "owner_repo": "aoa-techniques",
        "policy_ref": artifact_bundles.POLICY_REF,
        "mode": "os_abyss_local",
        "public_safe": True,
        "subject_repo_root": "../../..",
        "abi_subject": {
            "path": "generated/kag_export.min.json",
            "artifact_identity_pointer": "/artifact_identity",
        },
        "artifact_subjects": [
            {"path": "generated/kag_export.min.json", "role": "kag_export_capsule"},
            {"path": "docs/source-lift/KAG_EXPORT.md", "role": "authority_doc"},
            {"path": "scripts/build_kag_export.py", "role": "builder"},
            {"path": "scripts/validators/projection_kag.py", "role": "validator"},
        ],
        "build_type": "https://abyssos.local/buildtypes/aoa-techniques-kag-export/v1",
        "package": {
            "ecosystem": "generated-readmodel",
            "name": "aoa-techniques-kag-export-capsule",
            "purl": "pkg:generic/aoa-techniques-kag-export-capsule@0",
        },
    }
    manifest_path = manifest_dir / "kag_export.bundle.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    bundle = tmp_path / "bundle"

    build = artifact_bundles.build_sidecars(bundle, manifest_ref=manifest_path)
    sign = artifact_bundles.sign_bundle(bundle)
    verify = artifact_bundles.verify_bundle(bundle)
    abi = json.loads((bundle / artifact_bundles.ABI_SIDECAR).read_text(encoding="utf-8"))
    subjects = json.loads((bundle / artifact_bundles.SUBJECTS_SIDECAR).read_text(encoding="utf-8"))
    slsa_line = (bundle / artifact_bundles.SLSA_INTOTO_SIDECAR).read_text(encoding="utf-8").splitlines()[0]
    slsa = json.loads(slsa_line)

    assert build["ok"] is True
    assert sign["ok"] is True
    assert verify["ok"] is True
    assert verify["required_controls"] == ["abi_signature", "slsa_in_toto"]
    assert verify["verified_controls"] == ["abi_signature", "slsa_in_toto"]
    assert abi["external_subject"]["artifact_class"] == "source_owned_kag_export_capsule"
    assert abi["external_subject"]["artifact_identity"]["abi_epoch"] == "aoa_techniques_kag_export_v1"
    assert {item["role"] for item in subjects["files"]} == {"authority_doc", "builder", "kag_export_capsule", "validator"}
    assert slsa["predicateType"] == "https://slsa.dev/provenance/v1"
    assert len(slsa["subject"]) == 4
    assert not (bundle / artifact_bundles.SBOM_CYCLONEDX_SIDECAR).exists()


def test_aoa_kag_registry_readmodel_generates_abi_sbom_and_slsa_controls(tmp_path: Path) -> None:
    sibling = tmp_path / "aoa-kag"
    generated = sibling / "generated"
    manifests = sibling / "manifests"
    schemas = sibling / "schemas"
    scripts = sibling / "scripts"
    config = sibling / "config"
    docs = sibling / "docs"
    manifest_dir = docs / "artifact-bundles"
    generated.mkdir(parents=True)
    manifests.mkdir(parents=True)
    schemas.mkdir(parents=True)
    scripts.mkdir(parents=True)
    config.mkdir(parents=True)
    docs.mkdir(parents=True)
    manifest_dir.mkdir(parents=True)
    registry = {
        "version": 1,
        "layer": "aoa-kag",
        "artifact_identity": {
            "artifact_class": "derived_kag_registry_readmodel_bundle",
            "abi_epoch": "aoa_kag_registry_readmodel_v1",
        },
        "surfaces": [],
    }
    (generated / "kag_registry.min.json").write_text(
        json.dumps(registry, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (generated / "kag_registry.json").write_text(
        json.dumps(registry, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (manifests / "kag_registry.json").write_text(json.dumps(registry, sort_keys=True) + "\n", encoding="utf-8")
    (schemas / "kag-registry.schema.json").write_text("{}\n", encoding="utf-8")
    (scripts / "generate_kag.py").write_text("# generator\n", encoding="utf-8")
    (scripts / "kag_generation.py").write_text("# generator library\n", encoding="utf-8")
    (scripts / "validate_kag.py").write_text("# validator\n", encoding="utf-8")
    (config / "validation_lanes.json").write_text("{}\n", encoding="utf-8")
    (generated / "AGENTS.md").write_text("# generated route\n", encoding="utf-8")
    (docs / "KAG_MODEL.md").write_text("# KAG Model\n", encoding="utf-8")
    manifest = {
        "schema": "abyss_machine_artifact_bundle_manifest_v1",
        "id": "aoa-kag-registry-readmodel-bundle",
        "artifact_class": "derived_kag_registry_readmodel_bundle",
        "owner_repo": "aoa-kag",
        "policy_ref": artifact_bundles.POLICY_REF,
        "mode": "os_abyss_local",
        "public_safe": True,
        "subject_repo_root": "../..",
        "abi_subject": {
            "path": "generated/kag_registry.min.json",
            "artifact_identity_pointer": "/artifact_identity",
        },
        "artifact_subjects": [
            {"path": "generated/kag_registry.min.json", "role": "kag_registry_readmodel"},
            {"path": "generated/kag_registry.json", "role": "kag_registry_readmodel_full"},
            {"path": "manifests/kag_registry.json", "role": "source_manifest"},
            {"path": "schemas/kag-registry.schema.json", "role": "schema"},
            {"path": "scripts/generate_kag.py", "role": "generator_entrypoint"},
            {"path": "scripts/kag_generation.py", "role": "generator_library"},
            {"path": "scripts/validate_kag.py", "role": "validator"},
            {"path": "config/validation_lanes.json", "role": "validation_lane_authority"},
            {"path": "generated/AGENTS.md", "role": "generated_route_card"},
            {"path": "docs/KAG_MODEL.md", "role": "authority_doc"},
        ],
        "build_type": "urn:abyssos:buildtype:aoa-kag-registry-readmodel:v1",
        "package": {
            "ecosystem": "generated-readmodel",
            "name": "aoa-kag-registry-readmodel-bundle",
            "purl": "pkg:generic/aoa-kag-registry-readmodel-bundle@0",
        },
    }
    manifest_path = manifest_dir / "kag_registry.bundle.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    bundle = tmp_path / "bundle"

    build = artifact_bundles.build_sidecars(bundle, manifest_ref=manifest_path)
    sign = artifact_bundles.sign_bundle(bundle)
    verify = artifact_bundles.verify_bundle(bundle)
    identity = json.loads((bundle / artifact_bundles.IDENTITY_SIDECAR).read_text(encoding="utf-8"))
    abi = json.loads((bundle / artifact_bundles.ABI_SIDECAR).read_text(encoding="utf-8"))
    subjects = json.loads((bundle / artifact_bundles.SUBJECTS_SIDECAR).read_text(encoding="utf-8"))
    cdx = json.loads((bundle / artifact_bundles.SBOM_CYCLONEDX_SIDECAR).read_text(encoding="utf-8"))
    slsa = json.loads((bundle / artifact_bundles.SLSA_INTOTO_SIDECAR).read_text(encoding="utf-8").splitlines()[0])
    verify_sidecar = json.loads((bundle / artifact_bundles.VERIFY_SIDECAR).read_text(encoding="utf-8"))

    assert build["ok"] is True
    assert sign["status"] == "not_required"
    assert verify["ok"] is True
    assert identity["bundle_manifest_ref"] == "docs/artifact-bundles/kag_registry.bundle.json"
    assert verify["required_controls"] == ["abi_signature", "sbom", "slsa_in_toto"]
    assert verify["verified_controls"] == ["abi_signature", "sbom", "slsa_in_toto"]
    assert abi["external_subject"]["artifact_class"] == "derived_kag_registry_readmodel_bundle"
    assert abi["external_subject"]["artifact_identity"]["abi_epoch"] == "aoa_kag_registry_readmodel_v1"
    assert len(subjects["files"]) == 10
    assert len(cdx["components"]) == 10
    assert slsa["predicate"]["buildDefinition"]["buildType"] == "urn:abyssos:buildtype:aoa-kag-registry-readmodel:v1"
    assert len(slsa["subject"]) == 10
    assert verify_sidecar["bundle_dir"] == "bundle"
    public_payload = json.dumps(
        {"identity": identity, "abi": abi, "subjects": subjects, "cdx": cdx, "slsa": slsa, "verify": verify_sidecar},
        sort_keys=True,
    )
    assert str(sibling) not in public_payload
    assert str(bundle) not in public_payload


def test_aoa_memo_memory_object_readmodels_generate_abi_and_slsa_provenance(tmp_path: Path) -> None:
    sibling = tmp_path / "aoa-memo"
    generated = sibling / "generated" / "memory-objects"
    docs = sibling / "docs" / "memory"
    schemas = sibling / "schemas" / "generated-surfaces"
    scripts = sibling / "scripts" / "memory"
    examples = sibling / "examples" / "generated-surfaces"
    manifest_dir = docs / "artifact-bundles"
    generated.mkdir(parents=True)
    docs.mkdir(parents=True)
    schemas.mkdir(parents=True)
    scripts.mkdir(parents=True)
    examples.mkdir(parents=True)
    manifest_dir.mkdir(parents=True)
    catalog = {
        "schema_version": "aoa_memo_memory_object_surfaces_v2",
        "artifact_identity": {
            "artifact_class": "derived_memory_object_readmodel_family",
            "abi_epoch": "aoa_memo_memory_object_surfaces_v2",
        },
        "memory_objects": [],
    }
    (generated / "memory_object_catalog.min.json").write_text(
        json.dumps(catalog, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (generated / "memory_object_catalog.json").write_text(json.dumps(catalog, sort_keys=True) + "\n", encoding="utf-8")
    (generated / "memory_object_capsules.json").write_text("{}\n", encoding="utf-8")
    (generated / "memory_object_sections.full.json").write_text("{}\n", encoding="utf-8")
    (docs / "MEMORY_OBJECT_PROFILES.md").write_text("# Memory Object Profiles\n", encoding="utf-8")
    (sibling / "MEMORY_INDEX.md").write_text("# Memory Index\n", encoding="utf-8")
    (schemas / "memory_object_catalog.schema.json").write_text("{}\n", encoding="utf-8")
    (examples / "memory_object_surface_manifest.json").write_text("{}\n", encoding="utf-8")
    (scripts / "generate_memory_object_surfaces.py").write_text("# builder\n", encoding="utf-8")
    (scripts / "validate_memory_object_surfaces.py").write_text("# validator\n", encoding="utf-8")
    manifest = {
        "schema": "abyss_machine_artifact_bundle_manifest_v1",
        "id": "aoa-memo-memory-object-readmodel-family",
        "artifact_class": "derived_memory_object_readmodel_family",
        "owner_repo": "aoa-memo",
        "policy_ref": artifact_bundles.POLICY_REF,
        "mode": "os_abyss_local",
        "public_safe": True,
        "subject_repo_root": "../../..",
        "abi_subject": {
            "path": "generated/memory-objects/memory_object_catalog.min.json",
            "artifact_identity_pointer": "/artifact_identity",
        },
        "artifact_subjects": [
            {"path": "generated/memory-objects/memory_object_catalog.min.json", "role": "memory_object_catalog_min"},
            {"path": "generated/memory-objects/memory_object_catalog.json", "role": "memory_object_catalog_full"},
            {"path": "generated/memory-objects/memory_object_capsules.json", "role": "memory_object_capsules"},
            {"path": "generated/memory-objects/memory_object_sections.full.json", "role": "memory_object_sections"},
            {"path": "schemas/generated-surfaces/memory_object_catalog.schema.json", "role": "schema"},
            {"path": "scripts/memory/generate_memory_object_surfaces.py", "role": "builder"},
            {"path": "scripts/memory/validate_memory_object_surfaces.py", "role": "validator"},
        ],
        "build_type": "urn:abyssos:buildtype:aoa-memo-memory-object-readmodels:v1",
        "package": {
            "ecosystem": "generated-readmodel",
            "name": "aoa-memo-memory-object-readmodels",
            "purl": "pkg:generic/aoa-memo-memory-object-readmodels@0",
        },
    }
    manifest_path = manifest_dir / "memory_object_readmodels.bundle.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    bundle = tmp_path / "bundle"

    build = artifact_bundles.build_sidecars(bundle, manifest_ref=manifest_path)
    sign = artifact_bundles.sign_bundle(bundle)
    verify = artifact_bundles.verify_bundle(bundle)
    abi = json.loads((bundle / artifact_bundles.ABI_SIDECAR).read_text(encoding="utf-8"))
    subjects = json.loads((bundle / artifact_bundles.SUBJECTS_SIDECAR).read_text(encoding="utf-8"))
    slsa_line = (bundle / artifact_bundles.SLSA_INTOTO_SIDECAR).read_text(encoding="utf-8").splitlines()[0]
    slsa = json.loads(slsa_line)

    assert build["ok"] is True
    assert sign["ok"] is True
    assert verify["ok"] is True
    assert verify["required_controls"] == ["abi_signature", "slsa_in_toto"]
    assert verify["verified_controls"] == ["abi_signature", "slsa_in_toto"]
    assert abi["external_subject"]["artifact_class"] == "derived_memory_object_readmodel_family"
    assert abi["external_subject"]["artifact_identity"]["abi_epoch"] == "aoa_memo_memory_object_surfaces_v2"
    assert len(subjects["files"]) == 7
    assert slsa["predicateType"] == "https://slsa.dev/provenance/v1"
    assert len(slsa["subject"]) == 7
    assert not (bundle / artifact_bundles.SBOM_CYCLONEDX_SIDECAR).exists()


def test_aoa_routing_thin_router_generates_abi_sbom_and_slsa_controls(tmp_path: Path) -> None:
    sibling = tmp_path / "aoa-routing"
    generated = sibling / "generated"
    schemas = sibling / "routing" / "core" / "schemas"
    scripts = sibling / "scripts"
    manifest_dir = sibling / "docs" / "artifact-bundles"
    generated.mkdir(parents=True)
    schemas.mkdir(parents=True)
    scripts.mkdir(parents=True)
    manifest_dir.mkdir(parents=True)
    router = {
        "version": "aoa-router-v1",
        "artifact_identity": {
            "artifact_class": "thin_routing_readmodel_bundle",
            "abi_epoch": "aoa_routing_thin_router_v1",
        },
        "entries": [],
    }
    generated_files = {
        "aoa_router.min.json": router,
        "cross_repo_registry.min.json": {"schema": "cross_repo_registry_v1", "repos": []},
        "task_to_surface_hints.json": {"schema": "task_to_surface_hints_v1", "hints": []},
        "task_to_tier_hints.json": {"schema": "task_to_tier_hints_v1", "hints": []},
        "recommended_paths.min.json": {"schema": "recommended_paths_v1", "paths": []},
        "federation_entrypoints.min.json": {"schema": "federation_entrypoints_v1", "entrypoints": []},
        "return_navigation_hints.min.json": {"schema": "return_navigation_hints_v1", "hints": []},
        "composite_stress_route_hints.min.json": {"schema": "composite_stress_route_hints_v1", "hints": []},
        "stats_regrounding_hints.min.json": {"schema": "stats_regrounding_hints_v1", "hints": []},
        "tiny_model_entrypoints.json": {"schema": "tiny_model_entrypoints_v1", "entrypoints": []},
    }
    for name, payload in generated_files.items():
        (generated / name).write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    (schemas / "aoa-router.schema.json").write_text("{}\n", encoding="utf-8")
    (schemas / "router-entry.schema.json").write_text("{}\n", encoding="utf-8")
    (scripts / "build_router.py").write_text("# builder\n", encoding="utf-8")
    (scripts / "router_core.py").write_text("# core\n", encoding="utf-8")
    (scripts / "validate_router.py").write_text("# validator\n", encoding="utf-8")
    (sibling / "README.md").write_text("# aoa-routing\n", encoding="utf-8")
    (generated / "AGENTS.md").write_text("# generated route\n", encoding="utf-8")
    manifest = {
        "schema": "abyss_machine_artifact_bundle_manifest_v1",
        "id": "aoa-routing-thin-router-readmodel",
        "artifact_class": "thin_routing_readmodel_bundle",
        "owner_repo": "aoa-routing",
        "policy_ref": artifact_bundles.POLICY_REF,
        "mode": "os_abyss_local",
        "public_safe": True,
        "subject_repo_root": "../..",
        "abi_subject": {
            "path": "generated/aoa_router.min.json",
            "artifact_identity_pointer": "/artifact_identity",
        },
        "artifact_subjects": [
            {"path": "generated/aoa_router.min.json", "role": "router"},
            {"path": "generated/cross_repo_registry.min.json", "role": "registry"},
            {"path": "generated/task_to_surface_hints.json", "role": "surface_hints"},
            {"path": "generated/task_to_tier_hints.json", "role": "tier_hints"},
            {"path": "generated/recommended_paths.min.json", "role": "recommended_paths"},
            {"path": "routing/core/schemas/aoa-router.schema.json", "role": "schema"},
            {"path": "routing/core/schemas/router-entry.schema.json", "role": "schema"},
            {"path": "scripts/build_router.py", "role": "builder"},
            {"path": "scripts/router_core.py", "role": "core"},
            {"path": "scripts/validate_router.py", "role": "validator"},
        ],
        "build_type": "urn:abyssos:buildtype:aoa-routing-thin-router:v1",
        "package": {
            "ecosystem": "generated-readmodel",
            "name": "aoa-routing-thin-router-readmodel",
            "purl": "pkg:generic/aoa-routing-thin-router-readmodel@0",
        },
    }
    manifest_path = manifest_dir / "thin_router.bundle.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    bundle = tmp_path / "bundle"

    build = artifact_bundles.build_sidecars(bundle, manifest_ref=manifest_path)
    sign = artifact_bundles.sign_bundle(bundle)
    verify = artifact_bundles.verify_bundle(bundle)
    identity = json.loads((bundle / artifact_bundles.IDENTITY_SIDECAR).read_text(encoding="utf-8"))
    abi = json.loads((bundle / artifact_bundles.ABI_SIDECAR).read_text(encoding="utf-8"))
    subjects = json.loads((bundle / artifact_bundles.SUBJECTS_SIDECAR).read_text(encoding="utf-8"))
    cdx = json.loads((bundle / artifact_bundles.SBOM_CYCLONEDX_SIDECAR).read_text(encoding="utf-8"))
    slsa = json.loads((bundle / artifact_bundles.SLSA_INTOTO_SIDECAR).read_text(encoding="utf-8").splitlines()[0])
    verify_sidecar = json.loads((bundle / artifact_bundles.VERIFY_SIDECAR).read_text(encoding="utf-8"))

    assert build["ok"] is True
    assert sign["status"] == "not_required"
    assert verify["ok"] is True
    assert identity["bundle_manifest_ref"] == "docs/artifact-bundles/thin_router.bundle.json"
    assert verify["required_controls"] == ["abi_signature", "sbom", "slsa_in_toto"]
    assert verify["verified_controls"] == ["abi_signature", "sbom", "slsa_in_toto"]
    assert abi["external_subject"]["artifact_class"] == "thin_routing_readmodel_bundle"
    assert abi["external_subject"]["artifact_identity"]["abi_epoch"] == "aoa_routing_thin_router_v1"
    assert len(subjects["files"]) == 10
    assert len(cdx["components"]) == 10
    assert slsa["predicate"]["buildDefinition"]["buildType"] == "urn:abyssos:buildtype:aoa-routing-thin-router:v1"
    assert len(slsa["subject"]) == 10
    assert verify_sidecar["bundle_dir"] == "bundle"
    public_payload = json.dumps(
        {"identity": identity, "abi": abi, "subjects": subjects, "cdx": cdx, "slsa": slsa, "verify": verify_sidecar},
        sort_keys=True,
    )
    assert str(sibling) not in public_payload
    assert str(bundle) not in public_payload


def test_aoa_playbooks_registry_bundle_generates_abi_and_slsa_provenance(tmp_path: Path) -> None:
    sibling = tmp_path / "aoa-playbooks"
    generated = sibling / "generated"
    schemas = sibling / "schemas"
    scripts = sibling / "scripts"
    manifest_dir = sibling / "docs" / "artifact-bundles"
    generated.mkdir(parents=True)
    schemas.mkdir(parents=True)
    scripts.mkdir(parents=True)
    manifest_dir.mkdir(parents=True)
    registry = {
        "version": 1,
        "layer": "aoa-playbooks",
        "artifact_identity": {
            "artifact_class": "playbook_registry_bundle",
            "abi_epoch": "aoa_playbooks_registry_bundle_v1",
        },
        "playbooks": [],
    }
    generated_files = {
        "playbook_registry.min.json": registry,
        "playbook_activation_surfaces.min.json": [],
        "playbook_federation_surfaces.min.json": [],
        "playbook_review_status.min.json": {"schema_version": 1, "playbooks": []},
        "playbook_handoff_contracts.json": {"schema_version": 1, "playbooks": []},
        "playbook_composition_manifest.json": {"schema_version": 1, "generated_files": []},
    }
    for name, payload in generated_files.items():
        (generated / name).write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    (schemas / "playbook-registry.schema.json").write_text("{}\n", encoding="utf-8")
    (scripts / "validate_playbooks.py").write_text("# validator\n", encoding="utf-8")
    (sibling / "README.md").write_text("# aoa-playbooks\n", encoding="utf-8")
    (generated / "AGENTS.md").write_text("# generated playbooks\n", encoding="utf-8")
    manifest = {
        "schema": "abyss_machine_artifact_bundle_manifest_v1",
        "id": "aoa-playbooks-registry-bundle",
        "artifact_class": "playbook_registry_bundle",
        "owner_repo": "aoa-playbooks",
        "policy_ref": artifact_bundles.POLICY_REF,
        "mode": "os_abyss_local",
        "public_safe": True,
        "subject_repo_root": "../..",
        "abi_subject": {
            "path": "generated/playbook_registry.min.json",
            "artifact_identity_pointer": "/artifact_identity",
        },
        "artifact_subjects": [
            {"path": "generated/playbook_registry.min.json", "role": "playbook_registry"},
            {"path": "schemas/playbook-registry.schema.json", "role": "schema"},
            {"path": "generated/playbook_activation_surfaces.min.json", "role": "activation_readout"},
            {"path": "generated/playbook_federation_surfaces.min.json", "role": "federation_readout"},
            {"path": "generated/playbook_review_status.min.json", "role": "review_status_readout"},
            {"path": "generated/playbook_handoff_contracts.json", "role": "handoff_contracts"},
            {"path": "generated/playbook_composition_manifest.json", "role": "composition_manifest"},
            {"path": "scripts/validate_playbooks.py", "role": "validator"},
            {"path": "generated/AGENTS.md", "role": "generated_route_card"},
            {"path": "README.md", "role": "authority_doc"},
        ],
        "build_type": "urn:abyssos:buildtype:aoa-playbooks-registry:v1",
        "package": {
            "ecosystem": "playbook-readmodel",
            "name": "aoa-playbooks-registry-bundle",
            "purl": "pkg:generic/aoa-playbooks-registry-bundle@0",
        },
    }
    manifest_path = manifest_dir / "playbook_registry.bundle.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    bundle = tmp_path / "bundle"

    build = artifact_bundles.build_sidecars(bundle, manifest_ref=manifest_path)
    sign = artifact_bundles.sign_bundle(bundle)
    verify = artifact_bundles.verify_bundle(bundle)
    identity = json.loads((bundle / artifact_bundles.IDENTITY_SIDECAR).read_text(encoding="utf-8"))
    abi = json.loads((bundle / artifact_bundles.ABI_SIDECAR).read_text(encoding="utf-8"))
    subjects = json.loads((bundle / artifact_bundles.SUBJECTS_SIDECAR).read_text(encoding="utf-8"))
    slsa = json.loads((bundle / artifact_bundles.SLSA_INTOTO_SIDECAR).read_text(encoding="utf-8").splitlines()[0])
    verify_sidecar = json.loads((bundle / artifact_bundles.VERIFY_SIDECAR).read_text(encoding="utf-8"))

    assert build["ok"] is True
    assert sign["status"] == "not_required"
    assert verify["ok"] is True
    assert identity["bundle_manifest_ref"] == "docs/artifact-bundles/playbook_registry.bundle.json"
    assert verify["required_controls"] == ["abi_signature", "slsa_in_toto"]
    assert verify["verified_controls"] == ["abi_signature", "slsa_in_toto"]
    assert abi["external_subject"]["artifact_class"] == "playbook_registry_bundle"
    assert abi["external_subject"]["artifact_identity"]["abi_epoch"] == "aoa_playbooks_registry_bundle_v1"
    assert len(subjects["files"]) == 10
    assert slsa["predicate"]["buildDefinition"]["buildType"] == "urn:abyssos:buildtype:aoa-playbooks-registry:v1"
    assert len(slsa["subject"]) == 10
    assert verify_sidecar["bundle_dir"] == "bundle"
    assert not (bundle / artifact_bundles.SBOM_CYCLONEDX_SIDECAR).exists()
    public_payload = json.dumps(
        {"identity": identity, "abi": abi, "subjects": subjects, "slsa": slsa, "verify": verify_sidecar},
        sort_keys=True,
    )
    assert str(sibling) not in public_payload
    assert str(bundle) not in public_payload


def test_aoa_sdk_python_distribution_generates_sbom_and_slsa_subject_controls(tmp_path: Path) -> None:
    sibling = tmp_path / "aoa-sdk"
    manifest_dir = sibling / "sdk" / "distribution" / "manifests"
    dist = sibling / "dist"
    manifest_dir.mkdir(parents=True)
    dist.mkdir(parents=True)
    (sibling / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "aoa-sdk"',
                'version = "0.4.0"',
                'license = {text = "Apache-2.0"}',
                'dependencies = ["pydantic>=2.8", "typer>=0.12"]',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (dist / "aoa_sdk-0.4.0-py3-none-any.whl").write_bytes(b"fake wheel")
    (dist / "aoa_sdk-0.4.0.tar.gz").write_bytes(b"fake sdist")
    manifest = {
        "schema": "abyss_machine_artifact_bundle_manifest_v1",
        "id": "aoa-sdk-python-distribution",
        "artifact_class": "aoa_sdk_python_distribution",
        "owner_repo": "aoa-sdk",
        "policy_ref": artifact_bundles.POLICY_REF,
        "mode": "github_release",
        "subject_repo_root": "../../..",
        "artifact_identity": {
            "artifact_class": "aoa_sdk_python_distribution",
            "abi_epoch": "aoa_sdk_python_distribution_v1",
        },
        "abi_subject": {
            "path": "sdk/distribution/manifests/python_distribution.bundle.json",
            "artifact_identity_pointer": "/artifact_identity",
        },
        "artifact_subjects": [
            {"glob": "dist/aoa_sdk-*.whl", "role": "wheel"},
            {"glob": "dist/aoa_sdk-*.tar.gz", "role": "sdist"},
        ],
        "package": {
            "ecosystem": "python",
            "pyproject": "pyproject.toml",
            "name": "aoa-sdk",
        },
    }
    manifest_path = manifest_dir / "python_distribution.bundle.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    bundle = tmp_path / "bundle"

    build = artifact_bundles.build_sidecars(bundle, manifest_ref=manifest_path)
    sign = artifact_bundles.sign_bundle(bundle)
    verify = artifact_bundles.verify_bundle(bundle)
    identity = json.loads((bundle / artifact_bundles.IDENTITY_SIDECAR).read_text(encoding="utf-8"))
    provenance = json.loads((bundle / artifact_bundles.PROVENANCE_SIDECAR).read_text(encoding="utf-8"))
    abi = json.loads((bundle / artifact_bundles.ABI_SIDECAR).read_text(encoding="utf-8"))
    verify_sidecar = json.loads((bundle / artifact_bundles.VERIFY_SIDECAR).read_text(encoding="utf-8"))
    subjects = json.loads((bundle / artifact_bundles.SUBJECTS_SIDECAR).read_text(encoding="utf-8"))
    cdx = json.loads((bundle / artifact_bundles.SBOM_CYCLONEDX_SIDECAR).read_text(encoding="utf-8"))
    slsa_line = (bundle / artifact_bundles.SLSA_INTOTO_SIDECAR).read_text(encoding="utf-8").splitlines()[0]
    slsa = json.loads(slsa_line)

    assert build["ok"] is True
    assert sign["ok"] is True
    assert sign["status"] == "not_required"
    assert verify["ok"] is True
    assert identity["bundle_manifest_ref"] == "sdk/distribution/manifests/python_distribution.bundle.json"
    assert verify_sidecar["bundle_dir"] == "bundle"
    assert verify["required_controls"] == ["abi_signature", "sbom", "slsa_in_toto"]
    assert verify["verified_controls"] == ["abi_signature", "sbom", "slsa_in_toto"]
    assert len(subjects["files"]) == 2
    assert subjects["path_basis"] == "repo_relative"
    assert "repo_root" not in subjects
    assert cdx["bomFormat"] == "CycloneDX"
    assert slsa["_type"] == "https://in-toto.io/Statement/v1"
    assert slsa["predicateType"] == "https://slsa.dev/provenance/v1"
    public_payload = json.dumps(
        {
            "identity": identity,
            "provenance": provenance,
            "abi": abi,
            "subjects": subjects,
            "slsa": slsa,
            "verify": verify_sidecar,
        },
        sort_keys=True,
    )
    assert str(sibling) not in public_payload
    assert str(bundle) not in public_payload


def test_abyss_stack_runtime_config_bundle_generates_runtime_config_controls(tmp_path: Path) -> None:
    sibling = tmp_path / "abyss-stack"
    manifest_dir = sibling / "mechanics" / "release-support" / "manifests"
    dist = sibling / "dist" / "abyss-stack-runtime-config"
    manifest_dir.mkdir(parents=True)
    dist.mkdir(parents=True)
    (dist / "substrate.rendered.yml").write_text(
        "\n".join(
            [
                "services:",
                "  qdrant:",
                "    image: docker.io/qdrant/qdrant:v1.18.1@sha256:45f8e3ddc2570a4d029877e1b5ec1045c19b3852b4e22a55c7f43b05aea0ca89",
                "    ports:",
                "      - 127.0.0.1:6333:6333",
                "",
            ]
        ),
        encoding="utf-8",
    )
    manifest = {
        "schema": "abyss_machine_artifact_bundle_manifest_v1",
        "id": "abyss-stack-runtime-config-bundle",
        "artifact_class": "abyss_stack_runtime_config_bundle",
        "owner_repo": "abyss-stack",
        "policy_ref": artifact_bundles.POLICY_REF,
        "mode": "github_release",
        "subject_repo_root": "../../..",
        "build_type": "https://abyssos.local/buildtypes/runtime-config-bundle/v1",
        "artifact_identity": {
            "artifact_class": "abyss_stack_runtime_config_bundle",
            "abi_epoch": "abyss_stack_runtime_config_bundle_v1",
        },
        "abi_subject": {
            "path": "mechanics/release-support/manifests/runtime_config.bundle.json",
            "artifact_identity_pointer": "/artifact_identity",
        },
        "artifact_subjects": [
            {"glob": "dist/abyss-stack-runtime-config/*.yml", "role": "rendered_runtime_config"},
        ],
        "package": {
            "ecosystem": "compose",
            "name": "abyss-stack-runtime-config",
            "purl": "pkg:generic/abyss-stack-runtime-config@0",
        },
    }
    manifest_path = manifest_dir / "runtime_config.bundle.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    bundle = tmp_path / "bundle"

    build = artifact_bundles.build_sidecars(bundle, manifest_ref=manifest_path)
    sign = artifact_bundles.sign_bundle(bundle)
    verify = artifact_bundles.verify_bundle(bundle)
    identity = json.loads((bundle / artifact_bundles.IDENTITY_SIDECAR).read_text(encoding="utf-8"))
    subjects = json.loads((bundle / artifact_bundles.SUBJECTS_SIDECAR).read_text(encoding="utf-8"))
    slsa = json.loads((bundle / artifact_bundles.SLSA_INTOTO_SIDECAR).read_text(encoding="utf-8").splitlines()[0])
    verify_sidecar = json.loads((bundle / artifact_bundles.VERIFY_SIDECAR).read_text(encoding="utf-8"))

    assert build["ok"] is True
    assert sign["status"] == "not_required"
    assert verify["ok"] is True
    assert identity["bundle_manifest_ref"] == "mechanics/release-support/manifests/runtime_config.bundle.json"
    assert verify["required_controls"] == ["abi_signature", "sbom", "slsa_in_toto"]
    assert verify["verified_controls"] == ["abi_signature", "sbom", "slsa_in_toto"]
    assert subjects["files"][0]["role"] == "rendered_runtime_config"
    assert slsa["predicate"]["buildDefinition"]["buildType"] == "https://abyssos.local/buildtypes/runtime-config-bundle/v1"
    assert verify_sidecar["bundle_dir"] == "bundle"
    public_payload = json.dumps({"identity": identity, "subjects": subjects, "slsa": slsa, "verify": verify_sidecar}, sort_keys=True)
    assert str(sibling) not in public_payload
    assert str(bundle) not in public_payload


def test_aoa_evals_generated_report_index_bundle_generates_report_index_controls(tmp_path: Path) -> None:
    sibling = tmp_path / "aoa-evals"
    manifest_dir = sibling / "mechanics" / "release-support" / "parts" / "artifact-bundles" / "manifests"
    generated = sibling / "generated"
    manifest_dir.mkdir(parents=True)
    generated.mkdir(parents=True)
    (generated / "eval_report_index.min.json").write_text(
        json.dumps(
            {
                "schema": "aoa_eval_report_index_min_v1",
                "reports": [
                    {
                        "eval": "evals/workflow/aoa-verification-honesty",
                        "report": "evals/workflow/aoa-verification-honesty/reports/example-report.json",
                    }
                ],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema": "abyss_machine_artifact_bundle_manifest_v1",
        "id": "aoa-evals-generated-report-index-bundle",
        "artifact_class": "aoa_evals_generated_report_index_bundle",
        "owner_repo": "aoa-evals",
        "policy_ref": artifact_bundles.POLICY_REF_REPO_QUALIFIED,
        "mode": "github_release",
        "subject_repo_root": "../../../../..",
        "build_type": "https://abyssos.local/buildtypes/aoa-evals-generated-report-index/v1",
        "artifact_identity": {
            "artifact_class": "aoa_evals_generated_report_index_bundle",
            "abi_epoch": "aoa_evals_generated_report_index_bundle_v1",
        },
        "abi_subject": {
            "path": "generated/eval_report_index.min.json",
        },
        "artifact_subjects": [
            {"path": "generated/eval_report_index.min.json", "role": "generated_report_index"},
        ],
        "package": {
            "ecosystem": "proof-reader",
            "name": "aoa-evals-generated-report-index",
            "purl": "pkg:generic/aoa-evals-generated-report-index@0",
        },
    }
    manifest_path = manifest_dir / "report_index.bundle.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    bundle = tmp_path / "bundle"

    build = artifact_bundles.build_sidecars(bundle, manifest_ref=manifest_path)
    sign = artifact_bundles.sign_bundle(bundle)
    verify = artifact_bundles.verify_bundle(bundle)
    identity = json.loads((bundle / artifact_bundles.IDENTITY_SIDECAR).read_text(encoding="utf-8"))
    abi = json.loads((bundle / artifact_bundles.ABI_SIDECAR).read_text(encoding="utf-8"))
    subjects = json.loads((bundle / artifact_bundles.SUBJECTS_SIDECAR).read_text(encoding="utf-8"))
    slsa = json.loads((bundle / artifact_bundles.SLSA_INTOTO_SIDECAR).read_text(encoding="utf-8").splitlines()[0])
    verify_sidecar = json.loads((bundle / artifact_bundles.VERIFY_SIDECAR).read_text(encoding="utf-8"))

    assert build["ok"] is True
    assert sign["status"] == "not_required"
    assert verify["ok"] is True
    assert identity["bundle_manifest_ref"] == "mechanics/release-support/parts/artifact-bundles/manifests/report_index.bundle.json"
    assert verify["required_controls"] == ["abi_signature", "sbom", "slsa_in_toto"]
    assert verify["verified_controls"] == ["abi_signature", "sbom", "slsa_in_toto"]
    assert abi["external_subject"]["path"] == "generated/eval_report_index.min.json"
    assert len(subjects["files"]) == 1
    assert subjects["files"][0]["path"] == "generated/eval_report_index.min.json"
    assert subjects["files"][0]["role"] == "generated_report_index"
    assert slsa["predicate"]["buildDefinition"]["buildType"] == "https://abyssos.local/buildtypes/aoa-evals-generated-report-index/v1"
    assert verify_sidecar["bundle_dir"] == "bundle"


def test_aoa_session_memory_portable_bundle_generates_controls_and_update_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sibling = tmp_path / "aoa-session-memory"
    manifest_dir = sibling / "manifests" / "artifact_bundles"
    scripts = sibling / "scripts"
    schemas = sibling / "schemas"
    config = sibling / "config"
    hooks = sibling / "hooks"
    tests = sibling / "tests"
    skill = sibling / "skills" / "aoa-session-memory-audit"
    for path in (manifest_dir, scripts, schemas, config, hooks, tests, skill):
        path.mkdir(parents=True)
    for filename in ("AGENTS.md", "DESIGN.md", "DESIGN.AGENTS.md", "PIPELINE.md", "INSTALL.md", "READINESS.md", "README.md"):
        (sibling / filename).write_text(f"# {filename}\n", encoding="utf-8")
    (scripts / "aoa_session_memory.py").write_text("# portable session-memory CLI\n", encoding="utf-8")
    (schemas / "session.manifest.schema.json").write_text("{}\n", encoding="utf-8")
    (schemas / "segment.index.schema.json").write_text("{}\n", encoding="utf-8")
    (config / "event-taxonomy.json").write_text("{}\n", encoding="utf-8")
    (config / "search-providers.json").write_text("{}\n", encoding="utf-8")
    (hooks / "codex-hooks.user.example.json").write_text("{}\n", encoding="utf-8")
    (tests / "test_session_memory.py").write_text("# session memory tests\n", encoding="utf-8")
    (skill / "SKILL.md").write_text("# audit skill\n", encoding="utf-8")
    manifest = {
        "schema": "abyss_machine_artifact_bundle_manifest_v1",
        "id": "aoa-session-memory-portable-bundle",
        "artifact_class": "aoa_session_memory_portable_bundle",
        "owner_repo": "aoa-session-memory",
        "policy_ref": artifact_bundles.POLICY_REF_REPO_QUALIFIED,
        "mode": "os_abyss_local",
        "public_safe": True,
        "subject_repo_root": "../..",
        "artifact_identity": {
            "artifact_class": "aoa_session_memory_portable_bundle",
            "abi_epoch": "aoa_session_memory_portable_bundle_v1",
        },
        "abi_subject": {
            "path": "manifests/artifact_bundles/portable_bundle.bundle.json",
            "artifact_identity_pointer": "/artifact_identity",
        },
        "artifact_subjects": [
            {"path": "manifests/artifact_bundles/portable_bundle.bundle.json", "role": "bundle_manifest"},
            {"path": "AGENTS.md", "role": "route_doc"},
            {"path": "DESIGN.md", "role": "design_doc"},
            {"path": "DESIGN.AGENTS.md", "role": "agent_design_doc"},
            {"path": "PIPELINE.md", "role": "pipeline_doc"},
            {"path": "INSTALL.md", "role": "install_doc"},
            {"path": "READINESS.md", "role": "readiness_doc"},
            {"path": "README.md", "role": "readme"},
            {"path": "scripts/aoa_session_memory.py", "role": "portable_cli"},
            {"path": "schemas/session.manifest.schema.json", "role": "schema"},
            {"path": "schemas/segment.index.schema.json", "role": "schema"},
            {"path": "config/event-taxonomy.json", "role": "config"},
            {"path": "config/search-providers.json", "role": "config"},
            {"path": "hooks/codex-hooks.user.example.json", "role": "hook_example"},
            {"path": "tests/test_session_memory.py", "role": "test"},
            {"path": "skills/aoa-session-memory-audit/SKILL.md", "role": "skill_route"},
        ],
        "build_type": "https://abyssos.local/buildtypes/aoa-session-memory-portable-bundle/v1",
        "package": {
            "ecosystem": "portable-kernel",
            "name": "aoa-session-memory-portable-bundle",
            "purl": "pkg:generic/aoa-session-memory-portable-bundle@0",
        },
        "lifecycle": {
            "initial_state": "built-local",
            "promotion_path": ["built-local", "manually-verified", "release-ready", "published", "superseded", "revoked"],
            "latest_eligible_states": ["release-ready", "published"],
        },
        "consumer_contract": {
            "stable_interface": "abyss-machine artifacts trust-gate --artifact-class aoa_session_memory_portable_bundle --consumer-intent update_client --json",
            "consumer_expectation": "Workspace installers select the portable session-memory bundle only after registry latest selection, ABI/SBOM/SLSA verification, portable audit evidence, and update-client trust-gate allow or warn.",
            "admission_gate": "fail_closed_consumer_admission",
            "subject_store_required": True,
        },
    }
    manifest_path = manifest_dir / "portable_bundle.bundle.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    bundle = tmp_path / "bundle"
    store_root = tmp_path / "subject-store"
    registry = tmp_path / "registry"
    monkeypatch.setenv("ABYSS_MACHINE_ARTIFACT_SUBJECT_STORE_ROOT", str(store_root))

    build = artifact_bundles.build_sidecars(bundle, manifest_ref=manifest_path)
    sign = artifact_bundles.sign_bundle(bundle)
    verify = artifact_bundles.verify_bundle(bundle)
    trust_root_mode = "public_release"
    trust_root_evidence = _trust_root_evidence(
        trust_root_mode,
        subject_digest=_bundle_subject_digest(bundle),
        source_repo="aoa-session-memory",
        source_ref="manifests/artifact_bundles/portable_bundle.bundle.json",
    )
    pre_materialize_promotion = artifact_bundles.promote_bundle_evidence(
        bundle,
        registry,
        lifecycle_state="release-ready",
        source_repo="aoa-session-memory",
        source_ref="manifests/artifact_bundles/portable_bundle.bundle.json",
        producer="pytest aoa-session-memory export-bundle",
        trust_root_mode=trust_root_mode,
        trust_root_evidence=trust_root_evidence,
    )
    materialized = artifact_bundles.materialize_artifact_subjects(
        bundle,
        store_root=store_root,
        registry_dir=registry,
        manifest_ref=manifest_path,
        expected_source_repo="aoa-session-memory",
        expected_trust_root_mode=trust_root_mode,
    )
    verify_from_store = artifact_bundles.verify_bundle(bundle)
    identity = json.loads((bundle / artifact_bundles.IDENTITY_SIDECAR).read_text(encoding="utf-8"))
    abi = json.loads((bundle / artifact_bundles.ABI_SIDECAR).read_text(encoding="utf-8"))
    subjects = json.loads((bundle / artifact_bundles.SUBJECTS_SIDECAR).read_text(encoding="utf-8"))
    cdx = json.loads((bundle / artifact_bundles.SBOM_CYCLONEDX_SIDECAR).read_text(encoding="utf-8"))
    slsa = json.loads((bundle / artifact_bundles.SLSA_INTOTO_SIDECAR).read_text(encoding="utf-8").splitlines()[0])
    promoted = artifact_bundles.promote_bundle_evidence(
        bundle,
        registry,
        lifecycle_state="release-ready",
        source_repo="aoa-session-memory",
        source_ref="manifests/artifact_bundles/portable_bundle.bundle.json",
        producer="pytest aoa-session-memory export-bundle",
        trust_root_mode=trust_root_mode,
        trust_root_evidence=trust_root_evidence,
    )
    gate = artifact_bundles.trust_gate(
        registry,
        artifact_class="aoa_session_memory_portable_bundle",
        consumer_intent="update_client",
        expected_source_repo="aoa-session-memory",
        expected_trust_root_mode=trust_root_mode,
    )
    requirements = artifact_bundles.artifact_requirements(
        "aoa_session_memory_portable_bundle",
        registry_dir=registry,
    )

    assert build["ok"] is True
    assert sign["status"] == "not_required"
    assert verify["ok"] is True
    assert pre_materialize_promotion["ok"] is True
    assert materialized["ok"] is True
    assert materialized["consumer_intent"] == "update_client"
    assert materialized["materialization_admission"]["verdict"] == "allow"
    assert materialized["materialization_admission"]["reason"] == "only_required_subject_store_missing"
    assert materialized["trust_gate"]["verdict"] == "deny"
    assert artifact_bundles.REQUIRED_SUBJECT_STORE_BLOCKER in materialized["trust_gate"]["blockers"]
    assert verify_from_store["ok"] is True
    assert {row["source"] for row in verify_from_store["artifact_subject_resolution"]} == {"artifact_subject_store"}
    assert verify["required_controls"] == ["abi_signature", "sbom", "slsa_in_toto"]
    assert verify["verified_controls"] == ["abi_signature", "sbom", "slsa_in_toto"]
    assert identity["bundle_manifest_ref"] == "manifests/artifact_bundles/portable_bundle.bundle.json"
    assert identity["deferred_controls"]["c2pa"]["reason"].startswith("not public media")
    assert abi["external_subject"]["artifact_class"] == "aoa_session_memory_portable_bundle"
    assert abi["external_subject"]["artifact_identity"]["abi_epoch"] == "aoa_session_memory_portable_bundle_v1"
    assert len(subjects["files"]) == 16
    assert len(cdx["components"]) == 16
    assert slsa["predicate"]["buildDefinition"]["buildType"] == "https://abyssos.local/buildtypes/aoa-session-memory-portable-bundle/v1"
    assert len(slsa["subject"]) == 16
    assert promoted["ok"] is True
    assert promoted["record"]["artifact_subject_store"]["ok"] is True
    assert gate["ok"] is True
    assert gate["verdict"] == "allow"
    assert gate["decision"]["consumer_intent"] == "update_client"
    assert gate["inspected_claims"]["controls"]["required_controls_missing"] == []
    assert gate["inspected_claims"]["source"]["source_repo_matched"] is True
    assert gate["inspected_claims"]["trust_root"]["trust_root_mode_matched"] is True
    assert gate["inspected_claims"]["trust_root_evidence"]["ok"] is True
    assert requirements["rows"][0]["consumer"]["intent"] == "update_client"
    assert requirements["rows"][0]["registry_status"]["has_latest"] is True

    public_payload = json.dumps({"identity": identity, "abi": abi, "subjects": subjects, "cdx": cdx, "slsa": slsa}, sort_keys=True)
    assert str(sibling) not in public_payload
    assert str(bundle) not in public_payload
    assert "sessions/" not in public_payload
    assert "raw/" not in public_payload

    record_path = (
        registry
        / artifact_bundles.BUNDLE_REGISTRY_RECORDS_DIR
        / f"{promoted['record']['record_id'].removeprefix('sha256:')}.json"
    )
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["verified_controls"] = ["abi_signature", "slsa_in_toto"]
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    denied = artifact_bundles.trust_gate(
        registry,
        artifact_class="aoa_session_memory_portable_bundle",
        consumer_intent="update_client",
    )

    assert denied["ok"] is False
    assert denied["verdict"] == "deny"
    assert "required_controls_not_verified:sbom" in denied["blockers"]


def test_tree_of_sophia_generated_readmodel_bundle_generates_abi_only_controls(tmp_path: Path) -> None:
    sibling = tmp_path / "Tree-of-Sophia"
    manifest_dir = sibling / "mechanics" / "release-support" / "parts" / "artifact-bundles" / "manifests"
    generated = sibling / "ToS" / "derived-exports"
    manifest_dir.mkdir(parents=True)
    generated.mkdir(parents=True)
    root_entry_map = {
        "schema_version": "tos_root_entry_map_v1",
        "artifact_identity": {
            "artifact_class": "tree_of_sophia_generated_readmodel_bundle",
            "abi_epoch": "tree_of_sophia_generated_readmodel_bundle_v1",
        },
    }
    (generated / "root_entry_map.min.json").write_text(
        json.dumps(root_entry_map, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (generated / "kag_export.min.json").write_text(
        json.dumps({"schema": "tos_kag_export_v1", "kind": "source_node"}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (generated / "tos_corpus_index.min.json").write_text(
        json.dumps({"schema_version": "tos_corpus_index_v1", "counts": {"nodes": 1}}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema": "abyss_machine_artifact_bundle_manifest_v1",
        "id": "tree-of-sophia-generated-readmodel-bundle",
        "artifact_class": "tree_of_sophia_generated_readmodel_bundle",
        "owner_repo": "Tree-of-Sophia",
        "policy_ref": artifact_bundles.POLICY_REF_REPO_QUALIFIED,
        "mode": "os_abyss_local",
        "subject_repo_root": "../../../../..",
        "artifact_identity": {
            "artifact_class": "tree_of_sophia_generated_readmodel_bundle",
            "abi_epoch": "tree_of_sophia_generated_readmodel_bundle_v1",
        },
        "abi_subject": {
            "path": "ToS/derived-exports/root_entry_map.min.json",
            "artifact_identity_pointer": "/artifact_identity",
        },
        "artifact_subjects": [
            {"path": "ToS/derived-exports/root_entry_map.min.json", "role": "root_entry_map"},
            {"path": "ToS/derived-exports/kag_export.min.json", "role": "kag_export"},
            {"path": "ToS/derived-exports/tos_corpus_index.min.json", "role": "corpus_index"},
        ],
    }
    manifest_path = manifest_dir / "generated_readmodel.bundle.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    bundle = tmp_path / "bundle"

    build = artifact_bundles.build_sidecars(bundle, manifest_ref=manifest_path)
    sign = artifact_bundles.sign_bundle(bundle)
    verify = artifact_bundles.verify_bundle(bundle)
    identity = json.loads((bundle / artifact_bundles.IDENTITY_SIDECAR).read_text(encoding="utf-8"))
    abi = json.loads((bundle / artifact_bundles.ABI_SIDECAR).read_text(encoding="utf-8"))
    subjects = json.loads((bundle / artifact_bundles.SUBJECTS_SIDECAR).read_text(encoding="utf-8"))
    verify_sidecar = json.loads((bundle / artifact_bundles.VERIFY_SIDECAR).read_text(encoding="utf-8"))

    assert build["ok"] is True
    assert sign["status"] == "not_required"
    assert verify["ok"] is True
    assert verify["required_controls"] == ["abi_signature"]
    assert verify["verified_controls"] == ["abi_signature"]
    assert identity["deferred_controls"]["c2pa"]["reason"].startswith("use public_media_export")
    assert identity["deferred_controls"]["slsa_in_toto"]["reason"].startswith("required only when generated ToS readmodels")
    assert abi["external_subject"]["artifact_identity"]["abi_epoch"] == "tree_of_sophia_generated_readmodel_bundle_v1"
    assert [item["role"] for item in subjects["files"]] == ["kag_export", "root_entry_map", "corpus_index"]
    assert verify_sidecar["bundle_dir"] == "bundle"
    public_payload = json.dumps({"identity": identity, "abi": abi, "subjects": subjects, "verify": verify_sidecar}, sort_keys=True)
    assert str(sibling) not in public_payload
    assert str(bundle) not in public_payload


def test_dionysus_seed_route_readmodel_bundle_generates_abi_only_controls(tmp_path: Path) -> None:
    sibling = tmp_path / "Dionysus"
    manifest_dir = sibling / "docs" / "codex" / "artifact-bundles" / "manifests"
    generated = sibling / "generated"
    manifest_dir.mkdir(parents=True)
    generated.mkdir(parents=True)
    route_map = {
        "schema": "dionysus_seed_route_map_v2",
        "artifact_identity": {
            "artifact_class": "dionysus_seed_route_readmodel_bundle",
            "abi_epoch": "dionysus_seed_route_map_v2",
        },
    }
    (generated / "seed_route_map.min.json").write_text(
        json.dumps(route_map, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema": "abyss_machine_artifact_bundle_manifest_v1",
        "id": "dionysus-seed-route-readmodel-bundle",
        "artifact_class": "dionysus_seed_route_readmodel_bundle",
        "owner_repo": "Dionysus",
        "policy_ref": artifact_bundles.POLICY_REF_REPO_QUALIFIED,
        "mode": "os_abyss_local",
        "subject_repo_root": "../../../..",
        "artifact_identity": {
            "artifact_class": "dionysus_seed_route_readmodel_bundle",
            "abi_epoch": "dionysus_seed_route_map_v2",
        },
        "abi_subject": {
            "path": "generated/seed_route_map.min.json",
            "artifact_identity_pointer": "/artifact_identity",
        },
        "artifact_subjects": [
            {"path": "generated/seed_route_map.min.json", "role": "seed_route_map"},
        ],
    }
    manifest_path = manifest_dir / "seed_route_readmodel.bundle.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    bundle = tmp_path / "bundle"

    build = artifact_bundles.build_sidecars(bundle, manifest_ref=manifest_path)
    sign = artifact_bundles.sign_bundle(bundle)
    verify = artifact_bundles.verify_bundle(bundle)
    identity = json.loads((bundle / artifact_bundles.IDENTITY_SIDECAR).read_text(encoding="utf-8"))
    abi = json.loads((bundle / artifact_bundles.ABI_SIDECAR).read_text(encoding="utf-8"))
    subjects = json.loads((bundle / artifact_bundles.SUBJECTS_SIDECAR).read_text(encoding="utf-8"))
    verify_sidecar = json.loads((bundle / artifact_bundles.VERIFY_SIDECAR).read_text(encoding="utf-8"))

    assert build["ok"] is True
    assert sign["status"] == "not_required"
    assert verify["ok"] is True
    assert verify["required_controls"] == ["abi_signature"]
    assert verify["verified_controls"] == ["abi_signature"]
    assert identity["deferred_controls"]["c2pa"]["reason"].startswith("use public_media_export")
    assert "future Dionysus seed-pack credential class" in identity["deferred_controls"]["c2pa"]["reason"]
    assert "planting artifact bundle" in identity["deferred_controls"]["slsa_in_toto"]["reason"]
    assert abi["external_subject"]["artifact_identity"]["abi_epoch"] == "dionysus_seed_route_map_v2"
    assert subjects["files"][0]["path"] == "generated/seed_route_map.min.json"
    assert subjects["files"][0]["role"] == "seed_route_map"
    assert verify_sidecar["bundle_dir"] == "bundle"
    public_payload = json.dumps({"identity": identity, "abi": abi, "subjects": subjects, "verify": verify_sidecar}, sort_keys=True)
    assert str(sibling) not in public_payload
    assert str(bundle) not in public_payload


def test_verify_requires_explicit_signature_decision(tmp_path: Path) -> None:
    bundle = tmp_path / "unsigned-public-source-seed"

    artifact_bundles.build_sidecars(bundle, artifact_class="public_source_seed")
    verify = artifact_bundles.verify_bundle(bundle)

    assert verify["ok"] is False
    assert artifact_bundles.SIGNATURE_DECISION_SIDECAR in verify["missing"]


def test_verify_requires_local_provenance_for_host_local_evidence(tmp_path: Path) -> None:
    bundle = tmp_path / "host-local-evidence-with-missing-packet"

    artifact_bundles.build_sidecars(
        bundle,
        manifest_ref="manifests/artifact_bundles/host_local_evidence.sample.bundle.json",
    )
    artifact_bundles.sign_bundle(bundle)
    (bundle / artifact_bundles.LOCAL_PROVENANCE_SIDECAR).unlink()
    verify = artifact_bundles.verify_bundle(bundle)

    assert verify["ok"] is False
    assert artifact_bundles.LOCAL_PROVENANCE_SIDECAR in verify["missing"]
    assert any("artifact.local-provenance.json missing required field" in item for item in verify["errors"])


def test_warn_release_check_reports_failed_verification_without_blocking(tmp_path: Path) -> None:
    bundle = tmp_path / "warn-public-source-seed"

    artifact_bundles.build_sidecars(bundle, artifact_class="public_source_seed")
    release = artifact_bundles.release_check(bundle, enforcement="warn")

    assert release["ok"] is True
    assert release["verification_ok"] is False
    assert artifact_bundles.SIGNATURE_DECISION_SIDECAR in release["verification"]["missing"]


def test_bundle_manifest_lifecycle_rejects_unknown_state(tmp_path: Path) -> None:
    manifest = json.loads((ROOT / artifact_bundles.DEFAULT_BUNDLE_MANIFEST_REF).read_text(encoding="utf-8"))
    manifest["lifecycle"]["initial_state"] = "made-up"
    manifest_path = tmp_path / "bad.bundle.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unknown state"):
        artifact_bundles.load_bundle_manifest(manifest_path)

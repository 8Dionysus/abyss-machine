from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest


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


def _write_fake_c2patool(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys


if os.environ.get("FAKE_C2PA_STATE") == "invalid":
    print(json.dumps({
        "validation_state": "Invalid",
        "validation_status": [{"code": "assertion.dataHash.mismatch"}],
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


def test_public_media_export_verifies_c2pa_asset_binding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
            }
        ),
        encoding="utf-8",
    )
    fake_c2pa = tmp_path / "c2patool"
    _write_fake_c2patool(fake_c2pa)
    monkeypatch.setenv("ABYSS_MACHINE_C2PATOOL_BINARY", str(fake_c2pa))
    bundle = tmp_path / "bundle"

    artifact_bundles.build_sidecars(bundle, manifest_ref=manifest)
    artifact_bundles.sign_bundle(bundle)
    (bundle / artifact_bundles.C2PA_MANIFEST_SIDECAR).write_bytes(b"fake-c2pa")
    (bundle / artifact_bundles.C2PA_REPORT_SIDECAR).write_text(
        json.dumps({"validation_state": "Valid"}),
        encoding="utf-8",
    )

    verify = artifact_bundles.verify_bundle(bundle)
    assert verify["ok"] is True
    assert "c2pa" in verify["verified_controls"]
    assert any("untrusted" in warning for warning in verify["warnings"])

    monkeypatch.setenv("FAKE_C2PA_STATE", "invalid")
    invalid = artifact_bundles.verify_bundle(bundle)
    assert invalid["ok"] is False
    assert invalid["verified_controls"] == []
    assert "c2pa" in invalid["present_controls"]
    assert any("asset hash mismatch" in error for error in invalid["errors"])


def test_artifact_requirements_reports_sibling_producer_profile() -> None:
    requirements = artifact_bundles.artifact_requirements("aoa_sdk_python_distribution")
    row = requirements["rows"][0]

    assert requirements["ok"] is True
    assert requirements["schema"] == "abyss_machine_artifact_requirements_v1"
    assert row["owner_repo"] == "aoa-sdk"
    assert row["producer_profile"]["producer"]
    assert row["source_route"]["contract_surface_status"] == "external_subject_or_owner_bundle_required"
    assert row["controls"]["required"] == ["abi_signature", "sbom", "slsa_in_toto"]
    assert row["controls"]["deferred"]["sigstore_cosign"]["required"] is False
    assert row["trust_roots"]["local_dev"]["production_consumer_result"] == "manual_review_required"
    assert "affected" in row["agent_loop"]
    assert "GitHub OIDC is one producer adapter" in row["claim_limits"][2]


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
    assert accepted["rows"][0]["verdict"] == "accepted_lag"
    assert accepted["accept_sibling_lag"] is True


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


def test_update_lane_status_exposes_tuf_and_scitt_boundaries() -> None:
    status = artifact_bundles.update_lane_status()

    assert status["ok"] is True
    assert status["schema"] == "abyss_machine_update_transparency_lane_status_v1"
    assert status["summary"]["tuf_status"] == "prepared_v1"
    assert status["summary"]["blocking_v1"] is False
    assert "bootstrap_install_bundle" in [row["artifact_class"] for row in status["rows"]]
    assert "aoa_session_memory_portable_bundle" in [row["artifact_class"] for row in status["rows"]]
    assert status["tuf"]["metadata_sidecar"] == artifact_bundles.TUF_UPDATE_METADATA_SIDECAR
    assert "not a full external TUF repository" in status["claim_limits"][0]
    assert "external transparency integration point" in status["claim_limits"][1]


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
        expected_trust_root_mode="host_managed",
    )

    assert gate["ok"] is True
    assert gate["verdict"] == "allow"
    assert gate["manual_review"] == []
    assert "private captures" in gate["inspected_claims"]["privacy_boundary"]["value"]
    assert gate["inspected_claims"]["privacy_boundary"]["production_public_ready"] is True


def test_trust_gate_requires_manual_review_for_private_production_boundary(tmp_path: Path) -> None:
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
        expected_trust_root_mode="host_managed",
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
    }
    manifest_path = tmp_path / "bootstrap_install.bundle.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    bundle = tmp_path / "bundle"

    artifact_bundles.build_sidecars(bundle, manifest_ref=manifest_path)
    artifact_bundles.sign_bundle(bundle, backend="cosign-local-key")
    materialized = artifact_bundles.materialize_artifact_subjects(bundle, store_root=store_root, repo_root=tmp_path)
    artifact.unlink()

    verify = artifact_bundles.verify_bundle(bundle)
    registry = tmp_path / "registry"
    registered = artifact_bundles.write_bundle_registry_record(bundle, registry)

    assert materialized["ok"] is True
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


def test_ai_model_runtime_bundle_generates_ml_bom_and_required_release_controls(
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
    manifest_path = tmp_path / "ai_runtime_config.bundle.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    bundle = tmp_path / "bundle"

    build = artifact_bundles.build_sidecars(bundle, manifest_ref=manifest_path)
    sign = artifact_bundles.sign_bundle(bundle, backend="cosign-local-key")
    verify = artifact_bundles.verify_bundle(bundle)
    ml_bom = json.loads((bundle / artifact_bundles.MLBOM_CYCLONEDX_SIDECAR).read_text(encoding="utf-8"))

    assert build["ok"] is True
    assert artifact_bundles.MLBOM_CYCLONEDX_SIDECAR in build["written"]
    assert sign["ok"] is True
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
        },
    }
    manifest_path = manifest_dir / "portable_bundle.bundle.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    bundle = tmp_path / "bundle"
    store_root = tmp_path / "subject-store"
    monkeypatch.setenv("ABYSS_MACHINE_ARTIFACT_SUBJECT_STORE_ROOT", str(store_root))

    build = artifact_bundles.build_sidecars(bundle, manifest_ref=manifest_path)
    sign = artifact_bundles.sign_bundle(bundle)
    verify = artifact_bundles.verify_bundle(bundle)
    materialized = artifact_bundles.materialize_artifact_subjects(
        bundle,
        store_root=store_root,
        manifest_ref=manifest_path,
    )
    verify_from_store = artifact_bundles.verify_bundle(bundle)
    identity = json.loads((bundle / artifact_bundles.IDENTITY_SIDECAR).read_text(encoding="utf-8"))
    abi = json.loads((bundle / artifact_bundles.ABI_SIDECAR).read_text(encoding="utf-8"))
    subjects = json.loads((bundle / artifact_bundles.SUBJECTS_SIDECAR).read_text(encoding="utf-8"))
    cdx = json.loads((bundle / artifact_bundles.SBOM_CYCLONEDX_SIDECAR).read_text(encoding="utf-8"))
    slsa = json.loads((bundle / artifact_bundles.SLSA_INTOTO_SIDECAR).read_text(encoding="utf-8").splitlines()[0])
    registry = tmp_path / "registry"
    promoted = artifact_bundles.promote_bundle_evidence(
        bundle,
        registry,
        lifecycle_state="release-ready",
        source_repo="aoa-session-memory",
        source_ref="manifests/artifact_bundles/portable_bundle.bundle.json",
        producer="pytest aoa-session-memory export-bundle",
        trust_root_mode="host_managed",
    )
    gate = artifact_bundles.trust_gate(
        registry,
        artifact_class="aoa_session_memory_portable_bundle",
        consumer_intent="update_client",
        expected_source_repo="aoa-session-memory",
        expected_trust_root_mode="host_managed",
    )
    requirements = artifact_bundles.artifact_requirements(
        "aoa_session_memory_portable_bundle",
        registry_dir=registry,
    )

    assert build["ok"] is True
    assert sign["status"] == "not_required"
    assert verify["ok"] is True
    assert materialized["ok"] is True
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

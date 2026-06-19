from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import artifact_bundles


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

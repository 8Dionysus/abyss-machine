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
    public_payload = json.dumps({"identity": identity, "abi": abi, "subjects": subjects, "slsa": slsa, "verify": verify_sidecar}, sort_keys=True)
    assert str(sibling) not in public_payload
    assert str(bundle) not in public_payload


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

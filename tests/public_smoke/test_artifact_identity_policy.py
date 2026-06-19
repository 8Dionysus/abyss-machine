from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "manifests" / "artifact_signature_policy.manifest.json"
SCHEMA_INVENTORY = ROOT / "manifests" / "schema_inventory.manifest.json"

REQUIRED_IDENTITY_FIELDS = {
    "artifact_class",
    "surface_state",
    "owner_repo",
    "authority_ref",
    "producer",
    "consumer_expectation",
    "privacy_boundary",
    "content_identity",
    "abi_epoch",
    "contract_version",
    "trust_layer",
    "verification",
    "action",
}

REQUIRED_LOCAL_PROVENANCE_FIELDS = {
    "schema",
    "schema_ref",
    "artifact_class",
    "surface_state",
    "owner_repo",
    "authority_ref",
    "producer",
    "producer_command",
    "source_refs",
    "activity",
    "agent_or_tool",
    "created_at",
    "contract_version",
    "privacy_boundary",
    "content_identity",
    "consumer_expectation",
    "verification",
    "promotion_status",
}


def load_policy() -> dict:
    payload = json.loads(POLICY.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_every_artifact_class_has_identity_posture() -> None:
    policy = load_policy()
    policy_version = policy["policy_version"]
    assert REQUIRED_IDENTITY_FIELDS <= set(policy["identity_fields"])
    for class_id, class_rule in policy["artifact_classes"].items():
        identity = class_rule["identity"]
        assert REQUIRED_IDENTITY_FIELDS <= set(identity)
        assert identity["artifact_class"] == class_id
        if class_id in {
            "aoa_skills_release_manifest",
            "aoa_sdk_python_distribution",
            "abyss_stack_runtime_config_bundle",
            "aoa_evals_generated_report_index_bundle",
            "tree_of_sophia_generated_readmodel_bundle",
        }:
            expected_owner = {
                "aoa_skills_release_manifest": "aoa-skills",
                "aoa_sdk_python_distribution": "aoa-sdk",
                "abyss_stack_runtime_config_bundle": "abyss-stack",
                "aoa_evals_generated_report_index_bundle": "aoa-evals",
                "tree_of_sophia_generated_readmodel_bundle": "Tree-of-Sophia",
            }[class_id]
            assert identity["owner_repo"] == expected_owner
        else:
            assert identity["owner_repo"] == "abyss-machine"
        assert policy_version in identity["contract_version"]
        assert identity["authority_ref"]
        assert identity["trust_layer"]
        assert identity["verification"]


def test_host_local_evidence_uses_private_local_provenance_packet() -> None:
    policy = load_policy()
    packet = policy["local_provenance_packet"]
    assert packet["schema"] == "abyss_machine_local_provenance_packet_v1"
    assert packet["schema_ref"] == "schemas/local-provenance-packet.schema.json"
    assert "host_local_evidence" in packet["applies_to_artifact_classes"]
    assert packet["storage_route"].startswith("/var/lib/abyss-machine")
    assert packet["not_public_repo_content"] is True
    assert REQUIRED_LOCAL_PROVENANCE_FIELDS <= set(packet["required_fields"])
    inventory = load_json(SCHEMA_INVENTORY)
    assert packet["schema_ref"] in inventory["schemas"]

    host_identity = policy["artifact_classes"]["host_local_evidence"]["identity"]
    assert policy["artifact_classes"]["host_local_evidence"]["local_provenance"]["required"] is True
    assert {"local_provenance", "w3c_prov_lineage"} <= set(host_identity["trust_layer"])
    assert "private" in host_identity["privacy_boundary"].lower()


def test_local_provenance_schema_matches_packet_contract() -> None:
    policy = load_policy()
    packet = policy["local_provenance_packet"]
    schema = load_json(ROOT / packet["schema_ref"])

    assert schema["properties"]["schema"]["const"] == packet["schema"]
    assert REQUIRED_LOCAL_PROVENANCE_FIELDS <= set(schema["required"])
    assert schema["properties"]["schema_ref"]["const"] == packet["schema_ref"]


def test_ai_runtime_bundle_requires_ml_bom_when_published() -> None:
    policy = load_policy()
    ai_rule = policy["artifact_classes"]["ai_model_or_runtime_bundle"]
    assert ai_rule["ml_bom"]["required"] is True
    assert "ml_bom" in ai_rule["identity"]["trust_layer"]

    release_rules = {item["id"]: item for item in policy["release_artifact_rules"]}
    ai_release = release_rules["ai-model-runtime-release"]
    assert "ml_bom" in ai_release["required_controls"]
    assert ".mlbom.cdx.json" in ai_release["sidecar_extensions"]["ml_bom"]


def test_release_sidecar_expectations_cover_required_controls() -> None:
    policy = load_policy()
    expectations = policy["release_sidecar_expectations"]
    required_controls = {
        control
        for rule in policy["release_artifact_rules"]
        for control in rule["required_controls"]
    }

    assert required_controls <= set(expectations)
    assert "subject digest" in " ".join(expectations["slsa_in_toto"]["consumer_checks"]).lower()
    assert "signer identity" in " ".join(expectations["sigstore_cosign"]["consumer_checks"]).lower()
    assert "artifact digest" in " ".join(expectations["sbom"]["consumer_checks"]).lower()
    assert "privacy review" in " ".join(expectations["c2pa"]["consumer_checks"]).lower()


def test_aoa_sdk_python_distribution_requires_sbom_and_slsa_without_premature_cosign() -> None:
    policy = load_policy()
    sdk_rule = policy["artifact_classes"]["aoa_sdk_python_distribution"]
    assert sdk_rule["identity"]["owner_repo"] == "aoa-sdk"
    assert sdk_rule["abi_signature"]["required"] is True
    assert sdk_rule["sbom"]["required"] is True
    assert sdk_rule["slsa_in_toto"]["required"] is True
    assert sdk_rule["sigstore_cosign"]["required"] is False

    release_rules = {item["id"]: item for item in policy["release_artifact_rules"]}
    sdk_release = release_rules["aoa-sdk-python-distribution-release"]
    assert sdk_release["artifact_class"] == "aoa_sdk_python_distribution"
    assert sdk_release["required_controls"] == ["abi_signature", "sbom", "slsa_in_toto"]


def test_abyss_stack_runtime_config_bundle_requires_sbom_and_slsa_without_premature_cosign() -> None:
    policy = load_policy()
    stack_rule = policy["artifact_classes"]["abyss_stack_runtime_config_bundle"]
    assert stack_rule["identity"]["owner_repo"] == "abyss-stack"
    assert stack_rule["abi_signature"]["required"] is True
    assert stack_rule["sbom"]["required"] is True
    assert stack_rule["slsa_in_toto"]["required"] is True
    assert stack_rule["sigstore_cosign"]["required"] is False

    release_rules = {item["id"]: item for item in policy["release_artifact_rules"]}
    stack_release = release_rules["abyss-stack-runtime-config-bundle-release"]
    assert stack_release["artifact_class"] == "abyss_stack_runtime_config_bundle"
    assert stack_release["required_controls"] == ["abi_signature", "sbom", "slsa_in_toto"]


def test_aoa_evals_generated_report_index_requires_sbom_and_slsa_without_premature_cosign_or_c2pa() -> None:
    policy = load_policy()
    evals_rule = policy["artifact_classes"]["aoa_evals_generated_report_index_bundle"]
    assert evals_rule["identity"]["owner_repo"] == "aoa-evals"
    assert evals_rule["abi_signature"]["required"] is True
    assert evals_rule["sbom"]["required"] is True
    assert evals_rule["slsa_in_toto"]["required"] is True
    assert evals_rule["sigstore_cosign"]["required"] is False
    assert evals_rule["c2pa"]["required"] is False
    assert "PDF/media reports" in evals_rule["c2pa"]["trigger"]

    release_rules = {item["id"]: item for item in policy["release_artifact_rules"]}
    evals_release = release_rules["aoa-evals-generated-report-index-bundle-release"]
    assert evals_release["artifact_class"] == "aoa_evals_generated_report_index_bundle"
    assert evals_release["required_controls"] == ["abi_signature", "sbom", "slsa_in_toto"]


def test_tree_of_sophia_generated_readmodel_requires_abi_without_premature_media_or_release_controls() -> None:
    policy = load_policy()
    tos_rule = policy["artifact_classes"]["tree_of_sophia_generated_readmodel_bundle"]
    assert tos_rule["identity"]["owner_repo"] == "Tree-of-Sophia"
    assert tos_rule["identity"]["trust_layer"] == ["abi_contract_signature"]
    assert tos_rule["abi_signature"]["required"] is True
    assert tos_rule["sbom"]["required"] is False
    assert tos_rule["slsa_in_toto"]["required"] is False
    assert tos_rule["sigstore_cosign"]["required"] is False
    assert tos_rule["c2pa"]["required"] is False
    assert "external release/export bundle" in tos_rule["slsa_in_toto"]["trigger"]
    assert "PDFs" in tos_rule["c2pa"]["trigger"]

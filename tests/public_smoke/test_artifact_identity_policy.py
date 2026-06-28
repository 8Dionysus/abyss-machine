from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "manifests" / "artifact_signature_policy.manifest.json"
SCHEMA_INVENTORY = ROOT / "manifests" / "schema_inventory.manifest.json"
PUBLIC_MEDIA_MANIFEST = ROOT / "manifests" / "artifact_bundles" / "public_media_export.bundle.json"

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


def test_artifact_trust_controls_keep_primary_standard_refs() -> None:
    policy = load_policy()
    refs = policy["primary_standard_refs"]

    for control in {
        "sbom",
        "ml_bom",
        "slsa_in_toto",
        "sigstore_cosign",
        "c2pa",
        "oci_artifact",
        "tuf",
        "scitt",
    }:
        assert refs[control]
        assert all(str(item).startswith("https://") for item in refs[control])

    assert any("cyclonedx.org" in item for item in refs["sbom"])
    assert any("slsa.dev/spec" in item for item in refs["slsa_in_toto"])
    assert any("sigstore.dev" in item for item in refs["sigstore_cosign"])
    assert any("C2PA-TRUST-LIST.pem" in item for item in refs["c2pa"])
    assert any("opencontainers/distribution-spec" in item for item in refs["oci_artifact"])
    assert any("theupdateframework.github.io/specification" in item for item in refs["tuf"])
    assert any("datatracker.ietf.org/doc/rfc9699" in item for item in refs["scitt"])


def test_public_media_export_names_c2pa_primary_refs() -> None:
    manifest = load_json(PUBLIC_MEDIA_MANIFEST)
    refs = manifest["c2pa"]["standard_refs"]

    assert refs["specification"] == "https://spec.c2pa.org/specifications/specifications/2.4/specs/C2PA_Specification.html"
    assert refs["conformance_program"] == "https://c2pa.org/conformance/"
    assert refs["production_trust_list"].endswith("/trust-list/C2PA-TRUST-LIST.pem")
    assert "c2patool" in refs["c2patool_usage"]


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
            "role_contract_registry",
            "source_owned_kag_export_capsule",
            "derived_kag_registry_readmodel_bundle",
            "derived_memory_object_readmodel_family",
            "thin_routing_readmodel_bundle",
            "playbook_registry_bundle",
            "aoa_sdk_python_distribution",
            "abyss_stack_runtime_config_bundle",
            "aoa_evals_generated_report_index_bundle",
            "aoa_session_memory_portable_bundle",
            "derived_observability_readmodel_catalog",
            "tree_of_sophia_generated_readmodel_bundle",
            "dionysus_seed_route_readmodel_bundle",
        }:
            expected_owner = {
                "aoa_skills_release_manifest": "aoa-skills",
                "role_contract_registry": "aoa-agents",
                "source_owned_kag_export_capsule": "aoa-techniques",
                "derived_kag_registry_readmodel_bundle": "aoa-kag",
                "derived_memory_object_readmodel_family": "aoa-memo",
                "thin_routing_readmodel_bundle": "aoa-routing",
                "playbook_registry_bundle": "aoa-playbooks",
                "aoa_sdk_python_distribution": "aoa-sdk",
                "abyss_stack_runtime_config_bundle": "abyss-stack",
                "aoa_evals_generated_report_index_bundle": "aoa-evals",
                "aoa_session_memory_portable_bundle": "aoa-session-memory",
                "derived_observability_readmodel_catalog": "aoa-stats",
                "tree_of_sophia_generated_readmodel_bundle": "Tree-of-Sophia",
                "dionysus_seed_route_readmodel_bundle": "Dionysus",
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


def test_aoa_session_memory_portable_bundle_requires_abi_sbom_slsa_and_update_lane() -> None:
    policy = load_policy()
    session_rule = policy["artifact_classes"]["aoa_session_memory_portable_bundle"]
    assert session_rule["identity"]["owner_repo"] == "aoa-session-memory"
    assert session_rule["identity"]["abi_epoch"] == "aoa_session_memory_portable_bundle_v1"
    assert session_rule["identity"]["trust_layer"] == ["abi_contract_signature", "sbom", "slsa_in_toto"]
    assert session_rule["abi_signature"]["required"] is True
    assert session_rule["sbom"]["required"] is True
    assert session_rule["slsa_in_toto"]["required"] is True
    assert session_rule["sigstore_cosign"]["required"] is False
    assert session_rule["c2pa"]["required"] is False
    assert "raw transcripts" in session_rule["identity"]["privacy_boundary"]
    assert "raw .aoa evidence never becomes trust authority" in session_rule["identity"]["consumer_expectation"]

    release_rules = {item["id"]: item for item in policy["release_artifact_rules"]}
    session_release = release_rules["aoa-session-memory-portable-bundle-release"]
    assert session_release["artifact_class"] == "aoa_session_memory_portable_bundle"
    assert session_release["required_controls"] == ["abi_signature", "sbom", "slsa_in_toto"]
    assert "aoa_session_memory_portable_bundle" in policy["update_transparency_lane"]["tuf"]["applies_to_artifact_classes"]


def test_aoa_stats_summary_surface_catalog_requires_abi_and_sbom_lite_without_premature_release_provenance() -> None:
    policy = load_policy()
    stats_rule = policy["artifact_classes"]["derived_observability_readmodel_catalog"]
    assert stats_rule["identity"]["owner_repo"] == "aoa-stats"
    assert stats_rule["identity"]["trust_layer"] == ["abi_contract_signature", "sbom"]
    assert stats_rule["abi_signature"]["required"] is True
    assert stats_rule["sbom"]["required"] is True
    assert stats_rule["slsa_in_toto"]["required"] is False
    assert stats_rule["sigstore_cosign"]["required"] is False
    assert stats_rule["c2pa"]["required"] is False
    assert "external release/export bundle" in stats_rule["slsa_in_toto"]["trigger"]
    assert "public media" in stats_rule["c2pa"]["trigger"]

    release_rules = {item["id"]: item for item in policy["release_artifact_rules"]}
    stats_release = release_rules["aoa-stats-summary-surface-catalog-release"]
    assert stats_release["artifact_class"] == "derived_observability_readmodel_catalog"
    assert stats_release["required_controls"] == ["abi_signature", "sbom"]


def test_aoa_agents_role_registry_requires_abi_and_slsa_without_premature_sbom_or_cosign() -> None:
    policy = load_policy()
    agents_rule = policy["artifact_classes"]["role_contract_registry"]
    assert agents_rule["identity"]["owner_repo"] == "aoa-agents"
    assert agents_rule["identity"]["trust_layer"] == ["abi_contract_signature", "slsa_in_toto"]
    assert agents_rule["abi_signature"]["required"] is True
    assert agents_rule["sbom"]["required"] is False
    assert agents_rule["slsa_in_toto"]["required"] is True
    assert agents_rule["sigstore_cosign"]["required"] is False
    assert agents_rule["c2pa"]["required"] is False
    assert "distribution or release bundle" in agents_rule["sbom"]["trigger"]
    assert "signed release assets" in agents_rule["sigstore_cosign"]["trigger"]

    release_rules = {item["id"]: item for item in policy["release_artifact_rules"]}
    agents_release = release_rules["aoa-agents-role-contract-registry-release"]
    assert agents_release["artifact_class"] == "role_contract_registry"
    assert agents_release["required_controls"] == ["abi_signature", "slsa_in_toto"]


def test_aoa_techniques_kag_export_requires_abi_and_slsa_without_premature_sbom_or_cosign() -> None:
    policy = load_policy()
    techniques_rule = policy["artifact_classes"]["source_owned_kag_export_capsule"]
    assert techniques_rule["identity"]["owner_repo"] == "aoa-techniques"
    assert techniques_rule["identity"]["trust_layer"] == ["abi_contract_signature", "slsa_in_toto"]
    assert techniques_rule["abi_signature"]["required"] is True
    assert techniques_rule["sbom"]["required"] is False
    assert techniques_rule["slsa_in_toto"]["required"] is True
    assert techniques_rule["sigstore_cosign"]["required"] is False
    assert techniques_rule["c2pa"]["required"] is False
    assert "distribution or release bundle" in techniques_rule["sbom"]["trigger"]
    assert "signed release assets" in techniques_rule["sigstore_cosign"]["trigger"]
    assert "PDF/media/content exports" in techniques_rule["c2pa"]["trigger"]

    release_rules = {item["id"]: item for item in policy["release_artifact_rules"]}
    techniques_release = release_rules["aoa-techniques-kag-export-capsule-release"]
    assert techniques_release["artifact_class"] == "source_owned_kag_export_capsule"
    assert techniques_release["required_controls"] == ["abi_signature", "slsa_in_toto"]


def test_aoa_skills_release_manifest_uses_local_release_provenance_without_false_slsa() -> None:
    policy = load_policy()
    skills_rule = policy["artifact_classes"]["aoa_skills_release_manifest"]
    assert skills_rule["identity"]["owner_repo"] == "aoa-skills"
    assert skills_rule["identity"]["trust_layer"] == [
        "abi_contract_signature",
        "local_release_provenance",
        "w3c_prov_lineage",
    ]
    assert skills_rule["abi_signature"]["required"] is True
    assert skills_rule["slsa_in_toto"]["required"] is False
    assert skills_rule["sigstore_cosign"]["required"] is False
    assert "external release artifact" in skills_rule["slsa_in_toto"]["trigger"]


def test_aoa_kag_registry_readmodel_requires_abi_sbom_and_slsa_without_premature_cosign_or_c2pa() -> None:
    policy = load_policy()
    kag_rule = policy["artifact_classes"]["derived_kag_registry_readmodel_bundle"]
    assert kag_rule["identity"]["owner_repo"] == "aoa-kag"
    assert kag_rule["identity"]["trust_layer"] == ["abi_contract_signature", "sbom", "slsa_in_toto"]
    assert kag_rule["abi_signature"]["required"] is True
    assert kag_rule["sbom"]["required"] is True
    assert kag_rule["slsa_in_toto"]["required"] is True
    assert kag_rule["sigstore_cosign"]["required"] is False
    assert kag_rule["c2pa"]["required"] is False
    assert "subject inventory" in kag_rule["sbom"]["trigger"]
    assert "signed release assets" in kag_rule["sigstore_cosign"]["trigger"]
    assert "PDF/media/content exports" in kag_rule["c2pa"]["trigger"]

    release_rules = {item["id"]: item for item in policy["release_artifact_rules"]}
    kag_release = release_rules["aoa-kag-registry-readmodel-release"]
    assert kag_release["artifact_class"] == "derived_kag_registry_readmodel_bundle"
    assert kag_release["required_controls"] == ["abi_signature", "sbom", "slsa_in_toto"]


def test_aoa_memo_memory_object_readmodels_require_abi_and_slsa_without_premature_sbom_or_cosign() -> None:
    policy = load_policy()
    memo_rule = policy["artifact_classes"]["derived_memory_object_readmodel_family"]
    assert memo_rule["identity"]["owner_repo"] == "aoa-memo"
    assert memo_rule["identity"]["trust_layer"] == ["abi_contract_signature", "slsa_in_toto"]
    assert memo_rule["abi_signature"]["required"] is True
    assert memo_rule["sbom"]["required"] is False
    assert memo_rule["slsa_in_toto"]["required"] is True
    assert memo_rule["sigstore_cosign"]["required"] is False
    assert memo_rule["c2pa"]["required"] is False
    assert "distribution or release bundle" in memo_rule["sbom"]["trigger"]
    assert "signed release assets" in memo_rule["sigstore_cosign"]["trigger"]
    assert "PDF/media/content exports" in memo_rule["c2pa"]["trigger"]

    release_rules = {item["id"]: item for item in policy["release_artifact_rules"]}
    memo_release = release_rules["aoa-memo-memory-object-readmodels-release"]
    assert memo_release["artifact_class"] == "derived_memory_object_readmodel_family"
    assert memo_release["required_controls"] == ["abi_signature", "slsa_in_toto"]


def test_aoa_routing_thin_router_requires_abi_sbom_and_slsa_without_premature_cosign_or_c2pa() -> None:
    policy = load_policy()
    routing_rule = policy["artifact_classes"]["thin_routing_readmodel_bundle"]
    assert routing_rule["identity"]["owner_repo"] == "aoa-routing"
    assert routing_rule["identity"]["trust_layer"] == ["abi_contract_signature", "sbom", "slsa_in_toto"]
    assert routing_rule["abi_signature"]["required"] is True
    assert routing_rule["sbom"]["required"] is True
    assert routing_rule["slsa_in_toto"]["required"] is True
    assert routing_rule["sigstore_cosign"]["required"] is False
    assert routing_rule["c2pa"]["required"] is False
    assert "subject inventory" in routing_rule["sbom"]["trigger"]
    assert "release assets" in routing_rule["sigstore_cosign"]["trigger"]
    assert "PDF/media/content exports" in routing_rule["c2pa"]["trigger"]

    release_rules = {item["id"]: item for item in policy["release_artifact_rules"]}
    routing_release = release_rules["aoa-routing-thin-router-release"]
    assert routing_release["artifact_class"] == "thin_routing_readmodel_bundle"
    assert routing_release["required_controls"] == ["abi_signature", "sbom", "slsa_in_toto"]


def test_aoa_playbooks_registry_requires_abi_and_slsa_without_premature_sbom_or_cosign() -> None:
    policy = load_policy()
    playbooks_rule = policy["artifact_classes"]["playbook_registry_bundle"]
    assert playbooks_rule["identity"]["owner_repo"] == "aoa-playbooks"
    assert playbooks_rule["identity"]["trust_layer"] == ["abi_contract_signature", "slsa_in_toto"]
    assert playbooks_rule["abi_signature"]["required"] is True
    assert playbooks_rule["sbom"]["required"] is False
    assert playbooks_rule["slsa_in_toto"]["required"] is True
    assert playbooks_rule["sigstore_cosign"]["required"] is False
    assert playbooks_rule["c2pa"]["required"] is False
    assert "distribution or release bundle" in playbooks_rule["sbom"]["trigger"]
    assert "signed release assets" in playbooks_rule["sigstore_cosign"]["trigger"]
    assert "PDF/media/content exports" in playbooks_rule["c2pa"]["trigger"]

    release_rules = {item["id"]: item for item in policy["release_artifact_rules"]}
    playbooks_release = release_rules["aoa-playbooks-registry-bundle-release"]
    assert playbooks_release["artifact_class"] == "playbook_registry_bundle"
    assert playbooks_release["required_controls"] == ["abi_signature", "slsa_in_toto"]


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


def test_dionysus_seed_route_readmodel_requires_abi_without_premature_seed_pack_credentials() -> None:
    policy = load_policy()
    dionysus_rule = policy["artifact_classes"]["dionysus_seed_route_readmodel_bundle"]
    assert dionysus_rule["identity"]["owner_repo"] == "Dionysus"
    assert dionysus_rule["identity"]["abi_epoch"] == "dionysus_seed_route_map_v2"
    assert dionysus_rule["identity"]["trust_layer"] == ["abi_contract_signature"]
    assert dionysus_rule["abi_signature"]["required"] is True
    assert dionysus_rule["sbom"]["required"] is False
    assert dionysus_rule["slsa_in_toto"]["required"] is False
    assert dionysus_rule["sigstore_cosign"]["required"] is False
    assert dionysus_rule["c2pa"]["required"] is False
    assert "planting artifact bundle" in dionysus_rule["slsa_in_toto"]["trigger"]
    assert "future Dionysus seed-pack credential class" in dionysus_rule["c2pa"]["trigger"]

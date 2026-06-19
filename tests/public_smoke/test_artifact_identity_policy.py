from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "manifests" / "artifact_signature_policy.manifest.json"

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
    "trust_layer",
    "verification",
    "action",
}

REQUIRED_LOCAL_PROVENANCE_FIELDS = {
    "schema",
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


def test_every_artifact_class_has_identity_posture() -> None:
    policy = load_policy()
    assert REQUIRED_IDENTITY_FIELDS <= set(policy["identity_fields"])
    for class_id, class_rule in policy["artifact_classes"].items():
        identity = class_rule["identity"]
        assert REQUIRED_IDENTITY_FIELDS <= set(identity)
        assert identity["artifact_class"] == class_id
        assert identity["owner_repo"] == "abyss-machine"
        assert identity["authority_ref"]
        assert identity["trust_layer"]
        assert identity["verification"]


def test_host_local_evidence_uses_private_local_provenance_packet() -> None:
    policy = load_policy()
    packet = policy["local_provenance_packet"]
    assert packet["schema"] == "abyss_machine_local_provenance_packet_v1"
    assert "host_local_evidence" in packet["applies_to_artifact_classes"]
    assert packet["storage_route"].startswith("/var/lib/abyss-machine")
    assert packet["not_public_repo_content"] is True
    assert REQUIRED_LOCAL_PROVENANCE_FIELDS <= set(packet["required_fields"])

    host_identity = policy["artifact_classes"]["host_local_evidence"]["identity"]
    assert {"local_provenance", "w3c_prov_lineage"} <= set(host_identity["trust_layer"])
    assert "private" in host_identity["privacy_boundary"].lower()


def test_ai_runtime_bundle_requires_ml_bom_when_published() -> None:
    policy = load_policy()
    ai_rule = policy["artifact_classes"]["ai_model_or_runtime_bundle"]
    assert ai_rule["ml_bom"]["required"] is True
    assert "ml_bom" in ai_rule["identity"]["trust_layer"]

    release_rules = {item["id"]: item for item in policy["release_artifact_rules"]}
    ai_release = release_rules["ai-model-runtime-release"]
    assert "ml_bom" in ai_release["required_controls"]
    assert ".mlbom.cdx.json" in ai_release["sidecar_extensions"]["ml_bom"]

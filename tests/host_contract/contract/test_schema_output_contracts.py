from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from conftest import parse_json_stdout


EXPECTED_CONFIG_SCHEMAS = {
    Path("/etc/abyss-machine/agents-mesh.json"): "abyss_machine_agents_mesh_config_v1",
    Path("/etc/abyss-machine/ai/config.json"): "abyss_machine_ai_config_v1",
    Path("/etc/abyss-machine/bridge.json"): "abyss_machine_bridge_v1",
    Path("/etc/abyss-machine/cooling/config.json"): "abyss_machine_cooling_config_v1",
    Path("/etc/abyss-machine/dictation/config.json"): "abyss_machine_dictation_config_v1",
    Path("/etc/abyss-machine/dictation/replacements.json"): "abyss_machine_dictation_replacements_v1",
    Path("/etc/abyss-machine/doctor-policy.json"): "abyss_machine_doctor_policy_v1",
    Path("/etc/abyss-machine/maps-policy.json"): "abyss_machine_maps_policy_v1",
    Path("/etc/abyss-machine/memory-policy.json"): "abyss_machine_memory_policy_v1",
    Path("/etc/abyss-machine/mode-policy.json"): "abyss_machine_mode_policy_v1",
    Path("/etc/abyss-machine/nervous/index.json"): "abyss_machine_nervous_index_config_v1",
    Path("/etc/abyss-machine/nervous/policy.json"): "abyss_machine_nervous_policy_v1",
    Path("/etc/abyss-machine/nervous/privacy.json"): "abyss_machine_nervous_privacy_v1",
    Path("/etc/abyss-machine/nervous/sources.json"): "abyss_machine_nervous_sources_v1",
    Path("/etc/abyss-machine/observability/config.json"): "abyss_machine_observability_config_v1",
    Path("/etc/abyss-machine/resource-policy.json"): "abyss_machine_resource_policy_v1",
    Path("/etc/abyss-machine/stack-bridge.json"): "abyss_machine_stack_bridge_manifest_v1",
    Path("/etc/abyss-machine/storage-policy.json"): "abyss_machine_storage_policy_v1",
}


def assert_envelope(payload: dict[str, Any], schema: str) -> None:
    assert payload.get("schema") == schema
    assert isinstance(payload.get("version"), str) and payload["version"]


@pytest.mark.quick
@pytest.mark.contract
def test_host_policy_config_schema_names_are_pinned() -> None:
    for path, schema in EXPECTED_CONFIG_SCHEMAS.items():
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload.get("schema") == schema, str(path)
        assert isinstance(payload.get("version"), str) and payload["version"], str(path)


@pytest.mark.quick
@pytest.mark.contract
def test_core_policy_read_commands_preserve_schema_envelopes(run_abyss_machine) -> None:
    memory = parse_json_stdout(run_abyss_machine("memory", "policy", "--json"))
    assert_envelope(memory, "abyss_machine_memory_policy_v1")
    assert isinstance(memory.get("classes"), list)
    assert {"green", "watch", "warm", "hot", "critical"}.issubset(memory["classes"])
    assert isinstance(memory.get("thresholds"), dict)
    assert isinstance(memory.get("zram_swap_relief"), dict)

    resource = parse_json_stdout(run_abyss_machine("resource", "policy", "--json"))
    assert_envelope(resource, "abyss_machine_resource_policy_v1")
    assert isinstance(resource.get("classes"), list)
    assert {"probe", "light", "medium", "heavy", "sustained"}.issubset(resource["classes"])
    assert isinstance(resource.get("gates"), dict)
    assert isinstance(resource.get("launch"), dict)

    storage = parse_json_stdout(run_abyss_machine("storage", "policy", "--json"))
    assert_envelope(storage, "abyss_machine_storage_policy_read_v1")
    assert storage.get("ok") is True
    document = storage.get("document")
    assert isinstance(document, dict)
    assert document.get("schema") == "abyss_machine_storage_policy_v1"
    assert isinstance(document.get("large_root"), dict)
    assert isinstance(document.get("cache_environment_routes"), dict)
    assert isinstance(document.get("hook_points"), dict)

    maps = parse_json_stdout(run_abyss_machine("maps", "policy", "--json"))
    assert_envelope(maps, "abyss_machine_maps_policy_v1")
    assert isinstance(maps.get("axes"), list)
    assert {axis.get("axis") for axis in maps["axes"]}.issuperset(
        {"by-time", "by-freshness", "by-rag-run", "by-memory-candidate", "by-eval-packet", "by-kag-export"}
    )
    assert maps.get("policy", {}).get("automatic_action") is False
    assert maps.get("policy", {}).get("automatic_response") is False

    maps_packet = parse_json_stdout(
        run_abyss_machine("maps", "packet", "--axis", "by-eval-packet", "--consumer", "aoa-evals", "--json")
    )
    assert_envelope(maps_packet, "abyss_machine_maps_packet_v1")
    assert maps_packet.get("ok") is True
    assert maps_packet.get("truth_status") == "generated_route_signal_not_source_truth"
    assert maps_packet.get("consumer") == "aoa-evals"
    assert maps_packet.get("summary", {}).get("automatic_action") is False
    assert maps_packet.get("summary", {}).get("proof_verdict") is False
    assert isinstance(maps_packet.get("entries"), list) and maps_packet["entries"]


@pytest.mark.quick
@pytest.mark.contract
def test_planning_outputs_keep_non_apply_schema_contracts(run_abyss_machine) -> None:
    memory_plan = parse_json_stdout(run_abyss_machine("memory", "plan", "--json", timeout=30.0))
    assert_envelope(memory_plan, "abyss_machine_memory_plan_v1")
    assert memory_plan.get("ok") is True
    assert isinstance(memory_plan.get("pressure"), dict)
    assert isinstance(memory_plan.get("recommended_new_work"), dict)
    assert memory_plan.get("executed") is None

    resource_plan = parse_json_stdout(
        run_abyss_machine(
            "resource",
            "plan",
            "--class",
            "probe",
            "--kind",
            "generic",
            "--json",
            timeout=30.0,
        )
    )
    assert_envelope(resource_plan, "abyss_machine_resource_plan_v1")
    assert resource_plan.get("ok") is True
    assert resource_plan.get("executed") is None
    assert resource_plan.get("permission_required") is not True


@pytest.mark.live
@pytest.mark.contract
def test_live_preflight_and_validator_outputs_keep_schema_contracts(run_abyss_machine) -> None:
    preflight = parse_json_stdout(
        run_abyss_machine(
            "storage",
            "write-preflight",
            "--kind",
            "cache",
            "--bytes",
            "1024",
            "--target",
            "/srv/abyss-machine/tmp/schema-contract-probe",
            "--json",
            timeout=30.0,
        )
    )
    assert_envelope(preflight, "abyss_machine_storage_write_preflight_v1")
    assert preflight.get("ok") is True
    assert preflight.get("decision") == "allow"
    assert preflight.get("request", {}).get("target_requested") == "/srv/abyss-machine/tmp/schema-contract-probe"
    assert preflight.get("target", {}).get("protection", {}).get("class") == "host_owned_allowed"

    for args, schema in (
        (("docs", "mesh-validate", "--json"), "abyss_machine_docs_agents_mesh_validate_v1"),
        (("maps", "validate", "--json"), "abyss_machine_maps_validate_v1"),
        (("stack-bridge", "validate", "--json"), "abyss_machine_stack_bridge_validate_v1"),
        (("topology", "validate", "--json"), "abyss_machine_topology_validate_v1"),
    ):
        payload = parse_json_stdout(run_abyss_machine(*args, timeout=60.0))
        assert_envelope(payload, schema)
        assert payload.get("summary", {}).get("fails", 0) == 0

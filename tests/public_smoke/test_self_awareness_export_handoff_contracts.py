from __future__ import annotations

from typing import Any

from abyss_machine import self_awareness_export_handoff_contracts as contracts


def _unexpected(*_args: Any, **_kwargs: Any) -> Any:
    raise AssertionError("unexpected contract callback")


def _port(
    *,
    coverage_impact=None,
    coverage_impact_complete=None,
) -> contracts.ExportStackHandoffContractPort:
    return contracts.ExportStackHandoffContractPort(
        activation_proof_overlay=_unexpected,
        activation_proof_complete=_unexpected,
        stack_organ_use_packet_complete=_unexpected,
        activation_smoke_compact=_unexpected,
        activation_smoke_row_complete=_unexpected,
        coverage_impact_complete=coverage_impact_complete or _unexpected,
        coverage_impact=coverage_impact or _unexpected,
        closure_acceptance_complete=lambda packet: bool(packet),
    )


def test_export_artifact_refs_projects_only_public_handoff_fields() -> None:
    refs = contracts.export_artifact_refs(
        {
            "requirements": {
                "path": "/var/lib/abyss-machine/self-awareness/requirements/latest.json",
                "history_path": "/var/lib/abyss-machine/self-awareness/requirements/2026-07-10.jsonl",
                "schema": "abyss_machine_self_awareness_requirements_v1",
                "sha256": "abc123",
                "artifact_status": "ready",
                "evidence_ref": {"kind": "latest"},
                "private_payload": "must-not-project",
            },
            "malformed": "not-a-document",
        },
        ["requirements", "malformed", "missing"],
    )

    assert refs == {
        "requirements": {
            "path": "/var/lib/abyss-machine/self-awareness/requirements/latest.json",
            "history_path": "/var/lib/abyss-machine/self-awareness/requirements/2026-07-10.jsonl",
            "schema": "abyss_machine_self_awareness_requirements_v1",
            "sha256": "abc123",
            "artifact_status": "ready",
            "evidence_ref": {"kind": "latest"},
        }
    }


def test_empty_export_stack_handoff_is_satisfied_and_read_only() -> None:
    requirements, handoff = contracts.export_stack_handoff(
        {"ok": True, "summary": {"requirements": 0}, "requirements": [], "stack_handoff": []},
        {"ok": True, "status": "ready", "summary": {}, "probes": []},
        {},
        "2026-07-10T12:00:00+00:00",
        {},
        {},
        {},
        schema_prefix="abyss_machine",
        version="fixture",
        contract_port=_port(
            coverage_impact=lambda _requirement_id: {},
            coverage_impact_complete=lambda _impact: False,
        ),
    )

    assert requirements["schema"] == "abyss_machine_self_awareness_export_requirements_summary_v1"
    assert requirements["open_stack_ids"] == []
    assert requirements["policy"]["host_layer_mutates_stack"] is False
    assert handoff["schema"] == "abyss_machine_self_awareness_export_stack_handoff_v1"
    assert handoff["status"] == "satisfied"
    assert handoff["summary"]["open"] == 0
    assert handoff["policy"]["host_layer_mutates_stack"] is False
    assert handoff["policy"]["actions_executed"] is False


def test_open_requirement_builds_coverage_and_verifier_handoff() -> None:
    callback_calls: list[str] = []

    def coverage_impact(requirement_id: str) -> dict[str, Any]:
        callback_calls.append(requirement_id)
        return {
            "schema": "abyss_machine_self_awareness_stack_coverage_impact_v1",
            "requirement_id": requirement_id,
            "organ": "fixture-organ",
            "coverage_planes": ["trace", "replay"],
            "affected_stack_surfaces": ["fixture-stack"],
            "affected_machine_surfaces": ["fixture-machine"],
            "blocks_stack_usage_requirements": ["fixture-usage"],
            "closure_value": "fixture closure",
            "proof_commands": ["abyss-machine self-awareness validate --json"],
            "policy": {
                "host_layer_mutates_stack": False,
                "executes_commands": False,
                "raw_secrets_included": False,
            },
        }

    def coverage_impact_complete(impact: Any) -> bool:
        return (
            isinstance(impact, dict)
            and impact.get("schema") == "abyss_machine_self_awareness_stack_coverage_impact_v1"
            and impact.get("policy", {}).get("host_layer_mutates_stack") is False
        )

    requirements, handoff = contracts.export_stack_handoff(
        {
            "ok": True,
            "summary": {"requirements": 1, "stack_owned": 1},
            "requirements": [
                {
                    "id": "stack.fixture",
                    "title": "Fixture stack capability",
                    "owner": "abyss-stack",
                    "acceptance_contract": {
                        "schema": "abyss_machine_stack_requirement_acceptance_contract_v1",
                        "probe_plan": {
                            "kind": "read_only",
                            "candidate_routes": ["fixture"],
                            "required_fields": ["ready"],
                            "success_predicates": ["ready is true"],
                            "redaction_rules": ["no secrets"],
                            "boundedness": "one document",
                        },
                        "machine_verifiers": ["abyss-machine self-awareness validate --json"],
                    },
                }
            ],
            "stack_handoff": [{"id": "stack.fixture"}],
        },
        {
            "ok": True,
            "status": "open",
            "summary": {"internal_contract_failures": [], "secret_leaks": 0, "mutating_routes": 0},
            "probes": [
                {
                    "id": "stack.fixture",
                    "owner": "abyss-stack",
                    "status": "open",
                    "closed_by_current_probe": False,
                    "checks": [{"key": "ready", "level": "fail", "ok": False, "message": "not ready"}],
                    "acceptance_verifiers": ["abyss-machine self-awareness validate --json"],
                    "closure_readiness": {
                        "schema": "abyss_machine_stack_handoff_closure_readiness_v1",
                        "blocking_check_keys": ["ready"],
                        "missing_checks": ["ready"],
                        "closure_evidence_needed": ["ready evidence"],
                        "verifier_commands": ["abyss-machine self-awareness validate --json"],
                        "open_blocker_count": 1,
                    },
                    "current_state": {"ready": False, "private": "not exported"},
                    "evidence_refs": [{"kind": "fixture"}],
                }
            ],
        },
        {},
        "2026-07-10T12:00:00+00:00",
        {},
        {},
        {},
        schema_prefix="abyss_machine",
        version="fixture",
        contract_port=_port(
            coverage_impact=coverage_impact,
            coverage_impact_complete=coverage_impact_complete,
        ),
    )

    assert callback_calls == ["stack.fixture"]
    assert requirements["open_stack_ids"] == ["stack.fixture"]
    assert requirements["summary"]["stack_handoff_coverage_impact_entries"] == 1
    assert handoff["status"] == "open_requirements"
    assert handoff["blocked_coverage_planes"] == ["replay", "trace"]
    assert handoff["coverage_impacts_by_requirement"]["stack.fixture"]["organ"] == "fixture-organ"
    verifier = handoff["stack_owner_verifier_matrix_by_requirement"]["stack.fixture"]
    assert verifier["blocking_check_keys"] == ["ready"]
    assert verifier["policy"]["executes_commands"] is False
    entry = handoff["open_requirements"][0]
    assert entry["current_state_digest"]["keys"] == ["private", "ready"]
    assert entry["current_state_digest"]["policy"]["raw_payloads_included"] is False

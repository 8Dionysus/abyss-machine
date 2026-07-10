from __future__ import annotations

from pathlib import Path

from abyss_machine import self_awareness_completion_contracts as completion_contracts
from abyss_machine import self_awareness_completion_graph_contracts as graph_contracts


def _paths(tmp_path: Path) -> graph_contracts.CompletionEntityDocumentPaths:
    return graph_contracts.CompletionEntityDocumentPaths(
        requirements=tmp_path / "requirements/latest.json",
        requirement_probes=tmp_path / "requirement-probes/latest.json",
        stack_closure_dossier=tmp_path / "stack-closure-dossier/latest.json",
        working_stack=tmp_path / "working-stack/latest.json",
        activation_smoke=tmp_path / "activation-smoke/latest.json",
        collect=tmp_path / "collect/latest.json",
        events=tmp_path / "events/latest.json",
        timeline=tmp_path / "timeline/latest.json",
        spatial_graph=tmp_path / "spatial-graph/latest.json",
        context=tmp_path / "context/latest.json",
        coverage_audit=tmp_path / "coverage-audit/latest.json",
        autolink=tmp_path / "autolink/latest.json",
        completion_audit=tmp_path / "completion-audit/latest.json",
        cycle=tmp_path / "cycle/latest.json",
    )


def test_entity_event_document_map_covers_actions_body_and_bridge(tmp_path: Path) -> None:
    actions = [
        {
            "id": "stack-requirement:stack.trace-backend",
            "category": "stack_requirement",
            "requirement_id": "stack.trace-backend",
            "owner_route": "abyss-stack",
            "priority_rank": 1,
            "priority_class": "critical_trace_join",
            "coverage_planes": ["trace_join"],
            "closure_blocker_keys": ["trace_ready"],
            "evidence_refs": [{"path": "/fixture/requirements.json"}],
        },
        {
            "id": "working-stack:n8n",
            "category": "working_stack_usage_gap",
            "service": "n8n",
            "owner_route": "abyss-stack",
            "priority_rank": 2,
            "priority_class": "workflow_runtime_activation",
            "closure_blocker_keys": ["workflow_route"],
        },
        {
            "id": "custom:manual-review",
            "category": "custom_fixture",
            "owner_route": "abyss-stack",
            "priority_rank": 3,
            "priority_class": "custom_fixture",
            "closure_blocker_keys": ["manual_review"],
        },
    ]
    drilldowns = {
        "stack-requirement:stack.trace-backend": {
            "id": "drilldown-trace",
            "coverage": {"planes": ["trace_join"]},
            "acceptance": {"verifier_commands": ["validate-trace"]},
        },
        "working-stack:n8n": {
            "id": "drilldown-n8n",
            "coverage": {"planes": ["workflow"]},
            "next_step_packet": {"verifier_commands": ["validate-n8n"]},
        },
        "custom:manual-review": {
            "id": "drilldown-custom",
            "coverage": {"planes": ["manual"]},
            "next_step_packet": {"verifier_commands": ["review-custom"]},
        },
    }
    route_map = completion_contracts.completion_route_map(
        schema_prefix="abyss_machine",
        version="0.test",
        generated_at="2026-07-10T06:00:00-06:00",
        completion_actions=actions,
        drilldowns_by_action=drilldowns,
        resource_preflight={"ok": True},
    )
    working_stack = {
        "organs": [
            {
                "service": "n8n",
                "owner_surface": "abyss-stack",
                "machine_usage_status": "open_potential",
                "usage_gap": "workflow_call_unproven",
                "deep_usage_proven": False,
                "endpoint_ok": True,
                "runtime": {"container": "abyss-n8n"},
                "time_space_context_link": {"link_id": "link-n8n"},
                "evidence_refs": [{"path": "/fixture/working-stack.json"}],
            }
        ]
    }
    autolink = {
        "organ_links": [
            {
                "service": "n8n",
                "owner": "abyss-stack",
                "working_stack_link_id": "link-n8n",
                "event_id": "event-n8n",
                "automatic_link_state": "open_potential",
                "machine_usage_status": "open_potential",
                "usage_gap": "workflow_call_unproven",
                "time": {"observed_at": "2026-07-10T05:59:00-06:00"},
                "space": {"container": "abyss-n8n"},
                "context": {"surface": "workflow"},
                "episode_ids": ["episode-n8n"],
                "evidence_refs": [{"path": "/fixture/autolink.json"}],
            }
        ]
    }
    cycle = {
        "bridge_proof": {
            "generated_at": "2026-07-10T05:58:00-06:00",
            "rows": [
                {
                    "id": "heartbeats",
                    "organ": "heartbeat",
                    "ok": True,
                    "coverage": ["rhythm"],
                    "command": "heartbeat status",
                    "validator": "heartbeat validate",
                    "artifact": {
                        "path": str(tmp_path / "heartbeat/latest.json"),
                        "schema": "abyss_machine_heartbeat_v1",
                        "expected_schema": "abyss_machine_heartbeat_v1",
                        "ok": True,
                        "schema_ok": True,
                        "sha256": "sha256:fixture",
                        "machine_owned_path": True,
                    },
                }
            ],
        }
    }

    graph = graph_contracts.completion_entity_event_document_map(
        schema_prefix="abyss_machine",
        version="0.test",
        generated_at="2026-07-10T06:00:00-06:00",
        paths=_paths(tmp_path),
        completion_actions=actions,
        drilldowns_by_action=drilldowns,
        route_map=route_map,
        working_stack=working_stack,
        autolink=autolink,
        cycle=cycle,
    )

    assert graph["ok"] is True
    expected_summary = {
        "actions": 3,
        "entities": 5,
        "events": 5,
        "documents": 15,
        "routes": 5,
        "completion_action_entities": 3,
        "stack_organs": 1,
        "machine_bridges": 1,
        "body_surfaces": 2,
        "unmapped_actions": [],
        "unmapped_route_actions": [],
        "unmapped_stack_organs": [],
        "unmapped_machine_bridges": [],
        "automation_ready": True,
    }
    assert {
        key: graph["summary"][key]
        for key in expected_summary
    } == expected_summary
    assert graph["top_entity"]["entity_id"] == "stack.requirement.stack.trace-backend"
    assert graph["top_event"]["event_kind"] == "stack_requirement_open"
    assert graph["stack_organ_entities"][0]["entity_id"] == "stack.organ.n8n"
    assert graph["stack_organ_entities"][0]["event_id"] == "event-n8n"
    assert graph["machine_bridge_entities"][0]["entity_id"] == "machine.bridge.heartbeats"
    assert "machine.bridge.heartbeats.latest" in graph["machine_bridge_entities"][0]["document_ids"]
    assert [row["route_id"] for row in graph["routes"]] == [
        "observability.trace_join_backbone",
        "runtime.graph_workflow.routes",
        "completion.unassigned_open_actions",
        "body.stack_organs",
        "body.machine_bridges",
    ]
    assert all(row["policy"]["executes_commands"] is False for row in graph["entities"])
    assert all(row["policy"]["host_layer_mutates_stack"] is False for row in graph["events"])
    assert graph["automation"]["validation_contract"]["every_action_has_entity"] is True
    assert graph["automation"]["validation_contract"]["document_refs_resolve"] is True


def test_entity_event_document_map_preserves_empty_latest_state(tmp_path: Path) -> None:
    route_map = completion_contracts.completion_route_map(
        schema_prefix="abyss_machine",
        version="0.test",
        generated_at="2026-07-10T06:00:00-06:00",
        completion_actions=[],
        drilldowns_by_action={},
        resource_preflight={"ok": False},
    )

    graph = graph_contracts.completion_entity_event_document_map(
        schema_prefix="abyss_machine",
        version="0.test",
        generated_at="2026-07-10T06:00:00-06:00",
        paths=_paths(tmp_path),
        completion_actions=[],
        drilldowns_by_action={},
        route_map=route_map,
        working_stack={},
        autolink={},
        cycle={},
    )

    assert graph["ok"] is True
    assert graph["status"] == "ready"
    assert graph["summary"]["actions"] == 0
    assert graph["summary"]["entities"] == 0
    assert graph["summary"]["events"] == 0
    assert graph["summary"]["documents"] == 14
    assert graph["summary"]["routes"] == 2
    assert graph["top_entity"] == {}
    assert graph["top_event"] == {}
    assert graph["automation"]["runs_cycle"] is False
    assert graph["policy"]["host_layer_mutates_stack"] is False


def test_entity_event_document_map_recovers_stack_organ_from_autolink(tmp_path: Path) -> None:
    route_map = completion_contracts.completion_route_map(
        schema_prefix="abyss_machine",
        version="0.test",
        generated_at="2026-07-10T06:00:00-06:00",
        completion_actions=[],
        drilldowns_by_action={},
        resource_preflight={"ok": True},
    )
    autolink = {
        "organ_links": [
            {
                "service": "qdrant",
                "owner": "abyss-stack",
                "working_stack_link_id": "link-qdrant",
                "event_id": "event-qdrant",
                "automatic_link_state": "linked",
                "machine_usage_status": "active",
                "usage_gap": None,
                "evidence_refs": [{"path": "/fixture/autolink.json"}],
                "policy": {"host_layer_mutates_stack": False},
            }
        ]
    }

    graph = graph_contracts.completion_entity_event_document_map(
        schema_prefix="abyss_machine",
        version="0.test",
        generated_at="2026-07-10T06:00:00-06:00",
        paths=_paths(tmp_path),
        completion_actions=[],
        drilldowns_by_action={},
        route_map=route_map,
        working_stack={},
        autolink=autolink,
        cycle={},
    )

    assert graph["ok"] is True
    assert graph["summary"]["stack_organs"] == 1
    assert graph["summary"]["working_stack_organs"] == 1
    assert graph["summary"]["unmapped_stack_organs"] == []
    assert graph["stack_organ_entities"][0]["entity_id"] == "stack.organ.qdrant"
    assert graph["stack_organ_entities"][0]["event_id"] == "event-qdrant"
    assert graph["automation"]["validation_contract"]["every_stack_organ_has_entity"] is True


def test_entity_event_document_map_fails_closed_for_unresolved_bridge_document(tmp_path: Path) -> None:
    route_map = completion_contracts.completion_route_map(
        schema_prefix="abyss_machine",
        version="0.test",
        generated_at="2026-07-10T06:00:00-06:00",
        completion_actions=[],
        drilldowns_by_action={},
        resource_preflight={"ok": True},
    )

    graph = graph_contracts.completion_entity_event_document_map(
        schema_prefix="abyss_machine",
        version="0.test",
        generated_at="2026-07-10T06:00:00-06:00",
        paths=_paths(tmp_path),
        completion_actions=[],
        drilldowns_by_action={},
        route_map=route_map,
        working_stack={},
        autolink={},
        cycle={
            "bridge_proof": {
                "rows": [
                    {
                        "id": "heartbeats",
                        "organ": "heartbeat",
                        "ok": False,
                        "artifact": {},
                    }
                ]
            }
        },
    )

    assert graph["ok"] is False
    assert graph["status"] == "incomplete"
    assert graph["summary"]["documents"] == 14
    assert graph["summary"]["machine_bridges"] == 1
    assert graph["summary"]["unmapped_document_refs"] == ["entity.document_ids"]
    assert graph["machine_bridge_entities"][0]["entity_id"] == "machine.bridge.heartbeats"
    assert graph["automation"]["validation_contract"]["document_refs_resolve"] is False
    assert graph["policy"]["host_layer_mutates_stack"] is False

from __future__ import annotations

import pytest

from abyss_machine import self_awareness_completion_document_contracts as document_contracts


def _backlog() -> dict:
    actions = [
        {
            "id": "stack-requirement:stack.trace-backend",
            "category": "stack_requirement",
            "priority_class": "critical_trace_join",
            "owner_route": "abyss-stack",
            "policy": {
                "requires_human_approval": True,
                "executes_commands": False,
                "host_layer_mutates_stack": False,
            },
        }
    ]
    drilldowns = [
        {
            "id": "drilldown-trace",
            "action_id": "stack-requirement:stack.trace-backend",
            "complete": True,
            "policy": {
                "executes_commands": False,
                "host_layer_mutates_stack": False,
            },
        }
    ]
    return document_contracts.completion_action_backlog(
        schema_prefix="abyss_machine",
        version="0.test",
        generated_at="2026-07-10T07:00:00-06:00",
        completion_actions=actions,
        completion_drilldowns=drilldowns,
        drilldowns_by_action={"stack-requirement:stack.trace-backend": drilldowns[0]},
        route_map={
            "ok": True,
            "summary": {"routes": 1, "next_route_id": "observability.trace_join_backbone"},
        },
        route_packets={
            "ok": True,
            "summary": {
                "packets": 1,
                "packets_complete": 1,
                "covered_actions": 1,
                "automation_ready": True,
                "top_packet_id": "packet-trace",
            },
        },
        entity_event_document_map={"ok": True, "summary": {"entities": 1}},
    )


def _context(
    *,
    status_schema_ok: bool = True,
    gate_ok: bool = True,
    body_complete: bool = False,
    missing_artifacts: list[str] | None = None,
) -> document_contracts.CompletionAuditDocumentContext:
    return document_contracts.CompletionAuditDocumentContext(
        status_doc={
            "schema": (
                "abyss_machine_self_awareness_status_v1"
                if status_schema_ok
                else "abyss_machine_self_awareness_status_unknown_v1"
            ),
            "summary": {
                "body_status": "complete" if body_complete else "watch",
                "body_open_routes": 0 if body_complete else 1,
                "body_watch_sources": 0 if body_complete else 1,
            },
        },
        body_closure={
            "complete": body_complete,
            "status": "complete" if body_complete else "watch",
            "summary": {
                "response_routes": 0 if body_complete else 1,
                "watch_sources": 0 if body_complete else 1,
            },
        },
        open_requirement_doc={
            "rows": [{"id": "stack.trace-backend"}] if not gate_ok else [],
            "policy": {"host_layer_mutates_stack": False},
        },
        open_potential_doc={
            "rows": [{"service": "n8n"}] if not gate_ok else [],
            "policy": {"host_layer_mutates_stack": False},
        },
        coverage_audit={
            "summary": {"incomplete": 0 if gate_ok else 1},
            "rows": [
                {
                    "id": "coverage.trace",
                    "status": "complete" if gate_ok else "blocked",
                    "objective_area": "trace",
                    "open_stack_requirement_ids": [] if gate_ok else ["stack.trace-backend"],
                    "missing_artifacts": [],
                    "missing_chain_keys": [],
                    "coverage_planes": ["trace_join"],
                    "private_extra": "must-not-project",
                }
            ],
        },
        validate_green=True,
        cycle_green=True,
        coverage_green=True,
        completion_gates=[{"id": "closure", "ok": gate_ok}],
        blockers=[] if gate_ok else [{"id": "abyss-stack.requirements.open"}],
        action_backlog=_backlog(),
        route_map={
            "ok": True,
            "summary": {
                "routes": 1,
                "next_route_id": "observability.trace_join_backbone",
                "next_route_path": "observability/trace/join-backbone",
            },
        },
        route_packets={
            "ok": True,
            "summary": {
                "packets": 1,
                "packets_complete": 1,
                "covered_actions": 1,
                "automation_ready": True,
                "top_packet_id": "packet-trace",
            },
        },
        entity_event_document_map={
            "ok": True,
            "summary": {
                "entities": 3,
                "events": 3,
                "documents": 15,
                "stack_organs": 1,
                "machine_bridges": 1,
                "body_surfaces": 2,
                "automation_ready": True,
            },
        },
        status_open_stack_requirements=0 if gate_ok else 1,
        requirement_probes_open=0 if gate_ok else 1,
        coverage_blocked_stack_owned=0 if gate_ok else 1,
        working_stack_usage_gaps=0 if gate_ok else 1,
        activation_open_gaps=0 if gate_ok else 1,
        autolink_complete=gate_ok,
        resource_preflight={"ok": True},
        owner_boundary_ok=True,
        missing_artifacts=list(missing_artifacts or []),
        artifact_refs={"status": {"exists": True, "schema_ok": True}},
    )


def test_completion_action_backlog_aggregates_graph_without_execution() -> None:
    backlog = _backlog()

    assert backlog["ok"] is True
    assert backlog["status"] == "open"
    assert backlog["summary"] == {
        "actions": 1,
        "drilldowns": 1,
        "drilldowns_complete": 1,
        "stack_requirement_actions": 1,
        "working_stack_usage_gap_actions": 0,
        "requires_human_approval": 1,
        "executable_now": 0,
        "top_action_id": "stack-requirement:stack.trace-backend",
        "top_action_drilldown_id": "drilldown-trace",
        "top_action_drilldown_complete": True,
        "top_priority_class": "critical_trace_join",
        "top_owner_route": "abyss-stack",
        "route_packets": 1,
        "route_packets_complete": 1,
        "route_packet_actions": 1,
        "route_packet_automation_ready": True,
        "top_route_packet_id": "packet-trace",
    }
    assert backlog["top_action"]["id"] == "stack-requirement:stack.trace-backend"
    assert backlog["top_action_drilldown"]["id"] == "drilldown-trace"
    assert backlog["policy"]["executes_commands"] is False
    assert backlog["policy"]["host_layer_mutates_stack"] is False


@pytest.mark.parametrize(
    ("context_kwargs", "expected_status", "expected_ok"),
    [
        ({"status_schema_ok": False}, "degraded", False),
        ({"missing_artifacts": ["cycle"]}, "degraded", False),
        ({"gate_ok": False}, "incomplete", False),
        ({"gate_ok": True, "body_complete": False}, "watch", True),
        ({"gate_ok": True, "body_complete": True}, "complete", True),
    ],
)
def test_completion_audit_document_preserves_status_transitions(
    context_kwargs: dict,
    expected_status: str,
    expected_ok: bool,
) -> None:
    document = document_contracts.completion_audit_document(
        schema_prefix="abyss_machine",
        version="0.test",
        generated_at="2026-07-10T07:00:00-06:00",
        context=_context(**context_kwargs),
    )

    assert document["status"] == expected_status
    assert document["ok"] is expected_ok
    assert document["summary"]["stack_usage_status"] == (
        "unknown" if expected_status == "degraded" else "incomplete" if expected_status == "incomplete" else "complete"
    )
    assert document["policy"]["host_layer_mutates_stack"] is False
    assert document["source_commands"]["runs_probe"] is False
    assert document["source_commands"]["runs_cycle"] is False


def test_completion_audit_document_keeps_stack_completion_distinct_from_body_closure() -> None:
    document = document_contracts.completion_audit_document(
        schema_prefix="abyss_machine",
        version="0.test",
        generated_at="2026-07-10T07:00:00-06:00",
        context=_context(gate_ok=True, body_complete=False),
    )

    assert document["ok"] is True
    assert document["status"] == "watch"
    assert document["summary"]["stack_usage_closure_complete"] is True
    assert document["summary"]["body_closure_complete"] is False
    assert document["summary"]["stack_usage_complete_but_body_watch"] is True
    assert document["summary"]["validator_green_but_stack_usage_incomplete"] is False
    assert document["summary"]["completion_route_packet_automation_ready"] is True
    assert document["summary"]["entity_event_document_automation_ready"] is True
    assert "private_extra" not in document["coverage_matrix"]["rows"][0]
    assert document["coverage_matrix"]["rows"][0]["coverage_planes"] == ["trace_join"]
    assert document["policy"]["stack_usage_completion_is_not_body_closure"] is True

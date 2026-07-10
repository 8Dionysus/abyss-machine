from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from . import self_awareness_contracts


@dataclass(frozen=True)
class CompletionAuditDocumentContext:
    status_doc: Mapping[str, Any]
    body_closure: Mapping[str, Any]
    open_requirement_doc: Mapping[str, Any]
    open_potential_doc: Mapping[str, Any]
    coverage_audit: Mapping[str, Any]
    validate_green: bool
    cycle_green: bool
    coverage_green: bool
    completion_gates: list[dict[str, Any]]
    blockers: list[dict[str, Any]]
    action_backlog: Mapping[str, Any]
    route_map: Mapping[str, Any]
    route_packets: Mapping[str, Any]
    entity_event_document_map: Mapping[str, Any]
    status_open_stack_requirements: int
    requirement_probes_open: int
    coverage_blocked_stack_owned: int
    working_stack_usage_gaps: int
    activation_open_gaps: int
    autolink_complete: bool
    resource_preflight: Mapping[str, Any]
    owner_boundary_ok: bool
    missing_artifacts: list[str]
    artifact_refs: Mapping[str, dict[str, Any]]


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def completion_action_backlog(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    completion_actions: list[dict[str, Any]],
    completion_drilldowns: list[dict[str, Any]],
    drilldowns_by_action: Mapping[str, dict[str, Any]],
    route_map: Mapping[str, Any],
    route_packets: Mapping[str, Any],
    entity_event_document_map: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_self_awareness_completion_action_backlog_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": (
            all(self_awareness_contracts.nested_get(action, ["policy", "host_layer_mutates_stack"]) is False and self_awareness_contracts.nested_get(action, ["policy", "executes_commands"]) is False for action in completion_actions)
            and all(self_awareness_contracts.nested_get(drilldown, ["policy", "host_layer_mutates_stack"]) is False and self_awareness_contracts.nested_get(drilldown, ["policy", "executes_commands"]) is False for drilldown in completion_drilldowns)
            and (not completion_drilldowns or completion_drilldowns[0].get("complete") is True)
            and route_map.get("ok") is True
            and entity_event_document_map.get("ok") is True
            and route_packets.get("ok") is True
        ),
        "status": "open" if completion_actions else "empty",
        "summary": {
            "actions": len(completion_actions),
            "drilldowns": len(completion_drilldowns),
            "drilldowns_complete": sum(1 for drilldown in completion_drilldowns if drilldown.get("complete") is True),
            "stack_requirement_actions": sum(1 for action in completion_actions if action.get("category") == "stack_requirement"),
            "working_stack_usage_gap_actions": sum(1 for action in completion_actions if action.get("category") == "working_stack_usage_gap"),
            "requires_human_approval": sum(1 for action in completion_actions if self_awareness_contracts.nested_get(action, ["policy", "requires_human_approval"]) is True),
            "executable_now": 0,
            "top_action_id": completion_actions[0].get("id") if completion_actions else None,
            "top_action_drilldown_id": completion_drilldowns[0].get("id") if completion_drilldowns else None,
            "top_action_drilldown_complete": completion_drilldowns[0].get("complete") if completion_drilldowns else None,
            "top_priority_class": completion_actions[0].get("priority_class") if completion_actions else None,
            "top_owner_route": completion_actions[0].get("owner_route") if completion_actions else None,
            "route_packets": self_awareness_contracts.nested_get(route_packets, ["summary", "packets"]),
            "route_packets_complete": self_awareness_contracts.nested_get(route_packets, ["summary", "packets_complete"]),
            "route_packet_actions": self_awareness_contracts.nested_get(route_packets, ["summary", "covered_actions"]),
            "route_packet_automation_ready": self_awareness_contracts.nested_get(route_packets, ["summary", "automation_ready"]),
            "top_route_packet_id": self_awareness_contracts.nested_get(route_packets, ["summary", "top_packet_id"]),
        },
        "top_action": completion_actions[0] if completion_actions else {},
        "top_action_drilldown": completion_drilldowns[0] if completion_drilldowns else {},
        "actions": completion_actions,
        "drilldowns": completion_drilldowns,
        "drilldowns_by_action": drilldowns_by_action,
        "completion_route_map": route_map,
        "completion_route_packets": route_packets,
        "entity_event_document_map": entity_event_document_map,
        "source_commands": [
            "abyss-machine self-awareness completion-audit --json",
            "abyss-machine self-awareness export --json",
            "abyss-machine self-awareness requirement-probes --json",
            "abyss-machine self-awareness working-stack --json",
            "abyss-machine self-awareness activation-smoke --json",
        ],
        "policy": {
            "handoff_only": True,
            "automatic": False,
            "requires_human_approval": True,
            "executes_commands": False,
            "host_layer_mutates_stack": False,
            "actions_executed": False,
        },
    }


def completion_audit_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    context: CompletionAuditDocumentContext,
) -> dict[str, Any]:
    status_doc = context.status_doc
    status_summary = status_doc.get("summary") if isinstance(status_doc.get("summary"), dict) else {}
    body_closure = context.body_closure
    body_closure_summary = (
        body_closure.get("summary") if isinstance(body_closure.get("summary"), dict) else {}
    )
    open_requirement_doc = context.open_requirement_doc
    open_requirement_rows = (
        open_requirement_doc.get("rows")
        if isinstance(open_requirement_doc.get("rows"), list)
        else []
    )
    open_potential_doc = context.open_potential_doc
    open_potential_rows = (
        open_potential_doc.get("rows")
        if isinstance(open_potential_doc.get("rows"), list)
        else []
    )
    coverage_audit = context.coverage_audit
    coverage_summary = (
        coverage_audit.get("summary") if isinstance(coverage_audit.get("summary"), dict) else {}
    )
    coverage_rows = (
        coverage_audit.get("rows") if isinstance(coverage_audit.get("rows"), list) else []
    )
    validate_green = context.validate_green
    cycle_green = context.cycle_green
    coverage_green = context.coverage_green
    completion_gates = context.completion_gates
    blockers = context.blockers
    completion_action_backlog = context.action_backlog
    completion_actions = (
        completion_action_backlog.get("actions")
        if isinstance(completion_action_backlog.get("actions"), list)
        else []
    )
    route_map = context.route_map
    route_packets = context.route_packets
    entity_event_document_map = context.entity_event_document_map
    status_open_stack_requirements = context.status_open_stack_requirements
    requirement_probes_open = context.requirement_probes_open
    coverage_blocked_stack_owned = context.coverage_blocked_stack_owned
    working_stack_usage_gaps = context.working_stack_usage_gaps
    activation_open_gaps = context.activation_open_gaps
    autolink_complete = context.autolink_complete
    resource_preflight = context.resource_preflight
    owner_boundary_ok = context.owner_boundary_ok
    missing_artifacts = context.missing_artifacts
    artifact_refs = context.artifact_refs

    compact_coverage_rows = [
        {
            "id": row.get("id"),
            "status": row.get("status"),
            "objective_area": row.get("objective_area"),
            "open_stack_requirement_ids": row.get("open_stack_requirement_ids") if isinstance(row.get("open_stack_requirement_ids"), list) else [],
            "missing_artifacts": row.get("missing_artifacts") if isinstance(row.get("missing_artifacts"), list) else [],
            "missing_chain_keys": row.get("missing_chain_keys") if isinstance(row.get("missing_chain_keys"), list) else [],
            "coverage_planes": row.get("coverage_planes") if isinstance(row.get("coverage_planes"), list) else [],
        }
        for row in coverage_rows
        if isinstance(row, dict)
    ]
    audit_ok = status_doc.get("schema") == f"{schema_prefix}_self_awareness_status_v1" and not missing_artifacts
    stack_usage_closure_complete = audit_ok and all(bool(row.get("ok")) for row in completion_gates)
    body_closure_complete = body_closure.get("complete") is True
    body_status = str(body_closure.get("status") or status_summary.get("body_status") or "unknown")
    body_open_routes = _safe_int(body_closure_summary.get("response_routes"), _safe_int(status_summary.get("body_open_routes"), 0))
    body_watch_sources = _safe_int(body_closure_summary.get("watch_sources"), _safe_int(status_summary.get("body_watch_sources"), 0))
    stack_usage_status = "complete" if stack_usage_closure_complete else ("incomplete" if audit_ok else "unknown")
    if not audit_ok:
        audit_status = "degraded"
    elif not stack_usage_closure_complete:
        audit_status = "incomplete"
    elif body_closure_complete:
        audit_status = "complete"
    else:
        audit_status = "watch"
    validator_green_but_stack_usage_incomplete = validate_green and cycle_green and coverage_green and not stack_usage_closure_complete
    stack_usage_complete_but_body_watch = stack_usage_closure_complete and not body_closure_complete
    return {
        "schema": f"{schema_prefix}_self_awareness_completion_audit_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": stack_usage_closure_complete,
        "status": audit_status,
        "summary": {
            "audit_ok": audit_ok,
            "stack_usage_status": stack_usage_status,
            "stack_usage_closure_complete": stack_usage_closure_complete,
            "body_status": body_status,
            "body_closure_complete": body_closure_complete,
            "body_open_routes": body_open_routes,
            "body_watch_sources": body_watch_sources,
            "stack_usage_complete_but_body_watch": stack_usage_complete_but_body_watch,
            "validator_green": validate_green,
            "cycle_green": cycle_green,
            "coverage_green": coverage_green,
            "validator_green_but_stack_usage_incomplete": validator_green_but_stack_usage_incomplete,
            "gates": len(completion_gates),
            "gates_ok": sum(1 for row in completion_gates if row.get("ok")),
            "blockers": len(blockers),
            "completion_actions": len(completion_actions),
            "completion_routes": self_awareness_contracts.nested_get(route_map, ["summary", "routes"]),
            "next_completion_route_id": self_awareness_contracts.nested_get(route_map, ["summary", "next_route_id"]),
            "next_completion_route_path": self_awareness_contracts.nested_get(route_map, ["summary", "next_route_path"]),
            "completion_route_packets": self_awareness_contracts.nested_get(route_packets, ["summary", "packets"]),
            "completion_route_packets_complete": self_awareness_contracts.nested_get(route_packets, ["summary", "packets_complete"]),
            "completion_route_packet_actions": self_awareness_contracts.nested_get(route_packets, ["summary", "covered_actions"]),
            "completion_route_packet_automation_ready": self_awareness_contracts.nested_get(route_packets, ["summary", "automation_ready"]),
            "top_completion_route_packet_id": self_awareness_contracts.nested_get(route_packets, ["summary", "top_packet_id"]),
            "entity_event_document_entities": self_awareness_contracts.nested_get(entity_event_document_map, ["summary", "entities"]),
            "entity_event_document_events": self_awareness_contracts.nested_get(entity_event_document_map, ["summary", "events"]),
            "entity_event_document_documents": self_awareness_contracts.nested_get(entity_event_document_map, ["summary", "documents"]),
            "entity_event_document_stack_organs": self_awareness_contracts.nested_get(entity_event_document_map, ["summary", "stack_organs"]),
            "entity_event_document_machine_bridges": self_awareness_contracts.nested_get(entity_event_document_map, ["summary", "machine_bridges"]),
            "entity_event_document_body_surfaces": self_awareness_contracts.nested_get(entity_event_document_map, ["summary", "body_surfaces"]),
            "entity_event_document_automation_ready": self_awareness_contracts.nested_get(entity_event_document_map, ["summary", "automation_ready"]),
            "top_completion_action_id": completion_action_backlog["summary"]["top_action_id"],
            "top_completion_priority_class": completion_action_backlog["summary"]["top_priority_class"],
            "open_stack_requirements": max(len(open_requirement_rows), status_open_stack_requirements, requirement_probes_open, coverage_blocked_stack_owned),
            "working_stack_usage_gaps": max(len(open_potential_rows), working_stack_usage_gaps, activation_open_gaps),
            "automatic_time_space_context_links_complete": autolink_complete,
            "resource_guard_ok": bool(resource_preflight.get("ok")),
            "owner_boundary_readonly": owner_boundary_ok,
            "missing_artifacts": missing_artifacts,
        },
        "completion_gates": completion_gates,
        "blockers": blockers,
        "action_backlog": completion_action_backlog,
        "completion_route_map": route_map,
        "completion_route_packets": route_packets,
        "entity_event_document_map": entity_event_document_map,
        "body_closure": body_closure,
        "open_stack_requirements": {
            "schema": f"{schema_prefix}_self_awareness_completion_open_stack_requirements_v1",
            "rows": open_requirement_rows,
            "policy": open_requirement_doc.get("policy") if isinstance(open_requirement_doc.get("policy"), dict) else {},
        },
        "open_potential": {
            "schema": f"{schema_prefix}_self_awareness_completion_open_potential_v1",
            "rows": open_potential_rows,
            "policy": open_potential_doc.get("policy") if isinstance(open_potential_doc.get("policy"), dict) else {},
        },
        "coverage_matrix": {
            "schema": f"{schema_prefix}_self_awareness_completion_coverage_matrix_v1",
            "summary": coverage_summary,
            "rows": compact_coverage_rows,
        },
        "resource_preflight": resource_preflight,
        "artifact_refs": artifact_refs,
        "source_commands": {
            "status": "abyss-machine self-awareness status --json",
            "completion_audit": "abyss-machine self-awareness completion-audit --json",
            "latest_only": True,
            "runs_probe": False,
            "runs_cycle": False,
            "runs_stack_http_probes": False,
            "runs_indexing": False,
            "next_heavy_proof_when_safe": "abyss-machine self-awareness cycle --json",
        },
        "policy": {
            "read_only_stack_consumer": True,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "automatic_remediation": False,
            "raw_evidence_is_not_truth": True,
            "validator_green_is_not_stack_usage_closure": True,
            "stack_usage_completion_is_not_body_closure": True,
            "open_stack_requirements_are_blockers_not_host_failures": True,
            "working_stack_usage_gaps_are_open_potential_not_host_failures": True,
        },
    }

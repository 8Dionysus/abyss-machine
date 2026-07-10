from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from . import self_awareness_completion_contracts
from . import self_awareness_contracts


@dataclass(frozen=True)
class CompletionEntityDocumentPaths:
    requirements: Path
    requirement_probes: Path
    stack_closure_dossier: Path
    working_stack: Path
    activation_smoke: Path
    collect: Path
    events: Path
    timeline: Path
    spatial_graph: Path
    context: Path
    coverage_audit: Path
    autolink: Path
    completion_audit: Path
    cycle: Path


def completion_entity_event_document_map(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    paths: CompletionEntityDocumentPaths,
    completion_actions: list[dict[str, Any]],
    drilldowns_by_action: Mapping[str, dict[str, Any]],
    route_map: Mapping[str, Any],
    working_stack: Mapping[str, Any],
    autolink: Mapping[str, Any],
    cycle: Mapping[str, Any],
) -> dict[str, Any]:
    def stable_path_segment(value: Any) -> str:
        raw = str(value or "unknown").strip()
        compact = re.sub(r"[^A-Za-z0-9._-]+", "-", raw)
        return compact.strip("-") or "unknown"

    document_specs = [
        (
            "self-awareness.requirements.latest",
            "self-awareness/requirements/latest",
            "stack_requirement_handoff",
            paths.requirements,
            "stack-owned requirement source and acceptance shape",
        ),
        (
            "self-awareness.requirement-probes.latest",
            "self-awareness/requirement-probes/latest",
            "stack_requirement_probe",
            paths.requirement_probes,
            "bounded read-only probe over stack-owned acceptance contract",
        ),
        (
            "self-awareness.stack-closure-dossier.latest",
            "self-awareness/stack-closure-dossier/latest",
            "stack_owner_closure_packet",
            paths.stack_closure_dossier,
            "ordered handoff packet and closure acceptance contract",
        ),
        (
            "self-awareness.working-stack.latest",
            "self-awareness/working-stack/latest",
            "working_stack_body_inventory",
            paths.working_stack,
            "actual running/deployed stack body and usage gaps",
        ),
        (
            "self-awareness.activation-smoke.latest",
            "self-awareness/activation-smoke/latest",
            "working_stack_activation_smoke",
            paths.activation_smoke,
            "per-service functional smoke and replayability proof",
        ),
        (
            "self-awareness.collect.latest",
            "self-awareness/collect/latest",
            "signal_fabric_collect",
            paths.collect,
            "latest normalized signal-fabric collection",
        ),
        (
            "self-awareness.events.latest",
            "self-awareness/events/latest",
            "signal_fabric_events",
            paths.events,
            "normalized event fabric with actor, entity, time, space, context, and evidence route",
        ),
        (
            "self-awareness.timeline.latest",
            "self-awareness/timeline/latest",
            "temporal_readmodel",
            paths.timeline,
            "temporal ordering for stack organs, machine bridges, and synthetic events",
        ),
        (
            "self-awareness.spatial-graph.latest",
            "self-awareness/spatial-graph/latest",
            "spatial_readmodel",
            paths.spatial_graph,
            "spatial graph overlay for services, links, memory space, and owner surfaces",
        ),
        (
            "self-awareness.context.latest",
            "self-awareness/context/latest",
            "context_readmodel",
            paths.context,
            "bounded context index and resident/operator context packet",
        ),
        (
            "self-awareness.coverage-audit.latest",
            "self-awareness/coverage-audit/latest",
            "coverage_matrix",
            paths.coverage_audit,
            "coverage planes, blockers, and time-space-context integrity",
        ),
        (
            "self-awareness.autolink.latest",
            "self-awareness/autolink/latest",
            "automatic_time_space_context_links",
            paths.autolink,
            "automatic temporal, spatial, contextual, and state-delta links",
        ),
        (
            "self-awareness.completion-audit.latest",
            "self-awareness/completion-audit/latest",
            "completion_gate",
            paths.completion_audit,
            "stack-usage-closure gate and entity-event-document map container",
        ),
        (
            "self-awareness.cycle.latest",
            "self-awareness/cycle/latest",
            "cycle_bridge_proof",
            paths.cycle,
            "latest from-zero cycle, body lineage, and machine bridge proof",
        ),
    ]
    documents = [
        {
            "schema": f"{schema_prefix}_self_awareness_entity_event_document_document_v1",
            "document_id": document_id,
            "document_path": document_path,
            "role": role,
            "path": str(path),
            "owner_route": "abyss-machine",
            "source_kind": "latest_readmodel",
            "truth_level": truth_level,
            "policy": {
                "read_only_stack_consumer": True,
                "host_layer_mutates_stack": False,
                "writes_project_roots": False,
                "executes_commands": False,
            },
        }
        for document_id, document_path, role, path, truth_level in document_specs
    ]
    bridge_rows = self_awareness_contracts.nested_get(cycle, ["bridge_proof", "rows"])
    bridge_rows = bridge_rows if isinstance(bridge_rows, list) else []
    for bridge_row in bridge_rows:
        if not isinstance(bridge_row, dict):
            continue
        bridge_id = stable_path_segment(bridge_row.get("id") or bridge_row.get("organ"))
        artifact = bridge_row.get("artifact") if isinstance(bridge_row.get("artifact"), dict) else {}
        artifact_path = artifact.get("path")
        if not artifact_path:
            continue
        documents.append({
            "schema": f"{schema_prefix}_self_awareness_entity_event_document_document_v1",
            "document_id": f"machine.bridge.{bridge_id}.latest",
            "document_path": f"machine/bridge/{bridge_id}/latest",
            "role": "machine_bridge_artifact",
            "path": str(artifact_path),
            "owner_route": "abyss-machine",
            "source_kind": "latest_readmodel",
            "truth_level": "machine bridge proof artifact",
            "bridge_id": bridge_id,
            "expected_schema": artifact.get("expected_schema") or artifact.get("schema"),
            "sha256": artifact.get("sha256"),
            "policy": {
                "read_only_stack_consumer": True,
                "host_layer_mutates_stack": False,
                "writes_project_roots": False,
                "executes_commands": False,
            },
        })
    documents_by_id = {str(row.get("document_id")): row for row in documents}
    routes = route_map.get("routes") if isinstance(route_map.get("routes"), list) else []
    route_by_action_id: dict[str, dict[str, Any]] = {}
    for route_row in routes:
        if not isinstance(route_row, dict):
            continue
        for action_id in route_row.get("actions") if isinstance(route_row.get("actions"), list) else []:
            route_by_action_id[str(action_id)] = route_row

    entities: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    entity_by_action_id: dict[str, dict[str, Any]] = {}
    for action in completion_actions:
        if not isinstance(action, dict) or not action.get("id"):
            continue
        action_id = str(action.get("id"))
        category = str(action.get("category") or "unknown")
        route_row = route_by_action_id.get(action_id, {})
        drilldown = drilldowns_by_action.get(action_id, {})
        if category == "stack_requirement":
            subject = stable_path_segment(action.get("requirement_id") or action_id)
            entity_id = f"stack.requirement.{subject}"
            entity_path = f"stack/requirement/{subject}"
            entity_kind = "stack_requirement"
            event_kind = "stack_requirement_open"
            event_path = f"completion/open/stack-requirement/{subject}"
            source_document_ids = [
                "self-awareness.requirements.latest",
                "self-awareness.requirement-probes.latest",
                "self-awareness.stack-closure-dossier.latest",
                "self-awareness.coverage-audit.latest",
                "self-awareness.autolink.latest",
                "self-awareness.completion-audit.latest",
            ]
            subject_ref = {"requirement_id": action.get("requirement_id")}
        elif category == "working_stack_usage_gap":
            subject = stable_path_segment(action.get("service") or action_id)
            entity_id = f"stack.service.{subject}"
            entity_path = f"stack/service/{subject}"
            entity_kind = "stack_service"
            event_kind = "working_stack_usage_gap_open"
            event_path = f"completion/open/working-stack/{subject}"
            source_document_ids = [
                "self-awareness.working-stack.latest",
                "self-awareness.activation-smoke.latest",
                "self-awareness.coverage-audit.latest",
                "self-awareness.autolink.latest",
                "self-awareness.completion-audit.latest",
            ]
            subject_ref = {"service": action.get("service")}
        else:
            subject = stable_path_segment(action_id)
            entity_id = f"completion.action.{subject}"
            entity_path = f"completion/action/{subject}"
            entity_kind = "completion_action"
            event_kind = "completion_action_open"
            event_path = f"completion/open/action/{subject}"
            source_document_ids = [
                "self-awareness.coverage-audit.latest",
                "self-awareness.completion-audit.latest",
            ]
            subject_ref = {"action_id": action_id}

        event_id = "completion.open." + self_awareness_contracts.stable_hash_json(
            {"action_id": action_id, "entity_id": entity_id, "event_kind": event_kind},
            length=18,
        )
        coverage_planes = action.get("coverage_planes") if isinstance(action.get("coverage_planes"), list) else self_awareness_contracts.nested_get(drilldown, ["coverage", "planes"]) if isinstance(self_awareness_contracts.nested_get(drilldown, ["coverage", "planes"]), list) else []
        blocker_keys = action.get("closure_blocker_keys") if isinstance(action.get("closure_blocker_keys"), list) else self_awareness_contracts.nested_get(drilldown, ["checks", "closure_blocker_keys"]) if isinstance(self_awareness_contracts.nested_get(drilldown, ["checks", "closure_blocker_keys"]), list) else []
        evidence_refs = action.get("evidence_refs") if isinstance(action.get("evidence_refs"), list) else []
        entity = {
            "schema": f"{schema_prefix}_self_awareness_entity_event_document_entity_v1",
            "entity_id": entity_id,
            "entity_path": entity_path,
            "entity_parts": [part for part in entity_path.split("/") if part],
            "entity_kind": entity_kind,
            "status": "open",
            "owner_route": action.get("owner_route") or "abyss-stack",
            "action_id": action_id,
            "event_id": event_id,
            "route_id": route_row.get("route_id"),
            "route_path": route_row.get("route_path"),
            "priority_rank": action.get("priority_rank"),
            "priority_class": action.get("priority_class"),
            "subject": subject_ref,
            "document_ids": source_document_ids,
            "coverage_planes": coverage_planes,
            "closure_blocker_keys": blocker_keys,
            "drilldown_id": drilldown.get("id"),
            "evidence_refs": evidence_refs,
            "safe_next_action": action.get("safe_next_action") if isinstance(action.get("safe_next_action"), dict) else {},
            "policy": {
                "handoff_only": True,
                "requires_human_approval": True,
                "read_only": True,
                "executes_commands": False,
                "host_layer_mutates_stack": False,
                "writes_project_roots": False,
                "automatic_remediation": False,
                "actions_executed": False,
            },
        }
        event = {
            "schema": f"{schema_prefix}_self_awareness_entity_event_document_event_v1",
            "event_id": event_id,
            "event_path": event_path,
            "event_parts": [part for part in event_path.split("/") if part],
            "event_kind": event_kind,
            "source": "completion-audit",
            "action_id": action_id,
            "entity_id": entity_id,
            "route_id": route_row.get("route_id"),
            "route_path": route_row.get("route_path"),
            "document_ids": source_document_ids,
            "evidence_refs": evidence_refs,
            "observed_at": generated_at,
            "truth_level": "latest_readmodel_open_state",
            "policy": {
                "handoff_only": True,
                "read_only": True,
                "executes_commands": False,
                "host_layer_mutates_stack": False,
                "writes_project_roots": False,
                "automatic_remediation": False,
                "actions_executed": False,
            },
        }
        entities.append(entity)
        events.append(event)
        entity_by_action_id[action_id] = entity

    autolink_organ_links = autolink.get("organ_links") if isinstance(autolink.get("organ_links"), list) else []
    working_stack_organs = working_stack.get("organs") if isinstance(working_stack.get("organs"), list) else []
    if not working_stack_organs:
        working_stack_organs = [
            {
                "service": link.get("service"),
                "owner_surface": link.get("owner"),
                "machine_usage_status": link.get("machine_usage_status"),
                "usage_gap": link.get("usage_gap"),
                "time_space_context_link": {"link_id": link.get("working_stack_link_id")},
                "evidence_refs": link.get("evidence_refs") if isinstance(link.get("evidence_refs"), list) else [],
                "policy": link.get("policy") if isinstance(link.get("policy"), dict) else {},
            }
            for link in autolink_organ_links
            if isinstance(link, dict) and link.get("service")
        ]
    stack_organ_entities = []
    for organ in working_stack_organs:
        if not isinstance(organ, dict) or not organ.get("service"):
            continue
        service = stable_path_segment(organ.get("service"))
        link = self_awareness_completion_contracts.first_matching_row(autolink_organ_links, ("service", str(organ.get("service") or "")))
        link_id = self_awareness_contracts.nested_get(organ, ["time_space_context_link", "link_id"]) or link.get("working_stack_link_id")
        event_id = str(link.get("event_id") or "body.stack_organ." + self_awareness_contracts.stable_hash_json({"service": service, "link_id": link_id}, length=18))
        source_document_ids = [
            "self-awareness.working-stack.latest",
            "self-awareness.collect.latest",
            "self-awareness.events.latest",
            "self-awareness.timeline.latest",
            "self-awareness.spatial-graph.latest",
            "self-awareness.context.latest",
            "self-awareness.autolink.latest",
            "self-awareness.completion-audit.latest",
        ]
        if organ.get("usage_gap") or link.get("usage_gap"):
            source_document_ids.append("self-awareness.activation-smoke.latest")
        evidence_refs = (
            link.get("evidence_refs")
            if isinstance(link.get("evidence_refs"), list) and link.get("evidence_refs")
            else organ.get("evidence_refs")
            if isinstance(organ.get("evidence_refs"), list)
            else [{"path": str(paths.working_stack), "service": organ.get("service")}]
        )
        entity = {
            "schema": f"{schema_prefix}_self_awareness_entity_event_document_entity_v1",
            "entity_id": f"stack.organ.{service}",
            "entity_path": f"stack/organ/{service}",
            "entity_parts": ["stack", "organ", service],
            "entity_kind": "stack_organ",
            "status": link.get("automatic_link_state") or ("open_potential" if organ.get("usage_gap") else "active"),
            "owner_route": organ.get("owner_surface") or link.get("owner") or "abyss-stack",
            "event_id": event_id,
            "route_id": "body.stack_organs",
            "route_path": "body/stack-organs",
            "subject": {
                "service": organ.get("service"),
                "working_stack_link_id": link_id,
                "container": self_awareness_contracts.nested_get(organ, ["runtime", "container"]),
            },
            "document_ids": source_document_ids,
            "machine_usage_status": organ.get("machine_usage_status") or link.get("machine_usage_status"),
            "usage_gap": organ.get("usage_gap") or link.get("usage_gap"),
            "deep_usage_proven": organ.get("deep_usage_proven"),
            "endpoint_ok": organ.get("endpoint_ok"),
            "time": link.get("time") if isinstance(link.get("time"), dict) else self_awareness_contracts.nested_get(organ, ["time_space_context_link", "time"]) or {},
            "space": link.get("space") if isinstance(link.get("space"), dict) else self_awareness_contracts.nested_get(organ, ["time_space_context_link", "space"]) or {},
            "context": link.get("context") if isinstance(link.get("context"), dict) else self_awareness_contracts.nested_get(organ, ["time_space_context_link", "context"]) or {},
            "episode_ids": link.get("episode_ids") if isinstance(link.get("episode_ids"), list) else [],
            "current_state_digest": link.get("current_state_digest"),
            "evidence_refs": evidence_refs,
            "stack_source_refs": organ.get("stack_source_refs") if isinstance(organ.get("stack_source_refs"), list) else [],
            "policy": {
                "handoff_only": bool(organ.get("usage_gap") or link.get("usage_gap")),
                "requires_human_approval": bool(organ.get("usage_gap") or link.get("usage_gap")),
                "read_only": True,
                "executes_commands": False,
                "host_layer_mutates_stack": False,
                "writes_project_roots": False,
                "automatic_remediation": False,
                "actions_executed": False,
                "raw_evidence_is_not_truth": True,
            },
        }
        event = {
            "schema": f"{schema_prefix}_self_awareness_entity_event_document_event_v1",
            "event_id": event_id,
            "event_path": f"body/stack-organ/{service}/{entity['status']}",
            "event_parts": ["body", "stack-organ", service, str(entity["status"])],
            "event_kind": "stack_organ_linked",
            "source": "working-stack",
            "entity_id": entity["entity_id"],
            "route_id": "body.stack_organs",
            "route_path": "body/stack-organs",
            "document_ids": source_document_ids,
            "evidence_refs": evidence_refs,
            "observed_at": self_awareness_contracts.nested_get(entity, ["time", "observed_at"]) or generated_at,
            "truth_level": "latest_readmodel_body_state",
            "policy": {
                "handoff_only": bool(organ.get("usage_gap") or link.get("usage_gap")),
                "read_only": True,
                "executes_commands": False,
                "host_layer_mutates_stack": False,
                "writes_project_roots": False,
                "automatic_remediation": False,
                "actions_executed": False,
            },
        }
        entities.append(entity)
        events.append(event)
        stack_organ_entities.append(entity)

    machine_bridge_entities = []
    for bridge_row in bridge_rows:
        if not isinstance(bridge_row, dict) or not (bridge_row.get("id") or bridge_row.get("organ")):
            continue
        bridge_id = stable_path_segment(bridge_row.get("id") or bridge_row.get("organ"))
        artifact = bridge_row.get("artifact") if isinstance(bridge_row.get("artifact"), dict) else {}
        bridge_document_id = f"machine.bridge.{bridge_id}.latest"
        source_document_ids = ["self-awareness.cycle.latest", bridge_document_id]
        coverage = bridge_row.get("coverage") if isinstance(bridge_row.get("coverage"), list) else []
        bridge_status = "ok" if bridge_row.get("ok") is True and artifact.get("ok") is not False else "degraded"
        event_id = "body.machine_bridge." + self_awareness_contracts.stable_hash_json(
            {"bridge_id": bridge_id, "artifact": artifact.get("path"), "status": bridge_status},
            length=18,
        )
        evidence_refs = bridge_row.get("evidence_refs") if isinstance(bridge_row.get("evidence_refs"), list) else []
        entity = {
            "schema": f"{schema_prefix}_self_awareness_entity_event_document_entity_v1",
            "entity_id": f"machine.bridge.{bridge_id}",
            "entity_path": f"machine/bridge/{bridge_id}",
            "entity_parts": ["machine", "bridge", bridge_id],
            "entity_kind": "machine_bridge",
            "status": bridge_status,
            "owner_route": "abyss-machine",
            "event_id": event_id,
            "route_id": "body.machine_bridges",
            "route_path": "body/machine-bridges",
            "subject": {
                "bridge_id": bridge_row.get("id"),
                "organ": bridge_row.get("organ"),
                "artifact_path": artifact.get("path"),
                "artifact_schema": artifact.get("schema"),
            },
            "document_ids": source_document_ids,
            "coverage_planes": coverage,
            "command": bridge_row.get("command"),
            "validator": bridge_row.get("validator"),
            "artifact": {
                "path": artifact.get("path"),
                "schema": artifact.get("schema"),
                "expected_schema": artifact.get("expected_schema"),
                "ok": artifact.get("ok"),
                "schema_ok": artifact.get("schema_ok"),
                "sha256": artifact.get("sha256"),
                "machine_owned_path": artifact.get("machine_owned_path"),
            },
            "evidence_refs": evidence_refs,
            "policy": {
                "handoff_only": False,
                "requires_human_approval": False,
                "read_only": True,
                "executes_commands": False,
                "host_layer_mutates_stack": False,
                "writes_project_roots": False,
                "automatic_remediation": False,
                "actions_executed": False,
                "raw_secrets_included": False,
            },
        }
        event = {
            "schema": f"{schema_prefix}_self_awareness_entity_event_document_event_v1",
            "event_id": event_id,
            "event_path": f"body/machine-bridge/{bridge_id}/{bridge_status}",
            "event_parts": ["body", "machine-bridge", bridge_id, bridge_status],
            "event_kind": "machine_bridge_proven" if bridge_status == "ok" else "machine_bridge_degraded",
            "source": "cycle.bridge_proof",
            "entity_id": entity["entity_id"],
            "route_id": "body.machine_bridges",
            "route_path": "body/machine-bridges",
            "document_ids": source_document_ids,
            "evidence_refs": evidence_refs,
            "observed_at": self_awareness_contracts.nested_get(cycle, ["bridge_proof", "generated_at"]) or generated_at,
            "truth_level": "latest_cycle_bridge_proof",
            "policy": {
                "handoff_only": False,
                "read_only": True,
                "executes_commands": False,
                "host_layer_mutates_stack": False,
                "writes_project_roots": False,
                "automatic_remediation": False,
                "actions_executed": False,
            },
        }
        entities.append(entity)
        events.append(event)
        machine_bridge_entities.append(entity)

    route_entities = []
    for route_row in routes:
        if not isinstance(route_row, dict):
            continue
        action_ids = [
            str(item)
            for item in (route_row.get("actions") if isinstance(route_row.get("actions"), list) else [])
        ]
        mapped_entities = [entity_by_action_id[action_id] for action_id in action_ids if action_id in entity_by_action_id]
        route_entities.append({
            "schema": f"{schema_prefix}_self_awareness_entity_event_document_route_binding_v1",
            "route_id": route_row.get("route_id"),
            "route_path": route_row.get("route_path"),
            "action_ids": action_ids,
            "entity_ids": [entity.get("entity_id") for entity in mapped_entities],
            "event_ids": [entity.get("event_id") for entity in mapped_entities],
            "document_ids": sorted({
                str(document_id)
                for entity in mapped_entities
                for document_id in (entity.get("document_ids") if isinstance(entity.get("document_ids"), list) else [])
            }),
        })
    route_entities.extend([
        {
            "schema": f"{schema_prefix}_self_awareness_entity_event_document_route_binding_v1",
            "route_id": "body.stack_organs",
            "route_path": "body/stack-organs",
            "action_ids": [],
            "entity_ids": [entity.get("entity_id") for entity in stack_organ_entities],
            "event_ids": [entity.get("event_id") for entity in stack_organ_entities],
            "document_ids": sorted({
                str(document_id)
                for entity in stack_organ_entities
                for document_id in (entity.get("document_ids") if isinstance(entity.get("document_ids"), list) else [])
            }),
        },
        {
            "schema": f"{schema_prefix}_self_awareness_entity_event_document_route_binding_v1",
            "route_id": "body.machine_bridges",
            "route_path": "body/machine-bridges",
            "action_ids": [],
            "entity_ids": [entity.get("entity_id") for entity in machine_bridge_entities],
            "event_ids": [entity.get("event_id") for entity in machine_bridge_entities],
            "document_ids": sorted({
                str(document_id)
                for entity in machine_bridge_entities
                for document_id in (entity.get("document_ids") if isinstance(entity.get("document_ids"), list) else [])
            }),
        },
    ])

    action_ids = {str(action.get("id")) for action in completion_actions if isinstance(action, dict) and action.get("id")}
    entity_action_ids = {str(entity.get("action_id")) for entity in entities if entity.get("action_id")}
    event_action_ids = {str(event.get("action_id")) for event in events if event.get("action_id")}
    route_action_ids = {
        str(action_id)
        for route_row in routes
        for action_id in (route_row.get("actions") if isinstance(route_row.get("actions"), list) else [])
    }
    document_ids = set(documents_by_id)
    document_refs_mapped = all(
        set(str(document_id) for document_id in (entity.get("document_ids") if isinstance(entity.get("document_ids"), list) else [])).issubset(document_ids)
        for entity in entities
    )
    all_actions_mapped = action_ids == entity_action_ids == event_action_ids
    route_actions_mapped = route_action_ids.issubset(entity_action_ids)
    stack_organ_services = {
        str(organ.get("service"))
        for organ in working_stack_organs
        if isinstance(organ, dict) and organ.get("service")
    }
    stack_organ_entity_services = {
        str(self_awareness_contracts.nested_get(entity, ["subject", "service"]))
        for entity in stack_organ_entities
        if self_awareness_contracts.nested_get(entity, ["subject", "service"])
    }
    machine_bridge_ids = {
        stable_path_segment(bridge_row.get("id") or bridge_row.get("organ"))
        for bridge_row in bridge_rows
        if isinstance(bridge_row, dict) and (bridge_row.get("id") or bridge_row.get("organ"))
    }
    machine_bridge_entity_ids = {
        str(entity.get("entity_id", "")).removeprefix("machine.bridge.")
        for entity in machine_bridge_entities
        if entity.get("entity_id")
    }
    body_surfaces_mapped = (
        stack_organ_services == stack_organ_entity_services
        and machine_bridge_ids == machine_bridge_entity_ids
    )
    automation_ready = (
        all_actions_mapped
        and route_actions_mapped
        and body_surfaces_mapped
        and document_refs_mapped
        and all(entity.get("entity_path") and entity.get("route_path") and entity.get("event_id") for entity in entities)
        and all(event.get("event_path") and event.get("document_ids") for event in events)
        and all(self_awareness_contracts.nested_get(row, ["policy", "executes_commands"]) is False and self_awareness_contracts.nested_get(row, ["policy", "host_layer_mutates_stack"]) is False for row in entities + events + documents)
    )
    return {
        "schema": f"{schema_prefix}_self_awareness_entity_event_document_map_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": automation_ready,
        "status": "ready" if automation_ready else "incomplete",
        "summary": {
            "actions": len(action_ids),
            "entities": len(entities),
            "events": len(events),
            "documents": len(documents),
            "routes": len(route_entities),
            "completion_action_entities": len(entity_action_ids),
            "stack_organs": len(stack_organ_entities),
            "machine_bridges": len(machine_bridge_entities),
            "body_surfaces": len(stack_organ_entities) + len(machine_bridge_entities),
            "working_stack_organs": len(stack_organ_services),
            "working_stack_organs_with_entities": len(stack_organ_entity_services),
            "machine_bridge_rows": len(machine_bridge_ids),
            "machine_bridge_rows_with_entities": len(machine_bridge_entity_ids),
            "actions_with_entities": len(entity_action_ids),
            "actions_with_events": len(event_action_ids),
            "route_actions_mapped": len(route_action_ids),
            "unmapped_actions": sorted(action_ids - entity_action_ids),
            "unmapped_route_actions": sorted(route_action_ids - entity_action_ids),
            "unmapped_stack_organs": sorted(stack_organ_services - stack_organ_entity_services),
            "unmapped_machine_bridges": sorted(machine_bridge_ids - machine_bridge_entity_ids),
            "unmapped_document_refs": [] if document_refs_mapped else ["entity.document_ids"],
            "top_entity_id": entities[0].get("entity_id") if entities else None,
            "top_entity_path": entities[0].get("entity_path") if entities else None,
            "top_event_id": events[0].get("event_id") if events else None,
            "top_event_path": events[0].get("event_path") if events else None,
            "automation_ready": automation_ready,
            "owner_boundary_readonly": True,
        },
        "top_entity": entities[0] if entities else {},
        "top_event": events[0] if events else {},
        "documents": documents,
        "entities": entities,
        "events": events,
        "stack_organ_entities": stack_organ_entities,
        "machine_bridge_entities": machine_bridge_entities,
        "routes": route_entities,
        "automation": {
            "mode": "latest_only_readmodel",
            "generated_from_latest_only": True,
            "generated_from": [
                "completion_actions",
                "completion_action_drilldowns",
                "completion_route_map",
                "working_stack.organs",
                "autolink.organ_links",
                "cycle.bridge_proof.rows",
                "self_awareness_latest_artifact_refs",
            ],
            "runs_probe": False,
            "runs_cycle": False,
            "runs_indexing": False,
            "runs_stack_http_probes": False,
            "executes_verifiers": False,
            "validation_contract": {
                "every_action_has_entity": action_ids == entity_action_ids,
                "every_action_has_event": action_ids == event_action_ids,
                "every_route_action_has_entity": route_actions_mapped,
                "every_entity_has_document_refs": all(bool(entity.get("document_ids")) for entity in entities),
                "every_entity_has_route": all(bool(entity.get("route_path")) for entity in entities),
                "every_stack_organ_has_entity": stack_organ_services == stack_organ_entity_services,
                "every_machine_bridge_has_entity": machine_bridge_ids == machine_bridge_entity_ids,
                "document_refs_resolve": document_refs_mapped,
                "host_layer_mutates_stack": False,
            },
        },
        "policy": {
            "handoff_only": True,
            "read_only_stack_consumer": True,
            "requires_human_approval": True,
            "executes_commands": False,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "automatic_remediation": False,
            "actions_executed": False,
        },
    }

from __future__ import annotations

import collections
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from . import self_awareness_contracts


DocumentPort = Callable[..., Any]


@dataclass(frozen=True)
class SelfAwarenessCausalOverlayPaths:
    maps_latest: Path
    rag_trace_latest: Path
    rag_validate_latest: Path
    graph_latest: Path
    memory_latest: Path
    nervous_brief_latest: Path
    nervous_semantic_maintain_latest: Path
    requirements_latest: Path
    process_container_latest: Path
    ai_capabilities_latest: Path
    requirement_probes_latest: Path
    brief_latest: Path


@dataclass(frozen=True)
class SelfAwarenessCausalOverlayConfig:
    schema_prefix: str
    version: str
    memory_space_required_gates: Sequence[str]
    semantic_maintain_review_command: str
    semantic_maintain_retry_command: str


@dataclass(frozen=True)
class SelfAwarenessCausalOverlayRuntimePort:
    load_latest_json: DocumentPort
    now_iso: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessCausalOverlayRefreshPort:
    load_events: DocumentPort
    requirement_probes: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessCausalOverlayContractPort:
    match_score: DocumentPort
    artifact_ref: DocumentPort
    redact_text: DocumentPort
    freshness_gate: DocumentPort
    brief_stack_handoff_action_map: DocumentPort
    time_bucket: DocumentPort
    stack_handoff_impacted_services: DocumentPort


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def memory_space_overlay(
    events: list[dict[str, Any]] | None = None,
    *,
    maps: dict[str, Any] | None = None,
    rag_trace: dict[str, Any] | None = None,
    rag_validate_doc: dict[str, Any] | None = None,
    graph: dict[str, Any] | None = None,
    memory_latest: dict[str, Any] | None = None,
    nervous: dict[str, Any] | None = None,
    nervous_semantic_maintain: dict[str, Any] | None = None,
    requirements: dict[str, Any] | None = None,
    containers: dict[str, Any] | None = None,
    paths: SelfAwarenessCausalOverlayPaths,
    config: SelfAwarenessCausalOverlayConfig,
    runtime_port: SelfAwarenessCausalOverlayRuntimePort,
    refresh_port: SelfAwarenessCausalOverlayRefreshPort,
    contract_port: SelfAwarenessCausalOverlayContractPort,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    VERSION = config.version
    MAPS_LATEST_PATH = paths.maps_latest
    RAG_TRACE_LATEST_PATH = paths.rag_trace_latest
    RAG_VALIDATE_LATEST_PATH = paths.rag_validate_latest
    GRAPH_LATEST_PATH = paths.graph_latest
    MEMORY_LATEST_PATH = paths.memory_latest
    NERVOUS_BRIEF_LATEST_PATH = paths.nervous_brief_latest
    NERVOUS_SEMANTIC_MAINTAIN_LATEST_PATH = paths.nervous_semantic_maintain_latest
    SELF_AWARENESS_REQUIREMENTS_LATEST_PATH = paths.requirements_latest
    PROCESS_CONTAINER_LATEST_PATH = paths.process_container_latest
    AI_CAPABILITIES_LATEST_PATH = paths.ai_capabilities_latest
    SELF_AWARENESS_MEMORY_SPACE_REQUIRED_GATES = config.memory_space_required_gates
    NERVOUS_SEMANTIC_MAINTAIN_REVIEW_COMMAND = config.semantic_maintain_review_command
    NERVOUS_SEMANTIC_MAINTAIN_RETRY_COMMAND = config.semantic_maintain_retry_command
    load_latest_json = runtime_port.load_latest_json
    now_iso = runtime_port.now_iso
    nested_get = self_awareness_contracts.nested_get
    safe_int = _safe_int
    self_awareness_load_events = refresh_port.load_events
    self_awareness_match_score = contract_port.match_score
    self_awareness_artifact_ref = contract_port.artifact_ref
    self_awareness_redact_text = contract_port.redact_text
    self_awareness_freshness_gate = contract_port.freshness_gate
    events = events if events is not None else self_awareness_load_events(refresh=True)
    maps = maps if isinstance(maps, dict) else load_latest_json(MAPS_LATEST_PATH, f"{SCHEMA_PREFIX}_maps_v1")
    rag_trace = rag_trace if isinstance(rag_trace, dict) else load_latest_json(RAG_TRACE_LATEST_PATH, f"{SCHEMA_PREFIX}_rag_trace_v1")
    rag_validate_doc = rag_validate_doc if isinstance(rag_validate_doc, dict) else load_latest_json(RAG_VALIDATE_LATEST_PATH, f"{SCHEMA_PREFIX}_rag_validate_v1")
    graph = graph if isinstance(graph, dict) else load_latest_json(GRAPH_LATEST_PATH, f"{SCHEMA_PREFIX}_graph_v1")
    memory_latest = memory_latest if isinstance(memory_latest, dict) else load_latest_json(MEMORY_LATEST_PATH, f"{SCHEMA_PREFIX}_memory_status_v1")
    nervous = nervous if isinstance(nervous, dict) else load_latest_json(NERVOUS_BRIEF_LATEST_PATH, f"{SCHEMA_PREFIX}_nervous_brief_v1")
    nervous_semantic_maintain = nervous_semantic_maintain if isinstance(nervous_semantic_maintain, dict) else load_latest_json(NERVOUS_SEMANTIC_MAINTAIN_LATEST_PATH, f"{SCHEMA_PREFIX}_nervous_semantic_maintain_v1")
    requirements = requirements if isinstance(requirements, dict) else load_latest_json(SELF_AWARENESS_REQUIREMENTS_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_requirements_v1")
    containers = containers if isinstance(containers, dict) else load_latest_json(PROCESS_CONTAINER_LATEST_PATH, f"{SCHEMA_PREFIX}_process_container_health_v1")

    packet_entries = nested_get(rag_trace, ["packet", "entries"])
    packet_entries = packet_entries if isinstance(packet_entries, list) else []
    retrieval_packets: list[dict[str, Any]] = []
    for entry in packet_entries[:12]:
        if not isinstance(entry, dict):
            continue
        retrieval_packets.append({
            "packet_entry_id": entry.get("id"),
            "axis": entry.get("axis"),
            "label": entry.get("label"),
            "route": entry.get("route"),
            "owner_route": entry.get("owner_route"),
            "tags": entry.get("tags") if isinstance(entry.get("tags"), list) else [],
            "actionability": entry.get("actionability"),
            "truth_status": entry.get("truth_status"),
            "freshness": entry.get("freshness"),
            "next_commands": entry.get("next_commands") if isinstance(entry.get("next_commands"), list) else [],
            "evidence_refs": entry.get("evidence_refs") if isinstance(entry.get("evidence_refs"), list) else [],
            "bounded": True,
            "raw_evidence_is_not_truth": True,
            "automatic_action": False,
        })

    maps_axes = maps.get("entries_by_axis") if isinstance(maps.get("entries_by_axis"), dict) else {}
    overlay_axes = ["by-freshness", "by-rag-run", "by-memory-candidate", "by-subsystem", "by-correlation"]
    spatial_overlays: list[dict[str, Any]] = []
    for axis in overlay_axes:
        entries = maps_axes.get(axis) if isinstance(maps_axes.get(axis), list) else []
        hits = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if axis in {"by-freshness", "by-rag-run", "by-memory-candidate"} or self_awareness_match_score(entry, "rag graph memory postgres neo4j embeddings freshness") > 0:
                hits.append({
                    "id": entry.get("id"),
                    "axis": entry.get("axis") or axis,
                    "label": entry.get("label"),
                    "route": entry.get("route"),
                    "owner_route": entry.get("owner_route"),
                    "tags": entry.get("tags") if isinstance(entry.get("tags"), list) else [],
                    "freshness": entry.get("freshness"),
                    "truth_status": entry.get("truth_status"),
                    "evidence_refs": entry.get("evidence_refs") if isinstance(entry.get("evidence_refs"), list) else [],
                })
            if len(hits) >= 10:
                break
        spatial_overlays.append({
            "axis": axis,
            "entries": hits,
            "entry_count": len(entries),
            "bounded_entries": len(hits),
            "evidence_refs": [self_awareness_artifact_ref(MAPS_LATEST_PATH, maps, "generated_route_atlas")],
        })

    requirements_rows = requirements.get("requirements") if isinstance(requirements.get("requirements"), list) else []
    requirement_by_id = {str(item.get("id")): item for item in requirements_rows if isinstance(item, dict)}
    container_text = self_awareness_redact_text(containers, 20000).lower()
    stack_semantic_backends = [
        {
            "id": "postgres",
            "owner": "abyss-stack",
            "visible": "postgres" in container_text,
            "semantic_inventory": "requirement_open" if "stack.database-graph.read-route" in requirement_by_id else "not_required",
            "requirement_id": "stack.database-graph.read-route" if "stack.database-graph.read-route" in requirement_by_id else None,
            "machine_role": "read_only_consumer",
            "evidence_refs": [
                self_awareness_artifact_ref(PROCESS_CONTAINER_LATEST_PATH, containers, "container_health"),
            ] + ([{"path": str(SELF_AWARENESS_REQUIREMENTS_LATEST_PATH), "requirement_id": "stack.database-graph.read-route"}] if "stack.database-graph.read-route" in requirement_by_id else []),
        },
        {
            "id": "neo4j",
            "owner": "abyss-stack",
            "visible": "neo4j" in container_text,
            "semantic_inventory": "requirement_open" if "stack.database-graph.read-route" in requirement_by_id else "not_required",
            "requirement_id": "stack.database-graph.read-route" if "stack.database-graph.read-route" in requirement_by_id else None,
            "machine_role": "read_only_consumer",
            "evidence_refs": [
                self_awareness_artifact_ref(PROCESS_CONTAINER_LATEST_PATH, containers, "container_health"),
            ] + ([{"path": str(SELF_AWARENESS_REQUIREMENTS_LATEST_PATH), "requirement_id": "stack.database-graph.read-route"}] if "stack.database-graph.read-route" in requirement_by_id else []),
        },
        {
            "id": "rag-api",
            "owner": "abyss-stack",
            "visible": "rag-api" in container_text,
            "semantic_inventory": "bounded_machine_rag_trace",
            "machine_role": "read_only_consumer",
            "evidence_refs": [
                self_awareness_artifact_ref(RAG_TRACE_LATEST_PATH, rag_trace, "generated_rag_trace"),
                self_awareness_artifact_ref(RAG_VALIDATE_LATEST_PATH, rag_validate_doc, "rag_validation"),
            ],
        },
        {
            "id": "embeddings",
            "owner": "abyss-machine",
            "visible": True,
            "semantic_inventory": "ai_capability_map",
            "machine_role": "host_capability_evidence",
            "evidence_refs": [{"path": str(AI_CAPABILITIES_LATEST_PATH), "truth_level": "ai_capability_map"}],
        },
    ]

    nervous_readiness = nervous.get("readiness") if isinstance(nervous.get("readiness"), dict) else {}
    semantic_stale = bool(nested_get(nervous, ["readiness", "semantic_stale"]) or nested_get(nervous, ["readiness", "semantic_maintenance_needed"]))
    nervous_maintenance_details = {
        "readiness": nervous_readiness,
        "gaps": nervous.get("gaps") if isinstance(nervous.get("gaps"), list) else [],
        "next_actions": nervous.get("next_actions") if isinstance(nervous.get("next_actions"), list) else [],
        "maintenance_review_command": NERVOUS_SEMANTIC_MAINTAIN_REVIEW_COMMAND,
        "maintenance_retry_command": NERVOUS_SEMANTIC_MAINTAIN_RETRY_COMMAND,
        "semantic_maintain": {
            "decision": nervous_semantic_maintain.get("decision"),
            "reason": nervous_semantic_maintain.get("reason"),
            "ok": nervous_semantic_maintain.get("ok"),
            "resource": nervous_semantic_maintain.get("resource") if isinstance(nervous_semantic_maintain.get("resource"), dict) else {},
            "assessment": nervous_semantic_maintain.get("assessment") if isinstance(nervous_semantic_maintain.get("assessment"), dict) else {},
            "index_refresh_assessment": nested_get(nervous_semantic_maintain, ["index_refresh", "assessment"]) if isinstance(nested_get(nervous_semantic_maintain, ["index_refresh", "assessment"]), dict) else {},
            "index_refresh_blocked_reasons": nested_get(nervous_semantic_maintain, ["index_refresh", "launch", "blocked_reasons"]) if isinstance(nested_get(nervous_semantic_maintain, ["index_refresh", "launch", "blocked_reasons"]), list) else [],
            "index_refresh_denied_reasons": nested_get(nervous_semantic_maintain, ["index_refresh", "launch", "denied_reasons"]) if isinstance(nested_get(nervous_semantic_maintain, ["index_refresh", "launch", "denied_reasons"]), list) else [],
            "build_blocked_reasons": nested_get(nervous_semantic_maintain, ["launch", "blocked_reasons"]) if isinstance(nested_get(nervous_semantic_maintain, ["launch", "blocked_reasons"]), list) else [],
            "build_denied_reasons": nested_get(nervous_semantic_maintain, ["launch", "denied_reasons"]) if isinstance(nested_get(nervous_semantic_maintain, ["launch", "denied_reasons"]), list) else [],
        },
        "resource_denial_is_safe_gate": bool(
            nested_get(nervous_semantic_maintain, ["index_refresh", "launch", "blocked_reasons"])
            or nested_get(nervous_semantic_maintain, ["index_refresh", "launch", "denied_reasons"])
            or nested_get(nervous_semantic_maintain, ["launch", "blocked_reasons"])
            or nested_get(nervous_semantic_maintain, ["launch", "denied_reasons"])
        ),
        "policy": {
            "freshness_must_precede_reasoning": True,
            "does_not_bypass_resource_gate": True,
            "automatic_remediation": False,
            "host_layer_mutates_stack": False,
        },
    }
    gates = [
        self_awareness_freshness_gate("rag_trace", "Machine RAG trace packet", RAG_TRACE_LATEST_PATH, rag_trace, "generated_rag_trace", ok=rag_trace.get("ok"), generated_at=rag_trace.get("generated_at"), maintenance_route="abyss-machine rag trace --query TEXT --json"),
        self_awareness_freshness_gate("rag_validate", "Machine RAG validation", RAG_VALIDATE_LATEST_PATH, rag_validate_doc, "rag_validation", ok=rag_validate_doc.get("ok"), generated_at=rag_validate_doc.get("generated_at"), maintenance_route="abyss-machine rag validate --json"),
        self_awareness_freshness_gate("maps", "Machine maps route atlas", MAPS_LATEST_PATH, maps, "generated_route_atlas", ok=maps.get("ok"), generated_at=maps.get("generated_at"), maintenance_route="abyss-machine maps refresh --json"),
        self_awareness_freshness_gate("graph", "Machine graph overlay source", GRAPH_LATEST_PATH, graph, "generated_contract_graph", ok=graph.get("ok"), generated_at=graph.get("generated_at"), maintenance_route="abyss-machine graph --json"),
        self_awareness_freshness_gate("memory_status", "Host memory pressure/status", MEMORY_LATEST_PATH, memory_latest, "host_memory_status", ok=memory_latest.get("ok"), generated_at=memory_latest.get("generated_at"), maintenance_route="abyss-machine memory status --json"),
        self_awareness_freshness_gate(
            "nervous_freshness",
            "Nervous freshness/readiness",
            NERVOUS_BRIEF_LATEST_PATH,
            nervous,
            "nervous_readiness",
            ok=bool(nervous_readiness),
            generated_at=nervous.get("generated_at"),
            stale=semantic_stale,
            maintenance_route=NERVOUS_SEMANTIC_MAINTAIN_REVIEW_COMMAND,
            evidence_refs=[self_awareness_artifact_ref(NERVOUS_SEMANTIC_MAINTAIN_LATEST_PATH, nervous_semantic_maintain, "nervous_semantic_maintain")],
            details=nervous_maintenance_details,
        ),
    ]

    service_counts = dict(collections.Counter(
        str(nested_get(event, ["fabric", "entity", "service"]) or nested_get(event, ["resource", "service"]) or nested_get(event, ["resource", "container"]) or "unknown")
        for event in events if isinstance(event, dict)
    ))
    event_contexts = [
        {
            "event_id": event.get("event_id"),
            "service": nested_get(event, ["fabric", "entity", "service"]) or nested_get(event, ["resource", "service"]),
            "time_bucket": nested_get(event, ["fabric", "temporal", "time_bucket"]),
            "correlation_keys": nested_get(event, ["fabric", "context_links", "correlation_keys"]),
            "evidence_refs": event.get("evidence_refs") if isinstance(event.get("evidence_refs"), list) else [],
        }
        for event in events[:20] if isinstance(event, dict)
    ]
    evidence_refs = [
        self_awareness_artifact_ref(RAG_TRACE_LATEST_PATH, rag_trace, "generated_rag_trace"),
        self_awareness_artifact_ref(RAG_VALIDATE_LATEST_PATH, rag_validate_doc, "rag_validation"),
        self_awareness_artifact_ref(MAPS_LATEST_PATH, maps, "generated_route_atlas"),
        self_awareness_artifact_ref(GRAPH_LATEST_PATH, graph, "generated_contract_graph"),
        self_awareness_artifact_ref(MEMORY_LATEST_PATH, memory_latest, "host_memory_status"),
        self_awareness_artifact_ref(NERVOUS_BRIEF_LATEST_PATH, nervous, "nervous_readiness"),
    ]
    open_stack_backends = [item for item in stack_semantic_backends if item.get("owner") == "abyss-stack" and item.get("semantic_inventory") == "requirement_open"]
    return {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_memory_space_overlay_v1",
        "version": VERSION,
        "generated_at": now_iso(),
        "ok": bool(retrieval_packets) and all(gate.get("gate_id") in SELF_AWARENESS_MEMORY_SPACE_REQUIRED_GATES for gate in gates),
        "summary": {
            "events": len(events),
            "retrieval_packets": len(retrieval_packets),
            "spatial_overlay_axes": len(spatial_overlays),
            "spatial_overlay_entries": sum(safe_int(item.get("bounded_entries"), 0) for item in spatial_overlays),
            "freshness_gates": len(gates),
            "blocked_gates": sum(1 for gate in gates if gate.get("blocks_deep_reasoning")),
            "stack_semantic_backends": len(stack_semantic_backends),
            "open_stack_semantic_requirements": len(open_stack_backends),
            "event_contexts": len(event_contexts),
        },
        "retrieval_packets": retrieval_packets,
        "freshness_gates": gates,
        "spatial_overlays": spatial_overlays,
        "stack_semantic_backends": stack_semantic_backends,
        "event_contexts": event_contexts,
        "service_counts": service_counts,
        "evidence_refs": evidence_refs,
        "policy": {
            "bounded_retrieval": True,
            "freshness_must_precede_reasoning": True,
            "raw_evidence_is_not_truth": True,
            "raw_private_content": False,
            "memory_writeback": False,
            "kag_truth_publication": False,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "stack_requirements_are_handoffs": True,
        },
    }


def stack_handoff_time_space_overlay(
    requirement_probes: dict[str, Any] | None = None,
    *,
    generated_at: str | None = None,
    refresh_probes: bool = False,
    paths: SelfAwarenessCausalOverlayPaths,
    config: SelfAwarenessCausalOverlayConfig,
    runtime_port: SelfAwarenessCausalOverlayRuntimePort,
    refresh_port: SelfAwarenessCausalOverlayRefreshPort,
    contract_port: SelfAwarenessCausalOverlayContractPort,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    VERSION = config.version
    SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH = paths.requirement_probes_latest
    SELF_AWARENESS_BRIEF_LATEST_PATH = paths.brief_latest
    load_latest_json = runtime_port.load_latest_json
    now_iso = runtime_port.now_iso
    nested_get = self_awareness_contracts.nested_get
    stable_hash_json = self_awareness_contracts.stable_hash_json
    self_awareness_requirement_probes = refresh_port.requirement_probes
    self_awareness_brief_stack_handoff_action_map = contract_port.brief_stack_handoff_action_map
    self_awareness_time_bucket = contract_port.time_bucket
    self_awareness_stack_handoff_impacted_services = contract_port.stack_handoff_impacted_services
    generated_at = generated_at or now_iso()
    if not isinstance(requirement_probes, dict):
        requirement_probes = self_awareness_requirement_probes(write_latest=True) if refresh_probes else load_latest_json(SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_requirement_probes_v1")
    if requirement_probes.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_requirement_probes_v1":
        requirement_probes = self_awareness_requirement_probes(write_latest=True)
    action_map = self_awareness_brief_stack_handoff_action_map(requirement_probes)
    actions = action_map.get("actions") if isinstance(action_map.get("actions"), list) else []
    bucket = self_awareness_time_bucket(generated_at)
    markers: list[dict[str, Any]] = []
    spatial_nodes: list[dict[str, Any]] = [{
        "id": "overlay:stack-handoff",
        "kind": "stack_handoff_overlay",
        "label": "stack handoff time-space overlay",
        "owner_surface": "abyss-machine",
        "summary": action_map.get("summary"),
        "policy": action_map.get("policy"),
    }]
    spatial_edges: list[dict[str, Any]] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        requirement_id = str(action.get("requirement_id") or action.get("id") or "unknown")
        action_id = str(action.get("id") or ("stack-handoff-action-" + requirement_id))
        requirement_node_id = "stack_requirement:" + requirement_id
        action_node_id = "stack_handoff_action:" + action_id
        runbook_id = str(action.get("runbook_candidate_id") or nested_get(action, ["runbook_candidate", "id"]) or ("runbook:" + requirement_id))
        runbook_node_id = "stack_runbook:" + runbook_id
        services = self_awareness_stack_handoff_impacted_services(requirement_id)
        evidence_refs = action.get("evidence_refs") if isinstance(action.get("evidence_refs"), list) else []
        closure_blocker_keys = [str(item) for item in (action.get("closure_blocker_keys") if isinstance(action.get("closure_blocker_keys"), list) else [])]
        coverage_impact = action.get("coverage_impact") if isinstance(action.get("coverage_impact"), dict) else {}
        coverage_planes = [str(item) for item in (coverage_impact.get("coverage_planes") if isinstance(coverage_impact.get("coverage_planes"), list) else []) if item]
        marker = {
            "schema": f"{SCHEMA_PREFIX}_self_awareness_stack_handoff_timeline_marker_v1",
            "id": "stack_handoff_marker:" + requirement_id,
            "requirement_id": requirement_id,
            "action_id": action_id,
            "owner_route": action.get("owner_route") or "abyss-stack",
            "priority_rank": action.get("priority_rank"),
            "priority_class": action.get("priority_class"),
            "priority_score": action.get("priority_score"),
            "priority_reasons": action.get("priority_reasons"),
            "time": {
                "observed_at": generated_at,
                "bucket": bucket,
                "status": "open_stack_requirement",
                "freshness_must_precede_reasoning": True,
            },
            "space": {
                "owner_surface": "abyss-stack",
                "service_nodes": ["service:" + service for service in services],
                "requirement_node": requirement_node_id,
                "action_node": action_node_id,
            },
            "services": services,
            "impact_organ": coverage_impact.get("organ"),
            "coverage_planes": coverage_planes,
            "coverage_impact": coverage_impact,
            "closure_blocker_keys": closure_blocker_keys,
            "closure_blockers": action.get("closure_blockers"),
            "closure_readiness": action.get("closure_readiness"),
            "current_state": action.get("current_state"),
            "runbook_candidate_id": runbook_id,
            "runbook_candidate": action.get("runbook_candidate"),
            "acceptance_verifiers": action.get("acceptance_verifiers"),
            "verifier_commands": action.get("verifier_commands"),
            "safe_next_action": action.get("safe_next_action"),
            "policy": action.get("policy"),
            "evidence_refs": evidence_refs,
        }
        markers.append(marker)
        spatial_nodes.extend([
            {
                "id": requirement_node_id,
                "kind": "stack_requirement",
                "label": requirement_id,
                "owner_surface": "abyss-stack",
                "status": "open",
                "requirement_id": requirement_id,
                "priority_rank": action.get("priority_rank"),
                "priority_class": action.get("priority_class"),
                "impact_organ": coverage_impact.get("organ"),
                "coverage_planes": coverage_planes,
                "coverage_impact": coverage_impact,
                "closure_blocker_keys": closure_blocker_keys,
                "closure_readiness": action.get("closure_readiness"),
                "current_state": action.get("current_state"),
                "evidence_refs": evidence_refs,
                "policy": action.get("policy"),
            },
            {
                "id": action_node_id,
                "kind": "stack_handoff_action",
                "label": action_id,
                "owner_surface": "abyss-machine",
                "requirement_id": requirement_id,
                "owner_route": action.get("owner_route") or "abyss-stack",
                "priority_rank": action.get("priority_rank"),
                "priority_class": action.get("priority_class"),
                "impact_organ": coverage_impact.get("organ"),
                "coverage_planes": coverage_planes,
                "coverage_impact": coverage_impact,
                "closure_readiness": action.get("closure_readiness"),
                "safe_next_action": action.get("safe_next_action"),
                "verifier_commands": action.get("verifier_commands"),
                "policy": action.get("policy"),
                "evidence_refs": evidence_refs,
            },
            {
                "id": runbook_node_id,
                "kind": "stack_runbook_candidate",
                "label": runbook_id,
                "owner_surface": "abyss-stack",
                "requirement_id": requirement_id,
                "machine_executes_stack_change": nested_get(action, ["runbook_candidate", "machine_executes_stack_change"]),
                "host_layer_mutates_stack": nested_get(action, ["runbook_candidate", "host_layer_mutates_stack"]),
                "acceptance_verifiers": nested_get(action, ["runbook_candidate", "acceptance_verifiers"]),
                "evidence_refs": evidence_refs,
            },
        ])
        spatial_edges.extend([
            {
                "id": "saedge-" + stable_hash_json({"from": "overlay:stack-handoff", "to": requirement_node_id, "kind": "tracks_open_stack_requirement"}, length=20),
                "from": "overlay:stack-handoff",
                "to": requirement_node_id,
                "kind": "tracks_open_stack_requirement",
                "evidence_refs": evidence_refs,
            },
            {
                "id": "saedge-" + stable_hash_json({"from": action_node_id, "to": requirement_node_id, "kind": "proposes_handoff_for"}, length=20),
                "from": action_node_id,
                "to": requirement_node_id,
                "kind": "proposes_handoff_for",
                "evidence_refs": evidence_refs,
            },
            {
                "id": "saedge-" + stable_hash_json({"from": action_node_id, "to": runbook_node_id, "kind": "has_runbook_candidate"}, length=20),
                "from": action_node_id,
                "to": runbook_node_id,
                "kind": "has_runbook_candidate",
                "evidence_refs": evidence_refs,
            },
        ])
        for service in services:
            service_node_id = "service:" + service
            spatial_nodes.append({
                "id": service_node_id,
                "kind": "service",
                "label": service,
                "owner_surface": "abyss-stack",
                "required_by_stack_handoff": True,
            })
            spatial_edges.append({
                "id": "saedge-" + stable_hash_json({"from": requirement_node_id, "to": service_node_id, "kind": "blocks_stack_surface"}, length=20),
                "from": requirement_node_id,
                "to": service_node_id,
                "kind": "blocks_stack_surface",
                "requirement_id": requirement_id,
                "evidence_refs": evidence_refs,
            })
        for plane in coverage_planes:
            plane_node_id = "coverage_plane:" + plane
            spatial_nodes.append({
                "id": plane_node_id,
                "kind": "coverage_plane",
                "label": plane,
                "owner_surface": "abyss-machine:self-awareness",
                "requirement_id": requirement_id,
                "impact_organ": coverage_impact.get("organ"),
                "required_by_stack_handoff": True,
            })
            spatial_edges.append({
                "id": "saedge-" + stable_hash_json({"from": requirement_node_id, "to": plane_node_id, "kind": "blocks_coverage_plane"}, length=20),
                "from": requirement_node_id,
                "to": plane_node_id,
                "kind": "blocks_coverage_plane",
                "requirement_id": requirement_id,
                "impact_organ": coverage_impact.get("organ"),
                "evidence_refs": evidence_refs,
            })
    spatial_node_ids = sorted({str(item.get("id")) for item in spatial_nodes if isinstance(item, dict) and item.get("id")})
    spatial_edge_ids = sorted({str(item.get("id")) for item in spatial_edges if isinstance(item, dict) and item.get("id")})
    return {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_stack_handoff_time_space_overlay_v1",
        "version": VERSION,
        "generated_at": generated_at,
        "ok": action_map.get("schema") == f"{SCHEMA_PREFIX}_self_awareness_brief_stack_handoff_action_map_v1"
        and nested_get(action_map, ["policy", "host_layer_mutates_stack"]) is False
        and nested_get(action_map, ["policy", "executes_commands"]) is False,
        "status": action_map.get("status"),
        "action_map_summary": action_map.get("summary"),
        "open_requirement_ids": action_map.get("open_requirement_ids"),
        "timeline_markers": markers,
        "spatial_nodes": spatial_nodes,
        "spatial_edges": spatial_edges,
        "safe_next_action": action_map.get("safe_next_action"),
        "summary": {
            "open_stack_requirements": len(markers),
            "actions": len(actions),
            "timeline_markers": len(markers),
            "spatial_nodes": len(spatial_node_ids),
            "spatial_edges": len(spatial_edge_ids),
            "acceptance_verifier_steps": nested_get(action_map, ["summary", "acceptance_verifier_steps"]),
            "closure_blockers": nested_get(action_map, ["summary", "closure_blockers"]),
            "top_requirement_id": nested_get(action_map, ["summary", "top_requirement_id"]),
            "top_priority_class": nested_get(action_map, ["summary", "top_priority_class"]),
        },
        "policy": {
            "read_only": True,
            "handoff_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "automatic_remediation": False,
            "raw_secrets_included": False,
            "open_stack_requirements_are_blockers_not_host_failures": True,
        },
        "evidence_refs": [
            {"path": str(SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH), "schema": requirement_probes.get("schema")},
            {"path": str(SELF_AWARENESS_BRIEF_LATEST_PATH), "section": "stack_handoff_action_map"},
        ],
    }

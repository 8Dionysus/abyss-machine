from __future__ import annotations

import collections
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from . import self_awareness_contracts


DocumentPort = Callable[..., Any]


@dataclass(frozen=True)
class SelfAwarenessCausalPaths:
    timeline_latest: Path
    timeline_root: Path
    spatial_graph_latest: Path
    spatial_graph_root: Path
    working_stack_latest: Path
    stack_observability_latest: Path
    capabilities_latest: Path
    context_latest: Path
    context_root: Path
    requirement_probes_latest: Path
    trace_context_latest: Path
    episodes_latest: Path
    episodes_root: Path
    events_latest: Path


@dataclass(frozen=True)
class SelfAwarenessCausalConstants:
    working_stack_expected_live_services: Sequence[str]
    unbounded_labels: set[str]


@dataclass(frozen=True)
class SelfAwarenessCausalRuntimePort:
    load_latest_json: DocumentPort
    write_latest_and_history: DocumentPort
    now_iso: DocumentPort
    hostname: DocumentPort
    storage_path_protection: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessCausalRefreshPort:
    load_events: DocumentPort
    working_stack_inventory: DocumentPort
    capabilities: DocumentPort
    requirement_probes: DocumentPort
    timeline: DocumentPort
    spatial_graph: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessCausalContractPort:
    dedupe_events: DocumentPort
    parse_time: DocumentPort
    stack_handoff_time_space_overlay: DocumentPort
    time_bucket: DocumentPort
    memory_space_overlay: DocumentPort
    bounded_context_packet: DocumentPort
    brief_stack_handoff_action_map: DocumentPort
    working_stack_gap_episodes: DocumentPort


def timeline(
    write_latest: bool = True,
    *,
    schema_prefix: str,
    version: str,
    paths: SelfAwarenessCausalPaths,
    runtime_port: SelfAwarenessCausalRuntimePort,
    refresh_port: SelfAwarenessCausalRefreshPort,
    contract_port: SelfAwarenessCausalContractPort,
    constants: SelfAwarenessCausalConstants,
) -> dict[str, Any]:
    SCHEMA_PREFIX = schema_prefix
    VERSION = version
    SELF_AWARENESS_TIMELINE_LATEST_PATH = paths.timeline_latest
    SELF_AWARENESS_TIMELINE_ROOT = paths.timeline_root
    now_iso = runtime_port.now_iso
    write_latest_and_history = runtime_port.write_latest_and_history
    nested_get = self_awareness_contracts.nested_get
    self_awareness_dedupe_events = contract_port.dedupe_events
    self_awareness_load_events = refresh_port.load_events
    self_awareness_parse_time = contract_port.parse_time
    self_awareness_stack_handoff_time_space_overlay = contract_port.stack_handoff_time_space_overlay
    self_awareness_time_bucket = contract_port.time_bucket
    events = self_awareness_dedupe_events(self_awareness_load_events(refresh=True))
    events.sort(key=lambda event: str(event.get("event_time") or ""))
    windows: dict[str, dict[str, Any]] = {}
    skewed: list[dict[str, Any]] = []
    for event in events:
        bucket = self_awareness_time_bucket(event.get("event_time"))
        window = windows.setdefault(bucket, {"bucket": bucket, "event_ids": [], "signals": {}, "sources": {}, "contexts": [], "resources": []})
        event_id = str(event.get("event_id"))
        window["event_ids"].append(event_id)
        window["signals"][str(event.get("signal"))] = int(window["signals"].get(str(event.get("signal")), 0)) + 1
        window["sources"][str(event.get("source"))] = int(window["sources"].get(str(event.get("source")), 0)) + 1
        context = event.get("context") if isinstance(event.get("context"), dict) else {}
        resource = event.get("resource") if isinstance(event.get("resource"), dict) else {}
        if context:
            window["contexts"].append({key: context.get(key) for key in ("trace_id", "request_id", "session_id", "synthetic_run_id", "alert_fingerprint", "working_stack_link_id", "movement_packet_id", "pid") if context.get(key)})
        window["resources"].append({key: resource.get(key) for key in ("service", "container", "pid", "alertname", "owner_surface", "route", "movement_packet_id") if resource.get(key)})
        event_time = self_awareness_parse_time(event.get("event_time"))
        observed_at = self_awareness_parse_time(event.get("observed_at"))
        if event_time and observed_at and abs((observed_at - event_time).total_seconds()) > 300:
            skewed.append({"event_id": event_id, "event_time": event.get("event_time"), "observed_at": event.get("observed_at")})
    generated_at = now_iso()
    stack_handoff_overlay = self_awareness_stack_handoff_time_space_overlay(generated_at=generated_at)
    for marker in stack_handoff_overlay.get("timeline_markers", []) if isinstance(stack_handoff_overlay.get("timeline_markers"), list) else []:
        if not isinstance(marker, dict):
            continue
        bucket = nested_get(marker, ["time", "bucket"]) or self_awareness_time_bucket(generated_at)
        window = windows.setdefault(bucket, {"bucket": bucket, "event_ids": [], "signals": {}, "sources": {}, "contexts": [], "resources": []})
        marker_ids = window.setdefault("stack_handoff_marker_ids", [])
        if isinstance(marker_ids, list):
            marker_ids.append(marker.get("id"))
        requirement_ids = window.setdefault("open_stack_requirement_ids", [])
        if isinstance(requirement_ids, list) and marker.get("requirement_id") not in requirement_ids:
            requirement_ids.append(marker.get("requirement_id"))
        window["signals"]["stack_handoff"] = int(window["signals"].get("stack_handoff", 0)) + 1
        window["sources"]["self_awareness_requirement_probes"] = int(window["sources"].get("self_awareness_requirement_probes", 0)) + 1
        window["resources"].append({
            "service": ",".join(marker.get("services") if isinstance(marker.get("services"), list) else []),
            "owner_surface": "abyss-stack",
            "requirement_id": marker.get("requirement_id"),
        })
    data = {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_timeline_v1",
        "version": VERSION,
        "generated_at": generated_at,
        "ok": bool(events),
        "summary": {
            "events": len(events),
            "windows": len(windows),
            "clock_skewed_events": len(skewed),
            "latest_event_time": events[-1].get("event_time") if events else None,
            "stack_handoff_markers": nested_get(stack_handoff_overlay, ["summary", "timeline_markers"]),
            "open_stack_requirements": nested_get(stack_handoff_overlay, ["summary", "open_stack_requirements"]),
            "stack_handoff_verifier_steps": nested_get(stack_handoff_overlay, ["summary", "acceptance_verifier_steps"]),
        },
        "windows": list(windows.values()),
        "events": events,
        "stack_handoff_time_space_overlay": stack_handoff_overlay,
        "clock_skew": skewed,
        "source_freshness": {
            source: max((str(event.get("observed_at") or "") for event in events if event.get("source") == source), default=None)
            for source in sorted(set(str(event.get("source")) for event in events))
        },
        "tests": {
            "dedupe": "event_id dedupe applied",
            "skew": "event_time and observed_at both preserved",
        },
    }
    if write_latest:
        errors = write_latest_and_history(data, SELF_AWARENESS_TIMELINE_LATEST_PATH, SELF_AWARENESS_TIMELINE_ROOT)
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def spatial_graph(
    write_latest: bool = True,
    *,
    working_stack_doc: dict[str, Any] | None = None,
    timeline_doc: dict[str, Any] | None = None,
    schema_prefix: str,
    version: str,
    paths: SelfAwarenessCausalPaths,
    runtime_port: SelfAwarenessCausalRuntimePort,
    refresh_port: SelfAwarenessCausalRefreshPort,
    contract_port: SelfAwarenessCausalContractPort,
    constants: SelfAwarenessCausalConstants,
) -> dict[str, Any]:
    SCHEMA_PREFIX = schema_prefix
    VERSION = version
    SELF_AWARENESS_SPATIAL_GRAPH_LATEST_PATH = paths.spatial_graph_latest
    SELF_AWARENESS_SPATIAL_GRAPH_ROOT = paths.spatial_graph_root
    SELF_AWARENESS_TIMELINE_LATEST_PATH = paths.timeline_latest
    SELF_AWARENESS_WORKING_STACK_LATEST_PATH = paths.working_stack_latest
    SELF_AWARENESS_WORKING_STACK_EXPECTED_LIVE_SERVICES = constants.working_stack_expected_live_services
    load_latest_json = runtime_port.load_latest_json
    now_iso = runtime_port.now_iso
    storage_path_protection = runtime_port.storage_path_protection
    write_latest_and_history = runtime_port.write_latest_and_history
    nested_get = self_awareness_contracts.nested_get
    stable_hash_json = self_awareness_contracts.stable_hash_json
    self_awareness_memory_space_overlay = contract_port.memory_space_overlay
    self_awareness_stack_handoff_time_space_overlay = contract_port.stack_handoff_time_space_overlay
    self_awareness_working_stack_inventory = refresh_port.working_stack_inventory

    timeline_document = timeline_doc if isinstance(timeline_doc, dict) else load_latest_json(SELF_AWARENESS_TIMELINE_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_timeline_v1")
    if not isinstance(timeline_document.get("events"), list) or not isinstance(timeline_document.get("stack_handoff_time_space_overlay"), dict):
        timeline_document = refresh_port.timeline(write_latest=True)
    events = timeline_document.get("events") if isinstance(timeline_document.get("events"), list) else []
    stack_handoff_overlay = timeline_document.get("stack_handoff_time_space_overlay") if isinstance(timeline_document.get("stack_handoff_time_space_overlay"), dict) else self_awareness_stack_handoff_time_space_overlay()
    memory_space = self_awareness_memory_space_overlay(events)
    working_stack = working_stack_doc if isinstance(working_stack_doc, dict) else load_latest_json(SELF_AWARENESS_WORKING_STACK_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_working_stack_inventory_v1")
    if working_stack.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_working_stack_inventory_v1":
        working_stack = self_awareness_working_stack_inventory(write_latest=True)
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}

    def node(node_id: str, kind: str, label: str, **extra: Any) -> None:
        if not node_id:
            return
        incoming = {"id": node_id, "kind": kind, "label": label, **extra}
        existing = nodes.setdefault(node_id, incoming)
        if existing is incoming:
            return
        for key, value in incoming.items():
            if value in (None, "", [], {}):
                continue
            if key == "owner_surface" and node_id.startswith("service:") and existing.get(key) == "abyss-machine" and value == "abyss-stack":
                existing[key] = value
            elif key not in existing or existing.get(key) in (None, "", [], {}):
                existing[key] = value

    def edge(src: str, dst: str, kind: str, **extra: Any) -> None:
        if not src or not dst:
            return
        edge_id = "saedge-" + stable_hash_json({"src": src, "dst": dst, "kind": kind, **extra}, length=20)
        edges.setdefault(edge_id, {"id": edge_id, "from": src, "to": dst, "kind": kind, **extra})

    host_id = "host:" + (runtime_port.hostname() or "localhost")
    node(host_id, "host", runtime_port.hostname() or "localhost", owner_surface="abyss-machine")
    for service_name in (
        "prometheus", "grafana", "loki", "alloy", "alertmanager",
        "route-api", "rag-api", "langchain-api", "postgres", "neo4j",
        "warm-e2b-gemma4.spark", "llm-registry", "ai-capabilities", "stt", "embeddings", "tts", "npu",
    ):
        sid = "service:" + service_name
        owner_surface = "abyss-machine" if service_name in {"warm-e2b-gemma4.spark", "llm-registry", "ai-capabilities", "stt", "embeddings", "tts", "npu"} else "abyss-stack"
        node(sid, "service", service_name, owner_surface=owner_surface)
        edge(sid, host_id, "runs_on")
    edge("service:alloy", "service:loki", "logs_to")
    edge("service:prometheus", "service:alloy", "scraped_by")
    edge("service:prometheus", "service:alertmanager", "alerts_to")
    edge("service:grafana", "service:prometheus", "depends_on")
    edge("service:grafana", "service:loki", "depends_on")
    edge("service:route-api", "service:rag-api", "routes_to")
    edge("service:rag-api", "service:postgres", "reads_from")
    edge("service:rag-api", "service:neo4j", "reads_from")
    edge("service:langchain-api", "service:rag-api", "uses_context")
    edge("service:warm-e2b-gemma4.spark", "service:ai-capabilities", "member_of")
    edge("service:warm-e2b-gemma4.spark", "service:rag-api", "read_only_context_candidate")
    edge("service:warm-e2b-gemma4.spark", "service:resource-status", "gated_by")
    edge("service:warm-e2b-gemma4.spark", "service:mode-status", "gated_by")
    for organ in working_stack.get("organs", []) if isinstance(working_stack.get("organs"), list) else []:
        if not isinstance(organ, dict):
            continue
        service = str(organ.get("service") or "")
        if not service:
            continue
        sid = "service:" + service
        runtime = organ.get("runtime") if isinstance(organ.get("runtime"), dict) else {}
        link = organ.get("time_space_context_link") if isinstance(organ.get("time_space_context_link"), dict) else {}
        node(
            sid,
            "service",
            service,
            owner_surface="abyss-stack",
            machine_usage_status=organ.get("machine_usage_status"),
            deep_usage_proven=organ.get("deep_usage_proven"),
            roles=organ.get("roles"),
            runtime_running=runtime.get("running"),
            pid=runtime.get("pid"),
            pid_alive=runtime.get("pid_alive"),
            health=runtime.get("health"),
            declared=nested_get(organ, ["declared", "present"]),
            service_roots=organ.get("service_roots"),
            model_roots=organ.get("model_roots"),
        )
        edge(sid, host_id, "runs_on", evidence_refs=organ.get("evidence_refs"))
        if runtime.get("container"):
            cid = "container:" + str(runtime.get("container"))
            node(cid, "container", str(runtime.get("container")), owner_surface="abyss-stack", running=runtime.get("running"), pid=runtime.get("pid"), pid_alive=runtime.get("pid_alive"), health=runtime.get("health"))
            edge(cid, host_id, "runs_on")
            edge(sid, cid, "has_container")
            if runtime.get("pid"):
                pid_id = "process:" + str(runtime.get("pid"))
                node(pid_id, "process", str(runtime.get("pid")), owner_surface="abyss-stack", service=service, container=runtime.get("container"), pid_alive=runtime.get("pid_alive"))
                edge(pid_id, cid, "process_of_container")
                edge(pid_id, host_id, "runs_on")
        if link.get("link_id"):
            lid = "working_stack_link:" + str(link.get("link_id"))
            node(lid, "working_stack_context_link", str(link.get("link_id")), owner_surface="abyss-stack", machine_usage_status=organ.get("machine_usage_status"), time=nested_get(link, ["time", "bucket"]))
            edge(sid, lid, "has_time_space_context_link")
        for probe in organ.get("endpoint_probes", []) if isinstance(organ.get("endpoint_probes"), list) else []:
            if not isinstance(probe, dict) or not probe.get("url"):
                continue
            endpoint_id = "endpoint:" + stable_hash_json(probe.get("url"), length=16)
            node(endpoint_id, "endpoint", str(probe.get("probe") or probe.get("url")), owner_surface="abyss-stack", ok=probe.get("ok"), url=probe.get("url"), status_code=probe.get("status_code"))
            edge(sid, endpoint_id, "has_readonly_probe", evidence_refs=[{"path": str(SELF_AWARENESS_WORKING_STACK_LATEST_PATH), "service": service, "probe": probe.get("probe")}])
        if organ.get("usage_gap"):
            gap_id = "usage_gap:" + stable_hash_json({"service": service, "status": organ.get("machine_usage_status")}, length=16)
            node(gap_id, "usage_gap", service, owner_surface="abyss-stack", reason=organ.get("usage_gap"), status=organ.get("machine_usage_status"))
            edge(sid, gap_id, "has_unexhausted_potential")
    for model in nested_get(working_stack, ["model_roots", "models"]) or []:
        if not isinstance(model, dict):
            continue
        model_id = "model_root:" + stable_hash_json(model.get("relative_path"), length=16)
        node(model_id, "model_root", str(model.get("relative_path") or "model-root"), owner_surface="abyss-stack", tags=model.get("tags"), service_candidates=model.get("service_candidates"))
        for service in model.get("service_candidates", []) if isinstance(model.get("service_candidates"), list) else []:
            edge("service:" + str(service), model_id, "uses_or_serves_model_root")
    edge("service:rag-api", "service:qdrant", "uses_vector_store")
    edge("service:rag-api", "service:rerank-api", "uses_reranker")
    edge("service:rag-api", "service:route-api", "uses_routes")
    edge("service:rag-api", "service:langchain-api", "uses_agent_runtime")
    edge("service:langchain-api", "service:llama-cpp", "uses_llm_runtime")
    edge("service:langchain-api", "service:ovms", "uses_embedding_runtime")
    edge("service:rerank-api", "service:ovms", "uses_model_server")
    edge("service:prometheus", "service:cadvisor", "scrapes_container_metrics")
    overlay_id = "overlay:memory-space"
    node(
        overlay_id,
        "memory_space_overlay",
        "memory/space overlay",
        owner_surface="abyss-machine",
        summary=memory_space.get("summary"),
        policy=memory_space.get("policy"),
    )
    edge(overlay_id, "service:rag-api", "bounded_retrieval_from")
    edge(overlay_id, "service:postgres", "semantic_backend_requirement")
    edge(overlay_id, "service:neo4j", "semantic_backend_requirement")
    edge(overlay_id, "service:embeddings", "semantic_capability")
    for gate in memory_space.get("freshness_gates", []):
        if not isinstance(gate, dict):
            continue
        gid = "freshness_gate:" + str(gate.get("gate_id"))
        node(
            gid,
            "freshness_gate",
            str(gate.get("title") or gate.get("gate_id")),
            status=gate.get("status"),
            blocks_deep_reasoning=gate.get("blocks_deep_reasoning"),
            maintenance_route=gate.get("maintenance_route"),
            owner_surface="abyss-machine",
        )
        edge(overlay_id, gid, "requires_freshness_gate")
        for ref in gate.get("evidence_refs", []) if isinstance(gate.get("evidence_refs"), list) else []:
            if not isinstance(ref, dict) or not ref.get("path"):
                continue
            artifact_id = "artifact:" + stable_hash_json(ref.get("path"), length=16)
            node(artifact_id, "artifact", str(ref.get("path")), owner_surface="abyss-machine", schema=ref.get("schema"), truth_level=ref.get("truth_level"))
            edge(gid, artifact_id, "checks_artifact", evidence_refs=[ref])
    for packet in memory_space.get("retrieval_packets", []):
        if not isinstance(packet, dict):
            continue
        pid = "retrieval_packet:" + str(packet.get("packet_entry_id") or stable_hash_json(packet, length=16))
        node(pid, "retrieval_packet", str(packet.get("label") or packet.get("packet_entry_id")), axis=packet.get("axis"), owner_surface=packet.get("owner_route"), truth_status=packet.get("truth_status"))
        edge(overlay_id, pid, "uses_bounded_retrieval", evidence_refs=packet.get("evidence_refs"))
        if packet.get("axis"):
            axis_id = "axis:" + str(packet.get("axis"))
            node(axis_id, "map_axis", str(packet.get("axis")), owner_surface="abyss-machine")
            edge(pid, axis_id, "from_axis")
    for axis in memory_space.get("spatial_overlays", []):
        if not isinstance(axis, dict):
            continue
        axis_id = "axis:" + str(axis.get("axis"))
        node(axis_id, "map_axis", str(axis.get("axis")), owner_surface="abyss-machine", entry_count=axis.get("entry_count"), bounded_entries=axis.get("bounded_entries"))
        edge(overlay_id, axis_id, "projects_axis")
    for backend in memory_space.get("stack_semantic_backends", []):
        if not isinstance(backend, dict):
            continue
        backend_id = "semantic_backend:" + str(backend.get("id"))
        service_id = "service:" + str(backend.get("id"))
        node(backend_id, "semantic_backend", str(backend.get("id")), owner_surface=backend.get("owner"), visible=backend.get("visible"), semantic_inventory=backend.get("semantic_inventory"), requirement_id=backend.get("requirement_id"))
        edge(service_id, backend_id, "has_semantic_inventory_state", evidence_refs=backend.get("evidence_refs"))
        edge(overlay_id, backend_id, "tracks_semantic_backend")
    for overlay_node in stack_handoff_overlay.get("spatial_nodes", []) if isinstance(stack_handoff_overlay.get("spatial_nodes"), list) else []:
        if not isinstance(overlay_node, dict):
            continue
        node(
            str(overlay_node.get("id") or ""),
            str(overlay_node.get("kind") or "stack_handoff"),
            str(overlay_node.get("label") or overlay_node.get("id")),
            **{key: value for key, value in overlay_node.items() if key not in {"id", "kind", "label"}},
        )
    for overlay_edge in stack_handoff_overlay.get("spatial_edges", []) if isinstance(stack_handoff_overlay.get("spatial_edges"), list) else []:
        if not isinstance(overlay_edge, dict):
            continue
        edge(
            str(overlay_edge.get("from") or ""),
            str(overlay_edge.get("to") or ""),
            str(overlay_edge.get("kind") or "stack_handoff"),
            **{key: value for key, value in overlay_edge.items() if key not in {"id", "from", "to", "kind"}},
        )
    if stack_handoff_overlay.get("spatial_nodes"):
        edge("overlay:stack-handoff", overlay_id, "intersects_memory_space")
    for event in events:
        if not isinstance(event, dict):
            continue
        event_id = str(event.get("event_id") or "")
        signal = str(event.get("signal") or "event")
        node(event_id, signal, event_id, severity=event.get("severity"), source=event.get("source"))
        resource = event.get("resource") if isinstance(event.get("resource"), dict) else {}
        context = event.get("context") if isinstance(event.get("context"), dict) else {}
        service = resource.get("service") or resource.get("job") or resource.get("container")
        if service:
            sid = "service:" + str(service)
            node(sid, "service", str(service), owner_surface=resource.get("owner_surface"))
            edge(event_id, sid, "observed_in", evidence_refs=event.get("evidence_refs"))
        movement_packet_id = context.get("movement_packet_id") or resource.get("movement_packet_id")
        working_stack_link_id = context.get("working_stack_link_id") or nested_get(event, ["fabric", "context_links", "links", "working_stack_link_id"])
        if movement_packet_id:
            mid = "movement_packet:" + str(movement_packet_id)
            node(
                mid,
                "movement_packet",
                str(movement_packet_id),
                owner_surface=resource.get("owner_surface"),
                service=service,
                selected_for_episode=resource.get("selected_for_episode"),
                selected_for_resident_reasoning=resource.get("selected_for_resident_reasoning"),
                observed_signal=resource.get("observed_signal") or event.get("signal"),
                observed_source=resource.get("observed_source") or event.get("source"),
            )
            edge(event_id, mid, "materializes_movement_packet", evidence_refs=event.get("evidence_refs"))
            if service:
                edge(mid, "service:" + str(service), "observes_service_movement", evidence_refs=event.get("evidence_refs"))
        if working_stack_link_id:
            lid = "working_stack_link:" + str(working_stack_link_id)
            node(lid, "working_stack_context_link", str(working_stack_link_id), owner_surface=resource.get("owner_surface") or "abyss-stack")
            edge(event_id, lid, "has_working_stack_context", evidence_refs=event.get("evidence_refs"))
            if movement_packet_id:
                edge("movement_packet:" + str(movement_packet_id), lid, "bound_to_working_stack_link", evidence_refs=event.get("evidence_refs"))
        if resource.get("container"):
            cid = "container:" + str(resource.get("container"))
            node(cid, "container", str(resource.get("container")), owner_surface=resource.get("owner_surface"), pid=resource.get("pid") or context.get("pid"))
            edge(cid, host_id, "runs_on")
            edge(event_id, cid, "observed_in")
            if resource.get("pid") or context.get("pid"):
                pid_value = resource.get("pid") or context.get("pid")
                pid_id = "process:" + str(pid_value)
                node(pid_id, "process", str(pid_value), owner_surface=resource.get("owner_surface"), service=service, container=resource.get("container"), pid_alive=resource.get("pid_alive") if "pid_alive" in resource else context.get("pid_alive"))
                edge(event_id, pid_id, "observed_process")
                edge(pid_id, cid, "process_of_container")
                edge(pid_id, host_id, "runs_on")
        if context.get("trace_id"):
            tid = "trace:" + str(context.get("trace_id"))
            node(tid, "trace_context", str(context.get("trace_id")))
            edge(event_id, tid, "same_trace")
        if context.get("synthetic_run_id"):
            rid = "synthetic_run:" + str(context.get("synthetic_run_id"))
            node(rid, "synthetic_probe", str(context.get("synthetic_run_id")))
            edge(event_id, rid, "observed_in")
        if resource.get("alert_fingerprint"):
            aid = "alert:" + str(resource.get("alert_fingerprint"))
            node(aid, "alert", str(resource.get("alertname") or resource.get("alert_fingerprint")))
            edge(event_id, aid, "observed_in")
    protected_writes = [
        edge_item for edge_item in edges.values()
        if edge_item.get("kind") == "writes" and storage_path_protection(Path(str(edge_item.get("to") or ""))).get("decision") == "deny"
    ]
    data = {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_spatial_graph_v1",
        "version": VERSION,
        "generated_at": now_iso(),
        "ok": not protected_writes and bool(nodes),
        "summary": {
            "nodes": len(nodes),
            "edges": len(edges),
            "protected_write_edges": len(protected_writes),
            "stack_nodes_present": all(("service:" + name) in nodes for name in ("prometheus", "grafana", "loki", "alloy", "route-api", "rag-api", "postgres", "neo4j")),
            "ai_nodes_present": all(("service:" + name) in nodes for name in ("warm-e2b-gemma4.spark", "ai-capabilities")),
            "memory_space_nodes": sum(1 for item in nodes.values() if item.get("kind") in {"memory_space_overlay", "freshness_gate", "retrieval_packet", "semantic_backend", "map_axis", "artifact"}),
            "memory_space_edges": sum(1 for item in edges.values() if str(item.get("kind") or "").startswith(("requires_freshness", "uses_bounded", "projects_axis", "tracks_semantic", "checks_artifact", "has_semantic"))),
            "freshness_gates": nested_get(memory_space, ["summary", "freshness_gates"]),
            "retrieval_packets": nested_get(memory_space, ["summary", "retrieval_packets"]),
            "stack_handoff_nodes": sum(1 for item in nodes.values() if item.get("kind") in {"stack_handoff_overlay", "stack_requirement", "stack_handoff_action", "stack_runbook_candidate"}),
            "stack_handoff_edges": sum(1 for item in edges.values() if str(item.get("kind") or "").startswith(("tracks_open_stack", "proposes_handoff", "has_runbook", "blocks_stack", "intersects_memory"))),
            "stack_handoff_markers": nested_get(stack_handoff_overlay, ["summary", "timeline_markers"]),
            "open_stack_requirements": nested_get(stack_handoff_overlay, ["summary", "open_stack_requirements"]),
            "working_stack_organs": nested_get(working_stack, ["summary", "organs"]),
            "working_stack_usage_gaps": nested_get(working_stack, ["summary", "usage_gaps"]),
            "working_stack_context_links": nested_get(working_stack, ["summary", "time_space_context_links"]),
            "movement_packet_nodes": sum(1 for item in nodes.values() if item.get("kind") == "movement_packet"),
            "movement_packet_edges": sum(1 for item in edges.values() if item.get("kind") in {"materializes_movement_packet", "observes_service_movement", "bound_to_working_stack_link"}),
            "working_stack_expected_live_present": all(("service:" + name) in nodes for name in SELF_AWARENESS_WORKING_STACK_EXPECTED_LIVE_SERVICES),
        },
        "memory_space_overlay": memory_space,
        "working_stack": {
            "schema": working_stack.get("schema"),
            "ok": working_stack.get("ok"),
            "status": working_stack.get("status"),
            "summary": working_stack.get("summary"),
            "latest": str(SELF_AWARENESS_WORKING_STACK_LATEST_PATH),
        },
        "stack_handoff_time_space_overlay": stack_handoff_overlay,
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "protected_write_edges": protected_writes,
        "query_examples": {
            "where_event": "select node by event_id then follow observed_in/runs_on/depends_on edges",
        },
        "tests": {
            "expected_stack_nodes": list(SELF_AWARENESS_WORKING_STACK_EXPECTED_LIVE_SERVICES),
            "expected_ai_nodes": ["warm-e2b-gemma4.spark", "ai-capabilities"],
            "protected_roots": "validated by self-awareness validate",
        },
    }
    if write_latest:
        errors = write_latest_and_history(data, SELF_AWARENESS_SPATIAL_GRAPH_LATEST_PATH, SELF_AWARENESS_SPATIAL_GRAPH_ROOT)
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def context(
    write_latest: bool = True,
    *,
    schema_prefix: str,
    version: str,
    paths: SelfAwarenessCausalPaths,
    runtime_port: SelfAwarenessCausalRuntimePort,
    refresh_port: SelfAwarenessCausalRefreshPort,
    contract_port: SelfAwarenessCausalContractPort,
    constants: SelfAwarenessCausalConstants,
) -> dict[str, Any]:
    SCHEMA_PREFIX = schema_prefix
    VERSION = version
    STACK_OBSERVABILITY_LATEST_PATH = paths.stack_observability_latest
    SELF_AWARENESS_CAPABILITIES_LATEST_PATH = paths.capabilities_latest
    SELF_AWARENESS_CONTEXT_LATEST_PATH = paths.context_latest
    SELF_AWARENESS_CONTEXT_ROOT = paths.context_root
    SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH = paths.requirement_probes_latest
    SELF_AWARENESS_TRACE_CONTEXT_LATEST_PATH = paths.trace_context_latest
    SELF_AWARENESS_UNBOUNDED_LABELS = constants.unbounded_labels
    load_latest_json = runtime_port.load_latest_json
    now_iso = runtime_port.now_iso
    write_latest_and_history = runtime_port.write_latest_and_history
    nested_get = self_awareness_contracts.nested_get
    self_awareness_bounded_context_packet = contract_port.bounded_context_packet
    self_awareness_brief_stack_handoff_action_map = contract_port.brief_stack_handoff_action_map
    self_awareness_load_events = refresh_port.load_events
    self_awareness_memory_space_overlay = contract_port.memory_space_overlay
    self_awareness_capabilities = refresh_port.capabilities
    self_awareness_requirement_probes = refresh_port.requirement_probes
    generated_at = now_iso()
    events = self_awareness_load_events(refresh=True)
    contexts: dict[str, dict[str, Any]] = {}
    degraded: list[dict[str, Any]] = []
    labels_latest = nested_get(load_latest_json(STACK_OBSERVABILITY_LATEST_PATH, f"{SCHEMA_PREFIX}_stack_observability_v1"), ["loki", "labels", "labels"]) or []
    forbidden_labels = sorted(set(str(label).lower() for label in labels_latest) & SELF_AWARENESS_UNBOUNDED_LABELS)
    def add_context_item(key: Any, event: dict[str, Any], context: dict[str, Any], *, index_kind: str | None = None, index_value: Any = None) -> None:
        if key in (None, ""):
            return
        event_id = event.get("event_id")
        fabric = event.get("fabric") if isinstance(event.get("fabric"), dict) else {}
        entity = fabric.get("entity") if isinstance(fabric.get("entity"), dict) else {}
        fabric_context_links = fabric.get("context_links") if isinstance(fabric.get("context_links"), dict) else {}
        correlation_keys = fabric_context_links.get("correlation_keys") if isinstance(fabric_context_links.get("correlation_keys"), list) else []
        service = entity.get("service") or nested_get(event, ["resource", "service"]) or nested_get(event, ["resource", "job"])
        context_payload = dict(context)
        resource = event.get("resource") if isinstance(event.get("resource"), dict) else {}
        for key_name in ("service", "container", "pid", "pid_alive", "route", "movement_packet_id"):
            if context_payload.get(key_name) in (None, "") and resource.get(key_name) not in (None, ""):
                context_payload[key_name] = resource.get(key_name)
        if context_payload.get("source_query") in (None, "") and event.get("source_query"):
            context_payload["source_query"] = event.get("source_query")
        if index_kind:
            context_payload["context_index_kind"] = index_kind
            context_payload["context_index_value"] = index_value
            context_payload["context_index_key"] = str(key)
        item = contexts.setdefault(str(key), {
            "key": str(key),
            "event_ids": [],
            "signals": {},
            "sources": {},
            "services": {},
            "correlation_keys": [],
            "context": context_payload,
        })
        if event_id not in item["event_ids"]:
            item["event_ids"].append(event_id)
        item["signals"][str(event.get("signal"))] = int(item["signals"].get(str(event.get("signal")), 0)) + 1
        item["sources"][str(event.get("source"))] = int(item["sources"].get(str(event.get("source")), 0)) + 1
        if service:
            item["services"][str(service)] = int(item["services"].get(str(service), 0)) + 1
        for correlation_key in correlation_keys:
            if correlation_key and correlation_key not in item["correlation_keys"] and len(item["correlation_keys"]) < 32:
                item["correlation_keys"].append(correlation_key)

    for event in events:
        context = event.get("context") if isinstance(event.get("context"), dict) else {}
        key = (
            context.get("trace_id")
            or context.get("traceparent")
            or context.get("synthetic_run_id")
            or context.get("alert_fingerprint")
            or context.get("working_stack_link_id")
        )
        add_context_item(key, event, context)
        for context_key in (
            "manual_collect_status",
            "scheduler_unit",
            "scheduler_scope",
            "scheduler_category",
            "host_service_unit",
            "host_service_scope",
            "host_service_category",
            "thread_id",
            "checkpoint_id",
            "run_id",
            "movement_packet_id",
            "session_id",
            "task_id",
            "goal_id",
        ):
            value = context.get(context_key)
            if value in (None, ""):
                continue
            add_context_item(f"{context_key}:{value}", event, context, index_kind=context_key, index_value=value)
    if not any("traceparent" in (item.get("context") or {}) for item in contexts.values()):
        degraded.append({"key": "traceparent", "reason": "no downstream log/readmodel traceparent found yet; context route is partial"})
    memory_space = self_awareness_memory_space_overlay(events)
    blocked_gates = [
        {"gate_id": gate.get("gate_id"), "status": gate.get("status"), "maintenance_route": gate.get("maintenance_route")}
        for gate in memory_space.get("freshness_gates", [])
        if isinstance(gate, dict) and gate.get("blocks_deep_reasoning")
    ]
    if blocked_gates:
        degraded.append({"key": "memory_space_freshness", "reason": "one or more freshness gates block deep reasoning", "gates": blocked_gates})
    capabilities = load_latest_json(SELF_AWARENESS_CAPABILITIES_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_capabilities_v1")
    capability_rows = capabilities.get("capabilities") if isinstance(capabilities.get("capabilities"), list) else []
    capability_ids = {str(item.get("id")) for item in capability_rows if isinstance(item, dict) and item.get("id")}
    if (
        capabilities.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_capabilities_v1"
        or not {"warm-e2b.resident-cognitive-worker", "host.governance-gates", "llm.escalation.routes"}.issubset(capability_ids)
    ):
        capabilities = self_awareness_capabilities(write_latest=True)
    requirement_probes = load_latest_json(SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_requirement_probes_v1")
    if requirement_probes.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_requirement_probes_v1":
        requirement_probes = self_awareness_requirement_probes(write_latest=True, capabilities=capabilities)
    stack_handoff_action_map = self_awareness_brief_stack_handoff_action_map(requirement_probes)
    trace_context_doc = load_latest_json(SELF_AWARENESS_TRACE_CONTEXT_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_trace_context_fallback_v1")
    context_packet = self_awareness_bounded_context_packet(
        contexts,
        memory_space,
        stack_handoff_action_map,
        capabilities,
        generated_at,
        trace_context_doc,
    )
    data = {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_context_v1",
        "version": VERSION,
        "generated_at": generated_at,
        "ok": not forbidden_labels and bool(context_packet.get("complete")),
        "summary": {
            "contexts": len(contexts),
            "trace_contexts": sum(1 for item in contexts.values() if (item.get("context") or {}).get("trace_id")),
            "working_stack_contexts": sum(1 for item in contexts.values() if (item.get("context") or {}).get("working_stack_link_id")),
            "scheduler_contexts": sum(1 for item in contexts.values() if str(item.get("key") or "").startswith("scheduler_")),
            "scheduler_unit_contexts": sum(1 for item in contexts.values() if str(item.get("key") or "").startswith("scheduler_unit:")),
            "scheduler_category_contexts": sum(1 for item in contexts.values() if str(item.get("key") or "").startswith("scheduler_category:")),
            "host_service_contexts": sum(1 for item in contexts.values() if str(item.get("key") or "").startswith("host_service_")),
            "host_service_unit_contexts": sum(1 for item in contexts.values() if str(item.get("key") or "").startswith("host_service_unit:")),
            "host_service_category_contexts": sum(1 for item in contexts.values() if str(item.get("key") or "").startswith("host_service_category:")),
            "manual_collect_contexts": sum(1 for item in contexts.values() if str(item.get("key") or "").startswith("manual_collect_status:")),
            "forbidden_loki_labels": forbidden_labels,
            "degraded": len(degraded),
            "memory_space": memory_space.get("summary"),
            "bounded_context_packet_complete": context_packet.get("complete"),
            "context_packet_sections": nested_get(context_packet, ["summary", "sections"]),
            "context_packet_stack_handoff_actions": nested_get(context_packet, ["summary", "stack_handoff_actions"]),
            "context_packet_open_stack_requirements": nested_get(context_packet, ["summary", "open_stack_requirements"]),
            "resident_worker_complete": nested_get(context_packet, ["summary", "resident_worker_complete"]),
            "governance_gates_complete": nested_get(context_packet, ["summary", "governance_gates_complete"]),
        },
        "contexts": sorted(contexts.values(), key=lambda item: str(item.get("key"))),
        "memory_space": memory_space,
        "stack_handoff_action_map": stack_handoff_action_map,
        "context_packet": context_packet,
        "degraded": degraded,
        "policy": {
            "trace_backend_required": False,
            "uses_w3c_traceparent": True,
            "unbounded_ids_as_loki_labels": False,
            "bounded_retrieval": True,
            "bounded_context_packet": True,
            "freshness_must_precede_reasoning": True,
            "raw_evidence_is_not_truth": True,
            "action_execution": False,
            "host_layer_mutates_stack": False,
        },
        "tests": {
            "traceparent": "synthetic probe generates W3C traceparent",
            "labels": "validator rejects trace/request/session IDs as Loki labels",
            "memory_space": "validator checks bounded retrieval packets and freshness gates",
            "context_packet": "validator checks bounded resident/operator packet, stack handoff, governance gates, and no stack mutation",
        },
    }
    if write_latest:
        errors = write_latest_and_history(data, SELF_AWARENESS_CONTEXT_LATEST_PATH, SELF_AWARENESS_CONTEXT_ROOT)
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def episodes(
    write_latest: bool = True,
    *,
    working_stack_doc: dict[str, Any] | None = None,
    schema_prefix: str,
    version: str,
    paths: SelfAwarenessCausalPaths,
    runtime_port: SelfAwarenessCausalRuntimePort,
    refresh_port: SelfAwarenessCausalRefreshPort,
    contract_port: SelfAwarenessCausalContractPort,
    constants: SelfAwarenessCausalConstants,
) -> dict[str, Any]:
    SCHEMA_PREFIX = schema_prefix
    VERSION = version
    SELF_AWARENESS_EPISODES_LATEST_PATH = paths.episodes_latest
    SELF_AWARENESS_EPISODES_ROOT = paths.episodes_root
    SELF_AWARENESS_EVENTS_LATEST_PATH = paths.events_latest
    SELF_AWARENESS_SPATIAL_GRAPH_LATEST_PATH = paths.spatial_graph_latest
    SELF_AWARENESS_TIMELINE_LATEST_PATH = paths.timeline_latest
    SELF_AWARENESS_WORKING_STACK_LATEST_PATH = paths.working_stack_latest
    load_latest_json = runtime_port.load_latest_json
    now_iso = runtime_port.now_iso
    write_latest_and_history = runtime_port.write_latest_and_history
    nested_get = self_awareness_contracts.nested_get
    stable_hash_json = self_awareness_contracts.stable_hash_json
    self_awareness_time_bucket = contract_port.time_bucket
    self_awareness_working_stack_gap_episodes = contract_port.working_stack_gap_episodes
    self_awareness_working_stack_inventory = refresh_port.working_stack_inventory

    timeline_document = refresh_port.timeline(write_latest=True)
    if isinstance(working_stack_doc, dict):
        graph = refresh_port.spatial_graph(write_latest=True, working_stack_doc=working_stack_doc, timeline_doc=timeline_document)
    else:
        graph = refresh_port.spatial_graph(write_latest=True)
    events = timeline_document.get("events") if isinstance(timeline_document.get("events"), list) else []
    by_group: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        resource = event.get("resource") if isinstance(event.get("resource"), dict) else {}
        if (
            event.get("truth_level") == "working_stack_movement_observation"
            and resource.get("selected_for_episode") is not True
        ):
            continue
        context = event.get("context") if isinstance(event.get("context"), dict) else {}
        group = (
            context.get("synthetic_run_id")
            or context.get("trace_id")
            or context.get("alert_fingerprint")
            or resource.get("alert_fingerprint")
            or resource.get("service")
            or self_awareness_time_bucket(event.get("event_time"))
        )
        by_group.setdefault(str(group), []).append(event)
    episodes: list[dict[str, Any]] = []
    for group, grouped_events in by_group.items():
        if not grouped_events:
            continue
        signals = set(str(event.get("signal")) for event in grouped_events)
        sources = set(str(event.get("source")) for event in grouped_events)
        confidence_score = 0.35
        reasons = ["time/resource adjacency is weak evidence"]
        if any((event.get("context") or {}).get("trace_id") for event in grouped_events if isinstance(event.get("context"), dict)):
            confidence_score += 0.25
            reasons.append("shared trace/request context present")
        if any((event.get("context") or {}).get("synthetic_run_id") for event in grouped_events if isinstance(event.get("context"), dict)):
            confidence_score += 0.2
            reasons.append("synthetic probe run id links full path")
        if "alert" in signals:
            confidence_score += 0.15
            reasons.append("alert lifecycle event present")
        if len({(event.get("resource") or {}).get("service") for event in grouped_events if isinstance(event.get("resource"), dict) and (event.get("resource") or {}).get("service")}) > 1:
            confidence_score += 0.1
            reasons.append("multiple spatial services involved")
        if "host-service" in sources:
            confidence_score += 0.15
            reasons.append("direct active systemd service state present")
        confidence_score = min(0.95, round(confidence_score, 2))
        event_ids = [str(event.get("event_id")) for event in grouped_events]
        affected_services = sorted(set(
            str((event.get("resource") or {}).get("service"))
            for event in grouped_events
            if isinstance(event.get("resource"), dict) and (event.get("resource") or {}).get("service")
        ))
        source_counts = dict(collections.Counter(str(event.get("source") or "unknown") for event in grouped_events))
        context_keys = sorted(set(
            str(key)
            for event in grouped_events
            for key in (
                [
                    f"{context_key}:{value}"
                    for context_key, value in (event.get("context") if isinstance(event.get("context"), dict) else {}).items()
                    if value not in (None, "")
                ]
                + [
                    str(item)
                    for item in (nested_get(event, ["fabric", "context_links", "correlation_keys"]) or [])
                    if item
                ]
            )
        ))[:40]
        host_service_categories = sorted(set(
            str(nested_get(event, ["context", "host_service_category"]))
            for event in grouped_events
            if nested_get(event, ["context", "host_service_category"])
        ))
        host_service_units = sorted(set(
            str(nested_get(event, ["context", "host_service_unit"]))
            for event in grouped_events
            if nested_get(event, ["context", "host_service_unit"])
        ))
        episode_kind = "host_service_state" if "host-service" in sources else "event_correlation"
        evidence_refs = []
        for event in grouped_events[:12]:
            evidence_refs.extend(event.get("evidence_refs") if isinstance(event.get("evidence_refs"), list) else [])
        episodes.append({
            "schema": f"{SCHEMA_PREFIX}_causal_episode_v1",
            "episode_id": "saepisode-" + stable_hash_json({"group": group, "event_ids": event_ids}, length=24),
            "episode_kind": episode_kind,
            "time_window": {
                "start": min(str(event.get("event_time") or "") for event in grouped_events),
                "end": max(str(event.get("event_time") or "") for event in grouped_events),
            },
            "affected_spatial_nodes": sorted(set(
                "service:" + str((event.get("resource") or {}).get("service"))
                for event in grouped_events
                if isinstance(event.get("resource"), dict) and (event.get("resource") or {}).get("service")
            )),
            "affected_services": affected_services,
            "involved_contexts": [
                event.get("context") for event in grouped_events
                if isinstance(event.get("context"), dict) and event.get("context")
            ][:12],
            "context_keys": context_keys,
            "primary_signals": sorted(signals),
            "sources": sorted(sources),
            "source_counts": source_counts,
            "host_service": {
                "units": host_service_units,
                "categories": host_service_categories,
                "policy": {
                    "read_only": True,
                    "host_layer_mutates_stack": False,
                    "executes_commands": False,
                    "automatic_remediation": False,
                },
            } if episode_kind == "host_service_state" else None,
            "suspected_cause_chain": [
                "candidate: correlated observations share context/resource/time window",
                "no root cause claim without stronger counterfactual evidence",
            ],
            "counter_evidence": [
                "time adjacency alone is weak",
                "missing trace backend means context evidence may be partial",
            ] if not any((event.get("context") or {}).get("trace_id") for event in grouped_events if isinstance(event.get("context"), dict)) else [
                "trace context present, but stack services may still omit downstream propagation"
            ],
            "confidence": {"score": confidence_score, "reasons": reasons},
            "open_questions": [] if confidence_score >= 0.7 else ["Need stronger trace/request context or direct dependency evidence."],
            "event_ids": event_ids,
            "reaction_candidate_refs": [],
            "evidence_refs": evidence_refs[:20],
            "truth_level": "inferred",
        })
    stack_handoff_overlay = timeline_document.get("stack_handoff_time_space_overlay") if isinstance(timeline_document.get("stack_handoff_time_space_overlay"), dict) else {}
    stack_handoff_markers = stack_handoff_overlay.get("timeline_markers") if isinstance(stack_handoff_overlay.get("timeline_markers"), list) else []
    stack_handoff_episode_ids: list[str] = []
    for marker in stack_handoff_markers:
        if not isinstance(marker, dict):
            continue
        requirement_id = str(marker.get("requirement_id") or "")
        if not requirement_id:
            continue
        marker_time = nested_get(marker, ["time", "observed_at"]) or timeline_document.get("generated_at") or now_iso()
        service_nodes = nested_get(marker, ["space", "service_nodes"])
        service_nodes = service_nodes if isinstance(service_nodes, list) else []
        affected_spatial_nodes = sorted(set([
            str(item) for item in service_nodes if item
        ] + [
            str(nested_get(marker, ["space", "requirement_node"]) or ""),
            str(nested_get(marker, ["space", "action_node"]) or ""),
        ]))
        affected_spatial_nodes = [item for item in affected_spatial_nodes if item]
        episode_id = "saepisode-stack-handoff-" + stable_hash_json({
            "requirement_id": requirement_id,
            "marker_id": marker.get("id"),
            "blockers": marker.get("closure_blocker_keys"),
        }, length=24)
        stack_handoff_episode_ids.append(episode_id)
        evidence_refs = marker.get("evidence_refs") if isinstance(marker.get("evidence_refs"), list) else []
        evidence_refs = [
            {"path": str(SELF_AWARENESS_TIMELINE_LATEST_PATH), "section": "stack_handoff_time_space_overlay", "requirement_id": requirement_id},
            {"path": str(SELF_AWARENESS_SPATIAL_GRAPH_LATEST_PATH), "node": nested_get(marker, ["space", "requirement_node"]), "requirement_id": requirement_id},
            *evidence_refs,
        ]
        episodes.append({
            "schema": f"{SCHEMA_PREFIX}_causal_episode_v1",
            "episode_id": episode_id,
            "episode_kind": "stack_handoff_blocker",
            "requirement_id": requirement_id,
            "stack_handoff_marker_id": marker.get("id"),
            "owner_route": marker.get("owner_route") or "abyss-stack",
            "time_window": {
                "start": marker_time,
                "end": marker_time,
                "bucket": nested_get(marker, ["time", "bucket"]),
            },
            "affected_spatial_nodes": affected_spatial_nodes,
            "involved_contexts": [{
                "requirement_id": requirement_id,
                "closure_blocker_keys": marker.get("closure_blocker_keys"),
                "priority_class": marker.get("priority_class"),
                "owner_route": marker.get("owner_route") or "abyss-stack",
            }],
            "primary_signals": ["stack_handoff", "requirement_probe", "spatial_graph"],
            "sources": ["self_awareness_requirement_probes", "self_awareness_timeline", "self_awareness_spatial_graph"],
            "suspected_cause_chain": [
                "candidate: open stack-owned requirement blocks full self-awareness coverage",
                "candidate: affected stack services are linked by time-space overlay, not by a root-cause claim",
                "owner-routed stack work is required before this blocker can close",
            ],
            "counter_evidence": [
                "open stack handoff is a capability gap, not proof of a runtime incident",
                "abyss-machine has not mutated stack state and does not execute the runbook",
                "closure requires stack-owned route evidence plus machine verifier success",
            ],
            "confidence": {
                "score": 0.68,
                "reasons": [
                    "stack handoff marker has closure blockers, affected services, runbook candidate, and verifier commands",
                    "truth remains handoff_candidate until stack-owned route closes the requirement",
                ],
            },
            "open_questions": [
                "Which stack-owned route or bounded export will close this requirement?",
                "Which verifier command first proves the blocker is closed without exposing secrets?",
            ],
            "event_ids": [],
            "reaction_candidate_refs": [],
            "stack_handoff": {
                "marker": marker,
                "closure_blocker_keys": marker.get("closure_blocker_keys"),
                "runbook_candidate_id": marker.get("runbook_candidate_id"),
                "verifier_commands": marker.get("verifier_commands"),
                "safe_next_action": marker.get("safe_next_action"),
                "policy": marker.get("policy"),
            },
            "evidence_refs": evidence_refs[:40],
            "truth_level": "handoff_candidate",
            "policy": {
                "root_cause_claim": False,
                "handoff_only": True,
                "host_layer_mutates_stack": False,
                "executes_commands": False,
                "automatic_remediation": False,
            },
        })
    working_stack = load_latest_json(SELF_AWARENESS_WORKING_STACK_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_working_stack_inventory_v1")
    if working_stack.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_working_stack_inventory_v1":
        working_stack = self_awareness_working_stack_inventory(write_latest=True)
    working_stack_gap_episodes, working_stack_gap_episode_ids = self_awareness_working_stack_gap_episodes(
        working_stack=working_stack,
        events=events,
        generated_at=timeline_document.get("generated_at") or now_iso(),
    )
    episodes.extend(working_stack_gap_episodes)
    working_stack_movement_episode_ids: list[str] = []
    for event in events:
        if not isinstance(event, dict) or event.get("truth_level") != "working_stack_movement_observation":
            continue
        resource = event.get("resource") if isinstance(event.get("resource"), dict) else {}
        context = event.get("context") if isinstance(event.get("context"), dict) else {}
        if resource.get("selected_for_episode") is not True:
            continue
        service = str(resource.get("service") or "")
        movement_packet_id = str(resource.get("movement_packet_id") or context.get("movement_packet_id") or "")
        working_stack_link_id = str(context.get("working_stack_link_id") or "")
        event_id = str(event.get("event_id") or "")
        if not service or not movement_packet_id or not event_id:
            continue
        categories = [str(item) for item in (resource.get("movement_categories") if isinstance(resource.get("movement_categories"), list) else []) if item]
        degradation_reasons = [str(item) for item in (resource.get("degradation_reasons") if isinstance(resource.get("degradation_reasons"), list) else []) if item]
        episode_id = "saepisode-movement-" + stable_hash_json({
            "event_id": event_id,
            "service": service,
            "movement_packet_id": movement_packet_id,
            "working_stack_link_id": working_stack_link_id,
        }, length=24)
        working_stack_movement_episode_ids.append(episode_id)
        confidence_score = 0.62
        confidence_reasons = ["classifier selected this organ movement for causal follow-up"]
        if "state_change" in categories:
            confidence_score += 0.12
            confidence_reasons.append("state digest changed since previous movement packet")
        if degradation_reasons:
            confidence_score += 0.12
            confidence_reasons.append("degradation reason present: " + ",".join(degradation_reasons[:4]))
        if working_stack_link_id:
            confidence_score += 0.04
            confidence_reasons.append("working_stack_link_id binds time, service, and context")
        confidence_score = min(0.9, round(confidence_score, 2))
        evidence_refs = [
            {"path": str(SELF_AWARENESS_EVENTS_LATEST_PATH), "event_id": event_id, "movement_packet_id": movement_packet_id},
            {"path": str(SELF_AWARENESS_TIMELINE_LATEST_PATH), "event_id": event_id},
            {"path": str(SELF_AWARENESS_SPATIAL_GRAPH_LATEST_PATH), "nodes": ["service:" + service, "movement_packet:" + movement_packet_id, "working_stack_link:" + working_stack_link_id]},
            *(
                event.get("evidence_refs")
                if isinstance(event.get("evidence_refs"), list)
                else []
            ),
        ]
        episodes.append({
            "schema": f"{SCHEMA_PREFIX}_causal_episode_v1",
            "episode_id": episode_id,
            "episode_kind": "working_stack_movement",
            "service": service,
            "movement_packet_id": movement_packet_id,
            "working_stack_link_id": working_stack_link_id or None,
            "machine_usage_status": resource.get("machine_usage_status"),
            "time_window": {
                "start": event.get("event_time"),
                "end": event.get("event_time"),
                "bucket": self_awareness_time_bucket(event.get("event_time")),
            },
            "affected_spatial_nodes": [
                item for item in [
                    "service:" + service,
                    "movement_packet:" + movement_packet_id,
                    "working_stack_link:" + working_stack_link_id if working_stack_link_id else None,
                ]
                if item
            ],
            "affected_services": [service],
            "involved_contexts": [context],
            "context_keys": [
                item for item in [
                    "working_stack_link_id:" + working_stack_link_id if working_stack_link_id else None,
                    "movement_packet_id:" + movement_packet_id,
                ]
                if item
            ],
            "primary_signals": [str(event.get("signal") or "service"), "organ_movement"],
            "sources": [str(event.get("source") or "working-stack"), str(resource.get("observed_source") or "")],
            "movement_selection": {
                "categories": categories,
                "selected_reason": resource.get("selected_reason"),
                "degradation_reasons": degradation_reasons,
                "selected_for_resident_reasoning": resource.get("selected_for_resident_reasoning") is True,
            },
            "suspected_cause_chain": [
                "candidate: organ movement classifier selected this packet",
                "candidate: time/space/context link binds the movement to the working-stack service",
                "no remediation or root-cause claim without resident evidence review",
            ],
            "counter_evidence": [
                "working-stack inventory is a readmodel; underlying stack evidence must remain inspectable",
                "state change alone can be normal drift unless corroborated by metric/log/trace context",
            ],
            "confidence": {"score": confidence_score, "reasons": confidence_reasons},
            "open_questions": [
                "Which adjacent metric/log/trace/context evidence corroborates this movement?",
                "Does resident reasoning find contradiction or only a normal state transition?",
            ],
            "event_ids": [event_id],
            "reaction_candidate_refs": [],
            "evidence_refs": evidence_refs[:40],
            "truth_level": "candidate",
            "policy": {
                "root_cause_claim": False,
                "read_only": True,
                "host_layer_mutates_stack": False,
                "executes_commands": False,
                "automatic_remediation": False,
            },
        })
    episodes.sort(key=lambda item: (item.get("confidence") or {}).get("score", 0), reverse=True)
    host_service_episode_ids = [
        str(item.get("episode_id"))
        for item in episodes
        if item.get("episode_kind") == "host_service_state" and item.get("episode_id")
    ]
    data = {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_episodes_v1",
        "version": VERSION,
        "generated_at": now_iso(),
        "ok": bool(episodes),
        "summary": {
            "episodes": len(episodes),
            "events": len(events),
            "graph_nodes": nested_get(graph, ["summary", "nodes"]),
            "high_confidence": sum(1 for item in episodes if float((item.get("confidence") or {}).get("score") or 0) >= 0.7),
            "stack_handoff_episodes": len(stack_handoff_episode_ids),
            "working_stack_gap_episodes": len(working_stack_gap_episode_ids),
            "working_stack_movement_episodes": len(working_stack_movement_episode_ids),
            "host_service_episodes": len(host_service_episode_ids),
            "working_stack_usage_gaps": nested_get(working_stack, ["summary", "usage_gaps"]),
            "open_stack_requirements": nested_get(stack_handoff_overlay, ["summary", "open_stack_requirements"]),
        },
        "episodes": episodes,
        "stack_handoff_episode_ids": stack_handoff_episode_ids,
        "working_stack_gap_episode_ids": working_stack_gap_episode_ids,
        "working_stack_movement_episode_ids": working_stack_movement_episode_ids,
        "host_service_episode_ids": host_service_episode_ids,
        "policy": {
            "root_cause_claims_as_fact": False,
            "conservative_correlation": True,
            "stack_handoff_episodes_are_candidates": True,
            "working_stack_gap_episodes_are_candidates": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
        },
        "tests": {
            "synthetic_grouping": "probe run id groups request/metric/log/context/alert events",
            "unrelated_same_minute": "fixture self-test checks time-only correlation remains weak",
            "working_stack_gap": "organ-level usage gaps become non-mutating causal handoff candidates",
        },
    }
    if write_latest:
        errors = write_latest_and_history(data, SELF_AWARENESS_EPISODES_LATEST_PATH, SELF_AWARENESS_EPISODES_ROOT)
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data

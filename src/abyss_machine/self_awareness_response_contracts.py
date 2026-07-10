from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import self_awareness_contracts


DocumentPort = Callable[..., Any]


@dataclass(frozen=True)
class SelfAwarenessResponsePaths:
    activation_smoke_latest: Path
    investigate_latest: Path
    replay_latest: Path
    stack_closure_dossier_latest: Path
    probe_latest: Path
    alerts_latest: Path
    reactions_latest: Path
    responses_latest: Path
    episodes_latest: Path
    events_latest: Path
    spatial_graph_latest: Path
    working_stack_latest: Path
    process_container_latest: Path
    completion_audit_latest: Path
    requirement_probes_latest: Path
    timeline_latest: Path


@dataclass(frozen=True)
class SelfAwarenessResponseConfig:
    schema_prefix: str


@dataclass(frozen=True)
class SelfAwarenessResponseRuntimePort:
    load_latest_json: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessResponseContractPort:
    episode_body_trace: DocumentPort
    body_trace_complete: DocumentPort
    response_entity_event_document_context: DocumentPort
    response_entity_event_document_context_complete: DocumentPort
    stack_requirement_handoff_route: DocumentPort
    stack_requirement_handoff_route_complete: DocumentPort
    working_stack_activation_gap_route: DocumentPort
    working_stack_activation_gap_route_complete: DocumentPort
    working_stack_activation_smoke_row_complete: DocumentPort


def episode_response_contract(
    *,
    candidate_id: str,
    episode: dict[str, Any],
    source_event: dict[str, Any] | None = None,
    investigation: dict[str, Any] | None = None,
    replay: dict[str, Any] | None = None,
    context_doc: dict[str, Any] | None = None,
    completion_audit_doc: dict[str, Any] | None = None,
    paths: SelfAwarenessResponsePaths,
    config: SelfAwarenessResponseConfig,
    runtime_port: SelfAwarenessResponseRuntimePort,
    contract_port: SelfAwarenessResponseContractPort,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    SELF_AWARENESS_ACTIVATION_SMOKE_LATEST_PATH = paths.activation_smoke_latest
    SELF_AWARENESS_INVESTIGATE_LATEST_PATH = paths.investigate_latest
    SELF_AWARENESS_REPLAY_LATEST_PATH = paths.replay_latest
    SELF_AWARENESS_STACK_CLOSURE_DOSSIER_LATEST_PATH = paths.stack_closure_dossier_latest
    SELF_AWARENESS_PROBE_LATEST_PATH = paths.probe_latest
    SELF_AWARENESS_ALERTS_LATEST_PATH = paths.alerts_latest
    REACTIONS_LATEST_PATH = paths.reactions_latest
    RESPONSES_LATEST_PATH = paths.responses_latest
    SELF_AWARENESS_EPISODES_LATEST_PATH = paths.episodes_latest
    SELF_AWARENESS_EVENTS_LATEST_PATH = paths.events_latest
    SELF_AWARENESS_SPATIAL_GRAPH_LATEST_PATH = paths.spatial_graph_latest
    SELF_AWARENESS_WORKING_STACK_LATEST_PATH = paths.working_stack_latest
    PROCESS_CONTAINER_LATEST_PATH = paths.process_container_latest
    SELF_AWARENESS_COMPLETION_AUDIT_LATEST_PATH = paths.completion_audit_latest
    SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH = paths.requirement_probes_latest
    SELF_AWARENESS_TIMELINE_LATEST_PATH = paths.timeline_latest
    load_latest_json = runtime_port.load_latest_json
    nested_get = self_awareness_contracts.nested_get
    stable_hash_json = self_awareness_contracts.stable_hash_json
    self_awareness_episode_body_trace = contract_port.episode_body_trace
    self_awareness_body_trace_complete = contract_port.body_trace_complete
    self_awareness_response_entity_event_document_context = (
        contract_port.response_entity_event_document_context
    )
    self_awareness_stack_requirement_handoff_route = (
        contract_port.stack_requirement_handoff_route
    )
    self_awareness_working_stack_activation_gap_route = (
        contract_port.working_stack_activation_gap_route
    )
    self_awareness_working_stack_activation_smoke_row_complete = (
        contract_port.working_stack_activation_smoke_row_complete
    )
    source_event = source_event if isinstance(source_event, dict) else {}
    investigation = investigation if isinstance(investigation, dict) else {}
    replay = replay if isinstance(replay, dict) else {}
    episode_id = str(episode.get("episode_id") or "")
    event_ids = [str(item) for item in (episode.get("event_ids") if isinstance(episode.get("event_ids"), list) else []) if item]
    confidence = episode.get("confidence") if isinstance(episode.get("confidence"), dict) else {}
    affected_nodes = list(episode.get("affected_spatial_nodes") if isinstance(episode.get("affected_spatial_nodes"), list) else [])
    episode_kind = str(episode.get("episode_kind") or "")
    is_stack_handoff = episode_kind == "stack_handoff_blocker"
    is_working_stack_gap = episode_kind == "working_stack_usage_gap"
    is_working_stack_movement = episode_kind == "working_stack_movement"
    requirement_id = str(episode.get("requirement_id") or "")
    stack_handoff = episode.get("stack_handoff") if isinstance(episode.get("stack_handoff"), dict) else {}
    stack_marker = stack_handoff.get("marker") if isinstance(stack_handoff.get("marker"), dict) else {}
    stack_policy = stack_handoff.get("policy") if isinstance(stack_handoff.get("policy"), dict) else {}
    stack_safe_next = stack_handoff.get("safe_next_action") if isinstance(stack_handoff.get("safe_next_action"), dict) else {}
    stack_runbook_candidate = stack_marker.get("runbook_candidate") if isinstance(stack_marker.get("runbook_candidate"), dict) else {}
    stack_verifier_commands = [
        str(item) for item in (stack_handoff.get("verifier_commands") if isinstance(stack_handoff.get("verifier_commands"), list) else [])
        if item
    ]
    working_stack_gap = episode.get("working_stack_gap") if isinstance(episode.get("working_stack_gap"), dict) else {}
    stack_requirement_route: dict[str, Any] = {}
    activation_gap_route: dict[str, Any] = {}
    working_gap_safe_next = working_stack_gap.get("safe_next_action") if isinstance(working_stack_gap.get("safe_next_action"), dict) else {}
    working_gap_verifier_commands = [
        str(item) for item in (working_stack_gap.get("verifier_commands") if isinstance(working_stack_gap.get("verifier_commands"), list) else [])
        if item
    ]
    body_trace = self_awareness_episode_body_trace(
        episode=episode,
        source_event=source_event,
        context_doc=context_doc,
    )
    entity_event_document_context = self_awareness_response_entity_event_document_context(
        completion_audit_doc=completion_audit_doc,
        episode=episode,
        source_event=source_event,
        body_trace=body_trace,
    )
    episode_specific_evidence: dict[str, Any] = {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_response_episode_specific_evidence_v1",
        "episode_kind": episode_kind or "event_correlation",
        "source_kind": "latest_investigate_replay",
        "complete": False,
        "evidence_refs": [],
    }
    if is_working_stack_gap:
        service = str(working_stack_gap.get("service") or episode.get("service") or "")
        status = str(working_stack_gap.get("machine_usage_status") or "")
        activation_smoke_doc = load_latest_json(
            SELF_AWARENESS_ACTIVATION_SMOKE_LATEST_PATH,
            f"{SCHEMA_PREFIX}_self_awareness_working_stack_activation_smoke_v1",
        )
        activation_rows = activation_smoke_doc.get("rows") if isinstance(activation_smoke_doc.get("rows"), list) else []
        activation_row = next(
            (
                row for row in activation_rows
                if isinstance(row, dict)
                and (
                    str(row.get("episode_id") or "") == episode_id
                    or (
                        service
                        and str(row.get("service") or "") == service
                        and (not status or str(row.get("machine_usage_status") or "") == status)
                    )
                )
            ),
            {},
        )
        activation_packet = activation_row.get("stack_organ_use_packet") if isinstance(activation_row.get("stack_organ_use_packet"), dict) else {}
        activation_packet_gap = activation_packet.get("activation_gap") if isinstance(activation_packet.get("activation_gap"), dict) else {}
        activation_row_complete = self_awareness_working_stack_activation_smoke_row_complete(activation_row)
        movement_matrix_evidence_complete = bool(
            activation_row.get("row_kind") == "organ_movement"
            and activation_row_complete
            and activation_packet_gap.get("route_complete") is True
        )
        smoke_investigation = activation_row.get("investigation") if isinstance(activation_row.get("investigation"), dict) else {}
        smoke_replay = activation_row.get("replay") if isinstance(activation_row.get("replay"), dict) else {}
        smoke_thread_id = str(smoke_investigation.get("thread_id") or smoke_replay.get("thread_id") or "")
        smoke_investigation_matches = (
            bool(activation_row)
            and activation_row.get("complete") is True
            and smoke_investigation.get("ok") is True
            and smoke_investigation.get("selected_episode_matches") is True
            and str(smoke_investigation.get("selected_episode_id") or "") == episode_id
        )
        smoke_replay_matches = (
            bool(smoke_thread_id)
            and smoke_replay.get("ok") is True
            and smoke_replay.get("thread_matches") is True
            and smoke_replay.get("working_stack_gap_replayable") is True
            and smoke_replay.get("working_stack_gap_matches") is True
            and str(smoke_replay.get("thread_id") or "") == smoke_thread_id
        )
        if smoke_investigation_matches and smoke_replay_matches:
            investigation = {
                **investigation,
                "thread_id": smoke_thread_id,
                "selected_episode_id": episode_id,
                "source_kind": "activation_smoke_matrix",
                "summary": {
                    **(investigation.get("summary") if isinstance(investigation.get("summary"), dict) else {}),
                    "checkpoints": smoke_investigation.get("checkpoints"),
                    "graph_nodes": smoke_investigation.get("graph_nodes"),
                    "working_stack_gap_selected": True,
                    "working_stack_gap_service": service,
                    "working_stack_gap_status": status,
                    "working_stack_gap_complete": smoke_investigation.get("working_stack_gap_complete"),
                    "resident_worker_detail_complete": smoke_investigation.get("resident_worker_detail_complete"),
                    "resident_cognitive_packet_complete": smoke_investigation.get("resident_cognitive_packet_complete"),
                    "read_only_tools": smoke_investigation.get("read_only_tools"),
                    "hypothesis_tests": smoke_investigation.get("hypothesis_tests"),
                    "contradiction_notes": smoke_investigation.get("contradiction_notes"),
                },
            }
            replay = {
                **replay,
                "thread_id": smoke_thread_id,
                "ok": True,
                "source_kind": "activation_smoke_matrix",
                "summary": {
                    **(replay.get("summary") if isinstance(replay.get("summary"), dict) else {}),
                    "divergences": smoke_replay.get("divergences"),
                    "conclusion_diff_changed": False,
                    "working_stack_gap_selected": smoke_replay.get("working_stack_gap_selected"),
                    "working_stack_gap_replayable": smoke_replay.get("working_stack_gap_replayable"),
                    "working_stack_gap_service": service,
                    "working_stack_gap_status": status,
                    "resident_cognitive_replay_complete": smoke_replay.get("resident_cognitive_replay_complete"),
                    "resident_cognitive_read_only_tools": smoke_replay.get("resident_cognitive_read_only_tools"),
                    "resident_cognitive_hypothesis_tests": smoke_replay.get("resident_cognitive_hypothesis_tests"),
                    "resident_cognitive_contradiction_notes": smoke_replay.get("resident_cognitive_contradiction_notes"),
                },
            }
        episode_specific_evidence = {
            "schema": f"{SCHEMA_PREFIX}_self_awareness_response_episode_specific_evidence_v1",
            "episode_kind": episode_kind,
            "source_kind": "activation_smoke_matrix",
            "complete": bool((smoke_investigation_matches and smoke_replay_matches) or movement_matrix_evidence_complete),
            "service": service,
            "machine_usage_status": status,
            "episode_id": episode_id,
            "thread_id": smoke_thread_id or None,
            "activation_smoke_row_kind": activation_row.get("row_kind") if isinstance(activation_row, dict) else None,
            "activation_smoke_row_complete": activation_row_complete,
            "activation_gap_route_complete": activation_packet_gap.get("route_complete") if isinstance(activation_packet_gap, dict) else None,
            "movement_matrix_evidence_complete": movement_matrix_evidence_complete,
            "investigation_matches_episode": smoke_investigation_matches,
            "replay_matches_investigation": smoke_replay_matches,
            "policy": {
                "read_only": True,
                "host_layer_mutates_stack": False,
                "executes_commands": False,
                "source_latest_artifacts_may_be_overwritten": True,
            },
            "evidence_refs": [
                {"path": str(SELF_AWARENESS_ACTIVATION_SMOKE_LATEST_PATH), "service": service, "episode_id": episode_id},
                {"path": str(SELF_AWARENESS_INVESTIGATE_LATEST_PATH), "thread_id": smoke_thread_id or None, "source": "activation_smoke_matrix"},
                {"path": str(SELF_AWARENESS_REPLAY_LATEST_PATH), "thread_id": smoke_thread_id or None, "source": "activation_smoke_matrix"},
            ],
        }
        activation_gap_route = self_awareness_working_stack_activation_gap_route(
            working_stack_gap,
            episode_id=episode_id,
            activation_row=activation_row,
        )
    elif is_stack_handoff:
        stack_closure_dossier_doc = load_latest_json(
            SELF_AWARENESS_STACK_CLOSURE_DOSSIER_LATEST_PATH,
            f"{SCHEMA_PREFIX}_self_awareness_stack_closure_dossier_v1",
        )
        closure_packets = nested_get(stack_closure_dossier_doc, ["closure_acceptance_matrix", "packets"])
        closure_packets_list = closure_packets if isinstance(closure_packets, list) else []
        closure_packet = next(
            (
                packet for packet in closure_packets_list
                if isinstance(packet, dict) and str(packet.get("requirement_id") or "") == requirement_id
            ),
            {},
        )
        stack_replay = replay.get("stack_handoff_replay") if isinstance(replay.get("stack_handoff_replay"), dict) else {}
        open_requirement_ids = stack_replay.get("open_requirement_ids") if isinstance(stack_replay.get("open_requirement_ids"), list) else []
        stack_lineage_complete = (
            bool(requirement_id)
            and closure_packet.get("complete") is True
            and stack_replay.get("closure_readiness_replayable") is True
            and requirement_id in {str(item) for item in open_requirement_ids}
        )
        episode_specific_evidence = {
            "schema": f"{SCHEMA_PREFIX}_self_awareness_response_episode_specific_evidence_v1",
            "episode_kind": episode_kind,
            "source_kind": "stack_closure_dossier_and_stack_handoff_replay",
            "complete": bool(stack_lineage_complete),
            "requirement_id": requirement_id,
            "episode_id": episode_id,
            "closure_acceptance_complete": closure_packet.get("complete") if isinstance(closure_packet, dict) else None,
            "stack_handoff_replayable": stack_replay.get("closure_readiness_replayable"),
            "open_requirement_present_in_replay": requirement_id in {str(item) for item in open_requirement_ids},
            "policy": {
                "read_only": True,
                "host_layer_mutates_stack": False,
                "executes_commands": False,
                "handoff_only": True,
            },
            "evidence_refs": [
                {"path": str(SELF_AWARENESS_STACK_CLOSURE_DOSSIER_LATEST_PATH), "requirement_id": requirement_id, "section": "closure_acceptance_matrix"},
                {"path": str(SELF_AWARENESS_REPLAY_LATEST_PATH), "requirement_id": requirement_id, "section": "stack_handoff_replay"},
            ],
        }
        stack_requirement_route = self_awareness_stack_requirement_handoff_route(
            requirement_id,
            episode_id=episode_id,
            stack_handoff=stack_handoff,
            closure_packet=closure_packet,
            stack_replay=stack_replay,
        )
    elif not is_working_stack_movement:
        synthetic_run_id = str(nested_get(source_event, ["context", "synthetic_run_id"]) or "")
        if synthetic_run_id:
            probe_doc = load_latest_json(SELF_AWARENESS_PROBE_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_probe_v1")
            lineage_doc = probe_doc.get("e2e_lineage_proof") if isinstance(probe_doc.get("e2e_lineage_proof"), dict) else {}
            lineage_rows = lineage_doc.get("rows") if isinstance(lineage_doc.get("rows"), list) else []
            required_lineage_rows = {
                "alert",
                "langgraph_investigation",
                "replay",
                "reaction_candidate",
                "governed_response",
            }
            satisfied_rows = {
                str(row.get("id"))
                for row in lineage_rows
                if isinstance(row, dict)
                and row.get("satisfied") is True
                and str(row.get("id")) in required_lineage_rows
            }
            synthetic_lineage_complete = (
                probe_doc.get("ok") is True
                and str(probe_doc.get("run_id") or "") == synthetic_run_id
                and lineage_doc.get("ok") is True
                and required_lineage_rows.issubset(satisfied_rows)
                and nested_get(lineage_doc, ["summary", "missing_rows"]) == []
            )
            episode_specific_evidence = {
                "schema": f"{SCHEMA_PREFIX}_self_awareness_response_episode_specific_evidence_v1",
                "episode_kind": episode_kind or "event_correlation",
                "source_kind": "synthetic_probe_e2e_lineage",
                "complete": bool(synthetic_lineage_complete),
                "synthetic_run_id": synthetic_run_id,
                "probe_run_id": probe_doc.get("run_id"),
                "episode_id": episode_id,
                "required_lineage_rows": sorted(required_lineage_rows),
                "satisfied_lineage_rows": sorted(satisfied_rows),
                "policy": {
                    "read_only": True,
                    "host_layer_mutates_stack": False,
                    "executes_commands": False,
                    "actions_executed": False,
                },
                "evidence_refs": [
                    {"path": str(SELF_AWARENESS_PROBE_LATEST_PATH), "run_id": synthetic_run_id, "section": "e2e_lineage_proof"},
                    {"path": str(SELF_AWARENESS_ALERTS_LATEST_PATH), "event_id": source_event.get("event_id"), "section": "synthetic_alert"},
                    {"path": str(REACTIONS_LATEST_PATH), "run_id": synthetic_run_id, "section": "reaction_candidate"},
                    {"path": str(RESPONSES_LATEST_PATH), "run_id": synthetic_run_id, "section": "governed_response"},
                ],
            }
    investigation_matches = bool(episode_id and investigation.get("selected_episode_id") == episode_id)
    thread_id = str(investigation.get("thread_id") or "") if investigation_matches else ""
    replay_matches = bool(thread_id and replay.get("thread_id") == thread_id and replay.get("ok") is True)
    if is_working_stack_movement:
        movement_packet_id = str(episode.get("movement_packet_id") or nested_get(source_event, ["resource", "movement_packet_id"]) or "")
        movement_link_id = episode.get("working_stack_link_id") or nested_get(source_event, ["context", "working_stack_link_id"])
        movement_evidence_complete = bool(
            episode_id
            and movement_packet_id
            and (movement_link_id or source_event.get("event_id"))
            and self_awareness_body_trace_complete(body_trace)
        )
        episode_specific_evidence = {
            "schema": f"{SCHEMA_PREFIX}_self_awareness_response_episode_specific_evidence_v1",
            "episode_kind": episode_kind,
            "source_kind": "working_stack_movement_investigate_replay",
            "complete": bool((investigation_matches and replay_matches) or movement_evidence_complete),
            "episode_id": episode_id,
            "movement_packet_id": movement_packet_id or None,
            "working_stack_link_id": movement_link_id,
            "source_event_id": source_event.get("event_id"),
            "investigation_thread_id": thread_id or None,
            "replay_thread_id": replay.get("thread_id"),
            "movement_evidence_complete": movement_evidence_complete,
            "investigation_matches_episode": investigation_matches,
            "replay_matches_investigation": replay_matches,
            "policy": {
                "read_only": True,
                "host_layer_mutates_stack": False,
                "executes_commands": False,
                "actions_executed": False,
            },
            "evidence_refs": [
                {"path": str(SELF_AWARENESS_EPISODES_LATEST_PATH), "episode_id": episode_id, "movement_packet_id": movement_packet_id or None},
                {"path": str(SELF_AWARENESS_EVENTS_LATEST_PATH), "event_id": source_event.get("event_id"), "movement_packet_id": movement_packet_id or None},
                {"path": str(SELF_AWARENESS_INVESTIGATE_LATEST_PATH), "thread_id": thread_id or None, "episode_id": episode_id},
                {"path": str(SELF_AWARENESS_REPLAY_LATEST_PATH), "thread_id": replay.get("thread_id"), "episode_id": episode_id},
            ],
        }
    response_lineage_complete = bool(investigation_matches and replay_matches) or episode_specific_evidence.get("complete") is True
    response_lineage = {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_response_lineage_v1",
        "episode_kind": episode_kind or "event_correlation",
        "complete": response_lineage_complete,
        "latest_investigation_matches_episode": investigation_matches,
        "latest_replay_matches_investigation": replay_matches,
        "episode_specific_evidence_complete": episode_specific_evidence.get("complete") is True,
        "source_kind": episode_specific_evidence.get("source_kind") or "latest_investigate_replay",
        "evidence_refs": episode_specific_evidence.get("evidence_refs") if isinstance(episode_specific_evidence.get("evidence_refs"), list) else [],
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
        },
    }
    runbook_steps = [
        f"abyss-machine self-awareness investigate --episode-id {episode_id} --json" if episode_id else "abyss-machine self-awareness investigate --query latest --json",
        f"abyss-machine self-awareness replay --thread-id {thread_id} --json" if thread_id else "abyss-machine self-awareness replay --json",
        "abyss-machine self-awareness brief --json",
        "abyss-machine reactions --json",
        "abyss-machine responses --json",
        "abyss-machine responses validate --json",
    ]
    if is_stack_handoff:
        runbook_steps = list(dict.fromkeys([
            str(stack_safe_next.get("command") or "abyss-machine self-awareness export --json"),
            *stack_verifier_commands,
            f"abyss-machine self-awareness investigate --episode-id {episode_id} --json" if episode_id else "abyss-machine self-awareness investigate --query latest --json",
            f"abyss-machine self-awareness replay --thread-id {thread_id} --json" if thread_id else "abyss-machine self-awareness replay --json",
            "abyss-machine reactions --json",
            "abyss-machine responses --json",
            "abyss-machine responses validate --json",
        ]))
    elif is_working_stack_gap:
        runbook_steps = list(dict.fromkeys([
            str(working_gap_safe_next.get("command") or "abyss-machine self-awareness working-stack --json"),
            *working_gap_verifier_commands,
            f"abyss-machine self-awareness investigate --episode-id {episode_id} --json" if episode_id else "abyss-machine self-awareness investigate --query latest --json",
            f"abyss-machine self-awareness replay --thread-id {thread_id} --json" if thread_id else "abyss-machine self-awareness replay --json",
            "abyss-machine reactions --json",
            "abyss-machine responses --json",
            "abyss-machine responses validate --json",
        ]))
    acceptance_verifiers = (
        stack_verifier_commands
        if is_stack_handoff and stack_verifier_commands
        else working_gap_verifier_commands
        if is_working_stack_gap and working_gap_verifier_commands
        else [
            "abyss-machine self-awareness validate --json",
            "abyss-machine reactions validate --json",
            "abyss-machine responses validate --json",
        ]
    )
    evidence_refs = [
        {"path": str(SELF_AWARENESS_EPISODES_LATEST_PATH), "episode_id": episode_id},
        {"path": str(SELF_AWARENESS_EVENTS_LATEST_PATH), "event_id": source_event.get("event_id")},
        {"path": str(SELF_AWARENESS_INVESTIGATE_LATEST_PATH), "thread_id": investigation.get("thread_id"), "matches_episode": investigation_matches},
        {"path": str(SELF_AWARENESS_REPLAY_LATEST_PATH), "thread_id": replay.get("thread_id"), "matches_investigation": replay_matches},
        {"path": str(SELF_AWARENESS_COMPLETION_AUDIT_LATEST_PATH), "section": "entity_event_document_map", "complete": entity_event_document_context.get("complete")},
    ]
    evidence_refs.extend(episode.get("evidence_refs") if isinstance(episode.get("evidence_refs"), list) else [])
    if source_event.get("evidence_refs"):
        evidence_refs.extend(source_event.get("evidence_refs") if isinstance(source_event.get("evidence_refs"), list) else [])
    if is_stack_handoff:
        evidence_refs.extend([
            {"path": str(SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH), "requirement_id": requirement_id},
            {"path": str(SELF_AWARENESS_TIMELINE_LATEST_PATH), "marker_id": episode.get("stack_handoff_marker_id")},
            {"path": str(SELF_AWARENESS_SPATIAL_GRAPH_LATEST_PATH), "requirement_id": requirement_id},
        ])
    elif is_working_stack_gap:
        evidence_refs.extend([
            {"path": str(SELF_AWARENESS_WORKING_STACK_LATEST_PATH), "service": working_stack_gap.get("service")},
            {"path": str(SELF_AWARENESS_EVENTS_LATEST_PATH), "event_ids": event_ids[:8]},
            {"path": str(SELF_AWARENESS_SPATIAL_GRAPH_LATEST_PATH), "nodes": affected_nodes[:8]},
            {"path": str(PROCESS_CONTAINER_LATEST_PATH), "service": working_stack_gap.get("service"), "container": working_stack_gap.get("container")},
        ])
    risks = [
        "episode is inferred evidence, not root-cause fact",
        "stack trace/database/langgraph read routes may still be open requirements",
        "manual follow-up command may refresh machine-owned readmodels",
    ]
    rollback_steps = [
        "discard the generated reaction/response candidate if it is not useful",
        "rerun abyss-machine self-awareness alerts --json",
        "rerun abyss-machine reactions --json",
        "rerun abyss-machine responses --json",
    ]
    runbook_owner_route = "abyss-machine:self-awareness"
    machine_action = "route_for_owner_review_only"
    if is_stack_handoff:
        risks = [
            "stack-owned capability gap remains open until the owning stack route closes it",
            "episode is a handoff candidate, not proof of a runtime incident or root cause",
            "machine verifier commands may refresh host-owned readmodels but must not execute stack changes",
        ]
        rollback_steps = [
            "discard the generated stack handoff reaction/response candidate if it is not useful",
            "rerun abyss-machine self-awareness episodes --json",
            "rerun abyss-machine self-awareness alerts --json",
            "rerun abyss-machine reactions --json",
            "rerun abyss-machine responses --json",
        ]
        runbook_owner_route = "abyss-stack"
        machine_action = "handoff_for_stack_owner_review_only"
    elif is_working_stack_gap:
        service = str(working_stack_gap.get("service") or episode.get("service") or "unknown")
        status = str(working_stack_gap.get("machine_usage_status") or "unknown")
        risks = [
            f"working stack organ {service} remains a usage-gap candidate until bounded smoke proves deep use",
            "episode is a handoff candidate, not proof of a root cause or authorization to mutate stack state",
            "machine verifier commands may refresh host-owned readmodels but must not execute stack changes",
        ]
        rollback_steps = [
            "discard the generated working-stack gap reaction/response candidate if it is not useful",
            "rerun abyss-machine self-awareness working-stack --json",
            "rerun abyss-machine self-awareness episodes --json",
            "rerun abyss-machine self-awareness alerts --json",
            "rerun abyss-machine reactions --json",
            "rerun abyss-machine responses --json",
        ]
        runbook_owner_route = "abyss-stack"
        machine_action = f"handoff_for_stack_owner_review_only:{status}"
    return {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_response_contract_v1",
        "id": "sa-response-contract-" + stable_hash_json({"candidate": candidate_id, "episode": episode_id, "events": event_ids}, length=20),
        "candidate_id": candidate_id,
        "validated_episode": {
            "episode_id": episode_id,
            "schema": episode.get("schema"),
            "episode_kind": episode_kind or "event_correlation",
            "requirement_id": requirement_id or None,
            "owner_route": episode.get("owner_route"),
            "stack_handoff_marker_id": episode.get("stack_handoff_marker_id"),
            "time_window": episode.get("time_window") if isinstance(episode.get("time_window"), dict) else {},
            "event_ids": event_ids,
            "primary_signals": list(episode.get("primary_signals") if isinstance(episode.get("primary_signals"), list) else []),
            "affected_spatial_nodes": affected_nodes,
            "confidence": confidence,
            "truth_level": episode.get("truth_level") or "inferred",
            "source_latest": str(SELF_AWARENESS_EPISODES_LATEST_PATH),
            "validated_by": "abyss-machine self-awareness episodes + validate",
        },
        "source_event": {
            "event_id": source_event.get("event_id"),
            "signal": source_event.get("signal"),
            "source": source_event.get("source"),
            "severity": source_event.get("severity"),
            "resource": source_event.get("resource") if isinstance(source_event.get("resource"), dict) else {},
            "context": source_event.get("context") if isinstance(source_event.get("context"), dict) else {},
        },
        "investigation": {
            "thread_id": thread_id or investigation.get("thread_id"),
            "selected_episode_id": investigation.get("selected_episode_id"),
            "matches_episode": investigation_matches,
            "summary": investigation.get("summary") if isinstance(investigation.get("summary"), dict) else {},
            "command": f"abyss-machine self-awareness investigate --episode-id {episode_id} --json" if episode_id else "abyss-machine self-awareness investigate --query latest --json",
            "latest_path": str(SELF_AWARENESS_INVESTIGATE_LATEST_PATH),
        },
        "replay": {
            "thread_id": replay.get("thread_id"),
            "matches_investigation": replay_matches,
            "ok": replay.get("ok"),
            "divergences": nested_get(replay, ["summary", "divergences"]),
            "conclusion_diff_changed": nested_get(replay, ["summary", "conclusion_diff_changed"]),
            "command": f"abyss-machine self-awareness replay --thread-id {thread_id} --json" if thread_id else "abyss-machine self-awareness replay --json",
            "latest_path": str(SELF_AWARENESS_REPLAY_LATEST_PATH),
        },
        "episode_specific_evidence": episode_specific_evidence,
        "response_lineage": response_lineage,
        "body_trace": body_trace,
        "entity_event_document_context": entity_event_document_context,
        "risk": {
            "level": "review",
            "risks": risks,
            "claim_without_evidence": False,
        },
        "blast_radius": {
            "kind": "readmodel_only",
            "affected_surfaces": sorted(set([
                "/var/lib/abyss-machine/self-awareness",
                "/var/lib/abyss-machine/reactions",
                "/var/lib/abyss-machine/responses",
                *[str(item) for item in affected_nodes],
            ])),
            "stack_mutation": False,
            "project_repo_mutation": False,
        },
        "rollback": {
            "kind": "discard_regenerate_readmodels",
            "steps": rollback_steps,
            "stack_rollback_required": False,
        },
        "runbook_candidate": {
            "schema": f"{SCHEMA_PREFIX}_self_awareness_response_runbook_candidate_v1",
            "owner_route": runbook_owner_route,
            "machine_action": machine_action,
            "requirement_id": requirement_id or None,
            "closure_blocker_keys": (
                stack_handoff.get("closure_blocker_keys")
                if is_stack_handoff
                else working_stack_gap.get("closure_blocker_keys")
                if is_working_stack_gap
                else []
            ),
            "safe_next_action": (
                stack_safe_next
                if is_stack_handoff
                else working_gap_safe_next
                if is_working_stack_gap
                else {}
            ),
            "stack_runbook_candidate": stack_runbook_candidate if is_stack_handoff else {},
            "verifier_commands": (
                stack_verifier_commands
                if is_stack_handoff
                else working_gap_verifier_commands
                if is_working_stack_gap
                else []
            ),
            "steps": runbook_steps,
            "acceptance_verifiers": acceptance_verifiers,
            "operator_approval_required": True,
            "host_layer_mutates_stack": False,
            "machine_executes_stack_change": False,
            "automatic_execution": False,
        },
        "stack_handoff": {
            "requirement_id": requirement_id,
            "marker_id": episode.get("stack_handoff_marker_id"),
            "closure_blocker_keys": stack_handoff.get("closure_blocker_keys"),
            "runbook_candidate_id": stack_handoff.get("runbook_candidate_id"),
            "safe_next_action": stack_safe_next,
            "verifier_commands": stack_verifier_commands,
            "policy": stack_policy,
        } if is_stack_handoff else {},
        "stack_requirement_route": stack_requirement_route if is_stack_handoff else {},
        "working_stack_gap": {
            "service": working_stack_gap.get("service"),
            "owner_route": working_stack_gap.get("owner_route") or "abyss-stack",
            "working_stack_link_id": working_stack_gap.get("working_stack_link_id"),
            "machine_usage_status": working_stack_gap.get("machine_usage_status"),
            "usage_gap": working_stack_gap.get("usage_gap"),
            "closure_blocker_keys": working_stack_gap.get("closure_blocker_keys"),
            "safe_next_action": working_gap_safe_next,
            "verifier_commands": working_gap_verifier_commands,
            "policy": working_stack_gap.get("policy") if isinstance(working_stack_gap.get("policy"), dict) else {},
        } if is_working_stack_gap else {},
        "activation_gap_route": activation_gap_route if is_working_stack_gap else {},
        "approval": {
            "required": True,
            "route": "abyss-machine:self-awareness",
            "human_approval_before_mutation": True,
        },
        "policy": {
            "read_model": True,
            "automatic_action": False,
            "automatic_response": False,
            "executes_commands": False,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "candidate_output_is_owner_truth": False,
            "claims_require_evidence_refs": True,
        },
        "evidence_refs": evidence_refs[:40],
    }


def response_contract_complete(
    contract: dict[str, Any],
    *,
    config: SelfAwarenessResponseConfig,
    contract_port: SelfAwarenessResponseContractPort,
) -> bool:
    nested_get = self_awareness_contracts.nested_get
    if not isinstance(contract, dict):
        return False
    episode_kind = str(nested_get(contract, ["validated_episode", "episode_kind"]) or "")
    activation_gap_route_ok = (
        episode_kind != "working_stack_usage_gap"
        or contract_port.working_stack_activation_gap_route_complete(
            contract.get("activation_gap_route")
        )
    )
    stack_requirement_route_ok = (
        episode_kind != "stack_handoff_blocker"
        or contract_port.stack_requirement_handoff_route_complete(
            contract.get("stack_requirement_route")
        )
    )
    return (
        contract.get("schema")
        == f"{config.schema_prefix}_self_awareness_response_contract_v1"
        and bool(nested_get(contract, ["validated_episode", "episode_id"]))
        and isinstance(nested_get(contract, ["validated_episode", "event_ids"]), list)
        and bool(nested_get(contract, ["investigation", "command"]))
        and bool(nested_get(contract, ["replay", "command"]))
        and contract_port.body_trace_complete(contract.get("body_trace"))
        and contract_port.response_entity_event_document_context_complete(
            contract.get("entity_event_document_context")
        )
        and nested_get(contract, ["response_lineage", "complete"]) is True
        and nested_get(contract, ["response_lineage", "schema"])
        == f"{config.schema_prefix}_self_awareness_response_lineage_v1"
        and bool(nested_get(contract, ["risk", "risks"]))
        and bool(nested_get(contract, ["blast_radius", "affected_surfaces"]))
        and bool(nested_get(contract, ["rollback", "steps"]))
        and nested_get(contract, ["runbook_candidate", "schema"])
        == f"{config.schema_prefix}_self_awareness_response_runbook_candidate_v1"
        and bool(nested_get(contract, ["runbook_candidate", "steps"]))
        and bool(nested_get(contract, ["runbook_candidate", "acceptance_verifiers"]))
        and nested_get(contract, ["approval", "required"]) is True
        and nested_get(contract, ["policy", "automatic_action"]) is False
        and nested_get(contract, ["policy", "automatic_response"]) is False
        and nested_get(contract, ["policy", "executes_commands"]) is False
        and nested_get(contract, ["policy", "host_layer_mutates_stack"]) is False
        and nested_get(contract, ["policy", "writes_project_roots"]) is False
        and activation_gap_route_ok
        and stack_requirement_route_ok
        and bool(contract.get("evidence_refs"))
    )

def reaction_candidate_response_depth_complete(
    candidate: dict[str, Any],
    *,
    config: SelfAwarenessResponseConfig,
    contract_port: SelfAwarenessResponseContractPort,
) -> bool:
    nested_get = self_awareness_contracts.nested_get
    if not isinstance(candidate, dict):
        return False
    contract = (
        candidate.get("response_contract")
        if isinstance(candidate.get("response_contract"), dict)
        else {}
    )
    return (
        candidate.get("schema") == f"{config.schema_prefix}_reaction_candidate_v1"
        and candidate.get("category") == "self-awareness"
        and candidate.get("automatic") is False
        and candidate.get("owner_route") == "abyss-machine:self-awareness"
        and bool(
            candidate.get("episode_id")
            or nested_get(contract, ["validated_episode", "episode_id"])
        )
        and candidate.get("risk") == contract.get("risk")
        and candidate.get("blast_radius") == contract.get("blast_radius")
        and candidate.get("rollback") == contract.get("rollback")
        and candidate.get("runbook_candidate") == contract.get("runbook_candidate")
        and candidate.get("body_trace") == contract.get("body_trace")
        and candidate.get("entity_event_document_context")
        == contract.get("entity_event_document_context")
        and response_contract_complete(
            contract,
            config=config,
            contract_port=contract_port,
        )
    )


def response_route_depth_complete(
    route: dict[str, Any],
    *,
    config: SelfAwarenessResponseConfig,
    contract_port: SelfAwarenessResponseContractPort,
) -> bool:
    nested_get = self_awareness_contracts.nested_get
    if not isinstance(route, dict):
        return False
    contract = (
        route.get("response_contract")
        if isinstance(route.get("response_contract"), dict)
        else {}
    )
    return (
        route.get("schema") == f"{config.schema_prefix}_response_route_v1"
        and route.get("category") == "self-awareness"
        and route.get("automatic") is False
        and route.get("executes") is False
        and nested_get(route, ["approval", "required"]) is True
        and nested_get(route, ["policy", "automatic_response"]) is False
        and nested_get(route, ["policy", "executes_commands"]) is False
        and nested_get(route, ["policy", "host_layer_mutates_stack"]) is False
        and route.get("risk") == contract.get("risk")
        and route.get("blast_radius") == contract.get("blast_radius")
        and route.get("rollback") == contract.get("rollback")
        and route.get("runbook_candidate") == contract.get("runbook_candidate")
        and route.get("validated_episode") == contract.get("validated_episode")
        and route.get("body_trace") == contract.get("body_trace")
        and route.get("entity_event_document_context")
        == contract.get("entity_event_document_context")
        and response_contract_complete(
            contract,
            config=config,
            contract_port=contract_port,
        )
    )

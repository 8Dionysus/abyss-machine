from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import runtime_evidence_contracts
from . import self_awareness_contracts


DocumentPort = Callable[..., Any]


@dataclass(frozen=True)
class SelfAwarenessAlertPaths:
    context_latest: Path
    episodes_latest: Path
    requirement_probes_latest: Path
    working_stack_latest: Path
    investigate_latest: Path
    replay_latest: Path
    events_latest: Path
    spatial_graph_latest: Path
    timeline_latest: Path
    alerts_latest: Path
    alerts_root: Path
    reactions_latest: Path


@dataclass(frozen=True)
class SelfAwarenessAlertConfig:
    schema_prefix: str
    version: str


@dataclass(frozen=True)
class SelfAwarenessAlertRuntimePort:
    load_latest_json: DocumentPort
    now_iso: DocumentPort
    write_latest_and_history: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessAlertRefreshPort:
    load_events: DocumentPort
    context: DocumentPort
    episodes: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessAlertContractPort:
    episode_response_contract: DocumentPort
    reaction_candidate_response_depth_complete: DocumentPort
    body_trace_complete: DocumentPort


def alerts(
    write_latest: bool = True,
    *,
    paths: SelfAwarenessAlertPaths,
    config: SelfAwarenessAlertConfig,
    runtime_port: SelfAwarenessAlertRuntimePort,
    refresh_port: SelfAwarenessAlertRefreshPort,
    contract_port: SelfAwarenessAlertContractPort,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    VERSION = config.version
    SELF_AWARENESS_CONTEXT_LATEST_PATH = paths.context_latest
    SELF_AWARENESS_EPISODES_LATEST_PATH = paths.episodes_latest
    SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH = paths.requirement_probes_latest
    SELF_AWARENESS_WORKING_STACK_LATEST_PATH = paths.working_stack_latest
    SELF_AWARENESS_INVESTIGATE_LATEST_PATH = paths.investigate_latest
    SELF_AWARENESS_REPLAY_LATEST_PATH = paths.replay_latest
    SELF_AWARENESS_EVENTS_LATEST_PATH = paths.events_latest
    SELF_AWARENESS_SPATIAL_GRAPH_LATEST_PATH = paths.spatial_graph_latest
    SELF_AWARENESS_TIMELINE_LATEST_PATH = paths.timeline_latest
    SELF_AWARENESS_ALERTS_LATEST_PATH = paths.alerts_latest
    SELF_AWARENESS_ALERTS_ROOT = paths.alerts_root
    REACTIONS_LATEST_PATH = paths.reactions_latest
    load_latest_json = runtime_port.load_latest_json
    now_iso = runtime_port.now_iso
    write_latest_and_history = runtime_port.write_latest_and_history
    self_awareness_load_events = refresh_port.load_events
    self_awareness_context = refresh_port.context
    self_awareness_episodes = refresh_port.episodes
    self_awareness_episode_response_contract = contract_port.episode_response_contract
    self_awareness_reaction_candidate_response_depth_complete = (
        contract_port.reaction_candidate_response_depth_complete
    )
    self_awareness_body_trace_complete = contract_port.body_trace_complete
    nested_get = self_awareness_contracts.nested_get
    stable_hash_json = self_awareness_contracts.stable_hash_json

    events = self_awareness_load_events(refresh=True)
    context_doc = load_latest_json(SELF_AWARENESS_CONTEXT_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_context_v1")
    if nested_get(context_doc, ["context_packet", "sections", "host_body", "complete"]) is not True:
        context_doc = self_awareness_context(write_latest=True)
    episodes_doc = load_latest_json(SELF_AWARENESS_EPISODES_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_episodes_v1")
    episode_rows = episodes_doc.get("episodes") if isinstance(episodes_doc.get("episodes"), list) else []
    stack_handoff_episodes = [
        episode for episode in episode_rows
        if isinstance(episode, dict) and episode.get("episode_kind") == "stack_handoff_blocker"
    ]
    working_stack_gap_episodes = [
        episode for episode in episode_rows
        if isinstance(episode, dict) and episode.get("episode_kind") == "working_stack_usage_gap"
    ]
    working_stack_movement_episodes = [
        episode for episode in episode_rows
        if isinstance(episode, dict) and episode.get("episode_kind") == "working_stack_movement"
    ]
    if not stack_handoff_episodes:
        requirement_probes = load_latest_json(SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_requirement_probes_v1")
        if runtime_evidence_contracts.safe_int(nested_get(requirement_probes, ["summary", "open"]), 0) > 0:
            episodes_doc = self_awareness_episodes(write_latest=True)
            episode_rows = episodes_doc.get("episodes") if isinstance(episodes_doc.get("episodes"), list) else []
            stack_handoff_episodes = [
                episode for episode in episode_rows
                if isinstance(episode, dict) and episode.get("episode_kind") == "stack_handoff_blocker"
            ]
            working_stack_gap_episodes = [
                episode for episode in episode_rows
                if isinstance(episode, dict) and episode.get("episode_kind") == "working_stack_usage_gap"
            ]
    if not working_stack_gap_episodes:
        working_stack = load_latest_json(SELF_AWARENESS_WORKING_STACK_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_working_stack_inventory_v1")
        if runtime_evidence_contracts.safe_int(nested_get(working_stack, ["summary", "usage_gaps"]), 0) > 0:
            episodes_doc = self_awareness_episodes(write_latest=True)
            episode_rows = episodes_doc.get("episodes") if isinstance(episodes_doc.get("episodes"), list) else []
            stack_handoff_episodes = [
                episode for episode in episode_rows
                if isinstance(episode, dict) and episode.get("episode_kind") == "stack_handoff_blocker"
            ]
            working_stack_gap_episodes = [
                episode for episode in episode_rows
                if isinstance(episode, dict) and episode.get("episode_kind") == "working_stack_usage_gap"
            ]
    episode_by_event: dict[str, str] = {}
    episode_by_id: dict[str, dict[str, Any]] = {}
    for episode in episode_rows:
        if not isinstance(episode, dict):
            continue
        episode_id = str(episode.get("episode_id") or "")
        if episode_id:
            episode_by_id[episode_id] = episode
        for event_id in episode.get("event_ids", []) if isinstance(episode.get("event_ids"), list) else []:
            episode_by_event[str(event_id)] = episode_id
    event_by_id = {
        str(event.get("event_id")): event
        for event in events
        if isinstance(event, dict) and event.get("event_id")
    }
    investigation = load_latest_json(SELF_AWARENESS_INVESTIGATE_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_investigation_v1")
    replay = load_latest_json(SELF_AWARENESS_REPLAY_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_replay_v1")
    candidates: list[dict[str, Any]] = []
    probe_alert_markers: list[dict[str, Any]] = []
    seen: set[str] = set()
    for event in events:
        if event.get("signal") != "alert":
            continue
        resource = event.get("resource") if isinstance(event.get("resource"), dict) else {}
        context = event.get("context") if isinstance(event.get("context"), dict) else {}
        fingerprint = str(resource.get("alert_fingerprint") or context.get("alert_fingerprint") or event.get("event_id"))
        synthetic_run_id = context.get("synthetic_run_id")
        if synthetic_run_id and resource.get("alertname") == "SelfAwarenessSyntheticProbe":
            probe_alert_markers.append({
                "event_id": event.get("event_id"),
                "synthetic_run_id": synthetic_run_id,
                "fingerprint": fingerprint,
                "selected_for_response": False,
                "reason": "probe-only alert channel marker; resident-review candidate is the selected working-stack movement episode",
                "evidence_refs": [
                    {"path": str(SELF_AWARENESS_EVENTS_LATEST_PATH), "event_id": event.get("event_id")},
                    {"path": str(SELF_AWARENESS_EPISODES_LATEST_PATH), "episode_id": episode_by_event.get(str(event.get("event_id")))},
                ],
                "policy": {
                    "read_only": True,
                    "host_layer_mutates_stack": False,
                    "executes_commands": False,
                    "automatic_remediation": False,
                },
            })
            continue
        candidate_id = (
            "self-awareness-synthetic-alert-" + str(synthetic_run_id)
            if synthetic_run_id
            else "self-awareness-alert-" + stable_hash_json(fingerprint, length=20)
        )
        if candidate_id in seen:
            continue
        seen.add(candidate_id)
        episode_id = episode_by_event.get(str(event.get("event_id")))
        episode = episode_by_id.get(str(episode_id or ""), {})
        candidate = runtime_evidence_contracts.reaction_candidate(
            SCHEMA_PREFIX,
            candidate_id,
            title="Self-awareness alert evidence needs owner review",
            severity=str(event.get("severity") or "warning"),
            category="self-awareness",
            reason="Alert event was correlated into the machine self-awareness layer; route next checks through owner review.",
            command="abyss-machine self-awareness brief --json",
            owner_route="abyss-machine:self-awareness",
            action_mode="operator_review",
            evidence=[
                {"path": str(SELF_AWARENESS_EVENTS_LATEST_PATH), "event_id": event.get("event_id")},
                {"path": str(SELF_AWARENESS_EPISODES_LATEST_PATH), "episode_id": episode_id},
            ] + (event.get("evidence_refs") if isinstance(event.get("evidence_refs"), list) else []),
        )
        response_contract = self_awareness_episode_response_contract(
            candidate_id=candidate_id,
            episode=episode,
            source_event=event,
            investigation=investigation,
            replay=replay,
            context_doc=context_doc,
        )
        candidate["alert_fingerprint"] = fingerprint
        candidate["source_event_id"] = event.get("event_id")
        candidate["episode_id"] = episode_id
        _attach_response(candidate, response_contract, nested_get)
        candidates.append(candidate)
    for episode in working_stack_gap_episodes:
        if not isinstance(episode, dict):
            continue
        episode_id = str(episode.get("episode_id") or "")
        working_stack_gap = episode.get("working_stack_gap") if isinstance(episode.get("working_stack_gap"), dict) else {}
        service = str(working_stack_gap.get("service") or episode.get("service") or "")
        if not episode_id or not service:
            continue
        candidate_id = "self-awareness-working-stack-gap-" + stable_hash_json({"episode": episode_id, "service": service}, length=20)
        if candidate_id in seen:
            continue
        seen.add(candidate_id)
        response_contract = self_awareness_episode_response_contract(
            candidate_id=candidate_id,
            episode=episode,
            source_event={},
            investigation=investigation,
            replay=replay,
            context_doc=context_doc,
        )
        status = str(working_stack_gap.get("machine_usage_status") or "")
        severity = "warning" if status.endswith("_degraded") else "watch"
        candidate = runtime_evidence_contracts.reaction_candidate(
            SCHEMA_PREFIX,
            candidate_id,
            title="Working stack usage gap needs owner review",
            severity=severity,
            category="self-awareness",
            reason="A stack organ is linked into the machine time-space-context body but still has unexhausted usable potential; route it through review without executing stack changes.",
            command="abyss-machine self-awareness working-stack --json",
            owner_route="abyss-machine:self-awareness",
            action_mode="owner_handoff_review",
            evidence=[
                {"path": str(SELF_AWARENESS_EPISODES_LATEST_PATH), "episode_id": episode_id, "service": service},
                {"path": str(SELF_AWARENESS_WORKING_STACK_LATEST_PATH), "service": service, "status": status},
                {"path": str(SELF_AWARENESS_SPATIAL_GRAPH_LATEST_PATH), "nodes": episode.get("affected_spatial_nodes")},
            ] + (episode.get("evidence_refs") if isinstance(episode.get("evidence_refs"), list) else []),
        )
        candidate["episode_id"] = episode_id
        candidate["working_stack_gap_service"] = service
        candidate["working_stack_gap_status"] = status
        candidate["activation_gap_route"] = response_contract.get("activation_gap_route")
        _attach_response(candidate, response_contract, nested_get)
        candidates.append(candidate)
    for episode in working_stack_movement_episodes:
        if not isinstance(episode, dict):
            continue
        episode_id = str(episode.get("episode_id") or "")
        service = str(episode.get("service") or (episode.get("affected_services")[0] if isinstance(episode.get("affected_services"), list) and episode.get("affected_services") else "") or "")
        movement_packet_id = str(episode.get("movement_packet_id") or "")
        event_id = next((str(item) for item in (episode.get("event_ids") if isinstance(episode.get("event_ids"), list) else []) if item), "")
        if not episode_id or not service or not movement_packet_id:
            continue
        candidate_id = "self-awareness-working-stack-movement-" + stable_hash_json({"episode": episode_id, "service": service, "movement": movement_packet_id}, length=20)
        if candidate_id in seen:
            continue
        seen.add(candidate_id)
        source_event = event_by_id.get(event_id, {})
        response_contract = self_awareness_episode_response_contract(
            candidate_id=candidate_id,
            episode=episode,
            source_event=source_event,
            investigation=investigation,
            replay=replay,
            context_doc=context_doc,
        )
        movement_selection = episode.get("movement_selection") if isinstance(episode.get("movement_selection"), dict) else {}
        candidate = runtime_evidence_contracts.reaction_candidate(
            SCHEMA_PREFIX,
            candidate_id,
            title="Working stack movement selected for resident review",
            severity="notice",
            category="self-awareness",
            reason="A read-only organ movement packet was selected for causal follow-up; route resident reasoning and replay without executing stack changes.",
            command=f"abyss-machine self-awareness investigate --episode-id {episode_id} --json",
            owner_route="abyss-machine:self-awareness",
            action_mode="resident_review",
            evidence=[
                {"path": str(SELF_AWARENESS_EVENTS_LATEST_PATH), "event_id": event_id, "movement_packet_id": movement_packet_id},
                {"path": str(SELF_AWARENESS_EPISODES_LATEST_PATH), "episode_id": episode_id, "service": service},
                {"path": str(SELF_AWARENESS_SPATIAL_GRAPH_LATEST_PATH), "nodes": episode.get("affected_spatial_nodes")},
            ] + (episode.get("evidence_refs") if isinstance(episode.get("evidence_refs"), list) else []),
        )
        candidate["episode_id"] = episode_id
        candidate["working_stack_movement_service"] = service
        candidate["movement_packet_id"] = movement_packet_id
        candidate["working_stack_link_id"] = episode.get("working_stack_link_id")
        candidate["movement_selection"] = movement_selection
        candidate["selected_reason"] = movement_selection.get("selected_reason")
        _attach_response(candidate, response_contract, nested_get)
        candidates.append(candidate)
    for episode in stack_handoff_episodes:
        if not isinstance(episode, dict):
            continue
        episode_id = str(episode.get("episode_id") or "")
        requirement_id = str(episode.get("requirement_id") or "")
        if not episode_id or not requirement_id:
            continue
        candidate_id = "self-awareness-stack-handoff-" + stable_hash_json({"episode": episode_id, "requirement_id": requirement_id}, length=20)
        if candidate_id in seen:
            continue
        seen.add(candidate_id)
        response_contract = self_awareness_episode_response_contract(
            candidate_id=candidate_id,
            episode=episode,
            source_event={},
            investigation=investigation,
            replay=replay,
            context_doc=context_doc,
        )
        severity = "watch" if requirement_id in {"stack.trace-backend", "stack.langchain-api.graph-observability"} else "warning"
        candidate = runtime_evidence_contracts.reaction_candidate(
            SCHEMA_PREFIX,
            candidate_id,
            title="Stack handoff blocker needs owner review",
            severity=severity,
            category="self-awareness",
            reason="Open stack-owned requirement is represented as a causal handoff episode; route it through review without executing stack changes.",
            command="abyss-machine self-awareness export --json",
            owner_route="abyss-machine:self-awareness",
            action_mode="owner_handoff_review",
            evidence=[
                {"path": str(SELF_AWARENESS_EPISODES_LATEST_PATH), "episode_id": episode_id, "requirement_id": requirement_id},
                {"path": str(SELF_AWARENESS_TIMELINE_LATEST_PATH), "marker_id": episode.get("stack_handoff_marker_id")},
                {"path": str(SELF_AWARENESS_SPATIAL_GRAPH_LATEST_PATH), "requirement_id": requirement_id},
            ] + (episode.get("evidence_refs") if isinstance(episode.get("evidence_refs"), list) else []),
        )
        candidate["episode_id"] = episode_id
        candidate["stack_handoff_requirement_id"] = requirement_id
        candidate["stack_handoff_marker_id"] = episode.get("stack_handoff_marker_id")
        candidate["stack_requirement_route"] = response_contract.get("stack_requirement_route")
        _attach_response(candidate, response_contract, nested_get)
        candidates.append(candidate)
    response_depth_candidates = [item for item in candidates if self_awareness_reaction_candidate_response_depth_complete(item)]
    body_trace_candidates = [
        item for item in candidates
        if self_awareness_body_trace_complete(nested_get(item, ["response_contract", "body_trace"]))
    ]
    data = {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_alerts_v1",
        "version": VERSION,
        "generated_at": now_iso(),
        "ok": True,
        "summary": {
            "alert_events": sum(1 for event in events if event.get("signal") == "alert"),
            "reaction_candidates": len(candidates),
            "response_depth_candidates": len(response_depth_candidates),
            "response_depth_missing": len(candidates) - len(response_depth_candidates),
            "body_trace_candidates": len(body_trace_candidates),
            "body_trace_missing": len(candidates) - len(body_trace_candidates),
            "stack_handoff_candidates": sum(1 for item in candidates if isinstance(item, dict) and item.get("stack_handoff_requirement_id")),
            "stack_handoff_episodes": len(stack_handoff_episodes),
            "working_stack_gap_candidates": sum(1 for item in candidates if isinstance(item, dict) and item.get("working_stack_gap_service")),
            "working_stack_gap_episodes": len(working_stack_gap_episodes),
            "working_stack_movement_candidates": sum(1 for item in candidates if isinstance(item, dict) and item.get("working_stack_movement_service")),
            "working_stack_movement_episodes": len(working_stack_movement_episodes),
            "probe_alert_markers": len(probe_alert_markers),
            "automatic_actions": 0,
        },
        "candidates": candidates,
        "probe_alert_markers": probe_alert_markers,
        "body_trace": {
            "schema": f"{SCHEMA_PREFIX}_self_awareness_alert_body_trace_summary_v1",
            "candidates": len(candidates),
            "complete": len(body_trace_candidates),
            "missing": len(candidates) - len(body_trace_candidates),
            "host_body_complete": nested_get(context_doc, ["context_packet", "sections", "host_body", "complete"]),
            "evidence_refs": [{"path": str(SELF_AWARENESS_CONTEXT_LATEST_PATH), "section": "context_packet.host_body"}],
            "policy": {
                "read_only": True,
                "host_layer_mutates_stack": False,
                "executes_commands": False,
            },
        },
        "reaction_bridge": {
            "consumed_by": "abyss-machine reactions --json",
            "latest": str(REACTIONS_LATEST_PATH),
            "automatic_execution": False,
            "requires_response_contract": True,
        },
        "policy": {
            "automatic_action": False,
            "executes_commands": False,
            "response_execution": False,
            "owner_gated": True,
            "response_contract_required": True,
        },
        "tests": {
            "dedupe": "candidate id dedupes by alert fingerprint or synthetic run id",
            "owner_gate": "reaction candidate uses automatic=false",
            "working_stack_gap": "working stack usage-gap episodes route to owner-gated reaction candidates",
            "working_stack_movement": "selected organ movement episodes route to owner-gated resident-review candidates",
        },
    }
    if write_latest:
        errors = write_latest_and_history(data, SELF_AWARENESS_ALERTS_LATEST_PATH, SELF_AWARENESS_ALERTS_ROOT)
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def _attach_response(
    candidate: dict[str, Any],
    response_contract: dict[str, Any],
    nested_get: DocumentPort,
) -> None:
    candidate["validated_episode"] = response_contract.get("validated_episode")
    candidate["response_contract"] = response_contract
    candidate["body_trace"] = response_contract.get("body_trace")
    candidate["entity_event_document_context"] = response_contract.get("entity_event_document_context")
    candidate["risk"] = response_contract.get("risk")
    candidate["blast_radius"] = response_contract.get("blast_radius")
    candidate["rollback"] = response_contract.get("rollback")
    candidate["runbook_candidate"] = response_contract.get("runbook_candidate")
    candidate["investigation_thread_id"] = nested_get(response_contract, ["investigation", "thread_id"])
    candidate["replay_thread_id"] = nested_get(response_contract, ["replay", "thread_id"])

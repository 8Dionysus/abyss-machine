from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import runtime_evidence_contracts
from . import self_awareness_contracts


DocumentPort = Callable[..., Any]


@dataclass(frozen=True)
class SelfAwarenessResidentCognitivePaths:
    completion_audit_latest: Path
    context_latest: Path
    episodes_latest: Path
    resident_status_latest: Path
    resident_candidates_latest: Path
    resident_evals_latest: Path
    workhorse_preflight_latest: Path
    capabilities_latest: Path
    spatial_graph_latest: Path
    query_latest: Path
    correlation_latest: Path
    nervous_brief_latest: Path
    rag_validate_latest: Path
    requirements_latest: Path
    investigate_latest: Path
    replay_latest: Path
    export_latest: Path


@dataclass(frozen=True)
class SelfAwarenessResidentCognitiveConfig:
    schema_prefix: str
    version: str


@dataclass(frozen=True)
class SelfAwarenessResidentCognitiveRuntimePort:
    load_latest_json: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessResidentCognitiveRefreshPort:
    replay: DocumentPort
    export: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessResidentCognitiveContractPort:
    completion_route_packet_issues: DocumentPort
    episode_body_trace: DocumentPort
    body_trace_complete: DocumentPort
    resident_worker_detail_complete: DocumentPort


def resident_completion_route_context(
    completion_audit_doc: dict[str, Any] | None = None,
    *,
    paths: SelfAwarenessResidentCognitivePaths,
    config: SelfAwarenessResidentCognitiveConfig,
    runtime_port: SelfAwarenessResidentCognitiveRuntimePort,
    contract_port: SelfAwarenessResidentCognitiveContractPort,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    SELF_AWARENESS_COMPLETION_AUDIT_LATEST_PATH = paths.completion_audit_latest
    load_latest_json = runtime_port.load_latest_json
    nested_get = self_awareness_contracts.nested_get
    safe_int = runtime_evidence_contracts.safe_int
    self_awareness_completion_route_packet_issues = contract_port.completion_route_packet_issues
    completion_audit_doc = completion_audit_doc if isinstance(completion_audit_doc, dict) else load_latest_json(
        SELF_AWARENESS_COMPLETION_AUDIT_LATEST_PATH,
        f"{SCHEMA_PREFIX}_self_awareness_completion_audit_v1",
    )
    route_packets = completion_audit_doc.get("completion_route_packets") if isinstance(completion_audit_doc.get("completion_route_packets"), dict) else {}
    expected_routes = safe_int(nested_get(completion_audit_doc, ["completion_route_map", "summary", "routes"]), -1)
    expected_routes = expected_routes if expected_routes >= 0 else None
    expected_actions = safe_int(nested_get(completion_audit_doc, ["action_backlog", "summary", "actions"]), -1)
    expected_actions = expected_actions if expected_actions >= 0 else None
    issues = self_awareness_completion_route_packet_issues(
        route_packets,
        expected_routes=expected_routes,
        expected_actions=expected_actions,
    )
    packets = route_packets.get("packets") if isinstance(route_packets.get("packets"), list) else []
    top_packet = route_packets.get("top_packet") if isinstance(route_packets.get("top_packet"), dict) else (packets[0] if packets and isinstance(packets[0], dict) else {})

    def compact_packet(packet: dict[str, Any]) -> dict[str, Any]:
        return {
            "packet_id": packet.get("packet_id"),
            "route_id": packet.get("route_id"),
            "route_path": packet.get("route_path"),
            "status": packet.get("status"),
            "action_ids": packet.get("action_ids") if isinstance(packet.get("action_ids"), list) else [],
            "entity_ids": packet.get("entity_ids") if isinstance(packet.get("entity_ids"), list) else [],
            "event_ids": packet.get("event_ids") if isinstance(packet.get("event_ids"), list) else [],
            "document_ids": packet.get("document_ids") if isinstance(packet.get("document_ids"), list) else [],
            "coverage_planes": packet.get("coverage_planes") if isinstance(packet.get("coverage_planes"), list) else [],
            "closure_blocker_keys": packet.get("closure_blocker_keys") if isinstance(packet.get("closure_blocker_keys"), list) else [],
            "unblocks_requirement_ids": packet.get("unblocks_requirement_ids") if isinstance(packet.get("unblocks_requirement_ids"), list) else [],
            "safe_next_actions": packet.get("safe_next_actions") if isinstance(packet.get("safe_next_actions"), list) else [],
            "verifier_commands": packet.get("verifier_commands") if isinstance(packet.get("verifier_commands"), list) else [],
            "evidence_refs": (packet.get("evidence_refs") if isinstance(packet.get("evidence_refs"), list) else [])[:20],
            "complete": packet.get("complete") is True,
            "policy": packet.get("policy") if isinstance(packet.get("policy"), dict) else {},
        }

    compact_top_packet = compact_packet(top_packet) if top_packet else {}
    compact_packets = [
        compact_packet(packet)
        for packet in packets[:8]
        if isinstance(packet, dict)
    ]
    complete_with_packet = bool(
        not issues
        and route_packets.get("schema") == f"{SCHEMA_PREFIX}_self_awareness_completion_route_packet_index_v1"
        and route_packets.get("ok") is True
        and compact_top_packet
        and compact_top_packet.get("complete") is True
        and nested_get(compact_top_packet, ["policy", "host_layer_mutates_stack"]) is False
        and nested_get(compact_top_packet, ["policy", "executes_commands"]) is False
        and bool(compact_top_packet.get("entity_ids"))
        and bool(compact_top_packet.get("event_ids"))
        and bool(compact_top_packet.get("document_ids"))
        and bool(compact_top_packet.get("verifier_commands"))
    )
    complete_empty_no_actions = bool(
        not issues
        and route_packets.get("schema") == f"{SCHEMA_PREFIX}_self_awareness_completion_route_packet_index_v1"
        and route_packets.get("ok") is True
        and expected_actions == 0
        and safe_int(nested_get(route_packets, ["summary", "actions"]), 0) == 0
        and safe_int(nested_get(route_packets, ["summary", "covered_actions"]), 0) == 0
        and safe_int(nested_get(route_packets, ["summary", "packets"]), 0) == 0
        and not compact_top_packet
        and not compact_packets
    )
    complete = complete_with_packet or complete_empty_no_actions
    return {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_resident_completion_route_context_v1",
        "complete": complete,
        "state": "complete_empty_no_actions" if complete_empty_no_actions else "with_packet" if complete_with_packet else "incomplete",
        "issues": issues,
        "summary": route_packets.get("summary") if isinstance(route_packets.get("summary"), dict) else {},
        "top_packet": compact_top_packet,
        "ordered_packets": compact_packets,
        "expected_routes": expected_routes,
        "expected_actions": expected_actions,
        "automation": {
            "mode": "latest_only_readmodel",
            "runs_probe": False,
            "runs_cycle": False,
            "runs_indexing": False,
            "runs_stack_http_probes": False,
            "executes_verifiers": False,
        },
        "policy": {
            "read_only": True,
            "handoff_only": True,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "executes_commands": False,
            "action_execution": False,
            "automatic_remediation": False,
            "human_approval_before_mutation": True,
        },
        "evidence_refs": [
            {"path": str(SELF_AWARENESS_COMPLETION_AUDIT_LATEST_PATH), "section": "completion_route_packets"},
            {"path": str(SELF_AWARENESS_COMPLETION_AUDIT_LATEST_PATH), "section": "completion_route_map"},
            {"path": str(SELF_AWARENESS_COMPLETION_AUDIT_LATEST_PATH), "section": "entity_event_document_map"},
        ],
    }


def resident_completion_route_context_complete(
    context: Any,
    *,
    config: SelfAwarenessResidentCognitiveConfig,
) -> bool:
    SCHEMA_PREFIX = config.schema_prefix
    nested_get = self_awareness_contracts.nested_get
    safe_int = runtime_evidence_contracts.safe_int
    if not isinstance(context, dict):
        return False
    top_packet = context.get("top_packet") if isinstance(context.get("top_packet"), dict) else {}
    ordered_packets = context.get("ordered_packets") if isinstance(context.get("ordered_packets"), list) else []
    base_ok = (
        context.get("schema") == f"{SCHEMA_PREFIX}_self_awareness_resident_completion_route_context_v1"
        and context.get("complete") is True
        and context.get("issues") == []
        and nested_get(context, ["automation", "runs_probe"]) is False
        and nested_get(context, ["automation", "runs_cycle"]) is False
        and nested_get(context, ["automation", "runs_indexing"]) is False
        and nested_get(context, ["automation", "runs_stack_http_probes"]) is False
        and nested_get(context, ["automation", "executes_verifiers"]) is False
        and nested_get(context, ["policy", "host_layer_mutates_stack"]) is False
        and nested_get(context, ["policy", "executes_commands"]) is False
        and nested_get(context, ["policy", "action_execution"]) is False
        and bool(context.get("evidence_refs"))
    )
    if not base_ok:
        return False
    if context.get("state") == "complete_empty_no_actions":
        return (
            safe_int(context.get("expected_actions"), -1) == 0
            and safe_int(nested_get(context, ["summary", "actions"]), -1) == 0
            and safe_int(nested_get(context, ["summary", "covered_actions"]), -1) == 0
            and safe_int(nested_get(context, ["summary", "packets"]), -1) == 0
            and not top_packet
            and ordered_packets == []
        )
    return (
        bool(top_packet.get("packet_id"))
        and bool(top_packet.get("route_id"))
        and bool(top_packet.get("action_ids"))
        and bool(top_packet.get("entity_ids"))
        and bool(top_packet.get("event_ids"))
        and bool(top_packet.get("document_ids"))
        and bool(top_packet.get("verifier_commands"))
        and bool(top_packet.get("evidence_refs"))
        and bool(ordered_packets)
    )


def resident_cognitive_packet(
    *,
    query_text: str,
    selected_episode: dict[str, Any],
    resident_detail: dict[str, Any],
    query_doc: dict[str, Any],
    correlation: dict[str, Any],
    memory_space: dict[str, Any],
    llm_escalation_detail: dict[str, Any],
    rag_validation: dict[str, Any],
    nervous: dict[str, Any],
    artifact_refs: list[dict[str, Any]],
    context_doc: dict[str, Any] | None = None,
    completion_audit_doc: dict[str, Any] | None = None,
    paths: SelfAwarenessResidentCognitivePaths,
    config: SelfAwarenessResidentCognitiveConfig,
    runtime_port: SelfAwarenessResidentCognitiveRuntimePort,
    contract_port: SelfAwarenessResidentCognitiveContractPort,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    VERSION = config.version
    SELF_AWARENESS_COMPLETION_AUDIT_LATEST_PATH = paths.completion_audit_latest
    SELF_AWARENESS_CONTEXT_LATEST_PATH = paths.context_latest
    SELF_AWARENESS_EPISODES_LATEST_PATH = paths.episodes_latest
    AI_LLM_RESIDENT_STATUS_LATEST_PATH = paths.resident_status_latest
    AI_LLM_RESIDENT_CANDIDATES_LATEST_PATH = paths.resident_candidates_latest
    AI_LLM_RESIDENT_EVALS_LATEST_PATH = paths.resident_evals_latest
    AI_LLM_WORKHORSE_PREFLIGHT_LATEST_PATH = paths.workhorse_preflight_latest
    SELF_AWARENESS_CAPABILITIES_LATEST_PATH = paths.capabilities_latest
    SELF_AWARENESS_SPATIAL_GRAPH_LATEST_PATH = paths.spatial_graph_latest
    SELF_AWARENESS_QUERY_LATEST_PATH = paths.query_latest
    SELF_AWARENESS_CORRELATION_LATEST_PATH = paths.correlation_latest
    NERVOUS_BRIEF_LATEST_PATH = paths.nervous_brief_latest
    RAG_VALIDATE_LATEST_PATH = paths.rag_validate_latest
    SELF_AWARENESS_REQUIREMENTS_LATEST_PATH = paths.requirements_latest
    load_latest_json = runtime_port.load_latest_json
    nested_get = self_awareness_contracts.nested_get
    safe_float = runtime_evidence_contracts.safe_float
    safe_int = runtime_evidence_contracts.safe_int
    self_awareness_episode_body_trace = contract_port.episode_body_trace
    self_awareness_resident_worker_detail_complete = contract_port.resident_worker_detail_complete
    self_awareness_resident_completion_route_context = lambda document=None: resident_completion_route_context(
        document, paths=paths, config=config, runtime_port=runtime_port, contract_port=contract_port
    )
    self_awareness_resident_completion_route_context_complete = lambda document: resident_completion_route_context_complete(
        document, config=config
    )
    query_plan = query_doc.get("query_plan") if isinstance(query_doc.get("query_plan"), dict) else {}
    context_doc = context_doc if isinstance(context_doc, dict) else load_latest_json(
        SELF_AWARENESS_CONTEXT_LATEST_PATH,
        f"{SCHEMA_PREFIX}_self_awareness_context_v1",
    )
    body_trace = self_awareness_episode_body_trace(
        episode=selected_episode,
        source_event={},
        context_doc=context_doc,
    )
    completion_route_context = self_awareness_resident_completion_route_context(completion_audit_doc)
    top_completion_route_packet = completion_route_context.get("top_packet") if isinstance(completion_route_context.get("top_packet"), dict) else {}
    confidence = selected_episode.get("confidence") if isinstance(selected_episode.get("confidence"), dict) else {}
    selected_score = safe_float(confidence.get("score"), 0.0) or 0.0
    selected_working_stack_gap = selected_episode.get("working_stack_gap") if isinstance(selected_episode.get("working_stack_gap"), dict) else {}
    memory_blocked = safe_int(nested_get(memory_space, ["summary", "blocked_gates"]), 0)
    contradiction_notes: list[dict[str, Any]] = []
    if selected_episode.get("episode_kind") == "working_stack_usage_gap" and selected_working_stack_gap:
        contradiction_notes.append({
            "id": "working_stack_gap_selected",
            "note": "Selected episode is an organ-level working-stack usage gap; investigate it as unexhausted stack potential and keep remediation owner-gated.",
            "severity": "body_gap",
            "service": selected_working_stack_gap.get("service"),
            "machine_usage_status": selected_working_stack_gap.get("machine_usage_status"),
            "working_stack_link_id": selected_working_stack_gap.get("working_stack_link_id"),
            "evidence_refs": [{"path": str(SELF_AWARENESS_EPISODES_LATEST_PATH), "episode_id": selected_episode.get("episode_id"), "section": "working_stack_gap"}],
        })
    if memory_blocked:
        contradiction_notes.append({
            "id": "memory_space_freshness_block",
            "note": "Memory-space overlay reports blocked freshness gates; deep reasoning must surface maintenance route before treating retrieval as current.",
            "severity": "watch",
            "evidence_refs": [{"path": str(SELF_AWARENESS_CONTEXT_LATEST_PATH), "summary": memory_space.get("summary")}],
        })
    if nested_get(resident_detail, ["serving", "owner"]) == "abyss-stack":
        contradiction_notes.append({
            "id": "serving_owner_boundary",
            "note": "Resident worker serving endpoint is stack-owned; abyss-machine may observe and use bounded evidence but must not mutate serving runtime.",
            "severity": "boundary",
            "evidence_refs": [{"path": str(AI_LLM_RESIDENT_STATUS_LATEST_PATH), "serving": resident_detail.get("serving")}],
        })
    if nested_get(llm_escalation_detail, ["gates", "model_execution_now", "allowed"]) is not True:
        contradiction_notes.append({
            "id": "escalation_not_allowed_now",
            "note": "E4B/Qwen escalation route is present as review/gate evidence, but current model execution is not allowed without resource/mode/preflight approval.",
            "severity": "gate",
            "evidence_refs": [{"path": str(AI_LLM_WORKHORSE_PREFLIGHT_LATEST_PATH), "gate": nested_get(llm_escalation_detail, ["gates", "model_execution_now"])}],
        })
    if not selected_episode.get("episode_id") or selected_score < 0.7:
        contradiction_notes.append({
            "id": "episode_confidence_limited",
            "note": "Selected episode remains candidate-level evidence; root-cause truth requires stronger trace/span/counterfactual proof.",
            "severity": "truth_boundary",
            "evidence_refs": [{"path": str(SELF_AWARENESS_EPISODES_LATEST_PATH), "episode_id": selected_episode.get("episode_id"), "confidence": confidence}],
        })
    if self_awareness_resident_completion_route_context_complete(completion_route_context) and completion_route_context.get("state") == "complete_empty_no_actions":
        contradiction_notes.append({
            "id": "completion_route_no_open_actions",
            "note": "Completion route packet context is complete and empty because completion-audit reports no open action backlog.",
            "severity": "route_clear",
            "evidence_refs": [{"path": str(SELF_AWARENESS_COMPLETION_AUDIT_LATEST_PATH), "section": "completion_route_packets.summary"}],
        })
    elif self_awareness_resident_completion_route_context_complete(completion_route_context):
        contradiction_notes.append({
            "id": "completion_route_owner_boundary",
            "note": "Completion route packet is usable as the next body-navigation context, but its safe next action remains handoff-only and stack-owner gated.",
            "severity": "route_boundary",
            "route_id": top_completion_route_packet.get("route_id"),
            "route_path": top_completion_route_packet.get("route_path"),
            "evidence_refs": [{"path": str(SELF_AWARENESS_COMPLETION_AUDIT_LATEST_PATH), "section": "completion_route_packets.top_packet"}],
        })
    else:
        contradiction_notes.append({
            "id": "completion_route_context_incomplete",
            "note": "Completion route packet context is incomplete; resident reasoning cannot claim automatic route navigation until completion-audit refreshes it.",
            "severity": "route_gap",
            "issues": completion_route_context.get("issues") if isinstance(completion_route_context.get("issues"), list) else [],
            "evidence_refs": [{"path": str(SELF_AWARENESS_COMPLETION_AUDIT_LATEST_PATH), "section": "completion_route_packets"}],
        })
    if nested_get(resident_detail, ["policy", "candidate_output_is_owner_truth"]) is not False:
        contradiction_notes.append({
            "id": "candidate_truth_policy_missing",
            "note": "Resident candidate output truth boundary is not explicit.",
            "severity": "policy",
            "evidence_refs": [{"path": str(AI_LLM_RESIDENT_CANDIDATES_LATEST_PATH)}],
        })

    hypothesis_tests = [
        *([
            {
                "id": "working_stack_gap_needs_owner_gated_smoke",
                "hypothesis": "The selected stack organ has unexhausted usable potential until bounded smoke/verifier commands prove deep use.",
                "method": "check working_stack_gap service/status/link, failed probes, safe next action, verifier commands, and no-stack-mutation policy",
                "support": [
                    f"service={selected_working_stack_gap.get('service')}",
                    f"status={selected_working_stack_gap.get('machine_usage_status')}",
                    f"link={selected_working_stack_gap.get('working_stack_link_id')}",
                    f"gap={selected_working_stack_gap.get('usage_gap')}",
                ],
                "counter_evidence": selected_episode.get("counter_evidence") if isinstance(selected_episode.get("counter_evidence"), list) else [],
                "verdict": "owner_gated_usage_gap",
                "confidence": confidence,
                "evidence_refs": [{"path": str(SELF_AWARENESS_EPISODES_LATEST_PATH), "episode_id": selected_episode.get("episode_id"), "section": "working_stack_gap"}],
            }
        ] if selected_working_stack_gap else []),
        {
            "id": "episode_context_resource_time",
            "hypothesis": "The selected observations form one candidate episode through context/resource/time adjacency.",
            "method": "compare selected episode event ids, affected spatial nodes, context keys, SLO views, and anomaly baselines",
            "support": selected_episode.get("suspected_cause_chain") if isinstance(selected_episode.get("suspected_cause_chain"), list) else [],
            "counter_evidence": selected_episode.get("counter_evidence") if isinstance(selected_episode.get("counter_evidence"), list) else [],
            "verdict": "candidate_supported" if selected_episode.get("episode_id") else "not_selected",
            "confidence": confidence,
            "evidence_refs": [{"path": str(SELF_AWARENESS_EPISODES_LATEST_PATH), "episode_id": selected_episode.get("episode_id")}],
        },
        {
            "id": "completion_route_packet_context",
            "hypothesis": "The next self-awareness body route is navigable only when completion-audit binds route, actions, entities, events, documents, evidence refs, and verifier handoff commands.",
            "method": "check resident completion_route_context top packet and non-mutating policy before using it as agent context",
            "support": [
                f"route_id={top_completion_route_packet.get('route_id')}",
                f"actions={len(top_completion_route_packet.get('action_ids') if isinstance(top_completion_route_packet.get('action_ids'), list) else [])}",
                f"entities={len(top_completion_route_packet.get('entity_ids') if isinstance(top_completion_route_packet.get('entity_ids'), list) else [])}",
                f"documents={len(top_completion_route_packet.get('document_ids') if isinstance(top_completion_route_packet.get('document_ids'), list) else [])}",
            ],
            "counter_evidence": completion_route_context.get("issues") if isinstance(completion_route_context.get("issues"), list) else [],
            "verdict": (
                "no_open_completion_actions"
                if self_awareness_resident_completion_route_context_complete(completion_route_context) and completion_route_context.get("state") == "complete_empty_no_actions"
                else "route_packet_context_ready"
                if self_awareness_resident_completion_route_context_complete(completion_route_context)
                else "route_packet_context_incomplete"
            ),
            "confidence": {"score": 0.9 if self_awareness_resident_completion_route_context_complete(completion_route_context) else 0.35},
            "evidence_refs": [{"path": str(SELF_AWARENESS_COMPLETION_AUDIT_LATEST_PATH), "section": "completion_route_packets.top_packet"}],
        },
        {
            "id": "resident_worker_can_support_summary",
            "hypothesis": "warm-E2B can support evidence-cited summary synthesis without becoming proof authority.",
            "method": "check resident health, monitor timers, candidate queues, heartbeat evals, and non-action policy",
            "support": [
                f"status={resident_detail.get('status')}",
                f"health_latency_ms={nested_get(resident_detail, ['health', 'health_latency_ms'])}",
                f"candidates={nested_get(resident_detail, ['candidate_context', 'candidates'])}",
                f"eval_overall_score={nested_get(resident_detail, ['evals', 'overall_score'])}",
            ],
            "counter_evidence": [item.get("note") for item in contradiction_notes if item.get("id") in {"serving_owner_boundary", "candidate_truth_policy_missing"}],
            "verdict": "usable_as_bounded_worker" if self_awareness_resident_worker_detail_complete(resident_detail) else "worker_incomplete",
            "confidence": {"score": 0.82 if self_awareness_resident_worker_detail_complete(resident_detail) else 0.45},
            "evidence_refs": [
                {"path": str(AI_LLM_RESIDENT_STATUS_LATEST_PATH)},
                {"path": str(AI_LLM_RESIDENT_EVALS_LATEST_PATH)},
                {"path": str(AI_LLM_RESIDENT_CANDIDATES_LATEST_PATH)},
            ],
        },
        {
            "id": "escalation_requires_gates",
            "hypothesis": "E4B/Qwen escalation is available only as gated route evidence unless resource/mode/preflight explicitly allow execution.",
            "method": "read llm.escalation.routes capability gate state",
            "support": [f"status={nested_get(llm_escalation_detail, ['gates', 'model_execution_now', 'status'])}"],
            "counter_evidence": [item.get("note") for item in contradiction_notes if item.get("id") == "escalation_not_allowed_now"],
            "verdict": "gated_review_route",
            "confidence": {"score": 0.88},
            "evidence_refs": [{"path": str(SELF_AWARENESS_CAPABILITIES_LATEST_PATH), "capability_id": "llm.escalation.routes"}],
        },
    ]

    read_only_tools = [
        {
            "id": "promql.stack_core",
            "kind": "promql_read",
            "command": "query Prometheus through stack-bridge/self-awareness query plan",
            "queries": query_plan.get("promql") if isinstance(query_plan.get("promql"), list) else [],
            "read_only": True,
            "host_layer_mutates_stack": False,
            "stores_raw_body": False,
            "evidence_refs": [{"path": str(SELF_AWARENESS_QUERY_LATEST_PATH), "section": "query_plan.promql"}],
        },
        {
            "id": "logql.context",
            "kind": "logql_read",
            "command": "query Loki through bounded LogQL snippets",
            "queries": query_plan.get("logql") if isinstance(query_plan.get("logql"), list) else [],
            "read_only": True,
            "host_layer_mutates_stack": False,
            "stores_raw_body": False,
            "evidence_refs": [{"path": str(SELF_AWARENESS_QUERY_LATEST_PATH), "section": "query_plan.logql"}],
        },
        {
            "id": "self-awareness.context",
            "kind": "self_awareness_context",
            "command": "abyss-machine self-awareness context --json",
            "read_only": True,
            "host_layer_mutates_stack": False,
            "stores_raw_body": False,
            "evidence_refs": [{"path": str(SELF_AWARENESS_CONTEXT_LATEST_PATH), "summary": memory_space.get("summary")}],
        },
        {
            "id": "self-awareness.spatial-graph",
            "kind": "self_awareness_spatial_graph",
            "command": "abyss-machine self-awareness spatial-graph --json",
            "read_only": True,
            "host_layer_mutates_stack": False,
            "stores_raw_body": False,
            "evidence_refs": [{"path": str(SELF_AWARENESS_SPATIAL_GRAPH_LATEST_PATH)}],
        },
        {
            "id": "rag.validate",
            "kind": "rag_validate",
            "command": "abyss-machine rag validate --json",
            "read_only": True,
            "host_layer_mutates_stack": False,
            "stores_raw_body": False,
            "evidence_refs": [{"path": str(RAG_VALIDATE_LATEST_PATH), "ok": rag_validation.get("ok"), "summary": rag_validation.get("summary")}],
        },
        {
            "id": "nervous.brief",
            "kind": "nervous_brief",
            "command": "abyss-machine nervous brief --scope now --json",
            "read_only": True,
            "host_layer_mutates_stack": False,
            "stores_raw_body": False,
            "evidence_refs": [{"path": str(NERVOUS_BRIEF_LATEST_PATH), "readiness": nervous.get("readiness")}],
        },
        {
            "id": "requirements.handoff",
            "kind": "requirements_handoff",
            "command": "abyss-machine self-awareness requirements --json",
            "read_only": True,
            "host_layer_mutates_stack": False,
            "stores_raw_body": False,
            "evidence_refs": [{"path": str(SELF_AWARENESS_REQUIREMENTS_LATEST_PATH)}],
        },
        {
            "id": "completion.route-packets",
            "kind": "completion_route_packets",
            "command": "abyss-machine self-awareness completion-audit --json",
            "route_id": top_completion_route_packet.get("route_id"),
            "route_path": top_completion_route_packet.get("route_path"),
            "read_only": True,
            "host_layer_mutates_stack": False,
            "stores_raw_body": False,
            "evidence_refs": [{"path": str(SELF_AWARENESS_COMPLETION_AUDIT_LATEST_PATH), "section": "completion_route_packets"}],
        },
        {
            "id": "llm.escalation.gate",
            "kind": "resource_mode_gate",
            "command": "abyss-machine self-awareness capabilities --json",
            "read_only": True,
            "host_layer_mutates_stack": False,
            "stores_raw_body": False,
            "evidence_refs": [{"path": str(SELF_AWARENESS_CAPABILITIES_LATEST_PATH), "capability_id": "llm.escalation.routes"}],
        },
    ]

    bounded_sources = [
        {"name": "query", "path": str(SELF_AWARENESS_QUERY_LATEST_PATH), "summary": query_doc.get("summary")},
        {"name": "correlation", "path": str(SELF_AWARENESS_CORRELATION_LATEST_PATH), "summary": correlation.get("summary")},
        {"name": "memory_space", "path": str(SELF_AWARENESS_CONTEXT_LATEST_PATH), "summary": memory_space.get("summary")},
        {"name": "host_body", "path": str(SELF_AWARENESS_CONTEXT_LATEST_PATH), "summary": nested_get(context_doc, ["context_packet", "sections", "host_body"])},
        {"name": "resident_status", "path": str(AI_LLM_RESIDENT_STATUS_LATEST_PATH), "status": resident_detail.get("status")},
        {"name": "resident_candidates", "path": str(AI_LLM_RESIDENT_CANDIDATES_LATEST_PATH), "summary": nested_get(resident_detail, ["candidate_context", "candidate_readmodel"])},
        {"name": "resident_evals", "path": str(AI_LLM_RESIDENT_EVALS_LATEST_PATH), "summary": resident_detail.get("evals")},
        {"name": "completion_route_packets", "path": str(SELF_AWARENESS_COMPLETION_AUDIT_LATEST_PATH), "summary": completion_route_context.get("summary")},
    ]
    return {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_resident_cognitive_packet_v1",
        "version": VERSION,
        "worker": "warm-e2b/gemma4.spark",
        "query": query_text,
        "selected_episode_id": selected_episode.get("episode_id"),
        "body_trace": body_trace,
        "completion_route_context": completion_route_context,
        "resident_worker_detail": resident_detail,
        "bounded_context": {
            "max_sources": 12,
            "max_evidence_refs": 40,
            "sources": bounded_sources,
            "artifact_refs": artifact_refs[:40],
            "raw_private_content": False,
            "stores_raw_body": False,
            "freshness_must_precede_reasoning": True,
            "raw_evidence_is_not_truth": True,
        },
        "read_only_tools": read_only_tools,
        "hypothesis_tests": hypothesis_tests,
        "contradiction_notes": contradiction_notes,
        "evidence_cited_summary": {
            "summary": "Resident worker can support bounded candidate synthesis only when evidence refs, freshness gates, and resource/mode gates are preserved.",
            "truth_level": "candidate",
            "evidence_refs": artifact_refs[:20],
        },
        "escalation_gate": {
            "schema": f"{SCHEMA_PREFIX}_self_awareness_resident_escalation_gate_v1",
            "route_ready": llm_escalation_detail.get("route_ready"),
            "review_pipeline_ready": llm_escalation_detail.get("review_pipeline_ready"),
            "model_execution_now": nested_get(llm_escalation_detail, ["gates", "model_execution_now"]),
            "qwen_ready": nested_get(llm_escalation_detail, ["qwen_lazy_load", "ready"]),
            "human_approval_before_mutation": nested_get(llm_escalation_detail, ["policy", "human_approval_before_mutation"]) is True,
            "operator_force_required_for_model_execution": nested_get(llm_escalation_detail, ["policy", "operator_force_required_for_model_execution"]),
            "host_layer_mutates_stack": False,
            "action_execution": False,
            "evidence_refs": [{"path": str(SELF_AWARENESS_CAPABILITIES_LATEST_PATH), "capability_id": "llm.escalation.routes"}],
        },
        "policy": {
            "model_execution_in_this_graph": False,
            "direct_model_prompt_executed": False,
            "candidate_synthesis_only": True,
            "candidate_output_is_owner_truth": False,
            "conclusions_are_candidates": True,
            "bounded_context": True,
            "read_only_tools_only": True,
            "action_execution": False,
            "auto_remediation": False,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "human_approval_before_mutation": True,
        },
    }


def resident_cognitive_packet_complete(
    packet: dict[str, Any],
    *,
    config: SelfAwarenessResidentCognitiveConfig,
    contract_port: SelfAwarenessResidentCognitiveContractPort,
) -> bool:
    SCHEMA_PREFIX = config.schema_prefix
    nested_get = self_awareness_contracts.nested_get
    self_awareness_resident_worker_detail_complete = contract_port.resident_worker_detail_complete
    self_awareness_body_trace_complete = contract_port.body_trace_complete
    self_awareness_resident_completion_route_context_complete = lambda document: resident_completion_route_context_complete(
        document, config=config
    )
    if not isinstance(packet, dict):
        return False
    tools = packet.get("read_only_tools") if isinstance(packet.get("read_only_tools"), list) else []
    tool_kinds = {str(tool.get("kind")) for tool in tools if isinstance(tool, dict)}
    hypotheses = packet.get("hypothesis_tests") if isinstance(packet.get("hypothesis_tests"), list) else []
    contradictions = packet.get("contradiction_notes") if isinstance(packet.get("contradiction_notes"), list) else []
    return (
        packet.get("schema") == f"{SCHEMA_PREFIX}_self_awareness_resident_cognitive_packet_v1"
        and packet.get("worker") == "warm-e2b/gemma4.spark"
        and self_awareness_resident_worker_detail_complete(packet.get("resident_worker_detail") if isinstance(packet.get("resident_worker_detail"), dict) else {})
        and self_awareness_body_trace_complete(packet.get("body_trace"))
        and nested_get(packet, ["bounded_context", "raw_private_content"]) is False
        and nested_get(packet, ["bounded_context", "stores_raw_body"]) is False
        and nested_get(packet, ["bounded_context", "freshness_must_precede_reasoning"]) is True
        and self_awareness_resident_completion_route_context_complete(packet.get("completion_route_context"))
        and {"promql_read", "logql_read", "self_awareness_context", "self_awareness_spatial_graph", "rag_validate", "nervous_brief", "requirements_handoff", "completion_route_packets", "resource_mode_gate"}.issubset(tool_kinds)
        and all(isinstance(tool, dict) and tool.get("read_only") is True and tool.get("host_layer_mutates_stack") is False and tool.get("stores_raw_body") is False and tool.get("evidence_refs") for tool in tools)
        and len(hypotheses) >= 3
        and all(isinstance(item, dict) and item.get("hypothesis") and item.get("verdict") and item.get("evidence_refs") for item in hypotheses)
        and bool(contradictions)
        and nested_get(packet, ["evidence_cited_summary", "evidence_refs"])
        and nested_get(packet, ["escalation_gate", "schema"]) == f"{SCHEMA_PREFIX}_self_awareness_resident_escalation_gate_v1"
        and nested_get(packet, ["escalation_gate", "human_approval_before_mutation"]) is True
        and nested_get(packet, ["escalation_gate", "host_layer_mutates_stack"]) is False
        and nested_get(packet, ["escalation_gate", "action_execution"]) is False
        and nested_get(packet, ["policy", "model_execution_in_this_graph"]) is False
        and nested_get(packet, ["policy", "direct_model_prompt_executed"]) is False
        and nested_get(packet, ["policy", "read_only_tools_only"]) is True
        and nested_get(packet, ["policy", "host_layer_mutates_stack"]) is False
        and nested_get(packet, ["policy", "human_approval_before_mutation"]) is True
    )


def resident_cognitive_replay_summary(
    investigation: dict[str, Any],
    state_by_node: dict[str, dict[str, Any]] | None = None,
    *,
    paths: SelfAwarenessResidentCognitivePaths,
    config: SelfAwarenessResidentCognitiveConfig,
    contract_port: SelfAwarenessResidentCognitiveContractPort,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    SELF_AWARENESS_INVESTIGATE_LATEST_PATH = paths.investigate_latest
    nested_get = self_awareness_contracts.nested_get
    stable_hash_json = self_awareness_contracts.stable_hash_json
    self_awareness_body_trace_complete = contract_port.body_trace_complete
    self_awareness_resident_cognitive_packet_complete = lambda document: resident_cognitive_packet_complete(
        document, config=config, contract_port=contract_port
    )
    self_awareness_resident_completion_route_context_complete = lambda document: resident_completion_route_context_complete(
        document, config=config
    )
    state_by_node = state_by_node if isinstance(state_by_node, dict) else {}
    packet = investigation.get("resident_cognitive_packet") if isinstance(investigation.get("resident_cognitive_packet"), dict) else {}
    body_trace = investigation.get("body_trace") if isinstance(investigation.get("body_trace"), dict) else packet.get("body_trace") if isinstance(packet.get("body_trace"), dict) else {}
    resident_state = state_by_node.get("resident_context_packet", {})
    reason_state = state_by_node.get("reason_over_evidence", {})
    conclusion = investigation.get("conclusion") if isinstance(investigation.get("conclusion"), dict) else {}
    checkpoint_packet = resident_state.get("resident_cognitive_packet") if isinstance(resident_state.get("resident_cognitive_packet"), dict) else {}
    checkpoint_body_trace = resident_state.get("body_trace") if isinstance(resident_state.get("body_trace"), dict) else checkpoint_packet.get("body_trace") if isinstance(checkpoint_packet.get("body_trace"), dict) else {}
    reason_body_trace = reason_state.get("body_trace") if isinstance(reason_state.get("body_trace"), dict) else {}
    conclusion_packet = conclusion.get("resident_cognitive_packet") if isinstance(conclusion.get("resident_cognitive_packet"), dict) else {}
    conclusion_body_trace = conclusion.get("body_trace") if isinstance(conclusion.get("body_trace"), dict) else {}
    completion_route_context = packet.get("completion_route_context") if isinstance(packet.get("completion_route_context"), dict) else {}
    checkpoint_completion_route_context = checkpoint_packet.get("completion_route_context") if isinstance(checkpoint_packet.get("completion_route_context"), dict) else resident_state.get("completion_route_context") if isinstance(resident_state.get("completion_route_context"), dict) else {}
    reason_completion_route_context = reason_state.get("completion_route_context") if isinstance(reason_state.get("completion_route_context"), dict) else {}
    conclusion_completion_route_context = conclusion.get("completion_route_context") if isinstance(conclusion.get("completion_route_context"), dict) else {}
    hypotheses = packet.get("hypothesis_tests") if isinstance(packet.get("hypothesis_tests"), list) else []
    reason_hypotheses = reason_state.get("hypotheses") if isinstance(reason_state.get("hypotheses"), list) else []
    contradictions = packet.get("contradiction_notes") if isinstance(packet.get("contradiction_notes"), list) else []
    reason_contradictions = reason_state.get("contradiction_notes") if isinstance(reason_state.get("contradiction_notes"), list) else []
    read_only_tools = packet.get("read_only_tools") if isinstance(packet.get("read_only_tools"), list) else []
    tool_kinds = sorted({str(tool.get("kind")) for tool in read_only_tools if isinstance(tool, dict) and tool.get("kind")})
    state_preservation = {
        "investigation_top_level": self_awareness_resident_cognitive_packet_complete(packet),
        "resident_context_packet": self_awareness_resident_cognitive_packet_complete(checkpoint_packet),
        "reason_over_evidence": len(reason_hypotheses) >= len(hypotheses) and bool(reason_contradictions),
        "write_semantic_conclusion": conclusion_packet.get("complete") is True and isinstance(conclusion.get("resident_worker"), dict),
        "body_trace": (
            self_awareness_body_trace_complete(body_trace)
            and self_awareness_body_trace_complete(checkpoint_body_trace)
            and self_awareness_body_trace_complete(reason_body_trace)
            and self_awareness_body_trace_complete(conclusion_body_trace)
        ),
        "completion_route_context": (
            self_awareness_resident_completion_route_context_complete(completion_route_context)
            and self_awareness_resident_completion_route_context_complete(checkpoint_completion_route_context)
            and self_awareness_resident_completion_route_context_complete(reason_completion_route_context)
            and self_awareness_resident_completion_route_context_complete(conclusion_completion_route_context)
        ),
    }
    policy = packet.get("policy") if isinstance(packet.get("policy"), dict) else {}
    complete = (
        all(state_preservation.values())
        and len(read_only_tools) >= 8
        and len(hypotheses) >= 3
        and bool(contradictions)
        and self_awareness_resident_completion_route_context_complete(completion_route_context)
        and nested_get(packet, ["evidence_cited_summary", "evidence_refs"])
        and policy.get("read_only_tools_only") is True
        and policy.get("action_execution") is False
        and policy.get("host_layer_mutates_stack") is False
        and policy.get("direct_model_prompt_executed") is False
        and nested_get(packet, ["escalation_gate", "host_layer_mutates_stack"]) is False
        and nested_get(packet, ["escalation_gate", "action_execution"]) is False
    )
    return {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_resident_cognitive_replay_v1",
        "worker": packet.get("worker") or "warm-e2b/gemma4.spark",
        "complete": bool(complete),
        "thread_id": investigation.get("thread_id"),
        "selected_episode_id": investigation.get("selected_episode_id"),
        "body_trace": body_trace,
        "completion_route_context": completion_route_context,
        "packet_digest": stable_hash_json(packet, length=24) if packet else None,
        "checkpoint_packet_digest": stable_hash_json(checkpoint_packet, length=24) if checkpoint_packet else None,
        "state_preservation": state_preservation,
        "read_only_tool_kinds": tool_kinds,
        "summary": {
            "read_only_tools": len(read_only_tools),
            "hypothesis_tests": len(hypotheses),
            "reason_hypotheses": len(reason_hypotheses),
            "contradiction_notes": len(contradictions),
            "reason_contradiction_notes": len(reason_contradictions),
            "body_trace_complete": self_awareness_body_trace_complete(body_trace),
            "completion_route_context_complete": self_awareness_resident_completion_route_context_complete(completion_route_context),
            "completion_route_packets": nested_get(completion_route_context, ["summary", "packets"]),
            "completion_route_packet_actions": nested_get(completion_route_context, ["summary", "covered_actions"]),
            "top_completion_route_id": nested_get(completion_route_context, ["top_packet", "route_id"]),
            "top_completion_route_path": nested_get(completion_route_context, ["top_packet", "route_path"]),
            "evidence_refs": len(nested_get(packet, ["evidence_cited_summary", "evidence_refs"]) or []),
            "escalation_status": nested_get(packet, ["escalation_gate", "model_execution_now", "status"]),
        },
        "evidence_cited_summary": packet.get("evidence_cited_summary") if isinstance(packet.get("evidence_cited_summary"), dict) else {},
        "escalation_gate": packet.get("escalation_gate") if isinstance(packet.get("escalation_gate"), dict) else {},
        "policy": {
            "read_only": True,
            "model_execution_in_this_graph": False,
            "direct_model_prompt_executed": policy.get("direct_model_prompt_executed") is True,
            "read_only_tools_only": policy.get("read_only_tools_only") is True,
            "action_execution": False,
            "auto_remediation": False,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "human_approval_before_mutation": True,
            "candidate_output_is_owner_truth": False,
        },
        "evidence_refs": [
            {"path": str(SELF_AWARENESS_INVESTIGATE_LATEST_PATH), "thread_id": investigation.get("thread_id"), "section": "resident_cognitive_packet"},
            {"path": str(SELF_AWARENESS_INVESTIGATE_LATEST_PATH), "thread_id": investigation.get("thread_id"), "section": "body_trace"},
            {"path": str(SELF_AWARENESS_INVESTIGATE_LATEST_PATH), "thread_id": investigation.get("thread_id"), "section": "completion_route_context"},
            {"path": str(SELF_AWARENESS_INVESTIGATE_LATEST_PATH), "thread_id": investigation.get("thread_id"), "section": "states.resident_context_packet"},
            {"path": str(SELF_AWARENESS_INVESTIGATE_LATEST_PATH), "thread_id": investigation.get("thread_id"), "section": "conclusion.resident_cognitive_packet"},
        ],
    }


def resident_cognitive_replay_complete(
    packet: Any,
    *,
    config: SelfAwarenessResidentCognitiveConfig,
    contract_port: SelfAwarenessResidentCognitiveContractPort,
) -> bool:
    SCHEMA_PREFIX = config.schema_prefix
    nested_get = self_awareness_contracts.nested_get
    safe_int = runtime_evidence_contracts.safe_int
    self_awareness_body_trace_complete = contract_port.body_trace_complete
    self_awareness_resident_completion_route_context_complete = lambda document: resident_completion_route_context_complete(
        document, config=config
    )
    if not isinstance(packet, dict):
        return False
    preservation = packet.get("state_preservation") if isinstance(packet.get("state_preservation"), dict) else {}
    required_preservation = {
        "investigation_top_level",
        "resident_context_packet",
        "reason_over_evidence",
        "write_semantic_conclusion",
        "body_trace",
        "completion_route_context",
    }
    return (
        packet.get("schema") == f"{SCHEMA_PREFIX}_self_awareness_resident_cognitive_replay_v1"
        and packet.get("worker") == "warm-e2b/gemma4.spark"
        and packet.get("complete") is True
        and required_preservation.issubset(set(preservation))
        and all(preservation.values())
        and safe_int(nested_get(packet, ["summary", "read_only_tools"]), 0) >= 8
        and safe_int(nested_get(packet, ["summary", "hypothesis_tests"]), 0) >= 3
        and safe_int(nested_get(packet, ["summary", "contradiction_notes"]), 0) >= 1
        and nested_get(packet, ["summary", "body_trace_complete"]) is True
        and nested_get(packet, ["summary", "completion_route_context_complete"]) is True
        and self_awareness_body_trace_complete(packet.get("body_trace"))
        and self_awareness_resident_completion_route_context_complete(packet.get("completion_route_context"))
        and bool(packet.get("packet_digest"))
        and bool(packet.get("checkpoint_packet_digest"))
        and bool(nested_get(packet, ["evidence_cited_summary", "evidence_refs"]))
        and nested_get(packet, ["policy", "read_only_tools_only"]) is True
        and nested_get(packet, ["policy", "direct_model_prompt_executed"]) is False
        and nested_get(packet, ["policy", "action_execution"]) is False
        and nested_get(packet, ["policy", "host_layer_mutates_stack"]) is False
        and nested_get(packet, ["policy", "human_approval_before_mutation"]) is True
        and bool(packet.get("evidence_refs"))
    )


def resident_cognitive_cycle_chain_overlay(
    cycle_chain: dict[str, Any],
    *,
    replay_doc: dict[str, Any] | None = None,
    export_doc: dict[str, Any] | None = None,
    write_latest: bool = True,
    paths: SelfAwarenessResidentCognitivePaths,
    config: SelfAwarenessResidentCognitiveConfig,
    runtime_port: SelfAwarenessResidentCognitiveRuntimePort,
    refresh_port: SelfAwarenessResidentCognitiveRefreshPort,
    contract_port: SelfAwarenessResidentCognitiveContractPort,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    SCHEMA_PREFIX = config.schema_prefix
    SELF_AWARENESS_REPLAY_LATEST_PATH = paths.replay_latest
    SELF_AWARENESS_EXPORT_LATEST_PATH = paths.export_latest
    load_latest_json = runtime_port.load_latest_json
    nested_get = self_awareness_contracts.nested_get
    self_awareness_replay = refresh_port.replay
    self_awareness_export = refresh_port.export
    self_awareness_resident_cognitive_replay_complete = lambda document: resident_cognitive_replay_complete(
        document, config=config, contract_port=contract_port
    )
    overlay = dict(cycle_chain) if isinstance(cycle_chain, dict) else {}
    replay_doc = replay_doc if isinstance(replay_doc, dict) else load_latest_json(SELF_AWARENESS_REPLAY_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_replay_v1")
    replay_packet = replay_doc.get("resident_cognitive_replay") if isinstance(replay_doc.get("resident_cognitive_replay"), dict) else {}
    if not self_awareness_resident_cognitive_replay_complete(replay_packet) and write_latest:
        replay_doc = self_awareness_replay(write_latest=True)
        replay_packet = replay_doc.get("resident_cognitive_replay") if isinstance(replay_doc.get("resident_cognitive_replay"), dict) else {}
    overlay["resident_cognitive_replay"] = self_awareness_resident_cognitive_replay_complete(replay_packet)

    export_doc = export_doc if isinstance(export_doc, dict) else load_latest_json(SELF_AWARENESS_EXPORT_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_export_v1")
    export_packet = export_doc.get("resident_cognitive_replay") if isinstance(export_doc.get("resident_cognitive_replay"), dict) else {}
    if not self_awareness_resident_cognitive_replay_complete(export_packet) and write_latest:
        export_doc = self_awareness_export(write_latest=True)
        export_packet = export_doc.get("resident_cognitive_replay") if isinstance(export_doc.get("resident_cognitive_replay"), dict) else {}
    if (
        nested_get(export_doc, ["portable_contract", "response_entity_event_document_context_included"]) is not True
        and write_latest
    ):
        export_doc = self_awareness_export(write_latest=True)
        export_packet = export_doc.get("resident_cognitive_replay") if isinstance(export_doc.get("resident_cognitive_replay"), dict) else {}
    overlay["resident_cognitive_export"] = self_awareness_resident_cognitive_replay_complete(export_packet)
    overlay["body_trace"] = (
        nested_get(replay_doc, ["body_trace_replay", "replayable"]) is True
        and nested_get(export_doc, ["body_trace_handoff", "host_body_context_packet_included"]) is True
        and nested_get(export_doc, ["body_trace_handoff", "resident_body_trace_replayable"]) is True
        and nested_get(export_doc, ["body_trace_handoff", "response_body_trace_included"]) is True
    )
    overlay["entity_event_document"] = (
        nested_get(export_doc, ["portable_contract", "response_entity_event_document_context_included"]) is True
        and nested_get(export_doc, ["response_entity_event_document_handoff", "complete"]) is True
    )
    return overlay, replay_doc, export_doc

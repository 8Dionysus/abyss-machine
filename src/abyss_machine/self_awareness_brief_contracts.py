from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import runtime_evidence_contracts
from . import self_awareness_contracts


DocumentPort = Callable[..., Any]


@dataclass(frozen=True)
class SelfAwarenessBriefPaths:
    timeline_latest: Path
    spatial_graph_latest: Path
    context_latest: Path
    episodes_latest: Path
    alerts_latest: Path
    reactions_latest: Path
    stack_observability_latest: Path
    capabilities_latest: Path
    requirement_probes_latest: Path
    export_latest: Path
    ai_capabilities_latest: Path
    llm_resident_status_latest: Path
    rag_validate_latest: Path
    nervous_brief_latest: Path
    probe_latest: Path
    brief_latest: Path
    brief_root: Path


@dataclass(frozen=True)
class SelfAwarenessBriefConfig:
    schema_prefix: str
    version: str


@dataclass(frozen=True)
class SelfAwarenessBriefRuntimePort:
    load_latest_json: DocumentPort
    now_iso: DocumentPort
    write_latest_and_history: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessBriefRefreshPort:
    timeline: DocumentPort
    spatial_graph: DocumentPort
    context: DocumentPort
    episodes: DocumentPort
    alerts: DocumentPort
    requirement_probes: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessBriefContractPort:
    memory_space_freshness_handoff: DocumentPort
    stack_requirement_coverage_impact: DocumentPort
    stack_coverage_impact_complete: DocumentPort


def build_stack_handoff_action_map(
    requirement_probes: dict[str, Any],
    *,
    paths: SelfAwarenessBriefPaths,
    config: SelfAwarenessBriefConfig,
    runtime_port: SelfAwarenessBriefRuntimePort,
    contract_port: SelfAwarenessBriefContractPort,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    VERSION = config.version
    SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH = paths.requirement_probes_latest
    SELF_AWARENESS_EXPORT_LATEST_PATH = paths.export_latest
    now_iso = runtime_port.now_iso
    nested_get = self_awareness_contracts.nested_get
    safe_int = runtime_evidence_contracts.safe_int
    self_awareness_stack_requirement_coverage_impact = contract_port.stack_requirement_coverage_impact
    self_awareness_stack_coverage_impact_complete = contract_port.stack_coverage_impact_complete
    generated_at = now_iso()
    probes = [
        probe for probe in (requirement_probes.get("probes") if isinstance(requirement_probes.get("probes"), list) else [])
        if isinstance(probe, dict)
    ]
    open_probes = [probe for probe in probes if probe.get("closed_by_current_probe") is not True]

    def priority_for(probe: dict[str, Any], blockers: list[dict[str, Any]]) -> tuple[int, str, list[str]]:
        requirement_id = str(probe.get("id") or probe.get("requirement_id") or "")
        reasons = ["open_stack_owned_requirement"]
        score = 40 + (len(blockers) * 8)
        priority_class = "stack_handoff"
        if requirement_id == "stack.trace-backend":
            score += 40
            priority_class = "critical_trace_join"
            reasons.append("unlocks_span_log_metric_join_and_langgraph_trace_coupling")
        elif requirement_id == "stack.langchain-api.graph-observability":
            score += 34
            priority_class = "critical_replay_inventory"
            reasons.append("unlocks_thread_checkpoint_trace_replay_inventory")
        elif requirement_id == "stack.database-graph.read-route":
            score += 28
            priority_class = "critical_memory_space_inventory"
            reasons.append("unlocks_postgres_neo4j_spatial_memory_inventory")
        elif requirement_id == "stack.grafana.datasource-read":
            score += 20
            priority_class = "dashboard_source_inventory"
            reasons.append("unlocks_authoritative_dashboard_datasource_identity")
        if any(blocker.get("key") == "langchain_trace_backend_coupled" for blocker in blockers):
            score += 10
            reasons.append("depends_on_trace_backend_coupling")
        return score, priority_class, reasons

    actions: list[dict[str, Any]] = []
    for probe in open_probes:
        requirement_id = str(probe.get("id") or probe.get("requirement_id") or "")
        checks = probe.get("checks") if isinstance(probe.get("checks"), list) else []
        blockers = [
            {
                "key": check.get("key"),
                "level": check.get("level"),
                "ok": check.get("ok"),
                "message": check.get("message"),
                "data": check.get("data"),
            }
            for check in checks
            if isinstance(check, dict)
            and (check.get("ok") is not True or str(check.get("level") or "").lower() in {"open", "warn", "fail"})
        ]
        runbook = probe.get("runbook_candidate") if isinstance(probe.get("runbook_candidate"), dict) else {}
        closure_readiness = probe.get("closure_readiness") if isinstance(probe.get("closure_readiness"), dict) else {}
        verifiers = probe.get("acceptance_verifiers") if isinstance(probe.get("acceptance_verifiers"), list) else []
        score, priority_class, priority_reasons = priority_for(probe, blockers)
        coverage_impact = self_awareness_stack_requirement_coverage_impact(requirement_id)
        action = {
            "id": "stack-handoff:" + (requirement_id or "unknown"),
            "requirement_id": requirement_id,
            "owner_route": probe.get("owner") or "abyss-stack",
            "status": probe.get("status"),
            "priority_score": score,
            "priority_class": priority_class,
            "priority_reasons": priority_reasons,
            "probe_kind": probe.get("probe_kind"),
            "closure_blockers": blockers,
            "closure_blocker_keys": [str(blocker.get("key")) for blocker in blockers if blocker.get("key")],
            "closure_readiness": closure_readiness,
            "current_state": probe.get("current_state"),
            "coverage_impact": coverage_impact,
            "impact_organ": coverage_impact.get("organ"),
            "coverage_planes": coverage_impact.get("coverage_planes") if isinstance(coverage_impact.get("coverage_planes"), list) else [],
            "runbook_candidate_id": runbook.get("id"),
            "runbook_candidate": {
                "schema": runbook.get("schema"),
                "id": runbook.get("id"),
                "machine_action": runbook.get("machine_action"),
                "host_layer_mutates_stack": runbook.get("host_layer_mutates_stack"),
                "machine_executes_stack_change": runbook.get("machine_executes_stack_change"),
                "stack_owner_may_mutate_stack": runbook.get("stack_owner_may_mutate_stack"),
                "operator_approval_required": runbook.get("operator_approval_required"),
                "acceptance_steps": runbook.get("acceptance_steps"),
                "acceptance_verifiers": runbook.get("acceptance_verifiers"),
                "risk": runbook.get("risk"),
                "blast_radius": runbook.get("blast_radius"),
                "rollback": runbook.get("rollback"),
                "policy": runbook.get("policy"),
            } if runbook else None,
            "acceptance_verifiers": verifiers,
            "verifier_commands": [str(item.get("command")) for item in verifiers if isinstance(item, dict) and item.get("command")],
            "evidence_refs": probe.get("evidence_refs") if isinstance(probe.get("evidence_refs"), list) else [],
            "safe_next_action": {
                "kind": "stack_owner_review_handoff",
                "owner_route": "abyss-stack",
                "command": "abyss-machine self-awareness export --json",
                "source_brief_command": "abyss-machine self-awareness brief --json",
                "requirement_probe_command": "abyss-machine self-awareness requirement-probes --json",
                "automatic": False,
                "requires_human_approval": True,
                "executes_commands": False,
                "host_layer_mutates_stack": False,
                "action_execution": False,
                "machine_action": "handoff_only",
                "rollback": "discard/regenerate machine-owned brief/export/latest artifacts; abyss-machine did not change stack state",
            },
            "policy": {
                "handoff_only": True,
                "automatic": False,
                "requires_human_approval": True,
                "executes_commands": False,
                "host_layer_mutates_stack": False,
                "actions_executed": False,
                "raw_secrets_included": False,
            },
        }
        actions.append(action)

    actions.sort(key=lambda item: (-safe_int(item.get("priority_score"), 0), str(item.get("requirement_id") or "")))
    for index, action in enumerate(actions, start=1):
        action["priority_rank"] = index
    coverage_impacts = [
        action.get("coverage_impact")
        for action in actions
        if isinstance(action, dict) and isinstance(action.get("coverage_impact"), dict)
    ]
    blocked_coverage_planes = sorted({
        str(plane)
        for impact in coverage_impacts
        for plane in (impact.get("coverage_planes") if isinstance(impact.get("coverage_planes"), list) else [])
        if plane
    })
    top_action = actions[0]["safe_next_action"] if actions else {
        "kind": "no_open_stack_handoff",
        "command": "abyss-machine self-awareness validate --json",
        "automatic": False,
        "requires_human_approval": True,
        "executes_commands": False,
        "host_layer_mutates_stack": False,
        "action_execution": False,
        "rollback": "no stack state changed",
    }
    return {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_brief_stack_handoff_action_map_v1",
        "version": VERSION,
        "generated_at": generated_at,
        "ok": bool(requirement_probes.get("ok", True))
        and all(nested_get(action, ["policy", "host_layer_mutates_stack"]) is False for action in actions)
        and all(action.get("acceptance_verifiers") for action in actions)
        and all(self_awareness_stack_coverage_impact_complete(action.get("coverage_impact")) for action in actions),
        "status": "open_requirements" if actions else "satisfied",
        "summary": {
            "open_stack_requirements": len(actions),
            "actions": len(actions),
            "runbook_candidates": sum(1 for action in actions if isinstance(action.get("runbook_candidate"), dict)),
            "acceptance_verifier_steps": sum(len(action.get("acceptance_verifiers") if isinstance(action.get("acceptance_verifiers"), list) else []) for action in actions),
            "closure_blockers": sum(len(action.get("closure_blockers") if isinstance(action.get("closure_blockers"), list) else []) for action in actions),
            "closure_readiness_packets": sum(1 for action in actions if isinstance(action.get("closure_readiness"), dict)),
            "closure_readiness_missing_checks": sum(safe_int(nested_get(action, ["closure_readiness", "open_blocker_count"]), 0) for action in actions),
            "coverage_impact_entries": len(coverage_impacts),
            "blocked_coverage_planes": blocked_coverage_planes,
            "top_requirement_id": actions[0].get("requirement_id") if actions else None,
            "top_priority_class": actions[0].get("priority_class") if actions else None,
        },
        "actions": actions,
        "open_requirement_ids": [str(action.get("requirement_id")) for action in actions],
        "safe_next_action": top_action,
        "source_commands": [
            "abyss-machine self-awareness brief --json",
            "abyss-machine self-awareness requirement-probes --json",
            "abyss-machine self-awareness export --json",
            "abyss-machine self-awareness cycle --json",
            "abyss-machine self-awareness validate --json",
            "abyss-machine stack-bridge validate --json",
        ],
        "evidence_refs": [
            {"path": str(SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH), "schema": requirement_probes.get("schema")},
            {"path": str(SELF_AWARENESS_EXPORT_LATEST_PATH), "schema": f"{SCHEMA_PREFIX}_self_awareness_export_v1"},
        ],
        "policy": {
            "handoff_only": True,
            "automatic": False,
            "requires_human_approval": True,
            "executes_commands": False,
            "host_layer_mutates_stack": False,
            "actions_executed": False,
            "open_stack_requirements_are_blockers_not_host_failures": True,
            "raw_secrets_included": False,
        },
    }



def brief(
    write_latest: bool = True,
    *,
    paths: SelfAwarenessBriefPaths,
    config: SelfAwarenessBriefConfig,
    runtime_port: SelfAwarenessBriefRuntimePort,
    refresh_port: SelfAwarenessBriefRefreshPort,
    contract_port: SelfAwarenessBriefContractPort,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    VERSION = config.version
    SELF_AWARENESS_TIMELINE_LATEST_PATH = paths.timeline_latest
    SELF_AWARENESS_SPATIAL_GRAPH_LATEST_PATH = paths.spatial_graph_latest
    SELF_AWARENESS_CONTEXT_LATEST_PATH = paths.context_latest
    SELF_AWARENESS_EPISODES_LATEST_PATH = paths.episodes_latest
    SELF_AWARENESS_ALERTS_LATEST_PATH = paths.alerts_latest
    REACTIONS_LATEST_PATH = paths.reactions_latest
    STACK_OBSERVABILITY_LATEST_PATH = paths.stack_observability_latest
    SELF_AWARENESS_CAPABILITIES_LATEST_PATH = paths.capabilities_latest
    SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH = paths.requirement_probes_latest
    SELF_AWARENESS_EXPORT_LATEST_PATH = paths.export_latest
    AI_CAPABILITIES_LATEST_PATH = paths.ai_capabilities_latest
    AI_LLM_RESIDENT_STATUS_LATEST_PATH = paths.llm_resident_status_latest
    RAG_VALIDATE_LATEST_PATH = paths.rag_validate_latest
    NERVOUS_BRIEF_LATEST_PATH = paths.nervous_brief_latest
    SELF_AWARENESS_PROBE_LATEST_PATH = paths.probe_latest
    SELF_AWARENESS_BRIEF_LATEST_PATH = paths.brief_latest
    SELF_AWARENESS_BRIEF_ROOT = paths.brief_root
    load_latest_json = runtime_port.load_latest_json
    now_iso = runtime_port.now_iso
    write_latest_and_history = runtime_port.write_latest_and_history
    self_awareness_timeline = refresh_port.timeline
    self_awareness_spatial_graph = refresh_port.spatial_graph
    self_awareness_context = refresh_port.context
    self_awareness_episodes = refresh_port.episodes
    self_awareness_alerts = refresh_port.alerts
    self_awareness_requirement_probes = refresh_port.requirement_probes
    self_awareness_memory_space_freshness_handoff = contract_port.memory_space_freshness_handoff
    self_awareness_brief_stack_handoff_action_map = lambda requirement_probes: build_stack_handoff_action_map(
        requirement_probes,
        paths=paths,
        config=config,
        runtime_port=runtime_port,
        contract_port=contract_port,
    )
    nested_get = self_awareness_contracts.nested_get
    safe_int = runtime_evidence_contracts.safe_int
    timeline = self_awareness_timeline(write_latest=True)
    graph = self_awareness_spatial_graph(write_latest=True)
    context = self_awareness_context(write_latest=True)
    episodes = self_awareness_episodes(write_latest=True)
    alerts = self_awareness_alerts(write_latest=True)
    stack = load_latest_json(STACK_OBSERVABILITY_LATEST_PATH, f"{SCHEMA_PREFIX}_stack_observability_v1")
    reaction_latest = load_latest_json(REACTIONS_LATEST_PATH, f"{SCHEMA_PREFIX}_reactions_status_v1")
    capabilities = load_latest_json(SELF_AWARENESS_CAPABILITIES_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_capabilities_v1")
    requirement_probes = self_awareness_requirement_probes(write_latest=True, capabilities=capabilities if capabilities.get("schema") else None)
    stack_handoff_action_map = self_awareness_brief_stack_handoff_action_map(requirement_probes)
    stack_safe_next_action = stack_handoff_action_map.get("safe_next_action") if isinstance(stack_handoff_action_map.get("safe_next_action"), dict) else {}
    ai_caps = load_latest_json(AI_CAPABILITIES_LATEST_PATH, f"{SCHEMA_PREFIX}_ai_capabilities_v1")
    llm_resident_status = load_latest_json(AI_LLM_RESIDENT_STATUS_LATEST_PATH, f"{SCHEMA_PREFIX}_gemma4_spark_resident_status_v1")
    rag_validation = load_latest_json(RAG_VALIDATE_LATEST_PATH, f"{SCHEMA_PREFIX}_rag_validate_v1")
    nervous = load_latest_json(NERVOUS_BRIEF_LATEST_PATH, f"{SCHEMA_PREFIX}_nervous_brief_v1")
    memory_space_freshness = self_awareness_memory_space_freshness_handoff(context)
    claims = [
        {
            "claim": "Stack observability core is ready" if stack.get("ok") else "Stack observability core is degraded",
            "truth_level": "raw",
            "confidence": 0.9,
            "refs": [{"path": str(STACK_OBSERVABILITY_LATEST_PATH), "summary": stack.get("summary")}],
        },
        {
            "claim": f"Self-awareness timeline contains {nested_get(timeline, ['summary', 'events']) or 0} normalized events.",
            "truth_level": "normalized",
            "confidence": 0.85,
            "refs": [{"path": str(SELF_AWARENESS_TIMELINE_LATEST_PATH), "summary": timeline.get("summary")}],
        },
        {
            "claim": f"Spatial overlay has {nested_get(graph, ['summary', 'nodes']) or 0} nodes and {nested_get(graph, ['summary', 'edges']) or 0} edges.",
            "truth_level": "normalized",
            "confidence": 0.82,
            "refs": [{"path": str(SELF_AWARENESS_SPATIAL_GRAPH_LATEST_PATH), "summary": graph.get("summary")}],
        },
        {
            "claim": f"Causal episode candidates: {nested_get(episodes, ['summary', 'episodes']) or 0}.",
            "truth_level": "inferred",
            "confidence": 0.68,
            "refs": [{"path": str(SELF_AWARENESS_EPISODES_LATEST_PATH), "summary": episodes.get("summary")}],
        },
        {
            "claim": f"Open self-awareness reaction candidates: {nested_get(alerts, ['summary', 'reaction_candidates']) or 0}.",
            "truth_level": "candidate",
            "confidence": 0.8,
            "refs": [{"path": str(SELF_AWARENESS_ALERTS_LATEST_PATH), "summary": alerts.get("summary")}, {"path": str(REACTIONS_LATEST_PATH), "summary": reaction_latest.get("summary")}],
        },
        {
            "claim": "warm-E2B/gemma4.spark resident worker is running" if llm_resident_status.get("status") == "running" else "warm-E2B/gemma4.spark resident worker is not proven running",
            "truth_level": "raw",
            "confidence": 0.9 if llm_resident_status.get("status") == "running" else 0.55,
            "refs": [{"path": str(AI_LLM_RESIDENT_STATUS_LATEST_PATH), "status": llm_resident_status.get("status"), "model": llm_resident_status.get("model")}],
        },
        {
            "claim": f"AI capability map covers {len(ai_caps.get('capabilities') if isinstance(ai_caps.get('capabilities'), dict) else {})} modality surfaces.",
            "truth_level": "raw",
            "confidence": 0.84,
            "refs": [{"path": str(AI_CAPABILITIES_LATEST_PATH), "ok": ai_caps.get("ok"), "capabilities": sorted((ai_caps.get("capabilities") or {}).keys()) if isinstance(ai_caps.get("capabilities"), dict) else []}],
        },
        {
            "claim": "RAG trace/eval validation is passing" if rag_validation.get("ok") else "RAG validation is degraded or missing",
            "truth_level": "raw",
            "confidence": 0.85 if rag_validation.get("ok") else 0.55,
            "refs": [{"path": str(RAG_VALIDATE_LATEST_PATH), "summary": rag_validation.get("summary")}],
        },
        {
            "claim": (
                f"Memory-space overlay has {nested_get(context, ['summary', 'memory_space', 'retrieval_packets']) or 0} "
                f"bounded retrieval packets and {nested_get(context, ['summary', 'memory_space', 'freshness_gates']) or 0} freshness gates."
            ),
            "truth_level": "normalized",
            "confidence": 0.82,
            "refs": [{"path": str(SELF_AWARENESS_CONTEXT_LATEST_PATH), "summary": nested_get(context, ["summary", "memory_space"])}],
        },
        {
            "claim": f"Nervous freshness gate reports {nested_get(nervous, ['readiness', 'status']) or 'unknown'} readiness.",
            "truth_level": "raw",
            "confidence": 0.8 if nervous.get("readiness") else 0.45,
            "refs": [
                {"path": str(NERVOUS_BRIEF_LATEST_PATH), "readiness": nervous.get("readiness"), "next_actions": nervous.get("next_actions")},
                {
                    "path": str(SELF_AWARENESS_CONTEXT_LATEST_PATH),
                    "section": "memory_space_freshness",
                    "summary": memory_space_freshness.get("summary"),
                },
            ],
        },
        {
            "claim": f"Full-stack capability map has {nested_get(capabilities, ['summary', 'capabilities']) or 0} capabilities and {nested_get(capabilities, ['summary', 'requirements']) or 0} owner-routed requirements.",
            "truth_level": "normalized",
            "confidence": 0.82,
            "refs": [{"path": str(SELF_AWARENESS_CAPABILITIES_LATEST_PATH), "summary": capabilities.get("summary")}],
        },
        {
            "claim": (
                f"Stack handoff action map has {nested_get(stack_handoff_action_map, ['summary', 'open_stack_requirements']) or 0} "
                f"open stack-owned blockers and {nested_get(stack_handoff_action_map, ['summary', 'acceptance_verifier_steps']) or 0} verifier steps."
            ),
            "truth_level": "handoff",
            "confidence": 0.86,
            "refs": [
                {"path": str(SELF_AWARENESS_BRIEF_LATEST_PATH), "section": "stack_handoff_action_map", "summary": stack_handoff_action_map.get("summary")},
                {"path": str(SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH), "summary": requirement_probes.get("summary")},
            ],
        },
    ]
    missing_evidence = []
    if nested_get(context, ["summary", "degraded"]):
        missing_evidence.append("Full downstream trace propagation is not proven for every stack service.")
    if nested_get(context, ["summary", "memory_space", "blocked_gates"]):
        missing_evidence.append("One or more memory-space freshness gates block deep reasoning until maintenance runs.")
    if not (nested_get(episodes, ["summary", "high_confidence"]) or 0):
        missing_evidence.append("No high-confidence causal episode exists without synthetic/context linkage.")
    if nested_get(nervous, ["readiness", "semantic_maintenance_needed"]):
        missing_evidence.append("Nervous semantic maintenance is needed before deep resident reasoning should be treated as fresh.")
    if llm_resident_status.get("status") != "running":
        missing_evidence.append("warm-E2B resident worker is not currently proven running.")
    if safe_int(nested_get(stack_handoff_action_map, ["summary", "open_stack_requirements"]), 0) > 0:
        missing_evidence.append("Open stack-owned handoff blockers remain; use brief.stack_handoff_action_map or export.stack_handoff before stack-owner work.")
    data = {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_brief_v1",
        "version": VERSION,
        "generated_at": now_iso(),
        "ok": all(claim.get("refs") for claim in claims),
        "summary": {
            "status": "ready" if stack.get("ok") and timeline.get("ok") and graph.get("ok") else "degraded",
            "claims": len(claims),
            "missing_evidence": len(missing_evidence),
            "episodes": nested_get(episodes, ["summary", "episodes"]),
            "reaction_candidates": nested_get(alerts, ["summary", "reaction_candidates"]),
            "stack_handoff_open": nested_get(stack_handoff_action_map, ["summary", "open_stack_requirements"]),
            "stack_handoff_actions": nested_get(stack_handoff_action_map, ["summary", "actions"]),
            "stack_handoff_verifier_steps": nested_get(stack_handoff_action_map, ["summary", "acceptance_verifier_steps"]),
        },
        "what_changed_recently": {
            "events": nested_get(timeline, ["summary", "events"]),
            "latest_event_time": nested_get(timeline, ["summary", "latest_event_time"]),
            "refs": [{"path": str(SELF_AWARENESS_TIMELINE_LATEST_PATH)}],
        },
        "healthy": [
            {"item": "Prometheus/Grafana/Loki/Alloy bridge", "status": nested_get(stack, ["summary", "status"]), "refs": [{"path": str(STACK_OBSERVABILITY_LATEST_PATH)}]},
            {"item": "warm-E2B resident worker", "status": llm_resident_status.get("status"), "refs": [{"path": str(AI_LLM_RESIDENT_STATUS_LATEST_PATH)}]},
            {"item": "RAG validation", "status": nested_get(rag_validation, ["summary", "status"]), "refs": [{"path": str(RAG_VALIDATE_LATEST_PATH)}]},
        ],
        "degraded": missing_evidence,
        "spatial_impact": {"summary": graph.get("summary"), "refs": [{"path": str(SELF_AWARENESS_SPATIAL_GRAPH_LATEST_PATH)}]},
        "causal_episodes": {"summary": episodes.get("summary"), "refs": [{"path": str(SELF_AWARENESS_EPISODES_LATEST_PATH)}]},
        "reaction_candidates": {"summary": alerts.get("summary"), "refs": [{"path": str(SELF_AWARENESS_ALERTS_LATEST_PATH), "path_reactions": str(REACTIONS_LATEST_PATH)}]},
        "memory_space_freshness": memory_space_freshness,
        "stack_handoff_action_map": stack_handoff_action_map,
        "stack_handoff": {
            "summary": stack_handoff_action_map.get("summary"),
            "open_requirement_ids": stack_handoff_action_map.get("open_requirement_ids"),
            "actions": stack_handoff_action_map.get("actions"),
            "policy": stack_handoff_action_map.get("policy"),
            "refs": stack_handoff_action_map.get("evidence_refs"),
        },
        "open_requirements": stack_handoff_action_map.get("actions"),
        "runbook_candidates": [
            action.get("runbook_candidate")
            for action in (stack_handoff_action_map.get("actions") if isinstance(stack_handoff_action_map.get("actions"), list) else [])
            if isinstance(action, dict) and isinstance(action.get("runbook_candidate"), dict)
        ],
        "safe_next_action": stack_safe_next_action,
        "next_safe_action": stack_safe_next_action,
        "claims": claims,
        "next_checks": [
            {
                "command": "abyss-machine self-awareness export --json",
                "reason": "open the portable one-file stack-owner handoff packet before stack-side work",
                "refs": [{"path": str(SELF_AWARENESS_EXPORT_LATEST_PATH), "section": "stack_handoff"}],
            },
            {
                "command": "abyss-machine self-awareness requirement-probes --json",
                "reason": "refresh stack-owned closure blockers, runbook candidates, and acceptance verifiers",
                "refs": [{"path": str(SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH)}],
            },
            {
                "command": "abyss-machine self-awareness probe --json",
                "reason": "refresh full request-to-brief proof chain",
                "refs": [{"path": str(SELF_AWARENESS_PROBE_LATEST_PATH)}],
            },
            {
                "command": "abyss-machine self-awareness context --json",
                "reason": "inspect trace/context degradation before claiming full propagation",
                "refs": [{"path": str(SELF_AWARENESS_CONTEXT_LATEST_PATH)}],
            },
        ],
        "policy": {
            "claim_without_refs": False,
            "distinguish_raw_inferred_candidate": True,
            "host_layer_mutates_stack": False,
            "actions_executed": False,
            "open_stack_requirements_are_blockers_not_host_failures": True,
        },
        "tests": {
            "claim_refs": "validator checks every claim has refs",
            "redaction": "events store redacted previews only",
        },
    }
    if write_latest:
        errors = write_latest_and_history(data, SELF_AWARENESS_BRIEF_LATEST_PATH, SELF_AWARENESS_BRIEF_ROOT)
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data

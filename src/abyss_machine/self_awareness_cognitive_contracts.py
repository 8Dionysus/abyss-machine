from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from pathlib import Path
import shlex
from typing import Any, Callable

from . import self_awareness_contracts


DocumentPort = Callable[..., Any]


@dataclass(frozen=True)
class SelfAwarenessCognitivePaths:
    context_latest: Path
    trace_context_latest: Path
    capabilities_latest: Path
    requirement_probes_latest: Path
    spatial_graph_latest: Path
    ai_capabilities_latest: Path
    ai_devices_latest: Path
    ai_llm_registry_latest: Path
    ai_models_latest: Path
    ai_tts_eval_latest_success: Path
    ai_tts_profiles_latest: Path
    abyss_stack_user_source_root: Path
    ai_llm_workhorse_pack_latest: Path
    ai_llm_workhorse_preflight_latest: Path
    ai_llm_workhorse_review_latest: Path
    ai_llm_workhorse_validate_latest: Path
    mode_latest: Path
    resource_latest: Path
    episodes_latest: Path


@dataclass(frozen=True)
class SelfAwarenessCognitiveConfig:
    schema_prefix: str
    semantic_maintain_review_command: str
    semantic_maintain_retry_command: str


@dataclass(frozen=True)
class SelfAwarenessCognitiveContractPort:
    trace_context_fallback_complete: DocumentPort
    resident_worker_detail_complete: DocumentPort
    stack_coverage_impact_complete: DocumentPort


stable_hash_json = self_awareness_contracts.stable_hash_json
nested_get = self_awareness_contracts.nested_get


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def compact_freshness_gate(gate: dict[str, Any]) -> dict[str, Any]:
    details = gate.get("details") if isinstance(gate.get("details"), dict) else {}
    semantic_maintain = (
        details.get("semantic_maintain")
        if isinstance(details.get("semantic_maintain"), dict)
        else {}
    )
    readiness = (
        details.get("readiness") if isinstance(details.get("readiness"), dict) else {}
    )
    policy = details.get("policy") if isinstance(details.get("policy"), dict) else {}
    evidence_refs = (
        gate.get("evidence_refs") if isinstance(gate.get("evidence_refs"), list) else []
    )
    blocked_reasons = sorted(
        {
            str(reason)
            for key in ("index_refresh_blocked_reasons", "build_blocked_reasons")
            for reason in (
                semantic_maintain.get(key)
                if isinstance(semantic_maintain.get(key), list)
                else []
            )
            if reason
        }
    )
    denied_reasons = sorted(
        {
            str(reason)
            for key in ("index_refresh_denied_reasons", "build_denied_reasons")
            for reason in (
                semantic_maintain.get(key)
                if isinstance(semantic_maintain.get(key), list)
                else []
            )
            if reason
        }
    )
    compact = {
        "gate_id": gate.get("gate_id"),
        "status": gate.get("status"),
        "maintenance_route": gate.get("maintenance_route"),
        "blocks_deep_reasoning": gate.get("blocks_deep_reasoning"),
        "freshness_must_precede_reasoning": gate.get(
            "freshness_must_precede_reasoning"
        ),
        "raw_evidence_is_not_truth": gate.get("raw_evidence_is_not_truth"),
        "readiness_status": readiness.get("status"),
        "resource_denial_is_safe_gate": details.get("resource_denial_is_safe_gate"),
        "blocked_reasons": blocked_reasons,
        "denied_reasons": denied_reasons,
        "evidence_refs": [
            {
                "path": ref.get("path"),
                "schema": ref.get("schema"),
                "truth_level": ref.get("truth_level"),
                "ok": ref.get("ok"),
                "generated_at": ref.get("generated_at"),
            }
            for ref in evidence_refs
            if isinstance(ref, dict)
        ],
        "policy": {
            "does_not_bypass_resource_gate": policy.get(
                "does_not_bypass_resource_gate"
            ),
            "automatic_remediation": policy.get("automatic_remediation"),
            "host_layer_mutates_stack": policy.get("host_layer_mutates_stack"),
        },
    }
    if semantic_maintain:
        compact["semantic_maintain"] = {
            "decision": semantic_maintain.get("decision"),
            "reason": semantic_maintain.get("reason"),
            "ok": semantic_maintain.get("ok"),
            "resource": semantic_maintain.get("resource")
            if isinstance(semantic_maintain.get("resource"), dict)
            else {},
            "assessment": {
                "needed": nested_get(semantic_maintain, ["assessment", "needed"]),
                "stale": nested_get(semantic_maintain, ["assessment", "stale"]),
                "reasons": nested_get(semantic_maintain, ["assessment", "reasons"]),
                "semantic_age_minutes": nested_get(
                    semantic_maintain, ["assessment", "semantic_age_minutes"]
                ),
                "source_index_changed": nested_get(
                    semantic_maintain, ["assessment", "source_index_changed"]
                ),
            },
            "index_refresh_assessment": {
                "needed": nested_get(
                    semantic_maintain, ["index_refresh_assessment", "needed"]
                ),
                "stale": nested_get(
                    semantic_maintain, ["index_refresh_assessment", "stale"]
                ),
                "records_lag": nested_get(
                    semantic_maintain, ["index_refresh_assessment", "records_lag"]
                ),
                "run_id": nested_get(
                    semantic_maintain, ["index_refresh_assessment", "run_id"]
                ),
                "built_at": nested_get(
                    semantic_maintain, ["index_refresh_assessment", "built_at"]
                ),
            },
        }
    return compact


def memory_space_freshness_handoff(
    context_doc: dict[str, Any],
    *,
    paths: SelfAwarenessCognitivePaths,
    config: SelfAwarenessCognitiveConfig,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    SELF_AWARENESS_CONTEXT_LATEST_PATH = paths.context_latest
    self_awareness_compact_freshness_gate = compact_freshness_gate
    memory_space = (
        context_doc.get("memory_space")
        if isinstance(context_doc.get("memory_space"), dict)
        else {}
    )
    gates = (
        memory_space.get("freshness_gates")
        if isinstance(memory_space.get("freshness_gates"), list)
        else []
    )
    compact_gates = [
        self_awareness_compact_freshness_gate(gate)
        for gate in gates
        if isinstance(gate, dict)
    ]
    blocked_gates = [
        gate
        for gate in compact_gates
        if gate.get("blocks_deep_reasoning")
        or str(gate.get("status") or "") in {"stale", "blocked", "missing", "invalid"}
    ]
    resource_denial_gates = [
        gate
        for gate in blocked_gates
        if gate.get("resource_denial_is_safe_gate") is True
        or bool(gate.get("blocked_reasons"))
        or bool(gate.get("denied_reasons"))
    ]
    return {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_memory_space_freshness_handoff_v1",
        "complete": bool(compact_gates)
        and nested_get(memory_space, ["policy", "freshness_must_precede_reasoning"])
        is True,
        "summary": {
            "gates": len(compact_gates),
            "blocked_gates": len(blocked_gates),
            "resource_denial_gates": len(resource_denial_gates),
            "blocked_gate_ids": [
                str(gate.get("gate_id"))
                for gate in blocked_gates
                if gate.get("gate_id")
            ],
            "resource_denial_gate_ids": [
                str(gate.get("gate_id"))
                for gate in resource_denial_gates
                if gate.get("gate_id")
            ],
        },
        "blocked_gates": blocked_gates,
        "resource_denial_gates": resource_denial_gates,
        "evidence_refs": [
            {
                "path": str(SELF_AWARENESS_CONTEXT_LATEST_PATH),
                "section": "memory_space.freshness_gates",
            },
            *[
                ref
                for gate in resource_denial_gates
                for ref in (
                    gate.get("evidence_refs")
                    if isinstance(gate.get("evidence_refs"), list)
                    else []
                )
                if isinstance(ref, dict)
            ],
        ],
        "policy": {
            "freshness_must_precede_reasoning": True,
            "raw_evidence_is_not_truth": True,
            "does_not_bypass_resource_gate": all(
                (
                    nested_get(gate, ["policy", "does_not_bypass_resource_gate"])
                    is not False
                    for gate in resource_denial_gates
                )
            ),
            "automatic_remediation": False,
            "host_layer_mutates_stack": False,
        },
    }


def compact_trace_join_context(
    trace_context: dict[str, Any] | None,
    *,
    config: SelfAwarenessCognitiveConfig,
    contract_port: SelfAwarenessCognitiveContractPort,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    self_awareness_trace_context_fallback_complete = (
        contract_port.trace_context_fallback_complete
    )
    trace_context = trace_context if isinstance(trace_context, dict) else {}
    summary = (
        trace_context.get("summary")
        if isinstance(trace_context.get("summary"), dict)
        else {}
    )
    fallback = (
        trace_context.get("fallback")
        if isinstance(trace_context.get("fallback"), dict)
        else {}
    )
    loki_trace = (
        fallback.get("loki_trace_context")
        if isinstance(fallback.get("loki_trace_context"), dict)
        else {}
    )
    pipeline = (
        fallback.get("alloy_loki_pipeline")
        if isinstance(fallback.get("alloy_loki_pipeline"), dict)
        else {}
    )
    missing_checks = (
        summary.get("missing_checks")
        if isinstance(summary.get("missing_checks"), list)
        else []
    )
    evidence_refs = (
        trace_context.get("evidence_refs")
        if isinstance(trace_context.get("evidence_refs"), list)
        else []
    )
    policy = (
        trace_context.get("policy")
        if isinstance(trace_context.get("policy"), dict)
        else {}
    )
    safe_next_action = (
        trace_context.get("safe_next_action")
        if isinstance(trace_context.get("safe_next_action"), dict)
        else {}
    )
    return {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_trace_join_context_packet_v1",
        "complete": self_awareness_trace_context_fallback_complete(trace_context),
        "status": trace_context.get("status"),
        "stack_requirement_id": trace_context.get("stack_requirement_id"),
        "closes_stack_requirement": trace_context.get("closes_stack_requirement"),
        "stack_requirement_not_closed_by_fallback": summary.get(
            "stack_requirement_not_closed_by_fallback"
        ),
        "trace_backend": {
            "ready": summary.get("trace_backend_ready"),
            "search_readable": summary.get("trace_search_readable"),
            "span_log_metric_join_supported": summary.get(
                "span_log_metric_join_supported"
            ),
            "missing_check_keys": [
                str(check.get("key"))
                for check in missing_checks
                if isinstance(check, dict) and check.get("key")
            ],
        },
        "fallback": {
            "metrics_log_pipeline_readable": summary.get(
                "metrics_log_pipeline_readable"
            ),
            "traceparent_log_query_ok": summary.get("traceparent_log_query_ok"),
            "traceparent_log_entries_seen": summary.get("traceparent_log_entries_seen"),
            "trace_context_query_safe_empty": summary.get(
                "trace_context_query_safe_empty"
            ),
            "bounded_trace_context_links": summary.get("bounded_trace_context_links"),
            "blocked_coverage_planes": summary.get("blocked_coverage_planes")
            if isinstance(summary.get("blocked_coverage_planes"), list)
            else [],
            "loki_query": loki_trace.get("query"),
            "loki_samples_are_hashes_only": loki_trace.get("stores_line_hashes_only"),
            "raw_log_exports_stored": loki_trace.get("raw_log_exports_stored"),
            "alloy_seen": pipeline.get("alloy_seen"),
        },
        "safe_next_action": {
            "owner_route": safe_next_action.get("owner_route"),
            "requirement_id": safe_next_action.get("requirement_id"),
            "command": safe_next_action.get("command"),
            "requires_human_approval": safe_next_action.get("requires_human_approval"),
            "host_layer_mutates_stack": safe_next_action.get(
                "host_layer_mutates_stack"
            ),
            "executes_commands": safe_next_action.get("executes_commands"),
            "automatic": safe_next_action.get("automatic"),
        },
        "evidence_refs": [
            {
                "path": ref.get("path"),
                "schema": ref.get("schema"),
                "section": ref.get("section"),
                "requirement_id": ref.get("requirement_id"),
            }
            for ref in evidence_refs
            if isinstance(ref, dict)
        ],
        "policy": {
            "read_only": policy.get("read_only"),
            "host_layer_mutates_stack": policy.get("host_layer_mutates_stack"),
            "writes_project_roots": policy.get("writes_project_roots"),
            "closes_stack_requirement": policy.get("closes_stack_requirement"),
            "adds_loki_labels": policy.get("adds_loki_labels"),
            "high_cardinality_labels_added": policy.get(
                "high_cardinality_labels_added"
            ),
            "raw_span_payloads_stored": policy.get("raw_span_payloads_stored"),
            "raw_log_exports_stored": policy.get("raw_log_exports_stored"),
            "raw_trace_payloads_stored": policy.get("raw_trace_payloads_stored"),
            "fallback_is_not_backend": policy.get("fallback_is_not_backend"),
        },
    }


def bounded_context_packet(
    contexts: dict[str, dict[str, Any]],
    memory_space: dict[str, Any],
    action_map: dict[str, Any],
    capabilities: dict[str, Any],
    generated_at: str,
    trace_context: dict[str, Any] | None = None,
    *,
    paths: SelfAwarenessCognitivePaths,
    config: SelfAwarenessCognitiveConfig,
    contract_port: SelfAwarenessCognitiveContractPort,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    SELF_AWARENESS_CAPABILITIES_LATEST_PATH = paths.capabilities_latest
    SELF_AWARENESS_CONTEXT_LATEST_PATH = paths.context_latest
    SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH = paths.requirement_probes_latest
    SELF_AWARENESS_SPATIAL_GRAPH_LATEST_PATH = paths.spatial_graph_latest
    SELF_AWARENESS_TRACE_CONTEXT_LATEST_PATH = paths.trace_context_latest
    self_awareness_compact_freshness_gate = compact_freshness_gate
    self_awareness_compact_trace_join_context = partial(
        compact_trace_join_context, config=config, contract_port=contract_port
    )
    self_awareness_governance_gate_detail_complete = governance_gate_detail_complete
    self_awareness_resident_worker_detail_complete = (
        contract_port.resident_worker_detail_complete
    )
    self_awareness_stack_coverage_impact_complete = (
        contract_port.stack_coverage_impact_complete
    )
    capability_rows = (
        capabilities.get("capabilities")
        if isinstance(capabilities.get("capabilities"), list)
        else []
    )
    capability_by_id = {
        str(item.get("id")): item
        for item in capability_rows
        if isinstance(item, dict) and item.get("id")
    }
    resident_detail = capability_by_id.get(
        "warm-e2b.resident-cognitive-worker", {}
    ).get("detail")
    resident_detail = resident_detail if isinstance(resident_detail, dict) else {}
    governance_detail = capability_by_id.get("host.governance-gates", {}).get("detail")
    governance_detail = governance_detail if isinstance(governance_detail, dict) else {}
    llm_escalation = capability_by_id.get("llm.escalation.routes", {}).get("detail")
    llm_escalation = llm_escalation if isinstance(llm_escalation, dict) else {}
    actions = (
        action_map.get("actions") if isinstance(action_map.get("actions"), list) else []
    )
    packet_actions: list[dict[str, Any]] = []
    for action in actions[:8]:
        if not isinstance(action, dict):
            continue
        readiness = (
            action.get("closure_readiness")
            if isinstance(action.get("closure_readiness"), dict)
            else {}
        )
        coverage_impact = (
            action.get("coverage_impact")
            if isinstance(action.get("coverage_impact"), dict)
            else {}
        )
        packet_actions.append(
            {
                "requirement_id": action.get("requirement_id"),
                "priority_rank": action.get("priority_rank"),
                "priority_class": action.get("priority_class"),
                "readiness_score": readiness.get("readiness_score"),
                "impact_organ": coverage_impact.get("organ"),
                "coverage_planes": coverage_impact.get("coverage_planes")
                if isinstance(coverage_impact.get("coverage_planes"), list)
                else [],
                "coverage_impact": coverage_impact,
                "blocking_check_keys": readiness.get("blocking_check_keys")
                if isinstance(readiness.get("blocking_check_keys"), list)
                else action.get("closure_blocker_keys"),
                "missing_check_count": safe_int(
                    readiness.get("open_blocker_count"),
                    len(
                        readiness.get("missing_checks")
                        if isinstance(readiness.get("missing_checks"), list)
                        else []
                    ),
                ),
                "dependency_requirement_ids": readiness.get(
                    "dependency_requirement_ids"
                )
                if isinstance(readiness.get("dependency_requirement_ids"), list)
                else [],
                "verifier_commands": readiness.get("verifier_commands")
                if isinstance(readiness.get("verifier_commands"), list)
                else action.get("verifier_commands"),
                "safe_next_action": readiness.get("safe_next_action")
                if isinstance(readiness.get("safe_next_action"), dict)
                else action.get("safe_next_action"),
                "evidence_refs": readiness.get("evidence_refs")
                if isinstance(readiness.get("evidence_refs"), list)
                else action.get("evidence_refs"),
                "policy": readiness.get("policy")
                if isinstance(readiness.get("policy"), dict)
                else action.get("policy"),
            }
        )
    freshness_gates = (
        memory_space.get("freshness_gates")
        if isinstance(memory_space.get("freshness_gates"), list)
        else []
    )
    blocked_gates = [
        self_awareness_compact_freshness_gate(gate)
        for gate in freshness_gates
        if isinstance(gate, dict) and gate.get("blocks_deep_reasoning")
    ]
    retrieval_packets = (
        memory_space.get("retrieval_packets")
        if isinstance(memory_space.get("retrieval_packets"), list)
        else []
    )
    semantic_backends = (
        memory_space.get("stack_semantic_backends")
        if isinstance(memory_space.get("stack_semantic_backends"), list)
        else []
    )
    trace_join_context = self_awareness_compact_trace_join_context(trace_context)
    blocked_coverage_planes = sorted(
        {
            str(plane)
            for action in packet_actions
            for plane in (
                action.get("coverage_planes")
                if isinstance(action.get("coverage_planes"), list)
                else []
            )
            if plane
        }
    )
    context_rows = sorted(contexts.values(), key=lambda item: str(item.get("key")))
    compact_contexts = [
        {
            "key_hash": stable_hash_json({"key": item.get("key")}, length=16),
            "event_count": len(
                item.get("event_ids") if isinstance(item.get("event_ids"), list) else []
            ),
            "signals": item.get("signals"),
            "sources": item.get("sources"),
            "has_trace_id": bool(nested_get(item, ["context", "trace_id"])),
            "has_traceparent": bool(nested_get(item, ["context", "traceparent"])),
            "has_synthetic_run_id": bool(
                nested_get(item, ["context", "synthetic_run_id"])
            ),
        }
        for item in context_rows[:12]
        if isinstance(item, dict)
    ]

    def context_values(prefix: str, *, limit: int = 16) -> list[str]:
        values = sorted(
            {
                str(item.get("key"))[len(prefix) :]
                for item in context_rows
                if isinstance(item, dict)
                and str(item.get("key") or "").startswith(prefix)
            }
        )
        return values[:limit]

    host_body = {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_host_body_context_packet_v1",
        "scheduler": {
            "unit_contexts": sum(
                (
                    1
                    for item in context_rows
                    if isinstance(item, dict)
                    and str(item.get("key") or "").startswith("scheduler_unit:")
                )
            ),
            "category_contexts": sum(
                (
                    1
                    for item in context_rows
                    if isinstance(item, dict)
                    and str(item.get("key") or "").startswith("scheduler_category:")
                )
            ),
            "categories": context_values("scheduler_category:"),
            "sample_units": context_values("scheduler_unit:", limit=12),
        },
        "host_services": {
            "unit_contexts": sum(
                (
                    1
                    for item in context_rows
                    if isinstance(item, dict)
                    and str(item.get("key") or "").startswith("host_service_unit:")
                )
            ),
            "category_contexts": sum(
                (
                    1
                    for item in context_rows
                    if isinstance(item, dict)
                    and str(item.get("key") or "").startswith("host_service_category:")
                )
            ),
            "categories": context_values("host_service_category:"),
            "sample_units": context_values("host_service_unit:", limit=12),
        },
        "manual_collect": {
            "contexts": sum(
                (
                    1
                    for item in context_rows
                    if isinstance(item, dict)
                    and str(item.get("key") or "").startswith("manual_collect_status:")
                )
            ),
            "statuses": context_values("manual_collect_status:"),
        },
        "bounds": {
            "raw_private_content": False,
            "stores_raw_body": False,
            "stores_raw_context_values": False,
            "unit_names_are_service_identities": True,
        },
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "automatic_remediation": False,
        },
    }
    host_body["complete"] = bool(
        nested_get(host_body, ["scheduler", "unit_contexts"])
        or nested_get(host_body, ["host_services", "unit_contexts"])
        or nested_get(host_body, ["manual_collect", "contexts"])
    )
    read_only_tools = [
        {
            "kind": "promql_read",
            "command": "abyss-machine self-awareness query --query TEXT --json",
            "read_only": True,
            "stores_raw_body": False,
            "host_layer_mutates_stack": False,
        },
        {
            "kind": "logql_read",
            "command": "abyss-machine self-awareness query --query TEXT --json",
            "read_only": True,
            "stores_raw_body": False,
            "host_layer_mutates_stack": False,
        },
        {
            "kind": "trace_context",
            "command": "abyss-machine self-awareness trace-context --json",
            "read_only": True,
            "stores_raw_body": False,
            "host_layer_mutates_stack": False,
        },
        {
            "kind": "memory_space",
            "command": "abyss-machine self-awareness context --json",
            "read_only": True,
            "stores_raw_body": False,
            "host_layer_mutates_stack": False,
        },
        {
            "kind": "spatial_graph",
            "command": "abyss-machine self-awareness spatial-graph --json",
            "read_only": True,
            "stores_raw_body": False,
            "host_layer_mutates_stack": False,
        },
        {
            "kind": "requirements_handoff",
            "command": "abyss-machine self-awareness requirement-probes --json",
            "read_only": True,
            "stores_raw_body": False,
            "host_layer_mutates_stack": False,
        },
        {
            "kind": "resident_worker",
            "command": "abyss-machine self-awareness capabilities --json",
            "read_only": True,
            "stores_raw_body": False,
            "host_layer_mutates_stack": False,
        },
        {
            "kind": "governance_gates",
            "command": "abyss-machine mode plan --json",
            "read_only": True,
            "stores_raw_body": False,
            "host_layer_mutates_stack": False,
        },
        {
            "kind": "export_handoff",
            "command": "abyss-machine self-awareness export --json",
            "read_only": True,
            "stores_raw_body": False,
            "host_layer_mutates_stack": False,
        },
    ]
    sections = {
        "correlation_contexts": {
            "included": len(compact_contexts),
            "total_contexts": len(contexts),
            "items": compact_contexts,
            "raw_context_values_stored": False,
        },
        "host_body": host_body,
        "memory_space": {
            "summary": memory_space.get("summary")
            if isinstance(memory_space.get("summary"), dict)
            else {},
            "blocked_gates": blocked_gates,
            "retrieval_packet_ids": [
                packet.get("id") or packet.get("packet_id")
                for packet in retrieval_packets[:8]
                if isinstance(packet, dict)
            ],
            "semantic_backend_ids": [
                backend.get("id")
                for backend in semantic_backends
                if isinstance(backend, dict)
            ],
            "policy": memory_space.get("policy")
            if isinstance(memory_space.get("policy"), dict)
            else {},
        },
        "trace_join": trace_join_context,
        "stack_handoff": {
            "summary": action_map.get("summary")
            if isinstance(action_map.get("summary"), dict)
            else {},
            "open_requirement_ids": action_map.get("open_requirement_ids")
            if isinstance(action_map.get("open_requirement_ids"), list)
            else [],
            "ordered_actions": packet_actions,
            "policy": action_map.get("policy")
            if isinstance(action_map.get("policy"), dict)
            else {},
        },
        "resident_worker": {
            "worker": "warm-e2b/gemma4.spark",
            "status": resident_detail.get("status"),
            "complete": self_awareness_resident_worker_detail_complete(resident_detail),
            "serving_owner": nested_get(resident_detail, ["serving", "owner"]),
            "stack_owned_serving": nested_get(
                resident_detail, ["serving", "stack_owned_serving"]
            ),
            "health_latency_ms": nested_get(
                resident_detail, ["health", "health_latency_ms"]
            ),
            "package_temp_c": nested_get(
                resident_detail, ["resource_thermal", "package_temp_c"]
            ),
            "candidate_count": nested_get(
                resident_detail, ["candidate_context", "candidates"]
            ),
            "action_execution": nested_get(
                resident_detail, ["candidate_context", "action_execution"]
            ),
            "policy": resident_detail.get("policy")
            if isinstance(resident_detail.get("policy"), dict)
            else {},
        },
        "governance_gates": {
            "complete": self_awareness_governance_gate_detail_complete(
                governance_detail
            ),
            "readiness": governance_detail.get("readiness")
            if isinstance(governance_detail.get("readiness"), dict)
            else {},
            "memory_status": governance_detail.get("memory_status"),
            "resource_status": governance_detail.get("resource_status"),
            "mode_status": governance_detail.get("mode_status"),
            "memory_class": nested_get(governance_detail, ["memory", "class"]),
            "effective_mode": nested_get(governance_detail, ["mode", "effective_mode"]),
            "policy": governance_detail.get("policy")
            if isinstance(governance_detail.get("policy"), dict)
            else {},
        },
        "escalation_gate": {
            "route_ready": llm_escalation.get("route_ready"),
            "model_execution_status": nested_get(
                llm_escalation, ["gates", "model_execution_now", "status"]
            ),
            "model_execution_allowed": nested_get(
                llm_escalation, ["gates", "model_execution_now", "allowed"]
            ),
            "qwen_ready": nested_get(llm_escalation, ["qwen_lazy_load", "ready"]),
            "policy": llm_escalation.get("policy")
            if isinstance(llm_escalation.get("policy"), dict)
            else {},
        },
    }
    section_order = [
        "correlation_contexts",
        "host_body",
        "memory_space",
        "trace_join",
        "stack_handoff",
        "resident_worker",
        "governance_gates",
        "escalation_gate",
    ]
    evidence_refs = [
        {"path": str(SELF_AWARENESS_CONTEXT_LATEST_PATH), "section": "context_packet"},
        {
            "path": str(SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH),
            "section": "stack_handoff",
        },
        {
            "path": str(SELF_AWARENESS_TRACE_CONTEXT_LATEST_PATH),
            "section": "trace_join",
        },
        {
            "path": str(SELF_AWARENESS_CAPABILITIES_LATEST_PATH),
            "section": "resident_worker_and_governance",
        },
        {
            "path": str(SELF_AWARENESS_SPATIAL_GRAPH_LATEST_PATH),
            "section": "memory_space_overlay",
        },
    ]
    complete = (
        bool(memory_space.get("summary"))
        and action_map.get("schema")
        == f"{SCHEMA_PREFIX}_self_awareness_brief_stack_handoff_action_map_v1"
        and self_awareness_resident_worker_detail_complete(resident_detail)
        and self_awareness_governance_gate_detail_complete(governance_detail)
        and (nested_get(memory_space, ["policy", "bounded_retrieval"]) is True)
        and (
            nested_get(memory_space, ["policy", "freshness_must_precede_reasoning"])
            is True
        )
        and (nested_get(memory_space, ["policy", "raw_evidence_is_not_truth"]) is True)
        and (nested_get(action_map, ["policy", "host_layer_mutates_stack"]) is False)
        and (trace_join_context.get("complete") is True)
        and (
            nested_get(trace_join_context, ["policy", "host_layer_mutates_stack"])
            is False
        )
        and (
            nested_get(trace_join_context, ["policy", "closes_stack_requirement"])
            is False
        )
        and (nested_get(trace_join_context, ["policy", "adds_loki_labels"]) is False)
        and all(
            (
                self_awareness_stack_coverage_impact_complete(
                    action.get("coverage_impact")
                )
                for action in packet_actions
            )
        )
        and all(
            (
                tool["read_only"] is True
                and tool["host_layer_mutates_stack"] is False
                and (tool["stores_raw_body"] is False)
                for tool in read_only_tools
            )
        )
    )
    return {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_bounded_context_packet_v1",
        "generated_at": generated_at,
        "complete": complete,
        "purpose": "resident_worker_and_operator_readonly_reasoning",
        "section_order": section_order,
        "sections": sections,
        "read_only_tools": read_only_tools,
        "bounds": {
            "max_context_rows": 12,
            "max_stack_handoff_actions": 8,
            "max_retrieval_packet_ids": 8,
            "raw_private_content": False,
            "stores_raw_body": False,
            "stores_raw_context_values": False,
            "redacts_secret_like_values": True,
            "freshness_must_precede_reasoning": True,
            "raw_evidence_is_not_truth": True,
        },
        "summary": {
            "sections": len(section_order),
            "contexts": len(compact_contexts),
            "host_body_complete": host_body.get("complete"),
            "host_service_contexts": nested_get(
                host_body, ["host_services", "unit_contexts"]
            ),
            "scheduler_contexts": nested_get(host_body, ["scheduler", "unit_contexts"]),
            "manual_collect_contexts": nested_get(
                host_body, ["manual_collect", "contexts"]
            ),
            "retrieval_packets": safe_int(
                nested_get(memory_space, ["summary", "retrieval_packets"]), 0
            ),
            "blocked_freshness_gates": len(blocked_gates),
            "trace_join_complete": trace_join_context.get("complete"),
            "trace_backend_ready": nested_get(
                trace_join_context, ["trace_backend", "ready"]
            ),
            "trace_join_closes_stack_requirement": trace_join_context.get(
                "closes_stack_requirement"
            ),
            "stack_handoff_actions": len(packet_actions),
            "open_stack_requirements": safe_int(
                nested_get(action_map, ["summary", "open_stack_requirements"]), 0
            ),
            "coverage_impact_entries": sum(
                (
                    1
                    for action in packet_actions
                    if self_awareness_stack_coverage_impact_complete(
                        action.get("coverage_impact")
                    )
                )
            ),
            "blocked_coverage_planes": blocked_coverage_planes,
            "resident_worker_complete": self_awareness_resident_worker_detail_complete(
                resident_detail
            ),
            "governance_gates_complete": self_awareness_governance_gate_detail_complete(
                governance_detail
            ),
        },
        "digest": stable_hash_json(sections, length=24),
        "evidence_refs": evidence_refs,
        "policy": {
            "bounded_context": True,
            "read_only_tools_only": True,
            "action_execution": False,
            "auto_remediation": False,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "human_approval_before_mutation": True,
            "exports_raw_private_content": False,
            "raw_evidence_is_not_truth": True,
            "freshness_must_precede_reasoning": True,
        },
    }


def ai_multimodal_detail(
    ai_caps: dict[str, Any],
    ai_devices_latest: dict[str, Any],
    ai_models_latest: dict[str, Any],
    ai_tts_profiles_latest: dict[str, Any],
    ai_tts_success_latest: dict[str, Any],
    ai_llm: dict[str, Any],
    *,
    paths: SelfAwarenessCognitivePaths,
    config: SelfAwarenessCognitiveConfig,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    ABYSS_STACK_USER_SOURCE_ROOT = paths.abyss_stack_user_source_root
    AI_CAPABILITIES_LATEST_PATH = paths.ai_capabilities_latest
    AI_DEVICES_LATEST_PATH = paths.ai_devices_latest
    AI_LLM_REGISTRY_LATEST_PATH = paths.ai_llm_registry_latest
    AI_MODELS_LATEST_PATH = paths.ai_models_latest
    AI_TTS_EVAL_LATEST_SUCCESS_PATH = paths.ai_tts_eval_latest_success
    AI_TTS_PROFILES_LATEST_PATH = paths.ai_tts_profiles_latest
    caps = (
        ai_caps.get("capabilities")
        if isinstance(ai_caps.get("capabilities"), dict)
        else {}
    )

    def cap(name: str) -> dict[str, Any]:
        value = caps.get(name)
        return value if isinstance(value, dict) else {}

    def compact_source_models(
        source_models: Any, limit: int = 4
    ) -> list[dict[str, Any]]:
        models = source_models if isinstance(source_models, list) else []
        compact: list[dict[str, Any]] = []
        for item in models[:limit]:
            if not isinstance(item, dict):
                continue
            compact.append(
                {
                    "profile": item.get("profile"),
                    "kind": item.get("kind"),
                    "category": item.get("category"),
                    "name": item.get("name"),
                    "path": item.get("path") or item.get("model_dir"),
                    "root": item.get("root"),
                    "relative_path": item.get("relative_path"),
                    "device": item.get("device"),
                    "read_only_source": item.get("read_only_source"),
                    "artifacts": item.get("artifacts")
                    if isinstance(item.get("artifacts"), dict)
                    else None,
                    "file_summary": item.get("file_summary")
                    if isinstance(item.get("file_summary"), dict)
                    else None,
                }
            )
        return compact

    def compact_llm_profiles(profiles: dict[str, Any]) -> dict[str, dict[str, Any]]:
        compact: dict[str, dict[str, Any]] = {}
        for name, profile in profiles.items():
            if not isinstance(profile, dict):
                continue
            compact[str(name)] = {
                "status": profile.get("status"),
                "role": profile.get("role"),
                "backend": profile.get("backend"),
                "declared_class": profile.get("declared_class"),
                "warm_policy": profile.get("warm_policy"),
                "local_exists": profile.get("local_exists"),
                "size_bytes": profile.get("size_bytes"),
                "local_path": profile.get("local_path"),
                "runtime_ok": nested_get(profile, ["runtime", "ok"]),
                "under_host_cache": nested_get(
                    profile, ["storage", "under_host_cache"]
                ),
                "host_layer_mutates_stack": nested_get(
                    profile, ["policy", "host_layer_mutates_stack"]
                ),
                "resource_gated": profile.get("declared_class")
                in {"heavy", "sustained"},
            }
        return compact

    def compact_tts_profiles(profiles: dict[str, Any]) -> dict[str, dict[str, Any]]:
        compact: dict[str, dict[str, Any]] = {}
        for name, profile in profiles.items():
            if not isinstance(profile, dict):
                continue
            compact[str(name)] = {
                "status": profile.get("status"),
                "engine": profile.get("engine"),
                "declared_class": profile.get("declared_class"),
                "device": profile.get("device"),
                "precision": profile.get("precision"),
                "model_path": nested_get(profile, ["model", "path"]),
                "model_exists": nested_get(profile, ["model", "exists"]),
                "model_complete": nested_get(profile, ["model", "complete"]),
                "model_read_only_source": nested_get(
                    profile, ["model", "read_only_source"]
                ),
                "openvino_path": nested_get(profile, ["openvino", "path"]),
                "openvino_complete": nested_get(profile, ["openvino", "complete"]),
                "openvino_host_managed": nested_get(
                    profile, ["openvino", "host_managed"]
                ),
                "runtime_ready": nested_get(profile, ["runtime", "ready"]),
                "synth_supported": nested_get(profile, ["runtime", "synth_supported"]),
                "host_layer_mutates_stack": nested_get(
                    profile, ["policy", "host_layer_mutates_stack"]
                ),
            }
        return compact

    stt = cap("stt")
    embeddings = cap("embeddings")
    llm_text = cap("llm_text")
    tts = cap("tts")
    npu = cap("npu")
    llm_profiles = (
        ai_llm.get("profiles") if isinstance(ai_llm.get("profiles"), dict) else {}
    )
    tts_profiles = (
        ai_tts_profiles_latest.get("profiles")
        if isinstance(ai_tts_profiles_latest.get("profiles"), dict)
        else {}
    )
    device_ready = (
        ai_devices_latest.get("ready")
        if isinstance(ai_devices_latest.get("ready"), dict)
        else {}
    )
    openvino = (
        ai_devices_latest.get("openvino")
        if isinstance(ai_devices_latest.get("openvino"), dict)
        else {}
    )
    model_summary = (
        ai_models_latest.get("summary")
        if isinstance(ai_models_latest.get("summary"), dict)
        else {}
    )
    model_roots = (
        ai_models_latest.get("roots")
        if isinstance(ai_models_latest.get("roots"), list)
        else []
    )
    stack_model_roots = [
        {
            "path": item.get("path"),
            "exists": item.get("exists"),
            "entries_seen": item.get("entries_seen"),
            "read_only_source": str(item.get("path") or "").startswith(
                ("/srv/AbyssOS/abyss-stack", str(ABYSS_STACK_USER_SOURCE_ROOT))
            ),
        }
        for item in model_roots
        if isinstance(item, dict)
    ]
    tts_executable = [
        name
        for name, profile in tts_profiles.items()
        if isinstance(profile, dict) and profile.get("status") == "executable"
    ]
    tts_latest_success = {
        "ok": ai_tts_success_latest.get("ok"),
        "generated_at": ai_tts_success_latest.get("generated_at"),
        "profile": ai_tts_success_latest.get("profile"),
        "summary": ai_tts_success_latest.get("summary")
        if isinstance(ai_tts_success_latest.get("summary"), dict)
        else None,
    }
    return {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_ai_multimodal_detail_v1",
        "status": "ready"
        if all(
            (
                str(cap(name).get("status") or "") in accepted
                for name, accepted in {
                    "stt": {"ready"},
                    "embeddings": {"ready"},
                    "llm_text": {"resident-running", "llama-cpp-ready"},
                    "tts": {"runtime-proven", "bridge-ready"},
                    "npu": {"runtime-ready"},
                }.items()
            )
        )
        else "degraded",
        "devices": {
            "openvino_ok": openvino.get("ok"),
            "openvino_version": openvino.get("openvino_version"),
            "available_devices": openvino.get("available_devices")
            if isinstance(openvino.get("available_devices"), list)
            else [],
            "ready": device_ready,
            "npu": nested_get(openvino, ["device_properties", "NPU"]),
            "gpu": nested_get(openvino, ["device_properties", "GPU"]),
            "cpu": nested_get(openvino, ["device_properties", "CPU"]),
        },
        "model_inventory": {
            "entries": model_summary.get("entries"),
            "by_category": model_summary.get("by_category"),
            "truncated": model_summary.get("truncated"),
            "roots": stack_model_roots,
        },
        "modalities": {
            "stt": {
                "status": stt.get("status"),
                "host_recommended_backend": stt.get("host_recommended_backend"),
                "primary_bridge": stt.get("primary_bridge"),
                "source_model_count": len(
                    stt.get("source_models")
                    if isinstance(stt.get("source_models"), list)
                    else []
                ),
                "source_models": compact_source_models(stt.get("source_models")),
                "non_claims": stt.get("non_claims")
                if isinstance(stt.get("non_claims"), list)
                else [],
            },
            "embeddings": {
                "status": embeddings.get("status"),
                "host_recommended_backend": embeddings.get("host_recommended_backend"),
                "primary_bridge": embeddings.get("primary_bridge"),
                "source_model_count": len(
                    embeddings.get("source_models")
                    if isinstance(embeddings.get("source_models"), list)
                    else []
                ),
                "source_models": compact_source_models(embeddings.get("source_models")),
                "stack_bridge_hint": embeddings.get("stack_bridge_hint"),
            },
            "llm_text": {
                "status": llm_text.get("status"),
                "host_recommended_backend": llm_text.get("host_recommended_backend"),
                "primary_bridge": llm_text.get("primary_bridge"),
                "resident_bridge": llm_text.get("resident_bridge"),
                "eval_bridge": llm_text.get("eval_bridge"),
                "source_model_count": len(
                    llm_text.get("source_models")
                    if isinstance(llm_text.get("source_models"), list)
                    else []
                ),
                "source_models": compact_source_models(
                    llm_text.get("source_models"), limit=3
                ),
                "registry_summary": ai_llm.get("summary"),
                "profiles": compact_llm_profiles(llm_profiles),
                "stack_bridge_hint": llm_text.get("stack_bridge_hint"),
            },
            "tts": {
                "status": tts.get("status"),
                "host_recommended_backend": tts.get("host_recommended_backend"),
                "primary_bridge": tts.get("primary_bridge"),
                "eval_bridge": tts.get("eval_bridge"),
                "server_bridge": tts.get("server_bridge"),
                "source_model_count": len(
                    tts.get("source_models")
                    if isinstance(tts.get("source_models"), list)
                    else []
                ),
                "source_models": compact_source_models(
                    tts.get("source_models"), limit=4
                ),
                "profile_summary": ai_tts_profiles_latest.get("summary"),
                "executable_profiles": sorted(tts_executable),
                "profiles": compact_tts_profiles(tts_profiles),
                "latest_success_eval": tts_latest_success,
                "non_claims": tts.get("non_claims")
                if isinstance(tts.get("non_claims"), list)
                else [],
            },
            "npu": {
                "status": npu.get("status"),
                "host_recommended_backend": npu.get("host_recommended_backend"),
                "primary_bridge": npu.get("primary_bridge"),
                "source_model_count": len(
                    npu.get("source_models")
                    if isinstance(npu.get("source_models"), list)
                    else []
                ),
                "device_ready": device_ready.get("npu"),
                "device_properties": nested_get(openvino, ["device_properties", "NPU"]),
                "non_claims": npu.get("non_claims")
                if isinstance(npu.get("non_claims"), list)
                else [],
            },
        },
        "source_refs": {
            "ai_capabilities": str(AI_CAPABILITIES_LATEST_PATH),
            "ai_devices": str(AI_DEVICES_LATEST_PATH),
            "ai_models": str(AI_MODELS_LATEST_PATH),
            "ai_tts_profiles": str(AI_TTS_PROFILES_LATEST_PATH),
            "ai_tts_latest_success": str(AI_TTS_EVAL_LATEST_SUCCESS_PATH),
            "ai_llm_registry": str(AI_LLM_REGISTRY_LATEST_PATH),
        },
        "policy": {
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "capability_presence_is_stack_promotion": False,
            "stack_model_roots_read_only": all(
                (
                    root.get("read_only_source") is True
                    for root in stack_model_roots
                    if root.get("path")
                )
            ),
            "host_caches_under_srv_abyss_machine": True,
            "future_stack_must_run_own_promotion_gates": True,
        },
    }


def ai_multimodal_detail_complete(detail: dict[str, Any]) -> bool:
    if not isinstance(detail, dict):
        return False
    modalities = (
        detail.get("modalities") if isinstance(detail.get("modalities"), dict) else {}
    )
    return (
        detail.get("status") == "ready"
        and nested_get(detail, ["devices", "openvino_ok"]) is True
        and {"CPU", "GPU", "NPU"}.issubset(
            set(nested_get(detail, ["devices", "available_devices"]) or [])
        )
        and (safe_int(nested_get(detail, ["model_inventory", "entries"]), 0) > 0)
        and bool(nested_get(detail, ["model_inventory", "roots"]))
        and (safe_int(nested_get(modalities, ["stt", "source_model_count"]), 0) > 0)
        and (
            safe_int(nested_get(modalities, ["embeddings", "source_model_count"]), 0)
            > 0
        )
        and (
            safe_int(
                nested_get(
                    modalities, ["llm_text", "registry_summary", "ready_profiles"]
                ),
                0,
            )
            > 0
        )
        and bool(nested_get(modalities, ["llm_text", "profiles"]))
        and (
            safe_int(
                nested_get(modalities, ["tts", "profile_summary", "executable"]), 0
            )
            > 0
        )
        and bool(nested_get(modalities, ["tts", "profiles"]))
        and (nested_get(modalities, ["npu", "device_ready"]) is True)
        and (nested_get(detail, ["policy", "host_layer_mutates_stack"]) is False)
        and (nested_get(detail, ["policy", "writes_project_roots"]) is False)
        and (
            nested_get(detail, ["policy", "capability_presence_is_stack_promotion"])
            is False
        )
        and (
            nested_get(detail, ["policy", "future_stack_must_run_own_promotion_gates"])
            is True
        )
    )


def llm_escalation_detail(
    ai_llm: dict[str, Any],
    workhorse_pack: dict[str, Any],
    workhorse_review: dict[str, Any],
    workhorse_validate: dict[str, Any],
    workhorse_preflight: dict[str, Any],
    resource_latest: dict[str, Any],
    mode_latest: dict[str, Any],
    *,
    paths: SelfAwarenessCognitivePaths,
    config: SelfAwarenessCognitiveConfig,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    AI_LLM_REGISTRY_LATEST_PATH = paths.ai_llm_registry_latest
    AI_LLM_WORKHORSE_PACK_LATEST_PATH = paths.ai_llm_workhorse_pack_latest
    AI_LLM_WORKHORSE_PREFLIGHT_LATEST_PATH = paths.ai_llm_workhorse_preflight_latest
    AI_LLM_WORKHORSE_REVIEW_LATEST_PATH = paths.ai_llm_workhorse_review_latest
    AI_LLM_WORKHORSE_VALIDATE_LATEST_PATH = paths.ai_llm_workhorse_validate_latest
    MODE_LATEST_PATH = paths.mode_latest
    RESOURCE_LATEST_PATH = paths.resource_latest
    profiles = (
        ai_llm.get("profiles") if isinstance(ai_llm.get("profiles"), dict) else {}
    )
    escalation_names = ("gemma4.workhorse", "qwen36.ordinary", "qwen36.heretic")

    def profile(name: str) -> dict[str, Any]:
        value = profiles.get(name)
        return value if isinstance(value, dict) else {}

    def command_ctx(command: Any) -> int | None:
        if not isinstance(command, str) or not command:
            return None
        try:
            parts = shlex.split(command)
        except ValueError:
            parts = command.split()
        for index, part in enumerate(parts):
            if part in {"--ctx", "-c"} and index + 1 < len(parts):
                ctx = safe_int(parts[index + 1], 0)
                return ctx or None
        return None

    def compact_escalation_profile(name: str) -> dict[str, Any]:
        item = profile(name)
        lazy_load = (
            item.get("lazy_load") if isinstance(item.get("lazy_load"), dict) else {}
        )
        server = item.get("server") if isinstance(item.get("server"), dict) else {}
        launch = item.get("launch") if isinstance(item.get("launch"), dict) else {}
        default_context = (
            command_ctx(lazy_load.get("request_command"))
            or command_ctx(lazy_load.get("start_command"))
            or safe_int(item.get("context_size"), 0)
            or safe_int(item.get("max_context_size"), 0)
            or None
        )
        return {
            "status": item.get("status"),
            "role": item.get("role"),
            "backend": item.get("backend"),
            "declared_class": item.get("declared_class"),
            "warm_policy": item.get("warm_policy"),
            "local_exists": item.get("local_exists"),
            "size_bytes": item.get("size_bytes"),
            "local_path": item.get("local_path"),
            "runtime_ok": nested_get(item, ["runtime", "ok"]),
            "under_host_cache": nested_get(item, ["storage", "under_host_cache"]),
            "host_layer_mutates_stack": nested_get(
                item, ["policy", "host_layer_mutates_stack"]
            ),
            "resource_gated": item.get("declared_class") in {"heavy", "sustained"},
            "max_context_size": item.get("max_context_size"),
            "default_context_size": default_context,
            "launch": {
                "cli_smoke": launch.get("cli_smoke")
                if isinstance(launch.get("cli_smoke"), list)
                else None,
                "server_base": launch.get("server_base")
                if isinstance(launch.get("server_base"), list)
                else None,
            },
            "server": {
                "host": server.get("host"),
                "port_base": server.get("port_base"),
                "threads": server.get("threads"),
                "batch": server.get("batch"),
                "ubatch": server.get("ubatch"),
                "flash_attention": server.get("flash_attention"),
                "kv_cache": server.get("kv_cache"),
                "slot_cache_root": server.get("slot_cache_root"),
                "prefill_evidence_root": server.get("prefill_evidence_root"),
                "sleep_idle_seconds": server.get("sleep_idle_seconds"),
                "resource_class": server.get("resource_class")
                or item.get("declared_class"),
                "resource_kind": server.get("resource_kind"),
                "cpuset": server.get("cpuset"),
            },
            "lazy_load": {
                "tool": lazy_load.get("tool"),
                "start_command": lazy_load.get("start_command"),
                "prefill_command": lazy_load.get("prefill_command"),
                "restore_command": lazy_load.get("restore_command"),
                "request_command": lazy_load.get("request_command"),
                "stop_command": lazy_load.get("stop_command"),
            },
        }

    qwen_profiles = {
        name: compact_escalation_profile(name)
        for name in ("qwen36.ordinary", "qwen36.heretic")
    }
    workhorse_profile = compact_escalation_profile("gemma4.workhorse")
    validate_failed = (
        [
            item.get("key")
            for item in workhorse_validate.get("checks", [])
            if isinstance(item, dict) and item.get("level") == "fail"
        ]
        if isinstance(workhorse_validate.get("checks"), list)
        else []
    )
    latest_plan = (
        resource_latest.get("latest_plan")
        if isinstance(resource_latest.get("latest_plan"), dict)
        else {}
    )
    launch_policy = (
        mode_latest.get("launch_policy")
        if isinstance(mode_latest.get("launch_policy"), dict)
        else {}
    )
    cpu_routed_heavy = (
        launch_policy.get("cpu_routed_heavy")
        if isinstance(launch_policy.get("cpu_routed_heavy"), dict)
        else {}
    )
    preflight_resource = (
        workhorse_preflight.get("resource")
        if isinstance(workhorse_preflight.get("resource"), dict)
        else {}
    )
    preflight_decision = workhorse_preflight.get("decision")
    preflight_blocked_reasons = list(
        workhorse_preflight.get("blocked_reasons")
        if isinstance(workhorse_preflight.get("blocked_reasons"), list)
        else []
    )
    preflight_warnings = list(
        workhorse_preflight.get("warnings")
        if isinstance(workhorse_preflight.get("warnings"), list)
        else []
    )
    review_pipeline_ready = bool(
        workhorse_pack.get("ok")
        and workhorse_review.get("ok")
        and workhorse_validate.get("ok")
        and (safe_int(nested_get(workhorse_validate, ["summary", "fails"]), -1) == 0)
        and (nested_get(workhorse_review, ["summary", "model_used"]) is False)
        and (nested_get(workhorse_review, ["policy", "action_execution"]) is False)
        and (nested_get(workhorse_review, ["policy", "starts_llama_server"]) is False)
        and (nested_get(workhorse_review, ["policy", "resident_service"]) is False)
    )
    qwen_ready = all(
        (
            qwen_profiles[name].get("status") == "ready"
            and qwen_profiles[name].get("local_exists") is True
            and (qwen_profiles[name].get("runtime_ok") is True)
            and (qwen_profiles[name].get("declared_class") == "heavy")
            and (qwen_profiles[name].get("host_layer_mutates_stack") is False)
            and nested_get(qwen_profiles[name], ["lazy_load", "start_command"])
            and nested_get(qwen_profiles[name], ["lazy_load", "request_command"])
            and nested_get(qwen_profiles[name], ["server", "cpuset"])
            for name in qwen_profiles
        )
    )
    qwen_default_contexts = [
        safe_int(item.get("default_context_size"), 0)
        for item in qwen_profiles.values()
        if safe_int(item.get("default_context_size"), 0) > 0
    ]
    qwen_max_contexts = [
        safe_int(item.get("max_context_size"), 0)
        for item in qwen_profiles.values()
        if safe_int(item.get("max_context_size"), 0) > 0
    ]
    route_ready = bool(
        ai_llm.get("ok")
        and all((profile(name).get("status") == "ready" for name in escalation_names))
        and review_pipeline_ready
        and qwen_ready
    )
    model_execution_allowed = bool(
        workhorse_preflight.get("ok") is True
        and preflight_decision in {"allow", "ready"}
        and (preflight_resource.get("decision") in {"allow", "routed"})
    )
    if model_execution_allowed:
        execution_status = "allowed_now"
    elif preflight_decision == "block" or preflight_blocked_reasons:
        execution_status = "blocked_by_preflight"
    elif (
        preflight_resource.get("decision") == "force_required"
        or latest_plan.get("decision") == "force_required"
    ):
        execution_status = "operator_force_required"
    else:
        execution_status = "gated_unknown"
    return {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_llm_escalation_detail_v1",
        "status": "ready_review_only" if route_ready else "degraded",
        "route_ready": route_ready,
        "review_pipeline_ready": review_pipeline_ready,
        "registry": {
            "ok": ai_llm.get("ok"),
            "summary": ai_llm.get("summary")
            if isinstance(ai_llm.get("summary"), dict)
            else {},
            "profiles": {
                name: {
                    "status": profile(name).get("status"),
                    "role": profile(name).get("role"),
                    "declared_class": profile(name).get("declared_class"),
                    "local_exists": profile(name).get("local_exists"),
                    "runtime_ok": nested_get(profile(name), ["runtime", "ok"]),
                }
                for name in escalation_names
            },
        },
        "workhorse": {
            "profile": "gemma4.workhorse",
            "profile_detail": workhorse_profile,
            "pack": {
                "ok": workhorse_pack.get("ok"),
                "generated_at": workhorse_pack.get("generated_at"),
                "summary": workhorse_pack.get("summary")
                if isinstance(workhorse_pack.get("summary"), dict)
                else {},
                "allowed_source_ids": len(
                    workhorse_pack.get("allowed_source_ids")
                    if isinstance(workhorse_pack.get("allowed_source_ids"), list)
                    else []
                ),
                "policy": workhorse_pack.get("policy")
                if isinstance(workhorse_pack.get("policy"), dict)
                else {},
            },
            "review": {
                "ok": workhorse_review.get("ok"),
                "generated_at": workhorse_review.get("generated_at"),
                "summary": workhorse_review.get("summary")
                if isinstance(workhorse_review.get("summary"), dict)
                else {},
                "policy": workhorse_review.get("policy")
                if isinstance(workhorse_review.get("policy"), dict)
                else {},
            },
            "validate": {
                "ok": workhorse_validate.get("ok"),
                "generated_at": workhorse_validate.get("generated_at"),
                "summary": workhorse_validate.get("summary")
                if isinstance(workhorse_validate.get("summary"), dict)
                else {},
                "failed_keys": validate_failed,
            },
            "preflight": {
                "ok": workhorse_preflight.get("ok"),
                "generated_at": workhorse_preflight.get("generated_at"),
                "decision": preflight_decision,
                "blocked_reasons": preflight_blocked_reasons,
                "warnings": preflight_warnings,
                "resource_decision": preflight_resource.get("decision"),
                "resource_blocked_reasons": list(
                    preflight_resource.get("blocked_reasons")
                    if isinstance(preflight_resource.get("blocked_reasons"), list)
                    else []
                ),
                "memory": workhorse_preflight.get("memory")
                if isinstance(workhorse_preflight.get("memory"), dict)
                else {},
                "model": workhorse_preflight.get("model")
                if isinstance(workhorse_preflight.get("model"), dict)
                else {},
                "policy": workhorse_preflight.get("policy")
                if isinstance(workhorse_preflight.get("policy"), dict)
                else {},
            },
            "policy": {
                "review_default_runs_model": False,
                "run_model_requires_explicit_flag": True,
                "non_resident": True,
                "starts_llama_server": False,
                "action_execution": False,
                "final_safety_gate": False,
                "requires_downstream_validator": True,
            },
        },
        "qwen_lazy_load": {
            "profiles": qwen_profiles,
            "ready": qwen_ready,
            "default_context_size": min(qwen_default_contexts)
            if qwen_default_contexts
            else None,
            "max_context_size": max(qwen_max_contexts) if qwen_max_contexts else None,
            "rare_deep_contexts": sorted(
                {
                    value
                    for item in qwen_profiles.values()
                    for value in (safe_int(item.get("max_context_size"), 0),)
                    if value and value > safe_int(item.get("default_context_size"), 0)
                }
            ),
        },
        "gates": {
            "model_execution_now": {
                "allowed": model_execution_allowed,
                "status": execution_status,
                "preflight_ok": workhorse_preflight.get("ok"),
                "preflight_decision": preflight_decision,
                "blocked_reasons": preflight_blocked_reasons,
                "resource_decision": preflight_resource.get("decision"),
                "resource_latest_plan_decision": latest_plan.get("decision"),
            },
            "mode": {
                "selected_mode": mode_latest.get("selected_mode"),
                "effective_mode": mode_latest.get("effective_mode"),
                "degraded": bool(mode_latest.get("degraded")),
                "max_unattended_class": launch_policy.get("max_unattended_class"),
                "can_start_heavy_unattended": launch_policy.get(
                    "can_start_heavy_unattended"
                ),
                "operator_force_supported": launch_policy.get(
                    "operator_force_supported"
                ),
                "cpu_routed_heavy": {
                    "can_start": cpu_routed_heavy.get("can_start"),
                    "can_start_unattended": cpu_routed_heavy.get(
                        "can_start_unattended"
                    ),
                    "requires_route_application": cpu_routed_heavy.get(
                        "requires_route_application"
                    ),
                    "command": cpu_routed_heavy.get("command"),
                    "cpuset": nested_get(
                        cpu_routed_heavy, ["policy", "route", "cpuset"]
                    ),
                    "thread_limit": nested_get(
                        cpu_routed_heavy, ["policy", "route", "thread_limit"]
                    ),
                    "thermal_class": nested_get(
                        cpu_routed_heavy, ["policy", "distribution", "thermal_class"]
                    ),
                    "package_temperature_c_max": nested_get(
                        cpu_routed_heavy,
                        ["policy", "distribution", "package_temperature_c_max"],
                    ),
                },
            },
            "resource": {
                "latest_plan_decision": latest_plan.get("decision"),
                "latest_plan_request": latest_plan.get("request")
                if isinstance(latest_plan.get("request"), dict)
                else {},
                "preflight_decision": preflight_resource.get("decision"),
                "preflight_blocked_reasons": list(
                    preflight_resource.get("blocked_reasons")
                    if isinstance(preflight_resource.get("blocked_reasons"), list)
                    else []
                ),
                "systemd": preflight_resource.get("systemd")
                if isinstance(preflight_resource.get("systemd"), dict)
                else {},
            },
        },
        "evidence_paths": {
            "registry": str(AI_LLM_REGISTRY_LATEST_PATH),
            "workhorse_preflight": str(AI_LLM_WORKHORSE_PREFLIGHT_LATEST_PATH),
            "workhorse_pack": str(AI_LLM_WORKHORSE_PACK_LATEST_PATH),
            "workhorse_review": str(AI_LLM_WORKHORSE_REVIEW_LATEST_PATH),
            "workhorse_validate": str(AI_LLM_WORKHORSE_VALIDATE_LATEST_PATH),
            "resource": str(RESOURCE_LATEST_PATH),
            "mode": str(MODE_LATEST_PATH),
        },
        "policy": {
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "capability_presence_is_stack_promotion": False,
            "model_execution_in_self_awareness_graph": False,
            "default_model_execution": False,
            "human_approval_before_mutation": True,
            "operator_force_required_for_model_execution": not model_execution_allowed,
            "candidate_output_is_owner_truth": False,
            "action_execution": False,
            "qwen_lazy_load_is_not_resident_brain": True,
            "review_route_is_not_final_safety_gate": True,
        },
    }


def llm_escalation_detail_complete(
    detail: dict[str, Any], *, config: SelfAwarenessCognitiveConfig
) -> bool:
    SCHEMA_PREFIX = config.schema_prefix
    if not isinstance(detail, dict):
        return False
    profiles = nested_get(detail, ["registry", "profiles"]) or {}
    qwen_profiles = nested_get(detail, ["qwen_lazy_load", "profiles"]) or {}
    return (
        detail.get("schema")
        == f"{SCHEMA_PREFIX}_self_awareness_llm_escalation_detail_v1"
        and detail.get("route_ready") is True
        and (detail.get("review_pipeline_ready") is True)
        and (detail.get("status") == "ready_review_only")
        and all(
            (
                isinstance(profiles.get(name), dict)
                and profiles[name].get("status") == "ready"
                for name in ("gemma4.workhorse", "qwen36.ordinary", "qwen36.heretic")
            )
        )
        and (nested_get(detail, ["workhorse", "pack", "ok"]) is True)
        and (
            nested_get(detail, ["workhorse", "pack", "allowed_source_ids"]) is not None
        )
        and (
            safe_int(
                nested_get(detail, ["workhorse", "pack", "summary", "source_ids"]), 0
            )
            > 0
        )
        and (
            nested_get(detail, ["workhorse", "pack", "policy", "e4b_may_review_only"])
            is True
        )
        and (nested_get(detail, ["workhorse", "review", "ok"]) is True)
        and (
            nested_get(detail, ["workhorse", "review", "summary", "model_used"])
            is False
        )
        and (
            safe_int(
                nested_get(detail, ["workhorse", "review", "summary", "fails"]), -1
            )
            == 0
        )
        and (
            nested_get(detail, ["workhorse", "review", "policy", "action_execution"])
            is False
        )
        and (
            nested_get(detail, ["workhorse", "review", "policy", "starts_llama_server"])
            is False
        )
        and (
            nested_get(detail, ["workhorse", "review", "policy", "resident_service"])
            is False
        )
        and (nested_get(detail, ["workhorse", "validate", "ok"]) is True)
        and (
            safe_int(
                nested_get(detail, ["workhorse", "validate", "summary", "fails"]), -1
            )
            == 0
        )
        and (
            nested_get(detail, ["workhorse", "preflight", "decision"])
            in {"allow", "ready", "block"}
        )
        and (
            nested_get(
                detail,
                ["workhorse", "preflight", "policy", "default_review_runs_model"],
            )
            is False
        )
        and (
            nested_get(
                detail, ["workhorse", "preflight", "policy", "starts_llama_server"]
            )
            is False
        )
        and (
            nested_get(detail, ["workhorse", "preflight", "policy", "resident_service"])
            is False
        )
        and (nested_get(detail, ["qwen_lazy_load", "ready"]) is True)
        and all(
            (
                isinstance(qwen_profiles.get(name), dict)
                and qwen_profiles[name].get("status") == "ready"
                and (qwen_profiles[name].get("declared_class") == "heavy")
                and (qwen_profiles[name].get("local_exists") is True)
                and (qwen_profiles[name].get("runtime_ok") is True)
                and (qwen_profiles[name].get("host_layer_mutates_stack") is False)
                and nested_get(qwen_profiles[name], ["lazy_load", "start_command"])
                and nested_get(qwen_profiles[name], ["lazy_load", "request_command"])
                and nested_get(qwen_profiles[name], ["server", "cpuset"])
                for name in ("qwen36.ordinary", "qwen36.heretic")
            )
        )
        and (
            nested_get(detail, ["gates", "model_execution_now", "status"])
            in {
                "allowed_now",
                "blocked_by_preflight",
                "operator_force_required",
                "gated_unknown",
            }
        )
        and (
            nested_get(detail, ["gates", "model_execution_now", "allowed"])
            in {True, False}
        )
        and (
            nested_get(detail, ["gates", "mode", "operator_force_supported"])
            is not None
        )
        and (
            nested_get(detail, ["gates", "mode", "cpu_routed_heavy", "command"])
            is not None
        )
        and (
            nested_get(detail, ["gates", "resource", "preflight_decision"]) is not None
        )
        and (nested_get(detail, ["policy", "host_layer_mutates_stack"]) is False)
        and (nested_get(detail, ["policy", "writes_project_roots"]) is False)
        and (
            nested_get(detail, ["policy", "capability_presence_is_stack_promotion"])
            is False
        )
        and (
            nested_get(detail, ["policy", "model_execution_in_self_awareness_graph"])
            is False
        )
        and (nested_get(detail, ["policy", "default_model_execution"]) is False)
        and (nested_get(detail, ["policy", "human_approval_before_mutation"]) is True)
        and (nested_get(detail, ["policy", "action_execution"]) is False)
        and (
            nested_get(detail, ["policy", "qwen_lazy_load_is_not_resident_brain"])
            is True
        )
        and (
            nested_get(detail, ["policy", "review_route_is_not_final_safety_gate"])
            is True
        )
    )


def governance_gate_detail(
    memory_latest: dict[str, Any],
    resource_latest: dict[str, Any],
    mode_latest: dict[str, Any],
) -> dict[str, Any]:
    memory_summary = nested_get(memory_latest, ["meminfo", "summary"]) or {}
    zram_summary = nested_get(memory_latest, ["zram", "summary"]) or {}
    resource_summary = (
        nested_get(resource_latest, ["latest_orchestrator", "summary"]) or {}
    )
    latest_plan = (
        resource_latest.get("latest_plan")
        if isinstance(resource_latest.get("latest_plan"), dict)
        else {}
    )
    latest_run = (
        resource_latest.get("latest_run")
        if isinstance(resource_latest.get("latest_run"), dict)
        else {}
    )
    latest_plan_request = (
        latest_plan.get("request")
        if isinstance(latest_plan.get("request"), dict)
        else {}
    )
    latest_run_request = (
        latest_run.get("request") if isinstance(latest_run.get("request"), dict) else {}
    )
    launch_policy = (
        mode_latest.get("launch_policy")
        if isinstance(mode_latest.get("launch_policy"), dict)
        else {}
    )
    operating = (
        mode_latest.get("operating")
        if isinstance(mode_latest.get("operating"), dict)
        else {}
    )
    thermal = (
        mode_latest.get("thermal")
        if isinstance(mode_latest.get("thermal"), dict)
        else {}
    )
    memory_class = memory_latest.get("class") or nested_get(
        memory_latest, ["summary", "class"]
    )
    resource_status = resource_summary.get("status") or (
        "ok" if resource_latest.get("ok") else "unavailable"
    )
    mode_status = (
        "degraded"
        if mode_latest.get("degraded")
        else mode_latest.get("effective_mode") or mode_latest.get("selected_mode")
    )
    memory_ready = bool(memory_latest.get("ok") and memory_class)
    resource_ready = bool(resource_latest.get("ok") and resource_summary)
    mode_ready = bool(mode_latest.get("schema") and (not mode_latest.get("degraded")))
    return {
        "memory_status": memory_class,
        "resource_status": resource_status,
        "mode_status": mode_status,
        "readiness": {
            "status": "ready"
            if memory_ready and resource_ready and mode_ready
            else "degraded",
            "memory_ready": memory_ready,
            "resource_ready": resource_ready,
            "mode_ready": mode_ready,
            "degraded_reasons": list(
                mode_latest.get("degraded_reasons")
                if isinstance(mode_latest.get("degraded_reasons"), list)
                else []
            ),
        },
        "memory": {
            "schema": memory_latest.get("schema"),
            "ok": memory_latest.get("ok"),
            "class": memory_class,
            "reasons": memory_latest.get("reasons")
            if isinstance(memory_latest.get("reasons"), list)
            else [],
            "mem_available_mib": memory_summary.get("mem_available_mib"),
            "mem_available_percent": memory_summary.get("mem_available_percent"),
            "swap_used_percent": memory_summary.get("swap_used_percent"),
            "psi_some_avg10": nested_get(memory_latest, ["psi", "some", "avg10"]),
            "psi_full_avg10": nested_get(memory_latest, ["psi", "full", "avg10"]),
            "zram_resident_mib": zram_summary.get("total_memory_mib"),
            "automatic_kill": nested_get(memory_latest, ["policy", "automatic_kill"]),
            "automatic_tuning": nested_get(
                memory_latest, ["policy", "automatic_tuning"]
            ),
        },
        "resource": {
            "schema": resource_latest.get("schema"),
            "ok": resource_latest.get("ok"),
            "status": resource_status,
            "orchestrator_summary": resource_summary,
            "latest_plan_decision": latest_plan.get("decision"),
            "latest_plan_request": {
                "class": latest_plan_request.get("class")
                or latest_plan_request.get("normalized_class"),
                "kind": latest_plan_request.get("kind")
                or latest_plan_request.get("normalized_kind"),
                "unattended": latest_plan_request.get("unattended"),
            },
            "latest_run_ok": latest_run.get("ok"),
            "latest_run_request": {
                "class": latest_run_request.get("class"),
                "kind": latest_run_request.get("kind"),
                "unattended": latest_run_request.get("unattended"),
            },
            "launches_new_processes_only": nested_get(
                resource_latest, ["contract", "launches_new_processes_only"]
            ),
            "systemd_user_scope": nested_get(
                resource_latest, ["contract", "systemd_user_scope"]
            ),
            "future_stack_consumption": nested_get(
                resource_latest, ["contract", "future_stack_consumption"]
            ),
        },
        "mode": {
            "schema": mode_latest.get("schema"),
            "selected_mode": mode_latest.get("selected_mode"),
            "effective_mode": mode_latest.get("effective_mode"),
            "degraded": bool(mode_latest.get("degraded")),
            "degraded_reasons": list(
                mode_latest.get("degraded_reasons")
                if isinstance(mode_latest.get("degraded_reasons"), list)
                else []
            ),
            "target_power_profile": mode_latest.get("target_power_profile"),
            "actual_power_profile": mode_latest.get("actual_power_profile"),
            "profile_matches_target": mode_latest.get("profile_matches_target"),
            "power_profile_external_boost": mode_latest.get(
                "power_profile_external_boost"
            ),
            "thermal_class": nested_get(operating, ["temperature", "class"])
            or operating.get("thermal_class"),
            "temperature_c_max": thermal.get("temperature_c_max")
            or nested_get(operating, ["temperature", "temperature_c_max"]),
            "max_unattended_class": launch_policy.get("max_unattended_class"),
            "can_start_heavy_unattended": launch_policy.get(
                "can_start_heavy_unattended"
            ),
            "can_start_sustained_unattended": launch_policy.get(
                "can_start_sustained_unattended"
            ),
            "gate_new_unattended_tasks": launch_policy.get("gate_new_unattended_tasks"),
            "do_not_kill_running_tasks": launch_policy.get("do_not_kill_running_tasks"),
        },
        "policy": {
            "host_layer_mutates_stack": False,
            "mutates_existing_processes": False,
            "automatic_kill": nested_get(memory_latest, ["policy", "automatic_kill"])
            is True,
            "automatic_remediation": False,
            "operator_force_required_for_blocked_work": True,
        },
    }


def governance_gate_detail_complete(detail: dict[str, Any]) -> bool:
    if not isinstance(detail, dict):
        return False
    return (
        bool(detail.get("memory_status"))
        and bool(detail.get("resource_status"))
        and bool(detail.get("mode_status"))
        and bool(nested_get(detail, ["readiness", "status"]))
        and bool(nested_get(detail, ["memory", "class"]))
        and isinstance(nested_get(detail, ["resource", "orchestrator_summary"]), dict)
        and bool(nested_get(detail, ["mode", "effective_mode"]))
        and (nested_get(detail, ["policy", "host_layer_mutates_stack"]) is False)
        and (nested_get(detail, ["policy", "mutates_existing_processes"]) is False)
        and (nested_get(detail, ["policy", "automatic_remediation"]) is False)
    )


def investigation_failure_recovery(
    thread_id: str,
    latest_checkpoint_id: str | None = None,
    *,
    config: SelfAwarenessCognitiveConfig,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    NERVOUS_SEMANTIC_MAINTAIN_REVIEW_COMMAND = config.semantic_maintain_review_command
    NERVOUS_SEMANTIC_MAINTAIN_RETRY_COMMAND = config.semantic_maintain_retry_command
    return {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_investigation_failure_recovery_v1",
        "supported": True,
        "thread_id": thread_id,
        "latest_checkpoint_id": latest_checkpoint_id,
        "routes": [
            {
                "kind": "node_order_divergence",
                "command": "abyss-machine self-awareness investigate --query latest --json",
                "machine_action": "refresh_machine_owned_readmodels_then_replay",
            },
            {
                "kind": "missing_parent_checkpoint",
                "command": f"abyss-machine self-awareness replay --thread-id {thread_id} --json",
                "machine_action": "report_divergence_and_keep_latest_artifact_unchanged",
            },
            {
                "kind": "stale_freshness_gate",
                "command": NERVOUS_SEMANTIC_MAINTAIN_REVIEW_COMMAND,
                "retry_command": NERVOUS_SEMANTIC_MAINTAIN_RETRY_COMMAND,
                "machine_action": "review_resource_gated_freshness_maintenance_before_reasoning",
            },
            {
                "kind": "open_stack_requirement",
                "command": "abyss-machine self-awareness requirements --json",
                "machine_action": "record_stack_owned_handoff_only",
            },
        ],
        "policy": {
            "host_layer_mutates_stack": False,
            "action_execution": False,
            "automatic_remediation": False,
            "human_approval_before_mutation": True,
        },
    }


def investigation_working_stack_gap_packet(
    selected_episode: dict[str, Any],
    *,
    paths: SelfAwarenessCognitivePaths,
    config: SelfAwarenessCognitiveConfig,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    SELF_AWARENESS_EPISODES_LATEST_PATH = paths.episodes_latest
    if (
        not isinstance(selected_episode, dict)
        or selected_episode.get("episode_kind") != "working_stack_usage_gap"
    ):
        return {}
    gap = (
        selected_episode.get("working_stack_gap")
        if isinstance(selected_episode.get("working_stack_gap"), dict)
        else {}
    )
    service = str(gap.get("service") or selected_episode.get("service") or "")
    safe_next = (
        gap.get("safe_next_action")
        if isinstance(gap.get("safe_next_action"), dict)
        else {}
    )
    verifier_commands = [
        str(item)
        for item in (
            gap.get("verifier_commands")
            if isinstance(gap.get("verifier_commands"), list)
            else []
        )
        if item
    ]
    evidence_refs = (
        selected_episode.get("evidence_refs")
        if isinstance(selected_episode.get("evidence_refs"), list)
        else []
    )
    return {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_investigation_working_stack_gap_v1",
        "selected_episode_id": selected_episode.get("episode_id"),
        "episode_kind": selected_episode.get("episode_kind"),
        "truth_level": selected_episode.get("truth_level"),
        "service": service,
        "owner_route": gap.get("owner_route")
        or selected_episode.get("owner_route")
        or "abyss-stack",
        "working_stack_link_id": gap.get("working_stack_link_id"),
        "machine_usage_status": gap.get("machine_usage_status"),
        "usage_gap": gap.get("usage_gap"),
        "affected_spatial_nodes": selected_episode.get("affected_spatial_nodes")
        if isinstance(selected_episode.get("affected_spatial_nodes"), list)
        else [],
        "event_ids": selected_episode.get("event_ids")
        if isinstance(selected_episode.get("event_ids"), list)
        else [],
        "closure_blocker_keys": gap.get("closure_blocker_keys")
        if isinstance(gap.get("closure_blocker_keys"), list)
        else [],
        "safe_next_action": safe_next,
        "verifier_commands": verifier_commands,
        "request": {
            "id": "working-stack-gap:" + (service or "unknown"),
            "kind": "working_stack_usage_gap",
            "owner": "abyss-stack",
            "service": service,
            "reason": gap.get("usage_gap")
            or "working stack organ has unexhausted usable potential",
            "machine_action": "handoff_only",
            "command": safe_next.get("command")
            or "abyss-machine self-awareness working-stack --json",
            "source_command": "abyss-machine self-awareness episodes --json",
            "automatic": False,
            "requires_human_approval": True,
            "executes_commands": False,
            "host_layer_mutates_stack": False,
            "working_stack_link_id": gap.get("working_stack_link_id"),
            "machine_usage_status": gap.get("machine_usage_status"),
            "closure_blocker_keys": gap.get("closure_blocker_keys")
            if isinstance(gap.get("closure_blocker_keys"), list)
            else [],
            "safe_next_action": safe_next,
            "verifier_commands": verifier_commands,
            "policy": {
                "handoff_only": True,
                "automatic": False,
                "requires_human_approval": True,
                "executes_commands": False,
                "host_layer_mutates_stack": False,
                "action_execution": False,
            },
            "evidence_refs": evidence_refs[:20]
            or [
                {
                    "path": str(SELF_AWARENESS_EPISODES_LATEST_PATH),
                    "episode_id": selected_episode.get("episode_id"),
                }
            ],
        },
        "complete": bool(
            service
            and gap.get("working_stack_link_id")
            and gap.get("machine_usage_status")
            and gap.get("usage_gap")
            and safe_next
            and verifier_commands
            and (nested_get(safe_next, ["host_layer_mutates_stack"]) is False)
            and (nested_get(safe_next, ["executes_commands"]) is False)
        ),
        "policy": {
            "handoff_only": True,
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "action_execution": False,
            "automatic_remediation": False,
            "human_approval_before_mutation": True,
        },
        "evidence_refs": evidence_refs[:40]
        or [
            {
                "path": str(SELF_AWARENESS_EPISODES_LATEST_PATH),
                "episode_id": selected_episode.get("episode_id"),
            }
        ],
    }


def investigation_working_stack_gap_complete(
    packet: dict[str, Any], *, config: SelfAwarenessCognitiveConfig
) -> bool:
    SCHEMA_PREFIX = config.schema_prefix
    if not isinstance(packet, dict) or not packet:
        return False
    request = packet.get("request") if isinstance(packet.get("request"), dict) else {}
    return (
        packet.get("schema")
        == f"{SCHEMA_PREFIX}_self_awareness_investigation_working_stack_gap_v1"
        and packet.get("episode_kind") == "working_stack_usage_gap"
        and (packet.get("truth_level") == "working_stack_gap_candidate")
        and bool(packet.get("selected_episode_id"))
        and bool(packet.get("service"))
        and (packet.get("owner_route") == "abyss-stack")
        and bool(packet.get("working_stack_link_id"))
        and bool(packet.get("machine_usage_status"))
        and bool(packet.get("usage_gap"))
        and bool(packet.get("closure_blocker_keys"))
        and bool(packet.get("verifier_commands"))
        and (
            nested_get(packet, ["safe_next_action", "requires_human_approval"]) is True
        )
        and (
            nested_get(packet, ["safe_next_action", "host_layer_mutates_stack"])
            is False
        )
        and (nested_get(packet, ["safe_next_action", "executes_commands"]) is False)
        and (request.get("kind") == "working_stack_usage_gap")
        and (request.get("automatic") is False)
        and (request.get("host_layer_mutates_stack") is False)
        and (request.get("executes_commands") is False)
        and (nested_get(packet, ["policy", "host_layer_mutates_stack"]) is False)
        and (nested_get(packet, ["policy", "executes_commands"]) is False)
        and (nested_get(packet, ["policy", "action_execution"]) is False)
        and bool(packet.get("evidence_refs"))
    )

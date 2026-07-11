from __future__ import annotations

import collections
import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from . import self_awareness_contracts


DocumentPort = Callable[..., Any]


@dataclass(frozen=True)
class SelfAwarenessValidationConstants:
    stack_user_source_root: Path
    investigation_node_order: Sequence[str]
    memory_space_required_gates: Sequence[str]
    requirement_probes_latest: Path
    secret_pattern: Any
    working_stack_expected_live_services: Sequence[str]


@dataclass(frozen=True)
class SelfAwarenessValidationRepairPort:
    load_latest_json: DocumentPort
    now_iso: DocumentPort
    reaction_status: DocumentPort
    response_status: DocumentPort
    activation_smoke: DocumentPort
    alerts: DocumentPort
    autolink: DocumentPort
    capabilities: DocumentPort
    completion_audit: DocumentPort
    context: DocumentPort
    episodes: DocumentPort
    export: DocumentPort
    investigate: DocumentPort
    objective_coverage_audit: DocumentPort
    probe: DocumentPort
    replay: DocumentPort
    requirement_probes: DocumentPort
    requirements: DocumentPort
    spatial_graph: DocumentPort
    stack_closure_dossier: DocumentPort
    status: DocumentPort
    timeline: DocumentPort
    trace_context_fallback: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessValidationContractPort:
    add_check: DocumentPort
    bridge_manifest: DocumentPort
    stack_bridge_artifact_routes: DocumentPort
    storage_path_protection: DocumentPort
    activation_smoke_needs_refresh: DocumentPort
    ai_multimodal_detail_complete: DocumentPort
    autolink_complete: DocumentPort
    body_trace_complete: DocumentPort
    completion_route_packet_issues: DocumentPort
    coverage_audit_blocker_linkage_issues: DocumentPort
    cycle_bridge_proof_complete: DocumentPort
    cycle_from_zero_chain_sources: DocumentPort
    cycle_from_zero_proof: DocumentPort
    cycle_from_zero_proof_complete: DocumentPort
    entity_event_document_map_issues: DocumentPort
    event_issues: DocumentPort
    governance_gate_detail_complete: DocumentPort
    llm_escalation_detail_complete: DocumentPort
    paths_document: DocumentPort
    reaction_candidate_response_depth_complete: DocumentPort
    requirement_probes_export_ready: DocumentPort
    resident_cognitive_cycle_chain_overlay: DocumentPort
    resident_cognitive_packet_complete: DocumentPort
    resident_cognitive_replay_complete: DocumentPort
    resident_worker_detail_complete: DocumentPort
    response_entity_event_document_context_complete: DocumentPort
    response_route_depth_complete: DocumentPort
    self_tests: DocumentPort
    signal_fabric_summary: DocumentPort
    stack_compat_contract_complete: DocumentPort
    stack_coverage_impact_complete: DocumentPort
    stack_organ_use_packet_complete: DocumentPort
    stack_requirement_closure_acceptance_complete: DocumentPort
    stack_requirement_runbook_complete: DocumentPort
    top_level_lineage_complete: DocumentPort
    trace_context_fallback_complete: DocumentPort
    validate_document_from_checks: DocumentPort
    working_stack_activation_closure_acceptance_complete: DocumentPort
    working_stack_activation_entry_complete: DocumentPort
    working_stack_activation_gap_route_complete: DocumentPort
    working_stack_activation_smoke_complete: DocumentPort
    working_stack_activation_smoke_row_complete: DocumentPort
    working_stack_activation_synthetic_proof_complete: DocumentPort
    working_stack_activation_synthetic_scenario_complete: DocumentPort
    working_stack_link_integrity_matrix_complete: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessSelfTestPort:
    add_check: DocumentPort
    context_from_text: DocumentPort
    correlation_index: DocumentPort
    event_issues: DocumentPort
    failure_matrix_fixture: DocumentPort
    make_event: DocumentPort
    query_fixture: DocumentPort
    redact_text: DocumentPort
    requirement_item: DocumentPort
    time_bucket: DocumentPort


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def self_tests(
    *,
    now_utc: dt.datetime,
    contract_port: SelfAwarenessSelfTestPort,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    add_check = contract_port.add_check
    context_from_text = contract_port.context_from_text
    correlation_index = contract_port.correlation_index
    event_issues = contract_port.event_issues
    failure_matrix_fixture = contract_port.failure_matrix_fixture
    make_event = contract_port.make_event
    query_fixture = contract_port.query_fixture
    redact_text = contract_port.redact_text
    requirement_item = contract_port.requirement_item
    time_bucket = contract_port.time_bucket
    nested_get = self_awareness_contracts.nested_get
    generated_at = now_utc.isoformat()
    traceparent = "00-" + ("a" * 32) + "-" + ("b" * 16) + "-01"
    valid_event = make_event(
        "log",
        "loki",
        event_time="2026-01-01T00:00:00+00:00",
        observed_at="2026-01-01T00:00:01+00:00",
        source_query='{container="route-api"}',
        resource={"service": "route-api", "container": "route-api", "owner_surface": "abyss-stack", "labels": {"container": "route-api"}, "write": False},
        context=context_from_text("traceparent=" + traceparent),
        space={"host": "fixture", "owner_surface": "abyss-stack"},
        body="ok traceparent=" + traceparent,
        evidence_refs=[{"fixture": "valid"}],
    )
    invalid_event = dict(valid_event)
    invalid_event.pop("evidence_refs", None)
    add_check(checks, "ok" if not event_issues(valid_event) else "fail", "fixture_valid_event", "valid observation event fixture accepted", {"issues": event_issues(valid_event)})
    add_check(checks, "ok" if event_issues(invalid_event) else "fail", "fixture_invalid_event", "malformed observation event fixture rejected", {"issues": event_issues(invalid_event)})
    secret_preview = redact_text("Authorization: Bearer " + "sk" + "-testsecret1234567890")
    add_check(checks, "ok" if "sk-test" not in secret_preview.lower() and "bearer" not in secret_preview.lower() else "fail", "fixture_redaction", "secret-like values are redacted", {"preview": secret_preview})
    e2 = make_event(
        "metric",
        "prometheus",
        event_time="2026-01-01T00:00:02+00:00",
        resource={"service": "route-api", "owner_surface": "abyss-stack", "write": False},
        context={"trace_id": valid_event["context"].get("trace_id")},
        body={"value": 1},
        evidence_refs=[{"fixture": "same_trace"}],
    )
    e3 = make_event(
        "log",
        "loki",
        event_time="2026-01-01T00:20:00+00:00",
        resource={"service": "route-api", "owner_surface": "abyss-stack", "write": False},
        body="unrelated",
        evidence_refs=[{"fixture": "unrelated"}],
    )
    index = correlation_index([valid_event, e2, e3])
    context_key = "trace_id:" + str(valid_event["context"].get("trace_id"))
    linked = nested_get(index, ["indexes", "by_context", context_key]) or []
    add_check(checks, "ok" if len(linked) == 2 else "fail", "fixture_same_trace_links", "same trace links log and metric events", {"context_key": context_key, "linked": linked})
    buckets = nested_get(index, ["indexes", "by_time_bucket"]) or {}
    max_bucket_size = max((len(value) for value in buckets.values()), default=0)
    add_check(checks, "ok" if max_bucket_size < 3 else "fail", "fixture_unrelated_time_window", "unrelated later event does not over-correlate by time", {"buckets": buckets})
    bad_label_event = make_event(
        "log",
        "loki",
        resource={"service": "route-api", "owner_surface": "abyss-stack", "labels": {"trace_id": "abc"}, "write": False},
        body="bad label",
        evidence_refs=[{"fixture": "bad_label"}],
    )
    add_check(checks, "ok" if any(issue.startswith("unbounded_label") for issue in event_issues(bad_label_event)) else "fail", "fixture_unbounded_label_rejected", "unbounded context IDs are rejected as labels", {"issues": event_issues(bad_label_event)})
    resident_model_context_event = make_event(
        "model",
        "llm",
        event_time="2026-01-01T00:00:04+00:00",
        resource={
            "service": "warm-e2b-gemma4",
            "model": "gemma4",
            "owner_surface": "abyss-machine",
            "labels": {"service": "warm-e2b-gemma4", "role": "resident_llm"},
            "write": False,
        },
        context={
            "trace_id": "c" * 32,
            "span_id": "d" * 16,
            "thread_id": "thread-fixture",
            "checkpoint_id": "checkpoint-fixture",
        },
        body={"prompt": "Authorization: Bearer sk-fixture-secret", "response_status": "ok"},
        evidence_refs=[{"fixture": "resident_model_context"}],
        truth_level="resident_model_observation",
    )
    resident_model_links = nested_get(resident_model_context_event, ["fabric", "context_links", "links"]) or {}
    resident_model_label_policy = nested_get(resident_model_context_event, ["fabric", "label_policy"]) or {}
    add_check(
        checks,
        "ok"
        if not event_issues(resident_model_context_event)
        and resident_model_links.get("trace_id")
        and resident_model_links.get("thread_id") == "thread-fixture"
        and resident_model_links.get("checkpoint_id") == "checkpoint-fixture"
        and not resident_model_label_policy.get("forbidden_context_label_keys")
        and "sk-fixture" not in str(resident_model_context_event.get("body_preview", "")).lower()
        else "fail",
        "fixture_resident_model_context_not_loki_labels",
        "Resident model trace, thread, and checkpoint IDs remain context links and secret-like body text is redacted",
        {
            "issues": event_issues(resident_model_context_event),
            "context_links": resident_model_links,
            "label_policy": resident_model_label_policy,
            "body_preview": resident_model_context_event.get("body_preview"),
        },
    )
    model_event = make_event(
        "model",
        "llm",
        resource={"service": "warm-e2b-gemma4.spark", "owner_surface": "abyss-machine", "write": False},
        body={"status": "running", "model": "gemma-4-E2B"},
        evidence_refs=[{"fixture": "warm_e2b"}],
    )
    add_check(
        checks,
        "ok" if not event_issues(model_event) else "fail",
        "fixture_warm_e2b_model_event",
        "warm-E2B model event fixture is accepted by the observation schema",
        {"issues": event_issues(model_event)},
    )
    rag_event = make_event(
        "rag",
        "rag",
        resource={"service": "machine-rag-validate", "owner_surface": "abyss-machine", "write": False},
        body={"validate": "ok"},
        evidence_refs=[{"fixture": "rag_validate"}],
    )
    add_check(
        checks,
        "ok" if not event_issues(rag_event) else "fail",
        "fixture_rag_event",
        "RAG event fixture is accepted by the observation schema",
        {"issues": event_issues(rag_event)},
    )
    observability_event = make_event(
        "metric",
        "observability",
        event_time="2026-01-01T00:00:03+00:00",
        resource={"service": "observability-thermal-battery", "owner_surface": "abyss-machine", "write": False},
        space={"host": "fixture", "owner_surface": "abyss-machine", "path": "/var/lib/abyss-machine/observability/thermal-battery/latest.json"},
        body={"thermal_class": "ok", "battery_class": "ok", "temperature_c_max": 61.9, "battery_capacity_percent": 79},
        evidence_refs=[{"path": "/var/lib/abyss-machine/observability/thermal-battery/latest.json", "fixture": "observability"}],
    )
    add_check(
        checks,
        "ok" if not event_issues(observability_event) else "fail",
        "fixture_observability_metric_event",
        "host thermal/battery observability event fixture is accepted by the observation schema",
        {"issues": event_issues(observability_event)},
    )
    scheduler_event = make_event(
        "service",
        "scheduler",
        event_time="2026-01-01T00:00:04+00:00",
        resource={
            "service": "abyss-machine-heartbeat.timer",
            "owner_surface": "abyss-machine",
            "timer_unit": "abyss-machine-heartbeat.timer",
            "timer_scope": "user",
            "timer_category": "heartbeat",
            "timer_active": True,
            "timer_enabled": True,
            "timer_activates": "abyss-machine-heartbeat.service",
            "route": "scheduler/heartbeat",
            "write": False,
        },
        context={
            "scheduler_unit": "abyss-machine-heartbeat.timer",
            "scheduler_scope": "user",
            "scheduler_category": "heartbeat",
        },
        space={"host": "fixture", "owner_surface": "abyss-machine", "layer": "host-scheduler", "route": "scheduler/heartbeat"},
        body={"unit": "abyss-machine-heartbeat.timer", "active": "active", "enabled": "enabled"},
        evidence_refs=[{"schema": "abyss_machine_systemd_timer_state_v1", "fixture": "scheduler"}],
        truth_level="host_scheduler_state",
    )
    add_check(
        checks,
        "ok" if not event_issues(scheduler_event) else "fail",
        "fixture_scheduler_service_event",
        "host scheduler timer event fixture is accepted by the observation schema",
        {"issues": event_issues(scheduler_event), "correlation_keys": nested_get(scheduler_event, ["fabric", "context_links", "correlation_keys"])},
    )
    requirement = requirement_item(
        "fixture.missing-tempo",
        "Fixture missing trace backend",
        reason="fixture proves missing stack capability becomes a requirement, not a host mutation",
        detection={"url": "http://127.0.0.1:3200/ready", "error": "connection refused", "evidence_refs": [{"fixture": "missing_tempo"}]},
        expected_shape={"backend": "Tempo", "mutated_by": "abyss-stack"},
    )
    add_check(
        checks,
        "ok" if requirement.get("owner") == "abyss-stack" and requirement.get("host_layer_mutates_stack") is False else "fail",
        "fixture_missing_capability_requirement",
        "missing stack capability is represented as owner-routed non-mutating requirement",
        requirement,
    )
    query_document = query_fixture("route-api", limit=3, generated_at=generated_at)
    query_plan = query_document.get("query_plan") if isinstance(query_document.get("query_plan"), dict) else {}
    add_check(
        checks,
        "ok" if query_plan.get("bounded") and query_plan.get("promql") and query_plan.get("logql") and query_plan.get("readmodels") else "fail",
        "fixture_bounded_query_builders",
        "query builder fixture exposes bounded PromQL, LogQL, and host readmodel plans",
        {"query_plan": query_plan},
    )
    failure_matrix = failure_matrix_fixture(generated_at=generated_at)
    failure_ids = {str(item.get("id")) for item in failure_matrix.get("rows", []) if isinstance(item, dict)}
    add_check(
        checks,
        "ok" if {"machine.resource-denial", "machine.secret-redaction", "stack.downtime-bounded-readonly"}.issubset(failure_ids) else "fail",
        "fixture_failure_matrix_required_rows",
        "failure matrix fixture includes denial, redaction, and stack downtime rows",
        {"missing": sorted({"machine.resource-denial", "machine.secret-redaction", "stack.downtime-bounded-readonly"} - failure_ids), "summary": failure_matrix.get("summary")},
    )
    stale_time = (now_utc - dt.timedelta(days=7)).isoformat()
    stale_event = make_event(
        "validation",
        "synthetic",
        event_time=stale_time,
        observed_at=stale_time,
        resource={"service": "stale-fixture", "owner_surface": "abyss-machine", "write": False},
        body="stale latest fixture",
        evidence_refs=[{"fixture": "stale"}],
    )
    add_check(
        checks,
        "ok" if time_bucket(stale_event.get("event_time")) != "unknown" else "fail",
        "fixture_stale_time_parse",
        "stale data can still be parsed and routed to freshness checks",
        {"event_time": stale_event.get("event_time"), "bucket": time_bucket(stale_event.get("event_time"))},
    )
    return checks


def build_validation_document(
    *,
    schema_prefix: str,
    require_cycle: bool,
    strict: bool,
    allow_probe_refresh: bool,
    checks: list[dict[str, Any]],
    loaded: dict[str, dict[str, Any]],
    constants: SelfAwarenessValidationConstants,
    repair_port: SelfAwarenessValidationRepairPort,
    contract_port: SelfAwarenessValidationContractPort,
) -> dict[str, Any]:
    SCHEMA_PREFIX = schema_prefix
    ABYSS_STACK_USER_SOURCE_ROOT = constants.stack_user_source_root
    SELF_AWARENESS_INVESTIGATION_NODE_ORDER = constants.investigation_node_order
    SELF_AWARENESS_MEMORY_SPACE_REQUIRED_GATES = constants.memory_space_required_gates
    SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH = constants.requirement_probes_latest
    SELF_AWARENESS_SECRET_RE = constants.secret_pattern
    SELF_AWARENESS_WORKING_STACK_EXPECTED_LIVE_SERVICES = constants.working_stack_expected_live_services

    load_latest_json = repair_port.load_latest_json
    now_iso = repair_port.now_iso
    reaction_status = repair_port.reaction_status
    response_status = repair_port.response_status
    self_awareness_activation_smoke = repair_port.activation_smoke
    self_awareness_alerts = repair_port.alerts
    self_awareness_autolink = repair_port.autolink
    self_awareness_capabilities = repair_port.capabilities
    self_awareness_completion_audit = repair_port.completion_audit
    self_awareness_context = repair_port.context
    self_awareness_episodes = repair_port.episodes
    self_awareness_export = repair_port.export
    self_awareness_investigate = repair_port.investigate
    self_awareness_objective_coverage_audit = repair_port.objective_coverage_audit
    self_awareness_probe = repair_port.probe
    self_awareness_replay = repair_port.replay
    self_awareness_requirement_probes = repair_port.requirement_probes
    self_awareness_requirements = repair_port.requirements
    self_awareness_spatial_graph = repair_port.spatial_graph
    self_awareness_stack_closure_dossier = repair_port.stack_closure_dossier
    self_awareness_status = repair_port.status
    self_awareness_timeline = repair_port.timeline
    self_awareness_trace_context_fallback = repair_port.trace_context_fallback

    topology_validation_add = contract_port.add_check
    bridge_manifest = contract_port.bridge_manifest
    stack_bridge_artifact_routes = contract_port.stack_bridge_artifact_routes
    storage_path_protection = contract_port.storage_path_protection
    self_awareness_activation_smoke_needs_refresh = contract_port.activation_smoke_needs_refresh
    self_awareness_ai_multimodal_detail_complete = contract_port.ai_multimodal_detail_complete
    self_awareness_autolink_complete = contract_port.autolink_complete
    self_awareness_body_trace_complete = contract_port.body_trace_complete
    self_awareness_completion_route_packet_issues = contract_port.completion_route_packet_issues
    self_awareness_coverage_audit_blocker_linkage_issues = contract_port.coverage_audit_blocker_linkage_issues
    self_awareness_cycle_bridge_proof_complete = contract_port.cycle_bridge_proof_complete
    self_awareness_cycle_from_zero_chain_sources = contract_port.cycle_from_zero_chain_sources
    self_awareness_cycle_from_zero_proof = contract_port.cycle_from_zero_proof
    self_awareness_cycle_from_zero_proof_complete = contract_port.cycle_from_zero_proof_complete
    self_awareness_entity_event_document_map_issues = contract_port.entity_event_document_map_issues
    self_awareness_event_issues = contract_port.event_issues
    self_awareness_governance_gate_detail_complete = contract_port.governance_gate_detail_complete
    self_awareness_llm_escalation_detail_complete = contract_port.llm_escalation_detail_complete
    self_awareness_paths = contract_port.paths_document
    self_awareness_reaction_candidate_response_depth_complete = contract_port.reaction_candidate_response_depth_complete
    self_awareness_requirement_probes_export_ready = contract_port.requirement_probes_export_ready
    self_awareness_resident_cognitive_cycle_chain_overlay = contract_port.resident_cognitive_cycle_chain_overlay
    self_awareness_resident_cognitive_packet_complete = contract_port.resident_cognitive_packet_complete
    self_awareness_resident_cognitive_replay_complete = contract_port.resident_cognitive_replay_complete
    self_awareness_resident_worker_detail_complete = contract_port.resident_worker_detail_complete
    self_awareness_response_entity_event_document_context_complete = contract_port.response_entity_event_document_context_complete
    self_awareness_response_route_depth_complete = contract_port.response_route_depth_complete
    self_awareness_self_tests = contract_port.self_tests
    self_awareness_signal_fabric_summary = contract_port.signal_fabric_summary
    self_awareness_stack_compat_contract_complete = contract_port.stack_compat_contract_complete
    self_awareness_stack_coverage_impact_complete = contract_port.stack_coverage_impact_complete
    self_awareness_stack_organ_use_packet_complete = contract_port.stack_organ_use_packet_complete
    self_awareness_stack_requirement_closure_acceptance_complete = contract_port.stack_requirement_closure_acceptance_complete
    self_awareness_stack_requirement_runbook_complete = contract_port.stack_requirement_runbook_complete
    self_awareness_top_level_lineage_complete = contract_port.top_level_lineage_complete
    self_awareness_trace_context_fallback_complete = contract_port.trace_context_fallback_complete
    self_awareness_validate_document_from_checks = contract_port.validate_document_from_checks
    self_awareness_working_stack_activation_closure_acceptance_complete = contract_port.working_stack_activation_closure_acceptance_complete
    self_awareness_working_stack_activation_entry_complete = contract_port.working_stack_activation_entry_complete
    self_awareness_working_stack_activation_gap_route_complete = contract_port.working_stack_activation_gap_route_complete
    self_awareness_working_stack_activation_smoke_complete = contract_port.working_stack_activation_smoke_complete
    self_awareness_working_stack_activation_smoke_row_complete = contract_port.working_stack_activation_smoke_row_complete
    self_awareness_working_stack_activation_synthetic_proof_complete = contract_port.working_stack_activation_synthetic_proof_complete
    self_awareness_working_stack_activation_synthetic_scenario_complete = contract_port.working_stack_activation_synthetic_scenario_complete
    self_awareness_working_stack_link_integrity_matrix_complete = contract_port.working_stack_link_integrity_matrix_complete

    nested_get = self_awareness_contracts.nested_get
    safe_int = _safe_int
    requirements_doc = loaded.get("requirements", {})
    requirement_probes_doc = loaded.get("requirement_probes", {})
    if (
        isinstance(requirements_doc, dict)
        and isinstance(requirement_probes_doc, dict)
        and not self_awareness_requirement_probes_export_ready(requirements_doc, requirement_probes_doc)
    ):
        requirement_probes_doc = self_awareness_requirement_probes(write_latest=True, requirements_doc=requirements_doc)
        loaded["requirement_probes"] = requirement_probes_doc
        loaded["stack_closure_dossier"] = self_awareness_stack_closure_dossier(
            write_latest=True,
            requirements_doc=requirements_doc,
            requirement_probes_doc=requirement_probes_doc,
        )
    coverage_audit_doc = loaded.get("coverage_audit", {})
    coverage_linkage_issues = self_awareness_coverage_audit_blocker_linkage_issues(coverage_audit_doc)
    if coverage_linkage_issues:
        coverage_audit_doc = self_awareness_objective_coverage_audit(write_latest=True)
        loaded["coverage_audit"] = coverage_audit_doc
        coverage_linkage_issues = self_awareness_coverage_audit_blocker_linkage_issues(coverage_audit_doc)
    topology_validation_add(
        checks,
        "fail" if coverage_linkage_issues else "ok",
        "coverage_audit_stack_blocker_linkage",
        "coverage audit blocked rows expose stack requirement ids, blocking checks, coverage impacts, and affected coverage planes",
        {
            "issues": coverage_linkage_issues,
            "summary": coverage_audit_doc.get("summary") if isinstance(coverage_audit_doc, dict) else None,
            "blocked_rows": coverage_audit_doc.get("blocked_rows") if isinstance(coverage_audit_doc, dict) else None,
        },
    )
    working_gap_coverage_rows = coverage_audit_doc.get("working_stack_gap_rows") if isinstance(coverage_audit_doc.get("working_stack_gap_rows"), list) else []
    if working_gap_coverage_rows and (
        safe_int(nested_get(coverage_audit_doc, ["summary", "working_stack_activation_synthetic_proofs"]), -1) != len(working_gap_coverage_rows)
        or safe_int(nested_get(coverage_audit_doc, ["summary", "working_stack_activation_synthetic_proofs_complete"]), -1) != len(working_gap_coverage_rows)
        or nested_get(coverage_audit_doc, ["summary", "working_stack_activation_synthetic_proof_incomplete_rows"])
    ):
        coverage_audit_doc = self_awareness_objective_coverage_audit(write_latest=True)
        loaded["coverage_audit"] = coverage_audit_doc
        working_gap_coverage_rows = coverage_audit_doc.get("working_stack_gap_rows") if isinstance(coverage_audit_doc.get("working_stack_gap_rows"), list) else []
    working_gap_coverage_bad: list[str] = []
    if safe_int(nested_get(coverage_audit_doc, ["summary", "working_stack_usage_gaps"]), 0) != len(working_gap_coverage_rows):
        working_gap_coverage_bad.append("gap_row_count_mismatch")
    if safe_int(nested_get(coverage_audit_doc, ["summary", "working_stack_gap_rows"]), -1) != len(working_gap_coverage_rows):
        working_gap_coverage_bad.append("summary_gap_row_count_mismatch")
    if safe_int(nested_get(coverage_audit_doc, ["summary", "working_stack_activation_entries"]), -1) != len(working_gap_coverage_rows):
        working_gap_coverage_bad.append("activation_entry_count_mismatch")
    if safe_int(nested_get(coverage_audit_doc, ["summary", "working_stack_activation_entries_complete"]), -1) != len(working_gap_coverage_rows):
        working_gap_coverage_bad.append("activation_complete_count_mismatch")
    if safe_int(nested_get(coverage_audit_doc, ["summary", "working_stack_activation_synthetic_scenarios"]), -1) != len(working_gap_coverage_rows):
        working_gap_coverage_bad.append("activation_scenario_count_mismatch")
    if safe_int(nested_get(coverage_audit_doc, ["summary", "working_stack_activation_synthetic_scenarios_complete"]), -1) != len(working_gap_coverage_rows):
        working_gap_coverage_bad.append("activation_scenario_complete_count_mismatch")
    if safe_int(nested_get(coverage_audit_doc, ["summary", "working_stack_activation_closure_acceptance_packets"]), -1) != len(working_gap_coverage_rows):
        working_gap_coverage_bad.append("activation_closure_acceptance_count_mismatch")
    if safe_int(nested_get(coverage_audit_doc, ["summary", "working_stack_activation_closure_acceptance_packets_complete"]), -1) != len(working_gap_coverage_rows):
        working_gap_coverage_bad.append("activation_closure_acceptance_complete_count_mismatch")
    if safe_int(nested_get(coverage_audit_doc, ["summary", "working_stack_activation_compat_requirements"]), -1) != len(working_gap_coverage_rows):
        working_gap_coverage_bad.append("activation_compat_requirement_count_mismatch")
    if safe_int(nested_get(coverage_audit_doc, ["summary", "working_stack_activation_synthetic_proofs"]), -1) != len(working_gap_coverage_rows):
        working_gap_coverage_bad.append("activation_proof_count_mismatch")
    if safe_int(nested_get(coverage_audit_doc, ["summary", "working_stack_activation_synthetic_proofs_complete"]), -1) != len(working_gap_coverage_rows):
        working_gap_coverage_bad.append("activation_proof_complete_count_mismatch")
    if nested_get(coverage_audit_doc, ["summary", "working_stack_activation_synthetic_proof_incomplete_rows"]):
        working_gap_coverage_bad.append("activation_proof_incomplete_rows")
    expected_activation_smoke_rows = safe_int(nested_get(coverage_audit_doc, ["summary", "working_stack_organs"]), len(working_gap_coverage_rows))
    if expected_activation_smoke_rows > 0 and safe_int(nested_get(coverage_audit_doc, ["summary", "working_stack_activation_smoke_rows"]), -1) != expected_activation_smoke_rows:
        working_gap_coverage_bad.append("activation_smoke_count_mismatch")
    if expected_activation_smoke_rows > 0 and safe_int(nested_get(coverage_audit_doc, ["summary", "working_stack_activation_smoke_rows_ok"]), -1) != expected_activation_smoke_rows:
        working_gap_coverage_bad.append("activation_smoke_ok_count_mismatch")
    if nested_get(coverage_audit_doc, ["summary", "working_stack_activation_smoke_incomplete_rows"]):
        working_gap_coverage_bad.append("activation_smoke_incomplete_rows")
    if nested_get(coverage_audit_doc, ["summary", "working_stack_activation_smoke_failed_services"]):
        working_gap_coverage_bad.append("activation_smoke_failed_services")
    if working_gap_coverage_rows and not nested_get(coverage_audit_doc, ["summary", "working_stack_gap_coverage_planes"]):
        working_gap_coverage_bad.append("missing_gap_coverage_planes")
    coverage_activation_dossier = coverage_audit_doc.get("working_stack_activation_dossier") if isinstance(coverage_audit_doc.get("working_stack_activation_dossier"), dict) else {}
    if working_gap_coverage_rows and coverage_activation_dossier.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_working_stack_activation_dossier_v1":
        working_gap_coverage_bad.append("activation_dossier_missing")
    if working_gap_coverage_rows and nested_get(coverage_activation_dossier, ["policy", "host_layer_mutates_stack"]) is not False:
        working_gap_coverage_bad.append("activation_dossier_policy")
    for row in working_gap_coverage_rows:
        if not isinstance(row, dict):
            working_gap_coverage_bad.append("malformed_gap_row")
            continue
        row_id = str(row.get("id") or "unknown")
        if row.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_working_stack_gap_coverage_row_v1":
            working_gap_coverage_bad.append(f"{row_id}:schema")
        if row.get("status") != "working_stack_usage_gap":
            working_gap_coverage_bad.append(f"{row_id}:status")
        if row.get("owner") != "abyss-stack":
            working_gap_coverage_bad.append(f"{row_id}:owner")
        if not row.get("service") or not row.get("machine_usage_status") or not row.get("usage_gap"):
            working_gap_coverage_bad.append(f"{row_id}:identity")
        if not row.get("working_stack_link_id"):
            working_gap_coverage_bad.append(f"{row_id}:working_stack_link")
        if not row.get("blocked_coverage_planes"):
            working_gap_coverage_bad.append(f"{row_id}:coverage_planes")
        if not row.get("closure_blocker_keys"):
            working_gap_coverage_bad.append(f"{row_id}:closure_blockers")
        if not row.get("missing_checks"):
            working_gap_coverage_bad.append(f"{row_id}:missing_checks")
        if not isinstance(row.get("activation_readiness"), dict) or row["activation_readiness"].get("schema") != f"{SCHEMA_PREFIX}_self_awareness_working_stack_activation_readiness_v1":
            working_gap_coverage_bad.append(f"{row_id}:activation_readiness")
        closure_acceptance = row.get("closure_acceptance") if isinstance(row.get("closure_acceptance"), dict) else {}
        if not self_awareness_working_stack_activation_closure_acceptance_complete(closure_acceptance):
            working_gap_coverage_bad.append(f"{row_id}:closure_acceptance")
        if closure_acceptance and closure_acceptance.get("service") != row.get("service"):
            working_gap_coverage_bad.append(f"{row_id}:closure_acceptance_identity")
        if closure_acceptance and closure_acceptance.get("working_stack_link_id") != row.get("working_stack_link_id"):
            working_gap_coverage_bad.append(f"{row_id}:closure_acceptance_link")
        if closure_acceptance and nested_get(closure_acceptance, ["stack_compat_requirement", "owner"]) != "abyss-stack":
            working_gap_coverage_bad.append(f"{row_id}:closure_acceptance_owner")
        if closure_acceptance and nested_get(closure_acceptance, ["policy", "host_layer_mutates_stack"]) is not False:
            working_gap_coverage_bad.append(f"{row_id}:closure_acceptance_policy")
        scenario = row.get("synthetic_scenario") if isinstance(row.get("synthetic_scenario"), dict) else {}
        if not self_awareness_working_stack_activation_synthetic_scenario_complete(scenario):
            working_gap_coverage_bad.append(f"{row_id}:synthetic_scenario")
        if scenario.get("service") != row.get("service"):
            working_gap_coverage_bad.append(f"{row_id}:synthetic_scenario_identity")
        proof = row.get("synthetic_proof") if isinstance(row.get("synthetic_proof"), dict) else {}
        if not self_awareness_working_stack_activation_synthetic_proof_complete(proof):
            working_gap_coverage_bad.append(f"{row_id}:synthetic_proof")
        if proof.get("service") != row.get("service"):
            working_gap_coverage_bad.append(f"{row_id}:synthetic_proof_identity")
        if proof.get("machine_usage_status") != row.get("machine_usage_status"):
            working_gap_coverage_bad.append(f"{row_id}:synthetic_proof_status")
        if proof.get("working_stack_link_id") != row.get("working_stack_link_id"):
            working_gap_coverage_bad.append(f"{row_id}:synthetic_proof_link")
        if nested_get(proof, ["policy", "host_layer_mutates_stack"]) is not False:
            working_gap_coverage_bad.append(f"{row_id}:synthetic_proof_mutation")
        if nested_get(proof, ["policy", "executes_commands"]) is not False or nested_get(proof, ["policy", "action_execution"]) is not False:
            working_gap_coverage_bad.append(f"{row_id}:synthetic_proof_exec")
        activation_smoke = row.get("activation_smoke") if isinstance(row.get("activation_smoke"), dict) else {}
        if not activation_smoke or activation_smoke.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_working_stack_activation_smoke_compact_v1":
            working_gap_coverage_bad.append(f"{row_id}:activation_smoke")
        if activation_smoke and activation_smoke.get("complete") is not True:
            working_gap_coverage_bad.append(f"{row_id}:activation_smoke_incomplete")
        if activation_smoke and (
            activation_smoke.get("service") != row.get("service")
            or activation_smoke.get("machine_usage_status") != row.get("machine_usage_status")
            or activation_smoke.get("working_stack_link_id") != row.get("working_stack_link_id")
        ):
            working_gap_coverage_bad.append(f"{row_id}:activation_smoke_identity")
        activation_smoke_is_movement = activation_smoke.get("row_kind") == "organ_movement" if activation_smoke else False
        if activation_smoke and activation_smoke_is_movement:
            if not activation_smoke.get("stack_organ_use_packet_id") or not activation_smoke.get("stack_organ_event_id"):
                working_gap_coverage_bad.append(f"{row_id}:activation_smoke_movement_packet")
            if not activation_smoke.get("activation_gap_classification"):
                working_gap_coverage_bad.append(f"{row_id}:activation_smoke_activation_gap")
            if not activation_smoke.get("movement_categories"):
                working_gap_coverage_bad.append(f"{row_id}:activation_smoke_movement_categories")
        if activation_smoke and not activation_smoke_is_movement and safe_int(activation_smoke.get("divergences"), -1) != 0:
            working_gap_coverage_bad.append(f"{row_id}:activation_smoke_divergence")
        if activation_smoke and not activation_smoke_is_movement and activation_smoke.get("working_stack_gap_replayable") is not True:
            working_gap_coverage_bad.append(f"{row_id}:activation_smoke_replayable")
        if activation_smoke and nested_get(activation_smoke, ["policy", "host_layer_mutates_stack"]) is not False:
            working_gap_coverage_bad.append(f"{row_id}:activation_smoke_policy")
        if not isinstance(row.get("runbook_candidate"), dict) or row["runbook_candidate"].get("machine_executes_stack_change") is not False:
            working_gap_coverage_bad.append(f"{row_id}:runbook")
        if not row.get("verifier_commands"):
            working_gap_coverage_bad.append(f"{row_id}:verifiers")
        if not row.get("evidence_refs"):
            working_gap_coverage_bad.append(f"{row_id}:evidence_refs")
        if nested_get(row, ["safe_next_action", "requires_human_approval"]) is not True:
            working_gap_coverage_bad.append(f"{row_id}:safe_next_approval")
        if nested_get(row, ["safe_next_action", "host_layer_mutates_stack"]) is not False:
            working_gap_coverage_bad.append(f"{row_id}:safe_next_mutation")
        if nested_get(row, ["safe_next_action", "executes_commands"]) is not False:
            working_gap_coverage_bad.append(f"{row_id}:safe_next_exec")
        if nested_get(row, ["policy", "host_layer_mutates_stack"]) is not False:
            working_gap_coverage_bad.append(f"{row_id}:policy_mutation")
        if nested_get(row, ["policy", "executes_commands"]) is not False:
            working_gap_coverage_bad.append(f"{row_id}:policy_exec")
        if nested_get(row, ["policy", "automatic_remediation"]) is not False:
            working_gap_coverage_bad.append(f"{row_id}:policy_automatic")
    topology_validation_add(
        checks,
        "fail" if working_gap_coverage_bad else "ok",
        "coverage_audit_working_stack_gap_rows",
        "coverage audit exposes every working-stack usage gap as an explicit owner-routed row with safe-next, verifier, evidence, and no stack mutation policy",
        {
            "bad": working_gap_coverage_bad,
            "summary": coverage_audit_doc.get("summary") if isinstance(coverage_audit_doc, dict) else None,
            "services": [str(row.get("service")) for row in working_gap_coverage_rows if isinstance(row, dict)],
        },
    )
    working_stack_link_integrity = coverage_audit_doc.get("working_stack_link_integrity") if isinstance(coverage_audit_doc.get("working_stack_link_integrity"), dict) else {}
    if not self_awareness_working_stack_link_integrity_matrix_complete(working_stack_link_integrity):
        coverage_audit_doc = self_awareness_objective_coverage_audit(write_latest=True)
        loaded["coverage_audit"] = coverage_audit_doc
        working_stack_link_integrity = coverage_audit_doc.get("working_stack_link_integrity") if isinstance(coverage_audit_doc.get("working_stack_link_integrity"), dict) else {}
    link_integrity_rows = working_stack_link_integrity.get("rows") if isinstance(working_stack_link_integrity.get("rows"), list) else []
    link_integrity_bad: list[str] = []
    if not self_awareness_working_stack_link_integrity_matrix_complete(working_stack_link_integrity):
        link_integrity_bad.append("matrix_incomplete")
    if safe_int(nested_get(coverage_audit_doc, ["summary", "working_stack_link_integrity_rows"]), -1) != len(link_integrity_rows):
        link_integrity_bad.append("summary_row_count_mismatch")
    if safe_int(nested_get(coverage_audit_doc, ["summary", "working_stack_link_integrity_rows_complete"]), -1) != len(link_integrity_rows):
        link_integrity_bad.append("summary_complete_count_mismatch")
    if safe_int(nested_get(coverage_audit_doc, ["summary", "working_stack_link_integrity_rows"]), -1) != safe_int(nested_get(coverage_audit_doc, ["summary", "working_stack_organs"]), -2):
        link_integrity_bad.append("organ_count_mismatch")
    if nested_get(working_stack_link_integrity, ["policy", "host_layer_mutates_stack"]) is not False:
        link_integrity_bad.append("mutation_policy")
    for row in link_integrity_rows:
        if not isinstance(row, dict):
            link_integrity_bad.append("malformed_row")
            continue
        service = str(row.get("service") or "unknown")
        if row.get("complete") is not True:
            link_integrity_bad.append(f"{service}:incomplete")
        if (
            not row.get("working_stack_link_id")
            or not row.get("event_id")
            or (row.get("episode_required") is True and not row.get("episode_ids"))
        ):
            link_integrity_bad.append(f"{service}:identity")
        for check_key in ("working_stack_link", "event_projected", "event_fabric_link", "timeline_window", "spatial_service_to_link_edge", "context_indexed", "episode_present", "coverage_gap_row", "activation_smoke_if_gap"):
            if nested_get(row, ["checks", check_key]) is not True:
                link_integrity_bad.append(f"{service}:{check_key}")
        if nested_get(row, ["policy", "host_layer_mutates_stack"]) is not False:
            link_integrity_bad.append(f"{service}:policy")
    topology_validation_add(
        checks,
        "fail" if link_integrity_bad else "ok",
        "working_stack_link_integrity_matrix",
        "every working-stack organ preserves a live working_stack_link through event fabric, timeline, spatial graph, context, episode, and gap coverage when applicable",
        {
            "bad": link_integrity_bad[:24],
            "summary": working_stack_link_integrity.get("summary") if isinstance(working_stack_link_integrity, dict) else None,
            "services": [str(row.get("service")) for row in link_integrity_rows if isinstance(row, dict) and row.get("service")],
        },
    )
    autolink_doc = loaded.get("autolink", {})
    if (
        not self_awareness_autolink_complete(autolink_doc)
        or safe_int(nested_get(autolink_doc, ["summary", "organ_links"]), -1) != len(link_integrity_rows)
        or safe_int(nested_get(autolink_doc, ["summary", "open_stack_requirements"]), -1) != safe_int(nested_get(loaded.get("stack_closure_dossier", {}), ["summary", "open_stack_requirements"]), -2)
    ):
        autolink_doc = self_awareness_autolink(
            write_latest=True,
            coverage_audit_doc=coverage_audit_doc,
            stack_closure_dossier_doc=loaded.get("stack_closure_dossier", {}),
            activation_smoke_doc=loaded.get("activation_smoke", {}),
        )
        loaded["autolink"] = autolink_doc
    autolink_organ_rows = autolink_doc.get("organ_links") if isinstance(autolink_doc.get("organ_links"), list) else []
    autolink_requirement_rows = autolink_doc.get("stack_requirement_links") if isinstance(autolink_doc.get("stack_requirement_links"), list) else []
    autolink_scenarios = autolink_doc.get("synthetic_scenarios") if isinstance(autolink_doc.get("synthetic_scenarios"), list) else []
    autolink_bad: list[str] = []
    if not self_awareness_autolink_complete(autolink_doc):
        autolink_bad.append("autolink_incomplete")
    if safe_int(nested_get(autolink_doc, ["summary", "organ_links"]), -1) != len(link_integrity_rows):
        autolink_bad.append("organ_link_count_mismatch")
    if safe_int(nested_get(autolink_doc, ["summary", "organ_links_complete"]), -1) != len(link_integrity_rows):
        autolink_bad.append("organ_link_complete_count_mismatch")
    if safe_int(nested_get(autolink_doc, ["summary", "working_stack_usage_gaps"]), -1) != safe_int(nested_get(coverage_audit_doc, ["summary", "working_stack_usage_gaps"]), -2):
        autolink_bad.append("working_stack_usage_gap_count_mismatch")
    if safe_int(nested_get(autolink_doc, ["summary", "open_stack_requirements"]), -1) != safe_int(nested_get(loaded.get("stack_closure_dossier", {}), ["summary", "open_stack_requirements"]), -2):
        autolink_bad.append("open_stack_requirement_count_mismatch")
    if safe_int(nested_get(autolink_doc, ["summary", "stack_requirement_links"]), -1) != len(autolink_requirement_rows):
        autolink_bad.append("stack_requirement_link_summary_mismatch")
    if safe_int(nested_get(autolink_doc, ["summary", "synthetic_scenarios_complete"]), -1) != len(autolink_scenarios):
        autolink_bad.append("synthetic_scenario_complete_count_mismatch")
    if not autolink_doc.get("state_digest") or not isinstance(autolink_doc.get("state_delta"), dict):
        autolink_bad.append("state_delta_missing")
    if nested_get(autolink_doc, ["policy", "host_layer_mutates_stack"]) is not False:
        autolink_bad.append("mutation_policy")
    if nested_get(autolink_doc, ["policy", "executes_commands"]) is not False or nested_get(autolink_doc, ["policy", "automatic_remediation"]) is not False:
        autolink_bad.append("execution_policy")
    for row in autolink_organ_rows:
        if not isinstance(row, dict):
            autolink_bad.append("malformed_organ_row")
            continue
        service = str(row.get("service") or "unknown")
        if row.get("complete") is not True:
            autolink_bad.append(f"{service}:organ_incomplete")
        for check_key in ("time_linked", "space_linked", "context_linked", "episode_linked"):
            if nested_get(row, ["checks", check_key]) is not True:
                autolink_bad.append(f"{service}:{check_key}")
        if nested_get(row, ["policy", "host_layer_mutates_stack"]) is not False:
            autolink_bad.append(f"{service}:policy")
    for row in autolink_requirement_rows:
        if not isinstance(row, dict):
            autolink_bad.append("malformed_requirement_row")
            continue
        requirement_id = str(row.get("requirement_id") or "unknown")
        if row.get("complete") is not True:
            autolink_bad.append(f"{requirement_id}:requirement_incomplete")
        for check_key in ("closure_acceptance", "coverage_impact", "owner_route", "episode_linked"):
            if nested_get(row, ["checks", check_key]) is not True:
                autolink_bad.append(f"{requirement_id}:{check_key}")
        if nested_get(row, ["policy", "host_layer_mutates_stack"]) is not False:
            autolink_bad.append(f"{requirement_id}:policy")
    for scenario in autolink_scenarios:
        if not isinstance(scenario, dict) or scenario.get("complete") is not True:
            autolink_bad.append(f"scenario:{scenario.get('id') if isinstance(scenario, dict) else 'malformed'}")
        if nested_get(scenario, ["policy", "host_layer_mutates_stack"]) is not False or nested_get(scenario, ["policy", "executes_commands"]) is not False:
            autolink_bad.append(f"scenario_policy:{scenario.get('id') if isinstance(scenario, dict) else 'malformed'}")
    topology_validation_add(
        checks,
        "fail" if autolink_bad else "ok",
        "self_awareness_autolink_matrix",
        "autolink records automatic time-space-context state deltas for every working-stack organ and owner-routed stack blocker",
        {
            "bad": autolink_bad[:32],
            "summary": autolink_doc.get("summary") if isinstance(autolink_doc, dict) else None,
            "state_delta": autolink_doc.get("state_delta") if isinstance(autolink_doc, dict) else None,
        },
    )
    stack_closure_for_smoke = loaded.get("stack_closure_dossier", {})
    activation_dossier_for_smoke = stack_closure_for_smoke.get("working_stack_activation_dossier") if isinstance(stack_closure_for_smoke.get("working_stack_activation_dossier"), dict) else {}
    activation_entries_for_smoke = activation_dossier_for_smoke.get("entries") if isinstance(activation_dossier_for_smoke.get("entries"), list) else []
    working_stack_for_smoke = loaded.get("working_stack", {})
    working_stack_organs_for_smoke = [
        organ for organ in (working_stack_for_smoke.get("organs") if isinstance(working_stack_for_smoke.get("organs"), list) else [])
        if isinstance(organ, dict) and organ.get("service")
    ]
    expected_smoke_services = {
        str(organ.get("service"))
        for organ in working_stack_organs_for_smoke
        if isinstance(organ, dict) and organ.get("service")
    }
    activation_smoke_doc = loaded.get("activation_smoke", {})
    if self_awareness_activation_smoke_needs_refresh(activation_smoke_doc, activation_entries_for_smoke, expected_smoke_services):
        activation_smoke_doc = self_awareness_activation_smoke(
            write_latest=True,
            stack_closure_dossier_doc=stack_closure_for_smoke,
            working_stack_doc=working_stack_for_smoke,
        )
        loaded["activation_smoke"] = activation_smoke_doc
    activation_smoke_rows = activation_smoke_doc.get("rows") if isinstance(activation_smoke_doc.get("rows"), list) else []
    activation_smoke_by_service = activation_smoke_doc.get("by_service") if isinstance(activation_smoke_doc.get("by_service"), dict) else {}
    stack_organ_use_packets = activation_smoke_doc.get("stack_organ_use_packets") if isinstance(activation_smoke_doc.get("stack_organ_use_packets"), list) else []
    stack_organ_use_packet_by_service = activation_smoke_doc.get("stack_organ_use_packet_by_service") if isinstance(activation_smoke_doc.get("stack_organ_use_packet_by_service"), dict) else {}
    activation_smoke_bad: list[str] = []
    if activation_smoke_doc.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_working_stack_activation_smoke_v1":
        activation_smoke_bad.append("schema")
    if not self_awareness_working_stack_activation_smoke_complete(activation_smoke_doc):
        activation_smoke_bad.append("complete")
    if set(str(item) for item in activation_smoke_by_service) != expected_smoke_services:
        activation_smoke_bad.append("service_index_mismatch")
    if safe_int(nested_get(activation_smoke_doc, ["summary", "stack_organs_expected"]), -1) != len(expected_smoke_services):
        activation_smoke_bad.append("stack_organ_expected_count_mismatch")
    if safe_int(nested_get(activation_smoke_doc, ["summary", "rows"]), -1) != len(expected_smoke_services):
        activation_smoke_bad.append("row_count_mismatch")
    if safe_int(nested_get(activation_smoke_doc, ["summary", "rows_ok"]), -1) != len(expected_smoke_services):
        activation_smoke_bad.append("rows_ok_count_mismatch")
    if safe_int(nested_get(activation_smoke_doc, ["summary", "stack_organ_use_packets"]), -1) != len(expected_smoke_services):
        activation_smoke_bad.append("stack_organ_use_packet_count_mismatch")
    if safe_int(nested_get(activation_smoke_doc, ["summary", "stack_organ_use_packets_complete"]), -1) != len(expected_smoke_services):
        activation_smoke_bad.append("stack_organ_use_packet_complete_count_mismatch")
    if set(str(item) for item in stack_organ_use_packet_by_service) != expected_smoke_services:
        activation_smoke_bad.append("stack_organ_use_packet_service_index_mismatch")
    if {str(packet.get("service")) for packet in stack_organ_use_packets if isinstance(packet, dict) and packet.get("service")} != expected_smoke_services:
        activation_smoke_bad.append("stack_organ_use_packet_service_list_mismatch")
    if nested_get(activation_smoke_doc, ["summary", "failed_services"]):
        activation_smoke_bad.append("failed_services")
    if nested_get(activation_smoke_doc, ["policy", "host_layer_mutates_stack"]) is not False:
        activation_smoke_bad.append("mutation_policy")
    if nested_get(activation_smoke_doc, ["policy", "executes_commands"]) is not False or nested_get(activation_smoke_doc, ["policy", "action_execution"]) is not False:
        activation_smoke_bad.append("exec_policy")
    for row in activation_smoke_rows:
        if not isinstance(row, dict):
            activation_smoke_bad.append("malformed_row")
            continue
        service = str(row.get("service") or "unknown")
        if not self_awareness_working_stack_activation_smoke_row_complete(row):
            activation_smoke_bad.append(f"{service}:row_incomplete")
        if service not in expected_smoke_services:
            activation_smoke_bad.append(f"{service}:unexpected_service")
        packet = row.get("stack_organ_use_packet") if isinstance(row.get("stack_organ_use_packet"), dict) else {}
        indexed_packet = stack_organ_use_packet_by_service.get(service) if isinstance(stack_organ_use_packet_by_service.get(service), dict) else {}
        if not self_awareness_stack_organ_use_packet_complete(packet):
            activation_smoke_bad.append(f"{service}:stack_organ_use_packet")
        if indexed_packet != packet:
            activation_smoke_bad.append(f"{service}:stack_organ_use_packet_index")
        if packet and (
            packet.get("service") != service
            or nested_get(packet, ["event", "machine_usage_status"]) != row.get("machine_usage_status")
            or nested_get(packet, ["event", "working_stack_link_id"]) != row.get("working_stack_link_id")
        ):
            activation_smoke_bad.append(f"{service}:stack_organ_use_packet_identity")
        if not nested_get(packet, ["observed_signal", "event_id"]):
            activation_smoke_bad.append(f"{service}:observed_signal")
        if not nested_get(packet, ["movement_selection", "categories"]):
            activation_smoke_bad.append(f"{service}:movement_selection")
        if nested_get(row, ["policy", "host_layer_mutates_stack"]) is not False or nested_get(row, ["policy", "action_execution"]) is not False:
            activation_smoke_bad.append(f"{service}:policy")
    topology_validation_add(
        checks,
        "fail" if activation_smoke_bad else "ok",
        "working_stack_activation_smoke_matrix",
        "every working-stack organ has a movement packet with observed signal, selection reason, and preserved service/status/link context",
        {
            "bad": activation_smoke_bad,
            "summary": activation_smoke_doc.get("summary") if isinstance(activation_smoke_doc, dict) else None,
            "expected_services": sorted(expected_smoke_services),
            "row_services": sorted(str(row.get("service")) for row in activation_smoke_rows if isinstance(row, dict) and row.get("service")),
        },
    )
    status_doc = self_awareness_status()
    status_summary = status_doc.get("summary") if isinstance(status_doc.get("summary"), dict) else {}
    status_open_potential = status_doc.get("open_potential") if isinstance(status_doc.get("open_potential"), dict) else {}
    status_open_requirement_map = status_doc.get("open_stack_requirements") if isinstance(status_doc.get("open_stack_requirements"), dict) else {}
    status_open_potential_rows = status_open_potential.get("rows") if isinstance(status_open_potential.get("rows"), list) else []
    status_open_requirement_rows = status_open_requirement_map.get("rows") if isinstance(status_open_requirement_map.get("rows"), list) else []
    expected_status_open_potential_services = sorted({
        str(row.get("service"))
        for row in autolink_organ_rows
        if isinstance(row, dict) and row.get("service") and row.get("usage_gap")
    })
    expected_status_open_requirement_ids = sorted({
        str(row.get("requirement_id"))
        for row in autolink_requirement_rows
        if isinstance(row, dict) and row.get("requirement_id") and row.get("automatic_link_state") == "open_stack_blocker"
    })
    status_body_bad: list[str] = []
    if status_doc.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_status_v1":
        status_body_bad.append("schema")
    if safe_int(status_open_potential.get("services"), -1) != len(expected_status_open_potential_services):
        status_body_bad.append("open_potential_count")
    if sorted(str(row.get("service")) for row in status_open_potential_rows if isinstance(row, dict) and row.get("service")) != expected_status_open_potential_services:
        status_body_bad.append("open_potential_services")
    if safe_int(status_open_requirement_map.get("requirements"), -1) != len(expected_status_open_requirement_ids):
        status_body_bad.append("open_stack_requirement_count")
    if sorted(str(row.get("requirement_id")) for row in status_open_requirement_rows if isinstance(row, dict) and row.get("requirement_id")) != expected_status_open_requirement_ids:
        status_body_bad.append("open_stack_requirement_ids")
    if sorted(str(item) for item in status_summary.get("open_potential_services", []) if item) != expected_status_open_potential_services:
        status_body_bad.append("summary_open_potential_services")
    if sorted(str(item) for item in status_summary.get("open_stack_requirement_ids", []) if item) != sorted(str(row.get("requirement_id")) for row in autolink_requirement_rows if isinstance(row, dict) and row.get("requirement_id")):
        status_body_bad.append("summary_open_stack_requirement_ids")
    autolink_by_service = {
        str(row.get("service")): row
        for row in autolink_organ_rows
        if isinstance(row, dict) and row.get("service")
    }
    for row in status_open_potential_rows:
        if not isinstance(row, dict):
            status_body_bad.append("malformed_open_potential_row")
            continue
        service = str(row.get("service") or "unknown")
        source = autolink_by_service.get(service, {})
        if row.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_open_potential_service_status_v1":
            status_body_bad.append(f"{service}:schema")
        if not row.get("working_stack_link_id") or row.get("working_stack_link_id") != source.get("working_stack_link_id"):
            status_body_bad.append(f"{service}:working_stack_link")
        if nested_get(row, ["activation_smoke", "link_matches_current"]) is not True:
            status_body_bad.append(f"{service}:activation_smoke_link")
        activation_gap_route = row.get("activation_gap_route") if isinstance(row.get("activation_gap_route"), dict) else {}
        if not self_awareness_working_stack_activation_gap_route_complete(activation_gap_route):
            status_body_bad.append(f"{service}:activation_gap_route")
        if activation_gap_route.get("service") != service:
            status_body_bad.append(f"{service}:activation_gap_route_service")
        if row.get("activation_gap_classification") != activation_gap_route.get("classification") or not row.get("activation_gap_classification"):
            status_body_bad.append(f"{service}:activation_gap_classification")
        if not row.get("closure_blocker_keys") or not row.get("missing_checks"):
            status_body_bad.append(f"{service}:closure_readiness")
        if not row.get("verifier_commands") or not row.get("evidence_refs"):
            status_body_bad.append(f"{service}:evidence_or_verifier")
        if nested_get(row, ["safe_next_action", "requires_human_approval"]) is not True:
            status_body_bad.append(f"{service}:safe_next_approval")
        if nested_get(row, ["safe_next_action", "host_layer_mutates_stack"]) is not False:
            status_body_bad.append(f"{service}:safe_next_mutation")
        if nested_get(row, ["policy", "host_layer_mutates_stack"]) is not False or nested_get(row, ["policy", "automatic_remediation"]) is not False:
            status_body_bad.append(f"{service}:policy")
    for row in status_open_requirement_rows:
        if not isinstance(row, dict):
            status_body_bad.append("malformed_open_stack_requirement_row")
            continue
        requirement_id = str(row.get("requirement_id") or "unknown")
        if row.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_open_stack_requirement_status_v1":
            status_body_bad.append(f"{requirement_id}:schema")
        if row.get("automatic_link_state") != "open_stack_blocker":
            status_body_bad.append(f"{requirement_id}:state")
        if not row.get("blocking_check_keys") or not row.get("coverage_planes") or not row.get("missing_checks"):
            status_body_bad.append(f"{requirement_id}:readiness")
        if not row.get("verifier_commands") or not row.get("evidence_refs"):
            status_body_bad.append(f"{requirement_id}:evidence_or_verifier")
        if nested_get(row, ["safe_next_action", "requires_human_approval"]) is not True:
            status_body_bad.append(f"{requirement_id}:safe_next_approval")
        if nested_get(row, ["safe_next_action", "host_layer_mutates_stack"]) is not False:
            status_body_bad.append(f"{requirement_id}:safe_next_mutation")
        if nested_get(row, ["policy", "host_layer_mutates_stack"]) is not False or nested_get(row, ["policy", "automatic_remediation"]) is not False:
            status_body_bad.append(f"{requirement_id}:policy")
    if nested_get(status_open_potential, ["policy", "host_layer_mutates_stack"]) is not False or nested_get(status_open_requirement_map, ["policy", "host_layer_mutates_stack"]) is not False:
        status_body_bad.append("top_level_policy")
    topology_validation_add(
        checks,
        "fail" if status_body_bad else "ok",
        "self_awareness_status_open_potential_routes",
        "status exposes open stack potential as agent-readable service and requirement rows with current links, smoke proof, verifier commands, safe-next policy, and evidence refs",
        {
            "bad": status_body_bad[:32],
            "open_potential_services": expected_status_open_potential_services,
            "open_stack_requirement_ids": expected_status_open_requirement_ids,
            "activation_gap_routes": sum(1 for row in status_open_potential_rows if isinstance(row, dict) and self_awareness_working_stack_activation_gap_route_complete(row.get("activation_gap_route"))),
            "status_summary": status_summary,
        },
    )
    trace_context_doc = loaded.get("trace_context", {})
    if not self_awareness_trace_context_fallback_complete(trace_context_doc):
        trace_context_doc = self_awareness_trace_context_fallback(
            write_latest=True,
            requirement_probes_doc=loaded.get("requirement_probes", {}),
            context_doc=loaded.get("context", {}),
            timeline_doc=loaded.get("timeline", {}),
            episodes_doc=loaded.get("episodes", {}),
        )
        loaded["trace_context"] = trace_context_doc
    trace_context_bad: list[str] = []
    if not self_awareness_trace_context_fallback_complete(trace_context_doc):
        trace_context_bad.append("fallback_incomplete")
    if trace_context_doc.get("stack_requirement_id") != "stack.trace-backend":
        trace_context_bad.append("requirement_identity")
    if trace_context_doc.get("closes_stack_requirement") is not False:
        trace_context_bad.append("false_closure_claim")
    if nested_get(trace_context_doc, ["summary", "stack_requirement_not_closed_by_fallback"]) is not True:
        trace_context_bad.append("not_closed_by_fallback_flag")
    if nested_get(trace_context_doc, ["summary", "traceparent_log_query_ok"]) is not True:
        trace_context_bad.append("traceparent_log_query")
    if nested_get(trace_context_doc, ["fallback", "loki_trace_context", "raw_log_exports_stored"]) is not False:
        trace_context_bad.append("raw_log_policy")
    if nested_get(trace_context_doc, ["policy", "host_layer_mutates_stack"]) is not False:
        trace_context_bad.append("mutation_policy")
    if nested_get(trace_context_doc, ["policy", "writes_project_roots"]) is not False:
        trace_context_bad.append("project_write_policy")
    if nested_get(trace_context_doc, ["policy", "closes_stack_requirement"]) is not False:
        trace_context_bad.append("policy_false_closure")
    if nested_get(trace_context_doc, ["policy", "adds_loki_labels"]) is not False:
        trace_context_bad.append("loki_label_policy")
    if nested_get(trace_context_doc, ["safe_next_action", "requires_human_approval"]) is not True:
        trace_context_bad.append("safe_next_approval")
    if nested_get(trace_context_doc, ["safe_next_action", "host_layer_mutates_stack"]) is not False:
        trace_context_bad.append("safe_next_mutation")
    topology_validation_add(
        checks,
        "fail" if trace_context_bad else "ok",
        "trace_context_fallback_depth",
        "trace-context fallback exposes Loki/Alloy/probe trace links while preserving stack.trace-backend as an open owner-routed requirement",
        {
            "bad": trace_context_bad,
            "summary": trace_context_doc.get("summary") if isinstance(trace_context_doc, dict) else None,
            "status": trace_context_doc.get("status") if isinstance(trace_context_doc, dict) else None,
            "safe_next_action": trace_context_doc.get("safe_next_action") if isinstance(trace_context_doc, dict) else None,
        },
    )
    context_doc_for_refresh = loaded.get("context", {})
    context_packet_for_refresh = (
        context_doc_for_refresh.get("context_packet")
        if isinstance(context_doc_for_refresh, dict) and isinstance(context_doc_for_refresh.get("context_packet"), dict)
        else {}
    )
    context_memory_for_refresh = (
        context_doc_for_refresh.get("memory_space")
        if isinstance(context_doc_for_refresh, dict) and isinstance(context_doc_for_refresh.get("memory_space"), dict)
        else {}
    )
    if (
        context_packet_for_refresh.get("complete") is not True
        or safe_int(nested_get(context_memory_for_refresh, ["summary", "retrieval_packets"]), 0) <= 0
        or nested_get(context_packet_for_refresh, ["sections", "resident_worker", "complete"]) is not True
        or nested_get(context_packet_for_refresh, ["sections", "governance_gates", "complete"]) is not True
    ):
        loaded["timeline"] = self_awareness_timeline(write_latest=True)
        loaded["spatial_graph"] = self_awareness_spatial_graph(write_latest=True)
        loaded["context"] = self_awareness_context(write_latest=True)
    events = loaded.get("events", {}).get("events") if isinstance(loaded.get("events", {}).get("events"), list) else []
    invalid_events = [{"event_id": event.get("event_id"), "issues": self_awareness_event_issues(event)} for event in events if isinstance(event, dict) and self_awareness_event_issues(event)]
    topology_validation_add(
        checks,
        "fail" if invalid_events else "ok",
        "observation_events_schema",
        "all observation events satisfy required schema and evidence refs",
        {"invalid": invalid_events[:12], "events": len(events)},
    )
    fabric_summary = nested_get(loaded.get("events", {}), ["summary", "signal_fabric"])
    fabric_summary = fabric_summary if isinstance(fabric_summary, dict) else self_awareness_signal_fabric_summary([event for event in events if isinstance(event, dict)])
    bad_fabric_rows = [
        event.get("event_id") for event in events
        if isinstance(event, dict)
        and (
            not isinstance(event.get("fabric"), dict)
            or event["fabric"].get("schema") != f"{SCHEMA_PREFIX}_self_awareness_signal_fabric_v1"
            or not isinstance(nested_get(event, ["fabric", "actor"]), dict)
            or not nested_get(event, ["fabric", "actor", "owner_surface"])
            or not isinstance(nested_get(event, ["fabric", "entity"]), dict)
            or not nested_get(event, ["fabric", "temporal", "time_bucket"])
            or not nested_get(event, ["fabric", "spatial", "owner_surface"])
            or not nested_get(event, ["fabric", "context_links", "correlation_keys"])
            or nested_get(event, ["fabric", "evidence_route", "has_refs"]) is not True
            or nested_get(event, ["fabric", "policy", "read_only"]) is not True
            or nested_get(event, ["fabric", "policy", "host_layer_mutates_stack"]) is not False
            or nested_get(event, ["fabric", "policy", "raw_body_stored"]) is not False
            or nested_get(event, ["fabric", "label_policy", "forbidden_context_label_keys"])
        )
    ]
    topology_validation_add(
        checks,
        "fail" if bad_fabric_rows or safe_int(fabric_summary.get("with_fabric"), 0) != len(events) or safe_int(fabric_summary.get("with_thread_or_checkpoint"), 0) <= 0 else "ok",
        "signal_fabric_depth",
        "observation events expose actor, entity, temporal, spatial, context-link, checkpoint/thread, evidence-route, and non-mutating policy fabric",
        {"bad_rows": bad_fabric_rows[:12], "summary": fabric_summary},
    )
    source_counts = collections.Counter(str(event.get("source") or "unknown") for event in events if isinstance(event, dict))
    required_fabric_sources = {"observability", "scheduler", "host-service", "ai", "llm", "rag", "nervous", "memory", "resource", "mode", "typing", "heartbeats", "reactions", "responses"}
    missing_fabric_sources = sorted(required_fabric_sources - set(source_counts))
    topology_validation_add(
        checks,
        "fail" if missing_fabric_sources else "ok",
        "signal_fabric_host_organs",
        "self-awareness fabric includes host observability, scheduler, active host services, AI, memory, resource, mode, typing, heartbeat, reaction, and response organs",
        {"missing_sources": missing_fabric_sources, "source_counts": dict(source_counts)},
    )
    context_rows_for_scheduler = loaded.get("context", {}).get("contexts") if isinstance(loaded.get("context", {}).get("contexts"), list) else []
    context_keys_for_scheduler = {str(row.get("key")) for row in context_rows_for_scheduler if isinstance(row, dict) and row.get("key")}
    scheduler_units = sorted({
        str(nested_get(event, ["context", "scheduler_unit"]))
        for event in events
        if isinstance(event, dict) and event.get("source") == "scheduler" and nested_get(event, ["context", "scheduler_unit"])
    })
    scheduler_categories = sorted({
        str(nested_get(event, ["context", "scheduler_category"]))
        for event in events
        if isinstance(event, dict) and event.get("source") == "scheduler" and nested_get(event, ["context", "scheduler_category"])
    })
    manual_collect_statuses = sorted({
        str(nested_get(event, ["context", "manual_collect_status"]))
        for event in events
        if isinstance(event, dict) and nested_get(event, ["context", "manual_collect_status"])
    })
    scheduler_context_bad: list[str] = []
    missing_scheduler_unit_contexts = [unit for unit in scheduler_units if f"scheduler_unit:{unit}" not in context_keys_for_scheduler]
    missing_scheduler_category_contexts = [category for category in scheduler_categories if f"scheduler_category:{category}" not in context_keys_for_scheduler]
    missing_manual_contexts = [status for status in manual_collect_statuses if f"manual_collect_status:{status}" not in context_keys_for_scheduler]
    if missing_scheduler_unit_contexts:
        scheduler_context_bad.append("missing_scheduler_unit_contexts")
    if missing_scheduler_category_contexts:
        scheduler_context_bad.append("missing_scheduler_category_contexts")
    if missing_manual_contexts:
        scheduler_context_bad.append("missing_manual_collect_contexts")
    if scheduler_units and safe_int(nested_get(loaded.get("context", {}), ["summary", "scheduler_unit_contexts"]), 0) < len(scheduler_units):
        scheduler_context_bad.append("scheduler_unit_summary_count")
    if scheduler_categories and safe_int(nested_get(loaded.get("context", {}), ["summary", "scheduler_category_contexts"]), 0) < len(scheduler_categories):
        scheduler_context_bad.append("scheduler_category_summary_count")
    topology_validation_add(
        checks,
        "fail" if scheduler_context_bad else "ok",
        "scheduler_context_links",
        "scheduler and manual collection context links are indexed as bounded context rows for temporal host-body reasoning",
        {
            "bad": scheduler_context_bad,
            "missing_scheduler_unit_contexts": missing_scheduler_unit_contexts[:16],
            "missing_scheduler_category_contexts": missing_scheduler_category_contexts[:16],
            "missing_manual_collect_contexts": missing_manual_contexts[:16],
            "scheduler_units": scheduler_units[:32],
            "scheduler_categories": scheduler_categories,
            "manual_collect_statuses": manual_collect_statuses,
            "context_summary": loaded.get("context", {}).get("summary") if isinstance(loaded.get("context"), dict) else None,
        },
    )
    host_service_units = sorted({
        str(nested_get(event, ["context", "host_service_unit"]))
        for event in events
        if isinstance(event, dict) and event.get("source") == "host-service" and nested_get(event, ["context", "host_service_unit"])
    })
    host_service_categories = sorted({
        str(nested_get(event, ["context", "host_service_category"]))
        for event in events
        if isinstance(event, dict) and event.get("source") == "host-service" and nested_get(event, ["context", "host_service_category"])
    })
    host_service_context_bad: list[str] = []
    missing_host_service_unit_contexts = [unit for unit in host_service_units if f"host_service_unit:{unit}" not in context_keys_for_scheduler]
    missing_host_service_category_contexts = [category for category in host_service_categories if f"host_service_category:{category}" not in context_keys_for_scheduler]
    if not host_service_units:
        host_service_context_bad.append("missing_host_service_events")
    if missing_host_service_unit_contexts:
        host_service_context_bad.append("missing_host_service_unit_contexts")
    if missing_host_service_category_contexts:
        host_service_context_bad.append("missing_host_service_category_contexts")
    if host_service_units and safe_int(nested_get(loaded.get("context", {}), ["summary", "host_service_unit_contexts"]), 0) < len(host_service_units):
        host_service_context_bad.append("host_service_unit_summary_count")
    if host_service_categories and safe_int(nested_get(loaded.get("context", {}), ["summary", "host_service_category_contexts"]), 0) < len(host_service_categories):
        host_service_context_bad.append("host_service_category_summary_count")
    topology_validation_add(
        checks,
        "fail" if host_service_context_bad else "ok",
        "host_service_context_links",
        "active abyss/aoa/ydotoold host services are projected as bounded service events and context rows for live host-body reasoning",
        {
            "bad": host_service_context_bad,
            "missing_host_service_unit_contexts": missing_host_service_unit_contexts[:16],
            "missing_host_service_category_contexts": missing_host_service_category_contexts[:16],
            "host_service_units": host_service_units[:32],
            "host_service_categories": host_service_categories,
            "context_summary": loaded.get("context", {}).get("summary") if isinstance(loaded.get("context"), dict) else None,
        },
    )
    routes = stack_bridge_artifact_routes()
    layer = routes.get("self_awareness") if isinstance(routes.get("self_awareness"), dict) else {}
    missing_routes = [
        name for name in (
            "capabilities", "requirements", "requirement_probes", "failure_matrix", "working_stack", "events", "collect", "query", "correlation", "timeline",
            "spatial_graph", "context", "episodes", "trace_context", "alerts", "investigate", "replay", "activation_smoke", "brief", "probe", "cycle", "export", "validate"
        )
        if name not in layer
    ]
    topology_validation_add(
        checks,
        "fail" if missing_routes else "ok",
        "bridge_artifact_routes",
        "stack bridge exposes self-awareness latest artifacts",
        {"missing": missing_routes},
    )
    bridge = bridge_manifest()
    commands = bridge.get("commands") if isinstance(bridge.get("commands"), dict) else {}
    required_command_keys = {
        f"self_awareness_{name}_json"
        for name in (
            "paths", "status", "capabilities", "requirements", "requirement_probes", "collect", "query", "correlate", "timeline", "spatial_graph",
            "context", "episodes", "trace_context", "alerts", "investigate", "replay", "activation_smoke", "brief", "failure_matrix", "working_stack", "probe", "cycle", "export", "validate"
        )
    }
    missing_commands = sorted(required_command_keys - set(commands))
    topology_validation_add(
        checks,
        "fail" if missing_commands else "ok",
        "bridge_commands",
        "main bridge exposes self-awareness commands",
        {"missing": missing_commands},
    )
    forbidden_loki_labels = sorted(set(str(label).lower() for label in (nested_get(loaded.get("context", {}), ["summary", "forbidden_loki_labels"]) or [])))
    topology_validation_add(
        checks,
        "fail" if forbidden_loki_labels else "ok",
        "no_unbounded_loki_labels",
        "Loki labels do not use trace/request/session/task IDs",
        {"forbidden": forbidden_loki_labels},
    )
    memory_space = nested_get(loaded.get("context", {}), ["memory_space"])
    memory_space = memory_space if isinstance(memory_space, dict) else {}
    gates = memory_space.get("freshness_gates") if isinstance(memory_space.get("freshness_gates"), list) else []
    gate_ids = {str(gate.get("gate_id")) for gate in gates if isinstance(gate, dict)}
    retrieval_packets = memory_space.get("retrieval_packets") if isinstance(memory_space.get("retrieval_packets"), list) else []
    spatial_overlays = memory_space.get("spatial_overlays") if isinstance(memory_space.get("spatial_overlays"), list) else []
    backends = memory_space.get("stack_semantic_backends") if isinstance(memory_space.get("stack_semantic_backends"), list) else []
    backend_ids = {str(item.get("id")) for item in backends if isinstance(item, dict)}
    memory_space_bad = []
    if memory_space.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_memory_space_overlay_v1":
        memory_space_bad.append("missing_memory_space_schema")
    if not SELF_AWARENESS_MEMORY_SPACE_REQUIRED_GATES.issubset(gate_ids):
        memory_space_bad.append("missing_required_freshness_gates")
    if not retrieval_packets:
        memory_space_bad.append("missing_retrieval_packets")
    if not spatial_overlays:
        memory_space_bad.append("missing_spatial_overlays")
    if not {"postgres", "neo4j", "rag-api", "embeddings"}.issubset(backend_ids):
        memory_space_bad.append("missing_semantic_backends")
    if nested_get(memory_space, ["policy", "bounded_retrieval"]) is not True:
        memory_space_bad.append("bounded_retrieval_policy_missing")
    if nested_get(memory_space, ["policy", "freshness_must_precede_reasoning"]) is not True:
        memory_space_bad.append("freshness_policy_missing")
    if nested_get(memory_space, ["policy", "raw_evidence_is_not_truth"]) is not True:
        memory_space_bad.append("truth_boundary_policy_missing")
    if nested_get(memory_space, ["policy", "host_layer_mutates_stack"]) is not False:
        memory_space_bad.append("host_layer_mutates_stack_policy")
    if nested_get(loaded.get("spatial_graph", {}), ["summary", "memory_space_nodes"]) in (None, 0):
        memory_space_bad.append("spatial_graph_missing_memory_space_nodes")
    topology_validation_add(
        checks,
        "fail" if memory_space_bad else "ok",
        "memory_space_depth",
        "context and spatial graph expose bounded RAG/memory/graph overlays with freshness gates and stack-owned semantic handoffs",
        {
            "bad": memory_space_bad,
            "summary": memory_space.get("summary"),
            "gate_ids": sorted(gate_ids),
            "backend_ids": sorted(backend_ids),
            "spatial_graph_summary": loaded.get("spatial_graph", {}).get("summary") if isinstance(loaded.get("spatial_graph"), dict) else None,
        },
    )
    working_stack_doc = loaded.get("working_stack", {})
    working_organs = working_stack_doc.get("organs") if isinstance(working_stack_doc.get("organs"), list) else []
    working_links = working_stack_doc.get("time_space_context_links") if isinstance(working_stack_doc.get("time_space_context_links"), list) else []
    working_events = [
        event for event in events
        if isinstance(event, dict) and event.get("source") == "working-stack"
    ]
    working_services = {str(item.get("service")) for item in working_organs if isinstance(item, dict) and item.get("service")}
    working_organ_by_service = {
        str(item.get("service")): item
        for item in working_organs
        if isinstance(item, dict) and item.get("service")
    }
    working_evidence_refs = [
        ref
        for organ in working_organs
        if isinstance(organ, dict)
        for ref in (organ.get("evidence_refs") if isinstance(organ.get("evidence_refs"), list) else [])
        if isinstance(ref, dict)
    ]
    working_stack_source_refs = [
        ref
        for organ in working_organs
        if isinstance(organ, dict)
        for ref in (organ.get("stack_source_refs") if isinstance(organ.get("stack_source_refs"), list) else [])
        if isinstance(ref, dict)
    ]
    protected_stack_roots = ("/srv/AbyssOS", "/srv/abyss-stack", str(ABYSS_STACK_USER_SOURCE_ROOT))
    working_bad: list[str] = []
    if working_stack_doc.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_working_stack_inventory_v1":
        working_bad.append("missing_working_stack_schema")
    if not working_organs:
        working_bad.append("missing_working_stack_organs")
    if safe_int(nested_get(working_stack_doc, ["summary", "runtime_services"]), 0) <= 0:
        working_bad.append("missing_runtime_services")
    if len(working_links) < len(working_organs):
        working_bad.append("missing_time_space_context_links")
    if not set(SELF_AWARENESS_WORKING_STACK_EXPECTED_LIVE_SERVICES).issubset(working_services):
        working_bad.append("missing_expected_live_service_organs")
    if len(working_events) < len(working_organs):
        working_bad.append("working_stack_events_not_projected")
    if safe_int(nested_get(loaded.get("context", {}), ["summary", "working_stack_contexts"]), 0) < len(working_organs):
        working_bad.append("working_stack_contexts_not_indexed")
    if nested_get(loaded.get("spatial_graph", {}), ["summary", "working_stack_expected_live_present"]) is not True:
        working_bad.append("working_stack_expected_live_not_in_spatial_graph")
    if nested_get(working_stack_doc, ["policy", "host_layer_mutates_stack"]) is not False:
        working_bad.append("working_stack_mutation_policy")
    if any(str(ref.get("path") or "").startswith(protected_stack_roots) for ref in working_evidence_refs):
        working_bad.append("stack_path_in_evidence_refs")
    if working_stack_source_refs and not all(ref.get("read_only") is True and ref.get("host_layer_mutates_stack") is False for ref in working_stack_source_refs):
        working_bad.append("stack_source_refs_not_read_only")
    docs_organ = working_organ_by_service.get("docs-api", {})
    docs_probes = {
        str(probe.get("probe")): probe
        for probe in (docs_organ.get("endpoint_probes") if isinstance(docs_organ.get("endpoint_probes"), list) else [])
        if isinstance(probe, dict)
    }
    if docs_organ and (
        docs_organ.get("machine_usage_status") != "active_machine_tool_signal"
        or docs_organ.get("deep_usage_proven") is not True
        or docs_probes.get("health", {}).get("ok") is not True
        or docs_probes.get("search:n8n-workflow", {}).get("ok") is not True
        or any(probe.get("policy", {}).get("response_body_stored") is not False for probe in docs_probes.values() if isinstance(probe.get("policy"), dict))
    ):
        working_bad.append("docs_api_tool_probe_depth")
    browser_organ = working_organ_by_service.get("aoa-browser", {})
    browser_probes = {
        str(probe.get("probe")): probe
        for probe in (browser_organ.get("endpoint_probes") if isinstance(browser_organ.get("endpoint_probes"), list) else [])
        if isinstance(probe, dict)
    }
    if browser_organ:
        browser_status = browser_organ.get("machine_usage_status")
        browser_launch_ok = browser_probes.get("playwright-chromium-launch", {}).get("ok") is True
        browser_probe_depth_ok = (
            browser_probes.get("health", {}).get("ok") is True
            and browser_probes.get("private-host-guard", {}).get("ok") is True
            and browser_probes.get("private-host-guard", {}).get("status_code") == 403
            and "playwright-chromium-launch" in browser_probes
            and (
                (browser_launch_ok and browser_status == "active_machine_tool_signal" and browser_organ.get("deep_usage_proven") is True)
                or (not browser_launch_ok and browser_status == "tool_runtime_degraded" and browser_organ.get("deep_usage_proven") is False and bool(browser_organ.get("usage_gap")))
            )
        )
        if not browser_probe_depth_ok:
            working_bad.append("aoa_browser_tool_probe_depth")
    for model_service in ("embeddings", "stt", "tts", "llm-registry"):
        model_organ = working_organ_by_service.get(model_service, {})
        if not model_organ:
            continue
        model_bridge = model_organ.get("model_bridge") if isinstance(model_organ.get("model_bridge"), dict) else {}
        model_evidence_refs = model_bridge.get("evidence_refs") if isinstance(model_bridge.get("evidence_refs"), list) else []
        model_source_refs = model_bridge.get("stack_source_model_refs") if isinstance(model_bridge.get("stack_source_model_refs"), list) else []
        if (
            model_organ.get("machine_usage_status") != "active_model_root_bridge"
            or model_organ.get("deep_usage_proven") is not True
            or model_bridge.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_working_stack_model_bridge_v1"
            or model_bridge.get("active") is not True
            or model_bridge.get("runtime_ready") is not True
            or not model_bridge.get("linked_stack_model_source_paths")
            or any(str(ref.get("path") or "").startswith(protected_stack_roots) for ref in model_evidence_refs if isinstance(ref, dict))
            or any(
                ref.get("read_only") is not True or ref.get("host_layer_mutates_stack") is not False
                for ref in model_source_refs
                if isinstance(ref, dict)
            )
        ):
            working_bad.append(f"{model_service}_model_bridge_depth")
    topology_validation_add(
        checks,
        "fail" if working_bad else "ok",
        "working_stack_body_depth",
        "working stack inventory exposes runtime organs, source roots, endpoints, model roots, and automatic time-space-context links without stack mutation",
        {
            "bad": working_bad,
            "summary": working_stack_doc.get("summary") if isinstance(working_stack_doc, dict) else None,
            "services": sorted(working_services),
            "working_events": len(working_events),
            "context_summary": loaded.get("context", {}).get("summary") if isinstance(loaded.get("context"), dict) else None,
            "spatial_summary": loaded.get("spatial_graph", {}).get("summary") if isinstance(loaded.get("spatial_graph"), dict) else None,
        },
    )
    completion_audit_doc = loaded.get("completion_audit", {})
    cycle_doc_for_entity_map = loaded.get("cycle", {}) if require_cycle else {}
    bridge_rows_for_entity_map = nested_get(cycle_doc_for_entity_map, ["bridge_proof", "rows"])
    expected_machine_bridges_for_entity_map = len(bridge_rows_for_entity_map) if isinstance(bridge_rows_for_entity_map, list) else None
    entity_event_document_map = completion_audit_doc.get("entity_event_document_map") if isinstance(completion_audit_doc.get("entity_event_document_map"), dict) else {}
    entity_event_document_bad = self_awareness_entity_event_document_map_issues(
        entity_event_document_map,
        expected_stack_organs=len(working_organs),
        expected_machine_bridges=expected_machine_bridges_for_entity_map,
    )
    if entity_event_document_bad:
        completion_audit_doc = self_awareness_completion_audit(write_latest=True)
        loaded["completion_audit"] = completion_audit_doc
        entity_event_document_map = completion_audit_doc.get("entity_event_document_map") if isinstance(completion_audit_doc.get("entity_event_document_map"), dict) else {}
        entity_event_document_bad = self_awareness_entity_event_document_map_issues(
            entity_event_document_map,
            expected_stack_organs=len(working_organs),
            expected_machine_bridges=expected_machine_bridges_for_entity_map,
        )
    topology_validation_add(
        checks,
        "fail" if entity_event_document_bad else "ok",
        "entity_event_document_surface_graph",
        "completion audit entity-event-document map covers completion actions, every working stack organ, every machine bridge proof row, source documents, route bindings, and non-mutating policy",
        {
            "bad": entity_event_document_bad,
            "summary": entity_event_document_map.get("summary") if isinstance(entity_event_document_map, dict) else None,
            "expected_stack_organs": len(working_organs),
            "expected_machine_bridges": expected_machine_bridges_for_entity_map,
            "top_entity": entity_event_document_map.get("top_entity") if isinstance(entity_event_document_map, dict) else None,
            "top_event": entity_event_document_map.get("top_event") if isinstance(entity_event_document_map, dict) else None,
        },
    )
    expected_completion_routes_for_packets = safe_int(nested_get(completion_audit_doc, ["completion_route_map", "summary", "routes"]), -1)
    expected_completion_routes_for_packets = expected_completion_routes_for_packets if expected_completion_routes_for_packets >= 0 else None
    expected_completion_actions_for_packets = safe_int(nested_get(completion_audit_doc, ["action_backlog", "summary", "actions"]), -1)
    expected_completion_actions_for_packets = expected_completion_actions_for_packets if expected_completion_actions_for_packets >= 0 else None
    completion_route_packets = completion_audit_doc.get("completion_route_packets") if isinstance(completion_audit_doc.get("completion_route_packets"), dict) else {}
    completion_route_packet_bad = self_awareness_completion_route_packet_issues(
        completion_route_packets,
        expected_routes=expected_completion_routes_for_packets,
        expected_actions=expected_completion_actions_for_packets,
    )
    if completion_route_packet_bad:
        completion_audit_doc = self_awareness_completion_audit(write_latest=True)
        loaded["completion_audit"] = completion_audit_doc
        expected_completion_routes_for_packets = safe_int(nested_get(completion_audit_doc, ["completion_route_map", "summary", "routes"]), -1)
        expected_completion_routes_for_packets = expected_completion_routes_for_packets if expected_completion_routes_for_packets >= 0 else None
        expected_completion_actions_for_packets = safe_int(nested_get(completion_audit_doc, ["action_backlog", "summary", "actions"]), -1)
        expected_completion_actions_for_packets = expected_completion_actions_for_packets if expected_completion_actions_for_packets >= 0 else None
        completion_route_packets = completion_audit_doc.get("completion_route_packets") if isinstance(completion_audit_doc.get("completion_route_packets"), dict) else {}
        completion_route_packet_bad = self_awareness_completion_route_packet_issues(
            completion_route_packets,
            expected_routes=expected_completion_routes_for_packets,
            expected_actions=expected_completion_actions_for_packets,
        )
    topology_validation_add(
        checks,
        "fail" if completion_route_packet_bad else "ok",
        "completion_route_packets",
        "completion audit exposes per-route automation packets that bind route, actions, entities, events, documents, evidence refs, verifier commands, and non-mutating policy",
        {
            "bad": completion_route_packet_bad,
            "summary": completion_route_packets.get("summary") if isinstance(completion_route_packets, dict) else None,
            "expected_routes": expected_completion_routes_for_packets,
            "expected_actions": expected_completion_actions_for_packets,
            "top_packet": completion_route_packets.get("top_packet") if isinstance(completion_route_packets, dict) else None,
        },
    )
    context_doc = loaded.get("context", {})
    context_packet = context_doc.get("context_packet") if isinstance(context_doc.get("context_packet"), dict) else {}
    if context_packet.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_bounded_context_packet_v1":
        context_doc = self_awareness_context(write_latest=True)
        loaded["context"] = context_doc
        context_packet = context_doc.get("context_packet") if isinstance(context_doc.get("context_packet"), dict) else {}
    context_sections = context_packet.get("sections") if isinstance(context_packet.get("sections"), dict) else {}
    context_stack_actions = nested_get(context_sections, ["stack_handoff", "ordered_actions"])
    context_stack_actions = context_stack_actions if isinstance(context_stack_actions, list) else []
    context_tools = context_packet.get("read_only_tools") if isinstance(context_packet.get("read_only_tools"), list) else []
    context_tool_kinds = {str(tool.get("kind")) for tool in context_tools if isinstance(tool, dict)}
    context_packet_bad: list[str] = []
    if context_packet.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_bounded_context_packet_v1":
        context_packet_bad.append("missing_context_packet_schema")
    if context_packet.get("complete") is not True:
        context_packet_bad.append("context_packet_incomplete")
    if not {"correlation_contexts", "host_body", "memory_space", "stack_handoff", "resident_worker", "governance_gates", "escalation_gate"}.issubset(set(context_sections)):
        context_packet_bad.append("missing_required_sections")
    if not {"promql_read", "logql_read", "memory_space", "spatial_graph", "requirements_handoff", "resident_worker", "governance_gates", "export_handoff"}.issubset(context_tool_kinds):
        context_packet_bad.append("missing_read_only_tools")
    if nested_get(context_packet, ["bounds", "raw_private_content"]) is not False:
        context_packet_bad.append("raw_private_content_bound")
    if nested_get(context_packet, ["bounds", "stores_raw_body"]) is not False:
        context_packet_bad.append("stores_raw_body_bound")
    if nested_get(context_packet, ["bounds", "stores_raw_context_values"]) is not False:
        context_packet_bad.append("stores_raw_context_values_bound")
    if nested_get(context_packet, ["bounds", "freshness_must_precede_reasoning"]) is not True:
        context_packet_bad.append("freshness_bound_missing")
    if nested_get(context_packet, ["bounds", "raw_evidence_is_not_truth"]) is not True:
        context_packet_bad.append("truth_boundary_bound_missing")
    if nested_get(context_packet, ["policy", "host_layer_mutates_stack"]) is not False:
        context_packet_bad.append("host_layer_mutates_stack_policy")
    if nested_get(context_packet, ["policy", "action_execution"]) is not False:
        context_packet_bad.append("action_execution_policy")
    if nested_get(context_packet, ["policy", "read_only_tools_only"]) is not True:
        context_packet_bad.append("read_only_tools_policy")
    if nested_get(context_sections, ["resident_worker", "complete"]) is not True:
        context_packet_bad.append("resident_worker_incomplete")
    if nested_get(context_sections, ["governance_gates", "complete"]) is not True:
        context_packet_bad.append("governance_gates_incomplete")
    if nested_get(context_sections, ["memory_space", "policy", "host_layer_mutates_stack"]) is not False:
        context_packet_bad.append("memory_space_policy")
    if nested_get(context_sections, ["host_body", "policy", "host_layer_mutates_stack"]) is not False:
        context_packet_bad.append("host_body_policy")
    if nested_get(context_sections, ["host_body", "bounds", "stores_raw_body"]) is not False or nested_get(context_sections, ["host_body", "bounds", "stores_raw_context_values"]) is not False:
        context_packet_bad.append("host_body_bounds")
    if safe_int(nested_get(context_sections, ["host_body", "scheduler", "unit_contexts"]), -1) != safe_int(nested_get(context_doc, ["summary", "scheduler_unit_contexts"]), -2):
        context_packet_bad.append("host_body_scheduler_count")
    if safe_int(nested_get(context_sections, ["host_body", "host_services", "unit_contexts"]), -1) != safe_int(nested_get(context_doc, ["summary", "host_service_unit_contexts"]), -2):
        context_packet_bad.append("host_body_service_count")
    if safe_int(nested_get(context_sections, ["host_body", "manual_collect", "contexts"]), -1) != safe_int(nested_get(context_doc, ["summary", "manual_collect_contexts"]), -2):
        context_packet_bad.append("host_body_manual_collect_count")
    if nested_get(context_sections, ["stack_handoff", "policy", "host_layer_mutates_stack"]) is not False:
        context_packet_bad.append("stack_handoff_policy")
    if safe_int(nested_get(context_sections, ["stack_handoff", "summary", "open_stack_requirements"]), -1) != safe_int(nested_get(loaded.get("requirement_probes", {}), ["summary", "open"]), -1):
        context_packet_bad.append("stack_handoff_open_count_mismatch")
    if context_stack_actions and safe_int(nested_get(context_packet, ["summary", "coverage_impact_entries"]), -1) != len(context_stack_actions):
        context_packet_bad.append("coverage_impact_count_mismatch")
    if context_stack_actions and not nested_get(context_packet, ["summary", "blocked_coverage_planes"]):
        context_packet_bad.append("blocked_coverage_planes_missing")
    for action in context_stack_actions:
        if not isinstance(action, dict):
            context_packet_bad.append("malformed_stack_handoff_action")
            continue
        if not self_awareness_stack_coverage_impact_complete(action.get("coverage_impact")):
            context_packet_bad.append(f"{action.get('requirement_id')}:coverage_impact")
    if not context_packet.get("evidence_refs"):
        context_packet_bad.append("missing_evidence_refs")
    topology_validation_add(
        checks,
        "fail" if context_packet_bad else "ok",
        "bounded_context_packet_depth",
        "context exposes bounded resident/operator packet with memory-space, stack handoff, resident worker, governance gates, read-only tools, and no stack mutation",
        {
            "bad": context_packet_bad,
            "summary": context_packet.get("summary"),
            "tool_kinds": sorted(context_tool_kinds),
            "section_order": context_packet.get("section_order"),
        },
    )
    dossier_doc = loaded.get("stack_closure_dossier", {})
    if dossier_doc.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_stack_closure_dossier_v1":
        dossier_doc = self_awareness_stack_closure_dossier(write_latest=True)
        loaded["stack_closure_dossier"] = dossier_doc
    dossier_entries = dossier_doc.get("entries") if isinstance(dossier_doc.get("entries"), list) else []
    dossier_open = dossier_doc.get("open_requirements") if isinstance(dossier_doc.get("open_requirements"), list) else []
    dossier_graph = dossier_doc.get("dependency_graph") if isinstance(dossier_doc.get("dependency_graph"), dict) else {}
    dossier_handoff = dossier_doc.get("stack_owner_handoff") if isinstance(dossier_doc.get("stack_owner_handoff"), dict) else {}
    dossier_artifact_refs = dossier_doc.get("artifact_refs") if isinstance(dossier_doc.get("artifact_refs"), dict) else {}
    dossier_compat_contracts = dossier_doc.get("compat_contracts") if isinstance(dossier_doc.get("compat_contracts"), dict) else {}
    working_stack_doc_for_dossier = loaded.get("working_stack", {})
    working_gap_services_for_dossier = {
        str(organ.get("service"))
        for organ in (working_stack_doc_for_dossier.get("organs") if isinstance(working_stack_doc_for_dossier.get("organs"), list) else [])
        if isinstance(organ, dict) and organ.get("service") and organ.get("usage_gap")
    }
    if safe_int(nested_get(dossier_doc, ["summary", "working_stack_activation_entries"]), -1) != len(working_gap_services_for_dossier):
        dossier_doc = self_awareness_stack_closure_dossier(
            write_latest=True,
            requirements_doc=loaded.get("requirements", {}),
            requirement_probes_doc=loaded.get("requirement_probes", {}),
            working_stack_doc=working_stack_doc_for_dossier,
        )
        loaded["stack_closure_dossier"] = dossier_doc
        dossier_entries = dossier_doc.get("entries") if isinstance(dossier_doc.get("entries"), list) else []
        dossier_open = dossier_doc.get("open_requirements") if isinstance(dossier_doc.get("open_requirements"), list) else []
        dossier_graph = dossier_doc.get("dependency_graph") if isinstance(dossier_doc.get("dependency_graph"), dict) else {}
        dossier_handoff = dossier_doc.get("stack_owner_handoff") if isinstance(dossier_doc.get("stack_owner_handoff"), dict) else {}
        dossier_artifact_refs = dossier_doc.get("artifact_refs") if isinstance(dossier_doc.get("artifact_refs"), dict) else {}
        dossier_compat_contracts = dossier_doc.get("compat_contracts") if isinstance(dossier_doc.get("compat_contracts"), dict) else {}
    dossier_activation = dossier_doc.get("working_stack_activation_dossier") if isinstance(dossier_doc.get("working_stack_activation_dossier"), dict) else {}
    dossier_activation_entries = dossier_activation.get("entries") if isinstance(dossier_activation.get("entries"), list) else []
    dossier_activation_handoff = dossier_activation.get("working_stack_activation_handoff") if isinstance(dossier_activation.get("working_stack_activation_handoff"), dict) else dossier_doc.get("working_stack_activation_handoff") if isinstance(dossier_doc.get("working_stack_activation_handoff"), dict) else {}
    dossier_activation_summary = dossier_activation.get("summary") if isinstance(dossier_activation.get("summary"), dict) else {}
    probe_summary = loaded.get("requirement_probes", {}).get("summary") if isinstance(loaded.get("requirement_probes", {}).get("summary"), dict) else {}
    dossier_bad: list[str] = []
    if dossier_doc.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_stack_closure_dossier_v1":
        dossier_bad.append("missing_dossier_schema")
    if nested_get(dossier_doc, ["policy", "host_layer_mutates_stack"]) is not False:
        dossier_bad.append("host_layer_mutates_stack_policy")
    if nested_get(dossier_doc, ["policy", "executes_commands"]) is not False:
        dossier_bad.append("executes_commands_policy")
    if nested_get(dossier_doc, ["policy", "action_execution"]) is not False:
        dossier_bad.append("action_execution_policy")
    if nested_get(dossier_doc, ["policy", "raw_secrets_included"]) is not False:
        dossier_bad.append("raw_secret_policy")
    if safe_int(nested_get(dossier_doc, ["summary", "probes"]), -1) != safe_int(probe_summary.get("probes"), -1):
        dossier_bad.append("probe_count_mismatch")
    if safe_int(nested_get(dossier_doc, ["summary", "open_stack_requirements"]), -1) != safe_int(probe_summary.get("open"), -1):
        dossier_bad.append("open_count_mismatch")
    if safe_int(nested_get(dossier_doc, ["summary", "missing_checks"]), -1) != safe_int(probe_summary.get("closure_readiness_missing_checks"), -1):
        dossier_bad.append("missing_check_count_mismatch")
    if safe_int(nested_get(dossier_doc, ["summary", "dependency_edges"]), -1) != safe_int(probe_summary.get("closure_readiness_dependency_edges"), -1):
        dossier_bad.append("dependency_edge_count_mismatch")
    if safe_int(nested_get(dossier_doc, ["summary", "dependency_edges"]), 0) > 0:
        if safe_int(nested_get(dossier_doc, ["summary", "reverse_dependency_edges"]), -1) != safe_int(nested_get(dossier_doc, ["summary", "dependency_edges"]), -1):
            dossier_bad.append("reverse_dependency_edge_count_mismatch")
        if not isinstance(dossier_graph.get("reverse_edges"), list) or len(dossier_graph.get("reverse_edges")) != safe_int(nested_get(dossier_doc, ["summary", "dependency_edges"]), 0):
            dossier_bad.append("reverse_dependency_graph_missing")
        if not isinstance(dossier_graph.get("unblocking_requirement_ids"), list) or not dossier_graph.get("unblocking_requirement_ids"):
            dossier_bad.append("unblocking_requirement_ids_missing")
    if safe_int(nested_get(dossier_doc, ["summary", "coverage_impact_entries"]), -1) != len(dossier_entries):
        dossier_bad.append("coverage_impact_count_mismatch")
    if safe_int(nested_get(dossier_doc, ["summary", "compat_contract_entries"]), -1) != len(dossier_entries):
        dossier_bad.append("compat_contract_count_mismatch")
    if len(dossier_compat_contracts) != len(dossier_entries):
        dossier_bad.append("compat_contracts_map_mismatch")
    if safe_int(nested_get(dossier_doc, ["summary", "closure_acceptance_packets"]), -1) != len(dossier_entries):
        dossier_bad.append("closure_acceptance_count_mismatch")
    if safe_int(nested_get(dossier_doc, ["summary", "closure_acceptance_packets_complete"]), -1) != len(dossier_entries):
        dossier_bad.append("closure_acceptance_complete_count_mismatch")
    if safe_int(nested_get(dossier_doc, ["summary", "stack_requirement_compat_requirements"]), -1) != len(dossier_entries):
        dossier_bad.append("stack_requirement_compat_requirement_count_mismatch")
    dossier_closure_acceptance_matrix = dossier_doc.get("closure_acceptance_matrix") if isinstance(dossier_doc.get("closure_acceptance_matrix"), dict) else {}
    if dossier_entries and dossier_closure_acceptance_matrix.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_stack_requirement_closure_acceptance_matrix_v1":
        dossier_bad.append("closure_acceptance_matrix_schema")
    if dossier_entries and dossier_closure_acceptance_matrix.get("ok") is not True:
        dossier_bad.append("closure_acceptance_matrix_ok")
    if dossier_activation.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_working_stack_activation_dossier_v1":
        dossier_bad.append("working_stack_activation_dossier_schema")
    if nested_get(dossier_activation, ["policy", "host_layer_mutates_stack"]) is not False or nested_get(dossier_activation, ["policy", "executes_commands"]) is not False:
        dossier_bad.append("working_stack_activation_dossier_policy")
    if safe_int(nested_get(dossier_doc, ["summary", "working_stack_activation_entries"]), -1) != len(dossier_activation_entries):
        dossier_bad.append("working_stack_activation_entry_count_mismatch")
    if safe_int(dossier_activation_summary.get("working_stack_usage_gaps"), -1) != len(working_gap_services_for_dossier):
        dossier_bad.append("working_stack_activation_usage_gap_count_mismatch")
    if safe_int(dossier_activation_summary.get("activation_entries_complete"), -1) != len(dossier_activation_entries):
        dossier_bad.append("working_stack_activation_complete_count_mismatch")
    if safe_int(dossier_activation_summary.get("synthetic_scenarios"), -1) != len(dossier_activation_entries):
        dossier_bad.append("working_stack_activation_scenario_count_mismatch")
    if safe_int(dossier_activation_summary.get("synthetic_scenarios_complete"), -1) != len(dossier_activation_entries):
        dossier_bad.append("working_stack_activation_scenario_complete_count_mismatch")
    if safe_int(dossier_activation_summary.get("closure_acceptance_packets"), -1) != len(dossier_activation_entries):
        dossier_bad.append("working_stack_activation_closure_acceptance_count_mismatch")
    if safe_int(dossier_activation_summary.get("closure_acceptance_packets_complete"), -1) != len(dossier_activation_entries):
        dossier_bad.append("working_stack_activation_closure_acceptance_complete_count_mismatch")
    if safe_int(dossier_activation_summary.get("activation_compat_requirements"), -1) != len(dossier_activation_entries):
        dossier_bad.append("working_stack_activation_compat_requirement_count_mismatch")
    closure_matrix = dossier_activation.get("closure_acceptance_matrix") if isinstance(dossier_activation.get("closure_acceptance_matrix"), dict) else {}
    if dossier_activation_entries and closure_matrix.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_working_stack_activation_closure_acceptance_matrix_v1":
        dossier_bad.append("working_stack_activation_closure_acceptance_matrix_schema")
    if dossier_activation_entries and closure_matrix.get("ok") is not True:
        dossier_bad.append("working_stack_activation_closure_acceptance_matrix_ok")
    if working_gap_services_for_dossier and not dossier_activation_entries:
        dossier_bad.append("working_stack_activation_entries_missing")
    activation_services = {str(entry.get("service")) for entry in dossier_activation_entries if isinstance(entry, dict) and entry.get("service")}
    if working_gap_services_for_dossier and activation_services != working_gap_services_for_dossier:
        dossier_bad.append("working_stack_activation_service_mismatch")
    if not isinstance(dossier_activation_handoff.get("activation_order"), list) or len(dossier_activation_handoff.get("activation_order") if isinstance(dossier_activation_handoff.get("activation_order"), list) else []) != len(dossier_activation_entries):
        dossier_bad.append("working_stack_activation_handoff_order")
    if nested_get(dossier_activation_handoff, ["policy", "host_layer_mutates_stack"]) is not False or nested_get(dossier_activation_handoff, ["policy", "abyss_machine_executes_stack_change"]) is not False:
        dossier_bad.append("working_stack_activation_handoff_policy")
    if not isinstance(nested_get(dossier_doc, ["summary", "blocked_coverage_planes"]), list) or not nested_get(dossier_doc, ["summary", "blocked_coverage_planes"]):
        dossier_bad.append("blocked_coverage_planes_missing")
    if not isinstance(dossier_graph.get("edges"), list) or not isinstance(dossier_graph.get("ordered_requirement_ids"), list):
        dossier_bad.append("dependency_graph_missing")
    if nested_get(dossier_graph, ["policy", "host_layer_mutates_stack"]) is not False or nested_get(dossier_graph, ["policy", "executes_commands"]) is not False:
        dossier_bad.append("dependency_graph_policy")
    if not isinstance(dossier_handoff.get("closure_order"), list) or not isinstance(dossier_handoff.get("verifier_chain"), list):
        dossier_bad.append("stack_owner_handoff_missing")
    if nested_get(dossier_handoff, ["policy", "host_layer_mutates_stack"]) is not False or nested_get(dossier_handoff, ["policy", "abyss_machine_executes_stack_change"]) is not False:
        dossier_bad.append("stack_owner_handoff_policy")
    if not {"requirements", "requirement_probes"}.issubset(set(dossier_artifact_refs)):
        dossier_bad.append("artifact_refs_missing")
    for entry in dossier_entries:
        if not isinstance(entry, dict):
            dossier_bad.append("malformed_entry")
            continue
        requirement_id = str(entry.get("requirement_id") or "unknown")
        if entry.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_stack_closure_dossier_entry_v1":
            dossier_bad.append(f"{requirement_id}:schema")
        if entry.get("owner") != "abyss-stack":
            dossier_bad.append(f"{requirement_id}:owner")
        if entry.get("complete") is not True:
            dossier_bad.append(f"{requirement_id}:incomplete")
        if not isinstance(entry.get("closure_readiness"), dict) or entry["closure_readiness"].get("schema") != f"{SCHEMA_PREFIX}_stack_handoff_closure_readiness_v1":
            dossier_bad.append(f"{requirement_id}:closure_readiness")
        if not entry.get("runbook_candidate") or not isinstance(entry.get("runbook_candidate"), dict):
            dossier_bad.append(f"{requirement_id}:runbook")
        if not entry.get("acceptance_verifiers") or not entry.get("verifier_commands"):
            dossier_bad.append(f"{requirement_id}:verifiers")
        if not entry.get("evidence_refs"):
            dossier_bad.append(f"{requirement_id}:evidence_refs")
        impact = entry.get("closure_impact") if isinstance(entry.get("closure_impact"), dict) else {}
        if impact.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_stack_closure_impact_v1":
            dossier_bad.append(f"{requirement_id}:closure_impact")
        if nested_get(impact, ["policy", "host_layer_mutates_stack"]) is not False or nested_get(impact, ["policy", "executes_commands"]) is not False:
            dossier_bad.append(f"{requirement_id}:closure_impact_policy")
        coverage_impact = entry.get("coverage_impact") if isinstance(entry.get("coverage_impact"), dict) else {}
        if coverage_impact.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_stack_coverage_impact_v1":
            dossier_bad.append(f"{requirement_id}:coverage_impact")
        if not coverage_impact.get("organ") or not coverage_impact.get("closure_value"):
            dossier_bad.append(f"{requirement_id}:coverage_impact_detail")
        if not isinstance(coverage_impact.get("coverage_planes"), list) or not coverage_impact.get("coverage_planes"):
            dossier_bad.append(f"{requirement_id}:coverage_planes")
        if not isinstance(coverage_impact.get("proof_commands"), list) or not coverage_impact.get("proof_commands"):
            dossier_bad.append(f"{requirement_id}:coverage_proof_commands")
        if nested_get(coverage_impact, ["policy", "host_layer_mutates_stack"]) is not False or nested_get(coverage_impact, ["policy", "executes_commands"]) is not False:
            dossier_bad.append(f"{requirement_id}:coverage_impact_policy")
        compat_contract = entry.get("compat_contract") if isinstance(entry.get("compat_contract"), dict) else {}
        if not self_awareness_stack_compat_contract_complete(compat_contract):
            dossier_bad.append(f"{requirement_id}:compat_contract")
        if dossier_compat_contracts.get(requirement_id) != compat_contract:
            dossier_bad.append(f"{requirement_id}:compat_contract_map")
        if nested_get(compat_contract, ["dependency_contract", "depends_on_requirement_ids"]) != entry.get("depends_on_requirement_ids"):
            dossier_bad.append(f"{requirement_id}:compat_depends_on")
        if nested_get(compat_contract, ["dependency_contract", "unblocks_requirement_ids"]) != entry.get("unblocks_requirement_ids"):
            dossier_bad.append(f"{requirement_id}:compat_unblocks")
        if not isinstance(entry.get("depends_on_requirement_ids"), list) or not isinstance(entry.get("unblocks_requirement_ids"), list):
            dossier_bad.append(f"{requirement_id}:impact_lists")
        closure_acceptance = entry.get("closure_acceptance") if isinstance(entry.get("closure_acceptance"), dict) else {}
        if not self_awareness_stack_requirement_closure_acceptance_complete(closure_acceptance):
            dossier_bad.append(f"{requirement_id}:closure_acceptance")
        if closure_acceptance and closure_acceptance.get("requirement_id") != requirement_id:
            dossier_bad.append(f"{requirement_id}:closure_acceptance_identity")
        if closure_acceptance and nested_get(closure_acceptance, ["stack_compat_requirement", "owner"]) != "abyss-stack":
            dossier_bad.append(f"{requirement_id}:closure_acceptance_owner")
        if closure_acceptance and nested_get(closure_acceptance, ["policy", "host_layer_mutates_stack"]) is not False:
            dossier_bad.append(f"{requirement_id}:closure_acceptance_policy")
        if nested_get(entry, ["safe_next_action", "host_layer_mutates_stack"]) is not False:
            dossier_bad.append(f"{requirement_id}:safe_next_policy")
        if nested_get(entry, ["policy", "host_layer_mutates_stack"]) is not False or nested_get(entry, ["policy", "executes_commands"]) is not False:
            dossier_bad.append(f"{requirement_id}:policy")
    for entry in dossier_activation_entries:
        if not isinstance(entry, dict):
            dossier_bad.append("malformed_working_stack_activation_entry")
            continue
        service = str(entry.get("service") or "unknown")
        if not self_awareness_working_stack_activation_entry_complete(entry):
            dossier_bad.append(f"{service}:working_stack_activation_incomplete")
        if working_gap_services_for_dossier and service not in working_gap_services_for_dossier:
            dossier_bad.append(f"{service}:working_stack_activation_unknown_service")
        if entry.get("owner") != "abyss-stack":
            dossier_bad.append(f"{service}:working_stack_activation_owner")
        if not entry.get("missing_checks") or not entry.get("closure_blocker_keys"):
            dossier_bad.append(f"{service}:working_stack_activation_blockers")
        if not isinstance(entry.get("activation_readiness"), dict) or entry["activation_readiness"].get("schema") != f"{SCHEMA_PREFIX}_self_awareness_working_stack_activation_readiness_v1":
            dossier_bad.append(f"{service}:working_stack_activation_readiness")
        if not isinstance(entry.get("runbook_candidate"), dict) or entry["runbook_candidate"].get("machine_executes_stack_change") is not False:
            dossier_bad.append(f"{service}:working_stack_activation_runbook")
        closure_acceptance = entry.get("closure_acceptance") if isinstance(entry.get("closure_acceptance"), dict) else {}
        if not self_awareness_working_stack_activation_closure_acceptance_complete(closure_acceptance):
            dossier_bad.append(f"{service}:working_stack_activation_closure_acceptance")
        if closure_acceptance and closure_acceptance.get("service") != service:
            dossier_bad.append(f"{service}:working_stack_activation_closure_acceptance_identity")
        if closure_acceptance and nested_get(closure_acceptance, ["stack_compat_requirement", "owner"]) != "abyss-stack":
            dossier_bad.append(f"{service}:working_stack_activation_closure_acceptance_owner")
        scenario = entry.get("synthetic_scenario") if isinstance(entry.get("synthetic_scenario"), dict) else {}
        if not self_awareness_working_stack_activation_synthetic_scenario_complete(scenario):
            dossier_bad.append(f"{service}:working_stack_activation_synthetic_scenario")
        if scenario.get("service") != service:
            dossier_bad.append(f"{service}:working_stack_activation_synthetic_scenario_identity")
        if nested_get(entry, ["safe_next_action", "requires_human_approval"]) is not True or nested_get(entry, ["safe_next_action", "host_layer_mutates_stack"]) is not False:
            dossier_bad.append(f"{service}:working_stack_activation_safe_next")
        if nested_get(entry, ["policy", "host_layer_mutates_stack"]) is not False or nested_get(entry, ["policy", "executes_commands"]) is not False:
            dossier_bad.append(f"{service}:working_stack_activation_policy")
    if safe_int(probe_summary.get("open"), 0) > 0 and not dossier_open:
        dossier_bad.append("missing_open_entries")
    topology_validation_add(
        checks,
        "fail" if dossier_bad else "ok",
        "stack_closure_dossier_depth",
        "stack closure dossier joins open requirements plus working-stack activation gaps with readiness, runbooks, dependency order, coverage impact, verifier chains, artifact refs, and non-mutating owner handoff",
        {
            "bad": dossier_bad,
            "summary": dossier_doc.get("summary"),
            "probe_summary": probe_summary,
            "ordered_requirement_ids": dossier_graph.get("ordered_requirement_ids"),
            "compat_contracts": sorted(dossier_compat_contracts),
            "working_stack_gap_services": sorted(working_gap_services_for_dossier),
            "working_stack_activation_services": sorted(activation_services),
            "working_stack_activation_summary": dossier_activation_summary,
        },
    )
    timeline_doc = loaded.get("timeline", {})
    spatial_doc = loaded.get("spatial_graph", {})
    time_space_overlay = timeline_doc.get("stack_handoff_time_space_overlay") if isinstance(timeline_doc.get("stack_handoff_time_space_overlay"), dict) else {}
    if time_space_overlay.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_stack_handoff_time_space_overlay_v1":
        timeline_doc = self_awareness_timeline(write_latest=True)
        loaded["timeline"] = timeline_doc
        loaded["requirement_probes"] = load_latest_json(SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_requirement_probes_v1")
        if loaded["requirement_probes"].get("schema") != f"{SCHEMA_PREFIX}_self_awareness_requirement_probes_v1":
            loaded["requirement_probes"] = self_awareness_requirement_probes(write_latest=True)
        spatial_doc = self_awareness_spatial_graph(write_latest=True)
        loaded["spatial_graph"] = spatial_doc
        time_space_overlay = timeline_doc.get("stack_handoff_time_space_overlay") if isinstance(timeline_doc.get("stack_handoff_time_space_overlay"), dict) else {}
    spatial_time_space_overlay = spatial_doc.get("stack_handoff_time_space_overlay") if isinstance(spatial_doc.get("stack_handoff_time_space_overlay"), dict) else {}
    markers = time_space_overlay.get("timeline_markers") if isinstance(time_space_overlay.get("timeline_markers"), list) else []
    overlay_nodes = time_space_overlay.get("spatial_nodes") if isinstance(time_space_overlay.get("spatial_nodes"), list) else []
    overlay_edges = time_space_overlay.get("spatial_edges") if isinstance(time_space_overlay.get("spatial_edges"), list) else []
    graph_nodes = spatial_doc.get("nodes") if isinstance(spatial_doc.get("nodes"), list) else []
    graph_edges = spatial_doc.get("edges") if isinstance(spatial_doc.get("edges"), list) else []
    graph_stack_requirement_ids = {
        str(item.get("requirement_id")) for item in graph_nodes
        if isinstance(item, dict) and item.get("kind") == "stack_requirement" and item.get("requirement_id")
    }
    marker_requirement_ids = {str(item.get("requirement_id")) for item in markers if isinstance(item, dict) and item.get("requirement_id")}
    probe_open = safe_int(nested_get(loaded.get("requirement_probes", {}), ["summary", "open"]), 0)
    time_space_bad: list[str] = []
    if time_space_overlay.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_stack_handoff_time_space_overlay_v1":
        time_space_bad.append("missing_timeline_overlay_schema")
    if spatial_time_space_overlay.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_stack_handoff_time_space_overlay_v1":
        time_space_bad.append("missing_spatial_overlay_schema")
    if nested_get(time_space_overlay, ["policy", "host_layer_mutates_stack"]) is not False:
        time_space_bad.append("timeline_overlay_mutation_policy")
    if nested_get(time_space_overlay, ["policy", "executes_commands"]) is not False:
        time_space_bad.append("timeline_overlay_exec_policy")
    if safe_int(nested_get(time_space_overlay, ["summary", "open_stack_requirements"]), -1) != probe_open:
        time_space_bad.append("overlay_probe_open_count_mismatch")
    if safe_int(nested_get(time_space_overlay, ["summary", "timeline_markers"]), -1) != len(markers):
        time_space_bad.append("marker_count_mismatch")
    if safe_int(nested_get(timeline_doc, ["summary", "stack_handoff_markers"]), -1) != len(markers):
        time_space_bad.append("timeline_summary_marker_mismatch")
    if marker_requirement_ids != graph_stack_requirement_ids:
        time_space_bad.append("timeline_spatial_requirement_mismatch")
    if probe_open > 0 and not markers:
        time_space_bad.append("missing_markers_for_open_requirements")
    if probe_open > 0 and safe_int(nested_get(spatial_doc, ["summary", "stack_handoff_nodes"]), 0) <= 0:
        time_space_bad.append("spatial_missing_stack_handoff_nodes")
    if probe_open > 0 and safe_int(nested_get(spatial_doc, ["summary", "stack_handoff_edges"]), 0) <= 0:
        time_space_bad.append("spatial_missing_stack_handoff_edges")
    if not overlay_nodes:
        time_space_bad.append("missing_overlay_nodes")
    if probe_open > 0 and not overlay_edges:
        time_space_bad.append("missing_overlay_edges")
    for marker in markers:
        if not isinstance(marker, dict):
            time_space_bad.append("malformed_marker")
            continue
        marker_id = str(marker.get("id") or marker.get("requirement_id") or "unknown")
        if marker.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_stack_handoff_timeline_marker_v1":
            time_space_bad.append(f"{marker_id}:schema")
        if not nested_get(marker, ["time", "bucket"]) or nested_get(marker, ["time", "freshness_must_precede_reasoning"]) is not True:
            time_space_bad.append(f"{marker_id}:time")
        if nested_get(marker, ["space", "owner_surface"]) != "abyss-stack" or not nested_get(marker, ["space", "service_nodes"]):
            time_space_bad.append(f"{marker_id}:space")
        if not marker.get("closure_blockers") or not marker.get("closure_blocker_keys"):
            time_space_bad.append(f"{marker_id}:closure")
        if not marker.get("runbook_candidate_id") or not isinstance(marker.get("runbook_candidate"), dict):
            time_space_bad.append(f"{marker_id}:runbook")
        if not marker.get("verifier_commands") or not marker.get("acceptance_verifiers"):
            time_space_bad.append(f"{marker_id}:verifiers")
        if nested_get(marker, ["safe_next_action", "requires_human_approval"]) is not True or nested_get(marker, ["safe_next_action", "host_layer_mutates_stack"]) is not False:
            time_space_bad.append(f"{marker_id}:safe_next")
        if nested_get(marker, ["policy", "host_layer_mutates_stack"]) is not False or nested_get(marker, ["policy", "executes_commands"]) is not False:
            time_space_bad.append(f"{marker_id}:policy")
    topology_validation_add(
        checks,
        "fail" if time_space_bad else "ok",
        "stack_handoff_time_space_overlay",
        "timeline and spatial graph expose open stack handoff blockers as evidence-cited non-mutating time/space markers, nodes, and edges",
        {
            "bad": time_space_bad,
            "summary": time_space_overlay.get("summary"),
            "probe_open": probe_open,
            "marker_requirement_ids": sorted(marker_requirement_ids),
            "graph_stack_requirement_ids": sorted(graph_stack_requirement_ids),
            "spatial_summary": spatial_doc.get("summary") if isinstance(spatial_doc, dict) else None,
        },
    )
    episodes_doc = loaded.get("episodes", {})
    episode_rows = episodes_doc.get("episodes") if isinstance(episodes_doc.get("episodes"), list) else []
    stack_handoff_episode_ids = episodes_doc.get("stack_handoff_episode_ids") if isinstance(episodes_doc.get("stack_handoff_episode_ids"), list) else []
    stack_handoff_episodes = [
        episode for episode in episode_rows
        if isinstance(episode, dict) and episode.get("episode_kind") == "stack_handoff_blocker"
    ]
    if safe_int(nested_get(episodes_doc, ["summary", "stack_handoff_episodes"]), -1) != probe_open or (probe_open > 0 and not stack_handoff_episodes):
        episodes_doc = self_awareness_episodes(write_latest=True)
        loaded["episodes"] = episodes_doc
        episode_rows = episodes_doc.get("episodes") if isinstance(episodes_doc.get("episodes"), list) else []
        stack_handoff_episode_ids = episodes_doc.get("stack_handoff_episode_ids") if isinstance(episodes_doc.get("stack_handoff_episode_ids"), list) else []
        stack_handoff_episodes = [
            episode for episode in episode_rows
            if isinstance(episode, dict) and episode.get("episode_kind") == "stack_handoff_blocker"
        ]
    stack_episode_requirement_ids = {
        str(episode.get("requirement_id")) for episode in stack_handoff_episodes
        if isinstance(episode, dict) and episode.get("requirement_id")
    }
    marker_id_by_requirement = {
        str(marker.get("requirement_id")): str(marker.get("id"))
        for marker in markers
        if isinstance(marker, dict) and marker.get("requirement_id") and marker.get("id")
    }
    stack_episode_bad: list[str] = []
    if safe_int(nested_get(episodes_doc, ["summary", "stack_handoff_episodes"]), -1) != len(stack_handoff_episodes):
        stack_episode_bad.append("summary_episode_count_mismatch")
    if len(stack_handoff_episode_ids) != len(stack_handoff_episodes):
        stack_episode_bad.append("top_level_episode_id_count_mismatch")
    if safe_int(nested_get(episodes_doc, ["summary", "open_stack_requirements"]), -1) != probe_open:
        stack_episode_bad.append("open_requirement_count_mismatch")
    if probe_open > 0 and stack_episode_requirement_ids != marker_requirement_ids:
        stack_episode_bad.append("episode_marker_requirement_mismatch")
    if probe_open > 0 and len(set(str(item) for item in stack_handoff_episode_ids)) != len(stack_handoff_episode_ids):
        stack_episode_bad.append("duplicate_stack_handoff_episode_ids")
    for episode in stack_handoff_episodes:
        if not isinstance(episode, dict):
            stack_episode_bad.append("malformed_stack_episode")
            continue
        episode_id = str(episode.get("episode_id") or "unknown")
        requirement_id = str(episode.get("requirement_id") or "")
        affected_nodes = episode.get("affected_spatial_nodes") if isinstance(episode.get("affected_spatial_nodes"), list) else []
        primary_signals = {str(item) for item in (episode.get("primary_signals") if isinstance(episode.get("primary_signals"), list) else [])}
        handoff = episode.get("stack_handoff") if isinstance(episode.get("stack_handoff"), dict) else {}
        policy = episode.get("policy") if isinstance(episode.get("policy"), dict) else {}
        evidence_refs = episode.get("evidence_refs") if isinstance(episode.get("evidence_refs"), list) else []
        if episode.get("schema") != f"{SCHEMA_PREFIX}_causal_episode_v1":
            stack_episode_bad.append(f"{episode_id}:schema")
        if episode.get("truth_level") != "handoff_candidate":
            stack_episode_bad.append(f"{episode_id}:truth_level")
        if episode.get("owner_route") != "abyss-stack":
            stack_episode_bad.append(f"{episode_id}:owner_route")
        if requirement_id not in marker_requirement_ids:
            stack_episode_bad.append(f"{episode_id}:requirement_id")
        if marker_id_by_requirement.get(requirement_id) and episode.get("stack_handoff_marker_id") != marker_id_by_requirement.get(requirement_id):
            stack_episode_bad.append(f"{episode_id}:marker_id")
        if not any(str(node).startswith("stack_requirement:") for node in affected_nodes):
            stack_episode_bad.append(f"{episode_id}:missing_requirement_node")
        if not any(str(node).startswith("stack_handoff_action:") for node in affected_nodes):
            stack_episode_bad.append(f"{episode_id}:missing_action_node")
        if not {"stack_handoff", "requirement_probe", "spatial_graph"}.issubset(primary_signals):
            stack_episode_bad.append(f"{episode_id}:signals")
        if not isinstance(episode.get("event_ids"), list):
            stack_episode_bad.append(f"{episode_id}:event_ids")
        if not evidence_refs:
            stack_episode_bad.append(f"{episode_id}:evidence_refs")
        if not handoff.get("closure_blocker_keys"):
            stack_episode_bad.append(f"{episode_id}:closure_blockers")
        if not handoff.get("runbook_candidate_id"):
            stack_episode_bad.append(f"{episode_id}:runbook")
        if not handoff.get("verifier_commands"):
            stack_episode_bad.append(f"{episode_id}:verifiers")
        if not isinstance(handoff.get("safe_next_action"), dict):
            stack_episode_bad.append(f"{episode_id}:safe_next")
        if policy.get("root_cause_claim") is not False:
            stack_episode_bad.append(f"{episode_id}:root_cause_policy")
        if policy.get("handoff_only") is not True:
            stack_episode_bad.append(f"{episode_id}:handoff_policy")
        if policy.get("host_layer_mutates_stack") is not False:
            stack_episode_bad.append(f"{episode_id}:mutation_policy")
        if policy.get("executes_commands") is not False:
            stack_episode_bad.append(f"{episode_id}:exec_policy")
        if policy.get("automatic_remediation") is not False:
            stack_episode_bad.append(f"{episode_id}:automatic_policy")
    topology_validation_add(
        checks,
        "fail" if stack_episode_bad else "ok",
        "stack_handoff_causal_episodes",
        "open stack handoff blockers become conservative causal episodes with spatial lineage, verifier/runbook evidence, and no stack mutation policy",
        {
            "bad": stack_episode_bad,
            "probe_open": probe_open,
            "stack_handoff_episodes": len(stack_handoff_episodes),
            "stack_handoff_episode_ids": stack_handoff_episode_ids,
            "episode_requirement_ids": sorted(stack_episode_requirement_ids),
            "marker_requirement_ids": sorted(marker_requirement_ids),
            "summary": episodes_doc.get("summary") if isinstance(episodes_doc, dict) else None,
        },
    )
    working_stack_doc_for_gap = loaded.get("working_stack", {})
    protected_stack_roots_for_gap = ("/srv/AbyssOS", "/srv/abyss-stack", str(ABYSS_STACK_USER_SOURCE_ROOT))
    working_gap_services = {
        str(organ.get("service"))
        for organ in (working_stack_doc_for_gap.get("organs") if isinstance(working_stack_doc_for_gap.get("organs"), list) else [])
        if isinstance(organ, dict) and organ.get("service") and organ.get("usage_gap")
    }
    working_gap_episodes = [
        episode for episode in episode_rows
        if isinstance(episode, dict) and episode.get("episode_kind") == "working_stack_usage_gap"
    ]
    working_gap_episode_ids = episodes_doc.get("working_stack_gap_episode_ids") if isinstance(episodes_doc.get("working_stack_gap_episode_ids"), list) else []
    if working_gap_services and (
        safe_int(nested_get(episodes_doc, ["summary", "working_stack_gap_episodes"]), -1) != len(working_gap_services)
        or len(working_gap_episodes) != len(working_gap_services)
        or len(working_gap_episode_ids) != len(working_gap_episodes)
    ):
        episodes_doc = self_awareness_episodes(write_latest=True)
        loaded["episodes"] = episodes_doc
        episode_rows = episodes_doc.get("episodes") if isinstance(episodes_doc.get("episodes"), list) else []
        working_gap_episodes = [
            episode for episode in episode_rows
            if isinstance(episode, dict) and episode.get("episode_kind") == "working_stack_usage_gap"
        ]
        working_gap_episode_ids = episodes_doc.get("working_stack_gap_episode_ids") if isinstance(episodes_doc.get("working_stack_gap_episode_ids"), list) else []
    working_gap_bad: list[str] = []
    working_gap_episode_services = {
        str(episode.get("service"))
        for episode in working_gap_episodes
        if isinstance(episode, dict) and episode.get("service")
    }
    if safe_int(nested_get(episodes_doc, ["summary", "working_stack_gap_episodes"]), -1) != len(working_gap_episodes):
        working_gap_bad.append("summary_episode_count_mismatch")
    if len(working_gap_episode_ids) != len(working_gap_episodes):
        working_gap_bad.append("top_level_episode_id_count_mismatch")
    if working_gap_services and working_gap_episode_services != working_gap_services:
        working_gap_bad.append("episode_service_mismatch")
    if len(set(str(item) for item in working_gap_episode_ids)) != len(working_gap_episode_ids):
        working_gap_bad.append("duplicate_working_gap_episode_ids")
    for episode in working_gap_episodes:
        if not isinstance(episode, dict):
            working_gap_bad.append("malformed_working_gap_episode")
            continue
        episode_id = str(episode.get("episode_id") or "unknown")
        service = str(episode.get("service") or "")
        affected_nodes = episode.get("affected_spatial_nodes") if isinstance(episode.get("affected_spatial_nodes"), list) else []
        primary_signals = {str(item) for item in (episode.get("primary_signals") if isinstance(episode.get("primary_signals"), list) else [])}
        working_gap = episode.get("working_stack_gap") if isinstance(episode.get("working_stack_gap"), dict) else {}
        policy = episode.get("policy") if isinstance(episode.get("policy"), dict) else {}
        evidence_refs = episode.get("evidence_refs") if isinstance(episode.get("evidence_refs"), list) else []
        safe_next = working_gap.get("safe_next_action") if isinstance(working_gap.get("safe_next_action"), dict) else {}
        if episode.get("schema") != f"{SCHEMA_PREFIX}_causal_episode_v1":
            working_gap_bad.append(f"{episode_id}:schema")
        if episode.get("truth_level") != "working_stack_gap_candidate":
            working_gap_bad.append(f"{episode_id}:truth_level")
        if episode.get("owner_route") != "abyss-stack":
            working_gap_bad.append(f"{episode_id}:owner_route")
        if not service or service not in working_gap_services:
            working_gap_bad.append(f"{episode_id}:service")
        if f"service:{service}" not in affected_nodes:
            working_gap_bad.append(f"{episode_id}:missing_service_node")
        if not any(str(node).startswith("usage_gap:") for node in affected_nodes):
            working_gap_bad.append(f"{episode_id}:missing_usage_gap_node")
        if not {"working_stack", "spatial_graph", "usage_gap"}.issubset(primary_signals):
            working_gap_bad.append(f"{episode_id}:signals")
        if not isinstance(episode.get("event_ids"), list):
            working_gap_bad.append(f"{episode_id}:event_ids")
        if working_gap.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_working_stack_usage_gap_v1":
            working_gap_bad.append(f"{episode_id}:gap_schema")
        if working_gap.get("service") != service:
            working_gap_bad.append(f"{episode_id}:gap_service")
        if not working_gap.get("working_stack_link_id"):
            working_gap_bad.append(f"{episode_id}:working_stack_link")
        if not working_gap.get("closure_blocker_keys"):
            working_gap_bad.append(f"{episode_id}:closure_blockers")
        if not working_gap.get("verifier_commands"):
            working_gap_bad.append(f"{episode_id}:verifiers")
        if safe_next.get("requires_human_approval") is not True or safe_next.get("host_layer_mutates_stack") is not False:
            working_gap_bad.append(f"{episode_id}:safe_next")
        if not evidence_refs:
            working_gap_bad.append(f"{episode_id}:evidence_refs")
        if any(str(ref.get("path") or "").startswith(protected_stack_roots_for_gap) for ref in evidence_refs if isinstance(ref, dict)):
            working_gap_bad.append(f"{episode_id}:stack_path_in_evidence_refs")
        if policy.get("root_cause_claim") is not False:
            working_gap_bad.append(f"{episode_id}:root_cause_policy")
        if policy.get("handoff_only") is not True:
            working_gap_bad.append(f"{episode_id}:handoff_policy")
        if policy.get("host_layer_mutates_stack") is not False:
            working_gap_bad.append(f"{episode_id}:mutation_policy")
        if policy.get("executes_commands") is not False:
            working_gap_bad.append(f"{episode_id}:exec_policy")
        if policy.get("automatic_remediation") is not False:
            working_gap_bad.append(f"{episode_id}:automatic_policy")
    topology_validation_add(
        checks,
        "fail" if working_gap_bad else "ok",
        "working_stack_usage_gap_causal_episodes",
        "working-stack usage gaps become conservative causal episodes with service/link/usage-gap spatial lineage, verifier evidence, and no stack mutation policy",
        {
            "bad": working_gap_bad,
            "working_gap_services": sorted(working_gap_services),
            "episode_services": sorted(working_gap_episode_services),
            "working_stack_gap_episode_ids": working_gap_episode_ids,
            "summary": episodes_doc.get("summary") if isinstance(episodes_doc, dict) else None,
        },
    )
    host_service_events_for_episodes = [
        event for event in events
        if isinstance(event, dict) and event.get("source") == "host-service"
    ]
    host_service_event_units = sorted({
        str(nested_get(event, ["context", "host_service_unit"]) or nested_get(event, ["resource", "service"]))
        for event in host_service_events_for_episodes
        if nested_get(event, ["context", "host_service_unit"]) or nested_get(event, ["resource", "service"])
    })
    host_service_episodes = [
        episode for episode in episode_rows
        if isinstance(episode, dict) and episode.get("episode_kind") == "host_service_state"
    ]
    host_service_episode_ids = episodes_doc.get("host_service_episode_ids") if isinstance(episodes_doc.get("host_service_episode_ids"), list) else []
    if host_service_event_units and (
        safe_int(nested_get(episodes_doc, ["summary", "host_service_episodes"]), -1) != len(host_service_episodes)
        or not host_service_episodes
        or len(host_service_episode_ids) != len(host_service_episodes)
    ):
        episodes_doc = self_awareness_episodes(write_latest=True)
        loaded["episodes"] = episodes_doc
        episode_rows = episodes_doc.get("episodes") if isinstance(episodes_doc.get("episodes"), list) else []
        host_service_episodes = [
            episode for episode in episode_rows
            if isinstance(episode, dict) and episode.get("episode_kind") == "host_service_state"
        ]
        host_service_episode_ids = episodes_doc.get("host_service_episode_ids") if isinstance(episodes_doc.get("host_service_episode_ids"), list) else []
    host_service_bad: list[str] = []
    host_service_episode_units = sorted({
        str(unit)
        for episode in host_service_episodes
        for unit in (nested_get(episode, ["host_service", "units"]) if isinstance(nested_get(episode, ["host_service", "units"]), list) else [])
        if unit
    })
    if host_service_event_units and not host_service_episodes:
        host_service_bad.append("missing_host_service_episodes")
    if safe_int(nested_get(episodes_doc, ["summary", "host_service_episodes"]), -1) != len(host_service_episodes):
        host_service_bad.append("summary_episode_count_mismatch")
    if len(host_service_episode_ids) != len(host_service_episodes):
        host_service_bad.append("top_level_episode_id_count_mismatch")
    if host_service_event_units and sorted(host_service_episode_units) != host_service_event_units:
        host_service_bad.append("episode_unit_mismatch")
    if len(set(str(item) for item in host_service_episode_ids)) != len(host_service_episode_ids):
        host_service_bad.append("duplicate_host_service_episode_ids")
    for episode in host_service_episodes:
        if not isinstance(episode, dict):
            host_service_bad.append("malformed_host_service_episode")
            continue
        episode_id = str(episode.get("episode_id") or "unknown")
        affected_nodes = episode.get("affected_spatial_nodes") if isinstance(episode.get("affected_spatial_nodes"), list) else []
        affected_services = episode.get("affected_services") if isinstance(episode.get("affected_services"), list) else []
        context_keys = episode.get("context_keys") if isinstance(episode.get("context_keys"), list) else []
        host_service = episode.get("host_service") if isinstance(episode.get("host_service"), dict) else {}
        host_policy = host_service.get("policy") if isinstance(host_service.get("policy"), dict) else {}
        evidence_refs = episode.get("evidence_refs") if isinstance(episode.get("evidence_refs"), list) else []
        if episode.get("schema") != f"{SCHEMA_PREFIX}_causal_episode_v1":
            host_service_bad.append(f"{episode_id}:schema")
        if safe_int(nested_get(episode, ["source_counts", "host-service"]), 0) <= 0:
            host_service_bad.append(f"{episode_id}:source_count")
        if not affected_services:
            host_service_bad.append(f"{episode_id}:affected_services")
        if not any(str(node).startswith("service:") for node in affected_nodes):
            host_service_bad.append(f"{episode_id}:service_node")
        if not any(str(key).startswith("host_service_unit:") for key in context_keys):
            host_service_bad.append(f"{episode_id}:context_keys")
        if not host_service.get("units") or not host_service.get("categories"):
            host_service_bad.append(f"{episode_id}:host_service_block")
        if not evidence_refs:
            host_service_bad.append(f"{episode_id}:evidence_refs")
        if host_policy.get("host_layer_mutates_stack") is not False:
            host_service_bad.append(f"{episode_id}:mutation_policy")
        if host_policy.get("executes_commands") is not False:
            host_service_bad.append(f"{episode_id}:exec_policy")
        if host_policy.get("automatic_remediation") is not False:
            host_service_bad.append(f"{episode_id}:automatic_policy")
    topology_validation_add(
        checks,
        "fail" if host_service_bad else "ok",
        "host_service_causal_episodes",
        "active host-service events become bounded causal body episodes with unit/category context, spatial service nodes, evidence refs, and no mutation policy",
        {
            "bad": host_service_bad,
            "host_service_event_units": host_service_event_units,
            "host_service_episode_units": host_service_episode_units,
            "host_service_episode_ids": host_service_episode_ids,
            "summary": episodes_doc.get("summary") if isinstance(episodes_doc, dict) else None,
        },
    )
    protected_write_claims: list[dict[str, Any]] = []
    for event in events:
        resource = event.get("resource") if isinstance(event, dict) and isinstance(event.get("resource"), dict) else {}
        if resource.get("write") is True:
            path_text = str(resource.get("path") or (event.get("space") or {}).get("path") or "")
            if path_text.startswith("/") and storage_path_protection(Path(path_text)).get("decision") == "deny":
                protected_write_claims.append({"event_id": event.get("event_id"), "path": path_text})
    topology_validation_add(
        checks,
        "fail" if protected_write_claims else "ok",
        "no_protected_root_writes",
        "self-awareness events and routes have no protected-root write claims",
        {"claims": protected_write_claims},
    )
    combined_preview = json.dumps({key: loaded.get(key) for key in ("events", "collect", "brief", "alerts", "capabilities", "requirements", "requirement_probes", "trace_context", "query", "correlation", "investigate", "export")}, sort_keys=True, default=str)[:200000]
    topology_validation_add(
        checks,
        "fail" if SELF_AWARENESS_SECRET_RE.search(combined_preview) else "ok",
        "no_secret_leakage",
        "self-awareness latest previews do not contain obvious secrets",
    )
    probe = loaded.get("probe", {})
    chain = probe.get("chain") if isinstance(probe.get("chain"), dict) else {}
    required_probe_chain_keys = (
        "request", "capability_map", "metric", "log", "trace_context", "trace_context_fallback", "context", "observation_events",
        "requirement_probes", "failure_matrix", "query", "correlation", "timeline", "spatial_graph", "causal_episode", "alert",
        "warm_e2b", "resident_cognitive_replay", "resident_cognitive_export", "rag_memory", "nervous_freshness", "langgraph_investigation", "replay",
        "reaction_candidate", "governed_response", "body_trace", "entity_event_document", "semantic_brief", "export",
    )
    probe_lineage = probe.get("lineage") if isinstance(probe.get("lineage"), dict) else {}
    if allow_probe_refresh and (
        any(key not in chain for key in required_probe_chain_keys)
        or not self_awareness_top_level_lineage_complete(probe_lineage, require_cycle=False)
    ):
        probe = self_awareness_probe(write_latest=True)
        loaded["probe"] = probe
        chain = probe.get("chain") if isinstance(probe.get("chain"), dict) else {}
        probe_lineage = probe.get("lineage") if isinstance(probe.get("lineage"), dict) else {}
    missing_chain = [
        key for key in required_probe_chain_keys
        if not chain.get(key)
    ]
    topology_validation_add(
        checks,
        "fail" if missing_chain else "ok",
        "synthetic_e2e_probe",
        "synthetic probe proves full request-to-brief chain",
        {"missing_chain": missing_chain, "run_id": probe.get("run_id"), "chain": chain},
    )
    topology_validation_add(
        checks,
        "fail" if not self_awareness_top_level_lineage_complete(probe_lineage, require_cycle=False) else "ok",
        "synthetic_e2e_probe_lineage",
        "synthetic probe exposes top-level run/thread/trace/artifact/replay/response/export lineage without stack mutation",
        {
            "summary": probe_lineage.get("summary") if isinstance(probe_lineage, dict) else None,
            "run_id": probe.get("run_id"),
            "thread": probe_lineage.get("thread") if isinstance(probe_lineage, dict) else None,
            "trace": probe_lineage.get("trace") if isinstance(probe_lineage, dict) else None,
            "policy": probe_lineage.get("policy") if isinstance(probe_lineage, dict) else None,
        },
    )
    if require_cycle:
        cycle = loaded.get("cycle", {})
        cycle_chain = cycle.get("cycle_chain") if isinstance(cycle.get("cycle_chain"), dict) else {}
        cycle_chain, replay_doc, export_doc = self_awareness_resident_cognitive_cycle_chain_overlay(
            cycle_chain,
            replay_doc=loaded.get("replay") if isinstance(loaded.get("replay"), dict) else None,
            export_doc=loaded.get("export") if isinstance(loaded.get("export"), dict) else None,
            write_latest=True,
        )
        loaded["replay"] = replay_doc
        loaded["export"] = export_doc
        required_cycle_chain_keys = set(self_awareness_cycle_from_zero_chain_sources())
        cycle_missing_chain = sorted(key for key in required_cycle_chain_keys if not cycle_chain.get(key))
        cycle_missing_chain.extend(sorted(str(key) for key, value in cycle_chain.items() if not value and str(key) not in set(cycle_missing_chain)))
        cycle_summary = dict(cycle.get("summary")) if isinstance(cycle.get("summary"), dict) else {}
        cycle_summary["chain_passed_overlay"] = sum(1 for key in required_cycle_chain_keys if cycle_chain.get(key))
        cycle_summary["chain_total_overlay"] = len(required_cycle_chain_keys)
        cycle_policy = cycle.get("policy") if isinstance(cycle.get("policy"), dict) else {}
        from_zero_proof = cycle.get("from_zero_proof")
        proof_obligation_keys = {
            str(row.get("key"))
            for row in (from_zero_proof.get("chain_obligations") if isinstance(from_zero_proof, dict) and isinstance(from_zero_proof.get("chain_obligations"), list) else [])
            if isinstance(row, dict) and row.get("key")
        }
        if (
            not self_awareness_cycle_from_zero_proof_complete(from_zero_proof)
            or not required_cycle_chain_keys.issubset(proof_obligation_keys)
        ):
            cycle_steps = cycle.get("steps") if isinstance(cycle.get("steps"), list) else []
            failed_steps = [
                str(step.get("id") or "unknown")
                for step in cycle_steps
                if isinstance(step, dict) and step.get("ok") is not True
            ]
            from_zero_proof = self_awareness_cycle_from_zero_proof(
                generated_at=now_iso(),
                cycle_id=str(cycle.get("cycle_id") or "sacycle-validation-overlay"),
                probe_run_id=str(cycle.get("probe_run_id") or probe.get("run_id") or "saprobe-validation-overlay"),
                cycle_chain=cycle_chain,
                steps=cycle_steps,
                failed_steps=failed_steps,
                missing_chain=cycle_missing_chain,
            )
        from_zero_proof_ok = self_awareness_cycle_from_zero_proof_complete(from_zero_proof)
        bridge_proof = cycle.get("bridge_proof")
        bridge_proof_ok = self_awareness_cycle_bridge_proof_complete(bridge_proof)
        cycle_lineage = cycle.get("lineage") if isinstance(cycle.get("lineage"), dict) else {}
        topology_validation_add(
            checks,
            "fail" if not cycle.get("ok") or cycle_missing_chain or not from_zero_proof_ok or not bridge_proof_ok or cycle_policy.get("host_layer_mutates_stack") is not False or safe_int(cycle_policy.get("automatic_responses"), 0) != 0 else "ok",
            "e2e_cycle_proof",
            "cycle artifact proves probe-to-export loop with artifact-level from-zero proof, machine bridge proof, no stack mutation, and no automatic response",
            {
                "summary": cycle_summary,
                "missing_chain": cycle_missing_chain,
                "from_zero_proof_ok": from_zero_proof_ok,
                "from_zero_proof_summary": from_zero_proof.get("summary") if isinstance(from_zero_proof, dict) else None,
                "bridge_proof_ok": bridge_proof_ok,
                "bridge_proof_summary": bridge_proof.get("summary") if isinstance(bridge_proof, dict) else None,
                "policy": cycle_policy,
                "issues": cycle.get("issues"),
            },
        )
        topology_validation_add(
            checks,
            "fail" if not self_awareness_top_level_lineage_complete(cycle_lineage, require_cycle=True) else "ok",
            "e2e_cycle_lineage",
            "cycle exposes top-level from-zero, trace, thread, artifact, replay, response, export lineage with cycle id and no stack mutation",
            {
                "summary": cycle_lineage.get("summary") if isinstance(cycle_lineage, dict) else None,
                "cycle_id": cycle.get("cycle_id"),
                "run_id": cycle.get("probe_run_id"),
                "thread": cycle_lineage.get("thread") if isinstance(cycle_lineage, dict) else None,
                "trace": cycle_lineage.get("trace") if isinstance(cycle_lineage, dict) else None,
                "policy": cycle_lineage.get("policy") if isinstance(cycle_lineage, dict) else None,
            },
        )
    brief_claims = loaded.get("brief", {}).get("claims") if isinstance(loaded.get("brief", {}).get("claims"), list) else []
    claims_without_refs = [claim.get("claim") for claim in brief_claims if isinstance(claim, dict) and not claim.get("refs")]
    topology_validation_add(
        checks,
        "fail" if claims_without_refs else "ok",
        "brief_claim_refs",
        "semantic brief has evidence refs for every claim",
        {"claims_without_refs": claims_without_refs},
    )
    brief_doc = loaded.get("brief", {})
    brief_action_map = brief_doc.get("stack_handoff_action_map") if isinstance(brief_doc.get("stack_handoff_action_map"), dict) else {}
    brief_actions = brief_action_map.get("actions") if isinstance(brief_action_map.get("actions"), list) else []
    brief_safe_next = brief_doc.get("safe_next_action") if isinstance(brief_doc.get("safe_next_action"), dict) else {}
    brief_action_bad: list[str] = []
    if brief_action_map.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_brief_stack_handoff_action_map_v1":
        brief_action_bad.append("missing_action_map_schema")
    if nested_get(brief_action_map, ["policy", "host_layer_mutates_stack"]) is not False:
        brief_action_bad.append("action_map_mutation_policy")
    if nested_get(brief_action_map, ["policy", "executes_commands"]) is not False:
        brief_action_bad.append("action_map_exec_policy")
    if nested_get(brief_action_map, ["policy", "raw_secrets_included"]) is not False:
        brief_action_bad.append("action_map_secret_policy")
    if brief_safe_next.get("requires_human_approval") is not True or brief_safe_next.get("automatic") is not False or brief_safe_next.get("host_layer_mutates_stack") is not False:
        brief_action_bad.append("safe_next_action_policy")
    if safe_int(nested_get(brief_action_map, ["summary", "open_stack_requirements"]), -1) != len(brief_actions):
        brief_action_bad.append("action_count_mismatch")
    if safe_int(nested_get(brief_doc, ["summary", "stack_handoff_actions"]), -1) != len(brief_actions):
        brief_action_bad.append("brief_summary_action_count_mismatch")
    if brief_actions and safe_int(nested_get(brief_action_map, ["summary", "coverage_impact_entries"]), -1) != len(brief_actions):
        brief_action_bad.append("coverage_impact_count_mismatch")
    if brief_actions and not nested_get(brief_action_map, ["summary", "blocked_coverage_planes"]):
        brief_action_bad.append("blocked_coverage_planes_missing")
    if set(str(item) for item in brief_action_map.get("open_requirement_ids", [])) != {str(action.get("requirement_id")) for action in brief_actions if isinstance(action, dict)}:
        brief_action_bad.append("open_id_mismatch")
    for action in brief_actions:
        if not isinstance(action, dict):
            brief_action_bad.append("malformed_action")
            continue
        if action.get("owner_route") != "abyss-stack":
            brief_action_bad.append(f"{action.get('id')}:owner")
        if not action.get("closure_blockers"):
            brief_action_bad.append(f"{action.get('id')}:missing_closure_blockers")
        if not action.get("acceptance_verifiers") or not action.get("verifier_commands"):
            brief_action_bad.append(f"{action.get('id')}:missing_verifiers")
        if not isinstance(action.get("runbook_candidate"), dict):
            brief_action_bad.append(f"{action.get('id')}:missing_runbook")
        if not self_awareness_stack_coverage_impact_complete(action.get("coverage_impact")):
            brief_action_bad.append(f"{action.get('id')}:coverage_impact")
        if nested_get(action, ["policy", "host_layer_mutates_stack"]) is not False or nested_get(action, ["policy", "executes_commands"]) is not False:
            brief_action_bad.append(f"{action.get('id')}:action_policy")
        if nested_get(action, ["safe_next_action", "requires_human_approval"]) is not True or nested_get(action, ["safe_next_action", "automatic"]) is not False:
            brief_action_bad.append(f"{action.get('id')}:safe_next")
    topology_validation_add(
        checks,
        "fail" if brief_action_bad else "ok",
        "brief_stack_handoff_action_map",
        "semantic brief exposes prioritized stack handoff actions with blockers, runbooks, coverage impact, verifier commands, evidence refs, and no automatic stack mutation",
        {
            "summary": brief_action_map.get("summary"),
            "open_requirement_ids": brief_action_map.get("open_requirement_ids"),
            "safe_next_action": brief_safe_next,
            "bad": brief_action_bad,
        },
    )
    alerts_doc = loaded.get("alerts", {})
    working_gap_alert_candidates = [
        item for item in (alerts_doc.get("candidates") if isinstance(alerts_doc.get("candidates"), list) else [])
        if isinstance(item, dict) and item.get("working_stack_gap_service")
    ]
    if len(working_gap_alert_candidates) != len(working_gap_episodes):
        alerts_doc = self_awareness_alerts(write_latest=True)
        loaded["alerts"] = alerts_doc
        working_gap_alert_candidates = [
            item for item in (alerts_doc.get("candidates") if isinstance(alerts_doc.get("candidates"), list) else [])
            if isinstance(item, dict) and item.get("working_stack_gap_service")
        ]
    working_gap_alert_bad: list[str] = []
    working_gap_alert_services = {str(item.get("working_stack_gap_service")) for item in working_gap_alert_candidates if isinstance(item, dict)}
    if len(working_gap_alert_candidates) != len(working_gap_episodes):
        working_gap_alert_bad.append("candidate_count_mismatch")
    if working_gap_episode_services and working_gap_alert_services != working_gap_episode_services:
        working_gap_alert_bad.append("candidate_service_mismatch")
    for candidate in working_gap_alert_candidates:
        if not isinstance(candidate, dict):
            working_gap_alert_bad.append("malformed_candidate")
            continue
        candidate_id = str(candidate.get("id") or "unknown")
        contract = candidate.get("response_contract") if isinstance(candidate.get("response_contract"), dict) else {}
        if candidate.get("automatic") is not False:
            working_gap_alert_bad.append(f"{candidate_id}:automatic")
        if candidate.get("owner_route") != "abyss-machine:self-awareness":
            working_gap_alert_bad.append(f"{candidate_id}:owner_route")
        if contract.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_response_contract_v1":
            working_gap_alert_bad.append(f"{candidate_id}:contract_schema")
        if nested_get(contract, ["validated_episode", "episode_kind"]) != "working_stack_usage_gap":
            working_gap_alert_bad.append(f"{candidate_id}:episode_kind")
        if nested_get(contract, ["validated_episode", "truth_level"]) != "working_stack_gap_candidate":
            working_gap_alert_bad.append(f"{candidate_id}:truth_level")
        if nested_get(contract, ["runbook_candidate", "owner_route"]) != "abyss-stack":
            working_gap_alert_bad.append(f"{candidate_id}:runbook_owner")
        if nested_get(contract, ["runbook_candidate", "host_layer_mutates_stack"]) is not False:
            working_gap_alert_bad.append(f"{candidate_id}:runbook_mutation")
        if nested_get(contract, ["runbook_candidate", "machine_executes_stack_change"]) is not False:
            working_gap_alert_bad.append(f"{candidate_id}:runbook_execution")
        if not nested_get(contract, ["runbook_candidate", "verifier_commands"]):
            working_gap_alert_bad.append(f"{candidate_id}:verifiers")
        if nested_get(contract, ["policy", "automatic_action"]) is not False or nested_get(contract, ["policy", "automatic_response"]) is not False:
            working_gap_alert_bad.append(f"{candidate_id}:automatic_policy")
        if nested_get(contract, ["policy", "executes_commands"]) is not False or nested_get(contract, ["policy", "host_layer_mutates_stack"]) is not False:
            working_gap_alert_bad.append(f"{candidate_id}:mutation_policy")
        if not self_awareness_reaction_candidate_response_depth_complete(candidate):
            working_gap_alert_bad.append(f"{candidate_id}:response_depth")
    topology_validation_add(
        checks,
        "fail" if working_gap_alert_bad else "ok",
        "working_stack_usage_gap_reaction_candidates",
        "working-stack usage-gap causal episodes route through alerts/reactions as owner-gated response-contract candidates with no automatic execution",
        {
            "bad": working_gap_alert_bad,
            "candidate_services": sorted(working_gap_alert_services),
            "episode_services": sorted(working_gap_episode_services),
            "summary": alerts_doc.get("summary") if isinstance(alerts_doc, dict) else None,
        },
    )
    alerts_policy = alerts_doc.get("policy") if isinstance(alerts_doc.get("policy"), dict) else {}
    topology_validation_add(
        checks,
        "fail" if alerts_policy.get("automatic_action") is not False or alerts_policy.get("executes_commands") is not False else "ok",
        "alerts_owner_gated",
        "alerts create owner-gated reaction candidates only",
        {"policy": alerts_policy},
    )
    reactions_for_response = reaction_status(write_latest=True)
    responses_for_response = response_status(write_latest=True, reactions=reactions_for_response, refresh_reactions=False)
    reaction_candidates = reactions_for_response.get("candidates") if isinstance(reactions_for_response.get("candidates"), list) else []
    response_routes = responses_for_response.get("routes") if isinstance(responses_for_response.get("routes"), list) else []
    self_awareness_reaction_candidates = [
        item for item in reaction_candidates
        if isinstance(item, dict) and item.get("category") == "self-awareness"
    ]
    self_awareness_response_routes = [
        item for item in response_routes
        if isinstance(item, dict) and item.get("category") == "self-awareness"
    ]
    shallow_reaction_candidates = [
        item.get("id") for item in self_awareness_reaction_candidates
        if not self_awareness_reaction_candidate_response_depth_complete(item)
    ]
    shallow_response_routes = [
        item.get("id") for item in self_awareness_response_routes
        if not self_awareness_response_route_depth_complete(item)
    ]
    missing_body_trace_response_routes = [
        item.get("id") for item in self_awareness_response_routes
        if not self_awareness_body_trace_complete(nested_get(item, ["response_contract", "body_trace"]))
    ]
    missing_entity_event_document_response_routes = [
        item.get("id") for item in self_awareness_response_routes
        if not self_awareness_response_entity_event_document_context_complete(nested_get(item, ["response_contract", "entity_event_document_context"]))
    ]
    missing_response_routes = bool(self_awareness_reaction_candidates and not self_awareness_response_routes)
    topology_validation_add(
        checks,
        "fail" if shallow_reaction_candidates or shallow_response_routes or missing_entity_event_document_response_routes or missing_response_routes else "ok",
        "self_awareness_response_layer_depth",
        "validated self-awareness episodes route through reactions/responses with lineage, replay evidence, body trace, entity-event-document context, risk, blast radius, rollback, and no automatic execution",
        {
            "reaction_candidates": len(self_awareness_reaction_candidates),
            "response_routes": len(self_awareness_response_routes),
            "shallow_reaction_candidates": shallow_reaction_candidates,
            "shallow_response_routes": shallow_response_routes,
            "missing_response_routes": missing_response_routes,
            "missing_body_trace_response_routes": missing_body_trace_response_routes,
            "missing_entity_event_document_response_routes": missing_entity_event_document_response_routes,
            "reaction_summary": reactions_for_response.get("summary"),
            "response_summary": responses_for_response.get("summary"),
        },
    )
    topology_validation_add(
        checks,
        "fail" if missing_body_trace_response_routes else "ok",
        "self_awareness_response_body_trace",
        "self-awareness response routes preserve temporal, spatial, contextual, and host-body trace evidence for agent body reasoning",
        {
            "missing_body_trace_response_routes": missing_body_trace_response_routes,
            "response_routes": len(self_awareness_response_routes),
            "response_summary": responses_for_response.get("summary"),
        },
    )
    topology_validation_add(
        checks,
        "fail" if missing_entity_event_document_response_routes else "ok",
        "self_awareness_response_entity_event_document_context",
        "self-awareness response routes preserve automatic entity, event, document, and route bindings for agent body reasoning",
        {
            "missing_entity_event_document_response_routes": missing_entity_event_document_response_routes,
            "response_routes": len(self_awareness_response_routes),
            "response_summary": responses_for_response.get("summary"),
        },
    )
    capabilities = loaded.get("capabilities", {})
    requirements = loaded.get("requirements", {})
    raw_requirement_items = requirements.get("requirements") if isinstance(requirements.get("requirements"), list) else []
    requirements_need_direct_handoff_refresh = (
        requirements.get("schema") == f"{SCHEMA_PREFIX}_self_awareness_requirements_v1"
        and (
            not isinstance(requirements.get("open_stack_ids"), list)
            or not isinstance(requirements.get("open_stack_requirement_ids"), list)
            or any(
                isinstance(item, dict)
                and item.get("owner") == "abyss-stack"
                and (
                    not isinstance(item.get("acceptance_verifiers"), list)
                    or not item.get("acceptance_verifiers")
                    or not isinstance(item.get("current_state_digest"), dict)
                    or not isinstance(item.get("safe_next_action"), dict)
                    or not isinstance(item.get("coverage_impact"), dict)
                )
                for item in raw_requirement_items
            )
        )
    )
    if requirements_need_direct_handoff_refresh:
        requirements = self_awareness_requirements(write_latest=True)
        loaded["requirements"] = requirements
    requirement_items = requirements.get("requirements") if isinstance(requirements.get("requirements"), list) else []
    stack_handoff = requirements.get("stack_handoff") if isinstance(requirements.get("stack_handoff"), list) else []
    requirement_open_stack_ids = requirements.get("open_stack_ids") if isinstance(requirements.get("open_stack_ids"), list) else []
    requirement_open_stack_requirement_ids = requirements.get("open_stack_requirement_ids") if isinstance(requirements.get("open_stack_requirement_ids"), list) else []
    handoff_open_ids = [
        str(item.get("requirement_id") or item.get("id"))
        for item in stack_handoff
        if isinstance(item, dict)
        and (item.get("requirement_id") or item.get("id"))
        and item.get("owner") == "abyss-stack"
        and item.get("closed_by_current_probe") is not True
    ]
    bad_requirements = [
        item.get("id") for item in requirement_items
        if not isinstance(item, dict) or not item.get("owner") or not item.get("expected_shape") or item.get("host_layer_mutates_stack") is not False
    ]
    bad_requirement_direct_handoff_contracts = [
        item.get("id") for item in requirement_items
        if isinstance(item, dict)
        and item.get("owner") == "abyss-stack"
        and (
            not isinstance(item.get("acceptance_contract"), dict)
            or item["acceptance_contract"].get("schema") != f"{SCHEMA_PREFIX}_stack_requirement_acceptance_contract_v1"
            or not isinstance(item.get("machine_closure_probe"), dict)
            or not item["machine_closure_probe"].get("required_fields")
            or not isinstance(item.get("acceptance_verifiers"), list)
            or not item.get("acceptance_verifiers")
            or not self_awareness_stack_coverage_impact_complete(item.get("coverage_impact"))
            or nested_get(item, ["safe_next_action", "host_layer_mutates_stack"]) is not False
            or nested_get(item, ["current_state_digest", "schema"]) != f"{SCHEMA_PREFIX}_self_awareness_requirement_current_state_digest_v1"
            or nested_get(item, ["current_state_digest", "policy", "raw_payloads_included"]) is not False
            or nested_get(item, ["current_state_digest", "policy", "raw_secrets_included"]) is not False
            or item.get("handoff_contract_complete") is not True
        )
    ]
    bad_handoff_identity = [
        {"id": item.get("id"), "requirement_id": item.get("requirement_id")}
        for item in stack_handoff
        if not isinstance(item, dict) or not item.get("id") or item.get("requirement_id") != item.get("id")
    ]
    bad_handoff_contracts = [
        item.get("id") for item in stack_handoff
        if not isinstance(item, dict)
        or not isinstance(item.get("acceptance_contract"), dict)
        or item["acceptance_contract"].get("schema") != f"{SCHEMA_PREFIX}_stack_requirement_acceptance_contract_v1"
        or not isinstance(item.get("machine_closure_probe"), dict)
        or not item["machine_closure_probe"].get("required_fields")
        or not item["machine_closure_probe"].get("success_predicates")
        or not isinstance(item.get("acceptance_verifiers"), list)
        or not item.get("acceptance_verifiers")
        or not self_awareness_stack_coverage_impact_complete(item.get("coverage_impact"))
        or nested_get(item, ["safe_next_action", "host_layer_mutates_stack"]) is not False
        or nested_get(item, ["current_state_digest", "policy", "raw_secrets_included"]) is not False
        or item.get("handoff_contract_complete") is not True
        or item["acceptance_contract"].get("closure_semantics", {}).get("host_layer_mutates_stack") is not False
    ]
    bad_handoff_compat_contracts = [
        item.get("id") for item in stack_handoff
        if not isinstance(item, dict)
        or not self_awareness_stack_compat_contract_complete(item.get("compat_contract"))
    ]
    bad_requirement_open_ids = []
    if set(str(item) for item in requirement_open_stack_ids) != set(handoff_open_ids):
        bad_requirement_open_ids.append("open_stack_ids")
    if set(str(item) for item in requirement_open_stack_requirement_ids) != set(handoff_open_ids):
        bad_requirement_open_ids.append("open_stack_requirement_ids")
    topology_validation_add(
        checks,
        "fail" if bad_requirements or bad_requirement_direct_handoff_contracts or bad_handoff_identity or bad_handoff_contracts or bad_handoff_compat_contracts or bad_requirement_open_ids or not capabilities.get("ok") else "ok",
        "capability_map_and_requirements",
        "capability map is current and every missing stack capability is routed as a non-mutating machine-checkable requirement with direct stack-owner acceptance, verifier, coverage, and compat contracts",
        {
            "capabilities_ok": capabilities.get("ok"),
            "bad_requirements": bad_requirements,
            "bad_requirement_direct_handoff_contracts": bad_requirement_direct_handoff_contracts,
            "bad_handoff_identity": bad_handoff_identity,
            "bad_handoff_contracts": bad_handoff_contracts,
            "bad_handoff_compat_contracts": bad_handoff_compat_contracts,
            "bad_requirement_open_ids": bad_requirement_open_ids,
            "open_stack_ids": requirement_open_stack_ids,
            "open_stack_requirement_ids": requirement_open_stack_requirement_ids,
            "handoff_open_ids": handoff_open_ids,
            "requirements": len(requirement_items),
            "stack_handoff": len(stack_handoff),
        },
    )
    external_closure_evidence = nested_get(capabilities, ["raw", "stack_closure_external_evidence"])
    if not isinstance(external_closure_evidence, dict):
        capabilities = self_awareness_capabilities(write_latest=True)
        loaded["capabilities"] = capabilities
        external_closure_evidence = nested_get(capabilities, ["raw", "stack_closure_external_evidence"])
    external_closure_bad: list[str] = []
    external_closure_summary = None
    external_closure_status = None
    if not isinstance(external_closure_evidence, dict):
        external_closure_bad.append("missing_external_closure_evidence_raw")
    else:
        external_closure_summary = external_closure_evidence.get("summary") if isinstance(external_closure_evidence.get("summary"), dict) else {}
        external_closure_status = external_closure_evidence.get("status")
        external_closure_policy = external_closure_evidence.get("policy") if isinstance(external_closure_evidence.get("policy"), dict) else {}
        if external_closure_evidence.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_stack_closure_external_evidence_v1":
            external_closure_bad.append("schema")
        if external_closure_policy.get("read_only") is not True:
            external_closure_bad.append("policy:read_only")
        if external_closure_policy.get("host_layer_mutates_stack") is not False:
            external_closure_bad.append("policy:host_layer_mutates_stack")
        if external_closure_policy.get("raw_payloads_included") is not False:
            external_closure_bad.append("policy:raw_payloads")
        if external_closure_policy.get("raw_secrets_included") is not False:
            external_closure_bad.append("policy:raw_secrets")
        external_entries = external_closure_evidence.get("entries") if isinstance(external_closure_evidence.get("entries"), dict) else {}
        if not isinstance(external_closure_evidence.get("entries"), dict):
            external_closure_bad.append("entries")
        for requirement_id, row in external_entries.items():
            if not isinstance(row, dict):
                external_closure_bad.append(f"{requirement_id}:row")
                continue
            if row.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_stack_closure_external_evidence_row_v1":
                external_closure_bad.append(f"{requirement_id}:schema")
            if row.get("requirement_id") != requirement_id:
                external_closure_bad.append(f"{requirement_id}:identity")
            row_policy = row.get("policy") if isinstance(row.get("policy"), dict) else {}
            if row_policy.get("host_layer_mutates_stack") is not False:
                external_closure_bad.append(f"{requirement_id}:mutation_policy")
            if row_policy.get("raw_payloads_included") is not False:
                external_closure_bad.append(f"{requirement_id}:raw_payload_policy")
            if row_policy.get("raw_secrets_included") is not False:
                external_closure_bad.append(f"{requirement_id}:raw_secret_policy")
            if row.get("accepted") is True:
                if not isinstance(row.get("checks"), dict) or not row.get("checks"):
                    external_closure_bad.append(f"{requirement_id}:accepted_without_checks")
                if not isinstance(row.get("evidence_refs"), list) or not row.get("evidence_refs"):
                    external_closure_bad.append(f"{requirement_id}:accepted_without_evidence_refs")
                if not isinstance(row.get("current_state"), dict):
                    external_closure_bad.append(f"{requirement_id}:accepted_without_current_state")
    topology_validation_add(
        checks,
        "fail" if external_closure_bad else "ok",
        "stack_closure_external_evidence_contract",
        "optional stack-owned closure evidence route is read-only, redacted, bounded, and only accepted rows can close stack blockers",
        {
            "bad": external_closure_bad,
            "status": external_closure_status,
            "summary": external_closure_summary,
            "config_path": external_closure_evidence.get("config_path") if isinstance(external_closure_evidence, dict) else None,
        },
    )
    requirement_probes = loaded.get("requirement_probes", {})
    requirement_probe_rows = requirement_probes.get("probes") if isinstance(requirement_probes.get("probes"), list) else []
    probe_summary = requirement_probes.get("summary") if isinstance(requirement_probes.get("summary"), dict) else {}
    bad_probe_identity = [
        {"id": probe.get("id"), "requirement_id": probe.get("requirement_id")}
        for probe in requirement_probe_rows
        if not isinstance(probe, dict) or not probe.get("id") or probe.get("requirement_id") != probe.get("id")
    ]
    probes_without_checks = [
        probe.get("id") for probe in requirement_probe_rows
        if not isinstance(probe, dict) or not probe.get("checks") or not probe.get("evidence_refs")
    ]
    probes_without_contract_detail = [
        probe.get("id") for probe in requirement_probe_rows
        if not isinstance(probe, dict)
        or not isinstance(probe.get("acceptance_contract"), dict)
        or not isinstance(probe.get("machine_closure_probe"), dict)
        or not probe["machine_closure_probe"].get("required_fields")
        or not probe["machine_closure_probe"].get("success_predicates")
        or not isinstance(probe.get("acceptance_verifiers"), list)
        or not probe.get("acceptance_verifiers")
        or not isinstance(probe.get("closure_semantics"), dict)
        or probe["closure_semantics"].get("host_layer_mutates_stack") is not False
        or probe.get("stack_handoff") is not True
    ]
    probe_mutation_claims = [
        probe.get("id") for probe in requirement_probe_rows
        if isinstance(probe, dict) and probe.get("host_layer_mutates_stack") is not False
    ]
    probe_policy_bad = [
        probe.get("id") for probe in requirement_probe_rows
        if not isinstance(probe, dict)
        or not isinstance(probe.get("policy"), dict)
        or nested_get(probe, ["policy", "read_only"]) is not True
        or nested_get(probe, ["policy", "host_layer_mutates_stack"]) is not False
        or nested_get(probe, ["policy", "executes_commands"]) is not False
        or nested_get(probe, ["policy", "action_execution"]) is not False
        or nested_get(probe, ["policy", "raw_secrets_included"]) is not False
    ]
    bad_runbook_candidates = [
        probe.get("id") for probe in requirement_probe_rows
        if not isinstance(probe, dict)
        or not self_awareness_stack_requirement_runbook_complete(
            probe.get("runbook_candidate") if isinstance(probe.get("runbook_candidate"), dict) else {},
            str(probe.get("id") or ""),
        )
    ]
    bad_closure_readiness: list[str] = []
    for probe in requirement_probe_rows:
        if not isinstance(probe, dict):
            bad_closure_readiness.append("malformed_probe")
            continue
        probe_id = str(probe.get("id") or probe.get("requirement_id") or "unknown")
        readiness = probe.get("closure_readiness") if isinstance(probe.get("closure_readiness"), dict) else {}
        if readiness.get("schema") != f"{SCHEMA_PREFIX}_stack_handoff_closure_readiness_v1":
            bad_closure_readiness.append(f"{probe_id}:schema")
        if readiness.get("requirement_id") != probe_id:
            bad_closure_readiness.append(f"{probe_id}:identity")
        if readiness.get("status") != probe.get("status"):
            bad_closure_readiness.append(f"{probe_id}:status")
        if not isinstance(readiness.get("fulfilled_checks"), list):
            bad_closure_readiness.append(f"{probe_id}:fulfilled_checks")
        if not isinstance(readiness.get("missing_checks"), list):
            bad_closure_readiness.append(f"{probe_id}:missing_checks")
        if safe_int(readiness.get("open_blocker_count"), -1) != len(readiness.get("missing_checks") if isinstance(readiness.get("missing_checks"), list) else []):
            bad_closure_readiness.append(f"{probe_id}:open_blocker_count")
        if not isinstance(readiness.get("closure_evidence_needed"), list):
            bad_closure_readiness.append(f"{probe_id}:closure_evidence_needed")
        if not readiness.get("verifier_commands"):
            bad_closure_readiness.append(f"{probe_id}:verifier_commands")
        if nested_get(readiness, ["safe_next_action", "host_layer_mutates_stack"]) is not False:
            bad_closure_readiness.append(f"{probe_id}:safe_next_policy")
        if nested_get(readiness, ["policy", "host_layer_mutates_stack"]) is not False:
            bad_closure_readiness.append(f"{probe_id}:mutation_policy")
        if nested_get(readiness, ["policy", "executes_commands"]) is not False:
            bad_closure_readiness.append(f"{probe_id}:exec_policy")
        if nested_get(readiness, ["policy", "automatic_remediation"]) is not False:
            bad_closure_readiness.append(f"{probe_id}:automatic_policy")
        if probe.get("closed_by_current_probe") is not True and not readiness.get("missing_checks"):
            bad_closure_readiness.append(f"{probe_id}:open_without_missing_checks")
    if safe_int(nested_get(requirement_probes, ["summary", "closure_readiness_packets"]), -1) != len(requirement_probe_rows):
        bad_closure_readiness.append("summary_packet_count_mismatch")
    topology_validation_add(
        checks,
        "fail" if not requirement_probes.get("ok") or bad_probe_identity or probes_without_checks or probes_without_contract_detail or probe_mutation_claims or probe_policy_bad or bad_runbook_candidates or len(requirement_probe_rows) != len(stack_handoff) else "ok",
        "requirement_probes_acceptance_contracts",
        "stack-owned acceptance contracts have executable read-only machine probes and owner-gated runbook candidates",
        {
            "ok": requirement_probes.get("ok"),
            "summary": probe_summary,
            "probes": len(requirement_probe_rows),
            "stack_handoff": len(stack_handoff),
            "bad_probe_identity": bad_probe_identity,
            "probes_without_checks": probes_without_checks,
            "probes_without_contract_detail": probes_without_contract_detail,
            "mutation_claims": probe_mutation_claims,
            "probe_policy_bad": probe_policy_bad,
            "bad_runbook_candidates": bad_runbook_candidates,
        },
    )
    topology_validation_add(
        checks,
        "fail" if bad_closure_readiness else "ok",
        "stack_handoff_closure_readiness",
        "stack-owned requirement probes expose closure-readiness packets with fulfilled/missing checks, dependencies, verifier commands, and no stack mutation policy",
        {
            "bad": bad_closure_readiness,
            "summary": probe_summary,
            "probe_count": len(requirement_probe_rows),
        },
    )
    failure_matrix = loaded.get("failure_matrix", {})
    failure_rows = failure_matrix.get("rows") if isinstance(failure_matrix.get("rows"), list) else []
    failure_missing_required = nested_get(failure_matrix, ["summary", "missing_required"]) or []
    failure_malformed = nested_get(failure_matrix, ["summary", "malformed"]) or []
    failure_mutation_claims = [
        row.get("id") for row in failure_rows
        if isinstance(row, dict) and (row.get("host_layer_mutates_stack") is not False or row.get("automatic_remediation") is not False)
    ]
    topology_validation_add(
        checks,
        "fail" if not failure_matrix.get("ok") or failure_missing_required or failure_malformed or failure_mutation_claims else "ok",
        "failure_matrix_coverage",
        "failure matrix covers required missing/stale/down/denied/redaction/cardinality scenarios without host stack mutation",
        {
            "ok": failure_matrix.get("ok"),
            "summary": failure_matrix.get("summary"),
            "mutation_claims": failure_mutation_claims,
        },
    )
    failure_row_ids = {str(row.get("id")) for row in failure_rows if isinstance(row, dict)}
    required_failure_classes = {
        "machine.resource-denial",
        "machine.nervous-semantic-stale",
        "machine.secret-redaction",
        "stack.loki-logql-missing-or-cardinality-risk",
        "stack.downtime-bounded-readonly",
    }
    missing_failure_classes = sorted(required_failure_classes - failure_row_ids)
    topology_validation_add(
        checks,
        "fail" if missing_failure_classes else "ok",
        "failure_matrix_required_classes",
        "failure matrix includes resource denial, stale nervous, redaction, cardinality risk, and stack downtime classes",
        {"missing": missing_failure_classes, "present": sorted(failure_row_ids)},
    )
    capability_items = capabilities.get("capabilities") if isinstance(capabilities.get("capabilities"), list) else []
    capability_ids = {str(item.get("id")) for item in capability_items if isinstance(item, dict)}
    capability_by_id = {
        str(item.get("id")): item
        for item in capability_items
        if isinstance(item, dict) and item.get("id")
    }
    resident_detail = capability_by_id.get("warm-e2b.resident-cognitive-worker", {}).get("detail")
    ai_multimodal_detail = capability_by_id.get("ai.multimodal.capability-map", {}).get("detail")
    llm_escalation_detail = capability_by_id.get("llm.escalation.routes", {}).get("detail")
    if (
        not self_awareness_resident_worker_detail_complete(resident_detail if isinstance(resident_detail, dict) else {})
        or not self_awareness_ai_multimodal_detail_complete(ai_multimodal_detail if isinstance(ai_multimodal_detail, dict) else {})
        or not self_awareness_llm_escalation_detail_complete(llm_escalation_detail if isinstance(llm_escalation_detail, dict) else {})
    ):
        capabilities = self_awareness_capabilities(write_latest=True)
        loaded["capabilities"] = capabilities
        capability_items = capabilities.get("capabilities") if isinstance(capabilities.get("capabilities"), list) else []
        capability_ids = {str(item.get("id")) for item in capability_items if isinstance(item, dict)}
        capability_by_id = {
            str(item.get("id")): item
            for item in capability_items
            if isinstance(item, dict) and item.get("id")
        }
        resident_detail = capability_by_id.get("warm-e2b.resident-cognitive-worker", {}).get("detail")
        ai_multimodal_detail = capability_by_id.get("ai.multimodal.capability-map", {}).get("detail")
        llm_escalation_detail = capability_by_id.get("llm.escalation.routes", {}).get("detail")
    required_capability_ids = {
        "prometheus.targets",
        "loki.logql",
        "grafana.health",
        "alloy.otel.pipeline",
        "stack.active.services",
        "ai.multimodal.capability-map",
        "warm-e2b.resident-cognitive-worker",
        "llm.escalation.routes",
        "rag.memory.trace-gate",
        "nervous.freshness-gate",
        "host.governance-gates",
        "governed.response-loop",
    }
    missing_capability_ids = sorted(required_capability_ids - capability_ids)
    topology_validation_add(
        checks,
        "fail" if missing_capability_ids else "ok",
        "full_stack_capability_planes",
        "capability map covers observability, active stack services, AI, warm-E2B, RAG, nervous freshness, and governance planes",
        {"missing": missing_capability_ids, "present": sorted(capability_ids)},
    )
    http_capability_ids = {
        "prometheus.targets",
        "loki.logql",
        "grafana.health",
        "alertmanager.lifecycle",
        "tempo.trace.backend",
        "langgraph.investigator.runtime",
    }
    bad_capability_matrix_rows = [
        item.get("id") for item in capability_items
        if not isinstance(item, dict)
        or not isinstance(item.get("matrix"), dict)
        or item["matrix"].get("schema") != f"{SCHEMA_PREFIX}_self_awareness_capability_matrix_row_v1"
        or not isinstance(item.get("access"), dict)
        or item["access"].get("read_only") is not True
        or item["access"].get("host_layer_mutates_stack") is not False
        or item["access"].get("stores_raw_private_payload") is not False
        or not isinstance(item.get("owner_boundary"), dict)
        or item["owner_boundary"].get("host_layer_mutates_stack") is not False
        or item["owner_boundary"].get("owner") != item.get("owner")
        or not isinstance(item.get("freshness"), dict)
        or item["freshness"].get("freshness_must_precede_reasoning") is not True
        or item["freshness"].get("raw_evidence_is_not_truth") is not True
        or not isinstance(item.get("history"), dict)
        or not isinstance(item.get("schemas"), list)
        or not isinstance(item.get("latest_artifacts"), list)
        or not isinstance(item.get("endpoints"), list)
        or nested_get(item, ["matrix", "evidence_route", "has_endpoint_or_artifact"]) is not True
        or (item.get("id") in http_capability_ids and not item.get("endpoints"))
    ]
    depth_summary = nested_get(capabilities, ["summary", "capability_matrix_depth"]) if isinstance(capabilities.get("summary"), dict) else {}
    depth_summary = depth_summary if isinstance(depth_summary, dict) else {}
    topology_validation_add(
        checks,
        "fail" if bad_capability_matrix_rows or safe_int(depth_summary.get("with_matrix"), 0) != len(capability_items) else "ok",
        "capability_matrix_depth",
        "capability rows expose endpoint/artifact, schema, freshness, history, access, and owner-boundary metadata",
        {
            "bad_rows": bad_capability_matrix_rows,
            "summary": depth_summary,
            "http_capabilities_requiring_endpoints": sorted(http_capability_ids & capability_ids),
        },
    )
    governance_detail = capability_by_id.get("host.governance-gates", {}).get("detail")
    topology_validation_add(
        checks,
        "fail" if not self_awareness_governance_gate_detail_complete(governance_detail if isinstance(governance_detail, dict) else {}) else "ok",
        "governance_gate_detail",
        "host governance gate capability exposes concrete memory, resource, and mode readiness without stack mutation",
        {"detail": governance_detail},
    )
    topology_validation_add(
        checks,
        "fail" if not self_awareness_resident_worker_detail_complete(resident_detail if isinstance(resident_detail, dict) else {}) else "ok",
        "warm_e2b_resident_worker_detail",
        "warm-E2B resident worker exposes serving health, monitor, resource, candidate, eval, and non-action policy detail",
        {"detail": resident_detail},
    )
    investigation_doc = loaded.get("investigate", {})
    resident_cognitive_packet = investigation_doc.get("resident_cognitive_packet") if isinstance(investigation_doc, dict) else {}
    if not self_awareness_resident_cognitive_packet_complete(resident_cognitive_packet if isinstance(resident_cognitive_packet, dict) else {}):
        investigation_doc = self_awareness_investigate("latest", write_latest=True)
        loaded["investigate"] = investigation_doc
        resident_cognitive_packet = investigation_doc.get("resident_cognitive_packet") if isinstance(investigation_doc, dict) else {}
    topology_validation_add(
        checks,
        "fail" if not self_awareness_resident_cognitive_packet_complete(resident_cognitive_packet if isinstance(resident_cognitive_packet, dict) else {}) else "ok",
        "resident_cognitive_worker_depth",
        "warm-E2B investigation packet exposes bounded context, read-only tools, hypothesis tests, contradiction notes, and gated escalation policy",
        {
            "summary": investigation_doc.get("summary") if isinstance(investigation_doc, dict) else None,
            "tool_kinds": sorted({
                str(tool.get("kind"))
                for tool in (resident_cognitive_packet.get("read_only_tools") if isinstance(resident_cognitive_packet, dict) and isinstance(resident_cognitive_packet.get("read_only_tools"), list) else [])
                if isinstance(tool, dict)
            }),
            "hypothesis_tests": len(resident_cognitive_packet.get("hypothesis_tests") if isinstance(resident_cognitive_packet, dict) and isinstance(resident_cognitive_packet.get("hypothesis_tests"), list) else []),
            "contradiction_notes": len(resident_cognitive_packet.get("contradiction_notes") if isinstance(resident_cognitive_packet, dict) and isinstance(resident_cognitive_packet.get("contradiction_notes"), list) else []),
            "policy": resident_cognitive_packet.get("policy") if isinstance(resident_cognitive_packet, dict) else None,
            "escalation_gate": resident_cognitive_packet.get("escalation_gate") if isinstance(resident_cognitive_packet, dict) else None,
        },
    )
    replay_doc = loaded.get("replay", {})
    resident_cognitive_replay = replay_doc.get("resident_cognitive_replay") if isinstance(replay_doc, dict) and isinstance(replay_doc.get("resident_cognitive_replay"), dict) else {}
    if not self_awareness_resident_cognitive_replay_complete(resident_cognitive_replay):
        replay_doc = self_awareness_replay(write_latest=True)
        loaded["replay"] = replay_doc
        resident_cognitive_replay = replay_doc.get("resident_cognitive_replay") if isinstance(replay_doc.get("resident_cognitive_replay"), dict) else {}
    export_doc = loaded.get("export", {})
    resident_cognitive_export = export_doc.get("resident_cognitive_replay") if isinstance(export_doc, dict) and isinstance(export_doc.get("resident_cognitive_replay"), dict) else {}
    if not self_awareness_resident_cognitive_replay_complete(resident_cognitive_export):
        export_doc = self_awareness_export(write_latest=True)
        loaded["export"] = export_doc
        resident_cognitive_export = export_doc.get("resident_cognitive_replay") if isinstance(export_doc.get("resident_cognitive_replay"), dict) else {}
    topology_validation_add(
        checks,
        "fail" if not self_awareness_resident_cognitive_replay_complete(resident_cognitive_replay) or not self_awareness_resident_cognitive_replay_complete(resident_cognitive_export) else "ok",
        "resident_cognitive_replay_export_depth",
        "warm-E2B cognitive packet is preserved through replay and portable export with read-only tools, hypotheses, contradictions, evidence refs, and gated escalation",
        {
            "replay_summary": resident_cognitive_replay.get("summary") if isinstance(resident_cognitive_replay, dict) else None,
            "export_summary": resident_cognitive_export.get("summary") if isinstance(resident_cognitive_export, dict) else None,
            "replay_state_preservation": resident_cognitive_replay.get("state_preservation") if isinstance(resident_cognitive_replay, dict) else None,
            "export_state_preservation": resident_cognitive_export.get("state_preservation") if isinstance(resident_cognitive_export, dict) else None,
            "replay_policy": resident_cognitive_replay.get("policy") if isinstance(resident_cognitive_replay, dict) else None,
            "export_policy": resident_cognitive_export.get("policy") if isinstance(resident_cognitive_export, dict) else None,
        },
    )
    topology_validation_add(
        checks,
        "fail" if not self_awareness_ai_multimodal_detail_complete(ai_multimodal_detail if isinstance(ai_multimodal_detail, dict) else {}) else "ok",
        "ai_multimodal_detail",
        "AI multimodal capability exposes concrete STT, embeddings, LLM, TTS, NPU, model-root, device, and non-promotion detail",
        {"detail": ai_multimodal_detail},
    )
    topology_validation_add(
        checks,
        "fail" if not self_awareness_llm_escalation_detail_complete(llm_escalation_detail if isinstance(llm_escalation_detail, dict) else {}) else "ok",
        "llm_escalation_detail",
        "LLM escalation capability exposes concrete E4B workhorse review pipeline, Qwen lazy-load routes, resource/mode gates, and non-action policy",
        {"detail": llm_escalation_detail},
    )
    event_sources = {str(event.get("source")) for event in events if isinstance(event, dict)}
    required_event_sources = {"prometheus", "loki", "ai", "llm", "rag", "nervous", "memory", "resource", "mode", "reactions", "responses"}
    missing_event_sources = sorted(required_event_sources - event_sources)
    topology_validation_add(
        checks,
        "fail" if missing_event_sources else "ok",
        "full_stack_observation_sources",
        "observation events include stack observability, AI/warm-E2B, RAG, nervous, resource/mode/memory, and response-loop sources",
        {"missing": missing_event_sources, "sources": sorted(event_sources)},
    )
    query_doc = loaded.get("query", {})
    query_plan = query_doc.get("query_plan") if isinstance(query_doc.get("query_plan"), dict) else {}
    topology_validation_add(
        checks,
        "fail" if not query_plan.get("bounded") or not query_plan.get("promql") or not query_plan.get("logql") else "ok",
        "query_builders",
        "bounded PromQL/LogQL/context query builders are present",
        {"query_plan": query_plan},
    )
    correlation = loaded.get("correlation", {})
    correlation_summary = correlation.get("summary") if isinstance(correlation.get("summary"), dict) else {}
    missing_correlation = [
        key for key in ("joins", "dependencies", "slo_views", "anomaly_baselines", "provenance_chains")
        if safe_int(correlation_summary.get(key), 0) <= 0
    ]
    topology_validation_add(
        checks,
        "fail" if missing_correlation else "ok",
        "correlation_planes",
        "correlation readmodel includes joins, dependencies, SLO/error-budget, anomaly baseline, and provenance chains",
        {"missing": missing_correlation, "summary": correlation_summary},
    )
    investigation = loaded.get("investigate", {})
    graph = investigation.get("graph") if isinstance(investigation.get("graph"), dict) else {}
    checkpoints = investigation.get("checkpoints") if isinstance(investigation.get("checkpoints"), list) else []
    conclusion = investigation.get("conclusion") if isinstance(investigation.get("conclusion"), dict) else {}
    investigation_policy = investigation.get("policy") if isinstance(investigation.get("policy"), dict) else {}
    investigation_states = investigation.get("states") if isinstance(investigation.get("states"), list) else []
    state_by_node = {
        str(row.get("node")): (row.get("state") if isinstance(row.get("state"), dict) else {})
        for row in investigation_states
        if isinstance(row, dict) and row.get("node")
    }
    validation_state = state_by_node.get("validate_evidence", {})
    validation_doc = validation_state.get("validation") if isinstance(validation_state.get("validation"), dict) else {}
    brief_candidate_state = state_by_node.get("brief_reaction_candidate", {})
    brief_safe_next = brief_candidate_state.get("safe_next_action") if isinstance(brief_candidate_state.get("safe_next_action"), dict) else {}

    def _investigation_stack_handoff_action_map_status() -> dict[str, Any]:
        request_state = state_by_node.get("request_more_evidence", {})
        request_action_map = request_state.get("stack_handoff_action_map") if isinstance(request_state.get("stack_handoff_action_map"), dict) else {}
        request_summary = request_action_map.get("summary") if isinstance(request_action_map.get("summary"), dict) else {}
        request_actions = request_action_map.get("actions") if isinstance(request_action_map.get("actions"), list) else []
        readiness_schema = f"{SCHEMA_PREFIX}_self_awareness_investigation_stack_handoff_closure_readiness_v1"
        request_readiness = request_state.get("stack_handoff_closure_readiness") if isinstance(request_state.get("stack_handoff_closure_readiness"), dict) else {}
        brief_readiness = brief_candidate_state.get("stack_handoff_closure_readiness") if isinstance(brief_candidate_state.get("stack_handoff_closure_readiness"), dict) else {}
        investigation_readiness = investigation.get("stack_handoff_closure_readiness") if isinstance(investigation.get("stack_handoff_closure_readiness"), dict) else {}
        request_rows = request_state.get("requests") if isinstance(request_state.get("requests"), list) else []
        request_stack_actions = [
            item for item in request_rows
            if isinstance(item, dict) and item.get("kind") == "stack_handoff_action"
        ]
        investigation_action_map = investigation.get("stack_handoff_action_map") if isinstance(investigation.get("stack_handoff_action_map"), dict) else {}
        conclusion_action_map = conclusion.get("stack_handoff_action_map") if isinstance(conclusion.get("stack_handoff_action_map"), dict) else {}
        conclusion_readiness = conclusion.get("stack_handoff_closure_readiness") if isinstance(conclusion.get("stack_handoff_closure_readiness"), dict) else {}
        conclusion_action_summary = conclusion_action_map.get("summary") if isinstance(conclusion_action_map.get("summary"), dict) else {}
        conclusion_coverage_by_requirement = conclusion_action_map.get("coverage_impact_by_requirement") if isinstance(conclusion_action_map.get("coverage_impact_by_requirement"), dict) else {}
        validation_checks = validation_doc.get("checks") if isinstance(validation_doc.get("checks"), list) else []
        validation_by_id = {
            str(item.get("id")): item
            for item in validation_checks
            if isinstance(item, dict) and item.get("id")
        }
        bad: list[str] = []
        expected_schema = f"{SCHEMA_PREFIX}_self_awareness_brief_stack_handoff_action_map_v1"
        if request_action_map.get("schema") != expected_schema:
            bad.append("request_action_map_schema")
        if investigation_action_map.get("schema") != expected_schema:
            bad.append("investigation_action_map_schema")
        if conclusion_action_map.get("schema") != expected_schema:
            bad.append("conclusion_action_map_schema")
        if nested_get(request_action_map, ["policy", "host_layer_mutates_stack"]) is not False:
            bad.append("request_action_map_mutation_policy")
        if nested_get(request_action_map, ["policy", "executes_commands"]) is not False:
            bad.append("request_action_map_exec_policy")
        if nested_get(request_action_map, ["policy", "raw_secrets_included"]) is not False:
            bad.append("request_action_map_secret_policy")
        action_safe_next = request_action_map.get("safe_next_action") if isinstance(request_action_map.get("safe_next_action"), dict) else {}
        if (
            action_safe_next.get("requires_human_approval") is not True
            or action_safe_next.get("automatic") is not False
            or action_safe_next.get("executes_commands") is not False
            or action_safe_next.get("host_layer_mutates_stack") is not False
        ):
            bad.append("action_map_safe_next_policy")
        open_stack_requirements = safe_int(request_summary.get("open_stack_requirements"), 0)
        if open_stack_requirements != len(request_actions):
            bad.append("request_action_count_mismatch")
        if safe_int(request_summary.get("actions"), len(request_actions)) != len(request_actions):
            bad.append("request_summary_action_mismatch")
        if open_stack_requirements > 0 and not request_summary.get("top_requirement_id"):
            bad.append("missing_top_requirement")
        if open_stack_requirements > 0 and safe_int(request_summary.get("coverage_impact_entries"), -1) != len(request_actions):
            bad.append("request_coverage_impact_count_mismatch")
        if open_stack_requirements > 0 and not request_summary.get("blocked_coverage_planes"):
            bad.append("request_blocked_coverage_planes_missing")
        if safe_int(nested_get(investigation, ["summary", "stack_handoff_actions"]), -1) != len(request_actions):
            bad.append("investigation_summary_action_mismatch")
        if safe_int(nested_get(investigation, ["summary", "stack_handoff_open"]), -1) != open_stack_requirements:
            bad.append("investigation_summary_open_mismatch")
        if safe_int(conclusion_action_summary.get("open_stack_requirements"), -1) != open_stack_requirements:
            bad.append("conclusion_summary_open_mismatch")
        if len(request_stack_actions) != len(request_actions):
            bad.append("request_rows_action_count_mismatch")
        if open_stack_requirements > 0 and len(conclusion_coverage_by_requirement) != len(request_actions):
            bad.append("conclusion_coverage_impact_count_mismatch")
        for surface, readiness in {
            "request": request_readiness,
            "brief": brief_readiness,
            "investigation": investigation_readiness,
            "conclusion": conclusion_readiness,
        }.items():
            if readiness.get("schema") != readiness_schema:
                bad.append(f"{surface}_closure_readiness_schema")
                continue
            if nested_get(readiness, ["summary", "complete"]) is not True:
                bad.append(f"{surface}_closure_readiness_incomplete")
            if safe_int(nested_get(readiness, ["summary", "packets"]), -1) != len(request_actions):
                bad.append(f"{surface}_closure_readiness_packet_count")
            if safe_int(nested_get(readiness, ["summary", "coverage_impact_entries"]), -1) != len(request_actions):
                bad.append(f"{surface}_coverage_impact_count")
            if request_actions and not nested_get(readiness, ["summary", "blocked_coverage_planes"]):
                bad.append(f"{surface}_blocked_coverage_planes")
            if nested_get(readiness, ["policy", "host_layer_mutates_stack"]) is not False:
                bad.append(f"{surface}_closure_readiness_mutation_policy")
            if nested_get(readiness, ["policy", "executes_commands"]) is not False or nested_get(readiness, ["policy", "action_execution"]) is not False:
                bad.append(f"{surface}_closure_readiness_exec_policy")
        open_ids = {str(item) for item in request_action_map.get("open_requirement_ids", [])}
        action_ids = {str(action.get("requirement_id")) for action in request_actions if isinstance(action, dict)}
        if open_ids != action_ids:
            bad.append("open_requirement_ids_mismatch")
        if request_actions and request_summary.get("top_requirement_id") != request_actions[0].get("requirement_id"):
            bad.append("top_requirement_mismatch")
        validation_action_map = validation_by_id.get("stack_handoff_action_map_complete")
        if not validation_action_map or validation_action_map.get("ok") is not True:
            bad.append("evidence_validation_action_map_missing")
        validation_readiness = validation_by_id.get("stack_handoff_closure_readiness_complete")
        if not validation_readiness or validation_readiness.get("ok") is not True:
            bad.append("evidence_validation_closure_readiness_missing")
        validation_coverage = validation_by_id.get("stack_handoff_coverage_impact_complete")
        if not validation_coverage or validation_coverage.get("ok") is not True:
            bad.append("evidence_validation_coverage_impact_missing")
        for action in request_actions:
            if not isinstance(action, dict):
                bad.append("malformed_action")
                continue
            action_id = str(action.get("id") or action.get("requirement_id") or "unknown")
            if not action.get("closure_blockers") or not action.get("closure_blocker_keys"):
                bad.append(f"{action_id}:closure_blockers")
            if not action.get("runbook_candidate_id") or not isinstance(action.get("runbook_candidate"), dict):
                bad.append(f"{action_id}:runbook")
            if not action.get("acceptance_verifiers") or not action.get("verifier_commands"):
                bad.append(f"{action_id}:verifiers")
            if not isinstance(action.get("closure_readiness"), dict):
                bad.append(f"{action_id}:closure_readiness")
            if not self_awareness_stack_coverage_impact_complete(action.get("coverage_impact")):
                bad.append(f"{action_id}:coverage_impact")
            if nested_get(action, ["policy", "host_layer_mutates_stack"]) is not False or nested_get(action, ["policy", "executes_commands"]) is not False:
                bad.append(f"{action_id}:policy")
            if nested_get(action, ["safe_next_action", "requires_human_approval"]) is not True or nested_get(action, ["safe_next_action", "automatic"]) is not False:
                bad.append(f"{action_id}:safe_next")
        for request in request_stack_actions:
            request_id = str(request.get("id") or request.get("requirement_id") or "unknown")
            if not request.get("closure_blockers") or not request.get("closure_blocker_keys"):
                bad.append(f"{request_id}:request_closure_blockers")
            if not request.get("runbook_candidate_id") or not isinstance(request.get("runbook_candidate"), dict):
                bad.append(f"{request_id}:request_runbook")
            if not request.get("acceptance_verifiers") or not request.get("verifier_commands"):
                bad.append(f"{request_id}:request_verifiers")
            if not isinstance(request.get("closure_readiness"), dict):
                bad.append(f"{request_id}:request_closure_readiness")
            if not self_awareness_stack_coverage_impact_complete(request.get("coverage_impact")):
                bad.append(f"{request_id}:request_coverage_impact")
            if (
                request.get("requires_human_approval") is not True
                or request.get("automatic") is not False
                or request.get("executes_commands") is not False
                or request.get("host_layer_mutates_stack") is not False
            ):
                bad.append(f"{request_id}:request_policy")
            if nested_get(request, ["safe_next_action", "requires_human_approval"]) is not True or nested_get(request, ["safe_next_action", "automatic"]) is not False:
                bad.append(f"{request_id}:request_safe_next")
            if nested_get(request, ["policy", "host_layer_mutates_stack"]) is not False or nested_get(request, ["policy", "executes_commands"]) is not False:
                bad.append(f"{request_id}:request_embedded_policy")
        return {
            "bad": bad,
            "summary": request_summary,
            "open_requirement_ids": sorted(open_ids),
            "request_action_count": len(request_actions),
            "request_stack_action_count": len(request_stack_actions),
            "closure_readiness_summary": investigation_readiness.get("summary") if isinstance(investigation_readiness.get("summary"), dict) else {},
            "closure_readiness_state_preservation": {
                "request_more_evidence": request_readiness.get("schema") == readiness_schema,
                "brief_reaction_candidate": brief_readiness.get("schema") == readiness_schema,
                "investigation": investigation_readiness.get("schema") == readiness_schema,
                "write_semantic_conclusion": conclusion_readiness.get("schema") == readiness_schema,
            },
            "validation_check_ids": sorted(validation_by_id),
            "safe_next_action": action_safe_next,
        }

    investigation_stack_handoff = _investigation_stack_handoff_action_map_status()
    investigation_stack_handoff_bad = investigation_stack_handoff.get("bad") if isinstance(investigation_stack_handoff.get("bad"), list) else []
    required_investigation_nodes = list(SELF_AWARENESS_INVESTIGATION_NODE_ORDER)
    investigation_needs_refresh = (
        graph.get("nodes") != required_investigation_nodes
        or len(checkpoints) != len(required_investigation_nodes)
        or nested_get(graph, ["resume", "supported"]) is not True
        or nested_get(graph, ["failure_recovery", "supported"]) is not True
        or investigation_policy.get("human_approval_before_mutation") is not True
        or investigation_policy.get("action_execution") is not False
        or investigation_policy.get("host_layer_mutates_stack") is not False
        or safe_int(nested_get(validation_doc, ["summary", "fails"]), 0) != 0
        or not {"request_more_evidence", "validate_evidence", "record_artifact", "brief_reaction_candidate"}.issubset(set(state_by_node))
        or bool(investigation_stack_handoff_bad)
    )
    if investigation_needs_refresh:
        investigation = self_awareness_investigate("latest", write_latest=True)
        loaded["investigate"] = investigation
        graph = investigation.get("graph") if isinstance(investigation.get("graph"), dict) else {}
        checkpoints = investigation.get("checkpoints") if isinstance(investigation.get("checkpoints"), list) else []
        conclusion = investigation.get("conclusion") if isinstance(investigation.get("conclusion"), dict) else {}
        investigation_policy = investigation.get("policy") if isinstance(investigation.get("policy"), dict) else {}
        investigation_states = investigation.get("states") if isinstance(investigation.get("states"), list) else []
        state_by_node = {
            str(row.get("node")): (row.get("state") if isinstance(row.get("state"), dict) else {})
            for row in investigation_states
            if isinstance(row, dict) and row.get("node")
        }
        validation_state = state_by_node.get("validate_evidence", {})
        validation_doc = validation_state.get("validation") if isinstance(validation_state.get("validation"), dict) else {}
        brief_candidate_state = state_by_node.get("brief_reaction_candidate", {})
        brief_safe_next = brief_candidate_state.get("safe_next_action") if isinstance(brief_candidate_state.get("safe_next_action"), dict) else {}
        investigation_stack_handoff = _investigation_stack_handoff_action_map_status()
        investigation_stack_handoff_bad = investigation_stack_handoff.get("bad") if isinstance(investigation_stack_handoff.get("bad"), list) else []
    missing_investigation_nodes = [node for node in required_investigation_nodes if node not in state_by_node]
    langgraph_policy_bad = [
        key for key, expected_value in {
            "human_approval_before_mutation": True,
            "replay_required_before_action": True,
            "failure_recovery_non_mutating": True,
            "action_execution": False,
            "auto_remediation": False,
            "host_layer_mutates_stack": False,
        }.items()
        if investigation_policy.get(key) is not expected_value
    ]
    topology_validation_add(
        checks,
        "fail" if graph.get("nodes") != required_investigation_nodes
        or len(checkpoints) != len(required_investigation_nodes)
        or not conclusion.get("evidence_refs")
        or not graph.get("checkpointer")
        or nested_get(graph, ["resume", "supported"]) is not True
        or nested_get(graph, ["failure_recovery", "supported"]) is not True
        or missing_investigation_nodes
        or safe_int(nested_get(validation_doc, ["summary", "fails"]), 0) != 0
        or brief_safe_next.get("requires_human_approval") is not True
        or brief_safe_next.get("automatic") is not False
        or langgraph_policy_bad
        else "ok",
        "langgraph_investigator_checkpointed",
        "investigator has full checkpointed LangGraph-style loop, evidence validation, resume, recovery, and evidence-cited conclusion",
        {
            "required_nodes": required_investigation_nodes,
            "graph_nodes": graph.get("nodes"),
            "missing_nodes": missing_investigation_nodes,
            "checkpoints": len(checkpoints),
            "graph": graph,
            "validation_summary": validation_doc.get("summary") if isinstance(validation_doc, dict) else None,
            "brief_safe_next": brief_safe_next,
            "policy_bad": langgraph_policy_bad,
            "conclusion_refs": len(conclusion.get("evidence_refs", []) if isinstance(conclusion.get("evidence_refs"), list) else []),
        },
    )
    topology_validation_add(
        checks,
        "fail" if investigation_stack_handoff_bad else "ok",
        "investigation_stack_handoff_action_map",
        "investigation replay states, brief candidate, and semantic conclusion preserve prioritized stack handoff actions with blockers, runbooks, coverage impact, verifier commands, and no stack mutation",
        {
            "summary": investigation_stack_handoff.get("summary"),
            "open_requirement_ids": investigation_stack_handoff.get("open_requirement_ids"),
            "request_action_count": investigation_stack_handoff.get("request_action_count"),
            "request_stack_action_count": investigation_stack_handoff.get("request_stack_action_count"),
            "closure_readiness_summary": investigation_stack_handoff.get("closure_readiness_summary"),
            "closure_readiness_state_preservation": investigation_stack_handoff.get("closure_readiness_state_preservation"),
            "validation_check_ids": investigation_stack_handoff.get("validation_check_ids"),
            "safe_next_action": investigation_stack_handoff.get("safe_next_action"),
            "bad": investigation_stack_handoff_bad,
        },
    )
    replay = loaded.get("replay", {})
    replay_policy = replay.get("policy") if isinstance(replay.get("policy"), dict) else {}
    replay_needs_refresh = (
        not replay.get("ok")
        or safe_int(nested_get(replay, ["summary", "divergences"]), 0) != 0
        or nested_get(replay, ["summary", "node_order"]) != required_investigation_nodes
        or replay.get("expected_node_order") != required_investigation_nodes
        or nested_get(replay, ["conclusion_diff", "changed"]) is not False
        or nested_get(replay, ["resume", "supported"]) is not True
        or nested_get(replay, ["failure_recovery", "supported"]) is not True
        or nested_get(replay, ["stack_handoff_replay", "closure_readiness_replayable"]) is not True
        or (
            safe_int(nested_get(replay, ["summary", "stack_handoff_closure_readiness_packets"]), 0) > 0
            and safe_int(nested_get(replay, ["summary", "stack_handoff_coverage_impact_entries"]), -1)
            != safe_int(nested_get(replay, ["summary", "stack_handoff_closure_readiness_packets"]), 0)
        )
        or (
            safe_int(nested_get(replay, ["summary", "stack_handoff_closure_readiness_packets"]), 0) > 0
            and not nested_get(replay, ["summary", "stack_handoff_blocked_coverage_planes"])
        )
        or replay_policy.get("host_layer_mutates_stack") is not False
        or replay_policy.get("action_execution") is not False
        or replay_policy.get("human_approval_before_mutation") is not True
    )
    if replay_needs_refresh:
        replay = self_awareness_replay(thread_id=str(investigation.get("thread_id") or ""), write_latest=True)
        loaded["replay"] = replay
        replay_policy = replay.get("policy") if isinstance(replay.get("policy"), dict) else {}
    replay_policy_bad = [
        key for key, expected_value in {
            "host_layer_mutates_stack": False,
            "action_execution": False,
            "human_approval_before_mutation": True,
            "replay_required_before_action": True,
            "failure_recovery_non_mutating": True,
        }.items()
        if replay_policy.get(key) is not expected_value
    ]
    topology_validation_add(
        checks,
        "fail" if not replay.get("ok")
        or safe_int(nested_get(replay, ["summary", "divergences"]), 0) != 0
        or nested_get(replay, ["summary", "node_order"]) != required_investigation_nodes
        or replay.get("expected_node_order") != required_investigation_nodes
        or nested_get(replay, ["conclusion_diff", "changed"]) is not False
        or nested_get(replay, ["resume", "supported"]) is not True
        or nested_get(replay, ["failure_recovery", "supported"]) is not True
        or nested_get(replay, ["stack_handoff_replay", "closure_readiness_replayable"]) is not True
        or (
            safe_int(nested_get(replay, ["summary", "stack_handoff_closure_readiness_packets"]), 0) > 0
            and safe_int(nested_get(replay, ["summary", "stack_handoff_coverage_impact_entries"]), -1)
            != safe_int(nested_get(replay, ["summary", "stack_handoff_closure_readiness_packets"]), 0)
        )
        or (
            safe_int(nested_get(replay, ["summary", "stack_handoff_closure_readiness_packets"]), 0) > 0
            and not nested_get(replay, ["summary", "stack_handoff_blocked_coverage_planes"])
        )
        or replay_policy_bad
        else "ok",
        "investigation_replay",
        "latest investigation replays full loop without checkpoint divergence and preserves stack handoff closure-readiness plus coverage impact",
        {
            "summary": replay.get("summary"),
            "expected_node_order": replay.get("expected_node_order"),
            "conclusion_diff": replay.get("conclusion_diff"),
            "stack_handoff_replay": replay.get("stack_handoff_replay"),
            "resume": replay.get("resume"),
            "failure_recovery": replay.get("failure_recovery"),
            "policy_bad": replay_policy_bad,
            "divergences": replay.get("divergences"),
        },
    )
    export_doc = loaded.get("export", {})
    if (
        (
            safe_int(nested_get(export_doc, ["summary", "working_stack_activation_entries"]), 0) > 0
            and (
                safe_int(nested_get(export_doc, ["summary", "working_stack_activation_synthetic_proofs"]), -1)
                != safe_int(nested_get(export_doc, ["summary", "working_stack_activation_entries"]), -2)
                or safe_int(nested_get(export_doc, ["summary", "working_stack_activation_closure_acceptance_packets"]), -1)
                != safe_int(nested_get(export_doc, ["summary", "working_stack_activation_entries"]), -2)
                or safe_int(nested_get(export_doc, ["summary", "working_stack_activation_closure_acceptance_packets_complete"]), -1)
                != safe_int(nested_get(export_doc, ["summary", "working_stack_activation_entries"]), -2)
            )
        )
        or safe_int(nested_get(export_doc, ["summary", "working_stack_activation_smoke_rows"]), -1) != len(working_organs)
        or safe_int(nested_get(export_doc, ["summary", "working_stack_activation_smoke_rows_complete"]), -1) != len(working_organs)
        or safe_int(nested_get(export_doc, ["summary", "stack_organ_use_packets"]), -1) != len(working_organs)
        or safe_int(nested_get(export_doc, ["summary", "stack_organ_use_packets_complete"]), -1) != len(working_organs)
        or nested_get(export_doc, ["summary", "working_stack_activation_smoke_failed_services"])
        or nested_get(export_doc, ["summary", "stack_organ_use_packet_failed_services"])
        or (
            safe_int(nested_get(export_doc, ["summary", "stack_requirement_closure_acceptance_packets_complete"]), -1)
            != safe_int(nested_get(dossier_doc, ["summary", "probes"]), -2)
        )
        or (
            safe_int(nested_get(export_doc, ["summary", "working_stack_link_integrity_rows_complete"]), -1)
            != safe_int(nested_get(coverage_audit_doc, ["summary", "working_stack_link_integrity_rows"]), -2)
        )
        or nested_get(export_doc, ["portable_contract", "body_entity_event_document_map_included"]) is not True
        or nested_get(export_doc, ["portable_contract", "response_entity_event_document_context_included"]) is not True
        or nested_get(export_doc, ["portable_contract", "completion_route_packets_included"]) is not True
        or (
            safe_int(nested_get(export_doc, ["summary", "entity_event_document_body_surfaces"]), -1)
            != safe_int(nested_get(completion_audit_doc, ["entity_event_document_map", "summary", "body_surfaces"]), -2)
        )
        or (
            safe_int(nested_get(export_doc, ["summary", "completion_route_packet_actions"]), -1)
            != safe_int(nested_get(completion_audit_doc, ["completion_route_packets", "summary", "covered_actions"]), -2)
        )
    ):
        export_doc = self_awareness_export(write_latest=True)
        loaded["export"] = export_doc
    export_manifest = export_doc.get("manifest") if isinstance(export_doc.get("manifest"), dict) else {}
    export_artifact_list = export_doc.get("artifact_list") if isinstance(export_doc.get("artifact_list"), list) else []
    export_requirements = export_doc.get("requirements") if isinstance(export_doc.get("requirements"), dict) else {}
    export_stack_handoff = export_doc.get("stack_handoff") if isinstance(export_doc.get("stack_handoff"), dict) else {}
    export_open_requirements = export_stack_handoff.get("open_requirements") if isinstance(export_stack_handoff.get("open_requirements"), list) else []
    export_open_ids = export_stack_handoff.get("open_requirement_ids") if isinstance(export_stack_handoff.get("open_requirement_ids"), list) else []
    export_closed_ids = export_stack_handoff.get("closed_requirement_ids") if isinstance(export_stack_handoff.get("closed_requirement_ids"), list) else []
    export_closure_order = export_stack_handoff.get("closure_order") if isinstance(export_stack_handoff.get("closure_order"), list) else []
    export_closure_order_ids = [
        str(item.get("requirement_id"))
        for item in export_closure_order
        if isinstance(item, dict) and item.get("requirement_id")
    ]
    export_ordered_ids = export_stack_handoff.get("ordered_requirement_ids") if isinstance(export_stack_handoff.get("ordered_requirement_ids"), list) else []
    export_dependency_graph = export_stack_handoff.get("dependency_graph") if isinstance(export_stack_handoff.get("dependency_graph"), dict) else {}
    export_stack_owner_handoff = export_stack_handoff.get("stack_owner_handoff") if isinstance(export_stack_handoff.get("stack_owner_handoff"), dict) else {}
    export_artifact_refs = export_stack_handoff.get("artifact_refs") if isinstance(export_stack_handoff.get("artifact_refs"), dict) else {}
    export_coverage_impacts = export_stack_handoff.get("coverage_impacts") if isinstance(export_stack_handoff.get("coverage_impacts"), list) else []
    export_coverage_impacts_by_requirement = export_stack_handoff.get("coverage_impacts_by_requirement") if isinstance(export_stack_handoff.get("coverage_impacts_by_requirement"), dict) else {}
    export_blocked_coverage_planes = export_stack_handoff.get("blocked_coverage_planes") if isinstance(export_stack_handoff.get("blocked_coverage_planes"), list) else []
    export_verifier_matrix = export_stack_handoff.get("stack_owner_verifier_matrix") if isinstance(export_stack_handoff.get("stack_owner_verifier_matrix"), list) else []
    export_verifier_matrix_by_requirement = export_stack_handoff.get("stack_owner_verifier_matrix_by_requirement") if isinstance(export_stack_handoff.get("stack_owner_verifier_matrix_by_requirement"), dict) else {}
    export_stack_requirement_closure_summary = export_stack_handoff.get("stack_requirement_closure_acceptance_summary") if isinstance(export_stack_handoff.get("stack_requirement_closure_acceptance_summary"), dict) else {}
    export_stack_requirement_closure_packets = export_stack_handoff.get("stack_requirement_closure_acceptance_packets") if isinstance(export_stack_handoff.get("stack_requirement_closure_acceptance_packets"), list) else []
    export_stack_requirement_closure_by_requirement = export_stack_handoff.get("stack_requirement_closure_acceptance_packets_by_requirement") if isinstance(export_stack_handoff.get("stack_requirement_closure_acceptance_packets_by_requirement"), dict) else {}
    export_stack_requirement_closure_matrix = export_stack_handoff.get("stack_requirement_closure_acceptance_matrix") if isinstance(export_stack_handoff.get("stack_requirement_closure_acceptance_matrix"), dict) else {}
    export_activation_dossier = export_stack_handoff.get("working_stack_activation_dossier") if isinstance(export_stack_handoff.get("working_stack_activation_dossier"), dict) else {}
    export_activation_handoff = export_stack_handoff.get("working_stack_activation_handoff") if isinstance(export_stack_handoff.get("working_stack_activation_handoff"), dict) else {}
    export_activation_entries = export_stack_handoff.get("working_stack_activation_entries") if isinstance(export_stack_handoff.get("working_stack_activation_entries"), list) else []
    export_activation_service_ids = export_stack_handoff.get("working_stack_activation_service_ids") if isinstance(export_stack_handoff.get("working_stack_activation_service_ids"), list) else []
    export_activation_handoff_service_ids = export_activation_handoff.get("open_service_ids") if isinstance(export_activation_handoff.get("open_service_ids"), list) else []
    export_activation_summary = export_activation_dossier.get("summary") if isinstance(export_activation_dossier.get("summary"), dict) else {}
    export_activation_proof_summary = export_stack_handoff.get("working_stack_activation_synthetic_proof_summary") if isinstance(export_stack_handoff.get("working_stack_activation_synthetic_proof_summary"), dict) else {}
    export_activation_proofs = export_stack_handoff.get("working_stack_activation_synthetic_proofs") if isinstance(export_stack_handoff.get("working_stack_activation_synthetic_proofs"), list) else []
    export_activation_proofs_by_service = export_stack_handoff.get("working_stack_activation_synthetic_proofs_by_service") if isinstance(export_stack_handoff.get("working_stack_activation_synthetic_proofs_by_service"), dict) else {}
    export_activation_smoke_summary = export_stack_handoff.get("working_stack_activation_smoke_summary") if isinstance(export_stack_handoff.get("working_stack_activation_smoke_summary"), dict) else {}
    export_activation_smoke_rows = export_stack_handoff.get("working_stack_activation_smoke_rows") if isinstance(export_stack_handoff.get("working_stack_activation_smoke_rows"), list) else []
    export_activation_smoke_by_service = export_stack_handoff.get("working_stack_activation_smoke_by_service") if isinstance(export_stack_handoff.get("working_stack_activation_smoke_by_service"), dict) else {}
    export_activation_smoke_compact_by_service = export_stack_handoff.get("working_stack_activation_smoke_compact_by_service") if isinstance(export_stack_handoff.get("working_stack_activation_smoke_compact_by_service"), dict) else {}
    export_stack_organ_use_packet_summary = export_stack_handoff.get("stack_organ_use_packet_summary") if isinstance(export_stack_handoff.get("stack_organ_use_packet_summary"), dict) else {}
    export_stack_organ_use_packets = export_stack_handoff.get("stack_organ_use_packets") if isinstance(export_stack_handoff.get("stack_organ_use_packets"), list) else []
    export_stack_organ_use_packet_by_service = export_stack_handoff.get("stack_organ_use_packet_by_service") if isinstance(export_stack_handoff.get("stack_organ_use_packet_by_service"), dict) else {}
    expected_export_stack_organ_services = {
        str(organ.get("service"))
        for organ in working_organs
        if isinstance(organ, dict) and organ.get("service")
    }
    expected_export_stack_organ_count = len(expected_export_stack_organ_services)
    export_working_stack_link_integrity = export_doc.get("working_stack_link_integrity") if isinstance(export_doc.get("working_stack_link_integrity"), dict) else {}
    export_autolink = export_doc.get("autolink") if isinstance(export_doc.get("autolink"), dict) else {}
    export_entity_event_document_map = export_doc.get("entity_event_document_map") if isinstance(export_doc.get("entity_event_document_map"), dict) else {}
    export_entity_event_document_handoff = export_doc.get("entity_event_document_handoff") if isinstance(export_doc.get("entity_event_document_handoff"), dict) else {}
    export_response_entity_event_document_handoff = export_doc.get("response_entity_event_document_handoff") if isinstance(export_doc.get("response_entity_event_document_handoff"), dict) else {}
    export_completion_route_packets = export_doc.get("completion_route_packets") if isinstance(export_doc.get("completion_route_packets"), dict) else {}
    export_completion_route_packet_handoff = export_doc.get("completion_route_packet_handoff") if isinstance(export_doc.get("completion_route_packet_handoff"), dict) else {}
    export_entity_event_document_bad = self_awareness_entity_event_document_map_issues(
        export_entity_event_document_map,
        expected_stack_organs=len(working_organs),
        expected_machine_bridges=expected_machine_bridges_for_entity_map,
    )
    expected_export_completion_routes_for_packets = safe_int(nested_get(completion_audit_doc, ["completion_route_map", "summary", "routes"]), -1)
    expected_export_completion_routes_for_packets = expected_export_completion_routes_for_packets if expected_export_completion_routes_for_packets >= 0 else None
    expected_export_completion_actions_for_packets = safe_int(nested_get(completion_audit_doc, ["action_backlog", "summary", "actions"]), -1)
    expected_export_completion_actions_for_packets = expected_export_completion_actions_for_packets if expected_export_completion_actions_for_packets >= 0 else None
    export_completion_route_packet_bad = self_awareness_completion_route_packet_issues(
        export_completion_route_packets,
        expected_routes=expected_export_completion_routes_for_packets,
        expected_actions=expected_export_completion_actions_for_packets,
    )
    export_handoff_bad: list[str] = []
    if export_requirements.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_export_requirements_summary_v1":
        export_handoff_bad.append("missing_requirements_summary_schema")
    if export_stack_handoff.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_export_stack_handoff_v1":
        export_handoff_bad.append("missing_stack_handoff_schema")
    if nested_get(export_stack_handoff, ["policy", "host_layer_mutates_stack"]) is not False:
        export_handoff_bad.append("stack_handoff_mutation_policy")
    if nested_get(export_stack_handoff, ["policy", "runbook_candidates_are_handoff_only"]) is not True:
        export_handoff_bad.append("runbook_handoff_policy")
    if nested_get(export_stack_handoff, ["policy", "raw_secrets_included"]) is not False:
        export_handoff_bad.append("raw_secret_policy")
    if not self_awareness_working_stack_link_integrity_matrix_complete(export_working_stack_link_integrity):
        export_handoff_bad.append("working_stack_link_integrity_matrix")
    if nested_get(export_doc, ["portable_contract", "working_stack_link_integrity_included"]) is not True:
        export_handoff_bad.append("working_stack_link_integrity_portable_contract")
    if safe_int(nested_get(export_doc, ["summary", "working_stack_link_integrity_rows_complete"]), -1) != safe_int(nested_get(export_doc, ["summary", "working_stack_link_integrity_rows"]), -2):
        export_handoff_bad.append("working_stack_link_integrity_summary")
    if not self_awareness_autolink_complete(export_autolink):
        export_handoff_bad.append("autolink")
    if nested_get(export_doc, ["portable_contract", "autolink_included"]) is not True:
        export_handoff_bad.append("autolink_portable_contract")
    if safe_int(nested_get(export_doc, ["summary", "autolink_organ_links_complete"]), -1) != safe_int(nested_get(export_doc, ["summary", "autolink_organ_links"]), -2):
        export_handoff_bad.append("autolink_summary")
    if export_entity_event_document_bad:
        export_handoff_bad.append("entity_event_document_map")
    if export_entity_event_document_handoff.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_export_entity_event_document_handoff_v1":
        export_handoff_bad.append("entity_event_document_handoff_schema")
    if export_entity_event_document_handoff.get("complete") is not True:
        export_handoff_bad.append("entity_event_document_handoff_incomplete")
    if nested_get(export_entity_event_document_handoff, ["policy", "host_layer_mutates_stack"]) is not False:
        export_handoff_bad.append("entity_event_document_handoff_policy")
    if nested_get(export_doc, ["portable_contract", "entity_event_document_map_included"]) is not True:
        export_handoff_bad.append("entity_event_document_portable_contract")
    if nested_get(export_doc, ["portable_contract", "response_entity_event_document_context_included"]) is not True:
        export_handoff_bad.append("response_entity_event_document_portable_contract")
    if export_response_entity_event_document_handoff.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_export_response_entity_event_document_handoff_v1":
        export_handoff_bad.append("response_entity_event_document_handoff_schema")
    if export_response_entity_event_document_handoff.get("complete") is not True:
        export_handoff_bad.append("response_entity_event_document_handoff_incomplete")
    if nested_get(export_response_entity_event_document_handoff, ["policy", "host_layer_mutates_stack"]) is not False:
        export_handoff_bad.append("response_entity_event_document_handoff_policy")
    if nested_get(export_doc, ["portable_contract", "stack_organ_entities_included"]) is not True:
        export_handoff_bad.append("stack_organ_entities_portable_contract")
    if nested_get(export_doc, ["portable_contract", "stack_organ_use_packets_included"]) is not True:
        export_handoff_bad.append("stack_organ_use_packet_portable_contract")
    if nested_get(export_doc, ["portable_contract", "machine_bridge_entities_included"]) is not True:
        export_handoff_bad.append("machine_bridge_entities_portable_contract")
    if safe_int(nested_get(export_doc, ["summary", "entity_event_document_body_surfaces"]), -1) != safe_int(nested_get(export_entity_event_document_map, ["summary", "body_surfaces"]), -2):
        export_handoff_bad.append("entity_event_document_summary_mismatch")
    if export_completion_route_packet_bad:
        export_handoff_bad.append("completion_route_packets")
    if export_completion_route_packet_handoff.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_export_completion_route_packet_handoff_v1":
        export_handoff_bad.append("completion_route_packet_handoff_schema")
    if export_completion_route_packet_handoff.get("complete") is not True:
        export_handoff_bad.append("completion_route_packet_handoff_incomplete")
    if nested_get(export_completion_route_packet_handoff, ["policy", "host_layer_mutates_stack"]) is not False:
        export_handoff_bad.append("completion_route_packet_handoff_policy")
    if nested_get(export_doc, ["portable_contract", "completion_route_packets_included"]) is not True:
        export_handoff_bad.append("completion_route_packet_portable_contract")
    if safe_int(nested_get(export_doc, ["summary", "completion_route_packet_actions"]), -1) != safe_int(nested_get(export_completion_route_packets, ["summary", "covered_actions"]), -2):
        export_handoff_bad.append("completion_route_packet_summary_mismatch")
    if safe_int(nested_get(export_stack_handoff, ["summary", "open"]), -1) != len(export_open_requirements):
        export_handoff_bad.append("open_count_mismatch")
    if set(str(item) for item in export_open_ids) != {str(item.get("id")) for item in export_open_requirements if isinstance(item, dict)}:
        export_handoff_bad.append("open_id_mismatch")
    if safe_int(nested_get(export_requirements, ["summary", "open_stack_requirements"]), -1) != len(export_open_requirements):
        export_handoff_bad.append("requirements_open_count_mismatch")
    if safe_int(nested_get(export_stack_handoff, ["summary", "stack_owned_requirements"]), -1) != safe_int(nested_get(loaded.get("requirements", {}), ["summary", "stack_owned"]), -1):
        export_handoff_bad.append("stack_owned_count_mismatch")
    if safe_int(nested_get(export_stack_handoff, ["summary", "open"]), -1) != safe_int(nested_get(loaded.get("requirement_probes", {}), ["summary", "open"]), -1):
        export_handoff_bad.append("probe_open_count_mismatch")
    export_closure_readiness = export_stack_handoff.get("closure_readiness") if isinstance(export_stack_handoff.get("closure_readiness"), list) else []
    if safe_int(nested_get(export_stack_handoff, ["summary", "closure_readiness_packets"]), -1) != len(export_closure_readiness):
        export_handoff_bad.append("closure_readiness_count_mismatch")
    if safe_int(nested_get(export_stack_handoff, ["summary", "closure_readiness_packets"]), -1) != len(export_open_requirements) + len(export_stack_handoff.get("closed_requirements") if isinstance(export_stack_handoff.get("closed_requirements"), list) else []):
        export_handoff_bad.append("closure_readiness_entry_count_mismatch")
    expected_stack_requirement_entries = len(export_open_requirements) + len(export_stack_handoff.get("closed_requirements") if isinstance(export_stack_handoff.get("closed_requirements"), list) else [])
    if safe_int(nested_get(export_stack_handoff, ["summary", "stack_requirement_closure_acceptance_packets"]), -1) != expected_stack_requirement_entries:
        export_handoff_bad.append("stack_requirement_closure_acceptance_count_mismatch")
    if safe_int(nested_get(export_stack_handoff, ["summary", "stack_requirement_closure_acceptance_packets_complete"]), -1) != expected_stack_requirement_entries:
        export_handoff_bad.append("stack_requirement_closure_acceptance_complete_count_mismatch")
    if safe_int(nested_get(export_stack_handoff, ["summary", "stack_requirement_compat_requirements"]), -1) != expected_stack_requirement_entries:
        export_handoff_bad.append("stack_requirement_compat_requirement_count_mismatch")
    if export_stack_requirement_closure_summary.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_export_stack_requirement_closure_acceptance_summary_v1":
        export_handoff_bad.append("stack_requirement_closure_acceptance_summary_schema")
    if nested_get(export_stack_requirement_closure_summary, ["policy", "host_layer_mutates_stack"]) is not False:
        export_handoff_bad.append("stack_requirement_closure_acceptance_summary_policy")
    if export_stack_requirement_closure_matrix and export_stack_requirement_closure_matrix.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_stack_requirement_closure_acceptance_matrix_v1":
        export_handoff_bad.append("stack_requirement_closure_acceptance_matrix_schema")
    if safe_int(export_stack_requirement_closure_summary.get("packets"), -1) != len(export_stack_requirement_closure_packets):
        export_handoff_bad.append("stack_requirement_closure_acceptance_packet_list_mismatch")
    if set(str(item.get("requirement_id")) for item in export_stack_requirement_closure_packets if isinstance(item, dict) and item.get("requirement_id")) != set(str(item) for item in export_stack_requirement_closure_by_requirement):
        export_handoff_bad.append("stack_requirement_closure_acceptance_index_mismatch")
    for packet in export_stack_requirement_closure_packets:
        if not isinstance(packet, dict):
            export_handoff_bad.append("malformed_stack_requirement_closure_acceptance")
            continue
        requirement_id = str(packet.get("requirement_id") or "unknown")
        if not self_awareness_stack_requirement_closure_acceptance_complete(packet):
            export_handoff_bad.append(f"{requirement_id}:stack_requirement_closure_acceptance")
        if nested_get(packet, ["stack_compat_requirement", "owner"]) != "abyss-stack":
            export_handoff_bad.append(f"{requirement_id}:stack_requirement_closure_acceptance_owner")
        if nested_get(packet, ["policy", "host_layer_mutates_stack"]) is not False:
            export_handoff_bad.append(f"{requirement_id}:stack_requirement_closure_acceptance_policy")
    if export_stack_owner_handoff.get("closure_acceptance_summary") != export_stack_requirement_closure_summary:
        export_handoff_bad.append("stack_owner_handoff_closure_acceptance_summary_mismatch")
    if export_stack_owner_handoff.get("closure_acceptance_packets_by_requirement") != export_stack_requirement_closure_by_requirement:
        export_handoff_bad.append("stack_owner_handoff_closure_acceptance_index_mismatch")
    if not export_artifact_refs or not {"requirements", "requirement_probes", "coverage_audit", "working_stack"}.issubset(set(export_artifact_refs)):
        export_handoff_bad.append("missing_handoff_artifact_refs")
    if export_stack_handoff.get("coverage_audit_ref") != export_artifact_refs.get("coverage_audit"):
        export_handoff_bad.append("coverage_audit_ref_mismatch")
    if export_activation_dossier.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_working_stack_activation_dossier_v1":
        export_handoff_bad.append("working_stack_activation_dossier_schema")
    if nested_get(export_activation_dossier, ["policy", "host_layer_mutates_stack"]) is not False or nested_get(export_activation_dossier, ["policy", "executes_commands"]) is not False:
        export_handoff_bad.append("working_stack_activation_dossier_policy")
    if nested_get(export_activation_handoff, ["policy", "host_layer_mutates_stack"]) is not False or nested_get(export_activation_handoff, ["policy", "abyss_machine_executes_stack_change"]) is not False:
        export_handoff_bad.append("working_stack_activation_handoff_policy")
    if safe_int(nested_get(export_stack_handoff, ["summary", "working_stack_activation_entries"]), -1) != len(export_activation_entries):
        export_handoff_bad.append("working_stack_activation_entry_count_mismatch")
    if safe_int(export_activation_summary.get("activation_entries_complete"), -1) != len(export_activation_entries):
        export_handoff_bad.append("working_stack_activation_complete_count_mismatch")
    if safe_int(export_activation_summary.get("synthetic_scenarios"), -1) != len(export_activation_entries):
        export_handoff_bad.append("working_stack_activation_scenario_count_mismatch")
    if safe_int(export_activation_summary.get("synthetic_scenarios_complete"), -1) != len(export_activation_entries):
        export_handoff_bad.append("working_stack_activation_scenario_complete_count_mismatch")
    if safe_int(export_activation_summary.get("closure_acceptance_packets"), -1) != len(export_activation_entries):
        export_handoff_bad.append("working_stack_activation_closure_acceptance_count_mismatch")
    if safe_int(export_activation_summary.get("closure_acceptance_packets_complete"), -1) != len(export_activation_entries):
        export_handoff_bad.append("working_stack_activation_closure_acceptance_complete_count_mismatch")
    if safe_int(export_activation_summary.get("activation_compat_requirements"), -1) != len(export_activation_entries):
        export_handoff_bad.append("working_stack_activation_compat_requirement_count_mismatch")
    if export_activation_entries and export_activation_proof_summary.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_export_working_stack_activation_synthetic_proof_summary_v1":
        export_handoff_bad.append("working_stack_activation_proof_summary_schema")
    if export_activation_entries and nested_get(export_activation_proof_summary, ["policy", "host_layer_mutates_stack"]) is not False:
        export_handoff_bad.append("working_stack_activation_proof_summary_policy")
    if export_activation_entries and safe_int(nested_get(export_stack_handoff, ["summary", "working_stack_activation_synthetic_proofs"]), -1) != len(export_activation_entries):
        export_handoff_bad.append("working_stack_activation_proof_count_mismatch")
    if export_activation_entries and safe_int(nested_get(export_stack_handoff, ["summary", "working_stack_activation_synthetic_proofs_complete"]), -1) != len(export_activation_entries):
        export_handoff_bad.append("working_stack_activation_proof_complete_count_mismatch")
    if export_activation_entries and safe_int(export_activation_proof_summary.get("proofs"), -1) != len(export_activation_entries):
        export_handoff_bad.append("working_stack_activation_proof_summary_count_mismatch")
    if export_activation_entries and safe_int(export_activation_proof_summary.get("proofs_complete"), -1) != len(export_activation_entries):
        export_handoff_bad.append("working_stack_activation_proof_summary_complete_count_mismatch")
    if set(str(item) for item in export_activation_proofs_by_service) != set(str(item) for item in export_activation_service_ids):
        export_handoff_bad.append("working_stack_activation_proof_service_index_mismatch")
    if expected_export_stack_organ_count > 0 and export_activation_smoke_summary.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_export_working_stack_activation_smoke_summary_v1":
        export_handoff_bad.append("working_stack_activation_smoke_summary_schema")
    if expected_export_stack_organ_count > 0 and nested_get(export_activation_smoke_summary, ["policy", "host_layer_mutates_stack"]) is not False:
        export_handoff_bad.append("working_stack_activation_smoke_summary_policy")
    if safe_int(nested_get(export_stack_handoff, ["summary", "working_stack_activation_smoke_rows"]), -1) != expected_export_stack_organ_count:
        export_handoff_bad.append("working_stack_activation_smoke_count_mismatch")
    if safe_int(nested_get(export_stack_handoff, ["summary", "working_stack_activation_smoke_rows_complete"]), -1) != expected_export_stack_organ_count:
        export_handoff_bad.append("working_stack_activation_smoke_complete_count_mismatch")
    if safe_int(export_activation_smoke_summary.get("rows"), -1) != expected_export_stack_organ_count:
        export_handoff_bad.append("working_stack_activation_smoke_summary_count_mismatch")
    if safe_int(export_activation_smoke_summary.get("rows_complete"), -1) != expected_export_stack_organ_count:
        export_handoff_bad.append("working_stack_activation_smoke_summary_complete_count_mismatch")
    if export_activation_smoke_summary.get("failed_services"):
        export_handoff_bad.append("working_stack_activation_smoke_summary_failed_services")
    if set(str(item) for item in export_activation_smoke_by_service) != expected_export_stack_organ_services:
        export_handoff_bad.append("working_stack_activation_smoke_service_index_mismatch")
    if set(str(item) for item in export_activation_smoke_compact_by_service) != expected_export_stack_organ_services:
        export_handoff_bad.append("working_stack_activation_smoke_compact_index_mismatch")
    if expected_export_stack_organ_count > 0 and export_stack_organ_use_packet_summary.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_export_stack_organ_use_packet_summary_v1":
        export_handoff_bad.append("stack_organ_use_packet_summary_schema")
    if expected_export_stack_organ_count > 0 and nested_get(export_stack_organ_use_packet_summary, ["policy", "host_layer_mutates_stack"]) is not False:
        export_handoff_bad.append("stack_organ_use_packet_summary_policy")
    if safe_int(nested_get(export_stack_handoff, ["summary", "stack_organ_use_packets"]), -1) != expected_export_stack_organ_count:
        export_handoff_bad.append("stack_organ_use_packet_count_mismatch")
    if safe_int(nested_get(export_stack_handoff, ["summary", "stack_organ_use_packets_complete"]), -1) != expected_export_stack_organ_count:
        export_handoff_bad.append("stack_organ_use_packet_complete_count_mismatch")
    if safe_int(export_stack_organ_use_packet_summary.get("packets"), -1) != expected_export_stack_organ_count:
        export_handoff_bad.append("stack_organ_use_packet_summary_count_mismatch")
    if safe_int(export_stack_organ_use_packet_summary.get("packets_complete"), -1) != expected_export_stack_organ_count:
        export_handoff_bad.append("stack_organ_use_packet_summary_complete_count_mismatch")
    if export_stack_organ_use_packet_summary.get("failed_services"):
        export_handoff_bad.append("stack_organ_use_packet_summary_failed_services")
    if set(str(item) for item in export_stack_organ_use_packet_by_service) != expected_export_stack_organ_services:
        export_handoff_bad.append("stack_organ_use_packet_service_index_mismatch")
    if {str(packet.get("service")) for packet in export_stack_organ_use_packets if isinstance(packet, dict) and packet.get("service")} != expected_export_stack_organ_services:
        export_handoff_bad.append("stack_organ_use_packet_service_list_mismatch")
    if set(str(item) for item in export_activation_service_ids) != {str(item.get("service")) for item in export_activation_entries if isinstance(item, dict) and item.get("service")}:
        export_handoff_bad.append("working_stack_activation_service_id_mismatch")
    if set(str(item) for item in export_activation_handoff_service_ids if item) != set(str(item) for item in export_activation_service_ids):
        export_handoff_bad.append("working_stack_activation_handoff_service_mismatch")
    for entry in export_activation_entries:
        if not isinstance(entry, dict):
            export_handoff_bad.append("malformed_working_stack_activation_entry")
            continue
        service = str(entry.get("service") or "unknown")
        if not self_awareness_working_stack_activation_entry_complete(entry):
            export_handoff_bad.append(f"{service}:working_stack_activation_incomplete")
        closure_acceptance = entry.get("closure_acceptance") if isinstance(entry.get("closure_acceptance"), dict) else {}
        if not self_awareness_working_stack_activation_closure_acceptance_complete(closure_acceptance):
            export_handoff_bad.append(f"{service}:working_stack_activation_closure_acceptance")
        if closure_acceptance and (
            closure_acceptance.get("machine_usage_status") != entry.get("machine_usage_status")
            or closure_acceptance.get("working_stack_link_id") != entry.get("working_stack_link_id")
        ):
            export_handoff_bad.append(f"{service}:working_stack_activation_closure_acceptance_identity")
        if closure_acceptance and nested_get(closure_acceptance, ["stack_compat_requirement", "owner"]) != "abyss-stack":
            export_handoff_bad.append(f"{service}:working_stack_activation_closure_acceptance_owner")
        if closure_acceptance and nested_get(closure_acceptance, ["policy", "host_layer_mutates_stack"]) is not False:
            export_handoff_bad.append(f"{service}:working_stack_activation_closure_acceptance_policy")
        if not self_awareness_working_stack_activation_synthetic_scenario_complete(entry.get("synthetic_scenario")):
            export_handoff_bad.append(f"{service}:working_stack_activation_synthetic_scenario")
        proof = export_activation_proofs_by_service.get(service) if isinstance(export_activation_proofs_by_service.get(service), dict) else {}
        if not self_awareness_working_stack_activation_synthetic_proof_complete(proof):
            export_handoff_bad.append(f"{service}:working_stack_activation_synthetic_proof")
        if proof.get("machine_usage_status") != entry.get("machine_usage_status") or proof.get("working_stack_link_id") != entry.get("working_stack_link_id"):
            export_handoff_bad.append(f"{service}:working_stack_activation_synthetic_proof_identity")
        smoke_row = export_activation_smoke_by_service.get(service) if isinstance(export_activation_smoke_by_service.get(service), dict) else {}
        smoke_compact = export_activation_smoke_compact_by_service.get(service) if isinstance(export_activation_smoke_compact_by_service.get(service), dict) else {}
        if not self_awareness_working_stack_activation_smoke_row_complete(smoke_row):
            export_handoff_bad.append(f"{service}:working_stack_activation_smoke")
        if smoke_row and (smoke_row.get("machine_usage_status") != entry.get("machine_usage_status") or smoke_row.get("working_stack_link_id") != entry.get("working_stack_link_id")):
            export_handoff_bad.append(f"{service}:working_stack_activation_smoke_identity")
        if not smoke_compact or smoke_compact.get("complete") is not True or smoke_compact.get("service") != service:
            export_handoff_bad.append(f"{service}:working_stack_activation_smoke_compact")
        organ_use_packet = export_stack_organ_use_packet_by_service.get(service) if isinstance(export_stack_organ_use_packet_by_service.get(service), dict) else {}
        if not self_awareness_stack_organ_use_packet_complete(organ_use_packet):
            export_handoff_bad.append(f"{service}:stack_organ_use_packet")
        if organ_use_packet and (
            organ_use_packet.get("service") != service
            or nested_get(organ_use_packet, ["event", "machine_usage_status"]) != entry.get("machine_usage_status")
            or nested_get(organ_use_packet, ["event", "working_stack_link_id"]) != entry.get("working_stack_link_id")
        ):
            export_handoff_bad.append(f"{service}:stack_organ_use_packet_identity")
        if organ_use_packet and nested_get(organ_use_packet, ["policy", "host_layer_mutates_stack"]) is not False:
            export_handoff_bad.append(f"{service}:stack_organ_use_packet_policy")
        if nested_get(entry, ["safe_next_action", "host_layer_mutates_stack"]) is not False or nested_get(entry, ["safe_next_action", "executes_commands"]) is not False:
            export_handoff_bad.append(f"{service}:working_stack_activation_safe_next")
        if not entry.get("missing_checks") or not entry.get("runbook_candidate"):
            export_handoff_bad.append(f"{service}:working_stack_activation_depth")
    if export_open_requirements and not export_coverage_impacts:
        export_handoff_bad.append("coverage_impacts_missing")
    if export_open_requirements and not export_blocked_coverage_planes:
        export_handoff_bad.append("blocked_coverage_planes_missing")
    if safe_int(nested_get(export_stack_handoff, ["summary", "coverage_impact_entries"]), -1) != len(export_coverage_impacts):
        export_handoff_bad.append("coverage_impact_count_mismatch")
    if nested_get(export_stack_handoff, ["summary", "blocked_coverage_planes"]) != export_blocked_coverage_planes:
        export_handoff_bad.append("blocked_coverage_planes_summary_mismatch")
    impact_requirement_ids = {
        str(impact.get("requirement_id"))
        for impact in export_coverage_impacts
        if isinstance(impact, dict) and impact.get("requirement_id")
    }
    if set(str(item) for item in export_open_ids) != impact_requirement_ids:
        export_handoff_bad.append("coverage_impact_open_ids_mismatch")
    if set(str(item) for item in export_open_ids) != set(str(item) for item in export_coverage_impacts_by_requirement):
        export_handoff_bad.append("coverage_impact_index_open_ids_mismatch")
    if export_stack_owner_handoff.get("coverage_impacts_by_requirement") != export_coverage_impacts_by_requirement:
        export_handoff_bad.append("stack_owner_coverage_impact_index_mismatch")
    if export_stack_owner_handoff.get("blocked_coverage_planes") != export_blocked_coverage_planes:
        export_handoff_bad.append("stack_owner_blocked_coverage_planes_mismatch")
    for impact in export_coverage_impacts:
        if not self_awareness_stack_coverage_impact_complete(impact):
            export_handoff_bad.append(f"{impact.get('requirement_id')}:coverage_impact")
        if nested_get(impact, ["policy", "host_layer_mutates_stack"]) is not False:
            export_handoff_bad.append(f"{impact.get('requirement_id')}:coverage_impact_mutation_policy")
    if export_open_requirements and not export_verifier_matrix:
        export_handoff_bad.append("stack_owner_verifier_matrix_missing")
    if safe_int(nested_get(export_stack_handoff, ["summary", "stack_owner_verifier_matrix_entries"]), -1) != len(export_verifier_matrix):
        export_handoff_bad.append("stack_owner_verifier_matrix_count_mismatch")
    verifier_matrix_ids = {
        str(item.get("requirement_id"))
        for item in export_verifier_matrix
        if isinstance(item, dict) and item.get("requirement_id")
    }
    if set(str(item) for item in export_open_ids) != verifier_matrix_ids:
        export_handoff_bad.append("stack_owner_verifier_matrix_open_ids_mismatch")
    if set(str(item) for item in export_open_ids) != set(str(item) for item in export_verifier_matrix_by_requirement):
        export_handoff_bad.append("stack_owner_verifier_matrix_index_open_ids_mismatch")
    if export_stack_owner_handoff.get("verifier_matrix") != export_verifier_matrix:
        export_handoff_bad.append("stack_owner_handoff_verifier_matrix_mismatch")
    if export_stack_owner_handoff.get("verifier_matrix_by_requirement") != export_verifier_matrix_by_requirement:
        export_handoff_bad.append("stack_owner_handoff_verifier_matrix_index_mismatch")
    for item in export_verifier_matrix:
        if not isinstance(item, dict):
            export_handoff_bad.append("malformed_stack_owner_verifier_matrix_entry")
            continue
        requirement_id = item.get("requirement_id")
        if item.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_export_stack_owner_verifier_v1":
            export_handoff_bad.append(f"{requirement_id}:verifier_matrix_schema")
        if item.get("owner") != "abyss-stack":
            export_handoff_bad.append(f"{requirement_id}:verifier_matrix_owner")
        if not item.get("blocking_check_keys"):
            export_handoff_bad.append(f"{requirement_id}:verifier_matrix_blocking_keys")
        if not item.get("verifier_commands"):
            export_handoff_bad.append(f"{requirement_id}:verifier_matrix_commands")
        if not item.get("acceptance_verifiers"):
            export_handoff_bad.append(f"{requirement_id}:verifier_matrix_acceptance")
        if not item.get("post_close_verifiers"):
            export_handoff_bad.append(f"{requirement_id}:verifier_matrix_post_close")
        if not item.get("coverage_planes"):
            export_handoff_bad.append(f"{requirement_id}:verifier_matrix_coverage_planes")
        if nested_get(item, ["policy", "host_layer_mutates_stack"]) is not False or nested_get(item, ["policy", "executes_commands"]) is not False:
            export_handoff_bad.append(f"{requirement_id}:verifier_matrix_policy")
    if set(str(item) for item in export_requirements.get("open_stack_ids", [])) != set(str(item) for item in export_open_ids):
        export_handoff_bad.append("requirements_open_ids_mismatch")
    if not isinstance(export_closed_ids, list):
        export_handoff_bad.append("closed_ids_not_list")
    if export_open_requirements and not export_closure_order:
        export_handoff_bad.append("closure_order_missing")
    if export_closure_order and safe_int(nested_get(export_stack_handoff, ["summary", "closure_order_entries"]), -1) != len(export_closure_order):
        export_handoff_bad.append("closure_order_summary_mismatch")
    if export_closure_order and [str(item) for item in export_ordered_ids] != export_closure_order_ids:
        export_handoff_bad.append("ordered_ids_mismatch")
    if export_closure_order and set(export_closure_order_ids) != set(str(item) for item in export_open_ids):
        export_handoff_bad.append("closure_order_open_ids_mismatch")
    if export_closure_order and nested_get(export_stack_handoff, ["summary", "top_requirement_id"]) != export_closure_order_ids[0]:
        export_handoff_bad.append("closure_order_top_mismatch")
    if export_closure_order and export_stack_owner_handoff.get("closure_order_ids") != export_ordered_ids:
        export_handoff_bad.append("stack_owner_handoff_order_mismatch")
    if export_closure_order and nested_get(export_stack_owner_handoff, ["policy", "abyss_machine_executes_stack_change"]) is not False:
        export_handoff_bad.append("stack_owner_handoff_execution_policy")
    if export_closure_order and nested_get(export_stack_owner_handoff, ["policy", "host_layer_mutates_stack"]) is not False:
        export_handoff_bad.append("stack_owner_handoff_mutation_policy")
    if export_closure_order and nested_get(export_dependency_graph, ["policy", "host_layer_mutates_stack"]) is not False:
        export_handoff_bad.append("dependency_graph_mutation_policy")
    if export_closure_order and nested_get(export_dependency_graph, ["policy", "executes_commands"]) is not False:
        export_handoff_bad.append("dependency_graph_exec_policy")
    dependency_ordered_ids = export_dependency_graph.get("ordered_requirement_ids") if isinstance(export_dependency_graph.get("ordered_requirement_ids"), list) else []
    dependency_open_ids = export_dependency_graph.get("open_requirement_ids") if isinstance(export_dependency_graph.get("open_requirement_ids"), list) else []
    if export_closure_order and [str(item) for item in dependency_ordered_ids] != export_closure_order_ids:
        export_handoff_bad.append("dependency_order_mismatch")
    if export_closure_order and set(str(item) for item in dependency_open_ids) != set(str(item) for item in export_open_ids):
        export_handoff_bad.append("dependency_open_ids_mismatch")
    if "stack.trace-backend" in export_closure_order_ids and "stack.langchain-api.graph-observability" in export_closure_order_ids:
        if export_closure_order_ids.index("stack.trace-backend") > export_closure_order_ids.index("stack.langchain-api.graph-observability"):
            export_handoff_bad.append("trace_backend_not_before_langgraph")
        dependency_edges = export_dependency_graph.get("edges") if isinstance(export_dependency_graph.get("edges"), list) else []
        has_trace_langgraph_edge = any(
            isinstance(edge, dict)
            and edge.get("from") == "stack.langchain-api.graph-observability"
            and edge.get("to") == "stack.trace-backend"
            for edge in dependency_edges
        )
        if not has_trace_langgraph_edge:
            export_handoff_bad.append("missing_trace_langgraph_dependency_edge")
    for entry in export_open_requirements:
        if not isinstance(entry, dict):
            export_handoff_bad.append("malformed_open_requirement")
            continue
        if entry.get("owner") != "abyss-stack":
            export_handoff_bad.append(f"{entry.get('id')}:owner")
        if entry.get("closed_by_current_probe") is True:
            export_handoff_bad.append(f"{entry.get('id')}:closed_in_open")
        if not entry.get("closure_blockers"):
            export_handoff_bad.append(f"{entry.get('id')}:missing_closure_blockers")
        if not entry.get("acceptance_verifiers"):
            export_handoff_bad.append(f"{entry.get('id')}:missing_acceptance_verifiers")
        readiness = entry.get("closure_readiness") if isinstance(entry.get("closure_readiness"), dict) else {}
        if readiness.get("schema") != f"{SCHEMA_PREFIX}_stack_handoff_closure_readiness_v1":
            export_handoff_bad.append(f"{entry.get('id')}:missing_closure_readiness")
        if readiness.get("requirement_id") != entry.get("id"):
            export_handoff_bad.append(f"{entry.get('id')}:closure_readiness_identity")
        if nested_get(readiness, ["policy", "host_layer_mutates_stack"]) is not False or nested_get(readiness, ["policy", "executes_commands"]) is not False:
            export_handoff_bad.append(f"{entry.get('id')}:closure_readiness_policy")
        runbook = entry.get("runbook_candidate") if isinstance(entry.get("runbook_candidate"), dict) else {}
        if runbook.get("machine_executes_stack_change") is not False or runbook.get("host_layer_mutates_stack") is not False:
            export_handoff_bad.append(f"{entry.get('id')}:runbook_mutation_policy")
        if not runbook.get("acceptance_steps") or not runbook.get("rollback"):
            export_handoff_bad.append(f"{entry.get('id')}:runbook_incomplete")
        closure_acceptance = entry.get("closure_acceptance") if isinstance(entry.get("closure_acceptance"), dict) else {}
        if not self_awareness_stack_requirement_closure_acceptance_complete(closure_acceptance):
            export_handoff_bad.append(f"{entry.get('id')}:closure_acceptance")
        if closure_acceptance and closure_acceptance.get("requirement_id") != entry.get("id"):
            export_handoff_bad.append(f"{entry.get('id')}:closure_acceptance_identity")
        if closure_acceptance and nested_get(closure_acceptance, ["policy", "host_layer_mutates_stack"]) is not False:
            export_handoff_bad.append(f"{entry.get('id')}:closure_acceptance_policy")
    bad_export_artifacts = [
        item.get("name") for item in export_artifact_list
        if not isinstance(item, dict)
        or not item.get("name")
        or not item.get("path")
        or not item.get("history_path")
        or item.get("exists") is not True
        or item.get("schema_ok") is not True
        or not item.get("sha256")
        or not isinstance(item.get("evidence_ref"), dict)
    ]
    topology_validation_add(
        checks,
        "fail" if not export_doc.get("ok")
        or safe_int(nested_get(export_doc, ["summary", "missing"]), 0) != 0
        or safe_int(nested_get(export_doc, ["summary", "malformed"]), 0) != 0
        or not export_manifest.get("manifest_digest")
        or safe_int(export_manifest.get("artifact_count"), 0) != len(export_artifact_list)
        or bad_export_artifacts
        or export_handoff_bad
        or nested_get(export_doc, ["policy", "host_layer_mutates_stack"]) is not False
        else "ok",
        "self_awareness_export",
        "export bundle exposes every self-awareness artifact plus portable stack handoff with blockers, runbooks, verifier steps, and no stack mutation",
        {
            "summary": export_doc.get("summary"),
            "missing": export_doc.get("missing"),
            "malformed": export_doc.get("malformed"),
            "manifest": export_manifest,
            "bad_artifacts": bad_export_artifacts,
            "handoff_bad": export_handoff_bad,
            "requirements": export_requirements,
            "stack_handoff_summary": export_stack_handoff.get("summary") if isinstance(export_stack_handoff, dict) else None,
            "working_stack_activation_summary": export_activation_summary,
            "working_stack_activation_service_ids": export_activation_service_ids,
            "entity_event_document_summary": export_entity_event_document_map.get("summary") if isinstance(export_entity_event_document_map, dict) else None,
            "entity_event_document_handoff": export_entity_event_document_handoff,
            "entity_event_document_bad": export_entity_event_document_bad,
            "completion_route_packet_summary": export_completion_route_packets.get("summary") if isinstance(export_completion_route_packets, dict) else None,
            "completion_route_packet_handoff": export_completion_route_packet_handoff,
            "completion_route_packet_bad": export_completion_route_packet_bad,
        },
    )
    for test_check in self_awareness_self_tests():
        checks.append(test_check)
    data = self_awareness_validate_document_from_checks(
        checks,
        strict=strict,
        paths=self_awareness_paths(),
        summary_extra={
            "events": len(events),
            "probe_run_id": probe.get("run_id"),
        },
    )
    return data

from __future__ import annotations

from typing import Any

import pytest

from conftest import parse_json_stdout


pytestmark = [pytest.mark.live, pytest.mark.contract]


PROTECTED_STACK_ROOTS = (
    "/srv/AbyssOS",
    "/srv/abyss-stack",
    "/home/dionysus/src/abyss-stack",
)

FORBIDDEN_LOKI_LABELS = {
    "trace_id",
    "traceid",
    "traceparent",
    "span_id",
    "spanid",
    "request_id",
    "requestid",
    "session_id",
    "sessionid",
    "task_id",
    "taskid",
}


LANGGRAPH_INVESTIGATION_NODE_ORDER = [
    "plan_queries",
    "query_evidence",
    "resident_context_packet",
    "reason_over_evidence",
    "request_more_evidence",
    "validate_evidence",
    "record_artifact",
    "brief_reaction_candidate",
    "write_semantic_conclusion",
]


def _run_json(run_abyss_machine: Any, *args: str, timeout: float = 90.0) -> dict[str, Any]:
    result = run_abyss_machine(*args, timeout=timeout)
    assert result.returncode == 0, result.stderr[-1000:]
    return parse_json_stdout(result)


def _assert_no_stack_mutation_policy(payload: dict[str, Any]) -> None:
    policy = payload.get("policy", {})
    owner_boundary = payload.get("owner_boundary", {})

    assert policy.get("host_layer_mutates_stack") is not True
    assert owner_boundary.get("host_layer_mutates_stack") is not True
    assert policy.get("writes_project_roots") is not True
    assert owner_boundary.get("writes_project_roots") is not True


def _assert_evidence_refs(refs: Any) -> None:
    assert isinstance(refs, list)
    assert refs
    for ref in refs:
        assert isinstance(ref, dict)
        assert any(key in ref for key in ("path", "url", "schema", "step", "fixture", "python_module"))
        path = str(ref.get("path", ""))
        assert not any(path.startswith(root) for root in PROTECTED_STACK_ROOTS)


def test_live_stack_observability_is_readonly_and_correlated(run_abyss_machine) -> None:
    payload = _run_json(run_abyss_machine, "stack-bridge", "observability", "--json", timeout=90.0)

    assert payload["schema"] == "abyss_machine_stack_observability_v1"
    assert payload["ok"] is True
    assert payload["status"] in {"ready", "watch"}
    assert payload["owner_boundary"]["machine_role"] == "read_only_consumer"
    assert payload["owner_boundary"]["stack_owner"] == "abyss-stack"
    _assert_no_stack_mutation_policy(payload)

    summary = payload.get("summary", {})
    assert summary.get("required_failures") == []
    assert {"alloy", "grafana", "loki", "prometheus"}.issubset(set(summary.get("promql_jobs_up", [])))
    assert summary.get("logql_queries_ok", 0) >= 1
    assert summary.get("logql_entries_seen", 0) >= summary.get("logql_queries_ok", 0)

    endpoints = payload.get("endpoints", {})
    assert endpoints.get("prometheus_host", "").startswith("http://127.0.0.1:")
    assert endpoints.get("grafana_host", "").startswith("http://127.0.0.1:")
    assert endpoints.get("loki_internal", "").startswith("http://")

    containers = payload.get("containers", {})
    assert containers.get("ok") is True
    assert containers.get("missing_required") == []
    assert containers.get("not_running_required") == []
    for name in ("prometheus", "grafana", "loki", "alloy"):
        item = containers.get("expected", {}).get(name, {})
        assert item.get("present") is True
        assert item.get("running") is True

    labels = set(payload.get("loki", {}).get("labels", {}).get("labels", []))
    assert labels
    assert labels.isdisjoint(FORBIDDEN_LOKI_LABELS)

    for query in payload.get("loki", {}).get("logql", []):
        assert query.get("ok") is True
        assert query.get("stream_count", 0) >= 0
        assert query.get("entry_count", 0) >= 0
        for sample in query.get("samples", []):
            assert set(sample.get("labels", {})).isdisjoint(FORBIDDEN_LOKI_LABELS)
            assert "line_preview" in sample
            assert "line_hash" in sample


def test_live_self_awareness_collect_events_have_signal_fabric(run_abyss_machine) -> None:
    payload = _run_json(run_abyss_machine, "self-awareness", "collect", "--json", timeout=120.0)

    assert payload["schema"] == "abyss_machine_self_awareness_collect_v1"
    assert payload["ok"] is True
    _assert_no_stack_mutation_policy(payload)

    events = payload.get("events", [])
    summary = payload.get("summary", {}).get("signal_fabric", {})
    assert events
    assert summary.get("events") == len(events)
    assert summary.get("with_fabric") == len(events)
    assert summary.get("with_actor") == len(events)
    assert summary.get("with_temporal") == len(events)
    assert summary.get("with_spatial") == len(events)
    assert summary.get("with_context_links") == len(events)
    assert summary.get("with_evidence_route") == len(events)
    assert summary.get("with_policy") == len(events)
    assert summary.get("with_thread_or_checkpoint", 0) >= 1
    assert summary.get("forbidden_label_events") == 0

    owner_surfaces = set()
    checkpoint_link_events = 0
    sources = set()
    observability_events = []
    scheduler_events = []
    for event in events:
        fabric = event.get("fabric", {})
        sources.add(event.get("source"))
        if event.get("source") == "observability":
            observability_events.append(event)
        if event.get("source") == "scheduler":
            scheduler_events.append(event)
        owner_surfaces.add(fabric.get("actor", {}).get("owner_surface"))
        if fabric.get("context_links", {}).get("thread_id") or fabric.get("context_links", {}).get("checkpoint_id"):
            checkpoint_link_events += 1
            assert fabric.get("actor", {}).get("owner_surface") == "abyss-machine"
        assert fabric.get("schema") == "abyss_machine_self_awareness_signal_fabric_v1"
        assert fabric.get("actor", {}).get("owner_surface") in {"abyss-stack", "abyss-machine"}
        assert fabric.get("temporal", {}).get("time_bucket")
        assert fabric.get("spatial", {}).get("owner_surface") == fabric.get("actor", {}).get("owner_surface")
        assert fabric.get("context_links", {}).get("correlation_keys")
        assert fabric.get("evidence_route", {}).get("has_refs") is True
        assert fabric.get("policy", {}).get("read_only") is True
        assert fabric.get("policy", {}).get("host_layer_mutates_stack") is False
        assert fabric.get("policy", {}).get("raw_body_stored") is False
        assert fabric.get("label_policy", {}).get("forbidden_context_label_keys") in ([], None)

    assert {"abyss-stack", "abyss-machine"}.issubset(owner_surfaces)
    assert checkpoint_link_events >= 1
    assert "observability" in sources
    assert "scheduler" in sources
    assert observability_events
    for event in observability_events:
        assert event.get("signal") == "metric"
        assert event.get("resource", {}).get("service") == "observability-thermal-battery"
        assert event.get("fabric", {}).get("actor", {}).get("owner_surface") == "abyss-machine"
        assert event.get("fabric", {}).get("spatial", {}).get("owner_surface") == "abyss-machine"
        manual_collect_status = event.get("context", {}).get("manual_collect_status")
        assert manual_collect_status in {"ready", "operator_authorization_required"}
        assert event.get("fabric", {}).get("context_links", {}).get("links", {}).get("manual_collect_status") == manual_collect_status
        assert f"manual_collect_status:{manual_collect_status}" in event.get("fabric", {}).get("context_links", {}).get("correlation_keys", [])
        assert any(
            str(ref.get("path", "")).endswith("/observability/thermal-battery/latest.json")
            for ref in event.get("evidence_refs", [])
            if isinstance(ref, dict)
        )
    assert scheduler_events
    scheduler_units = {event.get("resource", {}).get("service") for event in scheduler_events}
    scheduler_categories = {event.get("resource", {}).get("timer_category") for event in scheduler_events}
    assert "abyss-machine-heartbeat.timer" in scheduler_units
    assert scheduler_categories.intersection({"warm_e2b", "session_memory"})
    for event in scheduler_events:
        assert event.get("signal") == "service"
        assert event.get("fabric", {}).get("actor", {}).get("owner_surface") == "abyss-machine"
        assert event.get("fabric", {}).get("spatial", {}).get("layer") == "host-scheduler"
        assert event.get("fabric", {}).get("policy", {}).get("read_only") is True
        unit = event.get("context", {}).get("scheduler_unit")
        assert unit == event.get("resource", {}).get("service")
        assert event.get("fabric", {}).get("context_links", {}).get("links", {}).get("scheduler_unit") == unit
        assert f"scheduler_unit:{unit}" in event.get("fabric", {}).get("context_links", {}).get("correlation_keys", [])
        _assert_evidence_refs(event.get("evidence_refs", []))


def test_live_self_awareness_working_stack_maps_actual_runtime_body(run_abyss_machine) -> None:
    payload = _run_json(run_abyss_machine, "self-awareness", "working-stack", "--json", timeout=120.0)

    assert payload["schema"] == "abyss_machine_self_awareness_working_stack_inventory_v1"
    assert payload["ok"] is True
    assert payload["status"] in {"mapped", "mapped_with_usage_gaps"}
    _assert_no_stack_mutation_policy(payload)

    summary = payload.get("summary", {})
    organs = {row.get("service"): row for row in payload.get("organs", [])}
    expected_live = {
        "prometheus",
        "grafana",
        "loki",
        "alloy",
        "alertmanager",
        "cadvisor",
        "route-api",
        "rag-api",
        "langchain-api",
        "postgres",
        "neo4j",
        "qdrant",
        "redis",
        "rerank-api",
        "ovms",
        "llama-cpp",
        "docs-api",
        "aoa-browser",
    }

    assert summary.get("organs", 0) >= len(expected_live)
    assert expected_live.issubset(organs)
    assert summary.get("time_space_context_links") == summary.get("organs")
    assert summary.get("runtime_services", 0) >= len(expected_live)
    assert summary.get("endpoint_probes", 0) >= 8
    assert summary.get("model_roots", 0) > 0
    assert isinstance(payload.get("machine_usage_gaps"), list)
    assert payload.get("policy", {}).get("stack_source_refs_are_read_only") is True

    declared_services = {row.get("service") for row in payload.get("compose", {}).get("services", [])}
    assert {"qwen-tts", "tts-router", "tos-graph", "babelvox-tts"}.issubset(declared_services)
    for service in expected_live:
        organ = organs[service]
        assert organ.get("owner_surface") == "abyss-stack"
        assert organ.get("policy", {}).get("host_layer_mutates_stack") is False
        assert organ.get("time_space_context_link", {}).get("context", {}).get("working_stack_link_id")
        assert organ.get("evidence_refs")
        assert not any(
            str(ref.get("path", "")).startswith(PROTECTED_STACK_ROOTS)
            for ref in organ.get("evidence_refs", [])
        )
    stack_source_refs = [
        ref
        for organ in organs.values()
        for ref in organ.get("stack_source_refs", [])
    ]
    assert stack_source_refs
    assert all(ref.get("read_only") is True for ref in stack_source_refs)
    assert all(ref.get("host_layer_mutates_stack") is False for ref in stack_source_refs)

    docs = organs["docs-api"]
    docs_probes = {row.get("probe"): row for row in docs.get("endpoint_probes", [])}
    assert docs["machine_usage_status"] == "active_machine_tool_signal"
    assert docs["deep_usage_proven"] is True
    assert docs_probes.get("health", {}).get("ok") is True
    assert docs_probes.get("search:n8n-workflow", {}).get("ok") is True
    assert docs_probes["search:n8n-workflow"].get("policy", {}).get("response_body_stored") is False

    browser = organs["aoa-browser"]
    browser_probes = {row.get("probe"): row for row in browser.get("endpoint_probes", [])}
    assert browser_probes.get("health", {}).get("ok") is True
    assert browser_probes.get("private-host-guard", {}).get("ok") is True
    assert browser_probes.get("private-host-guard", {}).get("status_code") == 403
    assert "playwright-chromium-launch" in browser_probes
    if browser_probes["playwright-chromium-launch"].get("ok") is True:
        assert browser["machine_usage_status"] == "active_machine_tool_signal"
        assert browser["deep_usage_proven"] is True
    else:
        assert browser["machine_usage_status"] == "tool_runtime_degraded"
        assert browser["deep_usage_proven"] is False
        assert browser.get("usage_gap")

    for service in ("embeddings", "stt", "tts", "llm-registry"):
        organ = organs[service]
        bridge = organ.get("model_bridge", {})
        assert organ["machine_usage_status"] == "active_model_root_bridge"
        assert organ["deep_usage_proven"] is True
        assert bridge.get("schema") == "abyss_machine_self_awareness_working_stack_model_bridge_v1"
        assert bridge.get("active") is True
        assert bridge.get("runtime_ready") is True
        assert bridge.get("linked_stack_model_source_paths")
        assert bridge.get("policy", {}).get("host_layer_mutates_stack") is False
        assert bridge.get("policy", {}).get("model_promotion_decision") is False
        assert not any(
            str(ref.get("path", "")).startswith(PROTECTED_STACK_ROOTS)
            for ref in bridge.get("evidence_refs", [])
        )


def test_live_self_awareness_working_stack_signal_reaches_time_space_context(run_abyss_machine) -> None:
    working = _run_json(run_abyss_machine, "self-awareness", "working-stack", "--json", timeout=120.0)
    collect = _run_json(run_abyss_machine, "self-awareness", "collect", "--json", timeout=160.0)
    timeline = _run_json(run_abyss_machine, "self-awareness", "timeline", "--json", timeout=120.0)
    spatial = _run_json(run_abyss_machine, "self-awareness", "spatial-graph", "--json", timeout=120.0)
    context = _run_json(run_abyss_machine, "self-awareness", "context", "--json", timeout=120.0)

    organs = {row.get("service"): row for row in working.get("organs", [])}
    assert "qdrant" in organs
    qdrant_link = organs["qdrant"].get("time_space_context_link", {}).get("link_id")
    assert qdrant_link

    qdrant_events = [
        event for event in collect.get("events", [])
        if event.get("source") == "working-stack" and event.get("resource", {}).get("service") == "qdrant"
    ]
    assert qdrant_events
    assert any((event.get("context") or {}).get("working_stack_link_id") == qdrant_link for event in qdrant_events)

    timeline_services = {
        resource.get("service")
        for window in timeline.get("windows", [])
        for resource in window.get("resources", [])
        if isinstance(resource, dict)
    }
    spatial_nodes = {node.get("id") for node in spatial.get("nodes", [])}
    context_keys = {row.get("key") for row in context.get("contexts", [])}

    assert "qdrant" in timeline_services
    assert "service:qdrant" in spatial_nodes
    assert qdrant_link in context_keys
    assert "scheduler_category:warm_e2b" in context_keys
    assert any(str(key).startswith("scheduler_unit:abyss-gemma4-spark-") for key in context_keys)
    assert "host_service_category:dictation" in context_keys
    assert any(key in context_keys for key in {
        "host_service_unit:abyss-dictation-server.service",
        "host_service_unit:abyss-dictation-hotkey.service",
        "host_service_unit:ydotoold.service",
    })
    assert spatial.get("summary", {}).get("working_stack_expected_live_present") is True
    assert context.get("summary", {}).get("working_stack_contexts", 0) >= working.get("summary", {}).get("organs", 0)
    assert context.get("summary", {}).get("scheduler_unit_contexts", 0) >= 1
    assert context.get("summary", {}).get("host_service_unit_contexts", 0) >= 1


def test_live_self_awareness_memory_space_overlay_depth(run_abyss_machine) -> None:
    context = _run_json(run_abyss_machine, "self-awareness", "context", "--json", timeout=120.0)
    timeline = _run_json(run_abyss_machine, "self-awareness", "timeline", "--json", timeout=120.0)
    spatial = _run_json(run_abyss_machine, "self-awareness", "spatial-graph", "--json", timeout=120.0)
    query = _run_json(
        run_abyss_machine,
        "self-awareness",
        "query",
        "--query",
        "rag graph memory postgres neo4j embeddings freshness",
        "--json",
        timeout=120.0,
    )

    assert context["schema"] == "abyss_machine_self_awareness_context_v1"
    assert timeline["schema"] == "abyss_machine_self_awareness_timeline_v1"
    assert spatial["schema"] == "abyss_machine_self_awareness_spatial_graph_v1"
    assert query["schema"] == "abyss_machine_self_awareness_query_v1"
    _assert_no_stack_mutation_policy(context)
    _assert_no_stack_mutation_policy(query)

    memory_space = context.get("memory_space", {})
    assert memory_space.get("schema") == "abyss_machine_self_awareness_memory_space_overlay_v1"
    assert memory_space.get("policy", {}).get("bounded_retrieval") is True
    assert memory_space.get("policy", {}).get("freshness_must_precede_reasoning") is True
    assert memory_space.get("policy", {}).get("raw_evidence_is_not_truth") is True
    assert memory_space.get("policy", {}).get("host_layer_mutates_stack") is False
    assert memory_space.get("summary", {}).get("retrieval_packets", 0) > 0
    assert memory_space.get("summary", {}).get("spatial_overlay_entries", 0) > 0

    context_packet = context.get("context_packet", {})
    assert context_packet.get("schema") == "abyss_machine_self_awareness_bounded_context_packet_v1"
    assert context_packet.get("complete") is True
    assert context.get("summary", {}).get("bounded_context_packet_complete") is True
    assert context_packet.get("bounds", {}).get("raw_private_content") is False
    assert context_packet.get("bounds", {}).get("stores_raw_body") is False
    assert context_packet.get("bounds", {}).get("stores_raw_context_values") is False
    assert context_packet.get("bounds", {}).get("freshness_must_precede_reasoning") is True
    assert context_packet.get("bounds", {}).get("raw_evidence_is_not_truth") is True
    assert context_packet.get("policy", {}).get("host_layer_mutates_stack") is False
    assert context_packet.get("policy", {}).get("action_execution") is False
    assert context_packet.get("policy", {}).get("read_only_tools_only") is True
    sections = context_packet.get("sections", {})
    assert {"correlation_contexts", "host_body", "memory_space", "stack_handoff", "resident_worker", "governance_gates", "escalation_gate"}.issubset(sections)
    assert sections.get("host_body", {}).get("policy", {}).get("host_layer_mutates_stack") is False
    assert sections.get("host_body", {}).get("bounds", {}).get("stores_raw_body") is False
    assert sections.get("host_body", {}).get("scheduler", {}).get("unit_contexts", 0) >= 1
    assert sections.get("host_body", {}).get("host_services", {}).get("unit_contexts", 0) >= 1
    assert sections.get("resident_worker", {}).get("complete") is True
    assert sections.get("governance_gates", {}).get("complete") is True
    assert sections.get("memory_space", {}).get("policy", {}).get("host_layer_mutates_stack") is False
    assert sections.get("stack_handoff", {}).get("policy", {}).get("host_layer_mutates_stack") is False
    assert context_packet.get("summary", {}).get("stack_handoff_actions", 0) >= 1
    tool_kinds = {tool.get("kind") for tool in context_packet.get("read_only_tools", [])}
    assert {"promql_read", "logql_read", "memory_space", "spatial_graph", "requirements_handoff", "resident_worker", "governance_gates", "export_handoff"}.issubset(tool_kinds)

    gate_ids = {gate.get("gate_id") for gate in memory_space.get("freshness_gates", [])}
    assert {"rag_trace", "rag_validate", "maps", "graph", "memory_status", "nervous_freshness"}.issubset(gate_ids)
    assert all(gate.get("freshness_must_precede_reasoning") is True for gate in memory_space.get("freshness_gates", []))
    assert all(gate.get("raw_evidence_is_not_truth") is True for gate in memory_space.get("freshness_gates", []))

    backend_by_id = {item.get("id"): item for item in memory_space.get("stack_semantic_backends", [])}
    assert {"postgres", "neo4j", "rag-api", "embeddings"}.issubset(backend_by_id)
    assert backend_by_id["postgres"].get("owner") == "abyss-stack"
    assert backend_by_id["neo4j"].get("owner") == "abyss-stack"
    assert backend_by_id["rag-api"].get("semantic_inventory") == "bounded_machine_rag_trace"

    assert spatial.get("memory_space_overlay", {}).get("schema") == "abyss_machine_self_awareness_memory_space_overlay_v1"
    assert spatial.get("summary", {}).get("memory_space_nodes", 0) > 0
    assert spatial.get("summary", {}).get("freshness_gates", 0) >= 6

    timeline_overlay = timeline.get("stack_handoff_time_space_overlay", {})
    spatial_overlay = spatial.get("stack_handoff_time_space_overlay", {})
    markers = timeline_overlay.get("timeline_markers", [])
    stack_nodes = [
        node for node in spatial.get("nodes", [])
        if node.get("kind") in {"stack_requirement", "stack_handoff_action", "stack_runbook_candidate", "stack_handoff_overlay"}
    ]
    stack_edges = [
        edge for edge in spatial.get("edges", [])
        if str(edge.get("kind", "")).startswith(("tracks_open_stack", "proposes_handoff", "has_runbook", "blocks_stack", "intersects_memory"))
    ]
    assert timeline_overlay.get("schema") == "abyss_machine_self_awareness_stack_handoff_time_space_overlay_v1"
    assert spatial_overlay.get("schema") == "abyss_machine_self_awareness_stack_handoff_time_space_overlay_v1"
    assert timeline_overlay.get("policy", {}).get("host_layer_mutates_stack") is False
    assert timeline_overlay.get("policy", {}).get("executes_commands") is False
    assert timeline.get("summary", {}).get("stack_handoff_markers") == len(markers)
    assert spatial.get("summary", {}).get("stack_handoff_markers") == len(markers)
    assert spatial.get("summary", {}).get("stack_handoff_nodes", 0) == len(stack_nodes)
    assert spatial.get("summary", {}).get("stack_handoff_edges", 0) == len(stack_edges)
    if markers:
        marker_ids = {
            marker_id
            for window in timeline.get("windows", [])
            for marker_id in window.get("stack_handoff_marker_ids", [])
        }
        assert {marker.get("id") for marker in markers}.issubset(marker_ids)
    for marker in markers:
        assert marker.get("time", {}).get("freshness_must_precede_reasoning") is True
        assert marker.get("space", {}).get("owner_surface") == "abyss-stack"
        assert marker.get("space", {}).get("service_nodes")
        assert marker.get("closure_blockers")
        assert marker.get("closure_blocker_keys")
        assert marker.get("runbook_candidate", {}).get("machine_executes_stack_change") is False
        assert marker.get("verifier_commands")
        assert marker.get("safe_next_action", {}).get("host_layer_mutates_stack") is False
        assert marker.get("policy", {}).get("host_layer_mutates_stack") is False

    assert query.get("query_plan", {}).get("match_strategy") == "bounded_term_score_over_redacted_json"
    assert query.get("summary", {}).get("memory_space_hits", 0) > 0
    assert query.get("results", {}).get("memory_space")


def test_live_self_awareness_requirements_are_stack_handoffs(run_abyss_machine) -> None:
    payload = _run_json(run_abyss_machine, "self-awareness", "requirements", "--json", timeout=90.0)

    assert payload["schema"] == "abyss_machine_self_awareness_requirements_v1"
    assert payload["ok"] is True
    assert payload["status"] in {"ok", "open_requirements"}
    assert payload.get("policy", {}).get("requirements_are_not_stack_mutations") is True
    assert payload.get("policy", {}).get("owner_route_required_before_runtime_change") is True
    assert payload.get("policy", {}).get("stack_handoff_is_machine_checkable") is True

    requirements = payload.get("requirements", [])
    handoff_by_id = {item.get("id"): item for item in payload.get("stack_handoff", [])}
    assert len(handoff_by_id) == len(payload.get("stack_handoff", []))

    if requirements:
        assert payload["summary"]["stack_owned"] == len(requirements)
        assert payload["summary"]["machine_owned"] == 0
        assert payload["summary"]["open_stack_requirements"] == len(requirements)
        assert payload["summary"]["stack_handoff_acceptance_verifiers"] == len(requirements)
        assert payload["summary"]["stack_handoff_acceptance_verifier_steps"] >= len(requirements)
        assert payload["summary"]["stack_handoff_safe_next_actions"] == len(requirements)
        assert payload["summary"]["stack_handoff_coverage_impact_entries"] == len(requirements)
        assert set(payload.get("open_stack_ids", [])) == {item["id"] for item in requirements}
        assert set(payload.get("open_stack_requirement_ids", [])) == {item["id"] for item in requirements}

    for requirement in requirements:
        requirement_id = requirement["id"]
        assert requirement["owner"] == "abyss-stack"
        assert requirement["host_layer_mutates_stack"] is False
        assert requirement["machine_action"] == "record_requirement_only"
        assert requirement["status"] == "open"
        assert requirement_id in handoff_by_id
        _assert_evidence_refs(requirement.get("evidence_refs"))
        readiness = requirement.get("closure_readiness", {})
        assert readiness.get("schema") == "abyss_machine_self_awareness_requirement_readiness_summary_v1"
        assert readiness.get("requirement_id") == requirement_id
        assert readiness.get("policy", {}).get("host_layer_mutates_stack") is False
        assert isinstance(requirement.get("missing_checks"), list)
        assert isinstance(requirement.get("blocking_check_keys"), list)
        assert requirement.get("runbook_candidate_id")
        assert requirement.get("verifier_commands")
        assert requirement.get("acceptance_contract", {}).get("schema") == "abyss_machine_stack_requirement_acceptance_contract_v1"
        assert requirement.get("machine_closure_probe", {}).get("required_fields")
        assert requirement.get("acceptance_verifiers")
        assert requirement.get("stack_acceptance")
        assert requirement.get("acceptance_after_stack_change")
        assert requirement.get("coverage_impact", {}).get("schema") == "abyss_machine_self_awareness_stack_coverage_impact_v1"
        assert requirement.get("coverage_impact", {}).get("policy", {}).get("host_layer_mutates_stack") is False
        assert requirement.get("safe_next_action", {}).get("host_layer_mutates_stack") is False
        assert requirement.get("current_state_digest", {}).get("schema") == "abyss_machine_self_awareness_requirement_current_state_digest_v1"
        assert requirement.get("current_state_digest", {}).get("has_current_state") is True
        assert requirement.get("current_state_digest", {}).get("policy", {}).get("raw_payloads_included") is False
        assert requirement.get("current_state_digest", {}).get("policy", {}).get("raw_secrets_included") is False
        assert requirement.get("closed_by_current_probe") is False
        assert requirement.get("handoff_contract_complete") is True
        compat = requirement.get("compat_contract", {})
        assert compat.get("schema") == "abyss_machine_self_awareness_stack_compat_contract_v1"
        assert compat.get("requirement_id") == requirement_id
        assert compat.get("operator_boundary", {}).get("abyss_machine_executes_stack_change") is False
        assert compat.get("policy", {}).get("host_layer_mutates_stack") is False

        expected_shape = requirement.get("expected_shape", {})
        if expected_shape:
            assert expected_shape.get("mutated_by") == "abyss-stack"

        handoff = handoff_by_id[requirement_id]
        assert handoff["id"] == handoff["requirement_id"] == requirement_id
        assert handoff["owner"] == "abyss-stack"
        assert handoff["host_layer_mutates_stack"] is False
        assert handoff["machine_read_command"] == "abyss-machine self-awareness requirements --json"
        assert handoff.get("stack_acceptance")
        assert handoff.get("acceptance_after_stack_change")
        assert handoff.get("machine_closure_probe")
        assert handoff.get("closure_readiness", {}).get("schema") == "abyss_machine_self_awareness_requirement_readiness_summary_v1"
        assert handoff.get("runbook_candidate_id")
        assert handoff.get("verifier_commands")
        assert handoff.get("acceptance_verifiers")
        assert handoff.get("current_state_digest", {}).get("policy", {}).get("raw_secrets_included") is False
        assert handoff.get("handoff_contract_complete") is True
        assert handoff.get("safe_next_action", {}).get("host_layer_mutates_stack") is False
        assert handoff.get("coverage_impact", {}).get("policy", {}).get("host_layer_mutates_stack") is False

        contract = handoff.get("acceptance_contract", {})
        probe = handoff["machine_closure_probe"]
        assert contract.get("schema") == "abyss_machine_stack_requirement_acceptance_contract_v1"
        assert contract.get("requirement_id") == requirement_id
        assert contract.get("machine_role") == "read_only_consumer"
        assert contract.get("closure_semantics", {}).get("host_layer_mutates_stack") is False
        assert contract.get("closure_semantics", {}).get("requires_stack_owned_route") is True
        assert contract.get("machine_verifiers")
        assert probe.get("kind")
        assert probe.get("required_fields")
        assert probe.get("success_predicates")
        assert probe.get("redaction_rules")

    if requirements:
        assert payload["summary"]["stack_handoff_closure_readiness_packets"] == len(requirements)
        assert payload["summary"]["stack_handoff_runbook_candidates"] == len(requirements)
        assert payload.get("stack_handoff_closure_order")
        assert payload["stack_handoff_closure_order"][0]["safe_next_action"]["host_layer_mutates_stack"] is False
        assert payload["stack_handoff_closure_order"][0]["acceptance_verifiers"]
        assert payload["stack_handoff_closure_order"][0]["verifier_commands"]
        assert payload["stack_handoff_closure_order"][0]["coverage_impact"]["schema"] == "abyss_machine_self_awareness_stack_coverage_impact_v1"


def test_live_self_awareness_capabilities_expose_governance_gate_detail(run_abyss_machine) -> None:
    payload = _run_json(run_abyss_machine, "self-awareness", "capabilities", "--json", timeout=120.0)

    assert payload["schema"] == "abyss_machine_self_awareness_capabilities_v1"
    assert payload["ok"] is True
    assert payload.get("summary", {}).get("coverage_planes", {}).get("governance_gates") is True
    _assert_no_stack_mutation_policy(payload)

    capabilities = {item.get("id"): item for item in payload.get("capabilities", [])}
    depth = payload.get("summary", {}).get("capability_matrix_depth", {})
    assert depth.get("rows") == len(capabilities)
    assert depth.get("with_matrix") == len(capabilities)
    assert depth.get("with_owner_boundary") == len(capabilities)
    assert depth.get("with_access") == len(capabilities)
    assert depth.get("with_freshness") == len(capabilities)
    assert depth.get("with_history") == len(capabilities)
    assert depth.get("with_evidence_route") == len(capabilities)
    assert depth.get("with_latest_artifacts", 0) > 0
    assert depth.get("with_endpoints", 0) > 0

    http_capabilities = {
        "prometheus.targets",
        "loki.logql",
        "grafana.health",
        "alertmanager.lifecycle",
        "tempo.trace.backend",
        "langgraph.investigator.runtime",
    }
    for capability_id, capability in capabilities.items():
        assert capability.get("matrix", {}).get("schema") == "abyss_machine_self_awareness_capability_matrix_row_v1"
        assert capability.get("matrix", {}).get("capability_id") == capability_id
        assert capability.get("owner_boundary", {}).get("owner") == capability.get("owner")
        assert capability.get("owner_boundary", {}).get("host_layer_mutates_stack") is False
        assert capability.get("access", {}).get("read_only") is True
        assert capability.get("access", {}).get("host_layer_mutates_stack") is False
        assert capability.get("access", {}).get("stores_raw_private_payload") is False
        assert capability.get("freshness", {}).get("freshness_must_precede_reasoning") is True
        assert capability.get("freshness", {}).get("raw_evidence_is_not_truth") is True
        assert isinstance(capability.get("history", {}).get("latest_artifacts"), list)
        assert isinstance(capability.get("schemas"), list)
        assert isinstance(capability.get("latest_artifacts"), list)
        assert isinstance(capability.get("endpoints"), list)
        assert capability.get("matrix", {}).get("evidence_route", {}).get("has_endpoint_or_artifact") is True
        if capability_id in http_capabilities:
            assert capability.get("endpoints")
            assert all(endpoint.get("read_only") is True for endpoint in capability.get("endpoints", []))
            assert all(endpoint.get("body_stored") is False for endpoint in capability.get("endpoints", []))

    governance = capabilities.get("host.governance-gates", {})
    detail = governance.get("detail", {})

    assert governance.get("owner") == "abyss-machine"
    assert governance.get("ok") is True
    assert detail.get("memory_status")
    assert detail.get("resource_status")
    assert detail.get("mode_status")
    assert detail.get("readiness", {}).get("status") in {"ready", "degraded"}
    assert detail.get("memory", {}).get("class")
    assert isinstance(detail.get("resource", {}).get("orchestrator_summary"), dict)
    assert detail.get("mode", {}).get("effective_mode")
    assert detail.get("policy", {}).get("host_layer_mutates_stack") is False
    assert detail.get("policy", {}).get("mutates_existing_processes") is False
    assert detail.get("policy", {}).get("automatic_remediation") is False
    _assert_evidence_refs(governance.get("evidence_refs"))


def test_live_self_awareness_capabilities_expose_resident_worker_detail(run_abyss_machine) -> None:
    payload = _run_json(run_abyss_machine, "self-awareness", "capabilities", "--json", timeout=120.0)

    assert payload["schema"] == "abyss_machine_self_awareness_capabilities_v1"
    assert payload["ok"] is True
    assert payload.get("summary", {}).get("coverage_planes", {}).get("ai_resident_worker") is True
    _assert_no_stack_mutation_policy(payload)

    capabilities = {item.get("id"): item for item in payload.get("capabilities", [])}
    resident = capabilities.get("warm-e2b.resident-cognitive-worker", {})
    detail = resident.get("detail", {})

    assert resident.get("owner") == "abyss-machine"
    assert resident.get("ok") is True
    assert detail.get("status") == "running"
    assert detail.get("serving", {}).get("owner") == "abyss-stack"
    assert detail.get("serving", {}).get("stack_owned_serving") is True
    assert detail.get("health", {}).get("ok") is True
    assert detail.get("health", {}).get("health_latency_ms") is not None
    assert detail.get("health", {}).get("model_id")
    assert detail.get("monitor", {}).get("ok") is True
    assert detail.get("monitor", {}).get("monitor_timer_active") == "active"
    assert detail.get("resource_thermal", {}).get("package_temp_c") is not None
    assert detail.get("candidate_context", {}).get("candidates") is not None
    assert detail.get("candidate_context", {}).get("action_execution") is False
    assert detail.get("evals", {}).get("overall_score") is not None
    assert detail.get("policy", {}).get("model_execution_in_self_awareness_graph") is False
    assert detail.get("policy", {}).get("candidate_synthesis_only") is True
    assert detail.get("policy", {}).get("host_layer_mutates_stack") is False
    assert detail.get("policy", {}).get("abyss_machine_writes_stack") is False
    assert detail.get("policy", {}).get("candidate_output_is_owner_truth") is False
    assert detail.get("cognitive_contract", {}).get("schema") == "abyss_machine_self_awareness_resident_cognitive_contract_v1"
    assert detail.get("cognitive_contract", {}).get("bounded_context_packet_required") is True
    assert detail.get("cognitive_contract", {}).get("read_only_tool_inventory_required") is True
    assert detail.get("cognitive_contract", {}).get("hypothesis_testing_required") is True
    assert detail.get("cognitive_contract", {}).get("contradiction_notes_required") is True
    assert detail.get("cognitive_contract", {}).get("direct_model_generation_in_self_awareness") is False
    _assert_evidence_refs(resident.get("evidence_refs"))


def test_live_self_awareness_investigation_exposes_resident_cognitive_packet(run_abyss_machine) -> None:
    payload = _run_json(
        run_abyss_machine,
        "self-awareness",
        "investigate",
        "--query",
        "warm e2b resident cognitive worker stack rag graph hypothesis contradiction escalation",
        "--json",
        timeout=140.0,
    )

    assert payload["schema"] == "abyss_machine_self_awareness_investigation_v1"
    assert payload["ok"] is True
    _assert_no_stack_mutation_policy(payload)

    graph = payload.get("graph", {})
    assert graph.get("nodes") == LANGGRAPH_INVESTIGATION_NODE_ORDER
    assert graph.get("node_order") == LANGGRAPH_INVESTIGATION_NODE_ORDER
    assert graph.get("resume", {}).get("supported") is True
    assert graph.get("failure_recovery", {}).get("supported") is True
    assert graph.get("human_approval_before_mutation") is True
    assert graph.get("automatic_actions") is False
    assert graph.get("mutation_nodes") == []
    assert payload.get("summary", {}).get("graph_nodes") == len(LANGGRAPH_INVESTIGATION_NODE_ORDER)
    assert payload.get("summary", {}).get("resume_supported") is True
    assert payload.get("summary", {}).get("evidence_validation_fails") == 0

    states = {row.get("node"): row.get("state", {}) for row in payload.get("states", [])}
    assert set(LANGGRAPH_INVESTIGATION_NODE_ORDER).issubset(states)
    requests_state = states["request_more_evidence"]
    requests = requests_state.get("requests", [])
    assert requests
    assert requests_state.get("all_requests_non_mutating") is True
    assert all(request.get("automatic") is False for request in requests)
    assert all(request.get("host_layer_mutates_stack") is False for request in requests)
    action_map = requests_state.get("stack_handoff_action_map", {})
    closure_readiness = requests_state.get("stack_handoff_closure_readiness", {})
    stack_actions = action_map.get("actions", [])
    stack_requests = [request for request in requests if request.get("kind") == "stack_handoff_action"]
    assert action_map.get("schema") == "abyss_machine_self_awareness_brief_stack_handoff_action_map_v1"
    assert action_map.get("policy", {}).get("host_layer_mutates_stack") is False
    assert action_map.get("policy", {}).get("executes_commands") is False
    assert action_map.get("summary", {}).get("open_stack_requirements") == len(stack_actions)
    assert action_map.get("summary", {}).get("actions") == len(stack_actions)
    assert closure_readiness.get("schema") == "abyss_machine_self_awareness_investigation_stack_handoff_closure_readiness_v1"
    assert closure_readiness.get("summary", {}).get("complete") is True
    assert closure_readiness.get("summary", {}).get("packets") == len(stack_actions)
    assert closure_readiness.get("policy", {}).get("host_layer_mutates_stack") is False
    assert closure_readiness.get("policy", {}).get("executes_commands") is False
    assert closure_readiness.get("policy", {}).get("action_execution") is False
    assert len(stack_requests) == len(stack_actions)
    if stack_actions:
        assert action_map.get("summary", {}).get("top_requirement_id") == stack_actions[0].get("requirement_id")
        assert closure_readiness.get("ordered_next_actions", [])[0].get("requirement_id") == stack_actions[0].get("requirement_id")
    for request in stack_requests:
        assert request.get("closure_blockers")
        assert request.get("closure_blocker_keys")
        assert request.get("runbook_candidate_id")
        assert request.get("runbook_candidate", {}).get("machine_executes_stack_change") is False
        assert request.get("acceptance_verifiers")
        assert request.get("verifier_commands")
        assert request.get("closure_readiness", {}).get("schema") == "abyss_machine_stack_handoff_closure_readiness_v1"
        assert request.get("closure_readiness", {}).get("blocking_check_keys")
        assert request.get("closure_readiness", {}).get("policy", {}).get("host_layer_mutates_stack") is False
        assert request.get("safe_next_action", {}).get("requires_human_approval") is True
        assert request.get("safe_next_action", {}).get("automatic") is False
        assert request.get("policy", {}).get("host_layer_mutates_stack") is False
        assert request.get("policy", {}).get("executes_commands") is False

    validation_state = states["validate_evidence"]
    validation = validation_state.get("validation", {})
    assert validation.get("schema") == "abyss_machine_self_awareness_investigation_evidence_validation_v1"
    assert validation.get("summary", {}).get("fails") == 0
    assert validation.get("policy", {}).get("host_layer_mutates_stack") is False
    assert validation.get("policy", {}).get("action_execution") is False
    validation_checks = {check.get("id"): check for check in validation.get("checks", [])}
    assert validation_checks.get("stack_handoff_action_map_complete", {}).get("ok") is True
    assert validation_checks.get("stack_handoff_closure_readiness_complete", {}).get("ok") is True

    record_state = states["record_artifact"]
    assert record_state.get("schema") == "abyss_machine_self_awareness_investigation_artifact_record_v1"
    assert record_state.get("artifact_path") == "/var/lib/abyss-machine/self-awareness/investigate/latest.json"
    assert record_state.get("policy", {}).get("host_layer_mutates_stack") is False

    brief_state = states["brief_reaction_candidate"]
    assert brief_state.get("stack_handoff_action_map", {}).get("schema") == "abyss_machine_self_awareness_brief_stack_handoff_action_map_v1"
    assert brief_state.get("stack_handoff_closure_readiness", {}).get("schema") == "abyss_machine_self_awareness_investigation_stack_handoff_closure_readiness_v1"
    assert brief_state.get("stack_handoff_closure_readiness", {}).get("summary", {}).get("packets") == len(stack_actions)
    if stack_actions:
        assert brief_state.get("top_stack_handoff_action", {}).get("requirement_id") == stack_actions[0].get("requirement_id")
    safe_next_action = brief_state.get("safe_next_action", {})
    assert safe_next_action.get("requires_human_approval") is True
    assert safe_next_action.get("automatic") is False
    assert safe_next_action.get("executes_commands") is False
    assert safe_next_action.get("host_layer_mutates_stack") is False

    assert payload.get("stack_handoff_action_map", {}).get("schema") == "abyss_machine_self_awareness_brief_stack_handoff_action_map_v1"
    assert payload.get("stack_handoff_closure_readiness", {}).get("schema") == "abyss_machine_self_awareness_investigation_stack_handoff_closure_readiness_v1"
    assert payload.get("summary", {}).get("stack_handoff_closure_readiness_packets") == len(stack_actions)
    conclusion = payload.get("conclusion", {})
    assert conclusion.get("stack_handoff_action_map", {}).get("schema") == "abyss_machine_self_awareness_brief_stack_handoff_action_map_v1"
    assert conclusion.get("stack_handoff_closure_readiness", {}).get("schema") == "abyss_machine_self_awareness_investigation_stack_handoff_closure_readiness_v1"
    assert conclusion.get("stack_handoff_closure_readiness", {}).get("summary", {}).get("packets") == len(stack_actions)
    if stack_actions:
        assert conclusion.get("top_stack_handoff_action", {}).get("requirement_id") == stack_actions[0].get("requirement_id")
    assert conclusion.get("next_safe_action", {}).get("requires_human_approval") is True
    assert conclusion.get("next_safe_action", {}).get("host_layer_mutates_stack") is False

    packet = payload.get("resident_cognitive_packet", {})
    assert packet.get("schema") == "abyss_machine_self_awareness_resident_cognitive_packet_v1"
    assert payload.get("summary", {}).get("resident_cognitive_packet_complete") is True
    assert packet.get("bounded_context", {}).get("raw_private_content") is False
    assert packet.get("bounded_context", {}).get("stores_raw_body") is False
    assert packet.get("bounded_context", {}).get("freshness_must_precede_reasoning") is True
    assert packet.get("policy", {}).get("direct_model_prompt_executed") is False
    assert packet.get("policy", {}).get("read_only_tools_only") is True
    assert packet.get("policy", {}).get("host_layer_mutates_stack") is False
    assert packet.get("policy", {}).get("human_approval_before_mutation") is True

    tools = packet.get("read_only_tools", [])
    tool_kinds = {tool.get("kind") for tool in tools}
    assert {"promql_read", "logql_read", "self_awareness_context", "self_awareness_spatial_graph", "rag_validate", "nervous_brief", "requirements_handoff", "resource_mode_gate"}.issubset(tool_kinds)
    assert all(tool.get("read_only") is True for tool in tools)
    assert all(tool.get("host_layer_mutates_stack") is False for tool in tools)
    assert all(tool.get("stores_raw_body") is False for tool in tools)

    assert len(packet.get("hypothesis_tests", [])) >= 3
    assert all(item.get("evidence_refs") for item in packet.get("hypothesis_tests", []))
    assert packet.get("contradiction_notes")
    assert packet.get("evidence_cited_summary", {}).get("evidence_refs")
    assert packet.get("escalation_gate", {}).get("schema") == "abyss_machine_self_awareness_resident_escalation_gate_v1"
    assert packet.get("escalation_gate", {}).get("human_approval_before_mutation") is True
    assert packet.get("escalation_gate", {}).get("host_layer_mutates_stack") is False
    assert packet.get("escalation_gate", {}).get("action_execution") is False


def test_live_self_awareness_replay_exposes_resume_diff_and_recovery(run_abyss_machine) -> None:
    investigation = _run_json(
        run_abyss_machine,
        "self-awareness",
        "investigate",
        "--query",
        "langgraph replay resume conclusion diff failure recovery",
        "--json",
        timeout=140.0,
    )
    replay = _run_json(
        run_abyss_machine,
        "self-awareness",
        "replay",
        "--thread-id",
        investigation["thread_id"],
        "--json",
        timeout=90.0,
    )

    assert replay["schema"] == "abyss_machine_self_awareness_replay_v1"
    assert replay["ok"] is True
    _assert_no_stack_mutation_policy(replay)
    assert replay.get("expected_node_order") == LANGGRAPH_INVESTIGATION_NODE_ORDER
    assert replay.get("summary", {}).get("node_order") == LANGGRAPH_INVESTIGATION_NODE_ORDER
    assert replay.get("summary", {}).get("divergences") == 0
    assert replay.get("summary", {}).get("conclusion_diff_changed") is False
    assert replay.get("conclusion_diff", {}).get("changed") is False
    assert replay.get("conclusion_diff", {}).get("divergences") == []
    assert replay.get("resume", {}).get("supported") is True
    assert replay.get("resume", {}).get("replay_required_before_action") is True
    assert replay.get("failure_recovery", {}).get("supported") is True
    assert replay.get("failure_recovery", {}).get("policy", {}).get("host_layer_mutates_stack") is False
    assert replay.get("failure_recovery", {}).get("policy", {}).get("action_execution") is False
    assert replay.get("summary", {}).get("stack_handoff_closure_readiness_replayable") is True
    assert replay.get("summary", {}).get("body_trace_replayable") is True
    readiness = replay.get("stack_handoff_closure_readiness", {})
    readiness_replay = replay.get("stack_handoff_replay", {})
    body_trace_replay = replay.get("body_trace_replay", {})
    assert readiness.get("schema") == "abyss_machine_self_awareness_investigation_stack_handoff_closure_readiness_v1"
    assert readiness.get("summary", {}).get("complete") is True
    assert replay.get("summary", {}).get("stack_handoff_closure_readiness_packets") == readiness.get("summary", {}).get("packets")
    assert readiness_replay.get("schema") == "abyss_machine_self_awareness_replay_stack_handoff_v1"
    assert readiness_replay.get("closure_readiness_replayable") is True
    assert all(readiness_replay.get("state_preservation", {}).values())
    assert readiness_replay.get("policy", {}).get("host_layer_mutates_stack") is False
    assert readiness_replay.get("policy", {}).get("executes_commands") is False
    assert body_trace_replay.get("schema") == "abyss_machine_self_awareness_replay_body_trace_v1"
    assert body_trace_replay.get("replayable") is True
    assert body_trace_replay.get("body_trace", {}).get("complete") is True
    assert body_trace_replay.get("body_trace", {}).get("host_body", {}).get("complete") is True
    assert all(body_trace_replay.get("state_preservation", {}).values())
    assert body_trace_replay.get("policy", {}).get("host_layer_mutates_stack") is False
    assert replay.get("policy", {}).get("host_layer_mutates_stack") is False
    assert replay.get("policy", {}).get("action_execution") is False
    assert replay.get("policy", {}).get("human_approval_before_mutation") is True


def test_live_self_awareness_capabilities_expose_ai_multimodal_detail(run_abyss_machine) -> None:
    payload = _run_json(run_abyss_machine, "self-awareness", "capabilities", "--json", timeout=120.0)

    assert payload["schema"] == "abyss_machine_self_awareness_capabilities_v1"
    assert payload["ok"] is True
    assert payload.get("summary", {}).get("coverage_planes", {}).get("ai_multimodal") is True
    _assert_no_stack_mutation_policy(payload)

    capabilities = {item.get("id"): item for item in payload.get("capabilities", [])}
    ai = capabilities.get("ai.multimodal.capability-map", {})
    detail = ai.get("detail", {})
    modalities = detail.get("modalities", {})

    assert ai.get("owner") == "abyss-machine"
    assert ai.get("ok") is True
    assert detail.get("status") == "ready"
    assert {"CPU", "GPU", "NPU"}.issubset(set(detail.get("devices", {}).get("available_devices", [])))
    assert detail.get("devices", {}).get("openvino_ok") is True
    assert detail.get("model_inventory", {}).get("entries", 0) > 0
    assert detail.get("model_inventory", {}).get("roots")
    assert modalities.get("stt", {}).get("source_model_count", 0) > 0
    assert modalities.get("embeddings", {}).get("source_model_count", 0) > 0
    assert modalities.get("llm_text", {}).get("registry_summary", {}).get("ready_profiles", 0) > 0
    assert modalities.get("llm_text", {}).get("profiles")
    assert modalities.get("tts", {}).get("profile_summary", {}).get("executable", 0) > 0
    assert modalities.get("tts", {}).get("profiles")
    assert modalities.get("npu", {}).get("device_ready") is True
    assert detail.get("policy", {}).get("host_layer_mutates_stack") is False
    assert detail.get("policy", {}).get("writes_project_roots") is False
    assert detail.get("policy", {}).get("capability_presence_is_stack_promotion") is False
    assert detail.get("policy", {}).get("future_stack_must_run_own_promotion_gates") is True
    _assert_evidence_refs(ai.get("evidence_refs"))


def test_live_self_awareness_capabilities_expose_llm_escalation_detail(run_abyss_machine) -> None:
    payload = _run_json(run_abyss_machine, "self-awareness", "capabilities", "--json", timeout=120.0)

    assert payload["schema"] == "abyss_machine_self_awareness_capabilities_v1"
    assert payload["ok"] is True
    assert payload.get("summary", {}).get("coverage_planes", {}).get("llm_escalation") is True
    _assert_no_stack_mutation_policy(payload)

    capabilities = {item.get("id"): item for item in payload.get("capabilities", [])}
    escalation = capabilities.get("llm.escalation.routes", {})
    detail = escalation.get("detail", {})

    assert escalation.get("owner") == "abyss-machine"
    assert escalation.get("ok") is True
    assert detail.get("schema") == "abyss_machine_self_awareness_llm_escalation_detail_v1"
    assert detail.get("status") == "ready_review_only"
    assert detail.get("route_ready") is True
    assert detail.get("review_pipeline_ready") is True
    profiles = detail.get("registry", {}).get("profiles", {})
    assert profiles.get("gemma4.workhorse", {}).get("status") == "ready"
    assert profiles.get("qwen36.ordinary", {}).get("status") == "ready"
    assert profiles.get("qwen36.heretic", {}).get("status") == "ready"
    workhorse = detail.get("workhorse", {})
    assert workhorse.get("pack", {}).get("ok") is True
    assert workhorse.get("pack", {}).get("summary", {}).get("source_ids", 0) > 0
    assert workhorse.get("review", {}).get("ok") is True
    assert workhorse.get("review", {}).get("summary", {}).get("model_used") is False
    assert workhorse.get("review", {}).get("policy", {}).get("action_execution") is False
    assert workhorse.get("review", {}).get("policy", {}).get("starts_llama_server") is False
    assert workhorse.get("validate", {}).get("ok") is True
    assert workhorse.get("validate", {}).get("summary", {}).get("fails") == 0
    assert workhorse.get("preflight", {}).get("decision") in {"allow", "ready", "block"}
    assert workhorse.get("preflight", {}).get("policy", {}).get("default_review_runs_model") is False
    qwen = detail.get("qwen_lazy_load", {})
    assert qwen.get("ready") is True
    for name in ("qwen36.ordinary", "qwen36.heretic"):
        qwen_profile = qwen.get("profiles", {}).get(name, {})
        assert qwen_profile.get("declared_class") == "heavy"
        assert qwen_profile.get("local_exists") is True
        assert qwen_profile.get("runtime_ok") is True
        assert qwen_profile.get("host_layer_mutates_stack") is False
        assert qwen_profile.get("lazy_load", {}).get("start_command")
        assert qwen_profile.get("lazy_load", {}).get("request_command")
        assert qwen_profile.get("server", {}).get("cpuset")
    gates = detail.get("gates", {})
    assert gates.get("model_execution_now", {}).get("allowed") in {True, False}
    assert gates.get("model_execution_now", {}).get("status") in {"allowed_now", "blocked_by_preflight", "operator_force_required", "gated_unknown"}
    assert gates.get("mode", {}).get("operator_force_supported") is not None
    assert gates.get("mode", {}).get("cpu_routed_heavy", {}).get("command")
    assert gates.get("resource", {}).get("preflight_decision")
    assert detail.get("policy", {}).get("host_layer_mutates_stack") is False
    assert detail.get("policy", {}).get("model_execution_in_self_awareness_graph") is False
    assert detail.get("policy", {}).get("default_model_execution") is False
    assert detail.get("policy", {}).get("action_execution") is False
    assert detail.get("policy", {}).get("qwen_lazy_load_is_not_resident_brain") is True
    _assert_evidence_refs(escalation.get("evidence_refs"))


def test_live_self_awareness_requirement_probes_verify_stack_handoffs(run_abyss_machine) -> None:
    payload = _run_json(run_abyss_machine, "self-awareness", "requirement-probes", "--json", timeout=120.0)

    assert payload["schema"] == "abyss_machine_self_awareness_requirement_probes_v1"
    assert payload["ok"] is True
    assert payload["status"] in {"open_requirements", "satisfied"}
    assert payload["policy"]["read_only"] is True
    assert payload["policy"]["host_layer_mutates_stack"] is False
    assert payload["policy"]["requirements_are_not_stack_mutations"] is True
    assert payload["policy"]["open_stack_requirements_are_blockers_not_host_failures"] is True
    assert payload["policy"]["runbook_candidates_are_handoff_only"] is True

    summary = payload["summary"]
    probes = payload.get("probes", [])
    runbook_candidates = payload.get("runbook_candidates", [])
    assert summary["probes"] == len(probes)
    assert summary["stack_handoff"] == len(probes)
    assert summary["internal_contract_failures"] == []
    assert summary["secret_leaks"] == 0
    assert summary["mutating_routes"] == 0
    assert summary["runbook_candidates"] == len(probes)
    assert summary["machine_closure_probes"] == len(probes)
    assert summary["acceptance_verifier_steps"] >= len(probes)
    assert summary["closure_readiness_packets"] == len(probes)
    assert summary["closure_readiness_fulfilled_checks"] >= len(probes)
    assert "closure_readiness_missing_checks" in summary
    assert len(runbook_candidates) == len(probes)
    assert len(payload.get("closure_readiness", [])) == len(probes)
    assert summary["open"] + summary["closed_by_current_probe"] == len(probes)

    for probe in probes:
        assert probe["owner"] == "abyss-stack"
        assert probe["stack_handoff"] is True
        assert probe["host_layer_mutates_stack"] is False
        assert probe.get("policy", {}).get("handoff_only") is True
        assert probe.get("policy", {}).get("read_only") is True
        assert probe.get("policy", {}).get("host_layer_mutates_stack") is False
        assert probe.get("policy", {}).get("executes_commands") is False
        assert probe.get("policy", {}).get("action_execution") is False
        assert probe.get("policy", {}).get("raw_secrets_included") is False
        assert probe["machine_read_command"] == "abyss-machine self-awareness requirement-probes --json"
        assert probe["source_handoff_command"] == "abyss-machine self-awareness requirements --json"
        assert probe.get("required_fields")
        assert probe.get("success_predicates")
        assert probe.get("redaction_rules")
        assert probe.get("acceptance_contract", {}).get("schema") == "abyss_machine_stack_requirement_acceptance_contract_v1"
        assert probe.get("machine_closure_probe", {}).get("kind") == probe.get("probe_kind")
        assert probe.get("machine_closure_probe", {}).get("required_fields")
        assert probe.get("machine_closure_probe", {}).get("success_predicates")
        assert probe.get("acceptance_verifiers")
        assert probe.get("closure_semantics", {}).get("host_layer_mutates_stack") is False
        assert probe.get("checks")
        _assert_evidence_refs(probe.get("evidence_refs"))
        assert any(check.get("key") == "acceptance_contract_probeable" and check.get("ok") is True for check in probe["checks"])
        assert any(check.get("key") == "host_layer_non_mutating" and check.get("ok") is True for check in probe["checks"])
        assert any(check.get("key") == "no_secret_leakage" and check.get("ok") is True for check in probe["checks"])
        assert any(check.get("key") == "runbook_candidate_complete" and check.get("ok") is True for check in probe["checks"])
        readiness = probe.get("closure_readiness", {})
        assert readiness in payload.get("closure_readiness", [])
        assert readiness.get("schema") == "abyss_machine_stack_handoff_closure_readiness_v1"
        assert readiness.get("requirement_id") == probe["id"]
        assert readiness.get("status") == probe["status"]
        assert isinstance(readiness.get("fulfilled_checks"), list)
        assert readiness.get("fulfilled_checks")
        assert isinstance(readiness.get("missing_checks"), list)
        assert readiness.get("open_blocker_count") == len(readiness.get("missing_checks", []))
        assert readiness.get("verifier_commands")
        assert readiness.get("safe_next_action", {}).get("requires_human_approval") is True
        assert readiness.get("safe_next_action", {}).get("host_layer_mutates_stack") is False
        assert readiness.get("policy", {}).get("host_layer_mutates_stack") is False
        assert readiness.get("policy", {}).get("executes_commands") is False
        assert readiness.get("policy", {}).get("automatic_remediation") is False
        if probe.get("closed_by_current_probe") is not True:
            assert readiness.get("missing_checks")
            assert readiness.get("closure_evidence_needed")

        runbook = probe.get("runbook_candidate", {})
        assert runbook in runbook_candidates
        assert runbook.get("schema") == "abyss_machine_stack_requirement_runbook_candidate_v1"
        assert runbook.get("requirement_id") == probe["id"]
        assert runbook.get("owner_route") == "abyss-stack"
        assert runbook.get("machine_action") == "handoff_only"
        assert runbook.get("host_layer_mutates_stack") is False
        assert runbook.get("machine_executes_stack_change") is False
        assert runbook.get("stack_owner_may_mutate_stack") is True
        assert runbook.get("operator_approval_required") is True
        assert runbook.get("risk", {}).get("risks")
        assert runbook.get("blast_radius", {}).get("affected_surfaces")
        assert runbook.get("rollback", {}).get("steps")
        assert runbook.get("acceptance_steps")
        assert runbook.get("acceptance_verifiers")
        assert runbook.get("acceptance_verifiers") == runbook.get("acceptance_steps")
        _assert_evidence_refs(runbook.get("evidence_refs"))

    grafana_probe = next((probe for probe in probes if probe.get("id") == "stack.grafana.datasource-read"), None)
    if grafana_probe:
        current = grafana_probe.get("current_state", {})
        assert current.get("health_ok") is True
        assert current.get("health_status_code") == 200
        assert current.get("grafana_version")
        assert current.get("grafana_database") == "ok"
        assert current.get("datasource_api_auth_denied") is True
        assert current.get("datasource_inventory_present") is False
        assert current.get("inferred_datasource_candidate_count", 0) >= 2
        assert "prometheus" in current.get("inferred_datasource_candidate_types", [])
        assert "loki" in current.get("inferred_datasource_candidate_types", [])
        assert current.get("inferred_candidates_are_not_inventory") is True
        check_by_key = {check.get("key"): check for check in grafana_probe.get("checks", [])}
        assert check_by_key.get("grafana_health_readable", {}).get("ok") is True
        assert check_by_key.get("grafana_datasource_candidates_inferred", {}).get("ok") is True
        assert check_by_key.get("grafana_datasource_api_auth_denied", {}).get("ok") is True
        assert check_by_key.get("grafana_datasource_inventory_readable", {}).get("level") == "open"

    trace_probe = next((probe for probe in probes if probe.get("id") == "stack.trace-backend"), None)
    if trace_probe:
        current = trace_probe.get("current_state", {})
        assert current.get("metrics_log_pipeline_readable") is True
        assert current.get("alloy_seen") is True
        assert current.get("loki_ready") is True
        assert current.get("loki_labels_readable") is True
        assert current.get("traceparent_log_query_ok") is True
        check_by_key = {check.get("key"): check for check in trace_probe.get("checks", [])}
        assert check_by_key.get("trace_pipeline_evidence_readable", {}).get("ok") is True
        assert check_by_key.get("traceparent_log_context_queryable", {}).get("ok") is True
        if current.get("trace_backend_ready") is True:
            assert current.get("trace_search_readable") is True
            assert current.get("span_log_metric_join_supported") is True
            assert check_by_key.get("trace_backend_ready", {}).get("ok") is True
            assert check_by_key.get("trace_span_search_readable", {}).get("ok") is True
            assert check_by_key.get("span_log_metric_join_supported", {}).get("ok") is True
        else:
            assert current.get("trace_search_readable") is False
            assert current.get("span_log_metric_join_supported") is False
            assert check_by_key.get("trace_backend_ready", {}).get("level") == "open"
            assert check_by_key.get("trace_span_search_readable", {}).get("level") == "open"
            assert check_by_key.get("span_log_metric_join_supported", {}).get("level") == "open"

    trace_context = _run_json(run_abyss_machine, "self-awareness", "trace-context", "--json", timeout=120.0)
    assert trace_context["schema"] == "abyss_machine_self_awareness_trace_context_fallback_v1"
    assert trace_context["ok"] is True
    assert trace_context["stack_requirement_id"] == "stack.trace-backend"
    assert trace_context["closes_stack_requirement"] is False
    assert trace_context.get("policy", {}).get("host_layer_mutates_stack") is False
    assert trace_context.get("policy", {}).get("closes_stack_requirement") is False
    assert trace_context.get("policy", {}).get("adds_loki_labels") is False
    assert trace_context.get("policy", {}).get("raw_span_payloads_stored") is False
    assert trace_context.get("policy", {}).get("raw_log_exports_stored") is False
    summary = trace_context.get("summary", {})
    assert summary.get("traceparent_log_query_ok") is True
    assert summary.get("stack_requirement_not_closed_by_fallback") is True
    assert trace_context.get("fallback", {}).get("loki_trace_context", {}).get("raw_log_exports_stored") is False
    assert trace_context.get("safe_next_action", {}).get("owner_route") == "abyss-stack"
    assert trace_context.get("safe_next_action", {}).get("host_layer_mutates_stack") is False

    database_probe = next((probe for probe in probes if probe.get("id") == "stack.database-graph.read-route"), None)
    if database_probe:
        current = database_probe.get("current_state", {})
        assert current.get("route_api_health_ok") is True
        assert current.get("route_api_openapi_ok") is True
        assert current.get("route_api_openapi_path_count", 0) >= 1
        assert any(row.get("path") == "/health" for row in current.get("route_api_openapi_paths", []))
        assert current.get("rag_api_health_ok") is True
        assert current.get("rag_api_openapi_ok") is True
        assert current.get("rag_api_openapi_path_count", 0) >= 1
        assert any(row.get("path") == "/collections" for row in current.get("rag_api_openapi_paths", []))
        assert "abyss_stack_rag_chunks_v1" in current.get("rag_collection_names", [])
        assert current.get("rag_source_count", 0) >= 1
        assert current.get("postgres_tcp_ready") is True
        assert current.get("neo4j_root_readable") is True
        assert current.get("neo4j_version")
        check_by_key = {check.get("key"): check for check in database_probe.get("checks", [])}
        assert check_by_key.get("route_api_health_openapi_readable", {}).get("ok") is True
        assert check_by_key.get("rag_api_inventory_routes_readable", {}).get("ok") is True
        assert check_by_key.get("database_endpoint_metadata_readable", {}).get("ok") is True
        if database_probe.get("status") == "open":
            assert check_by_key.get("database_graph_inventory_route_present", {}).get("level") == "open"

    langchain_probe = next((probe for probe in probes if probe.get("id") == "stack.langchain-api.graph-observability"), None)
    if langchain_probe:
        current = langchain_probe.get("current_state", {})
        assert current.get("api_health_ok") is True
        assert current.get("openapi_ok") is True
        assert current.get("langchain_api_base_url") == "http://127.0.0.1:5403"
        assert current.get("health_service") == "langchain-api"
        assert current.get("embeddings_provider") == "ovms"
        assert current.get("ovms_auth_enabled") is True
        assert current.get("federated_run_enabled") is True
        assert current.get("openapi_path_count", 0) >= 1
        assert any(row.get("path") == "/health" for row in current.get("openapi_paths", []))
        assert any(row.get("path") == "/run" for row in current.get("openapi_paths", []))
        assert any(row.get("path") == "/run/federated" for row in current.get("openapi_paths", []))
        assert any(row.get("path") == "/embeddings" for row in current.get("openapi_paths", []))
        assert current.get("run_route_present") is True
        assert current.get("federated_run_route_present") is True
        assert current.get("embeddings_route_present") is True
        assert current.get("runtime_surface_usable") is True
        assert "threads" in current.get("missing_replay_inventory", [])
        assert "checkpoints" in current.get("missing_replay_inventory", [])
        assert "traces" in current.get("missing_replay_inventory", [])
        check_by_key = {check.get("key"): check for check in langchain_probe.get("checks", [])}
        assert check_by_key.get("langchain_api_health_readable", {}).get("ok") is True
        assert check_by_key.get("langchain_api_openapi_readable", {}).get("ok") is True
        assert check_by_key.get("langchain_runtime_routes_readable", {}).get("ok") is True
        if current.get("trace_backend_ready") is True:
            assert check_by_key.get("langchain_trace_backend_coupled", {}).get("ok") is True
        else:
            assert check_by_key.get("langchain_trace_backend_coupled", {}).get("level") == "open"
        assert check_by_key.get("langchain_langgraph_inventory_readable", {}).get("level") == "open"
        if langchain_probe.get("status") == "open":
            assert check_by_key.get("langchain_langgraph_inventory_readable", {}).get("level") == "open"


def test_live_self_awareness_brief_exposes_stack_handoff_action_map(run_abyss_machine) -> None:
    payload = _run_json(run_abyss_machine, "self-awareness", "brief", "--json", timeout=120.0)

    assert payload["schema"] == "abyss_machine_self_awareness_brief_v1"
    assert payload["ok"] is True
    assert payload.get("policy", {}).get("host_layer_mutates_stack") is False
    assert payload.get("policy", {}).get("actions_executed") is False
    assert payload.get("policy", {}).get("open_stack_requirements_are_blockers_not_host_failures") is True

    action_map = payload.get("stack_handoff_action_map", {})
    actions = action_map.get("actions", [])
    safe_next = payload.get("safe_next_action", {})
    assert action_map.get("schema") == "abyss_machine_self_awareness_brief_stack_handoff_action_map_v1"
    assert action_map.get("ok") is True
    assert action_map.get("policy", {}).get("host_layer_mutates_stack") is False
    assert action_map.get("policy", {}).get("executes_commands") is False
    assert action_map.get("policy", {}).get("raw_secrets_included") is False
    assert action_map.get("summary", {}).get("open_stack_requirements") == len(actions)
    assert payload.get("summary", {}).get("stack_handoff_actions") == len(actions)
    assert payload.get("summary", {}).get("stack_handoff_verifier_steps") == action_map.get("summary", {}).get("acceptance_verifier_steps")
    assert set(action_map.get("open_requirement_ids", [])) == {action.get("requirement_id") for action in actions}
    assert safe_next.get("requires_human_approval") is True
    assert safe_next.get("automatic") is False
    assert safe_next.get("executes_commands") is False
    assert safe_next.get("host_layer_mutates_stack") is False
    assert safe_next.get("command") == "abyss-machine self-awareness export --json"

    if actions:
        assert action_map.get("summary", {}).get("top_requirement_id") == actions[0].get("requirement_id")
        assert actions[0].get("priority_rank") == 1
        assert actions[0].get("priority_class")
    for action in actions:
        assert action.get("owner_route") == "abyss-stack"
        assert action.get("policy", {}).get("handoff_only") is True
        assert action.get("policy", {}).get("host_layer_mutates_stack") is False
        assert action.get("policy", {}).get("executes_commands") is False
        assert action.get("closure_blockers")
        assert action.get("closure_blocker_keys")
        assert action.get("acceptance_verifiers")
        assert action.get("verifier_commands")
        assert action.get("runbook_candidate", {}).get("machine_executes_stack_change") is False
        assert action.get("runbook_candidate", {}).get("host_layer_mutates_stack") is False
        assert action.get("safe_next_action", {}).get("requires_human_approval") is True
        assert action.get("safe_next_action", {}).get("automatic") is False
        _assert_evidence_refs(action.get("evidence_refs"))


def test_live_self_awareness_response_layer_preserves_episode_lineage(run_abyss_machine) -> None:
    probe = _run_json(run_abyss_machine, "self-awareness", "probe", "--json", timeout=180.0)
    assert probe["ok"] is True
    lineage = probe.get("e2e_lineage_proof", {})
    assert lineage.get("schema") == "abyss_machine_self_awareness_e2e_lineage_proof_v1"
    assert lineage.get("ok") is True
    assert lineage.get("run_id") == probe.get("run_id")
    assert lineage.get("traceparent") == probe.get("traceparent")
    assert lineage.get("summary", {}).get("missing_rows") == []
    assert lineage.get("summary", {}).get("rows", 0) >= 15
    assert lineage.get("summary", {}).get("synthetic_event_ids", 0) >= 3
    assert probe.get("summary", {}).get("e2e_lineage_ok") is True
    lineage_ids = {row.get("id") for row in lineage.get("rows", [])}
    assert {
        "synthetic_request",
        "signal_fabric",
        "trace_context_fallback",
        "query_and_correlation",
        "timeline",
        "spatial_graph",
        "causal_episode",
        "alert",
        "warm_e2b_context",
        "rag_memory",
        "nervous_freshness",
        "langgraph_investigation",
        "replay",
        "reaction_candidate",
        "governed_response",
        "export",
    }.issubset(lineage_ids)
    for row in lineage.get("rows", []):
        assert row.get("schema") == "abyss_machine_self_awareness_e2e_lineage_row_v1"
        assert row.get("satisfied") is True
        assert row.get("artifacts_ok") is True
        assert row.get("chain", {}).get("satisfied") is True
        assert row.get("policy", {}).get("host_layer_mutates_stack") is False
        assert row.get("policy", {}).get("actions_executed") is False
        _assert_evidence_refs(row.get("evidence_refs"))

    alerts = _run_json(run_abyss_machine, "self-awareness", "alerts", "--json", timeout=120.0)
    reactions = _run_json(run_abyss_machine, "reactions", "--json", timeout=90.0)
    responses = _run_json(run_abyss_machine, "responses", "--json", timeout=90.0)
    reactions_validate = _run_json(run_abyss_machine, "reactions", "validate", "--json", timeout=90.0)
    responses_validate = _run_json(run_abyss_machine, "responses", "validate", "--json", timeout=90.0)

    assert alerts["schema"] == "abyss_machine_self_awareness_alerts_v1"
    assert alerts["ok"] is True
    assert alerts["summary"]["response_depth_candidates"] == alerts["summary"]["reaction_candidates"]
    assert alerts["summary"]["response_depth_missing"] == 0
    assert alerts["summary"]["body_trace_candidates"] == alerts["summary"]["reaction_candidates"]
    assert alerts["summary"]["body_trace_missing"] == 0
    assert reactions["summary"]["self_awareness_response_depth"] >= 1
    assert responses["summary"]["self_awareness_response_routes"] >= 1
    assert responses["summary"]["self_awareness_response_depth"] == responses["summary"]["self_awareness_response_routes"]
    assert responses["summary"]["self_awareness_body_trace_routes"] == responses["summary"]["self_awareness_response_routes"]
    assert responses["summary"]["self_awareness_body_trace_missing"] == 0
    assert responses.get("self_awareness", {}).get("body_trace_missing") == 0
    assert responses["summary"]["automatic_responses"] == 0
    assert responses["summary"]["routes_with_mutating_command_if_run"] == 0
    assert "host_owner_gap_candidates" in reactions["summary"]
    assert "host_owner_gap_routes" in responses["summary"]
    assert "working_stack_activation_gap_candidates" in reactions["summary"]
    assert "working_stack_activation_gap_routes" in responses["summary"]
    assert "stack_requirement_handoff_candidates" in reactions["summary"]
    assert "stack_requirement_handoff_routes" in responses["summary"]
    assert "memory_hotpath_candidates" in reactions["summary"]
    assert "memory_hotpath_routes" in responses["summary"]
    assert "doctor_warning_candidates" in reactions["summary"]
    assert "doctor_warning_routes" in responses["summary"]
    assert "desktop_compositor_pressure_candidates" in reactions["summary"]
    assert "desktop_compositor_pressure_routes" in responses["summary"]
    assert "nervous_retention_privacy_candidates" in reactions["summary"]
    assert "nervous_retention_privacy_routes" in responses["summary"]

    candidates = [item for item in reactions.get("candidates", []) if item.get("category") == "self-awareness"]
    routes = [item for item in responses.get("routes", []) if item.get("category") == "self-awareness"]
    host_gap_candidates = [item for item in reactions.get("candidates", []) if isinstance(item.get("host_owner_gap"), dict)]
    host_gap_routes = [item for item in responses.get("routes", []) if isinstance(item.get("host_owner_gap"), dict)]
    nervous_gate_candidates = [
        item for item in reactions.get("candidates", [])
        if item.get("id") in {"nervous-readiness-not-ready", "nervous-semantic-maintenance-needed"}
    ]
    nervous_gate_routes = [
        item for item in responses.get("routes", [])
        if item.get("candidate_id") in {"nervous-readiness-not-ready", "nervous-semantic-maintenance-needed"}
    ]
    memory_hotpath_candidates = [
        item for item in reactions.get("candidates", [])
        if str(item.get("id") or "").startswith("memory-hotpath-probe")
    ]
    memory_hotpath_routes = [
        item for item in responses.get("routes", [])
        if str(item.get("candidate_id") or "").startswith("memory-hotpath-probe")
    ]
    doctor_warning_candidates = [
        item for item in reactions.get("candidates", [])
        if item.get("id") == "doctor-warnings-present"
    ]
    doctor_warning_routes = [
        item for item in responses.get("routes", [])
        if item.get("candidate_id") == "doctor-warnings-present"
    ]
    desktop_compositor_candidates = [
        item for item in reactions.get("candidates", [])
        if item.get("id") == "desktop-compositor-pressure-review"
    ]
    desktop_compositor_routes = [
        item for item in responses.get("routes", [])
        if item.get("candidate_id") == "desktop-compositor-pressure-review"
    ]
    nervous_retention_candidates = [
        item for item in reactions.get("candidates", [])
        if item.get("id") == "nervous-retention-review"
    ]
    nervous_retention_routes = [
        item for item in responses.get("routes", [])
        if item.get("candidate_id") == "nervous-retention-review"
    ]
    assert candidates
    assert routes
    assert len(host_gap_routes) == len(host_gap_candidates)
    host_gap_route_by_candidate = {item.get("candidate_id"): item for item in host_gap_routes}
    for candidate in host_gap_candidates:
        assert candidate.get("automatic") is False
        assert candidate.get("owner_route") == "abyss-machine:root-operator"
        assert candidate.get("safe_next_action", {}).get("requires_human_approval") is True
        assert candidate.get("safe_next_action", {}).get("executes_commands") is False
        assert candidate.get("host_owner_gap", {}).get("policy", {}).get("host_layer_mutates_stack") is False
        route = host_gap_route_by_candidate.get(candidate.get("id"))
        assert route
        assert route.get("host_owner_gap") == candidate.get("host_owner_gap")
        assert route.get("safe_next_action") == candidate.get("safe_next_action")
        assert route.get("runbook_candidate") == candidate.get("runbook_candidate")
        assert route.get("policy", {}).get("host_owner_gap_route") is True
        assert route.get("suggestion", {}).get("command_profile", {}).get("mutating_if_run") is False

    assert len(nervous_gate_routes) == len(nervous_gate_candidates)
    nervous_gate_route_by_candidate = {item.get("candidate_id"): item for item in nervous_gate_routes}
    for candidate in nervous_gate_candidates:
        gate = candidate.get("resource_gate", {})
        assert gate.get("schema") == "abyss_machine_nervous_semantic_resource_gate_v1"
        assert gate.get("policy", {}).get("does_not_bypass_resource_gate") is True
        assert gate.get("safe_next_action", {}).get("executes_commands") is False
        assert gate.get("safe_next_action", {}).get("host_layer_mutates_stack") is False
        assert gate.get("evidence_refs")
        route = nervous_gate_route_by_candidate.get(candidate.get("id"))
        assert route
        route_gate = route.get("resource_gate", {})
        assert route_gate.get("schema") == gate.get("schema")
        assert route_gate.get("status") == gate.get("status")
        assert route_gate.get("decision") == gate.get("decision")
        assert route_gate.get("blocked_reasons") == gate.get("blocked_reasons")
        assert route_gate.get("semantic", {}).get("delta_chunks") == gate.get("semantic", {}).get("delta_chunks")
        assert route_gate.get("source_index", {}).get("records_lag") == gate.get("source_index", {}).get("records_lag")
        assert route_gate.get("game_guard", {}).get("active") == gate.get("game_guard", {}).get("active")
        assert route_gate.get("policy", {}).get("does_not_bypass_resource_gate") is True
        assert route.get("safe_next_action") == candidate.get("safe_next_action")
        assert route.get("suggestion", {}).get("command_profile", {}).get("mutating_if_run") is False
        assert route.get("executes") is False
    assert len(memory_hotpath_routes) == len(memory_hotpath_candidates)
    memory_hotpath_route_by_candidate = {item.get("candidate_id"): item for item in memory_hotpath_routes}
    for candidate in memory_hotpath_candidates:
        hotpath_route = candidate.get("memory_hotpath_route", {})
        assert hotpath_route.get("schema") == "abyss_machine_memory_hotpath_probe_route_v1"
        assert hotpath_route.get("complete") is True
        assert hotpath_route.get("measurement_status") in {
            "latest_failed",
            "stale",
            "fresh_watch",
            "fresh_unknown",
            "missing_required_before_persistent_cgroup_policy",
        }
        assert hotpath_route.get("latency", {}) != {}
        assert hotpath_route.get("swap", {}) != {}
        assert hotpath_route.get("safe_next_action", {}).get("executes_commands") is False
        assert hotpath_route.get("safe_next_action", {}).get("host_layer_mutates_stack") is False
        assert hotpath_route.get("safe_next_action", {}).get("does_not_apply_cgroup_properties") is True
        assert hotpath_route.get("policy", {}).get("does_not_stop_disable_restart_or_throttle_services") is True
        route = memory_hotpath_route_by_candidate.get(candidate.get("id"))
        assert route
        route_hotpath = route.get("memory_hotpath_route", {})
        assert route_hotpath.get("schema") == hotpath_route.get("schema")
        assert route_hotpath.get("measurement_status") == hotpath_route.get("measurement_status")
        assert route_hotpath.get("issues") == hotpath_route.get("issues")
        assert route_hotpath.get("findings") == hotpath_route.get("findings")
        assert route_hotpath.get("latency") == hotpath_route.get("latency")
        assert route_hotpath.get("swap") == hotpath_route.get("swap")
        assert route_hotpath.get("policy") == hotpath_route.get("policy")
        assert route.get("safe_next_action") == hotpath_route.get("safe_next_action")
        assert route.get("suggestion", {}).get("command_profile", {}).get("mutating_if_run") is False
        assert route.get("executes") is False
    assert len(doctor_warning_routes) == len(doctor_warning_candidates)
    doctor_warning_route_by_candidate = {item.get("candidate_id"): item for item in doctor_warning_routes}
    for candidate in doctor_warning_candidates:
        doctor_route = candidate.get("doctor_warning_route", {})
        assert doctor_route.get("schema") == "abyss_machine_doctor_warning_route_v1"
        assert doctor_route.get("complete") is True
        assert doctor_route.get("doctor", {}).get("warnings", 0) > 0
        assert doctor_route.get("warning_checks")
        assert doctor_route.get("warning_keys")
        assert doctor_route.get("safe_next_action", {}).get("executes_commands") is False
        assert doctor_route.get("safe_next_action", {}).get("host_layer_mutates_stack") is False
        assert doctor_route.get("safe_next_action", {}).get("clears_change_ledger") is False
        assert doctor_route.get("safe_next_action", {}).get("runs_heavy_maintenance") is False
        assert doctor_route.get("policy", {}).get("review_only") is True
        route = doctor_warning_route_by_candidate.get(candidate.get("id"))
        assert route
        route_doctor = route.get("doctor_warning_route", {})
        assert route_doctor.get("schema") == doctor_route.get("schema")
        assert route_doctor.get("warning_keys") == doctor_route.get("warning_keys")
        assert route_doctor.get("doctor", {}).get("warnings") == doctor_route.get("doctor", {}).get("warnings")
        assert route_doctor.get("policy") == doctor_route.get("policy")
        assert route.get("safe_next_action") == doctor_route.get("safe_next_action")
        assert route.get("suggestion", {}).get("command_profile", {}).get("mutating_if_run") is False
        assert route.get("executes") is False
    assert len(desktop_compositor_routes) == len(desktop_compositor_candidates)
    desktop_compositor_route_by_candidate = {item.get("candidate_id"): item for item in desktop_compositor_routes}
    for candidate in desktop_compositor_candidates:
        compositor_route = candidate.get("desktop_compositor_route", {})
        assert compositor_route.get("schema") == "abyss_machine_desktop_compositor_pressure_route_v1"
        assert compositor_route.get("complete") is True
        assert compositor_route.get("classification")
        assert isinstance(compositor_route.get("pressure", {}), dict)
        assert isinstance(compositor_route.get("display", {}), dict)
        assert isinstance(compositor_route.get("churn", {}), dict)
        assert compositor_route.get("safe_next_action", {}).get("executes_commands") is False
        assert compositor_route.get("safe_next_action", {}).get("host_layer_mutates_stack") is False
        assert compositor_route.get("safe_next_action", {}).get("does_not_kill_or_throttle") is True
        assert compositor_route.get("safe_next_action", {}).get("does_not_toggle_gnome_extensions") is True
        assert compositor_route.get("safe_next_action", {}).get("does_not_lower_refresh_or_quality") is True
        assert compositor_route.get("policy", {}).get("observe_only") is True
        assert compositor_route.get("policy", {}).get("mutates_desktop_state") is False
        assert compositor_route.get("policy", {}).get("redacts_process_cmdline") is True
        top_hint = compositor_route.get("pressure", {}).get("top_desktop_cpu_candidate")
        if isinstance(top_hint, dict):
            assert "cmdline" not in top_hint
        route = desktop_compositor_route_by_candidate.get(candidate.get("id"))
        assert route
        route_compositor = route.get("desktop_compositor_route", {})
        assert route_compositor.get("schema") == compositor_route.get("schema")
        assert route_compositor.get("classification") == compositor_route.get("classification")
        assert route_compositor.get("pressure") == compositor_route.get("pressure")
        assert route_compositor.get("display") == compositor_route.get("display")
        assert route_compositor.get("churn") == compositor_route.get("churn")
        assert route_compositor.get("policy") == compositor_route.get("policy")
        assert route.get("safe_next_action") == compositor_route.get("safe_next_action")
        assert route.get("suggestion", {}).get("command_profile", {}).get("kind") == "read_only_probe"
        assert route.get("suggestion", {}).get("command_profile", {}).get("mutating_if_run") is False
        assert route.get("executes") is False
    assert len(nervous_retention_routes) == len(nervous_retention_candidates)
    nervous_retention_route_by_candidate = {item.get("candidate_id"): item for item in nervous_retention_routes}
    for candidate in nervous_retention_candidates:
        retention_route = candidate.get("nervous_retention_route", {})
        assert retention_route.get("schema") == "abyss_machine_nervous_retention_privacy_route_v1"
        assert retention_route.get("complete") is True
        assert retention_route.get("summary", {}).get("candidates", 0) > 0 or retention_route.get("summary", {}).get("route_errors", 0) > 0
        assert isinstance(retention_route.get("candidate_layers"), list)
        assert isinstance(retention_route.get("by_layer"), dict)
        assert "candidates" not in retention_route
        assert retention_route.get("safe_next_action", {}).get("dry_run_command") == "abyss-machine nervous retention-apply --dry-run --json"
        assert retention_route.get("safe_next_action", {}).get("requires_explicit_confirm_for_deletion") is True
        assert retention_route.get("safe_next_action", {}).get("executes_commands") is False
        assert retention_route.get("safe_next_action", {}).get("host_layer_mutates_stack") is False
        assert retention_route.get("safe_next_action", {}).get("does_not_delete_facts") is True
        assert retention_route.get("safe_next_action", {}).get("does_not_delete_project_roots") is True
        assert retention_route.get("policy", {}).get("dry_run_first") is True
        assert retention_route.get("policy", {}).get("default_apply_dry_run") is True
        assert retention_route.get("policy", {}).get("facts_delete_behavior_explicit_forget_only") is True
        assert retention_route.get("policy", {}).get("no_project_repo_mutation") is True
        assert retention_route.get("policy", {}).get("raw_private_content") is False
        route = nervous_retention_route_by_candidate.get(candidate.get("id"))
        assert route
        route_retention = route.get("nervous_retention_route", {})
        assert route_retention.get("schema") == retention_route.get("schema")
        assert route_retention.get("summary") == retention_route.get("summary")
        assert route_retention.get("candidate_layers") == retention_route.get("candidate_layers")
        assert route_retention.get("by_layer") == retention_route.get("by_layer")
        assert route_retention.get("policy") == retention_route.get("policy")
        assert route.get("safe_next_action") == retention_route.get("safe_next_action")
        assert route.get("suggestion", {}).get("command_profile", {}).get("kind") == "owner_gated_retention_dry_run"
        assert route.get("suggestion", {}).get("command_profile", {}).get("mutating_if_run") is False
        assert route.get("executes") is False
    candidate_by_id = {item["id"]: item for item in candidates}
    for candidate in candidates:
        contract = candidate.get("response_contract", {})
        assert contract.get("schema") == "abyss_machine_self_awareness_response_contract_v1"
        assert candidate.get("episode_id") == contract.get("validated_episode", {}).get("episode_id")
        assert contract.get("response_lineage", {}).get("schema") == "abyss_machine_self_awareness_response_lineage_v1"
        assert contract.get("response_lineage", {}).get("complete") is True
        assert candidate.get("body_trace") == contract.get("body_trace")
        assert contract.get("body_trace", {}).get("schema") == "abyss_machine_self_awareness_body_trace_v1"
        assert contract.get("body_trace", {}).get("complete") is True
        assert contract.get("body_trace", {}).get("host_body", {}).get("complete") is True
        assert contract.get("body_trace", {}).get("policy", {}).get("host_layer_mutates_stack") is False
        assert contract.get("body_trace", {}).get("policy", {}).get("stores_raw_body") is False
        if contract.get("validated_episode", {}).get("episode_kind") == "working_stack_usage_gap":
            assert contract.get("episode_specific_evidence", {}).get("source_kind") == "activation_smoke_matrix"
            assert contract.get("episode_specific_evidence", {}).get("complete") is True
            assert contract.get("investigation", {}).get("matches_episode") is True
            assert contract.get("replay", {}).get("matches_investigation") is True
            activation_route = contract.get("activation_gap_route", {})
            assert candidate.get("activation_gap_route") == activation_route
            assert activation_route.get("schema") == "abyss_machine_self_awareness_working_stack_activation_gap_route_v1"
            assert activation_route.get("complete") is True
            assert activation_route.get("service") == candidate.get("working_stack_gap_service")
            assert activation_route.get("classification") in {
                "running_functional_smoke_failed",
                "running_probe_failed",
                "exited_stack_managed_container",
                "declared_without_running_runtime",
                "endpoint_probe_gap",
                "model_runtime_link_gap",
                "deep_usage_route_unproven",
                "working_stack_potential_unclassified",
            }
            assert activation_route.get("current_state", {}).get("runtime", {})
            assert activation_route.get("activation_smoke", {}).get("row_complete") is True
            assert activation_route.get("safe_next_action", {}).get("host_layer_mutates_stack") is False
            assert activation_route.get("safe_next_action", {}).get("executes_commands") is False
            assert activation_route.get("policy", {}).get("host_layer_mutates_stack") is False
            assert activation_route.get("policy", {}).get("executes_commands") is False
        if contract.get("validated_episode", {}).get("episode_kind") == "stack_handoff_blocker":
            assert contract.get("episode_specific_evidence", {}).get("source_kind") == "stack_closure_dossier_and_stack_handoff_replay"
            assert contract.get("episode_specific_evidence", {}).get("complete") is True
            stack_route = contract.get("stack_requirement_route", {})
            assert candidate.get("stack_requirement_route") == stack_route
            assert stack_route.get("schema") == "abyss_machine_self_awareness_stack_requirement_handoff_route_v1"
            assert stack_route.get("complete") is True
            assert stack_route.get("requirement_id") == candidate.get("stack_handoff_requirement_id")
            assert stack_route.get("owner_route") == "abyss-stack"
            assert stack_route.get("lineage", {}).get("stack_handoff_replayable") is True
            assert stack_route.get("lineage", {}).get("open_requirement_present_in_replay") is True
            assert stack_route.get("impact", {}).get("coverage_planes")
            assert stack_route.get("closure_acceptance", {}).get("complete") is True
            assert stack_route.get("safe_next_action", {}).get("host_layer_mutates_stack") is False
            assert stack_route.get("safe_next_action", {}).get("executes_commands") is False
            assert stack_route.get("policy", {}).get("host_layer_mutates_stack") is False
            assert stack_route.get("policy", {}).get("executes_commands") is False
        assert candidate.get("risk") == contract.get("risk")
        assert candidate.get("blast_radius") == contract.get("blast_radius")
        assert candidate.get("rollback") == contract.get("rollback")
        assert candidate.get("runbook_candidate") == contract.get("runbook_candidate")
        assert contract.get("approval", {}).get("required") is True
        assert contract.get("policy", {}).get("automatic_action") is False
        assert contract.get("policy", {}).get("automatic_response") is False
        assert contract.get("policy", {}).get("executes_commands") is False
        assert contract.get("policy", {}).get("host_layer_mutates_stack") is False
        assert contract.get("risk", {}).get("risks")
        assert contract.get("blast_radius", {}).get("affected_surfaces")
        assert contract.get("rollback", {}).get("steps")
        assert contract.get("runbook_candidate", {}).get("acceptance_verifiers")
        _assert_evidence_refs(contract.get("evidence_refs"))

    for route in routes:
        contract = route.get("response_contract", {})
        assert route.get("candidate_id") in candidate_by_id
        assert route.get("route_id") == route.get("id")
        assert route.get("validated_episode") == contract.get("validated_episode")
        assert route.get("risk") == contract.get("risk")
        assert route.get("blast_radius") == contract.get("blast_radius")
        assert route.get("rollback") == contract.get("rollback")
        assert route.get("runbook_candidate") == contract.get("runbook_candidate")
        assert route.get("body_trace") == contract.get("body_trace")
        assert route.get("approval", {}).get("required") is True
        assert route.get("automatic") is False
        assert route.get("executes") is False
        assert route.get("policy", {}).get("automatic_response") is False
        assert route.get("policy", {}).get("executes_commands") is False
        assert route.get("policy", {}).get("host_layer_mutates_stack") is False
        if contract.get("validated_episode", {}).get("episode_kind") == "working_stack_usage_gap":
            assert route.get("activation_gap_route") == contract.get("activation_gap_route")
            assert route.get("activation_gap_route", {}).get("complete") is True
        if contract.get("validated_episode", {}).get("episode_kind") == "stack_handoff_blocker":
            assert route.get("stack_requirement_route") == contract.get("stack_requirement_route")
            assert route.get("stack_requirement_route", {}).get("complete") is True

    assert reactions_validate["ok"] is True
    assert reactions_validate["summary"]["fails"] == 0
    assert any((check.get("key") or check.get("id")) == "self_awareness_response_candidate_depth" for check in reactions_validate.get("checks", []))
    assert any((check.get("key") or check.get("id")) == "host_owner_gap_candidates" for check in reactions_validate.get("checks", []))
    assert any((check.get("key") or check.get("id")) == "nervous_resource_gate_candidates" for check in reactions_validate.get("checks", []))
    assert any((check.get("key") or check.get("id")) == "working_stack_activation_gap_candidates" for check in reactions_validate.get("checks", []))
    assert any((check.get("key") or check.get("id")) == "stack_requirement_handoff_candidates" for check in reactions_validate.get("checks", []))
    assert any((check.get("key") or check.get("id")) == "memory_hotpath_probe_candidates" for check in reactions_validate.get("checks", []))
    assert any((check.get("key") or check.get("id")) == "doctor_warning_candidates" for check in reactions_validate.get("checks", []))
    assert any((check.get("key") or check.get("id")) == "desktop_compositor_pressure_candidates" for check in reactions_validate.get("checks", []))
    assert any((check.get("key") or check.get("id")) == "nervous_retention_privacy_candidates" for check in reactions_validate.get("checks", []))
    assert responses_validate["ok"] is True
    assert responses_validate["summary"]["fails"] == 0
    assert any((check.get("key") or check.get("id")) == "self_awareness_response_route_depth" for check in responses_validate.get("checks", []))
    assert any((check.get("key") or check.get("id")) == "self_awareness_response_body_trace" for check in responses_validate.get("checks", []))
    assert any((check.get("key") or check.get("id")) == "host_owner_gap_response_routes" for check in responses_validate.get("checks", []))
    assert any((check.get("key") or check.get("id")) == "nervous_resource_gate_response_routes" for check in responses_validate.get("checks", []))
    assert any((check.get("key") or check.get("id")) == "working_stack_activation_gap_response_routes" for check in responses_validate.get("checks", []))
    assert any((check.get("key") or check.get("id")) == "stack_requirement_handoff_response_routes" for check in responses_validate.get("checks", []))
    assert any((check.get("key") or check.get("id")) == "memory_hotpath_probe_response_routes" for check in responses_validate.get("checks", []))
    assert any((check.get("key") or check.get("id")) == "doctor_warning_response_routes" for check in responses_validate.get("checks", []))
    assert any((check.get("key") or check.get("id")) == "desktop_compositor_pressure_response_routes" for check in responses_validate.get("checks", []))
    assert any((check.get("key") or check.get("id")) == "nervous_retention_privacy_response_routes" for check in responses_validate.get("checks", []))


def test_live_self_awareness_stack_handoff_episodes_route_to_alerts(run_abyss_machine) -> None:
    episodes = _run_json(run_abyss_machine, "self-awareness", "episodes", "--json", timeout=180.0)
    stack_episodes = [
        episode for episode in episodes.get("episodes", [])
        if episode.get("episode_kind") == "stack_handoff_blocker"
    ]
    working_gap_episodes = [
        episode for episode in episodes.get("episodes", [])
        if episode.get("episode_kind") == "working_stack_usage_gap"
    ]
    host_service_episodes = [
        episode for episode in episodes.get("episodes", [])
        if episode.get("episode_kind") == "host_service_state"
    ]
    stack_episode_ids = {episode.get("episode_id") for episode in stack_episodes}
    working_gap_episode_ids = {episode.get("episode_id") for episode in working_gap_episodes}
    host_service_episode_ids = {episode.get("episode_id") for episode in host_service_episodes}

    assert episodes["schema"] == "abyss_machine_self_awareness_episodes_v1"
    assert episodes["ok"] is True
    assert episodes["summary"]["stack_handoff_episodes"] == len(stack_episodes)
    assert episodes["summary"]["stack_handoff_episodes"] == len(episodes.get("stack_handoff_episode_ids", []))
    assert episodes["summary"]["open_stack_requirements"] == len(stack_episodes)
    assert episodes["summary"]["working_stack_gap_episodes"] == len(working_gap_episodes)
    assert episodes["summary"]["working_stack_gap_episodes"] == len(episodes.get("working_stack_gap_episode_ids", []))
    assert episodes["summary"]["host_service_episodes"] == len(host_service_episodes)
    assert episodes["summary"]["host_service_episodes"] == len(episodes.get("host_service_episode_ids", []))
    assert host_service_episode_ids == set(episodes.get("host_service_episode_ids", []))
    for episode in stack_episodes:
        assert episode.get("truth_level") == "handoff_candidate"
        assert episode.get("owner_route") == "abyss-stack"
        assert episode.get("event_ids") == []
        assert {"stack_handoff", "requirement_probe", "spatial_graph"}.issubset(set(episode.get("primary_signals", [])))
        assert any(str(node).startswith("stack_requirement:") for node in episode.get("affected_spatial_nodes", []))
        assert any(str(node).startswith("stack_handoff_action:") for node in episode.get("affected_spatial_nodes", []))
        assert episode.get("stack_handoff", {}).get("closure_blocker_keys")
        assert episode.get("stack_handoff", {}).get("runbook_candidate_id")
        assert episode.get("stack_handoff", {}).get("verifier_commands")
        assert episode.get("policy", {}).get("handoff_only") is True
        assert episode.get("policy", {}).get("host_layer_mutates_stack") is False
        assert episode.get("policy", {}).get("executes_commands") is False
        _assert_evidence_refs(episode.get("evidence_refs"))
    for episode in working_gap_episodes:
        gap = episode.get("working_stack_gap", {})
        service = episode.get("service")
        assert episode.get("truth_level") == "working_stack_gap_candidate"
        assert episode.get("owner_route") == "abyss-stack"
        assert {"working_stack", "spatial_graph", "usage_gap"}.issubset(set(episode.get("primary_signals", [])))
        assert f"service:{service}" in episode.get("affected_spatial_nodes", [])
        assert any(str(node).startswith("usage_gap:") for node in episode.get("affected_spatial_nodes", []))
        assert gap.get("schema") == "abyss_machine_self_awareness_working_stack_usage_gap_v1"
        assert gap.get("working_stack_link_id")
        assert gap.get("closure_blocker_keys")
        assert gap.get("verifier_commands")
        assert gap.get("safe_next_action", {}).get("host_layer_mutates_stack") is False
        assert episode.get("policy", {}).get("handoff_only") is True
        assert episode.get("policy", {}).get("host_layer_mutates_stack") is False
        assert episode.get("policy", {}).get("executes_commands") is False
        _assert_evidence_refs(episode.get("evidence_refs"))
    assert host_service_episodes
    for episode in host_service_episodes:
        assert episode.get("source_counts", {}).get("host-service", 0) >= 1
        assert episode.get("affected_services")
        assert any(str(node).startswith("service:") for node in episode.get("affected_spatial_nodes", []))
        assert any(str(key).startswith("host_service_unit:") for key in episode.get("context_keys", []))
        assert episode.get("host_service", {}).get("units")
        assert episode.get("host_service", {}).get("categories")
        assert episode.get("host_service", {}).get("policy", {}).get("host_layer_mutates_stack") is False
        _assert_evidence_refs(episode.get("evidence_refs"))

    alerts = _run_json(run_abyss_machine, "self-awareness", "alerts", "--json", timeout=120.0)
    stack_candidates = [
        candidate for candidate in alerts.get("candidates", [])
        if candidate.get("stack_handoff_requirement_id")
    ]
    working_gap_candidates = [
        candidate for candidate in alerts.get("candidates", [])
        if candidate.get("working_stack_gap_service")
    ]

    assert alerts["schema"] == "abyss_machine_self_awareness_alerts_v1"
    assert alerts["ok"] is True
    assert alerts["summary"]["stack_handoff_candidates"] == len(stack_candidates)
    assert alerts["summary"]["stack_handoff_candidates"] == len(stack_episodes)
    assert alerts["summary"]["working_stack_gap_candidates"] == len(working_gap_candidates)
    assert alerts["summary"]["working_stack_gap_candidates"] == len(working_gap_episodes)
    assert alerts["summary"]["response_depth_missing"] == 0
    for candidate in stack_candidates:
        contract = candidate.get("response_contract", {})
        assert candidate.get("episode_id") in stack_episode_ids
        assert candidate.get("automatic") is False
        assert candidate.get("owner_route") == "abyss-machine:self-awareness"
        assert contract.get("schema") == "abyss_machine_self_awareness_response_contract_v1"
        assert contract.get("validated_episode", {}).get("episode_kind") == "stack_handoff_blocker"
        assert contract.get("validated_episode", {}).get("truth_level") == "handoff_candidate"
        assert contract.get("runbook_candidate", {}).get("owner_route") == "abyss-stack"
        assert contract.get("runbook_candidate", {}).get("machine_executes_stack_change") is False
        assert contract.get("runbook_candidate", {}).get("host_layer_mutates_stack") is False
        assert contract.get("runbook_candidate", {}).get("verifier_commands")
        assert contract.get("policy", {}).get("automatic_action") is False
        assert contract.get("policy", {}).get("automatic_response") is False
        assert contract.get("policy", {}).get("executes_commands") is False
        assert contract.get("policy", {}).get("host_layer_mutates_stack") is False
    for candidate in working_gap_candidates:
        contract = candidate.get("response_contract", {})
        assert candidate.get("episode_id") in working_gap_episode_ids
        assert candidate.get("automatic") is False
        assert candidate.get("owner_route") == "abyss-machine:self-awareness"
        assert contract.get("schema") == "abyss_machine_self_awareness_response_contract_v1"
        assert contract.get("validated_episode", {}).get("episode_kind") == "working_stack_usage_gap"
        assert contract.get("validated_episode", {}).get("truth_level") == "working_stack_gap_candidate"
        assert contract.get("runbook_candidate", {}).get("owner_route") == "abyss-stack"
        assert contract.get("runbook_candidate", {}).get("machine_executes_stack_change") is False
        assert contract.get("runbook_candidate", {}).get("host_layer_mutates_stack") is False
        assert contract.get("runbook_candidate", {}).get("verifier_commands")
        assert contract.get("working_stack_gap", {}).get("service") == candidate.get("working_stack_gap_service")
        assert contract.get("working_stack_gap", {}).get("safe_next_action", {}).get("host_layer_mutates_stack") is False
        activation_route = contract.get("activation_gap_route", {})
        assert candidate.get("activation_gap_route") == activation_route
        assert activation_route.get("schema") == "abyss_machine_self_awareness_working_stack_activation_gap_route_v1"
        assert activation_route.get("complete") is True
        assert activation_route.get("service") == candidate.get("working_stack_gap_service")
        assert activation_route.get("owner_route") == "abyss-stack"
        assert activation_route.get("safe_next_action", {}).get("executes_commands") is False
        assert activation_route.get("safe_next_action", {}).get("host_layer_mutates_stack") is False
        assert activation_route.get("policy", {}).get("executes_commands") is False
        assert activation_route.get("policy", {}).get("host_layer_mutates_stack") is False
        assert contract.get("policy", {}).get("automatic_action") is False
        assert contract.get("policy", {}).get("automatic_response") is False
        assert contract.get("policy", {}).get("executes_commands") is False
        assert contract.get("policy", {}).get("host_layer_mutates_stack") is False


def test_live_self_awareness_investigates_working_stack_usage_gap(run_abyss_machine) -> None:
    episodes = _run_json(run_abyss_machine, "self-awareness", "episodes", "--json", timeout=180.0)
    gap_episode = next(
        episode for episode in episodes.get("episodes", [])
        if episode.get("episode_kind") == "working_stack_usage_gap"
    )

    investigation = _run_json(
        run_abyss_machine,
        "self-awareness",
        "investigate",
        "--episode-id",
        gap_episode["episode_id"],
        "--json",
        timeout=180.0,
    )

    assert investigation["schema"] == "abyss_machine_self_awareness_investigation_v1"
    assert investigation["ok"] is True
    assert investigation["selected_episode_id"] == gap_episode["episode_id"]
    _assert_no_stack_mutation_policy(investigation)
    gap_packet = investigation.get("working_stack_gap", {})
    assert gap_packet.get("schema") == "abyss_machine_self_awareness_investigation_working_stack_gap_v1"
    assert gap_packet.get("selected_episode_id") == gap_episode["episode_id"]
    assert gap_packet.get("service") == gap_episode.get("service")
    assert gap_packet.get("working_stack_link_id")
    assert gap_packet.get("complete") is True
    assert gap_packet.get("safe_next_action", {}).get("host_layer_mutates_stack") is False
    assert gap_packet.get("safe_next_action", {}).get("executes_commands") is False
    assert gap_packet.get("verifier_commands")

    states = {row.get("node"): row.get("state", {}) for row in investigation.get("states", [])}
    request_state = states["request_more_evidence"]
    brief_state = states["brief_reaction_candidate"]
    conclusion = investigation.get("conclusion", {})
    assert request_state.get("working_stack_gap", {}).get("schema") == gap_packet.get("schema")
    assert brief_state.get("working_stack_gap", {}).get("schema") == gap_packet.get("schema")
    assert conclusion.get("working_stack_gap", {}).get("schema") == gap_packet.get("schema")
    assert any(request.get("kind") == "working_stack_usage_gap" for request in request_state.get("requests", []))
    assert investigation.get("summary", {}).get("working_stack_gap_selected") is True
    assert investigation.get("summary", {}).get("working_stack_gap_complete") is True
    assert investigation.get("resident_cognitive_packet", {}).get("contradiction_notes")
    assert any(
        note.get("id") == "working_stack_gap_selected"
        for note in investigation.get("resident_cognitive_packet", {}).get("contradiction_notes", [])
    )
    assert any(
        test.get("id") == "working_stack_gap_needs_owner_gated_smoke"
        for test in investigation.get("resident_cognitive_packet", {}).get("hypothesis_tests", [])
    )

    replay = _run_json(
        run_abyss_machine,
        "self-awareness",
        "replay",
        "--thread-id",
        investigation["thread_id"],
        "--json",
        timeout=120.0,
    )
    assert replay["schema"] == "abyss_machine_self_awareness_replay_v1"
    assert replay["ok"] is True
    assert replay.get("working_stack_gap_replay", {}).get("selected") is True
    assert replay.get("working_stack_gap_replay", {}).get("replayable") is True
    assert replay.get("summary", {}).get("working_stack_gap_status") == replay.get("working_stack_gap_replay", {}).get("machine_usage_status")
    assert all(replay.get("working_stack_gap_replay", {}).get("state_preservation", {}).values())
    assert replay.get("policy", {}).get("host_layer_mutates_stack") is False
    assert replay.get("policy", {}).get("action_execution") is False


def test_live_self_awareness_cycle_proves_non_mutating_e2e(run_abyss_machine) -> None:
    payload = _run_json(run_abyss_machine, "self-awareness", "cycle", "--json", timeout=240.0)

    assert payload["schema"] == "abyss_machine_self_awareness_cycle_v1"
    assert payload["ok"] is True
    assert payload["status"] == "covered"
    _assert_no_stack_mutation_policy(payload)

    summary = payload["summary"]
    assert summary["chain_passed"] == summary["chain_total"]
    assert summary["chain_total"] >= 17
    assert summary["from_zero_proof_ok"] is True
    assert summary["e2e_lineage_ok"] is True
    assert summary["e2e_lineage_rows"] >= 15
    assert summary["e2e_lineage_missing_rows"] == []
    assert summary["bridge_proof_ok"] is True
    assert summary["from_zero_proof_steps"] == len(payload.get("steps", []))
    assert summary["from_zero_chain_obligations"] == len(payload.get("cycle_chain", {}))
    assert summary["bridge_proof_rows"] >= 10
    assert summary["failed_steps"] == []
    assert summary["automatic_responses"] == 0
    assert summary["routes_with_mutating_command_if_run"] == 0
    assert summary["stack_handoff_closure_readiness_replayable"] is True
    assert summary["body_trace_replayable"] is True
    assert summary["body_trace_export_included"] is True
    assert summary["response_body_trace_missing"] == 0
    assert summary["response_body_trace_routes"] > 0
    assert summary["autolink_organ_links"] == summary["autolink_organ_links_complete"]
    assert summary["autolink_organ_links"] >= 30
    assert summary["autolink_stack_requirement_links"] == summary["open_stack_requirements"]
    assert summary["working_stack_usage_gaps"] == summary["activation_smoke_open_activation_gaps"]
    assert summary["working_stack_usage_gaps"] == summary["autolink_working_stack_usage_gaps"]
    assert summary["working_stack_usage_gaps"] > 0
    assert summary["autolink_synthetic_scenarios_complete"] == 3

    issues = payload.get("issues", {})
    assert issues.get("failed_steps") == []
    assert issues.get("missing_chain") == []
    assert issues.get("mutation_claims") == []

    assert payload["policy"]["host_layer_mutates_stack"] is False
    assert payload["policy"]["automatic_remediation"] is False
    assert payload["policy"]["open_stack_requirements_are_blockers_not_host_failures"] is True
    assert payload["policy"]["claims_require_evidence_refs"] is True

    required_chain = {
        "synthetic_request",
        "capability_inventory",
        "requirement_probes",
        "failure_matrix",
        "signal_fabric",
        "timeline",
        "spatial_graph",
        "causal_episode",
        "alert",
        "warm_e2b_worker",
        "rag_memory",
        "nervous_freshness",
        "langgraph_investigation",
        "replay",
        "stack_handoff_readiness_replay",
        "semantic_brief",
        "reaction_candidate",
        "governed_response",
        "body_trace",
        "autolink",
        "machine_bridges",
        "export",
    }
    assert required_chain.issubset({key for key, value in payload["cycle_chain"].items() if value is True})
    bridge_proof = payload.get("bridge_proof", {})
    assert bridge_proof.get("schema") == "abyss_machine_self_awareness_cycle_bridge_proof_v1"
    assert bridge_proof.get("ok") is True
    assert bridge_proof.get("policy", {}).get("host_layer_mutates_stack") is False
    assert bridge_proof.get("policy", {}).get("actions_executed") is False
    bridge_rows = bridge_proof.get("rows", [])
    bridge_ids = {row.get("id") for row in bridge_rows}
    assert {
        "heartbeats",
        "memory",
        "mode",
        "resource",
        "processes",
        "process_containers",
        "process_thermal_plan",
        "cooling",
        "typing_events",
        "typing_validate",
        "nervous_brief",
        "reactions",
        "responses",
    }.issubset(bridge_ids)
    for row in bridge_rows:
        artifact = row.get("artifact", {})
        assert row.get("schema") == "abyss_machine_self_awareness_cycle_bridge_proof_row_v1"
        assert row.get("ok") is True
        assert artifact.get("exists") is True
        assert artifact.get("schema_ok") is True
        assert artifact.get("machine_owned_path") is True
        assert artifact.get("sha256")
        assert row.get("evidence_refs")
        assert row.get("validator", "").startswith("abyss-machine ")
        assert row.get("policy", {}).get("host_layer_mutates_stack") is False
        assert row.get("policy", {}).get("automatic_remediation") is False
    from_zero_proof = payload.get("from_zero_proof", {})
    assert from_zero_proof.get("schema") == "abyss_machine_self_awareness_from_zero_cycle_proof_v1"
    assert from_zero_proof.get("ok") is True
    assert from_zero_proof.get("policy", {}).get("host_layer_mutates_stack") is False
    assert from_zero_proof.get("policy", {}).get("actions_executed") is False
    assert from_zero_proof.get("summary", {}).get("proof_bad_steps") == []
    assert from_zero_proof.get("summary", {}).get("missing_obligations") == []
    proof_steps = from_zero_proof.get("proof_steps", [])
    obligations = from_zero_proof.get("chain_obligations", [])
    assert len(proof_steps) == len(payload.get("steps", []))
    assert len(obligations) == len(payload["cycle_chain"])
    assert required_chain.issubset({row.get("key") for row in obligations if row.get("satisfied") is True})
    for proof_step in proof_steps:
        artifact = proof_step.get("artifact", {})
        assert proof_step.get("schema") == "abyss_machine_self_awareness_from_zero_proof_step_v1"
        assert proof_step.get("ok") is True
        assert artifact.get("exists") is True
        assert artifact.get("machine_owned_path") is True
        assert artifact.get("sha256")
        assert artifact.get("schema", "").startswith("abyss_machine_")
        assert proof_step.get("evidence_refs")
        assert proof_step.get("policy", {}).get("host_layer_mutates_stack") is False
    for obligation in obligations:
        assert obligation.get("schema") == "abyss_machine_self_awareness_from_zero_chain_obligation_v1"
        assert obligation.get("satisfied") is True
        assert obligation.get("evidence_step_ids")
        assert obligation.get("evidence_paths")
        assert obligation.get("policy", {}).get("host_layer_mutates_stack") is False
    e2e_lineage = payload.get("e2e_lineage_proof", {})
    assert e2e_lineage.get("schema") == "abyss_machine_self_awareness_e2e_lineage_proof_v1"
    assert e2e_lineage.get("ok") is True
    assert e2e_lineage.get("cycle_id") == payload.get("cycle_id")
    assert e2e_lineage.get("run_id") == payload.get("probe_run_id")
    assert e2e_lineage.get("summary", {}).get("missing_rows") == []
    lineage_ids = {row.get("id") for row in e2e_lineage.get("rows", [])}
    assert {
        "synthetic_request",
        "signal_fabric",
        "trace_context_fallback",
        "query_and_correlation",
        "timeline",
        "spatial_graph",
        "causal_episode",
        "alert",
        "warm_e2b_context",
        "rag_memory",
        "nervous_freshness",
        "langgraph_investigation",
        "replay",
        "reaction_candidate",
        "governed_response",
        "body_trace",
        "autolink",
        "export",
    }.issubset(lineage_ids)
    for row in e2e_lineage.get("rows", []):
        assert row.get("schema") == "abyss_machine_self_awareness_e2e_lineage_row_v1"
        assert row.get("satisfied") is True
        assert row.get("artifacts_ok") is True
        assert row.get("chain", {}).get("satisfied") is True
        assert row.get("policy", {}).get("host_layer_mutates_stack") is False
        assert row.get("policy", {}).get("actions_executed") is False
        _assert_evidence_refs(row.get("evidence_refs"))
    handoff_summary = payload.get("stack_handoff_summary", {})
    handoff_readiness = payload.get("stack_handoff_closure_readiness", {})
    assert handoff_summary.get("schema") == "abyss_machine_self_awareness_cycle_stack_handoff_summary_v1"
    assert handoff_summary.get("policy", {}).get("host_layer_mutates_stack") is False
    assert handoff_summary.get("replay", {}).get("closure_readiness_replayable") is True
    assert handoff_readiness.get("schema") == "abyss_machine_self_awareness_investigation_stack_handoff_closure_readiness_v1"
    assert handoff_readiness.get("summary", {}).get("packets") == summary["stack_handoff_closure_readiness_packets"]

    open_stack_requirements = payload.get("open_stack_requirements", [])
    if open_stack_requirements:
        assert summary["open_stack_requirements"] == len(open_stack_requirements)
        assert summary["full_stack_potential_covered"] is False
        for requirement in open_stack_requirements:
            assert requirement["owner"] == "abyss-stack"
            _assert_evidence_refs(requirement.get("evidence_refs"))
    else:
        assert summary["open_stack_requirements"] == 0
        assert summary["full_stack_potential_covered"] is True

    for step in payload.get("steps", []):
        assert step.get("ok") is True
        artifact = step.get("artifact", {})
        assert artifact.get("path", "").startswith("/var/lib/abyss-machine/")
        assert artifact.get("schema", "").startswith("abyss_machine_")

    _assert_evidence_refs(payload.get("evidence_refs"))


def test_live_self_awareness_coverage_audit_maps_full_stack_usage(run_abyss_machine) -> None:
    payload = _run_json(run_abyss_machine, "self-awareness", "coverage-audit", "--json", timeout=120.0)

    assert payload["schema"] == "abyss_machine_self_awareness_objective_coverage_audit_v1"
    assert payload["ok"] is True
    assert payload["status"] in {"covered", "covered_with_stack_blockers"}
    _assert_no_stack_mutation_policy(payload)
    assert payload.get("policy", {}).get("host_layer_mutates_stack") is False
    assert payload.get("policy", {}).get("writes_project_roots") is False
    assert payload.get("policy", {}).get("actions_executed") is False
    assert payload.get("policy", {}).get("automatic_remediation") is False

    summary = payload.get("summary", {})
    assert summary.get("rows", 0) >= 22
    assert summary.get("incomplete") == 0
    assert summary.get("open_stack_requirements") == 4
    assert summary.get("full_stack_potential_covered") is False
    assert summary.get("working_stack_gap_rows") == summary.get("working_stack_usage_gaps")
    assert summary.get("working_stack_gap_rows") == len(payload.get("working_stack_gap_rows", []))
    assert summary.get("working_stack_gap_services")
    assert summary.get("working_stack_activation_synthetic_proofs") == summary.get("working_stack_gap_rows")
    assert summary.get("working_stack_activation_synthetic_proofs_complete") == summary.get("working_stack_gap_rows")
    assert summary.get("working_stack_activation_synthetic_proof_incomplete_rows") == []
    assert set(summary.get("working_stack_activation_synthetic_proof_services", [])) == set(summary.get("working_stack_gap_services", []))
    assert summary.get("working_stack_activation_closure_acceptance_packets") == summary.get("working_stack_gap_rows")
    assert summary.get("working_stack_activation_closure_acceptance_packets_complete") == summary.get("working_stack_gap_rows")
    assert summary.get("working_stack_activation_compat_requirements") == summary.get("working_stack_gap_rows")
    assert summary.get("working_stack_activation_smoke_rows") == summary.get("working_stack_gap_rows")
    assert summary.get("working_stack_activation_smoke_rows_ok") == summary.get("working_stack_gap_rows")
    assert summary.get("working_stack_activation_smoke_incomplete_rows") == []
    assert summary.get("working_stack_activation_smoke_failed_services") == []
    assert summary.get("working_stack_link_integrity_rows") == summary.get("working_stack_organs")
    assert summary.get("working_stack_link_integrity_rows_complete") == summary.get("working_stack_organs")
    assert summary.get("working_stack_link_integrity_missing_rows") == []
    assert summary.get("working_stack_link_integrity_usage_gap_rows") == summary.get("working_stack_usage_gaps")
    assert summary.get("working_stack_link_integrity_usage_gap_rows_with_coverage") == summary.get("working_stack_usage_gaps")
    assert summary.get("working_stack_link_integrity_usage_gap_rows_with_activation_smoke") == summary.get("working_stack_usage_gaps")
    assert summary.get("cycle_chain_passed") == summary.get("cycle_chain_total")
    assert summary.get("e2e_lineage_ok") is True

    link_integrity = payload.get("working_stack_link_integrity", {})
    assert link_integrity.get("schema") == "abyss_machine_self_awareness_working_stack_link_integrity_matrix_v1"
    assert link_integrity.get("ok") is True
    assert link_integrity.get("summary", {}).get("rows") == summary.get("working_stack_organs")
    assert link_integrity.get("summary", {}).get("complete_rows") == summary.get("working_stack_organs")
    assert link_integrity.get("summary", {}).get("missing_rows") == []
    assert link_integrity.get("policy", {}).get("host_layer_mutates_stack") is False
    rows_by_service = link_integrity.get("rows_by_service", {})
    assert set(rows_by_service) >= {"prometheus", "grafana", "loki", "rag-api", "langchain-api"}
    for row in link_integrity.get("rows", []):
        assert row.get("schema") == "abyss_machine_self_awareness_working_stack_link_integrity_row_v1"
        assert row.get("complete") is True
        assert row.get("service")
        assert row.get("working_stack_link_id")
        assert row.get("event_id")
        assert row.get("episode_ids")
        assert row.get("checks", {}).get("working_stack_link") is True
        assert row.get("checks", {}).get("event_fabric_link") is True
        assert row.get("checks", {}).get("timeline_window") is True
        assert row.get("checks", {}).get("spatial_service_to_link_edge") is True
        assert row.get("checks", {}).get("context_indexed") is True
        assert row.get("checks", {}).get("episode_present") is True
        assert row.get("checks", {}).get("coverage_gap_row") is True
        assert row.get("checks", {}).get("activation_smoke_if_gap") is True
        assert row.get("policy", {}).get("host_layer_mutates_stack") is False
        _assert_evidence_refs(row.get("evidence_refs"))

    expected_rows = {
        "prometheus_promql",
        "loki_logql",
        "grafana_health",
        "grafana_datasource_inventory",
        "alertmanager",
        "alloy_otel",
        "trace_backend",
        "route_rag_api",
        "postgres_neo4j_graph",
        "langchain_langgraph_stack",
        "stack_models_stt_embeddings_tts_npu",
        "warm_e2b_resident_worker",
        "e4b_qwen_escalation",
        "machine_bridges",
        "signal_fabric_schema",
        "memory_space_freshness",
        "checkpointed_investigation_replay",
        "response_layer",
        "ux_api_commands",
        "failure_tests",
        "e2e_probe_export_replay",
        "owner_boundary",
    }
    rows = payload.get("rows", [])
    row_by_id = {row.get("id"): row for row in rows}
    assert expected_rows.issubset(row_by_id)
    assert set(payload.get("blocked_rows", [])) == {
        "grafana_datasource_inventory",
        "trace_backend",
        "postgres_neo4j_graph",
        "langchain_langgraph_stack",
    }
    assert set(payload.get("open_stack_requirement_ids", [])) == {
        "stack.database-graph.read-route",
        "stack.grafana.datasource-read",
        "stack.langchain-api.graph-observability",
        "stack.trace-backend",
    }
    assert set(summary.get("blocked_coverage_planes", []))
    assert set(summary.get("objective_coverage_planes", []))
    assert set(summary.get("covered_coverage_planes", []))
    assert set(summary.get("working_stack_gap_coverage_planes", []))
    for row in payload.get("working_stack_gap_rows", []):
        assert row.get("schema") == "abyss_machine_self_awareness_working_stack_gap_coverage_row_v1"
        assert row.get("owner") == "abyss-stack"
        assert row.get("service")
        assert row.get("working_stack_link_id")
        assert row.get("closure_blocker_keys")
        assert row.get("missing_checks")
        assert row.get("activation_readiness", {}).get("schema") == "abyss_machine_self_awareness_working_stack_activation_readiness_v1"
        closure_acceptance = row.get("closure_acceptance", {})
        assert closure_acceptance.get("schema") == "abyss_machine_self_awareness_working_stack_activation_closure_acceptance_v1"
        assert closure_acceptance.get("complete") is True
        assert closure_acceptance.get("service") == row.get("service")
        assert closure_acceptance.get("machine_usage_status") == row.get("machine_usage_status")
        assert closure_acceptance.get("working_stack_link_id") == row.get("working_stack_link_id")
        assert closure_acceptance.get("pre_close_identity", {}).get("missing_check_keys") == row.get("closure_blocker_keys")
        assert closure_acceptance.get("stack_compat_requirement", {}).get("schema") == "abyss_machine_self_awareness_working_stack_activation_compat_requirement_v1"
        assert closure_acceptance.get("stack_compat_requirement", {}).get("owner") == "abyss-stack"
        assert closure_acceptance.get("stack_compat_requirement", {}).get("operator_boundary", {}).get("abyss_machine_executes_stack_change") is False
        assert closure_acceptance.get("policy", {}).get("host_layer_mutates_stack") is False
        _assert_evidence_refs(closure_acceptance.get("evidence_refs"))
        assert row.get("synthetic_scenario", {}).get("schema") == "abyss_machine_self_awareness_working_stack_activation_synthetic_scenario_v1"
        assert row.get("synthetic_scenario", {}).get("complete") is True
        assert row.get("synthetic_scenario", {}).get("policy", {}).get("host_layer_mutates_stack") is False
        proof = row.get("synthetic_proof", {})
        assert proof.get("schema") == "abyss_machine_self_awareness_working_stack_activation_synthetic_proof_v1"
        assert proof.get("complete") is True
        assert proof.get("proof_status") == "proved_open_activation_gap"
        assert proof.get("service") == row.get("service")
        assert proof.get("machine_usage_status") == row.get("machine_usage_status")
        assert proof.get("working_stack_link_id") == row.get("working_stack_link_id")
        assert proof.get("summary", {}).get("failed_steps") == []
        assert {step.get("step") for step in proof.get("proof_steps", [])} >= {
            "inventory",
            "space",
            "causal_episode",
            "reaction_response_contract",
            "investigation_replay_contract",
            "coverage_row",
            "export",
            "cycle",
            "boundary_policy",
        }
        assert all(step.get("ok") is True for step in proof.get("proof_steps", []))
        assert proof.get("policy", {}).get("host_layer_mutates_stack") is False
        assert proof.get("policy", {}).get("executes_commands") is False
        _assert_evidence_refs(proof.get("evidence_refs"))
        smoke = row.get("activation_smoke", {})
        assert smoke.get("schema") == "abyss_machine_self_awareness_working_stack_activation_smoke_compact_v1"
        assert smoke.get("complete") is True
        assert smoke.get("service") == row.get("service")
        assert smoke.get("machine_usage_status") == row.get("machine_usage_status")
        assert smoke.get("working_stack_link_id") == row.get("working_stack_link_id")
        assert smoke.get("divergences") == 0
        assert smoke.get("working_stack_gap_replayable") is True
        assert smoke.get("resident_cognitive_replay_complete") is True
        assert smoke.get("policy", {}).get("host_layer_mutates_stack") is False
        assert smoke.get("policy", {}).get("executes_commands") is False
        assert smoke.get("policy", {}).get("action_execution") is False
        _assert_evidence_refs(smoke.get("evidence_refs"))
        assert row.get("runbook_candidate", {}).get("machine_executes_stack_change") is False
        assert row.get("verifier_commands")
        assert row.get("safe_next_action", {}).get("host_layer_mutates_stack") is False
        assert row.get("safe_next_action", {}).get("executes_commands") is False
        assert row.get("policy", {}).get("host_layer_mutates_stack") is False
        assert row.get("policy", {}).get("executes_commands") is False
        assert row.get("policy", {}).get("automatic_remediation") is False
        _assert_evidence_refs(row.get("evidence_refs"))

    for row in rows:
        assert row.get("schema") == "abyss_machine_self_awareness_objective_coverage_row_v1"
        assert row.get("status") in {"covered", "blocked_stack_owned", "degraded"}
        assert row.get("objective_coverage_planes")
        assert row.get("coverage_plane_status", {}).get("objective") == row.get("objective_coverage_planes")
        assert row.get("missing_capabilities") == []
        assert row.get("missing_requirements") == []
        assert row.get("missing_artifacts") == []
        assert row.get("missing_chain_keys") == []
        assert row.get("policy", {}).get("host_layer_mutates_stack") is False
        assert row.get("policy", {}).get("actions_executed") is False
        _assert_evidence_refs(row.get("evidence_refs"))
        if row.get("status") == "covered":
            assert row.get("covered_coverage_planes") == row.get("objective_coverage_planes")
            assert row.get("coverage_planes") == row.get("objective_coverage_planes")
            assert set(row.get("covered_coverage_planes", [])).issubset(set(summary.get("covered_coverage_planes", [])))
        if row.get("status") == "blocked_stack_owned":
            assert row.get("covered_coverage_planes") == []
            assert row.get("blocked_by_requirement_ids")
            assert row.get("blocked_by_requirement_ids") == row.get("open_stack_requirement_ids")
            assert row.get("blocking_check_keys")
            assert row.get("coverage_impacts")
            assert row.get("blocked_coverage_planes")
            assert row.get("coverage_planes") == row.get("blocked_coverage_planes")
            assert set(row.get("blocked_coverage_planes", [])).issubset(set(summary.get("blocked_coverage_planes", [])))
            for impact in row.get("coverage_impacts", []):
                assert impact.get("requirement_id") in row.get("blocked_by_requirement_ids", [])
                assert impact.get("coverage_planes")
                assert impact.get("policy", {}).get("host_layer_mutates_stack") is False
    assert "metrics_query" in row_by_id["prometheus_promql"]["covered_coverage_planes"]
    assert "resident_worker" in row_by_id["warm_e2b_resident_worker"]["covered_coverage_planes"]


def test_live_self_awareness_activation_smoke_runs_each_working_stack_gap(run_abyss_machine) -> None:
    payload = _run_json(run_abyss_machine, "self-awareness", "activation-smoke", "--json", timeout=180.0)

    assert payload["schema"] == "abyss_machine_self_awareness_working_stack_activation_smoke_v1"
    assert payload["ok"] is True
    assert payload["complete"] is True
    _assert_no_stack_mutation_policy(payload)
    summary = payload.get("summary", {})
    assert summary.get("activation_entries") == summary.get("rows")
    assert summary.get("rows_ok") == summary.get("rows")
    assert summary.get("investigation_ok") == summary.get("rows")
    assert summary.get("replay_ok") == summary.get("rows")
    assert summary.get("divergences") == 0
    assert summary.get("failed_services") == []
    assert summary.get("service_ids")
    assert payload.get("policy", {}).get("per_service_actual_investigate_replay") is True
    assert payload.get("policy", {}).get("host_layer_mutates_stack") is False
    assert payload.get("policy", {}).get("executes_commands") is False
    assert payload.get("policy", {}).get("action_execution") is False
    assert set(payload.get("by_service", {})) == set(summary.get("service_ids", []))
    assert set(payload.get("compact_by_service", {})) == set(summary.get("service_ids", []))
    for row in payload.get("rows", []):
        assert row.get("schema") == "abyss_machine_self_awareness_working_stack_activation_smoke_row_v1"
        assert row.get("owner") == "abyss-stack"
        assert row.get("ok") is True
        assert row.get("complete") is True
        assert row.get("service") in summary.get("service_ids", [])
        assert row.get("machine_usage_status")
        assert row.get("working_stack_link_id")
        assert row.get("episode_id")
        assert row.get("investigation", {}).get("schema") == "abyss_machine_self_awareness_working_stack_activation_smoke_investigation_v1"
        assert row.get("investigation", {}).get("ok") is True
        assert row.get("investigation", {}).get("selected_episode_matches") is True
        assert row.get("investigation", {}).get("working_stack_gap_complete") is True
        assert row.get("investigation", {}).get("working_stack_gap_matches") is True
        assert row.get("investigation", {}).get("checkpoints") == len(LANGGRAPH_INVESTIGATION_NODE_ORDER)
        assert row.get("investigation", {}).get("graph_nodes") == len(LANGGRAPH_INVESTIGATION_NODE_ORDER)
        assert row.get("investigation", {}).get("evidence_validation_fails") == 0
        assert row.get("replay", {}).get("schema") == "abyss_machine_self_awareness_working_stack_activation_smoke_replay_v1"
        assert row.get("replay", {}).get("ok") is True
        assert row.get("replay", {}).get("thread_matches") is True
        assert row.get("replay", {}).get("working_stack_gap_selected") is True
        assert row.get("replay", {}).get("working_stack_gap_replayable") is True
        assert row.get("replay", {}).get("working_stack_gap_matches") is True
        assert row.get("replay", {}).get("divergences") == 0
        assert row.get("replay", {}).get("resident_cognitive_replay_complete") is True
        assert row.get("replay", {}).get("node_order") == LANGGRAPH_INVESTIGATION_NODE_ORDER
        assert row.get("commands", {}).get("investigate", "").startswith("abyss-machine self-awareness investigate --episode-id ")
        assert row.get("commands", {}).get("replay", "").startswith("abyss-machine self-awareness replay --thread-id ")
        assert row.get("policy", {}).get("actual_investigate_replay_run") is True
        assert row.get("policy", {}).get("host_layer_mutates_stack") is False
        assert row.get("policy", {}).get("executes_commands") is False
        assert row.get("policy", {}).get("action_execution") is False
        assert row.get("policy", {}).get("automatic_remediation") is False
        _assert_evidence_refs(row.get("evidence_refs"))
        compact = payload.get("compact_by_service", {}).get(row.get("service"), {})
        assert compact.get("schema") == "abyss_machine_self_awareness_working_stack_activation_smoke_compact_v1"
        assert compact.get("complete") is True
        assert compact.get("service") == row.get("service")
        assert compact.get("working_stack_link_id") == row.get("working_stack_link_id")
        assert compact.get("divergences") == 0
        assert compact.get("working_stack_gap_replayable") is True
        assert compact.get("resident_cognitive_replay_complete") is True
        assert compact.get("policy", {}).get("host_layer_mutates_stack") is False
    _assert_evidence_refs(payload.get("evidence_refs"))


def test_live_self_awareness_autolink_records_time_space_context_delta(run_abyss_machine) -> None:
    payload = _run_json(run_abyss_machine, "self-awareness", "autolink", "--json", timeout=120.0)

    assert payload["schema"] == "abyss_machine_self_awareness_autolink_v1"
    assert payload["ok"] is True
    assert payload["status"] == "linked"
    _assert_no_stack_mutation_policy(payload)
    assert payload.get("policy", {}).get("host_layer_mutates_stack") is False
    assert payload.get("policy", {}).get("executes_commands") is False
    assert payload.get("policy", {}).get("automatic_remediation") is False

    summary = payload.get("summary", {})
    assert summary.get("organ_links") == summary.get("organ_links_complete")
    assert summary.get("organ_links") >= 30
    assert summary.get("stack_requirement_links") == summary.get("stack_requirement_links_complete")
    assert summary.get("open_stack_requirements") == summary.get("stack_requirement_links")
    assert summary.get("working_stack_usage_gaps", 0) > 0
    assert summary.get("synthetic_scenarios") == 3
    assert summary.get("synthetic_scenarios_complete") == 3
    assert summary.get("incomplete_organs") == []
    assert summary.get("incomplete_requirements") == []
    assert summary.get("incomplete_scenarios") == []
    assert summary.get("full_stack_potential_covered") is False

    state_delta = payload.get("state_delta", {})
    assert state_delta.get("schema") == "abyss_machine_self_awareness_autolink_state_delta_v1"
    assert state_delta.get("current_state_digest") == payload.get("state_digest")
    assert all(isinstance(state_delta.get(key), list) for key in (
        "added_services",
        "removed_services",
        "changed_services",
        "added_requirements",
        "removed_requirements",
        "changed_requirements",
    ))
    assert state_delta.get("policy", {}).get("host_layer_mutates_stack") is False
    assert state_delta.get("policy", {}).get("executes_commands") is False

    organs = payload.get("organ_links", [])
    assert len(organs) == summary.get("organ_links")
    assert set(payload.get("organ_links_by_service", {})) == set(summary.get("service_ids", []))
    for row in organs:
        assert row.get("schema") == "abyss_machine_self_awareness_autolink_organ_row_v1"
        assert row.get("complete") is True
        assert row.get("service")
        assert row.get("working_stack_link_id")
        assert row.get("event_id")
        assert row.get("episode_ids")
        assert row.get("checks", {}).get("time_linked") is True
        assert row.get("checks", {}).get("space_linked") is True
        assert row.get("checks", {}).get("context_linked") is True
        assert row.get("checks", {}).get("episode_linked") is True
        if row.get("usage_gap"):
            assert row.get("activation_smoke", {}).get("complete") is True
        assert row.get("policy", {}).get("host_layer_mutates_stack") is False
        assert row.get("policy", {}).get("executes_commands") is False
        _assert_evidence_refs(row.get("evidence_refs"))

    requirements = payload.get("stack_requirement_links", [])
    assert len(requirements) == summary.get("stack_requirement_links")
    assert set(payload.get("stack_requirement_links_by_requirement", {})) == set(summary.get("requirement_ids", []))
    for row in requirements:
        assert row.get("schema") == "abyss_machine_self_awareness_autolink_stack_requirement_row_v1"
        assert row.get("complete") is True
        assert row.get("owner") == "abyss-stack"
        assert row.get("requirement_id")
        assert row.get("episode_ids")
        assert row.get("checks", {}).get("closure_acceptance") is True
        assert row.get("checks", {}).get("coverage_impact") is True
        assert row.get("checks", {}).get("owner_route") is True
        assert row.get("policy", {}).get("host_layer_mutates_stack") is False
        assert row.get("policy", {}).get("executes_commands") is False
        _assert_evidence_refs(row.get("evidence_refs"))

    for scenario in payload.get("synthetic_scenarios", []):
        assert scenario.get("schema") == "abyss_machine_self_awareness_autolink_synthetic_scenario_v1"
        assert scenario.get("complete") is True
        assert scenario.get("policy", {}).get("host_layer_mutates_stack") is False
        assert scenario.get("policy", {}).get("executes_commands") is False
        _assert_evidence_refs(scenario.get("evidence_refs"))


def test_live_self_awareness_status_surfaces_autolink_stack_potential(run_abyss_machine) -> None:
    payload = _run_json(run_abyss_machine, "self-awareness", "status", "--json", timeout=60.0)

    assert payload["schema"] == "abyss_machine_self_awareness_status_v1"
    assert payload["ok"] is True
    assert payload["status"] == "ready"
    summary = payload.get("summary", {})
    assert summary.get("autolink_ok") is True
    assert summary.get("coverage_audit_ok") is True
    assert summary.get("activation_smoke_ok") is True
    assert summary.get("autolink_organ_links") == summary.get("autolink_organ_links_complete")
    assert summary.get("autolink_organ_links", 0) >= 30
    assert summary.get("autolink_stack_requirement_links") == summary.get("autolink_stack_requirement_links_complete")
    assert summary.get("autolink_stack_requirement_links") == summary.get("open_stack_requirements")
    assert summary.get("autolink_synthetic_scenarios") == 3
    assert summary.get("autolink_synthetic_scenarios_complete") == 3
    assert summary.get("working_stack_usage_gaps", 0) > 0
    assert summary.get("activation_smoke_open_activation_gaps") == summary.get("working_stack_usage_gaps")
    assert summary.get("open_potential_activation_gap_routes") == summary.get("working_stack_usage_gaps")
    assert set(summary.get("open_potential_activation_gap_classifications", [])) == {
        "declared_without_running_runtime",
        "exited_stack_managed_container",
        "running_functional_smoke_failed",
    }
    assert summary.get("full_stack_potential_covered") is False
    assert set(summary.get("open_potential_services", [])) == {
        "aoa-browser",
        "babelvox-tts",
        "langchain-api-llamacpp",
        "litellm",
        "n8n",
        "n8n-task-runners",
        "ollama",
        "qwen-tts",
        "tos-graph",
        "tts-router",
    }
    assert set(summary.get("open_stack_requirement_ids", [])) == {
        "stack.database-graph.read-route",
        "stack.grafana.datasource-read",
        "stack.langchain-api.graph-observability",
        "stack.trace-backend",
    }
    open_potential = payload.get("open_potential", {})
    open_potential_rows = open_potential.get("rows", [])
    assert open_potential.get("services") == len(open_potential_rows) == summary.get("working_stack_usage_gaps")
    assert open_potential.get("activation_gap_routes") == len(open_potential_rows)
    row_by_service = {row.get("service"): row for row in open_potential_rows}
    assert row_by_service["aoa-browser"]["activation_gap_classification"] == "running_functional_smoke_failed"
    assert row_by_service["qwen-tts"]["activation_gap_classification"] == "exited_stack_managed_container"
    assert row_by_service["tts-router"]["activation_gap_classification"] == "exited_stack_managed_container"
    for service, row in row_by_service.items():
        route = row.get("activation_gap_route", {})
        assert route.get("schema") == "abyss_machine_self_awareness_working_stack_activation_gap_route_v1"
        assert route.get("complete") is True
        assert route.get("service") == service
        assert route.get("classification") == row.get("activation_gap_classification")
        assert route.get("current_state", {}).get("runtime", {})
        assert route.get("activation_smoke", {}).get("row_complete") is True
        assert route.get("safe_next_action", {}).get("requires_human_approval") is True
        assert route.get("safe_next_action", {}).get("host_layer_mutates_stack") is False
        assert route.get("safe_next_action", {}).get("executes_commands") is False
        assert route.get("policy", {}).get("host_layer_mutates_stack") is False
        assert route.get("policy", {}).get("executes_commands") is False
    assert payload.get("latest", {}).get("coverage_audit", {}).get("ok") is True
    assert payload.get("latest", {}).get("activation_smoke", {}).get("ok") is True


def test_live_self_awareness_export_keeps_latest_artifacts_bounded(run_abyss_machine) -> None:
    payload = _run_json(run_abyss_machine, "self-awareness", "export", "--json", timeout=90.0)

    assert payload["schema"] == "abyss_machine_self_awareness_export_v1"
    assert payload["ok"] is True
    assert payload["summary"]["missing"] == 0
    assert payload["summary"]["malformed"] == 0
    assert payload["summary"]["artifacts"] >= 19
    assert payload["summary"]["manifest_digest"]
    _assert_no_stack_mutation_policy(payload)
    assert payload.get("policy", {}).get("host_layer_mutates_stack") is False
    assert payload.get("policy", {}).get("actions_executed") is False
    assert payload.get("portable_contract", {}).get("stack_mutation_included") is False
    assert payload.get("portable_contract", {}).get("actions_executed") is False

    manifest = payload.get("manifest", {})
    artifact_list = payload.get("artifact_list", [])
    assert manifest.get("schema") == "abyss_machine_self_awareness_export_manifest_v1"
    assert manifest.get("manifest_digest") == payload["summary"]["manifest_digest"]
    assert manifest.get("artifact_count") == len(artifact_list)
    assert manifest.get("portable_contract", {}).get("artifacts_are_machine_owned_readmodels") is True
    assert manifest.get("portable_contract", {}).get("stack_handoff_included") is True
    assert manifest.get("portable_contract", {}).get("stack_owner_acceptance_verifiers_included") is True
    assert manifest.get("portable_contract", {}).get("stack_closure_dossier_included") is True
    assert manifest.get("portable_contract", {}).get("stack_requirement_closure_acceptance_included") is True
    assert manifest.get("portable_contract", {}).get("working_stack_activation_dossier_included") is True
    assert manifest.get("portable_contract", {}).get("working_stack_activation_synthetic_proofs_included") is True
    assert manifest.get("portable_contract", {}).get("working_stack_activation_smoke_included") is True
    assert manifest.get("portable_contract", {}).get("working_stack_link_integrity_included") is True
    assert manifest.get("portable_contract", {}).get("autolink_included") is True
    assert manifest.get("portable_contract", {}).get("host_body_context_packet_included") is True
    assert manifest.get("portable_contract", {}).get("response_body_trace_included") is True
    assert manifest.get("portable_contract", {}).get("reactions_responses_included") is True
    assert manifest.get("owner_boundary", {}).get("host_layer_mutates_stack") is False

    artifacts = payload.get("artifacts", {})
    assert isinstance(artifacts, dict)
    assert len(artifacts) == payload["summary"]["artifacts"]
    assert len(artifact_list) == payload["summary"]["artifacts"]
    assert {item.get("name") for item in artifact_list} == set(artifacts)
    assert "stack_closure_dossier" in artifacts
    assert "autolink" in artifacts
    assert "reactions" in artifacts
    assert "responses" in artifacts
    for artifact in artifact_list:
        path = artifact.get("path", "")
        assert path.startswith("/var/lib/abyss-machine/")
        assert not any(path.startswith(root) for root in PROTECTED_STACK_ROOTS)
        assert artifact.get("name") in artifacts
        assert artifact.get("exists") is True
        assert artifact.get("history_path", "").startswith("/var/lib/abyss-machine/")
        assert artifact.get("schema_ok") is True
        assert artifact.get("schema", "").startswith("abyss_machine_")
        assert artifact.get("expected_schema") == artifact.get("schema")
        assert artifact.get("sha256")
        assert artifact.get("size_bytes", 0) > 0
        _assert_evidence_refs([artifact.get("evidence_ref")])

    requirements = payload.get("requirements", {})
    handoff = payload.get("stack_handoff", {})
    dossier = payload.get("stack_closure_dossier", {})
    assert requirements.get("schema") == "abyss_machine_self_awareness_export_requirements_summary_v1"
    assert handoff.get("schema") == "abyss_machine_self_awareness_export_stack_handoff_v1"
    assert dossier.get("schema") == "abyss_machine_self_awareness_stack_closure_dossier_v1"
    assert requirements.get("policy", {}).get("host_layer_mutates_stack") is False
    assert requirements.get("policy", {}).get("handoff_only") is True
    assert handoff.get("policy", {}).get("host_layer_mutates_stack") is False
    assert dossier.get("policy", {}).get("host_layer_mutates_stack") is False
    assert dossier.get("policy", {}).get("executes_commands") is False
    assert handoff.get("policy", {}).get("runbook_candidates_are_handoff_only") is True
    assert handoff.get("policy", {}).get("raw_secrets_included") is False
    assert handoff.get("artifact_refs", {}).get("requirements", {}).get("path", "").startswith("/var/lib/abyss-machine/")
    assert handoff.get("artifact_refs", {}).get("requirement_probes", {}).get("path", "").startswith("/var/lib/abyss-machine/")
    assert handoff.get("artifact_refs", {}).get("stack_closure_dossier", {}).get("path", "").startswith("/var/lib/abyss-machine/")
    assert handoff.get("artifact_refs", {}).get("working_stack", {}).get("path", "").startswith("/var/lib/abyss-machine/")
    assert handoff.get("artifact_refs", {}).get("activation_smoke", {}).get("path", "").startswith("/var/lib/abyss-machine/")
    assert handoff.get("artifact_refs", {}).get("coverage_audit", {}).get("schema") == "abyss_machine_self_awareness_objective_coverage_audit_v1"
    assert handoff.get("coverage_audit_ref") == handoff.get("artifact_refs", {}).get("coverage_audit")
    assert payload["summary"]["open_stack_requirements"] == handoff["summary"]["open"]
    assert payload["summary"]["stack_closure_dossier_entries"] == dossier["summary"]["probes"]
    assert payload["summary"]["stack_requirement_closure_acceptance_packets"] == handoff["summary"]["stack_requirement_closure_acceptance_packets"]
    assert payload["summary"]["stack_requirement_closure_acceptance_packets_complete"] == handoff["summary"]["stack_requirement_closure_acceptance_packets_complete"]
    assert payload["summary"]["stack_requirement_compat_requirements"] == handoff["summary"]["stack_requirement_compat_requirements"]
    assert payload["summary"]["working_stack_activation_entries"] == handoff["summary"]["working_stack_activation_entries"]
    assert payload["summary"]["working_stack_activation_closure_acceptance_packets"] == handoff["summary"]["working_stack_activation_closure_acceptance_packets"]
    assert payload["summary"]["working_stack_activation_closure_acceptance_packets_complete"] == handoff["summary"]["working_stack_activation_closure_acceptance_packets_complete"]
    assert payload["summary"]["working_stack_activation_compat_requirements"] == handoff["summary"]["working_stack_activation_compat_requirements"]
    assert payload["summary"]["working_stack_link_integrity_rows"] == payload["summary"]["working_stack_link_integrity_rows_complete"]
    assert payload["summary"]["working_stack_link_integrity_missing_rows"] == []
    assert payload["portable_contract"]["working_stack_link_integrity_included"] is True
    assert payload["portable_contract"]["autolink_included"] is True
    assert payload["portable_contract"]["host_body_context_packet_included"] is True
    assert payload["portable_contract"]["response_body_trace_included"] is True
    assert payload["portable_contract"]["reactions_responses_included"] is True
    assert payload["summary"]["host_body_context_packet_included"] is True
    assert payload["summary"]["response_body_trace_included"] is True
    body_trace_handoff = payload.get("body_trace_handoff", {})
    assert body_trace_handoff.get("schema") == "abyss_machine_self_awareness_export_body_trace_handoff_v1"
    assert body_trace_handoff.get("host_body_context_packet_included") is True
    assert body_trace_handoff.get("resident_body_trace_replayable") is True
    assert body_trace_handoff.get("response_body_trace_included") is True
    assert body_trace_handoff.get("policy", {}).get("host_layer_mutates_stack") is False
    link_integrity = payload.get("working_stack_link_integrity", {})
    assert link_integrity.get("schema") == "abyss_machine_self_awareness_working_stack_link_integrity_matrix_v1"
    assert link_integrity.get("ok") is True
    assert link_integrity.get("summary", {}).get("rows") == payload["summary"]["working_stack_link_integrity_rows"]
    assert link_integrity.get("summary", {}).get("complete_rows") == payload["summary"]["working_stack_link_integrity_rows_complete"]
    assert link_integrity.get("summary", {}).get("missing_rows") == []
    assert link_integrity.get("policy", {}).get("host_layer_mutates_stack") is False
    autolink = payload.get("autolink", {})
    assert autolink.get("schema") == "abyss_machine_self_awareness_autolink_v1"
    assert autolink.get("ok") is True
    assert payload["summary"]["autolink_organ_links"] == autolink.get("summary", {}).get("organ_links")
    assert payload["summary"]["autolink_organ_links_complete"] == autolink.get("summary", {}).get("organ_links_complete")
    assert payload["summary"]["autolink_organ_links"] == payload["summary"]["autolink_organ_links_complete"]
    assert payload["summary"]["autolink_stack_requirement_links"] == autolink.get("summary", {}).get("stack_requirement_links")
    assert payload["summary"]["autolink_synthetic_scenarios_complete"] == autolink.get("summary", {}).get("synthetic_scenarios_complete")
    assert autolink.get("policy", {}).get("host_layer_mutates_stack") is False
    assert autolink.get("policy", {}).get("executes_commands") is False
    assert payload["summary"]["working_stack_activation_synthetic_proofs"] == handoff["summary"]["working_stack_activation_synthetic_proofs"]
    assert payload["summary"]["working_stack_activation_synthetic_proofs_complete"] == handoff["summary"]["working_stack_activation_synthetic_proofs_complete"]
    assert payload["summary"]["working_stack_activation_smoke_rows"] == handoff["summary"]["working_stack_activation_smoke_rows"]
    assert payload["summary"]["working_stack_activation_smoke_rows_complete"] == handoff["summary"]["working_stack_activation_smoke_rows_complete"]
    assert payload["summary"]["working_stack_activation_smoke_failed_services"] == []
    assert requirements["summary"]["open_stack_requirements"] == handoff["summary"]["open"]
    assert dossier["summary"]["open_stack_requirements"] == handoff["summary"]["open"]
    assert dossier["summary"]["working_stack_activation_entries"] == handoff["summary"]["working_stack_activation_entries"]
    activation_dossier = handoff.get("working_stack_activation_dossier", {})
    activation_entries = handoff.get("working_stack_activation_entries", [])
    assert activation_dossier.get("schema") == "abyss_machine_self_awareness_working_stack_activation_dossier_v1"
    assert handoff.get("working_stack_activation_handoff", {}).get("policy", {}).get("host_layer_mutates_stack") is False
    assert handoff.get("working_stack_activation_handoff", {}).get("policy", {}).get("abyss_machine_executes_stack_change") is False
    assert handoff["summary"]["working_stack_activation_entries"] == len(activation_entries)
    assert set(handoff.get("working_stack_activation_service_ids", [])) == {
        entry.get("service") for entry in activation_entries
    }
    assert activation_dossier.get("summary", {}).get("synthetic_scenarios") == len(activation_entries)
    assert activation_dossier.get("summary", {}).get("synthetic_scenarios_complete") == len(activation_entries)
    assert activation_dossier.get("summary", {}).get("closure_acceptance_packets") == len(activation_entries)
    assert activation_dossier.get("summary", {}).get("closure_acceptance_packets_complete") == len(activation_entries)
    assert activation_dossier.get("summary", {}).get("activation_compat_requirements") == len(activation_entries)
    assert activation_dossier.get("synthetic_scenario_matrix", {}).get("ok") is True
    assert activation_dossier.get("closure_acceptance_matrix", {}).get("ok") is True
    proof_summary = handoff.get("working_stack_activation_synthetic_proof_summary", {})
    proofs_by_service = handoff.get("working_stack_activation_synthetic_proofs_by_service", {})
    smoke_summary = handoff.get("working_stack_activation_smoke_summary", {})
    smoke_by_service = handoff.get("working_stack_activation_smoke_by_service", {})
    smoke_compact_by_service = handoff.get("working_stack_activation_smoke_compact_by_service", {})
    assert proof_summary.get("schema") == "abyss_machine_self_awareness_export_working_stack_activation_synthetic_proof_summary_v1"
    assert proof_summary.get("proofs") == len(activation_entries)
    assert proof_summary.get("proofs_complete") == len(activation_entries)
    assert proof_summary.get("failed_services") == []
    assert set(proof_summary.get("services", [])) == set(handoff.get("working_stack_activation_service_ids", []))
    assert set(proofs_by_service) == set(handoff.get("working_stack_activation_service_ids", []))
    assert smoke_summary.get("schema") == "abyss_machine_self_awareness_export_working_stack_activation_smoke_summary_v1"
    assert smoke_summary.get("rows") == len(activation_entries)
    assert smoke_summary.get("rows_complete") == len(activation_entries)
    assert smoke_summary.get("failed_services") == []
    assert smoke_summary.get("policy", {}).get("host_layer_mutates_stack") is False
    assert set(smoke_summary.get("services", [])) == set(handoff.get("working_stack_activation_service_ids", []))
    assert set(smoke_by_service) == set(handoff.get("working_stack_activation_service_ids", []))
    assert set(smoke_compact_by_service) == set(handoff.get("working_stack_activation_service_ids", []))
    for entry in activation_entries:
        assert entry.get("schema") == "abyss_machine_self_awareness_working_stack_activation_entry_v1"
        assert entry.get("owner") == "abyss-stack"
        assert entry.get("complete") is True
        assert entry.get("activation_readiness", {}).get("schema") == "abyss_machine_self_awareness_working_stack_activation_readiness_v1"
        closure_acceptance = entry.get("closure_acceptance", {})
        assert closure_acceptance.get("schema") == "abyss_machine_self_awareness_working_stack_activation_closure_acceptance_v1"
        assert closure_acceptance.get("complete") is True
        assert closure_acceptance.get("service") == entry.get("service")
        assert closure_acceptance.get("machine_usage_status") == entry.get("machine_usage_status")
        assert closure_acceptance.get("working_stack_link_id") == entry.get("working_stack_link_id")
        assert closure_acceptance.get("stack_compat_requirement", {}).get("schema") == "abyss_machine_self_awareness_working_stack_activation_compat_requirement_v1"
        assert closure_acceptance.get("stack_compat_requirement", {}).get("owner") == "abyss-stack"
        assert closure_acceptance.get("stack_compat_requirement", {}).get("operator_boundary", {}).get("abyss_machine_executes_stack_change") is False
        assert closure_acceptance.get("policy", {}).get("host_layer_mutates_stack") is False
        assert entry.get("synthetic_scenario", {}).get("schema") == "abyss_machine_self_awareness_working_stack_activation_synthetic_scenario_v1"
        assert entry.get("synthetic_scenario", {}).get("complete") is True
        assert entry.get("synthetic_scenario", {}).get("policy", {}).get("host_layer_mutates_stack") is False
        proof = proofs_by_service.get(entry.get("service"), {})
        assert proof.get("schema") == "abyss_machine_self_awareness_working_stack_activation_synthetic_proof_v1"
        assert proof.get("complete") is True
        assert proof.get("service") == entry.get("service")
        assert proof.get("machine_usage_status") == entry.get("machine_usage_status")
        assert proof.get("working_stack_link_id") == entry.get("working_stack_link_id")
        assert proof.get("policy", {}).get("host_layer_mutates_stack") is False
        smoke = smoke_by_service.get(entry.get("service"), {})
        compact = smoke_compact_by_service.get(entry.get("service"), {})
        assert smoke.get("schema") == "abyss_machine_self_awareness_working_stack_activation_smoke_row_v1"
        assert smoke.get("complete") is True
        assert smoke.get("service") == entry.get("service")
        assert smoke.get("machine_usage_status") == entry.get("machine_usage_status")
        assert smoke.get("working_stack_link_id") == entry.get("working_stack_link_id")
        assert smoke.get("replay", {}).get("divergences") == 0
        assert smoke.get("replay", {}).get("working_stack_gap_replayable") is True
        assert smoke.get("policy", {}).get("host_layer_mutates_stack") is False
        assert compact.get("schema") == "abyss_machine_self_awareness_working_stack_activation_smoke_compact_v1"
        assert compact.get("complete") is True
        assert compact.get("service") == entry.get("service")
        assert compact.get("working_stack_link_id") == entry.get("working_stack_link_id")
        assert compact.get("policy", {}).get("host_layer_mutates_stack") is False
        assert entry.get("missing_checks")
        assert entry.get("runbook_candidate", {}).get("machine_executes_stack_change") is False
        assert entry.get("safe_next_action", {}).get("host_layer_mutates_stack") is False
        assert entry.get("safe_next_action", {}).get("executes_commands") is False
    assert dossier["summary"]["missing_checks"] == handoff["summary"]["closure_readiness_missing_checks"]
    assert handoff["summary"]["closure_readiness_packets"] == len(handoff.get("closure_readiness", []))
    assert handoff["summary"]["closure_readiness_packets"] == len(handoff.get("open_requirements", [])) + len(handoff.get("closed_requirements", []))
    assert handoff["summary"]["stack_requirement_closure_acceptance_packets"] == len(handoff.get("stack_requirement_closure_acceptance_packets", []))
    assert handoff["summary"]["stack_requirement_closure_acceptance_packets_complete"] == len(handoff.get("stack_requirement_closure_acceptance_packets", []))
    assert handoff["summary"]["stack_requirement_compat_requirements"] == len(handoff.get("stack_requirement_closure_acceptance_packets", []))
    assert set(requirements.get("open_stack_ids", [])) == set(handoff.get("open_requirement_ids", []))
    assert set(requirements.get("open_stack_requirement_ids", [])) == set(handoff.get("open_requirement_ids", []))
    ordered_ids = handoff.get("ordered_requirement_ids", [])
    closure_order_ids = [
        item.get("requirement_id")
        for item in handoff.get("closure_order", [])
        if isinstance(item, dict) and item.get("requirement_id")
    ]
    assert ordered_ids == closure_order_ids
    assert set(ordered_ids) == set(handoff.get("open_requirement_ids", []))
    assert handoff["summary"]["closure_order_entries"] == len(handoff.get("closure_order", []))
    assert handoff.get("stack_owner_handoff", {}).get("closure_order_ids") == ordered_ids
    assert handoff.get("stack_owner_handoff", {}).get("policy", {}).get("abyss_machine_executes_stack_change") is False
    assert handoff.get("stack_owner_handoff", {}).get("policy", {}).get("host_layer_mutates_stack") is False
    assert handoff.get("dependency_graph", {}).get("ordered_requirement_ids") == ordered_ids
    assert set(handoff.get("dependency_graph", {}).get("open_requirement_ids", [])) == set(handoff.get("open_requirement_ids", []))
    assert handoff.get("dependency_graph", {}).get("policy", {}).get("host_layer_mutates_stack") is False
    assert handoff.get("dependency_graph", {}).get("policy", {}).get("executes_commands") is False
    coverage_impacts = handoff.get("coverage_impacts", [])
    assert handoff["summary"]["coverage_impact_entries"] == len(coverage_impacts) == len(handoff.get("open_requirements", []))
    assert handoff.get("blocked_coverage_planes") == handoff["summary"]["blocked_coverage_planes"]
    assert handoff.get("blocked_coverage_planes")
    assert set(handoff.get("coverage_impacts_by_requirement", {})) == set(handoff.get("open_requirement_ids", []))
    assert {impact.get("requirement_id") for impact in coverage_impacts if isinstance(impact, dict)} == set(handoff.get("open_requirement_ids", []))
    assert handoff.get("stack_owner_handoff", {}).get("coverage_impacts_by_requirement") == handoff.get("coverage_impacts_by_requirement")
    assert handoff.get("stack_owner_handoff", {}).get("blocked_coverage_planes") == handoff.get("blocked_coverage_planes")
    assert set(handoff.get("blocked_coverage_planes", [])) == {
        plane
        for impact in coverage_impacts
        if isinstance(impact, dict)
        for plane in impact.get("coverage_planes", [])
    }
    verifier_matrix = handoff.get("stack_owner_verifier_matrix", [])
    assert handoff["summary"]["stack_owner_verifier_matrix_entries"] == len(verifier_matrix) == len(handoff.get("open_requirements", []))
    assert set(handoff.get("stack_owner_verifier_matrix_by_requirement", {})) == set(handoff.get("open_requirement_ids", []))
    assert {item.get("requirement_id") for item in verifier_matrix if isinstance(item, dict)} == set(handoff.get("open_requirement_ids", []))
    assert handoff.get("stack_owner_handoff", {}).get("verifier_matrix") == verifier_matrix
    assert handoff.get("stack_owner_handoff", {}).get("verifier_matrix_by_requirement") == handoff.get("stack_owner_verifier_matrix_by_requirement")
    assert handoff["summary"]["stack_owner_verifier_commands"] == sum(len(item.get("verifier_commands", [])) for item in verifier_matrix)
    assert handoff["summary"]["stack_owner_post_close_verifiers"] == sum(len(item.get("post_close_verifiers", [])) for item in verifier_matrix)
    closure_summary = handoff.get("stack_requirement_closure_acceptance_summary", {})
    closure_packets = handoff.get("stack_requirement_closure_acceptance_packets", [])
    closure_by_requirement = handoff.get("stack_requirement_closure_acceptance_packets_by_requirement", {})
    assert closure_summary.get("schema") == "abyss_machine_self_awareness_export_stack_requirement_closure_acceptance_summary_v1"
    assert closure_summary.get("packets") == len(closure_packets) == dossier["summary"]["probes"]
    assert closure_summary.get("packets_complete") == len(closure_packets)
    assert closure_summary.get("policy", {}).get("host_layer_mutates_stack") is False
    assert set(closure_by_requirement) == {entry.get("requirement_id") for entry in dossier.get("entries", []) if isinstance(entry, dict)}
    assert handoff.get("stack_owner_handoff", {}).get("closure_acceptance_summary") == closure_summary
    assert handoff.get("stack_owner_handoff", {}).get("closure_acceptance_packets_by_requirement") == closure_by_requirement
    for packet in closure_packets:
        assert packet.get("schema") == "abyss_machine_self_awareness_stack_requirement_closure_acceptance_v1"
        assert packet.get("complete") is True
        assert packet.get("owner") == "abyss-stack"
        assert packet.get("stack_compat_requirement", {}).get("schema") == "abyss_machine_self_awareness_stack_requirement_compat_requirement_v1"
        assert packet.get("stack_compat_requirement", {}).get("owner") == "abyss-stack"
        assert packet.get("stack_compat_requirement", {}).get("operator_boundary", {}).get("abyss_machine_executes_stack_change") is False
        assert packet.get("policy", {}).get("host_layer_mutates_stack") is False
    if ordered_ids:
        assert handoff["summary"]["top_requirement_id"] == ordered_ids[0]
        assert handoff.get("stack_owner_handoff", {}).get("top_requirement_id") == ordered_ids[0]
    if "stack.trace-backend" in ordered_ids and "stack.langchain-api.graph-observability" in ordered_ids:
        assert ordered_ids.index("stack.trace-backend") < ordered_ids.index("stack.langchain-api.graph-observability")
        assert any(
            edge.get("from") == "stack.langchain-api.graph-observability"
            and edge.get("to") == "stack.trace-backend"
            for edge in handoff.get("dependency_graph", {}).get("edges", [])
            if isinstance(edge, dict)
        )
    assert requirements.get("summary", {}).get("stack_handoff_acceptance_verifiers") == len(handoff.get("open_requirements", []))
    assert requirements.get("summary", {}).get("acceptance_verifier_steps", 0) >= len(handoff.get("open_requirements", []))
    assert requirements.get("summary", {}).get("stack_handoff_coverage_impact_entries") == len(handoff.get("open_requirements", []))
    assert requirements.get("summary", {}).get("stack_handoff_safe_next_actions") == len(handoff.get("open_requirements", []))
    assert set(dossier.get("dependency_graph", {}).get("open_requirement_ids", [])) == set(handoff.get("open_requirement_ids", []))
    assert dossier.get("stack_owner_handoff", {}).get("policy", {}).get("abyss_machine_executes_stack_change") is False

    for requirement in handoff.get("open_requirements", []):
        assert requirement.get("owner") == "abyss-stack"
        assert requirement.get("closed_by_current_probe") is False
        assert requirement.get("closure_blockers")
        readiness = requirement.get("closure_readiness", {})
        assert readiness.get("schema") == "abyss_machine_stack_handoff_closure_readiness_v1"
        assert readiness.get("requirement_id") == requirement.get("id")
        assert readiness.get("missing_checks")
        assert readiness.get("closure_evidence_needed")
        assert readiness.get("verifier_commands")
        assert readiness.get("policy", {}).get("host_layer_mutates_stack") is False
        assert readiness.get("policy", {}).get("executes_commands") is False
        assert requirement.get("current_state")
        assert requirement.get("acceptance_verifiers")
        assert requirement.get("machine_closure_probe", {}).get("success_predicates")
        assert requirement.get("coverage_impact", {}).get("schema") == "abyss_machine_self_awareness_stack_coverage_impact_v1"
        assert requirement.get("coverage_impact", {}).get("policy", {}).get("host_layer_mutates_stack") is False
        closure_acceptance = requirement.get("closure_acceptance", {})
        assert closure_acceptance.get("schema") == "abyss_machine_self_awareness_stack_requirement_closure_acceptance_v1"
        assert closure_acceptance.get("complete") is True
        assert closure_acceptance.get("requirement_id") == requirement.get("id")
        assert closure_acceptance.get("stack_compat_requirement", {}).get("owner") == "abyss-stack"
        assert closure_acceptance.get("policy", {}).get("host_layer_mutates_stack") is False
        assert requirement.get("safe_next_action", {}).get("host_layer_mutates_stack") is False
        assert requirement.get("current_state_digest", {}).get("schema") == "abyss_machine_self_awareness_requirement_current_state_digest_v1"
        assert requirement.get("current_state_digest", {}).get("policy", {}).get("raw_payloads_included") is False
        assert requirement.get("current_state_digest", {}).get("policy", {}).get("raw_secrets_included") is False
        assert requirement.get("handoff_contract_complete") is True
        runbook = requirement.get("runbook_candidate", {})
        assert runbook.get("machine_executes_stack_change") is False
        assert runbook.get("host_layer_mutates_stack") is False
        assert runbook.get("acceptance_steps")
        assert runbook.get("acceptance_verifiers")
        assert runbook.get("rollback")
    for impact in coverage_impacts:
        assert impact.get("schema") == "abyss_machine_self_awareness_stack_coverage_impact_v1"
        assert impact.get("coverage_planes")
        assert impact.get("proof_commands")
        assert impact.get("policy", {}).get("host_layer_mutates_stack") is False
        assert impact.get("policy", {}).get("executes_commands") is False
        assert impact.get("policy", {}).get("raw_secrets_included") is False
    for item in verifier_matrix:
        assert item.get("schema") == "abyss_machine_self_awareness_export_stack_owner_verifier_v1"
        assert item.get("owner") == "abyss-stack"
        assert item.get("blocking_check_keys")
        assert item.get("verifier_commands")
        assert item.get("acceptance_verifiers")
        assert item.get("post_close_verifiers")
        assert item.get("coverage_planes")
        assert item.get("coverage_impact", {}).get("schema") == "abyss_machine_self_awareness_stack_coverage_impact_v1"
        assert item.get("safe_next_action", {}).get("host_layer_mutates_stack") is False
        assert item.get("policy", {}).get("host_layer_mutates_stack") is False
        assert item.get("policy", {}).get("executes_commands") is False
        assert item.get("policy", {}).get("actions_executed") is False
        assert item.get("policy", {}).get("raw_secrets_included") is False
    for entry in dossier.get("open_requirements", []):
        assert entry.get("owner") == "abyss-stack"
        assert entry.get("complete") is True
        assert entry.get("closure_readiness", {}).get("schema") == "abyss_machine_stack_handoff_closure_readiness_v1"
        assert entry.get("closure_acceptance", {}).get("schema") == "abyss_machine_self_awareness_stack_requirement_closure_acceptance_v1"
        assert entry.get("closure_acceptance", {}).get("complete") is True
        assert entry.get("closure_acceptance", {}).get("requirement_id") == entry.get("requirement_id")
        assert entry.get("closure_acceptance", {}).get("policy", {}).get("host_layer_mutates_stack") is False
        assert entry.get("runbook_candidate", {}).get("machine_executes_stack_change") is False
        assert entry.get("safe_next_action", {}).get("host_layer_mutates_stack") is False

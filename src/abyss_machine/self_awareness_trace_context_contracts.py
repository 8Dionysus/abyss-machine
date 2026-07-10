from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import self_awareness_contracts


DocumentPort = Callable[..., Any]


@dataclass(frozen=True)
class SelfAwarenessTraceContextPaths:
    stack_observability_latest: Path
    requirement_probes_latest: Path
    probe_latest: Path
    context_latest: Path
    timeline_latest: Path
    episodes_latest: Path
    capabilities_latest: Path
    trace_context_latest: Path
    trace_context_root: Path


@dataclass(frozen=True)
class SelfAwarenessTraceContextConfig:
    schema_prefix: str
    version: str


@dataclass(frozen=True)
class SelfAwarenessTraceContextRuntimePort:
    load_latest_json: DocumentPort
    now_iso: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessTraceContextRefreshPort:
    stack_observability: DocumentPort
    requirement_probes: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessTraceContextContractPort:
    stack_requirement_coverage_impact: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessTraceContextPersistencePort:
    write_latest_and_history: DocumentPort


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def trace_context_links_from_doc(
    name: str,
    doc: dict[str, Any],
    *,
    limit: int = 16,
) -> list[dict[str, Any]]:
    nested_get = self_awareness_contracts.nested_get
    stable_hash_json = self_awareness_contracts.stable_hash_json
    links: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_link(path: str, item: dict[str, Any]) -> None:
        context = item.get("context") if isinstance(item.get("context"), dict) else item
        traceparent = context.get("traceparent")
        trace_id = context.get("trace_id")
        span_id = context.get("span_id")
        synthetic_run_id = context.get("synthetic_run_id") or item.get("run_id")
        if not any((traceparent, trace_id, span_id, synthetic_run_id)):
            return
        row = {
            "source": name,
            "json_path": path,
            "event_id": item.get("event_id"),
            "episode_id": item.get("episode_id") or item.get("id"),
            "thread_id": item.get("thread_id") or context.get("thread_id"),
            "checkpoint_id": item.get("checkpoint_id") or context.get("checkpoint_id"),
            "signal": item.get("signal"),
            "service": nested_get(item, ["resource", "service"]) or item.get("service"),
            "traceparent": traceparent,
            "trace_id": trace_id,
            "span_id": span_id,
            "synthetic_run_id": synthetic_run_id,
        }
        digest = stable_hash_json(row, length=16)
        if digest in seen:
            return
        seen.add(digest)
        links.append({key: value for key, value in row.items() if value not in (None, "")})

    def visit(value: Any, path: str, depth: int = 0) -> None:
        if len(links) >= limit or depth > 8:
            return
        if isinstance(value, dict):
            if any(key in value for key in ("traceparent", "trace_id", "span_id", "synthetic_run_id")):
                add_link(path, value)
            context = value.get("context") if isinstance(value.get("context"), dict) else {}
            if any(key in context for key in ("traceparent", "trace_id", "span_id", "synthetic_run_id")):
                add_link(path, value)
            for key, child in value.items():
                if isinstance(child, (dict, list)):
                    visit(child, f"{path}.{key}" if path else str(key), depth + 1)
        elif isinstance(value, list):
            for index, child in enumerate(value[:128]):
                if isinstance(child, (dict, list)):
                    visit(child, f"{path}[{index}]", depth + 1)

    visit(doc, name)
    return links


def trace_context_fallback_complete(data: Any, *, schema_prefix: str) -> bool:
    nested_get = self_awareness_contracts.nested_get
    return (
        isinstance(data, dict)
        and data.get("schema") == f"{schema_prefix}_self_awareness_trace_context_fallback_v1"
        and data.get("stack_requirement_id") == "stack.trace-backend"
        and nested_get(data, ["summary", "traceparent_log_query_ok"]) is True
        and nested_get(data, ["summary", "stack_requirement_not_closed_by_fallback"]) is True
        and nested_get(data, ["fallback", "loki_trace_context", "raw_log_exports_stored"]) is False
        and nested_get(data, ["policy", "host_layer_mutates_stack"]) is False
        and nested_get(data, ["policy", "writes_project_roots"]) is False
        and nested_get(data, ["policy", "closes_stack_requirement"]) is False
        and nested_get(data, ["policy", "adds_loki_labels"]) is False
        and nested_get(data, ["policy", "raw_span_payloads_stored"]) is False
        and nested_get(data, ["policy", "raw_log_exports_stored"]) is False
        and bool(data.get("evidence_refs"))
        and bool(data.get("safe_next_action"))
    )


def trace_context_fallback(
    write_latest: bool = True,
    *,
    stack_observability_doc: dict[str, Any] | None = None,
    requirement_probes_doc: dict[str, Any] | None = None,
    probe_doc: dict[str, Any] | None = None,
    context_doc: dict[str, Any] | None = None,
    timeline_doc: dict[str, Any] | None = None,
    episodes_doc: dict[str, Any] | None = None,
    paths: SelfAwarenessTraceContextPaths,
    config: SelfAwarenessTraceContextConfig,
    runtime_port: SelfAwarenessTraceContextRuntimePort,
    refresh_port: SelfAwarenessTraceContextRefreshPort,
    contract_port: SelfAwarenessTraceContextContractPort,
    persistence_port: SelfAwarenessTraceContextPersistencePort,
) -> dict[str, Any]:
    schema_prefix = config.schema_prefix
    nested_get = self_awareness_contracts.nested_get
    generated_at = runtime_port.now_iso()
    stack_observability_doc = (
        stack_observability_doc
        if isinstance(stack_observability_doc, dict)
        else refresh_port.stack_observability(write_latest=True)
    )
    requirement_probes_doc = (
        requirement_probes_doc
        if isinstance(requirement_probes_doc, dict)
        else refresh_port.requirement_probes(write_latest=True)
    )
    probe_doc = (
        probe_doc
        if isinstance(probe_doc, dict)
        else runtime_port.load_latest_json(
            paths.probe_latest,
            f"{schema_prefix}_self_awareness_probe_v1",
        )
    )
    context_doc = (
        context_doc
        if isinstance(context_doc, dict)
        else runtime_port.load_latest_json(
            paths.context_latest,
            f"{schema_prefix}_self_awareness_context_v1",
        )
    )
    timeline_doc = (
        timeline_doc
        if isinstance(timeline_doc, dict)
        else runtime_port.load_latest_json(
            paths.timeline_latest,
            f"{schema_prefix}_self_awareness_timeline_v1",
        )
    )
    episodes_doc = (
        episodes_doc
        if isinstance(episodes_doc, dict)
        else runtime_port.load_latest_json(
            paths.episodes_latest,
            f"{schema_prefix}_self_awareness_episodes_v1",
        )
    )

    probes = (
        requirement_probes_doc.get("probes")
        if isinstance(requirement_probes_doc.get("probes"), list)
        else []
    )
    trace_probe = next(
        (
            probe
            for probe in probes
            if isinstance(probe, dict)
            and str(probe.get("id") or probe.get("requirement_id") or "")
            == "stack.trace-backend"
        ),
        {},
    )
    current_state = (
        trace_probe.get("current_state")
        if isinstance(trace_probe.get("current_state"), dict)
        else {}
    )
    closure_readiness = (
        trace_probe.get("closure_readiness")
        if isinstance(trace_probe.get("closure_readiness"), dict)
        else {}
    )
    trace_checks = {
        str(check.get("key")): check
        for check in (
            trace_probe.get("checks") if isinstance(trace_probe.get("checks"), list) else []
        )
        if isinstance(check, dict) and check.get("key")
    }
    if not current_state:
        capabilities_doc = runtime_port.load_latest_json(
            paths.capabilities_latest,
            f"{schema_prefix}_self_awareness_capabilities_v1",
        )
        trace_backend = nested_get(capabilities_doc, ["raw", "trace_backend"])
        trace_backend = trace_backend if isinstance(trace_backend, dict) else {}
        join = (
            trace_backend.get("join_readiness")
            if isinstance(trace_backend.get("join_readiness"), dict)
            else {}
        )
        pipeline = (
            trace_backend.get("pipeline_evidence")
            if isinstance(trace_backend.get("pipeline_evidence"), dict)
            else {}
        )
        trace_ctx = (
            trace_backend.get("trace_context")
            if isinstance(trace_backend.get("trace_context"), dict)
            else {}
        )
        if join:
            current_state = {
                "requirement_status": "closed_by_current_probe"
                if join.get("span_log_metric_join_supported") is True
                else "open",
                "trace_backend_ready": join.get("trace_backend_ready"),
                "trace_search_readable": join.get("trace_search_readable"),
                "span_log_metric_join_supported": join.get("span_log_metric_join_supported"),
                "metrics_log_pipeline_readable": pipeline.get("metrics_log_pipeline_readable"),
                "traceparent_log_query_ok": trace_ctx.get("traceparent_log_query_ok"),
                "traceparent_log_entries_seen": trace_ctx.get("traceparent_log_entries_seen"),
                "trace_context_query_safe_empty": trace_ctx.get("trace_context_query_safe_empty"),
                "alloy_seen": pipeline.get("alloy_seen"),
                "loki_ready": pipeline.get("loki_ready"),
                "loki_labels_readable": pipeline.get("loki_labels_readable"),
            }
            trace_probe = {
                "id": "stack.trace-backend",
                "owner": "abyss-stack",
                "status": current_state["requirement_status"],
                "closed_by_current_probe": join.get("span_log_metric_join_supported") is True,
                "probe_kind": "capability_trace_backend",
                "current_state": current_state,
                "checks": [],
                "closure_readiness": {
                    "missing_checks": join.get("missing")
                    if isinstance(join.get("missing"), list)
                    else []
                },
            }
            closure_readiness = trace_probe["closure_readiness"]
    stack_summary = (
        stack_observability_doc.get("summary")
        if isinstance(stack_observability_doc.get("summary"), dict)
        else {}
    )
    loki_trace = nested_get(stack_observability_doc, ["loki", "trace_context"])
    loki_trace = loki_trace if isinstance(loki_trace, dict) else {}
    traceparent_query_ok = bool(current_state.get("traceparent_log_query_ok") or loki_trace.get("ok"))
    traceparent_entries = _safe_int(
        current_state.get("traceparent_log_entries_seen"),
        _safe_int(loki_trace.get("entry_count"), 0),
    )
    trace_context_query_safe_empty = bool(
        current_state.get("trace_context_query_safe_empty")
        or (traceparent_query_ok and traceparent_entries == 0)
    )
    trace_backend_ready = bool(current_state.get("trace_backend_ready"))
    trace_search_readable = bool(current_state.get("trace_search_readable"))
    span_log_metric_join_supported = bool(current_state.get("span_log_metric_join_supported"))
    metrics_log_pipeline_readable = bool(current_state.get("metrics_log_pipeline_readable"))
    if not metrics_log_pipeline_readable:
        metrics_log_pipeline_readable = bool(
            "alloy"
            in {
                str(item)
                for item in (
                    stack_summary.get("promql_jobs_up")
                    if isinstance(stack_summary.get("promql_jobs_up"), list)
                    else []
                )
            }
            and _safe_int(stack_summary.get("logql_queries_ok"), 0) > 0
        )
    coverage_impact = contract_port.stack_requirement_coverage_impact("stack.trace-backend")
    bounded_trace_links = (
        trace_context_links_from_doc("probe", probe_doc, limit=8)
        + trace_context_links_from_doc("context", context_doc, limit=8)
        + trace_context_links_from_doc("timeline", timeline_doc, limit=8)
        + trace_context_links_from_doc("episodes", episodes_doc, limit=8)
    )[:24]
    probe_trace_context = {
        "run_id": probe_doc.get("run_id"),
        "traceparent": probe_doc.get("traceparent"),
        "trace_id": None,
        "span_id": None,
        "schema": probe_doc.get("schema"),
        "ok": probe_doc.get("ok"),
        "generated_at": probe_doc.get("generated_at"),
    }
    if probe_trace_context.get("traceparent"):
        parts = str(probe_trace_context["traceparent"]).split("-")
        if len(parts) >= 4:
            probe_trace_context["trace_id"] = parts[1]
            probe_trace_context["span_id"] = parts[2]
    status = (
        "stack_trace_backend_ready_observed"
        if trace_backend_ready and trace_search_readable and span_log_metric_join_supported
        else "fallback_ready_stack_trace_backend_open"
        if traceparent_query_ok and metrics_log_pipeline_readable
        else "fallback_degraded_stack_trace_backend_open"
    )
    trace_context_samples = [
        {
            "ts": sample.get("ts"),
            "labels": sample.get("labels"),
            "line_hash": sample.get("line_hash"),
        }
        for sample in (
            loki_trace.get("samples") if isinstance(loki_trace.get("samples"), list) else []
        )[:3]
        if isinstance(sample, dict)
    ]
    missing_checks = (
        closure_readiness.get("missing_checks")
        if isinstance(closure_readiness.get("missing_checks"), list)
        else []
    )
    open_requirements = (
        requirement_probes_doc.get("open_requirements")
        if isinstance(requirement_probes_doc.get("open_requirements"), list)
        else []
    )

    def open_requirement_id(row: dict[str, Any]) -> str:
        return str(row.get("id") or row.get("requirement_id") or "")

    def next_open_stack_requirement() -> dict[str, Any]:
        candidates = [
            row
            for row in open_requirements
            if isinstance(row, dict)
            and str(row.get("owner") or "abyss-stack") == "abyss-stack"
            and open_requirement_id(row)
        ]
        preferred_order = (
            "stack.grafana.datasource-read",
            "stack.database-graph.read-route",
            "stack.langchain-api.graph-observability",
            "stack.trace-backend",
        )
        for requirement_id in preferred_order:
            for row in candidates:
                if open_requirement_id(row) == requirement_id:
                    return row
        return candidates[0] if candidates else {}

    next_requirement = next_open_stack_requirement() if span_log_metric_join_supported else {}
    next_requirement_safe_action = (
        next_requirement.get("safe_next_action")
        if isinstance(next_requirement.get("safe_next_action"), dict)
        else {}
    )
    next_requirement_id = open_requirement_id(next_requirement)
    next_requirement_command_by_id = {
        "stack.grafana.datasource-read": "expose a stack-owned bounded Grafana datasource inventory route or read-only datasource export with secrets redacted",
        "stack.database-graph.read-route": "expose stack-owned bounded Postgres schema/freshness and Neo4j label/relationship/freshness inventory routes",
        "stack.langchain-api.graph-observability": "wire LangGraph/langchain-api thread, checkpoint, and trace inventory to the readable trace backend",
    }
    safe_next_requirement_id = (
        next_requirement_id
        if span_log_metric_join_supported and next_requirement_id
        else "stack.trace-backend"
    )
    safe_next_stack_command = (
        str(
            next_requirement_safe_action.get("stack_command_candidate")
            or next_requirement.get("summary")
            or next_requirement.get("title")
            or next_requirement_command_by_id.get(next_requirement_id)
            or "continue with the next open stack-owned self-awareness inventory route"
        )
        if span_log_metric_join_supported and next_requirement_id
        else "configure/provide Tempo or compatible trace backend, W3C traceparent propagation, and bounded search route inside abyss-stack"
    )
    data = {
        "schema": f"{schema_prefix}_self_awareness_trace_context_fallback_v1",
        "version": config.version,
        "generated_at": generated_at,
        "ok": bool(trace_probe and traceparent_query_ok and metrics_log_pipeline_readable),
        "status": status,
        "stack_requirement_id": "stack.trace-backend",
        "stack_requirement_status": trace_probe.get("status"),
        "closed_by_current_probe": trace_probe.get("closed_by_current_probe"),
        "closes_stack_requirement": False,
        "summary": {
            "status": status,
            "trace_backend_ready": trace_backend_ready,
            "trace_search_readable": trace_search_readable,
            "span_log_metric_join_supported": span_log_metric_join_supported,
            "metrics_log_pipeline_readable": metrics_log_pipeline_readable,
            "traceparent_log_query_ok": traceparent_query_ok,
            "traceparent_log_entries_seen": traceparent_entries,
            "trace_context_query_safe_empty": trace_context_query_safe_empty,
            "bounded_trace_context_links": len(bounded_trace_links),
            "stack_requirement_not_closed_by_fallback": True,
            "blocked_coverage_planes": []
            if span_log_metric_join_supported
            else coverage_impact.get("coverage_planes"),
            "missing_checks": missing_checks,
            "next_open_stack_requirement_id": next_requirement_id
            if span_log_metric_join_supported
            else "stack.trace-backend",
        },
        "trace_backend_requirement": {
            "id": trace_probe.get("id") or "stack.trace-backend",
            "owner": trace_probe.get("owner") or "abyss-stack",
            "probe_kind": trace_probe.get("probe_kind"),
            "current_state": current_state,
            "checks": {
                key: {
                    "ok": value.get("ok"),
                    "level": value.get("level"),
                    "message": value.get("message"),
                }
                for key, value in trace_checks.items()
            },
            "closure_readiness": closure_readiness,
            "coverage_impact": coverage_impact,
        },
        "fallback": {
            "schema": f"{schema_prefix}_self_awareness_trace_context_fallback_surface_v1",
            "loki_trace_context": {
                "query": loki_trace.get("query") or current_state.get("loki_traceparent_query"),
                "query_ok": traceparent_query_ok,
                "entries_seen": traceparent_entries,
                "safe_empty_result": trace_context_query_safe_empty,
                "samples": trace_context_samples,
                "stores_line_hashes_only": True,
                "raw_log_exports_stored": False,
            },
            "alloy_loki_pipeline": {
                "promql_jobs_up": stack_summary.get("promql_jobs_up")
                if isinstance(stack_summary.get("promql_jobs_up"), list)
                else [],
                "logql_queries_ok": stack_summary.get("logql_queries_ok"),
                "logql_entries_seen": stack_summary.get("logql_entries_seen"),
                "alloy_seen": bool(
                    current_state.get("alloy_seen")
                    or "alloy"
                    in {
                        str(item)
                        for item in (
                            stack_summary.get("promql_jobs_up")
                            if isinstance(stack_summary.get("promql_jobs_up"), list)
                            else []
                        )
                    }
                ),
                "metrics_log_pipeline_readable": metrics_log_pipeline_readable,
            },
            "self_awareness_probe_trace": probe_trace_context,
            "bounded_trace_links": bounded_trace_links,
            "fallback_limit": (
                "Trace backend readiness and bounded search are observed; this surface remains a context packet, not the stack backend itself."
                if span_log_metric_join_supported
                else "Log/context trace evidence is readable, but span/log/metric joins remain unproven until stack.trace-backend closes."
            ),
        },
        "safe_next_action": {
            "owner_route": next_requirement_safe_action.get("owner_route") or "abyss-stack",
            "requirement_id": safe_next_requirement_id,
            "command": next_requirement_safe_action.get("command")
            or "abyss-machine self-awareness requirement-probes --json",
            "stack_command_candidate": safe_next_stack_command,
            "requires_human_approval": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "automatic": False,
        },
        "evidence_refs": [
            {"path": str(paths.stack_observability_latest), "schema": stack_observability_doc.get("schema"), "section": "loki.trace_context"},
            {"path": str(paths.requirement_probes_latest), "schema": requirement_probes_doc.get("schema"), "requirement_id": "stack.trace-backend"},
            {"path": str(paths.probe_latest), "schema": probe_doc.get("schema"), "run_id": probe_doc.get("run_id")},
            {"path": str(paths.context_latest), "schema": context_doc.get("schema"), "section": "trace_contexts"},
            {"path": str(paths.timeline_latest), "schema": timeline_doc.get("schema"), "section": "trace_contexts"},
            {"path": str(paths.episodes_latest), "schema": episodes_doc.get("schema"), "section": "trace_contexts"},
        ],
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "closes_stack_requirement": False,
            "adds_loki_labels": False,
            "high_cardinality_labels_added": False,
            "raw_span_payloads_stored": False,
            "raw_log_exports_stored": False,
            "raw_trace_payloads_stored": False,
            "raw_private_content": False,
            "fallback_is_not_backend": True,
        },
        "tests": {
            "smoke": "abyss-machine self-awareness trace-context --json",
            "requirement_probe": "abyss-machine self-awareness requirement-probes --json",
            "cycle": "abyss-machine self-awareness cycle --json includes trace_context_fallback in chain",
            "validator": "abyss-machine self-awareness validate --json includes trace_context_fallback_depth",
        },
    }
    if write_latest:
        errors = persistence_port.write_latest_and_history(
            data,
            paths.trace_context_latest,
            paths.trace_context_root,
        )
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data

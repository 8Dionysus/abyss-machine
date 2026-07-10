from __future__ import annotations

import collections
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import self_awareness_contracts


DocumentPort = Callable[..., Any]


@dataclass(frozen=True)
class SelfAwarenessQueryCorrelationPaths:
    events_latest: Path
    episodes_latest: Path
    spatial_graph_latest: Path
    capabilities_latest: Path
    context_latest: Path
    stack_observability_latest: Path
    collect_latest: Path
    ai_capabilities_latest: Path
    ai_llm_resident_status_latest: Path
    rag_validate_latest: Path
    nervous_brief_latest: Path
    memory_latest: Path
    resource_latest: Path
    mode_latest: Path
    maps_latest: Path
    graph_latest: Path
    rag_trace_latest: Path
    process_container_latest: Path
    query_latest: Path
    query_root: Path
    correlation_latest: Path
    correlation_root: Path


@dataclass(frozen=True)
class SelfAwarenessQueryCorrelationConfig:
    schema_prefix: str
    version: str


@dataclass(frozen=True)
class SelfAwarenessQueryCorrelationRuntimePort:
    load_events: DocumentPort
    load_latest_json: DocumentPort
    now_iso: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessQueryCorrelationRefreshPort:
    spatial_graph: DocumentPort
    memory_space_overlay: DocumentPort
    capabilities: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessQueryCorrelationContractPort:
    redact_text: DocumentPort
    query_terms: DocumentPort
    match_score: DocumentPort
    correlation_index: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessQueryCorrelationPersistencePort:
    write_latest_and_history: DocumentPort


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def query(
    query_text: str = "",
    limit: int = 20,
    write_latest: bool = True,
    *,
    events: list[dict[str, Any]] | None = None,
    episodes: dict[str, Any] | None = None,
    graph: dict[str, Any] | None = None,
    capabilities: dict[str, Any] | None = None,
    memory_space: dict[str, Any] | None = None,
    paths: SelfAwarenessQueryCorrelationPaths,
    config: SelfAwarenessQueryCorrelationConfig,
    runtime_port: SelfAwarenessQueryCorrelationRuntimePort,
    refresh_port: SelfAwarenessQueryCorrelationRefreshPort,
    contract_port: SelfAwarenessQueryCorrelationContractPort,
    persistence_port: SelfAwarenessQueryCorrelationPersistencePort,
) -> dict[str, Any]:
    schema_prefix = config.schema_prefix
    generated_at = runtime_port.now_iso()
    text = contract_port.redact_text(query_text or "latest", 240)
    limit = max(1, min(100, _safe_int(limit, 20)))
    events = events if isinstance(events, list) else runtime_port.load_events(refresh=True)
    episodes = (
        episodes
        if isinstance(episodes, dict)
        else runtime_port.load_latest_json(
            paths.episodes_latest,
            f"{schema_prefix}_self_awareness_episodes_v1",
        )
    )
    graph = graph if isinstance(graph, dict) else refresh_port.spatial_graph(write_latest=True)
    capabilities = (
        capabilities
        if isinstance(capabilities, dict)
        else runtime_port.load_latest_json(
            paths.capabilities_latest,
            f"{schema_prefix}_self_awareness_capabilities_v1",
        )
    )
    if not isinstance(memory_space, dict):
        graph_memory_space = graph.get("memory_space_overlay")
        memory_space = (
            graph_memory_space
            if isinstance(graph_memory_space, dict)
            else refresh_port.memory_space_overlay(events)
        )
    terms = contract_port.query_terms(text)

    def top_hits(items: list[Any]) -> list[Any]:
        scored = []
        for item in items:
            score = contract_port.match_score(item, text)
            if score > 0:
                scored.append((score, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in scored[:limit]]

    episode_rows = [
        item
        for item in (episodes.get("episodes") if isinstance(episodes.get("episodes"), list) else [])
        if isinstance(item, dict)
    ]
    node_rows = [
        item
        for item in (graph.get("nodes") if isinstance(graph.get("nodes"), list) else [])
        if isinstance(item, dict)
    ]
    memory_space_rows = []
    for key in (
        "retrieval_packets",
        "freshness_gates",
        "spatial_overlays",
        "stack_semantic_backends",
        "event_contexts",
    ):
        rows = memory_space.get(key) if isinstance(memory_space.get(key), list) else []
        for row in rows:
            if isinstance(row, dict):
                row_copy = dict(row)
                row_copy["memory_space_section"] = key
                memory_space_rows.append(row_copy)
    event_hits = top_hits([event for event in events if isinstance(event, dict)])
    episode_hits = top_hits(episode_rows)
    node_hits = top_hits(node_rows)
    memory_space_hits = top_hits(memory_space_rows)
    query_plan = {
        "terms": terms,
        "match_strategy": "bounded_term_score_over_redacted_json",
        "promql": [
            'up{job=~"loki|alloy|grafana|prometheus"}',
            'ALERTS{alertstate=~"firing|pending"}',
        ],
        "logql": [
            '{container="route-api"}',
            '{source="podman-journal-event"}',
            '{container="route-api"} |= "traceparent"',
        ],
        "context_keys": ["trace_id", "traceparent", "synthetic_run_id", "alert_fingerprint"],
        "readmodels": [
            str(paths.ai_capabilities_latest),
            str(paths.ai_llm_resident_status_latest),
            str(paths.rag_validate_latest),
            str(paths.nervous_brief_latest),
            str(paths.memory_latest),
            str(paths.resource_latest),
            str(paths.mode_latest),
            str(paths.maps_latest),
            str(paths.graph_latest),
            str(paths.rag_trace_latest),
        ],
        "bounded": True,
        "raw_secret_storage": False,
        "freshness_must_precede_reasoning": True,
        "raw_evidence_is_not_truth": True,
    }
    refs = [
        {"path": str(paths.events_latest), "matches": len(event_hits)},
        {"path": str(paths.episodes_latest), "matches": len(episode_hits)},
        {"path": str(paths.spatial_graph_latest), "matches": len(node_hits)},
        {"path": str(paths.capabilities_latest), "ok": capabilities.get("ok")},
        {"path": str(paths.context_latest), "memory_space_matches": len(memory_space_hits)},
    ]
    data = {
        "schema": f"{schema_prefix}_self_awareness_query_v1",
        "version": config.version,
        "generated_at": generated_at,
        "ok": True,
        "query": text,
        "summary": {
            "event_hits": len(event_hits),
            "episode_hits": len(episode_hits),
            "node_hits": len(node_hits),
            "memory_space_hits": len(memory_space_hits),
            "limit": limit,
        },
        "query_plan": query_plan,
        "results": {
            "events": event_hits,
            "episodes": episode_hits,
            "spatial_nodes": node_hits,
            "memory_space": memory_space_hits,
        },
        "evidence_refs": refs,
        "policy": {
            "bounded_results": True,
            "redacted_query": text,
            "does_not_mutate_stack": True,
            "freshness_must_precede_reasoning": True,
            "raw_evidence_is_not_truth": True,
            "raw_private_content": False,
        },
    }
    if write_latest:
        errors = persistence_port.write_latest_and_history(
            data,
            paths.query_latest,
            paths.query_root,
        )
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def correlation(
    write_latest: bool = True,
    *,
    events: list[dict[str, Any]] | None = None,
    capabilities: dict[str, Any] | None = None,
    stack: dict[str, Any] | None = None,
    index: dict[str, Any] | None = None,
    episodes: dict[str, Any] | None = None,
    paths: SelfAwarenessQueryCorrelationPaths,
    config: SelfAwarenessQueryCorrelationConfig,
    runtime_port: SelfAwarenessQueryCorrelationRuntimePort,
    refresh_port: SelfAwarenessQueryCorrelationRefreshPort,
    contract_port: SelfAwarenessQueryCorrelationContractPort,
    persistence_port: SelfAwarenessQueryCorrelationPersistencePort,
) -> dict[str, Any]:
    schema_prefix = config.schema_prefix
    nested_get = self_awareness_contracts.nested_get
    generated_at = runtime_port.now_iso()
    events = events if isinstance(events, list) else runtime_port.load_events(refresh=True)
    capabilities = (
        capabilities
        if isinstance(capabilities, dict)
        else runtime_port.load_latest_json(
            paths.capabilities_latest,
            f"{schema_prefix}_self_awareness_capabilities_v1",
        )
    )
    if not capabilities.get("schema"):
        capabilities = refresh_port.capabilities(write_latest=True)
    stack = (
        stack
        if isinstance(stack, dict)
        else runtime_port.load_latest_json(
            paths.stack_observability_latest,
            f"{schema_prefix}_stack_observability_v1",
        )
    )
    index = index if isinstance(index, dict) else contract_port.correlation_index(events)
    jobs = nested_get(stack, ["prometheus", "jobs"]) or {}
    jobs_up = (
        {str(job): str(value) in {"1", "1.0"} for job, value in jobs.items()}
        if isinstance(jobs, dict)
        else {}
    )
    core_jobs = [job for job in ("prometheus", "grafana", "loki", "alloy") if job in jobs_up]
    availability = round(sum(1 for job in core_jobs if jobs_up.get(job)) / max(1, len(core_jobs)), 3)
    slo_views = [
        {
            "id": "stack-core-up",
            "objective": "Prometheus, Grafana, Loki, and Alloy are up in current evidence window",
            "availability_ratio": availability,
            "error_budget_remaining_ratio": max(0.0, round(1.0 - (1.0 - availability), 3)),
            "evidence_refs": [
                {"path": str(paths.stack_observability_latest), "locator": "prometheus.jobs"}
            ],
            "truth_level": "current_window",
        }
    ]
    signal_counts = dict(collections.Counter(str(event.get("signal")) for event in events))
    source_counts = dict(collections.Counter(str(event.get("source")) for event in events))
    anomaly_baselines = [
        {
            "id": "signal-distribution-current-window",
            "baseline_kind": "current_window_counts",
            "counts": signal_counts,
            "confidence": "low" if len(events) < 50 else "medium",
            "reason": "Uses bounded latest/history evidence; broaden window before production anomaly claims.",
            "evidence_refs": [{"path": str(paths.events_latest), "events": len(events)}],
        },
        {
            "id": "source-distribution-current-window",
            "baseline_kind": "current_window_counts",
            "counts": source_counts,
            "confidence": "low" if len(events) < 50 else "medium",
            "reason": "Current-window baseline prevents blind anomaly claims while history matures.",
            "evidence_refs": [{"path": str(paths.events_latest), "events": len(events)}],
        },
    ]
    dependencies = [
        {"from": "grafana", "to": "prometheus", "kind": "datasource", "evidence_refs": [{"path": str(paths.stack_observability_latest)}]},
        {"from": "grafana", "to": "loki", "kind": "datasource", "evidence_refs": [{"path": str(paths.stack_observability_latest)}]},
        {"from": "prometheus", "to": "alertmanager", "kind": "alert_route", "evidence_refs": [{"path": str(paths.capabilities_latest)}]},
        {"from": "alloy", "to": "loki", "kind": "log_pipeline", "evidence_refs": [{"path": str(paths.stack_observability_latest), "locator": "loki.labels"}]},
        {"from": "abyss-machine:self-awareness", "to": "prometheus", "kind": "read_only_query", "evidence_refs": [{"path": str(paths.collect_latest)}]},
        {"from": "abyss-machine:self-awareness", "to": "loki", "kind": "read_only_query", "evidence_refs": [{"path": str(paths.collect_latest)}]},
        {"from": "abyss-machine:self-awareness", "to": "warm-e2b-gemma4.spark", "kind": "resident_reasoning_context", "evidence_refs": [{"path": str(paths.ai_llm_resident_status_latest)}]},
        {"from": "warm-e2b-gemma4.spark", "to": "rag", "kind": "bounded_retrieval_context", "evidence_refs": [{"path": str(paths.rag_validate_latest)}]},
        {"from": "warm-e2b-gemma4.spark", "to": "nervous", "kind": "freshness_gate", "evidence_refs": [{"path": str(paths.nervous_brief_latest)}]},
        {"from": "warm-e2b-gemma4.spark", "to": "resource", "kind": "resource_gate", "evidence_refs": [{"path": str(paths.resource_latest)}]},
        {"from": "warm-e2b-gemma4.spark", "to": "mode", "kind": "mode_gate", "evidence_refs": [{"path": str(paths.mode_latest)}]},
        {"from": "rag-api", "to": "postgres", "kind": "stack_memory_backend_candidate", "evidence_refs": [{"path": str(paths.process_container_latest)}]},
        {"from": "rag-api", "to": "neo4j", "kind": "stack_spatial_graph_backend_candidate", "evidence_refs": [{"path": str(paths.process_container_latest)}]},
    ]
    joins = []
    for key, event_ids in (nested_get(index, ["indexes", "by_context"]) or {}).items():
        if len(event_ids) < 2:
            continue
        joins.append(
            {
                "join_key": key,
                "event_ids": event_ids[:20],
                "join_kind": "context",
                "evidence_refs": [{"path": str(paths.events_latest)}],
            }
        )
    for service, event_ids in (nested_get(index, ["indexes", "by_service"]) or {}).items():
        if len(event_ids) < 2:
            continue
        joins.append(
            {
                "join_key": "service:" + service,
                "event_ids": event_ids[:20],
                "join_kind": "service",
                "evidence_refs": [{"path": str(paths.events_latest)}],
            }
        )
    episodes = (
        episodes
        if isinstance(episodes, dict)
        else runtime_port.load_latest_json(
            paths.episodes_latest,
            f"{schema_prefix}_self_awareness_episodes_v1",
        )
    )
    provenance = []
    for episode in (
        episodes.get("episodes") if isinstance(episodes.get("episodes"), list) else []
    )[:12]:
        if not isinstance(episode, dict):
            continue
        provenance.append(
            {
                "episode_id": episode.get("episode_id"),
                "symptom": ", ".join(episode.get("primary_signals") or []),
                "evidence": episode.get("evidence_refs", [])[:8],
                "hypothesis": episode.get("suspected_cause_chain", [])[:4],
                "conclusion": "candidate causal episode; no root-cause fact claim",
                "confidence": episode.get("confidence"),
            }
        )
    data = {
        "schema": f"{schema_prefix}_self_awareness_correlation_v1",
        "version": config.version,
        "generated_at": generated_at,
        "ok": bool(events),
        "summary": {
            "events": len(events),
            "joins": len(joins),
            "dependencies": len(dependencies),
            "slo_views": len(slo_views),
            "anomaly_baselines": len(anomaly_baselines),
            "provenance_chains": len(provenance),
        },
        "joins": joins[:80],
        "service_dependencies": dependencies,
        "slo_views": slo_views,
        "anomaly_baselines": anomaly_baselines,
        "provenance_chains": provenance,
        "capability_requirements": capabilities.get("requirements", []),
        "policy": {
            "no_high_cardinality_loki_labels": True,
            "correlation_not_root_cause_fact": True,
            "bounded_windows": True,
        },
    }
    if write_latest:
        errors = persistence_port.write_latest_and_history(
            data,
            paths.correlation_latest,
            paths.correlation_root,
        )
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data

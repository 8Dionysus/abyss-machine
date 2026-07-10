from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import self_awareness_contracts


DocumentPort = Callable[..., Any]


@dataclass(frozen=True)
class SelfAwarenessBodyTracePaths:
    episodes_latest: Path
    context_latest: Path
    timeline_latest: Path
    spatial_graph_latest: Path
    events_latest: Path


@dataclass(frozen=True)
class SelfAwarenessBodyTraceConfig:
    schema_prefix: str


@dataclass(frozen=True)
class SelfAwarenessBodyTraceRuntimePort:
    load_latest_json: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessBodyTraceContractPort:
    time_bucket: DocumentPort


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def body_trace_complete(trace: Any, *, schema_prefix: str) -> bool:
    nested_get = self_awareness_contracts.nested_get
    if not isinstance(trace, dict):
        return False
    return (
        trace.get("schema") == f"{schema_prefix}_self_awareness_body_trace_v1"
        and bool(trace.get("trace_id"))
        and bool(trace.get("episode_id"))
        and bool(nested_get(trace, ["temporal", "start"]))
        and bool(nested_get(trace, ["temporal", "end"]))
        and (
            _safe_int(nested_get(trace, ["spatial", "node_count"]), 0) > 0
            or _safe_int(nested_get(trace, ["spatial", "service_count"]), 0) > 0
        )
        and _safe_int(nested_get(trace, ["contextual", "context_key_count"]), 0) > 0
        and nested_get(trace, ["host_body", "complete"]) is True
        and nested_get(trace, ["policy", "host_layer_mutates_stack"]) is False
        and nested_get(trace, ["policy", "executes_commands"]) is False
        and nested_get(trace, ["policy", "stores_raw_body"]) is False
        and nested_get(trace, ["policy", "stores_raw_context_values"]) is False
        and bool(trace.get("evidence_refs"))
    )


def episode_body_trace(
    *,
    episode: dict[str, Any],
    source_event: dict[str, Any] | None = None,
    context_doc: dict[str, Any] | None = None,
    paths: SelfAwarenessBodyTracePaths,
    config: SelfAwarenessBodyTraceConfig,
    runtime_port: SelfAwarenessBodyTraceRuntimePort,
    contract_port: SelfAwarenessBodyTraceContractPort,
) -> dict[str, Any]:
    nested_get = self_awareness_contracts.nested_get
    stable_hash_json = self_awareness_contracts.stable_hash_json
    episode = episode if isinstance(episode, dict) else {}
    source_event = source_event if isinstance(source_event, dict) else {}
    context_doc = (
        context_doc
        if isinstance(context_doc, dict)
        else runtime_port.load_latest_json(
            paths.context_latest,
            f"{config.schema_prefix}_self_awareness_context_v1",
        )
    )
    context_packet = (
        context_doc.get("context_packet")
        if isinstance(context_doc.get("context_packet"), dict)
        else {}
    )
    host_body = nested_get(context_packet, ["sections", "host_body"])
    host_body = host_body if isinstance(host_body, dict) else {}
    time_window = (
        episode.get("time_window") if isinstance(episode.get("time_window"), dict) else {}
    )
    source_context = (
        source_event.get("context")
        if isinstance(source_event.get("context"), dict)
        else {}
    )
    source_resource = (
        source_event.get("resource")
        if isinstance(source_event.get("resource"), dict)
        else {}
    )
    involved_contexts = [
        item
        for item in (
            episode.get("involved_contexts")
            if isinstance(episode.get("involved_contexts"), list)
            else []
        )
        if isinstance(item, dict)
    ]
    context_keys = [
        str(item)
        for item in (
            episode.get("context_keys")
            if isinstance(episode.get("context_keys"), list)
            else []
        )
        if item
    ]
    for context in [*involved_contexts, source_context]:
        for key, value in context.items():
            if value in (None, ""):
                continue
            rendered = f"{key}:{value}"
            if rendered not in context_keys:
                context_keys.append(rendered)
    affected_nodes = [
        str(item)
        for item in (
            episode.get("affected_spatial_nodes")
            if isinstance(episode.get("affected_spatial_nodes"), list)
            else []
        )
        if item
    ]
    affected_services = [
        str(item)
        for item in (
            episode.get("affected_services")
            if isinstance(episode.get("affected_services"), list)
            else []
        )
        if item
    ]
    for node in affected_nodes:
        if node.startswith("service:"):
            service = node.split(":", 1)[1]
            if service and service not in affected_services:
                affected_services.append(service)
    for candidate in (
        source_resource.get("service"),
        nested_get(episode, ["working_stack_gap", "service"]),
        episode.get("service"),
    ):
        if candidate and str(candidate) not in affected_services:
            affected_services.append(str(candidate))
    if source_resource.get("service") and not any(
        node == f"service:{source_resource.get('service')}" for node in affected_nodes
    ):
        affected_nodes.append(f"service:{source_resource.get('service')}")
    evidence_refs = [
        {"path": str(paths.episodes_latest), "episode_id": episode.get("episode_id")},
        {"path": str(paths.context_latest), "section": "context_packet.host_body"},
        {"path": str(paths.timeline_latest), "episode_id": episode.get("episode_id")},
        {"path": str(paths.spatial_graph_latest), "nodes": affected_nodes[:12]},
    ]
    if source_event.get("event_id"):
        evidence_refs.append(
            {"path": str(paths.events_latest), "event_id": source_event.get("event_id")}
        )
    evidence_refs.extend(
        episode.get("evidence_refs") if isinstance(episode.get("evidence_refs"), list) else []
    )
    evidence_refs.extend(
        source_event.get("evidence_refs")
        if isinstance(source_event.get("evidence_refs"), list)
        else []
    )
    start = time_window.get("start") or source_event.get("event_time") or context_doc.get(
        "generated_at"
    )
    end = time_window.get("end") or source_event.get("event_time") or start
    body_trace = {
        "schema": f"{config.schema_prefix}_self_awareness_body_trace_v1",
        "trace_id": "sabody-"
        + stable_hash_json(
            {
                "episode": episode.get("episode_id"),
                "event": source_event.get("event_id"),
                "time": time_window,
                "nodes": affected_nodes,
                "contexts": context_keys,
            },
            length=20,
        ),
        "episode_id": episode.get("episode_id"),
        "episode_kind": episode.get("episode_kind") or "event_correlation",
        "temporal": {
            "start": start,
            "end": end,
            "bucket": time_window.get("bucket") or contract_port.time_bucket(start),
            "source_event_time": source_event.get("event_time"),
            "context_generated_at": context_doc.get("generated_at"),
        },
        "spatial": {
            "affected_spatial_nodes": affected_nodes[:40],
            "affected_services": affected_services[:40],
            "node_count": len(affected_nodes),
            "service_count": len(affected_services),
            "owner_surfaces": sorted(
                set(
                    str(item)
                    for item in [
                        episode.get("owner_route"),
                        nested_get(source_event, ["space", "owner_surface"]),
                        source_resource.get("owner_surface"),
                    ]
                    if item
                )
            ),
        },
        "contextual": {
            "context_keys": context_keys[:60],
            "context_key_count": len(context_keys),
            "involved_context_count": len(involved_contexts),
            "event_ids": [
                str(item)
                for item in (
                    episode.get("event_ids")
                    if isinstance(episode.get("event_ids"), list)
                    else []
                )
                if item
            ][:40],
            "source_event_id": source_event.get("event_id"),
            "host_service_units": nested_get(episode, ["host_service", "units"])
            if isinstance(nested_get(episode, ["host_service", "units"]), list)
            else [],
            "host_service_categories": nested_get(episode, ["host_service", "categories"])
            if isinstance(nested_get(episode, ["host_service", "categories"]), list)
            else [],
            "scheduler_units": [
                item.split(":", 1)[1]
                for item in context_keys
                if item.startswith("scheduler_unit:")
            ][:40],
            "scheduler_categories": [
                item.split(":", 1)[1]
                for item in context_keys
                if item.startswith("scheduler_category:")
            ][:40],
        },
        "host_body": {
            "schema": host_body.get("schema"),
            "complete": host_body.get("complete"),
            "scheduler_unit_contexts": nested_get(host_body, ["scheduler", "unit_contexts"]),
            "scheduler_categories": nested_get(host_body, ["scheduler", "categories"])
            if isinstance(nested_get(host_body, ["scheduler", "categories"]), list)
            else [],
            "host_service_unit_contexts": nested_get(
                host_body, ["host_services", "unit_contexts"]
            ),
            "host_service_categories": nested_get(host_body, ["host_services", "categories"])
            if isinstance(nested_get(host_body, ["host_services", "categories"]), list)
            else [],
            "manual_collect_contexts": nested_get(host_body, ["manual_collect", "contexts"]),
        },
        "lineage": {
            "episode_latest": str(paths.episodes_latest),
            "context_latest": str(paths.context_latest),
            "timeline_latest": str(paths.timeline_latest),
            "spatial_graph_latest": str(paths.spatial_graph_latest),
            "source_event_latest": str(paths.events_latest)
            if source_event.get("event_id")
            else None,
        },
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "automatic_remediation": False,
            "stores_raw_body": False,
            "stores_raw_context_values": False,
            "raw_private_content": False,
        },
        "evidence_refs": evidence_refs[:60],
    }
    body_trace["complete"] = body_trace_complete(
        body_trace,
        schema_prefix=config.schema_prefix,
    )
    return body_trace

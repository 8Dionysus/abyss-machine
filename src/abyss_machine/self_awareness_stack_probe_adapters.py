from __future__ import annotations

import datetime as dt
import json
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import self_awareness_contracts


DocumentPort = Callable[..., Any]


@dataclass(frozen=True)
class SelfAwarenessStackProbeConfig:
    schema_prefix: str
    version: str
    route_api_url: str
    rag_api_url: str
    langchain_api_url: str
    neo4j_url: str
    postgres_host: str
    postgres_port: int
    tempo_url: str
    alertmanager_url: str
    grafana_url: str
    loki_url: str
    prometheus_url: str
    stack_observability_latest: Path
    closure_evidence_config: Path


@dataclass(frozen=True)
class SelfAwarenessStackProbeRuntimePort:
    http_json: DocumentPort
    socket_create_connection: DocumentPort
    monotonic: DocumentPort
    time_now: DocumentPort
    path_exists: DocumentPort
    path_stat: DocumentPort
    load_json_document: DocumentPort
    now_iso: DocumentPort
    daily_jsonl_path: DocumentPort
    secret_search: DocumentPort


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def capability_matrix(
    capability_id: str,
    owner: str,
    evidence_refs: list[dict[str, Any]],
    detail: dict[str, Any],
    *,
    endpoints: list[dict[str, Any]] | None = None,
    generated_at: str | None = None,
    config: SelfAwarenessStackProbeConfig,
    runtime_port: SelfAwarenessStackProbeRuntimePort,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    safe_int = _safe_int
    endpoint_rows: list[dict[str, Any]] = []
    latest_artifacts: list[dict[str, Any]] = []
    schema_rows: list[dict[str, Any]] = []
    history_rows: list[dict[str, Any]] = []
    seen_endpoints: set[str] = set()
    seen_paths: set[str] = set()
    now_ts = runtime_port.time_now()

    def add_endpoint(ref: dict[str, Any], *, source: str) -> None:
        url = str(ref.get("url") or "").strip()
        if not url or url in seen_endpoints:
            return
        seen_endpoints.add(url)
        row = {
            "url": url,
            "status_code": ref.get("status_code"),
            "ok": ref.get("ok") if ref.get("ok") is not None else (safe_int(ref.get("status_code"), 0) in range(200, 300)),
            "source": source,
            "read_only": True,
            "auth_safe": True,
            "body_stored": False,
            "bounded": True,
        }
        if ref.get("error"):
            row["error"] = ref.get("error")
        endpoint_rows.append(row)

    def add_path(ref: dict[str, Any]) -> None:
        path_text = str(ref.get("path") or "").strip()
        if not path_text or path_text in seen_paths:
            return
        seen_paths.add(path_text)
        path = Path(path_text)
        exists = runtime_port.path_exists(path)
        artifact: dict[str, Any] = {
            "path": path_text,
            "schema": ref.get("schema"),
            "exists": exists,
            "read_only": True,
            "body_stored_in_matrix": False,
        }
        if exists:
            try:
                stat = runtime_port.path_stat(path)
                artifact["size_bytes"] = stat.st_size
                artifact["mtime"] = dt.datetime.fromtimestamp(stat.st_mtime, dt.timezone.utc).astimezone().isoformat(timespec="seconds")
                artifact["age_seconds"] = round(max(0.0, now_ts - stat.st_mtime), 3)
            except OSError as exc:
                artifact["stat_error"] = str(exc)
        latest_artifacts.append(artifact)
        if ref.get("schema"):
            schema_rows.append({"schema": ref.get("schema"), "path": path_text, "exists": exists})
        history_root = path.parent
        history_rows.append({
            "latest": path_text,
            "daily_glob": str(history_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "today": str(runtime_port.daily_jsonl_path(history_root)),
            "today_exists": runtime_port.path_exists(runtime_port.daily_jsonl_path(history_root)),
            "latest_exists": exists,
        })

    for ref in evidence_refs:
        if not isinstance(ref, dict):
            continue
        add_endpoint(ref, source="evidence_ref")
        add_path(ref)
    for endpoint in endpoints or []:
        if isinstance(endpoint, dict):
            add_endpoint(endpoint, source="capability_endpoint")

    latest_ages = [
        float(item.get("age_seconds"))
        for item in latest_artifacts
        if isinstance(item.get("age_seconds"), (int, float))
    ]
    freshness = {
        "observed_at": generated_at or runtime_port.now_iso(),
        "generated_at": generated_at,
        "latest_artifacts": len(latest_artifacts),
        "endpoints": len(endpoint_rows),
        "schemas": len(schema_rows),
        "max_latest_age_seconds": round(max(latest_ages), 3) if latest_ages else None,
        "missing_latest_artifacts": [item["path"] for item in latest_artifacts if not item.get("exists")],
        "freshness_must_precede_reasoning": True,
        "raw_evidence_is_not_truth": True,
    }
    access = {
        "read_only": True,
        "host_layer_mutates_stack": False,
        "mutates_project_roots": False,
        "auth_safe": True,
        "stores_raw_private_payload": False,
        "bounded": True,
        "source_policy": "capability matrix records endpoints and artifact metadata only; it does not fetch new payloads beyond the owning capability probe",
    }
    owner_boundary = {
        "owner": owner,
        "stack_owned": owner == "abyss-stack",
        "machine_owned": owner == "abyss-machine",
        "host_layer_mutates_stack": False,
        "writes_project_roots": False,
        "capability_presence_is_stack_promotion": False,
    }
    return {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_capability_matrix_row_v1",
        "capability_id": capability_id,
        "owner": owner,
        "endpoints": endpoint_rows,
        "schemas": schema_rows,
        "latest_artifacts": latest_artifacts,
        "freshness": freshness,
        "history": {
            "latest_artifacts": history_rows,
            "history_available": any(item.get("today_exists") for item in history_rows),
            "history_route": "latest_plus_daily_jsonl_when_writer_supports_history",
        },
        "access": access,
        "owner_boundary": owner_boundary,
        "evidence_route": {
            "has_endpoint_or_artifact": bool(endpoint_rows or latest_artifacts or schema_rows),
            "endpoint_count": len(endpoint_rows),
            "latest_artifact_count": len(latest_artifacts),
            "schema_count": len(schema_rows),
        },
        "detail_keys": sorted(detail.keys()) if isinstance(detail, dict) else [],
    }


def openapi_summary(openapi_doc: dict[str, Any]) -> dict[str, Any]:
    paths = openapi_doc.get("paths") if isinstance(openapi_doc.get("paths"), dict) else {}
    path_rows: list[dict[str, Any]] = []
    for path, methods in sorted(paths.items()):
        method_map = methods if isinstance(methods, dict) else {}
        public_methods = sorted(
            str(method).upper()
            for method in method_map
            if str(method).lower() in {"get", "post", "put", "patch", "delete"}
        )
        path_rows.append({"path": str(path), "methods": public_methods})
    schemas = self_awareness_contracts.nested_get(openapi_doc, ["components", "schemas"])
    schema_names = sorted(str(name) for name in schemas) if isinstance(schemas, dict) else []
    path_names = [str(row.get("path") or "") for row in path_rows]
    return {
        "path_count": len(path_rows),
        "paths": path_rows[:128],
        "schema_names": schema_names[:128],
        "inventory_paths": [path for path in path_names if re.search(r"inventory|schema|source|collection|graph|label|relationship|catalog|registry", path, re.IGNORECASE)][:64],
        "checkpoint_paths": [path for path in path_names if re.search(r"checkpoint|thread", path, re.IGNORECASE)][:32],
        "trace_paths": [path for path in path_names if re.search(r"trace|span", path, re.IGNORECASE)][:32],
    }


def bounded_names_from_json(payload: Any, keys: set[str], limit: int = 32) -> list[str]:
    found: list[str] = []

    def walk(value: Any) -> None:
        if len(found) >= limit:
            return
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key) in keys and isinstance(item, (str, int, float, bool)):
                    found.append(str(item))
                    if len(found) >= limit:
                        return
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
                if len(found) >= limit:
                    return

    walk(payload)
    return sorted(dict.fromkeys(found))[:limit]


def stack_memory_space_probe(
    *,
    config: SelfAwarenessStackProbeConfig,
    runtime_port: SelfAwarenessStackProbeRuntimePort,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    nested_get = self_awareness_contracts.nested_get
    route_base = config.route_api_url.rstrip("/")
    rag_base = config.rag_api_url.rstrip("/")
    neo4j_base = config.neo4j_url.rstrip("/")

    route_health = runtime_port.http_json(f"{route_base}/health", timeout=1.5, max_bytes=131072)
    route_openapi = runtime_port.http_json(f"{route_base}/openapi.json", timeout=1.5, max_bytes=262144)
    rag_health = runtime_port.http_json(f"{rag_base}/health", timeout=1.5, max_bytes=196608)
    rag_openapi = runtime_port.http_json(f"{rag_base}/openapi.json", timeout=1.5, max_bytes=196608)
    rag_collections = runtime_port.http_json(f"{rag_base}/collections", timeout=1.5, max_bytes=131072)
    rag_sources = runtime_port.http_json(f"{rag_base}/sources", timeout=1.5, max_bytes=131072)
    rag_graph = runtime_port.http_json(f"{rag_base}/agentic-rag/graph", timeout=1.5, max_bytes=131072)
    rag_semantic_inventory = runtime_port.http_json(f"{rag_base}/semantic-inventory", timeout=3.0, max_bytes=262144)
    neo4j_root = runtime_port.http_json(f"{neo4j_base}/", timeout=1.5, max_bytes=65536)

    postgres_ready = False
    postgres_error = None
    started = runtime_port.monotonic()
    try:
        with runtime_port.socket_create_connection((config.postgres_host, config.postgres_port), timeout=1.2):
            postgres_ready = True
    except OSError as exc:
        postgres_error = str(exc)
    postgres_elapsed_ms = round((runtime_port.monotonic() - started) * 1000.0, 1)

    route_openapi_json = route_openapi.get("json") if isinstance(route_openapi.get("json"), dict) else {}
    rag_openapi_json = rag_openapi.get("json") if isinstance(rag_openapi.get("json"), dict) else {}
    route_paths = openapi_summary(route_openapi_json)
    rag_paths = openapi_summary(rag_openapi_json)
    route_health_json = route_health.get("json") if isinstance(route_health.get("json"), dict) else {}
    rag_health_json = rag_health.get("json") if isinstance(rag_health.get("json"), dict) else {}
    collections_json = rag_collections.get("json") if isinstance(rag_collections.get("json"), dict) else {}
    sources_json = rag_sources.get("json") if isinstance(rag_sources.get("json"), dict) else {}
    graph_json = rag_graph.get("json") if isinstance(rag_graph.get("json"), dict) else {}
    graph_data = graph_json.get("data") if isinstance(graph_json.get("data"), dict) else graph_json
    semantic_json = rag_semantic_inventory.get("json") if isinstance(rag_semantic_inventory.get("json"), dict) else {}
    semantic_route_postgres = semantic_json.get("postgres") if isinstance(semantic_json.get("postgres"), dict) else {}
    semantic_route_neo4j = semantic_json.get("neo4j") if isinstance(semantic_json.get("neo4j"), dict) else {}
    semantic_route_summary = semantic_json.get("semantic_inventory") if isinstance(semantic_json.get("semantic_inventory"), dict) else {}
    semantic_route_redaction = semantic_json.get("redaction") if isinstance(semantic_json.get("redaction"), dict) else {}
    neo4j_json = neo4j_root.get("json") if isinstance(neo4j_root.get("json"), dict) else {}

    collection_names = bounded_names_from_json(collections_json, {"name", "collection", "collection_name"}, limit=32)
    source_names = bounded_names_from_json(sources_json, {"name", "id", "source"}, limit=32)
    graph_nodes = graph_data.get("nodes") if isinstance(graph_data.get("nodes"), list) else []
    graph_edges = graph_data.get("edges") if isinstance(graph_data.get("edges"), list) else []
    graph_keys = sorted(str(key) for key in graph_data.keys()) if isinstance(graph_data, dict) else []

    semantic_route_safe = bool(
        rag_semantic_inventory.get("ok")
        and semantic_route_redaction.get("raw_database_rows_stored") is False
        and semantic_route_redaction.get("raw_graph_properties_stored") is False
        and semantic_route_redaction.get("raw_source_documents_stored") is False
        and semantic_route_redaction.get("raw_credentials_stored") is False
    )
    stack_owned_schema_inventory_present = bool(
        semantic_route_safe
        and (
            semantic_route_postgres.get("schema_inventory_present")
            or semantic_route_summary.get("stack_owned_postgres_schema_inventory_present")
        )
    )
    stack_owned_graph_inventory_present = bool(
        semantic_route_safe
        and (
            semantic_route_neo4j.get("graph_inventory_present")
            or semantic_route_summary.get("stack_owned_neo4j_graph_inventory_present")
        )
    )
    inventory_complete = stack_owned_schema_inventory_present and stack_owned_graph_inventory_present
    evidence_refs = [
        {"url": route_health.get("url"), "status_code": route_health.get("status_code"), "probe": "route_api_health"},
        {"url": route_openapi.get("url"), "status_code": route_openapi.get("status_code"), "probe": "route_api_openapi"},
        {"url": rag_health.get("url"), "status_code": rag_health.get("status_code"), "probe": "rag_api_health"},
        {"url": rag_openapi.get("url"), "status_code": rag_openapi.get("status_code"), "probe": "rag_api_openapi"},
        {"url": rag_collections.get("url"), "status_code": rag_collections.get("status_code"), "probe": "rag_collections"},
        {"url": rag_sources.get("url"), "status_code": rag_sources.get("status_code"), "probe": "rag_sources"},
        {"url": rag_graph.get("url"), "status_code": rag_graph.get("status_code"), "probe": "rag_agentic_graph"},
        {"url": rag_semantic_inventory.get("url"), "status_code": rag_semantic_inventory.get("status_code"), "probe": "rag_semantic_inventory"},
        {"url": f"tcp://{config.postgres_host}:{config.postgres_port}", "ok": postgres_ready, "probe": "postgres_tcp_ready"},
        {"url": neo4j_root.get("url"), "status_code": neo4j_root.get("status_code"), "probe": "neo4j_root"},
    ]
    return {
        "schema": f"{SCHEMA_PREFIX}_stack_memory_space_probe_v1",
        "ok": bool(route_health.get("ok") and route_openapi.get("ok") and rag_health.get("ok") and rag_openapi.get("ok") and postgres_ready and neo4j_root.get("ok")),
        "route_api": {
            "base_url": route_base,
            "health": {
                "url": route_health.get("url"),
                "ok": route_health.get("ok"),
                "status_code": route_health.get("status_code"),
                "layers": route_health_json.get("layers") if isinstance(route_health_json.get("layers"), list) else [],
                "mirror_ready": route_health_json.get("mirror_ready"),
                "thin_routing_only": route_health_json.get("thin_routing_only"),
                "advisory_only": route_health_json.get("advisory_only"),
                "closure_ready": nested_get(route_health_json, ["closure_summary", "closure_ready"]),
                "error": route_health.get("error"),
            },
            "openapi": {
                "url": route_openapi.get("url"),
                "ok": route_openapi.get("ok"),
                "status_code": route_openapi.get("status_code"),
                "path_count": route_paths.get("path_count"),
                "paths": route_paths.get("paths"),
                "inventory_paths": route_paths.get("inventory_paths"),
                "schema_names": route_paths.get("schema_names"),
                "error": route_openapi.get("error"),
                "truncated": route_openapi.get("truncated"),
            },
        },
        "rag_api": {
            "base_url": rag_base,
            "health": {
                "url": rag_health.get("url"),
                "ok": rag_health.get("ok"),
                "status_code": rag_health.get("status_code"),
                "service": rag_health_json.get("service"),
                "collection": rag_health_json.get("collection"),
                "vector_size": rag_health_json.get("vector_size"),
                "qdrant_status": nested_get(rag_health_json, ["checks", "qdrant", "status"]),
                "langchain_ok": nested_get(rag_health_json, ["langchain", "ok"]),
                "route_api_ok": nested_get(rag_health_json, ["route_api", "ok"]),
                "rerank_api_ok": nested_get(rag_health_json, ["rerank_api", "ok"]),
                "error": rag_health.get("error"),
            },
            "openapi": {
                "url": rag_openapi.get("url"),
                "ok": rag_openapi.get("ok"),
                "status_code": rag_openapi.get("status_code"),
                "path_count": rag_paths.get("path_count"),
                "paths": rag_paths.get("paths"),
                "inventory_paths": rag_paths.get("inventory_paths"),
                "schema_names": rag_paths.get("schema_names"),
                "error": rag_openapi.get("error"),
                "truncated": rag_openapi.get("truncated"),
            },
            "collections": {
                "url": rag_collections.get("url"),
                "ok": rag_collections.get("ok"),
                "status_code": rag_collections.get("status_code"),
                "collection_names": collection_names,
                "collection_count": len(collection_names),
                "error": rag_collections.get("error"),
            },
            "sources": {
                "url": rag_sources.get("url"),
                "ok": rag_sources.get("ok"),
                "status_code": rag_sources.get("status_code"),
                "source_names": source_names,
                "source_count": len(source_names),
                "error": rag_sources.get("error"),
            },
            "agentic_graph": {
                "url": rag_graph.get("url"),
                "ok": rag_graph.get("ok"),
                "status_code": rag_graph.get("status_code"),
                "node_count": len(graph_nodes),
                "edge_count": len(graph_edges),
                "keys": graph_keys[:64],
                "error": rag_graph.get("error"),
            },
            "semantic_inventory": {
                "url": rag_semantic_inventory.get("url"),
                "ok": rag_semantic_inventory.get("ok"),
                "status_code": rag_semantic_inventory.get("status_code"),
                "schema": semantic_json.get("schema"),
                "inventory_complete": semantic_route_summary.get("inventory_complete"),
                "safe": semantic_route_safe,
                "error": rag_semantic_inventory.get("error"),
            },
        },
        "postgres": {
            "host": config.postgres_host,
            "port": config.postgres_port,
            "tcp_ready": postgres_ready,
            "elapsed_ms": postgres_elapsed_ms,
            "error": postgres_error,
            "schema_inventory_present": stack_owned_schema_inventory_present,
            "schemas": semantic_route_postgres.get("schemas") if isinstance(semantic_route_postgres.get("schemas"), list) else [],
            "relation_count": semantic_route_postgres.get("relation_count"),
            "freshness": semantic_route_postgres.get("freshness") if isinstance(semantic_route_postgres.get("freshness"), dict) else {},
            "inventory_error": semantic_route_postgres.get("error"),
        },
        "neo4j": {
            "base_url": neo4j_base,
            "root": {
                "url": neo4j_root.get("url"),
                "ok": neo4j_root.get("ok"),
                "status_code": neo4j_root.get("status_code"),
                "neo4j_version": neo4j_json.get("neo4j_version"),
                "neo4j_edition": neo4j_json.get("neo4j_edition"),
                "query_endpoint_present": bool(neo4j_json.get("query")),
                "bolt_routing_present": bool(neo4j_json.get("bolt_routing")),
                "error": neo4j_root.get("error"),
            },
            "graph_inventory_present": stack_owned_graph_inventory_present,
            "labels": semantic_route_neo4j.get("labels") if isinstance(semantic_route_neo4j.get("labels"), list) else [],
            "relationship_types": semantic_route_neo4j.get("relationship_types") if isinstance(semantic_route_neo4j.get("relationship_types"), list) else [],
            "node_count": semantic_route_neo4j.get("node_count"),
            "relationship_count": semantic_route_neo4j.get("relationship_count"),
            "freshness": semantic_route_neo4j.get("freshness") if isinstance(semantic_route_neo4j.get("freshness"), dict) else {},
            "inventory_error": semantic_route_neo4j.get("error"),
        },
        "semantic_inventory": {
            "route_api_readable": bool(route_health.get("ok") and route_openapi.get("ok")),
            "rag_api_readable": bool(rag_health.get("ok") and rag_openapi.get("ok") and rag_collections.get("ok") and rag_sources.get("ok")),
            "rag_graph_route_readable": bool(rag_graph.get("ok")),
            "rag_semantic_inventory_readable": bool(rag_semantic_inventory.get("ok")),
            "rag_semantic_inventory_safe": semantic_route_safe,
            "postgres_reachable_without_credentials": postgres_ready,
            "neo4j_root_readable_without_credentials": bool(neo4j_root.get("ok")),
            "stack_owned_postgres_schema_inventory_present": stack_owned_schema_inventory_present,
            "stack_owned_neo4j_graph_inventory_present": stack_owned_graph_inventory_present,
            "inventory_complete": inventory_complete,
        },
        "redaction": {
            "stores_route_and_inventory_summary_only": True,
            "raw_database_rows_stored": False,
            "raw_graph_properties_stored": False,
            "raw_source_documents_stored": False,
            "raw_credentials_stored": False,
        },
        "evidence_refs": evidence_refs,
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "raw_private_content": False,
            "database_credentials_used": False,
        },
    }


def langchain_api_probe(
    *,
    config: SelfAwarenessStackProbeConfig,
    runtime_port: SelfAwarenessStackProbeRuntimePort,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    base_url = config.langchain_api_url.rstrip("/")
    health = runtime_port.http_json(f"{base_url}/health", timeout=1.5, max_bytes=65536)
    openapi = runtime_port.http_json(f"{base_url}/openapi.json", timeout=1.5, max_bytes=131072)
    openapi_json = openapi.get("json") if isinstance(openapi.get("json"), dict) else {}
    openapi_document_summary = openapi_summary(openapi_json)
    path_rows = openapi_document_summary.get("paths") if isinstance(openapi_document_summary.get("paths"), list) else []
    schema_names = openapi_document_summary.get("schema_names") if isinstance(openapi_document_summary.get("schema_names"), list) else []
    checkpoint_paths = openapi_document_summary.get("checkpoint_paths") if isinstance(openapi_document_summary.get("checkpoint_paths"), list) else []
    trace_paths = openapi_document_summary.get("trace_paths") if isinstance(openapi_document_summary.get("trace_paths"), list) else []
    health_json = health.get("json") if isinstance(health.get("json"), dict) else {}

    def route_matches(pattern: str) -> list[dict[str, Any]]:
        return [
            row for row in path_rows
            if isinstance(row, dict) and re.search(pattern, str(row.get("path") or ""), re.IGNORECASE)
        ]

    run_paths = [
        row for row in path_rows
        if isinstance(row, dict) and str(row.get("path") or "").rstrip("/") == "/run"
    ]
    federated_run_paths = [
        row for row in path_rows
        if isinstance(row, dict) and str(row.get("path") or "").rstrip("/") == "/run/federated"
    ]
    embeddings_paths = route_matches(r"embed")
    thread_paths = route_matches(r"thread")
    runtime_request_schema_names = [
        name for name in schema_names
        if re.search(r"RunReq|FederatedRunReq|EmbeddingsReq|Thread|Checkpoint|Trace", str(name), re.IGNORECASE)
    ][:32]
    missing_replay_inventory = [
        label for label, present in [
            ("threads", bool(thread_paths)),
            ("checkpoints", bool(checkpoint_paths)),
            ("traces", bool(trace_paths)),
        ]
        if not present
    ]
    runtime_surface = {
        "service": health_json.get("service"),
        "embeddings_provider": health_json.get("embeddings_provider"),
        "ovms_auth_enabled": health_json.get("ovms_auth_enabled"),
        "federated_run_enabled": health_json.get("federated_run_enabled"),
        "run_route_present": bool(run_paths),
        "federated_run_route_present": bool(federated_run_paths),
        "embeddings_route_present": bool(embeddings_paths),
        "runtime_request_schema_names": runtime_request_schema_names,
        "runnable_route_count": len(run_paths) + len(federated_run_paths),
        "usable_runtime_surface": bool(run_paths and embeddings_paths),
    }
    route_classes = {
        "run_paths": run_paths[:16],
        "federated_run_paths": federated_run_paths[:16],
        "embeddings_paths": embeddings_paths[:16],
        "thread_paths": thread_paths[:16],
        "checkpoint_paths": checkpoint_paths[:32],
        "trace_paths": trace_paths[:32],
    }
    replay_inventory = {
        "thread_inventory_present": bool(thread_paths),
        "checkpoint_inventory_present": bool(checkpoint_paths),
        "trace_inventory_present": bool(trace_paths),
        "inventory_complete": not missing_replay_inventory,
        "missing_inventory": missing_replay_inventory,
    }
    return {
        "schema": f"{SCHEMA_PREFIX}_stack_langchain_api_probe_v1",
        "base_url": base_url,
        "ok": bool(health.get("ok") and openapi.get("ok")),
        "health": {
            "url": health.get("url"),
            "ok": health.get("ok"),
            "status_code": health.get("status_code"),
            "service": health_json.get("service"),
            "embeddings_provider": health_json.get("embeddings_provider"),
            "ovms_auth_enabled": health_json.get("ovms_auth_enabled"),
            "federated_run_enabled": health_json.get("federated_run_enabled"),
            "error": health.get("error"),
        },
        "openapi": {
            "url": openapi.get("url"),
            "ok": openapi.get("ok"),
            "status_code": openapi.get("status_code"),
            "path_count": len(path_rows),
            "paths": path_rows[:64],
            "schema_names": schema_names[:64],
            "runtime_request_schema_names": runtime_request_schema_names,
            "thread_paths": thread_paths[:32],
            "checkpoint_paths": checkpoint_paths[:32],
            "trace_paths": trace_paths[:32],
            "error": openapi.get("error"),
            "truncated": openapi.get("truncated"),
        },
        "runtime_surface": runtime_surface,
        "route_classes": route_classes,
        "replay_inventory": replay_inventory,
        "trace_backend_coupling": {
            "required_for_trace_join": True,
            "candidate_ready_url": f"{config.tempo_url.rstrip()}/ready",
            "machine_checks_trace_backend_separately": True,
            "stack_owned_trace_backend_requirement": "stack.trace-backend",
        },
        "observability": {
            "health_readable": bool(health.get("ok")),
            "openapi_readable": bool(openapi.get("ok")),
            "runtime_surface_usable": runtime_surface["usable_runtime_surface"],
            "thread_inventory_present": replay_inventory["thread_inventory_present"],
            "checkpoint_inventory_present": replay_inventory["checkpoint_inventory_present"],
            "trace_inventory_present": replay_inventory["trace_inventory_present"],
            "missing_replay_inventory": missing_replay_inventory,
            "graph_observability_complete": bool(health.get("ok") and openapi.get("ok") and replay_inventory["inventory_complete"]),
        },
        "redaction": {
            "stores_openapi_summary_only": True,
            "stores_runtime_route_shape_only": True,
            "raw_prompt_payloads_stored": False,
            "raw_message_payloads_stored": False,
            "raw_tool_payloads_stored": False,
            "raw_trace_payloads_stored": False,
        },
        "evidence_refs": [
            {"url": health.get("url"), "status_code": health.get("status_code")},
            {"url": openapi.get("url"), "status_code": openapi.get("status_code")},
        ],
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "raw_private_content": False,
        },
    }


def stack_closure_external_evidence(
    path: Path | None = None,
    *,
    config: SelfAwarenessStackProbeConfig,
    runtime_port: SelfAwarenessStackProbeRuntimePort,
) -> dict[str, Any]:
    source_path = path or config.closure_evidence_config
    schema = f"{config.schema_prefix}_self_awareness_stack_closure_external_evidence_v1"
    row_schema = f"{config.schema_prefix}_stack_requirement_closure_evidence_v1"
    exists = runtime_port.path_exists(source_path)
    if not exists:
        return {
            "schema": schema,
            "version": config.version,
            "generated_at": runtime_port.now_iso(),
            "ok": True,
            "status": "missing_optional_config",
            "config_path": str(source_path),
            "entries": {},
            "summary": {"entries": 0, "accepted": 0, "rejected": 0, "missing_optional_config": True},
            "policy": {
                "read_only": True,
                "host_layer_mutates_stack": False,
                "missing_config_is_not_failure": True,
                "raw_payloads_included": False,
                "raw_secrets_included": False,
            },
        }
    try:
        size_bytes = runtime_port.path_stat(source_path).st_size
    except OSError:
        size_bytes = None
    if size_bytes is not None and size_bytes > 512 * 1024:
        return {
            "schema": schema,
            "version": config.version,
            "generated_at": runtime_port.now_iso(),
            "ok": True,
            "status": "ignored_oversized_config",
            "config_path": str(source_path),
            "entries": {},
            "summary": {"entries": 0, "accepted": 0, "rejected": 1, "size_bytes": size_bytes},
            "policy": {
                "read_only": True,
                "host_layer_mutates_stack": False,
                "oversized_config_is_ignored": True,
                "raw_payloads_included": False,
                "raw_secrets_included": False,
            },
        }
    doc, error = runtime_port.load_json_document(source_path)
    if error:
        return {
            "schema": schema,
            "version": config.version,
            "generated_at": runtime_port.now_iso(),
            "ok": True,
            "status": "ignored_invalid_config",
            "config_path": str(source_path),
            "entries": {},
            "summary": {"entries": 0, "accepted": 0, "rejected": 1, "error": error},
            "policy": {
                "read_only": True,
                "host_layer_mutates_stack": False,
                "invalid_config_is_ignored": True,
                "raw_payloads_included": False,
                "raw_secrets_included": False,
            },
        }
    raw_entries: list[dict[str, Any]] = []
    if isinstance(doc.get("requirements"), dict):
        for key, value in doc["requirements"].items():
            if isinstance(value, dict):
                row = dict(value)
                row.setdefault("requirement_id", key)
                raw_entries.append(row)
    if isinstance(doc.get("entries"), dict):
        for key, value in doc["entries"].items():
            if isinstance(value, dict):
                row = dict(value)
                row.setdefault("requirement_id", key)
                raw_entries.append(row)
    elif isinstance(doc.get("entries"), list):
        raw_entries.extend(item for item in doc["entries"] if isinstance(item, dict))

    def compact_refs(refs: Any) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not isinstance(refs, list):
            return out
        for ref in refs[:24]:
            if not isinstance(ref, dict):
                continue
            clean: dict[str, Any] = {}
            for key in ("path", "url", "schema", "status_code", "probe", "locator", "sha256", "generated_at"):
                if key in ref:
                    clean[key] = ref.get(key)
            if clean:
                out.append(clean)
        return out

    def compact_current_state(state: Any) -> dict[str, Any]:
        if not isinstance(state, dict):
            return {}
        allowed = {
            "backend", "ready_status", "ready_status_code", "ready_url",
            "trace_id_query_supported", "traceparent_supported", "trace_backend_ready",
            "trace_search_readable", "trace_span_search_readable", "span_log_metric_join_supported",
            "alloy_pipeline_status", "loki_traceparent_query_status", "freshness_or_retention",
            "datasource_inventory_present", "datasource_inventory_count",
            "database_graph_inventory_route_present", "inventory_complete",
            "postgres_schema_inventory_present", "neo4j_graph_inventory_present",
            "stack_owned_postgres_schema_inventory_present",
            "stack_owned_neo4j_graph_inventory_present",
            "stack_owned_inventory_route_present",
            "thread_inventory_present", "checkpoint_inventory_present", "trace_inventory_present",
            "langchain_trace_backend_coupled", "langchain_langgraph_inventory_readable",
            "generated_at", "freshness", "source", "route", "export_path",
        }
        return {
            str(key): value
            for key, value in state.items()
            if str(key) in allowed and isinstance(value, (str, int, float, bool, type(None), list, dict))
        }

    entries: dict[str, dict[str, Any]] = {}
    for raw in raw_entries:
        requirement_id = str(raw.get("requirement_id") or raw.get("id") or "")
        if not requirement_id:
            continue
        policy = raw.get("policy") if isinstance(raw.get("policy"), dict) else {}
        checks = raw.get("checks") if isinstance(raw.get("checks"), dict) else {}
        current_state = compact_current_state(raw.get("current_state") if isinstance(raw.get("current_state"), dict) else raw.get("state"))
        evidence_refs = compact_refs(raw.get("evidence_refs"))
        preview = json.dumps(
            {
                "requirement_id": requirement_id,
                "checks": checks,
                "current_state": current_state,
                "evidence_refs": evidence_refs,
            },
            sort_keys=True,
            default=str,
        )[:50000]
        secret_like = bool(runtime_port.secret_search(preview))
        owner_ok = str(raw.get("owner_route") or raw.get("source_owner") or raw.get("owner") or "") == "abyss-stack"
        schema_ok = raw.get("schema") in {row_schema, f"{config.schema_prefix}_self_awareness_stack_requirement_closure_evidence_v1"}
        policy_ok = (
            policy.get("host_layer_mutates_stack") is False
            and policy.get("raw_secrets_included") is False
            and policy.get("raw_payloads_included") is False
            and (policy.get("bounded") is True or policy.get("bounded_evidence") is True or policy.get("read_only") is True)
        )
        checks_ok = isinstance(checks, dict) and bool(checks)
        accepted = bool(schema_ok and owner_ok and policy_ok and checks_ok and not secret_like)
        rejection_reasons = [
            reason for reason, ok in (
                ("schema", schema_ok),
                ("owner_route", owner_ok),
                ("policy", policy_ok),
                ("checks", checks_ok),
                ("no_secret_like_content", not secret_like),
            )
            if not ok
        ]
        entries[requirement_id] = {
            "schema": f"{config.schema_prefix}_self_awareness_stack_closure_external_evidence_row_v1",
            "requirement_id": requirement_id,
            "accepted": accepted,
            "rejection_reasons": rejection_reasons,
            "checks": checks if accepted else {},
            "current_state": current_state if accepted else {},
            "evidence_refs": evidence_refs,
            "source": {
                "config_path": str(source_path),
                "schema": raw.get("schema"),
                "owner_route": raw.get("owner_route") or raw.get("source_owner") or raw.get("owner"),
                "generated_at": raw.get("generated_at"),
            },
            "policy": {
                "read_only": True,
                "host_layer_mutates_stack": False,
                "raw_payloads_included": False,
                "raw_secrets_included": False,
                "accepted_only_after_policy_and_redaction_checks": True,
            },
        }
    return {
        "schema": schema,
        "version": config.version,
        "generated_at": runtime_port.now_iso(),
        "ok": True,
        "status": "loaded",
        "config_path": str(source_path),
        "entries": entries,
        "summary": {
            "entries": len(entries),
            "accepted": sum(1 for row in entries.values() if row.get("accepted") is True),
            "rejected": sum(1 for row in entries.values() if row.get("accepted") is not True),
            "missing_optional_config": False,
            "size_bytes": size_bytes,
        },
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "missing_config_is_not_failure": True,
            "raw_payloads_included": False,
            "raw_secrets_included": False,
        },
    }


def trace_backend_probe(
    tempo_ready: dict[str, Any],
    stack_observability: dict[str, Any],
    closure_evidence: dict[str, Any] | None = None,
    *,
    config: SelfAwarenessStackProbeConfig,
    runtime_port: SelfAwarenessStackProbeRuntimePort,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    nested_get = self_awareness_contracts.nested_get
    safe_int = _safe_int
    base_url = config.tempo_url.rstrip("/")
    search = runtime_port.http_json(f"{base_url}/api/search?limit=1", timeout=1.2, max_bytes=65536)
    stack_summary = stack_observability.get("summary") if isinstance(stack_observability.get("summary"), dict) else {}
    prometheus = stack_observability.get("prometheus") if isinstance(stack_observability.get("prometheus"), dict) else {}
    loki = stack_observability.get("loki") if isinstance(stack_observability.get("loki"), dict) else {}
    alloy = stack_observability.get("alloy") if isinstance(stack_observability.get("alloy"), dict) else {}
    labels = nested_get(loki, ["labels", "labels"]) or []
    trace_context = loki.get("trace_context") if isinstance(loki.get("trace_context"), dict) else {}
    promql_jobs_up = stack_summary.get("promql_jobs_up") if isinstance(stack_summary.get("promql_jobs_up"), list) else []
    alloy_value = alloy.get("prometheus_value")
    alloy_seen = str(alloy_value) in {"1", "1.0"} or "alloy" in {str(item) for item in promql_jobs_up}
    loki_ready = bool(nested_get(loki, ["ready", "ok"]))
    loki_labels_readable = bool(nested_get(loki, ["labels", "ok"]))
    traceparent_query_ok = bool(trace_context.get("ok"))
    traceparent_entries = safe_int(trace_context.get("entry_count"), 0)
    trace_context_query_safe_empty = bool(traceparent_query_ok and traceparent_entries == 0)
    metrics_log_pipeline_readable = bool(alloy_seen and loki_ready and loki_labels_readable)
    trace_search_readable = bool(search.get("ok"))
    tempo_ready_status_code = safe_int(tempo_ready.get("status_code"), 0)
    tempo_ready_by_http_status = tempo_ready_status_code in {200, 204}
    backend_ready = bool(tempo_ready.get("ok") or tempo_ready_by_http_status)
    backend_ready_error = tempo_ready.get("error")
    external_entries = closure_evidence.get("entries") if isinstance(closure_evidence, dict) and isinstance(closure_evidence.get("entries"), dict) else {}
    external_trace = external_entries.get("stack.trace-backend") if isinstance(external_entries.get("stack.trace-backend"), dict) else {}
    external_accepted = external_trace.get("accepted") is True
    external_checks = external_trace.get("checks") if external_accepted and isinstance(external_trace.get("checks"), dict) else {}
    external_state = external_trace.get("current_state") if external_accepted and isinstance(external_trace.get("current_state"), dict) else {}
    if external_accepted:
        backend_ready = bool(
            backend_ready
            or external_checks.get("trace_backend_ready")
            or external_state.get("trace_backend_ready")
        )
        trace_search_readable = bool(
            trace_search_readable
            or external_checks.get("trace_span_search_readable")
            or external_checks.get("trace_search_readable")
            or external_state.get("trace_search_readable")
            or external_state.get("trace_span_search_readable")
        )
    span_log_metric_join_supported = bool(backend_ready and trace_search_readable and traceparent_query_ok)
    if external_accepted:
        span_log_metric_join_supported = bool(
            span_log_metric_join_supported
            or external_checks.get("span_log_metric_join_supported")
            or external_state.get("span_log_metric_join_supported")
        )
    external_evidence_refs = external_trace.get("evidence_refs") if isinstance(external_trace.get("evidence_refs"), list) else []
    return {
        "schema": f"{SCHEMA_PREFIX}_stack_trace_backend_probe_v1",
        "backend": {
            "kind": "tempo_or_compatible",
            "base_url": base_url,
            "ready": {
                "url": external_state.get("ready_url") or external_state.get("route") or tempo_ready.get("url") or f"{base_url}/ready",
                "ok": backend_ready,
                "status_code": external_state.get("ready_status_code") or tempo_ready.get("status_code"),
                "error": None if tempo_ready_by_http_status else backend_ready_error,
                "accepted_by_http_status": tempo_ready_by_http_status,
            },
            "search": {
                "url": search.get("url"),
                "ok": trace_search_readable,
                "status_code": search.get("status_code"),
                "error": search.get("error"),
                "truncated": search.get("truncated"),
            },
            "external_closure_evidence": {
                "accepted": external_accepted,
                "config_path": nested_get(external_trace, ["source", "config_path"]),
                "rejection_reasons": external_trace.get("rejection_reasons") if isinstance(external_trace.get("rejection_reasons"), list) else [],
            },
        },
        "pipeline_evidence": {
            "prometheus_jobs_up": [str(item) for item in promql_jobs_up[:32]],
            "alloy_seen": alloy_seen,
            "alloy_prometheus_value": alloy_value,
            "loki_ready": loki_ready,
            "loki_labels_readable": loki_labels_readable,
            "loki_label_count": safe_int(nested_get(loki, ["labels", "label_count"]), len(labels)),
            "loki_labels": [str(item) for item in labels[:32]],
            "logql_entries_seen": safe_int(stack_summary.get("logql_entries_seen"), 0),
            "metrics_log_pipeline_readable": metrics_log_pipeline_readable,
        },
        "trace_context": {
            "w3c_traceparent_parser_present": True,
            "traceparent_log_query": trace_context.get("query"),
            "traceparent_log_query_ok": traceparent_query_ok,
            "traceparent_log_entries_seen": traceparent_entries,
            "trace_context_query_safe_empty": trace_context_query_safe_empty,
            "trace_context_samples": [
                {
                    "ts": sample.get("ts"),
                    "labels": sample.get("labels"),
                    "line_hash": sample.get("line_hash"),
                }
                for sample in (trace_context.get("samples") if isinstance(trace_context.get("samples"), list) else [])[:3]
                if isinstance(sample, dict)
            ],
        },
        "join_readiness": {
            "trace_backend_ready": backend_ready,
            "trace_search_readable": trace_search_readable,
            "traceparent_queryable_in_logs": traceparent_query_ok,
            "span_log_metric_join_supported": span_log_metric_join_supported,
            "explicit_empty_traceparent_result": trace_context_query_safe_empty,
            "missing": [
                label for label, present in [
                    ("trace_backend_ready", backend_ready),
                    ("trace_search_readable", trace_search_readable),
                    ("span_log_metric_join_supported", span_log_metric_join_supported),
                ]
                if not present
            ],
        },
        "redaction": {
            "stores_backend_status_only": True,
            "stores_log_line_hashes_only": True,
            "raw_span_payloads_stored": False,
            "raw_log_exports_stored": False,
            "raw_trace_payloads_stored": False,
            "raw_secrets_stored": False,
        },
            "evidence_refs": [
                {"url": tempo_ready.get("url") or f"{base_url}/ready", "status_code": tempo_ready.get("status_code"), "error": None if tempo_ready_by_http_status else backend_ready_error, "probe": "tempo_ready"},
                {"url": search.get("url"), "status_code": search.get("status_code"), "error": search.get("error"), "probe": "tempo_search"},
                {"path": str(config.stack_observability_latest), "schema": stack_observability.get("schema"), "locator": "alloy"},
                {"path": str(config.stack_observability_latest), "schema": stack_observability.get("schema"), "locator": "loki.trace_context"},
            ] + external_evidence_refs,
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "starts_trace_backend": False,
            "raw_private_content": False,
        },
    }


def redact_url_userinfo(value: Any) -> str | None:
    if not value:
        return None
    text = str(value)
    try:
        parsed = urllib.parse.urlsplit(text)
    except Exception:
        return text
    if not parsed.netloc or "@" not in parsed.netloc:
        return text
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return urllib.parse.urlunsplit((parsed.scheme, host, parsed.path, parsed.query, parsed.fragment))


def grafana_datasource_entry(entry: dict[str, Any]) -> dict[str, Any]:
    safe_keys = {
        "id", "uid", "name", "type", "access", "url", "isDefault",
        "readOnly", "basicAuth", "database", "jsonData",
    }
    safe_json = entry.get("jsonData") if isinstance(entry.get("jsonData"), dict) else {}
    return {
        "id": entry.get("id") if "id" in safe_keys else None,
        "uid": entry.get("uid"),
        "name": entry.get("name"),
        "type": entry.get("type"),
        "access": entry.get("access"),
        "url": redact_url_userinfo(entry.get("url")),
        "is_default": entry.get("isDefault"),
        "read_only": entry.get("readOnly"),
        "basic_auth_enabled": bool(entry.get("basicAuth")),
        "json_data_keys": sorted(str(key) for key in safe_json.keys())[:32],
    }


def grafana_datasource_probe(
    grafana_health: dict[str, Any],
    grafana_datasources: dict[str, Any],
    stack_observability: dict[str, Any],
    alertmanager_status: dict[str, Any],
    trace_backend: dict[str, Any],
    *,
    config: SelfAwarenessStackProbeConfig,
    runtime_port: SelfAwarenessStackProbeRuntimePort,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    nested_get = self_awareness_contracts.nested_get
    safe_int = _safe_int
    base_url = config.grafana_url.rstrip("/")
    stack_owned_inventory = runtime_port.http_json(
        f"{config.route_api_url.rstrip()}/observability/datasources",
        timeout=1.5,
        max_bytes=131072,
    )
    extra_routes = {
        "search": "/api/search",
        "frontend_settings": "/api/frontend/settings",
        "dashboards_home": "/api/dashboards/home",
        "org": "/api/org",
    }
    route_probes = {
        key: runtime_port.http_json(f"{base_url}{path}", timeout=1.5, max_bytes=65536)
        for key, path in extra_routes.items()
    }
    health_json = grafana_health.get("json") if isinstance(grafana_health.get("json"), dict) else {}
    datasource_payload = grafana_datasources.get("json")
    datasource_entries: list[dict[str, Any]] = []
    if isinstance(datasource_payload, list):
        datasource_entries = [
            grafana_datasource_entry(item)
            for item in datasource_payload[:256]
            if isinstance(item, dict)
        ]
    elif isinstance(datasource_payload, dict) and isinstance(datasource_payload.get("datasources"), list):
        datasource_entries = [
            grafana_datasource_entry(item)
            for item in datasource_payload["datasources"][:256]
            if isinstance(item, dict)
        ]
    stack_inventory_payload = stack_owned_inventory.get("json") if isinstance(stack_owned_inventory.get("json"), dict) else {}
    stack_inventory = stack_inventory_payload.get("datasource_inventory") if isinstance(stack_inventory_payload.get("datasource_inventory"), dict) else {}
    stack_inventory_entries = stack_inventory.get("entries") if isinstance(stack_inventory.get("entries"), list) else []
    stack_inventory_entries = [
        item for item in stack_inventory_entries[:256]
        if isinstance(item, dict)
    ]
    stack_inventory_redaction = stack_inventory_payload.get("redaction") if isinstance(stack_inventory_payload.get("redaction"), dict) else {}
    stack_inventory_safe = bool(
        stack_owned_inventory.get("ok")
        and stack_inventory.get("present")
        and safe_int(stack_inventory.get("count"), 0) > 0
        and stack_inventory_redaction.get("secure_json_data_included") is False
        and stack_inventory_redaction.get("passwords_included") is False
        and stack_inventory_redaction.get("tokens_included") is False
        and stack_inventory_redaction.get("raw_credentials_included") is False
    )
    if not datasource_entries and stack_inventory_safe:
        datasource_entries = stack_inventory_entries
    stack_summary = stack_observability.get("summary") if isinstance(stack_observability.get("summary"), dict) else {}
    jobs_up = {str(item) for item in (stack_summary.get("promql_jobs_up") if isinstance(stack_summary.get("promql_jobs_up"), list) else [])}
    loki = stack_observability.get("loki") if isinstance(stack_observability.get("loki"), dict) else {}
    trace_ready = bool(nested_get(trace_backend, ["join_readiness", "trace_backend_ready"]))
    inferred_candidates = [
        {
            "type": "prometheus",
            "name_hint": "Prometheus",
            "source": "live_prometheus_job",
            "route": config.prometheus_url.rstrip("/"),
            "source_readable": "prometheus" in jobs_up,
            "closure_kind": "candidate_not_grafana_inventory",
        },
        {
            "type": "loki",
            "name_hint": "Loki",
            "source": "live_loki_internal_route",
            "route": config.loki_url.rstrip("/"),
            "source_readable": bool(nested_get(loki, ["ready", "ok"])),
            "closure_kind": "candidate_not_grafana_inventory",
        },
        {
            "type": "alertmanager",
            "name_hint": "Alertmanager",
            "source": "live_alertmanager_api",
            "route": config.alertmanager_url.rstrip("/"),
            "source_readable": bool(alertmanager_status.get("ok")),
            "closure_kind": "candidate_not_grafana_inventory",
        },
        {
            "type": "tempo",
            "name_hint": "Tempo",
            "source": "trace_backend_requirement",
            "route": config.tempo_url.rstrip("/"),
            "source_readable": trace_ready,
            "closure_kind": "candidate_not_grafana_inventory",
        },
    ]
    route_statuses = {
        "datasources": {
            "url": grafana_datasources.get("url"),
            "ok": grafana_datasources.get("ok"),
            "status_code": grafana_datasources.get("status_code"),
            "error": grafana_datasources.get("error"),
        },
        "stack_owned_export": {
            "url": stack_owned_inventory.get("url"),
            "ok": stack_owned_inventory.get("ok"),
            "status_code": stack_owned_inventory.get("status_code"),
            "error": stack_owned_inventory.get("error"),
        },
        **{
            key: {
                "url": probe.get("url"),
                "ok": probe.get("ok"),
                "status_code": probe.get("status_code"),
                "error": probe.get("error"),
            }
            for key, probe in route_probes.items()
        },
    }
    denied_routes = [
        key for key, row in route_statuses.items()
        if safe_int(row.get("status_code"), 0) in {401, 403}
    ]
    readable_routes = [
        key for key, row in route_statuses.items()
        if row.get("ok") and safe_int(row.get("status_code"), 0) in range(200, 300)
    ]
    inventory_present = bool(datasource_entries)
    return {
        "schema": f"{SCHEMA_PREFIX}_stack_grafana_datasource_probe_v1",
        "base_url": base_url,
        "ok": bool(grafana_health.get("ok")),
        "health": {
            "url": grafana_health.get("url"),
            "ok": grafana_health.get("ok"),
            "status_code": grafana_health.get("status_code"),
            "database": health_json.get("database"),
            "version": health_json.get("version"),
            "commit": health_json.get("commit"),
            "error": grafana_health.get("error"),
        },
        "api_access": {
            "routes": route_statuses,
            "denied_routes": denied_routes,
            "readable_routes": readable_routes,
            "datasource_api_auth_denied": "datasources" in denied_routes,
            "all_inventory_routes_denied": bool(denied_routes) and not readable_routes,
        },
        "datasource_inventory": {
            "present": inventory_present,
            "count": len(datasource_entries),
            "entries": datasource_entries,
            "source": "stack_owned_route_api_export" if stack_inventory_safe else "grafana_api",
            "stack_owned_route_readable": bool(stack_owned_inventory.get("ok")),
            "stack_owned_route_safe": stack_inventory_safe,
        },
        "stack_owned_inventory": {
            "url": stack_owned_inventory.get("url"),
            "ok": stack_owned_inventory.get("ok"),
            "status_code": stack_owned_inventory.get("status_code"),
            "schema": stack_inventory_payload.get("schema"),
            "count": stack_inventory.get("count"),
            "types": stack_inventory.get("types") if isinstance(stack_inventory.get("types"), list) else [],
            "safe": stack_inventory_safe,
            "error": stack_owned_inventory.get("error"),
        },
        "inferred_datasource_candidates": inferred_candidates,
        "handoff": {
            "stack_owned_inventory_required": not inventory_present,
            "inferred_candidates_are_not_inventory": True,
            "acceptable_routes": [
                f"{base_url}/api/datasources with stack-owned read-only auth",
                f"{config.route_api_url.rstrip()}/observability/datasources",
            ],
        },
        "redaction": {
            "secure_json_data_stored": False,
            "passwords_stored": False,
            "tokens_stored": False,
            "url_userinfo_redacted": True,
            "raw_credentials_stored": False,
        },
        "evidence_refs": [
            {"url": grafana_health.get("url"), "status_code": grafana_health.get("status_code"), "probe": "grafana_health"},
            {"url": grafana_datasources.get("url"), "status_code": grafana_datasources.get("status_code"), "error": grafana_datasources.get("error"), "probe": "grafana_datasources"},
            {"url": stack_owned_inventory.get("url"), "status_code": stack_owned_inventory.get("status_code"), "error": stack_owned_inventory.get("error"), "probe": "stack_owned_grafana_datasource_inventory"},
            {"path": str(config.stack_observability_latest), "schema": stack_observability.get("schema"), "locator": "prometheus.jobs"},
            {"path": str(config.stack_observability_latest), "schema": stack_observability.get("schema"), "locator": "loki.ready"},
        ],
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "stores_grafana_credentials": False,
            "uses_operator_token": False,
        },
    }

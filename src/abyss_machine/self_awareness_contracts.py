from __future__ import annotations

import collections
import datetime as dt
import hashlib
import json
import platform
import re
from pathlib import Path
from typing import Any, Callable

from . import validation_contracts


SCHEMA_PREFIX_DEFAULT = "abyss_machine"

SIGNALS = {
    "metric",
    "log",
    "alert",
    "process",
    "container",
    "service",
    "organ_movement",
    "heartbeat",
    "reaction",
    "response",
    "typing",
    "trace_context",
    "validation",
    "capability",
    "model",
    "rag",
    "memory",
    "mode",
    "resource",
    "nervous",
    "synthetic_probe",
}

SOURCES = {
    "prometheus",
    "loki",
    "grafana",
    "alloy",
    "alertmanager",
    "podman",
    "heartbeats",
    "reactions",
    "responses",
    "typing",
    "graph",
    "maps",
    "rag",
    "ai",
    "llm",
    "stt",
    "tts",
    "npu",
    "embeddings",
    "memory",
    "resource",
    "mode",
    "nervous",
    "observability",
    "scheduler",
    "host-service",
    "processes",
    "postgres",
    "neo4j",
    "route-api",
    "rag-api",
    "langchain-api",
    "working-stack",
    "synthetic",
}

UNBOUNDED_LABELS = {
    "trace_id",
    "traceid",
    "span_id",
    "spanid",
    "traceparent",
    "request_id",
    "requestid",
    "session_id",
    "sessionid",
    "goal_id",
    "task_id",
    "run_id",
    "user_id",
    "order_id",
}

SECRET_RE = re.compile(
    r"(?i)(authorization:\s*bearer\s+[^\s]+|api[_-]?key\s*[:=]\s*['\"]?[^\s'\"]+|password\s*[:=]\s*[^\s]+|sk-[a-z0-9_-]{16,})"
)
TRACEPARENT_RE = re.compile(r"\b(00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2})\b", re.IGNORECASE)
TRACE_ID_RE = re.compile(r"\btrace[_-]?id[=: ]+([0-9a-f]{16,32})\b", re.IGNORECASE)


def _schema(schema_prefix: str, suffix: str) -> str:
    return f"{schema_prefix}_{suffix}"


def stable_hash_json(payload: Any, length: int = 24) -> str:
    try:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        raw = str(payload)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[: max(8, min(int(length), 64))]


def nested_get(data: Any, path: list[str]) -> Any:
    cursor: Any = data
    for key in path:
        if not isinstance(cursor, dict):
            return None
        cursor = cursor.get(key)
    return cursor


def commands() -> dict[str, str]:
    return {
        "paths": "abyss-machine self-awareness paths --json",
        "status": "abyss-machine self-awareness status --json",
        "capabilities": "abyss-machine self-awareness capabilities --json",
        "requirements": "abyss-machine self-awareness requirements --json",
        "requirement_probes": "abyss-machine self-awareness requirement-probes --json",
        "stack_closure_dossier": "abyss-machine self-awareness stack-closure-dossier --json",
        "trace_context": "abyss-machine self-awareness trace-context --json",
        "working_stack": "abyss-machine self-awareness working-stack --json",
        "collect": "abyss-machine self-awareness collect --json",
        "query": "abyss-machine self-awareness query --query TEXT --json",
        "correlate": "abyss-machine self-awareness correlate --json",
        "timeline": "abyss-machine self-awareness timeline --json",
        "spatial_graph": "abyss-machine self-awareness spatial-graph --json",
        "context": "abyss-machine self-awareness context --json",
        "episodes": "abyss-machine self-awareness episodes --json",
        "alerts": "abyss-machine self-awareness alerts --json",
        "investigate": "abyss-machine self-awareness investigate --query TEXT --json",
        "replay": "abyss-machine self-awareness replay --json",
        "brief": "abyss-machine self-awareness brief --json",
        "failure_matrix": "abyss-machine self-awareness failure-matrix --json",
        "coverage_audit": "abyss-machine self-awareness coverage-audit --json",
        "activation_smoke": "abyss-machine self-awareness activation-smoke --json",
        "autolink": "abyss-machine self-awareness autolink --json",
        "completion_audit": "abyss-machine self-awareness completion-audit --json",
        "probe": "abyss-machine self-awareness probe --json",
        "cycle": "abyss-machine self-awareness cycle --json",
        "export": "abyss-machine self-awareness export --json",
        "validate": "abyss-machine self-awareness validate --json",
    }


def paths_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    root: Path,
    doc_path: Path,
    agents_path: Path,
    index_path: Path,
    surfaces: dict[str, tuple[Path, Path]],
    inputs: dict[str, Path],
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "schema": _schema(schema_prefix, "self_awareness_paths_v1"),
        "version": version,
        "generated_at": generated_at,
        "root": str(root),
        "doc": str(doc_path),
        "agent_entrypoint": str(agents_path),
        "index": str(index_path),
    }
    for key, (surface_root, latest_path) in surfaces.items():
        row: dict[str, Any] = {"root": str(surface_root), "latest": str(latest_path)}
        if key == "events":
            row["daily_glob"] = str(surface_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl")
        data[key] = row
    data["commands"] = commands()
    data["inputs"] = {key: str(path) for key, path in inputs.items()}
    data["policy"] = {
        "read_only_stack_consumer": True,
        "host_layer_mutates_stack": False,
        "writes_project_roots": False,
        "automatic_remediation": False,
        "reaction_candidates_only": True,
    }
    return data


def validate_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    checks: list[dict[str, Any]],
    strict: bool,
    paths: dict[str, Any],
    summary_extra: dict[str, Any] | None,
) -> dict[str, Any]:
    return validation_contracts.validation_document(
        schema=_schema(schema_prefix, "self_awareness_validate_v1"),
        version=version,
        generated_at=generated_at,
        checks=checks,
        strict=strict,
        scope="Abyss Machine self-awareness observability layer",
        extra={
            "paths": dict(paths) if isinstance(paths, dict) else {},
            "summary_extra": dict(summary_extra) if isinstance(summary_extra, dict) else None,
        },
    )


def bridge_contract(
    *,
    agents_path: Path,
    doc_path: Path,
    collect_latest_path: Path,
    capabilities_latest_path: Path,
    requirements_latest_path: Path,
    requirement_probes_latest_path: Path,
    stack_closure_dossier_latest_path: Path,
    trace_context_latest_path: Path,
    failure_matrix_latest_path: Path,
    working_stack_latest_path: Path,
    coverage_audit_latest_path: Path,
    activation_smoke_latest_path: Path,
    autolink_latest_path: Path,
    completion_audit_latest_path: Path,
    correlation_latest_path: Path,
    investigate_latest_path: Path,
    replay_latest_path: Path,
    export_latest_path: Path,
    validate_latest_path: Path,
    probe_latest_path: Path,
    cycle_latest_path: Path,
) -> dict[str, Any]:
    return {
        "agent_entrypoint": str(agents_path),
        "doc": str(doc_path),
        "latest": str(collect_latest_path),
        "capabilities_latest": str(capabilities_latest_path),
        "requirements_latest": str(requirements_latest_path),
        "requirement_probes_latest": str(requirement_probes_latest_path),
        "stack_closure_dossier_latest": str(stack_closure_dossier_latest_path),
        "trace_context_latest": str(trace_context_latest_path),
        "failure_matrix_latest": str(failure_matrix_latest_path),
        "working_stack_latest": str(working_stack_latest_path),
        "coverage_audit_latest": str(coverage_audit_latest_path),
        "activation_smoke_latest": str(activation_smoke_latest_path),
        "autolink_latest": str(autolink_latest_path),
        "completion_audit_latest": str(completion_audit_latest_path),
        "correlation_latest": str(correlation_latest_path),
        "investigate_latest": str(investigate_latest_path),
        "replay_latest": str(replay_latest_path),
        "export_latest": str(export_latest_path),
        "validate_latest": str(validate_latest_path),
        "probe_latest": str(probe_latest_path),
        "cycle_latest": str(cycle_latest_path),
        "commands": commands(),
        "contract": "Read-only causal-temporal-spatial understanding layer over stack observability and host readmodels.",
        "non_claim": "Self-awareness is evidence and owner-gated reaction routing; it does not mutate abyss-stack, execute remediation, or claim root cause without cited evidence.",
    }


def redact_text(value: Any, limit: int = 500) -> str:
    text = "" if value is None else str(value)
    text = SECRET_RE.sub("<redacted>", text)
    text = " ".join(text.split())
    if len(text) > limit:
        return text[: max(0, limit - 3)] + "..."
    return text


def bounded_json_shape(value: Any, depth: int = 0, max_depth: int = 2, max_items: int = 12) -> Any:
    if depth >= max_depth:
        if isinstance(value, dict):
            return {"type": "object", "keys": sorted(str(key) for key in value)[:max_items]}
        if isinstance(value, list):
            return {"type": "list", "length": len(value)}
    if isinstance(value, dict):
        shaped: dict[str, Any] = {}
        for key in sorted(value)[:max_items]:
            item = value.get(key)
            if isinstance(item, (dict, list)):
                shaped[str(key)] = bounded_json_shape(item, depth + 1, max_depth, max_items)
            elif isinstance(item, (str, int, float, bool)) or item is None:
                shaped[str(key)] = redact_text(item, 120) if isinstance(item, str) else item
        return shaped
    if isinstance(value, list):
        return {
            "type": "list",
            "length": len(value),
            "sample": [bounded_json_shape(item, depth + 1, max_depth, max_items) for item in value[: min(len(value), 3)]],
        }
    if isinstance(value, str):
        return redact_text(value, 120)
    return value


def http_probe_summary(response: dict[str, Any], kind: str) -> dict[str, Any]:
    payload = response.get("json") if isinstance(response.get("json"), dict) else None
    return {
        "kind": kind,
        "ok": bool(response.get("ok")),
        "url": response.get("url"),
        "status_code": response.get("status_code"),
        "elapsed_ms": response.get("elapsed_ms"),
        "error": response.get("error"),
        "truncated": response.get("truncated"),
        "json_shape": response.get("json_shape") if isinstance(response.get("json_shape"), dict) else bounded_json_shape(payload) if payload is not None else None,
        "text_preview_hash": response.get("text_preview_hash") or (stable_hash_json(response.get("text_preview"), length=16) if response.get("text_preview") else None),
        "body_stored": False,
        "raw_private_content": False,
    }


def context_from_text(text: Any) -> dict[str, Any]:
    raw = "" if text is None else str(text)
    context: dict[str, Any] = {}
    traceparent_match = TRACEPARENT_RE.search(raw)
    if traceparent_match:
        traceparent = traceparent_match.group(1).lower()
        parts = traceparent.split("-")
        context.update({
            "traceparent": traceparent,
            "trace_id": parts[1],
            "span_id": parts[2],
        })
    else:
        trace_id_match = TRACE_ID_RE.search(raw)
        if trace_id_match:
            context["trace_id"] = trace_id_match.group(1).lower()
    return context


def parse_time(value: Any) -> dt.datetime | None:
    if not value:
        return None
    text = str(value)
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def time_bucket(value: Any, minutes: int = 5) -> str:
    parsed = parse_time(value)
    if parsed is None:
        return "unknown"
    parsed = parsed.astimezone(dt.timezone.utc)
    bucket_minute = (parsed.minute // minutes) * minutes
    return parsed.replace(minute=bucket_minute, second=0, microsecond=0).isoformat().replace("+00:00", "Z")


def signal_fabric(
    *,
    signal: str,
    source: str,
    event_time: str,
    observed_at: str,
    source_query: str,
    resource: dict[str, Any],
    context: dict[str, Any],
    space: dict[str, Any],
    evidence_refs: list[dict[str, Any]],
    truth_level: str,
    schema_prefix: str = SCHEMA_PREFIX_DEFAULT,
    host: str | None = None,
) -> dict[str, Any]:
    owner_surface = str(resource.get("owner_surface") or space.get("owner_surface") or ("abyss-stack" if source in {"prometheus", "loki", "grafana", "alloy", "alertmanager", "podman"} else "abyss-machine"))
    service = resource.get("service") or resource.get("job") or resource.get("container") or space.get("service") or source
    container = resource.get("container") or space.get("container")
    endpoint = space.get("endpoint") or resource.get("endpoint")
    route = resource.get("route") or space.get("route") or endpoint
    path = resource.get("path") or space.get("path")
    model = resource.get("model") or resource.get("model_id") or space.get("model")
    thread_id = context.get("thread_id") or resource.get("thread_id")
    checkpoint_id = context.get("checkpoint_id") or resource.get("checkpoint_id")
    pid = resource.get("pid")
    label_keys = sorted(str(key).lower() for key in (resource.get("labels") if isinstance(resource.get("labels"), dict) else {}).keys())
    forbidden_label_keys = sorted(set(label_keys) & UNBOUNDED_LABELS)
    context_keys = [
        "traceparent",
        "trace_id",
        "span_id",
        "request_id",
        "session_id",
        "task_id",
        "goal_id",
        "synthetic_run_id",
        "alert_fingerprint",
        "thread_id",
        "checkpoint_id",
        "run_id",
        "working_stack_link_id",
        "movement_packet_id",
        "manual_collect_status",
        "scheduler_unit",
        "scheduler_scope",
        "scheduler_category",
        "host_service_unit",
        "host_service_scope",
        "host_service_category",
    ]
    links = {
        key: context.get(key)
        for key in context_keys
        if context.get(key) not in (None, "")
    }
    if resource.get("alert_fingerprint") and "alert_fingerprint" not in links:
        links["alert_fingerprint"] = resource.get("alert_fingerprint")
    bucket = time_bucket(event_time)
    correlation_keys = [
        item for item in [
            f"time_bucket:{bucket}",
            f"owner_surface:{owner_surface}" if owner_surface else None,
            f"source:{source}" if source else None,
            f"service:{service}" if service else None,
            f"container:{container}" if container else None,
            f"trace_id:{links.get('trace_id')}" if links.get("trace_id") else None,
            f"traceparent:{links.get('traceparent')}" if links.get("traceparent") else None,
            f"synthetic_run_id:{links.get('synthetic_run_id')}" if links.get("synthetic_run_id") else None,
            f"alert_fingerprint:{links.get('alert_fingerprint')}" if links.get("alert_fingerprint") else None,
            f"thread_id:{thread_id}" if thread_id else None,
            f"checkpoint_id:{checkpoint_id}" if checkpoint_id else None,
            f"manual_collect_status:{links.get('manual_collect_status')}" if links.get("manual_collect_status") else None,
            f"scheduler_unit:{links.get('scheduler_unit')}" if links.get("scheduler_unit") else None,
            f"scheduler_scope:{links.get('scheduler_scope')}" if links.get("scheduler_scope") else None,
            f"scheduler_category:{links.get('scheduler_category')}" if links.get("scheduler_category") else None,
            f"host_service_unit:{links.get('host_service_unit')}" if links.get("host_service_unit") else None,
            f"host_service_scope:{links.get('host_service_scope')}" if links.get("host_service_scope") else None,
            f"host_service_category:{links.get('host_service_category')}" if links.get("host_service_category") else None,
        ]
        if item
    ]
    return {
        "schema": _schema(schema_prefix, "self_awareness_signal_fabric_v1"),
        "signal": signal,
        "source": source,
        "actor": {
            "owner_surface": owner_surface,
            "kind": "stack_service" if owner_surface == "abyss-stack" else "machine_bridge",
            "source": source,
            "service": service,
            "container": container,
            "pid": pid,
        },
        "entity": {
            "service": service,
            "container": container,
            "job": resource.get("job"),
            "pid": pid,
            "route": route,
            "endpoint": endpoint,
            "path": path,
            "model": model,
            "thread_id": thread_id,
            "checkpoint_id": checkpoint_id,
        },
        "temporal": {
            "event_time": event_time,
            "observed_at": observed_at,
            "time_bucket": bucket,
        },
        "spatial": {
            "host": host or space.get("host") or platform.node(),
            "owner_surface": owner_surface,
            "layer": space.get("layer"),
            "service": service,
            "container": container,
            "endpoint": endpoint,
            "route": route,
            "path": path,
        },
        "context_links": {
            "links": links,
            "correlation_keys": correlation_keys,
            "trace_id": links.get("trace_id"),
            "span_id": links.get("span_id"),
            "traceparent": links.get("traceparent"),
            "thread_id": thread_id,
            "checkpoint_id": checkpoint_id,
        },
        "evidence_route": {
            "refs": len(evidence_refs),
            "has_refs": bool(evidence_refs),
            "source_query": source_query,
            "source_query_redacted": True,
            "ref_kinds": sorted({
                "path" if ref.get("path") else "url" if ref.get("url") else "query" if ref.get("query") else "other"
                for ref in evidence_refs
                if isinstance(ref, dict)
            }),
        },
        "label_policy": {
            "label_keys": label_keys,
            "forbidden_context_label_keys": forbidden_label_keys,
            "high_cardinality_context_as_labels": False,
        },
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "raw_body_stored": False,
            "truth_level": truth_level,
        },
    }


def make_event(
    signal: str,
    source: str,
    *,
    event_time: str | None = None,
    observed_at: str | None = None,
    source_query: str | None = None,
    resource: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    space: dict[str, Any] | None = None,
    severity: str = "info",
    confidence: dict[str, Any] | None = None,
    body: Any = None,
    evidence_refs: list[dict[str, Any]] | None = None,
    truth_level: str = "normalized",
    schema_prefix: str = SCHEMA_PREFIX_DEFAULT,
    now: Callable[[], str] | None = None,
    host: str | None = None,
) -> dict[str, Any]:
    observed = observed_at or (now() if now else dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"))
    happened = event_time or observed
    resource_data = resource or {}
    context_data = context or {}
    space_data = space or {}
    refs = evidence_refs or []
    body_preview = redact_text(body, 600)
    body_hash = stable_hash_json(body_preview, length=32)
    event_core = {
        "signal": signal,
        "source": source,
        "event_time": happened,
        "resource": resource_data,
        "context": context_data,
        "body_hash": body_hash,
        "truth_level": truth_level,
    }
    redacted_source_query = redact_text(source_query or "", 500)
    fabric = signal_fabric(
        signal=signal,
        source=source,
        event_time=happened,
        observed_at=observed,
        source_query=redacted_source_query,
        resource=resource_data,
        context=context_data,
        space=space_data,
        evidence_refs=refs,
        truth_level=truth_level,
        schema_prefix=schema_prefix,
        host=host,
    )
    return {
        "schema": _schema(schema_prefix, "observation_event_v1"),
        "event_id": "saevt-" + stable_hash_json(event_core, length=24),
        "signal": signal,
        "event_time": happened,
        "observed_at": observed,
        "source": source,
        "source_query": redacted_source_query,
        "resource": resource_data,
        "context": context_data,
        "space": space_data,
        "fabric": fabric,
        "severity": severity,
        "confidence": confidence or {"score": 0.5, "reason": "normalized machine observation"},
        "body_hash": body_hash,
        "body_preview": body_preview,
        "redaction": {
            "secrets_redacted": True,
            "body_preview_limit": 600,
            "raw_body_stored": False,
        },
        "evidence_refs": refs,
        "truth_level": truth_level,
    }


def event_issues(
    event: dict[str, Any],
    *,
    schema_prefix: str = SCHEMA_PREFIX_DEFAULT,
    path_protection_decision: Callable[[str], str | None] | None = None,
) -> list[str]:
    issues: list[str] = []
    required = [
        "event_id",
        "signal",
        "event_time",
        "observed_at",
        "source",
        "source_query",
        "resource",
        "context",
        "space",
        "fabric",
        "severity",
        "confidence",
        "body_hash",
        "body_preview",
        "redaction",
        "evidence_refs",
        "truth_level",
    ]
    for key in required:
        if key not in event:
            issues.append(f"missing:{key}")
    if event.get("signal") not in SIGNALS:
        issues.append("invalid_signal")
    if event.get("source") not in SOURCES:
        issues.append("invalid_source")
    if not isinstance(event.get("evidence_refs"), list) or not event.get("evidence_refs"):
        issues.append("missing_evidence_refs")
    resource = event.get("resource") if isinstance(event.get("resource"), dict) else {}
    fabric = event.get("fabric") if isinstance(event.get("fabric"), dict) else {}
    if not fabric:
        issues.append("missing_fabric")
    else:
        if fabric.get("schema") != _schema(schema_prefix, "self_awareness_signal_fabric_v1"):
            issues.append("invalid_fabric_schema")
        for key in ("actor", "entity", "temporal", "spatial", "context_links", "evidence_route", "label_policy", "policy"):
            if not isinstance(fabric.get(key), dict):
                issues.append(f"fabric_missing:{key}")
        if nested_get(fabric, ["policy", "read_only"]) is not True:
            issues.append("fabric_not_read_only")
        if nested_get(fabric, ["policy", "host_layer_mutates_stack"]) is not False:
            issues.append("fabric_mutates_stack")
        if nested_get(fabric, ["policy", "raw_body_stored"]) is not False:
            issues.append("fabric_raw_body_stored")
        if nested_get(fabric, ["evidence_route", "has_refs"]) is not True:
            issues.append("fabric_missing_evidence_route")
        if nested_get(fabric, ["label_policy", "forbidden_context_label_keys"]):
            issues.append("fabric_forbidden_label_keys")
        if not nested_get(fabric, ["temporal", "time_bucket"]):
            issues.append("fabric_missing_time_bucket")
        if not nested_get(fabric, ["actor", "owner_surface"]):
            issues.append("fabric_missing_owner_surface")
    labels = resource.get("labels") if isinstance(resource.get("labels"), dict) else {}
    bad_labels = sorted(set(str(key).lower() for key in labels) & UNBOUNDED_LABELS)
    if bad_labels:
        issues.append("unbounded_label:" + ",".join(bad_labels))
    if path_protection_decision is not None:
        for path_text in [str(event.get("source_query") or ""), str(resource.get("path") or ""), str((event.get("space") or {}).get("path") or "")]:
            if not path_text.startswith("/"):
                continue
            if path_protection_decision(path_text) == "deny" and resource.get("write") is True:
                issues.append("protected_write_claim")
    preview = str(event.get("body_preview") or "")
    if SECRET_RE.search(preview):
        issues.append("secret_like_preview")
    return issues


def signal_fabric_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [event.get("fabric") for event in events if isinstance(event, dict) and isinstance(event.get("fabric"), dict)]
    return {
        "events": len(events),
        "with_fabric": len(rows),
        "with_actor": sum(1 for row in rows if isinstance(row.get("actor"), dict) and row["actor"].get("owner_surface")),
        "with_entity": sum(1 for row in rows if isinstance(row.get("entity"), dict)),
        "with_temporal": sum(1 for row in rows if isinstance(row.get("temporal"), dict) and row["temporal"].get("time_bucket")),
        "with_spatial": sum(1 for row in rows if isinstance(row.get("spatial"), dict) and row["spatial"].get("owner_surface")),
        "with_context_links": sum(1 for row in rows if isinstance(row.get("context_links"), dict) and isinstance(row["context_links"].get("correlation_keys"), list) and bool(row["context_links"].get("correlation_keys"))),
        "with_evidence_route": sum(1 for row in rows if nested_get(row, ["evidence_route", "has_refs"]) is True),
        "with_policy": sum(1 for row in rows if isinstance(row.get("policy"), dict) and row["policy"].get("read_only") is True and row["policy"].get("host_layer_mutates_stack") is False),
        "with_trace_context": sum(1 for row in rows if nested_get(row, ["context_links", "trace_id"]) or nested_get(row, ["context_links", "traceparent"])),
        "with_thread_or_checkpoint": sum(1 for row in rows if nested_get(row, ["context_links", "thread_id"]) or nested_get(row, ["context_links", "checkpoint_id"])),
        "forbidden_label_events": sum(1 for row in rows if nested_get(row, ["label_policy", "forbidden_context_label_keys"])),
        "sources": dict(collections.Counter(str(event.get("source")) for event in events if isinstance(event, dict))),
        "signals": dict(collections.Counter(str(event.get("signal")) for event in events if isinstance(event, dict))),
    }


def query_terms(query: Any) -> list[str]:
    text = redact_text(query or "", 480).lower()
    if text in {"", "*", "latest"}:
        return []
    raw_terms = re.findall(r"[a-z0-9][a-z0-9_.:-]{1,}", text)
    stop = {
        "and", "or", "the", "for", "with", "into", "from", "latest",
        "status", "state", "show", "find", "list", "about",
    }
    expansions = {
        "rag": ["rag", "retrieval", "graphrag", "context"],
        "graph": ["graph", "spatial", "neo4j", "dependency"],
        "memory": ["memory", "memo", "freshness", "context"],
        "postgres": ["postgres", "database", "schema"],
        "neo4j": ["neo4j", "graph", "relationship"],
        "embedding": ["embedding", "embeddings", "semantic"],
        "embeddings": ["embedding", "embeddings", "semantic"],
        "freshness": ["freshness", "stale", "generated_at", "gate"],
        "langgraph": ["langgraph", "checkpoint", "thread"],
    }
    terms: list[str] = []
    for term in raw_terms:
        pieces = [term]
        pieces.extend(part for part in re.split(r"[-_.:/]+", term) if len(part) >= 2)
        for piece in pieces:
            if piece in stop or len(piece) < 2:
                continue
            for expanded in expansions.get(piece, [piece]):
                if expanded not in terms:
                    terms.append(expanded)
    return terms[:32]


def match_score(value: Any, query: Any) -> int:
    terms = query_terms(query)
    if not terms:
        return 1
    text = redact_text(value, 20000).lower()
    score = 0
    for term in terms:
        if term in text:
            score += 1
    phrase = redact_text(query or "", 480).lower().strip()
    if phrase and phrase in text:
        score += max(2, len(terms))
    return score


def stack_handoff_impacted_services(requirement_id: str) -> list[str]:
    requirement_id = str(requirement_id or "")
    if "grafana" in requirement_id:
        return ["grafana", "prometheus", "loki", "alertmanager", "tempo"]
    if "trace" in requirement_id:
        return ["prometheus", "alloy", "loki", "tempo", "trace-backend"]
    if "database-graph" in requirement_id:
        return ["route-api", "rag-api", "postgres", "neo4j", "embeddings"]
    if "langchain" in requirement_id or "langgraph" in requirement_id:
        return ["langchain-api", "rag-api", "trace-backend", "tempo"]
    return ["abyss-stack"]


WORKING_STACK_ACTIVE_SIGNAL_SERVICES = {
    "prometheus",
    "grafana",
    "loki",
    "alloy",
    "tempo",
    "alertmanager",
    "cadvisor",
    "route-api",
    "rag-api",
    "langchain-api",
    "postgres",
    "neo4j",
}

WORKING_STACK_ACTIVE_DEPENDENCY_SERVICES = {
    "qdrant",
    "redis",
    "rerank-api",
    "ovms",
    "llama-cpp",
}

WORKING_STACK_POLICY_DEFERRED_STATUS_BY_POSTURE = {
    "explicit_opt_in": "policy_deferred_opt_in",
    "fallback_control": "policy_deferred_fallback",
    "lab_only": "policy_deferred_lab",
    "not_selected": "policy_deferred_not_selected",
}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def working_stack_policy_deferred_postures() -> list[str]:
    return sorted(WORKING_STACK_POLICY_DEFERRED_STATUS_BY_POSTURE)


def working_stack_policy_status(status: str, selection: dict[str, Any]) -> str:
    if status != "declared_not_running" or not isinstance(selection, dict):
        return status
    posture = str(selection.get("posture") or "").strip()
    return WORKING_STACK_POLICY_DEFERRED_STATUS_BY_POSTURE.get(posture, status)


def working_stack_roles(service: str) -> list[str]:
    roles = {
        "prometheus": ["promql", "metrics", "target_state"],
        "grafana": ["operator_dashboard", "health"],
        "loki": ["logql", "logs"],
        "alloy": ["otel_pipeline", "log_ingestion"],
        "tempo": ["trace_backend", "otel_trace_storage"],
        "alertmanager": ["alert_lifecycle"],
        "cadvisor": ["container_metrics"],
        "route-api": ["federation_routes", "space_routes"],
        "rag-api": ["rag_memory", "agentic_rag"],
        "langchain-api": ["agent_runtime", "embeddings_route", "langgraph_candidate"],
        "postgres": ["relational_backend", "semantic_inventory_requirement"],
        "neo4j": ["graph_backend", "semantic_inventory_requirement"],
        "qdrant": ["vector_database", "rag_dependency"],
        "redis": ["runtime_cache", "queue_or_cache_dependency"],
        "rerank-api": ["reranking", "rag_dependency"],
        "ovms": ["openvino_serving", "embeddings", "npu_gpu_runtime"],
        "llama-cpp": ["resident_llm_serving", "warm_e2b_candidate"],
        "docs-api": ["document_tooling"],
        "aoa-browser": ["browser_tooling"],
        "n8n": ["workflow_orchestration"],
        "litellm": ["llm_gateway"],
        "ollama": ["local_inference"],
        "qwen-tts": ["tts"],
        "tts-router": ["tts_route"],
        "babelvox-tts": ["tts"],
        "tos-graph": ["tree_of_sophia_graph"],
        "embeddings": ["semantic_embedding"],
        "stt": ["speech_to_text"],
        "tts": ["text_to_speech"],
        "npu": ["accelerator_runtime"],
    }
    return roles.get(service, ["stack_service"])


def working_stack_status(
    service: str,
    *,
    running: bool,
    declared: bool,
    endpoint_ok: bool,
    model_roots: int,
) -> str:
    if running and service in WORKING_STACK_ACTIVE_SIGNAL_SERVICES:
        return "active_machine_signal"
    if running and service in WORKING_STACK_ACTIVE_DEPENDENCY_SERVICES:
        return "active_dependency_signal"
    if running and endpoint_ok:
        return "endpoint_visible_unproven_deep_use"
    if running:
        return "runtime_visible_unproven_deep_use"
    if declared:
        return "declared_not_running"
    if model_roots:
        return "model_root_visible"
    return "visible_unclassified"


def working_stack_expected_link_id(service: str, status: str) -> str:
    return "saworklink-" + stable_hash_json({"service": service, "status": status}, length=20)


def working_stack_link(
    service: str,
    generated_at: str,
    *,
    status: str,
    container: str | None = None,
    pid: int | None = None,
    endpoint_ok: bool = False,
    schema_prefix: str = SCHEMA_PREFIX_DEFAULT,
) -> dict[str, Any]:
    bucket = time_bucket(generated_at)
    link_id = working_stack_expected_link_id(service, status)
    return {
        "schema": _schema(schema_prefix, "self_awareness_working_stack_time_space_context_link_v1"),
        "link_id": link_id,
        "service": service,
        "time": {
            "observed_at": generated_at,
            "bucket": bucket,
        },
        "space": {
            "node_id": f"service:{service}",
            "container_node_id": f"container:{container}" if container else None,
            "process_node_id": f"process:{pid}" if pid else None,
            "pid": pid,
            "owner_surface": "abyss-stack",
            "layer": "working-stack-runtime",
        },
        "context": {
            "working_stack_link_id": link_id,
            "correlation_keys": [
                f"time_bucket:{bucket}",
                "owner_surface:abyss-stack",
                "source:working-stack",
                f"service:{service}",
                f"container:{container}" if container else None,
                f"pid:{pid}" if pid else None,
                f"machine_usage_status:{status}",
            ],
            "machine_usage_status": status,
            "endpoint_ok": endpoint_ok,
            "pid": pid,
        },
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "raw_evidence_is_not_truth": True,
        },
    }


def working_stack_links_match_stable_identity(doc: dict[str, Any]) -> bool:
    organs = doc.get("organs") if isinstance(doc.get("organs"), list) else []
    if not organs:
        return False
    for organ in organs:
        if not isinstance(organ, dict):
            continue
        service = str(organ.get("service") or "")
        status = str(organ.get("machine_usage_status") or "")
        link_id = str(
            nested_get(organ, ["time_space_context_link", "link_id"])
            or nested_get(organ, ["time_space_context_link", "context", "working_stack_link_id"])
            or ""
        )
        if not service or not status or link_id != working_stack_expected_link_id(service, status):
            return False
    return True


def working_stack_gap_verifier_commands(service: str) -> list[str]:
    service = str(service or "").strip()
    commands = [
        "abyss-machine self-awareness working-stack --json",
        "abyss-machine self-awareness spatial-graph --json",
        "abyss-machine self-awareness episodes --json",
        "abyss-machine self-awareness alerts --json",
        "abyss-machine self-awareness validate --json",
        "abyss-machine reactions validate --json",
        "abyss-machine responses validate --json",
    ]
    if service:
        commands.insert(1, f"abyss-machine self-awareness query --query working-stack:{service} --json")
    return list(dict.fromkeys(commands))


def working_stack_gap_safe_next_action(service: str, status: str, gap_reason: str) -> dict[str, Any]:
    return {
        "kind": "stack_owner_runtime_usage_gap_review",
        "owner_route": "abyss-stack",
        "service": service,
        "machine_usage_status": status,
        "usage_gap": gap_reason,
        "command": "abyss-machine self-awareness working-stack --json",
        "source_episode_command": "abyss-machine self-awareness episodes --json",
        "source_alert_command": "abyss-machine self-awareness alerts --json",
        "verifier_commands": working_stack_gap_verifier_commands(service),
        "automatic": False,
        "requires_human_approval": True,
        "executes_commands": False,
        "host_layer_mutates_stack": False,
        "action_execution": False,
        "machine_action": "handoff_only",
        "rollback": "discard/regenerate machine-owned self-awareness/reactions/responses readmodels; abyss-machine did not change stack state",
    }


def working_stack_activation_gap_classification(gap: dict[str, Any]) -> str:
    status = str(gap.get("machine_usage_status") or "")
    failed_probe_names = [
        str(item)
        for item in (gap.get("failed_probe_names") if isinstance(gap.get("failed_probe_names"), list) else [])
        if item
    ]
    runtime_running = gap.get("runtime_running")
    runtime_state = str(gap.get("runtime_state") or "").lower()
    runtime_status = str(gap.get("runtime_status") or "").lower()
    container = str(gap.get("container") or "").strip()
    declared = gap.get("declared") is True
    endpoint_ok = gap.get("endpoint_ok")
    endpoint_probe_count = _safe_int(gap.get("endpoint_probe_count"), 0)
    model_roots = _safe_int(gap.get("model_roots"), 0)

    if status == "tool_runtime_degraded" and failed_probe_names:
        return "running_functional_smoke_failed"
    if runtime_running is True and failed_probe_names:
        return "running_probe_failed"
    if container and runtime_running is False and (runtime_state == "exited" or runtime_status.startswith("exited")):
        return "exited_stack_managed_container"
    if declared and runtime_running is not True:
        return "declared_without_running_runtime"
    if endpoint_probe_count > 0 and endpoint_ok is not True:
        return "endpoint_probe_gap"
    if status == "model_root_visible" or model_roots > 0:
        return "model_runtime_link_gap"
    if status.endswith("_unproven_deep_use"):
        return "deep_usage_route_unproven"
    return "working_stack_potential_unclassified"


def working_stack_gap_activation_kind(status: str) -> str:
    if status == "tool_runtime_degraded":
        return "stack_tool_runtime_smoke_gap"
    if status == "declared_not_running":
        return "stack_declared_service_activation_gap"
    if status == "model_root_visible":
        return "stack_model_root_runtime_link_gap"
    if status == "endpoint_visible_unproven_deep_use":
        return "stack_endpoint_deep_usage_gap"
    if status == "runtime_visible_unproven_deep_use":
        return "stack_runtime_deep_usage_gap"
    return "stack_working_organ_deep_usage_gap"


def working_stack_gap_coverage_planes(status: str) -> list[str]:
    planes = [
        "working_stack_body",
        "runtime_organs",
        "causal_timeline",
        "spatial_graph",
        "reaction_candidates",
        "response_governance",
        "investigation_replay",
        "langgraph_replay",
    ]
    if status == "tool_runtime_degraded":
        planes.append("tool_runtime_smoke")
    if status == "declared_not_running":
        planes.append("stack_service_activation")
    if status == "model_root_visible":
        planes.append("model_runtime_bridge")
    return list(dict.fromkeys(planes))


def working_stack_activation_gap_route(
    working_stack_gap: dict[str, Any],
    *,
    episode_id: str | None = None,
    activation_row: dict[str, Any] | None = None,
    evidence_refs: list[dict[str, Any]] | None = None,
    schema_prefix: str = SCHEMA_PREFIX_DEFAULT,
) -> dict[str, Any]:
    if not isinstance(working_stack_gap, dict) or not working_stack_gap.get("service"):
        return {}
    activation_row = activation_row if isinstance(activation_row, dict) else {}
    service = str(working_stack_gap.get("service") or "")
    status = str(working_stack_gap.get("machine_usage_status") or "unknown")
    usage_gap = str(working_stack_gap.get("usage_gap") or "")
    classification = working_stack_activation_gap_classification(working_stack_gap)
    activation_kind = str(working_stack_gap.get("activation_kind") or working_stack_gap_activation_kind(status))
    safe_next = working_stack_gap.get("safe_next_action") if isinstance(working_stack_gap.get("safe_next_action"), dict) else {}
    if not safe_next:
        safe_next = working_stack_gap_safe_next_action(service, status, usage_gap)
    verifier_commands = [
        str(item)
        for item in (working_stack_gap.get("verifier_commands") if isinstance(working_stack_gap.get("verifier_commands"), list) else [])
        if item
    ]
    if not verifier_commands:
        verifier_commands = working_stack_gap_verifier_commands(service)
    closure_blocker_keys = [
        str(item)
        for item in (working_stack_gap.get("closure_blocker_keys") if isinstance(working_stack_gap.get("closure_blocker_keys"), list) else [])
        if item
    ]
    if not closure_blocker_keys:
        closure_blocker_keys = [status, "usage_gap:" + stable_hash_json({"service": service, "status": status}, length=16)]
    failed_probe_names = [
        str(item)
        for item in (working_stack_gap.get("failed_probe_names") if isinstance(working_stack_gap.get("failed_probe_names"), list) else [])
        if item
    ]
    ok_probe_names = [
        str(item)
        for item in (working_stack_gap.get("ok_probe_names") if isinstance(working_stack_gap.get("ok_probe_names"), list) else [])
        if item
    ]
    smoke_investigation = activation_row.get("investigation") if isinstance(activation_row.get("investigation"), dict) else {}
    smoke_replay = activation_row.get("replay") if isinstance(activation_row.get("replay"), dict) else {}
    route = {
        "schema": _schema(schema_prefix, "self_awareness_working_stack_activation_gap_route_v1"),
        "route_id": "sagaproute-" + stable_hash_json({
            "episode_id": episode_id,
            "service": service,
            "status": status,
            "classification": classification,
        }, length=24),
        "episode_id": episode_id,
        "service": service,
        "owner_route": "abyss-stack",
        "machine_action": "handoff_only",
        "machine_usage_status": status,
        "usage_gap": usage_gap,
        "activation_kind": activation_kind,
        "classification": classification,
        "diagnosis": {
            "running_functional_smoke_failed": "service is running and guarded, but a bounded functional tool smoke failed",
            "running_probe_failed": "service is running, but at least one bounded probe failed",
            "exited_stack_managed_container": "stack-managed container exists but is currently exited",
            "declared_without_running_runtime": "stack declaration exists but no running runtime body is present",
            "endpoint_probe_gap": "service has probe surface, but current endpoint checks do not prove readiness",
            "model_runtime_link_gap": "model roots are visible but no current runtime route proves deep use",
            "deep_usage_route_unproven": "runtime or endpoint is visible, but no sustained machine usage route is proven",
            "working_stack_potential_unclassified": "working stack potential remains open and needs stack-owner review",
        }.get(classification, "working stack potential remains open and needs stack-owner review"),
        "working_stack_link_id": working_stack_gap.get("working_stack_link_id"),
        "current_state": {
            "runtime": {
                "present": working_stack_gap.get("runtime_present"),
                "running": working_stack_gap.get("runtime_running"),
                "container": working_stack_gap.get("container"),
                "health": working_stack_gap.get("health"),
                "state": working_stack_gap.get("runtime_state"),
                "status": working_stack_gap.get("runtime_status"),
                "stack_managed": working_stack_gap.get("runtime_stack_managed"),
            },
            "declared": {
                "present": working_stack_gap.get("declared"),
                "modules": working_stack_gap.get("declared_modules") if isinstance(working_stack_gap.get("declared_modules"), list) else [],
            },
            "endpoint": {
                "ok": working_stack_gap.get("endpoint_ok"),
                "probe_count": working_stack_gap.get("endpoint_probe_count"),
                "ok_probe_names": ok_probe_names,
                "failed_probe_names": failed_probe_names,
            },
            "roots": {
                "service_roots": working_stack_gap.get("service_roots"),
                "model_roots": working_stack_gap.get("model_roots"),
            },
            "deep_usage_proven": working_stack_gap.get("deep_usage_proven"),
        },
        "activation_smoke": {
            "row_complete": activation_row.get("complete") if activation_row else None,
            "thread_id": smoke_investigation.get("thread_id") or smoke_replay.get("thread_id"),
            "investigation_matches_episode": smoke_investigation.get("selected_episode_matches"),
            "replay_matches_investigation": smoke_replay.get("thread_matches"),
            "working_stack_gap_replayable": smoke_replay.get("working_stack_gap_replayable"),
        },
        "closure_blocker_keys": closure_blocker_keys,
        "safe_next_action": safe_next,
        "verifier_commands": verifier_commands,
        "evidence_refs": evidence_refs or [],
        "policy": {
            "handoff_only": True,
            "read_only": True,
            "automatic_execution": False,
            "executes_commands": False,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "raw_private_content": False,
            "raw_evidence_is_not_truth": True,
        },
    }
    route["complete"] = working_stack_activation_gap_route_complete(route, schema_prefix=schema_prefix)
    return route


def working_stack_activation_gap_route_complete(
    route: Any,
    *,
    schema_prefix: str = SCHEMA_PREFIX_DEFAULT,
) -> bool:
    if not isinstance(route, dict):
        return False
    current_state = route.get("current_state") if isinstance(route.get("current_state"), dict) else {}
    safe_next = route.get("safe_next_action") if isinstance(route.get("safe_next_action"), dict) else {}
    policy = route.get("policy") if isinstance(route.get("policy"), dict) else {}
    return (
        route.get("schema") == _schema(schema_prefix, "self_awareness_working_stack_activation_gap_route_v1")
        and bool(route.get("route_id"))
        and bool(route.get("service"))
        and route.get("owner_route") == "abyss-stack"
        and route.get("machine_action") == "handoff_only"
        and bool(route.get("machine_usage_status"))
        and bool(route.get("usage_gap"))
        and bool(route.get("activation_kind"))
        and bool(route.get("classification"))
        and bool(route.get("diagnosis"))
        and bool(route.get("working_stack_link_id"))
        and isinstance(current_state.get("runtime"), dict)
        and isinstance(current_state.get("declared"), dict)
        and isinstance(current_state.get("endpoint"), dict)
        and isinstance(route.get("closure_blocker_keys"), list)
        and bool(route.get("closure_blocker_keys"))
        and safe_next.get("requires_human_approval") is True
        and safe_next.get("executes_commands") is False
        and safe_next.get("host_layer_mutates_stack") is False
        and isinstance(route.get("verifier_commands"), list)
        and bool(route.get("verifier_commands"))
        and bool(route.get("evidence_refs"))
        and policy.get("handoff_only") is True
        and policy.get("automatic_execution") is False
        and policy.get("executes_commands") is False
        and policy.get("host_layer_mutates_stack") is False
        and policy.get("writes_project_roots") is False
    )

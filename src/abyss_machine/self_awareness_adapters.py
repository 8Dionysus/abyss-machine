from __future__ import annotations

import collections
import datetime as dt
import json
import re
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from . import self_awareness_contracts

try:
    import yaml
except ImportError:  # pragma: no cover - optional parser; JSON fallback is enough for tests.
    yaml = None


LatestJsonReaderPort = Callable[[Path, str], dict[str, Any]]
EnvGetPort = Callable[[str], str | None]
MeminfoTextReaderPort = Callable[[], str]
MeminfoReaderPort = Callable[[], dict[str, int]]
CpuCountReaderPort = Callable[[], int | None]
LoadAverageReaderPort = Callable[[], tuple[float, float, float]]
ClockPort = Callable[[], float]
HttpRequestFactoryPort = Callable[[str, Mapping[str, str], str], Any]
HttpOpenPort = Callable[[Any, float], Any]
HttpJsonPort = Callable[[str, float, int], dict[str, Any]]
HttpStatusPort = Callable[[str, float, int], dict[str, Any]]
RunCommandPort = Callable[[list[str], float], dict[str, Any]]
CommandExistsPort = Callable[[str], bool]
TcpConnectPort = Callable[[str, int, float], None]
PathExistsPort = Callable[[Path], bool]
PathIsDirPort = Callable[[Path], bool]
PathIsFilePort = Callable[[Path], bool]
PathGlobPort = Callable[[Path, str], Iterable[Path]]
PathIterdirPort = Callable[[Path], Iterable[Path]]
PathReadTextPort = Callable[[Path], str]
PathStatPort = Callable[[Path], Any]
PathSha256Port = Callable[[Path], str]
JsonDocumentLoaderPort = Callable[[Path], tuple[Any, str | None]]
SidecarDocumentLoaderPort = Callable[[str], Any]
WavFormatReaderPort = Callable[[Path], dict[str, Any]]
PidAlivePort = Callable[[int], bool]
ContainerToolProbesPort = Callable[[dict[str, dict[str, Any]], bool], list[dict[str, Any]]]
TtsSmokeProbesPort = Callable[[bool], list[dict[str, Any]]]
BackupPlaneActiveChangePort = Callable[[Mapping[str, Any]], bool]
BackupPlaneBlockersPort = Callable[[Mapping[str, Any]], list[str]]


@dataclass(frozen=True)
class SelfAwarenessLatestSpec:
    name: str
    path: Path
    schema: str


@dataclass(frozen=True)
class CycleArtifactStepSpec:
    step_id: str
    command: str
    path_key: str
    document_group: str
    document_key: str
    requires_ok: bool = True


@dataclass(frozen=True)
class WorkingStackEndpointProbeSpec:
    service: str
    probe: str
    url: str
    kind: str = "http_json"
    timeout: float = 1.5
    max_bytes: int = 131072


@dataclass(frozen=True)
class WorkingStackTcpProbeSpec:
    service: str
    host: str
    port: int
    timeout: float = 1.2


READMODEL_SCHEMA_SUFFIXES: tuple[tuple[str, str], ...] = (
    ("events", "self_awareness_events_v1"),
    ("collect", "self_awareness_collect_v1"),
    ("timeline", "self_awareness_timeline_v1"),
    ("spatial_graph", "self_awareness_spatial_graph_v1"),
    ("context", "self_awareness_context_v1"),
    ("episodes", "self_awareness_episodes_v1"),
    ("alerts", "self_awareness_alerts_v1"),
    ("brief", "self_awareness_brief_v1"),
    ("capabilities", "self_awareness_capabilities_v1"),
    ("requirements", "self_awareness_requirements_v1"),
    ("requirement_probes", "self_awareness_requirement_probes_v1"),
    ("stack_closure_dossier", "self_awareness_stack_closure_dossier_v1"),
    ("trace_context", "self_awareness_trace_context_fallback_v1"),
    ("failure_matrix", "self_awareness_failure_matrix_v1"),
    ("working_stack", "self_awareness_working_stack_inventory_v1"),
    ("coverage_audit", "self_awareness_objective_coverage_audit_v1"),
    ("activation_smoke", "self_awareness_working_stack_activation_smoke_v1"),
    ("autolink", "self_awareness_autolink_v1"),
    ("query", "self_awareness_query_v1"),
    ("correlation", "self_awareness_correlation_v1"),
    ("investigate", "self_awareness_investigation_v1"),
    ("replay", "self_awareness_replay_v1"),
    ("export", "self_awareness_export_v1"),
    ("probe", "self_awareness_probe_v1"),
    ("cycle", "self_awareness_cycle_v1"),
    ("validate", "self_awareness_validate_v1"),
)

CYCLE_LATEST_READ_NAMES: tuple[str, ...] = (
    "capabilities",
    "requirements",
    "trace_context",
    "working_stack",
    "collect",
    "events",
    "query",
    "correlation",
    "timeline",
    "spatial_graph",
    "context",
    "episodes",
    "alerts",
)

CYCLE_INITIAL_ARTIFACT_STEP_SPECS: tuple[CycleArtifactStepSpec, ...] = (
    CycleArtifactStepSpec("probe", "abyss-machine self-awareness probe --json", "probe", "direct", "probe"),
    CycleArtifactStepSpec("capabilities", "abyss-machine self-awareness capabilities --json", "capabilities", "latest", "capabilities"),
    CycleArtifactStepSpec("requirements", "abyss-machine self-awareness requirements --json", "requirements", "latest", "requirements"),
    CycleArtifactStepSpec("requirement_probes", "abyss-machine self-awareness requirement-probes --json", "requirement_probes", "direct", "requirement_probes"),
    CycleArtifactStepSpec("stack_closure_dossier", "abyss-machine self-awareness stack-closure-dossier --json", "stack_closure_dossier", "direct", "stack_closure_dossier"),
    CycleArtifactStepSpec("trace_context", "abyss-machine self-awareness trace-context --json", "trace_context", "latest", "trace_context"),
    CycleArtifactStepSpec("activation_smoke", "abyss-machine self-awareness activation-smoke --json", "activation_smoke", "direct", "activation_smoke"),
    CycleArtifactStepSpec("failure_matrix", "abyss-machine self-awareness failure-matrix --json", "failure_matrix", "direct", "failure_matrix"),
    CycleArtifactStepSpec("working_stack", "abyss-machine self-awareness working-stack --json", "working_stack", "latest", "working_stack"),
    CycleArtifactStepSpec("collect", "abyss-machine self-awareness collect --json", "collect", "latest", "collect"),
    CycleArtifactStepSpec("events", "abyss-machine self-awareness events/latest.json", "events", "latest", "events"),
    CycleArtifactStepSpec("query", "abyss-machine self-awareness query --query RUN_ID --json", "query", "latest", "query"),
    CycleArtifactStepSpec("correlation", "abyss-machine self-awareness correlate --json", "correlation", "latest", "correlation"),
    CycleArtifactStepSpec("timeline", "abyss-machine self-awareness timeline --json", "timeline", "latest", "timeline"),
    CycleArtifactStepSpec("spatial_graph", "abyss-machine self-awareness spatial-graph --json", "spatial_graph", "latest", "spatial_graph"),
    CycleArtifactStepSpec("context", "abyss-machine self-awareness context --json", "context", "latest", "context"),
    CycleArtifactStepSpec("episodes", "abyss-machine self-awareness episodes --json", "episodes", "latest", "episodes"),
    CycleArtifactStepSpec("alerts", "abyss-machine self-awareness alerts --json", "alerts", "latest", "alerts"),
    CycleArtifactStepSpec("heartbeats", "abyss-machine heartbeats pulse --json", "heartbeats", "bridge", "heartbeats", requires_ok=False),
    CycleArtifactStepSpec("memory", "abyss-machine memory status --json", "memory", "bridge", "memory", requires_ok=False),
    CycleArtifactStepSpec("mode", "abyss-machine mode status --json", "mode", "bridge", "mode", requires_ok=False),
    CycleArtifactStepSpec("resource", "abyss-machine resource status --json", "resource", "bridge", "resource", requires_ok=False),
    CycleArtifactStepSpec("processes", "abyss-machine processes latest --json", "processes", "bridge", "processes", requires_ok=False),
    CycleArtifactStepSpec("process_containers", "abyss-machine processes containers --json", "process_containers", "bridge", "process_containers", requires_ok=False),
    CycleArtifactStepSpec("process_thermal_plan", "abyss-machine processes thermal-plan --seconds 3 --interval 0.5 --json", "process_thermal_plan", "bridge", "process_thermal_plan", requires_ok=False),
    CycleArtifactStepSpec("cooling", "abyss-machine cooling status --json", "cooling", "bridge", "cooling", requires_ok=False),
    CycleArtifactStepSpec("typing_events", "abyss-machine typing latest --json", "typing_events", "bridge", "typing_events", requires_ok=False),
    CycleArtifactStepSpec("typing_validate", "abyss-machine typing validate --json", "typing_validate", "bridge", "typing_validate", requires_ok=False),
    CycleArtifactStepSpec("nervous_brief", "abyss-machine nervous brief --scope now --json", "nervous_brief", "bridge", "nervous_brief", requires_ok=False),
    CycleArtifactStepSpec("investigate", "abyss-machine self-awareness investigate --query RUN_ID --json", "investigate", "direct", "investigation"),
    CycleArtifactStepSpec("replay", "abyss-machine self-awareness replay --thread-id THREAD_ID --json", "replay", "direct", "replay"),
    CycleArtifactStepSpec("brief", "abyss-machine self-awareness brief --json", "brief", "direct", "brief"),
    CycleArtifactStepSpec("reactions", "abyss-machine reactions --json", "reactions", "direct", "reactions"),
    CycleArtifactStepSpec("responses", "abyss-machine responses --json", "responses", "direct", "responses"),
)

CYCLE_FINAL_ARTIFACT_STEP_SPECS: tuple[CycleArtifactStepSpec, ...] = (
    CycleArtifactStepSpec("autolink", "abyss-machine self-awareness autolink --json", "autolink", "direct", "autolink"),
    CycleArtifactStepSpec("export", "abyss-machine self-awareness export --json", "export", "direct", "export"),
)

COMPLETION_AUDIT_SCHEMA_SUFFIX = "self_awareness_completion_audit_v1"


def _spec(schema_prefix: str, paths: Mapping[str, Path], name: str, suffix: str) -> SelfAwarenessLatestSpec:
    try:
        path = paths[name]
    except KeyError as exc:
        raise KeyError(f"missing self-awareness latest path for {name}") from exc
    return SelfAwarenessLatestSpec(name=name, path=Path(path), schema=f"{schema_prefix}_{suffix}")


def readmodel_latest_specs(
    *,
    schema_prefix: str,
    paths: Mapping[str, Path],
    include_cycle: bool = True,
) -> tuple[SelfAwarenessLatestSpec, ...]:
    return tuple(
        _spec(schema_prefix, paths, name, suffix)
        for name, suffix in READMODEL_SCHEMA_SUFFIXES
        if include_cycle or name != "cycle"
    )


def completion_audit_latest_spec(
    *,
    schema_prefix: str,
    paths: Mapping[str, Path],
) -> SelfAwarenessLatestSpec:
    return _spec(schema_prefix, paths, "completion_audit", COMPLETION_AUDIT_SCHEMA_SUFFIX)


def status_latest_specs(
    *,
    schema_prefix: str,
    paths: Mapping[str, Path],
    include_cycle: bool = True,
) -> tuple[SelfAwarenessLatestSpec, ...]:
    return readmodel_latest_specs(
        schema_prefix=schema_prefix,
        paths=paths,
        include_cycle=include_cycle,
    ) + (completion_audit_latest_spec(schema_prefix=schema_prefix, paths=paths),)


def validation_latest_specs(
    *,
    schema_prefix: str,
    paths: Mapping[str, Path],
    require_cycle: bool = True,
) -> tuple[SelfAwarenessLatestSpec, ...]:
    specs = [
        _spec(schema_prefix, paths, name, suffix)
        for name, suffix in READMODEL_SCHEMA_SUFFIXES
        if name not in {"cycle", "validate", "probe"}
    ]
    specs.append(completion_audit_latest_spec(schema_prefix=schema_prefix, paths=paths))
    specs.append(_spec(schema_prefix, paths, "probe", "self_awareness_probe_v1"))
    if require_cycle:
        specs.append(_spec(schema_prefix, paths, "cycle", "self_awareness_cycle_v1"))
    return tuple(specs)


def load_latest_documents(
    specs: tuple[SelfAwarenessLatestSpec, ...],
    *,
    load_latest_json: LatestJsonReaderPort,
) -> dict[str, dict[str, Any]]:
    return {spec.name: load_latest_json(spec.path, spec.schema) for spec in specs}


def cycle_latest_specs(
    *,
    schema_prefix: str,
    paths: Mapping[str, Path],
) -> tuple[SelfAwarenessLatestSpec, ...]:
    suffixes = dict(READMODEL_SCHEMA_SUFFIXES)
    return tuple(
        _spec(schema_prefix, paths, name, suffixes[name])
        for name in CYCLE_LATEST_READ_NAMES
    )


def load_cycle_latest_documents(
    *,
    schema_prefix: str,
    paths: Mapping[str, Path],
    load_latest_json: LatestJsonReaderPort,
) -> dict[str, dict[str, Any]]:
    return load_latest_documents(
        cycle_latest_specs(schema_prefix=schema_prefix, paths=paths),
        load_latest_json=load_latest_json,
    )


def load_cycle_bridge_documents(
    surfaces: Iterable[Mapping[str, Any]],
    *,
    load_latest_json: LatestJsonReaderPort,
) -> dict[str, dict[str, Any]]:
    documents: dict[str, dict[str, Any]] = {}
    for surface in surfaces:
        documents[str(surface["id"])] = load_latest_json(Path(surface["path"]), str(surface["schema"]))
    return documents


def _public_value(value: Any, *, depth: int = 0, max_depth: int = 5, max_items: int = 80) -> Any:
    if depth >= max_depth:
        return self_awareness_contracts.bounded_json_shape(value, depth=0, max_depth=1, max_items=12)
    if isinstance(value, dict):
        return {
            str(key): _public_value(item, depth=depth + 1, max_depth=max_depth, max_items=max_items)
            for key, item in list(value.items())[:max_items]
        }
    if isinstance(value, list):
        return [
            _public_value(item, depth=depth + 1, max_depth=max_depth, max_items=max_items)
            for item in value[:max_items]
        ]
    if isinstance(value, str):
        return self_awareness_contracts.redact_text(value, limit=500)
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return self_awareness_contracts.redact_text(value, limit=200)


def latest_summary(spec: SelfAwarenessLatestSpec, document: dict[str, Any]) -> dict[str, Any]:
    summary = document.get("summary") if isinstance(document.get("summary"), dict) else None
    return {
        "path": str(spec.path),
        "ok": document.get("ok"),
        "schema": document.get("schema"),
        "generated_at": document.get("generated_at"),
        "summary": _public_value(summary) if summary is not None else None,
        "error": self_awareness_contracts.redact_text(document.get("error"), limit=500) if document.get("error") else None,
    }


def latest_summary_map(
    specs: tuple[SelfAwarenessLatestSpec, ...],
    documents: Mapping[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        spec.name: latest_summary(spec, documents.get(spec.name, {}))
        for spec in specs
    }


def missing_latest_document_names(documents: Mapping[str, dict[str, Any]]) -> list[str]:
    return [
        name
        for name, document in documents.items()
        if isinstance(document, dict) and not document.get("ok") and document.get("error")
    ]


def body_closure_status_document(
    *,
    heartbeat: Mapping[str, Any],
    reactions: Mapping[str, Any],
    responses: Mapping[str, Any],
    doctor: Mapping[str, Any],
    topology: Mapping[str, Any],
    stack_bridge: Mapping[str, Any],
    changes: Mapping[str, Any],
    nervous_brief: Mapping[str, Any],
    backup: Mapping[str, Any],
    latest_paths: Mapping[str, Path | str],
    schema_prefix: str,
    backup_plane_active_change: BackupPlaneActiveChangePort,
    backup_plane_blockers: BackupPlaneBlockersPort,
) -> dict[str, Any]:
    watch_sources: list[dict[str, Any]] = []

    def latest_path(name: str) -> str:
        return str(latest_paths.get(name) or "")

    def add_source(kind: str, status: str, evidence: dict[str, Any]) -> None:
        watch_sources.append({"kind": kind, "status": status, "evidence": evidence})

    heartbeat_status = str(_nested_get(heartbeat, ["summary", "status"]) or heartbeat.get("status") or "")
    if heartbeat_status and heartbeat_status not in {"steady", "linked", "ok", "ready"}:
        add_source("heartbeat", heartbeat_status, {"path": latest_path("heartbeat"), "summary": heartbeat.get("summary")})

    reaction_candidates = _safe_int(_nested_get(reactions, ["summary", "candidates"]), 0)
    reaction_status = str(_nested_get(reactions, ["summary", "status"]) or reactions.get("status") or "")
    if reaction_candidates > 0:
        add_source(
            "reactions",
            reaction_status or "open",
            {
                "path": latest_path("reactions"),
                "candidates": reaction_candidates,
                "by_category": _nested_get(reactions, ["summary", "by_category"]),
            },
        )

    response_routes = _safe_int(_nested_get(responses, ["summary", "routes"]), 0)
    response_status = str(_nested_get(responses, ["summary", "status"]) or responses.get("status") or "")
    if response_routes > 0:
        add_source(
            "responses",
            response_status or "open",
            {
                "path": latest_path("responses"),
                "routes": response_routes,
                "by_category": _nested_get(responses, ["summary", "by_category"]),
            },
        )

    doctor_warnings = _safe_int(_nested_get(doctor, ["summary", "warnings"]), 0)
    doctor_fails = _safe_int(_nested_get(doctor, ["summary", "fails"]), 0)
    if doctor_warnings > 0 or doctor_fails > 0:
        add_source(
            "doctor",
            str(_nested_get(doctor, ["summary", "status"]) or "warn"),
            {"path": latest_path("doctor"), "warnings": doctor_warnings, "fails": doctor_fails},
        )

    topology_warnings = _safe_int(_nested_get(topology, ["summary", "warnings"]), 0)
    topology_fails = _safe_int(_nested_get(topology, ["summary", "fails"]), 0)
    if topology_warnings > 0 or topology_fails > 0:
        add_source(
            "topology",
            str(_nested_get(topology, ["summary", "status"]) or "warn"),
            {"path": latest_path("topology"), "warnings": topology_warnings, "fails": topology_fails},
        )

    stack_bridge_warnings = _safe_int(_nested_get(stack_bridge, ["summary", "warnings"]), 0)
    stack_bridge_fails = _safe_int(_nested_get(stack_bridge, ["summary", "fails"]), 0)
    if stack_bridge_warnings > 0 or stack_bridge_fails > 0:
        add_source(
            "stack_bridge",
            str(_nested_get(stack_bridge, ["summary", "status"]) or "warn"),
            {"path": latest_path("stack_bridge"), "warnings": stack_bridge_warnings, "fails": stack_bridge_fails},
        )

    active_changes = _safe_int(_nested_get(changes, ["summary", "active_records"]), 0)
    if active_changes > 0:
        add_source("changes", "active", {"path": latest_path("changes"), "active_records": active_changes})

    readiness = nervous_brief.get("readiness") if isinstance(nervous_brief.get("readiness"), Mapping) else {}
    nervous_status = str(readiness.get("status") or "")
    if nervous_status and nervous_status not in {"ready", "ok"}:
        add_source("nervous", nervous_status, {"path": latest_path("nervous_brief"), "readiness": readiness})

    backup_blockers: list[str] = []
    if backup_plane_active_change(changes):
        backup_blockers = backup_plane_blockers(backup)
        if backup_blockers:
            add_source("backup", "blocked", {"path": latest_path("backup"), "blockers": backup_blockers})

    body_status = "ready" if not watch_sources else "watch"
    return {
        "schema": f"{schema_prefix}_self_awareness_body_closure_v1",
        "status": body_status,
        "complete": body_status == "ready",
        "watch_sources": watch_sources,
        "summary": {
            "watch_sources": len(watch_sources),
            "reaction_candidates": reaction_candidates,
            "response_routes": response_routes,
            "doctor_warnings": doctor_warnings,
            "doctor_fails": doctor_fails,
            "topology_warnings": topology_warnings,
            "topology_fails": topology_fails,
            "stack_bridge_warnings": stack_bridge_warnings,
            "stack_bridge_fails": stack_bridge_fails,
            "active_changes": active_changes,
            "nervous_status": nervous_status or None,
            "backup_blockers": backup_blockers,
        },
        "policy": {
            "read_model": True,
            "does_not_refresh": True,
            "does_not_execute_commands": True,
            "host_layer_mutates_stack": False,
            "separates_stack_usage_from_body_closure": True,
        },
    }


def http_status_with_headers(
    url: str,
    headers: Mapping[str, str],
    *,
    request_factory: HttpRequestFactoryPort,
    urlopen: HttpOpenPort,
    clock: ClockPort,
    timeout: float = 2.5,
    max_bytes: int = 65536,
) -> dict[str, Any]:
    started = clock()
    try:
        request = request_factory(url, dict(headers), "GET")
        with urlopen(request, timeout) as response:
            raw = response.read(max_bytes + 1)
            truncated = len(raw) > max_bytes
            if truncated:
                raw = raw[:max_bytes]
            text = raw.decode("utf-8", errors="replace")
            status_code = getattr(response, "status", None)
            try:
                status_int = int(status_code)
            except (TypeError, ValueError):
                status_int = None
            response_headers = getattr(response, "headers", {})
            header_get = getattr(response_headers, "get", None)
            return {
                "ok": bool(status_int is not None and 200 <= status_int < 300),
                "url": url,
                "status_code": status_code,
                "elapsed_ms": round((clock() - started) * 1000.0, 1),
                "content_type": header_get("content-type") if callable(header_get) else None,
                "truncated": truncated,
                "text_preview": self_awareness_contracts.redact_text(text, 300),
            }
    except Exception as exc:
        payload: dict[str, Any] = {
            "ok": False,
            "url": url,
            "elapsed_ms": round((clock() - started) * 1000.0, 1),
            "error": self_awareness_contracts.redact_text(str(exc), 500),
        }
        status_code = getattr(exc, "code", None)
        if status_code is not None:
            payload["status_code"] = status_code
        return payload


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def tcp_probe(
    service: str,
    host: str,
    port: int,
    *,
    tcp_connect: TcpConnectPort,
    clock: ClockPort,
    timeout: float = 1.2,
) -> dict[str, Any]:
    started = clock()
    ok = False
    error = None
    try:
        tcp_connect(host, int(port), timeout)
        ok = True
    except OSError as exc:
        error = str(exc)
    return {
        "service": service,
        "probe": f"tcp:{host}:{port}",
        "kind": "tcp_ready",
        "ok": ok,
        "url": f"tcp://{host}:{port}",
        "elapsed_ms": round((clock() - started) * 1000.0, 1),
        "error": error,
        "body_stored": False,
        "raw_private_content": False,
    }


def working_stack_endpoint_probes(
    *,
    http_specs: Iterable[WorkingStackEndpointProbeSpec],
    tcp_specs: Iterable[WorkingStackTcpProbeSpec],
    http_json: HttpJsonPort,
    http_status: HttpStatusPort,
    tcp_connect: TcpConnectPort,
    clock: ClockPort,
    enabled: bool = True,
) -> list[dict[str, Any]]:
    if not enabled:
        return []
    probes: list[dict[str, Any]] = []
    for spec in http_specs:
        kind = spec.kind
        if kind == "http_status":
            response = http_status(spec.url, spec.timeout, spec.max_bytes)
        else:
            kind = "http_json"
            response = http_json(spec.url, spec.timeout, spec.max_bytes)
        probes.append({
            "service": spec.service,
            "probe": spec.probe,
            **self_awareness_contracts.http_probe_summary(response, kind),
        })
    for spec in tcp_specs:
        probes.append(tcp_probe(
            spec.service,
            spec.host,
            spec.port,
            tcp_connect=tcp_connect,
            clock=clock,
            timeout=spec.timeout,
        ))
    return probes


_CONTAINER_HTTP_PROBE_SCRIPT = r'''
import hashlib, json, sys, time, urllib.error, urllib.parse, urllib.request

url = sys.argv[1]
method = sys.argv[2].upper()
payload = sys.argv[3]
timeout = float(sys.argv[4])
max_bytes = int(sys.argv[5])

def compact_shape(value):
    if isinstance(value, dict):
        shape = {"type": "dict", "keys": sorted(str(key) for key in value.keys())[:32]}
        if isinstance(value.get("ok"), bool):
            shape["ok"] = value.get("ok")
        if isinstance(value.get("results"), list):
            results = value.get("results") or []
            shape["results"] = {
                "type": "list",
                "length": len(results),
                "item_keys": sorted(str(key) for key in results[0].keys())[:16] if results and isinstance(results[0], dict) else [],
            }
        if isinstance(value.get("url"), str):
            parsed = urllib.parse.urlparse(value.get("url"))
            shape["url_scheme"] = parsed.scheme
            shape["url_host_hash"] = hashlib.sha256((parsed.hostname or "").encode()).hexdigest()[:16]
        if isinstance(value.get("title"), str):
            shape["title_hash"] = hashlib.sha256(value.get("title", "").encode()).hexdigest()[:16]
        if isinstance(value.get("text"), str):
            text = value.get("text", "")
            shape["text_chars"] = len(text)
            shape["text_hash"] = hashlib.sha256(text.encode()).hexdigest()[:16]
        return shape
    if isinstance(value, list):
        return {"type": "list", "length": len(value)}
    return {"type": type(value).__name__}

headers = {"Accept": "application/json"}
data = None
if payload and payload != "null":
    data = payload.encode("utf-8")
    headers["Content-Type"] = "application/json"
started = time.monotonic()
result = {"url": url, "method": method}
try:
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read(max_bytes + 1)
        truncated = len(body) > max_bytes
        body = body[:max_bytes]
        text = body.decode("utf-8", "replace")
        result.update({
            "ok": 200 <= int(response.status) < 400,
            "status_code": int(response.status),
            "elapsed_ms": round((time.monotonic() - started) * 1000.0, 1),
            "truncated": truncated,
            "content_hash": hashlib.sha256(body).hexdigest()[:24],
        })
        try:
            result["json_shape"] = compact_shape(json.loads(text))
        except Exception:
            result["text_preview_hash"] = hashlib.sha256(text[:512].encode()).hexdigest()[:16]
except urllib.error.HTTPError as exc:
    body = exc.read(max_bytes)
    text = body.decode("utf-8", "replace")
    result.update({
        "ok": False,
        "status_code": int(exc.code),
        "elapsed_ms": round((time.monotonic() - started) * 1000.0, 1),
        "truncated": False,
        "error": str(exc),
        "content_hash": hashlib.sha256(body).hexdigest()[:24],
    })
    try:
        result["json_shape"] = compact_shape(json.loads(text))
    except Exception:
        result["text_preview_hash"] = hashlib.sha256(text[:512].encode()).hexdigest()[:16]
except Exception as exc:
    result.update({
        "ok": False,
        "status_code": None,
        "elapsed_ms": round((time.monotonic() - started) * 1000.0, 1),
        "truncated": False,
        "error": str(exc)[:400],
    })
print(json.dumps(result, sort_keys=True))
'''


def container_http_probe(
    service: str,
    container: str,
    probe: str,
    url: str,
    *,
    command_exists: CommandExistsPort,
    run_command: RunCommandPort,
    clock: ClockPort,
    method: str = "GET",
    request_json: dict[str, Any] | None = None,
    timeout: float = 4.0,
    max_bytes: int = 65536,
    expected_statuses: set[int] | None = None,
) -> dict[str, Any]:
    started = clock()
    if not command_exists("podman"):
        return {
            "service": service,
            "probe": probe,
            "container": container,
            "kind": "container_http_json",
            "ok": False,
            "url": url,
            "method": method.upper(),
            "error": "podman is not installed",
            "body_stored": False,
            "raw_private_content": False,
        }
    expected = expected_statuses or set(range(200, 400))
    payload = json.dumps(request_json, sort_keys=True) if request_json is not None else "null"
    out = run_command(
        ["podman", "exec", container, "python", "-c", _CONTAINER_HTTP_PROBE_SCRIPT, url, method.upper(), payload, str(float(timeout)), str(int(max_bytes))],
        timeout + 8.0,
    )
    if not out.get("ok"):
        return {
            "service": service,
            "probe": probe,
            "container": container,
            "kind": "container_http_json",
            "ok": False,
            "url": url,
            "method": method.upper(),
            "elapsed_ms": round((clock() - started) * 1000.0, 1),
            "error": self_awareness_contracts.redact_text(str(out.get("stderr") or out.get("stdout") or "podman exec failed"), 400),
            "returncode": out.get("returncode"),
            "body_stored": False,
            "raw_private_content": False,
            "policy": {
                "host_layer_mutates_stack": False,
                "writes_project_roots": False,
                "response_body_stored": False,
            },
        }
    try:
        response = json.loads(str(out.get("stdout") or "{}"))
    except json.JSONDecodeError as exc:
        response = {
            "ok": False,
            "error": f"invalid container probe JSON: {exc}",
            "elapsed_ms": round((clock() - started) * 1000.0, 1),
        }
    status_code = _safe_int(response.get("status_code"), 0)
    response["ok"] = bool(status_code in expected) if status_code else bool(response.get("ok"))
    return {
        "service": service,
        "probe": probe,
        "container": container,
        **self_awareness_contracts.http_probe_summary(response, "container_http_json"),
        "method": method.upper(),
        "expected_status_codes": sorted(expected),
        "raw_http_ok": bool(response.get("ok")) if status_code in set(range(200, 400)) else None,
        "content_hash": response.get("content_hash"),
        "execution_route": "podman_exec_container_loopback_http",
        "policy": {
            "semantic_read_only": True,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "response_body_stored": False,
            "raw_private_content": False,
        },
    }


def container_python_smoke(
    service: str,
    container: str,
    probe: str,
    script: str,
    *,
    run_command: RunCommandPort,
    clock: ClockPort,
    timeout: float = 10.0,
) -> dict[str, Any]:
    started = clock()
    out = run_command(["podman", "exec", container, "python", "-c", script], timeout)
    stdout = str(out.get("stdout") or "")
    stderr = str(out.get("stderr") or "")
    error_text = stderr or "container runtime smoke failed"
    return {
        "service": service,
        "probe": probe,
        "container": container,
        "kind": "container_runtime_smoke",
        "ok": bool(out.get("ok")),
        "url": f"container://{container}/{probe}",
        "elapsed_ms": round((clock() - started) * 1000.0, 1),
        "returncode": out.get("returncode"),
        "stdout_hash": self_awareness_contracts.stable_hash_json(stdout, length=16) if stdout else None,
        "stderr_hash": self_awareness_contracts.stable_hash_json(stderr, length=16) if stderr else None,
        "error": self_awareness_contracts.redact_text(error_text, 400) if not out.get("ok") else None,
        "body_stored": False,
        "raw_private_content": False,
        "execution_route": "podman_exec_container_runtime_smoke",
        "policy": {
            "semantic_read_only": True,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "response_body_stored": False,
            "raw_private_content": False,
        },
    }


def working_stack_container_tool_probes(
    runtime_by_service: Mapping[str, dict[str, Any]],
    *,
    command_exists: CommandExistsPort,
    run_command: RunCommandPort,
    clock: ClockPort,
    enabled: bool = True,
) -> list[dict[str, Any]]:
    if not enabled:
        return []
    probes: list[dict[str, Any]] = []

    def container_for(service: str) -> str | None:
        runtime = runtime_by_service.get(service) if isinstance(runtime_by_service.get(service), dict) else {}
        if not runtime.get("running"):
            return None
        return str(runtime.get("container") or runtime.get("service") or "").strip() or None

    docs_container = container_for("docs-api")
    if docs_container:
        probes.append(container_http_probe(
            "docs-api",
            docs_container,
            "health",
            "http://127.0.0.1:5000/health",
            command_exists=command_exists,
            run_command=run_command,
            clock=clock,
            timeout=3.0,
        ))
        probes.append(container_http_probe(
            "docs-api",
            docs_container,
            "search:n8n-workflow",
            "http://127.0.0.1:5000/search?q=workflow",
            command_exists=command_exists,
            run_command=run_command,
            clock=clock,
            timeout=4.0,
        ))

    browser_container = container_for("aoa-browser")
    if browser_container:
        probes.append(container_http_probe(
            "aoa-browser",
            browser_container,
            "health",
            "http://127.0.0.1:8000/health",
            command_exists=command_exists,
            run_command=run_command,
            clock=clock,
            timeout=3.0,
        ))
        probes.append(container_http_probe(
            "aoa-browser",
            browser_container,
            "private-host-guard",
            "http://127.0.0.1:8000/read",
            command_exists=command_exists,
            run_command=run_command,
            clock=clock,
            method="POST",
            request_json={"url": "http://127.0.0.1:8000/health", "wait_ms": 50, "max_chars": 100},
            timeout=6.0,
            expected_statuses={403},
        ))
        probes.append(container_python_smoke(
            "aoa-browser",
            browser_container,
            "playwright-chromium-launch",
            "from playwright.sync_api import sync_playwright\nwith sync_playwright() as p:\n    browser = p.chromium.launch(headless=True)\n    browser.close()\nprint('launch_ok')",
            run_command=run_command,
            clock=clock,
            timeout=18.0,
        ))

    return probes


def parse_tts_smoke_sidecar(text: str) -> Any:
    if yaml is not None:
        return yaml.safe_load(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        parsed: dict[str, str] = {}
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or ":" not in stripped:
                continue
            key, value = stripped.split(":", 1)
            key = key.strip()
            if not key:
                continue
            parsed[key] = value.strip().strip("'\"")
        return parsed


def read_wav_format(path: Path) -> dict[str, Any]:
    with wave.open(str(path), "rb") as wav:
        return {
            "channels": wav.getnchannels(),
            "sample_width": wav.getsampwidth(),
            "framerate": wav.getframerate(),
            "frames": wav.getnframes(),
        }


def _safe_stat(path: Path, *, path_stat: PathStatPort) -> Any | None:
    try:
        return path_stat(path)
    except OSError:
        return None


def _relative_or_name(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return path.name


def working_stack_tts_smoke_evidence(
    stack_root: Path,
    *,
    schema_prefix: str,
    now: ClockPort,
    path_exists: PathExistsPort,
    path_is_file: PathIsFilePort,
    path_glob: PathGlobPort,
    path_read_text: PathReadTextPort,
    path_stat: PathStatPort,
    sidecar_loads: SidecarDocumentLoaderPort = parse_tts_smoke_sidecar,
    wav_format_reader: WavFormatReaderPort = read_wav_format,
    max_age_seconds: int = 24 * 60 * 60,
    max_sidecars: int = 64,
) -> dict[str, Any]:
    tts_log_root = Path(stack_root) / "Logs" / "tts"
    base = {
        "schema": f"{schema_prefix}_self_awareness_working_stack_tts_smoke_evidence_v1",
        "ok": False,
        "root": str(tts_log_root),
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "raw_text_stored": False,
            "raw_audio_stored": False,
        },
    }
    if not path_exists(tts_log_root):
        return {**base, "reason": "tts_log_root_missing"}

    sidecars: list[tuple[float, Path]] = []
    try:
        candidates = path_glob(tts_log_root, "**/*.json")
    except OSError:
        candidates = []
    for path in candidates:
        if not path_is_file(path):
            continue
        stat_result = _safe_stat(path, path_stat=path_stat)
        sidecars.append((float(getattr(stat_result, "st_mtime", 0.0) or 0.0), Path(path)))
    sidecars.sort(key=lambda item: item[0], reverse=True)

    now_ts = now()
    for _, sidecar in sidecars[:max_sidecars]:
        try:
            parsed = sidecar_loads(path_read_text(sidecar))
        except Exception:
            continue
        if not isinstance(parsed, dict):
            continue
        model_id = str(parsed.get("model_id") or "")
        saved_path = str(parsed.get("saved_path") or "")
        if "Qwen3-TTS" not in model_id or not saved_path:
            continue
        wav_path = sidecar.with_suffix(".wav")
        if not path_exists(wav_path):
            continue
        sidecar_stat = _safe_stat(sidecar, path_stat=path_stat)
        wav_stat = _safe_stat(wav_path, path_stat=path_stat)
        if sidecar_stat is None or wav_stat is None:
            continue
        age_seconds = max(0.0, now_ts - max(float(sidecar_stat.st_mtime), float(wav_stat.st_mtime)))
        if age_seconds > max_age_seconds:
            continue
        try:
            wav_format = wav_format_reader(wav_path)
        except (OSError, EOFError, wave.Error):
            continue
        if getattr(wav_stat, "st_size", 0) <= 44 or _safe_int(wav_format.get("frames"), 0) <= 0:
            continue
        return {
            **base,
            "ok": True,
            "sidecar_path": str(sidecar),
            "wav_path": str(wav_path),
            "age_seconds": round(age_seconds, 1),
            "wav_bytes": wav_stat.st_size,
            "wav_format": wav_format,
            "sidecar": {
                "agent_id": parsed.get("agent_id"),
                "voice_id": parsed.get("voice_id"),
                "model_id": model_id,
                "language": parsed.get("language"),
                "speaker": parsed.get("speaker"),
                "saved_path": saved_path,
                "host_rel_path": _relative_or_name(wav_path, tts_log_root),
                "text_hash": self_awareness_contracts.stable_hash_json(str(parsed.get("text") or ""), length=16) if parsed.get("text") else None,
                "ts": parsed.get("ts"),
            },
            "evidence_refs": [
                {"path": str(sidecar), "schema": "tts_router_sidecar_yaml", "service": "tts-router"},
                {"path": str(wav_path), "schema": "riff_wav_audio", "service": "qwen-tts"},
            ],
        }
    return {**base, "reason": "fresh_qwen_tts_sidecar_wav_pair_missing"}


def working_stack_tts_smoke_probes(
    *,
    evidence: dict[str, Any],
    enabled: bool = True,
) -> list[dict[str, Any]]:
    if not enabled or evidence.get("ok") is not True:
        return []
    probes: list[dict[str, Any]] = []
    for service in ("qwen-tts", "tts-router"):
        probes.append({
            "service": service,
            "probe": "tts-synthesis-artifact",
            "kind": "artifact_receipt",
            "ok": True,
            "url": f"file://{evidence.get('wav_path')}",
            "body_stored": False,
            "raw_private_content": False,
            "semantic_read_only": True,
            "evidence": evidence,
            "evidence_refs": evidence.get("evidence_refs") if isinstance(evidence.get("evidence_refs"), list) else [],
            "policy": evidence.get("policy"),
        })
    return probes


def env_int(name: str, default: int, *, env_get: EnvGetPort) -> int:
    raw = env_get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def env_float(name: str, default: float, *, env_get: EnvGetPort) -> float:
    raw = env_get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def proc_meminfo_bytes(*, read_text: MeminfoTextReaderPort) -> dict[str, int]:
    values: dict[str, int] = {}
    try:
        lines = read_text().splitlines()
    except OSError:
        return {}
    for line in lines:
        parts = line.split()
        if len(parts) >= 2 and parts[0].endswith(":"):
            key = parts[0].rstrip(":")
            try:
                values[key] = int(parts[1]) * 1024
            except ValueError:
                continue
    return values


def stack_owned_source_ref(path: Path, kind: str, **extra: Any) -> dict[str, Any]:
    return {
        "path": str(path),
        "kind": kind,
        "owner_surface": "abyss-stack",
        "read_only": True,
        "host_layer_mutates_stack": False,
        **extra,
    }


def normalize_stack_service_name(value: Any) -> str:
    name = str(value or "").strip().lstrip("/")
    if not name:
        return ""
    if name.startswith("abyss_") and name.endswith("_1"):
        name = name[len("abyss_"):-2]
    name = name.replace("_", "-")
    aliases = {
        "qwen-tts-api": "qwen-tts",
        "tts-router": "tts-router",
        "tts-router-api": "tts-router",
        "babelvox-tts-api": "babelvox-tts",
        "langchain-api-llamacpp": "langchain-api-llamacpp",
    }
    return aliases.get(name, name)


def service_from_container(item: Mapping[str, Any]) -> str:
    compose = item.get("compose") if isinstance(item.get("compose"), Mapping) else {}
    service = normalize_stack_service_name(compose.get("service"))
    if service:
        return service
    names = item.get("names") if isinstance(item.get("names"), list) else []
    for name in [item.get("name"), *names]:
        service = normalize_stack_service_name(name)
        if service:
            return service
    return "unknown"


def working_stack_service_selection_policy(
    *,
    schema_prefix: str,
    stack_paths: Mapping[str, Any],
    path_exists: PathExistsPort,
    load_json_document: JsonDocumentLoaderPort,
) -> dict[str, Any]:
    candidates: list[tuple[str, Path]] = []
    srv_root = stack_paths.get("srv_abyss_stack")
    source_root = stack_paths.get("source_abyss_stack")
    if srv_root:
        candidates.append((
            "runtime_configs",
            Path(str(srv_root)) / "Configs" / "docs" / "runtime" / "service-selection-policy.v1.json",
        ))
    if source_root:
        candidates.append((
            "source_checkout",
            Path(str(source_root)) / "docs" / "runtime" / "service-selection-policy.v1.json",
        ))

    services: dict[str, dict[str, Any]] = {}
    documents: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for origin, path in candidates:
        if not path_exists(path):
            continue
        loaded, error = load_json_document(path)
        if error or not isinstance(loaded, dict):
            errors.append({"path": str(path), "origin": origin, "error": error or "not_json_object"})
            continue
        raw_services = loaded.get("services") if isinstance(loaded.get("services"), list) else []
        documents.append({
            "path": str(path),
            "origin": origin,
            "schema": loaded.get("schema"),
            "updated_at": loaded.get("updated_at"),
            "service_count": len(raw_services),
            "source_ref": stack_owned_source_ref(path, "service_selection_policy", origin=origin),
        })
        for row in raw_services:
            if not isinstance(row, dict):
                continue
            service = normalize_stack_service_name(row.get("name") or row.get("service"))
            if not service or service in services:
                continue
            services[service] = {
                "schema": f"{schema_prefix}_self_awareness_working_stack_service_selection_entry_v1",
                "service": service,
                "posture": row.get("posture"),
                "tier": row.get("tier"),
                "owner_profile": row.get("owner_profile"),
                "module": row.get("module"),
                "resource_guard": row.get("resource_guard"),
                "decision": row.get("decision"),
                "policy_origin": origin,
                "source_ref": stack_owned_source_ref(path, "service_selection_policy", origin=origin, service=service),
            }

    return {
        "schema": f"{schema_prefix}_self_awareness_working_stack_service_selection_policy_v1",
        "ok": bool(services),
        "documents": documents,
        "services": services,
        "summary": {
            "documents": len(documents),
            "services": len(services),
            "errors": len(errors),
            "policy_deferred_postures": self_awareness_contracts.working_stack_policy_deferred_postures(),
        },
        "errors": errors,
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "policy_interprets_declared_runtime_expectation": True,
        },
    }


def stack_compose_module_roots(
    stack_paths: Mapping[str, Any],
    *,
    path_exists: PathExistsPort,
    path_is_dir: PathIsDirPort,
) -> list[Path]:
    roots: list[Path] = []
    for key, suffix in [
        ("source_abyss_stack", ("compose", "modules")),
        ("srv_abyss_stack", ("Configs", "compose", "modules")),
    ]:
        root_text = stack_paths.get(key)
        if not root_text:
            continue
        root = Path(str(root_text))
        for part in suffix:
            root = root / part
        if path_exists(root) and path_is_dir(root):
            roots.append(root)
    return roots


def parse_compose_services(path: Path, *, read_text: PathReadTextPort) -> list[str]:
    try:
        lines = read_text(path).splitlines()
    except OSError:
        return []
    in_services = False
    services_indent = 0
    child_indent: int | None = None
    services: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if not in_services:
            if re.match(r"^services\s*:\s*(?:#.*)?$", stripped):
                in_services = True
                services_indent = indent
                child_indent = None
            continue
        if indent <= services_indent:
            in_services = False
            child_indent = None
            if re.match(r"^services\s*:\s*(?:#.*)?$", stripped):
                in_services = True
                services_indent = indent
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)\s*:\s*(?:#.*)?$", stripped)
        if not match:
            continue
        if child_indent is None:
            child_indent = indent
        if indent != child_indent:
            continue
        service = normalize_stack_service_name(match.group(1))
        if service and not service.startswith("x-") and service not in services:
            services.append(service)
    return services


def stack_compose_service_inventory(
    *,
    schema_prefix: str,
    stack_paths: Mapping[str, Any],
    path_exists: PathExistsPort,
    path_is_dir: PathIsDirPort,
    path_glob: PathGlobPort,
    read_text: PathReadTextPort,
) -> dict[str, Any]:
    rows_by_service: dict[str, dict[str, Any]] = {}
    module_refs: list[dict[str, Any]] = []
    roots = stack_compose_module_roots(
        stack_paths,
        path_exists=path_exists,
        path_is_dir=path_is_dir,
    )
    for root in roots:
        for path in sorted(path_glob(root, "*.yml")):
            services = parse_compose_services(path, read_text=read_text)
            ref = stack_owned_source_ref(
                path,
                "compose_module",
                module=path.name,
                services=services,
            )
            module_refs.append(ref)
            for service in services:
                row = rows_by_service.setdefault(service, {
                    "service": service,
                    "declared": True,
                    "modules": [],
                    "stack_source_refs": [],
                })
                row["modules"].append(path.name)
                row["stack_source_refs"].append(ref)
    rows = sorted(rows_by_service.values(), key=lambda item: str(item.get("service") or ""))
    return {
        "schema": f"{schema_prefix}_self_awareness_working_stack_compose_inventory_v1",
        "ok": bool(rows),
        "services": rows,
        "module_refs": module_refs,
        "summary": {
            "module_roots": len(roots),
            "modules": len(module_refs),
            "declared_services": len(rows),
        },
    }


def stack_service_root_inventory(
    *,
    schema_prefix: str,
    stack_paths: Mapping[str, Any],
    path_exists: PathExistsPort,
    path_is_dir: PathIsDirPort,
    path_iterdir: PathIterdirPort,
) -> dict[str, Any]:
    candidate_roots = [
        Path(str(stack_paths.get("srv_abyss_stack") or "")) / "Services",
        Path(str(stack_paths.get("source_abyss_stack") or "")) / "Services",
    ]
    rows: list[dict[str, Any]] = []
    for root in candidate_roots:
        if not path_exists(root) or not path_is_dir(root):
            continue
        try:
            children = sorted(item for item in path_iterdir(root) if path_is_dir(item))
        except OSError:
            children = []
        for path in children:
            service = normalize_stack_service_name(path.name)
            rows.append({
                "service": service,
                "name": path.name,
                "present": True,
                "stack_source_refs": [stack_owned_source_ref(path, "service_root", service=service)],
            })
    rows = sorted(
        rows,
        key=lambda item: (
            str(item.get("service") or ""),
            str(((item.get("stack_source_refs") or [{}])[0] or {}).get("path") or ""),
        ),
    )
    return {
        "schema": f"{schema_prefix}_self_awareness_working_stack_service_root_inventory_v1",
        "ok": bool(rows),
        "services": rows,
        "summary": {"service_roots": len(rows)},
    }


def stack_model_tags(path: Path) -> list[str]:
    text = str(path).lower()
    tags: list[str] = []
    for tag, pattern in [
        ("embeddings", r"embed|embedding"),
        ("stt", r"whisper|/stt/"),
        ("tts", r"tts|voice|speech_tokenizer"),
        ("llm", r"llama|qwen3-[0-9].*b|phi-3\.5|gguf"),
        ("openvino", r"openvino|int4|int8|ovms"),
        ("npu", r"npu"),
    ]:
        if re.search(pattern, text):
            tags.append(tag)
    return tags


def stack_model_service_candidates(tags: list[str]) -> list[str]:
    services: list[str] = []
    if "embeddings" in tags or "openvino" in tags:
        services.extend(["ovms", "embeddings"])
    if "stt" in tags:
        services.append("stt")
    if "tts" in tags:
        services.extend(["tts", "qwen-tts", "tts-router", "babelvox-tts"])
    if "llm" in tags:
        services.extend(["llama-cpp", "llm-registry"])
    if "npu" in tags:
        services.append("npu")
    return sorted(dict.fromkeys(services))


def stack_model_root_inventory(
    *,
    schema_prefix: str,
    stack_paths: Mapping[str, Any],
    path_exists: PathExistsPort,
    path_is_dir: PathIsDirPort,
    path_iterdir: PathIterdirPort,
    max_entries: int = 160,
    max_depth: int = 4,
) -> dict[str, Any]:
    roots = [
        Path(str(stack_paths.get("srv_abyss_stack") or "")) / "Models",
        Path(str(stack_paths.get("source_abyss_stack") or "")) / "Models",
    ]
    rows: list[dict[str, Any]] = []
    for root in roots:
        if not path_exists(root) or not path_is_dir(root) or len(rows) >= max_entries:
            continue
        queue: list[tuple[Path, int]] = [(root, 0)]
        while queue and len(rows) < max_entries:
            path, depth = queue.pop(0)
            if depth > 0:
                tags = stack_model_tags(path)
                rows.append({
                    "relative_path": str(path.relative_to(root)),
                    "depth": depth,
                    "tags": tags,
                    "service_candidates": stack_model_service_candidates(tags),
                    "stack_source_refs": [stack_owned_source_ref(path, "model_root", tags=tags)],
                })
            if depth >= max_depth:
                continue
            try:
                children = sorted(child for child in path_iterdir(path) if path_is_dir(child))
            except OSError:
                children = []
            queue.extend((child, depth + 1) for child in children[:64])
    return {
        "schema": f"{schema_prefix}_self_awareness_working_stack_model_root_inventory_v1",
        "ok": bool(rows),
        "models": rows,
        "summary": {
            "model_roots": len(rows),
            "tag_counts": dict(collections.Counter(tag for row in rows for tag in row.get("tags", []))),
            "service_candidates": sorted({service for row in rows for service in row.get("service_candidates", [])}),
            "bounded": True,
            "max_entries": max_entries,
            "max_depth": max_depth,
        },
    }


def working_stack_probe_ok(probes: Iterable[Mapping[str, Any]], service: str, probe: str) -> bool:
    return any(
        isinstance(item, Mapping)
        and item.get("service") == service
        and item.get("probe") == probe
        and item.get("ok") is True
        for item in probes
    )


def working_stack_tool_status(service: str, status: str, probes: Iterable[Mapping[str, Any]]) -> str:
    probe_rows = list(probes)
    if service in {"qwen-tts", "tts-router"}:
        if working_stack_probe_ok(probe_rows, service, "tts-synthesis-artifact"):
            return "recent_on_demand_tool_signal"
    if service == "docs-api":
        if working_stack_probe_ok(probe_rows, service, "health") and working_stack_probe_ok(probe_rows, service, "search:n8n-workflow"):
            return "active_machine_tool_signal"
    if service == "aoa-browser":
        health_ok = working_stack_probe_ok(probe_rows, service, "health")
        guard_ok = working_stack_probe_ok(probe_rows, service, "private-host-guard")
        launch_probe_present = any(isinstance(item, Mapping) and item.get("service") == service and item.get("probe") == "playwright-chromium-launch" for item in probe_rows)
        launch_ok = working_stack_probe_ok(probe_rows, service, "playwright-chromium-launch")
        if health_ok and guard_ok and launch_ok:
            return "active_machine_tool_signal"
        if health_ok and guard_ok and launch_probe_present:
            return "tool_runtime_degraded"
        if health_ok and guard_ok:
            return "tool_guard_visible_unproven_deep_use"
    return status


def collect_stack_model_path_refs(
    value: Any,
    *,
    ai_model_roots: Iterable[Path | str],
    limit: int = 48,
) -> list[dict[str, Any]]:
    roots = tuple(str(path) for path in ai_model_roots)
    refs: list[dict[str, Any]] = []
    seen: set[str] = set()

    def visit(item: Any, depth: int = 0) -> None:
        if len(refs) >= limit or depth > 8:
            return
        if isinstance(item, Mapping):
            for key in ("path", "model_dir", "root", "local_path"):
                nested_value = item.get(key)
                if isinstance(nested_value, str):
                    visit(nested_value, depth + 1)
            for nested_value in item.values():
                if isinstance(nested_value, (Mapping, list)):
                    visit(nested_value, depth + 1)
            return
        if isinstance(item, list):
            for nested_value in item:
                visit(nested_value, depth + 1)
            return
        if not isinstance(item, str):
            return
        path = item.strip()
        if not path.startswith(roots) or path in seen:
            return
        seen.add(path)
        refs.append(stack_owned_source_ref(Path(path), "ai_capability_source_model"))

    visit(value)
    return refs


def model_row_paths(model_rows: Iterable[Mapping[str, Any]]) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for row in model_rows:
        if not isinstance(row, Mapping):
            continue
        candidates: list[Any] = [row.get("path")]
        stack_source_refs = row.get("stack_source_refs") if isinstance(row.get("stack_source_refs"), list) else []
        candidates.extend(ref.get("path") for ref in stack_source_refs if isinstance(ref, Mapping))
        for value in candidates:
            path = str(value or "").strip()
            if path and path not in seen:
                seen.add(path)
                paths.append(path)
    return paths


def paths_overlap(left: str, right: str) -> bool:
    left = left.rstrip("/")
    right = right.rstrip("/")
    if not left or not right:
        return False
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def _nested_get(value: Mapping[str, Any], path: list[str]) -> Any:
    current: Any = value
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def failure_matrix_row_is_open_requirement(row: Any) -> bool:
    if not isinstance(row, Mapping) or not str(row.get("id") or "").startswith("requirement:"):
        return False
    failure_kind = str(row.get("failure_kind") or "")
    if failure_kind == "open_requirement":
        return True
    if failure_kind == "closed_requirement_regression_guard":
        return False
    current_state = row.get("current_state") if isinstance(row.get("current_state"), Mapping) else {}
    status = str(current_state.get("status") or row.get("status") or "")
    if current_state.get("closed_by_current_probe") is True:
        return False
    if status in {"closed", "not_current_requirement"}:
        return False
    return current_state.get("requirement_present") is True


def cycle_initial_chain(
    *,
    probe_chain: Mapping[str, Any],
    requirement_probes: Mapping[str, Any],
    stack_closure_dossier: Mapping[str, Any],
    failure_matrix: Mapping[str, Any],
    investigation: Mapping[str, Any],
    replay: Mapping[str, Any],
    activation_smoke: Mapping[str, Any],
    trace_context_fallback: Mapping[str, Any],
    brief: Mapping[str, Any],
    reactions: Mapping[str, Any],
    responses: Mapping[str, Any],
    resident_cognitive_replay_complete: Callable[[Any], bool],
    working_stack_activation_smoke_complete: Callable[[Any], bool],
    trace_context_fallback_complete: Callable[[Any], bool],
) -> dict[str, bool]:
    resident_replay = replay.get("resident_cognitive_replay") if isinstance(replay.get("resident_cognitive_replay"), Mapping) else {}
    return {
        "synthetic_request": bool(probe_chain.get("request")),
        "capability_inventory": bool(probe_chain.get("capability_map")),
        "requirement_probes": bool(probe_chain.get("requirement_probes")) and bool(requirement_probes.get("ok")),
        "stack_closure_dossier": bool(probe_chain.get("stack_closure_dossier")) and bool(stack_closure_dossier.get("ok")),
        "failure_matrix": bool(probe_chain.get("failure_matrix")) and bool(failure_matrix.get("ok")),
        "working_stack": bool(probe_chain.get("working_stack")),
        "signal_fabric": all(bool(probe_chain.get(key)) for key in ("metric", "log", "trace_context", "context", "observation_events")),
        "query": bool(probe_chain.get("query")),
        "correlation": bool(probe_chain.get("correlation")),
        "timeline": bool(probe_chain.get("timeline")),
        "spatial_graph": bool(probe_chain.get("spatial_graph")),
        "causal_episode": bool(probe_chain.get("causal_episode")),
        "alert": bool(probe_chain.get("alert")),
        "warm_e2b_worker": bool(probe_chain.get("warm_e2b")),
        "rag_memory": bool(probe_chain.get("rag_memory")),
        "nervous_freshness": bool(probe_chain.get("nervous_freshness")),
        "langgraph_investigation": bool(investigation.get("ok")) and bool(investigation.get("checkpoints")),
        "replay": bool(replay.get("ok")) and _safe_int(_nested_get(replay, ["summary", "divergences"]), 0) == 0,
        "resident_cognitive_replay": resident_cognitive_replay_complete(resident_replay),
        "working_stack_activation_smoke": working_stack_activation_smoke_complete(activation_smoke),
        "stack_handoff_readiness_replay": _nested_get(replay, ["stack_handoff_replay", "closure_readiness_replayable"]) is True,
        "trace_context_fallback": trace_context_fallback_complete(trace_context_fallback),
        "semantic_brief": bool(brief.get("ok")),
        "reaction_candidate": bool(probe_chain.get("reaction_candidate")) and bool(reactions.get("ok", True)),
        "governed_response": bool(probe_chain.get("governed_response")) and bool(responses.get("ok", True)),
    }


def cycle_issue_inputs(
    *,
    failure_matrix: Mapping[str, Any],
    replay: Mapping[str, Any],
    stack_closure_dossier: Mapping[str, Any],
    responses: Mapping[str, Any],
) -> dict[str, Any]:
    rows = failure_matrix.get("rows") if isinstance(failure_matrix.get("rows"), list) else []
    open_requirement_rows = [
        row for row in rows
        if failure_matrix_row_is_open_requirement(row)
    ]
    stack_handoff_closure_readiness = (
        replay.get("stack_handoff_closure_readiness")
        if isinstance(replay.get("stack_handoff_closure_readiness"), Mapping)
        else {}
    )
    working_stack_activation_summary = _nested_get(stack_closure_dossier, ["working_stack_activation_dossier", "summary"])
    if not isinstance(working_stack_activation_summary, Mapping):
        working_stack_activation_summary = {}
    return {
        "open_requirement_rows": open_requirement_rows,
        "automatic_response_count": _safe_int(_nested_get(responses, ["summary", "automatic_responses"]), 0),
        "mutating_response_routes": _safe_int(_nested_get(responses, ["summary", "routes_with_mutating_command_if_run"]), 0),
        "mutation_claims": [
            row.get("id") for row in rows
            if isinstance(row, Mapping)
            and (row.get("host_layer_mutates_stack") is not False or row.get("automatic_remediation") is not False)
        ],
        "stack_handoff_closure_readiness": dict(stack_handoff_closure_readiness),
        "working_stack_activation_summary": dict(working_stack_activation_summary),
        "open_working_stack_activation_gaps": _safe_int(working_stack_activation_summary.get("open_activation_gaps"), 0),
    }


def cycle_export_chain_updates(
    *,
    probe_chain: Mapping[str, Any],
    replay: Mapping[str, Any],
    responses: Mapping[str, Any],
    export: Mapping[str, Any],
    autolink: Mapping[str, Any],
    autolink_complete: Callable[[Any], bool],
    resident_cognitive_replay_complete: Callable[[Any], bool],
    working_stack_link_integrity_complete: Callable[[Any], bool],
) -> dict[str, bool]:
    resident_export = export.get("resident_cognitive_replay") if isinstance(export.get("resident_cognitive_replay"), Mapping) else {}
    working_stack_link_integrity = (
        export.get("working_stack_link_integrity")
        if isinstance(export.get("working_stack_link_integrity"), Mapping)
        else {}
    )
    return {
        "autolink": autolink_complete(autolink),
        "export": bool(export.get("ok")),
        "resident_cognitive_export": resident_cognitive_replay_complete(resident_export),
        "body_trace": (
            bool(probe_chain.get("body_trace"))
            and _nested_get(replay, ["body_trace_replay", "replayable"]) is True
            and _safe_int(_nested_get(responses, ["summary", "self_awareness_body_trace_routes"]), 0) >= 1
            and _safe_int(_nested_get(responses, ["summary", "self_awareness_body_trace_missing"]), -1) == 0
            and _nested_get(export, ["body_trace_handoff", "host_body_context_packet_included"]) is True
            and _nested_get(export, ["body_trace_handoff", "resident_body_trace_replayable"]) is True
            and _nested_get(export, ["body_trace_handoff", "response_body_trace_included"]) is True
        ),
        "entity_event_document": (
            bool(probe_chain.get("entity_event_document"))
            and _safe_int(_nested_get(responses, ["summary", "self_awareness_entity_event_document_routes"]), 0) >= 1
            and _safe_int(_nested_get(responses, ["summary", "self_awareness_entity_event_document_missing"]), -1) == 0
            and _nested_get(export, ["portable_contract", "response_entity_event_document_context_included"]) is True
            and _nested_get(export, ["response_entity_event_document_handoff", "complete"]) is True
        ),
        "working_stack_link_integrity": working_stack_link_integrity_complete(working_stack_link_integrity),
    }


def _latest_path_text(latest_paths: Mapping[str, Path | str], name: str) -> str:
    return str(latest_paths.get(name) or name)


def working_stack_link_integrity_matches_working_stack(
    working_stack_doc: Mapping[str, Any],
    link_integrity: Mapping[str, Any],
) -> bool:
    organs = working_stack_doc.get("organs") if isinstance(working_stack_doc.get("organs"), list) else []
    rows = link_integrity.get("rows") if isinstance(link_integrity.get("rows"), list) else []
    if not organs or not rows:
        return False
    rows_by_service = {
        str(row.get("service")): row
        for row in rows
        if isinstance(row, Mapping) and row.get("service")
    }
    for organ in organs:
        if not isinstance(organ, Mapping) or not organ.get("service"):
            continue
        service = str(organ.get("service") or "")
        status = str(organ.get("machine_usage_status") or "")
        link_id = str(
            _nested_get(organ, ["time_space_context_link", "link_id"])
            or _nested_get(organ, ["time_space_context_link", "context", "working_stack_link_id"])
            or ""
        )
        row = rows_by_service.get(service)
        if not isinstance(row, Mapping):
            return False
        if str(row.get("working_stack_link_id") or "") != link_id:
            return False
        if str(row.get("machine_usage_status") or "") != status:
            return False
    return True


def working_stack_link_integrity_matrix(
    *,
    working_stack_doc: Mapping[str, Any],
    events_doc: Mapping[str, Any] | None = None,
    timeline_doc: Mapping[str, Any] | None = None,
    spatial_doc: Mapping[str, Any] | None = None,
    context_doc: Mapping[str, Any] | None = None,
    episodes_doc: Mapping[str, Any] | None = None,
    coverage_gap_rows: list[dict[str, Any]] | None = None,
    generated_at: str,
    schema_prefix: str,
    version: str,
    latest_paths: Mapping[str, Path | str],
) -> dict[str, Any]:
    events_doc = events_doc if isinstance(events_doc, Mapping) else {}
    timeline_doc = timeline_doc if isinstance(timeline_doc, Mapping) else {}
    spatial_doc = spatial_doc if isinstance(spatial_doc, Mapping) else {}
    context_doc = context_doc if isinstance(context_doc, Mapping) else {}
    episodes_doc = episodes_doc if isinstance(episodes_doc, Mapping) else {}
    coverage_gap_rows = coverage_gap_rows if isinstance(coverage_gap_rows, list) else []

    organs = working_stack_doc.get("organs") if isinstance(working_stack_doc.get("organs"), list) else []
    events = events_doc.get("events") if isinstance(events_doc.get("events"), list) else []
    windows = timeline_doc.get("windows") if isinstance(timeline_doc.get("windows"), list) else []
    nodes = spatial_doc.get("nodes") if isinstance(spatial_doc.get("nodes"), list) else []
    edges = spatial_doc.get("edges") if isinstance(spatial_doc.get("edges"), list) else []
    contexts = context_doc.get("contexts") if isinstance(context_doc.get("contexts"), list) else []
    episodes = episodes_doc.get("episodes") if isinstance(episodes_doc.get("episodes"), list) else []

    node_ids = {str(node.get("id")) for node in nodes if isinstance(node, Mapping) and node.get("id")}
    edge_tuples = {
        (str(edge.get("from")), str(edge.get("to")), str(edge.get("kind")))
        for edge in edges
        if isinstance(edge, Mapping) and edge.get("from") and edge.get("to") and edge.get("kind")
    }
    timeline_event_ids = {
        str(event_id)
        for window in windows
        if isinstance(window, Mapping)
        for event_id in (window.get("event_ids") if isinstance(window.get("event_ids"), list) else [])
        if event_id
    }
    contexts_by_link = {
        str(item.get("key")): item
        for item in contexts
        if isinstance(item, Mapping) and item.get("key")
    }
    for item in contexts:
        if not isinstance(item, Mapping):
            continue
        link_id = _nested_get(item, ["context", "working_stack_link_id"])
        if link_id:
            contexts_by_link.setdefault(str(link_id), item)
    gap_rows_by_service = {
        str(row.get("service")): row
        for row in coverage_gap_rows
        if isinstance(row, Mapping) and row.get("service")
    }

    rows: list[dict[str, Any]] = []
    for organ in organs:
        if not isinstance(organ, Mapping):
            continue
        service = str(organ.get("service") or "")
        if not service:
            continue
        link = organ.get("time_space_context_link") if isinstance(organ.get("time_space_context_link"), Mapping) else {}
        link_id = str(link.get("link_id") or _nested_get(link, ["context", "working_stack_link_id"]) or "")
        status = str(organ.get("machine_usage_status") or "")
        usage_gap = str(organ.get("usage_gap") or "")
        service_node = "service:" + service
        link_node = "working_stack_link:" + link_id if link_id else ""
        matching_events = [
            event for event in events
            if isinstance(event, Mapping)
            and event.get("source") == "working-stack"
            and str(_nested_get(event, ["resource", "service"]) or "") == service
            and (
                not link_id
                or str(
                    _nested_get(event, ["context", "working_stack_link_id"])
                    or _nested_get(event, ["fabric", "context_links", "links", "working_stack_link_id"])
                    or ""
                ) == link_id
            )
        ]
        event = matching_events[0] if matching_events else {}
        event_id = str(event.get("event_id") or "")
        event_resource = event.get("resource") if isinstance(event.get("resource"), Mapping) else {}
        event_context = event.get("context") if isinstance(event.get("context"), Mapping) else {}
        movement_packet_id = str(event_resource.get("movement_packet_id") or event_context.get("movement_packet_id") or "")
        movement_current_state_digest = str(event_context.get("current_state_digest") or event_resource.get("current_state_digest") or "")
        movement_pid = event_resource.get("pid") or event_context.get("pid")
        movement_pid_alive = event_resource.get("pid_alive") if "pid_alive" in event_resource else event_context.get("pid_alive")
        movement_categories = event_resource.get("movement_categories") if isinstance(event_resource.get("movement_categories"), list) else []
        movement_degradation_reasons = event_resource.get("degradation_reasons") if isinstance(event_resource.get("degradation_reasons"), list) else []
        event_selected_for_episode = _nested_get(event, ["resource", "selected_for_episode"]) is True
        episode_required = bool(usage_gap or event_selected_for_episode)
        context_item = contexts_by_link.get(link_id, {})
        coverage_row = gap_rows_by_service.get(service, {})
        activation_smoke = coverage_row.get("activation_smoke") if isinstance(coverage_row.get("activation_smoke"), Mapping) else {}
        episode_matches = [
            episode for episode in episodes
            if isinstance(episode, Mapping)
            and (
                (event_id and event_id in [str(item) for item in (episode.get("event_ids") if isinstance(episode.get("event_ids"), list) else [])])
                or service_node in [str(item) for item in (episode.get("affected_spatial_nodes") if isinstance(episode.get("affected_spatial_nodes"), list) else [])]
                or str(_nested_get(episode, ["working_stack_gap", "service"]) or "") == service
            )
        ]
        episode_ids = [str(episode.get("episode_id")) for episode in episode_matches if isinstance(episode, Mapping) and episode.get("episode_id")][:8]
        selected_episode_ids = episode_ids if episode_required else []
        checks = {
            "working_stack_link": bool(link_id and link.get("schema") == f"{schema_prefix}_self_awareness_working_stack_time_space_context_link_v1"),
            "event_projected": bool(event_id),
            "movement_packet": bool(movement_packet_id and movement_current_state_digest),
            "event_fabric_link": bool(
                event_id
                and _nested_get(event, ["fabric", "schema"]) == f"{schema_prefix}_self_awareness_signal_fabric_v1"
                and str(
                    _nested_get(event, ["fabric", "context_links", "links", "working_stack_link_id"])
                    or _nested_get(event, ["context", "working_stack_link_id"])
                    or ""
                ) == link_id
                and _nested_get(event, ["fabric", "policy", "host_layer_mutates_stack"]) is False
            ),
            "timeline_window": bool(event_id and event_id in timeline_event_ids),
            "spatial_service_node": service_node in node_ids,
            "spatial_link_node": bool(link_node and link_node in node_ids),
            "spatial_service_to_link_edge": bool(link_node and (service_node, link_node, "has_time_space_context_link") in edge_tuples),
            "context_indexed": bool(context_item and link_id),
            "episode_present": bool(not episode_required or episode_matches),
            "coverage_gap_row": bool(not usage_gap or (coverage_row and coverage_row.get("working_stack_link_id") == link_id)),
            "activation_smoke_if_gap": bool(not usage_gap or (activation_smoke.get("complete") is True and activation_smoke.get("working_stack_link_id") == link_id)),
            "policy": _nested_get(organ, ["policy", "host_layer_mutates_stack"]) is False,
        }
        missing_checks = [key for key, value in checks.items() if not value]
        rows.append({
            "schema": f"{schema_prefix}_self_awareness_working_stack_link_integrity_row_v1",
            "service": service,
            "owner": "abyss-stack",
            "machine_usage_status": status,
            "usage_gap": usage_gap or None,
            "working_stack_link_id": link_id or None,
            "event_id": event_id or None,
            "movement_packet_id": movement_packet_id or None,
            "observed_signal": event_resource.get("observed_signal"),
            "observed_source": event_resource.get("observed_source"),
            "pid": movement_pid,
            "pid_alive": movement_pid_alive,
            "current_state_digest": movement_current_state_digest or None,
            "state_changed": event_context.get("state_changed"),
            "movement_categories": movement_categories,
            "selected_for_episode": event_selected_for_episode,
            "selected_for_resident_reasoning": event_resource.get("selected_for_resident_reasoning") is True,
            "selected_reason": event_resource.get("selected_reason"),
            "not_selected_reason": event_resource.get("not_selected_reason"),
            "degradation_reasons": movement_degradation_reasons,
            "event_selected_for_episode": event_selected_for_episode,
            "episode_required": episode_required,
            "timeline_bucket": _nested_get(link, ["time", "bucket"]),
            "spatial_nodes": [item for item in [service_node, link_node, f"process:{movement_pid}" if movement_pid else None] if item],
            "context_key": context_item.get("key") if isinstance(context_item, Mapping) else None,
            "episode_ids": selected_episode_ids,
            "adjacent_episode_ids": episode_ids,
            "coverage_gap_row_id": coverage_row.get("id") if isinstance(coverage_row, Mapping) else None,
            "checks": checks,
            "missing_checks": missing_checks,
            "complete": not missing_checks,
            "evidence_refs": [
                {"path": _latest_path_text(latest_paths, "working_stack"), "service": service, "working_stack_link_id": link_id or None},
                {"path": _latest_path_text(latest_paths, "events"), "event_id": event_id or None},
                {"path": _latest_path_text(latest_paths, "timeline"), "event_id": event_id or None},
                {"path": _latest_path_text(latest_paths, "spatial_graph"), "nodes": [item for item in [service_node, link_node] if item]},
                {"path": _latest_path_text(latest_paths, "context"), "context_key": context_item.get("key") if isinstance(context_item, Mapping) else None},
                {"path": _latest_path_text(latest_paths, "episodes"), "episode_ids": selected_episode_ids, "adjacent_episode_ids": episode_ids},
            ],
            "policy": {
                "read_only": True,
                "host_layer_mutates_stack": False,
                "writes_project_roots": False,
                "actions_executed": False,
                "automatic_remediation": False,
                "raw_evidence_is_not_truth": True,
            },
        })

    missing_rows = [str(row.get("service")) for row in rows if not row.get("complete")]
    gap_rows = [row for row in rows if row.get("usage_gap")]
    return {
        "schema": f"{schema_prefix}_self_awareness_working_stack_link_integrity_matrix_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": bool(rows) and not missing_rows,
        "summary": {
            "organs": len(organs),
            "rows": len(rows),
            "complete_rows": sum(1 for row in rows if row.get("complete") is True),
            "missing_rows": missing_rows,
            "usage_gap_rows": len(gap_rows),
            "usage_gap_rows_with_coverage": sum(1 for row in gap_rows if _nested_get(row, ["checks", "coverage_gap_row"]) is True),
            "usage_gap_rows_with_activation_smoke": sum(1 for row in gap_rows if _nested_get(row, ["checks", "activation_smoke_if_gap"]) is True),
            "event_projected": sum(1 for row in rows if _nested_get(row, ["checks", "event_projected"]) is True),
            "timeline_linked": sum(1 for row in rows if _nested_get(row, ["checks", "timeline_window"]) is True),
            "spatial_linked": sum(1 for row in rows if _nested_get(row, ["checks", "spatial_service_to_link_edge"]) is True),
            "context_indexed": sum(1 for row in rows if _nested_get(row, ["checks", "context_indexed"]) is True),
            "episode_linked": sum(1 for row in rows if row.get("episode_required") is True and row.get("episode_ids")),
            "episode_required_rows": sum(1 for row in rows if row.get("episode_required") is True),
            "episode_not_required_rows": sum(1 for row in rows if row.get("episode_required") is not True),
        },
        "rows": rows,
        "rows_by_service": {str(row.get("service")): row for row in rows if row.get("service")},
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "actions_executed": False,
            "automatic_remediation": False,
            "raw_evidence_is_not_truth": True,
            "coverage_gap_rows_required_only_for_usage_gaps": True,
        },
        "evidence_refs": [
            {"path": _latest_path_text(latest_paths, "working_stack"), "schema": working_stack_doc.get("schema")},
            {"path": _latest_path_text(latest_paths, "events"), "schema": events_doc.get("schema")},
            {"path": _latest_path_text(latest_paths, "timeline"), "schema": timeline_doc.get("schema")},
            {"path": _latest_path_text(latest_paths, "spatial_graph"), "schema": spatial_doc.get("schema")},
            {"path": _latest_path_text(latest_paths, "context"), "schema": context_doc.get("schema")},
            {"path": _latest_path_text(latest_paths, "episodes"), "schema": episodes_doc.get("schema")},
        ],
    }


def working_stack_link_integrity_matrix_complete(matrix: Any, *, schema_prefix: str) -> bool:
    if not isinstance(matrix, Mapping):
        return False
    rows = matrix.get("rows") if isinstance(matrix.get("rows"), list) else []
    return (
        matrix.get("schema") == f"{schema_prefix}_self_awareness_working_stack_link_integrity_matrix_v1"
        and bool(rows)
        and matrix.get("ok") is True
        and _safe_int(_nested_get(matrix, ["summary", "rows"]), -1) == len(rows)
        and _safe_int(_nested_get(matrix, ["summary", "complete_rows"]), -1) == len(rows)
        and not _nested_get(matrix, ["summary", "missing_rows"])
        and _safe_int(_nested_get(matrix, ["summary", "organs"]), -1) == len(rows)
        and _nested_get(matrix, ["policy", "host_layer_mutates_stack"]) is False
        and all(
            isinstance(row, Mapping)
            and row.get("schema") == f"{schema_prefix}_self_awareness_working_stack_link_integrity_row_v1"
            and row.get("complete") is True
            and row.get("service")
            and row.get("working_stack_link_id")
            and row.get("event_id")
            and row.get("movement_packet_id")
            and row.get("current_state_digest")
            and _nested_get(row, ["checks", "working_stack_link"]) is True
            and _nested_get(row, ["checks", "event_projected"]) is True
            and _nested_get(row, ["checks", "movement_packet"]) is True
            and _nested_get(row, ["checks", "event_fabric_link"]) is True
            and _nested_get(row, ["checks", "timeline_window"]) is True
            and _nested_get(row, ["checks", "spatial_service_to_link_edge"]) is True
            and _nested_get(row, ["checks", "context_indexed"]) is True
            and _nested_get(row, ["checks", "episode_present"]) is True
            and (row.get("episode_required") is not True or row.get("episode_ids"))
            and _nested_get(row, ["checks", "coverage_gap_row"]) is True
            and _nested_get(row, ["checks", "activation_smoke_if_gap"]) is True
            and _nested_get(row, ["policy", "host_layer_mutates_stack"]) is False
            and row.get("evidence_refs")
            for row in rows
        )
    )


def working_stack_dependent_link_readmodels_fresh(matrix: Any) -> bool:
    if not isinstance(matrix, Mapping):
        return False
    summary = matrix.get("summary") if isinstance(matrix.get("summary"), Mapping) else {}
    rows = _safe_int(summary.get("rows"), 0)
    if rows <= 0:
        return False
    episode_required_rows = _safe_int(summary.get("episode_required_rows"), 0)
    return (
        _safe_int(summary.get("timeline_linked"), -1) == rows
        and _safe_int(summary.get("spatial_linked"), -1) == rows
        and _safe_int(summary.get("context_indexed"), -1) == rows
        and _safe_int(summary.get("episode_linked"), -1) >= episode_required_rows
    )


def autolink_row_state(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "service": row.get("service"),
        "working_stack_link_id": row.get("working_stack_link_id"),
        "machine_usage_status": row.get("machine_usage_status"),
        "usage_gap": row.get("usage_gap"),
        "movement_current_state_digest": row.get("current_state_digest"),
        "observed_signal": row.get("observed_signal"),
        "observed_source": row.get("observed_source"),
        "pid": row.get("pid"),
        "pid_alive": row.get("pid_alive"),
        "movement_categories": row.get("movement_categories") if isinstance(row.get("movement_categories"), list) else [],
        "selected_for_episode": row.get("selected_for_episode") is True,
        "selected_for_resident_reasoning": row.get("selected_for_resident_reasoning") is True,
        "not_selected_reason": row.get("not_selected_reason"),
        "degradation_reasons": row.get("degradation_reasons") if isinstance(row.get("degradation_reasons"), list) else [],
        "spatial_nodes": row.get("spatial_nodes") if isinstance(row.get("spatial_nodes"), list) else [],
        "context_key": row.get("context_key"),
        "episode_required": row.get("episode_required"),
        "episode_ids": row.get("episode_ids") if isinstance(row.get("episode_ids"), list) else [],
        "coverage_gap_row_id": row.get("coverage_gap_row_id"),
    }


def autolink_complete(doc: Any, *, schema_prefix: str) -> bool:
    if not isinstance(doc, Mapping):
        return False
    organ_rows = doc.get("organ_links") if isinstance(doc.get("organ_links"), list) else []
    requirement_rows = doc.get("stack_requirement_links") if isinstance(doc.get("stack_requirement_links"), list) else []
    scenarios = doc.get("synthetic_scenarios") if isinstance(doc.get("synthetic_scenarios"), list) else []
    return (
        doc.get("schema") == f"{schema_prefix}_self_awareness_autolink_v1"
        and doc.get("ok") is True
        and bool(organ_rows)
        and _safe_int(_nested_get(doc, ["summary", "organ_links"]), -1) == len(organ_rows)
        and _safe_int(_nested_get(doc, ["summary", "organ_links_complete"]), -1) == len(organ_rows)
        and _safe_int(_nested_get(doc, ["summary", "stack_requirement_links"]), -1) == len(requirement_rows)
        and _safe_int(_nested_get(doc, ["summary", "stack_requirement_links_complete"]), -1) == len(requirement_rows)
        and _safe_int(_nested_get(doc, ["summary", "synthetic_scenarios"]), -1) == len(scenarios)
        and _safe_int(_nested_get(doc, ["summary", "synthetic_scenarios_complete"]), -1) == len(scenarios)
        and bool(doc.get("state_digest"))
        and isinstance(doc.get("state_delta"), Mapping)
        and _nested_get(doc, ["policy", "host_layer_mutates_stack"]) is False
        and _nested_get(doc, ["policy", "executes_commands"]) is False
        and _nested_get(doc, ["policy", "automatic_remediation"]) is False
        and all(
            isinstance(row, Mapping)
            and row.get("schema") == f"{schema_prefix}_self_awareness_autolink_organ_row_v1"
            and row.get("complete") is True
            and row.get("service")
            and row.get("working_stack_link_id")
            and row.get("event_id")
            and row.get("movement_packet_id")
            and row.get("movement_current_state_digest")
            and _nested_get(row, ["checks", "time_linked"]) is True
            and _nested_get(row, ["checks", "space_linked"]) is True
            and _nested_get(row, ["checks", "context_linked"]) is True
            and _nested_get(row, ["checks", "movement_packet_linked"]) is True
            and _nested_get(row, ["checks", "episode_linked"]) is True
            and (row.get("episode_required") is not True or row.get("episode_ids"))
            and (
                not row.get("usage_gap")
                or (
                    _nested_get(row, ["checks", "gap_has_activation_smoke"]) is True
                    and _nested_get(row, ["activation_smoke", "complete"]) is True
                    and _nested_get(row, ["activation_smoke", "working_stack_link_id"]) == row.get("working_stack_link_id")
                )
            )
            and _nested_get(row, ["policy", "host_layer_mutates_stack"]) is False
            for row in organ_rows
        )
        and all(
            isinstance(row, Mapping)
            and row.get("schema") == f"{schema_prefix}_self_awareness_autolink_stack_requirement_row_v1"
            and row.get("complete") is True
            and row.get("requirement_id")
            and (
                row.get("episode_ids")
                or (
                    row.get("automatic_link_state") == "closed"
                    and row.get("closed_by_current_probe") is True
                )
            )
            and _nested_get(row, ["checks", "closure_acceptance"]) is True
            and _nested_get(row, ["checks", "coverage_impact"]) is True
            and _nested_get(row, ["checks", "owner_route"]) is True
            and _nested_get(row, ["policy", "host_layer_mutates_stack"]) is False
            for row in requirement_rows
        )
        and all(
            isinstance(row, Mapping)
            and row.get("schema") == f"{schema_prefix}_self_awareness_autolink_synthetic_scenario_v1"
            and row.get("complete") is True
            and _nested_get(row, ["policy", "host_layer_mutates_stack"]) is False
            and _nested_get(row, ["policy", "executes_commands"]) is False
            for row in scenarios
        )
    )


def autolink_document(
    *,
    working_stack_doc: Mapping[str, Any],
    coverage_audit_doc: Mapping[str, Any],
    stack_closure_dossier_doc: Mapping[str, Any],
    activation_smoke_doc: Mapping[str, Any],
    episodes_doc: Mapping[str, Any],
    previous: Mapping[str, Any],
    dependency_refresh: Mapping[str, Any] | None,
    generated_at: str,
    version: str,
    schema_prefix: str,
    cycle_id: str | None,
    probe_run_id: str | None,
    latest_paths: Mapping[str, Path | str],
    activation_smoke_compact: Callable[[Any], dict[str, Any]],
    stack_requirement_closure_acceptance_complete: Callable[[Any], bool],
    stack_coverage_impact_complete: Callable[[Any], bool],
) -> dict[str, Any]:
    link_integrity = coverage_audit_doc.get("working_stack_link_integrity") if isinstance(coverage_audit_doc.get("working_stack_link_integrity"), Mapping) else {}
    link_rows = link_integrity.get("rows") if isinstance(link_integrity.get("rows"), list) else []
    previous_organ_by_service = previous.get("organ_links_by_service") if isinstance(previous.get("organ_links_by_service"), Mapping) else {}
    previous_requirement_by_id = previous.get("stack_requirement_links_by_requirement") if isinstance(previous.get("stack_requirement_links_by_requirement"), Mapping) else {}
    activation_by_service = activation_smoke_doc.get("by_service") if isinstance(activation_smoke_doc.get("by_service"), Mapping) else {}

    organ_links: list[dict[str, Any]] = []
    for source_row in link_rows:
        if not isinstance(source_row, Mapping):
            continue
        service = str(source_row.get("service") or "")
        if not service:
            continue
        activation_smoke = activation_by_service.get(service) if isinstance(activation_by_service.get(service), Mapping) else {}
        current_state = autolink_row_state(source_row)
        current_state["activation_smoke_thread_id"] = _nested_get(activation_smoke, ["investigation", "thread_id"]) or _nested_get(activation_smoke, ["replay", "thread_id"])
        current_state["activation_smoke_working_stack_link_id"] = activation_smoke.get("working_stack_link_id")
        current_state_digest = self_awareness_contracts.stable_hash_json(current_state, length=24)
        previous_row = previous_organ_by_service.get(service) if isinstance(previous_organ_by_service.get(service), Mapping) else {}
        previous_state_digest = previous_row.get("current_state_digest")
        episode_required = source_row.get("episode_required") is True
        checks = {
            "source_integrity": source_row.get("complete") is True,
            "time_linked": bool(source_row.get("timeline_bucket")),
            "space_linked": bool(source_row.get("spatial_nodes")),
            "context_linked": bool(source_row.get("context_key")),
            "movement_packet_linked": bool(source_row.get("movement_packet_id") and source_row.get("current_state_digest")),
            "episode_linked": bool(not episode_required or source_row.get("episode_ids")),
            "gap_has_activation_smoke": bool(
                not source_row.get("usage_gap")
                or (
                    activation_smoke.get("ok") is True
                    and activation_smoke.get("working_stack_link_id") == source_row.get("working_stack_link_id")
                )
            ),
            "policy": _nested_get(source_row, ["policy", "host_layer_mutates_stack"]) is False,
        }
        missing_checks = [key for key, ok in checks.items() if not ok]
        organ_links.append({
            "schema": f"{schema_prefix}_self_awareness_autolink_organ_row_v1",
            "autolink_id": "saautolink-" + self_awareness_contracts.stable_hash_json({"service": service, "link": source_row.get("working_stack_link_id"), "at": generated_at}, length=20),
            "service": service,
            "owner": source_row.get("owner") or "abyss-stack",
            "automatic_link_state": "open_potential" if source_row.get("usage_gap") else "active",
            "machine_usage_status": source_row.get("machine_usage_status"),
            "usage_gap": source_row.get("usage_gap"),
            "working_stack_link_id": source_row.get("working_stack_link_id"),
            "event_id": source_row.get("event_id"),
            "movement_packet_id": source_row.get("movement_packet_id"),
            "observed_signal": source_row.get("observed_signal"),
            "observed_source": source_row.get("observed_source"),
            "pid": source_row.get("pid"),
            "pid_alive": source_row.get("pid_alive"),
            "movement_current_state_digest": source_row.get("current_state_digest"),
            "movement_state_changed": source_row.get("state_changed"),
            "movement_categories": source_row.get("movement_categories") if isinstance(source_row.get("movement_categories"), list) else [],
            "selected_for_episode": source_row.get("selected_for_episode") is True,
            "selected_for_resident_reasoning": source_row.get("selected_for_resident_reasoning") is True,
            "selected_reason": source_row.get("selected_reason"),
            "not_selected_reason": source_row.get("not_selected_reason"),
            "degradation_reasons": source_row.get("degradation_reasons") if isinstance(source_row.get("degradation_reasons"), list) else [],
            "time": {"bucket": source_row.get("timeline_bucket"), "observed_at": generated_at},
            "space": {"nodes": source_row.get("spatial_nodes") if isinstance(source_row.get("spatial_nodes"), list) else [], "pid": source_row.get("pid")},
            "context": {"key": source_row.get("context_key"), "correlation_keys": [source_row.get("context_key"), source_row.get("working_stack_link_id")]},
            "episode_required": episode_required,
            "episode_ids": source_row.get("episode_ids") if isinstance(source_row.get("episode_ids"), list) else [],
            "adjacent_episode_ids": source_row.get("adjacent_episode_ids") if isinstance(source_row.get("adjacent_episode_ids"), list) else [],
            "coverage_gap_row_id": source_row.get("coverage_gap_row_id"),
            "activation_smoke": activation_smoke_compact(activation_smoke) if activation_smoke else {},
            "current_state_digest": current_state_digest,
            "previous_state_digest": previous_state_digest,
            "state_changed_since_previous_autolink": bool(previous_state_digest and previous_state_digest != current_state_digest),
            "checks": checks,
            "missing_checks": missing_checks,
            "complete": not missing_checks,
            "evidence_refs": source_row.get("evidence_refs") if isinstance(source_row.get("evidence_refs"), list) else [],
            "policy": {
                "read_only": True,
                "host_layer_mutates_stack": False,
                "writes_project_roots": False,
                "executes_commands": False,
                "automatic_remediation": False,
                "raw_evidence_is_not_truth": True,
            },
        })

    episodes = episodes_doc.get("episodes") if isinstance(episodes_doc.get("episodes"), list) else []
    stack_requirement_links: list[dict[str, Any]] = []
    entries = stack_closure_dossier_doc.get("entries") if isinstance(stack_closure_dossier_doc.get("entries"), list) else []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        requirement_id = str(entry.get("requirement_id") or "")
        if not requirement_id:
            continue
        closure_acceptance = entry.get("closure_acceptance") if isinstance(entry.get("closure_acceptance"), Mapping) else {}
        coverage_impact = entry.get("coverage_impact") if isinstance(entry.get("coverage_impact"), Mapping) else {}
        closed_by_current_probe = entry.get("closed_by_current_probe") is True or entry.get("status") == "closed"
        requirement_episodes = [
            str(episode.get("episode_id"))
            for episode in episodes
            if isinstance(episode, Mapping)
            and (
                str(episode.get("requirement_id") or "") == requirement_id
                or requirement_id in [str(node).replace("stack_requirement:", "") for node in (episode.get("affected_spatial_nodes") if isinstance(episode.get("affected_spatial_nodes"), list) else [])]
            )
            and episode.get("episode_id")
        ][:8]
        current_state = {
            "requirement_id": requirement_id,
            "status": entry.get("status"),
            "closed_by_current_probe": closed_by_current_probe,
            "blocking_check_keys": entry.get("blocking_check_keys") if isinstance(entry.get("blocking_check_keys"), list) else [],
            "current_state_digest": entry.get("current_state_digest"),
            "closure_acceptance_id": closure_acceptance.get("acceptance_id"),
            "coverage_planes": coverage_impact.get("coverage_planes") if isinstance(coverage_impact.get("coverage_planes"), list) else [],
        }
        current_state_digest = self_awareness_contracts.stable_hash_json(current_state, length=24)
        previous_row = previous_requirement_by_id.get(requirement_id) if isinstance(previous_requirement_by_id.get(requirement_id), Mapping) else {}
        previous_state_digest = previous_row.get("current_state_digest")
        checks = {
            "dossier_entry_complete": entry.get("complete") is True,
            "closure_acceptance": stack_requirement_closure_acceptance_complete(closure_acceptance),
            "coverage_impact": stack_coverage_impact_complete(coverage_impact),
            "owner_route": entry.get("owner") == "abyss-stack",
            "time_linked": bool(entry.get("current_state_digest")),
            "space_linked": bool(coverage_impact.get("affected_stack_surfaces") or coverage_impact.get("affected_machine_surfaces")),
            "context_linked": bool(entry.get("blocking_check_keys")) or closed_by_current_probe,
            "episode_linked": bool(requirement_episodes) or closed_by_current_probe,
            "policy": _nested_get(entry, ["policy", "host_layer_mutates_stack"]) is False,
        }
        missing_checks = [key for key, ok in checks.items() if not ok]
        stack_requirement_links.append({
            "schema": f"{schema_prefix}_self_awareness_autolink_stack_requirement_row_v1",
            "autolink_id": "saautolink-req-" + self_awareness_contracts.stable_hash_json({"requirement": requirement_id, "at": generated_at}, length=20),
            "requirement_id": requirement_id,
            "owner": entry.get("owner") or "abyss-stack",
            "status": "closed" if closed_by_current_probe else (entry.get("status") or "open"),
            "closed_by_current_probe": closed_by_current_probe,
            "automatic_link_state": "closed" if closed_by_current_probe else "open_stack_blocker",
            "time": {"bucket": self_awareness_contracts.time_bucket(generated_at), "observed_at": generated_at},
            "space": {
                "nodes": ["stack_requirement:" + requirement_id, "owner:abyss-stack"],
                "affected_stack_surfaces": coverage_impact.get("affected_stack_surfaces") if isinstance(coverage_impact.get("affected_stack_surfaces"), list) else [],
                "affected_machine_surfaces": coverage_impact.get("affected_machine_surfaces") if isinstance(coverage_impact.get("affected_machine_surfaces"), list) else [],
            },
            "context": {
                "closure_acceptance_id": closure_acceptance.get("acceptance_id"),
                "compat_requirement_id": _nested_get(closure_acceptance, ["stack_compat_requirement", "requirement_id"]),
                "blocking_check_keys": entry.get("blocking_check_keys") if isinstance(entry.get("blocking_check_keys"), list) else [],
                "coverage_planes": coverage_impact.get("coverage_planes") if isinstance(coverage_impact.get("coverage_planes"), list) else [],
            },
            "episode_ids": requirement_episodes,
            "current_state_digest": current_state_digest,
            "previous_state_digest": previous_state_digest,
            "state_changed_since_previous_autolink": bool(previous_state_digest and previous_state_digest != current_state_digest),
            "checks": checks,
            "missing_checks": missing_checks,
            "complete": not missing_checks,
            "evidence_refs": entry.get("evidence_refs") if isinstance(entry.get("evidence_refs"), list) else [],
            "policy": {
                "read_only": True,
                "handoff_only": True,
                "host_layer_mutates_stack": False,
                "writes_project_roots": False,
                "executes_commands": False,
                "automatic_remediation": False,
                "raw_evidence_is_not_truth": True,
            },
        })

    state_basis = {
        "organ_states": {str(row.get("service")): row.get("current_state_digest") for row in organ_links},
        "requirement_states": {str(row.get("requirement_id")): row.get("current_state_digest") for row in stack_requirement_links},
        "open_stack_requirements": _safe_int(_nested_get(stack_closure_dossier_doc, ["summary", "open_stack_requirements"]), 0),
        "working_stack_usage_gaps": _safe_int(_nested_get(working_stack_doc, ["summary", "usage_gaps"]), 0),
    }
    state_digest = self_awareness_contracts.stable_hash_json(state_basis, length=32)
    previous_digest = previous.get("state_digest") if isinstance(previous, Mapping) else None
    previous_services = set(str(item) for item in (_nested_get(previous, ["summary", "service_ids"]) if isinstance(_nested_get(previous, ["summary", "service_ids"]), list) else []))
    current_services = {str(row.get("service")) for row in organ_links if row.get("service")}
    previous_requirements = set(str(item) for item in (_nested_get(previous, ["summary", "requirement_ids"]) if isinstance(_nested_get(previous, ["summary", "requirement_ids"]), list) else []))
    current_requirements = {str(row.get("requirement_id")) for row in stack_requirement_links if row.get("requirement_id")}
    changed_services = sorted(str(row.get("service")) for row in organ_links if row.get("state_changed_since_previous_autolink") is True)
    changed_requirements = sorted(str(row.get("requirement_id")) for row in stack_requirement_links if row.get("state_changed_since_previous_autolink") is True)
    previous_seen = previous.get("schema") == f"{schema_prefix}_self_awareness_autolink_v1" if isinstance(previous, Mapping) else False
    added_services = sorted(current_services - previous_services)
    removed_services = sorted(previous_services - current_services)
    added_requirements = sorted(current_requirements - previous_requirements)
    removed_requirements = sorted(previous_requirements - current_requirements)
    state_changed = bool(
        previous_seen
        and (
            not previous_digest
            or previous_digest != state_digest
            or added_services
            or removed_services
            or changed_services
            or added_requirements
            or removed_requirements
            or changed_requirements
        )
    )
    state_delta = {
        "schema": f"{schema_prefix}_self_awareness_autolink_state_delta_v1",
        "previous_seen": previous_seen,
        "previous_generated_at": previous.get("generated_at") if isinstance(previous, Mapping) else None,
        "previous_state_digest": previous_digest,
        "current_state_digest": state_digest,
        "state_changed": state_changed,
        "added_services": added_services,
        "removed_services": removed_services,
        "changed_services": changed_services,
        "added_requirements": added_requirements,
        "removed_requirements": removed_requirements,
        "changed_requirements": changed_requirements,
        "open_stack_requirements_delta": _safe_int(_nested_get(stack_closure_dossier_doc, ["summary", "open_stack_requirements"]), 0) - _safe_int(_nested_get(previous, ["summary", "open_stack_requirements"]), 0),
        "working_stack_usage_gaps_delta": _safe_int(_nested_get(working_stack_doc, ["summary", "usage_gaps"]), 0) - _safe_int(_nested_get(previous, ["summary", "working_stack_usage_gaps"]), 0),
        "policy": {"read_only": True, "host_layer_mutates_stack": False, "executes_commands": False},
    }

    gap_row = next((row for row in organ_links if row.get("usage_gap")), organ_links[0] if organ_links else {})
    open_requirement_rows = [row for row in stack_requirement_links if row.get("automatic_link_state") == "open_stack_blocker"]
    requirement_row = open_requirement_rows[0] if open_requirement_rows else stack_requirement_links[0] if stack_requirement_links else {}
    synthetic_scenarios = [
        {
            "schema": f"{schema_prefix}_self_awareness_autolink_synthetic_scenario_v1",
            "id": "organ_time_space_context_replay",
            "selected": gap_row.get("service"),
            "complete": bool(
                gap_row
                and gap_row.get("complete") is True
                and (
                    not gap_row.get("usage_gap")
                    or (
                        _nested_get(gap_row, ["activation_smoke", "complete"]) is True
                        and _nested_get(gap_row, ["activation_smoke", "working_stack_link_id"]) == gap_row.get("working_stack_link_id")
                    )
                )
            ),
            "checks": {
                "organ_link": bool(gap_row.get("working_stack_link_id")),
                "time": bool(_nested_get(gap_row, ["time", "bucket"])),
                "space": bool(_nested_get(gap_row, ["space", "nodes"])),
                "context": bool(_nested_get(gap_row, ["context", "key"])),
                "episode": bool(gap_row.get("episode_ids")),
                "activation_replay_if_gap": bool(
                    not gap_row.get("usage_gap")
                    or (
                        _nested_get(gap_row, ["activation_smoke", "complete"]) is True
                        and _nested_get(gap_row, ["activation_smoke", "working_stack_link_id"]) == gap_row.get("working_stack_link_id")
                    )
                ),
            },
            "evidence_refs": gap_row.get("evidence_refs") if isinstance(gap_row.get("evidence_refs"), list) else [],
            "policy": {"host_layer_mutates_stack": False, "executes_commands": False, "action_execution": False},
        },
        {
            "schema": f"{schema_prefix}_self_awareness_autolink_synthetic_scenario_v1",
            "id": "stack_blocker_owner_routed_context",
            "selected": requirement_row.get("requirement_id"),
            "complete": bool(not stack_requirement_links or requirement_row.get("complete") is True),
            "checks": {
                "requirement_present": bool(not stack_requirement_links or requirement_row.get("requirement_id")),
                "closure_acceptance": bool(not stack_requirement_links or _nested_get(requirement_row, ["checks", "closure_acceptance"]) is True),
                "coverage_impact": bool(not stack_requirement_links or _nested_get(requirement_row, ["checks", "coverage_impact"]) is True),
                "episode_or_closed_state": bool(
                    not stack_requirement_links
                    or requirement_row.get("episode_ids")
                    or (
                        requirement_row.get("automatic_link_state") == "closed"
                        and requirement_row.get("closed_by_current_probe") is True
                    )
                ),
                "owner_route": bool(not stack_requirement_links or requirement_row.get("owner") == "abyss-stack"),
            },
            "evidence_refs": requirement_row.get("evidence_refs") if isinstance(requirement_row.get("evidence_refs"), list) else [],
            "policy": {"host_layer_mutates_stack": False, "executes_commands": False, "action_execution": False},
        },
        {
            "schema": f"{schema_prefix}_self_awareness_autolink_synthetic_scenario_v1",
            "id": "state_delta_digest",
            "selected": state_digest,
            "complete": bool(state_digest and isinstance(state_delta, Mapping)),
            "checks": {
                "state_digest": bool(state_digest),
                "previous_allowed_empty": state_delta.get("previous_seen") is True or previous_digest in (None, ""),
                "delta_lists": all(isinstance(state_delta.get(key), list) for key in ("added_services", "removed_services", "changed_services", "added_requirements", "removed_requirements", "changed_requirements")),
            },
            "evidence_refs": [{"path": str(latest_paths.get("autolink") or ""), "previous_generated_at": state_delta.get("previous_generated_at")}],
            "policy": {"host_layer_mutates_stack": False, "executes_commands": False, "action_execution": False},
        },
    ]

    incomplete_organs = [str(row.get("service")) for row in organ_links if row.get("complete") is not True]
    incomplete_requirements = [str(row.get("requirement_id")) for row in stack_requirement_links if row.get("complete") is not True]
    incomplete_scenarios = [str(row.get("id")) for row in synthetic_scenarios if row.get("complete") is not True]
    return {
        "schema": f"{schema_prefix}_self_awareness_autolink_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": bool(organ_links) and not incomplete_organs and not incomplete_requirements and not incomplete_scenarios,
        "status": "linked" if not incomplete_organs and not incomplete_requirements and not incomplete_scenarios else "incomplete",
        "cycle_id": cycle_id,
        "probe_run_id": probe_run_id,
        "state_digest": state_digest,
        "state_delta": state_delta,
        "summary": {
            "organ_links": len(organ_links),
            "organ_links_complete": sum(1 for row in organ_links if row.get("complete") is True),
            "stack_requirement_links": len(stack_requirement_links),
            "stack_requirement_links_complete": sum(1 for row in stack_requirement_links if row.get("complete") is True),
            "working_stack_usage_gaps": _safe_int(_nested_get(working_stack_doc, ["summary", "usage_gaps"]), 0),
            "open_stack_requirements": _safe_int(_nested_get(stack_closure_dossier_doc, ["summary", "open_stack_requirements"]), 0),
            "synthetic_scenarios": len(synthetic_scenarios),
            "synthetic_scenarios_complete": sum(1 for row in synthetic_scenarios if row.get("complete") is True),
            "incomplete_organs": incomplete_organs,
            "incomplete_requirements": incomplete_requirements,
            "incomplete_scenarios": incomplete_scenarios,
            "service_ids": sorted(current_services),
            "requirement_ids": sorted(current_requirements),
            "state_changed": state_delta["state_changed"],
            "changed_services": changed_services,
            "changed_requirements": changed_requirements,
            "dependency_refresh_applied": bool(dependency_refresh),
        },
        "dependency_refresh": dict(dependency_refresh) if dependency_refresh else None,
        "organ_links": organ_links,
        "organ_links_by_service": {str(row.get("service")): row for row in organ_links if row.get("service")},
        "stack_requirement_links": stack_requirement_links,
        "stack_requirement_links_by_requirement": {str(row.get("requirement_id")): row for row in stack_requirement_links if row.get("requirement_id")},
        "synthetic_scenarios": synthetic_scenarios,
        "evidence_refs": [
            {"path": str(latest_paths.get("working_stack") or ""), "schema": working_stack_doc.get("schema")},
            {"path": str(latest_paths.get("coverage_audit") or ""), "schema": coverage_audit_doc.get("schema")},
            {"path": str(latest_paths.get("stack_closure_dossier") or ""), "schema": stack_closure_dossier_doc.get("schema")},
            {"path": str(latest_paths.get("activation_smoke") or ""), "schema": activation_smoke_doc.get("schema")},
            {"path": str(latest_paths.get("episodes") or ""), "schema": episodes_doc.get("schema")},
        ],
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "executes_commands": False,
            "action_execution": False,
            "automatic_remediation": False,
            "raw_evidence_is_not_truth": True,
            "open_stack_requirements_are_blockers_not_host_failures": True,
            "working_stack_usage_gaps_are_open_potential_not_host_failures": True,
        },
        "tests": {
            "smoke": "abyss-machine self-awareness autolink --json",
            "cycle": "abyss-machine self-awareness cycle --json includes autolink in chain and export",
            "synthetic": "synthetic_scenarios prove organ link, stack blocker owner route, and state delta digest",
        },
    }


def episodes_cover_stack_requirements(
    episodes_doc: Any,
    stack_closure_dossier_doc: Any,
    *,
    schema_prefix: str,
) -> bool:
    if (
        not isinstance(episodes_doc, Mapping)
        or episodes_doc.get("schema") != f"{schema_prefix}_self_awareness_episodes_v1"
    ):
        return False
    entries = (
        stack_closure_dossier_doc.get("entries")
        if isinstance(stack_closure_dossier_doc, Mapping)
        and isinstance(stack_closure_dossier_doc.get("entries"), list)
        else []
    )
    open_requirement_ids = {
        str(entry.get("requirement_id") or "")
        for entry in entries
        if isinstance(entry, Mapping)
        and entry.get("requirement_id")
        and not (entry.get("closed_by_current_probe") is True or entry.get("status") == "closed")
    }
    open_requirement_ids.discard("")
    if not open_requirement_ids:
        return True
    covered_requirement_ids: set[str] = set()
    for episode in episodes_doc.get("episodes", []) if isinstance(episodes_doc.get("episodes"), list) else []:
        if not isinstance(episode, Mapping):
            continue
        requirement_id = str(episode.get("requirement_id") or "")
        if requirement_id:
            covered_requirement_ids.add(requirement_id)
        for node in episode.get("affected_spatial_nodes", []) if isinstance(episode.get("affected_spatial_nodes"), list) else []:
            node_text = str(node)
            if node_text.startswith("stack_requirement:"):
                covered_requirement_ids.add(node_text.split(":", 1)[1])
    return open_requirement_ids <= covered_requirement_ids


def activation_entries_from_link_rows(link_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for row in link_rows:
        if not isinstance(row, Mapping) or not row.get("usage_gap"):
            continue
        entries.append({
            "service": row.get("service"),
            "machine_usage_status": row.get("machine_usage_status"),
            "working_stack_link_id": row.get("working_stack_link_id"),
        })
    return entries


def activation_entries_cover_expected(
    activation_entries: list[dict[str, Any]],
    expected_entries: list[dict[str, Any]],
) -> bool:
    expected = {
        (
            str(entry.get("service") or ""),
            str(entry.get("machine_usage_status") or ""),
            str(entry.get("working_stack_link_id") or ""),
        )
        for entry in expected_entries
        if isinstance(entry, Mapping) and entry.get("service")
    }
    actual = {
        (
            str(entry.get("service") or ""),
            str(entry.get("machine_usage_status") or ""),
            str(entry.get("working_stack_link_id") or ""),
        )
        for entry in activation_entries
        if isinstance(entry, Mapping) and entry.get("service")
    }
    return bool(expected) and expected == actual


def stack_requirement_handoff_route(
    requirement_id: str,
    *,
    episode_id: str | None = None,
    stack_handoff: Mapping[str, Any] | None = None,
    closure_packet: Mapping[str, Any] | None = None,
    stack_replay: Mapping[str, Any] | None = None,
    schema_prefix: str,
    stack_closure_dossier_latest_path: Path | str,
    requirement_probes_latest_path: Path | str,
    replay_latest_path: Path | str,
    closure_acceptance_complete: Callable[[Any], bool],
) -> dict[str, Any]:
    requirement_id = str(requirement_id or "").strip()
    if not requirement_id:
        return {}
    stack_handoff = stack_handoff if isinstance(stack_handoff, Mapping) else {}
    closure_packet = closure_packet if isinstance(closure_packet, Mapping) else {}
    stack_replay = stack_replay if isinstance(stack_replay, Mapping) else {}
    marker = stack_handoff.get("marker") if isinstance(stack_handoff.get("marker"), Mapping) else {}
    closure_readiness = marker.get("closure_readiness") if isinstance(marker.get("closure_readiness"), Mapping) else {}
    coverage_impact = marker.get("coverage_impact") if isinstance(marker.get("coverage_impact"), Mapping) else {}
    if not coverage_impact:
        coverage_impact = _nested_get(closure_packet, ["stack_compat_requirement", "coverage_contract"]) or {}
    safe_next = stack_handoff.get("safe_next_action") if isinstance(stack_handoff.get("safe_next_action"), Mapping) else {}
    if not safe_next:
        safe_next = marker.get("safe_next_action") if isinstance(marker.get("safe_next_action"), Mapping) else {}
    if not safe_next:
        safe_next = closure_packet.get("safe_next_action") if isinstance(closure_packet.get("safe_next_action"), Mapping) else {}
    verifier_commands = [
        str(item)
        for item in (
            stack_handoff.get("verifier_commands")
            if isinstance(stack_handoff.get("verifier_commands"), list)
            else marker.get("verifier_commands")
            if isinstance(marker.get("verifier_commands"), list)
            else closure_readiness.get("verifier_commands")
            if isinstance(closure_readiness.get("verifier_commands"), list)
            else []
        )
        if item
    ]
    if not verifier_commands:
        verifier_commands = [
            "abyss-machine self-awareness capabilities --json",
            "abyss-machine self-awareness requirements --json",
            "abyss-machine self-awareness cycle --json",
            "abyss-machine self-awareness validate --json",
            "abyss-machine stack-bridge validate --json",
        ]
    closure_blocker_keys = [
        str(item)
        for item in (
            stack_handoff.get("closure_blocker_keys")
            if isinstance(stack_handoff.get("closure_blocker_keys"), list)
            else marker.get("closure_blocker_keys")
            if isinstance(marker.get("closure_blocker_keys"), list)
            else closure_readiness.get("blocking_check_keys")
            if isinstance(closure_readiness.get("blocking_check_keys"), list)
            else _nested_get(closure_packet, ["pre_close_identity", "missing_check_keys"])
            if isinstance(_nested_get(closure_packet, ["pre_close_identity", "missing_check_keys"]), list)
            else []
        )
        if item
    ]
    missing_check_keys = [
        str(item)
        for item in (
            _nested_get(closure_packet, ["pre_close_identity", "missing_check_keys"])
            if isinstance(_nested_get(closure_packet, ["pre_close_identity", "missing_check_keys"]), list)
            else closure_readiness.get("blocking_check_keys")
            if isinstance(closure_readiness.get("blocking_check_keys"), list)
            else closure_blocker_keys
        )
        if item
    ]
    fulfilled_check_keys = [
        str(item)
        for item in (
            _nested_get(closure_packet, ["pre_close_identity", "fulfilled_check_keys"])
            if isinstance(_nested_get(closure_packet, ["pre_close_identity", "fulfilled_check_keys"]), list)
            else [
                check.get("key")
                for check in (closure_readiness.get("fulfilled_checks") if isinstance(closure_readiness.get("fulfilled_checks"), list) else [])
                if isinstance(check, Mapping)
            ]
        )
        if item
    ]
    coverage_planes = [
        str(item)
        for item in (
            coverage_impact.get("coverage_planes")
            if isinstance(coverage_impact, Mapping) and isinstance(coverage_impact.get("coverage_planes"), list)
            else marker.get("coverage_planes")
            if isinstance(marker.get("coverage_planes"), list)
            else _nested_get(closure_packet, ["pre_close_identity", "coverage_planes"])
            if isinstance(_nested_get(closure_packet, ["pre_close_identity", "coverage_planes"]), list)
            else []
        )
        if item
    ]
    evidence_refs: list[dict[str, Any]] = []
    for source in (
        stack_handoff.get("evidence_refs"),
        marker.get("evidence_refs"),
        closure_readiness.get("evidence_refs"),
        closure_packet.get("evidence_refs"),
    ):
        if isinstance(source, list):
            evidence_refs.extend(dict(item) for item in source if isinstance(item, Mapping))
    evidence_refs.extend([
        {"path": str(stack_closure_dossier_latest_path), "requirement_id": requirement_id, "section": "closure_acceptance_matrix"},
        {"path": str(requirement_probes_latest_path), "requirement_id": requirement_id},
        {"path": str(replay_latest_path), "requirement_id": requirement_id, "section": "stack_handoff_replay"},
    ])
    open_requirement_ids = stack_replay.get("open_requirement_ids") if isinstance(stack_replay.get("open_requirement_ids"), list) else []
    route = {
        "schema": f"{schema_prefix}_self_awareness_stack_requirement_handoff_route_v1",
        "route_id": "sastackreqroute-" + self_awareness_contracts.stable_hash_json({
            "episode_id": episode_id,
            "requirement_id": requirement_id,
            "current_state_digest": _nested_get(closure_packet, ["pre_close_identity", "current_state_digest"]) or _nested_get(closure_packet, ["closure_diff_contract", "current_state_digest_before"]),
        }, length=24),
        "episode_id": episode_id,
        "requirement_id": requirement_id,
        "owner_route": "abyss-stack",
        "machine_action": "handoff_only",
        "status": closure_packet.get("status") or closure_readiness.get("status") or "open",
        "requirement_status": closure_packet.get("requirement_status") or marker.get("status") or closure_readiness.get("status"),
        "surface_kind": closure_packet.get("surface_kind") or closure_readiness.get("probe_kind") or _nested_get(closure_packet, ["stack_compat_requirement", "surface_kind"]),
        "priority": {
            "class": marker.get("priority_class"),
            "rank": marker.get("priority_rank"),
            "score": marker.get("priority_score"),
            "top_unblocking": bool(_nested_get(closure_packet, ["closure_impact", "is_unblocking_requirement"])),
        },
        "impact": {
            "organ": coverage_impact.get("organ") if isinstance(coverage_impact, Mapping) else None,
            "coverage_planes": coverage_planes,
            "closure_value": coverage_impact.get("closure_value") if isinstance(coverage_impact, Mapping) else None,
            "blocks_stack_usage_requirements": (
                coverage_impact.get("blocks_stack_usage_requirements")
                if isinstance(coverage_impact, Mapping) and isinstance(coverage_impact.get("blocks_stack_usage_requirements"), list)
                else []
            ),
            "depends_on_requirement_ids": _nested_get(closure_packet, ["pre_close_identity", "depends_on_requirement_ids"]) or [],
            "unblocks_requirement_ids": _nested_get(closure_packet, ["pre_close_identity", "unblocks_requirement_ids"]) or [],
        },
        "current_state_identity": {
            "digest": _nested_get(closure_packet, ["pre_close_identity", "current_state_digest"]) or _nested_get(closure_packet, ["closure_diff_contract", "current_state_digest_before"]),
            "keys": _nested_get(closure_packet, ["pre_close_identity", "current_state_keys"]) or _nested_get(closure_readiness, ["current_state_digest", "keys"]) or [],
            "missing_check_keys": missing_check_keys,
            "fulfilled_check_keys": fulfilled_check_keys,
            "readiness_score": closure_readiness.get("readiness_score"),
        },
        "closure_acceptance": {
            "schema": closure_packet.get("schema"),
            "acceptance_id": closure_packet.get("acceptance_id"),
            "complete": closure_acceptance_complete(closure_packet),
            "compat_requirement_id": _nested_get(closure_packet, ["stack_compat_requirement", "requirement_id"]),
            "negative_controls": len(closure_packet.get("negative_controls") if isinstance(closure_packet.get("negative_controls"), list) else []),
            "post_close_success_predicates": len(closure_packet.get("post_close_success_predicates") if isinstance(closure_packet.get("post_close_success_predicates"), list) else []),
            "post_close_verifier_steps": len(closure_packet.get("post_close_verifier_chain") if isinstance(closure_packet.get("post_close_verifier_chain"), list) else []),
        },
        "lineage": {
            "stack_handoff_replayable": stack_replay.get("closure_readiness_replayable"),
            "open_requirement_present_in_replay": requirement_id in {str(item) for item in open_requirement_ids},
            "source_kind": "stack_closure_dossier_and_stack_handoff_replay",
        },
        "closure_blocker_keys": closure_blocker_keys,
        "safe_next_action": dict(safe_next) if isinstance(safe_next, Mapping) else {},
        "verifier_commands": verifier_commands,
        "evidence_refs": evidence_refs[:40],
        "policy": {
            "handoff_only": True,
            "read_only": True,
            "automatic_execution": False,
            "executes_commands": False,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "raw_secret_storage": False,
            "raw_private_payloads": False,
            "open_stack_requirements_are_blockers_not_host_failures": True,
        },
    }
    if not _nested_get(route, ["impact", "organ"]):
        route["impact"]["organ"] = marker.get("impact_organ")
    route["complete"] = stack_requirement_handoff_route_complete(route, schema_prefix=schema_prefix)
    return route


def stack_requirement_handoff_route_complete(route: Any, *, schema_prefix: str) -> bool:
    if not isinstance(route, Mapping):
        return False
    safe_next = route.get("safe_next_action") if isinstance(route.get("safe_next_action"), Mapping) else {}
    policy = route.get("policy") if isinstance(route.get("policy"), Mapping) else {}
    current_state_identity = route.get("current_state_identity") if isinstance(route.get("current_state_identity"), Mapping) else {}
    closure_acceptance = route.get("closure_acceptance") if isinstance(route.get("closure_acceptance"), Mapping) else {}
    lineage = route.get("lineage") if isinstance(route.get("lineage"), Mapping) else {}
    impact = route.get("impact") if isinstance(route.get("impact"), Mapping) else {}
    return (
        route.get("schema") == f"{schema_prefix}_self_awareness_stack_requirement_handoff_route_v1"
        and bool(route.get("route_id"))
        and bool(route.get("requirement_id"))
        and route.get("owner_route") == "abyss-stack"
        and route.get("machine_action") == "handoff_only"
        and bool(route.get("status"))
        and bool(route.get("surface_kind"))
        and bool(impact.get("organ"))
        and isinstance(impact.get("coverage_planes"), list)
        and bool(impact.get("coverage_planes"))
        and bool(current_state_identity.get("digest"))
        and isinstance(current_state_identity.get("missing_check_keys"), list)
        and closure_acceptance.get("complete") is True
        and lineage.get("stack_handoff_replayable") is True
        and lineage.get("open_requirement_present_in_replay") is True
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
        and policy.get("raw_secret_storage") is False
    )


def working_stack_activation_gap_route(
    working_stack_gap: Mapping[str, Any],
    *,
    episode_id: str | None = None,
    activation_row: Mapping[str, Any] | None = None,
    schema_prefix: str,
    working_stack_latest_path: Path | str,
    activation_smoke_latest_path: Path | str,
    episodes_latest_path: Path | str,
    process_container_latest_path: Path | str,
) -> dict[str, Any]:
    working_stack_gap = working_stack_gap if isinstance(working_stack_gap, Mapping) else {}
    service = str(working_stack_gap.get("service") or "")
    status = str(working_stack_gap.get("machine_usage_status") or "unknown")
    evidence_refs = [
        {"path": str(working_stack_latest_path), "service": service, "status": status},
        {"path": str(activation_smoke_latest_path), "service": service, "episode_id": episode_id},
        {"path": str(episodes_latest_path), "episode_id": episode_id, "section": "working_stack_gap"},
        {"path": str(process_container_latest_path), "service": service, "container": working_stack_gap.get("container")},
    ]
    return self_awareness_contracts.working_stack_activation_gap_route(
        dict(working_stack_gap),
        episode_id=episode_id,
        activation_row=dict(activation_row) if isinstance(activation_row, Mapping) else None,
        evidence_refs=evidence_refs,
        schema_prefix=schema_prefix,
    )


def working_stack_activation_gap_route_complete(route: Any, *, schema_prefix: str) -> bool:
    return self_awareness_contracts.working_stack_activation_gap_route_complete(route, schema_prefix=schema_prefix)


def working_stack_activation_synthetic_scenario(
    entry: Mapping[str, Any],
    generated_at: str,
    *,
    schema_prefix: str,
) -> dict[str, Any]:
    entry = entry if isinstance(entry, Mapping) else {}
    service = str(entry.get("service") or "")
    status = str(entry.get("machine_usage_status") or "unknown")
    activation_kind = str(entry.get("activation_kind") or self_awareness_contracts.working_stack_gap_activation_kind(status))
    link_id = str(entry.get("working_stack_link_id") or "")
    missing_checks = entry.get("missing_checks") if isinstance(entry.get("missing_checks"), list) else []
    fulfilled_checks = entry.get("fulfilled_checks") if isinstance(entry.get("fulfilled_checks"), list) else []
    failed_probe_names = [str(item) for item in (entry.get("failed_probe_names") if isinstance(entry.get("failed_probe_names"), list) else []) if item]
    if not failed_probe_names:
        failed_probe_names = [
            str(check.get("probe"))
            for check in missing_checks
            if isinstance(check, Mapping) and str(check.get("key") or "").startswith("probe_failed:") and check.get("probe")
        ]
    ok_probe_names = [str(item) for item in (entry.get("ok_probe_names") if isinstance(entry.get("ok_probe_names"), list) else []) if item]
    missing_check_keys = [str(check.get("key")) for check in missing_checks if isinstance(check, Mapping) and check.get("key")]
    fulfilled_check_keys = [str(check.get("key")) for check in fulfilled_checks if isinstance(check, Mapping) and check.get("key")]
    verifier_commands = entry.get("verifier_commands") if isinstance(entry.get("verifier_commands"), list) else []
    evidence_refs = entry.get("evidence_refs") if isinstance(entry.get("evidence_refs"), list) else []
    coverage_planes = entry.get("coverage_planes") if isinstance(entry.get("coverage_planes"), list) else self_awareness_contracts.working_stack_gap_coverage_planes(status)
    scenario_id = "sascenario-working-stack-activation-" + self_awareness_contracts.stable_hash_json({
        "service": service,
        "machine_usage_status": status,
        "activation_kind": activation_kind,
    }, length=24)
    current_result = "gap_reproduced"
    if status == "declared_not_running":
        current_result = "declared_service_absent_from_runtime"
    elif status == "tool_runtime_degraded":
        current_result = "functional_tool_smoke_failed"
    elif status.endswith("_unproven_deep_use"):
        current_result = "deep_machine_usage_unproven"
    elif status == "model_root_visible":
        current_result = "model_runtime_bridge_unproven"
    synthetic_chain = [
        {
            "step": "inventory",
            "command": "abyss-machine self-awareness working-stack --json",
            "must": [
                f"service {service} is present",
                "working_stack_link_id is stable for the service/status identity while the observed bucket records time",
                "usage_gap and machine_usage_status are explicit",
            ],
        },
        {
            "step": "space",
            "command": "abyss-machine self-awareness spatial-graph --json",
            "must": [
                f"service:{service} and working-stack link nodes exist",
                "owner_surface remains abyss-stack",
            ],
        },
        {
            "step": "causality",
            "command": "abyss-machine self-awareness episodes --json",
            "must": [
                "working_stack_usage_gap episode exists for the service",
                "episode keeps the same machine_usage_status and usage_gap",
            ],
        },
        {
            "step": "reaction",
            "command": "abyss-machine self-awareness alerts --json",
            "must": [
                "owner-gated reaction candidate exists",
                "candidate executes no commands and requires human approval",
            ],
        },
        {
            "step": "investigation_replay",
            "command": "abyss-machine self-awareness investigate --episode-id EPISODE_ID --json; abyss-machine self-awareness replay --thread-id THREAD_ID --json",
            "must": [
                "working_stack_gap packet is preserved through request, brief, conclusion, and replay",
                "replayable=true, divergences=0, host_layer_mutates_stack=false",
            ],
        },
        {
            "step": "coverage_export_cycle",
            "command": "abyss-machine self-awareness coverage-audit --json; abyss-machine self-awareness export --json; abyss-machine self-awareness cycle --json",
            "must": [
                "coverage row, portable export, and cycle agree on activation gap state",
            ],
        },
    ]
    scenario = {
        "schema": f"{schema_prefix}_self_awareness_working_stack_activation_synthetic_scenario_v1",
        "scenario_id": scenario_id,
        "generated_at": generated_at,
        "service": service,
        "owner": "abyss-stack",
        "activation_kind": activation_kind,
        "machine_usage_status": status,
        "working_stack_link_id": link_id or None,
        "current_result": current_result,
        "current_observation": {
            "schema": f"{schema_prefix}_self_awareness_working_stack_activation_synthetic_observation_v1",
            "expected_current_outcome": "open_activation_gap",
            "current_result": current_result,
            "usage_gap": entry.get("usage_gap"),
            "missing_check_keys": missing_check_keys,
            "fulfilled_check_keys": fulfilled_check_keys,
            "failed_probe_names": failed_probe_names,
            "ok_probe_names": ok_probe_names,
            "runtime": entry.get("runtime") if isinstance(entry.get("runtime"), Mapping) else {},
            "coverage_planes": coverage_planes,
        },
        "synthetic_chain": synthetic_chain,
        "closure_predicates": [
            f"working-stack inventory no longer reports usage_gap for {service}",
            f"coverage-audit has no working_stack_gap row for {service}",
            f"episodes/alerts no longer need an open working_stack_usage_gap candidate for {service}",
            "export carries closure evidence refs and no raw secrets/private payloads",
            "cycle keeps automatic_responses=0 and routes_with_mutating_command_if_run=0",
        ],
        "negative_controls": [
            "do not treat endpoint visibility alone as deep use",
            "do not close on a green validator if usage_gap remains in working-stack inventory",
            "do not execute stack service/runtime/model changes from abyss-machine",
            "do not persist raw credentials, prompts, messages, row payloads, or private graph properties",
        ],
        "verifier_commands": verifier_commands,
        "evidence_refs": evidence_refs,
        "policy": {
            "synthetic_only": True,
            "handoff_only": True,
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "action_execution": False,
            "automatic_remediation": False,
            "raw_secrets_included": False,
            "raw_private_content_included": False,
            "stack_owner_may_mutate_after_operator_approval": True,
        },
    }
    scenario["complete"] = working_stack_activation_synthetic_scenario_complete(scenario, schema_prefix=schema_prefix)
    return scenario


def working_stack_activation_synthetic_scenario_complete(scenario: Any, *, schema_prefix: str) -> bool:
    return (
        isinstance(scenario, Mapping)
        and scenario.get("schema") == f"{schema_prefix}_self_awareness_working_stack_activation_synthetic_scenario_v1"
        and bool(scenario.get("scenario_id"))
        and bool(scenario.get("service"))
        and scenario.get("owner") == "abyss-stack"
        and bool(scenario.get("machine_usage_status"))
        and bool(scenario.get("working_stack_link_id"))
        and isinstance(scenario.get("current_observation"), Mapping)
        and scenario["current_observation"].get("schema") == f"{schema_prefix}_self_awareness_working_stack_activation_synthetic_observation_v1"
        and isinstance(_nested_get(scenario, ["current_observation", "missing_check_keys"]), list)
        and bool(_nested_get(scenario, ["current_observation", "missing_check_keys"]))
        and isinstance(scenario.get("synthetic_chain"), list)
        and len(scenario.get("synthetic_chain")) >= 5
        and isinstance(scenario.get("closure_predicates"), list)
        and bool(scenario.get("closure_predicates"))
        and isinstance(scenario.get("negative_controls"), list)
        and bool(scenario.get("negative_controls"))
        and isinstance(scenario.get("verifier_commands"), list)
        and bool(scenario.get("verifier_commands"))
        and bool(scenario.get("evidence_refs"))
        and _nested_get(scenario, ["policy", "synthetic_only"]) is True
        and _nested_get(scenario, ["policy", "host_layer_mutates_stack"]) is False
        and _nested_get(scenario, ["policy", "executes_commands"]) is False
        and _nested_get(scenario, ["policy", "action_execution"]) is False
        and _nested_get(scenario, ["policy", "automatic_remediation"]) is False
        and _nested_get(scenario, ["policy", "raw_secrets_included"]) is False
    )


def working_stack_activation_closure_acceptance(
    entry: Mapping[str, Any],
    generated_at: str,
    *,
    schema_prefix: str,
) -> dict[str, Any]:
    entry = entry if isinstance(entry, Mapping) else {}
    service = str(entry.get("service") or "")
    status = str(entry.get("machine_usage_status") or "unknown")
    activation_kind = str(entry.get("activation_kind") or self_awareness_contracts.working_stack_gap_activation_kind(status))
    link_id = str(entry.get("working_stack_link_id") or "")
    missing_checks = entry.get("missing_checks") if isinstance(entry.get("missing_checks"), list) else []
    fulfilled_checks = entry.get("fulfilled_checks") if isinstance(entry.get("fulfilled_checks"), list) else []
    missing_keys = [str(item.get("key")) for item in missing_checks if isinstance(item, Mapping) and item.get("key")]
    fulfilled_keys = [str(item.get("key")) for item in fulfilled_checks if isinstance(item, Mapping) and item.get("key")]
    verifier_commands = list(dict.fromkeys([
        *[str(command) for command in (entry.get("verifier_commands") if isinstance(entry.get("verifier_commands"), list) else []) if command],
        "abyss-machine self-awareness activation-smoke --json",
        "abyss-machine self-awareness probe --json",
        "abyss-machine self-awareness validate --json",
    ]))
    source_refs = entry.get("stack_source_refs") if isinstance(entry.get("stack_source_refs"), list) else []
    expected_post_close_facts = [
        {
            "key": "working_stack_usage_gap_closed",
            "must": f"working-stack inventory no longer reports the same usage_gap for {service}",
            "evidence": "abyss-machine self-awareness working-stack --json",
        },
        {
            "key": "coverage_gap_row_absent_or_reclassified",
            "must": f"coverage-audit has no open working_stack_gap row for {service}",
            "evidence": "abyss-machine self-awareness coverage-audit --json",
        },
        {
            "key": "activation_smoke_no_failed_service",
            "must": f"activation-smoke has no failed row for {service}; if the gap is closed the service is absent from open activation rows",
            "evidence": "abyss-machine self-awareness activation-smoke --json",
        },
        {
            "key": "cycle_no_mutating_response",
            "must": "cycle keeps automatic_responses=0 and routes_with_mutating_command_if_run=0",
            "evidence": "abyss-machine self-awareness cycle --json",
        },
    ]
    if "declared_service_not_running" in missing_keys:
        expected_post_close_facts.append({
            "key": "runtime_container_running",
            "must": f"{service} is running in the stack runtime body or the stack owner removes the declaration from active machine scope",
            "evidence": "abyss-machine self-awareness working-stack --json",
        })
    for key in missing_keys:
        if key.startswith("probe_failed:"):
            probe_name = key.split(":", 1)[1]
            expected_post_close_facts.append({
                "key": "probe_ok:" + probe_name,
                "must": f"bounded probe {probe_name} passes for {service}",
                "evidence": "abyss-machine self-awareness working-stack --json",
            })
    if "deep_machine_usage_route_not_proven" in missing_keys:
        expected_post_close_facts.append({
            "key": "deep_machine_usage_route_proven",
            "must": f"abyss-machine proves sustained read-only machine usage route through {service}",
            "evidence": "abyss-machine self-awareness coverage-audit --json",
        })
    if "model_runtime_bridge_not_proven" in missing_keys:
        expected_post_close_facts.append({
            "key": "model_runtime_bridge_active",
            "must": f"{service} model root is linked to a current stack/runtime model bridge",
            "evidence": "abyss-machine self-awareness working-stack --json",
        })
    post_close_verifier_chain = [
        {
            "command": command,
            "must": [
                "evidence refs remain host-owned readmodels",
                "host_layer_mutates_stack=false",
                "raw secrets/private payloads are not exported",
            ],
        }
        for command in verifier_commands
    ]
    compat_requirement_id = "stack.activation." + self_awareness_contracts.stable_hash_json({
        "service": service,
        "status": status,
        "activation_kind": activation_kind,
    }, length=20)
    closure_acceptance = {
        "schema": f"{schema_prefix}_self_awareness_working_stack_activation_closure_acceptance_v1",
        "acceptance_id": "saaccept-working-stack-activation-" + self_awareness_contracts.stable_hash_json({
            "service": service,
            "machine_usage_status": status,
            "working_stack_link_id": link_id,
        }, length=24),
        "generated_at": generated_at,
        "service": service,
        "owner": "abyss-stack",
        "status": "awaiting_stack_owner_change" if missing_keys else "satisfied",
        "activation_kind": activation_kind,
        "machine_usage_status": status,
        "working_stack_link_id": link_id or None,
        "pre_close_identity": {
            "schema": f"{schema_prefix}_self_awareness_working_stack_activation_pre_close_identity_v1",
            "usage_gap": entry.get("usage_gap"),
            "current_state_digest": entry.get("current_state_digest"),
            "closure_blocker_keys": entry.get("closure_blocker_keys") if isinstance(entry.get("closure_blocker_keys"), list) else [],
            "missing_check_keys": missing_keys,
            "fulfilled_check_keys": fulfilled_keys,
        },
        "stack_compat_requirement": {
            "schema": f"{schema_prefix}_self_awareness_working_stack_activation_compat_requirement_v1",
            "requirement_id": compat_requirement_id,
            "owner": "abyss-stack",
            "consumer": "abyss-machine",
            "surface_kind": "working_stack_service_activation",
            "service": service,
            "activation_kind": activation_kind,
            "required_stack_outcome": "close the specific machine usage gap without weakening owner boundaries",
            "stack_source_refs": source_refs[:24],
            "machine_consumer_contract": {
                "post_close_verifiers": verifier_commands,
                "expected_post_close_facts": expected_post_close_facts,
            },
            "operator_boundary": {
                "operator_approval_required": True,
                "abyss_machine_executes_stack_change": False,
                "host_layer_mutates_stack": False,
            },
            "redaction_contract": {
                "raw_secrets_allowed": False,
                "raw_private_payloads_allowed": False,
                "evidence_refs_required": True,
            },
            "policy": {
                "handoff_only": True,
                "read_only": True,
                "host_layer_mutates_stack": False,
                "executes_commands": False,
                "action_execution": False,
            },
        },
        "closure_diff_contract": {
            "schema": f"{schema_prefix}_self_awareness_working_stack_activation_closure_diff_contract_v1",
            "before": {
                "service": service,
                "machine_usage_status": status,
                "working_stack_link_id": link_id or None,
                "missing_check_keys": missing_keys,
            },
            "after_must": expected_post_close_facts,
            "not_sufficient": [
                "green self-awareness validate while the same working-stack usage gap remains open",
                "endpoint visibility without deep machine usage proof",
                "manual stack change without post-close activation-smoke and cycle evidence",
            ],
        },
        "post_close_success_predicates": expected_post_close_facts,
        "post_close_verifier_chain": post_close_verifier_chain,
        "negative_controls": [
            "do not let abyss-machine start/stop/reconfigure stack services",
            "do not close this acceptance if service/status/link identity does not match",
            "do not treat stale latest artifacts as closure evidence",
            "do not export credentials, prompts, private payloads, database rows, or graph properties",
        ],
        "evidence_refs": entry.get("evidence_refs") if isinstance(entry.get("evidence_refs"), list) else [],
        "policy": {
            "handoff_only": True,
            "read_only": True,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "executes_commands": False,
            "action_execution": False,
            "automatic_remediation": False,
            "raw_secrets_included": False,
            "raw_private_content_included": False,
        },
    }
    closure_acceptance["complete"] = working_stack_activation_closure_acceptance_complete(closure_acceptance, schema_prefix=schema_prefix)
    return closure_acceptance


def working_stack_activation_closure_acceptance_complete(packet: Any, *, schema_prefix: str) -> bool:
    if not isinstance(packet, Mapping):
        return False
    pre_close = packet.get("pre_close_identity") if isinstance(packet.get("pre_close_identity"), Mapping) else {}
    compat = packet.get("stack_compat_requirement") if isinstance(packet.get("stack_compat_requirement"), Mapping) else {}
    diff = packet.get("closure_diff_contract") if isinstance(packet.get("closure_diff_contract"), Mapping) else {}
    return (
        packet.get("schema") == f"{schema_prefix}_self_awareness_working_stack_activation_closure_acceptance_v1"
        and bool(packet.get("acceptance_id"))
        and bool(packet.get("service"))
        and packet.get("owner") == "abyss-stack"
        and bool(packet.get("machine_usage_status"))
        and bool(packet.get("working_stack_link_id"))
        and pre_close.get("schema") == f"{schema_prefix}_self_awareness_working_stack_activation_pre_close_identity_v1"
        and bool(pre_close.get("usage_gap"))
        and bool(pre_close.get("missing_check_keys"))
        and compat.get("schema") == f"{schema_prefix}_self_awareness_working_stack_activation_compat_requirement_v1"
        and bool(compat.get("requirement_id"))
        and compat.get("owner") == "abyss-stack"
        and compat.get("consumer") == "abyss-machine"
        and _nested_get(compat, ["operator_boundary", "abyss_machine_executes_stack_change"]) is False
        and _nested_get(compat, ["operator_boundary", "host_layer_mutates_stack"]) is False
        and _nested_get(compat, ["redaction_contract", "raw_secrets_allowed"]) is False
        and diff.get("schema") == f"{schema_prefix}_self_awareness_working_stack_activation_closure_diff_contract_v1"
        and isinstance(packet.get("post_close_success_predicates"), list)
        and len(packet.get("post_close_success_predicates")) >= 4
        and isinstance(packet.get("post_close_verifier_chain"), list)
        and len(packet.get("post_close_verifier_chain")) >= 5
        and isinstance(packet.get("negative_controls"), list)
        and bool(packet.get("negative_controls"))
        and bool(packet.get("evidence_refs"))
        and _nested_get(packet, ["policy", "host_layer_mutates_stack"]) is False
        and _nested_get(packet, ["policy", "executes_commands"]) is False
        and _nested_get(packet, ["policy", "action_execution"]) is False
        and _nested_get(packet, ["policy", "automatic_remediation"]) is False
        and _nested_get(packet, ["policy", "raw_secrets_included"]) is False
    )


def working_stack_activation_entry(
    organ: Mapping[str, Any],
    order: int,
    generated_at: str,
    *,
    schema_prefix: str,
    working_stack_latest_path: Path | str,
    spatial_graph_latest_path: Path | str,
    episodes_latest_path: Path | str,
    alerts_latest_path: Path | str,
) -> dict[str, Any]:
    organ = organ if isinstance(organ, Mapping) else {}
    service = str(organ.get("service") or "")
    status = str(organ.get("machine_usage_status") or "unknown")
    gap_reason = str(organ.get("usage_gap") or "")
    activation_kind = self_awareness_contracts.working_stack_gap_activation_kind(status)
    coverage_planes = self_awareness_contracts.working_stack_gap_coverage_planes(status)
    runtime = organ.get("runtime") if isinstance(organ.get("runtime"), Mapping) else {}
    declared = organ.get("declared") if isinstance(organ.get("declared"), Mapping) else {}
    link = organ.get("time_space_context_link") if isinstance(organ.get("time_space_context_link"), Mapping) else {}
    link_id = str(link.get("link_id") or _nested_get(link, ["context", "working_stack_link_id"]) or "")
    probes = [
        probe for probe in (organ.get("endpoint_probes") if isinstance(organ.get("endpoint_probes"), list) else [])
        if isinstance(probe, Mapping)
    ]
    failed_probes = [
        {
            "probe": probe.get("probe"),
            "ok": probe.get("ok"),
            "kind": probe.get("kind"),
            "status_code": probe.get("status_code"),
            "error": probe.get("error"),
            "elapsed_ms": probe.get("elapsed_ms"),
        }
        for probe in probes
        if probe.get("ok") is not True
    ]
    ok_probe_names = [str(probe.get("probe")) for probe in probes if probe.get("ok") is True and probe.get("probe")]
    failed_probe_names = [str(probe.get("probe")) for probe in probes if probe.get("ok") is not True and probe.get("probe")]
    fulfilled_checks: list[dict[str, Any]] = []
    missing_checks: list[dict[str, Any]] = [
        {
            "key": "working_stack_usage_gap",
            "level": "open",
            "message": gap_reason,
            "status": status,
        }
    ]
    if link_id:
        fulfilled_checks.append({"key": "working_stack_time_space_context_link", "ok": True, "link_id": link_id})
    else:
        missing_checks.append({"key": "working_stack_time_space_context_link_missing", "level": "fail", "message": "working-stack gap has no stable time-space-context link"})
    if runtime.get("running") is True:
        fulfilled_checks.append({"key": "runtime_container_running", "ok": True, "container": runtime.get("container"), "health": runtime.get("health")})
    elif status == "declared_not_running":
        missing_checks.append({"key": "declared_service_not_running", "level": "open", "message": "declared stack service is not running in the current runtime body"})
    if declared.get("present") is True:
        fulfilled_checks.append({"key": "compose_declaration_present", "ok": True, "modules": declared.get("modules") if isinstance(declared.get("modules"), list) else []})
    if organ.get("endpoint_ok") is True:
        fulfilled_checks.append({"key": "endpoint_probe_ok", "ok": True, "probes": ok_probe_names})
    for probe_name in ok_probe_names:
        fulfilled_checks.append({"key": "probe_ok:" + probe_name, "ok": True, "probe": probe_name})
    for probe_name in failed_probe_names:
        missing_checks.append({"key": "probe_failed:" + probe_name, "level": "open", "message": "bounded working-stack probe failed", "probe": probe_name})
    if status == "tool_runtime_degraded" and not failed_probe_names:
        missing_checks.append({"key": "functional_runtime_smoke_not_proven", "level": "open", "message": "tool runtime is degraded but the failed functional smoke is not represented"})
    if status in {"runtime_visible_unproven_deep_use", "endpoint_visible_unproven_deep_use", "tool_guard_visible_unproven_deep_use"}:
        missing_checks.append({"key": "deep_machine_usage_route_not_proven", "level": "open", "message": "machine has visibility but no sustained reasoning/action route through this stack organ"})
    model_bridge = organ.get("model_bridge") if isinstance(organ.get("model_bridge"), Mapping) else {}
    if model_bridge.get("active") is True:
        fulfilled_checks.append({"key": "model_runtime_bridge_active", "ok": True, "model_bridge_id": model_bridge.get("bridge_id")})
    elif status == "model_root_visible":
        missing_checks.append({"key": "model_runtime_bridge_not_proven", "level": "open", "message": "model root is visible without a current service/runtime linkage"})
    stack_source_refs = organ.get("stack_source_refs") if isinstance(organ.get("stack_source_refs"), list) else []
    if stack_source_refs:
        fulfilled_checks.append({"key": "stack_source_refs_read_only", "ok": True, "count": len(stack_source_refs)})

    missing_checks = [item for index, item in enumerate(missing_checks) if item.get("key") and item.get("key") not in {m.get("key") for m in missing_checks[:index]}]
    fulfilled_checks = [item for index, item in enumerate(fulfilled_checks) if item.get("key") and item.get("key") not in {m.get("key") for m in fulfilled_checks[:index]}]
    closure_blocker_keys = [str(item.get("key")) for item in missing_checks if item.get("key")]
    verifier_commands = list(dict.fromkeys([
        *self_awareness_contracts.working_stack_gap_verifier_commands(service),
        "abyss-machine self-awareness stack-closure-dossier --json",
        "abyss-machine self-awareness coverage-audit --json",
        "abyss-machine self-awareness cycle --json",
    ]))
    safe_next_action = self_awareness_contracts.working_stack_gap_safe_next_action(service, status, gap_reason)
    safe_next_action["verifier_commands"] = verifier_commands
    activation_score = round(len(fulfilled_checks) / max(1, len(fulfilled_checks) + len(missing_checks)), 2)
    evidence_refs = [
        {"path": str(working_stack_latest_path), "schema": f"{schema_prefix}_self_awareness_working_stack_inventory_v1", "service": service},
        {"path": str(spatial_graph_latest_path), "service": service, "node": "service:" + service},
        {"path": str(episodes_latest_path), "episode_kind": "working_stack_usage_gap", "service": service},
        {"path": str(alerts_latest_path), "candidate_kind": "working_stack_gap", "service": service},
    ]
    evidence_refs.extend(organ.get("evidence_refs") if isinstance(organ.get("evidence_refs"), list) else [])
    current_state = {
        "service": service,
        "machine_usage_status": status,
        "activation_kind": activation_kind,
        "runtime": {
            "present": bool(runtime and runtime.get("present") is not False),
            "running": runtime.get("running"),
            "container": runtime.get("container"),
            "health": runtime.get("health"),
            "state": runtime.get("state"),
            "status": runtime.get("status"),
        },
        "declared": declared,
        "endpoint_ok": organ.get("endpoint_ok"),
        "deep_usage_proven": organ.get("deep_usage_proven"),
        "working_stack_link_id": link_id or None,
        "failed_probe_names": failed_probe_names,
        "ok_probe_names": ok_probe_names,
        "observed_at": _nested_get(link, ["time", "observed_at"]) or generated_at,
    }
    runbook_candidate = {
        "schema": f"{schema_prefix}_self_awareness_working_stack_activation_runbook_candidate_v1",
        "id": "stack-activation-runbook-" + self_awareness_contracts.stable_hash_json({"service": service, "status": status}, length=20),
        "service": service,
        "owner": "abyss-stack",
        "status": "open_activation_gap",
        "activation_kind": activation_kind,
        "machine_action": "handoff_only",
        "source_command": "abyss-machine self-awareness stack-closure-dossier --json",
        "host_layer_mutates_stack": False,
        "machine_executes_stack_change": False,
        "stack_owner_may_mutate_stack": True,
        "operator_approval_required": True,
        "proposed_stack_work": [
            "stack owner reviews service runtime declaration, container state, bounded probes, and intended machine usage route",
            "stack owner enables or repairs the service/tool/model route only after operator approval",
            "abyss-machine re-runs read-only smoke, coverage audit, cycle, and validation after the stack-owned change",
        ],
        "acceptance_steps": [
            "working-stack inventory keeps the service linked by service, time bucket, owner surface, and working_stack_link_id",
            "service no longer appears in machine_usage_gaps for the same gap reason",
            "causal episode, alert candidate, investigation replay, coverage audit, export, and cycle agree on closure without stack mutation claims",
        ],
        "acceptance_verifiers": [
            {"command": command, "must": ["current evidence refs remain host-owned readmodels", "host_layer_mutates_stack=false", "executes_commands=false"]}
            for command in verifier_commands
        ],
        "risk": "stack runtime/service/model activation can change resource pressure and dependent routes; machine records only handoff evidence",
        "blast_radius": ["abyss-stack service runtime", "machine self-awareness coverage", "operator-visible stack closure route"],
        "rollback": "stack owner reverts stack service/runtime change; abyss-machine regenerates read-only latest/history artifacts",
        "evidence_refs": evidence_refs,
        "policy": {
            "handoff_only": True,
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "action_execution": False,
            "raw_secrets_included": False,
        },
    }
    activation_readiness = {
        "schema": f"{schema_prefix}_self_awareness_working_stack_activation_readiness_v1",
        "service": service,
        "owner": "abyss-stack",
        "status": "open_activation_gap",
        "activation_kind": activation_kind,
        "readiness_score": activation_score,
        "open_blocker_count": len(missing_checks),
        "fulfilled_checks": fulfilled_checks,
        "missing_checks": missing_checks,
        "blocking_check_keys": closure_blocker_keys,
        "coverage_planes": coverage_planes,
        "closure_evidence_needed": [
            "bounded read-only service/tool/model smoke evidence",
            "fresh working-stack inventory without this usage gap",
            "matching causal/replay/export/coverage evidence after stack-owner activation",
        ],
        "required_fields": [
            "service",
            "machine_usage_status",
            "working_stack_link_id",
            "bounded smoke or runtime evidence",
            "evidence_refs",
            "policy.host_layer_mutates_stack=false",
        ],
        "success_predicates": [
            "service has a current time-space-context link",
            "functional runtime smoke passes when the service is a tool",
            "declared service is running when closure depends on runtime presence",
            "machine route proves deep usage without raw private payloads",
        ],
        "redaction_rules": ["no credentials", "no raw private payloads", "no prompts/messages/row bodies"],
        "boundedness": {"max_probe_rows": 32, "raw_private_content_allowed": False, "stack_mutation_allowed": False},
        "safe_next_action": safe_next_action,
        "verifier_commands": verifier_commands,
        "policy": {
            "handoff_only": True,
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "action_execution": False,
            "raw_secrets_included": False,
        },
    }
    entry = {
        "schema": f"{schema_prefix}_self_awareness_working_stack_activation_entry_v1",
        "order": order,
        "service": service,
        "owner": "abyss-stack",
        "activation_kind": activation_kind,
        "machine_usage_status": status,
        "usage_gap": gap_reason,
        "working_stack_link_id": link_id or None,
        "runtime": current_state["runtime"],
        "declared": declared,
        "endpoint_ok": organ.get("endpoint_ok"),
        "deep_usage_proven": organ.get("deep_usage_proven"),
        "coverage_planes": coverage_planes,
        "blocked_coverage_planes": coverage_planes,
        "closure_blocker_keys": closure_blocker_keys,
        "current_state": current_state,
        "current_state_digest": self_awareness_contracts.stable_hash_json(current_state, length=24),
        "fulfilled_checks": fulfilled_checks,
        "missing_checks": missing_checks,
        "failed_probes": failed_probes,
        "failed_probe_names": failed_probe_names,
        "ok_probe_names": ok_probe_names,
        "activation_readiness": activation_readiness,
        "safe_next_action": safe_next_action,
        "runbook_candidate": runbook_candidate,
        "verifier_commands": verifier_commands,
        "evidence_refs": evidence_refs,
        "stack_source_refs": stack_source_refs[:24],
        "policy": {
            "handoff_only": True,
            "read_only": True,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "executes_commands": False,
            "action_execution": False,
            "raw_secrets_included": False,
            "working_stack_gap_is_open_potential_not_host_failure": True,
        },
    }
    entry["closure_acceptance"] = working_stack_activation_closure_acceptance(
        entry,
        generated_at,
        schema_prefix=schema_prefix,
    )
    entry["synthetic_scenario"] = working_stack_activation_synthetic_scenario(
        entry,
        generated_at,
        schema_prefix=schema_prefix,
    )
    entry["complete"] = working_stack_activation_entry_complete(entry, schema_prefix=schema_prefix)
    return entry


def working_stack_activation_entry_complete(entry: Any, *, schema_prefix: str) -> bool:
    return (
        isinstance(entry, Mapping)
        and entry.get("schema") == f"{schema_prefix}_self_awareness_working_stack_activation_entry_v1"
        and bool(entry.get("service"))
        and entry.get("owner") == "abyss-stack"
        and bool(entry.get("usage_gap"))
        and bool(entry.get("machine_usage_status"))
        and bool(entry.get("working_stack_link_id"))
        and isinstance(entry.get("coverage_planes"), list)
        and bool(entry.get("coverage_planes"))
        and isinstance(entry.get("closure_blocker_keys"), list)
        and bool(entry.get("closure_blocker_keys"))
        and isinstance(entry.get("missing_checks"), list)
        and bool(entry.get("missing_checks"))
        and isinstance(entry.get("fulfilled_checks"), list)
        and isinstance(entry.get("activation_readiness"), Mapping)
        and entry["activation_readiness"].get("schema") == f"{schema_prefix}_self_awareness_working_stack_activation_readiness_v1"
        and bool(entry["activation_readiness"].get("verifier_commands"))
        and isinstance(entry.get("runbook_candidate"), Mapping)
        and entry["runbook_candidate"].get("machine_executes_stack_change") is False
        and entry["runbook_candidate"].get("host_layer_mutates_stack") is False
        and working_stack_activation_closure_acceptance_complete(entry.get("closure_acceptance"), schema_prefix=schema_prefix)
        and working_stack_activation_synthetic_scenario_complete(entry.get("synthetic_scenario"), schema_prefix=schema_prefix)
        and isinstance(entry.get("safe_next_action"), Mapping)
        and entry["safe_next_action"].get("requires_human_approval") is True
        and entry["safe_next_action"].get("host_layer_mutates_stack") is False
        and entry["safe_next_action"].get("executes_commands") is False
        and isinstance(entry.get("verifier_commands"), list)
        and bool(entry.get("verifier_commands"))
        and bool(entry.get("evidence_refs"))
        and _nested_get(entry, ["policy", "host_layer_mutates_stack"]) is False
        and _nested_get(entry, ["policy", "executes_commands"]) is False
        and _nested_get(entry, ["policy", "action_execution"]) is False
        and _nested_get(entry, ["policy", "raw_secrets_included"]) is False
    )



def working_stack_activation_dossier_document(
    working_stack_doc: Mapping[str, Any],
    *,
    generated_at: str,
    version: str,
    schema_prefix: str,
    working_stack_latest_path: Path | str,
    spatial_graph_latest_path: Path | str,
    episodes_latest_path: Path | str,
    alerts_latest_path: Path | str,
    artifact_refs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    working_stack_doc = working_stack_doc if isinstance(working_stack_doc, Mapping) else {}
    working_stack_organs = [
        organ for organ in (working_stack_doc.get("organs") if isinstance(working_stack_doc.get("organs"), list) else [])
        if isinstance(organ, Mapping) and organ.get("service")
    ]
    working_stack_service_ids = sorted(str(organ.get("service")) for organ in working_stack_organs)
    entries = [
        working_stack_activation_entry(
            organ,
            index,
            generated_at,
            schema_prefix=schema_prefix,
            working_stack_latest_path=working_stack_latest_path,
            spatial_graph_latest_path=spatial_graph_latest_path,
            episodes_latest_path=episodes_latest_path,
            alerts_latest_path=alerts_latest_path,
        )
        for index, organ in enumerate(
            [
                organ for organ in working_stack_organs
                if isinstance(organ, Mapping) and organ.get("service") and organ.get("usage_gap")
            ],
            start=1,
        )
    ]
    synthetic_scenarios = [
        entry.get("synthetic_scenario")
        for entry in entries
        if isinstance(entry.get("synthetic_scenario"), Mapping)
    ]
    synthetic_scenario_by_service = {
        str(scenario.get("service")): scenario
        for scenario in synthetic_scenarios
        if isinstance(scenario, Mapping) and scenario.get("service")
    }
    closure_acceptance_packets = [
        entry.get("closure_acceptance")
        for entry in entries
        if isinstance(entry.get("closure_acceptance"), Mapping)
    ]
    closure_acceptance_by_service = {
        str(packet.get("service")): packet
        for packet in closure_acceptance_packets
        if isinstance(packet, Mapping) and packet.get("service")
    }
    closure_acceptance_matrix = {
        "schema": f"{schema_prefix}_self_awareness_working_stack_activation_closure_acceptance_matrix_v1",
        "generated_at": generated_at,
        "ok": len(closure_acceptance_packets) == len(entries) and all(working_stack_activation_closure_acceptance_complete(packet, schema_prefix=schema_prefix) for packet in closure_acceptance_packets),
        "owner": "abyss-stack",
        "services": sorted(closure_acceptance_by_service),
        "packets": closure_acceptance_packets,
        "packet_by_service": closure_acceptance_by_service,
        "summary": {
            "packets": len(closure_acceptance_packets),
            "complete": sum(1 for packet in closure_acceptance_packets if packet.get("complete") is True),
            "services": len(closure_acceptance_by_service),
            "compat_requirements": len({
                str(_nested_get(packet, ["stack_compat_requirement", "requirement_id"]))
                for packet in closure_acceptance_packets
                if _nested_get(packet, ["stack_compat_requirement", "requirement_id"])
            }),
        },
        "policy": {
            "handoff_only": True,
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "action_execution": False,
            "automatic_remediation": False,
            "raw_secrets_included": False,
        },
    }
    synthetic_scenario_matrix = {
        "schema": f"{schema_prefix}_self_awareness_working_stack_activation_synthetic_scenario_matrix_v1",
        "generated_at": generated_at,
        "ok": len(synthetic_scenarios) == len(entries) and all(working_stack_activation_synthetic_scenario_complete(scenario, schema_prefix=schema_prefix) for scenario in synthetic_scenarios),
        "owner": "abyss-stack",
        "services": sorted(synthetic_scenario_by_service),
        "scenarios": synthetic_scenarios,
        "scenario_by_service": synthetic_scenario_by_service,
        "summary": {
            "scenarios": len(synthetic_scenarios),
            "complete": sum(1 for scenario in synthetic_scenarios if scenario.get("complete") is True),
            "services": len(synthetic_scenario_by_service),
            "open_gap_scenarios": len(synthetic_scenarios),
        },
        "policy": {
            "synthetic_only": True,
            "handoff_only": True,
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "action_execution": False,
            "automatic_remediation": False,
            "raw_secrets_included": False,
        },
    }
    missing_check_total = sum(len(entry.get("missing_checks") if isinstance(entry.get("missing_checks"), list) else []) for entry in entries)
    fulfilled_check_total = sum(len(entry.get("fulfilled_checks") if isinstance(entry.get("fulfilled_checks"), list) else []) for entry in entries)
    verifier_commands = sorted({
        str(command)
        for entry in entries
        for command in (entry.get("verifier_commands") if isinstance(entry.get("verifier_commands"), list) else [])
        if command
    })
    activation_coverage_planes = sorted({
        str(plane)
        for entry in entries
        for plane in (entry.get("coverage_planes") if isinstance(entry.get("coverage_planes"), list) else [])
        if plane
    })
    service_ids = [str(entry.get("service")) for entry in entries if entry.get("service")]
    verifier_chain = [
        {"command": "abyss-machine self-awareness working-stack --json", "must": ["usage-gap services have stable time-space-context links and bounded probe evidence"]},
        {"command": "abyss-machine self-awareness stack-closure-dossier --json", "must": ["working_stack_activation_dossier lists every usage gap as stack-owner handoff work"]},
        {"command": "abyss-machine self-awareness coverage-audit --json", "must": ["working_stack_gap_rows match activation dossier service ids"]},
        {"command": "abyss-machine self-awareness export --json", "must": ["portable export includes working-stack activation handoff"]},
        {"command": "abyss-machine self-awareness cycle --json", "must": ["cycle preserves activation-gap counts and non-mutating response policy"]},
        {"command": "abyss-machine self-awareness validate --json", "must": ["stack_closure_dossier_depth and export_stack_handoff validate activation dossier depth"]},
    ]
    activation_order = [
        {
            "service": entry.get("service"),
            "order": entry.get("order"),
            "activation_kind": entry.get("activation_kind"),
            "machine_usage_status": entry.get("machine_usage_status"),
            "working_stack_link_id": entry.get("working_stack_link_id"),
            "closure_blocker_keys": entry.get("closure_blocker_keys"),
            "safe_next_action": entry.get("safe_next_action"),
            "runbook_candidate_id": _nested_get(entry, ["runbook_candidate", "id"]),
            "closure_acceptance_id": _nested_get(entry, ["closure_acceptance", "acceptance_id"]),
            "compat_requirement_id": _nested_get(entry, ["closure_acceptance", "stack_compat_requirement", "requirement_id"]),
            "synthetic_scenario_id": _nested_get(entry, ["synthetic_scenario", "scenario_id"]),
            "verifier_commands": entry.get("verifier_commands"),
        }
        for entry in entries
    ]
    handoff = {
        "schema": f"{schema_prefix}_self_awareness_working_stack_activation_handoff_v1",
        "owner": "abyss-stack",
        "open_service_ids": service_ids,
        "activation_order": activation_order,
        "synthetic_scenario_ids": [
            str(scenario.get("scenario_id"))
            for scenario in synthetic_scenarios
            if isinstance(scenario, Mapping) and scenario.get("scenario_id")
        ],
        "verifier_chain": verifier_chain,
        "policy": {
            "handoff_only": True,
            "read_only": True,
            "operator_approval_required_before_stack_mutation": True,
            "abyss_machine_executes_stack_change": False,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "actions_executed": False,
        },
    }
    artifact_refs = artifact_refs if isinstance(artifact_refs, Mapping) else {}
    return {
        "schema": f"{schema_prefix}_self_awareness_working_stack_activation_dossier_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": all(working_stack_activation_entry_complete(entry, schema_prefix=schema_prefix) for entry in entries),
        "status": "open_activation_gaps" if entries else "no_open_activation_gaps",
        "summary": {
            "working_stack_organs": len(working_stack_service_ids),
            "working_stack_service_ids": working_stack_service_ids,
            "working_stack_usage_gaps": len(entries),
            "entries": len(entries),
            "open_activation_gaps": len(entries),
            "activation_entries_complete": sum(1 for entry in entries if entry.get("complete") is True),
            "synthetic_scenarios": len(synthetic_scenarios),
            "synthetic_scenarios_complete": sum(1 for scenario in synthetic_scenarios if scenario.get("complete") is True),
            "closure_acceptance_packets": len(closure_acceptance_packets),
            "closure_acceptance_packets_complete": sum(1 for packet in closure_acceptance_packets if packet.get("complete") is True),
            "activation_compat_requirements": _safe_int(_nested_get(closure_acceptance_matrix, ["summary", "compat_requirements"]), 0),
            "missing_checks": missing_check_total,
            "fulfilled_checks": fulfilled_check_total,
            "coverage_planes": activation_coverage_planes,
            "verifier_commands": len(verifier_commands),
            "top_service": service_ids[0] if service_ids else None,
        },
        "open_service_ids": service_ids,
        "activation_order": activation_order,
        "entries": entries,
        "open_activation_gaps": entries,
        "synthetic_scenarios": synthetic_scenarios,
        "synthetic_scenario_matrix": synthetic_scenario_matrix,
        "closure_acceptance_packets": closure_acceptance_packets,
        "closure_acceptance_matrix": closure_acceptance_matrix,
        "working_stack_activation_handoff": handoff,
        "verifier_commands": verifier_commands,
        "verifier_chain": verifier_chain,
        "artifact_refs": dict(artifact_refs),
        "evidence_refs": [
            {"path": str(working_stack_latest_path), "schema": working_stack_doc.get("schema")},
            {"path": str(spatial_graph_latest_path), "schema": f"{schema_prefix}_self_awareness_spatial_graph_v1"},
            {"path": str(episodes_latest_path), "schema": f"{schema_prefix}_self_awareness_episodes_v1"},
            {"path": str(alerts_latest_path), "schema": f"{schema_prefix}_self_awareness_alerts_v1"},
        ],
        "policy": {
            "handoff_only": True,
            "read_only": True,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "executes_commands": False,
            "action_execution": False,
            "raw_secrets_included": False,
            "working_stack_activation_gaps_are_stack_owner_work": True,
            "stack_owner_may_mutate_stack_after_operator_approval": True,
        },
    }

def working_stack_activation_synthetic_proof(
    entry: Mapping[str, Any],
    *,
    generated_at: str,
    working_stack_doc: Mapping[str, Any],
    spatial_doc: Mapping[str, Any],
    episodes_doc: Mapping[str, Any],
    alerts_doc: Mapping[str, Any],
    export_doc: Mapping[str, Any],
    cycle_doc: Mapping[str, Any],
    investigation_doc: Mapping[str, Any],
    replay_doc: Mapping[str, Any],
    coverage_row: Mapping[str, Any] | None = None,
    schema_prefix: str,
    working_stack_latest_path: Path | str,
    spatial_graph_latest_path: Path | str,
    episodes_latest_path: Path | str,
    alerts_latest_path: Path | str,
    investigate_latest_path: Path | str,
    replay_latest_path: Path | str,
    coverage_audit_latest_path: Path | str,
    export_latest_path: Path | str,
    cycle_latest_path: Path | str,
    validate_latest_path: Path | str,
) -> dict[str, Any]:
    entry = entry if isinstance(entry, Mapping) else {}
    service = str(entry.get("service") or "")
    status = str(entry.get("machine_usage_status") or "unknown")
    usage_gap = str(entry.get("usage_gap") or "")
    link_id = str(entry.get("working_stack_link_id") or "")
    service_node_id = f"service:{service}" if service else ""
    link_node_id = f"working_stack_link:{link_id}" if link_id else ""
    coverage_row = coverage_row if isinstance(coverage_row, Mapping) else {}

    organs = working_stack_doc.get("organs") if isinstance(working_stack_doc.get("organs"), list) else []
    organ = next((item for item in organs if isinstance(item, Mapping) and str(item.get("service") or "") == service), {})
    spatial_nodes = spatial_doc.get("nodes") if isinstance(spatial_doc.get("nodes"), list) else []
    spatial_edges = spatial_doc.get("edges") if isinstance(spatial_doc.get("edges"), list) else []
    node_ids = {str(node.get("id")) for node in spatial_nodes if isinstance(node, Mapping) and node.get("id")}
    service_node = next((node for node in spatial_nodes if isinstance(node, Mapping) and str(node.get("id") or "") == service_node_id), {})
    link_node = next((node for node in spatial_nodes if isinstance(node, Mapping) and str(node.get("id") or "") == link_node_id), {})
    usage_gap_nodes = [
        node for node in spatial_nodes
        if isinstance(node, Mapping)
        and node.get("kind") == "usage_gap"
        and (str(node.get("label") or "") == service or str(node.get("status") or "") == status)
    ]
    link_edge = next((
        edge for edge in spatial_edges
        if isinstance(edge, Mapping)
        and str(edge.get("from") or "") == service_node_id
        and str(edge.get("to") or "") == link_node_id
        and edge.get("kind") == "has_time_space_context_link"
    ), {})
    gap_edge = next((
        edge for edge in spatial_edges
        if isinstance(edge, Mapping)
        and str(edge.get("from") or "") == service_node_id
        and str(edge.get("to") or "").startswith("usage_gap:")
        and edge.get("kind") == "has_unexhausted_potential"
    ), {})

    episodes = episodes_doc.get("episodes") if isinstance(episodes_doc.get("episodes"), list) else []
    episode = next((
        item for item in episodes
        if isinstance(item, Mapping)
        and item.get("episode_kind") == "working_stack_usage_gap"
        and str(_nested_get(item, ["working_stack_gap", "service"]) or "") == service
        and str(_nested_get(item, ["working_stack_gap", "machine_usage_status"]) or "") == status
    ), {})
    episode_nodes = episode.get("affected_spatial_nodes") if isinstance(episode.get("affected_spatial_nodes"), list) else []

    candidates: list[Mapping[str, Any]] = []
    for key in ("reaction_candidates", "candidates"):
        value = alerts_doc.get(key) if isinstance(alerts_doc.get(key), list) else []
        candidates.extend(item for item in value if isinstance(item, Mapping))
    candidate = next((
        item for item in candidates
        if str(item.get("working_stack_gap_service") or _nested_get(item, ["response_contract", "working_stack_gap", "service"]) or "") == service
        and str(item.get("working_stack_gap_status") or _nested_get(item, ["response_contract", "working_stack_gap", "machine_usage_status"]) or "") == status
    ), {})
    response_contract = candidate.get("response_contract") if isinstance(candidate.get("response_contract"), Mapping) else {}
    contract_replay = response_contract.get("replay") if isinstance(response_contract.get("replay"), Mapping) else {}
    contract_investigation = response_contract.get("investigation") if isinstance(response_contract.get("investigation"), Mapping) else {}

    latest_investigation_matches = (
        str(_nested_get(investigation_doc, ["working_stack_gap", "service"]) or "") == service
        and str(_nested_get(investigation_doc, ["working_stack_gap", "machine_usage_status"]) or "") == status
        and _nested_get(investigation_doc, ["working_stack_gap", "complete"]) is True
    )
    latest_replay_matches = (
        str(_nested_get(replay_doc, ["working_stack_gap_replay", "service"]) or "") == service
        and str(_nested_get(replay_doc, ["working_stack_gap_replay", "machine_usage_status"]) or "") == status
        and _nested_get(replay_doc, ["working_stack_gap_replay", "replayable"]) is True
    )

    export_services = [
        str(item) for item in (_nested_get(export_doc, ["stack_handoff", "working_stack_activation_service_ids"]) or [])
        if item
    ]
    export_entries = _nested_get(export_doc, ["stack_handoff", "working_stack_activation_entries"])
    export_entries = export_entries if isinstance(export_entries, list) else []
    export_entry = next((item for item in export_entries if isinstance(item, Mapping) and str(item.get("service") or "") == service), {})

    scenario = entry.get("synthetic_scenario") if isinstance(entry.get("synthetic_scenario"), Mapping) else {}
    proof_steps = [
        {
            "step": "inventory",
            "command": "abyss-machine self-awareness working-stack --json",
            "ok": (
                bool(organ)
                and organ.get("owner") in (None, "abyss-stack")
                and str(organ.get("machine_usage_status") or "") == status
                and bool(organ.get("usage_gap"))
                and str(_nested_get(organ, ["time_space_context_link", "link_id"]) or _nested_get(organ, ["time_space_context_link", "context", "working_stack_link_id"]) or "") == link_id
            ),
            "evidence_refs": [{"path": str(working_stack_latest_path), "service": service, "working_stack_link_id": link_id}],
            "details": {
                "service_present": bool(organ),
                "machine_usage_status": organ.get("machine_usage_status") if isinstance(organ, Mapping) else None,
                "usage_gap": organ.get("usage_gap") if isinstance(organ, Mapping) else None,
                "working_stack_link_id": link_id or None,
            },
        },
        {
            "step": "space",
            "command": "abyss-machine self-awareness spatial-graph --json",
            "ok": (
                bool(service_node)
                and bool(link_node)
                and bool(link_edge)
                and bool(usage_gap_nodes)
                and bool(gap_edge)
                and service_node.get("owner_surface") == "abyss-stack"
            ),
            "evidence_refs": [{"path": str(spatial_graph_latest_path), "service": service, "nodes": [node for node in [service_node_id, link_node_id, str(gap_edge.get("to") or "")] if node]}],
            "details": {
                "service_node": service_node_id in node_ids,
                "link_node": link_node_id in node_ids,
                "usage_gap_nodes": [node.get("id") for node in usage_gap_nodes],
                "link_edge_id": link_edge.get("id"),
                "gap_edge_id": gap_edge.get("id"),
            },
        },
        {
            "step": "causal_episode",
            "command": "abyss-machine self-awareness episodes --json",
            "ok": (
                bool(episode)
                and _nested_get(episode, ["policy", "host_layer_mutates_stack"]) is False
                and _nested_get(episode, ["policy", "executes_commands"]) is False
                and service_node_id in episode_nodes
                and (not link_node_id or link_node_id in episode_nodes)
            ),
            "evidence_refs": [{"path": str(episodes_latest_path), "episode_id": episode.get("episode_id"), "service": service}],
            "details": {
                "episode_id": episode.get("episode_id"),
                "time_window": episode.get("time_window") if isinstance(episode.get("time_window"), Mapping) else {},
                "affected_spatial_nodes": episode_nodes,
            },
        },
        {
            "step": "reaction_response_contract",
            "command": "abyss-machine self-awareness alerts --json",
            "ok": (
                bool(candidate)
                and candidate.get("automatic") is False
                and bool(response_contract)
                and _nested_get(response_contract, ["policy", "host_layer_mutates_stack"]) is False
                and _nested_get(response_contract, ["policy", "executes_commands"]) is False
                and _nested_get(response_contract, ["approval", "human_approval_before_mutation"]) is True
            ),
            "evidence_refs": [{"path": str(alerts_latest_path), "candidate_id": candidate.get("id"), "service": service}],
            "details": {
                "candidate_id": candidate.get("id"),
                "episode_id": candidate.get("episode_id"),
                "automatic": candidate.get("automatic"),
                "approval_required": _nested_get(response_contract, ["approval", "required"]),
            },
        },
        {
            "step": "investigation_replay_contract",
            "command": "abyss-machine self-awareness investigate --episode-id EPISODE_ID --json; abyss-machine self-awareness replay --thread-id THREAD_ID --json",
            "ok": (
                bool(response_contract)
                and _safe_int(_nested_get(contract_investigation, ["summary", "checkpoints"]), 0) > 0
                and contract_replay.get("ok") is True
                and _nested_get(response_contract, ["working_stack_gap", "policy", "host_layer_mutates_stack"]) is False
                and _nested_get(response_contract, ["working_stack_gap", "policy", "executes_commands"]) is False
            ),
            "evidence_refs": [
                {"path": str(investigate_latest_path), "thread_id": contract_investigation.get("thread_id") or _nested_get(response_contract, ["investigation", "thread_id"]), "latest_matches_service": latest_investigation_matches},
                {"path": str(replay_latest_path), "thread_id": contract_replay.get("thread_id") or _nested_get(response_contract, ["replay", "thread_id"]), "latest_matches_service": latest_replay_matches},
            ],
            "details": {
                "contract_investigation_thread_id": contract_investigation.get("thread_id"),
                "contract_replay_thread_id": contract_replay.get("thread_id"),
                "contract_replay_ok": contract_replay.get("ok"),
                "latest_investigation_matches_service": latest_investigation_matches,
                "latest_replay_matches_service": latest_replay_matches,
            },
        },
        {
            "step": "coverage_row",
            "command": "abyss-machine self-awareness coverage-audit --json",
            "ok": (
                coverage_row.get("schema") == f"{schema_prefix}_self_awareness_working_stack_gap_coverage_row_v1"
                and coverage_row.get("service") == service
                and coverage_row.get("machine_usage_status") == status
                and coverage_row.get("working_stack_link_id") == link_id
                and working_stack_activation_synthetic_scenario_complete(scenario, schema_prefix=schema_prefix)
            ),
            "evidence_refs": [{"path": str(coverage_audit_latest_path), "coverage_row": coverage_row.get("id"), "service": service}],
            "details": {
                "coverage_row_id": coverage_row.get("id"),
                "scenario_id": scenario.get("scenario_id") if isinstance(scenario, Mapping) else None,
                "scenario_complete": working_stack_activation_synthetic_scenario_complete(scenario, schema_prefix=schema_prefix),
            },
        },
        {
            "step": "export",
            "command": "abyss-machine self-awareness export --json",
            "ok": (
                export_doc.get("schema") == f"{schema_prefix}_self_awareness_export_v1"
                and service in set(export_services)
                and bool(export_entry)
                and _nested_get(export_entry, ["policy", "host_layer_mutates_stack"]) is False
                and _nested_get(export_entry, ["policy", "executes_commands"]) is False
            ),
            "evidence_refs": [{"path": str(export_latest_path), "service": service}],
            "details": {
                "export_service_present": service in set(export_services),
                "export_entry_complete": export_entry.get("complete") if isinstance(export_entry, Mapping) else None,
                "export_generated_at": export_doc.get("generated_at"),
            },
        },
        {
            "step": "cycle",
            "command": "abyss-machine self-awareness cycle --json",
            "ok": (
                cycle_doc.get("schema") == f"{schema_prefix}_self_awareness_cycle_v1"
                and _safe_int(_nested_get(cycle_doc, ["summary", "working_stack_activation_entries"]), 0) >= 1
                and _safe_int(_nested_get(cycle_doc, ["summary", "automatic_responses"]), -1) == 0
                and _safe_int(_nested_get(cycle_doc, ["summary", "routes_with_mutating_command_if_run"]), -1) == 0
            ),
            "evidence_refs": [{"path": str(cycle_latest_path), "service": service}],
            "details": {
                "cycle_id": cycle_doc.get("cycle_id"),
                "activation_entries": _nested_get(cycle_doc, ["summary", "working_stack_activation_entries"]),
                "automatic_responses": _nested_get(cycle_doc, ["summary", "automatic_responses"]),
                "routes_with_mutating_command_if_run": _nested_get(cycle_doc, ["summary", "routes_with_mutating_command_if_run"]),
            },
        },
        {
            "step": "boundary_policy",
            "command": "abyss-machine self-awareness validate --json",
            "ok": (
                _nested_get(entry, ["policy", "host_layer_mutates_stack"]) is False
                and _nested_get(entry, ["policy", "executes_commands"]) is False
                and _nested_get(entry, ["safe_next_action", "host_layer_mutates_stack"]) is False
                and _nested_get(entry, ["safe_next_action", "executes_commands"]) is False
                and _nested_get(entry, ["safe_next_action", "requires_human_approval"]) is True
                and _nested_get(coverage_row, ["policy", "host_layer_mutates_stack"]) is False
                and _nested_get(coverage_row, ["policy", "executes_commands"]) is False
                and _nested_get(coverage_row, ["policy", "automatic_remediation"]) is False
            ),
            "evidence_refs": [{"path": str(validate_latest_path), "service": service}],
            "details": {
                "entry_policy": entry.get("policy") if isinstance(entry.get("policy"), Mapping) else {},
                "coverage_policy": coverage_row.get("policy") if isinstance(coverage_row.get("policy"), Mapping) else {},
                "safe_next_action": entry.get("safe_next_action") if isinstance(entry.get("safe_next_action"), Mapping) else {},
            },
        },
    ]
    ok_steps = [step for step in proof_steps if step.get("ok") is True]
    proof = {
        "schema": f"{schema_prefix}_self_awareness_working_stack_activation_synthetic_proof_v1",
        "proof_id": "saproof-working-stack-activation-" + self_awareness_contracts.stable_hash_json({
            "service": service,
            "machine_usage_status": status,
            "working_stack_link_id": link_id,
        }, length=24),
        "generated_at": generated_at,
        "service": service,
        "owner": "abyss-stack",
        "machine_usage_status": status,
        "usage_gap": usage_gap,
        "working_stack_link_id": link_id or None,
        "proof_status": "proved_open_activation_gap" if len(ok_steps) == len(proof_steps) else "proof_incomplete",
        "proof_steps": proof_steps,
        "summary": {
            "steps": len(proof_steps),
            "ok_steps": len(ok_steps),
            "failed_steps": [str(step.get("step")) for step in proof_steps if step.get("ok") is not True],
            "latest_investigation_matches_service": latest_investigation_matches,
            "latest_replay_matches_service": latest_replay_matches,
            "response_contract_replay_ok": contract_replay.get("ok") is True,
        },
        "evidence_refs": [
            ref
            for step in proof_steps
            for ref in (step.get("evidence_refs") if isinstance(step.get("evidence_refs"), list) else [])
            if isinstance(ref, Mapping)
        ],
        "policy": {
            "readmodel_smoke": True,
            "synthetic_scenario_contract": True,
            "handoff_only": True,
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "action_execution": False,
            "automatic_remediation": False,
            "raw_secrets_included": False,
            "raw_private_content_included": False,
            "latest_replay_may_cover_only_selected_episode": True,
        },
    }
    proof["complete"] = working_stack_activation_synthetic_proof_complete(proof, schema_prefix=schema_prefix)
    return proof


def working_stack_activation_synthetic_proof_complete(proof: Any, *, schema_prefix: str) -> bool:
    if not isinstance(proof, Mapping):
        return False
    steps = proof.get("proof_steps") if isinstance(proof.get("proof_steps"), list) else []
    required_steps = {
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
    step_by_name = {
        str(step.get("step")): step
        for step in steps
        if isinstance(step, Mapping) and step.get("step")
    }
    return (
        proof.get("schema") == f"{schema_prefix}_self_awareness_working_stack_activation_synthetic_proof_v1"
        and bool(proof.get("proof_id"))
        and bool(proof.get("service"))
        and proof.get("owner") == "abyss-stack"
        and bool(proof.get("machine_usage_status"))
        and bool(proof.get("usage_gap"))
        and bool(proof.get("working_stack_link_id"))
        and proof.get("proof_status") == "proved_open_activation_gap"
        and required_steps.issubset(set(step_by_name))
        and all(step_by_name[name].get("ok") is True for name in required_steps)
        and _safe_int(_nested_get(proof, ["summary", "ok_steps"]), 0) == _safe_int(_nested_get(proof, ["summary", "steps"]), -1)
        and bool(proof.get("evidence_refs"))
        and _nested_get(proof, ["policy", "readmodel_smoke"]) is True
        and _nested_get(proof, ["policy", "synthetic_scenario_contract"]) is True
        and _nested_get(proof, ["policy", "host_layer_mutates_stack"]) is False
        and _nested_get(proof, ["policy", "executes_commands"]) is False
        and _nested_get(proof, ["policy", "action_execution"]) is False
        and _nested_get(proof, ["policy", "automatic_remediation"]) is False
        and _nested_get(proof, ["policy", "raw_secrets_included"]) is False
        and _nested_get(proof, ["policy", "raw_private_content_included"]) is False
    )


def export_overlay_working_stack_activation_proof(
    proof: Any,
    activation_entry_by_service: Mapping[str, dict[str, Any]],
    *,
    generated_at: str,
    schema_prefix: str,
    export_latest_path: Path | str,
) -> Any:
    if not isinstance(proof, Mapping):
        return proof
    service = str(proof.get("service") or "")
    export_entry = activation_entry_by_service.get(service)
    if not service or not isinstance(export_entry, Mapping):
        return proof
    steps = proof.get("proof_steps") if isinstance(proof.get("proof_steps"), list) else []
    adjusted_steps: list[dict[str, Any]] = []
    overlay_applied = False
    for step in steps:
        if not isinstance(step, Mapping):
            continue
        adjusted_step = dict(step)
        if step.get("step") == "export":
            details = dict(step.get("details") if isinstance(step.get("details"), Mapping) else {})
            adjusted_step["ok"] = (
                export_entry.get("schema") == f"{schema_prefix}_self_awareness_working_stack_activation_entry_v1"
                and export_entry.get("service") == service
                and export_entry.get("complete") is True
                and export_entry.get("working_stack_link_id") == proof.get("working_stack_link_id")
                and _nested_get(export_entry, ["policy", "host_layer_mutates_stack"]) is False
                and _nested_get(export_entry, ["policy", "executes_commands"]) is False
            )
            details.update({
                "export_service_present": True,
                "export_entry_complete": export_entry.get("complete"),
                "export_generated_at": generated_at,
                "export_handoff_overlay_applied": True,
            })
            adjusted_step["details"] = details
            evidence_refs = adjusted_step.get("evidence_refs") if isinstance(adjusted_step.get("evidence_refs"), list) else []
            adjusted_step["evidence_refs"] = [
                *evidence_refs,
                {"path": str(export_latest_path), "section": "current_export_handoff", "service": service},
            ]
            overlay_applied = True
        adjusted_steps.append(adjusted_step)
    if not overlay_applied:
        return dict(proof)
    adjusted = dict(proof)
    adjusted["proof_steps"] = adjusted_steps
    ok_steps = [step for step in adjusted_steps if step.get("ok") is True]
    summary = dict(adjusted.get("summary") if isinstance(adjusted.get("summary"), Mapping) else {})
    summary.update({
        "steps": len(adjusted_steps),
        "ok_steps": len(ok_steps),
        "failed_steps": [str(step.get("step")) for step in adjusted_steps if step.get("ok") is not True],
        "export_handoff_overlay_applied": True,
    })
    adjusted["summary"] = summary
    adjusted["proof_status"] = "proved_open_activation_gap" if len(ok_steps) == len(adjusted_steps) else "proof_incomplete"
    evidence_refs = [
        ref
        for step in adjusted_steps
        for ref in (step.get("evidence_refs") if isinstance(step.get("evidence_refs"), list) else [])
        if isinstance(ref, Mapping)
    ]
    if evidence_refs:
        adjusted["evidence_refs"] = evidence_refs
    adjusted["complete"] = working_stack_activation_synthetic_proof_complete(adjusted, schema_prefix=schema_prefix)
    return adjusted


def stack_organ_use_packet_complete(
    packet: Any,
    *,
    schema_prefix: str,
    event_issues: Callable[[dict[str, Any]], list[str]],
) -> bool:
    if not isinstance(packet, Mapping):
        return False
    entity = packet.get("entity") if isinstance(packet.get("entity"), Mapping) else {}
    event = packet.get("event") if isinstance(packet.get("event"), Mapping) else {}
    documents = packet.get("documents") if isinstance(packet.get("documents"), list) else []
    checks = packet.get("checks") if isinstance(packet.get("checks"), Mapping) else {}
    observed_signal = packet.get("observed_signal") if isinstance(packet.get("observed_signal"), Mapping) else {}
    movement_selection = packet.get("movement_selection") if isinstance(packet.get("movement_selection"), Mapping) else {}
    return (
        packet.get("schema") == f"{schema_prefix}_self_awareness_stack_organ_use_packet_v1"
        and bool(packet.get("packet_id"))
        and bool(packet.get("service"))
        and packet.get("owner") == "abyss-stack"
        and entity.get("schema") == f"{schema_prefix}_self_awareness_stack_organ_use_entity_v1"
        and entity.get("entity_kind") == "stack_organ"
        and bool(entity.get("entity_id"))
        and event.get("schema") == f"{schema_prefix}_self_awareness_stack_organ_use_event_v1"
        and bool(event.get("event_id"))
        and bool(event.get("working_stack_link_id"))
        and bool(event.get("classification"))
        and isinstance(documents, list)
        and len(documents) >= 5
        and all(isinstance(item, Mapping) and item.get("document_id") and item.get("path") for item in documents)
        and isinstance(packet.get("document_ids"), list)
        and len(packet.get("document_ids")) == len(documents)
        and isinstance(packet.get("current_state"), Mapping)
        and bool(_nested_get(packet, ["time_space_context", "context", "working_stack_link_id"]))
        and observed_signal.get("schema") == f"{schema_prefix}_observation_event_v1"
        and not event_issues(dict(observed_signal))
        and movement_selection.get("schema") == f"{schema_prefix}_self_awareness_stack_organ_movement_selection_v1"
        and isinstance(movement_selection.get("categories"), list)
        and bool(movement_selection.get("categories"))
        and (
            bool(movement_selection.get("selected_reason"))
            or bool(movement_selection.get("not_selected_reason"))
        )
        and _nested_get(packet, ["automation", "required_in"]) == ["activation-smoke", "export", "validate"]
        and _nested_get(packet, ["automation", "host_layer_mutates_stack"]) is False
        and _nested_get(packet, ["automation", "executes_stack_verifiers"]) is False
        and bool(packet.get("evidence_refs"))
        and all(ok is True for ok in checks.values())
        and packet.get("missing_checks") == []
        and _nested_get(packet, ["policy", "host_layer_mutates_stack"]) is False
        and _nested_get(packet, ["policy", "writes_project_roots"]) is False
        and _nested_get(packet, ["policy", "executes_commands"]) is False
        and _nested_get(packet, ["policy", "action_execution"]) is False
        and _nested_get(packet, ["policy", "automatic_remediation"]) is False
        and _nested_get(packet, ["policy", "raw_secrets_included"]) is False
        and _nested_get(packet, ["policy", "raw_private_content_included"]) is False
    )


def working_stack_activation_smoke_row_complete(
    row: Any,
    *,
    schema_prefix: str,
    investigation_node_count: int,
    event_issues: Callable[[dict[str, Any]], list[str]],
) -> bool:
    if not isinstance(row, Mapping):
        return False
    investigation = row.get("investigation") if isinstance(row.get("investigation"), Mapping) else {}
    replay = row.get("replay") if isinstance(row.get("replay"), Mapping) else {}
    stack_organ_use_packet = row.get("stack_organ_use_packet") if isinstance(row.get("stack_organ_use_packet"), Mapping) else {}
    packet_complete = stack_organ_use_packet_complete(
        stack_organ_use_packet,
        schema_prefix=schema_prefix,
        event_issues=event_issues,
    )
    if row.get("row_kind") == "organ_movement":
        return (
            row.get("schema") == f"{schema_prefix}_self_awareness_working_stack_activation_smoke_row_v1"
            and row.get("ok") is True
            and bool(row.get("service"))
            and row.get("owner") == "abyss-stack"
            and bool(row.get("machine_usage_status"))
            and bool(row.get("working_stack_link_id"))
            and investigation.get("schema") == f"{schema_prefix}_self_awareness_working_stack_activation_smoke_investigation_v1"
            and investigation.get("actual_run") is False
            and replay.get("schema") == f"{schema_prefix}_self_awareness_working_stack_activation_smoke_replay_v1"
            and replay.get("actual_run") is False
            and packet_complete
            and stack_organ_use_packet.get("service") == row.get("service")
            and _nested_get(stack_organ_use_packet, ["event", "working_stack_link_id"]) == row.get("working_stack_link_id")
            and _nested_get(stack_organ_use_packet, ["event", "machine_usage_status"]) == row.get("machine_usage_status")
            and bool(row.get("evidence_refs"))
            and _nested_get(row, ["policy", "movement_packet"]) is True
            and _nested_get(row, ["policy", "actual_investigate_replay_run"]) is False
            and _nested_get(row, ["policy", "host_layer_mutates_stack"]) is False
            and _nested_get(row, ["policy", "executes_commands"]) is False
            and _nested_get(row, ["policy", "action_execution"]) is False
            and _nested_get(row, ["policy", "automatic_remediation"]) is False
        )
    return (
        row.get("schema") == f"{schema_prefix}_self_awareness_working_stack_activation_smoke_row_v1"
        and row.get("ok") is True
        and bool(row.get("service"))
        and row.get("owner") == "abyss-stack"
        and bool(row.get("machine_usage_status"))
        and bool(row.get("usage_gap"))
        and bool(row.get("working_stack_link_id"))
        and bool(row.get("episode_id"))
        and investigation.get("schema") == f"{schema_prefix}_self_awareness_working_stack_activation_smoke_investigation_v1"
        and investigation.get("ok") is True
        and investigation.get("selected_episode_matches") is True
        and investigation.get("working_stack_gap_complete") is True
        and investigation.get("working_stack_gap_matches") is True
        and _safe_int(investigation.get("evidence_validation_fails"), -1) == 0
        and _safe_int(investigation.get("checkpoints"), 0) == investigation_node_count
        and _safe_int(investigation.get("graph_nodes"), 0) == investigation_node_count
        and replay.get("schema") == f"{schema_prefix}_self_awareness_working_stack_activation_smoke_replay_v1"
        and replay.get("ok") is True
        and replay.get("thread_matches") is True
        and replay.get("working_stack_gap_selected") is True
        and replay.get("working_stack_gap_replayable") is True
        and replay.get("working_stack_gap_matches") is True
        and _safe_int(replay.get("divergences"), -1) == 0
        and replay.get("stack_handoff_closure_readiness_replayable") is True
        and replay.get("resident_cognitive_replay_complete") is True
        and packet_complete
        and stack_organ_use_packet.get("service") == row.get("service")
        and _nested_get(stack_organ_use_packet, ["event", "working_stack_link_id"]) == row.get("working_stack_link_id")
        and _nested_get(stack_organ_use_packet, ["event", "machine_usage_status"]) == row.get("machine_usage_status")
        and bool(row.get("evidence_refs"))
        and _nested_get(row, ["policy", "actual_investigate_replay_run"]) is True
        and _nested_get(row, ["policy", "host_layer_mutates_stack"]) is False
        and _nested_get(row, ["policy", "executes_commands"]) is False
        and _nested_get(row, ["policy", "action_execution"]) is False
        and _nested_get(row, ["policy", "automatic_remediation"]) is False
    )


def working_stack_activation_smoke_compact(
    row: Any,
    *,
    schema_prefix: str,
    investigation_node_count: int,
    event_issues: Callable[[dict[str, Any]], list[str]],
) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        return {}
    return {
        "schema": f"{schema_prefix}_self_awareness_working_stack_activation_smoke_compact_v1",
        "row_kind": row.get("row_kind"),
        "service": row.get("service"),
        "machine_usage_status": row.get("machine_usage_status"),
        "working_stack_link_id": row.get("working_stack_link_id"),
        "episode_id": row.get("episode_id"),
        "ok": row.get("ok"),
        "complete": working_stack_activation_smoke_row_complete(
            row,
            schema_prefix=schema_prefix,
            investigation_node_count=investigation_node_count,
            event_issues=event_issues,
        ),
        "thread_id": _nested_get(row, ["investigation", "thread_id"]),
        "divergences": _nested_get(row, ["replay", "divergences"]),
        "working_stack_gap_replayable": _nested_get(row, ["replay", "working_stack_gap_replayable"]),
        "resident_cognitive_replay_complete": _nested_get(row, ["replay", "resident_cognitive_replay_complete"]),
        "stack_organ_use_packet_id": _nested_get(row, ["stack_organ_use_packet", "packet_id"]),
        "stack_organ_entity_id": _nested_get(row, ["stack_organ_use_packet", "entity", "entity_id"]),
        "stack_organ_event_id": _nested_get(row, ["stack_organ_use_packet", "event", "event_id"]),
        "stack_organ_document_ids": _nested_get(row, ["stack_organ_use_packet", "document_ids"]) if isinstance(_nested_get(row, ["stack_organ_use_packet", "document_ids"]), list) else [],
        "activation_gap_classification": _nested_get(row, ["stack_organ_use_packet", "activation_gap", "classification"]),
        "movement_categories": _nested_get(row, ["stack_organ_use_packet", "movement_selection", "categories"]) if isinstance(_nested_get(row, ["stack_organ_use_packet", "movement_selection", "categories"]), list) else [],
        "selected_for_resident_reasoning": _nested_get(row, ["stack_organ_use_packet", "movement_selection", "selected_for_resident_reasoning"]),
        "evidence_refs": row.get("evidence_refs") if isinstance(row.get("evidence_refs"), list) else [],
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "action_execution": False,
        },
    }


def working_stack_activation_smoke_complete(
    smoke: Any,
    *,
    schema_prefix: str,
    investigation_node_count: int,
    event_issues: Callable[[dict[str, Any]], list[str]],
) -> bool:
    if not isinstance(smoke, Mapping):
        return False
    rows = smoke.get("rows") if isinstance(smoke.get("rows"), list) else []
    summary = smoke.get("summary") if isinstance(smoke.get("summary"), Mapping) else {}
    packets = smoke.get("stack_organ_use_packets") if isinstance(smoke.get("stack_organ_use_packets"), list) else []
    packet_by_service = smoke.get("stack_organ_use_packet_by_service") if isinstance(smoke.get("stack_organ_use_packet_by_service"), Mapping) else {}
    service_ids = [str(row.get("service")) for row in rows if isinstance(row, Mapping) and row.get("service")]
    summary_service_ids = [str(item) for item in (summary.get("service_ids") if isinstance(summary.get("service_ids"), list) else [])]
    expected_services = [str(item) for item in (summary.get("stack_organs_expected_services") if isinstance(summary.get("stack_organs_expected_services"), list) else [])]
    return (
        smoke.get("schema") == f"{schema_prefix}_self_awareness_working_stack_activation_smoke_v1"
        and smoke.get("ok") is True
        and bool(smoke.get("run_id"))
        and bool(rows)
        and bool(packets)
        and bool(expected_services)
        and _safe_int(summary.get("stack_organs_expected"), -1) == len(expected_services)
        and _safe_int(summary.get("rows"), -1) == len(rows)
        and _safe_int(summary.get("rows_ok"), -1) == len(rows)
        and _safe_int(summary.get("stack_organ_use_packets"), -1) == len(rows)
        and _safe_int(summary.get("stack_organ_use_packets_complete"), -1) == len(rows)
        and sorted(summary_service_ids) == sorted(service_ids)
        and len(packets) == len(rows)
        and set(service_ids) == set(expected_services)
        and set(str(item) for item in packet_by_service) == set(service_ids)
        and not summary.get("stack_organs_without_use_packets")
        and summary.get("all_stack_organs_have_use_packets") is True
        and all(
            stack_organ_use_packet_complete(packet, schema_prefix=schema_prefix, event_issues=event_issues)
            for packet in packets
        )
        and not summary.get("failed_services")
        and all(
            working_stack_activation_smoke_row_complete(
                row,
                schema_prefix=schema_prefix,
                investigation_node_count=investigation_node_count,
                event_issues=event_issues,
            )
            for row in rows
        )
        and bool(smoke.get("evidence_refs"))
        and _nested_get(smoke, ["policy", "host_layer_mutates_stack"]) is False
        and _nested_get(smoke, ["policy", "executes_commands"]) is False
        and _nested_get(smoke, ["policy", "action_execution"]) is False
        and _nested_get(smoke, ["policy", "automatic_remediation"]) is False
    )


def activation_smoke_needs_refresh(
    smoke: Any,
    activation_entries: list[dict[str, Any]],
    *,
    schema_prefix: str,
    investigation_node_count: int,
    event_issues: Callable[[dict[str, Any]], list[str]],
    expected_services: Iterable[str] | None = None,
) -> bool:
    if not working_stack_activation_smoke_complete(
        smoke,
        schema_prefix=schema_prefix,
        investigation_node_count=investigation_node_count,
        event_issues=event_issues,
    ):
        return True
    rows = smoke.get("rows") if isinstance(smoke, Mapping) and isinstance(smoke.get("rows"), list) else []
    row_by_service = {
        str(row.get("service")): row
        for row in rows
        if isinstance(row, Mapping) and row.get("service")
    }
    expected_service_set = {
        str(entry.get("service"))
        for entry in activation_entries
        if isinstance(entry, Mapping) and entry.get("service")
    }
    if expected_services is not None:
        expected_service_set = {str(service) for service in expected_services if service}
    if set(row_by_service) != expected_service_set:
        return True
    entry_by_service = {
        str(entry.get("service")): entry
        for entry in activation_entries
        if isinstance(entry, Mapping) and entry.get("service")
    }
    for service in set(row_by_service) & set(entry_by_service):
        entry = entry_by_service.get(service, {})
        if not isinstance(entry, Mapping) or not entry.get("service"):
            continue
        row = row_by_service.get(str(entry.get("service")), {})
        if (
            str(row.get("machine_usage_status") or "") != str(entry.get("machine_usage_status") or "")
            or str(row.get("working_stack_link_id") or "") != str(entry.get("working_stack_link_id") or "")
        ):
            return True
    return False


def working_stack_model_bridge(
    service: str,
    model_rows: Iterable[Mapping[str, Any]],
    ai_caps: Mapping[str, Any],
    *,
    schema_prefix: str,
    ai_model_roots: Iterable[Path | str],
    latest_paths: Mapping[str, Path | str],
) -> dict[str, Any]:
    capability_key_by_service = {
        "embeddings": "embeddings",
        "stt": "stt",
        "tts": "tts",
        "llm-registry": "llm_text",
    }
    capability_key = capability_key_by_service.get(service)
    if not capability_key:
        return {}
    capabilities = ai_caps.get("capabilities") if isinstance(ai_caps.get("capabilities"), Mapping) else {}
    capability = capabilities.get(capability_key) if isinstance(capabilities.get(capability_key), Mapping) else {}
    status = str(capability.get("status") or "")
    ready_statuses = {"ready", "runtime-ready", "runtime-proven", "resident-running", "executable"}
    source_refs = collect_stack_model_path_refs(
        capability,
        ai_model_roots=ai_model_roots,
    )
    source_paths = [str(ref.get("path")) for ref in source_refs if ref.get("path")]
    model_rows_list = list(model_rows)
    paths_from_rows = model_row_paths(model_rows_list)
    linked_paths = [
        source_path for source_path in source_paths
        if any(paths_overlap(source_path, model_path) for model_path in paths_from_rows)
    ]
    runtime_ready = status in ready_statuses or _nested_get(capability, ["runtime", "ready"]) is True
    active = bool(runtime_ready and linked_paths)
    evidence_refs: list[dict[str, Any]] = [
        {"path": str(latest_paths.get("ai_capabilities") or ""), "schema": ai_caps.get("schema"), "capability": capability_key},
    ]
    if service == "llm-registry":
        evidence_refs.append({"path": str(latest_paths.get("ai_llm_registry") or ""), "schema": f"{schema_prefix}_ai_llm_registry_v1"})
    if service == "tts":
        evidence_refs.extend([
            {"path": str(latest_paths.get("ai_tts_profiles") or ""), "schema": f"{schema_prefix}_ai_tts_profiles_v1"},
            {"path": str(latest_paths.get("ai_tts_eval_success") or ""), "schema": f"{schema_prefix}_ai_tts_eval_v1"},
        ])
    return {
        "schema": f"{schema_prefix}_self_awareness_working_stack_model_bridge_v1",
        "service": service,
        "capability": capability_key,
        "status": status,
        "active": active,
        "runtime_ready": runtime_ready,
        "primary_bridge": capability.get("primary_bridge") or capability.get("resident_bridge") or capability.get("eval_bridge"),
        "host_recommended_backend": capability.get("host_recommended_backend"),
        "model_root_count": len(model_rows_list),
        "stack_source_model_refs": source_refs[:12],
        "linked_stack_model_source_paths": linked_paths[:12],
        "evidence_refs": evidence_refs,
        "policy": {
            "read_only_source": True,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "model_promotion_decision": False,
        },
    }


def _working_stack_usage_gap_reason(status: str) -> str | None:
    if status == "runtime_visible_unproven_deep_use":
        return "running stack organ is visible, but no deeper machine usage path is proven yet"
    if status == "endpoint_visible_unproven_deep_use":
        return "endpoint is readable, but no sustained machine reasoning path is proven yet"
    if status == "tool_runtime_degraded":
        return "stack tool is reachable and guarded, but its functional runtime smoke failed"
    if status == "tool_guard_visible_unproven_deep_use":
        return "stack tool health and safety guard are visible, but functional runtime smoke is not proven yet"
    if status == "declared_not_running":
        return "declared stack service is not running in the current runtime body"
    if status == "model_root_visible":
        return "stack model root is visible, but no direct runtime/service linkage is proven yet"
    return None


def working_stack_inventory_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    stack_paths: Mapping[str, Any],
    stack_doc: Mapping[str, Any],
    container_health: Mapping[str, Any],
    compose_inventory: Mapping[str, Any],
    service_roots_inventory: Mapping[str, Any],
    model_inventory: Mapping[str, Any],
    selection_policy: Mapping[str, Any],
    ai_caps: Mapping[str, Any],
    initial_endpoint_probes: Iterable[Mapping[str, Any]],
    include_endpoint_probes: bool,
    pid_alive: PidAlivePort,
    container_tool_probes: ContainerToolProbesPort,
    tts_smoke_probes: TtsSmokeProbesPort,
    ai_model_roots: Iterable[Path | str],
    latest_paths: Mapping[str, Path | str],
    expected_live_services: Iterable[str],
) -> dict[str, Any]:
    selection_by_service = selection_policy.get("services") if isinstance(selection_policy.get("services"), Mapping) else {}

    declared_by_service = {
        str(row.get("service")): row
        for row in compose_inventory.get("services", [])
        if isinstance(row, Mapping) and row.get("service")
    }
    service_roots_by_service: dict[str, list[Mapping[str, Any]]] = {}
    for row in service_roots_inventory.get("services", []) if isinstance(service_roots_inventory.get("services"), list) else []:
        if isinstance(row, Mapping) and row.get("service"):
            service_roots_by_service.setdefault(str(row["service"]), []).append(row)
    model_roots_by_service: dict[str, list[Mapping[str, Any]]] = {}
    for row in model_inventory.get("models", []) if isinstance(model_inventory.get("models"), list) else []:
        if not isinstance(row, Mapping):
            continue
        for service in row.get("service_candidates", []) if isinstance(row.get("service_candidates"), list) else []:
            model_roots_by_service.setdefault(str(service), []).append(row)

    endpoint_probes: list[dict[str, Any]] = [dict(probe) for probe in initial_endpoint_probes if isinstance(probe, Mapping)]
    probes_by_service: dict[str, list[dict[str, Any]]] = {}
    for probe in endpoint_probes:
        if probe.get("service"):
            probes_by_service.setdefault(str(probe["service"]), []).append(probe)

    expected_live = tuple(str(service) for service in expected_live_services)
    runtime_by_service: dict[str, dict[str, Any]] = {}
    containers = container_health.get("containers") if isinstance(container_health.get("containers"), list) else []
    for item in containers:
        if not isinstance(item, Mapping):
            continue
        service = service_from_container(item)
        compose = item.get("compose") if isinstance(item.get("compose"), Mapping) else {}
        stack_managed = bool(compose.get("stack_managed") or compose.get("project") == "abyss")
        known = (
            service in declared_by_service
            or service in expected_live
            or service in service_roots_by_service
            or service in probes_by_service
        )
        if not stack_managed and not known:
            continue
        container_pid = _safe_int(item.get("pid"), 0)
        runtime_by_service[service] = {
            "service": service,
            "container": item.get("name"),
            "pid": container_pid if container_pid > 0 else None,
            "pid_alive": pid_alive(container_pid) if container_pid > 0 else False,
            "names": item.get("names") if isinstance(item.get("names"), list) else [],
            "running": bool(item.get("running")),
            "state": item.get("state"),
            "status": item.get("status"),
            "health": item.get("health"),
            "restart_count": item.get("restart_count"),
            "ports": item.get("ports"),
            "compose": dict(compose),
            "attention_reasons": item.get("attention_reasons") if isinstance(item.get("attention_reasons"), list) else [],
            "evidence_refs": [{
                "path": str(latest_paths.get("process_container") or ""),
                "schema": container_health.get("schema"),
                "service": service,
                "container": item.get("name"),
            }],
        }

    endpoint_probes.extend(container_tool_probes(runtime_by_service, include_endpoint_probes))
    endpoint_probes.extend(tts_smoke_probes(include_endpoint_probes))
    probes_by_service = {}
    for probe in endpoint_probes:
        if isinstance(probe, Mapping) and probe.get("service"):
            probes_by_service.setdefault(str(probe["service"]), []).append(dict(probe))

    service_names = sorted(
        set(declared_by_service)
        | set(service_roots_by_service)
        | set(model_roots_by_service)
        | set(probes_by_service)
        | set(runtime_by_service)
    )
    organs: list[dict[str, Any]] = []
    usage_gaps: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    latest_paths_for_bridge = {
        "ai_capabilities": latest_paths.get("ai_capabilities") or "",
        "ai_llm_registry": latest_paths.get("ai_llm_registry") or "",
        "ai_tts_profiles": latest_paths.get("ai_tts_profiles") or "",
        "ai_tts_eval_success": latest_paths.get("ai_tts_eval_success") or "",
    }
    working_stack_schema = f"{schema_prefix}_self_awareness_working_stack_inventory_v1"
    for service in service_names:
        runtime = runtime_by_service.get(service, {})
        declared = declared_by_service.get(service, {})
        root_rows = service_roots_by_service.get(service, [])
        model_rows = model_roots_by_service.get(service, [])
        probes = probes_by_service.get(service, [])
        endpoint_ok = any(probe.get("ok") is True for probe in probes)
        running = bool(runtime.get("running"))
        model_bridge = working_stack_model_bridge(
            service,
            model_rows,
            ai_caps,
            schema_prefix=schema_prefix,
            ai_model_roots=ai_model_roots,
            latest_paths=latest_paths_for_bridge,
        )
        usage_status = self_awareness_contracts.working_stack_status(
            service,
            running=running,
            declared=bool(declared),
            endpoint_ok=endpoint_ok,
            model_roots=len(model_rows),
        )
        usage_status = working_stack_tool_status(service, usage_status, probes)
        if usage_status == "model_root_visible" and model_bridge.get("active") is True:
            usage_status = "active_model_root_bridge"
        selection = selection_by_service.get(service) if isinstance(selection_by_service.get(service), Mapping) else {}
        usage_status = self_awareness_contracts.working_stack_policy_status(usage_status, selection)
        gap_reason = _working_stack_usage_gap_reason(usage_status)
        link = self_awareness_contracts.working_stack_link(
            service,
            generated_at,
            status=usage_status,
            container=str(runtime.get("container") or "") or None,
            pid=runtime.get("pid") if isinstance(runtime.get("pid"), int) else None,
            endpoint_ok=endpoint_ok,
            schema_prefix=schema_prefix,
        )
        links.append(link)
        stack_source_refs: list[Any] = []
        if isinstance(declared.get("stack_source_refs"), list):
            stack_source_refs.extend(declared["stack_source_refs"])
        for root_row in root_rows:
            stack_source_refs.extend(root_row.get("stack_source_refs") if isinstance(root_row.get("stack_source_refs"), list) else [])
        for model_row in model_rows[:8]:
            stack_source_refs.extend(model_row.get("stack_source_refs") if isinstance(model_row.get("stack_source_refs"), list) else [])
        organ = {
            "schema": f"{schema_prefix}_self_awareness_working_stack_organ_v1",
            "service": service,
            "owner_surface": "abyss-stack",
            "machine_role": "read_only_consumer",
            "roles": self_awareness_contracts.working_stack_roles(service),
            "runtime": runtime or {"present": False, "running": False},
            "declared": {
                "present": bool(declared),
                "modules": declared.get("modules") if isinstance(declared, Mapping) else [],
            },
            "service_roots": len(root_rows),
            "model_roots": len(model_rows),
            "endpoint_probes": probes,
            "endpoint_ok": endpoint_ok,
            "model_bridge": model_bridge,
            "service_selection": dict(selection),
            "machine_usage_status": usage_status,
            "deep_usage_proven": usage_status in {"active_machine_signal", "active_dependency_signal", "active_machine_tool_signal", "active_model_root_bridge", "recent_on_demand_tool_signal"},
            "usage_gap": gap_reason,
            "time_space_context_link": link,
            "evidence_refs": [
                {
                    "path": str(latest_paths.get("working_stack") or ""),
                    "schema": working_stack_schema,
                    "service": service,
                },
                *runtime.get("evidence_refs", []),
                *(model_bridge.get("evidence_refs", []) if isinstance(model_bridge.get("evidence_refs"), list) and model_bridge.get("active") is True else []),
            ],
            "stack_source_refs": stack_source_refs[:24],
            "policy": {
                "read_only": True,
                "host_layer_mutates_stack": False,
                "writes_project_roots": False,
                "raw_evidence_is_not_truth": True,
            },
        }
        organs.append(organ)
        if gap_reason:
            usage_gaps.append({
                "service": service,
                "status": usage_status,
                "reason": gap_reason,
                "owner_surface": "abyss-stack",
                "machine_next_step": "wire a bounded read-only query/health/semantic route before treating this organ as deeply used",
                "policy": {"host_layer_mutates_stack": False, "automatic_remediation": False},
            })

    active_runtime_services = sorted(service for service, row in runtime_by_service.items() if row.get("running"))
    missing_expected_live = sorted(service for service in expected_live if service not in active_runtime_services)
    organ_services = sorted(str(organ.get("service")) for organ in organs if organ.get("service"))
    endpoint_probe_services = sorted(str(probe.get("service")) for probe in endpoint_probes if isinstance(probe, Mapping) and probe.get("service"))
    deep_usage_proven_services = sorted(str(organ.get("service")) for organ in organs if organ.get("service") and organ.get("deep_usage_proven") is True)
    organs_without_endpoint_probe = sorted(set(organ_services) - set(endpoint_probe_services))
    return {
        "schema": working_stack_schema,
        "version": version,
        "generated_at": generated_at,
        "ok": bool(organs and runtime_by_service and compose_inventory.get("ok")),
        "status": "mapped_with_usage_gaps" if usage_gaps else "mapped",
        "summary": {
            "organs": len(organs),
            "runtime_services": len(runtime_by_service),
            "running_services": len(active_runtime_services),
            "declared_services": len(declared_by_service),
            "service_roots": _nested_get(service_roots_inventory, ["summary", "service_roots"]),
            "model_roots": _nested_get(model_inventory, ["summary", "model_roots"]),
            "endpoint_probes": len(endpoint_probes),
            "endpoint_ok": sum(1 for probe in endpoint_probes if probe.get("ok") is True),
            "time_space_context_links": len(links),
            "usage_gaps": len(usage_gaps),
            "policy_deferred_services": sum(1 for organ in organs if str(organ.get("machine_usage_status") or "").startswith("policy_deferred_")),
            "missing_expected_live": missing_expected_live,
            "active_runtime_services": active_runtime_services,
            "organ_services": organ_services,
            "endpoint_probe_services": endpoint_probe_services,
            "deep_usage_proven_services": deep_usage_proven_services,
            "organs_without_endpoint_probe": organs_without_endpoint_probe,
        },
        "owner_boundary": {
            "stack_owner": "abyss-stack",
            "machine_role": "read_only_consumer",
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
        },
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "automatic_remediation": False,
            "raw_evidence_is_not_truth": True,
            "endpoint_bodies_stored": False,
            "stack_source_refs_are_read_only": True,
        },
        "stack_paths": dict(stack_paths),
        "compose": dict(compose_inventory),
        "service_roots": dict(service_roots_inventory),
        "model_roots": dict(model_inventory),
        "service_selection_policy": dict(selection_policy),
        "endpoint_probes": endpoint_probes,
        "runtime_services": list(runtime_by_service.values()),
        "organs": organs,
        "time_space_context_links": links,
        "machine_usage_gaps": usage_gaps,
        "evidence_refs": [
            {"path": str(latest_paths.get("process_container") or ""), "schema": container_health.get("schema")},
            {"path": str(latest_paths.get("stack_observability") or ""), "schema": stack_doc.get("schema")},
            {"path": str(latest_paths.get("working_stack") or ""), "schema": working_stack_schema},
        ],
        "stack_source_refs": ([
            ref
            for source in (compose_inventory.get("module_refs") if isinstance(compose_inventory.get("module_refs"), list) else [])
            for ref in [source]
        ] + [
            doc.get("source_ref")
            for doc in (selection_policy.get("documents") if isinstance(selection_policy.get("documents"), list) else [])
            if isinstance(doc, Mapping) and isinstance(doc.get("source_ref"), Mapping)
        ])[:96],
        "tests": {
            "live_smoke": "abyss-machine self-awareness working-stack --json",
            "fabric_smoke": "abyss-machine self-awareness collect --json then inspect working-stack service events",
            "boundary": "stack paths appear only as read-only stack_source_refs; event evidence_refs use host-owned readmodels",
        },
    }


def working_stack_organ_signal_route(service: str, organ: Mapping[str, Any]) -> dict[str, str]:
    service_l = service.lower()
    if service_l in {"prometheus"}:
        return {"signal": "metric", "source": "prometheus"}
    if service_l in {"loki"}:
        return {"signal": "log", "source": "loki"}
    if service_l in {"grafana"}:
        return {"signal": "service", "source": "grafana"}
    if service_l in {"alertmanager"}:
        return {"signal": "alert", "source": "alertmanager"}
    if service_l in {"alloy", "tempo"}:
        return {"signal": "trace_context", "source": "alloy" if service_l == "alloy" else "observability"}
    if service_l in {"postgres"}:
        return {"signal": "memory", "source": "postgres"}
    if service_l in {"neo4j"}:
        return {"signal": "memory", "source": "neo4j"}
    if service_l in {"rag-api", "qdrant", "rerank-api"}:
        return {"signal": "rag", "source": "rag-api" if service_l == "rag-api" else "rag"}
    if service_l in {"embeddings"}:
        return {"signal": "model", "source": "embeddings"}
    if service_l in {"route-api"}:
        return {"signal": "service", "source": "route-api"}
    if service_l in {"langchain-api", "langchain-api-llamacpp"}:
        return {"signal": "model", "source": "langchain-api"}
    if service_l in {"llama-cpp", "llm-registry", "litellm", "ollama", "ovms"}:
        return {"signal": "model", "source": "llm"}
    if "tts" in service_l or service_l in {"qwen-tts", "babelvox-tts"}:
        return {"signal": "model", "source": "tts"}
    if service_l == "stt":
        return {"signal": "model", "source": "stt"}
    if service_l in {"redis"}:
        return {"signal": "memory", "source": "memory"}
    if service_l in {"cadvisor"}:
        return {"signal": "container", "source": "processes"}
    runtime = organ.get("runtime") if isinstance(organ.get("runtime"), Mapping) else {}
    if runtime.get("container"):
        return {"signal": "container", "source": "podman"}
    return {"signal": "service", "source": "working-stack"}


def working_stack_organ_state_digest(organ: Mapping[str, Any]) -> str:
    endpoint_probes = organ.get("endpoint_probes") if isinstance(organ.get("endpoint_probes"), list) else []
    runtime = organ.get("runtime") if isinstance(organ.get("runtime"), Mapping) else {}
    return self_awareness_contracts.stable_hash_json({
        "service": organ.get("service"),
        "machine_usage_status": organ.get("machine_usage_status"),
        "usage_gap": organ.get("usage_gap"),
        "runtime": {
            "container": runtime.get("container"),
            "pid": runtime.get("pid"),
            "pid_alive": runtime.get("pid_alive"),
            "running": runtime.get("running"),
            "state": runtime.get("state"),
            "health": runtime.get("health"),
            "restart_count": runtime.get("restart_count"),
        },
        "endpoint_ok": organ.get("endpoint_ok"),
        "endpoint_probes": [
            {
                "probe": probe.get("probe"),
                "ok": probe.get("ok"),
                "status_code": probe.get("status_code"),
                "error": probe.get("error"),
            }
            for probe in endpoint_probes
            if isinstance(probe, Mapping)
        ],
        "model_bridge": organ.get("model_bridge") if isinstance(organ.get("model_bridge"), Mapping) else {},
        "deep_usage_proven": organ.get("deep_usage_proven"),
    }, length=24)


def working_stack_organ_movement_selection(
    organ: Mapping[str, Any],
    *,
    current_state_digest: str,
    previous_row: Mapping[str, Any] | None,
    schema_prefix: str,
) -> dict[str, Any]:
    service = str(organ.get("service") or "")
    runtime = organ.get("runtime") if isinstance(organ.get("runtime"), Mapping) else {}
    declared = organ.get("declared") if isinstance(organ.get("declared"), Mapping) else {}
    status = str(organ.get("machine_usage_status") or "")
    endpoint_probes = organ.get("endpoint_probes") if isinstance(organ.get("endpoint_probes"), list) else []
    failed_probe_names = [
        str(probe.get("probe"))
        for probe in endpoint_probes
        if isinstance(probe, Mapping) and probe.get("ok") is not True and probe.get("probe")
    ]
    previous_digest = _nested_get(previous_row or {}, ["stack_organ_use_packet", "current_state", "current_state_digest"])
    categories = ["raw_signal"]
    reasons: list[str] = ["organ observed in working-stack inventory"]
    state_changed = bool(previous_digest and previous_digest != current_state_digest)
    if previous_digest is None:
        reasons.append("baseline movement packet")
    elif state_changed:
        categories.append("state_change")
        reasons.append("state digest changed since previous activation-smoke")
    degradation_reasons: list[str] = []
    if organ.get("usage_gap"):
        degradation_reasons.append("usage_gap")
    runtime_expected = bool(
        runtime
        and declared.get("present") is True
        and not status.startswith("policy_deferred_")
        and status not in {"active_model_root_bridge", "recent_on_demand_tool_signal"}
    )
    if runtime_expected and runtime.get("running") is False:
        degradation_reasons.append("runtime_not_running")
    if failed_probe_names:
        degradation_reasons.append("failed_endpoint_probe")
    if status.endswith("_degraded"):
        degradation_reasons.append("degraded_status")
    if degradation_reasons:
        categories.append("degradation")
        reasons.extend(degradation_reasons)
    if _nested_get(organ, ["time_space_context_link", "link_id"]):
        categories.append("correlation_candidate")
    selected_for_episode = bool(state_changed or degradation_reasons)
    if selected_for_episode:
        categories.append("episode_candidate")
    selected_for_resident = bool(degradation_reasons)
    if selected_for_resident:
        categories.append("needs_resident_reasoning")
    elif not selected_for_episode and previous_digest is not None:
        categories.append("ignore/noise")
    return {
        "schema": f"{schema_prefix}_self_awareness_stack_organ_movement_selection_v1",
        "service": service,
        "categories": list(dict.fromkeys(categories)),
        "state_changed": state_changed,
        "previous_state_digest": previous_digest,
        "current_state_digest": current_state_digest,
        "selected_for_timeline": True,
        "selected_for_spatial_graph": True,
        "selected_for_episode": selected_for_episode,
        "selected_for_resident_reasoning": selected_for_resident,
        "selected_reason": "; ".join(reasons) if selected_for_episode or selected_for_resident else None,
        "not_selected_reason": None if selected_for_episode or selected_for_resident else "stable observation retained as raw signal and spatial context",
        "degradation_reasons": degradation_reasons,
        "failed_probe_names": failed_probe_names,
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "automatic_remediation": False,
        },
    }


def working_stack_gap_episodes(
    *,
    working_stack: Mapping[str, Any],
    events: Iterable[Mapping[str, Any]],
    generated_at: str,
    schema_prefix: str,
    working_stack_latest_path: Path | str,
    events_latest_path: Path | str,
    spatial_graph_latest_path: Path | str,
    process_container_latest_path: Path | str,
) -> tuple[list[dict[str, Any]], list[str]]:
    if working_stack.get("schema") != f"{schema_prefix}_self_awareness_working_stack_inventory_v1":
        return [], []
    event_ids_by_service: dict[str, list[str]] = {}
    for event in events:
        if not isinstance(event, Mapping) or event.get("source") != "working-stack":
            continue
        resource = event.get("resource") if isinstance(event.get("resource"), Mapping) else {}
        service = str(resource.get("service") or "")
        event_id = str(event.get("event_id") or "")
        if service and event_id:
            event_ids_by_service.setdefault(service, []).append(event_id)
    episodes: list[dict[str, Any]] = []
    episode_ids: list[str] = []
    organs = working_stack.get("organs") if isinstance(working_stack.get("organs"), list) else []
    for organ in organs:
        if not isinstance(organ, Mapping):
            continue
        service = str(organ.get("service") or "")
        gap_reason = str(organ.get("usage_gap") or "")
        if not service or not gap_reason:
            continue
        status = str(organ.get("machine_usage_status") or "unknown")
        runtime = organ.get("runtime") if isinstance(organ.get("runtime"), Mapping) else {}
        link = organ.get("time_space_context_link") if isinstance(organ.get("time_space_context_link"), Mapping) else {}
        link_id = str(link.get("link_id") or _nested_get(link, ["context", "working_stack_link_id"]) or "")
        probes = [
            probe for probe in (organ.get("endpoint_probes") if isinstance(organ.get("endpoint_probes"), list) else [])
            if isinstance(probe, Mapping)
        ]
        failed_probe_names = [str(probe.get("probe")) for probe in probes if probe.get("ok") is not True and probe.get("probe")]
        ok_probe_names = [str(probe.get("probe")) for probe in probes if probe.get("ok") is True and probe.get("probe")]
        affected_spatial_nodes = [
            "service:" + service,
            "usage_gap:" + self_awareness_contracts.stable_hash_json({"service": service, "status": status}, length=16),
        ]
        if runtime.get("container"):
            affected_spatial_nodes.append("container:" + str(runtime.get("container")))
        if link_id:
            affected_spatial_nodes.append("working_stack_link:" + link_id)
        for probe in probes:
            if probe.get("url"):
                affected_spatial_nodes.append("endpoint:" + self_awareness_contracts.stable_hash_json(probe.get("url"), length=16))
        event_ids = event_ids_by_service.get(service, [])
        episode_id = "saepisode-working-stack-gap-" + self_awareness_contracts.stable_hash_json({
            "service": service,
            "status": status,
            "gap_reason": gap_reason,
        }, length=24)
        episode_ids.append(episode_id)
        is_degraded = status.endswith("_degraded")
        confidence_score = 0.74 if is_degraded else 0.62
        confidence_reasons = [
            "working-stack inventory has a service-level usage_gap and automatic time-space-context link",
            "spatial graph projects a matching usage_gap node",
        ]
        if runtime.get("running"):
            confidence_score += 0.08
            confidence_reasons.append("container/runtime body is currently running")
        if failed_probe_names:
            confidence_score += 0.08
            confidence_reasons.append("bounded runtime smoke or endpoint probe failed")
        confidence_score = min(0.9, round(confidence_score, 2))
        safe_next_action = self_awareness_contracts.working_stack_gap_safe_next_action(service, status, gap_reason)
        evidence_refs = [
            {"path": str(working_stack_latest_path), "service": service, "status": status},
            {"path": str(events_latest_path), "service": service, "event_ids": event_ids[:8]},
            {"path": str(spatial_graph_latest_path), "node": affected_spatial_nodes[1], "service": service},
            {"path": str(process_container_latest_path), "service": service, "container": runtime.get("container")},
        ]
        evidence_refs.extend(organ.get("evidence_refs") if isinstance(organ.get("evidence_refs"), list) else [])
        declared_modules = _nested_get(organ, ["declared", "modules"])
        episodes.append({
            "schema": f"{schema_prefix}_causal_episode_v1",
            "episode_id": episode_id,
            "episode_kind": "working_stack_usage_gap",
            "service": service,
            "owner_route": "abyss-stack",
            "working_stack_link_id": link_id or None,
            "time_window": {
                "start": _nested_get(link, ["time", "observed_at"]) or generated_at,
                "end": generated_at,
                "bucket": _nested_get(link, ["time", "bucket"]) or self_awareness_contracts.time_bucket(generated_at),
            },
            "affected_spatial_nodes": sorted(set(item for item in affected_spatial_nodes if item)),
            "involved_contexts": [{
                "service": service,
                "working_stack_link_id": link_id or None,
                "machine_usage_status": status,
                "usage_gap": gap_reason,
                "failed_probe_names": failed_probe_names,
                "ok_probe_names": ok_probe_names,
            }],
            "primary_signals": sorted(set([
                "working_stack",
                "spatial_graph",
                "usage_gap",
                "container_health" if runtime else "",
                "runtime_smoke" if failed_probe_names else "",
                "tool_probe" if probes else "",
            ]).difference({""})),
            "sources": sorted(set([
                "working-stack",
                "self_awareness_spatial_graph",
                "process_container_health" if runtime else "",
            ]).difference({""})),
            "suspected_cause_chain": [
                "candidate: working stack organ is present in the machine body but not fully usable by the self-awareness loop",
                "candidate: usage_gap/status/link/probe evidence describe missing potential, not a root-cause fact",
                "owner-routed stack review is required before this organ can be treated as fully exhausted potential",
            ],
            "counter_evidence": [
                "a usage gap is a capability or runtime-smoke finding, not proof of a stack incident",
                "abyss-machine has not mutated stack state and does not execute a repair",
                "closure requires a later working-stack smoke plus self-awareness/reaction/response verifier success",
            ],
            "confidence": {"score": confidence_score, "reasons": confidence_reasons},
            "open_questions": [
                "Which stack-owned activation or runtime artifact closes this organ-level usage gap?",
                "Which bounded smoke proves the organ is usable without storing private content or mutating stack state?",
            ],
            "event_ids": event_ids,
            "reaction_candidate_refs": [],
            "working_stack_gap": {
                "schema": f"{schema_prefix}_self_awareness_working_stack_usage_gap_v1",
                "service": service,
                "owner_route": "abyss-stack",
                "working_stack_link_id": link_id or None,
                "machine_usage_status": status,
                "activation_kind": self_awareness_contracts.working_stack_gap_activation_kind(status),
                "usage_gap": gap_reason,
                "runtime_present": bool(runtime and runtime.get("present") is not False),
                "runtime_running": runtime.get("running"),
                "container": runtime.get("container"),
                "health": runtime.get("health"),
                "runtime_state": runtime.get("state"),
                "runtime_status": runtime.get("status"),
                "runtime_stack_managed": runtime.get("stack_managed"),
                "declared": _nested_get(organ, ["declared", "present"]),
                "declared_modules": declared_modules if isinstance(declared_modules, list) else [],
                "endpoint_ok": organ.get("endpoint_ok"),
                "service_roots": organ.get("service_roots"),
                "model_roots": organ.get("model_roots"),
                "deep_usage_proven": organ.get("deep_usage_proven"),
                "failed_probe_names": failed_probe_names,
                "ok_probe_names": ok_probe_names,
                "endpoint_probe_count": len(probes),
                "closure_blocker_keys": [status, "usage_gap:" + self_awareness_contracts.stable_hash_json({"service": service, "status": status}, length=16)],
                "safe_next_action": safe_next_action,
                "verifier_commands": safe_next_action["verifier_commands"],
                "policy": {
                    "handoff_only": True,
                    "read_only": True,
                    "host_layer_mutates_stack": False,
                    "executes_commands": False,
                    "automatic_remediation": False,
                    "raw_private_content": False,
                },
            },
            "evidence_refs": evidence_refs[:40],
            "truth_level": "working_stack_gap_candidate",
            "policy": {
                "root_cause_claim": False,
                "handoff_only": True,
                "host_layer_mutates_stack": False,
                "executes_commands": False,
                "automatic_remediation": False,
            },
        })
    return episodes, episode_ids


def working_stack_events(
    inventory: Mapping[str, Any],
    generated_at: str,
    *,
    schema_prefix: str,
    previous_smoke: Mapping[str, Any],
    working_stack_latest_path: Path | str,
    host: str,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    organs = inventory.get("organs") if isinstance(inventory.get("organs"), list) else []
    previous_by_service = previous_smoke.get("by_service") if isinstance(previous_smoke.get("by_service"), Mapping) else {}
    latest_path = str(working_stack_latest_path)
    for organ in organs:
        if not isinstance(organ, Mapping):
            continue
        service = str(organ.get("service") or "")
        if not service:
            continue
        link = organ.get("time_space_context_link") if isinstance(organ.get("time_space_context_link"), Mapping) else {}
        runtime = organ.get("runtime") if isinstance(organ.get("runtime"), Mapping) else {}
        signal_route = working_stack_organ_signal_route(service, organ)
        current_state_digest = working_stack_organ_state_digest(organ)
        previous_row = previous_by_service.get(service) if isinstance(previous_by_service.get(service), Mapping) else None
        selection = working_stack_organ_movement_selection(
            organ,
            current_state_digest=current_state_digest,
            previous_row=previous_row,
            schema_prefix=schema_prefix,
        )
        movement_packet_id = "samove-" + self_awareness_contracts.stable_hash_json({
            "service": service,
            "working_stack_link_id": link.get("link_id"),
            "state": current_state_digest,
            "observed_at": generated_at,
        }, length=24)
        context = link.get("context") if isinstance(link.get("context"), Mapping) else {}
        context = {
            "working_stack_link_id": context.get("working_stack_link_id") or link.get("link_id"),
            "machine_usage_status": organ.get("machine_usage_status"),
            "movement_packet_id": movement_packet_id,
            "pid": runtime.get("pid"),
            "pid_alive": runtime.get("pid_alive"),
            "current_state_digest": current_state_digest,
            "state_changed": selection.get("state_changed"),
        }
        evidence_refs = [
            {"path": latest_path, "service": service, "working_stack_link_id": link.get("link_id")},
            *(
                organ.get("evidence_refs")
                if isinstance(organ.get("evidence_refs"), list)
                else [{"path": latest_path}]
            ),
        ]
        events.append(self_awareness_contracts.make_event(
            "organ_movement",
            "working-stack",
            event_time=generated_at,
            source_query=f"abyss-machine self-awareness working-stack --json#organs.{service}",
            resource={
                "service": service,
                "container": runtime.get("container"),
                "pid": runtime.get("pid"),
                "pid_alive": runtime.get("pid_alive"),
                "owner_surface": "abyss-stack",
                "path": latest_path,
                "model": service if organ.get("model_roots") else None,
                "route": "working-stack/" + service,
                "observed_signal": signal_route.get("signal"),
                "observed_source": signal_route.get("source"),
                "movement_packet_id": movement_packet_id,
                "machine_usage_status": organ.get("machine_usage_status"),
                "movement_categories": selection.get("categories") if isinstance(selection.get("categories"), list) else [],
                "selected_reason": selection.get("selected_reason"),
                "not_selected_reason": selection.get("not_selected_reason"),
                "degradation_reasons": selection.get("degradation_reasons") if isinstance(selection.get("degradation_reasons"), list) else [],
                "selected_for_episode": selection.get("selected_for_episode"),
                "selected_for_resident_reasoning": selection.get("selected_for_resident_reasoning"),
                "write": False,
            },
            context=context,
            space={
                "host": host,
                "owner_surface": "abyss-stack",
                "layer": "working-stack-runtime",
                "service": service,
                "container": runtime.get("container"),
                "pid": runtime.get("pid"),
                "pid_alive": runtime.get("pid_alive"),
                "route": "working-stack/" + service,
                "path": latest_path,
            },
            severity=(
                "warning" if selection.get("selected_for_resident_reasoning")
                else "notice" if selection.get("selected_for_episode")
                else "info" if organ.get("deep_usage_proven")
                else "notice"
            ),
            confidence={
                "score": 0.9 if runtime.get("running") or organ.get("endpoint_ok") else 0.7,
                "reason": "Read-only working stack inventory projected as an organ movement observation",
            },
            body={
                "schema": f"{schema_prefix}_self_awareness_stack_organ_movement_observation_v1",
                "movement_packet_id": movement_packet_id,
                "service": service,
                "observed_signal": signal_route.get("signal"),
                "observed_source": signal_route.get("source"),
                "roles": organ.get("roles"),
                "container": runtime.get("container"),
                "pid": runtime.get("pid"),
                "pid_alive": runtime.get("pid_alive"),
                "runtime_running": runtime.get("running"),
                "health": runtime.get("health"),
                "declared": _nested_get(organ, ["declared", "present"]),
                "endpoint_ok": organ.get("endpoint_ok"),
                "machine_usage_status": organ.get("machine_usage_status"),
                "deep_usage_proven": organ.get("deep_usage_proven"),
                "usage_gap": organ.get("usage_gap"),
                "current_state_digest": current_state_digest,
                "movement_selection": selection,
                "stack_source_ref_count": len(organ.get("stack_source_refs") if isinstance(organ.get("stack_source_refs"), list) else []),
            },
            evidence_refs=evidence_refs[:12],
            truth_level="working_stack_movement_observation",
            schema_prefix=schema_prefix,
        ))
    return events


def resource_preflight(
    operation: str,
    *,
    schema_prefix: str,
    env_get: EnvGetPort,
    meminfo_reader: MeminfoReaderPort,
    cpu_count_reader: CpuCountReaderPort,
    loadavg_reader: LoadAverageReaderPort,
) -> dict[str, Any]:
    meminfo = meminfo_reader()
    cpu_count = max(1, cpu_count_reader() or 1)
    try:
        load1, load5, load15 = loadavg_reader()
    except OSError:
        load1 = load5 = load15 = 0.0
    min_mem_available = env_int("ABYSS_MACHINE_SELF_AWARENESS_MIN_MEM_AVAILABLE_MB", 3072, env_get=env_get) * 1024 * 1024
    min_swap_free = env_int("ABYSS_MACHINE_SELF_AWARENESS_MIN_SWAP_FREE_MB", 2048, env_get=env_get) * 1024 * 1024
    max_load_per_cpu = env_float("ABYSS_MACHINE_SELF_AWARENESS_MAX_LOAD_PER_CPU", 4.0, env_get=env_get)
    guard_enabled = env_get("ABYSS_MACHINE_SELF_AWARENESS_RESOURCE_GUARD") != "0"
    mem_available = meminfo.get("MemAvailable", 0)
    swap_total = meminfo.get("SwapTotal", 0)
    swap_free = meminfo.get("SwapFree", 0)
    denial_reasons: list[str] = []
    if mem_available and mem_available < min_mem_available:
        denial_reasons.append("mem_available_below_floor")
    if swap_total > 0 and swap_free < min_swap_free:
        denial_reasons.append("swap_free_below_floor")
    if load1 > (float(cpu_count) * max_load_per_cpu):
        denial_reasons.append("load_average_above_cpu_floor")
    ok = (not guard_enabled) or not denial_reasons
    return {
        "schema": f"{schema_prefix}_self_awareness_resource_preflight_v1",
        "operation": operation,
        "ok": ok,
        "status": "ok" if ok else "resource_denied",
        "denial_reasons": denial_reasons,
        "checks": {
            "mem_available_bytes": mem_available,
            "swap_total_bytes": swap_total,
            "swap_free_bytes": swap_free,
            "load1": round(load1, 2),
            "load5": round(load5, 2),
            "load15": round(load15, 2),
            "cpu_count": cpu_count,
        },
        "thresholds": {
            "min_mem_available_bytes": min_mem_available,
            "min_swap_free_bytes": min_swap_free,
            "max_load_per_cpu": max_load_per_cpu,
        },
        "policy": {
            "guard_enabled": guard_enabled,
            "host_layer_mutates_stack": False,
            "heavy_operation_must_fail_closed_under_pressure": True,
        },
    }


def probe_resource_denied_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    run_id: str,
    traceparent: str,
    resource_preflight: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_self_awareness_probe_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "status": "resource_denied",
        "run_id": run_id,
        "traceparent": traceparent,
        "resource_preflight": dict(resource_preflight),
        "chain": {},
        "summary": {
            "status": "resource_denied",
            "chain_passed": 0,
            "chain_total": 0,
            "resource_guard_ok": False,
            "resource_guard_reasons": resource_preflight.get("denial_reasons"),
        },
        "policy": {
            "writes_project_roots": False,
            "restarts_stack_services": False,
            "synthetic_alert_mutates_stack_rules": False,
            "heavy_operation_must_fail_closed_under_pressure": True,
        },
        "evidence_refs": [{"source": "/proc/meminfo"}, {"source": "os.getloadavg"}],
    }


def cycle_resource_denied_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    cycle_id: str,
    resource_preflight: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_self_awareness_cycle_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "status": "resource_denied",
        "cycle_id": cycle_id,
        "probe_run_id": None,
        "resource_preflight": dict(resource_preflight),
        "summary": {
            "status": "resource_denied",
            "steps": 0,
            "chain_passed": 0,
            "chain_total": 0,
            "resource_guard_ok": False,
            "resource_guard_reasons": resource_preflight.get("denial_reasons"),
        },
        "cycle_chain": {},
        "steps": [],
        "issues": {"resource_preflight": dict(resource_preflight)},
        "policy": {
            "host_layer_mutates_stack": False,
            "automatic_remediation": False,
            "open_stack_requirements_are_blockers_not_host_failures": True,
            "working_stack_activation_gaps_are_blockers_not_host_failures": True,
            "heavy_operation_must_fail_closed_under_pressure": True,
        },
        "evidence_refs": [{"source": "/proc/meminfo"}, {"source": "os.getloadavg"}],
    }


def cycle_partial_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    cycle_id: str,
    probe_run_id: str,
    steps: Iterable[Mapping[str, Any]],
    resource_preflight: Mapping[str, Any],
    cycle_chain: Mapping[str, Any],
    bridge_proof: Mapping[str, Any],
    stack_handoff_summary: Mapping[str, Any],
    stack_handoff_closure_readiness: Mapping[str, Any],
    automatic_response_count: int,
    mutating_response_routes: int,
) -> dict[str, Any]:
    step_rows = list(steps)
    return {
        "schema": f"{schema_prefix}_self_awareness_cycle_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "status": "building",
        "cycle_id": cycle_id,
        "probe_run_id": probe_run_id,
        "summary": {"status": "building", "steps": len(step_rows)},
        "steps": step_rows,
        "resource_preflight": dict(resource_preflight),
        "cycle_chain": dict(cycle_chain),
        "bridge_proof": dict(bridge_proof),
        "stack_handoff_summary": dict(stack_handoff_summary),
        "stack_handoff_closure_readiness": dict(stack_handoff_closure_readiness),
        "evidence_refs": [{"path": str(step["artifact"]["path"]), "step": step["id"]} for step in step_rows],
        "policy": {
            "host_layer_mutates_stack": False,
            "automatic_remediation": False,
            "automatic_responses": automatic_response_count,
            "routes_with_mutating_command_if_run": mutating_response_routes,
            "open_stack_requirements_are_blockers_not_host_failures": True,
        },
    }


def cycle_stack_handoff_summary_document(
    *,
    schema_prefix: str,
    stack_handoff_closure_readiness: Mapping[str, Any],
    replay: Mapping[str, Any],
    requirement_probes: Mapping[str, Any],
    stack_closure_dossier: Mapping[str, Any],
    working_stack_activation_summary: Mapping[str, Any],
    activation_smoke: Mapping[str, Any],
    open_requirement_rows: Iterable[Mapping[str, Any]],
    paths: Mapping[str, Path | str],
) -> dict[str, Any]:
    open_requirement_ids = stack_handoff_closure_readiness.get("open_requirement_ids")
    working_stack_activation_smoke_summary = activation_smoke.get("summary")
    working_stack_activation_handoff = stack_closure_dossier.get("working_stack_activation_handoff")
    return {
        "schema": f"{schema_prefix}_self_awareness_cycle_stack_handoff_summary_v1",
        "open_requirement_ids": open_requirement_ids if isinstance(open_requirement_ids, list) else [],
        "closure_readiness_summary": stack_handoff_closure_readiness.get("summary"),
        "replay": replay.get("stack_handoff_replay"),
        "requirement_probe_summary": requirement_probes.get("summary"),
        "stack_closure_dossier_summary": stack_closure_dossier.get("summary"),
        "working_stack_activation_summary": dict(working_stack_activation_summary),
        "working_stack_activation_smoke_summary": working_stack_activation_smoke_summary if isinstance(working_stack_activation_smoke_summary, dict) else {},
        "working_stack_activation_handoff": working_stack_activation_handoff if isinstance(working_stack_activation_handoff, dict) else {},
        "stack_closure_dossier_latest": str(paths["stack_closure_dossier"]),
        "failure_matrix_open_rows": len(list(open_requirement_rows)),
        "policy": {
            "handoff_only": True,
            "read_only": True,
            "executes_commands": False,
            "action_execution": False,
            "host_layer_mutates_stack": False,
            "open_stack_requirements_are_blockers_not_host_failures": True,
            "working_stack_activation_gaps_are_blockers_not_host_failures": True,
        },
        "evidence_refs": [
            {"path": str(paths["requirement_probes"]), "section": "closure_readiness"},
            {"path": str(paths["stack_closure_dossier"]), "section": "stack_owner_handoff"},
            {"path": str(paths["stack_closure_dossier"]), "section": "working_stack_activation_dossier"},
            {"path": str(paths["working_stack"]), "section": "machine_usage_gaps"},
            {"path": str(paths["replay"]), "section": "stack_handoff_replay"},
        ],
    }


def cycle_result_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    cycle_id: str,
    probe_run_id: str,
    steps: Iterable[Mapping[str, Any]],
    resource_preflight: Mapping[str, Any],
    cycle_chain: Mapping[str, Any],
    bridge_proof: Mapping[str, Any],
    activation_smoke: Mapping[str, Any],
    autolink: Mapping[str, Any],
    stack_handoff_summary: Mapping[str, Any],
    stack_handoff_closure_readiness: Mapping[str, Any],
    stack_closure_dossier: Mapping[str, Any],
    replay: Mapping[str, Any],
    responses: Mapping[str, Any],
    export: Mapping[str, Any],
    from_zero_proof: Mapping[str, Any],
    e2e_lineage_proof: Mapping[str, Any],
    lineage: Mapping[str, Any],
    open_requirement_rows: Iterable[Mapping[str, Any]],
    open_working_stack_activation_gaps: int,
    working_stack_activation_summary: Mapping[str, Any],
    failed_steps: list[str],
    missing_chain: list[str],
    mutation_claims: list[Any],
    automatic_response_count: int,
    mutating_response_routes: int,
) -> dict[str, Any]:
    step_rows = list(steps)
    chain = dict(cycle_chain)
    open_rows = list(open_requirement_rows)
    activation_failed_services = _nested_get(activation_smoke, ["summary", "failed_services"])
    cycle_ok = (
        not failed_steps
        and not missing_chain
        and not mutation_claims
        and automatic_response_count == 0
        and mutating_response_routes == 0
        and from_zero_proof.get("ok") is True
        and e2e_lineage_proof.get("ok") is True
        and lineage.get("complete") is True
        and bridge_proof.get("ok") is True
    )
    status = "covered" if cycle_ok else "incomplete"
    return {
        "schema": f"{schema_prefix}_self_awareness_cycle_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": cycle_ok,
        "status": status,
        "cycle_id": cycle_id,
        "probe_run_id": probe_run_id,
        "summary": {
            "status": status,
            "steps": len(step_rows),
            "from_zero_proof_steps": _nested_get(from_zero_proof, ["summary", "proof_steps"]),
            "from_zero_chain_obligations": _nested_get(from_zero_proof, ["summary", "chain_obligations"]),
            "from_zero_proof_ok": from_zero_proof.get("ok"),
            "e2e_lineage_ok": e2e_lineage_proof.get("ok"),
            "e2e_lineage_rows": _nested_get(e2e_lineage_proof, ["summary", "rows"]),
            "e2e_lineage_missing_rows": _nested_get(e2e_lineage_proof, ["summary", "missing_rows"]),
            "lineage_complete": lineage.get("complete"),
            "lineage_artifacts": _nested_get(lineage, ["summary", "artifacts"]),
            "lineage_synthetic_event_ids": _nested_get(lineage, ["summary", "synthetic_event_ids"]),
            "bridge_proof_ok": bridge_proof.get("ok"),
            "bridge_proof_rows": _nested_get(bridge_proof, ["summary", "bridges"]),
            "failed_steps": failed_steps,
            "chain_passed": sum(1 for value in chain.values() if value),
            "chain_total": len(chain),
            "open_stack_requirements": len(open_rows),
            "stack_closure_dossier_entries": _nested_get(stack_closure_dossier, ["summary", "probes"]),
            "stack_closure_dossier_missing_checks": _nested_get(stack_closure_dossier, ["summary", "missing_checks"]),
            "stack_closure_dossier_dependency_edges": _nested_get(stack_closure_dossier, ["summary", "dependency_edges"]),
            "stack_requirement_closure_acceptance_packets": _nested_get(stack_closure_dossier, ["summary", "closure_acceptance_packets"]),
            "stack_requirement_closure_acceptance_packets_complete": _nested_get(stack_closure_dossier, ["summary", "closure_acceptance_packets_complete"]),
            "stack_requirement_compat_requirements": _nested_get(stack_closure_dossier, ["summary", "stack_requirement_compat_requirements"]),
            "working_stack_activation_gaps": open_working_stack_activation_gaps,
            "working_stack_activation_entries": _safe_int(working_stack_activation_summary.get("entries"), 0),
            "working_stack_activation_missing_checks": _safe_int(working_stack_activation_summary.get("missing_checks"), 0),
            "working_stack_activation_verifier_commands": _safe_int(working_stack_activation_summary.get("verifier_commands"), 0),
            "working_stack_activation_synthetic_scenarios": _safe_int(working_stack_activation_summary.get("synthetic_scenarios"), 0),
            "working_stack_activation_synthetic_scenarios_complete": _safe_int(working_stack_activation_summary.get("synthetic_scenarios_complete"), 0),
            "working_stack_activation_closure_acceptance_packets": _safe_int(working_stack_activation_summary.get("closure_acceptance_packets"), 0),
            "working_stack_activation_closure_acceptance_packets_complete": _safe_int(working_stack_activation_summary.get("closure_acceptance_packets_complete"), 0),
            "working_stack_activation_compat_requirements": _safe_int(working_stack_activation_summary.get("activation_compat_requirements"), 0),
            "working_stack_activation_smoke_rows": _safe_int(_nested_get(activation_smoke, ["summary", "rows"]), 0),
            "working_stack_activation_smoke_rows_ok": _safe_int(_nested_get(activation_smoke, ["summary", "rows_ok"]), 0),
            "working_stack_activation_smoke_failed_services": activation_failed_services if isinstance(activation_failed_services, list) else [],
            "activation_smoke_open_activation_gaps": _safe_int(_nested_get(activation_smoke, ["summary", "open_activation_gaps"]), 0),
            "working_stack_usage_gaps": _safe_int(
                _nested_get(autolink, ["summary", "working_stack_usage_gaps"]),
                _safe_int(_nested_get(activation_smoke, ["summary", "open_activation_gaps"]), open_working_stack_activation_gaps),
            ),
            "working_stack_link_integrity_rows": _nested_get(export, ["working_stack_link_integrity", "summary", "rows"]),
            "working_stack_link_integrity_rows_complete": _nested_get(export, ["working_stack_link_integrity", "summary", "complete_rows"]),
            "working_stack_link_integrity_missing_rows": _nested_get(export, ["working_stack_link_integrity", "summary", "missing_rows"]),
            "autolink_organ_links": _nested_get(autolink, ["summary", "organ_links"]),
            "autolink_organ_links_complete": _nested_get(autolink, ["summary", "organ_links_complete"]),
            "autolink_stack_requirement_links": _nested_get(autolink, ["summary", "stack_requirement_links"]),
            "autolink_working_stack_usage_gaps": _nested_get(autolink, ["summary", "working_stack_usage_gaps"]),
            "autolink_synthetic_scenarios_complete": _nested_get(autolink, ["summary", "synthetic_scenarios_complete"]),
            "autolink_state_changed": _nested_get(autolink, ["summary", "state_changed"]),
            "stack_handoff_closure_readiness_packets": _nested_get(stack_handoff_closure_readiness, ["summary", "packets"]),
            "stack_handoff_closure_readiness_missing_checks": _nested_get(stack_handoff_closure_readiness, ["summary", "missing_checks"]),
            "stack_handoff_closure_readiness_dependency_edges": _nested_get(stack_handoff_closure_readiness, ["summary", "dependency_edges"]),
            "stack_handoff_closure_readiness_replayable": _nested_get(replay, ["stack_handoff_replay", "closure_readiness_replayable"]),
            "resident_cognitive_replay_complete": _nested_get(replay, ["resident_cognitive_replay", "complete"]),
            "resident_cognitive_export_complete": _nested_get(export, ["resident_cognitive_replay", "complete"]),
            "body_trace_replayable": _nested_get(replay, ["body_trace_replay", "replayable"]),
            "response_body_trace_routes": _nested_get(responses, ["summary", "self_awareness_body_trace_routes"]),
            "response_body_trace_missing": _nested_get(responses, ["summary", "self_awareness_body_trace_missing"]),
            "body_trace_export_included": _nested_get(export, ["body_trace_handoff", "response_body_trace_included"]),
            "response_entity_event_document_routes": _nested_get(responses, ["summary", "self_awareness_entity_event_document_routes"]),
            "response_entity_event_document_missing": _nested_get(responses, ["summary", "self_awareness_entity_event_document_missing"]),
            "response_entity_event_document_export_included": _nested_get(export, ["portable_contract", "response_entity_event_document_context_included"]),
            "resident_cognitive_read_only_tools": _nested_get(replay, ["resident_cognitive_replay", "summary", "read_only_tools"]),
            "resident_cognitive_hypothesis_tests": _nested_get(replay, ["resident_cognitive_replay", "summary", "hypothesis_tests"]),
            "resident_cognitive_contradiction_notes": _nested_get(replay, ["resident_cognitive_replay", "summary", "contradiction_notes"]),
            "automatic_responses": automatic_response_count,
            "routes_with_mutating_command_if_run": mutating_response_routes,
            "resource_guard_ok": resource_preflight.get("ok"),
            "resource_guard_reasons": resource_preflight.get("denial_reasons"),
        },
        "cycle_chain": chain,
        "steps": step_rows,
        "from_zero_proof": dict(from_zero_proof),
        "e2e_lineage_proof": dict(e2e_lineage_proof),
        "lineage": dict(lineage),
        "bridge_proof": dict(bridge_proof),
        "activation_smoke": dict(activation_smoke),
        "autolink": dict(autolink),
        "stack_handoff_summary": dict(stack_handoff_summary),
        "stack_handoff_closure_readiness": dict(stack_handoff_closure_readiness),
        "open_stack_requirements": [
            {
                "id": str(row.get("id") or ""),
                "title": row.get("title"),
                "owner": row.get("owner"),
                "detector": row.get("detector"),
                "evidence_refs": row.get("evidence_refs"),
            }
            for row in open_rows
        ],
        "issues": {
            "failed_steps": failed_steps,
            "missing_chain": missing_chain,
            "mutation_claims": mutation_claims,
            "from_zero_proof": from_zero_proof.get("summary"),
            "e2e_lineage_proof": e2e_lineage_proof.get("summary"),
            "bridge_proof": bridge_proof.get("summary"),
        },
        "evidence_refs": [{"path": str(step["artifact"]["path"]), "step": step["id"]} for step in step_rows],
        "policy": {
            "host_layer_mutates_stack": False,
            "automatic_remediation": False,
            "automatic_responses": automatic_response_count,
            "routes_with_mutating_command_if_run": mutating_response_routes,
            "open_stack_requirements_are_blockers_not_host_failures": True,
            "working_stack_activation_gaps_are_blockers_not_host_failures": True,
            "claims_require_evidence_refs": True,
        },
        "tests": {
            "e2e_cycle": "probe -> failure-matrix -> investigate -> replay -> brief -> reactions -> responses -> export",
            "from_zero_command": "abyss-machine self-awareness cycle --json",
            "validate_command": "abyss-machine self-awareness validate --json",
        },
    }


def probe_movement_smoke_document(
    *,
    schema_prefix: str,
    paths: Mapping[str, Path | str],
    run_id: str,
    target_service: str,
    movement_packet_id: str,
    movement_selection: Mapping[str, Any],
    probe_movement_event: Mapping[str, Any],
    probe_movement_episode: Mapping[str, Any],
    investigation: Mapping[str, Any],
    replay: Mapping[str, Any],
    chain: Mapping[str, Any],
) -> dict[str, Any]:
    episode_id = probe_movement_episode.get("episode_id")
    return {
        "schema": f"{schema_prefix}_self_awareness_probe_movement_smoke_v1",
        "complete": bool(
            probe_movement_event.get("event_id")
            and episode_id
            and chain.get("movement_reaction_candidate")
            and chain.get("movement_response")
            and replay.get("ok") is True
            and _nested_get(replay, ["resident_cognitive_replay", "complete"]) is True
        ),
        "service": target_service,
        "movement_packet_id": movement_packet_id,
        "event_id": probe_movement_event.get("event_id"),
        "episode_id": episode_id,
        "investigation_thread_id": investigation.get("thread_id"),
        "replay_thread_id": replay.get("thread_id"),
        "selected_reason": movement_selection.get("selected_reason"),
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "automatic_remediation": False,
            "runtime_incident_claim": False,
        },
        "evidence_refs": [
            {"path": str(paths.get("events") or ""), "event_id": probe_movement_event.get("event_id")},
            {"path": str(paths.get("episodes") or ""), "episode_id": episode_id},
            {"path": str(paths.get("investigate") or ""), "thread_id": investigation.get("thread_id")},
            {"path": str(paths.get("replay") or ""), "thread_id": replay.get("thread_id")},
            {"path": str(paths.get("reactions") or ""), "episode_id": episode_id},
            {"path": str(paths.get("responses") or ""), "episode_id": episode_id},
            {"path": str(paths.get("export") or ""), "run_id": run_id},
        ],
    }


def probe_result_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    run_id: str,
    traceparent: str,
    target_url: str,
    response: Mapping[str, Any],
    resource_preflight: Mapping[str, Any],
    chain: Mapping[str, Any],
    e2e_lineage_proof: Mapping[str, Any],
    lineage: Mapping[str, Any],
    synthetic_event_refs: list[dict[str, Any]],
    artifacts: Mapping[str, str],
    target_service: str,
    movement_packet_id: str,
    movement_selection: Mapping[str, Any],
    probe_movement_event: Mapping[str, Any],
    probe_movement_episode: Mapping[str, Any],
    investigation: Mapping[str, Any],
    replay: Mapping[str, Any],
    alerts: Mapping[str, Any],
    autolink: Mapping[str, Any],
    paths: Mapping[str, Path | str],
) -> dict[str, Any]:
    chain_values = list(chain.values())
    complete = all(chain_values) and e2e_lineage_proof.get("ok") is True and lineage.get("complete") is True
    movement_episode_id = probe_movement_episode.get("episode_id")
    return {
        "schema": f"{schema_prefix}_self_awareness_probe_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": complete,
        "run_id": run_id,
        "traceparent": traceparent,
        "target": {"url": target_url, "safe": True, "method": "GET", "mutates_stack": False},
        "response": dict(response),
        "resource_preflight": dict(resource_preflight),
        "chain": dict(chain),
        "e2e_lineage_proof": dict(e2e_lineage_proof),
        "lineage": dict(lineage),
        "synthetic_events": synthetic_event_refs,
        "movement_smoke": probe_movement_smoke_document(
            schema_prefix=schema_prefix,
            paths=paths,
            run_id=run_id,
            target_service=target_service,
            movement_packet_id=movement_packet_id,
            movement_selection=movement_selection,
            probe_movement_event=probe_movement_event,
            probe_movement_episode=probe_movement_episode,
            investigation=investigation,
            replay=replay,
            chain=chain,
        ),
        "artifacts": dict(artifacts),
        "summary": {
            "status": "ok" if complete else "degraded",
            "chain_passed": sum(1 for value in chain_values if value),
            "chain_total": len(chain_values),
            "reaction_candidates": _nested_get(alerts, ["summary", "reaction_candidates"]),
            "movement_smoke_complete": bool(movement_episode_id and chain.get("movement_reaction_candidate") and chain.get("movement_response")),
            "movement_smoke_service": target_service,
            "movement_smoke_episode_id": movement_episode_id,
            "e2e_lineage_ok": e2e_lineage_proof.get("ok"),
            "e2e_lineage_rows": _nested_get(e2e_lineage_proof, ["summary", "rows"]),
            "e2e_lineage_missing_rows": _nested_get(e2e_lineage_proof, ["summary", "missing_rows"]),
            "lineage_complete": lineage.get("complete"),
            "lineage_artifacts": _nested_get(lineage, ["summary", "artifacts"]),
            "lineage_synthetic_event_ids": _nested_get(lineage, ["summary", "synthetic_event_ids"]),
            "autolink_organ_links": _nested_get(autolink, ["summary", "organ_links"]),
            "autolink_organ_links_complete": _nested_get(autolink, ["summary", "organ_links_complete"]),
            "autolink_stack_requirement_links": _nested_get(autolink, ["summary", "stack_requirement_links"]),
            "autolink_synthetic_scenarios_complete": _nested_get(autolink, ["summary", "synthetic_scenarios_complete"]),
            "resource_guard_ok": resource_preflight.get("ok"),
            "resource_guard_reasons": resource_preflight.get("denial_reasons"),
        },
        "policy": {
            "writes_project_roots": False,
            "restarts_stack_services": False,
            "synthetic_alert_mutates_stack_rules": False,
        },
        "tests": {
            "e2e_chain": "request -> metric/log/trace/log context -> event -> timeline -> graph -> episode -> alert -> warm-E2B/RAG/nervous context -> investigation -> reaction/response -> brief -> export",
            "searchable_run_id": run_id,
        },
    }


def _cycle_artifact_document(
    spec: CycleArtifactStepSpec,
    *,
    direct_documents: Mapping[str, Mapping[str, Any]],
    latest_documents: Mapping[str, Mapping[str, Any]],
    bridge_documents: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    groups = {
        "direct": direct_documents,
        "latest": latest_documents,
        "bridge": bridge_documents,
    }
    try:
        group = groups[spec.document_group]
    except KeyError as exc:
        raise KeyError(f"unknown cycle artifact document group for {spec.step_id}: {spec.document_group}") from exc
    try:
        document = group[spec.document_key]
    except KeyError as exc:
        raise KeyError(f"missing cycle artifact document for {spec.step_id}: {spec.document_group}.{spec.document_key}") from exc
    return dict(document) if isinstance(document, Mapping) else {}


def cycle_artifact_steps(
    *,
    specs: Iterable[CycleArtifactStepSpec],
    paths: Mapping[str, Path | str],
    direct_documents: Mapping[str, Mapping[str, Any]],
    latest_documents: Mapping[str, Mapping[str, Any]] | None = None,
    bridge_documents: Mapping[str, Mapping[str, Any]] | None = None,
    path_exists: PathExistsPort,
    path_stat: PathStatPort,
    path_sha256: PathSha256Port,
    evidence_extra_by_step: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    latest_documents = latest_documents or {}
    bridge_documents = bridge_documents or {}
    evidence_extra_by_step = evidence_extra_by_step or {}
    steps: list[dict[str, Any]] = []
    for spec in specs:
        try:
            artifact_path = paths[spec.path_key]
        except KeyError as exc:
            raise KeyError(f"missing cycle artifact path for {spec.step_id}: {spec.path_key}") from exc
        steps.append(
            cycle_artifact_step(
                spec.step_id,
                spec.command,
                Path(artifact_path),
                _cycle_artifact_document(
                    spec,
                    direct_documents=direct_documents,
                    latest_documents=latest_documents,
                    bridge_documents=bridge_documents,
                ),
                path_exists=path_exists,
                path_stat=path_stat,
                path_sha256=path_sha256,
                requires_ok=spec.requires_ok,
                evidence_extra=evidence_extra_by_step.get(spec.step_id),
            )
        )
    return steps


def cycle_artifact_step(
    step_id: str,
    command: str,
    artifact_path: Path,
    document: dict[str, Any],
    *,
    path_exists: PathExistsPort,
    path_stat: PathStatPort,
    path_sha256: PathSha256Port,
    requires_ok: bool = True,
    evidence_extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    path = Path(artifact_path)
    exists = path_exists(path)
    stat_result = path_stat(path) if exists else None
    mtime = getattr(stat_result, "st_mtime", None) if stat_result is not None else None
    evidence: dict[str, Any] = {
        "path": str(path),
        "schema": document.get("schema"),
        "generated_at": document.get("generated_at"),
        "status": document.get("status"),
        "ok": document.get("ok"),
        "summary": document.get("summary"),
        "exists": exists,
        "size_bytes": getattr(stat_result, "st_size", None) if stat_result is not None else None,
        "sha256": path_sha256(path) if exists else None,
        "mtime_ns": getattr(stat_result, "st_mtime_ns", None) if stat_result is not None else None,
        "mtime_iso": dt.datetime.fromtimestamp(mtime, tz=dt.timezone.utc).isoformat() if mtime is not None else None,
    }
    if evidence_extra:
        evidence.update(dict(evidence_extra))
    return {
        "id": step_id,
        "command": command,
        "ok": bool(document.get("ok", True)) if requires_ok else True,
        "artifact": evidence,
    }

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

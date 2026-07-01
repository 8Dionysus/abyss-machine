from __future__ import annotations

import collections
import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from . import self_awareness_contracts


LatestJsonReaderPort = Callable[[Path, str], dict[str, Any]]
EnvGetPort = Callable[[str], str | None]
MeminfoTextReaderPort = Callable[[], str]
MeminfoReaderPort = Callable[[], dict[str, int]]
CpuCountReaderPort = Callable[[], int | None]
LoadAverageReaderPort = Callable[[], tuple[float, float, float]]
ClockPort = Callable[[], float]
HttpRequestFactoryPort = Callable[[str, Mapping[str, str], str], Any]
HttpOpenPort = Callable[[Any, float], Any]
PathExistsPort = Callable[[Path], bool]
PathIsDirPort = Callable[[Path], bool]
PathGlobPort = Callable[[Path, str], Iterable[Path]]
PathIterdirPort = Callable[[Path], Iterable[Path]]
PathReadTextPort = Callable[[Path], str]
PathStatPort = Callable[[Path], Any]
PathSha256Port = Callable[[Path], str]
JsonDocumentLoaderPort = Callable[[Path], tuple[Any, str | None]]


@dataclass(frozen=True)
class SelfAwarenessLatestSpec:
    name: str
    path: Path
    schema: str


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

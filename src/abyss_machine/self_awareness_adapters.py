from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from . import self_awareness_contracts


LatestJsonReaderPort = Callable[[Path, str], dict[str, Any]]


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

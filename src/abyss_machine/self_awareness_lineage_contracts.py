from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import self_awareness_contracts


DocumentPort = Callable[..., Any]


@dataclass(frozen=True)
class SelfAwarenessLineagePaths:
    capabilities_latest: Path
    requirements_latest: Path
    requirement_probes_latest: Path
    stack_closure_dossier_latest: Path
    trace_context_latest: Path
    failure_matrix_latest: Path
    working_stack_latest: Path
    collect_latest: Path
    events_latest: Path
    query_latest: Path
    correlation_latest: Path
    timeline_latest: Path
    spatial_graph_latest: Path
    context_latest: Path
    episodes_latest: Path
    alerts_latest: Path
    investigate_latest: Path
    replay_latest: Path
    brief_latest: Path
    reactions_latest: Path
    responses_latest: Path
    autolink_latest: Path
    completion_audit_latest: Path
    export_latest: Path
    probe_latest: Path
    activation_smoke_latest: Path
    cycle_latest: Path


@dataclass(frozen=True)
class SelfAwarenessLineageConfig:
    schema_prefix: str
    version: str


@dataclass(frozen=True)
class SelfAwarenessLineageRuntimePort:
    latest_artifact_ref: DocumentPort
    path_exists: DocumentPort
    path_stat: DocumentPort
    path_is_file: DocumentPort
    sha256_path: DocumentPort


def e2e_lineage_artifact_specs(
    include_cycle: bool = False,
    include_probe: bool = True,
    *,
    paths: SelfAwarenessLineagePaths,
    config: SelfAwarenessLineageConfig,
) -> dict[str, tuple[Path, str]]:
    specs: dict[str, tuple[Path, str]] = {
        "capabilities": (
            paths.capabilities_latest,
            f"{config.schema_prefix}_self_awareness_capabilities_v1",
        ),
        "requirements": (
            paths.requirements_latest,
            f"{config.schema_prefix}_self_awareness_requirements_v1",
        ),
        "requirement_probes": (
            paths.requirement_probes_latest,
            f"{config.schema_prefix}_self_awareness_requirement_probes_v1",
        ),
        "stack_closure_dossier": (
            paths.stack_closure_dossier_latest,
            f"{config.schema_prefix}_self_awareness_stack_closure_dossier_v1",
        ),
        "trace_context": (
            paths.trace_context_latest,
            f"{config.schema_prefix}_self_awareness_trace_context_fallback_v1",
        ),
        "failure_matrix": (
            paths.failure_matrix_latest,
            f"{config.schema_prefix}_self_awareness_failure_matrix_v1",
        ),
        "working_stack": (
            paths.working_stack_latest,
            f"{config.schema_prefix}_self_awareness_working_stack_inventory_v1",
        ),
        "collect": (
            paths.collect_latest,
            f"{config.schema_prefix}_self_awareness_collect_v1",
        ),
        "events": (
            paths.events_latest,
            f"{config.schema_prefix}_self_awareness_events_v1",
        ),
        "query": (
            paths.query_latest,
            f"{config.schema_prefix}_self_awareness_query_v1",
        ),
        "correlation": (
            paths.correlation_latest,
            f"{config.schema_prefix}_self_awareness_correlation_v1",
        ),
        "timeline": (
            paths.timeline_latest,
            f"{config.schema_prefix}_self_awareness_timeline_v1",
        ),
        "spatial_graph": (
            paths.spatial_graph_latest,
            f"{config.schema_prefix}_self_awareness_spatial_graph_v1",
        ),
        "context": (
            paths.context_latest,
            f"{config.schema_prefix}_self_awareness_context_v1",
        ),
        "episodes": (
            paths.episodes_latest,
            f"{config.schema_prefix}_self_awareness_episodes_v1",
        ),
        "alerts": (
            paths.alerts_latest,
            f"{config.schema_prefix}_self_awareness_alerts_v1",
        ),
        "investigate": (
            paths.investigate_latest,
            f"{config.schema_prefix}_self_awareness_investigation_v1",
        ),
        "replay": (
            paths.replay_latest,
            f"{config.schema_prefix}_self_awareness_replay_v1",
        ),
        "brief": (
            paths.brief_latest,
            f"{config.schema_prefix}_self_awareness_brief_v1",
        ),
        "reactions": (
            paths.reactions_latest,
            f"{config.schema_prefix}_reactions_status_v1",
        ),
        "responses": (
            paths.responses_latest,
            f"{config.schema_prefix}_responses_status_v1",
        ),
        "autolink": (
            paths.autolink_latest,
            f"{config.schema_prefix}_self_awareness_autolink_v1",
        ),
        "completion_audit": (
            paths.completion_audit_latest,
            f"{config.schema_prefix}_self_awareness_completion_audit_v1",
        ),
        "export": (
            paths.export_latest,
            f"{config.schema_prefix}_self_awareness_export_v1",
        ),
    }
    if include_probe:
        specs["probe"] = (
            paths.probe_latest,
            f"{config.schema_prefix}_self_awareness_probe_v1",
        )
    if include_cycle:
        specs["activation_smoke"] = (
            paths.activation_smoke_latest,
            f"{config.schema_prefix}_self_awareness_working_stack_activation_smoke_v1",
        )
        specs["cycle"] = (
            paths.cycle_latest,
            f"{config.schema_prefix}_self_awareness_cycle_v1",
        )
    return specs


def e2e_lineage_specs() -> list[dict[str, Any]]:
    return [
        {
            "id": "synthetic_request",
            "title": "Synthetic traceparent request enters a safe stack health route",
            "chain_key_groups": [["request", "synthetic_request"]],
            "artifacts": ["probe", "collect", "events"],
            "from": "probe",
            "to": "collect",
        },
        {
            "id": "signal_fabric",
            "title": "Metrics, logs, trace context, alerts, model, RAG, and nervous events normalize into one fabric",
            "chain_key_groups": [
                ["metric", "signal_fabric"],
                ["log", "signal_fabric"],
                ["trace_context", "signal_fabric"],
                ["context", "signal_fabric"],
                ["observation_events", "signal_fabric"],
            ],
            "artifacts": ["collect", "events", "trace_context"],
            "from": "collect",
            "to": "events",
        },
        {
            "id": "trace_context_fallback",
            "title": "Trace context fallback exposes Loki/Alloy/probe links without closing the stack trace-backend requirement",
            "chain_key_groups": [["trace_context_fallback"]],
            "artifacts": [
                "trace_context",
                "requirement_probes",
                "stack_closure_dossier",
            ],
            "from": "requirement_probes",
            "to": "replay",
        },
        {
            "id": "working_stack_body",
            "title": "Actual working stack organs are inventoried and projected into time-space-context links",
            "chain_key_groups": [["working_stack"]],
            "artifacts": [
                "working_stack",
                "collect",
                "events",
                "timeline",
                "spatial_graph",
                "context",
            ],
            "from": "collect",
            "to": "spatial_graph",
        },
        {
            "id": "query_and_correlation",
            "title": "Bounded PromQL, LogQL, RAG, graph, and readmodel query evidence is correlated",
            "chain_key_groups": [["query"], ["correlation"]],
            "artifacts": ["query", "correlation", "context"],
            "from": "events",
            "to": "correlation",
        },
        {
            "id": "timeline",
            "title": "Correlated evidence is ordered in time",
            "chain_key_groups": [["timeline"]],
            "artifacts": ["timeline", "correlation"],
            "from": "correlation",
            "to": "timeline",
        },
        {
            "id": "spatial_graph",
            "title": "Correlated evidence is placed in service/container/route/model space",
            "chain_key_groups": [["spatial_graph"]],
            "artifacts": ["spatial_graph", "context"],
            "from": "timeline",
            "to": "spatial_graph",
        },
        {
            "id": "causal_episode",
            "title": "Timeline and spatial evidence become bounded causal episodes",
            "chain_key_groups": [["causal_episode"]],
            "artifacts": ["episodes", "timeline", "spatial_graph"],
            "from": "spatial_graph",
            "to": "episodes",
        },
        {
            "id": "alert",
            "title": "Synthetic and observed alert evidence is routed without mutating stack alert rules",
            "chain_key_groups": [["alert"]],
            "artifacts": ["alerts", "collect"],
            "from": "episodes",
            "to": "alerts",
        },
        {
            "id": "warm_e2b_context",
            "title": "warm-E2B/gemma4 resident worker contributes monitored read-only cognitive context",
            "chain_key_groups": [["warm_e2b", "warm_e2b_worker"]],
            "artifacts": ["collect", "context", "investigate"],
            "from": "alerts",
            "to": "investigate",
        },
        {
            "id": "resident_cognitive_replay",
            "title": "warm-E2B cognitive packet replays with read-only tools, hypotheses, contradictions, and gated escalation",
            "chain_key_groups": [["resident_cognitive_replay"]],
            "artifacts": ["investigate", "replay"],
            "from": "investigate",
            "to": "replay",
        },
        {
            "id": "resident_cognitive_export",
            "title": "Portable export preserves the warm-E2B cognitive replay contract",
            "chain_key_groups": [["resident_cognitive_export"]],
            "artifacts": ["replay", "export"],
            "from": "replay",
            "to": "export",
        },
        {
            "id": "autolink",
            "title": "Cycle automatically records time-space-context state delta for organs and owner-routed blockers",
            "chain_key_groups": [["autolink"]],
            "artifacts": ["autolink", "working_stack", "coverage_audit", "episodes"],
            "from": "episodes",
            "to": "export",
        },
        {
            "id": "rag_memory",
            "title": "RAG and memory-space evidence stay bounded evidence, not truth publication",
            "chain_key_groups": [["rag_memory"]],
            "artifacts": ["query", "context", "collect"],
            "from": "query",
            "to": "context",
        },
        {
            "id": "nervous_freshness",
            "title": "Nervous freshness gates are present before reasoning",
            "chain_key_groups": [["nervous_freshness"]],
            "artifacts": ["collect", "context"],
            "from": "context",
            "to": "investigate",
        },
        {
            "id": "langgraph_investigation",
            "title": "Checkpointed investigation records plan/query/reason/validate states",
            "chain_key_groups": [["langgraph_investigation"]],
            "artifacts": ["investigate"],
            "from": "context",
            "to": "investigate",
        },
        {
            "id": "replay",
            "title": "Investigation can replay without stack mutation or action execution",
            "chain_key_groups": [["replay"]],
            "artifacts": ["replay", "investigate"],
            "from": "investigate",
            "to": "replay",
        },
        {
            "id": "reaction_candidate",
            "title": "Validated episodes become non-automatic reaction candidates",
            "chain_key_groups": [["reaction_candidate"]],
            "artifacts": ["alerts", "reactions"],
            "from": "alerts",
            "to": "reactions",
        },
        {
            "id": "governed_response",
            "title": "Response routes stay owner-gated and non-automatic",
            "chain_key_groups": [["governed_response"]],
            "artifacts": ["responses", "reactions"],
            "from": "reactions",
            "to": "responses",
        },
        {
            "id": "body_trace",
            "title": "Response routes preserve temporal, spatial, contextual, and host-body trace evidence",
            "chain_key_groups": [["body_trace"]],
            "artifacts": ["context", "investigate", "replay", "responses", "export"],
            "from": "responses",
            "to": "export",
        },
        {
            "id": "entity_event_document_context",
            "title": "Response routes preserve automatic entity, event, document, and route bindings",
            "chain_key_groups": [["entity_event_document"]],
            "artifacts": ["completion_audit", "responses", "export"],
            "from": "completion_audit",
            "to": "export",
        },
        {
            "id": "export",
            "title": "Portable export preserves evidence refs, stack handoff, and runbook candidates",
            "chain_key_groups": [["export"]],
            "artifacts": [
                "export",
                "requirements",
                "requirement_probes",
                "stack_closure_dossier",
            ],
            "from": "responses",
            "to": "export",
        },
    ]


def e2e_lineage_proof(
    *,
    generated_at: str,
    run_id: str,
    chain: dict[str, Any],
    traceparent: str | None = None,
    cycle_id: str | None = None,
    synthetic_events: list[dict[str, Any]] | None = None,
    include_cycle: bool = False,
    include_probe: bool = False,
    paths: SelfAwarenessLineagePaths,
    config: SelfAwarenessLineageConfig,
    runtime_port: SelfAwarenessLineageRuntimePort,
) -> dict[str, Any]:
    artifact_specs = e2e_lineage_artifact_specs(
        include_cycle=include_cycle,
        include_probe=include_probe,
        paths=paths,
        config=config,
    )
    artifact_refs = {
        name: runtime_port.latest_artifact_ref(name, path, schema)
        for name, (path, schema) in artifact_specs.items()
    }
    event_ids = [
        str(event.get("event_id"))
        for event in (synthetic_events if isinstance(synthetic_events, list) else [])
        if isinstance(event, dict) and event.get("event_id")
    ]
    trace_id = None
    span_id = None
    if traceparent:
        parts = str(traceparent).split("-")
        if len(parts) >= 4:
            trace_id = parts[1]
            span_id = parts[2]
    rows: list[dict[str, Any]] = []
    for index, spec in enumerate(e2e_lineage_specs(), start=1):
        artifact_names = [
            str(name) for name in spec.get("artifacts", []) if name in artifact_refs
        ]
        row_artifacts = [artifact_refs[name] for name in artifact_names]
        chain_groups = (
            spec.get("chain_key_groups")
            if isinstance(spec.get("chain_key_groups"), list)
            else []
        )
        group_results: list[dict[str, Any]] = []
        for group in chain_groups:
            keys = (
                [str(key) for key in group] if isinstance(group, list) else [str(group)]
            )
            matched = [key for key in keys if key in chain]
            group_results.append(
                {
                    "keys": keys,
                    "matched_keys": matched,
                    "satisfied": any((bool(chain.get(key)) for key in keys)),
                }
            )
        chain_satisfied = all((item.get("satisfied") is True for item in group_results))
        artifacts_ok = all(
            (
                artifact.get("exists") is True
                and artifact.get("schema_ok") is True
                and bool(artifact.get("sha256"))
                for artifact in row_artifacts
            )
        )
        evidence_refs = [
            {
                "path": artifact.get("path"),
                "schema": artifact.get("schema"),
                "sha256": artifact.get("sha256"),
                "lineage_step": spec.get("id"),
            }
            for artifact in row_artifacts
            if artifact.get("path")
        ]
        rows.append(
            {
                "schema": f"{config.schema_prefix}_self_awareness_e2e_lineage_row_v1",
                "order": index,
                "id": spec.get("id"),
                "title": spec.get("title"),
                "from": spec.get("from"),
                "to": spec.get("to"),
                "satisfied": chain_satisfied and artifacts_ok,
                "chain": {"groups": group_results, "satisfied": chain_satisfied},
                "artifacts": row_artifacts,
                "artifact_names": artifact_names,
                "artifacts_ok": artifacts_ok,
                "correlation": {
                    "run_id": run_id,
                    "traceparent": traceparent,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "synthetic_event_ids": event_ids,
                },
                "evidence_refs": evidence_refs,
                "policy": {
                    "read_only": True,
                    "host_layer_mutates_stack": False,
                    "actions_executed": False,
                    "automatic_remediation": False,
                    "raw_secrets_included": False,
                },
            }
        )
    missing_rows = [
        str(row.get("id")) for row in rows if row.get("satisfied") is not True
    ]
    data = {
        "schema": f"{config.schema_prefix}_self_awareness_e2e_lineage_proof_v1",
        "version": config.version,
        "generated_at": generated_at,
        "cycle_id": cycle_id,
        "run_id": run_id,
        "traceparent": traceparent,
        "ok": not missing_rows,
        "summary": {
            "rows": len(rows),
            "satisfied": sum((1 for row in rows if row.get("satisfied") is True)),
            "missing_rows": missing_rows,
            "artifacts": len(artifact_refs),
            "synthetic_event_ids": len(event_ids),
            "has_traceparent": bool(traceparent),
            "has_cycle_id": bool(cycle_id),
        },
        "rows": rows,
        "artifact_refs": artifact_refs,
        "lineage_order": [str(row.get("id")) for row in rows],
        "evidence_refs": [
            ref
            for row in rows
            for ref in (
                row.get("evidence_refs")
                if isinstance(row.get("evidence_refs"), list)
                else []
            )
        ],
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "actions_executed": False,
            "automatic_remediation": False,
            "raw_secrets_included": False,
            "raw_evidence_is_not_truth": True,
            "claims_require_evidence_refs": True,
        },
    }
    return data


def e2e_lineage_proof_complete(
    proof: Any, *, config: SelfAwarenessLineageConfig
) -> bool:
    if not isinstance(proof, dict):
        return False
    rows = proof.get("rows") if isinstance(proof.get("rows"), list) else []
    expected_ids = {str(spec.get("id")) for spec in e2e_lineage_specs()}
    row_ids = {
        str(row.get("id")) for row in rows if isinstance(row, dict) and row.get("id")
    }
    return (
        proof.get("schema")
        == f"{config.schema_prefix}_self_awareness_e2e_lineage_proof_v1"
        and proof.get("ok") is True
        and bool(proof.get("run_id"))
        and (row_ids == expected_ids)
        and (
            self_awareness_contracts.nested_get(proof, ["summary", "missing_rows"])
            == []
        )
        and (
            self_awareness_contracts.nested_get(
                proof, ["policy", "host_layer_mutates_stack"]
            )
            is False
        )
        and (
            self_awareness_contracts.nested_get(proof, ["policy", "actions_executed"])
            is False
        )
        and (
            self_awareness_contracts.nested_get(
                proof, ["policy", "automatic_remediation"]
            )
            is False
        )
        and (
            self_awareness_contracts.nested_get(
                proof, ["policy", "claims_require_evidence_refs"]
            )
            is True
        )
        and all(
            (
                isinstance(row, dict)
                and row.get("schema")
                == f"{config.schema_prefix}_self_awareness_e2e_lineage_row_v1"
                and (row.get("satisfied") is True)
                and (
                    self_awareness_contracts.nested_get(row, ["chain", "satisfied"])
                    is True
                )
                and (row.get("artifacts_ok") is True)
                and bool(row.get("evidence_refs"))
                and (
                    self_awareness_contracts.nested_get(
                        row, ["policy", "host_layer_mutates_stack"]
                    )
                    is False
                )
                and (
                    self_awareness_contracts.nested_get(
                        row, ["policy", "actions_executed"]
                    )
                    is False
                )
                for row in rows
            )
        )
    )


def top_level_lineage_packet(
    *,
    generated_at: str,
    source: str,
    run_id: str,
    chain: dict[str, Any],
    traceparent: str | None = None,
    cycle_id: str | None = None,
    artifacts: dict[str, Any] | None = None,
    steps: list[dict[str, Any]] | None = None,
    e2e_lineage_proof: dict[str, Any] | None = None,
    from_zero_proof: dict[str, Any] | None = None,
    investigation: dict[str, Any] | None = None,
    replay: dict[str, Any] | None = None,
    reactions: dict[str, Any] | None = None,
    responses: dict[str, Any] | None = None,
    export: dict[str, Any] | None = None,
    synthetic_events: list[dict[str, Any]] | None = None,
    config: SelfAwarenessLineageConfig,
    runtime_port: SelfAwarenessLineageRuntimePort,
) -> dict[str, Any]:

    def trace_parts(
        value: str | None,
    ) -> tuple[str | None, str | None]:
        if not value:
            return (None, None)
        parts = str(value).split("-")
        if len(parts) >= 4:
            return (parts[1], parts[2])
        return (None, None)

    def step_artifact_rows(
        step_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for index, step in enumerate(step_rows, start=1):
            if not isinstance(step, dict):
                continue
            artifact = (
                step.get("artifact") if isinstance(step.get("artifact"), dict) else {}
            )
            path = str(artifact.get("path") or "")
            rows.append(
                {
                    "order": index,
                    "name": step.get("id"),
                    "command": step.get("command"),
                    "path": path,
                    "schema": artifact.get("schema"),
                    "ok": step.get("ok"),
                    "artifact_ok": artifact.get("ok"),
                    "exists": artifact.get("exists"),
                    "sha256": artifact.get("sha256"),
                    "generated_at": artifact.get("generated_at"),
                    "machine_owned_path": path.startswith("/var/lib/abyss-machine/"),
                }
            )
        return rows

    def path_artifact_rows(
        path_rows: dict[str, Any],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for index, (name, raw_path) in enumerate(path_rows.items(), start=1):
            path = Path(str(raw_path))
            exists = runtime_port.path_exists(path)
            stat_result = runtime_port.path_stat(path) if exists else None
            rows.append(
                {
                    "order": index,
                    "name": str(name),
                    "path": str(path),
                    "exists": exists,
                    "size_bytes": stat_result.st_size if stat_result else None,
                    "sha256": runtime_port.sha256_path(path)
                    if exists and runtime_port.path_is_file(path)
                    else None,
                    "machine_owned_path": str(path).startswith(
                        "/var/lib/abyss-machine/"
                    ),
                }
            )
        return rows

    trace_id, span_id = trace_parts(traceparent)
    artifact_chain = step_artifact_rows(steps if isinstance(steps, list) else [])
    if not artifact_chain and isinstance(artifacts, dict):
        artifact_chain = path_artifact_rows(artifacts)
    chain_missing = [str(key) for key, value in chain.items() if not value]
    artifact_missing = [
        str(row.get("name"))
        for row in artifact_chain
        if not row.get("path")
        or row.get("exists") is not True
        or row.get("machine_owned_path") is not True
    ]
    e2e_ok = (
        isinstance(e2e_lineage_proof, dict)
        and e2e_lineage_proof.get("ok") is True
        and (
            self_awareness_contracts.nested_get(
                e2e_lineage_proof, ["summary", "missing_rows"]
            )
            == []
        )
    )
    from_zero_required = isinstance(from_zero_proof, dict)
    from_zero_ok = True if not from_zero_required else from_zero_proof.get("ok") is True
    replay_required = isinstance(replay, dict)
    replay_ok = True if not replay_required else replay.get("ok") is True
    export_required = isinstance(export, dict)
    export_ok = True if not export_required else export.get("ok") is True
    reaction_ids = [
        str(item.get("id"))
        for item in (
            reactions.get("candidates")
            if isinstance(reactions, dict)
            and isinstance(reactions.get("candidates"), list)
            else []
        )
        if isinstance(item, dict) and item.get("id")
    ]
    response_route_ids = [
        str(item.get("id"))
        for item in (
            responses.get("routes")
            if isinstance(responses, dict) and isinstance(responses.get("routes"), list)
            else []
        )
        if isinstance(item, dict) and item.get("id")
    ]
    synthetic_event_ids = [
        str(event.get("event_id"))
        for event in (synthetic_events if isinstance(synthetic_events, list) else [])
        if isinstance(event, dict) and event.get("event_id")
    ]
    evidence_refs = [
        {
            "path": row.get("path"),
            "sha256": row.get("sha256"),
            "lineage_artifact": row.get("name"),
        }
        for row in artifact_chain
        if row.get("path")
    ]
    complete = (
        not chain_missing
        and (not artifact_missing)
        and e2e_ok
        and from_zero_ok
        and replay_ok
        and export_ok
        and bool(run_id)
        and bool(evidence_refs)
    )
    return {
        "schema": f"{config.schema_prefix}_self_awareness_top_level_lineage_v1",
        "version": config.version,
        "generated_at": generated_at,
        "source": source,
        "complete": complete,
        "cycle_bound": bool(cycle_id),
        "cycle_id": cycle_id,
        "run_id": run_id,
        "trace": {
            "traceparent": traceparent,
            "trace_id": trace_id,
            "span_id": span_id,
            "synthetic_event_ids": synthetic_event_ids,
        },
        "thread": {
            "investigation_thread_id": investigation.get("thread_id")
            if isinstance(investigation, dict)
            else None,
            "replay_thread_id": replay.get("thread_id")
            if isinstance(replay, dict)
            else None,
        },
        "chain": {
            "passed": sum((1 for value in chain.values() if value)),
            "total": len(chain),
            "missing": chain_missing,
        },
        "proofs": {
            "e2e_lineage": e2e_lineage_proof.get("summary")
            if isinstance(e2e_lineage_proof, dict)
            else None,
            "from_zero": from_zero_proof.get("summary")
            if isinstance(from_zero_proof, dict)
            else None,
            "replay": replay.get("summary") if isinstance(replay, dict) else None,
            "export": export.get("summary") if isinstance(export, dict) else None,
        },
        "reaction_response": {
            "reaction_candidate_ids": reaction_ids,
            "response_route_ids": response_route_ids,
            "automatic_responses": self_awareness_contracts.nested_get(
                responses, ["summary", "automatic_responses"]
            )
            if isinstance(responses, dict)
            else None,
            "approval_required": self_awareness_contracts.nested_get(
                responses, ["summary", "approval_required"]
            )
            if isinstance(responses, dict)
            else None,
        },
        "artifact_chain": artifact_chain,
        "summary": {
            "complete": complete,
            "artifacts": len(artifact_chain),
            "artifact_missing": artifact_missing,
            "chain_missing": chain_missing,
            "e2e_lineage_ok": e2e_ok,
            "from_zero_ok": from_zero_ok,
            "replay_ok": replay_ok,
            "export_ok": export_ok,
            "synthetic_event_ids": len(synthetic_event_ids),
            "reaction_candidates": len(reaction_ids),
            "response_routes": len(response_route_ids),
        },
        "evidence_refs": evidence_refs,
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "executes_commands": False,
            "actions_executed": False,
            "automatic_remediation": False,
            "raw_secrets_included": False,
            "raw_evidence_is_not_truth": True,
            "claims_require_evidence_refs": True,
        },
    }


def top_level_lineage_complete(
    packet: Any, *, require_cycle: bool = False, config: SelfAwarenessLineageConfig
) -> bool:
    if not isinstance(packet, dict):
        return False
    return (
        packet.get("schema")
        == f"{config.schema_prefix}_self_awareness_top_level_lineage_v1"
        and packet.get("complete") is True
        and bool(packet.get("run_id"))
        and (not require_cycle or bool(packet.get("cycle_id")))
        and (not require_cycle or packet.get("cycle_bound") is True)
        and (
            self_awareness_contracts.nested_get(packet, ["summary", "chain_missing"])
            == []
        )
        and (
            self_awareness_contracts.nested_get(packet, ["summary", "artifact_missing"])
            == []
        )
        and (
            self_awareness_contracts.nested_get(packet, ["summary", "e2e_lineage_ok"])
            is True
        )
        and (
            self_awareness_contracts.nested_get(packet, ["summary", "replay_ok"])
            is True
        )
        and (
            self_awareness_contracts.nested_get(packet, ["summary", "export_ok"])
            is True
        )
        and bool(packet.get("evidence_refs"))
        and (
            self_awareness_contracts.nested_get(
                packet, ["policy", "host_layer_mutates_stack"]
            )
            is False
        )
        and (
            self_awareness_contracts.nested_get(
                packet, ["policy", "writes_project_roots"]
            )
            is False
        )
        and (
            self_awareness_contracts.nested_get(packet, ["policy", "executes_commands"])
            is False
        )
        and (
            self_awareness_contracts.nested_get(packet, ["policy", "actions_executed"])
            is False
        )
        and (
            self_awareness_contracts.nested_get(
                packet, ["policy", "automatic_remediation"]
            )
            is False
        )
        and (
            self_awareness_contracts.nested_get(
                packet, ["policy", "claims_require_evidence_refs"]
            )
            is True
        )
    )

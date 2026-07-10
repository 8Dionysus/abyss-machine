from __future__ import annotations

import collections
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from . import self_awareness_contracts


DocumentPort = Callable[..., Any]


@dataclass(frozen=True)
class SelfAwarenessFailureMatrixPaths:
    capabilities_latest: Path
    requirements_latest: Path
    requirement_probes_latest: Path
    stack_observability_latest: Path
    collect_latest: Path
    rag_validate_latest: Path
    llm_resident_status_latest: Path
    nervous_brief_latest: Path
    nervous_semantic_maintain_latest: Path
    typing_validate_latest: Path
    context_latest: Path
    validate_latest: Path
    failure_matrix_latest: Path
    failure_matrix_root: Path


@dataclass(frozen=True)
class SelfAwarenessFailureMatrixConfig:
    schema_prefix: str
    version: str
    unbounded_labels: Sequence[str]
    semantic_maintain_review_command: str
    semantic_maintain_retry_command: str


@dataclass(frozen=True)
class SelfAwarenessFailureMatrixRuntimePort:
    load_latest_json: DocumentPort
    now_iso: DocumentPort
    write_latest_and_history: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessFailureMatrixRefreshPort:
    capabilities: DocumentPort


def failure_matrix(
    write_latest: bool = True,
    *,
    paths: SelfAwarenessFailureMatrixPaths,
    config: SelfAwarenessFailureMatrixConfig,
    runtime_port: SelfAwarenessFailureMatrixRuntimePort,
    refresh_port: SelfAwarenessFailureMatrixRefreshPort,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    VERSION = config.version
    SELF_AWARENESS_CAPABILITIES_LATEST_PATH = paths.capabilities_latest
    SELF_AWARENESS_REQUIREMENTS_LATEST_PATH = paths.requirements_latest
    SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH = paths.requirement_probes_latest
    STACK_OBSERVABILITY_LATEST_PATH = paths.stack_observability_latest
    SELF_AWARENESS_COLLECT_LATEST_PATH = paths.collect_latest
    RAG_VALIDATE_LATEST_PATH = paths.rag_validate_latest
    AI_LLM_RESIDENT_STATUS_LATEST_PATH = paths.llm_resident_status_latest
    NERVOUS_BRIEF_LATEST_PATH = paths.nervous_brief_latest
    NERVOUS_SEMANTIC_MAINTAIN_LATEST_PATH = paths.nervous_semantic_maintain_latest
    TYPING_VALIDATE_LATEST_PATH = paths.typing_validate_latest
    SELF_AWARENESS_CONTEXT_LATEST_PATH = paths.context_latest
    SELF_AWARENESS_VALIDATE_LATEST_PATH = paths.validate_latest
    SELF_AWARENESS_FAILURE_MATRIX_LATEST_PATH = paths.failure_matrix_latest
    SELF_AWARENESS_FAILURE_MATRIX_ROOT = paths.failure_matrix_root
    SELF_AWARENESS_UNBOUNDED_LABELS = config.unbounded_labels
    NERVOUS_SEMANTIC_MAINTAIN_REVIEW_COMMAND = config.semantic_maintain_review_command
    NERVOUS_SEMANTIC_MAINTAIN_RETRY_COMMAND = config.semantic_maintain_retry_command
    load_latest_json = runtime_port.load_latest_json
    now_iso = runtime_port.now_iso
    write_latest_and_history = runtime_port.write_latest_and_history
    nested_get = self_awareness_contracts.nested_get
    self_awareness_capabilities = refresh_port.capabilities
    generated_at = now_iso()
    capabilities = load_latest_json(SELF_AWARENESS_CAPABILITIES_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_capabilities_v1")
    if not capabilities.get("schema"):
        capabilities = self_awareness_capabilities(write_latest=True)
    requirements = load_latest_json(SELF_AWARENESS_REQUIREMENTS_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_requirements_v1")
    requirement_probes = load_latest_json(SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_requirement_probes_v1")
    stack = load_latest_json(STACK_OBSERVABILITY_LATEST_PATH, f"{SCHEMA_PREFIX}_stack_observability_v1")
    collect = load_latest_json(SELF_AWARENESS_COLLECT_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_collect_v1")
    rag_validation = load_latest_json(RAG_VALIDATE_LATEST_PATH, f"{SCHEMA_PREFIX}_rag_validate_v1")
    llm_resident_status = load_latest_json(AI_LLM_RESIDENT_STATUS_LATEST_PATH, f"{SCHEMA_PREFIX}_gemma4_spark_resident_status_v1")
    nervous = load_latest_json(NERVOUS_BRIEF_LATEST_PATH, f"{SCHEMA_PREFIX}_nervous_brief_v1")
    semantic_maintain = load_latest_json(NERVOUS_SEMANTIC_MAINTAIN_LATEST_PATH, f"{SCHEMA_PREFIX}_nervous_semantic_maintain_v1")
    typing_validation = load_latest_json(TYPING_VALIDATE_LATEST_PATH, f"{SCHEMA_PREFIX}_typing_validate_v1")
    rows: list[dict[str, Any]] = []

    def evidence_ref(path: Path, schema: str | None = None, **extra: Any) -> dict[str, Any]:
        item = {"path": str(path)}
        if schema:
            item["schema"] = schema
        item.update(extra)
        return item

    def add_row(
        row_id: str,
        title: str,
        *,
        owner: str,
        failure_kind: str,
        detector: dict[str, Any],
        expected_behavior: list[str],
        covered_by: list[str],
        evidence_refs: list[dict[str, Any]],
        current_state: dict[str, Any] | None = None,
        severity: str = "guard",
    ) -> None:
        rows.append({
            "id": row_id,
            "title": title,
            "owner": owner,
            "severity": severity,
            "failure_kind": failure_kind,
            "detector": detector,
            "expected_machine_behavior": expected_behavior,
            "covered_by": covered_by,
            "current_state": current_state or {},
            "evidence_refs": evidence_refs,
            "machine_action": "record_route_validate_only",
            "host_layer_mutates_stack": False,
            "automatic_remediation": False,
            "owner_route_required_before_mutation": owner == "abyss-stack",
        })

    requirement_items = requirements.get("requirements") if isinstance(requirements.get("requirements"), list) else []
    probe_items = requirement_probes.get("probes") if isinstance(requirement_probes.get("probes"), list) else []
    probe_by_id = {
        str(probe.get("requirement_id") or probe.get("id")): probe
        for probe in probe_items
        if isinstance(probe, dict) and (probe.get("requirement_id") or probe.get("id"))
    }
    requirement_by_id = {
        str(requirement.get("id") or requirement.get("requirement_id")): requirement
        for requirement in requirement_items
        if isinstance(requirement, dict) and (requirement.get("id") or requirement.get("requirement_id"))
    }
    known_stack_requirement_ids = {
        "stack.trace-backend",
        "stack.grafana.datasource-read",
        "stack.database-graph.read-route",
        "stack.langchain-api.graph-observability",
    }

    def add_requirement_row(requirement_id: str, requirement: dict[str, Any] | None = None) -> None:
        requirement = requirement if isinstance(requirement, dict) else {}
        probe = probe_by_id.get(requirement_id, {})
        requirement_present = bool(requirement)
        probe_status = str(probe.get("status") or "") if isinstance(probe, dict) else ""
        closed_by_probe = isinstance(probe, dict) and (probe.get("closed_by_current_probe") is True or probe_status == "closed")
        row_status = str(requirement.get("status") or ("closed" if closed_by_probe else "not_current_requirement"))
        closed = row_status == "closed" or closed_by_probe
        failure_kind = "open_requirement" if requirement_present and not closed else "closed_requirement_regression_guard"
        if failure_kind == "open_requirement":
            expected_behavior = [
                "keep the gap visible in requirements/latest.json",
                "do not mark the stack capability as host-owned",
                "do not write stack runtime/config from abyss-machine",
            ]
            severity = str(requirement.get("severity") or "gap")
        else:
            expected_behavior = [
                "preserve the regression guard for this stack-owned requirement",
                "re-open the owner-routed requirement if bounded evidence disappears or fails redaction",
                "do not write stack runtime/config from abyss-machine",
            ]
            severity = "watch"
        evidence_refs = list(requirement.get("evidence_refs") if isinstance(requirement.get("evidence_refs"), list) else [])
        evidence_refs.extend([
            evidence_ref(SELF_AWARENESS_REQUIREMENTS_LATEST_PATH, requirements.get("schema"), requirement_id=requirement_id),
            evidence_ref(SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH, requirement_probes.get("schema"), requirement_id=requirement_id),
        ])
        add_row(
            "requirement:" + requirement_id,
            str(requirement.get("title") or requirement_id),
            owner=str(requirement.get("owner") or nested_get(probe, ["owner"]) or "abyss-stack"),
            failure_kind=failure_kind,
            detector={
                "source": "self-awareness capabilities",
                "command": "abyss-machine self-awareness capabilities --json",
                "detection": requirement.get("detection"),
            },
            expected_behavior=expected_behavior,
            covered_by=[
                "abyss-machine self-awareness validate --json:capability_map_and_requirements",
                "abyss-machine stack-bridge validate --json:self_awareness_artifacts",
                "abyss-machine self-awareness requirement-probes --json",
            ],
            evidence_refs=evidence_refs,
            current_state={
                "status": row_status,
                "severity": requirement.get("severity"),
                "requirement_present": requirement_present,
                "probe_present": bool(probe),
                "probe_status": probe_status or None,
                "closed_by_current_probe": closed_by_probe,
                "not_current_requirement_is_not_open": not requirement_present,
            },
            severity=severity,
        )

    for requirement_id, requirement in requirement_by_id.items():
        add_requirement_row(requirement_id, requirement)
    for requirement_id in sorted(known_stack_requirement_ids - set(requirement_by_id)):
        add_requirement_row(requirement_id)

    jobs_up = set(str(item) for item in (nested_get(stack, ["summary", "promql_jobs_up"]) or []))
    add_row(
        "stack.prometheus-or-promql-missing",
        "Prometheus/PromQL target discovery missing or stale",
        owner="abyss-stack",
        failure_kind="missing_or_stale_observability",
        detector={"command": "abyss-machine stack-bridge observability --json", "signals": ["prometheus.targets", "promql up{}"]},
        expected_behavior=["mark stack observability degraded", "keep machine read-only", "route stack repair through abyss-stack"],
        covered_by=["abyss-machine stack-bridge validate --json", "abyss-machine self-awareness validate --json:full_stack_capability_planes"],
        evidence_refs=[evidence_ref(STACK_OBSERVABILITY_LATEST_PATH, stack.get("schema"))],
        current_state={"jobs_up": sorted(jobs_up), "ok": stack.get("ok")},
    )
    add_row(
        "stack.loki-logql-missing-or-cardinality-risk",
        "Loki/LogQL missing or unsafe high-cardinality labels detected",
        owner="abyss-stack",
        failure_kind="missing_or_cardinality_risk",
        detector={"command": "abyss-machine self-awareness context --json", "forbidden_labels": sorted(SELF_AWARENESS_UNBOUNDED_LABELS)},
        expected_behavior=["reject trace/request/session/task IDs as Loki labels", "keep IDs in event context/body", "fail validation on unsafe labels"],
        covered_by=["abyss-machine self-awareness validate --json:no_unbounded_loki_labels", "abyss-machine self-awareness validate --json:fixture_unbounded_label_rejected"],
        evidence_refs=[evidence_ref(SELF_AWARENESS_CONTEXT_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_context_v1")],
        current_state={"forbidden_loki_labels": nested_get(load_latest_json(SELF_AWARENESS_CONTEXT_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_context_v1"), ["summary", "forbidden_loki_labels"])},
    )
    add_row(
        "stack.grafana-health-or-auth-gap",
        "Grafana health or datasource inventory unavailable",
        owner="abyss-stack",
        failure_kind="missing_or_auth_gap",
        detector={"command": "abyss-machine self-awareness capabilities --json", "endpoint": "/api/health and /api/datasources"},
        expected_behavior=["use unauthenticated health as limited evidence", "record datasource auth gap as stack-owned requirement", "do not store Grafana credentials in abyss-machine"],
        covered_by=["abyss-machine self-awareness validate --json:capability_map_and_requirements"],
        evidence_refs=[evidence_ref(SELF_AWARENESS_CAPABILITIES_LATEST_PATH, capabilities.get("schema"))],
        current_state=nested_get(capabilities, ["raw", "grafana_datasources"]) or {},
    )
    add_row(
        "stack.alloy-otel-pipeline-missing",
        "Alloy/OTel log and metric pipeline missing",
        owner="abyss-stack",
        failure_kind="missing_pipeline",
        detector={"command": "abyss-machine stack-bridge observability --json", "signals": ["up{job=\"alloy\"}", "loki labels/log samples"]},
        expected_behavior=["mark observability source degraded", "do not edit Alloy config", "route pipeline repair to abyss-stack"],
        covered_by=["abyss-machine stack-bridge validate --json", "abyss-machine self-awareness validate --json:full_stack_observation_sources"],
        evidence_refs=[evidence_ref(STACK_OBSERVABILITY_LATEST_PATH, stack.get("schema"), locator="alloy")],
        current_state={"alloy_seen": "alloy" in jobs_up, "collect_degraded_sources": nested_get(collect, ["summary", "degraded_sources"])},
    )
    add_row(
        "stack.alertmanager-lifecycle-unavailable",
        "Alertmanager lifecycle unavailable",
        owner="abyss-stack",
        failure_kind="optional_lifecycle_unavailable",
        detector={"command": "abyss-machine self-awareness collect --json", "endpoint": "/api/v2/status and /api/v2/alerts"},
        expected_behavior=["keep Prometheus ALERTS and synthetic alerts usable", "record optional degradation when unavailable", "do not mutate alert rules"],
        covered_by=["abyss-machine self-awareness collect --json", "abyss-machine self-awareness alerts --json"],
        evidence_refs=[evidence_ref(SELF_AWARENESS_COLLECT_LATEST_PATH, collect.get("schema"))],
        current_state={"alert_events": nested_get(collect, ["summary", "alert_events"])},
    )
    add_row(
        "machine.rag-validation-missing-or-stale",
        "RAG trace/eval validation missing or stale",
        owner="abyss-machine",
        failure_kind="validation_gate",
        detector={"command": "abyss-machine rag validate --json", "latest": str(RAG_VALIDATE_LATEST_PATH)},
        expected_behavior=["block treating retrieval as proof", "surface raw evidence refs only", "refresh RAG before deep reasoning"],
        covered_by=["abyss-machine rag validate --json", "abyss-machine self-awareness validate --json:full_stack_observation_sources"],
        evidence_refs=[evidence_ref(RAG_VALIDATE_LATEST_PATH, rag_validation.get("schema"))],
        current_state={"ok": rag_validation.get("ok"), "summary": rag_validation.get("summary")},
    )
    add_row(
        "machine.warm-e2b-resident-unavailable",
        "warm-E2B/gemma4 resident worker unavailable",
        owner="abyss-machine",
        failure_kind="resident_worker_unavailable",
        detector={"command": "abyss-machine ai llm resident status --json", "latest": str(AI_LLM_RESIDENT_STATUS_LATEST_PATH)},
        expected_behavior=["keep deterministic investigation/replay available", "do not claim model-backed synthesis", "escalate only through resource/mode gates"],
        covered_by=["abyss-machine ai validate --json", "abyss-machine self-awareness probe --json:warm_e2b"],
        evidence_refs=[evidence_ref(AI_LLM_RESIDENT_STATUS_LATEST_PATH, llm_resident_status.get("schema"))],
        current_state={"status": llm_resident_status.get("status"), "ok": llm_resident_status.get("ok")},
    )
    add_row(
        "machine.nervous-semantic-stale",
        "Nervous semantic sidecar stale before reasoning",
        owner="abyss-machine",
        failure_kind="freshness_gate",
        detector={
            "command": "abyss-machine nervous brief --scope now --json",
            "maintenance_review": NERVOUS_SEMANTIC_MAINTAIN_REVIEW_COMMAND,
            "maintenance_retry": NERVOUS_SEMANTIC_MAINTAIN_RETRY_COMMAND,
        },
        expected_behavior=["surface semantic_maintenance_needed", "keep raw/session evidence separate from truth", "run maintainer only through resource gates"],
        covered_by=["abyss-machine nervous validate --json", "abyss-machine self-awareness capabilities --json:nervous.freshness-gate"],
        evidence_refs=[evidence_ref(NERVOUS_BRIEF_LATEST_PATH, nervous.get("schema")), evidence_ref(NERVOUS_SEMANTIC_MAINTAIN_LATEST_PATH, semantic_maintain.get("schema"))],
        current_state={
            "readiness": nervous.get("readiness"),
            "semantic_maintain_decision": semantic_maintain.get("decision"),
            "blocked_reasons": nested_get(semantic_maintain, ["launch", "blocked_reasons"]),
        },
    )
    add_row(
        "machine.resource-denial",
        "Resource or game guard denies indexing/model escalation",
        owner="abyss-machine",
        failure_kind="resource_denial",
        detector={"command": "abyss-machine resource plan --class medium --kind indexing --unattended --json"},
        expected_behavior=["treat denial as safe gate, not validation failure", "record blocked_reasons", "do not override without explicit operator route"],
        covered_by=["abyss-machine resource validate --json", NERVOUS_SEMANTIC_MAINTAIN_REVIEW_COMMAND],
        evidence_refs=[evidence_ref(NERVOUS_SEMANTIC_MAINTAIN_LATEST_PATH, semantic_maintain.get("schema"))],
        current_state={"decision": semantic_maintain.get("decision"), "reason": semantic_maintain.get("reason")},
    )
    add_row(
        "machine.secret-redaction",
        "Secret-like content in events, queries, or briefs",
        owner="abyss-machine",
        failure_kind="redaction_risk",
        detector={"command": "abyss-machine self-awareness validate --json", "regex": "SELF_AWARENESS_SECRET_RE"},
        expected_behavior=["redact previews", "store hashes/previews only", "fail validation if secret-like preview remains"],
        covered_by=["abyss-machine self-awareness validate --json:no_secret_leakage", "abyss-machine self-awareness validate --json:fixture_redaction"],
        evidence_refs=[evidence_ref(SELF_AWARENESS_VALIDATE_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_validate_v1")],
        current_state={"typing_validate": typing_validation.get("summary")},
    )
    add_row(
        "stack.downtime-bounded-readonly",
        "Stack service downtime during read-only collection",
        owner="abyss-stack",
        failure_kind="downtime",
        detector={"command": "abyss-machine self-awareness collect --json", "sources": ["prometheus", "loki", "grafana", "alloy", "containers"]},
        expected_behavior=["mark degraded_sources", "preserve latest evidence refs", "do not start/stop/reload stack services"],
        covered_by=["abyss-machine stack-bridge observability --json", "abyss-machine self-awareness collect --json"],
        evidence_refs=[evidence_ref(SELF_AWARENESS_COLLECT_LATEST_PATH, collect.get("schema"))],
        current_state={"degraded_sources": nested_get(collect, ["summary", "degraded_sources"]), "status": collect.get("status")},
    )
    base_required_rows = {
        "stack.prometheus-or-promql-missing",
        "stack.loki-logql-missing-or-cardinality-risk",
        "stack.grafana-health-or-auth-gap",
        "stack.alloy-otel-pipeline-missing",
        "stack.alertmanager-lifecycle-unavailable",
        "machine.rag-validation-missing-or-stale",
        "machine.warm-e2b-resident-unavailable",
        "machine.nervous-semantic-stale",
        "machine.resource-denial",
        "machine.secret-redaction",
        "stack.downtime-bounded-readonly",
    }
    required_rows = base_required_rows | {
        "requirement:" + requirement_id
        for requirement_id in sorted(known_stack_requirement_ids | set(requirement_by_id))
    }
    present_rows = {str(row.get("id")) for row in rows}
    malformed = [
        row.get("id") for row in rows
        if not row.get("id")
        or not row.get("owner")
        or not row.get("failure_kind")
        or not row.get("detector")
        or not row.get("expected_machine_behavior")
        or row.get("host_layer_mutates_stack") is not False
        or row.get("automatic_remediation") is not False
        or not row.get("evidence_refs")
    ]
    missing_required = sorted(required_rows - present_rows)
    by_owner = dict(collections.Counter(str(row.get("owner") or "unknown") for row in rows))
    by_failure_kind = dict(collections.Counter(str(row.get("failure_kind") or "unknown") for row in rows))
    data = {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_failure_matrix_v1",
        "version": VERSION,
        "generated_at": generated_at,
        "ok": not malformed and not missing_required,
        "status": "covered" if not malformed and not missing_required else "incomplete",
        "summary": {
            "failure_modes": len(rows),
            "requirements_rows": sum(1 for row in rows if str(row.get("id")).startswith("requirement:")),
            "by_owner": by_owner,
            "by_failure_kind": by_failure_kind,
            "missing_required": missing_required,
            "malformed": malformed,
        },
        "rows": rows,
        "required_rows": sorted(required_rows),
        "policy": {
            "host_layer_mutates_stack": False,
            "automatic_remediation": False,
            "owner_route_required_before_mutation": True,
            "resource_denial_is_safe_gate": True,
            "freshness_precedes_reasoning": True,
        },
        "evidence_refs": [
            evidence_ref(SELF_AWARENESS_CAPABILITIES_LATEST_PATH, capabilities.get("schema")),
            evidence_ref(SELF_AWARENESS_REQUIREMENTS_LATEST_PATH, requirements.get("schema")),
            evidence_ref(SELF_AWARENESS_VALIDATE_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_validate_v1"),
        ],
    }
    if write_latest:
        errors = write_latest_and_history(data, SELF_AWARENESS_FAILURE_MATRIX_LATEST_PATH, SELF_AWARENESS_FAILURE_MATRIX_ROOT)
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data

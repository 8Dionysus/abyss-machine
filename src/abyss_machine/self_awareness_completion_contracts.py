from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from . import self_awareness_contracts


@dataclass(frozen=True)
class CompletionAuditPaths:
    completion_audit: Path
    coverage_audit: Path
    autolink: Path
    validate: Path
    cycle: Path
    requirement_probes: Path
    stack_closure_dossier: Path
    working_stack: Path
    activation_smoke: Path


@dataclass(frozen=True)
class CompletionAuditReadiness:
    artifact_refs: Mapping[str, dict[str, Any]]
    missing_artifacts: list[str]
    validation_summary: Mapping[str, Any]
    validate_green: bool
    cycle: Mapping[str, Any]
    cycle_green: bool
    coverage_audit: Mapping[str, Any]
    coverage_summary: Mapping[str, Any]
    coverage_green: bool
    coverage_incomplete: int
    open_requirement_rows: list[dict[str, Any]]
    status_open_stack_requirements: int
    requirement_probes_open: int
    coverage_blocked_stack_owned: int
    open_potential_rows: list[dict[str, Any]]
    working_stack_usage_gaps: int
    activation_open_gaps: int
    autolink_summary: Mapping[str, Any]
    autolink_complete: bool
    resource_preflight: Mapping[str, Any]
    owner_boundary_ok: bool


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _count_pair_complete(summary: Mapping[str, Any], total_key: str, complete_key: str) -> bool:
    total = summary.get(total_key)
    complete = summary.get(complete_key)
    if total is None or complete is None:
        return False
    return _safe_int(total, -1) == _safe_int(complete, -2)


def completion_autolink_ready(autolink: Mapping[str, Any]) -> bool:
    summary = autolink.get("summary") if isinstance(autolink.get("summary"), Mapping) else {}
    return (
        bool(autolink.get("ok"))
        and _count_pair_complete(summary, "organ_links", "organ_links_complete")
        and _count_pair_complete(summary, "stack_requirement_links", "stack_requirement_links_complete")
        and _count_pair_complete(summary, "synthetic_scenarios", "synthetic_scenarios_complete")
        and bool(autolink.get("state_digest"))
    )


def completion_owner_boundary_readonly(
    open_requirement_doc: Mapping[str, Any],
    open_potential_doc: Mapping[str, Any],
    coverage_audit: Mapping[str, Any],
) -> bool:
    return (
        self_awareness_contracts.nested_get(open_requirement_doc, ["policy", "host_layer_mutates_stack"]) is False
        and self_awareness_contracts.nested_get(open_potential_doc, ["policy", "host_layer_mutates_stack"]) is False
        and self_awareness_contracts.nested_get(coverage_audit, ["policy", "host_layer_mutates_stack"]) is False
    )


def completion_gate(
    schema_prefix: str,
    gate_id: str,
    ok: bool,
    title: str,
    evidence_refs: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_self_awareness_completion_gate_v1",
        "id": gate_id,
        "ok": bool(ok),
        "title": title,
        "evidence_refs": evidence_refs,
    }


def completion_gates(
    *,
    schema_prefix: str,
    readiness: CompletionAuditReadiness,
    paths: CompletionAuditPaths,
) -> list[dict[str, Any]]:
    return [
        completion_gate(
            schema_prefix,
            "latest_artifacts_available",
            not readiness.missing_artifacts,
            "all required latest readmodels exist with expected schemas and digests",
            list(readiness.artifact_refs.values()),
        ),
        completion_gate(
            schema_prefix,
            "validator_green",
            readiness.validate_green,
            "self-awareness validate has no failures",
            [{"path": str(paths.validate), "summary": dict(readiness.validation_summary)}],
        ),
        completion_gate(
            schema_prefix,
            "cycle_green",
            readiness.cycle_green,
            "latest e2e cycle is present and not resource-denied",
            [{"path": str(paths.cycle), "status": readiness.cycle.get("status"), "summary": readiness.cycle.get("summary")}],
        ),
        completion_gate(
            schema_prefix,
            "coverage_green",
            readiness.coverage_green,
            "objective coverage has no incomplete rows",
            [{"path": str(paths.coverage_audit), "summary": dict(readiness.coverage_summary)}],
        ),
        completion_gate(
            schema_prefix,
            "no_open_stack_requirements",
            (
                not readiness.open_requirement_rows
                and readiness.status_open_stack_requirements == 0
                and readiness.requirement_probes_open == 0
                and readiness.coverage_blocked_stack_owned == 0
            ),
            "no abyss-stack-owned requirement blockers remain open",
            [
                {"path": str(paths.requirement_probes)},
                {"path": str(paths.stack_closure_dossier)},
                {"path": str(paths.coverage_audit)},
            ],
        ),
        completion_gate(
            schema_prefix,
            "no_working_stack_usage_gaps",
            (
                not readiness.open_potential_rows
                and readiness.working_stack_usage_gaps == 0
                and readiness.activation_open_gaps == 0
            ),
            "all working stack organs are linked into machine usage or deliberately closed by evidence",
            [{"path": str(paths.working_stack)}, {"path": str(paths.activation_smoke)}],
        ),
        completion_gate(
            schema_prefix,
            "automatic_time_space_context_links_complete",
            readiness.autolink_complete,
            "automatic temporal, spatial, and contextual links are complete",
            [{"path": str(paths.autolink), "summary": dict(readiness.autolink_summary)}],
        ),
        completion_gate(
            schema_prefix,
            "resource_guard_safe",
            bool(readiness.resource_preflight.get("ok")),
            "the machine has enough free memory, swap, and load headroom for the next proof step",
            [{"source": "/proc/meminfo"}, {"source": "os.getloadavg"}],
        ),
        completion_gate(
            schema_prefix,
            "owner_boundary_readonly",
            readiness.owner_boundary_ok,
            "host layer remains a read-only stack consumer with no automatic remediation",
            [{"path": str(paths.coverage_audit)}, {"path": str(paths.autolink)}],
        ),
    ]


def completion_blocker(
    schema_prefix: str,
    blocker_id: str,
    category: str,
    title: str,
    *,
    count: int = 0,
    items: list[Any] | None = None,
    evidence_refs: list[dict[str, Any]] | None = None,
    owner_route: str = "abyss-machine",
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_self_awareness_completion_blocker_v1",
        "id": blocker_id,
        "category": category,
        "title": title,
        "owner_route": owner_route,
        "count": count,
        "items": items or [],
        "evidence_refs": evidence_refs or [],
        "policy": {
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "automatic_remediation": False,
        },
    }


def completion_blockers(
    *,
    schema_prefix: str,
    readiness: CompletionAuditReadiness,
    paths: CompletionAuditPaths,
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []

    def add(*args: Any, **kwargs: Any) -> None:
        blockers.append(completion_blocker(schema_prefix, *args, **kwargs))

    if readiness.missing_artifacts:
        add(
            "self-awareness.latest-artifacts.missing",
            "artifact",
            "required self-awareness latest artifacts are missing or malformed",
            count=len(readiness.missing_artifacts),
            items=readiness.missing_artifacts,
            evidence_refs=list(readiness.artifact_refs.values()),
        )
    if not readiness.validate_green:
        add(
            "self-awareness.validate.not-green",
            "validator",
            "latest self-awareness validate is not green",
            evidence_refs=[{"path": str(paths.validate), "summary": dict(readiness.validation_summary)}],
        )
    if not readiness.cycle_green:
        add(
            "self-awareness.cycle.not-green",
            "e2e",
            "latest self-awareness cycle is not green or was resource-denied",
            evidence_refs=[
                {"path": str(paths.cycle), "status": readiness.cycle.get("status"), "summary": readiness.cycle.get("summary")}
            ],
        )
    if readiness.coverage_incomplete:
        incomplete_rows = readiness.coverage_audit.get("incomplete_rows")
        add(
            "self-awareness.coverage.incomplete",
            "coverage",
            "objective coverage has incomplete rows",
            count=readiness.coverage_incomplete,
            items=incomplete_rows if isinstance(incomplete_rows, list) else [],
            evidence_refs=[{"path": str(paths.coverage_audit), "summary": dict(readiness.coverage_summary)}],
        )
    if (
        readiness.open_requirement_rows
        or readiness.status_open_stack_requirements
        or readiness.requirement_probes_open
        or readiness.coverage_blocked_stack_owned
    ):
        add(
            "abyss-stack.requirements.open",
            "stack_requirement",
            "abyss-stack-owned requirements still block full self-awareness coverage",
            count=max(
                len(readiness.open_requirement_rows),
                readiness.status_open_stack_requirements,
                readiness.requirement_probes_open,
                readiness.coverage_blocked_stack_owned,
            ),
            items=readiness.open_requirement_rows,
            evidence_refs=[
                {"path": str(paths.requirement_probes)},
                {"path": str(paths.stack_closure_dossier)},
                {"path": str(paths.coverage_audit)},
            ],
            owner_route="abyss-stack",
        )
    if readiness.open_potential_rows or readiness.working_stack_usage_gaps or readiness.activation_open_gaps:
        add(
            "abyss-stack.working-potential.open",
            "working_stack_usage_gap",
            "working stack services are present but not fully used by abyss-machine",
            count=max(
                len(readiness.open_potential_rows),
                readiness.working_stack_usage_gaps,
                readiness.activation_open_gaps,
            ),
            items=readiness.open_potential_rows,
            evidence_refs=[
                {"path": str(paths.working_stack)},
                {"path": str(paths.activation_smoke)},
                {"path": str(paths.autolink)},
            ],
            owner_route="abyss-stack",
        )
    if not readiness.autolink_complete:
        add(
            "self-awareness.autolink.incomplete",
            "autolink",
            "automatic temporal, spatial, and contextual link state is not complete",
            evidence_refs=[{"path": str(paths.autolink), "summary": dict(readiness.autolink_summary)}],
        )
    if not readiness.resource_preflight.get("ok"):
        add(
            "self-awareness.resource-guard.not-safe",
            "resource",
            "resource preflight denies further live proof work",
            evidence_refs=[{"source": "/proc/meminfo"}, {"source": "os.getloadavg"}],
        )
    if not readiness.owner_boundary_ok:
        add(
            "self-awareness.owner-boundary.not-readonly",
            "owner_boundary",
            "one or more completion sources claim stack mutation or automatic remediation",
            evidence_refs=[{"path": str(paths.coverage_audit)}, {"path": str(paths.autolink)}],
        )
    return blockers


def stack_requirement_priority(row: Mapping[str, Any]) -> tuple[int, str, list[str]]:
    requirement_id = str(row.get("requirement_id") or row.get("id") or "")
    blockers = row.get("blocking_check_keys") if isinstance(row.get("blocking_check_keys"), list) else []
    score = 50 + (len(blockers) * 8)
    priority_class = "stack_handoff"
    reasons = ["open_stack_owned_requirement"]
    if requirement_id == "stack.trace-backend":
        score += 50
        priority_class = "critical_trace_join"
        reasons.append("unlocks_span_log_metric_join_and_langgraph_trace_coupling")
    elif requirement_id == "stack.langchain-api.graph-observability":
        score += 42
        priority_class = "critical_langgraph_checkpoint_inventory"
        reasons.append("unlocks_thread_checkpoint_trace_replay_inventory")
    elif requirement_id == "stack.database-graph.read-route":
        score += 34
        priority_class = "critical_memory_space_inventory"
        reasons.append("unlocks_postgres_neo4j_spatial_memory_inventory")
    elif requirement_id == "stack.grafana.datasource-read":
        score += 24
        priority_class = "dashboard_source_inventory"
        reasons.append("unlocks_authoritative_dashboard_datasource_identity")
    if "langchain_trace_backend_coupled" in {str(item) for item in blockers}:
        score += 10
        reasons.append("depends_on_trace_backend_coupling")
    return score, priority_class, reasons


def working_stack_priority(row: Mapping[str, Any]) -> tuple[int, str, list[str]]:
    service = str(row.get("service") or "")
    classification = str(row.get("activation_gap_classification") or "")
    blocker_keys = row.get("closure_blocker_keys") if isinstance(row.get("closure_blocker_keys"), list) else []
    missing_checks = row.get("missing_checks") if isinstance(row.get("missing_checks"), list) else []
    score = 36 + (len(blocker_keys) * 4) + (len(missing_checks) * 2)
    priority_class = "working_stack_activation"
    reasons = ["open_working_stack_usage_gap"]
    if classification == "running_functional_smoke_failed":
        score += 42
        priority_class = "functional_smoke_failed_runtime"
        reasons.append("runtime_present_but_functional_smoke_failed")
    elif classification == "exited_stack_managed_container":
        score += 32
        priority_class = "exited_stack_managed_runtime"
        reasons.append("stack_managed_container_exited")
    elif classification == "declared_without_running_runtime":
        score += 20
        priority_class = "declared_runtime_not_running"
        reasons.append("declared_service_not_running")
    service_classes = {
        "aoa-browser": ("browser_tool_runtime", 16, "browser_tool_is_direct_agent_body_surface"),
        "langchain-api-llamacpp": ("llm_route_activation", 14, "langchain_llamacpp_route_part_of_reasoning_body"),
        "litellm": ("llm_route_activation", 12, "litellm_route_part_of_model_gateway_body"),
        "ollama": ("llm_route_activation", 12, "ollama_route_part_of_model_gateway_body"),
        "tts-router": ("voice_runtime_activation", 10, "tts_router_part_of_voice_body"),
        "qwen-tts": ("voice_runtime_activation", 10, "qwen_tts_part_of_voice_body"),
        "babelvox-tts": ("voice_runtime_activation", 8, "babelvox_tts_part_of_voice_body"),
        "tos-graph": ("graph_runtime_activation", 8, "tree_of_sophia_graph_runtime_surface"),
        "n8n": ("workflow_runtime_activation", 6, "workflow_runtime_surface"),
        "n8n-task-runners": ("workflow_runtime_activation", 6, "workflow_task_runner_surface"),
    }
    if service in service_classes:
        priority_class, delta, reason = service_classes[service]
        score += delta
        reasons.append(reason)
    return score, priority_class, reasons


def completion_actions(
    *,
    schema_prefix: str,
    open_requirement_rows: list[dict[str, Any]],
    open_potential_rows: list[dict[str, Any]],
    resource_guard_ok: bool,
    paths: CompletionAuditPaths,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for row in open_requirement_rows:
        if not isinstance(row, dict):
            continue
        requirement_id = str(row.get("requirement_id") or row.get("id") or "unknown")
        score, priority_class, priority_reasons = stack_requirement_priority(row)
        safe_next = row.get("safe_next_action") if isinstance(row.get("safe_next_action"), dict) else {}
        actions.append({
            "schema": f"{schema_prefix}_self_awareness_completion_action_v1",
            "id": f"stack-requirement:{requirement_id}",
            "category": "stack_requirement",
            "owner_route": row.get("owner") or "abyss-stack",
            "requirement_id": requirement_id,
            "title": row.get("title"),
            "priority_score": score,
            "priority_class": priority_class,
            "priority_reasons": priority_reasons,
            "closure_blocker_keys": row.get("blocking_check_keys") if isinstance(row.get("blocking_check_keys"), list) else [],
            "missing_checks": row.get("missing_checks") if isinstance(row.get("missing_checks"), list) else [],
            "coverage_planes": row.get("coverage_planes") if isinstance(row.get("coverage_planes"), list) else [],
            "verifier_commands": row.get("verifier_commands") if isinstance(row.get("verifier_commands"), list) else [],
            "safe_next_action": safe_next,
            "resource_gate": {
                "current_audit_resource_guard_ok": resource_guard_ok,
                "completion_audit_runs_probe": False,
                "completion_audit_runs_cycle": False,
                "completion_audit_runs_indexing": False,
                "heavy_verifier_requires_resource_guard": True,
            },
            "evidence_refs": row.get("evidence_refs") if isinstance(row.get("evidence_refs"), list) else [
                {"path": str(paths.requirement_probes), "requirement_id": requirement_id}
            ],
            "policy": {
                "handoff_only": True,
                "requires_human_approval": True,
                "executes_commands": False,
                "host_layer_mutates_stack": False,
                "automatic_remediation": False,
                "actions_executed": False,
            },
        })
    for row in open_potential_rows:
        if not isinstance(row, dict):
            continue
        service = str(row.get("service") or "unknown")
        score, priority_class, priority_reasons = working_stack_priority(row)
        safe_next = row.get("safe_next_action") if isinstance(row.get("safe_next_action"), dict) else {}
        actions.append({
            "schema": f"{schema_prefix}_self_awareness_completion_action_v1",
            "id": f"working-stack:{service}",
            "category": "working_stack_usage_gap",
            "owner_route": row.get("owner") or "abyss-stack",
            "service": service,
            "machine_usage_status": row.get("machine_usage_status"),
            "usage_gap": row.get("usage_gap"),
            "activation_gap_classification": row.get("activation_gap_classification"),
            "priority_score": score,
            "priority_class": priority_class,
            "priority_reasons": priority_reasons,
            "closure_blocker_keys": row.get("closure_blocker_keys") if isinstance(row.get("closure_blocker_keys"), list) else [],
            "missing_checks": row.get("missing_checks") if isinstance(row.get("missing_checks"), list) else [],
            "verifier_commands": row.get("verifier_commands") if isinstance(row.get("verifier_commands"), list) else [],
            "safe_next_action": safe_next,
            "activation_gap_route": row.get("activation_gap_route") if isinstance(row.get("activation_gap_route"), dict) else {},
            "resource_gate": {
                "current_audit_resource_guard_ok": resource_guard_ok,
                "completion_audit_runs_probe": False,
                "completion_audit_runs_cycle": False,
                "completion_audit_runs_indexing": False,
                "heavy_verifier_requires_resource_guard": True,
            },
            "evidence_refs": row.get("evidence_refs") if isinstance(row.get("evidence_refs"), list) else [
                {"path": str(paths.working_stack), "service": service}
            ],
            "policy": {
                "handoff_only": True,
                "requires_human_approval": True,
                "executes_commands": False,
                "host_layer_mutates_stack": False,
                "automatic_remediation": False,
                "actions_executed": False,
            },
        })
    actions.sort(key=lambda item: (-_safe_int(item.get("priority_score"), 0), str(item.get("id") or "")))
    for rank, action in enumerate(actions, start=1):
        action["priority_rank"] = rank
        action["drilldown_id"] = "sacompletiondrill-" + self_awareness_contracts.stable_hash_json(
            {"action_id": action.get("id"), "category": action.get("category")},
            length=24,
        )
    return actions

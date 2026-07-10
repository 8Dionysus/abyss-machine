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


@dataclass(frozen=True)
class CompletionDrilldownContext:
    resource_preflight: Mapping[str, Any]
    requirements: Mapping[str, Any]
    requirement_probes: Mapping[str, Any]
    stack_closure_dossier: Mapping[str, Any]
    coverage_rows: list[dict[str, Any]]
    open_potential_rows: list[dict[str, Any]]
    activation_smoke: Mapping[str, Any]
    paths: CompletionAuditPaths


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


def first_matching_row(rows: Any, *pairs: tuple[str, str]) -> dict[str, Any]:
    if not isinstance(rows, list):
        return {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        if all(str(row.get(key) or "") == value for key, value in pairs):
            return row
    return {}


def _checks_from_probe(probe: Mapping[str, Any], ok: bool) -> list[dict[str, Any]]:
    checks = probe.get("checks") if isinstance(probe.get("checks"), list) else []
    return [
        {
            "key": check.get("key"),
            "level": check.get("level"),
            "message": check.get("message"),
            "evidence_hint": check.get("data") if isinstance(check.get("data"), dict) else {},
        }
        for check in checks
        if isinstance(check, dict) and (check.get("ok") is True) is ok
    ]


def _verifier_commands_from_chain(chain: Any) -> list[str]:
    commands: list[str] = []
    if isinstance(chain, list):
        for item in chain:
            if isinstance(item, dict) and item.get("command"):
                commands.append(str(item.get("command")))
            elif isinstance(item, str) and item:
                commands.append(item)
    return list(dict.fromkeys(commands))


def completion_action_drilldown(
    action: dict[str, Any],
    *,
    schema_prefix: str,
    context: CompletionDrilldownContext,
) -> dict[str, Any]:
    nested_get = self_awareness_contracts.nested_get
    action_id = str(action.get("id") or "")
    category = str(action.get("category") or "")
    drilldown_id = "sacompletiondrill-" + self_awareness_contracts.stable_hash_json(
        {"action_id": action_id, "category": category},
        length=24,
    )
    action_resource_gate = action.get("resource_gate") if isinstance(action.get("resource_gate"), dict) else {}
    safe_next = action.get("safe_next_action") if isinstance(action.get("safe_next_action"), dict) else {}
    common_policy = {
        "handoff_only": True,
        "read_only": True,
        "requires_human_approval": True,
        "executes_commands": False,
        "host_layer_mutates_stack": False,
        "writes_project_roots": False,
        "automatic_remediation": False,
        "actions_executed": False,
        "completion_audit_runs_probe": False,
        "completion_audit_runs_cycle": False,
        "completion_audit_runs_indexing": False,
    }
    source_artifacts = [
        {"name": "completion_audit", "path": str(context.paths.completion_audit)},
        {"name": "coverage_audit", "path": str(context.paths.coverage_audit)},
        {"name": "autolink", "path": str(context.paths.autolink)},
    ]
    payload: dict[str, Any] = {
        "schema": f"{schema_prefix}_self_awareness_completion_action_drilldown_v1",
        "id": drilldown_id,
        "action_id": action_id,
        "category": category,
        "owner_route": action.get("owner_route"),
        "priority": {
            "rank": action.get("priority_rank"),
            "score": action.get("priority_score"),
            "class": action.get("priority_class"),
            "reasons": action.get("priority_reasons") if isinstance(action.get("priority_reasons"), list) else [],
        },
        "resource_gate": {
            **action_resource_gate,
            "latest_only_readmodel": True,
            "heavy_verifier_requires_resource_guard": True,
            "resource_preflight_ok": bool(context.resource_preflight.get("ok")),
        },
        "safe_next_action": safe_next,
        "source_artifacts": source_artifacts,
        "policy": common_policy,
    }
    if category == "stack_requirement":
        requirement_id = str(action.get("requirement_id") or "")
        requirement = first_matching_row(context.requirements.get("requirements"), ("id", requirement_id))
        handoff = first_matching_row(context.requirements.get("stack_handoff"), ("requirement_id", requirement_id))
        probe = first_matching_row(context.requirement_probes.get("probes"), ("requirement_id", requirement_id))
        if not probe:
            probe = first_matching_row(context.requirement_probes.get("probes"), ("id", requirement_id))
        dossier_entry = first_matching_row(
            context.stack_closure_dossier.get("entries"),
            ("requirement_id", requirement_id),
        )
        closure_readiness = (
            dossier_entry.get("closure_readiness")
            if isinstance(dossier_entry.get("closure_readiness"), dict)
            else {}
        )
        if not closure_readiness and isinstance(probe.get("closure_readiness"), dict):
            closure_readiness = probe["closure_readiness"]
        closure_acceptance = (
            dossier_entry.get("closure_acceptance")
            if isinstance(dossier_entry.get("closure_acceptance"), dict)
            else {}
        )
        pre_close_identity = (
            closure_acceptance.get("pre_close_identity")
            if isinstance(closure_acceptance.get("pre_close_identity"), dict)
            else {}
        )
        stack_compat_requirement = (
            closure_acceptance.get("stack_compat_requirement")
            if isinstance(closure_acceptance.get("stack_compat_requirement"), dict)
            else {}
        )
        closure_diff_contract = (
            closure_acceptance.get("closure_diff_contract")
            if isinstance(closure_acceptance.get("closure_diff_contract"), dict)
            else {}
        )
        coverage_rows_for_requirement = [
            {
                "id": row.get("id"),
                "status": row.get("status"),
                "objective_area": row.get("objective_area"),
                "coverage_planes": row.get("coverage_planes") if isinstance(row.get("coverage_planes"), list) else [],
                "open_stack_requirement_ids": (
                    row.get("open_stack_requirement_ids")
                    if isinstance(row.get("open_stack_requirement_ids"), list)
                    else []
                ),
                "missing_chain_keys": row.get("missing_chain_keys") if isinstance(row.get("missing_chain_keys"), list) else [],
                "chain_keys": row.get("chain_keys") if isinstance(row.get("chain_keys"), list) else [],
            }
            for row in context.coverage_rows
            if isinstance(row, dict)
            and requirement_id
            in {
                str(item)
                for item in (
                    row.get("open_stack_requirement_ids")
                    if isinstance(row.get("open_stack_requirement_ids"), list)
                    else []
                )
            }
        ]
        fulfilled_checks = (
            closure_readiness.get("fulfilled_checks")
            if isinstance(closure_readiness.get("fulfilled_checks"), list)
            else _checks_from_probe(probe, True)
        )
        missing_checks = (
            closure_readiness.get("missing_checks")
            if isinstance(closure_readiness.get("missing_checks"), list)
            else action.get("missing_checks")
            if isinstance(action.get("missing_checks"), list)
            else _checks_from_probe(probe, False)
        )
        post_close_verifier_chain = (
            closure_acceptance.get("post_close_verifier_chain")
            if isinstance(closure_acceptance.get("post_close_verifier_chain"), list)
            else []
        )
        negative_controls = (
            closure_acceptance.get("negative_controls")
            if isinstance(closure_acceptance.get("negative_controls"), list)
            else []
        )
        verifier_commands = list(dict.fromkeys(
            _verifier_commands_from_chain(post_close_verifier_chain)
            + [
                str(item)
                for item in (
                    action.get("verifier_commands")
                    if isinstance(action.get("verifier_commands"), list)
                    else []
                )
                if item
            ]
        ))
        coverage_impact = (
            dossier_entry.get("coverage_impact")
            if isinstance(dossier_entry.get("coverage_impact"), dict)
            else stack_compat_requirement.get("coverage_contract")
            if isinstance(stack_compat_requirement.get("coverage_contract"), dict)
            else {}
        )
        dependency_contract = (
            stack_compat_requirement.get("dependency_contract")
            if isinstance(stack_compat_requirement.get("dependency_contract"), dict)
            else {}
        )
        payload.update({
            "requirement_id": requirement_id,
            "title": action.get("title") or requirement.get("title") or handoff.get("title"),
            "current_state": (
                probe.get("current_state")
                if isinstance(probe.get("current_state"), dict)
                else dossier_entry.get("current_state")
                if isinstance(dossier_entry.get("current_state"), dict)
                else {}
            ),
            "current_state_identity": {
                "digest": pre_close_identity.get("current_state_digest") or dossier_entry.get("current_state_digest"),
                "keys": (
                    pre_close_identity.get("current_state_keys")
                    if isinstance(pre_close_identity.get("current_state_keys"), list)
                    else nested_get(closure_readiness, ["current_state_digest", "keys"]) or []
                ),
                "closed_by_current_probe": bool(
                    probe.get("closed_by_current_probe") or dossier_entry.get("closed_by_current_probe")
                ),
                "readiness_score": closure_readiness.get("readiness_score") or dossier_entry.get("readiness_score"),
            },
            "checks": {
                "missing": missing_checks,
                "fulfilled": fulfilled_checks,
                "blocking_check_keys": (
                    action.get("closure_blocker_keys")
                    if isinstance(action.get("closure_blocker_keys"), list)
                    else closure_readiness.get("blocking_check_keys")
                    if isinstance(closure_readiness.get("blocking_check_keys"), list)
                    else []
                ),
                "open_blocker_count": len(missing_checks),
                "fulfilled_check_count": len(fulfilled_checks) if isinstance(fulfilled_checks, list) else 0,
            },
            "coverage": {
                "planes": (
                    action.get("coverage_planes")
                    if isinstance(action.get("coverage_planes"), list)
                    else coverage_impact.get("coverage_planes")
                    if isinstance(coverage_impact.get("coverage_planes"), list)
                    else []
                ),
                "impact": coverage_impact,
                "rows": coverage_rows_for_requirement,
                "blocked_stack_usage_requirements": (
                    coverage_impact.get("blocks_stack_usage_requirements")
                    if isinstance(coverage_impact.get("blocks_stack_usage_requirements"), list)
                    else []
                ),
            },
            "dependency_edges": {
                "depends_on_requirement_ids": (
                    dossier_entry.get("depends_on_requirement_ids")
                    if isinstance(dossier_entry.get("depends_on_requirement_ids"), list)
                    else dependency_contract.get("depends_on_requirement_ids")
                    if isinstance(dependency_contract.get("depends_on_requirement_ids"), list)
                    else []
                ),
                "unblocks_requirement_ids": (
                    dossier_entry.get("unblocks_requirement_ids")
                    if isinstance(dossier_entry.get("unblocks_requirement_ids"), list)
                    else dependency_contract.get("unblocks_requirement_ids")
                    if isinstance(dependency_contract.get("unblocks_requirement_ids"), list)
                    else []
                ),
                "blocked_by_dependency_edges": (
                    dossier_entry.get("blocked_by_dependency_edges")
                    if isinstance(dossier_entry.get("blocked_by_dependency_edges"), list)
                    else []
                ),
                "unblocks_dependency_edges": (
                    dossier_entry.get("unblocks_dependency_edges")
                    if isinstance(dossier_entry.get("unblocks_dependency_edges"), list)
                    else []
                ),
                "closure_impact": (
                    dossier_entry.get("closure_impact")
                    if isinstance(dossier_entry.get("closure_impact"), dict)
                    else {}
                ),
            },
            "closure_acceptance": {
                "schema": closure_acceptance.get("schema"),
                "acceptance_id": closure_acceptance.get("acceptance_id"),
                "complete": bool(closure_acceptance.get("complete")),
                "status": closure_acceptance.get("status"),
                "surface_kind": closure_acceptance.get("surface_kind"),
                "pre_close_identity": pre_close_identity,
                "stack_compat_requirement": stack_compat_requirement,
                "closure_diff_contract": closure_diff_contract,
                "post_close_success_predicates": (
                    closure_acceptance.get("post_close_success_predicates")
                    if isinstance(closure_acceptance.get("post_close_success_predicates"), list)
                    else []
                ),
                "post_close_verifier_chain": post_close_verifier_chain,
                "negative_controls": negative_controls,
                "safe_next_action": (
                    closure_acceptance.get("safe_next_action")
                    if isinstance(closure_acceptance.get("safe_next_action"), dict)
                    else safe_next
                ),
                "no_partial_credit_conditions": (
                    closure_diff_contract.get("no_partial_credit_conditions")
                    if isinstance(closure_diff_contract.get("no_partial_credit_conditions"), list)
                    else []
                ),
            },
            "acceptance": {
                "required_fields": (
                    nested_get(stack_compat_requirement, ["minimum_response_contract", "required_fields"])
                    or closure_readiness.get("required_fields")
                    or []
                ),
                "success_predicates": (
                    nested_get(stack_compat_requirement, ["minimum_response_contract", "success_predicates"])
                    or closure_readiness.get("success_predicates")
                    or []
                ),
                "verifier_commands": verifier_commands,
                "post_close_verifier_chain": post_close_verifier_chain,
                "negative_controls": negative_controls,
                "redaction_contract": (
                    stack_compat_requirement.get("redaction_contract")
                    if isinstance(stack_compat_requirement.get("redaction_contract"), dict)
                    else {}
                ),
                "operator_boundary": (
                    stack_compat_requirement.get("operator_boundary")
                    if isinstance(stack_compat_requirement.get("operator_boundary"), dict)
                    else {}
                ),
            },
            "evidence_refs": (
                action.get("evidence_refs")
                if isinstance(action.get("evidence_refs"), list)
                else closure_acceptance.get("evidence_refs")
                if isinstance(closure_acceptance.get("evidence_refs"), list)
                else []
            ),
            "next_step_packet": {
                "kind": "stack_owner_requirement_closure_packet",
                "owner_route": "abyss-stack",
                "read_command": "abyss-machine self-awareness completion-audit --json",
                "probe_command": "abyss-machine self-awareness requirement-probes --json",
                "dossier_command": "abyss-machine self-awareness stack-closure-dossier --json",
                "closure_requires_stack_owned_change": True,
                "closure_requires_current_probe_success": True,
                "audit_executes_verifiers": False,
                "heavy_verifiers_require_resource_guard": True,
                "verifier_commands": verifier_commands,
            },
        })
        stack_complete = (
            bool(requirement_id)
            and bool(payload["checks"]["missing"])
            and bool(payload["checks"]["fulfilled"])
            and bool(payload["coverage"]["planes"])
            and bool(payload["closure_acceptance"]["complete"])
            and bool(payload["acceptance"]["required_fields"])
            and bool(payload["acceptance"]["success_predicates"])
            and bool(payload["acceptance"]["verifier_commands"])
            and nested_get(payload, ["acceptance", "operator_boundary", "host_layer_mutates_stack"]) is False
            and nested_get(payload, ["acceptance", "operator_boundary", "abyss_machine_executes_stack_change"])
            is False
        )
        payload["complete"] = bool(
            stack_complete
            and safe_next.get("executes_commands") is False
            and safe_next.get("host_layer_mutates_stack") is False
        )
    elif category == "working_stack_usage_gap":
        service = str(action.get("service") or "")
        potential_row = first_matching_row(context.open_potential_rows, ("service", service))
        activation_rows = (
            context.activation_smoke.get("rows")
            if isinstance(context.activation_smoke.get("rows"), list)
            else []
        )
        activation_row = first_matching_row(activation_rows, ("service", service))
        activation_route = (
            action.get("activation_gap_route")
            if isinstance(action.get("activation_gap_route"), dict)
            else potential_row.get("activation_gap_route")
            if isinstance(potential_row.get("activation_gap_route"), dict)
            else {}
        )
        verifier_commands = [
            str(item)
            for item in (
                action.get("verifier_commands")
                if isinstance(action.get("verifier_commands"), list)
                else []
            )
            if item
        ]
        payload.update({
            "service": service,
            "activation_gap_classification": action.get("activation_gap_classification"),
            "machine_usage_status": action.get("machine_usage_status"),
            "usage_gap": action.get("usage_gap"),
            "current_state": (
                activation_route.get("current_state")
                if isinstance(activation_route.get("current_state"), dict)
                else {}
            ),
            "checks": {
                "missing": action.get("missing_checks") if isinstance(action.get("missing_checks"), list) else [],
                "closure_blocker_keys": (
                    action.get("closure_blocker_keys")
                    if isinstance(action.get("closure_blocker_keys"), list)
                    else []
                ),
            },
            "activation_smoke": {
                "row": activation_row,
                "row_complete": activation_row.get("complete") is True,
                "working_stack_gap_replayable": (
                    nested_get(activation_row, ["replay", "working_stack_gap_replayable"]) is True
                ),
            },
            "activation_gap_route": activation_route,
            "acceptance": {
                "verifier_commands": verifier_commands,
                "requires_functional_smoke_or_runtime_state_evidence": True,
            },
            "next_step_packet": {
                "kind": "stack_owner_working_stack_usage_gap_packet",
                "owner_route": "abyss-stack",
                "read_command": "abyss-machine self-awareness completion-audit --json",
                "working_stack_command": "abyss-machine self-awareness working-stack --json",
                "activation_smoke_command": "abyss-machine self-awareness activation-smoke --json",
                "audit_executes_verifiers": False,
                "heavy_verifiers_require_resource_guard": True,
                "verifier_commands": verifier_commands,
            },
            "evidence_refs": action.get("evidence_refs") if isinstance(action.get("evidence_refs"), list) else [],
        })
        payload["complete"] = bool(
            service
            and payload["checks"]["missing"]
            and payload["checks"]["closure_blocker_keys"]
            and verifier_commands
            and safe_next.get("executes_commands") is False
            and safe_next.get("host_layer_mutates_stack") is False
        )
    else:
        payload["complete"] = False
    return payload


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

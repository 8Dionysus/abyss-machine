from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import self_awareness_contracts


DocumentPort = Callable[..., Any]


@dataclass(frozen=True)
class SelfAwarenessStackClosurePaths:
    requirements_latest: Path
    requirements_root: Path
    capabilities_latest: Path
    requirement_probes_latest: Path
    requirement_probes_root: Path
    failure_matrix_latest: Path
    brief_latest: Path
    investigate_latest: Path
    replay_latest: Path
    export_latest: Path
    validate_latest: Path
    working_stack_latest: Path
    stack_closure_dossier_latest: Path
    stack_closure_dossier_root: Path


@dataclass(frozen=True)
class SelfAwarenessStackClosureRuntimePort:
    now_iso: DocumentPort
    write_latest_and_history: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessStackClosureRefreshPort:
    capabilities: DocumentPort
    requirements: DocumentPort
    requirement_probes: DocumentPort
    working_stack_activation_dossier: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessStackClosureContractPort:
    requirement_probe_evaluate: DocumentPort
    requirements_with_probe_readiness: DocumentPort
    brief_stack_handoff_action_map: DocumentPort
    latest_artifact_ref: DocumentPort
    requirement_acceptance_contract: DocumentPort
    stack_requirement_coverage_impact: DocumentPort
    stack_requirement_compat_contract: DocumentPort
    stack_compat_contract_complete: DocumentPort
    stack_requirement_closure_acceptance: DocumentPort
    stack_requirement_closure_acceptance_complete: DocumentPort


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def requirement_probes(
    write_latest: bool = True,
    requirements_doc: dict[str, Any] | None = None,
    capabilities: dict[str, Any] | None = None,
    *,
    schema_prefix: str,
    version: str,
    paths: SelfAwarenessStackClosurePaths,
    runtime_port: SelfAwarenessStackClosureRuntimePort,
    refresh_port: SelfAwarenessStackClosureRefreshPort,
    contract_port: SelfAwarenessStackClosureContractPort,
) -> dict[str, Any]:
    SCHEMA_PREFIX = schema_prefix
    VERSION = version
    SELF_AWARENESS_REQUIREMENTS_LATEST_PATH = paths.requirements_latest
    SELF_AWARENESS_REQUIREMENTS_ROOT = paths.requirements_root
    SELF_AWARENESS_CAPABILITIES_LATEST_PATH = paths.capabilities_latest
    SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH = paths.requirement_probes_latest
    SELF_AWARENESS_REQUIREMENT_PROBES_ROOT = paths.requirement_probes_root
    now_iso = runtime_port.now_iso
    write_latest_and_history = runtime_port.write_latest_and_history
    nested_get = self_awareness_contracts.nested_get
    safe_int = _safe_int
    self_awareness_capabilities = refresh_port.capabilities
    self_awareness_requirements = refresh_port.requirements
    self_awareness_requirement_probe_evaluate = contract_port.requirement_probe_evaluate
    self_awareness_requirements_with_probe_readiness = contract_port.requirements_with_probe_readiness
    generated_at = now_iso()
    capabilities = capabilities if isinstance(capabilities, dict) else self_awareness_capabilities(write_latest=True)
    explicit_requirements_doc = isinstance(requirements_doc, dict)
    requirements_doc = requirements_doc if explicit_requirements_doc else self_awareness_requirements(write_latest=write_latest)
    requirements = requirements_doc.get("requirements") if isinstance(requirements_doc.get("requirements"), list) else []
    stack_handoff = requirements_doc.get("stack_handoff") if isinstance(requirements_doc.get("stack_handoff"), list) else []
    requirement_by_id = {
        str(item.get("id")): item
        for item in requirements
        if isinstance(item, dict) and item.get("id")
    }
    probes = [
        self_awareness_requirement_probe_evaluate(handoff, capabilities, requirement_by_id.get(str(handoff.get("id") or handoff.get("requirement_id") or "")))
        for handoff in stack_handoff
        if isinstance(handoff, dict)
    ]
    internal_contract_failures = [
        probe.get("id") for probe in probes
        if any(check.get("level") == "fail" for check in probe.get("checks", []) if isinstance(check, dict))
    ]
    secret_leaks = [
        probe.get("id") for probe in probes
        if any(check.get("key") == "no_secret_leakage" and check.get("ok") is False for check in probe.get("checks", []) if isinstance(check, dict))
    ]
    mutating_routes = [
        probe.get("id") for probe in probes
        if probe.get("host_layer_mutates_stack") is not False
    ]
    open_probes = [probe for probe in probes if probe.get("status") != "closed"]
    closed_probes = [probe for probe in probes if probe.get("closed_by_current_probe")]
    runbook_candidates = [
        probe.get("runbook_candidate")
        for probe in probes
        if isinstance(probe, dict) and isinstance(probe.get("runbook_candidate"), dict)
    ]
    closure_readiness_packets = [
        probe.get("closure_readiness")
        for probe in probes
        if isinstance(probe, dict) and isinstance(probe.get("closure_readiness"), dict)
    ]
    missing_check_total = sum(
        safe_int(nested_get(packet, ["open_blocker_count"]), 0)
        for packet in closure_readiness_packets
        if isinstance(packet, dict)
    )
    fulfilled_check_total = sum(
        safe_int(nested_get(packet, ["fulfilled_check_count"]), 0)
        for packet in closure_readiness_packets
        if isinstance(packet, dict)
    )
    dependency_edges = sum(
        len(packet.get("dependency_requirement_ids") if isinstance(packet.get("dependency_requirement_ids"), list) else [])
        for packet in closure_readiness_packets
        if isinstance(packet, dict)
    )
    data = {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_requirement_probes_v1",
        "version": VERSION,
        "generated_at": generated_at,
        "ok": not internal_contract_failures and not secret_leaks and not mutating_routes,
        "status": "open_requirements" if open_probes else "satisfied",
        "summary": {
            "probes": len(probes),
            "open": len(open_probes),
            "closed_by_current_probe": len(closed_probes),
            "stack_handoff": len(stack_handoff),
            "internal_contract_failures": internal_contract_failures,
            "secret_leaks": len(secret_leaks),
            "mutating_routes": len(mutating_routes),
            "runbook_candidates": len(runbook_candidates),
            "machine_closure_probes": sum(1 for probe in probes if isinstance(probe.get("machine_closure_probe"), dict)),
            "acceptance_verifier_steps": sum(len(probe.get("acceptance_verifiers") if isinstance(probe.get("acceptance_verifiers"), list) else []) for probe in probes),
            "closure_readiness_packets": len(closure_readiness_packets),
            "closure_readiness_fulfilled_checks": fulfilled_check_total,
            "closure_readiness_missing_checks": missing_check_total,
            "closure_readiness_dependency_edges": dependency_edges,
        },
        "probes": probes,
        "runbook_candidates": runbook_candidates,
        "closure_readiness": closure_readiness_packets,
        "open_requirements": [
            {
                "id": probe.get("id"),
                "owner": probe.get("owner"),
                "probe_kind": probe.get("probe_kind"),
                "current_state": probe.get("current_state"),
                "closure_readiness": probe.get("closure_readiness"),
                "evidence_refs": probe.get("evidence_refs"),
                "runbook_candidate_id": nested_get(probe, ["runbook_candidate", "id"]),
            }
            for probe in open_probes
        ],
        "closed_requirements": [
            {
                "id": probe.get("id"),
                "owner": probe.get("owner"),
                "probe_kind": probe.get("probe_kind"),
                "evidence_refs": probe.get("evidence_refs"),
            }
            for probe in closed_probes
        ],
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "requirements_are_not_stack_mutations": True,
            "open_stack_requirements_are_blockers_not_host_failures": True,
            "closure_requires_probe_success": True,
            "runbook_candidates_are_handoff_only": True,
            "no_runtime_changes": True,
        },
        "evidence_refs": [
            {"path": str(SELF_AWARENESS_REQUIREMENTS_LATEST_PATH), "schema": requirements_doc.get("schema")},
            {"path": str(SELF_AWARENESS_CAPABILITIES_LATEST_PATH), "schema": capabilities.get("schema")},
        ],
        "tests": {
            "contract": "stack_handoff acceptance_contract and machine_closure_probe are evaluated for every open stack-owned requirement",
            "live": "abyss-machine self-awareness requirement-probes --json runs read-only against latest capability evidence",
        },
    }
    if write_latest:
        errors = write_latest_and_history(data, SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH, SELF_AWARENESS_REQUIREMENT_PROBES_ROOT)
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
        if not explicit_requirements_doc:
            enriched_requirements = self_awareness_requirements_with_probe_readiness(requirements_doc, data)
            write_latest_and_history(enriched_requirements, SELF_AWARENESS_REQUIREMENTS_LATEST_PATH, SELF_AWARENESS_REQUIREMENTS_ROOT)
    return data


def stack_closure_dossier(
    write_latest: bool = True,
    requirements_doc: dict[str, Any] | None = None,
    requirement_probes_doc: dict[str, Any] | None = None,
    working_stack_doc: dict[str, Any] | None = None,
    *,
    schema_prefix: str,
    version: str,
    paths: SelfAwarenessStackClosurePaths,
    runtime_port: SelfAwarenessStackClosureRuntimePort,
    refresh_port: SelfAwarenessStackClosureRefreshPort,
    contract_port: SelfAwarenessStackClosureContractPort,
) -> dict[str, Any]:
    SCHEMA_PREFIX = schema_prefix
    VERSION = version
    SELF_AWARENESS_REQUIREMENTS_LATEST_PATH = paths.requirements_latest
    SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH = paths.requirement_probes_latest
    SELF_AWARENESS_FAILURE_MATRIX_LATEST_PATH = paths.failure_matrix_latest
    SELF_AWARENESS_BRIEF_LATEST_PATH = paths.brief_latest
    SELF_AWARENESS_INVESTIGATE_LATEST_PATH = paths.investigate_latest
    SELF_AWARENESS_REPLAY_LATEST_PATH = paths.replay_latest
    SELF_AWARENESS_EXPORT_LATEST_PATH = paths.export_latest
    SELF_AWARENESS_VALIDATE_LATEST_PATH = paths.validate_latest
    SELF_AWARENESS_WORKING_STACK_LATEST_PATH = paths.working_stack_latest
    SELF_AWARENESS_STACK_CLOSURE_DOSSIER_LATEST_PATH = paths.stack_closure_dossier_latest
    SELF_AWARENESS_STACK_CLOSURE_DOSSIER_ROOT = paths.stack_closure_dossier_root
    now_iso = runtime_port.now_iso
    write_latest_and_history = runtime_port.write_latest_and_history
    nested_get = self_awareness_contracts.nested_get
    stable_hash_json = self_awareness_contracts.stable_hash_json
    safe_int = _safe_int
    self_awareness_requirements = refresh_port.requirements
    self_awareness_requirement_probes = refresh_port.requirement_probes
    self_awareness_working_stack_activation_dossier = refresh_port.working_stack_activation_dossier
    self_awareness_brief_stack_handoff_action_map = contract_port.brief_stack_handoff_action_map
    self_awareness_latest_artifact_ref = contract_port.latest_artifact_ref
    self_awareness_requirement_acceptance_contract = contract_port.requirement_acceptance_contract
    self_awareness_stack_requirement_coverage_impact = contract_port.stack_requirement_coverage_impact
    self_awareness_stack_requirement_compat_contract = contract_port.stack_requirement_compat_contract
    self_awareness_stack_compat_contract_complete = contract_port.stack_compat_contract_complete
    self_awareness_stack_requirement_closure_acceptance = contract_port.stack_requirement_closure_acceptance
    self_awareness_stack_requirement_closure_acceptance_complete = contract_port.stack_requirement_closure_acceptance_complete
    generated_at = now_iso()
    requirements_doc = requirements_doc if isinstance(requirements_doc, dict) else self_awareness_requirements(write_latest=write_latest)
    requirement_probes_doc = requirement_probes_doc if isinstance(requirement_probes_doc, dict) else self_awareness_requirement_probes(write_latest=write_latest, requirements_doc=requirements_doc)
    working_stack_activation_dossier = self_awareness_working_stack_activation_dossier(
        working_stack_doc,
        generated_at=generated_at,
        write_latest=write_latest,
    )
    working_stack_activation_entries = working_stack_activation_dossier.get("entries") if isinstance(working_stack_activation_dossier.get("entries"), list) else []
    working_stack_activation_summary = working_stack_activation_dossier.get("summary") if isinstance(working_stack_activation_dossier.get("summary"), dict) else {}
    working_stack_activation_handoff = working_stack_activation_dossier.get("working_stack_activation_handoff") if isinstance(working_stack_activation_dossier.get("working_stack_activation_handoff"), dict) else {}
    action_map = self_awareness_brief_stack_handoff_action_map(requirement_probes_doc)
    actions = action_map.get("actions") if isinstance(action_map.get("actions"), list) else []
    action_by_requirement = {
        str(action.get("requirement_id")): action
        for action in actions
        if isinstance(action, dict) and action.get("requirement_id")
    }
    probes = requirement_probes_doc.get("probes") if isinstance(requirement_probes_doc.get("probes"), list) else []
    requirements = requirements_doc.get("requirements") if isinstance(requirements_doc.get("requirements"), list) else []
    requirement_by_id = {
        str(item.get("id")): item
        for item in requirements
        if isinstance(item, dict) and item.get("id")
    }
    ordered_probe_ids = [str(action.get("requirement_id")) for action in actions if isinstance(action, dict) and action.get("requirement_id")]
    ordered_probe_ids.extend(
        str(probe.get("requirement_id") or probe.get("id"))
        for probe in probes
        if isinstance(probe, dict)
        and str(probe.get("requirement_id") or probe.get("id") or "") not in ordered_probe_ids
    )
    probe_by_id = {
        str(probe.get("requirement_id") or probe.get("id")): probe
        for probe in probes
        if isinstance(probe, dict) and (probe.get("requirement_id") or probe.get("id"))
    }

    artifact_refs = {
        "requirements": self_awareness_latest_artifact_ref("requirements", SELF_AWARENESS_REQUIREMENTS_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_requirements_v1"),
        "requirement_probes": self_awareness_latest_artifact_ref("requirement_probes", SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_requirement_probes_v1"),
        "failure_matrix": self_awareness_latest_artifact_ref("failure_matrix", SELF_AWARENESS_FAILURE_MATRIX_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_failure_matrix_v1"),
        "brief": self_awareness_latest_artifact_ref("brief", SELF_AWARENESS_BRIEF_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_brief_v1"),
        "investigate": self_awareness_latest_artifact_ref("investigate", SELF_AWARENESS_INVESTIGATE_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_investigation_v1"),
        "replay": self_awareness_latest_artifact_ref("replay", SELF_AWARENESS_REPLAY_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_replay_v1"),
        "export": self_awareness_latest_artifact_ref("export", SELF_AWARENESS_EXPORT_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_export_v1"),
        "validate": self_awareness_latest_artifact_ref("validate", SELF_AWARENESS_VALIDATE_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_validate_v1"),
        "working_stack": self_awareness_latest_artifact_ref("working_stack", SELF_AWARENESS_WORKING_STACK_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_working_stack_inventory_v1"),
    }

    entries: list[dict[str, Any]] = []
    dependency_edges: list[dict[str, Any]] = []
    for index, requirement_id in enumerate(ordered_probe_ids, start=1):
        probe = probe_by_id.get(requirement_id)
        if not isinstance(probe, dict):
            continue
        requirement = requirement_by_id.get(requirement_id, {})
        readiness = probe.get("closure_readiness") if isinstance(probe.get("closure_readiness"), dict) else {}
        action = action_by_requirement.get(requirement_id, {})
        current_state = probe.get("current_state") if isinstance(probe.get("current_state"), dict) else {}
        runbook = probe.get("runbook_candidate") if isinstance(probe.get("runbook_candidate"), dict) else {}
        dependency_ids = readiness.get("dependency_requirement_ids") if isinstance(readiness.get("dependency_requirement_ids"), list) else []
        for dependency_id in dependency_ids:
            dependency_edges.append({
                "from": requirement_id,
                "to": dependency_id,
                "kind": "requires_stack_requirement",
                "reason": readiness.get("dependency_reasons"),
            })
        missing_checks = readiness.get("missing_checks") if isinstance(readiness.get("missing_checks"), list) else []
        fulfilled_checks = readiness.get("fulfilled_checks") if isinstance(readiness.get("fulfilled_checks"), list) else []
        fallback_requirement = {"id": requirement_id, "owner": "abyss-stack", "status": probe.get("status"), "expected_shape": {}}
        requirement_for_contract = requirement if isinstance(requirement, dict) and requirement else fallback_requirement
        acceptance_contract = probe.get("acceptance_contract") if isinstance(probe.get("acceptance_contract"), dict) else self_awareness_requirement_acceptance_contract(requirement_for_contract)
        coverage_impact = self_awareness_stack_requirement_coverage_impact(requirement_id)
        compat_contract = self_awareness_stack_requirement_compat_contract(
            requirement_for_contract,
            acceptance_contract=acceptance_contract,
            readiness=readiness,
            current_state=current_state,
            coverage_impact=coverage_impact,
            dependency_requirement_ids=[str(item) for item in dependency_ids],
        )
        entry = {
            "schema": f"{SCHEMA_PREFIX}_self_awareness_stack_closure_dossier_entry_v1",
            "order": index,
            "requirement_id": requirement_id,
            "title": requirement.get("title") or probe.get("id") or requirement_id,
            "owner": probe.get("owner") or requirement.get("owner") or "abyss-stack",
            "status": probe.get("status"),
            "closed_by_current_probe": probe.get("closed_by_current_probe"),
            "priority_class": action.get("priority_class"),
            "readiness_score": readiness.get("readiness_score"),
            "probe_kind": probe.get("probe_kind"),
            "source_handoff_command": probe.get("source_handoff_command"),
            "machine_read_command": "abyss-machine self-awareness stack-closure-dossier --json",
            "requirement_probe_command": "abyss-machine self-awareness requirement-probes --json",
            "current_state": current_state,
            "current_state_digest": stable_hash_json(current_state, length=24),
            "fulfilled_checks": fulfilled_checks,
            "missing_checks": missing_checks,
            "blocking_check_keys": readiness.get("blocking_check_keys") if isinstance(readiness.get("blocking_check_keys"), list) else [],
            "dependency_requirement_ids": dependency_ids,
            "dependency_reasons": readiness.get("dependency_reasons") if isinstance(readiness.get("dependency_reasons"), list) else [],
            "closure_evidence_needed": readiness.get("closure_evidence_needed") if isinstance(readiness.get("closure_evidence_needed"), list) else [],
            "required_fields": readiness.get("required_fields") if isinstance(readiness.get("required_fields"), list) else [],
            "success_predicates": readiness.get("success_predicates") if isinstance(readiness.get("success_predicates"), list) else [],
            "redaction_rules": readiness.get("redaction_rules") if isinstance(readiness.get("redaction_rules"), list) else [],
            "boundedness": readiness.get("boundedness") if isinstance(readiness.get("boundedness"), dict) else {},
            "acceptance_verifiers": probe.get("acceptance_verifiers") if isinstance(probe.get("acceptance_verifiers"), list) else [],
            "verifier_commands": readiness.get("verifier_commands") if isinstance(readiness.get("verifier_commands"), list) else [],
            "safe_next_action": readiness.get("safe_next_action") if isinstance(readiness.get("safe_next_action"), dict) else {},
            "acceptance_contract": acceptance_contract,
            "compat_contract": compat_contract,
            "runbook_candidate": runbook,
            "closure_readiness": readiness,
            "coverage_impact": coverage_impact,
            "evidence_refs": probe.get("evidence_refs") if isinstance(probe.get("evidence_refs"), list) else [],
            "artifact_refs": {
                "requirements": artifact_refs["requirements"],
                "requirement_probes": artifact_refs["requirement_probes"],
            },
            "policy": {
                "handoff_only": True,
                "read_only": True,
                "executes_commands": False,
                "action_execution": False,
                "host_layer_mutates_stack": False,
                "writes_project_roots": False,
                "raw_secrets_included": False,
            },
            "complete": (
                bool(readiness.get("schema") == f"{SCHEMA_PREFIX}_stack_handoff_closure_readiness_v1")
                and bool(runbook)
                and self_awareness_stack_compat_contract_complete(compat_contract)
                and bool(probe.get("acceptance_verifiers"))
                and bool(readiness.get("verifier_commands"))
                and nested_get(readiness, ["policy", "host_layer_mutates_stack"]) is False
                and nested_get(readiness, ["policy", "executes_commands"]) is False
            ),
        }
        entries.append(entry)

    entry_order_by_id = {str(entry.get("requirement_id")): safe_int(entry.get("order"), 999999) for entry in entries if entry.get("requirement_id")}
    reverse_dependency_edges: list[dict[str, Any]] = []
    unblocks_by_requirement: dict[str, list[dict[str, Any]]] = {}
    blocked_by_requirement: dict[str, list[dict[str, Any]]] = {}
    for edge in dependency_edges:
        dependent_id = str(edge.get("from") or "")
        dependency_id = str(edge.get("to") or "")
        if not dependent_id or not dependency_id:
            continue
        blocked_by_requirement.setdefault(dependent_id, []).append(edge)
        reverse_edge = {
            "from": dependency_id,
            "to": dependent_id,
            "kind": "unblocks_stack_requirement",
            "reason": edge.get("reason"),
        }
        reverse_dependency_edges.append(reverse_edge)
        unblocks_by_requirement.setdefault(dependency_id, []).append(reverse_edge)
    reverse_dependency_edges = sorted(
        reverse_dependency_edges,
        key=lambda edge: (
            entry_order_by_id.get(str(edge.get("from") or ""), 999999),
            entry_order_by_id.get(str(edge.get("to") or ""), 999999),
            str(edge.get("to") or ""),
        ),
    )
    for entry in entries:
        requirement_id = str(entry.get("requirement_id") or "")
        blocked_edges = sorted(
            blocked_by_requirement.get(requirement_id, []),
            key=lambda edge: (entry_order_by_id.get(str(edge.get("to") or ""), 999999), str(edge.get("to") or "")),
        )
        unblock_edges = sorted(
            unblocks_by_requirement.get(requirement_id, []),
            key=lambda edge: (entry_order_by_id.get(str(edge.get("to") or ""), 999999), str(edge.get("to") or "")),
        )
        depends_on_ids = [str(edge.get("to")) for edge in blocked_edges if edge.get("to")]
        unblocks_ids = [str(edge.get("to")) for edge in unblock_edges if edge.get("to")]
        entry["depends_on_requirement_ids"] = depends_on_ids
        entry["blocked_by_dependency_edges"] = blocked_edges
        entry["unblocks_requirement_ids"] = unblocks_ids
        entry["unblocks_dependency_edges"] = unblock_edges
        entry["closure_impact"] = {
            "schema": f"{SCHEMA_PREFIX}_self_awareness_stack_closure_impact_v1",
            "requirement_id": requirement_id,
            "depends_on_requirement_ids": depends_on_ids,
            "unblocks_requirement_ids": unblocks_ids,
            "downstream_open_requirements": len(unblocks_ids),
            "is_dependency_root": not depends_on_ids,
            "is_unblocking_requirement": bool(unblocks_ids),
            "policy": {
                "handoff_only": True,
                "host_layer_mutates_stack": False,
                "executes_commands": False,
            },
        }
        if isinstance(entry.get("compat_contract"), dict):
            entry["compat_contract"].setdefault("dependency_contract", {})
            entry["compat_contract"]["dependency_contract"]["depends_on_requirement_ids"] = depends_on_ids
            entry["compat_contract"]["dependency_contract"]["unblocks_requirement_ids"] = unblocks_ids
        entry["closure_acceptance"] = self_awareness_stack_requirement_closure_acceptance(entry, generated_at)
        entry["complete"] = bool(
            entry.get("complete") is True
            and self_awareness_stack_requirement_closure_acceptance_complete(entry.get("closure_acceptance"))
        )

    open_entries = [entry for entry in entries if entry.get("closed_by_current_probe") is not True]
    closed_entries = [entry for entry in entries if entry.get("closed_by_current_probe") is True]
    missing_check_total = sum(len(entry.get("missing_checks") if isinstance(entry.get("missing_checks"), list) else []) for entry in entries)
    fulfilled_check_total = sum(len(entry.get("fulfilled_checks") if isinstance(entry.get("fulfilled_checks"), list) else []) for entry in entries)
    unblocking_requirement_ids = [
        str(entry.get("requirement_id"))
        for entry in entries
        if entry.get("unblocks_requirement_ids")
    ]
    dependent_requirement_ids = [
        str(entry.get("requirement_id"))
        for entry in entries
        if entry.get("depends_on_requirement_ids")
    ]
    dependency_root_requirement_ids = [
        str(entry.get("requirement_id"))
        for entry in entries
        if not entry.get("depends_on_requirement_ids")
    ]
    coverage_impact_entries = [
        entry.get("coverage_impact")
        for entry in entries
        if isinstance(entry.get("coverage_impact"), dict)
    ]
    compat_contract_entries = [
        entry.get("compat_contract")
        for entry in entries
        if self_awareness_stack_compat_contract_complete(entry.get("compat_contract"))
    ]
    closure_acceptance_packets = [
        entry.get("closure_acceptance")
        for entry in entries
        if isinstance(entry.get("closure_acceptance"), dict)
    ]
    closure_acceptance_by_requirement = {
        str(packet.get("requirement_id")): packet
        for packet in closure_acceptance_packets
        if packet.get("requirement_id")
    }
    closure_acceptance_matrix = {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_stack_requirement_closure_acceptance_matrix_v1",
        "generated_at": generated_at,
        "ok": len(closure_acceptance_packets) == len(entries) and all(self_awareness_stack_requirement_closure_acceptance_complete(packet) for packet in closure_acceptance_packets),
        "requirement_ids": sorted(closure_acceptance_by_requirement),
        "packets": closure_acceptance_packets,
        "packet_by_requirement": closure_acceptance_by_requirement,
        "summary": {
            "packets": len(closure_acceptance_packets),
            "complete": sum(1 for packet in closure_acceptance_packets if packet.get("complete") is True),
            "requirements": len(closure_acceptance_by_requirement),
            "compat_requirements": len({
                str(nested_get(packet, ["stack_compat_requirement", "requirement_id"]))
                for packet in closure_acceptance_packets
                if nested_get(packet, ["stack_compat_requirement", "requirement_id"])
            }),
        },
        "policy": {
            "handoff_only": True,
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "action_execution": False,
        },
    }
    blocked_coverage_planes = sorted({
        str(plane)
        for impact in coverage_impact_entries
        for plane in (impact.get("coverage_planes") if isinstance(impact.get("coverage_planes"), list) else [])
        if plane
    })
    verifier_commands = sorted({
        command
        for entry in entries
        for command in (entry.get("verifier_commands") if isinstance(entry.get("verifier_commands"), list) else [])
        if command
    })
    verifier_chain = [
        {"command": "abyss-machine self-awareness requirement-probes --json", "must": ["current checks and closure_readiness packets are present"]},
        {"command": "abyss-machine self-awareness stack-closure-dossier --json", "must": ["dossier entries match open stack handoff requirements and preserve dependency order"]},
        {"command": "abyss-machine self-awareness export --json", "must": ["portable export includes stack_closure_dossier artifact and top-level stack handoff"]},
        {"command": "abyss-machine self-awareness validate --json", "must": ["0 fails and 0 new warnings, including stack_closure_dossier_depth"]},
        {"command": "abyss-machine stack-bridge validate --json", "must": ["bridge exposes the dossier route without stack mutation"]},
        {"command": "abyss-machine self-awareness cycle --json", "must": ["full E2E cycle keeps dossier evidence and non-mutating response policy"]},
    ]
    probe_summary = requirement_probes_doc.get("summary") if isinstance(requirement_probes_doc.get("summary"), dict) else {}
    internal_contract_failures = probe_summary.get("internal_contract_failures") if isinstance(probe_summary.get("internal_contract_failures"), list) else []
    secret_leaks = safe_int(probe_summary.get("secret_leaks"), 0)
    mutating_routes = safe_int(probe_summary.get("mutating_routes"), 0)
    open_activation_gaps = safe_int(working_stack_activation_summary.get("open_activation_gaps"), len(working_stack_activation_entries))
    activation_complete = (
        working_stack_activation_dossier.get("schema") == f"{SCHEMA_PREFIX}_self_awareness_working_stack_activation_dossier_v1"
        and working_stack_activation_dossier.get("ok") is True
        and safe_int(working_stack_activation_summary.get("activation_entries_complete"), 0) == len(working_stack_activation_entries)
    )
    if open_entries and open_activation_gaps:
        dossier_status = "open_requirements_and_activation_gaps"
    elif open_entries:
        dossier_status = "open_requirements"
    elif open_activation_gaps:
        dossier_status = "open_activation_gaps"
    else:
        dossier_status = "satisfied"
    data = {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_stack_closure_dossier_v1",
        "version": VERSION,
        "generated_at": generated_at,
        "ok": not internal_contract_failures and secret_leaks == 0 and mutating_routes == 0 and all(entry.get("complete") for entry in entries) and activation_complete,
        "status": dossier_status,
        "summary": {
            "stack_owned_requirements": safe_int(nested_get(requirements_doc, ["summary", "stack_owned"]), len(requirements)),
            "probes": len(entries),
            "open_stack_requirements": len(open_entries),
            "closed_by_current_probe": len(closed_entries),
            "missing_checks": missing_check_total,
            "fulfilled_checks": fulfilled_check_total,
            "dependency_edges": len(dependency_edges),
            "reverse_dependency_edges": len(reverse_dependency_edges),
            "unblocking_requirements": len(unblocking_requirement_ids),
            "coverage_impact_entries": len(coverage_impact_entries),
            "compat_contract_entries": len(compat_contract_entries),
            "closure_acceptance_packets": len(closure_acceptance_packets),
            "closure_acceptance_packets_complete": sum(1 for packet in closure_acceptance_packets if packet.get("complete") is True),
            "stack_requirement_compat_requirements": safe_int(nested_get(closure_acceptance_matrix, ["summary", "compat_requirements"]), 0),
            "blocked_coverage_planes": blocked_coverage_planes,
            "runbook_candidates": sum(1 for entry in entries if isinstance(entry.get("runbook_candidate"), dict)),
            "acceptance_verifier_steps": sum(len(entry.get("acceptance_verifiers") if isinstance(entry.get("acceptance_verifiers"), list) else []) for entry in entries),
            "verifier_commands": len(verifier_commands),
            "dossier_entries_complete": sum(1 for entry in entries if entry.get("complete") is True),
            "internal_contract_failures": internal_contract_failures,
            "secret_leaks": secret_leaks,
            "mutating_routes": mutating_routes,
            "top_requirement_id": open_entries[0].get("requirement_id") if open_entries else None,
            "top_unblocking_requirement_id": unblocking_requirement_ids[0] if unblocking_requirement_ids else None,
            "working_stack_usage_gaps": safe_int(working_stack_activation_summary.get("working_stack_usage_gaps"), len(working_stack_activation_entries)),
            "working_stack_activation_entries": len(working_stack_activation_entries),
            "open_working_stack_activation_gaps": open_activation_gaps,
            "working_stack_activation_missing_checks": safe_int(working_stack_activation_summary.get("missing_checks"), 0),
            "working_stack_activation_fulfilled_checks": safe_int(working_stack_activation_summary.get("fulfilled_checks"), 0),
            "working_stack_activation_verifier_commands": safe_int(working_stack_activation_summary.get("verifier_commands"), 0),
            "working_stack_activation_entries_complete": safe_int(working_stack_activation_summary.get("activation_entries_complete"), 0),
            "working_stack_activation_synthetic_scenarios": safe_int(working_stack_activation_summary.get("synthetic_scenarios"), 0),
            "working_stack_activation_synthetic_scenarios_complete": safe_int(working_stack_activation_summary.get("synthetic_scenarios_complete"), 0),
            "working_stack_activation_closure_acceptance_packets": safe_int(working_stack_activation_summary.get("closure_acceptance_packets"), 0),
            "working_stack_activation_closure_acceptance_packets_complete": safe_int(working_stack_activation_summary.get("closure_acceptance_packets_complete"), 0),
            "working_stack_activation_compat_requirements": safe_int(working_stack_activation_summary.get("activation_compat_requirements"), 0),
            "working_stack_activation_coverage_planes": working_stack_activation_summary.get("coverage_planes") if isinstance(working_stack_activation_summary.get("coverage_planes"), list) else [],
            "top_working_stack_activation_service": working_stack_activation_summary.get("top_service"),
        },
        "dependency_graph": {
            "schema": f"{SCHEMA_PREFIX}_self_awareness_stack_closure_dependency_graph_v1",
            "ordered_requirement_ids": [entry["requirement_id"] for entry in entries],
            "open_requirement_ids": [entry["requirement_id"] for entry in open_entries],
            "closed_requirement_ids": [entry["requirement_id"] for entry in closed_entries],
            "edges": dependency_edges,
            "reverse_edges": reverse_dependency_edges,
            "dependency_root_requirement_ids": dependency_root_requirement_ids,
            "dependent_requirement_ids": dependent_requirement_ids,
            "unblocking_requirement_ids": unblocking_requirement_ids,
            "policy": {
                "dependency_order_is_handoff_guidance": True,
                "host_layer_mutates_stack": False,
                "executes_commands": False,
            },
        },
        "compat_contracts": {
            str(entry["requirement_id"]): entry.get("compat_contract")
            for entry in entries
            if entry.get("requirement_id") and isinstance(entry.get("compat_contract"), dict)
        },
        "stack_owner_handoff": {
            "schema": f"{SCHEMA_PREFIX}_self_awareness_stack_owner_handoff_dossier_v1",
            "owner": "abyss-stack",
            "open_requirement_ids": [entry["requirement_id"] for entry in open_entries],
            "closure_order": [
                {
                    "requirement_id": entry["requirement_id"],
                    "order": entry["order"],
                    "blocking_check_keys": entry.get("blocking_check_keys"),
                    "dependency_requirement_ids": entry.get("dependency_requirement_ids"),
                    "depends_on_requirement_ids": entry.get("depends_on_requirement_ids"),
                    "unblocks_requirement_ids": entry.get("unblocks_requirement_ids"),
                    "closure_acceptance_id": nested_get(entry, ["closure_acceptance", "acceptance_id"]),
                    "compat_requirement_id": nested_get(entry, ["closure_acceptance", "stack_compat_requirement", "requirement_id"]),
                    "safe_next_action": entry.get("safe_next_action"),
                    "runbook_candidate_id": nested_get(entry, ["runbook_candidate", "id"]),
                    "closure_acceptance": entry.get("closure_acceptance"),
                    "compat_contract": entry.get("compat_contract"),
                    "verifier_commands": entry.get("verifier_commands"),
                }
                for entry in open_entries
            ],
            "closure_acceptance_matrix": closure_acceptance_matrix,
            "closure_acceptance_packets": closure_acceptance_packets,
            "verifier_chain": verifier_chain,
            "policy": {
                "handoff_only": True,
                "read_only": True,
                "operator_approval_required_before_stack_mutation": True,
                "abyss_machine_executes_stack_change": False,
                "host_layer_mutates_stack": False,
            },
        },
        "working_stack_activation_dossier": working_stack_activation_dossier,
        "working_stack_activation_handoff": working_stack_activation_handoff,
        "working_stack_activation_entries": working_stack_activation_entries,
        "closure_acceptance_packets": closure_acceptance_packets,
        "closure_acceptance_matrix": closure_acceptance_matrix,
        "entries": entries,
        "open_requirements": open_entries,
        "closed_requirements": closed_entries,
        "verifier_commands": verifier_commands,
        "verifier_chain": verifier_chain,
        "artifact_refs": artifact_refs,
        "source_commands": [
            "abyss-machine self-awareness requirements --json",
            "abyss-machine self-awareness requirement-probes --json",
            "abyss-machine self-awareness stack-closure-dossier --json",
            "abyss-machine self-awareness export --json",
            "abyss-machine self-awareness validate --json",
            "abyss-machine stack-bridge validate --json",
            "abyss-machine self-awareness cycle --json",
        ],
        "policy": {
            "handoff_only": True,
            "read_only": True,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "executes_commands": False,
            "action_execution": False,
            "raw_secrets_included": False,
            "open_stack_requirements_are_blockers_not_host_failures": True,
            "stack_owner_may_mutate_stack_after_operator_approval": True,
        },
        "evidence_refs": [
            {"path": str(SELF_AWARENESS_REQUIREMENTS_LATEST_PATH), "schema": requirements_doc.get("schema")},
            {"path": str(SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH), "schema": requirement_probes_doc.get("schema")},
            {"path": str(SELF_AWARENESS_WORKING_STACK_LATEST_PATH), "schema": f"{SCHEMA_PREFIX}_self_awareness_working_stack_inventory_v1"},
        ],
        "tests": {
            "contract": "dossier preserves requirement probes, closure readiness, dependency order, runbooks, verifier commands, compat contracts, and no-mutation policy",
            "working_stack_activation": "every working-stack usage gap is an owner-routed activation entry with smoke/probe evidence, runbook candidate, verifier chain, and no stack mutation",
            "live": "abyss-machine self-awareness stack-closure-dossier --json is read-only and agrees with requirement-probes/latest.json plus working-stack/latest.json usage gaps",
        },
    }
    if write_latest:
        errors = write_latest_and_history(data, SELF_AWARENESS_STACK_CLOSURE_DOSSIER_LATEST_PATH, SELF_AWARENESS_STACK_CLOSURE_DOSSIER_ROOT)
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data

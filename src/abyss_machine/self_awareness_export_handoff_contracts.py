from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from . import self_awareness_contracts


DocumentBuilderPort = Callable[..., dict[str, Any]]
DocumentPredicatePort = Callable[[Any], bool]
DocumentTransformPort = Callable[..., Any]


@dataclass(frozen=True)
class ExportStackHandoffContractPort:
    activation_proof_overlay: DocumentTransformPort
    activation_proof_complete: DocumentPredicatePort
    stack_organ_use_packet_complete: DocumentPredicatePort
    activation_smoke_compact: DocumentBuilderPort
    activation_smoke_row_complete: DocumentPredicatePort
    coverage_impact_complete: DocumentPredicatePort
    coverage_impact: Callable[[str], dict[str, Any]]
    closure_acceptance_complete: DocumentPredicatePort


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def export_artifact_refs(
    exported: dict[str, Any],
    names: list[str],
) -> dict[str, Any]:
    refs: dict[str, Any] = {}
    for name in names:
        artifact = exported.get(name)
        if not isinstance(artifact, dict):
            continue
        refs[name] = {
            "path": artifact.get("path"),
            "history_path": artifact.get("history_path"),
            "schema": artifact.get("schema") or artifact.get("expected_schema"),
            "sha256": artifact.get("sha256"),
            "artifact_status": artifact.get("artifact_status"),
            "evidence_ref": artifact.get("evidence_ref"),
        }
    return refs


def export_stack_handoff(
    requirements_doc: dict[str, Any],
    requirement_probes_doc: dict[str, Any],
    exported: dict[str, Any],
    generated_at: str,
    stack_closure_dossier: dict[str, Any] | None = None,
    coverage_audit_doc: dict[str, Any] | None = None,
    activation_smoke_doc: dict[str, Any] | None = None,
    *,
    schema_prefix: str,
    version: str,
    contract_port: ExportStackHandoffContractPort,
) -> tuple[dict[str, Any], dict[str, Any]]:
    SCHEMA_PREFIX = schema_prefix
    VERSION = version
    nested_get = self_awareness_contracts.nested_get
    safe_int = _safe_int
    self_awareness_export_artifact_refs = export_artifact_refs
    self_awareness_export_overlay_working_stack_activation_proof = contract_port.activation_proof_overlay
    self_awareness_working_stack_activation_synthetic_proof_complete = contract_port.activation_proof_complete
    self_awareness_stack_organ_use_packet_complete = contract_port.stack_organ_use_packet_complete
    self_awareness_working_stack_activation_smoke_compact = contract_port.activation_smoke_compact
    self_awareness_working_stack_activation_smoke_row_complete = contract_port.activation_smoke_row_complete
    self_awareness_stack_coverage_impact_complete = contract_port.coverage_impact_complete
    self_awareness_stack_requirement_coverage_impact = contract_port.coverage_impact
    self_awareness_stack_requirement_closure_acceptance_complete = contract_port.closure_acceptance_complete
    stack_closure_dossier = stack_closure_dossier if isinstance(stack_closure_dossier, dict) else {}
    stack_owner_handoff = stack_closure_dossier.get("stack_owner_handoff") if isinstance(stack_closure_dossier.get("stack_owner_handoff"), dict) else {}
    dependency_graph = stack_closure_dossier.get("dependency_graph") if isinstance(stack_closure_dossier.get("dependency_graph"), dict) else {}
    dossier_summary = stack_closure_dossier.get("summary") if isinstance(stack_closure_dossier.get("summary"), dict) else {}
    working_stack_activation_dossier = stack_closure_dossier.get("working_stack_activation_dossier") if isinstance(stack_closure_dossier.get("working_stack_activation_dossier"), dict) else {}
    working_stack_activation_handoff = working_stack_activation_dossier.get("working_stack_activation_handoff") if isinstance(working_stack_activation_dossier.get("working_stack_activation_handoff"), dict) else stack_closure_dossier.get("working_stack_activation_handoff") if isinstance(stack_closure_dossier.get("working_stack_activation_handoff"), dict) else {}
    working_stack_activation_summary = working_stack_activation_dossier.get("summary") if isinstance(working_stack_activation_dossier.get("summary"), dict) else {}
    working_stack_activation_entries = working_stack_activation_dossier.get("entries") if isinstance(working_stack_activation_dossier.get("entries"), list) else []
    working_stack_activation_order = working_stack_activation_handoff.get("activation_order") if isinstance(working_stack_activation_handoff.get("activation_order"), list) else []
    working_stack_activation_service_ids = [
        str(item.get("service"))
        for item in working_stack_activation_entries
        if isinstance(item, dict) and item.get("service")
    ]
    working_stack_activation_entry_by_service = {
        str(item.get("service")): item
        for item in working_stack_activation_entries
        if isinstance(item, dict) and item.get("service")
    }
    dossier_entries = stack_closure_dossier.get("entries") if isinstance(stack_closure_dossier.get("entries"), list) else []
    dossier_entry_by_requirement = {
        str(item.get("requirement_id")): item
        for item in dossier_entries
        if isinstance(item, dict) and item.get("requirement_id")
    }
    dossier_closure_acceptance_matrix = stack_closure_dossier.get("closure_acceptance_matrix") if isinstance(stack_closure_dossier.get("closure_acceptance_matrix"), dict) else {}
    raw_closure_order = stack_owner_handoff.get("closure_order") if isinstance(stack_owner_handoff.get("closure_order"), list) else []
    closure_order = [
        {
            "requirement_id": item.get("requirement_id"),
            "order": item.get("order"),
            "blocking_check_keys": item.get("blocking_check_keys") if isinstance(item.get("blocking_check_keys"), list) else [],
            "depends_on_requirement_ids": item.get("depends_on_requirement_ids") if isinstance(item.get("depends_on_requirement_ids"), list) else [],
            "unblocks_requirement_ids": item.get("unblocks_requirement_ids") if isinstance(item.get("unblocks_requirement_ids"), list) else [],
            "runbook_candidate_id": item.get("runbook_candidate_id"),
            "closure_acceptance_id": item.get("closure_acceptance_id"),
            "compat_requirement_id": item.get("compat_requirement_id"),
            "safe_next_action": item.get("safe_next_action") if isinstance(item.get("safe_next_action"), dict) else {},
            "verifier_commands": item.get("verifier_commands") if isinstance(item.get("verifier_commands"), list) else [],
        }
        for item in raw_closure_order
        if isinstance(item, dict) and item.get("requirement_id")
    ]
    closure_order_ids = [str(item.get("requirement_id")) for item in closure_order if item.get("requirement_id")]
    dependency_graph_export = {
        "schema": dependency_graph.get("schema") or f"{SCHEMA_PREFIX}_self_awareness_export_stack_handoff_dependency_graph_v1",
        "ordered_requirement_ids": dependency_graph.get("ordered_requirement_ids") if isinstance(dependency_graph.get("ordered_requirement_ids"), list) else closure_order_ids,
        "open_requirement_ids": dependency_graph.get("open_requirement_ids") if isinstance(dependency_graph.get("open_requirement_ids"), list) else [],
        "closed_requirement_ids": dependency_graph.get("closed_requirement_ids") if isinstance(dependency_graph.get("closed_requirement_ids"), list) else [],
        "edges": dependency_graph.get("edges") if isinstance(dependency_graph.get("edges"), list) else [],
        "reverse_edges": dependency_graph.get("reverse_edges") if isinstance(dependency_graph.get("reverse_edges"), list) else [],
        "dependency_root_requirement_ids": dependency_graph.get("dependency_root_requirement_ids") if isinstance(dependency_graph.get("dependency_root_requirement_ids"), list) else [],
        "dependent_requirement_ids": dependency_graph.get("dependent_requirement_ids") if isinstance(dependency_graph.get("dependent_requirement_ids"), list) else [],
        "unblocking_requirement_ids": dependency_graph.get("unblocking_requirement_ids") if isinstance(dependency_graph.get("unblocking_requirement_ids"), list) else [],
        "policy": {
            "dependency_order_is_handoff_guidance": nested_get(dependency_graph, ["policy", "dependency_order_is_handoff_guidance"]) is not False,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
        },
    }
    requirement_rows = requirements_doc.get("requirements") if isinstance(requirements_doc.get("requirements"), list) else []
    stack_requirements = [
        item for item in requirement_rows
        if isinstance(item, dict) and item.get("owner") == "abyss-stack"
    ]
    requirement_by_id = {
        str(item.get("id")): item
        for item in stack_requirements
        if item.get("id")
    }
    handoff_rows = requirements_doc.get("stack_handoff") if isinstance(requirements_doc.get("stack_handoff"), list) else []
    handoff_by_id = {
        str(item.get("id") or item.get("requirement_id")): item
        for item in handoff_rows
        if isinstance(item, dict) and (item.get("id") or item.get("requirement_id"))
    }
    probe_rows = requirement_probes_doc.get("probes") if isinstance(requirement_probes_doc.get("probes"), list) else []
    probes = [
        probe for probe in probe_rows
        if isinstance(probe, dict) and (probe.get("id") or probe.get("requirement_id"))
    ]
    artifact_refs = self_awareness_export_artifact_refs(
        exported,
        ["requirements", "requirement_probes", "stack_closure_dossier", "working_stack", "capabilities", "failure_matrix", "coverage_audit", "activation_smoke", "cycle", "validate"],
    )
    coverage_audit_doc = coverage_audit_doc if isinstance(coverage_audit_doc, dict) else {}
    coverage_gap_rows = coverage_audit_doc.get("working_stack_gap_rows") if isinstance(coverage_audit_doc.get("working_stack_gap_rows"), list) else []
    working_stack_activation_synthetic_proofs = [
        self_awareness_export_overlay_working_stack_activation_proof(
            row.get("synthetic_proof"),
            working_stack_activation_entry_by_service,
            generated_at=generated_at,
        )
        for row in coverage_gap_rows
        if isinstance(row, dict) and isinstance(row.get("synthetic_proof"), dict)
    ]
    working_stack_activation_synthetic_proofs_complete = [
        proof for proof in working_stack_activation_synthetic_proofs
        if self_awareness_working_stack_activation_synthetic_proof_complete(proof)
    ]
    working_stack_activation_synthetic_proof_summary = {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_export_working_stack_activation_synthetic_proof_summary_v1",
        "coverage_audit_generated_at": coverage_audit_doc.get("generated_at"),
        "coverage_audit_ref": artifact_refs.get("coverage_audit"),
        "proofs": len(working_stack_activation_synthetic_proofs),
        "proofs_complete": len(working_stack_activation_synthetic_proofs_complete),
        "services": [
            str(proof.get("service"))
            for proof in working_stack_activation_synthetic_proofs
            if isinstance(proof, dict) and proof.get("service")
        ],
        "failed_services": [
            str(proof.get("service"))
            for proof in working_stack_activation_synthetic_proofs
            if isinstance(proof, dict) and not self_awareness_working_stack_activation_synthetic_proof_complete(proof)
        ],
        "policy": {
            "handoff_only": True,
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "actions_executed": False,
            "raw_private_content_included": False,
        },
    }
    working_stack_activation_synthetic_proofs_by_service = {
        str(proof.get("service")): proof
        for proof in working_stack_activation_synthetic_proofs
        if isinstance(proof, dict) and proof.get("service")
    }
    activation_smoke_doc = activation_smoke_doc if isinstance(activation_smoke_doc, dict) else {}
    activation_smoke_rows = activation_smoke_doc.get("rows") if isinstance(activation_smoke_doc.get("rows"), list) else []
    activation_smoke_by_service = activation_smoke_doc.get("by_service") if isinstance(activation_smoke_doc.get("by_service"), dict) else {}
    activation_smoke_compact_by_service = activation_smoke_doc.get("compact_by_service") if isinstance(activation_smoke_doc.get("compact_by_service"), dict) else {
        str(row.get("service")): self_awareness_working_stack_activation_smoke_compact(row)
        for row in activation_smoke_rows
        if isinstance(row, dict) and row.get("service")
    }
    stack_organ_use_packets = activation_smoke_doc.get("stack_organ_use_packets") if isinstance(activation_smoke_doc.get("stack_organ_use_packets"), list) else [
        row.get("stack_organ_use_packet")
        for row in activation_smoke_rows
        if isinstance(row, dict) and isinstance(row.get("stack_organ_use_packet"), dict)
    ]
    stack_organ_use_packets = [packet for packet in stack_organ_use_packets if isinstance(packet, dict)]
    stack_organ_use_packet_by_service = activation_smoke_doc.get("stack_organ_use_packet_by_service") if isinstance(activation_smoke_doc.get("stack_organ_use_packet_by_service"), dict) else {
        str(packet.get("service")): packet
        for packet in stack_organ_use_packets
        if packet.get("service")
    }
    stack_organ_use_packet_summary = {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_export_stack_organ_use_packet_summary_v1",
        "activation_smoke_generated_at": activation_smoke_doc.get("generated_at"),
        "activation_smoke_ref": artifact_refs.get("activation_smoke"),
        "packets": len(stack_organ_use_packets),
        "packets_complete": sum(1 for packet in stack_organ_use_packets if self_awareness_stack_organ_use_packet_complete(packet)),
        "services": [
            str(packet.get("service"))
            for packet in stack_organ_use_packets
            if packet.get("service")
        ],
        "classifications": sorted({
            str(nested_get(packet, ["activation_gap", "classification"]))
            for packet in stack_organ_use_packets
            if nested_get(packet, ["activation_gap", "classification"])
        }),
        "failed_services": [
            str(packet.get("service"))
            for packet in stack_organ_use_packets
            if packet.get("service") and not self_awareness_stack_organ_use_packet_complete(packet)
        ],
        "policy": {
            "handoff_only": True,
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "actions_executed": False,
            "raw_private_content_included": False,
        },
    }
    working_stack_activation_smoke_summary = {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_export_working_stack_activation_smoke_summary_v1",
        "activation_smoke_generated_at": activation_smoke_doc.get("generated_at"),
        "activation_smoke_ref": artifact_refs.get("activation_smoke"),
        "rows": len(activation_smoke_rows),
        "rows_complete": sum(1 for row in activation_smoke_rows if self_awareness_working_stack_activation_smoke_row_complete(row)),
        "services": [
            str(row.get("service"))
            for row in activation_smoke_rows
            if isinstance(row, dict) and row.get("service")
        ],
        "failed_services": [
            str(row.get("service"))
            for row in activation_smoke_rows
            if isinstance(row, dict) and not self_awareness_working_stack_activation_smoke_row_complete(row)
        ],
        "policy": {
            "handoff_only": True,
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "actions_executed": False,
            "raw_private_content_included": False,
        },
    }

    def first_export_dict(*values: Any) -> dict[str, Any]:
        for value in values:
            if isinstance(value, dict) and value:
                return value
        return {}

    def compact_runbook(runbook: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema": runbook.get("schema"),
            "id": runbook.get("id"),
            "requirement_id": runbook.get("requirement_id"),
            "status": runbook.get("status"),
            "machine_action": runbook.get("machine_action"),
            "source_command": runbook.get("source_command"),
            "host_layer_mutates_stack": runbook.get("host_layer_mutates_stack"),
            "machine_executes_stack_change": runbook.get("machine_executes_stack_change"),
            "stack_owner_may_mutate_stack": runbook.get("stack_owner_may_mutate_stack"),
            "operator_approval_required": runbook.get("operator_approval_required"),
            "proposed_stack_work": runbook.get("proposed_stack_work"),
            "acceptance_steps": runbook.get("acceptance_steps"),
            "acceptance_verifiers": runbook.get("acceptance_verifiers"),
            "risk": runbook.get("risk"),
            "blast_radius": runbook.get("blast_radius"),
            "rollback": runbook.get("rollback"),
            "evidence_refs": runbook.get("evidence_refs"),
            "policy": runbook.get("policy"),
        }

    entries: list[dict[str, Any]] = []
    for probe in probes:
        requirement_id = str(probe.get("id") or probe.get("requirement_id") or "")
        requirement = requirement_by_id.get(requirement_id, {})
        handoff = handoff_by_id.get(requirement_id, {})
        dossier_entry = dossier_entry_by_requirement.get(requirement_id, {})
        checks = probe.get("checks") if isinstance(probe.get("checks"), list) else []
        closure_blockers = [
            {
                "key": check.get("key"),
                "level": check.get("level"),
                "ok": check.get("ok"),
                "message": check.get("message"),
                "data": check.get("data"),
            }
            for check in checks
            if isinstance(check, dict)
            and (check.get("ok") is not True or str(check.get("level") or "").lower() in {"open", "warn", "fail"})
        ]
        ok_checks = sum(1 for check in checks if isinstance(check, dict) and check.get("ok") is True and check.get("level") == "ok")
        runbook = probe.get("runbook_candidate") if isinstance(probe.get("runbook_candidate"), dict) else {}
        acceptance_contract = first_export_dict(
            probe.get("acceptance_contract"),
            requirement.get("acceptance_contract"),
            handoff.get("acceptance_contract"),
        )
        machine_probe = first_export_dict(
            probe.get("machine_closure_probe"),
            acceptance_contract.get("probe_plan"),
            requirement.get("machine_closure_probe"),
            handoff.get("machine_closure_probe"),
        )
        acceptance_verifiers = (
            probe.get("acceptance_verifiers")
            if isinstance(probe.get("acceptance_verifiers"), list) and probe.get("acceptance_verifiers")
            else requirement.get("acceptance_verifiers")
            if isinstance(requirement.get("acceptance_verifiers"), list) and requirement.get("acceptance_verifiers")
            else handoff.get("acceptance_verifiers")
            if isinstance(handoff.get("acceptance_verifiers"), list) and handoff.get("acceptance_verifiers")
            else acceptance_contract.get("machine_verifiers")
            if isinstance(acceptance_contract.get("machine_verifiers"), list)
            else []
        )
        closure_readiness = probe.get("closure_readiness") if isinstance(probe.get("closure_readiness"), dict) else {}
        coverage_impact = first_export_dict(
            requirement.get("coverage_impact"),
            handoff.get("coverage_impact"),
            dossier_entry.get("coverage_impact") if isinstance(dossier_entry, dict) else {},
            closure_readiness.get("coverage_impact"),
        )
        if not self_awareness_stack_coverage_impact_complete(coverage_impact):
            coverage_impact = self_awareness_stack_requirement_coverage_impact(requirement_id)
        safe_next_action = first_export_dict(requirement.get("safe_next_action"), handoff.get("safe_next_action"), closure_readiness.get("safe_next_action"))
        current_state_digest = first_export_dict(requirement.get("current_state_digest"), handoff.get("current_state_digest"))
        if (
            current_state_digest.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_requirement_current_state_digest_v1"
            or nested_get(current_state_digest, ["policy", "raw_payloads_included"]) is not False
            or nested_get(current_state_digest, ["policy", "raw_secrets_included"]) is not False
        ):
            current_state = probe.get("current_state") if isinstance(probe.get("current_state"), dict) else {}
            evidence_refs = probe.get("evidence_refs") if isinstance(probe.get("evidence_refs"), list) else []
            current_state_digest = {
                "schema": f"{SCHEMA_PREFIX}_self_awareness_requirement_current_state_digest_v1",
                "has_current_state": bool(current_state),
                "keys": sorted(str(key) for key in current_state.keys())[:80],
                "evidence_refs": len(evidence_refs),
                "policy": {
                    "raw_payloads_included": False,
                    "raw_secrets_included": False,
                    "host_layer_mutates_stack": False,
                },
            }
        closure_acceptance = first_export_dict(
            dossier_entry.get("closure_acceptance") if isinstance(dossier_entry, dict) else {},
            requirement.get("closure_acceptance"),
            handoff.get("closure_acceptance"),
        )
        handoff_contract_complete = bool(
            requirement.get("handoff_contract_complete") is True
            or handoff.get("handoff_contract_complete") is True
            or (
                isinstance(acceptance_contract, dict)
                and bool(acceptance_contract)
                and bool(machine_probe)
                and bool(acceptance_verifiers)
                and self_awareness_stack_coverage_impact_complete(coverage_impact)
                and current_state_digest.get("schema") == f"{SCHEMA_PREFIX}_self_awareness_requirement_current_state_digest_v1"
                and nested_get(current_state_digest, ["policy", "raw_payloads_included"]) is False
                and nested_get(current_state_digest, ["policy", "raw_secrets_included"]) is False
            )
        )
        entry = {
            "id": requirement_id,
            "title": requirement.get("title") or requirement_id,
            "owner": probe.get("owner") or requirement.get("owner") or "abyss-stack",
            "status": probe.get("status"),
            "closed_by_current_probe": probe.get("closed_by_current_probe"),
            "probe_kind": probe.get("probe_kind"),
            "source_handoff_command": probe.get("source_handoff_command"),
            "machine_read_command": probe.get("machine_read_command"),
            "current_state": probe.get("current_state"),
            "closure_blockers": closure_blockers,
            "open_check_count": len(closure_blockers),
            "ok_check_count": ok_checks,
            "closure_readiness": closure_readiness,
            "expected_shape": requirement.get("expected_shape") or handoff.get("expected_shape"),
            "machine_closure_probe": {
                "kind": machine_probe.get("kind"),
                "candidate_routes": machine_probe.get("candidate_routes"),
                "required_fields": machine_probe.get("required_fields"),
                "success_predicates": machine_probe.get("success_predicates"),
                "redaction_rules": machine_probe.get("redaction_rules"),
                "boundedness": machine_probe.get("boundedness"),
            },
            "acceptance_contract": acceptance_contract,
            "acceptance_verifiers": acceptance_verifiers,
            "closure_semantics": probe.get("closure_semantics") if isinstance(probe.get("closure_semantics"), dict) else {},
            "required_fields": probe.get("required_fields") if isinstance(probe.get("required_fields"), list) else [],
            "success_predicates": probe.get("success_predicates") if isinstance(probe.get("success_predicates"), list) else [],
            "redaction_rules": probe.get("redaction_rules") if isinstance(probe.get("redaction_rules"), list) else [],
            "must_not": probe.get("must_not") if isinstance(probe.get("must_not"), list) else [],
            "evidence_refs": probe.get("evidence_refs"),
            "compat_contract": first_export_dict(requirement.get("compat_contract"), handoff.get("compat_contract")),
            "closure_acceptance": closure_acceptance,
            "coverage_impact": coverage_impact,
            "safe_next_action": safe_next_action,
            "current_state_digest": current_state_digest,
            "handoff_contract_complete": handoff_contract_complete,
            "runbook_candidate": compact_runbook(runbook) if runbook else None,
        }
        entries.append(entry)

    open_entries = [entry for entry in entries if entry.get("closed_by_current_probe") is not True]
    closed_entries = [entry for entry in entries if entry.get("closed_by_current_probe") is True]
    stack_requirement_closure_acceptance_packets = [
        entry.get("closure_acceptance")
        for entry in entries
        if isinstance(entry.get("closure_acceptance"), dict)
    ]
    stack_requirement_closure_acceptance_packets_by_requirement = {
        str(packet.get("requirement_id")): packet
        for packet in stack_requirement_closure_acceptance_packets
        if packet.get("requirement_id")
    }
    stack_requirement_closure_acceptance_summary = {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_export_stack_requirement_closure_acceptance_summary_v1",
        "stack_closure_dossier_generated_at": stack_closure_dossier.get("generated_at"),
        "packets": len(stack_requirement_closure_acceptance_packets),
        "packets_complete": sum(1 for packet in stack_requirement_closure_acceptance_packets if self_awareness_stack_requirement_closure_acceptance_complete(packet)),
        "requirements": len(stack_requirement_closure_acceptance_packets_by_requirement),
        "compat_requirements": len({
            str(nested_get(packet, ["stack_compat_requirement", "requirement_id"]))
            for packet in stack_requirement_closure_acceptance_packets
            if nested_get(packet, ["stack_compat_requirement", "requirement_id"])
        }),
        "matrix_ok": dossier_closure_acceptance_matrix.get("ok") is True,
        "policy": {
            "handoff_only": True,
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "actions_executed": False,
        },
    }
    stack_handoff_coverage_impacts = [
        {
            "schema": impact.get("schema"),
            "requirement_id": entry.get("id"),
            "organ": impact.get("organ"),
            "coverage_planes": impact.get("coverage_planes") if isinstance(impact.get("coverage_planes"), list) else [],
            "affected_stack_surfaces": impact.get("affected_stack_surfaces") if isinstance(impact.get("affected_stack_surfaces"), list) else [],
            "affected_machine_surfaces": impact.get("affected_machine_surfaces") if isinstance(impact.get("affected_machine_surfaces"), list) else [],
            "blocks_stack_usage_requirements": (
                impact.get("blocks_stack_usage_requirements")
                if isinstance(impact.get("blocks_stack_usage_requirements"), list)
                else []
            ),
            "closure_value": impact.get("closure_value"),
            "proof_commands": impact.get("proof_commands") if isinstance(impact.get("proof_commands"), list) else [],
            "policy": impact.get("policy") if isinstance(impact.get("policy"), dict) else {},
        }
        for entry in open_entries
        for impact in [entry.get("coverage_impact") if isinstance(entry.get("coverage_impact"), dict) else {}]
        if impact
    ]
    stack_handoff_coverage_impacts_by_requirement = {
        str(impact.get("requirement_id")): impact
        for impact in stack_handoff_coverage_impacts
        if impact.get("requirement_id")
    }
    stack_handoff_blocked_coverage_planes = sorted({
        str(plane)
        for impact in stack_handoff_coverage_impacts
        for plane in (impact.get("coverage_planes") if isinstance(impact.get("coverage_planes"), list) else [])
        if plane
    })
    stack_owner_verifier_matrix: list[dict[str, Any]] = []
    for entry in open_entries:
        requirement_id = str(entry.get("id") or "")
        closure_readiness = entry.get("closure_readiness") if isinstance(entry.get("closure_readiness"), dict) else {}
        compat_contract = entry.get("compat_contract") if isinstance(entry.get("compat_contract"), dict) else {}
        acceptance_contract = entry.get("acceptance_contract") if isinstance(entry.get("acceptance_contract"), dict) else {}
        coverage_impact = entry.get("coverage_impact") if isinstance(entry.get("coverage_impact"), dict) else {}
        post_close_verifiers = nested_get(compat_contract, ["machine_consumer_contract", "post_close_verifiers"])
        if not isinstance(post_close_verifiers, list):
            post_close_verifiers = acceptance_contract.get("machine_verifiers") if isinstance(acceptance_contract.get("machine_verifiers"), list) else []
        blocking_check_keys = closure_readiness.get("blocking_check_keys") if isinstance(closure_readiness.get("blocking_check_keys"), list) else [
            str(item.get("key"))
            for item in (entry.get("closure_blockers") if isinstance(entry.get("closure_blockers"), list) else [])
            if isinstance(item, dict) and item.get("key")
        ]
        verifier_commands = closure_readiness.get("verifier_commands") if isinstance(closure_readiness.get("verifier_commands"), list) else []
        stack_owner_verifier_matrix.append({
            "schema": f"{SCHEMA_PREFIX}_self_awareness_export_stack_owner_verifier_v1",
            "requirement_id": requirement_id,
            "owner": entry.get("owner") or "abyss-stack",
            "status": entry.get("status"),
            "closure_order": closure_order_ids.index(requirement_id) + 1 if requirement_id in closure_order_ids else None,
            "blocking_check_keys": blocking_check_keys,
            "missing_checks": closure_readiness.get("missing_checks") if isinstance(closure_readiness.get("missing_checks"), list) else entry.get("closure_blockers") if isinstance(entry.get("closure_blockers"), list) else [],
            "closure_evidence_needed": closure_readiness.get("closure_evidence_needed") if isinstance(closure_readiness.get("closure_evidence_needed"), list) else [],
            "verifier_commands": verifier_commands,
            "acceptance_verifiers": entry.get("acceptance_verifiers") if isinstance(entry.get("acceptance_verifiers"), list) else [],
            "post_close_verifiers": post_close_verifiers,
            "runbook_candidate_id": nested_get(entry, ["runbook_candidate", "id"]),
            "safe_next_action": entry.get("safe_next_action") if isinstance(entry.get("safe_next_action"), dict) else {},
            "coverage_planes": coverage_impact.get("coverage_planes") if isinstance(coverage_impact.get("coverage_planes"), list) else [],
            "coverage_impact": coverage_impact,
            "current_state_digest": entry.get("current_state_digest") if isinstance(entry.get("current_state_digest"), dict) else {},
            "evidence_refs": entry.get("evidence_refs") if isinstance(entry.get("evidence_refs"), list) else [],
            "policy": {
                "handoff_only": True,
                "host_layer_mutates_stack": False,
                "executes_commands": False,
                "actions_executed": False,
                "raw_secrets_included": False,
                "stack_owner_may_mutate_stack_after_operator_approval": True,
            },
        })
    stack_owner_verifier_matrix_by_requirement = {
        str(item.get("requirement_id")): item
        for item in stack_owner_verifier_matrix
        if item.get("requirement_id")
    }
    probe_summary = requirement_probes_doc.get("summary") if isinstance(requirement_probes_doc.get("summary"), dict) else {}
    requirements_summary = requirements_doc.get("summary") if isinstance(requirements_doc.get("summary"), dict) else {}
    internal_contract_failures = probe_summary.get("internal_contract_failures")
    if not isinstance(internal_contract_failures, list):
        internal_contract_failures = []
    secret_leaks = safe_int(probe_summary.get("secret_leaks"), 0)
    mutating_routes = safe_int(probe_summary.get("mutating_routes"), 0)
    verifier_steps = sum(
        len(entry.get("acceptance_verifiers") if isinstance(entry.get("acceptance_verifiers"), list) else [])
        for entry in entries
    )
    verifier_entry_count = sum(1 for entry in entries if isinstance(entry.get("acceptance_verifiers"), list) and entry.get("acceptance_verifiers"))
    coverage_impact_count = sum(1 for entry in entries if self_awareness_stack_coverage_impact_complete(entry.get("coverage_impact")))
    safe_next_action_count = sum(1 for entry in entries if isinstance(entry.get("safe_next_action"), dict) and entry.get("safe_next_action"))
    runbook_count = sum(1 for entry in entries if isinstance(entry.get("runbook_candidate"), dict))
    closure_readiness_entries = [entry.get("closure_readiness") for entry in entries if isinstance(entry.get("closure_readiness"), dict)]
    closure_readiness_missing = sum(
        safe_int(packet.get("open_blocker_count"), 0)
        for packet in closure_readiness_entries
        if isinstance(packet, dict)
    )
    closure_readiness_dependency_edges = sum(
        len(packet.get("dependency_requirement_ids") if isinstance(packet.get("dependency_requirement_ids"), list) else [])
        for packet in closure_readiness_entries
        if isinstance(packet, dict)
    )
    requirements_export = {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_export_requirements_summary_v1",
        "version": VERSION,
        "generated_at": generated_at,
        "ok": bool(requirements_doc.get("ok", True)) and bool(requirement_probes_doc.get("ok", True)),
        "status": requirement_probes_doc.get("status") or requirements_doc.get("status"),
        "summary": {
            "requirements": requirements_summary.get("requirements", len(requirement_rows)),
            "by_owner": requirements_summary.get("by_owner") or {},
            "stack_owned": len(stack_requirements),
            "machine_owned": requirements_summary.get("machine_owned", 0),
            "stack_handoff_acceptance_contracts": requirements_summary.get("stack_handoff_acceptance_contracts", len(handoff_rows)),
            "open_stack_requirements": len(open_entries),
            "closed_by_current_probe": len(closed_entries),
            "runbook_candidates": runbook_count,
            "stack_handoff_acceptance_verifiers": verifier_entry_count,
            "acceptance_verifier_steps": verifier_steps,
            "stack_handoff_coverage_impact_entries": coverage_impact_count,
            "stack_handoff_safe_next_actions": safe_next_action_count,
            "closure_readiness_packets": len(closure_readiness_entries),
            "closure_readiness_missing_checks": closure_readiness_missing,
            "stack_requirement_closure_acceptance_packets": len(stack_requirement_closure_acceptance_packets),
            "stack_requirement_closure_acceptance_packets_complete": stack_requirement_closure_acceptance_summary["packets_complete"],
            "stack_requirement_compat_requirements": stack_requirement_closure_acceptance_summary["compat_requirements"],
            "working_stack_activation_gaps": safe_int(working_stack_activation_summary.get("open_activation_gaps"), len(working_stack_activation_entries)),
            "working_stack_activation_entries": len(working_stack_activation_entries),
            "working_stack_activation_missing_checks": safe_int(working_stack_activation_summary.get("missing_checks"), 0),
            "working_stack_activation_verifier_commands": safe_int(working_stack_activation_summary.get("verifier_commands"), 0),
            "working_stack_activation_synthetic_scenarios": safe_int(working_stack_activation_summary.get("synthetic_scenarios"), len(working_stack_activation_entries)),
            "working_stack_activation_synthetic_scenarios_complete": safe_int(working_stack_activation_summary.get("synthetic_scenarios_complete"), len(working_stack_activation_entries)),
            "working_stack_activation_closure_acceptance_packets": safe_int(working_stack_activation_summary.get("closure_acceptance_packets"), len(working_stack_activation_entries)),
            "working_stack_activation_closure_acceptance_packets_complete": safe_int(working_stack_activation_summary.get("closure_acceptance_packets_complete"), len(working_stack_activation_entries)),
            "working_stack_activation_compat_requirements": safe_int(working_stack_activation_summary.get("activation_compat_requirements"), len(working_stack_activation_entries)),
            "working_stack_activation_synthetic_proofs": len(working_stack_activation_synthetic_proofs),
            "working_stack_activation_synthetic_proofs_complete": len(working_stack_activation_synthetic_proofs_complete),
            "working_stack_activation_smoke_rows": len(activation_smoke_rows),
            "working_stack_activation_smoke_rows_complete": working_stack_activation_smoke_summary.get("rows_complete"),
            "stack_organ_use_packets": stack_organ_use_packet_summary["packets"],
            "stack_organ_use_packets_complete": stack_organ_use_packet_summary["packets_complete"],
        },
        "open_stack_ids": [entry["id"] for entry in open_entries],
        "open_stack_requirement_ids": [entry["id"] for entry in open_entries],
        "closed_stack_ids": [entry["id"] for entry in closed_entries],
        "stack_handoff_count": len(handoff_rows),
        "source_commands": [
            "abyss-machine self-awareness requirements --json",
            "abyss-machine self-awareness requirement-probes --json",
            "abyss-machine self-awareness cycle --json",
            "abyss-machine self-awareness validate --json",
            "abyss-machine stack-bridge validate --json",
        ],
        "artifact_refs": artifact_refs,
        "policy": {
            "requirements_are_not_stack_mutations": True,
            "host_layer_mutates_stack": False,
            "open_stack_requirements_are_blockers_not_host_failures": True,
            "handoff_only": True,
        },
    }
    stack_handoff_export = {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_export_stack_handoff_v1",
        "version": VERSION,
        "generated_at": generated_at,
        "ok": bool(requirements_export.get("ok")) and not internal_contract_failures and secret_leaks == 0 and mutating_routes == 0,
        "status": "open_requirements" if open_entries else "satisfied",
        "summary": {
            "stack_owned_requirements": len(stack_requirements),
            "stack_handoff": len(handoff_rows),
            "open": len(open_entries),
            "closed_by_current_probe": len(closed_entries),
            "runbook_candidates": runbook_count,
            "machine_closure_probes": sum(1 for entry in entries if isinstance(entry.get("machine_closure_probe"), dict)),
            "acceptance_verifier_steps": verifier_steps,
            "closure_readiness_packets": len(closure_readiness_entries),
            "closure_readiness_missing_checks": closure_readiness_missing,
            "closure_readiness_dependency_edges": closure_readiness_dependency_edges,
            "stack_requirement_closure_acceptance_packets": len(stack_requirement_closure_acceptance_packets),
            "stack_requirement_closure_acceptance_packets_complete": stack_requirement_closure_acceptance_summary["packets_complete"],
            "stack_requirement_compat_requirements": stack_requirement_closure_acceptance_summary["compat_requirements"],
            "closure_order_entries": len(closure_order),
            "coverage_impact_entries": len(stack_handoff_coverage_impacts),
            "blocked_coverage_planes": stack_handoff_blocked_coverage_planes,
            "stack_owner_verifier_matrix_entries": len(stack_owner_verifier_matrix),
            "stack_owner_verifier_commands": sum(len(item.get("verifier_commands") if isinstance(item.get("verifier_commands"), list) else []) for item in stack_owner_verifier_matrix),
            "stack_owner_post_close_verifiers": sum(len(item.get("post_close_verifiers") if isinstance(item.get("post_close_verifiers"), list) else []) for item in stack_owner_verifier_matrix),
            "working_stack_activation_gaps": safe_int(working_stack_activation_summary.get("open_activation_gaps"), len(working_stack_activation_entries)),
            "working_stack_activation_entries": len(working_stack_activation_entries),
            "working_stack_activation_missing_checks": safe_int(working_stack_activation_summary.get("missing_checks"), 0),
            "working_stack_activation_fulfilled_checks": safe_int(working_stack_activation_summary.get("fulfilled_checks"), 0),
            "working_stack_activation_verifier_commands": safe_int(working_stack_activation_summary.get("verifier_commands"), 0),
            "working_stack_activation_synthetic_scenarios": safe_int(working_stack_activation_summary.get("synthetic_scenarios"), len(working_stack_activation_entries)),
            "working_stack_activation_synthetic_scenarios_complete": safe_int(working_stack_activation_summary.get("synthetic_scenarios_complete"), len(working_stack_activation_entries)),
            "working_stack_activation_closure_acceptance_packets": safe_int(working_stack_activation_summary.get("closure_acceptance_packets"), len(working_stack_activation_entries)),
            "working_stack_activation_closure_acceptance_packets_complete": safe_int(working_stack_activation_summary.get("closure_acceptance_packets_complete"), len(working_stack_activation_entries)),
            "working_stack_activation_compat_requirements": safe_int(working_stack_activation_summary.get("activation_compat_requirements"), len(working_stack_activation_entries)),
            "working_stack_activation_synthetic_proofs": len(working_stack_activation_synthetic_proofs),
            "working_stack_activation_synthetic_proofs_complete": len(working_stack_activation_synthetic_proofs_complete),
            "working_stack_activation_smoke_rows": len(activation_smoke_rows),
            "working_stack_activation_smoke_rows_complete": working_stack_activation_smoke_summary.get("rows_complete"),
            "working_stack_activation_smoke_failed_services": working_stack_activation_smoke_summary.get("failed_services"),
            "stack_organ_use_packets": stack_organ_use_packet_summary["packets"],
            "stack_organ_use_packets_complete": stack_organ_use_packet_summary["packets_complete"],
            "stack_organ_use_packet_failed_services": stack_organ_use_packet_summary["failed_services"],
            "stack_organ_use_packet_classifications": stack_organ_use_packet_summary["classifications"],
            "working_stack_activation_coverage_planes": working_stack_activation_summary.get("coverage_planes") if isinstance(working_stack_activation_summary.get("coverage_planes"), list) else [],
            "top_working_stack_activation_service": working_stack_activation_summary.get("top_service"),
            "top_requirement_id": dossier_summary.get("top_requirement_id") or (closure_order_ids[0] if closure_order_ids else None),
            "top_unblocking_requirement_id": dossier_summary.get("top_unblocking_requirement_id"),
            "internal_contract_failures": internal_contract_failures,
            "secret_leaks": secret_leaks,
            "mutating_routes": mutating_routes,
        },
        "open_requirement_ids": [entry["id"] for entry in open_entries],
        "closed_requirement_ids": [entry["id"] for entry in closed_entries],
        "ordered_requirement_ids": closure_order_ids,
        "closure_order": closure_order,
        "dependency_graph": dependency_graph_export,
        "stack_owner_handoff": {
            "schema": stack_owner_handoff.get("schema") or f"{SCHEMA_PREFIX}_self_awareness_export_stack_owner_handoff_v1",
            "owner": stack_owner_handoff.get("owner") or "abyss-stack",
            "open_requirement_ids": stack_owner_handoff.get("open_requirement_ids") if isinstance(stack_owner_handoff.get("open_requirement_ids"), list) else [entry["id"] for entry in open_entries],
            "closure_order_ids": closure_order_ids,
            "top_requirement_id": dossier_summary.get("top_requirement_id") or (closure_order_ids[0] if closure_order_ids else None),
            "top_unblocking_requirement_id": dossier_summary.get("top_unblocking_requirement_id"),
            "blocked_coverage_planes": stack_handoff_blocked_coverage_planes,
            "coverage_impacts_by_requirement": stack_handoff_coverage_impacts_by_requirement,
            "verifier_matrix": stack_owner_verifier_matrix,
            "verifier_matrix_by_requirement": stack_owner_verifier_matrix_by_requirement,
            "closure_acceptance_summary": stack_requirement_closure_acceptance_summary,
            "closure_acceptance_packets_by_requirement": stack_requirement_closure_acceptance_packets_by_requirement,
            "policy": {
                "handoff_only": True,
                "abyss_machine_executes_stack_change": False,
                "host_layer_mutates_stack": False,
                "executes_commands": False,
                "actions_executed": False,
            },
        },
        "working_stack_activation_dossier": working_stack_activation_dossier,
        "working_stack_activation_handoff": {
            "schema": working_stack_activation_handoff.get("schema") or f"{SCHEMA_PREFIX}_self_awareness_export_working_stack_activation_handoff_v1",
            "owner": working_stack_activation_handoff.get("owner") or "abyss-stack",
            "open_service_ids": working_stack_activation_handoff.get("open_service_ids") if isinstance(working_stack_activation_handoff.get("open_service_ids"), list) else working_stack_activation_service_ids,
            "activation_order": working_stack_activation_order,
            "top_service": working_stack_activation_summary.get("top_service") or (working_stack_activation_service_ids[0] if working_stack_activation_service_ids else None),
            "verifier_chain": working_stack_activation_handoff.get("verifier_chain") if isinstance(working_stack_activation_handoff.get("verifier_chain"), list) else [],
            "policy": {
                "handoff_only": True,
                "abyss_machine_executes_stack_change": False,
                "host_layer_mutates_stack": False,
                "executes_commands": False,
                "actions_executed": False,
                "operator_approval_required_before_stack_mutation": True,
            },
        },
        "working_stack_activation_entries": working_stack_activation_entries,
        "working_stack_activation_service_ids": working_stack_activation_service_ids,
        "working_stack_activation_synthetic_proof_summary": working_stack_activation_synthetic_proof_summary,
        "working_stack_activation_synthetic_proofs": working_stack_activation_synthetic_proofs,
        "working_stack_activation_synthetic_proofs_by_service": working_stack_activation_synthetic_proofs_by_service,
        "working_stack_activation_smoke_summary": working_stack_activation_smoke_summary,
        "working_stack_activation_smoke_rows": activation_smoke_rows,
        "working_stack_activation_smoke_by_service": activation_smoke_by_service,
        "working_stack_activation_smoke_compact_by_service": activation_smoke_compact_by_service,
        "stack_organ_use_packet_summary": stack_organ_use_packet_summary,
        "stack_organ_use_packets": stack_organ_use_packets,
        "stack_organ_use_packet_by_service": stack_organ_use_packet_by_service,
        "stack_requirement_closure_acceptance_summary": stack_requirement_closure_acceptance_summary,
        "stack_requirement_closure_acceptance_packets": stack_requirement_closure_acceptance_packets,
        "stack_requirement_closure_acceptance_packets_by_requirement": stack_requirement_closure_acceptance_packets_by_requirement,
        "stack_requirement_closure_acceptance_matrix": dossier_closure_acceptance_matrix,
        "closure_readiness": closure_readiness_entries,
        "open_requirements": open_entries,
        "closed_requirements": closed_entries,
        "blocked_coverage_planes": stack_handoff_blocked_coverage_planes,
        "coverage_impacts": stack_handoff_coverage_impacts,
        "coverage_impacts_by_requirement": stack_handoff_coverage_impacts_by_requirement,
        "stack_owner_verifier_matrix": stack_owner_verifier_matrix,
        "stack_owner_verifier_matrix_by_requirement": stack_owner_verifier_matrix_by_requirement,
        "coverage_audit_ref": artifact_refs.get("coverage_audit"),
        "artifact_refs": artifact_refs,
        "source_commands": requirements_export["source_commands"],
        "evidence_refs": [
            {"path": ref.get("path"), "schema": ref.get("schema"), "sha256": ref.get("sha256")}
            for ref in artifact_refs.values()
            if isinstance(ref, dict) and ref.get("path")
        ],
        "policy": {
            "handoff_only": True,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "actions_executed": False,
            "runbook_candidates_are_handoff_only": True,
            "stack_owner_may_mutate_stack_after_operator_approval": True,
            "raw_secrets_included": False,
            "open_stack_requirements_are_blockers_not_host_failures": True,
            "working_stack_activation_gaps_are_blockers_not_host_failures": True,
        },
    }
    return requirements_export, stack_handoff_export

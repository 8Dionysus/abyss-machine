from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import self_awareness_contracts


DocumentPort = Callable[..., Any]


@dataclass(frozen=True)
class SelfAwarenessAutolinkPaths:
    working_stack_latest: Path
    coverage_audit_latest: Path
    stack_closure_dossier_latest: Path
    activation_smoke_latest: Path
    episodes_latest: Path
    autolink_latest: Path
    autolink_root: Path


@dataclass(frozen=True)
class SelfAwarenessAutolinkConfig:
    schema_prefix: str
    version: str


@dataclass(frozen=True)
class SelfAwarenessAutolinkRuntimePort:
    load_latest_json: DocumentPort
    now_iso: DocumentPort
    write_latest_and_history: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessAutolinkRefreshPort:
    working_stack_inventory: DocumentPort
    dependent_readmodels: DocumentPort
    objective_coverage_audit: DocumentPort
    stack_closure_dossier: DocumentPort
    activation_smoke: DocumentPort
    episodes: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessAutolinkContractPort:
    working_stack_links_match_stable_identity: DocumentPort
    link_integrity_matrix_complete: DocumentPort
    link_integrity_matches_working_stack: DocumentPort
    activation_entries_from_link_rows: DocumentPort
    activation_entries_cover_expected: DocumentPort
    activation_smoke_needs_refresh: DocumentPort
    episodes_cover_stack_requirements: DocumentPort
    autolink_document: DocumentPort
    activation_smoke_compact: DocumentPort
    stack_requirement_closure_acceptance_complete: DocumentPort
    stack_coverage_impact_complete: DocumentPort


def autolink(
    write_latest: bool = True,
    *,
    cycle_id: str | None = None,
    probe_run_id: str | None = None,
    working_stack_doc: dict[str, Any] | None = None,
    coverage_audit_doc: dict[str, Any] | None = None,
    stack_closure_dossier_doc: dict[str, Any] | None = None,
    activation_smoke_doc: dict[str, Any] | None = None,
    paths: SelfAwarenessAutolinkPaths,
    config: SelfAwarenessAutolinkConfig,
    runtime_port: SelfAwarenessAutolinkRuntimePort,
    refresh_port: SelfAwarenessAutolinkRefreshPort,
    contract_port: SelfAwarenessAutolinkContractPort,
) -> dict[str, Any]:
    generated_at = runtime_port.now_iso()
    dependency_refresh: dict[str, Any] = {}
    working_stack_schema = (
        f"{config.schema_prefix}_self_awareness_working_stack_inventory_v1"
    )
    coverage_schema = (
        f"{config.schema_prefix}_self_awareness_objective_coverage_audit_v1"
    )
    dossier_schema = (
        f"{config.schema_prefix}_self_awareness_stack_closure_dossier_v1"
    )
    activation_smoke_schema = (
        f"{config.schema_prefix}_self_awareness_working_stack_activation_smoke_v1"
    )
    episodes_schema = f"{config.schema_prefix}_self_awareness_episodes_v1"
    autolink_schema = f"{config.schema_prefix}_self_awareness_autolink_v1"

    working_stack_doc = (
        working_stack_doc
        if isinstance(working_stack_doc, dict)
        else runtime_port.load_latest_json(
            paths.working_stack_latest, working_stack_schema
        )
    )
    if (
        working_stack_doc.get("schema") != working_stack_schema
        or not contract_port.working_stack_links_match_stable_identity(
            working_stack_doc
        )
    ):
        working_stack_doc = refresh_port.working_stack_inventory(write_latest=True)
        dependency_refresh = refresh_port.dependent_readmodels(
            working_stack_doc=working_stack_doc
        )
        working_stack_doc = runtime_port.load_latest_json(
            paths.working_stack_latest, working_stack_schema
        )

    coverage_audit_doc = (
        coverage_audit_doc
        if isinstance(coverage_audit_doc, dict)
        else runtime_port.load_latest_json(paths.coverage_audit_latest, coverage_schema)
    )
    link_integrity = (
        coverage_audit_doc.get("working_stack_link_integrity")
        if isinstance(
            coverage_audit_doc.get("working_stack_link_integrity"), dict
        )
        else {}
    )
    if (
        not contract_port.link_integrity_matrix_complete(link_integrity)
        or not contract_port.link_integrity_matches_working_stack(
            working_stack_doc, link_integrity
        )
    ):
        if not dependency_refresh:
            dependency_refresh = refresh_port.dependent_readmodels(
                working_stack_doc=working_stack_doc
            )
            working_stack_doc = runtime_port.load_latest_json(
                paths.working_stack_latest, working_stack_schema
            )
        coverage_audit_doc = refresh_port.objective_coverage_audit(
            write_latest=True,
            working_stack_doc=working_stack_doc,
            stack_closure_dossier_doc=stack_closure_dossier_doc,
        )
        link_integrity = (
            coverage_audit_doc.get("working_stack_link_integrity")
            if isinstance(
                coverage_audit_doc.get("working_stack_link_integrity"), dict
            )
            else {}
        )

    link_rows = (
        link_integrity.get("rows")
        if isinstance(link_integrity.get("rows"), list)
        else []
    )
    current_activation_entries = (
        contract_port.activation_entries_from_link_rows(link_rows)
    )
    stack_closure_dossier_doc = (
        stack_closure_dossier_doc
        if isinstance(stack_closure_dossier_doc, dict)
        else runtime_port.load_latest_json(
            paths.stack_closure_dossier_latest, dossier_schema
        )
    )
    if stack_closure_dossier_doc.get("schema") != dossier_schema:
        stack_closure_dossier_doc = refresh_port.stack_closure_dossier(
            write_latest=True, working_stack_doc=working_stack_doc
        )
    activation_entries = self_awareness_contracts.nested_get(
        stack_closure_dossier_doc, ["working_stack_activation_dossier", "entries"]
    )
    activation_entries = (
        activation_entries if isinstance(activation_entries, list) else []
    )
    if (
        current_activation_entries
        and not contract_port.activation_entries_cover_expected(
            activation_entries, current_activation_entries
        )
    ):
        stack_closure_dossier_doc = refresh_port.stack_closure_dossier(
            write_latest=True, working_stack_doc=working_stack_doc
        )
        activation_entries = self_awareness_contracts.nested_get(
            stack_closure_dossier_doc,
            ["working_stack_activation_dossier", "entries"],
        )
        activation_entries = (
            activation_entries if isinstance(activation_entries, list) else []
        )

    activation_smoke_doc = (
        activation_smoke_doc
        if isinstance(activation_smoke_doc, dict)
        else runtime_port.load_latest_json(
            paths.activation_smoke_latest, activation_smoke_schema
        )
    )
    activation_refresh_entries = current_activation_entries or activation_entries
    if contract_port.activation_smoke_needs_refresh(
        activation_smoke_doc, activation_refresh_entries
    ):
        activation_smoke_doc = refresh_port.activation_smoke(
            write_latest=True,
            stack_closure_dossier_doc=stack_closure_dossier_doc,
            working_stack_doc=working_stack_doc,
        )

    episodes_doc = runtime_port.load_latest_json(
        paths.episodes_latest, episodes_schema
    )
    if (
        episodes_doc.get("schema") != episodes_schema
        or not contract_port.episodes_cover_stack_requirements(
            episodes_doc, stack_closure_dossier_doc
        )
    ):
        episodes_doc = refresh_port.episodes(
            write_latest=True, working_stack_doc=working_stack_doc
        )

    previous = runtime_port.load_latest_json(paths.autolink_latest, autolink_schema)
    data = contract_port.autolink_document(
        working_stack_doc=working_stack_doc,
        coverage_audit_doc=coverage_audit_doc,
        stack_closure_dossier_doc=stack_closure_dossier_doc,
        activation_smoke_doc=activation_smoke_doc,
        episodes_doc=episodes_doc,
        previous=previous,
        dependency_refresh=dependency_refresh,
        generated_at=generated_at,
        version=config.version,
        schema_prefix=config.schema_prefix,
        cycle_id=cycle_id,
        probe_run_id=probe_run_id,
        latest_paths={
            "working_stack": paths.working_stack_latest,
            "coverage_audit": paths.coverage_audit_latest,
            "stack_closure_dossier": paths.stack_closure_dossier_latest,
            "activation_smoke": paths.activation_smoke_latest,
            "episodes": paths.episodes_latest,
            "autolink": paths.autolink_latest,
        },
        activation_smoke_compact=contract_port.activation_smoke_compact,
        stack_requirement_closure_acceptance_complete=(
            contract_port.stack_requirement_closure_acceptance_complete
        ),
        stack_coverage_impact_complete=(
            contract_port.stack_coverage_impact_complete
        ),
    )
    if write_latest:
        errors = runtime_port.write_latest_and_history(
            data, paths.autolink_latest, paths.autolink_root
        )
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data

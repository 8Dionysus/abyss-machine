from __future__ import annotations

from typing import Any

import pytest

from abyss_machine import cli
from abyss_machine import self_awareness_coverage_contracts as coverage


def _contract_port(
    *, closure_complete: bool = True
) -> coverage.SelfAwarenessCoverageContractPort:
    callbacks = {
        name: (lambda *_args, **_kwargs: None)
        for name in coverage.SelfAwarenessCoverageContractPort.__dataclass_fields__
    }
    callbacks["stack_requirement_closure_acceptance_complete"] = (
        lambda _packet: closure_complete
    )
    return coverage.SelfAwarenessCoverageContractPort(**callbacks)


def _linked_coverage_audit() -> dict[str, Any]:
    closure_acceptance = {
        "requirement_id": "stack.trace-backend",
        "stack_compat_requirement": {"owner": "abyss-stack"},
        "policy": {"host_layer_mutates_stack": False},
    }
    return {
        "schema": "abyss_machine_self_awareness_objective_coverage_audit_v1",
        "rows": [
            {
                "id": "prometheus_promql",
                "status": "covered",
                "objective_coverage_planes": ["metrics_query"],
                "coverage_plane_status": {"objective": ["metrics_query"]},
                "covered_coverage_planes": ["metrics_query"],
                "coverage_planes": ["metrics_query"],
            },
            {
                "id": "trace_backend",
                "status": "blocked_stack_owned",
                "objective_coverage_planes": ["causal_timeline"],
                "coverage_plane_status": {"objective": ["causal_timeline"]},
                "blocked_by_requirement_ids": ["stack.trace-backend"],
                "open_stack_requirement_ids": ["stack.trace-backend"],
                "blocking_check_keys": ["trace_backend_ready"],
                "requirements": [
                    {
                        "id": "stack.trace-backend",
                        "closure_acceptance": closure_acceptance,
                    }
                ],
                "coverage_impacts": [
                    {
                        "requirement_id": "stack.trace-backend",
                        "coverage_planes": ["causal_timeline"],
                        "policy": {"host_layer_mutates_stack": False},
                    }
                ],
                "blocked_coverage_planes": ["causal_timeline"],
                "coverage_planes": ["causal_timeline"],
            },
        ],
        "summary": {
            "blocked_coverage_planes": ["causal_timeline"],
            "objective_coverage_planes": ["causal_timeline", "metrics_query"],
            "covered_coverage_planes": ["metrics_query"],
            "stack_requirement_closure_acceptance_packets_complete": 1,
        },
    }


def test_coverage_specs_expose_objective_planes() -> None:
    specs = coverage.objective_coverage_specs()
    by_id = {str(spec["id"]): spec for spec in specs}

    assert len(specs) >= 20
    assert coverage.objective_coverage_planes(by_id["prometheus_promql"]) == [
        "metrics_query",
        "observability_inventory",
    ]
    assert "owner_boundary" in coverage.objective_coverage_planes(
        by_id["owner_boundary"]
    )
    assert all(spec.get("owner") for spec in specs)


def test_cli_coverage_audit_only_binds_typed_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_audit(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"schema": "synthetic-coverage"}

    monkeypatch.setattr(coverage, "objective_coverage_audit", fake_audit)
    result = cli.self_awareness_objective_coverage_audit(
        write_latest=False,
        refresh=False,
        working_stack_doc={"schema": "working-stack"},
        stack_closure_dossier_doc={"schema": "dossier"},
    )

    assert result == {"schema": "synthetic-coverage"}
    assert isinstance(captured["paths"], coverage.SelfAwarenessCoveragePaths)
    assert isinstance(captured["config"], coverage.SelfAwarenessCoverageConfig)
    assert isinstance(
        captured["runtime_port"], coverage.SelfAwarenessCoverageRuntimePort
    )
    assert isinstance(
        captured["refresh_port"], coverage.SelfAwarenessCoverageRefreshPort
    )
    assert isinstance(
        captured["contract_port"], coverage.SelfAwarenessCoverageContractPort
    )


def test_coverage_blocker_linkage_accepts_complete_owner_routed_document() -> None:
    issues = coverage.coverage_audit_blocker_linkage_issues(
        _linked_coverage_audit(),
        config=coverage.SelfAwarenessCoverageConfig("abyss_machine", "test"),
        contract_port=_contract_port(),
    )

    assert issues == []


def test_coverage_blocker_linkage_fails_closed_on_identity_policy_and_summary() -> None:
    audit = _linked_coverage_audit()
    blocked = audit["rows"][1]
    blocked["blocked_by_requirement_ids"] = ["stack.other"]
    blocked["coverage_impacts"][0]["policy"]["host_layer_mutates_stack"] = True
    audit["summary"]["blocked_coverage_planes"] = ["wrong_plane"]

    issues = coverage.coverage_audit_blocker_linkage_issues(
        audit,
        config=coverage.SelfAwarenessCoverageConfig("abyss_machine", "test"),
        contract_port=_contract_port(closure_complete=False),
    )

    assert "trace_backend:blocked_by_open_stack_mismatch" in issues
    assert "trace_backend:stack.trace-backend:closure_acceptance" in issues
    assert "trace_backend:impact_policy" in issues
    assert "summary:blocked_coverage_planes_mismatch" in issues


def test_cli_coverage_linkage_wrapper_binds_coverage_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_issues(document: Any, **kwargs: Any) -> list[str]:
        captured["document"] = document
        captured.update(kwargs)
        return ["synthetic"]

    monkeypatch.setattr(coverage, "coverage_audit_blocker_linkage_issues", fake_issues)
    result = cli.self_awareness_coverage_audit_blocker_linkage_issues(
        {"schema": "coverage"}
    )

    assert result == ["synthetic"]
    assert captured["document"] == {"schema": "coverage"}
    assert isinstance(captured["config"], coverage.SelfAwarenessCoverageConfig)
    assert isinstance(captured["contract_port"], coverage.SelfAwarenessCoverageContractPort)

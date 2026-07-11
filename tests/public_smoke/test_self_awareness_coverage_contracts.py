from __future__ import annotations

from typing import Any

import pytest

from abyss_machine import cli
from abyss_machine import self_awareness_coverage_contracts as coverage


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

from __future__ import annotations

from typing import Any

import pytest

from abyss_machine import cli
from abyss_machine import self_awareness_requirement_contracts as requirements


def test_requirement_contracts_keep_stack_closure_read_only() -> None:
    config = requirements.SelfAwarenessRequirementConfig(
        schema_prefix="synthetic",
        version="test",
        grafana_url="http://grafana.test",
        tempo_url="http://tempo.test",
        route_api_url="http://route.test",
        rag_api_url="http://rag.test",
        langchain_api_url="http://langchain.test",
        neo4j_url="http://neo4j.test",
        postgres_host="postgres.test",
        postgres_port=15432,
    )
    requirement = requirements.requirement_item(
        "stack.trace-backend",
        "Trace backend",
        reason="trace joins are not yet readable",
        detection={"evidence_refs": [{"path": "/synthetic/evidence.json"}]},
        expected_shape={"trace_search": "bounded"},
    )

    acceptance = requirements.requirement_acceptance_contract(
        requirement,
        config=config,
    )
    handoff = requirements.requirement_handoff(requirement, config=config)

    assert acceptance["schema"] == "synthetic_stack_requirement_acceptance_contract_v1"
    assert "http://tempo.test/ready" in acceptance["probe_plan"]["candidate_routes"][0]
    assert acceptance["closure_semantics"]["host_layer_mutates_stack"] is False
    assert handoff["compat_contract"]["policy"]["executes_commands"] is False


def test_cli_requirements_only_binds_typed_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_requirements(write_latest: bool = True, **kwargs: Any) -> dict[str, Any]:
        captured["write_latest"] = write_latest
        captured.update(kwargs)
        return {"schema": "synthetic-requirements"}

    monkeypatch.setattr(requirements, "requirements", fake_requirements)

    result = cli.self_awareness_requirements(write_latest=False)

    assert result == {"schema": "synthetic-requirements"}
    assert isinstance(captured["paths"], requirements.SelfAwarenessRequirementPaths)
    assert isinstance(captured["config"], requirements.SelfAwarenessRequirementConfig)
    assert isinstance(
        captured["runtime_port"],
        requirements.SelfAwarenessRequirementRuntimePort,
    )
    assert isinstance(
        captured["refresh_port"],
        requirements.SelfAwarenessRequirementRefreshPort,
    )
    assert isinstance(
        captured["contract_port"],
        requirements.SelfAwarenessRequirementContractPort,
    )

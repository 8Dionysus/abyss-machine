from __future__ import annotations

from typing import Any

import pytest

from abyss_machine import cli
from abyss_machine import self_awareness_cycle_proof_contracts as cycle_proof


def test_from_zero_sources_include_machine_and_cognitive_chains() -> None:
    sources = cycle_proof.cycle_from_zero_chain_sources()

    assert "machine_bridges" in sources
    assert "entity_event_document" in sources
    assert "resident_cognitive_replay" in sources
    assert "working_stack_activation_smoke" in sources
    assert all(values for values in sources.values())


def test_cli_cycle_bridge_proof_only_binds_typed_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_proof(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"schema": "synthetic-proof"}

    monkeypatch.setattr(cycle_proof, "cycle_bridge_proof", fake_proof)

    result = cli.self_awareness_cycle_bridge_proof(
        generated_at="2026-01-01T00:00:00+00:00",
        cycle_id="cycle-1",
        probe_run_id="probe-1",
    )

    assert result == {"schema": "synthetic-proof"}
    assert isinstance(captured["paths"], cycle_proof.SelfAwarenessCycleProofPaths)
    assert isinstance(captured["config"], cycle_proof.SelfAwarenessCycleProofConfig)
    assert isinstance(
        captured["contract_port"],
        cycle_proof.SelfAwarenessCycleProofContractPort,
    )
    assert isinstance(
        captured["runtime_port"],
        cycle_proof.SelfAwarenessCycleProofRuntimePort,
    )

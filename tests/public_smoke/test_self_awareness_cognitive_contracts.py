from __future__ import annotations

from typing import Any

import pytest

from abyss_machine import cli
from abyss_machine import self_awareness_cognitive_contracts as cognitive


def test_investigation_recovery_is_review_only() -> None:
    config = cognitive.SelfAwarenessCognitiveConfig(
        schema_prefix="synthetic",
        semantic_maintain_review_command="review-semantic-state",
        semantic_maintain_retry_command="retry-semantic-state",
    )

    recovery = cognitive.investigation_failure_recovery(
        "thread-1",
        "checkpoint-1",
        config=config,
    )

    assert (
        recovery["schema"]
        == "synthetic_self_awareness_investigation_failure_recovery_v1"
    )
    assert recovery["routes"][2]["command"] == "review-semantic-state"
    assert recovery["routes"][2]["retry_command"] == "retry-semantic-state"
    assert recovery["policy"]["host_layer_mutates_stack"] is False
    assert recovery["policy"]["action_execution"] is False


def test_cli_bounded_context_only_binds_typed_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_packet(*args: Any, **kwargs: Any) -> dict[str, Any]:
        captured["args"] = args
        captured.update(kwargs)
        return {"schema": "synthetic-context"}

    monkeypatch.setattr(cognitive, "bounded_context_packet", fake_packet)

    result = cli.self_awareness_bounded_context_packet(
        {},
        {},
        {},
        {},
        "2026-01-01T00:00:00+00:00",
    )

    assert result == {"schema": "synthetic-context"}
    assert isinstance(captured["paths"], cognitive.SelfAwarenessCognitivePaths)
    assert isinstance(captured["config"], cognitive.SelfAwarenessCognitiveConfig)
    assert isinstance(
        captured["contract_port"],
        cognitive.SelfAwarenessCognitiveContractPort,
    )

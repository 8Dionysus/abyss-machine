from __future__ import annotations

from typing import Any

import pytest

from abyss_machine import cli
from abyss_machine import self_awareness_entity_context_contracts as entity_context


def test_entity_map_issues_fail_closed() -> None:
    config = entity_context.SelfAwarenessEntityContextConfig(
        schema_prefix="synthetic",
    )

    assert entity_context.entity_event_document_map_issues(
        None,
        config=config,
    ) == ["map_missing"]
    assert entity_context.completion_route_packet_issues(
        None,
        config=config,
    ) == ["packet_index_missing"]


def test_cli_response_context_only_binds_typed_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_context(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"schema": "synthetic-context"}

    monkeypatch.setattr(
        entity_context,
        "response_entity_event_document_context",
        fake_context,
    )

    result = cli.self_awareness_response_entity_event_document_context(
        completion_audit_doc={"schema": "audit"},
        episode={"episode_id": "episode-1"},
    )

    assert result == {"schema": "synthetic-context"}
    assert isinstance(
        captured["paths"],
        entity_context.SelfAwarenessEntityContextPaths,
    )
    assert isinstance(
        captured["config"],
        entity_context.SelfAwarenessEntityContextConfig,
    )
    assert isinstance(
        captured["runtime_port"],
        entity_context.SelfAwarenessEntityContextRuntimePort,
    )

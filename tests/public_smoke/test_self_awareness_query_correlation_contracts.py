from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from abyss_machine import cli
from abyss_machine import self_awareness_query_correlation_contracts as readmodels


def _paths(tmp_path: Path) -> readmodels.SelfAwarenessQueryCorrelationPaths:
    values = {
        field: tmp_path / field.replace("_", "-") / "latest.json"
        for field in (
            "events_latest",
            "episodes_latest",
            "spatial_graph_latest",
            "capabilities_latest",
            "context_latest",
            "stack_observability_latest",
            "collect_latest",
            "ai_capabilities_latest",
            "ai_llm_resident_status_latest",
            "rag_validate_latest",
            "nervous_brief_latest",
            "memory_latest",
            "resource_latest",
            "mode_latest",
            "maps_latest",
            "graph_latest",
            "rag_trace_latest",
            "process_container_latest",
            "query_latest",
            "correlation_latest",
        )
    }
    values["query_root"] = tmp_path / "query"
    values["correlation_root"] = tmp_path / "correlation"
    return readmodels.SelfAwarenessQueryCorrelationPaths(**values)


def _ports(
    reads: list[tuple[Any, ...]],
    refreshes: list[str],
    writes: list[tuple[Path, Path]],
) -> tuple[
    readmodels.SelfAwarenessQueryCorrelationRuntimePort,
    readmodels.SelfAwarenessQueryCorrelationRefreshPort,
    readmodels.SelfAwarenessQueryCorrelationContractPort,
    readmodels.SelfAwarenessQueryCorrelationPersistencePort,
]:
    def load_events(**kwargs: Any) -> list[dict[str, Any]]:
        reads.append(("events", kwargs))
        return []

    def load_latest_json(*args: Any) -> dict[str, Any]:
        reads.append(("latest", *args))
        return {}

    def refreshed(name: str, document: dict[str, Any]) -> Any:
        def callback(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            refreshes.append(name)
            return document

        return callback

    def write_latest_and_history(
        _document: dict[str, Any],
        latest: Path,
        root: Path,
    ) -> list[str]:
        writes.append((latest, root))
        return []

    return (
        readmodels.SelfAwarenessQueryCorrelationRuntimePort(
            load_events=load_events,
            load_latest_json=load_latest_json,
            now_iso=lambda: "2026-07-10T12:30:00-06:00",
        ),
        readmodels.SelfAwarenessQueryCorrelationRefreshPort(
            spatial_graph=refreshed("spatial_graph", {}),
            memory_space_overlay=refreshed("memory_space", {}),
            capabilities=refreshed(
                "capabilities",
                {
                    "schema": "abyss_machine_self_awareness_capabilities_v1",
                    "requirements": [{"id": "stack.trace-backend"}],
                },
            ),
        ),
        readmodels.SelfAwarenessQueryCorrelationContractPort(
            redact_text=lambda value, limit: str(value)[:limit],
            query_terms=lambda value: str(value).lower().split(),
            match_score=lambda item, value: int(
                str(value).lower() in json.dumps(item, sort_keys=True).lower()
            ),
            correlation_index=lambda _events: {
                "indexes": {"by_context": {}, "by_service": {}}
            },
        ),
        readmodels.SelfAwarenessQueryCorrelationPersistencePort(
            write_latest_and_history=write_latest_and_history,
        ),
    )


def test_query_uses_supplied_readmodels_and_routes_single_write(tmp_path: Path) -> None:
    reads: list[tuple[Any, ...]] = []
    refreshes: list[str] = []
    writes: list[tuple[Path, Path]] = []
    runtime_port, refresh_port, contract_port, persistence_port = _ports(
        reads,
        refreshes,
        writes,
    )
    paths = _paths(tmp_path)

    document = readmodels.query(
        "needle",
        5,
        True,
        events=[{"event_id": "event-1", "label": "needle"}],
        episodes={"episodes": [{"episode_id": "episode-1", "label": "needle"}]},
        graph={"nodes": [{"id": "node-1", "label": "needle"}]},
        capabilities={"schema": "abyss_machine_self_awareness_capabilities_v1", "ok": True},
        memory_space={"retrieval_packets": [{"id": "packet-1", "label": "needle"}]},
        paths=paths,
        config=readmodels.SelfAwarenessQueryCorrelationConfig("abyss_machine", "0.test"),
        runtime_port=runtime_port,
        refresh_port=refresh_port,
        contract_port=contract_port,
        persistence_port=persistence_port,
    )

    assert document["ok"] is True
    assert document["summary"] == {
        "event_hits": 1,
        "episode_hits": 1,
        "node_hits": 1,
        "memory_space_hits": 1,
        "limit": 5,
    }
    assert document["policy"]["does_not_mutate_stack"] is True
    assert reads == []
    assert refreshes == []
    assert writes == [(paths.query_latest, paths.query_root)]


def test_correlation_uses_supplied_evidence_without_io(tmp_path: Path) -> None:
    reads: list[tuple[Any, ...]] = []
    refreshes: list[str] = []
    writes: list[tuple[Path, Path]] = []
    runtime_port, refresh_port, contract_port, persistence_port = _ports(
        reads,
        refreshes,
        writes,
    )
    events = [
        {"event_id": "event-1", "signal": "metric", "source": "prometheus"},
        {"event_id": "event-2", "signal": "log", "source": "loki"},
    ]

    document = readmodels.correlation(
        False,
        events=events,
        capabilities={
            "schema": "abyss_machine_self_awareness_capabilities_v1",
            "requirements": [{"id": "stack.trace-backend"}],
        },
        stack={
            "prometheus": {
                "jobs": {"prometheus": "1", "grafana": "1", "loki": "1", "alloy": "1"}
            }
        },
        index={
            "indexes": {
                "by_context": {"trace:one": ["event-1", "event-2"]},
                "by_service": {"route-api": ["event-1", "event-2"]},
            }
        },
        episodes={
            "episodes": [
                {
                    "episode_id": "episode-1",
                    "primary_signals": ["metric"],
                    "evidence_refs": [],
                    "suspected_cause_chain": ["candidate"],
                    "confidence": "bounded",
                }
            ]
        },
        paths=_paths(tmp_path),
        config=readmodels.SelfAwarenessQueryCorrelationConfig("abyss_machine", "0.test"),
        runtime_port=runtime_port,
        refresh_port=refresh_port,
        contract_port=contract_port,
        persistence_port=persistence_port,
    )

    assert document["ok"] is True
    assert document["summary"]["joins"] == 2
    assert document["summary"]["dependencies"] == 13
    assert document["slo_views"][0]["availability_ratio"] == 1.0
    assert document["policy"]["correlation_not_root_cause_fact"] is True
    assert reads == []
    assert refreshes == []
    assert writes == []


def test_correlation_refreshes_only_invalid_supplied_capabilities(tmp_path: Path) -> None:
    reads: list[tuple[Any, ...]] = []
    refreshes: list[str] = []
    writes: list[tuple[Path, Path]] = []
    runtime_port, refresh_port, contract_port, persistence_port = _ports(
        reads,
        refreshes,
        writes,
    )

    document = readmodels.correlation(
        False,
        events=[],
        capabilities={},
        stack={},
        index={"indexes": {"by_context": {}, "by_service": {}}},
        episodes={"episodes": []},
        paths=_paths(tmp_path),
        config=readmodels.SelfAwarenessQueryCorrelationConfig("abyss_machine", "0.test"),
        runtime_port=runtime_port,
        refresh_port=refresh_port,
        contract_port=contract_port,
        persistence_port=persistence_port,
    )

    assert document["ok"] is False
    assert document["capability_requirements"] == [{"id": "stack.trace-backend"}]
    assert reads == []
    assert refreshes == ["capabilities"]
    assert writes == []


@pytest.mark.parametrize(
    ("cli_name", "module_name", "args"),
    [
        ("self_awareness_query", "query", ("needle", 7, False)),
        ("self_awareness_correlation", "correlation", (False,)),
    ],
)
def test_cli_query_correlation_only_bind_current_ports(
    monkeypatch: pytest.MonkeyPatch,
    cli_name: str,
    module_name: str,
    args: tuple[Any, ...],
) -> None:
    captured: dict[str, Any] = {}

    def fake_readmodel(*_args: Any, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"schema": "synthetic"}

    monkeypatch.setattr(readmodels, module_name, fake_readmodel)

    document = getattr(cli, cli_name)(*args)

    assert document == {"schema": "synthetic"}
    assert isinstance(captured["paths"], readmodels.SelfAwarenessQueryCorrelationPaths)
    assert isinstance(captured["config"], readmodels.SelfAwarenessQueryCorrelationConfig)
    assert isinstance(captured["runtime_port"], readmodels.SelfAwarenessQueryCorrelationRuntimePort)
    assert isinstance(captured["refresh_port"], readmodels.SelfAwarenessQueryCorrelationRefreshPort)
    assert isinstance(captured["contract_port"], readmodels.SelfAwarenessQueryCorrelationContractPort)
    assert isinstance(
        captured["persistence_port"],
        readmodels.SelfAwarenessQueryCorrelationPersistencePort,
    )

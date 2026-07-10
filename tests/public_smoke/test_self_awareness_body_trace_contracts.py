from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from abyss_machine import cli
from abyss_machine import self_awareness_body_trace_contracts as body_trace


def _paths(tmp_path: Path) -> body_trace.SelfAwarenessBodyTracePaths:
    return body_trace.SelfAwarenessBodyTracePaths(
        episodes_latest=tmp_path / "episodes" / "latest.json",
        context_latest=tmp_path / "context" / "latest.json",
        timeline_latest=tmp_path / "timeline" / "latest.json",
        spatial_graph_latest=tmp_path / "spatial" / "latest.json",
        events_latest=tmp_path / "events" / "latest.json",
    )


def _context(*, complete: bool = True) -> dict[str, Any]:
    return {
        "schema": "abyss_machine_self_awareness_context_v1",
        "generated_at": "2026-07-10T13:45:00-06:00",
        "context_packet": {
            "sections": {
                "host_body": {
                    "schema": "abyss_machine_self_awareness_host_body_v1",
                    "complete": complete,
                    "scheduler": {"unit_contexts": 1, "categories": ["timer"]},
                    "host_services": {"unit_contexts": 1, "categories": ["service"]},
                    "manual_collect": {"contexts": 0},
                }
            }
        },
    }


def _episode() -> dict[str, Any]:
    return {
        "episode_id": "episode-1",
        "episode_kind": "working_stack_movement",
        "owner_route": "abyss-machine:self-awareness",
        "time_window": {
            "start": "2026-07-10T13:00:00-06:00",
            "end": "2026-07-10T13:05:00-06:00",
        },
        "context_keys": ["scheduler_unit:probe.timer"],
        "involved_contexts": [{"scheduler_category": "timer"}],
        "affected_spatial_nodes": ["service:route-api"],
        "affected_services": ["route-api"],
        "event_ids": ["event-1"],
        "evidence_refs": [{"path": "synthetic", "kind": "fixture"}],
    }


def _source_event() -> dict[str, Any]:
    return {
        "event_id": "event-1",
        "event_time": "2026-07-10T13:01:00-06:00",
        "context": {"trace_id": "trace-1"},
        "resource": {"service": "route-api", "owner_surface": "abyss-stack"},
        "space": {"owner_surface": "abyss-stack"},
        "evidence_refs": [{"path": "synthetic-event", "kind": "fixture"}],
    }


def test_body_trace_uses_supplied_context_without_latest_read(tmp_path: Path) -> None:
    reads: list[Path] = []
    paths = _paths(tmp_path)

    document = body_trace.episode_body_trace(
        episode=_episode(),
        source_event=_source_event(),
        context_doc=_context(),
        paths=paths,
        config=body_trace.SelfAwarenessBodyTraceConfig("abyss_machine"),
        runtime_port=body_trace.SelfAwarenessBodyTraceRuntimePort(
            load_latest_json=lambda path, _schema: reads.append(path) or {}
        ),
        contract_port=body_trace.SelfAwarenessBodyTraceContractPort(
            time_bucket=lambda _value: "2026-07-10T13:00:00Z"
        ),
    )

    assert document["complete"] is True
    assert document["temporal"]["bucket"] == "2026-07-10T13:00:00Z"
    assert document["spatial"]["affected_services"] == ["route-api"]
    assert document["contextual"]["source_event_id"] == "event-1"
    assert document["host_body"]["complete"] is True
    assert document["lineage"] == {
        "episode_latest": str(paths.episodes_latest),
        "context_latest": str(paths.context_latest),
        "timeline_latest": str(paths.timeline_latest),
        "spatial_graph_latest": str(paths.spatial_graph_latest),
        "source_event_latest": str(paths.events_latest),
    }
    assert document["policy"]["host_layer_mutates_stack"] is False
    assert document["policy"]["stores_raw_body"] is False
    assert reads == []


def test_body_trace_reads_only_context_latest_when_context_is_absent(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    reads: list[tuple[Path, str]] = []

    document = body_trace.episode_body_trace(
        episode=_episode(),
        source_event=_source_event(),
        paths=paths,
        config=body_trace.SelfAwarenessBodyTraceConfig("abyss_machine"),
        runtime_port=body_trace.SelfAwarenessBodyTraceRuntimePort(
            load_latest_json=lambda path, schema: reads.append((path, schema)) or _context()
        ),
        contract_port=body_trace.SelfAwarenessBodyTraceContractPort(
            time_bucket=lambda _value: "2026-07-10T13:00:00Z"
        ),
    )

    assert document["complete"] is True
    assert reads == [
        (paths.context_latest, "abyss_machine_self_awareness_context_v1")
    ]


def test_body_trace_completion_requires_complete_host_body(tmp_path: Path) -> None:
    document = body_trace.episode_body_trace(
        episode=_episode(),
        source_event=_source_event(),
        context_doc=_context(complete=False),
        paths=_paths(tmp_path),
        config=body_trace.SelfAwarenessBodyTraceConfig("abyss_machine"),
        runtime_port=body_trace.SelfAwarenessBodyTraceRuntimePort(
            load_latest_json=lambda *_args: {}
        ),
        contract_port=body_trace.SelfAwarenessBodyTraceContractPort(
            time_bucket=lambda _value: "2026-07-10T13:00:00Z"
        ),
    )

    assert document["complete"] is False
    assert body_trace.body_trace_complete(document, schema_prefix="abyss_machine") is False


def test_cli_body_trace_helpers_only_bind_current_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_body_trace(**kwargs: Any) -> dict[str, Any]:
        captured["body_trace"] = kwargs
        return {"schema": "synthetic"}

    def fake_complete(document: Any, *, schema_prefix: str) -> bool:
        captured["complete"] = (document, schema_prefix)
        return True

    monkeypatch.setattr(body_trace, "episode_body_trace", fake_body_trace)
    monkeypatch.setattr(body_trace, "body_trace_complete", fake_complete)

    assert cli.self_awareness_episode_body_trace(episode={"episode_id": "episode-1"}) == {
        "schema": "synthetic"
    }
    assert cli.self_awareness_body_trace_complete({"schema": "fixture"}) is True
    kwargs = captured["body_trace"]
    assert isinstance(kwargs["paths"], body_trace.SelfAwarenessBodyTracePaths)
    assert isinstance(kwargs["config"], body_trace.SelfAwarenessBodyTraceConfig)
    assert isinstance(kwargs["runtime_port"], body_trace.SelfAwarenessBodyTraceRuntimePort)
    assert isinstance(kwargs["contract_port"], body_trace.SelfAwarenessBodyTraceContractPort)
    assert captured["complete"] == ({"schema": "fixture"}, "abyss_machine")

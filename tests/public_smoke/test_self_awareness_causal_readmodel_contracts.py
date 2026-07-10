from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from abyss_machine import cli
from abyss_machine import self_awareness_causal_readmodel_contracts as causal


NOW = "2026-07-10T07:00:00-06:00"
SCHEMA_PREFIX = "abyss_machine"
VERSION = "0.test"


def _paths(tmp_path: Path) -> causal.SelfAwarenessCausalPaths:
    return causal.SelfAwarenessCausalPaths(
        timeline_latest=tmp_path / "timeline" / "latest.json",
        timeline_root=tmp_path / "timeline",
        spatial_graph_latest=tmp_path / "spatial-graph" / "latest.json",
        spatial_graph_root=tmp_path / "spatial-graph",
        working_stack_latest=tmp_path / "working-stack" / "latest.json",
        stack_observability_latest=tmp_path / "stack-observability" / "latest.json",
        capabilities_latest=tmp_path / "capabilities" / "latest.json",
        context_latest=tmp_path / "context" / "latest.json",
        context_root=tmp_path / "context",
        requirement_probes_latest=tmp_path / "requirement-probes" / "latest.json",
        trace_context_latest=tmp_path / "trace-context" / "latest.json",
        episodes_latest=tmp_path / "episodes" / "latest.json",
        episodes_root=tmp_path / "episodes",
        events_latest=tmp_path / "events" / "latest.json",
    )


def _event() -> dict[str, Any]:
    return {
        "event_id": "event-1",
        "event_time": "2026-07-10T06:59:00-06:00",
        "observed_at": "2026-07-10T07:00:00-06:00",
        "signal": "request",
        "source": "synthetic",
        "severity": "info",
        "resource": {"service": "rag-api", "owner_surface": "abyss-stack"},
        "context": {"trace_id": "trace-1", "request_id": "request-1"},
        "evidence_refs": [{"path": "/synthetic/event-1.json"}],
    }


def _working_stack() -> dict[str, Any]:
    return {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_working_stack_inventory_v1",
        "ok": True,
        "status": "ready",
        "summary": {"organs": 1, "usage_gaps": 0, "time_space_context_links": 1},
        "organs": [
            {
                "service": "rag-api",
                "machine_usage_status": "observed",
                "deep_usage_proven": True,
                "runtime": {"running": True, "pid_alive": True},
                "time_space_context_link": {"link_id": "link-rag"},
            }
        ],
        "model_roots": {"models": []},
    }


def _stack_handoff_overlay(*_: Any, **__: Any) -> dict[str, Any]:
    return {
        "summary": {
            "timeline_markers": 0,
            "open_stack_requirements": 0,
            "acceptance_verifier_steps": 0,
        },
        "timeline_markers": [],
        "spatial_nodes": [],
        "spatial_edges": [],
    }


def _memory_space_overlay(_: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "summary": {"freshness_gates": 0, "retrieval_packets": 0},
        "freshness_gates": [],
        "retrieval_packets": [],
        "spatial_overlays": [],
        "stack_semantic_backends": [],
        "policy": {"bounded": True},
    }


def _dedupe_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return list({str(event["event_id"]): event for event in events}.values())


def _ports(
    tmp_path: Path,
) -> tuple[
    causal.SelfAwarenessCausalPaths,
    causal.SelfAwarenessCausalRuntimePort,
    causal.SelfAwarenessCausalRefreshPort,
    causal.SelfAwarenessCausalContractPort,
    causal.SelfAwarenessCausalConstants,
    list[tuple[str, Path, Path]],
]:
    paths = _paths(tmp_path)
    event = _event()
    writes: list[tuple[str, Path, Path]] = []
    latest_documents = {
        paths.stack_observability_latest: {
            "schema": f"{SCHEMA_PREFIX}_stack_observability_v1",
            "loki": {"labels": {"labels": []}},
        },
        paths.capabilities_latest: {
            "schema": f"{SCHEMA_PREFIX}_self_awareness_capabilities_v1",
            "capabilities": [
                {"id": "warm-e2b.resident-cognitive-worker"},
                {"id": "host.governance-gates"},
                {"id": "llm.escalation.routes"},
            ],
        },
        paths.requirement_probes_latest: {
            "schema": f"{SCHEMA_PREFIX}_self_awareness_requirement_probes_v1",
            "probes": [],
        },
        paths.trace_context_latest: {
            "schema": f"{SCHEMA_PREFIX}_self_awareness_trace_context_fallback_v1"
        },
        paths.working_stack_latest: _working_stack(),
    }

    def load_latest_json(path: Path, _: str) -> dict[str, Any]:
        return latest_documents.get(path, {})

    def write_latest_and_history(
        document: dict[str, Any], latest: Path, root: Path
    ) -> list[str]:
        writes.append((str(document.get("schema")), latest, root))
        return []

    runtime_port = causal.SelfAwarenessCausalRuntimePort(
        load_latest_json=load_latest_json,
        write_latest_and_history=write_latest_and_history,
        now_iso=lambda: NOW,
        hostname=lambda: "synthetic-host",
        storage_path_protection=lambda _: {"decision": "allow"},
    )
    contract_port = causal.SelfAwarenessCausalContractPort(
        dedupe_events=_dedupe_events,
        parse_time=lambda value: datetime.fromisoformat(str(value)),
        stack_handoff_time_space_overlay=_stack_handoff_overlay,
        time_bucket=lambda value: str(value)[:13],
        memory_space_overlay=_memory_space_overlay,
        bounded_context_packet=lambda *_: {
            "complete": True,
            "summary": {
                "sections": 1,
                "stack_handoff_actions": 0,
                "open_stack_requirements": 0,
                "resident_worker_complete": True,
                "governance_gates_complete": True,
            },
        },
        brief_stack_handoff_action_map=lambda _: {"actions": []},
        working_stack_gap_episodes=lambda **_: ([], []),
    )
    constants = causal.SelfAwarenessCausalConstants(
        working_stack_expected_live_services=("rag-api",),
        unbounded_labels={"trace_id", "request_id"},
    )

    def refresh_timeline(*, write_latest: bool = True) -> dict[str, Any]:
        return causal.timeline(
            write_latest=write_latest,
            schema_prefix=SCHEMA_PREFIX,
            version=VERSION,
            paths=paths,
            runtime_port=runtime_port,
            refresh_port=refresh_port,
            contract_port=contract_port,
            constants=constants,
        )

    def refresh_spatial_graph(
        *,
        write_latest: bool = True,
        working_stack_doc: dict[str, Any] | None = None,
        timeline_doc: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return causal.spatial_graph(
            write_latest=write_latest,
            working_stack_doc=working_stack_doc,
            timeline_doc=timeline_doc,
            schema_prefix=SCHEMA_PREFIX,
            version=VERSION,
            paths=paths,
            runtime_port=runtime_port,
            refresh_port=refresh_port,
            contract_port=contract_port,
            constants=constants,
        )

    refresh_port = causal.SelfAwarenessCausalRefreshPort(
        load_events=lambda **_: [event, dict(event)],
        working_stack_inventory=lambda **_: _working_stack(),
        capabilities=lambda **_: latest_documents[paths.capabilities_latest],
        requirement_probes=lambda **_: latest_documents[paths.requirement_probes_latest],
        timeline=refresh_timeline,
        spatial_graph=refresh_spatial_graph,
    )
    return paths, runtime_port, refresh_port, contract_port, constants, writes


def _common_kwargs(tmp_path: Path) -> tuple[dict[str, Any], list[tuple[str, Path, Path]]]:
    paths, runtime_port, refresh_port, contract_port, constants, writes = _ports(tmp_path)
    return {
        "schema_prefix": SCHEMA_PREFIX,
        "version": VERSION,
        "paths": paths,
        "runtime_port": runtime_port,
        "refresh_port": refresh_port,
        "contract_port": contract_port,
        "constants": constants,
    }, writes


def test_timeline_deduplicates_events_and_persists_only_when_requested(
    tmp_path: Path,
) -> None:
    kwargs, writes = _common_kwargs(tmp_path)

    document = causal.timeline(write_latest=True, **kwargs)

    assert document["schema"] == f"{SCHEMA_PREFIX}_self_awareness_timeline_v1"
    assert document["summary"]["events"] == 1
    assert document["summary"]["windows"] == 1
    assert document["summary"]["clock_skewed_events"] == 0
    assert [write[0] for write in writes] == [document["schema"]]


def test_spatial_graph_uses_supplied_readmodels_without_live_refresh(tmp_path: Path) -> None:
    kwargs, writes = _common_kwargs(tmp_path)
    timeline_doc = causal.timeline(write_latest=False, **kwargs)

    document = causal.spatial_graph(
        write_latest=False,
        timeline_doc=timeline_doc,
        working_stack_doc=_working_stack(),
        **kwargs,
    )

    assert document["ok"] is True
    assert document["summary"]["working_stack_expected_live_present"] is True
    assert any(node["id"] == "host:synthetic-host" for node in document["nodes"])
    assert any(node["id"] == "service:rag-api" for node in document["nodes"])
    assert writes == []


def test_spatial_graph_refreshes_an_invalid_latest_timeline(tmp_path: Path) -> None:
    kwargs, writes = _common_kwargs(tmp_path)

    document = causal.spatial_graph(
        write_latest=False,
        working_stack_doc=_working_stack(),
        **kwargs,
    )

    assert document["summary"]["nodes"] > 0
    assert [write[0] for write in writes] == [
        f"{SCHEMA_PREFIX}_self_awareness_timeline_v1"
    ]


def test_context_builds_bounded_packet_from_fake_latest_documents(tmp_path: Path) -> None:
    kwargs, writes = _common_kwargs(tmp_path)

    document = causal.context(write_latest=True, **kwargs)

    assert document["ok"] is True
    assert document["summary"]["contexts"] == 1
    assert document["summary"]["bounded_context_packet_complete"] is True
    assert document["policy"]["action_execution"] is False
    assert [write[0] for write in writes] == [document["schema"]]


def test_episodes_runs_timeline_graph_and_episode_persistence_in_order(
    tmp_path: Path,
) -> None:
    kwargs, writes = _common_kwargs(tmp_path)

    document = causal.episodes(
        write_latest=True,
        working_stack_doc=_working_stack(),
        **kwargs,
    )

    assert document["ok"] is True
    assert document["summary"]["events"] == 1
    assert document["summary"]["episodes"] == 1
    assert document["episodes"][0]["truth_level"] == "inferred"
    assert [write[0] for write in writes] == [
        f"{SCHEMA_PREFIX}_self_awareness_timeline_v1",
        f"{SCHEMA_PREFIX}_self_awareness_spatial_graph_v1",
        f"{SCHEMA_PREFIX}_self_awareness_episodes_v1",
    ]


@pytest.mark.parametrize(
    ("cli_name", "module_name", "call_kwargs"),
    [
        ("self_awareness_timeline", "timeline", {}),
        ("self_awareness_spatial_graph", "spatial_graph", {}),
        ("self_awareness_context", "context", {}),
        ("self_awareness_episodes", "episodes", {}),
    ],
)
def test_cli_causal_readmodel_commands_only_bind_concrete_ports(
    monkeypatch: pytest.MonkeyPatch,
    cli_name: str,
    module_name: str,
    call_kwargs: dict[str, Any],
) -> None:
    captured: dict[str, Any] = {}

    def fake_command(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"schema": "synthetic"}

    monkeypatch.setattr(causal, module_name, fake_command)

    result = getattr(cli, cli_name)(write_latest=False, **call_kwargs)

    assert result == {"schema": "synthetic"}
    assert captured["write_latest"] is False
    assert isinstance(captured["paths"], causal.SelfAwarenessCausalPaths)
    assert isinstance(captured["runtime_port"], causal.SelfAwarenessCausalRuntimePort)
    assert isinstance(captured["refresh_port"], causal.SelfAwarenessCausalRefreshPort)
    assert isinstance(captured["contract_port"], causal.SelfAwarenessCausalContractPort)
    assert isinstance(captured["constants"], causal.SelfAwarenessCausalConstants)

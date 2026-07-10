from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from abyss_machine import cli
from abyss_machine import self_awareness_alert_contracts as alerts


def _paths(tmp_path: Path) -> alerts.SelfAwarenessAlertPaths:
    return alerts.SelfAwarenessAlertPaths(
        context_latest=tmp_path / "context/latest.json",
        episodes_latest=tmp_path / "episodes/latest.json",
        requirement_probes_latest=tmp_path / "requirement-probes/latest.json",
        working_stack_latest=tmp_path / "working-stack/latest.json",
        investigate_latest=tmp_path / "investigate/latest.json",
        replay_latest=tmp_path / "replay/latest.json",
        events_latest=tmp_path / "events/latest.json",
        spatial_graph_latest=tmp_path / "spatial-graph/latest.json",
        timeline_latest=tmp_path / "timeline/latest.json",
        alerts_latest=tmp_path / "alerts/latest.json",
        alerts_root=tmp_path / "alerts",
        reactions_latest=tmp_path / "reactions/latest.json",
    )


def _response(candidate_id: str, episode: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
    episode_id = str(episode.get("episode_id") or "")
    return {
        "validated_episode": {"episode_id": episode_id},
        "body_trace": {"complete": True},
        "entity_event_document_context": {"complete": True},
        "risk": {"risks": ["review"]},
        "blast_radius": {"affected_surfaces": ["self-awareness"]},
        "rollback": {"steps": ["discard"]},
        "runbook_candidate": {"steps": ["review"]},
        "investigation": {"thread_id": "thread-1"},
        "replay": {"thread_id": "thread-1"},
        "activation_gap_route": {"complete": True},
        "stack_requirement_route": {"complete": True},
        "candidate_id": candidate_id,
    }


def _contract_port() -> alerts.SelfAwarenessAlertContractPort:
    return alerts.SelfAwarenessAlertContractPort(
        episode_response_contract=_response,
        reaction_candidate_response_depth_complete=lambda candidate: bool(
            candidate.get("response_contract")
        ),
        body_trace_complete=lambda trace: trace.get("complete") is True,
    )


def _documents(paths: alerts.SelfAwarenessAlertPaths) -> dict[Path, dict[str, Any]]:
    return {
        paths.context_latest: {
            "context_packet": {"sections": {"host_body": {"complete": True}}}
        },
        paths.episodes_latest: {
            "episodes": [
                {
                    "episode_id": "episode-alert",
                    "episode_kind": "event_correlation",
                    "event_ids": ["event-alert"],
                },
                {
                    "episode_id": "episode-gap",
                    "episode_kind": "working_stack_usage_gap",
                    "working_stack_gap": {
                        "service": "aoa-browser",
                        "machine_usage_status": "tool_runtime_degraded",
                    },
                },
                {
                    "episode_id": "episode-movement",
                    "episode_kind": "working_stack_movement",
                    "service": "aoa-course-connector",
                    "movement_packet_id": "movement-1",
                    "event_ids": ["event-movement"],
                    "movement_selection": {"selected_reason": "bounded movement"},
                },
                {
                    "episode_id": "episode-stack",
                    "episode_kind": "stack_handoff_blocker",
                    "requirement_id": "stack.trace-backend",
                    "stack_handoff_marker_id": "marker-1",
                },
            ]
        },
        paths.investigate_latest: {"thread_id": "thread-1"},
        paths.replay_latest: {"thread_id": "thread-1", "ok": True},
        paths.requirement_probes_latest: {"summary": {"open": 0}},
        paths.working_stack_latest: {"summary": {"usage_gaps": 0}},
    }


def test_alert_pipeline_builds_every_owner_gated_candidate_kind(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    documents = _documents(paths)
    events = [
        {
            "event_id": "event-alert",
            "signal": "alert",
            "severity": "warning",
            "resource": {"alert_fingerprint": "fingerprint-1"},
        },
        {
            "event_id": "event-movement",
            "signal": "movement",
            "resource": {"movement_packet_id": "movement-1"},
        },
        {
            "event_id": "event-probe",
            "signal": "alert",
            "resource": {"alertname": "SelfAwarenessSyntheticProbe"},
            "context": {"synthetic_run_id": "probe-1"},
        },
    ]
    writes: list[tuple[Path, Path]] = []

    result = alerts.alerts(
        paths=paths,
        config=alerts.SelfAwarenessAlertConfig("abyss_machine", "test"),
        runtime_port=alerts.SelfAwarenessAlertRuntimePort(
            load_latest_json=lambda path, _schema: documents.get(path, {}),
            now_iso=lambda: "2026-07-10T20:00:00Z",
            write_latest_and_history=lambda _data, latest, root: writes.append(
                (latest, root)
            )
            or [],
        ),
        refresh_port=alerts.SelfAwarenessAlertRefreshPort(
            load_events=lambda refresh: events,
            context=lambda write_latest: pytest.fail("complete context must be reused"),
            episodes=lambda write_latest: pytest.fail("complete episodes must be reused"),
        ),
        contract_port=_contract_port(),
    )

    candidates = result["candidates"]
    assert result["summary"] == {
        "alert_events": 2,
        "reaction_candidates": 4,
        "response_depth_candidates": 4,
        "response_depth_missing": 0,
        "body_trace_candidates": 4,
        "body_trace_missing": 0,
        "stack_handoff_candidates": 1,
        "stack_handoff_episodes": 1,
        "working_stack_gap_candidates": 1,
        "working_stack_gap_episodes": 1,
        "working_stack_movement_candidates": 1,
        "working_stack_movement_episodes": 1,
        "probe_alert_markers": 1,
        "automatic_actions": 0,
    }
    assert {candidate["action_mode"] for candidate in candidates} == {
        "operator_review",
        "owner_handoff_review",
        "resident_review",
    }
    assert all(candidate["automatic"] is False for candidate in candidates)
    assert all(candidate["response_contract"] for candidate in candidates)
    assert result["policy"]["executes_commands"] is False
    assert result["probe_alert_markers"][0]["selected_for_response"] is False
    assert writes == [(paths.alerts_latest, paths.alerts_root)]


def test_alert_pipeline_refreshes_missing_context_and_episode_classes(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    documents = {
        paths.context_latest: {},
        paths.episodes_latest: {"episodes": []},
        paths.requirement_probes_latest: {"summary": {"open": 1}},
        paths.working_stack_latest: {"summary": {"usage_gaps": 1}},
        paths.investigate_latest: {},
        paths.replay_latest: {},
    }
    calls: list[str] = []
    refreshed = {
        "episodes": [
            {
                "episode_id": "episode-stack",
                "episode_kind": "stack_handoff_blocker",
                "requirement_id": "stack.database-graph.read-route",
            },
            {
                "episode_id": "episode-gap",
                "episode_kind": "working_stack_usage_gap",
                "working_stack_gap": {"service": "aoa-course-connector"},
            },
        ]
    }

    result = alerts.alerts(
        write_latest=False,
        paths=paths,
        config=alerts.SelfAwarenessAlertConfig("abyss_machine", "test"),
        runtime_port=alerts.SelfAwarenessAlertRuntimePort(
            load_latest_json=lambda path, _schema: documents.get(path, {}),
            now_iso=lambda: "2026-07-10T20:00:00Z",
            write_latest_and_history=lambda *_args: pytest.fail("write disabled"),
        ),
        refresh_port=alerts.SelfAwarenessAlertRefreshPort(
            load_events=lambda refresh: calls.append(f"events:{refresh}") or [],
            context=lambda write_latest: calls.append(f"context:{write_latest}")
            or {"context_packet": {"sections": {"host_body": {"complete": True}}}},
            episodes=lambda write_latest: calls.append(f"episodes:{write_latest}")
            or refreshed,
        ),
        contract_port=_contract_port(),
    )

    assert calls == ["events:True", "context:True", "episodes:True"]
    assert result["summary"]["stack_handoff_candidates"] == 1
    assert result["summary"]["working_stack_gap_candidates"] == 1


def test_alert_pipeline_projects_persistence_failure(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    documents = _documents(paths)
    result = alerts.alerts(
        paths=paths,
        config=alerts.SelfAwarenessAlertConfig("abyss_machine", "test"),
        runtime_port=alerts.SelfAwarenessAlertRuntimePort(
            load_latest_json=lambda path, _schema: documents.get(path, {}),
            now_iso=lambda: "2026-07-10T20:00:00Z",
            write_latest_and_history=lambda *_args: [{"error": "read-only"}],
        ),
        refresh_port=alerts.SelfAwarenessAlertRefreshPort(
            load_events=lambda refresh: [],
            context=lambda write_latest: {},
            episodes=lambda write_latest: {},
        ),
        contract_port=_contract_port(),
    )

    assert result["ok"] is False
    assert result["write_errors"] == [{"error": "read-only"}]


def test_cli_alerts_only_binds_typed_ports(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_alerts(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"schema": "synthetic-alerts"}

    monkeypatch.setattr(alerts, "alerts", fake_alerts)
    result = cli.self_awareness_alerts(write_latest=False)

    assert result == {"schema": "synthetic-alerts"}
    assert captured["write_latest"] is False
    assert isinstance(captured["paths"], alerts.SelfAwarenessAlertPaths)
    assert isinstance(captured["config"], alerts.SelfAwarenessAlertConfig)
    assert isinstance(captured["runtime_port"], alerts.SelfAwarenessAlertRuntimePort)
    assert isinstance(captured["refresh_port"], alerts.SelfAwarenessAlertRefreshPort)
    assert isinstance(captured["contract_port"], alerts.SelfAwarenessAlertContractPort)

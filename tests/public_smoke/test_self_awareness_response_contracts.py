from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from abyss_machine import cli
from abyss_machine import self_awareness_response_contracts as responses


def _paths(tmp_path: Path) -> responses.SelfAwarenessResponsePaths:
    fields = (
        "activation_smoke_latest",
        "investigate_latest",
        "replay_latest",
        "stack_closure_dossier_latest",
        "probe_latest",
        "alerts_latest",
        "reactions_latest",
        "responses_latest",
        "episodes_latest",
        "events_latest",
        "spatial_graph_latest",
        "working_stack_latest",
        "process_container_latest",
        "completion_audit_latest",
        "requirement_probes_latest",
        "timeline_latest",
    )
    return responses.SelfAwarenessResponsePaths(
        **{field: tmp_path / field.replace("_", "-") / "latest.json" for field in fields}
    )


def _contract_port(calls: list[tuple[str, Any]]) -> responses.SelfAwarenessResponseContractPort:
    def record(name: str, result: dict[str, Any]) -> Any:
        def callback(*args: Any, **kwargs: Any) -> dict[str, Any]:
            calls.append((name, {"args": args, "kwargs": kwargs}))
            return result

        return callback

    return responses.SelfAwarenessResponseContractPort(
        episode_body_trace=record(
            "body_trace",
            {
                "schema": "abyss_machine_self_awareness_body_trace_v1",
                "complete": True,
            },
        ),
        body_trace_complete=lambda document: document.get("complete") is True,
        response_entity_event_document_context=record(
            "entity_context",
            {
                "schema": "abyss_machine_self_awareness_response_entity_event_document_context_v1",
                "complete": True,
            },
        ),
        response_entity_event_document_context_complete=lambda document: document.get("complete")
        is True,
        stack_requirement_handoff_route=record(
            "stack_route",
            {"schema": "stack-route", "complete": True},
        ),
        stack_requirement_handoff_route_complete=lambda route: route.get("complete") is True,
        working_stack_activation_gap_route=record(
            "activation_route",
            {"schema": "activation-route", "complete": True},
        ),
        working_stack_activation_gap_route_complete=lambda route: route.get("complete") is True,
        working_stack_activation_smoke_row_complete=lambda row: row.get("complete") is True,
    )


def _episode(kind: str = "event_correlation") -> dict[str, Any]:
    return {
        "schema": "abyss_machine_causal_episode_v1",
        "episode_id": "episode-1",
        "episode_kind": kind,
        "owner_route": "abyss-machine:self-awareness",
        "time_window": {"start": "2026-07-10T13:00:00Z", "end": "2026-07-10T13:01:00Z"},
        "event_ids": ["event-1"],
        "primary_signals": ["alert"],
        "affected_spatial_nodes": ["service:route-api"],
        "confidence": {"score": 0.9},
        "truth_level": "inferred",
        "evidence_refs": [{"path": "synthetic-episode"}],
    }


def _investigation() -> dict[str, Any]:
    return {
        "thread_id": "thread-1",
        "selected_episode_id": "episode-1",
        "summary": {"checkpoints": 2},
    }


def _replay() -> dict[str, Any]:
    return {
        "thread_id": "thread-1",
        "ok": True,
        "summary": {"divergences": 0, "conclusion_diff_changed": False},
    }


def _assemble(
    tmp_path: Path,
    *,
    episode: dict[str, Any],
    source_event: dict[str, Any] | None = None,
    investigation: dict[str, Any] | None = None,
    replay: dict[str, Any] | None = None,
    documents: dict[Path, dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[Path], list[tuple[str, Any]], responses.SelfAwarenessResponseContractPort]:
    paths = _paths(tmp_path)
    reads: list[Path] = []
    calls: list[tuple[str, Any]] = []
    contract_port = _contract_port(calls)
    documents = documents or {}

    def load_latest_json(path: Path, _schema: str) -> dict[str, Any]:
        reads.append(path)
        return documents.get(path, {})

    document = responses.episode_response_contract(
        candidate_id="candidate-1",
        episode=episode,
        source_event=source_event or {},
        investigation=investigation if investigation is not None else _investigation(),
        replay=replay if replay is not None else _replay(),
        context_doc={"schema": "synthetic-context"},
        completion_audit_doc={"schema": "synthetic-completion"},
        paths=paths,
        config=responses.SelfAwarenessResponseConfig("abyss_machine"),
        runtime_port=responses.SelfAwarenessResponseRuntimePort(load_latest_json),
        contract_port=contract_port,
    )
    return document, reads, calls, contract_port


def test_response_synthetic_lineage_reads_only_probe(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    required = [
        "alert",
        "langgraph_investigation",
        "replay",
        "reaction_candidate",
        "governed_response",
    ]
    probe = {
        "ok": True,
        "run_id": "probe-1",
        "e2e_lineage_proof": {
            "ok": True,
            "rows": [{"id": row_id, "satisfied": True} for row_id in required],
            "summary": {"missing_rows": []},
        },
    }
    document, reads, _calls, _port = _assemble(
        tmp_path,
        episode=_episode(),
        source_event={
            "event_id": "event-1",
            "context": {"synthetic_run_id": "probe-1"},
        },
        documents={paths.probe_latest: probe},
    )

    assert document["episode_specific_evidence"]["source_kind"] == "synthetic_probe_e2e_lineage"
    assert document["episode_specific_evidence"]["complete"] is True
    assert reads == [paths.probe_latest]


def test_response_working_stack_gap_reads_only_activation_smoke(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    episode = _episode("working_stack_usage_gap")
    episode["service"] = "aoa-browser"
    episode["working_stack_gap"] = {
        "service": "aoa-browser",
        "machine_usage_status": "tool_runtime_degraded",
        "safe_next_action": {"owner_route": "abyss-stack"},
        "verifier_commands": ["verify-browser"],
    }
    activation_smoke = {
        "rows": [
            {
                "episode_id": "episode-1",
                "service": "aoa-browser",
                "machine_usage_status": "tool_runtime_degraded",
                "complete": True,
                "investigation": {
                    "ok": True,
                    "thread_id": "thread-1",
                    "selected_episode_matches": True,
                    "selected_episode_id": "episode-1",
                },
                "replay": {
                    "ok": True,
                    "thread_id": "thread-1",
                    "thread_matches": True,
                    "working_stack_gap_replayable": True,
                    "working_stack_gap_matches": True,
                },
            }
        ]
    }

    document, reads, calls, _port = _assemble(
        tmp_path,
        episode=episode,
        investigation={},
        replay={},
        documents={paths.activation_smoke_latest: activation_smoke},
    )

    assert document["episode_specific_evidence"]["source_kind"] == "activation_smoke_matrix"
    assert document["episode_specific_evidence"]["complete"] is True
    assert document["activation_gap_route"]["complete"] is True
    assert reads == [paths.activation_smoke_latest]
    assert any(name == "activation_route" for name, _ in calls)


def test_response_stack_handoff_reads_only_closure_dossier(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    episode = _episode("stack_handoff_blocker")
    episode["requirement_id"] = "stack.trace-backend"
    episode["stack_handoff"] = {
        "safe_next_action": {"owner_route": "abyss-stack"},
        "policy": {"host_layer_mutates_stack": False},
    }
    replay = _replay()
    replay["stack_handoff_replay"] = {
        "closure_readiness_replayable": True,
        "open_requirement_ids": ["stack.trace-backend"],
    }
    dossier = {
        "closure_acceptance_matrix": {
            "packets": [{"requirement_id": "stack.trace-backend", "complete": True}]
        }
    }

    document, reads, calls, _port = _assemble(
        tmp_path,
        episode=episode,
        replay=replay,
        documents={paths.stack_closure_dossier_latest: dossier},
    )

    assert document["episode_specific_evidence"]["source_kind"] == (
        "stack_closure_dossier_and_stack_handoff_replay"
    )
    assert document["episode_specific_evidence"]["complete"] is True
    assert document["stack_requirement_route"]["complete"] is True
    assert reads == [paths.stack_closure_dossier_latest]
    assert any(name == "stack_route" for name, _ in calls)


def test_response_working_stack_movement_requires_no_latest_read(tmp_path: Path) -> None:
    episode = _episode("working_stack_movement")
    episode["movement_packet_id"] = "movement-1"
    episode["working_stack_link_id"] = "link-1"

    document, reads, _calls, contract_port = _assemble(
        tmp_path,
        episode=episode,
        source_event={"event_id": "event-1", "resource": {"movement_packet_id": "movement-1"}},
    )

    assert document["episode_specific_evidence"]["source_kind"] == (
        "working_stack_movement_investigate_replay"
    )
    assert document["episode_specific_evidence"]["complete"] is True
    assert document["policy"]["executes_commands"] is False
    assert document["policy"]["host_layer_mutates_stack"] is False
    assert reads == []
    assert responses.response_contract_complete(
        document,
        config=responses.SelfAwarenessResponseConfig("abyss_machine"),
        contract_port=contract_port,
    ) is True


def test_response_candidate_and_route_depth_require_exact_contract_projection(
    tmp_path: Path,
) -> None:
    episode = _episode("working_stack_movement")
    episode["movement_packet_id"] = "movement-1"
    episode["working_stack_link_id"] = "link-1"
    contract, _reads, _calls, contract_port = _assemble(tmp_path, episode=episode)
    config = responses.SelfAwarenessResponseConfig("abyss_machine")
    candidate = {
        "schema": "abyss_machine_reaction_candidate_v1",
        "category": "self-awareness",
        "automatic": False,
        "owner_route": "abyss-machine:self-awareness",
        "episode_id": "episode-1",
        "response_contract": contract,
        **{
            key: contract[key]
            for key in (
                "risk",
                "blast_radius",
                "rollback",
                "runbook_candidate",
                "body_trace",
                "entity_event_document_context",
            )
        },
    }
    route = {
        "schema": "abyss_machine_response_route_v1",
        "category": "self-awareness",
        "automatic": False,
        "executes": False,
        "approval": {"required": True},
        "policy": {
            "automatic_response": False,
            "executes_commands": False,
            "host_layer_mutates_stack": False,
        },
        "response_contract": contract,
        "validated_episode": contract["validated_episode"],
        **{
            key: contract[key]
            for key in (
                "risk",
                "blast_radius",
                "rollback",
                "runbook_candidate",
                "body_trace",
                "entity_event_document_context",
            )
        },
    }

    assert responses.reaction_candidate_response_depth_complete(
        candidate,
        config=config,
        contract_port=contract_port,
    ) is True
    assert responses.response_route_depth_complete(
        route,
        config=config,
        contract_port=contract_port,
    ) is True
    route["executes"] = True
    assert responses.response_route_depth_complete(
        route,
        config=config,
        contract_port=contract_port,
    ) is False


def test_cli_response_contract_only_binds_current_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_response(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"schema": "synthetic"}

    monkeypatch.setattr(responses, "episode_response_contract", fake_response)

    document = cli.self_awareness_episode_response_contract(
        candidate_id="candidate-1",
        episode={"episode_id": "episode-1"},
    )

    assert document == {"schema": "synthetic"}
    assert isinstance(captured["paths"], responses.SelfAwarenessResponsePaths)
    assert isinstance(captured["config"], responses.SelfAwarenessResponseConfig)
    assert isinstance(captured["runtime_port"], responses.SelfAwarenessResponseRuntimePort)
    assert isinstance(captured["contract_port"], responses.SelfAwarenessResponseContractPort)

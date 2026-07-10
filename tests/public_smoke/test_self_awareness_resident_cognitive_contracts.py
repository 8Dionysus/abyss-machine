from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from abyss_machine import cli
from abyss_machine import self_awareness_resident_cognitive_contracts as cognitive


def _paths(tmp_path: Path) -> cognitive.SelfAwarenessResidentCognitivePaths:
    fields = cognitive.SelfAwarenessResidentCognitivePaths.__dataclass_fields__
    return cognitive.SelfAwarenessResidentCognitivePaths(
        **{name: tmp_path / name.replace("_", "-") for name in fields}
    )


def _config() -> cognitive.SelfAwarenessResidentCognitiveConfig:
    return cognitive.SelfAwarenessResidentCognitiveConfig("abyss_machine", "test")


def _contract_port() -> cognitive.SelfAwarenessResidentCognitiveContractPort:
    return cognitive.SelfAwarenessResidentCognitiveContractPort(
        completion_route_packet_issues=lambda *_args, **_kwargs: [],
        episode_body_trace=lambda **_kwargs: {"complete": True},
        body_trace_complete=lambda document: document.get("complete") is True,
        resident_worker_detail_complete=lambda document: document.get("complete") is True,
    )


def _complete_route_packet() -> dict[str, Any]:
    return {
        "schema": "abyss_machine_self_awareness_completion_route_packet_index_v1",
        "ok": True,
        "summary": {"packets": 1, "actions": 1, "covered_actions": 1},
        "packets": [
            {
                "packet_id": "packet-1",
                "route_id": "body.stack",
                "route_path": "body/stack",
                "action_ids": ["action-1"],
                "entity_ids": ["entity-1"],
                "event_ids": ["event-1"],
                "document_ids": ["document-1"],
                "verifier_commands": ["verify"],
                "evidence_refs": [{"path": "synthetic"}],
                "complete": True,
                "policy": {"host_layer_mutates_stack": False, "executes_commands": False},
            }
        ],
    }


def test_completion_route_context_uses_supplied_document_without_latest_read(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    audit = {
        "completion_route_packets": _complete_route_packet(),
        "completion_route_map": {"summary": {"routes": 1}},
        "action_backlog": {"summary": {"actions": 1}},
    }
    result = cognitive.resident_completion_route_context(
        audit,
        paths=paths,
        config=_config(),
        runtime_port=cognitive.SelfAwarenessResidentCognitiveRuntimePort(
            lambda *_args: pytest.fail("supplied audit must avoid latest read")
        ),
        contract_port=_contract_port(),
    )

    assert result["state"] == "with_packet"
    assert cognitive.resident_completion_route_context_complete(result, config=_config()) is True
    assert result["automation"]["executes_verifiers"] is False
    assert result["policy"]["host_layer_mutates_stack"] is False


def test_cycle_overlay_reads_latest_without_refresh_when_packets_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    replay = {
        "resident_cognitive_replay": {"complete": True},
        "body_trace_replay": {"replayable": True},
    }
    export = {
        "resident_cognitive_replay": {"complete": True},
        "portable_contract": {"response_entity_event_document_context_included": True},
        "body_trace_handoff": {
            "host_body_context_packet_included": True,
            "resident_body_trace_replayable": True,
            "response_body_trace_included": True,
        },
        "response_entity_event_document_handoff": {"complete": True},
    }
    reads: list[Path] = []
    monkeypatch.setattr(
        cognitive,
        "resident_cognitive_replay_complete",
        lambda packet, **_kwargs: packet.get("complete") is True,
    )
    documents = {paths.replay_latest: replay, paths.export_latest: export}

    overlay, replay_doc, export_doc = cognitive.resident_cognitive_cycle_chain_overlay(
        {"base": True},
        paths=paths,
        config=_config(),
        runtime_port=cognitive.SelfAwarenessResidentCognitiveRuntimePort(
            lambda path, _schema: reads.append(path) or documents[path]
        ),
        refresh_port=cognitive.SelfAwarenessResidentCognitiveRefreshPort(
            replay=lambda **_kwargs: pytest.fail("complete replay must not refresh"),
            export=lambda **_kwargs: pytest.fail("complete export must not refresh"),
        ),
        contract_port=_contract_port(),
    )

    assert reads == [paths.replay_latest, paths.export_latest]
    assert replay_doc is replay
    assert export_doc is export
    assert overlay == {
        "base": True,
        "resident_cognitive_replay": True,
        "resident_cognitive_export": True,
        "body_trace": True,
        "entity_event_document": True,
    }


def test_cycle_overlay_refreshes_incomplete_packets_only_when_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    calls: list[str] = []
    monkeypatch.setattr(
        cognitive,
        "resident_cognitive_replay_complete",
        lambda packet, **_kwargs: packet.get("complete") is True,
    )
    complete_replay = {"resident_cognitive_replay": {"complete": True}}
    complete_export = {
        "resident_cognitive_replay": {"complete": True},
        "portable_contract": {"response_entity_event_document_context_included": True},
    }

    overlay, _replay, _export = cognitive.resident_cognitive_cycle_chain_overlay(
        {},
        replay_doc={},
        export_doc={},
        write_latest=True,
        paths=paths,
        config=_config(),
        runtime_port=cognitive.SelfAwarenessResidentCognitiveRuntimePort(
            lambda *_args: pytest.fail("supplied docs avoid latest reads")
        ),
        refresh_port=cognitive.SelfAwarenessResidentCognitiveRefreshPort(
            replay=lambda **_kwargs: calls.append("replay") or complete_replay,
            export=lambda **_kwargs: calls.append("export") or complete_export,
        ),
        contract_port=_contract_port(),
    )

    assert calls == ["replay", "export"]
    assert overlay["resident_cognitive_replay"] is True
    assert overlay["resident_cognitive_export"] is True


def test_cli_completion_context_only_binds_typed_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_context(document: Any, **kwargs: Any) -> dict[str, Any]:
        captured["document"] = document
        captured.update(kwargs)
        return {"schema": "synthetic-context"}

    monkeypatch.setattr(cognitive, "resident_completion_route_context", fake_context)
    result = cli.self_awareness_resident_completion_route_context({"audit": True})

    assert result == {"schema": "synthetic-context"}
    assert captured["document"] == {"audit": True}
    assert isinstance(captured["paths"], cognitive.SelfAwarenessResidentCognitivePaths)
    assert isinstance(captured["config"], cognitive.SelfAwarenessResidentCognitiveConfig)
    assert isinstance(captured["runtime_port"], cognitive.SelfAwarenessResidentCognitiveRuntimePort)
    assert isinstance(captured["contract_port"], cognitive.SelfAwarenessResidentCognitiveContractPort)

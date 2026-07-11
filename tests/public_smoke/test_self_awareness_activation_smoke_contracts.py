from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from abyss_machine import cli
from abyss_machine import self_awareness_activation_smoke_contracts as activation


def _paths(tmp_path: Path) -> activation.SelfAwarenessActivationSmokePaths:
    fields = activation.SelfAwarenessActivationSmokePaths.__dataclass_fields__
    return activation.SelfAwarenessActivationSmokePaths(
        **{name: tmp_path / name.replace("_", "-") for name in fields}
    )


def _row(organ: dict[str, Any], *_args: Any, **_kwargs: Any) -> dict[str, Any]:
    service = str(organ.get("service"))
    return {
        "service": service,
        "complete": True,
        "investigation": {"actual_run": False, "thread_id": None},
        "replay": {"actual_run": False, "thread_id": None, "divergences": 0},
        "stack_organ_use_packet": {
            "schema": "abyss_machine_self_awareness_stack_organ_use_packet_v1",
            "service": service,
            "complete": True,
            "movement_selection": {
                "selected_for_episode": True,
                "selected_for_resident_reasoning": True,
                "categories": ["state_change"],
            },
            "activation_gap": {"classification": "runtime_present_not_deeply_used"},
        },
    }


def _contract_port() -> activation.SelfAwarenessActivationSmokeContractPort:
    return activation.SelfAwarenessActivationSmokeContractPort(
        activation_missing_episode_services=lambda _entries, _episodes: [],
        movement_smoke_row=_row,
        stack_organ_use_packet_complete=lambda packet: packet.get("complete") is True,
        activation_smoke_row_complete=lambda row: row.get("complete") is True,
        activation_smoke_compact=lambda row: {"service": row.get("service"), "complete": True},
        activation_smoke_complete=lambda document: document.get("ok") is True,
    )


def _documents(paths: activation.SelfAwarenessActivationSmokePaths) -> dict[Path, dict[str, Any]]:
    return {
        paths.stack_closure_dossier_latest: {
            "schema": "abyss_machine_self_awareness_stack_closure_dossier_v1",
            "working_stack_activation_dossier": {
                "entries": [{"service": "aoa-browser"}],
                "summary": {"open_activation_gaps": 1},
            },
        },
        paths.working_stack_latest: {
            "schema": "abyss_machine_self_awareness_working_stack_inventory_v1",
            "organs": [{"service": "aoa-browser"}],
        },
        paths.activation_smoke_latest: {"by_service": {}},
        paths.episodes_latest: {
            "schema": "abyss_machine_self_awareness_episodes_v1",
            "summary": {"working_stack_gap_episodes": 1},
        },
    }


def test_activation_smoke_uses_supplied_documents_and_persists(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    documents = _documents(paths)
    writes: list[tuple[Path, Path]] = []
    result = activation.activation_smoke(
        stack_closure_dossier_doc=documents[paths.stack_closure_dossier_latest],
        working_stack_doc=documents[paths.working_stack_latest],
        paths=paths,
        config=activation.SelfAwarenessActivationSmokeConfig("abyss_machine", "test"),
        runtime_port=activation.SelfAwarenessActivationSmokeRuntimePort(
            load_latest_json=lambda path, _schema: documents.get(path, {}),
            now_iso=lambda: "2026-07-11T04:00:00Z",
            write_latest_and_history=lambda _data, latest, root: writes.append((latest, root)) or [],
            host_name=lambda: "synthetic-host",
            process_id=lambda: 42,
        ),
        refresh_port=activation.SelfAwarenessActivationSmokeRefreshPort(
            stack_closure_dossier=lambda **_kwargs: pytest.fail("supplied dossier must be reused"),
            working_stack_inventory=lambda **_kwargs: pytest.fail("supplied inventory must be reused"),
            episodes=lambda **_kwargs: pytest.fail("complete episode identity must be reused"),
        ),
        contract_port=_contract_port(),
    )

    assert result["ok"] is True
    assert result["complete"] is True
    assert result["summary"]["all_stack_organs_have_use_packets"] is True
    assert result["summary"]["selected_for_resident_reasoning"] == ["aoa-browser"]
    assert result["policy"]["host_layer_mutates_stack"] is False
    assert writes == [(paths.activation_smoke_latest, paths.activation_smoke_root)]


def test_activation_smoke_refreshes_missing_documents(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    documents = _documents(paths)
    calls: list[str] = []
    result = activation.activation_smoke(
        write_latest=False,
        paths=paths,
        config=activation.SelfAwarenessActivationSmokeConfig("abyss_machine", "test"),
        runtime_port=activation.SelfAwarenessActivationSmokeRuntimePort(
            load_latest_json=lambda path, _schema: {} if path in {
                paths.stack_closure_dossier_latest,
                paths.working_stack_latest,
            } else documents.get(path, {}),
            now_iso=lambda: "2026-07-11T04:00:00Z",
            write_latest_and_history=lambda *_args: pytest.fail("write disabled"),
            host_name=lambda: "synthetic-host",
            process_id=lambda: 42,
        ),
        refresh_port=activation.SelfAwarenessActivationSmokeRefreshPort(
            stack_closure_dossier=lambda **_kwargs: calls.append("dossier") or documents[paths.stack_closure_dossier_latest],
            working_stack_inventory=lambda **_kwargs: calls.append("inventory") or documents[paths.working_stack_latest],
            episodes=lambda **_kwargs: calls.append("episodes") or documents[paths.episodes_latest],
        ),
        contract_port=_contract_port(),
    )

    assert calls == ["dossier", "inventory"]
    assert result["ok"] is True


def test_activation_smoke_projects_write_failure(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    documents = _documents(paths)
    result = activation.activation_smoke(
        stack_closure_dossier_doc=documents[paths.stack_closure_dossier_latest],
        working_stack_doc=documents[paths.working_stack_latest],
        paths=paths,
        config=activation.SelfAwarenessActivationSmokeConfig("abyss_machine", "test"),
        runtime_port=activation.SelfAwarenessActivationSmokeRuntimePort(
            load_latest_json=lambda path, _schema: documents.get(path, {}),
            now_iso=lambda: "2026-07-11T04:00:00Z",
            write_latest_and_history=lambda *_args: [{"error": "read-only"}],
            host_name=lambda: "synthetic-host",
            process_id=lambda: 42,
        ),
        refresh_port=activation.SelfAwarenessActivationSmokeRefreshPort(
            stack_closure_dossier=lambda **_kwargs: {},
            working_stack_inventory=lambda **_kwargs: {},
            episodes=lambda **_kwargs: {},
        ),
        contract_port=_contract_port(),
    )

    assert result["ok"] is False
    assert result["complete"] is False
    assert result["write_errors"] == [{"error": "read-only"}]


def test_cli_activation_smoke_only_binds_typed_ports(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_activation(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"schema": "synthetic-activation"}

    monkeypatch.setattr(activation, "activation_smoke", fake_activation)
    result = cli.self_awareness_activation_smoke(write_latest=False)

    assert result == {"schema": "synthetic-activation"}
    assert captured["write_latest"] is False
    assert isinstance(captured["paths"], activation.SelfAwarenessActivationSmokePaths)
    assert isinstance(captured["config"], activation.SelfAwarenessActivationSmokeConfig)
    assert isinstance(captured["runtime_port"], activation.SelfAwarenessActivationSmokeRuntimePort)
    assert isinstance(captured["refresh_port"], activation.SelfAwarenessActivationSmokeRefreshPort)
    assert isinstance(captured["contract_port"], activation.SelfAwarenessActivationSmokeContractPort)

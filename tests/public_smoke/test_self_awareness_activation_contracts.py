from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from abyss_machine import cli
from abyss_machine import self_awareness_activation_contracts as activation


def test_activation_contracts_classify_and_select_stack_organ_movement() -> None:
    organ = {
        "service": "tempo",
        "machine_usage_status": "runtime_degraded",
        "usage_gap": "trace backend is not ready",
        "runtime": {"container": "tempo", "running": False},
        "declared": {"present": True},
        "endpoint_probes": [{"probe": "ready", "ok": False, "status_code": 503}],
        "time_space_context_link": {"link_id": "saworklink-tempo"},
    }

    digest = activation.stack_organ_state_digest(organ)
    selection = activation.stack_organ_movement_selection(
        organ,
        current_state_digest=digest,
        previous_row=None,
        schema_prefix="abyss_machine",
    )

    assert activation.stack_organ_signal_route("tempo", organ) == {
        "signal": "trace_context",
        "source": "observability",
    }
    assert len(digest) == 24
    assert selection["selected_for_episode"] is True
    assert selection["selected_for_resident_reasoning"] is True
    assert selection["degradation_reasons"] == [
        "usage_gap",
        "runtime_not_running",
        "failed_endpoint_probe",
        "degraded_status",
    ]
    assert selection["policy"]["host_layer_mutates_stack"] is False


def test_activation_contracts_match_episode_identity_and_project_organ_entry() -> None:
    activation_entry = {
        "service": "grafana",
        "machine_usage_status": "runtime_present_not_deeply_used",
        "working_stack_link_id": "saworklink-grafana",
        "coverage_planes": ["working_stack", "service"],
    }
    episodes = {
        "episodes": [
            {
                "episode_id": "saepisode-grafana",
                "episode_kind": "working_stack_usage_gap",
                "working_stack_gap": activation_entry,
            }
        ]
    }
    organ = {
        "service": "grafana",
        "machine_usage_status": "runtime_present_not_deeply_used",
        "runtime": {"container": "grafana", "running": True},
        "endpoint_probes": [{"probe": "health", "ok": True}],
        "time_space_context_link": {"link_id": "fallback-link"},
    }

    assert (
        activation.working_stack_activation_episode_for_entry(
            activation_entry,
            episodes,
        )["episode_id"]
        == "saepisode-grafana"
    )
    assert activation.working_stack_activation_missing_episode_services(
        [activation_entry, {**activation_entry, "service": "loki"}],
        episodes,
    ) == ["loki"]

    entry = activation.working_stack_organ_entry(
        organ,
        activation_entry,
        state_digest=activation.stack_organ_state_digest,
    )
    assert entry["working_stack_link_id"] == "saworklink-grafana"
    assert entry["ok_probe_names"] == ["health"]
    assert entry["failed_probe_names"] == []
    assert entry["current_state_digest"]


def test_cli_activation_builders_only_bind_typed_contract_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_movement(
        organ: dict[str, Any],
        activation_entry: dict[str, Any] | None,
        previous_row: dict[str, Any] | None,
        *,
        generated_at: str,
        run_id: str,
        paths: activation.SelfAwarenessActivationPaths,
        config: activation.SelfAwarenessActivationConfig,
        contract_port: activation.SelfAwarenessActivationContractPort,
    ) -> dict[str, Any]:
        captured.update(
            organ=organ,
            activation_entry=activation_entry,
            previous_row=previous_row,
            generated_at=generated_at,
            run_id=run_id,
            paths=paths,
            config=config,
            contract_port=contract_port,
        )
        return {"schema": "synthetic-movement"}

    monkeypatch.setattr(activation, "working_stack_movement_smoke_row", fake_movement)
    result = cli.self_awareness_working_stack_movement_smoke_row(
        {"service": "grafana"},
        None,
        None,
        generated_at="2026-07-11T00:00:00Z",
        run_id="saactsmoke-test",
    )

    assert result == {"schema": "synthetic-movement"}
    assert captured["organ"] == {"service": "grafana"}
    assert isinstance(captured["paths"], activation.SelfAwarenessActivationPaths)
    assert isinstance(captured["config"], activation.SelfAwarenessActivationConfig)
    assert isinstance(
        captured["contract_port"], activation.SelfAwarenessActivationContractPort
    )
    assert all(isinstance(value, Path) for value in captured["paths"].__dict__.values())

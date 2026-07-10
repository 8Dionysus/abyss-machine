from __future__ import annotations

from typing import Any

import pytest

from abyss_machine import cli
from abyss_machine import self_awareness_resident_worker_contracts as resident


def _documents() -> tuple[dict[str, Any], ...]:
    status = {
        "ok": True,
        "status": "running",
        "profile": "gemma4.spark",
        "health": {
            "serving": {"owner": "abyss-stack", "base_url": "http://resident"},
            "health": {"status": "ok", "_http": {"ok": True, "status": 200, "latency_ms": 12.5}},
            "models": {
                "_http": {"ok": True, "status": 200, "latency_ms": 3.0},
                "data": [{"id": "gemma4-e2b-it", "meta": {"n_ctx": 4096}}],
            },
            "ok": True,
        },
    }
    monitor = {
        "status": {
            "ok": True,
            "status": "running",
            "service": {
                "active": "inactive",
                "monitor_timer": {"active": "active"},
                "digest_timer": {"active": "active"},
                "micro_timer": {"active": "active"},
            },
            "metrics": {"package_temp_c": 73.0},
        }
    }
    digest = {"ok": True, "status": "idle"}
    micro = {"ok": True, "summary": {"status": "ok", "candidate_readmodel": {"ok": True}}}
    evals = {"ok": True, "summary": {"overall_score": 1.0, "checks": 8, "fails": 0}}
    candidates = {"ok": True, "summary": {"candidates": 4, "action_execution": False}}
    return status, monitor, digest, micro, evals, candidates


def test_resident_worker_projection_is_complete_and_non_authoritative() -> None:
    config = resident.SelfAwarenessResidentWorkerConfig("abyss_machine")
    detail = resident.resident_worker_detail(*_documents(), config=config)

    assert resident.resident_worker_detail_complete(detail, config=config) is True
    assert detail["serving"]["stack_owned_serving"] is True
    assert detail["monitor"]["stack_owned_mode_legacy_service_expected_inactive"] is True
    assert detail["health"]["model_id"] == "gemma4-e2b-it"
    assert detail["candidate_context"]["action_execution"] is False
    assert detail["policy"]["host_layer_mutates_stack"] is False
    assert detail["policy"]["candidate_output_is_owner_truth"] is False


def test_resident_worker_projection_rejects_action_execution() -> None:
    documents = list(_documents())
    documents[-1] = {"ok": True, "summary": {"candidates": 4, "action_execution": True}}
    config = resident.SelfAwarenessResidentWorkerConfig("abyss_machine")
    detail = resident.resident_worker_detail(*documents, config=config)

    assert detail["ok"] is False
    assert resident.resident_worker_detail_complete(detail, config=config) is False


def test_cli_resident_worker_helpers_only_bind_config(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_detail(*documents: dict[str, Any], config: Any) -> dict[str, Any]:
        captured["documents"] = documents
        captured["config"] = config
        return {"schema": "synthetic-resident"}

    def fake_complete(detail: dict[str, Any], *, config: Any) -> bool:
        captured["complete_detail"] = detail
        captured["complete_config"] = config
        return True

    monkeypatch.setattr(resident, "resident_worker_detail", fake_detail)
    monkeypatch.setattr(resident, "resident_worker_detail_complete", fake_complete)
    documents = _documents()

    assert cli.self_awareness_resident_worker_detail(*documents) == {
        "schema": "synthetic-resident"
    }
    assert cli.self_awareness_resident_worker_detail_complete({"ok": True}) is True
    assert isinstance(captured["config"], resident.SelfAwarenessResidentWorkerConfig)
    assert isinstance(captured["complete_config"], resident.SelfAwarenessResidentWorkerConfig)

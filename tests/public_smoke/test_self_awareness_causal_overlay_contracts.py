from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from abyss_machine import cli
from abyss_machine import self_awareness_causal_overlay_contracts as overlays


def _paths(tmp_path: Path) -> overlays.SelfAwarenessCausalOverlayPaths:
    names = {
        "maps_latest": "maps",
        "rag_trace_latest": "rag-trace",
        "rag_validate_latest": "rag-validate",
        "graph_latest": "graph",
        "memory_latest": "memory",
        "nervous_brief_latest": "nervous-brief",
        "nervous_semantic_maintain_latest": "semantic-maintain",
        "requirements_latest": "requirements",
        "process_container_latest": "containers",
        "ai_capabilities_latest": "ai-capabilities",
        "requirement_probes_latest": "requirement-probes",
        "brief_latest": "brief",
    }
    return overlays.SelfAwarenessCausalOverlayPaths(
        **{key: tmp_path / value / "latest.json" for key, value in names.items()}
    )


def _config() -> overlays.SelfAwarenessCausalOverlayConfig:
    return overlays.SelfAwarenessCausalOverlayConfig(
        schema_prefix="abyss_machine",
        version="0.test",
        memory_space_required_gates=(
            "graph",
            "maps",
            "memory_status",
            "nervous_freshness",
            "rag_trace",
            "rag_validate",
        ),
        semantic_maintain_review_command="abyss-machine nervous semantic-maintain --json",
        semantic_maintain_retry_command="abyss-machine nervous semantic-maintain --apply --json",
    )


def _ports(
    reads: list[Path],
) -> tuple[
    overlays.SelfAwarenessCausalOverlayRuntimePort,
    overlays.SelfAwarenessCausalOverlayRefreshPort,
    overlays.SelfAwarenessCausalOverlayContractPort,
]:
    def load_latest_json(path: Path, _schema: str) -> dict[str, Any]:
        reads.append(path)
        return {}

    def artifact_ref(path: Path, document: dict[str, Any], truth_level: str) -> dict[str, Any]:
        return {"path": str(path), "schema": document.get("schema"), "truth_level": truth_level}

    def freshness_gate(
        gate_id: str,
        title: str,
        path: Path,
        _document: dict[str, Any],
        truth_level: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return {
            "gate_id": gate_id,
            "title": title,
            "path": str(path),
            "truth_level": truth_level,
            "blocks_deep_reasoning": bool(kwargs.get("stale")),
            "evidence_refs": kwargs.get("evidence_refs", []),
        }

    return (
        overlays.SelfAwarenessCausalOverlayRuntimePort(
            load_latest_json=load_latest_json,
            now_iso=lambda: "2026-07-10T10:30:00-06:00",
        ),
        overlays.SelfAwarenessCausalOverlayRefreshPort(
            load_events=lambda **_: [],
            requirement_probes=lambda **_: {},
        ),
        overlays.SelfAwarenessCausalOverlayContractPort(
            match_score=lambda *_: 1,
            artifact_ref=artifact_ref,
            redact_text=lambda value, _limit: str(value),
            freshness_gate=freshness_gate,
            brief_stack_handoff_action_map=lambda _probes: {},
            time_bucket=lambda _value: "2026-07-10T10:30:00Z",
            stack_handoff_impacted_services=lambda _requirement_id: ["trace-backend"],
        ),
    )


def test_memory_space_overlay_uses_supplied_documents_without_latest_reads(
    tmp_path: Path,
) -> None:
    reads: list[Path] = []
    runtime_port, refresh_port, contract_port = _ports(reads)
    event = {
        "event_id": "event-1",
        "fabric": {
            "entity": {"service": "rag-api"},
            "temporal": {"time_bucket": "2026-07-10T10:30:00Z"},
            "context_links": {"correlation_keys": ["trace:1"]},
        },
        "evidence_refs": [],
    }
    rag_trace = {
        "schema": "abyss_machine_rag_trace_v1",
        "ok": True,
        "packet": {"entries": [{"id": "packet-1", "axis": "by-rag-run"}]},
    }

    document = overlays.memory_space_overlay(
        [event],
        maps={"schema": "abyss_machine_maps_v1", "ok": True, "entries_by_axis": {}},
        rag_trace=rag_trace,
        rag_validate_doc={"schema": "abyss_machine_rag_validate_v1", "ok": True},
        graph={"schema": "abyss_machine_graph_v1", "ok": True},
        memory_latest={"schema": "abyss_machine_memory_status_v1", "ok": True},
        nervous={"schema": "abyss_machine_nervous_brief_v1", "readiness": {"semantic_stale": False}},
        nervous_semantic_maintain={"schema": "abyss_machine_nervous_semantic_maintain_v1"},
        requirements={"schema": "abyss_machine_self_awareness_requirements_v1", "requirements": []},
        containers={"schema": "abyss_machine_process_container_health_v1"},
        paths=_paths(tmp_path),
        config=_config(),
        runtime_port=runtime_port,
        refresh_port=refresh_port,
        contract_port=contract_port,
    )

    assert document["ok"] is True
    assert document["summary"]["events"] == 1
    assert document["summary"]["retrieval_packets"] == 1
    assert document["summary"]["freshness_gates"] == 6
    assert document["policy"]["memory_writeback"] is False
    assert document["policy"]["host_layer_mutates_stack"] is False
    assert reads == []


def test_stack_handoff_overlay_builds_non_mutating_time_space_graph(
    tmp_path: Path,
) -> None:
    reads: list[Path] = []
    runtime_port, refresh_port, contract_port = _ports(reads)
    action = {
        "id": "action-trace",
        "requirement_id": "stack.trace-backend",
        "owner_route": "abyss-stack",
        "priority_rank": 1,
        "priority_class": "critical_trace_join",
        "coverage_impact": {"organ": "trace_join_backbone", "coverage_planes": ["signal_fabric"]},
        "closure_blocker_keys": ["trace_backend_ready"],
        "runbook_candidate": {"id": "runbook-trace", "machine_executes_stack_change": False, "host_layer_mutates_stack": False},
        "policy": {"host_layer_mutates_stack": False, "executes_commands": False},
        "evidence_refs": [],
    }
    contract_port = overlays.SelfAwarenessCausalOverlayContractPort(
        **{
            **contract_port.__dict__,
            "brief_stack_handoff_action_map": lambda _probes: {
                "schema": "abyss_machine_self_awareness_brief_stack_handoff_action_map_v1",
                "status": "open_requirements",
                "summary": {"top_requirement_id": "stack.trace-backend"},
                "actions": [action],
                "open_requirement_ids": ["stack.trace-backend"],
                "policy": {"host_layer_mutates_stack": False, "executes_commands": False},
            },
        }
    )

    document = overlays.stack_handoff_time_space_overlay(
        {"schema": "abyss_machine_self_awareness_requirement_probes_v1"},
        generated_at="2026-07-10T10:30:00-06:00",
        paths=_paths(tmp_path),
        config=_config(),
        runtime_port=runtime_port,
        refresh_port=refresh_port,
        contract_port=contract_port,
    )

    assert document["ok"] is True
    assert document["summary"]["open_stack_requirements"] == 1
    assert document["timeline_markers"][0]["requirement_id"] == "stack.trace-backend"
    assert any(node["id"] == "service:trace-backend" for node in document["spatial_nodes"])
    assert any(node["id"] == "coverage_plane:signal_fabric" for node in document["spatial_nodes"])
    assert document["policy"]["executes_commands"] is False
    assert reads == []


@pytest.mark.parametrize(
    ("cli_name", "module_name"),
    [
        ("self_awareness_memory_space_overlay", "memory_space_overlay"),
        ("self_awareness_stack_handoff_time_space_overlay", "stack_handoff_time_space_overlay"),
    ],
)
def test_cli_causal_overlays_only_bind_current_ports(
    monkeypatch: pytest.MonkeyPatch,
    cli_name: str,
    module_name: str,
) -> None:
    captured: dict[str, Any] = {}

    def fake_overlay(*_args: Any, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"schema": "synthetic"}

    monkeypatch.setattr(overlays, module_name, fake_overlay)

    document = getattr(cli, cli_name)()

    assert document == {"schema": "synthetic"}
    assert isinstance(captured["paths"], overlays.SelfAwarenessCausalOverlayPaths)
    assert isinstance(captured["config"], overlays.SelfAwarenessCausalOverlayConfig)
    assert isinstance(captured["runtime_port"], overlays.SelfAwarenessCausalOverlayRuntimePort)
    assert isinstance(captured["refresh_port"], overlays.SelfAwarenessCausalOverlayRefreshPort)
    assert isinstance(captured["contract_port"], overlays.SelfAwarenessCausalOverlayContractPort)

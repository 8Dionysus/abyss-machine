from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from abyss_machine import cli
from abyss_machine import self_awareness_brief_contracts as brief


def _paths(tmp_path: Path) -> brief.SelfAwarenessBriefPaths:
    names = (
        "timeline_latest",
        "spatial_graph_latest",
        "context_latest",
        "episodes_latest",
        "alerts_latest",
        "reactions_latest",
        "stack_observability_latest",
        "capabilities_latest",
        "requirement_probes_latest",
        "export_latest",
        "ai_capabilities_latest",
        "llm_resident_status_latest",
        "rag_validate_latest",
        "nervous_brief_latest",
        "probe_latest",
        "brief_latest",
        "brief_root",
    )
    return brief.SelfAwarenessBriefPaths(
        **{name: tmp_path / name.replace("_", "-") for name in names}
    )


def _contract_port() -> brief.SelfAwarenessBriefContractPort:
    return brief.SelfAwarenessBriefContractPort(
        memory_space_freshness_handoff=lambda context: {
            "schema": "memory-space-freshness",
            "summary": {"blocked": 0},
            "context_schema": context.get("schema"),
        },
        stack_requirement_coverage_impact=lambda requirement_id: {
            "schema": "coverage-impact",
            "requirement_id": requirement_id,
            "organ": "trace" if requirement_id == "stack.trace-backend" else "dashboard",
            "coverage_planes": ["trace"],
        },
        stack_coverage_impact_complete=lambda impact: bool(impact.get("requirement_id")),
    )


def _runtime_port(
    documents: dict[Path, dict[str, Any]],
    *,
    writes: list[tuple[Path, Path]] | None = None,
    errors: list[dict[str, Any]] | None = None,
) -> brief.SelfAwarenessBriefRuntimePort:
    return brief.SelfAwarenessBriefRuntimePort(
        load_latest_json=lambda path, _schema: documents.get(path, {}),
        now_iso=lambda: "2026-07-10T22:30:00Z",
        write_latest_and_history=lambda _data, latest, root: (
            writes.append((latest, root)) if writes is not None else None
        )
        or list(errors or []),
    )


def test_stack_handoff_action_map_prioritizes_open_trace_blocker(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    probes = {
        "ok": True,
        "schema": "requirement-probes",
        "probes": [
            {
                "id": "stack.grafana.datasource-read",
                "owner": "abyss-stack",
                "checks": [{"key": "datasource", "ok": False, "level": "open"}],
                "acceptance_verifiers": [{"command": "verify-grafana"}],
            },
            {
                "id": "stack.trace-backend",
                "owner": "abyss-stack",
                "checks": [
                    {"key": "trace", "ok": False, "level": "open"},
                    {"key": "langchain_trace_backend_coupled", "ok": False, "level": "warn"},
                ],
                "acceptance_verifiers": [{"command": "verify-trace"}],
            },
            {
                "id": "stack.database-graph.read-route",
                "closed_by_current_probe": True,
                "acceptance_verifiers": [{"command": "verify-database"}],
            },
        ],
    }

    result = brief.build_stack_handoff_action_map(
        probes,
        paths=paths,
        config=brief.SelfAwarenessBriefConfig("abyss_machine", "test"),
        runtime_port=_runtime_port({}),
        contract_port=_contract_port(),
    )

    assert result["status"] == "open_requirements"
    assert result["open_requirement_ids"] == [
        "stack.trace-backend",
        "stack.grafana.datasource-read",
    ]
    assert result["actions"][0]["priority_class"] == "critical_trace_join"
    assert result["actions"][0]["priority_rank"] == 1
    assert result["summary"]["blocked_coverage_planes"] == ["trace"]
    assert result["safe_next_action"]["host_layer_mutates_stack"] is False
    assert result["ok"] is True


def test_brief_refreshes_inputs_builds_claims_and_persists(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    documents = {
        paths.stack_observability_latest: {"ok": True, "summary": {"status": "ready"}},
        paths.reactions_latest: {"summary": {"candidates": 2}},
        paths.capabilities_latest: {
            "schema": "capabilities",
            "summary": {"capabilities": 8, "requirements": 0},
        },
        paths.ai_capabilities_latest: {
            "ok": True,
            "capabilities": {"text": {}, "audio": {}},
        },
        paths.llm_resident_status_latest: {"status": "running", "model": "warm-e2b"},
        paths.rag_validate_latest: {"ok": True, "summary": {"status": "ready"}},
        paths.nervous_brief_latest: {
            "readiness": {"status": "ready", "semantic_maintenance_needed": False}
        },
    }
    calls: list[str] = []
    writes: list[tuple[Path, Path]] = []

    def refresh(name: str, document: dict[str, Any]):
        def callback(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            calls.append(name)
            return document

        return callback

    result = brief.brief(
        paths=paths,
        config=brief.SelfAwarenessBriefConfig("abyss_machine", "test"),
        runtime_port=_runtime_port(documents, writes=writes),
        refresh_port=brief.SelfAwarenessBriefRefreshPort(
            timeline=refresh(
                "timeline",
                {"ok": True, "summary": {"events": 4, "latest_event_time": "now"}},
            ),
            spatial_graph=refresh(
                "graph", {"ok": True, "summary": {"nodes": 3, "edges": 2}}
            ),
            context=refresh(
                "context",
                {
                    "schema": "context",
                    "summary": {
                        "degraded": False,
                        "memory_space": {
                            "retrieval_packets": 2,
                            "freshness_gates": 1,
                            "blocked_gates": 0,
                        },
                    },
                },
            ),
            episodes=refresh(
                "episodes", {"summary": {"episodes": 2, "high_confidence": 1}}
            ),
            alerts=refresh("alerts", {"summary": {"reaction_candidates": 2}}),
            requirement_probes=refresh(
                "probes", {"ok": True, "schema": "probes", "probes": []}
            ),
        ),
        contract_port=_contract_port(),
    )

    assert calls == ["timeline", "graph", "context", "episodes", "alerts", "probes"]
    assert result["summary"] == {
        "status": "ready",
        "claims": 12,
        "missing_evidence": 0,
        "episodes": 2,
        "reaction_candidates": 2,
        "stack_handoff_open": 0,
        "stack_handoff_actions": 0,
        "stack_handoff_verifier_steps": 0,
    }
    assert all(claim["refs"] for claim in result["claims"])
    assert result["safe_next_action"]["kind"] == "no_open_stack_handoff"
    assert result["policy"]["host_layer_mutates_stack"] is False
    assert writes == [(paths.brief_latest, paths.brief_root)]


def test_brief_projects_persistence_failure(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    refresh_port = brief.SelfAwarenessBriefRefreshPort(
        timeline=lambda **_kwargs: {"ok": True},
        spatial_graph=lambda **_kwargs: {"ok": True},
        context=lambda **_kwargs: {"summary": {}},
        episodes=lambda **_kwargs: {"summary": {}},
        alerts=lambda **_kwargs: {"summary": {}},
        requirement_probes=lambda **_kwargs: {"ok": True, "probes": []},
    )
    result = brief.brief(
        paths=paths,
        config=brief.SelfAwarenessBriefConfig("abyss_machine", "test"),
        runtime_port=_runtime_port({}, errors=[{"error": "read-only"}]),
        refresh_port=refresh_port,
        contract_port=_contract_port(),
    )

    assert result["ok"] is False
    assert result["write_errors"] == [{"error": "read-only"}]


def test_cli_brief_helpers_only_bind_typed_ports(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_map: dict[str, Any] = {}
    captured_brief: dict[str, Any] = {}

    def fake_map(requirement_probes: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        captured_map["requirement_probes"] = requirement_probes
        captured_map.update(kwargs)
        return {"schema": "synthetic-map"}

    def fake_brief(**kwargs: Any) -> dict[str, Any]:
        captured_brief.update(kwargs)
        return {"schema": "synthetic-brief"}

    monkeypatch.setattr(brief, "build_stack_handoff_action_map", fake_map)
    monkeypatch.setattr(brief, "brief", fake_brief)

    assert cli.self_awareness_brief_stack_handoff_action_map({"probes": []}) == {
        "schema": "synthetic-map"
    }
    assert cli.self_awareness_brief(write_latest=False) == {"schema": "synthetic-brief"}
    assert isinstance(captured_map["paths"], brief.SelfAwarenessBriefPaths)
    assert isinstance(captured_map["config"], brief.SelfAwarenessBriefConfig)
    assert isinstance(captured_map["runtime_port"], brief.SelfAwarenessBriefRuntimePort)
    assert isinstance(captured_map["contract_port"], brief.SelfAwarenessBriefContractPort)
    assert captured_brief["write_latest"] is False
    assert isinstance(captured_brief["refresh_port"], brief.SelfAwarenessBriefRefreshPort)

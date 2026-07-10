from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from abyss_machine import cli
from abyss_machine import self_awareness_trace_context_contracts as trace_context


def _paths(tmp_path: Path) -> trace_context.SelfAwarenessTraceContextPaths:
    return trace_context.SelfAwarenessTraceContextPaths(
        stack_observability_latest=tmp_path / "stack" / "latest.json",
        requirement_probes_latest=tmp_path / "requirements" / "latest.json",
        probe_latest=tmp_path / "probe" / "latest.json",
        context_latest=tmp_path / "context" / "latest.json",
        timeline_latest=tmp_path / "timeline" / "latest.json",
        episodes_latest=tmp_path / "episodes" / "latest.json",
        capabilities_latest=tmp_path / "capabilities" / "latest.json",
        trace_context_latest=tmp_path / "trace-context" / "latest.json",
        trace_context_root=tmp_path / "trace-context",
    )


def _ports(
    reads: list[Path],
    refreshes: list[str],
    writes: list[tuple[Path, Path]],
    *,
    capabilities: dict[str, Any] | None = None,
) -> tuple[
    trace_context.SelfAwarenessTraceContextRuntimePort,
    trace_context.SelfAwarenessTraceContextRefreshPort,
    trace_context.SelfAwarenessTraceContextContractPort,
    trace_context.SelfAwarenessTraceContextPersistencePort,
]:
    def load_latest_json(path: Path, _schema: str) -> dict[str, Any]:
        reads.append(path)
        return capabilities or {}

    def refresh(name: str) -> Any:
        def callback(**_kwargs: Any) -> dict[str, Any]:
            refreshes.append(name)
            return {}

        return callback

    def write_latest_and_history(
        _document: dict[str, Any],
        latest: Path,
        root: Path,
    ) -> list[str]:
        writes.append((latest, root))
        return []

    return (
        trace_context.SelfAwarenessTraceContextRuntimePort(
            load_latest_json=load_latest_json,
            now_iso=lambda: "2026-07-10T13:00:00-06:00",
        ),
        trace_context.SelfAwarenessTraceContextRefreshPort(
            stack_observability=refresh("stack"),
            requirement_probes=refresh("requirements"),
        ),
        trace_context.SelfAwarenessTraceContextContractPort(
            stack_requirement_coverage_impact=lambda _requirement_id: {
                "organ": "trace_join_backbone",
                "coverage_planes": ["signal_fabric", "causal_spine"],
            }
        ),
        trace_context.SelfAwarenessTraceContextPersistencePort(
            write_latest_and_history=write_latest_and_history,
        ),
    )


def _documents(*, trace_closed: bool = False) -> dict[str, dict[str, Any]]:
    traceparent = "00-" + ("a" * 32) + "-" + ("b" * 16) + "-01"
    current_state = {
        "metrics_log_pipeline_readable": True,
        "alloy_seen": True,
        "traceparent_log_query_ok": True,
        "traceparent_log_entries_seen": 1 if trace_closed else 0,
        "trace_context_query_safe_empty": not trace_closed,
        "trace_backend_ready": trace_closed,
        "trace_search_readable": trace_closed,
        "span_log_metric_join_supported": trace_closed,
    }
    return {
        "stack": {
            "schema": "abyss_machine_stack_observability_v1",
            "summary": {
                "promql_jobs_up": ["prometheus", "grafana", "loki", "alloy"],
                "logql_queries_ok": 1,
                "logql_entries_seen": 1,
            },
            "loki": {
                "trace_context": {
                    "ok": True,
                    "entry_count": current_state["traceparent_log_entries_seen"],
                    "samples": [
                        {
                            "ts": "1",
                            "labels": {"container": "route-api"},
                            "line_hash": "abc123",
                            "line_preview": "private raw line",
                        }
                    ],
                }
            },
        },
        "requirements": {
            "schema": "abyss_machine_self_awareness_requirement_probes_v1",
            "probes": [
                {
                    "id": "stack.trace-backend",
                    "owner": "abyss-stack",
                    "status": "closed_by_current_probe" if trace_closed else "open",
                    "closed_by_current_probe": trace_closed,
                    "probe_kind": "trace_backend_inventory",
                    "current_state": current_state,
                    "checks": [],
                    "closure_readiness": {"missing_checks": [] if trace_closed else ["trace_backend_ready"]},
                }
            ],
            "open_requirements": [
                {
                    "id": "stack.grafana.datasource-read",
                    "owner": "abyss-stack",
                    "safe_next_action": {
                        "owner_route": "abyss-stack",
                        "command": "abyss-machine self-awareness requirement-probes --json",
                        "stack_command_candidate": "expose bounded datasource inventory",
                    },
                }
            ],
        },
        "probe": {
            "schema": "abyss_machine_self_awareness_probe_v1",
            "ok": True,
            "run_id": "probe-1",
            "traceparent": traceparent,
        },
        "context": {
            "schema": "abyss_machine_self_awareness_context_v1",
            "contexts": [{"context": {"traceparent": traceparent, "trace_id": "a" * 32}}],
        },
        "timeline": {"schema": "abyss_machine_self_awareness_timeline_v1", "events": []},
        "episodes": {"schema": "abyss_machine_self_awareness_episodes_v1", "episodes": []},
    }


def test_trace_context_links_are_bounded_and_do_not_copy_unrelated_payload() -> None:
    traceparent = "00-" + ("a" * 32) + "-" + ("b" * 16) + "-01"
    document = {
        "event": {
            "event_id": "event-1",
            "context": {"traceparent": traceparent, "trace_id": "a" * 32},
            "raw": "must not be copied",
        }
    }

    links = trace_context.trace_context_links_from_doc("fixture", document, limit=1)

    assert len(links) == 1
    assert links[0]["event_id"] == "event-1"
    assert links[0]["traceparent"] == traceparent
    assert "raw" not in links[0]


def test_trace_context_uses_supplied_documents_and_routes_single_write(tmp_path: Path) -> None:
    reads: list[Path] = []
    refreshes: list[str] = []
    writes: list[tuple[Path, Path]] = []
    runtime_port, refresh_port, contract_port, persistence_port = _ports(
        reads,
        refreshes,
        writes,
    )
    paths = _paths(tmp_path)
    documents = _documents()

    payload = trace_context.trace_context_fallback(
        True,
        stack_observability_doc=documents["stack"],
        requirement_probes_doc=documents["requirements"],
        probe_doc=documents["probe"],
        context_doc=documents["context"],
        timeline_doc=documents["timeline"],
        episodes_doc=documents["episodes"],
        paths=paths,
        config=trace_context.SelfAwarenessTraceContextConfig("abyss_machine", "0.test"),
        runtime_port=runtime_port,
        refresh_port=refresh_port,
        contract_port=contract_port,
        persistence_port=persistence_port,
    )

    assert payload["ok"] is True
    assert payload["status"] == "fallback_ready_stack_trace_backend_open"
    assert payload["summary"]["stack_requirement_not_closed_by_fallback"] is True
    assert payload["fallback"]["loki_trace_context"]["samples"] == [
        {"ts": "1", "labels": {"container": "route-api"}, "line_hash": "abc123"}
    ]
    assert trace_context.trace_context_fallback_complete(
        payload,
        schema_prefix="abyss_machine",
    ) is True
    assert reads == []
    assert refreshes == []
    assert writes == [(paths.trace_context_latest, paths.trace_context_root)]


def test_trace_context_capabilities_fallback_reads_only_capabilities(tmp_path: Path) -> None:
    reads: list[Path] = []
    refreshes: list[str] = []
    writes: list[tuple[Path, Path]] = []
    paths = _paths(tmp_path)
    capabilities = {
        "raw": {
            "trace_backend": {
                "join_readiness": {
                    "trace_backend_ready": True,
                    "trace_search_readable": True,
                    "span_log_metric_join_supported": True,
                    "missing": [],
                },
                "pipeline_evidence": {"metrics_log_pipeline_readable": True},
                "trace_context": {
                    "traceparent_log_query_ok": True,
                    "traceparent_log_entries_seen": 1,
                },
            }
        }
    }
    runtime_port, refresh_port, contract_port, persistence_port = _ports(
        reads,
        refreshes,
        writes,
        capabilities=capabilities,
    )
    documents = _documents(trace_closed=True)
    documents["requirements"]["probes"] = []

    payload = trace_context.trace_context_fallback(
        False,
        stack_observability_doc=documents["stack"],
        requirement_probes_doc=documents["requirements"],
        probe_doc=documents["probe"],
        context_doc=documents["context"],
        timeline_doc=documents["timeline"],
        episodes_doc=documents["episodes"],
        paths=paths,
        config=trace_context.SelfAwarenessTraceContextConfig("abyss_machine", "0.test"),
        runtime_port=runtime_port,
        refresh_port=refresh_port,
        contract_port=contract_port,
        persistence_port=persistence_port,
    )

    assert payload["status"] == "stack_trace_backend_ready_observed"
    assert payload["safe_next_action"]["requirement_id"] == "stack.grafana.datasource-read"
    assert reads == [paths.capabilities_latest]
    assert refreshes == []
    assert writes == []


def test_cli_trace_context_fallback_only_binds_current_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_fallback(*_args: Any, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"schema": "synthetic"}

    monkeypatch.setattr(trace_context, "trace_context_fallback", fake_fallback)

    document = cli.self_awareness_trace_context_fallback(False)

    assert document == {"schema": "synthetic"}
    assert isinstance(captured["paths"], trace_context.SelfAwarenessTraceContextPaths)
    assert isinstance(captured["config"], trace_context.SelfAwarenessTraceContextConfig)
    assert isinstance(captured["runtime_port"], trace_context.SelfAwarenessTraceContextRuntimePort)
    assert isinstance(captured["refresh_port"], trace_context.SelfAwarenessTraceContextRefreshPort)
    assert isinstance(captured["contract_port"], trace_context.SelfAwarenessTraceContextContractPort)
    assert isinstance(
        captured["persistence_port"],
        trace_context.SelfAwarenessTraceContextPersistencePort,
    )


def test_cli_trace_context_helpers_delegate_schema_and_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_links(name: str, document: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
        captured["links"] = (name, document, limit)
        return [{"id": "synthetic"}]

    def fake_complete(document: Any, *, schema_prefix: str) -> bool:
        captured["complete"] = (document, schema_prefix)
        return True

    monkeypatch.setattr(trace_context, "trace_context_links_from_doc", fake_links)
    monkeypatch.setattr(trace_context, "trace_context_fallback_complete", fake_complete)

    assert cli.self_awareness_trace_context_links_from_doc("fixture", {"id": 1}, limit=3) == [
        {"id": "synthetic"}
    ]
    assert cli.self_awareness_trace_context_fallback_complete({"schema": "fixture"}) is True
    assert captured == {
        "links": ("fixture", {"id": 1}, 3),
        "complete": ({"schema": "fixture"}, "abyss_machine"),
    }

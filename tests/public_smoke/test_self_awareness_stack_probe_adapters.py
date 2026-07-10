from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from abyss_machine import cli
from abyss_machine import self_awareness_stack_probe_adapters as probes


def _config(tmp_path: Path) -> probes.SelfAwarenessStackProbeConfig:
    return probes.SelfAwarenessStackProbeConfig(
        schema_prefix="abyss_machine",
        version="0.test",
        route_api_url="http://route.test",
        rag_api_url="http://rag.test",
        langchain_api_url="http://langchain.test",
        neo4j_url="http://neo4j.test",
        postgres_host="postgres.test",
        postgres_port=5432,
        tempo_url="http://tempo.test",
        alertmanager_url="http://alertmanager.test",
        grafana_url="http://grafana.test",
        loki_url="http://loki.test",
        prometheus_url="http://prometheus.test",
        stack_observability_latest=tmp_path / "stack-observability" / "latest.json",
        closure_evidence_config=tmp_path / "stack-closure-evidence.json",
    )


def _runtime(
    *,
    http_json: Any | None = None,
    path_exists: Any | None = None,
    path_stat: Any | None = None,
    load_json_document: Any | None = None,
    secret_search: Any | None = None,
) -> probes.SelfAwarenessStackProbeRuntimePort:
    return probes.SelfAwarenessStackProbeRuntimePort(
        http_json=http_json or (lambda url, **_: {"ok": False, "url": url}),
        socket_create_connection=lambda *_args, **_kwargs: None,
        monotonic=lambda: 1.0,
        time_now=lambda: 1_800_000_000.0,
        path_exists=path_exists or (lambda _path: False),
        path_stat=path_stat or (lambda _path: SimpleNamespace(st_size=0, st_mtime=0.0)),
        load_json_document=load_json_document or (lambda _path: ({}, None)),
        now_iso=lambda: "2026-07-10T09:30:00-06:00",
        daily_jsonl_path=lambda root: root / "2026" / "07" / "2026-07-10.jsonl",
        secret_search=secret_search or (lambda _text: None),
    )


def test_capability_matrix_uses_metadata_ports_without_reading_artifact_bodies(
    tmp_path: Path,
) -> None:
    latest = tmp_path / "private" / "latest.json"
    today = latest.parent / "2026" / "07" / "2026-07-10.jsonl"
    existing = {latest, today}
    runtime = _runtime(
        path_exists=lambda path: path in existing,
        path_stat=lambda _path: SimpleNamespace(
            st_size=128,
            st_mtime=1_799_999_940.0,
        ),
    )

    document = probes.capability_matrix(
        "stack.trace-backend",
        "abyss-stack",
        [{"path": str(latest), "schema": "trace_v1"}],
        {"trace_backend_ready": True},
        endpoints=[{"url": "http://tempo.test/ready", "status_code": 200}],
        config=_config(tmp_path),
        runtime_port=runtime,
    )

    assert document["schema"] == "abyss_machine_self_awareness_capability_matrix_row_v1"
    assert document["latest_artifacts"][0]["size_bytes"] == 128
    assert document["latest_artifacts"][0]["age_seconds"] == 60.0
    assert document["history"]["history_available"] is True
    assert document["endpoints"][0]["body_stored"] is False
    assert document["access"]["stores_raw_private_payload"] is False


def test_langchain_probe_builds_runtime_shape_from_fake_http_port(tmp_path: Path) -> None:
    payloads = {
        "http://langchain.test/health": {
            "service": "langchain-api",
            "federated_run_enabled": True,
        },
        "http://langchain.test/openapi.json": {
            "paths": {
                "/run": {"post": {}},
                "/run/federated": {"post": {}},
                "/embeddings": {"post": {}},
            },
            "components": {"schemas": {"RunReq": {}, "FederatedRunReq": {}}},
        },
    }

    def http_json(url: str, **_: Any) -> dict[str, Any]:
        return {"ok": True, "url": url, "status_code": 200, "json": payloads[url]}

    document = probes.langchain_api_probe(
        config=_config(tmp_path),
        runtime_port=_runtime(http_json=http_json),
    )

    assert document["ok"] is True
    assert document["runtime_surface"]["run_route_present"] is True
    assert document["runtime_surface"]["federated_run_route_present"] is True
    assert document["runtime_surface"]["embeddings_route_present"] is True
    assert document["redaction"]["raw_prompt_payloads_stored"] is False


def test_external_closure_evidence_accepts_only_bounded_stack_owned_rows(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    source_document = {
        "entries": [
            {
                "schema": "abyss_machine_stack_requirement_closure_evidence_v1",
                "requirement_id": "stack.trace-backend",
                "owner_route": "abyss-stack",
                "checks": {"trace_backend_ready": True},
                "current_state": {
                    "trace_backend_ready": True,
                    "private_payload": "must-not-project",
                },
                "evidence_refs": [{"path": "/synthetic/trace.json", "sha256": "abc"}],
                "policy": {
                    "bounded": True,
                    "host_layer_mutates_stack": False,
                    "raw_payloads_included": False,
                    "raw_secrets_included": False,
                },
            }
        ]
    }
    runtime = _runtime(
        path_exists=lambda path: path == config.closure_evidence_config,
        path_stat=lambda _path: SimpleNamespace(st_size=512, st_mtime=0.0),
        load_json_document=lambda _path: (source_document, None),
    )

    document = probes.stack_closure_external_evidence(
        config=config,
        runtime_port=runtime,
    )

    row = document["entries"]["stack.trace-backend"]
    assert document["status"] == "loaded"
    assert document["summary"]["accepted"] == 1
    assert row["accepted"] is True
    assert row["current_state"] == {"trace_backend_ready": True}
    assert row["policy"]["host_layer_mutates_stack"] is False


@pytest.mark.parametrize(
    ("cli_name", "module_name", "args", "kwargs"),
    [
        (
            "self_awareness_capability_matrix",
            "capability_matrix",
            ("capability", "abyss-machine", [], {}),
            {},
        ),
        ("self_awareness_stack_memory_space_probe", "stack_memory_space_probe", (), {}),
        ("self_awareness_langchain_api_probe", "langchain_api_probe", (), {}),
        ("self_awareness_stack_closure_external_evidence", "stack_closure_external_evidence", (), {}),
        (
            "self_awareness_trace_backend_probe",
            "trace_backend_probe",
            ({}, {}),
            {},
        ),
        (
            "self_awareness_grafana_datasource_probe",
            "grafana_datasource_probe",
            ({}, {}, {}, {}, {}),
            {},
        ),
    ],
)
def test_cli_stack_probe_functions_only_bind_config_and_runtime_ports(
    monkeypatch: pytest.MonkeyPatch,
    cli_name: str,
    module_name: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> None:
    captured: dict[str, Any] = {}

    def fake_probe(*_args: Any, **call_kwargs: Any) -> dict[str, Any]:
        captured.update(call_kwargs)
        return {"schema": "synthetic"}

    monkeypatch.setattr(probes, module_name, fake_probe)

    result = getattr(cli, cli_name)(*args, **kwargs)

    assert result == {"schema": "synthetic"}
    assert isinstance(captured["config"], probes.SelfAwarenessStackProbeConfig)
    assert isinstance(captured["runtime_port"], probes.SelfAwarenessStackProbeRuntimePort)

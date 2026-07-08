from __future__ import annotations

import json
import wave
from pathlib import Path
from typing import Any

from abyss_machine import self_awareness_adapters
from abyss_machine import self_awareness_contracts


def _path_map(tmp_path: Path) -> dict[str, Path]:
    paths = {
        name: tmp_path / name / "latest.json"
        for name, _suffix in self_awareness_adapters.READMODEL_SCHEMA_SUFFIXES
    }
    paths["completion_audit"] = tmp_path / "completion-audit" / "latest.json"
    return paths


def test_readmodel_latest_specs_keep_public_order_and_cycle_switch(tmp_path: Path) -> None:
    specs = self_awareness_adapters.readmodel_latest_specs(
        schema_prefix="abyss_machine",
        paths=_path_map(tmp_path),
        include_cycle=False,
    )

    assert specs[0].name == "events"
    assert "cycle" not in {spec.name for spec in specs}
    assert specs[-1].name == "validate"
    assert specs[-1].schema == "abyss_machine_self_awareness_validate_v1"


def test_status_latest_specs_include_completion_audit_after_readmodels(tmp_path: Path) -> None:
    specs = self_awareness_adapters.status_latest_specs(
        schema_prefix="abyss_machine",
        paths=_path_map(tmp_path),
    )

    assert specs[-2].name == "validate"
    assert specs[-1].name == "completion_audit"
    assert specs[-1].schema == "abyss_machine_self_awareness_completion_audit_v1"


def test_load_latest_documents_uses_fake_read_port_without_live_io(tmp_path: Path) -> None:
    calls: list[tuple[Path, str]] = []
    specs = self_awareness_adapters.validation_latest_specs(
        schema_prefix="abyss_machine",
        paths=_path_map(tmp_path),
        require_cycle=False,
    )

    def fake_loader(path: Path, schema: str) -> dict[str, object]:
        calls.append((path, schema))
        return {"schema": schema, "ok": True, "generated_at": "2026-06-30T00:00:00Z", "summary": {}}

    documents = self_awareness_adapters.load_latest_documents(specs, load_latest_json=fake_loader)

    assert "completion_audit" in documents
    assert "probe" in documents
    assert "validate" not in documents
    assert "cycle" not in documents
    assert list(documents) == [spec.name for spec in specs]
    assert calls == [(spec.path, spec.schema) for spec in specs]


def test_cycle_latest_specs_keep_cycle_read_order(tmp_path: Path) -> None:
    specs = self_awareness_adapters.cycle_latest_specs(
        schema_prefix="abyss_machine",
        paths=_path_map(tmp_path),
    )

    assert [spec.name for spec in specs] == list(self_awareness_adapters.CYCLE_LATEST_READ_NAMES)
    assert specs[0].schema == "abyss_machine_self_awareness_capabilities_v1"
    assert specs[2].schema == "abyss_machine_self_awareness_trace_context_fallback_v1"
    assert specs[-1].schema == "abyss_machine_self_awareness_alerts_v1"


def test_cycle_latest_and_bridge_documents_use_fake_loaders(tmp_path: Path) -> None:
    latest_calls: list[tuple[Path, str]] = []
    bridge_calls: list[tuple[Path, str]] = []

    def fake_latest_loader(path: Path, schema: str) -> dict[str, Any]:
        latest_calls.append((path, schema))
        return {"schema": schema, "ok": True, "path": str(path)}

    def fake_bridge_loader(path: Path, schema: str) -> dict[str, Any]:
        bridge_calls.append((path, schema))
        return {"schema": schema, "ok": False, "path": str(path)}

    latest = self_awareness_adapters.load_cycle_latest_documents(
        schema_prefix="abyss_machine",
        paths=_path_map(tmp_path),
        load_latest_json=fake_latest_loader,
    )
    bridge = self_awareness_adapters.load_cycle_bridge_documents(
        [
            {"id": "memory", "path": tmp_path / "memory" / "latest.json", "schema": "abyss_machine_memory_status_v1"},
            {"id": "mode", "path": tmp_path / "mode" / "latest.json", "schema": "abyss_machine_mode_status_v1"},
        ],
        load_latest_json=fake_bridge_loader,
    )

    assert list(latest) == list(self_awareness_adapters.CYCLE_LATEST_READ_NAMES)
    assert latest["capabilities"]["schema"] == "abyss_machine_self_awareness_capabilities_v1"
    assert latest_calls == [(spec.path, spec.schema) for spec in self_awareness_adapters.cycle_latest_specs(schema_prefix="abyss_machine", paths=_path_map(tmp_path))]
    assert bridge == {
        "memory": {"schema": "abyss_machine_memory_status_v1", "ok": False, "path": str(tmp_path / "memory" / "latest.json")},
        "mode": {"schema": "abyss_machine_mode_status_v1", "ok": False, "path": str(tmp_path / "mode" / "latest.json")},
    }
    assert bridge_calls == [
        (tmp_path / "memory" / "latest.json", "abyss_machine_memory_status_v1"),
        (tmp_path / "mode" / "latest.json", "abyss_machine_mode_status_v1"),
    ]


def test_latest_summary_omits_raw_payload_and_redacts_summary(tmp_path: Path) -> None:
    spec = self_awareness_adapters.SelfAwarenessLatestSpec(
        name="events",
        path=tmp_path / "events" / "latest.json",
        schema="abyss_machine_self_awareness_events_v1",
    )
    document = {
        "schema": spec.schema,
        "ok": True,
        "generated_at": "2026-06-30T00:00:00Z",
        "summary": {
            "events": 2,
            "token": "Authorization: Bearer " + "sk-" + "testsecret1234567890",
        },
        "raw_events": [{"body": "private body"}],
    }

    summary = self_awareness_adapters.latest_summary(spec, document)

    assert summary["path"].endswith("events/latest.json")
    assert summary["summary"] == {"events": 2, "token": "<redacted>"}
    assert "raw_events" not in summary


def test_missing_latest_document_names_only_reports_error_documents() -> None:
    documents = {
        "events": {"ok": True},
        "collect": {"ok": False},
        "validate": {"ok": False, "error": "missing"},
    }

    assert self_awareness_adapters.missing_latest_document_names(documents) == ["validate"]


def test_body_closure_status_document_is_adapter_owned(tmp_path: Path) -> None:
    latest_paths = {
        "heartbeat": tmp_path / "heartbeat" / "latest.json",
        "reactions": tmp_path / "reactions" / "latest.json",
        "responses": tmp_path / "responses" / "latest.json",
        "doctor": tmp_path / "doctor" / "latest.json",
        "topology": tmp_path / "topology" / "latest.json",
        "stack_bridge": tmp_path / "stack-bridge" / "latest.json",
        "changes": tmp_path / "changes" / "latest.json",
        "nervous_brief": tmp_path / "nervous" / "latest.json",
        "backup": tmp_path / "backup" / "latest.json",
    }

    payload = self_awareness_adapters.body_closure_status_document(
        heartbeat={"summary": {"status": "watch"}},
        reactions={"summary": {"status": "open", "candidates": 2, "by_category": {"working_stack": 2}}},
        responses={"summary": {"status": "open", "routes": 1, "by_category": {"owner_gate": 1}}},
        doctor={"summary": {"status": "warn", "warnings": 1, "fails": 0}},
        topology={"summary": {"status": "fail", "warnings": 0, "fails": 1}},
        stack_bridge={"summary": {"status": "warn", "warnings": 1, "fails": 1}},
        changes={"summary": {"active_records": 1}, "backup_plane_active": True},
        nervous_brief={"readiness": {"status": "warming"}},
        backup={"blockers": ["vault_not_mounted"]},
        latest_paths=latest_paths,
        schema_prefix="abyss_machine",
        backup_plane_active_change=lambda document: document.get("backup_plane_active") is True,
        backup_plane_blockers=lambda document: list(document.get("blockers", [])),
    )

    assert payload["schema"] == "abyss_machine_self_awareness_body_closure_v1"
    assert payload["status"] == "watch"
    assert payload["complete"] is False
    assert {source["kind"] for source in payload["watch_sources"]} == {
        "heartbeat",
        "reactions",
        "responses",
        "doctor",
        "topology",
        "stack_bridge",
        "changes",
        "nervous",
        "backup",
    }
    assert payload["summary"] == {
        "watch_sources": 9,
        "reaction_candidates": 2,
        "response_routes": 1,
        "doctor_warnings": 1,
        "doctor_fails": 0,
        "topology_warnings": 0,
        "topology_fails": 1,
        "stack_bridge_warnings": 1,
        "stack_bridge_fails": 1,
        "active_changes": 1,
        "nervous_status": "warming",
        "backup_blockers": ["vault_not_mounted"],
    }
    backup_source = next(source for source in payload["watch_sources"] if source["kind"] == "backup")
    assert backup_source["evidence"]["path"] == str(latest_paths["backup"])
    assert payload["policy"] == {
        "read_model": True,
        "does_not_refresh": True,
        "does_not_execute_commands": True,
        "host_layer_mutates_stack": False,
        "separates_stack_usage_from_body_closure": True,
    }


def test_body_closure_status_document_ready_path_has_no_watch_sources(tmp_path: Path) -> None:
    payload = self_awareness_adapters.body_closure_status_document(
        heartbeat={"summary": {"status": "steady"}},
        reactions={"summary": {"status": "ok", "candidates": 0}},
        responses={"summary": {"status": "ok", "routes": 0}},
        doctor={"summary": {"status": "ok", "warnings": 0, "fails": 0}},
        topology={"summary": {"status": "ok", "warnings": 0, "fails": 0}},
        stack_bridge={"summary": {"status": "ok", "warnings": 0, "fails": 0}},
        changes={"summary": {"active_records": 0}},
        nervous_brief={"readiness": {"status": "ready"}},
        backup={},
        latest_paths={"heartbeat": tmp_path / "heartbeat" / "latest.json"},
        schema_prefix="abyss_machine",
        backup_plane_active_change=lambda _document: False,
        backup_plane_blockers=lambda _document: [],
    )

    assert payload["status"] == "ready"
    assert payload["complete"] is True
    assert payload["watch_sources"] == []
    assert payload["summary"]["watch_sources"] == 0
    assert payload["summary"]["backup_blockers"] == []


def test_status_open_rows_are_adapter_owned() -> None:
    route_calls: list[dict[str, Any]] = []

    def fake_activation_gap_route(
        gap: dict[str, Any],
        *,
        episode_id: str | None = None,
        activation_row: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        route_calls.append({"gap": gap, "episode_id": episode_id, "activation_row": activation_row})
        return {
            "schema": "abyss_machine_self_awareness_working_stack_activation_gap_route_v1",
            "complete": True,
            "service": gap["service"],
            "classification": "running_functional_smoke_failed",
            "current_state": {"runtime": {"running": gap["runtime_running"]}},
            "activation_smoke": {"working_stack_gap_replayable": True},
            "policy": {"host_layer_mutates_stack": False},
        }

    potential_rows = self_awareness_adapters.status_open_potential_rows(
        autolink_organ_rows=[
            {"service": "ignored", "usage_gap": False},
            {
                "service": "aoa-browser",
                "owner": "abyss-stack",
                "machine_usage_status": "runtime_present_but_not_used",
                "usage_gap": "functional_smoke_failed",
                "working_stack_link_id": "wslink-aoa-browser",
                "event_id": "event-1",
                "episode_ids": ["other", "saepisode-working-stack-gap-1"],
                "activation_smoke": {
                    "complete": True,
                    "thread_id": "thread-1",
                    "working_stack_link_id": "wslink-aoa-browser",
                },
                "evidence_refs": [{"name": "autolink"}],
            },
        ],
        activation_by_service={
            "aoa-browser": {
                "machine_usage_status": "runtime_present",
                "activation_kind": "browser_tool_runtime",
                "usage_gap": "functional_smoke_failed",
                "current_state": {
                    "runtime": {"present": True, "running": True, "container": "aoa-browser"},
                    "declared": {"present": True, "modules": ["browser"]},
                    "endpoint_ok": False,
                    "deep_usage_proven": False,
                },
                "failed_probe_names": ["playwright-chromium-launch"],
                "ok_probe_names": ["container-running"],
                "closure_blocker_keys": ["playwright_chromium_launch"],
                "missing_checks": ["browser_launch_smoke"],
                "verifier_commands": ["abyss-machine self-awareness working-stack --json"],
                "safe_next_action": {"requires_human_approval": True},
            }
        },
        activation_smoke_by_service={"aoa-browser": {"service": "aoa-browser", "complete": False}},
        schema_prefix="abyss_machine",
        activation_gap_route=fake_activation_gap_route,
    )

    assert len(potential_rows) == 1
    row = potential_rows[0]
    assert row["schema"] == "abyss_machine_self_awareness_open_potential_service_status_v1"
    assert row["service"] == "aoa-browser"
    assert row["activation_gap_classification"] == "running_functional_smoke_failed"
    assert row["activation_smoke"]["link_matches_current"] is True
    assert row["closure_blocker_keys"] == ["playwright_chromium_launch"]
    assert row["missing_checks"] == ["browser_launch_smoke"]
    assert row["policy"]["host_layer_mutates_stack"] is False
    assert route_calls[0]["episode_id"] == "saepisode-working-stack-gap-1"
    assert route_calls[0]["activation_row"] == {"service": "aoa-browser", "complete": False}
    assert route_calls[0]["gap"]["endpoint_probe_count"] == 2
    assert route_calls[0]["gap"]["declared_modules"] == ["browser"]

    requirement_rows = self_awareness_adapters.status_open_stack_requirement_rows(
        autolink_requirement_rows=[
            {"requirement_id": "closed", "automatic_link_state": "closed"},
            {
                "requirement_id": "stack.trace-backend",
                "owner": "abyss-stack",
                "automatic_link_state": "open_stack_blocker",
                "episode_ids": ["saepisode-req-1"],
                "evidence_refs": [{"name": "autolink"}],
            },
        ],
        requirement_by_id={
            "stack.trace-backend": {
                "title": "Trace backend",
                "owner": "abyss-stack",
                "blocking_check_keys": ["langchain_trace_backend_coupled"],
                "coverage_impact": {"coverage_planes": ["trace_backend"]},
                "runbook_candidate_id": "runbook-trace",
            }
        },
        stack_closure_by_id={
            "stack.trace-backend": {
                "closure_readiness": {"missing_checks": ["span_log_metric_join"]},
                "closure_acceptance": {
                    "acceptance_id": "accept-trace",
                    "stack_compat_requirement": {"requirement_id": "stack.trace-backend"},
                },
                "verifier_commands": ["abyss-stack trace verify"],
                "safe_next_action": {"requires_human_approval": True},
            }
        },
        schema_prefix="abyss_machine",
    )

    assert len(requirement_rows) == 1
    requirement = requirement_rows[0]
    assert requirement["schema"] == "abyss_machine_self_awareness_open_stack_requirement_status_v1"
    assert requirement["requirement_id"] == "stack.trace-backend"
    assert requirement["blocking_check_keys"] == ["langchain_trace_backend_coupled"]
    assert requirement["coverage_planes"] == ["trace_backend"]
    assert requirement["missing_checks"] == ["span_log_metric_join"]
    assert requirement["closure_acceptance_id"] == "accept-trace"
    assert requirement["compat_requirement_id"] == "stack.trace-backend"
    assert requirement["policy"]["executes_commands"] is False


class _FakeHttpResponse:
    def __init__(self, *, status: int, headers: dict[str, str], body: bytes) -> None:
        self.status = status
        self.headers = headers
        self._body = body

    def __enter__(self) -> "_FakeHttpResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, size: int) -> bytes:
        return self._body[:size]


def test_http_status_with_headers_uses_fake_ports_and_redacts_preview() -> None:
    requests: list[tuple[str, dict[str, str], str]] = []
    opened: list[tuple[dict[str, Any], float]] = []
    clock_values = iter([10.0, 10.125])
    secret = "Authorization: Bearer " + "sk-" + "testsecret1234567890"

    def fake_request_factory(url: str, headers: dict[str, str], method: str) -> dict[str, Any]:
        requests.append((url, headers, method))
        return {"url": url, "headers": headers, "method": method}

    def fake_urlopen(request: dict[str, Any], timeout: float) -> _FakeHttpResponse:
        opened.append((request, timeout))
        return _FakeHttpResponse(
            status=204,
            headers={"content-type": "application/json"},
            body=f'{{"token": "{secret}"}}'.encode(),
        )

    payload = self_awareness_adapters.http_status_with_headers(
        "http://127.0.0.1:3000/api/health",
        {"Accept": "application/json", "traceparent": "00-" + "a" * 32 + "-" + "b" * 16 + "-01"},
        request_factory=fake_request_factory,
        urlopen=fake_urlopen,
        clock=lambda: next(clock_values),
        timeout=1.25,
    )

    assert payload["ok"] is True
    assert payload["status_code"] == 204
    assert payload["content_type"] == "application/json"
    assert payload["elapsed_ms"] == 125.0
    assert "<redacted>" in payload["text_preview"]
    assert "testsecret1234567890" not in payload["text_preview"]
    assert requests == [
        (
            "http://127.0.0.1:3000/api/health",
            {"Accept": "application/json", "traceparent": "00-" + "a" * 32 + "-" + "b" * 16 + "-01"},
            "GET",
        )
    ]
    assert opened == [({"url": "http://127.0.0.1:3000/api/health", "headers": requests[0][1], "method": "GET"}, 1.25)]


def test_http_status_with_headers_bounds_large_body() -> None:
    clock_values = iter([1.0, 1.002])

    payload = self_awareness_adapters.http_status_with_headers(
        "http://service.local/health",
        {},
        request_factory=lambda url, headers, method: {"url": url, "headers": headers, "method": method},
        urlopen=lambda _request, _timeout: _FakeHttpResponse(status=200, headers={}, body=b"abcdef"),
        clock=lambda: next(clock_values),
        max_bytes=5,
    )

    assert payload["ok"] is True
    assert payload["truncated"] is True
    assert payload["text_preview"] == "abcde"


def test_http_status_with_headers_reports_bounded_error_with_status_code() -> None:
    class FakeHttpError(Exception):
        code = 503

    clock_values = iter([2.0, 2.01])

    def fake_urlopen(_request: object, _timeout: float) -> _FakeHttpResponse:
        raise FakeHttpError("password=" + "secret unavailable")

    payload = self_awareness_adapters.http_status_with_headers(
        "http://service.local/health",
        {},
        request_factory=lambda url, headers, method: {"url": url, "headers": headers, "method": method},
        urlopen=fake_urlopen,
        clock=lambda: next(clock_values),
    )

    assert payload["ok"] is False
    assert payload["status_code"] == 503
    assert payload["error"] == "<redacted> unavailable"


def test_working_stack_endpoint_probes_use_fake_http_and_tcp_ports() -> None:
    http_calls: list[tuple[str, str, float, int]] = []
    tcp_calls: list[tuple[str, int, float]] = []
    clock_values = iter([5.0, 5.025])

    def fake_http_json(url: str, timeout: float, max_bytes: int) -> dict[str, Any]:
        http_calls.append(("json", url, timeout, max_bytes))
        return {"ok": True, "url": url, "status_code": 200, "json_shape": {"type": "dict", "keys": ["ok"]}}

    def fake_http_status(url: str, timeout: float, max_bytes: int) -> dict[str, Any]:
        http_calls.append(("status", url, timeout, max_bytes))
        return {"ok": False, "url": url, "status_code": 503, "error": "down"}

    def fake_tcp_connect(host: str, port: int, timeout: float) -> None:
        tcp_calls.append((host, port, timeout))

    payload = self_awareness_adapters.working_stack_endpoint_probes(
        http_specs=[
            self_awareness_adapters.WorkingStackEndpointProbeSpec("grafana", "health", "http://grafana/api/health"),
            self_awareness_adapters.WorkingStackEndpointProbeSpec("prometheus", "ready", "http://prom/-/ready", kind="http_status", max_bytes=4096),
        ],
        tcp_specs=[self_awareness_adapters.WorkingStackTcpProbeSpec("postgres", "127.0.0.1", 5432, timeout=0.5)],
        http_json=fake_http_json,
        http_status=fake_http_status,
        tcp_connect=fake_tcp_connect,
        clock=lambda: next(clock_values),
    )

    assert [(row["service"], row["probe"], row["kind"], row["ok"]) for row in payload] == [
        ("grafana", "health", "http_json", True),
        ("prometheus", "ready", "http_status", False),
        ("postgres", "tcp:127.0.0.1:5432", "tcp_ready", True),
    ]
    assert http_calls == [
        ("json", "http://grafana/api/health", 1.5, 131072),
        ("status", "http://prom/-/ready", 1.5, 4096),
    ]
    assert tcp_calls == [("127.0.0.1", 5432, 0.5)]
    assert payload[2]["elapsed_ms"] == 25.0


def test_tcp_probe_reports_bounded_connect_error() -> None:
    clock_values = iter([10.0, 10.01])

    def fake_connect(_host: str, _port: int, _timeout: float) -> None:
        raise OSError("connection refused")

    payload = self_awareness_adapters.tcp_probe(
        "redis",
        "127.0.0.1",
        6379,
        tcp_connect=fake_connect,
        clock=lambda: next(clock_values),
    )

    assert payload["ok"] is False
    assert payload["error"] == "connection refused"
    assert payload["body_stored"] is False
    assert payload["raw_private_content"] is False


def test_container_http_probe_uses_fake_runner_expected_status_and_omits_body() -> None:
    calls: list[tuple[list[str], float]] = []

    def fake_run(command: list[str], timeout: float) -> dict[str, Any]:
        calls.append((command, timeout))
        return {
            "ok": True,
            "stdout": json.dumps({
                "ok": False,
                "status_code": 403,
                "elapsed_ms": 12.5,
                "content_hash": "abc123",
                "json_shape": {"type": "dict", "keys": ["detail"]},
            }),
            "stderr": "",
            "returncode": 0,
        }

    payload = self_awareness_adapters.container_http_probe(
        "aoa-browser",
        "abyss_aoa_browser_1",
        "private-host-guard",
        "http://127.0.0.1:8000/read",
        command_exists=lambda name: name == "podman",
        run_command=fake_run,
        clock=lambda: 1.0,
        method="POST",
        request_json={"url": "http://127.0.0.1:8000/health"},
        expected_statuses={403},
        timeout=6.0,
    )

    assert payload["ok"] is True
    assert payload["status_code"] == 403
    assert payload["expected_status_codes"] == [403]
    assert payload["method"] == "POST"
    assert payload["body_stored"] is False
    assert payload["raw_private_content"] is False
    assert "text_preview" not in payload
    assert calls and calls[0][0][:4] == ["podman", "exec", "abyss_aoa_browser_1", "python"]
    assert calls[0][1] == 14.0


def test_container_http_probe_runner_failure_redacts_error() -> None:
    secret = "Authorization: Bearer " + "sk-" + "testsecret1234567890"
    clock_values = iter([20.0, 20.25])

    payload = self_awareness_adapters.container_http_probe(
        "docs-api",
        "docs",
        "health",
        "http://127.0.0.1:5000/health",
        command_exists=lambda _name: True,
        run_command=lambda _command, _timeout: {"ok": False, "stderr": f"failed {secret}", "stdout": "", "returncode": 125},
        clock=lambda: next(clock_values),
    )

    assert payload["ok"] is False
    assert payload["returncode"] == 125
    assert "testsecret1234567890" not in payload["error"]
    assert payload["policy"]["response_body_stored"] is False


def test_container_python_smoke_hashes_output_without_storing_body() -> None:
    clock_values = iter([30.0, 30.05])

    payload = self_awareness_adapters.container_python_smoke(
        "aoa-browser",
        "browser",
        "playwright-chromium-launch",
        "print('launch_ok')",
        run_command=lambda _command, _timeout: {"ok": False, "stdout": "secret launch details", "stderr": "", "returncode": 1},
        clock=lambda: next(clock_values),
    )

    assert payload["ok"] is False
    assert payload["stdout_hash"]
    assert "secret launch details" not in json.dumps(payload)
    assert payload["body_stored"] is False
    assert payload["raw_private_content"] is False


def test_working_stack_container_tool_probes_maps_running_services_with_fake_runner() -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], _timeout: float) -> dict[str, Any]:
        calls.append(command)
        if command[-1] == "18.0":
            return {"ok": True, "stdout": "launch_ok", "stderr": "", "returncode": 0}
        status_code = 403 if any("8000/read" in part for part in command) else 200
        return {
            "ok": True,
            "stdout": json.dumps({"ok": 200 <= status_code < 400, "status_code": status_code, "elapsed_ms": 1.0}),
            "stderr": "",
            "returncode": 0,
        }

    payload = self_awareness_adapters.working_stack_container_tool_probes(
        {
            "docs-api": {"running": True, "container": "docs"},
            "aoa-browser": {"running": True, "container": "browser"},
            "qdrant": {"running": True, "container": "qdrant"},
        },
        command_exists=lambda name: name == "podman",
        run_command=fake_run,
        clock=lambda: 100.0,
    )

    assert [(row["service"], row["probe"], row["ok"]) for row in payload] == [
        ("docs-api", "health", True),
        ("docs-api", "search:n8n-workflow", True),
        ("aoa-browser", "health", True),
        ("aoa-browser", "private-host-guard", True),
        ("aoa-browser", "playwright-chromium-launch", True),
    ]
    assert len(calls) == 5


def test_working_stack_tts_smoke_evidence_reads_sidecar_wav_through_fakeable_ports(tmp_path: Path) -> None:
    stack_root = tmp_path / "stack"
    tts_root = stack_root / "Logs" / "tts" / "aoa_archivist"
    tts_root.mkdir(parents=True)
    wav_path = tts_root / "self_awareness_smoke.wav"
    with wave.open(str(wav_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\x00\x00" * 16)
    sidecar_path = wav_path.with_suffix(".json")
    sidecar_path.write_text(
        "\n".join([
            "agent_id: aoa_archivist",
            "voice_id: aoa_archivist",
            "model_id: /models/hf/local/Qwen3-TTS-12Hz-1.7B-CustomVoice",
            "language: Russian",
            "speaker: Aiden",
            "saved_path: /out/aoa_archivist/self_awareness_smoke.wav",
            "text: private smoke phrase",
            "ts: '2026-06-10 21:45:10'",
            "",
        ]),
        encoding="utf-8",
    )

    payload = self_awareness_adapters.working_stack_tts_smoke_evidence(
        stack_root,
        schema_prefix="abyss_machine",
        now=lambda: max(sidecar_path.stat().st_mtime, wav_path.stat().st_mtime) + 12.0,
        path_exists=Path.exists,
        path_is_file=Path.is_file,
        path_glob=lambda root, pattern: root.glob(pattern),
        path_read_text=lambda path: path.read_text(encoding="utf-8", errors="replace"),
        path_stat=Path.stat,
    )

    assert payload["ok"] is True
    assert payload["schema"] == "abyss_machine_self_awareness_working_stack_tts_smoke_evidence_v1"
    assert payload["wav_path"] == str(wav_path)
    assert payload["sidecar_path"] == str(sidecar_path)
    assert payload["age_seconds"] == 12.0
    assert payload["wav_format"]["framerate"] == 24000
    assert payload["sidecar"]["host_rel_path"] == "aoa_archivist/self_awareness_smoke.wav"
    assert payload["sidecar"]["text_hash"]
    assert "private smoke phrase" not in json.dumps(payload)
    assert payload["policy"]["raw_text_stored"] is False
    assert payload["policy"]["raw_audio_stored"] is False
    assert any(ref["path"] == str(wav_path) for ref in payload["evidence_refs"])


def test_working_stack_tts_smoke_evidence_rejects_stale_artifact(tmp_path: Path) -> None:
    stack_root = tmp_path / "stack"
    tts_root = stack_root / "Logs" / "tts"
    tts_root.mkdir(parents=True)
    sidecar_path = tts_root / "old.json"
    wav_path = tts_root / "old.wav"
    sidecar_path.write_text(json.dumps({"model_id": "Qwen3-TTS", "saved_path": "/out/old.wav"}), encoding="utf-8")
    wav_path.write_bytes(b"RIFF" + b"\x00" * 80)

    payload = self_awareness_adapters.working_stack_tts_smoke_evidence(
        stack_root,
        schema_prefix="abyss_machine",
        now=lambda: 1000.0,
        path_exists=Path.exists,
        path_is_file=Path.is_file,
        path_glob=lambda root, pattern: root.glob(pattern),
        path_read_text=lambda path: path.read_text(encoding="utf-8", errors="replace"),
        path_stat=lambda path: type("Stat", (), {"st_mtime": 0.0, "st_size": 84})(),
        wav_format_reader=lambda _path: {"frames": 16, "channels": 1, "sample_width": 2, "framerate": 24000},
        max_age_seconds=10,
    )

    assert payload["ok"] is False
    assert payload["reason"] == "fresh_qwen_tts_sidecar_wav_pair_missing"


def test_working_stack_tts_smoke_probes_are_public_safe_and_disableable(tmp_path: Path) -> None:
    evidence = {
        "ok": True,
        "wav_path": str(tmp_path / "speech.wav"),
        "evidence_refs": [{"path": str(tmp_path / "speech.wav"), "schema": "riff_wav_audio"}],
        "policy": {"raw_text_stored": False, "raw_audio_stored": False, "host_layer_mutates_stack": False},
    }

    disabled = self_awareness_adapters.working_stack_tts_smoke_probes(evidence=evidence, enabled=False)
    probes = self_awareness_adapters.working_stack_tts_smoke_probes(evidence=evidence)

    assert disabled == []
    assert [(row["service"], row["probe"], row["ok"]) for row in probes] == [
        ("qwen-tts", "tts-synthesis-artifact", True),
        ("tts-router", "tts-synthesis-artifact", True),
    ]
    assert probes[0]["body_stored"] is False
    assert probes[0]["raw_private_content"] is False
    assert probes[0]["policy"]["host_layer_mutates_stack"] is False


def test_env_and_meminfo_ports_are_fakeable() -> None:
    env = {"INT": "42", "FLOAT": "2.5", "EMPTY": "", "BAD": "nope"}

    assert self_awareness_adapters.env_int("INT", 7, env_get=env.get) == 42
    assert self_awareness_adapters.env_int("EMPTY", 7, env_get=env.get) == 7
    assert self_awareness_adapters.env_int("BAD", 7, env_get=env.get) == 7
    assert self_awareness_adapters.env_float("FLOAT", 1.0, env_get=env.get) == 2.5
    assert self_awareness_adapters.env_float("BAD", 1.0, env_get=env.get) == 1.0

    meminfo = self_awareness_adapters.proc_meminfo_bytes(
        read_text=lambda: "MemAvailable: 512 kB\nSwapTotal: 2 kB\nSwapFree: nope kB\n"
    )

    assert meminfo == {"MemAvailable": 512 * 1024, "SwapTotal": 2 * 1024}


def test_resource_preflight_fails_closed_under_pressure_with_fake_ports() -> None:
    env = {
        "ABYSS_MACHINE_SELF_AWARENESS_MIN_MEM_AVAILABLE_MB": "1024",
        "ABYSS_MACHINE_SELF_AWARENESS_MIN_SWAP_FREE_MB": "512",
        "ABYSS_MACHINE_SELF_AWARENESS_MAX_LOAD_PER_CPU": "1.0",
    }

    payload = self_awareness_adapters.resource_preflight(
        "self-awareness-probe",
        schema_prefix="abyss_machine",
        env_get=env.get,
        meminfo_reader=lambda: {
            "MemAvailable": 768 * 1024 * 1024,
            "SwapTotal": 4 * 1024 * 1024 * 1024,
            "SwapFree": 256 * 1024 * 1024,
        },
        cpu_count_reader=lambda: 2,
        loadavg_reader=lambda: (3.25, 2.0, 1.0),
    )

    assert payload["schema"] == "abyss_machine_self_awareness_resource_preflight_v1"
    assert payload["ok"] is False
    assert payload["status"] == "resource_denied"
    assert payload["denial_reasons"] == [
        "mem_available_below_floor",
        "swap_free_below_floor",
        "load_average_above_cpu_floor",
    ]
    assert payload["policy"]["heavy_operation_must_fail_closed_under_pressure"] is True


def test_resource_preflight_guard_disable_keeps_reasons_but_allows_operation() -> None:
    env = {
        "ABYSS_MACHINE_SELF_AWARENESS_RESOURCE_GUARD": "0",
        "ABYSS_MACHINE_SELF_AWARENESS_MIN_MEM_AVAILABLE_MB": "1024",
    }

    payload = self_awareness_adapters.resource_preflight(
        "self-awareness-cycle",
        schema_prefix="abyss_machine",
        env_get=env.get,
        meminfo_reader=lambda: {"MemAvailable": 128 * 1024 * 1024},
        cpu_count_reader=lambda: 1,
        loadavg_reader=lambda: (0.0, 0.0, 0.0),
    )

    assert payload["ok"] is True
    assert payload["status"] == "ok"
    assert payload["denial_reasons"] == ["mem_available_below_floor"]
    assert payload["policy"]["guard_enabled"] is False


def test_probe_resource_denied_document_is_public_safe_and_fail_closed() -> None:
    resource_preflight = {
        "schema": "abyss_machine_self_awareness_resource_preflight_v1",
        "ok": False,
        "status": "resource_denied",
        "denial_reasons": ["mem_available_below_floor", "swap_free_below_floor"],
    }

    payload = self_awareness_adapters.probe_resource_denied_document(
        schema_prefix="abyss_machine",
        version="0.test",
        generated_at="2026-07-07T00:00:00+00:00",
        run_id="saprobe-fixture",
        traceparent="00-" + "a" * 32 + "-" + "b" * 16 + "-01",
        resource_preflight=resource_preflight,
    )

    assert payload["schema"] == "abyss_machine_self_awareness_probe_v1"
    assert payload["ok"] is False
    assert payload["status"] == "resource_denied"
    assert payload["chain"] == {}
    assert payload["summary"] == {
        "status": "resource_denied",
        "chain_passed": 0,
        "chain_total": 0,
        "resource_guard_ok": False,
        "resource_guard_reasons": ["mem_available_below_floor", "swap_free_below_floor"],
    }
    assert payload["policy"]["heavy_operation_must_fail_closed_under_pressure"] is True
    assert payload["policy"]["writes_project_roots"] is False
    assert payload["evidence_refs"] == [{"source": "/proc/meminfo"}, {"source": "os.getloadavg"}]


def test_cycle_resource_denied_document_is_public_safe_and_fail_closed() -> None:
    resource_preflight = {
        "schema": "abyss_machine_self_awareness_resource_preflight_v1",
        "ok": False,
        "status": "resource_denied",
        "denial_reasons": ["load_average_above_cpu_floor"],
    }

    payload = self_awareness_adapters.cycle_resource_denied_document(
        schema_prefix="abyss_machine",
        version="0.test",
        generated_at="2026-07-07T00:00:00+00:00",
        cycle_id="sacycle-fixture",
        resource_preflight=resource_preflight,
    )

    assert payload["schema"] == "abyss_machine_self_awareness_cycle_v1"
    assert payload["ok"] is False
    assert payload["status"] == "resource_denied"
    assert payload["probe_run_id"] is None
    assert payload["summary"]["steps"] == 0
    assert payload["summary"]["chain_passed"] == 0
    assert payload["cycle_chain"] == {}
    assert payload["steps"] == []
    assert payload["issues"] == {"resource_preflight": resource_preflight}
    assert payload["policy"]["host_layer_mutates_stack"] is False
    assert payload["policy"]["automatic_remediation"] is False
    assert payload["policy"]["heavy_operation_must_fail_closed_under_pressure"] is True


def test_cycle_partial_document_builds_public_safe_building_snapshot(tmp_path: Path) -> None:
    steps = [
        {
            "id": "probe",
            "ok": True,
            "artifact": {
                "path": str(tmp_path / "probe" / "latest.json"),
                "schema": "abyss_machine_self_awareness_probe_v1",
                "ok": True,
            },
        },
        {
            "id": "memory",
            "ok": True,
            "artifact": {
                "path": str(tmp_path / "memory" / "latest.json"),
                "schema": "abyss_machine_memory_status_v1",
                "ok": False,
            },
        },
    ]
    resource_preflight = {"ok": True, "status": "ok", "denial_reasons": []}
    cycle_chain = {"probe": True, "replay": True}
    bridge_proof = {"ok": True, "summary": {"bridges": 2}}
    stack_handoff_summary = {"summary": {"open_requirements": 1}}
    stack_handoff_closure_readiness = {"summary": {"packets": 3}}

    payload = self_awareness_adapters.cycle_partial_document(
        schema_prefix="abyss_machine",
        version="0.test",
        generated_at="2026-07-07T00:00:00+00:00",
        cycle_id="sacycle-fixture",
        probe_run_id="saprobe-fixture",
        steps=steps,
        resource_preflight=resource_preflight,
        cycle_chain=cycle_chain,
        bridge_proof=bridge_proof,
        stack_handoff_summary=stack_handoff_summary,
        stack_handoff_closure_readiness=stack_handoff_closure_readiness,
        automatic_response_count=0,
        mutating_response_routes=0,
    )

    assert payload["schema"] == "abyss_machine_self_awareness_cycle_v1"
    assert payload["ok"] is False
    assert payload["status"] == "building"
    assert payload["cycle_id"] == "sacycle-fixture"
    assert payload["probe_run_id"] == "saprobe-fixture"
    assert payload["summary"] == {"status": "building", "steps": 2}
    assert payload["steps"] == steps
    assert payload["resource_preflight"] == resource_preflight
    assert payload["cycle_chain"] == cycle_chain
    assert payload["bridge_proof"] == bridge_proof
    assert payload["stack_handoff_summary"] == stack_handoff_summary
    assert payload["stack_handoff_closure_readiness"] == stack_handoff_closure_readiness
    assert payload["evidence_refs"] == [
        {"path": str(tmp_path / "probe" / "latest.json"), "step": "probe"},
        {"path": str(tmp_path / "memory" / "latest.json"), "step": "memory"},
    ]
    assert payload["policy"] == {
        "host_layer_mutates_stack": False,
        "automatic_remediation": False,
        "automatic_responses": 0,
        "routes_with_mutating_command_if_run": 0,
        "open_stack_requirements_are_blockers_not_host_failures": True,
    }


def test_cycle_stack_handoff_summary_document_is_public_safe(tmp_path: Path) -> None:
    paths = {
        "requirement_probes": tmp_path / "requirement-probes" / "latest.json",
        "stack_closure_dossier": tmp_path / "stack-closure-dossier" / "latest.json",
        "working_stack": tmp_path / "working-stack" / "latest.json",
        "replay": tmp_path / "replay" / "latest.json",
    }
    readiness = {
        "open_requirement_ids": ["REQ-1"],
        "summary": {"packets": 2, "missing_checks": 0},
    }
    replay = {"stack_handoff_replay": {"closure_readiness_replayable": True}}
    requirement_probes = {"summary": {"probes": 3}}
    stack_closure_dossier = {
        "summary": {"open_stack_requirements": 1},
        "working_stack_activation_handoff": {"complete": False},
    }
    activation_summary = {"entries": 4, "open_activation_gaps": 1}
    activation_smoke = {"summary": {"rows": 4, "rows_ok": 3}}

    payload = self_awareness_adapters.cycle_stack_handoff_summary_document(
        schema_prefix="abyss_machine",
        stack_handoff_closure_readiness=readiness,
        replay=replay,
        requirement_probes=requirement_probes,
        stack_closure_dossier=stack_closure_dossier,
        working_stack_activation_summary=activation_summary,
        activation_smoke=activation_smoke,
        open_requirement_rows=[{"id": "REQ-1"}, {"id": "REQ-2"}],
        paths=paths,
    )

    assert payload["schema"] == "abyss_machine_self_awareness_cycle_stack_handoff_summary_v1"
    assert payload["open_requirement_ids"] == ["REQ-1"]
    assert payload["closure_readiness_summary"] == {"packets": 2, "missing_checks": 0}
    assert payload["replay"] == {"closure_readiness_replayable": True}
    assert payload["requirement_probe_summary"] == {"probes": 3}
    assert payload["stack_closure_dossier_summary"] == {"open_stack_requirements": 1}
    assert payload["working_stack_activation_summary"] == activation_summary
    assert payload["working_stack_activation_smoke_summary"] == {"rows": 4, "rows_ok": 3}
    assert payload["working_stack_activation_handoff"] == {"complete": False}
    assert payload["stack_closure_dossier_latest"] == str(paths["stack_closure_dossier"])
    assert payload["failure_matrix_open_rows"] == 2
    assert payload["policy"] == {
        "handoff_only": True,
        "read_only": True,
        "executes_commands": False,
        "action_execution": False,
        "host_layer_mutates_stack": False,
        "open_stack_requirements_are_blockers_not_host_failures": True,
        "working_stack_activation_gaps_are_blockers_not_host_failures": True,
    }
    assert payload["evidence_refs"] == [
        {"path": str(paths["requirement_probes"]), "section": "closure_readiness"},
        {"path": str(paths["stack_closure_dossier"]), "section": "stack_owner_handoff"},
        {"path": str(paths["stack_closure_dossier"]), "section": "working_stack_activation_dossier"},
        {"path": str(paths["working_stack"]), "section": "machine_usage_gaps"},
        {"path": str(paths["replay"]), "section": "stack_handoff_replay"},
    ]


def test_failure_matrix_open_requirement_rule_stays_policy_owned() -> None:
    assert self_awareness_adapters.failure_matrix_row_is_open_requirement(
        {
            "id": "requirement:stack.trace-backend",
            "failure_kind": "open_requirement",
        }
    ) is True
    assert self_awareness_adapters.failure_matrix_row_is_open_requirement(
        {
            "id": "requirement:stack.closed",
            "failure_kind": "closed_requirement_regression_guard",
            "current_state": {"requirement_present": True},
        }
    ) is False
    assert self_awareness_adapters.failure_matrix_row_is_open_requirement(
        {
            "id": "requirement:stack.present",
            "current_state": {"requirement_present": True, "status": "open"},
        }
    ) is True
    assert self_awareness_adapters.failure_matrix_row_is_open_requirement(
        {
            "id": "requirement:stack.closed-by-probe",
            "current_state": {"requirement_present": True, "closed_by_current_probe": True},
        }
    ) is False
    assert self_awareness_adapters.failure_matrix_row_is_open_requirement({"id": "other:thing"}) is False


def test_cycle_issue_inputs_extract_guard_inputs_without_live_io() -> None:
    failure_matrix = {
        "rows": [
            {
                "id": "requirement:open-kind",
                "failure_kind": "open_requirement",
                "host_layer_mutates_stack": False,
                "automatic_remediation": False,
            },
            {
                "id": "requirement:present-state",
                "current_state": {"requirement_present": True, "status": "open"},
                "host_layer_mutates_stack": False,
                "automatic_remediation": False,
            },
            {
                "id": "requirement:closed",
                "current_state": {"requirement_present": True, "status": "closed"},
                "host_layer_mutates_stack": False,
                "automatic_remediation": False,
            },
            {
                "id": "requirement:unsafe-claim",
                "failure_kind": "open_requirement",
                "host_layer_mutates_stack": True,
                "automatic_remediation": False,
            },
        ]
    }
    replay = {
        "stack_handoff_closure_readiness": {
            "open_requirement_ids": ["requirement:open-kind"],
            "summary": {"packets": 2},
        }
    }
    stack_closure_dossier = {
        "working_stack_activation_dossier": {
            "summary": {"entries": 3, "open_activation_gaps": "2"}
        }
    }
    responses = {
        "summary": {
            "automatic_responses": "0",
            "routes_with_mutating_command_if_run": "1",
        }
    }

    payload = self_awareness_adapters.cycle_issue_inputs(
        failure_matrix=failure_matrix,
        replay=replay,
        stack_closure_dossier=stack_closure_dossier,
        responses=responses,
    )

    assert [row["id"] for row in payload["open_requirement_rows"]] == [
        "requirement:open-kind",
        "requirement:present-state",
        "requirement:unsafe-claim",
    ]
    assert payload["automatic_response_count"] == 0
    assert payload["mutating_response_routes"] == 1
    assert payload["mutation_claims"] == ["requirement:unsafe-claim"]
    assert payload["stack_handoff_closure_readiness"]["summary"] == {"packets": 2}
    assert payload["working_stack_activation_summary"] == {"entries": 3, "open_activation_gaps": "2"}
    assert payload["open_working_stack_activation_gaps"] == 2


def test_cycle_initial_chain_uses_supplied_completion_predicates() -> None:
    probe_chain = {
        key: True
        for key in (
            "request",
            "capability_map",
            "requirement_probes",
            "stack_closure_dossier",
            "failure_matrix",
            "working_stack",
            "metric",
            "log",
            "trace_context",
            "context",
            "observation_events",
            "query",
            "correlation",
            "timeline",
            "spatial_graph",
            "causal_episode",
            "alert",
            "warm_e2b",
            "rag_memory",
            "nervous_freshness",
            "reaction_candidate",
            "governed_response",
        )
    }
    resident_packets: list[Any] = []
    activation_packets: list[Any] = []
    trace_packets: list[Any] = []

    def resident_complete(packet: Any) -> bool:
        resident_packets.append(packet)
        return isinstance(packet, dict) and packet.get("complete") is True

    def activation_complete(packet: Any) -> bool:
        activation_packets.append(packet)
        return isinstance(packet, dict) and packet.get("complete") is True

    def trace_complete(packet: Any) -> bool:
        trace_packets.append(packet)
        return isinstance(packet, dict) and packet.get("complete") is True

    replay = {
        "ok": True,
        "summary": {"divergences": "0"},
        "resident_cognitive_replay": {"complete": True},
        "stack_handoff_replay": {"closure_readiness_replayable": True},
    }
    activation_smoke = {"complete": True}
    trace_context = {"complete": True}

    chain = self_awareness_adapters.cycle_initial_chain(
        probe_chain=probe_chain,
        requirement_probes={"ok": True},
        stack_closure_dossier={"ok": True},
        failure_matrix={"ok": True},
        investigation={"ok": True, "checkpoints": ["checkpoint-fixture"]},
        replay=replay,
        activation_smoke=activation_smoke,
        trace_context_fallback=trace_context,
        brief={"ok": True},
        reactions={"ok": True},
        responses={"ok": True},
        resident_cognitive_replay_complete=resident_complete,
        working_stack_activation_smoke_complete=activation_complete,
        trace_context_fallback_complete=trace_complete,
    )

    assert chain["signal_fabric"] is True
    assert chain["langgraph_investigation"] is True
    assert chain["replay"] is True
    assert chain["resident_cognitive_replay"] is True
    assert chain["working_stack_activation_smoke"] is True
    assert chain["stack_handoff_readiness_replay"] is True
    assert chain["trace_context_fallback"] is True
    assert chain["semantic_brief"] is True
    assert chain["reaction_candidate"] is True
    assert chain["governed_response"] is True
    assert resident_packets == [{"complete": True}]
    assert activation_packets == [activation_smoke]
    assert trace_packets == [trace_context]


def test_cycle_export_chain_updates_keep_handoff_guards_public_safe() -> None:
    responses = {
        "summary": {
            "self_awareness_body_trace_routes": "1",
            "self_awareness_body_trace_missing": "0",
            "self_awareness_entity_event_document_routes": "1",
            "self_awareness_entity_event_document_missing": "0",
        }
    }
    export = {
        "ok": True,
        "resident_cognitive_replay": {"complete": True},
        "body_trace_handoff": {
            "host_body_context_packet_included": True,
            "resident_body_trace_replayable": True,
            "response_body_trace_included": True,
        },
        "portable_contract": {"response_entity_event_document_context_included": True},
        "response_entity_event_document_handoff": {"complete": True},
        "working_stack_link_integrity": {"complete": True},
    }

    updates = self_awareness_adapters.cycle_export_chain_updates(
        probe_chain={"body_trace": True, "entity_event_document": True},
        replay={"body_trace_replay": {"replayable": True}},
        responses=responses,
        export=export,
        autolink={"complete": True},
        autolink_complete=lambda packet: packet.get("complete") is True,
        resident_cognitive_replay_complete=lambda packet: packet.get("complete") is True,
        working_stack_link_integrity_complete=lambda packet: packet.get("complete") is True,
    )

    assert updates == {
        "autolink": True,
        "export": True,
        "resident_cognitive_export": True,
        "body_trace": True,
        "entity_event_document": True,
        "working_stack_link_integrity": True,
    }

    broken = self_awareness_adapters.cycle_export_chain_updates(
        probe_chain={"body_trace": True, "entity_event_document": True},
        replay={"body_trace_replay": {"replayable": True}},
        responses={
            "summary": {
                **responses["summary"],
                "self_awareness_entity_event_document_missing": "1",
            }
        },
        export=export,
        autolink={"complete": True},
        autolink_complete=lambda packet: packet.get("complete") is True,
        resident_cognitive_replay_complete=lambda packet: packet.get("complete") is True,
        working_stack_link_integrity_complete=lambda packet: packet.get("complete") is True,
    )
    assert broken["body_trace"] is True
    assert broken["entity_event_document"] is False


def test_working_stack_link_integrity_matrix_is_adapter_owned(tmp_path: Path) -> None:
    generated_at = "2026-01-01T00:00:00+00:00"
    latest_paths = {
        "working_stack": tmp_path / "working-stack" / "latest.json",
        "events": tmp_path / "events" / "latest.json",
        "timeline": tmp_path / "timeline" / "latest.json",
        "spatial_graph": tmp_path / "spatial-graph" / "latest.json",
        "context": tmp_path / "context" / "latest.json",
        "episodes": tmp_path / "episodes" / "latest.json",
    }
    services = [
        ("prometheus", "active_machine_signal", None),
        ("aoa-browser", "tool_runtime_degraded", "fixture browser launch failed"),
    ]
    organs: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] = [{"id": "host:fixture", "kind": "host"}]
    edges: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    episodes: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []

    for service, status, usage_gap in services:
        link = self_awareness_contracts.working_stack_link(
            service,
            generated_at,
            status=status,
            container=service,
            endpoint_ok=True,
        )
        link_id = link["link_id"]
        movement_packet_id = "samove-fixture-" + service
        current_state_digest = "state-fixture-" + service
        organs.append({
            "schema": "abyss_machine_self_awareness_working_stack_organ_v1",
            "service": service,
            "machine_usage_status": status,
            "usage_gap": usage_gap,
            "time_space_context_link": link,
            "runtime": {"running": True, "container": service},
            "deep_usage_proven": usage_gap is None,
            "evidence_refs": [{"path": str(latest_paths["working_stack"]), "service": service}],
            "policy": {"host_layer_mutates_stack": False},
        })
        event = self_awareness_contracts.make_event(
            "organ_movement",
            "working-stack",
            event_time=generated_at,
            resource={
                "service": service,
                "container": service,
                "owner_surface": "abyss-stack",
                "movement_packet_id": movement_packet_id,
                "current_state_digest": current_state_digest,
                "movement_categories": ["raw_signal", "episode_candidate"] if usage_gap else ["raw_signal"],
                "selected_for_episode": usage_gap is not None,
                "write": False,
            },
            context={
                "working_stack_link_id": link_id,
                "movement_packet_id": movement_packet_id,
                "current_state_digest": current_state_digest,
            },
            space={"host": "fixture", "owner_surface": "abyss-stack", "service": service, "container": service},
            evidence_refs=[{"path": str(latest_paths["working_stack"]), "service": service}],
            truth_level="working_stack_inventory",
        )
        events.append(event)
        service_node = "service:" + service
        link_node = "working_stack_link:" + link_id
        nodes.extend([
            {"id": service_node, "kind": "service"},
            {"id": link_node, "kind": "working_stack_context_link"},
        ])
        edges.append({"from": service_node, "to": link_node, "kind": "has_time_space_context_link"})
        contexts.append({"key": link_id, "event_ids": [event["event_id"]], "context": {"working_stack_link_id": link_id}})
        episodes.append({
            "episode_id": "episode-" + service,
            "event_ids": [event["event_id"]],
            "affected_spatial_nodes": [service_node, link_node],
        })
        if usage_gap:
            coverage_rows.append({
                "id": "working_stack_gap:" + service,
                "service": service,
                "working_stack_link_id": link_id,
                "activation_smoke": {
                    "schema": "abyss_machine_self_awareness_working_stack_activation_smoke_compact_v1",
                    "complete": True,
                    "service": service,
                    "working_stack_link_id": link_id,
                    "policy": {"host_layer_mutates_stack": False},
                },
            })

    working_stack = {
        "schema": "abyss_machine_self_awareness_working_stack_inventory_v1",
        "summary": {"organs": len(organs), "usage_gaps": 1},
        "organs": organs,
    }
    matrix = self_awareness_adapters.working_stack_link_integrity_matrix(
        working_stack_doc=working_stack,
        events_doc={"schema": "abyss_machine_self_awareness_events_v1", "events": events},
        timeline_doc={"schema": "abyss_machine_self_awareness_timeline_v1", "windows": [{"event_ids": [event["event_id"] for event in events]}]},
        spatial_doc={"schema": "abyss_machine_self_awareness_spatial_graph_v1", "nodes": nodes, "edges": edges},
        context_doc={"schema": "abyss_machine_self_awareness_context_v1", "contexts": contexts},
        episodes_doc={"schema": "abyss_machine_self_awareness_episodes_v1", "episodes": episodes},
        coverage_gap_rows=coverage_rows,
        generated_at=generated_at,
        schema_prefix="abyss_machine",
        version="0.test",
        latest_paths=latest_paths,
    )

    assert matrix["schema"] == "abyss_machine_self_awareness_working_stack_link_integrity_matrix_v1"
    assert matrix["ok"] is True
    assert self_awareness_adapters.working_stack_link_integrity_matrix_complete(matrix, schema_prefix="abyss_machine") is True
    assert self_awareness_adapters.working_stack_dependent_link_readmodels_fresh(matrix) is True
    assert self_awareness_adapters.working_stack_link_integrity_matches_working_stack(working_stack, matrix) is True
    assert matrix["summary"]["rows"] == 2
    assert matrix["summary"]["complete_rows"] == 2
    assert matrix["summary"]["usage_gap_rows"] == 1
    assert matrix["summary"]["usage_gap_rows_with_coverage"] == 1
    assert matrix["summary"]["usage_gap_rows_with_activation_smoke"] == 1
    assert set(matrix["rows_by_service"]) == {"prometheus", "aoa-browser"}
    assert matrix["rows_by_service"]["aoa-browser"]["episode_ids"] == ["episode-aoa-browser"]
    assert matrix["rows_by_service"]["prometheus"]["adjacent_episode_ids"] == ["episode-prometheus"]
    assert matrix["evidence_refs"][0]["path"] == str(latest_paths["working_stack"])

    stale = json.loads(json.dumps(matrix))
    stale["summary"]["timeline_linked"] = 0
    assert self_awareness_adapters.working_stack_dependent_link_readmodels_fresh(stale) is False

    mismatched = json.loads(json.dumps(working_stack))
    mismatched["organs"][0]["machine_usage_status"] = "different"
    assert self_awareness_adapters.working_stack_link_integrity_matches_working_stack(mismatched, matrix) is False


def test_autolink_predicates_are_adapter_owned() -> None:
    source_rows = [
        {
            "service": "aoa-browser",
            "machine_usage_status": "tool_runtime_degraded",
            "usage_gap": "fixture browser launch failed",
            "working_stack_link_id": "saworklink-fixture",
            "current_state_digest": "state-fixture",
            "spatial_nodes": ["service:aoa-browser", "working_stack_link:saworklink-fixture"],
            "context_key": "saworklink-fixture",
            "episode_required": True,
            "episode_ids": ["saepisode-fixture"],
            "coverage_gap_row_id": "working_stack_gap:aoa-browser",
        },
        {
            "service": "prometheus",
            "machine_usage_status": "active_machine_signal",
            "working_stack_link_id": "saworklink-prometheus",
        },
    ]
    expected_entries = [{
        "service": "aoa-browser",
        "machine_usage_status": "tool_runtime_degraded",
        "working_stack_link_id": "saworklink-fixture",
    }]

    state = self_awareness_adapters.autolink_row_state(source_rows[0])
    activation_entries = self_awareness_adapters.activation_entries_from_link_rows(source_rows)

    assert state["movement_current_state_digest"] == "state-fixture"
    assert state["spatial_nodes"] == ["service:aoa-browser", "working_stack_link:saworklink-fixture"]
    assert activation_entries == expected_entries
    assert self_awareness_adapters.activation_entries_cover_expected(activation_entries, expected_entries) is True
    assert self_awareness_adapters.activation_entries_cover_expected([], expected_entries) is False

    dossier = {
        "entries": [
            {"requirement_id": "stack.database-graph.read-route", "status": "open"},
            {"requirement_id": "stack.trace-backend", "status": "closed"},
        ],
    }
    stale_episodes = {
        "schema": "abyss_machine_self_awareness_episodes_v1",
        "episodes": [{"episode_id": "saepisode-trace", "affected_spatial_nodes": ["stack_requirement:stack.trace-backend"]}],
    }
    fresh_episodes = {
        "schema": "abyss_machine_self_awareness_episodes_v1",
        "episodes": [{"episode_id": "saepisode-db", "affected_spatial_nodes": ["stack_requirement:stack.database-graph.read-route"]}],
    }

    assert self_awareness_adapters.episodes_cover_stack_requirements(
        stale_episodes,
        dossier,
        schema_prefix="abyss_machine",
    ) is False
    assert self_awareness_adapters.episodes_cover_stack_requirements(
        fresh_episodes,
        dossier,
        schema_prefix="abyss_machine",
    ) is True

    autolink_doc = {
        "schema": "abyss_machine_self_awareness_autolink_v1",
        "ok": True,
        "state_digest": "a" * 32,
        "state_delta": {"policy": {"host_layer_mutates_stack": False, "executes_commands": False}},
        "summary": {
            "organ_links": 1,
            "organ_links_complete": 1,
            "stack_requirement_links": 1,
            "stack_requirement_links_complete": 1,
            "synthetic_scenarios": 1,
            "synthetic_scenarios_complete": 1,
        },
        "organ_links": [
            {
                "schema": "abyss_machine_self_awareness_autolink_organ_row_v1",
                "complete": True,
                "service": "aoa-browser",
                "working_stack_link_id": "saworklink-fixture",
                "usage_gap": "fixture browser launch failed",
                "event_id": "saevt-fixture",
                "movement_packet_id": "samove-fixture",
                "movement_current_state_digest": "state-fixture",
                "episode_required": True,
                "episode_ids": ["saepisode-fixture"],
                "activation_smoke": {
                    "complete": True,
                    "working_stack_link_id": "saworklink-fixture",
                },
                "checks": {
                    "time_linked": True,
                    "space_linked": True,
                    "context_linked": True,
                    "movement_packet_linked": True,
                    "episode_linked": True,
                    "gap_has_activation_smoke": True,
                },
                "policy": {"host_layer_mutates_stack": False},
            }
        ],
        "stack_requirement_links": [
            {
                "schema": "abyss_machine_self_awareness_autolink_stack_requirement_row_v1",
                "complete": True,
                "requirement_id": "stack.database-graph.read-route",
                "episode_ids": ["saepisode-db"],
                "checks": {
                    "closure_acceptance": True,
                    "coverage_impact": True,
                    "owner_route": True,
                },
                "policy": {"host_layer_mutates_stack": False},
            }
        ],
        "synthetic_scenarios": [
            {
                "schema": "abyss_machine_self_awareness_autolink_synthetic_scenario_v1",
                "complete": True,
                "policy": {"host_layer_mutates_stack": False, "executes_commands": False},
            }
        ],
        "policy": {
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "automatic_remediation": False,
        },
    }

    assert self_awareness_adapters.autolink_complete(autolink_doc, schema_prefix="abyss_machine") is True

    broken = json.loads(json.dumps(autolink_doc))
    broken["organ_links"][0]["activation_smoke"]["working_stack_link_id"] = "saworklink-stale"
    assert self_awareness_adapters.autolink_complete(broken, schema_prefix="abyss_machine") is False


def test_autolink_document_is_adapter_owned(tmp_path: Path) -> None:
    prefix = "abyss_machine"
    service = "aoa-browser"
    requirement_id = "stack.browser-tools.runtime"
    link_id = "saworklink-aoa-browser"
    latest_paths = {
        "working_stack": tmp_path / "working-stack/latest.json",
        "coverage_audit": tmp_path / "coverage-audit/latest.json",
        "stack_closure_dossier": tmp_path / "stack-closure-dossier/latest.json",
        "activation_smoke": tmp_path / "activation-smoke/latest.json",
        "episodes": tmp_path / "episodes/latest.json",
        "autolink": tmp_path / "autolink/latest.json",
    }
    coverage_audit = {
        "schema": "abyss_machine_self_awareness_objective_coverage_audit_v1",
        "working_stack_link_integrity": {
            "rows": [
                {
                    "service": service,
                    "owner": "abyss-stack",
                    "machine_usage_status": "tool_runtime_degraded",
                    "usage_gap": "functional runtime smoke failed",
                    "working_stack_link_id": link_id,
                    "event_id": "saevt-working-stack-browser",
                    "movement_packet_id": "samove-browser",
                    "current_state_digest": "state-browser",
                    "state_changed": True,
                    "movement_categories": ["degradation", "episode_candidate"],
                    "selected_for_episode": True,
                    "selected_for_resident_reasoning": True,
                    "degradation_reasons": ["failed_endpoint_probe"],
                    "timeline_bucket": "2026-07-08T00:00:00Z",
                    "spatial_nodes": [f"service:{service}", f"working_stack_link:{link_id}"],
                    "context_key": link_id,
                    "episode_required": True,
                    "episode_ids": ["saepisode-gap"],
                    "adjacent_episode_ids": ["saepisode-browser-adjacent"],
                    "coverage_gap_row_id": "working_stack_gap:aoa-browser",
                    "complete": True,
                    "evidence_refs": [{"path": "fixture/autolink-source.json", "service": service}],
                    "policy": {"host_layer_mutates_stack": False},
                }
            ]
        },
    }
    stack_closure_dossier = {
        "schema": "abyss_machine_self_awareness_stack_closure_dossier_v1",
        "summary": {"open_stack_requirements": 1},
        "entries": [
            {
                "requirement_id": requirement_id,
                "owner": "abyss-stack",
                "status": "open",
                "complete": True,
                "blocking_check_keys": ["working_stack_usage_gap"],
                "current_state_digest": "state-requirement",
                "closure_acceptance": {
                    "acceptance_id": "saaccept-browser-runtime",
                    "complete": True,
                    "stack_compat_requirement": {"requirement_id": requirement_id},
                },
                "coverage_impact": {
                    "complete": True,
                    "coverage_planes": ["runtime"],
                    "affected_stack_surfaces": ["compose/51-browser-tools.yml"],
                    "affected_machine_surfaces": [f"service:{service}"],
                },
                "evidence_refs": [{"path": "fixture/stack-requirement.json", "requirement_id": requirement_id}],
                "policy": {"host_layer_mutates_stack": False},
            }
        ],
    }
    doc = self_awareness_adapters.autolink_document(
        working_stack_doc={
            "schema": "abyss_machine_self_awareness_working_stack_inventory_v1",
            "summary": {"usage_gaps": 1},
        },
        coverage_audit_doc=coverage_audit,
        stack_closure_dossier_doc=stack_closure_dossier,
        activation_smoke_doc={
            "schema": "abyss_machine_self_awareness_working_stack_activation_smoke_v1",
            "by_service": {service: {"ok": True, "service": service, "working_stack_link_id": link_id}},
        },
        episodes_doc={
            "schema": "abyss_machine_self_awareness_episodes_v1",
            "episodes": [
                {"episode_id": "saepisode-gap", "affected_spatial_nodes": [f"stack_requirement:{requirement_id}"]}
            ],
        },
        previous={
            "schema": "abyss_machine_self_awareness_autolink_v1",
            "generated_at": "2026-07-08T00:00:00Z",
            "state_digest": "previous-state",
            "summary": {"service_ids": [service], "requirement_ids": [], "open_stack_requirements": 0, "working_stack_usage_gaps": 0},
            "organ_links_by_service": {service: {"current_state_digest": "old-state"}},
            "stack_requirement_links_by_requirement": {},
        },
        dependency_refresh={"events": 1},
        generated_at="2026-07-08T00:05:00Z",
        version="0.0-test",
        schema_prefix=prefix,
        cycle_id="sacycle-fixture",
        probe_run_id="saprobe-fixture",
        latest_paths=latest_paths,
        activation_smoke_compact=lambda row: {
            "complete": True,
            "working_stack_link_id": row.get("working_stack_link_id"),
        },
        stack_requirement_closure_acceptance_complete=lambda packet: packet.get("complete") is True,
        stack_coverage_impact_complete=lambda packet: packet.get("complete") is True,
    )

    assert self_awareness_adapters.autolink_complete(doc, schema_prefix=prefix) is True
    assert doc["schema"] == "abyss_machine_self_awareness_autolink_v1"
    assert doc["ok"] is True
    assert doc["cycle_id"] == "sacycle-fixture"
    assert doc["summary"]["organ_links"] == 1
    assert doc["summary"]["stack_requirement_links"] == 1
    assert doc["summary"]["synthetic_scenarios_complete"] == 3
    assert doc["summary"]["state_changed"] is True
    assert doc["summary"]["changed_services"] == [service]
    assert doc["summary"]["dependency_refresh_applied"] is True
    assert doc["organ_links_by_service"][service]["activation_smoke"]["complete"] is True
    assert doc["stack_requirement_links_by_requirement"][requirement_id]["episode_ids"] == ["saepisode-gap"]
    assert doc["state_delta"]["added_requirements"] == [requirement_id]
    assert doc["policy"]["host_layer_mutates_stack"] is False
    assert doc["policy"]["executes_commands"] is False
    evidence_paths = {ref["path"] for ref in doc["evidence_refs"]}
    assert str(latest_paths["working_stack"]) in evidence_paths
    assert str(latest_paths["autolink"]) in {
        ref["path"]
        for scenario in doc["synthetic_scenarios"]
        for ref in scenario["evidence_refs"]
        if isinstance(ref, dict)
    }


def test_activation_smoke_predicates_are_adapter_owned() -> None:
    prefix = "abyss_machine"
    service = "aoa-browser"
    link_id = "saworklink-fixture"
    status = "tool_runtime_degraded"

    def event_issues(event: dict[str, object]) -> list[str]:
        if event.get("schema") == "abyss_machine_observation_event_v1" and event.get("event_id"):
            return []
        return ["invalid_event"]

    documents = [
        {"document_id": f"self-awareness.fixture.{index}", "path": f"/var/lib/abyss-machine/fixture/{index}.json"}
        for index in range(5)
    ]
    packet = {
        "schema": "abyss_machine_self_awareness_stack_organ_use_packet_v1",
        "packet_id": "sause-fixture",
        "service": service,
        "owner": "abyss-stack",
        "entity": {
            "schema": "abyss_machine_self_awareness_stack_organ_use_entity_v1",
            "entity_kind": "stack_organ",
            "entity_id": f"stack.organ.{service}",
        },
        "event": {
            "schema": "abyss_machine_self_awareness_stack_organ_use_event_v1",
            "event_id": "saevt-fixture",
            "working_stack_link_id": link_id,
            "machine_usage_status": status,
            "classification": "running_functional_smoke_failed",
        },
        "documents": documents,
        "document_ids": [str(doc["document_id"]) for doc in documents],
        "current_state": {"current_state_digest": "state-fixture"},
        "time_space_context": {"context": {"working_stack_link_id": link_id}},
        "observed_signal": {"schema": "abyss_machine_observation_event_v1", "event_id": "saevt-observed"},
        "movement_selection": {
            "schema": "abyss_machine_self_awareness_stack_organ_movement_selection_v1",
            "categories": ["raw_signal", "degradation"],
            "selected_reason": "fixture degradation",
            "selected_for_resident_reasoning": True,
        },
        "activation_gap": {"classification": "running_functional_smoke_failed"},
        "automation": {
            "required_in": ["activation-smoke", "export", "validate"],
            "host_layer_mutates_stack": False,
            "executes_stack_verifiers": False,
        },
        "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/activation-smoke/latest.json"}],
        "checks": {"entity_named": True, "event_named": True, "policy": True},
        "missing_checks": [],
        "policy": {
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "executes_commands": False,
            "action_execution": False,
            "automatic_remediation": False,
            "raw_secrets_included": False,
            "raw_private_content_included": False,
        },
    }
    movement_row = {
        "schema": "abyss_machine_self_awareness_working_stack_activation_smoke_row_v1",
        "row_kind": "organ_movement",
        "ok": True,
        "service": service,
        "owner": "abyss-stack",
        "machine_usage_status": status,
        "working_stack_link_id": link_id,
        "investigation": {
            "schema": "abyss_machine_self_awareness_working_stack_activation_smoke_investigation_v1",
            "actual_run": False,
        },
        "replay": {
            "schema": "abyss_machine_self_awareness_working_stack_activation_smoke_replay_v1",
            "actual_run": False,
        },
        "stack_organ_use_packet": packet,
        "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/working-stack/latest.json"}],
        "policy": {
            "movement_packet": True,
            "actual_investigate_replay_run": False,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "action_execution": False,
            "automatic_remediation": False,
        },
    }

    assert self_awareness_adapters.stack_organ_use_packet_complete(
        packet,
        schema_prefix=prefix,
        event_issues=event_issues,
    ) is True
    assert self_awareness_adapters.working_stack_activation_smoke_row_complete(
        movement_row,
        schema_prefix=prefix,
        investigation_node_count=3,
        event_issues=event_issues,
    ) is True

    actual_row = json.loads(json.dumps(movement_row))
    actual_row.pop("row_kind")
    actual_row["usage_gap"] = "fixture usage gap"
    actual_row["episode_id"] = "saepisode-fixture"
    actual_row["investigation"] = {
        "schema": "abyss_machine_self_awareness_working_stack_activation_smoke_investigation_v1",
        "ok": True,
        "selected_episode_matches": True,
        "working_stack_gap_complete": True,
        "working_stack_gap_matches": True,
        "evidence_validation_fails": 0,
        "checkpoints": 3,
        "graph_nodes": 3,
    }
    actual_row["replay"] = {
        "schema": "abyss_machine_self_awareness_working_stack_activation_smoke_replay_v1",
        "ok": True,
        "thread_matches": True,
        "working_stack_gap_selected": True,
        "working_stack_gap_replayable": True,
        "working_stack_gap_matches": True,
        "divergences": 0,
        "stack_handoff_closure_readiness_replayable": True,
        "resident_cognitive_replay_complete": True,
    }
    actual_row["policy"]["actual_investigate_replay_run"] = True

    assert self_awareness_adapters.working_stack_activation_smoke_row_complete(
        actual_row,
        schema_prefix=prefix,
        investigation_node_count=3,
        event_issues=event_issues,
    ) is True
    actual_row["replay"]["divergences"] = 1
    assert self_awareness_adapters.working_stack_activation_smoke_row_complete(
        actual_row,
        schema_prefix=prefix,
        investigation_node_count=3,
        event_issues=event_issues,
    ) is False

    compact = self_awareness_adapters.working_stack_activation_smoke_compact(
        movement_row,
        schema_prefix=prefix,
        investigation_node_count=3,
        event_issues=event_issues,
    )
    assert compact["schema"] == "abyss_machine_self_awareness_working_stack_activation_smoke_compact_v1"
    assert compact["complete"] is True
    assert compact["stack_organ_use_packet_id"] == "sause-fixture"
    assert compact["activation_gap_classification"] == "running_functional_smoke_failed"

    smoke = {
        "schema": "abyss_machine_self_awareness_working_stack_activation_smoke_v1",
        "ok": True,
        "run_id": "saactsmoke-fixture",
        "rows": [movement_row],
        "stack_organ_use_packets": [packet],
        "stack_organ_use_packet_by_service": {service: packet},
        "summary": {
            "stack_organs_expected_services": [service],
            "stack_organs_expected": 1,
            "rows": 1,
            "rows_ok": 1,
            "stack_organ_use_packets": 1,
            "stack_organ_use_packets_complete": 1,
            "service_ids": [service],
            "stack_organs_without_use_packets": [],
            "all_stack_organs_have_use_packets": True,
            "failed_services": [],
        },
        "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/activation-smoke/latest.json"}],
        "policy": {
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "action_execution": False,
            "automatic_remediation": False,
        },
    }
    activation_entries = [{"service": service, "machine_usage_status": status, "working_stack_link_id": link_id}]

    assert self_awareness_adapters.working_stack_activation_smoke_complete(
        smoke,
        schema_prefix=prefix,
        investigation_node_count=3,
        event_issues=event_issues,
    ) is True
    assert self_awareness_adapters.activation_smoke_needs_refresh(
        smoke,
        activation_entries,
        schema_prefix=prefix,
        investigation_node_count=3,
        event_issues=event_issues,
    ) is False

    broken_packet = json.loads(json.dumps(packet))
    broken_packet["observed_signal"]["event_id"] = ""
    assert self_awareness_adapters.stack_organ_use_packet_complete(
        broken_packet,
        schema_prefix=prefix,
        event_issues=event_issues,
    ) is False
    changed_entries = [{"service": service, "machine_usage_status": status, "working_stack_link_id": "saworklink-new"}]
    assert self_awareness_adapters.activation_smoke_needs_refresh(
        smoke,
        changed_entries,
        schema_prefix=prefix,
        investigation_node_count=3,
        event_issues=event_issues,
    ) is True


def test_activation_gap_and_handoff_routes_are_adapter_owned(tmp_path: Path) -> None:
    prefix = "abyss_machine"
    service = "aoa-browser"
    status = "tool_runtime_degraded"
    requirement_id = "stack.trace-backend"
    safe_next = self_awareness_contracts.working_stack_gap_safe_next_action(
        service,
        status,
        "functional runtime smoke failed",
    )

    activation_route = self_awareness_adapters.working_stack_activation_gap_route(
        {
            "schema": "abyss_machine_self_awareness_working_stack_usage_gap_v1",
            "service": service,
            "owner_route": "abyss-stack",
            "working_stack_link_id": "saworklink-aoa-browser",
            "machine_usage_status": status,
            "activation_kind": "stack_tool_runtime_smoke_gap",
            "usage_gap": "functional runtime smoke failed",
            "runtime_present": True,
            "runtime_running": True,
            "container": service,
            "health": "healthy",
            "runtime_state": "running",
            "runtime_status": "Up 1 minute",
            "runtime_stack_managed": True,
            "declared": True,
            "declared_modules": ["51-browser-tools.yml"],
            "endpoint_ok": True,
            "endpoint_probe_count": 3,
            "failed_probe_names": ["playwright-chromium-launch"],
            "ok_probe_names": ["health", "private-host-guard"],
            "service_roots": 1,
            "model_roots": 0,
            "deep_usage_proven": False,
            "closure_blocker_keys": [status, "usage_gap:fixture"],
            "safe_next_action": safe_next,
            "verifier_commands": safe_next["verifier_commands"],
        },
        episode_id="saepisode-gap",
        activation_row={
            "complete": True,
            "investigation": {"thread_id": "sainv-gap", "selected_episode_matches": True},
            "replay": {
                "thread_id": "sainv-gap",
                "thread_matches": True,
                "working_stack_gap_replayable": True,
            },
        },
        schema_prefix=prefix,
        working_stack_latest_path=tmp_path / "working-stack/latest.json",
        activation_smoke_latest_path=tmp_path / "activation-smoke/latest.json",
        episodes_latest_path=tmp_path / "episodes/latest.json",
        process_container_latest_path=tmp_path / "processes/containers/latest.json",
    )

    assert self_awareness_adapters.working_stack_activation_gap_route_complete(
        activation_route,
        schema_prefix=prefix,
    ) is True
    assert activation_route["classification"] == "running_functional_smoke_failed"
    assert activation_route["activation_smoke"]["working_stack_gap_replayable"] is True
    assert activation_route["policy"]["host_layer_mutates_stack"] is False
    assert [Path(ref["path"]).name for ref in activation_route["evidence_refs"]] == ["latest.json"] * 4

    closure_packet = {
        "schema": "abyss_machine_self_awareness_stack_requirement_closure_acceptance_v1",
        "acceptance_id": "saclose-trace-backend",
        "status": "open",
        "requirement_status": "open",
        "surface_kind": "trace_backend",
        "safe_next_action": {
            "requires_human_approval": True,
            "executes_commands": False,
            "host_layer_mutates_stack": False,
        },
        "stack_compat_requirement": {
            "requirement_id": requirement_id,
            "surface_kind": "trace_backend",
            "coverage_contract": {
                "organ": "trace_join_backbone",
                "coverage_planes": ["trace_context", "replay"],
                "closure_value": "stack trace joins become replayable",
            },
        },
        "pre_close_identity": {
            "current_state_digest": "state-trace-backend",
            "current_state_keys": ["trace_backend:missing"],
            "missing_check_keys": ["trace_search_ready"],
            "fulfilled_check_keys": ["trace_storage_ready"],
            "coverage_planes": ["trace_context", "replay"],
        },
        "negative_controls": [{"key": "host_does_not_patch_stack"}],
        "post_close_success_predicates": [{"key": "trace_search_ready"}],
        "post_close_verifier_chain": [{"command": "abyss-machine self-awareness cycle --json"}],
    }

    handoff_route = self_awareness_adapters.stack_requirement_handoff_route(
        requirement_id,
        episode_id="saepisode-stack",
        closure_packet=closure_packet,
        stack_replay={
            "closure_readiness_replayable": True,
            "open_requirement_ids": [requirement_id],
        },
        schema_prefix=prefix,
        stack_closure_dossier_latest_path=tmp_path / "stack-closure/latest.json",
        requirement_probes_latest_path=tmp_path / "requirement-probes/latest.json",
        replay_latest_path=tmp_path / "replay/latest.json",
        closure_acceptance_complete=lambda packet: packet.get("acceptance_id") == "saclose-trace-backend",
    )

    assert self_awareness_adapters.stack_requirement_handoff_route_complete(
        handoff_route,
        schema_prefix=prefix,
    ) is True
    assert handoff_route["owner_route"] == "abyss-stack"
    assert handoff_route["impact"]["organ"] == "trace_join_backbone"
    assert handoff_route["closure_acceptance"]["complete"] is True
    assert handoff_route["lineage"]["open_requirement_present_in_replay"] is True
    assert handoff_route["policy"]["host_layer_mutates_stack"] is False
    assert self_awareness_adapters.stack_requirement_handoff_route(
        "",
        schema_prefix=prefix,
        stack_closure_dossier_latest_path=tmp_path / "stack-closure/latest.json",
        requirement_probes_latest_path=tmp_path / "requirement-probes/latest.json",
        replay_latest_path=tmp_path / "replay/latest.json",
        closure_acceptance_complete=lambda _packet: False,
    ) == {}

    broken = json.loads(json.dumps(handoff_route))
    broken["lineage"]["stack_handoff_replayable"] = False
    assert self_awareness_adapters.stack_requirement_handoff_route_complete(
        broken,
        schema_prefix=prefix,
    ) is False


def test_activation_scenario_and_closure_packets_are_adapter_owned() -> None:
    prefix = "abyss_machine"
    entry = {
        "service": "aoa-browser",
        "machine_usage_status": "tool_runtime_degraded",
        "activation_kind": "stack_tool_runtime_smoke_gap",
        "working_stack_link_id": "saworklink-aoa-browser",
        "usage_gap": "functional runtime smoke failed",
        "current_state_digest": "state-aoa-browser",
        "coverage_planes": ["working_stack_body", "runtime_organs", "investigation_replay"],
        "missing_checks": [
            {"key": "working_stack_usage_gap", "message": "gap remains open"},
            {"key": "probe_failed:playwright-chromium-launch", "probe": "playwright-chromium-launch"},
        ],
        "fulfilled_checks": [
            {"key": "working_stack_time_space_context_link"},
            {"key": "runtime_container_running"},
        ],
        "failed_probe_names": ["playwright-chromium-launch"],
        "ok_probe_names": ["health", "private-host-guard"],
        "runtime": {"container": "aoa-browser", "running": True, "health": "healthy"},
        "verifier_commands": [
            "abyss-machine self-awareness working-stack --json",
            "abyss-machine self-awareness coverage-audit --json",
        ],
        "stack_source_refs": [{"path": "compose/51-browser-tools.yml", "kind": "compose"}],
        "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/working-stack/latest.json"}],
        "closure_blocker_keys": ["working_stack_usage_gap", "probe_failed:playwright-chromium-launch"],
    }

    scenario = self_awareness_adapters.working_stack_activation_synthetic_scenario(
        entry,
        "2026-07-08T00:00:00Z",
        schema_prefix=prefix,
    )
    assert self_awareness_adapters.working_stack_activation_synthetic_scenario_complete(
        scenario,
        schema_prefix=prefix,
    ) is True
    assert scenario["current_result"] == "functional_tool_smoke_failed"
    assert scenario["current_observation"]["failed_probe_names"] == ["playwright-chromium-launch"]
    assert scenario["policy"]["host_layer_mutates_stack"] is False

    closure = self_awareness_adapters.working_stack_activation_closure_acceptance(
        entry,
        "2026-07-08T00:00:00Z",
        schema_prefix=prefix,
    )
    assert self_awareness_adapters.working_stack_activation_closure_acceptance_complete(
        closure,
        schema_prefix=prefix,
    ) is True
    assert closure["status"] == "awaiting_stack_owner_change"
    assert closure["stack_compat_requirement"]["owner"] == "abyss-stack"
    assert closure["stack_compat_requirement"]["operator_boundary"]["abyss_machine_executes_stack_change"] is False
    assert closure["policy"]["executes_commands"] is False

    broken_scenario = json.loads(json.dumps(scenario))
    broken_scenario["evidence_refs"] = []
    assert self_awareness_adapters.working_stack_activation_synthetic_scenario_complete(
        broken_scenario,
        schema_prefix=prefix,
    ) is False
    broken_closure = json.loads(json.dumps(closure))
    broken_closure["pre_close_identity"]["missing_check_keys"] = []
    assert self_awareness_adapters.working_stack_activation_closure_acceptance_complete(
        broken_closure,
        schema_prefix=prefix,
    ) is False


def test_activation_entry_builder_is_adapter_owned(tmp_path: Path) -> None:
    prefix = "abyss_machine"
    service = "aoa-browser"
    status = "tool_runtime_degraded"
    link_id = "saworklink-aoa-browser"
    organ = {
        "service": service,
        "owner": "abyss-stack",
        "machine_usage_status": status,
        "usage_gap": "functional runtime smoke failed",
        "runtime": {
            "present": True,
            "running": True,
            "container": "aoa-browser",
            "health": "healthy",
            "state": "running",
            "status": "Up",
        },
        "declared": {"present": True, "modules": ["compose/51-browser-tools.yml"]},
        "endpoint_ok": False,
        "deep_usage_proven": False,
        "time_space_context_link": {
            "link_id": link_id,
            "time": {"observed_at": "2026-07-08T00:00:00Z"},
        },
        "endpoint_probes": [
            {
                "probe": "playwright-chromium-launch",
                "kind": "tool_smoke",
                "ok": False,
                "error": "browser launch failed",
                "elapsed_ms": 120,
            },
            {
                "probe": "http-health",
                "kind": "http_json",
                "ok": True,
                "status_code": 200,
                "elapsed_ms": 14,
            },
        ],
        "stack_source_refs": [{"path": "compose/51-browser-tools.yml", "kind": "compose"}],
        "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/working-stack/latest.json"}],
    }

    entry = self_awareness_adapters.working_stack_activation_entry(
        organ,
        1,
        "2026-07-08T00:00:00Z",
        schema_prefix=prefix,
        working_stack_latest_path=tmp_path / "working-stack/latest.json",
        spatial_graph_latest_path=tmp_path / "spatial-graph/latest.json",
        episodes_latest_path=tmp_path / "episodes/latest.json",
        alerts_latest_path=tmp_path / "alerts/latest.json",
    )

    assert self_awareness_adapters.working_stack_activation_entry_complete(entry, schema_prefix=prefix) is True
    assert entry["activation_kind"] == "stack_tool_runtime_smoke_gap"
    assert "probe_failed:playwright-chromium-launch" in entry["closure_blocker_keys"]
    assert entry["safe_next_action"]["host_layer_mutates_stack"] is False
    assert entry["runbook_candidate"]["machine_executes_stack_change"] is False
    assert entry["closure_acceptance"]["complete"] is True
    assert entry["synthetic_scenario"]["complete"] is True
    assert entry["evidence_refs"][0]["path"] == str(tmp_path / "working-stack/latest.json")


def test_activation_dossier_document_is_adapter_owned(tmp_path: Path) -> None:
    prefix = "abyss_machine"
    service = "aoa-browser"
    status = "tool_runtime_degraded"
    link_id = "saworklink-aoa-browser"
    working_stack_doc = {
        "schema": "abyss_machine_self_awareness_working_stack_inventory_v1",
        "organs": [
            {
                "service": service,
                "owner": "abyss-stack",
                "machine_usage_status": status,
                "usage_gap": "functional runtime smoke failed",
                "runtime": {"present": True, "running": True, "container": service, "health": "healthy"},
                "declared": {"present": True, "modules": ["compose/51-browser-tools.yml"]},
                "endpoint_ok": False,
                "deep_usage_proven": False,
                "time_space_context_link": {"link_id": link_id, "time": {"observed_at": "2026-07-08T00:00:00Z"}},
                "endpoint_probes": [{"probe": "playwright-chromium-launch", "kind": "tool_smoke", "ok": False}],
                "stack_source_refs": [{"path": "compose/51-browser-tools.yml", "kind": "compose"}],
                "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/working-stack/latest.json"}],
            }
        ],
    }

    dossier = self_awareness_adapters.working_stack_activation_dossier_document(
        working_stack_doc,
        generated_at="2026-07-08T00:00:00Z",
        version="0.0-test",
        schema_prefix=prefix,
        working_stack_latest_path=tmp_path / "working-stack/latest.json",
        spatial_graph_latest_path=tmp_path / "spatial-graph/latest.json",
        episodes_latest_path=tmp_path / "episodes/latest.json",
        alerts_latest_path=tmp_path / "alerts/latest.json",
        artifact_refs={"working_stack": {"path": str(tmp_path / "working-stack/latest.json"), "exists": False}},
    )

    assert dossier["schema"] == "abyss_machine_self_awareness_working_stack_activation_dossier_v1"
    assert dossier["ok"] is True
    assert dossier["summary"]["open_activation_gaps"] == 1
    assert dossier["summary"]["activation_entries_complete"] == 1
    assert dossier["synthetic_scenario_matrix"]["ok"] is True
    assert dossier["closure_acceptance_matrix"]["ok"] is True
    assert dossier["working_stack_activation_handoff"]["policy"]["host_layer_mutates_stack"] is False
    assert dossier["entries"][0]["service"] == service
    assert dossier["artifact_refs"]["working_stack"]["exists"] is False


def test_working_stack_gap_episodes_are_adapter_owned(tmp_path: Path) -> None:
    prefix = "abyss_machine"
    service = "aoa-browser"
    status = "tool_runtime_degraded"
    link_id = "saworklink-aoa-browser"
    working_stack_path = tmp_path / "working-stack/latest.json"
    events_path = tmp_path / "events/latest.json"
    spatial_path = tmp_path / "spatial-graph/latest.json"
    process_path = tmp_path / "process-container/latest.json"
    working_stack_doc = {
        "schema": "abyss_machine_self_awareness_working_stack_inventory_v1",
        "organs": [
            {
                "service": service,
                "owner": "abyss-stack",
                "machine_usage_status": status,
                "usage_gap": "functional runtime smoke failed",
                "runtime": {
                    "present": True,
                    "running": True,
                    "container": service,
                    "health": "healthy",
                    "state": "running",
                    "status": "Up 3 minutes",
                    "stack_managed": True,
                },
                "declared": {"present": True, "modules": ["compose/51-browser-tools.yml"]},
                "endpoint_ok": False,
                "deep_usage_proven": False,
                "time_space_context_link": {
                    "link_id": link_id,
                    "time": {"observed_at": "2026-07-08T00:00:00Z", "bucket": "2026-07-08T00:00:00Z"},
                },
                "endpoint_probes": [
                    {"probe": "playwright-chromium-launch", "kind": "tool_smoke", "ok": False},
                    {"probe": "http-health", "kind": "http_json", "ok": True, "url": "http://127.0.0.1:9222/json/version"},
                ],
                "service_roots": ["fixture-stack-root"],
                "evidence_refs": [{"path": str(tmp_path / "fixture-evidence/latest.json"), "service": service}],
            }
        ],
    }
    events = [
        {
            "source": "working-stack",
            "event_id": "saevt-working-stack-browser",
            "resource": {"service": service},
        }
    ]

    episodes, episode_ids = self_awareness_adapters.working_stack_gap_episodes(
        working_stack=working_stack_doc,
        events=events,
        generated_at="2026-07-08T00:05:00Z",
        schema_prefix=prefix,
        working_stack_latest_path=working_stack_path,
        events_latest_path=events_path,
        spatial_graph_latest_path=spatial_path,
        process_container_latest_path=process_path,
    )

    assert len(episodes) == 1
    episode = episodes[0]
    gap = episode["working_stack_gap"]
    assert episode_ids == [episode["episode_id"]]
    assert episode["schema"] == "abyss_machine_causal_episode_v1"
    assert episode["episode_kind"] == "working_stack_usage_gap"
    assert episode["event_ids"] == ["saevt-working-stack-browser"]
    assert episode["working_stack_link_id"] == link_id
    assert f"service:{service}" in episode["affected_spatial_nodes"]
    assert f"working_stack_link:{link_id}" in episode["affected_spatial_nodes"]
    assert gap["schema"] == "abyss_machine_self_awareness_working_stack_usage_gap_v1"
    assert gap["service"] == service
    assert gap["machine_usage_status"] == status
    assert gap["activation_kind"] == "stack_tool_runtime_smoke_gap"
    assert gap["failed_probe_names"] == ["playwright-chromium-launch"]
    assert gap["ok_probe_names"] == ["http-health"]
    assert gap["policy"]["host_layer_mutates_stack"] is False
    assert gap["policy"]["executes_commands"] is False
    assert episode["policy"]["host_layer_mutates_stack"] is False
    assert episode["policy"]["executes_commands"] is False
    evidence_paths = {ref["path"] for ref in episode["evidence_refs"] if isinstance(ref, dict)}
    assert str(working_stack_path) in evidence_paths
    assert str(events_path) in evidence_paths
    assert str(spatial_path) in evidence_paths
    assert str(process_path) in evidence_paths


def test_activation_synthetic_proof_and_export_overlay_are_adapter_owned(tmp_path: Path) -> None:
    prefix = "abyss_machine"
    service = "aoa-browser"
    status = "tool_runtime_degraded"
    link_id = "saworklink-aoa-browser"
    entry = {
        "service": service,
        "machine_usage_status": status,
        "working_stack_link_id": link_id,
        "usage_gap": "functional runtime smoke failed",
        "safe_next_action": {
            "requires_human_approval": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
        },
        "policy": {"host_layer_mutates_stack": False, "executes_commands": False},
        "synthetic_scenario": self_awareness_adapters.working_stack_activation_synthetic_scenario(
            {
                "service": service,
                "machine_usage_status": status,
                "activation_kind": "stack_tool_runtime_smoke_gap",
                "working_stack_link_id": link_id,
                "usage_gap": "functional runtime smoke failed",
                "missing_checks": [{"key": "working_stack_usage_gap"}],
                "verifier_commands": ["abyss-machine self-awareness working-stack --json"],
                "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/working-stack/latest.json"}],
            },
            "2026-07-08T00:00:00Z",
            schema_prefix=prefix,
        ),
    }
    working_stack_doc = {
        "organs": [
            {
                "service": service,
                "owner": "abyss-stack",
                "machine_usage_status": status,
                "usage_gap": "functional runtime smoke failed",
                "time_space_context_link": {"link_id": link_id},
            }
        ]
    }
    spatial_doc = {
        "nodes": [
            {"id": f"service:{service}", "owner_surface": "abyss-stack"},
            {"id": f"working_stack_link:{link_id}"},
            {"id": "usage_gap:fixture", "kind": "usage_gap", "label": service, "status": status},
        ],
        "edges": [
            {"from": f"service:{service}", "to": f"working_stack_link:{link_id}", "kind": "has_time_space_context_link"},
            {"from": f"service:{service}", "to": "usage_gap:fixture", "kind": "has_unexhausted_potential"},
        ],
    }
    episodes_doc = {
        "episodes": [
            {
                "episode_id": "saepisode-gap",
                "episode_kind": "working_stack_usage_gap",
                "working_stack_gap": {"service": service, "machine_usage_status": status},
                "affected_spatial_nodes": [f"service:{service}", f"working_stack_link:{link_id}"],
                "policy": {"host_layer_mutates_stack": False, "executes_commands": False},
            }
        ]
    }
    alerts_doc = {
        "candidates": [
            {
                "id": "sacandidate-gap",
                "automatic": False,
                "working_stack_gap_service": service,
                "working_stack_gap_status": status,
                "response_contract": {
                    "policy": {"host_layer_mutates_stack": False, "executes_commands": False},
                    "approval": {"human_approval_before_mutation": True},
                    "working_stack_gap": {"policy": {"host_layer_mutates_stack": False, "executes_commands": False}},
                    "investigation": {"thread_id": "sainv-gap", "summary": {"checkpoints": 3}},
                    "replay": {"thread_id": "sainv-gap", "ok": True},
                },
            }
        ]
    }
    export_entry = {
        "schema": "abyss_machine_self_awareness_working_stack_activation_entry_v1",
        "service": service,
        "complete": True,
        "working_stack_link_id": link_id,
        "policy": {"host_layer_mutates_stack": False, "executes_commands": False},
    }
    export_doc = {
        "schema": "abyss_machine_self_awareness_export_v1",
        "generated_at": "2026-07-08T00:00:00Z",
        "stack_handoff": {
            "working_stack_activation_service_ids": [service],
            "working_stack_activation_entries": [export_entry],
        },
    }
    cycle_doc = {
        "schema": "abyss_machine_self_awareness_cycle_v1",
        "cycle_id": "sacycle-gap",
        "summary": {"working_stack_activation_entries": 1, "automatic_responses": 0, "routes_with_mutating_command_if_run": 0},
    }
    investigation_doc = {
        "working_stack_gap": {"service": service, "machine_usage_status": status, "complete": True},
    }
    replay_doc = {
        "working_stack_gap_replay": {"service": service, "machine_usage_status": status, "replayable": True},
    }
    coverage_row = {
        "schema": "abyss_machine_self_awareness_working_stack_gap_coverage_row_v1",
        "id": "sacoverage-gap",
        "service": service,
        "machine_usage_status": status,
        "working_stack_link_id": link_id,
        "policy": {"host_layer_mutates_stack": False, "executes_commands": False, "automatic_remediation": False},
    }

    proof = self_awareness_adapters.working_stack_activation_synthetic_proof(
        entry,
        generated_at="2026-07-08T00:00:00Z",
        working_stack_doc=working_stack_doc,
        spatial_doc=spatial_doc,
        episodes_doc=episodes_doc,
        alerts_doc=alerts_doc,
        export_doc=export_doc,
        cycle_doc=cycle_doc,
        investigation_doc=investigation_doc,
        replay_doc=replay_doc,
        coverage_row=coverage_row,
        schema_prefix=prefix,
        working_stack_latest_path=tmp_path / "working-stack/latest.json",
        spatial_graph_latest_path=tmp_path / "spatial-graph/latest.json",
        episodes_latest_path=tmp_path / "episodes/latest.json",
        alerts_latest_path=tmp_path / "alerts/latest.json",
        investigate_latest_path=tmp_path / "investigate/latest.json",
        replay_latest_path=tmp_path / "replay/latest.json",
        coverage_audit_latest_path=tmp_path / "coverage-audit/latest.json",
        export_latest_path=tmp_path / "export/latest.json",
        cycle_latest_path=tmp_path / "cycle/latest.json",
        validate_latest_path=tmp_path / "validate/latest.json",
    )
    assert self_awareness_adapters.working_stack_activation_synthetic_proof_complete(
        proof,
        schema_prefix=prefix,
    ) is True
    assert proof["summary"]["failed_steps"] == []
    assert proof["policy"]["host_layer_mutates_stack"] is False

    proof_needing_overlay = json.loads(json.dumps(proof))
    export_step = next(step for step in proof_needing_overlay["proof_steps"] if step["step"] == "export")
    export_step["ok"] = False
    proof_needing_overlay["proof_status"] = "proof_incomplete"
    proof_needing_overlay["summary"]["ok_steps"] = len(proof_needing_overlay["proof_steps"]) - 1
    proof_needing_overlay["summary"]["failed_steps"] = ["export"]
    proof_needing_overlay["complete"] = False

    adjusted = self_awareness_adapters.export_overlay_working_stack_activation_proof(
        proof_needing_overlay,
        {service: export_entry},
        generated_at="2026-07-08T00:00:00Z",
        schema_prefix=prefix,
        export_latest_path=tmp_path / "export/latest.json",
    )

    assert adjusted["complete"] is True
    assert adjusted["proof_status"] == "proved_open_activation_gap"
    assert adjusted["summary"]["failed_steps"] == []
    adjusted_export_step = next(step for step in adjusted["proof_steps"] if step["step"] == "export")
    assert adjusted_export_step["details"]["export_handoff_overlay_applied"] is True


def test_cycle_result_document_builds_public_safe_final_snapshot(tmp_path: Path) -> None:
    steps = [
        {
            "id": "probe",
            "ok": True,
            "artifact": {"path": str(tmp_path / "probe" / "latest.json"), "ok": True},
        },
        {
            "id": "export",
            "ok": True,
            "artifact": {"path": str(tmp_path / "export" / "latest.json"), "ok": True},
        },
    ]
    cycle_chain = {"probe": True, "export": True}
    from_zero_proof = {"ok": True, "summary": {"proof_steps": 2, "chain_obligations": 2}}
    e2e_lineage_proof = {"ok": True, "summary": {"rows": 3, "missing_rows": []}}
    lineage = {"complete": True, "summary": {"artifacts": 2, "synthetic_event_ids": ["event-fixture"]}}
    bridge_proof = {"ok": True, "summary": {"bridges": 4}}
    activation_smoke = {"summary": {"rows": "5", "rows_ok": "5", "failed_services": [], "open_activation_gaps": "1"}}
    autolink = {
        "summary": {
            "organ_links": 3,
            "organ_links_complete": 3,
            "stack_requirement_links": 2,
            "working_stack_usage_gaps": "0",
            "synthetic_scenarios_complete": 2,
            "state_changed": False,
        }
    }
    stack_closure_dossier = {
        "summary": {
            "probes": 7,
            "missing_checks": 0,
            "dependency_edges": 3,
            "closure_acceptance_packets": 2,
            "closure_acceptance_packets_complete": 2,
            "stack_requirement_compat_requirements": 1,
        }
    }
    stack_handoff_closure_readiness = {"summary": {"packets": 2, "missing_checks": 0, "dependency_edges": 1}}
    replay = {
        "stack_handoff_replay": {"closure_readiness_replayable": True},
        "resident_cognitive_replay": {
            "complete": True,
            "summary": {
                "read_only_tools": 3,
                "hypothesis_tests": 2,
                "contradiction_notes": 0,
            },
        },
        "body_trace_replay": {"replayable": True},
    }
    responses = {
        "summary": {
            "self_awareness_body_trace_routes": 1,
            "self_awareness_body_trace_missing": 0,
            "self_awareness_entity_event_document_routes": 1,
            "self_awareness_entity_event_document_missing": 0,
        }
    }
    export = {
        "working_stack_link_integrity": {"summary": {"rows": 2, "complete_rows": 2, "missing_rows": 0}},
        "resident_cognitive_replay": {"complete": True},
        "body_trace_handoff": {"response_body_trace_included": True},
        "portable_contract": {"response_entity_event_document_context_included": True},
    }

    payload = self_awareness_adapters.cycle_result_document(
        schema_prefix="abyss_machine",
        version="0.test",
        generated_at="2026-07-07T00:00:00+00:00",
        cycle_id="sacycle-fixture",
        probe_run_id="saprobe-fixture",
        steps=steps,
        resource_preflight={"ok": True, "denial_reasons": []},
        cycle_chain=cycle_chain,
        bridge_proof=bridge_proof,
        activation_smoke=activation_smoke,
        autolink=autolink,
        stack_handoff_summary={"summary": {"routes": 1}},
        stack_handoff_closure_readiness=stack_handoff_closure_readiness,
        stack_closure_dossier=stack_closure_dossier,
        replay=replay,
        responses=responses,
        export=export,
        from_zero_proof=from_zero_proof,
        e2e_lineage_proof=e2e_lineage_proof,
        lineage=lineage,
        open_requirement_rows=[
            {
                "id": "REQ-1",
                "title": "fixture requirement",
                "owner": "abyss-stack",
                "detector": "fixture",
                "evidence_refs": [{"path": "/tmp/fixture"}],
                "private_payload": "not projected",
            }
        ],
        open_working_stack_activation_gaps=1,
        working_stack_activation_summary={
            "entries": "6",
            "missing_checks": "0",
            "verifier_commands": "2",
            "synthetic_scenarios": "2",
            "synthetic_scenarios_complete": "2",
            "closure_acceptance_packets": "1",
            "closure_acceptance_packets_complete": "1",
            "activation_compat_requirements": "1",
        },
        failed_steps=[],
        missing_chain=[],
        mutation_claims=[],
        automatic_response_count=0,
        mutating_response_routes=0,
    )

    assert payload["schema"] == "abyss_machine_self_awareness_cycle_v1"
    assert payload["ok"] is True
    assert payload["status"] == "covered"
    assert payload["summary"]["steps"] == 2
    assert payload["summary"]["chain_passed"] == 2
    assert payload["summary"]["chain_total"] == 2
    assert payload["summary"]["from_zero_proof_ok"] is True
    assert payload["summary"]["e2e_lineage_rows"] == 3
    assert payload["summary"]["bridge_proof_rows"] == 4
    assert payload["summary"]["working_stack_activation_entries"] == 6
    assert payload["summary"]["working_stack_usage_gaps"] == 0
    assert payload["summary"]["resident_cognitive_read_only_tools"] == 3
    assert payload["open_stack_requirements"] == [
        {
            "id": "REQ-1",
            "title": "fixture requirement",
            "owner": "abyss-stack",
            "detector": "fixture",
            "evidence_refs": [{"path": "/tmp/fixture"}],
        }
    ]
    assert payload["evidence_refs"] == [
        {"path": str(tmp_path / "probe" / "latest.json"), "step": "probe"},
        {"path": str(tmp_path / "export" / "latest.json"), "step": "export"},
    ]
    assert payload["issues"]["failed_steps"] == []
    assert payload["policy"]["host_layer_mutates_stack"] is False
    assert payload["policy"]["claims_require_evidence_refs"] is True
    assert payload["tests"]["validate_command"] == "abyss-machine self-awareness validate --json"


def test_probe_result_document_builds_complete_public_safe_shape(tmp_path: Path) -> None:
    chain = {
        "request": True,
        "movement_reaction_candidate": True,
        "movement_response": True,
        "export": True,
    }
    e2e_lineage_proof = {"ok": True, "summary": {"rows": 4, "missing_rows": []}}
    lineage = {"complete": True, "summary": {"artifacts": 3, "synthetic_event_ids": ["event-fixture"]}}
    paths = {
        "events": tmp_path / "events" / "latest.json",
        "episodes": tmp_path / "episodes" / "latest.json",
        "investigate": tmp_path / "investigate" / "latest.json",
        "replay": tmp_path / "replay" / "latest.json",
        "reactions": tmp_path / "reactions" / "latest.json",
        "responses": tmp_path / "responses" / "latest.json",
        "export": tmp_path / "export" / "latest.json",
    }

    payload = self_awareness_adapters.probe_result_document(
        schema_prefix="abyss_machine",
        version="0.test",
        generated_at="2026-07-07T00:00:00+00:00",
        run_id="saprobe-fixture",
        traceparent="00-" + "a" * 32 + "-" + "b" * 16 + "-01",
        target_url="http://127.0.0.1:3000/api/health",
        response={"ok": True, "status_code": 200},
        resource_preflight={"ok": True, "denial_reasons": []},
        chain=chain,
        e2e_lineage_proof=e2e_lineage_proof,
        lineage=lineage,
        synthetic_event_refs=[{"event_id": "event-fixture", "signal": "metric"}],
        artifacts={"events": str(paths["events"])},
        target_service="grafana",
        movement_packet_id="samove-fixture",
        movement_selection={"selected_reason": "fixture movement"},
        probe_movement_event={"event_id": "event-fixture"},
        probe_movement_episode={"episode_id": "episode-fixture"},
        investigation={"thread_id": "thread-investigate"},
        replay={"ok": True, "thread_id": "thread-replay", "resident_cognitive_replay": {"complete": True}},
        alerts={"summary": {"reaction_candidates": 1}},
        autolink={
            "summary": {
                "organ_links": 2,
                "organ_links_complete": 2,
                "stack_requirement_links": 1,
                "synthetic_scenarios_complete": 1,
            }
        },
        paths=paths,
    )

    assert payload["schema"] == "abyss_machine_self_awareness_probe_v1"
    assert payload["ok"] is True
    assert payload["target"] == {"url": "http://127.0.0.1:3000/api/health", "safe": True, "method": "GET", "mutates_stack": False}
    assert payload["movement_smoke"]["schema"] == "abyss_machine_self_awareness_probe_movement_smoke_v1"
    assert payload["movement_smoke"]["complete"] is True
    assert payload["movement_smoke"]["selected_reason"] == "fixture movement"
    assert payload["movement_smoke"]["policy"]["host_layer_mutates_stack"] is False
    assert payload["movement_smoke"]["evidence_refs"] == [
        {"path": str(paths["events"]), "event_id": "event-fixture"},
        {"path": str(paths["episodes"]), "episode_id": "episode-fixture"},
        {"path": str(paths["investigate"]), "thread_id": "thread-investigate"},
        {"path": str(paths["replay"]), "thread_id": "thread-replay"},
        {"path": str(paths["reactions"]), "episode_id": "episode-fixture"},
        {"path": str(paths["responses"]), "episode_id": "episode-fixture"},
        {"path": str(paths["export"]), "run_id": "saprobe-fixture"},
    ]
    assert payload["summary"]["status"] == "ok"
    assert payload["summary"]["chain_passed"] == 4
    assert payload["summary"]["chain_total"] == 4
    assert payload["summary"]["movement_smoke_complete"] is True
    assert payload["summary"]["e2e_lineage_rows"] == 4
    assert payload["summary"]["lineage_complete"] is True
    assert payload["summary"]["autolink_organ_links_complete"] == 2
    assert payload["summary"]["resource_guard_ok"] is True
    assert payload["policy"]["writes_project_roots"] is False


def test_stack_source_ref_and_service_normalization_are_public_safe(tmp_path: Path) -> None:
    ref = self_awareness_adapters.stack_owned_source_ref(
        tmp_path / "abyss-stack" / "Services" / "qwen-tts-api",
        "service_root",
        service="qwen-tts",
    )

    assert ref == {
        "path": str(tmp_path / "abyss-stack" / "Services" / "qwen-tts-api"),
        "kind": "service_root",
        "owner_surface": "abyss-stack",
        "read_only": True,
        "host_layer_mutates_stack": False,
        "service": "qwen-tts",
    }
    assert self_awareness_adapters.normalize_stack_service_name("/abyss_qwen_tts_api_1") == "qwen-tts"
    assert self_awareness_adapters.normalize_stack_service_name("langchain_api_llamacpp") == "langchain-api-llamacpp"


def test_working_stack_service_selection_policy_uses_fake_json_ports(tmp_path: Path) -> None:
    policy_path = tmp_path / "srv" / "Configs" / "docs" / "runtime" / "service-selection-policy.v1.json"
    policy_path.parent.mkdir(parents=True)
    policy_path.write_text(
        json.dumps(
            {
                "schema": "abyss_stack_service_selection_policy_v1",
                "updated_at": "2026-07-01T00:00:00Z",
                "services": [
                    {
                        "name": "qwen-tts-api",
                        "posture": "explicit_opt_in",
                        "tier": "tool",
                        "owner_profile": "stack",
                        "module": "tts",
                        "resource_guard": "heavy",
                        "decision": "defer",
                    },
                    {
                        "service": "llm_registry",
                        "posture": "always_on",
                        "tier": "control",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    calls: list[Path] = []

    def fake_loader(path: Path) -> tuple[Any, str | None]:
        calls.append(path)
        return json.loads(path.read_text(encoding="utf-8")), None

    payload = self_awareness_adapters.working_stack_service_selection_policy(
        schema_prefix="abyss_machine",
        stack_paths={"srv_abyss_stack": tmp_path / "srv", "source_abyss_stack": tmp_path / "source"},
        path_exists=lambda path: path.exists(),
        load_json_document=fake_loader,
    )

    assert payload["schema"] == "abyss_machine_self_awareness_working_stack_service_selection_policy_v1"
    assert payload["ok"] is True
    assert list(payload["services"]) == ["qwen-tts", "llm-registry"]
    assert payload["services"]["qwen-tts"]["policy_origin"] == "runtime_configs"
    assert payload["services"]["qwen-tts"]["source_ref"]["owner_surface"] == "abyss-stack"
    assert payload["summary"]["services"] == 2
    assert payload["summary"]["errors"] == 0
    assert calls == [policy_path]


def test_working_stack_service_selection_policy_reports_bad_json_without_live_io(tmp_path: Path) -> None:
    policy_path = tmp_path / "source" / "docs" / "runtime" / "service-selection-policy.v1.json"

    def fake_exists(path: Path) -> bool:
        return path == policy_path

    payload = self_awareness_adapters.working_stack_service_selection_policy(
        schema_prefix="abyss_machine",
        stack_paths={"source_abyss_stack": tmp_path / "source"},
        path_exists=fake_exists,
        load_json_document=lambda path: (None, "fixture_error") if path == policy_path else ({}, None),
    )

    assert payload["ok"] is False
    assert payload["summary"]["errors"] == 1
    assert payload["errors"] == [{"path": str(policy_path), "origin": "source_checkout", "error": "fixture_error"}]


def test_stack_compose_inventory_parses_declared_services_from_fake_roots(tmp_path: Path) -> None:
    source_modules = tmp_path / "source" / "compose" / "modules"
    runtime_modules = tmp_path / "srv" / "Configs" / "compose" / "modules"
    source_modules.mkdir(parents=True)
    runtime_modules.mkdir(parents=True)
    (source_modules / "10-core.yml").write_text(
        """
services:
  route_api:
    image: example
  x-template:
    image: ignored
  nested:
    environment:
      CHILD: value
""",
        encoding="utf-8",
    )
    (runtime_modules / "20-tools.yml").write_text(
        """
services:
  qwen_tts_api:
    image: example
  docs-api:
    image: example
""",
        encoding="utf-8",
    )

    payload = self_awareness_adapters.stack_compose_service_inventory(
        schema_prefix="abyss_machine",
        stack_paths={"source_abyss_stack": tmp_path / "source", "srv_abyss_stack": tmp_path / "srv"},
        path_exists=lambda path: path.exists(),
        path_is_dir=lambda path: path.is_dir(),
        path_glob=lambda root, pattern: root.glob(pattern),
        read_text=lambda path: path.read_text(encoding="utf-8"),
    )

    assert payload["ok"] is True
    assert payload["summary"] == {"module_roots": 2, "modules": 2, "declared_services": 4}
    assert [row["service"] for row in payload["services"]] == ["docs-api", "nested", "qwen-tts", "route-api"]
    route_row = next(row for row in payload["services"] if row["service"] == "route-api")
    assert route_row["modules"] == ["10-core.yml"]
    assert route_row["stack_source_refs"][0]["kind"] == "compose_module"


def test_stack_service_and_model_root_inventory_are_bounded_and_fakeable(tmp_path: Path) -> None:
    (tmp_path / "srv" / "Services" / "qwen-tts-api").mkdir(parents=True)
    (tmp_path / "source" / "Services" / "route_api").mkdir(parents=True)
    (tmp_path / "srv" / "Models" / "openvino" / "embeddings-int8").mkdir(parents=True)
    (tmp_path / "source" / "Models" / "voices" / "qwen-tts-voice").mkdir(parents=True)
    (tmp_path / "source" / "Models" / "llama" / "qwen3-8b-gguf").mkdir(parents=True)

    stack_paths = {"source_abyss_stack": tmp_path / "source", "srv_abyss_stack": tmp_path / "srv"}
    service_roots = self_awareness_adapters.stack_service_root_inventory(
        schema_prefix="abyss_machine",
        stack_paths=stack_paths,
        path_exists=lambda path: path.exists(),
        path_is_dir=lambda path: path.is_dir(),
        path_iterdir=lambda path: path.iterdir(),
    )
    models = self_awareness_adapters.stack_model_root_inventory(
        schema_prefix="abyss_machine",
        stack_paths=stack_paths,
        path_exists=lambda path: path.exists(),
        path_is_dir=lambda path: path.is_dir(),
        path_iterdir=lambda path: path.iterdir(),
        max_entries=4,
        max_depth=3,
    )

    assert [row["service"] for row in service_roots["services"]] == ["qwen-tts", "route-api"]
    assert service_roots["services"][0]["stack_source_refs"][0]["host_layer_mutates_stack"] is False
    assert models["summary"]["bounded"] is True
    assert models["summary"]["model_roots"] == 4
    assert models["summary"]["service_candidates"] == [
        "babelvox-tts",
        "embeddings",
        "llama-cpp",
        "llm-registry",
        "ovms",
        "qwen-tts",
        "tts",
        "tts-router",
    ]
    assert models["summary"]["tag_counts"]["openvino"] == 2
    assert models["summary"]["tag_counts"]["tts"] == 1


def test_working_stack_model_bridge_links_ai_capability_to_stack_model_root(tmp_path: Path) -> None:
    model_root = tmp_path / "abyss-stack" / "Models"
    embedding_path = model_root / "ovms" / "OpenVINO" / "Qwen3-Embedding"
    source_ref = self_awareness_adapters.stack_owned_source_ref(
        embedding_path,
        "model_root",
        tags=["embeddings", "openvino"],
    )
    ai_caps = {
        "schema": "abyss_machine_ai_capabilities_v1",
        "capabilities": {
            "embeddings": {
                "status": "ready",
                "primary_bridge": "abyss-machine ai eval --suite embeddings --json",
                "runtime": {"ready": False},
                "source_models": [
                    {
                        "path": str(embedding_path / "model.xml"),
                        "read_only_source": True,
                    }
                ],
            }
        },
    }

    bridge = self_awareness_adapters.working_stack_model_bridge(
        "embeddings",
        [{"stack_source_refs": [source_ref]}],
        ai_caps,
        schema_prefix="abyss_machine",
        ai_model_roots=[model_root],
        latest_paths={"ai_capabilities": tmp_path / "ai" / "capabilities" / "latest.json"},
    )

    assert bridge["schema"] == "abyss_machine_self_awareness_working_stack_model_bridge_v1"
    assert bridge["active"] is True
    assert bridge["runtime_ready"] is True
    assert bridge["model_root_count"] == 1
    assert bridge["stack_source_model_refs"][0]["kind"] == "ai_capability_source_model"
    assert bridge["stack_source_model_refs"][0]["read_only"] is True
    assert bridge["linked_stack_model_source_paths"] == [str(embedding_path / "model.xml")]
    assert bridge["evidence_refs"] == [
        {
            "path": str(tmp_path / "ai" / "capabilities" / "latest.json"),
            "schema": "abyss_machine_ai_capabilities_v1",
            "capability": "embeddings",
        }
    ]
    assert bridge["policy"]["host_layer_mutates_stack"] is False
    assert bridge["policy"]["model_promotion_decision"] is False


def test_working_stack_tool_status_classifies_deep_tool_probes_without_cli() -> None:
    probes = [
        {"service": "docs-api", "probe": "health", "ok": True},
        {"service": "docs-api", "probe": "search:n8n-workflow", "ok": True},
        {"service": "aoa-browser", "probe": "health", "ok": True},
        {"service": "aoa-browser", "probe": "private-host-guard", "ok": True},
        {"service": "aoa-browser", "probe": "playwright-chromium-launch", "ok": False},
        {"service": "qwen-tts", "probe": "tts-synthesis-artifact", "ok": True},
    ]

    assert self_awareness_adapters.working_stack_tool_status("docs-api", "endpoint_visible_unproven_deep_use", iter(probes)) == "active_machine_tool_signal"
    assert self_awareness_adapters.working_stack_tool_status("aoa-browser", "endpoint_visible_unproven_deep_use", probes) == "tool_runtime_degraded"
    assert self_awareness_adapters.working_stack_tool_status("qwen-tts", "declared_not_running", probes) == "recent_on_demand_tool_signal"


def test_working_stack_inventory_document_assembles_readmodel_without_cli(tmp_path: Path) -> None:
    stack_root = tmp_path / "abyss-stack"
    model_root = stack_root / "Models"
    embedding_path = model_root / "ovms" / "OpenVINO" / "Qwen3-Embedding"
    docs_module = stack_root / "compose" / "modules" / "20-tools.yml"
    service_root = stack_root / "Services" / "qwen-tts-api"
    latest_paths = {
        "process_container": tmp_path / "processes" / "containers" / "latest.json",
        "stack_observability": tmp_path / "stack-bridge" / "observability" / "latest.json",
        "working_stack": tmp_path / "self-awareness" / "working-stack" / "latest.json",
        "ai_capabilities": tmp_path / "ai" / "capabilities" / "latest.json",
    }
    pid_calls: list[int] = []
    tool_runtime_seen: dict[str, dict[str, Any]] = {}

    def fake_pid_alive(pid: int) -> bool:
        pid_calls.append(pid)
        return pid == 4242

    def fake_container_tool_probes(runtime_by_service: dict[str, dict[str, Any]], enabled: bool) -> list[dict[str, Any]]:
        tool_runtime_seen.update(runtime_by_service)
        assert enabled is True
        return [
            {"service": "docs-api", "probe": "health", "ok": True, "container": "docs-api"},
            {"service": "docs-api", "probe": "search:n8n-workflow", "ok": True, "container": "docs-api"},
        ]

    def fake_tts_smoke_probes(enabled: bool) -> list[dict[str, Any]]:
        assert enabled is True
        return [
            {
                "service": "qwen-tts",
                "probe": "tts-synthesis-artifact",
                "ok": True,
                "policy": {"raw_text_stored": False, "raw_audio_stored": False},
            }
        ]

    payload = self_awareness_adapters.working_stack_inventory_document(
        schema_prefix="abyss_machine",
        version="0.test",
        generated_at="2026-07-08T00:00:00+00:00",
        stack_paths={"srv_abyss_stack": str(stack_root), "host_layer_mutates_stack": False},
        stack_doc={"schema": "abyss_machine_stack_observability_v1"},
        container_health={
            "schema": "abyss_machine_process_container_health_v1",
            "containers": [
                {
                    "name": "docs-api",
                    "names": ["abyss_docs_api_1"],
                    "pid": 4242,
                    "running": True,
                    "state": "running",
                    "compose": {"project": "abyss", "service": "docs-api", "stack_managed": True},
                },
                {
                    "name": "unrelated",
                    "names": ["unrelated"],
                    "pid": 99,
                    "running": True,
                    "compose": {"project": "other"},
                },
            ],
        },
        compose_inventory={
            "ok": True,
            "services": [
                {
                    "service": "docs-api",
                    "declared": True,
                    "modules": ["20-tools.yml"],
                    "stack_source_refs": [self_awareness_adapters.stack_owned_source_ref(docs_module, "compose_module")],
                }
            ],
            "module_refs": [self_awareness_adapters.stack_owned_source_ref(docs_module, "compose_module")],
        },
        service_roots_inventory={
            "services": [
                {
                    "service": "qwen-tts",
                    "stack_source_refs": [self_awareness_adapters.stack_owned_source_ref(service_root, "service_root", service="qwen-tts")],
                }
            ],
            "summary": {"service_roots": 1},
        },
        model_inventory={
            "models": [
                {
                    "service_candidates": ["embeddings"],
                    "stack_source_refs": [
                        self_awareness_adapters.stack_owned_source_ref(
                            embedding_path,
                            "model_root",
                            tags=["embeddings", "openvino"],
                        )
                    ],
                }
            ],
            "summary": {"model_roots": 1},
        },
        selection_policy={"services": {}, "documents": []},
        ai_caps={
            "schema": "abyss_machine_ai_capabilities_v1",
            "capabilities": {
                "embeddings": {
                    "status": "ready",
                    "source_models": [{"path": str(embedding_path / "model.xml"), "read_only_source": True}],
                }
            },
        },
        initial_endpoint_probes=[],
        include_endpoint_probes=True,
        pid_alive=fake_pid_alive,
        container_tool_probes=fake_container_tool_probes,
        tts_smoke_probes=fake_tts_smoke_probes,
        ai_model_roots=[model_root],
        latest_paths=latest_paths,
        expected_live_services=("docs-api", "qwen-tts", "embeddings"),
    )

    organs = {row["service"]: row for row in payload["organs"]}
    assert payload["schema"] == "abyss_machine_self_awareness_working_stack_inventory_v1"
    assert payload["ok"] is True
    assert pid_calls == [4242]
    assert sorted(tool_runtime_seen) == ["docs-api"]
    assert organs["docs-api"]["runtime"]["pid_alive"] is True
    assert organs["docs-api"]["machine_usage_status"] == "active_machine_tool_signal"
    assert organs["docs-api"]["deep_usage_proven"] is True
    assert organs["qwen-tts"]["machine_usage_status"] == "recent_on_demand_tool_signal"
    assert organs["qwen-tts"]["usage_gap"] is None
    assert organs["embeddings"]["machine_usage_status"] == "active_model_root_bridge"
    assert organs["embeddings"]["model_bridge"]["active"] is True
    assert payload["summary"]["runtime_services"] == 1
    assert payload["summary"]["deep_usage_proven_services"] == ["docs-api", "embeddings", "qwen-tts"]
    assert payload["evidence_refs"] == [
        {"path": str(latest_paths["process_container"]), "schema": "abyss_machine_process_container_health_v1"},
        {"path": str(latest_paths["stack_observability"]), "schema": "abyss_machine_stack_observability_v1"},
        {"path": str(latest_paths["working_stack"]), "schema": "abyss_machine_self_awareness_working_stack_inventory_v1"},
    ]
    assert all(ref["host_layer_mutates_stack"] is False for row in organs.values() for ref in row["stack_source_refs"])


def test_working_stack_events_assemble_movement_observations_without_cli(tmp_path: Path) -> None:
    source_stack = tmp_path / "source-stack"
    srv_stack = tmp_path / "srv-stack"
    working_stack_latest = tmp_path / "self-awareness" / "working-stack" / "latest.json"
    qdrant_organ = {
        "service": "qdrant",
        "roles": ["vector_store"],
        "runtime": {
            "container": "qdrant",
            "pid": 4242,
            "pid_alive": True,
            "running": True,
            "state": "running",
            "health": "healthy",
            "restart_count": 0,
        },
        "declared": {"present": True},
        "endpoint_probes": [{"service": "qdrant", "probe": "collections", "ok": True, "status_code": 200}],
        "endpoint_ok": True,
        "model_roots": 0,
        "machine_usage_status": "active_dependency_signal",
        "deep_usage_proven": True,
        "usage_gap": None,
        "model_bridge": {},
        "time_space_context_link": {
            "link_id": "wsl-qdrant",
            "context": {"working_stack_link_id": "wsl-qdrant"},
        },
        "evidence_refs": [{"path": str(working_stack_latest), "schema": "abyss_machine_self_awareness_working_stack_inventory_v1"}],
        "stack_source_refs": [
            self_awareness_adapters.stack_owned_source_ref(source_stack / "compose" / "modules" / "30-memory.yml", "compose_module"),
        ],
    }
    browser_organ = {
        "service": "aoa-browser",
        "roles": ["browser_tool"],
        "runtime": {
            "container": "aoa-browser",
            "pid": 5252,
            "pid_alive": True,
            "running": True,
            "state": "running",
            "health": "starting",
            "restart_count": 1,
        },
        "declared": {"present": True},
        "endpoint_probes": [
            {"service": "aoa-browser", "probe": "health", "ok": True, "status_code": 200},
            {"service": "aoa-browser", "probe": "playwright-chromium-launch", "ok": False, "error": "launch failed"},
        ],
        "endpoint_ok": True,
        "model_roots": 0,
        "machine_usage_status": "tool_runtime_degraded",
        "deep_usage_proven": False,
        "usage_gap": "stack tool is reachable and guarded, but its functional runtime smoke failed",
        "model_bridge": {},
        "time_space_context_link": {
            "link_id": "wsl-aoa-browser",
            "context": {"working_stack_link_id": "wsl-aoa-browser"},
        },
        "evidence_refs": [{"path": str(working_stack_latest), "schema": "abyss_machine_self_awareness_working_stack_inventory_v1"}],
        "stack_source_refs": [
            self_awareness_adapters.stack_owned_source_ref(srv_stack / "Services" / "aoa-browser", "service_root"),
        ],
    }
    qdrant_digest = self_awareness_adapters.working_stack_organ_state_digest(qdrant_organ)

    events = self_awareness_adapters.working_stack_events(
        {"organs": [qdrant_organ, browser_organ]},
        "2026-07-08T12:00:00+00:00",
        schema_prefix="abyss_machine",
        previous_smoke={
            "by_service": {
                "qdrant": {
                    "stack_organ_use_packet": {
                        "current_state": {"current_state_digest": qdrant_digest},
                    }
                },
                "aoa-browser": {
                    "stack_organ_use_packet": {
                        "current_state": {"current_state_digest": "older-digest"},
                    }
                },
            }
        },
        working_stack_latest_path=working_stack_latest,
        host="fixture-host",
    )

    by_service = {event["resource"]["service"]: event for event in events}
    assert set(by_service) == {"aoa-browser", "qdrant"}
    assert by_service["qdrant"]["severity"] == "info"
    assert by_service["qdrant"]["context"]["state_changed"] is False
    assert by_service["qdrant"]["resource"]["movement_categories"] == [
        "raw_signal",
        "correlation_candidate",
        "ignore/noise",
    ]
    assert by_service["aoa-browser"]["severity"] == "warning"
    assert by_service["aoa-browser"]["context"]["state_changed"] is True
    assert by_service["aoa-browser"]["resource"]["selected_for_episode"] is True
    assert by_service["aoa-browser"]["resource"]["selected_for_resident_reasoning"] is True
    assert by_service["aoa-browser"]["resource"]["degradation_reasons"] == [
        "usage_gap",
        "failed_endpoint_probe",
        "degraded_status",
    ]
    assert by_service["aoa-browser"]["space"]["host"] == "fixture-host"
    assert by_service["aoa-browser"]["space"]["path"] == str(working_stack_latest)
    assert all(
        not str(ref.get("path", "")).startswith((str(source_stack), str(srv_stack)))
        for event in events
        for ref in event["evidence_refs"]
    )
    assert all(
        self_awareness_contracts.event_issues(event, schema_prefix="abyss_machine") == []
        for event in events
    )
    assert all(event["fabric"]["policy"]["host_layer_mutates_stack"] is False for event in events)


def test_parse_compose_services_returns_empty_on_read_error(tmp_path: Path) -> None:
    assert self_awareness_adapters.parse_compose_services(
        tmp_path / "missing.yml",
        read_text=lambda _path: (_ for _ in ()).throw(OSError("fixture")),
    ) == []


class _FakeStat:
    st_size = 1234
    st_mtime_ns = 1_700_000_000_000_000_000
    st_mtime = 1_700_000_000.0


def test_cycle_artifact_step_uses_fake_file_ports_and_extra_evidence(tmp_path: Path) -> None:
    artifact_path = tmp_path / "probe" / "latest.json"
    calls: list[tuple[str, Path]] = []

    def fake_exists(path: Path) -> bool:
        calls.append(("exists", path))
        return True

    def fake_stat(path: Path) -> _FakeStat:
        calls.append(("stat", path))
        return _FakeStat()

    def fake_sha256(path: Path) -> str:
        calls.append(("sha256", path))
        return "sha256:fixture"

    step = self_awareness_adapters.cycle_artifact_step(
        "probe",
        "abyss-machine self-awareness probe --json",
        artifact_path,
        {
            "schema": "abyss_machine_self_awareness_probe_v1",
            "generated_at": "2026-06-30T00:00:00+00:00",
            "ok": True,
            "status": "covered",
            "summary": {"chain_passed": 3},
        },
        path_exists=fake_exists,
        path_stat=fake_stat,
        path_sha256=fake_sha256,
        evidence_extra={"run_id": "saprobe-fixture"},
    )

    assert step["id"] == "probe"
    assert step["ok"] is True
    assert step["artifact"] == {
        "path": str(artifact_path),
        "schema": "abyss_machine_self_awareness_probe_v1",
        "generated_at": "2026-06-30T00:00:00+00:00",
        "status": "covered",
        "ok": True,
        "summary": {"chain_passed": 3},
        "exists": True,
        "size_bytes": 1234,
        "sha256": "sha256:fixture",
        "mtime_ns": 1_700_000_000_000_000_000,
        "mtime_iso": "2023-11-14T22:13:20+00:00",
        "run_id": "saprobe-fixture",
    }
    assert calls == [("exists", artifact_path), ("stat", artifact_path), ("sha256", artifact_path)]


def test_cycle_artifact_step_missing_file_skips_stat_and_hash(tmp_path: Path) -> None:
    artifact_path = tmp_path / "missing" / "latest.json"
    calls: list[str] = []

    step = self_awareness_adapters.cycle_artifact_step(
        "missing",
        "abyss-machine missing --json",
        artifact_path,
        {"schema": "abyss_machine_missing_v1", "ok": False, "error": "not found"},
        path_exists=lambda _path: False,
        path_stat=lambda _path: calls.append("stat"),
        path_sha256=lambda _path: calls.append("sha256") or "sha256:should-not-happen",
    )

    assert step["ok"] is False
    assert step["artifact"]["exists"] is False
    assert step["artifact"]["size_bytes"] is None
    assert step["artifact"]["sha256"] is None
    assert step["artifact"]["mtime_ns"] is None
    assert step["artifact"]["mtime_iso"] is None
    assert calls == []


def test_cycle_artifact_step_requires_ok_false_keeps_bridge_step_non_blocking(tmp_path: Path) -> None:
    step = self_awareness_adapters.cycle_artifact_step(
        "memory",
        "abyss-machine memory status --json",
        tmp_path / "memory" / "latest.json",
        {"schema": "abyss_machine_memory_status_v1", "ok": False, "summary": {"status": "degraded"}},
        path_exists=lambda _path: False,
        path_stat=lambda _path: _FakeStat(),
        path_sha256=lambda _path: "sha256:unused",
        requires_ok=False,
    )

    assert step["ok"] is True
    assert step["artifact"]["ok"] is False
    assert step["artifact"]["summary"] == {"status": "degraded"}


def test_cycle_artifact_step_specs_keep_cycle_order_and_bridge_policy() -> None:
    initial = self_awareness_adapters.CYCLE_INITIAL_ARTIFACT_STEP_SPECS
    final = self_awareness_adapters.CYCLE_FINAL_ARTIFACT_STEP_SPECS

    assert [spec.step_id for spec in initial[:6]] == [
        "probe",
        "capabilities",
        "requirements",
        "requirement_probes",
        "stack_closure_dossier",
        "trace_context",
    ]
    assert [spec.step_id for spec in initial[-5:]] == ["investigate", "replay", "brief", "reactions", "responses"]
    assert [spec.step_id for spec in final] == ["autolink", "export"]

    bridge_specs = [spec for spec in initial if spec.document_group == "bridge"]
    assert [spec.step_id for spec in bridge_specs] == [
        "heartbeats",
        "memory",
        "mode",
        "resource",
        "processes",
        "process_containers",
        "process_thermal_plan",
        "cooling",
        "typing_events",
        "typing_validate",
        "nervous_brief",
    ]
    assert all(spec.requires_ok is False for spec in bridge_specs)
    assert all(spec.requires_ok is True for spec in initial if spec.document_group != "bridge")


def test_cycle_artifact_steps_builds_grouped_manifest_without_live_io(tmp_path: Path) -> None:
    specs = (
        self_awareness_adapters.CycleArtifactStepSpec(
            "probe",
            "abyss-machine self-awareness probe --json",
            "probe",
            "direct",
            "probe",
        ),
        self_awareness_adapters.CycleArtifactStepSpec(
            "capabilities",
            "abyss-machine self-awareness capabilities --json",
            "capabilities",
            "latest",
            "capabilities",
        ),
        self_awareness_adapters.CycleArtifactStepSpec(
            "memory",
            "abyss-machine memory status --json",
            "memory",
            "bridge",
            "memory",
            requires_ok=False,
        ),
    )
    paths = {
        "probe": tmp_path / "probe" / "latest.json",
        "capabilities": tmp_path / "capabilities" / "latest.json",
        "memory": tmp_path / "memory" / "latest.json",
    }
    docs = {
        "direct": {
            "probe": {
                "schema": "abyss_machine_self_awareness_probe_v1",
                "ok": True,
                "summary": {"chain_passed": 3},
            }
        },
        "latest": {
            "capabilities": {
                "schema": "abyss_machine_self_awareness_capabilities_v1",
                "ok": False,
                "summary": {"missing": 1},
            }
        },
        "bridge": {
            "memory": {
                "schema": "abyss_machine_memory_status_v1",
                "ok": False,
                "summary": {"status": "degraded"},
            }
        },
    }
    calls: list[str] = []

    steps = self_awareness_adapters.cycle_artifact_steps(
        specs=specs,
        paths=paths,
        direct_documents=docs["direct"],
        latest_documents=docs["latest"],
        bridge_documents=docs["bridge"],
        path_exists=lambda path: calls.append(f"exists:{path.name}") or False,
        path_stat=lambda _path: calls.append("stat"),
        path_sha256=lambda _path: calls.append("sha256") or "sha256:unused",
        evidence_extra_by_step={"probe": {"run_id": "saprobe-fixture"}},
    )

    assert [step["id"] for step in steps] == ["probe", "capabilities", "memory"]
    assert [step["command"] for step in steps] == [
        "abyss-machine self-awareness probe --json",
        "abyss-machine self-awareness capabilities --json",
        "abyss-machine memory status --json",
    ]
    assert steps[0]["ok"] is True
    assert steps[0]["artifact"]["schema"] == "abyss_machine_self_awareness_probe_v1"
    assert steps[0]["artifact"]["run_id"] == "saprobe-fixture"
    assert steps[1]["ok"] is False
    assert steps[1]["artifact"]["summary"] == {"missing": 1}
    assert steps[2]["ok"] is True
    assert steps[2]["artifact"]["ok"] is False
    assert steps[2]["artifact"]["summary"] == {"status": "degraded"}
    assert calls == ["exists:latest.json", "exists:latest.json", "exists:latest.json"]

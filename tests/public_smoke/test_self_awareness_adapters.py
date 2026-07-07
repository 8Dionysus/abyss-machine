from __future__ import annotations

import json
import wave
from pathlib import Path
from typing import Any

from abyss_machine import self_awareness_adapters


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

from __future__ import annotations

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

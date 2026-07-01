from __future__ import annotations

import json
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

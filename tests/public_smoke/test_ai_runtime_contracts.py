from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine.ai_runtime_contracts import (
    ai_capabilities_document,
    ai_capabilities_latest_document,
    ai_paths_document,
    ai_policy_document,
    ai_report_document,
    ai_runtime_snapshot_document,
    ai_status_document,
    build_models_inventory_document,
    cache_dir_path,
    classify_model_dir,
    embedding_eval_command,
    embedding_eval_missing_model,
    embedding_eval_missing_python,
    embedding_eval_result,
    eval_document,
    eval_suite_execution_plan,
    eval_suite_declared_class,
    eval_suites_for_request,
    eval_unknown_suite_result,
    highest_workload_class,
    llm_paths_document,
    llm_profile_status,
    llm_registry_document,
    llm_runtime_status,
    llm_validate_contract_checks,
    llm_validate_document,
    model_cache_label,
    model_file_entry,
    openvino_benchmark_device_plan,
    openvino_benchmark_device_timeout,
    openvino_benchmark_document,
    openvino_benchmark_requested_devices,
    openvino_benchmark_skipped_device_result,
    openvino_smoke_command,
    openvino_smoke_missing_python,
    openvino_smoke_result,
    policy_denied_result,
    policy_gate_document,
    resource_numeric_delta,
    resource_profile_document,
    policy_workload_route_level,
    stt_eval_normalize_text,
    stt_eval_profile_result,
    stt_eval_result,
    stt_eval_text_similarity,
    subprocess_env,
    text_eval_command,
    text_eval_missing_model,
    text_eval_missing_python,
    text_eval_result,
    token_accounting_aoa_planning,
    token_accounting_aoa_select_records,
    token_accounting_aoa_summary_document,
    token_accounting_contract_document,
    token_accounting_count_command,
    token_accounting_count_document,
    token_accounting_count_env_overlay,
    token_accounting_count_error_result,
    token_accounting_count_execution_result,
    token_accounting_merge_summaries,
    token_accounting_parse_count,
    token_accounting_privacy_flags,
    token_accounting_profile_entry,
    token_accounting_profiles_document,
    token_accounting_sanitize_summary,
    token_accounting_library_candidates,
    token_accounting_tokenizer_candidates,
    token_accounting_tokenizer_resolution,
    workload_status_document,
    workload_stats_document,
    workload_taxonomy_document,
    workload_duration_band,
    workload_measurements_from_benchmark,
    workload_measurements_from_eval,
    workload_measurements_from_resident_audit,
    workload_measurements_from_tts_eval,
    workload_metric_stats,
    workload_numeric,
    workload_refresh_document,
    workload_refresh_probe_plan,
)


def _runtime_refs() -> dict[str, object]:
    keys = [
        "AI_ROOT",
        "AI_AGENTS_PATH",
        "AI_INDEX_PATH",
        "AI_CONFIG_PATH",
        "AI_DEVICES_LATEST_PATH",
        "AI_MODELS_LATEST_PATH",
        "AI_BENCHMARK_ROOT",
        "AI_BENCHMARK_LATEST_PATH",
        "AI_BENCHMARK_TODAY_PATH",
        "AI_BENCHMARK_DAILY_GLOB",
        "AI_EVAL_ROOT",
        "AI_EVAL_LATEST_PATH",
        "AI_EVAL_TODAY_PATH",
        "AI_EVAL_DAILY_GLOB",
        "AI_CAPABILITIES_LATEST_PATH",
        "AI_POLICY_LATEST_PATH",
        "AI_TOKEN_ACCOUNTING_ROOT",
        "AI_TOKEN_ACCOUNTING_LATEST_PATH",
        "AI_TOKEN_ACCOUNTING_PROFILES_LATEST_PATH",
        "AI_TOKEN_ACCOUNTING_COUNTS_LATEST_PATH",
        "AI_TOKEN_ACCOUNTING_COUNTS_DAILY_GLOB",
        "AI_TOKEN_ACCOUNTING_AOA_LATEST_PATH",
        "AI_TOKEN_ACCOUNTING_AOA_DAILY_GLOB",
        "AI_LLM_REGISTRY_LATEST_PATH",
        "AI_LLM_VALIDATE_LATEST_PATH",
        "AI_CPU_ROOT",
        "AI_CPU_TOPOLOGY_LATEST_PATH",
        "AI_CPU_THERMAL_MAP_LATEST_PATH",
        "AI_CPU_ROUTE_LATEST_PATH",
        "AI_CPU_TEST_LATEST_PATH",
        "AI_CPU_TEST_DAILY_GLOB",
        "COOLING_AGENTS_PATH",
        "COOLING_LATEST_PATH",
        "COOLING_ACTION_DAILY_GLOB",
        "COOLING_CONFIG_PATH",
        "STORAGE_LATEST_PATH",
        "STORAGE_INDEX_PATH",
        "STORAGE_POLICY_PATH",
        "STORAGE_POLICY_ENV_PATH",
        "AI_STORAGE_LATEST_PATH",
        "AI_STORAGE_CLEANUP_DAILY_GLOB",
        "HOOKS_ETC_DIR",
        "HOOKS_SRV_DIR",
        "PROCESS_ROOT",
        "PROCESS_AGENTS_PATH",
        "PROCESS_INDEX_PATH",
        "PROCESS_LATEST_PATH",
        "PROCESS_SNAPSHOT_DAILY_GLOB",
        "AI_RUNTIME_LATEST_PATH",
        "AI_RUNTIME_TODAY_PATH",
        "AI_RUNTIME_DAILY_GLOB",
        "AI_REPORT_LATEST_PATH",
        "AI_REPORT_TODAY_PATH",
        "AI_REPORT_DAILY_GLOB",
        "AI_WORKLOAD_ROOT",
        "AI_WORKLOAD_LATEST_PATH",
        "AI_WORKLOAD_TAXONOMY_PATH",
        "AI_WORKLOAD_STATS_LATEST_PATH",
        "AI_WORKLOAD_RUNS_TODAY_PATH",
        "AI_WORKLOAD_RUNS_DAILY_GLOB",
        "AI_WORKLOAD_REFRESH_TODAY_PATH",
        "AI_WORKLOAD_REFRESH_DAILY_GLOB",
        "AI_TTS_ROOT",
        "AI_TTS_LATEST_PATH",
        "AI_TTS_INVENTORY_LATEST_PATH",
        "AI_TTS_PROFILES_LATEST_PATH",
        "AI_TTS_EVAL_LATEST_PATH",
        "AI_TTS_EVAL_LATEST_SUCCESS_PATH",
        "AI_TTS_EVAL_LATEST_SUCCESS_BY_PROFILE_PATH",
        "AI_TTS_EVAL_SUCCESS_BY_PROFILE_ROOT",
        "AI_TTS_EVAL_TODAY_PATH",
        "AI_TTS_EVAL_DAILY_GLOB",
        "AI_TTS_COMPARE_LATEST_PATH",
        "AI_TTS_SERVER_LATEST_PATH",
        "AI_TTS_SYNTH_ROOT",
        "AI_TTS_SYNTH_TODAY_PATH",
        "AI_TTS_CACHE_ROOT",
        "AI_FIXTURE_ROOT",
        "AI_FIXTURE_STT_RU_SMOKE",
        "AI_CACHE_ROOT",
        "AI_OPENVINO_CACHE_ROOT",
        "MANIFEST_PATH",
    ]
    refs: dict[str, object] = {key: f"/fixture/{key.lower()}" for key in keys}
    refs["AI_LLM_PATHS"] = {"root": "/fixture/llm", "registry_latest": "/fixture/llm/latest.json"}
    refs["AI_WORKLOAD_LATEST_EXISTS"] = True
    refs["TOKEN_ACCOUNTING_CONTRACT"] = {"privacy": {"stores_counts_only": True}}
    refs["TOKEN_ACCOUNTING_SCHEMA_VERSION"] = 1
    return refs


def test_ai_cache_and_subprocess_env_contracts_are_portable() -> None:
    label = model_cache_label("/srv/abyss-machine/cache/ai/models/gemma/model.gguf", "llm")
    env = subprocess_env(
        {"OPENVINO_LOG_LEVEL": "5", "KEEP": "yes"},
        machine_cache_root=Path("/srv/abyss-machine/cache"),
        ai_cache_root=Path("/srv/abyss-machine/cache/ai"),
        tmp_root=Path("/srv/abyss-machine/tmp"),
        openvino_cache_root=Path("/srv/abyss-machine/cache/ai/openvino"),
        extra={"EXTRA": "1", "HF_HOME": "/custom/hf"},
    )

    assert cache_dir_path(Path("/srv/abyss-machine/cache/ai/openvino"), "bad label !") == Path("/srv/abyss-machine/cache/ai/openvino/bad-label")
    assert label.startswith("llm-model.gguf-")
    assert len(label.rsplit("-", 1)[-1]) == 16
    assert env["OPENVINO_LOG_LEVEL"] == "5"
    assert env["KEEP"] == "yes"
    assert env["HF_HOME"] == "/custom/hf"
    assert env["TRANSFORMERS_OFFLINE"] == "1"
    assert env["TMPDIR"] == "/srv/abyss-machine/tmp/ai"


def test_ai_resource_profile_envelope_is_module_owned_and_cli_delegates() -> None:
    from abyss_machine import cli

    before = {
        "captured_at": "2026-06-25T12:00:00+00:00",
        "memory": {"mem_available_mib": 1024.0},
        "thermal": {"temperature_c_max": 42.0},
        "battery": {"capacity_percent": 88},
        "rusage": {
            "self": {"user_cpu_sec": 1.0, "system_cpu_sec": 0.5},
            "children": {"user_cpu_sec": 0.2, "system_cpu_sec": 0.1, "maxrss_kib": 1000},
        },
    }
    after = {
        "captured_at": "2026-06-25T12:00:01+00:00",
        "memory": {"mem_available_mib": 1000.4},
        "thermal": {"temperature_c_max": 43.3},
        "battery": {"capacity_percent": 87},
        "rusage": {
            "self": {"user_cpu_sec": 1.25, "system_cpu_sec": 0.75},
            "children": {"user_cpu_sec": 0.7, "system_cpu_sec": 0.4, "maxrss_kib": 2500},
        },
    }
    expected = resource_profile_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        before=before,
        after=after,
        scope="child_process",
        basis="fixture subprocess",
    )

    assert resource_numeric_delta(True, 1) is None
    assert resource_numeric_delta(2.34567, 1.0, 3) == 1.346
    assert expected["schema"] == "abyss_machine_ai_resource_profile_v1"
    assert expected["facts_only"] is True
    assert expected["delta"] == {
        "mem_available_mib": -23.6,
        "temperature_c_max": 1.3,
        "battery_capacity_percent": -1.0,
        "children_user_cpu_sec": 0.5,
        "children_system_cpu_sec": 0.3,
        "children_maxrss_kib": 1500.0,
        "self_user_cpu_sec": 0.25,
        "self_system_cpu_sec": 0.25,
    }
    assert cli.numeric_delta(2.34567, 1.0, 3) == resource_numeric_delta(2.34567, 1.0, 3)
    assert cli.ai_resource_profile(before, after, "child_process", "fixture subprocess") == expected


def test_ai_model_inventory_classification_and_document_shape() -> None:
    root = Path("/srv/AbyssOS/abyss-stack/Models")
    openvino = classify_model_dir(
        root / "ovms" / "OpenVINO" / "Qwen3-Embedding",
        root,
        ["model.xml", "model.bin", "config.json"],
        {"immediate_files": 3},
    )
    hf = classify_model_dir(
        root / "hf" / "local" / "Gemma",
        root,
        ["config.json", "tokenizer.json", "model.safetensors"],
        {"immediate_files": 3},
    )
    gguf = model_file_entry(root / "llm" / "gemma.gguf", root, size_bytes=123)
    doc = build_models_inventory_document(
        entries=[gguf, openvino, hf],
        roots=[{"path": str(root), "exists": True, "entries_seen": 3}],
        errors=[],
        truncated=False,
        max_entries=10,
        max_depth=5,
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
    )

    assert openvino is not None and openvino["category"] == "ovms_openvino"
    assert hf is not None and hf["category"] == "huggingface_local"
    assert gguf is not None and gguf["category"] == "gguf"
    assert doc["schema"] == "abyss_machine_ai_models_v1"
    assert doc["policy"]["host_layer_mutates_stack"] is False
    assert doc["summary"]["by_category"] == {
        "gguf": 1,
        "huggingface_local": 1,
        "ovms_openvino": 1,
    }
    assert [item["category"] for item in doc["entries"]] == ["gguf", "huggingface_local", "ovms_openvino"]


def test_llm_profile_status_keeps_execution_hints_without_claiming_promotion() -> None:
    status = llm_profile_status(
        family_name="gemma4",
        profile_name="spark",
        profile={
            "role": "resident_small_brain",
            "model_id": "unsloth/gemma-4-E2B-it-GGUF",
            "revision": "fixture",
            "hf_file": "gemma.gguf",
            "mmproj_file": "mmproj.gguf",
            "declared_class": "medium",
            "warm_policy": "resident_candidate_after_latency_eval",
            "gpu_layers": 99,
            "context_size": 8192,
            "lazy_load": True,
        },
        runtime={
            "ok": True,
            "llama_cli": "/srv/abyss-machine/runtimes/llama.cpp/llama-cli",
            "llama_server": "/srv/abyss-machine/runtimes/llama.cpp/llama-server",
            "configured_version": "fixture",
            "version_stdout": "llama fixture",
        },
        local_path=Path("/srv/abyss-machine/cache/ai/gemma4/e2b/gemma.gguf"),
        local_exists=True,
        local_size_bytes=456,
        mmproj_path=Path("/srv/abyss-machine/cache/ai/gemma4/e2b/mmproj.gguf"),
        mmproj_exists=False,
        mmproj_size_bytes=None,
        storage_protection={"decision": "allow", "reason": "host cache"},
        under_host_cache=True,
    )

    assert status["status"] == "ready"
    assert status["mmproj"]["optional_for_text"] is True
    assert status["storage"]["under_host_cache"] is True
    assert status["policy"]["host_layer_mutates_stack"] is False
    assert status["policy"]["profile_is_candidate_until_measured"] is True
    assert status["lazy_load"] is True
    assert status["launch"]["cli_smoke"][:6] == [
        "/srv/abyss-machine/runtimes/llama.cpp/llama-cli",
        "-m",
        "/srv/abyss-machine/cache/ai/gemma4/e2b/gemma.gguf",
        "-ngl",
        "99",
        "-c",
    ]
    assert status["launch"]["hf_download"][-2:] == ["--local-dir", "/srv/abyss-machine/cache/ai/gemma4/e2b"]


def test_llm_runtime_status_document_is_module_owned() -> None:
    status = llm_runtime_status(
        {
            "name": "llama.cpp",
            "version": "fixture-version",
            "release_url": "https://example.invalid/llama",
            "backend": "vulkan+cpu",
            "root": "/srv/abyss-machine/runtimes/llama.cpp",
            "llama_cli": "/srv/abyss-machine/runtimes/llama.cpp/llama-cli",
            "llama_server": "/srv/abyss-machine/runtimes/llama.cpp/llama-server",
            "llama_bench": "/srv/abyss-machine/runtimes/llama.cpp/llama-bench",
            "source": "host-managed fixture",
        },
        cli_exists=True,
        server_exists=False,
        version_probe={
            "returncode": 0,
            "stdout": "llama build fixture\n",
            "stderr": "x" * 1200,
        },
    )

    assert status["ok"] is False
    assert status["configured_version"] == "fixture-version"
    assert status["llama_cli"].endswith("/llama-cli")
    assert status["llama_bench"].endswith("/llama-bench")
    assert status["version_stdout"] == "llama build fixture\n"
    assert status["version_returncode"] == 0
    assert len(status["version_stderr_tail"]) == 1000


def _llm_registry_config() -> dict[str, object]:
    return {
        "backend": "llama.cpp",
        "families": {
            "gemma4": {
                "status": "candidate",
                "provider": "google",
                "format_provider": "unsloth",
                "license": "apache-2.0",
                "upstream": {"e2b": "https://example.invalid/e2b"},
                "local_root": "/srv/abyss-machine/cache/ai/gemma4",
                "notes": ["host-managed candidate"],
                "profiles": {
                    "spark": {"role": "resident_small_brain"},
                    "workhorse": {"role": "on_demand_better_reasoning", "runtime": {"llama_cli": "/runtime/workhorse/llama-cli"}},
                },
            },
            "bad": "not-a-family",
        },
    }


def _llm_registry_profile_statuses() -> dict[str, dict[str, object]]:
    return {
        "gemma4.spark": {
            "profile": "spark",
            "family": "gemma4",
            "status": "ready",
            "local_exists": True,
            "local_path": "/srv/abyss-machine/cache/ai/gemma4/e2b/gemma.gguf",
            "runtime": {"ok": True, "llama_cli": "/runtime/default/llama-cli"},
            "storage": {"under_host_cache": True, "protection": {"decision": "allow"}},
        },
        "gemma4.workhorse": {
            "profile": "workhorse",
            "family": "gemma4",
            "status": "model-missing",
            "local_exists": False,
            "local_path": "/srv/abyss-machine/cache/ai/gemma4/e4b/gemma.gguf",
            "runtime": {"ok": True, "llama_cli": "/runtime/workhorse/llama-cli"},
            "storage": {"under_host_cache": True, "protection": {"decision": "allow"}},
        },
    }


def test_llm_registry_document_is_module_owned_read_model() -> None:
    runtime = {"ok": True, "llama_cli": "/runtime/default/llama-cli"}
    data = llm_registry_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        config=_llm_registry_config(),
        runtime=runtime,
        family_runtimes={"gemma4": runtime},
        profile_statuses=_llm_registry_profile_statuses(),
        registry_latest_path="/var/lib/abyss-machine/ai/llm/registry/latest.json",
        registry_daily_path="/var/lib/abyss-machine/ai/llm/registry/2026/06/2026-06-25.jsonl",
        validate_latest_path="/var/lib/abyss-machine/ai/llm/validate/latest.json",
    )

    assert data["schema"] == "abyss_machine_ai_llm_registry_v1"
    assert data["ok"] is True
    assert data["backend"] == "llama.cpp"
    assert sorted(data["profiles"]) == ["gemma4.spark", "gemma4.workhorse"]
    assert data["families"]["gemma4"]["provider"] == "google"
    assert data["families"]["gemma4"]["profiles"]["spark"]["status"] == "ready"
    assert data["summary"] == {
        "families": 1,
        "profiles": 2,
        "ready_profiles": 1,
        "missing_models": 1,
        "runtime_ok": True,
    }
    assert data["paths"]["daily"].endswith("2026-06-25.jsonl")
    assert data["bridge"]["no_stack_mutation"] is True
    assert data["non_claims"][0].startswith("Registry readiness means files")


def test_llm_registry_cli_delegates_document_shape_to_module(monkeypatch) -> None:
    from abyss_machine import cli

    config = _llm_registry_config()
    runtime = {"ok": True, "llama_cli": "/runtime/default/llama-cli"}
    profile_statuses = _llm_registry_profile_statuses()
    runtime_calls: list[str] = []

    def fake_runtime_status(config_arg, runtime_override=None):
        if isinstance(runtime_override, dict) and runtime_override.get("llama_cli"):
            runtime_calls.append(str(runtime_override["llama_cli"]))
            return {"ok": True, "llama_cli": runtime_override["llama_cli"]}
        runtime_calls.append("default")
        return runtime

    def fake_profile_status(family_name, profile_name, profile, profile_runtime):
        assert profile_runtime["ok"] is True
        return profile_statuses[f"{family_name}.{profile_name}"]

    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T12:00:00+00:00")
    monkeypatch.setattr(cli, "ai_llm_config", lambda: config)
    monkeypatch.setattr(cli, "ai_llm_runtime_status", fake_runtime_status)
    monkeypatch.setattr(cli, "ai_llm_profile_status", fake_profile_status)
    monkeypatch.setattr(cli, "ai_daily_jsonl_path", lambda root: Path("/var/lib/abyss-machine/ai/llm/registry/2026/06/2026-06-25.jsonl"))

    result = cli.ai_llm_registry(write_latest=False)
    expected = llm_registry_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-25T12:00:00+00:00",
        config=config,
        runtime=runtime,
        family_runtimes={"gemma4": runtime},
        profile_statuses=profile_statuses,
        registry_latest_path=cli.AI_LLM_REGISTRY_LATEST_PATH,
        registry_daily_path=Path("/var/lib/abyss-machine/ai/llm/registry/2026/06/2026-06-25.jsonl"),
        validate_latest_path=cli.AI_LLM_VALIDATE_LATEST_PATH,
    )

    assert runtime_calls == ["default", "/runtime/workhorse/llama-cli"]
    assert result == expected


def _llm_registry_document_fixture() -> dict[str, object]:
    runtime = {"ok": True, "llama_cli": "/runtime/default/llama-cli"}
    return llm_registry_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        config=_llm_registry_config(),
        runtime=runtime,
        family_runtimes={"gemma4": runtime},
        profile_statuses=_llm_registry_profile_statuses(),
        registry_latest_path="/var/lib/abyss-machine/ai/llm/registry/latest.json",
        registry_daily_path="/var/lib/abyss-machine/ai/llm/registry/2026/06/2026-06-25.jsonl",
        validate_latest_path="/var/lib/abyss-machine/ai/llm/validate/latest.json",
    )


def test_llm_validate_contract_checks_and_document_are_module_owned() -> None:
    registry = _llm_registry_document_fixture()
    token_profiles = {"summary": {"exact_ready_profiles": 1}}
    checks = llm_validate_contract_checks(
        registry=registry,
        token_profiles=token_profiles,
        config=_llm_registry_config(),
        protected_roots=["/srv/AbyssOS/abyss-stack", "/work"],
    )
    data = llm_validate_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        checks=[{"level": "ok", "key": "live:path", "message": "fixture"}] + checks,
        registry=registry,
        paths={"root": "/var/lib/abyss-machine/ai/llm"},
    )

    by_key = {item["key"]: item for item in checks}
    assert by_key["runtime"]["level"] == "ok"
    assert by_key["profiles_configured"]["details"] == {"profiles": ["gemma4.spark", "gemma4.workhorse"]}
    assert by_key["token_accounting_profiles"]["level"] == "ok"
    assert by_key["profile_models"]["level"] == "warn"
    assert by_key["profile_models"]["details"] == {"missing": ["gemma4.workhorse"]}
    assert by_key["storage_routes"]["level"] == "ok"
    assert by_key["protected_roots"]["level"] == "ok"
    assert data["schema"] == "abyss_machine_ai_llm_validate_v1"
    assert data["ok"] is True
    assert data["summary"] == {
        "fails": 0,
        "warnings": 1,
        "checks": 7,
        "profiles": 2,
        "ready_profiles": 1,
    }
    assert data["policy"]["fail_only_for_broken_runtime_or_protected_routes"] is True


def test_llm_validate_contract_checks_catch_protected_roots() -> None:
    config = _llm_registry_config()
    config["families"]["gemma4"]["profiles"]["spark"]["local_path"] = "/srv/AbyssOS/abyss-stack/Models/gemma.gguf"
    checks = llm_validate_contract_checks(
        registry=_llm_registry_document_fixture(),
        token_profiles={"summary": {"exact_ready_profiles": 1}},
        config=config,
        protected_roots=["/srv/AbyssOS/abyss-stack", "/work"],
    )

    protected = next(item for item in checks if item["key"] == "protected_roots")
    assert protected["level"] == "fail"
    assert protected["details"]["bad_paths"] == [
        {"family": "gemma4", "profile": "spark", "path": "/srv/AbyssOS/abyss-stack/Models/gemma.gguf"}
    ]


def test_llm_validate_cli_delegates_contract_checks_and_document(monkeypatch) -> None:
    from abyss_machine import cli

    registry = _llm_registry_document_fixture()
    token_profiles = {"summary": {"exact_ready_profiles": 1}}
    paths = {"schema": "abyss_machine_ai_llm_paths_v1", "root": "/var/lib/abyss-machine/ai/llm"}

    def fake_path_check(checks, key, path, kind="any", required=True):
        checks.append({"level": "ok", "key": key, "message": "path ok", "details": {"path": str(path), "kind": kind}})

    def fake_json_check(checks, key, path, expected_schema=None, required=True):
        checks.append({"level": "ok", "key": key, "message": "json ok", "details": {"path": str(path), "schema": expected_schema}})
        return {"schema": expected_schema}

    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T12:00:00+00:00")
    monkeypatch.setattr(cli, "ai_llm_config", _llm_registry_config)
    monkeypatch.setattr(cli, "ai_llm_registry", lambda write_latest=True: registry)
    monkeypatch.setattr(cli, "ai_token_accounting_profiles", lambda write_latest=True, registry=None: token_profiles)
    monkeypatch.setattr(cli, "ai_llm_paths", lambda: paths)
    monkeypatch.setattr(cli, "validation_add_path_exists", fake_path_check)
    monkeypatch.setattr(cli, "validation_json_file", fake_json_check)

    live_checks: list[dict[str, object]] = []
    fake_path_check(live_checks, "dir:llm_root", cli.AI_LLM_ROOT, "dir", True)
    fake_path_check(live_checks, "doc:llm_agents", cli.AI_LLM_ROOT / "AGENTS.md", "file", True)
    fake_path_check(live_checks, "tool:workhorse_harness", cli.AI_LLM_WORKHORSE_CONTROLLER, "file", True)
    fake_json_check(live_checks, "json:ai_config", cli.AI_CONFIG_PATH, f"{cli.SCHEMA_PREFIX}_ai_config_v1", True)
    expected = llm_validate_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-25T12:00:00+00:00",
        checks=live_checks
        + llm_validate_contract_checks(
            registry=registry,
            token_profiles=token_profiles,
            config=_llm_registry_config(),
            protected_roots=[*cli.ABYSS_STACK_READONLY_ROOTS, "/work"],
        ),
        registry=registry,
        paths=paths,
    )

    assert cli.ai_llm_validate(write_latest=False) == expected


def test_openvino_probe_command_result_and_benchmark_shape_are_module_owned() -> None:
    command = openvino_smoke_command("/usr/bin/abyss-openvino-python", "NPU")
    benchmark_config = {"default_devices": ["cpu", "npu"], "per_device_timeout_sec": 11, "npu_timeout_sec": 44}
    requested = openvino_benchmark_requested_devices(None, benchmark_config)
    explicit = openvino_benchmark_requested_devices(["gpu"], benchmark_config)
    plan = openvino_benchmark_device_plan(
        requested_devices=requested,
        available_devices=["CPU"],
        benchmark_config=benchmark_config,
    )
    success = openvino_smoke_result(
        "NPU",
        {
            "ok": True,
            "returncode": 0,
            "stdout": 'noise\n{"device":"NPU","ok":true,"compile_sec":0.1,"runs":5}\n',
            "stderr": "diagnostic",
        },
        {"scope": "child_process"},
    )
    failure = openvino_smoke_result(
        "GPU",
        {"ok": False, "returncode": 1, "stdout": "", "stderr": "compile failed"},
        {"scope": "child_process"},
    )
    benchmark = openvino_benchmark_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        gate={"ok": True},
        requested_devices=["CPU", "GPU"],
        available_devices=["CPU"],
        runtime={"ok": True, "openvino_version": "fixture", "python": "/usr/bin/abyss-openvino-python"},
        results=[
            {"device": "CPU", "ok": True},
            {"device": "GPU", "ok": False, "skipped": True, "reason": "device not available"},
        ],
        resource_profile={"scope": "child_process"},
    )

    assert command[:2] == ["/usr/bin/abyss-openvino-python", "-c"]
    assert "abyss_ai_smoke" in command[2]
    assert command[-1] == "NPU"
    assert openvino_smoke_missing_python("CPU") == {"device": "CPU", "ok": False, "error": "abyss-openvino-python not found"}
    assert requested == ["cpu", "npu"]
    assert explicit == ["gpu"]
    assert openvino_benchmark_device_timeout("NPU", benchmark_config) == 44.0
    assert openvino_benchmark_device_timeout("GPU", benchmark_config) == 11.0
    assert openvino_benchmark_skipped_device_result("gpu") == {
        "device": "GPU",
        "ok": False,
        "skipped": True,
        "reason": "device not available",
    }
    assert plan == [
        {"device": "CPU", "available": True, "timeout_sec": 11.0, "skip_result": None},
        {
            "device": "NPU",
            "available": False,
            "timeout_sec": None,
            "skip_result": {"device": "NPU", "ok": False, "skipped": True, "reason": "device not available"},
        },
    ]
    assert success["ok"] is True
    assert success["stderr"] == "diagnostic"
    assert success["resource_profile"]["scope"] == "child_process"
    assert failure["error"] == "compile failed"
    assert benchmark["schema"] == "abyss_machine_ai_benchmark_v1"
    assert benchmark["summary"] == {
        "devices_tested": 1,
        "devices_ok": 1,
        "devices_failed": 0,
        "devices_skipped": 1,
    }
    assert benchmark["policy_gate"]["ok"] is True


def test_openvino_benchmark_cli_delegates_device_plan_and_document(monkeypatch) -> None:
    from abyss_machine import cli

    before = {
        "memory": {"mem_available_mib": 1024.0},
        "thermal": {"temperature_c_max": 40.0},
        "battery": {"capacity_percent": 80},
        "rusage": {"self": {}, "children": {}},
    }
    after = {
        "memory": {"mem_available_mib": 1020.0},
        "thermal": {"temperature_c_max": 40.2},
        "battery": {"capacity_percent": 80},
        "rusage": {"self": {}, "children": {}},
    }
    snapshots = iter([before, after])
    calls: list[tuple[str, float]] = []
    benchmark_config = {"default_devices": ["cpu", "npu"], "per_device_timeout_sec": 11, "npu_timeout_sec": 44}
    runtime = {
        "ok": True,
        "openvino_version": "fixture",
        "python": "/usr/bin/abyss-openvino-python",
        "available_devices": ["CPU"],
    }
    gate = {"ok": True, "declared_class": "probe"}

    def fake_smoke(device: str, timeout_sec: float) -> dict[str, object]:
        calls.append((device, timeout_sec))
        return {"device": device, "ok": True, "elapsed_sec": 0.5}

    monkeypatch.setattr(cli, "ai_resource_snapshot", lambda: next(snapshots))
    monkeypatch.setattr(cli, "ai_config", lambda: {"benchmark": benchmark_config})
    monkeypatch.setattr(cli, "ai_policy_gate_for_class", lambda declared_class, operation, force=False: gate)
    monkeypatch.setattr(cli, "openvino_runtime_info", lambda: runtime)
    monkeypatch.setattr(cli, "ai_openvino_smoke_device", fake_smoke)
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T12:00:00+00:00")

    expected_results = [
        {"device": "CPU", "ok": True, "elapsed_sec": 0.5},
        {"device": "NPU", "ok": False, "skipped": True, "reason": "device not available"},
    ]
    expected = openvino_benchmark_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-25T12:00:00+00:00",
        gate=gate,
        requested_devices=["cpu", "npu"],
        available_devices=["CPU"],
        runtime=runtime,
        results=expected_results,
        resource_profile=cli.ai_resource_profile(before, after, "child_process", "whole quick benchmark command"),
    )

    assert cli.ai_benchmark_quick(write_latest=False) == expected
    assert calls == [("CPU", 11.0)]


def test_openvino_eval_commands_and_result_envelopes_are_module_owned() -> None:
    embedding_command = embedding_eval_command(
        "/usr/bin/abyss-openvino-python",
        Path("/srv/AbyssOS/abyss-stack/Models/embedding"),
        "AUTO:GPU,CPU",
        Path("/srv/abyss-machine/cache/ai/openvino/embedding"),
    )
    embedding_result = embedding_eval_result(
        {
            "ok": True,
            "returncode": 0,
            "stdout": '{"ok":true,"duplicate_cosine":0.99,"shape":[3,768]}\n',
            "stderr": "embedding stderr",
        },
        {"basis": "embedding eval subprocess"},
    )
    text_command = text_eval_command(
        "/usr/bin/abyss-openvino-python",
        Path("/srv/AbyssOS/abyss-stack/Models/text"),
        "CPU",
        Path("/srv/abyss-machine/cache/ai/openvino/text"),
        "Answer with one token",
    )
    text_result = text_eval_result(
        {
            "ok": True,
            "returncode": 0,
            "stdout": '{"ok":true,"text":"4"}\n',
            "stderr": "text stderr",
        },
        {"basis": "text eval subprocess"},
    )
    invalid_embedding = embedding_eval_result(
        {"ok": False, "returncode": 1, "stdout": "not json", "stderr": "bad"},
        {"basis": "embedding eval subprocess"},
    )

    assert embedding_command[:2] == ["/usr/bin/abyss-openvino-python", "-c"]
    assert "OVModelForFeatureExtraction" in embedding_command[2]
    assert embedding_command[-3:] == [
        "/srv/AbyssOS/abyss-stack/Models/embedding",
        "AUTO:GPU,CPU",
        "/srv/abyss-machine/cache/ai/openvino/embedding",
    ]
    assert embedding_eval_missing_model(Path("/missing"))["error"] == "model directory missing"
    assert embedding_eval_missing_python()["error"] == "abyss-openvino-python not found"
    assert embedding_result["suite"] == "embeddings"
    assert embedding_result["ok"] is True
    assert invalid_embedding["ok"] is False
    assert invalid_embedding["error"] == "embedding eval returned invalid JSON"

    assert text_command[:2] == ["/usr/bin/abyss-openvino-python", "-c"]
    assert "openvino_genai" in text_command[2]
    assert text_command[-4:] == [
        "/srv/AbyssOS/abyss-stack/Models/text",
        "CPU",
        "/srv/abyss-machine/cache/ai/openvino/text",
        "Answer with one token",
    ]
    assert text_eval_missing_model(Path("/missing"))["error"] == "model directory missing"
    assert text_eval_missing_python()["error"] == "abyss-openvino-python not found"
    assert text_result["suite"] == "text"
    assert text_result["ok"] is True
    assert text_result["non_claims"][0].startswith("This is a bounded executable-path smoke")


def test_stt_eval_text_scoring_and_result_envelopes_are_module_owned() -> None:
    reference = "Локальный искусственный интеллект готов к работе!"
    transcript = {
        "ok": True,
        "text": "локальный искусственный интеллект готов к работе",
        "raw_text": "локальный искусственный интеллект готов к работе",
        "elapsed_sec": 1.25,
        "via": "fixture",
        "profile_selection": {"profile": "fast"},
    }
    resource_profile = {"scope": "client_wall_and_system_context"}
    profile = stt_eval_profile_result(
        profile="fast",
        reference_text=reference,
        transcript=transcript,
        elapsed_sec=1.5,
        similarity_warn_below=0.9,
        resource_profile=resource_profile,
    )
    doc = stt_eval_result(
        reference_text=reference,
        fixture={"ok": True, "path": "/fixture/ru-smoke.wav"},
        profiles=[profile],
    )
    missing = stt_eval_result(
        reference_text=reference,
        fixture={"ok": False, "path": "/fixture/ru-smoke.wav", "error": "espeak-ng not found"},
        profiles=[],
    )

    assert stt_eval_normalize_text("Ёж, TEST!") == "еж test"
    assert stt_eval_text_similarity("", "") == 1.0
    assert stt_eval_text_similarity(reference, "") == 0.0
    assert profile["ok"] is True
    assert profile["similarity"] == 1.0
    assert profile["quality_warning"] is False
    assert profile["resource_profile"] == resource_profile
    assert doc["suite"] == "stt"
    assert doc["ok"] is True
    assert doc["profiles"] == [profile]
    assert doc["non_claims"][0].startswith("Synthetic TTS audio")
    assert missing["ok"] is False
    assert missing["error"] == "espeak-ng not found"


def test_stt_eval_cli_delegates_scoring_and_result_envelopes(monkeypatch) -> None:
    from abyss_machine import cli

    reference = "локальный искусственный интеллект готов к работе"
    fixture = {"ok": True, "path": "/fixture/ru-smoke.wav", "duration_sec": 2.0, "sample_rate": 16000}
    transcript = {
        "ok": True,
        "text": reference,
        "raw_text": reference,
        "client_elapsed_sec": 0.75,
        "via": "fixture",
        "profile_selection": {"profile": "fast"},
    }
    before = {
        "memory": {"mem_available_mib": 1024.0},
        "thermal": {"temperature_c_max": 40.0},
        "battery": {"capacity_percent": 90},
        "rusage": {"self": {}, "children": {}},
    }
    after = {
        "memory": {"mem_available_mib": 1020.0},
        "thermal": {"temperature_c_max": 40.5},
        "battery": {"capacity_percent": 90},
        "rusage": {"self": {}, "children": {}},
    }
    snapshots = iter([before, after])
    ticks = iter([10.0, 10.25])

    monkeypatch.setattr(
        cli,
        "ai_config",
        lambda: {"eval": {"stt_reference_text": reference, "stt_profiles": ["fast"], "stt_similarity_warn_below": 0.9}},
    )
    monkeypatch.setattr(cli, "ensure_stt_fixture", lambda text: fixture)
    monkeypatch.setattr(cli, "dictation_transcribe", lambda path, profile: transcript)
    monkeypatch.setattr(cli, "ai_resource_snapshot", lambda: next(snapshots))
    monkeypatch.setattr(cli.time, "monotonic", lambda: next(ticks))

    expected_profile = stt_eval_profile_result(
        profile="fast",
        reference_text=reference,
        transcript=transcript,
        elapsed_sec=0.25,
        similarity_warn_below=0.9,
        resource_profile=cli.ai_resource_profile(
            before,
            after,
            "client_wall_and_system_context",
            "dictation client call around warm server; server CPU/RAM is not directly attributed",
        ),
    )
    expected = stt_eval_result(reference_text=reference, fixture=fixture, profiles=[expected_profile])

    assert cli.normalize_eval_text("Ёж, TEST!") == stt_eval_normalize_text("Ёж, TEST!")
    assert cli.text_similarity(reference, reference) == stt_eval_text_similarity(reference, reference)
    assert cli.ai_eval_stt() == expected


def test_eval_suite_policy_and_result_envelopes_are_module_owned() -> None:
    suites = eval_suites_for_request("quick", {"quick_suites": ["embeddings", "text"]})
    declared = highest_workload_class([eval_suite_declared_class(item) for item in suites])
    plan = eval_suite_execution_plan(["stt", "mystery", "text"])
    policy = {
        "ok": True,
        "class": "warm",
        "can_run_heavy": False,
        "can_run_routed_heavy": True,
        "heavy_policy": "routed",
        "reasons": ["thermal"],
    }
    gate = policy_gate_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        declared_class=declared,
        operation="ai eval --suite quick",
        policy=policy,
    )
    denied = policy_denied_result(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        command="ai eval",
        requested_suite="quick",
        suites=suites,
        gate=gate,
    )
    doc = eval_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        requested_suite="quick",
        declared_class=declared,
        policy_gate={**gate, "ok": True},
        results=[
            {"suite": "embeddings", "ok": True},
            {"suite": "text", "ok": False, "error": "fixture"},
        ],
        resource_profile={"scope": "mixed_eval_command"},
        openvino_cache_root=Path("/srv/abyss-machine/cache/ai/openvino"),
    )

    assert suites == ["embeddings", "text"]
    assert declared == "heavy"
    assert eval_suite_declared_class("unknown") == "sustained"
    assert eval_unknown_suite_result("mystery") == {"suite": "mystery", "ok": False, "error": "unknown eval suite"}
    assert plan == [
        {"suite": "stt", "known": True},
        {"suite": "mystery", "known": False, "result": {"suite": "mystery", "ok": False, "error": "unknown eval suite"}},
        {"suite": "text", "known": True},
    ]
    assert highest_workload_class([]) == "probe"
    assert policy_workload_route_level(policy) == (2, "routed_heavy_requires_cpu_route")
    assert gate["schema"] == "abyss_machine_ai_policy_gate_v1"
    assert gate["ok"] is False
    assert gate["allowed"] is False
    assert gate["required_level"] == 3
    assert gate["current_max_recommended_level"] == 2
    assert gate["force_hint"] == "rerun with --force to override host policy explicitly"
    assert denied["schema"] == "abyss_machine_ai_policy_denied_v1"
    assert denied["policy_denied"] is True
    assert denied["force_hint"] == "rerun with --force to override host policy explicitly"
    assert denied["non_claims"][0] == "Denied commands do not update latest eval results."

    assert doc["schema"] == "abyss_machine_ai_eval_v1"
    assert doc["ok"] is False
    assert doc["summary"] == {"suites": 2, "suites_ok": 1, "suites_failed": 1}
    assert doc["policy"]["host_layer_mutates_stack"] is False
    assert doc["policy"]["openvino_cache_root"] == "/srv/abyss-machine/cache/ai/openvino"


def test_ai_policy_gate_cli_delegates_to_module(monkeypatch) -> None:
    from abyss_machine import cli

    policy = {
        "ok": True,
        "class": "warm",
        "can_run_heavy": False,
        "can_run_routed_heavy": True,
        "heavy_policy": "routed",
        "reasons": ["thermal"],
    }
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T12:00:00+00:00")
    monkeypatch.setattr(cli, "ai_policy", lambda write_latest=True: policy)

    result = cli.ai_policy_gate_for_class("heavy", "fixture op", force=True)
    expected = policy_gate_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-25T12:00:00+00:00",
        declared_class="heavy",
        operation="fixture op",
        policy=policy,
        force=True,
        class_levels=cli.AI_WORKLOAD_CLASS_LEVELS,
    )

    assert result == expected
    assert result["ok"] is True
    assert result["forced"] is True


def test_ai_eval_quick_uses_module_execution_plan_and_preserves_result_order(monkeypatch) -> None:
    from abyss_machine import cli

    snapshots = iter([
        {
            "memory": {"mem_available_mib": 2048.0},
            "thermal": {"temperature_c_max": 41.0},
            "battery": {"capacity_percent": 70},
            "rusage": {"self": {}, "children": {}},
        },
        {
            "memory": {"mem_available_mib": 2040.0},
            "thermal": {"temperature_c_max": 41.5},
            "battery": {"capacity_percent": 69},
            "rusage": {"self": {}, "children": {}},
        },
    ])
    gate = {
        "schema": "abyss_machine_ai_policy_gate_v1",
        "ok": True,
        "declared_class": "sustained",
        "required_level": 4,
    }

    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T12:00:00+00:00")
    monkeypatch.setattr(cli, "ai_config", lambda: {"eval": {"quick_suites": ["stt", "mystery", "text"]}})
    monkeypatch.setattr(cli, "ai_resource_snapshot", lambda: next(snapshots))
    monkeypatch.setattr(cli, "ai_policy_gate_for_class", lambda declared_class, operation, force=False: gate)
    monkeypatch.setattr(cli, "ai_eval_stt", lambda: {"suite": "stt", "ok": True})
    monkeypatch.setattr(cli, "ai_eval_embeddings", lambda: {"suite": "embeddings", "ok": True})
    monkeypatch.setattr(cli, "ai_eval_text", lambda: {"suite": "text", "ok": True})

    result = cli.ai_eval_quick(suite="quick", write_latest=False, force=False)
    expected = eval_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-25T12:00:00+00:00",
        requested_suite="quick",
        declared_class="sustained",
        policy_gate=gate,
        results=[
            {"suite": "stt", "ok": True},
            {"suite": "mystery", "ok": False, "error": "unknown eval suite"},
            {"suite": "text", "ok": True},
        ],
        resource_profile=cli.ai_resource_profile(
            {
                "memory": {"mem_available_mib": 2048.0},
                "thermal": {"temperature_c_max": 41.0},
                "battery": {"capacity_percent": 70},
                "rusage": {"self": {}, "children": {}},
            },
            {
                "memory": {"mem_available_mib": 2040.0},
                "thermal": {"temperature_c_max": 41.5},
                "battery": {"capacity_percent": 69},
                "rusage": {"self": {}, "children": {}},
            },
            "mixed_eval_command",
            "whole eval command",
        ),
        openvino_cache_root=cli.AI_OPENVINO_CACHE_ROOT,
    )

    assert result == expected


def _workload_status_inputs() -> dict[str, object]:
    return {
        "taxonomy": {
            "classes": [
                {"class": "probe", "level": 0},
                {"class": "medium", "level": 2},
                {"class": "heavy", "level": 3},
            ],
            "workloads": {
                "embedding_eval": {"class": "medium", "command": "abyss-machine ai eval --suite embeddings --json"},
                "text_eval": {"class": "heavy", "command": "abyss-machine ai eval --suite text --json"},
            },
        },
        "refresh": {"ok": True, "records_appended": 1},
        "stats": {
            "ok": True,
            "summary": {"records": 3, "groups": 2},
            "groups": [
                {"workload_id": "embedding_eval", "declared_class": "medium", "count": 2},
                {"workload_id": "text_eval", "declared_class": "heavy", "count": 1},
            ],
        },
        "policy": {
            "ok": True,
            "class": "warm",
            "can_run_heavy": False,
            "can_run_routed_heavy": True,
            "heavy_policy": "routed",
            "reasons": ["thermal"],
        },
        "paths": {
            "root": "/var/lib/abyss-machine/ai/workload",
            "latest": "/var/lib/abyss-machine/ai/workload/latest.json",
            "taxonomy": "/etc/abyss-machine/ai-workload-taxonomy.json",
            "stats_latest": "/var/lib/abyss-machine/ai/workload/stats/latest.json",
            "runs_today": "/var/lib/abyss-machine/ai/workload/runs/2026/06/2026-06-25.jsonl",
            "refresh_today": "/var/lib/abyss-machine/ai/workload/refresh/2026/06/2026-06-25.jsonl",
        },
        "auto_refresh": {
            "service": {"active": True},
            "timer": {"active": True},
            "command": "abyss-machine ai workload refresh --json",
        },
    }


def _workload_stats_inputs() -> dict[str, object]:
    return {
        "config": {
            "workload": {
                "duration_bands_sec": {
                    "probe": 1.0,
                    "light": 5.0,
                    "medium": 30.0,
                    "heavy": 180.0,
                }
            }
        },
        "records": [
            {
                "workload_id": "embedding_eval",
                "device": "GPU",
                "profile": "quick",
                "declared_class": "medium",
                "capability": "embeddings",
                "operation": "eval",
                "resource_profile_scope": "eval",
                "ok": True,
                "measured_duration_sec": 2.0,
                "metrics": {"latency_ms": 10.0, "ignored": "not_numeric"},
                "source": {"generated_at": "2026-06-25T12:00:00+00:00"},
            },
            {
                "workload_id": "embedding_eval",
                "device": "GPU",
                "profile": "quick",
                "declared_class": "medium",
                "capability": "embeddings",
                "operation": "eval",
                "resource_profile_scope": "eval",
                "ok": False,
                "measured_duration_sec": 7.0,
                "metrics": {"latency_ms": 14.0},
                "source": {"generated_at": "2026-06-25T12:01:00+00:00"},
            },
            {
                "workload_id": "text_eval",
                "device": "CPU",
                "profile": "safe",
                "declared_class": "heavy",
                "capability": "llm_text",
                "operation": "eval",
                "ok": True,
                "measured_duration_sec": 220.0,
                "metrics": {"tokens_per_sec": 3.5},
                "source": {"generated_at": "2026-06-25T12:02:00+00:00"},
            },
        ],
    }


def _workload_measurement_inputs() -> dict[str, object]:
    config = _workload_stats_inputs()["config"]
    resource_profile = {
        "scope": "fixture",
        "delta": {"mem_available_mib": -32.5, "children_user_cpu_sec": 0.25},
        "after": {"thermal": {"temperature_c_max": 70.0}},
        "before": {"thermal": {"temperature_c_max": 68.0}},
    }
    return {
        "config": config,
        "dictation_profile_defs": {
            "fast": {"device": "CPU", "model_dir": "/models/stt/fast"},
        },
        "benchmark": {
            "schema": "abyss_machine_ai_benchmark_v1",
            "generated_at": "2026-06-25T12:00:00+00:00",
            "benchmark": "quick",
            "results": [
                {
                    "ok": True,
                    "device": "gpu",
                    "compile_sec": 1.0,
                    "first_infer_sec": 0.5,
                    "median_infer_sec": 0.2,
                    "elapsed_sec": 1.9,
                    "runs": 3,
                    "resource_profile": resource_profile,
                    "usage": {"prompt_tokens": 4, "completion_tokens": 6},
                }
            ],
        },
        "eval": {
            "schema": "abyss_machine_ai_eval_v1",
            "generated_at": "2026-06-25T12:01:00+00:00",
            "requested_suite": "quick",
            "results": [
                {
                    "suite": "stt",
                    "fixture": {"duration_sec": 1.25},
                    "profiles": [
                        {
                            "ok": True,
                            "profile": "fast",
                            "elapsed_sec": 2.5,
                            "transcript_elapsed_sec": 2.0,
                            "similarity": 0.98,
                            "resource_profile": resource_profile,
                        }
                    ],
                },
                {
                    "suite": "embeddings",
                    "ok": True,
                    "device": "GPU",
                    "model_dir": "/models/embedding",
                    "tokenizer_sec": 0.1,
                    "load_sec": 0.2,
                    "infer_sec": 0.3,
                    "duplicate_cosine": 0.99,
                    "resource_profile": resource_profile,
                },
                {
                    "suite": "text",
                    "ok": True,
                    "device": "CPU",
                    "model_dir": "/models/text",
                    "load_sec": 1.0,
                    "generate_sec": 2.0,
                    "chars": 42,
                    "text": "ok",
                    "usage": {"prompt_tokens": 2, "completion_tokens": 3},
                },
            ],
        },
        "resident": {
            "schema": "abyss_machine_gemma4_spark_resident_audit_v1",
            "generated_at": "2026-06-25T12:02:00+00:00",
            "profile": "gemma4.spark",
            "current": {
                "tiny_generation": {
                    "ok": True,
                    "elapsed_ms": 1250,
                    "max_tokens": 16,
                    "content_excerpt": "hello",
                    "http": {"ok": True, "status": 200, "elapsed_sec": 1.3},
                    "token_accounting": {
                        "source_kind": "openai_compatible_usage",
                        "count_basis": "provider_reported",
                        "input_tokens": 5,
                        "output_tokens": 7,
                        "model_id": "gemma4",
                        "provider": "llama.cpp",
                    },
                }
            },
        },
        "tts": {
            "schema": "abyss_machine_ai_tts_eval_v1",
            "generated_at": "2026-06-25T12:03:00+00:00",
            "ok": True,
            "profile": "quality",
            "result": {
                "wall_sec": 8.0,
                "rtf": 0.5,
                "text_chars": 20,
                "device": "GPU",
                "output": "/tmp/out.wav",
                "audio": {"exists": True, "duration_sec": 4.0, "sample_rate": 24000},
                "subprocess": {"load_sec": 1.0, "synth_sec": 6.0, "samples": 96000},
                "profile_status": {"model": {"path": "/models/tts/quality"}},
                "resource_profile": resource_profile,
            },
        },
    }


def test_ai_workload_measurement_extractors_are_module_owned_contracts() -> None:
    inputs = _workload_measurement_inputs()
    common = {
        "schema_prefix": "abyss_machine",
        "version": "test",
        "recorded_at": "2026-06-25T12:10:00+00:00",
        "config": inputs["config"],
    }
    benchmark = workload_measurements_from_benchmark(
        inputs["benchmark"],
        benchmark_latest_path="/var/lib/abyss-machine/ai/benchmarks/latest.json",
        **common,
    )
    eval_records = workload_measurements_from_eval(
        inputs["eval"],
        eval_latest_path="/var/lib/abyss-machine/ai/evals/latest.json",
        dictation_profile_defs=inputs["dictation_profile_defs"],
        **common,
    )
    resident = workload_measurements_from_resident_audit(
        inputs["resident"],
        resident_audit_latest_path="/var/lib/abyss-machine/ai/llm/resident/audit/latest.json",
        **common,
    )
    tts = workload_measurements_from_tts_eval(
        inputs["tts"],
        tts_eval_latest_path="/var/lib/abyss-machine/ai/tts/eval/latest.json",
        class_levels={"probe": 0, "light": 1, "medium": 2, "heavy": 3, "sustained": 4},
        **common,
    )
    all_records = benchmark + eval_records + resident + tts

    assert [item["workload_id"] for item in benchmark] == ["openvino.synthetic_smoke.gpu"]
    assert benchmark[0]["duration_band"] == "light"
    assert benchmark[0]["token_accounting"]["total_tokens"] == 10
    assert benchmark[0]["metrics"]["resource_children_user_cpu_sec"] == 0.25

    assert [item["workload_id"] for item in eval_records] == [
        "stt.fast",
        "embeddings.openvino.eval",
        "llm_text.openvino.eval",
    ]
    assert eval_records[0]["device"] == "CPU"
    assert eval_records[1]["metrics"]["component_sum_sec"] == 0.6
    assert eval_records[2]["metrics"]["token_total_per_sec"] == round(5 / 3.0, 6)
    assert eval_records[2]["quality"]["non_empty_text"] is True

    assert resident[0]["duration_band"] == "light"
    assert resident[0]["provider"] == "llama.cpp"
    assert resident[0]["metrics"]["token_total_tokens"] == 12
    assert resident[0]["http"]["status"] == 200

    assert tts[0]["workload_id"] == "tts.quality.eval"
    assert tts[0]["declared_class"] == "heavy"
    assert tts[0]["metrics"]["synth_sec"] == 6.0
    assert tts[0]["model_dir"] == "/models/tts/quality"
    assert all(item["schema"] == "abyss_machine_ai_workload_measurement_v1" for item in all_records)
    assert all(item["recorded_at"] == "2026-06-25T12:10:00+00:00" for item in all_records)


def test_ai_workload_measurement_cli_wrappers_delegate_to_module(monkeypatch) -> None:
    from abyss_machine import cli

    inputs = _workload_measurement_inputs()
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T12:10:00+00:00")
    monkeypatch.setattr(cli, "ai_config", lambda: inputs["config"])
    monkeypatch.setattr(cli, "dictation_profiles", lambda: inputs["dictation_profile_defs"])

    common = {
        "schema_prefix": cli.SCHEMA_PREFIX,
        "version": cli.VERSION,
        "recorded_at": "2026-06-25T12:10:00+00:00",
        "config": inputs["config"],
    }
    assert cli.ai_workload_measurements_from_benchmark(inputs["benchmark"]) == workload_measurements_from_benchmark(
        inputs["benchmark"],
        benchmark_latest_path=str(cli.AI_BENCHMARK_LATEST_PATH),
        **common,
    )
    assert cli.ai_workload_measurements_from_eval(inputs["eval"]) == workload_measurements_from_eval(
        inputs["eval"],
        eval_latest_path=str(cli.AI_EVAL_LATEST_PATH),
        dictation_profile_defs=inputs["dictation_profile_defs"],
        **common,
    )
    assert cli.ai_workload_measurements_from_resident_audit(inputs["resident"]) == workload_measurements_from_resident_audit(
        inputs["resident"],
        resident_audit_latest_path=str(cli.AI_LLM_RESIDENT_AUDIT_LATEST_PATH),
        **common,
    )
    assert cli.ai_workload_measurements_from_tts_eval(inputs["tts"]) == workload_measurements_from_tts_eval(
        inputs["tts"],
        tts_eval_latest_path=str(cli.AI_TTS_EVAL_LATEST_PATH),
        class_levels=cli.AI_WORKLOAD_CLASS_LEVELS,
        **common,
    )


def test_ai_workload_stats_document_is_module_owned_aggregation() -> None:
    inputs = _workload_stats_inputs()
    data = workload_stats_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        records=inputs["records"],
        config=inputs["config"],
        runs_daily_glob="/var/lib/abyss-machine/ai/workload/runs/YYYY/MM/YYYY-MM-DD.jsonl",
        latest_path="/var/lib/abyss-machine/ai/workload/stats/latest.json",
    )

    assert workload_numeric(True) is None
    assert workload_numeric(3) == 3.0
    assert workload_duration_band(7.0, inputs["config"]) == "medium"
    assert workload_metric_stats([1.0, 3.0]) == {"count": 2, "min": 1.0, "max": 3.0, "avg": 2.0, "latest": 3.0}
    assert data["schema"] == "abyss_machine_ai_workload_stats_v1"
    assert data["summary"]["records"] == 3
    assert data["summary"]["groups"] == 2
    assert data["summary"]["by_declared_class"] == {"heavy": 1, "medium": 2}
    assert data["summary"]["by_capability"] == {"embeddings": 2, "llm_text": 1}
    embedding = next(item for item in data["groups"] if item["workload_id"] == "embedding_eval")
    assert embedding["count"] == 2
    assert embedding["ok_count"] == 1
    assert embedding["failed_count"] == 1
    assert embedding["success_rate"] == 0.5
    assert embedding["metrics"]["latency_ms"]["avg"] == 12.0
    assert embedding["latest_duration_band"] == "medium"
    assert embedding["latest_seen_at"] == "2026-06-25T12:01:00+00:00"
    assert data["policy"]["absent_metrics_mean_unmeasured"] is True


def test_ai_workload_stats_cli_delegates_to_module(monkeypatch) -> None:
    from abyss_machine import cli

    inputs = _workload_stats_inputs()
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T12:00:00+00:00")
    monkeypatch.setattr(cli, "ai_config", lambda: inputs["config"])
    monkeypatch.setattr(cli, "ai_workload_read_measurements", lambda: inputs["records"])

    result = cli.ai_workload_stats(write_latest=False)
    expected = workload_stats_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-25T12:00:00+00:00",
        records=inputs["records"],
        config=inputs["config"],
        runs_daily_glob=str(cli.AI_WORKLOAD_RUNS_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        latest_path=str(cli.AI_WORKLOAD_STATS_LATEST_PATH),
    )

    assert result == expected


def test_ai_workload_refresh_plan_and_document_are_module_owned() -> None:
    config = {"workload": {"auto_refresh": {"run_quick_benchmark": True, "allow_when_hot": False}}}
    policy = {"class": "hot", "can_run_heavy": False, "reasons": ["thermal"]}
    plan = workload_refresh_probe_plan(config=config, policy=policy, run_probe=None)
    doc = workload_refresh_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        policy=policy,
        probe_plan=plan,
        benchmark_result=None,
        refresh={"ok": True, "records_appended": 2},
        stats={"ok": True, "summary": {"records": 2}},
        stats_latest_path="/var/lib/abyss-machine/ai/workload/stats/latest.json",
    )
    nonfatal = workload_refresh_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        policy={"class": "green", "can_run_heavy": True, "reasons": []},
        probe_plan={"quick_benchmark_requested": True, "quick_benchmark_skip_reasons": []},
        benchmark_result={
            "ok": False,
            "generated_at": "bench-at",
            "summary": {"devices_tested": 0, "devices_failed": 0, "devices_skipped": 1},
        },
        refresh={"ok": True},
        stats={"ok": True, "summary": {"records": 3}},
        stats_latest_path="/var/lib/abyss-machine/ai/workload/stats/latest.json",
    )

    assert plan == {"quick_benchmark_requested": True, "quick_benchmark_skip_reasons": ["policy_hot"]}
    assert doc["schema"] == "abyss_machine_ai_workload_refresh_v1"
    assert doc["ok"] is True
    assert doc["actions"]["quick_benchmark_requested"] is True
    assert doc["actions"]["quick_benchmark_ran"] is False
    assert doc["actions"]["quick_benchmark_skip_reasons"] == ["policy_hot"]
    assert doc["benchmark"] is None
    assert doc["stats"]["summary"] == {"records": 2}
    assert nonfatal["ok"] is True
    assert nonfatal["actions"]["quick_benchmark_nonfatal_skip"] is True
    assert nonfatal["benchmark"]["nonfatal_for_refresh"] is True


def test_ai_workload_refresh_cli_delegates_policy_and_envelope(monkeypatch) -> None:
    from abyss_machine import cli

    config = {"workload": {"auto_refresh": {"run_quick_benchmark": True, "allow_when_hot": False}}}
    policy = {"class": "hot", "can_run_heavy": False, "reasons": ["thermal"]}
    refresh = {"ok": True, "records_appended": 2}
    stats = {"ok": True, "summary": {"records": 2}}
    benchmark_calls: list[str] = []
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T12:00:00+00:00")
    monkeypatch.setattr(cli, "ai_config", lambda: config)
    monkeypatch.setattr(cli, "ai_policy", lambda write_latest=True: policy)
    monkeypatch.setattr(cli, "ai_benchmark_quick", lambda write_latest=True: benchmark_calls.append("called") or {"ok": True})
    monkeypatch.setattr(cli, "ai_workload_refresh_from_latest", lambda: refresh)
    monkeypatch.setattr(cli, "ai_workload_stats", lambda write_latest=True: stats)

    result = cli.ai_workload_refresh(write_latest=False, run_probe=None)
    plan = workload_refresh_probe_plan(config=config, policy=policy, run_probe=None)
    expected = workload_refresh_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-25T12:00:00+00:00",
        policy=policy,
        probe_plan=plan,
        benchmark_result=None,
        refresh=refresh,
        stats=stats,
        stats_latest_path=str(cli.AI_WORKLOAD_STATS_LATEST_PATH),
    )

    assert benchmark_calls == []
    assert result == expected


def test_ai_workload_taxonomy_document_is_module_owned_read_model() -> None:
    data = workload_taxonomy_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        class_levels={"probe": 0, "light": 1, "medium": 2, "heavy": 3, "sustained": 4},
    )

    assert data["schema"] == "abyss_machine_ai_workload_taxonomy_v1"
    assert data["classes"][0] == {
        "class": "probe",
        "level": 0,
        "description": "metadata, inventory, or tiny synthetic smoke checks",
        "route": "allowed in every machine mode; keep low frequency on battery",
    }
    assert data["classes"][-1]["class"] == "sustained"
    assert data["workloads"]["llm_text.openvino.eval"]["class"] == "heavy"
    assert data["workloads"]["tts.fallback.eval"]["class"] == "light"
    assert data["workloads"]["openvino.synthetic_smoke"]["known_metrics"] == [
        "compile_sec",
        "first_infer_sec",
        "median_infer_sec",
        "elapsed_sec",
    ]
    assert data["policy"]["facts_only"] is True
    assert data["policy"]["measurement_rule"].startswith("Only measured durations")
    assert data["policy"]["non_claims"] == [
        "Class labels are host routing policy, not abyss-stack runtime promotion decisions.",
        "Unmeasured CPU, RAM, power, and token throughput fields are intentionally absent; token throughput appears only when source artifacts carry token evidence.",
    ]


def test_ai_workload_taxonomy_cli_delegates_to_module(monkeypatch) -> None:
    from abyss_machine import cli

    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T12:00:00+00:00")

    result = cli.ai_workload_taxonomy(write_latest=False)
    expected = workload_taxonomy_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-25T12:00:00+00:00",
        class_levels=cli.AI_WORKLOAD_CLASS_LEVELS,
    )

    assert result == expected


def test_ai_workload_status_document_is_module_owned_routing_read_model() -> None:
    inputs = _workload_status_inputs()
    data = workload_status_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        taxonomy=inputs["taxonomy"],
        refresh=inputs["refresh"],
        stats=inputs["stats"],
        policy=inputs["policy"],
        paths=inputs["paths"],
        auto_refresh=inputs["auto_refresh"],
    )

    assert data["schema"] == "abyss_machine_ai_workload_status_v1"
    assert data["ok"] is True
    assert data["summary"] == {"records": 3, "groups": 2}
    assert data["routing"]["current_max_recommended_level"] == 2
    assert data["routing"]["basis"] == "routed_heavy_requires_cpu_route"
    assert data["routing"]["workloads"]["embedding_eval"]["recommended_now"] is True
    assert data["routing"]["workloads"]["text_eval"]["recommended_now"] is False
    assert data["taxonomy"]["latest"] == inputs["paths"]["taxonomy"]
    assert data["auto_refresh"]["command"] == "abyss-machine ai workload refresh --json"
    assert data["policy"]["facts_only"] is True


def test_ai_workload_status_cli_delegates_to_module(monkeypatch) -> None:
    from abyss_machine import cli

    inputs = _workload_status_inputs()
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T12:00:00+00:00")
    monkeypatch.setattr(cli, "ai_workload_taxonomy", lambda write_latest=True: inputs["taxonomy"])
    monkeypatch.setattr(cli, "ai_workload_refresh_from_latest", lambda: inputs["refresh"])
    monkeypatch.setattr(cli, "ai_workload_stats", lambda write_latest=True: inputs["stats"])
    monkeypatch.setattr(cli, "ai_policy", lambda write_latest=True: inputs["policy"])
    monkeypatch.setattr(cli, "ai_daily_jsonl_path", lambda root: f"{root}/today.jsonl")
    monkeypatch.setattr(cli, "systemd_unit", lambda name: {"name": name, "active": name.endswith(".timer")})

    result = cli.ai_workload_status(write_latest=False)
    expected = workload_status_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-25T12:00:00+00:00",
        taxonomy=inputs["taxonomy"],
        refresh=inputs["refresh"],
        stats=inputs["stats"],
        policy=inputs["policy"],
        paths={
            "root": str(cli.AI_WORKLOAD_ROOT),
            "latest": str(cli.AI_WORKLOAD_LATEST_PATH),
            "taxonomy": str(cli.AI_WORKLOAD_TAXONOMY_PATH),
            "stats_latest": str(cli.AI_WORKLOAD_STATS_LATEST_PATH),
            "runs_today": f"{cli.AI_WORKLOAD_RUNS_ROOT}/today.jsonl",
            "refresh_today": f"{cli.AI_WORKLOAD_REFRESH_ROOT}/today.jsonl",
        },
        auto_refresh={
            "service": {"name": cli.AI_WORKLOAD_REFRESH_SERVICE, "active": False},
            "timer": {"name": cli.AI_WORKLOAD_REFRESH_TIMER, "active": True},
            "command": "abyss-machine ai workload refresh --json",
        },
    )

    assert result == expected


def test_token_accounting_contract_profiles_and_summaries_are_module_owned() -> None:
    contract = token_accounting_contract_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        root="/var/lib/abyss-machine/ai/token-accounting",
        latest_path="/var/lib/abyss-machine/ai/token-accounting/latest.json",
        profiles_latest_path="/var/lib/abyss-machine/ai/token-accounting/profiles/latest.json",
        counts_latest_path="/var/lib/abyss-machine/ai/token-accounting/counts/latest.json",
    )
    profile = token_accounting_profile_entry(
        "gemma4.spark",
        {
            "local_exists": True,
            "model_id": "fixture-model",
            "local_path": "/srv/abyss-machine/cache/ai/gemma.gguf",
            "backend": "llama.cpp",
            "runtime": {
                "configured_version": "fixture",
                "llama_cli": "/srv/abyss-machine/runtimes/llama.cpp/llama-cli",
                "llama_server": "/srv/abyss-machine/runtimes/llama.cpp/llama-server",
            },
        },
        {
            "tokenizer_path": "/srv/abyss-machine/runtimes/llama.cpp/llama-tokenize",
            "tokenizer_exists": True,
            "candidate_paths": ["/srv/abyss-machine/runtimes/llama.cpp/llama-tokenize"],
            "library_paths": ["/srv/abyss-machine/runtimes/llama.cpp/lib"],
        },
    )
    profiles = token_accounting_profiles_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        root="/var/lib/abyss-machine/ai/token-accounting",
        profile_rows={"gemma4.spark": profile},
    )
    summary = token_accounting_sanitize_summary(
        {
            "generator_version": "2",
            "provider_reported_event_count": "1",
            "estimated_event_count": True,
            "count_by_basis": {"provider_reported": "1", "bad": "nan"},
            "totals_by_basis": {
                "provider_reported": {"input_tokens": "3", "output_tokens": 2, "total_tokens": "5", "ignored": 99},
                "estimated": {"total_tokens": "9", "context_tokens": "120", "context_window_tokens": "1000"},
            },
        }
    )
    aggregate = token_accounting_merge_summaries(
        [summary],
        {"kind": "fixture", "session_count": 1},
    )

    assert contract["schema"] == "abyss_machine_ai_token_accounting_contract_v1"
    assert contract["fields"]["privacy"] == token_accounting_privacy_flags()
    assert contract["policy"]["do_not_store_prompt_text"] is True
    assert profile["status"] == "exact-ready"
    assert profile["count_basis"] == "exact_tokenizer"
    assert profile["tokenizer_id"] == "llama.cpp:fixture:gemma4.spark"
    assert profiles["ok"] is True
    assert profiles["summary"] == {"profiles": 1, "exact_ready_profiles": 1, "unknown_profiles": 0}
    assert "estimated_event_count" not in summary
    assert summary["count_by_basis"] == {"provider_reported": 1}
    assert summary["totals_by_basis"]["provider_reported"] == {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5}
    assert aggregate["totals_by_basis"]["estimated"]["context_window_tokens"] == 1000


def test_token_accounting_aoa_selection_planning_and_count_documents_are_module_owned() -> None:
    sessions = [
        {"session_id": "older", "session_label": "2026-06-20__002__older", "updated_at": "2026-06-20T01:00:00Z"},
        {"session_id": "newer", "session_label": "2026-06-21__001__newer", "updated_at": "2026-06-21T02:00:00Z"},
        {"session_id": "latest", "session_label": "2026-06-22__003__latest", "updated_at": "2026-06-22T03:00:00Z"},
    ]
    selected, diagnostics, effective_since = token_accounting_aoa_select_records(
        sessions,
        target="all",
        since=None,
        since_days=2,
        until=None,
        limit=2,
        today=dt.date(2026, 6, 22),
    )
    summary = {
        "selected_sessions": 2,
        "available_sessions": 3,
        "generated_token_accounting_sessions": 1,
        "missing_generated_token_accounting": 1,
        "provider_reported_sessions": 1,
        "estimated_only_sessions": 0,
        "source_counts": {"session_registry": 1, "missing": 1},
        "diagnostics": 1,
    }
    aggregate = token_accounting_merge_summaries(
        [
            {
                "provider_reported_event_count": 1,
                "count_by_basis": {"provider_reported": 1},
                "totals_by_basis": {
                    "provider_reported": {"total_tokens": 5, "context_tokens": 100, "context_window_tokens": 1000}
                },
            }
        ],
        {"kind": "fixture", "session_count": 2},
    )
    planning = token_accounting_aoa_planning(aggregate, summary)
    document = token_accounting_aoa_summary_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        ok=True,
        aoa_root="/srv/AbyssOS/.aoa",
        target="all",
        since=effective_since,
        until=None,
        limit=2,
        summary=summary,
        aggregate=aggregate,
        sessions=[{"session_id": "safe", "token_accounting": {}}],
        diagnostics=["generated_token_accounting_missing", "generated_token_accounting_missing"],
        session_registry_path="/srv/AbyssOS/.aoa/session-registry.json",
        session_registry_sha256="sha256:fixture",
    )
    count_doc = token_accounting_count_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        profile_name="gemma4.spark",
        profile={
            "tokenizer_id": "llama.cpp:fixture:gemma4.spark",
            "model_id": "fixture-model",
            "model_path": "/models/gemma.gguf",
            "tokenizer": {"tokenizer_path": "/runtime/llama-tokenize"},
        },
        input_bytes=b"SECRET_PROMPT_TEXT",
        elapsed_sec=0.1234567,
        total_tokens=3,
        ok=True,
        error=None,
        returncode=0,
        stderr="diagnostic",
    )
    missing = token_accounting_count_error_result(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        profile_name="missing",
        error="profile_not_found",
        known_profiles=["gemma4.spark"],
    )
    encoded_count = json.dumps(count_doc, ensure_ascii=False, sort_keys=True)

    assert [item["session_id"] for item in selected] == ["older", "newer"]
    assert diagnostics == []
    assert effective_since == "2026-06-20"
    assert planning["usable_for_capacity_planning"] is True
    assert planning["quality"] == "missing_generated_ledgers"
    assert planning["context_pressure"]["ratio"] == 0.1
    assert document["schema"] == "abyss_machine_ai_token_accounting_aoa_session_memory_summary_v1"
    assert document["diagnostics"] == ["generated_token_accounting_missing"]
    assert document["policy"]["raw_transcripts_read"] is False
    assert token_accounting_parse_count("Total number of tokens: 42\n") == 42
    assert token_accounting_parse_count("ids [1, 2, 3]") == 3
    assert count_doc["schema"] == "abyss_machine_ai_token_accounting_count_v1"
    assert count_doc["token_accounting"]["total_tokens"] == 3
    assert count_doc["input_bytes"] == len(b"SECRET_PROMPT_TEXT")
    assert "SECRET_PROMPT_TEXT" not in encoded_count
    assert missing["known_profiles"] == ["gemma4.spark"]


def test_token_accounting_tokenizer_route_contracts_are_module_owned() -> None:
    profile = {
        "runtime": {
            "llama_cli": "/srv/abyss-machine/runtimes/llama.cpp/current/bin/llama-cli",
            "llama_server": "/srv/abyss-machine/runtimes/llama.cpp/current/bin/llama-server",
            "root": "/srv/abyss-machine/runtimes/llama.cpp/current",
        }
    }
    candidates = token_accounting_tokenizer_candidates(profile)
    library_candidates = token_accounting_library_candidates(candidates[0], profile)
    resolution = token_accounting_tokenizer_resolution(
        tokenizer=candidates[0],
        candidate_paths=candidates,
        library_paths=library_candidates[:2],
    )

    assert candidates == [
        Path("/srv/abyss-machine/runtimes/llama.cpp/current/bin/llama-tokenize"),
        Path("/srv/abyss-machine/runtimes/llama.cpp/current/bin/bin/llama-tokenize"),
        Path("/srv/abyss-machine/runtimes/llama.cpp/current/llama-tokenize"),
    ]
    assert library_candidates[:4] == [
        Path("/srv/abyss-machine/runtimes/llama.cpp/current/bin/lib64"),
        Path("/srv/abyss-machine/runtimes/llama.cpp/current/bin/lib"),
        Path("/srv/abyss-machine/runtimes/llama.cpp/current/lib64"),
        Path("/srv/abyss-machine/runtimes/llama.cpp/current/lib"),
    ]
    assert resolution == {
        "tokenizer_path": "/srv/abyss-machine/runtimes/llama.cpp/current/bin/llama-tokenize",
        "tokenizer_exists": True,
        "candidate_paths": [str(path) for path in candidates],
        "library_paths": [str(path) for path in library_candidates[:2]],
    }


def test_token_accounting_count_execution_contracts_are_module_owned() -> None:
    profile = {
        "model_path": "/srv/abyss-machine/cache/ai/models/gemma.gguf",
        "tokenizer": {
            "tokenizer_path": "/srv/abyss-machine/runtimes/llama.cpp/current/bin/llama-tokenize",
            "library_paths": [
                "/srv/abyss-machine/runtimes/llama.cpp/current/lib64",
                "/srv/abyss-machine/runtimes/llama.cpp/current/lib",
            ],
        },
    }

    assert token_accounting_count_command(profile) == [
        "/srv/abyss-machine/runtimes/llama.cpp/current/bin/llama-tokenize",
        "-m",
        "/srv/abyss-machine/cache/ai/models/gemma.gguf",
        "--stdin",
        "--ids",
        "--show-count",
        "--no-bos",
        "--log-disable",
    ]
    assert token_accounting_count_env_overlay(profile, "/existing/lib") == {
        "LD_LIBRARY_PATH": "/srv/abyss-machine/runtimes/llama.cpp/current/lib64:/srv/abyss-machine/runtimes/llama.cpp/current/lib:/existing/lib"
    }
    assert token_accounting_count_env_overlay({"tokenizer": {"library_paths": []}}, "/existing/lib") == {}
    assert token_accounting_count_execution_result(
        stdout="Total number of tokens: 7\n",
        stderr="",
        returncode=0,
    ) == {
        "ok": True,
        "total_tokens": 7,
        "error": None,
        "returncode": 0,
        "stderr": "",
    }
    assert token_accounting_count_execution_result(stdout="not a count", stderr="bad tokenizer", returncode=1) == {
        "ok": False,
        "total_tokens": None,
        "error": "bad tokenizer",
        "returncode": 1,
        "stderr": "bad tokenizer",
    }
    assert token_accounting_count_execution_result(stdout="not a count", stderr="", returncode=0)["error"] == (
        "tokenizer_output_missing_total_count"
    )


def test_token_accounting_cli_tokenizer_route_wrappers_delegate_to_module(monkeypatch) -> None:
    from abyss_machine import cli

    profile = {
        "runtime": {
            "llama_cli": "/runtime/bin/llama-cli",
            "llama_server": "/runtime/bin/llama-server",
            "root": "/runtime",
        }
    }
    candidates = token_accounting_tokenizer_candidates(profile)
    found = candidates[0]
    existing_dirs = {Path("/runtime/bin/lib64"), Path("/runtime/lib")}

    def fake_exists(path: Path) -> bool:
        return path == found or path in existing_dirs

    monkeypatch.setattr(Path, "exists", fake_exists)
    monkeypatch.setattr(cli.os, "access", lambda path, mode: Path(path) == found and mode == cli.os.X_OK)

    library_paths = [path for path in token_accounting_library_candidates(found, profile) if path in existing_dirs]
    expected = token_accounting_tokenizer_resolution(
        tokenizer=found,
        candidate_paths=candidates,
        library_paths=library_paths,
    )

    assert cli.ai_token_accounting_tokenizer_candidates(profile) == candidates
    assert cli.ai_token_accounting_library_paths(found, profile) == library_paths
    assert cli.ai_token_accounting_resolve_tokenizer(profile) == expected


def test_token_accounting_cli_contract_and_profile_documents_delegate_to_module(monkeypatch) -> None:
    from abyss_machine import cli

    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T12:00:00+00:00")
    expected_contract = token_accounting_contract_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-25T12:00:00+00:00",
        root=cli.AI_TOKEN_ACCOUNTING_ROOT,
        latest_path=cli.AI_TOKEN_ACCOUNTING_LATEST_PATH,
        profiles_latest_path=cli.AI_TOKEN_ACCOUNTING_PROFILES_LATEST_PATH,
        counts_latest_path=cli.AI_TOKEN_ACCOUNTING_COUNTS_LATEST_PATH,
    )
    registry = {
        "profiles": {
            "gemma4.spark": {
                "local_exists": True,
                "model_id": "fixture-model",
                "local_path": "/models/gemma.gguf",
                "backend": "llama.cpp",
                "runtime": {"configured_version": "fixture", "llama_cli": "/runtime/llama-cli"},
            }
        }
    }
    tokenizer = {
        "tokenizer_path": "/runtime/llama-tokenize",
        "tokenizer_exists": True,
        "candidate_paths": ["/runtime/llama-tokenize"],
        "library_paths": [],
    }
    monkeypatch.setattr(cli, "ai_llm_registry", lambda write_latest=True: registry)
    monkeypatch.setattr(cli, "ai_token_accounting_resolve_tokenizer", lambda profile: tokenizer)

    profile_row = token_accounting_profile_entry("gemma4.spark", registry["profiles"]["gemma4.spark"], tokenizer)
    expected_profiles = token_accounting_profiles_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-25T12:00:00+00:00",
        root=cli.AI_TOKEN_ACCOUNTING_ROOT,
        profile_rows={"gemma4.spark": profile_row},
    )

    assert cli.ai_token_accounting_contract(write_latest=False) == expected_contract
    assert cli.ai_token_accounting_profiles(write_latest=False) == expected_profiles


def test_token_accounting_cli_count_text_delegates_count_execution_contract(monkeypatch) -> None:
    from abyss_machine import cli

    profile = {
        "profile": "gemma4.spark",
        "exact_supported": True,
        "tokenizer_id": "llama.cpp:fixture:gemma4.spark",
        "model_id": "fixture-model",
        "model_path": "/srv/abyss-machine/cache/ai/models/gemma.gguf",
        "tokenizer": {
            "tokenizer_path": "/srv/abyss-machine/runtimes/llama.cpp/current/bin/llama-tokenize",
            "library_paths": ["/srv/abyss-machine/runtimes/llama.cpp/current/lib"],
        },
    }
    profiles = {"profiles": {"gemma4.spark": profile}}
    captured: dict[str, object] = {}
    monotonic_values = iter([100.0, 100.25])

    class FakeProc:
        returncode = 0
        stdout = "Total number of tokens: 7\n"
        stderr = "diagnostic"

    def fake_run(cmd, input, text, stdout, stderr, timeout, check, env):
        captured.update(
            {
                "cmd": cmd,
                "input": input,
                "text": text,
                "stdout": stdout,
                "stderr": stderr,
                "timeout": timeout,
                "check": check,
                "env": env,
            }
        )
        return FakeProc()

    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T12:00:00+00:00")
    monkeypatch.setattr(cli.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(cli, "ai_token_accounting_profiles", lambda write_latest=True: profiles)
    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/existing/lib")

    result = cli.ai_token_accounting_count_text(
        profile_name="gemma4.spark",
        text="SECRET_PROMPT_TEXT",
        write_latest=False,
        timeout=12.5,
    )
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True)

    assert captured["cmd"] == token_accounting_count_command(profile)
    assert captured["input"] == "SECRET_PROMPT_TEXT"
    assert captured["text"] is True
    assert captured["stdout"] == cli.subprocess.PIPE
    assert captured["stderr"] == cli.subprocess.PIPE
    assert captured["timeout"] == 12.5
    assert captured["check"] is False
    assert captured["env"]["LD_LIBRARY_PATH"] == "/srv/abyss-machine/runtimes/llama.cpp/current/lib:/existing/lib"
    assert result["schema"] == "abyss_machine_ai_token_accounting_count_v1"
    assert result["ok"] is True
    assert result["elapsed_sec"] == 0.25
    assert result["input_bytes"] == len(b"SECRET_PROMPT_TEXT")
    assert result["token_accounting"]["total_tokens"] == 7
    assert result["tokenizer_returncode"] == 0
    assert result["tokenizer_stderr_tail"] == "diagnostic"
    assert "SECRET_PROMPT_TEXT" not in encoded


def _llm_path_refs() -> dict[str, object]:
    return {
        "AI_LLM_ROOT": "/var/lib/abyss-machine/ai/llm",
        "AI_LLM_AGENTS_PATH": "/var/lib/abyss-machine/ai/llm/AGENTS.md",
        "AI_CONFIG_PATH": "/etc/abyss-machine/ai.json",
        "AI_LLM_REGISTRY_ROOT": "/var/lib/abyss-machine/ai/llm/registry",
        "AI_LLM_REGISTRY_LATEST_PATH": "/var/lib/abyss-machine/ai/llm/registry/latest.json",
        "AI_LLM_REGISTRY_TODAY_PATH": "/var/lib/abyss-machine/ai/llm/registry/2026/06/2026-06-25.jsonl",
        "AI_LLM_REGISTRY_DAILY_GLOB": "/var/lib/abyss-machine/ai/llm/registry/YYYY/MM/YYYY-MM-DD.jsonl",
        "AI_LLM_VALIDATE_ROOT": "/var/lib/abyss-machine/ai/llm/validate",
        "AI_LLM_VALIDATE_LATEST_PATH": "/var/lib/abyss-machine/ai/llm/validate/latest.json",
        "AI_LLM_RESIDENT_ROOT": "/var/lib/abyss-machine/ai/llm/resident/gemma4.spark",
        "AI_LLM_RESIDENT_CONTROLLER": "/srv/abyss-machine/tools/abyss-gemma4-spark-resident",
        "AI_LLM_RESIDENT_STATUS_LATEST_PATH": "/var/lib/abyss-machine/ai/llm/resident/gemma4.spark/status/latest.json",
        "AI_LLM_RESIDENT_MONITOR_LATEST_PATH": "/var/lib/abyss-machine/ai/llm/resident/gemma4.spark/monitor/latest.json",
        "AI_LLM_RESIDENT_DIGEST_LATEST_PATH": "/var/lib/abyss-machine/ai/llm/resident/gemma4.spark/digests/latest.json",
        "AI_LLM_RESIDENT_JOBS_ROOT": "/var/lib/abyss-machine/ai/llm/resident/gemma4.spark/jobs",
        "AI_LLM_RESIDENT_JOBS_LATEST_PATH": "/var/lib/abyss-machine/ai/llm/resident/gemma4.spark/jobs/latest.json",
        "AI_LLM_RESIDENT_MICRO_LATEST_PATH": "/var/lib/abyss-machine/ai/llm/resident/gemma4.spark/jobs/micro/latest.json",
        "AI_LLM_RESIDENT_JOBS_VALIDATE_LATEST_PATH": "/var/lib/abyss-machine/ai/llm/resident/gemma4.spark/jobs/validate/latest.json",
        "AI_LLM_RESIDENT_CANDIDATES_LATEST_PATH": "/var/lib/abyss-machine/ai/llm/resident/gemma4.spark/candidates/latest.json",
        "AI_LLM_RESIDENT_CANDIDATES_VALIDATE_LATEST_PATH": "/var/lib/abyss-machine/ai/llm/resident/gemma4.spark/candidates/validate/latest.json",
        "AI_LLM_RESIDENT_EVALS_LATEST_PATH": "/var/lib/abyss-machine/ai/llm/evals/resident/gemma4.spark/latest.json",
        "AI_LLM_RESIDENT_EVALS_VALIDATE_LATEST_PATH": "/var/lib/abyss-machine/ai/llm/evals/resident/gemma4.spark/validate/latest.json",
        "AI_LLM_RESIDENT_JOB_NAMES": ["micro", "digest"],
        "AI_LLM_WORKHORSE_ROOT": "/var/lib/abyss-machine/ai/llm/workhorse/gemma4.workhorse",
        "AI_LLM_WORKHORSE_CONTROLLER": "/srv/abyss-machine/tools/abyss-gemma4-e4b-harness",
        "AI_LLM_WORKHORSE_PREFLIGHT_LATEST_PATH": "/var/lib/abyss-machine/ai/llm/workhorse/gemma4.workhorse/preflight/latest.json",
        "AI_LLM_WORKHORSE_PACK_LATEST_PATH": "/var/lib/abyss-machine/ai/llm/workhorse/gemma4.workhorse/packs/latest.json",
        "AI_LLM_WORKHORSE_REVIEW_LATEST_PATH": "/var/lib/abyss-machine/ai/llm/workhorse/gemma4.workhorse/reviews/latest.json",
        "AI_LLM_WORKHORSE_VALIDATE_LATEST_PATH": "/var/lib/abyss-machine/ai/llm/workhorse/gemma4.workhorse/validate/latest.json",
        "AI_CACHE_ROOT": "/srv/abyss-machine/cache/ai",
    }


def _llm_path_config() -> dict[str, object]:
    return {
        "model_root_base": "/srv/abyss-machine/cache/ai",
        "runtime": {
            "root": "/srv/abyss-machine/runtimes/llama.cpp/current",
            "llama_cli": "/srv/abyss-machine/runtimes/llama.cpp/current/llama-cli",
            "llama_server": "/srv/abyss-machine/runtimes/llama.cpp/current/llama-server",
        },
        "families": {
            "gemma4": {"local_root": "/srv/abyss-machine/cache/ai/gemma4"},
            "ignored": "not-a-family-dict",
        },
    }


def test_llm_paths_document_is_module_owned_read_model() -> None:
    refs = _llm_path_refs()
    data = llm_paths_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        refs=refs,
        config=_llm_path_config(),
    )

    assert data["schema"] == "abyss_machine_ai_llm_paths_v1"
    assert data["registry"]["today"] == refs["AI_LLM_REGISTRY_TODAY_PATH"]
    assert data["resident"]["profile"] == "gemma4.spark"
    assert data["resident"]["job_names"] == ["micro", "digest"]
    assert data["resident"]["micro_latest"] == refs["AI_LLM_RESIDENT_MICRO_LATEST_PATH"]
    assert data["workhorse"]["mode"] == "non_resident_on_demand_review_harness"
    assert data["workhorse"]["policy"]["starts_llama_server"] is False
    assert data["runtime"]["llama_cli"].endswith("/llama-cli")
    assert data["model_roots"] == {
        "base": "/srv/abyss-machine/cache/ai",
        "families": {"gemma4": "/srv/abyss-machine/cache/ai/gemma4"},
    }
    assert data["commands"]["workhorse_review_model"] == "abyss-machine ai llm workhorse review --run-model --json"
    assert data["policy"]["host_layer_mutates_stack"] is False


def test_llm_paths_cli_delegates_to_module(monkeypatch) -> None:
    from abyss_machine import cli

    config = _llm_path_config()
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T12:00:00+00:00")
    monkeypatch.setattr(cli, "ai_llm_config", lambda: config)
    monkeypatch.setattr(cli, "ai_daily_jsonl_path", lambda root: Path(f"/fixture/{Path(root).name}/today.jsonl"))

    expected = llm_paths_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-25T12:00:00+00:00",
        refs=cli.ai_llm_path_refs(),
        config=config,
    )

    assert cli.ai_llm_paths() == expected


def test_ai_paths_and_runtime_snapshot_documents_are_module_owned() -> None:
    refs = _runtime_refs()
    paths = ai_paths_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        refs=refs,
        stack_model_roots=[Path("/srv/AbyssOS/abyss-stack/Models")],
        openvino_config={"python": "/usr/bin/abyss-openvino-python"},
    )
    snapshot = ai_runtime_snapshot_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        current={
            "kernel": "6.12",
            "openvino_version": "2026.1",
            "available_devices": ["CPU", "GPU"],
            "python_packages": {"openvino": "2026.1"},
            "npu_user_driver": {"ok": True},
            "packages": {"intel-npu": "installed"},
        },
        devices={"openvino": {"ok": True}},
        python_runtime={"ok": True, "packages": {"openvino": "2026.1"}},
        kernel_modules={"loaded": {"i915": {}}},
        previous_latest={"current": {"kernel": "6.11", "openvino_version": "2026.1", "available_devices": ["CPU"]}},
    )

    assert paths["schema"] == "abyss_machine_ai_paths_v1"
    assert paths["benchmarks"]["today"] == refs["AI_BENCHMARK_TODAY_PATH"]
    assert paths["llm"]["registry_latest"] == "/fixture/llm/latest.json"
    assert paths["tts"]["synth_today"] == refs["AI_TTS_SYNTH_TODAY_PATH"]
    assert paths["stack_model_roots"] == ["/srv/AbyssOS/abyss-stack/Models"]

    assert snapshot["schema"] == "abyss_machine_ai_runtime_v1"
    assert snapshot["ok"] is True
    assert snapshot["drift_from_previous_latest"] == ["kernel", "available_devices", "python_packages", "npu_user_driver", "packages"]
    assert snapshot["policy"]["internet_freshness_checked"] is False


def _capability_inputs() -> dict[str, object]:
    return {
        "devices": {"ready": {"openvino": True, "gpu": True, "npu": True}},
        "models": {
            "entries": [
                {"category": "openvino_ir", "name": "Qwen3-Embedding", "path": "/models/embedding"},
                {"category": "openvino_ir", "name": "Qwen3-4B", "path": "/models/qwen3-4b"},
                {"category": "openvino_ir", "name": "Qwen3-TTS", "path": "/models/tts/qwen3"},
            ]
        },
        "dictation": {
            "server_socket_exists": True,
            "profiles": {"auto": {"model_dir": "/models/stt/auto", "model_dir_exists": True, "device": "GPU"}},
        },
        "tts_profiles": {
            "profiles": {
                "quality": {"status": "executable"},
                "fast": {"status": "model-ready-adapter-missing"},
            }
        },
        "latest_tts_eval": {"ok": False, "generated_at": "tts-eval-at", "profile": "quality", "summary": {"profiles": 1}},
        "latest_tts_success": {"ok": True, "generated_at": "tts-success-at", "profile": "quality", "summary": {"wall_sec": 1.2}},
        "llm_registry": {
            "summary": {"ready_profiles": 1},
            "profiles": {"gemma4.spark": {"status": "ready", "role": "resident_small_brain"}},
        },
        "llm_resident_status": {"ok": True, "status": "running"},
        "llm_resident_digest": {"ok": True, "generated_at": "digest-at", "status": "ok", "digest": {"items": [1, 2]}},
        "llm_resident_micro": {"ok": True, "generated_at": "micro-at", "summary": {"jobs": 1}},
        "llm_resident_jobs": {"ok": True, "generated_at": "jobs-at", "summary": {"jobs": 2}},
        "resident_refs": {
            "status_latest": "/var/lib/abyss-machine/ai/llm/resident/status/latest.json",
            "monitor_latest": "/var/lib/abyss-machine/ai/llm/resident/monitor/latest.json",
            "digest_latest": "/var/lib/abyss-machine/ai/llm/resident/digests/latest.json",
            "micro_latest": "/var/lib/abyss-machine/ai/llm/resident/jobs/micro/latest.json",
            "jobs_latest": "/var/lib/abyss-machine/ai/llm/resident/jobs/latest.json",
            "jobs_validate_latest": "/var/lib/abyss-machine/ai/llm/resident/jobs/validate/latest.json",
        },
        "resident_job_names": ["micro", "digest"],
    }


def test_ai_capabilities_document_is_module_owned() -> None:
    refs = _runtime_refs()
    inputs = _capability_inputs()
    data = ai_capabilities_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        devices=inputs["devices"],
        models=inputs["models"],
        dictation=inputs["dictation"],
        tts_profiles=inputs["tts_profiles"],
        latest_tts_eval=inputs["latest_tts_eval"],
        latest_tts_success=inputs["latest_tts_success"],
        llm_registry=inputs["llm_registry"],
        llm_resident_status=inputs["llm_resident_status"],
        llm_resident_digest=inputs["llm_resident_digest"],
        llm_resident_micro=inputs["llm_resident_micro"],
        llm_resident_jobs=inputs["llm_resident_jobs"],
        refs=refs,
        resident_refs=inputs["resident_refs"],
        resident_job_names=inputs["resident_job_names"],
    )
    latest = ai_capabilities_latest_document(data, latest_path="/var/lib/abyss-machine/ai/capabilities/latest.json")

    assert data["schema"] == "abyss_machine_ai_capabilities_v1"
    assert data["ok"] is True
    assert data["capabilities"]["stt"]["status"] == "ready"
    assert data["capabilities"]["embeddings"]["status"] == "ready"
    assert data["capabilities"]["llm_text"]["status"] == "resident-running"
    assert data["capabilities"]["tts"]["status"] == "runtime-proven"
    assert data["capabilities"]["npu"]["status"] == "runtime-ready"
    assert data["capabilities"]["llm_text"]["resident_candidate"]["digest"]["items"] == 2
    assert data["capabilities"]["llm_text"]["resident_candidate"]["jobs"]["job_names"] == ["micro", "digest"]
    assert data["source_refs"]["llm_registry"] == refs["AI_LLM_REGISTRY_LATEST_PATH"]
    assert data["policy"]["host_layer_mutates_stack"] is False
    assert latest["policy"]["consumed_from_latest"] is True
    assert latest["latest_consumption"]["heavy_runtime_probe_allowed"] is False


def test_ai_capabilities_cli_delegates_projection_to_module(monkeypatch) -> None:
    from abyss_machine import cli

    inputs = _capability_inputs()
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T12:00:00+00:00")
    monkeypatch.setattr(cli, "ai_devices_status", lambda write_latest=True: inputs["devices"])
    monkeypatch.setattr(cli, "ai_models_inventory", lambda write_latest=True: inputs["models"])
    monkeypatch.setattr(cli, "dictation_status", lambda: inputs["dictation"])
    monkeypatch.setattr(cli, "ai_tts_profiles", lambda write_latest=True: inputs["tts_profiles"])
    monkeypatch.setattr(cli, "ai_tts_latest_eval", lambda: inputs["latest_tts_eval"])
    monkeypatch.setattr(cli, "ai_tts_latest_success_eval", lambda: inputs["latest_tts_success"])
    monkeypatch.setattr(cli, "ai_llm_registry", lambda write_latest=True: inputs["llm_registry"])

    def fake_load_json(path):
        text = str(path)
        if "/status/" in text:
            return inputs["llm_resident_status"], None
        if "/digests/" in text:
            return inputs["llm_resident_digest"], None
        if "/micro/" in text:
            return inputs["llm_resident_micro"], None
        if "/jobs/" in text:
            return inputs["llm_resident_jobs"], None
        return {}, "unexpected"

    monkeypatch.setattr(cli, "load_json_document", fake_load_json)
    result = cli.ai_capabilities(write_latest=False)
    expected = ai_capabilities_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-25T12:00:00+00:00",
        devices=inputs["devices"],
        models=inputs["models"],
        dictation=inputs["dictation"],
        tts_profiles=inputs["tts_profiles"],
        latest_tts_eval=inputs["latest_tts_eval"],
        latest_tts_success=inputs["latest_tts_success"],
        llm_registry=inputs["llm_registry"],
        llm_resident_status=inputs["llm_resident_status"],
        llm_resident_digest=inputs["llm_resident_digest"],
        llm_resident_micro=inputs["llm_resident_micro"],
        llm_resident_jobs=inputs["llm_resident_jobs"],
        refs=cli.ai_runtime_path_refs(),
        resident_refs={
            "status_latest": cli.AI_LLM_RESIDENT_ROOT / "status" / "latest.json",
            "monitor_latest": cli.AI_LLM_RESIDENT_ROOT / "monitor" / "latest.json",
            "digest_latest": cli.AI_LLM_RESIDENT_ROOT / "digests" / "latest.json",
            "micro_latest": cli.AI_LLM_RESIDENT_ROOT / "jobs" / "micro" / "latest.json",
            "jobs_latest": cli.AI_LLM_RESIDENT_ROOT / "jobs" / "latest.json",
            "jobs_validate_latest": cli.AI_LLM_RESIDENT_ROOT / "jobs" / "validate" / "latest.json",
        },
        resident_job_names=cli.AI_LLM_RESIDENT_JOB_NAMES,
    )

    assert result == expected


def _policy_inputs() -> dict[str, object]:
    return {
        "config": {
            "thermal_policy": {
                "warm_temperature_c": 80.0,
                "hot_temperature_c": 106.0,
                "critical_temperature_c": 109.0,
                "balanced_warm_heavy_max_c": 105.0,
                "min_battery_percent_for_heavy": 35,
                "telemetry_max_age_sec": 300,
                "rolling_window_sec": 180,
                "falling_trend_min_c": 3.0,
                "thin_laptop_active_range_c": [100.0, 105.0],
            },
            "cpu_routing": {
                "thread_limits": {"heavy": 4},
                "routed_heavy_min_cpus": 4,
                "routed_heavy_max_hot_cpus": 2,
                "routed_heavy_max_critical_cpus": 1,
                "routed_heavy_broad_heat_hot_core_count": 4,
                "routed_heavy_broad_heat_avoid_cpu_count": 6,
                "routed_heavy_block_on_package_hot": False,
                "package_critical_temperature_c": 109.0,
            },
        },
        "battery": {"ac_online": True, "capacity_percent": 82},
        "mode": {
            "selected_mode": "balanced",
            "effective_mode": "balanced",
            "actual_power_profile": "balanced",
        },
        "thermal": {
            "current_temperature_c": 84.0,
            "rolling_avg_temperature_c": 83.0,
            "recent_peak_temperature_c": 99.0,
            "trend": "stable",
            "episode": {"class": "warm_brief"},
        },
        "cpu_thermal_map": {
            "ok": True,
            "class": "warm",
            "available_by_role": {
                "p_cores": [0, 1],
                "e_cores": [2, 3, 4, 5, 6, 7],
                "lp_e_cores": [],
                "unknown": [],
            },
            "available_by_role_cpuset": {"ai": "0-7"},
            "summary": {
                "mapped_core_sensors": 8,
                "package_temperature_c_max": 84.0,
                "core_temperature_c_max": 83.0,
                "route_avoid_cpus": [],
                "hard_avoid_cpus": [],
                "hot_cpus": [],
                "critical_cpus": [],
            },
            "thresholds": {
                "hot_temperature_c": 106.0,
                "package_critical_temperature_c": 109.0,
            },
        },
    }


def test_ai_policy_document_is_module_owned_decision_logic() -> None:
    inputs = _policy_inputs()
    data = ai_policy_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        config=inputs["config"],
        telemetry_age_sec=30,
        battery=inputs["battery"],
        mode=inputs["mode"],
        thermal=inputs["thermal"],
        cpu_thermal_map=inputs["cpu_thermal_map"],
        observability_latest_path="/var/lib/abyss-machine/observability/thermal-battery/latest.json",
        cpu_thermal_map_latest_path="/var/lib/abyss-machine/ai/cpu/thermal-map/latest.json",
    )

    assert data["schema"] == "abyss_machine_ai_policy_v1"
    assert data["ok"] is True
    assert data["class"] == "warm"
    assert data["can_run_heavy"] is True
    assert data["heavy_policy"] == "unrestricted"
    assert data["recommended_devices_by_capability"]["llm_text"] == ["GPU", "CPU"]
    assert "temperature_warm:current=84.0>=threshold=80.0" in data["reasons"]
    assert "balanced_warm_controlled_allowed:current=84.0<threshold=105.0:trend=stable" in data["reasons"]
    assert data["thresholds"]["episode"]["active_high_c"] == 105.0
    assert data["current"]["cpu_thermal_map"]["available_by_role_cpuset"] == {"ai": "0-7"}
    assert data["cpu_routing"]["routed_heavy"]["route"]["cpuset"] == "0-7"
    assert data["source_refs"]["mode_status"] == "abyss-machine mode status --json"


def test_ai_policy_cli_delegates_decision_to_module(monkeypatch) -> None:
    from abyss_machine import cli

    inputs = _policy_inputs()
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T12:00:00+00:00")
    monkeypatch.setattr(cli, "ai_config", lambda: inputs["config"])
    monkeypatch.setattr(cli, "observability_status", lambda: {"latest": {"age_sec": 30, "battery": inputs["battery"]}})
    monkeypatch.setattr(cli, "observability_latest", lambda: {"latest": "unused"})
    monkeypatch.setattr(cli, "mode_status", lambda: inputs["mode"])
    monkeypatch.setattr(cli, "battery_summary", lambda: {"unexpected": True})
    monkeypatch.setattr(cli, "ai_thermal_policy_snapshot", lambda latest, thresholds: inputs["thermal"])
    monkeypatch.setattr(cli, "ai_cpu_thermal_map", lambda write_latest=True: inputs["cpu_thermal_map"])

    result = cli.ai_policy(write_latest=False)
    expected = ai_policy_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-25T12:00:00+00:00",
        config=inputs["config"],
        telemetry_age_sec=30,
        battery=inputs["battery"],
        mode=inputs["mode"],
        thermal=inputs["thermal"],
        cpu_thermal_map=inputs["cpu_thermal_map"],
        observability_latest_path=str(cli.OBSERVABILITY_ROOT / "thermal-battery" / "latest.json"),
        cpu_thermal_map_latest_path=str(cli.AI_CPU_THERMAL_MAP_LATEST_PATH),
    )

    assert result == expected


def test_ai_status_and_report_documents_are_module_owned_contracts() -> None:
    refs = _runtime_refs()
    paths = ai_paths_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        refs=refs,
        stack_model_roots=[],
        openvino_config={},
    )
    devices = {
        "ready": {"openvino": True, "gpu": True, "npu": False},
        "openvino": {"openvino_version": "2026.1", "available_devices": ["CPU", "GPU"]},
    }
    models = {"summary": {"entries": 2}, "roots": [{"path": "/models", "exists": True}]}
    llm_registry = {
        "summary": {"ready_profiles": 1},
        "runtime": {"ok": True},
        "profiles": {
            "gemma4.spark": {
                "status": "ready",
                "role": "resident_small_brain",
                "local_path": "/models/gemma.gguf",
                "size_bytes": 123,
                "model_id": "fixture",
                "hf_file": "gemma.gguf",
            }
        },
    }
    latest_benchmark = {"ok": True, "summary": {"devices_ok": 1}, "generated_at": "bench-at"}
    latest_eval = {"ok": True, "summary": {"suites_ok": 3}, "generated_at": "eval-at"}
    latest_tts_eval = {"ok": False, "summary": {"profiles": 1}, "generated_at": "tts-at"}
    latest_tts_success = {"ok": True, "summary": {"profile": "quality"}, "generated_at": "tts-success-at"}
    tts_profiles = {"summary": {"profiles": 2}}
    tts_server = {"ok": True, "socket": "/run/tts.sock", "ping": {"profile": "quality"}, "service": {"active": True}}
    dictation = {
        "default_profile": "auto",
        "model_root": "/models/stt",
        "server_socket_exists": True,
        "profiles": {"auto": {"model_dir": "/models/stt/auto", "model_dir_exists": True, "device": "GPU"}},
    }
    cpu_route = {"allowed": True, "requested": {"normalized_class": "heavy"}, "route": {"cpuset": "0-3"}, "reasons": ["ok"]}
    cpu_thermal = {"class": "green", "summary": {"route_avoid_cpus": []}, "available_by_role_cpuset": {"ai": "0-3"}}
    cooling = {"ok": True, "temperature": {"class": "green", "summary": {"temperature_c_max": 70}}, "fan": {"fan_mode": "auto"}, "power": {"platform_profile": {"current": "balanced"}}}

    status = ai_status_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        paths=paths,
        config_path="/etc/abyss-machine/ai.json",
        config_exists=True,
        config_load_error=None,
        devices=devices,
        models=models,
        llm_registry=llm_registry,
        latest_benchmark=latest_benchmark,
        latest_eval=latest_eval,
        latest_tts_eval=latest_tts_eval,
        latest_tts_success=latest_tts_success,
        tts_profiles=tts_profiles,
        tts_server=tts_server,
        dictation=dictation,
        cpu_route_latest=cpu_route,
        cpu_thermal_latest=cpu_thermal,
        cooling_latest=cooling,
        refs=refs,
        include_report=True,
        report_latest_path="/var/lib/abyss-machine/ai/reports/latest.json",
        report_exists=False,
    )
    report = ai_report_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        paths=paths,
        status_data=status,
        capabilities={"ok": True, "capabilities": {"tts": {"status": "runtime-proven"}}},
        policy={"ok": True, "class": "green", "can_run_heavy": True, "can_run_routed_heavy": True, "heavy_policy": "unrestricted"},
        runtime={"ok": True, "current": {"kernel": "6.12"}, "drift_from_previous_latest": []},
        storage={"summary": {"stack_local_openvino_cache_dirs": 0}, "host_cache": {"openvino": {"exists": True}}},
        llm_registry=llm_registry,
        llm_validate={"ok": True, "summary": {"fails": 0}},
        token_accounting_profiles={"summary": {"exact_ready_profiles": 1}},
        aoa_token_summary={"ok": True, "summary": {"selected_sessions": 2, "missing_generated_token_accounting": 0}, "planning": {}, "source_truth_owner": ".aoa", "source_truth": []},
        latest_eval=latest_eval,
        latest_benchmark=latest_benchmark,
        latest_tts_eval=latest_tts_eval,
        latest_tts_success=latest_tts_success,
        tts_profiles=tts_profiles,
        tts_server=tts_server,
        workload={"ok": True, "summary": {"records": 4, "groups": 2}, "routing": {"latest": True}},
        cpu_route_latest=cpu_route,
        cpu_thermal_latest=cpu_thermal,
        cooling_latest=cooling,
        observability={"latest": "/var/lib/abyss-machine/observability/latest.json"},
        dictation=dictation,
        refs=refs,
    )

    assert status["schema"] == "abyss_machine_ai_status_v1"
    assert status["ready"] == {
        "openvino": True,
        "gpu": True,
        "npu": False,
        "models": True,
        "llm": True,
        "dictation_server": True,
    }
    assert status["llm"]["profiles"]["gemma4.spark"]["local_path"] == "/models/gemma.gguf"
    assert status["cpu"]["latest_route_cpuset"] == "0-3"
    assert status["report"]["exists"] is False

    assert report["schema"] == "abyss_machine_ai_report_v1"
    assert report["ok"] is True
    assert report["summary"]["tts_server_ok"] is True
    assert report["summary"]["token_accounting_exact_ready_profiles"] == 1
    assert report["token_accounting"]["contract"]["privacy"]["stores_counts_only"] is True
    assert report["bridge"]["manifest"] == refs["MANIFEST_PATH"]
    assert report["non_claims"][0].startswith("Host report is an integration support bundle")

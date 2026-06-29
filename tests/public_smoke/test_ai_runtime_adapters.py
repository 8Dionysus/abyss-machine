from __future__ import annotations

import json
from pathlib import Path
import subprocess
import stat
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import ai_runtime_adapters, ai_runtime_contracts


STAMP = "2026-06-29T12:00:00+00:00"


def test_env_resource_snapshot_and_profile_bindings_use_fake_ports(tmp_path: Path) -> None:
    env = ai_runtime_adapters.subprocess_env_binding(
        environ={"OPENVINO_LOG_LEVEL": "5", "KEEP": "yes"},
        machine_cache_root=tmp_path / "machine-cache",
        ai_cache_root=tmp_path / "ai-cache",
        tmp_root=tmp_path / "tmp",
        openvino_cache_root=tmp_path / "ov-cache",
        extra={"HF_HOME": str(tmp_path / "custom-hf"), "EXTRA": "1"},
    )

    snapshot = ai_runtime_adapters.resource_snapshot(
        now_iso=lambda: STAMP,
        memory_summary=lambda: {"mem_available_mib": 512.25},
        thermal_summary=lambda: {"temperature_c_max": 41.2},
        battery_summary=lambda: {"capacity_percent": 88},
        self_rusage=lambda: {"user_cpu_sec": 1.0, "system_cpu_sec": 0.5},
        children_rusage=lambda: {"user_cpu_sec": 0.2, "system_cpu_sec": 0.1, "maxrss_kib": 1000},
        loadavg=lambda: (1, 2.34567, 3),
    )
    missing_load = ai_runtime_adapters.resource_snapshot(
        now_iso=lambda: STAMP,
        memory_summary=lambda: {},
        thermal_summary=lambda: {},
        battery_summary=lambda: {},
        self_rusage=lambda: {},
        children_rusage=lambda: {},
        loadavg=lambda: (_ for _ in ()).throw(OSError("load unavailable")),
    )
    profile = ai_runtime_adapters.resource_profile(
        schema_prefix="abyss_machine",
        version="test",
        before={
            "memory": {"mem_available_mib": 512.25},
            "thermal": {"temperature_c_max": 41.2},
            "battery": {"capacity_percent": 88},
            "rusage": {
                "self": {"user_cpu_sec": 1.0, "system_cpu_sec": 0.5},
                "children": {"user_cpu_sec": 0.2, "system_cpu_sec": 0.1, "maxrss_kib": 1000},
            },
        },
        after={
            "memory": {"mem_available_mib": 500.0},
            "thermal": {"temperature_c_max": 42.0},
            "battery": {"capacity_percent": 87},
            "rusage": {
                "self": {"user_cpu_sec": 1.25, "system_cpu_sec": 0.6},
                "children": {"user_cpu_sec": 0.7, "system_cpu_sec": 0.3, "maxrss_kib": 1400},
            },
        },
        scope="child_process",
        basis="fixture",
    )

    assert env["OPENVINO_LOG_LEVEL"] == "5"
    assert env["KEEP"] == "yes"
    assert env["HF_HOME"] == str(tmp_path / "custom-hf")
    assert env["TMPDIR"] == str(tmp_path / "tmp" / "ai")
    assert snapshot["captured_at"] == STAMP
    assert snapshot["loadavg"] == [1.0, 2.3457, 3.0]
    assert snapshot["rusage"]["children"]["maxrss_kib"] == 1000
    assert missing_load["loadavg"] is None
    assert profile["schema"] == "abyss_machine_ai_resource_profile_v1"
    assert profile["delta"]["mem_available_mib"] == -12.2
    assert profile["delta"]["children_maxrss_kib"] == 400.0


def test_cli_ai_env_resource_and_profile_bindings_delegate_to_runtime_adapter(monkeypatch) -> None:
    from abyss_machine import cli

    calls: dict[str, Any] = {}

    def fake_env(**kwargs: Any) -> dict[str, str]:
        calls["env"] = kwargs
        return {"ENV": "adapter"}

    def fake_snapshot(**kwargs: Any) -> dict[str, Any]:
        calls["snapshot"] = kwargs
        return {"snapshot": "adapter"}

    def fake_profile(**kwargs: Any) -> dict[str, Any]:
        calls["profile"] = kwargs
        return {"profile": "adapter"}

    monkeypatch.setattr(cli.ai_runtime_adapters, "subprocess_env_binding", fake_env)
    monkeypatch.setattr(cli.ai_runtime_adapters, "resource_snapshot", fake_snapshot)
    monkeypatch.setattr(cli.ai_runtime_adapters, "resource_profile", fake_profile)

    assert cli.ai_subprocess_env({"EXTRA": "1"}) == {"ENV": "adapter"}
    assert cli.ai_resource_snapshot() == {"snapshot": "adapter"}
    assert cli.ai_resource_profile({"before": True}, {"after": True}, "scope", "basis") == {"profile": "adapter"}

    assert calls["env"]["environ"] is cli.os.environ
    assert calls["env"]["extra"] == {"EXTRA": "1"}
    assert calls["snapshot"]["now_iso"] is cli.now_iso
    assert calls["snapshot"]["memory_summary"] is cli.proc_meminfo_summary
    assert calls["snapshot"]["thermal_summary"] is cli.sensors_summary
    assert calls["snapshot"]["battery_summary"] is cli.battery_summary
    assert calls["snapshot"]["loadavg"] is cli.os.getloadavg
    assert calls["profile"]["schema_prefix"] == cli.SCHEMA_PREFIX
    assert calls["profile"]["version"] == cli.VERSION


def test_model_inventory_adapter_walks_configured_roots(tmp_path: Path) -> None:
    root = tmp_path / "models"
    (root / "ovms" / "OpenVINO" / "Qwen3-Embedding").mkdir(parents=True)
    (root / "ovms" / "OpenVINO" / "Qwen3-Embedding" / "model.xml").write_text("<xml/>")
    (root / "ovms" / "OpenVINO" / "Qwen3-Embedding" / "model.bin").write_bytes(b"bin")
    (root / "hf" / "local" / "Gemma").mkdir(parents=True)
    (root / "hf" / "local" / "Gemma" / "config.json").write_text("{}")
    (root / "hf" / "local" / "Gemma" / "tokenizer.json").write_text("{}")
    (root / "hf" / "local" / "Gemma" / "model.safetensors").write_bytes(b"weights")
    (root / "llm").mkdir()
    (root / "llm" / "gemma.gguf").write_bytes(b"gguf")
    (root / ".git" / "ignored").mkdir(parents=True)
    (root / ".git" / "ignored" / "ignored.gguf").write_bytes(b"ignored")

    doc = ai_runtime_adapters.models_inventory(
        config={
            "model_roots": [str(root), str(root), None],
            "inventory": {"max_depth": 8, "max_entries": 20},
        },
        schema_prefix="abyss_machine",
        version="test",
        generated_at=STAMP,
    )

    assert doc["schema"] == "abyss_machine_ai_models_v1"
    assert doc["roots"] == [{"path": str(root), "exists": True, "entries_seen": 3}]
    assert doc["summary"]["by_category"] == {
        "gguf": 1,
        "huggingface_local": 1,
        "ovms_openvino": 1,
    }
    assert all(".git" not in item["path"] for item in doc["entries"])
    assert doc["policy"]["host_layer_mutates_stack"] is False


def test_openvino_and_device_discovery_use_fake_ports(tmp_path: Path) -> None:
    npu_root = tmp_path / "linux-npu-driver"
    (npu_root / "1.2.3").mkdir(parents=True)
    commands: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: Any) -> dict[str, Any]:
        commands.append(command)
        if command[:2] == ["/runtime/python", "-c"]:
            return {
                "ok": True,
                "returncode": 0,
                "stdout": '{"ok": true, "openvino_version": "fixture", "available_devices": ["CPU", "GPU", "NPU"]}',
                "stderr": "",
            }
        if command[:2] == ["rpm", "-q"]:
            return {"ok": command[-1] == "intel-openvino-runtime", "returncode": 0, "stdout": command[-1], "stderr": ""}
        if command == ["ldconfig", "-p"]:
            return {"ok": True, "returncode": 0, "stdout": "libze_intel_gpu.so\nlibnpu_driver.so\n", "stderr": ""}
        raise AssertionError(command)

    data = ai_runtime_adapters.devices_status(
        device_nodes={"dev_dri_present": True, "dev_accel_present": True},
        paths={"schema": "abyss_machine_ai_paths_v1"},
        config={"openvino": {"python": "/unused"}},
        schema_prefix="abyss_machine",
        version="test",
        generated_at=STAMP,
        run_command=fake_run,
        command_exists=lambda name: name in {"rpm", "ldconfig"},
        which=lambda name: "/runtime/python" if name == "abyss-openvino-python" else None,
        path_exists=lambda path: str(path) == "/runtime/python" or Path(path).exists(),
        user_systemd_unit=lambda name: {"unit": name, "active": False},
        npu_driver_root=npu_root,
    )

    assert data["openvino"]["ok"] is True
    assert data["ready"] == {"openvino": True, "cpu": True, "gpu": True, "npu": True}
    assert data["npu_user_driver"]["preferred_version"] == "1.2.3"
    assert data["packages"]["packages"]["intel-openvino-runtime"]["installed"] is True
    assert data["ldconfig"]["matches"] == ["libze_intel_gpu.so", "libnpu_driver.so"]
    assert [command[0] for command in commands].count("rpm") == 5


def test_openvino_discovery_reports_missing_and_invalid_json() -> None:
    missing = ai_runtime_adapters.openvino_runtime_info(
        config={"openvino": {"python": "/missing/python"}},
        schema_prefix="abyss_machine",
        version="test",
        generated_at=STAMP,
        run_command=lambda command, **kwargs: {"ok": True, "stdout": "{}", "stderr": "", "returncode": 0},
        which=lambda name: None,
        path_exists=lambda path: False,
    )
    invalid = ai_runtime_adapters.openvino_runtime_info(
        config={},
        schema_prefix="abyss_machine",
        version="test",
        generated_at=STAMP,
        run_command=lambda command, **kwargs: {"ok": False, "stdout": "not json", "stderr": "bad", "returncode": 1},
        which=lambda name: "/runtime/python",
        path_exists=lambda path: True,
    )

    assert missing["ok"] is False
    assert missing["python"] == "/missing/python"
    assert invalid["ok"] is False
    assert invalid["error"] == "OpenVINO query returned invalid JSON"
    assert invalid["stdout_tail"] == "not json"


def test_openvino_smoke_runner_uses_fake_ports() -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []
    snapshots = iter([{"marker": "before"}, {"marker": "after"}])
    profiles: list[tuple[dict[str, Any], dict[str, Any], str, str]] = []

    def fake_run(command: list[str], **kwargs: Any) -> dict[str, Any]:
        calls.append((command, kwargs))
        return {
            "ok": True,
            "returncode": 0,
            "stdout": '{"device":"GPU","ok":true,"compile_sec":0.1,"runs":5}\n',
            "stderr": "diagnostic",
        }

    def fake_profile(before: dict[str, Any], after: dict[str, Any], scope: str, basis: str) -> dict[str, Any]:
        profiles.append((before, after, scope, basis))
        return {"scope": scope, "basis": basis, "before": before["marker"], "after": after["marker"]}

    data = ai_runtime_adapters.openvino_smoke_device(
        device="GPU",
        timeout_sec=7.5,
        python="/runtime/python",
        run_command=fake_run,
        resource_snapshot=lambda: next(snapshots),
        resource_profile=fake_profile,
        path_exists=lambda path: str(path) == "/runtime/python",
    )
    missing = ai_runtime_adapters.openvino_smoke_device(
        device="CPU",
        timeout_sec=7.5,
        python="/missing/python",
        run_command=lambda command, **kwargs: (_ for _ in ()).throw(AssertionError(command)),
        resource_snapshot=lambda: (_ for _ in ()).throw(AssertionError("snapshot should not run")),
        resource_profile=fake_profile,
        path_exists=lambda path: False,
    )

    assert calls[0][0][:2] == ["/runtime/python", "-c"]
    assert calls[0][0][-1] == "GPU"
    assert calls[0][1] == {"timeout": 7.5}
    assert profiles == [({"marker": "before"}, {"marker": "after"}, "child_process", "OpenVINO smoke subprocess")]
    assert data["ok"] is True
    assert data["resource_profile"] == {
        "scope": "child_process",
        "basis": "OpenVINO smoke subprocess",
        "before": "before",
        "after": "after",
    }
    assert missing == {"device": "CPU", "ok": False, "error": "abyss-openvino-python not found"}


def test_openvino_eval_runners_bind_env_timeout_and_resource_ports(tmp_path: Path) -> None:
    embedding_model = tmp_path / "embedding"
    text_model = tmp_path / "text"
    embedding_model.mkdir()
    text_model.mkdir()
    calls: list[tuple[list[str], dict[str, Any]]] = []
    snapshots = iter([
        {"marker": "embedding-before"},
        {"marker": "embedding-after"},
        {"marker": "text-before"},
        {"marker": "text-after"},
    ])

    def fake_run(command: list[str], **kwargs: Any) -> dict[str, Any]:
        calls.append((command, kwargs))
        if "OVModelForFeatureExtraction" in command[2]:
            return {
                "ok": True,
                "returncode": 0,
                "stdout": '{"ok":true,"duplicate_cosine":0.99,"shape":[3,768]}\n',
                "stderr": "embedding stderr",
            }
        if "openvino_genai" in command[2]:
            return {"ok": True, "returncode": 0, "stdout": '{"ok":true,"text":"4"}\n', "stderr": "text stderr"}
        raise AssertionError(command)

    def fake_profile(before: dict[str, Any], after: dict[str, Any], scope: str, basis: str) -> dict[str, Any]:
        return {"scope": scope, "basis": basis, "before": before["marker"], "after": after["marker"]}

    path_exists = lambda path: str(path) == "/runtime/python" or Path(path).exists()
    missing_model = ai_runtime_adapters.openvino_embedding_eval(
        model_dir=tmp_path / "missing",
        device="CPU",
        cache_dir=tmp_path / "cache",
        timeout_sec=12,
        python="/runtime/python",
        subprocess_env={"ENV": "1"},
        run_command=fake_run,
        resource_snapshot=lambda: next(snapshots),
        resource_profile=fake_profile,
        path_exists=path_exists,
    )
    missing_python = ai_runtime_adapters.openvino_text_eval(
        model_dir=text_model,
        device="CPU",
        cache_dir=tmp_path / "cache",
        prompt="hi",
        timeout_sec=12,
        python="/missing/python",
        subprocess_env={"ENV": "1"},
        run_command=fake_run,
        resource_snapshot=lambda: next(snapshots),
        resource_profile=fake_profile,
        path_exists=path_exists,
    )
    embedding = ai_runtime_adapters.openvino_embedding_eval(
        model_dir=embedding_model,
        device="AUTO:GPU,CPU",
        cache_dir=tmp_path / "cache" / "embedding",
        timeout_sec=13,
        python="/runtime/python",
        subprocess_env={"ENV": "1"},
        run_command=fake_run,
        resource_snapshot=lambda: next(snapshots),
        resource_profile=fake_profile,
        path_exists=path_exists,
    )
    text = ai_runtime_adapters.openvino_text_eval(
        model_dir=text_model,
        device="NPU",
        cache_dir=tmp_path / "cache" / "text",
        prompt="Answer with one token",
        timeout_sec=14,
        python="/runtime/python",
        subprocess_env={"ENV": "1"},
        run_command=fake_run,
        resource_snapshot=lambda: next(snapshots),
        resource_profile=fake_profile,
        path_exists=path_exists,
    )

    assert missing_model["error"] == "model directory missing"
    assert missing_python["error"] == "abyss-openvino-python not found"
    assert calls[0][0][:2] == ["/runtime/python", "-c"]
    assert calls[0][0][-3:] == [str(embedding_model), "AUTO:GPU,CPU", str(tmp_path / "cache" / "embedding")]
    assert calls[0][1] == {"timeout": 13, "env": {"ENV": "1"}}
    assert calls[1][0][-4:] == [str(text_model), "NPU", str(tmp_path / "cache" / "text"), "Answer with one token"]
    assert calls[1][1] == {"timeout": 14, "env": {"ENV": "1"}}
    assert embedding["suite"] == "embeddings"
    assert embedding["ok"] is True
    assert embedding["resource_profile"]["basis"] == "embedding eval subprocess"
    assert text["suite"] == "text"
    assert text["ok"] is True
    assert text["resource_profile"]["basis"] == "OpenVINO GenAI text eval subprocess"


def test_openvino_benchmark_suite_adapter_orchestrates_plan_and_writes(tmp_path: Path) -> None:
    snapshots = iter([{"marker": "before"}, {"marker": "after"}])
    smoke_calls: list[tuple[str, float]] = []
    gate_calls: list[tuple[str, str, bool]] = []
    writes: list[dict[str, Any]] = []
    appends: list[dict[str, Any]] = []
    latest_path = tmp_path / "benchmark" / "latest.json"
    daily_path = tmp_path / "benchmark" / "2026-06-29.jsonl"

    def fake_profile(before: dict[str, Any], after: dict[str, Any], scope: str, basis: str) -> dict[str, Any]:
        return {"scope": scope, "basis": basis, "before": before["marker"], "after": after["marker"]}

    def fake_policy_gate(declared_class: str, operation: str, force: bool) -> dict[str, Any]:
        gate_calls.append((declared_class, operation, force))
        return {"ok": True, "declared_class": declared_class, "operation": operation, "force": force}

    def fake_smoke(device: str, timeout_sec: float) -> dict[str, Any]:
        smoke_calls.append((device, timeout_sec))
        return {"device": device, "ok": True, "elapsed_sec": 0.25}

    result = ai_runtime_adapters.run_openvino_benchmark_suite(
        devices=None,
        config={"benchmark": {"default_devices": ["cpu", "npu"], "per_device_timeout_sec": 10, "npu_timeout_sec": 45}},
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: STAMP,
        policy_gate=fake_policy_gate,
        runtime_info=lambda: {"ok": True, "available_devices": ["CPU"], "python": "/runtime/python"},
        smoke_device=fake_smoke,
        resource_snapshot=lambda: next(snapshots),
        resource_profile=fake_profile,
        write_latest=True,
        latest_path=latest_path,
        daily_path=lambda: daily_path,
        write_json=lambda path, data, mode: writes.append({"path": path, "data": dict(data), "mode": mode}) or None,
        append_jsonl=lambda path, data, mode: appends.append({"path": path, "data": dict(data), "mode": mode}) or None,
        workload_update=lambda data: {"ok": True, "summary_devices": data.get("summary", {}).get("devices_tested")},
    )
    written_doc = {key: value for key, value in result.items() if key != "workload_update"}

    assert gate_calls == [("probe", "ai benchmark --quick", False)]
    assert smoke_calls == [("CPU", 10.0)]
    assert result["schema"] == "abyss_machine_ai_benchmark_v1"
    assert result["requested_devices"] == ["cpu", "npu"]
    assert result["results"] == [
        {"device": "CPU", "ok": True, "elapsed_sec": 0.25},
        {"device": "NPU", "ok": False, "skipped": True, "reason": "device not available"},
    ]
    assert result["summary"]["devices_tested"] == 1
    assert result["resource_profile"] == {
        "scope": "child_process",
        "basis": "whole quick benchmark command",
        "before": "before",
        "after": "after",
    }
    assert result["workload_update"] == {"ok": True, "summary_devices": 1}
    assert writes == [{"path": latest_path, "data": written_doc, "mode": 0o664}]
    assert appends == [{"path": daily_path, "data": written_doc, "mode": 0o664}]


def test_eval_suite_adapter_orchestrates_runners_unknowns_and_writes(tmp_path: Path) -> None:
    snapshots = iter([{"marker": "before"}, {"marker": "after"}])
    gate_calls: list[tuple[str, str, bool]] = []
    writes: list[dict[str, Any]] = []
    appends: list[dict[str, Any]] = []
    runner_calls: list[str] = []
    latest_path = tmp_path / "eval" / "latest.json"
    daily_path = tmp_path / "eval" / "2026-06-29.jsonl"

    def fake_profile(before: dict[str, Any], after: dict[str, Any], scope: str, basis: str) -> dict[str, Any]:
        return {"scope": scope, "basis": basis, "before": before["marker"], "after": after["marker"]}

    def fake_policy_gate(declared_class: str, operation: str, force: bool) -> dict[str, Any]:
        gate_calls.append((declared_class, operation, force))
        return {"ok": True, "declared_class": declared_class}

    result = ai_runtime_adapters.run_eval_suite(
        requested_suite="quick",
        config={"eval": {"quick_suites": ["stt", "mystery", "text"]}},
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: STAMP,
        class_levels=ai_runtime_contracts.WORKLOAD_CLASS_LEVELS,
        policy_gate=fake_policy_gate,
        suite_runners={
            "stt": lambda: runner_calls.append("stt") or {"suite": "stt", "ok": True},
            "text": lambda: runner_calls.append("text") or {"suite": "text", "ok": True},
        },
        resource_snapshot=lambda: next(snapshots),
        resource_profile=fake_profile,
        openvino_cache_root=tmp_path / "openvino-cache",
        write_latest=True,
        latest_path=latest_path,
        daily_path=lambda: daily_path,
        write_json=lambda path, data, mode: writes.append({"path": path, "data": dict(data), "mode": mode}) or None,
        append_jsonl=lambda path, data, mode: appends.append({"path": path, "data": dict(data), "mode": mode}) or None,
        workload_update=lambda data: {"ok": True, "results": len(data.get("results", []))},
        force=True,
    )
    written_doc = {key: value for key, value in result.items() if key != "workload_update"}

    assert gate_calls == [("sustained", "ai eval --suite quick", True)]
    assert runner_calls == ["stt", "text"]
    assert result["schema"] == "abyss_machine_ai_eval_v1"
    assert result["requested_suite"] == "quick"
    assert result["results"] == [
        {"suite": "stt", "ok": True},
        {"suite": "mystery", "ok": False, "error": "unknown eval suite"},
        {"suite": "text", "ok": True},
    ]
    assert result["resource_profile"] == {
        "scope": "mixed_eval_command",
        "basis": "whole eval command",
        "before": "before",
        "after": "after",
    }
    assert result["workload_update"] == {"ok": True, "results": 3}
    assert writes == [{"path": latest_path, "data": written_doc, "mode": 0o664}]
    assert appends == [{"path": daily_path, "data": written_doc, "mode": 0o664}]


def test_eval_suite_adapter_denies_before_execution_and_writes_nothing(tmp_path: Path) -> None:
    snapshots = iter([{"marker": "before"}, {"marker": "after-denied"}])
    writes: list[dict[str, Any]] = []

    def fake_profile(before: dict[str, Any], after: dict[str, Any], scope: str, basis: str) -> dict[str, Any]:
        return {"scope": scope, "basis": basis, "before": before["marker"], "after": after["marker"]}

    denied = ai_runtime_adapters.run_eval_suite(
        requested_suite="text",
        config={},
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: STAMP,
        class_levels=ai_runtime_contracts.WORKLOAD_CLASS_LEVELS,
        policy_gate=lambda declared_class, operation, force: {"ok": False, "declared_class": declared_class, "operation": operation, "force": force},
        suite_runners={"text": lambda: (_ for _ in ()).throw(AssertionError("runner should not execute"))},
        resource_snapshot=lambda: next(snapshots),
        resource_profile=fake_profile,
        openvino_cache_root=tmp_path / "openvino-cache",
        write_latest=True,
        latest_path=tmp_path / "eval" / "latest.json",
        daily_path=lambda: tmp_path / "eval" / "2026-06-29.jsonl",
        write_json=lambda path, data, mode: writes.append({"path": path, "data": dict(data), "mode": mode}) or None,
        append_jsonl=lambda path, data, mode: writes.append({"path": path, "data": dict(data), "mode": mode}) or None,
        workload_update=lambda data: {"ok": True},
    )

    assert denied["schema"] == "abyss_machine_ai_policy_denied_v1"
    assert denied["ok"] is False
    assert denied["suites"] == ["text"]
    assert denied["resource_profile"] == {
        "scope": "policy_check_only",
        "basis": "eval denied before model execution",
        "before": "before",
        "after": "after-denied",
    }
    assert writes == []


def test_workload_store_reads_dedupes_appends_and_updates_stats(tmp_path: Path) -> None:
    runs_root = tmp_path / "workloads" / "runs"
    existing_path = runs_root / "2026" / "06" / "2026-06-28.jsonl"
    existing_path.parent.mkdir(parents=True)
    existing_path.write_text(
        '{"record_id":"old","workload_id":"existing"}\n'
        "not json\n"
        "[]\n"
        '{"record_id":"second","workload_id":"existing"}\n',
        encoding="utf-8",
    )
    daily_path = runs_root / "2026" / "06" / "2026-06-29.jsonl"
    appends: list[dict[str, Any]] = []

    result = ai_runtime_adapters.workload_append_measurements(
        [
            {"record_id": "old", "workload_id": "duplicate"},
            {"record_id": "", "workload_id": "invalid"},
            {"record_id": "new", "workload_id": "fresh"},
        ],
        runs_root=runs_root,
        runs_daily_path=lambda: daily_path,
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: STAMP,
        append_jsonl=lambda path, data, mode: appends.append({"path": path, "data": dict(data), "mode": mode}) or None,
        stats_latest_path=tmp_path / "workloads" / "stats" / "latest.json",
        stats_update=lambda: {"ok": True},
        write_stats=True,
    )

    assert ai_runtime_adapters.workload_measurement_files(runs_root) == [existing_path]
    assert [item["record_id"] for item in ai_runtime_adapters.workload_read_measurements(runs_root)] == ["old", "second"]
    assert result == {
        "schema": "abyss_machine_ai_workload_update_v1",
        "version": "test",
        "generated_at": STAMP,
        "ok": True,
        "records_seen": 3,
        "records_appended": 1,
        "records_skipped_existing_or_invalid": 2,
        "errors": [],
        "stats": {"latest": str(tmp_path / "workloads" / "stats" / "latest.json"), "updated": True},
    }
    assert appends == [{"path": daily_path, "data": {"record_id": "new", "workload_id": "fresh"}, "mode": 0o664}]


def test_workload_refresh_from_latest_uses_source_gates_and_append_port() -> None:
    append_calls: list[tuple[list[dict[str, Any]], bool]] = []

    def extract(label: str) -> Any:
        return lambda data: [{"record_id": label, "source_generated_at": data.get("generated_at")}]

    result = ai_runtime_adapters.workload_refresh_from_latest(
        latest_benchmark={"ok": True, "generated_at": "benchmark-at"},
        latest_eval={"ok": True, "generated_at": "eval-at"},
        latest_tts_eval={"schema": "abyss_machine_ai_tts_eval_v1", "generated_at": "tts-at"},
        latest_resident_audit={"schema": "abyss_machine_gemma4_spark_resident_audit_v1", "generated_at": "resident-at"},
        schema_prefix="abyss_machine",
        benchmark_measurements=extract("benchmark"),
        eval_measurements=extract("eval"),
        tts_eval_measurements=extract("tts"),
        resident_audit_measurements=extract("resident"),
        append_measurements=lambda records, write_stats: append_calls.append((records, write_stats)) or {"ok": True, "records_seen": len(records)},
    )

    assert [item["record_id"] for item in append_calls[0][0]] == ["benchmark", "eval", "tts", "resident"]
    assert append_calls[0][1] is True
    assert result["records_seen"] == 4
    assert result["sources"] == {
        "benchmark_generated_at": "benchmark-at",
        "eval_generated_at": "eval-at",
        "tts_eval_generated_at": "tts-at",
        "resident_audit_generated_at": "resident-at",
    }


def test_workload_stats_taxonomy_refresh_and_status_write_routing(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    run_path = runs_root / "2026" / "06" / "2026-06-29.jsonl"
    run_path.parent.mkdir(parents=True)
    run_path.write_text(
        '{"record_id":"r1","workload_id":"embedding_eval","declared_class":"medium","metrics":{"elapsed_sec":1.0}}\n',
        encoding="utf-8",
    )
    writes: list[dict[str, Any]] = []
    appends: list[dict[str, Any]] = []

    def write_json(path: Path, data: dict[str, Any], mode: int) -> None:
        writes.append({"path": path, "schema": data.get("schema"), "mode": mode})
        return None

    taxonomy = ai_runtime_adapters.workload_taxonomy(
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: STAMP,
        class_levels=ai_runtime_contracts.WORKLOAD_CLASS_LEVELS,
        write_latest=True,
        taxonomy_path=tmp_path / "taxonomy.json",
        write_json=write_json,
    )
    stats = ai_runtime_adapters.workload_stats(
        config={},
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: STAMP,
        runs_root=runs_root,
        runs_daily_glob="/var/lib/abyss-machine/ai/workloads/runs/YYYY/MM/YYYY-MM-DD.jsonl",
        latest_path=tmp_path / "stats.json",
        write_latest=True,
        write_json=write_json,
    )
    refresh = ai_runtime_adapters.workload_refresh(
        config={"workload": {"auto_refresh": {"run_quick_benchmark": True}}},
        policy={"class": "normal"},
        run_probe=None,
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: STAMP,
        benchmark_runner=lambda: {"ok": True, "summary": {"devices_tested": 1}},
        refresh_from_latest=lambda: {"ok": True, "records_seen": 1},
        stats=lambda: stats,
        stats_latest_path=tmp_path / "stats.json",
        write_latest=True,
        refresh_daily_path=lambda: tmp_path / "refresh.jsonl",
        append_jsonl=lambda path, data, mode: appends.append({"path": path, "schema": data.get("schema"), "mode": mode}) or None,
    )
    status = ai_runtime_adapters.workload_status(
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: STAMP,
        taxonomy=lambda: taxonomy,
        refresh_from_latest=lambda: {"ok": True, "records_seen": 1},
        stats=lambda: stats,
        policy=lambda: {"class": "normal", "can_run_heavy": False},
        refresh_from_latest_enabled=True,
        paths={
            "root": "/var/lib/abyss-machine/ai/workloads",
            "latest": "/var/lib/abyss-machine/ai/workloads/latest.json",
            "taxonomy": "/var/lib/abyss-machine/ai/workloads/taxonomy.json",
            "stats_latest": "/var/lib/abyss-machine/ai/workloads/stats/latest.json",
            "runs_today": "/var/lib/abyss-machine/ai/workloads/runs/2026/06/2026-06-29.jsonl",
            "refresh_today": "/var/lib/abyss-machine/ai/workloads/refresh/2026/06/2026-06-29.jsonl",
        },
        auto_refresh={"service": {"active": "active"}, "timer": {"active": "active"}, "command": "abyss-machine ai workload refresh --json"},
        write_latest=True,
        latest_path=tmp_path / "status.json",
        write_json=write_json,
    )

    assert taxonomy["schema"] == "abyss_machine_ai_workload_taxonomy_v1"
    assert stats["schema"] == "abyss_machine_ai_workload_stats_v1"
    assert stats["summary"]["records"] == 1
    assert refresh["schema"] == "abyss_machine_ai_workload_refresh_v1"
    assert refresh["actions"]["quick_benchmark_ran"] is True
    assert status["schema"] == "abyss_machine_ai_workload_status_v1"
    assert status["refresh"] == {"ok": True, "records_seen": 1}
    assert writes == [
        {"path": tmp_path / "taxonomy.json", "schema": "abyss_machine_ai_workload_taxonomy_v1", "mode": 0o664},
        {"path": tmp_path / "stats.json", "schema": "abyss_machine_ai_workload_stats_v1", "mode": 0o664},
        {"path": tmp_path / "status.json", "schema": "abyss_machine_ai_workload_status_v1", "mode": 0o664},
    ]
    assert appends == [{"path": tmp_path / "refresh.jsonl", "schema": "abyss_machine_ai_workload_refresh_v1", "mode": 0o664}]


def test_llm_runtime_profile_and_tokenizer_discovery_are_fakeable(tmp_path: Path) -> None:
    runtime_root = tmp_path / "llama.cpp"
    bin_root = runtime_root / "bin"
    bin_root.mkdir(parents=True)
    llama_cli = bin_root / "llama-cli"
    llama_server = bin_root / "llama-server"
    tokenizer = bin_root / "llama-tokenize"
    lib_root = bin_root / "lib64"
    model = tmp_path / "cache" / "gemma.gguf"
    for path in (llama_cli, llama_server, tokenizer):
        path.write_text("#!/bin/sh\n")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
    lib_root.mkdir()
    model.parent.mkdir()
    model.write_bytes(b"model")

    runtime = ai_runtime_adapters.llm_runtime_status(
        {
            "runtime": {
                "root": str(runtime_root),
                "llama_cli": str(llama_cli),
                "llama_server": str(llama_server),
                "backend": "vulkan+cpu",
            }
        },
        run_command=lambda command, **kwargs: {"ok": True, "returncode": 0, "stdout": "llama fixture\n", "stderr": ""},
    )
    profile = {
        "role": "resident_small_brain",
        "local_path": str(model),
        "runtime": {"root": str(runtime_root), "llama_cli": str(llama_cli), "llama_server": str(llama_server)},
        "gpu_layers": 99,
        "context_size": 8192,
    }
    profile_status = ai_runtime_adapters.llm_profile_status(
        family_name="gemma4",
        profile_name="spark",
        profile=profile,
        runtime=runtime,
        cache_root=model.parent,
        storage_protection=lambda path: {"decision": "allow", "path": str(path)},
        is_relative_to_path=lambda path, root: path.is_relative_to(root),
    )
    tokenizer_status = ai_runtime_adapters.token_accounting_resolve_tokenizer(profile)

    assert runtime["ok"] is True
    assert runtime["version_stdout"] == "llama fixture\n"
    assert profile_status["status"] == "ready"
    assert profile_status["storage"]["under_host_cache"] is True
    assert tokenizer_status["tokenizer_path"] == str(tokenizer)
    assert tokenizer_status["library_paths"] == [str(lib_root)]


def test_llm_resident_controller_runner_binds_command_timeout_and_output() -> None:
    controller = Path("/srv/abyss-machine/tools/abyss-gemma4-spark-resident")
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(command: list[str], **kwargs: Any) -> dict[str, Any]:
        calls.append((command, kwargs))
        return {"returncode": 0, "stdout": '{"ok": true}\\n', "stderr": ""}

    job = ai_runtime_adapters.llm_resident_controller_run(
        controller=controller,
        command="job",
        job_name="dictation_quality",
        limit=2,
        json_output=True,
        run_command=fake_run,
    )
    jobs_run = ai_runtime_adapters.llm_resident_controller_run(
        controller=controller,
        command="jobs",
        jobs_action="run",
        json_output=True,
        run_command=fake_run,
    )
    policy = ai_runtime_adapters.llm_resident_controller_run(
        controller=controller,
        command="policy",
        job_name="daily_brief",
        request_class="foreground",
        force=True,
        run_command=fake_run,
    )

    assert calls[0] == (
        [str(controller), "job", "dictation_quality", "--limit", "2", "--json"],
        {"timeout": 360.0},
    )
    assert calls[1] == ([str(controller), "jobs", "run", "--json"], {"timeout": 900.0})
    assert calls[2] == (
        [str(controller), "policy", "daily_brief", "--request-class", "foreground", "--force"],
        {"timeout": 60.0},
    )
    assert job["stdout"] == '{"ok": true}\\n'
    assert job["returncode"] == 0
    assert jobs_run["timeout"] == 900.0
    assert policy["command"][-1] == "--force"


def test_llm_resident_controller_runner_reports_json_no_output_error() -> None:
    controller = Path("/srv/abyss-machine/tools/abyss-gemma4-spark-resident")

    def fake_run(command: list[str], **kwargs: Any) -> dict[str, Any]:
        return {"returncode": 2, "stdout": "", "stderr": "controller failed"}

    result = ai_runtime_adapters.llm_resident_controller_run(
        controller=controller,
        command="audit",
        no_generation=True,
        json_output=True,
        run_command=fake_run,
    )

    assert result["command"] == [str(controller), "audit", "--no-generation", "--json"]
    assert result["timeout"] == 180.0
    assert result["returncode"] == 2
    assert result["json_error"] == {
        "ok": False,
        "error": "controller failed",
        "command": [str(controller), "audit", "--no-generation", "--json"],
    }


def test_llm_controller_result_projection_parses_json_and_bounds_invalid_output() -> None:
    parsed = ai_runtime_adapters.llm_controller_result_projection(
        {
            "returncode": 0,
            "command": ["/tool", "status"],
            "stdout": 'controller warmup\n{"ok": true, "status": "ready"}\n',
            "stderr": "",
        },
        json_output=True,
        empty_error="controller produced no output",
        invalid_json_error="controller produced invalid JSON",
    )
    invalid = ai_runtime_adapters.llm_controller_result_projection(
        {
            "returncode": 2,
            "command": ["/tool", "status"],
            "stdout": "not-json-" * 200,
            "stderr": "stderr-" * 200,
        },
        json_output=True,
        empty_error="controller produced no output",
        invalid_json_error="controller produced invalid JSON",
    )
    text = ai_runtime_adapters.llm_controller_result_projection(
        {"returncode": 1, "stdout": "", "stderr": "plain failure"},
        json_output=False,
        empty_error="controller produced no output",
        invalid_json_error="controller produced invalid JSON",
    )

    assert parsed == {"format": "json", "data": {"ok": True, "status": "ready"}, "returncode": 0}
    assert invalid["format"] == "json"
    assert invalid["returncode"] == 2
    assert invalid["data"]["error"] == "controller produced invalid JSON"
    assert invalid["data"]["command"] == ["/tool", "status"]
    assert len(invalid["data"]["stdout_tail"]) == 1000
    assert len(invalid["data"]["stderr_tail"]) == 1000
    assert text == {"format": "text", "text": "plain failure", "returncode": 1}


def test_cli_llm_resident_command_delegates_to_runner(monkeypatch, capsys) -> None:
    from abyss_machine import cli

    calls: dict[str, Any] = {}

    def fake_controller_run(**kwargs: Any) -> dict[str, Any]:
        calls.update(kwargs)
        return {"returncode": 0, "stdout": 'controller warmup\n{"ok": true, "source": "adapter"}\n', "stderr": ""}

    monkeypatch.setattr(cli.ai_runtime_adapters, "llm_resident_controller_run", fake_controller_run)

    rc = cli.main(["ai", "llm", "resident", "jobs", "run", "--limit", "2", "--json"])
    captured = capsys.readouterr()

    assert rc == 0
    assert json.loads(captured.out) == {"ok": True, "source": "adapter"}
    assert calls["controller"] == cli.AI_LLM_RESIDENT_CONTROLLER
    assert calls["command"] == "jobs"
    assert calls["jobs_action"] == "run"
    assert calls["limit"] == 2
    assert calls["json_output"] is True
    assert calls["run_command"] is cli.run


def test_llm_workhorse_controller_runner_binds_command_timeout_and_output() -> None:
    controller = Path("/srv/abyss-machine/tools/abyss-gemma4-e4b-harness")
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(command: list[str], **kwargs: Any) -> dict[str, Any]:
        calls.append((command, kwargs))
        return {"returncode": 0, "stdout": '{"ok": true}\\n', "stderr": ""}

    pack = ai_runtime_adapters.llm_workhorse_controller_run(
        controller=controller,
        command="pack",
        limit=3,
        refresh_candidates=True,
        json_output=True,
        run_command=fake_run,
    )
    review = ai_runtime_adapters.llm_workhorse_controller_run(
        controller=controller,
        command="review",
        run_model=True,
        n_predict=64,
        timeout=8.5,
        json_output=True,
        run_command=fake_run,
    )

    assert calls[0] == (
        [str(controller), "pack", "--limit", "3", "--refresh-candidates", "--json"],
        {"timeout": 120.0},
    )
    assert calls[1] == (
        [
            str(controller),
            "review",
            "--run-model",
            "--n-predict",
            "64",
            "--timeout",
            "8.5",
            "--json",
        ],
        {"timeout": 38.5},
    )
    assert pack["stdout"] == '{"ok": true}\\n'
    assert pack["returncode"] == 0
    assert review["timeout"] == 38.5


def test_llm_workhorse_controller_runner_reports_json_no_output_error() -> None:
    controller = Path("/srv/abyss-machine/tools/abyss-gemma4-e4b-harness")

    def fake_run(command: list[str], **kwargs: Any) -> dict[str, Any]:
        return {"returncode": 2, "stdout": "", "stderr": "workhorse failed"}

    result = ai_runtime_adapters.llm_workhorse_controller_run(
        controller=controller,
        command="validate",
        json_output=True,
        run_command=fake_run,
    )

    assert result["command"] == [str(controller), "validate", "--json"]
    assert result["timeout"] == 120.0
    assert result["returncode"] == 2
    assert result["json_error"] == {
        "ok": False,
        "error": "workhorse failed",
        "command": [str(controller), "validate", "--json"],
    }


def test_cli_llm_workhorse_command_delegates_to_runner(monkeypatch, capsys) -> None:
    from abyss_machine import cli

    calls: dict[str, Any] = {}

    def fake_controller_run(**kwargs: Any) -> dict[str, Any]:
        calls.update(kwargs)
        return {"returncode": 0, "stdout": 'controller warmup\n{"ok": true, "source": "workhorse"}\n', "stderr": ""}

    monkeypatch.setattr(cli.ai_runtime_adapters, "llm_workhorse_controller_run", fake_controller_run)

    rc = cli.main(["ai", "llm", "workhorse", "review", "--run-model", "--timeout", "7", "--json"])
    captured = capsys.readouterr()

    assert rc == 0
    assert json.loads(captured.out) == {"ok": True, "source": "workhorse"}
    assert calls["controller"] == cli.AI_LLM_WORKHORSE_CONTROLLER
    assert calls["command"] == "review"
    assert calls["limit"] == 24
    assert calls["refresh_candidates"] is False
    assert calls["run_model"] is True
    assert calls["n_predict"] == 768
    assert calls["timeout"] == 7.0
    assert calls["json_output"] is True
    assert calls["run_command"] is cli.run


def test_stt_eval_fixture_reuses_existing_valid_wav_without_subprocess() -> None:
    fixture = Path("/fixtures/stt/ru-smoke.wav")
    mkdir_calls: list[Path] = []

    def fail_command_exists(name: str) -> bool:
        raise AssertionError(f"{name} should not be checked for an existing valid fixture")

    def fail_run(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("subprocess should not run for an existing valid fixture")

    result = ai_runtime_adapters.stt_eval_fixture(
        reference_text="локальный искусственный интеллект готов к работе",
        fixture=fixture,
        command_exists=fail_command_exists,
        run_command=fail_run,
        path_exists=lambda path: path == fixture,
        path_size=lambda path: 2400 if path == fixture else None,
        mkdir=lambda path: mkdir_calls.append(path),
        wav_duration=lambda path: 1.5 if path == fixture else None,
        wav_sample_rate=lambda path: 16000 if path == fixture else None,
    )

    assert result == {
        "ok": True,
        "path": str(fixture),
        "created": False,
        "duration_sec": 1.5,
        "sample_rate": 16000,
        "generator": "espeak-ng",
    }
    assert mkdir_calls == [fixture.parent]


def test_stt_eval_fixture_generates_with_espeak_and_ffmpeg() -> None:
    fixture = Path("/fixtures/stt/ru-smoke.wav")
    reference = "локальный искусственный интеллект готов к работе"
    existing: set[Path] = set()
    runs: list[list[str]] = []
    unlinked: list[Path] = []

    def fake_run(argv: list[str], **kwargs: Any) -> dict[str, Any]:
        runs.append(argv)
        if argv[0] == "ffmpeg":
            existing.add(fixture)
        return {"ok": True, "stdout": "", "stderr": "", "returncode": 0}

    result = ai_runtime_adapters.stt_eval_fixture(
        reference_text=reference,
        fixture=fixture,
        command_exists=lambda name: name in {"espeak-ng", "ffmpeg"},
        run_command=fake_run,
        path_exists=lambda path: path in existing,
        path_size=lambda path: 2400 if path in existing else None,
        mkdir=lambda path: None,
        unlink=lambda path: unlinked.append(path),
        wav_duration=lambda path: 1.5 if path in existing else None,
        wav_sample_rate=lambda path: 16000 if path in existing else None,
    )

    assert result == {
        "ok": True,
        "path": str(fixture),
        "created": True,
        "duration_sec": 1.5,
        "sample_rate": 16000,
        "generator": "espeak-ng",
        "resampler": "ffmpeg",
        "stderr": "",
        "returncode": 0,
    }
    assert runs == [
        ["espeak-ng", "-v", "ru", "-s", "145", "-w", str(fixture.with_suffix(".raw.wav")), reference],
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(fixture.with_suffix(".raw.wav")),
            "-ar",
            "16000",
            "-ac",
            "1",
            str(fixture),
        ],
    ]
    assert unlinked == [fixture.with_suffix(".raw.wav")]


def test_stt_eval_fixture_reports_missing_espeak_without_transport() -> None:
    fixture = Path("/fixtures/stt/ru-smoke.wav")

    def fail_run(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("subprocess should not run without espeak-ng")

    result = ai_runtime_adapters.stt_eval_fixture(
        reference_text="ref",
        fixture=fixture,
        command_exists=lambda name: False,
        run_command=fail_run,
        path_exists=lambda path: False,
        path_size=lambda path: None,
        mkdir=lambda path: None,
    )

    assert result == {
        "ok": False,
        "path": str(fixture),
        "error": "espeak-ng not found",
    }


def test_cli_stt_fixture_delegates_generation_to_runtime_adapter(monkeypatch) -> None:
    from abyss_machine import cli

    calls: dict[str, Any] = {}

    def fake_stt_eval_fixture(**kwargs: Any) -> dict[str, Any]:
        calls.update(kwargs)
        return {"ok": True, "path": "/fixtures/stt/ru-smoke.wav", "source": "adapter"}

    monkeypatch.setattr(cli, "AI_FIXTURE_ROOT", Path("/fixtures"))
    monkeypatch.setattr(cli.ai_runtime_adapters, "stt_eval_fixture", fake_stt_eval_fixture)

    result = cli.ensure_stt_fixture("ref")

    assert result == {"ok": True, "path": "/fixtures/stt/ru-smoke.wav", "source": "adapter"}
    assert calls == {
        "reference_text": "ref",
        "fixture": Path("/fixtures/stt/ru-smoke.wav"),
        "command_exists": cli.command_exists,
        "run_command": cli.run,
    }


def test_stt_eval_runner_uses_dictation_transport_timing_and_resources() -> None:
    reference = "локальный искусственный интеллект готов к работе"
    fixture = {"ok": True, "path": "/tmp/ru-smoke.wav", "duration_sec": 2.0, "sample_rate": 16000}
    transcript = {
        "ok": True,
        "text": reference,
        "raw_text": reference,
        "client_elapsed_sec": 0.7,
        "via": "dictation-client",
        "profile_selection": {"profile": "fast"},
    }
    before = {"memory": {"mem_available_mib": 1000.0}, "rusage": {"self": {}, "children": {}}}
    after = {"memory": {"mem_available_mib": 990.0}, "rusage": {"self": {}, "children": {}}}
    snapshots = iter([before, after])
    ticks = iter([20.0, 20.375])
    transcribe_calls: list[tuple[str, str]] = []
    profile_calls: list[tuple[dict[str, Any], dict[str, Any], str, str]] = []

    def fake_transcribe(path: str, profile: str) -> dict[str, Any]:
        transcribe_calls.append((path, profile))
        return transcript

    def fake_profile(before_doc: dict[str, Any], after_doc: dict[str, Any], scope: str, basis: str) -> dict[str, Any]:
        profile_calls.append((before_doc, after_doc, scope, basis))
        return {"scope": scope, "basis": basis, "delta": {"mem_available_mib": -10.0}}

    result = ai_runtime_adapters.stt_eval_run(
        reference_text=reference,
        fixture=fixture,
        profiles=["fast"],
        similarity_warn_below=0.9,
        transcribe_audio=fake_transcribe,
        monotonic=lambda: next(ticks),
        resource_snapshot=lambda: next(snapshots),
        resource_profile=fake_profile,
    )

    expected_profile = ai_runtime_contracts.stt_eval_profile_result(
        profile="fast",
        reference_text=reference,
        transcript=transcript,
        elapsed_sec=0.375,
        similarity_warn_below=0.9,
        resource_profile={
            "scope": "client_wall_and_system_context",
            "basis": "dictation client call around warm server; server CPU/RAM is not directly attributed",
            "delta": {"mem_available_mib": -10.0},
        },
    )
    assert result == ai_runtime_contracts.stt_eval_result(
        reference_text=reference,
        fixture=fixture,
        profiles=[expected_profile],
    )
    assert transcribe_calls == [("/tmp/ru-smoke.wav", "fast")]
    assert profile_calls == [
        (
            before,
            after,
            "client_wall_and_system_context",
            "dictation client call around warm server; server CPU/RAM is not directly attributed",
        )
    ]


def test_stt_eval_runner_skips_transport_when_fixture_failed() -> None:
    fixture = {"ok": False, "path": "/tmp/missing.wav", "error": "fixture generation failed"}

    def fail_transcribe(path: str, profile: str) -> dict[str, Any]:
        raise AssertionError("transport should not run for failed fixture")

    result = ai_runtime_adapters.stt_eval_run(
        reference_text="ref",
        fixture=fixture,
        profiles=["fast"],
        similarity_warn_below=0.5,
        transcribe_audio=fail_transcribe,
        monotonic=lambda: 1.0,
        resource_snapshot=lambda: {"unexpected": True},
        resource_profile=lambda before, after, scope, basis: {"unexpected": True},
    )

    assert result == ai_runtime_contracts.stt_eval_result(
        reference_text="ref",
        fixture=fixture,
        profiles=[],
    )


def test_cli_stt_eval_delegates_transport_to_runtime_adapter(monkeypatch) -> None:
    from abyss_machine import cli

    reference = "локальный искусственный интеллект готов к работе"
    fixture = {"ok": True, "path": "/fixture/ru-smoke.wav"}
    calls: dict[str, Any] = {}

    def fake_stt_eval_run(**kwargs: Any) -> dict[str, Any]:
        calls.update(kwargs)
        return {"suite": "stt", "ok": True, "source": "adapter"}

    monkeypatch.setattr(
        cli,
        "ai_config",
        lambda: {"eval": {"stt_reference_text": reference, "stt_profiles": ["fast"], "stt_similarity_warn_below": 0.9}},
    )
    monkeypatch.setattr(cli, "ensure_stt_fixture", lambda text: fixture)
    monkeypatch.setattr(cli.ai_runtime_adapters, "stt_eval_run", fake_stt_eval_run)

    result = cli.ai_eval_stt()

    assert result == {"suite": "stt", "ok": True, "source": "adapter"}
    assert calls["reference_text"] == reference
    assert calls["fixture"] == fixture
    assert calls["profiles"] == ["fast"]
    assert calls["similarity_warn_below"] == 0.9
    assert calls["transcribe_audio"] is cli.dictation_transcribe
    assert calls["monotonic"] is cli.time.monotonic
    assert calls["resource_snapshot"] is cli.ai_resource_snapshot
    assert calls["resource_profile"] is cli.ai_resource_profile


def test_token_accounting_count_subprocess_binds_command_env_timeout_and_clock() -> None:
    profile = {
        "profile": "gemma4.spark",
        "model_path": "/srv/abyss-machine/cache/ai/models/gemma.gguf",
        "tokenizer": {
            "tokenizer_path": "/srv/abyss-machine/runtimes/llama.cpp/current/bin/llama-tokenize",
            "library_paths": ["/srv/abyss-machine/runtimes/llama.cpp/current/lib"],
        },
    }
    captured: dict[str, Any] = {}
    monotonic_values = iter([100.0, 100.25])

    class FakeProc:
        returncode = 0
        stdout = "Total number of tokens: 7\n"
        stderr = "diagnostic"

    def fake_run(command: list[str], **kwargs: Any) -> FakeProc:
        captured["command"] = command
        captured.update(kwargs)
        return FakeProc()

    result = ai_runtime_adapters.token_accounting_count_subprocess(
        profile=profile,
        text="SECRET_PROMPT_TEXT",
        timeout=12.5,
        environ={"LD_LIBRARY_PATH": "/existing/lib", "KEEP": "1"},
        run_subprocess=fake_run,
        monotonic=lambda: next(monotonic_values),
    )

    assert captured["command"] == ai_runtime_contracts.token_accounting_count_command(profile)
    assert captured["input"] == "SECRET_PROMPT_TEXT"
    assert captured["text"] is True
    assert captured["stdout"] == subprocess.PIPE
    assert captured["stderr"] == subprocess.PIPE
    assert captured["timeout"] == 12.5
    assert captured["check"] is False
    assert captured["env"]["KEEP"] == "1"
    assert captured["env"]["LD_LIBRARY_PATH"] == "/srv/abyss-machine/runtimes/llama.cpp/current/lib:/existing/lib"
    assert result["elapsed_sec"] == 0.25
    assert result["input_bytes"] == b"SECRET_PROMPT_TEXT"
    assert result["outcome"] == {
        "ok": True,
        "total_tokens": 7,
        "error": None,
        "returncode": 0,
        "stderr": "diagnostic",
    }


def test_token_accounting_count_subprocess_reports_timeout_without_stdout() -> None:
    profile = {
        "model_path": "/model.gguf",
        "tokenizer": {"tokenizer_path": "/runtime/llama-tokenize", "library_paths": []},
    }
    monotonic_values = iter([5.0, 6.5])

    def fake_timeout(command: list[str], **kwargs: Any) -> object:
        raise subprocess.TimeoutExpired(cmd=command, timeout=kwargs["timeout"])

    result = ai_runtime_adapters.token_accounting_count_subprocess(
        profile=profile,
        text="private text",
        timeout=1.0,
        environ={},
        run_subprocess=fake_timeout,
        monotonic=lambda: next(monotonic_values),
    )

    assert result["elapsed_sec"] == 1.5
    assert result["input_bytes"] == b"private text"
    assert result["outcome"] == {
        "ok": False,
        "total_tokens": None,
        "error": "tokenizer_timeout",
        "returncode": None,
        "stderr": None,
    }


def test_token_accounting_store_readmodels_route_writes_and_count(tmp_path: Path) -> None:
    latest_contract = tmp_path / "token-accounting" / "latest.json"
    latest_profiles = tmp_path / "token-accounting" / "profiles" / "latest.json"
    latest_counts = tmp_path / "token-accounting" / "counts" / "latest.json"
    daily_profiles = tmp_path / "token-accounting" / "profiles" / "2026-06-29.jsonl"
    daily_counts = tmp_path / "token-accounting" / "counts" / "2026-06-29.jsonl"
    writes: list[dict[str, Any]] = []
    appends: list[dict[str, Any]] = []

    def fake_write(path: Path, data: dict[str, Any], mode: int) -> None:
        writes.append({"path": path, "schema": data.get("schema"), "mode": mode})
        return None

    def fake_append(path: Path, data: dict[str, Any], mode: int) -> None:
        appends.append({"path": path, "schema": data.get("schema"), "mode": mode})
        return None

    registry = {
        "profiles": {
            "gemma4.spark": {
                "local_exists": True,
                "local_path": "/models/gemma.gguf",
                "model_id": "fixture-model",
                "backend": "llama.cpp",
                "runtime": {"configured_version": "fixture"},
            }
        }
    }
    tokenizer = {
        "tokenizer_path": "/runtime/llama-tokenize",
        "tokenizer_exists": True,
        "candidate_paths": ["/runtime/llama-tokenize"],
        "library_paths": [],
    }
    contract = ai_runtime_adapters.token_accounting_contract_readmodel(
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: STAMP,
        root=tmp_path / "token-accounting",
        latest_path=latest_contract,
        profiles_latest_path=latest_profiles,
        counts_latest_path=latest_counts,
        write_latest=True,
        write_json=fake_write,
    )
    profiles = ai_runtime_adapters.token_accounting_profiles_readmodel(
        registry=registry,
        resolve_tokenizer=lambda profile: tokenizer,
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: STAMP,
        root=tmp_path / "token-accounting",
        write_latest=True,
        latest_path=latest_profiles,
        daily_path=lambda: daily_profiles,
        write_json=fake_write,
        append_jsonl=fake_append,
    )
    latest = ai_runtime_adapters.token_accounting_latest_readmodel(
        latest_path=latest_counts,
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: STAMP,
        read_json=lambda path: ({"schema": "existing", "ok": True, "path": str(path)}, None),
    )
    count = ai_runtime_adapters.token_accounting_count_text_readmodel(
        profile_name="gemma4.spark",
        text="SECRET_PROMPT_TEXT",
        profiles_payload=profiles,
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: STAMP,
        write_latest=True,
        latest_path=latest_counts,
        daily_path=lambda: daily_counts,
        write_json=fake_write,
        append_jsonl=fake_append,
        timeout=12.5,
        environ={"KEEP": "1"},
        count_subprocess=lambda **kwargs: {
            "elapsed_sec": 0.25,
            "input_bytes": kwargs["text"].encode("utf-8", errors="replace"),
            "outcome": {
                "ok": True,
                "total_tokens": 7,
                "error": None,
                "returncode": 0,
                "stderr": "diagnostic",
            },
        },
    )

    assert contract["schema"] == "abyss_machine_ai_token_accounting_contract_v1"
    assert profiles["summary"] == {"profiles": 1, "exact_ready_profiles": 1, "unknown_profiles": 0}
    assert latest["read_at"] == STAMP
    assert count["schema"] == "abyss_machine_ai_token_accounting_count_v1"
    assert count["ok"] is True
    assert count["input_bytes"] == len(b"SECRET_PROMPT_TEXT")
    assert count["token_accounting"]["total_tokens"] == 7
    assert "SECRET_PROMPT_TEXT" not in str(count)
    assert writes == [
        {"path": latest_contract, "schema": "abyss_machine_ai_token_accounting_contract_v1", "mode": 0o664},
        {"path": latest_profiles, "schema": "abyss_machine_ai_token_accounting_profiles_v1", "mode": 0o664},
        {"path": latest_counts, "schema": "abyss_machine_ai_token_accounting_count_v1", "mode": 0o664},
    ]
    assert appends == [
        {"path": daily_profiles, "schema": "abyss_machine_ai_token_accounting_profiles_v1", "mode": 0o664},
        {"path": daily_counts, "schema": "abyss_machine_ai_token_accounting_count_v1", "mode": 0o664},
    ]


def test_python_runtime_and_kernel_module_probes_use_ports() -> None:
    def fake_run(command: list[str], **kwargs: Any) -> dict[str, Any]:
        if command[:2] == ["/runtime/python", "-c"]:
            assert kwargs["env"] == {"OV_CACHE_DIR": "/cache"}
            return {"ok": True, "returncode": 0, "stdout": '{"ok": true, "packages": {"openvino": "2026.0"}}', "stderr": ""}
        if command == ["lsmod"]:
            return {"ok": True, "returncode": 0, "stdout": "Module Size Used by\ni915 10 0\nignored 1 0\n", "stderr": ""}
        if command[:1] == ["modinfo"]:
            return {"ok": command[-1] == "i915", "returncode": 0, "stdout": "summary line\nextra\n", "stderr": "missing"}
        raise AssertionError(command)

    versions = ai_runtime_adapters.python_runtime_versions(
        config={},
        run_command=fake_run,
        which=lambda name: "/runtime/python",
        subprocess_env={"OV_CACHE_DIR": "/cache"},
        path_exists=lambda path: True,
    )
    modules = ai_runtime_adapters.kernel_module_snapshot(
        command_exists=lambda name: name in {"lsmod", "modinfo"},
        run_command=fake_run,
    )

    assert versions["packages"]["openvino"] == "2026.0"
    assert versions["python"] == "/runtime/python"
    assert modules["loaded"] == {"i915": {"size": "10", "used_by": []}}
    assert modules["modinfo"]["i915"]["summary"] == "summary line\nextra"
    assert modules["modinfo"]["xe"]["ok"] is False


def test_core_readmodel_store_adapters_route_writes(tmp_path: Path) -> None:
    writes: list[tuple[Path, str, int]] = []
    appends: list[tuple[Path, str, int]] = []

    def write_json(path: Path, data: dict[str, Any], mode: int) -> None:
        writes.append((path, data["schema"], mode))
        return None

    def append_jsonl(path: Path, data: dict[str, Any], mode: int) -> None:
        appends.append((path, data["schema"], mode))
        return None

    policy = ai_runtime_adapters.policy_readmodel(
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: STAMP,
        config={},
        telemetry_age_sec=1,
        battery={"ac_online": True, "capacity_percent": 90},
        mode={"effective_mode": "performance", "selected_mode": "performance", "actual_power_profile": "performance"},
        thermal={"current_temperature_c": 40.0, "trend": "stable"},
        cpu_thermal_map={"ok": True, "available_by_role": {"p_cores": [0]}, "summary": {}},
        observability_latest_path="/var/lib/abyss-machine/observability/thermal-battery/latest.json",
        cpu_thermal_map_latest_path="/var/lib/abyss-machine/ai/cpu/thermal-map/latest.json",
        write_latest=True,
        latest_path=tmp_path / "policy.json",
        write_json=write_json,
    )
    runtime = ai_runtime_adapters.runtime_snapshot_readmodel(
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: STAMP,
        kernel="test-kernel",
        os_release={"NAME": "TestOS"},
        devices={
            "openvino": {"ok": True, "openvino_version": "fixture", "available_devices": ["CPU"]},
            "npu_user_driver": {"exists": False},
            "packages": {},
        },
        python_runtime={"packages": {"openvino": "fixture"}},
        kernel_modules={},
        previous_latest={"current": {"kernel": "old-kernel"}},
        write_latest=True,
        latest_path=tmp_path / "runtime.json",
        daily_path=lambda: tmp_path / "runtime.jsonl",
        write_json=write_json,
        append_jsonl=append_jsonl,
    )
    status = ai_runtime_adapters.status_readmodel(
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: STAMP,
        paths={"schema": "abyss_machine_ai_paths_v1"},
        config_path=tmp_path / "config.json",
        config_exists=True,
        config_load_error=None,
        devices={"ready": {"openvino": True, "gpu": False, "npu": False}},
        models={"summary": {"entries": 1}, "roots": []},
        llm_registry={"summary": {"ready_profiles": 1}, "profiles": {}},
        latest_benchmark={"ok": True},
        latest_eval={"ok": True},
        latest_tts_eval={},
        latest_tts_success={},
        tts_profiles={"summary": {}},
        tts_server={"ok": False},
        dictation={"profiles": {}, "server_socket_exists": False},
        cpu_route_latest={},
        cpu_thermal_latest={},
        cooling_latest={},
        refs={"AI_REPORT_LATEST_PATH": str(tmp_path / "report.json")},
        include_report=True,
        report_latest_path=tmp_path / "report.json",
        report_exists=False,
    )
    report = ai_runtime_adapters.report_readmodel(
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: STAMP,
        paths={"schema": "abyss_machine_ai_paths_v1"},
        status_data=status,
        capabilities={"ok": True, "capabilities": {"npu": {"status": "ready"}}},
        policy=policy,
        runtime=runtime,
        storage={"summary": {}},
        llm_registry={"summary": {}},
        llm_validate={"ok": True},
        token_accounting_profiles={"summary": {}},
        aoa_token_summary={"summary": {}},
        latest_eval={"ok": True},
        latest_benchmark={"ok": True},
        latest_tts_eval={},
        latest_tts_success={},
        tts_profiles={},
        tts_server={"ok": False},
        workload={"summary": {}},
        cpu_route_latest={},
        cpu_thermal_latest={},
        cooling_latest={},
        observability={},
        dictation={},
        refs={},
        write_latest=True,
        latest_path=tmp_path / "report.json",
        daily_path=lambda: tmp_path / "report.jsonl",
        write_json=write_json,
        append_jsonl=append_jsonl,
    )

    assert policy["schema"] == "abyss_machine_ai_policy_v1"
    assert runtime["schema"] == "abyss_machine_ai_runtime_v1"
    assert status["schema"] == "abyss_machine_ai_status_v1"
    assert report["schema"] == "abyss_machine_ai_report_v1"
    assert writes == [
        (tmp_path / "policy.json", "abyss_machine_ai_policy_v1", 0o664),
        (tmp_path / "runtime.json", "abyss_machine_ai_runtime_v1", 0o664),
        (tmp_path / "report.json", "abyss_machine_ai_report_v1", 0o664),
    ]
    assert appends == [
        (tmp_path / "runtime.jsonl", "abyss_machine_ai_runtime_v1", 0o664),
        (tmp_path / "report.jsonl", "abyss_machine_ai_report_v1", 0o664),
    ]


def test_policy_readmodel_from_live_inputs_uses_fake_ports(tmp_path: Path) -> None:
    writes: list[tuple[Path, str, int]] = []
    cpu_calls: list[dict[str, Any]] = []
    fallback_battery_calls = 0
    thermal_calls: list[tuple[dict[str, Any], dict[str, Any]]] = []

    config = {
        "thermal_policy": {
            "warm_temperature_c": 80.0,
            "hot_temperature_c": 106.0,
            "critical_temperature_c": 109.0,
            "balanced_warm_heavy_max_c": 105.0,
            "min_battery_percent_for_heavy": 35,
            "telemetry_max_age_sec": 300,
        },
        "cpu_routing": {"thread_limits": {"heavy": 4}},
    }
    mode = {"effective_mode": "balanced", "selected_mode": "balanced", "actual_power_profile": "balanced"}
    cpu_map = {"ok": True, "available_by_role": {"p_cores": [0, 1]}, "summary": {}}

    def write_json(path: Path, data: dict[str, Any], mode_bits: int) -> None:
        writes.append((path, data["schema"], mode_bits))

    def thermal_policy_snapshot(latest: dict[str, Any], thresholds: dict[str, Any]) -> dict[str, Any]:
        thermal_calls.append((latest, thresholds))
        return {"current_temperature_c": 84.0, "trend": "stable", "episode": {"class": "warm"}}

    def cpu_thermal_map(**kwargs: Any) -> dict[str, Any]:
        cpu_calls.append(dict(kwargs))
        return cpu_map

    def fallback_battery() -> dict[str, Any]:
        nonlocal fallback_battery_calls
        fallback_battery_calls += 1
        return {"ac_online": True, "capacity_percent": 77}

    collected = ai_runtime_adapters.policy_readmodel_from_live_inputs(
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: STAMP,
        config=config,
        observability_status=lambda: {"latest": {"age_sec": 12, "battery": {"ac_online": True, "capacity_percent": 90}}},
        observability_latest=lambda: {"latest": "thermal-source"},
        mode_status=lambda: mode,
        battery_summary=fallback_battery,
        thermal_policy_snapshot=thermal_policy_snapshot,
        cpu_thermal_map=cpu_thermal_map,
        cpu_thermal_map_input=None,
        observability_latest_path="/var/lib/abyss-machine/observability/thermal-battery/latest.json",
        cpu_thermal_map_latest_path="/var/lib/abyss-machine/ai/cpu/thermal-map/latest.json",
        write_latest=True,
        latest_path=tmp_path / "policy.json",
        write_json=write_json,
    )
    provided = ai_runtime_adapters.policy_readmodel_from_live_inputs(
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: STAMP,
        config=config,
        observability_status=lambda: {"latest": {"age_sec": 18}},
        observability_latest=lambda: {"latest": "thermal-source-2"},
        mode_status=lambda: mode,
        battery_summary=fallback_battery,
        thermal_policy_snapshot=thermal_policy_snapshot,
        cpu_thermal_map=lambda **kwargs: (_ for _ in ()).throw(AssertionError("cpu port should not run")),
        cpu_thermal_map_input={"ok": True, "available_by_role": {"e_cores": [2, 3]}, "summary": {"provided": True}},
        observability_latest_path="/var/lib/abyss-machine/observability/thermal-battery/latest.json",
        cpu_thermal_map_latest_path="/var/lib/abyss-machine/ai/cpu/thermal-map/latest.json",
        write_latest=False,
        latest_path=tmp_path / "policy.json",
        write_json=write_json,
    )

    assert collected["schema"] == "abyss_machine_ai_policy_v1"
    assert collected["generated_at"] == STAMP
    assert collected["current"]["battery"]["capacity_percent"] == 90
    assert collected["current"]["telemetry_age_sec"] == 12
    assert cpu_calls == [{"write_latest": True}]
    assert fallback_battery_calls == 1
    assert provided["current"]["battery"]["capacity_percent"] == 77
    assert provided["current"]["telemetry_age_sec"] == 18
    assert provided["current"]["cpu_thermal_map"]["summary"] == {"provided": True}
    assert thermal_calls == [
        ({"latest": "thermal-source"}, config["thermal_policy"]),
        ({"latest": "thermal-source-2"}, config["thermal_policy"]),
    ]
    assert writes == [(tmp_path / "policy.json", "abyss_machine_ai_policy_v1", 0o664)]


def test_cli_ai_policy_delegates_live_input_collection_to_runtime_adapter(monkeypatch) -> None:
    from abyss_machine import cli

    calls: dict[str, Any] = {}
    provided_cpu_map = {"ok": True}

    def fake_policy_from_live_inputs(**kwargs: Any) -> dict[str, Any]:
        calls.update(kwargs)
        return {"schema": "fixture_policy", "ok": True}

    monkeypatch.setattr(cli, "ai_config", lambda: {"thermal_policy": {}})
    monkeypatch.setattr(cli.ai_runtime_adapters, "policy_readmodel_from_live_inputs", fake_policy_from_live_inputs)

    assert cli.ai_policy(write_latest=False, cpu_thermal_map=provided_cpu_map) == {"schema": "fixture_policy", "ok": True}
    assert calls["schema_prefix"] == cli.SCHEMA_PREFIX
    assert calls["version"] == cli.VERSION
    assert calls["now_iso"] is cli.now_iso
    assert calls["config"] == {"thermal_policy": {}}
    assert calls["observability_status"] is cli.observability_status
    assert calls["observability_latest"] is cli.observability_latest
    assert calls["mode_status"] is cli.mode_status
    assert calls["battery_summary"] is cli.battery_summary
    assert calls["thermal_policy_snapshot"] is cli.ai_thermal_policy_snapshot
    assert calls["cpu_thermal_map"] is cli.ai_cpu_thermal_map
    assert calls["cpu_thermal_map_input"] is provided_cpu_map
    assert calls["write_latest"] is False
    assert calls["latest_path"] == cli.AI_POLICY_LATEST_PATH
    assert calls["write_json"] is cli.safe_atomic_write_json


def test_cli_ai_capabilities_delegates_live_input_collection_to_runtime_adapter(monkeypatch) -> None:
    from abyss_machine import cli

    calls: dict[str, Any] = {}

    def fake_capabilities_from_live_inputs(**kwargs: Any) -> dict[str, Any]:
        calls.update(kwargs)
        return {"schema": "fixture_capabilities", "ok": True}

    monkeypatch.setattr(cli.ai_runtime_adapters, "capabilities_readmodel_from_live_inputs", fake_capabilities_from_live_inputs)

    assert cli.ai_capabilities(write_latest=False) == {"schema": "fixture_capabilities", "ok": True}
    assert calls["schema_prefix"] == cli.SCHEMA_PREFIX
    assert calls["version"] == cli.VERSION
    assert calls["now_iso"] is cli.now_iso
    assert calls["devices_status"] is cli.ai_devices_status
    assert calls["models_inventory"] is cli.ai_models_inventory
    assert calls["dictation_status"] is cli.dictation_status
    assert calls["tts_profiles"] is cli.ai_tts_profiles
    assert calls["tts_latest_eval"] is cli.ai_tts_latest_eval
    assert calls["tts_latest_success"] is cli.ai_tts_latest_success_eval
    assert calls["llm_registry"] is cli.ai_llm_registry
    assert calls["refs"] is cli.ai_runtime_path_refs
    assert calls["resident_status_path"] == cli.AI_LLM_RESIDENT_ROOT / "status" / "latest.json"
    assert calls["resident_monitor_path"] == cli.AI_LLM_RESIDENT_ROOT / "monitor" / "latest.json"
    assert calls["resident_digest_path"] == cli.AI_LLM_RESIDENT_ROOT / "digests" / "latest.json"
    assert calls["resident_micro_path"] == cli.AI_LLM_RESIDENT_ROOT / "jobs" / "micro" / "latest.json"
    assert calls["resident_jobs_path"] == cli.AI_LLM_RESIDENT_ROOT / "jobs" / "latest.json"
    assert calls["resident_jobs_validate_path"] == cli.AI_LLM_RESIDENT_ROOT / "jobs" / "validate" / "latest.json"
    assert calls["resident_job_names"] is cli.AI_LLM_RESIDENT_JOB_NAMES
    assert calls["read_json"] is cli.load_json_document
    assert calls["write_latest"] is False
    assert calls["latest_path"] == cli.AI_CAPABILITIES_LATEST_PATH
    assert calls["write_json"] is cli.safe_atomic_write_json


def test_policy_gate_binding_uses_fake_policy_clock_and_class_levels() -> None:
    calls: list[dict[str, Any]] = []

    def fake_policy(**kwargs: Any) -> dict[str, Any]:
        calls.append(dict(kwargs))
        return {
            "ok": True,
            "class": "warm",
            "can_run_heavy": False,
            "can_run_routed_heavy": True,
            "heavy_policy": "routed",
            "reasons": ["thermal"],
        }

    result = ai_runtime_adapters.policy_gate_binding(
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: STAMP,
        declared_class="heavy",
        operation="fixture op",
        policy=fake_policy,
        force=True,
        class_levels={"cold": 0, "warm": 1, "heavy": 2},
    )

    assert calls == [{"write_latest": True}]
    assert result["schema"] == "abyss_machine_ai_policy_gate_v1"
    assert result["generated_at"] == STAMP
    assert result["declared_class"] == "heavy"
    assert result["operation"] == "fixture op"
    assert result["forced"] is False
    assert result["ok"] is True


def test_resident_latest_readmodels_use_fake_reader(tmp_path: Path) -> None:
    paths = {
        "status_path": tmp_path / "status.json",
        "digest_path": tmp_path / "digest.json",
        "micro_path": tmp_path / "micro.json",
        "jobs_path": tmp_path / "jobs.json",
    }
    payloads = {
        paths["status_path"]: {"ok": True, "status": "running"},
        paths["digest_path"]: [],
        paths["micro_path"]: {"ok": True, "summary": {"ticks": 1}},
        paths["jobs_path"]: {"ok": True, "summary": {"jobs": 2}},
    }

    result = ai_runtime_adapters.resident_latest_readmodels(
        **paths,
        read_json=lambda path: (payloads[path], None),
    )

    assert result == {
        "status": {"ok": True, "status": "running"},
        "digest": {},
        "micro": {"ok": True, "summary": {"ticks": 1}},
        "jobs": {"ok": True, "summary": {"jobs": 2}},
    }


def test_capabilities_readmodel_from_live_inputs_uses_fake_ports(tmp_path: Path) -> None:
    writes: list[tuple[Path, str, int]] = []
    write_latest_calls: list[tuple[str, bool]] = []
    resident_paths = {
        "status": tmp_path / "status.json",
        "monitor": tmp_path / "monitor.json",
        "digest": tmp_path / "digest.json",
        "micro": tmp_path / "micro.json",
        "jobs": tmp_path / "jobs.json",
        "jobs_validate": tmp_path / "jobs-validate.json",
    }
    resident_payloads = {
        resident_paths["status"]: {"ok": True, "status": "running"},
        resident_paths["digest"]: {"ok": True, "generated_at": "digest-at", "status": "ok", "digest": {"items": [1]}},
        resident_paths["micro"]: {"ok": True, "generated_at": "micro-at", "summary": {"jobs": 1}},
        resident_paths["jobs"]: {"ok": True, "generated_at": "jobs-at", "summary": {"jobs": 2}},
    }

    def write_json(path: Path, data: dict[str, Any], mode_bits: int) -> None:
        writes.append((path, data["schema"], mode_bits))

    def latest_port(name: str, payload: dict[str, Any]):
        def _port(**kwargs: Any) -> dict[str, Any]:
            write_latest_calls.append((name, kwargs["write_latest"]))
            return payload

        return _port

    result = ai_runtime_adapters.capabilities_readmodel_from_live_inputs(
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: STAMP,
        devices_status=latest_port("devices", {"ready": {"openvino": True, "npu": True}}),
        models_inventory=latest_port(
            "models",
            {
                "entries": [
                    {"category": "openvino_ir", "name": "Qwen3-Embedding", "path": "/models/embedding"},
                    {"category": "openvino_ir", "name": "Qwen3-4B", "path": "/models/qwen3-4b"},
                    {"category": "openvino_ir", "name": "Qwen3-TTS", "path": "/models/tts/qwen3"},
                ]
            },
        ),
        dictation_status=lambda: {"server_socket_exists": True, "profiles": {"auto": {"model_dir_exists": True}}},
        tts_profiles=latest_port("tts_profiles", {"profiles": {"quality": {"status": "executable"}}}),
        tts_latest_eval=lambda: {"ok": False},
        tts_latest_success=lambda: {"ok": True, "profile": "quality"},
        llm_registry=latest_port("llm_registry", {"summary": {"ready_profiles": 1}, "profiles": {"gemma4.spark": {"status": "ready"}}}),
        refs=lambda: {"AI_LLM_REGISTRY_LATEST_PATH": "/var/lib/abyss-machine/ai/llm/registry/latest.json"},
        resident_status_path=resident_paths["status"],
        resident_monitor_path=resident_paths["monitor"],
        resident_digest_path=resident_paths["digest"],
        resident_micro_path=resident_paths["micro"],
        resident_jobs_path=resident_paths["jobs"],
        resident_jobs_validate_path=resident_paths["jobs_validate"],
        resident_job_names=["micro", "digest"],
        read_json=lambda path: (resident_payloads.get(path, {}), None),
        write_latest=True,
        latest_path=tmp_path / "capabilities.json",
        write_json=write_json,
    )

    assert result["schema"] == "abyss_machine_ai_capabilities_v1"
    assert result["generated_at"] == STAMP
    assert result["capabilities"]["llm_text"]["status"] == "resident-running"
    assert result["capabilities"]["llm_text"]["resident_candidate"]["digest"]["items"] == 1
    assert result["capabilities"]["llm_text"]["resident_candidate"]["jobs"]["job_names"] == ["micro", "digest"]
    assert result["capabilities"]["llm_text"]["resident_candidate"]["status_latest"] == str(resident_paths["status"])
    assert write_latest_calls == [
        ("devices", True),
        ("models", True),
        ("tts_profiles", True),
        ("llm_registry", True),
    ]
    assert writes == [(tmp_path / "capabilities.json", "abyss_machine_ai_capabilities_v1", 0o664)]


def test_token_accounting_aoa_summary_adapter_reads_generated_summaries_without_raw_transcripts(tmp_path: Path) -> None:
    aoa_root = tmp_path / ".aoa"
    sessions_root = aoa_root / "sessions"
    session_with_registry = sessions_root / "2026-06-02__001__registry"
    session_with_index = sessions_root / "2026-06-03__002__index"
    session_with_registry.mkdir(parents=True)
    session_with_index.mkdir(parents=True)
    forbidden = "SECRET_PROMPT_TEXT_SHOULD_NOT_LEAK"
    provider_summary = {
        "schema": ai_runtime_contracts.TOKEN_ACCOUNTING_CONTRACT,
        "schema_version": ai_runtime_contracts.TOKEN_ACCOUNTING_SCHEMA_VERSION,
        "generator_version": 2,
        "provider_reported_event_count": 1,
        "count_by_basis": {"provider_reported": 1},
        "totals_by_basis": {"provider_reported": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5}},
    }
    estimated_summary = {
        "schema": ai_runtime_contracts.TOKEN_ACCOUNTING_CONTRACT,
        "schema_version": ai_runtime_contracts.TOKEN_ACCOUNTING_SCHEMA_VERSION,
        "generator_version": 2,
        "estimated_event_count": 1,
        "count_by_basis": {"estimated": 1},
        "totals_by_basis": {"estimated": {"total_tokens": 9}},
    }
    registry = {
        "sessions": [
            {
                "session_id": "registry-summary",
                "session_label": f"2026-06-02__001__{forbidden}",
                "session_title": forbidden,
                "path": str(session_with_registry),
                "transcript_path": f"/tmp/{forbidden}.jsonl",
                "updated_at": "2026-06-02T00:00:00Z",
                "archive_status": "indexed",
                "event_count": 2,
                "segment_count": 1,
                "raw": {"path": f"/tmp/{forbidden}/session.raw.jsonl"},
                "token_accounting": provider_summary,
            },
            {
                "session_id": "index-summary",
                "session_label": "2026-06-03__002__index",
                "path": str(session_with_index),
                "updated_at": "2026-06-03T00:00:00Z",
                "archive_status": "indexed",
                "event_count": 1,
                "segment_count": 1,
            },
            {
                "session_id": "outside-root",
                "session_label": "2026-06-04__003__outside",
                "path": str(tmp_path / "outside"),
                "updated_at": "2026-06-04T00:00:00Z",
            },
            {
                "session_id": "missing-path",
                "session_label": "2026-06-05__004__missing",
                "updated_at": "2026-06-05T00:00:00Z",
            },
        ]
    }
    (aoa_root / "session-registry.json").write_text(json.dumps(registry), encoding="utf-8")
    (session_with_index / "session.index.json").write_text(json.dumps({"token_accounting": estimated_summary}), encoding="utf-8")
    read_paths: list[Path] = []
    writes: list[tuple[Path, Path, str]] = []

    def read_json(path: Path) -> tuple[Any, str | None]:
        read_paths.append(path)
        try:
            return json.loads(path.read_text(encoding="utf-8")), None
        except FileNotFoundError:
            return None, "missing"

    def is_relative(path: Path, root: Path) -> bool:
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except (OSError, ValueError):
            return False

    def write_latest_history(data: dict[str, Any], latest_path: Path, history_root: Path) -> list[dict[str, Any]]:
        writes.append((latest_path, history_root, data["schema"]))
        return []

    result = ai_runtime_adapters.token_accounting_aoa_summary_readmodel(
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: STAMP,
        aoa_root=aoa_root,
        target="all",
        since=None,
        since_days=None,
        until=None,
        limit=None,
        write_latest=True,
        latest_path=tmp_path / "latest.json",
        history_root=tmp_path / "history",
        read_json=read_json,
        sha256_path=lambda path: "sha256-fixture",
        write_latest_history=write_latest_history,
        is_relative_to_path=is_relative,
    )

    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True)
    assert result["ok"] is True
    assert result["summary"]["selected_sessions"] == 4
    assert result["summary"]["generated_token_accounting_sessions"] == 2
    assert result["summary"]["missing_generated_token_accounting"] == 2
    assert result["summary"]["source_counts"] == {"missing": 2, "session_index": 1, "session_registry": 1}
    assert result["aggregate"]["totals_by_basis"]["provider_reported"]["total_tokens"] == 5
    assert result["aggregate"]["totals_by_basis"]["estimated"]["total_tokens"] == 9
    assert result["source_refs"]["session_registry_sha256"] == "sha256-fixture"
    assert forbidden not in encoded
    assert f"/tmp/{forbidden}.jsonl" not in encoded
    assert "session.raw.jsonl" not in encoded
    assert writes == [
        (tmp_path / "latest.json", tmp_path / "history", "abyss_machine_ai_token_accounting_aoa_session_memory_summary_v1")
    ]
    assert session_with_registry / "session.manifest.json" not in read_paths
    assert session_with_index / "session.manifest.json" in read_paths
    assert session_with_index / "session.index.json" in read_paths


def test_cli_token_accounting_aoa_summary_delegates_filesystem_route_to_adapter(monkeypatch, tmp_path: Path) -> None:
    from abyss_machine import cli

    calls: dict[str, Any] = {}

    def fake_summary(**kwargs: Any) -> dict[str, Any]:
        calls.update(kwargs)
        return {"ok": True, "schema": "adapter"}

    monkeypatch.setattr(cli.ai_runtime_adapters, "token_accounting_aoa_summary_readmodel", fake_summary)
    result = cli.ai_token_accounting_aoa_summary(
        aoa_root=tmp_path / ".aoa",
        target="latest",
        since="2026-06-01",
        since_days=None,
        until="2026-06-29",
        limit=3,
        write_latest=False,
    )

    assert result == {"ok": True, "schema": "adapter"}
    assert calls["aoa_root"] == tmp_path / ".aoa"
    assert calls["target"] == "latest"
    assert calls["since"] == "2026-06-01"
    assert calls["since_days"] is None
    assert calls["until"] == "2026-06-29"
    assert calls["limit"] == 3
    assert calls["write_latest"] is False
    assert calls["read_json"] is cli.load_json_document
    assert calls["sha256_path"] is cli.sha256_path
    assert calls["write_latest_history"] is cli.write_latest_and_history
    assert calls["is_relative_to_path"] is cli.is_relative_to_path


def test_llm_registry_readmodel_uses_fake_runtime_profile_and_store_ports(tmp_path: Path) -> None:
    config = {
        "backend": "llama.cpp",
        "runtime": {"name": "base"},
        "families": {
            "gemma4": {
                "status": "candidate",
                "provider": "google",
                "runtime": {"name": "family"},
                "profiles": {
                    "spark": {"runtime": {"name": "spark"}, "local_path": "/srv/abyss-machine/cache/ai/gemma-e2b.gguf"},
                    "workhorse": {"local_path": "/srv/abyss-machine/cache/ai/gemma-e4b.gguf"},
                },
            }
        },
    }
    runtime_calls: list[dict[str, Any] | None] = []
    profile_calls: list[tuple[str, str, str]] = []
    writes: list[tuple[Path, str, int]] = []
    appends: list[tuple[Path, str, int]] = []

    def runtime_status(config_arg: dict[str, Any], runtime_override: dict[str, Any] | None = None) -> dict[str, Any]:
        assert config_arg["backend"] == "llama.cpp"
        runtime_calls.append(runtime_override)
        name = (runtime_override or config_arg["runtime"])["name"]
        return {"ok": True, "name": name}

    def profile_status(family_name: str, profile_name: str, profile: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
        profile_calls.append((family_name, profile_name, runtime["name"]))
        return {
            "status": "ready",
            "family": family_name,
            "profile": profile_name,
            "local_path": profile["local_path"],
            "local_exists": True,
            "storage": {"under_host_cache": True, "protection": {"decision": "allow"}},
        }

    def write_json(path: Path, data: dict[str, Any], mode: int) -> None:
        writes.append((path, data["schema"], mode))
        return None

    def append_jsonl(path: Path, data: dict[str, Any], mode: int) -> None:
        appends.append((path, data["schema"], mode))
        return None

    data = ai_runtime_adapters.llm_registry_readmodel(
        config=config,
        runtime_status=runtime_status,
        profile_status=profile_status,
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: STAMP,
        registry_latest_path=tmp_path / "registry.json",
        registry_daily_path=tmp_path / "registry.jsonl",
        validate_latest_path=tmp_path / "validate.json",
        write_latest=True,
        write_json=write_json,
        append_jsonl=append_jsonl,
    )

    assert data["schema"] == "abyss_machine_ai_llm_registry_v1"
    assert data["summary"]["ready_profiles"] == 2
    assert data["families"]["gemma4"]["runtime"]["name"] == "family"
    assert data["profiles"]["gemma4.spark"]["status"] == "ready"
    assert runtime_calls == [None, {"name": "family"}, {"name": "spark"}]
    assert profile_calls == [("gemma4", "spark", "spark"), ("gemma4", "workhorse", "family")]
    assert writes == [(tmp_path / "registry.json", "abyss_machine_ai_llm_registry_v1", 0o664)]
    assert appends == [(tmp_path / "registry.jsonl", "abyss_machine_ai_llm_registry_v1", 0o664)]


def test_llm_latest_and_validate_readmodels_use_fake_store_ports(tmp_path: Path) -> None:
    writes: list[tuple[Path, str, int]] = []
    latest_path = tmp_path / "registry.json"
    validate_path = tmp_path / "validate.json"
    registry = {
        "schema": "abyss_machine_ai_llm_registry_v1",
        "ok": True,
        "runtime": {"ok": True},
        "summary": {"ready_profiles": 1},
        "profiles": {
            "gemma4.spark": {
                "status": "ready",
                "local_exists": True,
                "local_path": "/srv/abyss-machine/cache/ai/gemma-e2b.gguf",
                "storage": {"under_host_cache": True, "protection": {"decision": "allow"}},
            }
        },
    }

    latest = ai_runtime_adapters.llm_latest_readmodel(
        latest_path=latest_path,
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: STAMP,
        read_json=lambda path: (registry if path == latest_path else None, None),
    )

    def write_json(path: Path, data: dict[str, Any], mode: int) -> None:
        writes.append((path, data["schema"], mode))
        return None

    validate = ai_runtime_adapters.llm_validate_readmodel(
        base_checks=[{"level": "ok", "key": "fixture", "message": "fixture base check"}],
        registry=registry,
        token_profiles={"summary": {"exact_ready_profiles": 1}},
        config={
            "families": {
                "gemma4": {
                    "profiles": {
                        "spark": {"local_path": "/srv/abyss-machine/cache/ai/gemma-e2b.gguf"}
                    }
                }
            }
        },
        protected_roots=["/srv/AbyssOS/abyss-stack", "/work"],
        paths={"schema": "abyss_machine_ai_llm_paths_v1"},
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: STAMP,
        write_latest=True,
        latest_path=validate_path,
        write_json=write_json,
    )

    assert latest["read_at"] == STAMP
    assert validate["schema"] == "abyss_machine_ai_llm_validate_v1"
    assert validate["ok"] is True
    assert validate["summary"] == {"fails": 0, "warnings": 0, "checks": 7, "profiles": 1, "ready_profiles": 1}
    assert [item["key"] for item in validate["checks"]] == [
        "fixture",
        "runtime",
        "profiles_configured",
        "token_accounting_profiles",
        "profile_models",
        "storage_routes",
        "protected_roots",
    ]
    assert writes == [(validate_path, "abyss_machine_ai_llm_validate_v1", 0o664)]


def test_cli_model_inventory_wrapper_binds_adapter_without_writing(monkeypatch) -> None:
    from abyss_machine import cli

    calls: dict[str, Any] = {}

    def fake_models_inventory_readmodel(**kwargs: Any) -> dict[str, Any]:
        calls.update(kwargs)
        return {"ok": True, "summary": {"entries": 0}}

    monkeypatch.setattr(cli, "ai_config", lambda: {"model_roots": []})
    monkeypatch.setattr(cli, "now_iso", lambda: STAMP)
    monkeypatch.setattr(cli.ai_runtime_adapters, "models_inventory_readmodel", fake_models_inventory_readmodel)

    assert cli.ai_models_inventory(write_latest=False) == {"ok": True, "summary": {"entries": 0}}
    assert calls["config"] == {"model_roots": []}
    assert calls["schema_prefix"] == cli.SCHEMA_PREFIX
    assert calls["now_iso"] is cli.now_iso
    assert calls["write_latest"] is False
    assert calls["latest_path"] == cli.AI_MODELS_LATEST_PATH


def test_cli_openvino_runner_wrappers_bind_adapter_ports(monkeypatch, tmp_path: Path) -> None:
    from abyss_machine import cli

    calls: dict[str, dict[str, Any]] = {}
    embedding_model = tmp_path / "embedding"
    text_model = tmp_path / "text"
    config = {
        "openvino": {"python": "/config/python"},
        "eval": {
            "embedding_model": str(embedding_model),
            "embedding_device": "CPU",
            "text_model": str(text_model),
            "text_device": "NPU",
            "text_prompt": "Answer with one token",
            "timeout_sec": 17,
        },
    }

    def fake_smoke(**kwargs: Any) -> dict[str, Any]:
        calls["smoke"] = kwargs
        return {"device": kwargs["device"], "ok": True}

    def fake_embedding(**kwargs: Any) -> dict[str, Any]:
        calls["embedding"] = kwargs
        return {"suite": "embeddings", "ok": True}

    def fake_text(**kwargs: Any) -> dict[str, Any]:
        calls["text"] = kwargs
        return {"suite": "text", "ok": True}

    monkeypatch.setattr(cli, "ai_config", lambda: config)
    monkeypatch.setattr(cli.shutil, "which", lambda name: "/which/python" if name == "abyss-openvino-python" else None)
    monkeypatch.setattr(cli, "ai_subprocess_env", lambda extra=None: {"ENV": "1"})
    monkeypatch.setattr(cli, "ai_openvino_cache_dir", lambda label="general": tmp_path / "cache" / str(label))
    monkeypatch.setattr(cli.ai_runtime_adapters, "openvino_smoke_device", fake_smoke)
    monkeypatch.setattr(cli.ai_runtime_adapters, "openvino_embedding_eval", fake_embedding)
    monkeypatch.setattr(cli.ai_runtime_adapters, "openvino_text_eval", fake_text)

    assert cli.ai_openvino_smoke_device("CPU", 3) == {"device": "CPU", "ok": True}
    assert cli.ai_eval_embeddings() == {"suite": "embeddings", "ok": True}
    assert cli.ai_eval_text() == {"suite": "text", "ok": True}

    assert calls["smoke"]["python"] == "/which/python"
    assert calls["smoke"]["timeout_sec"] == 3
    assert calls["smoke"]["run_command"] is cli.run
    assert calls["smoke"]["resource_snapshot"] is cli.ai_resource_snapshot
    assert calls["smoke"]["resource_profile"] is cli.ai_resource_profile
    assert calls["embedding"]["model_dir"] == embedding_model
    assert calls["embedding"]["device"] == "CPU"
    assert calls["embedding"]["cache_dir"] == cli.ai_openvino_cache_dir(cli.ai_model_cache_label(embedding_model, "embedding"))
    assert calls["embedding"]["timeout_sec"] == 17.0
    assert calls["embedding"]["subprocess_env"] == {"ENV": "1"}
    assert calls["text"]["model_dir"] == text_model
    assert calls["text"]["device"] == "NPU"
    assert calls["text"]["cache_dir"] == cli.ai_openvino_cache_dir(cli.ai_model_cache_label(text_model, "text"))
    assert calls["text"]["prompt"] == "Answer with one token"

from __future__ import annotations

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


def test_cli_llm_resident_command_delegates_to_runner(monkeypatch, capsys) -> None:
    from abyss_machine import cli

    calls: dict[str, Any] = {}

    def fake_controller_run(**kwargs: Any) -> dict[str, Any]:
        calls.update(kwargs)
        return {"returncode": 0, "stdout": '{"ok": true, "source": "adapter"}\n', "stderr": ""}

    monkeypatch.setattr(cli.ai_runtime_adapters, "llm_resident_controller_run", fake_controller_run)

    rc = cli.main(["ai", "llm", "resident", "jobs", "run", "--limit", "2", "--json"])
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.out == '{"ok": true, "source": "adapter"}\n'
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
        return {"returncode": 0, "stdout": '{"ok": true, "source": "workhorse"}\n', "stderr": ""}

    monkeypatch.setattr(cli.ai_runtime_adapters, "llm_workhorse_controller_run", fake_controller_run)

    rc = cli.main(["ai", "llm", "workhorse", "review", "--run-model", "--timeout", "7", "--json"])
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.out == '{"ok": true, "source": "workhorse"}\n'
    assert calls["controller"] == cli.AI_LLM_WORKHORSE_CONTROLLER
    assert calls["command"] == "review"
    assert calls["limit"] == 24
    assert calls["refresh_candidates"] is False
    assert calls["run_model"] is True
    assert calls["n_predict"] == 768
    assert calls["timeout"] == 7.0
    assert calls["json_output"] is True
    assert calls["run_command"] is cli.run


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

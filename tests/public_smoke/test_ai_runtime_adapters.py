from __future__ import annotations

from pathlib import Path
import stat
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import ai_runtime_adapters


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


def test_cli_model_inventory_wrapper_binds_adapter_without_writing(monkeypatch) -> None:
    from abyss_machine import cli

    calls: dict[str, Any] = {}

    def fake_models_inventory(**kwargs: Any) -> dict[str, Any]:
        calls.update(kwargs)
        return {"ok": True, "summary": {"entries": 0}}

    monkeypatch.setattr(cli, "ai_config", lambda: {"model_roots": []})
    monkeypatch.setattr(cli, "now_iso", lambda: STAMP)
    monkeypatch.setattr(cli.ai_runtime_adapters, "models_inventory", fake_models_inventory)

    assert cli.ai_models_inventory(write_latest=False) == {"ok": True, "summary": {"entries": 0}}
    assert calls["config"] == {"model_roots": []}
    assert calls["schema_prefix"] == cli.SCHEMA_PREFIX
    assert calls["generated_at"] == STAMP


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

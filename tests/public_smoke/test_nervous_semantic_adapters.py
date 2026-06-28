from __future__ import annotations

import array
import base64
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli
from abyss_machine import nervous_semantic_adapters


def test_embedding_adapter_returns_empty_without_runtime_calls(tmp_path: Path) -> None:
    called: list[str] = []

    def forbidden(*_args: object, **_kwargs: object):
        called.append("called")
        return {}

    data = nervous_semantic_adapters.embed_texts_with_subprocess(
        [],
        embedding={},
        model_dir=tmp_path / "missing-model",
        device="CPU",
        cache_dir=tmp_path / "cache",
        python="/missing/python",
        tmp_root=tmp_path / "tmp",
        run_command=forbidden,
        env=None,
        resource_snapshot=forbidden,
        resource_profile=forbidden,
    )

    assert data == {"ok": True, "vectors": {}, "summary": {"items": 0}}
    assert called == []


def test_embedding_adapter_reports_missing_runtime_before_tmp_files(tmp_path: Path) -> None:
    called: list[str] = []

    def forbidden(*_args: object, **_kwargs: object):
        called.append("called")
        return {}

    data = nervous_semantic_adapters.embed_texts_with_subprocess(
        [{"id": "query", "text": "thermal route"}],
        embedding={},
        model_dir=tmp_path / "missing-model",
        device="CPU",
        cache_dir=tmp_path / "cache",
        python="/missing/python",
        tmp_root=tmp_path / "tmp",
        run_command=forbidden,
        env=None,
        resource_snapshot=forbidden,
        resource_profile=forbidden,
    )

    assert data["ok"] is False
    assert "embedding model directory missing" in data["error"]
    assert not (tmp_path / "tmp").exists()
    assert called == []


def test_embedding_adapter_reports_missing_python_before_tmp_files(tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    called: list[str] = []

    def forbidden(*_args: object, **_kwargs: object):
        called.append("called")
        return {}

    data = nervous_semantic_adapters.embed_texts_with_subprocess(
        [{"id": "query", "text": "thermal route"}],
        embedding={},
        model_dir=model_dir,
        device="CPU",
        cache_dir=tmp_path / "cache",
        python="/missing/python",
        tmp_root=tmp_path / "tmp",
        run_command=forbidden,
        env=None,
        resource_snapshot=forbidden,
        resource_profile=forbidden,
    )

    assert data == {"ok": False, "error": "abyss-openvino-python not found"}
    assert not (tmp_path / "tmp").exists()
    assert called == []


def test_embedding_adapter_runs_subprocess_and_cleans_public_safe_files(tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    python = tmp_path / "python"
    python.write_text("#!/bin/sh\n", encoding="utf-8")
    cache_dir = tmp_path / "cache"
    tmp_root = tmp_path / "tmp"
    vector = array.array("f", [1.0, 0.0])
    snapshots = [{"mem": "before"}, {"mem": "after"}]
    calls: list[dict[str, object]] = []
    env = {"ABYSS_TEST_ENV": "1"}

    def fake_snapshot() -> dict[str, object]:
        return snapshots.pop(0)

    def fake_profile(before: dict[str, object], after: dict[str, object], scope: str, description: str) -> dict[str, object]:
        return {"before": before, "after": after, "scope": scope, "description": description}

    def fake_run(command: list[str], timeout: float, run_env: dict[str, str] | None) -> dict[str, object]:
        input_path = Path(command[3])
        output_path = Path(command[4])
        calls.append({"command": command, "timeout": timeout, "env": run_env, "input_exists": input_path.exists()})
        assert input_path.read_text(encoding="utf-8") == '{"id": "query", "text": "thermal route"}\n'
        output_path.write_text(
            json.dumps(
                {
                    "id": "query",
                    "dim": 2,
                    "vector_b64": base64.b64encode(vector.tobytes()).decode("ascii"),
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return {"stdout": '{"ok":true,"items":1,"vectors":1,"dim":2}', "stderr": "runtime warning", "returncode": 0}

    data = nervous_semantic_adapters.embed_texts_with_subprocess(
        [{"id": "query", "text": "thermal route"}],
        embedding={"batch_size": 2, "max_tokens": 64, "timeout_sec": 12.5, "pooling": "mean", "padding_side": "right"},
        model_dir=model_dir,
        device="CPU",
        cache_dir=cache_dir,
        python=str(python),
        tmp_root=tmp_root,
        run_command=fake_run,
        env=env,
        resource_snapshot=fake_snapshot,
        resource_profile=fake_profile,
    )

    assert data["ok"] is True
    assert data["stderr_tail"] == "runtime warning"
    assert data["resource_profile"]["scope"] == "child_process"
    assert data["vectors"]["query"]["blob"] == vector.tobytes()
    assert calls[0]["timeout"] == 12.5
    assert calls[0]["env"] == env
    command = calls[0]["command"]
    assert command[:3] == [str(python), "-c", command[2]]
    assert command[-7:] == [str(model_dir), "CPU", str(cache_dir), "2", "64", "mean", "right"]
    assert not list(tmp_root.glob("embed-*.jsonl"))


def test_cli_nervous_semantic_embed_texts_binds_live_adapter(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    model_dir = tmp_path / "model"
    cache_dir = tmp_path / "cache"

    monkeypatch.setattr(cli, "nervous_semantic_model_paths", lambda embedding: (model_dir, "CPU", cache_dir, None))
    monkeypatch.setattr(cli, "ai_config", lambda: {"openvino": {"python": "/unused"}})
    monkeypatch.setattr(cli.shutil, "which", lambda name: "/usr/bin/abyss-openvino-python" if name == "abyss-openvino-python" else None)
    monkeypatch.setattr(cli, "ai_subprocess_env", lambda: {"ENV": "1"})
    monkeypatch.setattr(cli, "ai_resource_snapshot", lambda: {"snapshot": True})
    monkeypatch.setattr(
        cli,
        "ai_resource_profile",
        lambda before, after, scope, description: {"before": before, "after": after, "scope": scope, "description": description},
    )

    def fake_adapter(text_items: list[dict[str, str]], **kwargs: object) -> dict[str, object]:
        captured["text_items"] = text_items
        captured.update(kwargs)
        return {"ok": True, "vectors": {}}

    monkeypatch.setattr(nervous_semantic_adapters, "embed_texts_with_subprocess", fake_adapter)

    data = cli.nervous_semantic_embed_texts([{"id": "query", "text": "thermal route"}], {"batch_size": 3})

    assert data["ok"] is True
    assert captured["text_items"] == [{"id": "query", "text": "thermal route"}]
    assert captured["embedding"] == {"batch_size": 3}
    assert captured["model_dir"] == model_dir
    assert captured["device"] == "CPU"
    assert captured["cache_dir"] == cache_dir
    assert captured["python"] == "/usr/bin/abyss-openvino-python"
    assert captured["tmp_root"] == cli.ABYSS_MACHINE_TMP_ROOT / "nervous" / "semantic"
    assert captured["run_command"] is cli.run
    assert captured["env"] == {"ENV": "1"}
    assert captured["resource_snapshot"] is cli.ai_resource_snapshot
    assert captured["resource_profile"] is cli.ai_resource_profile

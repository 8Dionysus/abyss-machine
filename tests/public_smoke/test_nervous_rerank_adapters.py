from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli
from abyss_machine import nervous_rerank_adapters


def _forbidden(*_args: object, **_kwargs: object):
    raise AssertionError("runtime dependency should not be called")


def _ready_runtime(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    scorer = tmp_path / "score.py"
    scorer.write_text("# scorer\n", encoding="utf-8")
    python = tmp_path / "python"
    python.write_text("#!/bin/sh\n", encoding="utf-8")
    cache_dir = tmp_path / "cache"
    return model_dir, scorer, python, cache_dir


def test_rerank_adapter_returns_disabled_without_runtime_calls(tmp_path: Path) -> None:
    data = nervous_rerank_adapters.score_with_subprocess(
        "thermal",
        [{"chunk_id": "a", "title": "Thermal"}],
        config={"enabled": False},
        model_dir=tmp_path / "missing-model",
        scorer=tmp_path / "missing-scorer",
        python="/missing/python",
        tmp_root=tmp_path / "tmp",
        run_command=_forbidden,
        env=None,
        resource_snapshot=_forbidden,
        resource_profile=_forbidden,
        policy_gate=_forbidden,
        cache_dir=tmp_path / "cache",
    )

    assert data == {"ok": False, "skipped": True, "reason": "neural rerank disabled"}
    assert not (tmp_path / "tmp").exists()


def test_rerank_adapter_reports_missing_runtime_before_policy_or_tmp(tmp_path: Path) -> None:
    data = nervous_rerank_adapters.score_with_subprocess(
        "thermal",
        [{"chunk_id": "a", "title": "Thermal"}],
        config={"enabled": True},
        model_dir=tmp_path / "missing-model",
        scorer=tmp_path / "missing-scorer",
        python="/missing/python",
        tmp_root=tmp_path / "tmp",
        run_command=_forbidden,
        env=None,
        resource_snapshot=_forbidden,
        resource_profile=_forbidden,
        policy_gate=_forbidden,
        cache_dir=tmp_path / "cache",
    )

    assert data["ok"] is False
    assert "neural reranker model missing" in data["error"]
    assert not (tmp_path / "tmp").exists()


def test_rerank_adapter_reports_policy_denial_before_scoring_docs(tmp_path: Path) -> None:
    model_dir, scorer, python, cache_dir = _ready_runtime(tmp_path)

    data = nervous_rerank_adapters.score_with_subprocess(
        "thermal",
        [{"chunk_id": "a", "title": "Thermal"}],
        config={"enabled": True},
        model_dir=model_dir,
        scorer=scorer,
        python=str(python),
        tmp_root=tmp_path / "tmp",
        run_command=_forbidden,
        env=None,
        resource_snapshot=_forbidden,
        resource_profile=_forbidden,
        policy_gate=lambda: {"ok": False, "reason": "pressure"},
        cache_dir=cache_dir,
    )

    assert data == {
        "ok": False,
        "policy_denied": True,
        "error": "host AI policy denied neural rerank",
        "policy_gate": {"ok": False, "reason": "pressure"},
    }
    assert not (tmp_path / "tmp").exists()


def test_rerank_adapter_runs_scorer_and_keeps_debug_paths(tmp_path: Path) -> None:
    model_dir, scorer, python, cache_dir = _ready_runtime(tmp_path)
    tmp_root = tmp_path / "tmp"
    env = {"ABYSS_TEST_ENV": "1"}
    snapshots = [{"rss": "before"}, {"rss": "after"}]
    calls: list[dict[str, object]] = []

    def fake_snapshot() -> dict[str, object]:
        return snapshots.pop(0)

    def fake_profile(before: dict[str, object], after: dict[str, object], scope: str, description: str) -> dict[str, object]:
        return {"before": before, "after": after, "scope": scope, "description": description}

    def fake_run(command: list[str], timeout: float, run_env: dict[str, str] | None) -> dict[str, object]:
        input_path = Path(command[-3])
        output_path = Path(command[-1])
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        calls.append({"command": command, "timeout": timeout, "env": run_env, "payload": payload})
        output_path.write_text(json.dumps({"ok": True, "scores": [{"id": "host-1", "score": 0.9}]}) + "\n", encoding="utf-8")
        return {"stdout": "noise\n{\"ok\": true, \"scores\": [{\"id\": \"host-1\", \"score\": 0.8}]}", "stderr": "runtime warning", "returncode": 0}

    data = nervous_rerank_adapters.score_with_subprocess(
        "thermal",
        [{"chunk_id": "host-1", "source_id": "abyss_machine_facts", "title": "Thermal", "snippet": "warm state"}],
        config={
            "enabled": True,
            "device": "CPU",
            "max_length": 128,
            "batch_size": 2,
            "timeout_sec": 12,
            "instruction": "rank local evidence",
        },
        model_dir=model_dir,
        scorer=scorer,
        python=str(python),
        tmp_root=tmp_root,
        run_command=fake_run,
        env=env,
        resource_snapshot=fake_snapshot,
        resource_profile=fake_profile,
        policy_gate=lambda: {"ok": True, "decision": "allow"},
        cache_dir=cache_dir,
        time_ns=lambda: 123,
    )

    assert data["ok"] is True
    assert data["scores"] == [{"id": "host-1", "score": 0.8}]
    assert data["stderr_tail"] == "runtime warning"
    assert data["policy_gate"] == {"ok": True, "decision": "allow"}
    assert data["resource_profile"]["scope"] == "child_process"
    assert calls[0]["timeout"] == 12.0
    assert calls[0]["env"] == env
    assert calls[0]["payload"]["query"] == "thermal"
    assert calls[0]["payload"]["instruction"] == "rank local evidence"
    assert calls[0]["payload"]["documents"] == [{"id": "host-1", "text": "Source: abyss_machine_facts\nTitle: Thermal\nwarm state"}]
    command = calls[0]["command"]
    assert command[:8] == [str(python), str(scorer), "--model-dir", str(model_dir), "--device", "CPU", "--cache-dir", str(cache_dir)]
    assert Path(data["input_path"]).exists()
    assert Path(data["output_path"]).exists()


def test_rerank_adapter_falls_back_to_output_json(tmp_path: Path) -> None:
    model_dir, scorer, python, cache_dir = _ready_runtime(tmp_path)

    def fake_run(command: list[str], _timeout: float, _run_env: dict[str, str] | None) -> dict[str, object]:
        Path(command[-1]).write_text(json.dumps({"ok": True, "scores": [{"id": "host-1", "score": 0.7}]}) + "\n", encoding="utf-8")
        return {"stdout": "not json", "stderr": "", "returncode": 0}

    data = nervous_rerank_adapters.score_with_subprocess(
        "thermal",
        [{"chunk_id": "host-1", "title": "Thermal"}],
        config={"enabled": True},
        model_dir=model_dir,
        scorer=scorer,
        python=str(python),
        tmp_root=tmp_path / "tmp",
        run_command=fake_run,
        env=None,
        resource_snapshot=lambda: {},
        resource_profile=lambda _before, _after, scope, description: {"scope": scope, "description": description},
        policy_gate=lambda: {"ok": True},
        cache_dir=cache_dir,
    )

    assert data["ok"] is True
    assert data["scores"] == [{"id": "host-1", "score": 0.7}]


def test_cli_neural_rerank_scores_binds_live_adapter(monkeypatch, tmp_path: Path) -> None:
    model_dir, scorer, python, cache_dir = _ready_runtime(tmp_path)
    captured: dict[str, object] = {}

    monkeypatch.setattr(cli.shutil, "which", lambda name: str(python) if name == "abyss-openvino-python" else None)
    monkeypatch.setattr(cli, "ai_config", lambda: {"openvino": {"python": "/unused"}})
    monkeypatch.setattr(cli, "ai_subprocess_env", lambda: {"ENV": "1"})
    monkeypatch.setattr(cli, "ai_resource_snapshot", lambda: {"snapshot": True})
    monkeypatch.setattr(
        cli,
        "ai_resource_profile",
        lambda before, after, scope, description: {"before": before, "after": after, "scope": scope, "description": description},
    )
    monkeypatch.setattr(cli, "ai_policy_gate_for_class", lambda resource_class, label, force=False: {"ok": True, "resource_class": resource_class, "label": label, "force": force})

    def fake_adapter(query: str, items: list[dict[str, object]], **kwargs: object) -> dict[str, object]:
        captured["query"] = query
        captured["items"] = items
        captured.update(kwargs)
        policy_gate = kwargs["policy_gate"]
        captured["policy_gate_result"] = policy_gate()
        return {"ok": True, "scores": []}

    monkeypatch.setattr(nervous_rerank_adapters, "score_with_subprocess", fake_adapter)

    data = cli.nervous_neural_rerank_scores(
        "thermal",
        [{"chunk_id": "host-1", "title": "Thermal"}],
        {
            "enabled": True,
            "model_dir": str(model_dir),
            "scorer": str(scorer),
            "cache_dir": str(cache_dir),
            "resource_class": "heavy",
        },
        force_policy=True,
    )

    assert data["ok"] is True
    assert captured["query"] == "thermal"
    assert captured["items"] == [{"chunk_id": "host-1", "title": "Thermal"}]
    assert captured["model_dir"] == model_dir
    assert captured["scorer"] == scorer
    assert captured["python"] == str(python)
    assert captured["cache_dir"] == cache_dir
    assert captured["tmp_root"] == cli.ABYSS_MACHINE_TMP_ROOT / "nervous" / "rerank" / "neural"
    assert captured["run_command"] is cli.run
    assert captured["env"] == {"ENV": "1"}
    assert captured["resource_snapshot"] is cli.ai_resource_snapshot
    assert captured["resource_profile"] is cli.ai_resource_profile
    assert captured["policy_gate_result"] == {"ok": True, "resource_class": "heavy", "label": "nervous neural-rerank", "force": True}

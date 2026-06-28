from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli
from abyss_machine import dictation_docs_adapters


def _paths(tmp_path: Path) -> dictation_docs_adapters.DictationDocsPaths:
    runtime = tmp_path / "runtime"
    return dictation_docs_adapters.DictationDocsPaths(
        root=tmp_path / "var" / "lib" / "abyss-machine" / "dictation",
        agent_entrypoint=tmp_path / "var" / "lib" / "abyss-machine" / "dictation" / "AGENTS.md",
        index=tmp_path / "var" / "lib" / "abyss-machine" / "dictation" / "index.json",
        config=tmp_path / "etc" / "abyss-machine" / "dictation" / "config.json",
        replacements=tmp_path / "etc" / "abyss-machine" / "dictation" / "replacements.json",
        helper=tmp_path / "bin" / "dictation-helper",
        server=tmp_path / "bin" / "dictation-server",
        runtime_dir=runtime,
        server_audio_dir=runtime / "server-audio",
        transcript_root=tmp_path / "var" / "lib" / "abyss-machine" / "dictation" / "transcripts",
        transcript_jsonl_root=tmp_path / "var" / "lib" / "abyss-machine" / "dictation" / "transcripts" / "jsonl",
        transcript_readable_root=tmp_path / "var" / "lib" / "abyss-machine" / "dictation" / "transcripts" / "readable",
        transcript_latest=tmp_path / "var" / "lib" / "abyss-machine" / "dictation" / "transcripts" / "latest.json",
        today_jsonl=tmp_path / "var" / "lib" / "abyss-machine" / "dictation" / "transcripts" / "jsonl" / "2026" / "06" / "2026-06-28.jsonl",
        today_markdown=tmp_path / "var" / "lib" / "abyss-machine" / "dictation" / "transcripts" / "readable" / "2026" / "06" / "2026-06-28.md",
        validate_latest=tmp_path / "var" / "lib" / "abyss-machine" / "dictation" / "validate" / "latest.json",
    )


def test_today_path_uses_injected_clock(tmp_path: Path) -> None:
    path = dictation_docs_adapters.today_path(
        tmp_path / "root",
        ".jsonl",
        now_datetime=lambda: dt.datetime(2026, 6, 28, 12, 0, tzinfo=dt.timezone.utc),
    )

    assert path == tmp_path / "root" / "2026" / "06" / "2026-06-28.jsonl"


def test_docs_paths_and_index_documents_are_stable(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    paths_doc = dictation_docs_adapters.paths_document(
        paths,
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:00+00:00",
    )
    index_doc = dictation_docs_adapters.index_document(
        paths,
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:00+00:00",
    )
    agents = dictation_docs_adapters.agents_doc(paths)

    assert paths_doc["schema"] == "abyss_machine_dictation_paths_v1"
    assert paths_doc["runtime_dir"] == str(paths.runtime_dir)
    assert paths_doc["transcripts"]["today_jsonl"] == str(paths.today_jsonl)
    assert index_doc["schema"] == "abyss_machine_dictation_index_v1"
    assert index_doc["commands"]["validate"] == ["abyss-machine", "dictation", "validate", "--json"]
    assert str(paths.config) in agents
    assert str(paths.server_audio_dir) in agents


def test_ensure_docs_writes_agents_and_index_under_tmp_path(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    errors = dictation_docs_adapters.ensure_docs(
        paths,
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:00+00:00",
    )

    assert errors == []
    assert paths.agent_entrypoint.exists()
    assert paths.index.exists()
    assert "Abyss Machine Dictation" in paths.agent_entrypoint.read_text(encoding="utf-8")
    index = json.loads(paths.index.read_text(encoding="utf-8"))
    assert index["schema"] == "abyss_machine_dictation_index_v1"
    assert index["paths"]["agent_entrypoint"] == str(paths.agent_entrypoint)


def test_ensure_docs_uses_fakeable_ports(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    calls: dict[str, object] = {"dirs": [], "appends": [], "texts": [], "json": []}

    def ensure_dir(path: Path) -> None:
        calls["dirs"].append(path)
        return None

    def append_text(path: Path, text: str, mode: int) -> None:
        calls["appends"].append((path, text, mode))
        return None

    def write_text(path: Path, text: str, mode: int) -> None:
        calls["texts"].append((path, text, mode))
        return None

    def write_json(path: Path, data: dict[str, object], mode: int) -> None:
        calls["json"].append((path, data, mode))
        return None

    errors = dictation_docs_adapters.ensure_docs(
        paths,
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:00+00:00",
        ensure_dir=ensure_dir,
        append_text=append_text,
        write_text=write_text,
        write_json=write_json,
        read_text_fn=lambda path: "old",
        path_exists=lambda path: True,
    )

    assert errors == []
    assert calls["dirs"] == [paths.root, paths.transcript_root, paths.transcript_jsonl_root, paths.transcript_readable_root]
    assert calls["appends"] == [(paths.agent_entrypoint, "", 0o664)]
    assert calls["texts"][0][0] == paths.agent_entrypoint
    assert calls["json"][0][0] == paths.index
    assert calls["json"][0][1]["schema"] == "abyss_machine_dictation_index_v1"


def test_cli_dictation_docs_wrappers_bind_docs_adapter(monkeypatch, tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    captured: dict[str, object] = {}

    def fake_paths_document(paths_arg: object, **kwargs: object) -> dict[str, object]:
        captured["paths_document"] = (paths_arg, kwargs)
        return {"schema": "paths"}

    def fake_index_document(paths_arg: object, **kwargs: object) -> dict[str, object]:
        captured["index_document"] = (paths_arg, kwargs)
        return {"schema": "index"}

    def fake_agents_doc(paths_arg: object) -> str:
        captured["agents_doc"] = paths_arg
        return "agents"

    def fake_ensure_docs(paths_arg: object, **kwargs: object) -> list[dict[str, object]]:
        captured["ensure_docs"] = (paths_arg, kwargs)
        return []

    monkeypatch.setattr(cli, "dictation_docs_paths", lambda: paths)
    monkeypatch.setattr(dictation_docs_adapters, "paths_document", fake_paths_document)
    monkeypatch.setattr(dictation_docs_adapters, "index_document", fake_index_document)
    monkeypatch.setattr(dictation_docs_adapters, "agents_doc", fake_agents_doc)
    monkeypatch.setattr(dictation_docs_adapters, "ensure_docs", fake_ensure_docs)

    assert cli.dictation_paths() == {"schema": "paths"}
    assert cli.dictation_index_document() == {"schema": "index"}
    assert cli.dictation_agents_doc() == "agents"
    assert cli.ensure_dictation_docs() == []

    assert captured["paths_document"][0] == paths
    assert captured["paths_document"][1]["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["index_document"][0] == paths
    assert captured["agents_doc"] == paths
    assert captured["ensure_docs"][0] == paths
    assert captured["ensure_docs"][1]["schema_prefix"] == cli.SCHEMA_PREFIX

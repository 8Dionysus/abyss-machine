from __future__ import annotations

import array
import base64
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli
from abyss_machine import nervous_semantic_adapters


def test_semantic_adapter_initializes_db_and_writes_latest_failures(tmp_path: Path) -> None:
    db_path = tmp_path / "semantic" / "semantic.db"
    conn = nervous_semantic_adapters.connect_db(db_path, create=True)
    nervous_semantic_adapters.initialize_db(conn, schema_prefix="abyss_machine", version="test-version")
    conn.commit()
    meta = {row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM meta")}
    conn.close()

    latest_path = tmp_path / "not-a-dir" / "latest.json"
    latest_path.parent.write_text("blocks directory creation", encoding="utf-8")
    latest = nervous_semantic_adapters.write_latest({"ok": True}, latest_path, group="missing-test-group")

    assert meta["schema"] == "abyss_machine_nervous_semantic_index_v1"
    assert meta["tool_version"] == "test-version"
    assert latest["ok"] is False
    assert latest["write_errors"][0]["path"] == str(latest_path)


def test_semantic_adapter_loads_source_chunks_from_lexical_sqlite(tmp_path: Path) -> None:
    source_db = tmp_path / "source.db"
    conn = sqlite3.connect(source_db)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE documents (
          doc_id TEXT PRIMARY KEY,
          generated_at TEXT,
          schema TEXT,
          capture_trigger TEXT,
          source_path TEXT,
          source_line INTEGER
        );
        CREATE TABLE chunks (
          chunk_id TEXT PRIMARY KEY,
          doc_id TEXT,
          source_id TEXT,
          title TEXT,
          body TEXT,
          generated_at TEXT,
          privacy_mode TEXT,
          provenance_json TEXT
        );
        """
    )
    conn.execute(
        "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?)",
        ("doc-a", "2026-06-28T10:00:00+00:00", "abyss_machine_nervous_event_v1", "test", "/var/lib/private.jsonl", 7),
    )
    conn.execute(
        "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "chunk-a",
            "doc-a",
            "nervous_events",
            "Thermal route",
            "zram pressure and thermal routing",
            "2026-06-28T10:00:00+00:00",
            "normal",
            '{"severity":"warn"}',
        ),
    )
    conn.commit()
    conn.close()

    chunks, error = nervous_semantic_adapters.source_chunks(
        source_db,
        max_chunks=4,
        max_input_chars=128,
    )

    assert error is None
    assert len(chunks) == 1
    assert chunks[0]["chunk_id"] == "chunk-a"
    assert chunks[0]["body_sha256"]
    assert chunks[0]["embedding_text"].startswith("Thermal route")
    assert chunks[0]["body_preview"] == "zram pressure and thermal routing"


def test_semantic_adapter_records_successful_build_metadata_and_deletes_stale_vectors(tmp_path: Path) -> None:
    db_path = tmp_path / "semantic.db"
    conn = nervous_semantic_adapters.connect_db(db_path, create=True)
    nervous_semantic_adapters.initialize_db(conn, schema_prefix="abyss_machine", version="test-version")
    conn.commit()
    vector_keep = array.array("f", [1.0, 0.0])
    vector_stale = array.array("f", [0.0, 1.0])
    pending_by_id = {
        "keep": {
            "chunk_id": "keep",
            "doc_id": "doc-keep",
            "source_id": "nervous_events",
            "document_schema": "schema-keep",
            "title": "Keep",
            "body_sha256": "hash-keep",
            "body_preview": "kept evidence",
            "generated_at": "2026-06-28T10:00:00+00:00",
            "document_generated_at": "2026-06-28T10:00:00+00:00",
            "privacy_mode": "normal",
            "provenance_json": '{"event_id":"keep"}',
        },
        "stale": {
            "chunk_id": "stale",
            "doc_id": "doc-stale",
            "source_id": "nervous_events",
            "document_schema": "schema-stale",
            "title": "Stale",
            "body_sha256": "hash-stale",
            "body_preview": "stale evidence",
            "generated_at": "2026-06-28T09:00:00+00:00",
            "document_generated_at": "2026-06-28T09:00:00+00:00",
            "privacy_mode": "normal",
            "provenance_json": '{"event_id":"stale"}',
        },
    }
    inserted = nervous_semantic_adapters.insert_vectors(
        conn,
        {
            "keep": {"dim": 2, "blob": vector_keep.tobytes()},
            "stale": {"dim": 2, "blob": vector_stale.tobytes()},
        },
        pending_by_id,
        "2026-06-28T10:01:00+00:00",
    )

    stale_deleted = nervous_semantic_adapters.finish_successful_build_run(
        conn,
        current_chunk_ids={"keep"},
        partial=False,
        meta_values={
            "run_id": "semantic-run",
            "source_index_run_id": "source-run",
            "built_at": "2026-06-28T10:02:00+00:00",
            "partial": "false",
        },
        run_id="semantic-run",
        started_at="2026-06-28T10:00:00+00:00",
        finished_at="2026-06-28T10:02:00+00:00",
        source_chunks=1,
        pending_chunks=2,
        vectors_indexed=inserted,
        errors={"provenance": {"source_index_run_id": "source-run"}},
    )
    conn.close()
    counts = nervous_semantic_adapters.counts(db_path)

    assert inserted == 2
    assert stale_deleted == 1
    assert counts["vectors"] == 1
    assert counts["build_runs"] == 1
    assert counts["meta"]["run_id"] == "semantic-run"
    assert counts["last_successful_build_run"]["details"]["provenance"]["source_index_run_id"] == "source-run"


def test_cli_nervous_semantic_lifecycle_binds_live_adapter(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    db_path = tmp_path / "semantic.db"
    root = tmp_path / "semantic-root"
    latest_path = tmp_path / "latest.json"
    maintain_latest = tmp_path / "maintain" / "latest.json"
    maintain_root = tmp_path / "maintain"
    source_db = tmp_path / "source.db"
    fake_conn = sqlite3.connect(":memory:")

    @contextmanager
    def fake_lock(path: Path):
        captured["lock_root"] = path
        yield

    def fake_connect(path: Path, create: bool = False):
        captured["connect"] = {"path": path, "create": create}
        return fake_conn

    def fake_initialize(conn: object, **kwargs: object) -> None:
        captured["initialize"] = {"conn": conn, "kwargs": kwargs}

    def fake_write_latest(data: dict[str, object], path: Path, **kwargs: object) -> dict[str, object]:
        captured["write_latest"] = {"data": data, "path": path, "kwargs": kwargs}
        return {"ok": True, "adapter": "latest"}

    def fake_write_maintain_latest(data: dict[str, object], path: Path, daily_root: Path) -> dict[str, object]:
        captured["write_maintain_latest"] = {"data": data, "path": path, "daily_root": daily_root}
        return {"ok": True, "adapter": "maintain"}

    def fake_source_chunks(path: Path, **kwargs: object):
        captured["source_chunks"] = {"path": path, "kwargs": kwargs}
        return [{"chunk_id": "chunk-a"}], None

    def fake_lock_active(path: Path) -> bool:
        captured["lock_active_root"] = path
        return True

    monkeypatch.setattr(cli, "NERVOUS_SEMANTIC_INDEX_DB_PATH", db_path)
    monkeypatch.setattr(cli, "NERVOUS_SEMANTIC_INDEX_ROOT", root)
    monkeypatch.setattr(cli, "NERVOUS_SEMANTIC_INDEX_LATEST_PATH", latest_path)
    monkeypatch.setattr(cli, "NERVOUS_SEMANTIC_MAINTAIN_LATEST_PATH", maintain_latest)
    monkeypatch.setattr(cli, "NERVOUS_SEMANTIC_MAINTAIN_ROOT", maintain_root)
    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_DB_PATH", source_db)
    monkeypatch.setattr(cli, "nervous_semantic_config", lambda: {"embedding": {"max_input_chars": 512}})
    monkeypatch.setattr(cli.nervous_semantic_adapters, "connect_db", fake_connect)
    monkeypatch.setattr(cli.nervous_semantic_adapters, "initialize_db", fake_initialize)
    monkeypatch.setattr(cli.nervous_semantic_adapters, "semantic_lock", fake_lock)
    monkeypatch.setattr(cli.nervous_semantic_adapters, "semantic_lock_active", fake_lock_active)
    monkeypatch.setattr(cli.nervous_semantic_adapters, "write_latest", fake_write_latest)
    monkeypatch.setattr(cli.nervous_semantic_adapters, "write_maintain_latest", fake_write_maintain_latest)
    monkeypatch.setattr(cli.nervous_semantic_adapters, "counts", lambda path: {"db_path": str(path), "from_adapter": True})
    monkeypatch.setattr(cli.nervous_semantic_adapters, "source_chunks", fake_source_chunks)

    assert cli.nervous_semantic_connect(create=True) is fake_conn
    cli.nervous_semantic_initialize(fake_conn)
    with cli.nervous_semantic_lock():
        pass
    assert cli.nervous_semantic_lock_active() is True
    assert cli.nervous_semantic_write_latest({"ok": True}) == {"ok": True, "adapter": "latest"}
    assert cli.nervous_semantic_maintain_write_latest({"ok": True}) == {"ok": True, "adapter": "maintain"}
    assert cli.nervous_semantic_counts()["from_adapter"] is True
    chunks, error = cli.nervous_semantic_source_chunks(max_chunks=3)

    assert chunks == [{"chunk_id": "chunk-a"}]
    assert error is None
    assert captured["connect"] == {"path": db_path, "create": True}
    assert captured["initialize"]["conn"] is fake_conn
    assert captured["initialize"]["kwargs"]["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["initialize"]["kwargs"]["version"] == cli.VERSION
    assert captured["lock_root"] == root
    assert captured["lock_active_root"] == root
    assert captured["write_latest"]["path"] == latest_path
    assert captured["write_latest"]["kwargs"]["group"] == cli.MODE_STATE_GROUP
    assert captured["write_maintain_latest"]["path"] == maintain_latest
    assert captured["write_maintain_latest"]["daily_root"] == maintain_root
    assert captured["source_chunks"]["path"] == source_db
    assert captured["source_chunks"]["kwargs"]["max_chunks"] == 3
    assert captured["source_chunks"]["kwargs"]["max_input_chars"] == 512


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

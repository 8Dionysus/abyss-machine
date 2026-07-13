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


def test_semantic_maintain_adapter_dry_run_refreshes_index_through_resource_port(tmp_path: Path) -> None:
    calls: list[tuple[str, object]] = []

    def latest_writer(data: dict[str, object]) -> dict[str, object]:
        calls.append(("latest", data["decision"]))
        return {**data, "written": True}

    def resource_launch(command: list[str], **kwargs: object) -> dict[str, object]:
        calls.append(("launch", {"command": command, "kwargs": kwargs}))
        return {"ok": True, "dry_run": kwargs.get("dry_run")}

    data = nervous_semantic_adapters.semantic_maintain_document(
        semantic_config={"maintain": {"index_refresh_timeout_sec": 42, "resource_class": "medium"}},
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-07-07T00:00:00+00:00",
        maintain_latest_path=tmp_path / "maintain" / "latest.json",
        maintain_daily_root=tmp_path / "maintain",
        semantic_latest_path=tmp_path / "semantic" / "latest.json",
        index_status=lambda: {
            "ok": True,
            "ready": False,
            "warnings": ["missing-source-index"],
            "freshness": {"stale": True, "records_lag": 12},
            "counts": {"chunks": 5, "documents": 3, "meta": {"run_id": "idx-old", "built_at": "2026-07-06T23:00:00+00:00"}},
        },
        semantic_status=lambda: {"ready": True, "freshness": {"source_chunks": 5, "vectors": 5}, "counts": {"vectors": 5, "meta": {}}},
        lock_active=lambda: (_ for _ in ()).throw(AssertionError("dry-run index refresh must not inspect semantic lock")),
        resource_launch=resource_launch,
        memory_plan=lambda: (_ for _ in ()).throw(AssertionError("pre-refresh dry-run exits before batch policy")),
        latest_writer=latest_writer,
        json_parser=lambda _stdout: None,
        dry_run=True,
        write_latest=True,
    )

    assert data["written"] is True
    assert data["decision"] == "dry_run_refresh_index"
    assert data["index_refresh"]["before"]["counts"]["run_id"] == "idx-old"
    assert data["index_refresh"]["launch"] == {"ok": True, "dry_run": True}
    assert calls[0][0] == "launch"
    assert calls[0][1]["command"] == ["abyss-machine", "nervous", "index-build", "--json"]
    assert calls[0][1]["kwargs"]["timeout_sec"] == 42
    assert calls[0][1]["kwargs"]["write_latest"] is False
    assert calls[-1] == ("latest", "dry_run_refresh_index")


def test_semantic_maintain_adapter_blocks_build_launch_through_resource_port(tmp_path: Path) -> None:
    lock_calls: list[bool] = []
    launches: list[dict[str, object]] = []

    def resource_launch(command: list[str], **kwargs: object) -> dict[str, object]:
        launches.append({"command": command, "kwargs": kwargs})
        return {"ok": False, "blocked_reasons": ["memory_hot"]}

    data = nervous_semantic_adapters.semantic_maintain_document(
        semantic_config={"maintain": {"min_delta_chunks": 2, "max_stale_minutes": 10, "success_on_block": True}},
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-07-07T00:00:00+00:00",
        maintain_latest_path=tmp_path / "maintain" / "latest.json",
        maintain_daily_root=tmp_path / "maintain",
        semantic_latest_path=tmp_path / "semantic" / "latest.json",
        index_status=lambda: {
            "ok": True,
            "ready": True,
            "freshness": {"stale": False, "records_lag": 0},
            "counts": {"chunks": 10, "documents": 4, "meta": {"run_id": "idx-new", "built_at": "2026-07-07T00:00:00+00:00"}},
        },
        semantic_status=lambda: {
            "ready": True,
            "freshness": {
                "source_index_run_id": "idx-new",
                "semantic_source_index_run_id": "idx-old",
                "source_chunks": 10,
                "vectors": 1,
            },
            "source_index": {"run_id": "idx-new", "built_at": "2026-07-07T00:00:00+00:00", "chunks": 10},
            "counts": {"vectors": 1, "meta": {"source_index_run_id": "idx-old"}},
            "embedding": {"batch_size": 16},
        },
        lock_active=lambda: lock_calls.append(True) or False,
        resource_launch=resource_launch,
        memory_plan=lambda: {"class": "normal", "pressure": {"summary": {}}},
        latest_writer=lambda data: {**data, "written": True},
        json_parser=lambda _stdout: None,
        write_latest=True,
    )

    assert data["written"] is True
    assert data["decision"] == "blocked"
    assert data["ok"] is True
    assert data["reason"] == "resource gate blocked semantic maintenance launch"
    assert data["assessment"]["delta_chunks"] == 9
    assert data["build_command"] == ["abyss-machine", "nervous", "semantic-build", "--json"]
    assert lock_calls == [True]
    assert launches == [
        {
            "command": ["abyss-machine", "nervous", "semantic-build", "--json"],
            "kwargs": {
                "workload_class": "medium",
                "kind": "indexing",
                "unattended": True,
                "dry_run": False,
                "timeout_sec": 1800.0,
                "sample_thermal": None,
                "write_latest": True,
            },
        }
    ]


def test_cli_nervous_semantic_maintain_binds_orchestration_adapter(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(cli, "NERVOUS_SEMANTIC_MAINTAIN_LATEST_PATH", tmp_path / "maintain" / "latest.json")
    monkeypatch.setattr(cli, "NERVOUS_SEMANTIC_MAINTAIN_ROOT", tmp_path / "maintain")
    monkeypatch.setattr(cli, "NERVOUS_SEMANTIC_INDEX_LATEST_PATH", tmp_path / "semantic" / "latest.json")
    monkeypatch.setattr(cli, "nervous_semantic_config", lambda: {"maintain": {"min_delta_chunks": 7}})

    def fake_adapter(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"ok": True, "from_adapter": True}

    monkeypatch.setattr(nervous_semantic_adapters, "semantic_maintain_document", fake_adapter)

    data = cli.nervous_semantic_maintain(
        min_delta_chunks=3,
        max_stale_minutes=4.5,
        timeout_sec=9,
        dry_run=True,
        force_refresh=True,
        max_chunks=11,
        batch_size=2,
        rebuild=True,
        no_thermal_sample=True,
        refresh_index_first=False,
        write_latest=False,
    )

    assert data == {"ok": True, "from_adapter": True}
    assert captured["semantic_config"] == {"maintain": {"min_delta_chunks": 7}}
    assert captured["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["version"] == cli.VERSION
    assert captured["maintain_latest_path"] == tmp_path / "maintain" / "latest.json"
    assert captured["maintain_daily_root"] == tmp_path / "maintain"
    assert captured["semantic_latest_path"] == tmp_path / "semantic" / "latest.json"
    assert captured["lock_active"] is cli.nervous_semantic_lock_active
    assert captured["resource_launch"] is cli.resource_launch
    assert captured["latest_writer"] is cli.nervous_semantic_maintain_write_latest
    assert captured["json_parser"] is cli.parse_json_stdout
    assert captured["min_delta_chunks"] == 3
    assert captured["max_stale_minutes"] == 4.5
    assert captured["timeout_sec"] == 9
    assert captured["dry_run"] is True
    assert captured["force_refresh"] is True
    assert captured["max_chunks"] == 11
    assert captured["batch_size"] == 2
    assert captured["rebuild"] is True
    assert captured["no_thermal_sample"] is True
    assert captured["refresh_index_first"] is False
    assert captured["write_latest"] is False


def test_semantic_search_adapter_dispatches_fake_vector_search(tmp_path: Path) -> None:
    calls: list[tuple[str, object]] = []

    def query_vector(query: str, embedding: dict[str, object], force_policy: bool = False) -> dict[str, object]:
        calls.append(("query_vector", {"query": query, "embedding": embedding, "force_policy": force_policy}))
        return {"ok": True, "blob": b"query-vector", "dim": 2, "embedding_status": {"ok": True}}

    def search_with_vector(**kwargs: object) -> dict[str, object]:
        calls.append(("search_with_vector", {key: value for key, value in kwargs.items() if key != "query_vector_blob"}))
        return {"ok": True, "summary": {"results": 1}, "results": [{"chunk_id": "hit"}]}

    data = nervous_semantic_adapters.semantic_search_document(
        query="thermal zram",
        semantic_config={"embedding": {"model_dir": "/models/embed"}, "search": {"default_limit": 8, "max_limit": 20}},
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-07-07T03:00:00+00:00",
        db_path=tmp_path / "semantic.db",
        privacy={},
        counts=lambda: {"vectors": 3},
        db_exists=lambda path: path == tmp_path / "semantic.db",
        query_vector=query_vector,
        semantic_search_with_vector=search_with_vector,
        limit=99,
        dedupe=False,
        source="nervous_events",
        schema="abyss_machine_nervous_event_v1",
        since="2026-07-01T00:00:00+00:00",
        until="2026-07-07T00:00:00+00:00",
        severity="warn",
        sensitivity="normal",
        force_policy=True,
    )

    assert data["ok"] is True
    assert data["summary"] == {"results": 1}
    assert calls[0] == (
        "query_vector",
        {"query": "thermal zram", "embedding": {"model_dir": "/models/embed"}, "force_policy": True},
    )
    assert calls[1][0] == "search_with_vector"
    assert calls[1][1]["query"] == "thermal zram"
    assert calls[1][1]["query_vector_result"]["dim"] == 2
    assert calls[1][1]["final_limit"] == 20
    assert calls[1][1]["dedupe"] is False
    assert calls[1][1]["source"] == "nervous_events"
    assert calls[1][1]["schema"] == "abyss_machine_nervous_event_v1"
    assert calls[1][1]["since"] == "2026-07-01T00:00:00+00:00"
    assert calls[1][1]["until"] == "2026-07-07T00:00:00+00:00"
    assert calls[1][1]["severity"] == "warn"
    assert calls[1][1]["sensitivity"] == "normal"


def test_semantic_search_adapter_preflight_is_lazy_and_public_safe(tmp_path: Path) -> None:
    calls: list[str] = []

    def counts() -> dict[str, object]:
        calls.append("counts")
        return {"vectors": 0}

    def query_vector(*args: object, **kwargs: object) -> dict[str, object]:
        calls.append("query_vector")
        return {"ok": True, "blob": b"query-vector"}

    def search_with_vector(**kwargs: object) -> dict[str, object]:
        calls.append("search_with_vector")
        return {"ok": True}

    paused = nervous_semantic_adapters.semantic_search_document(
        query="paused",
        semantic_config={},
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-07-07T03:00:00+00:00",
        db_path=tmp_path / "missing.db",
        privacy={"global_pause": True},
        counts=counts,
        db_exists=lambda path: False,
        query_vector=query_vector,
        semantic_search_with_vector=search_with_vector,
    )
    missing = nervous_semantic_adapters.semantic_search_document(
        query="missing",
        semantic_config={},
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-07-07T03:00:00+00:00",
        db_path=tmp_path / "missing.db",
        privacy={},
        counts=counts,
        db_exists=lambda path: False,
        query_vector=query_vector,
        semantic_search_with_vector=search_with_vector,
    )
    no_vectors = nervous_semantic_adapters.semantic_search_document(
        query="empty",
        semantic_config={},
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-07-07T03:00:00+00:00",
        db_path=tmp_path / "semantic.db",
        privacy={},
        counts=counts,
        db_exists=lambda path: True,
        query_vector=query_vector,
        semantic_search_with_vector=search_with_vector,
    )

    assert paused["refused"] is True
    assert paused["error"] == "global_pause is active; semantic search is refused"
    assert missing["db_path"] == str(tmp_path / "missing.db")
    assert "run abyss-machine nervous semantic-build --json" in missing["error"]
    assert no_vectors["counts"] == {"vectors": 0}
    assert "host policy allows medium AI work" in no_vectors["error"]
    assert calls == ["counts"]


def test_semantic_search_adapter_projects_query_vector_policy_denial(tmp_path: Path) -> None:
    calls: list[str] = []

    def search_with_vector(**kwargs: object) -> dict[str, object]:
        calls.append("search_with_vector")
        return {"ok": True}

    data = nervous_semantic_adapters.semantic_search_document(
        query="blocked",
        semantic_config={"embedding": {"model_dir": "/models/embed"}},
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-07-07T03:00:00+00:00",
        db_path=tmp_path / "semantic.db",
        privacy={},
        counts=lambda: {"vectors": 1},
        db_exists=lambda path: True,
        query_vector=lambda query, embedding, force_policy=False: {
            "ok": False,
            "policy_denied": True,
            "policy_gate": {"ok": False, "reason": "test"},
            "error": "host AI policy denied semantic search",
        },
        semantic_search_with_vector=search_with_vector,
        force_policy=False,
    )

    assert data["ok"] is False
    assert data["query"] == "blocked"
    assert data["policy_denied"] is True
    assert data["policy_gate"] == {"ok": False, "reason": "test"}
    assert calls == []


def test_cli_nervous_semantic_search_binds_adapter_ports(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(cli, "NERVOUS_SEMANTIC_INDEX_DB_PATH", tmp_path / "semantic.db")
    monkeypatch.setattr(cli, "nervous_semantic_config", lambda: {"embedding": {"model_dir": "/models/embed"}})
    monkeypatch.setattr(cli, "nervous_effective_privacy", lambda write_latest=False: {"global_pause": False, "write_latest": write_latest})
    monkeypatch.setattr(cli, "nervous_semantic_counts", lambda: {"vectors": 4})
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-07-07T03:00:00+00:00")

    def fake_adapter(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"ok": True, "from_adapter": True}

    monkeypatch.setattr(nervous_semantic_adapters, "semantic_search_document", fake_adapter)

    data = cli.nervous_semantic_search(
        "thermal",
        limit=7,
        dedupe=False,
        source="nervous_events",
        schema="schema",
        since="since",
        until="until",
        severity="warn",
        sensitivity="normal",
        force_policy=True,
    )

    assert data == {"ok": True, "from_adapter": True}
    assert captured["query"] == "thermal"
    assert captured["semantic_config"] == {"embedding": {"model_dir": "/models/embed"}}
    assert captured["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["version"] == cli.VERSION
    assert captured["generated_at"] == "2026-07-07T03:00:00+00:00"
    assert captured["db_path"] == tmp_path / "semantic.db"
    assert captured["privacy"] == {"global_pause": False, "write_latest": False}
    assert captured["counts"]() == {"vectors": 4}
    assert captured["db_exists"](tmp_path / "semantic.db") is False
    assert captured["query_vector"] is cli.nervous_semantic_query_vector
    assert captured["semantic_search_with_vector"] is cli.nervous_semantic_search_with_vector
    assert captured["limit"] == 7
    assert captured["dedupe"] is False
    assert captured["source"] == "nervous_events"
    assert captured["schema"] == "schema"
    assert captured["since"] == "since"
    assert captured["until"] == "until"
    assert captured["severity"] == "warn"
    assert captured["sensitivity"] == "normal"
    assert captured["force_policy"] is True


def test_semantic_eval_adapter_runs_fake_ports_without_writing(tmp_path: Path) -> None:
    calls: list[tuple[str, object]] = []
    vector = array.array("f", [1.0, 0.0]).tobytes()
    probes = [
        {"id": "thermal", "query": "thermal zram", "preferred_sources": {"nervous_events"}},
        {"id": "desktop", "query": "gnome pidfd", "avoid_top_sources": {"screenshots"}},
    ]

    def embed_texts(text_items: list[dict[str, str]], embedding: dict[str, object]) -> dict[str, object]:
        calls.append(("embed", {"items": text_items, "embedding": embedding}))
        return {
            "ok": True,
            "vectors": {
                "thermal": {"dim": 2, "blob": vector},
                "desktop": {"dim": 2, "blob": vector},
            },
            "summary": {"items": 2},
        }

    def lexical_search(query: str) -> dict[str, object]:
        calls.append(("lexical", query))
        return {"ok": True, "results": [{"source_id": "nervous_events", "title": f"lexical {query}"}]}

    def semantic_search_with_vector(**kwargs: object) -> dict[str, object]:
        calls.append(("semantic", {key: value for key, value in kwargs.items() if key != "query_vector_blob"}))
        return {
            "ok": True,
            "results": [
                {
                    "source_id": "nervous_events",
                    "title": f"semantic {kwargs['query']}",
                    "score": 0.875,
                }
            ],
        }

    data = nervous_semantic_adapters.semantic_eval_document(
        semantic_config={"embedding": {"batch_size": 2}},
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-07-07T02:00:00+00:00",
        latest_path=tmp_path / "semantic-eval" / "latest.json",
        daily_root=tmp_path / "semantic-eval",
        semantic_status=lambda: {"ready": True, "freshness": {"vectors": 2}},
        policy_gate=lambda: {"ok": True, "class": "medium"},
        embed_texts=embed_texts,
        lexical_search=lexical_search,
        semantic_search_with_vector=semantic_search_with_vector,
        latest_writer=lambda document: {**document, "written": True},
        probes=probes,
        write_latest=True,
    )

    assert data["written"] is True
    assert data["ok"] is True
    assert data["status"] == "ok"
    assert data["summary"] == {"fails": 0, "warnings": 0, "checks": 5, "probes": 2}
    assert data["embedding_status"]["summary"] == {"items": 2}
    assert data["results"][0]["semantic"]["top_scores"] == [0.875]
    assert data["results"][1]["semantic"]["top_sources"] == ["nervous_events"]
    assert not (tmp_path / "semantic-eval").exists()
    assert calls[0][0] == "embed"
    assert calls[0][1]["items"][0]["id"] == "thermal"
    assert calls[1] == ("lexical", "thermal zram")
    assert calls[2][0] == "semantic"
    assert calls[2][1]["query_vector_result"]["dim"] == 2


def test_semantic_eval_adapter_projects_policy_denial_without_embedding(tmp_path: Path) -> None:
    calls: list[str] = []

    def embed_texts(text_items: list[dict[str, str]], embedding: dict[str, object]) -> dict[str, object]:
        calls.append("embed")
        return {"ok": True, "vectors": {}}

    def semantic_search_with_vector(**kwargs: object) -> dict[str, object]:
        calls.append("semantic")
        return {"ok": True, "results": []}

    data = nervous_semantic_adapters.semantic_eval_document(
        semantic_config={"embedding": {"batch_size": 2}},
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-07-07T02:00:00+00:00",
        latest_path=tmp_path / "semantic-eval" / "latest.json",
        daily_root=tmp_path / "semantic-eval",
        semantic_status=lambda: {"ready": True, "freshness": {"vectors": 2}},
        policy_gate=lambda: {"ok": False, "reason": "test policy"},
        embed_texts=embed_texts,
        lexical_search=lambda query: {"ok": True, "results": []},
        semantic_search_with_vector=semantic_search_with_vector,
        latest_writer=lambda document: document,
        probes=[{"id": "blocked", "query": "blocked query"}],
        write_latest=False,
    )

    assert data["ok"] is False
    assert data["status"] == "fail"
    assert data["summary"] == {"fails": 1, "warnings": 0, "checks": 2, "probes": 1}
    assert data["embedding_status"]["policy_denied"] is True
    assert data["results"][0]["semantic"]["policy_denied"] is True
    assert calls == []


def test_cli_nervous_semantic_eval_binds_adapter_ports(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(cli, "NERVOUS_SEMANTIC_EVAL_LATEST_PATH", tmp_path / "eval" / "latest.json")
    monkeypatch.setattr(cli, "NERVOUS_SEMANTIC_EVAL_ROOT", tmp_path / "eval")
    monkeypatch.setattr(cli, "nervous_semantic_config", lambda: {"embedding": {"batch_size": 3}})
    monkeypatch.setattr(cli, "nervous_semantic_status", lambda write_latest=False: {"ready": True, "write_latest": write_latest})
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-07-07T02:00:00+00:00")
    monkeypatch.setattr(cli, "ai_policy_gate_for_class", lambda cls, action, force=False: {"ok": True, "class": cls, "action": action, "force": force})

    def fake_adapter(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"ok": True, "from_adapter": True}

    monkeypatch.setattr(nervous_semantic_adapters, "semantic_eval_document", fake_adapter)

    data = cli.nervous_semantic_eval(force_policy=True, write_latest=False)

    assert data == {"ok": True, "from_adapter": True}
    assert captured["semantic_config"] == {"embedding": {"batch_size": 3}}
    assert captured["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["version"] == cli.VERSION
    assert captured["generated_at"] == "2026-07-07T02:00:00+00:00"
    assert captured["latest_path"] == tmp_path / "eval" / "latest.json"
    assert captured["daily_root"] == tmp_path / "eval"
    assert captured["semantic_status"]() == {"ready": True, "write_latest": False}
    assert captured["policy_gate"]() == {"ok": True, "class": "medium", "action": "nervous semantic-eval", "force": True}
    assert captured["embed_texts"] is cli.nervous_semantic_embed_texts
    assert captured["semantic_search_with_vector"] is cli.nervous_semantic_search_with_vector
    assert captured["latest_writer"] is cli.nervous_semantic_eval_write_latest
    assert captured["write_latest"] is False


def test_semantic_build_pending_plan_classifies_reuse_and_embedding() -> None:
    chunks = [
        {"chunk_id": "same", "body_sha256": "hash-same"},
        {"chunk_id": "reuse", "body_sha256": "hash-reuse"},
        {"chunk_id": "embed", "body_sha256": "hash-embed"},
    ]

    plan = nervous_semantic_adapters.semantic_build_pending_plan(
        chunks,
        existing={"same": "hash-same", "reuse": "old-hash"},
        existing_vectors_by_hash={"hash-reuse": {"dim": 2, "blob": b"reuse-vector"}},
        rebuild=False,
    )
    rebuild_plan = nervous_semantic_adapters.semantic_build_pending_plan(
        chunks,
        existing={"same": "hash-same"},
        existing_vectors_by_hash={"hash-reuse": {"dim": 2, "blob": b"reuse-vector"}},
        rebuild=True,
    )

    assert [item["chunk_id"] for item in plan["pending"]] == ["reuse", "embed"]
    assert set(plan["pending_by_id"]) == {"reuse", "embed"}
    assert plan["reuse_vectors"] == {"reuse": {"dim": 2, "blob": b"reuse-vector"}}
    assert [item["chunk_id"] for item in plan["embed_pending"]] == ["embed"]
    assert plan["summary"] == {
        "source_chunks_selected": 3,
        "existing_vectors": 2,
        "pending_chunks": 2,
        "embedding_pending_chunks": 1,
        "vectors_reused_by_body_hash": 1,
        "unchanged_chunks": 1,
        "vectors_indexed": 0,
        "stale_vectors_deleted": 0,
    }
    assert [item["chunk_id"] for item in rebuild_plan["embed_pending"]] == ["same", "reuse", "embed"]
    assert rebuild_plan["reuse_vectors"] == {}


def test_semantic_build_document_preflight_shapes_public_safe_receipts(tmp_path: Path) -> None:
    embedding = nervous_semantic_adapters.semantic_build_embedding_config(
        {"model_dir": "/models/embed", "batch_size": 16, "max_tokens": 256, "pooling": "last_token"},
        batch_size=4,
        device="CPU",
    )
    command = nervous_semantic_adapters.semantic_build_command(
        max_chunks=8,
        batch_size=4,
        device="CPU",
        rebuild=True,
    )
    refusal = nervous_semantic_adapters.semantic_build_refusal_document(
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-07-07T01:00:00+00:00",
        run_id="semantic-run",
        refused=True,
        error="global_pause is active",
    )
    document = nervous_semantic_adapters.semantic_build_initial_document(
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-07-07T01:00:00+00:00",
        run_id="semantic-run",
        started_at="2026-07-07T00:59:00+00:00",
        db_path=tmp_path / "semantic.db",
        source_index_db_path=tmp_path / "source.db",
        latest_path=tmp_path / "latest.json",
        source_counts={"chunks": 12, "meta": {"run_id": "idx-run", "built_at": "2026-07-07T00:50:00+00:00"}},
        partial=True,
        max_chunks=8,
        rebuild=True,
        build_command=command,
        semantic_config={"backend": "sqlite_float32_sidecar"},
        embedding=embedding,
        model_dir=Path("/models/embed"),
        device="CPU",
        cache_dir=tmp_path / "cache",
        cache_before={"exists": False, "mtime": None},
    )

    assert embedding["batch_size"] == 4
    assert embedding["device"] == "CPU"
    assert command == [
        "abyss-machine",
        "nervous",
        "semantic-build",
        "--json",
        "--max-chunks",
        "8",
        "--batch-size",
        "4",
        "--device",
        "CPU",
        "--rebuild",
    ]
    assert refusal["refused"] is True
    assert refusal["error"] == "global_pause is active"
    assert document["source_index"]["run_id"] == "idx-run"
    assert document["provenance"]["probe"]["type"] == "bounded_rebuild"
    assert document["provenance"]["compile_cache"]["before"] == {"exists": False, "mtime": None}
    assert "chunks" not in document


def test_semantic_build_source_reload_and_policy_outcomes() -> None:
    data: dict[str, object] = {}

    assert nervous_semantic_adapters.semantic_build_source_index_changed(
        {"chunks": 10, "meta": {"run_id": "idx-a"}},
        {"chunks": 10, "meta": {"run_id": "idx-a"}},
    ) is False
    assert nervous_semantic_adapters.semantic_build_source_index_changed(
        {"chunks": 10, "meta": {"run_id": "idx-a"}},
        {"chunks": 11, "meta": {"run_id": "idx-b"}},
    ) is True

    nervous_semantic_adapters.semantic_build_mark_source_index_reloaded(
        data,
        {"chunks": 11, "meta": {"run_id": "idx-b", "built_at": "2026-07-07T01:02:00+00:00"}},
    )
    nervous_semantic_adapters.semantic_build_apply_source_error(data, {"error": "source unavailable", "db": "/private/source.db"})
    nervous_semantic_adapters.semantic_build_defer_source_index_active(data)
    nervous_semantic_adapters.semantic_build_apply_policy_denial(data, {"ok": False, "denied_reasons": ["thermal_hot"]})

    assert data["source_index_reloaded_under_lock"] is True
    assert data["source_index"]["run_id"] == "idx-b"
    assert data["deferred"] is True
    assert data["policy_denied"] is True
    assert data["error"] == "host AI policy denied semantic embedding build"


def test_semantic_build_finalize_success_updates_meta_provenance_and_counts(tmp_path: Path) -> None:
    conn = sqlite3.connect(":memory:")
    data = {
        "summary": {"vectors_indexed": 1, "stale_vectors_deleted": 0},
        "provenance": {"compile_cache": {"before": {"exists": True, "mtime": 1}}},
    }
    chunks = [{"chunk_id": "a"}, {"chunk_id": "b"}]
    pending = [{"chunk_id": "a"}]
    finish_calls: list[dict[str, object]] = []
    state_calls: list[dict[str, object]] = []
    times = iter(["2026-07-07T01:03:00+00:00", "2026-07-07T01:04:00+00:00"])

    def fake_finish(_conn: sqlite3.Connection, **kwargs: object) -> int:
        finish_calls.append(kwargs)
        return 2

    def fake_state_mode(path: Path, **kwargs: object) -> None:
        state_calls.append({"path": path, "kwargs": kwargs})

    result = nervous_semantic_adapters.semantic_build_finalize_success(
        conn,
        data,
        schema_prefix="abyss_machine",
        version="test-version",
        source_counts={"chunks": 7, "meta": {"run_id": "idx-run", "built_at": "2026-07-07T00:50:00+00:00"}},
        chunks=chunks,
        embedding={"model_dir": "/models/embed", "device": "CPU", "dimension": 384, "max_tokens": 256},
        run_id="semantic-run",
        started_at="2026-07-07T01:00:00+00:00",
        partial=False,
        cache_before={"exists": True, "mtime": 1},
        cache_dir=tmp_path / "cache",
        cache_stats=lambda _path: {"exists": True, "mtime": 2},
        now=lambda: next(times),
        indexed=3,
        pending=pending,
        reuse_vectors={"b": {"dim": 384}},
        db_path=tmp_path / "semantic.db",
        embed_pending=pending,
        state_group="test-group",
        counts_port=lambda: {"vectors": 3, "build_runs": 1},
        finish_successful_build_run_port=fake_finish,
        state_mode_port=fake_state_mode,
    )
    conn.close()

    assert result["ok"] is True
    assert result["finished_at"] == "2026-07-07T01:04:00+00:00"
    assert result["counts"] == {"vectors": 3, "build_runs": 1}
    assert result["summary"]["vectors_indexed"] == 3
    assert result["summary"]["stale_vectors_deleted"] == 2
    assert result["provenance"]["compile_cache"]["after"] == {"exists": True, "mtime": 2}
    assert result["provenance"]["compile_cache"]["mtime_changed"] is True
    assert result["provenance"]["compile_cache"]["used_or_regenerated"] is True
    assert result["provenance"]["vectors_reused_by_body_hash"] == 1
    assert finish_calls[0]["meta_values"]["source_index_run_id"] == "idx-run"
    assert finish_calls[0]["meta_values"]["selected_chunks"] == "2"
    assert finish_calls[0]["finished_at"] == "2026-07-07T01:04:00+00:00"
    assert finish_calls[0]["current_chunk_ids"] == {"a", "b"}
    assert state_calls == [{"path": tmp_path / "semantic.db", "kwargs": {"group": "test-group"}}]


def test_semantic_build_embedding_windows_fallbacks_and_progressively_inserts(tmp_path: Path) -> None:
    conn = sqlite3.connect(":memory:")
    data = {
        "summary": {"vectors_indexed": 1, "vectors_reused_by_body_hash": 1},
        "provenance": {"compile_cache": {"before": {"mtime": 10}}},
    }
    pending = [
        {"chunk_id": "a", "embedding_text": "alpha"},
        {"chunk_id": "b", "embedding_text": "beta"},
    ]
    calls: list[dict[str, object]] = []
    inserted: list[dict[str, object]] = []

    def fake_embed_texts(text_items: list[dict[str, str]], embedding: dict[str, object]) -> dict[str, object]:
        calls.append({"text_items": text_items, "embedding": dict(embedding)})
        if len(calls) == 1:
            return {"ok": False, "error": "batch too large"}
        vector = array.array("f", [1.0, 0.0]).tobytes()
        return {
            "ok": True,
            "vectors": {
                "a": {"dim": 2, "blob": vector},
                "b": {"dim": 2, "blob": vector},
            },
            "stdout_tail": "ok",
        }

    def fake_insert_vectors(_conn: sqlite3.Connection, vectors: dict[str, dict[str, object]], pending_by_id: dict[str, dict[str, object]], started_at: str) -> int:
        inserted.append({"vectors": sorted(vectors), "pending": sorted(pending_by_id), "started_at": started_at})
        return len(vectors)

    result = nervous_semantic_adapters.semantic_build_embedding_windows(
        conn,
        data,
        semantic_config={"maintain": {"embedding_window_chunks": 2}},
        embedding={"batch_size": 32},
        chunks=pending,
        pending=pending,
        pending_by_id={str(item["chunk_id"]): item for item in pending},
        embed_pending=pending,
        started_at="2026-07-07T01:00:00+00:00",
        run_id="semantic-run",
        partial=False,
        cache_before={"mtime": 10},
        cache_dir=tmp_path / "cache",
        cache_stats=lambda _path: {"exists": False, "mtime": 10},
        now=lambda: "2026-07-07T01:01:00+00:00",
        embed_texts=fake_embed_texts,
        insert_vectors_port=fake_insert_vectors,
    )
    conn.close()

    assert result["ok"] is True
    assert result["indexed"] == 3
    assert data["summary"]["vectors_indexed"] == 3
    assert data["embedding_status"]["vectors"] == 2
    assert data["embedding_status"]["windows"] == 1
    assert data["embedding_status"]["reused_by_body_hash"] == 1
    assert [call["embedding"]["batch_size"] for call in calls] == [32, 16]
    assert data["embedding_windows"][0]["attempts"][0]["error"] == "batch too large"
    assert data["embedding_windows"][0]["attempts"][1]["batch_size"] == 16
    assert inserted == [{"vectors": ["a", "b"], "pending": ["a", "b"], "started_at": "2026-07-07T01:00:00+00:00"}]


def test_semantic_build_embedding_windows_records_failure_and_cache_summary(tmp_path: Path) -> None:
    conn = sqlite3.connect(":memory:")
    data = {
        "summary": {"vectors_indexed": 0, "vectors_reused_by_body_hash": 0},
        "provenance": {"compile_cache": {"before": {"mtime": 1}}},
    }
    pending = [{"chunk_id": "a", "embedding_text": "alpha"}]
    failed_records: list[dict[str, object]] = []

    def fake_record_failed(_conn: sqlite3.Connection, **kwargs: object) -> None:
        failed_records.append(kwargs)

    result = nervous_semantic_adapters.semantic_build_embedding_windows(
        conn,
        data,
        semantic_config={"maintain": {"embedding_window_chunks": 1}},
        embedding={"batch_size": 8},
        chunks=pending,
        pending=pending,
        pending_by_id={"a": pending[0]},
        embed_pending=pending,
        started_at="2026-07-07T01:00:00+00:00",
        run_id="semantic-run",
        partial=True,
        cache_before={"mtime": 1},
        cache_dir=tmp_path / "cache",
        cache_stats=lambda _path: {"exists": True, "mtime": 2},
        now=lambda: "2026-07-07T01:02:00+00:00",
        embed_texts=lambda _items, _embedding: {"ok": False, "error": "runtime failed"},
        record_failed_build_run_port=fake_record_failed,
    )
    conn.close()

    assert result["ok"] is False
    assert data["error"] == "runtime failed"
    assert data["embedding_status"]["ok"] is False
    assert data["provenance"]["compile_cache"]["after"] == {"exists": True, "mtime": 2}
    assert data["provenance"]["compile_cache"]["mtime_changed"] is True
    assert data["provenance"]["compile_cache"]["used_or_regenerated"] is True
    assert failed_records[0]["run_id"] == "semantic-run"
    assert failed_records[0]["finished_at"] == "2026-07-07T01:02:00+00:00"
    assert failed_records[0]["partial"] is True
    assert failed_records[0]["errors"]["embedding_status"]["error"] == "runtime failed"


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


def test_cli_nervous_semantic_status_does_not_create_default_cache_dir(monkeypatch, tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    cache_root = tmp_path / "cache"

    def forbidden_cache_dir(_label: str = "general") -> Path:
        raise AssertionError("semantic status must not create the OpenVINO cache directory")

    monkeypatch.setattr(cli, "AI_OPENVINO_CACHE_ROOT", cache_root)
    monkeypatch.setattr(cli, "ai_openvino_cache_dir", forbidden_cache_dir)
    monkeypatch.setattr(cli, "nervous_semantic_config", lambda: {"enabled": True, "embedding": {"model_dir": str(model_dir)}})
    monkeypatch.setattr(cli, "nervous_semantic_counts", lambda: {"db_exists": False, "vectors": 0, "meta": {}})
    monkeypatch.setattr(cli, "nervous_index_db_counts", lambda: {"chunks": 0, "meta": {}})
    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_DB_PATH", tmp_path / "source.db")
    monkeypatch.setattr(cli, "NERVOUS_SEMANTIC_INDEX_DB_PATH", tmp_path / "semantic.db")
    monkeypatch.setattr(cli, "NERVOUS_SEMANTIC_INDEX_ROOT", tmp_path / "semantic")
    monkeypatch.setattr(cli, "NERVOUS_SEMANTIC_INDEX_LATEST_PATH", tmp_path / "semantic" / "latest.json")

    data = cli.nervous_semantic_status(write_latest=False)

    assert data["embedding"]["cache_dir"].startswith(str(cache_root))
    assert data["embedding"]["cache_exists"] is False
    assert not cache_root.exists()


def test_cli_nervous_semantic_build_global_pause_does_not_resolve_cache(monkeypatch) -> None:
    def forbidden_model_paths(_embedding: dict[str, object]):
        raise AssertionError("global_pause refusal must not resolve model/cache paths")

    monkeypatch.setattr(cli, "nervous_semantic_config", lambda: {"enabled": True, "embedding": {"model_dir": "/missing/model"}})
    monkeypatch.setattr(cli, "nervous_effective_privacy", lambda write_latest=False: {"global_pause": True})
    monkeypatch.setattr(cli, "nervous_semantic_model_paths", forbidden_model_paths)

    data = cli.nervous_semantic_build(write_latest=False)

    assert data["ok"] is False
    assert data["refused"] is True
    assert "global_pause" in data["error"]


def test_cli_nervous_semantic_build_disabled_does_not_resolve_cache(monkeypatch) -> None:
    def forbidden_model_paths(_embedding: dict[str, object]):
        raise AssertionError("disabled semantic build must not resolve model/cache paths")

    monkeypatch.setattr(cli, "nervous_semantic_config", lambda: {"enabled": False, "embedding": {"model_dir": "/missing/model"}})
    monkeypatch.setattr(cli, "nervous_effective_privacy", lambda write_latest=False: {"global_pause": False})
    monkeypatch.setattr(cli, "nervous_semantic_model_paths", forbidden_model_paths)

    data = cli.nervous_semantic_build(write_latest=False)

    assert data["ok"] is False
    assert data["error"] == "semantic index disabled by config"


def test_cli_nervous_semantic_build_binds_document_finalize_adapter(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    fake_conn = sqlite3.connect(":memory:")
    model_dir = tmp_path / "model"
    cache_dir = tmp_path / "cache"
    chunks = [{"chunk_id": "chunk-a", "body_sha256": "hash-a"}]

    @contextmanager
    def fake_lock():
        yield

    def fake_finalize(conn: sqlite3.Connection, data: dict[str, object], **kwargs: object) -> dict[str, object]:
        captured["conn"] = conn
        captured["data"] = dict(data)
        captured.update(kwargs)
        return {**data, "ok": True, "from_finalize": True}

    monkeypatch.setattr(cli, "nervous_change_id", lambda _kind: "semantic-run")
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-07-07T01:00:00+00:00")
    monkeypatch.setattr(cli, "nervous_semantic_config", lambda: {"enabled": True, "backend": "sqlite_float32_sidecar", "embedding": {"model_dir": str(model_dir), "batch_size": 16}})
    monkeypatch.setattr(cli, "nervous_effective_privacy", lambda write_latest=False: {"global_pause": False})
    monkeypatch.setattr(cli, "nervous_semantic_model_paths", lambda embedding: (model_dir, str(embedding.get("device") or "CPU"), cache_dir, None))
    monkeypatch.setattr(cli, "artifact_backup_state", lambda _path: {"state": "before"})
    monkeypatch.setattr(cli, "artifact_path_stats", lambda _path, _state: {"exists": True, "mtime": 1})
    monkeypatch.setattr(cli, "nervous_semantic_source_chunks", lambda max_chunks=None: (chunks, None))
    monkeypatch.setattr(cli, "nervous_index_db_counts", lambda: {"chunks": 1, "meta": {"run_id": "idx-run", "built_at": "2026-07-07T00:59:00+00:00"}})
    monkeypatch.setattr(cli, "nervous_semantic_lock", fake_lock)
    monkeypatch.setattr(cli, "nervous_index_lock_active", lambda: False)
    monkeypatch.setattr(cli, "nervous_semantic_connect", lambda create=False: fake_conn)
    monkeypatch.setattr(cli, "nervous_semantic_initialize", lambda _conn: None)
    monkeypatch.setattr(cli, "nervous_semantic_existing_hashes", lambda _conn: {})
    monkeypatch.setattr(cli, "nervous_semantic_existing_vectors_by_hash", lambda _conn: {})
    monkeypatch.setattr(
        nervous_semantic_adapters,
        "semantic_build_pending_plan",
        lambda _chunks, **_kwargs: {
            "pending": [],
            "pending_by_id": {},
            "reuse_vectors": {},
            "embed_pending": [],
            "summary": {
                "source_chunks_selected": 1,
                "existing_vectors": 0,
                "pending_chunks": 0,
                "embedding_pending_chunks": 0,
                "vectors_reused_by_body_hash": 0,
                "unchanged_chunks": 1,
                "vectors_indexed": 0,
                "stale_vectors_deleted": 0,
            },
        },
    )
    monkeypatch.setattr(nervous_semantic_adapters, "semantic_build_insert_reused_vectors", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(nervous_semantic_adapters, "semantic_build_embedding_windows", lambda *_args, **_kwargs: {"ok": True, "indexed": 0})
    monkeypatch.setattr(nervous_semantic_adapters, "semantic_build_finalize_success", fake_finalize)

    data = cli.nervous_semantic_build(max_chunks=1, batch_size=2, device="CPU", rebuild=True, write_latest=False)
    fake_conn.close()

    assert data["ok"] is True
    assert data["from_finalize"] is True
    assert captured["conn"] is fake_conn
    assert captured["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["version"] == cli.VERSION
    assert captured["chunks"] == chunks
    assert captured["embedding"]["batch_size"] == 2
    assert captured["embedding"]["device"] == "CPU"
    assert captured["run_id"] == "semantic-run"
    assert captured["partial"] is True
    assert captured["cache_dir"] == cache_dir
    assert captured["indexed"] == 0
    assert captured["pending"] == []
    assert captured["embed_pending"] == []
    assert captured["reuse_vectors"] == {}
    assert captured["db_path"] == cli.NERVOUS_SEMANTIC_INDEX_DB_PATH
    assert captured["state_group"] == cli.MODE_STATE_GROUP
    assert captured["counts_port"] is cli.nervous_semantic_counts
    assert captured["data"]["build_command"] == [
        "abyss-machine",
        "nervous",
        "semantic-build",
        "--json",
        "--max-chunks",
        "1",
        "--batch-size",
        "2",
        "--device",
        "CPU",
        "--rebuild",
    ]
